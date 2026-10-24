# src/dbml_sharepoint/model/sections/_concern_files.py
"""Concern files: fixed-name files beside `mapping.yaml` that hold some of its sections.

Each file holds the sections of one concern and nothing else, and a section
lives in one place: declared both in the mapping and in its concern file, it
is refused with the line of each, never merged. The blocks read here are
added to the mapping's raw sections, so every family reads exactly the
dictionary it would read had the sections been written inline.

A concern may instead be a `<stem>.d/` folder of `.yaml` files, read in
code-point order of their names. That order sets the order of the merged
entries, and an entry declared in two files is refused.
"""

from collections.abc import Mapping
from pathlib import Path
from typing import cast

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


def _where(path: Path, base_dir: Path, *keys: str) -> str:
    """`file:line` for the key path `keys` in `path`, or the file alone when the line is unknown."""
    name = path.relative_to(base_dir).as_posix()
    line = _key_lines(path.read_text(encoding="utf-8"), depth=len(keys)).get(keys)
    return name if line is None else f"{name}:{line}"


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
    concern: str, keys: tuple[str, ...], path: Path, folder: Path, raw: Mapping[str, object],
) -> bool:
    """True when the family's pointer names this concern file, which it then reads itself."""
    pointer = _POINTERS.get(keys)
    value = raw.get(pointer) if pointer else None
    # Any other value is left for `_pointed_blocks` to refuse, as it does today.
    if not isinstance(value, str) or not value.strip():
        return False
    names_file = (path.parent / value).resolve() == path.resolve()
    if folder.is_dir() or (path.is_file() and not names_file):
        found = f"{folder.name}/" if folder.is_dir() else concern
        raise MappingShapeError(
            f"{pointer} points at {value!r} and {found} exists beside the mapping: "
            f"{', '.join(keys)} live in one place. Remove one.",
        )
    return names_file


def _read_block(
    path: Path, home: str, keys: tuple[str, ...], base_dir: Path, mapping_name: str,
) -> dict[str, object]:
    """One concern file's sections, refusing a key that belongs anywhere else."""
    label = path.relative_to(base_dir).as_posix()
    block = _require_mapping(read_yaml_document(path), label)
    for key in block:
        if key in keys:
            continue
        found = _home(key, base_dir, mapping_name)
        belongs = "" if found is None else f"; {key} belongs in {found}"
        raise MappingShapeError(
            f"{_where(path, base_dir, key)}: {home} holds {', '.join(keys)} only, "
            f"not {key}{belongs}",
        )
    return block


def _read_folder(
    folder: Path, keys: tuple[str, ...], base_dir: Path, mapping_name: str,
) -> tuple[dict[str, object], dict[str, Path]]:
    """The folder's files merged in name order, and the first file declaring each section."""
    merged: dict[str, object] = {}
    first: dict[str, Path] = {}
    owner: dict[tuple[str, object], Path] = {}
    for path in sorted(folder.iterdir(), key=lambda entry: entry.name):
        if path.suffix != ".yaml" or not path.is_file():
            raise MappingShapeError(
                f"{folder.name}/{path.name}: a concern folder holds .yaml files only",
            )
        block = _read_block(path, f"{folder.name}/", keys, base_dir, mapping_name)
        for key, value in block.items():
            if key not in merged:
                merged[key], first[key] = value, path
                if isinstance(value, dict):
                    owner.update({(key, name): path for name in value})
                continue
            held = merged[key]
            if not isinstance(held, dict) or not isinstance(value, dict):
                raise MappingShapeError(
                    f"{key} is declared in {_where(first[key], base_dir, key)} and "
                    f"{_where(path, base_dir, key)}",
                )
            for name, entry in cast("dict[object, object]", value).items():
                if (key, name) in owner:
                    raise MappingShapeError(
                        f"{key}[{name}] is declared in "
                        f"{_where(owner[key, name], base_dir, key, str(name))} and "
                        f"{_where(path, base_dir, key, str(name))}",
                    )
                cast("dict[object, object]", held)[name], owner[key, name] = entry, path
    return merged, first


def read_concern_files(mapping_path: Path, raw: Mapping[str, object]) -> dict[str, object]:
    """`raw` plus the sections read from each concern file or folder beside `mapping.yaml`."""
    if mapping_path.name != _MAPPING_FILE_NAME:
        # A folder may hold several mappings, as test/fixtures does; concern files belong to one.
        return dict(raw)
    base_dir = mapping_path.parent
    merged = dict(raw)
    for concern, keys in CONCERN_FILES.items():
        path = base_dir / concern
        folder = base_dir / f"{path.stem}.d"
        if path.is_file() and folder.is_dir():
            raise MappingShapeError(
                f"{concern} and {folder.name}/ both exist: "
                "a concern lives in one file or one folder.",
            )
        if _pointer_skips(concern, keys, path, folder, raw):
            continue
        if folder.is_dir():
            block, first = _read_folder(folder, keys, base_dir, mapping_path.name)
        elif path.is_file():
            block = _read_block(path, concern, keys, base_dir, mapping_path.name)
            first = dict.fromkeys(block, path)
        else:
            continue
        for key in block:
            if key in raw:
                raise MappingShapeError(
                    f"{key} is declared in {_where(mapping_path, base_dir, key)} and "
                    f"{_where(first[key], base_dir, key)}: a section lives in one place. Keep one.",
                )
        merged.update(block)
    return merged
