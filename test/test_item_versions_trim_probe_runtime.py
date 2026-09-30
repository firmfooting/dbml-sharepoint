"""Execute item-versions-trim-probe.js under node against a mock web.

The mock (`_versions_mock.py`) keeps every version unless told to keep the newest
MajorVersionLimit of them, at once or only from a later read, so an untrimmed list, a list
trimmed on write and a list trimmed after a delay are each reached. The probe's one-minute
wait is swapped for none.
"""

import json
from typing import Any

import pytest
from _node import NODE
from _paths import MANUAL
from _probe_runs import (
    catalogued_dependents,
    ended_with_report,
    recycled_last,
    run_probe,
    voided,
)
from _versions_mock import VERSIONS_MOCK

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "item-versions-trim-probe.js"
LIST = "field.version.fixture-trim-list"
LIMIT = "field.version.trim-limit-taken"
ITEM = "field.version.fixture-trim-item"
ONCE = "field.version.trim-versions-at-once"
WAIT = "field.version.trim-versions-after-wait"
# The create and the five writes after it each take one versions read before the rows' reads.
WRITE_READS = 6
NO_WAIT = {"  const TRIM_WAIT_MS = 60000;": "  const TRIM_WAIT_MS = 0;"}


def _run(gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"), **config: Any,
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    return run_probe(VERSIONS_MOCK, PROBE, gates, config, NO_WAIT)


def _deps(fixture: str) -> set[str]:
    return catalogued_dependents(PROBE.name, fixture)


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates)

    assert sent == []
    assert rows == {}


def test_a_list_that_trims_on_write_is_recorded_trimmed_both_times() -> None:
    rows, sent, _ = _run(trimToLimit=True)

    assert rows[LIST]["outcome"] == "PASS"
    assert rows[LIMIT]["outcome"] == "TAKEN AS ASKED"
    assert "the settings MERGE answered HTTP 204" in rows[LIMIT]["evidence"]
    assert "MajorVersionLimit reads back 2" in rows[LIMIT]["evidence"]
    assert rows[ITEM]["outcome"] == "PASS"
    for row_id in (ONCE, WAIT):
        assert rows[row_id]["outcome"] == "TRIMMED", rows[row_id]
        assert rows[row_id]["evidence"].startswith(
            'limit 2; 2 of the 6 version(s) the writes created answered, in order: '
            '"6.0"/3072/"dbmlsp versions trim 6", "5.0"/2560/"dbmlsp versions trim 5"; '
            'the lowest VersionId answered carries ')
    assert "after the first read" in rows[WAIT]["evidence"]
    assert len([r for r in sent if r["verb"] == "MERGE" and "items(1)" in r["path"]]) == 5
    assert recycled_last(sent)


def test_a_list_that_keeps_every_version_is_recorded_untrimmed() -> None:
    rows, _, _ = _run()

    assert rows[ONCE]["outcome"] == "UNTRIMMED"
    assert "6 of the 6 version(s) the writes created answered" in rows[ONCE]["evidence"]


def test_a_trim_that_lands_after_the_first_read_shows_in_the_second() -> None:
    # The six writes each take one versions read, so the first read the rows record is the seventh.
    rows, _, _ = _run(trimToLimit=True, trimAfterReads=WRITE_READS + 1)

    assert rows[ONCE]["outcome"] == "UNTRIMMED"
    assert rows[WAIT]["outcome"] == "TRIMMED"


def test_versionids_that_are_not_numbers_name_no_lowest() -> None:
    rows, _, _ = _run(versionIds="text")

    assert rows[ONCE]["outcome"] == "UNTRIMMED"
    assert "the lowest VersionId answered carries" not in rows[ONCE]["evidence"]
    assert "not all numbers" in rows[ONCE]["evidence"]


def test_a_list_that_took_another_limit_is_measured_at_that_limit() -> None:
    rows, sent, _ = _run(listMerge={"MajorVersionLimit": 5}, trimToLimit=True)

    assert rows[LIMIT]["outcome"] == "OTHER LIMIT"
    assert "asked 2" in rows[LIMIT]["evidence"]
    assert "MajorVersionLimit reads back 5" in rows[LIMIT]["evidence"]
    assert len([r for r in sent if r["verb"] == "MERGE" and "items(1)" in r["path"]]) == 8
    assert "5 of the 9 version(s) the writes created answered" in rows[ONCE]["evidence"]


def test_a_limit_past_what_the_run_will_write_voids_everything_after_the_list() -> None:
    rows, sent, _ = _run(listMerge={"MajorVersionLimit": 500})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "MajorVersionLimit differs: read 500, declared by a predicate it fails" in (
        rows[LIST]["evidence"])
    assert voided(rows) == _deps(LIST)
    assert not [r for r in sent if "/items" in r["path"]]
    assert recycled_last(sent)


def test_a_refused_settings_merge_is_kept_in_the_evidence() -> None:
    rows, _, _ = _run(rules=[{"contains": "web/lists(guid'", "verb": "MERGE", "status": 400,
                              "text": "The value is out of range."}])

    assert rows[LIST]["outcome"] == "FAIL"
    assert "EnableVersioning differs" in rows[LIST]["evidence"]
    assert 'Settings="HTTP 400: The value is out of range."' in rows[LIST]["evidence"]


def test_a_refused_settings_merge_on_a_list_still_in_range_is_observed_not_voided() -> None:
    rows, _, _ = _run(listDefaults={"EnableVersioning": True, "MajorVersionLimit": 2},
                      trimToLimit=True,
                      rules=[{"contains": "web/lists(guid'",
                              "verb": "MERGE", "bodyContains": "MajorVersionLimit", "status": 400,
                              "text": "The value is out of range."}])

    assert rows[LIST]["outcome"] == "PASS"
    assert 'Settings="HTTP 400: The value is out of range."' in rows[LIST]["evidence"]
    assert rows[LIMIT]["outcome"] == "TAKEN AS ASKED"
    assert rows[LIMIT]["state"] == "settled"
    assert "the settings MERGE answered HTTP 400: The value is out of range." in (
        rows[LIMIT]["evidence"])
    assert rows[ONCE]["outcome"] == "TRIMMED"
    assert voided(rows) == set()


def test_a_refused_settings_merge_naming_an_account_is_masked() -> None:
    rows, _, output = _run(listDefaults={"EnableVersioning": True, "MajorVersionLimit": 2},
                           rules=[{"contains": "web/lists(guid'",
                                   "verb": "MERGE", "bodyContains": "MajorVersionLimit",
                                   "status": 400, "text": "Refused for ada@example.com."}])

    assert 'Settings="HTTP 400: Refused for <account>"' in rows[LIST]["evidence"]
    assert "HTTP 400: Refused for <account>" in rows[LIMIT]["evidence"]
    assert "ada@example.com" not in output.split("__SENT__")[0]


def test_a_shortfall_that_is_not_the_limit_is_described_not_called_trimmed() -> None:
    rows, _, _ = _run(keepVersions=3)

    assert rows[ONCE]["outcome"] == "FEWER THAN WRITTEN"
    assert rows[ONCE]["evidence"].startswith(
        "limit 2; 3 of the 6 version(s) the writes created answered")


def test_a_write_that_did_not_land_voids_the_reads() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)", "verb": "MERGE", "bodyContains": "trim 4",
                              "status": 409, "text": "Save conflict."}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "Written differs: read 5, declared 6" in rows[ITEM]["evidence"]
    assert "write 4: HTTP 409: Save conflict." in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


def test_a_write_answered_2xx_that_did_not_land_is_not_counted() -> None:
    # The rule answers 204 and never reaches the mock's store, so Title stays at write 2.
    rows, _, _ = _run(trimToLimit=True, rules=[{"contains": "items(1)", "verb": "MERGE",
                                                "bodyContains": "trim 3", "status": 204,
                                                "text": ""}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "Written differs: read 5, declared 6" in rows[ITEM]["evidence"]
    assert 'write 3: HTTP 204, but Title reads back \\"dbmlsp versions trim 2\\"' in (
        rows[ITEM]["evidence"])
    assert voided(rows) == _deps(ITEM)


def test_a_write_whose_read_back_went_unanswered_is_not_counted() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)?$select=Id,Title", "nth": 2, "status": 429,
                              "text": "busy"}])

    assert rows[ITEM]["outcome"] == "FAIL"
    # Write 2's version is never attributed, so no later version can be pinned to one write either.
    assert "Written differs: read 1, declared 6" in rows[ITEM]["evidence"]
    assert "write 2: HTTP 204, but the read-back " in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


def test_a_refused_create_is_kept_in_the_evidence() -> None:
    rows, _, _ = _run(rules=[{"contains": "/items", "verb": "POST", "status": 500,
                              "text": "Denied for ada@example.com."}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "the create: HTTP 500: Denied for <account>" in rows[ITEM]["evidence"]
    assert "ada@example.com" not in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


def test_a_refused_versions_read_is_recorded_with_its_text() -> None:
    rows, _, _ = _run(rules=[{"contains": "/versions", "after": WRITE_READS, "status": 500,
                              "text": "Unexpected."}])

    assert rows[ONCE]["outcome"] == "REFUSED"
    assert "HTTP 500: Unexpected." in rows[ONCE]["evidence"]
    assert rows[WAIT]["outcome"] == "REFUSED"


def test_refusal_text_naming_an_account_is_masked() -> None:
    rows, _, output = _run(rules=[{"contains": "/versions", "after": WRITE_READS, "status": 500,
                                   "text": "Locked by i:0#.f|membership|ada@example.com."}])

    assert "i:0#.f|membership|<account>" in rows[ONCE]["evidence"]
    assert "ada@example.com" not in output.split("__SENT__")[0]


@pytest.mark.parametrize("status", [429, 503])
def test_a_throttled_versions_read_is_left_open(status: int) -> None:
    rows, _, _ = _run(rules=[{"contains": "/versions", "after": WRITE_READS, "status": status,
                              "text": "busy"}])

    assert rows[ONCE]["outcome"] == "NOT ESTABLISHED"
    assert rows[ONCE]["state"] == "open"


def test_a_digest_lost_before_the_writes_leaves_them_open_and_asks_for_a_recycle() -> None:
    rows, sent, output = _run(digestsAllowed=2)

    assert rows[LIST]["outcome"] == "PASS"
    assert rows[LIMIT]["outcome"] == "TAKEN AS ASKED"
    assert all(rows[row_id]["state"] == "open" for row_id in (ITEM, ONCE, WAIT))
    assert "recycle it by hand" in output
    assert not [r for r in sent if r["path"].endswith("/recycle")]


def test_a_versions_read_answered_2xx_with_no_value_array_is_left_open() -> None:
    rows, _, output = _run(rules=[{"contains": "/versions", "after": WRITE_READS, "status": 200,
                                   "text": '{"d": "not a list"}'}])

    for row_id in (ONCE, WAIT):
        assert rows[row_id]["outcome"] == "NOT ESTABLISHED", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert rows[row_id]["evidence"].startswith(
            'limit 2; HTTP 200 carried no value array: {"d": "not a list"}')
    assert voided(rows) == set()
    assert ended_with_report(output)


@pytest.mark.parametrize("spelling", [
    {"odata.nextLink": "https://example.sharepoint.com/sites/probe/_api/web/lists/versions?$skiptoken=2"},
    {"@odata.nextLink": "https://example.sharepoint.com/sites/probe/_api/web/lists/versions?$skiptoken=2"},
    {"d": {"__next": "https://example.sharepoint.com/sites/probe/_api/web/lists/versions?$skiptoken=2"}},
], ids=["odata", "at-odata", "verbose"])
def test_a_versions_answer_with_a_continuation_link_is_not_called_trimmed(
        spelling: dict[str, Any]) -> None:
    # A rule rather than `versionsNext`, so the reads between the writes stay unpaged.
    newest = [{"VersionId": 3072, "VersionLabel": "6.0", "Title": "dbmlsp versions trim 6"},
              {"VersionId": 2560, "VersionLabel": "5.0", "Title": "dbmlsp versions trim 5"}]
    rows, _, output = _run(rules=[{"contains": "/versions", "after": WRITE_READS, "status": 200,
                                   "text": json.dumps({"value": newest, **spelling})}])

    for row_id in (ONCE, WAIT):
        assert rows[row_id]["outcome"] == "NOT COMPARABLE", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert ("the answer carried a continuation link ([TENANT]/sites/probe/_api/web/lists/"
                "versions?$skiptoken=2), which this probe does not follow, so its 2 entries may "
                "not be every version") in rows[row_id]["evidence"]
    assert "example.sharepoint.com" not in str(rows)
    assert ended_with_report(output)


def test_every_request_after_the_claim_goes_by_the_list_id() -> None:
    _, sent, _ = _run(trimToLimit=True)

    titled = [r["path"] for r in sent if "getbytitle" in r["path"]]
    assert titled
    assert all("?$select=Id,Description" in path or "?$select=Id,BaseTemplate" in path
               for path in titled), titled


def test_a_versions_answer_repeating_a_versionid_is_not_counted() -> None:
    repeated = json.dumps({"value": [
        {"VersionId": 3072, "VersionLabel": "6.0", "Title": "dbmlsp versions trim 6"},
        {"VersionId": 3072, "VersionLabel": "6.0", "Title": "dbmlsp versions trim 6"}]})
    rows, _, _ = _run(rules=[{"contains": "/versions", "after": WRITE_READS, "status": 200,
                              "text": repeated}])

    for row_id in (ONCE, WAIT):
        assert rows[row_id]["outcome"] == "NOT COMPARABLE", rows[row_id]
        assert rows[row_id]["state"] == "settled"
        assert "VersionId 3072 answered more than once" in rows[row_id]["evidence"]
        # The lowest VersionId is the repeated one, so no single entry is named for it.
        assert "the lowest VersionId answered carries" not in rows[row_id]["evidence"]
        assert "a VersionId repeats, so no lowest is named" in rows[row_id]["evidence"]


def test_a_write_that_landed_without_a_new_version_is_not_counted() -> None:
    # The mock's second MERGE, write 3, stores its Title and adds no version.
    rows, _, _ = _run(trimToLimit=True, mergesWithoutVersion=[2])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert ("write 3: HTTP 204 and its Title read back, but the versions read after it listed 0 "
            "VersionId(s) no earlier read had") in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)


_LINK = "https://example.sharepoint.com/sites/probe/_api/web/lists/versions?$skiptoken=2"


@pytest.mark.parametrize(("status", "body", "reason"), [
    (429, "busy", "throttled"),
    (200, '{"d": "not a list"}', "HTTP 200 carried no value array"),
    (200, json.dumps({"value": [{"VersionId": 512}], "odata.nextLink": _LINK}),
     "the answer carried a continuation link"),
    (200, json.dumps({"value": [{"VersionId": 512}, {"VersionId": 512}]}),
     "it listed a VersionId more than once"),
    (200, json.dumps({"value": [{"VersionLabel": "1.0"}]}), "an entry carried no VersionId"),
], ids=["throttled", "no-value", "paged", "repeated", "no-id"])
def test_a_versions_read_between_the_writes_that_cannot_be_counted_fails_the_item(
        status: int, body: str, reason: str) -> None:
    rows, _, output = _run(rules=[{"contains": "/versions", "nth": 1, "status": status,
                                   "text": body}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert "the create: HTTP 201 and its Title read back, but the versions read after it: " in (
        rows[ITEM]["evidence"])
    assert reason in rows[ITEM]["evidence"]
    assert voided(rows) == _deps(ITEM)
    assert ended_with_report(output)


def test_a_versions_answer_listing_a_version_no_write_created_is_not_called_trimmed() -> None:
    foreign = json.dumps({"value": [
        {"VersionId": 3072, "VersionLabel": "6.0", "Title": "dbmlsp versions trim 6"},
        {"VersionId": 9728, "VersionLabel": "19.0", "Title": "dbmlsp versions trim 6"}]})
    rows, _, _ = _run(rules=[{"contains": "/versions", "after": WRITE_READS, "status": 200,
                              "text": foreign}])

    for row_id in (ONCE, WAIT):
        assert rows[row_id]["outcome"] == "NOT COMPARABLE", rows[row_id]
        assert rows[row_id]["state"] == "settled"
        assert "VersionId 9728 answered, which no write was seen to create" in (
            rows[row_id]["evidence"])
