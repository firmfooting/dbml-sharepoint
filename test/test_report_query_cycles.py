# test/test_report_query_cycles.py
"""No reporting query may read, by any chain of names, a query that reads it.

Reported against release 4.0.0, the day after the self-reference was fixed:
a ten-list family's queries formed six mutual pairs and twelve cycles,
because a `count` over a child list read the child's QUERY while a `lookup`
on the child read the parent's, and each query carried the other's read. In
M two queries that name each other are a cyclic reference (Learn, M
specification, operator behavior), and the refresh fails naming neither.
Nine of the ten queries could not refresh.

The fix is that a cross-list read inlines the other list's rows: fetched
and keyed exactly as the list's query fetches them, under the internal
names, with none of the reporting-only columns. Nothing is named, so no
chain of reads can return to where it started, and that is what this
module pins: over every shipped family, and over the pair shape that
produced the report.
"""

import re
from pathlib import Path

import pytest
from _packs import pack
from _paths import engine_blueprints

from dbml_sharepoint.generators.report_m import generate_powerquery
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml

#: Core's blueprints and the suite's: this sweeps the engine's output, not the shipped set.
BLUEPRINTS = engine_blueprints()
FAMILIES = sorted(BLUEPRINTS)

_QUERY_REF = re.compile(r'#"([^"$][^"]*)"')


def _family(name: str) -> tuple[Schema, MappingBundle]:
    root = BLUEPRINTS[name]
    return (
        parse_dbml(root / "10-design" / "schema.dbml"),
        load_mapping(root / "20-configure" / "mapping.yaml"),
    )


def _reads(queries: dict[str, str]) -> dict[str, set[str]]:
    """Which query names each emitted query names, comments included: a
    name in a comment resolves to nothing, but the graph is read from the
    text a consumer pastes, and a stray reference there is still wrong."""
    return {
        filename[:-3]: set(_QUERY_REF.findall(text)) - {filename[:-3]}
        for filename, text in queries.items()
    }


def _cycles(graph: dict[str, set[str]]) -> list[tuple[str, ...]]:
    found: set[tuple[str, ...]] = set()

    def walk(start: str, node: str, path: tuple[str, ...]) -> None:
        for nxt in sorted(graph.get(node, ())):
            if nxt == start:
                pivot = path.index(min(path))
                found.add(path[pivot:] + path[:pivot])
            elif nxt not in path:
                walk(start, nxt, (*path, nxt))

    for name in graph:
        walk(name, name, (name,))
    return sorted(found, key=len)


@pytest.mark.parametrize("family", FAMILIES)
def test_no_shipped_pack_has_a_cycle_and_every_name_read_is_shipped(
    family: str,
) -> None:
    schema, bundle = _family(family)
    roles = sorted({entity.site_role for entity in bundle.mapping.entities.values()})
    for role in roles:
        queries = generate_powerquery(schema, bundle, role)
        graph = _reads(queries)
        assert _cycles(graph) == [], f"{family}/{role}"
        for reader, read in graph.items():
            missing = read - set(graph)
            assert not missing, f"{family}/{role}: {reader} reads {missing}"


# ------------------------------------------------------ the pair, minimal

_PAIR_DBML = """
Table Risk {
  Id int [pk, increment]
  Title nvarchar [not null]
  Score int
}

Table Action {
  Id int [pk, increment]
  Title nvarchar [not null]
  Status nvarchar
  RelatedRisk int [ref: > Risk.Id]
}
"""

_PAIR_MAPPING = """
entities:
  Risk: {kind: List, base_template: 100, site_role: default}
  Action: {kind: List, base_template: 100, site_role: default}
display_names:
  mode: auto
derived_columns:
  Risk:
    - kind: count
      from: Action
      via: RelatedRisk
      name: OpenActions
      aggregate: count
      type: Int64
      where: '[Status] = "Open"'
  Action:
    - kind: lookup
      from: Risk
      via: RelatedRisk
      pick:
        RiskScore: Score
      types:
        RiskScore: Int64
"""


def _pair(tmp_path: Path, site_url: str | None = None) -> dict[str, str]:
    schema, bundle = pack(tmp_path, _PAIR_DBML, _PAIR_MAPPING)
    return generate_powerquery(schema, bundle, "default", site_url=site_url)


def test_a_mutual_pair_renders_acyclic_with_the_rows_inlined_each_way(
    tmp_path: Path,
) -> None:
    queries = _pair(tmp_path)
    assert set(queries) == {"APP_Risk.pq", "APP_Action.pq"}
    assert _cycles(_reads(queries)) == []
    for reader, other in (("APP_Risk", "APP_Action"), ("APP_Action", "APP_Risk")):
        text = queries[f"{reader}.pq"]
        assert "    Rows1 =" in text
        assert f"getbytitle('{other}')/items" in text


def test_an_inlined_read_names_no_query_and_binds_no_url_of_its_own(
    tmp_path: Path,
) -> None:
    """The property that makes the graph acyclic by construction, and the
    one that makes a duplicate pointed at another site read that site's
    children: the inner `let` reads the enclosing query's SiteUrl. It is
    also why nothing is a function of the site: a data source behind a
    function parameter is dynamic and cannot be scheduled."""
    for site_url in (None, "https://tenant.sharepoint.com/sites/Ops"):
        query = _pair(tmp_path, site_url)["APP_Risk.pq"]
        inline = query.split("    Rows1 =\n", 1)[1].split("\n        in\n", 1)[0]
        assert not re.search(r'#"(?!\$)', inline), "an inlined read must read nothing by name"
        assert "SiteUrl =" not in inline.replace("WithSiteUrl =", "")
        assert "SiteUrlProblem =" not in inline
        assert "(SiteUrl as text)" not in query
        assert "Derived" not in inline
        assert "RenamedForModel" not in inline


def test_an_inlined_read_fetches_exactly_what_its_query_fetches(
    tmp_path: Path,
) -> None:
    """One rendering for both, so the rows read from another list are the
    rows that list's own query carries, step for step, up to the
    reporting-only columns."""
    queries = _pair(tmp_path)
    action, risk = queries["APP_Action.pq"], queries["APP_Risk.pq"]
    own = action.split("\nlet\n", 1)[1].split("    SiteName =", 1)[1].split(
        "    // Reporting-only columns", 1,
    )[0].rstrip().rstrip(",")
    inline = risk.split("    Rows1 =\n", 1)[1].split("\n        in\n", 1)[0]
    inline = "\n".join(line[8:] for line in inline.splitlines()[1:])
    assert own.strip() == inline.split("SiteName =", 1)[1].strip()


def test_a_list_is_inlined_once_per_reader_however_many_steps_read_it(
    tmp_path: Path,
) -> None:
    """Two steps over one child share a single fetch, not two."""
    second = (
        "    - kind: count\n      from: Action\n      via: RelatedRisk\n"
        "      name: AllActions\n      aggregate: count\n      type: Int64\n"
    )
    schema, bundle = pack(
        tmp_path, _PAIR_DBML,
        _PAIR_MAPPING.replace(
            "  Action:\n    - kind: lookup", second + "  Action:\n    - kind: lookup",
        ),
        dbml_name="two.dbml", mapping_name="two.yaml",
    )
    risk = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert "OpenActions" in risk
    assert "AllActions" in risk
    assert risk.count("    Rows1 =") == 1
    assert "    Rows2 =" not in risk


def test_a_count_over_a_base_coalesces_a_blank_to_zero_without_a_site_read(
    tmp_path: Path,
) -> None:
    """The child is fetched for this query's site, so an unmatched parent
    has zero children, and the site binding that used to decide between
    zero and null is gone with the reason for it."""
    risk = _pair(tmp_path)["APP_Risk.pq"]
    assert "DerivedSite" not in risk
    assert 'Table.Column(#"APP_Action"' not in risk
    assert "each if _ = null then 0 else _" in risk
