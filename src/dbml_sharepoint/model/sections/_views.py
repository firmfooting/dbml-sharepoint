# src/dbml_sharepoint/model/sections/_views.py
"""`views` and `field_sets`, which exist to be pulled into a view's `fields`.

Expansion happens here, before anything downstream sees a view, so every
consumer from the retirement fold to jsgen reads a flat list of internal
column names.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

from dbml_sharepoint.analysis.typemap import TOTAL_FUNCTIONS
from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.conditions import parse_condition
from dbml_sharepoint.model.mapping_types import (
    VIEW_SCOPES,
    SortDirection,
    ViewDef,
    ViewGroupBy,
    ViewScope,
    ViewSort,
)
from dbml_sharepoint.model.reading import load_json_value, optional_bool, optional_int
from dbml_sharepoint.model.sections.context import SectionContext

_VIEW_KEYS = frozenset({
    "title", "renamed_from", "fields", "default", "where", "sort", "group_by",
    "row_limit", "formatting", "widths", "totals", "scope",
})


def read(sc: SectionContext) -> dict[str, Any]:
    field_sets = _parse_field_sets(sc.block("field_sets"))
    # Resolve "@setname" references BEFORE anything downstream sees a view.
    # Every consumer from here on (retirement folding, the validator,
    # jsgen) reads a flat list of internal column names.
    expanded_views = _expand_field_sets(
        {
            entity: [
                _parse_view(item, f"views.{entity}[{i}]", sc.base_dir)
                for i, item in enumerate(items or [])
            ]
            for entity, items in _require_mapping(sc.block("views"), "views").items()
        },
        field_sets,
    )
    return {"views": expanded_views, "field_sets": field_sets}


def _parse_view(raw_view: Any, context: str, base_dir: Path) -> ViewDef:
    """Parse one declared view. Structural checks only (title/fields present,
    sort direction shape); semantic rules need the schema and live in
    validate_against_mapping."""
    if not isinstance(raw_view, dict):
        raise ValueError(f"{context}: view must be a mapping, got {type(raw_view).__name__}")
    _reject_unknown_keys(raw_view, _VIEW_KEYS, context)
    title = raw_view.get("title")
    if not title:
        raise ValueError(f"{context}: view 'title' is required")
    fields = raw_view.get("fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(f, str) for f in fields):
        raise ValueError(f"{context}: view 'fields' must be a non-empty list of column names")
    renamed_from = raw_view.get("renamed_from") or []
    if not isinstance(renamed_from, list) or not all(
        isinstance(previous, str) for previous in renamed_from
    ):
        raise ValueError(f"{context}: 'renamed_from' must be a list of view titles")
    where = (
        parse_condition(raw_view["where"], f"{context}.where")
        if "where" in raw_view
        else None
    )
    sort: list[ViewSort] = []
    for i, entry in enumerate(raw_view.get("sort") or []):
        _reject_unknown_keys(entry, {"field", "direction"}, f"{context}.sort[{i}]")
        direction = str(entry.get("direction", "asc"))
        if direction not in {"asc", "desc"}:
            raise ValueError(
                f"{context}: sort direction must be 'asc' or 'desc', got {direction!r}",
            )
        sort.append(ViewSort(field=str(entry["field"]), direction=cast("SortDirection", direction)))
    raw_group = raw_view.get("group_by")
    group_by = None
    if raw_group is not None:
        _reject_unknown_keys(
            raw_group, {"field", "fields", "collapsed"}, f"{context}.group_by",
        )
        # Both spellings at once would need a precedence rule nobody would
        # remember, so it is an error rather than a silent winner.
        if ("field" in raw_group) == ("fields" in raw_group):
            raise ValueError(
                f"{context}.group_by: declare exactly one of 'field' (one level) "
                f"or 'fields' (one or two levels)",
            )
        raw_fields = (
            raw_group["fields"] if "fields" in raw_group else [raw_group["field"]]
        )
        if not isinstance(raw_fields, list) or not raw_fields:
            raise ValueError(
                f"{context}.group_by: 'fields' must be a non-empty list of column names",
            )
        # SharePoint's own ceiling. Dropping the third silently would answer
        # a declared grouping with a different one.
        if len(raw_fields) > 2:
            raise ValueError(
                f"{context}.group_by: SharePoint groups by at most two levels, "
                f"got {len(raw_fields)}",
            )
        group_by = ViewGroupBy(
            fields=[str(name) for name in raw_fields],
            collapsed=optional_bool(raw_group, "collapsed", f"{context}.group_by"),
        )
    raw_formatting = raw_view.get("formatting")
    raw_widths = raw_view.get("widths")
    widths: dict[str, int] = {}
    if raw_widths is not None:
        if not isinstance(raw_widths, dict):
            raise ValueError(
                f"{context}: 'widths' must be a mapping of column name to "
                f"pixel width, got {type(raw_widths).__name__}",
            )
        for col, px in raw_widths.items():
            if isinstance(px, bool) or not isinstance(px, int):
                raise ValueError(
                    f"{context}: widths[{col}] must be an integer pixel "
                    f"width, got {px!r}",
                )
            widths[str(col)] = px
    raw_scope = raw_view.get("scope")
    if raw_scope is not None and raw_scope not in VIEW_SCOPES:
        raise ValueError(
            f"{context}: scope must be one of {', '.join(sorted(VIEW_SCOPES))}, "
            f"got {raw_scope!r}",
        )
    raw_totals = raw_view.get("totals")
    totals: dict[str, str] = {}
    if raw_totals is not None:
        if not isinstance(raw_totals, dict):
            raise ValueError(
                f"{context}: 'totals' must be a mapping of column name to "
                f"aggregation, got {type(raw_totals).__name__}",
            )
        for col, func in raw_totals.items():
            if not isinstance(func, str) or func not in TOTAL_FUNCTIONS:
                raise ValueError(
                    f"{context}: totals[{col}] must be one of "
                    f"{', '.join(sorted(TOTAL_FUNCTIONS))}, got {func!r}",
                )
            totals[str(col)] = func
    return ViewDef(
        title=str(title),
        fields=[str(f) for f in fields],
        renamed_from=[str(previous) for previous in renamed_from],
        default=optional_bool(raw_view, "default", context),
        where=where,
        sort=sort,
        group_by=group_by,
        row_limit=optional_int(raw_view, "row_limit", context),
        formatting=(
            load_json_value(base_dir, raw_formatting, f"{context}.formatting")
            if raw_formatting is not None
            else None
        ),
        widths=widths,
        totals=totals,
        scope=cast("ViewScope | None", raw_scope),
    )


def _parse_field_sets(raw_sets: Any) -> dict[str, dict[str, list[str]]]:
    """Structural parse of the `field_sets:` section.

    Shape only: an unknown entity, an undeclared column, an '@' in a set
    name and an empty set are semantic and live in the validator, which
    reports them as findings beside the view checks. A declaration mistake
    should hand the operator a manifest full of findings, not a traceback.
    """
    parsed: dict[str, dict[str, list[str]]] = {}
    for entity, sets in _require_mapping(raw_sets, "field_sets").items():
        if not isinstance(sets, dict):
            raise ValueError(
                f"field_sets.{entity}: expected a mapping of set name to "
                f"column list, got {type(sets).__name__}",
            )
        parsed[str(entity)] = {}
        for set_name, columns in sets.items():
            if not isinstance(columns, list) or not all(
                isinstance(col, str) for col in columns
            ):
                raise ValueError(
                    f"field_sets.{entity}.{set_name}: expected a list of "
                    f"column names",
                )
            parsed[str(entity)][str(set_name)] = [str(col) for col in columns]
    return parsed


def _expand_field_sets(
    views: dict[str, list[ViewDef]],
    field_sets: dict[str, dict[str, list[str]]],
) -> dict[str, list[ViewDef]]:
    """Resolve every "@setname" entry in a view's `fields` into the columns
    that set declares, on the same entity.

    Expansion is in declaration order and duplicates are dropped keeping
    FIRST position, so ["@header", "BoardDate"] is a no-op rather than an
    error. Sets do NOT nest (one level only, deliberately): a set member
    that itself looks like a reference is left literal and the validator
    reports it. An "@name" with no matching set on the entity is likewise
    left in place untouched, so nothing is silently dropped; the validator
    names it and cli.py aborts before jsgen is ever reached.

    Applies to `fields` ONLY. `widths`, `sort`, `group_by` and `where`
    continue to name columns directly. A set has no meaningful expansion
    there.

    Runs BEFORE _apply_retirement so retirement filters the already-expanded
    list: a view that pulls in a set containing a retired column must end up
    without that column.
    """
    expanded: dict[str, list[ViewDef]] = {}
    for entity, entity_views in views.items():
        sets = field_sets.get(entity, {})
        rebuilt: list[ViewDef] = []
        for view in entity_views:
            fields: list[str] = []
            seen: set[str] = set()
            used: list[str] = []
            for entry in view.fields:
                if entry.startswith("@") and entry[1:] in sets:
                    set_name = entry[1:]
                    if set_name not in used:
                        used.append(set_name)
                    members = sets[set_name]
                else:
                    members = [entry]
                for name in members:
                    if name not in seen:
                        seen.add(name)
                        fields.append(name)
            rebuilt.append(replace(view, fields=fields, expanded_sets=used))
        expanded[entity] = rebuilt
    return expanded
