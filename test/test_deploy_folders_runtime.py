# test/test_deploy_folders_runtime.py
"""Execute the declared-folders phase against a mock SharePoint.

The phase partial is rendered on its own and wrapped in a harness that
defines the deploy helpers it calls, so each branch (create, verify and
skip, refuse a file where a folder was declared, a root that does not read
back) runs under Node rather than being asserted from the template's text.
Node is required; the module skips without it.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE, run_node

from dbml_sharepoint.analysis.phases import phase_number
from dbml_sharepoint.templating import script_env

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_ROOT = "/sites/test/APP_Doc"

#: The helpers the partial reads from the deploy's enclosing scope, and a
#: fetch that answers folder reads from `STATE` and records every request.
_HARNESS = textwrap.dedent("""
    const calls = [];
    const changes = [];
    const log = (level, msg) => console.log(`[${level}] ${msg}`);
    const apiUrl = (suffix) => `https://example.sharepoint.com/sites/test/_api/${suffix}`;
    const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
    const getDigest = async () => 'digest';
    const spError = (text) => text;
    const isAbsent400 = () => false;
    const logChange = (change) => { changes.push(change); };
    const created = new Set(STATE.existing);
    const answer = (url, method) => {
      if (url.includes('RootFolder')) {
        return STATE.rootMissing ? [500, {}] : [200, { d: { ServerRelativeUrl: STATE.root } }];
      }
      if (url.includes('folders/add(url=')) {
        const name = decodeURIComponent(url.split("folders/add(url='")[1].split("')")[0]);
        if (STATE.refuseCreate) return [500, { error: 'refused' }];
        created.add(name);
        return [200, { d: { Name: name } }];
      }
      if (url.includes('GetFolderByServerRelativeUrl')) {
        const quoted = url.split("GetFolderByServerRelativeUrl('")[1];
        const path = decodeURIComponent(quoted.split("')")[0]);
        const name = path.slice(STATE.root.length + 1);
        return [200, { d: { Exists: created.has(name), Name: name, ServerRelativeUrl: path } }];
      }
      if (url.includes('FileSystemObjectType')) {
        // encodeURIComponent leaves the apostrophes bare, so the name sits
        // between two literal quotes with its spaces as %20.
        const name = decodeURIComponent(url.split("FileLeafRef%20eq%20'")[1].split("'")[0]);
        const type = STATE.filesNamed.includes(name) ? 0 : 1;
        return [200, { d: { results: created.has(name) || STATE.filesNamed.includes(name)
          ? [{ Id: 7, FileSystemObjectType: type, FileLeafRef: name }] : [] } }];
      }
      return [200, { d: { results: [] } }];
    };
    const fetchWithRetry = async (url, opts = {}) => {
      const method = opts.method || 'GET';
      calls.push({ method, url: String(url) });
      const [status, body] = answer(String(url), method);
      return {
        ok: status < 400, status,
        json: async () => body,
        text: async () => JSON.stringify(body),
      };
    };
    async function postJson(url, body, digest) {
      const r = await fetchWithRetry(url, { method: 'POST', body: JSON.stringify(body) });
      if (!r.ok) throw new Error(spError(await r.text()) || `HTTP ${r.status}`);
      return r.json();
    }
    const summary = { errors: [], foldersCreated: [], foldersVerified: [] };
""")


def _render_phase() -> str:
    number = phase_number("folders")
    return script_env().get_template("deploy/_folders.js.j2").render(phase={
        "number": number, "name": "declared folders", "group_number": number.split(".")[0],
        "group_name": "STRUCTURE", "first_in_group": False,
    })


def _run_phase(state: dict[str, Any], lists: list[dict[str, Any]]) -> dict[str, Any]:
    script = (
        f"const STATE = {json.dumps(state)};\n"
        f"const SCHEMA = {json.dumps({'lists': lists})};\n"
        + _HARNESS
        + "(async () => {\n" + _render_phase() + "\n})().then(() => console.log("
        "'__RESULT__' + JSON.stringify({ summary, changes, "
        "posts: calls.filter((c) => c.method === 'POST').map((c) => c.url) })));\n"
    )
    output = run_node(script)
    line = next(ln for ln in output.splitlines() if ln.startswith("__RESULT__"))
    return json.loads(line.removeprefix("__RESULT__"))  # type: ignore[no-any-return]


def _library(*folders: str) -> dict[str, Any]:
    return {"title": "APP_Doc", "is_library": True, "folders": list(folders)}


def _state(**overrides: Any) -> dict[str, Any]:
    return {
        "root": _ROOT, "existing": [], "filesNamed": [], "rootMissing": False,
        "refuseCreate": False, **overrides,
    }


def test_a_declared_folder_is_created_under_the_root_and_read_back() -> None:
    """MEASURED 2026-09-03, `library.folder.creation-path`: the create is a
    POST to folders/add(url=) under the library root, and the folder reads
    back as an SP.Folder with a list item of FileSystemObjectType 1."""
    result = _run_phase(_state(), [_library("Clinical services", "Corporate")])
    assert result["summary"]["errors"] == []
    assert result["summary"]["foldersCreated"] == ["APP_Doc/Clinical services", "APP_Doc/Corporate"]
    assert result["summary"]["foldersVerified"] == []
    root_api = "https://example.sharepoint.com/sites/test/_api/web/GetFolderByServerRelativeUrl"
    assert result["posts"] == [
        f"{root_api}('/sites/test/APP_Doc')/folders/add(url='Clinical services')",
        f"{root_api}('/sites/test/APP_Doc')/folders/add(url='Corporate')",
    ]
    assert [c["key"] for c in result["changes"]] == [
        "folder: APP_Doc/Clinical services", "folder: APP_Doc/Corporate",
    ]


def test_an_existing_folder_is_verified_and_not_recreated() -> None:
    """A redeploy: the folder is there, so nothing is written and its
    contents are never touched."""
    result = _run_phase(_state(existing=["Clinical services"]), [_library("Clinical services")])
    assert result["summary"]["errors"] == []
    assert result["summary"]["foldersCreated"] == []
    assert result["summary"]["foldersVerified"] == ["APP_Doc/Clinical services"]
    assert result["posts"] == []


def test_a_file_where_a_folder_was_declared_is_refused_and_nothing_is_written() -> None:
    """The shape check: a file of the declared name reads back
    FileSystemObjectType 0, and the deploy must not create beside it."""
    result = _run_phase(
        _state(existing=["Clinical services"], filesNamed=["Clinical services"]),
        [_library("Clinical services")],
    )
    assert result["posts"] == []
    (error,) = result["summary"]["errors"]
    assert error["list"] == "APP_Doc" and error["folder"] == "Clinical services"
    assert "a file where a folder was declared" in error["error"]


def test_a_root_that_does_not_read_back_fails_the_library_not_the_run() -> None:
    result = _run_phase(_state(rootMissing=True), [_library("Clinical services")])
    assert result["posts"] == []
    (error,) = result["summary"]["errors"]
    assert error["list"] == "APP_Doc" and "RootFolder" in error["error"]


def test_a_refused_create_is_reported_against_the_folder() -> None:
    result = _run_phase(_state(refuseCreate=True), [_library("Clinical services")])
    (error,) = result["summary"]["errors"]
    assert error["folder"] == "Clinical services"
    assert result["summary"]["foldersCreated"] == []


def test_lists_and_libraries_without_folders_are_left_alone() -> None:
    result = _run_phase(
        _state(),
        [{"title": "APP_Topic", "is_library": False, "folders": []},
         {"title": "APP_Doc", "is_library": True, "folders": []}],
    )
    assert result["posts"] == []
    assert result["summary"] == {"errors": [], "foldersCreated": [], "foldersVerified": []}
