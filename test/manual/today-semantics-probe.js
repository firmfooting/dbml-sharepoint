/**
 * dbml-sharepoint PROBE (WRITES TO ITS OWN SCRATCH LIST): WHAT TODAY() AND
 * NOW() EVALUATE TO IN A VALIDATION FORMULA
 *
 * QUESTION: on this tenant, at this moment, what date is TODAY() and what
 * instant is NOW() inside a validation formula, measured against values
 * whose stored instants are known?
 *
 * WHY: with the site zone set, the server clock right, and date-only values
 * stored as site-local midnight, `=[D]<=TODAY()` still refused today at
 * mid-morning while accepting yesterday. Whether NOW() is the true instant
 * decides how "not in the future" can be expressed for every date rule.
 *
 * WHAT IT DOES
 *   1. Creates `dbml-probe-today-semantics` with three columns: D (date
 *      only, validation `=[D]<=TODAY()`), W (date and time, validation
 *      `=[W]<=NOW()`), T (date only, default formula `=TODAY()`).
 *   2. Saves one item with no dates: T shows what TODAY() resolved to (D0).
 *   3. Saves D at several site-local midnights (D1 to D5) and W at several
 *      instants around now (N1 to N6), recording which the rule refuses.
 *   4. Leaves the list for the follow-up probes, which reuse it; set
 *      CLEANUP_AT_END = true on a final run to recycle it (X1).
 *
 * HOW TO RUN: F12 -> Console on the site, paste, Enter; it prints its plan.
 * Set CONFIRMED and ALLOW_WRITES to true and paste again. Copy the RESULTS
 * block back verbatim.
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
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT'];
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
    // a person records the observation; so does void, which is open for a
    // reason the control row names.
    const open = RESULTS.filter((r) => r.state !== 'settled').length;
    const waiting = RESULTS.filter((r) => r.state === 'awaiting-capture').length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} open.`);
    if (waiting) {
      console.log(`${waiting} of those are waiting on an observation somebody has to make.`);
    }
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };
  const CLEANUP_AT_END = false;
  const LIST = 'dbml-probe-today-semantics';

  expect('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock');
  expect('formula.datetime.fixture-date-columns-created', 'the three date columns are created');
  expect('formula.datetime.fixture-today-now-rules-stored', 'the TODAY() and NOW() validation formulas are stored');
  expect('formula.datetime.today-function-default-value', 'what TODAY() resolves to, through a =TODAY() default');
  expect('formula.datetime.today-allows-two-days-ago', 'D = the day before yesterday (site-local midnight) saves');
  expect('formula.datetime.today-allows-yesterday', 'D = yesterday (site-local midnight) saves');
  expect('formula.datetime.today-allows-site-midnight-today', 'D = today (site-local midnight) saves');
  expect('formula.datetime.today-allows-utc-midnight-today', 'D = today as UTC midnight saves');
  expect('formula.datetime.today-rejects-tomorrow', 'D = tomorrow (site-local midnight) is refused');
  expect('formula.datetime.now-function-minus-20h', 'W = now - 20 h');
  expect('formula.datetime.now-function-minus-12h', 'W = now - 12 h');
  expect('formula.datetime.now-function-minus-1h', 'W = now - 1 h');
  expect('formula.datetime.now-function-plus-1h', 'W = now + 1 h');
  expect('formula.datetime.now-function-plus-12h', 'W = now + 12 h');
  expect('formula.datetime.now-function-plus-20h', 'W = now + 20 h');
  expect('formula.datetime.fixture-scratch-list-recycled', 'the scratch list is recycled at the end');

  if (!CONFIRMED) {
    log('INFO', `Would create '${LIST}' on ${WEB} with three date columns and two`);
    log('INFO', 'validation formulas, save a dozen items against them, and leave the list.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }
  const enc = (t) => encodeURIComponent(t.replace(/'/g, "''"));
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const post = async (path, payload, extra = {}) => spPost(path, payload, await getDigest(), { ...VERBOSE, ...extra });
  const reason = (r) => (r.body && r.body.error && r.body.error.message && r.body.error.message.value) || r.text.slice(0, 160);
  const verdict = (r) => (r.ok ? 'SAVED' : `REFUSED HTTP ${r.status} ${reason(r)}`);

  // ---- Z: the frames --------------------------------------------------------
  const dated = await fetch(`${WEB}/_api/web/regionalsettings/timezone`, {
    headers: { Accept: 'application/json;odata=nometadata' },
  });
  const tz = await dated.json().catch(() => null);
  const info = tz && tz.Information;
  const nowUtc = new Date();
  record('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock', dated.ok ? 'PASS' : 'FAIL',
    `site zone "${tz && tz.Description}" bias=${info && info.Bias} daylight=${info && info.DaylightBias}; browser offset ${-nowUtc.getTimezoneOffset()} min; browser now ${nowUtc.toISOString()}; server ${dated.headers.get('date')}`);

  // Site-local midnight of the browser's local date plus `days`, as a UTC
  // instant. Browser and site share the zone (Z says so); if they did not,
  // this would be the browser's midnight and Z would show it.
  const localMidnightUtc = (days) =>
    new Date(nowUtc.getFullYear(), nowUtc.getMonth(), nowUtc.getDate() + days, 0, 0, 0, 0).toISOString();

  // ---- Create the scratch list -----------------------------------------------
  await resetList(LIST);
  const listPath = `web/lists/getbytitle('${enc(LIST)}')`;
  const existing = await spGet(`${listPath}?$select=Id`);
  if (existing.ok) {
    record('formula.datetime.fixture-date-columns-created', 'the three date columns are created', 'ABORTED', `a list named '${LIST}' already exists; set CLEANUP = true to recycle it first`);
    return report();
  }
  const created = await post('web/lists', {
    __metadata: { type: 'SP.List' }, BaseTemplate: 100, Title: LIST,
    Description: 'dbml-sharepoint probe of TODAY() and NOW(); safe to delete.',
  });
  if (!created.ok) {
    record('formula.datetime.fixture-date-columns-created', 'the three date columns are created', 'ABORTED', `could not create the list: HTTP ${created.status} ${reason(created)}`);
    return report();
  }
  const fields = `${listPath}/fields`;
  const addField = async (title, displayFormat, extra) => post(fields, {
    __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: title, DisplayFormat: displayFormat, ...extra,
  });
  const merge = async (title, payload) => post(`${fields}/getbytitle('${enc(title)}')`, {
    __metadata: { type: 'SP.FieldDateTime' }, ...payload,
  }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  const fD = await addField('D', 0, {});
  const fW = await addField('W', 1, {});
  const fT = await addField('T', 0, { DefaultFormula: '=TODAY()' });
  record('formula.datetime.fixture-date-columns-created', 'the three date columns are created', fD.ok && fW.ok && fT.ok ? 'PASS' : 'FAIL',
    `D ${fD.status}, W ${fW.status}, T with DefaultFormula =TODAY() ${fT.status}${fT.ok ? '' : ` ${reason(fT)}`}`);
  const vD = await merge('D', { ValidationFormula: '=[D]<=TODAY()', ValidationMessage: 'D is after TODAY()' });
  const vW = await merge('W', { ValidationFormula: '=[W]<=NOW()', ValidationMessage: 'W is after NOW()' });
  record('formula.datetime.fixture-today-now-rules-stored', 'the TODAY() and NOW() validation formulas are stored', vD.ok && vW.ok ? 'PASS' : 'FAIL',
    `D ${vD.status}${vD.ok ? '' : ` ${reason(vD)}`}; W ${vW.status}${vW.ok ? '' : ` ${reason(vW)}`}`);

  const meta = await spGet(`${listPath}?$select=ListItemEntityTypeFullName`);
  const itemType = meta.body && meta.body.ListItemEntityTypeFullName;
  const items = `${listPath}/items`;
  const save = async (label, payload) => post(items, { __metadata: { type: itemType }, Title: label, ...payload });

  // ---- D0: what TODAY() resolved to, via the default formula ------------------
  const bare = await save('bare', {});
  if (bare.ok) {
    const back = await spGet(`${items}(${bare.body.d.Id})?$select=Id,T,Created`);
    record('formula.datetime.today-function-default-value', 'what TODAY() resolves to, through a =TODAY() default', 'PASS',
      `T stored as ${back.body && back.body.T}; Created ${back.body && back.body.Created}; site-local midnight today would be ${localMidnightUtc(0)}`);
  } else {
    record('formula.datetime.today-function-default-value', 'what TODAY() resolves to, through a =TODAY() default', 'FAIL', `bare item refused: HTTP ${bare.status} ${reason(bare)}`);
  }

  // ---- D rows: date-only D against TODAY() ------------------------------------
  const utcMidnight = new Date(Date.UTC(nowUtc.getUTCFullYear(), nowUtc.getUTCMonth(), nowUtc.getUTCDate())).toISOString();
  const dates = [
    ['formula.datetime.today-allows-two-days-ago', 'D = the day before yesterday (site-local midnight) saves', localMidnightUtc(-2)],
    ['formula.datetime.today-allows-yesterday', 'D = yesterday (site-local midnight) saves', localMidnightUtc(-1)],
    ['formula.datetime.today-allows-site-midnight-today', 'D = today (site-local midnight) saves', localMidnightUtc(0)],
    ['formula.datetime.today-allows-utc-midnight-today', 'D = today as UTC midnight saves', utcMidnight],
    ['formula.datetime.today-rejects-tomorrow', 'D = tomorrow (site-local midnight) is refused', localMidnightUtc(1)],
  ];
  for (const [id, question, value] of dates) {
    const r = await save(id, { D: value });
    record(id, question, r.ok ? 'SAVED' : 'REFUSED', `${value}: ${verdict(r)}`);
  }

  // ---- N rows: datetime W against NOW() ---------------------------------------
  const hours = [['formula.datetime.now-function-minus-20h', -20], ['formula.datetime.now-function-minus-12h', -12], ['formula.datetime.now-function-minus-1h', -1], ['formula.datetime.now-function-plus-1h', 1], ['formula.datetime.now-function-plus-12h', 12], ['formula.datetime.now-function-plus-20h', 20]];
  for (const [id, h] of hours) {
    const value = new Date(nowUtc.getTime() + h * 3600 * 1000).toISOString();
    const r = await save(id, { W: value });
    record(id, `W = now ${h >= 0 ? '+' : '-'} ${Math.abs(h)} h`, r.ok ? 'SAVED' : 'REFUSED', `${value}: ${verdict(r)}`);
  }

  // ---- X1: cleanup ----------------------------------------------------------------
  if (CLEANUP_AT_END) {
    const gone = await post(`${listPath}/recycle`, {});
    record('formula.datetime.fixture-scratch-list-recycled', 'the scratch list is recycled at the end', gone.ok ? 'PASS' : 'FAIL',
      gone.ok ? `'${LIST}' recycled (restorable from the recycle bin)` : `could not recycle '${LIST}': HTTP ${gone.status} ${reason(gone)}`);
  } else {
    record('formula.datetime.fixture-scratch-list-recycled', 'the scratch list is recycled at the end', 'NOT APPLICABLE',
      `'${LIST}' left in place for the follow-up probes; set CLEANUP_AT_END = true to recycle it`);
  }
  return report();
})();
