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
from _versions_mock import mock_list_id

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "item-access-probe.js"
LIBRARY = "access.item-acl.fixture-library"
GROUPS = "access.item-acl.fixture-library-groups"
FILES = "access.item-acl.fixture-files"
USER = "access.item-acl.fixture-test-user"
DENIED = "access.item-acl.control-test-user-denied"
STATE_ONE = "access.item-acl.fixture-state-one"
LEVEL_BITS = "access.item-acl.fixture-level-permissions"
# STATE 2 addresses the library by the Id it reads back, as the mock derives it.
LIBRARY_ID = mock_list_id("dbmlsp Probe ItemAccess")
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
    assert voided(rows) == catalogued_dependents(PROBE.name, DENIED) == {C3, C4}
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
    assert voided(rows) == catalogued_dependents(PROBE.name, USER)


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


@pytest.mark.parametrize(("swaps", "config", "row"), [
    ((), {"throttle": "items(1)?$select=HasUniqueRoleAssignments"}, C1),
    ((), {"throttle": "items(1)/roleassignments?"}, C2),
    ((STATE_TWO,), {"stateOne": True, "throttle": "items(2)?$select=HasUniqueRoleAssignments"}, C6),
    ((STATE_TWO,), {"stateOne": True, "throttle": f"{LIBRARY_ID}')/roleassignments?"}, C6),
], ids=["c1-unique", "c2-file-bindings", "c6-unique", "c6-library-bindings"])
def test_an_unread_value_leaves_its_row_not_established(
        swaps: tuple[dict[str, str], ...], config: dict[str, Any], row: str) -> None:
    rows, _, _ = _run(*swaps, **config)

    assert rows[row]["outcome"] == "NOT ESTABLISHED", rows[row]
    assert rows[row]["state"] == "open"
    assert "unread (" in rows[row]["evidence"]


CREATES = {"web/lists", "web/roledefinitions", "web/sitegroups"}
FOREIGN = "CLEANUP leaves by design"


@pytest.mark.parametrize(("config", "advice"), [
    ({"heldNames": {"roledefinitions": ["dbmlsp ItemAccess No Delete"]}}, FOREIGN),
    ({"heldNames": {"sitegroups": ["dbmlsp ItemAccess B"]}}, FOREIGN),
    ({"stateOne": True}, "run CLEANUP first"),
    ({"stateOne": True, "levelTwice": True}, "held 2 times"),
], ids=["foreign-level", "foreign-group", "own-names", "level-held-twice"])
def test_a_fixed_name_already_on_the_site_stops_state_one_before_it_creates(
        config: dict[str, Any], advice: str) -> None:
    rows, sent, _ = _run(**config)

    assert rows[GROUPS]["outcome"] == "FAIL"
    assert advice in rows[GROUPS]["evidence"]
    assert rows[LIBRARY]["outcome"] == "NOT ESTABLISHED"
    assert voided(rows) == catalogued_dependents(PROBE.name, GROUPS)
    assert not any(r["verb"] == "POST" and r["path"] in CREATES for r in sent)


def test_a_fixed_name_read_that_does_not_answer_creates_nothing() -> None:
    rows, sent, _ = _run(throttle="sitegroups/getbyname")

    assert rows[GROUPS]["outcome"] == "NOT ESTABLISHED"
    assert rows[GROUPS]["state"] == "open"
    assert "a re-run can ask it" in rows[GROUPS]["evidence"]
    assert catalogued_dependents(PROBE.name, GROUPS) <= voided(rows)
    assert not any(r["verb"] == "POST" and r["path"] in CREATES for r in sent)


def test_cleanup_leaves_a_level_whose_name_is_held_twice() -> None:
    _, sent, output = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                           levelTwice=True)

    assert not any(r["path"].startswith("web/roledefinitions(") for r in sent)
    assert "held 2 times" in output


def test_cleanup_leaves_a_library_and_level_whose_description_is_not_the_probes() -> None:
    _, sent, _ = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                      foreignLibrary=True, foreignLevel=True)

    assert not any(r["verb"] == "DELETE" for r in sent)
    assert not any(r["path"].endswith("/recycle") for r in sent)
    assert len([r for r in sent if "sitegroups/removebyid(" in r["path"]]) == 3


def test_a_state_other_than_one_or_two_is_refused_before_anything_is_sent() -> None:
    rows, sent, output = _run({"  const STATE = 1;": "  const STATE = '2';"})

    assert sent == []
    assert rows == {}
    assert "STATE must be the number 1 or 2" in output


def test_an_echoed_percent_encoded_login_is_masked() -> None:
    rows, _, output = _run(throttle="getusereffectivepermissions")

    assert rows[DENIED]["outcome"] == "NOT ESTABLISHED"
    assert "throttled: " in output
    assert "tess" not in output.split("__SENT__")[0]


def test_a_user_grant_that_never_reads_back_leaves_c3_and_c4_unasked() -> None:
    rows, _, output = _run(fileGrantIgnored=True)

    for manual in (C3, C4):
        assert rows[manual]["outcome"] == "NOT ESTABLISHED", rows[manual]
        assert rows[manual]["state"] == "open"
    assert "MANUAL HALF" not in output


def test_a_copied_binding_to_another_level_of_the_same_name_is_not_a_copy() -> None:
    rows, _, _ = _run(breakCopiesTwinLevel=True)

    assert rows[C1]["outcome"] == "NOT ALL COPIED", rows[C1]


def test_a_level_stored_with_other_bits_voids_the_rows_that_rest_on_it() -> None:
    rows, sent, _ = _run(levelAddsDelete=True)

    assert rows[LEVEL_BITS]["outcome"] == "FAIL", rows[LEVEL_BITS]
    assert voided(rows) == catalogued_dependents(PROBE.name, LEVEL_BITS) == {C3, C4}
    assert rows[C1]["outcome"] == "COPIED"
    assert not any("addroleassignment(principalid=20," in r["path"] for r in sent)


@pytest.mark.parametrize(("swaps", "config", "row", "outcome"), [
    ((), {}, C1, "COPIED"),
    ((STATE_TWO,), {"stateOne": True}, C6, "MATCHES THE LIBRARY"),
], ids=["c1", "c6"])
def test_bindings_that_trail_the_inheritance_flag_are_waited_for(
        swaps: tuple[dict[str, str], ...], config: dict[str, Any], row: str, outcome: str) -> None:
    rows, _, _ = _run(*swaps, bindingsLag=2, **config)

    assert rows[row]["outcome"] == outcome, rows[row]


def test_the_delete_trial_is_on_its_own_file_so_state_two_keeps_the_c3_file() -> None:
    rows, sent, output = _run()

    assert rows[FILES]["outcome"] == "PASS"
    assert "Try to delete item-access-c3-delete.txt" in output
    assert "item-access-c3-delete.txt" in rows[C3]["evidence"]
    granted = [r["path"] for r in sent if "addroleassignment(principalid=20," in r["path"]]
    assert len(granted) == 2


def test_cleanup_stops_when_the_library_ownership_read_does_not_answer() -> None:
    _, sent, output = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                           throttle="ItemAccess')?$select=Id,Description")

    assert not any(r["verb"] in {"POST", "DELETE"} and r["path"] != "contextinfo" for r in sent)
    assert "nothing was deleted" in output


def test_cleanup_reads_each_removal_back() -> None:
    _, _, output = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                        ignore=["removebyid", "deleterole"])

    assert "[FAIL] CLEANUP: group 'dbmlsp ItemAccess A'" in output
    assert "[FAIL] CLEANUP: level 'dbmlsp ItemAccess No Delete'" in output
    _, _, clean = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True)
    assert "[OK] CLEANUP: group 'dbmlsp ItemAccess A' removed and read back absent" in clean
    assert "[OK] CLEANUP: level 'dbmlsp ItemAccess No Delete' deleted and read back absent" in clean


def test_a_malformed_levels_answer_is_unread_not_none() -> None:
    rows, _, _ = _run(levelsMalformed=True)

    assert "the user's levels at the library unread (" in rows[C3]["evidence"]


def test_c6_compares_the_file_with_the_library_as_it_reads_after_the_reset() -> None:
    rows, _, _ = _run(STATE_TWO, stateOne=True, resetDropsLimitedAccess=True)

    assert rows[C6]["outcome"] == "MATCHES THE LIBRARY", rows[C6]


def test_role_assignments_without_level_bindings_are_unread() -> None:
    rows, _, _ = _run(STATE_TWO, stateOne=True, malformedAfter="removeroleassignment")

    assert rows[C5]["outcome"] == "NOT ESTABLISHED", rows[C5]
    assert "RoleDefinitionBindings" in rows[C5]["evidence"]


def test_cleanup_stops_when_the_library_recycle_fails() -> None:
    _, sent, output = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                           rules=[{"contains": "/recycle", "status": 429, "text": "throttled"}])

    assert not any("sitegroups/removebyid(" in r["path"] for r in sent)
    assert not any(r["path"].startswith("web/roledefinitions(") for r in sent)
    assert "CLEANUP stopped" in output


def test_groups_and_a_level_that_lose_the_ownership_marker_fail_the_fixture() -> None:
    rows, _, _ = _run(createDropsDescription=True)

    assert rows[GROUPS]["outcome"] == "FAIL", rows[GROUPS]
    assert voided(rows) == catalogued_dependents(PROBE.name, GROUPS)


def test_files_that_never_read_unique_leave_c3_and_c4_unasked() -> None:
    rows, _, output = _run(fileFlagInheriting=True)

    for manual in (C3, C4):
        assert rows[manual]["outcome"] == "NOT ESTABLISHED", rows[manual]
    assert "MANUAL HALF" not in output


def test_the_manual_view_link_is_built_from_the_root_folder() -> None:
    _, _, output = _run(listDefaults={"root": "/sites/probe/ItemAccessSlug"})

    assert "https://example.sharepoint.com/sites/probe/ItemAccessSlug/Forms/AllItems.aspx" in output


@pytest.mark.parametrize("swaps", [(), (STATE_TWO,)], ids=["state-one", "state-two"])
def test_writes_after_the_library_is_claimed_address_it_by_id(
        swaps: tuple[dict[str, str], ...]) -> None:
    _, sent, _ = _run(*swaps, stateOne=bool(swaps))

    writes = [r["path"] for r in sent
              if r["verb"] != "GET" and r["path"].startswith(("web/lists/", "web/lists("))]
    assert writes
    assert not any("getbytitle(" in path for path in writes)


def test_c2_reads_the_library_and_the_file_in_one_window() -> None:
    rows, _, _ = _run(grantReachesBrokenFiles=True, virtualClock=True, libraryGrantMs=20000,
                      fileGrantMs=45000)

    assert rows[C2]["outcome"] == "NOT ON THE FILE", rows[C2]


def test_a_cleanup_request_that_throws_still_reports() -> None:
    _, _, output = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                        rules=[{"contains": "contextinfo", "reject": True}])

    assert ended_with_report(output), output[-2000:]
    assert "CLEANUP aborted" in output


DECOY_ID = mock_list_id("decoy")


@pytest.mark.parametrize(("swaps", "config", "row", "outcome"), [
    ((), {"rebindAfter": "ItemAccess')?$select=Id,BaseTemplate,Description"}, C1, "COPIED"),
    ((STATE_TWO,), {"stateOne": True, "rebindAfter": "ItemAccess')?$select=Id,Description"}, C5,
     "REMOVED"),
], ids=["state-one", "state-two"])
def test_a_title_rebound_to_another_list_mid_run_receives_no_write(
        swaps: tuple[dict[str, str], ...], config: dict[str, Any], row: str, outcome: str) -> None:
    """After the claim the library is renamed and its title given to another list."""
    rows, sent, _ = _run(*swaps, **config)

    assert rows[row]["outcome"] == outcome, rows[row]
    after = sent[next(i for i, r in enumerate(sent) if config["rebindAfter"] in r["path"]) + 1:]
    writes = [r["path"] for r in after if r["verb"] != "GET"]
    assert any(f"guid'{LIBRARY_ID}'" in path for path in writes)
    assert not any("getbytitle(" in path or DECOY_ID in path for path in writes)


def test_cleanup_recycles_the_library_it_read_by_id_when_the_title_is_rebound() -> None:
    _, sent, _ = _run(gates=("CONFIRMED", "ALLOW_WRITES", "CLEANUP"), stateOne=True,
                      rebindAfter="ItemAccess')?$select=Id,Description")

    writes = [r["path"] for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]
    assert f"web/lists(guid'{LIBRARY_ID}')/recycle" in writes
    assert not any("getbytitle(" in path or DECOY_ID in path for path in writes)
