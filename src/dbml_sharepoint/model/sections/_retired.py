# src/dbml_sharepoint/model/sections/_retired.py
"""`retired_columns`, the authoritative retirement record.

Parsed here and folded into the other sections by
`_retirement._apply_retirement` once the whole mapping is built, because the
fold rewrites views, forms and display names that other families produce.
"""

from typing import Any

from dbml_sharepoint.model._keys import _require_mapping
from dbml_sharepoint.model._retirement import _parse_retired_columns
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    return {
        "retired_columns": {
            entity: _parse_retired_columns(cols, f"retired_columns.{entity}")
            for entity, cols in _require_mapping(
                sc.block("retired_columns"), "retired_columns",
            ).items()
        },
    }
