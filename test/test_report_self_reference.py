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

from dbml_sharepoint.generators.report_m import generate_powerquery
from dbml_sharepoint.generators.report_md import generate_reporting_md
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

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
