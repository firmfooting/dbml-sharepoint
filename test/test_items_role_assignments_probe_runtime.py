"""Execute items-role-assignments-probe.js under node against a mock web.

The mock (`_items_acl_mock.py`) adds paged item reads and per-item bindings to the versions
mock, with a switch for each way a site could answer, so every outcome both rows can record
is reached: every item carrying its bindings, none, some, a throttle, a refusal and a read
that never answered.
"""

import json
from typing import Any

import pytest
from _items_acl_mock import ITEMS_ACL_MOCK
from _node import NODE
from _paths import MANUAL
from _probe_runs import catalogued_dependents, ended_with_report, run_probe, voided
from _versions_mock import mock_list_id

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "items-role-assignments-probe.js"
LIB = "dbmlsp Probe ItemsAcl"
OWNED = "dbml-sharepoint items role-assignments probe fixture. Safe to delete."
LIBRARY = "access.item-acl.items-fixture-library"
FILES = "access.item-acl.items-fixture-files"
COLUMN = "access.item-acl.items-fixture-owner-column"
BROKEN = "access.item-acl.items-fixture-broken"
BY_ID = "access.item-acl.items-expand-role-assignments"
BY_LOGIN = "access.item-acl.items-expand-role-assignments-by-login"
FIXTURES = (LIBRARY, FILES, COLUMN, BROKEN)
ROLES = ("RoleAssignments/PrincipalId,RoleAssignments/Member/PrincipalType,"
         "RoleAssignments/Member/LoginName,RoleAssignments/RoleDefinitionBindings/Id,"
         "RoleAssignments/RoleDefinitionBindings/Name")
EXPAND = "RoleAssignments/Member,RoleAssignments/RoleDefinitionBindings"
FLOW_READ = {
    BY_ID: f"web/lists/getbytitle('{LIB}')/items?$select=Id,HasUniqueRoleAssignments,"
           f"ProbeOwnerId,{ROLES}&$expand={EXPAND}&$top=100",
    BY_LOGIN: f"web/lists/getbytitle('{LIB}')/items?$select=Id,HasUniqueRoleAssignments,"
              f"ProbeOwner/Name,{ROLES}&$expand=ProbeOwner,{EXPAND}&$top=100",
}
WRITES = ("CONFIRMED", "ALLOW_WRITES")


def _run(gates: tuple[str, ...] = WRITES, **config: Any,
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    return run_probe(ITEMS_ACL_MOCK, PROBE, gates, config)


def _flow_reads(sent: list[dict[str, str]]) -> list[str]:
    return [r["path"] for r in sent if "RoleAssignments" in r["path"] and "/items?" in r["path"]]


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates)

    assert sent == []
    assert rows == {}


def test_a_site_where_every_item_carries_its_bindings() -> None:
    rows, sent, output = _run()

    assert ended_with_report(output), output[-2000:]
    for fixture in FIXTURES:
        assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    for row in (BY_ID, BY_LOGIN):
        assert rows[row]["outcome"] == "EVERY ITEM CARRIES ITS BINDINGS", rows[row]
        assert rows[row]["state"] == "settled"
        evidence = rows[row]["evidence"]
        assert ("page 1: HTTP 200, 100 item(s), 100 carrying RoleAssignments, 2 unique, "
                "nextLink present") in evidence
        assert ("page 2: HTTP 200, 30 item(s), 30 carrying RoleAssignments, 1 unique, "
                "nextLink absent") in evidence
        assert ("broken item 100 (page 1): the page held 3:1073741829 5:1073741826 "
                "7:1073741826, the per-item read 3:1073741829 5:1073741826 7:1073741826, "
                "the same") in evidence
    assert "ProbeOwnerId 7, among the page's principals: yes" in rows[BY_ID]["evidence"]
    # The login is masked as the account it names, and still compared unmasked.
    assert ('ProbeOwner/Name "i:0#.f|membership|<account>", among the page\'s logins: yes'
            in rows[BY_LOGIN]["evidence"])
    assert "ada@example.com" not in output
    # Each shape is sent exactly as the flow sends it, then by its nextLink.
    reads = _flow_reads(sent)
    assert reads[0] == FLOW_READ[BY_ID]
    assert reads[2] == FLOW_READ[BY_LOGIN]
    assert len(reads) == 4
    assert "$skiptoken=Paged=TRUE&p_ID=100" in reads[1]
    # A run leaves its fixture for CLEANUP: nothing is recycled.
    assert not any(r["path"].endswith("/recycle") for r in sent)


def test_a_site_where_no_item_carries_bindings() -> None:
    rows, _, _ = _run(expand="none")

    for row in (BY_ID, BY_LOGIN):
        assert rows[row]["outcome"] == "NO ITEM CARRIES BINDINGS", rows[row]
        assert "carried no RoleAssignments" in rows[row]["evidence"]


def test_bindings_on_the_first_page_only_are_partial_and_name_the_items() -> None:
    rows, _, _ = _run(expand="firstPage")

    assert rows[BY_ID]["outcome"] == "PARTIAL"
    assert "page 2: HTTP 200, 30 item(s), 0 carrying RoleAssignments" in rows[BY_ID]["evidence"]
    assert "without RoleAssignments: items 101, 102" in rows[BY_ID]["evidence"]
    assert "and 20 more" in rows[BY_ID]["evidence"]


def test_bindings_that_differ_from_the_per_item_read_are_partial() -> None:
    rows, _, _ = _run(expand="inheritedEmpty")

    assert rows[BY_ID]["outcome"] == "PARTIAL"
    assert ("inheriting item 1 (page 1): the page held none, the per-item read "
            "3:1073741829 5:1073741826, different") in rows[BY_ID]["evidence"]


@pytest.mark.parametrize(("status", "retry_after", "said"), [
    (429, "7", "Retry-After 7"), (503, None, "no Retry-After header")])
def test_a_throttled_page_is_recorded_with_its_retry_after(
        status: int, retry_after: str | None, said: str) -> None:
    rows, _, _ = _run(failPage={"query": "ProbeOwnerId", "page": 2, "status": status,
                                "text": "Request was throttled", "retryAfter": retry_after})

    assert rows[BY_ID]["outcome"] == "THROTTLED"
    assert rows[BY_ID]["state"] == "open"
    assert "page 1: HTTP 200, 100 item(s)" in rows[BY_ID]["evidence"]
    assert f"page 2: HTTP {status}" in rows[BY_ID]["evidence"]
    assert said in rows[BY_ID]["evidence"]
    assert rows[BY_LOGIN]["outcome"] == "EVERY ITEM CARRIES ITS BINDINGS"


def test_a_refused_read_is_recorded_with_its_error_text() -> None:
    error = '{"odata.error":{"message":{"value":"The field ProbeOwner cannot be expanded."}}}'
    rows, _, _ = _run(failPage={"query": "ProbeOwner/Name", "page": 1, "status": 400,
                                "text": error})

    assert rows[BY_LOGIN]["outcome"] == "REFUSED"
    assert rows[BY_LOGIN]["state"] == "settled"
    assert "HTTP 400: " in rows[BY_LOGIN]["evidence"]
    assert "cannot be expanded" in rows[BY_LOGIN]["evidence"]
    assert rows[BY_ID]["outcome"] == "EVERY ITEM CARRIES ITS BINDINGS"


@pytest.mark.parametrize(("fail", "said"), [
    ({"status": 200, "text": '{"odata.metadata":"none"}'}, "carried no value array"),
    ({"reject": True}, "no response: Failed to fetch"),
    ({"status": 401, "text": "Unauthorized"}, "was not authorised (HTTP 401)")],
    ids=["no-value-array", "no-response", "unauthorised"])
def test_a_read_that_says_nothing_leaves_the_row_open(fail: dict[str, Any], said: str) -> None:
    rows, _, _ = _run(failPage={"query": "ProbeOwnerId", "page": 1, **fail})

    assert rows[BY_ID]["outcome"] == "NOT ESTABLISHED"
    assert rows[BY_ID]["state"] == "open"
    assert said in rows[BY_ID]["evidence"]


def test_a_next_link_that_never_ends_is_cut_and_partial() -> None:
    rows, sent, _ = _run(nextLoops="ProbeOwnerId")

    assert rows[BY_ID]["outcome"] == "PARTIAL"
    assert "the nextLink still present after 20 pages" in rows[BY_ID]["evidence"]
    assert len([p for p in _flow_reads(sent) if "ProbeOwnerId" in p]) == 20


def test_too_few_files_voids_what_rests_on_them_and_reads_no_page() -> None:
    rows, sent, _ = _run(filesKept=50)

    assert rows[FILES]["outcome"] == "FAIL"
    assert "Count=50" in rows[FILES]["evidence"]
    assert catalogued_dependents(PROBE.name, FILES) <= voided(rows)
    assert _flow_reads(sent) == []


def test_a_refused_owner_column_voids_the_rest() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/fields", "verb": "POST", "status": 400,
                                 "text": "Invalid field"}])

    assert rows[COLUMN]["outcome"] == "FAIL"
    assert catalogued_dependents(PROBE.name, COLUMN) <= voided(rows)
    assert not any("breakroleinheritance" in r["path"] for r in sent)


def test_a_break_that_does_not_take_voids_both_rows() -> None:
    rows, sent, _ = _run(rules=[{"contains": "breakroleinheritance", "status": 200,
                                 "text": "{}"}])

    assert rows[BROKEN]["outcome"] == "FAIL"
    assert "Unique differs" in rows[BROKEN]["evidence"]
    assert {BY_ID, BY_LOGIN} <= voided(rows)
    assert _flow_reads(sent) == []


def _seeded(description: str) -> dict[str, Any]:
    return {"lists": {LIB: {"Id": mock_list_id(LIB), "Title": LIB, "BaseTemplate": 101,
                            "Description": description, "fields": {}, "items": []}}}


def test_a_library_already_there_is_never_built_over() -> None:
    rows, sent, _ = _run(**_seeded(OWNED))

    assert rows[LIBRARY]["outcome"] == "FAIL"
    assert "already exists" in rows[LIBRARY]["evidence"]
    assert catalogued_dependents(PROBE.name, LIBRARY) <= voided(rows)
    assert not any(r["verb"] != "GET" for r in sent)


def test_cleanup_recycles_the_library_with_the_probes_description() -> None:
    rows, sent, _ = _run((*WRITES, "CLEANUP"), **_seeded(OWNED))

    assert any(r["path"].endswith("/recycle") for r in sent)
    assert all(row["outcome"] == "NOT REACHED" for row in rows.values())


def test_cleanup_leaves_a_library_whose_description_is_not_the_probes() -> None:
    _, sent, output = _run((*WRITES, "CLEANUP"), **_seeded("somebody else's library"))

    assert not any(r["path"].endswith("/recycle") for r in sent)
    assert "its description differs" in output


def test_a_count_read_with_no_value_array_leaves_the_files_open() -> None:
    rows, sent, _ = _run(rules=[{"contains": "$select=Id&", "status": 200, "text": "{}"}])

    assert rows[FILES]["outcome"] == "NOT ESTABLISHED", rows[FILES]
    assert rows[FILES]["state"] == "open"
    assert "carried no value array" in rows[FILES]["evidence"]
    assert not {BY_ID, BY_LOGIN} & voided(rows)
    assert _flow_reads(sent) == []


def test_a_bindings_read_with_no_value_array_leaves_the_broken_fixture_open() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/roleassignments?$expand", "status": 200,
                                 "text": "{}"}])

    assert rows[BROKEN]["outcome"] == "NOT ESTABLISHED", rows[BROKEN]
    assert rows[BROKEN]["state"] == "open"
    assert not {BY_ID, BY_LOGIN} & voided(rows)
    assert _flow_reads(sent) == []


def test_an_unanswered_account_read_leaves_the_broken_fixture_open() -> None:
    rows, sent, _ = _run(rules=[{"contains": "web/currentuser", "status": 503, "text": "busy"}])

    assert rows[BROKEN]["outcome"] == "NOT ESTABLISHED", rows[BROKEN]
    assert rows[BROKEN]["state"] == "open"
    assert "HTTP 503" in rows[BROKEN]["evidence"]
    assert not {BY_ID, BY_LOGIN} & voided(rows)
    assert _flow_reads(sent) == []


def test_a_value_the_page_answers_is_masked_in_the_evidence() -> None:
    login = "i:0#.f|membership|bob@example.com"
    page = {"value": [{"Id": 1, "HasUniqueRoleAssignments": False, "ProbeOwnerId": None,
                       "RoleAssignments": [{"PrincipalId": login,
                                            "RoleDefinitionBindings": [{"Id": 1}]}]}]}
    rows, _, output = _run(rules=[{"contains": "ProbeOwnerId,RoleAssignments", "status": 200,
                                   "text": json.dumps(page)}])

    assert rows[BY_ID]["outcome"] == "PARTIAL", rows[BY_ID]
    assert "the page held i:0#.f|membership|<account>" in rows[BY_ID]["evidence"]
    assert "bob@example.com" not in output


def _paged(contains: str, first: list[dict[str, Any]], second: list[dict[str, Any]],
           query: str) -> list[dict[str, Any]]:
    """Rules answering the first two reads holding `contains` with a page each, linked."""
    link = ("https://example.sharepoint.com/sites/probe/_api/web/lists/"
            f"getbytitle('{LIB}')/items?p=2&{query}")
    return [{"contains": contains, "nth": 1, "status": 200,
             "text": json.dumps({"value": first, "odata.nextLink": link})},
            {"contains": contains, "nth": 1, "status": 200, "text": json.dumps({"value": second})}]


def _bound(item: int) -> dict[str, Any]:
    """An item as the mock's per-item read binds it, with its bindings expanded."""
    broken = item in (10, 100, 111)
    pairs = [(3, 1073741829), (5, 1073741826)] + ([(7, 1073741826)] if broken else [])
    return {"Id": item, "HasUniqueRoleAssignments": broken, "ProbeOwnerId": None,
            "RoleAssignments": [{"PrincipalId": p, "RoleDefinitionBindings": [{"Id": level}]}
                                for p, level in pairs]}


def test_an_item_id_that_is_not_a_whole_number_fails_the_files_and_writes_nothing() -> None:
    first = [{"Id": "10)/recycle" if n == 10 else n} for n in range(1, 101)]
    rows, sent, _ = _run(rules=_paged("$select=Id&", first, [{"Id": n} for n in range(101, 131)],
                                      "$select=Id&$top=100"))

    assert rows[FILES]["outcome"] == "FAIL", rows[FILES]
    assert "Integers differs" in rows[FILES]["evidence"]
    assert not any("breakroleinheritance" in r["path"] for r in sent)


def test_a_read_level_id_that_is_not_a_whole_number_grants_nothing() -> None:
    rows, sent, _ = _run(rules=[{"contains": "getbyname('Read')", "status": 200,
                                 "text": '{"Id": "1073741826)/x"}'}])

    assert rows[BROKEN]["outcome"] == "FAIL", rows[BROKEN]
    assert not any("addroleassignment" in r["path"] for r in sent)
    assert not any("breakroleinheritance" in r["path"] for r in sent)


def test_cleanup_whose_ownership_read_is_throttled_recycles_nothing_and_says_so() -> None:
    _, sent, output = _run((*WRITES, "CLEANUP"), rules=[
        {"contains": "$select=Id,Description", "status": 503, "text": "busy"}], **_seeded(OWNED))

    assert not any(r["path"].endswith("/recycle") for r in sent)
    assert "[FAIL] CLEANUP" in output
    assert "Paste CLEANUP again" in output
    assert "no library" not in output


def test_pages_holding_no_items_are_partial_not_no_item_carries() -> None:
    rows, _, _ = _run(rules=[{"contains": "ProbeOwnerId,RoleAssignments", "status": 200,
                              "text": '{"value": []}'}])

    assert rows[BY_ID]["outcome"] == "PARTIAL", rows[BY_ID]
    assert "0 item(s) read of the 130 counted" in rows[BY_ID]["evidence"]


def test_files_are_uploaded_as_raw_text() -> None:
    _, sent, _ = _run()

    adds = [r for r in sent if "/Files/add(" in r["path"]]
    assert len(adds) == 130
    assert adds[0]["type"] == "text/plain"
    assert adds[0]["body"] == "dbmlsp items role-assignments probe file"


def test_no_retry_after_is_judged_on_the_page_that_stopped() -> None:
    rows, _, _ = _run(pageRetryAfter="1", failPage={"query": "ProbeOwnerId", "page": 2,
                                                    "status": 429, "text": "throttled"})

    assert rows[BY_ID]["outcome"] == "THROTTLED", rows[BY_ID]
    assert "no Retry-After header" in rows[BY_ID]["evidence"]


def test_a_next_link_with_no_api_path_is_not_followed() -> None:
    page = {"value": [_bound(1)], "odata.nextLink": "https://example.sharepoint.com/elsewhere?p=2"}
    rows, sent, _ = _run(rules=[{"contains": "ProbeOwnerId,RoleAssignments", "status": 200,
                                 "text": json.dumps(page)}])

    assert rows[BY_ID]["outcome"] == "NOT ESTABLISHED", rows[BY_ID]
    assert rows[BY_ID]["state"] == "open"
    assert "no /_api/ path" in rows[BY_ID]["evidence"]
    assert len([p for p in _flow_reads(sent) if "ProbeOwnerId" in p]) == 1


def test_a_duplicate_does_not_stand_in_for_a_missing_item() -> None:
    first = [_bound(n) for n in range(1, 101) if n != 50]
    second = [_bound(51)] + [_bound(n) for n in range(101, 131)]
    query = f"$select=Id,HasUniqueRoleAssignments,ProbeOwnerId,{ROLES}&$expand={EXPAND}&$top=100"
    rows, _, _ = _run(rules=_paged("ProbeOwnerId,RoleAssignments", first, second, query))

    assert rows[BY_ID]["outcome"] == "PARTIAL", rows[BY_ID]
    assert "130 item(s) read of the 130 counted" in rows[BY_ID]["evidence"]
