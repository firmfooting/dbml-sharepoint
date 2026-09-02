---
title: clock_usage
sidebar_position: 26
---

# `dbml_sharepoint.analysis.clock_usage`

*which clock cells a pack uses, and where*

Which clock cells a pack uses, and where.

One scan, read by two scripts: the assess script asks whether the site's
time zone matters to this pack, and the verify script asks which cells to
exercise on its scratch list. Generators may not import `analysis/checks/`,
so the scan lives beside the cell table it classifies against.

### `TODAY_DEFAULT`

```python
TODAY_DEFAULT = '[today]'
```

### `TodayDefault`

```python
@dataclass(frozen=True)
class TodayDefault:
    entity: str
    column: str
    column_kind: str
```

A column whose default is SharePoint's dynamic `[today]`.

### `ClockUsage`

```python
@dataclass(frozen=True)
class ClockUsage:
    cells: MappingABC[str, frozenset[int]]
    today_defaults: tuple[TodayDefault, ...]
```

ClockUsage(cells: 'MappingABC[str, frozenset[int]]', today_defaults: 'tuple[TodayDefault, ...]')

### `clock_usage`

```python
def clock_usage(schema: 'Schema', mapping: 'Mapping', table_names: 'Iterable[str]') -> 'ClockUsage'
```

Scan the named tables' validation rules, view windows and defaults.

