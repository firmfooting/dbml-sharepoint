---
title: timezones
sidebar_position: 27
---

# `dbml_sharepoint.analysis.timezones`

*a declared site zone's daylight-saving transitions, as data*

A declared site zone's daylight-saving transitions, as data the pack ships.

Power Query M has no time zone database. `DateTimeZone.SwitchZone` shifts by
a fixed offset, and `DateTimeZone.ToLocal` uses the machine the refresh runs
on, which in the Power BI Service is UTC. SharePoint's REST surface does not
fill the gap: `_api/web/RegionalSettings/TimeZone` answers with `Bias`,
`StandardBias` and `DaylightBias`, three static properties of the zone that
say nothing about which is in force on a given day, and the transition dates
exist only in the page context Power Query cannot reach.

So the transitions are computed here, from Python's `zoneinfo`, and emitted
into every list query as a literal table. `zoneinfo` resolves real rules: a
30-minute shift (Australia/Lord_Howe), southern-hemisphere dates
(America/Santiago), a rule change inside the window (Australia/Melbourne,
2008) and a zone that abolished daylight saving (Asia/Tehran, nothing after
2022). That is why the mapping declares a zone NAME rather than a rule.

SHARED because two sides read it: `generators/reportgen` emits the table and
the offsets it compares the site's biases against, and `checks/_sources`
refuses a name the database does not declare. Neither may import the other.

The window is FIXED. The repository commits generated artifacts and pins
them with currency tests, so a window derived from the build date would
make every regeneration churn. `test_site_zone` fails once the end is within
ten years of today, which is the prompt to move it.

### `WINDOW_START`

```python
WINDOW_START = datetime.datetime(2000, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
```

### `WINDOW_END`

```python
WINDOW_END = datetime.datetime(2050, 1, 1, 0, 0, tzinfo=datetime.timezone.utc)
```

### `ZoneTable`

```python
@dataclass(frozen=True)
class ZoneTable:
    zone: str
    start_offset: int
    transitions: tuple[tuple[datetime.datetime, int], ...]
```

One zone's offsets over the window, in minutes east of UTC.

#### `ZoneTable.offset_at`

```python
def offset_at(self, stamp: datetime.datetime) -> int
```

The offset in force at a UTC instant: the last transition at or
before it, or the opening offset when none is. The same rule the
emitted `SiteOffsetAt` applies, so a test can pin one against the
other.

### `known_zones`

```python
def known_zones() -> frozenset[str]
```

Every name `zoneinfo` can resolve on this machine, from the system
database where there is one and from the `tzdata` package otherwise.

### `is_known_zone`

```python
def is_known_zone(name: str) -> bool
```

### `zone_table`

```python
def zone_table(name: str) -> dbml_sharepoint.analysis.timezones.ZoneTable
```

The transitions of one IANA zone across the window, bisected to the
minute.

Raises `ValueError` naming the zone when the database does not declare
it, so the `report` command, which does not validate, refuses rather
than emitting a query with no table behind it.

### `transitions`

```python
def transitions(name: str) -> tuple[tuple[datetime.datetime, int], ...]
```

The (UTC instant, offset from then on) rows for one zone; see
`zone_table` for the opening offset and the refusal.

