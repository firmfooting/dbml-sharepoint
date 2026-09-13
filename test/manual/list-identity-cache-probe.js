/**
 * dbml-sharepoint PROBE: DOES A BY-TITLE LIST READ GO STALE
 *
 * REVISION: 7a53fe18
 *
 * ONE QUESTION:
 *   A list is deleted and another is created under the same title, which is
 *   what a rollback followed by a redeploy does. Does a by-title read then
 *   answer the NEW list's Id, or the dead one's?
 *
 * MEASURED on two live runs 2026-09-13: Phase 3.1's filter-editor check
 * compared the Id its write lane proved against the Id a second read
 * resolved, and they disagreed. Once for a generic list, once for a document
 * library, and 3 of 8 views passed the same check in the run where 5 failed,
 * so it is neither every list nor a property of the container kind. A third
 * read minutes later, by every spelling and cache-busted, agreed on an Id
 * that was neither of the two, because the site had been rolled back and
 * redeployed again in between. Every failing pair therefore spans a
 * delete-and-recreate under one title.
 *
 * The two sides of that comparison ask the same question by DIFFERENT URLs:
 *
 *   the ownership survey   getbytitle('X')?$select=Id,Title,BaseTemplate,...
 *   the filter-editor read getbytitle('X')?$select=Id
 *
 * Neither sends a cache directive, so they are separate cache entries and
 * one can be stale while the other is not. That is a hypothesis about a
 * TRANSPORT, not about a list, and it has never been measured here.
 *
 * The cache-busted rows are what make the answer actionable. If a plain read
 * answers the dead Id and a busted one answers the live Id, the fix is to
 * bust the cache on every by-title identity read. If BOTH answer the dead
 * Id, no cache-buster helps and the fix is to stop addressing these reads by
 * title at all.
 *
 * ROUND ONE ANSWERED IT, revision d346f6af, 2026-09-13. Both by-title reads
 * came back STALE, each naming the DEAD list, while the unique-parameter
 * read and the enumeration both named the live one. Served under
 * `Cache-Control: private, max-age=0` and `ETag: "1"`. The same run with the
 * browser's cache disabled answered FRESH on every row, which is the control
 * that rules out SharePoint itself holding the stale answer.
 *
 * So the transport is the cause, and a by-title identity read can name a
 * list that no longer exists. That cuts both ways and the dangerous way is
 * the quiet one: two reads that go stale TOGETHER agree with each other, so
 * the ownership guard passes while naming an object the run never saw.
 *
 * ROUND TWO asks which request-side directive fixes it, because the answer
 * decides the size of the change. A directive costs one line in
 * fetchWithRetry; a unique parameter on every URL does not, and it would
 * also make each read uncacheable for the rest of the session.
 *
 * SCOPE AND QUESTIONS
 *   transport.cache.fixture-list-created
 *     A generic list is created and its Id recorded.
 *   transport.cache.observed-response-headers
 *     OBSERVATION: Cache-Control, ETag, Expires and Age as served on a
 *     by-title list read. Printed, never asserted: it is what the browser
 *     decides caching from, and a tenant that answers differently is a
 *     finding rather than a failure.
 *   transport.cache.control-repeat-read-unchanged
 *     CONTROL: two identical reads with nothing written in between agree. If
 *     they do not, this run cannot attribute any later disagreement to the
 *     recreate.
 *   transport.cache.id-select-after-recreate
 *     The filter-editor read's spelling, after delete and recreate under the
 *     same title. Does it answer the new list?
 *   transport.cache.shape-select-after-recreate
 *     The ownership survey's spelling, same moment, same question.
 *   transport.cache.control-busted-after-recreate
 *     CONTROL: the same read with a unique parameter appended. A cache is
 *     only implicated if this one answers the live Id while a plain one does
 *     not.
 *   transport.cache.control-enumeration-after-recreate
 *     CONTROL: web/lists enumerated, which is the authority on which Id the
 *     title is on.
 *   transport.cache.id-select-after-recreate-library
 *     The same question on a document library, because the live evidence hit
 *     one of each and neither kind may be assumed to answer for the other.
 *   transport.cache.remedy-no-store
 *     ROUND TWO: the same stale URL read under `cache: 'no-store'`. Measured
 *     before the other two because no-store is specified not to write the
 *     entry back, so it cannot repair what the rows after it are reading.
 *   transport.cache.remedy-no-cache-header
 *     ROUND TWO: the same URL under a `Cache-Control: no-cache` REQUEST
 *     header. Expected to be the weak one: it forces revalidation rather
 *     than a fresh fetch, and a recreated list is served ETag "1" just as
 *     the dead one was, so a 304 would hand back the stale body. Measured
 *     rather than reasoned, and measured precisely so that nobody later
 *     fixes this the cheap way and ships a guard that still lies.
 *   transport.cache.remedy-reload
 *     ROUND TWO: the same URL under `cache: 'reload'`. Last, because reload
 *     does update the entry.
 *   transport.cache.plain-read-after-reload
 *     ROUND TWO: an ordinary read once reload has run, which says whether
 *     one cache-defeating read per URL repairs the entry for the reads
 *     after it, or whether every read has to carry the directive itself.
 *
 * OBSERVED, NEVER ASSERTED
 *   The caching headers, and the Ids themselves. Which Id each read answers
 *   IS the measurement; asserting one in advance would make the experiment
 *   fail on exactly the tenant it was written to measure.
 *
 * NOT MEASURED HERE
 *   How long an entry lives. Round one's cache-disabled control settled that
 *   the browser holds it rather than SharePoint, and round two settles
 *   whether a reload repairs it, so what is left open is only duration,
 *   which no fix here depends on.
 *
 * MICROSOFT LEARN CITATIONS
 *   List creation and deletion over REST, and getbytitle:
 *     "Working with lists and list items with REST"
 *   The X-HTTP-Method DELETE spelling a rollback sends:
 *     "Make a DELETE request" in the same article
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: the probe deletes what it creates and reads back to confirm
 * each one is gone, so a leftover is reported rather than assumed away.
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

  log('INFO', 'probe revision 7a53fe18. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Cache Identity';
  const LIB = 'dbmlsp Probe Cache Identity Library';

  // Written on every container this probe creates, and the only marker that
  // lets it delete one: a title is not ownership.
  const OWNERSHIP = 'dbml-sharepoint list identity cache probe. Safe to delete.';

  // The two spellings the deploy actually sends, and the Accept header it
  // sends them under. A different Accept can key a different cache entry, so
  // reproducing the transport means reproducing the header too.
  const SHAPE_SELECT = [
    'Id', 'Title', 'BaseTemplate', 'ContentTypesEnabled', 'Description',
    'EnableVersioning', 'EnableMinorVersions', 'MajorVersionLimit',
    'ValidationFormula', 'ValidationMessage',
  ].join(',');
  const VERBOSE = { Accept: 'application/json;odata=verbose' };

  const Q = {
    fixture: 'A generic list is created and its Id recorded',
    headers: 'OBSERVATION: which caching headers does a by-title list read carry',
    repeat: 'CONTROL: do two identical by-title reads agree with nothing written between them',
    idSelect: "After delete and recreate under one title, does ?$select=Id answer the NEW list",
    shapeSelect: "After the same recreate, does the ownership survey's longer $select answer it",
    busted: 'CONTROL: does the same read with a unique parameter answer the new list',
    enumerated: 'CONTROL: which Id does the web/lists enumeration put the title on',
    library: 'The same question on a document library',
    noStore: "ROUND TWO: does the same stale URL read fresh under cache: 'no-store'",
    noCacheHeader: 'ROUND TWO: does a Cache-Control: no-cache REQUEST header read it fresh',
    reload: "ROUND TWO: does the same URL read fresh under cache: 'reload'",
    afterReload: 'ROUND TWO: once reload has run, does an ORDINARY read answer the live list',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}', read its Id by two spellings, DELETE it,`);
    log('INFO', 'create another list under the same title, and read again by both');
    log('INFO', 'spellings plainly, with a cache-busting parameter, and under each of');
    log('INFO', "cache: 'no-store', a no-cache request header and cache: 'reload'.");
    log('INFO', `The same delete-and-recreate is then done for a LIBRARY '${LIB}'.`);
    log('INFO', 'A list already under either title stops the run instead: only one');
    log('INFO', 'carrying this probe\'s own description is cleared, and only with');
    log('INFO', 'CLEANUP on, which recycles it rather than deleting it.');
    log('INFO', 'Both are deleted at the end. Nothing else on the site is touched.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  const IDS = [
    'transport.cache.observed-response-headers',
    'transport.cache.control-repeat-read-unchanged',
    'transport.cache.id-select-after-recreate',
    'transport.cache.shape-select-after-recreate',
    'transport.cache.control-busted-after-recreate',
    'transport.cache.control-enumeration-after-recreate',
    'transport.cache.id-select-after-recreate-library',
    'transport.cache.remedy-no-store',
    'transport.cache.remedy-no-cache-header',
    'transport.cache.remedy-reload',
    'transport.cache.plain-read-after-reload',
  ];

  expect('transport.cache.fixture-list-created', Q.fixture);
  expect('transport.cache.observed-response-headers', Q.headers);
  expect('transport.cache.control-repeat-read-unchanged', Q.repeat);
  expect('transport.cache.id-select-after-recreate', Q.idSelect);
  expect('transport.cache.shape-select-after-recreate', Q.shapeSelect);
  expect('transport.cache.control-busted-after-recreate', Q.busted);
  expect('transport.cache.control-enumeration-after-recreate', Q.enumerated);
  expect('transport.cache.id-select-after-recreate-library', Q.library);
  expect('transport.cache.remedy-no-store', Q.noStore);
  expect('transport.cache.remedy-no-cache-header', Q.noCacheHeader);
  expect('transport.cache.remedy-reload', Q.reload);
  expect('transport.cache.plain-read-after-reload', Q.afterReload);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 200)}`;

  // Which list did this read answer? A read that failed or carried no Id
  // never answered at all, so it voids its row: recording UNEXPECTED would
  // settle it as a third identity nobody observed.
  const sayRead = (id, question, label, r, liveId, deadId, note) => {
    if (!r.ok || !r.id) {
      record(id, question, 'NOT ESTABLISHED',
             `${label} did not answer, so the list it names is unknown: ${short(r)}`,
             'void');
      return;
    }
    record(id, question,
           r.id === liveId ? 'FRESH' : r.id === deadId ? 'STALE' : 'UNEXPECTED',
           `${label} answered ${r.id}; live is ${liveId}, dead was ${deadId}`
           + (note || ''));
  };

  // Read exactly the way the deploy reads, headers included, and hand back
  // the response object too so its caching headers can be reported.
  const readVerbose = async (suffix, init = {}) => {
    const { headers: extraHeaders, ...rest } = init;
    const res = await fetch(`${WEB}/_api/${suffix}`, {
      headers: { ...VERBOSE, ...(extraHeaders || {}) },
      credentials: 'same-origin',
      ...rest,
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return {
      ok: res.ok, status: res.status, text, res,
      d: (parsed && parsed.d) || null,
      id: (parsed && parsed.d && parsed.d.Id) || null,
    };
  };

  const titlePath = (title) => `web/lists/getbytitle('${String(title).replace(/'/g, "''")}')`;
  const nonce = () => `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const readId = (title) => readVerbose(`${titlePath(title)}?$select=Id`);
  const readShape = (title) => readVerbose(`${titlePath(title)}?$select=${SHAPE_SELECT}`);
  const readBusted = (title) => readVerbose(`${titlePath(title)}?$select=Id&dbmlsp=${nonce()}`);

  // Asked on a unique URL every time, because the stale by-title entry this
  // probe exists to measure would otherwise answer its own setup questions.
  const exists = (title) => readVerbose(
    `${titlePath(title)}?$select=Id,Description&dbmlsp=${nonce()}`,
  );

  const enumeratedId = async (title) => {
    const r = await readVerbose(
      `web/lists?$select=Id,Title&$top=500&dbmlsp=${Date.now()}`,
    );
    if (!r.ok) return { error: short(r) };
    let parsed = null;
    try { parsed = JSON.parse(r.text); } catch { return { error: 'the enumeration was not JSON' }; }
    const rows = ((parsed.d && parsed.d.results) || []).filter((l) => l.Title === title);
    if (rows.length !== 1) return { error: `${rows.length} lists are titled '${title}'` };
    return { id: rows[0].Id };
  };

  const createList = async (title, template) => {
    const digest = await getDigest();
    return spPost('web/lists', {
      Title: title,
      BaseTemplate: template,
      Description: OWNERSHIP,
    }, digest);
  };

  // May this run create under `title`, and remove what is there first? A
  // container without this probe's description is never touched, and a read
  // that cannot answer counts as occupied, because the destructive branch is
  // the one that has to fail closed.
  const claimTitle = async (title) => {
    const found = await exists(title);
    if (found.status === 404) return { ok: true };
    if (!found.ok || !found.id) {
      return { ok: false, why: `could not tell whether '${title}' exists: ${short(found)}` };
    }
    if (!found.d || found.d.Description !== OWNERSHIP) {
      return {
        ok: false,
        why: `'${title}' already exists on Id ${found.id} without this probe's`
          + ' ownership description, so this run did not create it and will not'
          + ' delete it. Remove or rename it by hand and re-run.',
      };
    }
    const recycled = await resetList(title);
    if (!recycled) {
      return {
        ok: false,
        why: `'${title}' on Id ${found.id} is left over from an earlier run of this`
          + ' probe. Set CLEANUP = true to recycle it, which is restorable from the'
          + ' site recycle bin.',
      };
    }
    const after = await exists(title);
    if (after.status !== 404) {
      return { ok: false, why: `'${title}' is still present after the recycle: ${short(after)}` };
    }
    return { ok: true };
  };

  // The hard DELETE a rollback sends, not a recycle: a recycled list keeps
  // its Id in the bin and would answer a different question.
  const deleteList = async (title) => {
    const digest = await getDigest();
    const res = await fetch(`${WEB}/_api/${titlePath(title)}`, {
      method: 'POST',
      headers: {
        ...VERBOSE, 'X-RequestDigest': digest,
        'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE',
      },
      credentials: 'same-origin',
    });
    return { ok: res.ok, status: res.status, text: await res.text() };
  };

  // Cleanup is advertised as policy "after", so it is confirmed rather than
  // announced: a refused DELETE otherwise leaves a container behind silently.
  const teardown = async (title) => {
    const gone = await deleteList(title);
    const after = await exists(title);
    if (after.status === 404) return null;
    if (after.ok && after.id) {
      return `'${title}' is still on Id ${after.id} after its delete (${short(gone)})`;
    }
    return `could not confirm '${title}' is gone: delete ${short(gone)},`
      + ` read back ${short(after)}`;
  };

  // Every exit that created something runs this, so an early abort does not
  // leave a scratch container the operator was never told about.
  const finish = async (titles) => {
    const leftover = [];
    for (const title of titles) {
      const why = await teardown(title);
      if (why) leftover.push(why);
    }
    if (leftover.length) {
      log('FAIL', `cleanup did not finish: ${leftover.join('; ')}. Remove by hand.`);
    } else if (titles.length) {
      log('INFO', `deleted and confirmed absent: ${titles.join(', ')}.`);
    }
    return report();
  };

  // ---- fixture ---------------------------------------------------------
  // Only the titles this run was cleared to use, so nothing else is deleted.
  const OWNED = [];

  const claimed = await claimTitle(LIST);
  if (!claimed.ok) {
    record('transport.cache.fixture-list-created', Q.fixture, 'ABORTED', claimed.why);
    voidAll(IDS, 'the scratch title was not this run\'s to use, so nothing was created.');
    return report();
  }
  OWNED.push(LIST);

  const first = await createList(LIST, 100);
  if (!first.ok) {
    record('transport.cache.fixture-list-created', Q.fixture, 'FAIL', short(first));
    voidAll(IDS, 'the fixture list did not build, so nothing could be recreated under its title.');
    return finish(OWNED);
  }
  const before = await readId(LIST);
  const beforeShape = await readShape(LIST);
  if (!before.id) {
    record('transport.cache.fixture-list-created', Q.fixture, 'FAIL',
           `the list was created but its Id did not read back: ${short(before)}`);
    voidAll(IDS, 'the first Id was never established, so no later read can be compared to it.');
    return finish(OWNED);
  }
  record('transport.cache.fixture-list-created', Q.fixture, 'PASS',
         `'${LIST}' created on ${before.id}`);

  // The survey URL needs an entry from BEFORE the recreate. Without one, the
  // read after it is that URL's first and reports FRESH having measured
  // nothing.
  const shapePrimed = Boolean(beforeShape.ok && beforeShape.id === before.id);

  record('transport.cache.observed-response-headers', Q.headers, 'OBSERVED',
         ['Cache-Control', 'ETag', 'Expires', 'Age', 'Vary']
           .map((name) => `${name}: ${JSON.stringify(before.res.headers.get(name))}`)
           .join(', '));

  {
    const again = await readId(LIST);
    const agrees = Boolean(again.ok && again.id && again.id === before.id);
    record('transport.cache.control-repeat-read-unchanged', Q.repeat,
           agrees ? 'PASS' : 'FAIL',
           `first ${before.id}, second ${again.id}, shape-select read ${beforeShape.id}`);
    if (!agrees) {
      voidAll(IDS.slice(2),
              'two identical reads disagreed with nothing written between them, so this'
              + ' run cannot attribute any later disagreement to the recreate.');
      return finish(OWNED);
    }
  }

  // ---- delete, recreate under the same title ---------------------------
  {
    const gone = await deleteList(LIST);
    const made = gone.ok ? await createList(LIST, 100) : null;
    const live = made && made.ok ? await enumeratedId(LIST) : { error: 'the recreate failed' };
    if (!gone.ok || !made || !made.ok || live.error) {
      const why = !gone.ok ? `the delete failed: ${short(gone)}`
        : !made || !made.ok ? `the recreate failed: ${short(made || gone)}`
        : live.error;
      voidAll(IDS.slice(2), `the delete-and-recreate did not complete: ${why}`);
      return finish(OWNED);
    }

    record('transport.cache.control-enumeration-after-recreate', Q.enumerated,
           live.id === before.id ? 'UNCHANGED' : 'NEW',
           `the enumeration puts '${LIST}' on ${live.id}`
           + ` (it was ${before.id} before the recreate)`);

    const plainId = await readId(LIST);
    sayRead('transport.cache.id-select-after-recreate', Q.idSelect,
            '?$select=Id', plainId, live.id, before.id);

    if (!shapePrimed) {
      record('transport.cache.shape-select-after-recreate', Q.shapeSelect, 'NOT ESTABLISHED',
             `the survey's $select never answered ${before.id} before the recreate`
             + ` (${short(beforeShape)}), so a read of it now is that URL's first and`
             + ' cannot show a stale entry', 'void');
    } else {
      const plainShape = await readShape(LIST);
      sayRead('transport.cache.shape-select-after-recreate', Q.shapeSelect,
              "the survey's $select", plainShape, live.id, before.id);
    }

    const busted = await readBusted(LIST);
    sayRead('transport.cache.control-busted-after-recreate', Q.busted,
            'the cache-busted read', busted, live.id, before.id);

    // ---- round two: which directive on the SAME url reads it fresh ------
    // Ordered by what each one does to the entry, not by preference.
    // no-store neither reads nor writes it, so it leaves the following rows
    // measuring what they were written to measure; the no-cache header only
    // revalidates; reload refetches AND rewrites, so it goes last and
    // `afterReload` reads what it left behind.
    const noStore = await readVerbose(`${titlePath(LIST)}?$select=Id`, { cache: 'no-store' });
    sayRead('transport.cache.remedy-no-store', Q.noStore,
            "cache: 'no-store'", noStore, live.id, before.id);

    const noCacheHeader = await readVerbose(`${titlePath(LIST)}?$select=Id`,
                                            { headers: { 'Cache-Control': 'no-cache' } });
    sayRead('transport.cache.remedy-no-cache-header', Q.noCacheHeader,
            'a no-cache request header', noCacheHeader, live.id, before.id);

    const reloaded = await readVerbose(`${titlePath(LIST)}?$select=Id`, { cache: 'reload' });
    sayRead('transport.cache.remedy-reload', Q.reload,
            "cache: 'reload'", reloaded, live.id, before.id);

    const afterReload = await readId(LIST);
    sayRead('transport.cache.plain-read-after-reload', Q.afterReload,
            'an ordinary read after reload', afterReload, live.id, before.id,
            afterReload.id === live.id
              ? '. So one cache-defeating read repairs the entry for the reads after it'
              : '. So repairing the entry once is not enough and every read must carry it');
  }

  // ---- the same question on a document library -------------------------
  {
    const claimedLib = await claimTitle(LIB);
    if (!claimedLib.ok) {
      record('transport.cache.id-select-after-recreate-library', Q.library, 'NOT ESTABLISHED',
             claimedLib.why, 'void');
      return finish(OWNED);
    }
    OWNED.push(LIB);

    const made = await createList(LIB, 101);
    const firstLib = made.ok ? await readId(LIB) : null;
    let ok = Boolean(made.ok && firstLib && firstLib.id);
    let gone = null;
    let again = null;
    if (ok) {
      gone = await deleteList(LIB);
      again = gone.ok ? await createList(LIB, 101) : null;
      ok = Boolean(gone.ok && again && again.ok);
    }
    if (!ok) {
      record('transport.cache.id-select-after-recreate-library', Q.library, 'NOT ESTABLISHED',
             'the library fixture could not be built and recreated under one title', 'void');
    } else {
      const live = await enumeratedId(LIB);
      const plain = await readId(LIB);
      if (live.error) {
        record('transport.cache.id-select-after-recreate-library', Q.library,
               'NOT ESTABLISHED', live.error, 'void');
      } else {
        sayRead('transport.cache.id-select-after-recreate-library', Q.library,
                '?$select=Id', plain, live.id, firstLib.id);
      }
    }
  }

  return finish(OWNED);
})();
