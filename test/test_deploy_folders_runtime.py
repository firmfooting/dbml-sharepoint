# test/test_deploy_folders_runtime.py
"""Execute the declared-folders phase against a mock SharePoint.

The phase partial is rendered on its own and wrapped in a harness that
defines the deploy helpers it calls, so each branch (create, verify and
skip, refuse a file where a folder was declared, a root that does not read
back, a create that vanishes or reads back as a file, a shape read that
fails) runs under Node rather than being asserted from the template's text.
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
_HARNESS = textwrap.dedent(r"""
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
    const createdByRun = new Set();
    const answer = (url, method) => {
      if (STATE.shapePages && Object.hasOwn(STATE.shapePages, url)) {
        return STATE.shapePages[url];
      }
      if (url.includes('RootFolder')) {
        return STATE.rootMissing ? [500, {}] : [200, { d: { ServerRelativeUrl: STATE.root } }];
      }
      if (url.includes('folders/add(url=')) {
        const name = decodeURIComponent(url.split("folders/add(url='")[1].split("')")[0]);
        if (STATE.refuseCreate) return [500, { error: 'refused' }];
        // MEASURED 2026-09-13, `library.folder.add-under-existing-file-name`:
        // with a file of that name in place the call answers 404 File Not Found.
        if (STATE.filesNamed.includes(name)) {
          return [404, { error: { message: { value: 'File Not Found.' } } }];
        }
        createdByRun.add(name);
        // vanishAfterCreate: the create answers 200 and the folder never appears.
        if (!STATE.vanishAfterCreate) created.add(name);
        return [200, { d: { Name: name } }];
      }
      if (url.includes('GetFolderByServerRelativeUrl')) {
        const quoted = url.split("GetFolderByServerRelativeUrl('")[1];
        const path = decodeURIComponent(quoted.split("')")[0]);
        const name = path.slice(STATE.root.length + 1);
        if (url.includes('/ListItemAllFields')) {
          if (STATE.refuseShapeRead) return [500, {}];
          if (Object.hasOwn(STATE, 'itemPayload')) return [200, { d: STATE.itemPayload }];
          return [200, { d: { FileRef: path,
            FileSystemObjectType: STATE.createdAsFile && createdByRun.has(name) ? 0 : 1 } }];
        }
        if (Object.hasOwn(STATE, 'folderPayload')) return [200, { d: STATE.folderPayload }];
        // `library.folder.folder-read-on-file-path`, same run: a file's own
        // path reads Exists false, exactly as an empty path does. So a file
        // never reaches the "present already" branch.
        const exists = created.has(name) && !STATE.filesNamed.includes(name);
        return [200, { d: { Exists: exists, Name: name, ServerRelativeUrl: path } }];
      }
      if (url.includes('FileSystemObjectType')) {
        if (STATE.threshold) return [500, { error: 'SPQueryThrottledException' }];
        if (STATE.refuseShapeRead) return [500, { error: 'refused' }];
        if (STATE.firstShapePage && !createdByRun.size) return STATE.firstShapePage;
        // encodeURIComponent leaves the apostrophes bare, so the name sits
        // between two literal quotes with its spaces as %20.
        const name = decodeURIComponent(url.split("FileLeafRef%20eq%20'")[1].split("'")[0]);
        // createdAsFile: this run's own create landed as a file, not a folder.
        const asFile = STATE.filesNamed.includes(name)
          || (STATE.createdAsFile && createdByRun.has(name));
        const type = asFile ? 0 : 1;
        return [200, { d: { results: created.has(name) || STATE.filesNamed.includes(name)
          ? [{ Id: 7, FileSystemObjectType: type, FileLeafRef: name,
               FileRef: `${STATE.root}/${name}` }] : [] } }];
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

    // The library's own shape, and the two list writes the phase makes to
    // lift and put back the save rule that refuses a folder create. The
    // restore helper is the deploy's, spelled here because the phase partial
    // is rendered on its own; the emitted one is pinned by a static test.
    const listState = {
      Id: 'list-guid',
      ValidationFormula: STATE.validationFormula,
      ValidationMessage: STATE.validationMessage,
    };
    const listWrites = [];
    const readListShape = async () => (STATE.listMissing ? null : { ...listState });
    const assertListAdoptable = () => {};
    const canonicalFormula = (value) => String(value == null ? '' : value)
      .replace(/\[([A-Za-z0-9_]+)\]/g, '$1');
    const patchListById = async (listId, body) => {
      const clearing = body.ValidationFormula === '';
      listWrites.push({
        ValidationFormula: body.ValidationFormula,
        ValidationMessage: body.ValidationMessage,
      });
      if (clearing && STATE.refuseLift) throw new Error('lift refused');
      if (!clearing && STATE.refuseRestore) throw new Error('restore refused');
      // liftDoesNothing: the MERGE answers 204 and the rule stays on, which
      // is the silent failure the lift's own read-back exists to catch.
      if (clearing && STATE.liftDoesNothing) return;
      listState.ValidationFormula = body.ValidationFormula;
      listState.ValidationMessage = body.ValidationMessage;
    };
    const listValidationLiftedForRun = new Map();
    async function restoreListValidation(listTitle, listId, formula, message) {
      const digest = await getDigest();
      await patchListById(listId, {
        __metadata: { type: 'SP.List' },
        ValidationFormula: formula,
        ValidationMessage: message,
      }, digest);
      const after = await readListShape(listTitle, true);
      if (!after) throw new Error(`list '${listTitle}' no longer exists`);
      if (after.Id !== listId) {
        throw new Error(`list '${listTitle}' changed identity before the restore`);
      }
      if (canonicalFormula(after.ValidationFormula || '') !== canonicalFormula(formula)) {
        throw new Error(`list '${listTitle}' did not retain its save rule`);
      }
      listValidationLiftedForRun.delete(listTitle);
    }
""")


def _render_phase() -> str:
    number = phase_number("folders")
    shapes = script_env().get_template("deploy/_shape_probes.js.j2").render()
    start = shapes.index("  function validatedNextPage(")
    end = shapes.index("\n  }\n", start) + len("\n  }\n")
    # Run the real pagination guard rather than a permissive mock of it.
    return shapes[start:end] + script_env().get_template("deploy/_folders.js.j2").render(phase={
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
        "posts: calls.filter((c) => c.method === 'POST').map((c) => c.url), "
        "gets: calls.filter((c) => c.method === 'GET').map((c) => c.url), "
        "listWrites, stillLifted: [...listValidationLiftedForRun.keys()] })));\n"
    )
    output = run_node(script)
    line = next(ln for ln in output.splitlines() if ln.startswith("__RESULT__"))
    return json.loads(line.removeprefix("__RESULT__"))  # type: ignore[no-any-return]


def _library(*folders: str) -> dict[str, Any]:
    return {"title": "APP_Doc", "is_library": True, "folders": list(folders)}


def _state(**overrides: Any) -> dict[str, Any]:
    return {
        "root": _ROOT, "existing": [], "filesNamed": [], "rootMissing": False,
        "refuseCreate": False, "vanishAfterCreate": False, "createdAsFile": False,
        "refuseShapeRead": False,
        # The library's save rule, and the three ways the lift or the restore
        # can go wrong. Empty formula is the ordinary list with no save rule.
        "validationFormula": "", "validationMessage": "",
        "refuseLift": False, "refuseRestore": False, "liftDoesNothing": False,
        "listMissing": False,
        **overrides,
    }


#: A rule a folder cannot satisfy, which is every rule naming a declared
#: column: a folder's item reads them all back null.
_RULE = '=NOT(ISBLANK([Division]))'
_RULE_MESSAGE = 'A division is required.'


def _guarded(**overrides: Any) -> dict[str, Any]:
    return _state(
        validationFormula=_RULE, validationMessage=_RULE_MESSAGE, **overrides,
    )


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
    contents are never touched.

    The read is what guarantees that, not the endpoint. MEASURED 2026-09-13,
    `library.folder.add-under-existing-folder-name`: a create on a name a
    folder already holds answers HTTP 200 and returns that folder, so a read
    that raced one would cost nothing either.
    """
    result = _run_phase(_state(existing=["Clinical services"]), [_library("Clinical services")])
    assert result["summary"]["errors"] == []
    assert result["summary"]["foldersCreated"] == []
    assert result["summary"]["foldersVerified"] == ["APP_Doc/Clinical services"]
    assert result["posts"] == []


def test_a_file_where_a_folder_was_declared_is_refused_and_nothing_is_written() -> None:
    """MEASURED 2026-09-13, folder-shape-probe.js: a folder read on a file's
    own path answers Exists false, so the file never reaches the "present
    already" branch, and the create that follows answers HTTP 404 "File Not
    Found". The phase must name the file rather than repeat that.
    """
    result = _run_phase(
        _state(filesNamed=["Clinical services"]), [_library("Clinical services")],
    )
    (error,) = result["summary"]["errors"]
    assert error["list"] == "APP_Doc" and error["folder"] == "Clinical services"
    assert "a file where a folder was declared" in error["error"]
    assert "File Not Found" not in error["error"]


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


def test_a_folder_that_does_not_read_back_after_creation_is_reported() -> None:
    """The create answered 200 and the read-back finds nothing, so the
    phase reports the folder rather than recording one nobody can see."""
    result = _run_phase(_state(vanishAfterCreate=True), [_library("Clinical services")])
    (error,) = result["summary"]["errors"]
    assert error["folder"] == "Clinical services"
    assert "did not read back" in error["error"]
    assert result["summary"]["foldersCreated"] == []
    assert result["changes"] == []


def test_a_create_that_reads_back_as_a_file_is_reported() -> None:
    """The path exists after the create but its item reads
    FileSystemObjectType 0, so the shape check refuses to count it."""
    result = _run_phase(_state(createdAsFile=True), [_library("Clinical services")])
    (error,) = result["summary"]["errors"]
    assert error["folder"] == "Clinical services"
    assert "not a folder" in error["error"]
    assert result["summary"]["foldersCreated"] == []
    assert result["changes"] == []


def test_a_shape_read_that_fails_on_an_existing_folder_writes_nothing() -> None:
    """An existing folder whose item probe answers 500 is neither verified
    nor recreated: the phase cannot tell a folder from a file and stops."""
    result = _run_phase(
        _state(existing=["Clinical services"], refuseShapeRead=True),
        [_library("Clinical services")],
    )
    assert result["posts"] == []
    (error,) = result["summary"]["errors"]
    assert error["folder"] == "Clinical services"
    assert "folder item probe failed" in error["error"]
    assert result["summary"]["foldersVerified"] == []


def test_lists_and_libraries_without_folders_are_left_alone() -> None:
    result = _run_phase(
        _state(),
        [{"title": "APP_Topic", "is_library": False, "folders": []},
         {"title": "APP_Doc", "is_library": True, "folders": []}],
    )
    assert result["posts"] == []
    assert result["summary"] == {"errors": [], "foldersCreated": [], "foldersVerified": []}


def test_a_library_with_no_save_rule_has_its_rule_left_alone() -> None:
    """Nothing to lift, so nothing is written to the list at all."""
    result = _run_phase(_state(), [_library("Clinical services")])
    assert result["listWrites"] == []
    assert result["summary"]["foldersCreated"] == ["APP_Doc/Clinical services"]


def test_declared_folders_that_all_exist_never_touch_the_save_rule() -> None:
    """The missing set is asked for BEFORE anything is written, so a
    steady-state redeploy of a guarded library writes nothing here."""
    result = _run_phase(
        _guarded(existing=["Clinical services"]), [_library("Clinical services")],
    )
    assert result["listWrites"] == []
    assert result["posts"] == []
    assert result["summary"]["foldersVerified"] == ["APP_Doc/Clinical services"]


def test_a_save_rule_is_lifted_for_the_create_and_put_straight_back() -> None:
    """MEASURED 2026-09-13, `library.folder.add-with-list-validation` and the
    three rows after it in folder-under-schema-probe.js: a list save rule
    refuses a folder create outright, a cleared list accepts it, and the rule
    goes back onto a library that now holds folders."""
    result = _run_phase(_guarded(), [_library("Clinical services", "Corporate")])
    assert result["summary"]["errors"] == []
    assert result["summary"]["foldersCreated"] == [
        "APP_Doc/Clinical services", "APP_Doc/Corporate",
    ]
    # Lifted once for both folders, not once each, and put back as it was.
    assert result["listWrites"] == [
        {"ValidationFormula": "", "ValidationMessage": ""},
        {"ValidationFormula": _RULE, "ValidationMessage": _RULE_MESSAGE},
    ]
    assert result["stillLifted"] == []


def test_a_save_rule_is_put_back_when_a_folder_create_fails() -> None:
    """The restore is a finally: a create that throws must not carry the
    lifted rule out of the phase with it."""
    result = _run_phase(_guarded(refuseCreate=True), [_library("Clinical services")])
    (error,) = result["summary"]["errors"]
    assert error["folder"] == "Clinical services"
    assert result["listWrites"][-1] == {
        "ValidationFormula": _RULE, "ValidationMessage": _RULE_MESSAGE,
    }
    assert result["stillLifted"] == []


def test_a_lift_that_does_not_take_creates_no_folder() -> None:
    """The MERGE answers and the rule stays on. Without the read-back the
    phase would go on to a create the rule refuses and report the folder
    rather than the lift."""
    result = _run_phase(_guarded(liftDoesNothing=True), [_library("Clinical services")])
    (error,) = result["summary"]["errors"]
    assert "did not lift" in error["error"]
    assert "folder" not in error
    assert result["posts"] == []
    assert result["summary"]["foldersCreated"] == []


def test_a_refused_lift_reports_the_list_and_creates_nothing() -> None:
    result = _run_phase(_guarded(refuseLift=True), [_library("Clinical services")])
    (error,) = result["summary"]["errors"]
    assert "lift refused" in error["error"]
    assert result["posts"] == []
    assert result["summary"]["foldersCreated"] == []


def test_a_refused_restore_is_reported_and_left_for_exit_cleanup() -> None:
    """The folder is created and the rule will not go back. The phase says
    so in the operator's own terms, and the list stays registered so the
    finally in deploy.js.j2 tries again on the way out."""
    result = _run_phase(_guarded(refuseRestore=True), [_library("Clinical services")])
    assert result["summary"]["foldersCreated"] == ["APP_Doc/Clinical services"]
    (error,) = result["summary"]["errors"]
    assert error["error"].startswith("restore the save rule: ")
    assert "restore refused" in error["error"]
    assert result["stillLifted"] == ["APP_Doc"]


@pytest.mark.parametrize("root_type", [None, 0, 1])
def test_folder_shape_is_scoped_to_root_across_all_pages(root_type: int | None) -> None:
    root = "/sites/test/OriginalLibrarySlug"
    name = "Clinical services"
    next_url = "https://example.sharepoint.com/sites/test/_api/folder-items-page2"
    nested = [
        {"FileSystemObjectType": kind, "FileRef": f"{root}/Nested{index}/{name}"}
        for index, kind in enumerate([0, 1, 1, 0])
    ]
    matches = [] if root_type is None else [
        {"FileSystemObjectType": root_type, "FileRef": f"{root}/{name}"},
    ]
    result = _run_phase(_state(
        root=root, refuseCreate=True,
        firstShapePage=[200, {"d": {"results": nested, "__next": next_url}}],
        shapePages={next_url: [200, {"d": {"results": matches}}]},
    ), [_library(name)])
    queries = [url for url in result["gets"] if "FileSystemObjectType" in url]
    assert queries
    assert all("$top=" not in url for url in queries)
    assert all("FileRef" in url.split("$select=")[1].split("&")[0].split(",") for url in queries)
    assert len(result["posts"]) == 1
    assert result["summary"]["foldersCreated"] == []
    error = result["summary"]["errors"][0]["error"]
    if root_type == 0:
        assert "a file where a folder was declared" in error
    else:
        assert "refused" in error
        assert "a file where a folder was declared" not in error


@pytest.mark.parametrize("later_page", [
    [500, {}],
    [200, {"d": {"results": [], "__next": "https://example.sharepoint.com/sites/test/_api/page2"}}],
    [200, {"d": {"results": [], "__next": False}}],
    *[[200, {"d": {"results": [{"FileSystemObjectType": 1, "FileRef": path}]}}]
      for path in [None, "relative/name", "/sites/test/", 42]],
    [200, {"d": {"results": [
        {"FileSystemObjectType": 1, "FileRef": f"{_ROOT}/Clinical services"},
    ]}}],
])
def test_folder_collision_diagnosis_rejects_unreadable_later_pages(later_page: Any) -> None:
    next_url = "https://example.sharepoint.com/sites/test/_api/page2"
    result = _run_phase(_guarded(
        refuseCreate=True, firstShapePage=[200, {"d": {"results": [
            {"FileSystemObjectType": 1, "FileRef": f"{_ROOT}/Clinical services"},
        ], "__next": next_url}}],
        shapePages={next_url: later_page},
    ), [_library("Clinical services")])
    assert "folder item probe" in result["summary"]["errors"][0]["error"]
    assert result["summary"]["foldersCreated"] == []
    assert result["summary"]["foldersVerified"] == []
    assert len(result["posts"]) == 1
    assert result["listWrites"][-1]["ValidationFormula"] == _RULE
    assert result["stillLifted"] == []


def test_folder_shape_refuses_a_collection_exceeding_the_page_limit() -> None:
    pages = {
        f"https://example.sharepoint.com/sites/test/_api/page{index}": [200, {"d": {
            "results": [],
            "__next": f"https://example.sharepoint.com/sites/test/_api/page{index + 1}",
        }}]
        for index in range(1, 101)
    }
    result = _run_phase(_guarded(
        refuseCreate=True, firstShapePage=[200, {"d": {
            "results": [], "__next": "https://example.sharepoint.com/sites/test/_api/page1",
        }}], shapePages=pages,
    ), [_library("Clinical services")])
    assert "incomplete folder collection" in result["summary"]["errors"][0]["error"]
    assert len(result["posts"]) == 1
    assert result["listWrites"][-1]["ValidationFormula"] == _RULE
    assert result["stillLifted"] == []


@pytest.mark.parametrize("existing", [False, True])
def test_folder_paths_work_when_unindexed_queries_are_throttled(existing: bool) -> None:
    name = "Clinical services"
    result = _run_phase(_guarded(
        root="/sites/test/Original Library Slug", threshold=True,
        existing=[name] if existing else [],
    ), [_library(name)])
    assert result["summary"]["errors"] == []
    key = "foldersVerified" if existing else "foldersCreated"
    assert result["summary"][key] == [f"APP_Doc/{name}"]
    assert not any("$filter=" in url for url in result["gets"])
    assert any("/ListItemAllFields?" in url for url in result["gets"])
    assert result["stillLifted"] == []


@pytest.mark.parametrize("property_name", ["folderPayload", "itemPayload"])
@pytest.mark.parametrize("payload", [None, [], 7, "bad", {}, {"Exists": "true"},
                                     {"Exists": True, "ServerRelativeUrl": "/wrong"},
                                     {"FileSystemObjectType": 1, "FileRef": "/wrong"}])
def test_malformed_folder_path_reads_do_not_allow_writes(property_name: str, payload: Any) -> None:
    result = _run_phase(_guarded(
        existing=["Clinical services"], **{property_name: payload},
    ), [_library("Clinical services")])
    assert result["summary"]["errors"]
    assert result["summary"]["foldersVerified"] == []
    assert result["posts"] == [] and result["listWrites"] == []


def test_throttled_collision_diagnosis_keeps_the_create_error_and_restores_the_rule() -> None:
    result = _run_phase(
        _guarded(refuseCreate=True, threshold=True), [_library("Clinical services")],
    )
    error = result["summary"]["errors"][0]["error"]
    assert "refused" in error and "collision diagnosis unavailable" in error
    assert "SPQueryThrottledException" in error
    assert result["summary"]["foldersCreated"] == []
    assert result["listWrites"][-1]["ValidationFormula"] == _RULE
    assert result["stillLifted"] == []
