# src/dbml_sharepoint/reportgen.py
"""Report-query generator: Power Query (M) and T-SQL views from the schema.

The same DBML + mapping that provisions the lists also describes how to
report on them. This module emits:

- one Power Query (M) query per list — ``OData.Feed`` against the list's
  REST endpoint, parameterised by a ``SiteUrl`` text parameter, with lookup
  and person columns expanded to a join key plus display column, and column
  types applied from the deployer's own typemap;
- a single T-SQL script of ``CREATE OR ALTER VIEW`` statements (SQLCMD
  variables for the landing/report schemas): a typed view per list plus an
  ``_Enriched`` view joining each lookup to its display column, for lists
  landed in a warehouse by any extract process;
- REPORTING.md with usage instructions and the Power BI relationship table
  derived from the DBML refs.

Cross-site reference columns are extension-expanded at deploy time into
shapes the core cannot know; they are skipped here and listed in
REPORTING.md. Person columns land differently per extract tool, so the SQL
views carry them as display-name text while the M queries expand both the
site-user id and display name.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dbml_sharepoint import __version__
from dbml_sharepoint.mapping_loader import MappingBundle
from dbml_sharepoint.parser import Schema, Table
from dbml_sharepoint.release import Release
from dbml_sharepoint.typemap import SPField, map_column


@dataclass
class _ListPlan:
    """Everything the renderers need for one list, in DBML column order."""

    entity: str
    list_title: str
    selects: list[str] = field(default_factory=list)
    expands: list[str] = field(default_factory=list)
    # (record column, inner field, expanded output column)
    record_expands: list[tuple[str, str, str]] = field(default_factory=list)
    # (output column, M type token)
    m_types: list[tuple[str, str]] = field(default_factory=list)
    # (landed column, SQL type)
    sql_columns: list[tuple[str, str]] = field(default_factory=list)
    # (fk column, target list title, target display column)
    joins: list[tuple[str, str, str]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    # Site-relative path of the item display form, ending in "?ID=" — the
    # ItemURL helper column is SiteUrl + this + the item id.
    item_url_path: str = ""
    # (internal/out column, model-facing display name) — populated only when
    # the mapping declares display_names; the rename is the LAST query step
    # so internal names remain the wire/OData contract.
    renames: list[tuple[str, str]] = field(default_factory=list)
    # Declared internal field names (no cross-site, no Id) — the expected
    # set for the user-added-column audit; cross-site names ride
    # ``skipped``.
    field_internal_names: list[str] = field(default_factory=list)


def _tables_for_role(schema: Schema, bundle: MappingBundle, site_role: str) -> list[Table]:
    """Schema-order tables mapped to the requested site role (same filter as
    jsgen: absent-from-mapping or other-role entities are not deployed there,
    so they must not be reported there either)."""
    out = []
    for table in schema.tables:
        entity = bundle.mapping.entities.get(table.name)
        if entity is not None and entity.site_role == site_role:
            out.append(table)
    return out


def _display_column(bundle: MappingBundle, target_entity: str) -> str:
    entity = bundle.mapping.entities.get(target_entity)
    if entity is not None and entity.display_column:
        return entity.display_column
    return "Title"


def _item_url_path(bundle: MappingBundle, entity_name: str, list_title: str) -> str:
    """Site-relative display-form path for one item, ending in ``?ID=``.

    Lists live under /Lists/<Title>/; document libraries put their forms
    under /<Title>/Forms/.
    """
    entity = bundle.mapping.entities.get(entity_name)
    if entity is not None and entity.kind == "DocumentLibrary":
        return f"/{list_title}/Forms/DispForm.aspx?ID="
    return f"/Lists/{list_title}/DispForm.aspx?ID="


def _build_plans(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> list[_ListPlan]:
    tables = _tables_for_role(schema, bundle, site_role)
    emitted = {t.name for t in tables}
    enum_names = {e.name for e in schema.enums}
    cross_site_keys = {
        (xref.entity, xref.column)
        for xref in bundle.mapping.cross_site_reference_columns
    }
    prefix = bundle.mapping.prefix

    plans: list[_ListPlan] = []
    for table in tables:
        plan = _ListPlan(
            entity=table.name,
            list_title=prefix + table.name,
            item_url_path=_item_url_path(bundle, table.name, prefix + table.name),
        )
        for col in table.columns:
            if (table.name, col.name) in cross_site_keys:
                plan.skipped.append(col.name)
                continue
            sp = map_column(col, enum_names)
            if sp.kind != "Skip":
                plan.field_internal_names.append(sp.name)
            match sp.kind:
                case "Skip":
                    plan.selects.append("Id")
                    plan.m_types.append(("Id", "Int64.Type"))
                    plan.sql_columns.append(("Id", "INT"))
                case "Text" | "Choice":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(255)"))
                case "Note":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(MAX)"))
                case "Number":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type number"))
                    plan.sql_columns.append((sp.name, "DECIMAL(18,4)"))
                case "DateTime":
                    plan.selects.append(sp.name)
                    if sp.date_only:
                        plan.m_types.append((sp.name, "type date"))
                        plan.sql_columns.append((sp.name, "DATE"))
                    else:
                        plan.m_types.append((sp.name, "type datetimezone"))
                        plan.sql_columns.append((sp.name, "DATETIMEOFFSET"))
                case "Boolean":
                    plan.selects.append(sp.name)
                    plan.m_types.append((sp.name, "type logical"))
                    plan.sql_columns.append((sp.name, "BIT"))
                case "URL":
                    # SP.FieldUrlValue arrives as a record; keep the Url part.
                    plan.selects.append(sp.name)
                    plan.record_expands.append((sp.name, "Url", f"{sp.name}Url"))
                    plan.m_types.append((f"{sp.name}Url", "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(2000)"))
                case "User":
                    plan.selects.append(f"{sp.name}Id")
                    plan.selects.append(f"{sp.name}/Title")
                    plan.expands.append(sp.name)
                    plan.record_expands.append((sp.name, "Title", f"{sp.name}Title"))
                    plan.m_types.append((f"{sp.name}Id", "Int64.Type"))
                    plan.m_types.append((f"{sp.name}Title", "type text"))
                    plan.sql_columns.append((sp.name, "NVARCHAR(255)"))
                case "Lookup":
                    target = sp.target_list or ""
                    display = _display_column(bundle, target)
                    plan.selects.append(f"{sp.name}Id")
                    plan.selects.append(f"{sp.name}/{display}")
                    plan.expands.append(sp.name)
                    plan.record_expands.append(
                        (sp.name, display, f"{sp.name}{display}"),
                    )
                    plan.m_types.append((f"{sp.name}Id", "Int64.Type"))
                    plan.m_types.append((f"{sp.name}{display}", "type text"))
                    plan.sql_columns.append((f"{sp.name}Id", "INT"))
                    if target in emitted:
                        plan.joins.append(
                            (f"{sp.name}Id", prefix + target, display),
                        )
                case "Calculated":
                    plan.selects.append(sp.name)
                    if sp.output_type == 9:
                        plan.m_types.append((sp.name, "type number"))
                        plan.sql_columns.append((sp.name, "DECIMAL(18,4)"))
                    elif sp.output_type == 4:
                        plan.m_types.append((sp.name, "type date"))
                        plan.sql_columns.append((sp.name, "DATE"))
                    else:
                        plan.m_types.append((sp.name, "type text"))
                        plan.sql_columns.append((sp.name, "NVARCHAR(255)"))
        if bundle.mapping.display_name_mode is not None:
            # Derived out-columns (FooId/FooTitle/FooUrl) resolve through the
            # same map: overrides hit exact column names, everything else
            # auto-splits ("RiskOwnerTitle" -> "Risk Owner Title").
            for out_name in [name for name, _ in plan.m_types] + ["ItemURL"]:
                display = bundle.mapping.display_name_for(table.name, out_name)
                if display != out_name:
                    plan.renames.append((out_name, display))
        plans.append(plan)
    return plans


# ---------------------------------------------------------------- Power Query


def _render_m(plan: _ListPlan) -> str:
    query_string = "?$select=" + ",".join(plan.selects)
    lines = [
        f"// {plan.list_title} — generated by dbml-sharepoint; regenerate "
        "rather than hand-edit.",
        "// Requires a text parameter named SiteUrl holding the site URL,",
        "// e.g. https://tenant.sharepoint.com/sites/YourSite",
        "let",
        "    Source = OData.Feed(",
        f"        SiteUrl & \"/_api/web/lists/getbytitle('{plan.list_title}')/items\"",
        f'            & "{query_string}"',
    ]
    if plan.expands:
        lines.append(f'            & "&$expand={",".join(plan.expands)}"')
    lines[-1] += ","
    lines += [
        "        null,",
        '        [Implementation = "2.0"]',
        "    ),",
    ]
    prev = "Source"
    for i, (record_col, inner, out) in enumerate(plan.record_expands, start=1):
        step = f"Expand{i}"
        lines.append(
            f'    {step} = Table.ExpandRecordColumn({prev}, "{record_col}", '
            f'{{"{inner}"}}, {{"{out}"}}),',
        )
        prev = step
    lines.append("    Typed = Table.TransformColumnTypes(")
    lines.append(f"        {prev},")
    lines.append("        {")
    for name, m_type in plan.m_types:
        lines.append(f'            {{"{name}", {m_type}}},')
    # M list literals do not allow a trailing comma.
    lines[-1] = lines[-1].rstrip(",")
    lines += [
        "        }",
        "    ),",
        '    WithItemURL = Table.AddColumn(',
        '        Typed, "ItemURL",',
        f'        each SiteUrl & "{plan.item_url_path}" & Number.ToText([Id]),',
        "        type text",
        "    )",
    ]
    if plan.renames:
        lines[-1] += ","
        lines += [
            "    // Model-facing names match the SharePoint display titles.",
            "    RenamedForModel = Table.RenameColumns(",
            "        WithItemURL,",
            "        {",
        ]
        lines += [
            f'            {{"{internal}", "{display}"}},'
            for internal, display in plan.renames
        ]
        lines[-1] = lines[-1].rstrip(",")
        lines += [
            "        },",
            "        MissingField.Ignore",
            "    )",
            "in",
            "    RenamedForModel",
            "",
        ]
    else:
        lines += [
            "in",
            "    WithItemURL",
            "",
        ]
    return "\n".join(lines)


def generate_powerquery(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> dict[str, str]:
    """One M query per list for the site role: {filename: query text}."""
    return {
        f"{plan.list_title}.pq": _render_m(plan)
        for plan in _build_plans(schema, bundle, site_role)
    }


# ------------------------------------------------------------------ SQL views


_SQL_HEADER = """\
-- Generated by dbml-sharepoint; regenerate rather than hand-edit.
-- T-SQL views over SharePoint list data landed in a warehouse.
-- Run in SQLCMD mode; point the variables at your landing/reporting schemas
-- and SiteUrl at the site the lists were deployed to (no trailing slash) —
-- it feeds the ItemURL helper column linking each row back to SharePoint.
-- Assumes each list lands as a table named after the list, with columns
-- named after the SharePoint internal column names (see REPORTING.md).
:setvar LandingSchema landing
:setvar ReportSchema rpt
:setvar SiteUrl https://yourtenant.sharepoint.com/sites/YourSite
GO
"""


def _render_sql_view(plan: _ListPlan) -> str:
    col_lines = [
        f"    CAST(t.[{name}] AS {sql_type}) AS [{name}]"
        for name, sql_type in plan.sql_columns
    ]
    col_lines.append(
        f"    CONCAT('$(SiteUrl){plan.item_url_path}', CAST(t.[Id] AS INT)) "
        "AS [ItemURL]",
    )
    cols = ",\n".join(col_lines)
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[vw_{plan.list_title}] AS\n"
        f"SELECT\n{cols}\n"
        f"FROM [$(LandingSchema)].[{plan.list_title}] AS t;\n"
        "GO\n"
    )


def _render_sql_enriched(plan: _ListPlan) -> str:
    select_lines = ["    t.*"]
    join_lines = []
    for i, (fk_col, target_title, display) in enumerate(plan.joins, start=1):
        alias = f"j{i}"
        out_col = fk_col.removesuffix("Id") + display
        select_lines.append(f"    {alias}.[{display}] AS [{out_col}]")
        join_lines.append(
            f"LEFT JOIN [$(ReportSchema)].[vw_{target_title}] AS {alias}\n"
            f"    ON t.[{fk_col}] = {alias}.[Id]",
        )
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[vw_{plan.list_title}_Enriched] AS\n"
        "SELECT\n" + ",\n".join(select_lines) + "\n"
        f"FROM [$(ReportSchema)].[vw_{plan.list_title}] AS t\n"
        + "\n".join(join_lines) + ";\n"
        "GO\n"
    )


def generate_sql_views(schema: Schema, bundle: MappingBundle, site_role: str) -> str:
    """A single SQLCMD script: typed view per list + _Enriched join views."""
    plans = _build_plans(schema, bundle, site_role)
    parts = [_SQL_HEADER]
    parts += [_render_sql_view(plan) for plan in plans]
    parts += [_render_sql_enriched(plan) for plan in plans if plan.joins]
    return "\n".join(parts)


# --------------------------------------------------------------- REPORTING.md


def generate_reporting_md(schema: Schema, bundle: MappingBundle, site_role: str) -> str:
    """Usage instructions + the Power BI relationship table."""
    plans = _build_plans(schema, bundle, site_role)
    lines = [
        "# Reporting queries",
        "",
        f"Generated by dbml-sharepoint for site role `{site_role}` "
        f"(list prefix `{bundle.mapping.prefix}`). Regenerate with "
        "`dbml-sharepoint report` after any schema change — these queries "
        "stay in lockstep with the deployed lists only if they are "
        "regenerated together.",
        "",
        "## Power Query (M) — Power BI Desktop / Excel",
        "",
        "1. **Manage Parameters → New parameter**: a *Text* parameter named "
        "`SiteUrl` holding the site URL, e.g. "
        "`https://tenant.sharepoint.com/sites/YourSite` (no trailing slash).",
        "2. For each `.pq` file: **Get Data → Blank Query → Advanced "
        "Editor**, paste the file contents, and rename the query to the "
        "list name (the first line of the file).",
        "3. When prompted to authenticate, choose **Organizational account** "
        "and sign in with an account that can read the lists.",
        "",
        "Each query returns a typed table with lookup and person columns "
        "already expanded to a join key (`…Id`) plus a display column.",
        "",
        "## Relationships (Power BI model)",
        "",
        "After loading the queries, create these many-to-one, "
        "single-direction relationships:",
        "",
        "| From table | From column | To table | To column |",
        "|---|---|---|---|",
    ]
    for plan in plans:
        for fk_col, target_title, _display in plan.joins:
            lines.append(
                f"| {plan.list_title} | {fk_col} | {target_title} | Id |",
            )
    lines += [
        "",
        "Person columns carry the site-user id (`…Id`) and display name "
        "(`…Title`) but no relationship target — the site user list is not "
        "part of this schema.",
        "",
        "## SQL views — warehouse landing zone",
        "",
        "`sql/views.sql` assumes each list has been landed (by any extract "
        "process — Azure Data Factory, Power Automate, Dataflows) as a "
        "table named after the list, columns named after the SharePoint "
        "internal names, in the `$(LandingSchema)` schema. Lookup columns "
        "land as `…Id` integers; person columns land as display-name text. "
        "Run the script in SQLCMD mode after adjusting `:setvar "
        "LandingSchema` / `:setvar ReportSchema`.",
        "",
        "Per list you get `vw_<List>` (typed casts) and, where the list has "
        "lookups, `vw_<List>_Enriched` (lookups joined to their display "
        "columns) — the horizontal, cross-list reporting layer.",
    ]
    lines += [
        "",
        "Both layers add an **ItemURL** helper column — the SharePoint "
        "display-form link for the row, built from the site URL, the list "
        "path and the item id — so any report visual can link straight "
        "back to the source item. `DATA-DICTIONARY.md` documents every "
        "list and column plus the deployment metadata behind this "
        "generation.",
        "",
        "## Data dictionary page (in-report)",
        "",
        "The dictionary also ships as loadable data so every report can "
        "carry its own documentation page: load `_DataDictionary.pq` and "
        "`_ModelInfo.pq` alongside the list queries (they are static "
        "`#table` literals — no connection, no refresh cost), add a report "
        "page with a table visual over `_DataDictionary` sorted by "
        "`SortOrder`, and a card or table over `_ModelInfo` for the "
        "release/schema provenance. SQL consumers get the same rows as "
        f"`vw_{bundle.mapping.prefix}DataDictionary` and "
        f"`vw_{bundle.mapping.prefix}ModelInfo` (built from embedded "
        "VALUES — no landing table needed).",
    ]
    lines += [
        "",
        "## User-added column audit",
        "",
        "Load `_UserAddedColumns.pq` alongside the dictionary queries. It "
        "reads each list's fields collection live on every refresh and "
        "returns the visible, deletable columns the schema does not "
        "declare — expected EMPTY. Any row is a column added outside this "
        "generation: investigate it before trusting the model. "
        "Extension-expanded cross-site columns (if any) can appear; "
        "recognise them once. SQL consumers get "
        f"`vw_{bundle.mapping.prefix}UserAddedColumns` over "
        "INFORMATION_SCHEMA — it sees only columns the extract process "
        "lands, and extractor-added audit columns (e.g. `LoadDate`) "
        "appear there as recognisable rows.",
    ]
    skipped = [
        (plan.list_title, name) for plan in plans for name in plan.skipped
    ]
    if skipped:
        lines += [
            "",
            "## Columns not included",
            "",
            "Cross-site reference columns are expanded at deploy time by the "
            "active extension into shapes this generator cannot know; add "
            "them to the queries by hand if needed:",
            "",
        ]
        lines += [f"- {title}: `{name}`" for title, name in skipped]
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------- Data dictionary


def _md_cell(text: str) -> str:
    """Make free text safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _sp_type_cell(
    sp: SPField,
    enum_members: dict[str, list[str]],
    formula: str | None,
    prefix: str,
) -> str:
    """Human-readable SharePoint type description for one column.

    Plain text — each renderer (markdown / M / SQL) applies its own
    escaping so the same rows can feed the document and the report-loadable
    dictionary tables.
    """
    match sp.kind:
        case "Skip":
            return "Counter (item ID)"
        case "Text":
            return f"Text ({sp.max_length})"
        case "Note":
            if sp.rich_text:
                return (
                    "Multi-line text (rich; HTML over OData — strip markup "
                    "for reporting)"
                )
            return "Multi-line text (plain)"
        case "Choice":
            # Declaration-order ordinals: Power BI sorts choice text
            # alphabetically; these feed sort-by-column mappings.
            members = enum_members.get(sp.choices_enum or "", [])
            return "Choice: " + ", ".join(
                f"{i}. {member}" for i, member in enumerate(members, 1)
            )
        case "Number":
            return "Number"
        case "DateTime":
            return "Date" if sp.date_only else "Date and time"
        case "Boolean":
            return "Yes/No"
        case "URL":
            return "Hyperlink"
        case "User":
            return "Person"
        case "Lookup":
            return f"Lookup → {prefix}{sp.target_list}"
        case "Calculated":
            output = {9: "Number", 4: "Date"}.get(sp.output_type or 0, "Text")
            if formula:
                return f"Calculated {output}: {formula}"
            return f"Calculated {output}"
    return sp.kind


def _column_rows_for_table(
    table: Table,
    bundle: MappingBundle,
    enum_names: set[str],
    enum_members: dict[str, list[str]],
    cross_site_keys: set[tuple[str, str]],
) -> list[tuple[str, str, str, str, str, str]]:
    """Plain-text dictionary rows for one table:
    (column, type, required, unique, default, description)."""
    formulas = bundle.mapping.calculated_formulas.get(table.name, {})
    rows: list[tuple[str, str, str, str, str, str]] = []
    for col in table.columns:
        if (table.name, col.name) in cross_site_keys:
            rows.append((
                col.name,
                "Cross-site reference (extension-expanded at deploy time)",
                "—", "—", "—",
                col.note or "—",
            ))
            continue
        sp = map_column(col, enum_names)
        name = "Id" if sp.kind == "Skip" else sp.name
        rows.append((
            name,
            _sp_type_cell(sp, enum_members, formulas.get(col.name), bundle.mapping.prefix),
            "yes" if sp.required else "—",
            "yes" if sp.unique else "—",
            str(sp.default) if sp.default is not None else "—",
            sp.description or (
                "SharePoint item identifier." if sp.kind == "Skip" else "—"
            ),
        ))
    return rows


def _metadata_rows(
    bundle: MappingBundle,
    site_role: str,
    list_count: int,
    release: Release | None,
    generated_at: str,
    source_schema: str,
    source_mapping: str,
) -> list[tuple[str, str]]:
    """Deployment/schema model metadata as plain (field, value) rows —
    shared by the DATA-DICTIONARY.md header and the _ModelInfo report table."""
    mapping = bundle.mapping
    rows = [
        ("Generated at", generated_at or "—"),
        ("Generator", f"dbml-sharepoint {__version__}"),
        ("Source schema", source_schema or "—"),
        ("Source mapping", source_mapping or "—"),
        (
            "List prefix",
            mapping.prefix
            + (f" (owner: {mapping.prefix_owner})" if mapping.prefix_owner else ""),
        ),
        ("Site role", site_role),
        ("Lists", str(list_count)),
    ]
    if release is not None:
        rows += [
            ("Release", f"{release.release_tag} ({release.date})"),
            ("Schema version", release.schema_version),
            ("Deployer version pin", release.deployer_version),
        ]
    else:
        rows.append((
            "Release",
            "— (regenerate with `--release` to stamp release metadata)",
        ))
    return rows


def generate_data_dictionary(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None = None,
    generated_at: str = "",
    source_schema: str = "",
    source_mapping: str = "",
) -> str:
    """Companion data dictionary: deployment/schema metadata + every list and
    column as deployed, including choices, lookup targets, calculated
    formulas, indexing, versioning and the query-layer helper columns."""
    tables = _tables_for_role(schema, bundle, site_role)
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = {
        (xref.entity, xref.column)
        for xref in bundle.mapping.cross_site_reference_columns
    }
    mapping = bundle.mapping
    prefix = mapping.prefix

    lines = [
        f"# Data dictionary — `{prefix}` (site role `{site_role}`)",
        "",
        "## Deployment / schema model metadata",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    lines += [
        f"| {field_name} | {_md_cell(value)} |"
        for field_name, value in _metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]

    for table in tables:
        entity = mapping.entities[table.name]
        list_title = prefix + table.name
        heading = (
            f"## {list_title} — entity `{table.name}` "
            f"({entity.kind}, template {entity.base_template}"
            + (", singleton" if entity.singleton else "")
            + ")"
        )
        lines += ["", heading, ""]
        if table.note:
            lines += [_md_cell(table.note), ""]
        lines += [
            "| Column | SharePoint type | Required | Unique | Default | Description |",
            "|---|---|---|---|---|---|",
        ]
        for name, type_cell, required, unique, default, description in (
            _column_rows_for_table(
                table, bundle, enum_names, enum_members, cross_site_keys,
            )
        ):
            lines.append(
                f"| {name} | {_md_cell(type_cell)} | {required} | {unique} | "
                f"{_md_cell(default)} | {_md_cell(description)} |",
            )
        details: list[str] = []
        indexed = mapping.indexed_columns.get(table.name, [])
        if indexed:
            details.append(f"Indexed columns: {', '.join(indexed)}.")
        v_override = mapping.versioning_overrides.get(table.name, {})
        v_default = mapping.versioning_default
        enable_versioning = bool(
            v_override.get("enable_versioning", v_default.enable_versioning),
        )
        if enable_versioning:
            limit = int(
                v_override.get("major_version_limit", v_default.major_version_limit),
            )
            minor = bool(
                v_override.get("enable_minor_versions", v_default.enable_minor_versions),
            )
            details.append(
                f"Versioning: major versions on, limit {limit}"
                + (", minor versions on" if minor else "")
                + ".",
            )
        else:
            details.append("Versioning: off.")
        lines += ["", " ".join(details)]

    lines += [
        "",
        "## Helper columns (query layer only)",
        "",
        "Added by every generated Power Query and SQL view; they are "
        "constructed at query time and do not exist on the lists:",
        "",
        "| Column | Construction | Purpose |",
        "|---|---|---|",
        "| ItemURL | SiteUrl + list form path + item id | Direct link from "
        "any report row back to the SharePoint item (display form) |",
        "| …Id / …Title (lookups, person) | `$select`/`$expand` of the "
        "lookup | Join key plus display column without a second query |",
        "",
    ]
    return "\n".join(lines)


# ----------------------------------------- Dictionary as report-loadable data


def _dictionary_rows(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> list[tuple[str, str, str, str, str, str, str]]:
    """(list, column, type, required, unique, default, description) for every
    column in the site role, in schema order."""
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = {
        (xref.entity, xref.column)
        for xref in bundle.mapping.cross_site_reference_columns
    }
    prefix = bundle.mapping.prefix
    rows: list[tuple[str, str, str, str, str, str, str]] = []
    for table in _tables_for_role(schema, bundle, site_role):
        for row in _column_rows_for_table(
            table, bundle, enum_names, enum_members, cross_site_keys,
        ):
            rows.append((prefix + table.name, *row))
    return rows


def _m_string(text: str) -> str:
    """An M string literal: double quotes are escaped by doubling."""
    return '"' + text.replace('"', '""') + '"'


def _render_m_table(
    query_name: str, purpose: str, type_spec: str, row_literals: list[str],
) -> str:
    lines = [
        f"// {query_name} — generated by dbml-sharepoint; regenerate rather "
        "than hand-edit.",
        f"// {purpose}",
        "let",
        "    Source = #table(",
        f"        type table [{type_spec}],",
        "        {",
    ]
    lines += [f"            {row}," for row in row_literals]
    lines[-1] = lines[-1].rstrip(",")
    lines += [
        "        }",
        "    )",
        "in",
        "    Source",
        "",
    ]
    return "\n".join(lines)


def _render_user_added_columns_m(plans: list[_ListPlan]) -> str:
    """The live drift-audit query: every visible, deletable field on the
    deployed lists that the schema does not declare. Expected EMPTY.

    Filtering happens IN M (Table.SelectRows), never OData $filter, so
    REST property filterability quirks cannot break the query. Per the
    documented CanBeDeleted contract, sealed fields and base-type
    built-ins return CanBeDeleted=false, so system columns drop out even
    before the declared-name anti-join.
    """
    if not plans:
        return "\n".join([
            "// _UserAddedColumns — generated by dbml-sharepoint; "
            "regenerate rather than hand-edit.",
            "// No lists in this site role.",
            "let",
            "    Source = #table(",
            "        type table [List = text, InternalName = text, "
            "DisplayName = text, Type = text],",
            "        {}",
            "    )",
            "in",
            "    Source",
            "",
        ])
    audit_calls = []
    for plan in plans:
        expected = ", ".join(
            _m_string(name)
            for name in dict.fromkeys(plan.field_internal_names + plan.skipped)
        )
        audit_calls.append(
            f"        Audit({_m_string(plan.list_title)}, {{{expected}}}),",
        )
    audit_calls[-1] = audit_calls[-1].rstrip(",")
    lines = [
        "// _UserAddedColumns — generated by dbml-sharepoint; regenerate "
        "rather than hand-edit.",
        "// Live drift audit: every visible, deletable column on the deployed",
        "// lists that the schema does not declare. Expected EMPTY — any row",
        "// is a column added outside this generation; investigate it.",
        "// Requires the same SiteUrl text parameter as the list queries.",
        "let",
        "    // Added by a tenant compliance feature outside operator",
        "    // control; a standing row here would erode the",
        "    // \"any row = investigate\" meaning of this table.",
        '    KnownTenantFields = {"ComplianceAssetId"},',
        "    Audit = (listTitle as text, expected as list) as table =>",
        "        let",
        "            Fields = OData.Feed(",
        "                SiteUrl & \"/_api/web/lists/getbytitle('\" & listTitle & \"')/fields\"",
        "                    & \"?$select=InternalName,Title,TypeAsString,"
        "Hidden,ReadOnlyField,CanBeDeleted\",",
        "                null,",
        '                [Implementation = "2.0"]',
        "            ),",
        "            UserAdded = Table.SelectRows(",
        "                Fields,",
        "                each not [Hidden] and not [ReadOnlyField] and [CanBeDeleted]",
        "                    and not List.Contains(expected, [InternalName])",
        "                    and not List.Contains(KnownTenantFields, [InternalName])",
        "            ),",
        "            Named = Table.RenameColumns(",
        "                Table.SelectColumns(UserAdded, "
        '{"InternalName", "Title", "TypeAsString"}),',
        '                {{"Title", "DisplayName"}, {"TypeAsString", "Type"}}',
        "            ),",
        '            Tagged = Table.AddColumn(Named, "List", each listTitle, type text)',
        "        in",
        "            Tagged,",
        "    Combined = Table.Combine({",
        *audit_calls,
        "    }),",
        '    Sorted = Table.Sort(Combined, {{"List", Order.Ascending}, '
        '{"InternalName", Order.Ascending}}),',
        '    Final = Table.ReorderColumns(Sorted, {"List", "InternalName", '
        '"DisplayName", "Type"})',
        "in",
        "    Final",
        "",
    ]
    return "\n".join(lines)


def generate_dictionary_powerquery(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None = None,
    generated_at: str = "",
    source_schema: str = "",
    source_mapping: str = "",
) -> dict[str, str]:
    """The data dictionary as report-loadable M queries, so any report can
    surface it as a page: _DataDictionary (one row per column), _ModelInfo
    (deployment/schema metadata as field/value rows) and _UserAddedColumns
    (live drift audit — undeclared columns on the deployed lists)."""
    dd_rows = [
        "{" + ", ".join([str(i)] + [_m_string(cell) for cell in row]) + "}"
        for i, row in enumerate(_dictionary_rows(schema, bundle, site_role), start=1)
    ]
    tables = _tables_for_role(schema, bundle, site_role)
    mi_rows = [
        "{" + _m_string(field_name) + ", " + _m_string(value) + "}"
        for field_name, value in _metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]
    return {
        "_DataDictionary.pq": _render_m_table(
            "_DataDictionary",
            "Load and add a report page with a table visual over this query "
            "(sorted by SortOrder) to surface the data dictionary in the report.",
            "SortOrder = Int64.Type, List = text, Column = text, Type = text, "
            "Required = text, Unique = text, Default = text, Description = text",
            dd_rows,
        ),
        "_ModelInfo.pq": _render_m_table(
            "_ModelInfo",
            "Deployment/schema model metadata for the report's data-dictionary "
            "page (release, schema version, sources, generation time).",
            "Field = text, Value = text",
            mi_rows,
        ),
        "_UserAddedColumns.pq": _render_user_added_columns_m(
            _build_plans(schema, bundle, site_role),
        ),
    }


def _sql_string(text: str) -> str:
    """An N'…' T-SQL literal: single quotes are escaped by doubling."""
    return "N'" + text.replace("'", "''") + "'"


def _render_sql_values_view(
    view_name: str, columns: list[str], row_literals: list[str],
) -> str:
    col_list = ", ".join(f"[{c}]" for c in columns)
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[{view_name}] AS\n"
        f"SELECT {col_list}\n"
        "FROM (VALUES\n"
        + ",\n".join(f"    ({row})" for row in row_literals)
        + f"\n) AS v({col_list});\n"
        "GO\n"
    )


def _render_user_added_columns_sql(plans: list[_ListPlan], prefix: str) -> str:
    """Drift-audit view over the landing schema: columns present on the
    landed tables that the schema does not declare. Sees only what the
    extract process lands (the M audit query is the live control);
    extractor-added audit columns (e.g. LoadDate) surface as recognisable
    rows."""
    if not plans:
        return ""
    table_list = ", ".join(_sql_string(plan.list_title) for plan in plans)
    expected_rows = []
    for plan in plans:
        names = ["Id"] + [name for name, _ in plan.sql_columns]
        for name in dict.fromkeys(names):
            expected_rows.append(
                f"    ({_sql_string(plan.list_title)}, {_sql_string(name)})",
            )
    return (
        f"CREATE OR ALTER VIEW [$(ReportSchema)].[vw_{prefix}UserAddedColumns] AS\n"
        "-- Drift audit: landed columns the schema does not declare. Expected\n"
        "-- EMPTY. Only sees columns the extract process lands.\n"
        "SELECT c.TABLE_NAME AS [List], c.COLUMN_NAME AS [Column],\n"
        "       c.DATA_TYPE AS [LandedType]\n"
        "FROM INFORMATION_SCHEMA.COLUMNS AS c\n"
        "WHERE c.TABLE_SCHEMA = '$(LandingSchema)'\n"
        f"  AND c.TABLE_NAME IN ({table_list})\n"
        "  AND NOT EXISTS (SELECT 1 FROM (VALUES\n"
        + ",\n".join(expected_rows)
        + "\n  ) AS d([List], [Column])\n"
        "  WHERE d.[List] = c.TABLE_NAME AND d.[Column] = c.COLUMN_NAME);\n"
        "GO\n"
    )


def generate_dictionary_sql(
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None = None,
    generated_at: str = "",
    source_schema: str = "",
    source_mapping: str = "",
) -> str:
    """The data dictionary as SQL views built from embedded VALUES rows (no
    landing table needed), so warehouse-driven reports can surface the same
    dictionary page."""
    prefix = bundle.mapping.prefix
    dd_rows = [
        ", ".join([str(i)] + [_sql_string(cell) for cell in row])
        for i, row in enumerate(_dictionary_rows(schema, bundle, site_role), start=1)
    ]
    tables = _tables_for_role(schema, bundle, site_role)
    mi_rows = [
        _sql_string(field_name) + ", " + _sql_string(value)
        for field_name, value in _metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]
    audit_view = _render_user_added_columns_sql(
        _build_plans(schema, bundle, site_role), prefix,
    )
    return (
        _render_sql_values_view(
            f"vw_{prefix}DataDictionary",
            ["SortOrder", "List", "Column", "Type",
             "Required", "Unique", "Default", "Description"],
            dd_rows,
        )
        + "\n"
        + _render_sql_values_view(
            f"vw_{prefix}ModelInfo", ["Field", "Value"], mi_rows,
        )
        + ("\n" + audit_view if audit_view else "")
    )


def emit_reporting(
    out: Path,
    schema: Schema,
    bundle: MappingBundle,
    site_role: str,
    *,
    release: Release | None,
    generated_at: str,
    source_schema: str,
    source_mapping: str,
) -> list[str]:
    """Write the reporting bundle under ``out/reporting/`` and return the
    POSIX relpaths written (for checksums.txt).

    Shared by the core and extension CLIs so the shipped reporting
    artifact set cannot drift between them: per-list Power Query (M)
    plus the dictionary/model/audit queries, the SQL views script,
    REPORTING.md and data-dictionary.md.
    """
    reporting_dir = out / "reporting"
    pq_dir = reporting_dir / "powerquery"
    sql_dir = reporting_dir / "sql"
    pq_dir.mkdir(parents=True, exist_ok=True)
    sql_dir.mkdir(parents=True, exist_ok=True)
    dictionary_kwargs: dict[str, Any] = dict(
        release=release,
        generated_at=generated_at,
        source_schema=source_schema,
        source_mapping=source_mapping,
    )
    relpaths: list[str] = []
    queries = generate_powerquery(schema, bundle, site_role)
    queries.update(
        generate_dictionary_powerquery(schema, bundle, site_role, **dictionary_kwargs),
    )
    for filename, content in queries.items():
        (pq_dir / filename).write_text(content, encoding="utf-8")
        relpaths.append(f"reporting/powerquery/{filename}")
    (sql_dir / "views.sql").write_text(
        generate_sql_views(schema, bundle, site_role)
        + "\n"
        + generate_dictionary_sql(schema, bundle, site_role, **dictionary_kwargs),
        encoding="utf-8",
    )
    (reporting_dir / "REPORTING.md").write_text(
        generate_reporting_md(schema, bundle, site_role), encoding="utf-8",
    )
    (reporting_dir / "data-dictionary.md").write_text(
        generate_data_dictionary(schema, bundle, site_role, **dictionary_kwargs),
        encoding="utf-8",
    )
    relpaths += [
        "reporting/sql/views.sql",
        "reporting/REPORTING.md",
        "reporting/data-dictionary.md",
    ]
    return relpaths
