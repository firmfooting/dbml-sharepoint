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

#: A declared view whose previous title is the one a bare library ships on
#: AllItems.aspx. Nothing refuses this at build time: 'All Documents' is not
#: another declared title, so the checks in `_views.py` have nothing to see.
_CLAIMS_THE_BUILTIN_TITLE = _LIBRARY_ENTITY + """
views:
  Escalation:
    - title: "Docs"
      default: true
      fields: [FileLeafRef, Note]
      scope: recursive
      renamed_from: ["All Documents"]
"""

#: Two declared views, neither claiming anything of the other's. The
#: collision the runtime guard refuses is spliced into the emitted SCHEMA
#: afterwards, because no mapping can express it.
_TWO_VIEWS = _LIBRARY_ENTITY + """
views:
  Escalation:
    - title: "Alpha"
      default: true
      fields: [FileLeafRef, Note]
    - title: "Beta"
      fields: [FileLeafRef, Note]
"""

#: 'Alpha' adopts the live 'Gamma' and renames it. The second claim on
#: 'Gamma' is spliced into the emitted SCHEMA afterwards, because
#: `PREVIOUS_TITLE_CLAIMED_TWICE` refuses two declarations claiming one.
_RENAME_THEN_CLAIM = _LIBRARY_ENTITY + """
views:
  Escalation:
    - title: "Alpha"
      default: true
      fields: [FileLeafRef, Note]
      renamed_from: ["Gamma"]
    - title: "Beta"
      fields: [FileLeafRef, Note]
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


def _library_deploy_js(tmp_path: Path, mapping: str, *, titled: bool = True) -> str:
    """`titled` declares a Title column, which is what puts a `title_patch` on
    the list. A library naming its files through FileLeafRef declares none, and
    the shipped legal-compliance-register library is one, so `titled=False` is
    the shape that reaches the branches a null patch takes."""
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    columns = [ID_PK, TITLE, "Note nvarchar"] if titled else [ID_PK, "Note nvarchar"]
    schema, bundle = pack(
        tmp_path, dbml=table("Escalation", *columns), mapping=mapping,
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


#: A MERGE addressed by immutable view Id, which is how the view phase renames
#: a view it adopted under another title. The shared harness only serves
#: getbytitle, so without this the rename lands nowhere and the read-back
#: reports a view that disappeared. Re-keying `views` is the point: the deploy
#: reads the view back by its DECLARED title on the very next call, exactly as
#: `library.view.builtin-getbytitle-after-rename` measured on the live site.
_VIEW_MERGE_BY_ID_JS = (
    "  if ((opts.method || 'GET') === 'POST' && opts.body"
    " && /\\/views\\('[^']+'\\)$/.test(u)) {\n"
    "    const guid = (u.match(/\\/views\\('([^']+)'\\)$/) || [])[1];\n"
    "    const named = VIEW_BY_GUID[guid];\n"
    "    const state = named && views[`${named.list} ${named.title}`];\n"
    "    const parsed = JSON.parse(opts.body);\n"
    "    if (state && parsed.Title !== undefined && parsed.Title !== named.title) {\n"
    "      delete views[`${named.list} ${named.title}`];\n"
    "      state.Title = parsed.Title;\n"
    "      views[`${named.list} ${parsed.Title}`] = state;\n"
    "      VIEW_GUIDS[`${named.list} ${parsed.Title}`] = guid;\n"
    "      named.title = parsed.Title;\n"
    "    }\n"
    "  }\n"
)


#: The shared harness keys its view state on the RAW title out of the URL,
#: so `getbytitle('All%20Items')` and the seeded 'All Items' are two views to
#: it and a read after a write lands on an empty second one. Decoding the way
#: `listOf` already does gives one view one key. Paired with the re-key below,
#: because a rename moves the key a later read resolves by.
_VIEW_KEY_DECODE_OLD_JS = (
    "const viewOf = (url) => {\n"
    "  const match = url.match(/\\/views\\/getbytitle\\('([^']+)'\\)/);\n"
    "  return match && match[1];\n"
    "};\n"
)

_VIEW_KEY_DECODE_JS = (
    "const viewOf = (url) => {\n"
    "  const match = url.match(/\\/views\\/getbytitle\\('(.*?)'\\)/);\n"
    "  return match == null ? match"
    " : decodeURIComponent(match[1]).replace(/''/g, \"'\");\n"
    "};\n"
)

#: A rename through getbytitle, which is how a view created under its URL
#: slug takes its declared title. SharePoint resolves the new title on the
#: next call; without this the mock still answers only to the old one, and
#: every setting the create body carried reads back absent.
_VIEW_RENAME_REKEY_OLD_JS = (
    "          if (parsed[key] !== undefined) state[key] = parsed[key];\n"
    "        }\n"
)

_VIEW_RENAME_REKEY_JS = _VIEW_RENAME_REKEY_OLD_JS + (
    "        if (parsed.Title !== undefined) {\n"
    "          delete views[`${listOf(u)} ${viewOf(u)}`];\n"
    "          views[`${listOf(u)} ${parsed.Title}`] = state;\n"
    "        }\n"
)

#: A response is a snapshot. The shared harness hands its own state objects
#: to the caller, so the view enumeration the phase caches silently follows
#: every later write to the mock, and a phase that reads a stale cache reads
#: a fresh one here instead. Serialising is what a fetch does.
_RESPONSE_SNAPSHOT_JS = (
    "    json: async () => JSON.parse(JSON.stringify(payload)),\n"
)

#: Views the mock seeds beside the built-in, at a .aspx of their own and
#: never as the default. A live library can hold views the deployer did not
#: create, and two of the view phase's guards only run when one is there.
_SEED_EXTRA_VIEWS_JS = (
    "    viewState(listTitle);\n"
    "    for (const [seededTitle, base] of Object.entries(__EXTRA_VIEWS__)) {\n"
    "      const seeded = viewState(listTitle, seededTitle);\n"
    "      seeded.DefaultView = false;\n"
    "      seeded.ServerRelativeUrl = `/sites/test/Lists/${listTitle}/${base}`;\n"
    "    }\n"
)


def _library_harness(
    *, scope_sticks: bool = True, unique_after: int | None = None,
    unique_fail: bool = False, declared_folder: bool = False,
    builtin_view_title: str | None = None, builtin_is_default: bool = True,
    extra_views: dict[str, str] | None = None,
) -> str:
    """The view-guard harness (per-view identity, view creates) with the one
    list answering as a library and the level marker carrying this pack's
    project name.

    `unique_after` and `unique_fail` splice the inheritance read in;
    `declared_folder` splices the folder reads in, for a pack built from
    `_FOLDERED_LIBRARY`.

    `builtin_view_title` renames the view the mock seeds on AllItems.aspx.
    The shared harness seeds it as 'All Items', which is what a generic LIST
    ships; a live library ships 'All Documents' there
    (`library.view.builtin-occupies-allitems`, 2026-09-13), and that title is
    the whole reason the view phase needs to adopt by URL.

    `builtin_is_default` clears DefaultView on the seeded view, which is the
    shape a foreign view on a freed AllItems.aspx has. `extra_views` maps a
    title to a .aspx basename and seeds each one beside the built-in.
    """
    harness = _view_guard_harness({}).replace("simple-test", "t")
    for what, old, new in (
        ("base template", "BaseTemplate: 100,", "BaseTemplate: 101,"),
        ("scope write", "'RowLimit', 'ViewQuery']", "'RowLimit', 'ViewQuery', 'Scope']"),
        ("view merge by id",
         "  if ((opts.method || 'GET') === 'POST' && u.includes('/views/getbytitle')) {\n",
         _VIEW_MERGE_BY_ID_JS
         + "  if ((opts.method || 'GET') === 'POST'"
           " && u.includes('/views/getbytitle')) {\n"),
        ("response snapshot",
         "    json: async () => payload,\n", _RESPONSE_SNAPSHOT_JS),
        ("view key decode", _VIEW_KEY_DECODE_OLD_JS, _VIEW_KEY_DECODE_JS),
        ("view rename re-key", _VIEW_RENAME_REKEY_OLD_JS, _VIEW_RENAME_REKEY_JS),
        ("built-in view title",
         "(listTitle, title = 'All Items') =>",
         f"(listTitle, title = {json.dumps(builtin_view_title)}) =>"),
        ("built-in default flag",
         "Title: title, DefaultView: true,", "Title: title, DefaultView: false,"),
        ("extra views", "    viewState(listTitle);\n",
         _SEED_EXTRA_VIEWS_JS.replace("__EXTRA_VIEWS__", json.dumps(extra_views or {}))),
    ):
        if what == "scope write" and not scope_sticks:
            continue
        if what == "built-in view title" and builtin_view_title is None:
            continue
        if what == "built-in default flag" and builtin_is_default:
            continue
        if what == "extra views" and not extra_views:
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


def _run_output(harness: str, deploy_js: str) -> str:
    """The whole Node transcript, which carries the operator's log lines as
    well as the markers `_run` parses its three values out of."""
    body = deploy_js.rstrip()
    assert body.endswith("})();")
    return run_node(
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(globalThis.__calls));\n"
        "  console.log('__UNIQUE__' + JSON.stringify(globalThis.__uniqueReads || 0));\n"
        "});\n",
    )


def _calls_of(output: str) -> list[dict[str, Any]]:
    """The recorded calls out of a transcript `_run_output` returned."""
    line = next(ln for ln in output.splitlines() if ln.startswith("__CALLS__"))
    calls: list[dict[str, Any]] = json.loads(line.removeprefix("__CALLS__"))
    return calls


def _run(harness: str, deploy_js: str) -> tuple[dict[str, Any], list[dict[str, Any]], int]:
    """The summary, the recorded calls, and how often the inheritance flag
    was read (counted by the spliced handler, which answers before the
    harness records the call)."""
    output = _run_output(harness, deploy_js)
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


def _view_titles_created(calls: list[dict[str, Any]]) -> list[str]:
    """Every Title the run POSTed to a /views collection, in order."""
    made: list[str] = []
    for call in calls:
        if call["method"] != "POST" or not call["body"] or not call["url"].endswith("/views"):
            continue
        parsed = json.loads(call["body"])
        if parsed.get("__metadata", {}).get("type") == "SP.View":
            made.append(parsed["Title"])
    return made


def _titles_merged_by_id(calls: list[dict[str, Any]]) -> list[str]:
    """Every Title sent to a view addressed by its immutable Id, which is how
    the phase renames a view it adopted under another title."""
    renamed: list[str] = []
    for call in calls:
        url = call["url"]
        if call["method"] != "POST" or not call["body"]:
            continue
        if "/views('" not in url or not url.endswith("')"):
            continue
        title = json.loads(call["body"]).get("Title")
        if title is not None:
            renamed.append(title)
    return renamed


def test_a_librarys_builtin_view_is_adopted_rather_than_created_beside(
    tmp_path: Path,
) -> None:
    """MEASURED 2026-09-13, `library.view.builtin-occupies-allitems` and
    `library.view.create-allitems-title-on-library` in
    library-builtin-view-probe.js: a bare library's view on AllItems.aspx reads
    'All Documents', and a second view created under the slug is minted
    AllItems1.aspx. The generated All Items can therefore never be created at
    its own declared URL, and a live run failed the view closed on that drift.

    The phase adopts the view already on the URL instead: nothing is POSTed to
    the views collection for it, and the adopted view is renamed by Id.
    """
    summary, calls, _reads = _run(
        _library_harness(builtin_view_title="All Documents"),
        _library_deploy_js(tmp_path, _RECURSIVE_VIEW),
    )
    assert summary["errors"] == [], summary["errors"]
    assert "All Items" not in _view_titles_created(calls), (
        "the generated All Items was created beside the built-in view, "
        "which is the defect adopting it avoids"
    )
    assert "All Items" in _titles_merged_by_id(calls), (
        "the adopted view was never renamed to the declared title"
    )


def test_an_adopted_builtin_view_still_takes_every_declared_setting(
    tmp_path: Path,
) -> None:
    """Adoption is only worth having if the view then reconciles like any
    other. Each of these was measured on the live built-in view on 2026-09-13:
    `library.view.builtin-scope-merge`, `library.view.builtin-viewfields-replace`
    and `library.view.builtin-hidden-once-not-default`.
    """
    _summary, calls, _reads = _run(
        _library_harness(builtin_view_title="All Documents"),
        _library_deploy_js(tmp_path, _RECURSIVE_VIEW),
    )
    assert _scope_writes(calls, "All Items") == [1], (
        "an adopted All Items must still be made recursive"
    )
    encoded = quote("All Items")
    hidden = [
        json.loads(call["body"]).get("Hidden")
        for call in calls
        if call["method"] == "POST" and call["body"]
        and f"views/getbytitle('{encoded}')" in call["url"]
        and "viewfields" not in call["url"]
        and json.loads(call["body"]).get("Hidden") is not None
    ]
    assert hidden == [True], (
        "the recovery view is hidden behind the declared default, adopted or not"
    )
    assert any(
        "removeallviewfields" in call["url"] and encoded in call["url"] for call in calls
    ), "the adopted view's field list was never rebuilt"


def test_a_library_whose_builtin_view_is_already_all_items_is_adopted_by_title(
    tmp_path: Path,
) -> None:
    """The URL match is a fallback, not a replacement. When the view on the URL
    already carries the declared title there is nothing to rename, and the run
    must not send a title MERGE it does not need.
    """
    summary, calls, _reads = _run(
        _library_harness(), _library_deploy_js(tmp_path, _RECURSIVE_VIEW),
    )
    assert summary["errors"] == [], summary["errors"]
    assert "All Items" not in _view_titles_created(calls)
    assert _titles_merged_by_id(calls) == []


def test_a_foreign_view_holding_the_builtin_url_is_not_adopted(
    tmp_path: Path,
) -> None:
    """A basename match is not identity. MEASURED 2026-09-13,
    `library.view.builtin-delete-frees-url` in library-builtin-view-probe.js:
    the built-in can be deleted and AllItems.aspx then reads free, so a custom
    public view can afterwards hold it. Adopting on the basename alone would
    rename that view and replace its query, fields and formatting.

    Nothing in the view enumeration says "built-in", so adoption is restricted
    to the shape that was measured: the page is the list's default view. A view
    on the URL that is not takes nothing, and the operator is told why.
    """
    output = _run_output(
        _library_harness(builtin_view_title="Team docs", builtin_is_default=False),
        _library_deploy_js(tmp_path, _RECURSIVE_VIEW),
    )
    calls = _calls_of(output)
    assert _titles_merged_by_id(calls) == [], (
        "the foreign view on AllItems.aspx was renamed, which is the defect"
    )
    assert "AllItems" in _view_titles_created(calls), (
        "All Items fell through to the create beside it, which is what the "
        "URL drift gate then fails closed on a real library"
    )
    assert any(
        "WARN" in line and "'Team docs' holds AllItems.aspx" in line
        and "(default: false)" in line
        for line in output.splitlines()
    ), output[-3000:]


def test_a_builtin_view_another_declaration_claims_is_not_adopted(
    tmp_path: Path,
) -> None:
    """The second half of the same guard. A declaration whose `renamed_from`
    names the built-in's title owns that view, and no mapping check can see
    the collision: 'All Documents' is a live title, not a declared one.

    Here that declaration refuses to act (its current and previous titles both
    exist), so the built-in is still on the URL when the generated All Items
    reaches it. Adopting it there would rename the very view the run has just
    declined to choose between.
    """
    output = _run_output(
        _library_harness(
            builtin_view_title="All Documents", extra_views={"Docs": "Docs.aspx"},
        ),
        _library_deploy_js(tmp_path, _CLAIMS_THE_BUILTIN_TITLE),
    )
    summary, calls = _summary_of(output), _calls_of(output)
    assert [e["error"] for e in summary["errors"]] == [
        ("both current view 'Docs' and previous-title view 'All Documents' "
         "exist; refusing to choose or delete either"),
    ], summary["errors"]
    assert _titles_merged_by_id(calls) == [], (
        "the built-in was adopted and renamed out from under 'Docs'"
    )
    assert any(
        "WARN" in line and "'All Documents' holds AllItems.aspx" in line
        and "(default: true)" in line
        for line in output.splitlines()
    ), output[-3000:]


def _declare_previous_title(deploy_js: str, title: str, previous: str) -> str:
    """Put `previous` on the declared view `title` in the emitted SCHEMA.

    No mapping can say this: `PREVIOUS_TITLE_IS_A_CURRENT_TITLE` refuses a
    previous title that is another declared view's current one, which is the
    only schema-level route to two declarations resolving to one live view.
    The runtime guard is the layer under that, so reaching it means writing
    the SCHEMA the check would have refused.
    """
    blob = _schema_blob(deploy_js)
    schema = json.loads(blob)
    matched = [v for v in schema["views"] if v["title"] == title]
    assert len(matched) == 1, f"{title!r} is not one declared view: {matched}"
    matched[0]["renamed_from"] = [previous]
    return deploy_js.replace(blob, json.dumps(schema), 1)


def test_two_declarations_resolving_to_one_live_view_write_neither(
    tmp_path: Path,
) -> None:
    """'Alpha' matches the live view by title and verifies it. 'Beta' then
    matches the same view by previous title, sees a basename that is not its
    own, and migrates: create, transfer the default flag, DELETE the old view.
    The view 'Alpha' was reported verified on is gone, and both were reported
    verified.

    The phase records which live view each declaration resolved to and refuses
    the second claim instead, before any write.
    """
    deploy_js = _declare_previous_title(
        _library_deploy_js(tmp_path, _TWO_VIEWS), "Beta", "Alpha",
    )
    summary, calls, _reads = _run(
        _library_harness(
            builtin_view_title="All Documents", extra_views={"Alpha": "Alpha.aspx"},
        ),
        deploy_js,
    )
    assert [e["error"] for e in summary["errors"]] == [
        ("views 'Alpha' and 'Beta' on this list both resolved to the same "
         "live view; refusing to write either"),
    ], summary["errors"]
    assert "Beta" not in _view_titles_created(calls), (
        "the migration that deletes Alpha's view had already started"
    )


def test_a_rename_this_phase_performed_does_not_trip_the_claim_guard(
    tmp_path: Path,
) -> None:
    """One enumeration serves every declaration on a list, so it still shows
    'Gamma' after 'Alpha' has renamed it. A later declaration claiming 'Gamma'
    would match a title that no longer exists, resolve the Id behind it, and be
    refused as a second claim on a view nothing else is using.

    The phase writes the new title back into the enumeration, so the matchers
    read the list as it now is. The guard fails closed; this is what keeps it
    from firing on the deployer's own work.
    """
    deploy_js = _declare_previous_title(
        _library_deploy_js(tmp_path, _RENAME_THEN_CLAIM), "Beta", "Gamma",
    )
    summary, calls, _reads = _run(
        _library_harness(
            builtin_view_title="All Documents", extra_views={"Gamma": "Alpha.aspx"},
        ),
        deploy_js,
    )
    assert summary["errors"] == [], summary["errors"]
    assert "Alpha" in _titles_merged_by_id(calls), (
        "'Gamma' was never renamed, so nothing was there to trip the guard"
    )
    assert "Beta" in _view_titles_created(calls), (
        "'Beta' resolved to a live view instead of being created"
    )


def test_a_view_this_phase_deleted_is_dropped_from_the_enumeration(
    tmp_path: Path,
) -> None:
    """The same list read, and the other thing a declaration does to it. A
    migration to the clean URL recreates the page and DELETES the old view, so
    the enumeration now names a view that is gone; a later declaration
    claiming its title would resolve an Id that no longer resolves.

    Identical to the rename above except for where 'Gamma' lives, which is
    what chooses the migration between them.
    """
    deploy_js = _declare_previous_title(
        _library_deploy_js(tmp_path, _RENAME_THEN_CLAIM), "Beta", "Gamma",
    )
    summary, calls, _reads = _run(
        _library_harness(
            builtin_view_title="All Documents", extra_views={"Gamma": "Gamma.aspx"},
        ),
        deploy_js,
    )
    assert summary["errors"] == [], summary["errors"]
    created = _view_titles_created(calls)
    assert "Alpha" in created, "'Gamma' was never migrated off Gamma.aspx"
    assert "Beta" in created, "'Beta' resolved to the view the migration deleted"


def _schema_blob(deploy_js: str) -> str:
    """The SCHEMA literal out of the emitted script, brace-balanced."""
    blob = deploy_js.split("const SCHEMA = ", 1)[1]
    depth = 0
    for index, char in enumerate(blob):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return blob[: index + 1]
    raise AssertionError("the emitted SCHEMA literal never closed")


def _schema_lists(deploy_js: str) -> list[dict[str, Any]]:
    """The SCHEMA.lists the emitted script carries."""
    lists: list[dict[str, Any]] = json.loads(_schema_blob(deploy_js))["lists"]
    return lists


def test_a_library_naming_files_by_leafref_declares_no_title_patch(
    tmp_path: Path,
) -> None:
    """The state the branches below exist for. A library whose Title carries no
    display rename gets no patch, because its built-in Title reads Sealed and
    the maintenance unseal of it is refused HTTP 400 (MEASURED 2026-09-13).
    The shipped legal-compliance-register library is exactly this shape.
    """
    untitled = _schema_lists(_library_deploy_js(tmp_path, _RECURSIVE_VIEW, titled=False))
    assert [lst["title_patch"] for lst in untitled] == [None]
    second = tmp_path / "titled"
    second.mkdir()
    titled = _schema_lists(_library_deploy_js(second, _RECURSIVE_VIEW, titled=True))
    assert titled[0]["title_patch"] is not None, (
        "a declared Title column must still produce a patch, or this fixture "
        "stops telling the two shapes apart"
    )


def test_preflight_over_an_existing_library_with_no_title_patch_does_not_throw(
    tmp_path: Path,
) -> None:
    """The preflight synthesised a Title field for every list and read
    `list.title_patch.Title` off it, which throws on a null patch. Every other
    caller of syntheticTitleField already guarded on the same fact.

    It is reached only once the list EXISTS, because the field wave runs over
    the lists whose shape the list wave read back. A first provision onto a
    clean site therefore never found it, and the live run that did reported
    `Phase 1.2: read-only preflight: Cannot read properties of null (reading
    'Title')`, aborting before any write.
    """
    summary, _calls, _reads = _run(
        _library_harness(),
        _library_deploy_js(tmp_path, _RECURSIVE_VIEW, titled=False),
    )
    assert summary.get("aborted") is None, summary.get("aborted")
    assert summary["errors"] == [], summary["errors"]


def test_a_declared_title_column_is_still_preflighted_on_a_library(
    tmp_path: Path,
) -> None:
    """The guard skips a patch that is absent, not one that is there. A library
    that does declare a Title column keeps its synthetic field and the shape
    check that comes with it."""
    summary, calls, _reads = _run(
        _library_harness(),
        _library_deploy_js(tmp_path, _RECURSIVE_VIEW, titled=True),
    )
    assert summary.get("aborted") is None, summary.get("aborted")
    assert any(
        "getbyinternalnameortitle('Title')" in call["url"]
        or "fields?" in call["url"]
        for call in calls
    ), "a declared Title column was never read during the run"
