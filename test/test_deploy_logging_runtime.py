# test/test_deploy_logging_runtime.py
"""Execute the generated deploy.js with its SIDECARS ON, against a mock site.

The committed golden is built with `--no-sidecars`, so until this module
existed no test ever ran phase 1.7's JavaScript. Four separate defects
shipped green through that hole in one branch: a flag that never reached the
build, a `$filter` on a column the script does not create, logging failures
pushed onto the abort bus every later phase gates on, and a two-argument
writer published under a name every caller invokes with one argument.

Each is a runtime fact, so each is pinned by running the script rather than
by reading it. `node --check` would have caught none of them.

Node is required; the tests skip without it rather than failing.
"""

import json
import textwrap
from typing import Any

import pytest
from _batch_mock import BATCH_MOCK
from _model import bundle as make_bundle
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE
from _node import run_node as _run
from _paths import FIXTURES

from dbml_sharepoint.analysis.sidecars import (
    CENTRAL_LOG_COLUMNS,
    CENTRAL_LOG_SITE_DEFAULT,
    CHANGE_FIELDS,
    CHANGE_LOG_TITLE,
    EXTERNAL_LOG_DEFAULT,
    RUN_LOG_STAMP_COLUMNS,
    RUN_LOG_TITLE,
    change_log_marker,
    run_log_marker,
)
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.release import load_release

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

#: A change key the mock's change log already holds a CURRENT row for, so the
#: type-2 close has something to close. Spelled exactly as `_lists.js.j2`
#: spells the key it raises for a list it created.
SEEDED_KEY = "list: APP_Risk"

_HARNESS = textwrap.dedent(r"""
    const FAIL_CHANGE_ITEM_WRITES = false;
    const FAIL_RUN_LOG_FIELD_CREATES = false;
    const SEED_ITEMS = {};
    const SEED_LISTS = [];
    // The columns the central list carries. Empty models a list the operator
    // pointed DBMLSP_DEPLOY_LOG_LIST at that this tool never provisioned.
    const CENTRAL_FIELDS = CENTRAL_FIELD_NAMES;
    const calls = [];
    const unhandled = [];
    // The one assertion this harness exists to make possible: _lists.js.j2
    // calls logChange WITHOUT awaiting it, so a writer that rejects surfaces
    // here and nowhere else. Node prints these and exits non-zero on some
    // versions and not others, so they are collected and asserted on.
    process.on('unhandledRejection', (err) => {
      unhandled.push(String((err && err.stack) || err));
    });
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const state = {
      lists: {},                  // Title -> the stored list shape
      fields: {},                 // list Title -> [ { Id, InternalName, Indexed } ]
      items: { ...SEED_ITEMS },   // list Title -> [ row ]
      central: [],                // rows POSTed to the cross-web deployment log
      nextList: 1,
      nextField: 1,
      nextItem: 1,
    };
    const guid = (prefix, n) => `${prefix}-0000-0000-0000-${String(n).padStart(12, '0')}`;
    // Settings are STORED and echoed rather than answered with constants: the
    // deploy reads every list back and aborts wave 1 on a setting it declared
    // and did not get, so a mock that forgets its own writes fails the run for
    // a reason that has nothing to do with logging.
    const SHAPE_DEFAULTS = {
      BaseTemplate: 100, ContentTypesEnabled: false, Description: '',
      EnableVersioning: false, EnableMinorVersions: false, MajorVersionLimit: 0,
      ValidationFormula: null, ValidationMessage: null, Hidden: false,
      NoCrawl: false, EnableAttachments: true, ItemCount: 0,
      HasUniqueRoleAssignments: false,
    };
    const shapeOf = (l) => ({ ...SHAPE_DEFAULTS, ...l });
    // Every list SharePoint creates already has these, so a mock whose new
    // list has no columns at all reports the declared Title as missing after
    // creation and aborts wave 1 before phase 1.7's writes can be read.
    const BUILT_INS = ['Title', 'ID', 'Created', 'Modified', 'Author', 'Editor'];
    const FIELD_DEFAULTS = {
      TypeAsString: 'Text', Description: '', Required: false,
      EnforceUniqueValues: false, Indexed: false, ReadOnlyField: false,
      Sealed: false, DefaultValue: null, CustomFormatter: '', Hidden: false,
      ValidationFormula: null, ValidationMessage: '',
      ClientValidationFormula: null, ClientValidationMessage: '',
    };
    const newField = (body) => {
      const { __metadata, ...rest } = body;
      // `SP.FieldText` -> `Text`, which is what TypeAsString reads back as.
      // Taken from the declaration rather than assumed, so a field created
      // without a type name is visible here as one.
      const typed = __metadata && typeof __metadata.type === 'string'
        ? { TypeAsString: __metadata.type.replace(/^SP\.Field/, '') } : {};
      return { ...FIELD_DEFAULTS, ...typed, ...rest,
        Id: guid('eeeeeeee', state.nextField++), InternalName: rest.Title };
    };
    const reply = (status, payload) => ({
      ok: status < 400, status, headers: { get: () => null },
      json: async () => payload, text: async () => JSON.stringify(payload),
    });
    const notFound = () => reply(404, { error: { message: { value: 'not found' } } });
    const digestReply = (value) => reply(200, { d: { GetContextWebInformation: {
      FormDigestValue: value, FormDigestTimeoutSeconds: 1800 } } });
    const badDigest = () => reply(403, { error: { message: { value:
      'The security validation for this page is invalid and might be corrupted. '
      + 'Please use your web browser back button to try your operation again.' } } });
    // contextinfo sits at the API ROOT. Measured live on 2026-09-05: the
    // web-scoped `_api/web/contextinfo` answered 403 with the SAME "security
    // validation ... invalid" sentence a wrong-web digest answers, which is
    // why a wrong URL here reads exactly like the cross-web digest-scope bug.
    // Modelled, because the mock that answered any URL containing the word
    // let the regression through green.
    const digestFor = (u, method, value) => (
      /\/_api\/contextinfo$/.test(u) && method === 'POST'
        ? digestReply(value) : badDigest()
    );
    // Two refusals a real item POST answers with, neither of which a mock
    // that stores whatever body it is handed can ever show. Both measured
    // live on 2026-09-05.
    const itemRefusal = (body, known, type) => {
      if (!body || !body.__metadata || !body.__metadata.type) {
        return reply(400, { error: { message: { value:
          'An entry without a type name was found, but no expected type was specified.' } } });
      }
      const unknown = Object.keys(body).find(
        (k) => k !== '__metadata' && !known.includes(k));
      if (unknown) {
        return reply(400, { error: { message: { value:
          `The property '${unknown}' does not exist on type '${type}'. Make sure to only `
          + 'use property names that are defined by the type.' } } });
      }
      return null;
    };
    // `ChangeKey eq 'X'` out of the close query, so the mock answers the same
    // question the script asked rather than a convenient approximation of it.
    const filteredKey = (rest) => {
      const m = /ChangeKey eq '([^']*)'/.exec(rest);
      return m ? m[1] : null;
    };
    // Lists that already exist when the paste starts, with the built-in
    // columns and NOTHING else. A run log created by the bare-Title version
    // of this phase is exactly this, and it is the state `ensureSidecar`
    // reuses rather than creates.
    for (const seed of SEED_LISTS) {
      const seeded = { ...SHAPE_DEFAULTS, ...seed, Id: guid('bbbbbbbb', state.nextList++) };
      state.lists[seeded.Title] = seeded;
      state.fields[seeded.Title] = BUILT_INS.map(
        (name) => newField({ Title: name, ReadOnlyField: name !== 'Title' }));
      state.items[seeded.Title] = state.items[seeded.Title] || [];
    }
    globalThis.fetch = async (url, opts = {}) => {
      const u = decodeURIComponent(String(url));
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const body = opts.body ? JSON.parse(opts.body) : null;
      calls.push({ url: u, method, headers, body });
      const verb = headers['X-HTTP-Method'] || method;

      // ---- the CENTRAL logging site, addressed cross-web ------------------
      if (u.includes('/sites/CENTRAL_SITE/')) {
        if (u.includes('contextinfo')) return digestFor(u, method, 'central-digest');
        if (u.toLowerCase().includes('effectivebasepermissions')) {
          return reply(200, { d: { EffectiveBasePermissions: { High: 0, Low: 2 } } });
        }
        if (/_api\/web\/\?\$select=Url$/.test(u)) {
          return reply(200, { d: { Url: 'https://example.sharepoint.com/sites/CENTRAL_SITE' } });
        }
        const centralByTitle = /lists\/getbytitle\('CENTRAL_LIST'\)\?\$select=(.*)$/.exec(u);
        if (centralByTitle && centralByTitle[1] === 'Id,ListItemEntityTypeFullName') {
          return reply(200, { d: {
            Id: guid('dddddddd', 1), ListItemEntityTypeFullName: CENTRAL_ITEM_TYPE } });
        }
        if (/lists\/getbytitle\('CENTRAL_LIST'\)\/fields/.test(u)) {
          return reply(200, { d: { results:
            ['Title'].concat(CENTRAL_FIELDS).map((n) => ({ InternalName: n })) } });
        }
        if (method === 'POST' && /\/items$/.test(u)) {
          // A digest is scoped to the web that ISSUED it, so the host web's
          // is refused here exactly as SharePoint refused it live.
          if (headers['X-RequestDigest'] !== 'central-digest') return badDigest();
          const bad = itemRefusal(body, ['Title'].concat(CENTRAL_FIELDS), CENTRAL_ITEM_TYPE);
          if (bad) return bad;
          state.central.push(body);
          return reply(201, { d: { Id: state.nextItem++ } });
        }
        return reply(200, { d: { results: [] } });
      }

      if (u.includes('contextinfo')) return digestFor(u, method, 'local-digest');
      if (u.toLowerCase().includes('effectivebasepermissions')) {
        const all = { High: 4294967295, Low: 4294967295 };
        return reply(200, { d: { EffectiveBasePermissions: all } });
      }
      if (/web\/lists\?\$select=Title/.test(u)) {
        const rows = Object.values(state.lists)
          .map((l) => ({ Title: l.Title, ItemCount: 0, Hidden: false }));
        return reply(200, { d: { results: rows } });
      }
      if (method === 'POST' && /\/_api\/web\/lists$/.test(u) && body && body.Title) {
        const { __metadata, ...settings } = body;
        const created = { ...SHAPE_DEFAULTS, ...settings,
          Id: guid('bbbbbbbb', state.nextList++) };
        state.lists[created.Title] = created;
        state.fields[created.Title] = BUILT_INS.map(
          (name) => newField({ Title: name, ReadOnlyField: name !== 'Title' }));
        state.items[created.Title] = state.items[created.Title] || [];
        return reply(201, { d: shapeOf(created) });
      }
      // A field MERGE addresses the field by GUID, so the Indexed assertion
      // has to be found by id rather than by the list path.
      const fieldById = /web\/lists\(guid'([^']+)'\)\/fields\(guid'([^']+)'\)/.exec(u);
      if (fieldById && verb === 'MERGE') {
        for (const rows of Object.values(state.fields)) {
          const field = rows.find((f) => f.Id === fieldById[2]);
          if (field) Object.assign(field, body || {});
        }
        return reply(204, {});
      }

      const byTitle = /web\/lists\/getbytitle\('([^']+)'\)(.*)$/.exec(u);
      if (byTitle) {
        const title = byTitle[1];
        const rest = byTitle[2];
        const list = state.lists[title] || null;
        if (!list) return notFound();
        if (rest.startsWith('?$select=ListItemEntityTypeFullName')) {
          return reply(200, { d: {
            ListItemEntityTypeFullName: `SP.Data.${title.replace(/\W/g, '')}ListItem`,
          } });
        }
        if (rest.startsWith('/fields')) {
          state.fields[title] = state.fields[title] || [];
          const named = /^\/fields\/getbyinternalnameortitle\('([^']+)'\)/.exec(rest);
          if (named) {
            const field = state.fields[title].find(
              (f) => f.InternalName === named[1] || f.Title === named[1]);
            if (!field) return notFound();
            if (verb === 'MERGE') {
              const { __metadata, ...settings } = body || {};
              Object.assign(field, settings);
              return reply(204, {});
            }
            return reply(200, { d: field });
          }
          if (method === 'POST' && body && body.Title) {
            if (FAIL_RUN_LOG_FIELD_CREATES && title === 'RUN_LOG_LIST') {
              return reply(400, { error: { message: { value:
                'the site column could not be added' } } });
            }
            state.fields[title].push(newField(body));
            return reply(201, { d: {} });
          }
          return reply(200, { d: { results: state.fields[title] } });
        }
        if (rest.startsWith('/items')) {
          state.items[title] = state.items[title] || [];
          const itemById = /\/items\((\d+)\)/.exec(rest);
          if (itemById && verb === 'MERGE') {
            const row = state.items[title].find((r) => r.Id === Number(itemById[1]));
            if (row) Object.assign(row, body || {});
            return reply(204, {});
          }
          if (method === 'POST') {
            if (FAIL_CHANGE_ITEM_WRITES && title === 'CHANGE_LIST') {
              return reply(500, { error: { message: { value: 'change log is refusing writes' } } });
            }
            // The list's OWN columns decide what the row may name. A run log
            // reused from the bare-Title version has only the built-ins, and
            // a stamp naming StampKind against it is refused, which is the
            // 400 the live run collected.
            const bad = itemRefusal(
              body, state.fields[title].map((f) => f.InternalName),
              `SP.Data.${title.replace(/\W/g, '')}ListItem`);
            if (bad) return bad;
            const row = { Id: state.nextItem++, ...(body || {}) };
            state.items[title].push(row);
            return reply(201, { d: row });
          }
          const key = filteredKey(rest);
          const rows = state.items[title].filter(
            (r) => (key === null || r.ChangeKey === key) && r.IsCurrent === true,
          );
          return reply(200, { d: { results: rows } });
        }
        if (verb === 'MERGE') {
          const { __metadata, ...settings } = body || {};
          Object.assign(list, settings);
          return reply(204, {});
        }
        if (rest.startsWith('/')) return reply(200, { d: { results: [] } });
        return reply(200, { d: shapeOf(list) });
      }
      return reply(200, { d: { results: [] } });
    };
""") + BATCH_MOCK


def _deploy_js() -> str:
    """A one-list deploy with both sidecars on and a central log named."""
    schema = make_schema(make_table("Risk", "Title", note="Risks."))
    bundle = make_bundle(entities=["Risk"])
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test", site_role="default",
        source_dbml="x.dbml", source_mtime="2026-09-05T00:00:00Z",
        generated_at="2026-09-05T00:00:00Z",
        sidecar_run_log_title=RUN_LOG_TITLE,
        sidecar_run_log_marker=run_log_marker(),
        sidecar_run_log_fields=list(RUN_LOG_STAMP_COLUMNS),
        sidecar_change_log_title=CHANGE_LOG_TITLE,
        sidecar_change_log_marker=change_log_marker(),
        sidecar_change_fields=list(CHANGE_FIELDS),
        deployment_log_list=EXTERNAL_LOG_DEFAULT,
        deployment_log_site=CENTRAL_LOG_SITE_DEFAULT,
    )
    # The assessment is a whole second script's worth of probes and is not
    # what these runs are about; the renames harness stubs it the same way.
    stubbed = js.replace(
        "    assessment = await assessSite({",
        "    assessment = { findings: [], verdict: 'COMPATIBLE' };\n"
        "    if (false) await assessSite({",
        1,
    )
    assert stubbed != js
    return stubbed


def _substitute(harness: str, old: str, new: str) -> str:
    """`str.replace`, but a placeholder that stopped matching is a failure.

    The harness is dedented, so a target copied from the source with its
    indentation silently matches nothing, and a mock that quietly ignored
    half its configuration still passes the assertions it no longer sets up.
    """
    assert harness.count(old) == 1, f"{old!r} appears {harness.count(old)} times"
    return harness.replace(old, new, 1)


def _run_deploy(
    *,
    seeded_change_rows: bool = False,
    fail_change_writes: bool = False,
    bare_run_log: bool = False,
    fail_run_log_field_creates: bool = False,
    central_columns: bool = True,
) -> dict[str, Any]:
    harness = _HARNESS
    # Substituted BEFORE the placeholder titles, because the entity type is
    # spelled from the list title and would otherwise be rewritten twice.
    central_names = json.dumps(list(CENTRAL_LOG_COLUMNS) if central_columns else [])
    harness = _substitute(
        harness, "const CENTRAL_FIELDS = CENTRAL_FIELD_NAMES;",
        f"const CENTRAL_FIELDS = {central_names};",
    )
    assert harness.count("CENTRAL_ITEM_TYPE") == 2
    harness = harness.replace(
        "CENTRAL_ITEM_TYPE",
        json.dumps(f"SP.Data.{EXTERNAL_LOG_DEFAULT.replace('-', '')}ListItem"),
    )
    for placeholder, actual in (
        ("CENTRAL_SITE", CENTRAL_LOG_SITE_DEFAULT),
        ("CENTRAL_LIST", EXTERNAL_LOG_DEFAULT),
        ("CHANGE_LIST", CHANGE_LOG_TITLE),
        ("RUN_LOG_LIST", RUN_LOG_TITLE),
    ):
        assert placeholder in harness
        harness = harness.replace(placeholder, actual)
    if fail_change_writes:
        harness = _substitute(
            harness, "const FAIL_CHANGE_ITEM_WRITES = false;",
            "const FAIL_CHANGE_ITEM_WRITES = true;",
        )
    if fail_run_log_field_creates:
        harness = _substitute(
            harness, "const FAIL_RUN_LOG_FIELD_CREATES = false;",
            "const FAIL_RUN_LOG_FIELD_CREATES = true;",
        )
    if bare_run_log:
        # The run log as the OLD bare-Title code left it on a live site:
        # marker-matched so it is reused, and carrying no stamp columns.
        seeded_lists = json.dumps([
            {"Title": RUN_LOG_TITLE, "Description": run_log_marker(), "Hidden": True},
        ])
        harness = _substitute(
            harness, "const SEED_LISTS = [];", f"const SEED_LISTS = {seeded_lists};",
        )
    if seeded_change_rows:
        seeded = json.dumps({CHANGE_LOG_TITLE: [{
            "Id": 900, "Title": SEEDED_KEY, "ChangeKey": SEEDED_KEY,
            "ChangeKind": "create", "IsCurrent": True,
        }]})
        harness = _substitute(
            harness, "const SEED_ITEMS = {};", f"const SEED_ITEMS = {seeded};",
        )
    body = _deploy_js().rstrip()
    assert body.endswith("})();")
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(calls));\n"
        "  console.log('__STATE__' + JSON.stringify(state));\n"
        "  console.log('__UNHANDLED__' + JSON.stringify(unhandled));\n"
        "});\n"
    )
    output = _run(script)
    markers = ("__RESULT__", "__CALLS__", "__STATE__", "__UNHANDLED__")
    lines = output.splitlines()
    found = {m: next((ln for ln in lines if ln.startswith(m)), None) for m in markers}
    missing = [m for m, ln in found.items() if ln is None]
    assert not missing, f"deploy.js never reached {missing}:\n{output[-6000:]}"
    summary, calls, state, unhandled = (
        json.loads((found[m] or "").removeprefix(m)) for m in markers
    )
    return {
        "summary": summary, "calls": calls, "state": state,
        "unhandled": unhandled, "output": output,
    }


def _posts_to(calls: list[dict[str, Any]], title: str) -> list[dict[str, Any]]:
    return [
        c for c in calls
        if c["method"] == "POST"
        and c["headers"].get("X-HTTP-Method") is None
        and c["url"].endswith(f"getbytitle('{title}')/items")
    ]


@pytest.fixture(scope="module")
def accepting_run() -> dict[str, Any]:
    """One run whose change log takes every write. The control."""
    return _run_deploy(seeded_change_rows=True)


@pytest.fixture(scope="module")
def refusing_run() -> dict[str, Any]:
    """The same run with the change log refusing every item POST."""
    return _run_deploy(seeded_change_rows=True, fail_change_writes=True)


def test_the_logging_phase_stamps_writes_and_closes_against_a_live_script(
    accepting_run: dict[str, Any],
) -> None:
    """One sidecar-enabled run, and every claim phase 1.7 makes about it.

    Written as ONE run asserted many ways rather than as several runs: the
    facts are all about the same execution, and re-running the whole deploy
    per assertion would pay another Node start for each.
    """
    run = accepting_run
    calls, state, summary = run["calls"], run["state"], run["summary"]

    assert run["unhandled"] == [], (
        "the logging writer rejected out of an un-awaited call:\n"
        + "\n".join(run["unhandled"])
    )

    # The change log's own columns, including the one the close query filters
    # on. Absent, every close read is an HTTP 400 and the insert after it
    # never runs, which is how a change log came to be created and stay empty.
    created = {f["InternalName"] for f in state["fields"][CHANGE_LOG_TITLE]}
    assert {field["Title"] for field in CHANGE_FIELDS} <= created
    assert "ChangeKey" in created

    # Both sides of the close query's AND are asserted indexed, by MERGE,
    # because a create body's handling of `Indexed` has never been measured
    # here and a REUSED log would never see one either way.
    indexed = {f["InternalName"] for f in state["fields"][CHANGE_LOG_TITLE] if f["Indexed"]}
    assert indexed == {"ChangeKey", "IsCurrent"}

    # The field probe is paged. Unfiltered `/fields` reads take the server's
    # page size, and a truncated field map reads as a list missing columns.
    field_reads = [
        c for c in calls
        if c["method"] == "GET" and f"getbytitle('{CHANGE_LOG_TITLE}')/fields" in c["url"]
    ]
    assert field_reads, "the change log's fields were never enumerated"
    assert all("$top=500" in c["url"] for c in field_reads)

    # The type-2 close, keyed on ChangeKey and not on Title.
    closes = [c for c in calls if "ChangeKey eq" in c["url"]]
    assert closes, "no close query was issued; the writer never reached the insert"
    assert all("IsCurrent eq true" in c["url"] for c in closes)
    seeded = next(r for r in state["items"][CHANGE_LOG_TITLE] if r["Id"] == 900)
    assert seeded["IsCurrent"] is False, "the seeded current row was never closed"
    assert seeded["EffectiveTo"], "the closed row carries no EffectiveTo"

    # The change row itself: one argument in, both key columns out.
    inserted = [r for r in state["items"][CHANGE_LOG_TITLE] if r["Id"] != 900]
    assert inserted, "no change row was inserted"
    assert all(r["ChangeKey"] == r["Title"] for r in inserted)
    assert any(r["ChangeKey"] == SEEDED_KEY for r in inserted)
    assert all(r["IsCurrent"] is True and r["EffectiveTo"] is None for r in inserted)

    # The run log's own stamp columns, created on the list this run made.
    # The create body is BaseTemplate 100 plus a Description, so a run log
    # that is never given these has only Title, and every structured stamp
    # against it is refused.
    run_log_fields = {f["InternalName"] for f in state["fields"][RUN_LOG_TITLE]}
    assert {f["Title"] for f in RUN_LOG_STAMP_COLUMNS} <= run_log_fields

    # Both run-log stamps, each carrying a real entity type: a typeless item
    # POST is refused outright, and the stop stamp is written from the exit
    # path in deploy.js.j2 long after this phase returned, which is where a
    # `const` scoped to the start stamp's own try became a ReferenceError.
    stamps = _posts_to(calls, RUN_LOG_TITLE)
    kinds = [c["body"]["StampKind"] for c in stamps]
    assert len(kinds) == 2, f"expected a start stamp and an exit stamp, got {kinds}"
    assert kinds[0] == "deployment start"
    # The mock is deliberately thin (test_deploy_runtime.py says the same),
    # so later phases legitimately record errors and the exit stamp names the
    # exit it saw. Which of the two it is follows from summary.errors.
    assert kinds[1] == ("abort" if summary["errors"] else "deployment stop")
    assert all(c["body"]["__metadata"]["type"].startswith("SP.Data.") for c in stamps)
    assert all(len(c["body"]["Title"]) <= 255 for c in stamps)
    # Every column the stamp names is one the list carries, which is the
    # check the live 400 came from the absence of.
    assert all(
        set(c["body"]) - {"__metadata"} <= run_log_fields for c in stamps
    ), [sorted(set(c["body"]) - {"__metadata"} - run_log_fields) for c in stamps]

    # The central log's rows, in full: the family declares every stamp column
    # so the field probe finds them all and the row is structured.
    central = state["central"]
    titles = [row["Title"] for row in central]
    assert any(t.startswith("dbml-sharepoint deployment start:") for t in titles)
    assert any(t.startswith("dbml-sharepoint provenance:") for t in titles)
    assert any(t.startswith(f"dbml-sharepoint {kinds[1]}:") for t in titles)
    assert all(len(t) <= 255 for t in titles)
    assert all(row["__metadata"]["type"].startswith("SP.Data.") for row in central)
    assert all(set(CENTRAL_LOG_COLUMNS) <= set(row) for row in central), (
        f"a central row was written without its stamp columns: {central}"
    )
    assert {row["StampKind"] for row in central} == {
        "deployment start", "provenance", kinds[1],
    }
    assert all(row["SourceSite"] == "https://example.sharepoint.com/sites/test" for row in central)

    assert summary["loggingFailures"] == []
    # Nothing phase 1.7 did reached the abort bus.
    assert not [e for e in summary["errors"] if str(e.get("phase")) == "1.7"]


def test_a_change_log_that_refuses_every_write_changes_nothing_but_the_log(
    accepting_run: dict[str, Any], refusing_run: dict[str, Any],
) -> None:
    """The contract phase 1.7 states, pinned against the code that broke it.

    `recordFailure` used to push onto `summary.errors`, which every phase
    gate from 2.1 onward reads: a change row SharePoint would not accept
    aborted the whole deployment, one phase after the logging phase had
    finished saying that logging failures never halt a run. The registers
    must not depend on the logs that document them.

    Asserted as a DIFFERENCE against the accepting run rather than as
    `aborted: null`, because the mock is thin enough that the run reaches a
    schema-shape wall either way. The claim is the one that matters and the
    stronger of the two: refusing every change row moves nothing except the
    logging-failure list.
    """
    summary = refusing_run["summary"]
    control = accepting_run["summary"]

    assert refusing_run["unhandled"] == [], "\n".join(refusing_run["unhandled"])
    assert summary.get("aborted") == control.get("aborted"), (
        f"a refused change row changed how the deploy ended: "
        f"{control.get('aborted')} -> {summary.get('aborted')}"
    )
    assert summary["errors"] == control["errors"], (
        f"a logging failure reached the abort bus: {summary['errors']}"
    )
    assert not any(
        "refusing writes" in json.dumps(e) for e in summary["errors"]
    ), summary["errors"]

    assert summary["loggingFailures"], "the refusals were recorded nowhere"
    assert all(
        "refusing writes" in json.dumps(f) for f in summary["loggingFailures"]
    ), summary["loggingFailures"]
    # Counted once, out loud, because nothing later in the run mentions them.
    assert "logging operation(s)" in refusing_run["output"]


@pytest.fixture(scope="module")
def reused_bare_run_log() -> dict[str, Any]:
    """A run log the OLD bare-Title code left behind: reused, no columns."""
    return _run_deploy(bare_run_log=True)


def test_a_reused_run_log_is_given_the_stamp_columns_it_never_had(
    reused_bare_run_log: dict[str, Any],
) -> None:
    """The live 400, and the fix for it.

    `ensureSidecar` REUSES a marker-matched list, so a run log created by the
    version of this phase that wrote nothing but Title survives every later
    deploy with nothing but Title. The stamp then named StampKind and was
    refused with HTTP 400 "The property 'StampKind' does not exist on type
    'SP.Data.Dbml_x0020_Local_x0020_LogListItem'" (live 2026-09-05), losing
    the row entirely.

    A fresh create was in the same state: the create body is BaseTemplate 100
    and a Description, so it never carried the columns either.
    """
    run = reused_bare_run_log
    state, summary, calls = run["state"], run["summary"], run["calls"]

    assert run["unhandled"] == [], "\n".join(run["unhandled"])
    assert "exists (marker matched); reusing it" in run["output"], (
        "the seeded run log was created rather than reused, so this run never "
        "exercised the path the live failure came from"
    )

    present = {f["InternalName"] for f in state["fields"][RUN_LOG_TITLE]}
    assert {f["Title"] for f in RUN_LOG_STAMP_COLUMNS} <= present, (
        f"the reused run log was left without its stamp columns: {sorted(present)}"
    )

    stamps = _posts_to(calls, RUN_LOG_TITLE)
    assert len(stamps) == 2, f"expected two stamps, got {len(stamps)}"
    assert all(s["body"].get("StampKind") for s in stamps), (
        "the stamps degraded to Title only against a log whose columns were created"
    )
    assert all(len(state["items"][RUN_LOG_TITLE]) == 2 for _ in [0]), (
        f"a stamp was refused: {state['items'][RUN_LOG_TITLE]}"
    )
    assert not [
        f for f in summary["loggingFailures"] if RUN_LOG_TITLE in json.dumps(f)
    ], summary["loggingFailures"]


def test_a_run_log_whose_columns_cannot_be_created_still_gets_its_stamps() -> None:
    """The degrade path: Title alone, one recorded failure, no abort.

    A column create can be refused for reasons this tool does not control (a
    site column of that name, a locked list). Losing the stamp entirely would
    mean a run that happened is recorded nowhere, so the row is written
    without the structured half instead.
    """
    run = _run_deploy(bare_run_log=True, fail_run_log_field_creates=True)
    state, summary, calls = run["state"], run["summary"], run["calls"]

    assert run["unhandled"] == [], "\n".join(run["unhandled"])

    stamps = _posts_to(calls, RUN_LOG_TITLE)
    assert len(stamps) == 2, f"expected two stamps, got {len(stamps)}"
    assert all(set(s["body"]) == {"__metadata", "Title"} for s in stamps), (
        f"a stamp named a column the list does not have: {[s['body'] for s in stamps]}"
    )
    rows = state["items"][RUN_LOG_TITLE]
    assert len(rows) == 2, f"a Title-only stamp was still refused: {rows}"

    # Recorded, once, and NOT on the abort bus.
    failures = [
        f for f in summary["loggingFailures"]
        if f["where"] == f"stamp columns on '{RUN_LOG_TITLE}'"
    ]
    assert len(failures) == 1, summary["loggingFailures"]
    assert not [e for e in summary["errors"] if str(e.get("phase")) == "1.7"]
    assert "carry Title only" in run["output"]


def test_the_central_digest_is_the_central_web_s_own(
    accepting_run: dict[str, Any],
) -> None:
    """Where the cross-web digest comes from, and where it goes.

    Two separate facts, and confusing them is how this broke twice:

    - the contextinfo POST goes to the CENTRAL site, because a digest is
      scoped to the web that issued it and the host web's answered 403
      against the logging site (live 2026-09-05);
    - it goes to `_api/contextinfo`, the API ROOT. The web-scoped
      `_api/web/contextinfo` answered 403 with the SAME sentence, and that is
      what `externalApi('contextinfo')` addressed; the identical error text is
      why it read as the scope bug rather than as a wrong URL.
    """
    calls = accepting_run["calls"]
    central_root = f"/sites/{CENTRAL_LOG_SITE_DEFAULT}"

    digest_calls = [c for c in calls if "contextinfo" in c["url"]]
    assert digest_calls, "no digest was ever fetched"

    central_digests = [c for c in digest_calls if central_root in c["url"]]
    assert central_digests, "the central site's own digest was never fetched"
    for call in central_digests:
        assert call["method"] == "POST"
        assert call["url"].endswith("/_api/contextinfo"), (
            f"the central digest was fetched from {call['url']!r}; contextinfo "
            "sits at the API root, not under web scope"
        )

    # And the host web's digest never leaves the host web.
    host_digest_sent_central = [
        c for c in calls
        if central_root in c["url"] and c["headers"].get("X-RequestDigest") == "local-digest"
    ]
    assert not host_digest_sent_central, (
        f"a host-web digest was sent to the central site: {host_digest_sent_central}"
    )

    central_writes = [
        c for c in calls if central_root in c["url"] and c["method"] == "POST"
        and c["url"].endswith("/items")
    ]
    assert central_writes, "nothing was ever written to the central log"
    assert all(
        c["headers"]["X-RequestDigest"] == "central-digest" for c in central_writes
    )


def test_a_central_log_without_the_stamp_columns_takes_a_title_only_row() -> None:
    """`DBMLSP_DEPLOY_LOG_LIST` can name a list this tool never provisioned.

    The field probe finds the columns missing and every stamp degrades to
    Title, which is the one column a generic SharePoint list always has. The
    rows still arrive; nothing is recorded as a failure.
    """
    run = _run_deploy(central_columns=False)
    assert run["unhandled"] == [], "\n".join(run["unhandled"])

    central = run["state"]["central"]
    assert central, "the degraded stamps never reached the central log"
    assert all(set(row) == {"__metadata", "Title"} for row in central), (
        f"a stamp named a column the list does not carry: {central}"
    )
    assert "Title only" in run["output"]
    assert not [
        f for f in run["summary"]["loggingFailures"]
        if EXTERNAL_LOG_DEFAULT in json.dumps(f)
    ], run["summary"]["loggingFailures"]
