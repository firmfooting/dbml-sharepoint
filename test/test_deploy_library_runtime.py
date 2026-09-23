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

#: A library whose one folder carries its own ACL. The folder policy names
#: its principal through `{member}`, which is what lets one declaration cover
#: every folder and is how `groups[].from_enum` names the same object without
#: either list being written twice. Only DECLARED levels are used: the mock
#: knows the levels this pack creates and nothing about SharePoint's built-ins.
_FOLDER_ACL_LIBRARY = _FOLDERED_LIBRARY + """
permission_levels:
  - name: "Folder Editor"
    description: "Edit inside one folder."
    base_permissions:
      - ViewListItems
      - AddListItems
      - EditListItems

groups:
  - name: "List Maintainer"
    description: "Test group."
    owner_group: "Site Owners"
  - name: "Clinical services Editors"
    description: "One folder's editors."
    owner_group: "Site Owners"

list_permissions:
  default:
    site_role: default
    break_inheritance: true
    reconcile: exact
    assignments:
      - principal: { kind: group, name: "List Maintainer" }
        level: "Folder Editor"
  folders:
    Escalation:
      break_inheritance: true
      reconcile: exact
      assignments:
        - principal: { kind: group, name: "{member} Editors" }
          level: "Folder Editor"
"""

#: The same library in `configured` mode, with ONE principal declared at TWO
#: levels. That is the shape the per-assignment prune got wrong: each pass
#: treated its own level as the principal's whole desired state, so the pass
#: for one level removed the other and the pass for the other removed the
#: first, off the same pre-write snapshot.
_TWO_LEVEL_CONFIGURED_LIBRARY = _FOLDERED_LIBRARY + """
permission_levels:
  - name: "Folder Editor"
    description: "Edit inside one folder."
    base_permissions:
      - ViewListItems
      - AddListItems
      - EditListItems
  - name: "Folder Approver"
    description: "Approve inside one folder."
    base_permissions:
      - ViewListItems
      - ApproveItems

groups:
  - name: "List Maintainer"
    description: "Test group."
    owner_group: "Site Owners"
  - name: "Clinical services Editors"
    description: "One folder's editors."
    owner_group: "Site Owners"

list_permissions:
  default:
    site_role: default
    break_inheritance: true
    reconcile: configured
    assignments:
      - principal: { kind: group, name: "List Maintainer" }
        level: "Folder Editor"
      - principal: { kind: group, name: "List Maintainer" }
        level: "Folder Approver"
  folders:
    Escalation:
      break_inheritance: true
      reconcile: configured
      assignments:
        - principal: { kind: group, name: "{member} Editors" }
          level: "Folder Editor"
        - principal: { kind: group, name: "{member} Editors" }
          level: "Folder Approver"
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
_FOLDER_JS = r"""globalThis.fetch = async (url, opts = {}) => {
  const requested = String(url);
  const folderAnswer = (payload) => ({
    ok: true, status: 200, headers: { get: () => null },
    json: async () => payload, text: async () => '',
  });
  if (requested.includes('/RootFolder?')) {
    return folderAnswer({ d: { ServerRelativeUrl: '/sites/test/APP_Escalation' } });
  }
  if (requested.includes('/folders/add(')) {
    globalThis.__calls.push({
      url: requested, method: opts.method || 'GET', body: opts.body || null,
    });
    globalThis.__folderCreated = true;
    return folderAnswer({ d: { Name: 'Clinical services' } });
  }
  if (requested.includes('/ListItemAllFields')) {
    // Id is what the ACL phase addresses the folder by; __folderIdMissing
    // models a tenant that answers the read without it.
    const item = { FileSystemObjectType: 1,
      FileRef: '/sites/test/APP_Escalation/Clinical services' };
    if (!globalThis.__folderIdMissing) item.Id = 1;
    return folderAnswer({ d: item });
  }
  if (requested.includes('GetFolderByServerRelativeUrl(')) {
    return folderAnswer({ d: {
      Exists: Boolean(globalThis.__folderCreated), Name: 'Clinical services',
      ServerRelativeUrl: '/sites/test/APP_Escalation/Clinical services',
    } });
  }
  // ONE item, re-read inside the ownership bracket before the folder is
  // written to. Ahead of the enumeration below because that matches any URL
  // naming the field, and answering this read with a results array is what
  // made the re-read see `undefined`.
  if (requested.includes('/items(') && requested.includes('FileSystemObjectType')) {
    globalThis.__calls.push({ url: requested, method: opts.method || 'GET', body: null });
    return folderAnswer({ d: globalThis.__folderIdentity || {
      FileSystemObjectType: 1,
      FileRef: '/sites/test/APP_Escalation/Clinical services',
    } });
  }
  if (requested.includes('FileSystemObjectType')) {
    globalThis.__calls.push({ url: requested, method: opts.method || 'GET', body: null });
    const rows = (globalThis.__folderCreated && !globalThis.__folderMissing)
      ? [{ Id: 1, FileSystemObjectType: 1, FileLeafRef: 'Clinical services',
          FileRef: '/sites/test/APP_Escalation/Clinical services',
          HasUniqueRoleAssignments: Boolean(globalThis.__folderScoped) }] : [];
    // A file somebody shared by hand: a descendant scope this bundle never
    // declared, which the ACL phase must still refuse to run past.
    if (globalThis.__strayScope) {
      rows.push({ Id: 99, FileSystemObjectType: 0, FileLeafRef: 'stray.docx',
        FileRef: '/sites/test/APP_Escalation/stray.docx',
        HasUniqueRoleAssignments: true });
    }
    return folderAnswer({ d: { results: rows } });
  }
  // The folder's OWN inheritance flag. The shared inheritance mock tracks one
  // global `__broke`, which would make the folder read as already unique the
  // moment the list's break landed and skip the branch under test.
  if (requested.includes('/items(')
      && requested.endsWith('$select=HasUniqueRoleAssignments')) {
    return folderAnswer({
      d: { HasUniqueRoleAssignments: Boolean(globalThis.__folderScoped) },
    });
  }
  if (requested.includes('/items(') && requested.includes('/breakroleinheritance')) {
    globalThis.__folderScoped = true;
  }
  // Role assignments at FOLDER scope as state, so the phase's read-back sees
  // what it wrote rather than a fixed empty snapshot. `__folderBindingsBlind`
  // accepts every write and reports none, which is what a scope that never
  // catches up looks like from the script's side.
  globalThis.__folderBindings = globalThis.__folderBindings || new Set();
  if (requested.includes('/items(') && requested.includes('/roleassignments/addroleassignment(')) {
    const m = /principalid=(\d+),roleDefId=(\d+)/.exec(requested);
    if (m) globalThis.__folderBindings.add(m[1] + ':' + m[2]);
  }
  if (requested.includes('/items(')
      && requested.includes('/roleassignments/removeroleassignment(')) {
    const m = /principalid=(\d+),roleDefId=(\d+)/.exec(requested);
    // __folderRemovalsIgnored answers the delete and keeps the binding,
    // which is what an accepted but ineffective removal looks like.
    if (m && !globalThis.__folderRemovalsIgnored) {
      globalThis.__folderBindings.delete(m[1] + ':' + m[2]);
    }
  }
  if (requested.includes('/items(') && /\/roleassignments\?/.test(requested)) {
    globalThis.__calls.push({ url: requested, method: opts.method || 'GET', body: null });
    const byPrincipal = new Map();
    if (!globalThis.__folderBindingsBlind) {
      const pairs = [...globalThis.__folderBindings];
      // A binding nobody declared, left behind by an earlier run or a hand
      // edit: what an exact policy has to prune and then prove it pruned.
      if (globalThis.__folderStrayBinding) pairs.push('777:888');
      for (const pair of pairs) {
        const [principalId, roleDefId] = pair.split(':').map(Number);
        if (!byPrincipal.has(principalId)) byPrincipal.set(principalId, []);
        byPrincipal.get(principalId).push({ Id: roleDefId, Name: 'Level ' + roleDefId });
      }
    }
    // Both shapes: the exact-mode allowlist enumeration selects Member/Id
    // and the read-back selects PrincipalId, off the same endpoint.
    const rows = [...byPrincipal].map(([PrincipalId, bindings]) => ({
      PrincipalId,
      Member: { Id: PrincipalId, Title: 'Principal ' + PrincipalId },
      RoleDefinitionBindings: { results: bindings },
    }));
    // One row per page, so a declared binding sits behind a __next the
    // read-back has to follow.
    if (globalThis.__folderBindingsPaged && rows.length > 0) {
      const page = Number((/[?&]fpage=(\d+)/.exec(requested) || [])[1] || 0);
      const payload = { d: { results: rows.slice(page, page + 1) } };
      if (page + 1 < rows.length) {
        payload.d.__next = requested.replace(/&fpage=\d+/, '') + '&fpage=' + (page + 1);
      }
      return folderAnswer(payload);
    }
    return folderAnswer({ d: { results: rows } });
  }
"""


def _library_deploy_js(
    tmp_path: Path, mapping: str, *, titled: bool = True,
    enterprise_reader: str | None = None,
) -> str:
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
        enterprise_reader=enterprise_reader,
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


@pytest.mark.parametrize("types", [[1, 0], [0, 1]])
def test_folder_deploy_diagnoses_the_root_collision_after_a_refused_create(
    tmp_path: Path, types: list[int],
) -> None:
    rows = [
        {"FileSystemObjectType": value,
         "FileRef": "/sites/test/APP_Escalation/"
         + ("Nested/Clinical services" if value else "Clinical services")}
        for value in types
    ]
    harness = _library_harness(declared_folder=True).replace(
        "return folderAnswer({ d: { results: rows } });",
        f"return folderAnswer({{ d: {{ results: {json.dumps(rows)} }} }});",
    )
    harness = harness.replace(
        "globalThis.__folderCreated = true;",
        "throw new Error('folder create refused');",
    )
    summary, _calls, _reads = _run(harness, _library_deploy_js(tmp_path, _FOLDERED_LIBRARY))
    assert any("a file where a folder was declared" in e["error"] for e in summary["errors"])
    assert not any("unexpected folder create" in e["error"] for e in summary["errors"])
    assert summary["foldersCreated"] == []
    assert summary["foldersVerified"] == []


@pytest.mark.parametrize("payload", [
    None, [], "bad", 0, {}, {"FileSystemObjectType": 1},
    {"FileSystemObjectType": 0, "FileRef": "/sites/test/APP_Escalation/Clinical services"},
    {"FileSystemObjectType": 1, "FileRef": "/wrong"},
])
@pytest.mark.parametrize("after_create", [False, True])
def test_folder_deploy_refuses_unestablished_path_items(
    tmp_path: Path, payload: Any, after_create: bool,
) -> None:
    harness = _library_harness(declared_folder=True).replace(
        "return folderAnswer({ d: item });",
        f"return folderAnswer({{ d: {json.dumps(payload)} }});",
    )
    harness = f"globalThis.__folderCreated = {json.dumps(not after_create)};\n" + harness
    summary, calls, _reads = _run(harness, _library_deploy_js(tmp_path, _FOLDERED_LIBRARY))
    assert any("folder item probe" in e["error"] for e in summary["errors"]), summary["errors"]
    assert summary["foldersCreated"] == []
    assert summary["foldersVerified"] == []
    creates = [call for call in calls if '/folders/add(' in call['url']]
    assert len(creates) == int(after_create)


@pytest.mark.parametrize("existing", [False, True])
def test_whole_deploy_verifies_folder_paths_without_unindexed_queries(
    tmp_path: Path, existing: bool,
) -> None:
    harness = _library_harness(declared_folder=True).replace(
        "return folderAnswer({ d: { results: rows } });",
        "throw new Error('SPQueryThrottledException');",
    )
    harness = f"globalThis.__folderCreated = {json.dumps(existing)};\n" + harness
    summary, _calls, _reads = _run(harness, _library_deploy_js(tmp_path, _FOLDERED_LIBRARY))
    assert summary["errors"] == [], summary["errors"]
    key = "foldersVerified" if existing else "foldersCreated"
    assert summary[key] == ["APP_Escalation/Clinical services"]


@pytest.mark.parametrize("next_page", [False, True, 0, 1, [], {}])
def test_descendant_scope_enumeration_rejects_malformed_continuation(
    tmp_path: Path, next_page: Any,
) -> None:
    harness = _library_harness(unique_after=1)
    harness += """
const scopeFetch = globalThis.fetch;
globalThis.fetch = async (url, options) => {
  if (String(url).includes('/items?$select=Id,HasUniqueRoleAssignments')) {
    return {ok: true, status: 200, json: async () => ({d: {
      results: [], __next: NEXT_PAGE
    }})};
  }
  return scopeFetch(url, options);
};
""".replace("NEXT_PAGE", json.dumps(next_page))
    summary, calls, _reads = _run(harness, _library_deploy_js(tmp_path, _BROKEN_INHERITANCE))
    assert any("invalid OData __next" in e["error"] for e in summary["errors"])
    assert not [c for c in calls if "addroleassignment" in c["url"]
                or "removeroleassignment" in c["url"]]


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


@pytest.mark.parametrize("root", ["LegislativeCompliance", "WrongRoot", None])
@pytest.mark.parametrize("existing", [True, False])
def test_declared_library_url_is_created_and_verified(
    tmp_path: Path, root: str | None, existing: bool,
) -> None:
    mapping = _RECURSIVE_VIEW.replace(
        "base_template: 101,", "base_template: 101, internal_name: LegislativeCompliance,",
    )
    harness = _library_harness()
    harness = f"globalThis.__libraryCreated = {json.dumps(existing)};\n" + harness
    harness = harness.replace(
        "if (ABSENT_LIST_TITLES.includes(probeTitle)) {",
        "if (!globalThis.__libraryCreated || ABSENT_LIST_TITLES.includes(probeTitle)) {",
    )
    root_shape = {"ServerRelativeUrl": f"/sites/test/{root}"} if root else {}
    harness = harness.replace(
        "Title: 'adopted', BaseTemplate: 101,",
        f"RootFolder: {json.dumps(root_shape)}, Title: 'adopted', BaseTemplate: 101,",
    )
    anchor = "  const u = String(url);\n"
    creation = r"""
      if (u.endsWith('/web/lists/add')) {
        calls.push({url: u, method: opts.method, body: opts.body, phase: mockPhase});
        globalThis.__libraryCreated = true;
        const payload = { d: { Id: '22222222-2222-2222-2222-222222222222' } };
        return { ok: true, status: 201, json: async () => payload,
          text: async () => JSON.stringify(payload) };
      }
"""
    assert anchor in harness
    harness = harness.replace(anchor, anchor + creation, 1)
    summary, calls, _ = _run(harness, _library_deploy_js(tmp_path, mapping))
    creates = [c for c in calls if c["url"].endswith('/web/lists/add')]
    assert len(creates) == (0 if existing else 1)
    if creates:
        assert json.loads(creates[0]["body"])["parameters"] == {
            "__metadata": {"type": "SP.ListCreationInformation"},
            "Title": "APP_Escalation", "Url": "LegislativeCompliance", "TemplateType": 101,
            "Description": next(row["description"] for row in _schema_lists(
                _library_deploy_js(tmp_path, mapping),
            )),
        }
    if root == "LegislativeCompliance":
        assert summary["errors"] == [], summary["errors"]
        assert any("RootFolder/ServerRelativeUrl" in c["url"] for c in calls)
    else:
        assert "LIBRARY_INTERNAL_NAME_MISMATCH" in str(summary["errors"])
        assert not any(c["method"] == "POST" and "/fields" in c["url"] for c in calls)


def _folder_acl_run(
    tmp_path: Path, *, stray: bool = False, missing: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The whole deploy against a library whose one folder carries an ACL."""
    # `unique_after=1` is what makes the mock answer the inheritance flag
    # at all; both securables read it, the list for its settle loop and
    # the folder for the same wait.
    harness = _library_harness(declared_folder=True, unique_after=1)
    flags = ""
    if stray:
        flags += "globalThis.__strayScope = true;\n"
    if missing:
        flags += "globalThis.__folderMissing = true;\n"
    summary, calls, _ = _run(
        flags + harness,
        _library_deploy_js(tmp_path, _FOLDER_ACL_LIBRARY, titled=False),
    )
    return summary, calls


def test_configured_mode_keeps_every_level_one_principal_is_declared_with(
    tmp_path: Path,
) -> None:
    """Two levels for one principal survive a redeploy that already has both.

    `configured` mode prunes the levels a DECLARED principal holds that the
    mapping does not. Asked per assignment, each pass treated its own level
    as that principal's whole desired state: the pass for the first removed
    the second, the pass for the second removed the first, both off the same
    pre-write snapshot, and the principal ended with neither. The deploy read
    back clean because the snapshot it pruned against was never re-read.
    """
    # Principal 9 is what the mock resolves any group to; 2 and 3 are the two
    # declared levels, in declaration order.
    both = json.dumps({"APP_Escalation": [[{
        "Member": {"Id": 9, "Title": "List Maintainer", "PrincipalType": 8},
        "RoleDefinitionBindings": {"results": [
            {"Id": 2, "Name": "Folder Editor"},
            {"Id": 3, "Name": "Folder Approver"},
        ]},
    }]]})
    harness = _library_harness(declared_folder=True, unique_after=1).replace(
        "const ROLE_ASSIGNMENT_PAGES = {};",
        f"const ROLE_ASSIGNMENT_PAGES = {both};",
    )
    summary, calls, _ = _run(
        harness,
        _library_deploy_js(tmp_path, _TWO_LEVEL_CONFIGURED_LIBRARY, titled=False),
    )

    assert summary["errors"] == [], summary["errors"]
    removals = [
        c["url"] for c in calls if "removeroleassignment" in c.get("url", "")
    ]
    assert removals == [], removals


def test_configured_mode_prunes_a_declared_principal_and_spares_a_stranger(
    tmp_path: Path,
) -> None:
    """Both halves of the configured-mode predicate, in one run.

    Configured mode judges a binding by whether the mapping names its
    PRINCIPAL: a declared principal loses a level the mapping does not
    declare, and a principal the mapping never names keeps every binding it
    holds. This branch now reads the one snapshot rather than probing each
    declared principal, and a predicate wrong in either direction reports the
    same clean run, having stripped a stranger or having pruned nothing.
    """
    # Principal 9 is what the mock resolves any group to, so 7 is a principal
    # this mapping cannot name. 2 and 3 are the two declared levels, in
    # declaration order; 99 is a level it never declares.
    seeded = json.dumps({"APP_Escalation": [[
        {
            "Member": {"Id": 9, "Title": "List Maintainer", "PrincipalType": 8},
            "RoleDefinitionBindings": {"results": [
                {"Id": 2, "Name": "Folder Editor"},
                {"Id": 3, "Name": "Folder Approver"},
                {"Id": 99, "Name": "Full Control"},
            ]},
        },
        {
            "Member": {"Id": 7, "Title": "Stray Group", "PrincipalType": 8},
            "RoleDefinitionBindings": {"results": [
                {"Id": 2, "Name": "Folder Editor"},
            ]},
        },
    ]]})
    harness = _library_harness(declared_folder=True, unique_after=1).replace(
        "const ROLE_ASSIGNMENT_PAGES = {};",
        f"const ROLE_ASSIGNMENT_PAGES = {seeded};",
    )
    summary, calls, _ = _run(
        harness,
        _library_deploy_js(tmp_path, _TWO_LEVEL_CONFIGURED_LIBRARY, titled=False),
    )

    assert summary["errors"] == [], summary["errors"]
    removals = [
        c["url"] for c in calls if "removeroleassignment" in c.get("url", "")
    ]
    assert len(removals) == 1, removals
    assert "removeroleassignment(principalid=9,roleDefId=99)" in removals[0], removals
    assert not any("principalid=7," in url for url in removals), (
        f"a principal the mapping never names lost a binding: {removals}"
    )


def test_exact_mode_prunes_a_stray_binding_and_never_the_derived_one(
    tmp_path: Path,
) -> None:
    """'Limited Access' survives an allowlist that declares neither it nor
    the principal holding it.

    SharePoint derives that binding to support access at a LOWER scope, so
    removing it from the list breaks the folder or item grant it exists for,
    and nothing in the run or in verify.js reads it back afterwards. Both
    rows come off the one snapshot this phase now prunes from, so the exempt
    one and the pruned one are judged by the same pass.
    """
    # The exemption is keyed on the binding's NAME, so the level ids here are
    # arbitrary and the names are not. Neither principal is one the mock
    # resolves a declared group to, which is 9.
    seeded = json.dumps({"APP_Escalation": [[
        {
            "Member": {"Id": 7, "Title": "Stray Group", "PrincipalType": 8},
            "RoleDefinitionBindings": {"results": [
                {"Id": 888, "Name": "Full Control"},
            ]},
        },
        {
            "Member": {"Id": 8, "Title": "Lower Scope Group", "PrincipalType": 8},
            "RoleDefinitionBindings": {"results": [
                {"Id": 889, "Name": "Limited Access"},
            ]},
        },
    ]]})
    harness = _library_harness(declared_folder=True, unique_after=1).replace(
        "const ROLE_ASSIGNMENT_PAGES = {};",
        f"const ROLE_ASSIGNMENT_PAGES = {seeded};",
    )
    summary, calls, _ = _run(
        harness, _library_deploy_js(tmp_path, _FOLDER_ACL_LIBRARY, titled=False),
    )

    assert summary["errors"] == [], summary["errors"]
    removals = [
        c["url"] for c in calls if "removeroleassignment" in c.get("url", "")
    ]
    assert len(removals) == 1, removals
    assert "removeroleassignment(principalid=7,roleDefId=888)" in removals[0], removals
    assert not any("roleDefId=889)" in url for url in removals), (
        f"the derived 'Limited Access' binding was removed: {removals}"
    )


def test_a_folder_lookup_without_an_id_is_refused(tmp_path: Path) -> None:
    """A folder read that answers without an Id must abort, not proceed.

    The id is the whole point of the lookup, and it is the only thing that
    addresses the folder afterwards. Left unchecked the map carried
    `undefined`, every folder endpoint became `items(undefined)`, SharePoint
    answered it, and the phase reported a clean run having secured nothing.
    Found exactly that way: the mock answered the read without an Id.
    """
    harness = _library_harness(declared_folder=True, unique_after=1)
    summary, calls, _ = _run(
        "globalThis.__folderIdMissing = true;\n" + harness,
        _library_deploy_js(tmp_path, _TWO_LEVEL_CONFIGURED_LIBRARY, titled=False),
    )

    assert summary["errors"], "a folder with no addressable id must fail the phase"
    assert any(
        "no usable list item Id" in e["error"] for e in summary["errors"]
    ), summary["errors"]
    assert not any("items(undefined)" in c.get("url", "") for c in calls)


def test_a_declared_folder_gets_its_own_acl(tmp_path: Path) -> None:
    """The folder is secured as its own list item, addressed by id.

    A folder is not itself a SecurableObject -- Microsoft Learn derives
    SecurableObject as List, ListItem and Web -- so the grant goes on the
    folder's list item. Addressed by `items(<id>)` rather than by
    server-relative path, which keeps the write inside the ownership bracket
    that proves the title still resolves to the surveyed list. In exact mode
    the id falls out of the descendant-scope enumeration the phase already
    runs; configured mode has no enumeration and resolves it by path.
    """
    summary, calls = _folder_acl_run(tmp_path)
    assert summary["errors"] == [], summary["errors"]
    urls = [c["url"] for c in calls]
    assert any(
        "/items(1)/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)"
        in u for u in urls
    ), "the folder's inheritance was never broken"
    assert any(
        "/items(1)/roleassignments/addroleassignment(" in u for u in urls
    ), "the folder grant was never written"
    # The list's own ACL is untouched by the folder pass: two securables, one
    # rule, and neither addressed through the other.
    assert any(
        u.endswith("/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)")
        and "/items(" not in u for u in urls
    ), "the list's own inheritance break went missing"

    # The guard runs again AFTER the folder pass, by which point the folder
    # reads HasUniqueRoleAssignments=true because this run just broke it. A
    # clean summary is therefore the assertion that matters most in this
    # module: without the declared-scope exclusion, the very next deploy
    # would abort forever on the phase's own work.
    surveys = [
        u for u in urls if "FileSystemObjectType" in u and "/items(" not in u
    ]
    assert len(surveys) >= 2, surveys


def test_a_folder_that_no_longer_reads_back_at_its_path_is_refused(
    tmp_path: Path,
) -> None:
    """The id is resolved before the write bracket, so it is re-proved inside it.

    `withOwnedList` proves the LIST's identity and nothing below it. A title
    rebound between the lookup and the write could hand back an id from a
    replacement library, and restoring the title afterwards leaves that
    numeric suffix addressing an unrelated item of the intended one, whose
    ACL would then be rewritten. Nothing further down can see that, so the
    item is re-read inside the bracket and the phase fails closed.
    """
    harness = _library_harness(declared_folder=True, unique_after=1)
    summary, calls, _ = _run(
        "globalThis.__folderIdentity = { FileSystemObjectType: 0,"
        " FileRef: '/sites/test/APP_Escalation/stray.docx' };\n" + harness,
        _library_deploy_js(tmp_path, _TWO_LEVEL_CONFIGURED_LIBRARY, titled=False),
    )

    messages = [e["error"] for e in summary["errors"]]
    assert any("no longer reads back as a folder" in m for m in messages), messages
    assert any("nothing was written to it" in m for m in messages), messages
    # Fails closed: the refusal comes before any write to that item.
    assert not any(
        "/items(" in c.get("url", "")
        and ("roleassignment" in c.get("url", "") or "breakroleinheritance" in c.get("url", ""))
        for c in calls
    ), [c.get("url") for c in calls]


#: The folder group carries the reader flag and is granted NOTHING at list
#: scope, which is the shape that made the enrolment preflight read an empty
#: level list and enrol the account without judging any bitmap.
_FOLDER_ONLY_READER_LIBRARY = _TWO_LEVEL_CONFIGURED_LIBRARY.replace(
    '  - name: "Clinical services Editors"\n'
    "    description: \"One folder's editors.\"\n"
    '    owner_group: "Site Owners"\n',
    '  - name: "Clinical services Editors"\n'
    "    description: \"One folder's editors.\"\n"
    '    owner_group: "Site Owners"\n'
    "    enroll_enterprise_reader: true\n",
)


def test_a_reader_granted_only_inside_the_folders_has_its_level_judged(
    tmp_path: Path,
) -> None:
    """The enrolment preflight reads the folder grants, not the list ones alone.

    `ENTERPRISE_READER_GROUP_NOT_GRANTED` counts a folder grant, so a mapping
    granting the reader only inside the folders builds. The preflight read
    `list_assignments` alone, found nothing, took the branch that says the
    group grants nothing here, skipped the bitmap check and enrolled the
    account permanently into a level nothing had judged.

    'Folder Editor' carries neither ViewFormPages nor Open, so a preflight
    that looks at it has to abort. A clean run is this test failing.
    """
    js = _library_deploy_js(
        tmp_path, _FOLDER_ONLY_READER_LIBRARY, titled=False,
        enterprise_reader="reader@example.com",
    )
    output = _run_output(_library_harness(declared_folder=True, unique_after=1), js)

    assert "Folder Editor' on this site does not grant" in output, output[-3000:]
    assert "granted no permission level" not in output, (
        "the preflight took the no-grant branch although the folders grant the reader"
    )
    summary = _summary_of(output)
    assert [e for e in summary["errors"] if str(e.get("phase")) == "1.6"], summary["errors"]
    # Nothing was created: the abort comes before list creation, so the
    # account is not left holding a level this run never judged.
    assert summary["listsCreated"] == []


def test_a_folder_that_never_reports_its_bindings_is_refused(tmp_path: Path) -> None:
    """HTTP 200 on the write is evidence the request was accepted, not that
    the folder holds the grant.

    Nothing downstream would catch it: verify.js reads lists, columns and
    views and never role assignments, so a write that did not take left an
    operator with a green run and a folder the division cannot reach. The
    mock accepts every write and reports none, which is what that looks like
    from the script's side.
    """
    harness = _library_harness(declared_folder=True, unique_after=1)
    summary, calls, _ = _run(
        "globalThis.__folderBindingsBlind = true;\n" + harness,
        _library_deploy_js(tmp_path, _TWO_LEVEL_CONFIGURED_LIBRARY, titled=False),
    )

    messages = [e["error"] for e in summary["errors"]]
    assert any("does not report" in m for m in messages), messages
    assert any("nothing was removed" in m for m in messages), messages
    # The read-back is a read: it must not have pruned anything on its way to
    # deciding the grant is missing.
    assert not any("removeroleassignment" in c.get("url", "") for c in calls)


def test_a_folder_removal_that_did_not_take_is_refused(tmp_path: Path) -> None:
    """An exact policy has to prove what it REMOVED, not only what it added.

    `removeroleassignment` answering HTTP 200 is evidence the request was
    accepted. A stale principal that survives it keeps access to the folder
    on a run that reports success, which is the half a presence-only
    read-back could not see.
    """
    harness = _library_harness(declared_folder=True, unique_after=1)
    summary, calls, _ = _run(
        "globalThis.__folderStrayBinding = true;\n"
        "globalThis.__folderRemovalsIgnored = true;\n" + harness,
        _library_deploy_js(tmp_path, _FOLDER_ACL_LIBRARY, titled=False),
    )

    messages = [e["error"] for e in summary["errors"]]
    assert any("does not declare" in m for m in messages), messages
    assert any("777:888" in m for m in messages), messages
    # It tried: the refusal is about the removal not taking, not about
    # never having been attempted.
    assert any("removeroleassignment" in c.get("url", "") for c in calls)


def test_a_folder_binding_on_a_later_page_is_found(tmp_path: Path) -> None:
    """The read-back pages to the end, like the allowlist enumeration.

    A capped read is a PARTIAL view. Treating a second page as absence fails
    a folder whose declared bindings are all present, and it fails it after
    the ACL has already been modified, so every retry does the same.
    """
    harness = _library_harness(declared_folder=True, unique_after=1)
    summary, calls, _ = _run(
        "globalThis.__folderBindingsPaged = true;\n"
        "globalThis.__folderStrayBinding = true;\n" + harness,
        _library_deploy_js(tmp_path, _TWO_LEVEL_CONFIGURED_LIBRARY, titled=False),
    )

    assert summary["errors"] == [], summary["errors"]
    followed = [c["url"] for c in calls if "fpage=" in c.get("url", "")]
    assert followed, "the read-back never followed a next-page link"


def test_a_folder_that_never_reports_its_grants_is_refused_before_pruning(
    tmp_path: Path,
) -> None:
    """Order matters, because breaking inheritance with
    copyRoleAssignments=false can leave the operator's own binding as the
    only way back in.

    Pruning first and finding out afterwards that the declared
    administrators never landed is how a folder gets locked with nobody in
    it. Verified first, the phase aborts with every existing binding still
    in place.
    """
    harness = _library_harness(declared_folder=True, unique_after=1)
    summary, calls, _ = _run(
        "globalThis.__folderBindingsBlind = true;\n"
        "globalThis.__folderStrayBinding = true;\n" + harness,
        _library_deploy_js(tmp_path, _FOLDER_ACL_LIBRARY, titled=False),
    )

    messages = [e["error"] for e in summary["errors"]]
    assert any("does not report" in m for m in messages), messages
    folder_removals = [
        c["url"] for c in calls
        if "/items(" in c.get("url", "") and "removeroleassignment" in c.get("url", "")
    ]
    assert folder_removals == [], folder_removals


def test_an_undeclared_descendant_scope_still_aborts(tmp_path: Path) -> None:
    """Declaring folder ACLs must not blunt the guard.

    The whole risk of teaching this phase to create descendant scopes is that
    it stops noticing the ones nobody asked for -- a file somebody shared by
    hand, which is how SharePoint breaks inheritance behind an operator's
    back. The scope is named by path, and nothing is erased.
    """
    summary, calls = _folder_acl_run(tmp_path, stray=True)
    messages = [e["error"] for e in summary["errors"]]
    assert any("undeclared item/folder unique permission scope" in m for m in messages), \
        messages
    assert any("stray.docx" in m for m in messages), messages
    # Never erased, only reported.
    assert not any("removeroleassignment" in c["url"] for c in calls)


def test_a_declared_folder_that_does_not_exist_is_refused(tmp_path: Path) -> None:
    """The branch that only runs when the folder phase has not done its job.

    Without it the folder id reads `undefined`, the phase writes to
    `items(undefined)`, and what the operator gets is a REST parse error
    rather than the sentence naming the folder (#454 is the same shape: an
    abort path whose own diagnosis threw).
    """
    summary, calls = _folder_acl_run(tmp_path, missing=True)
    messages = [e["error"] for e in summary["errors"]]
    assert any("declared folder 'Clinical services' was not found" in m for m in messages), \
        messages
    assert not any("items(undefined)" in c["url"] for c in calls)
