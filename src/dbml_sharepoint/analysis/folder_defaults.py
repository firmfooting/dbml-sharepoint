# src/dbml_sharepoint/analysis/folder_defaults.py
"""How a `folder_defaults` value is spelled in the location-based defaults file.

SHARED because the validator judges a value by whether it has a spelling here,
and the deploy, verify and assess payloads all carry the spelled value, so the
file the deploy writes and the text verify compares can never disagree.

Each spelling is the one SharePoint's own receiver was measured to apply
(`library.folder-defaults.value.*` in the maintainers' probes). A value with no
spelling here is one the receiver drops, or one that stops it applying any
default to the file.
"""

import re
from collections.abc import Sequence
from datetime import datetime

from dbml_sharepoint.analysis.typemap import (
    DATE_TYPES,
    NUMBER_TYPES,
    element_type,
    is_boolean,
    is_multi_person,
    is_multi_value,
    is_person,
)
from dbml_sharepoint.model.mapping_types import FolderDefaultValue

#: The claim prefix of a tenant member's login, which the receiver resolves.
PERSON_CLAIM_PREFIX = "i:0#.f|membership|"
_UPN = re.compile(r"^[^@\s;#|]+@[^@\s;#|]+\.[^@\s;#|]+$")
_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_BOOLEAN_TEXT = {"1": "1", "0": "0", "true": "1", "false": "0"}


def _values(value: FolderDefaultValue) -> Sequence[str]:
    return value if isinstance(value, tuple) else (str(value),)


def _is_person(column_type: str) -> bool:
    return is_person(column_type) or is_multi_person(column_type)


def folder_default_problem(column_type: str, value: FolderDefaultValue) -> str | None:
    """Why `value` has no spelling the receiver applies for a column of this type, or None.

    Lookups, enum membership, `[unique]` and XML-illegal text are the
    validator's to judge; this answers only the shape of the value.
    """
    if isinstance(value, tuple) and not is_multi_value(column_type):
        return "a list is only a default for a multi-value column; give one value."
    if _is_person(column_type):
        bad = [v for v in _values(value) if not _UPN.match(v)]
        if bad:
            return (
                f"a person default is the account's user principal name, such as "
                f"name@contoso.com; {', '.join(map(repr, bad))} is not one."
            )
        return None
    if isinstance(value, bool):
        if is_boolean(column_type):
            return None
        return "true or false is only a default for a boolean column."
    if isinstance(value, tuple):
        # Only a multi-choice column reaches here; the validator judges its members.
        return None
    if is_boolean(column_type) and value.lower() not in _BOOLEAN_TEXT:
        # library.folder-defaults.value.boolean: the receiver drops `Yes`.
        return f"a boolean default is true or false; SharePoint drops {value!r}."
    if element_type(column_type) in NUMBER_TYPES and not _NUMBER.match(value):
        # library.folder-defaults.value.number: the receiver drops a value that does not parse.
        return (
            f"a number default is digits with an optional decimal point, such as "
            f"1234.5; got {value!r}."
        )
    if element_type(column_type) in DATE_TYPES and value != "today" and not _is_instant(value):
        # library.folder-defaults.value.date-bare-dropped: the receiver drops a bare date.
        return (
            f"a date default is today, or a UTC instant such as 2026-03-14T13:00:00Z "
            f"(the site's midnight on 15 March in Melbourne); {value!r} is neither, and "
            f"SharePoint drops a bare date."
        )
    return None


def _is_instant(value: str) -> bool:
    if not _INSTANT.match(value):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def encode_folder_default(column_type: str, value: FolderDefaultValue) -> str:
    """The text the defaults file holds for an accepted value (see `folder_default_problem`)."""
    if _is_person(column_type):
        # library.folder-defaults.value.person-claim and .multi-person-claims.
        return ";#".join(f"-1;#{PERSON_CLAIM_PREFIX}{upn}" for upn in _values(value))
    if is_boolean(column_type):
        if isinstance(value, bool):
            return "1" if value else "0"
        return _BOOLEAN_TEXT[str(value).lower()]
    if element_type(column_type) in DATE_TYPES and value == "today":
        return "[today]"
    # library.folder-defaults.value.multi-choice: members joined by ;#.
    return ";#".join(_values(value))


def person_logins(column_type: str, value: FolderDefaultValue) -> list[str]:
    """The login claims a person default names, which the deploy resolves first."""
    return [PERSON_CLAIM_PREFIX + upn for upn in _values(value)] if _is_person(column_type) else []
