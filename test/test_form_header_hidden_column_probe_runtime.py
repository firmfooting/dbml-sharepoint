"""Execute form-header-hidden-column-probe.js under node against a mock web.

The probe builds the fixture and prints what a person must look at; the reading
itself is the person's, so every row it can settle is a fixture or a control, and
the check row stays awaiting a capture.
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

from dbml_sharepoint.analysis.form_rendering import compose_visibility

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "form-header-hidden-column-probe.js"
EDIT = "form.edit-form.header-hidden-column"
DISPLAY = "form.display-form.header-hidden-column"
BASE = ("form.edit-form.footer-baseline-renders", "form.display-form.footer-baseline-renders")
BODY = ("form.edit-form.body-hides-column", "form.display-form.body-hides-column")
OBSERVED_BASELINE = BASE + BODY
TOKEN = ("form.edit-form.header-choice-token-renders",
         "form.display-form.header-choice-token-renders")
TARGET = (EDIT, DISPLAY)
LINKS = "text.form-fmt.control-columns-in-content-type"
LIST = "text.form-fmt.fixture-hidden-list"
CONTROL = "text.form-fmt.control-column-hidden-on-forms"
FORMATTER = "text.form-fmt.fixture-header-formatter"
FOOTER_FIXTURE = "text.form-fmt.fixture-footer-baseline"
CONTROL_FIXTURE = "text.form-fmt.fixture-control-header"
FIXTURES = (
    LIST,
    "text.form-fmt.fixture-hidden-columns",
    "text.form-fmt.fixture-hidden-item",
    CONTROL,
    LINKS,
)
GATES = ("CONFIRMED", "ALLOW_WRITES")
CONTROL_MODE = {"  const MODE = 'baseline';": "  const MODE = 'control';"}
HEADER = {"  const MODE = 'baseline';": "  const MODE = 'header';"}
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
    // `prior` is the state a baseline run leaves behind, for a header run to find.
    let made = !!CONFIG.prior;
    let formula = CONFIG.prior ? CONFIG.hide : '';
    let stored = CONFIG.prior ? CONFIG.stored : '';
    if (CONFIG.prior) standing = { Description: OWNER };
    globalThis.fetch = async (url, init = {}) => {
      const path = String(url).replace(/^https:\/\/example\.sharepoint\.com\/sites\/probe/, '');
      const method = init.method || 'GET';
      SENT.push({ method, path, body: typeof init.body === 'string' ? init.body : '' });
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
      if (rest.startsWith('/items?')) {
        return answer(200, { value: made ? [{ Id: CONFIG.itemId || 1 }] : [] });
      }
      if (rest.includes('/fields/getbyinternalnameortitle(')) {
        if (method === 'POST') {
          if (!CONFIG.stayShown) formula = JSON.parse(init.body).ClientValidationFormula;
          return answer(204, '');
        }
        return answer(200, { ClientValidationFormula: formula });
      }
      if (rest.startsWith('/fields/createfieldasxml')) return answer(201, { d: {} });
      if (rest.startsWith('/fields?')) return answer(200, { value: [
        { InternalName: 'HiddenResult', TypeAsString: 'Choice', ClientValidationFormula: formula },
        { InternalName: 'ShownResult', TypeAsString: 'Choice',
          ...(CONFIG.omitShownFormula ? {}
            : { ClientValidationFormula: CONFIG.shownFormula || '' }) }] });
      if (rest.startsWith('/items') && method === 'POST') {
        made = true;
        return answer(201, { d: { Id: CONFIG.itemId || 1 } });
      }
      const item = /^\/items\((\d+)\)/.exec(rest);
      if (item) {
        return answer(200, { Id: CONFIG.readId || Number(item[1]),
          HiddenResult: 'No', ShownResult: 'Yes' });
      }
      if (rest.startsWith('/contenttypes?')) {
        return answer(200, { value: [{ Name: 'Folder', StringId: '0x0120' },
          { Name: CONFIG.typeName || 'Item', StringId: '0x01' }] });
      }
      if (rest.includes('/fieldlinks')) {
        return answer(200, { value: CONFIG.links || [{ Name: 'HiddenResult', Hidden: false },
          { Name: 'ShownResult', Hidden: false }] });
      }
      if (rest.startsWith("/contenttypes('0x01')")) {
        if (method === 'POST') {
          if (CONFIG.refuseFormatter) return answer(403, 'denied');
          stored = JSON.parse(init.body).ClientFormCustomFormatter;
          // `ambiguous` commits the write and answers as if it failed.
          return CONFIG.ambiguous ? answer(500, 'unknown') : answer(204, '');
        }
        return answer(200, { ClientFormCustomFormatter: stored });
      }
      return answer(200, { Id: LIST_ID, Description: standing.Description,
        RootFolder: { ServerRelativeUrl: CONFIG.rootUrl
          || '/sites/probe/Lists/occupied-elsewhere' },
        ListItemEntityTypeFullName: 'SP.Data.ProbeListItem' });
    };
""")

Run = tuple[dict[str, dict[str, str]], list[dict[str, str]], str]
HIDE = "=if([$ID] == '', 'true', 'false')"
FOOTER_ONLY = '{"footerJSONFormatter":{"elmType":"div","txtContent":"probe-baseline-footer"}}'
CONTROL_FORMATTER = json.dumps({
    "headerJSONFormatter": {"elmType": "div", "children": [
        {"elmType": "div", "txtContent": "='visible-choice: ' + [$ShownResult]"}]},
    "footerJSONFormatter": {"elmType": "div", "txtContent": "probe-baseline-footer"}},
    separators=(",", ":"))
PRIOR = {"prior": True, "hide": HIDE, "stored": FOOTER_ONLY}
PREVIOUS = "text.form-fmt.fixture-previous-phase-formatter"


def _run(gates: tuple[str, ...] = GATES, swaps: dict[str, str] | None = None,
         **config: Any) -> Run:
    # The probe's list title is fixed, so there is no per-run token to pin.
    return run_probe(_MOCK, PROBE, gates, config, swaps=swaps, pin=False)


def _header(**config: Any) -> Run:
    """The last paste, against the state the earlier ones leave."""
    config = {**PRIOR, "stored": CONTROL_FORMATTER, **config}
    return run_probe(_MOCK, PROBE, GATES, config, swaps=HEADER, pin=False)


def _control(**config: Any) -> Run:
    """The middle paste."""
    return run_probe(_MOCK, PROBE, GATES, {**PRIOR, **config}, swaps=CONTROL_MODE, pin=False)


def _writes(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [s for s in sent if s["method"] == "POST" and not s["path"].endswith("/contextinfo")]


def test_an_unconfirmed_probe_prints_its_plan_and_sends_nothing() -> None:
    rows, sent, output = _run(gates=())
    assert sent == [] and "Set CONFIRMED = true" in output
    assert rows[BASE[0]]["state"] == "open"


def test_a_healthy_baseline_run_writes_the_footer_alone_and_awaits_a_person() -> None:
    rows, sent, output = _run()
    for row in (*FIXTURES, FOOTER_FIXTURE):
        assert rows[row]["outcome"] == "PASS", (row, rows[row]["evidence"])
    for row in OBSERVED_BASELINE:
        assert rows[row]["outcome"] == "MANUAL" and rows[row]["state"] == "awaiting-capture"
    assert not set(TOKEN + TARGET) & set(rows)
    formatter = next(s for s in sent if "ClientFormCustomFormatter" in s["body"])
    assert "headerJSONFormatter" not in formatter["body"]
    assert "footerJSONFormatter" in formatter["body"]
    assert "Open the item's Edit form" in rows[BASE[0]]["evidence"] and ended_with_report(output)
    # Every write after the create goes to the list by the Id the create answered.
    assert not any(s["method"] == "POST" and "getbytitle" in s["path"] for s in sent)


def test_a_control_run_adds_only_the_visible_choice_line() -> None:
    rows, sent, output = _control()
    for row in (*FIXTURES, CONTROL_FIXTURE):
        assert rows[row]["outcome"] == "PASS", (row, rows[row]["evidence"])
    for row in TOKEN:
        assert rows[row]["outcome"] == "MANUAL" and rows[row]["state"] == "awaiting-capture"
    assert not set(BASE + BODY + TARGET) & set(rows)
    [write] = _writes(sent)
    assert "visible-choice: " in write["body"] and "hidden-column" not in write["body"]
    assert "footerJSONFormatter" in write["body"] and ended_with_report(output)


def test_a_header_run_adds_the_hidden_line_and_writes_nothing_else() -> None:
    rows, sent, output = _header()
    for row in (*FIXTURES, FORMATTER):
        assert rows[row]["outcome"] == "PASS", (row, rows[row]["evidence"])
    for row in TARGET:
        assert rows[row]["outcome"] == "MANUAL" and rows[row]["state"] == "awaiting-capture"
    assert not set(BASE + BODY + TOKEN) & set(rows)
    [write] = _writes(sent)
    assert "hidden-column: " in write["body"] and "visible-choice: " in write["body"]
    assert "contenttypes('0x01')" in write["path"] and ended_with_report(output)


def test_each_reading_is_its_own_finding_and_body_visibility_voids_only_the_target() -> None:
    rows, _sent, _output = _run()
    assert "HiddenResult is absent from the Edit form body" in rows[BODY[0]]["evidence"]
    assert "probe-baseline-footer" in rows[BASE[0]]["evidence"]
    assert "VOID" not in rows[BASE[0]]["evidence"] and "VOID" not in rows[BODY[0]]["evidence"]
    rows, _sent, _output = _control()
    assert "observed failure of the visible Choice token" in rows[TOKEN[0]]["evidence"]
    assert "VOID" not in rows[TOKEN[0]]["evidence"]
    rows, _sent, _output = _header()
    assert "VOID it where the body row did not show the column hidden" in rows[EDIT]["evidence"]
    assert "suppression by the hidden token" in rows[EDIT]["evidence"]


def test_joined_text_is_an_expression_and_the_footer_a_plain_literal() -> None:
    js = PROBE.read_text(encoding="utf-8")
    assert "txtContent: `='visible-choice: ' + [$${SHOWN}]`" in js
    assert "txtContent: `='hidden-column: ' + [$${HIDDEN}]`" in js
    assert "txtContent: 'probe-baseline-footer'" in js
    assert "attributes: {" not in js


def test_a_header_run_without_a_baseline_list_refuses_and_writes_nothing() -> None:
    rows, sent, _output = _run(swaps=HEADER)
    assert rows[LIST]["outcome"] == "FAIL" and set(TARGET) <= voided(rows)
    assert not _writes(sent)


def test_a_header_run_never_touches_a_same_title_list_it_did_not_make() -> None:
    rows, sent, _output = _run(swaps=HEADER, existing="foreign")
    assert rows[LIST]["outcome"] == "FAIL" and set(TARGET) <= voided(rows)
    assert not _writes(sent)


def test_a_header_run_with_more_than_one_item_voids_the_reading() -> None:
    rows, _sent, _output = _header(itemId=2, readId=9)
    assert rows["text.form-fmt.fixture-hidden-item"]["outcome"] == "FAIL"
    assert set(TARGET) <= voided(rows)


def test_a_committed_write_that_answers_an_error_stands_on_an_exact_readback() -> None:
    rows, _sent, _output = _header(ambiguous=True)
    assert rows[FORMATTER]["outcome"] == "PASS"
    assert rows[EDIT]["outcome"] == "MANUAL"


def test_a_refused_formatter_write_voids_the_reading() -> None:
    rows, _sent, _output = _header(refuseFormatter=True)
    assert rows[FORMATTER]["outcome"] == "FAIL"
    assert set(TARGET) <= voided(rows)
    rows, _sent, _output = _run(refuseFormatter=True)
    assert rows[FOOTER_FIXTURE]["outcome"] == "FAIL" and set(BASE) <= voided(rows)


def test_a_hiding_that_did_not_read_back_voids_only_the_rows_resting_on_it() -> None:
    rows, _sent, _output = _run(stayShown=True)
    assert rows[CONTROL]["outcome"] == "FAIL"
    assert set(BODY) <= voided(rows)
    assert not set(BASE) & voided(rows)
    rows, _sent, _output = _header(hide="")
    assert set(TARGET) <= voided(rows)


def test_the_item_need_not_be_item_1() -> None:
    rows, _sent, _output = _run(itemId=2)
    assert rows["text.form-fmt.fixture-hidden-item"]["outcome"] == "PASS"
    assert "ID=2" in rows[BASE[0]]["evidence"] and "ID=2" in rows[BASE[1]]["evidence"]


def test_an_item_read_that_answers_another_id_voids_the_reading() -> None:
    rows, _sent, _output = _run(readId=9)
    assert rows["text.form-fmt.fixture-hidden-item"]["outcome"] == "FAIL"
    assert set(BASE) <= voided(rows)


def test_the_content_type_is_found_by_id_prefix_not_by_its_name() -> None:
    rows, sent, _output = _run(typeName="Eintrag")
    assert rows[FOOTER_FIXTURE]["outcome"] == "PASS"
    assert any("contenttypes('0x01')" in s["path"] for s in sent)
    assert not any("0x0120" in s["path"] and s["method"] == "POST" for s in sent)


def test_the_hiding_is_the_formula_the_generator_emits_and_never_a_show_in_form_setter() -> None:
    expected = compose_visibility(new=True, existing=False, when=None, types={})
    assert expected == HIDE
    js = PROBE.read_text(encoding="utf-8")
    assert f'const HIDE_ON_EXISTING = "{expected}";' in js
    _rows, sent, _output = _run()
    assert not any("setshowin" in s["path"].lower() for s in sent)


def test_the_form_links_come_from_the_lists_own_folder_url() -> None:
    rows, _sent, _output = _run(rootUrl="/sites/probe/Lists/Renamed%20Folder")
    assert "https://example.sharepoint.com/sites/probe/Lists/Renamed%20Folder/EditForm.aspx?ID=1" \
        in rows[BASE[0]]["evidence"]
    assert "/DispForm.aspx?ID=1" in rows[BASE[1]]["evidence"]
    assert "dbml-probe-header-hidden-column/" not in rows[BASE[0]]["evidence"]


def test_a_visible_control_carrying_a_formula_voids_the_reading() -> None:
    rows, _sent, _output = _run(shownFormula="=if(false, 'true', 'false')")
    assert rows[CONTROL]["outcome"] == "FAIL"
    assert set(BODY) <= voided(rows)


def test_a_control_row_that_omits_the_formula_property_proves_nothing() -> None:
    rows, _sent, _output = _run(omitShownFormula=True)
    assert rows[CONTROL]["outcome"] == "FAIL"
    assert set(BODY) <= voided(rows)


@pytest.mark.parametrize("links", [
    [{"Name": "HiddenResult", "Hidden": False}],
    [{"Name": "HiddenResult", "Hidden": False}, {"Name": "ShownResult", "Hidden": True}],
    [{"Name": "HiddenResult", "Hidden": False}, {"Name": "ShownResult"}],
    [{"Name": "HiddenResult", "Hidden": False}, {"Name": "ShownResult", "Hidden": None}],
], ids=["control-not-a-link", "control-hidden", "hidden-omitted", "hidden-null"])
def test_a_control_not_on_the_content_type_voids_the_reading(links: list[dict[str, Any]]) -> None:
    rows, _sent, _output = _run(links=links)
    assert rows[LINKS]["outcome"] == "FAIL"
    assert set(BASE) <= voided(rows)


def test_a_same_title_list_it_did_not_make_is_left_alone() -> None:
    rows, sent, _output = _run(swaps=CLEANUP, existing="foreign")
    assert rows[LIST]["outcome"] == "FAIL" and set(BASE) <= voided(rows)
    assert not _writes(sent)


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
    assert rows[BASE[0]]["outcome"] == "MANUAL"


def test_the_revision_is_derived_from_the_probe_text() -> None:
    js = PROBE.read_text(encoding="utf-8")
    stamped = re.search(r"REVISION: ([0-9a-f]{8})", js)
    assert stamped is not None
    neutral = js.replace(stamped.group(1), "00000000")
    # Re-stamp with this digest whenever the probe changes.
    assert stamped.group(1) == hashlib.sha256(neutral.encode()).hexdigest()[:8]
    assert f"probe revision {stamped.group(1)}." in js


def test_a_mistyped_mode_fails_closed_by_name_and_sends_nothing() -> None:
    rows, sent, output = _run(swaps={"  const MODE = 'baseline';": "  const MODE = 'heder';"})
    assert sent == [] and rows == {}
    assert "MODE is 'heder'" in output and "TypeError" not in output


def test_a_control_run_needs_the_footer_only_formatter_before_it_writes() -> None:
    rows, sent, _output = run_probe(_MOCK, PROBE, GATES, {**PRIOR, "stored": ""},
                                    swaps=CONTROL_MODE, pin=False)
    assert rows[PREVIOUS]["outcome"] == "FAIL" and set(TOKEN) <= voided(rows)
    assert not _writes(sent)


def test_a_header_run_straight_after_the_baseline_is_refused() -> None:
    rows, sent, _output = _header(stored=FOOTER_ONLY)
    assert rows[PREVIOUS]["outcome"] == "FAIL" and set(TARGET) <= voided(rows)
    assert not _writes(sent)


def test_a_header_run_after_a_control_run_passes_the_previous_phase_check() -> None:
    rows, _sent, _output = _header()
    assert rows[PREVIOUS]["outcome"] == "PASS"
