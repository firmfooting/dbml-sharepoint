# src/dbml_sharepoint/analysis/folder_defaults.py
"""How a `folder_defaults` value is spelled in the location-based defaults file.

SHARED because the validator judges a value by whether it has a spelling here,
and the deploy, verify and assess payloads all carry the spelled value, so the
file the deploy writes and the text verify compares can never disagree.

Each rule follows what SharePoint's own receiver was measured to do
(`library.folder-defaults.value.*` in the maintainers' probes). Only a value
the receiver was seen to drop is refused; any other text is written as given.
"""

import re
from collections.abc import Sequence

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
_UPN = re.compile(r"[^@\s;#|]+@[^@\s;#|]+\.[^@\s;#|]+")
# library.folder-defaults.value.number-forms: letters (bar an exponent) or a space are dropped.
_NUMBER_DROPPED = re.compile(r"\s|[A-DF-Za-df-z]|^[^0-9]*$")
# library.folder-defaults.value.date-forms: a bare date, a day-first date and an offset from today.
_DATE_DROPPED = re.compile(
    r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{4}|today\s*[+-]\s*\d+", re.IGNORECASE,
)
_TODAY = ("today", "[today]")
# library.folder-defaults.value.boolean-forms: true, 1 and -1 read Yes; other text reads No.
_BOOLEAN_TEXT = {
    "true": "1", "1": "1", "-1": "1", "yes": "1", "on": "1",
    "false": "0", "0": "0", "no": "0", "off": "0",
}


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
        bad = [v for v in _values(value) if not _UPN.fullmatch(v)]
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
    if element_type(column_type) in NUMBER_TYPES and _NUMBER_DROPPED.search(value):
        return (
            f"SharePoint drops a number default it cannot parse, such as {value!r}; "
            f"write digits, such as 1234.5, 1,234.5 or 1e3."
        )
    if (
        element_type(column_type) in DATE_TYPES
        and value.lower() not in _TODAY
        and _DATE_DROPPED.fullmatch(value.strip())
    ):
        return (
            f"SharePoint drops a date default written as {value!r}; write today, or a "
            f"UTC instant such as 2026-03-15T00:00:00Z (midnight on 15 March for a "
            f"site on UTC)."
        )
    return None


def encode_folder_default(column_type: str, value: FolderDefaultValue) -> str:
    """The text the defaults file holds for an accepted value (see `folder_default_problem`)."""
    if _is_person(column_type):
        # library.folder-defaults.value.person-claim and .multi-person-claims.
        return ";#".join(f"-1;#{PERSON_CLAIM_PREFIX}{upn}" for upn in _values(value))
    if is_boolean(column_type):
        if isinstance(value, bool):
            return "1" if value else "0"
        text = str(value)
        return _BOOLEAN_TEXT.get(text.strip().lower(), text)
    if element_type(column_type) in DATE_TYPES and str(value).lower() in _TODAY:
        return "[today]"
    # library.folder-defaults.value.multi-choice: members joined by ;#.
    return ";#".join(_values(value))


def person_logins(column_type: str, value: FolderDefaultValue) -> list[str]:
    """The login claims a person default names, which the deploy resolves first."""
    return [PERSON_CLAIM_PREFIX + upn for upn in _values(value)] if _is_person(column_type) else []
