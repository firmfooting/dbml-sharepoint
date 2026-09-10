# src/dbml_sharepoint/analysis/reporting/dictionary.py
"""The data dictionary's rows, as plain text.

Every cell here is unescaped prose. The markdown page, the `_DataDictionary`
query and the `vw_<prefix>DataDictionary` view all read the same rows, and
each renderer applies its own escaping (`_md_cell`, `_m_string`,
`_sql_string`), so the dictionary cannot say one thing on the page and
another in the model.

The users dimension's column vocabulary lives here for the same reason: the
query that reads the list and the rows that describe it come from one
table.
"""

from dbml_sharepoint import __version__
from dbml_sharepoint.analysis.condition_description import describe
from dbml_sharepoint.analysis.derived import derived_output_names
from dbml_sharepoint.analysis.exports import MULTI_VALUE_JOIN
from dbml_sharepoint.analysis.report_columns import (
    REPORT_KEY_SUFFIX,
    REPORT_SYSTEM_COLUMNS,
    USERS_DISPLAY_TITLES,
    USERS_KEY_LIST,
)
from dbml_sharepoint.analysis.reporting.plan import (
    refuse_ambiguous_members,
    tables_for_role,
)
from dbml_sharepoint.analysis.typemap import SPField, map_column
from dbml_sharepoint.model.mapping_types import DerivedColumn, MappingBundle
from dbml_sharepoint.model.parser import Schema, Table
from dbml_sharepoint.model.release import Release

#: (internal name, M type, model-facing name) for the users dimension. The
#: internal names are the user information list's own, MEASURED 2026-09-02.
#: (internal name, M type, model-facing name). The third is read off
#: `USERS_DISPLAY_TITLES` rather than restated, because a derived `lookup`
#: into `_Users` translates its picked columns through that map and the two
#: spellings must be one.
USERS_COLUMNS: tuple[tuple[str, str, str], ...] = tuple(
    (name, m_type, USERS_DISPLAY_TITLES[name])
    for name, m_type in (
        ("Id", "Int64.Type"),
        ("Title", "type text"),
        ("EMail", "type text"),
        ("UserName", "type text"),
        ("Department", "type text"),
        ("JobTitle", "type text"),
        ("Office", "type text"),
        ("Deleted", "type logical"),
    )
)

#: ContentTypeId prefixes on the user information list, MEASURED 2026-09-02.
PRINCIPAL_KINDS: tuple[tuple[str, str], ...] = (
    ("0x010A", "Person"),
    ("0x010B", "SharePoint group"),
    ("0x010C", "Domain group"),
)


def _sp_type_cell(
    sp: SPField,
    enum_members: dict[str, list[str]],
    formula: str | None,
    prefix: str,
) -> str:
    """Human-readable SharePoint type description for one column.

    Plain text. Each renderer (markdown / M / SQL) applies its own
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
                    "Multi-line text (rich; HTML over OData, so strip markup "
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
        case "MultiChoice":
            # `MultiChoice` is this codebase's token for FieldTypeKind 15, and
            # the raw token is what a fall-through printed here, into the one
            # column a report author reads to find out what a column IS.
            #
            # Same declaration-order ordinals as Choice, and then how the
            # export spells a set, because this page is where somebody looking
            # at one text cell holding several members finds out that it is
            # several members and what to split on.
            members = enum_members.get(sp.choices_enum or "", [])
            # The dictionary is the one entry point that never builds a plan,
            # so the plan builder's guard does not cover it. It is also the
            # page that tells a reader to split on the separator.
            refuse_ambiguous_members(sp.name, members)
            joined = ", ".join(
                f"{i}. {member}" for i, member in enumerate(members, 1)
            )
            # Says WHICH export joins them. The Power Query one does, in a
            # step this generator writes. The SQL views do not: they cast
            # whatever the extract process landed, and this module never sees
            # that process. Telling a warehouse reader the members "are"
            # joined by "; " would state as fact something no part of the SQL
            # path performs -- guide.md carries the landing contract.
            return (
                f"Choice (multiple): {joined} (a set of members; the Power "
                f"Query export joins them into one text cell separated by "
                f'"{MULTI_VALUE_JOIN}")'
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
            return f"Lookup -> {prefix}{sp.target_list}"
        case "LookupMulti":
            # Says what the cell holds and what to split on, like the
            # MultiChoice arm, and says IDS because that is what the export
            # lands: this column takes no $expand, so no title comes back
            # with it.
            return (
                f"Lookup (multiple) -> {prefix}{sp.target_list} (a set of "
                f"item ids; the Power Query export joins them into one text "
                f'cell separated by "{MULTI_VALUE_JOIN}")'
            )
        case "Calculated":
            output = {9: "Number", 4: "Date"}.get(sp.output_type or 0, "Text")
            if formula:
                return f"Calculated {output}: {formula}"
            return f"Calculated {output}"
    # `generate_data_dictionary` is the ONE entry point in this module that
    # never goes through `build_plans`, so the `case _` that guards the
    # queries does not cover this page. Ending `return sp.kind` published the
    # internal token instead: a reader of data-dictionary.md would be told a
    # column's SharePoint type is "MultiChoice", which is this codebase's word
    # and not one that appears anywhere in a SharePoint UI, in the one place
    # they went to look it up -- and nothing in the build could see it.
    #
    # The loadable tables are covered incidentally, because both their entry
    # points also build `_UserAddedColumns` and so hit `build_plans` first.
    # That is not a guard, it is a coincidence of ordering, and this is.
    raise ValueError(
        f"{sp.name}: the data dictionary has no description for SharePoint "
        f"field kind {sp.kind!r}. Add an arm to _sp_type_cell saying what a "
        f"report author should understand the column to be, rather than "
        f"printing an internal token into data-dictionary.md and the "
        f"dictionary tables loaded beside it.",
    )


def _form_behaviour_cells(
    table_name: str, column: str, bundle: MappingBundle,
) -> tuple[str, str]:
    """(populated when, save rule) for one column, in prose.

    Described through `describe()`, never in a target's syntax. This is the
    artefact a report author reads, and `[$ID] != ''` tells them nothing.
    It is a SharePoint list-formatting expression they would first have to
    identify as one. The declaration is theirs to understand; the mechanism
    carrying it is not.
    """
    populated = "-"
    section = bundle.mapping.form_visibility.get(table_name)
    declared = section.columns.get(column) if section else None
    if declared is not None:
        when = describe(declared.when) if declared.when is not None else ""
        if not declared.new and not declared.existing:
            populated = "Never on a form"
        elif not declared.new:
            populated = "Only after creation" + (f", and when {when}" if when else "")
        elif not declared.existing:
            populated = "Only at creation" + (f", and when {when}" if when else "")
        elif when:
            populated = f"When {when}"
        else:
            populated = "Always"

    rule = "-"
    cv_section = bundle.mapping.column_validation.get(table_name)
    cv = cv_section.columns.get(column) if cv_section else None
    if cv is not None:
        rule = f"{describe(cv.when)}: {cv.message}"
    return populated, rule


def column_rows_for_table(
    table: Table,
    bundle: MappingBundle,
    enum_names: set[str],
    enum_members: dict[str, list[str]],
    cross_site_keys: set[tuple[str, str]],
) -> list[tuple[str, str, str, str, str, str, str, str, str, str]]:
    """Plain-text dictionary rows for one table: (column, type, required,
    unique, default, retired, superseded by, populated when, save rule,
    description).

    Retired columns are still listed, and the generated list queries still
    select them: history is the entire point of retiring rather than
    deleting.
    """
    formulas = bundle.mapping.calculated_formulas.get(table.name, {})
    retired = bundle.mapping.retired_columns.get(table.name, {})
    rows: list[tuple[str, str, str, str, str, str, str, str, str, str]] = []
    for col in table.columns:
        populated, rule = _form_behaviour_cells(table.name, col.name, bundle)
        spec = retired.get(col.name)
        # The bare-list declaration form carries no date; "yes" still says
        # the column is retired.
        retired_cell = (spec.retired or "yes") if spec is not None else "-"
        superseded_cell = (spec.superseded_by or "-") if spec is not None else "-"
        if (table.name, col.name) in cross_site_keys:
            rows.append((
                col.name,
                "Cross-site reference (extension-expanded at deploy time)",
                "-", "-", "-",
                retired_cell, superseded_cell, populated, rule,
                col.note or "-",
            ))
            continue
        sp = map_column(col, enum_names)
        name = "Id" if sp.kind == "Skip" else sp.name
        rows.append((
            name,
            _sp_type_cell(sp, enum_members, formulas.get(col.name), bundle.mapping.prefix),
            "yes" if sp.required else "-",
            "yes" if sp.unique else "-",
            str(sp.default) if sp.default is not None else "-",
            retired_cell,
            superseded_cell,
            populated,
            rule,
            sp.description or (
                "SharePoint item identifier." if sp.kind == "Skip" else "-"
            ),
        ))
    for column, targets in bundle.mapping.lookup_projections.get(table.name, {}).items():
        for target in targets:
            rows.append((
                f"{column}{target}",
                "Lookup (read-only dependent)",
                "-", "-", "-", "-", "-", "Always", "-",
                f"Read-only dependent of {column}, showing the target's {target}.",
            ))
    # Reporting-only, and said so in the type cell: a reader looking for one
    # of these on the list will not find it, and the dictionary is where
    # they would look.
    for entry in bundle.mapping.derived_for(table.name):
        for name in derived_output_names(entry):
            rows.append((
                name,
                _derived_type_cell(entry),
                "-", "-", "-", "-", "-", "Always", "-",
                entry.description or _derived_default_description(entry, name),
            ))
    if bundle.mapping.reporting.system_columns:
        rows += _system_column_rows()
    return rows


def _derived_type_cell(entry: DerivedColumn) -> str:
    """The dictionary's type cell for a derived column, which has to say the
    column exists only in the report before it says what type it is."""
    kind = {
        "expr": "computed per row",
        "lookup": "read from another list",
        "count": "aggregated from a child list",
    }[entry.kind]
    return f"Reporting only ({kind})"


def _derived_default_description(entry: DerivedColumn, name: str) -> str:
    """What a derived column does, where its author wrote no description."""
    if entry.kind == "lookup":
        source = entry.pick[name]
        return (
            f"{source} read from the matching {entry.from_entity} row, "
            f"through the report's own keys."
        )
    if entry.kind == "count":
        subject = (
            "rows" if entry.aggregate == "count"
            else f"{entry.column} over the rows"
        )
        return (
            f"The {entry.aggregate} of {subject} of {entry.from_entity} "
            f"pointing at this one through {entry.via}."
        )
    return "Computed in the report query; no SharePoint column behind it."


def _system_column_rows() -> list[tuple[str, str, str, str, str, str, str, str, str, str]]:
    """Dictionary rows for the system columns, in the query's order. They
    exist on every list, so they belong beside the list's own columns rather
    than in the query-layer helper table."""
    described = {
        "Author": ("Person (system: Created By)", "Who created the item."),
        "Created": ("Date and time (system)", "When the item was created."),
        "Editor": ("Person (system: Modified By)", "Who last modified the item."),
        "Modified": ("Date and time (system)", "When the item was last modified."),
    }
    return [
        (name, described[name][0], "-", "-", "-", "-", "-", "Always", "-", described[name][1])
        for name in REPORT_SYSTEM_COLUMNS
    ]


def metadata_rows(
    bundle: MappingBundle,
    site_role: str,
    list_count: int,
    release: Release | None,
    generated_at: str,
    source_schema: str,
    source_mapping: str,
) -> list[tuple[str, str]]:
    """Deployment/schema model metadata as plain (field, value) rows,
    shared by the data-dictionary.md header and the _ModelInfo report table."""
    mapping = bundle.mapping
    rows = [
        ("Generated at", generated_at or "-"),
        ("Generator", f"dbml-sharepoint {__version__}"),
        ("Source schema", source_schema or "-"),
        ("Source mapping", source_mapping or "-"),
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
            "- (regenerate with `--release` to stamp release metadata)",
        ))
    return rows


def dictionary_rows(
    schema: Schema, bundle: MappingBundle, site_role: str,
) -> list[tuple[str, str, str, str, str, str, str, str, str, str, str]]:
    """(list, column, type, required, unique, default, retired, superseded
    by, populated when, save rule, description) for every column in the site
    role, in schema order."""
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = bundle.mapping.cross_site_keys()
    prefix = bundle.mapping.prefix
    rows: list[tuple[str, str, str, str, str, str, str, str, str, str, str]] = []
    for table in tables_for_role(schema, bundle, site_role):
        for row in column_rows_for_table(
            table, bundle, enum_names, enum_members, cross_site_keys,
        ):
            rows.append((prefix + table.name, *row))
    if bundle.mapping.reporting.users_table:
        rows += [(USERS_KEY_LIST, *row) for row in users_dictionary_rows()]
    return rows


def users_dictionary_rows() -> list[tuple[str, str, str, str, str, str, str, str, str, str]]:
    """Dictionary rows for the `_Users` dimension, in its column order."""
    described = [
        ("Id", "Counter (site user id)",
         "The site user id a person column carries as `...Id`."),
        ("Name", "Text (system)", "Display name."),
        ("Email", "Text (system)", "Work email, when the profile carries one."),
        ("Account", "Text (system)", "Account name, when the profile carries one."),
        ("Department", "Text (system)",
         "From the user profile, synced from Microsoft Entra; blank until synced."),
        ("Job Title", "Text (system)",
         "From the user profile, synced from Microsoft Entra; blank until synced."),
        ("Office", "Text (system)", "From the user profile; blank until synced."),
        ("Deleted", "Yes/No (system)",
         "Set once the account has left the site; the row stays so older items still resolve."),
        ("Principal Kind", "Derived from ContentTypeId",
         "Person, SharePoint group, Domain group or Other."),
        (f"User{REPORT_KEY_SUFFIX}", f"Site Url, `{USERS_KEY_LIST}` and the id",
         "The join target for every `... Key` a person column carries."),
    ]
    return [
        (name, type_cell, "-", "-", "-", "-", "-", "Always", "-", description)
        for name, type_cell, description in described
    ]
