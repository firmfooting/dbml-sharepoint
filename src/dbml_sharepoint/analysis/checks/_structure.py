# src/dbml_sharepoint/analysis/checks/_structure.py
"""Entities, cross-site references, indexes, deferred lookups, calculated columns."""

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.ordering import compute_phases
from dbml_sharepoint.analysis.validator import (
    CALCULATED_TYPES,
    MAX_CALCULATED_FORMULA,
    Finding,
    _rendered_columns,
    formula_column_refs,
)

_UNSUPPORTED_INDEX_TYPES = {
    "longtext": "Multiple lines of text (Note)",
    "richtext": "Multiple lines of text (Note)",
    "hyperlink": "Hyperlink",
}


def check(vc: ValidationContext) -> list[Finding]:
    schema = vc.schema
    bundle = vc.bundle
    table_names = vc.table_names
    tables_by_name = vc.tables_by_name
    cross_site_by_entity = vc.cross_site_by_entity
    findings: list[Finding] = []
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
            if col.unique:
                findings.append(Finding(
                    "error",
                    f"{xref.entity}.{xref.column}: a cross-site reference cannot "
                    "be unique. Its logical DBML column is replaced by generated "
                    "Abbreviation and SiteUrl fields, so the column-level unique "
                    "constraint would not be deployed.",
                ))
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
                if any(col.name == generated and col.name != xref.column for col in table.columns):
                    findings.append(Finding(
                        "error",
                        f"cross_site {xref.entity}.{xref.column}: generated field "
                        f"{generated!r} collides with the declared DBML column "
                        f"{xref.entity}.{generated}.",
                    ))

    # DBML table indexes are the sole source of ordinary SharePoint indexes.
    # The deployer can represent only a one-column index and SharePoint does
    # not expose DBML's SQL name/type options, so unsupported structure is a
    # build error rather than silently discarded metadata.
    for entity_name in bundle.mapping.entities:
        indexed_table = tables_by_name.get(entity_name)
        if indexed_table is None:
            continue
        xcols = cross_site_by_entity.get(entity_name, set())
        rendered = _rendered_columns(indexed_table, xcols)
        indexed: list[str] = []
        for position, index in enumerate(indexed_table.indexes):
            ctx = f"{entity_name}.indexes[{position}]"
            if len(index.columns) != 1:
                findings.append(Finding(
                    "error",
                    f"{ctx}: composite index {index.columns!r} is unsupported; "
                    "SharePoint deployment supports one column per DBML index.",
                ))
                continue
            settings = {
                "name": index.name,
                "unique": index.unique or None,
                "type": index.type,
                "pk": index.pk or None,
                "note": index.note or None,
            }
            configured = {key: value for key, value in settings.items() if value is not None}
            if configured:
                findings.append(Finding(
                    "error",
                    f"{ctx}: DBML index settings {configured!r} are unsupported by "
                    "SharePoint. Declare a bare column index; use the column's "
                    "[unique] setting when uniqueness is required.",
                ))
            indexed.append(index.columns[0])
        for duplicate in sorted({name for name in indexed if indexed.count(name) > 1}):
            findings.append(Finding(
                "error",
                f"{entity_name}.indexes: duplicate index target {duplicate!r}.",
            ))
        # Unique fields carry an implicit SharePoint index and count toward
        # the same per-list ceiling as explicit declarations.
        unique_indexes = {
            col.name for col in indexed_table.columns
            if col.unique and col.name in rendered
        }
        for duplicate in sorted(set(indexed) & unique_indexes):
            findings.append(Finding(
                "error",
                f"{entity_name}.indexes: {duplicate!r} is already indexed by "
                "its column [unique] setting; remove the redundant indexes entry.",
            ))
        effective_indexes = set(indexed) | unique_indexes
        if len(effective_indexes) > 20:
            findings.append(Finding(
                "error",
                f"{entity_name}.indexes: {len(effective_indexes)} "
                f"effective indexes exceed SharePoint's limit of 20 "
                f"(including unique columns).",
            ))
        columns_by_name = {col.name: col for col in indexed_table.columns}
        for col_name in indexed:
            if col_name not in rendered:
                hint = (
                    " (cross-site logical columns are replaced by generated "
                    "companion fields and cannot be indexed from DBML)"
                    if col_name in xcols
                    else ""
                )
                findings.append(Finding(
                    "error",
                    f"{entity_name}.indexes: {col_name!r} is not a "
                    f"rendered column of {entity_name}{hint}.",
                ))
                continue
            column = columns_by_name.get(col_name)
            if column is not None and column.type in _UNSUPPORTED_INDEX_TYPES:
                findings.append(Finding(
                    "error",
                    f"{entity_name}.indexes: {col_name!r} is a "
                    f"{_UNSUPPORTED_INDEX_TYPES[column.type]} column, which SharePoint "
                    f"cannot index.",
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
    # calculated columns cannot be indexed (handled here separately from the
    # other unsupported index field kinds checked above).
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
    for table in schema.tables:
        for index in table.indexes:
            if len(index.columns) != 1:
                continue
            col_name = index.columns[0]
            if col_name in calc_columns_by_table.get(table.name, set()):
                findings.append(Finding(
                    "error",
                    f"{table.name}.indexes: {col_name!r} is a "
                    f"calculated column — SharePoint cannot index calculated "
                    f"columns.",
                ))

    return findings
