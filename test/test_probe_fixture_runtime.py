"""Execute the shared `establishFixture` helper and the probes built on it (#559).

A fixture row recorded from a status, a name match or a literal `'PASS'` lets
a measurement run against a fixture that is not the one declared, and the
finding it produces is confident and wrong. The helper reads the declared
properties back and voids every dependent row when one does not hold.

The helper is run on its own first, once per way it fails closed and once
healthy, then each probe fixed on it is run against a mock SharePoint with a
wrong-shaped fixture and with a healthy one.
"""

import importlib.util
import json
import sys
import textwrap
from types import ModuleType
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

WINDOW = (
    "globalThis.window = { _spPageContextInfo: "
    "{ webAbsoluteUrl: 'https://example.sharepoint.com/sites/test' } };\n"
)

#: Shared by every mock below: a fetch response, and a record of what was sent.
_RESPONSES = textwrap.dedent("""
    const SENT = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => 'Thu, 24 Sep 2026 09:00:00 GMT' },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    const digestResponse = () => jsonResponse(200, {
      d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
    // A field absent by name answers 400 on a live site, not 404.
    const noSuchField = () => jsonResponse(400, {
      'odata.error': { message: { value: 'Column does not exist.' } } });
    // Only the status is asserted on, so the body claims nothing about its shape.
    const throttled = () => jsonResponse(429, { 'odata.error': { message: { value: '' } } });
    // Waits are skipped, so a probe's ten-second pause costs the suite nothing.
    const realSetTimeout = setTimeout;
    globalThis.setTimeout = (fn, ms, ...rest) => realSetTimeout(fn, 0, ...rest);
""")


def _load_renderer() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "dbmlsp_render_probes_fixture", MANUAL / "render_probes.py",
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _rows(output: str) -> dict[str, dict[str, str]]:
    line = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert line is not None, f"no result table was printed:\n{output[-3000:]}"
    return {row["id"]: row for row in json.loads(line.removeprefix("__ROWS__"))}


def _sent(output: str) -> list[dict[str, str]]:
    line = next((ln for ln in output.splitlines() if ln.startswith("__SENT__")), None)
    assert line is not None, f"no request log was printed:\n{output[-3000:]}"
    return list(json.loads(line.removeprefix("__SENT__")))


# --------------------------------------------------------------------------
# The helper on its own.
# --------------------------------------------------------------------------
FIXTURE = "field.probe.fixture-thing"
DEPENDENTS = ["field.probe.dependent-one", "field.probe.dependent-two"]
BYSTANDER = "field.probe.bystander"


DATE_TIME_DECLARED = "{ TypeAsString: 'DateTime', DisplayFormat: 1 }"


def _run_helper(
    read: str, declared: str = DATE_TIME_DECLARED,
) -> tuple[bool, dict[str, dict[str, str]]]:
    """Call establishFixture once, with `read` as the body of its read function."""
    harness = _load_renderer()._env().get_template("_probe_harness.js.j2").render()
    script = (
        WINDOW
        + "(async () => {\n"
        + harness
        + f"  expect('{FIXTURE}', 'the thing holds');\n"
        + f"  expect('{DEPENDENTS[0]}', 'question one');\n"
        + f"  expect('{DEPENDENTS[1]}', 'question two');\n"
        + f"  expect('{BYSTANDER}', 'a question that does not rest on the thing');\n"
        + f"  const held = await establishFixture('{FIXTURE}', async () => {{ {read} }},\n"
        + f"    {declared}, {json.dumps(DEPENDENTS)});\n"
        + "  console.log('__HELD__' + JSON.stringify(held));\n"
        + "  console.log('__ROWS__' + JSON.stringify(RESULTS));\n"
        + "})();\n"
    )
    output = run_node(script)
    held_line = next(ln for ln in output.splitlines() if ln.startswith("__HELD__"))
    return json.loads(held_line.removeprefix("__HELD__")), _rows(output)


def _assert_voided(rows: dict[str, dict[str, str]], named: str) -> None:
    fixture = rows[FIXTURE]
    assert fixture["outcome"] == "FAIL", fixture
    assert named in fixture["evidence"], fixture
    for dependent in DEPENDENTS:
        row = rows[dependent]
        assert row["state"] == "void", row
        assert FIXTURE in row["evidence"], row
        assert named in row["evidence"], row
        assert row["question"].startswith("question"), row
    assert rows[BYSTANDER]["state"] == "open", rows[BYSTANDER]


def test_a_fixture_that_reads_back_as_declared_passes_and_voids_nothing() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { TypeAsString: 'DateTime', DisplayFormat: 1 } };")

    assert held is True
    assert rows[FIXTURE]["outcome"] == "PASS"
    assert "DisplayFormat=1" in rows[FIXTURE]["evidence"]
    assert [row["state"] for row in rows.values()] == ["settled", "open", "open", "open"]


def test_a_predicate_decides_a_declared_property() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { ValidationFormula: 'DM<=Modified' } };",
        "{ ValidationFormula: (v) => String(v).replace(/[[\\]]/g, '') === 'DM<=Modified' }",
    )

    assert held is True
    assert rows[FIXTURE]["outcome"] == "PASS"


def test_a_property_that_differs_voids_the_dependents() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { TypeAsString: 'DateTime', DisplayFormat: 0 } };")

    assert held is False
    _assert_voided(rows, "DisplayFormat differs: read 0, declared 1")


def test_a_predicate_that_fails_is_a_difference() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { ItemCount: 4000 } };",
        "{ ItemCount: (n) => n >= 5001 }",
    )

    assert held is False
    _assert_voided(rows, "ItemCount differs: read 4000, declared by a predicate it fails")


def test_a_property_absent_from_the_payload_voids_the_dependents() -> None:
    held, rows = _run_helper(
        "return { ok: true, status: 200, body: { TypeAsString: 'DateTime' } };")

    assert held is False
    _assert_voided(rows, "DisplayFormat is absent from the payload")


@pytest.mark.parametrize(
    ("status", "named"),
    [
        (404, "the read was refused (HTTP 404)"),
        (500, "the read was refused (HTTP 500)"),
        (403, "the read was not authorised (HTTP 403)"),
        (408, "the read timed out (HTTP 408)"),
    ],
)
def test_a_read_that_did_not_answer_voids_the_dependents(status: int, named: str) -> None:
    # The error payload carries both declared names, so only the status can refuse it.
    held, rows = _run_helper(
        f"return {{ ok: false, status: {status}, "
        "body: { TypeAsString: 'DateTime', DisplayFormat: 1 } };")

    assert held is False
    _assert_voided(rows, named)


@pytest.mark.parametrize("status", [429, 503])
def test_a_throttled_read_voids_the_dependents(status: int) -> None:
    held, rows = _run_helper(
        f"return {{ ok: false, status: {status}, "
        "body: { TypeAsString: 'DateTime', DisplayFormat: 1 } };")

    assert held is False
    _assert_voided(rows, f"the read was throttled (HTTP {status})")


def test_a_read_that_throws_voids_the_dependents() -> None:
    held, rows = _run_helper("throw new Error('Failed to fetch');")

    assert held is False
    _assert_voided(rows, "the read threw: Failed to fetch")


def test_a_2xx_with_no_payload_voids_the_dependents() -> None:
    held, rows = _run_helper("return { ok: true, status: 200, body: null };")

    assert held is False
    _assert_voided(rows, "the read answered HTTP 200 with no payload")


# --------------------------------------------------------------------------
# The probes fixed on it. Each probe runs as an operator pastes it, with its
# write gates opened and its result table dumped from report().
# --------------------------------------------------------------------------
def _probe_js(name: str, gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES")) -> str:
    js = (MANUAL / name).read_text(encoding="utf-8")
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


def _run_probe(
    mock: str,
    config: dict[str, Any],
    name: str,
    gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"),
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    script = (
        WINDOW + _RESPONSES + mock.replace("__CONFIG__", json.dumps(config))
        + "\n" + _probe_js(name, gates)
    )
    output = run_node(script)
    return _rows(output), _sent(output)


def _void_ids(rows: dict[str, dict[str, str]]) -> set[str]:
    return {row_id for row_id, row in rows.items() if row["state"] == "void"}


def _catalogued_dependents(probe: str, fixture: str) -> set[str]:
    """The findings probe-catalog.json says `fixture` gates, so runtime and catalogue agree."""
    catalog = json.loads((MANUAL / "probe-catalog.json").read_text(encoding="utf-8"))
    [entry] = [p for p in catalog["probes"] if p["file"] == probe]
    return {finding["id"] for scenario in entry["scenarios"] for finding in scenario["findings"]
            if fixture in finding["depends_on"]}


#: The scratch list the today-semantics probe leaves, with the columns the two
#: clock probes reuse by Title. A field is served whole, as a GET with no
#: $select is on a live site.
_SCRATCH_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const fields = new Map(Object.entries(CONFIG.fields));
    let listFormula = '';
    let nextItem = 1;
    const items = new Map();
    const FIELD = /\\/fields\\/getby(?:internalnameortitle|title)\\('([^']+)'\\)/;
    const ITEM = /\\/items\\((\\d+)\\)/;

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const sent = opts.body === undefined ? {} : JSON.parse(String(opts.body));
      const path = decodeURIComponent(u.split('/_api/')[1] || '');
      SENT.push({ verb, path, body: opts.body === undefined ? '' : String(opts.body) });

      if (path.startsWith('contextinfo')) {
        return digestResponse();
      }
      if (path.startsWith('web/regionalsettings/timezone')) {
        return jsonResponse(200, { Description: '(UTC) Coordinated Universal Time' });
      }
      const named = FIELD.exec(path);
      if (named) {
        const held = fields.get(named[1]);
        if (!held) return noSuchField();
        if (verb === 'MERGE') {
          if ('ValidationFormula' in sent) held.ValidationFormula = sent.ValidationFormula;
          return jsonResponse(204, {});
        }
        if (CONFIG.fieldReadStatus) return jsonResponse(CONFIG.fieldReadStatus, { error: 'no' });
        return jsonResponse(200, {
          InternalName: named[1], Title: named[1], FieldTypeKind: 4, ...held });
      }
      if (path.includes('/fields')) {
        if (method === 'POST') {
          fields.set(sent.Title, {
            TypeAsString: 'DateTime', DisplayFormat: sent.DisplayFormat,
            ValidationFormula: '', Required: false, DefaultValue: null, DefaultFormula: null,
            ReadOnlyField: false,
          });
          return jsonResponse(201, { d: { Title: sent.Title, TypeAsString: 'DateTime' } });
        }
        return jsonResponse(200, { value: [...fields.keys()].map((title) => ({ Title: title })) });
      }
      const item = ITEM.exec(path);
      if (item) {
        const id = Number(item[1]);
        if (verb === 'MERGE') {
          Object.assign(items.get(id), sent, { Modified: '2026-09-24T09:00:10Z' });
          return jsonResponse(204, {});
        }
        if (CONFIG.itemReadStatus) return jsonResponse(CONFIG.itemReadStatus, { error: 'no' });
        return jsonResponse(200, items.get(id));
      }
      if (path.includes('/items')) {
        const id = nextItem;
        nextItem += 1;
        const row = { Id: id, Title: sent.Title, DM: null, DC: null, WM: null,
                      Created: '2026-09-24T09:00:00Z', Modified: '2026-09-24T09:00:00Z' };
        for (const name of ['DM', 'DC', 'WM']) if (name in sent) row[name] = sent[name];
        items.set(id, row);
        return jsonResponse(201, { d: { Id: id, Title: sent.Title } });
      }
      if (verb === 'MERGE') {
        listFormula = sent.ValidationFormula;
        return jsonResponse(204, {});
      }
      return jsonResponse(200, {
        Id: 'list-1', ListItemEntityTypeFullName: 'SP.Data.ScratchListItem',
        ValidationFormula: listFormula,
      });
    };
""")

_DATE = {"TypeAsString": "DateTime", "DisplayFormat": 0, "ValidationFormula": "",
         "Required": False, "DefaultValue": None, "DefaultFormula": None,
         "ReadOnlyField": False}
_DATE_TIME = {**_DATE, "DisplayFormat": 1}
_SCRATCH_COLUMNS = {"DM": _DATE, "DC": _DATE, "WM": _DATE_TIME}

_COLUMN_DM = ("formula.validation.column-modified-allows-yesterday",
              "formula.validation.column-modified-allows-today",
              "formula.validation.column-modified-rejects-tomorrow")
_COLUMN_ALL = {*_COLUMN_DM,
               "formula.validation.column-created-allows-today",
               "formula.validation.column-created-rejects-tomorrow",
               "formula.validation.column-modified-allows-hour-ago",
               "formula.validation.column-modified-rejects-hour-ahead",
               "formula.validation.column-modified-update-sees-own-save"}
_FIXTURE_DM = "formula.validation.fixture-dm-date-only-column"
_FIXTURE_WM = "formula.validation.fixture-wm-date-time-column"


def _item_writes(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if r["verb"] == "POST" and r["path"].endswith("/items")]


@pytest.mark.parametrize("columns", [{}, _SCRATCH_COLUMNS], ids=["created", "reused"])
def test_modified_clock_measures_on_date_columns_it_read_back(columns: dict[str, Any]) -> None:
    """The control: created or reused, columns of the declared shape void nothing."""
    rows, sent = _run_probe(_SCRATCH_MOCK, {"fields": columns}, "modified-clock-probe.js")

    for fixture in (_FIXTURE_DM, "formula.validation.fixture-dc-date-only-column", _FIXTURE_WM):
        assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    assert rows["formula.validation.column-rule-cross-column-accepted"]["outcome"] == "ACCEPTED"
    assert rows[_COLUMN_DM[0]]["outcome"] == "SAVED"
    assert not _void_ids(rows)
    assert _item_writes(sent)


def test_modified_clock_voids_the_rows_on_a_reused_column_of_the_wrong_shape() -> None:
    """DM left by an earlier run as date and time: its midnight rows would measure an instant."""
    columns = {**_SCRATCH_COLUMNS, "DM": _DATE_TIME}
    rows, sent = _run_probe(_SCRATCH_MOCK, {"fields": columns}, "modified-clock-probe.js")

    fixture = rows[_FIXTURE_DM]
    assert fixture["outcome"] == "FAIL", fixture
    assert "DisplayFormat differs: read 1, declared 0" in fixture["evidence"]
    # One shared rule covers all three columns, so every row is blocked, not only DM's.
    assert _void_ids(rows) == {"formula.validation.column-rule-cross-column-accepted", *_COLUMN_ALL}
    assert _void_ids(rows) == _catalogued_dependents("modified-clock-probe.js", _FIXTURE_DM)
    assert all(_FIXTURE_DM in rows[row_id]["evidence"] for row_id in _COLUMN_ALL)
    assert not _item_writes(sent)
    assert not [r for r in sent if r["verb"] == "MERGE"]


def test_modified_clock_voids_the_rows_on_a_column_renamed_to_a_probe_title() -> None:
    """Payloads name DM as an internal name, so a field only titled DM is the wrong fixture."""
    columns = {**_SCRATCH_COLUMNS, "DM": {**_DATE, "InternalName": "OldName"}}
    rows, sent = _run_probe(_SCRATCH_MOCK, {"fields": columns}, "modified-clock-probe.js")

    assert rows[_FIXTURE_DM]["outcome"] == "FAIL"
    assert 'InternalName differs: read "OldName", declared "DM"' in rows[_FIXTURE_DM]["evidence"]
    assert _void_ids(rows) == {"formula.validation.column-rule-cross-column-accepted", *_COLUMN_ALL}
    assert not _item_writes(sent)


_LIST_DM = ("formula.validation.list-modified-allows-yesterday",
            "formula.validation.list-modified-allows-today",
            "formula.validation.list-modified-rejects-tomorrow",
            "formula.validation.control-list-modified-rejects-thirty-days")
_LIST_RULE = ("formula.validation.list-modified-rule-accepted",
              "formula.validation.list-modified-rule-readback")
_LIST_UPDATE = ("formula.validation.list-modified-update-sees-own-save",
                "formula.validation.control-list-modified-update-rejects-hour-ahead")
_SEED = "formula.validation.fixture-update-seed-created"
_LIST_ALL = {*_LIST_RULE, *_LIST_DM, *_LIST_UPDATE, _SEED,
             "formula.validation.list-created-allows-today",
             "formula.validation.list-created-rejects-tomorrow",
             "formula.validation.list-modified-allows-20h-ago",
             "formula.validation.list-modified-allows-hour-ago",
             "formula.validation.list-modified-rejects-hour-ahead",
             "formula.validation.list-modified-rejects-20h-ahead"}


@pytest.mark.parametrize(
    "shape",
    [{"Required": True}, {"DefaultValue": "[today]"}, {"DefaultFormula": "=TODAY()"},
     {"ReadOnlyField": True}],
    ids=["required", "defaulted", "formula-defaulted", "read-only"],
)
def test_modified_clock_voids_the_rows_on_a_reused_column_that_is_not_optional(
    shape: dict[str, Any],
) -> None:
    """Each save names one column, so a required or defaulted other column skews every row."""
    columns = {**_SCRATCH_COLUMNS, "DC": {**_DATE, **shape}}
    rows, sent = _run_probe(_SCRATCH_MOCK, {"fields": columns}, "modified-clock-probe.js")

    fixture = rows["formula.validation.fixture-dc-date-only-column"]
    assert fixture["outcome"] == "FAIL", fixture
    assert _void_ids(rows) == {"formula.validation.column-rule-cross-column-accepted", *_COLUMN_ALL}
    assert _void_ids(rows) == _catalogued_dependents(
        "modified-clock-probe.js", "formula.validation.fixture-dc-date-only-column")
    assert not _item_writes(sent)


def test_list_modified_clock_measures_on_date_columns_it_read_back() -> None:
    rows, sent = _run_probe(_SCRATCH_MOCK, {"fields": _SCRATCH_COLUMNS},
                            "list-modified-clock-probe.js")

    assert rows[_FIXTURE_DM]["outcome"] == "PASS", rows[_FIXTURE_DM]
    assert rows[_SEED]["outcome"] == "PASS", rows[_SEED]
    assert rows[_LIST_RULE[0]]["outcome"] == "ACCEPTED"
    assert rows[_LIST_UPDATE[0]]["outcome"] == "SAVED"
    assert not _void_ids(rows)
    assert _item_writes(sent)


def test_list_modified_clock_voids_the_rows_on_a_reused_column_of_the_wrong_shape() -> None:
    columns = {**_SCRATCH_COLUMNS, "DM": {**_DATE, "TypeAsString": "Text"}}
    rows, sent = _run_probe(_SCRATCH_MOCK, {"fields": columns}, "list-modified-clock-probe.js")

    assert rows[_FIXTURE_DM]["outcome"] == "FAIL"
    assert "TypeAsString differs" in rows[_FIXTURE_DM]["evidence"]
    assert _void_ids(rows) == _LIST_ALL
    assert _void_ids(rows) == _catalogued_dependents("list-modified-clock-probe.js", _FIXTURE_DM)
    assert not _item_writes(sent)
    assert not [r for r in sent if r["verb"] == "MERGE"]


def test_list_modified_clock_voids_the_update_rows_when_the_seed_does_not_read_back() -> None:
    """`fixture-update-seed-created` was a literal 'PASS' off the create's status."""
    rows, _ = _run_probe(_SCRATCH_MOCK, {"fields": _SCRATCH_COLUMNS, "itemReadStatus": 429},
                         "list-modified-clock-probe.js")

    assert rows[_SEED]["outcome"] == "FAIL", rows[_SEED]
    assert "throttled (HTTP 429)" in rows[_SEED]["evidence"]
    assert _void_ids(rows) == set(_LIST_UPDATE)
    assert rows["formula.validation.fixture-list-rule-cleared"]["outcome"] == "PASS"


#: The datetime-sentinel probe's list, answering every call the probe sends.
#: Saves are accepted and CAML answers every row, which a live site can do.
_SENTINEL_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const fields = new Map(Object.entries(CONFIG.fields));
    const items = new Map();
    const views = new Map();
    let nextItem = 1;
    const FIELD = /\\/fields\\/getbyinternalnameortitle\\('([^']+)'\\)/;
    const VIEW = /\\/views\\/getbytitle\\('([^']+)'\\)/;
    const ITEM = /\\/items\\((\\d+)\\)/;

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const sent = raw ? JSON.parse(raw) : {};
      const path = decodeURIComponent(u.split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });

      if (path.startsWith('contextinfo')) {
        return digestResponse();
      }
      if (path.startsWith('web/RegionalSettings/TimeZone')) {
        return jsonResponse(200, { Description: '(UTC) Coordinated Universal Time',
          Information: { Bias: 0, StandardBias: 0, DaylightBias: 0 } });
      }
      if (path.endsWith('/fields/createfieldasxml')) {
        const xml = sent.parameters.SchemaXml;
        const name = /Name="([^"]+)"/.exec(xml)[1];
        const type = /Type="([^"]+)"/.exec(xml)[1];
        fields.set(name, { TypeAsString: type, ReadOnlyField: false,
          DisplayFormat: /Format="DateTime"/.test(xml) ? 1 : 0, ValidationFormula: '' });
        return jsonResponse(201, { Id: `field-${name}`, InternalName: name });
      }
      const named = FIELD.exec(path);
      if (named) {
        const held = fields.get(named[1]);
        if (!held) return noSuchField();
        if (verb === 'MERGE') {
          if (String(sent.ValidationFormula || '').includes('NoSuchColumnHere')) {
            return jsonResponse(500, { 'odata.error': { message: {
              value: 'The formula refers to a column that does not exist.' } } });
          }
          Object.assign(held, sent);
          return jsonResponse(204, {});
        }
        return jsonResponse(200, { InternalName: named[1], Title: named[1], ...held });
      }
      const view = VIEW.exec(path);
      if (view) {
        if (path.includes('/viewfields/addviewfield')) return jsonResponse(200, {});
        return jsonResponse(200, { Title: view[1], ViewQuery: views.get(view[1]) });
      }
      if (path.endsWith('/views')) {
        views.set(sent.Title, sent.ViewQuery);
        return jsonResponse(201, { Title: sent.Title });
      }
      if (path.endsWith('/getitems')) {
        const results = [...items.values()].map((row) => ({ Title: row.Title }));
        return jsonResponse(200, { d: { results } });
      }
      const item = ITEM.exec(path);
      if (item) {
        items.delete(Number(item[1]));
        return jsonResponse(200, {});
      }
      if (path.endsWith('/items')) {
        const id = nextItem;
        nextItem += 1;
        items.set(id, { Id: id, ...sent });
        return jsonResponse(201, { Id: id, ...sent });
      }
      return jsonResponse(200, { Id: 'list-1', Title: 'dbmlsp Probe DateTimeSentinel' });
    };
""")

_PROBE_WHEN = "formula.datetime.fixture-probewhen-date-time-column"
_TIME_OF_DAY = {
    "formula.datetime.now-function-accepted",
    "formula.datetime.now-function-rejects-future",
    "formula.datetime.control-now-function-allows-past",
    "formula.datetime.today-rejects-earlier-today",
    "formula.datetime.control-today-allows-yesterday",
    "formula.datetime.today-plus-one-allows-later-today",
    "formula.datetime.today-plus-one-rejects-two-days-out",
    "formula.datetime.today-plus-one-ceiling-tomorrow-night",
    "query.caml.control-real-element-selects",
    "query.caml.bogus-element-accepted",
    "query.caml-adhoc.now-element-inert",
    "query.view-query.now-element-roundtrip",
    "query.caml-adhoc.now-element-discriminates",
    "query.caml-adhoc.now-element-include-time-discriminates",
    "query.caml-adhoc.today-element-include-time-discriminates",
    "query.caml-adhoc.today-element-date-granular",
    "query.view-query.today-include-time-roundtrip",
    "query.view-query.today-include-time-selects",
    "expression.client-validation.now-sentinel-stored",
}


@pytest.mark.parametrize(
    "fields",
    [{}, {"ProbeWhen": {"TypeAsString": "DateTime", "DisplayFormat": 1, "ValidationFormula": "",
                        "ReadOnlyField": False}}],
    ids=["created", "reused"],
)
def test_datetime_sentinel_measures_on_a_date_time_column_it_read_back(
    fields: dict[str, Any],
) -> None:
    rows, sent = _run_probe(_SENTINEL_MOCK, {"fields": fields}, "datetime-sentinel-probe.js")

    assert rows[_PROBE_WHEN]["outcome"] == "PASS", rows[_PROBE_WHEN]
    assert rows["formula.datetime.now-function-accepted"]["outcome"] == "ACCEPTED"
    assert not _void_ids(rows)
    assert _item_writes(sent)


def test_datetime_sentinel_voids_on_a_column_renamed_to_probe_when() -> None:
    """Saves and CAML name ProbeWhen as an internal name, which a title match does not prove."""
    fields = {"ProbeWhen": {
        "InternalName": "Renamed", "TypeAsString": "DateTime", "DisplayFormat": 1,
        "ValidationFormula": "", "ReadOnlyField": False,
    }}
    rows, _ = _run_probe(_SENTINEL_MOCK, {"fields": fields}, "datetime-sentinel-probe.js")

    assert rows[_PROBE_WHEN]["outcome"] == "FAIL", rows[_PROBE_WHEN]
    assert "InternalName differs" in rows[_PROBE_WHEN]["evidence"]
    assert _void_ids(rows) == _TIME_OF_DAY
    assert _void_ids(rows) == _catalogued_dependents("datetime-sentinel-probe.js", _PROBE_WHEN)


def test_datetime_sentinel_voids_the_time_of_day_rows_on_a_reused_date_only_column() -> None:
    """A reused ProbeWhen with no time portion makes every time-of-day row vacuous."""
    fields = {"ProbeWhen": {
        "TypeAsString": "DateTime", "DisplayFormat": 0, "ValidationFormula": "",
        "ReadOnlyField": False,
    }}
    rows, sent = _run_probe(_SENTINEL_MOCK, {"fields": fields}, "datetime-sentinel-probe.js")

    fixture = rows[_PROBE_WHEN]
    assert fixture["outcome"] == "FAIL", fixture
    assert "DisplayFormat differs: read 0, declared 1" in fixture["evidence"]
    assert _void_ids(rows) == _TIME_OF_DAY
    assert all(_PROBE_WHEN in rows[row_id]["evidence"] for row_id in _TIME_OF_DAY)
    probe_when_saves = [r for r in _item_writes(sent) if "ProbeWhen" in r["body"]]
    assert probe_when_saves == []
    assert not [r for r in sent if r["path"].endswith("/getitems") or r["path"].endswith("/views")]
    # The rows that do not rest on ProbeWhen's time of day still answer.
    assert rows["formula.validation.doubled-quote-literal-accepted"]["outcome"] == "ACCEPTED"


#: Two document libraries, the fixture and the small shape control. The big
#: one refuses every filter but Id with the threshold error a live run gave.
_THRESHOLD_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const BIG = 'dbmlsp Probe LibIdxThreshold';
    const SMALL = 'dbmlsp Probe LibIdxThreshold Small';
    const target = {
      [BIG]: { Id: 1, Title: null, Created: '2026-09-20T01:00:00Z',
               Modified: '2026-09-20T01:00:00Z', AuthorId: 11, EditorId: 11,
               TidxUnindexedText: null, TidxUnindexedPersonId: null },
      [SMALL]: { Id: 1, Title: null, Created: '2026-09-20T02:00:00Z',
                 Modified: '2026-09-20T02:00:00Z', AuthorId: 11, EditorId: 11,
                 TidxUnindexedText: null, TidxUnindexedPersonId: null },
    };
    const LIB = /web\\/lists\\/getbytitle\\('([^']+)'\\)/;
    const refusedThreshold = () => jsonResponse(500, { 'odata.error': {
      code: '-2147024860, Microsoft.SharePoint.SPQueryThrottledException',
      message: { lang: 'en-US', value: 'The attempted operation is prohibited because it '
        + 'exceeds the list view threshold.' } } });

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const path = decodeURIComponent(u.split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });

      if (path.startsWith('contextinfo')) {
        return digestResponse();
      }
      if (path.includes('/Files/add(')) return jsonResponse(200, { Name: 'uploaded' });
      if (path.startsWith('web/GetFileByServerRelativeUrl')) {
        const lib = path.includes('/LibIdxThresholdSmall/') ? SMALL : BIG;
        return jsonResponse(200, target[lib]);
      }
      const lib = LIB.exec(path);
      if (!lib) return jsonResponse(404, { 'odata.error': { message: { value: 'unexpected' } } });
      const title = lib[1];
      const rest = path.slice(lib.index + lib[0].length);
      if (rest.startsWith('/fields/getbyinternalnameortitle')) {
        return jsonResponse(200, { InternalName: 'probe', TypeAsString: 'Text',
                                   Indexed: false, AutoIndexed: false });
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: title === BIG
          ? '/sites/test/LibIdxThreshold' : '/sites/test/LibIdxThresholdSmall' });
      }
      if (rest.startsWith('/items(')) {
        Object.assign(target[title], JSON.parse(raw));
        return jsonResponse(204, {});
      }
      if (rest.startsWith('/items')) {
        if (rest.includes('$orderby=Id desc')) {
          if (CONFIG.resumeStatus) return throttled();
          const newest = title === BIG ? CONFIG.newestBig : 6;
          return jsonResponse(200, { value: [
            { Id: newest, FileLeafRef: `dbmlsp-tidx-${String(newest).padStart(5, '0')}.txt` }] });
        }
        const filter = /\\$filter=(.*)$/.exec(rest);
        if (!filter) {
          return jsonResponse(200, { value: [1, 2, 3, 4, 5, 6].map((Id) => ({ Id })) });
        }
        if (title === BIG && !filter[1].startsWith('Id eq')) return refusedThreshold();
        return jsonResponse(200, { value: / eq 0$/.test(filter[1]) ? [] : [{ Id: 1 }] });
      }
      if (rest.startsWith('?$select=ItemCount')) {
        if (CONFIG.countThrows) throw new TypeError('Failed to fetch');
        if (CONFIG.countStatus) return throttled();
        return jsonResponse(200, { ItemCount: CONFIG.itemCount });
      }
      return jsonResponse(200, { Id: `list-${title}`, Title: title, BaseTemplate: 101 });
    };
""")

_THRESHOLD_HEALTHY: dict[str, Any] = {
    "itemCount": 5001, "newestBig": 5001, "countStatus": None, "resumeStatus": None,
}
_COUNT = "library.index.fixture-file-count"
_COUNT_DEPENDENTS = {
    "library.index.fixture-target-seeded",
    "library.index.control-small-library-shapes",
    "library.index.control-threshold-id-served",
    "library.index.control-unindexed-refused",
    "library.index.control-unindexed-person-refused",
    "library.index.threshold-filter-title",
    "library.index.threshold-filter-name",
    "library.index.threshold-filter-created",
    "library.index.threshold-filter-modified",
    "library.index.threshold-filter-author",
    "library.index.threshold-filter-editor",
}
_BUILD = ("CONFIRMED", "ALLOW_WRITES", "BUILD_FIXTURE")


def _filters(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    return [r for r in sent if "$filter=" in r["path"]]


@pytest.mark.parametrize("gates", [("CONFIRMED", "ALLOW_WRITES"), _BUILD], ids=["measure", "build"])
def test_threshold_measures_on_a_count_it_read(gates: tuple[str, ...]) -> None:
    rows, sent = _run_probe(_THRESHOLD_MOCK, _THRESHOLD_HEALTHY,
                            "library-index-threshold-probe.js", gates)

    assert rows[_COUNT]["outcome"] == "PASS", rows[_COUNT]
    assert "ItemCount=5001" in rows[_COUNT]["evidence"]
    assert rows["library.index.control-threshold-id-served"]["outcome"].startswith("SERVED")
    assert rows["library.index.threshold-filter-title"]["outcome"] == "REFUSED (threshold)"
    assert not _void_ids(rows)
    assert _filters(sent)


def test_threshold_counts_from_item_count_not_from_the_newest_file_name() -> None:
    """The newest file reads 05001, but only a read count says 5,001 files are there."""
    rows, sent = _run_probe(_THRESHOLD_MOCK, {**_THRESHOLD_HEALTHY, "itemCount": 4000},
                            "library-index-threshold-probe.js", _BUILD)

    assert rows[_COUNT]["outcome"] == "SHORT", rows[_COUNT]
    assert "ItemCount reads 4000" in rows[_COUNT]["evidence"]
    assert not _filters(sent)


def test_threshold_voids_the_rows_when_the_count_read_is_throttled() -> None:
    rows, sent = _run_probe(_THRESHOLD_MOCK, {**_THRESHOLD_HEALTHY, "countStatus": 429},
                            "library-index-threshold-probe.js")

    assert rows[_COUNT]["outcome"] == "FAIL", rows[_COUNT]
    assert "the read was throttled (HTTP 429)" in rows[_COUNT]["evidence"]
    assert _void_ids(rows) == _COUNT_DEPENDENTS
    assert not _filters(sent)


def test_threshold_voids_the_rows_when_the_resume_read_is_throttled() -> None:
    """A throttled resume read used to fall back as if the library held nothing past it."""
    rows, sent = _run_probe(_THRESHOLD_MOCK, {**_THRESHOLD_HEALTHY, "resumeStatus": 429},
                            "library-index-threshold-probe.js", _BUILD)

    assert rows[_COUNT]["outcome"] == "FAIL", rows[_COUNT]
    assert "the resume read was throttled (HTTP 429)" in rows[_COUNT]["evidence"]
    assert _void_ids(rows) == _COUNT_DEPENDENTS
    assert not [r for r in sent if "/Files/add(" in r["path"]]
    assert not _filters(sent)


#: Libraries by title. A generic list reused under a library's title is the
#: shape the fixture must refuse; folders are accepted and read back.
_FOLDER_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const lists = new Map(Object.entries(CONFIG.lists));
    const folders = new Set();
    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(\\/RootFolder)?/;
    const ADD = /GetFolderByServerRelativeUrl\\('([^']+)'\\)\\/folders\\/add\\(url='([^']+)'\\)/;
    const PATH = /Folders\\/AddUsingPath\\(decodedurl='([^']+)'\\)/;
    const READ = /GetFolderByServerRelativeUrl\\('([^']+)'\\)\\?/;

    globalThis.fetch = async (url, opts = {}) => {
      const method = opts.method || 'GET';
      const raw = opts.body === undefined ? '' : String(opts.body);
      const sent = raw ? JSON.parse(raw) : {};
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      SENT.push({ verb: method, path, body: raw });

      if (path.startsWith('contextinfo')) return digestResponse();
      if (path === 'web/lists' && method === 'POST') {
        lists.set(sent.Title, { BaseTemplate: sent.BaseTemplate,
          ContentTypesEnabled: sent.ContentTypesEnabled !== false, EnableFolderCreation: true });
        return jsonResponse(201, { Title: sent.Title });
      }
      const add = ADD.exec(path);
      if (add) { folders.add(`${add[1]}/${add[2]}`); return jsonResponse(200, { Exists: true }); }
      const made = PATH.exec(path);
      if (made) { folders.add(made[1]); return jsonResponse(200, { Exists: true }); }
      const read = READ.exec(path);
      if (read) {
        return jsonResponse(200, { Exists: folders.has(read[1]), Name: read[1],
          ServerRelativeUrl: read[1] });
      }
      if (CONFIG.shapeThrows && path.includes('$select=BaseTemplate')) {
        throw new TypeError('Failed to fetch');
      }
      const list = LIST.exec(path);
      if (list) {
        const held = lists.get(list[1]);
        if (!held) return jsonResponse(404, { error: 'List does not exist.' });
        if (list[2]) return jsonResponse(200, { ServerRelativeUrl: `/sites/s/${list[1]}` });
        return jsonResponse(200, { Title: list[1], ...held });
      }
      return jsonResponse(404, { error: `unmocked ${path}` });
    };
""")

_LIBRARY = "library.doc-lib.fixture-library-created"
_FOLDER_ROWS = {
    "library.folder.control-plain-name-default-library",
    "library.folder.spaced-name-default-library",
    "library.folder.plain-name-content-types-disabled",
    "library.folder.spaced-name-content-types-disabled",
    "library.folder.add-using-path-spaced-name",
}
_DEFAULT_LIB = "dbmlsp Probe Folder Default"
_NOCT_LIB = "dbmlsp Probe Folder NoCT"


@pytest.mark.parametrize("lists", [
    {},
    {_DEFAULT_LIB: {"BaseTemplate": 101, "ContentTypesEnabled": True},
     _NOCT_LIB: {"BaseTemplate": 101, "ContentTypesEnabled": False}},
], ids=["created", "reused"])
def test_folder_create_refusal_measures_on_libraries_it_read_back(
    lists: dict[str, Any],
) -> None:
    rows, _ = _run_probe(_FOLDER_MOCK, {"lists": lists}, "folder-create-refusal-probe.js")

    assert rows[_LIBRARY]["outcome"] == "PASS", rows[_LIBRARY]
    assert rows["library.folder.control-plain-name-default-library"]["outcome"] == "PASS"
    assert not _void_ids(rows)


@pytest.mark.parametrize("lists", [
    {_DEFAULT_LIB: {"BaseTemplate": 100, "ContentTypesEnabled": False},
     _NOCT_LIB: {"BaseTemplate": 101, "ContentTypesEnabled": False}},
    {_DEFAULT_LIB: {"BaseTemplate": 101, "ContentTypesEnabled": True},
     _NOCT_LIB: {"BaseTemplate": 101, "ContentTypesEnabled": True}},
], ids=["generic-list", "content-types-on"])
def test_folder_create_refusal_voids_the_cells_on_a_reused_list_of_the_wrong_shape(
    lists: dict[str, Any],
) -> None:
    rows, sent = _run_probe(_FOLDER_MOCK, {"lists": lists}, "folder-create-refusal-probe.js")

    assert rows[_LIBRARY]["outcome"] == "FAIL", rows[_LIBRARY]
    assert "differs" in rows[_LIBRARY]["evidence"]
    assert _void_ids(rows) == _FOLDER_ROWS
    assert not [r for r in sent if "folders" in r["path"].lower()]


def test_threshold_voids_the_rows_when_the_count_read_throws() -> None:
    """A fetch that rejects is recorded by the helper, not left to end the run unrecorded."""
    rows, _ = _run_probe(_THRESHOLD_MOCK, {"countThrows": True}, "library-index-threshold-probe.js")

    fixture = rows["library.index.fixture-file-count"]
    assert fixture["outcome"] == "FAIL", fixture
    assert "the read threw" in fixture["evidence"]
    assert _void_ids(rows)


def test_folder_create_refusal_voids_the_cells_when_a_shape_read_throws() -> None:
    rows, sent = _run_probe(_FOLDER_MOCK, {"lists": {}, "shapeThrows": True},
                            "folder-create-refusal-probe.js")

    assert rows[_LIBRARY]["outcome"] == "FAIL", rows[_LIBRARY]
    assert "the read threw" in rows[_LIBRARY]["evidence"]
    assert _void_ids(rows) == _FOLDER_ROWS
    assert not [r for r in sent if "folders" in r["path"].lower()]
