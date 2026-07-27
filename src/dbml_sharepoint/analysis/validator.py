# src/dbml_sharepoint/analysis/validator.py
"""Validation rules for the parsed schema."""

import re
from dataclasses import dataclass
from typing import Literal

from dbml_sharepoint.analysis.conditions import (
    CAML,
    SYSTEM_COLUMN_TYPES,
    VALIDATION,
    leaves,
    validate_condition,
)
from dbml_sharepoint.analysis.forms import validate_form_visibility
from dbml_sharepoint.analysis.ordering import compute_phases
from dbml_sharepoint.analysis.permissions import BASE_PERMISSIONS, BUILT_IN_LEVELS
from dbml_sharepoint.extension import DeploymentExtension
from dbml_sharepoint.model.mapping_loader import ListPermissionPolicy, MappingBundle, view_url_slug
from dbml_sharepoint.model.parser import Column, Schema, Table

type Severity = Literal["error", "warning"]

# Hard-error reserved names. Note: 'Title' is special-cased (PATCH existing
# system column); 'Id' annotated pk+increment is special-cased (skip).
RESERVED_NAMES = frozenset({
    "Created", "Modified", "Editor", "_UIVersion", "Attachments", "Author",
    # SharePoint's own identity column. Legal only as the declared
    # `Id int [pk, increment]`, which is skipped at render time; anything
    # else named Id was emitted as a Text field against a name every list
    # already has.
    "Id", "ID",
})

# SharePoint system columns that exist on every list. Formatter [$Field]
# references and view/form field lists may name them; they are never
# DBML-declared. Deployer-managed sets (indexed_columns, hidden_on_forms,
# display_names) stay strict, as do list-validation formulas (SP support
# for system columns there is not relied on — fail closed).
SYSTEM_COLUMNS = frozenset({"ID", "Created", "Modified", "Author", "Editor"})

# Columns that never reach the per-field deploy loop, so a per-field
# declaration on one is validated, reported and never written.
#
# The built-in Title is provisioned through its own patch object — jsgen
# routes it there and continues BEFORE the formula and formatter keys are
# attached — and the system columns are not DBML columns, so they are
# never in the field list at all. A declaration on any of them validated
# clean, the manifest reported "(none declared)", and the deploy wrote
# nothing: an asserted, validated, silently unenforced guarantee, which is
# the worst shape a data-quality rule can take.
#
# Supporting Title properly means threading the formulas through the patch
# path, a larger change than these sections warrant. Fail closed instead,
# and say why.
_UNDEPLOYABLE_DECLARATION_COLUMNS = frozenset({"Title"}) | SYSTEM_COLUMNS


def _undeployable(context: str, column: str) -> str:
    """The message for a declaration on a column the deploy never writes."""
    reason = (
        "the built-in Title column is provisioned through its own patch"
        if column == "Title"
        else f"{column} is a SharePoint system column, not a deployed field"
    )
    return (
        f"{context}: {column!r} cannot carry a per-column declaration — "
        f"{reason}, so it never receives these properties. Declaring it here "
        f"would validate clean and deploy nothing."
    )

# DBML scalar types that we recognise. Anything else must be an enum.
KNOWN_SCALARS = frozenset({
    "int", "number", "nvarchar", "longtext", "richtext", "person", "date", "datetime",
    "boolean", "hyperlink",
})

# SP.FieldCalculated column types. The formula is NOT in DBML — it lives in
# the mapping's `calculated_formulas: {entity: {column: formula}}` section;
# validate_against_mapping enforces the pairing and SP's formula constraints.
CALCULATED_TYPES = frozenset({"calculated_text", "calculated_number", "calculated_date"})

_FORMULA_STRING_LITERAL = re.compile(r'"[^"]*"')
FORMULA_COLUMN_REF = re.compile(r"\[([^\[\]]+)\]")


# Formatter JSON `[$Field]` references (column/view/form formatting). SP
# resolves these against INTERNAL names at runtime.
_FORMATTER_FIELD_REF = re.compile(r"\[\$([A-Za-z0-9_]+)")


def formatter_field_refs(node: object) -> frozenset[str]:
    """Every `[$Field]` reference in a formatter JSON structure — walks
    nested dicts/lists and scans every string value."""
    refs: set[str] = set()

    def _walk(value: object) -> None:
        if isinstance(value, str):
            refs.update(_FORMATTER_FIELD_REF.findall(value))
        elif isinstance(value, dict):
            for child in value.values():
                _walk(child)
        elif isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(node)
    return frozenset(refs)


# Declared-view DSL operators. is_null/is_not_null take no value; the rest
# require one. Date/datetime values additionally accept the today sentinel.
# List validation: SP resolves ValidationFormula references at MERGE
# time and silently rejects unsupported column types — fail at build.
_VALIDATION_FORBIDDEN_TYPES = {
    "person": "a person column",
    "richtext": "a multi-line column",
    "longtext": "a multi-line column",
}

# Built-in SP groups a declared group's owner_group may reference.
_BUILTIN_SP_GROUPS = frozenset({
    "Site Owners", "Site Members", "Site Visitors",
    "Owners", "Members", "Visitors",
})

VIEW_OPERATORS = frozenset({
    "eq", "neq", "lt", "leq", "gt", "geq", "is_null", "is_not_null",
})
_VIEW_VALUELESS_OPERATORS = frozenset({"is_null", "is_not_null"})
_TODAY_SENTINEL = re.compile(r"^today([+-]\d+)?$")
_DEMO_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DATE_TYPES = frozenset({"date", "datetime", "calculated_date"})


def _rendered_columns(table: "Table", cross_site_cols: set[str]) -> set[str]:
    """Column names that will actually exist on the provisioned SP list:
    auto-increment Id is skipped at render time, cross-site logical columns
    expand to <col>Abbreviation / <col>SiteUrl and never exist themselves."""
    rendered: set[str] = set()
    for col in table.columns:
        if col.name == "Id" and col.is_pk and col.is_auto_increment:
            continue  # skipped at render time; SP indexes Id natively
        if col.name in cross_site_cols:
            rendered.add(col.name + "Abbreviation")
            rendered.add(col.name + "SiteUrl")
        else:
            rendered.add(col.name)
    return rendered


def formula_column_refs(formula: str) -> frozenset[str]:
    """Column names referenced as ``[Name]`` in a calculated formula.

    String literals are stripped first so bracket text inside a quoted
    constant is not misread as a reference. Shared with jsgen, which orders
    Phase-1 field creation by these references."""
    return frozenset(
        FORMULA_COLUMN_REF.findall(_FORMULA_STRING_LITERAL.sub("", formula)),
    )

# SharePoint's documented calculated-column formula length ceiling.
MAX_CALCULATED_FORMULA = 1024

MAX_INTERNAL_NAME = 32

# Built-in associated-group ALIASES (casefolded) mapped to the principal kind
# that resolves them correctly at deploy time. `kind: group` principals are
# resolved via sitegroups/getbyname(name), which fails for these aliases on
# real sites (the actual groups are named '<SiteTitle> Owners' etc.). Note the
# aliases remain valid for groups[*].owner_group, where the template resolves
# them through the AssociatedOwnerGroup/... endpoints.
_ASSOCIATED_GROUP_ALIASES = {
    "site owners": "associated_owner_group",
    "site members": "associated_member_group",
    "site visitors": "associated_visitor_group",
}


@dataclass(frozen=True)
class Finding:
    severity: Severity
    message: str


def validate(schema: Schema) -> list[Finding]:
    findings: list[Finding] = []
    table_names = {t.name for t in schema.tables}
    enum_members = {e.name: e.members for e in schema.enums}

    seen_tables: set[str] = set()
    for table in schema.tables:
        if table.name in seen_tables:
            findings.append(Finding("error", f"Duplicate table name: {table.name}"))
            continue
        seen_tables.add(table.name)

        seen_columns: set[str] = set()
        for col in table.columns:
            if col.name in seen_columns:
                findings.append(Finding("error", f"{table.name}: duplicate column {col.name}"))
                continue
            seen_columns.add(col.name)

            findings.extend(_check_column(table.name, col, table_names, enum_members))

    seen_enums: set[str] = set()
    referenced_enums = _collect_referenced_enums(schema)
    for enum in schema.enums:
        if enum.name in seen_enums:
            findings.append(Finding("error", f"Duplicate enum name: {enum.name}"))
        seen_enums.add(enum.name)
        if not enum.members:
            findings.append(Finding("warning", f"Enum {enum.name} has zero members."))
        if enum.name not in referenced_enums:
            findings.append(Finding(
                "warning", f"Enum {enum.name} is orphan (defined but unreferenced).",
            ))

    return findings


def _check_column(
    table: str, col: Column, tables: set[str], enums: dict[str, list[str]],
) -> list[Finding]:
    findings: list[Finding] = []
    name = col.name
    is_pk_id = name == "Id" and col.is_pk and col.is_auto_increment
    is_title = name == "Title"

    if name in RESERVED_NAMES and not is_pk_id:
        findings.append(Finding("error", f"{table}.{name}: reserved column name."))

    # The identity column must be called Id. typemap skips ANY
    # `int [pk, increment]` column, while jsgen and _rendered_columns
    # special-case the NAME — so a differently named one was validated as a
    # real column and never created. Every consequence then validated
    # clean: per-column declarations deployed nothing, indexed_columns and
    # views.fields emitted calls that fail live, and demo_items wrote to a
    # column that does not exist.
    #
    # Rejected rather than taught to the four consumers deliberately. A
    # SharePoint list has exactly one auto-increment column and it is
    # called ID; accepting another name would let the DBML claim a column
    # the site does not have, and every downstream reader — the data
    # dictionary, the Power Query bundle, any flow — would still have to
    # say ID. That is a rename with no deployed counterpart, which is the
    # same silent-drop class this rejection exists to close.
    if col.is_pk and col.is_auto_increment and not is_pk_id:
        findings.append(Finding(
            "error",
            f"{table}.{name}: an auto-increment primary key must be named "
            f"'Id' — it maps to SharePoint's built-in ID column, which is "
            f"created with the list and cannot be renamed. Declared under "
            f"any other name it is validated as an ordinary column and "
            f"never provisioned.",
        ))

    if any(c in name for c in " !@#$%^&*()+={}[]|\\:;\"'<>,?/~`"):
        findings.append(Finding("error", f"{table}.{name}: contains illegal character."))

    if len(name) > MAX_INTERNAL_NAME:
        findings.append(Finding(
            "error", f"{table}.{name}: name exceeds {MAX_INTERNAL_NAME} chars.",
        ))

    if col.type == "choice":
        findings.append(Finding(
            "error",
            f"{table}.{name}: legacy 'choice' type — migrate to a named DBML enum.",
        ))
    elif (
        col.type not in KNOWN_SCALARS
        and col.type not in CALCULATED_TYPES
        and col.type not in enums
        and not is_pk_id
    ):
        findings.append(Finding("error", f"{table}.{name}: unknown type {col.type!r}."))

    if col.type in enums and col.default is not None:
        members = enums[col.type]
        declared = str(col.default).strip("\"'")
        if declared not in members:
            findings.append(Finding(
                "error",
                f"{table}.{name}: default {col.default!r} is not a member of "
                f"enum {col.type!r} ({members}).",
            ))

    if col.ref is not None and col.ref.target_table not in tables:
        findings.append(Finding(
            "error",
            f"{table}.{name}: ref target {col.ref.target_table} not defined.",
        ))

    if col.unique and col.type in {"longtext", "richtext"}:
        findings.append(Finding(
            "warning",
            f"{table}.{name}: unique on {col.type} is silently dropped by SP.",
        ))

    if col.unique and not col.required and not is_title:
        findings.append(Finding(
            "warning",
            f"{table}.{name}: unique without not_null — "
            "uniqueness enforced only on populated values.",
        ))

    return findings


def _collect_referenced_enums(schema: Schema) -> set[str]:
    enum_names = {e.name for e in schema.enums}
    referenced: set[str] = set()
    for table in schema.tables:
        for col in table.columns:
            if col.type in enum_names:
                referenced.add(col.type)
    return referenced


def validate_against_mapping(schema: Schema, bundle: MappingBundle) -> list[Finding]:
    findings: list[Finding] = []
    table_names = {t.name for t in schema.tables}
    enum_by_name = {e.name: e for e in schema.enums}

    # Every entity in the mapping must exist in the schema.
    for entity_name in bundle.mapping.entities:
        if entity_name not in table_names:
            findings.append(Finding(
                "error",
                f"Mapping references unknown entity: {entity_name}",
            ))

    # ...and every schema table must have a mapping entry (opposite direction).
    # build_schema_json silently skips unmapped tables, so an unmapped schema
    # entity would otherwise be dropped from the deploy plan without any error.
    for table in schema.tables:
        if table.name not in bundle.mapping.entities:
            findings.append(Finding(
                "error",
                f"Schema table {table.name} has no mapping entry in "
                "sharepoint-mapping.yaml (would be omitted from the deploy plan).",
            ))

    # Every cross-site reference must point at an existing entity + column ref.
    for xref in bundle.mapping.cross_site_reference_columns:
        if xref.entity not in table_names:
            findings.append(Finding(
                "error",
                f"cross_site_reference_columns: entity {xref.entity} not in schema",
            ))
            continue
        table = next(t for t in schema.tables if t.name == xref.entity)
        col = next((c for c in table.columns if c.name == xref.column), None)
        if col is None:
            findings.append(Finding(
                "error",
                f"cross_site_reference_columns: {xref.entity}.{xref.column} not in schema",
            ))
        elif col.ref is None:
            findings.append(Finding(
                "error",
                f"cross_site_reference_columns: {xref.entity}.{xref.column} has no ref:",
            ))
        else:
            # Cross-site columns expand to <name>Abbreviation + <name>SiteUrl
            # at deploy time. The longer of the two ("Abbreviation", 12 chars)
            # plus the column name must fit within SP's 32-char internal-name
            # limit.
            for suffix in ("Abbreviation", "SiteUrl"):
                generated = xref.column + suffix
                if len(generated) > 32:
                    findings.append(Finding(
                        "error",
                        f"cross_site {xref.entity}.{xref.column}: generated "
                        f"name '{generated}' is {len(generated)} chars; "
                        f"SP internal-name limit is 32.",
                    ))

    # Every indexed_columns entry must name a column that will actually be
    # rendered in SP for that table. Phase 2.3 patches fields by name, so an
    # unknown name (or a cross-site LOGICAL name, which is expanded to
    # <col>Abbreviation / <col>SiteUrl and never exists itself) would only
    # fail late, in the browser.
    cross_site_by_entity: dict[str, set[str]] = {}
    for xref in bundle.mapping.cross_site_reference_columns:
        cross_site_by_entity.setdefault(xref.entity, set()).add(xref.column)
    tables_by_name = {t.name: t for t in schema.tables}
    for entity_name, indexed in bundle.mapping.indexed_columns.items():
        indexed_table = tables_by_name.get(entity_name)
        if indexed_table is None:
            findings.append(Finding(
                "error",
                f"indexed_columns references unknown entity: {entity_name}",
            ))
            continue
        xcols = cross_site_by_entity.get(entity_name, set())
        rendered = _rendered_columns(indexed_table, xcols)
        for col_name in indexed:
            if col_name not in rendered:
                hint = (
                    f" (cross-site column: use '{col_name}Abbreviation' or "
                    f"'{col_name}SiteUrl')"
                    if col_name in xcols
                    else ""
                )
                findings.append(Finding(
                    "error",
                    f"indexed_columns[{entity_name}]: {col_name!r} is not a "
                    f"rendered column of {entity_name}{hint}.",
                ))

    # watched_lists, polymorphic_patterns and versioning.overrides were the
    # three entity-keyed sections nothing validated at all. Every other
    # section names its unknown entities; these three silently dropped a
    # typo — the versioning one in the fail-open direction, leaving a list
    # with versioning ON when the author declared it off.
    for i, watched in enumerate(bundle.mapping.watched_lists):
        watched_table = tables_by_name.get(watched.entity)
        if watched_table is None:
            findings.append(Finding(
                "error",
                f"watched_lists[{i}]: unknown entity {watched.entity!r}.",
            ))
            continue
        watched_cols = _rendered_columns(
            watched_table, cross_site_by_entity.get(watched.entity, set()),
        )
        if watched.column not in watched_cols:
            findings.append(Finding(
                "error",
                f"watched_lists[{i}]: {watched.column!r} is not a rendered "
                f"column of {watched.entity}.",
            ))
    for i, pattern in enumerate(bundle.mapping.polymorphic_patterns):
        pattern_table = tables_by_name.get(pattern.list)
        if pattern_table is None:
            findings.append(Finding(
                "error",
                f"polymorphic_patterns[{i}]: unknown entity {pattern.list!r}.",
            ))
            continue
        pattern_cols = _rendered_columns(
            pattern_table, cross_site_by_entity.get(pattern.list, set()),
        )
        for role, col_name in (("field", pattern.field), ("discriminator", pattern.discriminator)):
            if col_name not in pattern_cols:
                findings.append(Finding(
                    "error",
                    f"polymorphic_patterns[{i}]: {role} {col_name!r} is not a "
                    f"rendered column of {pattern.list}.",
                ))
    for entity_name in bundle.mapping.versioning_overrides:
        if entity_name not in tables_by_name:
            findings.append(Finding(
                "error",
                f"versioning.overrides: unknown entity {entity_name!r} — the "
                f"override is read by nobody, so the real list keeps the "
                f"defaults.",
            ))

    # Lookups the deploy plan defers to Phase 2 — self-references and one
    # side of every cycle. They exist by the end of the run but not when
    # Phase 1 fields are created.
    deferred_by_entity: dict[str, set[str]] = {}
    for entity_name, col_name in compute_phases(schema).phase2_lookups:
        deferred_by_entity.setdefault(entity_name, set()).add(col_name)

    # Calculated columns (SP.FieldCalculated): every calculated_* column must
    # have a formula in the mapping, every mapping formula must target a
    # calculated_* column, formulas must satisfy SP's constraints, and
    # calculated columns cannot be indexed (SP does not support it).
    calc_columns_by_table: dict[str, set[str]] = {}
    for table in schema.tables:
        for col in table.columns:
            if col.type not in CALCULATED_TYPES:
                continue
            calc_columns_by_table.setdefault(table.name, set()).add(col.name)
            formula = bundle.mapping.calculated_formulas.get(
                table.name, {},
            ).get(col.name)
            if formula is None:
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: calculated column has no "
                    f"formula — add calculated_formulas.{table.name}."
                    f"{col.name} to the mapping.",
                ))
                continue
            if not formula.startswith("="):
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: calculated formula must start "
                    f"with '='.",
                ))
            if len(formula) > MAX_CALCULATED_FORMULA:
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: calculated formula is "
                    f"{len(formula)} chars; SharePoint's limit is "
                    f"{MAX_CALCULATED_FORMULA}.",
                ))
            # SharePoint resolves [Column] references when the field is
            # CREATED and rejects the POST (HTTP 500, "The formula refers to
            # a column that does not exist") on any miss — fail at build, not
            # at paste.
            #
            # Checked against the RENDERED columns, not the declared ones.
            # `Id int [pk, increment]` is skipped at render time and a
            # cross-site column is expanded into <col>Abbreviation and
            # <col>SiteUrl, so both are names the deploy never creates while
            # sitting in table.columns — and a formula naming either passed
            # this very check before dying at paste time.
            declared = _rendered_columns(
                table, cross_site_by_entity.get(table.name, set()),
            )
            refs = formula_column_refs(formula)
            if col.name in refs:
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: calculated formula references "
                    f"itself.",
                ))
            for ref in sorted(refs - declared):
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: calculated formula references "
                    f"[{ref}], which is not a rendered column of "
                    f"{table.name} — SharePoint would reject the field "
                    f"creation at deploy time.",
                ))
            # A DEFERRED lookup exists by the end of the deploy but not when
            # this field is created. jsgen orders calculated fields only
            # within fields_phase1 and never consults phase2_lookups, so the
            # formula is posted in Phase 1 against a column Phase 2 has not
            # added yet. Rejected rather than deferred: moving the calculated
            # field into Phase 2 would mean a second creation path for
            # calculated columns, and the declaration has a cheap rewrite —
            # compute from the column the lookup mirrors, or drop it.
            for ref in sorted(refs & deferred_by_entity.get(table.name, set())):
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: calculated formula references "
                    f"[{ref}], a lookup deferred to Phase 2 because its "
                    f"target is created later (a self-reference or a "
                    f"circular one). The calculated field is created in "
                    f"Phase 1, so the column does not exist yet.",
                ))
    for entity_name, cols in bundle.mapping.calculated_formulas.items():
        for col_name in cols:
            if col_name not in calc_columns_by_table.get(entity_name, set()):
                findings.append(Finding(
                    "error",
                    f"calculated_formulas[{entity_name}]: {col_name!r} is not "
                    f"a calculated_text/calculated_number column of "
                    f"{entity_name}.",
                ))
        # Calc-on-calc chains are provisioned in dependency order by jsgen;
        # a cycle has no valid creation order (each field's formula would
        # reference a not-yet-existing column).
        calc_names = calc_columns_by_table.get(entity_name, set())
        remaining = {
            name: (formula_column_refs(f) & calc_names) - {name}
            for name, f in cols.items()
            if name in calc_names
        }
        while remaining:
            ready = [n for n, deps in remaining.items() if not deps & remaining.keys()]
            if not ready:
                findings.append(Finding(
                    "error",
                    f"calculated_formulas[{entity_name}]: circular reference "
                    f"among {sorted(remaining)} — no creation order can "
                    f"satisfy mutually dependent calculated columns.",
                ))
                break
            for name in ready:
                del remaining[name]
    for entity_name, indexed in bundle.mapping.indexed_columns.items():
        for col_name in indexed:
            if col_name in calc_columns_by_table.get(entity_name, set()):
                findings.append(Finding(
                    "error",
                    f"indexed_columns[{entity_name}]: {col_name!r} is a "
                    f"calculated column — SharePoint cannot index calculated "
                    f"columns.",
                ))

    # Declared views: everything checkable at build time IS checked at build
    # time — a deploy-time CAML rejection in the browser console is exactly
    # the failure class this tool exists to prevent.
    for entity_name, views in bundle.mapping.views.items():
        view_table = tables_by_name.get(entity_name)
        if view_table is None or entity_name not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"views[{entity_name}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(entity_name, set())
        # The built-in Title always exists on a provisioned list, declared or not.
        view_rendered = _rendered_columns(view_table, xcols) | {"Title"} | SYSTEM_COLUMNS
        types_by_col = {c.name: c.type for c in view_table.columns}
        titles = [v.title for v in views]
        for title in sorted({t for t in titles if titles.count(t) > 1}):
            findings.append(Finding(
                "error", f"views[{entity_name}]: duplicate view title {title!r}.",
            ))
        defaults = [v.title for v in views if v.default]
        if len(defaults) > 1:
            findings.append(Finding(
                "error",
                f"views[{entity_name}]: more than one default view "
                f"({', '.join(defaults)}); SharePoint lists have exactly one.",
            ))
        # Views are created under a URL slug derived from the title (the
        # .aspx name is fixed at creation); two titles collapsing to one
        # slug would fight over the same page.
        slugs_seen: dict[str, str] = {}
        for view in views:
            slug = view_url_slug(view.title)
            if not slug:
                findings.append(Finding(
                    "error",
                    f"views[{entity_name}].{view.title}: title yields an "
                    f"empty URL slug; include at least one letter or digit.",
                ))
            elif slug in slugs_seen:
                findings.append(Finding(
                    "error",
                    f"views[{entity_name}]: titles {slugs_seen[slug]!r} and "
                    f"{view.title!r} share the URL slug {slug}.aspx; retitle "
                    f"one so the view pages differ.",
                ))
            else:
                slugs_seen[slug] = view.title
        for view in views:
            ctx = f"views[{entity_name}].{view.title}"
            referenced = (
                [("fields", name) for name in view.fields]
                + [("sort", sort.field) for sort in view.sort]
                + ([("group_by", view.group_by.field)] if view.group_by else [])
            )
            for part, name in referenced:
                if name not in view_rendered:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: {part} references {name!r}, which is not a "
                        f"rendered column of {entity_name}.",
                    ))
            if view.where is not None:
                # The shared grammar owns operator, operand and capability
                # rules for every conditional surface; duplicating them here
                # is how the two would drift.
                lookup_cols = {c.name for c in view_table.columns if c.ref is not None}
                findings.extend(
                    Finding("error", message)
                    for message in validate_condition(
                        view.where,
                        target=CAML,
                        rendered=view_rendered,
                        types={**SYSTEM_COLUMN_TYPES, **types_by_col},
                        lookups=lookup_cols,
                        context=f"{ctx}.where",
                    )
                )
            if view.row_limit is not None and not 1 <= view.row_limit <= 5000:
                findings.append(Finding(
                    "error", f"{ctx}: row_limit must be between 1 and 5000.",
                ))
            if view.formatting is not None:
                for ref in sorted(formatter_field_refs(view.formatting) - view_rendered):
                    findings.append(Finding(
                        "error",
                        f"{ctx}: formatting references [${ref}], which is "
                        f"not a rendered column of {entity_name}.",
                    ))
            # Widths bind to columns the view actually shows; a width on an
            # unshown column is dead config the deployer would emit and SP
            # would silently ignore.
            for width_col, width_px in view.widths.items():
                if width_col not in view.fields:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: widths references {width_col!r}, which is "
                        f"not one of this view's fields.",
                    ))
                if not 16 <= width_px <= 2000:
                    findings.append(Finding(
                        "error",
                        f"{ctx}: widths[{width_col}] must be between 16 and "
                        f"2000 pixels (got {width_px}).",
                    ))

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


    # form_visibility / column_validation. Without this the declarations
    # reach the generator unchecked and surface as a traceback carrying an
    # internal context string instead of a Finding naming the mapping key.
    for fv_entity, fv_section in bundle.mapping.form_visibility.items():
        section_table = tables_by_name.get(fv_entity)
        if section_table is None or fv_entity not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"form_visibility[{fv_entity}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(fv_entity, set())
        rendered = _rendered_columns(section_table, xcols) | {"Title"}
        types = {c.name: c.type for c in section_table.columns}
        lookups = {c.name for c in section_table.columns if c.ref is not None}
        calculated = set(bundle.mapping.calculated_formulas.get(fv_entity, {}))
        by_name = {c.name: c for c in section_table.columns}
        ctx = f"form_visibility[{fv_entity}]"
        for column, fv_declared in fv_section.columns.items():
            if column in _UNDEPLOYABLE_DECLARATION_COLUMNS:
                findings.append(Finding("error", _undeployable(ctx, column)))
                continue
            if column not in rendered:
                findings.append(Finding(
                    "error", f"{ctx}: {column!r} is not a rendered column of {fv_entity}.",
                ))
                continue
            col = by_name.get(column)
            findings.extend(
                Finding(severity, message)
                for severity, message in validate_form_visibility(
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
                    context=ctx,
                )
            )

    for cv_entity, cv_section in bundle.mapping.column_validation.items():
        section_table = tables_by_name.get(cv_entity)
        if section_table is None or cv_entity not in bundle.mapping.entities:
            findings.append(Finding(
                "error", f"column_validation[{cv_entity}]: unknown entity.",
            ))
            continue
        xcols = cross_site_by_entity.get(cv_entity, set())
        rendered = _rendered_columns(section_table, xcols) | {"Title"}
        types = {c.name: c.type for c in section_table.columns}
        lookups = {c.name for c in section_table.columns if c.ref is not None}
        ctx = f"column_validation[{cv_entity}]"
        for column, cv_rule in cv_section.columns.items():
            if column in _UNDEPLOYABLE_DECLARATION_COLUMNS:
                findings.append(Finding("error", _undeployable(ctx, column)))
                continue
            if column not in rendered:
                findings.append(Finding(
                    "error", f"{ctx}: {column!r} is not a rendered column of {cv_entity}.",
                ))
                continue
            if len(cv_rule.message) > 1024:
                findings.append(Finding(
                    "error", f"{ctx}.{column}: message must be ≤1024 characters.",
                ))
            # SharePoint permits a column validation formula to reference
            # ONLY the column being validated; a cross-column rule belongs
            # in list_validation, and the error says so.
            others = sorted({leaf.field for leaf in leaves(cv_rule.when)} - {column})
            if others:
                findings.append(Finding(
                    "error",
                    f"{ctx}.{column}: references {others} — column validation may only "
                    f"reference its own column; use list_validation for a cross-column rule.",
                ))
            findings.extend(
                Finding("error", message)
                for message in validate_condition(
                    cv_rule.when,
                    target=VALIDATION,
                    rendered=rendered,
                    types=types,
                    lookups=lookups,
                    context=f"{ctx}.{column}.when",
                )
            )

    # Display names: overrides must target rendered columns, and the resolved
    # display titles (auto + overrides) must be non-empty, within SharePoint's
    # 255-char Title bound, and unique per entity — a duplicate display title
    # makes two columns indistinguishable on every form and view.
    if bundle.mapping.display_name_mode is not None:
        for entity_name, cols in bundle.mapping.display_name_overrides.items():
            override_table = tables_by_name.get(entity_name)
            if override_table is None or entity_name not in bundle.mapping.entities:
                findings.append(Finding(
                    "error", f"display_names.overrides[{entity_name}]: unknown entity.",
                ))
                continue
            xcols = cross_site_by_entity.get(entity_name, set())
            rendered = _rendered_columns(override_table, xcols)
            for col_name, display_title in cols.items():
                if col_name not in rendered:
                    findings.append(Finding(
                        "error",
                        f"display_names.overrides[{entity_name}]: {col_name!r} "
                        f"is not a rendered column of {entity_name}.",
                    ))
                if not display_title:
                    findings.append(Finding(
                        "error",
                        f"display_names.overrides[{entity_name}]: {col_name!r} "
                        f"resolves to an empty display title.",
                    ))
                elif len(display_title) > 255:
                    findings.append(Finding(
                        "error",
                        f"display_names.overrides[{entity_name}]: {col_name!r} "
                        f"display title exceeds 255 characters.",
                    ))
        for table in schema.tables:
            if table.name not in bundle.mapping.entities:
                continue
            xcols = cross_site_by_entity.get(table.name, set())
            resolved: dict[str, list[str]] = {}
            for col_name in sorted(_rendered_columns(table, xcols)):
                resolved.setdefault(
                    bundle.mapping.display_name_for(table.name, col_name), [],
                ).append(col_name)
            for display_title, sources in resolved.items():
                if len(sources) > 1:
                    findings.append(Finding(
                        "error",
                        f"display_names[{table.name}]: duplicate display title "
                        f"{display_title!r} for columns {', '.join(sources)}.",
                    ))

    # Lookup display-column guard: a SharePoint lookup renders its target row's
    # LookupField. jsgen defaults LookupField to "Title"; if the target list has
    # no Title column AND the mapping declares no display_column for it, every
    # lookup into it renders BLANK (the empty built-in Title). Force the author
    # to declare display_column so person/roster references show a name (A1).
    # Cross-site reference columns are expanded to Choice+URL, not lookups, so
    # they are excluded.
    cross_site_pairs = {
        (x.entity, x.column) for x in bundle.mapping.cross_site_reference_columns
    }
    for table in schema.tables:
        for col in table.columns:
            if col.ref is None or (table.name, col.name) in cross_site_pairs:
                continue
            target_table = tables_by_name.get(col.ref.target_table)
            if target_table is None:
                continue  # missing-ref target already errored by validate()
            source_entity = bundle.mapping.entities.get(table.name)
            target_entity = bundle.mapping.entities.get(col.ref.target_table)
            # A7: a SharePoint lookup cannot span webs. If the source and target
            # map to different site_roles and the column is not declared
            # cross-site, deploy.js would emit a lookup whose target list is
            # never created in this site — failing only at deploy time
            # ('Lookup target ... not yet created'). Fail the build instead.
            if (
                source_entity is not None
                and target_entity is not None
                and source_entity.site_role != target_entity.site_role
            ):
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: lookup crosses site_role "
                    f"({source_entity.site_role} -> {target_entity.site_role}); "
                    f"SharePoint lookups cannot span webs. Declare "
                    f"({table.name}, {col.name}) in cross_site_reference_columns "
                    f"to expand it to a Choice+URL pair, or keep both entities in "
                    f"the same site_role.",
                ))
                continue
            # A1: lookup display-column guard. jsgen emits
            # LookupField = display_column or "Title".
            display = target_entity.display_column if target_entity else None
            if display:
                # A display_column IS declared: it must name a real column of the
                # target table (checked regardless of whether Title also exists,
                # since jsgen prefers display_column). A typo'd / removed value
                # would emit LookupField=<bad name> and fail at deploy time
                #.
                if not any(c.name == display for c in target_table.columns):
                    findings.append(Finding(
                        "error",
                        f"{table.name}.{col.name}: lookup target "
                        f"{col.ref.target_table} declares display_column "
                        f"{display!r}, which is not a column of "
                        f"{col.ref.target_table}; jsgen would emit "
                        f"LookupField={display!r} and the deploy would fail. Fix "
                        f"display_column in sharepoint-mapping.yaml.",
                    ))
            elif not any(c.name == "Title" for c in target_table.columns):
                # No display_column and no Title → the lookup renders blank.
                findings.append(Finding(
                    "error",
                    f"{table.name}.{col.name}: lookup target "
                    f"{col.ref.target_table} has no Title column and its mapping "
                    f"declares no display_column, so the lookup would render "
                    f"blank. Add display_column to the {col.ref.target_table} "
                    f"entity in sharepoint-mapping.yaml.",
                ))

    # Retention cross-checks only apply when retention config is actually
    # present. mapping_loader ties retention_policies and
    # retention_list_defaults together (both loaded from the same
    # retention-policies.yaml; both empty when retention_policies_source is
    # unset), but the checks below key off retention_policies specifically
    # so a bundle with list_defaults but no defined policies does not
    # spuriously error on every 'not in policies' comparison.
    if bundle.retention_policies:
        # Every retention list_default key must be a known entity.
        # Keys carry the APP_ prefix; DBML table names are unprefixed.
        prefix = bundle.mapping.prefix
        for entity_name in bundle.retention_list_defaults:
            bare = (
                entity_name.removeprefix(prefix)
                if prefix and entity_name.startswith(prefix)
                else entity_name
            )
            if bare not in table_names:
                findings.append(Finding(
                    "error",
                    f"retention list_defaults references unknown entity: {entity_name}",
                ))

        # Every list_defaults policy must be a known retention policy.
        for entity_name, policy in bundle.retention_list_defaults.items():
            if policy not in bundle.retention_policies:
                findings.append(Finding(
                    "error",
                    f"retention list_defaults[{entity_name}] = {policy} not in policies",
                ))

    # For every configured enum_sources entry, cross-check its choices
    # against the matching DBML enum. A configured enum name with no
    # matching DBML enum is only a warning — the schema simply hasn't
    # defined that enum yet, which isn't by itself wrong. A DBML enum whose
    # members differ from the configured choices IS an error: SP would
    # render different choices from what the loader feeds to other enum
    # consumers.
    for enum_name, choices in bundle.enum_choices.items():
        dbml_enum = enum_by_name.get(enum_name)
        if dbml_enum is None:
            findings.append(Finding(
                "warning",
                f"enum_sources[{enum_name!r}] has no matching DBML enum "
                f"{enum_name!r} in the schema.",
            ))
        elif dbml_enum.members != choices:
            findings.append(Finding(
                "error",
                f"DBML enum {enum_name!r} members differ from configured "
                f"enum_sources[{enum_name!r}] — "
                f"DBML: {dbml_enum.members!r}; YAML: {choices!r}",
            ))

    # === Permissions cross-checks (R4) ===
    if bundle.mapping.permissions is not None:
        perms = bundle.mapping.permissions

        # list_permissions.default.site_role, when declared, must be a known
        # site role — a typo would silently scope the default to nothing. The
        # valid roles are data-driven: those declared on the mapping's
        # entities, plus "default" (no hardcoded any labels you choose.
        scope = perms.default_policy_site_role
        known_roles = {e.site_role for e in bundle.mapping.entities.values()} | {"default"}
        if scope is not None and scope not in known_roles:
            findings.append(Finding(
                "error",
                f"list_permissions.default.site_role: unknown site role "
                f"{scope!r} (mapping declares: {', '.join(sorted(known_roles))}).",
            ))

        # permission_levels[*].name must be unique.
        seen_level_names: set[str] = set()
        for lvl in perms.levels:
            if lvl.name in seen_level_names:
                findings.append(Finding("error", f"permission_levels: duplicate name {lvl.name!r}"))
            seen_level_names.add(lvl.name)

        # permission_levels[*].base_permissions must be known bits.
        for lvl in perms.levels:
            for bit in lvl.base_permissions:
                if bit not in BASE_PERMISSIONS:
                    findings.append(Finding(
                        "error",
                        f"permission_levels[{lvl.name!r}]: unknown base permission {bit!r}",
                    ))

        # groups[*].name must be unique.
        seen_group_names: set[str] = set()
        custom_group_names = {g.name for g in perms.groups}
        for grp in perms.groups:
            if grp.name in seen_group_names:
                findings.append(Finding("error", f"groups: duplicate name {grp.name!r}"))
            seen_group_names.add(grp.name)

        # groups[*].owner_group must be a built-in SP group or a declared custom group.
        for grp in perms.groups:
            owner_ok = (
                grp.owner_group in _BUILTIN_SP_GROUPS
                or grp.owner_group in custom_group_names
            )
            if not owner_ok:
                findings.append(Finding(
                    "error",
                    f"groups[{grp.name!r}]: owner_group {grp.owner_group!r} is not a "
                    f"built-in SP group or a declared custom group",
                ))

        # Collect all valid level names (built-in + declared custom).
        all_level_names = BUILT_IN_LEVELS | seen_level_names
        # Collect all valid group names (declared custom + built-in SP groups).
        all_group_names = custom_group_names | _BUILTIN_SP_GROUPS

        def _check_policy_assignments(policy: ListPermissionPolicy, ctx: str) -> None:
            for i, assignment in enumerate(policy.assignments):
                lvl = assignment.level
                if lvl not in all_level_names:
                    findings.append(Finding(
                        "error",
                        f"{ctx}.assignments[{i}]: level {lvl!r} is not a built-in "
                        f"or declared custom permission level",
                    ))
                principal = assignment.principal
                if principal.kind != "group":
                    continue
                suggested_kind = _ASSOCIATED_GROUP_ALIASES.get(
                    (principal.name or "").casefold(),
                )
                if suggested_kind is not None:
                    # Phase 4.2 resolves kind=group via sitegroups/getbyname(name).
                    # The built-in aliases never exist under these literal names
                    # on real sites (the associated groups are named
                    # '<SiteTitle> Owners' etc.), so the assignment would fail
                    # at deploy time.
                    findings.append(Finding(
                        "error",
                        f"{ctx}.assignments[{i}]: principal group "
                        f"{principal.name!r} is a built-in associated-group "
                        f"alias that cannot be resolved by name at deploy time "
                        f"(real sites name it '<SiteTitle> ...'). Use principal "
                        f"kind {suggested_kind!r} instead.",
                    ))
                elif principal.name not in all_group_names:
                    findings.append(Finding(
                        "error",
                        f"{ctx}.assignments[{i}]: principal group {principal.name!r} "
                        f"is not a built-in or declared custom group",
                    ))

        if perms.default_policy is not None:
            _check_policy_assignments(perms.default_policy, "list_permissions.default")

        # list_permissions.overrides keys must be unprefixed DBML table names.
        for entity_name, override_policy in perms.overrides.items():
            if entity_name not in table_names:
                findings.append(Finding(
                    "error",
                    f"list_permissions.overrides: key {entity_name!r} is not a "
                    "known DBML table name (use unprefixed name, "
                    "e.g. 'Ticket' not 'APP_Ticket')",
                ))
            ctx_key = f"list_permissions.overrides[{entity_name!r}]"
            _check_policy_assignments(override_policy, ctx_key)

    return findings


def _validate_cross_site_expansion(
    schema: Schema, bundle: MappingBundle, extension: DeploymentExtension,
) -> list[Finding]:
    """Every column named in ``cross_site_reference_columns`` must be handled
    by the active extension's ``expand_column`` hook. The generic
    core no longer knows how to expand such a column, so if the extension
    defers (returns None) the deploy plan would silently drop the reference.
    Surface that as an error. Entity/column existence is already checked by
    validate_against_mapping, so missing targets are skipped here."""
    findings: list[Finding] = []
    tables_by_name = {t.name: t for t in schema.tables}
    for xref in bundle.mapping.cross_site_reference_columns:
        table = tables_by_name.get(xref.entity)
        if table is None:
            continue
        col = next((c for c in table.columns if c.name == xref.column), None)
        if col is None:
            continue
        if extension.expand_column(table, col, bundle) is None:
            findings.append(Finding(
                "error",
                f"cross_site_reference_columns requires an extension that "
                f"handles expand_column ({xref.entity}.{xref.column}); the "
                f"active extension deferred it.",
            ))
    return findings


def validate_all(
    schema: Schema, bundle: MappingBundle, extension: DeploymentExtension,
) -> list[Finding]:
    """Run every validation stage: core schema rules, mapping cross-checks,
    the cross-site/extension contract, then the active extension's
    project-specific rules."""
    return (
        validate(schema)
        + validate_against_mapping(schema, bundle)
        + _validate_cross_site_expansion(schema, bundle, extension)
        + extension.extra_validators(bundle, schema)
    )
