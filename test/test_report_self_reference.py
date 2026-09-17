# test/test_report_self_reference.py
"""A derived step over a list's own rows must not name its own query.

Reported 2026-09-17 against release 4.0.0 by the consumer of a
`programme-governance` reporting pack: `GOV_Decision.pq` named
`#"GOV_Decision"` twice, once to read its own site and once to group itself
by `SupersedesDecision Key` for the back-reference to the superseding
decision. In M a query whose expression names itself is a cyclic reference
and the refresh fails.

Nothing short of a refresh sees it. The text parses, the model loads and a
name-resolution pass sees the name resolve, to the query being defined. So
the shape is pinned here: a step that reads its own list reads the step
above it, with the names that step carries, and a count over its own rows
needs no site binding because its rows are on its own site by construction.
"""

import re
from pathlib import Path

import pytest
from _packs import pack
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.generators.report_m import generate_powerquery
from dbml_sharepoint.generators.report_md import generate_reporting_md
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema, parse_dbml

FAMILIES = sorted(
    path.parent.parent.name
    for path in SOLUTION_TEMPLATES.glob("*/10-design/schema.dbml")
)

_SELF_REF_DBML = """
Table Risk {
  Id int [pk, increment]
  Title nvarchar [not null]
  Status nvarchar
  ParentRisk int [ref: > Risk.Id]
}
"""

_SELF_REF_MAPPING = """
entities:
  Risk: {kind: List, base_template: 100, site_role: default}
display_names:
  mode: auto
  overrides:
    Risk:
      Status: "State"
derived_columns:
  Risk:
    - kind: count
      from: Risk
      via: ParentRisk
      name: OpenChildren
      aggregate: count
      type: Int64
      where: '[Status] = "Open"'
    - kind: count
      from: Risk
      via: ParentRisk
      name: LastChildStatus
      aggregate: max
      type: text
      column: Status
"""


def _own_query(tmp_path: Path) -> str:
    schema, bundle = pack(tmp_path, _SELF_REF_DBML, _SELF_REF_MAPPING)
    return generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]


@pytest.mark.parametrize("family", FAMILIES)
def test_no_shipped_query_names_itself(family: str) -> None:
    root = SOLUTION_TEMPLATES / family
    schema = parse_dbml(root / "10-design" / "schema.dbml")
    bundle = load_mapping(root / "20-configure" / "mapping.yaml")
    for filename, text in generate_powerquery(schema, bundle, "default").items():
        own = f'#"{filename[:-3]}"'
        assert own not in text, f"{filename} names itself: a cyclic reference at refresh"


def test_a_self_count_groups_the_step_above_and_binds_no_site(tmp_path: Path) -> None:
    query = _own_query(tmp_path)
    assert '#"APP_Risk"' not in query
    assert "DerivedSite" not in query
    grouped = re.findall(r"Table\.Group\(\n\s+(\S+),", query)
    assert grouped, "no group step emitted"
    for source in grouped:
        assert source.startswith(("With", "Derived", "Table.SelectRows(With")), source
    # A blank over its own rows is a true zero: the rows are on this site.
    assert 'each if _ = null then 0 else _' in query


def test_a_self_read_uses_the_names_the_step_above_carries(tmp_path: Path) -> None:
    """The rename to display titles is the query's LAST step, so a step over
    its own rows sees internal names; a step over another query sees that
    query's renamed ones. `Status` is renamed to `State` here, and both the
    filter and the aggregated column must still read `Status`."""
    query = _own_query(tmp_path)
    assert 'each [Status] = "Open"' in query
    aggregated = query.split('"LastChildStatus"', 1)[1].split("JoinKind", 1)[0]
    assert "[Status]" in aggregated, aggregated
    assert "[State]" not in query.split("RenamedForModel")[0]
    assert '{"Status", "State"}' in query


def test_the_superseding_decision_is_read_without_a_cycle() -> None:
    """The declaration that surfaced the defect, on the shipped family."""
    root = SOLUTION_TEMPLATES / "programme-governance"
    schema = parse_dbml(root / "10-design" / "schema.dbml")
    bundle = load_mapping(root / "20-configure" / "mapping.yaml")
    decision = generate_powerquery(schema, bundle, "default")["GOV_Decision.pq"]
    assert '#"GOV_Decision"' not in decision
    assert '"SupersededByKey"' in decision
    assert "Reads this query's own rows" in decision


def test_the_guide_names_what_each_query_reads() -> None:
    """The consumer that loads the files under names of its own learns the
    dependencies from the guide, not from the refresh one import at a
    time. A query's read of its own rows is a step, not a name, and is not
    listed."""
    root = SOLUTION_TEMPLATES / "programme-governance"
    schema = parse_dbml(root / "10-design" / "schema.dbml")
    bundle = load_mapping(root / "20-configure" / "mapping.yaml")
    guide = generate_reporting_md(schema, bundle, "default")
    line = next(
        row for row in guide.splitlines() if row.startswith("- `GOV_Decision` reads ")
    )
    assert "`GOV_Action`" in line
    assert "`GOV_Decision`" not in line.split(" reads ", 1)[1]


# --------------------------------------------- what a self-read can see

_SELF_PROJECTION_DBML = """
Enum category {
  "Clinical"
  "Corporate"
}

Table Risk {
  Id int [pk, increment]
  Title nvarchar [not null]
  Category category
  ParentRisk int [ref: > Risk.Id]
}
"""

# A Choice cannot be fetched through `$expand` (measured 2026-09-10), so the
# projection is carried by joining the target's query: here, this query.
_SELF_PROJECTION_MAPPING = """
entities:
  Risk: {kind: List, base_template: 100, site_role: default}
display_names:
  mode: auto
  overrides:
    Risk:
      Category: "Kind"
lookup_projections:
  Risk:
    ParentRisk: [Category]
"""


def test_a_self_projection_keeps_the_internal_name_under_a_rename(tmp_path: Path) -> None:
    """The automatic key-joined projection is a self-read like any declared
    one: it reads the step above, which has not renamed `Category` yet."""
    schema, bundle = pack(tmp_path, _SELF_PROJECTION_DBML, _SELF_PROJECTION_MAPPING)
    query = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert '#"APP_Risk"' not in query
    own_read = query.split("Reads this query's own rows", 1)[1]
    selected = re.search(r"Table\.SelectColumns\(\n\s+(\S+),\n\s+\{([^}]*)\}", own_read)
    assert selected is not None, own_read
    assert selected.group(1).startswith("With"), selected.group(1)
    assert '"Category"' in selected.group(2)
    assert '"Kind"' not in selected.group(2)
    assert '{"Category", "Kind"}' in query


def _self_read_mapping(entries: str) -> str:
    return (
        "entities:\n"
        "  Risk: {kind: List, base_template: 100, site_role: default}\n"
        "derived_columns:\n"
        "  Risk:\n"
        + entries
    )


_LATER_EXPR = (
    "    - kind: expr\n"
    "      name: Later\n"
    "      type: text\n"
    "      m: '[Title]'\n"
)
_SELF_MAX_OF_LATER = (
    "    - kind: count\n"
    "      from: Risk\n"
    "      via: ParentRisk\n"
    "      name: ChildLater\n"
    "      aggregate: max\n"
    "      type: text\n"
    "      column: Later\n"
)
_SELF_COUNT_WHERE_LATER = (
    "    - kind: count\n"
    "      from: Risk\n"
    "      via: ParentRisk\n"
    "      name: ChildrenWithLater\n"
    "      aggregate: count\n"
    "      type: Int64\n"
    "      where: '[Later] <> null'\n"
)
_SELF_PICK_OF_LATER = (
    "    - kind: lookup\n"
    "      from: Risk\n"
    "      via: ParentRisk\n"
    "      pick:\n"
    "        ParentLater: Later\n"
    "      types:\n"
    "        ParentLater: text\n"
)


def _errors(schema: Schema, bundle: MappingBundle) -> set[FindingCode]:
    return {
        f.code for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    }


@pytest.mark.parametrize(
    "self_read", [_SELF_MAX_OF_LATER, _SELF_COUNT_WHERE_LATER, _SELF_PICK_OF_LATER],
    ids=["aggregate-column", "count-where", "lookup-pick"],
)
def test_a_self_read_of_an_output_declared_below_is_refused(
    tmp_path: Path, self_read: str,
) -> None:
    """The step reads the step above it, where `Later` does not exist yet.
    The finished query would have it, which is what made this pass before
    and fail at refresh."""
    below = pack(tmp_path, _SELF_REF_DBML, _self_read_mapping(self_read + _LATER_EXPR))
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE in _errors(*below)
    above = pack(
        tmp_path, _SELF_REF_DBML, _self_read_mapping(_LATER_EXPR + self_read),
        dbml_name="above.dbml", mapping_name="above.yaml",
    )
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE not in _errors(*above)
    query = generate_powerquery(*above, "default")["APP_Risk.pq"]
    assert "[Later]" in query or '"Later"' in query


_OTHER_LIST_DBML = """
Table Risk {
  Id int [pk, increment]
  Title nvarchar [not null]
}

Table Action {
  Id int [pk, increment]
  Title nvarchar [not null]
  RelatedRisk int [ref: > Risk.Id]
}
"""

_OTHER_LIST_MAPPING = """
entities:
  Risk: {kind: List, base_template: 100, site_role: default}
  Action: {kind: List, base_template: 100, site_role: default}
derived_columns:
  Risk:
    - kind: count
      from: Action
      via: RelatedRisk
      name: FlaggedActions
      aggregate: count
      type: Int64
      where: '[Flag] = true'
  Action:
    - kind: expr
      name: Flag
      type: logical
      m: 'true'
"""


def test_another_querys_derived_output_stays_readable(tmp_path: Path) -> None:
    """Only a self-read is held to declaration order. Another list is read
    as a finished query, so its own derived columns are there whatever the
    order the two entities are declared in."""
    schema, bundle = pack(tmp_path, _OTHER_LIST_DBML, _OTHER_LIST_MAPPING)
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE not in _errors(schema, bundle)
    risk = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert '#"APP_Action"' in risk
    assert "[Flag] = true" in risk
