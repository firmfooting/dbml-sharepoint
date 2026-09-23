/**
 * dbml-sharepoint PROBE: WHAT A LOOKUP SHOWS, AND WHAT IT OFFERS
 *
 * TWO QUESTIONS about the same column type, asked together because they
 * need the same pair of lists.
 *
 * QUESTION A: DOES A LOOKUP LEAK ACROSS AN ACL? When list A carries a
 * Lookup into list B, and a reader is DENIED list B, does the referencing
 * item on list A still show them B's display value?
 *
 * WHY: service-evidence-register puts `RelatedIssue` on `ServiceEvent`,
 * which every contributor can read, pointing at `ServiceIssue`, which they
 * are deliberately denied. 50-govern says "Contributors deliberately
 * cannot see ServiceIssue... a leaked one is worse than no register at
 * all". A review raised that the lookup may render the theme's title on
 * the event anyway, defeating the boundary. Nobody has measured it. This
 * project has been wrong about SharePoint by reasoning from plausibility
 * before, so the register ships the guidance that is safe under both
 * answers and this file exists to settle which answer it is.
 *
 * QUESTION B: CAN A LOOKUP OFFER FEWER ROWS? A lookup picker lists every
 * item in the target, which stops being usable at a few hundred rows and
 * offers choices that are wrong rather than merely many: a closed theme
 * should not be selectable for a new event. The widely-repeated remedy is
 * to point the lookup at a CALCULATED column that returns an empty string
 * for the rows you want hidden, on the belief that the picker omits rows
 * whose display value is empty. Two things about that are unverified here
 * and one of them can lose data:
 *
 *   - does SharePoint accept a calculated column as a lookup's display
 *     field at all? The tool's own validator does not check the TYPE of
 *     `display_column`, only that the name exists, so it would emit
 *     LookupField pointing at one and find out at deploy time.
 *   - what happens to rows ALREADY LINKED when their label later becomes
 *     empty? If an event links to a theme and the theme is then closed,
 *     the trick would blank the link on every event behind it. That is a
 *     worse failure than a long picker, and it is the reason this asks
 *     rather than recommends.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. The old mnemonic each one replaces is
 * given beside it, because the prose below and every run reported against
 * this probe quote the mnemonics.
 *
 *   -- Question A, needs the second account ------------------------------
 *   access.lookup-acl.control-target-denied           (K1)
 *        CONTROL: is the second account actually denied the TARGET list?
 *        If it can still open the target, every row below means nothing.
 *        A 401 or 403 is a denial. A 404 is also one on a tenant that
 *        hides a list the caller may not read (measured 2026-09-19, #592),
 *        but a DELETED target answers 404 too, so the 404 reading holds
 *        only once K8 has confirmed the target was still there.
 *   access.lookup-acl.display-value-to-denied-reader  (K2)
 *        THE ONE THAT MATTERS. Reading the SOURCE item as the denied
 *        account, does the lookup's display value come back?
 *   access.lookup-acl.expand-reaches-other-columns    (K3)
 *        ...and does $expand reach the target row's OTHER columns, or only
 *        the display field? A denied reader who can expand is a bigger
 *        hole than one who sees a title.
 *   access.lookup-acl.control-source-readable         (K4)
 *        CONTROL: can the denied account read the SOURCE list at all? If
 *        not, K2 and K3 are silent for the wrong reason.
 *   access.lookup-acl.control-target-present-after-read  (K8)
 *        CONTROL, pass 3, as the site owner: does the target pass 2 read
 *        (by the GUID it carries) still exist, holding the linked row with
 *        both sentinel values? It reports those four facts separately, and
 *        each row pass 2 left open names the ones it rests on: a 404-derived
 *        K1 needs the target, a withheld K2 the row and its Title, a
 *        display-field-only K3 the row and ProbeSide. A sighting after a 403
 *        is settled in pass 2 and needs nothing. Only a site collection
 *        administrator can read a 404 here as an absence.
 *
 *   -- Question B, answered by the site owner ----------------------------
 *   field.lookup.calculated-display-field             (K5)
 *        does SharePoint accept a CALCULATED column as a lookup's display
 *        field (LookupFieldName)?
 *   field.lookup.empty-label-linked-readback          (K6)
 *        ...and with the label empty for a row, what does an item ALREADY
 *        LINKED to that row read back as? This is the risky one: a theme that
 *        closes must not blank the link on the events behind it.
 *   field.lookup.picker-omits-empty-label             (K7)
 *        EYES-ON: does the New form's picker actually omit the row whose
 *        calculated label is empty? A picker is a rendering surface and no
 *        REST call can answer it.
 *
 * K5 to K7 file under `field`, not `access`, because a check is keyed to the
 * surface of its own question rather than the surface of its probe. Whether a
 * calculated column can be a lookup's display field, and what an existing
 * link reads back as when that label empties, are questions about the column
 * type. They are asked here because question A already needs the pair of
 * lists, and nothing about them is an access result.
 *
 * READ K1, K4 AND K8 FIRST. K2 is evidence only when the account is
 * provably denied the target AND provably allowed the source, and the
 * target provably existed while it was denied.
 *
 * TWO ACCOUNTS, THREE PASTES (question A only). No probe here has needed a
 * second identity before, and a site collection administrator cannot deny
 * themselves, so running it all as one person would answer a question
 * nobody asked.
 *
 *   PASS 1: as a SITE OWNER. MODE = 'setup'. Creates two lists, links
 *            rows, answers K5 and K6, prints the K7 checklist, then breaks
 *            inheritance on the target and strips every assignment except
 *            Site Owners.
 *   PASS 2: as a SECOND, NON-PRIVILEGED account, a member or visitor of
 *            this site who is NOT a site owner, site collection admin or
 *            tenant admin. MODE = 'read'. Writes NOTHING.
 *   PASS 3: as the SITE OWNER again. MODE = 'confirm', with the PASS2
 *            line pass 2 printed. Writes NOTHING. Answers K8 against the
 *            fixture pass 2 read, then settles pass 2's K1 to K3, which pass
 *            2 leaves open. Run it as a site collection administrator if you
 *            can: only one can read a missing target as deleted rather than
 *            hidden.
 *
 * If the second account turns out to be an administrator, K1 says so
 * rather than letting the run look successful.
 *
 * HOW TO RUN
 *   1. As the site owner, open a site you own at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED and ALLOW_WRITES to true, leave MODE = 'setup', paste
 *      again. Do the K7 checklist it prints before signing out.
 *   4. Sign in as the second account (a private window is easiest), open
 *      the same settings page, set MODE = 'read', paste. CONFIRMED alone is
 *      enough for pass 2; it never writes.
 *   5. Back as the site owner, set MODE = 'confirm', paste the
 *      `const PASS2 = ...;` line pass 2 printed over `const PASS2 = null;`,
 *      paste. CONFIRMED alone is enough; it never writes.
 *   6. Copy ALL THREE results blocks back, and the eyes-on lines.
 *
 * WHEN FINISHED: delete both lists as the site owner.
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

  // 'setup' writes and needs a site owner; 'read' only reads and is the
  // pass that answers question A; 'confirm' only reads, as the owner, and
  // proves the target was still there. Committed as 'setup' so a stray
  // paste by an owner is the harmless half.
  const MODE = 'setup';
  // Pass 3 only: the `const PASS2 = ...;` line pass 2 prints, pasted over this
  // one. It carries what pass 2 saw, so pass 3 confirms that fixture and not a later one.
  const PASS2 = null;

  const TARGET = 'dbmlsp Probe LookupTarget';
  const SOURCE = 'dbmlsp Probe LookupSource';
  const LOOKUP = 'ProbeLink';
  const PICK = 'ProbePick';
  const LABEL = 'ProbePickLabel';
  // Distinctive enough that finding it in a response is unambiguous, and
  // obviously not real data to anyone who stumbles on the list.
  const SECRET = 'dbmlsp-probe-target-title-should-not-leak';
  const SIDE = 'dbmlsp-probe-target-second-column';
  const CLOSED_TITLE = 'dbmlsp-probe-closed-row';

  const guidOf = (value) => String(value || '').replace(/[{}]/g, '').toLowerCase();

  // The pass-2 rows K8 decides, carried to pass 3 in PASS2 and settled there.
  const PASS2_ROWS = [
    'access.lookup-acl.control-target-denied',
    'access.lookup-acl.display-value-to-denied-reader',
    'access.lookup-acl.expand-reaches-other-columns',
  ];

  expect('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?');
  expect('access.lookup-acl.display-value-to-denied-reader', 'Reading the SOURCE item as the denied account, does the lookup display value come back?');
  expect('access.lookup-acl.expand-reaches-other-columns', 'Does $expand on the lookup reach the target row\'s other columns?');
  expect('access.lookup-acl.control-source-readable', 'CONTROL: can the denied account read the SOURCE list at all?');
  expect('access.lookup-acl.control-target-present-after-read', 'CONTROL: after pass 2, does the target pass 2 read still hold the linked row and its sentinels?');
  expect('field.lookup.calculated-display-field', 'Does SharePoint accept a CALCULATED column as a lookup display field?');
  expect('field.lookup.empty-label-linked-readback', 'With the label empty, what does an ALREADY LINKED item read back as?');
  expect('field.lookup.picker-omits-empty-label', 'EYES-ON: does the picker omit the row whose calculated label is empty?');

  if (!CONFIRMED) {
    log('INFO', `MODE is '${MODE}'.`);
    if (MODE === 'setup') {
      log('INFO', `Would create lists '${TARGET}' and '${SOURCE}' on ${WEB}, add a`);
      log('INFO', `lookup '${LOOKUP}' on Title and a second lookup '${PICK}' on a`);
      log('INFO', `calculated column '${LABEL}' that is empty for a closed row,`);
      log('INFO', 'create three rows and link them, then BREAK INHERITANCE on the');
      log('INFO', 'target and remove every assignment except Site Owners.');
      log('INFO', 'Nothing else on the site is touched.');
      if (CLEANUP) {
        log('INFO', `CLEANUP is ON: '${TARGET}' and '${SOURCE}' would be RECYCLED first.`);
      }
    } else if (MODE === 'confirm') {
      log('INFO', `Would only READ '${TARGET}' and '${SOURCE}', as the site owner.`);
      log('INFO', 'Run this pass AFTER pass 2, signed in as the site owner again.');
    } else {
      log('INFO', 'Would only READ, as the account you are signed in as now.');
      log('INFO', 'Run this pass as a NON-PRIVILEGED account, not the site owner.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED (and ALLOW_WRITES for setup).');
    return;
  }

  // ---- PASS 2: read as the denied account -----------------------------
  if (MODE === 'read') {
    const me = await spGet('web/currentuser?$select=Title,LoginName,IsSiteAdmin');
    const who = me.ok && me.body
      ? `${me.body.Title} (${me.body.LoginName}), IsSiteAdmin=${me.body.IsSiteAdmin}`
      : `could not read web/currentuser (HTTP ${me.status})`;
    log('INFO', `Running as: ${who}`);

    // K1 is the control. A site collection admin is never denied anything,
    // so an admin running this pass invalidates the run and must be told,
    // not quietly passed.
    // The source is read before K1 is judged, because a 404 on the target is
    // a denial only if the target provably existed: the fixture row linking
    // into it is the part of that proof this account can see. K8, run by
    // the owner after this pass, is the rest.
    const source = await spGet(
      `web/lists/getbytitle('${SOURCE}')/items?$select=Title,${LOOKUP}Id&$top=10`);
    const rows = (source.ok && source.body && source.body.value) || [];
    // The list the lookup is bound to and the column it shows, read while this pass measures.
    const bound = await spGet(
      `web/lists/getbytitle('${SOURCE}')/fields/getbyinternalnameortitle('${LOOKUP}')?$select=LookupList,LookupField`);
    const boundList = (!readFailed(bound) && bound.body.LookupList) || null;
    // K2 and K3 look for SECRET as the display value; shown through any other column its absence measures nothing.
    const showsTitle = !readFailed(bound) && bound.body.LookupField === 'Title';
    // Reading the list is not enough. K2 concludes "withheld" from the
    // ABSENCE of a string, so the row that would carry it has to be proven
    // present and linked first. Otherwise a deleted fixture, or one past
    // the page limit, reads as a clean security result.
    const fixture = rows.find((r) => r.Title === 'dbmlsp-probe-source-row');
    const fixtureLinked = Boolean(fixture && fixture[`${LOOKUP}Id`]);

    // By the bound GUID, not the title: a renamed target answers a title read with 404 whoever asks.
    const target = boundList
      ? await spGet(`web/lists(guid'${guidOf(boundList)}')/items?$select=Title&$top=5`)
      : null;
    const isAdmin = me.ok && me.body && me.body.IsSiteAdmin === true;
    // Only 401/403 is a DENIAL on its face. A 429 or a 500 also fails, and
    // reading either as "denied" would let K2 run believing a premise it has
    // not established. A 404 is a denial on a tenant that hides a list the
    // caller may not read (measured 2026-09-19 on a title read, #592), and it
    // is also what a deleted list answers, so it counts only with the linked
    // fixture in hand here and K8 confirming the target from the owner's side.
    const refusedTarget = Boolean(target) && (target.status === 401 || target.status === 403);
    const hiddenTarget = Boolean(target) && target.status === 404 && fixtureLinked;
    const deniedTarget = refusedTarget || hiddenTarget;
    if (!me.ok) {
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'NOT ESTABLISHED',
             `could not read web/currentuser (HTTP ${me.status}), so this run cannot `
             + 'even say who it is running as, let alone whether they are privileged.');
    } else if (isAdmin) {
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'NOT ESTABLISHED',
             `this account is a site collection administrator (${who}). SharePoint `
             + 'does not apply broken inheritance to one, so nothing below can be '
             + 'read as evidence. Re-run pass 2 as a non-privileged account.');
    } else if (!target) {
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'NOT ESTABLISHED',
             `could not read the list '${LOOKUP}' is bound to (HTTP ${bound.status}), so there `
             + 'is no target to ask about. Re-run.');
    } else if (target.ok) {
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'FAIL',
             `the account READ ${TARGET} (HTTP ${target.status}), so inheritance was `
             + 'not broken as intended and K2/K3 prove nothing about a denied reader');
    } else if (target.status === 404 && !fixtureLinked) {
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'NOT ESTABLISHED',
             'the target read answered HTTP 404, which a hidden list and a deleted one '
             + 'both answer, and the source fixture row that would show the target '
             + 'existed is not linked (see K4). Re-run the setup pass.');
    } else if (!deniedTarget) {
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'NOT ESTABLISHED',
             `the target read failed with HTTP ${target.status}, which is not an access `
             + 'denial. A throttled or erroring request is not evidence that the ACL '
             + 'holds. Re-run.');
    } else if (hiddenTarget) {
      // Open, not settled: a deleted target answers the same 404, so pass 3 settles it.
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'PASS',
             'hidden rather than refused: HTTP 404 for a list the linked source row '
             + `(${LOOKUP}Id=${fixture[`${LOOKUP}Id`]}) shows existed. This reading holds `
             + 'only if pass 3 (access.lookup-acl.control-target-present-after-read) finds '
             + `the target still there. Running as: ${who}`, 'open');
    } else {
      record('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
             'PASS',
             `refused with HTTP ${target.status}, so the account is denied the `
             + `target list. Running as: ${who}`);
    }

    // K4 is the other control, asked before K2 so the read-out order is the
    // order a reader needs them in.
    record('access.lookup-acl.control-source-readable', 'CONTROL: can the denied account read the SOURCE list at all?',
           !source.ok ? 'FAIL' : fixtureLinked ? 'PASS' : 'NOT ESTABLISHED',
           !source.ok
             ? `refused with HTTP ${source.status}. K2 and K3 are silent for the `
               + 'wrong reason. Grant this account read on the source list and re-run.'
             : fixtureLinked
               ? `read ${rows.length} row(s), including the linked fixture row `
                 + `(${LOOKUP}Id=${fixture[`${LOOKUP}Id`]})`
               : `read ${rows.length} row(s) from ${SOURCE}, but the linked fixture row `
                 + `'dbmlsp-probe-source-row' is ${fixture ? 'present without a lookup id'
                                                          : 'not among them'}. K2 would `
                 + 'be reading the absence of a string that was never going to be there. '
                 + 'Re-run the setup pass.');

    if (!me.ok || !source.ok || !fixtureLinked || isAdmin || !target || target.ok || !deniedTarget
        || !showsTitle) {
      const why = !showsTitle && !readFailed(bound)
        ? `'${LOOKUP}' shows ${JSON.stringify(bound.body.LookupField)}, not Title, so the `
          + 'sentinels are not the display value it carries. Re-run the setup pass.'
        : 'a control above did not hold (see K1 and K4)';
      record('access.lookup-acl.display-value-to-denied-reader', 'Reading the SOURCE item as the denied account, does the lookup display value come back?',
             'NOT ESTABLISHED', why);
      record('access.lookup-acl.expand-reaches-other-columns', 'Does $expand on the lookup reach the target row\'s other columns?',
             'NOT ESTABLISHED', why);
    } else {
      const expanded = await spGet(
        `web/lists/getbytitle('${SOURCE}')/items?$select=Title,${LOOKUP}/Title`
        + `&$expand=${LOOKUP}&$top=10`);
      const raw = expanded.ok ? JSON.stringify(expanded.body) : '';
      const denied = expanded.status === 401 || expanded.status === 403;
      if (!expanded.ok && !denied) {
        record('access.lookup-acl.display-value-to-denied-reader', 'Reading the SOURCE item as the denied account, does the lookup display value come back?',
               'NOT ESTABLISHED',
               `the $expand read failed with HTTP ${expanded.status}, which is neither `
               + 'a denial nor an answer');
      } else {
        const leaked = raw.includes(SECRET);
        // A sighting stands on its own once the denial is settled; an absence waits for K8's sentinels.
        record('access.lookup-acl.display-value-to-denied-reader', 'Reading the SOURCE item as the denied account, does the lookup display value come back?',
               leaked ? 'LOOKUP VALUE IS VISIBLE' : 'LOOKUP VALUE IS WITHHELD',
               leaked
                 ? 'the target Title came back to an account denied the target list: '
                   + `the response contains ${JSON.stringify(SECRET)}. A lookup does not `
                   + 'respect the target list ACL, and any register relying on one to '
                   + 'hide a title is relying on nothing.'
                 : `HTTP ${expanded.status}; the response does not contain `
                   + `${JSON.stringify(SECRET)}. Body: ${JSON.stringify(raw.slice(0, 300))}`,
               leaked && !hiddenTarget ? undefined : 'open');
      }

      const side = await spGet(
        `web/lists/getbytitle('${SOURCE}')/items?$select=${LOOKUP}/Title,${LOOKUP}/ProbeSide`
        + `&$expand=${LOOKUP}&$top=10`);
      const sideRaw = side.ok ? JSON.stringify(side.body) : '';
      // A refusal is the server rejecting the query or the access. A 429 or
      // a 500 is neither, and calling one REFUSED would turn a throttle into
      // an ACL result, which K1 and K2 above already avoid.
      const sideRefused = isRefusal(side.status)
        || side.status === 401 || side.status === 403;
      const sideObserved = side.ok ? sideRaw.includes(SIDE) : sideRefused;
      record('access.lookup-acl.expand-reaches-other-columns', 'Does $expand on the lookup reach the target row\'s other columns?',
             side.ok
               ? sideRaw.includes(SIDE) ? 'OTHER COLUMNS ALSO VISIBLE'
                 : sideRaw.includes(SECRET) ? 'DISPLAY FIELD ONLY'
                 : 'NOT ESTABLISHED'
               : sideRefused ? 'REFUSED' : 'NOT ESTABLISHED',
             side.ok
               ? sideRaw.includes(SIDE)
                 ? 'a column that is NOT the lookup display field came back too '
                   + `(${JSON.stringify(SIDE)}), so the exposure is wider than the title`
                 : sideRaw.includes(SECRET)
                   ? `the display field came back and ${JSON.stringify(SIDE)} did not`
                   : 'NEITHER field came back, so this says nothing about the second '
                     + 'one: the response may simply not carry the linked row. Body: '
                     + JSON.stringify(sideRaw.slice(0, 300))
               : sideRefused
                 ? '$expand naming a second target column was refused with HTTP '
                   + `${side.status}: ${JSON.stringify(String(side.body).slice(0, 200))}`
                 : `the $expand request failed with HTTP ${side.status}, which is `
                   + 'neither a refusal nor an answer',
             sideObserved && !hiddenTarget ? undefined : 'open');
    }

    // K8 is answered by pass 3, not here. Said on the row rather than left as
    // "the run did not reach this question", which reads as a probe that stopped.
    record('access.lookup-acl.control-target-present-after-read', 'CONTROL: after pass 2, does the target pass 2 read still hold the linked row and its sentinels?',
           'NOT ESTABLISHED',
           "answered by pass 3 (MODE = 'confirm', as the owner, with the PASS2 line below). "
           + 'Until it passes, the rows above marked open stay open.');
    // What each open row rests on, so pass 3 voids a row only for a change that row depends on:
    // the target behind a 404, and the one sentinel an absence was read against.
    const behind404 = hiddenTarget ? ['target'] : [];
    const outcomeOf = (id) => RESULTS.find((r) => r.id === id).outcome;
    const needs = {
      'access.lookup-acl.control-target-denied': behind404,
      'access.lookup-acl.display-value-to-denied-reader': [...behind404,
        ...(outcomeOf('access.lookup-acl.display-value-to-denied-reader') === 'LOOKUP VALUE IS WITHHELD' ? ['row', 'title'] : [])],
      'access.lookup-acl.expand-reaches-other-columns': [...behind404,
        ...(outcomeOf('access.lookup-acl.expand-reaches-other-columns') === 'DISPLAY FIELD ONLY' ? ['row', 'side'] : [])],
    };
    const carried = Object.fromEntries(PASS2_ROWS.map((id) => {
      const row = RESULTS.find((r) => r.id === id);
      return [id, { outcome: row.outcome, evidence: row.evidence, state: row.state, needs: needs[id] }];
    }));
    const pass2 = {
      lookupList: boundList,
      linkedId: fixtureLinked ? fixture[`${LOOKUP}Id`] : null,
      rows: carried,
    };

    report();
    console.log('\n============ EYES-ON, PASS 2 ============');
    console.log('REST is not the only surface. Still signed in as this account:');
    console.log(`  1. Open ${WEB}/Lists/${encodeURIComponent(SOURCE)}/AllItems.aspx`);
    console.log(`  2. Look at the '${LOOKUP}' column, and open an item.`);
    console.log('     Does the target row title appear, is the cell blank, or is');
    console.log('     there an error?');
    console.log('     what you see: ______________________________________');
    console.log('==========================================');
    log('INFO', 'Read-only pass complete. Nothing was written.');
    log('INFO', "Now run pass 3 as the site owner: MODE = 'confirm', with this line pasted over `const PASS2 = null;`:");
    console.log(`const PASS2 = ${JSON.stringify(pass2)};`);
    return;
  }

  // ---- PASS 3: confirm, as the site owner, after pass 2 ---------------
  // Reads, as the owner, the target pass 2 read (by the GUID it carried) and
  // the linked row, and reports each fact on its own. Pass 2 said which facts
  // each open row rests on, so a change voids only the rows that depend on it.
  if (MODE === 'confirm') {
    const K8 = 'access.lookup-acl.control-target-present-after-read';
    const K8Q = 'CONTROL: after pass 2, does the target pass 2 read still hold the linked row and its sentinels?';
    const NE = 'NOT ESTABLISHED';
    const FACTS = ['target', 'row', 'title', 'side'];
    const facts = {};
    const settleRest = (verdict, why) => {
      for (const k of FACTS) if (!facts[k]) facts[k] = [verdict, why];
    };
    const establish = async () => {
      if (!PASS2 || !PASS2.rows) {
        return settleRest(NE, 'no PASS2 line: paste the `const PASS2 = ...;` line pass 2 printed over `const PASS2 = null;`');
      }
      if (!PASS2.lookupList || !PASS2.linkedId) {
        return settleRest(NE, `pass 2 recorded no bound list (${JSON.stringify(PASS2.lookupList)}) or no linked row (${JSON.stringify(PASS2.linkedId)}). Re-run pass 2.`);
      }
      // A 404 means "absent" only to an account the target's ACL does not bind.
      const me = await spGet('web/currentuser?$select=Title,LoginName,IsSiteAdmin');
      if (readFailed(me)) return settleRest(NE, `could not read web/currentuser (HTTP ${me.status})`);
      const isAdmin = me.body.IsSiteAdmin === true;
      const who = `${me.body.Title} (${me.body.LoginName}), IsSiteAdmin=${me.body.IsSiteAdmin}`;
      const listPath = `web/lists(guid'${guidOf(PASS2.lookupList)}')`;
      const list = await spGet(`${listPath}?$select=Id,HasUniqueRoleAssignments`);
      if (list.status === 404) {
        return isAdmin
          ? settleRest('FAIL', `a site collection administrator reads list ${PASS2.lookupList} as HTTP 404: the target pass 2 read is gone`)
          : settleRest(NE, `list ${PASS2.lookupList} reads as HTTP 404 to an account that is not a site collection administrator, which a deleted list and a hidden one both answer. Re-run pass 3 as one. Running as: ${who}`);
      }
      if (readFailed(list)) return settleRest(NE, `reading list ${PASS2.lookupList} answered HTTP ${list.status}`);
      // Inheritance now is reported, not required: pass 2's 403 or 404 measured the ACL it met.
      facts.target = ['PASS', `list ${PASS2.lookupList} still exists (HasUniqueRoleAssignments=${JSON.stringify(list.body.HasUniqueRoleAssignments)})`];
      const id = Number(PASS2.linkedId);
      const row = await spGet(`${listPath}/items(${id})?$select=Id,Title,ProbeSide`);
      if (row.status === 404) return settleRest('FAIL', `item ${id}, the row the source fixture linked to, is gone`);
      if (readFailed(row) || row.body.Id !== id) return settleRest(NE, `reading item ${id} answered HTTP ${row.status}`);
      facts.row = ['PASS', `item ${id} is still there`];
      facts.title = row.body.Title === SECRET
        ? ['PASS', 'Title is still the sentinel'] : ['FAIL', `Title now reads ${JSON.stringify(row.body.Title)}`];
      facts.side = row.body.ProbeSide === SIDE
        ? ['PASS', 'ProbeSide is still the sentinel'] : ['FAIL', `ProbeSide now reads ${JSON.stringify(row.body.ProbeSide)}`];
      return undefined;
    };
    await establish();
    const verdicts = FACTS.map((k) => facts[k][0]);
    record(K8, K8Q,
           verdicts.includes('FAIL') ? 'FAIL' : verdicts.every((v) => v === 'PASS') ? 'PASS' : NE,
           FACTS.map((k) => `${k}: ${facts[k][0]} (${facts[k][1]})`).join('; '));
    // Pass 2's OPEN rows, each against the facts it named. A row pass 2 settled needs nothing here.
    for (const rid of PASS2_ROWS) {
      const carried = PASS2 && PASS2.rows && PASS2.rows[rid];
      if (!carried || carried.state !== 'open') continue;
      const question = RESULTS.find((r) => r.id === rid).question;
      if (!Array.isArray(carried.needs)) {
        record(rid, question, carried.outcome, `${carried.evidence} PASS2 names no facts for it, so it stays open.`, 'open');
        continue;
      }
      const failed = carried.needs.filter((k) => facts[k][0] === 'FAIL');
      const unmet = carried.needs.filter((k) => facts[k][0] !== 'PASS');
      if (failed.length > 0) {
        record(rid, question, carried.outcome, `${carried.evidence} Void: ${failed.join(', ')} changed since pass 2.`, 'void');
      } else if (unmet.length > 0) {
        record(rid, question, carried.outcome, `${carried.evidence} Still open: ${unmet.join(', ')} not established.`, 'open');
      } else {
        record(rid, question, carried.outcome,
               `${carried.evidence} Confirmed by pass 3${carried.needs.length ? ` (${carried.needs.join(', ')})` : ''}.`);
      }
    }
    report();
    log('INFO', 'Read-only pass complete. Nothing was written.');
    return;
  }

  // ---- PASS 1: setup, as the site owner -------------------------------
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and setup must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  await resetList(SOURCE);
  await resetList(TARGET);
  let digest = await getDigest();

  const bail = (id, question, why) => {
    record(id, question, 'NOT ESTABLISHED', why);
    report();
  };

  const ensureList = async (title) => {
    const found = await spGet(`web/lists/getbytitle('${title}')`);
    if (found.ok) {
      log('INFO', `List '${title}' already exists, reusing it.`);
      return found.body;
    }
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint probe list. Safe to delete.',
    }, digest);
    if (!made.ok) {
      log('FAIL', `Could not create '${title}': HTTP ${made.status} ${made.text.slice(0, 240)}`);
      return null;
    }
    log('OK', `Created list '${title}'.`);
    return made.body;
  };

  const addField = async (list, schemaXml) => {
    digest = await getDigest();
    return spPost(`web/lists/getbytitle('${list}')/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };

  const targetList = await ensureList(TARGET);
  if (!targetList) {
    return bail('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
                `the target list could not be created (see the FAIL above)`);
  }
  const sourceList = await ensureList(SOURCE);
  if (!sourceList) {
    return bail('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
                `the source list could not be created (see the FAIL above)`);
  }

  // A second target column, so K3 can ask whether $expand reaches past the
  // display field; and a status column the calculated label keys on.
  await addField(TARGET, '<Field Type="Text" DisplayName="ProbeSide" Name="ProbeSide" />');
  await addField(TARGET, '<Field Type="Text" DisplayName="ProbeStatus" Name="ProbeStatus" />');

  // The label the picker would be pointed at: empty for a closed row.
  const labelXml =
    `<Field Type="Calculated" DisplayName="${LABEL}" Name="${LABEL}" ResultType="Text">`
    + '<Formula>=IF([ProbeStatus]="Closed","",[Title])</Formula>'
    + '<FieldRefs><FieldRef Name="ProbeStatus"/><FieldRef Name="Title"/></FieldRefs>'
    + '</Field>';
  const labelMade = await addField(TARGET, labelXml);
  if (!labelMade.ok) {
    log('FAIL', `Calculated label column refused: HTTP ${labelMade.status} `
                + labelMade.text.slice(0, 240));
  } else {
    log('OK', `Added calculated column '${LABEL}'.`);
  }

  digest = await getDigest();
  const openRow = await spPost(`web/lists/getbytitle('${TARGET}')/items`,
                               { Title: SECRET, ProbeSide: SIDE, ProbeStatus: 'Open' }, digest);
  digest = await getDigest();
  // Created OPEN, so its calculated label is populated. K6 closes it AFTER
  // the link exists. The transition is the question, and a row born closed
  // would only have shown what linking to an already-empty label does.
  const closedRow = await spPost(`web/lists/getbytitle('${TARGET}')/items`,
                                 { Title: CLOSED_TITLE, ProbeStatus: 'Open' }, digest);
  if (!openRow.ok || !closedRow.ok) {
    return bail('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
                `could not create the target rows: HTTP ${openRow.status}/${closedRow.status}`);
  }
  const openId = openRow.body.Id;
  const closedId = closedRow.body.Id;
  log('OK', 'Created one open and one closed row on the target.');

  const targetGuid = targetList.Id;
  const addLookup = async (name, lookupFieldName) => {
    digest = await getDigest();
    return spPost(`web/lists/getbytitle('${SOURCE}')/fields/addfield`, {
      parameters: {
        Title: name,
        FieldTypeKind: 7,
        LookupListId: targetGuid,
        LookupFieldName: lookupFieldName,
      },
    }, digest);
  };

  // The ordinary lookup, on Title. This is the one question A is about.
  const plainLookup = await addLookup(LOOKUP, 'Title');
  if (!plainLookup.ok) {
    return bail('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
                `could not add the lookup column: HTTP ${plainLookup.status} `
                + plainLookup.text.slice(0, 240));
  }
  log('OK', `Added lookup '${LOOKUP}' -> ${TARGET}.Title.`);

  // K5 is the calculated display field. The tool's validator would let this
  // through (it checks the NAME exists, never the type), so whether the
  // platform accepts it is the whole question.
  const calcLookup = await addLookup(PICK, LABEL);
  // The calculated label column has to exist before any of this means
  // anything: if addField refused IT, addfield refusing the lookup says
  // nothing about calculated display fields.
  record('field.lookup.calculated-display-field', 'Does SharePoint accept a CALCULATED column as a lookup display field?',
         !labelMade.ok ? 'NOT ESTABLISHED'
           : calcLookup.ok ? 'ACCEPTED'
           : isRefusal(calcLookup.status) ? 'REFUSED' : 'NOT ESTABLISHED',
         !labelMade.ok
           ? `the calculated column '${LABEL}' could not be created (HTTP `
             + `${labelMade.status}), so there was never a calculated display field to `
             + 'point a lookup at: ' + labelMade.text.slice(0, 200)
           : calcLookup.ok
             ? `addfield with LookupFieldName='${LABEL}' (a Calculated column) returned `
               + `HTTP ${calcLookup.status}. Accepted is not the same as usable. K6 and `
               + 'K7 are what decide that.'
             : isRefusal(calcLookup.status)
               ? `HTTP ${calcLookup.status}: ${calcLookup.text.slice(0, 300)}. The `
                 + 'empty-label trick cannot be built this way on this tenant, so a '
                 + 'shorter picker needs a different mechanism.'
               : `the request failed with HTTP ${calcLookup.status}, which is not the `
                 + 'server refusing the column: ' + calcLookup.text.slice(0, 200));

  digest = await getDigest();
  const sourceRow = await spPost(`web/lists/getbytitle('${SOURCE}')/items`, {
    Title: 'dbmlsp-probe-source-row',
    [`${LOOKUP}Id`]: openId,
  }, digest);
  if (!sourceRow.ok) {
    return bail('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
                `could not create the linked source row: HTTP ${sourceRow.status} `
                + sourceRow.text.slice(0, 240));
  }
  log('OK', 'Created and linked one source row.');

  // K6 is the risk, and the ORDER is the whole point. Link a row through the
  // CALCULATED lookup while the target's label is still populated, THEN
  // close the target so the label empties, THEN read the link back. If it
  // comes back blank, closing a theme would blank the link on every event
  // behind it, and the trick costs history to buy a shorter picker.
  //
  // Linking to a row that was already empty would answer a different and
  // much less interesting question.
  if (!calcLookup.ok) {
    record('field.lookup.empty-label-linked-readback', 'With the label empty, what does an ALREADY LINKED item read back as?',
           'NOT ESTABLISHED', 'the calculated lookup column was refused at K5');
    record('field.lookup.picker-omits-empty-label', 'EYES-ON: does the picker omit the row whose calculated label is empty?',
           'NOT ESTABLISHED', 'the calculated lookup column was refused at K5');
  } else {
    digest = await getDigest();
    const linkedToClosed = await spPost(`web/lists/getbytitle('${SOURCE}')/items`, {
      Title: 'dbmlsp-probe-linked-to-closed',
      [`${PICK}Id`]: closedId,
    }, digest);
    if (!linkedToClosed.ok) {
      record('field.lookup.empty-label-linked-readback', 'With the label empty, what does an ALREADY LINKED item read back as?',
             'NOT ESTABLISHED',
             `could not link a row through '${PICK}' to the target row: HTTP `
             + `${linkedToClosed.status}: ${linkedToClosed.text.slice(0, 240)}`);
    } else {
      // BEFORE closing: prove the label is actually rendering. K6's whole
      // conclusion is drawn from the title's ABSENCE afterwards, so without
      // this a calculated column that never computed at all would read as
      // "the transition blanked it". The absence has to be shown to be a
      // CHANGE rather than the way it always was.
      const before = await spGet(
        `web/lists/getbytitle('${SOURCE}')/items(${linkedToClosed.body.Id})`
        + `?$select=${PICK}/${LABEL}&$expand=${PICK}`);
      const labelWasRendering =
        !readFailed(before) && JSON.stringify(before.body).includes(CLOSED_TITLE);
      if (!labelWasRendering) {
        record('field.lookup.empty-label-linked-readback', 'With the label empty, what does an ALREADY LINKED item read back as?',
               'NOT ESTABLISHED',
               `the link was made, but the label was NOT rendering before the target `
               + `was closed (HTTP ${before.status}; body `
               + `${JSON.stringify(String(JSON.stringify(before.body)).slice(0, 200))}). `
               + 'There is no transition to observe: an empty read afterwards would be '
               + 'the state it started in.');
        return report();
      }
      log('OK', `'${LABEL}' renders through the lookup before closing.`);

      // Now close it. The label goes empty UNDER an existing link, which is
      // the state a theme reaches when a curator concludes it.
      digest = await getDigest();
      const closed = await spPost(
        `web/lists/getbytitle('${TARGET}')/items(${closedId})`,
        { ProbeStatus: 'Closed' }, digest,
        { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
      if (!closed.ok) {
        record('field.lookup.empty-label-linked-readback', 'With the label empty, what does an ALREADY LINKED item read back as?',
               'NOT ESTABLISHED',
               `the link was made, but closing the target failed (HTTP ${closed.status}), `
               + `so the label never emptied and there is no transition to observe: `
               + closed.text.slice(0, 200));
        return report();
      }
      log('OK', `Closed the target row, so '${LABEL}' is now empty under a live link.`);
      const readBack = await spGet(
        `web/lists/getbytitle('${SOURCE}')/items(${linkedToClosed.body.Id})`
        + `?$select=Title,${PICK}Id,${PICK}/${LABEL}&$expand=${PICK}`);
      if (!readBack.ok || !readBack.body) {
        record('field.lookup.empty-label-linked-readback', 'With the label empty, what does an ALREADY LINKED item read back as?',
               'NOT ESTABLISHED',
               `the read-back failed with HTTP ${readBack.status}, so this run has no `
               + 'evidence either way');
      } else {
        const body = JSON.stringify(readBack.body);
        const keepsId = body.includes(`"${PICK}Id"`);
        const showsTitle = body.includes(CLOSED_TITLE);
        record('field.lookup.empty-label-linked-readback', 'With the label empty, what does an ALREADY LINKED item read back as?',
               showsTitle ? 'LABEL STILL RENDERS' : 'LABEL READS EMPTY',
               `${showsTitle
                   ? 'the closed row title came back anyway'
                   : 'the display value is empty for a row that IS linked'}`
               + `${keepsId ? ' (the id is still stored)' : ' (no id came back either)'}`
               + `. Body: ${JSON.stringify(body.slice(0, 300))}`);
      }
    }
  }

  // Break inheritance on the TARGET and strip every assignment except the
  // owners group, the same shape `list_permissions` deploys, done by hand
  // because this probe asks what that shape actually buys.
  digest = await getDigest();
  const broke = await spPost(
    `web/lists/getbytitle('${TARGET}')/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)`,
    {}, digest);
  if (!broke.ok) {
    return bail('access.lookup-acl.control-target-denied', 'CONTROL: is the second account actually denied the TARGET list?',
                `breakroleinheritance failed: HTTP ${broke.status} ${broke.text.slice(0, 240)}`);
  }
  log('OK', `Broke inheritance on '${TARGET}' with NO copied assignments.`);

  const owners = await spGet('web/associatedownergroup?$select=Id,Title');
  if (owners.ok && owners.body && owners.body.Id) {
    digest = await getDigest();
    const granted = await spPost(
      `web/lists/getbytitle('${TARGET}')/roleassignments/addroleassignment`
      + `(principalid=${owners.body.Id},roledefid=1073741829)`, {}, digest);
    log(granted.ok ? 'OK' : 'FAIL',
        granted.ok
          ? `Granted Full Control on '${TARGET}' to '${owners.body.Title}' only.`
          : `Could not grant owners on '${TARGET}': HTTP ${granted.status}`);
  } else {
    log('FAIL', 'Could not read the associated owner group. Grant yourself access '
                + `to '${TARGET}' by hand before deleting it.`);
  }

  report();
  console.log('\n============ EYES-ON, PASS 1 (K7) ============');
  console.log('Do this BEFORE signing out; a picker is a rendering surface and');
  console.log('no REST call can answer it.');
  console.log(`  1. Open ${WEB}/Lists/${encodeURIComponent(SOURCE)}/NewForm.aspx`);
  console.log(`  2. Open the '${PICK}' picker, the one on the CALCULATED label.`);
  console.log(`     Rows on the target are "${SECRET}" (label populated) and`);
  console.log(`     "${CLOSED_TITLE}" (label empty, because it is Closed).`);
  console.log('     Which rows does the picker offer?');
  console.log('     offered: ______________________________________');
  console.log(`  3. Open the '${LOOKUP}' picker (the one on Title) for contrast.`);
  console.log('     offered: ______________________________________');
  console.log('');
  console.log('  A picker that omits the empty-label row is the mechanism for a');
  console.log('  shorter, correct choice list. One that offers a BLANK entry is');
  console.log('  worse than doing nothing: the choice is still there and now has');
  console.log('  no name. Read this together with K6: if a linked row goes blank');
  console.log('  when its label empties, the trick costs history to buy tidiness.');
  console.log('');
  console.log('============ NOW RUN PASS 2 ============');
  console.log('Question A is unanswered until a SECOND account runs the read');
  console.log('pass. That account must NOT be a site owner, site collection');
  console.log('administrator or tenant administrator. K1 checks.');
  console.log('');
  console.log(`  1. Give the second account read access to '${SOURCE}' only.`);
  console.log(`     It must have NOTHING on '${TARGET}'.`);
  console.log('  2. Sign in as that account (a private window is easiest) and');
  console.log(`     open ${WEB}/_layouts/15/settings.aspx`);
  console.log("  3. Paste this same file with MODE = 'read' and CONFIRMED = true.");
  console.log("  4. Back as the site owner, paste with MODE = 'confirm', CONFIRMED = true and");
  console.log('     the PASS2 line pass 2 prints.');
  console.log('  5. Copy back ALL THREE results blocks and the eyes-on lines.');
  console.log('==========================================');
  log('INFO', `Delete '${SOURCE}' and '${TARGET}' when you have finished.`);
})();
