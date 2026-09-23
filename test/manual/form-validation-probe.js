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
  // `!body.X` is true both for a property that is unset and for one the site
  // never served, and only the first says the column carries nothing.
  const unset = (body, prop) => prop in body && !body[prop];

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
    // The whole field is read rather than a $select: naming a property the
    // entity does not have answers HTTP 400, which would read as "absent" for
    // a column of the right Title that is simply the wrong type. A DT left by
    // an earlier run is the normal path, since this probe has no CLEANUP.
    //
    // Requiredness and a default are part of the shape because four of the six
    // form steps leave DT blank: a DT an earlier run left required, or carrying
    // a value of its own, refuses or fills that save for a reason the step
    // never asked about, and the row is written up against the [Modified]
    // rule. Each is read as served-and-falsy, because a property the site
    // withheld is not a property that is unset.
    const dt = await spGet(`${fields}/getbyinternalnameortitle('DT')`);
    const dtShape = !readFailed(dt) && dt.body.TypeAsString === 'DateTime'
      && dt.body.DisplayFormat === 0
      && unset(dt.body, 'Required') && unset(dt.body, 'DefaultValue');
    record('formula.validation.fixture-dt-column', 'the DT column exists', dtShape ? 'PASS' : 'FAIL',
      (made.ok ? `DT ${made.status}` : `DT create refused: HTTP ${made.status} ${reason(made)}`)
      + '; ' + (readFailed(dt)
        ? `DT did not read back (HTTP ${dt.status})`
        : `reads back TypeAsString=${dt.body.TypeAsString} DisplayFormat=${dt.body.DisplayFormat}`
          + ` Required=${JSON.stringify(dt.body.Required)}`
          + ` DefaultValue=${JSON.stringify(dt.body.DefaultValue)}`));
    // MEASURED 2026-09-02 (save-instant-paths-probe): SharePoint stores
    // `[DM]<=[Modified]` and reads it back as `DM<=Modified`, so the
    // comparison ignores the brackets, as the deployer's own readback does.
    const canonical = (formula) => String(formula || '').replace(/[[\]]/g, '');
    // A MERGE answers 204 whether or not the store kept the formula, and six
    // MANUAL form findings hang off these two rows: a rule that never landed
    // would be written up as a form-versus-REST divergence. Both are read
    // back, which is what this file's own report mode already does.
    //
    // The readback runs whatever the write answered, because the question is
    // whether the rule IS stored: a MERGE throttled over a store that already
    // holds the rule is not the rule being absent, and a failed write is only
    // evidence beside the reading.
    const storedVerdict = async (sent, write, path) => {
      const back = await spGet(`${path}?$select=ValidationFormula`);
      const wrote = `MERGE answered HTTP ${write.status}${write.ok ? '' : ` ${reason(write)}`}`;
      if (readFailed(back)) {
        return { held: false, line: `${wrote}; the rule did not read back (HTTP ${back.status})` };
      }
      return {
        held: canonical(back.body.ValidationFormula) === canonical(sent),
        line: `${wrote}; sent ${JSON.stringify(sent)}, stored ${JSON.stringify(back.body.ValidationFormula)}`,
      };
    };
    const COLUMN_RULE = '=[DT]<=TODAY()';
    const cv = await post(`${fields}/getbytitle('DT')`, {
      __metadata: { type: 'SP.FieldDateTime' },
      ValidationFormula: COLUMN_RULE, ValidationMessage: 'DT: TODAY() says this is in the future',
    }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    const columnRule = await storedVerdict(COLUMN_RULE, cv, `${fields}/getbyinternalnameortitle('DT')`);
    record('formula.validation.fixture-today-column-rule-stored', 'the column rule =[DT]<=TODAY() is stored', columnRule.held ? 'PASS' : 'FAIL', columnRule.line);
    const LIST_RULE = '=OR(ISBLANK([DM]),[DM]<=[Modified])';
    const lv = await post(listPath, {
      __metadata: { type: 'SP.List' },
      ValidationFormula: LIST_RULE, ValidationMessage: 'DM: later than this save',
    }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    const listRule = await storedVerdict(LIST_RULE, lv, listPath);
    record('formula.validation.fixture-modified-list-rule-stored', 'the list rule =OR(ISBLANK([DM]),[DM]<=[Modified]) is stored', listRule.held ? 'PASS' : 'FAIL', listRule.line);
    // One bare item per list, not one per setup run: reuse an existing
    // 'today-now' row when a previous setup left one, so repeated setup runs
    // do not accumulate rows the form steps then have to look past.
    const existing = await spGet(`${items}?$select=Id,Title&$filter=${encodeURIComponent("Title eq 'today-now'")}&$top=1`);
    const left = !readFailed(existing) && Array.isArray(existing.body.value) && existing.body.value.length
      ? existing.body.value[0].Id
      : null;
    const reused = left !== null;
    const bare = reused
      ? { ok: true, status: 200, body: { d: { Id: left } } }
      : await post(items, { __metadata: { type: itemType }, Title: 'today-now' });
    // An accepted create that served no id leaves no row to read T off, and
    // `bare.body.d.Id` threw on it, losing every row the run already had.
    const bareId = bare.ok && bare.body !== null && bare.body.d ? bare.body.d.Id : null;
    if (bareId !== undefined && bareId !== null) {
      const back = await spGet(`${items}(${bareId})?$select=Id,T,Created`);
      const siteMidnight = new Date(nowUtc.getFullYear(), nowUtc.getMonth(), nowUtc.getDate()).toISOString();
      // T and its =TODAY() default come from the today-semantics probe, not
      // from here. A row that reads back blank says the default never fired,
      // and PASS would report a resolved TODAY() nobody observed.
      //
      // The question is what TODAY() resolves to RIGHT NOW, and only a row
      // this run created answers it: the default fires once, at create, so a
      // row an earlier run left holds what TODAY() resolved to on its own day.
      const filled = !readFailed(back) && back.body.T !== null && back.body.T !== undefined;
      const resolved = filled && !reused;
      record('formula.datetime.today-function-default-value', 'what TODAY() resolves to right now, through the =TODAY() default',
        resolved ? 'PASS' : 'NOT ESTABLISHED',
        readFailed(back)
          ? `the bare item did not read back (HTTP ${back.status})`
          : `T = ${JSON.stringify(back.body.T)} (site-local midnight today would be ${siteMidnight}); Created ${back.body.Created}`
            + (filled ? '' : '. Run the today-semantics probe first: T carries the =TODAY() default this reads')
            + (reused
              ? '. That row was left by an earlier setup run, so T is what TODAY() resolved to '
                + "then rather than now. Delete the 'today-now' item and run setup again."
              : ''));
    } else {
      record('formula.datetime.today-function-default-value', 'what TODAY() resolves to right now, through the =TODAY() default',
        bare.ok ? 'NOT ESTABLISHED' : 'FAIL',
        bare.ok
          ? `the bare item create answered HTTP ${bare.status} and served no id, so there is no row to read T off`
          : `bare item refused: HTTP ${bare.status} ${reason(bare)}`);
    }
    for (const [id, question, step] of formSteps) {
      record(id, question, 'MANUAL', `${step}; note what happened, then run again with MODE = 'report'`);
    }
    // A form step is only a form-versus-REST comparison while the rule it
    // names is in the store. Voided by id after the loop above, so a step
    // whose rule never landed is not handed to a person to go and perform.
    const voidSteps = (ids, why) => {
      for (const id of ids) {
        record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', why, 'void');
      }
    };
    // Every New step goes through a form that shows DT: two type a date into
    // it and two leave it blank, so a DT of another shape refuses or fills
    // those saves for a reason no step asked about. The two Edit steps open an
    // item that already carries a DT, so they are not about its shape.
    if (!dtShape) {
      voidSteps(['formula.validation.form-new-today-under-today-rule',
                 'formula.validation.form-new-tomorrow-under-today-rule',
                 'formula.validation.form-new-today-under-modified-rule',
                 'formula.validation.form-new-tomorrow-under-modified-rule'],
                'DT is not the optional, undefaulted date column the New steps type into and leave '
                + 'blank, so what the form does with one says nothing about either rule');
    }
    if (!columnRule.held) {
      voidSteps(['formula.validation.form-new-today-under-today-rule',
                 'formula.validation.form-new-tomorrow-under-today-rule'],
                'the column rule =[DT]<=TODAY() did not read back off DT, so the form has no DT '
                + 'rule to evaluate and a save either way says nothing about TODAY()');
    }
    if (!listRule.held) {
      voidSteps(['formula.validation.form-new-today-under-modified-rule',
                 'formula.validation.form-new-tomorrow-under-modified-rule',
                 'formula.validation.form-edit-today-under-modified-rule',
                 'formula.validation.form-edit-tomorrow-under-modified-rule'],
                'the list rule over [DM] and [Modified] did not read back off the list, so the '
                + 'form has no rule to evaluate and a save either way says nothing about [Modified]');
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
    const dtNow = await spGet(`${fields}/getbytitle('DT')?$select=ValidationFormula`);
    const bothRead = !readFailed(ruleNow) && !readFailed(dtNow);
    record('formula.validation.fixture-rules-readback', 'report: the rules as stored now', bothRead ? 'PASS' : 'FAIL',
      `list: ${readFailed(ruleNow) ? `did not read back (HTTP ${ruleNow.status})` : JSON.stringify(ruleNow.body.ValidationFormula)}`
      + `; DT: ${readFailed(dtNow) ? `did not read back (HTTP ${dtNow.status})` : JSON.stringify(dtNow.body.ValidationFormula)}`);
    for (const id of ['formula.validation.fixture-dt-column', 'formula.validation.fixture-today-column-rule-stored', 'formula.validation.fixture-modified-list-rule-stored', 'formula.datetime.today-function-default-value']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT APPLICABLE', 'a setup-mode question');
    }
  }
  return report();
})();
