# test/test_deploy_runtime.py
"""Execute the generated deploy.js against a mock SharePoint.

The golden-file test proves deploy.js does not CHANGE; it cannot prove it
RUNS. A whole class of defect lives in that gap (a caller that omits a
key another function requires, a comparison against `undefined`, a
sentinel that reads as a real value). One such bug shipped in the golden
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
from typing import Any, ClassVar, NamedTuple
from urllib.parse import quote

import pytest
from _batch_mock import BATCH_MOCK
from _builders import ID_PK, table
from _node import NODE
from _node import run_node as _run
from _packs import DEFAULT_PREFIX, blocks, entities, pack
from _paths import FIXTURES

from dbml_sharepoint.analysis.list_description import marker_for
from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.extension import BaseExtension


def _deploy_js_with_assessment() -> str:
    """The deploy script exactly as it ships, assessment and all.

    Only the assessment gate's own tests use this. Everything else goes
    through `_deploy_js`, which stubs the assessment out.
    """
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


def _without_assessment(js: str) -> str:
    """Skip the assessment so a test reaches the phase it was written for.

    Not `ACKNOWLEDGE_DEGRADED`: the assessment's own read-only ProcessQuery
    POST trips `_security_writes`, whose guard must not be narrowed to suit a
    test. A stub makes no requests at all.

    `if (false) await assessSite({` keeps the original call syntactically
    valid, so the object literal that follows still parses.
    """
    stubbed = js.replace(
        "    assessment = await assessSite({",
        "    assessment = { findings: [], verdict: 'COMPATIBLE' };\n"
        "    if (false) await assessSite({",
        1,
    )
    assert stubbed != js, "the assessment stub did not splice in"
    return stubbed


def _deploy_js() -> str:
    """The shipped deploy script with the assessment stubbed out."""
    return _without_assessment(_deploy_js_with_assessment())


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
""") + BATCH_MOCK


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_deploy_js_runs_without_throwing() -> None:
    """The generated script must reach a summary against a healthy site.

    It need not succeed at provisioning (the mock is too thin for that),
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
    it before aborting, an unrequested write to a built-in column."""
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
# adoption path (the one where declared shapes are actually compared)
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
    // run can never satisfy its own read-back. Explicit entries drive the
    // ownership/refusal cases. The default map gives unrelated adopted-site
    // tests currently owned lists so they reach the behavior they exercise.
    // These constants are rewritten by _run_adopted_deploy.
    const LIST_DESCRIPTIONS = new Map([]);
    const DEFAULT_LIST_DESCRIPTIONS = new Map([
      ['APP_Project', 'Provisioned by dbml-sharepoint from simple-test for list Project.'],
      ['APP_Task', 'Provisioned by dbml-sharepoint from simple-test for list Task.'],
      ['APP_AppSettings', 'Provisioned by dbml-sharepoint from simple-test for list AppSettings.'],
      ['APP_Escalation', 'Provisioned by dbml-sharepoint from t for list Escalation.'],
    ]);
    const IGNORE_DESCRIPTION_WRITES = false;
    const DROP_LIST_MARKER_AFTER_READS = null;
    const DROP_LIST_MARKER_AFTER_READS_BY_TITLE = new Map([]);
    // Drop every list's marker the moment a named phase announces itself. A
    // read COUNT cannot name a phase boundary: it shifts as soon as any probe
    // is added earlier in the run, and the test then measures a different
    // boundary while still passing. The phase's own 'Starting Phase N.M:'
    // line IS the boundary, so watch stdout for it instead of counting.
    const DROP_LIST_MARKER_AT_PHASE = null;
    let phaseMarkerDropped = false;
    const listDescriptionReads = Object.create(null);
    const listDescription = (listTitle) => {
      const reads = listDescriptionReads[listTitle] || 0;
      listDescriptionReads[listTitle] = reads + 1;
      if (phaseMarkerDropped) return '';
      const dropAfter = DROP_LIST_MARKER_AFTER_READS_BY_TITLE.has(listTitle)
        ? DROP_LIST_MARKER_AFTER_READS_BY_TITLE.get(listTitle)
        : DROP_LIST_MARKER_AFTER_READS;
      if (Number.isInteger(dropAfter) && reads >= dropAfter) return '';
      if (LIST_DESCRIPTIONS.has(listTitle)) {
        return LIST_DESCRIPTIONS.get(listTitle) == null ? '' : LIST_DESCRIPTIONS.get(listTitle);
      }
      return DEFAULT_LIST_DESCRIPTIONS.get(listTitle) || '';
    };
    // #305: ownership sabotage armed at a PHASE BOUNDARY rather than after an
    // absolute read count. Every post-schema phase issues a different number
    // of list reads, so a count pins the test to today's request pattern
    // instead of to the boundary it means. SABOTAGE_AFTER_READS then allows
    // that many further reads of the named title before it bites: 0 breaks
    // the phase's ownership survey, 1 lets the survey pass and breaks the
    // recheck the write group makes immediately before mutating. Mode
    // 'marker' removes the provenance marker; 'rebind' keeps the marker and
    // answers with a different list Id, which is what a same-titled
    // replacement looks like from here. Rewritten by _run_ownership_deploy.
    const SABOTAGE_FROM_PHASE = null;
    const SABOTAGE_TITLES = [];
    const SABOTAGE_MODE = 'marker';
    const SABOTAGE_AFTER_READS = 0;
    const REPLACEMENT_LIST_ID = '55555555-5555-5555-5555-555555555555';
    // Titles this site does NOT have, so the by-title list probe answers 404.
    // Empty by default: every other test's fiction is that a probed list is
    // there. Exposed as the array itself so a test can arm it mid-run.
    const ABSENT_LIST_TITLES = [];
    globalThis.__absentListTitles = ABSENT_LIST_TITLES;
    let sabotageArmed = false;
    const sabotageReads = Object.create(null);
    // The phase every request belongs to, read off the run's own phase
    // banner. The call log carries it so a test can say "nothing was written
    // during THIS phase" without re-deriving phase boundaries from URLs.
    let mockPhase = null;
    const consoleLog = console.log.bind(console);
    console.log = (...args) => {
      const line = typeof args[0] === 'string' ? args[0] : '';
      const started = /Starting Phase ([0-9.]+):/.exec(line);
      if (DROP_LIST_MARKER_AT_PHASE != null
          && String(args[0]).includes(`Starting Phase ${DROP_LIST_MARKER_AT_PHASE}:`)) {
        phaseMarkerDropped = true;
      }
      if (started) {
        mockPhase = started[1];
        if (started[1] === SABOTAGE_FROM_PHASE) sabotageArmed = true;
      }
      // A phase that announces an abort has ended, even though its banner is
      // still the last one printed. What runs after it is the exit cleanup in
      // the run's finally, which re-seals what the run opened and belongs to
      // no phase. Attributing those writes to the aborted phase would make
      // every "this phase wrote nothing" assertion fail on the guarantee that
      // a failed run does not leave a column unsealed.
      if (/\[ERROR\].*aborting/.test(line)) mockPhase = null;
      consoleLog(...args);
    };
    const sabotageFor = (listTitle) => {
      if (!sabotageArmed || !SABOTAGE_TITLES.includes(listTitle)) return null;
      const seen = sabotageReads[listTitle] || 0;
      sabotageReads[listTitle] = seen + 1;
      return seen < SABOTAGE_AFTER_READS ? null : SABOTAGE_MODE;
    };
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
    // Existence for the by-name GET and its /users sub-resource: known from
    // the enumeration (case-insensitive, matching SharePoint's own group-name
    // resolution) or already written into GROUP_STATE by a create/MERGE this
    // run performed. Checked with hasOwnProperty rather than through
    // groupState() itself, whose `||=` would auto-vivify an absent name into
    // "existing" the instant it is asked about -- which is the exact hole
    // that let a read ahead of the create that makes it possible pass.
    const KNOWN_GROUP_NAME_SET = new Set(KNOWN_GROUP_NAMES.map((n) => String(n).toLowerCase()));
    const groupIsKnown = (name) => (
      KNOWN_GROUP_NAME_SET.has(String(name).toLowerCase())
      || Object.prototype.hasOwnProperty.call(GROUP_STATE, name)
    );
    // Group Id, historically fixed at 9 for every name -- harmless while the
    // owner probe below answered the same fixed value regardless of Id. A
    // test exercising TWO groups' owner state independently (one group
    // adopted, its declared owner_group a second, absent custom group) needs
    // them to resolve to DIFFERENT Ids, so this is now a per-name map,
    // defaulting every unconfigured name to the old fixed 9 so every
    // existing test is unaffected.
    const GROUP_IDS = {};
    const groupId = (name) => (GROUP_IDS[name] != null ? GROUP_IDS[name] : 9);
    // Current owner per governed-group Id (`web/sitegroups(N)/owner`), keyed
    // by the same Id groupId() hands out. Overridable per test so a declared
    // owner_group naming a CUSTOM group, rather than a built-in, can be
    // modelled as already correct -- exercising resolveGroupOwner without
    // also exercising CSOM ProcessQuery correction, which this mock does not
    // apply. Default (Id 9, i.e. every unconfigured name) matches the
    // built-in Site Owners every other test in this file declares as
    // owner_group, so their existing mismatch-free behaviour is unchanged.
    const GROUP_CURRENT_OWNER = { 9: { Id: 3, Title: 'Site Owners', PrincipalType: 8 } };
    const currentOwnerFor = (id) => (
      GROUP_CURRENT_OWNER[id] || { Id: 3, Title: 'Site Owners', PrincipalType: 8 }
    );
    // Role definitions (custom permission levels). Task 3: the single line
    // this replaces answered every roledefinitions read alike, whether it
    // was the existence probe, a getbyname resolve, or a by-Id read-back --
    // so a MERGE could never be observed landing or failing to land.
    // Seeded with the one level the fixture declares, 'Schema Manager'
    // (test/fixtures/sharepoint-mapping.yaml:72). Its default Description
    // already carries THIS family's marker, matching every other pre-existing
    // object in this harness's "adopted site" fiction: a level a prior run of
    // the same family already created and stamped, so a fresh run reconciles
    // it rather than refusing it. ROLE_DEF_ABSENT and
    // ROLE_DEF_DESCRIPTION_OVERRIDE let #224's adoption-gate tests put the
    // level through the create path, or give it an unmarked or
    // other-family-marked Description, without touching every other test.
    // ROLE_DEF_DROP_FIELD_ON_WRITE follows GROUP_DROP_FIELD_ON_WRITE: it
    // names one field the MERGE accepts but does not store, so a later test
    // can prove a permission-level read-back fails closed.
    let nextRoleDefId = 2;
    const ROLE_DEF_DROP_FIELD_ON_WRITE = null;
    const ROLE_DEF_SETTINGS_KEYS = ['Description', 'High', 'Low'];
    const ROLE_DEF_ABSENT = false;
    const ROLE_DEF_DESCRIPTION_OVERRIDE = null;
    const ROLE_DEF_STATE = ROLE_DEF_ABSENT ? {} : {
      'Schema Manager': {
        Id: 1,
        Description: ROLE_DEF_DESCRIPTION_OVERRIDE == null
          ? 'Test permission level. '
            + 'Provisioned by dbml-sharepoint from simple-test for level Schema Manager.'
          : ROLE_DEF_DESCRIPTION_OVERRIDE,
        BasePermissions: { High: '0', Low: '2049' },
      },
    };
    const roleDefState = (name) => (ROLE_DEF_STATE[name] ||= {
      Id: nextRoleDefId++, Description: '', BasePermissions: { High: '0', Low: '0' },
    });
    // Decode idiom shared with listOf/groupNameOf: odataName DOUBLES an
    // apostrophe and encodeURIComponent leaves it alone, so undo percent
    // encoding first and then the doubling.
    const roleDefFilterNameOf = (url) => {
      const raw = (url.match(/\$filter=Name eq '(.*?)'/) || [])[1];
      return raw == null ? raw : decodeURIComponent(raw).replace(/''/g, "'");
    };
    const roleDefByNameOf = (url) => {
      const raw = (url.match(/roledefinitions\/getbyname\('(.*?)'\)/) || [])[1];
      return raw == null ? raw : decodeURIComponent(raw).replace(/''/g, "'");
    };
    // The web/lists/getbytitle('X')/roleassignments enumeration
    // _acls.js.j2 reads to decide what a list already has bound, keyed by
    // list title. Configurable per title so a later test can exercise the
    // __next pagination path; empty by default, matching every other
    // probe's brand-new-site fiction ('nothing bound yet') so an
    // unconfigured run only ever adds.
    const ROLE_ASSIGNMENT_PAGES = {};
    const roleAssignmentPages = (listTitle) => ROLE_ASSIGNMENT_PAGES[listTitle] || [[]];
    // Per-list Title state, mutated by MERGEs exactly as SharePoint would.
    const titles = Object.create(null);
    // Indexed is state, not a constant: a lookup's TARGET carries the
    // picker's index on its display column, so any run with a lookup MERGEs
    // Indexed:true onto a Title and reads it back. Answering a fixed false
    // fails that read-back, which looks like a deploy defect.
    const TITLE_SETTINGS_KEYS = ['Sealed', 'Required', 'Description',
      'DefaultValue', 'Indexed'];
    const titleState = (listTitle) => (titles[listTitle] ||= {
      Sealed: true, Required: true, Description: '', DefaultValue: null,
      Indexed: false,
    });
    const titleField = (listTitle) => ({
      Id: '11111111-1111-1111-1111-111111111111',
      InternalName: 'Title', Title: 'Title', TypeAsString: 'Text',
      EnforceUniqueValues: false, ReadOnlyField: false,
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
    // List items. Without them the seed phase reads an empty list, inserts,
    // reads empty again and fails its own read-back, so no test could ever
    // reach the seeding write group; with them a seeded row persists exactly
    // as SharePoint would return it.
    const items = {};
    const itemsOf = (listTitle) => (items[listTitle] ||= []);
    // The list's content types. A list form's declared layout lives on the
    // default item content type, so without this the form phase finds no
    // content type at all and fails before its write group is reached.
    const contentTypes = {};
    const contentTypeState = (listTitle) => (contentTypes[listTitle] ||= {
      Name: 'Item', StringId: '0x0100AA', ClientFormCustomFormatter: null,
    });
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
      // A create body may declare Indexed itself (a DBML `indexes` block
      // reaches the field that way), and Phase 2.1 verifies that setting by
      // read-back like any other. Deriving it from EnforceUniqueValues alone
      // made every such column fail the phase it was created in.
      Indexed: b.Indexed === true || b.EnforceUniqueValues === true,
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
          // or a lookup-target probe names none of the shape columns; echo
          // what the field was created with, which is what the declaration
          // asked for. Every probe that wants the SHAPE selects Id first,
          // which is what tells the two apart: the index read-back selects
          // Id alone and is a shape probe, not a derived one.
          if (!url.includes('$select=Id')) return { d: f.__body };
          return { d: f };
        }
        const own = Object.entries(created)
          .filter(([k]) => k.startsWith(`${listTitle} `))
          .map(([, v]) => v);
        return { d: { results: [titleField(listTitle), ...own] } };
      }
      // Principals: enough shape to get PREPARE past 1.3/1.4 and reach the
      // maintenance unseal at 1.6. Before this, the runtime test had never
      // executed a phase beyond the read-only preflight.
      if (url.includes('AssociatedOwnerGroup') || url.includes('AssociatedMemberGroup')
          || url.includes('AssociatedVisitorGroup')) {
        return { d: { Id: 3, Title: 'Site Owners', PrincipalType: 8 } };
      }
      // A governed group's current owner (`web/sitegroups(N)/owner`), keyed
      // by the Id in the URL so two groups in the same run can carry
      // different current owners. See GROUP_CURRENT_OWNER above.
      if (url.includes('/owner')) {
        const idMatch = url.match(/sitegroups\((\d+)\)\/owner/);
        return { d: currentOwnerFor(idMatch ? Number(idMatch[1]) : 9) };
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
        // INFERRED, NOT MEASURED: the parent by-name GET answers 404 for an
        // absent group (measured; see surveyGroup in
        // _security_principals.js.j2), but what
        // this /users sub-resource answers for an absent group has not been
        // probed. 404 is used because the parent does and because either
        // status fails the template closed; a future probe should confirm
        // or correct this.
        if (!groupIsKnown(name)) {
          return { error: { code: '-2147024809, System.ArgumentException', status: 404 } };
        }
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
        // MEASURED (surveyGroup in _security_principals.js.j2): a by-name GET
        // for a site group that is not there answers 404. The role-definition
        // getbyname is NOT the same: that one answers 500 for an absent level,
        // which is why the template probes levels by $filter instead.
        // groupIsKnown is checked
        // before groupState(name), whose `||=` would otherwise auto-vivify
        // an absent name into "existing" the instant it is read.
        if (!groupIsKnown(name)) {
          return { error: { code: '-2147024809, System.ArgumentException', status: 404 } };
        }
        return { d: { Id: groupId(name), Title: name, PrincipalType: 8, ...groupState(name) } };
      }
      // Every roledefinitions read shares that substring, so the most
      // specific shape is checked first: the $filter existence probe (by
      // Name), a by-Id read-back, getbyname (both the MERGE target below
      // and what resolveRoleDefId GETs directly), then the bare collection
      // endpoint, which only a create POST reaches -- the write-application
      // block below has already recorded the new state by the time this
      // runs, so it is echoed back the way SharePoint would.
      if (url.includes('roledefinitions')) {
        const notFound = { error: { code: '-2147024809, System.ArgumentException' } };
        if (url.includes('$filter=Name')) {
          const state = ROLE_DEF_STATE[roleDefFilterNameOf(url)];
          const row = state ? [{ Id: state.Id, Description: state.Description }] : [];
          return { d: { results: row } };
        }
        const byId = url.match(/roledefinitions\((\d+)\)/);
        if (byId) {
          const state = Object.values(ROLE_DEF_STATE).find((s) => String(s.Id) === byId[1]);
          return state ? { d: state } : notFound;
        }
        if (url.includes('getbyname')) {
          const state = ROLE_DEF_STATE[roleDefByNameOf(url)];
          return state ? { d: state } : notFound;
        }
        if (opts && opts.body) {
          const parsed = JSON.parse(opts.body);
          const state = ROLE_DEF_STATE[parsed.Name];
          if (state) return { d: state };
        }
        return { d: { results: [] } };
      }
      // A list's role-assignment enumeration (Member + RoleDefinitionBindings),
      // paginated the same way the group membership mock pages
      // sitegroups/.../users: page 0 unless the caller followed a __next
      // this mock handed out.
      if (url.includes('/roleassignments')) {
        const listTitle = listOf(url);
        const pages = roleAssignmentPages(listTitle);
        const marked = /[?&]page=(\d+)/.exec(url);
        const page = marked ? Number(marked[1]) : 0;
        const payload = { d: { results: pages[page] || [] } };
        if (page + 1 < pages.length) {
          payload.d.__next =
            `https://example.sharepoint.com/_api/web/lists/getbytitle('${encodeURIComponent(listTitle)}')`
            + `/roleassignments?$expand=Member,RoleDefinitionBindings&page=${page + 1}`;
        }
        return payload;
      }
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
      if (url.includes('/contenttypes')) {
        const state = contentTypeState(listOf(url));
        return url.includes("contenttypes('")
          ? { d: state } : { d: { results: [state] } };
      }
      if (/\/items(\?|$)/.test(url)) {
        return { d: { results: itemsOf(listOf(url)) } };
      }
      // The seed phase resolves __metadata.type from the list rather than
      // hardcoding SP.Data.<Title>ListItem, so the mock has to answer it.
      if (url.includes('ListItemEntityTypeFullName')) {
        return { d: { ListItemEntityTypeFullName: `SP.Data.${listOf(url)}ListItem` } };
      }
      // The single list ENUMERATION. This mock's fiction is "any list probe
      // succeeds", which an enumeration cannot express, since it would have to
      // know the declared names. Refusing it exercises the documented
      // fallback in ensureKnownListTitles: enumeration unavailable, probe
      // per list. The fast path itself is NOT covered here.
      if (url.includes('web/lists?')) return { error: { code: 'enumeration-not-mocked' } };
      // A list probe: the list exists, matching the declared shape.
      if (url.includes('getbytitle') && url.includes('BaseTemplate')) {
        const probeTitle = listOf(url);
        // Unless a test says the site does not have it. The branch above
        // answers every title alike, which leaves the by-title 404 -- the
        // only way a run learns a declared list is GONE, now that the
        // ownership guard probes without enumerating first -- unreachable.
        // Mutable, so a test can arm it after the run it measures.
        if (ABSENT_LIST_TITLES.includes(probeTitle)) {
          return { error: { code: 'List not found', status: 404 } };
        }
        const sabotage = sabotageFor(probeTitle);
        // Called either way: it drives the read counter DROP_LIST_MARKER_
        // AFTER_READS uses, which must not depend on the sabotage knobs.
        const description = listDescription(probeTitle);
        return { d: {
          Id: sabotage === 'rebind'
            ? REPLACEMENT_LIST_ID : '22222222-2222-2222-2222-222222222222',
          Title: 'adopted', BaseTemplate: 100, ContentTypesEnabled: false,
          Description: sabotage === 'marker' ? '' : description,
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
                   phase: mockPhase,
                   body: opts.body === undefined ? null : opts.body });
      // Apply writes, exactly as SharePoint would, so readbacks converge.
      if ((opts.method || 'GET') === 'POST' && opts.body && u.includes('/fields')) {
        const parsed = JSON.parse(opts.body);
        const listTitle = listOf(u);
        const named = (u.match(/getbyinternalnameortitle\('([^']+)'\)/) || [])[1];
        const byId = (u.match(/\/fields\(guid'([^']+)'\)/) || [])[1];
        if (byId === '11111111-1111-1111-1111-111111111111') {
          for (const state of Object.values(titles)) {
            for (const k of TITLE_SETTINGS_KEYS) {
              if (parsed[k] !== undefined) state[k] = parsed[k];
            }
          }
        } else if (byId) {
          const f = Object.values(created).find(candidate => candidate.Id === byId);
          if (f && parsed.Sealed != null) f.Sealed = parsed.Sealed;
        } else if (named === 'Title') {
          for (const k of TITLE_SETTINGS_KEYS) {
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
            // Indexed and EnforceUniqueValues among them: the field
            // reconcile MERGEs whichever of these has drifted and then
            // verifies by read-back, so a mock that accepts the write and
            // keeps the old value fails the phase that made it.
            for (const k of ['Description', 'Required', 'DefaultValue', 'CustomFormatter',
                             'Indexed', 'EnforceUniqueValues']) {
              if (parsed[k] !== undefined) f[k] = parsed[k];
            }
          }
        } else if (parsed.Title) {
          created[`${listTitle} ${parsed.Title}`] = fieldShape(listTitle, parsed.Title, parsed);
        } else if (parsed.parameters && parsed.parameters.Title) {
          // FieldCollection.AddField. SharePoint refuses an SP.FieldLookup
          // POSTed to /fields, so a lookup create arrives with its
          // SP.FieldCreationInformation nested under `parameters`. Without
          // this branch the column is never recorded and the deferred-lookup
          // phase always fails its own read-back.
          const p = parsed.parameters;
          created[`${listTitle} ${p.Title}`] = fieldShape(listTitle, p.Title, {
            ...p,
            // AddField names the target LookupListId / LookupFieldName, and
            // the read-back probe asks for LookupList / LookupField. Recorded
            // under both spellings so the probe answers off __body, the same
            // route every hand-seeded lookup in this file already takes.
            LookupList: p.LookupListId,
            LookupField: p.LookupFieldName,
          });
        }
      }
      // A MERGE onto the LIST object itself. The URL ends at getbytitle(...)
      // with nothing after it, which is what separates a list write from a
      // field or view write under the same list. `[^/]*` rather than `[^']+`
      // for the title: odataName DOUBLES an apostrophe, so `[^']+` would miss
      // every list whose name has one and this mock would silently drop the
      // write while answering 200; see _LIST_WRITE_URL for the full note.
      // IGNORE_DESCRIPTION_WRITES drops it on purpose instead: a write
      // SharePoint reports as 200 and discards, which is the only state in
      // which the read-back can be watched failing.
      if ((opts.method || 'GET') === 'POST' && opts.body
          && (/getbytitle\('[^/]*'\)$/.test(u) || /lists\(guid'[^']+'\)$/.test(u))) {
        const parsed = JSON.parse(opts.body);
        if (parsed.Description !== undefined && !IGNORE_DESCRIPTION_WRITES) {
          let writtenTitle = listOf(u);
          if (!writtenTitle) {
            const marker = /(Provisioned by dbml-sharepoint from .* for list [^.]+\.)$/.exec(
              parsed.Description || '',
            );
            writtenTitle = marker && [
              ...LIST_DESCRIPTIONS.entries(), ...DEFAULT_LIST_DESCRIPTIONS.entries(),
            ].find(
              ([, description]) => String(description || '').includes(marker[1]),
            )?.[0];
          }
          if (writtenTitle) LIST_DESCRIPTIONS.set(writtenTitle, parsed.Description);
        }
      }
      if ((opts.method || 'GET') === 'POST' && opts.body && u.includes("/contenttypes('")) {
        const parsed = JSON.parse(opts.body);
        if (parsed.ClientFormCustomFormatter !== undefined) {
          contentTypeState(listOf(u)).ClientFormCustomFormatter = parsed.ClientFormCustomFormatter;
        }
      }
      if ((opts.method || 'GET') === 'POST' && opts.body && /\/items$/.test(u)) {
        const row = { Id: itemsOf(listOf(u)).length + 1 };
        for (const [key, value] of Object.entries(JSON.parse(opts.body))) {
          if (key !== '__metadata') row[key] = value;
        }
        itemsOf(listOf(u)).push(row);
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
      // A permission-level create (POST to .../web/roledefinitions) or a
      // MERGE onto the definition itself (POST to
      // .../roledefinitions/getbyname('...') with nothing after the closing
      // paren, matching the group write above). Mutates ROLE_DEF_STATE so a
      // later by-Id or by-name read-back sees what this write actually
      // stored, applying ROLE_DEF_DROP_FIELD_ON_WRITE the same way
      // GROUP_DROP_FIELD_ON_WRITE models a write the tenant 200s and
      // discards.
      if ((opts.method || 'GET') === 'POST' && opts.body
          && (u.endsWith('/roledefinitions') || /roledefinitions\/getbyname\('.*'\)$/.test(u))) {
        const parsed = JSON.parse(opts.body);
        if (parsed.__metadata && parsed.__metadata.type === 'SP.RoleDefinition') {
          const name = u.endsWith('/roledefinitions') ? parsed.Name : roleDefByNameOf(u);
          const state = roleDefState(name);
          const sent = {
            Description: parsed.Description,
            High: parsed.BasePermissions && parsed.BasePermissions.High,
            Low: parsed.BasePermissions && parsed.BasePermissions.Low,
          };
          for (const key of ROLE_DEF_SETTINGS_KEYS) {
            if (sent[key] === undefined || key === ROLE_DEF_DROP_FIELD_ON_WRITE) continue;
            if (key === 'Description') state.Description = sent[key];
            else state.BasePermissions[key] = sent[key];
          }
        }
      }
      const payload = body(u, opts);
      const absent = payload && payload.error;
      // Most absence mocks in this file don't carry a measured status and
      // default to 400. The site-group absence mocks above set one
      // explicitly (404), matching what is measured (or inferred) for them.
      const status = absent ? (payload.error.status || 400) : 200;
      return {
        ok: !absent, status,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
    globalThis.__calls = calls;
""") + BATCH_MOCK


def _run_deploy(harness: str, tail: str) -> str:
    script = harness + "\n" + _deploy_js().replace("})();", tail).replace(
        "(async () => {", "((async () => {", 1,
    )
    return _run(script)


def _summary_of(output: str) -> dict[str, Any]:
    """The summary object deploy.js returned, out of the Node transcript."""
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary: dict[str, Any] = json.loads(line.removeprefix("__RESULT__"))
    return summary


# The assessment gate's own tests. These deliberately do NOT stub: the gate is
# what is under test, so the run makes the assessment's real requests.
_ACK_FALSE = "const ACKNOWLEDGE_DEGRADED = false;"
_ACK_TRUE = "const ACKNOWLEDGE_DEGRADED = true;"


def _locked_harness() -> str:
    """`_HARNESS` with the same site answering as read-only.

    Only `site?$select=ReadOnly,LockIssue` carries `ReadOnly` in its URL, so
    one spliced branch is the single answer that separates a BLOCKED run from
    the DEGRADED one above it.
    """
    locked = _HARNESS.replace(
        "const body = (url) => {\n",
        "const body = (url) => {\n"
        "  if (url.includes('ReadOnly')) {\n"
        "    return { d: { ReadOnly: true, LockIssue: 'Locked for migration' } };\n"
        "  }\n",
        1,
    )
    assert locked != _HARNESS, "the locked branch was not spliced in"
    return locked


def _answers_the_lock_probe(base: str) -> str:
    """`base` with the site answering the lock probe it selects two properties from.

    `_HARNESS` replies `{d: {results: []}}` to everything it does not name, and
    a payload carrying neither `ReadOnly` nor `LockIssue` is now reported as a
    requirement nobody could assess rather than as a writable site. Any fixture
    whose verdict is meant to come from something else has to answer it.
    """
    answered = base.replace(
        "const body = (url) => {\n",
        "const body = (url) => {\n"
        "  if (url.includes('ReadOnly')) {\n"
        "    return { d: { ReadOnly: false, LockIssue: null } };\n"
        "  }\n",
        1,
    )
    assert answered != base, "the lock answer was not spliced in"
    return answered


def _template_stocked_harness() -> str:
    """`_HARNESS` with the one WARN it otherwise always raises answered away.

    `web/listtemplates` replies `{d: {results: []}}`, so `list_template_100`
    warns on every run against this mock and no verdict taken from it can say
    what caused the degradation.
    """
    stocked = _HARNESS.replace(
        "const body = (url) => {\n",
        "const body = (url) => {\n"
        "  if (url.includes('listtemplates')) {\n"
        "    return { d: { results: [{ ListTemplateTypeKind: 100 }] } };\n"
        "  }\n",
        1,
    )
    assert stocked != _HARNESS, "the list-template branch was not spliced in"
    return stocked


def _list_only_harness(*, template_creatable: bool = True) -> str:
    """`_HARNESS` with an operator who can manage lists but not ACLs.

    Splices off the healthy site rather than a second copy of it, so what
    this fixture changes is exactly what the tests using it are about: the
    ManagePermissions bit, and no declared list already on the site.

    `template_creatable` decides the verdict. True enumerates base template
    100 and the pack comes out COMPATIBLE; False leaves `list_template_100`
    warning, which is DEGRADED.
    """
    cleared = _HARNESS.replace(
        "{ High: 4294967295, Low: 4294967295 }",
        # Every right except ManagePermissions, which is Low bit 0x2000000.
        "{ High: 4294967295, Low: (4294967295 & ~0x2000000) >>> 0 }",
        1,
    )
    assert cleared != _HARNESS, "the ManagePermissions bit was not cleared"
    cleared = _answers_the_lock_probe(cleared)
    stocked = cleared
    if template_creatable:
        stocked = cleared.replace(
            "const body = (url) => {\n",
            "const body = (url) => {\n"
            "  if (url.includes('listtemplates')) {\n"
            "    return { d: { results: [{ ListTemplateTypeKind: 100 }] } };\n"
            "  }\n",
            1,
        )
        assert stocked != cleared, "the list-template branch was not spliced in"
    # A 404 on the declared list is a clean provision target, which passes the
    # collision requirement and raises no provenance-marker finding.
    absent = stocked.replace(
        "  return {\n    ok: true, status: 200,\n",
        "  if (/\\/lists\\/getbytitle\\('[^/]*'\\)$/.test(String(url).split('?')[0])) {\n"
        "    const missing = { error: { message: { value: 'List not found' } } };\n"
        "    return { ok: false, status: 404, headers: { get: () => null },\n"
        "             json: async () => missing,\n"
        "             text: async () => JSON.stringify(missing) };\n"
        "  }\n"
        "  return {\n    ok: true, status: 200,\n",
        1,
    )
    assert absent != stocked, "the absent-list branch was not spliced in"
    return absent


def _list_only_deploy_js(tmp_path: Path) -> str:
    """deploy.js for a pack that performs no ACL work of any kind.

    `requires_manage_permissions` is false for it, so neither the deploy's own
    preflight nor the assessment's requirement list asks for the bit.
    """
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
            }
        """,
        mapping=entities("Risk"),
    )
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


def _run_deploy_with_assessment(
    *, acknowledge: bool = False, harness: str = _HARNESS, js: str | None = None,
) -> str:
    """The Node transcript of a run whose assessment actually executes."""
    js = _deploy_js_with_assessment() if js is None else js
    if acknowledge:
        js = js.replace(_ACK_FALSE, _ACK_TRUE, 1)
        assert _ACK_TRUE in js, "the acknowledgement flag was not flipped"
    script = harness + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    return _run(script)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_degraded_site_stops_until_the_operator_acknowledges() -> None:
    """Stopping costs the operator a second paste, and it is worth it.

    Print-and-proceed would turn a real finding into a log line, which is the
    failure this design exists to prevent.
    """
    output = _run_deploy_with_assessment()
    summary = _summary_of(output)
    assert summary.get("aborted") == "assessment-degraded-unacknowledged", summary
    assert summary["assessment"]["verdict"] == "DEGRADED"
    # The abort is the gate's, not a schema failure wearing its name.
    assert not summary.get("errors"), summary["errors"]
    # Nothing past the gate ran, so no write phase was even entered.
    assert f"Starting Phase {pn('preflight')}" not in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_acknowledged_degraded_site_runs_on_past_the_gate() -> None:
    """The flag has to actually let the run through, or it is a dead end.

    A gate that refused both ways would look identical in the abort code and
    differ only in how far the run got, so the reach is asserted.
    """
    output = _run_deploy_with_assessment(acknowledge=True)
    summary = _summary_of(output)
    assert summary["assessment"]["verdict"] == "DEGRADED"
    assert summary.get("aborted") != "assessment-degraded-unacknowledged", summary
    assert f"Starting Phase {pn('preflight')}" in output, output[-3000:]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_blocked_site_stops_even_when_degradation_is_acknowledged() -> None:
    """An operator who sets the flag once leaves it set.

    A BLOCKED verdict the flag could wave through would therefore be waved
    through on every later paste, against every later site.
    """
    output = _run_deploy_with_assessment(
        acknowledge=True, harness=_locked_harness(),
    )
    summary = _summary_of(output)
    assert summary.get("aborted") == "assessment-blocked", summary
    assert summary["assessment"]["verdict"] == "BLOCKED"
    blocking = [
        f for f in summary["assessment"]["findings"] if f["level"] == "BLOCKED"
    ]
    assert [f["key"] for f in blocking] == ["site_not_locked"], blocking
    assert f"Starting Phase {pn('preflight')}" not in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_missing_list_ownership_blocks_embedded_assessment_before_preflight() -> None:
    from dbml_sharepoint.generators.assessgen import assess_targets
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.parser import parse_dbml

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    titles = assess_targets(schema, bundle, "default")["list_titles"]
    harness = _ADOPTED_HARNESS.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        "const LIST_DESCRIPTIONS = new Map("
        f"{json.dumps(list(dict.fromkeys(titles, '').items()))});",
    )

    output = _run_deploy_with_assessment(acknowledge=True, harness=harness)
    summary = _summary_of(output)

    assert summary["assessment"]["verdict"] == "BLOCKED"
    assert summary.get("aborted") == "assessment-blocked"
    assert f"Starting Phase {pn('preflight')}" not in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_pack_needing_no_acl_work_deploys_without_manage_permissions(
    tmp_path: Path,
) -> None:
    """The verdict decides, never the raw findings.

    `_assess_body` raises `manage_permissions_bit` at BLOCKED for any operator
    lacking the right, while the verdict counts only the keys THIS pack
    requires, and a list-only pack requires none. assessgen, jsgen and
    deploy.js's own preflight all admit that operator (see
    `test_manage_permissions_agreement`), so a gate reading the findings
    instead of the verdict refused a deployment the other three permit, and no
    flag could override it.
    """
    output = _run_deploy_with_assessment(
        js=_list_only_deploy_js(tmp_path), harness=_list_only_harness(),
    )
    summary = _summary_of(output)
    assert summary["assessment"]["verdict"] == "COMPATIBLE"
    # The finding is raised; acting on it is what must not happen. Asserted so
    # a fixture that stopped producing it could not pass this vacuously.
    blocking = [
        f["key"] for f in summary["assessment"]["findings"]
        if f["level"] == "BLOCKED"
    ]
    assert blocking == ["manage_permissions_bit"], blocking
    assert summary.get("aborted") != "assessment-blocked", summary
    assert f"Starting Phase {pn('preflight')}" in output, output[-3000:]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_degraded_stop_names_the_findings_it_does_not_gate_on(
    tmp_path: Path,
) -> None:
    """A BLOCKED finding the pack does not require still has to be readable.

    It no longer stops the run, so the list this stop prints is where an
    operator meets it while deciding whether to acknowledge. Printing WARN
    alone would hide the more serious of the two.
    """
    output = _run_deploy_with_assessment(
        js=_list_only_deploy_js(tmp_path),
        harness=_list_only_harness(template_creatable=False),
    )
    summary = _summary_of(output)
    assert summary["assessment"]["verdict"] == "DEGRADED"
    assert summary.get("aborted") == "assessment-degraded-unacknowledged", summary
    printed = [ln for ln in output.splitlines() if "[ERROR]" in ln]
    assert any("list_template_100" in ln for ln in printed), printed
    assert any("manage_permissions_bit" in ln for ln in printed), printed


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_degraded_stop_names_the_findings_nobody_could_assess() -> None:
    """NOT-ASSESSABLE degrades the verdict, so the stop has to name it too.

    Filtering the re-statement to WARN and BLOCKED left a site degrading only
    this way printing the generic abort line and nothing else, which is the
    state the re-statement exists to prevent. `_HARNESS` reaches it once its
    one WARN is answered: three provenance markers, the lock state and the
    version trim mode are all answered by payloads carrying none of the
    properties they select.
    """
    output = _run_deploy_with_assessment(harness=_template_stocked_harness())
    summary = _summary_of(output)
    findings = summary["assessment"]["findings"]
    assert summary["assessment"]["verdict"] == "DEGRADED"
    assert summary.get("aborted") == "assessment-degraded-unacknowledged", summary
    # Nothing WARNed or BLOCKED, so the verdict can only have come from the
    # level this test is about.
    assert not [
        f for f in findings if f["level"] in {"WARN", "BLOCKED"}
    ], findings
    unassessed = [
        f["key"] for f in findings
        if f["level"] == "NOT-ASSESSABLE" and f["tier"] != 3
    ]
    assert unassessed, findings
    printed = [ln for ln in output.splitlines() if "[ERROR]" in ln]
    for key in unassessed:
        assert any(key in ln for ln in printed), (key, printed)
    # Tier 3 is the same list on every site, and re-stating it here would bury
    # the findings that are about this one.
    assert not [ln for ln in printed if "not_assessable:" in ln], printed


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_throw_inside_the_assessment_still_names_the_abort() -> None:
    """An unhandled rejection hands the operator nothing at all.

    No `__RESULT__`, no abort code and no [ERROR] line, so a broken probe
    looks exactly like a script that never ran. The run does fail closed
    without writing, but every other phase abort returns a structured
    summary and this one has to as well.
    """
    js = _deploy_js_with_assessment().replace(
        '"base_templates"', '"base_templates_typo"', 1,
    )
    assert '"base_templates_typo"' in js, "the targets key was not renamed"
    output = _run_deploy_with_assessment(js=js)
    summary = _summary_of(output)
    assert summary.get("aborted") == "assessment-failed", summary
    assert "assess-targets-incomplete" in output
    assert f"Starting Phase {pn('preflight')}" not in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_every_not_assessable_finding_survives_into_the_deploy_summary() -> None:
    """Deploy must keep the findings that say nobody could check something.

    Counting them against the declared list, rather than asserting one exists,
    is what catches a collapse: dropping any into a PASS leaves the level
    present and the count short.
    """
    from dbml_sharepoint.generators.assessgen import NOT_ASSESSABLE

    summary = _summary_of(_run_deploy_with_assessment())
    findings = summary["assessment"]["findings"]
    # Tier 3, because the level is no longer that block's alone: a probe that
    # answered without the property it was asked for now says so at the same
    # level, and this test is about the printed honesty block surviving.
    unchecked = [
        f for f in findings if f["level"] == "NOT-ASSESSABLE" and f["tier"] == 3
    ]
    assert {f["detail"] for f in unchecked} == set(NOT_ASSESSABLE)
    assert len(unchecked) == len(NOT_ASSESSABLE), unchecked
    passed = {f["detail"] for f in findings if f["level"] == "PASS"}
    assert not passed & set(NOT_ASSESSABLE), passed & set(NOT_ASSESSABLE)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_sealed_builtin_title_does_not_abort_every_list() -> None:
    """`assertFieldImmutableShape` throws when a field is sealed and
    `field.seal` is falsy. Both synthetic Title objects omitted the key, so
    against a site whose Title is sealed EVERY list failed preflight, and
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
        and (
            "getbyinternalnameortitle('Title')" in c["url"]
            or "/fields(guid'" in c["url"]
        )
        and "Sealed" in c["body"]
    ]
    assert False in seal_writes, "a sealed Title was never unsealed for the run"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_adopted_run_reaches_the_write_phases() -> None:
    """Guards the reach of the harness itself.

    The original mock answered every field probe as absent and every list
    probe as malformed, so the run aborted in the read-only preflight: no
    phase past the preflight had ever executed in a test, which is how a bug
    in the list-creation field reconcile shipped in a green suite. If a
    future change quietly shortens this run, the coverage disappears
    silently, so the reach is asserted rather than assumed."""
    output = _run_deploy(
        _ADOPTED_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    reached = [ln.split("Starting Phase ")[1][:3] for ln in output.splitlines()
               if "Starting Phase " in ln]
    # By key, never by number: inserting a step renumbers every phase after
    # it, and a literal then names a DIFFERENT phase while still passing.
    # This test is about REACH; test_phases pins the numbering.
    for phase in (pn("preflight"), pn("security"), pn("enrolment"),
                  pn("unseal"), pn("lists")):
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
        and (
            "getbyinternalnameortitle('Title')" in c["url"]
            or "/fields(guid'" in c["url"]
        )
        and "Sealed" in c["body"]
    ]
    assert seal_writes[0] is False, f"PREPARE did not unseal Title: {seal_writes}"
    assert seal_writes[-1] is True, f"the run left Title unsealed: {seal_writes}"


# A POST to the LIST object itself: the path ends at getbytitle(...) with
# nothing after it. Anchored deliberately. A FIELD MERGE is a POST to
# `web/lists/getbytitle('X')/fields/getbyinternalnameortitle('Y')` and
# routinely carries a Description of its own (every column with a note has
# one), so a filter that only asks for `web/lists` in the URL counts column
# descriptions as list writes, and then no run can ever be observed NOT
# writing a list description, which is half of what these tests measure.
#
# The title is matched as `[^/]*`, NOT `[^']+` and NOT `.*`, and both of the
# rejected spellings are wrong in a way that passes:
#
#   [^']+  cannot match an OData-escaped apostrophe. `odataName`
#          (`_site_guard.js.j2`) DOUBLES `'` and encodeURIComponent leaves it
#          alone, so a list called `O'Brien Register` arrives as
#          getbytitle('O''Brien%20Register'), no match, so the idempotence
#          test observes zero writes for the happiest of reasons and passes.
#   .*     matches too much: greedy backtracking lets it swallow
#          `X')/fields/getbyinternalnameortitle('Y` and call a FIELD write a
#          list write, which is the false positive this anchor exists to stop.
#
# A SharePoint list title cannot contain `/`, and encodeURIComponent would
# percent-encode one anyway, so "no slash after the opening quote" separates
# the list object from everything nested under it. Both directions are pinned
# by test_the_list_write_matcher_survives_an_apostrophe.
_LIST_WRITE_URL = re.compile(
    r"(?:web/lists/getbytitle\('[^/]*'\)|web/lists\(guid'[0-9a-f-]+'\))$",
)


def _description_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every request that MERGEs a Description onto a list."""
    return [
        c for c in calls
        if c["method"] == "POST" and c["body"] and "Description" in c["body"]
        and _LIST_WRITE_URL.search(c["url"])
    ]


def _deployment_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutating requests, excluding read-only POST-shaped protocols."""
    return [
        call
        for call in calls
        if call["method"] == "POST"
        and "contextinfo" not in call["url"]
        and "ProcessQuery" not in call["url"]
    ]


def _field_writes(
    calls: list[dict[str, Any]], list_title: str | None = None,
) -> list[dict[str, Any]]:
    """POSTs into a list's `/fields` collection: creates and MERGEs alike.

    Matched on the collection rather than on the verb because
    `summary.columnsCreated` already counts creates, and it is the MERGE that
    it cannot see: a reconcile onto a list whose ownership was just lost
    writes without incrementing anything.

    `list_title` is compared against the by-title segment. Every caller passes
    a plain ASCII title, which `odataName` and encodeURIComponent both leave
    untouched; `_LIST_WRITE_URL` above records what an escaped one costs.
    """
    return [
        call
        for call in calls
        if call["method"] == "POST"
        and "/fields" in call["url"].split("?")[0]
        and (
            list_title is None
            or f"web/lists/getbytitle('{list_title}')/fields" in call["url"]
        )
    ]


def _addfield_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """POSTs that create a lookup column.

    SharePoint refuses an SP.FieldLookup POSTed to `/fields`, so every lookup
    create goes through FieldCollection.AddField instead. That makes it the
    one field write the deferred-lookup phase performs, and the thing to count
    when asking whether that phase wrote.
    """
    return [
        call
        for call in calls
        if call["method"] == "POST"
        and call["url"].split("?")[0].endswith("/fields/addfield")
    ]


def _declared_list_descriptions(
    tmp_path: Path, prefix: str = DEFAULT_PREFIX,
    *, table_names: tuple[str, ...] | None = None,
    self_reference: bool = False,
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

    schema, bundle = _declared_pack(
        tmp_path, "", prefix, table_names=table_names,
        self_reference=self_reference,
    )
    schema_json = build_schema_json(schema, bundle, "default")
    return {entry["title"]: entry["description"] for entry in schema_json["lists"]}


def _declared_list_markers(
    tmp_path: Path, prefix: str = DEFAULT_PREFIX,
) -> dict[str, str]:
    """List title -> the exact ownership marker emitted in SCHEMA."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _declared_pack(tmp_path, "", prefix)
    schema_json = build_schema_json(schema, bundle, "default")
    return {entry["title"]: entry["expected_marker"] for entry in schema_json["lists"]}


def _run_adopted_deploy(
    tmp_path: Path,
    list_description: str | dict[str, str],
    *,
    ignore_description_writes: bool = False,
    prefix: str = DEFAULT_PREFIX,
    expect_list_phase: bool = True,
    drop_marker_after_reads: int | None = None,
    drop_marker_after_reads_by_title: dict[str, int] | None = None,
    drop_marker_at_phase: str | None = None,
    table_names: tuple[str, ...] | None = None,
    self_reference: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run the emitted deploy against a site whose lists already exist.

    Built on `_declared_deploy_js`, not on the shipped `simple.dbml` fixture.
    That matters for the abort assertion: `test_a_declared_run_completes_every
    _phase_cleanly` pins this schema as finishing with NO errors and NO abort
    against `_ADOPTED_HARNESS`, whereas the simple fixture's adopted run
    already aborts on `phase-1-schema-errors` (the mock is too thin for its
    renamed and indexed columns). On that base `summary['aborted']` is truthy
    no matter what the description does, and the read-back test could not
    fail, which is worse than not having it.

    `list_description` is what the site HOLDS before the run: one string for
    every list, or a per-title mapping. `ignore_description_writes` makes the
    mock accept the MERGE with a 200 and keep serving the old value (a
    silently discarded write, which is the only state in which the read-back
    can be watched failing).

    `prefix` reaches the mapping's list-title prefix, which is how a caller
    deploys to a list whose title needs OData escaping.

    `drop_marker_at_phase` takes a dotted phase number and removes every
    list's marker as that phase announces itself, which names a boundary a
    read count cannot. `self_reference` reaches `_declared_pack`, and is what
    gives the run a deferred lookup to defer.

    Returns (summary, calls, output). The list phase must actually have
    started: otherwise a "nothing was written" assertion would pass against a
    run that aborted in the preflight and never reached the reconcile at all.
    """
    held = (
        dict.fromkeys(
            _declared_list_descriptions(
                tmp_path, prefix, table_names=table_names,
                self_reference=self_reference,
            ),
            list_description,
        )
        if isinstance(list_description, str) else dict(list_description)
    )
    harness = _ADOPTED_HARNESS.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(held.items()))});",
    ).replace(
        "const IGNORE_DESCRIPTION_WRITES = false;",
        f"const IGNORE_DESCRIPTION_WRITES = {json.dumps(ignore_description_writes)};",
    ).replace(
        "const DROP_LIST_MARKER_AFTER_READS = null;",
        f"const DROP_LIST_MARKER_AFTER_READS = {json.dumps(drop_marker_after_reads)};",
    ).replace(
        "const DROP_LIST_MARKER_AFTER_READS_BY_TITLE = new Map([]);",
        "const DROP_LIST_MARKER_AFTER_READS_BY_TITLE = new Map("
        f"{json.dumps(list((drop_marker_after_reads_by_title or {}).items()))});",
    ).replace(
        "const DROP_LIST_MARKER_AT_PHASE = null;",
        f"const DROP_LIST_MARKER_AT_PHASE = {json.dumps(drop_marker_at_phase)};",
    )
    script = harness + "\n" + _declared_deploy_js(
        tmp_path, "", prefix, table_names=table_names,
        self_reference=self_reference,
    ).replace(
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
    if expect_list_phase:
        assert f"Starting Phase {pn('lists')}" in output, (
            f"the list reconcile phase never ran:\n{output[-3000:]}"
        )
    return (
        json.loads(result_line.removeprefix("__RESULT__")),
        json.loads(calls_line.removeprefix("__CALLS__")),
        output,
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_existing_list_without_the_marker_is_refused_before_writes(
    tmp_path: Path,
) -> None:
    """A matching title and shape are information, not ownership authority."""
    summary, calls, output = _run_adopted_deploy(
        tmp_path, "something an owner typed",
        expect_list_phase=False,
    )
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    assert not _deployment_writes(calls), (
        f"a deployment write occurred before ownership refusal\n{output[-2000:]}"
    )
    assert any(
        "provenance marker" in error["error"] for error in summary["errors"]
    ), summary["errors"]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    "description",
    [
        "",
        marker_for("other", "Escalation"),
        marker_for("t", "OtherEntity"),
        "Provisioned by dbml-sharepoint from t/Escalation.",
    ],
)
def test_foreign_copied_and_legacy_markers_are_refused(
    tmp_path: Path,
    description: str,
) -> None:
    summary, calls, _ = _run_adopted_deploy(
        tmp_path,
        description,
        expect_list_phase=False,
    )

    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    assert not _deployment_writes(calls), calls


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("replacement", ["null", '""'])
def test_missing_or_empty_generated_expected_marker_fails_closed(
    tmp_path: Path,
    replacement: str,
) -> None:
    js = _declared_deploy_js(tmp_path, "")
    mutated, count = re.subn(
        r'"expected_marker": "[^"]+"',
        f'"expected_marker": {replacement}',
        js,
    )
    assert count == 1, "the one-list fixture did not expose one expected marker"
    script = _ADOPTED_HARNESS + "\n" + mutated.replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)

    output = _run(script)
    summary = _summary_of(output)
    calls_line = next(
        line for line in output.splitlines() if line.startswith("__CALLS__")
    )
    calls = json.loads(calls_line.removeprefix("__CALLS__"))

    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    assert not _deployment_writes(calls), calls


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_owned_list_named_proto_reaches_reconciliation(tmp_path: Path) -> None:
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _declared_pack(
        tmp_path, "", prefix='prefix: ""', table_name="__proto__",
    )
    built = build_schema_json(schema, bundle, "default")
    descriptions = {
        entry["title"]: entry["description"] for entry in built["lists"]
    }
    harness = _ADOPTED_HARNESS.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(descriptions.items()))});",
    )
    js = _declared_deploy_js(
        tmp_path, "", prefix='prefix: ""', table_name="__proto__",
    )
    script = harness + "\n" + js.replace(
        "})();",
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)

    output = _run(script)
    summary = _summary_of(output)

    assert summary.get("errors") == [], summary["errors"]
    assert summary.get("aborted") is None, (summary, output[-2000:])


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
def test_owned_list_with_human_prose_drift_is_repaired(tmp_path: Path) -> None:
    held = {
        title: f"An owner rewrote the note. {marker}"
        for title, marker in _declared_list_markers(tmp_path).items()
    }

    summary, calls, output = _run_adopted_deploy(tmp_path, held)

    assert summary.get("aborted") is None, summary
    assert _description_writes(calls), f"owned prose drift was not repaired\n{output[-2000:]}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_marker_disappearing_after_preflight_is_refused_before_reconcile(
    tmp_path: Path,
) -> None:
    summary, calls, output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path),
        drop_marker_after_reads=1,
        expect_list_phase=False,
    )

    assert summary.get("aborted") == "maintenance-ownership-errors", summary
    assert not _deployment_writes(calls), (
        f"a deployment write occurred after ownership disappeared\n{output[-2000:]}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_marker_disappearing_during_unseal_aborts_before_structure(
    tmp_path: Path,
) -> None:
    summary, calls, output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path),
        drop_marker_after_reads=2,
        expect_list_phase=False,
    )

    assert summary.get("aborted") == "maintenance-unseal-errors", summary
    assert not _deployment_writes(calls), (
        f"a deployment write followed the per-field ownership loss\n{output[-2000:]}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_marker_disappearing_after_wave_one_aborts_before_fields(
    tmp_path: Path,
) -> None:
    summary, _calls, _output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path),
        drop_marker_after_reads=6,
    )

    assert summary.get("aborted") == "field-wave-ownership-errors", summary
    assert summary["columnsCreated"] == 0, summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_marker_disappearing_at_field_lane_stops_the_wave(
    tmp_path: Path,
) -> None:
    summary, _calls, _output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path),
        drop_marker_after_reads=7,
    )

    assert summary.get("aborted") == "field-wave-ownership-loss", summary
    assert summary["columnsCreated"] == 0, summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_marker_disappearing_after_field_lane_entry_blocks_field_writes(
    tmp_path: Path,
) -> None:
    summary, _calls, _output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path),
        drop_marker_after_reads=8,
    )

    assert summary.get("aborted") == "field-wave-ownership-loss", summary
    assert summary["columnsCreated"] == 0, summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_ownership_loss_in_one_field_lane_stops_every_other_lane(
    tmp_path: Path,
) -> None:
    """One lane's ownership loss is phase-wide, not that lane's own business.

    Wave 2 provisions fields in one concurrent lane per list, and the
    per-field catch records an error and moves on to the next column. An
    ownership recheck that failed inside it was therefore recorded like a
    transient 403 and every other lane kept provisioning: structural writes
    that follow a KNOWN ownership loss, which is the state this gate exists
    to stop.

    The boundary is inside a phase rather than at its start, so it is named
    by a read count: read eight of `APP_Escalation`'s Description is its
    wave-2 lane entry, seven having gone to the preflight, the unseal, wave 1
    and the pre-wave re-survey. A count that drifts lands on a different
    boundary and changes the abort code, so it fails rather than passing on
    the wrong thing.
    """
    table_names = ("Escalation", "Second")
    summary, calls, output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path, table_names=table_names),
        table_names=table_names,
        drop_marker_after_reads_by_title={"APP_Escalation": 7},
    )

    assert summary.get("aborted") == "field-wave-ownership-loss", summary
    assert summary["columnsCreated"] == 0, summary
    assert not _field_writes(calls, "APP_Second"), (
        "the second lane went on writing fields after the first list lost "
        f"ownership\n{output[-2000:]}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_self_referencing_declaration_writes_its_deferred_lookup(
    tmp_path: Path,
) -> None:
    """The control for the gate below.

    "No lookup was written" passes just as happily against a fixture that had
    no lookup to write, so pin first that this one writes one.
    """
    summary, calls, output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path, self_reference=True),
        self_reference=True,
    )

    assert f"Starting Phase {pn('lookups')}" in output, output[-3000:]
    assert not summary.get("aborted"), summary
    assert _addfield_writes(calls), f"no deferred lookup was created\n{output[-3000:]}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_marker_disappearing_before_deferred_lookups_writes_nothing(
    tmp_path: Path,
) -> None:
    """The deferred phase wrote by a GUID map the field wave left behind.

    `listGuids` maps a declared title to the GUID read during the field wave.
    A list can lose its marker between that wave and this phase, and the
    cached entry kept the lookup writes flowing to a list nobody could still
    prove was ours.
    """
    summary, calls, output = _run_adopted_deploy(
        tmp_path,
        _declared_list_descriptions(tmp_path, self_reference=True),
        self_reference=True,
        drop_marker_at_phase=pn("lookups"),
    )

    assert summary.get("aborted") == "deferred-lookup-ownership-errors", summary
    assert not _addfield_writes(calls), (
        f"a deferred lookup was created after ownership was lost\n{output[-3000:]}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_wave_one_failure_on_one_list_aborts_before_other_list_fields(
    tmp_path: Path,
) -> None:
    table_names = ("Escalation", "Second")
    held = _declared_list_descriptions(tmp_path, table_names=table_names)
    summary, _calls, _output = _run_adopted_deploy(
        tmp_path,
        held,
        table_names=table_names,
        drop_marker_after_reads_by_title={"APP_Escalation": 4},
    )

    assert summary.get("aborted") == "wave-1-schema-errors", summary
    assert summary["columnsCreated"] == 0, summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_description_that_does_not_read_back_aborts(tmp_path: Path) -> None:
    """`AGENTS.md`: anything that writes must read back and verify.

    A MERGE that returns 200 while the stored value stays stale is the exact
    shape this repository exists to catch -- the deploy reports success and
    the list is still undiscoverable.
    """
    held = {
        title: f"An owner rewrote the note. {marker}"
        for title, marker in _declared_list_markers(tmp_path).items()
    }
    summary, calls, output = _run_adopted_deploy(
        tmp_path, held, ignore_description_writes=True,
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
    first quote and matches nothing, which does not look like a broken
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
    turns this red, where reasoning about it would just leave the other
    tests quietly passing on a name no fixture happens to use.
    """
    declared = _declared_list_descriptions(tmp_path, _APOSTROPHE_PREFIX)
    assert any("'" in title for title in declared), declared
    held = {
        title: f"typed by an owner. {marker}"
        for title, marker in _declared_list_markers(
            tmp_path, _APOSTROPHE_PREFIX,
        ).items()
    }
    summary, calls, output = _run_adopted_deploy(
        tmp_path, held, prefix=_APOSTROPHE_PREFIX,
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
# then records an error per column and takes its early return, the
# designed abort that skips ACL work on a broken schema. It also skips
# PROTECTION, which is where a Title unsealed at 1.6 used to be handed
# back. Only creation is refused: the 1.6 MERGE that unseals Title is a
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
    two (schema errors, lookup errors, enrolment errors) returns before
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
    # Without this the test could pass by never aborting at all, and a
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
        and (
            "getbyinternalnameortitle('Title')" in c["url"]
            or "/fields(guid'" in c["url"]
        )
        and "Sealed" in c["body"]
    ]
    assert seal_writes, "PREPARE never unsealed a Title, so there was nothing to restore"
    assert seal_writes[0] is False, f"PREPARE did not unseal Title: {seal_writes}"
    assert seal_writes[-1] is True, (
        f"the aborted run left Title unsealed: {seal_writes}; errors={summary['errors']}"
    )


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
        and (
            "getbyinternalnameortitle('Note')" in c["url"]
            or "/fields(guid'" in c["url"]
        )
        and "Sealed" in c["body"]
    ]
    assert seal_writes[0] is False, f"PREPARE did not unseal Note: {seal_writes}"
    assert seal_writes[-1] is True, f"the aborted run left Note unsealed: {seal_writes}"


_TWO_WRONG_PROPERTIES_HARNESS = _ADOPTED_HARNESS + textwrap.dedent(r"""
    // One adopted column wrong in two immutable properties at once. `fieldShape`
    // derives TypeAsString from FieldTypeKind, so both are set afterwards.
    const wrongNote = fieldShape('APP_Escalation', 'Note', {
      FieldTypeKind: 2, Required: false, Description: 'stale description', MaxLength: 255,
    });
    wrongNote.Sealed = true;
    wrongNote.TypeAsString = 'Note';
    created['APP_Escalation Note'] = wrongNote;
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_column_with_multiple_immutable_mismatches_reports_all_of_them(
    tmp_path: Path,
) -> None:
    """Reporting the first mismatch sends an operator round the loop once per fault.

    This column is wrong in both TypeAsString and Sealed, and the mapping declares
    no seal, so both are real. One error naming both is what makes the abort
    describe the column rather than the first thing checked about it.
    """
    js = _declared_deploy_js(tmp_path, "")
    script = _TWO_WRONG_PROPERTIES_HARNESS + "\n" + js.replace(
        "})();", "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)

    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    both = (
        "Existing field 'APP_Escalation.Note' has immutable TypeAsString 'Note'; "
        "expected 'Text' "
        "Existing field 'APP_Escalation.Note' is sealed; expected an unsealed declared field"
    )
    reported = [err["error"] for err in summary["errors"] if err.get("column") == "Note"]
    assert reported == [both]


# One adopted lookup column, correct in every property the collector can still
# compare, whose TARGET list has lost the display field the lookup names. The
# enumeration is what the non-fresh probe reads, so dropping Title from it is
# what makes expectedLookupFieldInternalName throw.
_UNRESOLVABLE_LOOKUP_TARGET_HARNESS = _ADOPTED_HARNESS.replace(
    "return { d: { results: [titleField(listTitle), ...own] } };",
    "return { d: { results: listTitle === 'APP_Project'\n"
    "          ? own : [titleField(listTitle), ...own] } };",
) + textwrap.dedent(r"""
    created['APP_Task Project'] = fieldShape('APP_Task', 'Project', {
      FieldTypeKind: 7, Title: 'Project', Required: true,
      LookupList: '22222222-2222-2222-2222-222222222222', LookupField: 'Title',
    });
""")


# The same unresolvable target, but the existing lookup also points at the wrong
# list. Both facts have to survive one run.
_WRONG_LIST_AND_UNRESOLVABLE_HARNESS = _UNRESOLVABLE_LOOKUP_TARGET_HARNESS.replace(
    "LookupList: '22222222-2222-2222-2222-222222222222', LookupField: 'Title',",
    "LookupList: '99999999-9999-9999-9999-999999999999', LookupField: 'Title',",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_wrong_target_list_survives_an_unresolvable_display_field() -> None:
    """The display-field probe throwing must not hide the wrong target list.

    Resolving the declared target ran before the list was compared, so its
    throw returned early and the operator needed another deploy to learn the
    lookup pointed at the wrong list at all.
    """
    output = _run_deploy(
        _WRONG_LIST_AND_UNRESOLVABLE_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, output[-3000:]
    summary = json.loads(line.removeprefix("__RESULT__"))
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    entry = next(
        (e for e in summary["errors"] if e.get("column") == "Project"), None,
    )
    assert entry is not None, summary["errors"]
    assert "targets list" in entry["error"], entry
    assert "target display field" in entry["error"], entry


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_lookup_whose_target_display_field_cannot_be_resolved_is_refused() -> None:
    """The catch around `expectedLookupFieldInternalName` records, it does not swallow.

    That resolve throws for a target display field that does not exist and for a
    probe that failed, and the collector catches it so the mismatches already
    found for the column are not discarded. Deleting the `notChecked` call inside
    the catch leaves an empty list, and the column is then adopted with a lookup
    target nothing ever verified.
    """
    output = _run_deploy(
        _UNRESOLVABLE_LOOKUP_TARGET_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    reported = [err["error"] for err in summary["errors"] if err.get("column") == "Project"]
    assert reported == [
        "Lookup 'APP_Task.Project' target display field 'APP_Project.Title' does not exist",
    ]


# One owned list carrying the wrong BaseTemplate. Every other list keeps the
# declared 100, so the abort has to name this one.
_WRONG_BASE_TEMPLATE_HARNESS = _ADOPTED_HARNESS.replace(
    "Title: 'adopted', BaseTemplate: 100, ContentTypesEnabled: false,",
    "Title: 'adopted', BaseTemplate: listOf(url) === 'APP_Task' ? 101 : 100,\n"
    "          ContentTypesEnabled: false,",
)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_existing_list_with_the_wrong_base_template_aborts_before_any_write() -> None:
    """Execute the immutable half of the combined adoptability classifier.

    Preflight collects both ownership and immutable mismatches before any
    write. A wrong BaseTemplate cannot be repaired and must stay visible even
    when the exact ownership marker is present.
    """
    output = _run_deploy(
        _WRONG_BASE_TEMPLATE_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    reported = [
        err["error"] for err in summary["errors"]
        if err.get("list") == "APP_Task" and not err.get("column")
    ]
    assert reported == [
        (
            "Existing 'APP_Task' has BaseTemplate 101; expected 100 for declared kind 'List'. "
            "SharePoint list/library templates are immutable; provision a clean object "
            "or perform an explicit migration."
        ),
    ]


# APP_Task gets the wrong template AND a column with the wrong type, so the
# run has something to say about the list and about one of its columns. DueDate
# because preflight probes declared columns only, and simple.dbml gives APP_Task
# just Title, Project and DueDate.
_WRONG_TEMPLATE_AND_COLUMN_HARNESS = _WRONG_BASE_TEMPLATE_HARNESS + textwrap.dedent(r"""
    // DisplayFormat because the declared DueDate owns it, so readFieldShape
    // probes for it and throws when the body has none. Without it this column
    // reached the report through the field lane's CATCH, which carries no
    // mismatches, and immutableFieldMismatches never ran at all.
    const wrongType = fieldShape('APP_Task', 'DueDate', {
      FieldTypeKind: 4, Required: false, Description: '', DisplayFormat: 0,
    });
    wrongType.TypeAsString = 'Text';
    created['APP_Task DueDate'] = wrongType;
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_with_a_wrong_template_still_reports_its_columns() -> None:
    """A list-level mismatch used to hide every column in that list.

    `preflightListShapes` was assigned after the assert threw, and the field
    wave filtered on it, so the operator saw one line, fixed it, re-pasted and
    met the column mismatches on the next run.

    The column entry has to carry a COLLECTED mismatch. A probe that threw
    reaches the same report through the field lane's catch and is
    indistinguishable by list and column name alone, so the compared property
    is asserted here.
    """
    summary = _summary_of(_run_deploy(
        _WRONG_TEMPLATE_AND_COLUMN_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ))
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    task = [err for err in summary["errors"] if err.get("list") == "APP_Task"]
    assert [err.get("column") for err in task] == [None, "DueDate"], task
    due_date = task[1]
    assert [
        (m["property"], m["declared"], m["actual"], m["checked"])
        for m in due_date.get("mismatches", [])
    ] == [("TypeAsString", "DateTime", "Text", True)], due_date


# One list's metadata read fails outright, while a lookup in another list
# targets it. 500 rather than 503: fetchWithRetry does not retry 500. The
# adopted lookup column has to exist, because `_ADOPTED_HARNESS` answers every
# field probe absent and the field wave skips a column it cannot read.
_UNREADABLE_LOOKUP_TARGET_HARNESS = _ADOPTED_HARNESS + textwrap.dedent(r"""
    created['APP_Task Project'] = fieldShape('APP_Task', 'Project', {
      FieldTypeKind: 7, Title: 'Project', Required: true,
      LookupList: '22222222-2222-2222-2222-222222222222', LookupField: 'Title',
    });
    const _passThrough = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const readingProjectShape = u.includes("getbytitle('APP_Project')")
        && u.includes('BaseTemplate');
      if (!readingProjectShape) return _passThrough(url, opts);
      const payload = { error: { message: { value: 'list metadata unavailable' } } };
      return {
        ok: false, status: 500,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_lookup_into_an_unreadable_list_is_not_checked_rather_than_missing() -> None:
    """Saying "does not exist" about an unreadable list blames the wrong object.

    The operator reads it as a schema error in the list holding the lookup and
    goes looking there, when the fault is the target list nobody could read.
    """
    summary = _summary_of(_run_deploy(
        _UNREADABLE_LOOKUP_TARGET_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ))
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    lookups = [
        err["error"] for err in summary["errors"] if err.get("column") == "Project"
    ]
    assert lookups, summary["errors"]
    assert "could not be read" in lookups[0], lookups
    assert "does not yet exist" not in lookups[0], lookups


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_abort_prints_the_delta_grouped_by_list_and_column() -> None:
    """Four concurrent lanes interleave their own ERROR lines.

    The grouped report is what an operator reads after the run stops, so it
    has to name each property with both values rather than one joined
    sentence per column.
    """
    output = _run_deploy(
        _WRONG_TEMPLATE_AND_COLUMN_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    assert "Existing-schema shape delta:" in output, output[-3000:]
    assert "  APP_Task" in output, output[-3000:]
    assert "    DueDate" in output, output[-3000:]
    assert "BaseTemplate: declared 100, readback 101" in output, output[-3000:]
    # The compared-property line, not just the column heading. A column whose
    # probe threw prints the same heading followed by NOT CHECKED, so this is
    # the only part of the report that says a comparison actually happened.
    assert (
        'TypeAsString: declared "DateTime", readback "Text"' in output
    ), output[-3000:]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unreadable_list_reports_that_no_column_was_checked() -> None:
    """Reporting no column mismatches for a list nobody read is a false pass."""
    output = _run_deploy(
        _UNREADABLE_LOOKUP_TARGET_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    )
    assert "No column was checked" in output, output[-3000:]
    # Named per property, not just anywhere in the transcript: the printer's own
    # unreadable-list line says NOT CHECKED too, and would satisfy a bare
    # substring assertion while every uncompared property printed as a difference.
    assert "LookupList: NOT CHECKED" in output, output[-3000:]


# The mirror of `_UNREADABLE_LOOKUP_TARGET_HARNESS`: the same adopted lookup,
# but its target list is ABSENT rather than unreadable. 404 rather than 500,
# because `readListShape` returns null only on 404 and throws on anything else,
# and null is what records the 'absent' outcome.
_ABSENT_LOOKUP_TARGET_HARNESS = _ADOPTED_HARNESS + textwrap.dedent(r"""
    created['APP_Task Project'] = fieldShape('APP_Task', 'Project', {
      FieldTypeKind: 7, Title: 'Project', Required: true,
      LookupList: '22222222-2222-2222-2222-222222222222', LookupField: 'Title',
    });
    const _passThrough = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const readingProjectShape = u.includes("getbytitle('APP_Project')")
        && u.includes('BaseTemplate');
      if (!readingProjectShape) return _passThrough(url, opts);
      const payload = { error: { message: { value: 'list not found' } } };
      return {
        ok: false, status: 404,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_lookup_into_an_absent_list_is_a_certain_refusal() -> None:
    """'absent' and 'ok' must not collapse into the same sentence.

    An absent target list means adoption is impossible and the refusal is
    certain, so the column is reported as compared. Every other reason
    `targetGuid` is falsy means nobody resolved the target, which is reported
    as not checked. Substituting 'ok' for the recorded 'absent' outcome
    downgrades this certain refusal to "nobody looked", so both the sentence
    and `checked` are pinned.
    """
    summary = _summary_of(_run_deploy(
        _ABSENT_LOOKUP_TARGET_HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ))
    assert summary.get("aborted") == "existing-schema-shape-errors", summary
    lookups = [err for err in summary["errors"] if err.get("column") == "Project"]
    assert lookups, summary["errors"]
    assert lookups[0]["error"] == (
        "Existing lookup 'APP_Task.Project' cannot be adopted because declared "
        "target list 'APP_Project' does not yet exist"
    ), lookups
    assert [
        (m["property"], m["checked"]) for m in lookups[0].get("mismatches", [])
    ] == [("LookupList", True)], lookups


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_list_that_does_not_exist_is_silent_in_preflight() -> None:
    """A first deploy has nothing to adopt, so preflight must say nothing.

    `_HARNESS` is the brand-new-site mock: its list enumeration is empty, so
    `readListShape` answers every declared list absent. What keeps an absent
    list out of the field wave is the early return rather than the recorded
    outcome, so this pins the silence rather than the literal. The literal
    itself is pinned by
    `test_a_lookup_into_an_absent_list_is_a_certain_refusal`.
    """
    summary = _summary_of(_run_deploy(
        _HARNESS,
        "}))().then(r => console.log('__RESULT__' + JSON.stringify(r)))",
    ))
    assert [e for e in summary["errors"] if e.get("phase") == "preflight"] == []


# The collector's two collaborators. Stubbed because this test is about what the
# collector RECORDS, not about how a declaration is read or a probe is answered.
_COLLECTOR_STUBS = textwrap.dedent("""
    let TARGET_DISPLAY_FIELD = { InternalName: 'Title' };
    const declaredFieldState = () => ({ typeAsString: 'Lookup' });
    const readFieldShape = async () => TARGET_DISPLAY_FIELD;
""")

_COLLECTOR_SCENARIOS = textwrap.dedent("""
    const GUID = '22222222-2222-2222-2222-222222222222';
    const field = {
      title: 'Project', seal: false, target_list: 'APP_Project',
      body: { LookupField: 'Title', FieldTypeKind: 7 },
    };
    const actual = {
      InternalName: 'Project', TypeAsString: 'Lookup', ReadOnlyField: false,
      Sealed: false, LookupList: `{${GUID}}`, LookupField: 'Title',
    };
    (async () => {
      const out = {};
      out.absentTarget = await immutableFieldMismatches('APP_Task', field, actual, null);
      TARGET_DISPLAY_FIELD = null;
      out.probeThrew = await immutableFieldMismatches('APP_Task', field, actual, GUID);
      TARGET_DISPLAY_FIELD = { InternalName: 'Title' };
      out.displayFieldOnly = await immutableFieldMismatches(
        'APP_Task', field, { ...actual, LookupField: 'Other' }, GUID);
      console.log('__OUT__' + JSON.stringify(out));
    })();
""")


def _lifted(script: str, header: str) -> str:
    """A two-space-indented declaration lifted whole out of the emitted script.

    The emitted functions sit at that indent inside the IIFE, so the first
    `\\n  }` after the declaration is the function's own closing brace. Lifting
    the shipped source rather than copying it: a copy keeps passing after the
    real one changes.
    """
    start = script.index(header)
    rest = script[start:]
    end = rest.index("\n  }") + len("\n  }")
    return rest[:end]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_field_collector_records_what_it_compared_and_what_it_could_not() -> None:
    """`checked` separates "compared and differed" from "could not be compared".

    An absent target list is the first kind: the declared list is not there,
    adoption is impossible, and the refusal is certain. A target-display-field
    probe that threw is the second: the property may well match, and a report
    must not present it as a difference. Nothing asserted either value before.

    Property attribution is pinned here too. One entry covered a two-property
    condition and hard-coded 'LookupList', so a column differing only in
    LookupField named the wrong property and carried two GUIDs differing only in
    the normalisation `normalizeGuid` exists to erase.
    """
    script = _deploy_js()
    program = "\n".join([
        _COLLECTOR_STUBS,
        next(ln for ln in script.splitlines() if "const normalizeGuid =" in ln),
        _lifted(script, "async function expectedLookupFieldInternalName"),
        _lifted(script, "async function immutableFieldMismatches"),
        _COLLECTOR_SCENARIOS,
    ])
    output = _run(program)
    line = next((ln for ln in output.splitlines() if ln.startswith("__OUT__")), None)
    assert line is not None, f"the collector produced no output:\n{output[-3000:]}"
    out = json.loads(line.removeprefix("__OUT__"))

    assert [(m["property"], m["checked"]) for m in out["absentTarget"]] == [
        ("LookupList", True),
    ]
    assert [(m["property"], m["checked"]) for m in out["probeThrew"]] == [
        ("LookupField", False),
    ]
    assert out["probeThrew"][0]["actual"] is None
    assert [(m["property"], m["checked"]) for m in out["displayFieldOnly"]] == [
        ("LookupField", True),
    ]
    assert out["displayFieldOnly"][0]["declared"] == "Title"
    assert out["displayFieldOnly"][0]["actual"] == "Other"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_declared_run_completes_every_phase_cleanly(tmp_path: Path) -> None:
    """The end-to-end guard, and the one that gives the others their value.

    The original mock aborted in the read-only preflight, so no phase past
    the preflight had ever executed in a test, which is how a bug in the
    list-creation field reconcile shipped in a green suite. This run adopts
    an existing site, unseals, creates, reconciles declared formulas, seals
    and seeds, and must finish with no errors and no abort. If a future
    change shortens it, the coverage disappears silently unless this fails.
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
    # By key, never by number. The stubbed assessment banner prints on every
    # run, so a literal "1.1" here asserted nothing once the assessment took
    # that number.
    for phase in (pn("preflight"), pn("unseal"), pn("lists"), pn("views"),
                  pn("seal"), pn("seeds")):
        assert phase in reached, f"phase {phase} not reached: {reached}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_seal_phase_writes_one_batch_per_list(tmp_path: Path) -> None:
    """The seals travel as ChangeSet parts, one $batch per list.

    A burst of one MERGE per column is the shape that got a nine-list run
    throttled mid-phase (#401). Asserting the transport rather than the
    outcome, because the outcome is identical either way: the columns end
    sealed whether the writes went singly or batched, so nothing else in the
    suite can see this stop working.
    """
    body = _declared_deploy_js(tmp_path, "").rstrip()
    assert body.endswith("})();")
    output = _run(
        f"{_ADOPTED_HARNESS}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__BATCHES__' + JSON.stringify(globalThis.__batches));\n"
        "});\n",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__BATCHES__")), None,
    )
    assert line is not None, f"deploy.js sent no $batch at all:\n{output[-3000:]}"
    batches = json.loads(line.removeprefix("__BATCHES__"))

    sealing = [
        b for b in batches
        if any('"Sealed":true' in (op["body"] or "") for op in b["ops"])
    ]
    assert sealing, f"no seal write travelled as a ChangeSet part: {batches}"
    for batch in sealing:
        list_ids = {
            match.group(1) for match in (
                re.search(r"lists\(guid'([^']+)'\)", op["url"]) for op in batch["ops"]
            ) if match
        }
        assert len(list_ids) == 1, (
            f"one ChangeSet spans {len(list_ids)} lists; the lane boundary is "
            "the batch boundary because same-list field writes race"
        )
        for op in batch["ops"]:
            assert op["method"] == "MERGE", (
                "a seal part would POST rather than MERGE the field"
            )
            assert "/fields(guid'" in op["url"], (
                "a seal part addresses the field by name, which a rebind can "
                "redirect; patchFieldById addresses it by Id"
            )

    # The phase reports what LANDED, and every landed write was a part.
    reported = sum(
        int(match.group(1)) for match in (
            re.search(r"\((\d+) newly sealed\)", ln) for ln in output.splitlines()
        ) if match
    )
    parts = sum(
        1 for b in sealing for op in b["ops"] if '"Sealed":true' in (op["body"] or "")
    )
    assert parts == reported, (
        f"{parts} seal part(s) went out but the phase reported {reported} sealed"
    )


# Two groups on one level, so the list has two grants to make and a
# ChangeSet that coalesces them is distinguishable from one that does not.
# The harness's markers are spelled for the family it was written against,
# so the declared family is substituted into them below.
_TWO_GRANT_ACL = """
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
  - name: "List Reader"
    description: "Second test group."
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
      - principal: { kind: group, name: "List Reader" }
        level: "Schema Manager"
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_acl_phase_batches_its_adds_and_only_its_adds(tmp_path: Path) -> None:
    """The grants travel as ChangeSet parts; nothing ordered joins them.

    addroleassignment is a function invocation with no body, and a list's
    grants are independent of one another. breakroleinheritance is not: it
    has to have run before any of them, and the enumeration that decides
    which are missing has to have been read before that. So a ChangeSet here
    must carry adds, all of the list's adds, and nothing else.
    """
    body = _declared_deploy_js(tmp_path, _TWO_GRANT_ACL).rstrip()
    assert body.endswith("})();")
    output = _run(
        f"{_ADOPTED_HARNESS.replace('simple-test', 't')}\n({body[:-1]}).then(() => {{\n"
        "  console.log('__BATCHES__' + JSON.stringify(globalThis.__batches));\n"
        "});\n",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__BATCHES__")), None,
    )
    assert line is not None, f"deploy.js sent no $batch at all:\n{output[-3000:]}"
    batches = json.loads(line.removeprefix("__BATCHES__"))

    adding = [
        b for b in batches
        if any("addroleassignment(" in op["url"] for op in b["ops"])
    ]
    assert adding, f"no role-assignment grant travelled as a ChangeSet part: {batches}"
    assert len(adding) == 1, (
        f"the list's two grants went out as {len(adding)} $batch requests; "
        "they are settled by one read and belong in one ChangeSet"
    )
    assert len(adding[0]["ops"]) == 2, (
        f"expected both declared grants as parts, got {adding[0]['ops']}"
    )
    for op in adding[0]["ops"]:
        assert "addroleassignment(" in op["url"], (
            f"an ordered ACL call shares a ChangeSet with the adds: {op['url']}"
        )
        assert op["method"] == "POST", (
            "addroleassignment is a POST as a single write and stays one as a "
            f"part, not {op['method']}"
        )
        assert op["body"] is None, (
            "the arguments belong in the URL; a body here is not what the "
            "single write sent"
        )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_index_phase_batches_a_list_s_index_writes(tmp_path: Path) -> None:
    """Indexed:true travels as ChangeSet parts, one $batch per list.

    Two indexed columns on one list, so a batch that coalesces them is
    distinguishable from one request per column: the declared index on Note
    plus the lookup display column the picker indexes.
    """
    body = _declared_deploy_js(
        tmp_path, "", self_reference=True,
        extra_lines=("indexes {", "(Note)", "}"),
    ).rstrip()
    assert body.endswith("})();")
    output = _run(
        f"{_ADOPTED_HARNESS}\n({body[:-1]}).then(() => {{\n"
        "  console.log('__BATCHES__' + JSON.stringify(globalThis.__batches));\n"
        "});\n",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__BATCHES__")), None,
    )
    assert line is not None, f"deploy.js sent no $batch at all:\n{output[-3000:]}"
    batches = json.loads(line.removeprefix("__BATCHES__"))

    indexing = [
        b for b in batches
        if any('"Indexed":true' in (op["body"] or "") for op in b["ops"])
    ]
    assert indexing, f"no index write travelled as a ChangeSet part: {batches}"
    assert len(indexing) == 1, (
        f"the list's index writes went out as {len(indexing)} $batch requests"
    )
    assert len(indexing[0]["ops"]) == 2, (
        f"expected both indexed columns as parts, got {indexing[0]['ops']}"
    )
    for op in indexing[0]["ops"]:
        assert op["method"] == "MERGE", (
            "an index part would POST rather than MERGE the field"
        )
        assert "/fields(guid'" in op["url"], (
            "an index part addresses the field by name, which a rebind can "
            "redirect; the write it replaces went by Id"
        )
        assert '"Indexed":true' in (op["body"] or ""), (
            f"an unrelated write shares the index ChangeSet: {op['body']}"
        )
    list_ids = {
        match.group(1) for match in (
            re.search(r"lists\(guid'([^']+)'\)", op["url"])
            for op in indexing[0]["ops"]
        ) if match
    }
    assert len(list_ids) == 1, (
        f"one ChangeSet spans {len(list_ids)} lists; the list is the boundary "
        "the seal phase draws and this phase makes no wider claim"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_index_readback_reads_every_column_as_one_query_batch(
    tmp_path: Path,
) -> None:
    """The verification is batched, not sampled: N columns, N query parts.

    `Indexed` is a property SharePoint can silently drop, so every declared
    column is read back after the write and compared. What changed is only the
    transport -- the read-backs travel as top-level `$batch` query parts in one
    request instead of one GET each -- and this pins BOTH halves of that: the
    count still matches the columns, and it still went out once.

    The parts are asserted to address each field THROUGH ITS LIST TITLE. That
    spelling is what makes the surviving list check safe to do once per list
    rather than once per column: a list swapped out between two read-backs
    answers with a different field Id, or with none, and the column still
    fails.
    """
    body = _declared_deploy_js(
        tmp_path, "", self_reference=True,
        extra_lines=("indexes {", "(Note)", "}"),
    ).rstrip()
    assert body.endswith("})();")
    output = _run(
        f"{_ADOPTED_HARNESS}\n({body[:-1]}).then(() => {{\n"
        "  console.log('__BATCHES__' + JSON.stringify(globalThis.__batches));\n"
        "});\n",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__BATCHES__")), None,
    )
    assert line is not None, f"deploy.js sent no $batch at all:\n{output[-3000:]}"
    batches = json.loads(line.removeprefix("__BATCHES__"))

    reads = [
        b for b in batches
        if b["ops"] and all(
            op["method"] == "GET" and "/fields/getbyinternalnameortitle('" in op["url"]
            for op in b["ops"]
        )
    ]
    assert reads, (
        f"no field read-back travelled as a $batch of query parts: {batches}"
    )
    assert len(reads) == 1, (
        f"the index read-back went out as {len(reads)} $batch requests; two "
        "columns fit in one envelope and splitting is the budget, not the phase"
    )
    assert len(reads[0]["ops"]) == 2, (
        "the read-back did not read every indexed column back, which is the "
        f"one thing batching them may not change: {reads[0]['ops']}"
    )
    for op in reads[0]["ops"]:
        assert op["body"] is None, f"a query part carried a body: {op['body']}"
        assert "$select=Id" in op["url"], (
            "the read-back asks for more than the identity it compares: "
            f"{op['url']}"
        )
        assert "/lists/getbytitle('" in op["url"], (
            "a query part addresses its field through a list GUID; the "
            "surviving per-list ownership check depends on the TITLE spelling "
            f"to catch a swapped list: {op['url']}"
        )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_index_readback_fails_every_column_closed(
    tmp_path: Path,
) -> None:
    """A read-back that could not run is reported per column, not skipped.

    Batching moves every column's verification behind ONE request, so a
    refusal of that request is a phase-wide event where it used to be a
    per-column one. The failure mode this exists to refuse is the phase
    logging one transport error and then reporting the columns as verified.
    Each column names itself, exactly as it would have under single GETs.
    """
    body = _declared_deploy_js(
        tmp_path, "", self_reference=True,
        extra_lines=("indexes {", "(Note)", "}"),
    ).rstrip()
    assert body.endswith("})();")
    # Refuses ONLY the read envelope, so the index writes still land: what is
    # measured is a verification that could not run, not an index never
    # written. An unparseable 200 is the shape that matters -- the outer
    # request is `ok`, and a reader that trusted that would return nothing and
    # report everything.
    refuse_reads = textwrap.dedent(r"""
        {
          const _under = globalThis.fetch;
          globalThis.fetch = async (url, opts = {}) => {
            const sent = String((opts && opts.body) || '');
            if (/\/_api\/\$batch$/.test(String(url)) && sent.includes('GET ')) {
              return {
                ok: true, status: 200, url: String(url),
                headers: { get: () => null },
                json: async () => ({}),
                text: async () => 'nothing parseable here',
              };
            }
            return _under(url, opts);
          };
        }
    """)
    output = _run(
        f"{_ADOPTED_HARNESS}\n{refuse_reads}\n({body[:-1]})"
        ".then(r => console.log('__RESULT__' + JSON.stringify(r)));\n",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(line.removeprefix("__RESULT__"))

    unread = [
        err for err in (summary.get("errors") or [])
        if "not read back" in str(err.get("error", ""))
    ]
    assert len(unread) == 2, (
        "a refused read-back left indexed columns reported as verified; "
        f"expected both named, got {summary.get('errors')}"
    )
    assert {err["column"] for err in unread} == {"Note", "Title"}, (
        f"the columns that went unverified are not named: {unread}"
    )
    assert "[ERROR] Index readback:" in output, (
        "the transport refusal never reached the transcript the operator "
        "pastes back, so the per-column errors have no cause"
    )


# Two views on one list, declaring the SAME two columns in OPPOSITE orders.
# That is what makes both claims below visible at once: a ChangeSet drawn
# around the wrong unit merges them, and a transport that reorders parts
# cannot produce two batches that disagree. Single-word titles for the same
# reason `_GUARDED_VIEWS` uses them: a title equal to its own URL slug keeps
# the mock's view state under one key across the create-then-rename.
_TWO_VIEW_ORDERS = """
views:
  Escalation:
    - title: "TitleFirst"
      fields: [Title, Note]
    - title: "NoteFirst"
      fields: [Note, Title]
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_views_phase_batches_a_view_s_field_writes(tmp_path: Path) -> None:
    """The column reset and adds travel as ChangeSet parts, one $batch per view.

    445 of the views phase's 1,221 requests on a ten-list family were
    addviewfield, the largest single bucket in the deploy, and the deploy is
    throttle-bound, so the count is what costs.

    ORDER is asserted, not just membership. A view's column order is a
    declared setting, OData v3 says a ChangeSet MAY be reordered, and the
    live measurement that says SharePoint does not is recorded at the call
    site. This pins the half that is ours: the parts leave in declared order,
    with the reset first, so a reordering here would be a bug in the deploy
    rather than in the tenant.
    """
    body = _declared_deploy_js(tmp_path, _TWO_VIEW_ORDERS).rstrip()
    assert body.endswith("})();")
    # The harness that keeps per-view state. `_ADOPTED_HARNESS` alone gives
    # every view one id and one .aspx name, so two declared views read back
    # as the same object and fail their own URL check. No policy: neither
    # view is filtered, so the settings page it also serves is never asked
    # for.
    output = _run(
        f"{_view_guard_harness({})}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__BATCHES__' + JSON.stringify(globalThis.__batches));\n"
        "});\n",
    )
    summary = _summary_of(output)
    assert summary.get("errors") == [], summary["errors"]
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__BATCHES__")), None,
    )
    assert line is not None, f"deploy.js sent no $batch at all:\n{output[-3000:]}"
    batches = json.loads(line.removeprefix("__BATCHES__"))

    fielding = [
        b for b in batches
        if any("/viewfields/" in op["url"] for op in b["ops"])
    ]
    # Three views, not two: the deployer also reconciles the built-in All
    # Items. One request each is the claim, and the view is the boundary
    # because the reset clears the whole collection and a ChangeSet drawn any
    # wider would wipe the adds queued ahead of it.
    assert len(fielding) == 3, (
        f"three views wrote their columns in {len(fielding)} $batch request(s)"
    )
    ordered = {}
    for batch in fielding:
        views = {
            match.group(1) for match in (
                re.search(r"views/getbytitle\('([^']+)'\)", op["url"])
                for op in batch["ops"]
            ) if match
        }
        assert len(views) == 1, (
            f"one ChangeSet spans {len(views)} views: {views}"
        )
        for op in batch["ops"]:
            assert op["method"] == "POST", (
                "a view-field part would MERGE rather than POST the function"
            )
        assert "/viewfields/removeallviewfields" in batch["ops"][0]["url"], (
            "the reset is not the first part, so the adds ahead of it are "
            f"cleared by it: {[op['url'] for op in batch['ops']]}"
        )
        added = [re.search(r"addviewfield\('([^']+)'\)", op["url"])
                 for op in batch["ops"][1:]]
        assert all(added), (
            f"a part after the reset is not an addviewfield: {batch['ops']}"
        )
        ordered[views.pop()] = [m.group(1) for m in added if m]
    declared = {k: v for k, v in ordered.items() if k in ("TitleFirst", "NoteFirst")}
    assert declared == {"TitleFirst": ["Title", "Note"],
                        "NoteFirst": ["Note", "Title"]}, (
        f"the parts did not leave in each view's declared order: {ordered}"
    )


# Two lists with a declared layout, so a ChangeSet that coalesces them is
# distinguishable from one request each.
_TWO_FORM_LAYOUTS = """
form_formatting:
  Escalation:
    body:
      sections:
        - { displayname: Main, fields: [Title, Note] }
  Other:
    body:
      sections:
        - { displayname: Main, fields: [Title, Note] }
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_form_phase_batches_across_lists(tmp_path: Path) -> None:
    """One ChangeSet for every list's layout, not one per list.

    The boundary the seal and index phases draw is the LIST, because same-list
    field writes race into save conflicts. A layout is one write per list, so
    there is no same-list pair to race and nothing that boundary protects;
    this pins the wider boundary rather than leaving it to be narrowed back by
    a later change that reads the other two phases as the rule.

    The content-type resolution ahead of the writes and the read-back after
    them are both asserted to be single query batches, because they are what
    the phase spent its requests on: one enumeration and one verify per list.
    """
    tables = ("Escalation", "Other")
    body = _declared_deploy_js(tmp_path, _TWO_FORM_LAYOUTS, table_names=tables).rstrip()
    assert body.endswith("})();")
    # The plain harness only knows the default fixture's markers, and the
    # second list would fail preflight for a reason unrelated to transport.
    descriptions = _declared_list_descriptions(tmp_path, table_names=tables)
    harness = _ADOPTED_HARNESS.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(descriptions.items()))});",
    )
    output = _run(
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__BATCHES__' + JSON.stringify(globalThis.__batches));\n"
        "});\n",
    )
    summary = _summary_of(output)
    assert summary.get("errors") == [], summary["errors"]
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__BATCHES__")), None,
    )
    assert line is not None, f"deploy.js sent no $batch at all:\n{output[-3000:]}"
    batches = json.loads(line.removeprefix("__BATCHES__"))

    writes = [
        b for b in batches
        if any("ClientFormCustomFormatter" in (op["body"] or "") for op in b["ops"])
    ]
    assert len(writes) == 1, (
        f"two layouts went out as {len(writes)} $batch request(s)"
    )
    assert len(writes[0]["ops"]) == 2, (
        f"expected both lists as parts, got {writes[0]['ops']}"
    )
    for op in writes[0]["ops"]:
        assert op["method"] == "MERGE", (
            "a layout part would POST rather than MERGE the content type"
        )
        assert "/contenttypes('" in op["url"], (
            "a layout part addresses the content-type collection rather than "
            "the default item content type the write it replaces named"
        )
    written = {
        match.group(1) for match in (
            re.search(r"lists/getbytitle\('([^']+)'\)", op["url"])
            for op in writes[0]["ops"]
        ) if match
    }
    assert len(written) == 2, (
        f"both parts wrote to the same list: {writes[0]['ops']}"
    )

    reads = [
        b for b in batches
        if all(op["method"] == "GET" for op in b["ops"])
        and any("/contenttypes" in op["url"] for op in b["ops"])
    ]
    assert len(reads) == 2, (
        "the content-type resolution and the read-back are one query batch "
        f"each; got {len(reads)}: {[[op['url'] for op in b['ops']] for b in reads]}"
    )
    for batch in reads:
        assert len(batch["ops"]) == 2, (
            f"a query batch skipped a list: {[op['url'] for op in batch['ops']]}"
        )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_field_default_phase_batches_a_list_s_writes(tmp_path: Path) -> None:
    """The DefaultValue MERGEs travel as ChangeSet parts, one $batch per list.

    Two declared defaults on one list, so a batch that coalesces them is
    distinguishable from one request per column. The per-column readback that
    follows is what still names a default that did not land, which a
    ChangeSet refusal cannot do for itself.
    """
    body = _declared_deploy_js(
        tmp_path, "",
        extra_lines=(
            "Status nvarchar [default: 'open']",
            "Owner nvarchar [default: 'nobody']",
        ),
    ).rstrip()
    assert body.endswith("})();")
    output = _run(
        f"{_ADOPTED_HARNESS}\n({body[:-1]}).then(() => {{\n"
        "  console.log('__BATCHES__' + JSON.stringify(globalThis.__batches));\n"
        "});\n",
    )
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__BATCHES__")), None,
    )
    assert line is not None, f"deploy.js sent no $batch at all:\n{output[-3000:]}"
    batches = json.loads(line.removeprefix("__BATCHES__"))

    writing = [
        b for b in batches
        if any('"DefaultValue"' in (op["body"] or "") for op in b["ops"])
    ]
    assert writing, f"no default write travelled as a ChangeSet part: {batches}"
    assert len(writing) == 1, (
        f"the list's defaults went out as {len(writing)} $batch requests"
    )
    values = [json.loads(op["body"])["DefaultValue"] for op in writing[0]["ops"]]
    assert values == ["open", "nobody"], (
        f"expected both declared defaults as parts, got {writing[0]['ops']}"
    )
    for op in writing[0]["ops"]:
        assert op["method"] == "MERGE", (
            "a default part would POST rather than MERGE the field"
        )
        assert "/fields(guid'" in op["url"], (
            "a default part addresses the field by name, which a rebind can "
            "redirect; the write it replaces went by Id"
        )


def test_generated_deploy_js_carries_no_control_characters() -> None:
    """deploy.js is pasted into a browser console by hand.

    A stray control character survives templating, the golden file and
    every text-mode diff (git reports the file as binary and shows
    nothing). Writing this fix, a literal NUL reached a template's
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
    *, table_name: str = "Escalation",
    table_names: tuple[str, ...] | None = None,
    self_reference: bool = False,
    extra_lines: tuple[str, ...] = (),
) -> tuple[Any, Any]:
    """The (schema, bundle) behind `_declared_deploy_js`.

    Split out so a test can ask what the generator DECLARES for these lists
    without re-spelling the fixture. A second copy of the schema here would
    drift from the one the script is built from, and the tests that compare
    declared-against-live would then be comparing two different fixtures.

    `prefix` is the only knob that puts an arbitrary character into a LIST
    TITLE. The rest of the title is the DBML table name, which the parser
    constrains. It is what lets a test deploy to a list whose title needs
    OData escaping.

    `self_reference` gives every table a lookup back to its own list. That is
    what puts a column in `phase2_lookups`: a lookup whose target does not
    exist yet when the field wave runs is deferred, and without one the
    deferred-lookup phase has nothing to do and cannot be reached from here.

    `extra_lines` are further lines inside every table block, one per entry.
    Columns are what `table()` normally takes, but a DBML `indexes { ... }`
    block is also just lines, and declaring one is the only way to reach the
    index phase with more than the lookup display column.
    """
    names = table_names or (table_name,)
    return pack(
        tmp_path,
        dbml="".join(
            table(
                name, ID_PK, "Title nvarchar", "Note nvarchar",
                *((f"Parent int [ref: > {name}.Id]",) if self_reference else ()),
                *extra_lines,
            )
            for name in names
        ),
        mapping=blocks(entities(*names), section),
        prefix=prefix,
    )


def _declared_deploy_js(
    tmp_path: Path, section: str, prefix: str = DEFAULT_PREFIX,
    *, table_name: str = "Escalation",
    table_names: tuple[str, ...] | None = None,
    self_reference: bool = False,
    extra_lines: tuple[str, ...] = (),
) -> str:
    """deploy.js for an all-text schema that actually declares a formula.

    The shipped fixture declares none, so enforceDeclaredFormulas returns
    before doing anything and cannot be exercised through it. All-Text
    columns keep the run clear of the derived-property probes the mock does
    not answer.

    `section` is whatever extra mapping the test needs. It is dedented, so a
    caller may pass a triple-quoted block indented to match its surrounding
    code. `blocks()` rather than `with_tail()` because every caller opens a
    TOP-LEVEL section here. Nothing nests under the entity, so no
    indentation matters and the two agree.
    """
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = _declared_pack(
        tmp_path, section, prefix,
        table_name=table_name, table_names=table_names,
        self_reference=self_reference, extra_lines=extra_lines,
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


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_overwriting_a_declared_formula_logs_the_prior_value(tmp_path: Path) -> None:
    """`before` was read, compared and discarded; on success nothing was
    logged, so a deploy that removed or rewrote an existing formula left no
    record of what had been there. Under `reconcile: exact` an undeclared
    column's formula is cleared outright, exactly the case where the prior
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
    `...Type="Sum"/>` it was sent, verified against a live tenant on
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
    # AggregationsStatus is a plain enum ('On'/'Off') and IS compared raw,
    # asserted so the regex above cannot be "fixed" by wrapping it too.
    assert "AggregationsStatus !== 'On'" in script


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_first_deploy_probes_no_absent_group_or_field_by_name() -> None:
    """A clean run must leave a clean console.

    The browser logs a failed request itself, before the script sees the
    response, and nothing in JavaScript can suppress that, so a handled
    404 still paints red and an operator reads it as a failure. The only
    fix is not to make the request: enumerate once, answer absence
    locally. Lists and views already did; site groups and the field probe
    did not, and a live first deploy showed four red lines because of it.

    The harness answers every enumeration as EMPTY, which is the state of
    a brand-new site, so any by-name probe here is one an operator would
    have seen painted red.

    Covers the two surfaces this harness reaches. The third (a list's
    role assignments by principal id) is asserted structurally instead,
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
# the membership is PERMANENT, unlike the operator's, which the run
# removes on the way out. Two resolutions must never be enrolled: a
# security GROUP (everyone in it gets Read) and one of SharePoint's
# everyone-claims (every user in the tenant gets Read). Neither is visible
# afterwards, because the deploy reads back byte-identical either way.
#
# So every test below RUNS the emitted script and asserts on what the run
# DOES (did it abort, and above all was a membership POST ever issued).
# `assert "PrincipalType !== 1" in js` would pass with the guard sitting in
# a comment; "no POST to sitegroups(N)/users happened" cannot.

_READER_ADDRESS = "svc-reporting@example.org"

# A well-formed resolution of _READER_ADDRESS. Every refusal test below
# starts from this and varies exactly ONE attribute, so the guard under
# test is the only one that can fire. Otherwise deleting it would leave
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

    return _without_assessment(generate_deploy_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping-with-reader.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        enterprise_reader=enterprise_reader,
    ))


def _reader_harness(
    ensure_user: dict[str, Any],
    *,
    members: list[dict[str, Any]] | None = None,
    member_pages: list[list[dict[str, Any]]] | None = None,
    drop_readback: bool = False,
    stray_on_write: dict[str, Any] | None = None,
) -> str:
    """`_ADOPTED_HARNESS` plus the two surfaces the reader phase touches.

    `ensureuser` answers `ensure_user` verbatim. That is the whole point of
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
    reads the first and stops, and the second is a gate that a large
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
          // Task 6 (security-phase-atomicity): removeReaderEnrollments's
          // drain POSTs here. Checked BEFORE the broader
          // sitegroups(N)/users test below, which this URL also matches --
          // and whose POST branch assumes an add, parsing `opts.body` as
          // JSON. A remove call carries no body, so falling through to that
          // branch throws `JSON.parse(undefined)` instead of modelling the
          // removal.
          const removed = /sitegroups\(\d+\)\/users\/removebyid\((\d+)\)/.exec(u);
          if (removed && method === 'POST') {
            const removedId = Number(removed[1]);
            for (const page of READER_MEMBER_PAGES) {
              const idx = page.findIndex((m) => Number(m.Id) === removedId);
              if (idx !== -1) page.splice(idx, 1);
            }
            return respond({ d: null });
          }
          // The flagged group's own membership, keyed off the BY-ID form of
          // the path so the 1.3 empty-group gate (which asks by name)
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
    a refusal test would otherwise pass against a run that aborted in 1.3
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
    SecurityGroup 4, SharePointGroup 8, and it carries [Flags], so the
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
    the strict type check refuses by itself, so the needle is belt and
    braces behind that check, not the thing holding the door. This test
    hands it PrincipalType 1 anyway, because ONE TENANT IS ONE DATA POINT
    and the needle exists for the tenant that types it differently. That is
    also the only payload under which removing the needle can be watched
    failing.

    The payload keeps the matching Email deliberately, so neither the type
    check nor the identity check can be what refuses it. The claims check
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

    A real user, correctly typed, with a real login. Only the address
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
    there. The account here is the right one (its claims login ends in the
    requested UPN), so it must be enrolled, not refused.
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

    SharePoint answering 200 is not evidence the membership exists. The
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
    this bundle provisions, permanently, since nothing here removes anyone.
    The only trace was one INFO line in a run that reported success.

    Three things are asserted, and the ORDER matters. The damage is the
    grant, so "nothing was POSTed" comes first: deleting the gate must fail
    on a second reader having been enrolled, not on a summary key. Then the
    abort. Then, still, that nobody was removed. That half of the old
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
    big, and it would look like it worked, because the small groups every
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

    Ordering guard: the idempotence check ("already a member, skip") must
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

    Nothing here removes the STRAY -- the same reason the before-read gives:
    membership is an operator-owned concern and this is a gate, not a
    reconciler for an account this run did not add. But (task 6,
    security-phase atomicity, #213 form 1) this run's OWN account no longer
    stays enrolled after this abort: deploy.js.j2's finally drains it,
    because the run never reached the end. This used to be the case that
    left BOTH accounts in two concurrent deploys permanently enrolled.
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
    removals = _removals(calls)
    assert any(f"removebyid({_RESOLVED_USER['Id']})" in c["url"] for c in removals), (
        f"the reader this run just enrolled was left in place after the abort: {removals}"
    )
    assert not any(f"removebyid({_OTHER_MEMBER['Id']})" in c["url"] for c in removals), (
        f"the stray, which this run never added, was removed: {removals}"
    )


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


# Task 6 (security-phase atomicity, #213 form 1): the reader enrolment must
# clean up after a run that adds the account and then fails LATER, and must
# leave it alone on a run that reaches the end. Two concurrent deploys
# naming different reader addresses used to both add their account, both
# abort, and both leave their account enrolled forever.


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_later_phase_failure_drains_the_reader_this_run_added() -> None:
    """The general form of #213's fix: the reader phase itself succeeds
    cleanly, and a LATER phase aborts. The account this run just added must
    not survive that abort -- only a run that reaches the end may leave it.

    Plain `_run_reader_deploy` already aborts in Phase 2.1 on this fixture's
    Lookup column, for reasons that have nothing to do with the reader (the
    same fact `test_an_already_enrolled_reader_is_not_added_twice` notes
    above) -- exactly the shape this test needs: a clean 1.5 followed by a
    dirty later phase, with no bespoke harness required to get there.
    """
    summary, calls, output = _run_reader_deploy(_RESOLVED_USER)
    assert not _reader_errors(summary), (
        f"the reader phase itself failed, so this does not test a LATER "
        f"phase's abort: {summary}"
    )
    assert summary.get("aborted") not in (None, "reader-enrolment-errors"), (
        f"the run did not abort in a later phase: {summary}\n{output[-2000:]}"
    )
    assert _membership_writes(calls), "the reader was never enrolled in the first place"
    removals = _removals(calls)
    assert any(f"removebyid({_RESOLVED_USER['Id']})" in c["url"] for c in removals), (
        f"a later phase's abort must remove the reader this run just enrolled: {removals}"
    )


# `_declared_pack`'s minimal all-text schema is what `_ADOPTED_HARNESS` can
# drive all the way to a clean DATA-phase finish
# (`test_a_declared_run_completes_every_phase_cleanly`); the shipped
# `sharepoint-mapping(-with-reader).yaml` fixture's Lookup and formula
# columns are not modelled that completely (see the test above), so "a
# clean run leaves the reader enrolled" needs this schema, not that
# fixture, to reach the end at all.
_READER_DECLARED_SECTION = """
    groups:
      - name: "Enterprise Reader"
        description: "Read-only enrolment target for --enterprise-reader."
        owner_group: "Site Owners"
        allow_members_edit_membership: false
        allow_request_to_join_leave: false
        auto_accept_request_to_join_leave: false
        only_allow_members_view_membership: false
        enroll_enterprise_reader: true

    list_permissions:
      default:
        site_role: default
        break_inheritance: true
        reconcile: exact
        assignments:
          - principal: { kind: group, name: "Enterprise Reader" }
            level: "Read"
"""


def _declared_reader_deploy_js(tmp_path: Path) -> str:
    """`_declared_deploy_js`, plus an enterprise-reader group with a Read
    ACL assignment, built with `--enterprise-reader`."""
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = _declared_pack(tmp_path, _READER_DECLARED_SECTION)
    return _without_assessment(generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
        enterprise_reader=_READER_ADDRESS,
    ))


# The ACL phase resolves a declared assignment's level by name through
# `web/roledefinitions/getbyname`, the same surface `ROLE_DEF_STATE` already
# models for this tool's own custom levels. No existing test names a
# BUILT-IN level ('Read') in an ACL assignment, so `_ADOPTED_HARNESS` never
# needed to seed one; this is the first run to carry an enterprise-reader
# group's Read grant all the way through Phase 4.2.
_READER_ACL_HARNESS = _ADOPTED_HARNESS.replace(
    "'Schema Manager': {",
    "'Read': { Id: 100, Description: '', BasePermissions: { High: '0', Low: '138612833' } },\n"
    "      'Schema Manager': {",
)


def _reader_harness_for_declared_run(ensure_user: dict[str, Any]) -> str:
    """`_reader_harness`, rebuilt on `_READER_ACL_HARNESS` instead of the
    plain `_ADOPTED_HARNESS` it always starts from."""
    overlay = _reader_harness(ensure_user)[len(_ADOPTED_HARNESS):]
    return _READER_ACL_HARNESS + overlay


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_clean_end_to_end_run_leaves_the_reader_enrolled(tmp_path: Path) -> None:
    """The other half of #213's fix: a run that reaches the end must NOT
    remove the reader it just added. That membership is meant to outlive
    the run, and only a run that never gets here should undo it.
    """
    js = _declared_reader_deploy_js(tmp_path)
    script = _reader_harness_for_declared_run(_RESOLVED_USER) + "\n" + js.replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    result_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None,
    )
    assert result_line is not None, f"deploy.js did not return a summary:\n{output[-3000:]}"
    summary = json.loads(result_line.removeprefix("__RESULT__"))
    calls_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None,
    )
    assert calls_line is not None, f"harness produced no call log:\n{output[-3000:]}"
    calls = json.loads(calls_line.removeprefix("__CALLS__"))

    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]
    assert _membership_writes(calls), "the reader was never enrolled"
    assert not _removals(calls), (
        f"a successful run removed the reader it just enrolled: {_removals(calls)}"
    )


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
        description="Read-only accounts. "
            "Provisioned by dbml-sharepoint from simple-test for group Enterprise Reader.",
        member_pages=[[{"Id": 501}]],
    )
    assert not _security_errors(summary), summary
    assert _group_settings_writes(calls, "Enterprise Reader"), (
        "a marked group's settings were never reconciled"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_group_marked_by_another_family_with_members_is_refused() -> None:
    """The gate must compare the exact marker this declaration expects, not
    the shared prefix every family's marker starts with. A group another
    family stamped and populated satisfied the old prefix-only test, and the
    ACL phase then granted those members whatever THIS family declares."""
    summary, calls, _ = _group_gate_deploy(
        _reader_deploy_js(enterprise_reader=None), "Enterprise Reader",
        description="Read-only accounts. "
            "Provisioned by dbml-sharepoint from other-family for group Enterprise Reader.",
        member_pages=[[{"Id": 501}]],
    )
    assert not _group_settings_writes(calls, "Enterprise Reader"), (
        "a group marked by another family was reconciled before the refusal"
    )
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "Enterprise Reader" in message, message
    assert "carries no" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


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
    stale_description = (
        "Stale note. "
        "Provisioned by dbml-sharepoint from simple-test for group List Maintainer."
    )
    harness = _ADOPTED_HARNESS.replace(
        "const GROUP_DESCRIPTIONS = {};",
        f"const GROUP_DESCRIPTIONS = {json.dumps({group_name: stale_description})};",
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
    assert "group" in errors[0], errors[0]
    message = str(errors[0]["error"])
    assert group_name in message, message
    assert "Description" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


# Every survey in the security phase now runs before every create, so an
# adopt decision's owner resolve, which reads a SECOND group (the declared
# owner_group), can hit a custom group this SAME pass has not created yet.
# `_owner_pending_groups_deploy_js` splits the fixture's one declared group
# into two so the adopted one names the about-to-be-created one as its owner.


def _owner_pending_groups_deploy_js() -> str:
    """`_deploy_js()` with the fixture's one declared group ('List
    Maintainer') split into two: it now declares owner_group 'Group B', a
    second custom group this same declaration also creates. Mutates the
    generated JSON directly, the same way `test_auto_accept_is_compared_...`
    does, rather than adding a second group to the shared mapping fixture.
    """
    js = _deploy_js()
    match = re.search(r'"groups": (\[.*?\n  \])', js, re.DOTALL)
    assert match, "groups array not found in generated deploy.js"
    groups = json.loads(match.group(1))
    assert len(groups) == 1, groups
    list_maintainer = dict(groups[0])
    assert list_maintainer["owner_group"] == "Site Owners", list_maintainer
    list_maintainer["owner_group"] = "Group B"
    group_b = dict(list_maintainer)
    group_b["name"] = "Group B"
    group_b["description"] = "Group B."
    group_b["owner_group"] = "Site Owners"
    group_b["require_empty_at_deploy"] = False
    new_groups = json.dumps([group_b, list_maintainer], indent=2).replace("\n", "\n  ")
    return js[: match.start(1)] + new_groups + js[match.end(1):]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_adopted_group_owned_by_a_group_pending_creation_still_deploys() -> None:
    """'List Maintainer' already exists and declares owner_group 'Group B',
    which is declared but absent, so this same pass decides to create it.
    Resolving 'List Maintainer's owner during the survey, before Group B
    exists, would 404 and abort the whole phase; the fix defers that resolve
    to applyGroupDecision, which runs after Group B's own create has
    applied. Verified by mutation: forcing the resolve back into the survey
    unconditionally reproduces the abort this test would otherwise miss.
    """
    js = _owner_pending_groups_deploy_js()
    harness = _ADOPTED_HARNESS.replace(
        "const GROUP_DESCRIPTIONS = {};",
        f"const GROUP_DESCRIPTIONS = {json.dumps({
            'List Maintainer': 'Test group. Provisioned by dbml-sharepoint from simple-test.',
        })};",
    ).replace(
        "const GROUP_MEMBER_PAGES = {};",
        f"const GROUP_MEMBER_PAGES = {json.dumps({'List Maintainer': [[]]})};",
    ).replace(
        "const KNOWN_GROUP_NAMES = [];",
        f"const KNOWN_GROUP_NAMES = {json.dumps(['List Maintainer'])};",
    ).replace(
        "const GROUP_IDS = {};",
        f"const GROUP_IDS = {json.dumps({'List Maintainer': 101, 'Group B': 102})};",
    ).replace(
        "const GROUP_CURRENT_OWNER = { 9: { Id: 3, Title: 'Site Owners', PrincipalType: 8 } };",
        "const GROUP_CURRENT_OWNER = { 9: { Id: 3, Title: 'Site Owners', PrincipalType: 8 }, "
        "101: { Id: 102, Title: 'Group B', PrincipalType: 8 } };",
    )
    summary, calls, output = _run_group_verify_deploy(js, harness)
    assert not _security_errors(summary), summary
    assert summary.get("aborted") != "phase-0-security-errors", summary
    create_indices = [
        i for i, c in enumerate(calls)
        if c["method"] == "POST" and c["url"].endswith("/sitegroups") and c["body"]
        and json.loads(c["body"]).get("Title") == "Group B"
    ]
    assert create_indices, f"Group B was never created:\n{output[-3000:]}"
    owner_resolve_indices = [
        i for i, c in enumerate(calls)
        if c["method"] == "GET"
        and "sitegroups/getbyname('Group%20B')" in c["url"]
    ]
    assert owner_resolve_indices, f"'List Maintainer's owner was never resolved:\n{output[-3000:]}"
    assert min(owner_resolve_indices) > create_indices[0], (
        "the owner resolve for 'List Maintainer' ran before Group B was created: "
        f"resolve at {owner_resolve_indices}, create at {create_indices[0]}"
    )


# #224: `_security_principals.js.j2` adopted any role definition whose name
# matched a declared one and MERGEd the declared bitmap onto it. A role
# definition is SITE-SCOPED, so a hand-made level sharing a declared name and
# assigned on lists this tool never reads had its bitmap silently
# overwritten. `_role_def_gate_deploy` lets these tests control the
# fixture's one declared level, 'Schema Manager', against `_ADOPTED_HARNESS`.


def _role_def_gate_deploy(
    deploy_js: str,
    *,
    absent: bool = False,
    description_override: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run `deploy_js` against `_ADOPTED_HARNESS` with the fixture's one
    declared permission level, 'Schema Manager', either absent (so the
    CREATE path runs) or present with its Description overridden (so the
    #224 adoption gate can be exercised against an unmarked level, or one
    another family stamped).
    """
    harness = _ADOPTED_HARNESS.replace(
        "const ROLE_DEF_ABSENT = false;",
        f"const ROLE_DEF_ABSENT = {json.dumps(absent)};",
    ).replace(
        "const ROLE_DEF_DESCRIPTION_OVERRIDE = null;",
        f"const ROLE_DEF_DESCRIPTION_OVERRIDE = {json.dumps(description_override)};",
    )
    return _run_group_verify_deploy(deploy_js, harness)


def _role_def_merge_writes(
    calls: list[dict[str, Any]], level_name: str,
) -> list[dict[str, Any]]:
    """Every POST that MERGEs settings onto the named role definition itself."""
    encoded = quote(level_name, safe="")
    return [
        c for c in calls
        if c["method"] == "POST" and c["body"]
        and f"roledefinitions/getbyname('{encoded}')" in c["url"]
    ]


def _role_def_create_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every POST that creates a new role definition."""
    return [
        c for c in calls
        if c["method"] == "POST" and c["body"]
        and c["url"].endswith("/web/roledefinitions")
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unmarked_permission_level_is_refused() -> None:
    """MARKER ONLY, unlike the group gate: no usage count can clear this
    refusal. Default `_ADOPTED_HARNESS` state reports zero web-scope role
    assignments for it, and it is still refused. `_acls.js.j2` assigns a
    permission level at LIST scope, which a web-scope count cannot see, so
    treating an unmeasured surface as empty would adopt exactly the level
    #224 exists to stop adopting."""
    summary, calls, _ = _role_def_gate_deploy(
        _deploy_js(), description_override="Our own level.",
    )
    # The overwritten bitmap is the damage; the refusal is only how the
    # script avoids it. Asserted first so removing the gate fails on "the
    # level was reconciled" rather than on a summary key.
    assert not _role_def_merge_writes(calls, "Schema Manager"), (
        "an unmarked permission level was reconciled before the refusal: "
        "its Description and BasePermissions were rewritten"
    )
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "Schema Manager" in message, message
    assert "carries no" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_permission_level_marked_by_another_family_is_refused() -> None:
    """The gate compares the exact marker THIS declaration expects, not the
    shared 'Provisioned by dbml-sharepoint' prefix every family's marker
    starts with, so a level another family stamped cannot satisfy it."""
    summary, calls, _ = _role_def_gate_deploy(
        _deploy_js(),
        description_override="Provisioned by dbml-sharepoint from other-family.",
    )
    assert not _role_def_merge_writes(calls, "Schema Manager"), (
        "a permission level marked by another family was reconciled before the refusal"
    )
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "Schema Manager" in message, message
    assert "carries no" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_marked_permission_level_is_adopted_silently() -> None:
    """The default `_ADOPTED_HARNESS` state already carries this
    declaration's marker, matching a prior run of the same family: the
    level is reconciled without a security error."""
    summary, calls, _ = _role_def_gate_deploy(_deploy_js())
    assert not _security_errors(summary), summary
    assert _role_def_merge_writes(calls, "Schema Manager"), (
        "a marked permission level's settings were never reconciled"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_permission_level_created_fresh_is_stamped() -> None:
    """A level this deploy creates must carry the marker that lets a later
    redeploy recognise it as this tool's own."""
    summary, calls, _ = _role_def_gate_deploy(_deploy_js(), absent=True)
    assert not _security_errors(summary), summary
    writes = _role_def_create_writes(calls)
    assert writes, "a fresh permission level was never created"
    marker = "Provisioned by dbml-sharepoint from simple-test for level Schema Manager."
    assert marker in writes[0]["body"]


# Task 5 (#224): `mergeResp.ok` and the create POST's `ok` only say the
# tenant accepted the request, not that it stored what was sent.
# `verifyLevelSettings` reads the level back after both the create and the
# MERGE and compares Description and both bitmap halves.
# `ROLE_DEF_DROP_FIELD_ON_WRITE` models a write the tenant 200s and
# discards, the same way `GROUP_DROP_FIELD_ON_WRITE` does for a site group.


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_permission_level_description_the_tenant_did_not_store_fails_closed() -> None:
    """AGENTS.md: anything that writes must read back and verify.

    The stale description still carries this family's marker, so the run
    takes the adopt-and-reconcile branch rather than the refusal gate; only
    the read-back after the MERGE can catch the drop.
    """
    stale_description = (
        "Stale note. "
        "Provisioned by dbml-sharepoint from simple-test for level Schema Manager."
    )
    harness = _ADOPTED_HARNESS.replace(
        "const ROLE_DEF_DESCRIPTION_OVERRIDE = null;",
        f"const ROLE_DEF_DESCRIPTION_OVERRIDE = {json.dumps(stale_description)};",
    ).replace(
        "const ROLE_DEF_DROP_FIELD_ON_WRITE = null;",
        "const ROLE_DEF_DROP_FIELD_ON_WRITE = 'Description';",
    )
    summary, calls, _ = _run_group_verify_deploy(_deploy_js(), harness)
    assert _role_def_merge_writes(calls, "Schema Manager"), (
        "the reconcile MERGE never happened"
    )
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "Schema Manager" in message, message
    assert "Description" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_permission_level_base_permissions_the_tenant_did_not_store_fails_closed() -> None:
    """A dropped bitmap half is the exact failure #224 exists to catch: the
    MERGE reports success while the level keeps its old permissions. The
    declared Low is overridden so the drop is observable, since the mock's
    stored default otherwise already equals the undisturbed declared value.
    """
    js = _deploy_js().replace('"low": "2049"', '"low": "4098"', 1)
    assert '"low": "4098"' in js
    harness = _ADOPTED_HARNESS.replace(
        "const ROLE_DEF_DROP_FIELD_ON_WRITE = null;",
        "const ROLE_DEF_DROP_FIELD_ON_WRITE = 'Low';",
    )
    summary, calls, _ = _run_group_verify_deploy(js, harness)
    assert _role_def_merge_writes(calls, "Schema Manager"), (
        "the reconcile MERGE never happened"
    )
    errors = _security_errors(summary)
    assert errors, summary
    assert "permissionLevel" in errors[0], errors[0]
    message = str(errors[0]["error"])
    assert "Schema Manager" in message, message
    assert "BasePermissions" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_freshly_created_level_base_permissions_the_tenant_did_not_store_fails_closed() -> None:
    """The two drop-field tests above only drive the MERGE (adopt) branch.
    `verifyLevelSettings` is called separately after CREATE, and deleting
    that call left every other test in this file green: the create-body
    assertion in `test_a_permission_level_created_fresh_is_stamped` does not
    move when the post-create read-back is skipped.

    `roleDefState`'s untouched default for a never-seen name already has
    BasePermissions.Low '0', which differs from the fixture's declared
    '2049' on its own, so no override of the declared value is needed here
    to make the drop observable, unlike the MERGE-path test above it.
    """
    harness = _ADOPTED_HARNESS.replace(
        "const ROLE_DEF_ABSENT = false;",
        "const ROLE_DEF_ABSENT = true;",
    ).replace(
        "const ROLE_DEF_DROP_FIELD_ON_WRITE = null;",
        "const ROLE_DEF_DROP_FIELD_ON_WRITE = 'Low';",
    )
    summary, calls, _ = _run_group_verify_deploy(_deploy_js(), harness)
    assert _role_def_create_writes(calls), "the create POST never happened"
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "Schema Manager" in message, message
    assert "BasePermissions" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


# Task 4 (security-phase-atomicity): the abort check used to run only after
# BOTH loops (levels, then groups) had finished, so a refusal on the first
# object did not stop a write on a LATER one. `_security_writes` names every
# POST the phase can issue, regardless of which object it belongs to, so the
# tests below anchor on the absence of writes in the call log rather than on
# a summary key, matching AGENTS.md's evidence rule: the gate must never be
# softenable without a test failing on the write itself.


def _security_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every POST `_security_principals.js.j2` can issue: a permission-level
    create or MERGE, a site-group create or MERGE, or the CSOM ProcessQuery
    owner correction. The first two only ever fire from the apply loop; the
    assessment's read-only ProcessQuery probe also matches, which is why the
    tests below stub the assessment out rather than acknowledging it."""
    return [
        c for c in calls
        if c["method"] == "POST"
        and (
            "sitegroups" in c["url"]
            or "roledefinitions" in c["url"]
            or "ProcessQuery" in c["url"]
        )
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_apply_pass_takes_its_own_fresh_digest() -> None:
    """digest0 is captured near the top of phase 1.3, before the whole
    survey (every level probe, the group enumeration, every adopt-path
    owner read and membership count) now runs ahead of it, where before this
    task the first write followed the fetch almost immediately. A create
    write that reused digest0 directly, without asking getDigest() again,
    would carry whatever was fetched before the survey started rather than
    a digest taken right before the apply pass's first write.

    getDigest() caches for at least 60s (`_digest_cached.js.j2`), which a
    synchronous test cannot outlast, so the cache guard is disabled here to
    make every call a real fetch: the count of `contextinfo` POSTs before
    the first write is then a reliable proxy for whether the apply pass took
    its own fresh digest, rather than reusing the one taken before survey.
    """
    js = _deploy_js().replace(
        "if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;",
        "if (false) return cachedDigest; // test: force every call to re-fetch",
    )
    assert "if (false) return cachedDigest" in js, "getDigest cache guard not found"
    summary, calls, output = _role_def_gate_deploy(js, absent=True)
    assert not _security_errors(summary), summary
    creates = _role_def_create_writes(calls)
    assert creates, f"a fresh permission level was never created:\n{output[-3000:]}"
    first_write_index = calls.index(creates[0])
    digests_before_first_write = [
        c for c in calls[:first_write_index] if "contextinfo" in c["url"]
    ]
    assert len(digests_before_first_write) >= 2, (
        "the apply pass reused the digest fetched before the survey instead of "
        f"taking its own fresh one: {digests_before_first_write}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_level_blocks_the_group_create_that_used_to_follow_it() -> None:
    """Before this task, the level loop ran survey-then-apply per object and
    only checked `summary.errors` after BOTH loops. A refused level did not
    stop the group loop a few lines later from creating 'List Maintainer'.
    """
    summary, calls, output = _role_def_gate_deploy(
        _deploy_js(), description_override="Our own level.",
    )
    assert not _security_writes(calls), (
        f"a refused permission level did not stop a write on another "
        f"object\n{output[-2000:]}"
    )
    errors = _security_errors(summary)
    assert errors, summary
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_group_blocks_the_permission_level_reconcile_too() -> None:
    """Symmetric case: with no override the fixture's one declared level
    ('Schema Manager') is adopted and reconciled cleanly on its own
    (`test_a_marked_permission_level_is_adopted_silently`). Refusing the
    group here must stop that reconcile from happening, whichever loop ran
    first.
    """
    summary, calls, output = _group_gate_deploy(
        _deploy_js(), "List Maintainer",
        description="Our own group", member_pages=[[{"Id": 501}]],
    )
    assert not _security_writes(calls), (
        f"a refused site group did not stop the permission level reconcile "
        f"that would otherwise have run\n{output[-2000:]}"
    )
    errors = _security_errors(summary)
    assert errors, summary
    assert summary.get("aborted") == "phase-0-security-errors", summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_two_refusals_both_appear_in_the_transcript() -> None:
    """Surveying must not short-circuit on the first refusal: an operator
    who fixes one blocker and redeploys must not just meet the next one
    they were never told about."""
    harness = _ADOPTED_HARNESS.replace(
        "const ROLE_DEF_DESCRIPTION_OVERRIDE = null;",
        f"const ROLE_DEF_DESCRIPTION_OVERRIDE = {json.dumps('Our own level.')};",
    ).replace(
        "const GROUP_DESCRIPTIONS = {};",
        f"const GROUP_DESCRIPTIONS = {json.dumps({'List Maintainer': 'Our own group'})};",
    ).replace(
        "const GROUP_MEMBER_PAGES = {};",
        f"const GROUP_MEMBER_PAGES = {json.dumps({'List Maintainer': [[{'Id': 501}]]})};",
    ).replace(
        "const KNOWN_GROUP_NAMES = [];",
        f"const KNOWN_GROUP_NAMES = {json.dumps(['List Maintainer'])};",
    )
    summary, calls, output = _run_group_verify_deploy(_deploy_js(), harness)
    assert not _security_writes(calls), output[-2000:]
    errors = _security_errors(summary)
    messages = [str(e["error"]) for e in errors]
    assert any("Schema Manager" in m for m in messages), errors
    assert any("List Maintainer" in m for m in messages), errors
    assert len(errors) == 2, (
        f"only one of two refusals reached the transcript: {errors}"
    )
    assert summary.get("aborted") == "phase-0-security-errors", summary


# A genuine survey FAILURE (not a refusal): the permission-level existence
# probe answers a real HTTP error rather than a filtered result set.
# `surveyLevel` throws in that case, and the per-object catch around it must
# still turn that into the same structured summary a refusal produces,
# rather than letting it escape the phase, the `try` in deploy.js.j2, and
# the async IIFE as an unhandled rejection -- which the harness would
# surface as a missing `__RESULT__` line, since nothing would ever call the
# `.then()` that prints it.
_SURVEY_FAILURE_HARNESS = _ADOPTED_HARNESS + textwrap.dedent(r"""
    const _passThrough = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      if ((opts.method || 'GET') === 'GET' && u.includes('roledefinitions')
          && u.includes('$filter=Name')) {
        calls.push({ url: u, method: 'GET', body: null });
        const payload = { error: { message: { value: 'probe exploded' } } };
        return {
          ok: false, status: 500,
          headers: { get: () => null },
          json: async () => payload,
          text: async () => JSON.stringify(payload),
        };
      }
      return _passThrough(url, opts);
    };
""")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_survey_failure_still_produces_a_structured_abort() -> None:
    """`_run_group_verify_deploy` already asserts a `__RESULT__` line was
    printed; if the probe failure above escaped as an unhandled rejection,
    that assertion is what would catch it, not the abort-key check below.
    """
    summary, calls, output = _run_group_verify_deploy(
        _deploy_js(), _SURVEY_FAILURE_HARNESS,
    )
    assert not _security_writes(calls), output[-2000:]
    errors = _security_errors(summary)
    assert errors, summary
    message = str(errors[0]["error"])
    assert "Schema Manager" in message, message
    assert "500" in message, message
    assert summary.get("aborted") == "phase-0-security-errors", summary


def _group_create_writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every POST that creates a new site group."""
    return [
        c for c in calls
        if c["method"] == "POST" and c["body"]
        and c["url"].endswith("/web/sitegroups")
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_clean_run_still_writes_both_the_level_and_the_group() -> None:
    """No refusals, no survey failures: the restructure must not turn a
    previously clean run into one that skips writes it used to make.

    Plain `_ADOPTED_HARNESS` carries no entry in `KNOWN_GROUP_NAMES`, so
    'List Maintainer' takes the create path here rather than the adopt
    path other tests in this file exercise via `_group_gate_deploy`.
    """
    summary, calls, _ = _run_group_verify_deploy(_deploy_js(), _ADOPTED_HARNESS)
    assert not _security_errors(summary), summary
    assert _role_def_merge_writes(calls, "Schema Manager"), (
        "a clean run stopped reconciling the permission level"
    )
    assert _group_create_writes(calls), (
        "a clean run stopped creating the site group"
    )


# Task 5 (#32): the decision table. Every object BOTH survey loops decided
# to create or adopt must be named before either loop's apply step writes
# anything. `_ADOPTED_HARNESS` carries no entry in `KNOWN_GROUP_NAMES`, so
# the group takes the create path and the level (matching this family's
# marker) takes the adopt path in the same run, exercising both verbs.


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_decision_table_names_every_declared_object_before_any_write() -> None:
    """A refusal already logs its own ERROR line in the survey loop that
    found it; this table is what a CLEAN run additionally gets, printed
    before a single write.
    """
    summary, _calls, output = _run_group_verify_deploy(_deploy_js(), _ADOPTED_HARNESS)
    assert not _security_errors(summary), summary
    lines = output.splitlines()

    table_index = next(
        (i for i, ln in enumerate(lines)
         if "decisions" in ln.lower() and pn("security") in ln), None,
    )
    assert table_index is not None, f"no decision table was printed:\n{output[-2000:]}"

    table_block = "\n".join(lines[table_index:table_index + 5])
    assert "Schema Manager" in table_block, table_block
    assert "List Maintainer" in table_block, table_block

    first_write_log = next(
        i for i, ln in enumerate(lines)
        if "Creating" in ln or "reconciled" in ln
    )
    assert table_index < first_write_log, (
        f"the decision table printed after a write had already started:\n{output[-2000:]}"
    )


def _duplicate_group_case_variant(js: str) -> str:
    """Splice a second declared group into `SCHEMA.groups`, differing from
    the first only in case, so `surveyGroup` meets a name `decidedCreates`
    already holds. `sharepoint-mapping.yaml` declares one group ('List
    Maintainer'); the build itself refuses two case-variant declarations in
    one mapping (`DUPLICATE_GROUP_NAME`), so this bypasses that by editing
    the already-generated JSON rather than the mapping, modelling a bundle
    built before that rule existed.
    """
    match = re.search(r'  "groups": (\[\n.*?\n  \]),\n  "indexed_columns"', js, re.DOTALL)
    assert match, "SCHEMA.groups block not found in generated deploy.js"
    groups = json.loads(match.group(1))
    variant = dict(groups[0])
    variant["name"] = "LIST MAINTAINER"
    return js.replace(match.group(1), json.dumps([*groups, variant], indent=2), 1)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_case_variant_group_declaration_is_refused_not_double_created() -> None:
    """`decidedCreates` used to feed only `isKnown`, which only decides
    whether to skip the by-name probe. For a name already decided 'create',
    the group does not exist yet, so the real probe still answers 404 and
    the survey returned a SECOND 'create' decision: applied, that queues two
    POSTs colliding on the one name SharePoint resolves them both to.

    The fix refuses the second declaration in the survey itself: one create
    decision reaches the table, the second is a refusal, and because a
    refusal blocks the whole phase's apply step, neither group is actually
    written. Mutation-tested: deleting the `hasName(decidedCreates, ...)`
    check in `surveyGroup` makes this test fail, printing two 'create site
    group' lines and no case-collision error.
    """
    js = _duplicate_group_case_variant(_deploy_js())
    summary, calls, output = _run_group_verify_deploy(js, _ADOPTED_HARNESS)

    create_lines = [ln for ln in output.splitlines() if "create site group" in ln]
    assert len(create_lines) == 1, (
        f"expected exactly one create decision for the two case-variant "
        f"declarations, got: {create_lines}"
    )
    errors = _security_errors(summary)
    assert len(errors) == 1, summary
    assert "group" in errors[0], errors[0]
    message = str(errors[0]["error"])
    assert "LIST MAINTAINER" in message, message
    assert "case" in message.lower(), message
    assert not _group_create_writes(calls), (
        "a refusal must block the apply step entirely, not just the refused object"
    )
    assert not _role_def_merge_writes(calls, "Schema Manager"), (
        "a refusal must block every object's apply, not only the colliding group's"
    )
    assert summary.get("aborted") == "phase-0-security-errors", summary


def test_no_reader_no_enrolment_code() -> None:
    """Opt-in: the code path must not exist unless asked for.

    Absence, asserted on the emitted text, is the one thing a text
    assertion states exactly. A guard that is present but unreachable is
    the failure mode this file avoids elsewhere; a call site that is not
    emitted at all cannot run.
    """
    js = _deploy_js()
    assert "ensureuser" not in js
    assert f"Starting Phase {pn('reader_enrolment')}" not in js
    # And the same mapping, WITH a reader, does emit it. Otherwise the two
    # assertions above would also hold for a template that never works.
    assert "ensureuser" in _reader_deploy_js()


# Every write path reaches a refused contextinfo through the shared digest helper (#282).
_ACCESS_DENIED = json.dumps({
    "error": {
        "code": "-2147024891, System.UnauthorizedAccessException",
        "message": {
            "lang": "en-US",
            "value": "Access denied. You do not have permission to perform this action.",
        },
    },
})

# Wrap `_HARNESS` so contextinfo alone fails and the call log shows any later write.
_REFUSE_DIGEST = textwrap.dedent("""
    const DIGEST_BODY = __BODY__;
    const healthyFetch = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      if (!String(url).includes('contextinfo')) return healthyFetch(url, opts);
      // json() reads through text(), so a body that cannot be read cannot be
      // parsed either, as with a real Response.
      const refused = {
        ok: false, status: __STATUS__,
        headers: { get: () => null },
        text: async () => __TEXT__,
        json: async () => JSON.parse(await refused.text()),
      };
      return refused;
    };
""")

# Model a fetch rejection before any contextinfo Response exists.
_NO_RESPONSE = textwrap.dedent("""
    const healthyFetch = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      if (!String(url).includes('contextinfo')) return healthyFetch(url, opts);
      // The message a browser gives for a failed or blocked fetch.
      throw new TypeError('Failed to fetch');
    };
""")

# Model a successful HTTP response whose contextinfo payload cannot authorise a write.
_MALFORMED_CONTEXTINFO = textwrap.dedent("""
    const healthyFetch = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      if (!String(url).includes('contextinfo')) return healthyFetch(url, opts);
      const payload = { d: { GetContextWebInformation: __INFO__ } };
      return {
        ok: true, status: 200, headers: { get: () => null },
        json: async () => payload, text: async () => JSON.stringify(payload),
      };
    };
""")


def _malformed_contextinfo(info: Any) -> str:
    return _MALFORMED_CONTEXTINFO.replace("__INFO__", json.dumps(info))


# Model a connection drop or decode failure while `Response.text()` reads the body.
_BODY_READ_REJECTS = "Promise.reject(new Error('network error reading the response body'))"


def _refuse_digest(status: int, body: str, *, body_read_fails: bool = False) -> str:
    """`_HARNESS`'s fetch, wrapped so contextinfo alone answers `status`."""
    return _REFUSE_DIGEST.replace("__STATUS__", str(status)).replace(
        "__BODY__", json.dumps(body),
    ).replace("__TEXT__", _BODY_READ_REJECTS if body_read_fails else "DIGEST_BODY")


class _DigestRun(NamedTuple):
    """What a run whose contextinfo is refused left the operator with.

    `thrown` is the rejection that reached the top of the deploy promise, and
    it must be None: every phase hands back a structured summary, so a
    refusal that rejects instead is the #282 failure one level up. It is
    captured rather than asserted here so each test can say so in its own
    terms.
    """

    summary: dict[str, Any] | None
    messages: list[str]
    calls: list[dict[str, Any]]
    thrown: str | None
    output: str


def _run_with_failing_digest(refusal: str, *, js: str | None = None) -> _DigestRun:
    """Run the shipped deploy against a site whose contextinfo is refused.

    `refusal` is one of the fetch wrappers above; `js` swaps the stubbed
    assessment for the script exactly as it ships. The contextinfo attempt
    itself never reaches the call log (the wrapper answers it before
    delegating), so any POST in `calls` is a real write.
    """
    js = _deploy_js() if js is None else js
    script = _HARNESS + refusal + "\n" + js.replace(
        "})();",
        "}))().then("
        "(r) => console.log('__RESULT__' + JSON.stringify(r)),"
        " (e) => console.log('__THROWN__' + JSON.stringify(String((e && e.message) || e))))"
        ".then(() => console.log('__CALLS__' + JSON.stringify(globalThis.__calls)))",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)

    def _marker(name: str) -> Any:
        line = next((ln for ln in output.splitlines() if ln.startswith(name)), None)
        return None if line is None else json.loads(line.removeprefix(name))

    calls = _marker("__CALLS__")
    assert calls is not None, f"the harness produced no call log:\n{output[-3000:]}"
    summary = _marker("__RESULT__")
    thrown = _marker("__THROWN__")
    messages = [str(e.get("error")) for e in ((summary or {}).get("errors") or [])]
    return _DigestRun(summary, messages, calls, None if thrown is None else str(thrown), output)


def _reached_a_summary(run: _DigestRun) -> dict[str, Any]:
    """The summary, refusing a run that rejected instead of returning one."""
    assert run.thrown is None, (
        "the deploy promise rejected instead of handing back a summary: "
        f"{run.thrown}\n{run.output[-3000:]}"
    )
    assert run.summary is not None, f"the run returned no summary:\n{run.output[-3000:]}"
    return run.summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_contextinfo_reports_the_sharepoint_reason() -> None:
    """A 403 on contextinfo surfaced as `Cannot read properties of undefined
    (reading 'GetContextWebInformation')`, because the helper read the
    verbose success shape without checking `r.ok`. The operator was handed a
    JavaScript type error in place of the reason SharePoint gave.
    """
    run = _run_with_failing_digest(_refuse_digest(403, _ACCESS_DENIED))
    _reached_a_summary(run)
    assert "GetContextWebInformation" not in run.output, (
        f"the refusal still surfaces as a property-access error:\n{run.output[-3000:]}"
    )
    named = [m for m in run.messages if "contextinfo" in m]
    assert named, f"nothing the operator sees names the failed operation: {run.messages}"
    for message in named:
        assert "403" in message, message
        assert "Access denied" in message, message
    writes = [c for c in run.calls if c["method"] == "POST"]
    assert not writes, f"a run that cannot take a digest must not write: {writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_refused_phase_digest_is_recorded_rather_than_thrown() -> None:
    """The first digest of the run is taken at the head of the security phase,
    outside every per-object catch there, so a refusal rejected the whole
    deploy promise. An operator got an unhandled rejection where every other
    failure in that phase hands back the aborted summary, and a test that
    accepted the throw as a named message could not tell the two apart.
    """
    run = _run_with_failing_digest(_refuse_digest(403, _ACCESS_DENIED))
    summary = _reached_a_summary(run)
    assert summary.get("aborted") == "phase-0-security-errors", summary
    errors = _security_errors(summary)
    assert errors, f"the refused phase digest reached no summary.errors: {summary}"
    for err in errors:
        assert "contextinfo" in str(err.get("error")), err
        assert "403" in str(err.get("error")), err
    # The abort has to precede the apply pass, not merely be reported after it.
    writes = [c for c in run.calls if c["method"] == "POST"]
    assert not writes, f"the phase wrote without a digest: {writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_contextinfo_that_never_answered_still_names_the_operation() -> None:
    """`fetchWithRetry` can reject before there is any Response: a dropped
    connection, a CORS refusal. Checking `r.ok` cannot see that, so the raw
    `TypeError: Failed to fetch` bubbled with nothing saying which request
    produced it, on a script that makes hundreds.
    """
    run = _run_with_failing_digest(_NO_RESPONSE)
    _reached_a_summary(run)
    named = [m for m in run.messages if "contextinfo" in m]
    assert named, f"nothing the operator sees names the failed operation: {run.messages}"
    for message in named:
        assert "no response" in message, message
        assert "Failed to fetch" in message, message
        # Bounded like every other arm, rather than pasting an unbounded cause.
        assert len(message) < 400, message
    writes = [c for c in run.calls if c["method"] == "POST"]
    assert not writes, f"a run that cannot take a digest must not write: {writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(("info", "expected"), [
    ([], "GetContextWebInformation"),
    ({}, "FormDigestValue"),
    ({"FormDigestValue": ""}, "FormDigestValue"),
    ({"FormDigestValue": "   "}, "FormDigestValue"),
])
def test_a_contextinfo_without_a_digest_cannot_reach_a_write(
    info: Any, expected: str,
) -> None:
    run = _run_with_failing_digest(_malformed_contextinfo(info))
    _reached_a_summary(run)
    named = [m for m in run.messages if expected in m]
    assert named, f"the malformed success payload was not named: {run.messages}"
    assert all("HTTP 200" in message for message in named)
    writes = [c for c in run.calls if c["method"] == "POST"]
    assert not writes, f"the phase wrote with no usable digest: {writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_malformed_contextinfo_error_body_falls_back_to_bounded_text() -> None:
    """`spError` cannot parse a sign-in page or a proxy's HTML, so the helper
    must still name the operation and the status, and carry the raw text
    clipped to spError's 300-character bound rather than the whole page.
    """
    body = "<html><body>Sign in to SharePoint " + ("x" * 600) + "</body></html>"
    run = _run_with_failing_digest(_refuse_digest(500, body))
    _reached_a_summary(run)
    named = [m for m in run.messages if "contextinfo" in m]
    assert named, f"nothing the operator sees names the failed operation: {run.messages}"
    for message in named:
        assert "500" in message, message
        assert "Sign in to SharePoint" in message, message
        assert body not in message, f"the whole body was pasted in unbounded: {message}"
        assert len(message) < len(body), message


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_parsed_sharepoint_error_message_is_also_bounded() -> None:
    server_message = "SharePoint says " + ("x" * 800)
    body = json.dumps({"error": {"message": {"value": server_message}}})
    run = _run_with_failing_digest(_refuse_digest(500, body))
    _reached_a_summary(run)
    named = [m for m in run.messages if "contextinfo" in m]
    assert named, f"nothing names the failed operation: {run.messages}"
    assert all("SharePoint says" in message for message in named)
    assert all(server_message not in message for message in named)
    assert all(len(message) < 400 for message in named)


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_contextinfo_body_that_cannot_be_read_still_names_the_operation() -> None:
    """`Response.text()` can itself reject: a connection dropped mid-body, a
    decode failure. Awaiting it inside the throw expression let that
    rejection replace the named error before it was ever constructed,
    leaving the operator with neither the operation nor the status, which is
    where #282 started.
    """
    run = _run_with_failing_digest(
        _refuse_digest(500, "never read", body_read_fails=True),
    )
    _reached_a_summary(run)
    named = [m for m in run.messages if "contextinfo" in m]
    assert named, f"nothing the operator sees names the failed operation: {run.messages}"
    for message in named:
        assert "500" in message, message
        assert "unreadable" in message, message
        # A 400-character cap proves the bounded fallback rather than the whole body.
        assert len(message) < 400, message
    writes = [c for c in run.calls if c["method"] == "POST"]
    assert not writes, f"a run that cannot take a digest must not write: {writes}"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_uncaught_phase_failure_returns_an_aborted_summary() -> None:
    needle = (
        f"  log('INFO', 'Starting Phase {pn('security')}: permission levels and site groups.');"
    )
    js = _deploy_js().replace(
        needle,
        needle + "\n  throw new Error('contextinfo (request digest) failed: no response');",
        1,
    ).replace(
        "    await removeSelfEnrollments();",
        "    await removeSelfEnrollments();\n    console.log('__CLEANUP__');",
        1,
    )
    assert js != _deploy_js(), "the phase failure and cleanup marker were not injected"
    run = _run_with_failing_digest("", js=js)
    summary = _reached_a_summary(run)
    assert "__CLEANUP__" in run.output
    assert summary.get("aborted") == "uncaught-phase-error", summary
    assert any("contextinfo" in str(error.get("error")) for error in summary["errors"])
    list_writes = [
        call for call in run.calls
        if call["method"] == "POST" and call["url"].rstrip("/").endswith("/lists")
    ]
    assert not list_writes, f"list creation ran after the phase failed: {list_writes}"


def test_a_security_digest_failure_stops_the_decision_loop() -> None:
    js = _deploy_js()
    assert "failure.digestFailure = true;" in js
    assert "let digestFailure" not in js
    assert "if (err && err.digestFailure) break;" in js
    assert js.index(f"summary.errors.push({{ phase: '{pn('security')}'") < js.index(
        "if (err && err.digestFailure) break;",
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_deploy_assessment_names_a_refused_contextinfo() -> None:
    """Deploy's first phase is the assessment, and its own contextinfo probe
    read `j.d.GetContextWebInformation` without checking the response. A 403
    there reported a property-access TypeError as the site's answer, one
    phase before the shared digest helper is ever reached.
    """
    run = _run_with_failing_digest(
        _refuse_digest(403, _ACCESS_DENIED), js=_deploy_js_with_assessment(),
    )
    summary = _reached_a_summary(run)
    assert "GetContextWebInformation" not in run.output, (
        f"the refusal still surfaces as a property-access error:\n{run.output[-3000:]}"
    )
    findings = (summary.get("assessment") or {}).get("findings") or []
    named = [f for f in findings if "contextinfo" in str(f.get("detail"))]
    assert named, f"no finding names the refused request: {findings}"
    for finding in named:
        assert "403" in str(finding["detail"]), finding
        assert "Access denied" in str(finding["detail"]), finding
    # The gate must stop the run, and it must stop it before anything is written.
    assert str(summary.get("aborted")).startswith("assessment-"), summary
    writes = [c for c in run.calls if c["method"] == "POST"]
    assert not writes, f"the deploy wrote after a failed assessment: {writes}"


# --- The live ownership guard on the later write phases (#305) --------------
#
# Ownership is proved by the schema phases and then goes stale: every phase
# after them addresses its target list by TITLE, so a marker removed or a
# same-titled list swapped in afterwards used to be written to by a run that
# had never proved it owned the object in front of it. The runs below put
# each of those two events at each later write phase's boundary and assert
# the phase writes nothing.
#
# The two are not the same guard and are tested separately. A marker loss is
# caught by the phase's batch survey, which runs before the first write of
# the batch; a same-titled replacement carries the marker, so only the list
# ID comparison sees it, and it is armed one read LATER (the survey passes,
# the recheck immediately before the write does not).


class _GuardedPhase(NamedTuple):
    """A write phase with a live ownership guard, and the code it aborts on."""

    key: str
    aborted: str


_GUARDED_WRITE_PHASES = (
    _GuardedPhase("unseal", "maintenance-ownership-errors"),
    _GuardedPhase("indexes", "index-ownership-errors"),
    _GuardedPhase("defaults", "default-ownership-errors"),
    _GuardedPhase("views", "view-ownership-errors"),
    _GuardedPhase("forms", "form-ownership-errors"),
    _GuardedPhase("seal", "seal-ownership-errors"),
    _GuardedPhase("acls", "acl-ownership-errors"),
    _GuardedPhase("seeds", "seed-ownership-errors"),
)


class _OwnershipSeedExtension(BaseExtension):
    """Seeds one row into every declared list.

    Seeding is the only write phase whose work comes from an extension
    rather than the mapping, so without one the DATA phase loops over an
    empty list and every assertion about it passes for the wrong reason.
    """

    name: ClassVar[str] = "ownershipstub"

    def __init__(self, titles: tuple[str, ...]) -> None:
        self._titles = titles

    def seed_lists(
        self, bundle: Any, schema: Any, site_context: Any,
    ) -> dict[str, dict[str, Any]]:
        return {title: {"Title": "seeded"} for title in self._titles}


def _ownership_section(table_names: tuple[str, ...]) -> str:
    """Mapping that gives every guarded write phase something to write.

    `_declared_pack`'s schema reaches the end of the run but declares no
    index, no default, no form formatting and no ACL, so six of the eight
    guarded phases would loop over nothing.
    """
    forms = "".join(
        f"  {name}:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Main, fields: [Title, Note] }\n"
        for name in table_names
    )
    return (
        "groups:\n"
        '  - name: "Ownership Reader"\n'
        '    description: "Read-only grant target for the ownership tests."\n'
        '    owner_group: "Site Owners"\n'
        "    allow_members_edit_membership: false\n"
        "    allow_request_to_join_leave: false\n"
        "    auto_accept_request_to_join_leave: false\n"
        "    only_allow_members_view_membership: false\n"
        "\n"
        "list_permissions:\n"
        "  default:\n"
        "    site_role: default\n"
        "    break_inheritance: true\n"
        "    reconcile: exact\n"
        "    assignments:\n"
        '      - principal: { kind: group, name: "Ownership Reader" }\n'
        '        level: "Read"\n'
        "\n"
        f"form_formatting:\n{forms}"
    )


def _ownership_pack(
    tmp_path: Path, table_names: tuple[str, ...],
) -> tuple[Any, Any]:
    """The (schema, bundle) the ownership runs deploy.

    A DBML default on `Title` rather than on `Note`: the mock keys created
    columns by a shared Id, so only the Title field's own state can observe
    a by-Id MERGE landing, and a default that cannot be read back would fail
    the phase for a reason that has nothing to do with ownership.
    """
    return pack(
        tmp_path,
        dbml="".join(
            table(
                name, ID_PK, "Title nvarchar [default: 'seeded']", "Note nvarchar",
                "indexes {\n    Note\n  }",
            )
            for name in table_names
        ),
        mapping=blocks(entities(*table_names), _ownership_section(table_names)),
    )


def _ownership_deploy_js(tmp_path: Path, table_names: tuple[str, ...]) -> str:
    from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = _ownership_pack(tmp_path, table_names)
    titles = tuple(
        entry["title"] for entry in build_schema_json(schema, bundle, "default")["lists"]
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
        extension=_OwnershipSeedExtension(titles),
    ))


def _ownership_list_descriptions(
    tmp_path: Path, table_names: tuple[str, ...],
) -> dict[str, str]:
    """List title -> the Description this pack declares for it.

    Read out of the generator rather than re-spelled, for the reason
    `_declared_list_descriptions` gives: the marker embeds the entity name,
    so no single string is the declared description of two lists.
    """
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _ownership_pack(tmp_path, table_names)
    return {
        entry["title"]: entry["description"]
        for entry in build_schema_json(schema, bundle, "default")["lists"]
    }


# One direct grant nobody declared, so exact-mode reconciliation has a
# removal to make. Without it the ACL phase only ever adds, and the
# removal path -- the irreversible one, and the reason #305 calls ACLs the
# highest risk alongside seeding -- is never reached by any of these runs.
_STRAY_BINDING = [[{
    "Member": {"Id": 7, "Title": "Stray Group", "PrincipalType": 8},
    "RoleDefinitionBindings": {"results": [{"Id": 1, "Name": "Schema Manager"}]},
}]]


def _run_ownership_deploy(
    tmp_path: Path,
    *,
    table_names: tuple[str, ...] = ("Escalation",),
    sabotage_phase: str | None = None,
    sabotage_titles: tuple[str, ...] = (),
    sabotage_mode: str = "marker",
    sabotage_after_reads: int = 0,
) -> tuple[dict[str, Any], list[dict[str, Any]], str]:
    """Run the ownership pack against the adopted-site mock.

    Built on `_READER_ACL_HARNESS` rather than `_ADOPTED_HARNESS` for the
    same reason the enterprise-reader run is: these lists grant a BUILT-IN
    level ('Read'), which the plain harness's role-definition state does not
    carry.
    """
    descriptions = _ownership_list_descriptions(tmp_path, table_names)
    harness = _READER_ACL_HARNESS.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(descriptions.items()))});",
    ).replace(
        "const ROLE_ASSIGNMENT_PAGES = {};",
        "const ROLE_ASSIGNMENT_PAGES = "
        f"{json.dumps(dict.fromkeys(descriptions, _STRAY_BINDING))};",
    ).replace(
        "const SABOTAGE_FROM_PHASE = null;",
        f"const SABOTAGE_FROM_PHASE = {json.dumps(sabotage_phase)};",
    ).replace(
        "const SABOTAGE_TITLES = [];",
        f"const SABOTAGE_TITLES = {json.dumps(list(sabotage_titles))};",
    ).replace(
        "const SABOTAGE_MODE = 'marker';",
        f"const SABOTAGE_MODE = {json.dumps(sabotage_mode)};",
    ).replace(
        "const SABOTAGE_AFTER_READS = 0;",
        f"const SABOTAGE_AFTER_READS = {json.dumps(sabotage_after_reads)};",
    )
    script = harness + "\n" + _ownership_deploy_js(tmp_path, table_names).replace(
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
    return (
        json.loads(result_line.removeprefix("__RESULT__")),
        json.loads(calls_line.removeprefix("__CALLS__")),
        output,
    )


def _writes_in_phase(
    calls: list[dict[str, Any]], phase: str,
) -> list[dict[str, Any]]:
    """Mutating requests the run issued while `phase` was the current one.

    The mock tags every request with the phase banner in force when it was
    made, so a test can say "this phase wrote nothing" without re-deriving
    phase boundaries from URLs.
    """
    return [c for c in _deployment_writes(calls) if c["phase"] == phase]


def _phase_log(output: str, phase: str) -> list[str]:
    """The run's log lines between `phase`'s banner and the next phase's.

    So a test can say WHICH phase reported a failure. The summary's error
    list cannot: half the write phases record an error without a phase key,
    and a rebound title survives into the phases after the one under test,
    which would let a later phase's identical complaint satisfy an
    assertion about this one.
    """
    lines = output.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if f"Starting Phase {phase}:" in line), None,
    )
    assert start is not None, f"phase {phase} never ran:\n{output[-3000:]}"
    rest = lines[start + 1:]
    end = next(
        (i for i, line in enumerate(rest) if "Starting Phase " in line), len(rest),
    )
    return rest[:end]


_OWNED_TITLE = "APP_Escalation"
_OTHER_TITLE = "APP_Other"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_every_guarded_phase_writes_when_ownership_holds(tmp_path: Path) -> None:
    """What gives the refusal tests below their meaning.

    Each of those asserts a phase wrote NOTHING. That assertion passes just
    as happily against a fixture that declares no index, no default, no form
    and no ACL, or against a run that never reached the phase at all. This
    run is the same fixture with nothing sabotaged: it must finish clean and
    write in every phase the others watch refusing to write.
    """
    summary, calls, output = _run_ownership_deploy(
        tmp_path, table_names=("Escalation", "Other"),
    )
    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]
    for phase in _GUARDED_WRITE_PHASES:
        assert _writes_in_phase(calls, pn(phase.key)), (
            f"phase {phase.key} ({pn(phase.key)}) wrote nothing, so the "
            f"refusal test for it proves nothing:\n{output[-3000:]}"
        )


# The guard is a closure, not an export, so it is measured from INSIDE the
# run: spliced ahead of the next function declaration, which runs before any
# phase does. Attributing requests to it from the outside instead would mean
# re-deriving which of a phase's list reads were its, and that attribution
# shifts with every probe added anywhere else in the run.
_GUARD_EXPORT_ANCHOR = "  async function assertDeclaredFieldOwnedNow(listName, field) {"

_GUARD_COST_TAIL = """.then(async (r) => {
  console.log('__RESULT__' + JSON.stringify(r));
  const measure = async (title) => {
    globalThis.__calls.length = 0;
    let message = null;
    try { await globalThis.__ownedGuard(title); } catch (err) { message = err.message; }
    return { message, urls: globalThis.__calls.map((c) => c.url) };
  };
  const hit = await measure('APP_Escalation');
  globalThis.__absentListTitles.push('APP_Escalation');
  const miss = await measure('APP_Escalation');
  console.log('__GUARD__' + JSON.stringify({ hit, miss }));
});
"""


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_ownership_guard_costs_one_request_per_call(tmp_path: Path) -> None:
    """The guard reads the list by title, with no enumeration ahead of it.

    It is the deploy's most-called function by a wide margin (462 calls on a
    ten-list family, 21% of every request the run made when each cost two
    GETs), so its per-call cost is pinned rather than left to be doubled
    again by a later change routing it back through `readListShape`, whose
    forced `web/lists?$select=Title` is right for the callers that expect
    absence and wasted here, where absence is fatal.

    Both paths, because the cheaper one is only safe if the refusal it
    replaces is unchanged: the absent list still produces the same message,
    for the same one request.
    """
    descriptions = _ownership_list_descriptions(tmp_path, ("Escalation", "Other"))
    harness = _READER_ACL_HARNESS.replace(
        "const LIST_DESCRIPTIONS = new Map([]);",
        f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(descriptions.items()))});",
    ).replace(
        "const ROLE_ASSIGNMENT_PAGES = {};",
        "const ROLE_ASSIGNMENT_PAGES = "
        f"{json.dumps(dict.fromkeys(descriptions, _STRAY_BINDING))};",
    )
    js = _ownership_deploy_js(tmp_path, ("Escalation", "Other"))
    exported = js.replace(
        _GUARD_EXPORT_ANCHOR,
        "  globalThis.__ownedGuard = (name) => assertDeclaredListOwnedNow(name);\n"
        + _GUARD_EXPORT_ANCHOR,
        1,
    )
    assert exported != js, "the guard export did not splice in"
    # Wrapped rather than spliced on `})();`: one of the emitted comments
    # names that sequence, and a multi-line tail replacing THAT occurrence
    # escapes the comment and breaks the file.
    body = exported.rstrip()
    assert body.endswith("})();")
    output = _run(f"{harness}\n({body[:-1]}){_GUARD_COST_TAIL}")
    # A measurement taken against a broken run measures the wrong thing.
    assert _summary_of(output).get("errors") == [], output[-3000:]
    line = next(
        (ln for ln in output.splitlines() if ln.startswith("__GUARD__")), None,
    )
    assert line is not None, f"the guard was never measured:\n{output[-3000:]}"
    measured = json.loads(line.removeprefix("__GUARD__"))

    hit = measured["hit"]
    assert hit["message"] is None, hit
    assert len(hit["urls"]) == 1, (
        f"an owned list cost {len(hit['urls'])} requests: {hit['urls']}"
    )
    assert f"getbytitle('{_OWNED_TITLE}')" in hit["urls"][0], hit["urls"]
    assert "web/lists?" not in hit["urls"][0], hit["urls"]

    miss = measured["miss"]
    assert miss["message"] == (
        f"Declared list '{_OWNED_TITLE}' disappeared before a field write"
    ), miss
    assert len(miss["urls"]) == 1, (
        f"an absent list cost {len(miss['urls'])} requests: {miss['urls']}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    "phase", _GUARDED_WRITE_PHASES, ids=[p.key for p in _GUARDED_WRITE_PHASES],
)
def test_losing_a_marker_stops_a_write_phase_before_its_first_write(
    tmp_path: Path, phase: _GuardedPhase,
) -> None:
    """One list loses its marker as the phase opens, and the batch stops.

    Two lists, and only the first loses its marker: the phase must not write
    to the SECOND one either. Every one of these phases loops over its
    targets, so the failure has to be found by the survey that runs before
    the loop, not by the target's own turn in it.
    """
    summary, calls, output = _run_ownership_deploy(
        tmp_path,
        table_names=("Escalation", "Other"),
        sabotage_phase=pn(phase.key),
        sabotage_titles=(_OWNED_TITLE,),
        sabotage_mode="marker",
    )
    assert summary.get("aborted") == phase.aborted, summary
    assert any(
        f"ownership survey '{_OWNED_TITLE}'" in line
        for line in _phase_log(output, pn(phase.key))
    ), f"phase {phase.key} did not name the list it refused:\n{output[-3000:]}"
    assert not _writes_in_phase(calls, pn(phase.key)), (
        f"phase {phase.key} wrote after its ownership survey failed: "
        f"{_writes_in_phase(calls, pn(phase.key))}"
    )


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize(
    "phase", _GUARDED_WRITE_PHASES, ids=[p.key for p in _GUARDED_WRITE_PHASES],
)
def test_a_same_titled_replacement_stops_a_write_phase(
    tmp_path: Path, phase: _GuardedPhase,
) -> None:
    """The title still resolves, and it resolves to a different list.

    The replacement carries the marker, which is the case the survey cannot
    see: only comparing the live list ID against the one the survey captured
    catches it. Armed one read after the phase opens, so the survey passes
    and the recheck immediately before the write is what refuses.
    """
    summary, calls, output = _run_ownership_deploy(
        tmp_path,
        sabotage_phase=pn(phase.key),
        sabotage_titles=(_OWNED_TITLE,),
        sabotage_mode="rebind",
        sabotage_after_reads=1,
    )
    assert any(
        "changed identity" in line for line in _phase_log(output, pn(phase.key))
    ), f"phase {phase.key} did not refuse the replacement:\n{output[-3000:]}"
    assert summary["errors"], summary
    assert not _writes_in_phase(calls, pn(phase.key)), (
        f"phase {phase.key} wrote to a replaced list: "
        f"{_writes_in_phase(calls, pn(phase.key))}"
    )


def test_the_deploy_confirms_the_editor_still_refuses_the_guard() -> None:
    """The emitted script must ask the tenant rather than assume.

    Measured 2026-08-17 (view-edit-page-probe.js): a view is protected when
    its edit page returns 200 from the endpoint asked for, carries a
    sentinel, and does not carry the editor's control names. What that
    predicate is applied to (an editable control, then every filtered view)
    is exercised against a mock site further down.
    """
    script = _deploy_js()
    assert "ViewEdit.aspx" in script
    assert 'name=\"FieldPicker1\"' in script
    # A sentinel gates the absence check. C6 measured a request for a view
    # that does not exist answering 200 with no editor controls, so absence
    # alone would call a page that is not a view protected. Pinned as the
    # declaration rather than as a substring: `ctl00` and `ViewEdit` are on
    # that page too and are named in the comment beside it, so a bare
    # containment test would pass on either of them.
    assert "const EDITOR_PAGE_SENTINEL = 'ViewFilter';" in script
    # English display text must not be the predicate: it reads correctly on
    # an English tenant and silently wrong on any other.
    assert "complex filter" not in script


def test_no_path_through_the_guard_check_can_report_a_clean_run() -> None:
    """Unverifiable and unprotected are different, and both must fail.

    They were once a warning and an error respectively, on the reading that a
    check unable to read the page is not evidence the view is unprotected.
    True, and not enough: nothing else asks the question, so a warning left
    the run reporting clean about the one property an operator destroys by
    pressing Save. Every path out of the check now records an error, and the
    behaviours themselves are exercised against a mock site below.
    """
    script = _deploy_js()
    start = script.index("async function confirmEditorRefusesTheGuard")
    block = script[start:script.index("await confirmEditorRefusesTheGuard();")]

    # Nothing under this check warns any more, anywhere in the script: a
    # second warn-only path is the shape this regressed as the first time.
    assert "summary.warnings" not in script

    # Every path that could not answer routes through one helper, and each
    # one stops there rather than falling through to the success line.
    calls = [line for line in block.splitlines() if "unverified(" in line]
    assert len(calls) >= 4, calls
    lines = block.splitlines()
    for index, line in enumerate(lines):
        if "unverified(" not in line:
            continue
        assert "return;" in chr(10).join(lines[index:index + 8]), line

    # The helper records an error rather than a warning, and the push is a
    # statement rather than a guarded expression: `void 0 && push` would
    # satisfy a containment test while never running.
    helper = script[script.index("const unverified = (why, view) => {"):]
    helper = helper[:helper.index("\n  };")]
    assert "log('ERROR'" in helper
    assert [ln.strip() for ln in helper.splitlines() if "summary.errors.push" in ln] == [
        "summary.errors.push({",
    ]


# The view settings page as measured on 2026-08-17 (view-edit-page-probe.js):
# half a megabyte of markup carrying the `ViewFilter` sentinel, and the
# editor's control names only where the filter is editable. The mock serves a
# variant per view title, so one run can hold a refused view beside an
# editable one, which is the arrangement the whole check exists to tell apart.
#
#   editable   the controls are there, so the filter can be truncated
#   refused    the guard took: sentinel, no controls, complete document
#   drifted    complete and editable, but the controls carry other names
#   truncated  HTTP 200 cut after the sentinel and before the controls
#   trailing   refused shape, then trailing markup after the document close
#   interior   cut before the controls, past an `</html>` literal in script
#   stub       complete and sentinelled, but a fraction of a page's size
#   redirect   HTTP 200 from somewhere else, as a login redirect answers
_SETTINGS_PAGE_JS = (
    "const PAGE_POLICY = __POLICY__;\n"
    "const FILLER = 'f'.repeat(60000);\n"
    "const CONTROLS = ['FieldPicker1', 'OperatorPicker1'];\n"
    "const editorPage = (names, tail) => "
    "'<html><head><title>ViewFilter</title></head><body>'\n"
    "  + names.map((n) => `<input name=\"${n}\" type=\"text\" />`).join('')\n"
    "  + FILLER + tail;\n"
    "globalThis.__pageReads = [];\n"
    "const settingsPage = (u) => {\n"
    "  const raw = decodeURIComponent((u.match(/View=([^&]+)/) || [])[1] || '');\n"
    "  const known = VIEW_BY_GUID[raw.replace(/[{}]/g, '')];\n"
    "  globalThis.__pageReads.push(known ? known.title : `unknown ${raw}`);\n"
    "  const policy = known ? (PAGE_POLICY[known.title] || 'refused') : 'unknown';\n"
    "  const pages = {\n"
    "    editable: editorPage(CONTROLS, '</body></html>'),\n"
    "    refused: editorPage([], '</body></html>'),\n"
    "    drifted: editorPage(['FilterField1', 'FilterOperator1'], '</body></html>'),\n"
    "    truncated: '<html><head><title>ViewFilter</title></head><body>',\n"
    "    trailing: editorPage([], '</body></html><script>window.telem=1</script>'),\n"
    "    interior: '<html><head><title>ViewFilter</title></head><body>'\n"
    "      + '<script>var CLOSE = \"</html>\";</script>' + FILLER,\n"
    "    stub: '<html><head><title>ViewFilter</title></head><body>x</body></html>',\n"
    "    unknown: editorPage([], '</body></html>'),\n"
    "    redirect: '<html><body>sign in</body></html>',\n"
    "  };\n"
    "  const redirected = policy === 'redirect';\n"
    "  return { ok: true, status: 200, redirected,\n"
    "    url: redirected ? 'https://example.sharepoint.com/_forms/default.aspx' : u,\n"
    "    headers: { get: () => null },\n"
    "    text: async () => pages[policy],\n"
    "    json: async () => ({}) };\n"
    "};\n"
    "globalThis.fetch = async (url, opts = {}) => {\n"
    "  if (String(url).includes('ViewEdit.aspx')) {\n"
    "    calls.push({ url: String(url), method: 'GET', body: null });\n"
    "    return settingsPage(String(url));\n"
    "  }\n"
)

# What `web/lists/getbytitle('X')?$select=Id` answers with. Only the guard
# confirmation reads that endpoint, and it reads it after the write lanes have
# closed their ownership brackets, so answering it with a different Id models
# one thing and nothing else: a same-titled list that replaced the owned one
# in between.
_OWNED_LIST_ID = "22222222-2222-2222-2222-222222222222"
_REPLACEMENT_LIST_ID = "66666666-6666-6666-6666-666666666666"

# A distinct id per view. The settings-page URL carries the view GUID and
# nothing else that names the view, so the mock cannot serve two views
# different pages while `_ADOPTED_HARNESS` gives every view one fixed id.
_VIEW_GUIDS_JS = (
    "const views = {};\n"
    "const SETTINGS_LIST_ID = '__SETTINGS_LIST_ID__';\n"
    "const VIEW_GUIDS = {};\n"
    "const VIEW_BY_GUID = {};\n"
    "let nextViewId = 0;\n"
    "const viewGuid = (listTitle, title) => {\n"
    "  const key = `${listTitle} ${title}`;\n"
    "  if (!VIEW_GUIDS[key]) {\n"
    "    nextViewId += 1;\n"
    "    VIEW_GUIDS[key] = "
    "`55555555-0000-0000-0000-${String(nextViewId).padStart(12, '0')}`;\n"
    "    VIEW_BY_GUID[VIEW_GUIDS[key]] = { list: listTitle, title };\n"
    "  }\n"
    "  return VIEW_GUIDS[key];\n"
    "};\n"
)

_VIEWS_ENUM_OLD = (
    "  if (url.includes('/views?')) {\n"
    "    const listTitle = listOf(url);\n"
    "    return { d: { results: [viewState(listTitle)] } };\n"
    "  }\n"
)

# The list's own Id (the check reads `?$select=Id` to build the page URL) and
# an enumeration that answers with the views this run created, not with the
# one built-in All Items. Without the second, every declared view reads as
# absent after deployment and the check can only ever report that.
_VIEWS_ENUM_NEW = (
    "  if (url.endsWith('?$select=Id')) {\n"
    "    return { d: { Id: SETTINGS_LIST_ID } };\n"
    "  }\n"
    "  if (url.includes('/views?')) {\n"
    "    const listTitle = listOf(url);\n"
    "    viewState(listTitle);\n"
    "    return { d: { results: Object.entries(views)\n"
    "      .filter(([key]) => key.startsWith(`${listTitle} `))\n"
    "      .map(([, shape]) => shape) } };\n"
    "  }\n"
)

_VIEW_CREATE_JS = (
    "  if ((opts.method || 'GET') === 'POST' && opts.body && /\\/views$/.test(u)) {\n"
    "    const parsed = JSON.parse(opts.body);\n"
    "    if (parsed.__metadata && parsed.__metadata.type === 'SP.View') {\n"
    "      const state = viewState(listOf(u), parsed.Title);\n"
    "      for (const key of ['Hidden', 'RowLimit', 'ViewQuery']) {\n"
    "        if (parsed[key] !== undefined) state[key] = parsed[key];\n"
    "      }\n"
    "      state.DefaultView = parsed.DefaultView === true;\n"
    "      state.ServerRelativeUrl = "
    "`/sites/test/Lists/${listOf(u)}/${parsed.Title}.aspx`;\n"
    "      state.ViewFields = { Items: { results: [] } };\n"
    "    }\n"
    "  }\n"
    "  if ((opts.method || 'GET') === 'POST' && u.includes('/views/getbytitle')) {\n"
)

# Two filtered views on one list, so a run can refuse the first and open the
# second. Single-word titles: the deployer creates a view under its URL slug
# and renames it afterwards, and a title equal to its own slug keeps the
# mock's view state under one key.
_GUARDED_VIEWS = """
views:
  Escalation:
    - title: "Open"
      fields: [Title, Note]
      where:
        - { field: Note, op: neq, value: "done" }
    - title: "Recent"
      fields: [Title, Note]
      where:
        - { field: Title, op: neq, value: "x" }
"""


def _view_guard_harness(
    policy: dict[str, str], settings_list_id: str = _OWNED_LIST_ID,
) -> str:
    """`_ADOPTED_HARNESS` that also serves view settings pages.

    `policy` maps a view title to the page variant the mock serves for it,
    defaulting to `refused`. `All Items` is the unfiltered control the check
    validates its markers against, so a run that means to reach the filtered
    views has to declare it editable.

    `settings_list_id` is the Id the guard confirmation's list read answers
    with; see `_REPLACEMENT_LIST_ID`.
    """
    harness = _ADOPTED_HARNESS
    for what, old, new in (
        ("view guids", "const views = {};\n", _VIEW_GUIDS_JS),
        ("view id", "    Id: '44444444-4444-4444-4444-444444444444',\n",
         "    Id: viewGuid(listTitle, title),\n"),
        ("view enumeration", _VIEWS_ENUM_OLD, _VIEWS_ENUM_NEW),
        ("view create",
         "  if ((opts.method || 'GET') === 'POST' && u.includes('/views/getbytitle')) {\n",
         _VIEW_CREATE_JS),
        ("settings page", "globalThis.fetch = async (url, opts = {}) => {\n",
         _SETTINGS_PAGE_JS),
    ):
        spliced = harness.replace(old, new, 1)
        assert spliced != harness, f"{what} was not spliced into the harness"
        harness = spliced
    return harness.replace("__POLICY__", json.dumps(policy)).replace(
        "__SETTINGS_LIST_ID__", settings_list_id,
    )


def _run_view_guard_deploy(
    tmp_path: Path, policy: dict[str, str],
    settings_list_id: str = _OWNED_LIST_ID,
) -> tuple[dict[str, Any], list[str], str]:
    """Deploy two filtered views against a site that serves settings pages.

    Returns (summary, the view titles whose settings page was read in order,
    output).
    """
    js = _declared_deploy_js(tmp_path, _GUARDED_VIEWS)
    script = _view_guard_harness(policy, settings_list_id) + "\n" + js.replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r));"
        " console.log('__PAGES__' + JSON.stringify(globalThis.__pageReads)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    summary = _summary_of(output)
    pages_line = next(
        (ln for ln in output.splitlines() if ln.startswith("__PAGES__")), None,
    )
    assert pages_line is not None, f"harness logged no page reads:\n{output[-3000:]}"
    read: list[str] = json.loads(pages_line.removeprefix("__PAGES__"))
    return summary, read, output


def _refusal_errors(summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        e for e in summary.get("errors", [])
        if e.get("check") == "filter-editor-refusal"
    ]


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_guard_check_reads_the_control_then_every_filtered_view(
    tmp_path: Path,
) -> None:
    """The clean run, and what the failing runs below are measured against.

    The control is read first: its markers are what makes an absence on a
    guarded view mean anything, so a run that could not read it has nothing
    to conclude from the pages that follow.
    """
    summary, read, output = _run_view_guard_deploy(tmp_path, {"All Items": "editable"})
    assert summary.get("aborted") is None, summary
    assert summary.get("errors") == [], summary["errors"]
    assert read == ["All Items", "Open", "Recent"], read
    assert "refuses 2 of 2 declared filter(s)" in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_view_the_editor_opens_fails_the_run_even_when_the_first_is_refused(
    tmp_path: Path,
) -> None:
    """Checking one view establishes nothing about the others.

    The first filtered view here is refused and the second is editable, which
    is the arrangement a single-view check reports as protected: it reads the
    refused one, finds no controls and says so for the whole deployment.
    """
    summary, read, output = _run_view_guard_deploy(
        tmp_path, {"All Items": "editable", "Recent": "editable"},
    )
    assert read == ["All Items", "Open", "Recent"], read
    errors = _refusal_errors(summary)
    assert [e["view"] for e in errors] == ["Recent"], errors
    assert "still editable in the filter editor" in errors[0]["error"]
    assert summary.get("aborted"), summary
    assert "refuses 1 of 2 declared filter(s)" in output


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_truncated_settings_page_is_not_a_confirmation(tmp_path: Path) -> None:
    """A response cut after the sentinel and before the controls has neither.

    Absence of the controls is the whole predicate, so a page that stopped
    early reads exactly like a protected one. view-edit-page-probe.js
    `view.filter-editor.control-non-editor-page` (C6) records this shape as
    unmeasured and names a length or completeness test
    as what closes it, which is what the check now requires.
    """
    summary, read, _ = _run_view_guard_deploy(
        tmp_path, {"All Items": "editable", "Open": "truncated"},
    )
    assert read == ["All Items", "Open", "Recent"], read
    errors = _refusal_errors(summary)
    assert [e["view"] for e in errors] == ["Open"], errors
    assert "complete=false" in errors[0]["error"]
    assert summary.get("aborted"), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_page_far_smaller_than_the_settings_page_is_not_a_confirmation(
    tmp_path: Path,
) -> None:
    """Ending in `</html>` is not the same as having arrived whole.

    A stub that closes its own document passes a terminator test while
    carrying none of the editor. The settings page measured 501,773
    characters on 2026-08-17, so a response orders of magnitude under that is
    not the page whose missing controls would mean anything.
    """
    summary, _, _ = _run_view_guard_deploy(
        tmp_path, {"All Items": "editable", "Open": "stub"},
    )
    errors = _refusal_errors(summary)
    assert [e["view"] for e in errors] == ["Open"], errors
    assert "complete=false" in errors[0]["error"]
    assert summary.get("aborted"), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_trailing_markup_after_the_document_close_is_still_a_refusal(
    tmp_path: Path,
) -> None:
    """`</html>` need not be the final characters to count as complete.

    SharePoint serves trailing markup after the document close, so a page
    that ended cleanly on the probe day now reads as cut short. The closing
    tag marks the document complete; what follows it is post-document, not
    truncation.
    """
    summary, _, _ = _run_view_guard_deploy(
        tmp_path, {"All Items": "editable", "Open": "trailing"},
    )
    assert _refusal_errors(summary) == [], summary.get("errors")
    assert summary.get("aborted") is None, summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_html_close_inside_page_script_is_not_a_confirmation(
    tmp_path: Path,
) -> None:
    """Containing `</html>` is not the same as having closed the document.

    The page carries the literal in its own script, ahead of the editor, and
    is then cut before the controls and before the real close. Accepting the
    literal as proof of a whole document reports a view protected on a page
    whose controls simply never arrived, which is the one wrong answer this
    check exists to prevent.
    """
    summary, read, _ = _run_view_guard_deploy(
        tmp_path, {"All Items": "editable", "Open": "interior"},
    )
    assert read == ["All Items", "Open", "Recent"], read
    errors = _refusal_errors(summary)
    assert [e["view"] for e in errors] == ["Open"], errors
    assert "complete=false" in errors[0]["error"]
    assert summary.get("aborted"), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_redirected_settings_page_is_not_a_confirmation(tmp_path: Path) -> None:
    """A login or modern-settings redirect answers HTTP 200 from elsewhere.

    The page never arrived, so nothing is missing from it. This was a warning
    once, which left the deployment reporting clean.
    """
    summary, _, _ = _run_view_guard_deploy(
        tmp_path, {"All Items": "editable", "Open": "redirect"},
    )
    errors = _refusal_errors(summary)
    assert [e["view"] for e in errors] == ["Open"], errors
    assert "redirected=true" in errors[0]["error"]
    assert summary.get("aborted"), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_control_markers_missing_from_an_editable_view_stop_the_check(
    tmp_path: Path,
) -> None:
    """A tenant that renamed both controls would read as every view protected.

    The sentinel is still on the page and the control names are not, which is
    indistinguishable from protection unless something known to be editable
    is asked the same question. So the unfiltered view is read first, and its
    answer decides whether an absence means anything at all.
    """
    summary, read, _ = _run_view_guard_deploy(tmp_path, {"All Items": "drifted"})
    assert read == ["All Items"], read
    errors = _refusal_errors(summary)
    assert [e["view"] for e in errors] == ["All Items"], errors
    assert "marker drift" in errors[0]["error"]
    assert summary.get("aborted"), summary


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_a_same_titled_replacement_stops_the_guard_confirmation(
    tmp_path: Path,
) -> None:
    """The confirmation resolves each list by title, long after the lane.

    #305 brackets the view-write lane: the title is proved to resolve to the
    Id the survey captured before the first write and again after the last.
    The guard confirmation runs after every lane has closed, and it resolves
    the title again to build the settings-page URL. A same-titled list that
    replaced the owned one in between answers that read, so its settings page
    would be read and reported on under the owned list's name. Nothing
    downstream can see that the wrong list was asked, which is the whole
    reason this check exists.
    """
    summary, read, output = _run_view_guard_deploy(
        tmp_path, {"All Items": "editable"},
        settings_list_id=_REPLACEMENT_LIST_ID,
    )
    assert read == [], f"a replaced list's settings page was read: {read}"
    errors = _refusal_errors(summary)
    assert len(errors) == 1, errors
    assert "changed identity before the filter editor was read" in errors[0]["error"]
    assert _REPLACEMENT_LIST_ID in errors[0]["error"]
    assert summary.get("aborted"), summary
    assert "refuses 2 of 2 declared filter(s)" not in output
