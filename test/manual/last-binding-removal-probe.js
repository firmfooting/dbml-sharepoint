
/** ---- dbml-sharepoint PROBE: REMOVING THE LAST ROLE ASSIGNMENT ON A LIST ----
 *
 * REVISION: 2ea9271b
 *
 * THE REQUEST UNDER TEST (issue #667). A `list_permissions` policy with
 * `reconcile: exact` and no assignments makes Phase 4.2 in
 * `deploy/_acls.js.j2` remove every direct binding on the list except
 * 'Limited Access', and nothing exempts the operator's own. MEASURED
 * 2026-09-22 by operator-safety-grant-probe.js on two sites: a break with
 * copyRoleAssignments=false left one binding, this account's own USER
 * binding at 'Full Control'. So the prune ends by removing the LAST role
 * assignment on the scope. That probe never sends it, because it grants the
 * owner group first.
 *
 * WHAT THIS RUN ANSWERS. This is the site collection administrator half of
 * #667. It answers whether SharePoint accepts the removal of the last direct
 * binding on a list, and what the scope then reports: the enumeration, the
 * unique-permissions flag, the deploy's own read-back and what the deploy
 * would conclude from it, and whether the list can still be deleted. That
 * an administrator keeps access afterwards is Learn's prediction, not an
 * unknown: "Choose administrators and owners for the administration
 * hierarchy" says site collection administrators have Full Control of all
 * site content "even if they do not have explicit permissions", and
 * `templates/list.js.j2` already cites it. That page is written for
 * SharePoint Server; "Default SharePoint groups" says the same of site
 * admins in Microsoft 365 in fewer words. This run tests the prediction on
 * SharePoint Online.
 *
 * WHAT IT DOES NOT ANSWER. The deploy's documented operator is a Site Owner
 * (website/docs/artifacts/deploy.md, Requirements), and an owner who is not
 * an administrator has no such standing. What that account can reach once
 * its binding is gone needs a second identity, and nothing here measures it.
 *
 * WHY A PROBE OF ITS OWN. The owner grant is the premise of the sibling
 * probe's removal row, and its questions share one list and one restore
 * pass. This one needs a list nobody else is ever granted on, and it ends by
 * deleting the list rather than restoring it.
 *
 * WHAT DOCUMENTATION SAYS about the removal itself: nothing. Checked
 * 2026-09-27, the RoleAssignmentCollection pages and "Role, inheritance,
 * elevation of privilege, and password changes in SharePoint" do not say
 * whether the last role assignment on a scope can be removed, or what the
 * scope reports once it has been.
 *
 * DEPENDED ON. Each is asserted, and a failure VOIDS every row after it:
 *   access.list-acl.fixture-last-binding-list
 *     A list this run created carries its marker and Id and still inherits.
 *   access.list-acl.fixture-last-binding-break
 *     breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)
 *     is accepted and the list then reads HasUniqueRoleAssignments=true.
 *   access.list-acl.fixture-last-binding-direct
 *     The deploy's own pruning snapshot, read once the break has settled and
 *     to its last page, holds at least one binding other than 'Limited
 *     Access'. Not "exactly one, this account's": that is a measurement, and
 *     the sibling probe's header explains why asserting it is wrong.
 *
 * OBSERVED. Recorded as they came back, never asserted:
 *   access.list-acl.last-binding-removal
 *     Every removal the exact prune sends, in its order, each with its
 *     status and body, and whose binding went last.
 *   access.list-acl.after-last-binding-readback
 *     Every GET Phase 4.2 makes after its last removal, in its order: the
 *     list read that closes that removal's bracket, the one that opens
 *     settleBindings', the enumeration up to five times 2000 ms apart, the
 *     read that closes settleBindings', then surveyDescendants' items read
 *     to its last page. Each answer, and what the deploy would conclude from
 *     all of them, including a conclusion it reaches by reading a 200 that
 *     carries no results array as zero rows.
 *   access.list-acl.after-last-binding-enumeration
 *     Five enumerations over 8000 ms, every page, each row with its
 *     principal type and level, because this enumeration was measured to
 *     flap (access.list-acl.enumeration-is-monotonic).
 *   access.list-acl.after-last-binding-unique
 *     HasUniqueRoleAssignments on each of the same five reads.
 *   access.list-acl.after-last-binding-delete
 *     What the DELETE that ends the run answers, and whether a read by Id
 *     then finds the list gone. It is sent only once a read by Id shows this
 *     probe's marker, and every request goes by Id, so the row is recorded
 *     even when the title came to answer another list.
 *
 * The after- rows describe the scope once a removal was SENT, whatever it
 * answered, so a refused call that removed the binding anyway is visible.
 * No principal's title is printed, only its length. Every response text has
 * this site's URL, host and path and this account's login name, email and
 * display name replaced first, then URLs, hosts and account names masked by
 * pattern, because a transcript gets pasted into a pull request.
 *
 * FIDELITY TO THE DEPLOY. WHICH PATH: an exact policy requires
 * break_inheritance: true (model/sections/_permissions.py), and Phase 1
 * breaks every inheriting exact-mode list as soon as it is created or
 * adopted (early isolation in deploy/_lists.js.j2). Phase 4.2 then finds the
 * list already unique, breaks nothing, and takes its pruning snapshot after
 * every phase in between. That is the path reproduced here. reconcileScope's
 * own break, with the snapshot straight after it, runs only for a list that
 * inherits again by Phase 4.2, and is not reproduced.
 *
 * So the break stands for Phase 1's, and the settle window stands for the
 * phases in between: this probe reads HasUniqueRoleAssignments until it
 * turns (up to 6 reads 2000 ms apart), then re-reads the snapshot until two
 * consecutive reads agree and hold a binding other than 'Limited Access' (up
 * to 6 reads 2000 ms apart). The deploy reads its snapshot once, but on a
 * real bundle that read comes far longer after the break than this window
 * lasts, and this enumeration was measured to flap
 * (access.list-acl.enumeration-is-monotonic), so one read here is not the
 * settled scope Phase 4.2 sees. Every snapshot read is recorded: an empty
 * one, which the deploy would have pruned nothing from, is an observation
 * and does not void the run. If no two reads agree, the last one holding a
 * binding is used and the evidence says so.
 *
 * From the identity read that opens Phase 4.2 on, the requests are the
 * deploy's own, in its order, with its $select, its verbose Accept and
 * no-store: that read, the snapshot, the identity read before pruning, each
 * removal in its own bracket in snapshot order, settleBindings, and
 * surveyDescendants. The break and the removals carry only Accept and
 * X-RequestDigest, no body, as the deploy sends them. A throttle (429, 503
 * or the throttle page) is retried as fetchWithRetry retries it: up to 8
 * times, after Retry-After seconds or 2^n seconds capped at 60. The
 * remaining differences, named:
 *   (a) the break is bracketed by this probe's identity reads; Phase 1 sends
 *       it straight after reconcileListShape proved the list, and follows it
 *       with an ItemCount check this probe does not make.
 *   (b) an identity read must carry a string Id and this probe's marker as
 *       its Description, or nothing further is written. The deploy also
 *       applies probeListShapeByTitle's other type checks and
 *       assertListAdoptable, and adds a RootFolder select for a list with an
 *       internal_name, which this scratch list does not have.
 *   (c) Phase 4.2's own reads before the snapshot, the descendant survey and
 *       the flag check, are not reproduced: the list holds no items, and the
 *       settle window has just read the flag.
 *   (d) the deploy caches its digest and gates throttles across lanes; this
 *       probe asks for a digest per write and sends one request at a time.
 *
 * MICROSOFT LEARN CITATIONS
 *   "SP.SecurableObject.breakRoleInheritance method"
 *   "SP.RoleAssignmentCollection.removeRoleAssignment(principalId,
 *    roleDefId) method" and "SP.RoleAssignmentCollection object"
 *   "Choose administrators and owners for the administration hierarchy in
 *    SharePoint Server" and "Default SharePoint groups"
 *   "Working with lists and list items with REST": create a list by POST
 *    to web/lists, delete one by POST to web/lists(guid'...') with
 *    X-HTTP-Method DELETE
 *   "Complete basic operations using SharePoint REST endpoints": a DELETE
 *    of a recyclable object such as a list is a Recycle operation
 *
 * RUN AS A SITE COLLECTION ADMINISTRATOR ON A DISPOSABLE SITE. The run takes
 * every direct binding off its list, and an administrator is the one
 * identity Learn expects to still reach the list and delete it in the same
 * paste. It checks web/currentuser for IsSiteAdmin=true and writes nothing
 * at all when it is not.
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
 * line naming the list's Id means it may still be there, and it prints a
 * line to paste that deletes it by that Id.
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

  log('INFO', 'probe revision 2ea9271b. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe LastBinding';
  const OWNERSHIP = 'dbml-sharepoint last-binding-removal probe list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${LIST}')`;

  const Q = {
    list: 'A list this run created carries its marker and Id and still inherits',
    break: 'breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false) is accepted and the list then reads unique',
    direct: "The deploy's pruning snapshot, read once the break has settled and to its last page, holds at least one binding other than 'Limited Access'",
    removal: "What does removeroleassignment answer for each binding the exact prune removes, in its order, the list's last one included",
    readback: 'After them, what do the GETs Phase 4.2 makes after its last removal answer, and what would the deploy conclude',
    enumeration: 'After them, what does the role-assignment enumeration return over the settle window',
    unique: 'After them, does the list still read HasUniqueRoleAssignments=true',
    delete: 'After them, can this account still delete the list',
  };

  expect('access.list-acl.fixture-last-binding-list', Q.list);
  expect('access.list-acl.fixture-last-binding-break', Q.break);
  expect('access.list-acl.fixture-last-binding-direct', Q.direct);
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
  // The rows read through the title; the closing delete goes by Id and is not among them.
  const READ_BY_TITLE = OBSERVED_ROWS.slice(0, -1);
  // The harness's own words for a row nothing has recorded yet.
  const PENDING = RESULTS[0].evidence;

  if (!CONFIRMED) {
    log('INFO', 'Would check that this account is a site collection administrator, create');
    log('INFO', `a LIST '${LIST}', break its role inheritance with copyRoleAssignments=false,`);
    log('INFO', "remove every direct binding the break leaves except 'Limited Access', this");
    log('INFO', "account's own among them, in the order the deploy's exact prune removes them,");
    log('INFO', 'record what the list reports over 8 seconds, and DELETE the list by its Id.');
    log('INFO', 'Run it on a disposable site.');
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
  // The snapshot window: see FIDELITY in the header for why it exists.
  const SNAPSHOT_READS = 6;
  const PAGE_LIMIT = 50;
  // fetchWithRetry's policy in _http.js.j2; RETRY_UNIT_MS is the second it counts in.
  const RETRY_ATTEMPTS = 8;
  const RETRY_UNIT_MS = 1000;
  const THROTTLE_PAGE = /\/_layouts\/15\/throttle\.htm(\?|$)/i;
  // The pattern resetList in _probe_harness.js.j2 refuses a non-list Id with.
  const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const api = (path) => `${WEB}/_api/${path}`;
  const guidOf = (value) => (
    value == null ? null : String(value).replace(/[{}]/g, '').toLowerCase());

  // ---- masking -----------------------------------------------------------
  // The strings this run knows go first, longest first, since a pattern can only guess at them.
  const KNOWN = [];
  const know = (value, mask) => {
    const text = value == null ? '' : String(value);
    if (text.length < 2) return;
    KNOWN.push({ text, mask });
    KNOWN.sort((a, b) => b.text.length - a.text.length);
  };
  const escapeForRegExp = (text) => text.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
  try {
    const here = new URL(WEB);
    know(WEB, '<web>');
    know(here.host, '<host>');
    know(here.pathname.replace(/\/+$/, ''), '<web-path>');
  } catch {
    know(WEB, '<web>');
  }

  const scrub = (text) => {
    let out = String(text);
    for (const { text: known, mask } of KNOWN) {
      out = out.replace(new RegExp(escapeForRegExp(known), 'gi'), mask);
    }
    return out
      .replace(/https?:\/\/[^\s'"]+/gi, '<url>')
      .replace(/\b[a-z0-9-]+(\.[a-z0-9-]+)*\.sharepoint\.com\b/gi, '<host>')
      .replace(/\/(sites|teams|personal)\/[^\s'"]+/gi, '/$1/<site>')
      .replace(/(i:0[^|\s'"]*\|([^|\s'"]+\|)?)[^\s'"|]+/gi, '$1<account>')
      .replace(/[^\s'"|:<>]+@[^\s'"<>]+/gi, '<account>');
  };

  // ---- transport, as fetchWithRetry sends it -------------------------------
  // no-store on every request: a by-title read can otherwise be the browser's
  // cached answer (MEASURED 2026-09-13, list-identity-cache-probe.js).
  const isThrottled = (res) => res.status === 429 || res.status === 503
    || THROTTLE_PAGE.test(res.url || '');
  const send = async (url, init) => {
    for (let attempt = 0; ; attempt += 1) {
      const res = await fetch(url, { ...init, cache: 'no-store' });
      if (!isThrottled(res) || attempt >= RETRY_ATTEMPTS) return res;
      const header = res.headers && typeof res.headers.get === 'function'
        ? res.headers.get('Retry-After') : null;
      const seconds = Number(header) || Math.min(2 ** attempt, 60);
      log('INFO', `Throttled (HTTP ${res.status}); waiting ${seconds}s, retry ${attempt + 1}/`
        + `${RETRY_ATTEMPTS}, as the deploy does.`);
      await sleep(seconds * RETRY_UNIT_MS);
    }
  };

  const read = async (url, accept = NOMETADATA) => {
    try {
      const res = await send(url, { headers: { Accept: accept } });
      const throttled = isThrottled(res);
      let unparsed = false;
      const body = await res.json().catch(() => { unparsed = true; return null; });
      return { ok: res.ok && !throttled, status: res.status, body, unparsed, throttled };
    } catch (err) {
      return { ok: false, status: 0, body: null, threw: String(err) };
    }
  };

  // The deploy's POST: the digest and a verbose Accept, and a body only where one is sent.
  const post = async (path, digest, { body, headers } = {}) => {
    try {
      const init = {
        method: 'POST',
        headers: { Accept: VERBOSE, 'X-RequestDigest': digest, ...(headers || {}) },
      };
      if (body !== undefined) init.body = body;
      const res = await send(api(path), init);
      const throttled = isThrottled(res);
      const text = await res.text().catch(() => '');
      let parsed = null;
      try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
      return { ok: res.ok && !throttled, status: res.status, text, body: parsed, throttled };
    } catch (err) {
      return { ok: false, status: 0, text: '', body: null, threw: String(err) };
    }
  };

  // Not an answer at all: a throttle that outlasted the retries, a timeout, or a throw.
  const silent = (r) => Boolean(r.threw) || Boolean(r.throttled) || r.status === 408;

  const describeRead = (r) => {
    if (r.threw) return `the request threw (${scrub(r.threw)})`;
    if (r.ok) return `HTTP ${r.status}`;
    const still = r.throttled ? ', still throttled after the deploy\'s retries,' : '';
    const said = r.text !== undefined ? r.text : JSON.stringify(r.body);
    return `HTTP ${r.status}${still} ${scrub(said || '').slice(0, 200)}`.trim();
  };

  const closeAll = (ids, outcome, why, state) => {
    for (const id of ids) record(id, RESULTS.find((r) => r.id === id).question, outcome, why, state);
  };
  const closeUnreached = (why) => {
    for (const r of RESULTS) {
      if (r.outcome === 'NOT ESTABLISHED' && r.evidence === PENDING) {
        record(r.id, r.question, 'NOT ESTABLISHED', why);
      }
    }
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
  let myId = null;

  const noteIdentity = (where, id, marker) => {
    if (rebound !== null || id === undefined) return;
    const now = guidOf(id);
    if (now !== ownedId || (marker !== undefined && marker !== OWNERSHIP)) {
      rebound = `${where} answered list ${now} where this run claimed ${ownedId}`;
    }
  };

  // probeListShapeByTitle's request; see (b) in the header for what is judged.
  const SHAPE_SELECT = [
    'Id', 'Title', 'BaseTemplate', 'ContentTypesEnabled', 'Description',
    'EnableVersioning', 'EnableMinorVersions', 'MajorVersionLimit',
    'ValidationFormula', 'ValidationMessage',
  ].join(',');

  const deployIdentity = async (label) => {
    const r = await read(api(`${listPath}?$select=${SHAPE_SELECT}`), VERBOSE);
    const d = r.ok && r.body && typeof r.body.d === 'object' ? r.body.d : null;
    // An identity with a field missing proves nothing, and the deploy's shape gate refuses one.
    const whole = d !== null && typeof d.Id === 'string' && typeof d.Description === 'string';
    if (whole) noteIdentity(label, d.Id, d.Description);
    const step = `${label}: ${describeRead(r)}${whole ? ` carrying list ${guidOf(d.Id)}` : ''}`;
    if (silent(r)) return { step, silent: true, stop: null };
    if (!r.ok) return { step, stop: `the deploy throws at ${label}, which answered HTTP ${r.status}` };
    if (d === null) {
      return { step, stop: `the deploy throws at ${label}, which answered HTTP ${r.status} with no list in it` };
    }
    if (!whole) {
      return {
        step,
        stop: `the deploy throws at ${label}, which answered HTTP ${r.status} with an Id of `
          + `${shapeOf(d.Id)} and a Description of ${shapeOf(d.Description)}, so it identifies no list`,
      };
    }
    if (rebound !== null) return { step, stop: `the deploy throws at ${label}: ${rebound}` };
    return { step, stop: null };
  };

  // Before a write the read is a guard: anything short of this run's list stops the run.
  const proveOwned = async (label) => {
    const got = await deployIdentity(label);
    if (got.silent || got.stop !== null) {
      throw new Error(`${got.stop || `${got.step}, which is not an answer`}. Nothing further `
        + 'was sent by title.');
    }
  };

  // ---- the enumerations ------------------------------------------------------
  const PROBE_BINDING_QUERY = 'roleassignments?$expand=Member,RoleDefinitionBindings&$top=200';
  const DEPLOY_BINDING_QUERY = 'roleassignments?$expand=RoleDefinitionBindings'
    + '&$select=PrincipalId,RoleDefinitionBindings/Id,RoleDefinitionBindings/Name';
  const ITEMS_QUERY = 'items?$select=Id,HasUniqueRoleAssignments,FileSystemObjectType,FileRef&$top=5000';

  // validatedNextPage in deploy/_shape_probes.js.j2.
  const validatedNext = (page) => {
    const next = page && page.__next;
    if (next != null && typeof next !== 'string') throw new Error('invalid OData __next continuation');
    return next || null;
  };

  // scopeBindings, to the letter where the letter decides the verdict: its
  // `(json.d && json.d.results) || []` reads a 200 without results as no rows.
  const deployEnumeration = async () => {
    const rows = [];
    const notes = [];
    let url = api(`${listPath}/${DEPLOY_BINDING_QUERY}`);
    let pages = 0;
    let status = null;
    while (url) {
      if (pages >= PAGE_LIMIT) {
        return { kind: 'silent', why: `still continuing after ${pages} page(s), so the read stopped short of the end` };
      }
      const r = await read(url, VERBOSE);
      const at = `page ${pages + 1}`;
      if (silent(r)) return { kind: 'silent', why: `${at} ${describeRead(r)}` };
      if (!r.ok) return { kind: 'throws', why: `${at} answered ${describeRead(r)}` };
      if (r.unparsed) return { kind: 'throws', why: `${at} answered HTTP ${r.status} with a body that is not JSON` };
      if (status === null) status = r.status;
      pages += 1;
      try {
        const json = r.body;
        const next = validatedNext(json.d);
        if (!(json.d && json.d.results)) {
          notes.push(`${at} carried no results array, so the deploy read zero rows from it`);
        }
        for (const row of ((json.d && json.d.results) || [])) {
          if (row.PrincipalId == null) throw new Error('an entry without PrincipalId');
          const bindings = row.RoleDefinitionBindings && row.RoleDefinitionBindings.results;
          if (!Array.isArray(bindings)) {
            throw new Error(`principal ${row.PrincipalId} without a RoleDefinitionBindings.results array`);
          }
          for (const binding of bindings) {
            if (binding == null || binding.Id == null) {
              throw new Error(`a binding for principal ${row.PrincipalId} without RoleDefinitionBindings/Id`);
            }
            if (typeof binding.Name !== 'string') {
              throw new Error(`binding ${binding.Id} for principal ${row.PrincipalId} without RoleDefinitionBindings/Name`);
            }
            rows.push({
              principalId: row.PrincipalId, roleDefId: binding.Id,
              key: `${row.PrincipalId}:${binding.Id}`, name: binding.Name,
            });
          }
        }
        url = next;
      } catch (err) {
        return { kind: 'throws', why: `${at}: ${err instanceof Error ? err.message : String(err)}` };
      }
    }
    return { kind: 'rows', status, pages, rows, notes };
  };

  // surveyDescendants, which exact mode runs again once reconcileScope is done.
  const deploySurvey = async () => {
    const rows = [];
    const notes = [];
    let url = api(`${listPath}/${ITEMS_QUERY}`);
    let pages = 0;
    let status = null;
    while (url) {
      if (pages >= PAGE_LIMIT) {
        return { kind: 'silent', step: `still continuing after ${pages} page(s)` };
      }
      const r = await read(url, VERBOSE);
      const at = `page ${pages + 1}`;
      if (silent(r)) return { kind: 'silent', step: `${at} ${describeRead(r)}` };
      if (!r.ok) return { kind: 'throws', step: `${at} answered ${describeRead(r)}`, why: `${at} answered HTTP ${r.status}` };
      if (r.unparsed) {
        return { kind: 'throws', step: `${at} answered HTTP ${r.status}`, why: `${at} carried a body that is not JSON` };
      }
      if (status === null) status = r.status;
      pages += 1;
      try {
        const json = r.body;
        const next = validatedNext(json.d);
        if (!(json.d && json.d.results)) {
          notes.push(`${at} carried no results array, so the deploy read zero items from it`);
        }
        rows.push(...((json.d && json.d.results) || []));
        url = next;
      } catch (err) {
        const why = `${at}: ${err instanceof Error ? err.message : String(err)}`;
        return { kind: 'throws', step: why, why };
      }
    }
    let undeclared;
    try {
      undeclared = rows.filter((row) => row.HasUniqueRoleAssignments);
    } catch (err) {
      const why = `an item could not be read: ${String(err)}`;
      return { kind: 'throws', step: why, why };
    }
    const step = `HTTP ${status}, ${rows.length} item(s) over ${pages} page(s)`
      + `${notes.length ? `; ${notes.join('; ')}` : ''}`;
    if (undeclared.length > 0) {
      return { kind: 'throws', step, why: `${undeclared.length} undeclared item/folder unique permission scope(s) remain` };
    }
    return { kind: 'rows', step, count: rows.length };
  };

  // The probe's own read, on the URL enumeration-is-monotonic was measured with.
  const readPages = async (url) => {
    const entities = [];
    let next = url;
    let pages = 0;
    let status = null;
    while (next) {
      if (pages >= PAGE_LIMIT) {
        return { kind: 'silent', why: `still continuing after ${pages} page(s), so the read stopped short of the end` };
      }
      const r = await read(next, NOMETADATA);
      if (silent(r)) return { kind: 'silent', why: `page ${pages + 1} ${describeRead(r)}` };
      if (!r.ok) return { kind: 'refused', why: `page ${pages + 1} answered ${describeRead(r)}` };
      if (status === null) status = r.status;
      const rows = r.body ? r.body.value : undefined;
      if (!Array.isArray(rows)) {
        return { kind: 'malformed', why: `page ${pages + 1} carried ${shapeOf(rows)} where its rows belong` };
      }
      entities.push(...rows);
      pages += 1;
      const link = r.body['odata.nextLink'] || r.body.__next;
      if (link != null && link !== '' && typeof link !== 'string') {
        return { kind: 'malformed', why: `page ${pages} carried a continuation of ${shapeOf(link)}, which cannot be followed` };
      }
      next = link || null;
    }
    return { kind: 'rows', status, pages, entities };
  };

  // Every field a row is placed by is a prerequisite, as in operator-safety-grant-probe.js.
  const enumerate = async () => {
    const got = await readPages(api(`${listPath}/${PROBE_BINDING_QUERY}`));
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

  const whose = (principalId) => (Number(principalId) === myId ? 'this account' : 'another principal');

  const describeRows = (rows) => (
    rows.length === 0
      ? 'no rows'
      : rows.map((r) => (
        `principal ${r.principalId} (${whose(r.principalId)}, `
        + `PrincipalType ${r.principalType}, `
        + `title ${r.titleLength === null ? 'absent' : `${r.titleLength} chars`}) `
        + `-> level ${r.levelId} '${r.levelName}'`
      )).join('; ')
  );

  const describeBindings = (rows) => rows.map(
    (row) => `${row.key} '${row.name}' (${whose(row.principalId)})`).join(', ');

  // ---- who is running this, before anything is written -------------------
  const me = await read(api('web/currentuser?$select=Id,IsSiteAdmin,LoginName,Email,Title'));
  const meId = me.ok && me.body ? Number(me.body.Id) : NaN;
  if (!me.ok || !me.body || typeof me.body.IsSiteAdmin !== 'boolean'
      || !Number.isFinite(meId) || meId <= 0) {
    closeAll(ALL, 'NOT ESTABLISHED',
      `web/currentuser answered ${describeRead(me)} without a usable Id and IsSiteAdmin, so this `
      + 'run could not tell whether it may take a list\'s last role assignment away, or match a '
      + 'binding to this account. Nothing was written.');
    return report();
  }
  know(me.body.LoginName, '<account>');
  know(me.body.Email, '<account>');
  know(me.body.Title, '<name>');
  if (me.body.IsSiteAdmin !== true) {
    closeAll(ALL, 'NOT REACHED',
      'this account is not a site collection administrator (web/currentuser reports '
      + 'IsSiteAdmin=false). This run takes every direct binding off its list, and an '
      + 'administrator is the one identity expected to delete it afterwards. Nothing was '
      + 'written. Re-run as a site collection administrator on a disposable site.', 'void');
    return report();
  }
  myId = meId;

  // ---- the closing DELETE, also CLEANUP's ---------------------------------
  // By Id, the documented form, so a rebound title cannot redirect it. The marker is
  // re-read by Id first: no title bracket guards this write, so that read is its guard,
  // and it is also what makes a 404 after it mean gone rather than hidden.
  const deleteById = async (id) => {
    if (!GUID.test(String(id))) {
      return { sent: false, confirmed: false, facts: `'${id}' is not a list Id, so no DELETE was sent` };
    }
    const byId = `web/lists(guid'${id}')`;
    const before = await read(api(`${byId}?$select=Id,Description`));
    const ours = before.ok && before.body !== null && typeof before.body === 'object'
      && guidOf(before.body.Id) === String(id).toLowerCase() && before.body.Description === OWNERSHIP;
    if (!ours) {
      return {
        sent: false,
        confirmed: false,
        foreign: before.ok,
        facts: `the read by Id answered ${describeRead(before)}`
          + `${before.ok ? `, which does not show this probe's marker on list ${id}` : ''}, so no `
          + 'DELETE was sent',
      };
    }
    let gone;
    try {
      gone = await post(byId, await getDigest(), { headers: { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' } });
    } catch (err) {
      gone = { ok: false, status: 0, text: '', threw: String(err) };
    }
    const after = await read(api(`${byId}?$select=Id`));
    return {
      sent: true,
      gone,
      confirmed: gone.ok && after.status === 404,
      facts: `the read by Id answered ${describeRead(before)} carrying this probe's marker before `
        + `the DELETE, the DELETE ${gone.threw ? `threw (${scrub(gone.threw)})` : `answered ${describeRead(gone)}`}, `
        + `and the read by Id answered ${describeRead(after)} after it`,
    };
  };

  // Site-relative, so the line carries no URL and runs on whichever site it is pasted into.
  const handDelete = (id) => (GUID.test(String(id))
    ? 'To delete it by its Id, paste this line into the console of this same site as a site '
      + 'collection administrator: '
      + "fetch(_spPageContextInfo.webAbsoluteUrl + '/_api/contextinfo', { method: 'POST', "
      + "headers: { Accept: 'application/json;odata=verbose' } }).then((r) => r.json())"
      + '.then((j) => fetch(_spPageContextInfo.webAbsoluteUrl + '
      + `"/_api/web/lists(guid'${String(id).toLowerCase()}')", { method: 'POST', headers: { `
      + "'X-RequestDigest': j.d.GetContextWebInformation.FormDigestValue, "
      + "'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' } }))"
      + ".then((r) => console.log('DELETE answered HTTP ' + r.status));"
    : `'${id}' is not a list Id, so there is no line to delete it by. Delete the list titled `
      + `'${LIST}' that carries this probe's Description by hand, from Site contents, as a site `
      + 'collection administrator.');

  // ---- the scratch title -------------------------------------------------
  // A title is never ownership: only a list carrying this probe's exact marker is
  // cleared, and only by its Id with CLEANUP on.
  const claim = await read(api(`${listPath}?$select=Id,Description`));
  let refusal = null;
  if (claim.status !== 404) {
    const leftover = claim.ok && claim.body ? guidOf(claim.body.Id) : null;
    if (!claim.ok || !claim.body) {
      refusal = `could not read whether the title '${LIST}' is occupied (${describeRead(claim)}). `
        + 'That is not the title being free, so nothing was deleted or created.';
    } else if (claim.body.Description !== OWNERSHIP) {
      refusal = `a list titled '${LIST}' already exists without this probe's ownership marker, `
        + 'so this run did not make it and will not touch it. Rename or remove it, and paste again.';
    } else if (leftover === null || !GUID.test(leftover)) {
      refusal = `a list titled '${LIST}' carries this probe's ownership marker but answered `
        + `${leftover === null ? 'without an Id' : `with the Id '${leftover}'`}, so no write to it `
        + 'could be addressed by Id. Nothing was deleted or created.';
    } else if (!CLEANUP) {
      refusal = `'${LIST}' (list ${leftover}) is left over from an earlier run of this probe. `
        + 'Set CLEANUP = true to delete it by its Id, and paste again.';
    } else {
      // Not the harness's resetList: its refusal line prints SharePoint's text unmasked.
      const cleared = await deleteById(leftover);
      if (!cleared.confirmed) {
        refusal = `the CLEANUP delete of '${LIST}' (list ${leftover}) did not complete: `
          + `${cleared.facts}. Nothing was created over it. ${handDelete(leftover)}`;
      } else {
        log('OK', `CLEANUP: deleted the leftover '${LIST}' (list ${leftover}) by its Id and read it back absent.`);
        const after = await read(api(`${listPath}?$select=Id`));
        if (after.status !== 404) {
          refusal = `'${LIST}' still answers ${describeRead(after)} after the CLEANUP delete, so `
            + 'nothing was created over it.';
        }
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
    let digest = await getDigest();
    createSent = true;
    const made = await post('web/lists', digest, {
      body: JSON.stringify({ Title: LIST, BaseTemplate: 100, Description: OWNERSHIP }),
      headers: { Accept: NOMETADATA, 'Content-Type': NOMETADATA },
    });
    // Read back whatever the create answered: a write reported as refused may still
    // have been applied. Only this marker read adopts an Id, never the create's answer.
    const shape = await read(api(`${listPath}?$select=Id,Description,HasUniqueRoleAssignments`));
    const marked = shape.ok && shape.body !== null && typeof shape.body === 'object'
      && shape.body.Description === OWNERSHIP;
    ownedId = marked ? guidOf(shape.body.Id) : null;
    if (!made.ok) {
      if (shape.status === 404) createSent = false;
      let after;
      if (shape.status === 404) after = 'read as absent, so nothing was created';
      else if (ownedId !== null) {
        after = `read list ${ownedId} carrying this probe's marker, so the create was applied `
          + 'anyway, and that list is deleted at the end';
      } else {
        after = `answered ${describeRead(shape)} without this probe's marker, so what the create `
          + 'left is unknown';
      }
      settleFixture('access.list-acl.fixture-last-binding-list', false,
        `could not create '${LIST}': ${describeRead(made)}. The title then ${after}`, AFTER_LIST);
      return;
    }
    const createdId = guidOf(made.body && made.body.Id);
    if (createdId !== null && ownedId !== null && createdId !== ownedId) {
      settleFixture('access.list-acl.fixture-last-binding-list', false,
        `the create answered list ${createdId}, but the title reads list ${ownedId} carrying this `
        + 'probe\'s marker. Only the list the marker read confirmed is deleted at the end.', AFTER_LIST);
      return;
    }
    const listHeld = await establishFixture('access.list-acl.fixture-last-binding-list',
      async () => shape, {
        Id: (value) => GUID.test(String(guidOf(value))) && guidOf(value) === ownedId,
        Description: OWNERSHIP,
        HasUniqueRoleAssignments: false,
      }, AFTER_LIST);
    if (!listHeld) return;

    // ---- fixture-last-binding-break --------------------------------------
    await proveOwned('the list read before breakroleinheritance');
    digest = await getDigest();
    const broke = await post(
      `${listPath}/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)`, digest);
    if (!broke.ok) {
      settleFixture('access.list-acl.fixture-last-binding-break', false,
        `breakroleinheritance answered ${describeRead(broke)}`, AFTER_BREAK);
      return;
    }
    await proveOwned('the list read after breakroleinheritance');
    // ---- the settle window, standing for the phases before Phase 4.2 --------
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

    // ---- fixture-last-binding-direct: Phase 4.2 opens -----------------------
    await proveOwned('the list read before reading ACL state');
    const pruneable = (e) => (e.kind === 'rows' && e.notes.length === 0
      ? e.rows.filter((row) => row.name !== 'Limited Access') : []);
    const snapshotReads = [];
    let previous = null;
    let chosen = null;
    let stable = false;
    for (let attempt = 0; attempt < SNAPSHOT_READS && !stable; attempt += 1) {
      if (attempt > 0) await sleep(SETTLE_MS);
      const e = await deployEnumeration();
      const n = attempt + 1;
      let said;
      if (e.kind === 'throws') said = `the deploy would throw reading it (${e.why})`;
      else if (e.kind === 'silent') said = `it did not answer (${e.why})`;
      else {
        said = `${e.rows.length} binding(s) over ${e.pages} page(s)`
          + `${e.rows.length ? `: ${describeBindings(e.rows)}` : ''}, ${pruneable(e).length} other `
          + `than 'Limited Access'${e.notes.length ? `; ${e.notes.join('; ')}` : ''}`;
      }
      snapshotReads.push(`read ${n}: ${said}`);
      if (pruneable(e).length === 0) {
        previous = null;
        continue;
      }
      const keys = e.rows.map((row) => row.key).join(',');
      stable = previous !== null && previous.keys === keys;
      previous = { keys };
      chosen = { e, n };
    }
    let chosenBecause = `no read held a binding other than 'Limited Access' for the prune to remove, `
      + 'so no removal was sent';
    if (stable) chosenBecause = `reads ${chosen.n - 1} and ${chosen.n} agreed, so read ${chosen.n} is the snapshot`;
    else if (chosen !== null) {
      chosenBecause = `no two consecutive reads agreed, so read ${chosen.n}, the last holding a binding `
        + "other than 'Limited Access', is the snapshot";
    }
    if (!settleFixture('access.list-acl.fixture-last-binding-direct', chosen !== null,
      `this account is principal ${myId}. The deploy's snapshot, re-read up to ${SNAPSHOT_READS} `
      + `times ${SETTLE_MS} ms apart until two consecutive reads agreed: ${snapshotReads.join('; ')}. `
      + `${chosenBecause}.`, OBSERVED_ROWS)) {
      return;
    }
    const strays = pruneable(chosen.e);

    // ---- the exact prune, and the read-back after it -----------------------
    const trace = [];
    const removals = [];
    let lastRemovalAt = -1;
    let stop = null;
    let stopSilent = false;

    // Once a removal has gone, a failed step ends the prune rather than the run.
    const step = (got) => {
      trace.push(got.step);
      if (got.silent) stopSilent = true;
      else if (got.stop) stop = got.stop;
      return got.silent || Boolean(got.stop);
    };
    try {
      await proveOwned('the list read before pruning');
      for (let i = 0; i < strays.length; i += 1) {
        const row = strays[i];
        const n = i + 1;
        const opening = `the list read that opens removal ${n}'s bracket`;
        if (removals.length === 0) await proveOwned(opening);
        else if (step(await deployIdentity(opening))) break;
        digest = await getDigest();
        removalSent = true;
        const answer = await post(`${listPath}/roleassignments/removeroleassignment(`
          + `principalid=${row.principalId},roleDefId=${row.roleDefId})`, digest);
        removals.push({ n, row, answer });
        trace.push(`removal ${n}: ${describeRead(answer)}`);
        lastRemovalAt = trace.length;
        if (silent(answer)) { stopSilent = true; break; }
        if (!answer.ok) {
          stop = `the deploy throws at removal ${n}, which answered HTTP ${answer.status}`;
          break;
        }
        if (step(await deployIdentity(`the list read that closes removal ${n}'s bracket`))) break;
      }
    } catch (err) {
      if (removals.length === 0) throw err;
      stopSilent = true;
      trace.push(`the prune stopped: ${scrub(err instanceof Error ? err.message : String(err))}`);
    }

    // ---- last-binding-removal --------------------------------------------
    const last = removals[removals.length - 1];
    const heard = removals.filter((x) => !silent(x.answer));
    const refused = heard.some((x) => !x.answer.ok);
    const accepted = heard.some((x) => x.answer.ok);
    const answered = (x) => (x.answer.threw ? `threw: ${scrub(x.answer.threw)}`
      : `answered HTTP ${x.answer.status}: ${scrub(x.answer.text).slice(0, 260) || '(empty body)'}`);
    record('access.list-acl.last-binding-removal', Q.removal,
      heard.length < removals.length ? 'NOT ESTABLISHED' : refused ? 'REFUSED' : 'ACCEPTED',
      removals.map((x) => `removal ${x.n} of ${strays.length}, removeroleassignment(principalid=`
        + `${x.row.principalId},roleDefId=${x.row.roleDefId}), ${whose(x.row.principalId)}'s `
        + `'${x.row.name}' binding, ${answered(x)}`).join('; ')
      + `. The last removal sent was ${whose(last.row.principalId)}'s binding`
      + (removals.length < strays.length
        ? `, and the deploy stops there, so ${strays.length - removals.length} binding(s) were never sent`
        : '')
      + (removals.some((x) => x.answer.status === 401 || x.answer.status === 403)
        ? '. A refusal here is an authorisation answer' : '')
      + (heard.length < removals.length
        ? '. A removal that did not answer is not an answer; the rows below still say what the scope reported' : '')
      + (accepted ? '. A 200 here is not evidence by itself: MEASURED 2026-09-22, this endpoint '
        + 'answered 200 for a principal and level that do not exist, so the enumeration row says '
        + 'whether it took' : ''));

    // ---- after-last-binding-readback -------------------------------------
    // Immediately, as the deploy reads: its first request after the last removal is this.
    let judged = null;
    let survey = null;
    if (!stopSilent && stop === null) {
      step(await deployIdentity("the list read that opens settleBindings' bracket"));
      for (let attempt = 0; !stopSilent && stop === null && judged === null && attempt < SETTLE_READS;
        attempt += 1) {
        if (attempt > 0) await sleep(SETTLE_MS);
        const e = await deployEnumeration();
        const label = `enumeration ${attempt + 1}`;
        if (e.kind === 'silent') {
          trace.push(`${label}: ${e.why}`);
          stopSilent = true;
        } else if (e.kind === 'throws') {
          trace.push(`${label}: ${e.why}`);
          stop = `the deploy throws at ${label}: ${e.why}`;
        } else {
          // The exact-mode judge with nothing declared: any binding but 'Limited Access' is a stray.
          const left = e.rows.filter((row) => row.name !== 'Limited Access');
          trace.push(`${label}: HTTP ${e.status}, ${e.rows.length} binding(s)`
            + `${e.rows.length ? ` (${describeBindings(e.rows)})` : ''}`
            + `${e.notes.length ? `; ${e.notes.join('; ')}` : ''}`);
          if (left.length === 0) judged = attempt + 1;
        }
      }
      // settleBindings closes its bracket before its caller looks at the judge's complaint.
      if (!stopSilent && stop === null) step(await deployIdentity("the list read that closes settleBindings' bracket"));
      if (!stopSilent && stop === null && judged === null) {
        stop = `the deploy aborts: all ${SETTLE_READS} enumerations still reported a binding other `
          + "than 'Limited Access'";
      }
      if (!stopSilent && stop === null) {
        survey = await deploySurvey();
        trace.push(`the descendant survey: ${survey.step}`);
        if (survey.kind === 'silent') stopSilent = true;
      }
    }
    const certified = `the deploy logs that the scope reports exactly the 0 declared role `
      + `assignment(s), because enumeration ${judged} reported no binding other than 'Limited Access'`;
    let verdict = stop;
    if (verdict === null && survey !== null) {
      verdict = survey.kind === 'throws'
        ? `${certified}, then throws at the descendant survey: ${survey.why}`
        : `${certified}, and its descendant survey found no undeclared unique scope among `
          + `${survey.count} item(s), so the list completes Phase 4.2`;
    }
    const after = trace.slice(lastRemovalAt);
    record('access.list-acl.after-last-binding-readback', Q.readback,
      stopSilent ? 'NOT ESTABLISHED' : 'OBSERVED',
      stopSilent
        ? 'a request did not answer after the deploy\'s own retries, so what the deploy concludes '
          + `rests on a throttle or a transport failure; re-run. ${trace.join('; ')}.`
        : `${verdict}${after.length ? `. In order after the last removal: ${after.join('; ')}` : '. It makes no read after that'}.`);

    // ---- after-last-binding-enumeration, after-last-binding-unique --------
    // One window, both reads each time; the flag read carries the Id, which re-proves
    // the title between enumerations.
    const removedKeys = new Set(removals.map((x) => `${x.row.principalId}:${x.row.roleDefId}`));
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
        const held = e.rows.some((r) => removedKeys.has(`${r.principalId}:${r.levelId}`));
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
      summary = `the removed binding(s) (${[...removedKeys].join(', ')}) read present on `
        + `${which(present)} and absent on ${which(absent)}, ${span}`;
    }
    record('access.list-acl.after-last-binding-enumeration', Q.enumeration,
      enumHeard ? 'OBSERVED' : 'NOT ESTABLISHED', `${summary}: ${enumReads.join('; ')}.`);
    record('access.list-acl.after-last-binding-unique', Q.unique,
      uniqueHeard ? 'OBSERVED' : 'NOT ESTABLISHED',
      `${uniqueHeard ? '' : `none of the ${SETTLE_READS} reads answered. `}`
      + `HasUniqueRoleAssignments ${span}: ${uniqueReads.join('; ')}.`);

    if (rebound !== null) {
      closeAll(READ_BY_TITLE, 'NOT ESTABLISHED',
        `the title '${LIST}' answered another list during the run (${rebound}), so which list `
        + 'the removals and these reads reached is unknown. Nothing further was written by title.');
    }
  };

  // ---- after-last-binding-delete, and the cleanup it is ------------------
  const removeList = async () => {
    if (ownedId === null) {
      if (createSent) {
        log('FAIL', `this run could not establish the Id of '${LIST}', so it deleted nothing. If `
          + 'a list with that title carries this probe\'s Description, delete it by hand from Site '
          + 'contents as a site collection administrator.');
      }
      return;
    }
    const result = await deleteById(ownedId);
    // Every request here goes by Id, so a rebound title leaves this row answerable.
    if (removalSent) {
      const gone = result.gone;
      let outcome = 'NOT ESTABLISHED';
      if (result.sent && !silent(gone)) outcome = gone.ok ? 'ACCEPTED' : 'REFUSED';
      let head = 'no DELETE was sent';
      if (result.confirmed) head = 'the list is gone';
      else if (result.sent) head = 'the list was not read back absent';
      record('access.list-acl.after-last-binding-delete', Q.delete, outcome,
        `${head}: ${result.facts}${rebound === null ? '' : `. Addressed by Id throughout, `
          + `which the rebound title (${rebound}) does not redirect`}.`);
    }
    log(result.confirmed ? 'OK' : 'FAIL', result.confirmed
      ? `deleted '${LIST}' (list ${ownedId}) and read it back absent. Learn documents a DELETE of `
        + 'a list as a Recycle operation; this run did not look in the recycle bin.'
      : `'${LIST}' (list ${ownedId}) may still exist: ${result.facts}. ${result.foreign
        // A pasted line would delete whatever the Id reads as, so none is offered here.
        ? 'It no longer reads as this probe\'s list, so no line to delete it is printed. Check it '
          + 'in Site contents before removing it by hand.'
        : handDelete(ownedId)}`);
  };

  try {
    await measure();
  } catch (err) {
    const why = scrub(err && err.message ? err.message : String(err));
    log('FAIL', `the measurement pass stopped: ${why}`);
    closeUnreached(`the run stopped before this question: ${why}`);
  } finally {
    try {
      await removeList();
    } catch (err) {
      log('FAIL', `the delete of '${LIST}' (list ${ownedId}) threw: ${scrub(String(err))}. `
        + `${handDelete(ownedId)}`);
    }
  }

  // After the delete, so the block the operator copies back says what it did.
  return report();
})();
