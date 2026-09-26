# src/dbml_sharepoint/model/_keys.py
"""The unknown-key guard, shared by every parser in this package.

Lives alone so the parsers and the retirement fold can both apply it
without importing each other.
"""

import datetime as dt
from typing import Any

from dbml_sharepoint.model.errors import MappingShapeError, UnknownMappingKeyError


def _text_key(key: object, context: str) -> str:
    """`key` as the name the author typed, or fail saying to quote it.

    YAML 1.1 resolves an unquoted key as it resolves a value, so `No:` loads
    as False, `2.10:` as 2.1, `010:` as 8 and `~:` as None. None of those is
    the text that was typed, and `str()` cannot recover it: `2.10` comes back
    as "2.1". Normalising also merged `1:` with a `"1":` beside it, one entry
    silently replacing the other. Every key this loader reads is a name, so a
    key that is not text is refused.
    """
    if isinstance(key, str):
        return key
    # "NoneType" is Python's word; the author wrote `~` or nothing, which YAML calls null.
    kind = "null" if key is None else type(key).__name__
    # The ISO text the author typed, not `datetime.date(2026, 9, 1)`.
    shown = key.isoformat() if isinstance(key, dt.date) else repr(key)
    raise MappingShapeError(
        f"{context}: key {shown} is not text (YAML read it as {kind}); quote it",
    )


def _require_mapping(
    block: Any, context: str, *, allow_absent: bool = True,
) -> dict[str, Any]:
    """Return `block` as a mapping, or fail naming the section.

    For the sections read as `name -> block`. Apply it BEFORE indexing or
    iterating one:

    - A populated list reaches `.items()` and raises AttributeError, which
      the CLI cannot catch (`_CONFIG_ERRORS` deliberately excludes it so a
      genuine loader bug keeps its traceback), so a SharePoint admin editing
      YAML got twenty lines of loader internals instead of a sentence.
    - An EMPTY list is falsy, so the `or {}` these sections were written with
      coerced it to an empty mapping and the section loaded as absent.

    What this is NOT is a rule about emptiness. `{}` is accepted: it is this
    structure with zero entries, and the thirty shipped mappings write it
    that way deliberately. `enum_sources: {}` and `versioning.overrides: {}`
    sit beside `watched_lists: []` and `permission_levels: []`, which are
    list-shaped sections where `[]` is the correct literal. The templates
    already keep the two apart, 143 times, so `[]` on a name-keyed section
    means the author has the wrong shape in mind, not that they have nothing
    to declare.

    Note it is worth being accurate about where `[]` comes from, because the
    obvious guess is wrong: commenting out the entries under a section yields
    `None`, not an empty sequence. `[]` has to be typed, or emitted by a
    templating step that reached for the wrong empty literal.

    `None` still means absent. A blank or commented-out key is YAML's way of
    not supplying a value, and refusing it would break every mapping that
    omits an optional section.

    `allow_absent=False` is for the REQUIRED sections, where that reasoning
    inverts: `entities:` with nothing under it is not "no entities declared,
    carry on", it is a mapping that cannot build. Letting it through as `{}`
    made the build die further downstream on "Invalid --site-role 'default';
    the mapping declares: (none)", an error that points at a flag which was
    never the problem. A loud error in the wrong shape is still better than a
    quiet one aimed at the wrong place.

    Apply this at EVERY level, not just the top, for the same reason
    `_reject_unknown_keys` says so: a level that still reads
    `x.get("default") or {}` coerces an empty list right back to an empty
    mapping and the section loads as absent.

    Every key must be text, because each one is a name: see `_text_key`.
    """
    if block is None:
        if not allow_absent:
            raise MappingShapeError(
                f"{context}: required, but the key is present with no value",
            )
        return {}
    if not isinstance(block, dict):
        raise MappingShapeError(
            f"{context}: expected a mapping of names, got {type(block).__name__}",
        )
    entries: dict[object, Any] = block
    for key in entries:
        _text_key(key, context)
    return block


def _require_list(block: object, context: str) -> list[object]:
    """Return `block` as a list, or fail naming the section.

    `_require_mapping` for the list-shaped sections, with the same rule for
    `None`: a blank key, or one whose entries are all commented out, is
    absent. A number or a mapping reached `enumerate` and raised TypeError.
    """
    if block is None:
        return []
    if not isinstance(block, list):
        raise MappingShapeError(
            f"{context}: expected a list, got {type(block).__name__}",
        )
    entries: list[object] = block
    return entries


def _reject_unknown_keys(block: Any, allowed: frozenset[str] | set[str], context: str) -> None:
    """Fail on any key the loader does not read.

    Apply this at EVERY nesting level, not just the top. A fail-open level
    makes a typo'd build byte-identical to one with the key deleted, so
    `deafult:` never makes a view the default, a filter under `wheres:`
    deploys an unfiltered view, and a misspelled `break_inheritance` leaves
    a list on inherited permissions, all reporting zero findings.
    """
    _known_keys(block, allowed, context)


def _known_keys(
    block: object, allowed: frozenset[str] | set[str], context: str,
) -> dict[str, object]:
    """`_reject_unknown_keys`, returning the block typed as what it proved.

    Every key is one of `allowed`, so the result is keyed by `str`; each
    value is still unchecked YAML, so it is `object` until the caller
    narrows it. A key that is not text is refused by `_text_key` first,
    because "unknown key False" does not tell the author they typed `No:`.
    """
    if not isinstance(block, dict):
        raise MappingShapeError(
            f"{context}: expected a mapping, got {type(block).__name__}",
        )
    entries: dict[object, object] = block
    unknown = {_text_key(key, context) for key in entries} - set(allowed)
    if unknown:
        raise UnknownMappingKeyError(
            f"{context}: unknown key(s) {sorted(unknown)} "
            f"(known: {sorted(allowed)})",
        )
    checked: dict[str, object] = block
    return checked
