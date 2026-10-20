# src/dbml_sharepoint/model/sections/_form_file.py
"""`form.yaml`: the whole form of each entity in one file beside the mapping.

It is keyed by entity, and each entity holds `header`, `body`, `footer` and
`visibility`. This module only reshapes the file into the raw `form_formatting`
and `form_visibility` blocks the existing readers take, so validation and
generation see no difference. A header or footer written as a component tree
is not JSON, so it travels separately as `trees`.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from dbml_sharepoint.model._keys import _known_keys, _require_mapping, _text_key
from dbml_sharepoint.model.errors import MappingReferenceError, MappingShapeError
from dbml_sharepoint.model.mapping_types import FormFormatting
from dbml_sharepoint.model.reading import load_yaml

FORM_FILE_NAME = "form.yaml"
_PARTS = frozenset({"header", "body", "footer", "visibility"})
_TREE_PARTS = ("header", "footer")

#: A header or footer component tree as written, shape-checked only.
RawTree = Mapping[str, object]


@dataclass(frozen=True)
class FormFileBlocks:
    form_formatting: dict[str, object] = field(default_factory=dict)
    form_visibility: dict[str, object] = field(default_factory=dict)
    # entity -> `header` or `footer` -> component tree
    trees: dict[str, dict[str, RawTree]] = field(default_factory=dict)
    present: bool = False

    def sections(self) -> dict[str, object]:
        """The raw `form_formatting` and `form_visibility` blocks, or none without a file."""
        if not self.present:
            return {}
        return {"form_formatting": self.form_formatting, "form_visibility": self.form_visibility}

    def add_tree_only_entities(self, formatting: dict[str, FormFormatting]) -> None:
        """A tree-only entity has no JSON part for the formatting reader to take."""
        for entity in self.trees:
            formatting.setdefault(entity, FormFormatting())


def _header_part(raw: object, context: str) -> RawTree:
    """The one place a header/footer component tree is read."""
    return _require_mapping(raw, context)


def _file_pointer(raw: object, context: str) -> str | None:
    """The path of `{file: <path>}`, or None when `raw` is not that form."""
    if not isinstance(raw, dict) or "file" not in raw:
        return None
    path = _known_keys(raw, {"file"}, context)["file"]
    if not isinstance(path, str) or not path:
        raise MappingShapeError(f"{context}.file: expected a path to a JSON file")
    return path


def _refuse_clash(raw: Mapping[str, object]) -> None:
    for key in ("form_formatting", "form_visibility"):
        if key in raw:
            raise MappingReferenceError(
                f"mapping.yaml declares {key} and {FORM_FILE_NAME} exists beside it: "
                f"the form lives in one place. Move the {key} section into "
                f"{FORM_FILE_NAME}.",
            )


def _read_entity(
    entity: str, block: object,
) -> tuple[dict[str, object], object, dict[str, RawTree]]:
    """One entity's raw formatting parts, visibility block and component trees."""
    context = f"{FORM_FILE_NAME}.{entity}"
    parts = {k: v for k, v in _known_keys(block, _PARTS, context).items() if v is not None}
    if not parts:
        raise MappingShapeError(
            f"{context}: declare at least one of header/body/footer/visibility",
        )
    formatting: dict[str, object] = {}
    trees: dict[str, RawTree] = {}
    for part, value in parts.items():
        where = f"{context}.{part}"
        pointer = _file_pointer(value, where)
        if pointer is not None and part != "visibility":
            formatting[part] = pointer
        elif part in _TREE_PARTS:
            trees[part] = _header_part(value, where)
        elif part == "body":
            formatting[part] = value  # an inline body
    return formatting, parts.get("visibility"), trees


def read_form_file(base_dir: Path, raw: Mapping[str, object]) -> FormFileBlocks:
    path = base_dir / FORM_FILE_NAME
    if not path.is_file():
        return FormFileBlocks()
    _refuse_clash(raw)
    form = FormFileBlocks(present=True)
    for key, block in load_yaml(path).items():
        entity = _text_key(key, FORM_FILE_NAME)
        formatting, visibility, trees = _read_entity(entity, block)
        if formatting:
            form.form_formatting[entity] = formatting
        if visibility is not None:
            form.form_visibility[entity] = visibility
        if trees:
            form.trees[entity] = trees
    return form
