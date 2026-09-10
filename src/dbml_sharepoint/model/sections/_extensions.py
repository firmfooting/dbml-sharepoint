# src/dbml_sharepoint/model/sections/_extensions.py
"""`extension` and `extensions`: which extension runs, and its configuration.

The blocks are passed through untyped. Selection by name is deferred to
`MappingBundle.extension_config_for` so it honours the RESOLVED extension: a
CLI `--extension` override may differ from the mapping's own `extension:`
key.
"""

from typing import Any

from dbml_sharepoint.model._keys import _require_mapping
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    extensions_block: dict[str, Any] = _require_mapping(
        sc.block("extensions"), "extensions",
    )
    return {
        "extension": sc.block("extension"),
        "extension_configs": {
            name: dict(block or {}) for name, block in extensions_block.items()
        },
    }
