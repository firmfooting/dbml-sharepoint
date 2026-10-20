# test/test_deploy_folder_defaults_runtime.py
"""Execute the folder defaults phase against a mock of the defaults file.

The phase partial is rendered on its own, like the declared-folders phase, so
each branch (first write, no-op redeploy, change, removal, entries the mapping
does not declare, read-back mismatch, an unrecognised existing file) runs
under Node. Node is required; the module skips without it.
"""

import json
import textwrap
from collections.abc import Mapping, Sequence

import pytest
from _json_view import Json
from _node import NODE, run_node

from dbml_sharepoint.analysis.phases import phase_number
from dbml_sharepoint.templating import script_env

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_ROOT = "/sites/test/APP_Doc"

_HARNESS = textwrap.dedent(r"""
    const calls = [];
    const changes = [];
    const log = (level, msg) => console.log(`[${level}] ${msg}`);
    const apiUrl = (suffix) => `https://example.sharepoint.com/sites/test/_api/${suffix}`;
    const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
    const pathLiteral = (path) => String(path).replace(/'/g, "''");
    const getDigest = async () => 'digest';
    const logChange = (change) => { changes.push(change); };
    // null is "no file yet"; the file is the only state the phase writes.
    let file = STATE.file;
    globalThis.fetch = async (url, opts = {}) => {
      const method = opts.method || 'GET';
      url = String(url);
      calls.push({ method, url, body: opts.body === undefined ? null : opts.body });
      const reply = (status, text) => ({
        ok: status < 400, status, url, headers: { get: () => null },
        json: async () => JSON.parse(text), text: async () => text,
      });
      if (url.includes('RootFolder')) {
        return reply(200, JSON.stringify({ d: { ServerRelativeUrl: STATE.root } }));
      }
      if (url.includes('Files/add(')) {
        if (STATE.refuseWrite) return reply(500, '{}');
        if (!STATE.ignoreWrite) file = STATE.mangleWrite ? opts.body + ' ' : opts.body;
        return reply(200, '{}');
      }
      if (url.includes('GetFileByServerRelativeUrl')) {
        return file === null ? reply(404, '') : reply(200, file);
      }
      return reply(200, JSON.stringify({ d: { results: [] } }));
    };
    const summary = { errors: [] };
""")


def _render_phase() -> str:
    number = phase_number("folder_defaults")
    return script_env().get_template("deploy/_folder_defaults.js.j2").render(phase={
        "number": number, "name": "folder default values",
        "group_number": number.split(".")[0], "group_name": "STRUCTURE",
        "first_in_group": False,
    })


def _run_phase(state: Mapping[str, object], lists: Sequence[Mapping[str, object]]) -> Json:
    script = (
        f"const STATE = {json.dumps(state)};\n"
        f"const SCHEMA = {json.dumps({'lists': lists})};\n"
        + _HARNESS
        + script_env().get_template("_http.js.j2").render()
        + "(async () => {\n" + _render_phase() + "\n})().then(() => console.log("
        "'__RESULT__' + JSON.stringify({ summary, changes, file, "
        "writes: calls.filter((c) => c.method === 'POST').map((c) => c.body) })));\n"
    )
    output = run_node(script)
    line = next(ln for ln in output.splitlines() if ln.startswith("__RESULT__"))
    result = Json.loads(line.removeprefix("__RESULT__"))
    assert result.is_object, result
    return result


def _state(file: str | None = None, **overrides: object) -> dict[str, object]:
    return {"root": _ROOT, "file": file, **overrides}


def _library(
    defaults: Mapping[str, Mapping[str, str]], folders: Sequence[str] = ("FolderA", "FolderB"),
) -> dict[str, object]:
    return {
        "title": "APP_Doc", "is_library": True, "folders": list(folders),
        "folder_defaults": [
            {"folder": folder, "values": [{"field": c, "value": v} for c, v in values.items()]}
            for folder, values in defaults.items()
        ],
    }


def _entry(folder: str, **values: str) -> str:
    inner = "".join(f'<DefaultValue FieldName="{c}">{v}</DefaultValue>' for c, v in values.items())
    return f'<a href="{_ROOT}/{folder}">{inner}</a>'


def _doc(*entries: str) -> str:
    return f"<MetadataDefaults>{''.join(entries)}</MetadataDefaults>"


def test_first_deploy_writes_declared_defaults_and_reads_back() -> None:
    result = _run_phase(_state(), [_library({"FolderA": {"Division": "Corporate"}})])
    assert result["summary"]["errors"] == []
    assert result["file"] == _doc(_entry("FolderA", Division="Corporate"))
    assert len(result["writes"]) == 1
    assert [c["key"] for c in result["changes"]] == ["list-setting:APP_Doc:folder-defaults"]


def test_redeploy_with_same_declaration_writes_nothing() -> None:
    held = _doc(_entry("FolderA", Division="Corporate"))
    result = _run_phase(_state(held), [_library({"FolderA": {"Division": "Corporate"}})])
    assert result["summary"]["errors"] == []
    assert result["writes"] == [] and result["changes"] == []


def test_redeploy_keeps_defaults_for_folders_the_mapping_does_not_declare() -> None:
    other = _entry("HandMade", Division="Hand")
    held = _doc(other)
    result = _run_phase(_state(held), [_library({"FolderA": {"Division": "Corporate"}})])
    assert result["summary"]["errors"] == []
    assert other in result["file"]
    assert _entry("FolderA", Division="Corporate") in result["file"]


def test_changed_default_is_reconciled() -> None:
    held = _doc(_entry("FolderA", Division="Corporate"))
    result = _run_phase(_state(held), [_library({"FolderA": {"Division": "Finance"}})])
    assert result["file"] == _doc(_entry("FolderA", Division="Finance"))


def test_removed_default_on_a_declared_folder_is_deleted_from_storage() -> None:
    held = _doc(_entry("FolderA", Division="Corporate", Status="Open"))
    result = _run_phase(_state(held), [_library({"FolderA": {"Division": "Corporate"}})])
    assert result["file"] == _doc(_entry("FolderA", Division="Corporate"))


def test_folder_dropped_from_the_mapping_keeps_its_entries() -> None:
    # FolderB is declared as a folder but no longer has defaults: its entry goes.
    # HandMade was never declared as a folder: its entry stays.
    held = _doc(
        _entry("FolderA", Division="Corporate"), _entry("FolderB", Division="Old"),
        _entry("HandMade", Division="Hand"),
    )
    result = _run_phase(_state(held), [_library({"FolderA": {"Division": "Corporate"}})])
    assert _entry("FolderB", Division="Old") not in result["file"]
    assert _entry("HandMade", Division="Hand") in result["file"]
    assert _entry("FolderA", Division="Corporate") in result["file"]


def test_values_are_xml_escaped_and_read_back_equal() -> None:
    result = _run_phase(_state(), [_library({"FolderA": {"Note": 'A & B <"x">'}})])
    assert result["summary"]["errors"] == []
    assert "A &amp; B &lt;&quot;x&quot;&gt;" in result["file"]
    # A second run over what was written sees nothing to change.
    again = _run_phase(_state(str(result["file"].value)), [
        _library({"FolderA": {"Note": 'A & B <"x">'}}),
    ])
    assert again["writes"] == []


def test_readback_mismatch_throws() -> None:
    result = _run_phase(_state(mangleWrite=True), [_library({"FolderA": {"Division": "X"}})])
    (error,) = [e["error"] for e in result["summary"]["errors"]]
    assert "did not read back" in error and result["changes"] == []


def test_a_write_the_site_ignores_is_an_error() -> None:
    result = _run_phase(_state(ignoreWrite=True), [_library({"FolderA": {"Division": "X"}})])
    assert [e["list"] for e in result["summary"]["errors"]] == ["APP_Doc"]


def test_an_unrecognised_existing_file_is_left_alone() -> None:
    result = _run_phase(
        _state("<html>not ours</html>"), [_library({"FolderA": {"Division": "X"}})],
    )
    assert result["writes"] == []
    assert "left alone" in result["summary"]["errors"][0]["error"]


def test_a_library_without_folder_defaults_is_never_read() -> None:
    result = _run_phase(_state("<html>not ours</html>"), [_library({})])
    assert result["summary"]["errors"] == [] and result["writes"] == []
