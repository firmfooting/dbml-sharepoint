/**
 * dbml-sharepoint PROBE (WRITES TO THE EXISTING SCRATCH LIST, THEN A PERSON
 * USES THE LIST): THE SAVE PATHS AND THE DEFAULT RACE THE [Modified] RULE
 * HAS NOT BEEN MEASURED THROUGH
 *
 * The shipped rule `=OR(ISBLANK([D]),[D]<=[Modified])` was measured through
 * REST and the modern form on CREATE. Unmeasured, and each a way a real user
 * saves:
 *   R1  the DEFAULT RACE: a date column with dynamic default [today] under
 *       the rule, created through REST with the date left blank, five
 *       times. The default is filled server-side at the same instant
 *       [Modified] is set; which lands first decides whether every Power
 *       Automate "Create item" against three shipped solutions is refused.
 *   R2  the same through the form's own endpoint (ValidateUpdateListItem)
 *   F1  EDIT through the modern form: an existing item, DM set to today
 *   F2  EDIT through the form: DM set to tomorrow (expect the message)
 *   G1  "Edit in grid view": DM set to today on an existing row
 *   G2  grid view: DM set to tomorrow (expect a refusal)
 *   B1  BULK EDIT: select two items, Edit, DM = today
 *   N1  NEW through the form with TR left at its prefilled default
 *   H1  (optional, CREATE_HIDDEN_LIST) can a list be created HIDDEN through
 *       REST, and does it stay out of Site contents? Informs where the
 *       verification artifact may write.
 *
 * Two runs on `dbml-probe-today-semantics`. MODE = 'setup' adds the
 * columns, sets the list rule, runs R1 and R2 and prints the human steps;
 * MODE = 'report' prints what the human steps saved.
 *
 * HOW TO RUN: F12 -> Console on the site. Set CONFIRMED, ALLOW_WRITES to
 * true and MODE as above; paste; Enter. CREATE_HIDDEN_LIST adds one more
 * list a site on hold cannot delete; leave it false unless that is fine.
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
  const CREATE_HIDDEN_LIST = false;
  const LIST = 'dbml-probe-today-semantics';
  const HIDDEN = 'dbml-probe-hidden-verify';

  expect('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock');
  expect('formula.validation.fixture-default-columns', 'TR (date) and WR (datetime) exist with dynamic default [today]');
  expect('formula.validation.fixture-three-column-modified-rule-stored', 'the list rule over DM, TR and WR against [Modified] is stored');
  expect('formula.validation.today-default-races-modified-rule-rest', 'five bare REST creates: does the [today] default race the rule?');
  expect('formula.validation.today-default-races-modified-rule-form-endpoint', 'a bare create through the form endpoint saves');
  expect('field.list.hidden-list-readback', 'a list created with Hidden=true reads back hidden');
  expect('formula.validation.form-edit-today-under-three-column-rule', 'form: Edit R1 item, DM = today saves');
  expect('formula.validation.form-edit-tomorrow-under-three-column-rule', 'form: Edit R1 item, DM = tomorrow shows the message');
  expect('formula.validation.grid-edit-today-under-modified-rule', 'grid view: DM = today sticks');
  expect('formula.validation.grid-edit-tomorrow-under-modified-rule', 'grid view: DM = tomorrow is refused');
  expect('formula.validation.bulk-edit-today-under-modified-rule', 'bulk edit: DM = today on two items saves both');
  expect('formula.validation.form-new-prefilled-default-under-modified-rule', 'form: New with TR left at its prefilled default saves');
  expect('formula.validation.fixture-path-rows-readback', 'report: the rows as saved');
  expect('formula.validation.fixture-three-column-rule-readback', 'report: the list rule as stored now');

  if (!CONFIRMED) {
    log('INFO', `Would add two columns and a list rule to '${LIST}' on ${WEB} and create six items (MODE setup), or read its rows (MODE report).`);
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

  const dated = await fetch(`${WEB}/_api/web/regionalsettings/timezone`, {
    headers: { Accept: 'application/json;odata=nometadata' },
  });
  const tz = await dated.json().catch(() => null);
  record('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock', dated.ok ? 'PASS' : 'FAIL',
    `site zone "${tz && tz.Description}"; browser offset ${-new Date().getTimezoneOffset()} min; browser now ${new Date().toISOString()}; server ${dated.headers.get('date')}`);
  const listPath = `web/lists/getbytitle('${enc(LIST)}')`;
  const list = await spGet(`${listPath}?$select=Id,ListItemEntityTypeFullName,RootFolder/ServerRelativeUrl&$expand=RootFolder`);
  if (readFailed(list)) {
    record('formula.validation.fixture-default-columns', 'TR (date) and WR (datetime) exist with dynamic default [today]', 'ABORTED', `list '${LIST}' not found; run the today-semantics probe first`);
    return report();
  }
  const itemType = list.body.ListItemEntityTypeFullName;
  const items = `${listPath}/items`;
  const fields = `${listPath}/fields`;
  const humanSteps = [
    ['formula.validation.form-edit-today-under-three-column-rule', 'form: Edit R1 item, DM = today saves', 'open item R1-1, Edit, DM = today, Save'],
    ['formula.validation.form-edit-tomorrow-under-three-column-rule', 'form: Edit R1 item, DM = tomorrow shows the message', 'open item R1-1, Edit, DM = tomorrow, Save'],
    ['formula.validation.grid-edit-today-under-modified-rule', 'grid view: DM = today sticks', 'Edit in grid view: on item R1-2 set DM = today, click away'],
    ['formula.validation.grid-edit-tomorrow-under-modified-rule', 'grid view: DM = tomorrow is refused', 'grid view: on item R1-2 set DM = tomorrow'],
    ['formula.validation.bulk-edit-today-under-modified-rule', 'bulk edit: DM = today on two items saves both', 'select R1-3 and R1-4, Edit (bulk), DM = today, Save'],
    ['formula.validation.form-new-prefilled-default-under-modified-rule', 'form: New with TR left at its prefilled default saves', 'New, Title "N1", leave TR at its prefilled value, Save; note the prefilled TR'],
  ];

  if (MODE === 'setup') {
    const have = new Set(((await spGet(`${fields}?$select=Title&$top=500`)).body?.value || []).map((f) => f.Title));
    const ensure = async (title, displayFormat) => {
      if (have.has(title)) return `${title} exists`;
      const r = await post(fields, { __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: title, DisplayFormat: displayFormat, DefaultValue: '[today]' });
      return `${title} ${r.ok ? 'created with default [today]' : `create refused ${r.status} ${reason(r)}`}`;
    };
    record('formula.validation.fixture-default-columns', 'TR (date) and WR (datetime) exist with dynamic default [today]', 'PASS', [await ensure('TR', 0), await ensure('WR', 1)].join('; '));
    const rule = '=AND(OR(ISBLANK([DM]),[DM]<=[Modified]),OR(ISBLANK([TR]),[TR]<=[Modified]),OR(ISBLANK([WR]),[WR]<=[Modified]))';
    const lv = await post(listPath, { __metadata: { type: 'SP.List' }, ValidationFormula: rule, ValidationMessage: 'probe: a date is after this save' },
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    const back = await spGet(`${listPath}?$select=ValidationFormula`);
    // MEASURED 2026-09-02: SharePoint stores `[DM]<=[Modified]` and reads it
    // back as `DM<=Modified`, so the comparison ignores the brackets, as the
    // deployer's own readback does.
    const canonical = (formula) => String(formula || '').replace(/[[\]]/g, '');
    record('formula.validation.fixture-three-column-modified-rule-stored', 'the list rule over DM, TR and WR against [Modified] is stored', lv.ok && back.body && canonical(back.body.ValidationFormula) === canonical(rule) ? 'PASS' : 'FAIL',
      lv.ok ? `stored: ${back.body && back.body.ValidationFormula}` : `HTTP ${lv.status} ${reason(lv)}`);

    // ---- R1: the default race through REST, five times --------------------
    const outcomes = [];
    for (let i = 1; i <= 5; i += 1) {
      const r = await post(items, { __metadata: { type: itemType }, Title: `R1-${i}` });
      if (r.ok) {
        const row = await spGet(`${items}(${r.body.d.Id})?$select=Id,TR,WR,Created,Modified`);
        outcomes.push(`R1-${i} SAVED id=${row.body.Id} TR=${row.body.TR} WR=${row.body.WR} Modified=${row.body.Modified}`);
      } else {
        outcomes.push(`R1-${i} ${verdict(r)}`);
      }
    }
    const saved = outcomes.filter((o) => o.includes(' SAVED ')).length;
    record('formula.validation.today-default-races-modified-rule-rest', 'five bare REST creates: does the [today] default race the rule?', saved === 5 ? 'ALL SAVED' : saved === 0 ? 'ALL REFUSED' : 'MIXED', outcomes.join(' | '));

    // ---- R2: the same through the form's endpoint -----------------------------
    const folder = list.body.RootFolder.ServerRelativeUrl;
    const r2 = await post(`${listPath}/AddValidateUpdateItemUsingPath`, {
      listItemCreateInfo: { __metadata: { type: 'SP.ListItemCreationInformationUsingPath' }, FolderPath: { __metadata: { type: 'SP.ResourcePath' }, DecodedUrl: folder } },
      formValues: [{ FieldName: 'Title', FieldValue: 'formula.validation.today-default-races-modified-rule-form-endpoint' }],
      bNewDocumentUpdate: false,
    });
    const r2rows = (r2.ok && r2.body && r2.body.d && r2.body.d.AddValidateUpdateItemUsingPath && r2.body.d.AddValidateUpdateItemUsingPath.results) || [];
    const r2err = r2rows.filter((x) => x.HasException).map((x) => `${x.FieldName}: ${x.ErrorMessage}`);
    const r2id = (r2rows.find((x) => x.FieldName === 'Id') || {}).FieldValue;
    let r2detail = r2.ok ? (r2err.length ? `REFUSED by validation: ${r2err.join('; ')}` : `SAVED id=${r2id}`) : `HTTP ${r2.status} ${reason(r2)}`;
    if (r2id) {
      const row = await spGet(`${items}(${r2id})?$select=Id,TR,WR,Modified`);
      r2detail += `; TR=${row.body && row.body.TR} WR=${row.body && row.body.WR} Modified=${row.body && row.body.Modified}`;
    }
    record('formula.validation.today-default-races-modified-rule-form-endpoint', 'a bare create through the form endpoint saves', r2.ok && !r2err.length ? 'SAVED' : 'REFUSED', r2detail);

    // ---- H1: a hidden list ------------------------------------------------------
    if (CREATE_HIDDEN_LIST) {
      const h = await post('web/lists', { __metadata: { type: 'SP.List' }, Title: HIDDEN, BaseTemplate: 100, Hidden: true, Description: 'dbml-sharepoint probe: may this list be hidden?' });
      const hb = h.ok ? await spGet(`web/lists/getbytitle('${enc(HIDDEN)}')?$select=Hidden,NoCrawl`) : null;
      record('field.list.hidden-list-readback', 'a list created with Hidden=true reads back hidden', h.ok ? (hb.body && hb.body.Hidden ? 'PASS' : 'FAIL') : 'FAIL',
        h.ok ? `Hidden=${hb.body && hb.body.Hidden} NoCrawl=${hb.body && hb.body.NoCrawl}; open Site contents and note whether '${HIDDEN}' is listed` : `create refused: HTTP ${h.status} ${reason(h)}`);
    } else {
      record('field.list.hidden-list-readback', 'a list created with Hidden=true reads back hidden', 'NOT APPLICABLE', 'CREATE_HIDDEN_LIST is off');
    }

    for (const [id, question, step] of humanSteps) {
      record(id, question, 'MANUAL', `${step}; note what happened, then run again with MODE = 'report'`);
    }
    record('formula.validation.fixture-path-rows-readback', 'report: the rows as saved', 'NOT REACHED', 'run again with MODE = report after the human steps');
    record('formula.validation.fixture-three-column-rule-readback', 'report: the list rule as stored now', 'NOT REACHED', 'run again with MODE = report after the human steps');
    log('INFO', `The list is at ${WEB}/Lists/${encodeURIComponent(LIST)}`);
  } else {
    for (const id of ['formula.validation.fixture-default-columns', 'formula.validation.fixture-three-column-modified-rule-stored', 'formula.validation.today-default-races-modified-rule-rest', 'formula.validation.today-default-races-modified-rule-form-endpoint', 'field.list.hidden-list-readback']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT APPLICABLE', 'a setup-mode question');
    }
    for (const [id, question] of humanSteps) {
      record(id, question, 'MANUAL', 'fill in from your notes of the step');
    }
    const rows = await spGet(`${items}?$select=Id,Title,DM,TR,WR,Created,Modified&$orderby=Id desc&$top=14`);
    const lines = ((rows.body && rows.body.value) || []).map((r) =>
      `id=${r.Id} title=${r.Title} DM=${r.DM} TR=${r.TR} WR=${r.WR} Created=${r.Created} Modified=${r.Modified}`);
    record('formula.validation.fixture-path-rows-readback', 'report: the rows as saved', readFailed(rows) ? 'FAIL' : 'PASS', lines.join(' | ') || 'no rows');
    const ruleNow = await spGet(`${listPath}?$select=ValidationFormula`);
    record('formula.validation.fixture-three-column-rule-readback', 'report: the list rule as stored now', 'PASS', `${ruleNow.body && ruleNow.body.ValidationFormula}`);
  }
  return report();
})();
