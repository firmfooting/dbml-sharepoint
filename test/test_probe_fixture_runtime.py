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
            ValidationFormula: '', Required: false, DefaultValue: null,
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
         "Required": False, "DefaultValue": None}
_DATE_TIME = {**_DATE, "DisplayFormat": 1}
_SCRATCH_COLUMNS = {"DM": _DATE, "DC": _DATE, "WM": _DATE_TIME}

_COLUMN_DM = ("formula.validation.column-modified-allows-yesterday",
              "formula.validation.column-modified-allows-today",
              "formula.validation.column-modified-rejects-tomorrow")
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
    assert _void_ids(rows) == {"formula.validation.column-rule-cross-column-accepted", *_COLUMN_DM}
    assert all(_FIXTURE_DM in rows[row_id]["evidence"] for row_id in _COLUMN_DM)
    assert not _item_writes(sent)
    assert not [r for r in sent if r["verb"] == "MERGE"]


_LIST_DM = ("formula.validation.list-modified-allows-yesterday",
            "formula.validation.list-modified-allows-today",
            "formula.validation.list-modified-rejects-tomorrow",
            "formula.validation.control-list-modified-rejects-thirty-days")
_LIST_RULE = ("formula.validation.list-modified-rule-accepted",
              "formula.validation.list-modified-rule-readback")
_LIST_UPDATE = ("formula.validation.list-modified-update-sees-own-save",
                "formula.validation.control-list-modified-update-rejects-hour-ahead")
_SEED = "formula.validation.fixture-update-seed-created"


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
    assert _void_ids(rows) == {*_LIST_RULE, *_LIST_DM}
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
