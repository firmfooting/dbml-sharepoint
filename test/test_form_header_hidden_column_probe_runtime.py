"""Execute form-header-hidden-column-probe.js under node against a mock web.

The probe builds the fixture and prints what a person must look at; the reading
itself is the person's, so every row it can settle is a fixture or a control, and
the check row stays awaiting a capture.
"""
from __future__ import annotations

import textwrap
from typing import Any

import pytest
from _node import NODE
from _paths import MANUAL
from _probe_runs import ended_with_report, run_probe, voided

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "form-header-hidden-column-probe.js"
CHECK = "text.form-fmt.header-hidden-column"
LIST = "text.form-fmt.fixture-hidden-list"
CONTROL = "text.form-fmt.control-column-hidden-on-forms"
FORMATTER = "text.form-fmt.fixture-header-formatter"
FIXTURES = (
    LIST,
    "text.form-fmt.fixture-hidden-columns",
    "text.form-fmt.fixture-hidden-item",
    CONTROL,
    FORMATTER,
)
GATES = ("CONFIRMED", "ALLOW_WRITES")
CLEANUP = {"  const CLEANUP = false;": "  const CLEANUP = true;"}

# The shapes are this mock's own; the probe never compares what a page shows with them.
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
    const LIST_ID = '00000000-0000-4000-8000-000000000abc';
    const OWNER = 'dbml-sharepoint form-header-hidden-column probe scratch list. Safe to delete.';
    let standing = CONFIG.existing === 'foreign' ? { Description: 'Not made by the probe.' }
      : CONFIG.existing ? { Description: OWNER } : null;
    const hidden = new Set();
    const flags = () => [...hidden].map((a) => a + '="FALSE"').join(' ');
    const schema = () => `<Field Name='HiddenResult' ${flags()}/>`;
    let stored = '';
    globalThis.fetch = async (url, init = {}) => {
      const path = String(url).replace(/^https:\/\/example\.sharepoint\.com\/sites\/probe/, '');
      const method = init.method || 'GET';
      SENT.push({ method, path });
      if (CONFIG.refuse && path.includes(CONFIG.refuse)) return answer(403, 'denied');
      if (path.endsWith('/_api/contextinfo')) return answer(200, { d: {
        GetContextWebInformation: { FormDigestValue: 'digest' } } });
      if (path.endsWith('/_api/web/lists') && method === 'POST') {
        standing = { Description: JSON.parse(init.body).Description };
        return answer(201, { d: { Id: LIST_ID } });
      }
      const head = [`getbytitle('dbml-probe-header-hidden-column')`, `lists(guid'${LIST_ID}')`]
        .find((h) => path.includes(h));
      if (!head) return answer(404, 'mock has no ' + path);
      const at = path.indexOf(head) + head.length;
      const rest = path.slice(at);
      if (!standing) return answer(404, { error: { message: { value: 'List does not exist.' } } });
      if (rest.startsWith('/recycle')) { standing = null; return answer(200, { d: {} }); }
      if (rest.startsWith('/items?')) return answer(200, { value: [] });
      if (rest.includes('/setshowin')) {
        const attr = rest.includes('editform') ? 'ShowInEditForm' : 'ShowInDisplayForm';
        if (!CONFIG.stayShown) hidden.add(attr);
        return answer(204, '');
      }
      if (rest.includes('/fields/getbyinternalnameortitle(')) {
        return answer(200, { SchemaXml: schema() });
      }
      if (rest.startsWith('/fields/createfieldasxml')) return answer(201, { d: {} });
      if (rest.startsWith('/fields?')) return answer(200, { value: [
        { InternalName: 'HiddenResult', TypeAsString: 'Choice' },
        { InternalName: 'Shown', TypeAsString: 'Text' }] });
      if (rest.startsWith('/items') && method === 'POST') {
        return answer(201, { d: { Id: CONFIG.itemId || 1 } });
      }
      const item = /^\/items\((\d+)\)/.exec(rest);
      if (item) return answer(200, { Id: Number(item[1]), HiddenResult: 'No', Shown: 'visible' });
      if (rest.startsWith('/contenttypes?')) {
        return answer(200, { value: [{ Name: 'Item', StringId: '0x01' }] });
      }
      if (rest.startsWith("/contenttypes('0x01')")) {
        if (method === 'POST') {
          if (CONFIG.refuseFormatter) return answer(403, 'denied');
          stored = JSON.parse(init.body).ClientFormCustomFormatter;
          return answer(204, '');
        }
        return answer(200, { ClientFormCustomFormatter: stored });
      }
      return answer(200, { Id: LIST_ID, Description: standing.Description,
        ListItemEntityTypeFullName: 'SP.Data.ProbeListItem' });
    };
""")

Run = tuple[dict[str, dict[str, str]], list[dict[str, str]], str]


def _run(gates: tuple[str, ...] = GATES, swaps: dict[str, str] | None = None,
         **config: Any) -> Run:
    # The probe's list title is fixed, so there is no per-run token to pin.
    return run_probe(_MOCK, PROBE, gates, config, swaps=swaps, pin=False)


def test_an_unconfirmed_probe_prints_its_plan_and_sends_nothing() -> None:
    rows, sent, output = _run(gates=())
    assert sent == [] and "Set CONFIRMED = true" in output
    assert rows[CHECK]["state"] == "open"


def test_a_healthy_run_settles_the_fixture_and_leaves_the_reading_to_a_person() -> None:
    rows, sent, output = _run()
    for row in FIXTURES:
        assert rows[row]["outcome"] == "PASS", (row, rows[row]["evidence"])
    assert rows[CHECK]["outcome"] == "MANUAL"
    assert rows[CHECK]["state"] == "awaiting-capture"
    assert "Open the item's Display form" in output and ended_with_report(output)
    # Every write after the create goes to the list by the Id the create answered.
    assert not any(s["method"] == "POST" and "getbytitle" in s["path"] for s in sent)


def test_a_column_still_shown_on_the_forms_voids_the_reading() -> None:
    rows, _sent, _output = _run(stayShown=True)
    assert rows[CONTROL]["outcome"] == "FAIL"
    assert CHECK in voided(rows)


def test_a_refused_formatter_write_voids_the_reading() -> None:
    rows, _sent, _output = _run(refuseFormatter=True)
    assert rows[FORMATTER]["outcome"] == "FAIL"
    assert CHECK in voided(rows)


def test_an_item_that_is_not_item_1_voids_the_reading() -> None:
    rows, _sent, _output = _run(itemId=2)
    assert rows["text.form-fmt.fixture-hidden-item"]["outcome"] == "FAIL"
    assert CHECK in voided(rows)


def test_a_same_title_list_it_did_not_make_is_left_alone() -> None:
    rows, sent, _output = _run(swaps=CLEANUP, existing="foreign")
    assert rows[LIST]["outcome"] == "FAIL" and CHECK in voided(rows)
    assert not any(s["method"] == "POST" for s in sent if not s["path"].endswith("/contextinfo"))


def test_its_own_earlier_list_is_refused_while_cleanup_is_off() -> None:
    rows, _sent, _output = _run(existing="owned")
    assert rows[LIST]["outcome"] == "FAIL" and "CLEANUP" in rows[LIST]["evidence"]


def test_cleanup_recycles_its_own_earlier_list_by_id_first() -> None:
    rows, sent, _output = _run(swaps=CLEANUP, existing="owned")
    recycled = [i for i, s in enumerate(sent) if s["path"].endswith("/recycle")]
    made = [i for i, s in enumerate(sent)
            if s["method"] == "POST" and s["path"].endswith("/_api/web/lists")]
    assert recycled and made and recycled[0] < made[0]
    assert "lists(guid'" in sent[recycled[0]]["path"]
    assert rows[CHECK]["outcome"] == "MANUAL"
