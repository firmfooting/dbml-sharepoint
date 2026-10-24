"""Execute formula-facts-probe.js under node against a mock web.

The probe measures; these tests check its plumbing only. The mock answers with its own invented
shapes, so no test asserts how a site behaves, only that the probe reports what it was given,
refuses what it cannot depend on, and prints every fact key.
"""

from __future__ import annotations

import hashlib
import json
import re
import textwrap
from collections.abc import Mapping

import pytest
from _json_view import Json
from _paths import MANUAL
from _probe_runs import ended_with_report, run_probe, voided

from dbml_sharepoint.testing.node import NODE

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "formula-facts-probe.js"
GATES = ("CONFIRMED", "ALLOW_WRITES")
READ = {"  const MODE = 'build';": "  const MODE = 'read';"}
SIZE = {"  const MODE = 'build';": "  const MODE = 'size';"}
FACT_KEYS = {
    "date_overflow", "blank_coercion", "text_equality_case", "created_plus_days_day",
    "calculated_date_read", "calculated_number_display", "header_size_limit",
}
LIST = "formula.calc.fixture-facts-list"
ITEM = "formula.calc.fixture-facts-item"
TYPE = "formula.calc.fixture-facts-content-type"
CREATED = "formula.datetime.fact-created-plus-days-day"
TYPES = ("number", "text", "date", "choice")
OPS = ["add", "sub", "mul", "div", "pow", "cat", "eq", "ne", "lt", "gt", "le", "ge"]
CASE_NAMES = (
    [f"B_{op}_{t}_{s}" for op in OPS for t in TYPES for s in "lrb"]
    + ["Dov1", "Dov2", "Dov3", "Dov4", "Dov5", "Teq1", "Teq2", "CpdZero", "CpdOne", "Cdr",
       "CdrTime", "Ndisp", "NdispWhole"]
)
FORMATTER = json.dumps({"elmType": "div", "children": [
    {"elmType": "div", "txtContent": "@currentField"},
    {"elmType": "div", "txtContent": "=toLocaleString(@currentField)"},
    {"elmType": "div", "txtContent": "=toLocaleDateString(@currentField)"},
    {"elmType": "div", "txtContent": "@currentField.displayValue"}]}, separators=(",", ":"))

# The shapes are this mock's own; the probe never compares what a site gives with them.
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
    const GUID = '00000000-0000-4000-8000-0000000000a';
    const idOf = (title) => GUID + (title.replace('FormulaFacts', '') || '1');
    const OWNER = 'dbml-sharepoint formula-facts probe scratch list. Safe to delete.';
    const OPERANDS = { NumA: 'Number', BlankNum: 'Number', TextA: 'Text', BlankText: 'Text',
      DateA: 'DateTime', DateLeap: 'DateTime', BlankDate: 'DateTime', ChoiceA: 'Choice',
      BlankChoice: 'Choice' };
    // The mock encodes a leading D or T of a calculated internal name.
    const encode = (title) => (/^[DT]/.test(title)
      ? '_x00' + title.charCodeAt(0).toString(16).toUpperCase() + '_' + title.slice(1) : title);
    const field = (Title, InternalName, TypeAsString) => ({ Title, InternalName, TypeAsString });
    const standingList = (title, names = []) => ({ title, Description: OWNER,
      hasItem: !!CONFIG.prior,
      fields: [...Object.entries(OPERANDS).map(([n, t]) => field(n, n, t)),
        ...names.map((n) => field(n, encode(n), 'Calculated'))] });
    const lists = {};
    if (CONFIG.existing) {
      lists.FormulaFacts = { title: 'FormulaFacts', fields: [], hasItem: false,
        Description: CONFIG.existing === 'foreign' ? 'Not made by the probe.' : OWNER };
    }
    let formatters = {};
    let stored = null;
    if (CONFIG.prior) {
      CONFIG.chunks.forEach((names, i) => {
        const title = 'FormulaFacts' + (i ? i + 1 : '');
        lists[title] = standingList(title, names);
      });
      formatters = { Cdr: CONFIG.formatter, CdrTime: CONFIG.formatter };
    }
    const fail = (message) => answer(500, { error: { message: { value: message } } });
    globalThis.fetch = async (url, init = {}) => {
      const path = String(url).replace(/^https:\/\/example\.sharepoint\.com\/sites\/probe/, '');
      const method = init.method || 'GET';
      const body = typeof init.body === 'string' ? init.body : '';
      SENT.push({ method, path, body });
      if (path.endsWith('/_api/contextinfo')) return answer(200, { d: {
        GetContextWebInformation: { FormDigestValue: 'digest' } } });
      if (path.endsWith('/_api/web/lists') && method === 'POST') {
        const sent = JSON.parse(body);
        lists[sent.Title] = { title: sent.Title, Description: sent.Description, fields: [],
          hasItem: false };
        return answer(201, { d: { Id: idOf(sent.Title) } });
      }
      if (path.includes('/regionalsettings/timezone')) {
        const zone = { Bias: -600, StandardBias: 0, DaylightBias: -60 };
        return answer(200, { Id: 1, Information: CONFIG.zone || zone });
      }
      const found = new RegExp(`getbytitle\\('(FormulaFacts\\d*)'\\)|lists\\(guid'${GUID}(\\d)'\\)`)
        .exec(path);
      if (!found) return answer(404, 'mock has no ' + path);
      const title = found[1] || 'FormulaFacts' + (found[2] === '1' ? '' : found[2]);
      const rest = path.slice(found.index + found[0].length);
      const standing = lists[title];
      if (!standing) return answer(404, { error: { message: { value: 'List does not exist.' } } });
      if (rest.startsWith('/recycle')) { delete lists[title]; return answer(200, { d: {} }); }
      if (rest.startsWith('/fields/createfieldasxml')) {
        const name = /Name='([^']+)'/.exec(JSON.parse(body).parameters.SchemaXml)[1];
        const kind = /Type='([^']+)'/.exec(JSON.parse(body).parameters.SchemaXml)[1];
        standing.fields.push({ Title: name, InternalName: name, TypeAsString: kind });
        return answer(201, { d: {} });
      }
      if (rest === '/fields' && method === 'POST') {
        const sent = JSON.parse(body);
        if (CONFIG.refuse && sent.Formula.includes(CONFIG.refuse)) {
          return fail('refused: ' + sent.Formula);
        }
        standing.fields.push({ Title: sent.Title, InternalName: encode(sent.Title),
          TypeAsString: 'Calculated' });
        return answer(201, { d: {} });
      }
      if (rest.startsWith('/fields?')) {
        return answer(200, { value: standing.fields });
      }
      const named = /^\/fields\/getbyinternalnameortitle\('([^']+)'\)/.exec(rest);
      if (named) {
        if (method === 'POST') {
          formatters[named[1]] = JSON.parse(body).CustomFormatter;
          return answer(204, '');
        }
        if (rest.includes('SchemaXml')) {
          return answer(200, { SchemaXml: CONFIG.schema || '<Field Name="Ndisp"/>' });
        }
        return answer(200, { CustomFormatter: formatters[named[1]] ?? null });
      }
      if (rest.startsWith('/items') && method === 'POST') {
        standing.hasItem = true;
        return answer(201, { d: { Id: 1 } });
      }
      if (rest.startsWith('/items?')) {
        return answer(200, { value: standing.hasItem ? [{ Id: 1 }] : [] });
      }
      if (rest.startsWith('/items(1)/FieldValuesAsText')) {
        // Displayed text escapes an encoded name (OData_, _x005f_); the item never does.
        const shown = Object.fromEntries([1, 2, 3, 4, 5].map((i) => [
          'OData__x005f_x0044_ov' + i, '1/0' + i + '/2027']));
        return answer(200, { Created: '21/10/2026 6:00 AM', Cdr: '15/03/2026',
          CdrTime: '21/10/2026', Ndisp: '1.67', NdispWhole: '10', ...shown,
          CpdZero: CONFIG.cpdZeroText || '21/10/2026 7:00 AM', CpdOne: '22/10/2026 7:00 AM' });
      }
      if (rest.startsWith('/items(1)')) {
        const wanted = decodeURIComponent(rest.split('$select=')[1]).split(',');
        const row = { Id: 1, Created: CONFIG.created || '2026-10-20T20:00:00Z', NumA: 5,
          TextA: 'abc',
          DateA: '2026-03-15T00:00:00Z', ChoiceA: 'Low', DateLeap: '2024-02-29T00:00:00Z',
          BlankNum: null, BlankDate: null, BlankChoice: null,
          BlankText: CONFIG.blankValue === undefined ? null : CONFIG.blankValue,
          CpdZero: CONFIG.cpdZero || '2026-10-21T00:00:00Z', CpdOne: '2026-10-22T00:00:00Z',
          Cdr: '2026-03-15T00:00:00Z', CdrTime: '2026-10-21T06:00:00Z' };
        // An item exposes a column as its internal name, or OData_ plus it when that starts with _.
        const props = Object.fromEntries(standing.fields.map((f) => [
          f.InternalName.startsWith('_') ? 'OData_' + f.InternalName : f.InternalName, f.Title]));
        const bad = wanted.filter((n) => !(n in props) && !(n in row));
        if (bad.length) return fail('The field or property does not exist: ' + bad.join(','));
        return answer(200, Object.fromEntries(wanted.map((n) => {
          const t = props[n] ?? n;
          return [n, t in row ? row[t] : 'v_' + t];
        })));
      }
      if (rest.startsWith('/contenttypes?')) {
        return answer(200, { value: [{ Name: 'Folder', StringId: '0x0120' },
          { Name: 'Item', StringId: '0x01' }] });
      }
      if (rest.startsWith("/contenttypes('0x01')")) {
        if (method === 'POST') {
          const busy = CONFIG.throttle === true ? 429 : CONFIG.throttle;
          if (busy) return answer(busy, 'busy');
          const next = JSON.parse(body).ClientFormCustomFormatter;
          if (CONFIG.limit && next.length > CONFIG.limit) return fail('the formatter is too large');
          stored = next;
          return answer(204, '');
        }
        return answer(200, { ClientFormCustomFormatter: CONFIG.ctBroken ? 5 : stored });
      }
      return answer(200, { Id: idOf(title), Description: standing.Description,
        RootFolder: { ServerRelativeUrl: '/sites/probe/Lists/FormulaFacts' },
        ListItemEntityTypeFullName: 'SP.Data.FormulaFactsListItem' });
    };
""")

Run = tuple[dict[str, Json], list[Json], str]
PER_LIST = 40
BLANK_CASES = len(OPS) * len(TYPES) * 3
_ORDER = CASE_NAMES[BLANK_CASES:] + CASE_NAMES[:BLANK_CASES]
CHUNKS = [_ORDER[i:i + PER_LIST] for i in range(0, len(_ORDER), PER_LIST)]
PRIOR = {"prior": True, "chunks": CHUNKS, "formatter": FORMATTER}
SIZE_PRIOR: dict[str, object] = {"prior": True, "chunks": [[]], "formatter": ""}


def _run(config: Mapping[str, object] | None = None, swaps: dict[str, str] | None = None,
         gates: tuple[str, ...] = GATES) -> Run:
    # The list title is fixed, so there is no per-run token to pin.
    return run_probe(_MOCK, PROBE, gates, config or {}, swaps=swaps, pin=False)


def _facts(output: str) -> Json:
    line = next(ln for ln in output.splitlines() if ln.startswith("FACTS "))
    return Json.loads(line.removeprefix("FACTS "))


def _writes(sent: list[Json]) -> list[Json]:
    return [s for s in sent if s["method"] == "POST" and not s["path"].endswith("/contextinfo")]


def test_an_unconfirmed_probe_prints_its_plan_and_sends_nothing() -> None:
    rows, sent, output = _run(gates=())

    assert sent == [] and "Set CONFIRMED = true" in output
    assert rows[LIST]["state"] == "open"
    assert set(_facts(output).keys()) == FACT_KEYS


def test_a_build_run_creates_every_case_and_holds_its_fixtures() -> None:
    rows, sent, output = _run()

    for row_id in (LIST, "formula.calc.fixture-facts-columns", ITEM,
                   "formula.datetime.fixture-facts-column-formatter"):
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    assert rows["formula.calc.case-columns-accepted"]["outcome"] == "ALL ACCEPTED"
    assert sum(1 for s in _writes(sent) if s["path"].endswith("/fields")) == len(CASE_NAMES)
    assert ended_with_report(output)


def test_blank_is_covered_for_every_operator_operand_type_and_side() -> None:
    _rows, sent, _output = _run()

    created = {json.loads(s["body"].text)["Title"] for s in _writes(sent)
               if s["path"].endswith("/fields")}
    assert len(CASE_NAMES) == BLANK_CASES + 13
    assert {n for n in CASE_NAMES if n.startswith("B_")} <= created
    twins = {"BlankNum": "Number", "BlankText": "Text", "BlankDate": "DateTime",
             "BlankChoice": "Choice"}
    made = [json.loads(s["body"].text)["parameters"]["SchemaXml"] for s in _writes(sent)
            if s["path"].endswith("/fields/createfieldasxml")]
    for name, kind in twins.items():
        assert any(f"Name='{name}'" in x and f"Type='{kind}'" in x for x in made), name
    facts = _facts(_run(PRIOR, READ)[2])["blank_coercion"]["cases"]
    assert all(set(facts[op][t].keys()) == {"left", "right", "both"} for op in OPS for t in TYPES)


def test_a_refused_case_is_recorded_with_its_message_and_the_run_goes_on() -> None:
    rows, _sent, _output = _run({"refuse": "^"})

    row = rows["formula.calc.case-columns-accepted"]
    assert row["outcome"] == "SOME REFUSED" and "refused: =[BlankNum]^[NumA]" in row["evidence"]
    assert rows["formula.datetime.fixture-facts-column-formatter"]["outcome"] == "PASS"


def test_a_read_run_prints_exactly_the_fact_keys_with_results() -> None:
    rows, sent, output = _run(PRIOR, READ)

    facts = _facts(output)
    assert set(facts.keys()) == FACT_KEYS
    assert facts["header_size_limit"] == "NOT MEASURED IN THIS MODE"
    assert all(facts[k] != "VOID" for k in FACT_KEYS)
    assert not _writes(sent)
    cases = facts["blank_coercion"]["cases"]
    assert cases["add"]["number"]["left"] == "v_B_add_number_l"
    assert cases["ge"]["choice"]["both"] == "v_B_ge_choice_b"
    assert rows["formula.datetime.calculated-date-form-body-reads"]["outcome"] == "MANUAL"


def test_a_read_run_reaches_columns_whose_internal_name_the_server_encoded() -> None:
    _rows, sent, output = _run(PRIOR, READ)

    selects = " ".join(s["path"].text for s in sent if "$select=" in s["path"].text)
    assert "OData__x0044_ov1" in selects and "OData__x0054_eq1" in selects
    facts = _facts(output)
    assert facts["date_overflow"]["DATE(2026,13,5)"] == {
        "instant": "v_Dov1", "displayed": "1/01/2027"}
    assert facts["text_equality_case"]["literal"] == "v_Teq1"


def test_a_displayed_overflow_date_is_found_under_its_escaped_key() -> None:
    # Fails without the escaped-key lookup: the mock offers only the OData_ and _x005f_ spelling.
    _rows, _sent, output = _run(PRIOR, READ)

    overflow = _facts(output)["date_overflow"]
    assert [v["displayed"] for k, v in overflow.items()] == [f"1/0{i}/2027" for i in range(1, 6)]


def test_the_created_day_is_reported_against_both_candidate_local_days() -> None:
    rows, _sent, output = _run(PRIOR, READ)

    created = _facts(output)["created_plus_days_day"]
    assert created["utc_day"] == "2026-10-20" and created["standard_local_day"] == "2026-10-21"
    assert created["verdict"] == "SITE-LOCAL DAY"
    assert (created["shown_zero"], created["shown_one"]) == ("2026-10-21", "2026-10-22")
    assert rows[CREATED]["state"] == "settled"


def test_a_created_item_whose_local_day_equals_the_utc_day_stays_open() -> None:
    rows, _sent, output = _run({**PRIOR, "created": "2026-10-20T02:00:00Z",
                                "zone": {"Bias": 0, "StandardBias": 0, "DaylightBias": 0}}, READ)

    assert rows[CREATED]["state"] == "open"
    assert _facts(output)["created_plus_days_day"]["verdict"].startswith("NOT DISCRIMINATED")


def test_a_blank_column_that_is_not_blank_voids_every_fact_resting_on_the_item() -> None:
    rows, _sent, output = _run({**PRIOR, "blankValue": 3}, READ)

    facts = _facts(output)
    resting = FACT_KEYS - {"header_size_limit"}
    assert rows[ITEM]["outcome"] == "FAIL" and "BlankText" in rows[ITEM]["evidence"]
    assert {k for k in FACT_KEYS if facts[k] == "VOID"} == resting
    assert len(voided(rows)) >= len(resting)
    assert ended_with_report(output)


def test_a_formatter_that_does_not_read_back_voids_the_rows_resting_on_it() -> None:
    rows, _sent, output = _run({**PRIOR, "formatter": "{}"}, READ)

    assert rows["formula.datetime.fixture-facts-column-formatter"]["outcome"] == "FAIL"
    assert "formula.datetime.calculated-date-formatter-reads" in voided(rows)
    assert _facts(output)["date_overflow"] != "VOID"


def test_a_size_run_finds_the_boundary_by_doubling_then_bisecting() -> None:
    rows, sent, output = _run({**SIZE_PRIOR, "limit": 5000}, SIZE)

    limit = _facts(output)["header_size_limit"]
    assert limit["largest_saved"] == 5000 and limit["first_refused"] == 5001
    assert rows["formula.calc.header-size-renders"]["outcome"] == "MANUAL"
    assert len(_writes(sent)) < 40


def test_a_size_run_with_a_content_type_that_does_not_read_back_prints_void() -> None:
    rows, sent, output = _run({**SIZE_PRIOR, "ctBroken": True}, SIZE)

    assert rows[TYPE]["outcome"] == "FAIL"
    assert _facts(output)["header_size_limit"] == "VOID"
    assert not _writes(sent)


def test_a_throttled_size_search_is_left_open_not_recorded_as_a_limit() -> None:
    rows, _sent, output = _run(
        {**SIZE_PRIOR, "throttle": True}, SIZE)

    row = rows["formula.calc.fact-header-size-limit"]
    assert row["state"] == "open" and "429" in row["evidence"]
    assert _facts(output)["header_size_limit"].startswith("INCONCLUSIVE")


@pytest.mark.parametrize("status", [502, 504])
def test_a_gateway_error_on_the_size_search_is_inconclusive_not_a_refusal(status: int) -> None:
    rows, _sent, output = _run({**SIZE_PRIOR, "throttle": status}, SIZE)

    row = rows["formula.calc.fact-header-size-limit"]
    assert row["state"] == "open" and str(status) in row["evidence"]
    assert _facts(output)["header_size_limit"].startswith("INCONCLUSIVE")


def test_a_foreign_list_of_the_same_title_is_never_touched() -> None:
    rows, sent, _output = _run({"existing": "foreign"})

    assert rows[LIST]["outcome"] == "FAIL" and not _writes(sent)


def test_a_mistyped_mode_fails_closed_by_name_and_sends_nothing() -> None:
    rows, sent, output = _run(swaps={"  const MODE = 'build';": "  const MODE = 'bild';"})

    assert sent == [] and rows == {}
    assert "MODE is 'bild'" in output and "TypeError" not in output


def test_the_revision_is_derived_from_the_probe_text() -> None:
    js = PROBE.read_text(encoding="utf-8")
    stamped = re.search(r"REVISION: ([0-9a-f]{8})", js)
    assert stamped is not None
    neutral = js.replace(stamped.group(1), "00000000")
    # Re-stamp with this digest whenever the probe changes.
    assert stamped.group(1) == hashlib.sha256(neutral.encode()).hexdigest()[:8]
    assert f"probe revision {stamped.group(1)}." in js
