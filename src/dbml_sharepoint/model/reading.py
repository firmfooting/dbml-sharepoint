# src/dbml_sharepoint/model/reading.py
"""Typed reads shared by every section family.

One scalar off a YAML block, refusing the shapes YAML also accepts for it,
or one file the mapping names beside itself. Each helper carries the typo it
exists to refuse: `bool("false")` is True and a bare string iterates
character by character, and a value read leniently deploys the wrong thing
while the build reports success.

A blank key follows one rule (decided on #665), and every reader here keeps it:

- An absent key takes its default, silently.
- A key written with no value (`direction:`, which YAML reads as null) reads
  as absent, so it takes its default too.
- Where that default decides how the deployed lists behave, the blank is
  recorded as a `BlankDefault` and validation warns with
  `blank_key_took_default`, because the author may have meant a value. That
  is any boolean, a vocabulary word (`direction`, `reconcile`, `trigger`,
  `owner_group`, item_security `read` and `write`, a view's `scope`), a
  condition (`where`, `when`), a `from_enum` source, `major_version_limit`,
  a view's `row_limit`, an entity's `title`, and a policy's `assignments`
  (under `reconcile: exact` an empty grant list strips every grant).
- Where the default is empty text, an empty list or a value that changes
  nothing (`description`, `notes`, `extension`, a style guard's `not`), a
  blank stays silent, because it can only mean nothing.
- A required key left blank is refused as `{context}.{key} is required`.
- A value of the wrong type is refused.

Recording happens only inside `recording_blank_defaults()`, which
`load_mapping` opens around the section families. Outside it a blank still
takes its default, without a record.
"""

import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Any

import yaml

from dbml_sharepoint.model.errors import (
    MappingReferenceError,
    MappingShapeError,
    MappingSourceError,
    MappingValueError,
)
from dbml_sharepoint.model.mapping_types import BlankDefault

# The collector for the load in progress; a ContextVar because the readers are
# called from nested parse functions that carry no section context.
_BLANK_DEFAULTS: ContextVar[list[BlankDefault] | None] = ContextVar(
    "blank_defaults", default=None,
)


@contextmanager
def recording_blank_defaults() -> Iterator[list[BlankDefault]]:
    """Collect the blank keys that took a behavioural default, for one load."""
    recorded: list[BlankDefault] = []
    token = _BLANK_DEFAULTS.set(recorded)
    try:
        yield recorded
    finally:
        _BLANK_DEFAULTS.reset(token)


def _took_default(context: str, key: str, default: object) -> None:
    """Record that `context.key` was blank and took `default`, if a load is recording."""
    recorded = _BLANK_DEFAULTS.get()
    if recorded is not None:
        recorded.append(BlankDefault(path=f"{context}.{key}", default=default))


def _or_default(raw: Mapping[str, Any], key: str, context: str, default: object) -> object:
    """`raw[key]`, or `default` when the key is absent or blank. A blank is recorded."""
    value: object = raw.get(key)
    if value is not None:
        return value
    if key in raw:
        _took_default(context, key, default)
    return default


def optional_value(
    raw: Mapping[str, Any], key: str, context: str, *, default: object = None,
) -> Any:
    """The untyped value under `key`, or `default` when it is absent or blank.

    For a key whose default is itself a behaviour (no condition, no enum to
    expand, a style's boolean) and whose value the caller types, so a blank
    is recorded as taking `default`.
    """
    return _or_default(raw, key, context, default)


def drop_blank_keys(
    block: Mapping[str, object], context: str, defaults: Mapping[str, object],
) -> dict[str, object]:
    """`block` without its blank keys, each recorded as taking `defaults[key]`.

    For a block stored raw and merged later, where a blank left in place would
    reach the merge as None rather than as absent. `defaults` must name every
    key the caller admitted.
    """
    kept: dict[str, object] = {}
    for key, value in block.items():
        if value is None:
            _took_default(context, key, defaults[key])
        else:
            kept[key] = value
    return kept


def read_yaml_document(path: Path, named_by: str | None = None) -> Any:
    """Parse one YAML file, naming every way reading it can fail.

    `yaml.YAMLError` and the `OSError` from opening the file are neither of
    them a `MappingError`, so a caller switching on the base class used to
    miss the two most ordinary failures there are: a mapping with a typo
    that stops it parsing, and a source file that is not where the mapping
    says. The original is kept as `__cause__`, and the parser's own text is
    passed through because it carries the line and column, which is the part
    an author can act on.

    Decoding is the third way, and it is the one that hides: the bytes turn
    into text inside `yaml.safe_load`, so a file that is not UTF-8 raises
    `UnicodeDecodeError` past both of the other handlers. It is a
    `ValueError` subclass, so it reached a caller catching `ValueError`
    looking exactly like a refusal this module composed.

    `named_by` is the declaration that pointed at this file, when one did.
    An unreadable file is then the reference that did not resolve, which is
    what `MappingReferenceError` documents; a path the caller supplied has
    no declaration to blame, so it is the document itself that failed.
    """
    try:
        with path.open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except OSError as exc:
        reason = exc.strerror or exc
        if named_by is None:
            raise MappingSourceError(f"{path}: cannot be read: {reason}") from exc
        raise MappingReferenceError(f"{named_by}: cannot read {path}: {reason}") from exc
    except UnicodeDecodeError as exc:
        # The pointer resolved and the file opened, so the declaration is
        # not what is wrong: these bytes are not a document at all.
        raise MappingSourceError(f"{path}: is not valid UTF-8: {exc}") from exc
    except yaml.YAMLError as exc:
        raise MappingSourceError(f"{path}: is not valid YAML: {exc}") from exc


def load_yaml(path: Path, named_by: str | None = None) -> dict[str, Any]:
    """Load a YAML file; require a top-level mapping (dict)."""
    raw = read_yaml_document(path, named_by)
    if not isinstance(raw, dict):
        raise MappingShapeError(
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
            raise MappingReferenceError(f"{context}: cannot read {value!r}: {exc}") from exc
        except UnicodeDecodeError as exc:
            # `read_text` decodes, so the same hole `read_yaml_document` had:
            # a `ValueError` subclass that no handler here caught.
            raise MappingSourceError(
                f"{context}: {value!r} is not valid UTF-8: {exc}",
            ) from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise MappingValueError(f"{context}: {value!r} is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise MappingShapeError(f"{context}: {value!r} must contain a JSON object")
        return parsed
    raise MappingShapeError(
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

    A blank key takes `default` and is recorded, as the module docstring says.
    """
    value = _or_default(raw, key, context, default)
    if not isinstance(value, bool):
        raise MappingShapeError(f"{context}.{key}: expected true or false, got {value!r}")
    return value


def optional_bool(
    raw: Mapping[str, Any], key: str, context: str, *, default: bool = False,
) -> bool:
    """Read an optional boolean without truthiness-coercing malformed YAML.

    `default` exists for the same reason `strict_bool`'s does: so a caller
    whose fallback is declared elsewhere can name it instead of copying it.
    A blank key takes it and is recorded, as `strict_bool`'s does.
    """
    value = _or_default(raw, key, context, default)
    if not isinstance(value, bool):
        raise MappingShapeError(f"{context}.{key} must be a boolean, got {value!r}")
    return value


def optional_str(
    raw: Mapping[str, Any], key: str, context: str, *, record_blank: bool = False,
) -> str | None:
    """Read an optional string, refusing anything YAML happened to parse instead.

    `display_column: [Title]` is a plausible typo and YAML accepts it as a list.
    Passed through, it reaches a set-membership test deep in validation and
    raises `TypeError: unhashable type: 'list'`, a traceback instead of the
    ordinary "this column does not exist" error the author needed. Refuse the
    shape here, where the context string can name the key.

    `record_blank` is for a key whose absence is itself a behaviour (an
    entity's `title` falls back to the derived list title): a blank one is
    recorded as taking None. Off by default, so `extension:` stays silent.
    """
    value = optional_value(raw, key, context) if record_blank else raw.get(key)
    if value is not None and not isinstance(value, str):
        raise MappingShapeError(f"{context}.{key} must be a string, got {value!r}")
    return value


def strict_str(
    raw: Mapping[str, Any], key: str, context: str, *, default: str,
) -> str:
    """Read a string that falls back to a default the author should hear about.

    An absent key and a blank one (`direction:` with nothing after it) both
    take the default, and the blank is recorded, as the module docstring
    says. That record is the whole difference from `optional_str`.

    Use it wherever the fallback is a CHOICE the loader would otherwise make
    silently. Where the fallback is the empty value of the same kind (`""`
    for free text, `()` for a list of names), a blank can only mean nothing
    and `optional_str` is the reader.
    """
    value = _or_default(raw, key, context, default)
    if not isinstance(value, str):
        raise MappingShapeError(f"{context}.{key} must be a string, got {value!r}")
    return value


def _require(raw: Mapping[str, Any], key: str, context: str) -> Any:
    """The value under `key`, refusing a block that omits it or leaves it blank."""
    value = raw.get(key)
    if value is None:
        raise MappingShapeError(f"{context}.{key} is required")
    return value


def require_int(raw: Mapping[str, Any], key: str, context: str) -> int:
    """Read a required integer, refusing the bool YAML hands back for `yes`.

    `isinstance(True, int)` is True in Python, so a plain int check passes a
    boolean straight through and `int(True)` is 1. Both fields read this way
    are ones where 1 is a legal-looking value, so nothing downstream can tell
    the difference.

    An absent key is a `MappingShapeError` naming the key path, not the bare
    KeyError this subscripted before #170: the hierarchy claims an absent
    required key, so a caller catching `MappingError` has to get one.
    """
    value = _require(raw, key, context)
    if isinstance(value, bool) or not isinstance(value, int):
        raise MappingShapeError(f"{context}.{key} must be an integer, got {value!r}")
    return value


def optional_int(
    raw: Mapping[str, Any], key: str, context: str, *, record_blank: bool = False,
) -> int | None:
    """Read an optional integer, refusing bools and un-coercible strings.

    `int(raw)` accepted three wrong things silently or badly: `yes` became 1,
    `"100"` became 100 (so a quoted number worked by accident and taught the
    wrong lesson), and `many` raised `invalid literal for int() with base 10`,
    a message naming neither the key, the view, nor the entity.

    `record_blank` works as `optional_str`'s does (a view's `row_limit`).
    """
    value = optional_value(raw, key, context) if record_blank else raw.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise MappingShapeError(f"{context}.{key} must be an integer, got {value!r}")
    return value


def require_str(raw: Mapping[str, Any], key: str, context: str) -> str:
    """Read a required string. The mirror of `optional_str`.

    Refuses an absent or blank key the same way `require_int` does.
    """
    value = _require(raw, key, context)
    if not isinstance(value, str):
        raise MappingShapeError(f"{context}.{key} must be a string, got {value!r}")
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
        raise MappingShapeError(f"{context}.{key} must be a list of strings, got {value!r}")
    for item in value:
        if not isinstance(item, str):
            raise MappingShapeError(
                f"{context}.{key} must be a list of strings, got {item!r}",
            )
    return tuple(value)
