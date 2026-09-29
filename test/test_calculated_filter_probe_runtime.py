"""Execute calculated-filter-probe.js under node against a mock list.

The mock holds one list, its fields and its items, and answers the filters the probe sends by
evaluating them. The calculated-column queries answer as `CONFIG.calc` says: served, refused,
or served empty, which are the three answers the probe exists to tell apart.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "calculated-filter-probe.js"
LIST = "query.odata.fixture-calc-filter-list"
COLUMNS = "query.odata.fixture-calc-filter-columns"
ITEMS = "query.odata.fixture-calc-filter-items"
CONTROLS = [
    "query.odata.control-stored-boolean-eq-filter",
    "query.odata.control-stored-choice-eq-filter",
    "query.odata.control-stored-date-ne-null-filter",
    "query.odata.control-stored-date-le-datetime-filter",
]
SUBJECTS = [
    "query.odata.calc-over-created-ne-null-filter",
    "query.odata.calc-over-created-le-datetime-filter",
    "query.odata.calc-over-stored-ne-null-filter",
    "query.odata.calc-over-created-orderby",
]
OWNED = "dbml-sharepoint calculated-filter probe scratch list. Safe to delete."
SUBJECT_SENDS = {
    "query.odata.calc-over-created-ne-null-filter": "$filter=ProbeCalcCreated ne null",
    "query.odata.calc-over-created-le-datetime-filter": "$filter=ProbeCalcCreated le datetime",
    "query.odata.calc-over-stored-ne-null-filter": "$filter=ProbeCalcStored ne null",
    "query.odata.calc-over-created-orderby": "$orderby=ProbeCalcCreated desc",
}

_MOCK = textwrap.dedent("""
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
    const LIST = "web/lists/getbytitle('dbmlsp Probe CalcFilter')";
    const KINDS = { 8: 'Boolean', 6: 'Choice', 4: 'DateTime', 17: 'Calculated' };
    let list = CONFIG.list;
    const fields = new Map();
    const items = [];
    const calcOf = (row) => ({
      ProbeCalcCreated: '2026-10-13T00:00:00Z',
      ProbeCalcStored: row.ProbeDate ? row.ProbeDate.replace('2026', '2027') : null,
    });
    const served = (rows) => answer(200, { value: rows.map((row) => ({ Id: row.Id })) });
    globalThis.fetch = async (url, opts = {}) => {
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      const verb = (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET';
      const sent = opts.body ? JSON.parse(String(opts.body)) : {};
      SENT.push({ verb, path });
      for (const rule of CONFIG.rules || []) {
        if (!path.includes(rule.contains) || (rule.verb && rule.verb !== verb)) continue;
        if (rule.title && rule.title !== sent.Title) continue;
        if (rule.reject) throw new TypeError('Failed to fetch');
        return answer(rule.status, rule.text);
      }
      if (path === 'contextinfo') {
        return answer(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      if (path === 'web/lists' && verb === 'POST') {
        list = { Id: 'list-1', BaseTemplate: sent.BaseTemplate, Description: sent.Description };
        return answer(201, { Id: 'list-1' });
      }
      if (!path.startsWith(LIST)) return answer(404, 'no such endpoint in the mock: ' + path);
      const rest = path.slice(LIST.length);
      if (list === null) return answer(404, 'List does not exist.');
      if (rest === '' || rest.startsWith('?')) return answer(200, list);
      if (rest === '/recycle') { list = null; return answer(200, {}); }
      if (rest === '/fields' && verb === 'POST') {
        fields.set(sent.Title, { InternalName: sent.Title, TypeAsString: KINDS[sent.FieldTypeKind],
          OutputType: sent.OutputType,
          Formula: sent.Formula ? sent.Formula.replace(/[[\\]]/g, '') : undefined,
          ...((CONFIG.fieldShape || {})[sent.Title] || {}) });
        return answer(201, { d: { Title: sent.Title } });
      }
      const named = /^\\/fields\\/getbyinternalnameortitle\\('([^']+)'\\)/.exec(rest);
      if (named) {
        const field = fields.get(named[1]);
        // One answer a site might give; the probe must never select these on a stored column.
        if (field && field.TypeAsString !== 'Calculated' && /OutputType|Formula/.test(rest)) {
          return answer(400, { 'odata.error': { message: {
            value: "The property 'OutputType' does not exist on type 'SP.Field'." } } });
        }
        return field ? answer(200, field)
          : answer(400, { 'odata.error': { message: { value: 'Column does not exist.' } } });
      }
      if (rest === '/items' && verb === 'POST') {
        const row = { Id: items.length + 1, Title: sent.Title, ProbeFlag: sent.ProbeFlag,
          ProbeChoice: sent.ProbeChoice, ProbeDate: sent.ProbeDate || null };
        items.push({ ...row, ...calcOf(row), ...((CONFIG.itemShape || {})[sent.Title] || {}) });
        return answer(201, { Id: row.Id });
      }
      if (rest.startsWith('/items?')) {
        const options = Object.fromEntries(rest.slice('/items?'.length).split('&')
          .map((pair) => [pair.slice(0, pair.indexOf('=')), pair.slice(pair.indexOf('=') + 1)]));
        const filter = options.$filter || '';
        const orderBy = options.$orderby || '';
        if (!filter && (!orderBy || orderBy === 'Id')) return answer(200, { value: items });
        if ((filter + orderBy).includes('ProbeCalc')) {
          if (CONFIG.calc === 'refused') {
            return answer(500, { 'odata.error': { message: {
              value: 'The field cannot be used in the query filter expression.' } } });
          }
          if (CONFIG.calc === 'empty') return served([]);
          if (orderBy) return served([...items].reverse());
          if (filter.includes('ProbeCalcStored')) {
            return served(items.filter((row) => row.ProbeCalcStored));
          }
          return served(items);
        }
        const stored = {
          'ProbeFlag eq 0': (row) => row.ProbeFlag === false,
          "ProbeChoice eq 'Q1'": (row) => row.ProbeChoice === 'Q1',
          'ProbeDate ne null': (row) => Boolean(row.ProbeDate),
        }[filter];
        if (stored) return served(items.filter(stored));
        const bound = /^ProbeDate le datetime'([^']+)'$/.exec(filter);
        if (bound) return served(items.filter((row) => row.ProbeDate && row.ProbeDate <= bound[1]));
      }
      return answer(404, 'no such endpoint in the mock: ' + path);
    };
""")


def _probe_js(gates: tuple[str, ...]) -> str:
    js = PROBE.read_text(encoding="utf-8")
    for gate in gates:
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _run(
    gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"), **config: Any,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    settings = {"list": None, "calc": "served", **config}
    output = run_node(_MOCK.replace("__CONFIG__", json.dumps(settings)) + "\n" + _probe_js(gates))
    sent_line = next(ln for ln in output.splitlines() if ln.startswith("__SENT__"))
    rows_line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    rows = {} if rows_line is None else {
        row["id"]: row for row in json.loads(rows_line.removeprefix("__ROWS__"))}
    return rows, json.loads(sent_line.removeprefix("__SENT__")), output


def _writes(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]


def _catalogued_dependents(fixture: str) -> set[str]:
    catalog = json.loads((MANUAL / "probe-catalog.json").read_text(encoding="utf-8"))
    [entry] = [p for p in catalog["probes"] if p["file"] == PROBE.name]
    return {finding["id"] for scenario in entry["scenarios"] for finding in scenario["findings"]
            if fixture in finding["depends_on"]}


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates)

    assert sent == []
    assert rows == {}


def test_a_healthy_run_holds_every_fixture_and_control_and_records_the_served_rows() -> None:
    rows, sent, _ = _run()

    for row_id in (LIST, COLUMNS, ITEMS, *CONTROLS):
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    for row_id in SUBJECTS:
        assert rows[row_id]["outcome"] == "ACCEPTED", rows[row_id]
        assert rows[row_id]["state"] == "settled"
    assert "served A, C" in rows["query.odata.calc-over-stored-ne-null-filter"]["evidence"]
    assert "served C, B, A" in rows["query.odata.calc-over-created-orderby"]["evidence"]
    assert "holds 2 of 3 item(s) with ProbeCalcStored filled" in (
        rows["query.odata.calc-over-stored-ne-null-filter"]["evidence"])
    assert sent[-1]["path"].endswith("/recycle")


def test_a_refused_calculated_filter_is_recorded_with_its_text() -> None:
    rows, _, _ = _run(calc="refused")

    for row_id in SUBJECTS:
        assert rows[row_id]["outcome"] == "REFUSED", rows[row_id]
        assert "cannot be used in the query filter" in rows[row_id]["evidence"]
    assert all(rows[c]["outcome"] == "PASS" for c in CONTROLS)


def test_a_silently_empty_calculated_filter_is_recorded_beside_the_fill_count() -> None:
    rows, _, _ = _run(calc="empty")

    row = rows["query.odata.calc-over-created-ne-null-filter"]
    assert row["outcome"] == "ACCEPTED, NO ROWS"
    assert row["state"] == "settled"
    assert "served no rows; the unfiltered read holds 3 of 3 item(s) with ProbeCalcCreated" in (
        row["evidence"])


@pytest.mark.parametrize("status", [429, 503, 403])
def test_a_throttle_or_a_denial_on_a_calculated_query_leaves_it_open(status: int) -> None:
    rows, _, _ = _run(rules=[{"contains": "ProbeCalcStored ne null", "status": status,
                              "text": "busy"}])

    row = rows["query.odata.calc-over-stored-ne-null-filter"]
    assert row["outcome"] == "NOT ESTABLISHED"
    assert row["state"] == "open"
    assert f"HTTP {status}" in row["evidence"]
    assert rows["query.odata.calc-over-created-ne-null-filter"]["outcome"] == "ACCEPTED"


def test_a_calculated_query_with_no_response_is_a_row_and_the_list_is_still_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "$orderby=ProbeCalcCreated", "reject": True}])

    row = rows["query.odata.calc-over-created-orderby"]
    assert row["outcome"] == "NOT ESTABLISHED"
    assert "no response: Failed to fetch" in row["evidence"]
    assert sent[-1]["path"].endswith("/recycle")


def test_a_failed_control_voids_every_calculated_row() -> None:
    rows, _, _ = _run(rules=[{"contains": "ProbeFlag eq 0", "status": 500, "text": "no"}])

    assert rows[CONTROLS[0]]["outcome"] == "FAIL"
    assert {row_id for row_id in SUBJECTS if rows[row_id]["state"] == "void"} == set(SUBJECTS)
    assert set(SUBJECTS) <= _catalogued_dependents(CONTROLS[0])


@pytest.mark.parametrize(("control", "sent", "voided"), [
    ("query.odata.control-stored-date-ne-null-filter", "ProbeDate ne null",
     {"query.odata.calc-over-created-ne-null-filter",
      "query.odata.calc-over-stored-ne-null-filter"}),
    ("query.odata.control-stored-date-le-datetime-filter", "ProbeDate le datetime",
     {"query.odata.calc-over-created-le-datetime-filter"}),
], ids=["ne-null", "le-datetime"])
def test_a_failed_date_control_voids_only_the_subjects_sharing_its_operator(
    control: str, sent: str, voided: set[str],
) -> None:
    rows, _, _ = _run(rules=[{"contains": sent, "status": 500, "text": "no"}])

    assert rows[control]["outcome"] == "FAIL", rows[control]
    assert {row_id for row_id, row in rows.items() if row["state"] == "void"} == voided
    assert _catalogued_dependents(control) == voided
    for row_id in set(SUBJECTS) - voided:
        assert rows[row_id]["outcome"] == "ACCEPTED", rows[row_id]


@pytest.mark.parametrize(("rule", "said"), [
    ({"status": 401, "text": "denied"}, "the request was not authorised (HTTP 401): denied"),
    ({"status": 403, "text": "denied"}, "the request was not authorised (HTTP 403): denied"),
    ({"status": 408, "text": "late"}, "the request timed out (HTTP 408): late"),
    ({"status": 429, "text": "busy"}, "the request was throttled (HTTP 429): busy"),
    ({"status": 503, "text": "busy"}, "the request was throttled (HTTP 503): busy"),
    ({"reject": True}, "no response: Failed to fetch"),
], ids=["unauthenticated", "denied", "timed-out", "throttled", "unavailable", "no-response"])
@pytest.mark.parametrize(("control", "sent", "dependents"), [
    ("query.odata.control-stored-date-ne-null-filter", "ProbeDate ne null",
     {"query.odata.calc-over-created-ne-null-filter",
      "query.odata.calc-over-stored-ne-null-filter"}),
    ("query.odata.control-stored-date-le-datetime-filter", "ProbeDate le datetime",
     {"query.odata.calc-over-created-le-datetime-filter"}),
], ids=["ne-null", "le-datetime"])
def test_a_control_not_established_leaves_its_subjects_open_and_unasked(
    rule: dict[str, Any], said: str, control: str, sent: str, dependents: set[str],
) -> None:
    rows, requests, _ = _run(rules=[{"contains": sent, **rule}])

    assert rows[control]["outcome"] == "NOT ESTABLISHED", rows[control]
    assert rows[control]["state"] == "open"
    assert _catalogued_dependents(control) == dependents
    for row_id in dependents:
        assert rows[row_id]["outcome"] == "NOT ESTABLISHED", rows[row_id]
        assert rows[row_id]["state"] == "open", rows[row_id]
        assert rows[row_id]["evidence"].startswith(
            f"not asked: control {control} not established ({said})"), rows[row_id]
    assert not {row_id for row_id, row in rows.items() if row["state"] == "void"}
    for row_id in set(SUBJECTS) - dependents:
        assert rows[row_id]["outcome"] == "ACCEPTED", rows[row_id]
    for row_id in SUBJECTS:
        asked = [r for r in requests if SUBJECT_SENDS[row_id] in r["path"]]
        assert len(asked) == (0 if row_id in dependents else 1), (row_id, asked)


def test_the_le_control_sends_the_subject_s_datetime_literal_on_a_stored_date() -> None:
    rows, sent, _ = _run()

    [control] = [r["path"] for r in sent if "ProbeDate le datetime'" in r["path"]]
    [subject] = [r["path"] for r in sent if "ProbeCalcCreated le datetime'" in r["path"]]
    assert control.split("ProbeDate le ")[1] == subject.split("ProbeCalcCreated le ")[1]
    assert "served A, C; written A, C" in rows[CONTROLS[3]]["evidence"]


def test_a_calculated_column_of_the_wrong_output_type_voids_everything_after_it() -> None:
    rows, _, _ = _run(fieldShape={"ProbeCalcCreated": {"OutputType": 2}})

    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert "ProbeCalcCreated.OutputType differs: read 2, declared 4" in rows[COLUMNS]["evidence"]
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(COLUMNS)


def test_a_seed_that_did_not_read_back_as_written_voids_the_controls_and_subjects() -> None:
    rows, _, _ = _run(itemShape={"dbmlsp calc filter A": {"ProbeFlag": True}})

    assert rows[ITEMS]["outcome"] == "FAIL"
    assert "A.ProbeFlag differs: read true, declared false" in rows[ITEMS]["evidence"]
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(ITEMS)


def test_a_foreign_list_holding_the_title_is_never_written_to() -> None:
    rows, sent, _ = _run(list={"Id": "x", "BaseTemplate": 100, "Description": "somebody else's"})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "refusing to modify it" in rows[LIST]["evidence"]
    assert _writes(sent) == []


def test_a_leftover_list_is_refused_until_cleanup_is_set() -> None:
    rows, sent, _ = _run(list={"Id": "x", "BaseTemplate": 100, "Description": OWNED})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "CLEANUP is off" in rows[LIST]["evidence"]
    assert _writes(sent) == []


def test_with_cleanup_a_leftover_list_is_recycled_and_built_again() -> None:
    rows, sent, _ = _run(("CONFIRMED", "ALLOW_WRITES", "CLEANUP"),
                         list={"Id": "x", "BaseTemplate": 100, "Description": OWNED})

    assert rows[LIST]["outcome"] == "PASS"
    assert [r["verb"] for r in sent if r["path"].endswith("/recycle")] == ["POST", "POST"]


def test_a_list_create_with_no_response_leaves_the_rows_open_and_recycles_nothing() -> None:
    rows, sent, output = _run(rules=[{"contains": "web/lists", "reject": True}])

    assert rows[LIST]["state"] == "open"
    assert all(rows[row_id]["state"] == "open" for row_id in SUBJECTS)
    assert "probe aborted" in output
    assert not [r for r in sent if r["path"].endswith("/recycle")]


def test_a_refused_column_create_voids_what_follows_and_the_list_is_still_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/fields", "verb": "POST", "status": 400,
                                 "text": "Invalid field type."}])

    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert "ProbeFlag.TypeAsString is absent from the payload" in rows[COLUMNS]["evidence"]
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(COLUMNS)
    assert sent[-1]["path"].endswith("/recycle")


def test_a_throttled_seed_voids_the_controls_and_the_list_is_still_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/items", "verb": "POST", "status": 429,
                                 "text": "busy"}])

    assert rows[ITEMS]["outcome"] == "FAIL"
    assert "Items differs: read 0, declared 3" in rows[ITEMS]["evidence"]
    assert {row_id for row_id, row in rows.items() if row["state"] == "void"} == (
        _catalogued_dependents(ITEMS))
    assert sent[-1]["path"].endswith("/recycle")


def test_a_refusal_quoting_the_site_url_is_recorded_without_the_tenant() -> None:
    said = "Bad request to https://example.sharepoint.com/sites/probe/_api/web"
    rows, _, _ = _run(rules=[{"contains": "ProbeCalcCreated ne null", "status": 500, "text": said}])

    row = rows["query.odata.calc-over-created-ne-null-filter"]
    assert row["outcome"] == "REFUSED"
    assert "[TENANT]/sites/probe/_api/web" in row["evidence"]
    assert "example.sharepoint.com" not in json.dumps(rows)


def test_a_yes_no_create_refused_part_way_names_it_and_the_list_is_still_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/fields", "verb": "POST", "title": "ProbeFlag",
                                 "status": 400, "text": "Invalid field type."}])

    evidence = rows[COLUMNS]["evidence"]
    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert "ProbeFlag.TypeAsString is absent from the payload" in evidence
    assert evidence.count("is absent from the payload") == 1
    assert 'ProbeCalcCreated.TypeAsString="Calculated"' in evidence
    assert len([r for r in sent if r["verb"] == "POST" and r["path"].endswith("/fields")]) == 5
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(COLUMNS)
    assert sent[-1]["path"].endswith("/recycle")


def test_a_seed_throttled_part_way_fails_on_the_count_and_the_list_is_still_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/items", "verb": "POST",
                                 "title": "dbmlsp calc filter B", "status": 429, "text": "busy"}])

    assert rows[ITEMS]["outcome"] == "FAIL"
    assert "Items differs: read 2, declared 3" in rows[ITEMS]["evidence"]
    assert "B.ProbeFlag is absent from the payload" in rows[ITEMS]["evidence"]
    assert {row_id for row_id, row in rows.items() if row["state"] == "void"} == (
        _catalogued_dependents(ITEMS))
    assert sent[-1]["path"].endswith("/recycle")


def test_an_answered_calculated_query_keeps_the_raw_answer() -> None:
    served, _, _ = _run()
    empty, _, _ = _run(calc="empty")

    assert 'answered {"value":[{"Id":1},{"Id":2},{"Id":3}]}' in (
        served["query.odata.calc-over-created-ne-null-filter"]["evidence"])
    assert 'answered {"value":[]}' in (
        empty["query.odata.calc-over-created-ne-null-filter"]["evidence"])


def test_an_accepted_answer_that_names_the_tenant_is_redacted() -> None:
    said = ('{"value":[{"Id":1}],'
            '"odata.nextLink":"https://example.sharepoint.com/sites/probe/_api/web/next"}')
    rows, _, _ = _run(rules=[{"contains": "ProbeCalcCreated ne null", "status": 200, "text": said}])

    row = rows["query.odata.calc-over-created-ne-null-filter"]
    assert row["outcome"] == "ACCEPTED"
    assert "[TENANT]/sites/probe/_api/web/next" in row["evidence"]
    assert "example.sharepoint.com" not in json.dumps(rows)


def test_a_control_answered_without_rows_keeps_the_answer_text() -> None:
    rows, _, _ = _run(rules=[{"contains": "ProbeFlag eq 0", "status": 200, "text": "not a feed"}])

    row = rows[CONTROLS[0]]
    assert row["outcome"] == "FAIL"
    assert "HTTP 200 carried no rows: not a feed" in row["evidence"]
    assert {row_id for row_id in SUBJECTS if rows[row_id]["state"] == "void"} == set(SUBJECTS)


def test_a_stored_column_is_read_without_the_calculated_only_properties() -> None:
    rows, sent, _ = _run()

    reads = {r["path"].split("getbyinternalnameortitle('")[1].split("'")[0]: r["path"]
             for r in sent if r["verb"] == "GET" and "getbyinternalnameortitle(" in r["path"]}
    for stored in ("ProbeFlag", "ProbeChoice", "ProbeDate"):
        assert "OutputType" not in reads[stored] and "Formula" not in reads[stored], reads[stored]
    for calculated in ("ProbeCalcCreated", "ProbeCalcStored"):
        assert "OutputType,Formula" in reads[calculated], reads[calculated]
    assert rows[COLUMNS]["outcome"] == "PASS", rows[COLUMNS]


@pytest.mark.parametrize(("rule", "said"), [
    ({"status": 400, "text": "Refused at https://example.sharepoint.com/sites/probe/_api/web"},
     "HTTP 400: Refused at [TENANT]/sites/probe/_api/web"),
    ({"reject": True}, "no response: Failed to fetch"),
], ids=["refused", "no-response"])
def test_a_field_read_that_fails_keeps_its_answer_in_the_fixture_evidence(
    rule: dict[str, Any], said: str,
) -> None:
    rows, sent, _ = _run(rules=[{"contains": "getbyinternalnameortitle('ProbeChoice')",
                                 "verb": "GET", **rule}])

    evidence = rows[COLUMNS]["evidence"]
    assert rows[COLUMNS]["outcome"] == "FAIL"
    assert f"ProbeChoice.Read differs: read {json.dumps(said)}" in evidence
    assert "example.sharepoint.com" not in json.dumps(rows)
    assert {row_id for row_id, row in rows.items() if row["state"] == "void"} == (
        _catalogued_dependents(COLUMNS))
    assert sent[-1]["path"].endswith("/recycle")


def test_an_early_return_whose_recycle_fails_says_so_before_the_results_block() -> None:
    rows, _, output = _run(rules=[
        {"contains": "/recycle", "status": 500, "text": "locked"},
        {"contains": "/fields", "verb": "POST", "status": 400, "text": "Invalid field type."},
    ])

    assert rows[COLUMNS]["outcome"] == "FAIL"
    told = "could not recycle 'dbmlsp Probe CalcFilter' (HTTP 500); recycle it by hand."
    marker = "Copy this whole block back verbatim."
    assert output.count(marker) == 1
    assert output.index(told) < output.index("==================== RESULTS") < output.index(marker)
