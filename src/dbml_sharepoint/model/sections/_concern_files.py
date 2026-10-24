# src/dbml_sharepoint/model/sections/_concern_files.py
"""Concern files: fixed-name files beside `mapping.yaml` that hold some of its sections.

Each file holds the sections of one concern and nothing else, and a section
lives in one place: declared both in the mapping and in its concern file, it
is refused with the line of each, never merged. The blocks read here are
added to the mapping's raw sections, so every family reads exactly the
dictionary it would read had the sections been written inline.
"""

from collections.abc import Mapping
from pathlib import Path

from dbml_sharepoint.model._keys import _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_types import _REMOVED_SECTIONS
from dbml_sharepoint.model.reading import read_yaml_document
from dbml_sharepoint.model.sections import KNOWN_SECTIONS, SECTION_FAMILIES
from dbml_sharepoint.model.sections._form_file import FORM_FILE_NAME
from dbml_sharepoint.model.yamlio import _key_lines

#: Each concern file's name and the sections it may hold.
CONCERN_FILES: dict[str, tuple[str, ...]] = {
    "views.yaml": ("field_sets", "views"),
    "permissions.yaml": ("groups", "permission_levels", "list_permissions", "identities"),
    "formatting.yaml": ("style_theme", "column_formatting"),
    "validation.yaml": ("column_validation", "list_validation"),
    "governance.yaml": ("governance",),
    "reporting.yaml": ("reporting", "derived_columns"),
    "demo.yaml": ("demo_items",),
}

_MAPPING_FILE_NAME = "mapping.yaml"
_HOMES = {key: concern for concern, keys in CONCERN_FILES.items() for key in keys}
_POINTERS = {family.keys: family.source for family in SECTION_FAMILIES if family.source}


def _where(path: Path, key: str) -> str:
    """`file:line` for top-level `key` in `path`, or the file alone when the line is unknown."""
    line = _key_lines(path.read_text(encoding="utf-8"), depth=1).get((key,))
    return path.name if line is None else f"{path.name}:{line}"


def _home(key: str, base_dir: Path, mapping_name: str) -> str | None:
    """The file `key` belongs in, or None for a key the mapping would refuse too."""
    if key in _HOMES:
        return _HOMES[key]
    if key in ("form_formatting", "form_visibility") and (base_dir / FORM_FILE_NAME).is_file():
        return FORM_FILE_NAME
    if key in KNOWN_SECTIONS and key not in _REMOVED_SECTIONS:
        return mapping_name
    return None


def _pointer_skips(
    concern: str, keys: tuple[str, ...], path: Path, raw: Mapping[str, object],
) -> bool:
    """True when the family's pointer names this concern file, which it then reads itself."""
    pointer = _POINTERS.get(keys)
    value = raw.get(pointer) if pointer else None
    # Any other value is left for `_pointed_blocks` to refuse, as it does today.
    if not isinstance(value, str) or not value.strip():
        return False
    if (path.parent / value).resolve() == path.resolve():
        return True
    if path.is_file():
        raise MappingShapeError(
            f"{pointer} points at {value!r} and {concern} exists beside the mapping: "
            f"{', '.join(keys)} live in one place. Remove one.",
        )
    return False


def read_concern_files(mapping_path: Path, raw: Mapping[str, object]) -> dict[str, object]:
    """`raw` plus the sections read from each concern file beside `mapping.yaml`."""
    if mapping_path.name != _MAPPING_FILE_NAME:
        # A folder may hold several mappings, as test/fixtures does; concern files belong to one.
        return dict(raw)
    base_dir = mapping_path.parent
    merged = dict(raw)
    for concern, keys in CONCERN_FILES.items():
        path = base_dir / concern
        if _pointer_skips(concern, keys, path, raw) or not path.is_file():
            continue
        block = _require_mapping(read_yaml_document(path), concern)
        for key in block:
            if key in keys:
                continue
            home = _home(key, base_dir, mapping_path.name)
            belongs = "" if home is None else f"; {key} belongs in {home}"
            raise MappingShapeError(
                f"{_where(path, key)}: {concern} holds {', '.join(keys)} only, "
                f"not {key}{belongs}",
            )
        for key in block:
            if key in raw:
                raise MappingShapeError(
                    f"{key} is declared in {_where(mapping_path, key)} and "
                    f"{_where(path, key)}: a section lives in one place. Keep one.",
                )
        merged.update(block)
    return merged
