# src/dbml_sharepoint/model/sections/_forms.py
"""`form_visibility`, `column_validation` and `list_validation`: what a form
shows and what a save requires.

All three carry condition trees. They are parsed here for shape and
diagnosed by the validator, which has the schema the operators need.
"""

from collections.abc import Mapping
from typing import Any

from dbml_sharepoint.model._keys import (
    _known_keys,
    _reject_unknown_keys,
    _require_mapping,
    _text_key,
)
from dbml_sharepoint.model.conditions import Condition, parse_condition
from dbml_sharepoint.model.errors import (
    MappingShapeError,
    MappingValueError,
    UnknownMappingKeyError,
)
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    FormVisibility,
    ListValidation,
)
from dbml_sharepoint.model.reading import optional_str, optional_value, strict_bool, strict_str
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    # A blank entity block reads as absent: that entity declares nothing here.
    return {
        "form_visibility": {
            entity: _parse_form_visibility(block, f"form_visibility.{entity}")
            for entity, block in _require_mapping(
                sc.block("form_visibility"), "form_visibility",
            ).items() if block is not None
        },
        "column_validation": {
            entity: _parse_column_validation(block, f"column_validation.{entity}")
            for entity, block in _require_mapping(
                sc.block("column_validation"), "column_validation",
            ).items() if block is not None
        },
        "list_validation": {
            entity: _parse_list_validation(rule, f"list_validation.{entity}")
            for entity, rule in _require_mapping(
                sc.block("list_validation"), "list_validation",
            ).items() if rule is not None
        },
    }


def _entity_section(block: Any, context: str) -> tuple[str, dict[str, Any]]:
    if not isinstance(block, dict):
        raise MappingShapeError(f"{context}: expected a mapping with 'columns'")
    _reject_unknown_keys(block, {"reconcile", "columns"}, context)
    # The shape first: `reconcile: [exact]` is the wrong shape, and `str()`
    # on it reported "['exact']" as a word this loader declined. `strict_str`
    # records a blank `reconcile:`, which takes 'exact'.
    reconcile = strict_str(block, "reconcile", context, default="exact")
    if reconcile not in ("exact", "declared"):
        raise MappingValueError(
            f"{context}.reconcile: expected 'exact' or 'declared', got {reconcile!r}",
        )
    columns = block.get("columns")
    if columns is None:
        columns = dict[str, Any]()
    if not isinstance(columns, dict):
        raise MappingShapeError(
            f"{context}.columns: expected a mapping of column name to declaration",
        )
    for name in columns:
        _text_key(name, f"{context}.columns")
    return reconcile, columns


def _parse_form_visibility(block: Any, context: str) -> EntitySection[FormVisibility]:
    reconcile, raw_columns = _entity_section(block, context)
    columns: dict[str, FormVisibility] = {}
    for name, raw in raw_columns.items():
        where = f"{context}.columns.{name}"
        if isinstance(raw, str):
            if raw not in ("hidden", "visible"):
                raise MappingValueError(
                    f"{where}: expected 'hidden', 'visible' or a mapping, got {raw!r}",
                )
            columns[name] = FormVisibility(new=raw == "visible", existing=raw == "visible")
            continue
        if not isinstance(raw, dict):
            raise MappingShapeError(f"{where}: expected 'hidden', 'visible' or a mapping")
        declared = _known_keys(raw, {"new", "existing", "when"}, where)
        # A blank `when:` shows the column unconditionally, which the load records.
        raw_when = optional_value(declared, "when", where)
        columns[name] = FormVisibility(
            new=strict_bool(declared, "new", where),
            existing=strict_bool(declared, "existing", where),
            when=parse_condition(raw_when, f"{where}.when") if raw_when is not None else None,
        )
    return EntitySection(reconcile=reconcile, columns=columns)


def _parse_column_validation(block: Any, context: str) -> EntitySection[ColumnValidation]:
    reconcile, raw_columns = _entity_section(block, context)
    columns: dict[str, ColumnValidation] = {}
    for name, raw in raw_columns.items():
        where = f"{context}.columns.{name}"
        if not isinstance(raw, dict):
            raise MappingShapeError(f"{where}: expected a mapping with 'when' and 'message'")
        declared = _known_keys(raw, {"when", "message"}, where)
        when, message = _rule(declared, where, _NO_MESSAGE)
        columns[name] = ColumnValidation(when=when, message=message)
    return EntitySection(reconcile=reconcile, columns=columns)


_NO_MESSAGE = (
    " -- a rule with no message fails the save with SharePoint's generic text, "
    "which tells the author nothing"
)


def _rule(declared: Mapping[str, object], context: str, why: str = "") -> tuple[Condition, str]:
    """A validation rule's `when` and `message`, each typed before it is required.

    Presence was tested first, so `message: false` or `0` was reported as
    missing. Only an absent, blank or empty value is; any other value of the
    wrong type is named as that. `str()` showed `message: [x]` to the person
    whose save failed as "['x']".
    """
    message = optional_str(declared, "message", context)
    when = declared.get("when")
    # An empty tree is no condition; any other wrong type is `parse_condition`'s to name.
    if when is None or when == [] or when == {}:
        raise MappingShapeError(f"{context}: 'when' is required{why}")
    if not message:
        raise MappingShapeError(f"{context}: 'message' is required{why}")
    return parse_condition(when, f"{context}.when"), message


def _parse_list_validation(rule: Any, context: str) -> ListValidation:
    if not isinstance(rule, dict):
        raise MappingShapeError(f"{context}: expected a mapping with 'when' and 'message'")
    entries: dict[object, object] = rule
    unknown = {_text_key(key, context) for key in entries} - {"when", "message"}
    if "formula" in unknown:
        raise UnknownMappingKeyError(
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
        raise UnknownMappingKeyError(f"{context}: unknown key(s) {sorted(unknown)}")
    declared: dict[str, object] = rule
    when, message = _rule(declared, context)
    return ListValidation(when=when, message=message)
