# test/test_site_zone.py
"""The declared site zone: the declaration, the rule, the derivation and the
emitted M.

Power Query M has no time zone database and SharePoint serves no transition
dates, so the pack ships the declared zone's daylight-saving transitions,
derived from `zoneinfo` when it is built. Nothing downstream verifies them:
a wrong row converts every timestamp near a transition by the wrong offset,
and the refresh reports success. These tests stand in for that readback,
and `test/manual/site-zone-transitions-probe.js` asks the platform itself.
"""

import datetime as dt
import re
from dataclasses import replace
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from _builders import ID_PK
from _builders import table as dbml_table
from _findings import none_of, only
from _packs import entities, write_dbml, write_mapping
from _paths import FIXTURES, MANUAL, SOLUTION_TEMPLATES
from typer.testing import CliRunner

from dbml_sharepoint.analysis.derived import report_column_names
from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.analysis.timezones import (
    WINDOW_END,
    WINDOW_START,
    is_known_zone,
    transitions,
    zone_table,
)
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.cli import app
from dbml_sharepoint.generators.report_m import generate_powerquery
from dbml_sharepoint.generators.report_md import (
    generate_data_dictionary,
    generate_reporting_md,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    DerivedColumn,
    MappingBundle,
    ReportingOptions,
)
from dbml_sharepoint.model.parser import Schema, parse_dbml

MELBOURNE = "Australia/Melbourne"
_UTC = dt.UTC


def _simple() -> tuple[Schema, MappingBundle]:
    return (
        parse_dbml(FIXTURES / "simple.dbml"),
        load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
    )


def _zoned(
    bundle: MappingBundle, zone: str | None = MELBOURNE, **reporting: bool,
) -> MappingBundle:
    return replace(
        bundle,
        mapping=replace(
            bundle.mapping, reporting=ReportingOptions(time_zone=zone, **reporting),
        ),
    )


def _zoneinfo_offset(zone: str, at: dt.datetime) -> int:
    offset = at.astimezone(ZoneInfo(zone)).utcoffset()
    assert offset is not None
    return int(offset.total_seconds()) // 60


# ------------------------------------------------------------ the derivation


def test_melbourne_is_pinned_against_zoneinfo() -> None:
    """The family's zone, and one whose rule changed inside the window: from
    2008 daylight saving ends on the first Sunday of April rather than the
    last Sunday of March. A table that knew only the current rule would
    date every 2007 row a week out, and nothing in a refresh could tell."""
    table = zone_table(MELBOURNE)
    assert table.start_offset == 660  # daylight saving is on at New Year
    assert table.offsets == (600, 660)
    assert len(table.transitions) == 100
    assert table.transitions[0] == (dt.datetime(2000, 3, 25, 16, tzinfo=_UTC), 600)
    assert table.transitions[-1] == (dt.datetime(2049, 10, 2, 16, tzinfo=_UTC), 660)
    assert (dt.datetime(2007, 3, 24, 16, tzinfo=_UTC), 600) in table.transitions
    assert (dt.datetime(2008, 4, 5, 16, tzinfo=_UTC), 600) in table.transitions
    assert (dt.datetime(2008, 10, 4, 16, tzinfo=_UTC), 660) in table.transitions


def test_every_row_is_a_real_transition_and_every_day_agrees() -> None:
    """Pinned against zoneinfo itself rather than against literals alone:
    the offset changes at each row and not the minute before it, and
    `offset_at`, which the emitted `SiteOffsetAt` reproduces, answers the
    same as zoneinfo at noon on every day of the window. Santiago is the
    southern-hemisphere case with the opposite sign."""
    for zone in (MELBOURNE, "America/Santiago", "Europe/London"):
        table = zone_table(zone)
        for at, offset in table.transitions:
            assert _zoneinfo_offset(zone, at) == offset, (zone, at)
            assert _zoneinfo_offset(zone, at - dt.timedelta(minutes=1)) != offset, (zone, at)
    table = zone_table(MELBOURNE)
    day = WINDOW_START + dt.timedelta(hours=12)
    while day < WINDOW_END:
        assert table.offset_at(day) == _zoneinfo_offset(MELBOURNE, day), day
        day += dt.timedelta(days=1)


def test_lord_howe_keeps_its_thirty_minute_shift() -> None:
    """A rule vocabulary written by hand would have to know a shift can be
    half an hour. The zone name carries it, which is why the mapping
    declares a name rather than a rule."""
    table = zone_table("Australia/Lord_Howe")
    assert table.offsets == (630, 660)
    assert table.transitions[0] == (dt.datetime(2000, 3, 25, 15, tzinfo=_UTC), 630)
    assert table.transitions[1] == (dt.datetime(2000, 8, 26, 15, 30, tzinfo=_UTC), 660)


def test_a_zone_that_abolished_daylight_saving_stops() -> None:
    table = zone_table("Asia/Tehran")
    assert table.transitions[-1] == (dt.datetime(2022, 9, 21, 19, 30, tzinfo=_UTC), 210)
    assert table.offset_at(dt.datetime(2030, 7, 1, tzinfo=_UTC)) == 210


def test_a_zone_with_no_transitions_yields_an_empty_table() -> None:
    table = zone_table("UTC")
    assert table.transitions == ()
    assert table.start_offset == 0
    assert table.offsets == (0,)
    assert table.offset_at(dt.datetime(2030, 7, 1, tzinfo=_UTC)) == 0
    assert transitions("Asia/Tokyo") == ()


def test_rows_are_minute_aligned_ascending_and_each_changes_the_offset() -> None:
    """The emitted `SiteOffsetAt` takes the last row at or before an
    instant, which is only the offset in force if the rows ascend and each
    one really changes something."""
    for zone in (MELBOURNE, "Australia/Lord_Howe", "Asia/Tehran"):
        table = zone_table(zone)
        previous_at, previous_offset = WINDOW_START, table.start_offset
        for at, offset in table.transitions:
            assert at.tzinfo is _UTC and at.second == 0 and at.microsecond == 0
            assert WINDOW_START <= at < WINDOW_END
            assert at > previous_at, (zone, at)
            assert offset != previous_offset, (zone, at)
            previous_at, previous_offset = at, offset


def test_an_unknown_zone_is_refused_by_name() -> None:
    assert not is_known_zone("Mars/Olympus")
    with pytest.raises(ValueError, match="Mars/Olympus"):
        zone_table("Mars/Olympus")


def test_the_window_ends_at_least_ten_years_from_today() -> None:
    """The window is fixed so the committed artifacts do not churn, and a
    fixed window goes stale silently: a timestamp past the last row takes
    that row's offset for ever. This is the visible failure that prompts
    the bump, rather than a report quietly dating 2051 by 2049's rule."""
    assert dt.datetime.now(dt.UTC) + dt.timedelta(days=10 * 366) <= WINDOW_END


# ----------------------------------------------------------- the declaration


_MINIMAL = (
    "prefix: APP_\n"
    "entities:\n"
    "  Risk: {kind: List, base_template: 100, site_role: default}\n"
)


def _load(tmp_path: Path, reporting: str) -> MappingBundle:
    path = tmp_path / "m.yaml"
    path.write_text(_MINIMAL + reporting, encoding="utf-8")
    return load_mapping(path)


def test_time_zone_is_parsed_and_defaults_off(tmp_path: Path) -> None:
    assert _load(tmp_path, "").mapping.reporting.time_zone is None
    loaded = _load(tmp_path, "reporting:\n  time_zone: Australia/Melbourne\n")
    assert loaded.mapping.reporting == ReportingOptions(time_zone=MELBOURNE)


@pytest.mark.parametrize("value", ["''", "3", "[Australia/Melbourne]"])
def test_the_loader_checks_the_shape_only(tmp_path: Path, value: str) -> None:
    """A name the IANA database does not declare is the validator's finding,
    with a location beside every other; the loader refuses only what is not
    a name at all, the same split as `lookup_projections`."""
    with pytest.raises(ValueError, match=r"reporting\.time_zone"):
        _load(tmp_path, f"reporting:\n  time_zone: {value}\n")
    unknown = _load(tmp_path, "reporting:\n  time_zone: Mars/Olympus\n")
    assert unknown.mapping.reporting.time_zone == "Mars/Olympus"


# ------------------------------------------------------------------- the rule


def test_an_unknown_zone_is_refused_by_the_validator() -> None:
    """The pack ships the declared zone's transitions, so a name the
    database does not declare has nothing to generate from."""
    schema, bundle = _simple()
    findings = validate_against_mapping(schema, _zoned(bundle, "Mars/Olympus"))
    finding = only(findings, FindingCode.UNKNOWN_TIME_ZONE)
    assert finding.severity == "error"
    assert "'Mars/Olympus'" in finding.message
    assert finding.location is not None
    assert finding.location.path == "reporting.time_zone"


def test_a_known_zone_passes() -> None:
    schema, bundle = _simple()
    none_of(validate_against_mapping(schema, _zoned(bundle)), FindingCode.UNKNOWN_TIME_ZONE)


def _with_created_date(bundle: MappingBundle) -> MappingBundle:
    return replace(
        bundle,
        mapping=replace(
            bundle.mapping,
            reporting=ReportingOptions(system_columns=True, time_zone=MELBOURNE),
            derived_columns={"Task": [DerivedColumn(
                kind="expr", name="CreatedDate", type="date",
                m="AsSiteDate([Created])",
            )]},
        ),
    )


def test_a_derived_column_may_call_the_helpers() -> None:
    """The reference rule reads `[Column]` names, so a helper call is not a
    reference; what has to resolve is the timestamp the helper is given.
    The helper is bound above the step that calls it."""
    schema, bundle = _simple()
    zoned = _with_created_date(bundle)
    none_of(validate_against_mapping(schema, zoned), FindingCode.DERIVED_UNKNOWN_REFERENCE)
    query = generate_powerquery(schema, zoned, "default")["APP_Task.pq"]
    assert "each AsSiteDate([Created])," in query
    assert query.index("AsSiteDate = (v as any)") < query.index("each AsSiteDate([Created])")


# ------------------------------------------------------------- the emitted M


def _zone_binding(query: str) -> str:
    """The `Zone = ...` binding alone, up to the `AsStamp` helper after it."""
    return query.split("    Zone =", 1)[1].split("    // The wall clock", 1)[0]


def test_every_list_query_carries_the_table_and_the_helpers() -> None:
    """Unconditionally, once a zone is declared: predictable output beats an
    emission rule that can be got wrong, and the rows are the derivation's
    rows, not a literal restated here."""
    schema, bundle = _simple()
    table = zone_table(MELBOURNE)
    queries = generate_powerquery(schema, _zoned(bundle), "default")
    assert len(queries) == 3
    for name, query in queries.items():
        assert query.count("#datetime(") == len(table.transitions) == 100, name
        assert "{#datetime(2000, 3, 25, 16, 0, 0), 600}," in query, name
        assert "{#datetime(2049, 10, 2, 16, 0, 0), 660}\n" in query, name
        assert "SiteTransitions = List.Buffer({" in query, name
        assert "SiteOffsetAt = (stamp as datetime) as number =>" in query, name
        # The opening offset, for an instant before the first row.
        assert "if List.IsEmpty(Before) then 660" in query, name
        assert "AsSiteDateTime = (v as any) as nullable datetime =>" in query, name
        assert "AsSiteDate = (v as any) as nullable date =>" in query, name
        assert "Stamp + #duration(0, 0, SiteOffsetAt(Stamp), 0)" in query, name
        # One AsStamp, read by AsDate where there is a date column and by
        # the helpers everywhere.
        assert query.count("AsStamp = (v as any)") == 1, name
        for opener, closer in ("()", "{}", "[]"):
            assert query.count(opener) == query.count(closer), (name, opener)


def test_nothing_is_emitted_without_a_declaration() -> None:
    schema, bundle = _simple()
    assert bundle.mapping.reporting.time_zone is None
    for name, query in generate_powerquery(schema, bundle, "default").items():
        for token in (
            "SiteTransitions", "SiteOffsetAt", "AsSiteDateTime", "AsSiteDate",
            "#datetime(",
        ):
            assert token not in query, (name, token)
        # The flag keeps its first meaning, on the lists that had it. Scoped
        # to the Zone binding: the ItemUrl binding says `resolved = true` too.
        if "    Zone =" in query:
            assert "resolved = true," in _zone_binding(query), name


def test_resolved_requires_agreement_with_the_sites_biases() -> None:
    """THE fold. The shipped table is only right on a site set to the
    declared zone, and nothing else in the pack can tell, so the flag the
    lists already carry takes the check: the two candidates the site
    answers with must be exactly the offsets the declared zone uses. A
    mapping declaring Melbourne against a site set to London reads false
    on every row rather than converting by the wrong table."""
    schema, bundle = _simple()
    query = generate_powerquery(schema, _zoned(bundle), "default")["APP_Task.pq"]
    zone_binding = _zone_binding(query)
    assert "resolved = true," not in zone_binding
    assert "{- (Bias + Standard), - (Bias + Daylight)}" in zone_binding
    assert "DeclaredOffsets = {600, 660}" in zone_binding
    # Both directions, so a site with one of the two offsets (Brisbane
    # against a declared Melbourne) reads false too. Written with
    # List.Difference rather than list equality, because nothing here can
    # execute M and the check must lean on nothing in question.
    assert "List.Difference(SiteOffsets, DeclaredOffsets)" in zone_binding
    assert "List.Difference(DeclaredOffsets, SiteOffsets)" in zone_binding
    assert "List.Sort" not in zone_binding
    assert "otherwise [resolved = false, offsets = {0}]," in zone_binding
    # The date-only candidates are untouched: AsDate still tries all three.
    assert "{0, - (Bias + Standard), - (Bias + Daylight)}" in zone_binding
    # A zone with one offset compares against one, and ships no rows.
    tokyo = generate_powerquery(schema, _zoned(bundle, "Asia/Tokyo"), "default")
    assert "DeclaredOffsets = {540}" in tokyo["APP_Task.pq"]
    assert "SiteTransitions = List.Buffer({\n    })," in tokyo["APP_Task.pq"]
    assert "if List.IsEmpty(Before) then 540" in tokyo["APP_Task.pq"]


def _agrees(site: tuple[int, int], declared: tuple[int, ...]) -> bool:
    """The emitted check, in Python: the site's two candidates as a set
    against the declared literal, differenced in both directions."""
    site_offsets = set(site)
    declared_offsets = set(declared)
    return not (site_offsets - declared_offsets) and not (declared_offsets - site_offsets)


@pytest.mark.parametrize(
    ("zone", "current", "historic"),
    [
        ("Asia/Tehran", (210,), (210, 270)),
        ("America/Sao_Paulo", (-180,), (-180, -120)),
    ],
)
def test_a_zone_that_changed_its_rule_compares_by_the_current_one(
    zone: str, current: tuple[int, ...], historic: tuple[int, ...],
) -> None:
    """THE test that would have caught the first version. The site's three
    biases describe its zone's CURRENT rule, so a zone that abolished
    daylight saving inside the window reports one offset, and a check
    against both of its historical offsets read false on every row of
    every table for ever, with nothing wrong. A standing false destroys a
    flag whose meaning is that false is worth investigating."""
    table = zone_table(zone)
    assert table.offsets == historic
    assert table.current_offsets == current
    schema, bundle = _simple()
    query = generate_powerquery(schema, _zoned(bundle, zone), "default")["APP_Task.pq"]
    literal = "{" + ", ".join(str(o) for o in current) + "}"
    assert f"DeclaredOffsets = {literal}" in _zone_binding(query)
    # A site reporting equal biases (no daylight bias) agrees...
    assert _agrees((current[0], current[0]), current)
    # ...and the historical pair would not have.
    assert not _agrees((current[0], current[0]), historic)


def test_the_current_rule_reads_both_offsets_of_a_zone_that_still_shifts() -> None:
    """Melbourne, London and Lord Howe name both offsets either way, and the
    check stays symmetric: a site set to Brisbane, one of Melbourne's two
    offsets, does not agree with a declared Melbourne."""
    for zone in (MELBOURNE, "Europe/London", "Australia/Lord_Howe"):
        table = zone_table(zone)
        assert table.current_offsets == table.offsets, zone
        assert len(table.current_offsets) == 2, zone
    assert zone_table("Asia/Tokyo").current_offsets == (540,)
    melbourne = zone_table(MELBOURNE).current_offsets
    assert _agrees((600, 660), melbourne)
    assert not _agrees((600, 600), melbourne)  # Brisbane
    assert not _agrees((0, 60), melbourne)  # London


def test_the_flag_rides_every_list_once_a_zone_is_declared() -> None:
    """The agreement check has nowhere else to surface, so a list with no
    date-only column carries the flag too, and the shared column derivation
    the validator reads says the same."""
    schema, bundle = _simple()
    zoned = _zoned(bundle)
    plain = generate_powerquery(schema, bundle, "default")
    plain_flagged = {n for n, q in plain.items() if '"DateZoneResolved"' in q}
    assert plain_flagged and plain_flagged != set(plain)  # the declaration widens it
    queries = generate_powerquery(schema, zoned, "default")
    enums = {e.name for e in schema.enums}
    for table in schema.tables:
        query = queries[f"APP_{table.name}.pq"]
        assert '"DateZoneResolved"' in query, table.name
        assert "RegionalSettings/TimeZone" in query, table.name
        assert "DateZoneResolved" in report_column_names(table, zoned, enums), table.name


def test_the_users_dimension_carries_no_table() -> None:
    """No derived column can target `_Users`, so nothing there could call
    the helpers, and a table with no reader is weight."""
    schema, bundle = _simple()
    queries = generate_powerquery(schema, _zoned(bundle, users_table=True), "default")
    assert "SiteTransitions" not in queries["_Users.pq"]


def test_the_guide_and_the_dictionary_say_what_the_flag_now_means() -> None:
    schema, bundle = _simple()
    guide = generate_reporting_md(schema, _zoned(bundle), "default")
    assert "Every list carries **DateZoneResolved**" in guide
    assert "does not agree with it" in guide
    assert "100 rows" in guide
    assert "`AsSiteDate`" in guide
    dictionary = generate_data_dictionary(schema, _zoned(bundle), "default")
    assert "agrees with the declared `Australia/Melbourne`" in dictionary
    plain_guide = generate_reporting_md(schema, bundle, "default")
    assert "A list with a date-only column also carries **DateZoneResolved**" in plain_guide
    assert "AsSiteDate" not in plain_guide


def test_report_refuses_an_unknown_zone_by_name(tmp_path: Path) -> None:
    """`report` does not validate, so the derivation's own refusal is the
    only thing between a typo and a query with no table behind it."""
    mapping = write_mapping(
        tmp_path, entities("Risk") + "reporting:\n  time_zone: Mars/Olympus\n",
    )
    schema = write_dbml(tmp_path, dbml_table("Risk", ID_PK))
    result = CliRunner().invoke(app, [
        "report", "--schema", str(schema), "--mapping", str(mapping),
        "--out", str(tmp_path / "reports"),
    ])
    assert result.exit_code == 1, result.output
    assert "Mars/Olympus" in result.output
    assert "Traceback" not in result.output
    assert not list((tmp_path / "reports").rglob("*.pq"))


# ----------------------------------------------------------------- the family


_FAMILY = SOLUTION_TEMPLATES / "programme-governance"


def test_the_family_declares_its_zone_and_dates_its_timestamps_by_it() -> None:
    """The three derived date columns used to truncate in UTC and said so
    in their descriptions; now they convert by the site's zone."""
    schema = parse_dbml(_FAMILY / "10-design" / "schema.dbml")
    bundle = load_mapping(_FAMILY / "20-configure" / "mapping.yaml")
    assert bundle.mapping.reporting.time_zone == MELBOURNE
    dated = [
        (entity, entry)
        for entity, entries in bundle.mapping.derived_columns.items()
        for entry in entries
        if entry.name in {"CreatedDate", "ModifiedDate"}
    ]
    assert {(entity, entry.name) for entity, entry in dated} == {
        ("ServiceRequest", "CreatedDate"),
        ("ServiceRequest", "ModifiedDate"),
        ("Activity", "ModifiedDate"),
    }
    for _, entry in dated:
        assert entry.m == f"AsSiteDate([{entry.name.removesuffix('Date')}])"
        assert "truncated in UTC" not in entry.description
        assert MELBOURNE in entry.description
    findings = validate_against_mapping(schema, bundle)
    none_of(findings, FindingCode.UNKNOWN_TIME_ZONE)
    none_of(findings, FindingCode.DERIVED_UNKNOWN_REFERENCE)
    queries = generate_powerquery(schema, bundle, "default")
    prefix = bundle.mapping.prefix
    assert "each AsSiteDate([Created])," in queries[f"{prefix}ServiceRequest.pq"]
    assert "each AsSiteDate([Modified])," in queries[f"{prefix}ServiceRequest.pq"]
    assert "each AsSiteDate([Modified])," in queries[f"{prefix}Activity.pq"]
    for name, query in queries.items():
        assert "Date.From([Created])" not in query, name
        assert "Date.From([Modified])" not in query, name
        if name != "_Users.pq":
            assert "SiteTransitions = List.Buffer({" in query, name


# ------------------------------------------------------------------ the probe


_PROBE = MANUAL / "site-zone-transitions-probe.js"
_SAMPLE_ZONE = re.compile(r"^    '([A-Za-z_]+/[A-Za-z_]+)': \[$", re.MULTILINE)
_SAMPLE_ROW = re.compile(
    r"^      \{ at: '([^']+)', before: (-?\d+), after: (-?\d+) \},$", re.MULTILINE,
)


def test_the_probe_samples_are_rows_of_the_shipped_table() -> None:
    """The probe compares SharePoint's `utctolocaltime` against literal rows,
    and a literal can drift from the derivation it claims to copy. Every
    sampled row must be a transition the table really emits, with the
    offset in force before it, or the probe would report SharePoint
    disagreeing with something the pack never shipped."""
    source = _PROBE.read_text(encoding="utf-8")
    assert f"const ZONE = '{MELBOURNE}';" in source
    block = source.split("const SAMPLES = {", 1)[1].split("\n  };", 1)[0]
    heads = list(_SAMPLE_ZONE.finditer(block))
    assert {head.group(1) for head in heads} >= {MELBOURNE, "Australia/Lord_Howe"}
    checked = 0
    for index, head in enumerate(heads):
        end = heads[index + 1].start() if index + 1 < len(heads) else len(block)
        zone = head.group(1)
        table = zone_table(zone)
        rows = _SAMPLE_ROW.findall(block[head.end():end])
        assert len(rows) == 3, zone
        for at_text, before, after in rows:
            at = dt.datetime.fromisoformat(at_text)
            assert (at, int(after)) in table.transitions, (zone, at_text)
            assert table.offset_at(at - dt.timedelta(minutes=1)) == int(before), (zone, at_text)
            checked += 1
    assert checked == 12
