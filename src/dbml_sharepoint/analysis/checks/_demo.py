# src/dbml_sharepoint/analysis/checks/_demo.py
"""Demo rows seeded by ``--seed``."""

import datetime as dt

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
        # A document library's items ARE files. demo-data.js POSTs to
        # /items, and SharePoint refuses that on a library outright —
        # HTTP 500, "To add an item to a document library, use
        # SPFileCollection.Add()" (probed 2026-07-29,
        # test/manual/document-library-probe.js, L2).
        #
        # So the paste fails, loudly, in front of whoever was being shown
        # the demo. Refusing at build turns that into a failed build.
        # Seeding a library would mean uploading real files, which is a
        # different feature from writing list rows and is not one this tool
        # has.
        if bundle.mapping.entities[entity_name].kind == "DocumentLibrary":
            findings.append(Finding(
                "error",
                f"demo_items[{entity_name}]: {entity_name} is a DocumentLibrary, and a "
                f"library's items are files. Seeding posts to /items and would create "
                f"rows with no file behind them. Seed the register list that accompanies "
                f"the library, and upload sample documents by hand.",
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
        columns = {c.name: c for c in demo_table.columns}
        row_positions = {row.key: position for position, row in enumerate(demo_rows)}
        for position, row in enumerate(demo_rows):
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
                # Hyperlinks are checked FIRST, and in BOTH authored shapes:
                # a URL column takes a bare address or a {url, description}
                # record. Gating this on `isinstance(value, dict)` left the
                # scalar form unchecked — and the generator DOES refuse a
                # non-string there, so an invalid mapping surfaced as a build
                # traceback rather than a finding. A validator must refuse
                # everything its generator refuses, and refuse it first.
                if col_type == "hyperlink":
                    if isinstance(value, dict):
                        unknown = set(value) - {"url", "description"}
                        if unknown or "url" not in value:
                            findings.append(Finding(
                                "error",
                                f"{ctx}: {col_name} is a hyperlink; an object value "
                                f"must be {{url: <address>, description: <label>}} "
                                f"with 'description' optional. Got keys "
                                f"{sorted(value)}.",
                            ))
                            continue
                        address = value["url"]
                    else:
                        address = value
                    # Checked as a STRING, not stringified: str(None) is
                    # "None", which is non-empty, so a coerced emptiness test
                    # passes a null through to become a link pointing at the
                    # word None.
                    if not (isinstance(address, str) and address.strip()):
                        findings.append(Finding(
                            "error",
                            f"{ctx}: {col_name} is a hyperlink; its address must be "
                            f"a non-empty string, got {address!r}.",
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
                    else:
                        column = columns.get(col_name)
                        target_entity = demo_keys[value["demo_ref"]]
                        if column is None or column.ref is None:
                            findings.append(Finding(
                                "error",
                                f"{ctx}: {col_name} uses demo_ref but is not a lookup column.",
                            ))
                        elif column.ref.target_table != target_entity:
                            findings.append(Finding(
                                "error",
                                f"{ctx}: {col_name} targets {column.ref.target_table}, but "
                                f"demo_ref {value['demo_ref']!r} belongs to {target_entity}.",
                            ))
                        elif (
                            target_entity == entity_name
                            and row_positions.get(value["demo_ref"], position) >= position
                        ):
                            findings.append(Finding(
                                "error",
                                f"{ctx}: {col_name} demo_ref {value['demo_ref']!r} must be "
                                f"declared before the row that uses it.",
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
                    valid_date = False
                    if isinstance(value, str) and _TODAY_SENTINEL.match(value):
                        valid_date = True
                    elif isinstance(value, str) and _DEMO_ISO_DATE.match(value):
                        try:
                            dt.date.fromisoformat(value)
                            valid_date = True
                        except ValueError:
                            pass
                    if not valid_date:
                        findings.append(Finding(
                            "error",
                            f"{ctx}: date column {col_name} accepts "
                            f"'today+N'/'today-N' or a real ISO calendar date "
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
