# src/dbml_sharepoint/generators/jsgen.py
"""Render deploy.js from the schema, mapping bundle, and release."""

import json
import re
from pathlib import Path
from typing import Any

from dbml_sharepoint.analysis.conditions import (
    SYSTEM_COLUMN_TYPES,
    effective_column_types,
    to_caml,
    to_validation,
)
from dbml_sharepoint.analysis.forms import compose_visibility
from dbml_sharepoint.analysis.ordering import compute_phases, site_tables_in_order
from dbml_sharepoint.analysis.permissions import base_permissions_to_high_low
from dbml_sharepoint.analysis.phases import phases_context
from dbml_sharepoint.analysis.typemap import format_description, map_column
from dbml_sharepoint.analysis.validator import FORMULA_COLUMN_REF, formula_column_refs
from dbml_sharepoint.extension import DeploymentExtension, NullExtension, SiteContext
from dbml_sharepoint.model.mapping_loader import (
    ColumnValidation,
    EntityMapping,
    EntitySection,
    FormVisibility,
    MappingBundle,
    ViewDef,
    view_url_slug,
)
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release
from dbml_sharepoint.templating import script_env


def _resolve_site_context(
    site_context: SiteContext | None,
    *,
    site_url: str,
    site_role: str,
    release: Release | None,
) -> SiteContext:
    """Return the caller-supplied SiteContext, or synthesise a minimal one for
    direct callers (e.g. tests) that pass only the scalar build inputs."""
    if site_context is not None:
        return site_context
    return SiteContext(
        site_url=site_url,
        site_role=site_role,
        release=release,
        output_dir=Path(),
        extension_args={},
    )


def generate_deploy_js(
    *,
    schema: Schema,
    bundle: MappingBundle,
    release: Release,
    site_url: str,
    site_role: str,
    source_dbml: str,
    source_mtime: str,
    generated_at: str,
    extension: DeploymentExtension | None = None,
    site_context: SiteContext | None = None,
) -> str:
    env = script_env()
    ext: DeploymentExtension = extension if extension is not None else NullExtension()
    sc = _resolve_site_context(
        site_context, site_url=site_url, site_role=site_role, release=release,
    )
    schema_json = build_schema_json(
        schema,
        bundle,
        site_role,
        site_url=site_url,
        release=release,
        extension=ext,
        site_context=sc,
    )
    template = env.get_template("deploy.js.j2")
    return template.render(
        site_url=site_url,
        site_role=site_role,
        release=release,
        source_dbml=source_dbml,
        source_mtime=source_mtime,
        generated_at=generated_at,
        schema_json=schema_json,
        phases=phases_context(),
        unmanaged_sentinel=UNMANAGED,
    )


# SP formula string literals use Excel-style "" escaping; odd split indices
# are literal tokens and pass through any rewrite untouched.
_FORMULA_LITERAL_SPLIT = re.compile(r'("(?:""|[^"])*")')


def _rewrite_formula_refs(formula: str, display_by_col: dict[str, str]) -> str:
    """Rewrite [InternalName] formula references to [Display Name].

    SharePoint resolves calculated-formula column references against DISPLAY
    names when the formula is written, so once fields are renamed a formula
    authored with internal names would fail to create. Authors keep writing
    internal names; the build translates. String literals are data and are
    never rewritten."""

    def _replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        return f"[{display_by_col.get(name, name)}]"

    return "".join(
        part if index % 2 == 1 else FORMULA_COLUMN_REF.sub(_replace, part)
        for index, part in enumerate(_FORMULA_LITERAL_SPLIT.split(formula))
    )


# CAML fragments for the declared-view DSL. Operators/columns are validated
# at build time (validate_against_mapping), so rendering can be direct.

# `declared` reconcile leaves an undeclared column alone, which is not the
# same as clearing it; the deploy script must be able to tell them apart.
UNMANAGED = "__dbmlsp_unmanaged__"

# SP rejects ValidationFormula even when the desired value is an empty
# string on these field kinds. This is a property-surface capability, not
# merely an operand rule: exact reconciliation must not attempt to CLEAR a
# formula the field type cannot carry. Confirmed live for Note (HTTP 500,
# "This field type does not support validation formulas"); Lookup, User and
# Calculated are already refused as validation operands for the same platform
# limitation.
_COLUMN_VALIDATION_UNSUPPORTED_FIELD_KINDS = frozenset({3, 7, 17, 20})


def _section_target[T](
    section: EntitySection[T] | None,
    column: str,
    *,
    is_calculated: bool,
) -> tuple[T, bool] | tuple[None, bool]:
    """What a per-column section wants done to one column.

    Returns (declaration, clear):
      (None, False)  — not managed here; the live value is never touched
      (None, True)   — `reconcile: exact` with no entry, so CLEAR it
      (decl, False)  — render the declaration

    Shared by both sections deliberately, so the calculated-column exclusion
    cannot apply to one and not the other. Clearing a calculated column is a
    no-op write — it never reaches an entry form, which is why declaring one
    is a build error — but the manifest would report a clear that never
    happened, and two siblings disagreeing about one rule is how the wrong
    one gets "fixed" later.
    """
    if section is None or is_calculated:
        return None, False
    declared = section.columns.get(column)
    if declared is None:
        return None, section.reconcile == "exact"
    return declared, False


def _visibility_formula(
    section: "EntitySection[FormVisibility] | None",
    column: str,
    types: dict[str, str],
    *,
    is_calculated: bool = False,
) -> str:
    """The composed formula for a column, "" to clear it, or UNMANAGED.

    Under `reconcile: exact` an undeclared column is cleared rather than
    left alone, so deployed state follows the declaration rather than the
    history of edits to it.
    """
    declared, clear = _section_target(section, column, is_calculated=is_calculated)
    if declared is None:
        return "" if clear else UNMANAGED
    return compose_visibility(
        new=declared.new, existing=declared.existing, when=declared.when, types=types,
    )


def _column_validation(
    section: "EntitySection[ColumnValidation] | None",
    column: str,
    types: dict[str, str],
    display_map: dict[str, str],
    *,
    field_type_kind: int,
    is_calculated: bool = False,
) -> tuple[str, str]:
    if field_type_kind in _COLUMN_VALIDATION_UNSUPPORTED_FIELD_KINDS:
        return (UNMANAGED, UNMANAGED)
    declared, clear = _section_target(section, column, is_calculated=is_calculated)
    if declared is None:
        return ("", "") if clear else (UNMANAGED, UNMANAGED)
    # SP resolves validation formulas by DISPLAY name, exactly as it does
    # for the list-level rule and for calculated columns.
    rendered = _rewrite_formula_refs(f"={to_validation(declared.when, types)}", display_map)
    return (rendered, declared.message)



def _view_caml_query(view: ViewDef, column_types: dict[str, str]) -> str:
    """Render a declared view's ViewQuery inner XML: <GroupBy>, then <Where>
    from the shared condition grammar, then <OrderBy> (ascending is CAML's
    default; only descending carries the attribute)."""
    parts: list[str] = []
    if view.group_by is not None:
        collapse = "TRUE" if view.group_by.collapsed else "FALSE"
        parts.append(
            f'<GroupBy Collapse="{collapse}">'
            f'<FieldRef Name="{view.group_by.field}"/></GroupBy>',
        )
    if view.where is not None:
        # System columns are renderable in a view but never declared in
        # DBML; without their types a Created comparison would render as
        # Type="Text" and the view would answer with the wrong rows.
        types = {**SYSTEM_COLUMN_TYPES, **column_types}
        parts.append(f"<Where>{to_caml(view.where, types)}</Where>")
    if view.sort:
        refs = "".join(
            f'<FieldRef Name="{entry.field}"/>' if entry.direction == "asc"
            else f'<FieldRef Name="{entry.field}" Ascending="FALSE"/>'
            for entry in view.sort
        )
        parts.append(f"<OrderBy>{refs}</OrderBy>")
    return "".join(parts)


def _order_calculated_after_references(
    fields: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Order a list's Phase-1 fields so every calculated field follows the
    columns its formula references.

    SharePoint resolves a calculated formula's [Column] references when the
    field is CREATED and rejects the POST (HTTP 500, "The formula refers to a
    column that does not exist") on any miss, so declaration order is not a
    valid creation order when a formula references a later column. Plain
    fields keep declaration order (it drives form order; calculated fields
    never appear on entry forms), calculated fields move after them,
    topologically ordered among themselves for calc-on-calc chains."""
    plain = [f for f in fields if "Formula" not in f["body"]]
    calc = [f for f in fields if "Formula" in f["body"]]
    if not calc:
        return fields
    calc_titles = {f["title"] for f in calc}
    ordered: list[dict[str, Any]] = []
    emitted: set[str] = set()
    remaining = list(calc)
    while remaining:
        ready = [
            f for f in remaining
            if not (
                (formula_column_refs(f["body"]["Formula"]) & calc_titles)
                - emitted - {f["title"]}
            )
        ]
        if not ready:
            # validate_against_mapping reports this as a build error first;
            # guard defensively in case it is bypassed.
            raise ValueError(
                "circular calculated-column references: "
                + ", ".join(sorted(f["title"] for f in remaining)),
            )
        for f in ready:
            ordered.append(f)
            emitted.add(f["title"])
        remaining = [f for f in remaining if f["title"] not in emitted]
    return plain + ordered


def build_schema_json(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    site_url: str = "",
    release: Release | None = None,
    extension: DeploymentExtension | None = None,
    site_context: SiteContext | None = None,
) -> dict[str, Any]:
    by_name = {t.name: t for t in schema.tables}
    plan = compute_phases(schema)

    ext: DeploymentExtension = extension if extension is not None else NullExtension()
    sc = _resolve_site_context(
        site_context, site_url=site_url, site_role=site_role, release=release,
    )

    cross_site_keys = {
        (xref.entity, xref.column) for xref in bundle.mapping.cross_site_reference_columns
    }
    # Cross-site columns are emitted as Choice + URL pairs; they must never
    # appear in phase 2 (would be a double-emit alongside the cross-site
    # expansion). Subtract cross_site_keys defensively.
    deferred_set = set(plan.phase2_lookups) - cross_site_keys
    enums_by_name = {e.name: e for e in schema.enums}

    lists: list[dict[str, Any]] = []
    phase2: list[dict[str, Any]] = []
    indexed_columns_out: list[dict[str, Any]] = []
    views_out: list[dict[str, Any]] = []
    form_formatting_out: list[dict[str, Any]] = []
    field_defaults_out: list[dict[str, Any]] = []

    for table_name in site_tables_in_order(schema, bundle.mapping.entities, site_role):
        entity = bundle.mapping.entities[table_name]
        list_title = bundle.mapping.prefix + table_name
        versioning_o = bundle.mapping.versioning_overrides.get(table_name, {})
        enable_versioning = bool(versioning_o.get(
            "enable_versioning", bundle.mapping.versioning_default.enable_versioning,
        ))
        major_limit = int(versioning_o.get(
            "major_version_limit", bundle.mapping.versioning_default.major_version_limit,
        ))
        enable_minor_versions = bool(versioning_o.get(
            "enable_minor_versions", bundle.mapping.versioning_default.enable_minor_versions,
        ))
        table = by_name[table_name]

        fields_phase1: list[dict[str, Any]] = []
        title_patch: dict[str, Any] | None = None

        for col in table.columns:
            if (table.name, col.name) in cross_site_keys:
                # Cross-site columns are expanded by the active extension
                #. expand_column returns the SP field list (or
                # None to defer). None here is a validation error surfaced by
                # validate_all; guard defensively in case it is bypassed.
                expanded = ext.expand_column(table, col, bundle)
                if expanded is None:
                    raise ValueError(
                        "cross_site_reference_columns requires an extension "
                        f"that handles expand_column ({table.name}.{col.name})",
                    )
                fields_phase1.extend(expanded)
                continue

            if col.name == "Id" and col.is_pk and col.is_auto_increment:
                continue

            if col.name == "Title":
                title_patch = {
                    "__metadata": {"type": "SP.FieldText"},
                    "Required": col.required,
                    "Description": format_description(col.note),
                }
                if col.default is not None:
                    title_patch["DefaultValue"] = col.default
                    field_defaults_out.append({
                        "list": list_title,
                        "field": "Title",
                        "metadata_type": "SP.FieldText",
                        "default_value": col.default,
                    })
                continue

            if (table.name, col.name) in deferred_set:
                prefix = bundle.mapping.prefix
                target = (prefix + col.ref.target_table) if col.ref else ""
                phase2.append({
                    "list": list_title,
                    "target_list": target,
                    "field": _field_body(
                        col, enums_by_name, list_title_prefix=prefix,
                        entities=bundle.mapping.entities,
                    ),
                })
                continue

            prefix = bundle.mapping.prefix
            field = _field_body(
                col, enums_by_name, list_title_prefix=prefix,
                entities=bundle.mapping.entities,
                formulas=bundle.mapping.calculated_formulas.get(table_name, {}),
            )
            if field is None:
                continue
            fields_phase1.append(field)
            body = field["body"]
            if "DefaultValue" in body:
                field_defaults_out.append({
                    "list": list_title,
                    "field": field["title"],
                    "metadata_type": body["__metadata"]["type"],
                    "default_value": body["DefaultValue"],
                })

        fields_phase1 = _order_calculated_after_references(fields_phase1)

        # Display titles: CREATE bodies keep Title = internal name (clean
        # InternalName); reconciliation renames Title to display_title after
        # create. Formula refs must be rewritten to the display names SP will
        # resolve them against.
        display_map = {
            f["title"]: bundle.mapping.display_name_for(table_name, f["title"])
            for f in fields_phase1
        }
        table_formatting = bundle.mapping.column_formatting.get(table_name, {})
        # form_visibility carries per-column visibility as a composed
        # ClientValidationFormula. Never write SchemaXml ShowIn*Form:
        # saving the form designer migrates it into FieldLink.Hidden,
        # which hides a column from EVERY form and cannot be undone
        # over REST.
        visibility = bundle.mapping.form_visibility.get(table_name)
        validation = bundle.mapping.column_validation.get(table_name)
        col_types = effective_column_types(
            {c.name: c.type for c in table.columns},
            {name for entity_name, name in cross_site_keys if entity_name == table_name},
        )
        calculated_here = bundle.mapping.calculated_formulas.get(table_name, {})
        for f in fields_phase1:
            f["display_title"] = display_map[f["title"]]
            is_calculated = f["title"] in calculated_here
            f["client_validation_formula"] = _visibility_formula(
                visibility, f["title"], col_types, is_calculated=is_calculated,
            )
            f["validation_formula"], f["validation_message"] = _column_validation(
                validation, f["title"], col_types, display_map,
                field_type_kind=f["body"]["FieldTypeKind"],
                is_calculated=is_calculated,
            )
            f["seal"] = bundle.mapping.seal_columns
            if "Formula" in f["body"]:
                f["body"]["Formula"] = _rewrite_formula_refs(f["body"]["Formula"], display_map)
            formatter = table_formatting.get(f["title"])
            f["custom_formatter"] = (
                json.dumps(formatter, separators=(",", ":"), sort_keys=True)
                if formatter is not None
                else None
            )
        for deferred in phase2:
            if deferred["list"] == list_title and "display_title" not in deferred["field"]:
                deferred["field"]["display_title"] = bundle.mapping.display_name_for(
                    table_name, deferred["field"]["title"],
                )
                deferred_formatter = table_formatting.get(deferred["field"]["title"])
                deferred["field"]["custom_formatter"] = (
                    json.dumps(deferred_formatter, separators=(",", ":"), sort_keys=True)
                    if deferred_formatter is not None
                    else None
                )
                deferred_calculated = deferred["field"]["title"] in calculated_here
                deferred["field"]["client_validation_formula"] = _visibility_formula(
                    visibility, deferred["field"]["title"], col_types,
                    is_calculated=deferred_calculated,
                )
                (
                    deferred["field"]["validation_formula"],
                    deferred["field"]["validation_message"],
                ) = _column_validation(
                    validation, deferred["field"]["title"], col_types, display_map,
                    field_type_kind=deferred["field"]["body"]["FieldTypeKind"],
                    is_calculated=deferred_calculated,
                )
                deferred["field"]["seal"] = bundle.mapping.seal_columns

        if title_patch is None:
            # No DBML Title column: the built-in Title on a base-template list is
            # Required by default, which blocks programmatic inserts (a flow
            # creating a row without Title gets HTTP 400) and forces manual
            # entry. Patch it optional.
            title_patch = {
                "__metadata": {"type": "SP.FieldText"},
                "Required": False,
            }

        declared_validation = bundle.mapping.list_validation.get(table_name)
        lists.append({
            "title": list_title,
            "kind": entity.kind,
            "base_template": entity.base_template,
            "description": (table.note[:255] if table.note else ""),
            "content_types_enabled": False,
            "enable_versioning": enable_versioning,
            "major_version_limit": major_limit,
            "enable_minor_versions": enable_minor_versions,
            "fields_phase1": fields_phase1,
            "title_patch": title_patch,
            "validation_formula": (
                # SP resolves validation formulas by DISPLAY name, like
                # calculated formulas, so names are rewritten after the
                # grammar renders them.
                _rewrite_formula_refs(
                    f"={to_validation(declared_validation.when, col_types)}", display_map,
                )
                if declared_validation is not None
                else None
            ),
            "validation_message": (
                declared_validation.message if declared_validation is not None else None
            ),
            "prevent_deletion": bundle.mapping.prevent_list_deletion,
        })

        for col_name in bundle.mapping.indexed_columns.get(table_name, []):
            indexed_columns_out.append({"list": list_title, "field": col_name})

        declared_form = bundle.mapping.form_formatting.get(table_name)
        if declared_form is not None:
            # Pane-native encoding: the CT property is ONE JSON string whose
            # *JSONFormatter keys hold part OBJECTS — the Format pane
            # displays this cleanly; string-encoded parts render but display
            # escaped (Phase 3.2 compares encoding-agnostically for sites
            # deployed under the old nested-string encoding). Body section
            # field lists are the one place SP matches by DISPLAY name —
            # rewrite them through the display map.
            parts: dict[str, Any] = {}
            if declared_form.header is not None:
                parts["headerJSONFormatter"] = declared_form.header
            if declared_form.body is not None:
                body = json.loads(json.dumps(declared_form.body))
                for section in body.get("sections") or []:
                    if isinstance(section, dict) and isinstance(section.get("fields"), list):
                        section["fields"] = [
                            bundle.mapping.display_name_for(table_name, name)
                            for name in section["fields"]
                        ]
                parts["bodyJSONFormatter"] = body
            if declared_form.footer is not None:
                parts["footerJSONFormatter"] = declared_form.footer
            form_formatting_out.append({
                "list": list_title,
                "client_form_custom_formatter": json.dumps(
                    parts, separators=(",", ":"), sort_keys=True,
                ),
            })

        column_types = effective_column_types(
            {col.name: col.type for col in table.columns},
            {name for entity_name, name in cross_site_keys if entity_name == table_name},
        )
        declared_views = bundle.mapping.views.get(table_name, [])
        views_to_render = list(declared_views)
        if entity.kind != "DocumentLibrary":
            emitted_fields = [field["title"] for field in fields_phase1]
            emitted_fields.extend(
                lookup["field"]["title"]
                for lookup in phase2
                if lookup["list"] == list_title
            )
            system_fields = list(SYSTEM_COLUMN_TYPES)
            all_items = ViewDef(
                title="All Items",
                fields=[
                    "ID", "Title", *emitted_fields,
                    *(name for name in system_fields if name != "ID"),
                ],
                default=not any(view.default for view in declared_views),
            )
            # A live list's built-in All Items may still hold DefaultView.
            # SharePoint will not reliably hide the current default, so an
            # authored default must be reconciled first. A recovery view that
            # is itself the default stays first and visible.
            if all_items.default:
                views_to_render.insert(0, all_items)
            else:
                views_to_render.append(all_items)
        for view in views_to_render:
            views_out.append({
                "list": list_title,
                "title": view.title,
                "view_fields": list(view.fields),
                "caml_query": _view_caml_query(view, column_types),
                "row_limit": view.row_limit,
                "set_default": view.default,
                # All Items is a recovery/audit view. Keep it out of modern
                # view tabs when an authored default provides the working UI.
                "hidden": view.title == "All Items" and not view.default,
                "formatting": (
                    json.dumps(view.formatting, separators=(",", ":"), sort_keys=True)
                    if view.formatting is not None
                    else None
                ),
                # ColumnWidth binds by DISPLAY title (live finding: internal
                # names are accepted but silently reset the widths), so keys
                # are rewritten at generation time like calculated-formula
                # and form-body references — the deployer asserts the same
                # display titles, so bundle and live Titles cannot drift.
                "widths": (
                    {
                        bundle.mapping.display_name_for(table_name, width_col): width_px
                        for width_col, width_px in view.widths.items()
                    }
                    if view.widths
                    else None
                ),
                # The .aspx name is fixed at creation: create under the slug,
                # rename Title to the declared display afterwards.
                "url_slug": view_url_slug(view.title),
            })

    # === Permissions (R5) ===
    permission_levels_out: list[dict[str, Any]] = []
    groups_out: list[dict[str, Any]] = []
    list_assignments_out: list[dict[str, Any]] = []

    mapping_perms = bundle.mapping.permissions
    if mapping_perms is not None:
        for lvl in mapping_perms.levels:
            hl = base_permissions_to_high_low(lvl.base_permissions)
            permission_levels_out.append({
                "name": lvl.name,
                "description": lvl.description,
                "base_permissions": {"high": hl.high, "low": hl.low},
            })

        for grp in mapping_perms.groups:
            groups_out.append({
                "name": grp.name,
                "description": grp.description,
                "owner_group": grp.owner_group,
                "allow_members_edit_membership": grp.allow_members_edit_membership,
                "allow_request_to_join_leave": grp.allow_request_to_join_leave,
                "auto_accept_request_to_join_leave": grp.auto_accept_request_to_join_leave,
                "only_allow_members_view_membership": grp.only_allow_members_view_membership,
                "require_empty_at_deploy": grp.require_empty_at_deploy,
                "enroll_operator_during_deploy": grp.enroll_operator_during_deploy,
            })

        # Build list_assignments for every list in this site role.
        prefix = bundle.mapping.prefix
        for table_name in plan.list_creation_order:
            acl_entity = bundle.mapping.entities.get(table_name)
            if acl_entity is None or acl_entity.site_role != site_role:
                continue
            policy = bundle.mapping.permissions_for_entity(table_name)
            if policy is None:
                continue
            list_title = prefix + table_name
            assignments_out: list[dict[str, Any]] = []
            for assignment in policy.assignments:
                p = assignment.principal
                principal_out: dict[str, Any] = {"kind": p.kind}
                if p.kind == "group" and p.name is not None:
                    principal_out["name"] = p.name
                assignments_out.append({
                    "principal": principal_out,
                    "level": assignment.level,
                })
            list_assignments_out.append({
                "list": list_title,
                "break_inheritance": policy.break_inheritance,
                "reconcile_mode": policy.reconcile_mode,
                "assignments": assignments_out,
            })

    # === Seed items (extension-provided) ===
    # The active extension decides which lists get a seeded singleton row and
    # with what fields. The core is domain-agnostic: it renders
    # whatever {list title -> field dict} the hook returns. Sorted for
    # deterministic output. skip_if_has_rows means an existing singleton must
    # match every declared field exactly; an arbitrary row never counts as an
    # idempotent success.
    seed_items: list[dict[str, Any]] = [
        {"title": title, "fields": fields, "skip_if_has_rows": True}
        for title, fields in sorted(ext.seed_lists(bundle, schema, sc).items())
    ]

    return {
        "lists": lists,
        "phase2_lookups": phase2,
        "indexed_columns": indexed_columns_out,
        "views": views_out,
        "form_formatting": form_formatting_out,
        "field_defaults": field_defaults_out,
        "permission_levels": permission_levels_out,
        "groups": groups_out,
        "list_assignments": list_assignments_out,
        "seed_items": seed_items,
    }


def _field_body(
    col: Any, enums_by_name: dict[str, Any], list_title_prefix: str,
    entities: dict[str, EntityMapping] | None = None,
    formulas: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    enum_names = set(enums_by_name)
    sp = map_column(col, enum_names)
    if sp.kind == "Skip":
        return None

    body: dict[str, Any] = {"Title": sp.name, "FieldTypeKind": sp.field_type_kind}
    metadata: dict[str, str] = {"type": _meta_type(sp.kind)}
    body["__metadata"] = metadata

    if sp.required:
        body["Required"] = True
    if sp.unique:
        body["EnforceUniqueValues"] = True
        body["Indexed"] = True
    if sp.description:
        body["Description"] = sp.description

    match sp.kind:
        case "Text":
            body["MaxLength"] = sp.max_length
            if sp.default is not None:
                body["DefaultValue"] = sp.default
        case "Note":
            body["RichText"] = sp.rich_text
            body["NumberOfLines"] = sp.number_of_lines
            body["AppendOnly"] = False
        case "Choice":
            if sp.choices_enum is None:
                raise ValueError(
                    f"Choice field {sp.name!r} has no backing enum "
                    "(typemap invariant violated)",
                )
            members = enums_by_name[sp.choices_enum].members
            body["Choices"] = {"results": list(members)}
            body["FillInChoice"] = False
            if sp.default is not None:
                body["DefaultValue"] = sp.default
        case "DateTime":
            body["DisplayFormat"] = 0 if sp.date_only else 1
            # SP dynamic defaults ("[today]") and literal dates both ride
            # DefaultValue, so this branch must carry whatever the typemap
            # resolved rather than handling only literals.
            if sp.default is not None:
                body["DefaultValue"] = str(sp.default)
        case "Boolean":
            if sp.default is not None:
                body["DefaultValue"] = _bool_default_to_sp(sp.default)
        case "URL":
            body["DisplayFormat"] = sp.display_format
        case "User":
            body["SelectionMode"] = sp.selection_mode
        case "Lookup":
            # Display the target list's primary field. Defaults to the built-in
            # "Title", but a target whose mapping declares display_column (e.g.
            # Membership → DisplayName) renders that instead — a bare "Title"
            # shows blank on lists that never populate Title.
            target_entity = (
                entities.get(sp.target_list) if entities and sp.target_list else None
            )
            lookup_field = (
                target_entity.display_column if target_entity else None
            ) or "Title"
            body["LookupField"] = lookup_field
            # A lookup is the one field type SharePoint refuses through a
            # normal POST of SP.FieldLookup to the /fields collection. Keep
            # the complete desired SP.FieldLookup body above for post-create
            # reconciliation/readback, but give deploy.js the supported
            # FieldCollection.AddField creation shape separately. The target
            # GUID is only known in the browser and is added there as
            # LookupListId.
            creation_parameters = {
                "__metadata": {"type": "SP.FieldCreationInformation"},
                "FieldTypeKind": sp.field_type_kind,
                "Title": sp.name,
                "Required": sp.required,
                "LookupFieldName": lookup_field,
            }
            target = list_title_prefix + (sp.target_list or "")
            return {
                "title": sp.name,
                "body": body,
                "target_list": target,
                "lookup_creation_parameters": creation_parameters,
            }
        case "Number":
            if sp.default is not None:
                # SP.Field.DefaultValue is a string even for Number fields.
                # Keeping the schema value numeric makes both the create body
                # and Phase 2.4 MERGE payload invalid for SharePoint REST.
                body["DefaultValue"] = str(sp.default)
        case "Calculated":
            # Formula comes from the mapping (calculated_formulas), joined in
            # here; the validator guarantees a formula exists for every
            # calculated column before generation runs.
            body["OutputType"] = sp.output_type
            body["Formula"] = (formulas or {}).get(sp.name, "")

    return {"title": sp.name, "body": body}


def _bool_default_to_sp(value: str | int | bool) -> str:
    """Map a DBML boolean default literal to SharePoint's '1'/'0' string.

    DBML/pydbml surfaces booleans as ``True``/``False`` or the integer/string
    literals ``1``/``0``/``'true'``/``'false'``. Interpret them explicitly
    rather than via Python truthiness, because ``bool('false')`` is ``True``.
    """
    if isinstance(value, str):
        return "1" if value.strip().lower() in {"1", "true", "yes"} else "0"
    return "1" if value else "0"


def _meta_type(kind: str) -> str:
    return {
        "Text": "SP.FieldText",
        "Note": "SP.FieldMultiLineText",
        "DateTime": "SP.FieldDateTime",
        "Choice": "SP.FieldChoice",
        "Lookup": "SP.FieldLookup",
        "Boolean": "SP.Field",
        "Number": "SP.FieldNumber",
        "URL": "SP.FieldUrl",
        "User": "SP.FieldUser",
        "Calculated": "SP.FieldCalculated",
    }[kind]
