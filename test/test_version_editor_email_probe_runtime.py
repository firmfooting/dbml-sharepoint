"""Execute version-editor-email-probe.js under node against a mock web.

Each case reaches one branch: the setup run, each report outcome, the
fixture that voids the question (a user whose sign-in name is their email),
a refused versions read, and a paste with the second account left blank.
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
FILLED = {"  const SECOND_ACCOUNT = '';": f"  const SECOND_ACCOUNT = '{LOGIN}';"}
REPORT = {"  const MODE = 'setup';": "  const MODE = 'report';"}

Run = tuple[dict[str, dict[str, str]], list[dict[str, str]], str]


def _run(gates: tuple[str, ...] = GATES, swaps: dict[str, str] | None = None,
         **config: Any) -> Run:
    # The probe has no per-run title token to pin, since its list title is fixed.
    return run_probe(EDITOR_MOCK, PROBE, gates, config, swaps=swaps, pin=False)


def _report(**config: Any) -> Run:
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


def test_a_refused_versions_read_leaves_the_question_open() -> None:
    rows, _, _ = _report(refuse="/versions")
    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    assert QUESTION in voided(rows)
