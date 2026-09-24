/**
 * dbml-sharepoint PROBE (WRITES TO THE EXISTING SCRATCH LIST): IN A LIST
 * VALIDATION FORMULA, IS [Modified] THE CURRENT SAVE INSTANT IN SITE-LOCAL
 * TIME, AND IS [Created] SET ON A NEW ITEM?
 *
 * A column validation formula may reference only its own column (the
 * modified-clock probe measures that refusal). A list validation formula
 * may reference any column, so the rule goes on the list:
 *
 *   =AND(OR(ISBLANK([DM]),[DM]<=[Modified]),
 *        OR(ISBLANK([DC]),[DC]<=[Created]),
 *        OR(ISBLANK([WM]),[WM]<=[Modified]))
 *
 * WHAT IT DOES, on `dbml-probe-today-semantics` (columns from the earlier
 * probes):
 *   1. Sets that list validation formula (L1) and reads it back (L2).
 *   2. CREATE: DM at yesterday, today, tomorrow and thirty days out (D1 to
 *      D4, site-local midnights); DC at today and tomorrow (C1, C2); WM at
 *      now - 20 h, - 1 h, + 1 h, + 20 h (W1 to W4).
 *   3. UPDATE: creates an item with WM = now - 1 h (U1), waits ten seconds,
 *      updates it to WM = now - 5 s (U2), then to now + 1 h as a control
 *      (U3). U2 saved means the formula saw THIS save's instant.
 *   4. Clears the list validation formula again (X1).
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
  const LIST = 'dbml-probe-today-semantics';

  expect('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock');
  expect('formula.validation.list-modified-rule-accepted', 'the list validation formula against [Modified] and [Created] is accepted');
  expect('formula.validation.list-modified-rule-readback', 'the stored formula reads back as written');
  expect('formula.validation.list-modified-allows-yesterday', 'DM = yesterday (site-local midnight) saves');
  expect('formula.validation.list-modified-allows-today', 'DM = today (site-local midnight) saves');
  expect('formula.validation.list-modified-rejects-tomorrow', 'DM = tomorrow (site-local midnight) is refused');
  expect('formula.validation.control-list-modified-rejects-thirty-days', 'DM = thirty days out is refused (control)');
  expect('formula.validation.list-created-allows-today', 'DC = today (site-local midnight) saves');
  expect('formula.validation.list-created-rejects-tomorrow', 'DC = tomorrow (site-local midnight) is refused');
  expect('formula.validation.list-modified-allows-20h-ago', 'WM = now - 20 h saves');
  expect('formula.validation.list-modified-allows-hour-ago', 'WM = now - 1 h saves');
  expect('formula.validation.list-modified-rejects-hour-ahead', 'WM = now + 1 h is refused');
  expect('formula.validation.list-modified-rejects-20h-ahead', 'WM = now + 20 h is refused');
  expect('formula.validation.fixture-update-seed-created', 'a seed item with WM = now - 1 h is created');
  expect('formula.validation.list-modified-update-sees-own-save', 'an update to WM = five seconds before its own save saves');
  expect('formula.validation.control-list-modified-update-rejects-hour-ahead', 'an update to WM = now + 1 h is refused (control)');
  expect('formula.validation.fixture-list-rule-cleared', 'the list validation formula is cleared again');
  expect('formula.validation.fixture-dm-date-only-column', 'DM reads back as a date-only DateTime column');
  expect('formula.validation.fixture-dc-date-only-column', 'DC reads back as a date-only DateTime column');
  expect('formula.validation.fixture-wm-date-time-column', 'WM reads back as a date-and-time DateTime column');
  const RULE_ROWS = ['formula.validation.list-modified-rule-accepted', 'formula.validation.list-modified-rule-readback'];
  const DM_ROWS = ['formula.validation.list-modified-allows-yesterday', 'formula.validation.list-modified-allows-today', 'formula.validation.list-modified-rejects-tomorrow', 'formula.validation.control-list-modified-rejects-thirty-days'];
  const DC_ROWS = ['formula.validation.list-created-allows-today', 'formula.validation.list-created-rejects-tomorrow'];
  const UPDATE_ROWS = ['formula.validation.list-modified-update-sees-own-save', 'formula.validation.control-list-modified-update-rejects-hour-ahead'];
  const WM_ROWS = ['formula.validation.list-modified-allows-20h-ago', 'formula.validation.list-modified-allows-hour-ago', 'formula.validation.list-modified-rejects-hour-ahead', 'formula.validation.list-modified-rejects-20h-ahead', 'formula.validation.fixture-update-seed-created', ...UPDATE_ROWS];

  if (!CONFIRMED) {
    log('INFO', `Would set and clear a list validation formula on '${LIST}' on ${WEB} and save a dozen items.`);
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
    record('formula.validation.list-modified-rule-accepted', 'the list validation formula against [Modified] and [Created] is accepted', 'ABORTED', `list '${LIST}' not found; run the today-semantics probe first`);
    return report();
  }
  const itemType = list.body.ListItemEntityTypeFullName;
  const items = `${listPath}/items`;
  // DM, DC and WM are left by the modified-clock probe and reused by Title, so each shape is read back first.
  // The run stops on any failed column, so each fixture blocks every row.
  const ALL_ROWS = [...RULE_ROWS, ...DM_ROWS, ...DC_ROWS, ...WM_ROWS];
  const COLUMNS = [
    ['DM', 0, 'formula.validation.fixture-dm-date-only-column'],
    ['DC', 0, 'formula.validation.fixture-dc-date-only-column'],
    ['WM', 1, 'formula.validation.fixture-wm-date-time-column'],
  ];
  const fieldOf = (title) => `${listPath}/fields/getbyinternalnameortitle('${enc(title)}')`;
  const blank = (v) => v === null || v === '';
  const shapeFor = (title, displayFormat) => ({
    InternalName: title, TypeAsString: 'DateTime', DisplayFormat: displayFormat,
    ReadOnlyField: false, EnforceUniqueValues: false,
    Required: false, DefaultValue: blank, DefaultFormula: blank });
  // Identity and shape first, with no write, so a wrong-shaped column is never cleared (#644).
  let shaped = true;
  for (const [title, displayFormat, fixture] of COLUMNS) {
    shaped = await establishFixture(fixture, () => spGet(fieldOf(title)),
      shapeFor(title, displayFormat), ALL_ROWS) && shaped;
  }
  if (!shaped) return report();
  // modified-clock leaves column rules on these, which would refuse saves the list rule is measured on.
  for (const [title, displayFormat, fixture] of COLUMNS) {
    const clear = await post(fieldOf(title), { __metadata: { type: 'SP.FieldDateTime' }, ValidationFormula: '', ValidationMessage: '' },
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    log(clear.ok ? 'OK' : 'WARN', `${title} column rule clear answered HTTP ${clear.status}`);
    shaped = await establishFixture(fixture, () => spGet(fieldOf(title)),
      { ...shapeFor(title, displayFormat), ValidationFormula: blank }, ALL_ROWS) && shaped;
  }
  if (!shaped) return report();
  const setRule = async (formula, message) => post(listPath, {
    __metadata: { type: 'SP.List' }, ValidationFormula: formula, ValidationMessage: message,
  }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });

  const rule = '=AND(OR(ISBLANK([DM]),[DM]<=[Modified]),OR(ISBLANK([DC]),[DC]<=[Created]),OR(ISBLANK([WM]),[WM]<=[Modified]))';
  const set = await setRule(rule, 'probe: a date is after the save instant');
  record('formula.validation.list-modified-rule-accepted', 'the list validation formula against [Modified] and [Created] is accepted', set.ok ? 'ACCEPTED' : 'REFUSED', set.ok ? `HTTP ${set.status}` : `HTTP ${set.status} ${reason(set)}`);
  if (!set.ok) return report();
  const back = await spGet(`${listPath}?$select=ValidationFormula`);
  // SharePoint reads `[DM]<=[Modified]` back as `DM<=Modified` (measured
  // 2026-09-02), so the brackets are ignored, as the deployer's readback does.
  const canonical = (formula) => String(formula || '').replace(/[[\]]/g, '');
  record('formula.validation.list-modified-rule-readback', 'the stored formula reads back as written', back.body && canonical(back.body.ValidationFormula) === canonical(rule) ? 'PASS' : 'FAIL', `stored: ${back.body && back.body.ValidationFormula}`);

  const save = async (label, payload) => post(items, { __metadata: { type: itemType }, Title: label, ...payload });
  const rows = [
    ['formula.validation.list-modified-allows-yesterday', 'DM = yesterday (site-local midnight) saves', { DM: localMidnightUtc(-1) }],
    ['formula.validation.list-modified-allows-today', 'DM = today (site-local midnight) saves', { DM: localMidnightUtc(0) }],
    ['formula.validation.list-modified-rejects-tomorrow', 'DM = tomorrow (site-local midnight) is refused', { DM: localMidnightUtc(1) }],
    ['formula.validation.control-list-modified-rejects-thirty-days', 'DM = thirty days out is refused (control)', { DM: localMidnightUtc(30) }],
    ['formula.validation.list-created-allows-today', 'DC = today (site-local midnight) saves', { DC: localMidnightUtc(0) }],
    ['formula.validation.list-created-rejects-tomorrow', 'DC = tomorrow (site-local midnight) is refused', { DC: localMidnightUtc(1) }],
    ['formula.validation.list-modified-allows-20h-ago', 'WM = now - 20 h saves', { WM: new Date(nowUtc.getTime() - 20 * 3600 * 1000).toISOString() }],
    ['formula.validation.list-modified-allows-hour-ago', 'WM = now - 1 h saves', { WM: new Date(nowUtc.getTime() - 3600 * 1000).toISOString() }],
    ['formula.validation.list-modified-rejects-hour-ahead', 'WM = now + 1 h is refused', { WM: new Date(nowUtc.getTime() + 3600 * 1000).toISOString() }],
    ['formula.validation.list-modified-rejects-20h-ahead', 'WM = now + 20 h is refused', { WM: new Date(nowUtc.getTime() + 20 * 3600 * 1000).toISOString() }],
  ];
  for (const [id, question, payload] of rows) {
    const r = await save(id, payload);
    record(id, question, r.ok ? 'SAVED' : 'REFUSED', `${JSON.stringify(payload)}: ${verdict(r)}`);
  }

  const seed = await save('update-seed', { WM: new Date(nowUtc.getTime() - 3600 * 1000).toISOString() });
  const seedId = seed.ok && seed.body && seed.body.d ? seed.body.d.Id : null;
  if (seedId !== null && seedId !== undefined) {
    const seeded = await establishFixture('formula.validation.fixture-update-seed-created',
      () => spGet(`${items}(${seedId})?$select=Id,Modified,WM`),
      { Id: seedId, Modified: (v) => typeof v === 'string', WM: (v) => typeof v === 'string' && v !== '' },
      UPDATE_ROWS);
    if (seeded) {
      await sleep(10000);
      const t1 = new Date();
      const value = new Date(t1.getTime() - 5000).toISOString();
      const upd = await post(`${items}(${seedId})`, { __metadata: { type: itemType }, WM: value }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
      const after = await spGet(`${items}(${seedId})?$select=Id,Modified,WM`);
      record('formula.validation.list-modified-update-sees-own-save', 'an update to WM = five seconds before its own save saves', upd.ok ? 'SAVED' : 'REFUSED',
        `update at ${t1.toISOString()} to ${value}: ${verdict(upd)}; Modified now ${after.body && after.body.Modified}; WM ${after.body && after.body.WM}`);
      const upd2 = await post(`${items}(${seedId})`, { __metadata: { type: itemType }, WM: new Date(Date.now() + 3600 * 1000).toISOString() }, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
      record('formula.validation.control-list-modified-update-rejects-hour-ahead', 'an update to WM = now + 1 h is refused (control)', upd2.ok ? 'SAVED' : 'REFUSED', verdict(upd2));
    }
  } else {
    record('formula.validation.fixture-update-seed-created', 'a seed item with WM = now - 1 h is created', 'FAIL', `could not create the seed item: HTTP ${seed.status} ${reason(seed)}`);
    voidDependents(UPDATE_ROWS, 'the fixture formula.validation.fixture-update-seed-created was not created');
  }

  const cleared = await setRule('', '');
  record('formula.validation.fixture-list-rule-cleared', 'the list validation formula is cleared again', cleared.ok ? 'PASS' : 'FAIL', cleared.ok ? 'cleared' : `HTTP ${cleared.status} ${reason(cleared)}`);
  return report();
})();
