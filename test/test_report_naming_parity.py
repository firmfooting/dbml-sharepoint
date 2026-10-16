# test/test_report_naming_parity.py
"""The reporting naming API is unchanged by how the queries read the site.

`build_plans` and `report_column_names` decide every column a report carries;
the renderer in `report_m` only writes them down. This pins the plans and the
column names over the fixtures and shipped blueprints, so a change to how the
M reads SharePoint cannot move a column.
"""

import hashlib

from _paths import FIXTURES, engine_blueprints

from dbml_sharepoint.analysis.reporting.plan import build_plans, report_column_names
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

PINNED = "39b62f76cbdde06158b9f5aad70a8b43f4db2ba97c0527c4687b4ae7d45c863e"


def _digest() -> str:
    pairs = [
        ("simple", FIXTURES / "simple.dbml", FIXTURES / "sharepoint-mapping.yaml"),
        ("calculated", FIXTURES / "calculated.dbml", FIXTURES / "calculated-mapping.yaml"),
        ("multilookup", FIXTURES / "multilookup.dbml", FIXTURES / "multilookup-mapping.yaml"),
        ("personmulti", FIXTURES / "personmulti.dbml", FIXTURES / "personmulti-mapping.yaml"),
    ]
    for family, root in sorted(engine_blueprints().items()):
        pairs.append((
            family, root / "10-design" / "schema.dbml",
            root / "20-configure" / "mapping.yaml",
        ))
    rows: list[tuple[object, ...]] = []
    for label, dbml, mapping in pairs:
        schema, bundle = parse_dbml(dbml), load_mapping(mapping)
        for role in sorted({e.site_role for e in bundle.mapping.entities.values()}):
            rows.extend(
                (
                    label, role, repr(plan), report_column_names(plan),
                    report_column_names(plan, include_derived=False),
                )
                for plan in build_plans(schema, bundle, role, time_zone="Australia/Melbourne")
            )
    return hashlib.sha256(repr(rows).encode()).hexdigest()


def test_the_naming_api_output_is_unchanged() -> None:
    assert _digest() == PINNED
