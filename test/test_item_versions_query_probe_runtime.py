"""Execute item-versions-query-probe.js under node against a mock web.

The mock (`_versions_mock.py`) answers `items(id)/versions` newest first and honours the
four options unless told to ignore them, so both kinds of site answer are reached. The
test prelude projects every GET to its `$select`; the case for a site that ignores `$select`
turns that off in the mock.
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

PROBE = MANUAL / "item-versions-query-probe.js"
LIST = "query.odata.fixture-versions-query-list"
ITEMS = "query.odata.fixture-versions-query-items"
READ = "query.odata.control-versions-read"
FILTER_CONTROL = "query.odata.control-versions-items-filter"
TOP_CONTROL = "query.odata.control-versions-items-top-orderby"
ORDER = "query.odata.versions-default-order"
SELECT = "query.odata.versions-select"
FILTER = "query.odata.versions-filter"
TOP = "query.odata.versions-top"
ORDERBY = "query.odata.versions-orderby"
SUBJECTS = (ORDER, SELECT, FILTER, TOP, ORDERBY)


def _run(gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"), **config: Any,
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    return run_probe(VERSIONS_MOCK, PROBE, gates, config)


def _deps(fixture: str) -> set[str]:
    return catalogued_dependents(PROBE.name, fixture)


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates)

    assert sent == []
    assert rows == {}


def test_a_site_honouring_every_option_is_recorded_as_such() -> None:
    rows, sent, _ = _run()

    for row_id in (LIST, ITEMS, READ, FILTER_CONTROL, TOP_CONTROL):
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    assert rows[ORDER]["outcome"] == "DESCENDING"
    assert "VersionIds in the order answered: [1536,1024,512]" in rows[ORDER]["evidence"]
    assert rows[SELECT]["outcome"] == "NARROWED"
    assert "the plain read also carried" in rows[SELECT]["evidence"]
    assert "HTTP 201" in rows[ITEMS]["evidence"]
    assert rows[FILTER]["outcome"] == "FILTERED"
    assert "served VersionIds [1536,1024]" in rows[FILTER]["evidence"]
    assert rows[TOP]["outcome"] == "TOPPED"
    assert rows[ORDERBY]["outcome"] == "ASCENDING"
    assert "asked asc" in rows[ORDERBY]["evidence"]
    assert recycled_last(sent)


def test_a_site_ignoring_every_option_is_recorded_as_such() -> None:
    rows, _, _ = _run(versionsIgnoreOptions=True, unprojected=True)

    assert rows[SELECT]["outcome"] == "NOT NARROWED"
    assert "ProbeChoice" in rows[SELECT]["evidence"]
    assert "Editor" in rows[SELECT]["evidence"]
    assert rows[FILTER]["outcome"] == "UNFILTERED"
    assert rows[TOP]["outcome"] == "NOT TOPPED"
    assert rows[ORDERBY]["outcome"] == "DESCENDING"
    for row_id in SUBJECTS:
        assert rows[row_id]["state"] == "settled"


def test_a_plain_read_carrying_only_the_selected_names_is_not_comparable() -> None:
    narrow = ('{"value": [{"VersionId": 1024, "VersionLabel": "2.0", "ProbeChoice": "Q2"},'
              ' {"VersionId": 512, "VersionLabel": "1.0", "ProbeChoice": "Q1"}]}')
    rows, _, _ = _run(rules=[{"contains": "items(1)/versions", "status": 200, "text": narrow}])

    assert rows[READ]["outcome"] == "PASS"
    assert rows[SELECT]["outcome"] == "NOT COMPARABLE"
    assert "carried nothing beyond the selected names" in rows[SELECT]["evidence"]


@pytest.mark.parametrize("answer", [
    '{"value": [{"VersionId": 1536}, {"VersionId": 1024}, {"VersionId": 512}]}',
    ('{"value": [{"VersionId": 1536, "VersionLabel": "3.0", "ProbeChoice": "Q3"},'
     ' {"VersionId": 1024, "VersionLabel": "2.0"}]}'),
], ids=["every-entry", "one-entry"])
def test_a_select_answer_lacking_a_selected_name_is_not_called_narrowed(answer: str) -> None:
    rows, _, _ = _run(rules=[{"contains": "/versions?$select", "status": 200, "text": answer}])

    assert rows[SELECT]["outcome"] == "SELECTED MISSING"
    assert rows[SELECT]["state"] == "settled"
    assert "which every entry of the plain read carried" in rows[SELECT]["evidence"]


def test_an_empty_select_answer_is_not_called_narrowed() -> None:
    rows, _, _ = _run(rules=[{"contains": "/versions?$select", "status": 200,
                              "text": '{"value": []}'}])

    assert rows[SELECT]["outcome"] == "NO VERSIONS"
    assert "0 entries carrying nothing" in rows[SELECT]["evidence"]


def test_a_refused_column_create_is_kept_in_the_items_evidence() -> None:
    rows, _, _ = _run(rules=[{"contains": "/fields", "verb": "POST", "status": 400,
                              "text": "The column is not valid."}])

    assert "HTTP 400: The column is not valid." in rows[ITEMS]["evidence"]


def test_an_ascending_plain_read_asks_for_the_opposite_order() -> None:
    rows, _, _ = _run(versionsAscending=True)

    assert rows[ORDER]["outcome"] == "ASCENDING"
    assert "asked desc" in rows[ORDERBY]["evidence"]
    assert rows[ORDERBY]["outcome"] == "DESCENDING"


def test_a_refused_option_is_recorded_with_its_text() -> None:
    rows, _, _ = _run(rules=[{"contains": "/versions?$filter", "status": 400,
                              "text": "The query is not valid."}])

    assert rows[FILTER]["outcome"] == "REFUSED"
    assert "HTTP 400: The query is not valid." in rows[FILTER]["evidence"]
    assert rows[TOP]["outcome"] == "TOPPED"


def test_a_failed_filter_control_voids_only_the_filter_row() -> None:
    rows, _, _ = _run(rules=[{"contains": "/items?$select=Id&$filter", "status": 200,
                              "text": '{"value": []}'}])

    assert rows[FILTER_CONTROL]["outcome"] == "FAIL"
    assert voided(rows) == _deps(FILTER_CONTROL) == {FILTER}
    assert rows[TOP]["outcome"] == "TOPPED"


def test_a_throttled_top_control_leaves_its_rows_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "/items?$select=Id&$orderby", "status": 429,
                              "text": "busy"}])

    assert rows[TOP_CONTROL]["outcome"] == "NOT ESTABLISHED"
    for row_id in (TOP, ORDERBY):
        assert rows[row_id]["state"] == "open"
        assert "a re-run can ask it" in rows[row_id]["evidence"]
    assert rows[FILTER]["outcome"] == "FILTERED"


def test_a_plain_read_of_two_versions_is_enough_to_ask_the_options() -> None:
    rows, _, _ = _run(keepVersions=2)

    assert rows[READ]["outcome"] == "PASS"
    assert "2 entries" in rows[READ]["evidence"]
    assert voided(rows) == set()
    for row_id in SUBJECTS:
        assert rows[row_id]["state"] == "settled"


def test_a_plain_read_of_one_version_voids_everything_after_it() -> None:
    rows, _, _ = _run(keepVersions=1)

    assert rows[READ]["outcome"] == "FAIL"
    assert "1 entry," in rows[READ]["evidence"]
    assert voided(rows) == _deps(READ)


def test_a_throttled_plain_read_leaves_everything_after_it_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)/versions", "status": 503, "text": "busy"}])

    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    for row_id in (FILTER_CONTROL, TOP_CONTROL, *SUBJECTS):
        assert rows[row_id]["state"] == "open"


def test_an_item_write_that_did_not_land_voids_the_reads() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)", "verb": "MERGE", "status": 412,
                              "text": "conflict"}])

    assert rows[ITEMS]["outcome"] == "FAIL"
    assert voided(rows) == _deps(ITEMS)


def test_a_list_that_will_not_take_versioning_voids_everything() -> None:
    rows, sent, _ = _run(listMerge={"EnableVersioning": False})

    assert rows[LIST]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIST)
    assert recycled_last(sent)


def test_an_option_answered_2xx_with_no_value_array_is_left_open() -> None:
    rows, _, output = _run(rules=[{"contains": "/versions?$top", "status": 200,
                                   "text": '{"d": "not a list"}'}])

    assert rows[TOP]["outcome"] == "NOT ESTABLISHED"
    assert rows[TOP]["state"] == "open"
    assert rows[TOP]["evidence"] == (
        '$top=1: HTTP 200 carried no value array: {"d": "not a list"}')
    assert rows[FILTER]["outcome"] == "FILTERED"
    assert voided(rows) == set()
    assert ended_with_report(output)


def test_a_digest_lost_mid_run_is_caught_and_the_rest_left_open() -> None:
    rows, sent, output = _run(digestsAllowed=3)

    assert rows[LIST]["outcome"] == "PASS"
    assert "probe aborted: contextinfo failed: HTTP 403. The unasked rows stay open." in output
    assert all(rows[row_id]["state"] == "open" for row_id in (ITEMS, READ, *SUBJECTS))
    assert "recycle it by hand" in output
    assert not [r for r in sent if r["path"].endswith("/recycle")]
    assert ended_with_report(output)


NEXT = {"odata.nextLink": "https://example.sharepoint.com/sites/probe/_api/web/lists/versions?$skiptoken=2"}


def test_a_plain_read_with_a_continuation_link_leaves_every_option_row_open() -> None:
    rows, _, output = _run(versionsNext=NEXT)

    assert rows[READ]["outcome"] == "PASS"
    for row_id in SUBJECTS:
        assert rows[row_id]["outcome"] == "NOT COMPARABLE", rows[row_id]
        assert rows[row_id]["state"] == "open"
        assert "which this probe does not follow" in rows[row_id]["evidence"]
    for row_id in (FILTER_CONTROL, TOP_CONTROL):
        assert rows[row_id]["outcome"] == "NOT ESTABLISHED"
        assert rows[row_id]["evidence"].startswith(
            "not asked: the plain versions read is not known")
    assert voided(rows) == set()
    assert ended_with_report(output)


def test_an_option_answer_with_a_continuation_link_is_not_compared() -> None:
    rows, _, _ = _run(versionsNext=NEXT, versionsNextFor="$top=1")

    assert rows[TOP]["outcome"] == "NOT COMPARABLE"
    assert rows[TOP]["state"] == "open"
    assert rows[TOP]["evidence"].startswith("$top=1: the answer carried a continuation link")
    assert rows[FILTER]["outcome"] == "FILTERED"


def test_every_request_after_the_claim_goes_by_the_list_id() -> None:
    _, sent, _ = _run()

    titled = [r["path"] for r in sent if "getbytitle" in r["path"]]
    assert titled
    assert all("?$select=Id,Description" in path or "?$select=Id,BaseTemplate" in path
               for path in titled), titled


def test_a_write_answered_2xx_that_did_not_land_stops_the_writes_and_fails_the_items() -> None:
    rows, sent, _ = _run(rules=[{"contains": "items(1)", "verb": "MERGE",
                                 "bodyContains": '"ProbeChoice":"Q2"', "status": 204, "text": ""}])

    assert rows[ITEMS]["outcome"] == "FAIL"
    assert "Written differs: read 2, declared 4" in rows[ITEMS]["evidence"]
    assert "A's write of Q2: HTTP 204, but ProbeChoice reads back \\\"Q1\\\"" in (
        rows[ITEMS]["evidence"])
    assert voided(rows) == _deps(ITEMS)
    assert len([r for r in sent if r["verb"] == "MERGE" and "items(1)" in r["path"]]) == 1


def test_a_write_whose_read_back_went_unanswered_is_not_counted() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)?$select=Id,Title,ProbeChoice", "nth": 1,
                              "status": 429, "text": "busy"}])

    assert rows[ITEMS]["outcome"] == "NOT ESTABLISHED"
    assert "was throttled (HTTP 429)" in rows[ITEMS]["evidence"]
    assert voided(rows) == set()


@pytest.mark.parametrize(("option", "row_id", "answer"), [
    ("$select", SELECT, [{"VersionId": 1536, "VersionLabel": "3.0", "ProbeChoice": "Q3"},
                         {"VersionId": 1024, "VersionLabel": "2.0", "ProbeChoice": "Q2"}]),
    ("$top", TOP, [{"VersionId": 9999, "VersionLabel": "9.0", "ProbeChoice": "Q3"}]),
    ("$orderby", ORDERBY, [{"VersionId": 512, "VersionLabel": "1.0", "ProbeChoice": "Q1"},
                           {"VersionId": 1536, "VersionLabel": "3.0", "ProbeChoice": "Q3"}]),
], ids=["select-subset", "top-unknown", "orderby-subset"])
def test_an_option_serving_other_versions_than_the_plain_read_is_named_so(
        option: str, row_id: str, answer: list[dict[str, Any]]) -> None:
    rows, _, _ = _run(rules=[{"contains": f"/versions?{option}", "status": 200,
                              "text": json.dumps({"value": answer})}])

    assert rows[row_id]["outcome"] == "OTHER ROWS", rows[row_id]


def test_a_plain_read_answered_2xx_with_no_value_array_leaves_everything_after_it_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)/versions", "nth": 1, "status": 200,
                              "text": '{"d": "x"}'}])

    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    for row_id in (FILTER_CONTROL, TOP_CONTROL, *SUBJECTS):
        assert rows[row_id]["state"] == "open", rows[row_id]
    assert voided(rows) == set()


def test_an_item_list_control_answered_2xx_with_no_rows_leaves_its_row_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "/items?$select=Id&$filter", "status": 200,
                              "text": '{"d": 1}'}])

    assert rows[FILTER_CONTROL]["outcome"] == "NOT ESTABLISHED"
    assert rows[FILTER]["state"] == "open"
    assert voided(rows) == set()


def test_an_unordered_plain_read_asks_ascending_and_does_not_call_it_opposite() -> None:
    unordered = json.dumps({"value": [
        {"VersionId": 1024, "VersionLabel": "2.0", "ProbeChoice": "Q2"},
        {"VersionId": 1536, "VersionLabel": "3.0", "ProbeChoice": "Q3"},
        {"VersionId": 512, "VersionLabel": "1.0", "ProbeChoice": "Q1"}]})
    rows, _, _ = _run(rules=[{"contains": "items(1)/versions", "nth": 1, "status": 200,
                              "text": unordered}])

    assert rows[ORDER]["outcome"] == "UNORDERED"
    assert rows[ORDERBY]["outcome"] == "ASCENDING"
    assert rows[ORDERBY]["evidence"].startswith(
        "$orderby=VersionId asc: asked asc, since the plain read was UNORDERED and has no opposite")
    assert "opposite to" not in rows[ORDERBY]["evidence"]


def test_the_top_control_expects_the_greater_id_read_back_whichever_item_has_it() -> None:
    rows, _, _ = _run(itemIds=[5, 3])

    assert rows[TOP_CONTROL]["outcome"] == "PASS", rows[TOP_CONTROL]
    assert "served [5], want [5]" in rows[TOP_CONTROL]["evidence"]
    assert rows[TOP]["outcome"] == "TOPPED"
    assert voided(rows) == set()


def test_a_plain_read_repeating_a_versionid_voids_the_option_rows() -> None:
    repeated = json.dumps({"value": [
        {"VersionId": 1536, "VersionLabel": "3.0"}, {"VersionId": 1536, "VersionLabel": "3.0"},
        {"VersionId": 512, "VersionLabel": "1.0"}]})
    rows, _, _ = _run(rules=[{"contains": "items(1)/versions", "nth": 1, "status": 200,
                              "text": repeated}])

    assert rows[READ]["outcome"] == "FAIL"
    assert voided(rows) == _deps(READ)
    assert "none repeated" in rows[FILTER]["evidence"]


def test_a_refusal_naming_this_account_by_display_name_is_masked() -> None:
    rows, _, output = _run(rules=[{"contains": "/versions?$filter", "status": 400,
                                   "text": "Refused while Ada Probe holds the item."}])

    assert "HTTP 400: Refused while <name> holds the item." in rows[FILTER]["evidence"]
    assert "Ada Probe" not in output.split("__SENT__")[0]


def test_two_items_answered_one_id_fail_the_items_fixture() -> None:
    rows, _, _ = _run(itemIds=[1, 1], sameIdReplaces=True)

    assert rows[ITEMS]["outcome"] == "FAIL"
    assert "Distinct differs: read false, declared true" in rows[ITEMS]["evidence"]


@pytest.mark.parametrize(("contains", "text", "row_id"), [
    pytest.param("/versions?$filter", '{"value": [{"VersionId": "1536"}, {"VersionId": "1024"}]}',
                 FILTER, id="filter"),
    pytest.param("/versions?$top", '{"value": [{"VersionId": "1536"}]}', TOP, id="top"),
    pytest.param("/versions?$select",
                 json.dumps({"value": [
                     {"VersionId": str(v), "VersionLabel": f"{n}.0", "ProbeChoice": "Q"}
                     for v, n in ((1536, 3), (1024, 2), (512, 1))]}),
                 SELECT, id="select"),
])
def test_versionids_served_as_text_are_not_the_plain_reads_numbers(
        contains: str, text: str, row_id: str) -> None:
    rows, _, _ = _run(rules=[{"contains": contains, "status": 200, "text": text}])

    assert rows[row_id]["outcome"] == "OTHER ROWS", rows[row_id]


def test_an_item_list_control_serving_the_id_as_text_fails() -> None:
    rows, _, _ = _run(rules=[{"contains": "/items?$select=Id&$filter", "status": 200,
                              "text": '{"value": [{"Id": "1"}]}'}])

    assert rows[FILTER_CONTROL]["outcome"] == "FAIL"


def test_an_unavailable_item_write_leaves_the_items_open() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)", "verb": "MERGE", "status": 503,
                              "text": "busy"}])

    assert rows[ITEMS]["outcome"] == "NOT ESTABLISHED"
    assert all(rows[row_id]["state"] == "open" for row_id in _deps(ITEMS))


@pytest.mark.parametrize(("contains", "row_id"), [
    ("/versions?$top", TOP), ("/versions?$filter", FILTER), ("/versions?$select", SELECT),
    ("/versions?$orderby", ORDERBY)])
def test_an_option_answer_with_a_malformed_entry_is_not_established(
        contains: str, row_id: str) -> None:
    rows, _, output = _run(rules=[{"contains": contains, "status": 200,
                                   "text": '{"value": [7]}'}])

    assert rows[row_id]["outcome"] == "NOT ESTABLISHED", rows[row_id]
    assert "carried entry 1 of its value array as 7, not an object" in rows[row_id]["evidence"]
    assert ended_with_report(output)


def test_a_malformed_item_list_control_answer_is_not_established() -> None:
    rows, _, output = _run(rules=[{"contains": "/items?$select=Id&$filter", "status": 200,
                                   "text": '{"value": [null]}'}])

    assert rows[FILTER_CONTROL]["outcome"] == "NOT ESTABLISHED"
    assert "carried entry 1 of its value array as null" in rows[FILTER_CONTROL]["evidence"]
    assert ended_with_report(output)
