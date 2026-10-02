"""Execute item-access-probe.js under node against a mock web.

The mock (`_item_acl_mock.py`) adds role assignments to the versions mock, with a switch
for each way a site could answer, so every outcome a row can record is reached. STATE 2
and CLEANUP runs start from `stateOne`, the mock's copy of what STATE 1 leaves. The
probe's settle wait is swapped for none and its test user set.
"""

from typing import Any

import pytest
from _item_acl_mock import ITEM_ACL_MOCK
from _node import NODE
from _paths import MANUAL
from _probe_runs import catalogued_dependents, ended_with_report, run_probe, voided

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "item-access-probe.js"
LIBRARY = "access.item-acl.fixture-library"
GROUPS = "access.item-acl.fixture-library-groups"
FILES = "access.item-acl.fixture-files"
USER = "access.item-acl.fixture-test-user"
DENIED = "access.item-acl.control-test-user-denied"
STATE_ONE = "access.item-acl.fixture-state-one"
C1 = "access.item-acl.break-copies-parent-groups"
C2 = "access.item-acl.parent-grant-after-break"
C3 = "access.item-acl.custom-level-user-grant"
C4 = "access.item-acl.item-only-user-views"
C5 = "access.item-acl.user-binding-removal"
C6 = "access.item-acl.reset-restores-parent"
NO_WAIT = {"  const SETTLE_MS = 2000;": "  const SETTLE_MS = 0;"}
USER_SET = {"  const TEST_USER_LOGIN = 'CHANGE ME - the test user claims login';":
            "  const TEST_USER_LOGIN = 'i:0#.f|membership|tess@example.com';"}
STATE_TWO = {"  const STATE = 1;": "  const STATE = 2;"}
WORKBOOK = {"  const WORKBOOK_URL = '';":
            "  const WORKBOOK_URL = '/sites/probe/Shared Documents/book.xlsx';"}


def _run(*swaps: dict[str, str], gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"),
         user: bool = True, **config: Any,
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    merged = {**NO_WAIT, **(USER_SET if user else {})}
    for swap in swaps:
        merged.update(swap)
    return run_probe(ITEM_ACL_MOCK, PROBE, gates, config, merged)


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates=gates)

    assert sent == []
    assert rows == {}


def test_state_one_on_a_site_that_behaves_as_designed() -> None:
    rows, sent, output = _run()

    assert ended_with_report(output), output[-2000:]
    for fixture in (LIBRARY, GROUPS, FILES, USER, DENIED):
        assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    assert rows[C1]["outcome"] == "COPIED"
    assert rows[C2]["outcome"] == "NOT ON THE FILE"
    for manual in (C3, C4):
        assert rows[manual]["state"] == "awaiting-capture", rows[manual]
    assert "(DeleteListItems false)" in rows[C3]["evidence"]
    assert "the user's levels at the library Limited Access" in rows[C3]["evidence"]
    for later in (STATE_ONE, C5, C6):
        assert rows[later]["outcome"] == "NOT REACHED", rows[later]
    assert "MANUAL HALF (C3, C4)" in output
    # STATE 1 leaves its fixture for STATE 2: nothing is removed or recycled.
    assert not any("removebyid" in r["path"] or r["path"].endswith("/recycle") for r in sent)


def test_state_one_copies_the_workbook_when_one_is_named() -> None:
    rows, sent, _ = _run(WORKBOOK)

    assert rows[FILES]["outcome"] == "PASS"
    assert any("/copyto(strnewurl=" in r["path"] and "item-access-c3.xlsx" in r["path"]
               for r in sent)
    assert "item-access-c3.xlsx" in rows[C4]["evidence"]


def test_a_break_that_copies_nothing_is_recorded_as_such() -> None:
    rows, _, _ = _run(breakCopiesNothing=True)

    assert rows[C1]["outcome"] == "NOT ALL COPIED"
    assert "not on the file:" in rows[C1]["evidence"]


def test_a_library_grant_that_reaches_a_broken_file_is_recorded() -> None:
    rows, _, _ = _run(grantReachesBrokenFiles=True)

    assert rows[C2]["outcome"] == "REACHED THE FILE"


def test_a_user_who_can_already_read_voids_the_rows_that_grant_it() -> None:
    """The control is the only thing that makes C3 and C4 mean the grant did it."""
    rows, sent, _ = _run(userAlreadyReads=True)

    assert rows[DENIED]["outcome"] == "FAIL"
    assert {C3, C4} <= voided(rows)
    assert not any("addroleassignment(principalid=20," in r["path"] for r in sent)


def test_an_unset_test_user_leaves_its_rows_unasked() -> None:
    rows, sent, _ = _run(user=False)

    assert rows[USER]["outcome"] != "PASS"
    assert rows[C1]["outcome"] == "COPIED"
    unasked = {r for r, row in rows.items() if row["state"] in {"void", "open"}}
    assert catalogued_dependents(PROBE.name, USER) <= unasked
    assert not any(r["path"] == "web/ensureuser" for r in sent)


def test_a_site_administrator_as_the_test_user_is_refused() -> None:
    rows, _, _ = _run(userIsAdmin=True)

    assert rows[USER]["outcome"] != "PASS"
    assert rows[C3]["state"] in {"void", "open"}


def test_state_two_on_a_site_that_behaves_as_designed() -> None:
    rows, sent, output = _run(STATE_TWO, stateOne=True)

    assert ended_with_report(output), output[-2000:]
    assert rows[STATE_ONE]["outcome"] == "PASS", rows[STATE_ONE]
    assert rows[C5]["outcome"] == "REMOVED"
    assert rows[C6]["outcome"] == "MATCHES THE LIBRARY"
    for earlier in (LIBRARY, C1, C2, C3, C4):
        assert rows[earlier]["outcome"] == "NOT REACHED", rows[earlier]
    assert not any(r["path"] == "web/lists" for r in sent)


def test_state_two_without_state_one_asks_nothing() -> None:
    rows, sent, _ = _run(STATE_TWO)

    assert rows[STATE_ONE]["outcome"] != "PASS"
    assert catalogued_dependents(PROBE.name, STATE_ONE) <= voided(rows) | {
        r for r, row in rows.items() if row["state"] == "open"}
    assert not any("roleassignment(" in r["path"] for r in sent)


def test_a_removal_that_does_not_take_is_recorded_still_bound() -> None:
    rows, _, _ = _run(STATE_TWO, stateOne=True, ignore=["removeroleassignment"])

    assert rows[C5]["outcome"] == "STILL BOUND"


def test_a_reset_that_does_not_take_is_recorded_still_unique() -> None:
    rows, _, _ = _run(STATE_TWO, stateOne=True, ignore=["resetroleinheritance"])

    assert rows[C6]["outcome"] == "STILL UNIQUE"


def test_a_reset_that_keeps_the_user_grant_differs_from_the_library() -> None:
    rows, _, _ = _run(STATE_TWO, stateOne=True, resetKeepsUser=True)

    assert rows[C6]["outcome"] == "DIFFERS FROM THE LIBRARY"


def test_cleanup_removes_only_what_carries_the_probe_description() -> None:
    rows, sent, _ = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True)

    assert len([r for r in sent if "sitegroups/removebyid(" in r["path"]]) == 3
    assert any(r["path"] == "web/roledefinitions(1073741930)" and r["verb"] == "DELETE"
               for r in sent)
    assert any(r["path"].endswith("/recycle") for r in sent)
    assert all(row["outcome"] == "NOT REACHED" for row in rows.values())


def test_cleanup_leaves_a_group_whose_description_is_not_the_probes() -> None:
    _, sent, output = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                           foreignGroups=True)

    assert not any("sitegroups/removebyid(" in r["path"] for r in sent)
    assert "its description differs" in output
