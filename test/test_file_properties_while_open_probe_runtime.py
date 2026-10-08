"""Execute file-properties-while-open-probe.js under node against a mock web.

The probe runs twice by hand: STATE 'open' once a second account has the workbook open,
and STATE 'closed' after. Each write is recorded as answered, never compared with an
expected outcome.
"""
from __future__ import annotations

import hashlib
import json
import re
import textwrap
from typing import Any

import pytest
from _node import NODE
from _paths import MANUAL
from _probe_runs import ended_with_report, run_probe, voided

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "file-properties-while-open-probe.js"
WEB = "library.file.properties-update-while-open-web"
DESKTOP = "library.file.properties-update-while-open-desktop"
FIXTURE = "library.file.fixture-open-workbook"
CONTROL = "library.file.control-properties-update-closed"
GATES = ("CONFIRMED", "ALLOW_WRITES")
URL = {"  const WORKBOOK_URL = '';": "  const WORKBOOK_URL = '/sites/probe/Lib/p & q.xlsx';"}
ATTEST = {**URL, "  const SECOND_ACCOUNT_HAS_IT_OPEN = false;":
          "  const SECOND_ACCOUNT_HAS_IT_OPEN = true;"}
OPEN_WEB = {**ATTEST, "  const OPENED_IN = '';": "  const OPENED_IN = 'web';"}
OPEN_DESKTOP = {**ATTEST, "  const OPENED_IN = '';": "  const OPENED_IN = 'desktop';"}
CLOSED_ONLY = {"  const STATE = 'open';": "  const STATE = 'closed';",
               "  const SECOND_ACCOUNT_HAS_IT_OPEN = true;":
               "  const SECOND_ACCOUNT_HAS_IT_OPEN = false;"}
CLOSED_IT = {"  const SECOND_ACCOUNT_HAS_CLOSED_IT = false;":
             "  const SECOND_ACCOUNT_HAS_CLOSED_IT = true;"}
CLOSED = {**OPEN_WEB, **CLOSED_ONLY, **CLOSED_IT}

# The shapes are this mock's own; the probe records what a site answers and never compares it.
_MOCK = textwrap.dedent(r"""
    const CONFIG = __CONFIG__;
    globalThis.window = { _spPageContextInfo: {
      webAbsoluteUrl: 'https://example.sharepoint.com/sites/probe' } };
    const SENT = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
    const answer = (status, payload) => {
      const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
      return { ok: status >= 200 && status < 300, status, headers: { get: () => null },
        text: async () => text, json: async () => JSON.parse(text) };
    };
    let note = null;
    let wrote = false;
    globalThis.fetch = async (url, init = {}) => {
      const path = String(url).replace(/^https:\/\/example\.sharepoint\.com\/sites\/probe/, '');
      const method = init.method || 'GET';
      SENT.push({ method, path, headers: init.headers || {}, body: init.body });
      if (path.endsWith('/_api/contextinfo') && CONFIG.digestThrows) throw new Error('no digest');
      if (path.endsWith('/_api/contextinfo')) return answer(200, { d: {
        GetContextWebInformation: { FormDigestValue: 'digest' } } });
      if (!path.includes('GetFileByServerRelativePath')) return answer(404, 'mock has no ' + path);
      if (CONFIG.missing) return answer(404, { error: { message: { value: 'File Not Found.' } } });
      if (method === 'POST') {
        wrote = true;
        if (CONFIG.commitThenThrow) {
          note = JSON.parse(init.body).ProbeNotes;
          throw new Error('connection lost');
        }
        if (CONFIG.refuse && CONFIG.bare) return answer(CONFIG.refuse, 'internal error');
        if (CONFIG.refuse) return answer(CONFIG.refuse, { error: {
          code: '-2130575305, Microsoft.SharePoint.SPException',
          message: { value: 'locked for shared use' } } });
        note = JSON.parse(init.body)[CONFIG.noteName || 'ProbeNotes'];
        return answer(204, '');
      }
      if (path.includes('/ParentList')) {
        return CONFIG.noParent ? answer(404, 'no parent list')
          : answer(200, { ListItemEntityTypeFullName: 'SP.Data.LibItem' });
      }
      if (path.includes('/LockedByUser')) {
        if (CONFIG.lockEmpty) return answer(200, '');
        return answer(200, CONFIG.locked ? { Id: 9 } : { Id: null });
      }
      if (wrote && CONFIG.noNoteRead) return answer(200, { Id: 3 });
      if (wrote && CONFIG.emptyRead) return answer(200, '');
      if (wrote && CONFIG.readStatus) return answer(CONFIG.readStatus, 'slow down');
      if (wrote && CONFIG.readFailsAfterWrite) throw new Error('read after write failed');
      const staleNote = CONFIG.staleRead && wrote ? null : note;
      return answer(200, { Id: CONFIG.itemId === undefined ? 3 : CONFIG.itemId,
        ProbeNotes: staleNote });
    };
""")


Run = tuple[dict[str, dict[str, str]], list[dict[str, Any]], str]


def _run(swaps: dict[str, str] | None, gates: tuple[str, ...] = GATES, **config: Any) -> Run:
    return run_probe(_MOCK, PROBE, gates, config, swaps=swaps, pin=False)


def _writes(sent: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in sent if s["method"] == "POST" and "GetFileByServerRelativePath" in s["path"]]


def test_an_unconfirmed_paste_prints_its_plan_and_sends_nothing() -> None:
    _, sent, output = _run(None, gates=())
    assert sent == [] and "WORKBOOK_URL" in output


PHONE = {**ATTEST, "  const OPENED_IN = '';": "  const OPENED_IN = 'phone';"}


@pytest.mark.parametrize("swaps", [ATTEST, PHONE], ids=["unset", "unknown"])
def test_an_opened_in_that_is_not_web_or_desktop_stops_before_any_request(
        swaps: dict[str, str]) -> None:
    _, sent, output = _run(swaps)
    assert sent == [] and "OPENED_IN" in output


def test_a_refused_merge_is_recorded_with_its_status_not_failed() -> None:
    rows, sent, output = _run(OPEN_WEB, refuse=423)
    assert rows[WEB]["outcome"] == "OBSERVED" and rows[WEB]["state"] == "open"
    assert "error.code: -2130575305" in rows[WEB]["evidence"]
    assert "before: LockedByUser read: HTTP 200" in rows[WEB]["evidence"]
    assert "423" in rows[WEB]["evidence"] and "locked for shared use" in rows[WEB]["evidence"]
    assert rows[CONTROL]["state"] == "open"
    assert len(_writes(sent)) == 1 and ended_with_report(output)


def test_an_accepted_merge_records_the_value_read_back_under_the_desktop_check() -> None:
    rows, sent, _ = _run(OPEN_DESKTOP)
    assert rows[DESKTOP]["outcome"] == "OBSERVED"
    assert "read back:" in rows[DESKTOP]["evidence"]
    assert rows[WEB]["state"] == "open"
    [write] = _writes(sent)
    assert write["headers"]["X-HTTP-Method"] == "MERGE" and write["headers"]["IF-MATCH"] == "*"
    assert "p%20%26%20q.xlsx" in write["path"]
    assert json.loads(write["body"])["__metadata"] == {"type": "SP.Data.LibItem"}


def test_the_closed_paste_records_the_control_and_leaves_the_checks_alone() -> None:
    rows, _, _ = _run(CLOSED)
    assert rows[CONTROL]["outcome"] == "PASS" and "read back:" in rows[CONTROL]["evidence"]
    assert rows[WEB]["state"] == "open"


def test_a_closed_paste_whose_merge_is_refused_fails_the_control() -> None:
    rows, _, _ = _run(CLOSED, refuse=423)
    assert rows[CONTROL]["outcome"] == "FAIL" and "423" in rows[CONTROL]["evidence"]


@pytest.mark.parametrize("config", [{"missing": True}, {"itemId": None}],
                         ids=["not-found", "no-item-id"])
def test_a_workbook_that_cannot_be_read_voids_the_control_and_the_check(
        config: dict[str, Any]) -> None:
    rows, sent, _ = _run(OPEN_WEB, **config)
    assert rows[FIXTURE]["outcome"] == "FAIL"
    assert {CONTROL, WEB} <= voided(rows)
    assert _writes(sent) == []


def test_an_open_paste_without_the_attestation_sends_nothing() -> None:
    swaps = {**URL, "  const OPENED_IN = '';": "  const OPENED_IN = 'web';"}
    _, sent, output = _run(swaps)
    assert sent == [] and "SECOND_ACCOUNT_HAS_IT_OPEN" in output


def test_a_request_that_throws_still_prints_the_report() -> None:
    rows, _, output = _run(OPEN_WEB, digestThrows=True)
    assert rows[WEB]["state"] == "open" and "the probe stopped" in output
    assert ended_with_report(output)


def test_the_item_type_is_read_from_the_containing_list() -> None:
    _, sent, _ = _run(OPEN_WEB)
    assert any("/ListItemAllFields/ParentList" in s["path"] for s in sent)
    assert not any("ListItemEntityTypeFullName" in s["path"] and "ParentList" not in s["path"]
                   for s in sent)


def test_a_list_that_cannot_be_read_voids_both_checks_and_writes_nothing() -> None:
    rows, sent, _ = _run(OPEN_WEB, noParent=True)
    assert rows[FIXTURE]["outcome"] == "FAIL"
    assert {CONTROL, WEB, DESKTOP} <= voided(rows)
    assert _writes(sent) == []


def test_a_closed_paste_needs_the_closed_attestation() -> None:
    swaps = {**OPEN_WEB, **CLOSED_ONLY}
    _, sent, output = _run(swaps)
    assert sent == [] and "SECOND_ACCOUNT_HAS_CLOSED_IT" in output


def test_a_closed_paste_that_also_says_it_is_open_sends_nothing() -> None:
    swaps = {**OPEN_WEB, **CLOSED_IT, "  const STATE = 'open';": "  const STATE = 'closed';"}
    _, sent, _ = _run(swaps)
    assert sent == []


def test_a_failed_control_voids_both_checks() -> None:
    rows, _, _ = _run(CLOSED, refuse=400)
    assert rows[CONTROL]["outcome"] == "FAIL"
    assert {WEB, DESKTOP} <= voided(rows)


def test_the_control_verdict_and_its_evidence_come_from_one_read() -> None:
    rows, sent, _ = _run(CLOSED, staleRead=True)
    assert rows[CONTROL]["outcome"] == "FAIL" and "read back: null" in rows[CONTROL]["evidence"]
    reads = [s for s in sent if s["method"] == "GET" and s["path"].endswith("ProbeNotes")]
    assert len(reads) == 2  # the fixture read and the one read after the write


@pytest.mark.parametrize("status", [401, 403, 408, 429, 502, 503, 504])
def test_a_status_that_says_nothing_about_the_update_is_not_established(status: int) -> None:
    rows, _, _ = _run(OPEN_WEB, refuse=status)
    assert rows[WEB]["outcome"] == "NOT ESTABLISHED" and rows[WEB]["state"] == "open"
    assert str(status) in rows[WEB]["evidence"]
    rows, _, _ = _run(CLOSED, refuse=status)
    assert rows[CONTROL]["outcome"] == "NOT ESTABLISHED" and rows[CONTROL]["state"] == "open"


def test_the_merge_answer_survives_a_failing_read_back() -> None:
    rows, _, output = _run(OPEN_WEB, refuse=423, readFailsAfterWrite=True)
    assert "423" in rows[WEB]["evidence"] and "read back threw" in rows[WEB]["evidence"]
    assert ended_with_report(output)


def test_a_refused_update_is_not_labelled_as_written() -> None:
    rows, _, _ = _run(OPEN_WEB, refuse=423)
    assert "requested" in rows[WEB]["evidence"] and "wrote" not in rows[WEB]["evidence"]


@pytest.mark.parametrize("config", [{"readFailsAfterWrite": True}, {"readStatus": 429},
                                    {"readStatus": 404}, {"emptyRead": True}, {"noNoteRead": True}],
                         ids=["throws", "429", "404", "empty", "no-note"])
def test_a_control_readback_that_did_not_answer_is_not_established_and_voids_nothing(
        config: dict[str, Any]) -> None:
    rows, _, _ = _run(CLOSED, **config)
    assert rows[CONTROL]["outcome"] == "NOT ESTABLISHED" and rows[CONTROL]["state"] == "open"
    assert "HTTP 204" in rows[CONTROL]["evidence"]
    assert not voided(rows)


@pytest.mark.parametrize("swaps", [OPEN_WEB, CLOSED], ids=["open", "closed"])
def test_a_merge_that_rejects_is_read_back_for_the_token(swaps: dict[str, str]) -> None:
    rows, _, output = _run(swaps, commitThenThrow=True)
    row = rows[CONTROL if swaps is CLOSED else WEB]
    assert row["outcome"] == "NOT ESTABLISHED" and "the write is uncertain" in row["evidence"]
    assert "connection lost" in row["evidence"] and "token" in row["evidence"]
    assert ended_with_report(output)


def test_the_revision_is_derived_from_the_probe_text() -> None:
    js = PROBE.read_text(encoding="utf-8")
    stamped = re.search(r"REVISION: ([0-9a-f]{8})", js)
    assert stamped is not None
    neutral = js.replace(stamped.group(1), "00000000")
    # Re-stamp with this digest whenever the probe changes.
    assert stamped.group(1) == hashlib.sha256(neutral.encode()).hexdigest()[:8]
    _, _, output = _run(OPEN_WEB)
    assert f"probe revision {stamped.group(1)}." in output


@pytest.mark.parametrize("swaps", [OPEN_WEB, CLOSED], ids=["open", "closed"])
@pytest.mark.parametrize("status", [502, 504])
def test_a_gateway_failure_still_reads_the_token_back(swaps: dict[str, str], status: int) -> None:
    rows, sent, _ = _run(swaps, refuse=status)
    row = rows[CONTROL if swaps is CLOSED else WEB]
    assert row["outcome"] == "NOT ESTABLISHED" and "the write is uncertain" in row["evidence"]
    assert "token" in row["evidence"]
    assert sent[-1]["method"] == "GET"


@pytest.mark.parametrize("swaps", [OPEN_WEB, CLOSED], ids=["open", "closed"])
def test_a_bare_500_is_not_a_finding_but_a_500_with_a_sharepoint_error_is(
        swaps: dict[str, str]) -> None:
    key = CONTROL if swaps is CLOSED else WEB
    rows, _, _ = _run(swaps, refuse=500, bare=True)
    assert rows[key]["outcome"] == "NOT ESTABLISHED"
    assert "no SharePoint error payload" in rows[key]["evidence"]
    assert not voided(rows)
    rows, _, _ = _run(swaps, refuse=500)
    assert rows[key]["outcome"] in {"OBSERVED", "FAIL"}


def test_a_lock_read_with_no_payload_or_a_null_id_names_no_user() -> None:
    rows, _, _ = _run(OPEN_WEB, refuse=423, lockEmpty=True)
    assert "no readable payload" in rows[WEB]["evidence"]
    assert "a user is named" not in rows[WEB]["evidence"]
    rows, _, _ = _run(OPEN_WEB, refuse=423)
    assert "the payload carried no integer Id" in rows[WEB]["evidence"]
    rows, _, _ = _run(OPEN_WEB, refuse=423, locked=True)
    assert "a user is named" in rows[WEB]["evidence"]


def test_every_report_names_its_target() -> None:
    for swaps in (OPEN_WEB, CLOSED):
        _, _, output = _run(swaps)
        assert "target: https://example.sharepoint.com/sites/probe/Lib/p" in output
        assert "/sites/probe/sites/probe" not in output.split("target:")[1].splitlines()[0]


@pytest.mark.parametrize("config", [{"readFailsAfterWrite": True}, {"readStatus": 429},
                                    {"emptyRead": True}, {"noNoteRead": True}],
                         ids=["throws", "429", "empty", "no-note"])
def test_an_accepted_open_update_with_an_unreadable_readback_is_not_a_finding(
        config: dict[str, Any]) -> None:
    rows, _, _ = _run(OPEN_WEB, **config)
    assert rows[WEB]["outcome"] == "NOT ESTABLISHED" and "HTTP 204" in rows[WEB]["evidence"]


def test_the_note_column_is_the_one_the_catalogue_prerequisite_names() -> None:
    # Core holds no fixture schema, so the catalogue prerequisite is what grounds the column.
    note = re.search(r"const NOTE = '(\w+)'", PROBE.read_text(encoding="utf-8"))
    assert note is not None
    catalogue = (MANUAL / "probe-catalog.json").read_text(encoding="utf-8")
    assert f"a library with a text column {note.group(1)}\"" in catalogue
