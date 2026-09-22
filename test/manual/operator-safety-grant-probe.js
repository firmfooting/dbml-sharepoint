/**
 * dbml-sharepoint PROBE: WHAT A BREAK LEAVES, AND WHETHER REMOVING IT STICKS
 *
 * REVISION: 819eb22e
 *
 * THE CLAIM UNDER TEST. `deploy/_lists.js.j2` says, beside the early
 * isolation break, that "copyRoleAssignments=false leaves only SharePoint's
 * current-operator safety grant". Nothing in this repository measures that.
 * `library.access.unique-permissions-library` GRANTS the owner group as its
 * own safety net immediately after the break, so it never observes what the
 * break left behind on its own.
 *
 * WHY IT MATTERS NOW. Phase 4.2 has always PRUNED such a binding under
 * `reconcile: exact`, and it now reads the scope back afterwards and ABORTS
 * if an undeclared binding is still reported. Every shipped family uses
 * `reconcile: exact` with `break_inheritance: true` on every list. So if
 * SharePoint re-derives the operator's grant after a removal it accepted,
 * every shipped family's deploy starts failing at Phase 4.2 where it
 * previously reported success. The question is whether the platform treats
 * that binding as removable or as something it restores.
 *
 * WHY THIS CANNOT BE ANSWERED FROM DOCUMENTATION. Microsoft Learn documents
 * `SecurableObject.BreakRoleInheritance(copyRoleAssignments, clearSubscopes)`
 * as a signature and says what copying means. It does not say what the
 * collection contains when nothing is copied, and it does not say whether a
 * binding the platform created for the caller can be removed. Checked
 * 2026-09-22: the method page, the RoleAssignmentCollection page and "Role,
 * inheritance, elevation of privilege, and password changes in SharePoint"
 * are all silent on both.
 *
 * SEPARATING WHAT IS DEPENDED ON FROM WHAT IS OBSERVED. The break being
 * ACCEPTED, the scope then reading HasUniqueRoleAssignments=true, and the
 * negative control refusing are things every measurement below DEPENDS on,
 * so they are asserted, and a failure CLOSES the rows that rest on them:
 * void when no re-run by this account could clear it, open when one could.
 * What the break LEFT, whether any of it names this account, whether a
 * removal stuck, and what the levels are called are the things measured, so
 * they are recorded exactly as they came back and never asserted. A probe
 * that asserted "the break leaves one binding" would report FAIL on a tenant
 * that leaves two, which is a measurement, and it would report PASS on a
 * tenant that leaves one belonging to somebody else.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`.
 *
 *   access.list-acl.fixture-scratch-list
 *     A generic list exists and still INHERITS, so the break below has
 *     something to act on and its result is this run's rather than a
 *     previous run's leftover.
 *   access.list-acl.control-unknown-principal-refused
 *     NEGATIVE CONTROL: `removeroleassignment` naming a principal and a
 *     level that do not exist is REFUSED on the broken scope. Without it a
 *     removal answering HTTP 200 says nothing, and "the binding came back"
 *     could not be told from "the server accepted a call it ignored".
 *   access.list-acl.break-leaves-bindings
 *     What does the collection hold after
 *     breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)?
 *     Recorded as found: how many rows, and for each the principal id, its
 *     principal type, the LENGTH of its title and the level names bound to
 *     it. The title's text is deliberately not recorded: on a live run it is
 *     the operator's display name or a group name carrying the site's, and a
 *     transcript ends up in a pull request.
 *   access.list-acl.break-leaves-operator-binding
 *     Is one of those rows a DIRECT binding for the account that ran the
 *     break? Compared by principal id against `web/currentuser`, so the
 *     answer does not depend on reading a login name.
 *   access.list-acl.operator-binding-removal-sticks
 *     The deploy's question. Grant the owner group full control FIRST, so
 *     the scope holds another role assignment exactly as it does when the
 *     deploy prunes, then remove that binding, re-read over the same window
 *     `settleBindings` uses (five reads, 2000 ms apart), and record whether
 *     it stayed gone or came back, and on which read. Without the grant the
 *     probe would be removing the LAST role assignment on the scope, which
 *     is a different request, and a refusal could be an artifact of emptying
 *     the scope rather than the answer.
 *   access.list-acl.derived-level-names
 *     `_acls.js.j2` exempts a binding whose level is named `Limited Access`,
 *     an English literal. This records the level names THIS tenant reports
 *     at a list scope, so a localized tenant is visible rather than assumed.
 *
 * MICROSOFT LEARN CITATIONS
 *   Breaking and restoring role inheritance:
 *     "SP.SecurableObject.breakRoleInheritance method"
 *     "SP.SecurableObject.resetRoleInheritance method"
 *   Removing a role assignment:
 *     "SP.RoleAssignmentCollection.removeRoleAssignment(principalId,
 *      roleDefId) method"
 *   Reading role assignments back:
 *     "SP.RoleAssignmentCollection object"
 *   List creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED, ALLOW_WRITES and CLEANUP to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * The scratch list is claimed by its DESCRIPTION, never by its title. A
 * same-title list this probe did not create is refused before anything is
 * recycled or reused, and so is a title whose occupancy cannot be read,
 * because CLEANUP would recycle a title match and a run without CLEANUP
 * would reuse it and rewrite its permissions.
 *
 * RUN AS A SITE COLLECTION ADMINISTRATOR, and the probe checks rather than
 * trusts. It breaks role inheritance with copyRoleAssignments=false and then
 * removes this account's own binding, and whether either leaves the account
 * able to write the scope is the very thing being measured. A site
 * collection administrator keeps access whatever the bindings say; anyone
 * else may lose the list and would then be unable to restore it. So NOTHING
 * IS BROKEN, and every question the break gates is recorded NOT REACHED,
 * when `web/currentuser` does not report IsSiteAdmin=true. The gate is on
 * the break rather than on the removal because the break is the earlier and
 * the less understood of the two.
 *
 * The restore pass runs on every path out, grants the site's owner group
 * full control before it resets, and says loudly if it could not. A run
 * interrupted between the break and the restore leaves one scratch list with
 * unique permissions: re-run with CLEANUP, or delete the list.
 *
 * STATUS: RUN TWICE, 2026-09-22, on two different sites.
 *
 * Run one, revision 09528a60. The break left EXACTLY ONE role assignment,
 * and it was this account's own direct USER binding (PrincipalType 1) at
 * 'Full Control', which confirms the first of the two claims in
 * `_lists.js.j2`. No 'Limited Access' row existed on a fresh scratch list,
 * consistent with SharePoint deriving it only to support access at a lower
 * scope. The negative control FAILED: `removeroleassignment` answered HTTP
 * 200 for a principal id and a role definition id that do not exist on the
 * tenant, so a 200 from that endpoint is not evidence the call did anything,
 * which is why `_acls.js.j2` reads the scope back after pruning. The removal
 * question was voided by that failed control, which was too strict, and it
 * answers off the read-back now: the deploy aborts on a binding that is
 * still there whatever caused it.
 *
 * Run two, revision a3f177fe, a different site. The removal STUCK. The owner
 * group was granted first, so the scope held another role assignment
 * throughout, exactly as it does when the deploy prunes. Two sites agreed on
 * what the break leaves: one binding, this account's own, PrincipalType 1 at
 * 'Full Control'.
 *
 * Run two also produced the finding that matters more than that verdict. The
 * role-assignment enumeration at list scope is NOT MONOTONIC. The removed
 * binding read gone on reads 1, 2 and 3, PRESENT again on read 4, and gone
 * on read 5, over 8000 ms with nothing written between them. A single
 * read-back landing on read 4 would have aborted a deploy whose removal had
 * in fact taken, which is what `settleBindings` in `_acls.js.j2` exists to
 * survive. `enumeration-is-monotonic` carries that on a row of its own.
 *
 * Still open: whether a localized tenant names the derived level
 * differently. Both runs reported English level names.
 *
 * WHEN FINISHED: delete the list it created.
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
    && status !== 408 && status !== 429;

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
  const resetList = async (title) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
      return false;
    }
    const found = await spGet(`web/lists/getbytitle('${title}')`);
    if (!found.ok) {
      log('INFO', `CLEANUP: no list named '${title}' to remove.`);
      return false;
    }
    log('INFO', `CLEANUP: removing list '${title}' and its items.`);

    // Items first. Recycling the list takes them with it, but doing this
    // explicitly still clears the data if the list itself cannot be
    // removed. A locked or no-delete list would otherwise leave rows from
    // a previous run answering this run's questions.
    let digest = await getDigest();
    const items = await spGet(
      `web/lists/getbytitle('${title}')/items?$select=Id&$top=5000`);
    const rows = (items.ok && items.body && items.body.value) || [];
    for (const row of rows) {
      digest = await getDigest();
      await spPost(`web/lists/getbytitle('${title}')/items(${row.Id})`, {}, digest,
                   { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    }
    if (rows.length) log('INFO', `CLEANUP: deleted ${rows.length} item(s).`);
    if (rows.length === 5000) {
      log('INFO', 'CLEANUP: hit the 5000-row page limit; re-run to clear the rest.');
    }

    digest = await getDigest();
    const gone = await spPost(`web/lists/getbytitle('${title}')/recycle`, {}, digest);
    if (gone.ok) {
      log('OK', `CLEANUP: recycled list '${title}'. It is restorable from the recycle bin.`);
    } else {
      log('FAIL', `CLEANUP: could not recycle '${title}': HTTP ${gone.status} ${gone.text.slice(0, 200)}`);
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

  log('INFO', 'probe revision 819eb22e. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe OperatorGrant';
  const OWNERSHIP = 'dbml-sharepoint operator-safety-grant probe list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${LIST}')`;

  const Q_FIXTURE = 'A generic list exists and still inherits, so the break below has something to act on';
  const Q_CONTROL = 'NEGATIVE CONTROL: removeroleassignment naming a principal and a level that do not exist is refused on the broken scope';
  const Q_LEFT = 'What role assignments does breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false) leave on a list';
  const Q_OPERATOR = 'Is one of them a direct binding for the account that ran the break';
  const Q_STICKS = 'Does removing that direct binding stick, or does SharePoint re-derive it';
  const Q_MONOTONIC = 'Once a read of the role-assignment enumeration reflects a removal, does every later read reflect it';
  const Q_LEVELS = 'What level names does this tenant report at a list scope, for the English literal the deploy matches on';

  expect('access.list-acl.fixture-scratch-list', Q_FIXTURE);
  expect('access.list-acl.control-unknown-principal-refused', Q_CONTROL);
  expect('access.list-acl.break-leaves-bindings', Q_LEFT);
  expect('access.list-acl.break-leaves-operator-binding', Q_OPERATOR);
  expect('access.list-acl.operator-binding-removal-sticks', Q_STICKS);
  expect('access.list-acl.enumeration-is-monotonic', Q_MONOTONIC);
  expect('access.list-acl.derived-level-names', Q_LEVELS);

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' on ${WEB}, break its role inheritance`);
    log('INFO', 'with copyRoleAssignments=false, record exactly what bindings the break');
    log('INFO', "left, remove this account's own binding if there is one, and record");
    log('INFO', 'whether it came back. It then grants the owner group Full Control and');
    log('INFO', 'restores inheritance. Run as a site collection administrator.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off. A list left unique by an earlier run cannot answer');
      log('INFO', 'what a break leaves, so set CLEANUP = true for a clean run.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  // Track what this run broke so the restore pass knows what to reset.
  let listBroken = false;
  // And, separately, that a break was SENT at all. `listBroken` is only set
  // by a 2xx answer, so a break the server applied and then threw or refused
  // on leaves it false, and the restore's single HasUniqueRoleAssignments
  // read is measured to lag (2026-09-09,
  // `library.access.unique-permissions-library`). Two values that establish
  // nothing were being read together as proof that nothing was broken.
  let breakAttempted = false;

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  // HasUniqueRoleAssignments reports the state BEFORE the write for a moment:
  // MEASURED 2026-09-09 by library.access.unique-permissions-library, where a
  // library read false on the first read after a successful break and true on
  // the second. Every reading of it is a bounded re-read that reports each
  // attempt, so a lagging property stays separable from a break that did not
  // hold.
  const UNIQUE_TRIES = 6;
  const UNIQUE_WAIT_MS = 2000;
  const readUnique = async (wanted) => {
    const attempts = [];
    let value = null;
    for (let i = 0; i < UNIQUE_TRIES; i += 1) {
      if (i) await sleep(UNIQUE_WAIT_MS);
      const res = await spGet(`${listPath}?$select=HasUniqueRoleAssignments`);
      value = readFailed(res) ? null : res.body.HasUniqueRoleAssignments;
      attempts.push(`read ${i + 1}: HTTP ${res.status}, HasUniqueRoleAssignments=${String(value)}`);
      if (value === wanted) break;
    }
    return {
      value,
      reached: value === wanted,
      text: `${attempts.length} read(s) waiting for ${String(wanted)}: ${attempts.join('; ')}`,
    };
  };

  // One binding per (principal, level) pair, which is the shape _acls.js.j2
  // reconciles in. The login name is deliberately NOT carried out of here: the
  // only question about identity is whether a row is THIS account, and a
  // principal id answers it without putting a UPN in a transcript.
  const bindings = async () => {
    const res = await spGet(`${listPath}/roleassignments?$expand=Member,RoleDefinitionBindings&$top=200`);
    if (readFailed(res) || !Array.isArray(res.body.value)) {
      return { ok: false, status: res.status, rows: [] };
    }
    const rows = [];
    for (const row of res.body.value) {
      const member = row.Member || {};
      for (const level of (row.RoleDefinitionBindings || [])) {
        rows.push({
          principalId: Number(row.PrincipalId),
          // The LENGTH, never the text. On a live run a principal's Title is
          // the operator's display name or a group name carrying the site's,
          // and a transcript gets pasted into a pull request.
          titleLength: member.Title == null ? null : String(member.Title).length,
          principalType: member.PrincipalType,
          levelId: Number(level.Id),
          levelName: level.Name,
        });
      }
    }
    return { ok: true, status: res.status, rows };
  };

  // The window settleBindings uses in the deploy: five reads, 2000 ms apart.
  const SETTLE_READS = 5;
  const SETTLE_MS = 2000;

  // Bounded wait for one binding to appear or disappear, reporting every read
  // it took. `stopEarly` is false for the removal, because a binding that goes
  // and comes back is the finding and the first agreement would hide it.
  const settleForBinding = async (principalId, levelId, wanted, stopEarly) => {
    const reads = [];
    // The prose for a reader and the raw states beside it, because
    // enumeration-is-monotonic is derived from THIS sequence: a second set of
    // reads would answer for a different moment.
    const states = [];
    let present = null;
    for (let attempt = 0; attempt < SETTLE_READS; attempt += 1) {
      if (attempt > 0) await sleep(SETTLE_MS);
      const now = await bindings();
      present = now.ok
        ? now.rows.some((r) => r.principalId === principalId && r.levelId === levelId)
        : null;
      reads.push(`read ${attempt + 1}: HTTP ${now.status}, ${now.ok ? `${now.rows.length} row(s), ` : ''}`
                 + `binding ${present === null ? 'unreadable' : present ? 'PRESENT' : 'gone'}`);
      states.push(present);
      if (stopEarly && present === wanted) break;
    }
    return { present, reached: present === wanted, reads, states };
  };

  // One read, not the bounded poll: a caller deciding whether to RESTORE
  // cannot spend the whole settle window waiting for an answer it already has.
  // null is UNKNOWN and never false. A 2xx body that simply lacks the field
  // would otherwise read as 'inherits' and skip the reset over a list the
  // tenant holds unique, which is the one place uncertainty could fail open.
  // `readUnique` keeps the raw value for the same reason.
  const readsUnique = async () => {
    const res = await spGet(`${listPath}?$select=HasUniqueRoleAssignments`);
    if (readFailed(res)) return null;
    const value = res.body.HasUniqueRoleAssignments;
    return typeof value === 'boolean' ? value : null;
  };

  // The owner group bound to this site's full-control level, at the scratch
  // list's scope. Resolved from the tenant, never from a remembered id: a
  // wrong level id here would grant something nobody chose, and RoleTypeKind 5
  // is read rather than trusted.
  const grantOwnersFullControl = async () => {
    const owners = await spGet('web/associatedownergroup?$select=Id,Title');
    const defs = await spGet('web/roledefinitions?$select=Id,Name,RoleTypeKind&$top=100');
    const full = (!readFailed(defs) && Array.isArray(defs.body.value))
      ? defs.body.value.find((d) => Number(d.RoleTypeKind) === 5)
      : null;
    if (readFailed(owners) || !owners.body.Id || !full) {
      return { ok: false, why: 'could not resolve the owner group or a full-control level' };
    }
    const digest = await getDigest();
    const granted = await spPost(
      `${listPath}/roleassignments/addroleassignment(principalid=${owners.body.Id},roleDefId=${full.Id})`,
      {}, digest);
    return {
      ok: granted.ok,
      principalId: Number(owners.body.Id),
      levelId: Number(full.Id),
      levelName: full.Name,
      why: granted.ok ? null : `addroleassignment answered HTTP ${granted.status}`,
    };
  };

  const describe = (rows) => (
    rows.length === 0
      ? 'no rows'
      : rows.map((r) => (
        `principal ${r.principalId} (PrincipalType ${r.principalType}, `
        + `title ${r.titleLength === null ? 'absent' : `${r.titleLength} chars`}) `
        + `-> level ${r.levelId} '${r.levelName}'`
      )).join('; ')
  );

  // Runs on every path out of the questions, so a scope that is unique is
  // always put back. The owner group is granted full control FIRST and
  // deliberately after every measurement: the run may have removed this
  // account's own binding, and a scope nobody can write is a scope nobody can
  // restore.
  const restoreInheritance = async () => {
    try {
      // The UNION of the two, never one of them, and UNKNOWN resets. The flag
      // alone misses a break the server applied and answered non-2xx, or one
      // whose fetch threw after the write landed. The property alone misses a
      // break that took and has not surfaced: MEASURED 2026-09-09,
      // `library.access.unique-permissions-library`, where
      // HasUniqueRoleAssignments read FALSE on the first read after a
      // successful break and TRUE on the second, within 10 s. So a false read
      // is not permission to walk away from a break that was accepted, and an
      // unreadable one is not either. The costs are not symmetric: resetting
      // an inheriting list is a no-op write, and leaving a production list
      // broken is not. Only two falses skip.
      const unique = await readsUnique();
      if (!breakAttempted && unique === false) {
        log('OK', `'${LIST}' reads as inheriting and this run broke nothing; nothing to restore.`);
        return;
      }
      if (unique === null) {
        log('FAIL', `Could not read whether '${LIST}' holds unique permissions`
                    + `${listBroken ? ' after this run broke it' : ''}. Resetting anyway, `
                    + 'because leaving a list broken is the worse error.');
      } else if (unique === false) {
        log('INFO', `'${LIST}' reads as inheriting, and this run sent a break to it. `
                    + 'Resetting anyway: the property is measured to lag the break, and a '
                    + 'break the server applied and then threw on never sets a 2xx flag.');
      }
      // Its own catch. A transport throw here would otherwise land in the
      // outer one and skip the reset below, which is the single write this
      // pass exists to make.
      let grant;
      try {
        grant = await grantOwnersFullControl();
      } catch (err) {
        grant = { ok: false, why: `resolving or adding the safety grant threw: ${String(err)}` };
      }
      log(grant.ok ? 'OK' : 'FAIL',
          grant.ok
            ? `owner-group safety grant ('${grant.levelName}') before the reset.`
            : `No safety grant was made before the reset: ${grant.why}. If the reset below `
              + `fails, fix '${LIST}' by hand.`);
      const digest = await getDigest();
      const reset = await spPost(`${listPath}/resetroleinheritance`, {}, digest);
      if (!reset.ok) {
        log('FAIL', `Could not restore '${LIST}': HTTP ${reset.status} ${reset.text.slice(0, 200)}. `
                    + 'The list still holds unique permissions. Fix or delete it by hand.');
        return;
      }
      const after = await readUnique(false);
      log(after.reached ? 'OK' : 'FAIL',
          after.reached
            ? `'${LIST}' restored to inherited permissions.`
            : `'${LIST}' still does not read as inheriting after a successful reset. `
              + `Verify by hand. ${after.text}`);
    } catch (err) {
      log('FAIL', `restore pass failed: ${String(err)}. Check '${LIST}' by hand.`);
    }
  };

  // ---- OWNERSHIP, before either path touches the title ----------------
  // Title is never ownership. A site can already hold a list under this
  // title that somebody's work depends on, and both paths below would touch
  // it: CLEANUP recycles a title match, and a run without CLEANUP reuses it
  // and rewrites its permissions. So the Description has to carry this
  // probe's exact marker, and a read that fails for any reason other than
  // absence establishes nothing and licenses neither path.
  const claimed = await spGet(`${listPath}?$select=Title,Description`);
  if (!readFailed(claimed) && claimed.body.Description !== OWNERSHIP) {
    record('access.list-acl.fixture-scratch-list', Q_FIXTURE, 'ABORTED',
           `a list titled '${LIST}' already exists on this site and its Description is `
           + 'not this probe\'s ownership marker, so it is not a scratch list this probe '
           + 'made. Nothing was recycled, reused, broken or written. Rename or remove '
           + 'that list, or change LIST at the top of this script, and paste again.');
    return report();
  }
  // A 404 is the title being free. Anything else that did not read, a
  // refusal or a body that would not parse, leaves ownership unestablished.
  if (readFailed(claimed) && claimed.status !== 404) {
    record('access.list-acl.fixture-scratch-list', Q_FIXTURE, 'ABORTED',
           `could not read whether the title '${LIST}' is already occupied: `
           + `HTTP ${claimed.status} ${JSON.stringify(claimed.body || '').slice(0, 200)}. `
           + 'That is not the same as the title being free, so nothing was recycled, '
           + 'reused or written.');
    return report();
  }

  await resetList(LIST);
  let digest = await getDigest();

  // ---- fixture-scratch-list -------------------------------------------
  const existing = await spGet(`${listPath}?$select=Title`);
  if (!existing.ok) {
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: LIST,
      BaseTemplate: 100,
      Description: OWNERSHIP,
    }, digest);
    if (!made.ok) {
      record('access.list-acl.fixture-scratch-list', Q_FIXTURE, 'ABORTED',
             `could not create '${LIST}': HTTP ${made.status} ${made.text.slice(0, 260)}`);
      return report();
    }
  }

  // A list an earlier run left broken cannot answer what a break leaves, and
  // reporting its leftover bindings as this run's measurement is the exact
  // failure a fixture row exists to prevent.
  const beforeBreak = await readUnique(false);
  if (!beforeBreak.reached) {
    record('access.list-acl.fixture-scratch-list', Q_FIXTURE, 'ABORTED',
           `'${LIST}' does not read as inheriting before the break, so what a break `
           + `leaves cannot be observed on it. Set CLEANUP = true and paste again. `
           + beforeBreak.text);
    return report();
  }
  record('access.list-acl.fixture-scratch-list', Q_FIXTURE, 'PASS',
         `'${LIST}' exists and inherits. ${beforeBreak.text}`);

  // Every question the break gates, closed in one place. The STATE is an
  // argument because the reasons differ in kind: a throttled read clears on a
  // re-run and is open, while an account that is not an administrator can
  // never answer these and is void. Defaulting everything to void printed
  // "5 voided" for a 429, which reads as nothing further being learnable.
  const closeEveryGatedQuestion = (outcome, why, state) => {
    record('access.list-acl.control-unknown-principal-refused', Q_CONTROL, outcome, why, state);
    record('access.list-acl.break-leaves-bindings', Q_LEFT, outcome, why, state);
    record('access.list-acl.break-leaves-operator-binding', Q_OPERATOR, outcome, why, state);
    record('access.list-acl.operator-binding-removal-sticks', Q_STICKS, outcome, why, state);
    record('access.list-acl.enumeration-is-monotonic', Q_MONOTONIC, outcome, why, state);
    record('access.list-acl.derived-level-names', Q_LEVELS, outcome, why, state);
  };

  // The measurement pass, in a function of its own rather than in the body
  // of the try below. `return report()` inside a try is EVALUATED before the
  // finally runs, so each early exit printed the RESULTS block and restored
  // the list afterwards, and an operator doing what the block's last line
  // tells them left out the line saying their site was still broken.
  const measure = async () => {
    // ---- who is running this, before anything is written ---------------
    // The gate sits on the BREAK, not on the removal. Breaking with
    // copyRoleAssignments=false is the call whose result this probe exists
    // to measure, so it may leave the scope unwritable by this account, and
    // the restore would then be unable to put it back. A site collection
    // administrator keeps access to a scope whatever its bindings say.
    // IsSiteAdmin comes off the same read as the id, the way
    // library-sharing-probe.js takes it. Both are values the run DEPENDS on
    // rather than things it measures, so both are asserted.
    const me = await spGet('web/currentuser?$select=Id,PrincipalType,IsSiteAdmin');
    if (readFailed(me) || typeof me.body.IsSiteAdmin !== 'boolean') {
      // Open, not void: a 429 or a 500 here clears on a re-run.
      closeEveryGatedQuestion('NOT ESTABLISHED',
        `web/currentuser answered HTTP ${me.status} without a readable Id and IsSiteAdmin, `
        + 'so no row could be attributed to this account and no break was safe to make');
      return;
    }
    // A finite positive id, because `myId` is what every enumerated row is
    // matched against. A missing or nonnumeric Id makes it NaN, no row
    // matches, and the run reports that the break left no operator binding
    // when it never looked. That is a false answer to the experiment's own
    // premise, so the identity is asserted like IsSiteAdmin beside it.
    const myId = Number(me.body.Id);
    if (!Number.isFinite(myId) || myId <= 0) {
      closeEveryGatedQuestion('NOT ESTABLISHED',
        `web/currentuser answered HTTP ${me.status} with an Id this run cannot match a `
        + `role assignment against (${JSON.stringify(me.body.Id)}), so no binding could `
        + 'be attributed to this account. Nothing was broken.');
      return;
    }
    if (me.body.IsSiteAdmin !== true) {
      // Void: no re-run as THIS account clears it.
      closeEveryGatedQuestion('NOT REACHED',
        'this account is not a site collection administrator (web/currentuser reports '
        + 'IsSiteAdmin=false). Whether breakroleinheritance(copyRoleAssignments=false) '
        + 'leaves this account able to write the scope is the very thing being measured, '
        + 'so breaking as a non-administrator risks a list nobody can restore. Nothing '
        + `was broken and nothing was removed; the scratch list '${LIST}' was created and `
        + 'still inherits, so it is safe to delete. Re-run as a site collection '
        + 'administrator.', 'void');
      return;
    }

    // ---- the break ----------------------------------------------------
    // Asserted, not measured: every row below is about a scope that actually
    // holds unique permissions, so a break that was refused or never took
    // leaves nothing to observe rather than something to report.
    digest = await getDigest();
    // Before the write, because a fetch that throws after the server applied
    // the break is the case this flag exists for.
    breakAttempted = true;
    const broke = await spPost(
      `${listPath}/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)`,
      {}, digest);
    if (broke.ok) listBroken = true;
    const unique = broke.ok ? await readUnique(true) : null;
    if (!broke.ok || !unique.reached) {
      const why = broke.ok
        ? `the break was accepted but the list never read HasUniqueRoleAssignments=true. ${unique.text}`
        : `breakroleinheritance answered HTTP ${broke.status} ${broke.text.slice(0, 200)}`;
      // Open, not void: a refused break is a request that can be made again.
      closeEveryGatedQuestion('NOT ESTABLISHED', why);
      return;
    }

    // ---- break-leaves-bindings, derived-level-names -------------------
    // OBSERVED. Whatever came back is the answer, including nothing.
    const left = await bindings();
    if (!left.ok) {
      const why = `the role-assignment enumeration answered HTTP ${left.status}, so what the `
        + 'break left was never read. A refused read here may itself be the answer: this '
        + 'account may no longer be able to read the scope it just broke.';
      // All five open, matching the row they depend on: a refused read is a
      // read that can be made again.
      closeEveryGatedQuestion('NOT ESTABLISHED', why);
      return;
    }
    record('access.list-acl.break-leaves-bindings', Q_LEFT, 'OBSERVED',
           `${left.rows.length} binding(s) after the break: ${describe(left.rows)}`);
    const levelNames = [...new Set(left.rows.map((r) => r.levelName))];
    record('access.list-acl.derived-level-names', Q_LEVELS, 'OBSERVED',
           `level name(s) this scope reports: ${levelNames.length ? levelNames.map((n) => `'${n}'`).join(', ') : 'none'}. `
           + `_acls.js.j2 exempts the literal 'Limited Access' and matches no other name.`);

    // ---- break-leaves-operator-binding --------------------------------
    const mine = left.rows.filter((r) => r.principalId === myId);
    record('access.list-acl.break-leaves-operator-binding', Q_OPERATOR, 'OBSERVED',
           mine.length
             ? `principal ${myId} is this account and holds ${mine.length} binding(s) here: ${describe(mine)}`
             : `principal ${myId} is this account and holds NO direct binding here. The `
               + `${left.rows.length} row(s) the break left name other principals.`);

    // ---- control-unknown-principal-refused ----------------------------
    // 42424242 is far above any real principal or role definition id on a
    // tenant. If the server accepts it, a removal answering HTTP 200 below
    // proves nothing and the removal row is void.
    digest = await getDigest();
    const bogus = await spPost(
      `${listPath}/roleassignments/removeroleassignment(principalid=42424242,roleDefId=42424242)`,
      {}, digest);
    const controlHeld = !bogus.ok && isRefusal(bogus.status);
    record('access.list-acl.control-unknown-principal-refused', Q_CONTROL,
           bogus.ok ? 'FAIL' : controlHeld ? 'PASS' : 'NOT ESTABLISHED',
           bogus.ok
             ? 'removeroleassignment accepted a nonexistent principal and level with HTTP 200, '
               + 'so a 200 from the real removal below is not evidence of anything.'
             : controlHeld
               ? `refused with HTTP ${bogus.status}: ${bogus.text.slice(0, 260)}`
               : `the request failed with HTTP ${bogus.status}, which is not the server `
                 + 'rejecting the call. The removal row below is void.');

    // ---- enumeration-is-monotonic -------------------------------------
    // Derived from the reads the removal row already took, never a second
    // enumeration: a fresh sequence would answer for a different moment. The
    // question is whether a read that has once reflected the removal keeps
    // reflecting it, so the reversal to look for is a PRESENT after a gone.
    const recordMonotonic = (settled) => {
      const firstGone = settled.states.indexOf(false);
      const reversed = firstGone === -1
        ? -1
        : settled.states.findIndex((state, i) => i > firstGone && state === true);
      const unreadable = settled.states.filter((state) => state === null).length;
      const sequence = `Over ${(SETTLE_READS - 1) * SETTLE_MS} ms: `
        + `${settled.reads.join('; ')}.`
        + (unreadable
          ? ` ${unreadable} read(s) could not be read, so a reversal inside them would `
            + 'not be visible here.'
          : '');
      if (firstGone === -1) {
        record('access.list-acl.enumeration-is-monotonic', Q_MONOTONIC, 'NOT ESTABLISHED',
               'no read reported the binding gone, so the enumeration never reflected the '
               + `removal and there was no transition for a later read to reverse. ${sequence}`);
      } else if (reversed === -1) {
        record('access.list-acl.enumeration-is-monotonic', Q_MONOTONIC, 'OBSERVED',
               `the binding read gone at read ${firstGone + 1} and on every read after it. `
               + sequence);
      } else {
        record('access.list-acl.enumeration-is-monotonic', Q_MONOTONIC, 'OBSERVED',
               `NOT MONOTONIC on this tenant: the binding read gone at read ${firstGone + 1} `
               + `and PRESENT again at read ${reversed + 1}, on the same scope with nothing `
               + 'written between the two. A single read-back that had landed on read '
               + `${reversed + 1} would have reported a removal that had in fact taken. `
               + sequence);
      }
    };

    // ---- operator-binding-removal-sticks ------------------------------
    // NOT gated on the control. The control tells a re-derivation from a call
    // the server accepted and ignored, which are two CAUSES with one
    // consequence, and the consequence is the question: the deploy aborts
    // either way. A binding gone after the window is conclusive whatever a
    // 200 means, and a binding still there is the failure whatever caused it.
    if (!mine.length) {
      record('access.list-acl.operator-binding-removal-sticks', Q_STICKS,
             'NOT REACHED', 'the break left no direct binding for this account, so there was '
             + 'nothing to remove. That is an answer about the premise and not about the '
             + 'removal: on this tenant the deploy has no operator grant to prune.');
      record('access.list-acl.enumeration-is-monotonic', Q_MONOTONIC, 'NOT REACHED',
             'nothing was removed, so no read sequence was taken.');
    } else {
      // The grant comes FIRST because the deploy removes this binding from a
      // scope that already holds the declared grants: its adds and its
      // presence check both run before any removal. Removing the last
      // remaining role assignment is a different request, and a refusal of it
      // would answer a harsher question than the one asked.
      const grant = await grantOwnersFullControl();
      const landed = grant.ok
        ? await settleForBinding(grant.principalId, grant.levelId, true, true)
        : null;
      if (!grant.ok || !landed.reached) {
        record('access.list-acl.operator-binding-removal-sticks', Q_STICKS, 'NOT ESTABLISHED',
               'the scope could not be put into the condition the deploy removes from. '
               + `A declared grant had to be in place first, and ${grant.ok
                 ? `the owner-group grant never read back: ${landed.reads.join('; ')}`
                 : grant.why}. Nothing was removed.`);
        record('access.list-acl.enumeration-is-monotonic', Q_MONOTONIC, 'NOT ESTABLISHED',
               'nothing was removed, so no read sequence was taken.');
      } else {
        const target = mine[0];
        digest = await getDigest();
        const removed = await spPost(
          `${listPath}/roleassignments/removeroleassignment(principalid=${target.principalId},roleDefId=${target.levelId})`,
          {}, digest);
        // Every read, not the first agreement: the deploy's verdict is
        // whatever the LAST one sees, and a binding that goes and comes back
        // is the finding.
        const settled = await settleForBinding(
          target.principalId, target.levelId, false, false);
        // The verdict is the last read, and the control only says which
        // cause produced it.
        const cause = settled.present !== true
          ? ''
          : controlHeld
            ? ' The negative control held, so the 200 was a real acceptance and the binding '
              + 'was either re-derived by the platform or never removed.'
            : ' The negative control did NOT hold on this tenant, so this run cannot tell a '
              + 'binding the platform re-derived from a call the server accepted and ignored. '
              + 'The deploy aborts either way, which is what this question is about.';
        record('access.list-acl.operator-binding-removal-sticks', Q_STICKS,
               settled.present === null ? 'NOT ESTABLISHED'
                 : settled.present ? 'STILL PRESENT' : 'REMOVED',
               `the owner group (principal ${grant.principalId}) was granted '${grant.levelName}' `
               + 'first, so the scope held another role assignment throughout, as it does when '
               + `the deploy prunes. Then removeroleassignment(principalid=${target.principalId},`
               + `roleDefId=${target.levelId}) answered HTTP ${removed.status}`
               + `${removed.ok ? '' : ` ${removed.text.slice(0, 200)}`}. `
               + `Over ${(SETTLE_READS - 1) * SETTLE_MS} ms: ${settled.reads.join('; ')}.${cause}`);
        recordMonotonic(settled);
      }
    }
  };

  try {
    await measure();
  } catch (err) {
    log('FAIL', `the access pass aborted: ${err && err.message ? err.message : String(err)}`);
  } finally {
    await restoreInheritance();
  }

  // Once, and after the restore, so the block the operator is told to copy
  // back carries whatever the restore had to say about their site.
  return report();
})();
