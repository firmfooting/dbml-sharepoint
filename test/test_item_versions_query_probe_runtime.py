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
from _probe_runs import catalogued_dependents, run_probe, voided
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
    assert rows[FILTER]["outcome"] == "FILTERED"
    assert "served VersionIds [1536,1024]" in rows[FILTER]["evidence"]
    assert rows[TOP]["outcome"] == "TOPPED"
    assert rows[ORDERBY]["outcome"] == "ASCENDING"
    assert "asked asc" in rows[ORDERBY]["evidence"]
    assert sent[-1]["path"].endswith("/recycle")


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
    assert sent[-1]["path"].endswith("/recycle")
