# src/dbml_sharepoint/model/sections/_extensions.py
"""`extension` and `extensions`: which extension runs, and its configuration.

Each block must be a mapping, and what it holds is passed through untyped,
because only the extension knows its own keys. Selection by name is deferred to
`MappingBundle.extension_config_for` so it honours the RESOLVED extension: a
CLI `--extension` override may differ from the mapping's own `extension:`
key.
"""

from typing import Any

from dbml_sharepoint.model._keys import _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.reading import optional_str
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    extensions_block: dict[str, Any] = _require_mapping(
        sc.block("extensions"), "extensions",
    )
    return {
        # Refused as the wrong type here, where a list was reported as an unknown extension.
        "extension": optional_str(sc.blocks, "extension", "mapping"),
        "extension_configs": {
            name: _extension_config(block, f"extensions.{name}")
            for name, block in extensions_block.items()
        },
    }


def _extension_config(block: object, context: str) -> dict[Any, Any]:
    """One extension's block, as written: only the extension knows its keys.

    `dict()` loaded `[on]` as `{"o": "n"}` and raised a bare error on any
    other list or a scalar. Not `_require_mapping`, which rewrites a key that
    is not text, and the reference promises the block reaches the extension
    untouched. A blank block is an empty one.
    """
    if block is None:
        return {}
    if not isinstance(block, dict):
        raise MappingShapeError(f"{context}: expected a mapping, got {type(block).__name__}")
    config: dict[Any, Any] = block
    return dict(config)
