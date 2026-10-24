"""Split a `mapping.yaml` into its concern files, as text.

Each top-level block moves verbatim, with the comments above it, so comments
and quoting survive and the operator reviews a move rather than a rewrite.
The pieces are parsed back and compared with the mapping before anything is
written. The concern files are written first and the mapping is replaced
last, in one rename: a failed write leaves a section in two homes, which the
loader refuses, never in none.
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from dbml_sharepoint.bundle import write_artifact
from dbml_sharepoint.model.errors import MappingError
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.sections._concern_files import CONCERN_FILES
from dbml_sharepoint.model.yamlio import PARSE_ERRORS, safe_load

_MAPPING = "mapping.yaml"
_KEY_LINE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)[ \t]*:(?:[ \t]|$)")
_HOMES = {key: concern for concern, keys in CONCERN_FILES.items() for key in keys}


class SplitRefusedError(Exception):
    """The converter's one refusal. Its text is the operator's message; nothing was written."""


@dataclass(frozen=True)
class SplitPlan:
    """What a split would write, and which keys it would move."""

    #: File name to its full new text: `mapping.yaml` first, then concern files in order.
    texts: dict[str, str]
    #: Concern file to the keys moved into it, in source order. Empty means nothing to split.
    moved: dict[str, tuple[str, ...]]


def _cut(lines: list[str]) -> list[tuple[str | None, list[str]]]:
    """The header (key None), then each top-level block with the comments directly above it."""
    keys = [(i, match[1]) for i, line in enumerate(lines) if (match := _KEY_LINE.match(line))]
    starts: list[int] = []
    for n, (i, _key) in enumerate(keys):
        start = i
        # The first key takes nothing from above: that is the header.
        while n and start - 1 > keys[n - 1][0] and (
            not lines[start - 1].strip() or lines[start - 1].startswith("#")
        ):
            start -= 1
        starts.append(start)
    ends = [*starts[1:], len(lines)]
    header = lines[: starts[0]] if starts else lines
    spans = zip(keys, starts, ends, strict=True)
    blocks = [(key, lines[start:end]) for (_i, key), start, end in spans]
    return [(None, header), *blocks]


def _text(lines: list[str]) -> str:
    """`lines` without blank lines at either end, ending in one newline."""
    kept = [i for i, line in enumerate(lines) if line.strip()]
    return "\n".join(lines[kept[0] : kept[-1] + 1]) + "\n" if kept else "\n"


def _verify(source: str, texts: dict[str, str]) -> dict[str, tuple[str, ...]]:
    """Each piece's keys, refusing pieces that do not each parse and together read as `source`."""
    mismatch = SplitRefusedError(
        "the split does not read back as the same mapping; nothing was written",
    )
    union: dict[object, object] = {}
    keys: dict[str, tuple[str, ...]] = {}
    for name, text in texts.items():
        try:
            data = safe_load(text)
        except PARSE_ERRORS as error:
            raise SplitRefusedError(
                f"{name} would not parse on its own, most likely an alias whose anchor "
                f"stays in another file: {error}",
            ) from error
        if not isinstance(data, dict):
            raise mismatch
        # A key line the pattern missed rides in the block above it, into the wrong file.
        block = cast("dict[object, object]", data)
        if any(_HOMES.get(str(key), _MAPPING) != name for key in block):
            raise mismatch
        union.update(block)
        keys[name] = tuple(str(key) for key in block)
    if union != safe_load(source):
        raise mismatch
    return keys


def plan_split(mapping_path: Path) -> SplitPlan:
    """What splitting `mapping_path` would write, verified. Writes nothing."""
    if mapping_path.name != _MAPPING:
        raise SplitRefusedError(
            f"{mapping_path.name}: only a file named mapping.yaml is split, "
            "because its concern files are read by every mapping in its folder",
        )
    try:
        load_mapping(mapping_path)
    except MappingError as error:
        raise SplitRefusedError(f"{mapping_path} must load before it is split: {error}") from error
    source = mapping_path.read_text(encoding="utf-8")
    files: dict[str, list[str]] = {_MAPPING: []}
    moved: dict[str, list[str]] = {}
    for key, block in _cut(source.split("\n")):
        home = _MAPPING if key is None else _HOMES.get(key, _MAPPING)
        files.setdefault(home, []).extend(block)
        if home != _MAPPING:
            moved.setdefault(home, []).append(str(key))
    base_dir = mapping_path.parent
    for concern, keys in moved.items():
        folder = base_dir / f"{Path(concern).stem}.d"
        if (base_dir / concern).exists() or folder.exists():
            found = f"{folder.name}/" if folder.exists() else concern
            raise SplitRefusedError(
                f"{found} already exists; move {', '.join(keys)} into it by hand",
            )
    texts = {name: _text(files[name]) for name in (_MAPPING, *CONCERN_FILES) if name in files}
    # From the parsed pieces, so a key line the pattern missed is still reported.
    parsed = _verify(source, texts)
    return SplitPlan(texts=texts, moved={name: parsed[name] for name in texts if name != _MAPPING})


def split_mapping(mapping_path: Path) -> dict[str, tuple[str, ...]]:
    """Split `mapping_path` into its concern files and return the keys moved into each."""
    plan = plan_split(mapping_path)
    if plan.moved:
        for name in plan.moved:
            write_artifact(mapping_path.parent / name, plan.texts[name])
        # Replaced in one rename, so a failed write never truncates the sections that stay.
        temp = mapping_path.with_name(f".{_MAPPING}.split")
        try:
            write_artifact(temp, plan.texts[_MAPPING])
            temp.replace(mapping_path)
        finally:
            temp.unlink(missing_ok=True)
    return plan.moved
