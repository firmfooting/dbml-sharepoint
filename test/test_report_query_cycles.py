# test/test_report_query_cycles.py
"""No reporting query may read, by any chain of names, a query that reads it.

Reported 2026-09-18 against release 4.0.0 of the `programme-governance`
pack, the day after its self-reference was fixed: the ten list queries
formed six mutual pairs and twelve cycles, because a `count` over a child
list read the child's QUERY while a `lookup` on the child read the
parent's, and each query carried the other's read. In M two queries that
name each other are a cyclic reference (Learn, M specification, operator
behavior), and the refresh fails naming neither. Nine of the ten queries
could not refresh.

The fix is a base function per list that another list reads: the rows
fetched and keyed exactly as the list's query fetches them, under the
internal names, with none of the reporting-only columns, taking the site
URL as its parameter. A cross-list read calls the base rather than naming
the query. A base reads nothing, so no chain of reads can return to where
it started, and that is what this module pins: over every shipped family,
and over the pair shape that produced the report.
"""

import re
from dataclasses import replace
from pathlib import Path

import pytest
from _model import bundle as make_bundle
from _model import column
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table
from _packs import pack
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.reporting.names import (
    BASE_SUFFIX,
    base_query_name,
    query_name,
)
from dbml_sharepoint.generators.report_m import generate_powerquery
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import DerivedColumn, MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml

FAMILIES = sorted(
    path.parent.parent.name
    for path in SOLUTION_TEMPLATES.glob("*/10-design/schema.dbml")
)

_QUERY_REF = re.compile(r'#"([^"]+)"')


def _family(name: str) -> tuple[Schema, MappingBundle]:
    root = SOLUTION_TEMPLATES / name
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


def test_the_reported_pairs_are_read_through_base_functions() -> None:
    """The instance that surfaced the class. Risk counts Actions and Action
    looks up its Risk; both reads now call the other's base, and neither
    query names the other."""
    queries = generate_powerquery(*_family("programme-governance"), "default")
    risk, action = queries["GOV_Risk.pq"], queries["GOV_Action.pq"]
    assert '#"GOV_Action_Base"(SiteRoot)' in risk
    assert '#"GOV_Risk_Base"(SiteRoot)' in action
    assert '#"GOV_Action"' not in risk
    assert '#"GOV_Risk"' not in action
    for name in ("GOV_Action_Base.pq", "GOV_Risk_Base.pq"):
        assert name in queries


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


def _pair(tmp_path: Path, **kwargs: str | None) -> dict[str, str]:
    schema, bundle = pack(tmp_path, _PAIR_DBML, _PAIR_MAPPING)
    return generate_powerquery(schema, bundle, "default", **kwargs)


def test_a_mutual_pair_renders_acyclic_with_a_base_each_way(tmp_path: Path) -> None:
    queries = _pair(tmp_path)
    assert set(queries) == {
        "APP_Risk.pq", "APP_Action.pq", "APP_Risk_Base.pq", "APP_Action_Base.pq",
    }
    assert _cycles(_reads(queries)) == []
    assert '#"APP_Action_Base"(SiteRoot)' in queries["APP_Risk.pq"]
    assert '#"APP_Risk_Base"(SiteRoot)' in queries["APP_Action.pq"]


def test_a_base_function_reads_no_query_and_takes_the_site_as_its_parameter(
    tmp_path: Path,
) -> None:
    """The property that makes the graph acyclic by construction, and the
    one that makes a duplicate pointed at another site read that site's
    children: the base is a function of the site, binding no URL of its
    own, baked pack or not."""
    for kwargs in ({}, {"site_url": "https://tenant.sharepoint.com/sites/Ops"}):
        base = _pair(tmp_path, **kwargs)["APP_Action_Base.pq"]
        code = [
            line for line in base.splitlines() if not line.strip().startswith("//")
        ]
        assert code[0] == "(SiteUrl as text) as table =>", code[0]
        assert code[1] == "let"
        assert '#"' not in "\n".join(code), "a base must read nothing by name"
        assert not any(line.strip().startswith("SiteUrl =") for line in code)
        assert 'Text.TrimEnd(SiteUrl, "/")' in base, "normalised like the query"
        assert "Derived" not in base
        assert "RenamedForModel" not in base
        assert "Reporting-only" not in base


def test_a_base_fetches_exactly_what_its_query_fetches(tmp_path: Path) -> None:
    """One rendering for both. The rows a query reads from another list
    through its base are the rows that list's own query carries, step for
    step, up to the reporting-only columns, so a base cannot drift from the
    query it stands in for."""
    queries = _pair(tmp_path)
    query, base = queries["APP_Action.pq"], queries["APP_Action_Base.pq"]
    query_fetch = query.split("\nlet\n", 1)[1].split(
        "    // Reporting-only columns", 1,
    )[0].rstrip().rstrip(",")
    base_fetch = base.split("\nlet\n", 1)[1].split("\nin\n", 1)[0].rstrip()
    assert query_fetch == base_fetch
    last_step = base.rsplit("\nin\n", 1)[1].strip()
    assert last_step.startswith("With"), last_step


def test_a_base_is_emitted_only_for_a_list_another_list_reads(tmp_path: Path) -> None:
    """A pack with no cross-list read is exactly what it was, and a list
    only its own steps read needs no base: a self-read reads the step above."""
    one_way = pack(
        tmp_path, _PAIR_DBML,
        _PAIR_MAPPING.split("  Action:\n", 1)[0],
        dbml_name="one.dbml", mapping_name="one.yaml",
    )
    queries = generate_powerquery(*one_way, "default")
    assert set(queries) == {"APP_Risk.pq", "APP_Action.pq", "APP_Action_Base.pq"}
    self_only = pack(
        tmp_path, _PAIR_DBML,
        _PAIR_MAPPING.split("derived_columns:", 1)[0]
        + "derived_columns:\n"
        "  Action:\n"
        "    - kind: count\n"
        "      from: Action\n"
        "      via: RelatedRisk\n"
        "      name: Siblings\n"
        "      aggregate: count\n"
        "      type: Int64\n",
        dbml_name="self.dbml", mapping_name="self.yaml",
    )
    assert set(generate_powerquery(*self_only, "default")) == {
        "APP_Risk.pq", "APP_Action.pq",
    }


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


# --------------------------------------------- the base name is one name

_PORTABLE_LIMIT = 184  # bytes, the same figure test_report_query_paths_are_portable holds


@pytest.mark.parametrize("length", [176, 177, 180, 181, 255])
def test_a_base_filename_stays_inside_the_portable_budget(
    tmp_path: Path, length: int,
) -> None:
    """Review of #590. The length budget was applied to the title part and
    `_Base` appended after it, so a title encoding to 177 to 180 bytes
    passed on its own and its base file came out at up to 188. The budget
    now runs over the whole basename, and the query names what the file is
    called, at every length either side of the limit."""
    schema, bundle = pack(
        tmp_path, _PAIR_DBML, _PAIR_MAPPING,
        dbml_name=f"len{length}.dbml", mapping_name=f"len{length}.yaml",
    )
    bundle.mapping.entities["Action"] = replace(
        bundle.mapping.entities["Action"], title="A" * length,
    )
    queries = generate_powerquery(schema, bundle, "default")
    for filename in queries:
        assert len(filename.encode("utf-8")) <= _PORTABLE_LIMIT, filename
    graph = _reads(queries)
    for reader, read in graph.items():
        assert read <= set(graph), f"{reader} reads a name that is not a file"
    base = base_query_name("A" * length)
    assert f"{base}.pq" in queries
    assert base.endswith(BASE_SUFFIX)


def test_a_reserved_stem_is_judged_on_the_whole_basename() -> None:
    """`CON_Base` is not a reserved stem, so nothing is escaped; `CON` alone
    still is. One rule over the composed name rather than one per part."""
    assert query_name("CON") == "%43ON"
    assert base_query_name("CON") == "CON_Base"
    assert base_query_name("CON .x") == "%43ON .x_Base"


def test_a_list_titled_like_another_lists_base_is_refused() -> None:
    """Every query that reads Risk would call the list instead."""
    schema = make_schema(
        make_table("Risk", column("Title")),
        make_table("Action", column("Title"), make_ref("RelatedRisk", "Risk.Id")),
        make_table("Other", column("Title")),
    )
    bundle = make_bundle(
        entities=["Risk", "Action", "Other"],
        derived_columns={"Action": [
            DerivedColumn(
                kind="lookup", from_entity="Risk", via="RelatedRisk",
                pick={"RiskTitle": "Title"}, types={"RiskTitle": "text"},
            ),
        ]},
    )
    bundle.mapping.entities["Other"] = replace(
        bundle.mapping.entities["Other"], title="APP_Risk_Base",
    )
    with pytest.raises(ValueError, match="collides"):
        generate_powerquery(schema, bundle, "default")
