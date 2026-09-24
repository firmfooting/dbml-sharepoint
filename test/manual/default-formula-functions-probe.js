/**
 * dbml-sharepoint PROBE: WHICH FUNCTIONS A DefaultFormula EVALUATES
 *
 * REVISION: a7bf7dea
 *
 * ONE QUESTION:
 *   Does a DefaultFormula calling DAY, ROUNDDOWN, MOD, TEXT, IF, AND or OR
 *   store as sent and fill a bare item create, the way the measured
 *   TODAY, YEAR, MONTH and ROUNDUP do?
 *
 * The validator admits a fixed set of functions in a default formula
 * (analysis/checks/_default_formulas.py). Four of them were measured on
 * 2026-09-13 by library-guards-probe.js: =YEAR(TODAY()) filled a Number
 * column and ="Q"&ROUNDUP(MONTH(TODAY())/3,0) filled a Choice column on a
 * bare item create. The other seven were admitted because the calculated
 * column grammar documents them, which is evidence about a calculated
 * column and not about a default formula. A /fields POST may accept and
 * read back any string, and the failure would show only as a blank at item
 * create, which is the silent class this project exists to close. Until
 * this probe has run, those seven are refused with a finding that says the
 * measurement is pending.
 *
 * The shipped family documents a financial-year customisation built from
 * IF and MOD (legal-compliance-register/README.md), so the two formulas it
 * prints are measured here as written. A single-line Text column and a
 * DateTime column (DisplayFormat 1), each carrying a default formula, are
 * measured beside them, because the same validator holds both types
 * pending: every date measurement so far used a date-only column.
 *
 * The write shape is the deploy's: a POST to /fields carrying __metadata,
 * FieldTypeKind and DefaultFormula (generators/jsgen.py), then a bare item
 * create carrying Title only.
 *
 * SCOPE AND QUESTIONS
 *   field.default-formula.fixture-list-created
 *     A generic list is created (BaseTemplate 100).
 *   field.default-formula.control-missing-column-refused
 *     NEGATIVE CONTROL: an item POST naming a column that does not exist is
 *     REFUSED. Without it, a blank below could be any server answer.
 *   field.default-formula.function-day-fills
 *   field.default-formula.function-rounddown-fills
 *   field.default-formula.function-mod-fills
 *   field.default-formula.function-text-fills
 *   field.default-formula.function-if-fills
 *   field.default-formula.function-and-fills
 *   field.default-formula.function-or-fills
 *     One column per function: does the formula read back as sent, and
 *     does a bare item create come back with the column filled? AND and OR
 *     are wrapped in IF so the result is a number, and depend on IF's row.
 *   field.default-formula.text-property-reads-back
 *   field.default-formula.text-fills-on-item-create
 *     A single-line Text column carrying ="Y"&YEAR(TODAY()): the property
 *     round trip and the fill, with measured functions only, so the row is
 *     about the column type.
 *   field.default-formula.datetime-fills-on-item-create
 *     A DateTime column (DisplayFormat 1) carrying =TODAY(): the property
 *     round trip and the fill. The stored value is the site zone's midnight
 *     read back as UTC, so it is compared to the browser clock within two
 *     days rather than to the browser's date.
 *   field.default-formula.shipped-financial-year-fills
 *   field.default-formula.shipped-financial-quarter-fills
 *     The two formulas the family README prints for a July to June
 *     financial year, on a Number and on a Choice column.
 *
 * NOT MEASURED HERE
 *   Whether the same formulas fill in Quick edit or on a form. Those are
 *   rendered surfaces and need a capture, not a machine row.
 *
 * MICROSOFT LEARN CITATIONS
 *   DefaultFormula on a field:
 *     "DefaultFormula element (List)", "Field.DefaultFormula Property" (CSOM)
 *   List creation via POST to `web/lists` and item creation via `items`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
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

  log('INFO', 'probe revision a7bf7dea. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Functions List';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4'];
  const MONTHS = ['01', '02', '03', '04', '05', '06', '07', '08', '09', '10', '11', '12'];

  // What the browser's clock says each formula should produce. Reported
  // beside the observed value and NEVER asserted: the formula evaluates on
  // the server in the site's regional zone, and a paste near midnight or a
  // quarter boundary can legitimately disagree with this machine.
  const now = new Date();
  const month = now.getMonth() + 1;
  const year = now.getFullYear();
  const expectFinancialYear = year + (month >= 7 ? 1 : 0);
  const expectFinancialQuarter = `Q${((Math.ceil(month / 3) + 1) % 4) + 1}`;
  // A DateTime reads back as UTC ISO text and TODAY() is the site zone's
  // midnight, so the stored day can sit either side of the browser's; two
  // days of tolerance keeps the head about the fill rather than the zone.
  const TWO_DAYS_MS = 2 * 24 * 60 * 60 * 1000;
  const withinTwoDays = (v) => Math.abs(new Date(v).getTime() - now.getTime()) <= TWO_DAYS_MS;

  // Internal names equal display names. Each row is one column, created
  // through the same POST to /fields the deploy uses.
  const ROWS = [
    { id: 'field.default-formula.function-day-fills', col: 'FnDay', type: 'number',
      formula: '=DAY(TODAY())', expect: now.getDate(),
      question: 'Does =DAY(TODAY()) on a Number column read back as sent and fill a bare item create' },
    { id: 'field.default-formula.function-rounddown-fills', col: 'FnRoundDown', type: 'number',
      formula: '=ROUNDDOWN(MONTH(TODAY())/3,0)', expect: Math.floor(month / 3),
      question: 'Does =ROUNDDOWN(MONTH(TODAY())/3,0) on a Number column read back as sent and fill a bare item create' },
    { id: 'field.default-formula.function-mod-fills', col: 'FnMod', type: 'number',
      formula: '=MOD(MONTH(TODAY()),3)', expect: month % 3,
      question: 'Does =MOD(MONTH(TODAY()),3) on a Number column read back as sent and fill a bare item create' },
    { id: 'field.default-formula.function-text-fills', col: 'FnText', type: 'choice', choices: MONTHS,
      formula: '=TEXT(MONTH(TODAY()),"00")', expect: MONTHS[month - 1],
      question: 'Does =TEXT(MONTH(TODAY()),"00") on a Choice column read back as sent and fill a bare item create' },
    { id: 'field.default-formula.function-if-fills', col: 'FnIf', type: 'number',
      formula: '=IF(MONTH(TODAY())>=7,1,0)', expect: month >= 7 ? 1 : 0,
      question: 'Does =IF(MONTH(TODAY())>=7,1,0) on a Number column read back as sent and fill a bare item create' },
    { id: 'field.default-formula.function-and-fills', col: 'FnAnd', type: 'number',
      formula: '=IF(AND(MONTH(TODAY())>=1,MONTH(TODAY())<=12),1,0)', expect: 1,
      question: 'Does an IF over AND(...) on a Number column read back as sent and fill a bare item create with 1' },
    { id: 'field.default-formula.function-or-fills', col: 'FnOr', type: 'number',
      formula: '=IF(OR(MONTH(TODAY())<1,MONTH(TODAY())>=1),1,0)', expect: 1,
      question: 'Does an IF over OR(...) on a Number column read back as sent and fill a bare item create with 1' },
    { id: 'field.default-formula.shipped-financial-year-fills', col: 'ShippedFinYear', type: 'number',
      formula: '=YEAR(TODAY())+IF(MONTH(TODAY())>=7,1,0)', expect: expectFinancialYear,
      question: 'Does the README financial-year formula on a Number column read back as sent and fill a bare item create' },
    { id: 'field.default-formula.shipped-financial-quarter-fills', col: 'ShippedFinQuarter', type: 'choice', choices: QUARTERS,
      formula: '="Q"&(MOD(ROUNDUP(MONTH(TODAY())/3,0)+1,4)+1)', expect: expectFinancialQuarter,
      question: 'Does the README financial-quarter formula on a Choice column read back as sent and fill a bare item create' },
    { id: 'field.default-formula.datetime-fills-on-item-create', col: 'FnDateTime', type: 'datetime',
      formula: '=TODAY()', expect: now.toISOString().slice(0, 10), same: withinTwoDays,
      question: 'Does =TODAY() on a DateTime column (DisplayFormat 1) read back as sent and fill a bare item create within two days of the browser clock' },
  ];
  const TEXT_COL = 'FnTextColumn';
  const TEXT_FORMULA = '="Y"&YEAR(TODAY())';
  const expectText = `Y${year}`;

  const Q = {
    fixture: 'A generic list is created (BaseTemplate 100)',
    control: 'NEGATIVE CONTROL: an item POST naming a column that does not exist is refused',
    columns: 'Every probe column reads back as its declared type, and a reused one carries the formula this probe sends',
    textProp: 'Does DefaultFormula on a single-line Text column read back as sent',
    textFill: 'Does ="Y"&YEAR(TODAY()) on a single-line Text column fill on a bare item create',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' on ${WEB} with ${ROWS.length + 1} columns, each carrying a DefaultFormula,`);
    log('INFO', 'then create one bare item and read every column back.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing list would be reused.');
      log('INFO', 'Set CLEANUP = true for a clean run.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('field.default-formula.fixture-list-created', Q.fixture);
  expect('field.default-formula.control-missing-column-refused', Q.control);
  expect('field.default-formula.fixture-columns-typed', Q.columns);
  expect('field.default-formula.function-day-fills', ROWS[0].question);
  expect('field.default-formula.function-rounddown-fills', ROWS[1].question);
  expect('field.default-formula.function-mod-fills', ROWS[2].question);
  expect('field.default-formula.function-text-fills', ROWS[3].question);
  expect('field.default-formula.function-if-fills', ROWS[4].question);
  expect('field.default-formula.function-and-fills', ROWS[5].question);
  expect('field.default-formula.function-or-fills', ROWS[6].question);
  expect('field.default-formula.text-property-reads-back', Q.textProp);
  expect('field.default-formula.text-fills-on-item-create', Q.textFill);
  expect('field.default-formula.datetime-fills-on-item-create', ROWS[9].question);
  expect('field.default-formula.shipped-financial-year-fills', ROWS[7].question);
  expect('field.default-formula.shipped-financial-quarter-fills', ROWS[8].question);
  const DEPENDANTS = RESULTS.map((r) => r.id).slice(1);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // __metadata is a VERBOSE OData construct, so every write carrying it
  // overrides the harness's default nometadata content type.
  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;
  const show = (v) => JSON.stringify(v === undefined ? null : v);

  // Reads a field WITHOUT $select, so an absent property reads as undefined
  // rather than failing the whole read.
  const readField = async (name) => spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')`);

  const bodyFor = (row) => {
    if (row.type === 'choice') {
      return { __metadata: { type: 'SP.FieldChoice' }, Title: row.col, FieldTypeKind: 6,
               Choices: { results: row.choices }, FillInChoice: false, DefaultFormula: row.formula };
    }
    if (row.type === 'text') {
      return { __metadata: { type: 'SP.FieldText' }, Title: row.col, FieldTypeKind: 2, DefaultFormula: row.formula };
    }
    if (row.type === 'datetime') {
      return { __metadata: { type: 'SP.FieldDateTime' }, Title: row.col, FieldTypeKind: 4,
               DisplayFormat: 1, DefaultFormula: row.formula };
    }
    return { __metadata: { type: 'SP.FieldNumber' }, Title: row.col, FieldTypeKind: 9, DefaultFormula: row.formula };
  };
  const ensureField = async (row) => {
    const have = await readField(row.col);
    if (have.ok) return { ok: true, status: have.status, text: 'already present', reused: true };
    const digest = await getDigest();
    return spPost(`${listPath}/fields`, bodyFor(row), digest, VERBOSE);
  };

  const fillOutcome = (value, expected, same) => {
    if (value === null || value === undefined || value === '') return 'BLANK';
    const matches = same ? same(value) : String(value) === String(expected);
    return matches ? 'FILLED, MATCHES BROWSER CLOCK' : 'FILLED, DIFFERS FROM BROWSER CLOCK';
  };

  await resetList(LIST);

  let digest = await getDigest();
  const haveList = await spGet(listPath);
  const madeList = haveList.ok ? null : await spPost('web/lists', {
    Title: LIST, BaseTemplate: 100,
    Description: 'dbml-sharepoint default-formula functions probe list. Safe to delete.',
  }, digest);
  if (madeList !== null && !madeList.ok) {
    record('field.default-formula.fixture-list-created', Q.fixture, 'FAIL', short(madeList));
    voidAll(DEPENDANTS, `fixture incomplete: list creation failed (HTTP ${madeList.status})`);
    return report();
  }
  log('INFO', madeList === null
    ? `reusing an existing list '${LIST}'. Set CLEANUP = true for a clean answer.`
    : `created '${LIST}'`);
  // Read back on reuse as well as on create, because a list found by title may be a library.
  if (!await establishFixture('field.default-formula.fixture-list-created',
    () => spGet(`${listPath}?$select=BaseTemplate`), { BaseTemplate: 100 }, DEPENDANTS)) {
    return report();
  }

  // ---- NEGATIVE CONTROL: an item POST naming a missing column -----------
  digest = await getDigest();
  const junk = await spPost(`${listPath}/items`,
    { Title: 'dbmlsp functions control', dbmlspNoSuchColumn: 1 }, digest);
  const controlHeld = !junk.ok && isRefusal(junk.status);
  record('field.default-formula.control-missing-column-refused', Q.control,
         controlHeld ? 'PASS' : (junk.ok ? 'FAIL' : 'NOT ESTABLISHED'),
         controlHeld ? `refused with ${short(junk)}`
           : (junk.ok ? 'the item POST naming a missing column was ACCEPTED, so a blank '
                        + 'below cannot be told from a column the server ignored'
                      : `the item POST failed with non-refusal ${short(junk)}`));
  if (!controlHeld) {
    voidAll(DEPENDANTS.slice(1),
            `negative control did not hold (HTTP ${junk.status}), so a blank below could `
            + 'not be told from any other server answer');
    return report();
  }

  // ---- Every column, then one bare item ---------------------------------
  const textRow = { col: TEXT_COL, type: 'text', formula: TEXT_FORMULA };
  const made = {};
  for (const row of [...ROWS, textRow]) {
    const create = await ensureField(row);
    const back = await readField(row.col);
    made[row.col] = {
      create,
      back,
      stored: !readFailed(back) && back.body.DefaultFormula === row.formula,
    };
  }
  // A reused column's formula was not sent by this run, so there it is a precondition, not the observation.
  const TYPES = { number: 'Number', choice: 'Choice', text: 'Text', datetime: 'DateTime' };
  const declared = {};
  for (const row of [...ROWS, textRow]) {
    const m = made[row.col];
    if (!m.create.ok) continue;
    declared[`${row.col}.TypeAsString`] = TYPES[row.type];
    if (row.type === 'datetime') declared[`${row.col}.DisplayFormat`] = 1;
    if (m.create.reused) declared[`${row.col}.DefaultFormula`] = row.formula;
  }
  if (!await establishFixture('field.default-formula.fixture-columns-typed', async () => {
    const body = {};
    for (const key of Object.keys(declared)) {
      const [col, name] = key.split('.');
      if (unanswered(made[col].back) !== null) return made[col].back;
      body[key] = made[col].back.body[name];
    }
    return { ok: true, status: 200, body };
  }, declared, DEPENDANTS.slice(2))) {
    return report();
  }
  const textMade = made[TEXT_COL];
  if (readFailed(textMade.back)) {
    record('field.default-formula.text-property-reads-back', Q.textProp, 'NOT ESTABLISHED',
           `create answered ${short(textMade.create)}; the field did not read back (HTTP ${textMade.back.status})`, 'void');
  } else {
    const stored = textMade.back.body.DefaultFormula;
    record('field.default-formula.text-property-reads-back', Q.textProp,
           textMade.stored ? 'READS BACK AS SENT' : (stored == null || stored === '' ? 'PROPERTY DROPPED' : 'READS BACK DIFFERENT'),
           `create answered ${short(textMade.create)}; TypeAsString=${textMade.back.body.TypeAsString}; `
           + `DefaultFormula reads back ${show(stored)} (sent ${show(TEXT_FORMULA)})`);
  }

  digest = await getDigest();
  const item = await spPost(`${listPath}/items`, { Title: 'dbmlsp functions row' }, digest);
  const fillIds = [...ROWS.map((row) => row.id), 'field.default-formula.text-fills-on-item-create'];
  if (!item.ok || !item.body) {
    voidAll(fillIds, `the bare item create failed (${short(item)})`);
    return report();
  }
  const cols = [...ROWS.map((row) => row.col), TEXT_COL].join(',');
  const back = await spGet(`${listPath}/items(${item.body.Id})?$select=Id,${cols}`);
  if (readFailed(back)) {
    voidAll(fillIds, `the created item did not read back (HTTP ${back.status})`);
    return report();
  }
  const how = `POST items with Title only answered HTTP ${item.status}`;
  const ifRow = ROWS.find((row) => row.col === 'FnIf');
  const ifFilled = made[ifRow.col].stored && fillOutcome(back.body[ifRow.col], ifRow.expect) !== 'BLANK';
  for (const row of ROWS) {
    const m = made[row.col];
    const value = back.body[row.col];
    if (!m.stored) {
      const stored = readFailed(m.back) ? `(read failed HTTP ${m.back.status})` : show(m.back.body.DefaultFormula);
      record(row.id, row.question,
             m.create.ok ? 'PROPERTY DROPPED' : (isRefusal(m.create.status) ? 'CREATE REFUSED' : 'NOT ESTABLISHED'),
             `create answered ${short(m.create)}; DefaultFormula reads back ${stored} (sent ${show(row.formula)}), `
             + 'so the fill is unmeasured');
      continue;
    }
    if ((row.col === 'FnAnd' || row.col === 'FnOr') && !ifFilled) {
      record(row.id, row.question, 'NOT ESTABLISHED',
             'the IF wrapper did not fill on its own row, so a blank here says nothing about the inner function', 'void');
      continue;
    }
    record(row.id, row.question, fillOutcome(value, row.expect, row.same),
           `${how}; ${row.col} (formula ${row.formula}) reads back ${show(value)} `
           + `(browser clock expects ${show(row.expect)})`);
  }
  record('field.default-formula.text-fills-on-item-create', Q.textFill,
         textMade.stored ? fillOutcome(back.body[TEXT_COL], expectText) : 'NOT ESTABLISHED',
         textMade.stored
           ? `${how}; ${TEXT_COL} reads back ${show(back.body[TEXT_COL])} (browser clock expects ${show(expectText)})`
           : 'the formula was not stored on the Text column, so its fill is unmeasured');

  return report();
})();
