# test/test_deploy_builtin_title_runtime.py
"""The deploy's preflight guard on a calculated formula that names `[Created]`.

SharePoint resolves a formula's column references by display title, and
`=[Created]+14` was measured only where the built-in column is titled
`Created` (2026-09-28). The deploy reads that title from the list itself and
refuses any other: in the preflight for a list that already exists, and again
before each calculated create. Node is required; the module skips without it.
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
    _ADOPTED_HARNESS,
    _declared_deploy_js,
    _declared_list_descriptions,
    _deployment_writes,
    _field_writes,
    _lifted,
    _summary_of,
    _without_assessment,
)

from dbml_sharepoint.analysis.phases import phase_number as pn
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


def test_a_library_reading_no_builtin_carries_no_entry(tmp_path: Path) -> None:
    mapping = _mapping().replace('"=[Created]+14"', '"=[Title]"')
    (library,) = _declaration(tmp_path, mapping)["lists"]
    assert "builtin_formula_refs" not in library


_TITLE_STUBS = """
    let LIST_FIELDS = new Map();
    let ENUMERATION_FAILS = false;
    const listFieldShapes = async () => {
      if (ENUMERATION_FAILS) throw new Error('HTTP 500 refused');
      return { get: (name) => LIST_FIELDS.get(name), size: LIST_FIELDS.size, truncated: false };
    };
"""

_TITLE_SCENARIOS = """
    (async () => {
      const out = {};
      LIST_FIELDS = new Map([['Created', { InternalName: 'Created', Title: 'Created' }]]);
      out.matches = await builtinTitleMismatch('APP_Escalation', 'Created');
      LIST_FIELDS = new Map([['Created', { InternalName: 'Created', Title: 'Erstellt' }]]);
      out.localised = await builtinTitleMismatch('APP_Escalation', 'Created');
      LIST_FIELDS = new Map();
      out.lacksIt = await builtinTitleMismatch('APP_Escalation', 'Created');
      ENUMERATION_FAILS = true;
      out.unreadable = await builtinTitleMismatch('APP_Escalation', 'Created');
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

    assert out["matches"] is None
    assert (out["localised"]["checked"], out["localised"]["actual"]) == (True, "Erstellt")
    for key in ("lacksIt", "unreadable"):
        assert out[key]["checked"] is False, out[key]


# The adopted harness serves generic lists only. The generator collects a
# formula's built-ins for any kind, so the guard runs here although the
# validator would refuse this list's formula.
_FORMULA = """
    calculated_formulas:
      Escalation:
        DueDate: "=[Created]+14"
"""


def _run_adopted(
    tmp_path: Path, *, at_preflight: str, afterwards: str,
) -> tuple[dict[str, Any], list[Any], str]:
    """Deploy to an existing list whose `Created` title is `at_preflight`, then `afterwards`."""
    held = _declared_list_descriptions(tmp_path)
    created = (
        "{ Id: '22222222-2222-2222-2222-222222222222', InternalName: 'Created', "
        "TypeAsString: 'DateTime', ReadOnlyField: true, Sealed: false, "
        f"Title: mockPhase === {json.dumps(pn('preflight'))} "
        f"? {json.dumps(at_preflight)} : {json.dumps(afterwards)} }}"
    )
    harness = _ADOPTED_HARNESS.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(held.items()))});",
    ).replace(
        "return { d: { results: [titleField(listTitle), ...own] } };",
        f"return {{ d: {{ results: [titleField(listTitle), {created}, ...own] }} }};",
    )
    assert "InternalName: 'Created'" in harness, "the Created column was not spliced in"
    js = _declared_deploy_js(tmp_path, _FORMULA, extra_lines=("DueDate calculated_date",))
    script = harness + "\n" + js.replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    calls_line = next(ln for ln in output.splitlines() if ln.startswith("__CALLS__"))
    return _summary_of(output), json.loads(calls_line.removeprefix("__CALLS__")), output


def _due_date_creates(calls: list[Any]) -> list[Any]:
    return [
        c for c in _field_writes(calls)
        if c["body"] and json.loads(c["body"]).get("Title") == "DueDate"
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_existing_list_titled_otherwise_stops_before_any_write(tmp_path: Path) -> None:
    summary, calls, output = _run_adopted(
        tmp_path, at_preflight="Erstellt", afterwards="Erstellt",
    )
    assert summary.get("aborted") == "existing-schema-shape-errors", output[-3000:]
    assert not _deployment_writes(calls), _deployment_writes(calls)
    (refusal,) = [e for e in summary["errors"] if e.get("column") == "DueDate"]
    assert refusal["mismatches"][0]["actual"] == "Erstellt"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_calculated_create_is_refused_when_the_title_is_otherwise_by_then(
    tmp_path: Path,
) -> None:
    """The check a list created by this run gets, since the preflight had nothing to read."""
    summary, calls, output = _run_adopted(
        tmp_path, at_preflight="Created", afterwards="Erstellt",
    )
    assert not _due_date_creates(calls), _due_date_creates(calls)
    (refusal,) = [e for e in summary["errors"] if e.get("column") == "DueDate"]
    assert refusal["phase"] == pn("lists"), refusal
    assert "Erstellt" in refusal["error"], refusal
    assert summary.get("aborted") == "phase-1-schema-errors", output[-3000:]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_measured_title_creates_the_column(tmp_path: Path) -> None:
    summary, calls, output = _run_adopted(
        tmp_path, at_preflight="Created", afterwards="Created",
    )
    assert summary.get("errors") == [], output[-3000:]
    (create,) = _due_date_creates(calls)
    assert json.loads(create["body"])["Formula"] == "=[Created]+14"
