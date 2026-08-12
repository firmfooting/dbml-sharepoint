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

#: Added to the row table for every entity, before the model-facing rename.
#: `Site Url` and `Site Name` say which SITE a row came from; `List Title`
#: says which LIST, which is the other half of the same problem once a model
#: appends several lists.
REPORT_FIXED_COLUMNS: tuple[str, ...] = ("Site Url", "Site Name", "List Title")

#: `Id` is unique only within one list on one site, so an appended model needs
#: a key that carries both. Named per entity, so it cannot be a constant.
REPORT_KEY_SUFFIX = " Key"


def report_columns_for(entity: str) -> tuple[str, ...]:
    """Every reporting column present when `entity`'s rename runs."""
    return (*REPORT_FIXED_COLUMNS, f"{entity}{REPORT_KEY_SUFFIX}")
