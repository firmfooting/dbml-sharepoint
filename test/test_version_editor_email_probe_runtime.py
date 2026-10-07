"""Execute version-editor-email-probe.js under node against a mock web.

Each case reaches one branch: the setup run and each way its fixtures fail,
each report outcome, the fixture that voids the question (a user whose
sign-in name is their email, or who cannot be read), a refused versions read,
and a paste with the second account left blank.
"""
from __future__ import annotations

from typing import Any

import pytest
from _node import NODE
from _paths import MANUAL
from _probe_runs import ended_with_report, run_probe, voided
from _version_editor_mock import EDITOR_MOCK

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "version-editor-email-probe.js"
GATES = ("CONFIRMED", "ALLOW_WRITES")
QUESTION = "field.version.editor-email-sign-in"
PERSON = "field.version.person-email-matches-editor"
DISTINCT = "field.version.fixture-editor-distinct-names"
READ = "field.version.control-editor-versions-read"
EMAIL = "second@example.com"
LOGIN = "second.login@example.onmicrosoft.com"
LIST_FIXTURE = "field.version.fixture-editor-list"
PERSON_WRITE = "field.version.fixture-editor-person-write"
FILLED = {"  const SECOND_ACCOUNT = '';": f"  const SECOND_ACCOUNT = '{LOGIN}';"}
REPORT = {"  const MODE = 'setup';": "  const MODE = 'report';"}
CLEANUP = {"  const CLEANUP = false;": "  const CLEANUP = true;"}

Run = tuple[dict[str, dict[str, str]], list[dict[str, str]], str]


def _run(gates: tuple[str, ...] = GATES, swaps: dict[str, str] | None = None,
         **config: Any) -> Run:
    # The probe has no per-run title token to pin, since its list title is fixed.
    return run_probe(EDITOR_MOCK, PROBE, gates, config, swaps=swaps, pin=False)


def _report(**config: Any) -> Run:
    # A report run reads the list its setup run made.
    config.setdefault("existing", "owned")
    return _run(swaps={**FILLED, **REPORT}, **config)


def test_an_unedited_paste_prints_its_plan_and_sends_nothing() -> None:
    _, sent, output = _run(gates=())
    assert sent == [] and "Would" in output


def test_a_paste_with_no_second_account_refuses_to_run() -> None:
    _, sent, output = _run()
    assert sent == [] and "SECOND_ACCOUNT" in output


def test_setup_makes_the_list_writes_the_person_and_asks_for_the_manual_edit() -> None:
    rows, sent, output = _run(swaps=FILLED)
    assert rows[QUESTION]["outcome"] == "MANUAL"
    assert any(s["method"] == "POST" and s["path"].endswith("/_api/web/lists") for s in sent)
    assert ended_with_report(output)
    assert LOGIN not in output  # the account typed at paste time is never printed
    # Every write after the create goes to the list by the Id the create answered.
    assert not any(s["method"] == "POST" and "getbytitle" in s["path"] for s in sent)


def test_setup_stops_when_another_list_takes_the_title_before_its_create() -> None:
    rows, sent, _ = _run(swaps=FILLED, raced=True)
    assert rows[LIST_FIXTURE]["outcome"] == "FAIL"
    assert {PERSON_WRITE, QUESTION, PERSON} <= voided(rows)
    after = sent[next(i for i, s in enumerate(sent) if s["path"].endswith("/_api/web/lists")) + 1:]
    assert not any(s["method"] == "POST" and s["path"] != "/_api/contextinfo" for s in after)


@pytest.mark.parametrize("field", [
    {"TypeAsString": "UserMulti", "AllowMultipleValues": True}, {"InternalName": "ProbePerson0"},
    {"FieldTypeKind": 7}], ids=["multi", "renamed", "lookup"])
def test_setup_refuses_a_person_column_not_a_single_user_field(field: dict[str, Any]) -> None:
    rows, sent, _ = _run(swaps=FILLED, field=field)
    assert rows[PERSON_WRITE]["outcome"] == "FAIL"
    assert {QUESTION, PERSON} <= voided(rows)
    assert not any(s["method"] == "POST" and s["path"].endswith("/items") for s in sent)


def _touched(sent: list[dict[str, str]]) -> bool:
    """Whether a run sent any write: a list create, an item delete or a recycle."""
    return any(s["method"] == "POST" and (s["path"].endswith("/_api/web/lists")
                                          or "/recycle" in s["path"] or "/items(" in s["path"])
               for s in sent)


def test_setup_refuses_its_own_earlier_list_while_cleanup_is_off() -> None:
    rows, sent, _ = _run(swaps=FILLED, existing="owned")
    assert rows[LIST_FIXTURE]["outcome"] == "FAIL"
    assert "CLEANUP" in rows[LIST_FIXTURE]["evidence"]
    assert {PERSON_WRITE, QUESTION, PERSON} <= voided(rows)
    assert not _touched(sent)


@pytest.mark.parametrize("swaps", [FILLED, {**FILLED, **CLEANUP}], ids=["kept", "cleanup"])
def test_setup_never_touches_a_same_title_list_it_did_not_make(swaps: dict[str, str]) -> None:
    rows, sent, _ = _run(swaps=swaps, existing="foreign")
    assert rows[LIST_FIXTURE]["outcome"] == "FAIL"
    assert "ownership" in rows[LIST_FIXTURE]["evidence"]
    assert {PERSON_WRITE, QUESTION, PERSON} <= voided(rows)
    assert not _touched(sent)


def test_setup_with_cleanup_recycles_its_own_list_by_id_and_starts_again() -> None:
    rows, sent, output = _run(swaps={**FILLED, **CLEANUP}, existing="owned")
    recycled = [i for i, s in enumerate(sent) if s["path"].endswith("/recycle")]
    made = [i for i, s in enumerate(sent)
            if s["method"] == "POST" and s["path"].endswith("/_api/web/lists")]
    assert recycled and made and recycled[0] < made[0]
    assert "lists(guid'" in sent[recycled[0]]["path"]
    assert rows[QUESTION]["outcome"] == "MANUAL"
    assert ended_with_report(output)


@pytest.mark.parametrize("config", [{"refuse": "/ensureuser"}, {"ensuredId": None},
                                    {"ensuredId": "12"}], ids=["refused", "no-id", "text-id"])
def test_setup_writes_no_item_unless_ensureuser_answers_an_integer_id(
        config: dict[str, Any]) -> None:
    rows, sent, _ = _run(swaps=FILLED, **config)
    assert rows[PERSON_WRITE]["outcome"] == "FAIL"
    assert "ensureuser" in rows[PERSON_WRITE]["evidence"]
    assert {DISTINCT, QUESTION, PERSON} <= voided(rows)
    assert not any(s["method"] == "POST" and s["path"].endswith("/items") for s in sent)


def test_the_report_needs_item_1_to_name_the_account_typed_at_paste_time() -> None:
    rows, sent, output = _report(accountId=13)
    assert rows[PERSON_WRITE]["outcome"] == "FAIL"
    assert {DISTINCT, QUESTION, PERSON} <= voided(rows)
    assert not any("/ensureuser" in s["path"] for s in sent)  # the report run writes nothing
    assert LOGIN not in output


def test_the_report_refuses_a_same_title_list_it_did_not_make() -> None:
    rows, _, _ = _report(existing="foreign")
    assert rows[LIST_FIXTURE]["outcome"] == "FAIL"
    assert {PERSON_WRITE, DISTINCT, READ, QUESTION, PERSON} <= voided(rows)


def test_setup_reads_back_the_item_the_create_answered_and_needs_it_to_be_item_1() -> None:
    rows, sent, _ = _run(swaps=FILLED, itemId=3)
    assert any("/items(3)?" in s["path"] for s in sent)
    assert rows[PERSON_WRITE]["outcome"] == "FAIL"
    assert {QUESTION, PERSON} <= voided(rows)


@pytest.mark.parametrize(("editor_email", "head"), [
    (EMAIL, "EMAIL"), (LOGIN, "SIGN-IN NAME"), ("other@example.com", "NEITHER"),
    (None, "ABSENT")], ids=["email", "sign-in", "neither", "absent"])
def test_the_report_names_which_address_the_editor_carries(editor_email: str | None,
                                                           head: str) -> None:
    editor = {"LookupId": 12, "LookupValue": "Second Probe", "Email": editor_email}
    rows, _, output = _report(editor=editor)
    assert rows[QUESTION]["outcome"] == head
    assert EMAIL not in output and LOGIN not in output  # masked


def test_the_person_column_relation_is_recorded_separately() -> None:
    rows, _, _ = _report(person={"LookupId": 12, "Email": LOGIN})
    assert rows[PERSON]["outcome"] == "DIFFERS"
    rows, _, _ = _report()
    assert rows[PERSON]["outcome"] == "SAME"


def test_versions_by_one_user_that_disagree_read_as_mixed() -> None:
    older = {"LookupId": 12, "LookupValue": "Second Probe", "Email": LOGIN}
    rows, _, _ = _report(older=older)
    assert rows[QUESTION]["outcome"] == "MIXED"


def test_a_person_value_differing_only_in_case_is_its_own_outcome() -> None:
    rows, _, _ = _report(person={"LookupId": 12, "Email": EMAIL.upper()})
    assert rows[PERSON]["outcome"] == "SAME IGNORING CASE"


def test_a_person_value_without_email_leaves_the_relation_open() -> None:
    rows, _, _ = _report(person={"LookupId": 12, "LookupValue": "Second Probe"})
    assert rows[PERSON]["state"] == "open"
    assert "LookupId, LookupValue" in rows[PERSON]["evidence"]


def test_a_person_value_naming_another_user_leaves_the_relation_open() -> None:
    rows, _, _ = _report(person={"LookupId": 7, "Email": EMAIL})
    assert rows[PERSON]["state"] == "open"


def test_an_editor_without_email_leaves_the_relation_open() -> None:
    rows, _, _ = _report(editor={"LookupId": 12, "Email": None},
                         person={"LookupId": 12, "Email": None})
    assert rows[QUESTION]["outcome"] == "ABSENT"
    assert rows[PERSON]["outcome"] == "NOT ESTABLISHED"


def test_a_paged_versions_answer_leaves_the_observations_open() -> None:
    link = "https://example.sharepoint.com/sites/probe/_api/next"
    rows, sent, output = _report(nextLink=link)
    assert rows[QUESTION]["state"] == "open" and rows[PERSON]["state"] == "open"
    assert "continuation link" in rows[QUESTION]["evidence"]
    assert sum("/versions" in s["path"] for s in sent) == 1  # never followed
    assert link not in output


def test_a_version_without_a_usable_editor_id_leaves_the_observations_open() -> None:
    rows, _, _ = _report(older={"LookupValue": "Ada Probe", "Email": "ada@example.com"})
    assert rows[QUESTION]["state"] == "open" and rows[PERSON]["state"] == "open"
    assert "LookupId" in rows[QUESTION]["evidence"]


def test_no_version_by_the_second_account_leaves_the_question_open() -> None:
    rows, _, _ = _report(editor={"LookupId": 7, "Email": "ada@example.com"})
    assert rows[QUESTION]["state"] == "open"
    assert rows[PERSON]["state"] == "open"


def test_a_user_whose_sign_in_name_is_their_email_voids_the_question() -> None:
    same = {"Email": EMAIL, "UserPrincipalName": EMAIL.upper(),
            "LoginName": f"i:0#.f|membership|{EMAIL}"}
    rows, _, _ = _report(user=same)
    assert rows[DISTINCT]["outcome"] == "NOT ESTABLISHED"
    assert {QUESTION, PERSON} <= voided(rows)


def test_a_user_read_without_a_sign_in_name_names_the_keys_it_carried() -> None:
    rows, _, _ = _report(user={"Email": EMAIL, "LoginName": f"i:0#.f|membership|{LOGIN}"})
    assert rows[DISTINCT]["outcome"] == "NOT ESTABLISHED"
    assert "carried no Email or no UserPrincipalName (keys: Email)" in rows[DISTINCT]["evidence"]
    assert {QUESTION, PERSON} <= voided(rows)


def test_an_unanswered_user_read_voids_the_question() -> None:
    rows, _, _ = _report(refuse="/siteusers/getbyid(")
    assert "not authorised" in rows[DISTINCT]["evidence"]
    assert {QUESTION, PERSON} <= voided(rows)


def test_a_refused_versions_read_leaves_the_question_open() -> None:
    rows, _, _ = _report(refuse="/versions")
    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    assert QUESTION in voided(rows)
