# src/dbml_sharepoint/analysis/timezones.py
"""A declared site zone's daylight-saving transitions, as data the pack ships.

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
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import cache
from zoneinfo import ZoneInfo, available_timezones

#: The first instant a transition can be reported at. Nothing this tool
#: reports on predates SharePoint Online, so nothing earlier is needed.
WINDOW_START = datetime(2000, 1, 1, tzinfo=UTC)
#: The instant the table stops. A timestamp past it is converted with the
#: last offset the table names, which is right until the zone's rules change.
WINDOW_END = datetime(2050, 1, 1, tzinfo=UTC)

#: Transitions are found by comparing the offset at the two ends of a stride
#: and bisecting the stride that differs, so two transitions inside one
#: stride that cancel each other out would be missed. No zone has changed
#: its offset twice in one day since 2000, which is where the window opens.
_STRIDE = timedelta(days=1)
_MINUTE = timedelta(minutes=1)

#: How far back from `WINDOW_END` the zone's CURRENT rule is read. The IANA
#: database projects the rule in force today to the end of the window, so
#: the offsets seen there are the rule's, and two years holds every
#: transition a periodic rule makes.
_CURRENT_RULE_SPAN = timedelta(days=2 * 366)


@dataclass(frozen=True)
class ZoneTable:
    """One zone's offsets over the window, in minutes east of UTC."""

    zone: str
    #: The offset in force at `WINDOW_START`.
    start_offset: int
    #: (UTC instant of the change, the offset in force from that instant),
    #: ascending. Empty for a zone that never changes inside the window.
    transitions: tuple[tuple[datetime, int], ...]

    @property
    def offsets(self) -> tuple[int, ...]:
        """Every distinct offset the zone uses inside the window, ascending.

        The whole history, so NOT what the site's biases are compared
        against: Brazil abolished daylight saving in 2019 and Iran in 2022,
        and a site correctly set to either reports one offset while this
        still names two. See `current_offsets`.
        """
        return tuple(sorted({self.start_offset, *(o for _, o in self.transitions)}))

    @property
    def current_offsets(self) -> tuple[int, ...]:
        """The distinct offsets in force at any point during the final two
        years of the window, ascending: the zone's CURRENT rule, which the
        database projects forward from today.

        What the emitted query compares the site's own two candidates
        against, because `Bias`, `StandardBias` and `DaylightBias` describe
        the site zone's current rule and nothing earlier. A zone whose rule
        changed inside the window (Asia/Tehran, America/Sao_Paulo) names one
        offset here and two in `offsets`; comparing the site against the
        second would read false on every row, for ever, with nothing wrong.
        Reading through `offset_at` covers a zone with no transitions in the
        span, which answers its trailing offset, and one with none at all,
        which answers `start_offset`.
        """
        since = WINDOW_END - _CURRENT_RULE_SPAN
        return tuple(sorted({
            self.offset_at(since),
            *(offset for at, offset in self.transitions if at >= since),
        }))

    def offset_at(self, stamp: datetime) -> int:
        """The offset in force at a UTC instant: the last transition at or
        before it, or the opening offset when none is. The same rule the
        emitted `SiteOffsetAt` applies, so a test can pin one against the
        other."""
        offset = self.start_offset
        for at, next_offset in self.transitions:
            if at > stamp:
                break
            offset = next_offset
        return offset


@cache
def known_zones() -> frozenset[str]:
    """Every name `zoneinfo` can resolve on this machine, from the system
    database where there is one and from the `tzdata` package otherwise."""
    return frozenset(available_timezones())


def is_known_zone(name: str) -> bool:
    return name in known_zones()


def _offset_minutes(zone: ZoneInfo, at: datetime) -> int:
    offset = at.astimezone(zone).utcoffset()
    assert offset is not None  # noqa: S101  (a ZoneInfo always has one)
    return int(offset.total_seconds()) // 60


@cache
def zone_table(name: str) -> ZoneTable:
    """The transitions of one IANA zone across the window, bisected to the
    minute.

    Raises `ValueError` naming the zone when the database does not declare
    it, so the `report` command, which does not validate, refuses rather
    than emitting a query with no table behind it.
    """
    if not is_known_zone(name):
        raise ValueError(
            f"reporting.time_zone: {name!r} is not an IANA time zone name. "
            f"The reporting pack derives the site's daylight-saving "
            f"transitions from the IANA database, so the name must be one "
            f"it declares, such as Australia/Melbourne or Europe/London.",
        )
    zone = ZoneInfo(name)
    start = _offset_minutes(zone, WINDOW_START)
    transitions: list[tuple[datetime, int]] = []
    cursor = WINDOW_START
    current = start
    while cursor < WINDOW_END:
        probe = min(cursor + _STRIDE, WINDOW_END)
        if _offset_minutes(zone, probe) == current:
            cursor = probe
            continue
        # The offset at `low` is still `current` and at `high` it is not;
        # halve in whole minutes until the two are adjacent.
        low, high = cursor, probe
        while high - low > _MINUTE:
            mid = low + _MINUTE * ((high - low) // _MINUTE // 2)
            if _offset_minutes(zone, mid) == current:
                low = mid
            else:
                high = mid
        current = _offset_minutes(zone, high)
        transitions.append((high, current))
        cursor = high
    return ZoneTable(zone=name, start_offset=start, transitions=tuple(transitions))


def transitions(name: str) -> tuple[tuple[datetime, int], ...]:
    """The (UTC instant, offset from then on) rows for one zone; see
    `zone_table` for the opening offset and the refusal."""
    return zone_table(name).transitions
