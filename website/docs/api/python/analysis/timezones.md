---
title: timezones
sidebar_position: 29
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
2022). That is why the build takes a zone NAME rather than a rule.

The zone is a BUILD INPUT (`--time-zone`, or `DBMLSP_TIME_ZONE` in the env
file), never a mapping key: it is a fact about the site a pack is built for,
the same as `--site-url`, and a mapping is the solution's to write, not the
site's.

SHARED because three sides read it: `generators/reportgen` emits the table and
the offsets it compares the site's biases against, `cli.validate_time_zone`
refuses a name the database does not declare, and the wizard offers a name
before asking for one. None of them may import another for this.

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

### `suggest_zones`

```python
def suggest_zones(name: str, *, limit: int = 3) -> tuple[str, ...]
```

Known zones a mistyped name probably meant, best first.

Three readings, in order: the same name in another case
(`australia/melbourne`), a bare city that is the last segment of a zone
(`Melbourne`, which is how SharePoint's own regional settings name a
zone), then the nearest spellings. An operator who is refused with
nothing to try next reaches for a guess, and a guess is what the build
exists to refuse.

### `unknown_zone_message`

```python
def unknown_zone_message(name: str) -> str
```

Why a name was refused, with what to try next. One sentence shared by
the CLI refusal and the derivation's own, so the two cannot disagree.

### `zone_table`

```python
def zone_table(name: str) -> dbml_sharepoint.analysis.timezones.ZoneTable
```

The transitions of one IANA zone across the window, bisected to the
minute.

Raises `ValueError` naming the zone when the database does not declare
it. The CLI refuses the same name earlier, at `validate_time_zone`; this
is the derivation failing closed for any caller that did not go through
it, rather than emitting a query with no table behind it.

### `transitions`

```python
def transitions(name: str) -> tuple[tuple[datetime.datetime, int], ...]
```

The (UTC instant, offset from then on) rows for one zone; see
`zone_table` for the opening offset and the refusal.

