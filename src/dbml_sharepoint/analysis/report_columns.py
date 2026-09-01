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

from dbml_sharepoint.analysis.column_projection import SYSTEM_COLUMN_TYPES
from dbml_sharepoint.analysis.typemap import is_person

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
