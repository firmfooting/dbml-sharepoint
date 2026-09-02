/**
 * dbml-sharepoint PROBE (WRITES TO THE EXISTING SCRATCH LIST, THEN A PERSON
 * USES THE FORM): COLUMN AND LIST VALIDATION THROUGH THE MODERN FORM
 *
 * QUESTION: does the modern form evaluate a column rule against TODAY() and
 * a list rule against [Modified] the same way REST does? A form validates
 * before it saves, so whether [Modified] already holds the save's instant
 * at that point is exactly what this asks.
 *
 * Two runs on `dbml-probe-today-semantics`. MODE = 'setup' puts the rules in
 * place and reads what TODAY() resolves to right now; you then use the
 * list's own form. MODE = 'report' prints what the form saved so the
 * RESULTS block can be sent back with your notes.
 *
 * Rules it sets:
 *   DT  date only, COLUMN validation `=[DT]<=TODAY()`
 *   DM  date only (already there), LIST validation
 *       `=OR(ISBLANK([DM]),[DM]<=[Modified])`
 *   T   date only (already there), default formula `=TODAY()`: a bare item
 *       shows what TODAY() resolves to right now (D0).
 *
 * THE FORM STEPS, after MODE = 'setup' (each is a MANUAL question until you
 * write down what happened):
 *   F1  New. Title "form-1", DT = today, DM blank. Save.
 *   F2  New. Title "form-2", DT = tomorrow. Expect the DT message.
 *   F3  New. Title "form-3", DM = today. Save.
 *   F4  New. Title "form-4", DM = tomorrow. Expect the DM message.
 *   F5  Edit "form-1": set DM = today. Save. (an UPDATE against [Modified])
 *   F6  Edit "form-1": set DM = tomorrow. Expect the DM message.
 *
 * HOW TO RUN: F12 -> Console on the site. Set CONFIRMED, ALLOW_WRITES to
 * true and MODE as above; paste; Enter.
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
  const MODE = 'setup'; // 'setup' first, then 'report'
  const LIST = 'dbml-probe-today-semantics';

  expect('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock');
  expect('formula.validation.fixture-dt-column', 'the DT column exists');
  expect('formula.validation.fixture-today-column-rule-stored', 'the column rule =[DT]<=TODAY() is stored');
  expect('formula.validation.fixture-modified-list-rule-stored', 'the list rule =OR(ISBLANK([DM]),[DM]<=[Modified]) is stored');
  expect('formula.datetime.today-function-default-value', 'what TODAY() resolves to right now, through the =TODAY() default');
  expect('formula.validation.form-new-today-under-today-rule', 'form: New with DT = today saves');
  expect('formula.validation.form-new-tomorrow-under-today-rule', 'form: New with DT = tomorrow shows the DT message');
  expect('formula.validation.form-new-today-under-modified-rule', 'form: New with DM = today saves');
  expect('formula.validation.form-new-tomorrow-under-modified-rule', 'form: New with DM = tomorrow shows the DM message');
  expect('formula.validation.form-edit-today-under-modified-rule', 'form: Edit form-1 to DM = today saves');
  expect('formula.validation.form-edit-tomorrow-under-modified-rule', 'form: Edit form-1 to DM = tomorrow shows the DM message');
  expect('formula.validation.fixture-form-rows-readback', 'report: the rows the form saved');
  expect('formula.validation.fixture-rules-readback', 'report: the rules as stored now');

  if (!CONFIRMED) {
    log('INFO', `Would set a column rule and a list rule on '${LIST}' on ${WEB} (MODE setup), or read its rows (MODE report).`);
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

  const dated = await fetch(`${WEB}/_api/web/regionalsettings/timezone`, {
    headers: { Accept: 'application/json;odata=nometadata' },
  });
  const tz = await dated.json().catch(() => null);
  const nowUtc = new Date();
  record('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock', dated.ok ? 'PASS' : 'FAIL',
    `site zone "${tz && tz.Description}"; browser offset ${-nowUtc.getTimezoneOffset()} min; browser now ${nowUtc.toISOString()}; server ${dated.headers.get('date')}`);
  const listPath = `web/lists/getbytitle('${enc(LIST)}')`;
  const list = await spGet(`${listPath}?$select=Id,ListItemEntityTypeFullName`);
  if (readFailed(list)) {
    record('formula.validation.fixture-dt-column', 'the DT column exists', 'ABORTED', `list '${LIST}' not found; run the today-semantics probe first`);
    return report();
  }
  const itemType = list.body.ListItemEntityTypeFullName;
  const items = `${listPath}/items`;
  const fields = `${listPath}/fields`;
  const formSteps = [
    ['formula.validation.form-new-today-under-today-rule', 'form: New with DT = today saves', 'New, Title "form-1", DT = today, DM blank, Save'],
    ['formula.validation.form-new-tomorrow-under-today-rule', 'form: New with DT = tomorrow shows the DT message', 'New, Title "form-2", DT = tomorrow, Save'],
    ['formula.validation.form-new-today-under-modified-rule', 'form: New with DM = today saves', 'New, Title "form-3", DM = today, Save'],
    ['formula.validation.form-new-tomorrow-under-modified-rule', 'form: New with DM = tomorrow shows the DM message', 'New, Title "form-4", DM = tomorrow, Save'],
    ['formula.validation.form-edit-today-under-modified-rule', 'form: Edit form-1 to DM = today saves', 'Edit "form-1", DM = today, Save'],
    ['formula.validation.form-edit-tomorrow-under-modified-rule', 'form: Edit form-1 to DM = tomorrow shows the DM message', 'Edit "form-1", DM = tomorrow, Save'],
  ];

  if (MODE === 'setup') {
    const have = new Set(((await spGet(`${fields}?$select=Title&$top=500`)).body?.value || []).map((f) => f.Title));
    let made = { ok: true, status: 'present' };
    if (!have.has('DT')) {
      made = await post(fields, { __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: 'DT', DisplayFormat: 0 });
    }
    record('formula.validation.fixture-dt-column', 'the DT column exists', made.ok ? 'PASS' : 'FAIL', made.ok ? `DT ${made.status}` : `DT create refused: HTTP ${made.status} ${reason(made)}`);
    const cv = await post(`${fields}/getbytitle('DT')`, {
      __metadata: { type: 'SP.FieldDateTime' },
      ValidationFormula: '=[DT]<=TODAY()', ValidationMessage: 'DT: TODAY() says this is in the future',
    }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    record('formula.validation.fixture-today-column-rule-stored', 'the column rule =[DT]<=TODAY() is stored', cv.ok ? 'PASS' : 'FAIL', cv.ok ? `HTTP ${cv.status}` : `HTTP ${cv.status} ${reason(cv)}`);
    const lv = await post(listPath, {
      __metadata: { type: 'SP.List' },
      ValidationFormula: '=OR(ISBLANK([DM]),[DM]<=[Modified])', ValidationMessage: 'DM: later than this save',
    }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    record('formula.validation.fixture-modified-list-rule-stored', 'the list rule =OR(ISBLANK([DM]),[DM]<=[Modified]) is stored', lv.ok ? 'PASS' : 'FAIL', lv.ok ? `HTTP ${lv.status}` : `HTTP ${lv.status} ${reason(lv)}`);
    const bare = await post(items, { __metadata: { type: itemType }, Title: 'today-now' });
    if (bare.ok) {
      const back = await spGet(`${items}(${bare.body.d.Id})?$select=Id,T,Created`);
      const siteMidnight = new Date(nowUtc.getFullYear(), nowUtc.getMonth(), nowUtc.getDate()).toISOString();
      record('formula.datetime.today-function-default-value', 'what TODAY() resolves to right now, through the =TODAY() default', 'PASS',
        `T = ${back.body && back.body.T} (site-local midnight today would be ${siteMidnight}); Created ${back.body && back.body.Created}`);
    } else {
      record('formula.datetime.today-function-default-value', 'what TODAY() resolves to right now, through the =TODAY() default', 'FAIL', `bare item refused: HTTP ${bare.status} ${reason(bare)}`);
    }
    for (const [id, question, step] of formSteps) {
      record(id, question, 'MANUAL', `${step}; note what happened, then run again with MODE = 'report'`);
    }
    record('formula.validation.fixture-form-rows-readback', 'report: the rows the form saved', 'NOT REACHED', 'run again with MODE = report after the form steps');
    record('formula.validation.fixture-rules-readback', 'report: the rules as stored now', 'NOT REACHED', 'run again with MODE = report after the form steps');
    log('INFO', `The list's form is at ${WEB}/Lists/${encodeURIComponent(LIST)}`);
  } else {
    for (const [id, question] of formSteps) {
      record(id, question, 'MANUAL', 'fill in from your notes of the form step');
    }
    const rows = await spGet(`${items}?$select=Id,Title,DT,DM,T,Created,Modified&$orderby=Id desc&$top=12`);
    const lines = ((rows.body && rows.body.value) || []).map((r) =>
      `id=${r.Id} title=${r.Title} DT=${r.DT} DM=${r.DM} T=${r.T} Created=${r.Created} Modified=${r.Modified}`);
    record('formula.validation.fixture-form-rows-readback', 'report: the rows the form saved', readFailed(rows) ? 'FAIL' : 'PASS', lines.join(' | ') || 'no rows');
    const ruleNow = await spGet(`${listPath}?$select=ValidationFormula,ValidationMessage`);
    const dt = await spGet(`${fields}/getbytitle('DT')?$select=ValidationFormula`);
    record('formula.validation.fixture-rules-readback', 'report: the rules as stored now', 'PASS',
      `list: ${ruleNow.body && ruleNow.body.ValidationFormula}; DT: ${dt.body && dt.body.ValidationFormula}`);
    for (const id of ['formula.validation.fixture-dt-column', 'formula.validation.fixture-today-column-rule-stored', 'formula.validation.fixture-modified-list-rule-stored', 'formula.datetime.today-function-default-value']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT APPLICABLE', 'a setup-mode question');
    }
  }
  return report();
})();
