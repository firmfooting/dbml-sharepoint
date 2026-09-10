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
"""

import warnings
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from difflib import get_close_matches
from functools import cache
from zoneinfo import ZoneInfo, available_timezones

import tzlocal

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


def suggest_zones(name: str, *, limit: int = 3) -> tuple[str, ...]:
    """Known zones a mistyped name probably meant, best first.

    Three readings, in order: the same name in another case
    (`australia/melbourne`), a bare city that is the last segment of a zone
    (`Melbourne`, which is how SharePoint's own regional settings name a
    zone), then the nearest spellings. An operator who is refused with
    nothing to try next reaches for a guess, and a guess is what the build
    exists to refuse.
    """
    wanted = name.strip()
    if not wanted:
        return ()
    lowered = wanted.lower()
    found: list[str] = []
    for zone in sorted(known_zones()):
        if zone.lower() == lowered or zone.rsplit("/", 1)[-1].lower() == lowered:
            found.append(zone)
    for zone in get_close_matches(wanted, sorted(known_zones()), n=limit, cutoff=0.6):
        if zone not in found:
            found.append(zone)
    return tuple(found[:limit])


def local_zone_name() -> str | None:
    """The IANA name of the zone THIS MACHINE is set to, or None.

    The build machine's zone, not the site's: the two agree often enough
    to be worth offering and disagree often enough that the wizard must say
    which one this is and ask. `tzlocal` reads TZ and /etc/localtime on
    POSIX and the registry on Windows, where it maps the Windows zone id to
    an IANA name.

    None whenever the answer would be a guess. `tzlocal` itself warns and
    answers UTC when it finds no configuration at all, so warnings are
    raised here and caught with the rest: an offer of UTC on a machine
    that never said so is exactly the wrong default to confirm by reflex.
    A name the database here does not declare is refused the same way,
    since nothing downstream could derive a table from it.
    """
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            name = tzlocal.get_localzone_name()
    except (LookupError, OSError, ValueError, Warning):
        return None
    return name if is_known_zone(name) else None


def unknown_zone_message(name: str) -> str:
    """Why a name was refused, with what to try next. One sentence shared by
    the CLI refusal and the derivation's own, so the two cannot disagree."""
    near = suggest_zones(name)
    suggestion = f" Did you mean: {', '.join(near)}?" if near else ""
    return (
        f"{name!r} is not an IANA time zone name. The reporting pack derives "
        f"the site's daylight-saving transitions from the IANA database, so "
        f"the name must be one it declares, such as Australia/Melbourne or "
        f"Europe/London.{suggestion}"
    )


def _offset_minutes(zone: ZoneInfo, at: datetime) -> int:
    offset = at.astimezone(zone).utcoffset()
    assert offset is not None  # noqa: S101  (a ZoneInfo always has one)
    return int(offset.total_seconds()) // 60


@cache
def zone_table(name: str) -> ZoneTable:
    """The transitions of one IANA zone across the window, bisected to the
    minute.

    Raises `ValueError` naming the zone when the database does not declare
    it. The CLI refuses the same name earlier, at `validate_time_zone`; this
    is the derivation failing closed for any caller that did not go through
    it, rather than emitting a query with no table behind it.
    """
    if not is_known_zone(name):
        raise ValueError(unknown_zone_message(name))
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
