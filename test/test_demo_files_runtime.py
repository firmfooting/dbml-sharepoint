# test/test_demo_files_runtime.py
"""Execute the generated demo-data.js against a mock library.

A library row is a file: uploaded into its folder, found again by name, its
values set on the file's item and read back. Each branch runs under Node:
the upload, the re-paste skip, a refused upload, and a value the site did
not keep. Node is required; the module skips without it.
"""

import json
import textwrap
from typing import Any

import pytest
from _model import bundle as make_bundle
from _model import column, enum
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE, run_node
from _paths import FIXTURES

from dbml_sharepoint.generators.demogen import generate_demo_js
from dbml_sharepoint.model.mapping_types import DemoFile, DemoItem, EntityMapping
from dbml_sharepoint.model.release import load_release

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_ROOT = "/sites/test/APP_Doc"
_FOLDER = "Clinical services"
_NAME = "[DEMO] Privacy - 2026 Q3.txt"


def _demo_js() -> str:
    schema = make_schema(
        make_table(
            "Doc", column("Title"), column("Division", "division"),
            column("Status", "doc_status"),
        ),
        enums=[
            enum("division", "Clinical services", "Corporate services"),
            enum("doc_status", "Required", "Complete"),
        ],
    )
    bundle = make_bundle(
        entities={
            "Doc": EntityMapping(
                name="Doc", kind="DocumentLibrary", base_template=101,
                site_role="default", folders=(_FOLDER, "Corporate services"),
            ),
        },
        demo_items={
            "Doc": [
                DemoItem(
                    key="d1",
                    values={"Division": _FOLDER, "Status": "Required"},
                    file=DemoFile(name=_NAME, folder=_FOLDER, content="Sample SAQ."),
                ),
            ],
        },
    )
    return generate_demo_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


#: A mock library: the file exists only once its upload has been seen (or
#: from the start, for the re-paste case), the MERGE stores what it was sent,
#: and the read-back answers from STORED when it is set.
_HARNESS = textwrap.dedent(r"""
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    let uploaded = STATE.present;
    let merged = {};
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      calls.push({ url: u, method, body: opts.body === undefined ? null : opts.body });
      let status = 200;
      let payload = { d: { results: [] } };
      if (u.includes('contextinfo')) {
        payload = { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } };
      } else if (u.includes('ListItemEntityTypeFullName')) {
        payload = { d: { ListItemEntityTypeFullName: 'SP.Data.APP_DocItem' } };
      } else if (u.includes('RootFolder')) {
        payload = { d: { ServerRelativeUrl: STATE.root } };
      } else if (u.includes('Files/add(')) {
        if (STATE.refuseUpload) {
          status = 500;
          payload = { error: { message: { value: 'upload refused' } } };
        } else {
          uploaded = true;
          payload = { d: {} };
        }
      } else if (u.includes('FileLeafRef%20eq')) {
        payload = { d: { results: uploaded
          ? [{ Id: 9, FileLeafRef: STATE.name, FileDirRef: STATE.root + '/' + STATE.folder }]
          : [] } };
      } else if (method === 'POST' && /\/items\(9\)$/.test(u)) {
        status = 204;
        merged = JSON.parse(opts.body);
        payload = {};
      } else if (/\/items\(9\)\?/.test(u)) {
        payload = { d: STATE.stored === null
          ? { Division: merged.Division, Status: merged.Status }
          : STATE.stored };
      }
      return {
        ok: status < 400, status,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
    globalThis.__calls = calls;
""")


def _seed(**overrides: Any) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = {
        "root": _ROOT, "folder": _FOLDER, "name": _NAME, "present": False,
        "refuseUpload": False, "stored": None, **overrides,
    }
    body = _demo_js().rstrip()
    assert body.endswith("})();")
    output = run_node(
        f"const STATE = {json.dumps(state)};\n{_HARNESS}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(globalThis.__calls));\n"
        "});\n",
    )
    result = next(ln for ln in output.splitlines() if ln.startswith("__RESULT__"))
    calls = next(ln for ln in output.splitlines() if ln.startswith("__CALLS__"))
    return (
        json.loads(result.removeprefix("__RESULT__")),
        json.loads(calls.removeprefix("__CALLS__")),
    )


def _posts(calls: list[dict[str, Any]], fragment: str) -> list[dict[str, Any]]:
    return [c for c in calls if c["method"] == "POST" and fragment in c["url"]]


def test_a_library_row_is_uploaded_into_its_folder_and_its_values_set() -> None:
    """MEASURED 2026-09-03, `library.file.upload-path-files-add`: the upload
    is a POST of the file's bytes to Files/add under the folder, and the
    file's item then takes the row's values."""
    summary, calls = _seed()
    assert summary["errors"] == [], summary["errors"]
    (upload,) = _posts(calls, "Files/add(")
    assert upload["url"].endswith(
        f"GetFolderByServerRelativeUrl('{_ROOT}/{_FOLDER}')"
        f"/Files/add(url='{_NAME}',overwrite=false)"
    )
    assert upload["body"] == "Sample SAQ."
    (merge,) = _posts(calls, "/items(9)")
    assert json.loads(merge["body"]) == {
        "__metadata": {"type": "SP.Data.APP_DocItem"}, "Division": _FOLDER, "Status": "Required",
    }
    assert summary["created"] == [
        {"list": "APP_Doc", "key": "d1", "id": 9, "file": f"{_ROOT}/{_FOLDER}/{_NAME}"},
    ]
    assert not _posts(calls, "/items'") and not any(
        c["method"] == "POST" and c["url"].endswith("/items") for c in calls
    ), "a library row must never be created with a POST to /items"


def test_a_file_already_in_its_folder_is_skipped_not_duplicated() -> None:
    summary, calls = _seed(present=True)
    assert summary["errors"] == []
    assert summary["created"] == []
    assert summary["skipped"] == [{"list": "APP_Doc", "key": "d1", "id": 9}]
    assert _posts(calls, "Files/add(") == []
    assert _posts(calls, "/items(9)") == []


def test_a_refused_upload_is_reported_and_nothing_is_set() -> None:
    summary, calls = _seed(refuseUpload=True)
    (error,) = summary["errors"]
    assert error["key"] == "d1" and "upload refused" in error["error"]
    assert _posts(calls, "/items(9)") == []
    assert summary["created"] == []


def test_a_value_the_site_did_not_keep_fails_the_file() -> None:
    """The MERGE is a second write on the file, so its values are read back;
    a file whose value did not stick is not recorded as created."""
    summary, _calls = _seed(stored={"Division": _FOLDER, "Status": "Complete"})
    (error,) = summary["errors"]
    assert 'Status was written "Required" and read back "Complete"' in error["error"]
    assert summary["created"] == []
