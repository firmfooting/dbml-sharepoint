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
from dbml_sharepoint.model._keys import _known_keys, _require_list, _require_mapping, _text_key
from dbml_sharepoint.model.conditions import parse_condition
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.mapping_types import (
    VIEW_SCOPES,
    SortDirection,
    ViewDef,
    ViewGroupBy,
    ViewScope,
    ViewSort,
)
from dbml_sharepoint.model.reading import (
    load_json_value,
    optional_bool,
    optional_int,
    optional_str,
    optional_str_list,
    optional_value,
    require_str,
    strict_str,
)
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
                for i, item in enumerate(_require_list(items, f"views.{entity}"))
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
        raise MappingShapeError(f"{context}: view must be a mapping, got {type(raw_view).__name__}")
    view = _known_keys(raw_view, _VIEW_KEYS, context)
    # The type before the presence, because `str()` made `title: [All]` the title "['All']".
    title = optional_str(view, "title", context)
    if not title:
        raise MappingShapeError(f"{context}: view 'title' is required")
    fields = view.get("fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(f, str) for f in fields):
        raise MappingShapeError(
            f"{context}: view 'fields' must be a non-empty list of column names",
        )
    field_names: list[str] = fields
    # Only a blank is absent here and for `sort`: `or` read `renamed_from: 0` as none.
    renamed_from = view.get("renamed_from")
    if renamed_from is None:
        renamed_from = list[str]()
    if not isinstance(renamed_from, list) or not all(
        isinstance(previous, str) for previous in renamed_from
    ):
        raise MappingShapeError(f"{context}: 'renamed_from' must be a list of view titles")
    previous_titles: list[str] = renamed_from
    # A blank `where:` is an unfiltered view, which the load records.
    raw_where = optional_value(view, "where", context)
    where = parse_condition(raw_where, f"{context}.where") if raw_where is not None else None
    raw_sort = view.get("sort")
    if raw_sort is None:
        raw_sort = list[object]()
    # A mapping or a string iterated as keys or characters, and a number raised TypeError.
    if not isinstance(raw_sort, list):
        raise MappingShapeError(f"{context}.sort must be a list, got {raw_sort!r}")
    sort_entries: list[object] = raw_sort
    sort: list[ViewSort] = []
    for i, raw_entry in enumerate(sort_entries):
        entry = _known_keys(raw_entry, {"field", "direction"}, f"{context}.sort[{i}]")
        # The shape before the word, as `scope` below does: a list here is
        # not a direction spelled wrongly. `strict_str` so a blank is recorded.
        direction = strict_str(entry, "direction", f"{context}.sort[{i}]", default="asc")
        if direction not in {"asc", "desc"}:
            raise MappingValueError(
                f"{context}: sort direction must be 'asc' or 'desc', got {direction!r}",
            )
        sort.append(ViewSort(
            field=require_str(entry, "field", f"{context}.sort[{i}]"),
            direction=cast("SortDirection", direction),
        ))
    raw_group = view.get("group_by")
    group_by = None
    if raw_group is not None:
        group = _known_keys(
            raw_group, {"field", "fields", "collapsed"}, f"{context}.group_by",
        )
        # Both spellings at once would need a precedence rule nobody would
        # remember, so it is an error rather than a silent winner. A blank
        # one reads as absent, so it is not a second spelling.
        spellings = [key for key in ("field", "fields") if group.get(key) is not None]
        if len(spellings) != 1:
            raise MappingShapeError(
                f"{context}.group_by: declare exactly one of 'field' (one level) "
                f"or 'fields' (one or two levels)",
            )
        # Read as text, because `str()` grouped `field: [Status]` by "['Status']".
        group_fields = (
            list(optional_str_list(group, "fields", f"{context}.group_by"))
            if spellings == ["fields"]
            else [require_str(group, "field", f"{context}.group_by")]
        )
        if not group_fields:
            raise MappingShapeError(
                f"{context}.group_by: 'fields' must be a non-empty list of column names",
            )
        # SharePoint's own ceiling. Dropping the third silently would answer
        # a declared grouping with a different one.
        if len(group_fields) > 2:
            raise MappingShapeError(
                f"{context}.group_by: SharePoint groups by at most two levels, "
                f"got {len(group_fields)}",
            )
        group_by = ViewGroupBy(
            fields=group_fields,
            collapsed=optional_bool(group, "collapsed", f"{context}.group_by"),
        )
    raw_formatting = view.get("formatting")
    raw_widths = view.get("widths")
    widths: dict[str, int] = {}
    if raw_widths is not None:
        if not isinstance(raw_widths, dict):
            raise MappingShapeError(
                f"{context}: 'widths' must be a mapping of column name to "
                f"pixel width, got {type(raw_widths).__name__}",
            )
        width_map: dict[object, object] = raw_widths
        for raw_col, px in width_map.items():
            col = _text_key(raw_col, f"{context}.widths")
            if isinstance(px, bool) or not isinstance(px, int):
                raise MappingShapeError(
                    f"{context}: widths[{col}] must be an integer pixel "
                    f"width, got {px!r}",
                )
            widths[col] = px
    raw_scope = optional_value(view, "scope", context)
    # isinstance first: a list or mapping is unhashable, and `in` over a
    # frozenset would raise the TypeError the CLI does not catch. Two
    # refusals rather than one, because the wrong YAML type is a shape error
    # and a string outside the vocabulary is a value error.
    if raw_scope is not None and not isinstance(raw_scope, str):
        raise MappingShapeError(
            f"{context}: scope must be a string, got {type(raw_scope).__name__}",
        )
    if raw_scope is not None and raw_scope not in VIEW_SCOPES:
        raise MappingValueError(
            f"{context}: scope must be one of {', '.join(sorted(VIEW_SCOPES))}, "
            f"got {raw_scope!r}",
        )
    raw_totals = view.get("totals")
    totals: dict[str, str] = {}
    if raw_totals is not None:
        if not isinstance(raw_totals, dict):
            raise MappingShapeError(
                f"{context}: 'totals' must be a mapping of column name to "
                f"aggregation, got {type(raw_totals).__name__}",
            )
        total_map: dict[object, object] = raw_totals
        for raw_col, func in total_map.items():
            col = _text_key(raw_col, f"{context}.totals")
            # Split for the same reason `scope` is: a non-string is a shape.
            if not isinstance(func, str):
                raise MappingShapeError(
                    f"{context}: totals[{col}] must be a string, got "
                    f"{type(func).__name__}",
                )
            if func not in TOTAL_FUNCTIONS:
                raise MappingValueError(
                    f"{context}: totals[{col}] must be one of "
                    f"{', '.join(sorted(TOTAL_FUNCTIONS))}, got {func!r}",
                )
            totals[col] = func
    return ViewDef(
        title=title,
        fields=list(field_names),
        renamed_from=list(previous_titles),
        default=optional_bool(view, "default", context),
        where=where,
        sort=sort,
        group_by=group_by,
        row_limit=optional_int(view, "row_limit", context, record_blank=True),
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
        # A blank entity block reads as absent: that entity declares no sets.
        if sets is None:
            continue
        if not isinstance(sets, dict):
            raise MappingShapeError(
                f"field_sets.{entity}: expected a mapping of set name to "
                f"column list, got {type(sets).__name__}",
            )
        parsed[entity] = {}
        set_map: dict[object, object] = sets
        for raw_set_name, columns in set_map.items():
            set_name = _text_key(raw_set_name, f"field_sets.{entity}")
            if not isinstance(columns, list) or not all(
                isinstance(col, str) for col in columns
            ):
                raise MappingShapeError(
                    f"field_sets.{entity}.{set_name}: expected a list of "
                    f"column names",
                )
            column_names: list[str] = columns
            parsed[entity][set_name] = list(column_names)
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
