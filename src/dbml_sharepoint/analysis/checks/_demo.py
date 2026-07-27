# src/dbml_sharepoint/analysis/checks/_demo.py
"""Demo rows seeded by ``--seed``."""

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.validator import (
    _DATE_TYPES,
    _DEMO_ISO_DATE,
    _TODAY_SENTINEL,
    Finding,
    _rendered_columns,
)


def check(vc: ValidationContext) -> list[Finding]:
    bundle = vc.bundle
    tables_by_name = vc.tables_by_name
    enum_by_name = vc.enum_by_name
    cross_site_by_entity = vc.cross_site_by_entity
    findings: list[Finding] = []
    # Demo rows (--seed): everything checkable at build time IS checked —
    # a demo paste failing live in front of an audience is exactly the
    # failure class this tool exists to prevent.
    demo_keys: dict[str, str] = {}
    for entity_name, demo_rows in bundle.mapping.demo_items.items():
        if entity_name not in tables_by_name or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"demo_items[{entity_name}]: unknown entity.",
            ))
            continue
        for row in demo_rows:
            if row.key in demo_keys:
                findings.append(Finding(
                    "error",
                    f"demo_items[{entity_name}].{row.key}: duplicate demo "
                    f"key (also declared under {demo_keys[row.key]}).",
                ))
            else:
                demo_keys[row.key] = entity_name
    for entity_name, demo_rows in bundle.mapping.demo_items.items():
        demo_table = tables_by_name.get(entity_name)
        if demo_table is None or entity_name not in bundle.mapping.entities:
            continue
        xcols = cross_site_by_entity.get(entity_name, set())
        demo_writable = _rendered_columns(demo_table, xcols) | {"Title"}
        demo_types = {c.name: c.type for c in demo_table.columns}
        for row in demo_rows:
            ctx = f"demo_items[{entity_name}].{row.key}"
            demo_title = row.values.get("Title")
            if not isinstance(demo_title, str) or not demo_title.startswith("[DEMO] "):
                findings.append(Finding(
                    "error",
                    f"{ctx}: Title must start with '[DEMO] ' — the marker "
                    f"the teardown trusts to tell demo rows from real "
                    f"records.",
                ))
            for col_name, value in row.values.items():
                col_type = demo_types.get(col_name)
                if col_name not in demo_writable or col_name == "Id":
                    findings.append(Finding(
                        "error",
                        f"{ctx}: values references {col_name!r}, which is "
                        f"not a writable column of {entity_name}.",
                    ))
                    continue
                if isinstance(col_type, str) and col_type.startswith("calculated"):
                    findings.append(Finding(
                        "error",
                        f"{ctx}: {col_name} is a calculated column; demo "
                        f"rows cannot write it (set its inputs instead).",
                    ))
                    continue
                if isinstance(value, dict):
                    if set(value) != {"demo_ref"}:
                        findings.append(Finding(
                            "error",
                            f"{ctx}: {col_name} object value must be exactly "
                            f"{{demo_ref: <key>}}.",
                        ))
                    elif value["demo_ref"] not in demo_keys:
                        findings.append(Finding(
                            "error",
                            f"{ctx}: {col_name} demo_ref "
                            f"{value['demo_ref']!r} is not a declared demo "
                            f"key.",
                        ))
                    continue
                if col_type == "person":
                    if value != "@me":
                        findings.append(Finding(
                            "error",
                            f"{ctx}: person column {col_name} accepts only "
                            f"\"@me\" (the deploying operator).",
                        ))
                    continue
                if col_type in _DATE_TYPES:
                    if not (isinstance(value, str)
                            and (_TODAY_SENTINEL.match(value) or _DEMO_ISO_DATE.match(value))):
                        findings.append(Finding(
                            "error",
                            f"{ctx}: date column {col_name} accepts "
                            f"'today+N'/'today-N' or an ISO date "
                            f"(got {value!r}).",
                        ))
                    continue
                demo_enum = enum_by_name.get(col_type or "")
                if demo_enum is not None and value not in demo_enum.members:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: {col_name} value {value!r} is not a member "
                        f"of enum {col_type}.",
                    ))

    return findings
