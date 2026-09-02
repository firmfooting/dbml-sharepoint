# test/test_verifygen.py
"""verify.js.txt: each clock cell a pack uses, exercised on a scratch list.

The checks are derived from the pack's clock usage and rendered with the
same renderer and the same list-rule join the deployer uses, so what the
script writes to the scratch list is what the deploy writes to the real
lists, one column at a time.
"""
import json
import subprocess
import textwrap
from pathlib import Path
from typing import Any

import pytest
from _model import bundle as make_bundle
from _model import column
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE, run_node
from _paths import EXPECTED, FIXTURES, write_golden

from dbml_sharepoint.analysis.clock_cells import cell_for
from dbml_sharepoint.analysis.condition_rendering import to_validation
from dbml_sharepoint.analysis.list_description import VERIFY_LIST_TITLE, verify_marker
from dbml_sharepoint.analysis.save_rules import joined_list_validation
from dbml_sharepoint.generators.verifygen import generate_verify_js, verify_targets
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    ListValidation,
    MappingBundle,
    ViewDef,
)
from dbml_sharepoint.model.parser import Schema, parse_dbml
from dbml_sharepoint.model.release import load_release


def _rule(field: str, op: str, value: str) -> ColumnValidation:
    return ColumnValidation(when=Leaf(field=field, op=op, value=value), message="m")


def _clock_pack() -> tuple[Schema, MappingBundle]:
    schema = make_schema(make_table(
        "Task",
        column("Title", required=True),
        column("Due", "date"),
        column("OccurredAt", "datetime"),
        column("Raised", "date", default="[today]"),
        note="Tasks.",
    ))
    bundle = make_bundle(
        entities=["Task"],
        column_validation={"Task": EntitySection(columns={
            "Due": _rule("Due", "leq", "today"),
            "OccurredAt": _rule("OccurredAt", "leq", "now"),
        })},
        list_validation={"Task": ListValidation(
            when=Group("all_of", (Leaf(field="Due", op="leq", value="today+30"),)), message="m",
        )},
        views={"Task": [ViewDef(title="Soon", fields=["Title"], where=Group("all_of", (
            Leaf(field="Due", op="leq", value="today+7"),
        )))]},
    )
    return schema, bundle


def _checks(targets: dict) -> dict[str, dict]:  # type: ignore[type-arg]
    return {check["key"]: check for check in targets["checks"]}


def test_a_pack_without_a_clock_cell_has_nothing_to_verify() -> None:
    schema = make_schema(make_table("Task", column("Title", required=True), note="Tasks."))
    targets = verify_targets(schema, make_bundle(entities=["Task"]), "default")
    assert targets["checks"] == []
    assert targets["rule"] is None


def test_the_scratch_list_is_named_and_marked_from_the_shared_spellers() -> None:
    targets = verify_targets(*_clock_pack(), "default")
    assert targets["list_title"] == VERIFY_LIST_TITLE
    assert targets["marker"] == verify_marker()


def test_one_save_check_per_validation_cell_and_offset_with_the_cells_rendering() -> None:
    checks = _checks(verify_targets(*_clock_pack(), "default"))
    today = checks["validation_date_today"]
    assert today["cell"] == "validation/date/today"
    assert today["column"] == {"name": "VDT", "kind": "date", "display_format": 0}
    rendering = cell_for("today", "date", "validation").renderings[("leq", "today")]
    assert today["clause"] == rendering.replace("[D]", "[VDT]")
    assert [(c["id"], c["op"], c["expect"]) for c in today["cases"]] == [
        ("yesterday", "create", "save"),
        ("today", "create", "save"),
        ("tomorrow", "create", "refuse"),
        ("update-today", "update", "save"),
        ("update-tomorrow", "update", "refuse"),
    ]
    assert today["cases"][0]["value"] == {"kind": "midnight", "days": -1}
    assert today["cases"][3]["on"] == "today"

    offset = checks["validation_date_today_offset_30"]
    assert offset["column"]["name"] == "VDO30"
    assert offset["clause"] == to_validation(
        Group("all_of", (Leaf(field="VDO30", op="leq", value="today+30"),)), {"VDO30": "date"},
    )
    assert [(c["id"], c["expect"], c["value"]["days"]) for c in offset["cases"]] == [
        ("day-30", "save", 30), ("day-31", "refuse", 31), ("day-29", "save", 29),
    ]

    now = checks["validation_datetime_now"]
    assert now["column"] == {"name": "VWN", "kind": "datetime", "display_format": 1}
    assert now["clause"] == "[VWN]<=[Modified]"
    assert [(c["id"], c["op"], c["expect"], c["value"]) for c in now["cases"]] == [
        ("hour-ago", "create", "save", {"kind": "instant", "seconds": -3600}),
        ("hour-ahead", "create", "refuse", {"kind": "instant", "seconds": 3600}),
        ("update-now", "update", "save", {"kind": "instant", "seconds": -5}),
    ]


def test_the_list_rule_is_the_deployers_join_over_the_save_checks() -> None:
    """The joined shape is what the deploy writes for a real list, so the
    scratch list exercises it too. Produced by the same function, not
    re-spelled."""
    targets = verify_targets(*_clock_pack(), "default")
    save_checks = [c for c in targets["checks"] if c["kind"] == "save"]
    types = {c["column"]["name"]: c["column"]["kind"] for c in save_checks}
    joined = joined_list_validation(
        None,
        [(c["column"]["name"], ColumnValidation(when=Leaf(**c["leaf"]), message=c["message"]))
         for c in save_checks],
    )
    assert joined is not None
    assert targets["rule"]["formula"] == f"={to_validation(joined.when, types)}"
    assert targets["rule"]["message"] == joined.message
    assert targets["rule"]["formula"].startswith("=AND(OR(ISBLANK([VDT]),[VDT]<=[Modified]),")


def test_a_lagging_clock_cell_is_reported_not_judged() -> None:
    schema = make_schema(make_table(
        "Event", column("Title", required=True), column("At", "datetime"), note="Events.",
    ))
    bundle = make_bundle(
        entities=["Event"],
        column_validation={"Event": EntitySection(columns={"At": _rule("At", "leq", "today+1")})},
    )
    checks = _checks(verify_targets(schema, bundle, "default"))
    check = checks["validation_datetime_today_offset_1"]
    assert check["cell"] == "validation/datetime/today_offset"
    assert check["column"]["name"] == "VWO1"
    assert all(case["expect"] == "info" for case in check["cases"])


def test_view_windows_become_query_checks_over_rows_the_script_places() -> None:
    targets = verify_targets(*_clock_pack(), "default")
    checks = _checks(targets)
    query = checks["caml_date_today_offset_7"]
    assert query["kind"] == "query"
    assert query["field"] == "CD"
    assert query["op"] == "Eq"
    assert query["element"] == '<Value Type="DateTime"><Today OffsetDays="7"/></Value>'
    assert query["expect"] == ["cd-day-7"]
    rows = {row["id"]: row for row in targets["rows"]}
    assert rows["cd-day-7"] == {
        "id": "cd-day-7", "column": "CD", "value": {"kind": "midnight", "days": 7},
    }
    # The fixed rows around today are always placed, so a window's edges are visible.
    assert {"cd-day--1", "cd-day-0", "cd-day-1"} <= set(rows)


def test_a_today_default_and_the_formula_clock_are_checked_when_used() -> None:
    targets = verify_targets(*_clock_pack(), "default")
    checks = _checks(targets)
    assert checks["default_date"]["column"]["default_value"] == "[today]"
    assert checks["default_date"]["method"] == "today-query"
    assert checks["formula_clock_lag"]["column"] == {
        "name": "LT", "kind": "date", "display_format": 0, "default_formula": "=TODAY()",
    }
    names = [c["name"] for c in targets["columns"]]
    assert names == sorted(names) and len(names) == len(set(names))
    assert {"VDT", "VDO30", "VWN", "CD", "DD", "LT"} <= set(names)


# ---- The emitted script ----------------------------------------------------

def _simple_verify_js() -> str:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    return generate_verify_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def _clock_verify_js() -> str:
    schema, bundle = _clock_pack()
    return generate_verify_js(
        schema=schema, bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="clock.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def test_simple_verify_js_matches_golden() -> None:
    """The only byte-level check on verify.js.j2; the simple pack's view
    window is a `caml/date/today_offset` cell, so it emits a real script."""
    golden_path = EXPECTED / "simple-verify.js"
    assert golden_path.exists(), f"Golden file missing: {golden_path}"
    assert _simple_verify_js() == golden_path.read_text(encoding="utf-8"), (
        "the emitted verify script changed. Review the diff, then regenerate "
        "with `uv run python test/test_verifygen.py`."
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_verify_script_is_syntactically_valid(tmp_path: Path) -> None:
    path = tmp_path / "verify.js"
    write_golden(path, _clock_verify_js())
    assert NODE is not None
    completed = subprocess.run(  # noqa: S603
        [NODE, "--check", str(path)], capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr


# A fake site that enforces the same rule the scratch list would carry, fills
# [today] defaults, answers CAML with the same day arithmetic, and reads a
# stored formula back with its brackets stripped, as SharePoint does. Each
# `const` at the top is a knob a test flips by string replacement.
_VERIFY_HARNESS = textwrap.dedent(r"""
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test', userLoginName: 'probe@example.com',
    };
    const BROWSER_OFFSET = 0;
    const LISTS = [];
    const HIDDEN_READBACK = true;
    const ACCEPT_ALL = false;
    const LAG_DAYS = 0;
    Date.prototype.getTimezoneOffset = () => -BROWSER_OFFSET;
    const DAY = 86400000;
    const STORED = { rule: null };
    const defaults = new Map();
    const items = new Map();
    let nextId = 1;
    const respond = (status, payload) => ({
      ok: status < 400, status, headers: { get: () => null },
      json: async () => payload, text: async () => JSON.stringify(payload),
    });
    const refuse = () => respond(500, {
      error: { message: { value: 'a date is after this save' } },
    });
    const pick = (body) => Object.fromEntries(
      Object.entries(body || {}).filter(([k]) => k !== '__metadata' && k !== 'Title'),
    );
    const violates = (fields) => {
      if (ACCEPT_ALL) return false;
      const now = Date.now();
      for (const [name, value] of Object.entries(fields)) {
        if (value == null) continue;
        const t = Date.parse(value);
        if ((name === 'VDT' || name === 'VWN') && t > now) return true;
        const m = /^VDO(M?)(\d+)$/.exec(name);
        if (m && t - Number(m[2]) * (m[1] ? -1 : 1) * DAY > now) return true;
      }
      return false;
    };
    const midnight = (days) =>
      new Date(Math.floor(Date.now() / DAY) * DAY + days * DAY).toISOString();
    const fill = (fields) => {
      const out = { ...fields };
      for (const [name, spec] of defaults) {
        if (name in out) continue;
        if (spec === '[today]') out[name] = name === 'DW' ? new Date().toISOString() : midnight(0);
        if (spec === '=TODAY()') out[name] = midnight(-LAG_DAYS);
      }
      return out;
    };
    const answerQuery = (viewXml) => {
      const pattern = new RegExp(
        String.raw`<(Eq|Lt|Leq)><FieldRef Name=['"](\w+)['"]\/>`
        + String.raw`<Value Type=['"]DateTime['"]( IncludeTimeValue=['"]TRUE['"])?>`
        + String.raw`<Today( OffsetDays=['"](-?\d+)['"])?\/><\/Value><\/\1>`,
      );
      const m = pattern.exec(viewXml);
      if (!m) return [];
      const [, op, field, includeTime, , offset] = m;
      const target = includeTime ? Date.now() : Date.parse(midnight(Number(offset || 0)));
      const hits = [];
      for (const it of items.values()) {
        const value = it.fields[field];
        if (value == null) continue;
        const t = Date.parse(value);
        const same = Math.floor(t / DAY) === Math.floor(target / DAY);
        const hit = (op === 'Eq' && same) || (op === 'Lt' && t < target)
          || (op === 'Leq' && t <= target);
        if (hit) hits.push({ Title: it.Title });
      }
      return hits;
    };
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const path = u.split('?')[0];
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const body = opts.body ? JSON.parse(opts.body) : null;
      calls.push({ url: u, method, headers, body });
      if (u.includes('contextinfo')) {
        return respond(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } });
      }
      if (u.includes('regionalsettings/timezone')) {
        return respond(200, { d: {
          Description: '(UTC) Coordinated Universal Time',
          Information: { Bias: 0, StandardBias: 0, DaylightBias: 0 } } });
      }
      if (path.endsWith('/web/lists') && method === 'GET') {
        return respond(200, { d: { results: LISTS } });
      }
      if (path.endsWith('/web/lists') && method === 'POST') {
        LISTS.push({ Title: body.Title, Hidden: true, Description: body.Description });
        return respond(201, { d: { Id: 'list-guid', Title: body.Title } });
      }
      if (u.includes('$select=Hidden')) return respond(200, { d: { Hidden: HIDDEN_READBACK } });
      if (u.includes('ListItemEntityTypeFullName')) {
        return respond(200, { d: { ListItemEntityTypeFullName: 'SP.Data.VerifyListItem' } });
      }
      if (path.endsWith('/fields') && method === 'GET') return respond(200, { d: { results: [] } });
      if (path.endsWith('/fields') && method === 'POST') {
        if (body.DefaultValue) defaults.set(body.Title, body.DefaultValue);
        if (body.DefaultFormula) defaults.set(body.Title, body.DefaultFormula);
        return respond(201, { d: { Id: 'field-guid' } });
      }
      if (headers['X-HTTP-Method'] === 'MERGE' && /getbytitle\('[^']*'\)$/.test(path)) {
        STORED.rule = body.ValidationFormula;
        return respond(204, {});
      }
      if (u.includes('$select=ValidationFormula')) {
        const stored = String(STORED.rule || '').replace(/\[([A-Za-z0-9_]+)\]/g, '$1');
        return respond(200, { d: { ValidationFormula: stored } });
      }
      if (u.includes('/items?$select=Id,Title')) {
        const rows = [...items.entries()].map(([Id, it]) => ({ Id, Title: it.Title }));
        return respond(200, { d: { results: rows } });
      }
      if (path.endsWith('/getitems')) {
        return respond(200, { d: { results: answerQuery(body.query.ViewXml) } });
      }
      const recycle = /\/items\((\d+)\)\/recycle$/.exec(path);
      if (recycle) { items.delete(Number(recycle[1])); return respond(200, {}); }
      const one = /\/items\((\d+)\)$/.exec(path);
      if (one && method === 'POST') {
        const it = items.get(Number(one[1]));
        const fields = { ...it.fields, ...pick(body) };
        if (violates(fields)) return refuse();
        it.fields = fields;
        it.modified = new Date().toISOString();
        return respond(204, {});
      }
      if (one) {
        const it = items.get(Number(one[1]));
        return respond(200, { d: { Modified: it.modified, ...it.fields } });
      }
      if (path.endsWith('/items') && method === 'POST') {
        const fields = fill(pick(body));
        if (violates(fields)) return refuse();
        const id = nextId++;
        items.set(id, { Title: body.Title, fields, modified: new Date().toISOString() });
        return respond(201, { d: { Id: id } });
      }
      return respond(404, { error: { message: { value: `unmocked ${method} ${u}` } } });
    };
    globalThis.__calls = calls;
""")


def _run_verify(js: str | None = None, **knobs: str) -> dict[str, Any]:
    """Execute a verify script against the fake site; returns its summary."""
    harness = _VERIFY_HARNESS
    for name, value in knobs.items():
        marker = f"const {name} = "
        assert harness.count(marker) == 1, name
        start = harness.index(marker) + len(marker)
        end = harness.index(";", start)
        harness = harness[:start] + value + harness[end:]
    script = js if js is not None else _clock_verify_js()
    assert script.count("})();") == 1, "the IIFE terminator is no longer unique"
    wrapped = script.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = run_node(harness + "\n" + wrapped)
    line = next((ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None)
    assert line is not None, f"verify.js did not return a summary:\n{output[-3000:]}"
    summary: dict[str, Any] = json.loads(line.removeprefix("__RESULT__"))
    assert summary.get("verdict"), f"verify.js reached no verdict:\n{output[-3000:]}"
    return summary


def _levels(summary: dict[str, Any]) -> dict[str, str]:
    return {f["key"]: f["level"] for f in summary["findings"]}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_site_that_keeps_every_promise_is_verified() -> None:
    summary = _run_verify()
    levels = _levels(summary)
    assert summary["verdict"] == "VERIFIED", summary
    assert levels["scratch_list"] == "PASS"
    assert levels["list_rule"] == "PASS"
    assert levels["validation_date_today.tomorrow"] == "PASS"
    assert levels["validation_date_today.update-tomorrow"] == "PASS"
    assert levels["validation_datetime_now.hour-ahead"] == "PASS"
    assert levels["caml_date_today_offset_7"] == "PASS"
    assert levels["default_date"] == "PASS"
    assert levels["formula_clock_lag"] == "INFO"
    lag = next(f["detail"] for f in summary["findings"] if f["key"] == "formula_clock_lag")
    assert "the site's date" in lag
    assert "FAIL" not in levels.values() and "NOT-ASSESSABLE" not in levels.values()


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_site_that_accepts_tomorrow_is_a_mismatch() -> None:
    summary = _run_verify(ACCEPT_ALL="true")
    levels = _levels(summary)
    assert summary["verdict"] == "MISMATCH"
    assert levels["validation_date_today.tomorrow"] == "FAIL"
    assert levels["validation_date_today.today"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_foreign_list_of_the_same_title_stops_the_run_before_any_write() -> None:
    summary = _run_verify(
        LISTS="[{ Title: '_dbml-verify', Hidden: false, Description: 'Somebody else\\'s list.' }]",
    )
    assert summary["verdict"] == "NOT-VERIFIED"
    assert summary["aborted"] == "foreign-list"
    assert _levels(summary)["scratch_list"] == "FAIL"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_scratch_list_that_reads_back_visible_is_reported() -> None:
    summary = _run_verify(HIDDEN_READBACK="false")
    detail = next(f["detail"] for f in summary["findings"] if f["key"] == "scratch_list_hidden")
    assert "VISIBLE" in detail
    assert summary["verdict"] == "VERIFIED"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_date_cases_are_not_assessable_when_the_browser_zone_differs() -> None:
    summary = _run_verify(BROWSER_OFFSET="600")
    levels = _levels(summary)
    assert summary["verdict"] == "NOT-VERIFIED"
    assert levels["site_zone"] == "NOT-ASSESSABLE"
    assert levels["validation_date_today.today"] == "NOT-ASSESSABLE"
    assert levels["validation_datetime_now.hour-ahead"] == "PASS"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_lagging_formula_clock_is_reported_as_information() -> None:
    summary = _run_verify(LAG_DAYS="1")
    lag = next(f for f in summary["findings"] if f["key"] == "formula_clock_lag")
    assert lag["level"] == "INFO"
    assert "1 day(s) behind" in lag["detail"]
    assert summary["verdict"] == "VERIFIED"


if __name__ == "__main__":  # pragma: no cover
    # Regenerate the golden through the same helper the test uses.
    _target = EXPECTED / "simple-verify.js"
    write_golden(_target, _simple_verify_js())
    print(f"wrote {_target}")  # noqa: T201
