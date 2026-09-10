# src/dbml_sharepoint/model/sections/_display_names.py
"""`display_names`: automatic display titles, and the overrides that win."""

from typing import Any

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    section = sc.block("display_names")
    mode = _parse_display_name_mode(section)
    overrides = {
        entity: {
            col: str(name)
            for col, name in _require_mapping(
                cols, f"display_names.overrides.{entity}",
            ).items()
        }
        for entity, cols in _require_mapping(
            _require_mapping(section, "display_names").get("overrides"),
            "display_names.overrides",
        ).items()
    }
    return {"display_name_mode": mode, "display_name_overrides": overrides}


def _parse_display_name_mode(section: Any) -> str | None:
    if section is None:
        return None
    _reject_unknown_keys(section, {"mode", "overrides"}, "display_names")
    mode = section.get("mode")
    if mode != "auto":
        raise ValueError(
            f"display_names.mode must be 'auto' (got {mode!r}); omit the "
            f"display_names section to leave display titles untouched",
        )
    return "auto"
