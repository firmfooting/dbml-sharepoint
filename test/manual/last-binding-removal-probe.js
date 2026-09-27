
/** ---- dbml-sharepoint PROBE: REMOVING THE LAST ROLE ASSIGNMENT ON A LIST ----
 *
 * REVISION: 78f41d72
 *
 * THE REQUEST UNDER TEST (issue #667). A `list_permissions` policy with
 * `reconcile: exact` and no assignments makes Phase 4.2 in
 * `deploy/_acls.js.j2` remove every direct binding on the list except
 * 'Limited Access', and nothing exempts the operator's own. MEASURED
 * 2026-09-22 by operator-safety-grant-probe.js on two sites: a break with
 * copyRoleAssignments=false leaves exactly one binding, this account's own
 * USER binding at 'Full Control'. So the deploy's removal of it is the
 * removal of the LAST role assignment on the scope, and that probe never
 * sends it, because it grants the owner group first.
 *
 * WHY A PROBE OF ITS OWN. The owner grant is the premise of that probe's
 * removal row, and its questions share one list and one restore pass. This
 * one needs a list nobody else is ever granted on, and it ends by deleting
 * the list rather than restoring it.
 *
 * WHY THIS CANNOT BE ANSWERED FROM DOCUMENTATION. Checked 2026-09-27: the
 * RoleAssignmentCollection pages and "Role, inheritance, elevation of
 * privilege, and password changes in SharePoint" say nothing about removing
 * the last role assignment on a scope, or about what a site collection
 * administrator can still read once it is gone.
 *
 * DEPENDED ON. Each is asserted, and a failure VOIDS every row after it:
 *   access.list-acl.fixture-last-binding-list
 *     A list this run created carries its marker and Id and still inherits.
 *   access.list-acl.fixture-last-binding-break
 *     breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)
 *     is accepted and the list then reads HasUniqueRoleAssignments=true.
 *   access.list-acl.fixture-last-binding-sole-operator
 *     The enumeration, every page, then holds exactly one binding: a direct
 *     one for this account at a level other than 'Limited Access'.
 *
 * OBSERVED. Recorded as they came back, never asserted:
 *   access.list-acl.last-binding-removal
 *     What removeroleassignment answers for that binding, status and body.
 *   access.list-acl.after-last-binding-readback
 *     The GETs Phase 4.2 makes after its last removal, in its order, with its
 *     $select, its verbose Accept and its no-store: the list shape read, then
 *     the role-assignment enumeration up to five times 2000 ms apart, then
 *     the shape read again. Each answer, and what the deploy would conclude.
 *   access.list-acl.after-last-binding-enumeration
 *     Five enumerations over 8000 ms, every page, each row with its
 *     principal type and level, because this enumeration was measured to
 *     flap (access.list-acl.enumeration-is-monotonic).
 *   access.list-acl.after-last-binding-unique
 *     HasUniqueRoleAssignments on each of the same five reads.
 *   access.list-acl.after-last-binding-delete
 *     What the DELETE that ends the run answers, and whether a read by Id
 *     then finds the list gone.
 *
 * The after- rows describe the scope once the removal was SENT, whatever it
 * answered, so a refused call that removed the binding anyway is visible.
 * No principal's title is printed, only its length, and every response text
 * has URLs and account names masked, because a transcript gets pasted into
 * a pull request.
 *
 * MICROSOFT LEARN CITATIONS
 *   "SP.SecurableObject.breakRoleInheritance method"
 *   "SP.RoleAssignmentCollection.removeRoleAssignment(principalId,
 *    roleDefId) method" and "SP.RoleAssignmentCollection object"
 *   "Working with lists and list items with REST": create a list by POST
 *    to web/lists, delete one by POST to web/lists(guid'...') with
 *    X-HTTP-Method DELETE
 *   "Complete basic operations using SharePoint REST endpoints": a DELETE
 *    of a recyclable object such as a list is a Recycle operation
 *
 * RUN AS A SITE COLLECTION ADMINISTRATOR ON A DISPOSABLE SITE. The run takes
 * the list's last role assignment away from the account running it, and
 * whether that account can still read or delete the list is the thing being
 * measured. It checks web/currentuser for IsSiteAdmin=true and writes
 * nothing at all when it is not.
 *
 * HOW TO RUN
 *   1. Open the disposable site at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * STATUS: NOT YET RUN.
 *
 * WHEN FINISHED: the run deletes its list by Id and reads it back. A FAIL
 * line naming the list's Id means it may still be there.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // CLEANUP deletes the probe's own list BEFORE the run, so every question
  // is answered by actually creating something rather than reporting
  // "already present" from a previous run, which is much weaker evidence.
  //
  // It is destructive and needs CONFIRMED and ALLOW_WRITES as well. It only
  // ever touches the explicitly named probe-owned list or lists; it never
  // enumerates or deletes anything else. Each list is RECYCLED, not purged,
  // so a mistake is recoverable from the site recycle bin.
  const CLEANUP = false;

  // No SITE_URL constant, deliberately. The probe reads the site it was
  // pasted into. A tenant URL committed to this repo has leaked twice, and
  // the field was the vector both times.
  const pageCtx = window._spPageContextInfo;
  if (!pageCtx) {
    console.error('[FATAL] No _spPageContextInfo. Paste this into a SharePoint page.');
    return;
  }
  const WEB = pageCtx.webAbsoluteUrl;

  const log = (level, msg) => console.log(`[${level}] ${msg}`);

  const getDigest = async () => {
    const res = await fetch(`${WEB}/_api/contextinfo`, {
      method: 'POST', headers: { Accept: 'application/json;odata=verbose' },
    });
    if (!res.ok) throw new Error(`contextinfo failed: HTTP ${res.status}`);
    const body = await res.json();
    return body.d.GetContextWebInformation.FormDigestValue;
  };

  const spGet = async (path) => {
    const res = await fetch(`${WEB}/_api/${path}`, {
      headers: { Accept: 'application/json;odata=nometadata' },
    });
    return { ok: res.ok, status: res.status, body: await res.json().catch(() => null) };
  };

  // NOTE the contract, because getting it wrong has produced false verdicts
  // here twice: `body` is the PARSED payload whether or not the request
  // succeeded. SharePoint answers a 403 or a 429 with a JSON error object,
  // so `body !== null` says the response was JSON, never that the call
  // worked. Anything asking "did I actually read this?" must test `ok`.
  const readFailed = (r) => !r.ok || r.body === null;

  // Was this request REFUSED (the server saying no to what was sent) or
  // did it merely fail? A negative control that cannot tell the difference
  // certifies the surface as observable on the strength of a throttle, and
  // every row it guards is then read as evidence.
  //
  // Defined by what it EXCLUDES, because the tempting definition is wrong
  // here. "400 means bad request" is the HTTP convention and it is not what
  // this tenant does: every SharePoint refusal this project has recorded
  // came back 500:
  //
  //   "To add an item to a document library, use SPFileCollection.Add()"
  //   "One or more column references are not allowed, because the columns
  //    are defined as a data type that is not supported in formulas"
  //   "The formula refers to a column that does not exist"
  //   "This field type does not support..."
  //
  // (analysis/checks/_structure.py, analysis/conditions.py, generators/
  // jsgen.py, each dated and cited to a live run). A 400-only test would
  // therefore have reported NOT ESTABLISHED for every negative control on a
  // tenant behaving exactly as recorded, which is the opposite failure and a
  // worse one: it would quietly retire the controls the stack's own evidence
  // rests on.
  //
  // So: 401/403 are about WHO is asking and 408/429 about the moment; those
  // are never refusals. Everything else non-2xx is treated as the server
  // rejecting the content, and the response TEXT is always printed beside
  // the verdict so a reader can see which it was.
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 503; // 503: the other documented throttle

  // extraHeaders carries X-HTTP-Method for MERGE/DELETE: SharePoint tunnels
  // both through POST rather than accepting them as real verbs.
  const spPost = async (path, payload, digest, extraHeaders = {}) => {
    const res = await fetch(`${WEB}/_api/${path}`, {
      method: 'POST',
      headers: {
        Accept: 'application/json;odata=nometadata',
        'Content-Type': 'application/json;odata=nometadata',
        'X-RequestDigest': digest,
        ...extraHeaders,
      },
      body: JSON.stringify(payload),
    });
    // The interesting result is often the REFUSAL, so the response text is
    // returned rather than thrown: a 400 here is the finding, not a crash.
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };

  // ---- Pre-run reset --------------------------------------------------
  // Call this before bootstrapping. A no-op unless CLEANUP is on, so the
  // probe body reads the same either way.
  //
  // expectedId is OPTIONAL because most callers have no claimed Id to bracket
  // with, and the behaviour without one is unchanged. Supply one and every
  // request below addresses that list Id instead of the title, so a title
  // rebound mid-run cannot redirect the deletes or the recycle onto a list
  // this run never owned.
  //
  // DOCUMENTED: `web/lists(guid'<id>')` is the list resource, and `/items`
  // and `/items(<id>)` hang off it (Working with lists and list items with
  // REST, and the CSOM/REST API index, both checked 2026-09-23).
  // NOT DOCUMENTED: `/recycle` on the by-Id form appears on no Learn page.
  // It is the call this project has live evidence for with only the
  // addressing changed, and an unsupported URL fails visibly here rather
  // than losing somebody's list. One CLEANUP run settles it; see issue #611.
  const resetList = async (title, expectedId = null) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
      return false;
    }
    // An Id that is not a GUID would be spliced into a URL that addresses
    // something else, so it fails closed instead of being sent.
    const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (expectedId !== null && !GUID.test(String(expectedId))) {
      log('FAIL', `CLEANUP: '${expectedId}' is not a list Id, so nothing was deleted or `
                  + `recycled under '${title}'.`);
      return false;
    }
    const listPath = expectedId === null
      ? `web/lists/getbytitle('${title}')`
      : `web/lists(guid'${expectedId}')`;
    const found = await spGet(expectedId === null ? listPath : `${listPath}?$select=Id`);
    if (!found.ok) {
      log('INFO', `CLEANUP: no list named '${title}' to remove.`);
      return false;
    }
    // Addressing by Id still gets read back, because every destructive
    // request below rests on this one answer.
    const answeredId = found.body && found.body.Id
      ? String(found.body.Id).replace(/[{}]/g, '').toLowerCase() : null;
    if (expectedId !== null && answeredId !== String(expectedId).toLowerCase()) {
      log('FAIL', `CLEANUP: list ${expectedId} answered as ${answeredId}, so nothing was `
                  + `deleted or recycled under '${title}'.`);
      return false;
    }
    log('INFO', `CLEANUP: removing list '${title}' and its items.`);

    // Items first. Recycling the list takes them with it, but doing this
    // explicitly still clears the data if the list itself cannot be
    // removed. A locked or no-delete list would otherwise leave rows from
    // a previous run answering this run's questions.
    let digest = await getDigest();
    const items = await spGet(`${listPath}/items?$select=Id&$top=5000`);
    const rows = (items.ok && items.body && items.body.value) || [];
    for (const row of rows) {
      digest = await getDigest();
      await spPost(`${listPath}/items(${row.Id})`, {}, digest,
                   { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    }
    if (rows.length) log('INFO', `CLEANUP: deleted ${rows.length} item(s).`);
    if (rows.length === 5000) {
      log('INFO', 'CLEANUP: hit the 5000-row page limit; re-run to clear the rest.');
    }

    digest = await getDigest();
    const gone = await spPost(`${listPath}/recycle`, {}, digest);
    // The Id is named where there is one, because a repair by hand off the
    // title would go to whatever the title resolves to now.
    const which = expectedId === null ? `'${title}'` : `'${title}' (list ${expectedId})`;
    if (gone.ok) {
      log('OK', `CLEANUP: recycled list ${which}. It is restorable from the recycle bin.`);
    } else {
      log('FAIL', `CLEANUP: could not recycle ${which}: HTTP ${gone.status} ${gone.text.slice(0, 200)}`);
    }
    return gone.ok;
  };

  // ---- Result table --------------------------------------------------
  // A probe answers questions. Outcome and EVIDENCE are recorded
  // separately so a run cannot be summarised as a verdict with nothing
  // behind it.
  //
  // Every question is REGISTERED UP FRONT as NOT ESTABLISHED, and record()
  // overwrites. Appending as you go looks equivalent and is not: a probe
  // that aborts early then reports only what it reached, and prints
  // "0 not established" while most of its questions were never asked.
  //
  // STATE carries the coarse answer alongside the prose, from the five-value
  // vocabulary in test/manual/SURFACES.md: settled, open, awaiting-capture,
  // void, needs-human. There are 83 distinct outcome heads across the
  // committed evidence, which is good prose and a bad enum, so a reader
  // downstream sorts on state and quotes outcome. record() takes an explicit
  // state and that always wins; the classifier below is the default for the
  // rows nobody has ruled on yet, and it reproduces exactly what report()
  // used to derive from the outcome head.
  //
  // ABORTED is open, not settled. It is the head a probe records when its
  // fixture never built, so the question it names was never asked; classifying
  // it settled printed "N answered, 0 open" for a run that measured nothing.
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT', 'ABORTED'];
  const AWAITING_CAPTURE_HEADS = ['MANUAL', 'NOT REACHED'];
  const stateFor = (outcome) => {
    if (AWAITING_CAPTURE_HEADS.some((p) => outcome.startsWith(p))) return 'awaiting-capture';
    if (OPEN_HEADS.some((p) => outcome.startsWith(p))) return 'open';
    return 'settled';
  };
  const RESULTS = [];
  const expect = (id, question) => {
    RESULTS.push({
      id, question, outcome: 'NOT ESTABLISHED',
      evidence: 'the run did not reach this question', state: 'open',
    });
  };
  const record = (id, question, outcome, evidence, state) => {
    const next = { question, outcome, evidence, state: state || stateFor(outcome) };
    const row = RESULTS.find((r) => r.id === id);
    if (row) {
      Object.assign(row, next);
    } else {
      RESULTS.push({ id, ...next });
    }
    const level = outcome === 'PASS' ? 'OK' : outcome === 'FAIL' ? 'FAIL' : 'INFO';
    log(level, `${id}: ${outcome}. ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };

  // ---- Fixtures (#559) -----------------------------------------------
  // Why a response carries no reading, or null when it does. Learn documents
  // 429 and 503 as the two SharePoint Online throttle statuses.
  const unanswered = (r) => {
    if (r.ok) {
      return r.body !== null && typeof r.body === 'object'
        ? null : `answered HTTP ${r.status} with no payload`;
    }
    if (r.status === 429 || r.status === 503) return `was throttled (HTTP ${r.status})`;
    if (r.status === 408) return 'timed out (HTTP 408)';
    if (r.status === 401 || r.status === 403) return `was not authorised (HTTP ${r.status})`;
    return isRefusal(r.status) ? `was refused (HTTP ${r.status})` : `did not answer (HTTP ${r.status})`;
  };

  // A voided row keeps its question and is counted apart from open and answered.
  const voidDependents = (ids, reason) => {
    for (const id of ids) {
      const row = RESULTS.find((r) => r.id === id);
      record(id, row ? row.question : id, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // `read` resolves to a harness response ({ ok, status, body }). `declared`
  // maps each property the measurement depends on to a value or a predicate.
  // PASS needs every one read back; otherwise FAIL, void `dependents`, false.
  const establishFixture = async (id, read, declared, dependents) => {
    const row = RESULTS.find((r) => r.id === id);
    const question = row ? row.question : id;
    const problems = [];
    const seen = [];
    let got = null;
    let threw = false;
    try {
      got = await read();
    } catch (err) {
      threw = true;
      problems.push(`the read threw: ${err && err.message ? err.message : String(err)}`);
    }
    if (!threw) {
      const silent = got && typeof got === 'object' ? unanswered(got) : 'returned no response';
      if (silent) problems.push(`the read ${silent}`);
    }
    if (!problems.length) {
      for (const [name, want] of Object.entries(declared)) {
        if (!Object.prototype.hasOwnProperty.call(got.body, name) || got.body[name] === undefined) {
          problems.push(`${name} is absent from the payload`);
          continue;
        }
        const value = got.body[name];
        seen.push(`${name}=${JSON.stringify(value)}`);
        const held = typeof want === 'function' ? want(value) === true : value === want;
        if (!held) {
          problems.push(`${name} differs: read ${JSON.stringify(value)}, declared `
            + (typeof want === 'function' ? 'by a predicate it fails' : JSON.stringify(want)));
        }
      }
    }
    if (!problems.length) {
      record(id, question, 'PASS', `read back ${seen.join(', ')}`);
      return true;
    }
    record(id, question, 'FAIL', problems.join('; ') + (seen.length ? `; read ${seen.join(', ')}` : ''));
    voidDependents(dependents, `the fixture ${id} did not hold: ${problems.join('; ')}`);
    return false;
  };

  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.state.padEnd(16)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    // Counted off state rather than off the outcome head, so the summary and
    // the per-row state can never disagree. awaiting-capture stays open until
    // a person records the observation. void does NOT: the control row names a
    // reason this identity can never answer, so counting it open reports work
    // that no re-run can clear, and counting it answered claims a measurement
    // nobody made. It gets its own number.
    const voided = RESULTS.filter((r) => r.state === 'void').length;
    const open = RESULTS.filter((r) => r.state !== 'settled' && r.state !== 'void').length;
    const waiting = RESULTS.filter((r) => r.state === 'awaiting-capture').length;
    const answered = RESULTS.length - open - voided;
    console.log(`${RESULTS.length} question(s); ${answered} answered, ${open} open, ${voided} voided.`);
    if (waiting) {
      console.log(`${waiting} of those are waiting on an observation somebody has to make.`);
    }
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };
  // Shared observation vocabulary v1: how a probe says "this read did not
  // establish what it was supposed to".
  //
  // This is the NOT ESTABLISHED head from _probe_harness.js.j2 reached from
  // the READ side, not a second vocabulary beside it. Everything here ends in
  // record(id, question, 'NOT ESTABLISHED', why), which stateFor() already
  // classifies `open`.
  //
  // A SHAPE RATHER THAN A CONVENTION, because the failure it exists against is
  // a row recorded OBSERVED from a field nothing ever read. A reading is
  // either established, carrying a value every field of which was read, or
  // unestablished, carrying the reason. There is no third shape and no way to
  // the value except mustRead(), so an observation cannot reach a partial one
  // by forgetting a check.
  class Unestablished extends Error {}
  const established = (value) => ({ established: true, value, why: null });
  const unestablished = (why) => ({ established: false, value: null, why });
  const mustRead = (reading) => {
    if (!reading.established) throw new Unestablished(reading.why);
    return reading.value;
  };
  // A field the claim RESTS on, checked where it is read rather than where it
  // is reported.
  const mustCarry = (ok, what) => {
    if (!ok) throw new Unestablished(what);
  };
  // What came back, never what it said: a principal's Title is somebody's
  // display name and a transcript gets pasted into a pull request.
  const shapeOf = (value) => {
    if (value === null) return 'null';
    if (Array.isArray(value)) return `an array of ${value.length}`;
    if (typeof value === 'string') return `a string of ${value.length} char(s)`;
    return typeof value;
  };
  // One row, from a body that may fail to establish it at any depth. A shape
  // nobody predicted is a measurement of this tenant and never a reason to
  // abort the questions after it, so a throw inside `body` is RECORDED here
  // rather than propagated. `body` returns the evidence for an OBSERVED row,
  // or { outcome, evidence, state } for any other head.
  const observe = async (id, question, body) => {
    let found;
    try {
      found = await body();
    } catch (err) {
      found = {
        outcome: 'NOT ESTABLISHED',
        evidence: err instanceof Unestablished
          ? err.message
          : `the observation threw: ${String(err)}`,
      };
    }
    const row = typeof found === 'string'
      ? { outcome: 'OBSERVED', evidence: found }
      : found;
    record(id, question, row.outcome, row.evidence, row.state);
  };

  log('INFO', 'probe revision 78f41d72. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe LastBinding';
  const OWNERSHIP = 'dbml-sharepoint last-binding-removal probe list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${LIST}')`;

  const Q = {
    list: 'A list this run created carries its marker and Id and still inherits',
    break: 'breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false) is accepted and the list then reads unique',
    sole: "The list then holds exactly one binding, this account's own, at a level other than 'Limited Access'",
    removal: "What does removeroleassignment answer for the LAST role assignment on a list, this account's own",
    readback: 'After it, what do the GETs Phase 4.2 makes after its last removal answer, and what would the deploy conclude',
    enumeration: 'After it, what does the role-assignment enumeration return over the settle window',
    unique: 'After it, does the list still read HasUniqueRoleAssignments=true',
    delete: 'After it, can this account still delete the list',
  };

  expect('access.list-acl.fixture-last-binding-list', Q.list);
  expect('access.list-acl.fixture-last-binding-break', Q.break);
  expect('access.list-acl.fixture-last-binding-sole-operator', Q.sole);
  expect('access.list-acl.last-binding-removal', Q.removal);
  expect('access.list-acl.after-last-binding-readback', Q.readback);
  expect('access.list-acl.after-last-binding-enumeration', Q.enumeration);
  expect('access.list-acl.after-last-binding-unique', Q.unique);
  expect('access.list-acl.after-last-binding-delete', Q.delete);

  const ALL = RESULTS.map((r) => r.id);
  // What rests on each dependency: everything after it, in registration order.
  const AFTER_LIST = ALL.slice(1);
  const AFTER_BREAK = ALL.slice(2);
  const OBSERVED_ROWS = ALL.slice(3);

  if (!CONFIRMED) {
    log('INFO', `Would check that this account is a site collection administrator, create`);
    log('INFO', `a LIST '${LIST}', break its role inheritance with`);
    log('INFO', 'copyRoleAssignments=false, remove the one role assignment the break leaves');
    log('INFO', "(this account's own), record what the list then reports over 8 seconds,");
    log('INFO', 'and DELETE the list. Run it on a disposable site.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  const NOMETADATA = 'application/json;odata=nometadata';
  const VERBOSE = 'application/json;odata=verbose';
  // The window settleBindings uses in the deploy: five reads, 2000 ms apart.
  const SETTLE_READS = 5;
  const SETTLE_MS = 2000;
  // HasUniqueRoleAssignments lags a break (MEASURED 2026-09-09, library.access.unique-permissions-library).
  const UNIQUE_TRIES = 6;
  const BINDING_PAGE_LIMIT = 50;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const api = (path) => `${WEB}/_api/${path}`;
  const guidOf = (value) => (
    value == null ? null : String(value).replace(/[{}]/g, '').toLowerCase());

  // A response text is SharePoint's words, which can carry a site URL or a login name.
  const scrub = (text) => String(text)
    .replace(/https?:\/\/[^\s'"]+/g, '<url>')
    .replace(/\/(sites|teams)\/[^\s'"]+/g, '/$1/<site>')
    .replace(/[^\s'"|:]+@[^\s'"]+/g, '<account>');

  // no-store on every read, as the deploy sends: a by-title read can otherwise be the
  // browser's cached answer (MEASURED 2026-09-13, list-identity-cache-probe.js).
  const read = async (url, accept = NOMETADATA) => {
    try {
      const res = await fetch(url, { headers: { Accept: accept }, cache: 'no-store' });
      return { ok: res.ok, status: res.status, body: await res.json().catch(() => null) };
    } catch (err) {
      return { ok: false, status: 0, body: null, threw: String(err) };
    }
  };

  // Not an answer at all: a throttle, a timeout, or a request that never came back.
  const silent = (r) => Boolean(r.threw) || r.status === 408 || r.status === 429 || r.status === 503;

  const describeRead = (r) => {
    if (r.threw) return `the request threw (${scrub(r.threw)})`;
    if (r.ok) return `HTTP ${r.status}`;
    const said = r.text !== undefined ? r.text : JSON.stringify(r.body);
    return `HTTP ${r.status} ${scrub(said).slice(0, 200)}`;
  };

  const closeAll = (ids, outcome, why, state) => {
    for (const id of ids) record(id, RESULTS.find((r) => r.id === id).question, outcome, why, state);
  };

  // A dependency computed from reads rather than one response: PASS only when it held.
  const settleFixture = (id, held, evidence, dependents) => {
    record(id, RESULTS.find((r) => r.id === id).question, held ? 'PASS' : 'FAIL', evidence);
    if (!held) voidDependents(dependents, `the fixture ${id} did not hold: ${evidence}`);
    return held;
  };

  // ---- identity ----------------------------------------------------------
  // Role-assignment writes have no documented by-Id form, so each is bracketed by
  // title and marker, as `withOwnedList` brackets them in deploy/_acls.js.j2.
  let ownedId = null;
  let rebound = null;

  const proveOwned = async (when) => {
    const res = await read(api(`${listPath}?$select=Id,Title,Description`));
    if (!res.ok || !res.body) {
      throw new Error(`the identity of '${LIST}' could not be read ${when} (${describeRead(res)})`);
    }
    const now = guidOf(res.body.Id);
    if (now === null || now !== ownedId || res.body.Description !== OWNERSHIP) {
      throw new Error(`the title '${LIST}' resolves to list ${now} ${when}, and this run `
        + `claimed ${ownedId} carrying its marker`);
    }
  };

  const withOwnedList = async (what, request) => {
    await proveOwned(`before ${what}`);
    const result = await request();
    await proveOwned(`after ${what}`);
    return result;
  };

  // After the removal no write goes by title, so a read that answers another list
  // only has to be noticed, and every row it touched is then left open.
  const noteIdentity = (where, id, marker) => {
    if (rebound !== null || id === undefined) return;
    const now = guidOf(id);
    if (now !== ownedId || (marker !== undefined && marker !== OWNERSHIP)) {
      rebound = `${where} answered list ${now} where this run claimed ${ownedId}`;
    }
  };

  // ---- the two enumerations ---------------------------------------------
  // The probe's own read is the URL enumeration-is-monotonic was measured on; the
  // deploy's is scopeBindings' URL. Both are read to the last page.
  const PROBE_BINDING_QUERY = 'roleassignments?$expand=Member,RoleDefinitionBindings&$top=200';
  const DEPLOY_BINDING_QUERY = 'roleassignments?$expand=RoleDefinitionBindings'
    + '&$select=PrincipalId,RoleDefinitionBindings/Id,RoleDefinitionBindings/Name';

  const readPages = async (url, accept) => {
    const verbose = accept === VERBOSE;
    const entities = [];
    let next = url;
    let pages = 0;
    let status = null;
    while (next) {
      if (pages >= BINDING_PAGE_LIMIT) {
        return { kind: 'silent', why: `still continuing after ${pages} page(s), so the read stopped short of the end` };
      }
      const r = await read(next, accept);
      if (silent(r)) return { kind: 'silent', why: `page ${pages + 1} ${describeRead(r)}` };
      if (!r.ok) return { kind: 'refused', status: r.status, why: `page ${pages + 1} answered ${describeRead(r)}` };
      if (status === null) status = r.status;
      const holder = verbose ? (r.body && r.body.d) : r.body;
      const rows = holder ? (verbose ? holder.results : holder.value) : undefined;
      if (!Array.isArray(rows)) {
        return { kind: 'malformed', why: `page ${pages + 1} carried ${shapeOf(rows)} where its rows belong` };
      }
      entities.push(...rows);
      pages += 1;
      // `d.__next` is the verbose spelling and `odata.nextLink` the nometadata one.
      const link = verbose ? holder.__next : (holder['odata.nextLink'] || holder.__next);
      if (link != null && link !== '' && typeof link !== 'string') {
        return { kind: 'malformed', why: `page ${pages} carried a continuation of ${shapeOf(link)}, which cannot be followed` };
      }
      next = link || null;
    }
    return { kind: 'rows', status, pages, entities };
  };

  // Every field a row is placed by is a prerequisite, as in operator-safety-grant-probe.js.
  const enumerate = async () => {
    const got = await readPages(api(`${listPath}/${PROBE_BINDING_QUERY}`), NOMETADATA);
    if (got.kind !== 'rows') return got;
    try {
      const rows = [];
      for (const entity of got.entities) {
        mustCarry(entity !== null && typeof entity === 'object',
          `the enumeration returned ${shapeOf(entity)} where an entity belongs`);
        const principalId = Number(entity.PrincipalId);
        mustCarry(Number.isFinite(principalId) && principalId > 0,
          `a role assignment came back with a PrincipalId of ${shapeOf(entity.PrincipalId)}`);
        const member = entity.Member || {};
        const levels = entity.RoleDefinitionBindings;
        mustCarry(Array.isArray(levels),
          `principal ${principalId} carried ${shapeOf(levels)} where its RoleDefinitionBindings belong`);
        for (const level of levels) {
          mustCarry(level !== null && typeof level === 'object',
            `principal ${principalId} carried ${shapeOf(level)} where a role definition belongs`);
          const levelId = Number(level.Id);
          mustCarry(Number.isFinite(levelId) && levelId > 0,
            `a binding for principal ${principalId} carried a role definition Id of ${shapeOf(level.Id)}`);
          mustCarry(typeof level.Name === 'string',
            `a binding for principal ${principalId} carried a level Name of ${shapeOf(level.Name)}`);
          rows.push({
            principalId,
            titleLength: member.Title == null ? null : String(member.Title).length,
            principalType: member.PrincipalType,
            levelId,
            levelName: level.Name,
          });
        }
      }
      return { ...got, rows };
    } catch (err) {
      return {
        kind: 'malformed',
        why: err instanceof Unestablished ? err.message : `the enumeration could not be parsed: ${String(err)}`,
      };
    }
  };

  // The checks scopeBindings makes; each one throws in the deploy.
  const deployEnumeration = async () => {
    const got = await readPages(api(`${listPath}/${DEPLOY_BINDING_QUERY}`), VERBOSE);
    if (got.kind !== 'rows') return got;
    const rows = [];
    for (const row of got.entities) {
      if (!row || row.PrincipalId == null) return { kind: 'malformed', why: 'an entry without PrincipalId' };
      const bindings = row.RoleDefinitionBindings && row.RoleDefinitionBindings.results;
      if (!Array.isArray(bindings)) {
        return { kind: 'malformed', why: `principal ${row.PrincipalId} without a RoleDefinitionBindings.results array` };
      }
      for (const binding of bindings) {
        if (binding == null || binding.Id == null || typeof binding.Name !== 'string') {
          return { kind: 'malformed', why: `a binding for principal ${row.PrincipalId} without its Id or Name` };
        }
        rows.push({ key: `${row.PrincipalId}:${binding.Id}`, name: binding.Name });
      }
    }
    return { ...got, rows };
  };

  let myId = null;

  const describeRows = (rows) => (
    rows.length === 0
      ? 'no rows'
      : rows.map((r) => (
        `principal ${r.principalId} (${r.principalId === myId ? 'this account' : 'another principal'}, `
        + `PrincipalType ${r.principalType}, `
        + `title ${r.titleLength === null ? 'absent' : `${r.titleLength} chars`}) `
        + `-> level ${r.levelId} '${r.levelName}'`
      )).join('; ')
  );

  // ---- the deploy's read-back, exactly as Phase 4.2 sends it --------------
  // ownedListIdentity reads the list through probeListShapeByTitle, with this $select.
  const SHAPE_SELECT = [
    'Id', 'Title', 'BaseTemplate', 'ContentTypesEnabled', 'Description',
    'EnableVersioning', 'EnableMinorVersions', 'MajorVersionLimit',
    'ValidationFormula', 'ValidationMessage',
  ].join(',');

  const deployReadback = async () => {
    const steps = [];
    const shapeRead = async (label) => {
      const r = await read(api(`${listPath}?$select=${SHAPE_SELECT}`), VERBOSE);
      const d = r.ok && r.body ? r.body.d : null;
      if (d) noteIdentity(label, d.Id, d.Description);
      steps.push(`${label}: ${describeRead(r)}${d ? ` carrying list ${guidOf(d.Id)}` : ''}`);
      if (silent(r)) return 'silent';
      return r.ok ? null : `the deploy throws at ${label}, which answered HTTP ${r.status}`;
    };

    let stop = await shapeRead("the list read that closes the removal's bracket");
    if (stop === null) stop = await shapeRead("the list read that opens settleBindings' bracket");
    let judged = null;
    for (let attempt = 0; stop === null && judged === null && attempt < SETTLE_READS; attempt += 1) {
      if (attempt > 0) await sleep(SETTLE_MS);
      const e = await deployEnumeration();
      const label = `enumeration ${attempt + 1}`;
      if (e.kind === 'silent') {
        steps.push(`${label}: ${e.why}`);
        stop = 'silent';
      } else if (e.kind !== 'rows') {
        steps.push(`${label}: ${e.why}`);
        stop = `the deploy throws at ${label}: ${e.why}`;
      } else {
        // The exact-mode judge with nothing declared: any binding but 'Limited Access' is a stray.
        const strays = e.rows.filter((row) => row.name !== 'Limited Access');
        steps.push(`${label}: HTTP ${e.status}, ${e.rows.length} binding(s)`
          + `${e.rows.length ? ` (${e.rows.map((row) => `${row.key} '${row.name}'`).join(', ')})` : ''}`);
        if (strays.length === 0) judged = attempt + 1;
      }
    }
    // settleBindings closes its bracket before its caller looks at the judge's complaint.
    if (stop === null) stop = await shapeRead("the list read that closes settleBindings' bracket");
    if (stop === null && judged === null) {
      stop = `the deploy aborts: all ${SETTLE_READS} enumerations still reported a binding other `
        + "than 'Limited Access'";
    }
    if (stop === 'silent') return { silent: true, steps };
    return {
      silent: false,
      steps,
      verdict: stop !== null ? stop
        : `the deploy reports the scope holds exactly the 0 declared role assignment(s): `
          + `enumeration ${judged} reported no binding other than 'Limited Access', and every `
          + 'read answered 2xx',
    };
  };

  // ---- who is running this, before anything is written -------------------
  const me = await read(api('web/currentuser?$select=Id,IsSiteAdmin'));
  const meId = me.ok && me.body ? Number(me.body.Id) : NaN;
  if (!me.ok || !me.body || typeof me.body.IsSiteAdmin !== 'boolean'
      || !Number.isFinite(meId) || meId <= 0) {
    closeAll(ALL, 'NOT ESTABLISHED',
      `web/currentuser answered ${describeRead(me)} without a usable Id and IsSiteAdmin, so this `
      + 'run could not tell whether it may take a list\'s last role assignment away, or match a '
      + 'binding to this account. Nothing was written.');
    return report();
  }
  if (me.body.IsSiteAdmin !== true) {
    closeAll(ALL, 'NOT REACHED',
      'this account is not a site collection administrator (web/currentuser reports '
      + 'IsSiteAdmin=false). Removing the last role assignment on a list may leave nobody but an '
      + 'administrator able to reach it. Nothing was written. Re-run as a site collection '
      + 'administrator on a disposable site.', 'void');
    return report();
  }
  myId = meId;

  // ---- the scratch title -------------------------------------------------
  // A title is never ownership: only a list carrying this probe's exact marker is
  // cleared, and only by its Id with CLEANUP on.
  const claim = await read(api(`${listPath}?$select=Id,Description`));
  let refusal = null;
  if (claim.status !== 404) {
    const leftover = claim.ok && claim.body ? guidOf(claim.body.Id) : null;
    if (!claim.ok || !claim.body) {
      refusal = `could not read whether the title '${LIST}' is occupied (${describeRead(claim)}). `
        + 'That is not the title being free, so nothing was recycled or created.';
    } else if (claim.body.Description !== OWNERSHIP || leftover === null) {
      refusal = `a list titled '${LIST}' already exists without this probe's ownership marker, `
        + 'so this run did not make it and will not touch it. Rename or remove it, and paste again.';
    } else if (!(await resetList(LIST, leftover))) {
      refusal = `'${LIST}' (list ${leftover}) is left over from an earlier run of this probe. `
        + (CLEANUP ? 'The CLEANUP recycle did not complete, as the line above says.'
          : 'Set CLEANUP = true to recycle it by its Id, and paste again.');
    } else {
      const after = await read(api(`${listPath}?$select=Id`));
      if (after.status !== 404) {
        refusal = `'${LIST}' still answers ${describeRead(after)} after the CLEANUP recycle, so `
          + 'nothing was created over it.';
      }
    }
  }
  if (refusal !== null) {
    record('access.list-acl.fixture-last-binding-list', Q.list, 'ABORTED', refusal);
    voidDependents(AFTER_LIST, 'the scratch title was not this run\'s to use, so nothing was created.');
    return report();
  }

  let createSent = false;
  let removalSent = false;

  const measure = async () => {
    // ---- fixture-last-binding-list ---------------------------------------
    createSent = true;
    let digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: LIST,
      BaseTemplate: 100,
      Description: OWNERSHIP,
    }, digest);
    if (!made.ok) {
      // Refused, so nothing of this run's exists to delete.
      createSent = false;
      settleFixture('access.list-acl.fixture-last-binding-list', false,
        `could not create '${LIST}': ${describeRead(made)}`, AFTER_LIST);
      return;
    }
    const createdId = guidOf(made.body && made.body.Id);
    const shape = await read(api(`${listPath}?$select=Id,Description,HasUniqueRoleAssignments`));
    // The delete at the end goes by the Id this run made; the read-back supplies it only
    // when the create answered without one.
    const readBackId = shape.ok && shape.body && shape.body.Description === OWNERSHIP
      ? guidOf(shape.body.Id) : null;
    ownedId = createdId !== null ? createdId : readBackId;
    const listHeld = await establishFixture('access.list-acl.fixture-last-binding-list',
      async () => shape, {
        Id: (value) => guidOf(value) !== null && guidOf(value) === ownedId,
        Description: OWNERSHIP,
        HasUniqueRoleAssignments: false,
      }, AFTER_LIST);
    if (!listHeld) return;

    // ---- fixture-last-binding-break --------------------------------------
    digest = await getDigest();
    const broke = await withOwnedList(`breakroleinheritance on '${LIST}'`, () => spPost(
      `${listPath}/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)`,
      {}, digest));
    if (!broke.ok) {
      settleFixture('access.list-acl.fixture-last-binding-break', false,
        `breakroleinheritance answered ${describeRead(broke)}`, AFTER_BREAK);
      return;
    }
    const polls = [];
    let unique = null;
    for (let attempt = 0; attempt < UNIQUE_TRIES; attempt += 1) {
      if (attempt > 0) await sleep(SETTLE_MS);
      unique = await read(api(`${listPath}?$select=Id,HasUniqueRoleAssignments`));
      polls.push(`read ${attempt + 1}: ${describeRead(unique)}, HasUniqueRoleAssignments=`
        + `${String(unique.ok && unique.body ? unique.body.HasUniqueRoleAssignments : null)}`);
      if (unique.ok && unique.body && unique.body.HasUniqueRoleAssignments === true) break;
    }
    log('INFO', `HasUniqueRoleAssignments after the break: ${polls.join('; ')}`);
    const brokeHeld = await establishFixture('access.list-acl.fixture-last-binding-break',
      async () => unique, {
        Id: (value) => guidOf(value) === ownedId,
        HasUniqueRoleAssignments: true,
      }, AFTER_BREAK);
    if (!brokeHeld) return;

    // ---- fixture-last-binding-sole-operator ------------------------------
    const left = await enumerate();
    if (left.kind !== 'rows') {
      settleFixture('access.list-acl.fixture-last-binding-sole-operator', false,
        `the enumeration after the break ${left.kind === 'refused' ? 'was refused' : 'was not read'}: `
        + `${left.why}`, OBSERVED_ROWS);
      return;
    }
    const target = left.rows[0];
    const sole = left.rows.length === 1 && target.principalId === myId
      && target.levelName !== 'Limited Access';
    if (!settleFixture('access.list-acl.fixture-last-binding-sole-operator', sole,
      `this account is principal ${myId}; the break left ${left.rows.length} binding(s), read `
      + `over ${left.pages} page(s): ${describeRows(left.rows)}`
      + (sole ? '' : '. Removing this account\'s binding would not remove the last role '
        + 'assignment on the scope, so it was not sent.'), OBSERVED_ROWS)) {
      return;
    }

    // ---- last-binding-removal --------------------------------------------
    digest = await getDigest();
    await proveOwned('before the removal');
    removalSent = true;
    let removal;
    try {
      removal = await spPost(
        `${listPath}/roleassignments/removeroleassignment(principalid=${target.principalId},roleDefId=${target.levelId})`,
        {}, digest);
    } catch (err) {
      removal = { ok: false, status: 0, text: '', threw: String(err) };
    }
    const authorisation = removal.status === 401 || removal.status === 403;
    record('access.list-acl.last-binding-removal', Q.removal,
      silent(removal) ? 'NOT ESTABLISHED' : removal.ok ? 'ACCEPTED' : 'REFUSED',
      `removeroleassignment(principalid=${target.principalId},roleDefId=${target.levelId}), `
      + `this account's '${target.levelName}' binding and the only one on the scope, `
      + (removal.threw ? `threw: ${scrub(removal.threw)}`
        : `answered HTTP ${removal.status}: ${scrub(removal.text).slice(0, 260) || '(empty body)'}`)
      + (authorisation ? '. The refusal is an authorisation answer' : '')
      + (silent(removal) ? '. That is not an answer; the rows below still say what the scope reported' : '')
      + (removal.ok ? '. A 200 here is not evidence by itself: MEASURED 2026-09-22, this endpoint '
        + 'answered 200 for a principal and level that do not exist, so the enumeration row says '
        + 'whether it took' : ''));

    // ---- after-last-binding-readback -------------------------------------
    // Immediately, as the deploy reads: its first request after the removal is this.
    const back = await deployReadback();
    record('access.list-acl.after-last-binding-readback', Q.readback,
      back.silent ? 'NOT ESTABLISHED' : 'OBSERVED',
      back.silent
        ? 'a read did not answer, which the deploy retries and this probe does not, so what the '
          + `deploy concludes is unknown; re-run. ${back.steps.join('; ')}.`
        : `${back.verdict}. In order: ${back.steps.join('; ')}.`);

    // ---- after-last-binding-enumeration, after-last-binding-unique --------
    // One window, both reads each time; the flag read carries the Id, which re-proves
    // the title between enumerations.
    const enumReads = [];
    const uniqueReads = [];
    const present = [];
    const absent = [];
    let enumHeard = 0;
    let uniqueHeard = 0;
    for (let attempt = 0; attempt < SETTLE_READS; attempt += 1) {
      if (attempt > 0) await sleep(SETTLE_MS);
      const n = attempt + 1;
      const e = await enumerate();
      if (e.kind === 'rows') {
        enumHeard += 1;
        const held = e.rows.some(
          (r) => r.principalId === target.principalId && r.levelId === target.levelId);
        (held ? present : absent).push(n);
        enumReads.push(`read ${n}: HTTP ${e.status}, ${e.rows.length} row(s) over ${e.pages} `
          + `page(s): ${describeRows(e.rows)}`);
      } else if (e.kind === 'refused') {
        enumHeard += 1;
        enumReads.push(`read ${n}: ${e.why}`);
      } else {
        enumReads.push(`read ${n}: ${e.why}, not an answer`);
      }
      const u = await read(api(`${listPath}?$select=Id,HasUniqueRoleAssignments`));
      if (u.ok && u.body) noteIdentity(`the flag read ${n}`, u.body.Id);
      const flag = u.ok && u.body ? u.body.HasUniqueRoleAssignments : undefined;
      if (silent(u) || (u.ok && typeof flag !== 'boolean')) {
        uniqueReads.push(`read ${n}: ${describeRead(u)}${u.ok ? ` carrying ${shapeOf(flag)}` : ''}, not an answer`);
      } else {
        uniqueHeard += 1;
        uniqueReads.push(`read ${n}: ${describeRead(u)}${u.ok ? `, HasUniqueRoleAssignments=${flag}` : ''}`);
      }
    }
    const span = `over ${(SETTLE_READS - 1) * SETTLE_MS} ms`;
    const which = (reads) => (reads.length ? `read(s) ${reads.join(', ')}` : 'no read');
    let summary = `none of the ${SETTLE_READS} reads ${span} answered`;
    if (enumHeard && present.length + absent.length === 0) {
      summary = `no read ${span} returned rows`;
    } else if (enumHeard) {
      summary = `this account's removed binding (principal ${target.principalId}, level `
        + `${target.levelId}) read present on ${which(present)} and absent on ${which(absent)}, ${span}`;
    }
    record('access.list-acl.after-last-binding-enumeration', Q.enumeration,
      enumHeard ? 'OBSERVED' : 'NOT ESTABLISHED', `${summary}: ${enumReads.join('; ')}.`);
    record('access.list-acl.after-last-binding-unique', Q.unique,
      uniqueHeard ? 'OBSERVED' : 'NOT ESTABLISHED',
      `${uniqueHeard ? '' : `none of the ${SETTLE_READS} reads answered. `}`
      + `HasUniqueRoleAssignments ${span}: ${uniqueReads.join('; ')}.`);

    if (rebound !== null) {
      closeAll(OBSERVED_ROWS, 'NOT ESTABLISHED',
        `the title '${LIST}' answered another list during the run (${rebound}), so which list `
        + 'the removal and these reads reached is unknown. Nothing further was written by title.');
    }
  };

  // ---- after-last-binding-delete, and the cleanup it is ------------------
  // By Id, the documented form, so a rebound title cannot redirect it. The read before
  // it is what makes a 404 after it mean gone rather than hidden.
  const removeList = async () => {
    if (ownedId === null) {
      if (createSent) {
        log('FAIL', `this run could not establish the Id of '${LIST}', so it deleted nothing. If `
          + 'a list with that title carries this probe\'s Description, delete it by hand.');
      }
      return;
    }
    const byId = `web/lists(guid'${ownedId}')`;
    const before = await read(api(`${byId}?$select=Id`));
    let gone;
    try {
      const digest = await getDigest();
      gone = await spPost(byId, {}, digest, { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    } catch (err) {
      gone = { ok: false, status: 0, text: '', threw: String(err) };
    }
    const after = await read(api(`${byId}?$select=Id`));
    const confirmed = gone.ok && before.ok && after.status === 404;
    const facts = `the read by Id answered ${describeRead(before)} before the DELETE, the DELETE `
      + `${gone.threw ? `threw (${scrub(gone.threw)})` : `answered ${describeRead(gone)}`}, and the `
      + `read by Id answered ${describeRead(after)} after it`;
    if (removalSent && rebound === null) {
      record('access.list-acl.after-last-binding-delete', Q.delete,
        silent(gone) ? 'NOT ESTABLISHED' : gone.ok ? 'ACCEPTED' : 'REFUSED',
        `${confirmed ? 'the list is gone' : before.ok ? 'the list was not read back absent'
          : 'the list was not readable by Id before the DELETE, so a 404 after it cannot say gone'}: `
        + `${facts}.`);
    }
    log(confirmed ? 'OK' : 'FAIL', confirmed
      ? `deleted '${LIST}' (list ${ownedId}) and read it back absent. Learn documents a DELETE of `
        + 'a list as a recycle, so it is in the site recycle bin.'
      : `'${LIST}' (list ${ownedId}) may still exist: ${facts}. Delete it by hand as a site `
        + 'collection administrator, going by the Id rather than the title.');
  };

  try {
    await measure();
  } catch (err) {
    log('FAIL', `the measurement pass stopped: ${scrub(err && err.message ? err.message : String(err))}`);
  } finally {
    try {
      await removeList();
    } catch (err) {
      log('FAIL', `the delete of '${LIST}' (list ${ownedId}) threw: ${scrub(String(err))}. `
        + 'Delete it by hand as a site collection administrator, going by the Id.');
    }
  }

  // After the delete, so the block the operator copies back says what it did.
  return report();
})();
