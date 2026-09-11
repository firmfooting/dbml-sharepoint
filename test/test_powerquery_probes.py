# test/test_powerquery_probes.py
"""The Power Query probe lane: the only thing that ever executes the pack's M.

A `.pq` probe is loaded into Power BI by a person, so nothing about it runs
here. These checks exist for the one failure that costs the most: a probe
that has drifted from the generator, which then measures a construct the
pack no longer emits and reports OK for something nobody tested.

`test_probes.py` already sweeps every tracked file under `test/manual` for
tenant identifiers, and `git ls-files` reaches this subdirectory, so the
probes inherit that guard without restating it.
"""

import re

import pytest
from _paths import MANUAL

from dbml_sharepoint.generators import report_m

PROBES = MANUAL / "powerquery"


def _normalised(text: str) -> str:
    """Whitespace collapsed, so a fragment matches whatever a generator or a
    probe happens to indent it to."""
    return re.sub(r"\s+", " ", text)


def _probe(name: str) -> str:
    return (PROBES / name).read_text(encoding="utf-8")


def test_the_lane_ships_the_three_probes_and_its_readme() -> None:
    """Named individually rather than counted: a probe deleted by accident
    reads the same as a lane nobody has added to yet."""
    for name in (
        "m-runtime-probe.pq",
        "_ProbeOther.pq",
        "sharepoint-feed-probe.pq",
        "README.md",
    ):
        assert (PROBES / name).is_file(), name


@pytest.mark.parametrize("fragment", [
    "each DateTime.Time(_) = #time(0, 0, 0)",
    "each Stamp + #duration(0, 0, _, 0)",
])
def test_the_date_probe_measures_the_expression_the_generator_emits(
    fragment: str,
) -> None:
    """THE reason this file exists. The probe carries its own copy of the
    date conversion, because a probe has to run without the generator. A
    copy that drifts still returns a table full of OK, which is worse than
    no probe: it reports that something was measured when the thing measured
    is not the thing shipped.

    Matched on the two expressions that carry the whole argument, rather
    than on the block verbatim, because the probe takes its candidate
    offsets as a parameter and the emitted version reads them off `Zone`.
    """
    emitted = _normalised("\n".join(report_m._AS_DATE_M))
    assert _normalised(fragment) in emitted, "the generator no longer emits it"
    assert _normalised(fragment) in _normalised(_probe("m-runtime-probe.pq"))


def test_the_feed_probe_normalises_a_value_the_way_the_generator_does() -> None:
    """The shape tests in `AsStamp` decide which branch a value takes, and
    their ORDER is the part that matters: a zoned value must be recognised
    before the naive test, or it never reaches `ToUtc`."""
    emitted = _normalised("\n".join(report_m._AS_STAMP_M))
    probe = _normalised(_probe("sharepoint-feed-probe.pq"))
    for fragment in (
        "if v is datetimezone then",
        "DateTimeZone.RemoveZone(DateTimeZone.ToUtc(v))",
        "else if v is datetime then v",
        "else if v is date then DateTime.From(v)",
    ):
        assert _normalised(fragment) in emitted, fragment
        assert _normalised(fragment) in probe, fragment


def test_the_feed_probe_reads_nothing_until_an_operator_edits_it() -> None:
    """The same gate every probe in the sibling directory ships with: pasted
    unedited it prints its plan and touches nothing. Here the gate is also
    what keeps a placeholder host out of a real request."""
    text = _probe("sharepoint-feed-probe.pq")
    assert 'ListTitle = "SET_ME"' in text
    assert 'DateOnlyColumn = "SET_ME"' in text
    assert "https://contoso.sharepoint.com" in text
    assert 'not Text.Contains(SiteUrl, "contoso")' in text
    assert "if Configured then WithVerdict else NotConfigured" in text


def test_no_probe_here_writes_anything() -> None:
    """Read-only by construction. `OData.Feed` cannot write, so the check is
    that nothing reaches for a transport that can."""
    for name in ("m-runtime-probe.pq", "sharepoint-feed-probe.pq", "_ProbeOther.pq"):
        text = _probe(name)
        assert "Web.Contents" not in text, name
        assert "Json.Document" not in text, name


def test_the_cross_query_probe_is_read_by_the_name_the_generator_emits() -> None:
    """A derived lookup or count names another query, and the emitted form is
    quoted because a bare identifier is not valid for every query name. The
    probe asks whether that resolves, so it has to use the same form."""
    assert '#"_ProbeOther"' in _probe("m-runtime-probe.pq")
    assert report_m._query_ref("_ProbeOther") == '#"_ProbeOther"'


def test_the_readme_says_to_run_both_hosts() -> None:
    """The Service refreshes in UTC with no machine time zone and Desktop
    does not, so a probe run in one has not measured the other. That is the
    instruction most easily skipped, and the one this lane exists for."""
    readme = _probe("README.md")
    assert "Service" in readme
    assert "Desktop" in readme
    assert "run twice" in readme
