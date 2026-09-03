/**
 * dbml-sharepoint PROBE (WRITES TO THE EXISTING SCRATCH LIST): CAN A COLUMN
 * VALIDATION FORMULA COMPARE ITS COLUMN WITH [Modified] OR [Created]?
 *
 * QUESTION: TODAY() and NOW() were measured hours behind the site. Can a
 * COLUMN validation formula compare against [Modified] or [Created] at all,
 * and if it can, does it see the instant of the save being validated?
 *
 * Runs against `dbml-probe-today-semantics`, left by the today-semantics
 * probe. Adds DM (date only, `=[DM]<=[Modified]`), DC (date only,
 * `=[DC]<=[Created]`) and WM (date and time, `=[WM]<=[Modified]`), then
 * saves items at known instants. If SharePoint refuses the formulas at C1
 * (a column rule may reference only its own column), every row below is
 * NOT APPLICABLE and the list-modified-clock probe is the one to run.
 *
 * HOW TO RUN: F12 -> Console on the site, paste, Enter; set CONFIRMED and
 * ALLOW_WRITES to true and paste again. Wait through the ten-second pause.
 * Copy the RESULTS block back.
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
  const LIST = 'dbml-probe-today-semantics';

  expect('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock');
  expect('formula.validation.column-rule-cross-column-accepted', 'column rules against [Modified] and [Created] are accepted');
  expect('formula.validation.column-modified-allows-yesterday', 'DM = yesterday (site-local midnight)');
  expect('formula.validation.column-modified-allows-today', 'DM = today (site-local midnight)');
  expect('formula.validation.column-modified-rejects-tomorrow', 'DM = tomorrow (site-local midnight)');
  expect('formula.validation.column-created-allows-today', 'DC = today (site-local midnight)');
  expect('formula.validation.column-created-rejects-tomorrow', 'DC = tomorrow (site-local midnight)');
  expect('formula.validation.column-modified-allows-hour-ago', 'WM = now - 1 h');
  expect('formula.validation.column-modified-rejects-hour-ahead', 'WM = now + 1 h');
  expect('formula.validation.column-modified-update-sees-own-save', 'an update to WM = five seconds ago saves against this save\'s Modified');

  if (!CONFIRMED) {
    log('INFO', `Would add three columns with validation rules to '${LIST}' on ${WEB} and save nine items.`);
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
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const dated = await fetch(`${WEB}/_api/web/regionalsettings/timezone`, {
    headers: { Accept: 'application/json;odata=nometadata' },
  });
  const tz = await dated.json().catch(() => null);
  const nowUtc = new Date();
  record('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock', dated.ok ? 'PASS' : 'FAIL',
    `site zone "${tz && tz.Description}"; browser offset ${-nowUtc.getTimezoneOffset()} min; browser now ${nowUtc.toISOString()}; server ${dated.headers.get('date')}`);
  const localMidnightUtc = (days) =>
    new Date(nowUtc.getFullYear(), nowUtc.getMonth(), nowUtc.getDate() + days, 0, 0, 0, 0).toISOString();

  const listPath = `web/lists/getbytitle('${enc(LIST)}')`;
  const list = await spGet(`${listPath}?$select=Id,ListItemEntityTypeFullName`);
  if (readFailed(list)) {
    record('formula.validation.column-rule-cross-column-accepted', 'column rules against [Modified] and [Created] are accepted', 'ABORTED', `list '${LIST}' not found; run the today-semantics probe first`);
    return report();
  }
  const itemType = list.body.ListItemEntityTypeFullName;
  const fields = `${listPath}/fields`;
  const items = `${listPath}/items`;
  const have = new Set(((await spGet(`${fields}?$select=Title&$top=500`)).body?.value || []).map((f) => f.Title));
  const ensure = async (title, displayFormat, formula, message) => {
    if (!have.has(title)) {
      const made = await post(fields, { __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: title, DisplayFormat: displayFormat });
      if (!made.ok) return { ok: false, detail: `${title} create ${made.status} ${reason(made)}` };
    }
    const set = await post(`${fields}/getbytitle('${enc(title)}')`, {
      __metadata: { type: 'SP.FieldDateTime' }, ValidationFormula: formula, ValidationMessage: message,
    }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    return { ok: set.ok, detail: `${title} ${set.ok ? 'rule accepted' : `rule refused ${set.status} ${reason(set)}`}` };
  };
  const rules = [
    await ensure('DM', 0, '=[DM]<=[Modified]', 'DM after Modified'),
    await ensure('DC', 0, '=[DC]<=[Created]', 'DC after Created'),
    await ensure('WM', 1, '=[WM]<=[Modified]', 'WM after Modified'),
  ];
  const accepted = rules.every((r) => r.ok);
  record('formula.validation.column-rule-cross-column-accepted', 'column rules against [Modified] and [Created] are accepted', accepted ? 'ACCEPTED' : 'REFUSED', rules.map((r) => r.detail).join('; '));
  if (!accepted) {
    for (const id of ['formula.validation.column-modified-allows-yesterday', 'formula.validation.column-modified-allows-today', 'formula.validation.column-modified-rejects-tomorrow', 'formula.validation.column-created-allows-today', 'formula.validation.column-created-rejects-tomorrow', 'formula.validation.column-modified-allows-hour-ago', 'formula.validation.column-modified-rejects-hour-ahead', 'formula.validation.column-modified-update-sees-own-save']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT APPLICABLE', 'the column rules were refused at C1, so there is nothing to save against');
    }
    return report();
  }

  const save = async (label, payload) => post(items, { __metadata: { type: itemType }, Title: label, ...payload });
  const rows = [
    ['formula.validation.column-modified-allows-yesterday', 'DM = yesterday (site-local midnight)', { DM: localMidnightUtc(-1) }],
    ['formula.validation.column-modified-allows-today', 'DM = today (site-local midnight)', { DM: localMidnightUtc(0) }],
    ['formula.validation.column-modified-rejects-tomorrow', 'DM = tomorrow (site-local midnight)', { DM: localMidnightUtc(1) }],
    ['formula.validation.column-created-allows-today', 'DC = today (site-local midnight)', { DC: localMidnightUtc(0) }],
    ['formula.validation.column-created-rejects-tomorrow', 'DC = tomorrow (site-local midnight)', { DC: localMidnightUtc(1) }],
    ['formula.validation.column-modified-allows-hour-ago', 'WM = now - 1 h', { WM: new Date(nowUtc.getTime() - 3600 * 1000).toISOString() }],
    ['formula.validation.column-modified-rejects-hour-ahead', 'WM = now + 1 h', { WM: new Date(nowUtc.getTime() + 3600 * 1000).toISOString() }],
  ];
  for (const [id, question, payload] of rows) {
    const r = await save(id, payload);
    record(id, question, r.ok ? 'SAVED' : 'REFUSED', `${JSON.stringify(payload)}: ${verdict(r)}`);
  }

  // UPDATE: does [Modified] mean THIS save, or the previous one?
  const seed = await save('update-seed', { WM: new Date(nowUtc.getTime() - 3600 * 1000).toISOString() });
  if (!seed.ok) {
    record('formula.validation.column-modified-update-sees-own-save', 'an update to WM = five seconds ago saves against this save\'s Modified', 'FAIL', `could not create the seed item: HTTP ${seed.status} ${reason(seed)}`);
    return report();
  }
  const seedId = seed.body.d.Id;
  await sleep(10000);
  const t1 = new Date();
  const value = new Date(t1.getTime() - 5000).toISOString();
  const upd = await post(`${items}(${seedId})`, { __metadata: { type: itemType }, WM: value }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  const after = await spGet(`${items}(${seedId})?$select=Id,Modified,WM`);
  record('formula.validation.column-modified-update-sees-own-save', 'an update to WM = five seconds ago saves against this save\'s Modified', upd.ok ? 'SAVED' : 'REFUSED',
    `update at ${t1.toISOString()} to ${value}: ${verdict(upd)}; Modified now ${after.body && after.body.Modified}; WM ${after.body && after.body.WM}`);
  return report();
})();
