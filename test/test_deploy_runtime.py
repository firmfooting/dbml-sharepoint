# test/test_deploy_runtime.py
"""Execute the generated deploy.js against a mock SharePoint.

The golden-file test proves deploy.js does not CHANGE; it cannot prove it
RUNS. A whole class of defect lives in that gap — a caller that omits a
key another function requires, a comparison against `undefined`, a
sentinel that reads as a real value. One such bug shipped in the golden
fixture and was asserted as correct: the synthetic Title patch carried
none of the declared-formula keys, so every field reconcile treated it as
managed and aborted the phase on every list, on every run.

Node is required; the test skips without it rather than failing, since it
is not a dependency of the package.
"""

import json
import re
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any
from urllib.parse import quote

import pytest
from _builders import ID_PK, table
from _node import NODE
from _node import run_node as _run
from _packs import DEFAULT_PREFIX, blocks, entities, pack
from _paths import FIXTURES

from dbml_sharepoint.analysis.phases import phase_number as pn


def _deploy_js() -> str:
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.parser import parse_dbml
    from dbml_sharepoint.model.release import load_release

    return generate_deploy_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )


# A SharePoint that answers every read as an EMPTY, healthy list: no fields
# exist, no formulas are set. That is the state of a brand-new site, and the
# state in which the shipped bug threw.
_HARNESS = textwrap.dedent("""
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const body = (url) => {
      if (url.includes('contextinfo')) {
        return { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } };
      }
      if (url.toLowerCase().includes('effectivebasepermissions')) {
        return { d: { EffectiveBasePermissions: { High: 4294967295, Low: 4294967295 } } };
      }
      if (url.includes('ClientValidationFormula') || url.includes('ValidationFormula')) {
        return { d: {
          ClientValidationFormula: null, ClientValidationMessage: null,
          ValidationFormula: null, ValidationMessage: null } };
      }
      return { d: { results: [] } };
    };
    globalThis.fetch = async (url, opts = {}) => {
      // body is null, never absent: JSON.stringify drops an undefined key,
      // and the Python side reads c['body'] unconditionally.
      calls.push({ url: String(url), method: opts.method || 'GET',
                   body: opts.body === undefined ? null : opts.body });
      return {
        ok: true, status: 200,
        headers: { get: () => null },
        json: async () => body(String(url)),
        text: async () => JSON.stringify(body(String(url))),
      };
    };
    globalThis.__calls = calls;
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_deploy_js_runs_without_throwing() -> None:
    """The generated script must reach a summary against a healthy site.

    It need not succeed at provisioning — the mock is too thin for that —
    but a thrown exception or an abort carrying schema errors means the
    script is broken for every operator on every site.
    """
    script = _HARNESS + "\n" + _deploy_js().replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))"
        ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(result_line.removeprefix("__RESULT__"))
    # The mock is deliberately thin, so shape probes legitimately complain.
    # What must never appear is a formula error: that is the phase-aborting
    # failure the synthetic Title patch produced on every list, every run,
    # and it is invisible to a golden-file comparison.
    formula_errors = [
        err for err in (summary.get("errors") or [])
        if "ValidationFormula" in str(err) or "ValidationMessage" in str(err)
    ]
    assert not formula_errors, f"deploy.js aborted on the declared formulas: {formula_errors}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_builtin_title_column_is_never_sent_a_formula() -> None:
    """Title is not a declared field, so the tool does not own its
    formulas. The shipped bug MERGEd an empty ClientValidationMessage onto
    it before aborting — an unrequested write to a built-in column."""
    script = _HARNESS + "\n" + _deploy_js().replace(
        "})();", "}))().then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
        ).replace("(async () => {", "((async () => {", 1)
    line = next(
        (ln for ln in _run(script).splitlines() if ln.startswith("__CALLS__")),
        None,
    )
    assert line is not None, "harness produced no call log"
    calls = json.loads(line.removeprefix("__CALLS__"))
    title_writes = [
        c for c in calls
        if c["method"] == "POST" and c["body"] and "ValidationMessage" in c["body"]
        and "'Title'" in c["url"]
    ]
    assert not title_writes, (
        f"wrote formula properties to the built-in Title column: {title_writes}"
    )


# An ADOPTED site: the lists already exist and the built-in Title is
# SEALED. The harness above answers every field probe as absent, so the
# adoption path — the one where declared shapes are actually compared —
# has never executed in a test. That is the gap the synthetic-Title bug
# shipped through.
_ADOPTED_HARNESS = textwrap.dedent(r"""
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    // Per-list Description state, mutated by MERGEs exactly as SharePoint
    // would, so the list probe reads back what was actually written and a
    // run can never satisfy its own read-back. Default '' is the honest
    // pre-marker state: a list provisioned before descriptions were written,
    // or one an owner blanked, which is exactly what the reconcile repairs.
    // Both constants are rewritten by _run_adopted_deploy.
    const LIST_DESCRIPTIONS = {};
    const IGNORE_DESCRIPTION_WRITES = false;
    const listDescription = (listTitle) => (
      LIST_DESCRIPTIONS[listTitle] == null ? '' : LIST_DESCRIPTIONS[listTitle]
    );
    // Per-group Description and paginated membership, keyed by group Title.
    // A name with no entry keeps the prior fixed shape (Description 'Test
    // group.', no members), so every existing test is unaffected. Rewritten
    // by _group_gate_deploy for the adoption-gate tests.
    const GROUP_DESCRIPTIONS = {};
    const GROUP_MEMBER_PAGES = {};
    // The site-group enumeration (web/sitegroups?$select=Title) that decides
    // whether a declared group reads as pre-existing or absent. Empty by
    // default, matching every other test's "brand-new site" fiction for
    // groups: the ADOPT branch below is otherwise unreachable, because the
    // enumeration fast path answers every declared group 404 before the
    // by-name probe this override targets ever runs.
    const KNOWN_GROUP_NAMES = [];
    const groupDescription = (name) => (
      GROUP_DESCRIPTIONS[name] == null ? 'Test group.' : GROUP_DESCRIPTIONS[name]
    );
    const groupMemberPages = (name) => GROUP_MEMBER_PAGES[name] || [[]];
    const groupNameOf = (url) => {
      const raw = (url.match(/sitegroups\/getbyname\('(.*?)'\)/) || [])[1];
      return raw == null ? raw : decodeURIComponent(raw).replace(/''/g, "'");
    };
    // Task 7 read-back verification. A group's write endpoints (create and
    // MERGE) mutate GROUP_STATE the same way the list write above mutates
    // LIST_DESCRIPTIONS, so verifyGroupSettings reads back what the mock
    // actually stored rather than a shape fixed in advance.
    // GROUP_DROP_FIELD_ON_WRITE names one property the tenant accepts but
    // never stores, modelling a write SharePoint 200s and discards.
    // GROUP_COERCE_AUTO_ACCEPT models the measured tenant behaviour
    // (test/manual/group-description-probe.js, G9/G10, 2026-08-13/14):
    // AutoAcceptRequestToJoinLeave is forced false whenever the written
    // AllowRequestToJoinLeave is false, regardless of what was sent for
    // AutoAccept itself.
    const GROUP_DROP_FIELD_ON_WRITE = null;
    const GROUP_COERCE_AUTO_ACCEPT = false;
    const GROUP_SETTINGS_KEYS = ['Description', 'AllowMembersEditMembership',
      'AllowRequestToJoinLeave', 'AutoAcceptRequestToJoinLeave',
      'OnlyAllowMembersViewMembership'];
    const GROUP_STATE = {};
    const groupState = (name) => (GROUP_STATE[name] ||= {
      Description: groupDescription(name), AllowMembersEditMembership: false,
      AllowRequestToJoinLeave: false, AutoAcceptRequestToJoinLeave: false,
      OnlyAllowMembersViewMembership: false,
    });
    // Per-list Title state, mutated by MERGEs exactly as SharePoint would.
    const titles = {};
    const titleState = (listTitle) => (titles[listTitle] ||= {
      Sealed: true, Required: true, Description: '', DefaultValue: null,
    });
    const titleField = (listTitle) => ({
      Id: '11111111-1111-1111-1111-111111111111',
      InternalName: 'Title', Title: 'Title', TypeAsString: 'Text',
      EnforceUniqueValues: false, Indexed: false, ReadOnlyField: false,
      CustomFormatter: null, ...titleState(listTitle),
    });
    // Created fields persist, so the run converges instead of failing
    // "missing after creation" and aborting before PROTECTION. Without
    // this the mock could never execute a phase past list creation.
    const TYPE_BY_KIND = { 2: 'Text', 3: 'Note', 4: 'DateTime', 6: 'Choice',
      7: 'Lookup', 8: 'Boolean', 9: 'Number', 11: 'URL', 20: 'User',
      17: 'Calculated' };
    const created = {};   // `${list} ${title}` -> shape
    // The list title out of a URL, back in the spelling the declaration uses.
    // `[^']+` would stop at the first apostrophe of an OData-escaped title
    // (odataName doubles `'`, and encodeURIComponent does not touch it), so
    // `O'Brien Register` keyed as `O` and every per-list mock state silently
    // went to the wrong bucket. Non-greedy to the first `')`, then undo the
    // two encodings in the order odataName applied them: percent first,
    // doubling second.
    const listOf = (url) => {
      const raw = (url.match(/getbytitle\('(.*?)'\)/) || [])[1];
      return raw == null ? raw : decodeURIComponent(raw).replace(/''/g, "'");
    };
    const views = {};
    const viewOf = (url) => {
      const match = url.match(/\/views\/getbytitle\('([^']+)'\)/);
      return match && match[1];
    };
    const viewState = (listTitle, title = 'All Items') => (
      views[`${listTitle} ${title}`] ||= {
        Id: '44444444-4444-4444-4444-444444444444',
        Title: title, DefaultView: true, RowLimit: 30, ViewQuery: '',
        Hidden: false, PersonalView: false, CustomFormatter: null,
        ServerRelativeUrl: `/sites/test/Lists/${listTitle}/AllItems.aspx`,
        ViewFields: { Items: { results: ['Title'] } },
      }
    );
    const fieldShape = (listTitle, name, b) => ({
      Id: '33333333-3333-3333-3333-333333333333',
      InternalName: name, Title: name,
      TypeAsString: TYPE_BY_KIND[b.FieldTypeKind] || 'Text',
      Description: b.Description == null ? '' : b.Description,
      Required: b.Required === true,
      EnforceUniqueValues: b.EnforceUniqueValues === true,
      Indexed: b.EnforceUniqueValues === true,
      ReadOnlyField: b.FieldTypeKind === 17,
      Sealed: false,
      DefaultValue: b.DefaultValue == null ? null : b.DefaultValue,
      CustomFormatter: b.CustomFormatter == null ? null : b.CustomFormatter,
      __body: b,
    });
    const body = (url, opts) => {
      if (url.includes('contextinfo')) {
        return { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } };
      }
      if (url.toLowerCase().includes('effectivebasepermissions')) {
        return { d: { EffectiveBasePermissions: { High: 4294967295, Low: 4294967295 } } };
      }
      // A field probe or enumeration. Title exists from the start (it is
      // the adopted, sealed one); everything else appears once created.
      // Checked BEFORE the list probe, whose own $select also names
      // ValidationFormula.
      if (url.includes('/fields')) {
        const listTitle = listOf(url);
        if (url.includes('ClientValidationFormula')) {
          const probed = (url.match(/getbyinternalnameortitle\('([^']+)'\)/) || [])[1];
          const f = created[`${listTitle} ${probed}`] || {};
          return { d: {
            ClientValidationFormula: f.__cvf == null ? null : f.__cvf,
            ClientValidationMessage: null,
            ValidationFormula: f.__vf == null ? null : f.__vf,
            ValidationMessage: f.__vm == null ? null : f.__vm } };
        }
        const named = (url.match(/getbyinternalnameortitle\('([^']+)'\)/) || [])[1];
        if (named === 'Title') return { d: titleField(listTitle) };
        if (named) {
          const f = created[`${listTitle} ${named}`];
          if (!f) return { error: { code: '-2147024809, System.ArgumentException' } };
          // A derived-property probe (MaxLength, Choices, DisplayFormat...)
          // names none of the shape columns; echo what the field was
          // created with, which is what the declaration asked for.
          if (!url.includes('InternalName')) return { d: f.__body };
          return { d: f };
        }
        const own = Object.entries(created)
          .filter(([k]) => k.startsWith(`${listTitle} `))
          .map(([, v]) => v);
        return { d: { results: [titleField(listTitle), ...own] } };
      }
      // Principals: enough shape to get PREPARE past 1.2/1.3 and reach the
      // maintenance unseal at 1.4. Before this, the runtime test had never
      // executed a phase beyond the read-only preflight.
      if (url.includes('AssociatedOwnerGroup') || url.includes('AssociatedMemberGroup')
          || url.includes('AssociatedVisitorGroup') || url.includes('/owner')) {
        return { d: { Id: 3, Title: 'Site Owners', PrincipalType: 8 } };
      }
      // The site-group enumeration the security phase uses to decide
      // create-vs-adopt without a per-group 404 probe. Checked before the
      // by-name probe below, whose URL also contains 'sitegroups' but not
      // this exact query shape.
      if (url.includes('web/sitegroups?')) {
        return { d: { results: KNOWN_GROUP_NAMES.map((name) => ({ Title: name })) } };
      }
      // A group's own membership, by NAME (the shape countGroupMembers and
      // require_empty_at_deploy both read) and paginated the same way the
      // reader-enrolment mock pages sitegroups(N)/users: page 0 unless the
      // caller followed a __next this mock handed out.
      if (url.includes('/users')) {
        const name = groupNameOf(url);
        const pages = groupMemberPages(name);
        const marked = /[?&]page=(\d+)/.exec(url);
        const page = marked ? Number(marked[1]) : 0;
        const payload = { d: { results: pages[page] || [] } };
        if (page + 1 < pages.length) {
          payload.d.__next =
            `https://example.sharepoint.com/_api/web/sitegroups/getbyname('${encodeURIComponent(name)}')`
            + `/users?$select=Id&$top=5000&page=${page + 1}`;
        }
        return payload;
      }
      if (url.includes('sitegroups/getbyname')) {
        const name = groupNameOf(url);
        return { d: { Id: 9, Title: name, PrincipalType: 8, ...groupState(name) } };
      }
      if (url.includes('roledefinitions')) return { d: { results: [{ Id: 1 }] } };
      // The adopted list starts with SharePoint's built-in Title-only All
      // Items view. View writes below mutate this state so exact field/query
      // readback exercises the generated recovery-view behavior.
      if (url.includes('/views?')) {
        const listTitle = listOf(url);
        return { d: { results: [viewState(listTitle)] } };
      }
      if (url.includes('/views/getbytitle')) {
        const state = viewState(listOf(url), viewOf(url));
        if (url.includes('/viewfields')) return { d: state.ViewFields };
        return { d: state };
      }
      // The single list ENUMERATION. This mock's fiction is "any list probe
      // succeeds", which an enumeration cannot express — it would have to
      // know the declared names. Refusing it exercises the documented
      // fallback in ensureKnownListTitles: enumeration unavailable, probe
      // per list. The fast path itself is NOT covered here.
      if (url.includes('web/lists?')) return { error: { code: 'enumeration-not-mocked' } };
      // A list probe: the list exists, matching the declared shape.
      if (url.includes('getbytitle') && url.includes('BaseTemplate')) {
        return { d: {
          Id: '22222222-2222-2222-2222-222222222222',
          Title: 'adopted', BaseTemplate: 100, ContentTypesEnabled: false,
          Description: listDescription(listOf(url)),
          EnableVersioning: true, EnableMinorVersions: false,
          MajorVersionLimit: 500, ValidationFormula: null, ValidationMessage: null } };
      }
      return { d: { results: [] } };
    };
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      // body is null, never absent: JSON.stringify drops an undefined key,
      // and the Python side reads c['body'] unconditionally.
      calls.push({ url: u, method: opts.method || 'GET',
                   body: opts.body === undefined ? null : opts.body });
      // Apply writes, exactly as SharePoint would, so readbacks converge.
      if ((opts.method || 'GET') === 'POST' && opts.body && u.includes('/fields')) {
        const parsed = JSON.parse(opts.body);
        const listTitle = listOf(u);
        const named = (u.match(/getbyinternalnameortitle\('([^']+)'\)/) || [])[1];
        if (named === 'Title') {
          for (const k of ['Sealed', 'Required', 'Description', 'DefaultValue']) {
            if (parsed[k] !== undefined) titleState(listTitle)[k] = parsed[k];
          }
        } else if (named) {
          const key = `${listTitle} ${named}`;
          const f = created[key];
          if (f) {
            if (parsed.Sealed != null) f.Sealed = parsed.Sealed;
            if (parsed.ClientValidationFormula != null) f.__cvf = parsed.ClientValidationFormula;
            if (parsed.ValidationFormula != null) f.__vf = parsed.ValidationFormula;
            if (parsed.ValidationMessage != null) f.__vm = parsed.ValidationMessage;
            for (const k of ['Description', 'Required', 'DefaultValue', 'CustomFormatter']) {
              if (parsed[k] !== undefined) f[k] = parsed[k];
            }
          }
        } else if (parsed.Title) {
          created[`${listTitle} ${parsed.Title}`] = fieldShape(listTitle, parsed.Title, parsed);
        }
      }
      // A MERGE onto the LIST object itself. The URL ends at getbytitle(...)
      // with nothing after it, which is what separates a list write from a
      // field or view write under the same list. `[^/]*` rather than `[^']+`
      // for the title: odataName DOUBLES an apostrophe, so `[^']+` would miss
      // every list whose name has one and this mock would silently drop the
      // write while answering 200 — see _LIST_WRITE_URL for the full note.
      // IGNORE_DESCRIPTION_WRITES drops it on purpose instead: a write
      // SharePoint reports as 200 and discards, which is the only state in
      // which the read-back can be watched failing.
      if ((opts.method || 'GET') === 'POST' && opts.body
          && /getbytitle\('[^/]*'\)$/.test(u)) {
        const parsed = JSON.parse(opts.body);
        if (parsed.Description !== undefined && !IGNORE_DESCRIPTION_WRITES) {
          LIST_DESCRIPTIONS[listOf(u)] = parsed.Description;
        }
      }
      if ((opts.method || 'GET') === 'POST' && u.includes('/views/getbytitle')) {
        const state = viewState(listOf(u), viewOf(u));
        if (u.includes('/viewfields/removeallviewfields')) {
          state.ViewFields.Items.results = [];
        } else {
          const added = (u.match(/addviewfield\('([^']+)'\)/) || [])[1];
          if (added) {
            state.ViewFields.Items.results.push(added);
          } else if (opts.body) {
            const parsed = JSON.parse(opts.body);
            for (const key of ['Title', 'DefaultView', 'Hidden', 'RowLimit', 'ViewQuery']) {
              if (parsed[key] !== undefined) state[key] = parsed[key];
            }
          }
        }
      }
      // A group create (POST to .../web/sitegroups) or a MERGE onto the
      // group object itself (POST to .../sitegroups/getbyname('...') with
      // nothing after the closing paren, so a membership write to the same
      // group's /users does not match). Mutates GROUP_STATE so
      // verifyGroupSettings's read-back sees what this write actually
      // stored, applying GROUP_DROP_FIELD_ON_WRITE and
      // GROUP_COERCE_AUTO_ACCEPT.
      if ((opts.method || 'GET') === 'POST' && opts.body
          && (u.endsWith('/sitegroups') || /sitegroups\/getbyname\('.*'\)$/.test(u))) {
        const parsed = JSON.parse(opts.body);
        if (parsed.__metadata && parsed.__metadata.type === 'SP.Group') {
          const name = u.endsWith('/sitegroups') ? parsed.Title : groupNameOf(u);
          const state = groupState(name);
          for (const key of GROUP_SETTINGS_KEYS) {
            if (parsed[key] === undefined || key === GROUP_DROP_FIELD_ON_WRITE) continue;
            state[key] = parsed[key];
          }
          if (GROUP_COERCE_AUTO_ACCEPT && !state.AllowRequestToJoinLeave) {
            state.AutoAcceptRequestToJoinLeave = false;
          }
        }
      }
      const payload = body(u, opts);
      const absent = payload && payload.error;
      return {
        ok: !absent, status: absent ? 400 : 200,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
    globalThis.__calls = calls;
""")


def _run_deploy(harness: str, tail: str) -> str:
    script = harness + "\n" + _deploy_js().replace("})();", tail).replace(
        "(async () => {", "((async () => {", 1,
    )
    return _run(script)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_sealed_builtin_title_does_not_abort_every_list() -> None:
    """`assertFieldImmutableShape` throws when a field is sealed and
    `field.seal` is falsy. Both synthetic Title objects omitted the key, so
    against a site whose Title is sealed EVERY list failed preflight — and
    the tool could not self-heal, because the maintenance unseal walks
    declared columns only and Title is not one. A site that ever sealed
    Title was permanently un-deployable."""
    output = _run_deploy(
        _ADOPTED_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))
    seal_errors = [
        err for err in (summary.get("errors") or []) if "sealed" in str(err)
    ]
    assert not seal_errors, f"a sealed built-in Title aborted the run: {seal_errors}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_sealed_title_is_unsealed_for_the_run() -> None:
    """Not aborting is not enough to make the site deployable: Phase 2.1
    writes list.title_patch to Title, and a sealed column discards writes.
    The maintenance unseal walked declared columns only, and Title is not
    one, so the run could never converge. It must open Title too."""
    output = _run_deploy(
        _ADOPTED_HARNESS,
        "}))().then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert line is not None, f"harness produced no call log:\n{output[-3000:]}"
    calls = json.loads(line.removeprefix("__CALLS__"))
    seal_writes = [
        json.loads(c["body"])["Sealed"]
        for c in calls
        if c["method"] == "POST" and c.get("body")
        and "getbyinternalnameortitle('Title')" in c["url"]
        and "Sealed" in c["body"]
    ]
    assert False in seal_writes, "a sealed Title was never unsealed for the run"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_adopted_run_reaches_the_write_phases() -> None:
    """Guards the reach of the harness itself.

    The original mock answered every field probe as absent and every list
    probe as malformed, so the run aborted in the read-only preflight: no
    phase past 1.1 had ever executed in a test, which is how a bug in the
    Phase 2.1 field reconcile shipped in a green suite. If a future change
    quietly shortens this run, the coverage disappears silently — so the
    reach is asserted rather than assumed."""
    output = _run_deploy(
        _ADOPTED_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    reached = [ln.split("Starting Phase ")[1][:3] for ln in output.splitlines()
               if "Starting Phase " in ln]
    # `unseal` by key, not by number: the enterprise-reader step renumbered
    # it once already, and this test is about REACH, not about numbering
    # (which test_phases pins).
    for phase in ("1.1", "1.2", "1.3", pn("unseal"), "2.1"):
        assert phase in reached, f"phase {phase} not reached: {reached}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_protection_restores_only_the_titles_prepare_unsealed(tmp_path: Path) -> None:
    """The tool does not own Title's seal state, so a run that unseals one
    must hand back what it found: it must neither seal a Title it found
    unsealed nor leave open one it opened to write."""
    js = _declared_deploy_js(
        tmp_path,
        """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
        """,
    )
    script = _ADOPTED_HARNESS + "\n" + js.replace(
        "})();", "}))().then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
    ).replace("(async () => {", "((async () => {", 1)
    line = next(
        (ln for ln in _run(script).splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert line is not None, "harness produced no call log"
    calls = json.loads(line.removeprefix("__CALLS__"))
    seal_writes = [
        json.loads(c["body"])["Sealed"]
        for c in calls
        if c["method"] == "POST" and c.get("body")
        and "getbyinternalnameortitle('Title')" in c["url"]
        and "Sealed" in c["body"]
    ]
    assert seal_writes[0] is False, f"PREPARE did not unseal Title: {seal_writes}"
    assert seal_writes[-1] is True, f"the run left Title unsealed: {seal_writes}"


# A POST to the LIST object itself: the path ends at getbytitle(...) with
# nothing after it. Anchored deliberately. A FIELD MERGE is a POST to
# `web/lists/getbytitle('X')/fields/getbyinternalnameortitle('Y')` and
# routinely carries a Description of its own (every column with a note has
# one), so a filter that only asks for `web/lists` in the URL counts column
# descriptions as list writes — and then no run can ever be observed NOT
# writing a list description, which is half of what these tests measure.
#
# The title is matched as `[^/]*`, NOT `[^']+` and NOT `.*`, and both of the
# rejected spellings are wrong in a way that passes:
#
#   [^']+  cannot match an OData-escaped apostrophe. `odataName`
#          (`_site_guard.js.j2`) DOUBLES `'` and encodeURIComponent leaves it
#          alone, so a list called `O'Brien Register` arrives as
#          getbytitle('O''Brien%20Register') — no match, so the idempotence
#          test observes zero writes for the happiest of reasons and passes.
#   .*     matches too much: greedy backtracking lets it swallow
#          `X')/fields/getbyinternalnameortitle('Y` and call a FIELD write a
#          list write, which is the false positive this anchor exists to stop.
#
# A SharePoint list title cannot contain `/`, and encodeURIComponent would
# percent-encode one anyway, so "no slash after the opening quote" separates
# the list object from everything nested under it. Both directions are pinned
# by test_the_list_write_matcher_survives_an_apostrophe.
_LIST_WRITE_URL = re.compile(r"web/lists/getbytitle\('[^/]*'\)$")


def _description_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every request that MERGEs a Description onto a list."""
    return [
        c for c in calls
        if c["method"] == "POST" and c["body"] and "Description" in c["body"]
        and _LIST_WRITE_URL.search(c["url"])
    ]


def _declared_list_descriptions(
    tmp_path: Path, prefix: str = DEFAULT_PREFIX,
) -> dict[str, str]:
    """List title -> the Description `_declared_deploy_js` declares for it.

    Read out of the generator, off the SAME pack the script is built from,
    rather than re-spelled here: a second copy of the fixture would drift,
    and a declared-against-live test comparing two different fixtures proves
    nothing. Returns a mapping rather than one string because the marker
    embeds the entity name, so no single value can be "the declared
    description" for more than one list.
    """
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _declared_pack(tmp_path, "", prefix)
    schema_json = build_schema_json(schema, bundle, "default")
    return {entry["title"]: entry["description"] for entry in schema_json["lists"]}


def _run_adopted_deploy(
    tmp_path: Path,
    list_description: str | dict[str, str],
    *,
    ignore_description_writes: bool = False,
    prefix: str = DEFAULT_PREFIX,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run the emitted deploy against a site whose lists already exist.

    Built on `_declared_deploy_js`, not on the shipped `simple.dbml` fixture.
    That matters for the abort assertion: `test_a_declared_run_completes_every
    _phase_cleanly` pins this schema as finishing with NO errors and NO abort
    against `_ADOPTED_HARNESS`, whereas the simple fixture's adopted run
    already aborts on `phase-1-schema-errors` (the mock is too thin for its
    renamed and indexed columns). On that base `summary['aborted']` is truthy
    no matter what the description does, and the read-back test could not
    fail — which is worse than not having it.

    `list_description` is what the site HOLDS before the run: one string for
    every list, or a per-title mapping. `ignore_description_writes` makes the
    mock accept the MERGE with a 200 and keep serving the old value — a
    silently discarded write, which is the only state in which the read-back
    can be watched failing.

    `prefix` reaches the mapping's list-title prefix, which is how a caller
    deploys to a list whose title needs OData escaping.

    Returns (summary, calls, output). The list phase must actually have
    started: otherwise a "nothing was written" assertion would pass against a
    run that aborted in the preflight and never reached the reconcile at all.
    """
    held = (
        dict.fromkeys(
            _declared_list_descriptions(tmp_path, prefix), list_description,
        )
        if isinstance(list_description, str) else dict(list_description)
    )
    harness = _ADOPTED_HARNESS.replace(
        "const LIST_DESCRIPTIONS = {};",
        f"const LIST_DESCRIPTIONS = {json.dumps(held)};",
    ).replace(
        "const IGNORE_DESCRIPTION_WRITES = false;",
        f"const IGNORE_DESCRIPTION_WRITES = {json.dumps(ignore_description_writes)};",
    )
    script = harness + "\n" + _declared_deploy_js(tmp_path, "", prefix).replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    calls_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert calls_line is not None, f"harness produced no call log:\n{output[-3000:]}"
    # By KEY, not by number: phase numbers derive from position and renumber
    # themselves the moment anybody inserts a phase, and a hardcoded '2.1'
    # would then silently stop guarding reach.
    assert f"Starting Phase {pn('lists')}" in output, (
        f"the list reconcile phase never ran:\n{output[-3000:]}"
    )
    return (
        json.loads(result_line.removeprefix("__RESULT__")),
        json.loads(calls_line.removeprefix("__CALLS__")),
        output,
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_existing_list_with_the_wrong_description_is_corrected(
    tmp_path: Path,
) -> None:
    """The adoption path is the one that matters.

    A list provisioned before markers existed, or one an owner edited, holds
    a description discovery cannot match. Creation-only writing leaves it
    that way forever and reports success.
    """
    summary, calls, output = _run_adopted_deploy(
        tmp_path, "something an owner typed",
    )
    writes = _description_writes(calls)
    assert writes, (
        "an existing list kept a description with no marker and the run "
        f"reported success; it is now invisible to fleet reporting\n{output[-2000:]}"
    )
    assert "Provisioned by dbml-sharepoint" in writes[0]["body"]
    # The repair has to CONVERGE, not merely be attempted: a MERGE whose
    # read-back then failed would satisfy the assertions above while leaving
    # the operator with an aborted run.
    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_correct_description_is_not_rewritten(tmp_path: Path) -> None:
    """Idempotence: a re-paste must not churn every list it looks at."""
    declared = _declared_list_descriptions(tmp_path)
    # Without this the test is vacuous: an empty declared description would
    # also never be rewritten, and nothing else here would notice the marker
    # had gone missing from the generator entirely.
    assert declared and all(
        "Provisioned by dbml-sharepoint" in value for value in declared.values()
    ), declared
    summary, calls, output = _run_adopted_deploy(tmp_path, declared)
    # Same guard as the sibling test, and for the same reason: "no description
    # was written" is also true of a run that fell over before it got there.
    # Without this the test would keep passing through an unrelated breakage
    # that stopped the reconcile from executing at all.
    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]
    assert not _description_writes(calls), (
        f"a list already carrying its declared description was rewritten"
        f"\n{output[-2000:]}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_description_that_does_not_read_back_aborts(tmp_path: Path) -> None:
    """`AGENTS.md`: anything that writes must read back and verify.

    A MERGE that returns 200 while the stored value stays stale is the exact
    shape this repository exists to catch -- the deploy reports success and
    the list is still undiscoverable.
    """
    summary, calls, output = _run_adopted_deploy(
        tmp_path, "stale", ignore_description_writes=True,
    )
    assert _description_writes(calls), f"nothing was even attempted\n{output[-2000:]}"
    assert summary.get("aborted"), (
        f"the description never took and the run still reported success"
        f"\n{output[-2000:]}"
    )
    assert "did not retain its declared Description" in output, output[-2000:]


# A list title carrying the one character OData escapes by DOUBLING rather
# than by percent-encoding. `prefix` is the knob because the rest of a list
# title is the DBML table name, which the parser will not let hold one.
_APOSTROPHE_PREFIX = "prefix: \"O'Brien \""


def test_the_list_write_matcher_survives_an_apostrophe() -> None:
    """The matcher must be exact in BOTH directions, and neither is obvious.

    `odataName` doubles an apostrophe and encodeURIComponent leaves it alone,
    so a title like `O'Brien Register` reaches the wire as
    getbytitle('O''Brien%20Register'). A `[^']+` title pattern stops at the
    first quote and matches nothing — which does not look like a broken
    matcher, it looks like a run that correctly wrote nothing, and the
    idempotence test passes for that reason forever.

    `.*` is the other trap: greedy backtracking lets it swallow the rest of
    the path, so a FIELD MERGE (which routinely carries its own Description)
    is counted as a list write.

    Asserted over the real URL shapes rather than over prose, because both
    failures are the kind that get reasoned about correctly and coded wrongly.
    """
    escaped = "/sites/x/_api/web/lists/getbytitle('O''Brien%20Register')"
    plain = "/sites/x/_api/web/lists/getbytitle('APP_Plain')"
    assert _LIST_WRITE_URL.search(escaped), "an escaped apostrophe was not matched"
    assert _LIST_WRITE_URL.search(plain)
    for nested in (
        f"{escaped}/fields/getbyinternalnameortitle('Note')",
        f"{escaped}/views/getbytitle('All%20Items')",
        f"{plain}/fields/getbyinternalnameortitle('Note')",
    ):
        assert not _LIST_WRITE_URL.search(nested), (
            f"a write nested under the list was counted as a list write: {nested}"
        )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_description_is_reconciled_on_a_list_whose_title_needs_escaping(
    tmp_path: Path,
) -> None:
    """End-to-end companion to the matcher test above.

    Pins the whole chain against an OData-escaped title at once: the emitted
    script builds the URL, the mock recognises it as a list write and applies
    it, the read-back sees it, and the harness's own `listOf` keys the state
    by the right list. Any one of those regressing to a `[^']+` title pattern
    turns this red — where reasoning about it would just leave the other
    tests quietly passing on a name no fixture happens to use.
    """
    declared = _declared_list_descriptions(tmp_path, _APOSTROPHE_PREFIX)
    assert any("'" in title for title in declared), declared
    summary, calls, output = _run_adopted_deploy(
        tmp_path, "typed by an owner", prefix=_APOSTROPHE_PREFIX,
    )
    writes = _description_writes(calls)
    assert writes, (
        "no list write was seen for a title carrying an apostrophe; either the "
        f"script or the matcher lost it\n{output[-2000:]}"
    )
    assert "Provisioned by dbml-sharepoint" in writes[0]["body"]
    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]


# The adopted site again, but every field CREATION is refused. STRUCTURE
# then records an error per column and takes its early return — the
# designed abort that skips ACL work on a broken schema. It also skips
# PROTECTION, which is where a Title unsealed at 1.4 used to be handed
# back. Only creation is refused: the 1.4 MERGE that unseals Title is a
# write to an existing field and still succeeds.
_ABORTING_HARNESS = _ADOPTED_HARNESS + textwrap.dedent(r"""
    const _passThrough = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const path = u.split('?')[0];
      const creating = (opts.method || 'GET') === 'POST' && opts.body
        && (path.endsWith('/fields') || path.endsWith('/fields/addfield'));
      if (!creating) return _passThrough(url, opts);
      calls.push({ url: u, method: 'POST', body: opts.body });
      const payload = { error: { message: { value: 'field creation refused' } } };
      return {
        ok: false, status: 400,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
""")


_ABORTING_SEALED_FIELD_HARNESS = _ADOPTED_HARNESS + textwrap.dedent(r"""
    // Adopt one ordinary declared field in the sealed state PREPARE finds
    // on a maintained site. Its stale description forces Phase 2.1 to write.
    const adoptedNote = fieldShape('APP_Escalation', 'Note', {
      FieldTypeKind: 2, Required: false, Description: 'stale description', MaxLength: 255,
    });
    adoptedNote.Sealed = true;
    created['APP_Escalation Note'] = adoptedNote;

    const _passThrough = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const parsed = opts.body ? JSON.parse(opts.body) : {};
      const refusingReconcile = (opts.method || 'GET') === 'POST'
        && u.includes("getbyinternalnameortitle('Note')")
        && parsed.Description !== undefined && parsed.Sealed === undefined;
      if (!refusingReconcile) return _passThrough(url, opts);
      calls.push({ url: u, method: 'POST', body: opts.body });
      const payload = { error: { message: { value: 'field reconcile refused' } } };
      return {
        ok: false, status: 400,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_run_that_aborts_after_unsealing_a_title_reseals_it() -> None:
    """A failed run must not leave the site less protected than it found it.

    PREPARE unseals an already-sealed built-in Title so the write phases
    can patch it, and PROTECTION hands it back. Every abort between the
    two — schema errors, lookup errors, enrolment errors — returns before
    PROTECTION, so the run ended with a column someone had deliberately
    sealed left open. Restoration must therefore be on the exit path, not
    on the success path."""
    output = _run_deploy(
        _ABORTING_HARNESS,
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    )
    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(result_line.removeprefix("__RESULT__"))
    # Without this the test could pass by never aborting at all — and a
    # run that reaches PROTECTION re-seals for the ordinary reason.
    assert summary.get("aborted"), (
        f"the run did not abort, so it never tested the abort path: {summary}"
    )
    reached = [ln.split("Starting Phase ")[1][:3] for ln in output.splitlines()
               if "Starting Phase " in ln]
    assert pn("unseal") in reached, f"the maintenance unseal never ran: {reached}"
    assert "4.1" not in reached, f"the run reached PROTECTION, so it did not abort early: {reached}"

    calls_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert calls_line is not None, "harness produced no call log"
    calls = json.loads(calls_line.removeprefix("__CALLS__"))
    seal_writes = [
        json.loads(c["body"])["Sealed"]
        for c in calls
        if c["method"] == "POST" and c.get("body")
        and "getbyinternalnameortitle('Title')" in c["url"]
        and "Sealed" in c["body"]
    ]
    assert seal_writes, "PREPARE never unsealed a Title, so there was nothing to restore"
    assert seal_writes[0] is False, f"PREPARE did not unseal Title: {seal_writes}"
    assert seal_writes[-1] is True, f"the aborted run left Title unsealed: {seal_writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_run_that_aborts_after_unsealing_a_declared_field_reseals_it(tmp_path: Path) -> None:
    """Title is not special on the exit path: PREPARE opens every declared
    sealed field, so a Phase 2.1 abort must hand every one of them back."""
    js = _declared_deploy_js(tmp_path, "seal_columns: true\n")
    script = _ABORTING_SEALED_FIELD_HARNESS + "\n" + js.replace(
        "})();", "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)

    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(result_line.removeprefix("__RESULT__"))
    assert summary.get("aborted") == "phase-1-schema-errors"

    calls_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert calls_line is not None, "harness produced no call log"
    calls = json.loads(calls_line.removeprefix("__CALLS__"))
    seal_writes = [
        json.loads(c["body"])["Sealed"]
        for c in calls
        if c["method"] == "POST" and c.get("body")
        and "getbyinternalnameortitle('Note')" in c["url"]
        and "Sealed" in c["body"]
    ]
    assert seal_writes[0] is False, f"PREPARE did not unseal Note: {seal_writes}"
    assert seal_writes[-1] is True, f"the aborted run left Note unsealed: {seal_writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_declared_run_completes_every_phase_cleanly(tmp_path: Path) -> None:
    """The end-to-end guard, and the one that gives the others their value.

    The original mock aborted in the read-only preflight, so no phase past
    1.1 had ever executed in a test — which is how a bug in the Phase 2.1
    field reconcile shipped in a green suite. This run adopts an existing
    site, unseals, creates, reconciles declared formulas, seals and seeds,
    and must finish with no errors and no abort. If a future change
    shortens it, the coverage disappears silently unless this fails.
    """
    js = _declared_deploy_js(
        tmp_path,
        """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
        """,
    )
    script = _ADOPTED_HARNESS + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))
    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]
    reached = [ln.split("Starting Phase ")[1][:3] for ln in output.splitlines()
               if "Starting Phase " in ln]
    for phase in ("1.1", pn("unseal"), "2.1", "3.1", "4.1", "5.1"):
        assert phase in reached, f"phase {phase} not reached: {reached}"


def test_generated_deploy_js_carries_no_control_characters() -> None:
    """deploy.js is pasted into a browser console by hand.

    A stray control character survives templating, the golden file and
    every text-mode diff — git reports the file as binary and shows
    nothing. Writing this fix, a literal NUL reached a template's
    executable code from an editing tool and rode into the generated
    script; the suite was green. Cheap to assert, invisible otherwise.
    """
    js = _deploy_js()
    stray = sorted({
        ch for ch in js
        if ord(ch) < 32 and ch not in "\n\r\t"
    })
    assert not stray, f"control characters in generated deploy.js: {[hex(ord(c)) for c in stray]}"


def _declared_pack(
    tmp_path: Path, section: str, prefix: str = DEFAULT_PREFIX,
) -> tuple[Any, Any]:
    """The (schema, bundle) behind `_declared_deploy_js`.

    Split out so a test can ask what the generator DECLARES for these lists
    without re-spelling the fixture. A second copy of the schema here would
    drift from the one the script is built from, and the tests that compare
    declared-against-live would then be comparing two different fixtures.

    `prefix` is the only knob that puts an arbitrary character into a LIST
    TITLE — the rest of the title is the DBML table name, which the parser
    constrains. It is what lets a test deploy to a list whose title needs
    OData escaping.
    """
    return pack(
        tmp_path,
        dbml=table("Escalation", ID_PK, "Title nvarchar", "Note nvarchar"),
        mapping=blocks(entities("Escalation"), section),
        prefix=prefix,
    )


def _declared_deploy_js(
    tmp_path: Path, section: str, prefix: str = DEFAULT_PREFIX,
) -> str:
    """deploy.js for an all-text schema that actually declares a formula.

    The shipped fixture declares none, so enforceDeclaredFormulas returns
    before doing anything and cannot be exercised through it. All-Text
    columns keep the run clear of the derived-property probes the mock does
    not answer.

    `section` is whatever extra mapping the test needs. It is dedented, so a
    caller may pass a triple-quoted block indented to match its surrounding
    code. `blocks()` rather than `with_tail()` because every caller opens a
    TOP-LEVEL section here — nothing nests under the entity, so no
    indentation is load-bearing and the two agree.
    """
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = _declared_pack(tmp_path, section, prefix)
    return generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_overwriting_a_declared_formula_logs_the_prior_value(tmp_path: Path) -> None:
    """`before` was read, compared and discarded; on success nothing was
    logged, so a deploy that removed or rewrote an existing formula left no
    record of what had been there. Under `reconcile: exact` an undeclared
    column's formula is cleared outright — exactly the case where the prior
    value is the only thing anyone would want back."""
    harness = _ADOPTED_HARNESS.replace(
        "ClientValidationFormula: f.__cvf == null ? null : f.__cvf,",
        "ClientValidationFormula: f.__cvf == null ? "
        "\"=if([$WasHere] != '', 'true', 'false')\" : f.__cvf,",
    )
    js = _declared_deploy_js(
        tmp_path,
        """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
        """,
    )
    script = harness + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    replaced = [ln for ln in output.splitlines() if "declared formulas" in ln]
    assert replaced, f"no prior value logged:\n{output[-2500:]}"
    assert any("WasHere" in ln for ln in replaced), replaced


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_formula_reconcile_fails_when_sharepoint_drops_validation_message(
    tmp_path: Path,
) -> None:
    harness = _ADOPTED_HARNESS.replace(
        "if (parsed.ValidationMessage != null) f.__vm = parsed.ValidationMessage;",
        "// Simulate SharePoint accepting the MERGE but dropping ValidationMessage.",
    )
    js = _declared_deploy_js(
        tmp_path,
        """
        column_validation:
          Escalation:
            columns:
              Note:
                when: [{ field: Note, op: is_not_null }]
                message: A note is required.
        """,
    )
    script = harness + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    assert "did not retain ValidationMessage" in output, output[-3000:]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_formula_reconcile_fails_when_client_message_is_not_cleared(tmp_path: Path) -> None:
    harness = _ADOPTED_HARNESS.replace(
        "ClientValidationMessage: null,",
        "ClientValidationMessage: 'stale guidance',",
    )
    js = _declared_deploy_js(
        tmp_path,
        """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
        """,
    )
    script = harness + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    assert "did not retain ClientValidationMessage" in output, output[-3000:]


def test_the_aggregations_comparison_survives_sharepoints_readback_spacing() -> None:
    """SharePoint returns `<FieldRef Name="X" Type="Sum" />` for the
    `...Type="Sum"/>` it was sent — verified against a live tenant on
    2026-07-29 (test/manual/view-aggregations-probe.js).

    Compared raw, a perfectly correct totals view drifts on EVERY redeploy:
    the phase rewrites the property, reads the same difference back, and
    fails closed. And it does so on the second run, never the first, which
    is the kind of bug that ships.

    This executes the SHIPPED normaliser out of the generated script rather
    than a copy of its logic, because a copy would keep passing after the
    real one changed.
    """
    if NODE is None:
        pytest.skip("node is not installed")
    script = _deploy_js()
    decode = re.search(r"^\s*const xmlDecode = .*?;$", script, re.MULTILINE | re.DOTALL)
    normalise = re.search(r"^\s*const normalizeViewQuery = .*?;$", script, re.MULTILINE)
    assert decode and normalise, "could not extract the normaliser from the generated script"

    sent = '<FieldRef Name="Amount" Type="Sum"/>'
    read_back = '<FieldRef Name="Amount" Type="Sum" />'
    program = (
        f"{decode.group(0)}\n{normalise.group(0)}\n"
        f"const a = normalizeViewQuery({json.dumps(sent)});\n"
        f"const b = normalizeViewQuery({json.dumps(read_back)});\n"
        "console.log(JSON.stringify({ equal: a === b, a, b }));"
    )
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "normalise.js"
        path.write_text(program, encoding="utf-8")
        out = subprocess.run(  # noqa: S603
            [NODE, str(path)], capture_output=True, text=True, check=True, timeout=60,
        )
    result = json.loads(out.stdout.strip())
    assert result["equal"], (
        f"the shipped normaliser does not equalise SharePoint's readback spacing: "
        f"sent normalised to {result['a']!r}, readback to {result['b']!r}"
    )


def test_no_aggregations_comparison_is_made_raw() -> None:
    """The write-side and readback-side comparisons are separate call sites
    and either one left raw reintroduces the never-converging redeploy.

    Asserted as the ABSENCE of any raw comparison rather than the presence
    of two known-good ones: naming the variables would break on a rename
    while saying nothing about a third call site somebody adds later.
    """
    script = _deploy_js()
    raw = re.findall(r"(?<!normalizeViewQuery\()\b\w+\.Aggregations\s*[!=]==", script)
    assert not raw, f"Aggregations compared without the normaliser: {raw}"
    # AggregationsStatus is a plain enum ('On'/'Off') and IS compared raw —
    # asserted so the regex above cannot be "fixed" by wrapping it too.
    assert "AggregationsStatus !== 'On'" in script


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_first_deploy_probes_no_absent_group_or_field_by_name() -> None:
    """A clean run must leave a clean console.

    The browser logs a failed request itself, before the script sees the
    response, and nothing in JavaScript can suppress that — so a handled
    404 still paints red and an operator reads it as a failure. The only
    fix is not to make the request: enumerate once, answer absence
    locally. Lists and views already did; site groups and the field probe
    did not, and a live first deploy showed four red lines because of it.

    The harness answers every enumeration as EMPTY, which is the state of
    a brand-new site — so any by-name probe here is one an operator would
    have seen painted red.

    Covers the two surfaces this harness reaches. The third — a list's
    role assignments by principal id — is asserted structurally instead,
    because the mock's principal resolution never returns an Id and so the
    run never reaches the ACL phase's role-assignment calls. A clause for
    it here would pass while testing nothing.
    """
    script = _HARNESS + "\n" + _deploy_js().replace(
        "})();", "}))().then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
        ).replace("(async () => {", "((async () => {", 1)
    line = next(
        (ln for ln in _run(script).splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert line is not None, "harness produced no call log"
    calls = json.loads(line.removeprefix("__CALLS__"))
    gets = [c["url"] for c in calls if c["method"] == "GET"]
    # The ACL phase resolves a group's Id by name AFTER creating it, so on
    # a real run that request succeeds and is not console noise; the mock
    # creates nothing, which is why it is excluded by its $select rather
    # than by being overlooked.
    by_name = [
        u for u in gets
        if ("sitegroups/getbyname" in u and "$select=Id" not in u)
        or ("getbytitle" in u and "/fields?" in u)
    ]
    assert not by_name, (
        "a first deploy probed by name for something it had already "
        f"enumerated as absent; each is a red console line: {by_name[:5]}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_unsupported_formula_tolerance_is_scoped_to_clears() -> None:
    """The clearing-only guard is a deliberate hole in fail-closed, so its
    edges are asserted rather than described.

    Extracts the shipped predicate and runs it over every combination: a
    clear (empty or UNMANAGED on both) may be tolerated; anything that SETS
    either formula must not be, or a rejected write to a field type that
    silently drops formulas would be reported as success.
    """
    script = _deploy_js()
    match = re.search(
        r"const clearingOnly = (.*?);\n", script, re.DOTALL,
    )
    assert match, "could not extract the clearingOnly predicate"
    cases = [
        ("", "", True),
        ("__dbmlsp_unmanaged__", "__dbmlsp_unmanaged__", True),
        ("", "__dbmlsp_unmanaged__", True),
        ("=[X]>1", "", False),
        ("", "=[X]>1", False),
        ("=[X]>1", "=[Y]>1", False),
        ("__dbmlsp_unmanaged__", "=[Y]>1", False),
    ]
    program = (
        "const UNMANAGED = '__dbmlsp_unmanaged__';\n"
        "const out = [];\n"
        f"for (const [v, c] of {json.dumps([[a, b] for a, b, _ in cases])}) {{\n"
        "  const field = { validation_formula: v, client_validation_formula: c };\n"
        f"  const clearingOnly = {match.group(1)};\n"
        "  out.push(clearingOnly);\n"
        "}\n"
        "console.log(JSON.stringify(out));"
    )
    assert NODE is not None
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "guard.js"
        path.write_text(program, encoding="utf-8")
        proc = subprocess.run(  # noqa: S603
            [NODE, str(path)], capture_output=True, text=True, check=True, timeout=60,
        )
    got = json.loads(proc.stdout.strip())
    expected = [tolerated for _, _, tolerated in cases]
    assert got == expected, (
        f"clearingOnly must tolerate only clears; got {got}, expected {expected} "
        f"for {[(a, b) for a, b, _ in cases]}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_clear_still_retries_the_client_properties() -> None:
    """A MERGE is atomic: the refusal applies none of the body, including a
    ClientValidationFormula clear the same request carried and which a URL
    field does accept. Tolerating the refusal without retrying those would
    report success while a stale show/hide rule stayed live."""
    script = _deploy_js()
    assert "client-only retry also failed" in script, (
        "the tolerant branch must retry the properties the field type accepts"
    )
    # And it must not simply return: the read-back below is what proves the
    # client clear landed.
    tolerant = script[script.index("const clearingOnly ="):]
    tolerant = tolerant[: tolerant.index("const after = await read();")]
    assert "return;" not in tolerant, (
        "the tolerant branch must fall through to the read-back, not return"
    )


# === Enterprise reader enrolment (the reader_enrolment phase) ===
#
# This phase grants Read on a customer's register to a named account, and
# the membership is PERMANENT — unlike the operator's, which the run
# removes on the way out. Two resolutions must never be enrolled: a
# security GROUP (everyone in it gets Read) and one of SharePoint's
# everyone-claims (every user in the tenant gets Read). Neither is visible
# afterwards, because the deploy reads back byte-identical either way.
#
# So every test below RUNS the emitted script and asserts on what the run
# DOES — did it abort, and above all was a membership POST ever issued.
# `assert "PrincipalType !== 1" in js` would pass with the guard sitting in
# a comment; "no POST to sitegroups(N)/users happened" cannot.

_READER_ADDRESS = "svc-reporting@example.org"

# A well-formed resolution of _READER_ADDRESS. Every refusal test below
# starts from this and varies exactly ONE attribute, so the guard under
# test is the only one that can fire — otherwise deleting it would leave
# the test green for a neighbouring reason and prove nothing.
_RESOLVED_USER: dict[str, Any] = {
    "Id": 42,
    "LoginName": "i:0#.f|membership|svc-reporting@example.org",
    "Title": "Reporting Service",
    "Email": _READER_ADDRESS,
    "PrincipalType": 1,
}

_MEMBERSHIP_URL = re.compile(r"sitegroups\(\d+\)/users")


def _reader_deploy_js(enterprise_reader: str | None = _READER_ADDRESS) -> str:
    """deploy.js for the mapping that declares an enterprise-reader group."""
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.parser import parse_dbml
    from dbml_sharepoint.model.release import load_release

    return generate_deploy_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        enterprise_reader=enterprise_reader,
    )


def _reader_harness(
    ensure_user: dict[str, Any],
    *,
    members: list[dict[str, Any]] | None = None,
    member_pages: list[list[dict[str, Any]]] | None = None,
    drop_readback: bool = False,
    stray_on_write: dict[str, Any] | None = None,
) -> str:
    """`_ADOPTED_HARNESS` plus the two surfaces the reader phase touches.

    `ensureuser` answers `ensure_user` verbatim — that is the whole point of
    the harness, since what a tenant resolves an address to is exactly what
    the guards have to judge. The flagged group's membership is real state:
    the POST appends to it and the verification re-read sees the result, so
    a run cannot satisfy the read-back by asserting its own success.
    `drop_readback` accepts the POST and drops the write, which is what a
    silently-refused membership looks like from the script's side.

    `stray_on_write` appends a FOREIGN principal at the same moment, which
    is what another administrator adding somebody between the before-read
    and the read-back looks like. It cannot be modelled by seeding
    `members`, because a principal present before the run is caught by the
    gate that runs first -- the whole point is that this one arrives after
    that gate has already passed.

    `member_pages` serves the membership across SEVERAL OData pages, each
    but the last carrying a `__next`. A group whose membership arrives in
    one page cannot distinguish a gate that reads every page from one that
    reads the first and stops — and the second is a gate that a large
    group defeats simply by being large. `members=[...]` is the one-page
    case, and is exactly `member_pages=[[...]]`.
    """
    pages = [list(members or [])] if member_pages is None else [
        list(page) for page in member_pages
    ]
    return _ADOPTED_HARNESS + textwrap.dedent(r"""
        const ENSURED = __ENSURE_USER__;
        const READER_MEMBER_PAGES = __MEMBER_PAGES__;
        const DROP_READBACK = __DROP_READBACK__;
        const STRAY_ON_WRITE = __STRAY_ON_WRITE__;
        const _beforeReader = globalThis.fetch;
        globalThis.fetch = async (url, opts = {}) => {
          const u = String(url);
          const method = opts.method || 'GET';
          const respond = (payload) => {
            calls.push({ url: u, method,
                         body: opts.body === undefined ? null : opts.body });
            return { ok: true, status: 200, headers: { get: () => null },
                     json: async () => payload,
                     text: async () => JSON.stringify(payload) };
          };
          if (u.toLowerCase().includes('/ensureuser')) return respond({ d: ENSURED });
          // The flagged group's own membership, keyed off the BY-ID form of
          // the path so the 1.2 empty-group gate — which asks by name —
          // still reaches the adopted mock underneath and still sees empty.
          if (/sitegroups\(\d+\)\/users/.test(u)) {
            if (method === 'POST') {
              const added = JSON.parse(opts.body);
              if (!DROP_READBACK) {
                READER_MEMBER_PAGES[READER_MEMBER_PAGES.length - 1].push(
                  { Id: ENSURED.Id, Title: ENSURED.Title || '',
                    LoginName: added.LoginName });
              }
              // Somebody else's write landing in the same window.
              if (STRAY_ON_WRITE) {
                READER_MEMBER_PAGES[READER_MEMBER_PAGES.length - 1].push(
                  STRAY_ON_WRITE);
              }
              return respond({ d: { Id: ENSURED.Id, LoginName: added.LoginName } });
            }
            // Page 0 unless the caller followed a __next we handed out.
            // The follow-on URL keeps the sitegroups(N)/users shape so it
            // lands back here rather than falling through to the adopted
            // mock, which would answer an unrelated empty membership.
            const marked = /[?&]page=(\d+)/.exec(u);
            const page = marked ? Number(marked[1]) : 0;
            const payload = { d: { results: READER_MEMBER_PAGES[page] || [] } };
            if (page + 1 < READER_MEMBER_PAGES.length) {
              payload.d.__next =
                'https://example.sharepoint.com/_api/web/sitegroups(9)/users?page='
                + (page + 1);
            }
            return respond(payload);
          }
          return _beforeReader(url, opts);
        };
    """).replace(
        "__ENSURE_USER__", json.dumps(ensure_user),
    ).replace(
        "__MEMBER_PAGES__", json.dumps(pages),
    ).replace(
        "__DROP_READBACK__", "true" if drop_readback else "false",
    ).replace(
        "__STRAY_ON_WRITE__", json.dumps(stray_on_write),
    )


def _run_reader_deploy(
    ensure_user: dict[str, Any],
    *,
    members: list[dict[str, Any]] | None = None,
    member_pages: list[list[dict[str, Any]]] | None = None,
    drop_readback: bool = False,
    stray_on_write: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run the emitted deploy against the reader harness.

    Returns (summary, calls, output). The phase must actually have STARTED:
    a refusal test would otherwise pass against a run that aborted in 1.2
    and never reached the code under test at all.
    """
    script = _reader_harness(
        ensure_user, members=members, member_pages=member_pages,
        drop_readback=drop_readback, stray_on_write=stray_on_write,
    ) + "\n" + _reader_deploy_js().replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    calls_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert calls_line is not None, f"harness produced no call log:\n{output[-3000:]}"
    assert f"Starting Phase {pn('reader_enrolment')}" in output, (
        f"the reader-enrolment phase never ran:\n{output[-3000:]}"
    )
    return (
        json.loads(result_line.removeprefix("__RESULT__")),
        json.loads(calls_line.removeprefix("__CALLS__")),
        output,
    )


def _membership_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every POST that adds somebody to a site group, by parsed body."""
    return [
        json.loads(c["body"]) for c in calls
        if c["method"] == "POST" and c.get("body") and _MEMBERSHIP_URL.search(c["url"])
    ]


def _reader_errors(summary: dict[str, Any]) -> list[Any]:
    return [
        err for err in (summary.get("errors") or [])
        if str(err.get("phase")) == pn("reader_enrolment")
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_security_group_is_refused_as_an_enterprise_reader() -> None:
    """Microsoft Learn: PrincipalType is None 0, User 1, DistributionList 2,
    SecurityGroup 4, SharePointGroup 8, and it carries [Flags] — so the
    check is strict equality to 1, never a bitwise AND.

    `ensureuser` resolves a security group happily. Enrolling one would hand
    Read to everybody in it, and nothing downstream could tell: the deploy
    reads back byte-identical either way. Only the type differs from the
    success payload, so the type check is the only guard that can fire.
    """
    summary, calls, _ = _run_reader_deploy({
        **_RESOLVED_USER,
        "PrincipalType": 4,
        "LoginName": "c:0t.c|tenant|4d4a4d54-0b2e-4a1f-9b6c-2f0d7a0b1c3e",
        "Title": "Reporting Readers",
    })
    # The grant first: that is the damage, and the abort is only how the
    # script avoids it. Asserted in this order so removing the guard fails
    # on "a group was enrolled" rather than on a summary key.
    assert not _membership_writes(calls), (
        "a security group was enrolled: every member of it now holds Read"
    )
    assert summary.get("aborted") == "reader-enrolment-errors", summary
    assert _reader_errors(summary), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_everyone_claim_is_refused_even_though_it_types_as_a_user() -> None:
    """`spo-grid-all-users` is the one mistake here with no cheap undo.

    On the one tenant this has been measured on (2026-08-12, group B of
    `test/manual/enterprise-reader-probe.js`) it came back typed 4, which
    the strict type check refuses by itself — so the needle is belt and
    braces behind that check, not the thing holding the door. This test
    hands it PrincipalType 1 anyway, because ONE TENANT IS ONE DATA POINT
    and the needle exists for the tenant that types it differently. That is
    also the only payload under which removing the needle can be watched
    failing.

    The payload keeps the matching Email deliberately, so neither the type
    check nor the identity check can be what refuses it — the claims check
    is on its own here, which is the only way removing it can be watched
    failing.
    """
    summary, calls, _ = _run_reader_deploy({
        **_RESOLVED_USER,
        "LoginName": "c:0-.f|rolemanager|spo-grid-all-users/contoso",
        "Title": "Everyone except external users",
    })
    assert not _membership_writes(calls), (
        "an everyone-claim was enrolled: every user in the tenant now holds Read"
    )
    assert summary.get("aborted") == "reader-enrolment-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_mismatched_identity_is_refused() -> None:
    """`ensureuser` resolving something other than what was asked for is the
    quiet failure: the deploy succeeds and the wrong account holds Read.

    A real user, correctly typed, with a real login — only the address
    differs from the one the build asked for.
    """
    summary, calls, _ = _run_reader_deploy({
        **_RESOLVED_USER,
        "Id": 43,
        "LoginName": "i:0#.f|membership|someone-else@example.org",
        "Title": "Someone Else",
        "Email": "someone-else@example.org",
    })
    assert not _membership_writes(calls), (
        "an account other than the one asked for was enrolled"
    )
    assert summary.get("aborted") == "reader-enrolment-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_resolved_user_is_enrolled_and_the_membership_read_back() -> None:
    """The success path: the account IS added, by its resolved LoginName,
    and the run re-reads the membership afterwards rather than trusting the
    POST's own answer."""
    summary, calls, output = _run_reader_deploy(_RESOLVED_USER)
    assert not _reader_errors(summary), summary
    writes = _membership_writes(calls)
    assert [w["LoginName"] for w in writes] == [_RESOLVED_USER["LoginName"]], writes
    membership = [
        i for i, c in enumerate(calls) if _MEMBERSHIP_URL.search(c["url"])
    ]
    posted = next(
        i for i in membership
        if calls[i]["method"] == "POST" and calls[i].get("body")
    )
    assert any(
        i > posted and calls[i]["method"] == "GET" for i in membership
    ), f"the membership was never re-read after the write: {[calls[i] for i in membership]}"
    assert _RESOLVED_USER["Title"] in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_alias_mailbox_still_matches_the_requested_upn() -> None:
    """The identity check accepts the Email OR the LoginName's UPN part.

    An account whose mailbox address differs from its UPN is ordinary, and
    refusing it would send an operator looking for a fault that is not
    there. The account here is the right one — its claims login ends in the
    requested UPN — so it must be enrolled, not refused.
    """
    summary, calls, _ = _run_reader_deploy({
        **_RESOLVED_USER, "Email": "svc.reporting.alias@example.org",
    })
    assert not _reader_errors(summary), summary
    assert [w["LoginName"] for w in _membership_writes(calls)] == [
        _RESOLVED_USER["LoginName"],
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_membership_that_does_not_read_back_aborts() -> None:
    """The house rule: anything that writes reads back and verifies.

    SharePoint answering 200 is not evidence the membership exists — the
    harness accepts the POST and drops it, which is what a silently refused
    write looks like from the script's side. Reporting that as success is
    worse than failing, because the operator stops looking.
    """
    summary, calls, _ = _run_reader_deploy(_RESOLVED_USER, drop_readback=True)
    assert _membership_writes(calls), "the run never attempted the enrolment"
    assert summary.get("aborted") == "reader-enrolment-errors", summary


_OTHER_MEMBER: dict[str, Any] = {
    "Id": 7, "Title": "Data Team",
    "LoginName": "i:0#.f|membership|data-team@example.org",
}


def _removals(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every call that could take somebody OUT of a site group."""
    return [
        c for c in calls
        if "removebyid" in c["url"].lower() or "removebyloginname" in c["url"].lower()
        or c["method"] == "DELETE"
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unexpected_member_aborts_the_run_and_is_never_removed() -> None:
    """A principal in the group that is not the named reader stops the run.

    This replaced an INFO line that let the run continue, and the case that
    forced the change is mundane: enrol a mistyped-but-valid address, notice,
    redeploy with the right one, and BOTH accounts hold Read on every list
    this bundle provisions — permanently, since nothing here removes anyone.
    The only trace was one INFO line in a run that reported success.

    Three things are asserted, and the ORDER matters. The damage is the
    grant, so "nothing was POSTed" comes first: deleting the gate must fail
    on a second reader having been enrolled, not on a summary key. Then the
    abort. Then, still, that nobody was removed — that half of the old
    behaviour is unchanged and this is the test pinning it. A gate that
    "fixed" the problem by evicting the stranger would pass the first two
    assertions and be a far worse tool.
    """
    summary, calls, output = _run_reader_deploy(
        _RESOLVED_USER, members=[_OTHER_MEMBER],
    )
    assert not _membership_writes(calls), (
        "a second account was enrolled into a group that already held "
        "somebody else; both now hold Read on every list in the bundle"
    )
    assert summary.get("aborted") == "reader-enrolment-errors", summary
    assert not _removals(calls), (
        f"the phase removed an existing member: {_removals(calls)}"
    )
    # Actionable: the operator has to be able to go and find the principal,
    # which needs the login name, not just a display title.
    errors = _reader_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert _OTHER_MEMBER["Title"] in message, message
    assert _OTHER_MEMBER["LoginName"] in message, message
    assert "Site permissions" in message, message
    assert "--enterprise-reader" in message, message
    assert _OTHER_MEMBER["Title"] in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unexpected_member_on_a_later_page_still_aborts() -> None:
    """The gate reads every page of the membership, not the first one.

    SharePoint pages `sitegroups(N)/users` and hands back a `__next`. A gate
    that stopped at page one would be defeated by the group simply being
    big — and it would look like it worked, because the small groups every
    test uses fit in one page. Page one here is EMPTY and the stranger is
    alone on page two, so a first-page-only read sees a group with no
    members at all and enrols straight past them.
    """
    summary, calls, _ = _run_reader_deploy(_RESOLVED_USER, member_pages=[
        [],
        [_OTHER_MEMBER],
    ])
    assert not _membership_writes(calls), (
        "a member on page two was missed and the enrolment went ahead"
    )
    assert summary.get("aborted") == "reader-enrolment-errors", summary
    assert not _removals(calls)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_named_reader_plus_a_stranger_still_aborts() -> None:
    """The named account already being a member does not excuse the other one.

    Ordering guard: the idempotence check ("already a member — skip") must
    not run before the gate, or the very redeploy that follows a mistyped
    address would sail through, which is the exact sequence this feature
    exists to catch.
    """
    summary, calls, _ = _run_reader_deploy(_RESOLVED_USER, members=[
        {"Id": _RESOLVED_USER["Id"], "Title": _RESOLVED_USER["Title"],
         "LoginName": _RESOLVED_USER["LoginName"]},
        _OTHER_MEMBER,
    ])
    assert not _membership_writes(calls)
    assert summary.get("aborted") == "reader-enrolment-errors", summary
    assert not _removals(calls)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_principal_added_during_the_run_is_caught_by_the_read_back() -> None:
    """The gate above reads the state this run FOUND; this reads what it LEFT.

    The before-read gate cannot see a principal that arrives after it has
    already passed. Checking only that the reader is present made the
    read-back a presence check, so another administrator adding somebody
    between the two reads left the run reporting success on a group whose
    entire purpose is that it holds one account.

    A deploy is pasted into a site while people are working in it, so the
    window is not theoretical. `stray_on_write` models exactly that and
    nothing else: the membership is empty when the gate runs, and the
    foreign principal appears at the moment of the write.

    Nothing is removed -- the same reason the before-read gives. The run
    fails closed AFTER the write, which is the point: the write cannot be
    safely undone, so the operator is told what the group now holds.
    """
    summary, calls, output = _run_reader_deploy(
        _RESOLVED_USER, members=[], stray_on_write=_OTHER_MEMBER,
    )
    # The enrolment really happened -- otherwise this would be re-testing
    # the before-read gate under a new name.
    assert _membership_writes(calls), output[-2000:]
    # The message assertion comes FIRST deliberately. Without the read-back
    # invariant the run carries on and aborts later for an unrelated reason,
    # so asserting the abort code first reports that later reason and buries
    # the defect. This one names it.
    errors = _reader_errors(summary)
    assert errors, summary
    assert "while this script was running" in str(errors), errors
    assert summary.get("aborted") == "reader-enrolment-errors", summary
    assert not _removals(calls)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_already_enrolled_reader_is_not_added_twice() -> None:
    """Idempotence: a redeploy must not POST a membership that is already
    there, and must not treat the existing one as a failure.

    The gate above counts principals that are not the named reader, so this
    is the case that says it counts them CORRECTLY: a re-run with the same
    flag has to stay green, or the feature is unusable after its first use.
    """
    summary, calls, _ = _run_reader_deploy(_RESOLVED_USER, members=[{
        "Id": _RESOLVED_USER["Id"], "Title": _RESOLVED_USER["Title"],
        "LoginName": _RESOLVED_USER["LoginName"],
    }])
    assert not _reader_errors(summary), summary
    # Not `aborted is None`: this harness's run stops later in Phase 1 for
    # reasons that have nothing to do with the reader. What must be true is
    # that the reader phase is not what stopped it.
    assert summary.get("aborted") != "reader-enrolment-errors", summary
    assert not _membership_writes(calls), "an existing membership was re-POSTed"


# #209: a hand-made site group whose name happens to match a declared one
# used to be adopted by name alone, and the ACL phase then granted it
# whatever the mapping declares for that group. `_group_gate_deploy` lets
# these tests control ONE declared group's Description and paginated
# membership against `_ADOPTED_HARNESS`, leaving every other group at the
# shared defaults (unmarked, empty) so it is neither created nor refused.


def _run_group_verify_deploy(
    deploy_js: str, harness: str,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run `deploy_js` against `harness` and return (summary, calls, output).

    Phase 'security' must actually have started, or a refusal assertion
    would pass against a run that never reached the group loop at all.
    """
    script = harness + "\n" + deploy_js.replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    calls_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert calls_line is not None, f"harness produced no call log:\n{output[-3000:]}"
    assert f"Starting Phase {pn('security')}" in output, (
        f"the security phase never ran:\n{output[-3000:]}"
    )
    return (
        json.loads(result_line.removeprefix("__RESULT__")),
        json.loads(calls_line.removeprefix("__CALLS__")),
        output,
    )


def _group_gate_deploy(
    deploy_js: str,
    group_name: str,
    *,
    description: str,
    member_pages: list[list[dict[str, Any]]],
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run `deploy_js` against `_ADOPTED_HARNESS` with one group's Description
    and membership overridden.
    """
    harness = _ADOPTED_HARNESS.replace(
        "const GROUP_DESCRIPTIONS = {};",
        f"const GROUP_DESCRIPTIONS = {json.dumps({group_name: description})};",
    ).replace(
        "const GROUP_MEMBER_PAGES = {};",
        f"const GROUP_MEMBER_PAGES = {json.dumps({group_name: member_pages})};",
    ).replace(
        "const KNOWN_GROUP_NAMES = [];",
        f"const KNOWN_GROUP_NAMES = {json.dumps([group_name])};",
    )
    return _run_group_verify_deploy(deploy_js, harness)


def _group_settings_writes(
    calls: list[dict[str, Any]], group_name: str,
) -> list[dict[str, Any]]:
    """Every POST that MERGEs settings, description included, onto the named
    group object itself, not its membership."""
    encoded = quote(group_name, safe="")
    return [
        c for c in calls
        if c["method"] == "POST" and c["body"]
        and f"sitegroups/getbyname('{encoded}')" in c["url"]
        and "/users" not in c["url"]
    ]


def _security_errors(summary: dict[str, Any]) -> list[Any]:
    return [
        err for err in (summary.get("errors") or [])
        if str(err.get("phase")) == pn("security")
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unmarked_group_with_members_is_refused() -> None:
    """#209: adopting it would grant those members whatever the family
    declares. 'List Maintainer' is granted 'Schema Manager' in the plain
    fixture mapping, which can create and manage every list in the family."""
    summary, calls, _ = _group_gate_deploy(
        _deploy_js(), "List Maintainer",
        description="Our own group", member_pages=[[{"Id": 501}]],
    )
    # The grant is the damage; the refusal is only how the script avoids it.
    # Asserted first so removing the gate fails on "the group was
    # reconciled" rather than on a summary key.
    assert not _group_settings_writes(calls, "List Maintainer"), (
        "an unmarked group with members was reconciled before the refusal: "
        "its description and membership controls were rewritten"
    )
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "List Maintainer" in message, message
    assert "carries no" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unmarked_but_empty_group_is_adopted_and_stamped() -> None:
    """A group nobody has joined yet carries no access to hand out, so it is
    adopted like any other pre-existing group and stamped with the marker
    that lets a later redeploy recognise it as this tool's own."""
    summary, calls, _ = _group_gate_deploy(
        _deploy_js(), "List Maintainer",
        description="Our own group", member_pages=[[]],
    )
    assert not _security_errors(summary), summary
    writes = _group_settings_writes(calls, "List Maintainer")
    assert writes, "an unmarked, empty group was never adopted"
    assert "Provisioned by dbml-sharepoint" in writes[0]["body"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unmarked_group_with_a_member_on_a_later_page_is_refused() -> None:
    """`countGroupMembers` must follow every page, not just the first.

    The first page is empty and the only member sits on page two. A count
    that stopped after page one would read zero, adopt the group, and MERGE
    the family's grant onto it. This is the only guard surface on this
    branch with no coverage of its own `__next` pagination, so it gets a
    test that a broken loop cannot pass by accident:
    `test_an_unmarked_group_with_members_is_refused` puts every member on
    page one and would stay green even if pagination were deleted entirely.
    """
    summary, calls, _ = _group_gate_deploy(
        _deploy_js(), "List Maintainer",
        description="Our own group", member_pages=[[], [{"Id": 501}]],
    )
    assert not _group_settings_writes(calls, "List Maintainer"), (
        "an unmarked group with a member on a later page was reconciled "
        "before the refusal"
    )
    assert _security_errors(summary), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_marked_group_with_members_is_adopted_silently() -> None:
    """A redeploy must not trip over the enterprise reader a prior run
    already enrolled into this same group. `enterprise_reader=None` keeps
    the reader-enrolment phase itself out of the emitted script, so this
    exercises only the adoption gate in the security phase that reconciles
    'Enterprise Reader' regardless of --enterprise-reader."""
    summary, calls, _ = _group_gate_deploy(
        _reader_deploy_js(enterprise_reader=None), "Enterprise Reader",
        description="Read-only accounts. Provisioned by dbml-sharepoint from Test.",
        member_pages=[[{"Id": 501}]],
    )
    assert not _security_errors(summary), summary
    assert _group_settings_writes(calls, "Enterprise Reader"), (
        "a marked group's settings were never reconciled"
    )


# Task 7: `mergeResp.ok` and the create POST's `ok` only say the tenant
# accepted the request, not that it stored what was sent. `verifyGroupSettings`
# reads the group back after both the create and the reconcile write and
# compares every field it wrote. `GROUP_DROP_FIELD_ON_WRITE` and
# `GROUP_COERCE_AUTO_ACCEPT` model the two ways the mock, like the tenant, can
# answer 200 while storing something other than what was sent.


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_group_description_the_tenant_did_not_store_fails_closed() -> None:
    """AGENTS.md: anything that writes must read back and verify."""
    harness = _ADOPTED_HARNESS.replace(
        "const GROUP_DROP_FIELD_ON_WRITE = null;",
        "const GROUP_DROP_FIELD_ON_WRITE = 'Description';",
    )
    summary, _, _ = _run_group_verify_deploy(_deploy_js(), harness)
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "List Maintainer" in message, message
    assert "Description" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_flag_the_tenant_ignored_fails_closed() -> None:
    """OnlyAllowMembersViewMembership is part of the security boundary.

    The fixture declares it false, which is also the mock's untouched
    default, so dropping the write would leave the state unchanged and
    prove nothing. The schema text is overridden to true so the drop is
    observable: the state stays at the untouched default instead of
    picking up what was sent.
    """
    js = _deploy_js().replace(
        '"only_allow_members_view_membership": false',
        '"only_allow_members_view_membership": true', 1,
    )
    assert '"only_allow_members_view_membership": true' in js
    harness = _ADOPTED_HARNESS.replace(
        "const GROUP_DROP_FIELD_ON_WRITE = null;",
        "const GROUP_DROP_FIELD_ON_WRITE = 'OnlyAllowMembersViewMembership';",
    )
    summary, _, _ = _run_group_verify_deploy(js, harness)
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "List Maintainer" in message, message
    assert "OnlyAllowMembersViewMembership" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_auto_accept_is_compared_against_the_coerced_value() -> None:
    """group-description-probe.js, G9/G10 (2026-08-13 and 2026-08-14): the
    tenant stores AutoAcceptRequestToJoinLeave as false whenever the written
    AllowRequestToJoinLeave is false, no matter what was sent for AutoAccept.
    `group_auto_accept_without_requests` refuses a mapping that declares
    that pair, so no shipped mapping can reach this branch through the CLI.
    The schema text is overridden directly to reach it anyway, the same way
    every other test in this file calls `generate_deploy_js` without going
    through the build-time checks.

    Comparing the read-back against the value SENT, rather than the coerced
    one, would fail here: SENT is true, the tenant stores false, and the
    deploy must accept that as correct rather than abort. Getting this wrong
    aborts a redeploy for every shipped family, since every one of them
    declares AllowRequestToJoinLeave false.
    """
    js = _deploy_js().replace(
        '"auto_accept_request_to_join_leave": false',
        '"auto_accept_request_to_join_leave": true', 1,
    )
    assert '"auto_accept_request_to_join_leave": true' in js
    harness = _ADOPTED_HARNESS.replace(
        "const GROUP_COERCE_AUTO_ACCEPT = false;",
        "const GROUP_COERCE_AUTO_ACCEPT = true;",
    )
    summary, _, _ = _run_group_verify_deploy(js, harness)
    assert not _security_errors(summary), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_reconciled_group_setting_the_tenant_did_not_store_fails_closed() -> None:
    """The three tests above all exercise the create path (`KNOWN_GROUP_NAMES`
    empty). `verifyGroupSettings` is called on the reconcile path too, and
    that call has no coverage of its own without this: `KNOWN_GROUP_NAMES`
    names the group, and its pre-existing Description already carries the
    marker (`Stale note...`), so this takes the adopt-and-reconcile branch,
    never the create branch, and the drop can only be caught by the
    reconcile read-back.
    """
    group_name = "List Maintainer"
    harness = _ADOPTED_HARNESS.replace(
        "const GROUP_DESCRIPTIONS = {};",
        "const GROUP_DESCRIPTIONS = "
        f"{json.dumps({group_name: 'Stale note. Provisioned by dbml-sharepoint from Test.'})};",
    ).replace(
        "const GROUP_MEMBER_PAGES = {};",
        f"const GROUP_MEMBER_PAGES = {json.dumps({group_name: [[]]})};",
    ).replace(
        "const KNOWN_GROUP_NAMES = [];",
        f"const KNOWN_GROUP_NAMES = {json.dumps([group_name])};",
    ).replace(
        "const GROUP_DROP_FIELD_ON_WRITE = null;",
        "const GROUP_DROP_FIELD_ON_WRITE = 'Description';",
    )
    summary, calls, _ = _run_group_verify_deploy(_deploy_js(), harness)
    assert _group_settings_writes(calls, group_name), (
        "the reconcile MERGE never happened"
    )
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert group_name in message, message
    assert "Description" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


def test_no_reader_no_enrolment_code() -> None:
    """Opt-in: the code path must not exist unless asked for.

    Absence, asserted on the emitted text, is the one thing a text
    assertion states exactly — a guard that is present but unreachable is
    the failure mode this file avoids elsewhere; a call site that is not
    emitted at all cannot run.
    """
    js = _deploy_js()
    assert "ensureuser" not in js
    assert f"Starting Phase {pn('reader_enrolment')}" not in js
    # And the same mapping, WITH a reader, does emit it — otherwise the two
    # assertions above would also hold for a template that never works.
    assert "ensureuser" in _reader_deploy_js()
