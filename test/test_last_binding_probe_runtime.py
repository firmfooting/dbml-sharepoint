# test/test_last_binding_probe_runtime.py
"""Execute `last-binding-removal-probe.js` against a mock SharePoint.

The probe sends what a `reconcile: exact` policy with no assignments sends
(#667): every direct binding the break leaves is removed, in the deploy's
order, the list's last one included, and then the scope is read back the way
Phase 4.2 reads it. Its rows split into what the measurement depends on (the
list, the break, a binding for the prune to remove) and what it observes (the
removals' answers, the deploy's own read-back and verdict, the enumeration,
the flag, the closing delete). The tests hold it to that split: a failed
dependency voids the rows after it, and an observation is recorded whichever
way it came out, including the ways that would break the deploy.

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
HARNESS = MANUAL / "templates" / "_probe_harness.js.j2"

FIXTURE_LIST = "access.list-acl.fixture-last-binding-list"
FIXTURE_BREAK = "access.list-acl.fixture-last-binding-break"
FIXTURE_DIRECT = "access.list-acl.fixture-last-binding-direct"
REMOVAL = "access.list-acl.last-binding-removal"
READBACK = "access.list-acl.after-last-binding-readback"
ENUMERATION = "access.list-acl.after-last-binding-enumeration"
UNIQUE = "access.list-acl.after-last-binding-unique"
DELETE = "access.list-acl.after-last-binding-delete"

#: The five rows that observe the scope once a removal was sent.
OBSERVED = (REMOVAL, READBACK, ENUMERATION, UNIQUE, DELETE)
ALL = (FIXTURE_LIST, FIXTURE_BREAK, FIXTURE_DIRECT, *OBSERVED)

_TITLE = "dbmlsp Probe LastBinding"
_OWNERSHIP = "dbml-sharepoint last-binding-removal probe list. Safe to delete."
_CREATED_ID = "22222222-2222-2222-2222-222222222222"
_LEFTOVER_ID = "11111111-1111-1111-1111-111111111111"
_REBOUND_ID = "33333333-3333-3333-3333-333333333333"
_OPERATOR = 11
_DISPLAY_NAME = "Wilhelmina Torres"

#: What the break leaves, as MEASURED 2026-09-22 by operator-safety-grant-probe.js
#: on two sites: one binding, this account's own USER binding at Full Control.
#: The title must not reach the transcript, so it collides with nothing printed.
_OPERATOR_BINDING = {
    "principalId": _OPERATOR, "title": _DISPLAY_NAME,
    "principalType": 1, "levelId": 3, "levelName": "Full Control",
}
_GROUP_BINDING = {
    "principalId": 5, "title": "Owners Group", "principalType": 8,
    "levelId": 3, "levelName": "Full Control",
}

_HARNESS = textwrap.dedent("""
    const CONFIG = __CONFIG__;

    globalThis.__calls = [];
    process.on('exit', () => {
      console.log('__CALLS__' + JSON.stringify(globalThis.__calls));
    });

    globalThis.window = { _spPageContextInfo: { webAbsoluteUrl: CONFIG.web } };

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
      `List '${CONFIG.title}' does not exist at site with URL '${CONFIG.web}'.`);
    const denied = () => spError(403, '-2147024891, System.UnauthorizedAccessException',
      'Access denied.');
    const throttled = () => spError(429,
      '-2147024860, Microsoft.SharePoint.SPQueryThrottledException',
      'The request has been throttled.');

    const occupied = ['foreign', 'leftover', 'marker-no-id'].includes(CONFIG.titleOccupied);
    const site = {
      listExists: occupied,
      listId: occupied ? CONFIG.leftoverId : null,
      description: CONFIG.titleOccupied === 'foreign' ? 'Quarterly board packs' : CONFIG.ownership,
      unique: false,
      bindings: [],
      removed: [],
      removalSent: false,
      probeReads: 0,
      deployReads: 0,
      shapeReads: 0,
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
      if (verbose && !site.removalSent) {
        if (CONFIG.snapshot === 'refused') return spError(500, '-1, x', 'enumeration refused');
        if (CONFIG.snapshot === 'no-results') return respond(200, { d: {} });
      }
      if (verbose && site.removalSent && CONFIG.deployEnumAfter === 'no-results') {
        return respond(200, { d: {} });
      }
      let visible = site.bindings;
      if (site.removalSent && !continued) {
        if (verbose) site.deployReads += 1; else site.probeReads += 1;
        const reads = verbose ? site.deployReads : site.probeReads;
        const back = verbose ? CONFIG.reappearOnDeployRead : CONFIG.reappearOnProbeRead;
        if (back === reads) visible = [...visible, ...site.removed];
      }
      let rows = entities(visible, verbose);
      if (verbose && !site.removalSent && CONFIG.snapshot === 'no-principal') {
        rows = [{ RoleDefinitionBindings: { results: [] } }];
      }
      if (verbose && CONFIG.deployRowMalformed && site.removalSent && rows.length === 0) {
        rows = [{ RoleDefinitionBindings: { results: [] } }];
      }
      if (!verbose && CONFIG.probeRowMalformed && site.removalSent) {
        rows = [{ RoleDefinitionBindings: [] }];
      }
      const endless = CONFIG.endlessPages;
      const paged = (CONFIG.paged || endless) && (endless || !continued);
      const page = paged ? rows.slice(0, 1) : continued ? rows.slice(1) : rows;
      const next = paged ? `${u}&$skiptoken=1` : undefined;
      if (verbose) return respond(200, { d: { results: page, ...(next ? { __next: next } : {}) } });
      return respond(200, { value: page, ...(next ? { 'odata.nextLink': next } : {}) });
    };

    const items = () => {
      switch (CONFIG.items) {
        case 'unique-item': return respond(200, { d: { results: [{
          Id: 1, HasUniqueRoleAssignments: true, FileSystemObjectType: 0,
          FileRef: '/sites/test/Lists/x/1_.000',
        }] } });
        case 'no-results': return respond(200, { d: {} });
        case 'refused': return spError(500, '-1, x', 'items read refused');
        default: return respond(200, { d: { results: [] } });
      }
    };

    const behaviour = (principalId) => (
      CONFIG.removalOverrides[String(principalId)] || CONFIG.removal);

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      globalThis.__calls.push({
        url: u, method, accept: headers.Accept || null, cache: opts.cache || null,
        tunnel: headers['X-HTTP-Method'] || null, body: opts.body !== undefined,
        contentType: headers['Content-Type'] || null,
        digest: headers['X-RequestDigest'] || null,
      });
      if (u.endsWith('/_api/contextinfo')) {
        if (CONFIG.digestRefused) return spError(403, '-1, x', 'no digest');
        return respond(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      if (u.includes('/web/currentuser')) {
        if (CONFIG.currentUserRefused) return spError(500, '-1, x', 'refused');
        const me = {
          Id: CONFIG.operatorPrincipal, Title: CONFIG.displayName,
          LoginName: CONFIG.loginName, Email: CONFIG.email,
        };
        if (CONFIG.siteAdmin !== null) me.IsSiteAdmin = CONFIG.siteAdmin;
        return respond(200, me);
      }
      if (u.endsWith('/web/lists') && method === 'POST') {
        if (CONFIG.createRefused) return spError(500, '-1, x', 'list create refused');
        site.listExists = true;
        site.listId = CONFIG.createdId;
        site.description = JSON.parse(String(opts.body)).Description;
        return respond(201, {
          Title: CONFIG.title,
          ...(CONFIG.createAnswersId === null ? {} : { Id: CONFIG.createAnswersId }),
        });
      }

      const reading = method === 'GET';
      if (reading && site.removalSent && CONFIG.afterRemoval === 'throttled') return throttled();
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
            site.removed.push(...site.bindings.filter(
              (b) => b.principalId === principalId && b.levelId === levelId));
            site.bindings = site.bindings.filter(
              (b) => !(b.principalId === principalId && b.levelId === levelId));
            if (CONFIG.uniqueAfterRemoval !== null) site.unique = CONFIG.uniqueAfterRemoval;
          };
          const refusal = () => spError(500, '-2146232832, Microsoft.SharePoint.SPException',
            CONFIG.removalMessage);
          switch (behaviour(principalId)) {
            case 'accepted': take(); return respond(200, { 'odata.null': true });
            case 'ignored': return respond(200, { 'odata.null': true });
            case 'refused': return refusal();
            case 'refused-but-removed': take(); return refusal();
            case 'throttled': return throttled();
            default: throw new Error('mock transport failure on the removal');
          }
        }
        return spError(404, '-1, x', `unmocked POST ${u}`);
      }

      if (hidden) return denied();
      if (u.includes('/roleassignments?')) return enumeration(u, u.includes('$select='));
      if (u.includes('/items?')) return items();
      if (u.includes('$select=Id,Title,BaseTemplate')) site.shapeReads += 1;
      if (CONFIG.listReadBackRefused && u.includes('HasUniqueRoleAssignments')
          && u.includes('Description')) {
        return spError(500, '-1, x', 'list read refused');
      }
      const reboundNow = (site.removalSent && CONFIG.rebindAfterRemoval)
        || (CONFIG.rebindFromShapeRead !== null && site.shapeReads >= CONFIG.rebindFromShapeRead);
      const entity = {
        Id: occupied && CONFIG.titleOccupied === 'marker-no-id' ? undefined
          : reboundNow ? CONFIG.reboundId : site.listId,
        Title: CONFIG.title, BaseTemplate: 100, ContentTypesEnabled: false,
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
    "web": "https://example.sharepoint.com/sites/test",
    "createdId": _CREATED_ID,
    "createAnswersId": _CREATED_ID,
    "leftoverId": _LEFTOVER_ID,
    "reboundId": _REBOUND_ID,
    "operatorPrincipal": _OPERATOR,
    "displayName": _DISPLAY_NAME,
    "loginName": "i:0#.f|membership|wtorres@example.com",
    "email": "WTorres@example.com",
    "siteAdmin": True,
    "currentUserRefused": False,
    "digestRefused": False,
    "titleOccupied": None,
    "createRefused": False,
    "listReadBackRefused": False,
    "breakRefused": False,
    "uniqueNeverTrue": False,
    "leftBindings": [_OPERATOR_BINDING],
    "snapshot": "normal",
    "removal": "accepted",
    "removalOverrides": {},
    "removalMessage": "The role assignment could not be removed.",
    "uniqueAfterRemoval": None,
    "afterRemoval": "readable",
    "rebindAfterRemoval": False,
    "rebindFromShapeRead": None,
    "reappearOnProbeRead": None,
    "reappearOnDeployRead": None,
    "deployRowMalformed": False,
    "deployEnumAfter": None,
    "probeRowMalformed": False,
    "items": "empty",
    "paged": False,
    "endlessPages": False,
    "deleteRefused": False,
    "deleteThrows": False,
}

#: The probe's waits, cut so a run takes milliseconds. The splices are the pins.
_WAITS = [
    ("  const SETTLE_MS = 2000;", "  const SETTLE_MS = 1;"),
    ("  const RETRY_UNIT_MS = 1000;", "  const RETRY_UNIT_MS = 0;"),
]


def _probe_js(cleanup: bool) -> str:
    """The committed probe with its gates open, its waits cut, its table exposed."""
    js = PROBE.read_text(encoding="utf-8")
    edits = [
        ("  const CONFIRMED = false;", "  const CONFIRMED = true;"),
        ("  const ALLOW_WRITES = false;", "  const ALLOW_WRITES = true;"),
        *_WAITS,
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


def _breaks(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return _writes(calls, "/breakroleinheritance(")


def _creates(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if c["method"] == "POST" and c["url"].endswith("/web/lists")]


def _lines(output: str, level: str) -> list[str]:
    return [ln for ln in output.splitlines() if ln.startswith(f"[{level}] ")]


def _acls() -> str:
    return (JINJA_TEMPLATES / "deploy" / "_acls.js.j2").read_text(encoding="utf-8")


def _deploy_binding_query() -> str:
    """The role-assignment query `_acls.js.j2` reads a scope back with."""
    found = set(re.findall(r"/roleassignments\?(\$expand=[^`]+)`", _acls()))
    assert len(found) == 1, found
    return f"roleassignments?{found.pop()}"


def _deploy_items_query() -> str:
    """The items query `surveyDescendants` pages through."""
    found = set(re.findall(r"/items\?(\$select=Id,HasUniqueRoleAssignments[^`]+)`", _acls()))
    assert len(found) == 1, found
    return f"items?{found.pop()}"


def _deploy_shape_select() -> str:
    """The `$select` `probeListShapeByTitle` reads a list's identity with."""
    source = (JINJA_TEMPLATES / "deploy" / "_shape_probes.js.j2").read_text(encoding="utf-8")
    block = source.split("const select = [", 1)[1].split("].join(',')", 1)[0]
    names: list[str] = re.findall(r"'([^']+)'", block)
    return ",".join(names)


def _path(call: dict[str, Any]) -> str:
    return str(call["url"]).split("/_api/web/lists/", 1)[1]


needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


@needs_node
def test_a_removal_the_platform_accepts_answers_every_row() -> None:
    """The healthy run, which gives every narrower test below its meaning."""
    rows, calls, output = _run_probe()

    for fixture in (FIXTURE_LIST, FIXTURE_BREAK, FIXTURE_DIRECT):
        assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    assert f"{_OPERATOR}:3 'Full Control' (this account)" in rows[FIXTURE_DIRECT]["evidence"]
    removal = rows[REMOVAL]
    assert removal["outcome"] == "ACCEPTED", removal
    assert "removal 1 of 1" in removal["evidence"]
    assert "answered HTTP 200" in removal["evidence"]
    assert "The last removal sent was this account's binding" in removal["evidence"]
    readback = rows[READBACK]
    assert readback["outcome"] == "OBSERVED", readback
    assert readback["evidence"].startswith(
        "the deploy logs that the scope reports exactly the 0 declared role assignment(s), "
        "because enumeration 1 reported no binding other than 'Limited Access', and its "
        "descendant survey found no undeclared unique scope among 0 item(s), so the list "
        "completes Phase 4.2"
    ), readback["evidence"]
    enumeration = rows[ENUMERATION]
    assert enumeration["outcome"] == "OBSERVED"
    assert "read present on no read and absent on read(s) 1, 2, 3, 4, 5" in (
        enumeration["evidence"]
    )
    assert f"principal {_OPERATOR} (this account" not in enumeration["evidence"]
    assert rows[UNIQUE]["evidence"].count("HasUniqueRoleAssignments=true") == 5
    delete = rows[DELETE]
    assert delete["outcome"] == "ACCEPTED", delete
    assert delete["evidence"].startswith("the list is gone"), delete["evidence"]
    assert all(row["state"] == "settled" for row in rows.values()), rows
    assert any("read it back absent" in line for line in _lines(output, "OK")), output
    assert not _lines(output, "FAIL"), output

    removal_call = calls.index(_removals(calls)[0])
    assert calls.index(_breaks(calls)[0]) < removal_call
    assert calls.index(_deletes(calls)[0]) > removal_call
    assert f"lists(guid'{_CREATED_ID}')" in _deletes(calls)[0]["url"]


@needs_node
def test_no_site_address_and_no_account_reach_the_transcript() -> None:
    """A transcript is pasted into a pull request. The strings this run knows
    are replaced exactly, whatever their case, so a host or a path no pattern
    would recognise is still masked; then every form a pattern can recognise
    is masked too. A principal's title is only ever printed as its length."""
    message = " ".join([
        # Known at run time, and recognisable by no pattern below.
        "INTRANET.EXAMPLE.ORG", "/Depts/Finance/Lists/x", "wilhelmina torres",
        "i:0#.f|membership|wtorres@example.org", "wtorres@EXAMPLE.org",
        # Recognised by pattern, in either case.
        "HTTPS://CONTOSO.SHAREPOINT.COM/TEAMS/X", "contoso-my.sharepoint.com",
        "/personal/jdoe_contoso_com/Documents", "i:0#.w|corp\\jdoe", "someone@example.com",
    ])
    rows, _calls, output = _run_probe(
        web="https://intranet.example.org/depts/finance",
        loginName="i:0#.f|membership|wtorres@example.org",
        email="WTorres@example.org",
        removal="refused",
        removalMessage=message,
    )

    evidence = rows[REMOVAL]["evidence"]
    # The mock's own request log carries every URL, and is not the probe's output.
    printed = "\n".join(ln for ln in output.splitlines() if not ln.startswith("__CALLS__"))
    for fragment in ("intranet.example.org", "/depts/finance", "wilhelmina", "wtorres",
                     "contoso", "jdoe", "someone@", "https://"):
        assert fragment not in printed.lower(), fragment
    for mask in ("<host>", "<web-path>/Lists/x", "<name>", "<url>",
                 "/personal/<site>", "i:0#.w|<account>", "<account>"):
        assert mask in evidence, (mask, evidence)
    assert f"title {len(_DISPLAY_NAME)} chars" in rows[ENUMERATION]["evidence"]


def test_the_guid_check_is_the_one_the_harness_cleanup_uses() -> None:
    """The closing DELETE splices an Id into a URL, so it refuses one that is
    not a list Id with the same pattern `resetList` refuses one with."""
    pattern = "/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i"
    assert f"const GUID = {pattern};" in HARNESS.read_text(encoding="utf-8")
    assert f"const GUID = {pattern};" in PROBE.read_text(encoding="utf-8")


@needs_node
def test_the_read_back_sends_the_deploys_own_requests_in_its_order() -> None:
    """The read-back row claims to be what Phase 4.2 sees after its last
    removal, so its requests are pinned to the deploy's source rather than
    re-spelled: the list read that closes the removal's bracket, the one that
    opens `settleBindings`' bracket, the enumeration, the closing read, and
    the descendant survey exact mode runs after `reconcileScope`. Each is
    verbose and no-store the way `fetchWithRetry` sends it."""
    acls = _acls()
    assert "const SCOPE_BINDING_SETTLE_MS = 2000;" in acls
    assert "attempt < 5; attempt += 1" in acls
    assert "(await surveyDescendants(listTitle, wantedFolders)).undeclared" in acls
    assert (
        "settle: (SCHEMA.lists.find((l) => l.title === listTitle) || {}).is_library === true"
    ) in acls
    shape = f"getbytitle('{_TITLE}')?$select={_deploy_shape_select()}"
    enumeration = f"getbytitle('{_TITLE}')/{_deploy_binding_query()}"
    survey = f"getbytitle('{_TITLE}')/{_deploy_items_query()}"

    _rows, calls, _output = _run_probe()

    after = [c for c in calls[calls.index(_removals(calls)[-1]) + 1:] if c["method"] == "GET"]
    assert [_path(c) for c in after[:5]] == [shape, shape, enumeration, shape, survey]
    assert all(c["accept"] == "application/json;odata=verbose" for c in after[:5])
    gets = [c for c in calls if c["method"] == "GET"]
    assert gets and all(c["cache"] == "no-store" for c in gets), [
        c["url"] for c in gets if c["cache"] != "no-store"
    ]

    # The break's bracket, then the snapshot with no wait between, as for a list.
    broke = calls.index(_breaks(calls)[0])
    after_break = [c for c in calls[broke + 1:] if c["method"] == "GET"]
    assert [_path(c) for c in after_break[:2]] == [shape, enumeration]
    # ownedListIdentity before pruning, then the removal's own opening read.
    removed = calls.index(_removals(calls)[0])
    before_removal = [c for c in calls[:removed] if c["method"] == "GET"]
    assert [_path(c) for c in before_removal[-2:]] == [shape, shape]


def _deploy_post(what: str) -> str:
    """The fetchWithRetry call `_acls.js.j2` sends `what` with."""
    source = _acls()
    start = source.index(f"/{what}(")
    return source[start:source.index("});", start)]


@needs_node
def test_the_break_and_the_removals_carry_the_deploys_headers_and_no_body() -> None:
    for what in ("breakroleinheritance", "removeroleassignment"):
        sent = _deploy_post(what)
        assert (
            "headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 }"
        ) in sent
        assert "body" not in sent, sent

    _rows, calls, _output = _run_probe()

    for call in (*_breaks(calls), *_removals(calls)):
        assert call["accept"] == "application/json;odata=verbose", call
        assert call["digest"] == "digest", call
        assert call["body"] is False, call
        assert call["contentType"] is None, call
        assert call["cache"] == "no-store", call


@needs_node
@pytest.mark.parametrize(
    ("left", "whose_first", "whose_last"),
    [
        ([_GROUP_BINDING, _OPERATOR_BINDING], "another principal", "this account"),
        ([_OPERATOR_BINDING, _GROUP_BINDING], "this account", "another principal"),
        ([_GROUP_BINDING], "another principal", "another principal"),
    ],
)
def test_every_binding_goes_in_the_deploys_order_and_whose_went_last_is_recorded(
    left: list[dict[str, Any]], whose_first: str, whose_last: str,
) -> None:
    """The exact prune removes every direct binding but 'Limited Access', in
    enumeration order, each in its own identity bracket. Which binding is the
    last one is observed, not assumed to be this account's."""
    rows, calls, _output = _run_probe(leftBindings=left)

    assert rows[FIXTURE_DIRECT]["outcome"] == "PASS"
    sent = [re.search(r"principalid=(\d+)", c["url"]) for c in _removals(calls)]
    assert [int(m.group(1)) for m in sent if m] == [b["principalId"] for b in left]
    evidence = rows[REMOVAL]["evidence"]
    assert rows[REMOVAL]["outcome"] == "ACCEPTED"
    first_sent = f"removeroleassignment(principalid={left[0]['principalId']}"
    assert f"removal 1 of {len(left)}, {first_sent}" in evidence
    assert f"{whose_first}'s 'Full Control' binding" in evidence
    assert f"The last removal sent was {whose_last}'s binding" in evidence
    assert rows[READBACK]["evidence"].startswith("the deploy logs that the scope reports exactly")
    if len(left) == 2:
        first, second = (calls.index(c) for c in _removals(calls))
        between = [_path(c) for c in calls[first + 1:second] if c["method"] == "GET"]
        shape = f"getbytitle('{_TITLE}')?$select={_deploy_shape_select()}"
        assert between == [shape, shape]


@needs_node
def test_a_removal_refused_part_way_stops_the_prune_as_the_deploy_does() -> None:
    rows, calls, _output = _run_probe(
        leftBindings=[_GROUP_BINDING, _OPERATOR_BINDING],
        removalOverrides={"5": "refused"},
    )

    assert len(_removals(calls)) == 1
    evidence = rows[REMOVAL]["evidence"]
    assert rows[REMOVAL]["outcome"] == "REFUSED"
    assert "the deploy stops there, so 1 binding(s) were never sent" in evidence
    assert "The last removal sent was another principal's binding" in evidence
    assert rows[READBACK]["evidence"] == (
        "the deploy throws at removal 1, which answered HTTP 500. It makes no read after that."
    )


@needs_node
@pytest.mark.parametrize(
    ("removal", "present"),
    [("refused", "read(s) 1, 2, 3, 4, 5"), ("refused-but-removed", "no read")],
)
def test_a_refused_removal_is_recorded_and_the_list_is_still_deleted(
    removal: str, present: str,
) -> None:
    """A refusal is an answer, not a failure of the run. The deploy throws
    there and reads nothing back, which the read-back row says; the after-
    rows still read the scope, which is how a refusal that removed the
    binding anyway shows up."""
    rows, calls, _output = _run_probe(removal=removal)

    assert rows[REMOVAL]["outcome"] == "REFUSED"
    assert rows[REMOVAL]["state"] == "settled"
    assert "answered HTTP 500" in rows[REMOVAL]["evidence"]
    assert "The role assignment could not be removed." in rows[REMOVAL]["evidence"]
    assert rows[READBACK]["outcome"] == "OBSERVED"
    assert rows[READBACK]["evidence"].startswith(
        "the deploy throws at removal 1, which answered HTTP 500"
    )
    assert f"read present on {present}" in rows[ENUMERATION]["evidence"]
    assert rows[ENUMERATION]["outcome"] == "OBSERVED"
    assert rows[UNIQUE]["outcome"] == "OBSERVED"
    assert rows[DELETE]["outcome"] == "ACCEPTED"
    assert len(_deletes(calls)) == 1


@needs_node
def test_a_throttled_removal_is_retried_as_the_deploy_retries_it_and_is_not_an_answer() -> None:
    """fetchWithRetry retries a throttle 8 times before handing the response
    back; the probe does the same, and a throttle that outlasts it answers
    nothing about the removal."""
    rows, calls, _output = _run_probe(removal="throttled")

    assert len(_removals(calls)) == 9
    assert rows[REMOVAL]["outcome"] == "NOT ESTABLISHED"
    assert rows[REMOVAL]["state"] == "open"
    assert "A removal that did not answer is not an answer" in rows[REMOVAL]["evidence"]
    assert rows[READBACK]["outcome"] == "NOT ESTABLISHED"
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
    for row in (FIXTURE_DIRECT, *OBSERVED):
        assert rows[row]["state"] == "void", rows[row]
        assert f"the fixture {FIXTURE_BREAK} did not hold" in rows[row]["evidence"]
    assert not _removals(calls)
    assert len(_deletes(calls)) == 1


@needs_node
@pytest.mark.parametrize(
    ("config", "said"),
    [
        ({"leftBindings": []}, "it returned 0 binding(s) over 1 page(s), 0 of them"),
        (
            {"leftBindings": [{**_OPERATOR_BINDING, "levelId": 4, "levelName": "Limited Access"}]},
            "0 of them other than 'Limited Access'",
        ),
        ({"snapshot": "refused"}, "the deploy would throw reading it (page 1 answered HTTP 500"),
        ({"snapshot": "no-principal"},
         "the deploy would throw reading it (page 1: an entry without PrincipalId)"),
        ({"snapshot": "no-results"},
         "page 1 carried no results array, so the deploy read zero rows from it"),
        ({"endlessPages": True}, "still continuing after 50 page(s)"),
    ],
)
def test_a_snapshot_with_nothing_to_prune_sends_no_removal(
    config: dict[str, Any], said: str,
) -> None:
    """The prune needs a binding to remove, read the way the deploy reads it
    and to its last page. A snapshot the deploy would throw on, or read as
    empty, voids the question rather than answering it."""
    rows, calls, _output = _run_probe(**config)

    assert rows[FIXTURE_DIRECT]["outcome"] == "FAIL"
    assert said in rows[FIXTURE_DIRECT]["evidence"], rows[FIXTURE_DIRECT]["evidence"]
    assert "so no removal was sent" in rows[FIXTURE_DIRECT]["evidence"]
    for row in OBSERVED:
        assert rows[row]["state"] == "void", rows[row]
    assert not _removals(calls)
    assert len(_deletes(calls)) == 1


@needs_node
def test_a_paged_snapshot_is_read_to_the_end() -> None:
    """The binding may be on a page nobody asked for."""
    rows, calls, _output = _run_probe(paged=True, leftBindings=[_GROUP_BINDING, _OPERATOR_BINDING])

    assert [c for c in calls if "$skiptoken=" in c["url"]]
    assert "it returned 2 binding(s) over 2 page(s)" in rows[FIXTURE_DIRECT]["evidence"]
    assert len(_removals(calls)) == 2


@needs_node
def test_the_deploy_reading_a_200_without_results_as_no_rows_is_modelled_not_corrected() -> None:
    """`(json.d && json.d.results) || []` reads a 200 that carries no results
    array as a scope with no bindings, so the deploy certifies it. The probe
    reports that verdict, and says separately that the answer carried no
    rows, while its own enumeration still reads the binding there."""
    rows, _calls, _output = _run_probe(removal="ignored", deployEnumAfter="no-results")

    readback = rows[READBACK]["evidence"]
    assert rows[READBACK]["outcome"] == "OBSERVED"
    assert readback.startswith(
        "the deploy logs that the scope reports exactly the 0 declared role assignment(s), "
        "because enumeration 1 reported no binding other than 'Limited Access'"
    ), readback
    assert (
        "enumeration 1: HTTP 200, 0 binding(s); page 1 carried no results array, so the "
        "deploy read zero rows from it"
    ) in readback
    assert "read present on read(s) 1, 2, 3, 4, 5" in rows[ENUMERATION]["evidence"]


@needs_node
@pytest.mark.parametrize(
    ("items", "verdict"),
    [
        ("unique-item", (", then throws at the descendant survey: 1 undeclared item/folder "
                         "unique permission scope(s) remain")),
        ("refused", ", then throws at the descendant survey: page 1 answered HTTP 500"),
        ("no-results", (", and its descendant survey found no undeclared unique scope among 0 "
                        "item(s), so the list completes Phase 4.2")),
    ],
)
def test_the_descendant_survey_decides_the_verdict_after_the_settle(
    items: str, verdict: str,
) -> None:
    rows, _calls, _output = _run_probe(items=items)

    readback = rows[READBACK]["evidence"]
    assert rows[READBACK]["outcome"] == "OBSERVED"
    assert verdict in readback, readback
    if items == "no-results":
        assert "page 1 carried no results array, so the deploy read zero items from it" in readback


@needs_node
@pytest.mark.parametrize(
    ("config", "outcome", "said"),
    [
        ({"deleteRefused": True}, "REFUSED", "the DELETE answered HTTP 500"),
        ({"deleteThrows": True}, "NOT ESTABLISHED", "the DELETE threw (Error: mock transport"),
    ],
)
def test_a_delete_that_did_not_go_is_recorded_and_hands_over_a_line_that_does(
    config: dict[str, Any], outcome: str, said: str,
) -> None:
    """The delete is the run's cleanup and one of its observations. When it
    does not go, the row says so and the operator is given a line that
    deletes the list by its Id, printed before the block they copy back."""
    rows, _calls, output = _run_probe(**config)

    delete = rows[DELETE]
    assert delete["outcome"] == outcome, delete
    assert said in delete["evidence"], delete["evidence"]
    assert delete["evidence"].startswith("the list was not read back absent")
    failures = _lines(output, "FAIL")
    assert len(failures) == 1, failures
    assert f"'{_TITLE}' (list {_CREATED_ID}) may still exist" in failures[0]
    lines = output.splitlines()
    assert lines.index(failures[0]) < next(
        i for i, line in enumerate(lines) if "RESULTS" in line
    )
    assert rows[REMOVAL]["outcome"] == "ACCEPTED"

    pasted = failures[0].split("as a site collection administrator: ", 1)[1]
    assert "https://" not in pasted
    replay = textwrap.dedent("""
        const calls = [];
        globalThis._spPageContextInfo = {
          webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
        };
        globalThis.fetch = async (url, opts = {}) => {
          calls.push({ url: String(url), method: opts.method, headers: opts.headers || {} });
          const d = { GetContextWebInformation: { FormDigestValue: 'fresh-digest' } };
          return { status: 200, json: async () => ({ d }) };
        };
        __PASTED__
        setTimeout(() => console.log('__REPLAY__' + JSON.stringify(calls)), 50);
    """).replace("__PASTED__", pasted)
    replayed = _run(replay)
    sent = json.loads(next(
        ln for ln in replayed.splitlines() if ln.startswith("__REPLAY__")
    ).removeprefix("__REPLAY__"))
    assert [c["url"] for c in sent] == [
        "https://example.sharepoint.com/sites/test/_api/contextinfo",
        f"https://example.sharepoint.com/sites/test/_api/web/lists(guid'{_CREATED_ID}')",
    ]
    assert sent[1]["method"] == "POST"
    assert sent[1]["headers"] == {
        "X-RequestDigest": "fresh-digest", "X-HTTP-Method": "DELETE", "IF-MATCH": "*",
    }
    assert "DELETE answered HTTP 200" in replayed


@needs_node
def test_an_id_that_is_not_a_guid_is_never_spliced_into_the_delete() -> None:
    rows, calls, output = _run_probe(createAnswersId="not-a-guid')/items(1")

    assert rows[FIXTURE_LIST]["outcome"] == "FAIL"
    assert not _deletes(calls)
    failures = _lines(output, "FAIL")
    assert any("is not a list Id, so no DELETE was sent" in line for line in failures), failures
    assert any("Delete the list titled" in line for line in failures), failures


@needs_node
def test_an_administrator_shut_out_after_the_removal_is_what_the_rows_record() -> None:
    """Learn predicts an administrator keeps access; a 403 on every read is
    therefore the observation that would contradict it, and it is recorded
    as one. A 404 after the delete says nothing when the list was not
    readable before it."""
    rows, _calls, _output = _run_probe(afterRemoval="denied")

    readback = rows[READBACK]
    assert readback["outcome"] == "OBSERVED", readback
    assert readback["evidence"].startswith(
        "the deploy throws at the list read that closes removal 1's bracket, which "
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
def test_reads_that_never_answer_after_the_removal_settle_nothing() -> None:
    """A throttle that outlasts the deploy's retries on every read is not an
    observation of the scope, so no row settles from it."""
    rows, _calls, _output = _run_probe(afterRemoval="throttled")

    assert rows[REMOVAL]["outcome"] == "ACCEPTED"
    for row in (READBACK, ENUMERATION, UNIQUE):
        assert rows[row]["outcome"] == "NOT ESTABLISHED", rows[row]
        assert rows[row]["state"] == "open", rows[row]
    assert "still throttled after the deploy's retries" in rows[READBACK]["evidence"]
    assert rows[UNIQUE]["evidence"].startswith("none of the 5 reads answered")


@needs_node
def test_an_enumeration_row_the_probe_cannot_place_is_not_an_answer() -> None:
    rows, _calls, _output = _run_probe(probeRowMalformed=True)

    enumeration = rows[ENUMERATION]
    assert enumeration["outcome"] == "NOT ESTABLISHED", enumeration
    assert enumeration["evidence"].count(
        "a role assignment came back with a PrincipalId of undefined, not an answer") == 5


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
    assert (
        f"enumeration 1: HTTP 200, 1 binding(s) ({_OPERATOR}:3 'Full Control' (this account))"
    ) in readback


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
        "the deploy throws at enumeration 1: page 1: an entry without PrincipalId"
    ), rows[READBACK]["evidence"]


@needs_node
def test_a_title_rebound_after_the_removal_leaves_the_after_rows_open() -> None:
    """After the removals nothing is written by title, so a read answering
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
@pytest.mark.parametrize(
    ("from_read", "where", "broke"),
    [
        (1, "the list read before breakroleinheritance", False),
        (4, "the list read that opens removal 1's bracket", True),
    ],
)
def test_a_title_rebound_before_a_write_stops_the_run_before_it(
    from_read: int, where: str, broke: bool,
) -> None:
    """Every write goes by title, so each is bracketed by an identity read. A
    title answering another list, one carrying a copied marker, stops the run
    before the write it guards, and the delete still goes to the claimed Id."""
    rows, calls, output = _run_probe(rebindFromShapeRead=from_read)

    assert bool(_breaks(calls)) is broke
    assert not _removals(calls)
    stop = [line for line in _lines(output, "FAIL") if "the measurement pass stopped" in line]
    assert stop == [(
        f"[FAIL] the measurement pass stopped: the deploy throws at {where}: {where} answered "
        f"list {_REBOUND_ID} where this run claimed {_CREATED_ID}. Nothing further was sent "
        "by title."
    )], stop
    for row in OBSERVED:
        assert rows[row]["state"] == "open", rows[row]
        assert rows[row]["evidence"].startswith("the run stopped before this question")
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
    ("occupied", "cleanup", "said"),
    [
        ("foreign", False, "without this probe's ownership marker"),
        ("foreign", True, "without this probe's ownership marker"),
        ("unreadable", True, "could not read whether the title"),
        ("leftover", False, "Set CLEANUP = true to delete it by its Id"),
        ("marker-no-id", True, "carries this probe's ownership marker but answered without an Id"),
    ],
)
def test_a_title_this_run_may_not_use_is_never_touched(
    occupied: str, cleanup: bool, said: str,
) -> None:
    rows, calls, _output = _run_probe(cleanup=cleanup, titleOccupied=occupied)

    assert rows[FIXTURE_LIST]["outcome"] == "ABORTED"
    assert said in rows[FIXTURE_LIST]["evidence"], rows[FIXTURE_LIST]["evidence"]
    for row in ALL[1:]:
        assert rows[row]["state"] == "void", rows[row]
    assert not [c for c in calls if c["method"] == "POST"], calls


@needs_node
def test_a_leftover_is_deleted_by_its_id_under_cleanup_and_the_run_proceeds() -> None:
    rows, calls, output = _run_probe(cleanup=True, titleOccupied="leftover")

    deletes = _deletes(calls)
    assert [f"lists(guid'{_LEFTOVER_ID}')" in c["url"] for c in deletes] == [True, False]
    assert calls.index(deletes[0]) < calls.index(_creates(calls)[0])
    assert not _writes(calls, "/recycle")
    assert any(f"CLEANUP: deleted the leftover '{_TITLE}' (list {_LEFTOVER_ID})" in line
               for line in _lines(output, "OK"))
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
    question = rows[FIXTURE_LIST]["question"]
    assert _lines(output, "FAIL") == [f"[FAIL] {FIXTURE_LIST}: FAIL. {question}"]


@needs_node
def test_a_digest_that_cannot_be_read_creates_nothing_and_claims_nothing_was_made() -> None:
    """The create is sent only once a digest is in hand, so a failure to get
    one is not a create that may have landed."""
    rows, calls, output = _run_probe(digestRefused=True)

    assert not _creates(calls)
    stops = _lines(output, "FAIL")
    assert stops == ["[FAIL] the measurement pass stopped: contextinfo failed: HTTP 403"], stops
    for row in ALL:
        assert rows[row]["state"] == "open", rows[row]
        assert rows[row]["evidence"].startswith("the run stopped before this question")


@needs_node
def test_a_create_that_answers_without_an_id_claims_the_list_from_its_read_back() -> None:
    rows, calls, _output = _run_probe(createAnswersId=None)

    assert rows[FIXTURE_LIST]["outcome"] == "PASS"
    assert rows[DELETE]["outcome"] == "ACCEPTED"
    assert f"lists(guid'{_CREATED_ID}')" in _deletes(calls)[0]["url"]


@needs_node
def test_a_list_whose_id_was_never_established_is_named_for_deletion_by_hand() -> None:
    """The create was sent and may have landed, but neither its answer nor
    the read-back gave an Id, so nothing is deleted by guesswork and the
    operator is told what to look for."""
    rows, calls, output = _run_probe(createAnswersId=None, listReadBackRefused=True)

    assert rows[FIXTURE_LIST]["outcome"] == "FAIL"
    assert not _deletes(calls)
    assert [line for line in _lines(output, "FAIL") if "could not establish the Id" in line] == [(
        f"[FAIL] this run could not establish the Id of '{_TITLE}', so it deleted nothing. If "
        "a list with that title carries this probe's Description, delete it by hand from Site "
        "contents as a site collection administrator."
    )]
