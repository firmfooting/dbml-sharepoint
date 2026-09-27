# test/test_last_binding_probe_runtime.py
"""Execute `last-binding-removal-probe.js` against a mock SharePoint.

The probe removes the last role assignment on a list, which is the request a
`reconcile: exact` policy with no assignments sends (#667), and then records
what the scope reports. Its rows split into what the measurement depends on
(the list, the break, the one binding the break leaves) and what it observes
(the removal's answer, the deploy's own read-back, the enumeration, the flag,
the closing delete). The tests hold it to that split: a failed dependency
voids the rows after it, and an observation is recorded whichever way it
came out, including the ways that would break the deploy.

Every mock body here is SYNTHETIC unless a comment cites a live run. No live
run has yet recorded what SharePoint answers to this removal, which is the
point of the probe.
"""

import json
import re
import textwrap
from typing import Any

import pytest
from _node import NODE
from _node import run_node as _run
from _paths import JINJA_TEMPLATES, MANUAL

PROBE = MANUAL / "last-binding-removal-probe.js"

FIXTURE_LIST = "access.list-acl.fixture-last-binding-list"
FIXTURE_BREAK = "access.list-acl.fixture-last-binding-break"
FIXTURE_SOLE = "access.list-acl.fixture-last-binding-sole-operator"
REMOVAL = "access.list-acl.last-binding-removal"
READBACK = "access.list-acl.after-last-binding-readback"
ENUMERATION = "access.list-acl.after-last-binding-enumeration"
UNIQUE = "access.list-acl.after-last-binding-unique"
DELETE = "access.list-acl.after-last-binding-delete"

#: The five rows that observe the scope once the removal was sent.
OBSERVED = (REMOVAL, READBACK, ENUMERATION, UNIQUE, DELETE)
ALL = (FIXTURE_LIST, FIXTURE_BREAK, FIXTURE_SOLE, *OBSERVED)

_TITLE = "dbmlsp Probe LastBinding"
_OWNERSHIP = "dbml-sharepoint last-binding-removal probe list. Safe to delete."
_CREATED_ID = "22222222-2222-2222-2222-222222222222"
_LEFTOVER_ID = "11111111-1111-1111-1111-111111111111"
_REBOUND_ID = "33333333-3333-3333-3333-333333333333"
_OPERATOR = 11

#: What the break leaves, as MEASURED 2026-09-22 by operator-safety-grant-probe.js
#: on two sites: one binding, this account's own USER binding at Full Control.
#: The title must not reach the transcript, so it collides with nothing printed.
_OPERATOR_BINDING = {
    "principalId": _OPERATOR, "title": "Wilhelmina Torres",
    "principalType": 1, "levelId": 3, "levelName": "Full Control",
}

_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.__calls = [];
    process.on('exit', () => {
      console.log('__CALLS__' + JSON.stringify(globalThis.__calls));
    });

    globalThis.window = {
      _spPageContextInfo: { webAbsoluteUrl: 'https://example.sharepoint.com/sites/test' },
    };

    const respond = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    const spError = (status, code, value) => respond(status, {
      'odata.error': { code, message: { lang: 'en-US', value } },
    });
    // The text _sp_mock.ABSENT cites for a list title that does not exist.
    const absent = () => spError(404, '-1, System.ArgumentException',
      `List '${CONFIG.title}' does not exist at site with URL `
      + "'https://example.sharepoint.com/sites/test'.");
    const denied = () => spError(403, '-2147024891, System.UnauthorizedAccessException',
      'Access denied.');

    const occupied = CONFIG.titleOccupied === 'foreign' || CONFIG.titleOccupied === 'leftover';
    const site = {
      listExists: occupied,
      listId: occupied ? CONFIG.leftoverId : null,
      description: CONFIG.titleOccupied === 'foreign' ? 'Quarterly board packs' : CONFIG.ownership,
      unique: false,
      bindings: [],
      removed: null,
      removalSent: false,
      probeReads: 0,
      deployReads: 0,
    };

    const TITLE = `getbytitle('${CONFIG.title}')`;
    const REMOVE = /removeroleassignment\\(principalid=(\\d+),roleDefId=(\\d+)\\)/;

    // One entity per principal carrying every level it holds, in either envelope.
    const entities = (visible, verbose) => {
      const byPrincipal = new Map();
      for (const b of visible) {
        if (!byPrincipal.has(b.principalId)) {
          byPrincipal.set(b.principalId, {
            PrincipalId: b.principalId,
            Member: { Id: b.principalId, Title: b.title, PrincipalType: b.principalType },
            levels: [],
          });
        }
        byPrincipal.get(b.principalId).levels.push({ Id: b.levelId, Name: b.levelName });
      }
      return [...byPrincipal.values()].map(({ levels, ...entity }) => ({
        ...entity,
        RoleDefinitionBindings: verbose ? { results: levels } : levels,
      }));
    };

    const enumeration = (u, verbose) => {
      const continued = u.includes('$skiptoken=');
      let visible = site.bindings;
      if (site.removalSent && !continued) {
        if (verbose) site.deployReads += 1; else site.probeReads += 1;
        const reads = verbose ? site.deployReads : site.probeReads;
        const back = verbose ? CONFIG.reappearOnDeployRead : CONFIG.reappearOnProbeRead;
        if (site.removed && back === reads) visible = [...visible, site.removed];
      }
      let rows = entities(visible, verbose);
      if (verbose && CONFIG.deployRowMalformed && site.removalSent && rows.length === 0) {
        rows = [{ RoleDefinitionBindings: { results: [] } }];
      }
      const endless = CONFIG.endlessPages;
      const paged = (CONFIG.paged || endless) && (endless || !continued);
      const page = paged ? rows.slice(0, 1) : continued ? rows.slice(1) : rows;
      const next = paged ? `${u}&$skiptoken=1` : undefined;
      if (verbose) return respond(200, { d: { results: page, ...(next ? { __next: next } : {}) } });
      return respond(200, { value: page, ...(next ? { 'odata.nextLink': next } : {}) });
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      globalThis.__calls.push({
        url: u, method, accept: headers.Accept || null, cache: opts.cache || null,
        tunnel: headers['X-HTTP-Method'] || null,
      });
      if (u.endsWith('/_api/contextinfo')) {
        return respond(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      if (u.includes('/web/currentuser')) {
        if (CONFIG.currentUserRefused) return spError(500, '-1, x', 'refused');
        const me = { Id: CONFIG.operatorPrincipal, Title: 'Wilhelmina Torres' };
        if (CONFIG.siteAdmin !== null) me.IsSiteAdmin = CONFIG.siteAdmin;
        return respond(200, me);
      }
      if (u.endsWith('/web/lists') && method === 'POST') {
        if (CONFIG.createRefused) return spError(500, '-1, x', 'list create refused');
        site.listExists = true;
        site.listId = CONFIG.createdId;
        site.description = JSON.parse(String(opts.body)).Description;
        return respond(201, {
          Title: CONFIG.title, ...(CONFIG.createOmitsId ? {} : { Id: CONFIG.createdId }),
        });
      }

      const hidden = site.removalSent && CONFIG.afterRemoval === 'denied';
      const byId = /\\/web\\/lists\\(guid'([^']*)'\\)/.exec(u);
      if (byId) {
        const mine = site.listExists
          && byId[1].toLowerCase() === String(site.listId).toLowerCase();
        if (method === 'POST' && headers['X-HTTP-Method'] === 'DELETE') {
          if (CONFIG.deleteThrows) throw new Error('mock transport failure on the DELETE');
          if (!mine) return spError(404, '-1, x', 'no such list');
          if (CONFIG.deleteRefused) return spError(500, '-1, x', 'the list delete was refused');
          site.listExists = false;
          return respond(200, {});
        }
        if (method === 'POST' && u.endsWith('/recycle')) {
          if (!mine) return spError(404, '-1, x', 'no such list');
          site.listExists = false;
          return respond(200, {});
        }
        if (u.includes('/items?')) return respond(200, { value: [] });
        if (!mine) return spError(404, '-1, x', 'no such list');
        if (hidden) return denied();
        return respond(200, {
          Id: site.listId, Title: CONFIG.title, Description: site.description,
        });
      }

      if (!u.includes(TITLE)) return spError(404, '-1, x', `unmocked ${u}`);
      if (CONFIG.titleOccupied === 'unreadable') return spError(500, '-1, x', 'list read refused');
      if (!site.listExists) return absent();

      if (method === 'POST') {
        if (u.includes('/breakroleinheritance(')) {
          if (CONFIG.breakRefused) return spError(500, '-1, x', 'breakroleinheritance refused');
          site.unique = !CONFIG.uniqueNeverTrue;
          site.bindings = CONFIG.leftBindings.map((b) => ({ ...b }));
          return respond(200, { 'odata.null': true });
        }
        const removal = REMOVE.exec(u);
        if (removal) {
          site.removalSent = true;
          const principalId = Number(removal[1]);
          const levelId = Number(removal[2]);
          const take = () => {
            site.removed = site.bindings.find(
              (b) => b.principalId === principalId && b.levelId === levelId) || null;
            site.bindings = site.bindings.filter(
              (b) => !(b.principalId === principalId && b.levelId === levelId));
            if (CONFIG.uniqueAfterRemoval !== null) site.unique = CONFIG.uniqueAfterRemoval;
          };
          const refusal = () => spError(500, '-2146232832, Microsoft.SharePoint.SPException',
            CONFIG.removalMessage);
          switch (CONFIG.removal) {
            case 'accepted': take(); return respond(200, { 'odata.null': true });
            case 'ignored': return respond(200, { 'odata.null': true });
            case 'refused': return refusal();
            case 'refused-but-removed': take(); return refusal();
            case 'throttled': return spError(429, '-1, x', 'throttled');
            default: throw new Error('mock transport failure on the removal');
          }
        }
        return spError(404, '-1, x', `unmocked POST ${u}`);
      }

      if (hidden) return denied();
      if (u.includes('/roleassignments?')) return enumeration(u, u.includes('$select='));
      const listId = site.removalSent && CONFIG.rebindAfterRemoval ? CONFIG.reboundId : site.listId;
      const entity = {
        Id: listId, Title: CONFIG.title, BaseTemplate: 100, ContentTypesEnabled: false,
        Description: site.description, EnableVersioning: false, EnableMinorVersions: false,
        MajorVersionLimit: 0, ValidationFormula: '', ValidationMessage: '',
        HasUniqueRoleAssignments: site.unique,
      };
      if (String(headers.Accept).includes('odata=verbose')) return respond(200, { d: entity });
      return respond(200, entity);
    };
""")

_DEFAULTS: dict[str, Any] = {
    "title": _TITLE,
    "ownership": _OWNERSHIP,
    "createdId": _CREATED_ID,
    "leftoverId": _LEFTOVER_ID,
    "reboundId": _REBOUND_ID,
    "operatorPrincipal": _OPERATOR,
    "siteAdmin": True,
    "currentUserRefused": False,
    "titleOccupied": None,
    "createRefused": False,
    "createOmitsId": False,
    "breakRefused": False,
    "uniqueNeverTrue": False,
    "leftBindings": [_OPERATOR_BINDING],
    "removal": "accepted",
    "removalMessage": "The role assignment could not be removed.",
    "uniqueAfterRemoval": None,
    "afterRemoval": "readable",
    "rebindAfterRemoval": False,
    "reappearOnProbeRead": None,
    "reappearOnDeployRead": None,
    "deployRowMalformed": False,
    "paged": False,
    "endlessPages": False,
    "deleteRefused": False,
    "deleteThrows": False,
}

#: The probe's one wait, cut so a run takes milliseconds. The splice is the pin.
_WAIT = ("  const SETTLE_MS = 2000;", "  const SETTLE_MS = 1;")


def _probe_js(cleanup: bool) -> str:
    """The committed probe with its gates open, its wait cut, its table exposed."""
    js = PROBE.read_text(encoding="utf-8")
    edits = [
        ("  const CONFIRMED = false;", "  const CONFIRMED = true;"),
        ("  const ALLOW_WRITES = false;", "  const ALLOW_WRITES = true;"),
        _WAIT,
        ("  const report = () => {\n",
         "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n"),
    ]
    if cleanup:
        edits.append(("  const CLEANUP = false;", "  const CLEANUP = true;"))
    for old, new in edits:
        assert js.count(old) == 1, f"{old!r} is not spelled as this test expects"
        js = js.replace(old, new)
    return js


def _run_probe(
    cleanup: bool = False, **config: Any,
) -> tuple[dict[str, dict[str, str]], list[dict[str, Any]], str]:
    """(rows by id, every request the probe made, the whole transcript)."""
    unknown = set(config) - set(_DEFAULTS)
    assert not unknown, f"no such mock knob: {sorted(unknown)}"
    settings = {**_DEFAULTS, **config}
    script = (
        _HARNESS.replace("__CONFIG__", json.dumps(settings)) + "\n" + _probe_js(cleanup)
    )
    output = _run(script)
    rows = next((ln for ln in output.splitlines() if ln.startswith("__ROWS__")), None)
    assert rows is not None, f"the probe printed no result table:\n{output[-3000:]}"
    calls = next((ln for ln in output.splitlines() if ln.startswith("__CALLS__")), None)
    assert calls is not None, f"the mock logged no requests:\n{output[-3000:]}"
    return (
        {row["id"]: row for row in json.loads(rows.removeprefix("__ROWS__"))},
        json.loads(calls.removeprefix("__CALLS__")),
        output,
    )


def _writes(calls: list[dict[str, Any]], fragment: str) -> list[dict[str, Any]]:
    return [c for c in calls if c["method"] == "POST" and fragment in c["url"]]


def _deletes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if c["tunnel"] == "DELETE"]


def _removals(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _writes(calls, "/removeroleassignment(")


def _lines(output: str, level: str) -> list[str]:
    return [ln for ln in output.splitlines() if ln.startswith(f"[{level}] ")]


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@needs_node
def test_a_removal_the_platform_accepts_answers_every_row() -> None:
    """The healthy run, which gives every narrower test below its meaning."""
    rows, calls, output = _run_probe()

    for fixture in (FIXTURE_LIST, FIXTURE_BREAK, FIXTURE_SOLE):
        assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    assert f"principal {_OPERATOR} (this account, PrincipalType 1" in (
        rows[FIXTURE_SOLE]["evidence"]
    )
    removal = rows[REMOVAL]
    assert removal["outcome"] == "ACCEPTED", removal
    assert "answered HTTP 200" in removal["evidence"]
    assert "the only one on the scope" in removal["evidence"]
    readback = rows[READBACK]
    assert readback["outcome"] == "OBSERVED", readback
    assert readback["evidence"].startswith(
        "the deploy reports the scope holds exactly the 0 declared role assignment(s): "
        "enumeration 1 reported no binding"
    ), readback["evidence"]
    enumeration = rows[ENUMERATION]
    assert enumeration["outcome"] == "OBSERVED"
    assert "read present on no read and absent on read(s) 1, 2, 3, 4, 5" in (
        enumeration["evidence"]
    )
    assert rows[UNIQUE]["evidence"].count("HasUniqueRoleAssignments=true") == 5
    delete = rows[DELETE]
    assert delete["outcome"] == "ACCEPTED", delete
    assert delete["evidence"].startswith("the list is gone"), delete["evidence"]
    assert all(row["state"] == "settled" for row in rows.values()), rows
    assert any("read it back absent" in line for line in _lines(output, "OK")), output
    assert not _lines(output, "FAIL"), output

    removal_call = calls.index(_removals(calls)[0])
    assert _writes(calls, "/breakroleinheritance(")
    assert calls.index(_writes(calls, "/breakroleinheritance(")[0]) < removal_call
    assert calls.index(_deletes(calls)[0]) > removal_call
    assert f"lists(guid'{_CREATED_ID}')" in _deletes(calls)[0]["url"]


@needs_node
def test_no_principal_title_and_no_site_url_reach_the_transcript() -> None:
    """A transcript is pasted into a pull request. A principal's Title is a
    person's name and SharePoint's own messages carry the site URL, so the
    title's length is recorded and every response text is masked."""
    rows, _calls, output = _run_probe(
        removal="refused",
        removalMessage=(
            "Cannot remove i:0#.f|membership|someone@example.com from "
            "https://example.sharepoint.com/sites/test/Lists/x"
        ),
    )

    assert "Wilhelmina Torres" not in output
    assert "title 17 chars" in rows[FIXTURE_SOLE]["evidence"]
    table = json.dumps(rows)
    assert "someone@example.com" not in table
    assert "https://" not in table
    assert "i:0#.f|membership|<account>" in rows[REMOVAL]["evidence"]
    assert "from <url>" in rows[REMOVAL]["evidence"]


def _deploy_binding_query() -> str:
    """The role-assignment query `_acls.js.j2` reads a scope back with."""
    source = (JINJA_TEMPLATES / "deploy" / "_acls.js.j2").read_text(encoding="utf-8")
    found = set(re.findall(r"/roleassignments\?(\$expand=[^`]+)`", source))
    assert len(found) == 1, found
    return f"roleassignments?{found.pop()}"


def _deploy_shape_select() -> str:
    """The `$select` `probeListShapeByTitle` reads a list's identity with."""
    source = (JINJA_TEMPLATES / "deploy" / "_shape_probes.js.j2").read_text(encoding="utf-8")
    block = source.split("const select = [", 1)[1].split("].join(',')", 1)[0]
    names: list[str] = re.findall(r"'([^']+)'", block)
    return ",".join(names)


@needs_node
def test_the_read_back_sends_the_deploys_own_requests_in_its_order() -> None:
    """The read-back row claims to be what Phase 4.2 sees after its last
    removal, so its requests are pinned to the deploy's source rather than
    re-spelled: the shape read that closes the removal's bracket, the one that
    opens `settleBindings`' bracket, the enumeration, and the closing shape
    read, each verbose and no-store the way `fetchWithRetry` sends it."""
    acls = (JINJA_TEMPLATES / "deploy" / "_acls.js.j2").read_text(encoding="utf-8")
    assert "const SCOPE_BINDING_SETTLE_MS = 2000;" in acls
    assert "attempt < 5; attempt += 1" in acls
    shape = f"getbytitle('{_TITLE}')?$select={_deploy_shape_select()}"
    enumeration = f"getbytitle('{_TITLE}')/{_deploy_binding_query()}"

    _rows, calls, _output = _run_probe()

    after = calls[calls.index(_removals(calls)[0]) + 1:]
    first_four = [c for c in after if c["method"] == "GET"][:4]
    assert [c["url"].split("/_api/web/lists/", 1)[1] for c in first_four] == [
        shape, shape, enumeration, shape,
    ]
    assert all(c["accept"] == "application/json;odata=verbose" for c in first_four)
    gets = [c for c in calls if c["method"] == "GET"]
    assert gets and all(c["cache"] == "no-store" for c in gets), [
        c["url"] for c in gets if c["cache"] != "no-store"
    ]


@needs_node
@pytest.mark.parametrize(
    ("removal", "outcome", "present"),
    [
        ("refused", "REFUSED", "read(s) 1, 2, 3, 4, 5"),
        ("refused-but-removed", "REFUSED", "no read"),
    ],
)
def test_a_refused_removal_is_recorded_and_the_list_is_still_deleted(
    removal: str, outcome: str, present: str,
) -> None:
    """A refusal is an answer, not a failure of the run. The after- rows still
    read the scope, which is how a refusal that removed the binding anyway
    shows up: the enumeration then reads it absent."""
    rows, calls, _output = _run_probe(removal=removal)

    assert rows[REMOVAL]["outcome"] == outcome
    assert rows[REMOVAL]["state"] == "settled"
    assert "answered HTTP 500" in rows[REMOVAL]["evidence"]
    assert "The role assignment could not be removed." in rows[REMOVAL]["evidence"]
    assert f"read present on {present}" in rows[ENUMERATION]["evidence"]
    for row in (READBACK, ENUMERATION, UNIQUE):
        assert rows[row]["outcome"] == "OBSERVED", rows[row]
    if removal == "refused":
        assert rows[READBACK]["evidence"].startswith(
            "the deploy aborts: all 5 enumerations still reported a binding other than "
            "'Limited Access'"
        ), rows[READBACK]["evidence"]
    assert rows[DELETE]["outcome"] == "ACCEPTED"
    assert len(_deletes(calls)) == 1


@needs_node
def test_a_throttled_removal_is_not_an_answer_but_the_scope_is_still_read() -> None:
    rows, _calls, _output = _run_probe(removal="throttled")

    assert rows[REMOVAL]["outcome"] == "NOT ESTABLISHED"
    assert rows[REMOVAL]["state"] == "open"
    assert "That is not an answer" in rows[REMOVAL]["evidence"]
    assert rows[ENUMERATION]["outcome"] == "OBSERVED"


@needs_node
def test_a_removal_that_throws_is_recorded_and_the_list_is_still_deleted() -> None:
    rows, calls, output = _run_probe(removal="throws")

    assert rows[REMOVAL]["outcome"] == "NOT ESTABLISHED"
    assert "threw: Error: mock transport failure on the removal" in rows[REMOVAL]["evidence"]
    assert rows[DELETE]["outcome"] == "ACCEPTED"
    assert len(_deletes(calls)) == 1
    assert "the measurement pass stopped" not in output


@needs_node
@pytest.mark.parametrize(
    ("config", "said"),
    [
        ({"breakRefused": True}, "breakroleinheritance answered HTTP 500"),
        ({"uniqueNeverTrue": True}, "HasUniqueRoleAssignments differs: read false"),
    ],
)
def test_a_break_that_did_not_hold_voids_every_row_after_it(
    config: dict[str, Any], said: str,
) -> None:
    """The break is depended on, not measured, so a failure there voids the
    rows that rest on it rather than settling them. The list is still
    deleted, because it was created."""
    rows, calls, _output = _run_probe(**config)

    assert rows[FIXTURE_LIST]["outcome"] == "PASS"
    assert rows[FIXTURE_BREAK]["outcome"] == "FAIL"
    assert said in rows[FIXTURE_BREAK]["evidence"], rows[FIXTURE_BREAK]["evidence"]
    for row in (FIXTURE_SOLE, *OBSERVED):
        assert rows[row]["state"] == "void", rows[row]
        assert f"the fixture {FIXTURE_BREAK} did not hold" in rows[row]["evidence"]
    assert not _removals(calls)
    assert len(_deletes(calls)) == 1


@needs_node
@pytest.mark.parametrize(
    ("left", "said"),
    [
        (
            [_OPERATOR_BINDING, {**_OPERATOR_BINDING, "principalId": 5,
                                 "title": "Owners Group", "principalType": 8}],
            "the break left 2 binding(s)",
        ),
        ([], "the break left 0 binding(s)"),
        (
            [{**_OPERATOR_BINDING, "principalId": 5, "title": "Owners Group",
              "principalType": 8}],
            "another principal, PrincipalType 8",
        ),
        (
            [{**_OPERATOR_BINDING, "levelId": 4, "levelName": "Limited Access"}],
            "level 4 'Limited Access'",
        ),
    ],
)
def test_a_break_that_leaves_anything_but_this_accounts_one_binding_sends_no_removal(
    left: list[dict[str, Any]], said: str,
) -> None:
    """Removing this account's binding is the removal of the LAST one only
    when it is the one binding there, so anything else voids the question."""
    rows, calls, _output = _run_probe(leftBindings=left)

    assert rows[FIXTURE_SOLE]["outcome"] == "FAIL"
    assert said in rows[FIXTURE_SOLE]["evidence"], rows[FIXTURE_SOLE]["evidence"]
    assert "so it was not sent" in rows[FIXTURE_SOLE]["evidence"]
    for row in OBSERVED:
        assert rows[row]["state"] == "void", rows[row]
    assert not _removals(calls)
    assert len(_deletes(calls)) == 1


@needs_node
def test_an_enumeration_that_never_ends_is_not_what_the_break_left() -> None:
    rows, calls, _output = _run_probe(endlessPages=True)

    assert rows[FIXTURE_SOLE]["outcome"] == "FAIL"
    assert "still continuing after 50 page(s)" in rows[FIXTURE_SOLE]["evidence"]
    assert all(rows[row]["state"] == "void" for row in OBSERVED)
    assert not _removals(calls)


@needs_node
def test_a_paged_enumeration_is_read_to_the_end() -> None:
    """The binding may be on a page nobody asked for."""
    rows, calls, _output = _run_probe(
        paged=True,
        leftBindings=[
            {**_OPERATOR_BINDING, "principalId": 5, "title": "Owners Group",
             "principalType": 8},
            _OPERATOR_BINDING,
        ],
    )

    assert [c for c in calls if "$skiptoken=" in c["url"]]
    assert "the break left 2 binding(s), read over 2 page(s)" in (
        rows[FIXTURE_SOLE]["evidence"]
    )


@needs_node
@pytest.mark.parametrize(
    ("config", "outcome", "said"),
    [
        ({"deleteRefused": True}, "REFUSED", "the DELETE answered HTTP 500"),
        ({"deleteThrows": True}, "NOT ESTABLISHED", "the DELETE threw (Error: mock transport"),
    ],
)
def test_a_delete_that_did_not_go_is_recorded_and_names_the_list(
    config: dict[str, Any], outcome: str, said: str,
) -> None:
    """The delete is the run's cleanup and one of its observations. When it
    does not go, the row says so and the operator is told which list to
    remove, by Id, before the block they are asked to copy back."""
    rows, _calls, output = _run_probe(**config)

    delete = rows[DELETE]
    assert delete["outcome"] == outcome, delete
    assert said in delete["evidence"], delete["evidence"]
    assert delete["evidence"].startswith("the list was not read back absent")
    failures = _lines(output, "FAIL")
    assert len(failures) == 1, failures
    assert f"'{_TITLE}' (list {_CREATED_ID}) may still exist" in failures[0]
    assert "going by the Id rather than the title" in failures[0]
    lines = output.splitlines()
    assert lines.index(failures[0]) < next(
        i for i, line in enumerate(lines) if "RESULTS" in line
    )
    assert rows[REMOVAL]["outcome"] == "ACCEPTED"


@needs_node
def test_an_administrator_shut_out_after_the_removal_is_what_the_rows_record() -> None:
    """The failure the deploy most needs to know about is a successful
    measurement here: every read answering 403 is the observation, and a 404
    after the delete says nothing when the list was not readable before it."""
    rows, _calls, _output = _run_probe(afterRemoval="denied")

    readback = rows[READBACK]
    assert readback["outcome"] == "OBSERVED", readback
    assert readback["evidence"].startswith(
        "the deploy throws at the list read that closes the removal's bracket, which "
        "answered HTTP 403"
    ), readback["evidence"]
    assert "Access denied." in readback["evidence"]
    enumeration = rows[ENUMERATION]
    assert enumeration["outcome"] == "OBSERVED", enumeration
    assert re.match(r"no read over \d+ ms returned rows", enumeration["evidence"])
    assert enumeration["evidence"].count("answered HTTP 403") == 5
    assert rows[UNIQUE]["outcome"] == "OBSERVED"
    assert rows[UNIQUE]["evidence"].count("HTTP 403") == 5
    assert rows[DELETE]["evidence"].startswith(
        "the list was not readable by Id before the DELETE"
    ), rows[DELETE]["evidence"]


@needs_node
def test_an_enumeration_that_serves_the_removed_binding_back_is_recorded() -> None:
    """MEASURED 2026-09-22, access.list-acl.enumeration-is-monotonic: a
    removed binding read gone, present, gone. Each read is carried, and the
    deploy's judge still stops at its first clean read, as the deploy does."""
    rows, _calls, _output = _run_probe(reappearOnProbeRead=3, reappearOnDeployRead=1)

    assert "read present on read(s) 3 and absent on read(s) 1, 2, 4, 5" in (
        rows[ENUMERATION]["evidence"]
    )
    readback = rows[READBACK]["evidence"]
    assert "enumeration 2 reported no binding other than 'Limited Access'" in readback
    assert f"enumeration 1: HTTP 200, 1 binding(s) ({_OPERATOR}:3 'Full Control')" in readback


@needs_node
def test_a_list_that_resets_its_inheritance_is_recorded_not_asserted() -> None:
    rows, _calls, _output = _run_probe(uniqueAfterRemoval=False)

    assert rows[UNIQUE]["outcome"] == "OBSERVED"
    assert rows[UNIQUE]["evidence"].count("HasUniqueRoleAssignments=false") == 5


@needs_node
def test_a_row_the_deploy_would_throw_on_is_where_the_read_back_stops() -> None:
    rows, _calls, _output = _run_probe(deployRowMalformed=True)

    assert rows[READBACK]["outcome"] == "OBSERVED"
    assert rows[READBACK]["evidence"].startswith(
        "the deploy throws at enumeration 1: an entry without PrincipalId"
    ), rows[READBACK]["evidence"]


@needs_node
def test_a_title_rebound_after_the_removal_leaves_the_after_rows_open() -> None:
    """After the removal nothing is written by title, so a read answering
    another list only has to be noticed. What was read cannot be attributed,
    so the rows stay open; the delete still goes to the claimed Id."""
    rows, calls, _output = _run_probe(rebindAfterRemoval=True)

    for row in OBSERVED:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", rows[row]
        assert rows[row]["state"] == "open"
        assert f"answered list {_REBOUND_ID} where this run claimed {_CREATED_ID}" in (
            rows[row]["evidence"]
        )
    deletes = _deletes(calls)
    assert len(deletes) == 1
    assert f"lists(guid'{_CREATED_ID}')" in deletes[0]["url"]


@needs_node
def test_an_account_that_is_not_a_site_admin_writes_nothing() -> None:
    rows, calls, _output = _run_probe(siteAdmin=False)

    for row in ALL:
        assert rows[row]["outcome"] == "NOT REACHED", rows[row]
        assert rows[row]["state"] == "void"
        assert "not a site collection administrator" in rows[row]["evidence"]
    assert not [c for c in calls if c["method"] == "POST"], calls


@needs_node
@pytest.mark.parametrize("config", [{"siteAdmin": None}, {"currentUserRefused": True},
                                    {"operatorPrincipal": "not-a-number"}])
def test_an_account_the_run_cannot_identify_writes_nothing(config: dict[str, Any]) -> None:
    rows, calls, _output = _run_probe(**config)

    for row in ALL:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", rows[row]
        assert rows[row]["state"] == "open"
        assert "without a usable Id and IsSiteAdmin" in rows[row]["evidence"]
    assert not [c for c in calls if c["method"] == "POST"], calls


@needs_node
@pytest.mark.parametrize(
    ("occupied", "said"),
    [
        ("foreign", "without this probe's ownership marker"),
        ("unreadable", "could not read whether the title"),
        ("leftover", "Set CLEANUP = true to recycle it by its Id"),
    ],
)
def test_a_title_this_run_may_not_use_is_never_touched(occupied: str, said: str) -> None:
    rows, calls, _output = _run_probe(titleOccupied=occupied)

    assert rows[FIXTURE_LIST]["outcome"] == "ABORTED"
    assert said in rows[FIXTURE_LIST]["evidence"], rows[FIXTURE_LIST]["evidence"]
    for row in ALL[1:]:
        assert rows[row]["state"] == "void", rows[row]
    assert not [c for c in calls if c["method"] == "POST" and "contextinfo" not in c["url"]]


@needs_node
def test_a_leftover_is_recycled_by_its_id_under_cleanup_and_the_run_proceeds() -> None:
    rows, calls, _output = _run_probe(cleanup=True, titleOccupied="leftover")

    recycles = _writes(calls, "/recycle")
    assert len(recycles) == 1
    assert f"lists(guid'{_LEFTOVER_ID}')/recycle" in recycles[0]["url"]
    assert rows[FIXTURE_LIST]["outcome"] == "PASS"
    assert rows[REMOVAL]["outcome"] == "ACCEPTED"


@needs_node
def test_a_list_that_cannot_be_created_voids_everything_and_deletes_nothing() -> None:
    rows, calls, output = _run_probe(createRefused=True)

    assert rows[FIXTURE_LIST]["outcome"] == "FAIL"
    assert "could not create" in rows[FIXTURE_LIST]["evidence"]
    for row in ALL[1:]:
        assert rows[row]["state"] == "void", rows[row]
    assert not _deletes(calls)
    assert not [ln for ln in _lines(output, "FAIL") if "delete" in ln], output


@needs_node
def test_a_create_that_answers_without_an_id_claims_the_list_from_its_read_back() -> None:
    rows, calls, _output = _run_probe(createOmitsId=True)

    assert rows[FIXTURE_LIST]["outcome"] == "PASS"
    assert rows[DELETE]["outcome"] == "ACCEPTED"
    assert f"lists(guid'{_CREATED_ID}')" in _deletes(calls)[0]["url"]
