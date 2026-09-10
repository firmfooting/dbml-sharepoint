"""The columns the reporting pack adds beside a list's own.

Shared because two sides need the same fact and must not drift: `reportgen`
writes these into the Power Query, and `checks/_naming` refuses a display
title that would collide with one. `AGENTS.md` is explicit that where both
sides need the same fact it lives in a shared module -- `analysis/joins.py`
is the worked example -- and a generator must never import from
`analysis/checks/`.

WHY A COLLISION MATTERS. The generated query adds these columns and THEN
runs `Table.RenameColumns` to give every schema column its display title.
Renaming a column onto a name the table already carries is an error in M, so
the collision does not produce a wrong report -- it produces a refresh that
fails, after the operator has published the model. `display_name_mode: auto`
reaches it with no override at all: `auto_display_name` splits `SiteUrl` to
`Site Url`, `SiteName` to `Site Name` and `ListTitle` to `List Title`.
"""

from typing import assert_never

from dbml_sharepoint.analysis.column_projection import SYSTEM_COLUMN_TYPES
from dbml_sharepoint.analysis.typemap import SPField, is_person

#: Added to the row table for every entity, before the model-facing rename.
#: `Site Url` and `Site Name` say which SITE a row came from; `List Title`
#: says which LIST, which is the other half of the same problem once a model
#: appends several lists.
REPORT_FIXED_COLUMNS: tuple[str, ...] = ("Site Url", "Site Name", "List Title")

#: `Id` is unique only within one list on one site, so an appended model needs
#: a key that carries both. Named per entity, so it cannot be a constant.
REPORT_KEY_SUFFIX = " Key"

#: The system columns `reporting.system_columns` adds to every list, in
#: reporting order: Created By, Created, Modified By, Modified. Which columns
#: exist and what kind each is comes from `column_projection.SYSTEM_COLUMN_TYPES`,
#: the deploy side's list; only the order is decided here. ID is not among
#: them because every query already carries the row id as `Id`.
REPORT_SYSTEM_COLUMNS: tuple[str, ...] = ("Author", "Created", "Editor", "Modified")

#: SharePoint's own display titles for the two person columns. Created and
#: Modified are already theirs.
SYSTEM_DISPLAY_TITLES: dict[str, str] = {"Author": "Created By", "Editor": "Modified By"}

#: The namespace the users dimension keys itself under. A leading underscore
#: like the query's own name, so no list title can produce the same key.
USERS_KEY_LIST = "_Users"

#: The helper column linking each row back to its SharePoint item. Added by
#: the query itself, so no declared column stands behind it.
ITEM_URL_COLUMN = "ItemURL"


def projection_output_name(column: str, target: str) -> str:
    """The report column one lookup projection contributes.

    The SAME name the deploy gives the dependent field it creates (`jsgen`
    composes it identically), so the column a report carries is the column
    the list carries and the data dictionary names.
    """
    return f"{column}{target}"


def report_output_names(
    sp: SPField, *, lookup_display: str, projections: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """The report columns one declared field contributes, in query order.

    THE NAMES `Table.RenameColumns` ACTUALLY SEES, which for a record-valued
    field are not the declared name. A URL value, a person expand and a lookup
    expand all arrive as records, so the query keeps a part of each under a
    derived name and the declared name never reaches the rename. Comparing the
    declared column's display title therefore asks about a column the report
    does not have: it refused a `URL` column named `SiteUrl`, whose report
    column is `SiteUrlUrl` and renames to `Site Url Url`, and let through a
    `URL` column named `Site`, whose report column IS `SiteUrl` and does
    collide with the `Site Url` the pack adds (#202).

    `lookup_display` is the column a lookup into the target shows, from
    `analysis.lookups.display_column_for`. Every other kind ignores it.

    `projections` are the target columns a lookup ALSO projects onto this
    list, from `mapping.projections_for`. SharePoint and the data dictionary
    both carry them as columns of the list, so a report that omits them
    contradicts both, and it does so by leaving the column out rather than
    blank. The display column is dropped from them where the two coincide,
    because one expand path cannot land twice under one name.

    A fourteenth `FieldKind` fails `uv run mypy` on the `assert_never` below,
    which is the point: a kind whose report columns nobody has decided must
    not resolve to silence in a rule that refuses builds. The runtime raise
    behind it is a backstop only, because `_build_plans` reaches its own
    `case _` first and that one names the entity and the column.
    """
    match sp.kind:
        case "Skip":
            # The auto-increment Id is never created; the query reads
            # SharePoint's own.
            return ("Id",)
        case "URL":
            return (f"{sp.name}Url",)
        case "User":
            return (f"{sp.name}Id", f"{sp.name}Title")
        case "Lookup":
            projected = tuple(
                projection_output_name(sp.name, target)
                for target in projections
                if target != lookup_display
            )
            return (f"{sp.name}Id", f"{sp.name}{lookup_display}", *projected)
        case "LookupMulti":
            # No expand, so no display column: expanding a collection yields a
            # nested table per row and the query carries the ids alone.
            return (f"{sp.name}Id",)
        case (
            "Text" | "Note" | "Choice" | "MultiChoice"
            | "Number" | "Boolean" | "DateTime" | "Calculated"
        ):
            return (sp.name,)
        case _:
            assert_never(sp.kind)


def fk_key_column(fk_column: str) -> str:
    """The `... Key` a single-value lookup carries into its target's rows.

    `IncidentId` becomes `Incident Key`, matching the `<Entity> Key` the
    target table exposes, so the relationship reads as one name on both
    sides. Spaced to sit alongside the other model-facing names, which are
    display titles rather than internal ones.
    """
    return f"{fk_column.removesuffix('Id')}{REPORT_KEY_SUFFIX}"


def system_person_columns() -> tuple[str, ...]:
    """The system columns that are person columns, in reporting order."""
    return tuple(
        name for name in REPORT_SYSTEM_COLUMNS
        if is_person(SYSTEM_COLUMN_TYPES[name])
    )


def person_key_column(column: str) -> str:
    """The `... Key` a person column carries when the users table is on.

    A schema column keeps its internal name, as a lookup key does. A system
    column takes its display title, because `Author` and `Editor` never
    reach a report author under those names.
    """
    return f"{SYSTEM_DISPLAY_TITLES.get(column, column)}{REPORT_KEY_SUFFIX}"


def system_report_columns() -> tuple[str, ...]:
    """The model-facing names the system columns take under display-name
    mode: `Created By Id`, `Created By Title`, `Created`, and the Modified
    three. The person pair follows the `<Display> Id` / `<Display> Title`
    shape a declared person column gets, so it sits consistently beside
    one."""
    names: list[str] = []
    for name in REPORT_SYSTEM_COLUMNS:
        title = SYSTEM_DISPLAY_TITLES.get(name)
        if title is None:
            names.append(name)
        else:
            names += [f"{title} Id", f"{title} Title"]
    return tuple(names)


def report_columns_for(
    entity: str,
    *,
    system_columns: bool = False,
    person_columns: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Every reporting column present when `entity`'s rename runs.

    With `reporting.system_columns` on, the six system column names are in
    the table too, renamed in the same step as the schema columns, so a
    schema column landing on one of them fails the refresh the same way.
    `person_columns` are the columns that carry a `... Key` when the users
    table is on; pass none when it is off.
    """
    columns = (*REPORT_FIXED_COLUMNS, f"{entity}{REPORT_KEY_SUFFIX}")
    if system_columns:
        columns += system_report_columns()
    columns += tuple(person_key_column(name) for name in person_columns)
    return columns
