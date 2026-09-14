# test/test_demo_files_runtime.py
"""Execute the generated demo-data.js against a mock library.

A library row is a file: uploaded into its folder, found again by name, its
values set on the file's item and read back. Every branch runs under Node:
the upload, the re-paste skip, and each of the five ways it can fail. A
branch whose only job is to explain a failure is the one a static reading
cannot check, so each is provoked here. Node is required; the module
skips without it.
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
        payload = { d: { results: uploaded && !STATE.vanishAfterUpload
          ? [{ Id: 9, FileLeafRef: STATE.name, FileDirRef: STATE.root + '/' + STATE.folder }]
          : [] } };
        const override = uploaded ? 'afterFileProbe' : 'beforeFileProbe';
        if (Object.hasOwn(STATE, override)) payload = STATE[override];
      } else if (method === 'POST' && /\/items\(9\)$/.test(u)) {
        if (STATE.refuseMerge) {
          status = 500;
          payload = { error: { message: { value: 'merge refused' } } };
        } else {
          status = 204;
          merged = JSON.parse(opts.body);
          payload = {};
        }
      } else if (/\/items\(9\)\?/.test(u)) {
        if (STATE.refuseReadback) {
          status = 500;
          payload = { error: { message: { value: 'read-back refused' } } };
        } else {
          payload = { d: STATE.stored === null
            ? { Division: merged.Division, Status: merged.Status }
            : STATE.stored };
        }
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
        "refuseUpload": False, "vanishAfterUpload": False, "refuseMerge": False,
        "refuseReadback": False, "stored": None, **overrides,
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
    assert not any(
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


_INVALID_FILE_IDENTITIES: list[dict[str, Any]] = [
    {"Id": None}, {"Id": 0}, {"Id": "9"}, {"Id": 1.5},
    {"FileDirRef": None},
    {"FileDirRef": "relative/path"},
]


@pytest.mark.parametrize("payload", [
    None, {}, {"d": {}}, {"d": {"results": {}}},
    {"d": {"results": [], "__next": False}},
    {"d": {"results": [], "__next": 5}},
    {"d": {"results": [None]}},
    *[
        {"d": {"results": [{
            "Id": 9, "FileLeafRef": _NAME, "FileDirRef": f"{_ROOT}/{_FOLDER}",
            **bad,
        }]}}
        for bad in _INVALID_FILE_IDENTITIES
    ],
])
@pytest.mark.parametrize("after_upload", [False, True])
def test_a_malformed_file_probe_never_seeds_or_merges(
    payload: Any, after_upload: bool,
) -> None:
    key = "afterFileProbe" if after_upload else "beforeFileProbe"
    summary, calls = _seed(**{key: payload})
    assert "invalid response" in summary["errors"][0]["error"]
    assert summary["created"] == [] and summary["skipped"] == []
    assert _posts(calls, "/items(9)") == []
    assert len(_posts(calls, "Files/add(")) == int(after_upload)


@pytest.mark.parametrize("count,next_link", [(50, None), (0, "next-page"), (1, "next-page")])
def test_an_incomplete_file_probe_cannot_establish_absence_or_identity(
    count: int, next_link: str | None,
) -> None:
    rows = [
        {"Id": n + 1, "FileLeafRef": _NAME, "FileDirRef": f"{_ROOT}/other-{n}"}
        for n in range(count)
    ]
    summary, calls = _seed(beforeFileProbe={"d": {"results": rows, "__next": next_link}})
    assert "incomplete collection" in summary["errors"][0]["error"]
    assert _posts(calls, "Files/add(") == []
    assert summary["created"] == [] and summary["skipped"] == []


def test_duplicate_file_matches_are_refused() -> None:
    rows = [
        {"Id": n, "FileLeafRef": _NAME, "FileDirRef": f"{_ROOT}/{_FOLDER}"}
        for n in [9, 10]
    ]
    summary, calls = _seed(beforeFileProbe={"d": {"results": rows}})
    assert "ambiguous matches" in summary["errors"][0]["error"]
    assert _posts(calls, "Files/add(") == []
    assert summary["created"] == [] and summary["skipped"] == []


def test_a_same_named_file_in_another_folder_does_not_skip_the_upload() -> None:
    row = {"Id": 10, "FileLeafRef": _NAME, "FileDirRef": f"{_ROOT}/other"}
    summary, calls = _seed(beforeFileProbe={"d": {"results": [row]}})
    assert summary["errors"] == [] and summary["skipped"] == []
    assert len(_posts(calls, "Files/add(")) == 1
    assert summary["created"][0]["id"] == 9


def test_a_file_that_does_not_read_back_after_upload_is_reported() -> None:
    """The upload answered 200 and the file is not there. Fail closed and
    named, rather than MERGE values onto an item nothing has found."""
    summary, calls = _seed(vanishAfterUpload=True)
    (error,) = summary["errors"]
    assert error["key"] == "d1"
    assert "did not read back" in error["error"]
    assert _posts(calls, "/items(9)") == []
    assert summary["created"] == []


def test_a_refused_merge_never_records_the_file_as_created() -> None:
    """The file is uploaded and its values are not set, so the row is an
    error: a file that looks seeded and carries none of its data."""
    summary, calls = _seed(refuseMerge=True)
    (error,) = summary["errors"]
    assert "merge refused" in error["error"]
    assert _posts(calls, "Files/add(") != []
    assert summary["created"] == []


def test_a_read_back_that_fails_leaves_the_values_unverified() -> None:
    summary, _calls = _seed(refuseReadback=True)
    (error,) = summary["errors"]
    assert "unverified" in error["error"]
    assert summary["created"] == []


def test_a_value_the_site_did_not_keep_fails_the_file() -> None:
    """The MERGE is a second write on the file, so its values are read back;
    a file whose value did not stick is not recorded as created."""
    summary, _calls = _seed(stored={"Division": _FOLDER, "Status": "Complete"})
    (error,) = summary["errors"]
    assert 'Status was written "Required" and read back "Complete"' in error["error"]
    assert summary["created"] == []
#: What a rich Note does to a string on the way in. MEASURED 2026-09-13,
#: `text.item-value.rich-note-roundtrip` and `text.item-value.rich-note-colon`
#: in item-text-roundtrip-probe.js: a Note with RichText true stores
#: `Colon: ... & < > " { }` as `Colon&#58; ... &amp; &lt; &gt; &quot; &#123;
#: &#125;`, while `' / # % + @ - [ ] ( ) = ? ;` pass through untouched. The
#: same run measured the plain Note and the single-line Text returning the
#: bytes they were given, so the encoding belongs to RichText and not to the
#: transport.
_RICH_WRITTEN = 'Reviewed: privacy & records <ok> {q3}'
_RICH_STORED = 'Reviewed&#58; privacy &amp; records &lt;ok&gt; &#123;q3&#125;'


def _rich_demo_js(written: str = _RICH_WRITTEN) -> str:
    """The same library, carrying one richtext column with a demo value."""
    schema = make_schema(
        make_table(
            "Doc", column("Title"), column("Division", "division"),
            column("Status", "doc_status"), column("Notes", "richtext"),
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
                    values={"Division": _FOLDER, "Status": "Required", "Notes": written},
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


def _seed_rich(**overrides: Any) -> dict[str, Any]:
    state = {
        "root": _ROOT, "folder": _FOLDER, "name": _NAME, "present": False,
        "refuseUpload": False, "vanishAfterUpload": False, "refuseMerge": False,
        "refuseReadback": False, "stored": None, **overrides,
    }
    body = _rich_demo_js(overrides.pop("written", _RICH_WRITTEN)).rstrip()
    assert body.endswith("})();")
    output = run_node(
        f"const STATE = {json.dumps(state)};\n{_HARNESS}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "});\n",
    )
    result = next(ln for ln in output.splitlines() if ln.startswith("__RESULT__"))
    parsed: dict[str, Any] = json.loads(result.removeprefix("__RESULT__"))
    return parsed


def test_a_rich_note_read_back_in_its_stored_encoding_is_accepted() -> None:
    """The defect this closes: seeding a library refused every rich Note
    carrying one of the encoded characters, because the read-back compares
    the MERGE's second write and a rich Note never returns the bytes it was
    given. MEASURED 2026-09-13, `text.item-value.rich-note-decode-recovers`:
    decoding the character references returns the written string exactly, so
    the decoded form is what the comparison can honestly be made on."""
    summary = _seed_rich(stored={
        "Division": _FOLDER, "Status": "Required", "Notes": _RICH_STORED,
    })
    assert summary["errors"] == []
    assert [row["key"] for row in summary["created"]] == ["d1"]


def test_a_rich_note_the_site_did_not_keep_still_fails_the_file() -> None:
    """Decoding the read-back must not decode the check away: a value the
    site genuinely did not store is still caught."""
    summary = _seed_rich(stored={
        "Division": _FOLDER, "Status": "Required", "Notes": 'Reviewed&#58; something else',
    })
    (error,) = summary["errors"]
    assert "Notes was written" in error["error"]
    assert summary["created"] == []


def test_a_rich_note_reports_both_forms_when_it_fails() -> None:
    """An operator reading the error needs the stored form as well as the
    decoded one, because the two differ and only one of them is on the page."""
    summary = _seed_rich(stored={
        "Division": _FOLDER, "Status": "Required", "Notes": '&lt;wrong&gt;',
    })
    (error,) = summary["errors"]
    assert "&lt;wrong&gt;" in error["error"]
    assert "<wrong>" in error["error"]


def test_a_plain_column_is_still_compared_byte_for_byte() -> None:
    """Only a rich Note is decoded. MEASURED in the same run: the single-line
    Text and the plain Note both returned the bytes they were given, so
    decoding either would forgive a difference the site really made."""
    summary = _seed_rich(stored={
        "Division": _FOLDER, "Status": "&lt;Required&gt;", "Notes": _RICH_STORED,
    })
    (error,) = summary["errors"]
    assert "Status was written" in error["error"]
