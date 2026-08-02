# src/dbml_sharepoint/analysis/checks/_retirement.py
"""Retired columns, and the declarations the load-time fold rewrote."""

import datetime as dt

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.conditions import (
    VALIDATION,
    effective_column_types,
    leaves,
    to_validation,
    validate_condition,
)
from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.analysis.forms import validate_form_visibility
from dbml_sharepoint.analysis.validator import (
    _UNDEPLOYABLE_DECLARATION_COLUMNS,
    Finding,
    _rendered_columns,
    _undeployable,
    formula_column_refs,
)


def check(vc: ValidationContext) -> list[Finding]:
    bundle = vc.bundle
    tables_by_name = vc.tables_by_name
    cross_site_by_entity = vc.cross_site_by_entity
    findings: list[Finding] = []
    # Retired columns. The declaration is folded into form_visibility, the
    # display titles, the view field lists and the form body sections at
    # LOAD time, so these checks run against the authoritative record
    # retained on the mapping. Fail closed where a mistake would break the
    # list; warn where it would only waste something.
    #
    # The one check NOT here is "required with no default": the fold makes
    # that a form_visibility declaration, and the rule already lives beside
    # the mechanism in analysis/forms.py. The loop below re-labels it so it
    # names retirement rather than a section the author never wrote.
    for entity_name, retired_cols in bundle.mapping.retired_columns.items():
        retired_table = tables_by_name.get(entity_name)
        if retired_table is None or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                FindingCode.UNCLASSIFIED,
                "error", f"retired_columns[{entity_name}]: unknown entity.",
            ))
            continue
        ctx = f"retired_columns[{entity_name}]"
        xcols = cross_site_by_entity.get(entity_name, set())
        rendered = _rendered_columns(retired_table, xcols)
        cols_by_name = {c.name: c for c in retired_table.columns}
        for col_name, retired_spec in retired_cols.items():
            if col_name not in rendered:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"{ctx}: {col_name!r} is not a rendered column of "
                    f"{entity_name}. Retire the column the DBML declares — "
                    f"never delete the declaration, or the column stays live "
                    f"on the site and drifts the _UserAddedColumns audit on "
                    f"every refresh, forever.",
                ))
                continue
            if retired_spec.retired:
                try:
                    dt.date.fromisoformat(retired_spec.retired)
                except ValueError:
                    findings.append(Finding(
                        FindingCode.UNCLASSIFIED,
                        "error",
                        f"{ctx}.{col_name}: retired {retired_spec.retired!r} is not "
                        f"an ISO date (YYYY-MM-DD).",
                    ))
            col = cols_by_name.get(col_name)
            if col is not None and col.required and col.default is not None:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "warning",
                    f"{ctx}: {col_name!r} is required with a declared "
                    f"default — saves succeed, but every new row is stamped "
                    f"with {col.default!r} forever.",
                ))
            superseded = retired_spec.superseded_by
            if superseded is None:
                continue
            if superseded == col_name:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"{ctx}.{col_name}: superseded_by names the retired "
                    f"column itself.",
                ))
            elif superseded not in rendered:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"{ctx}.{col_name}: superseded_by {superseded!r} is not "
                    f"a rendered column of {entity_name}.",
                ))
            elif superseded in retired_cols:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"{ctx}.{col_name}: superseded_by {superseded!r} is "
                    f"itself retired.",
                ))
        for indexed_col in (
            index.columns[0]
            for index in retired_table.indexes
            if len(index.columns) == 1
        ):
            if indexed_col in retired_cols:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "warning",
                    f"{ctx}: {indexed_col!r} is still in the DBML indexes block — a "
                    f"list's index budget is finite and this one is now dead "
                    f"weight.",
                ))
        # _parse_view rejects an empty fields list, so a view can only reach
        # zero fields by having every one of them retired.
        for retired_view in bundle.mapping.views.get(entity_name, []):
            if not retired_view.fields:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "warning",
                    f"views[{entity_name}].{retired_view.title}: retirement "
                    f"stripped every declared field; the view would be "
                    f"created with no columns.",
                ))
        # A LIVE formula referencing a retired column still runs against a
        # column that has left the forms and every view. A calculated column
        # that is itself retired is dead and is not reported.
        for calc_col, formula in bundle.mapping.calculated_formulas.get(
            entity_name, {},
        ).items():
            if calc_col in retired_cols:
                continue
            for ref in sorted(formula_column_refs(formula) & set(retired_cols)):
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"calculated_formulas[{entity_name}].{calc_col}: formula "
                    f"references [{ref}], which is retired.",
                ))
        retirement_rule = bundle.mapping.list_validation.get(entity_name)
        if retirement_rule is not None:
            retired_refs = {leaf.field for leaf in leaves(retirement_rule.when)} & set(retired_cols)
            for ref in sorted(retired_refs):
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"list_validation[{entity_name}]: condition references "
                    f"{ref}, which is retired.",
                ))

        # A save rule ON a retired column, rather than one referencing it.
        # Retirement hides the column from the NEW form, so a rule the blank
        # value fails — is_not_null being the obvious one — rejects every new
        # item with no field on the form to satisfy it. The list stops
        # accepting rows, and nothing in the build says why.
        #
        # An error rather than a silent clear: dropping someone's declared
        # save rule to make a deploy succeed is the kind of quiet repair this
        # project keeps removing. Retire the column or drop the rule, but
        # the author decides which.
        validation_section = bundle.mapping.column_validation.get(entity_name)
        if validation_section is not None:
            for ruled in sorted(set(validation_section.columns) & set(retired_cols)):
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"column_validation[{entity_name}].{ruled}: {ruled!r} is retired, "
                    f"so it is hidden on the new form — a save rule on it cannot "
                    f"be satisfied there and would reject every new item. "
                    f"Remove the rule, or the retirement.",
                ))

    # Declarations the load-time fold rewrote. The structures no longer
    # carry the reference, so the record on the mapping is the only source.
    findings.extend(
        Finding(
            FindingCode.UNCLASSIFIED,
            "warning",
            f"retired_columns[{strip.entity}]: {strip.column!r} is still "
            f"named in {strip.context}; retirement stripped it and the build "
            f"continues.",
        )
        for strip in bundle.mapping.retirement_strips
    )
    if bundle.mapping.retired_columns and bundle.mapping.display_name_mode is None:
        findings.append(Finding(
            FindingCode.UNCLASSIFIED,
            "warning",
            "retired_columns are declared but display_names is not enabled, "
            "so the ' (retired)' display-title suffix never reaches "
            "SharePoint. Add `display_names: {mode: auto}` to surface "
            "retirement on the list itself.",
        ))

    # form_visibility / column_validation. Without this the declarations
    # reach the generator unchecked and surface as a traceback carrying an
    # internal context string instead of a Finding naming the mapping key.
    for fv_entity, fv_section in bundle.mapping.form_visibility.items():
        section_table = tables_by_name.get(fv_entity)
        if section_table is None or fv_entity not in bundle.mapping.entities:
            findings.append(Finding(
                FindingCode.UNCLASSIFIED,
                "error", f"form_visibility[{fv_entity}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(fv_entity, set())
        rendered = _rendered_columns(section_table, xcols) | {"Title"}
        types = effective_column_types(
            {c.name: c.type for c in section_table.columns}, xcols,
        )
        lookups = {c.name for c in section_table.columns if c.ref is not None}
        calculated = set(bundle.mapping.calculated_formulas.get(fv_entity, {}))
        by_name = {c.name: c for c in section_table.columns}
        ctx = f"form_visibility[{fv_entity}]"
        # _apply_retirement synthesises an entry here for every retired
        # column, so a problem with one is a problem with the retirement
        # declaration the author actually wrote. Re-labelling rather than
        # restating keeps one copy of each rule.
        retired_here = bundle.mapping.retired_columns.get(fv_entity, {})
        fv_at = Location(Section.FORM_VISIBILITY, entity=fv_entity)
        retired_at = Location(Section.RETIRED_COLUMNS, entity=fv_entity)
        for column, fv_declared in fv_section.columns.items():
            retired = column in retired_here
            col_ctx = f"retired_columns[{fv_entity}]" if retired else ctx
            col_at = retired_at if retired else fv_at
            if column in _UNDEPLOYABLE_DECLARATION_COLUMNS:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    _undeployable(col_ctx, column),
                ))
                continue
            if column not in rendered:
                # A retired column that names nothing is already reported
                # by the retirement block, with the consequence of deleting
                # the DBML declaration spelled out.
                if not retired:
                    findings.append(Finding(
                        FindingCode.UNCLASSIFIED,
                        "error",
                        f"{ctx}: {column!r} is not a rendered column of {fv_entity}.",
                    ))
                continue
            col = by_name.get(column)
            # Five distinct rules with a per-rule severity, so
            # validate_form_visibility names its own codes and hands back
            # Findings. Wrapping (severity, message) pairs here would have
            # given all five one code.
            findings.extend(validate_form_visibility(
                column=column,
                new=fv_declared.new,
                existing=fv_declared.existing,
                when=fv_declared.when,
                required=bool(col is not None and col.required),
                has_default=bool(col is not None and col.default is not None),
                is_calculated=column in calculated,
                rendered=rendered,
                types=types,
                lookups=lookups,
                at=col_at,
            ))

    for cv_entity, cv_section in bundle.mapping.column_validation.items():
        section_table = tables_by_name.get(cv_entity)
        if section_table is None or cv_entity not in bundle.mapping.entities:
            findings.append(Finding(
                FindingCode.UNCLASSIFIED,
                "error", f"column_validation[{cv_entity}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(cv_entity, set())
        rendered = _rendered_columns(section_table, xcols) | {"Title"}
        types = effective_column_types(
            {c.name: c.type for c in section_table.columns}, xcols,
        )
        lookups = {c.name for c in section_table.columns if c.ref is not None}
        ctx = f"column_validation[{cv_entity}]"
        for column, cv_rule in cv_section.columns.items():
            if column in _UNDEPLOYABLE_DECLARATION_COLUMNS:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    _undeployable(ctx, column),
                ))
                continue
            if column not in rendered:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error", f"{ctx}: {column!r} is not a rendered column of {cv_entity}.",
                ))
                continue
            if len(cv_rule.message) > 1024:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error", f"{ctx}.{column}: message must be ≤1024 characters.",
                ))
            # SharePoint permits a column validation formula to reference
            # ONLY the column being validated; a cross-column rule belongs
            # in list_validation, and the error says so.
            others = sorted({leaf.field for leaf in leaves(cv_rule.when)} - {column})
            if others:
                findings.append(Finding(
                    FindingCode.UNCLASSIFIED,
                    "error",
                    f"{ctx}.{column}: references {others} — column validation may only "
                    f"reference its own column; use list_validation for a cross-column rule.",
                ))
            problems = validate_condition(
                cv_rule.when,
                target=VALIDATION,
                rendered=rendered,
                types=types,
                lookups=lookups,
                context=f"{ctx}.{column}.when",
            )
            findings.extend(
                Finding(FindingCode.UNCLASSIFIED, "error", message)
                for message in problems
            )
            if not problems:
                formula = f"={to_validation(cv_rule.when, types)}"
                for internal in types:
                    display = bundle.mapping.display_name_for(cv_entity, internal)
                    formula = formula.replace(f"[{internal}]", f"[{display}]")
                if len(formula) > 1024:
                    findings.append(Finding(
                        FindingCode.UNCLASSIFIED,
                        "error",
                        f"{ctx}.{column}: rendered formula is {len(formula)} characters; "
                        "SharePoint's limit is 1024.",
                    ))

    return findings
