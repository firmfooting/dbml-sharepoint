"""Execute item-versions-query-probe.js under node against a mock web.

The mock (`_versions_mock.py`) answers `items(id)/versions` newest first and honours the
four options unless told to ignore them, so both kinds of site answer are reached. The
test prelude projects every GET to its `$select`; the case for a site that ignores `$select`
turns that off in the mock.
"""

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
