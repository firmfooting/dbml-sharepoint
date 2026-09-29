"""Execute calculated-date-rest-probe.js under node against a mock list.

The mock holds one list, its calculated column and its items, answers the item read in the
envelope the Accept header asks for, and answers utctolocaltime with a wall clock ten hours
ahead of UTC, so a Created just after UTC midnight falls on the same local date.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "calculated-date-rest-probe.js"
LIST = "field.date.fixture-calc-date-list"
COLUMN = "field.date.fixture-calc-date-column"
ITEM = "field.date.fixture-calc-date-item"
ZONE = "field.date.control-site-time-zone"
DIFFER = "field.date.calc-date-local-and-utc-dates-differ"
NOMETADATA = "field.date.calc-date-rest-nometadata"
VERBOSE = "field.date.calc-date-rest-verbose"
OWNED = "dbml-sharepoint calculated-date probe scratch list. Safe to delete."
TENANT_TEXT = "Refused at https://example.sharepoint.com/sites/probe/_api/web"
FIELD_READ = "fields/getbyinternalnameortitle('CalcDue')"

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
    const LIST = "web/lists/getbytitle('dbmlsp Probe CalcDate')";
    let list = CONFIG.list;
    let field = null;
    const items = [];
    let digests = 0;
    globalThis.fetch = async (url, opts = {}) => {
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      const verb = (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET';
      const accept = String((opts.headers || {}).Accept || '');
      const sent = opts.body ? JSON.parse(String(opts.body)) : {};
      SENT.push({ verb, path, accept });
      for (const rule of CONFIG.rules || []) {
        if (!path.includes(rule.contains)) continue;
        if (rule.accept && !accept.includes(rule.accept)) continue;
        if (rule.reject) throw new TypeError('Failed to fetch');
        return answer(rule.status, rule.text);
      }
      if (path === 'contextinfo') {
        digests += 1;
        if (CONFIG.digestsAllowed !== undefined && digests > CONFIG.digestsAllowed) {
          return answer(403, 'denied');
        }
        return answer(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      if (path === 'web/RegionalSettings/TimeZone') {
        return answer(200, { Description: '(UTC+10:00) Canberra, Melbourne, Sydney', Id: 76,
          Information: { Bias: -600, DaylightBias: -60, StandardBias: 0 } });
      }
      const wall = /^web\\/RegionalSettings\\/TimeZone\\/utctolocaltime\\('([^']+)'\\)$/.exec(path);
      if (wall) {
        const local = new Date(Date.parse(wall[1]) + 600 * 60000).toISOString().slice(0, 19);
        const shape = CONFIG.wallShape || 'value';
        return answer(200, shape === 'bare' ? JSON.stringify(local) : { [shape]: local });
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
        field = { InternalName: sent.Title, TypeAsString: 'Calculated', OutputType: sent.OutputType,
          Formula: sent.Formula.replace(/[[\\]]/g, ''), DateFormat: 0,
          ...(CONFIG.fieldShape || {}) };
        return answer(201, { d: { Title: sent.Title } });
      }
      if (rest.startsWith("/fields/getbyinternalnameortitle('CalcDue')")) {
        const refuse = (value) => answer(400, { 'odata.error': { message: { value } } });
        if (!field) return refuse('Column does not exist.');
        // One answer a site might give when a calculated-only property is asked of another type.
        if (field.TypeAsString !== 'Calculated' && /OutputType|Formula|DateFormat/.test(rest)) {
          return refuse('The property does not exist.');
        }
        return answer(200, field);
      }
      if (rest === '/items' && verb === 'POST') {
        items.push({ Id: items.length + 1, Title: sent.Title, Created: CONFIG.created,
          CalcDue: CONFIG.calcDue });
        return answer(201, CONFIG.createShape || { Id: items.length });
      }
      if (rest.startsWith('/items?')) return answer(200, { value: items });
      const one = /^\\/items\\((\\d+)\\)/.exec(rest);
      if (one) {
        const row = items[Number(one[1]) - 1];
        const verbose = { d: { __metadata: { type: 'SP.Data.X' }, ...row } };
        return answer(200, accept.includes('verbose') ? verbose : row);
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
    settings = {"list": None, "created": "2026-09-28T15:30:00Z",
                "calcDue": "2026-10-12T14:00:00Z", **config}
    output = run_node(_MOCK.replace("__CONFIG__", json.dumps(settings)) + "\n" + _probe_js(gates))
    sent_line = next(ln for ln in output.splitlines() if ln.startswith("__SENT__"))
    rows_line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    rows = {} if rows_line is None else {
        row["id"]: row for row in json.loads(rows_line.removeprefix("__ROWS__"))}
    return rows, json.loads(sent_line.removeprefix("__SENT__")), output


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


def test_a_healthy_run_records_the_raw_value_in_both_envelopes() -> None:
    rows, sent, _ = _run()

    for row_id in (LIST, COLUMN, ITEM, ZONE):
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    for row_id in (NOMETADATA, VERBOSE):
        assert rows[row_id]["outcome"] == "OBSERVED", rows[row_id]
        assert rows[row_id]["state"] == "settled"
        assert 'CalcDue="2026-10-12T14:00:00Z" (string)' in rows[row_id]["evidence"]
        assert 'Created="2026-09-28T15:30:00Z"' in rows[row_id]["evidence"]
        assert "DateFormat=0" in rows[row_id]["evidence"]
    assert [r["accept"] for r in sent if r["path"].startswith(
        "web/lists/getbytitle('dbmlsp Probe CalcDate')/items(1)?$select=Id,Created,CalcDue")] == [
        "application/json;odata=nometadata", "application/json;odata=verbose"]
    assert sent[-1]["path"].endswith("/recycle")


def test_a_created_across_local_midnight_is_recorded_as_dates_differ() -> None:
    rows, _, _ = _run()

    assert rows[DIFFER]["outcome"] == "DATES DIFFER"
    said = rows[DIFFER]["evidence"]
    assert "UTC date 2026-09-28; the site's clock reads 2026-09-29T01:30:00" in said


def test_a_created_on_the_same_local_date_is_recorded_and_voids_nothing() -> None:
    rows, _, _ = _run(created="2026-09-28T05:00:00Z")

    assert rows[DIFFER]["outcome"] == "SAME DATE"
    assert rows[NOMETADATA]["outcome"] == "OBSERVED"


def test_a_value_the_probe_did_not_predict_is_recorded_not_judged() -> None:
    rows, _, _ = _run(calcDue=46307)

    assert rows[NOMETADATA]["outcome"] == "OBSERVED"
    assert "CalcDue=46307 (number)" in rows[NOMETADATA]["evidence"]


def test_a_refused_verbose_read_is_recorded_with_its_text() -> None:
    rows, _, _ = _run(rules=[{"contains": "Id,Created,CalcDue", "accept": "verbose", "status": 400,
                              "text": "The expression is not valid."}])

    assert rows[VERBOSE]["outcome"] == "REFUSED"
    assert "HTTP 400: The expression is not valid." in rows[VERBOSE]["evidence"]
    assert rows[NOMETADATA]["outcome"] == "OBSERVED"


@pytest.mark.parametrize("status", [429, 503, 403])
def test_a_throttle_or_a_denial_on_a_read_leaves_it_open(status: int) -> None:
    rows, _, _ = _run(rules=[{"contains": "Id,Created,CalcDue", "accept": "nometadata",
                              "status": status, "text": "busy"}])

    assert rows[NOMETADATA]["outcome"] == "NOT ESTABLISHED"
    assert rows[NOMETADATA]["state"] == "open"
    assert f"HTTP {status}" in rows[NOMETADATA]["evidence"]


def test_a_read_with_no_response_is_a_row_and_the_list_is_still_recycled() -> None:
    rows, sent, _ = _run(rules=[{"contains": "Id,Created,CalcDue", "accept": "verbose",
                                 "reject": True}])

    assert rows[VERBOSE]["outcome"] == "NOT ESTABLISHED"
    assert "no response: Failed to fetch" in rows[VERBOSE]["evidence"]
    assert sent[-1]["path"].endswith("/recycle")


def test_a_read_that_omits_the_column_is_not_an_observation() -> None:
    rows, _, _ = _run(rules=[{"contains": "Id,Created,CalcDue", "accept": "nometadata",
                              "status": 200, "text": '{"Id": 1}'}])

    assert rows[NOMETADATA]["outcome"] == "NOT ESTABLISHED"
    assert "carried no CalcDue" in rows[NOMETADATA]["evidence"]


def test_a_column_that_is_not_a_calculated_date_voids_everything_after_it() -> None:
    rows, _, _ = _run(fieldShape={"OutputType": 2})

    assert rows[COLUMN]["outcome"] == "FAIL"
    assert "OutputType differs: read 2, declared 4" in rows[COLUMN]["evidence"]
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(COLUMN)


def test_an_item_create_that_served_no_id_voids_the_reads() -> None:
    rows, _, _ = _run(createShape={})

    assert rows[ITEM]["outcome"] == "FAIL"
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(ITEM)


def test_an_unread_zone_is_recorded_and_the_reads_still_run() -> None:
    rows, _, _ = _run(rules=[{"contains": "web/RegionalSettings/TimeZone", "status": 429,
                              "text": "busy"}])

    assert rows[ZONE]["outcome"] == "NOT ESTABLISHED"
    assert rows[DIFFER]["outcome"] == "NOT ESTABLISHED"
    assert rows[NOMETADATA]["outcome"] == "OBSERVED"


def test_a_foreign_list_holding_the_title_is_never_written_to() -> None:
    rows, sent, _ = _run(list={"Id": "x", "BaseTemplate": 100, "Description": "somebody else's"})

    assert rows[LIST]["outcome"] == "FAIL"
    assert "refusing to modify it" in rows[LIST]["evidence"]
    assert not [r for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]


def test_with_cleanup_a_leftover_list_is_recycled_and_built_again() -> None:
    rows, sent, _ = _run(("CONFIRMED", "ALLOW_WRITES", "CLEANUP"),
                         list={"Id": "x", "BaseTemplate": 100, "Description": OWNED})

    assert rows[LIST]["outcome"] == "PASS"
    assert len([r for r in sent if r["path"].endswith("/recycle")]) == 2


def test_a_digest_lost_mid_run_leaves_the_rest_open_and_asks_for_a_recycle_by_hand() -> None:
    rows, sent, output = _run(digestsAllowed=2)

    assert rows[COLUMN]["outcome"] == "PASS"
    assert rows[ITEM]["state"] == "open"
    assert all(rows[row_id]["state"] == "open" for row_id in (DIFFER, NOMETADATA, VERBOSE))
    assert "probe aborted: contextinfo failed: HTTP 403" in output
    assert "recycle it by hand" in output
    assert not [r for r in sent if r["path"].endswith("/recycle")]


def test_each_observed_read_keeps_its_raw_answer() -> None:
    rows, _, _ = _run()

    assert rows[NOMETADATA]["evidence"].endswith(
        'answered {"Id":1,"Created":"2026-09-28T15:30:00Z","CalcDue":"2026-10-12T14:00:00Z"}')
    assert 'answered {"d":{"__metadata":{"type":"SP.Data.X"},"Id":1,' in rows[VERBOSE]["evidence"]
    assert 'answered {"value":"2026-09-29T01:30:00"}' in rows[DIFFER]["evidence"]


def test_an_observed_answer_that_names_the_tenant_is_redacted() -> None:
    verbose = json.dumps({"d": {"__metadata": {
        "uri": "https://example.sharepoint.com/sites/probe/_api/Web/Lists(guid'1')/Items(1)"},
        "Id": 1, "Created": "2026-09-28T15:30:00Z", "CalcDue": "2026-10-12T14:00:00Z"}})
    rows, _, _ = _run(rules=[{"contains": "Id,Created,CalcDue", "accept": "verbose",
                              "status": 200, "text": verbose}])

    assert rows[VERBOSE]["outcome"] == "OBSERVED"
    assert "[TENANT]/sites/probe/_api/Web/Lists" in rows[VERBOSE]["evidence"]
    assert "example.sharepoint.com" not in json.dumps(rows)


#: Built by hand, because json.dumps does not escape a slash and SharePoint may.
ESCAPED_URI = "https:\\/\\/example.sharepoint.com/sites/probe/_api/Web/Lists(guid'1')/Items(1)"
ESCAPED_BODY = ('{"d": {"__metadata": {"uri": "' + ESCAPED_URI + '", '
                '"host": "example.sharepoint.com"}, "Id": 1, "Created": "2026-09-28T15:30:00Z", '
                '"CalcDue": "2026-10-12T14:00:00Z"}}')


# The shared mock re-serialises a 2xx $select answer, so only the refusal keeps the escapes intact.
@pytest.mark.parametrize(("status", "outcome"), [(500, "REFUSED"), (200, "OBSERVED")],
                         ids=["refused-verbatim", "observed"])
def test_a_json_escaped_uri_and_a_bare_host_are_redacted(status: int, outcome: str) -> None:
    assert "\\/\\/example" in ESCAPED_BODY
    rows, _, _ = _run(rules=[{"contains": "Id,Created,CalcDue", "accept": "verbose",
                              "status": status, "text": ESCAPED_BODY}])

    evidence = rows[VERBOSE]["evidence"]
    assert rows[VERBOSE]["outcome"] == outcome
    assert "[TENANT]/sites/probe/_api/Web/Lists" in evidence
    assert '"host": "[TENANT]"' in evidence or '"host":"[TENANT]"' in evidence
    assert "example.sharepoint.com" not in json.dumps(rows).lower()


def test_the_calculated_only_properties_are_asked_only_of_a_calculated_column() -> None:
    _, sent, _ = _run()

    reads = [r["path"].split("?")[1] for r in sent if FIELD_READ in r["path"]]
    assert reads == ["$select=InternalName,TypeAsString", "$select=OutputType,Formula,DateFormat"]


def test_a_column_of_another_type_fails_on_its_type_not_on_a_refused_select() -> None:
    rows, sent, _ = _run(fieldShape={"TypeAsString": "Text"})

    assert rows[COLUMN]["outcome"] == "FAIL"
    assert 'TypeAsString differs: read "Text", declared "Calculated"' in rows[COLUMN]["evidence"]
    assert not [r for r in sent if FIELD_READ in r["path"] and "OutputType" in r["path"]]
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(COLUMN)
    assert sent[-1]["path"].endswith("/recycle")


@pytest.mark.parametrize(("rule", "said"), [
    ({"status": 400, "text": TENANT_TEXT}, 'HTTP 400: Refused at [TENANT]/sites/probe/_api/web'),
    ({"reject": True}, "no response: Failed to fetch"),
], ids=["refused", "no-response"])
def test_a_column_read_that_fails_keeps_its_answer_in_the_fixture_evidence(
    rule: dict[str, Any], said: str,
) -> None:
    rows, sent, _ = _run(rules=[{"contains": FIELD_READ, **rule}])

    assert rows[COLUMN]["outcome"] == "FAIL"
    assert f'Read differs: read "{said}"' in rows[COLUMN]["evidence"]
    assert "example.sharepoint.com" not in json.dumps(rows)
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(COLUMN)
    assert sent[-1]["path"].endswith("/recycle")


def test_a_refused_item_create_keeps_its_answer_in_the_fixture_evidence() -> None:
    rows, sent, _ = _run(rules=[{"contains": "CalcDate')/items", "status": 400,
                                 "text": TENANT_TEXT}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert ('Read differs: read "the item create answered HTTP 400: Refused at '
            '[TENANT]/sites/probe/_api/web"') in rows[ITEM]["evidence"]
    voided = {row_id for row_id, row in rows.items() if row["state"] == "void"}
    assert voided == _catalogued_dependents(ITEM)
    assert sent[-1]["path"].endswith("/recycle")


def test_an_item_read_that_is_refused_keeps_its_answer_in_the_fixture_evidence() -> None:
    rows, _, _ = _run(rules=[{"contains": "items(1)?$select=Id,Created", "status": 500,
                              "text": TENANT_TEXT}])

    assert rows[ITEM]["outcome"] == "FAIL"
    assert ('Read differs: read "HTTP 500: Refused at [TENANT]/sites/probe/_api/web"'
            in rows[ITEM]["evidence"])


def test_a_zone_answer_without_its_biases_keeps_the_answer() -> None:
    rows, _, _ = _run(rules=[{"contains": "web/RegionalSettings/TimeZone", "status": 200,
                              "text": '{"Description": "somewhere"}'}])

    assert rows[ZONE]["outcome"] == "FAIL"
    assert 'HTTP 200 carried no Information: {"Description": "somewhere"}' in rows[ZONE]["evidence"]


def test_a_site_clock_that_does_not_answer_keeps_both_shapes_answers() -> None:
    rows, _, _ = _run(rules=[{"contains": "utctolocaltime", "status": 400, "text": TENANT_TEXT}])

    assert rows[DIFFER]["outcome"] == "NOT ESTABLISHED"
    said = rows[DIFFER]["evidence"]
    assert "utctolocaltime('2026-09-28T15:30:00.000Z'): HTTP 400: Refused at [TENANT]" in said
    assert "utctolocaltime(@d): HTTP 400: Refused at [TENANT]" in said
    assert rows[NOMETADATA]["outcome"] == "OBSERVED"


def test_a_digest_lost_before_the_column_leaves_it_open_not_void() -> None:
    rows, sent, output = _run(digestsAllowed=1)

    assert rows[LIST]["outcome"] == "PASS"
    assert all(row["state"] == "open" for row_id, row in rows.items() if row_id not in (LIST, ZONE))
    told = "could not recycle 'dbmlsp Probe CalcDate' (contextinfo failed: HTTP 403); recycle it"
    assert f"{told} by hand." in output
    assert not [r for r in sent if r["path"].endswith("/recycle")]


def test_a_digest_lost_only_at_the_recycle_keeps_every_answer_and_asks_for_a_recycle() -> None:
    rows, sent, output = _run(digestsAllowed=3)

    assert all(row["state"] == "settled" for row in rows.values()), rows
    assert "recycle it by hand" in output
    assert not [r for r in sent if r["path"].endswith("/recycle")]


def test_an_early_return_whose_recycle_fails_says_so_before_the_results_block() -> None:
    rows, _, output = _run(fieldShape={"OutputType": 2},
                           rules=[{"contains": "/recycle", "status": 500, "text": "locked"}])

    assert rows[COLUMN]["outcome"] == "FAIL"
    told = "could not recycle 'dbmlsp Probe CalcDate' (HTTP 500); recycle it by hand."
    marker = "Copy this whole block back verbatim."
    assert output.count(marker) == 1
    assert output.index(told) < output.index("==================== RESULTS") < output.index(marker)


@pytest.mark.parametrize("shape", ["value", "bare", "UTCToLocalTime"])
def test_the_site_clock_is_read_in_each_answer_shape_the_zone_probe_accepts(shape: str) -> None:
    rows, _, _ = _run(wallShape=shape)

    assert rows[DIFFER]["outcome"] == "DATES DIFFER", rows[DIFFER]
    assert "the site's clock reads 2026-09-29T01:30:00" in rows[DIFFER]["evidence"]
