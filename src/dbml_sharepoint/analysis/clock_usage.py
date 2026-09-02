# src/dbml_sharepoint/analysis/clock_usage.py
"""Which clock cells a pack uses, and where.

One scan, read by two scripts: the assess script asks whether the site's
time zone matters to this pack, and the verify script asks which cells to
exercise on its scratch list. Generators may not import `analysis/checks/`,
so the scan lives beside the cell table it classifies against.
"""
from __future__ import annotations

from collections.abc import Iterable
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass

from dbml_sharepoint.analysis.clock_cells import cell_for, sentinel_of
from dbml_sharepoint.analysis.column_projection import SYSTEM_COLUMN_TYPES
from dbml_sharepoint.analysis.condition_rendering import CAML, VALIDATION
from dbml_sharepoint.analysis.conditions import leaves
from dbml_sharepoint.analysis.typemap import DATE_TYPES, TODAY_SENTINEL
from dbml_sharepoint.model.mapping_types import Mapping
from dbml_sharepoint.model.parser import Schema

TODAY_DEFAULT = "[today]"


@dataclass(frozen=True)
class TodayDefault:
    """A column whose default is SharePoint's dynamic `[today]`."""

    entity: str
    column: str
    column_kind: str


@dataclass(frozen=True)
class ClockUsage:
    #: Cell id (see `clock_cells.ClockCell.id`) to the day offsets the pack
    #: uses it with; 0 for bare `today` and for `now`.
    cells: MappingABC[str, frozenset[int]]
    today_defaults: tuple[TodayDefault, ...]

    @property
    def uses_today(self) -> bool:
        """Whether a date is read against the site's day anywhere: a `today`
        sentinel or a `[today]` default. `now` compares with the save instant
        and never reads a date, so it does not count."""
        return bool(self.today_defaults) or any(
            cell_id.endswith(("/today", "/today_offset")) for cell_id in self.cells
        )


def _offset(value: object) -> int:
    match = TODAY_SENTINEL.match(str(value))
    if match is None or match.group(2) is None:
        return 0
    days = int(match.group(2))
    return -days if match.group(1) == "-" else days


def clock_usage(schema: Schema, mapping: Mapping, table_names: Iterable[str]) -> ClockUsage:
    """Scan the named tables' validation rules, view windows and defaults."""
    wanted = set(table_names)
    cells: dict[str, set[int]] = {}
    defaults: list[TodayDefault] = []

    def note(leaf_value: object, column_type: str, target: str) -> None:
        sentinel = sentinel_of(leaf_value, column_type)
        if sentinel is None:
            return
        cell = cell_for(sentinel, column_type, target)
        cells.setdefault(cell.id, set()).add(_offset(leaf_value))

    for table in schema.tables:
        if table.name not in wanted:
            continue
        types = {c.name: c.type for c in table.columns}
        # A view may filter on Modified or Created, which no schema declares.
        view_types = {**SYSTEM_COLUMN_TYPES, **types}
        conditions = []
        section = mapping.column_validation.get(table.name)
        if section is not None:
            conditions += [rule.when for rule in section.columns.values()]
        rule = mapping.list_validation.get(table.name)
        if rule is not None:
            conditions.append(rule.when)
        for condition in conditions:
            for leaf in leaves(condition):
                note(leaf.value, types.get(leaf.field, ""), VALIDATION)
        for view in mapping.views.get(table.name, []):
            if view.where is None:
                continue
            for leaf in leaves(view.where):
                note(leaf.value, view_types.get(leaf.field, ""), CAML)
        for col in table.columns:
            if (
                col.type in DATE_TYPES
                and isinstance(col.default, str)
                and col.default.strip().lower() == TODAY_DEFAULT
            ):
                defaults.append(TodayDefault(table.name, col.name, col.type))

    return ClockUsage(
        cells={cell_id: frozenset(offsets) for cell_id, offsets in cells.items()},
        today_defaults=tuple(defaults),
    )
