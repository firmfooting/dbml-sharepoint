# test/test_deploy_builtin_title_runtime.py
"""The deploy's preflight guard on a calculated formula that names `[Created]`.

SharePoint resolves a formula's column references by display title, and
`=[Created]+14` was measured only where the built-in column is titled
`Created` (2026-09-28). The preflight reads that title and refuses any other
before the first write. Node is required; the module skips without it.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from _node import NODE
from _node import run_node as _run
from _packs import pack
from _paths import FIXTURES
from test_deploy_runtime import (
    _HARNESS,
    _deployment_writes,
    _lifted,
    _summary_of,
    _without_assessment,
)

from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js

_DBML = """
    Table Escalation {
      Id int [pk, increment]
      Title nvarchar [not null]
      DueDate calculated_date
    }
"""


def _mapping(kind: str = "DocumentLibrary", base_template: int = 101) -> str:
    return f"""
entities:
  Escalation: {{ kind: {kind}, base_template: {base_template}, site_role: default }}

calculated_formulas:
  Escalation:
    DueDate: "=[Created]+14"
"""


def _declaration(tmp_path: Path, mapping: str) -> dict[str, Any]:
    schema, bundle = pack(tmp_path, dbml=_DBML, mapping=mapping)
    declaration: dict[str, Any] = build_schema_json(
        schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
    )
    return declaration


def _deploy_js(tmp_path: Path) -> str:
    from dbml_sharepoint.model.release import load_release

    schema, bundle = pack(tmp_path, dbml=_DBML, mapping=_mapping())
    return _without_assessment(generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        resolved=resolve(schema, bundle.mapping),
    ))


def test_the_declaration_names_each_column_reading_a_builtin(tmp_path: Path) -> None:
    (library,) = _declaration(tmp_path, _mapping())["lists"]
    assert library["builtin_formula_refs"] == [
        {"builtin": "Created", "columns": ["DueDate"]},
    ]


def test_a_list_reading_no_builtin_carries_no_entry(tmp_path: Path) -> None:
    mapping = _mapping().replace('"=[Created]+14"', '"=[Title]"')
    (library,) = _declaration(tmp_path, mapping)["lists"]
    assert "builtin_formula_refs" not in library


_TITLE_STUBS = """
    const odataName = (s) => String(s).replace(/'/g, "''");
    const apiUrl = (path) => `https://example.sharepoint.com/sites/test/_api/${path}`;
    let LIST_FIELDS = new Map();
    let SITE_ANSWER = { ok: true, status: 200, d: { Title: 'Created' } };
    const listFieldShapes = async () => ({
      get: (name) => LIST_FIELDS.get(name), size: LIST_FIELDS.size, truncated: false,
    });
    const fetchWithRetry = async () => ({
      ok: SITE_ANSWER.ok, status: SITE_ANSWER.status,
      json: async () => ({ d: SITE_ANSWER.d }), text: async () => 'refused',
    });
"""

_TITLE_SCENARIOS = """
    (async () => {
      const out = {};
      LIST_FIELDS = new Map([['Created', { InternalName: 'Created', Title: 'Created' }]]);
      out.listMatches = await builtinTitleMismatch('APP_Escalation', 'Created');
      LIST_FIELDS = new Map([['Created', { InternalName: 'Created', Title: 'Erstellt' }]]);
      out.listLocalised = await builtinTitleMismatch('APP_Escalation', 'Created');
      LIST_FIELDS = new Map();
      out.listLacksIt = await builtinTitleMismatch('APP_Escalation', 'Created');
      out.siteMatches = await builtinTitleMismatch(null, 'Created');
      SITE_ANSWER = { ok: true, status: 200, d: { Title: 'Erstellt' } };
      out.siteLocalised = await builtinTitleMismatch(null, 'Created');
      SITE_ANSWER = { ok: false, status: 500, d: null };
      out.siteRefused = await builtinTitleMismatch(null, 'Created');
      console.log('__OUT__' + JSON.stringify(out));
    })();
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_only_the_measured_title_passes(tmp_path: Path) -> None:
    """A read that fails is NOT CHECKED, never a difference, and never a pass."""
    program = "\n".join([
        _TITLE_STUBS,
        _lifted(_deploy_js(tmp_path), "async function builtinTitleMismatch"),
        _TITLE_SCENARIOS,
    ])
    output = _run(program)
    line = next((ln for ln in output.splitlines() if ln.startswith("__OUT__")), None)
    assert line is not None, output
    out = json.loads(line.removeprefix("__OUT__"))

    assert out["listMatches"] is None
    assert out["siteMatches"] is None
    for key in ("listLocalised", "siteLocalised"):
        assert (out[key]["checked"], out[key]["actual"]) == (True, "Erstellt"), out[key]
    for key in ("listLacksIt", "siteRefused"):
        assert out[key]["checked"] is False, out[key]


def _run_fresh_site(tmp_path: Path, site_title: str) -> tuple[dict[str, Any], list[Any], str]:
    """Deploy the library to an empty site whose `Created` column has `site_title`."""
    harness = _HARNESS.replace(
        "const body = (url) => {\n",
        "const body = (url) => {\n"
        "  if (url.includes(\"availablefields/getbyinternalnameortitle('Created')\")) {\n"
        f"    return {{ d: {{ Title: {json.dumps(site_title)} }} }};\n"
        "  }\n",
        1,
    )
    assert harness != _HARNESS, "the site column answer was not spliced in"
    script = harness + "\n" + _deploy_js(tmp_path).replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    calls_line = next(ln for ln in output.splitlines() if ln.startswith("__CALLS__"))
    return _summary_of(output), json.loads(calls_line.removeprefix("__CALLS__")), output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_localised_created_title_stops_the_run_before_any_write(tmp_path: Path) -> None:
    summary, calls, output = _run_fresh_site(tmp_path, "Erstellt")
    assert summary.get("aborted") == "existing-schema-shape-errors", output[-3000:]
    assert not _deployment_writes(calls), _deployment_writes(calls)
    (refusal,) = [e for e in summary["errors"] if e.get("column") == "DueDate"]
    assert refusal["mismatches"][0]["actual"] == "Erstellt"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_measured_created_title_passes_the_preflight(tmp_path: Path) -> None:
    summary, calls, output = _run_fresh_site(tmp_path, "Created")
    assert any("availablefields/getbyinternalnameortitle('Created')" in c["url"] for c in calls)
    assert not [e for e in summary.get("errors") or [] if e.get("column") == "DueDate"
                and e.get("phase") == "preflight"], output[-3000:]
    assert summary.get("aborted") != "existing-schema-shape-errors", output[-3000:]
