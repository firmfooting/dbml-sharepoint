# src/dbml_sharepoint/generators/report_md.py
"""The two markdown documents of the reporting pack.

``guide.md`` carries the usage instructions and the Power BI relationship
table derived from the DBML refs; ``data-dictionary.md`` carries the
deployment metadata and every list and column as deployed. Both return
markdown text, and every free-text cell that reaches a table goes through
:func:`_md_cell`. What the pages SAY about the queries is read off
``analysis/reporting/plan.py`` and ``analysis/reporting/dictionary.py``;
this module only writes it down.

Cross-site reference columns are extension-expanded at deploy time into
shapes the core cannot know; they are skipped by the queries and listed
in ``guide.md``.
"""

from dbml_sharepoint.analysis.exports import MULTI_VALUE_JOIN
from dbml_sharepoint.analysis.lookups import lookup_display_columns
from dbml_sharepoint.analysis.report_columns import (
    DATE_ZONE_RESOLVED_COLUMN,
    ITEM_URL_RESOLVED_COLUMN,
    REPORT_KEY_SUFFIX,
    USERS_KEY_LIST,
    fk_key_column,
    person_key_column,
)
from dbml_sharepoint.analysis.reporting.dictionary import (
    column_rows_for_table,
    metadata_rows,
    users_dictionary_rows,
)
from dbml_sharepoint.analysis.reporting.plan import build_plans, tables_for_role
from dbml_sharepoint.analysis.timezones import WINDOW_END, WINDOW_START, zone_table
from dbml_sharepoint.analysis.typemap import CALCULATED_TYPES
from dbml_sharepoint.generators._indexes import deployable_index_columns
from dbml_sharepoint.model.mapping_types import MappingBundle
from dbml_sharepoint.model.parser import Schema
from dbml_sharepoint.model.release import Release


def _date_zone_guide_paragraphs(time_zone: str | None) -> list[str]:
    """What the guide says about `DateZoneResolved`, and about the declared
    zone's helpers where there is one."""
    if time_zone is None:
        return [
            (f"A list with a date-only column also carries "
             f"**{DATE_ZONE_RESOLVED_COLUMN}**, for the same reason. A "
             "date-only value is site-local midnight served as a UTC "
             "instant, so the query reads the site's time zone to turn it "
             "back into the date the list shows. That read fails soft too, "
             "and without it those columns truncate in UTC and read a day "
             "early east of UTC."),
        ]
    table = zone_table(time_zone)
    return [
        (f"Every list carries **{DATE_ZONE_RESOLVED_COLUMN}**, for the same "
         "reason. A date-only value is site-local midnight served as a UTC "
         "instant, so the query reads the site's time zone to turn it back "
         "into the date the list shows. That read fails soft too, and "
         "without it those columns truncate in UTC and read a day early "
         "east of UTC. The mapping declares the site's zone as "
         f"`{time_zone}`, so the flag is also false when the zone the site "
         "reports does not agree with it, which means the offsets the site "
         "reports are not exactly the ones that zone uses under its current "
         "rule: a pack built for one zone and refreshed against a site set "
         "to another says so on every row rather than converting timestamps "
         "by the wrong rule."),
        "",
        (f"Each list query also carries `{time_zone}`'s daylight-saving "
         f"transitions ({len(table.transitions)} rows, "
         f"{WINDOW_START:%Y-%m-%d} to {WINDOW_END:%Y-%m-%d}), generated from "
         "the IANA database when the pack was built, and two helpers over "
         "them: `AsSiteDateTime` turns a UTC timestamp such as `Created` "
         "into the site's local date and time, and `AsSiteDate` into its "
         "local date. Power Query has no time zone database of its own and "
         "SharePoint does not serve the transition dates, which is why they "
         "ship in the query. Regenerate the pack when the zone's rules "
         "change. A date-only column needs neither: its value is local "
         "midnight already, and the query resolves the offset from that."),
    ]


def _users_guide_paragraphs() -> list[str]:
    """What the guide says about `_Users` and the person keys, once."""
    return [
        (f"Person columns carry the site-user id (`...Id`), the display name "
         f"(`...Title`) and a `... Key` that joins **`{USERS_KEY_LIST}`** "
         "(`reporting.users_table` in the mapping): the site's user "
         "information list as one row per person, SharePoint group or "
         "domain group the site has ever resolved, with name, email, "
         "account, department, job title, office, a deleted flag and the "
         "principal kind. Department and job title come from the user "
         "profile and are blank until it has synced."),
        "",
        ("**Power BI allows one active relationship between two tables.** "
         "A list with several person columns therefore gets one active "
         f"relationship to `{USERS_KEY_LIST}` and the rest inactive. Either "
         "reach the inactive ones from measures with `USERELATIONSHIP`, or "
         f"reference `{USERS_KEY_LIST}` once per role (right-click, "
         "*Reference*, rename the copy to `Responsible User` and so on) and "
         "give each copy its own active relationship, which is what "
         "Microsoft recommends when a visual has to slice by more than one "
         "role at once."),
        "",
        ("Site user ids are per site collection, so `User Key` carries the "
         "site and the same person on two sites is two rows; the email is "
         "on the row for anyone who needs a cross-site people table. The "
         "list was read by a site admin when this was measured; a 403 on "
         "refresh means the reporting (reader) account needs read access "
         "to the site's user information list."),
    ]


def generate_reporting_md(
    schema: Schema, bundle: MappingBundle, site_role: str,
    *,
    site_url: str | None = None,
) -> str:
    """Usage instructions + the Power BI relationship table.

    ``site_url`` must be passed whenever the queries beside this guide were
    built with it: the setup step it documents is the difference between
    "create a parameter" and "there is nothing to create", and a guide that
    is wrong about that costs the operator the whole first hour.
    """
    plans = build_plans(schema, bundle, site_role)
    system_columns = bundle.mapping.reporting.system_columns
    users_table = bundle.mapping.reporting.users_table
    setup_step = (
        ("1. **Manage Parameters -> New parameter**: a *Text* parameter named "
         "`SiteUrl` holding the **site** URL, e.g. "
         "`https://tenant.sharepoint.com/sites/YourSite` (no trailing slash). "
         "That is the site, not a list or a page. Note the address bar shows the "
         "*list* URL (`.../Lists/YourList`) while you are looking at a list; "
         "each query trims that back to the site for you, so a pasted list, "
         "form, page or API URL still works.")
        if site_url is None else
        ("1. **Nothing to configure.** Each query already carries the site it "
         f"was built for (`{site_url}`) as its first line. See *Reporting on "
         "several sites at once* below to point a copy somewhere else.")
    )
    combine_steps = (
        [("1. Add one text parameter per site: `SiteUrl_North`, "
          "`SiteUrl_South`, and so on."),
         ("2. Duplicate each list query once per site (*right-click -> "
          "Duplicate*) and change `SiteUrl` in the duplicate to that site's "
          "parameter. Nothing else needs editing: the rows, the item links, "
          "the site name and the keys all follow that one reference.")]
        if site_url is None else
        [("1. Duplicate each list query once per site (*right-click -> "
          "Duplicate*)."),
         ("2. In each duplicate, change the one `SiteUrl = \"...\"` line to "
          "that site's URL, or replace it with a text parameter per site "
          "if you would rather manage them in one place. Nothing else needs "
          "editing: the rows, the item links, the site name and the keys "
          "all follow that one line.")]
    )
    lines = [
        "# Reporting queries",
        "",
        (f"Generated by dbml-sharepoint for site role `{site_role}` "
         f"(list prefix `{bundle.mapping.prefix}`). Regenerate with "
         "`dbml-sharepoint report` after any schema change. These queries "
         "stay in lockstep with the deployed lists only if they are "
         "regenerated together."),
        "",
        "## Power Query (M): Power BI Desktop / Excel",
        "",
        setup_step,
        ("2. For each `.pq` file: **Get Data -> Blank Query -> Advanced "
         "Editor**, paste the file contents, and rename the query to the "
         "list name (the first line of the file)."),
        ("3. When prompted to authenticate, choose **Organizational account** "
         "and sign in with an account that can read the lists."),
        "",
        ("Each query returns a typed table with lookup and person columns "
         "already expanded to a join key (`...Id`) plus a display column."),
        "",
        "## Reporting on several sites at once",
        "",
        ("This template is deployed one site at a time, but a report often "
         "needs all of them together: every region, service or committee "
         "running the same lists, in one model, sliced by site."),
        "",
        ("Every table already carries **`Site Url`**, **`Site Name`** and "
         "**`List Title`** for that, so a model that appends several "
         "deployments can slice by site and by list. The site name is read "
         "from the site's own title at refresh time, so nothing has to be "
         "typed in and a site renamed in SharePoint shows its new name at "
         "the next refresh."),
        "",
        ("Each query works that out for itself, from whichever URL it was "
         "given. That is deliberate: a single shared site-name query would "
         "bind to one `SiteUrl`, and every copy of a list pointed at a "
         "different site would still be stamped with the FIRST site's name."),
        "",
        "To combine deployments:",
        "",
        *combine_steps,
        ("3. **Append** the copies of a list into one table (*Home -> Append "
         "Queries as New*)."),
        ("4. Build the relationships below on the **Key** columns, not on "
         "`Id`."),
        "",
        (">  **`Id` is unique within one list on one site, and nowhere "
         "wider.** Append three sites and three different rows all have "
         "`Id = 1`, and so do the first rows of any two lists on a single "
         "site, because every list numbers its items from 1. A relationship "
         "on `Id` cannot then be many-to-one; Power BI degrades it to "
         "many-to-many and joins each child to the same-numbered parent "
         "everywhere. The report still renders. The numbers are just "
         "wrong. The `... Key` columns are `Site Url`, the **list title** and "
         "the id together, which is unique across any number of sites and "
         "lists, and they are why the relationships below are safe to "
         "append."),
        "",
        "## Relationships (Power BI model)",
        "",
        ("After loading the queries, create these many-to-one, "
         "single-direction relationships:"),
        "",
        "| From table | From column | To table | To column |",
        "|---|---|---|---|",
    ]
    for plan in plans:
        for fk_col, target_title, _display, _proj in plan.joins:
            target_entity = next(
                (p.entity for p in plans if p.list_title == target_title),
                target_title,
            )
            lines.append(
                f"| {plan.list_title} | {fk_key_column(fk_col)} "
                f"| {target_title} | {target_entity} Key |",
            )
        if plan.users_table:
            for name in plan.person_columns:
                lines.append(
                    f"| {plan.list_title} | {person_key_column(name)} "
                    f"| {USERS_KEY_LIST} | User{REPORT_KEY_SUFFIX} |",
                )
    lines += [
        "",
        *(_users_guide_paragraphs() if users_table else [
            ("Person columns carry the site-user id (`...Id`) and display "
             "name (`...Title`) but no relationship target. The site user "
             "list is not part of this schema."),
        ]),
        *(
            ["",
             ("Every list also carries SharePoint's **Created By**, "
              "**Created**, **Modified By** and **Modified** "
              "(`reporting.system_columns` in the mapping), after its own "
              "columns and in the same shape as a declared person or "
              "date-time column.")]
            if system_columns else []
        ),
        "",
        "## SQL views: warehouse landing zone",
        "",
        ("`sql/views.sql` assumes each list has been landed (by any extract "
         "process: Azure Data Factory, Power Automate, Dataflows) as a "
         "table named after the list, columns named after the SharePoint "
         "internal names, in the `$(LandingSchema)` schema. Lookup columns "
         "land as `...Id` integers; person columns land as display-name text. "
         + ("With `reporting.system_columns` on, each landed table must also "
            "carry `Author`, `Editor`, `Created` and `Modified`; a missing "
            "one fails the view by name rather than silently. "
            if system_columns else "")
         + "Run the script in SQLCMD mode after adjusting `:setvar "
         "LandingSchema` / `:setvar ReportSchema`."),
        "",
        ("**Multi-value choice columns are a landing contract, not a "
         "transform.** The Power Query queries join a set into one text cell "
         f'separated by `\"{MULTI_VALUE_JOIN}\"`, in a step written into the '
         "`.pq` file. The SQL views do not: they `CAST` whatever the extract "
         "landed, as `NVARCHAR(MAX)` so nothing is truncated in silence. "
         "Your extract must therefore land such a column as text, and the "
         "text it lands is the text your reports will read: SharePoint's "
         "own `;#`-delimited string, a JSON array, or the same "
         f'`\"{MULTI_VALUE_JOIN}\"` join, depending on the extractor. Match '
         "it to the Power Query separator if the two layers are to agree, or "
         "record which one your warehouse uses; this generator cannot see "
         "the extract and does not guess."),
        "",
        ("Per list you get `vw_<List>` (typed casts) and, where the list has "
         "lookups, `vw_<List>_Enriched` (lookups joined to their display "
         "columns), the horizontal, cross-list reporting layer."),
    ]
    lines += [
        "",
        ("Both layers add an **ItemURL** helper column (the SharePoint "
         "display-form link for the row), so any report visual can link "
         "straight back to the source item. The Power Query reads each "
         "list's own folder at refresh, so a list renamed in place still "
         "links correctly; the SQL views have no site to read and build the "
         "path from the declared title, which is a dead link for such a "
         "list. `data-dictionary.md` documents every list and column plus "
         "the deployment metadata behind this generation."),
        "",
        (f"The Power Query carries **{ITEM_URL_RESOLVED_COLUMN}** beside it, "
         "because that folder read fails soft: a permission that grants "
         "items but not the folder, a throttled call or a transient 503 all "
         "leave the refresh reporting success while every link in the table "
         "points at the declared title. Where the links matter, hide them on "
         f"the rows where {ITEM_URL_RESOLVED_COLUMN} is false rather than "
         "shipping a 404."),
        "",
        ("Where the mapping declares them, each query also carries "
         "**reporting-only columns**: flags, aggregates over a child list, "
         "and columns read from a related list, computed in the query and "
         "backed by no SharePoint field. `data-dictionary.md` marks each "
         "one, and the SQL views do not carry them."),
        "",
        ":::warning Load each query under the name of its file",
        ("A query that reads another list names it, so `GOV_Risk.pq` must "
         "be loaded as `GOV_Risk` for a query that reads it to resolve. "
         "Renaming a query breaks every derived column that reads it, at "
         "refresh. Appending several sites needs the same care: a "
         "duplicated query still reads the ORIGINAL copy of whatever it "
         "joins, so point each duplicate at its own copies. A count that "
         "finds itself reading another site's rows reports blank rather "
         "than zero, which is why the blank is worth checking."),
        ":::",
        "",
        *_date_zone_guide_paragraphs(bundle.mapping.reporting.time_zone),
        "",
        "## Data dictionary page (in-report)",
        "",
        ("The dictionary also ships as loadable data so every report can "
         "carry its own documentation page: load `_DataDictionary.pq` and "
         "`_ModelInfo.pq` alongside the list queries (they are static "
         "`#table` literals with no connection and no refresh cost), add a report "
         "page with a table visual over `_DataDictionary` sorted by "
         "`SortOrder`, and a card or table over `_ModelInfo` for the "
         "release/schema provenance. SQL consumers get the same rows as "
         f"`vw_{bundle.mapping.prefix}DataDictionary` and "
         f"`vw_{bundle.mapping.prefix}ModelInfo` (built from embedded "
         "VALUES, with no landing table needed)."),
    ]
    lines += [
        "",
        "## User-added column audit",
        "",
        ("Load `_UserAddedColumns.pq` alongside the dictionary queries. It "
         "reads each list's fields collection live on every refresh and "
         "returns the visible, deletable columns the schema does not "
         "declare. Expected EMPTY. Any row is a column added outside this "
         "generation: investigate it before trusting the model. "
         "Extension-expanded cross-site columns (if any) can appear; "
         "recognise them once. SQL consumers get "
         f"`vw_{bundle.mapping.prefix}UserAddedColumns` over "
         "INFORMATION_SCHEMA, which sees only columns the extract process "
         "lands, and extractor-added audit columns (e.g. `LoadDate`) "
         "appear there as recognisable rows."),
    ]
    skipped = [
        (plan.list_title, name) for plan in plans for name in plan.skipped
    ]
    if skipped:
        lines += [
            "",
            "## Columns not included",
            "",
            ("Cross-site reference columns are expanded at deploy time by the "
             "active extension into shapes this generator cannot know; add "
             "them to the queries by hand if needed:"),
            "",
        ]
        lines += [f"- {title}: `{name}`" for title, name in skipped]
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------- Data dictionary


def _md_cell(text: str) -> str:
    """Make free text safe inside a markdown table cell."""
    return text.replace("|", "\\|").replace("\n", " ")


def _date_zone_dictionary_row(time_zone: str | None) -> str:
    """The helper-column row for `DateZoneResolved`, which means one thing
    more once the mapping declares the site's zone."""
    if time_zone is None:
        return (
            f"| {DATE_ZONE_RESOLVED_COLUMN} | Whether the site's time zone was "
            "read at refresh (only on lists that have a date-only column) "
            "| False means date-only columns were truncated in UTC and may be "
            "a day early east of UTC |"
        )
    return (
        f"| {DATE_ZONE_RESOLVED_COLUMN} | Whether the site's time zone was "
        f"read at refresh and agrees with the declared `{time_zone}` "
        "| False means date-only columns were truncated in UTC and may be a "
        "day early east of UTC, or the site is set to a zone other than the "
        "one the pack's timestamp conversions were built for |"
    )


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
    tables = tables_for_role(schema, bundle, site_role)
    enum_names = {e.name for e in schema.enums}
    enum_members = {e.name: e.members for e in schema.enums}
    cross_site_keys = bundle.mapping.cross_site_keys()
    mapping = bundle.mapping
    prefix = mapping.prefix
    # cross_site_keys above is exactly the pair set lookup_display_columns
    # needs, so the report excludes a cross-site ref's target for the same
    # reason the validator and the deployer do: it renders as a Choice + URL
    # pair, and no picker exists on the far side to protect.
    calculated_by_entity = {
        table.name: {c.name for c in table.columns if c.type in CALCULATED_TYPES}
        for table in schema.tables
    }
    display_columns = lookup_display_columns(
        schema, mapping.entities, calculated_by_entity, cross_site_keys,
    )

    lines = [
        f"# Data dictionary: `{prefix}` (site role `{site_role}`)",
        "",
        "## Deployment / schema model metadata",
        "",
        "| Field | Value |",
        "|---|---|",
    ]
    lines += [
        f"| {field_name} | {_md_cell(value)} |"
        for field_name, value in metadata_rows(
            bundle, site_role, len(tables),
            release, generated_at, source_schema, source_mapping,
        )
    ]

    for table in tables:
        entity = mapping.entities[table.name]
        list_title = prefix + table.name
        heading = (
            f"## {list_title}: entity `{table.name}` "
            f"({entity.kind}, template {entity.base_template}"
            + (", singleton" if entity.singleton else "")
            + ")"
        )
        lines += ["", heading, ""]
        if table.note:
            lines += [_md_cell(table.note), ""]
        lines += [
            ("| Column | SharePoint type | Required | Unique | Default | "
             "Retired | Superseded by | Populated when | Save rule | Description |"),
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for (
            name, type_cell, required, unique, default,
            retired, superseded_by, populated, rule, description,
        ) in column_rows_for_table(
            table, bundle, enum_names, enum_members, cross_site_keys,
        ):
            lines.append(
                f"| {name} | {_md_cell(type_cell)} | {required} | {unique} | "
                f"{_md_cell(default)} | {retired} | {superseded_by} | "
                f"{_md_cell(populated)} | {_md_cell(rule)} | "
                f"{_md_cell(description)} |",
            )
        details: list[str] = []
        # The declared indexes PLUS the one a lookup target gets for free. A
        # list that anything looks up is indexed on its display column so the
        # picker keeps working past 5,000 items, and that index spends one of
        # the twenty, so a dictionary listing only the declared ones
        # understates a budget an author is reading this page to manage.
        # Derived from the same lookup_display_columns the deployer emits from,
        # so the report cannot disagree with what is deployed.
        indexed = list(deployable_index_columns(table))
        display = display_columns.get(table.name)
        if display is not None and display not in indexed:
            indexed.append(f"{display} (lookup display column)")
        if indexed:
            details.append(f"Indexed columns: {', '.join(indexed)}.")
        # `versioning_for` rather than the merge again: this page tells a
        # reader what the list was provisioned with, so it has to be the same
        # answer jsgen sent.
        versioning = mapping.versioning_for(table.name)
        if versioning.enable_versioning:
            details.append(
                "Versioning: major versions on, limit "
                f"{versioning.major_version_limit}"
                + (", minor versions on" if versioning.enable_minor_versions else "")
                + ".",
            )
        else:
            details.append("Versioning: off.")
        lines += ["", " ".join(details)]

    if mapping.reporting.users_table:
        lines += [
            "",
            f"## {USERS_KEY_LIST}: the site's user information list",
            "",
            ("Not a list of this schema. One row per person, SharePoint group "
             "or domain group the site has ever resolved, read from "
             "`/_api/web/siteuserinfolist`, carrying `Site Url` and "
             "`Site Name` like every list table. Every person column's "
             "`... Key` joins `User Key` here; guide.md has the relationships "
             "and the one-active rule."),
            "",
            "| Column | SharePoint type | Description |",
            "|---|---|---|",
            *(
                f"| {name} | {_md_cell(type_cell)} | {_md_cell(description)} |"
                for name, type_cell, _r, _u, _d, _re, _s, _p, _ru, description
                in users_dictionary_rows()
            ),
        ]
    lines += [
        "",
        "## Helper columns (query layer only)",
        "",
        ("Added by every generated Power Query and SQL view; they are "
         "constructed at query time and do not exist on the lists:"),
        "",
        "| Column | Construction | Purpose |",
        "|---|---|---|",
        ("| ItemURL | The list's own folder, read at refresh, + item id "
         "(the SQL views use the declared list path instead) | Direct link "
         "from any report row back to the SharePoint item (display form) |"),
        (f"| {ITEM_URL_RESOLVED_COLUMN} | Whether that folder read succeeded "
         "| False means every ItemURL in the table was built from the "
         "declared title, which is a dead link on a list that has been "
         "renamed. Suppress the link rather than ship a 404 |"),
        _date_zone_dictionary_row(mapping.reporting.time_zone),
        ("| ...Id / ...Title (lookups, person) | `$select`/`$expand` of the "
         "lookup | Join key plus display column without a second query |"),
        "",
        "## Reporting-only columns",
        "",
        ("Columns marked **Reporting only** above are computed in the "
         "generated Power Query and exist nowhere else. No SharePoint field "
         "stands behind one, no list carries it, and a site search will not "
         "find it. They are declared in the mapping beside the schema, so "
         "the report and the lists are generated from one description "
         "rather than two."),
        "",
        ("They are Power Query only. The SQL views carry the lists' own "
         "columns and the lookup joins, and none of these, because a "
         "row-level expression written in M has no SQL to translate to."),
        "",
        "## Blank in a column marked required",
        "",
        ("A column's Required cell says what SharePoint enforces on SAVE, "
         "which is not the same as what every row holds. SharePoint applies "
         "a column default to NEW items only, so a required column with a "
         "default reads blank on every row created before that column was "
         "added to the list, and stays blank until somebody edits the row "
         "or bulk-edits the column. The generated queries pass those blanks "
         "through unchanged."),
        "",
        ("A blank in such a column therefore means either that the row "
         "predates the column or that somebody cleared it, and nothing in "
         "the feed separates the two. Where that distinction matters, "
         "compare the row's Created against the release that added the "
         "column rather than reading the blank as a data quality problem."),
        "",
    ]
    return "\n".join(lines)
