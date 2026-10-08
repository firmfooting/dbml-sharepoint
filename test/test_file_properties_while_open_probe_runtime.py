"""Execute file-properties-while-open-probe.js under node against a mock web.

The probe runs twice by hand: STATE 'open' once a second account has the workbook open,
and STATE 'closed' after. Each write is recorded as answered, never compared with an
expected outcome.
"""
from __future__ import annotations

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
OPEN_WEB = {**URL, "  const OPENED_IN = '';": "  const OPENED_IN = 'web';"}
OPEN_DESKTOP = {**URL, "  const OPENED_IN = '';": "  const OPENED_IN = 'desktop';"}
CLOSED = {**OPEN_WEB, "  const STATE = 'open';": "  const STATE = 'closed';"}

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
    globalThis.fetch = async (url, init = {}) => {
      const path = String(url).replace(/^https:\/\/example\.sharepoint\.com\/sites\/probe/, '');
      const method = init.method || 'GET';
      SENT.push({ method, path, headers: init.headers || {} });
      if (path.endsWith('/_api/contextinfo')) return answer(200, { d: {
        GetContextWebInformation: { FormDigestValue: 'digest' } } });
      if (!path.includes('GetFileByServerRelativePath')) return answer(404, 'mock has no ' + path);
      if (CONFIG.missing) return answer(404, { error: { message: { value: 'File Not Found.' } } });
      if (method === 'POST') {
        if (CONFIG.refuse) return answer(CONFIG.refuse, 'locked for shared use');
        note = JSON.parse(init.body)[CONFIG.noteName || 'ProbeNote'];
        return answer(204, '');
      }
      return answer(200, { Id: CONFIG.itemId === undefined ? 3 : CONFIG.itemId,
        ProbeNote: note, ListItemEntityTypeFullName: 'SP.Data.LibItem' });
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


PHONE = {**URL, "  const OPENED_IN = '';": "  const OPENED_IN = 'phone';"}


@pytest.mark.parametrize("swaps", [URL, PHONE], ids=["unset", "unknown"])
def test_an_opened_in_that_is_not_web_or_desktop_stops_before_any_request(
        swaps: dict[str, str]) -> None:
    _, sent, output = _run(swaps)
    assert sent == [] and "OPENED_IN" in output


def test_a_refused_merge_is_recorded_with_its_status_not_failed() -> None:
    rows, sent, output = _run(OPEN_WEB, refuse=423)
    assert rows[WEB]["outcome"] == "OBSERVED" and rows[WEB]["state"] == "settled"
    assert "423" in rows[WEB]["evidence"] and "locked for shared use" in rows[WEB]["evidence"]
    assert rows[CONTROL]["state"] == "awaiting-capture"
    assert len(_writes(sent)) == 1 and ended_with_report(output)


def test_an_accepted_merge_records_the_value_read_back_under_the_desktop_check() -> None:
    rows, sent, _ = _run(OPEN_DESKTOP)
    assert rows[DESKTOP]["outcome"] == "OBSERVED"
    assert "read back:" in rows[DESKTOP]["evidence"]
    assert rows[WEB]["state"] == "open"
    [write] = _writes(sent)
    assert write["headers"]["X-HTTP-Method"] == "MERGE" and write["headers"]["IF-MATCH"] == "*"
    assert "p%20%26%20q.xlsx" in write["path"]


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
