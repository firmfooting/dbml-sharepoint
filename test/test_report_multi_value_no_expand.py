# test/test_report_multi_value_no_expand.py
"""A multi-value Person or Lookup column is never expanded or projected.

SharePoint fails the WHOLE items request when a projected field is null for any
member of a multi-value column, so the report reads such a column as ids only
(sp.rest.person-projection.multi-null-member, sp.rest.lookup-projection.multi-null-member).
"""

from pathlib import Path

import pytest
from _paths import FIXTURES, engine_blueprints

from dbml_sharepoint.analysis.reporting.plan import build_plans
from dbml_sharepoint.analysis.typemap import map_column
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

_PAIRS = [
    (FIXTURES / "personmulti.dbml", FIXTURES / "personmulti-mapping.yaml"),
    (FIXTURES / "multilookup.dbml", FIXTURES / "multilookup-mapping.yaml"),
    *[
        (root / "10-design" / "schema.dbml", root / "20-configure" / "mapping.yaml")
        for _, root in sorted(engine_blueprints().items())
    ],
]


@pytest.mark.parametrize(("dbml", "mapping"), _PAIRS, ids=lambda p: p.parent.name)
def test_no_multi_value_column_gets_an_expand_or_a_projected_select(
    dbml: Path, mapping: Path,
) -> None:
    schema, bundle = parse_dbml(dbml), load_mapping(mapping)
    enums = {e.name for e in schema.enums}
    multi = {
        (t.name, c.name)
        for t in schema.tables
        for c in t.columns
        if map_column(c, enums).kind in {"UserMulti", "LookupMulti"}
    }
    for role in sorted({e.site_role for e in bundle.mapping.entities.values()}):
        for plan in build_plans(schema, bundle, role, time_zone="Australia/Melbourne"):
            for table, column in (m for m in multi if m[0] == plan.entity):
                assert column not in plan.expands, (table, column)
                assert not any(s.startswith(column + "/") for s in plan.selects), (table, column)
                assert column not in {r[0] for r in plan.record_expands}, (table, column)


def test_the_guard_sees_a_multi_value_column() -> None:
    """The sweep above passes vacuously if no fixture holds one."""
    seen = 0
    for dbml, _ in _PAIRS[:2]:
        schema = parse_dbml(dbml)
        enums = {e.name for e in schema.enums}
        seen += sum(
            map_column(c, enums).kind in {"UserMulti", "LookupMulti"}
            for t in schema.tables for c in t.columns
        )
    assert seen >= 2
