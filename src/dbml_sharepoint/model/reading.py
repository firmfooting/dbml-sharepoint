# src/dbml_sharepoint/model/reading.py
"""Typed reads shared by every section family.

One scalar off a YAML block, refusing the shapes YAML also accepts for it,
or one file the mapping names beside itself. Each helper carries the typo it
exists to refuse: `bool("false")` is True and a bare string iterates
character by character, and a value read leniently deploys the wrong thing
while the build reports success.
"""

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file; require a top-level mapping (dict)."""
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at the top level, got {type(raw).__name__}",
        )
    return raw


def load_json_value(base_dir: Path, value: Any, context: str) -> dict[str, Any]:
    """A formatter declaration: a relative path to a JSON file (resolved
    against the mapping's directory, like enum_sources) or an inline
    mapping. Anything else (or malformed JSON) is a load error naming the
    offending declaration."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        path = (base_dir / value).resolve()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"{context}: cannot read {value!r}: {exc}") from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{context}: {value!r} is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{context}: {value!r} must contain a JSON object")
        return parsed
    raise ValueError(
        f"{context}: expected a relative .json path or an inline mapping, "
        f"got {type(value).__name__}",
    )


def strict_bool(
    raw: Mapping[str, Any], key: str, context: str, *, default: bool = True,
) -> bool:
    """Read a boolean without truthiness-coercing malformed YAML.

    `bool("false")` is True, so a quoted boolean would silently mean its
    opposite, and a visibility flag reading backwards hides nothing while
    reporting success.

    `default` is the absent-key value, and it is a parameter only so a caller
    whose default already has a home elsewhere can point at it rather than
    restate it (see the `versioning.default` block, which reads its three
    fallbacks off `Versioning`). The three form-visibility and permission
    callers keep the true default they have always had.
    """
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{context}.{key}: expected true or false, got {value!r}")
    return value


def optional_bool(
    raw: Mapping[str, Any], key: str, context: str, *, default: bool = False,
) -> bool:
    """Read an optional boolean without truthiness-coercing malformed YAML.

    `default` exists for the same reason `strict_bool`'s does: so a caller
    whose fallback is declared elsewhere can name it instead of copying it.
    """
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{context}.{key} must be a boolean, got {value!r}")
    return value


def optional_str(raw: Mapping[str, Any], key: str, context: str) -> str | None:
    """Read an optional string, refusing anything YAML happened to parse instead.

    `display_column: [Title]` is a plausible typo and YAML accepts it as a list.
    Passed through, it reaches a set-membership test deep in validation and
    raises `TypeError: unhashable type: 'list'`, a traceback instead of the
    ordinary "this column does not exist" error the author needed. Refuse the
    shape here, where the context string can name the key.
    """
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"{context}.{key} must be a string, got {value!r}")
    return value


def require_int(raw: Mapping[str, Any], key: str, context: str) -> int:
    """Read a required integer, refusing the bool YAML hands back for `yes`.

    `isinstance(True, int)` is True in Python, so a plain int check passes a
    boolean straight through and `int(True)` is 1. Both fields read this way
    are ones where 1 is a legal-looking value, so nothing downstream can tell
    the difference.

    Subscripted, not `.get()`: an absent required key stays the KeyError it
    has always been. Reporting that with a location is the error-model work
    in #170, and doing it here would change an unrelated message.
    """
    value = raw[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context}.{key} must be an integer, got {value!r}")
    return value


def optional_int(raw: Mapping[str, Any], key: str, context: str) -> int | None:
    """Read an optional integer, refusing bools and un-coercible strings.

    `int(raw)` accepted three wrong things silently or badly: `yes` became 1,
    `"100"` became 100 (so a quoted number worked by accident and taught the
    wrong lesson), and `many` raised `invalid literal for int() with base 10`,
    a message naming neither the key, the view, nor the entity.
    """
    value = raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{context}.{key} must be an integer, got {value!r}")
    return value


def require_str(raw: Mapping[str, Any], key: str, context: str) -> str:
    """Read a required string. The mirror of `optional_str`.

    Subscripted for the same reason as `require_int`.
    """
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(f"{context}.{key} must be a string, got {value!r}")
    return value


def optional_str_list(raw: Mapping[str, Any], key: str, context: str) -> tuple[str, ...]:
    """Read an optional list of strings, refusing the shapes YAML also accepts.

    `hide_from_all_items: Author` is the plausible typo, and YAML hands it back
    as a `str`, which iterates CHARACTER BY CHARACTER, so the column names
    silently become 'A', 'u', 't', 'h'... and every one reports as a column that
    does not exist. Refuse the shape here, where the context string can name the
    key. `optional_str` is the mirror of this and deliberately rejects a list.
    """
    value = raw.get(key)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{context}.{key} must be a list of strings, got {value!r}")
    for item in value:
        if not isinstance(item, str):
            raise ValueError(
                f"{context}.{key} must be a list of strings, got {item!r}",
            )
    return tuple(value)
