# src/dbml_sharepoint/model/sections/_demo.py
"""`demo_items`: the sample rows `build --seed` writes into demo-data.js.txt.

Nothing in the deploy, rollback, assess or verify scripts reads them, which
is why `demo_source` may move the section to a file beside the mapping, on
the rule the reporting split set: the seam is what consumes a section rather
than how long it is. The loader checks each row's shape; the title marker,
the value grammar and the column semantics are the validator's, checked
against the schema.
"""

from typing import Any

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_list, _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_types import DEMO_FILE_CONTENT, DemoFile, DemoItem
from dbml_sharepoint.model.reading import optional_str, require_str, strict_str
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    return {
        "demo_items": {
            entity: [
                _parse_demo_item(item, f"demo_items.{entity}[{i}]")
                for i, item in enumerate(_require_list(items, f"demo_items.{entity}"))
            ]
            for entity, items in _require_mapping(
                sc.block("demo_items"), "demo_items",
            ).items()
        },
    }


def _parse_demo_item(raw_item: Any, context: str) -> DemoItem:
    """Structural parse of one demo row (title marker, value grammar and
    column semantics are validated against the schema in the validator)."""
    if not isinstance(raw_item, dict):
        raise MappingShapeError(
            f"{context}: demo item must be a mapping, got {type(raw_item).__name__}",
        )
    _reject_unknown_keys(raw_item, {"key", "values", "file"}, context)
    key = raw_item.get("key")
    if not key or not isinstance(key, str):
        raise MappingShapeError(f"{context}: demo item 'key' is required (a string)")
    values = raw_item.get("values")
    if not isinstance(values, dict) or not values:
        raise MappingShapeError(
            f"{context}: demo item 'values' must be a non-empty mapping of "
            f"column name to value",
        )
    value_map: dict[object, object] = values
    return DemoItem(
        key=key,
        values={str(col): v for col, v in value_map.items()},
        file=_parse_demo_file(raw_item.get("file"), f"{context}.file"),
    )


def _parse_demo_file(raw_file: Any, context: str) -> DemoFile | None:
    """Structural parse of `file:`; that the entity is a library, the folder
    is declared and the name is legal are the validator's."""
    if raw_file is None:
        return None
    if not isinstance(raw_file, dict):
        raise MappingShapeError(
            f"{context}: must be a mapping with 'name', got {type(raw_file).__name__}",
        )
    _reject_unknown_keys(raw_file, {"name", "folder", "content"}, context)
    if "name" not in raw_file:
        raise MappingShapeError(f"{context}: 'name' is required, the file name to upload")
    return DemoFile(
        name=require_str(raw_file, "name", context),
        folder=optional_str(raw_file, "folder", context),
        # `strict_str`: the fallback is a body of text, so `content:` with
        # nothing after it must not silently upload the sample paragraph.
        content=strict_str(raw_file, "content", context, default=DEMO_FILE_CONTENT),
    )
