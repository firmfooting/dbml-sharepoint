# test/test_deploy_library_runtime.py
"""Execute the deploy against a mock site that already holds a document library.

The adopted harness answers every list as an owned generic list; here one
answers as a library (BaseTemplate 101), so the view phase's Scope write and
read-back, the ACL phase's wait for the inheritance flag and the folder
phase's create run under Node inside the real deploy scope.
Node is required; the module skips without it.
"""

import json
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from _builders import ID_PK, TITLE, table
from _node import NODE, run_node
from _packs import pack
from _paths import FIXTURES
from test_deploy_runtime import _summary_of, _view_guard_harness, _without_assessment

from dbml_sharepoint.analysis.phases import phase_number

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_LIBRARY_ENTITY = """
entities:
  Escalation: { kind: DocumentLibrary, base_template: 101, site_role: default }
"""

_FOLDERED_LIBRARY = """
entities:
  Escalation:
    kind: DocumentLibrary
    base_template: 101
    site_role: default
    folders: ["Clinical services"]
"""

_RECURSIVE_VIEW = _LIBRARY_ENTITY + """
views:
  Escalation:
    - title: "Flat"
      default: true
      fields: [FileLeafRef, Note]
      scope: recursive
"""

_BROKEN_INHERITANCE = _LIBRARY_ENTITY + """
permission_levels:
  - name: "Schema Manager"
    description: "Test permission level."
    base_permissions:
      - ViewListItems
      - ManageLists

groups:
  - name: "List Maintainer"
    description: "Test group."
    owner_group: "Site Owners"
    require_empty_at_deploy: true

list_permissions:
  default:
    site_role: default
    break_inheritance: true
    reconcile: exact
    assignments:
      - principal: { kind: group, name: "List Maintainer" }
        level: "Schema Manager"
"""

#: Answers the list-level inheritance read. `__uniqueAfter` is how many reads
#: it takes for the flag to turn true once the break has been sent; a value
#: nothing reaches keeps it false for good. `__uniqueFail` makes every read
#: after the ACL phase's own break answer HTTP 500; the isolation phase breaks
#: earlier without re-reading, and the ACL probe before the break still passes.
_INHERITANCE_JS = """globalThis.fetch = async (url, opts = {}) => {
  const asked = String(url);
  if (asked.includes('breakroleinheritance')) {
    globalThis.__broke = true;
    if (mockPhase === globalThis.__aclPhase) globalThis.__brokeInAcl = true;
  }
  if (asked.endsWith('$select=HasUniqueRoleAssignments')) {
    globalThis.__uniqueReads = (globalThis.__uniqueReads || 0) + 1;
    if (globalThis.__brokeInAcl && globalThis.__uniqueFail) {
      return {
        ok: false, status: 500, headers: { get: () => null },
        json: async () => ({}), text: async () => 'boom',
      };
    }
    const unique = Boolean(globalThis.__broke)
      && globalThis.__uniqueReads >= globalThis.__uniqueAfter;
    return {
      ok: true, status: 200, headers: { get: () => null },
      json: async () => ({ d: { HasUniqueRoleAssignments: unique } }),
      text: async () => '',
    };
  }
"""

#: Answers the folder phase's reads for the one folder `_FOLDERED_LIBRARY`
#: declares. `__folderCreated` turns on at the create POST, after which the
#: folder reads back as existing and its item as FileSystemObjectType 1.
_FOLDER_JS = """globalThis.fetch = async (url, opts = {}) => {
  const requested = String(url);
  const folderAnswer = (payload) => ({
    ok: true, status: 200, headers: { get: () => null },
    json: async () => payload, text: async () => '',
  });
  if (requested.includes('/RootFolder?')) {
    return folderAnswer({ d: { ServerRelativeUrl: '/sites/test/APP_Escalation' } });
  }
  if (requested.includes('/folders/add(')) {
    globalThis.__folderCreated = true;
    return folderAnswer({ d: { Name: 'Clinical services' } });
  }
  if (requested.includes('GetFolderByServerRelativeUrl(')) {
    return folderAnswer({ d: {
      Exists: Boolean(globalThis.__folderCreated), Name: 'Clinical services',
      ServerRelativeUrl: '/sites/test/APP_Escalation/Clinical services',
    } });
  }
  if (requested.includes('FileSystemObjectType')) {
    const rows = globalThis.__folderCreated
      ? [{ Id: 1, FileSystemObjectType: 1, FileLeafRef: 'Clinical services' }] : [];
    return folderAnswer({ d: { results: rows } });
  }
"""


def _library_deploy_js(tmp_path: Path, mapping: str) -> str:
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = pack(
        tmp_path, dbml=table("Escalation", ID_PK, TITLE, "Note nvarchar"), mapping=mapping,
    )
    return _without_assessment(generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    ))


def _library_harness(
    *, scope_sticks: bool = True, unique_after: int | None = None,
    unique_fail: bool = False, declared_folder: bool = False,
) -> str:
    """The view-guard harness (per-view identity, view creates) with the one
    list answering as a library and the level marker carrying this pack's
    project name.

    `unique_after` and `unique_fail` splice the inheritance read in;
    `declared_folder` splices the folder reads in, for a pack built from
    `_FOLDERED_LIBRARY`.
    """
    harness = _view_guard_harness({}).replace("simple-test", "t")
    for what, old, new in (
        ("base template", "BaseTemplate: 100,", "BaseTemplate: 101,"),
        ("scope write", "'RowLimit', 'ViewQuery']", "'RowLimit', 'ViewQuery', 'Scope']"),
    ):
        if what == "scope write" and not scope_sticks:
            continue
        spliced = harness.replace(old, new)
        assert spliced != harness, f"{what} was not spliced into the harness"
        harness = spliced
    anchor = "globalThis.fetch = async (url, opts = {}) => {\n"
    if unique_after is not None or unique_fail:
        spliced = harness.replace(anchor, _INHERITANCE_JS, 1)
        assert spliced != harness, "the inheritance read was not spliced into the harness"
        # A failing re-read still needs the probe before the break to read
        # false, or the phase never breaks and never re-reads.
        harness = (
            f"globalThis.__uniqueAfter = {1000 if unique_after is None else unique_after};\n"
            f"globalThis.__uniqueFail = {json.dumps(unique_fail)};\n"
            f"globalThis.__aclPhase = {json.dumps(phase_number('acls'))};\n" + spliced
        )
    if declared_folder:
        spliced = harness.replace(anchor, _FOLDER_JS, 1)
        assert spliced != harness, "the folder reads were not spliced into the harness"
        harness = spliced
    # The library settle wait is real time the mock needs none of.
    return (
        "{ const real = globalThis.setTimeout;"
        " globalThis.setTimeout = (fn, _ms, ...a) => real(fn, 0, ...a); }\n"
        + harness
    )


def _run(harness: str, deploy_js: str) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """The summary, the recorded calls, and how often the inheritance flag
    was read (counted by the spliced handler, which answers before the
    harness records the call)."""
    body = deploy_js.rstrip()
    assert body.endswith("})();")
    output = run_node(
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(globalThis.__calls));\n"
        "  console.log('__UNIQUE__' + JSON.stringify(globalThis.__uniqueReads || 0));\n"
        "});\n",
    )
    calls_line = next(ln for ln in output.splitlines() if ln.startswith("__CALLS__"))
    unique_line = next(ln for ln in output.splitlines() if ln.startswith("__UNIQUE__"))
    return (
        _summary_of(output),
        json.loads(calls_line.removeprefix("__CALLS__")),
        int(unique_line.removeprefix("__UNIQUE__")),
    )


def _scope_writes(calls: list[dict[str, Any]], title: str) -> list[Any]:
    """Every Scope the deploy sent for one view, named by its plain title: in
    the create body when the view was absent, in a MERGE (whose URL carries
    the title encoded) when it existed and read back differently."""
    encoded = quote(title)
    written: list[Any] = []
    for call in calls:
        if call["method"] != "POST" or not call["body"]:
            continue
        parsed = json.loads(call["body"])
        created = call["url"].endswith("/views") and parsed.get("Title") == title
        merged = (
            f"views/getbytitle('{encoded}')" in call["url"] and "viewfields" not in call["url"]
        )
        if (created or merged) and parsed.get("Scope") is not None:
            written.append(parsed["Scope"])
    return written


def test_a_recursive_library_view_is_written_and_reads_back(tmp_path: Path) -> None:
    """MEASURED 2026-09-13, `library.view.scope-on-merge-reads-back`: a stored
    view reading Scope 0 takes MERGE Scope 1 and reads back 1. The mock
    stores the write, so the read-back finds no drift and the run is clean."""
    summary, calls, _reads = _run(
        _library_harness(), _library_deploy_js(tmp_path, _RECURSIVE_VIEW),
    )
    assert summary["errors"] == [], summary["errors"]
    assert _scope_writes(calls, "Flat") == [1]
    assert _scope_writes(calls, "All Items") == [1], (
        "a library's generated All Items must be recursive too"
    )


def test_a_scope_write_that_does_not_stick_is_reported_as_drift(tmp_path: Path) -> None:
    """The fail-closed branch: a MERGE the site accepted but did not keep
    reads back as the old value and the run names the property."""
    summary, _calls, _reads = _run(
        _library_harness(scope_sticks=False), _library_deploy_js(tmp_path, _RECURSIVE_VIEW),
    )
    drift = [e for e in summary["errors"] if "Scope (declared 1" in str(e)]
    assert drift, summary["errors"]


def test_breaking_inheritance_on_a_library_waits_for_the_flag(tmp_path: Path) -> None:
    """MEASURED 2026-09-09, `library.access.unique-permissions-library`: after
    the break a library read HasUniqueRoleAssignments=false once and true on
    the next read. The mock answers the same way and the phase carries on."""
    summary, calls, reads = _run(
        _library_harness(unique_after=3), _library_deploy_js(tmp_path, _BROKEN_INHERITANCE),
    )
    inheritance_errors = [e for e in summary["errors"] if "HasUniqueRoleAssignments" in str(e)]
    assert inheritance_errors == [], summary["errors"]
    assert reads >= 3, "the phase did not re-read the flag after the break"
    assert any("breakroleinheritance" in c["url"] for c in calls)


def test_a_library_whose_flag_never_turns_is_refused(tmp_path: Path) -> None:
    """Fail closed: an allowlist written onto a library that still inherits
    would be a no-op the verify could not tell from success."""
    summary, _calls, _reads = _run(
        _library_harness(unique_after=1000), _library_deploy_js(tmp_path, _BROKEN_INHERITANCE),
    )
    refused = [
        e for e in summary["errors"] if "still reads HasUniqueRoleAssignments=false" in str(e)
    ]
    assert refused, summary["errors"]


def test_a_failed_re_read_of_the_flag_is_reported_and_writes_no_allowlist(
    tmp_path: Path,
) -> None:
    """The re-read after the break answering HTTP 500 is its own named
    error, and the phase stops before a single role assignment is sent."""
    summary, calls, _reads = _run(
        _library_harness(unique_fail=True), _library_deploy_js(tmp_path, _BROKEN_INHERITANCE),
    )
    failed = [e for e in summary["errors"] if "re-read failed" in str(e)]
    assert failed, summary["errors"]
    assignments = [
        c["url"] for c in calls
        if "addroleassignment" in c["url"] or "removeroleassignment" in c["url"]
    ]
    assert assignments == [], assignments


def test_a_declared_folder_is_created_by_the_whole_deploy(tmp_path: Path) -> None:
    """The folder phase inside the real deploy scope rather than as a
    rendered partial: the helpers it reads are the deploy's own, and the
    summary key it fills is the one deploy.js.j2 declares."""
    summary, _calls, _reads = _run(
        _library_harness(declared_folder=True), _library_deploy_js(tmp_path, _FOLDERED_LIBRARY),
    )
    assert summary["errors"] == [], summary["errors"]
    assert summary["foldersCreated"] == ["APP_Escalation/Clinical services"]
