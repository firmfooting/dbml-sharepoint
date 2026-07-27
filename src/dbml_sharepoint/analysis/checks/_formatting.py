# src/dbml_sharepoint/analysis/checks/_formatting.py
"""Column formatting, style specs, and form formatting."""

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.conditions import VALIDATION, validate_condition
from dbml_sharepoint.analysis.validator import (
    _UNDEPLOYABLE_DECLARATION_COLUMNS,
    SYSTEM_COLUMNS,
    Finding,
    _rendered_columns,
    _undeployable,
    formatter_field_refs,
)


def check(vc: ValidationContext) -> list[Finding]:
    schema = vc.schema
    bundle = vc.bundle
    tables_by_name = vc.tables_by_name
    cross_site_by_entity = vc.cross_site_by_entity
    findings: list[Finding] = []
    # Column formatting: declared targets must be rendered columns, the
    # formatter must be an SP formatter object (elmType root), and every
    # [$Field] reference must name a rendered column — deploy-time render
    # failures are silent (the column just shows raw), so catch at build.
    for entity_name, fmt_cols in bundle.mapping.column_formatting.items():
        fmt_table = tables_by_name.get(entity_name)
        if fmt_table is None or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"column_formatting[{entity_name}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(entity_name, set())
        rendered = _rendered_columns(fmt_table, xcols) | {"Title"} | SYSTEM_COLUMNS
        for col_name, formatter in fmt_cols.items():
            ctx = f"column_formatting[{entity_name}].{col_name}"
            if col_name in _UNDEPLOYABLE_DECLARATION_COLUMNS:
                findings.append(Finding("error", _undeployable(ctx, col_name)))
                continue
            if col_name not in rendered:
                findings.append(Finding(
                    "error",
                    f"{ctx}: not a rendered column of {entity_name}.",
                ))
            if "elmType" not in formatter:
                findings.append(Finding(
                    "error",
                    f"{ctx}: formatter JSON must be an SP column-formatting "
                    f"object with a root 'elmType'.",
                ))
            for ref in sorted(formatter_field_refs(formatter) - rendered):
                findings.append(Finding(
                    "error",
                    f"{ctx}: formatter references [${ref}], which is not a "
                    f"rendered column of {entity_name}.",
                ))

    # Style specs: a severity/pill map naming a choice the enum does not
    # contain is a declaration bug (same ethos as [$Field] checking);
    # trend/guard references must name rendered columns.
    style_enum_members = {e.name: set(e.members) for e in schema.enums}
    for entity_name, spec_cols in bundle.mapping.column_style_specs.items():
        spec_table = tables_by_name.get(entity_name)
        if spec_table is None:
            continue  # unknown entity already reported above
        xcols = cross_site_by_entity.get(entity_name, set())
        rendered = _rendered_columns(spec_table, xcols) | {"Title"} | SYSTEM_COLUMNS
        types_by_col = {col.name: col.type for col in spec_table.columns}
        for col_name, spec in spec_cols.items():
            ctx = f"column_formatting[{entity_name}].{col_name}"
            style = spec.get("style")
            if style in ("severity", "pill"):
                members = style_enum_members.get(types_by_col.get(col_name, ""))
                if members is not None:
                    for unknown in sorted(set(spec.get("map", {})) - members):
                        findings.append(Finding(
                            "error",
                            f"{ctx}: map key {unknown!r} is not a member of "
                            f"enum {types_by_col[col_name]!r}.",
                        ))
            if style == "data-bar":
                # color_by's [$field] existence is already covered by the
                # formatter_field_refs check on the expanded output; here we
                # mirror the severity rule for the TRANSLATION map when the
                # source column is enum-typed.
                color_by = spec.get("color_by")
                if isinstance(color_by, dict):
                    cfield = color_by.get("field")
                    if isinstance(cfield, str) and cfield:
                        members = style_enum_members.get(types_by_col.get(cfield, ""))
                        if members is not None:
                            for unknown in sorted(set(color_by.get("map", {})) - members):
                                findings.append(Finding(
                                    "error",
                                    f"{ctx}: color_by map key {unknown!r} is not "
                                    f"a member of enum {types_by_col[cfield]!r}.",
                                ))
            if style == "trend":
                against = spec.get("against")
                if isinstance(against, str) and against not in rendered:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: trend 'against' references {against!r}, "
                        f"which is not a rendered column of {entity_name}.",
                    ))
            if style == "overdue-date":
                guard = spec.get("guard") or {}
                gfield = guard.get("field") if isinstance(guard, dict) else None
                if gfield and gfield not in rendered:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: guard field {gfield!r} is not a rendered "
                        f"column of {entity_name}.",
                    ))

    # Form formatting: body sections and [$Field] references are validated
    # against rendered columns (authored internal names; jsgen rewrites body
    # sections to display titles at build).
    for entity_name, form in bundle.mapping.form_formatting.items():
        form_table = tables_by_name.get(entity_name)
        if form_table is None or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"form_formatting[{entity_name}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(entity_name, set())
        rendered = _rendered_columns(form_table, xcols) | {"Title"} | SYSTEM_COLUMNS
        for part_name, part_json in (
            ("header", form.header), ("body", form.body), ("footer", form.footer),
        ):
            if part_json is None:
                continue
            ctx = f"form_formatting[{entity_name}].{part_name}"
            for ref in sorted(formatter_field_refs(part_json) - rendered):
                findings.append(Finding(
                    "error",
                    f"{ctx}: references [${ref}], which is not a rendered "
                    f"column of {entity_name}.",
                ))
        if form.body is not None:
            sections = form.body.get("sections")
            if isinstance(sections, list):
                for section in sections:
                    if not isinstance(section, dict):
                        continue
                    for name in section.get("fields") or []:
                        if name not in rendered:
                            findings.append(Finding(
                                "error",
                                f"form_formatting[{entity_name}].body: "
                                f"sections field {name!r} is not a rendered "
                                f"column of {entity_name}.",
                            ))

    for entity_name, rule in bundle.mapping.list_validation.items():
        rule_table = tables_by_name.get(entity_name)
        if rule_table is None or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"list_validation[{entity_name}]: unknown entity.",
            ))
            continue
        ctx = f"list_validation[{entity_name}]"
        if len(rule.message) > 1024:
            findings.append(Finding("error", f"{ctx}: message must be ≤1024 characters."))
        xcols = cross_site_by_entity.get(entity_name, set())
        findings.extend(
            Finding("error", message)
            for message in validate_condition(
                rule.when,
                target=VALIDATION,
                rendered=_rendered_columns(rule_table, xcols) | {"Title"},
                types={c.name: c.type for c in rule_table.columns},
                lookups={c.name for c in rule_table.columns if c.ref is not None},
                context=f"{ctx}.when",
            )
        )


    return findings
