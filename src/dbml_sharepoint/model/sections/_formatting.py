# src/dbml_sharepoint/model/sections/_formatting.py
"""`style_theme`, `column_formatting` and `form_formatting`: the JSON
formatters a list renders with.

A column formatter declared as a dict with a 'style' key is a style spec
(fleet style standard, website/docs/reference/style-guide.md) expanded here
against the theme; a str stays a JSON file path and a plain dict an inline
formatter. Raw specs are kept for the validator's enum-map checks.
"""

from pathlib import Path
from typing import Any

from dbml_sharepoint.analysis import styles
from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.mapping_types import FormFormatting
from dbml_sharepoint.model.reading import load_json_value
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    style_theme = styles.parse_theme(sc.block("style_theme"), "style_theme")
    column_formatting: dict[str, dict[str, dict[str, Any]]] = {}
    column_style_specs: dict[str, dict[str, dict[str, Any]]] = {}
    for cf_entity, cf_cols in _require_mapping(
        sc.block("column_formatting"), "column_formatting",
    ).items():
        for cf_col, cf_value in _require_mapping(
            cf_cols, f"column_formatting.{cf_entity}",
        ).items():
            cf_ctx = f"column_formatting.{cf_entity}.{cf_col}"
            if isinstance(cf_value, dict) and "style" in cf_value:
                column_style_specs.setdefault(cf_entity, {})[cf_col] = dict(cf_value)
                expanded = styles.expand_style(cf_value, cf_ctx, theme=style_theme)
            else:
                expanded = load_json_value(sc.base_dir, cf_value, cf_ctx)
            column_formatting.setdefault(cf_entity, {})[cf_col] = expanded

    form_formatting = {
        entity: _parse_form_formatting(
            sc.base_dir, parts, f"form_formatting.{entity}",
        )
        for entity, parts in _require_mapping(
            sc.block("form_formatting"), "form_formatting",
        ).items()
    }

    return {
        "column_formatting": column_formatting,
        "column_style_specs": column_style_specs,
        "form_formatting": form_formatting,
    }


def _parse_form_formatting(base_dir: Path, parts: Any, context: str) -> FormFormatting:
    if not isinstance(parts, dict):
        raise ValueError(f"{context}: expected a mapping of header/body/footer parts")
    _reject_unknown_keys(parts, {"header", "body", "footer"}, context)
    loaded = {
        name: load_json_value(base_dir, value, f"{context}.{name}")
        for name, value in parts.items()
        if value is not None
    }
    if not loaded:
        raise ValueError(f"{context}: declare at least one of header/body/footer")
    # Every accepted part must be carried. Dropping one here is invisible:
    # `footer` was allow-listed, loaded and then discarded, so a declaration
    # validated clean, reported no findings and deployed nothing, and a
    # footer-only declaration passed the "at least one part" check above and
    # then emitted an empty formatter.
    return FormFormatting(
        header=loaded.get("header"),
        body=loaded.get("body"),
        footer=loaded.get("footer"),
    )
