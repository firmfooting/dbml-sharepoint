# src/dbml_sharepoint/model/sections/_demo.py
"""`demo_items`: the sample rows `build --seed` writes into demo-data.js.txt.

Nothing in the deploy, rollback, assess or verify scripts reads them. The
loader checks each row's shape; the title marker, the value grammar and the
column semantics are the validator's, checked against the schema.
"""

from typing import Any

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.mapping_types import DemoItem
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    return {
        "demo_items": {
            entity: [
                _parse_demo_item(item, f"demo_items.{entity}[{i}]")
                for i, item in enumerate(items or [])
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
        raise ValueError(
            f"{context}: demo item must be a mapping, got {type(raw_item).__name__}",
        )
    _reject_unknown_keys(raw_item, {"key", "values"}, context)
    key = raw_item.get("key")
    if not key or not isinstance(key, str):
        raise ValueError(f"{context}: demo item 'key' is required (a string)")
    values = raw_item.get("values")
    if not isinstance(values, dict) or not values:
        raise ValueError(
            f"{context}: demo item 'values' must be a non-empty mapping of "
            f"column name to value",
        )
    return DemoItem(key=str(key), values={str(col): v for col, v in values.items()})
