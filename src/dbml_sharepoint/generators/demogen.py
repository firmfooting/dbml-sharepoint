# src/dbml_sharepoint/generators/demogen.py
"""Render demo-data.js — declared demo/sample rows, emitted with --seed.

The plan is generation-time typed: each field carries a `kind` so the
script knows whether to write a literal, resolve the deploying operator
(person columns take `<Name>Id`), resolve a demo_ref to a created item's
Id (lookups also take `<Name>Id`), or compute a run-time date from a
`today±N` offset — cadence-derived demo surfaces (Review due, overdue
formatting, Tolerance due) must land on whatever day the demo runs.
The '[DEMO] ' Title marker (validated mandatory) is the in-record notice
and the teardown contract.
"""

import re
from typing import Any

from dbml_sharepoint.analysis.ordering import site_tables_in_order
from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release
from dbml_sharepoint.templating import script_env

# Offset optional, matching analysis.validator._TODAY_SENTINEL. The two
# must agree: the validator gates what may be declared, this decides what
# is generated, and a value the validator accepts but this rejects would
# pass the build with zero findings and emit the literal string "today".
_TODAY_OFFSET = re.compile(r"^today([+-]\d+)?$")

# The Title marker is the in-record demo notice: visible in every view and
# form header, and the marker rollback.js trusts. (Per-row list-item
# comments were tried and withdrawn: the modern Comments() endpoint is
# undocumented surface and rejected the write live — 2026-07-24 — while
# adding nothing the marker doesn't already show.)
DEMO_TITLE_PREFIX = "[DEMO] "

_DATE_TYPES = {"date", "datetime"}


def _field_plan(col_type: str | None, name: str, value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return {"name": name, "kind": "ref", "value": str(value["demo_ref"])}
    if col_type == "person":
        return {"name": name, "kind": "me", "value": None}
    if col_type in _DATE_TYPES and isinstance(value, str):
        m = _TODAY_OFFSET.match(value)
        if m:
            return {"name": name, "kind": "date_offset", "value": int(m.group(1) or 0)}
    return {"name": name, "kind": "literal", "value": value}


def generate_demo_js(
    *,
    schema: Schema,
    bundle: MappingBundle,
    release: Release,
    site_url: str,
    site_role: str,
    source_dbml: str,
    generated_at: str,
) -> str:
    env = script_env()
    tables_by_name = {t.name: t for t in schema.tables}
    demo_plan: list[dict[str, Any]] = []
    for table_name in site_tables_in_order(schema, bundle.mapping.entities, site_role):
        table = tables_by_name[table_name]
        types_by_col = {c.name: c.type for c in table.columns}
        for item in bundle.mapping.demo_items.get(table_name, []):
            demo_plan.append({
                "list": bundle.mapping.prefix + table_name,
                "key": item.key,
                "fields": [
                    _field_plan(types_by_col.get(name), name, value)
                    for name, value in item.values.items()
                ],
            })

    template = env.get_template("demo.js.j2")
    return template.render(
        site_url=site_url,
        site_role=site_role,
        release=release,
        source_dbml=source_dbml,
        generated_at=generated_at,
        demo_plan=demo_plan,
        demo_title_prefix=DEMO_TITLE_PREFIX,
    )
