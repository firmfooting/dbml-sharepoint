# src/dbml_sharepoint/model/sections/_forms.py
"""`form_visibility`, `column_validation` and `list_validation`: what a form
shows and what a save requires.

All three carry condition trees. They are parsed here for shape and
diagnosed by the validator, which has the schema the operators need.
"""

from typing import Any

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.conditions import parse_condition
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    FormVisibility,
    ListValidation,
)
from dbml_sharepoint.model.reading import strict_bool
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    return {
        "form_visibility": {
            entity: _parse_form_visibility(block, f"form_visibility.{entity}")
            for entity, block in _require_mapping(
                sc.block("form_visibility"), "form_visibility",
            ).items()
        },
        "column_validation": {
            entity: _parse_column_validation(block, f"column_validation.{entity}")
            for entity, block in _require_mapping(
                sc.block("column_validation"), "column_validation",
            ).items()
        },
        "list_validation": {
            entity: _parse_list_validation(rule, f"list_validation.{entity}")
            for entity, rule in _require_mapping(
                sc.block("list_validation"), "list_validation",
            ).items()
        },
    }


def _entity_section(block: Any, context: str) -> tuple[str, dict[str, Any]]:
    if not isinstance(block, dict):
        raise ValueError(f"{context}: expected a mapping with 'columns'")
    _reject_unknown_keys(block, {"reconcile", "columns"}, context)
    reconcile = str(block.get("reconcile", "exact"))
    if reconcile not in ("exact", "declared"):
        raise ValueError(
            f"{context}.reconcile: expected 'exact' or 'declared', got {reconcile!r}",
        )
    columns = block.get("columns")
    if columns is None:
        columns = {}
    if not isinstance(columns, dict):
        raise ValueError(f"{context}.columns: expected a mapping of column name to declaration")
    return reconcile, columns


def _parse_form_visibility(block: Any, context: str) -> EntitySection[FormVisibility]:
    reconcile, raw_columns = _entity_section(block, context)
    columns: dict[str, FormVisibility] = {}
    for name, raw in raw_columns.items():
        where = f"{context}.columns.{name}"
        if isinstance(raw, str):
            if raw not in ("hidden", "visible"):
                raise ValueError(
                    f"{where}: expected 'hidden', 'visible' or a mapping, got {raw!r}",
                )
            columns[name] = FormVisibility(new=raw == "visible", existing=raw == "visible")
            continue
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: expected 'hidden', 'visible' or a mapping")
        _reject_unknown_keys(raw, {"new", "existing", "when"}, where)
        columns[name] = FormVisibility(
            new=strict_bool(raw, "new", where),
            existing=strict_bool(raw, "existing", where),
            # An empty `when` is a mistake, not an absence. The same
            # declaration errors in column_validation and as an empty group.
            when=parse_condition(raw["when"], f"{where}.when") if "when" in raw else None,
        )
    return EntitySection(reconcile=reconcile, columns=columns)


def _parse_column_validation(block: Any, context: str) -> EntitySection[ColumnValidation]:
    reconcile, raw_columns = _entity_section(block, context)
    columns: dict[str, ColumnValidation] = {}
    for name, raw in raw_columns.items():
        where = f"{context}.columns.{name}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: expected a mapping with 'when' and 'message'")
        _reject_unknown_keys(raw, {"when", "message"}, where)
        for key in ("when", "message"):
            if not raw.get(key):
                raise ValueError(
                    f"{where}: {key!r} is required -- a rule with no message fails the save "
                    f"with SharePoint's generic text, which tells the author nothing",
                )
        columns[name] = ColumnValidation(
            when=parse_condition(raw["when"], f"{where}.when"),
            message=str(raw["message"]),
        )
    return EntitySection(reconcile=reconcile, columns=columns)


def _parse_list_validation(rule: Any, context: str) -> ListValidation:
    if not isinstance(rule, dict):
        raise ValueError(f"{context}: expected a mapping with 'when' and 'message'")
    unknown = set(rule) - {"when", "message"}
    if "formula" in unknown:
        raise ValueError(
            f"{context}: 'formula' has been replaced by 'when', which takes a condition "
            f"tree instead of a SharePoint formula:\n"
            f"\n"
            f"    list_validation:\n"
            f"      <Entity>:\n"
            f"        when:\n"
            f"          - {{ field: <Column>, op: is_not_null }}\n"
            f"        message: \"<shown to the person whose save failed>\"\n"
            f"\n"
            f"See the condition grammar reference for the operator vocabulary.",
        )
    if unknown:
        raise ValueError(f"{context}: unknown key(s) {sorted(unknown)}")
    for key in ("when", "message"):
        if not rule.get(key):
            raise ValueError(f"{context}: {key!r} is required")
    return ListValidation(
        when=parse_condition(rule["when"], f"{context}.when"),
        message=str(rule["message"]),
    )
