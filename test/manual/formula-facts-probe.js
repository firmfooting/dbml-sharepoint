/** ---- dbml-sharepoint PROBE: THE FORMULA FACTS A FORM HEADER DEPENDS ON ----
 *
 * REVISION: f450e8ed
 *
 * QUESTION: what does the server do with the corners of a calculated column's
 * formula that a header evaluator written outside the server would have to
 * reproduce: DATE with a month or day out of range, a blank operand beside each
 * operator, text equality, the day [Created]+n lands on, how a calculated date
 * and a calculated number read and display, and how large a form formatter can
 * be before the content type refuses it?
 *
 * WHY: Learn documents the formula functions and the formatting language, not
 * these corners. An evaluator that guesses them saves, reads back and renders,
 * and shows a value that differs from the column on some row. The probe measures
 * each corner; the maintainer pastes the printed FACTS object into a facts file
 * the evaluator's tests pin, and the probe's own tests check plumbing only.
 *
 * THREE PASTES, one MODE each:
 *   MODE = 'build'  creates the scratch list, the operand columns, one item and a
 *       calculated column per case, then a column formatter on the two calculated
 *       date columns. A case the server refuses is recorded with its message.
 *   MODE = 'read'   reads the item's calculated values and prints FACTS. Run it
 *       after build; run build in a window where the site-local day differs
 *       from the UTC day for the [Created]+n corner to discriminate (the row
 *       names the window when it did not).
 *   MODE = 'size'   doubles then bisects the size of the content type's
 *       ClientFormCustomFormatter, then leaves the largest saved one in place.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   formula.calc.fixture-facts-list              the list, with this probe's Description
 *   formula.calc.fixture-facts-columns           the operand columns, by TypeAsString
 *   formula.calc.fixture-facts-item              the one item: operands filled, every Blank column empty
 *   formula.datetime.fixture-facts-column-formatter  the formatter on both calculated date columns
 *   formula.datetime.fixture-facts-site-zone     the site's time zone offsets
 *   formula.calc.fixture-facts-content-type      the default item content type (size)
 *
 * OBSERVES (never asserted; each is a fact key in the printed FACTS object)
 *   date_overflow, blank_coercion, text_equality_case, created_plus_days_day,
 *   calculated_date_read, calculated_number_display, header_size_limit
 *   A person records how the calculated date shows through the column formatter
 *   and the Display form, and whether the largest saved formatter renders.
 *
 * HOW TO READ IT: a fact whose fixture failed prints VOID, never a result. A fact
 * measured by another MODE prints NOT MEASURED IN THIS MODE. Copy the FACTS line
 * back with the results block.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again. Set
 * CLEANUP to true on a later build run to recycle the previous list first; a
 * same-title list without this probe's Description is never touched.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // CLEANUP recycles only this probe's own list, by Id, before the run; it needs CONFIRMED and ALLOW_WRITES too.
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
  const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

  const getDigest = async () => {
    const res = await fetch(`${WEB}/_api/contextinfo`, {
      method: 'POST', headers: { Accept: 'application/json;odata=verbose' },
    });
    if (!res.ok) throw new Error(`contextinfo failed: HTTP ${res.status}`);
    const body = await res.json();
    return body.d.GetContextWebInformation.FormDigestValue;
  };

  const spGet = async (path) => {
    // A rejected fetch is an unanswered read (status 0), so no direct read ends the run without its table.
    try {
      const res = await fetch(`${WEB}/_api/${path}`, {
        headers: { Accept: 'application/json;odata=nometadata' },
      });
      return { ok: res.ok, status: res.status, body: await res.json().catch(() => null) };
    } catch (err) {
      return { ok: false, status: 0, body: null, text: `the read threw: ${err && err.message ? err.message : String(err)}` };
    }
  };

  // `body` is the parsed payload even when the call failed, so only `ok` says a call worked.

  // Non-2xx other than 401/403/408/429/502/503/504 is the server rejecting the content, which answers 500 rather than 400.
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 502 && status !== 503 && status !== 504; // 503: the other documented throttle; 502 and 504 are gateway answers

  // extraHeaders carries X-HTTP-Method for MERGE/DELETE: SharePoint tunnels
  // both through POST rather than accepting them as real verbs.
  const spPost = async (path, payload, digest, extraHeaders = {}) => {
    let res;
    try {
      res = await fetch(`${WEB}/_api/${path}`, {
        method: 'POST',
        headers: {
          Accept: 'application/json;odata=nometadata',
          'Content-Type': 'application/json;odata=nometadata',
          'X-RequestDigest': digest,
          ...extraHeaders,
        },
        body: JSON.stringify(payload),
      });
    } catch (err) {
      // A rejected write may still have reached the site, so it is named and a readback decides.
      return { ok: false, status: 0, body: null, text: `the write request threw: ${err && err.message ? err.message : String(err)}` };
    }
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
  // REST, and the CSOM/REST API index).
  // NOT DOCUMENTED: `/recycle` on the by-Id form appears on no Learn page.
  // It is the call this project has live evidence for with only the
  // addressing changed, and an unsupported URL fails visibly here rather
  // than losing somebody's list.
  const resetList = async (title, expectedId = null) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
      return false;
    }
    // An Id that is not a GUID would be spliced into a URL that addresses
    // something else, so it fails closed instead of being sent.
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
  // void, needs-human. Outcome heads are
  // free prose and a bad enum, so a reader
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

  // ---- Fixtures -----------------------------------------------
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
    if (bare500(r)) return 'answered HTTP 500 with no SharePoint error payload';
    return isRefusal(r.status) ? `was refused (HTTP ${r.status})` : `did not answer (HTTP ${r.status})`;
  };

  // Only a refusal is a finding: throttling, authorisation, timeouts, gateways, an empty body and a 500 with no SharePoint error payload answer nothing.
  const hasErrorPayload = (r) => !!(r.body && (r.body.error || r.body['odata.error']));
  const bare500 = (r) => r.status === 500 && !hasErrorPayload(r);
  const silentOf = (r) => (r.ok || !isRefusal(r.status) || bare500(r) ? unanswered(r) : null);

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
    let quiet = null; // a read that said nothing about the fixture: a re-run can clear it
    try {
      got = await read();
    } catch (err) {
      quiet = `the read threw: ${err && err.message ? err.message : String(err)}`;
    }
    if (!quiet) {
      if (!got || typeof got !== 'object') quiet = 'the read returned no response';
      else if (silentOf(got)) quiet = `the read ${silentOf(got)}`;
      else if (unanswered(got)) problems.push(`the read ${unanswered(got)}`);
    }
    if (quiet) {
      record(id, question, 'NOT ESTABLISHED', quiet, 'open');
      return false;
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
  log('INFO', 'probe revision f450e8ed. Quote this when reporting results.');

  // ---- The question ----------------------------------------------------
  const MODE = 'build'; // 'build', then 'read', then 'size'
  // A mistyped MODE would index every phase table with undefined, so it fails closed here by name.
  if (!['build', 'read', 'size'].includes(MODE)) {
    console.error(`[FATAL] MODE is '${MODE}'; it must be 'build', 'read' or 'size'. Nothing was sent.`);
    return;
  }
  const BUILD = MODE === 'build';
  const LIST = 'FormulaFacts';
  // Ownership is the Description, never the title: a same-title list this probe did not make is left alone.
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint formula-facts probe scratch list. Safe to delete.';
  const NUM = 'NumA';
  const TXT = 'TextA';
  const DAT = 'DateA';
  const CHO = 'ChoiceA';
  const LEAP = 'DateLeap';
  const BLANKS = { number: 'BlankNum', text: 'BlankText', date: 'BlankDate', choice: 'BlankChoice' };
  const ITEM_VALUES = { [NUM]: 5, [TXT]: 'abc', [DAT]: '2026-03-15T00:00:00Z', [CHO]: 'Low', [LEAP]: '2024-02-29T00:00:00Z' };
  const OPERANDS = [['number', NUM], ['text', TXT], ['date', DAT], ['choice', CHO]];
  const OPS = [['add', '+'], ['sub', '-'], ['mul', '*'], ['div', '/'], ['pow', '^'], ['cat', '&'],
    ['eq', '='], ['ne', '<>'], ['lt', '<'], ['gt', '>'], ['le', '<='], ['ge', '>=']];
  const COMPARES = ['eq', 'ne', 'lt', 'gt', 'le', 'ge'];
  // A comparison is wrapped so its result is text either way; the operator itself is what is measured.
  const exprOf = ([code, sign], left, right) => (COMPARES.includes(code)
    ? `=IF([${left}]${sign}[${right}],"T","F")` : `=[${left}]${sign}[${right}]`);
  // OutputType values are the SP.FieldType numbers of the calculated column's result.
  const TEXT = 2;
  const DATETIME = 4;
  const NUMBER = 9;
  const CASES = [];
  const addCase = (name, formula, outputType, dateFormat) => CASES.push({ name, formula, outputType, dateFormat });
  for (const op of OPS) {
    for (const [type, column] of OPERANDS) {
      addCase(`B_${op[0]}_${type}_l`, exprOf(op, BLANKS[type], column), TEXT);
      addCase(`B_${op[0]}_${type}_r`, exprOf(op, column, BLANKS[type]), TEXT);
      addCase(`B_${op[0]}_${type}_b`, exprOf(op, BLANKS[type], BLANKS[type]), TEXT);
    }
  }
  const BLANK_CASES = CASES.length;
  const OVERFLOW_CASES = [['Dov1', 'DATE(2026,13,5)'], ['Dov2', 'DATE(2026,1,0)'], ['Dov3', 'DATE(2026,2,31)'],
    ['Dov4', 'DATE(2024,2,29)'], ['Dov5', `DATE(YEAR([${LEAP}])+1,MONTH([${LEAP}]),DAY([${LEAP}]))`]];
  for (const [name, call] of OVERFLOW_CASES) addCase(name, `=${call}`, DATETIME, 0);
  addCase('Teq1', '=IF("a"="A","T","F")', TEXT);
  addCase('Teq2', `=IF([${TXT}]="ABC","T","F")`, TEXT);
  addCase('CpdZero', '=[Created]+0', DATETIME, 0);
  addCase('CpdOne', '=[Created]+1', DATETIME, 0);
  addCase('Cdr', '=DATE(2026,3,15)', DATETIME, 0);
  addCase('CdrTime', '=[Created]+0', DATETIME, 1);
  addCase('Ndisp', `=[${NUM}]/3`, NUMBER);
  addCase('NdispWhole', `=[${NUM}]*2`, NUMBER);
  // Learn's formatting syntax reference lists displayValue, toLocaleString and toLocaleDateString.
  const DATE_FORMATTER = JSON.stringify({ elmType: 'div', children: [
    { elmType: 'div', txtContent: '@currentField' },
    { elmType: 'div', txtContent: '=toLocaleString(@currentField)' },
    { elmType: 'div', txtContent: '=toLocaleDateString(@currentField)' },
    { elmType: 'div', txtContent: '@currentField.displayValue' }] });
  const DATE_COLUMNS = ['Cdr', 'CdrTime'];
  const CAP = 1048576;
  // 40 per list keeps each list under the row-size limit.
  const PER_LIST = 40;
  // The cases that share the item's date and number reads stay in the first list; the blank cases fill the rest.
  const ORDER = [...CASES.slice(BLANK_CASES), ...CASES.slice(0, BLANK_CASES)];
  const LISTS = Array.from({ length: Math.ceil(ORDER.length / PER_LIST) }, (_, n) => ({
    n, title: n ? `${LIST}${n + 1}` : LIST, cases: ORDER.slice(n * PER_LIST, (n + 1) * PER_LIST) }));

  const LIST_F = 'formula.calc.fixture-facts-list';
  const COLS = 'formula.calc.fixture-facts-columns';
  const ITEM = 'formula.calc.fixture-facts-item';
  const FMT = 'formula.datetime.fixture-facts-column-formatter';
  const ZONE = 'formula.datetime.fixture-facts-site-zone';
  const TYPE = 'formula.calc.fixture-facts-content-type';
  const CASE_ROW = 'formula.calc.case-columns-accepted';
  const F_OVERFLOW = 'formula.calc.fact-date-overflow';
  const F_BLANK = 'formula.calc.fact-blank-coercion';
  const F_TEXT = 'formula.calc.fact-text-equality-case';
  const F_CREATED = 'formula.datetime.fact-created-plus-days-day';
  const F_DATE_READ = 'formula.datetime.fact-calculated-date-read';
  const F_NUMBER = 'formula.calc.fact-calculated-number-display';
  const F_SIZE = 'formula.calc.fact-header-size-limit';
  const M_FORMATTER = 'formula.datetime.calculated-date-formatter-reads';
  const M_BODY = 'formula.datetime.calculated-date-form-body-reads';
  const M_SIZE = 'formula.calc.header-size-renders';
  for (const L of LISTS) {
    L.ids = L.n ? { list: `${LIST_F}-${L.n + 1}`, cols: `${COLS}-${L.n + 1}`, item: `${ITEM}-${L.n + 1}` }
      : { list: LIST_F, cols: COLS, item: ITEM };
  }
  const EXTRA = LISTS.slice(1).flatMap((L) => [L.ids.list, L.ids.cols, L.ids.item]);
  // Fact keys are what the maintainer's facts file is keyed by; each fact lives in the MODE shown.
  const FACT_OF = { date_overflow: [F_OVERFLOW, 'read'], blank_coercion: [F_BLANK, 'read'],
    text_equality_case: [F_TEXT, 'read'], created_plus_days_day: [F_CREATED, 'read'],
    calculated_date_read: [F_DATE_READ, 'read'], calculated_number_display: [F_NUMBER, 'read'],
    header_size_limit: [F_SIZE, 'size'] };
  const NOT_MEASURED = 'NOT MEASURED IN THIS MODE';
  const FACTS = Object.fromEntries(Object.keys(FACT_OF).map((k) => [k, NOT_MEASURED]));
  // Explicit dependencies, as the catalogue declares them: a failure voids only the rows that rest on it.
  const REST_ON = {
    [COLS]: [LIST_F], [ITEM]: [COLS], [FMT]: [LIST_F], [ZONE]: [LIST_F], [TYPE]: [LIST_F],
    [F_OVERFLOW]: [ITEM], [F_BLANK]: [ITEM], [F_TEXT]: [ITEM], [F_CREATED]: [ITEM, ZONE],
    [F_DATE_READ]: [ITEM], [F_NUMBER]: [ITEM], [F_SIZE]: [TYPE],
    [M_FORMATTER]: [ITEM, FMT], [M_BODY]: [ITEM], [M_SIZE]: [TYPE, F_SIZE],
  };
  for (const L of LISTS.slice(1)) {
    REST_ON[L.ids.cols] = [L.ids.list];
    REST_ON[L.ids.item] = [L.ids.cols];
    REST_ON[F_BLANK].push(L.ids.item);
  }
  const NODES = { build: [LIST_F, COLS, ITEM, ...EXTRA, CASE_ROW, FMT],
    read: [LIST_F, COLS, ITEM, ...EXTRA, ZONE, FMT, F_OVERFLOW, F_BLANK, F_TEXT, F_CREATED, F_DATE_READ, F_NUMBER, M_FORMATTER, M_BODY],
    size: [LIST_F, TYPE, F_SIZE, M_SIZE] }[MODE];
  const rests = (id, on) => (REST_ON[id] || []).some((d) => d === on || rests(d, on));
  const dependents = (on) => NODES.filter((id) => id !== on && rests(id, on));

  expect('formula.calc.fixture-facts-list', 'the list reads back with its marker, an item type and its folder URL');
  if (MODE !== 'size') {
    expect('formula.calc.fixture-facts-columns', 'the operand columns read back with their types');
    expect('formula.calc.fixture-facts-item', 'the item reads back with the operands filled and every Blank column empty');
    expect('formula.datetime.fixture-facts-column-formatter', 'both calculated date columns read back the column formatter as written');
  }
  if (MODE !== 'size') {
    for (const L of LISTS.slice(1)) {
      expect(L.ids.list, `the list ${L.title} reads back with its marker, an item type and its folder URL`);
      expect(L.ids.cols, `the operand columns of ${L.title} read back with their types`);
      expect(L.ids.item, `the item of ${L.title} reads back with the operands filled and every Blank column empty`);
    }
  }
  if (BUILD) {
    expect('formula.calc.case-columns-accepted', 'every case column was created, or the server refused it with a message');
  } else if (MODE === 'read') {
    expect('formula.datetime.fixture-facts-site-zone', 'the site time zone reads back its bias values');
    expect('formula.calc.fact-date-overflow', 'what DATE gives for a month or day out of range, and a leap day plus one year');
    expect('formula.calc.fact-blank-coercion', 'what each operator gives for a blank beside each operand type');
    expect('formula.calc.fact-text-equality-case', 'whether text equality ignores case');
    expect('formula.datetime.fact-created-plus-days-day', 'whether [Created]+n takes its day in site-local time');
    expect('formula.datetime.fact-calculated-date-read', 'how a calculated date reads over REST and as text');
    expect('formula.calc.fact-calculated-number-display', 'how a calculated number with no decimals setting reads and displays');
    expect('formula.datetime.calculated-date-formatter-reads', 'what the column formatter shows for a calculated date');
    expect('formula.datetime.calculated-date-form-body-reads', 'what the Display form body shows for a calculated date');
  } else {
    expect('formula.calc.fixture-facts-content-type', 'the default item content type was found');
    expect('formula.calc.fact-header-size-limit', 'the largest form formatter the content type saves, found by doubling then bisecting');
    expect('formula.calc.header-size-renders', 'whether the largest saved formatter renders on the form');
  }

  // FACTS always carries every key; a fact that rests on a fixture that did not hold, or was not reached, is VOID.
  const finish = (ran) => {
    if (ran) {
      for (const [key, [id, mode]] of Object.entries(FACT_OF)) {
        const row = RESULTS.find((r) => r.id === id);
        if (mode === MODE && (FACTS[key] === NOT_MEASURED || (row && row.state === 'void'))) FACTS[key] = 'VOID';
      }
    }
    console.log(`FACTS ${JSON.stringify(FACTS)}`);
    return report();
  };

  if (!CONFIRMED || !ALLOW_WRITES) {
    log('INFO', {
      build: `Would create ${LISTS.length} lists from '${LIST}', each with operand columns and one item, and ${CASES.length} calculated case columns in all on ${WEB}.`,
      read: `Would read the item's calculated values on '${LIST}' on ${WEB} and print FACTS. Nothing is written.`,
      size: `Would write form formatters of growing size to the default content type of '${LIST}' on ${WEB}.`,
    }[MODE]);
    log('INFO', 'Nothing has been sent. Set CONFIRMED = true and ALLOW_WRITES = true to run it.');
    return finish(false);
  }

  const enc = (t) => encodeURIComponent(t.replace(/'/g, "''"));
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const post = async (path, payload, extra = {}) => {
    let digest;
    try { digest = await getDigest(); } catch (err) {
      return { ok: false, status: 0, body: null, text: `the write request threw: ${err && err.message ? err.message : String(err)}` };
    }
    return spPost(path, payload, digest, { ...VERBOSE, ...extra });
  };
  const reason = (r) => (r.body && r.body.error && r.body.error.message && r.body.error.message.value) || r.text.slice(0, 160);
  const said = (what, r) => log(r.ok ? 'INFO' : 'FAIL', `${what}: HTTP ${r.status}${r.ok ? '' : ` ${reason(r)}`}`);
  const CAPACITY = /too many (calculated )?(columns|fields)|row size|8,?000 bytes/i;
  const MERGE = { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' };

  // standList finds or makes one scratch list and reads it back; false once a row says why it could not.
  const standList = async (L) => {
    const refuse = (why) => {
      record(L.ids.list, 'the list reads back with its marker, an item type and its folder URL', 'FAIL', why);
      voidDependents(dependents(L.ids.list), 'the list was not established by this run');
      return false;
    };
    const listAt = `web/lists/getbytitle('${enc(L.title)}')`;
    let listId = '';
    if (BUILD) {
      // A by-title read answers an absent list 404; a standing one is recycled only if it carries the marker.
      const before = await spGet(`${listAt}?$select=Id,Description`);
      if (before.status !== 404) {
        if (!before.ok) return refuse(`could not tell whether '${L.title}' already stands: the read ${unanswered(before)}`);
        if (!before.body || before.body.Description !== OWNERSHIP_DESCRIPTION) {
          return refuse(`a list named '${L.title}' exists without this probe's ownership description; refusing to modify it`);
        }
        if (!CLEANUP) return refuse(`'${L.title}' from an earlier run already stands; set CLEANUP to true to recycle it first`);
        // By the Id read with the marker, so a title rebound since cannot redirect the deletes.
        let recycled = false;
        try { recycled = await resetList(L.title, String(before.body.Id).replace(/[{}]/g, '')); } catch { /* named below */ }
        if (!recycled) return refuse(`'${L.title}' from an earlier run could not be recycled`);
        const after = await spGet(`${listAt}?$select=Id`);
        if (after.status !== 404) return refuse(`'${L.title}' still answers HTTP ${after.status} after the recycle`);
      }
      const created = await post('web/lists', { __metadata: { type: 'SP.List' }, Title: L.title,
        BaseTemplate: 100, Description: OWNERSHIP_DESCRIPTION });
      said('list create', created);
      // Only a list this run's create answered for is written to, and only by its Id: the title may be another's now.
      listId = created.ok && created.body && created.body.d ? String(created.body.d.Id).replace(/[{}]/g, '') : '';
      if (!GUID.test(listId)) {
        return refuse(`the list create answered HTTP ${created.status} with no list Id; nothing more was written`);
      }
    } else {
      // Later runs write only to the list the build run made, found by title and proved by its marker.
      const standing = await spGet(`${listAt}?$select=Id,Description`);
      if (!standing.ok) return refuse(`the build list was not read: the read ${unanswered(standing)}`);
      if (!standing.body || standing.body.Description !== OWNERSHIP_DESCRIPTION) {
        return refuse(`'${L.title}' does not carry this probe's ownership description; run MODE = 'build' first`);
      }
      listId = String(standing.body.Id).replace(/[{}]/g, '');
      if (!GUID.test(listId)) return refuse('the list read answered no list Id');
    }
    L.at = `web/lists(guid'${listId}')`;
    return establishFixture(L.ids.list, async () => (L.list = await spGet(
      `${L.at}?$select=Description,ListItemEntityTypeFullName,RootFolder/ServerRelativeUrl&$expand=RootFolder`)),
    { Description: OWNERSHIP_DESCRIPTION, ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0,
      RootFolder: (v) => !!v && typeof v.ServerRelativeUrl === 'string' && v.ServerRelativeUrl.startsWith('/') },
    dependents(L.ids.list));
  };
  const M = LISTS[0];
  if (!await standList(M)) return finish(true);
  const at = M.at;
  const list = M.list;

  if (MODE === 'size') {
    // The default item content type, as the deploy finds it: an Item-derived type that is not a folder.
    const types = await spGet(`${at}/contenttypes?$select=Name,StringId&$top=100`);
    const itemType = !unanswered(types) && Array.isArray(types.body.value)
      ? types.body.value.find((t) => t && typeof t.StringId === 'string'
        && t.StringId.startsWith('0x01') && !t.StringId.startsWith('0x0120')) : null;
    if (!itemType) {
      const why = unanswered(types) ? `the content type read ${unanswered(types)}` : 'no default item content type answered';
      const quiet = silentOf(types) !== null;
      record(TYPE, 'the default item content type was found', quiet ? 'NOT ESTABLISHED' : 'FAIL', why, quiet ? 'open' : undefined);
      voidDependents(dependents(TYPE), why);
      return finish(true);
    }
    const typePath = `${at}/contenttypes('${itemType.StringId}')`;
    if (!await establishFixture(TYPE, () => spGet(`${typePath}?$select=ClientFormCustomFormatter`),
      { ClientFormCustomFormatter: (v) => v === null || typeof v === 'string' }, dependents(TYPE))) return finish(true);
    const shell = (t) => JSON.stringify({ headerJSONFormatter: { elmType: 'div', txtContent: t } });
    const overhead = shell('').length;
    // The read back, not the write status, says what the type holds: saved, refused, or unanswered.
    const attempt = async (n) => {
      const formatter = shell('x'.repeat(Math.max(0, n - overhead)));
      const w = await post(typePath, { __metadata: { type: 'SP.ContentType' }, ClientFormCustomFormatter: formatter }, MERGE);
      if (!w.ok) {
        return isRefusal(w.status) && !bare500(w)
          ? { verdict: 'refused', why: `HTTP ${w.status} ${reason(w)}` }
          : { verdict: 'unanswered', why: `the write ${unanswered(w)}` };
      }
      const back = await spGet(`${typePath}?$select=ClientFormCustomFormatter`);
      if (unanswered(back)) return { verdict: 'unanswered', why: `the read back ${unanswered(back)}` };
      return back.body.ClientFormCustomFormatter === formatter
        ? { verdict: 'saved' } : { verdict: 'refused', why: 'the write answered success but the read back differs' };
    };
    let good = 0;
    let bad = null;
    let why = '';
    let stopped = null;
    for (let n = 1024; n <= CAP && bad === null && stopped === null; n *= 2) {
      const r = await attempt(n);
      if (r.verdict === 'saved') good = n;
      else if (r.verdict === 'refused') { bad = n; why = r.why; } else stopped = r.why;
    }
    while (bad !== null && stopped === null && bad - good > 1) {
      const mid = Math.floor((good + bad) / 2);
      const r = await attempt(mid);
      if (r.verdict === 'saved') good = mid;
      else if (r.verdict === 'refused') { bad = mid; why = r.why; } else stopped = r.why;
    }
    if (stopped !== null) {
      record(F_SIZE, 'the largest form formatter the content type saves, found by doubling then bisecting', 'NOT ESTABLISHED',
        `the search stopped with ${good} saved: ${stopped}`, 'open');
      voidDependents(dependents(F_SIZE), 'the size search did not finish');
      FACTS.header_size_limit = `INCONCLUSIVE: the search stopped with ${good} saved: ${stopped}`;
      return finish(true);
    }
    FACTS.header_size_limit = { largest_saved: good, first_refused: bad, refusal: why, cap: CAP };
    record(F_SIZE, 'the largest form formatter the content type saves, found by doubling then bisecting',
      bad === null ? 'NO LIMIT BELOW CAP' : 'MEASURED', `largest saved ${good}, first refused ${bad === null ? 'none' : bad}: ${why}`);
    // Leave the largest saved formatter in place so a person can see whether it renders.
    const last = good > 0 ? await attempt(good) : { verdict: 'refused', why: 'nothing saved' };
    if (last.verdict !== 'saved') {
      record(M_SIZE, 'whether the largest saved formatter renders on the form', 'NOT ESTABLISHED',
        `the largest saved formatter could not be written back: ${last.why}`, 'open');
      return finish(true);
    }
    const sizeBase = `${new URL(WEB).origin}${list.body.RootFolder.ServerRelativeUrl}`;
    record(M_SIZE, 'whether the largest saved formatter renders on the form', 'MANUAL',
      `Open ${sizeBase}/NewForm.aspx. Screenshot it. Record whether the header shows (a ${good}-character text line) or the form shows no header.`);
    return finish(true);
  }

  const day = (v) => typeof v === 'string' && v.slice(0, 10);
  // standData makes or finds one list's operand columns and its one item, and reads both back.
  const standData = async (L) => {
    const at = L.at;
    const list = L.list;
    // Options 9 adds the field to the default content type, without which it reaches no form.
    const addField = (schemaXml) => post(`${at}/fields/createfieldasxml`, { parameters: {
      __metadata: { type: 'SP.XmlSchemaFieldCreationInformation' }, SchemaXml: schemaXml, Options: 9 } });
    if (BUILD) {
      for (const name of [NUM, BLANKS.number]) {
        said(`${name} create`, await addField(`<Field Type='Number' Name='${name}' DisplayName='${name}'></Field>`));
      }
      for (const name of [TXT, BLANKS.text]) {
        said(`${name} create`, await addField(`<Field Type='Text' Name='${name}' DisplayName='${name}'></Field>`));
      }
      for (const name of [DAT, LEAP, BLANKS.date]) {
        said(`${name} create`, await addField(`<Field Type='DateTime' Name='${name}' DisplayName='${name}' Format='DateOnly'></Field>`));
      }
      for (const name of [CHO, BLANKS.choice]) {
        said(`${name} create`, await addField(`<Field Type='Choice' Name='${name}' DisplayName='${name}'>`
          + '<CHOICES><CHOICE>Low</CHOICE><CHOICE>High</CHOICE></CHOICES></Field>'));
      }
    }
    const readFields = () => spGet(`${at}/fields?$select=Title,InternalName,TypeAsString&$top=500`);
    let fields = null;
    const kindOf = (name) => {
      const f = ((fields && fields.body && fields.body.value) || []).find((r) => r && r.InternalName === name);
      return f && f.TypeAsString;
    };
    const OPERAND_KINDS = { [NUM]: 'Number', [TXT]: 'Text', [DAT]: 'DateTime', [LEAP]: 'DateTime', [CHO]: 'Choice',
      BlankNum: 'Number', BlankText: 'Text', BlankDate: 'DateTime', BlankChoice: 'Choice' };
    if (!await establishFixture(L.ids.cols, async () => (fields = await readFields()),
      { value: (rows) => Array.isArray(rows) && Object.entries(OPERAND_KINDS).every(([n, k]) => kindOf(n) === k) },
      dependents(L.ids.cols))) return false;

    let itemId = null;
    if (BUILD) {
      const made = await post(`${at}/items`, { __metadata: { type: list.body.ListItemEntityTypeFullName },
        Title: 'facts', ...ITEM_VALUES });
      said('item create', made);
      itemId = made.body && made.body.d ? made.body.d.Id : null;
    } else {
      // The build run made exactly one item; later runs find it rather than assuming its Id.
      const items = await spGet(`${at}/items?$select=Id&$top=2`);
      itemId = !unanswered(items) && Array.isArray(items.body.value) && items.body.value.length === 1
        ? items.body.value[0].Id : null;
    }
    const itemRead = () => (Number.isInteger(itemId)
      ? spGet(`${at}/items(${itemId})?$select=Id,Created,${NUM},${TXT},${DAT},${CHO},${LEAP},${Object.values(BLANKS).join(',')}`)
      : { ok: false, status: 0, body: null });
    let item = null;
    if (!await establishFixture(L.ids.item, async () => (item = await itemRead()), {
      Id: itemId, [NUM]: 5, [TXT]: 'abc', [CHO]: 'Low', [DAT]: (v) => day(v) === '2026-03-15',
      [LEAP]: (v) => day(v) === '2024-02-29',
      ...Object.fromEntries(Object.values(BLANKS).map((n) => [n, (v) => v === null])),
      Created: (v) => typeof v === 'string' && !Number.isNaN(Date.parse(v)) },
    dependents(L.ids.item))) return false;

    L.fields = fields;
    L.itemId = itemId;
    L.item = item;
    return true;
  };
  for (const L of LISTS) {
    if (L !== M && !await standList(L)) return finish(true);
    if (!await standData(L)) return finish(true);
  }
  const { itemId, item } = M;

  const fieldAt = (name) => `${at}/fields/getbyinternalnameortitle('${name}')`;
  const readFormatters = async () => {
    const out = {};
    for (const name of DATE_COLUMNS) {
      const r = await spGet(`${fieldAt(name)}?$select=CustomFormatter`);
      if (unanswered(r)) return r;
      out[name] = r.body.CustomFormatter;
    }
    return { ok: true, status: 200, body: out };
  };

  if (BUILD) {
    const refused = [];
    const silent = [];
    for (const [L, c] of LISTS.flatMap((x) => x.cases.map((k) => [x, k]))) {
      const body = { __metadata: { type: 'SP.FieldCalculated' }, Title: c.name, FieldTypeKind: 17,
        OutputType: c.outputType, Formula: c.formula };
      if (c.dateFormat !== undefined) body.DateFormat = c.dateFormat;
      const r = await post(`${L.at}/fields`, body);
      // Only a refusal is a finding; a write nobody answered, or one refused for a column or row-size limit, leaves its case unknown.
      const why = r.ok ? null : silentOf(r) || (CAPACITY.test(reason(r)) ? `named a column or row-size limit: ${reason(r)}` : null);
      if (!r.ok) (why ? silent : refused).push(`${c.name} (${c.formula}): HTTP ${r.status} ${why || reason(r)}`);
    }
    record(CASE_ROW, 'every case column was created, or the server refused it with a message',
      silent.length ? 'NOT ESTABLISHED' : refused.length ? 'SOME REFUSED' : 'ALL ACCEPTED',
      [silent.length && `${silent.length} of ${CASES.length} unanswered: ${silent.join(' | ')}`,
        refused.length && `${refused.length} of ${CASES.length} refused: ${refused.join(' | ')}`].filter(Boolean).join('; ')
        || `${CASES.length} created`, silent.length ? 'open' : undefined);
    for (const name of DATE_COLUMNS) {
      said(`${name} formatter write`, await post(fieldAt(name), { __metadata: { type: 'SP.FieldCalculated' },
        CustomFormatter: DATE_FORMATTER }, MERGE));
    }
    await establishFixture(FMT, readFormatters, { Cdr: DATE_FORMATTER, CdrTime: DATE_FORMATTER }, dependents(FMT));
    return finish(true);
  }

  await establishFixture(FMT, readFormatters, { Cdr: DATE_FORMATTER, CdrTime: DATE_FORMATTER }, dependents(FMT));
  let zoneRead = null;
  const zone = await establishFixture(ZONE, async () => (zoneRead = await spGet('web/regionalsettings/timezone?$select=Id,Information')),
    { Information: (v) => !!v && [v.Bias, v.StandardBias, v.DaylightBias].every(Number.isFinite) }, dependents(ZONE));

  // Only columns the server created are selected: one absent name fails the whole read.
  // The server encodes some leading letters in an internal name, and an underscore-led one is read as OData_<name>.
  const present = new Map(LISTS.flatMap((L) => L.fields.body.value
    .filter((f) => f && f.TypeAsString === 'Calculated')
    .map((f) => [f.Title, f.InternalName.startsWith('_') ? `OData_${f.InternalName}` : f.InternalName])));
  const values = {};
  const unread = {};
  for (const L of LISTS) {
    const names = L.cases.map((c) => c.name).filter((n) => present.has(n));
    for (let i = 0; i < names.length; i += 20) {
      const chunk = names.slice(i, i + 20);
      const r = await spGet(`${L.at}/items(${L.itemId})?$select=${chunk.map((n) => present.get(n)).join(',')}`);
      if (unanswered(r)) { for (const n of chunk) unread[n] = `UNREAD: ${unanswered(r)}`; } else for (const n of chunk) if (present.get(n) in r.body) values[n] = r.body[present.get(n)];
    }
  }
  const cell = (n) => (n in unread ? unread[n] : n in values ? values[n] : present.has(n) ? 'UNREAD' : 'ABSENT');
  // A fact settles only from a value the server returned: the column present, its property in the payload and, where a kind is named, of that kind.
  const isDate = (v) => typeof v === 'string' && !Number.isNaN(Date.parse(v));
  const unreadOf = (ns, kind) => ns.flatMap((n) => {
    if (!present.has(n)) return [`${n} is absent (not created at build)`];
    if (n in unread) return [`${n} ${unread[n]}`];
    if (!(n in values) || values[n] === undefined) return [`${n} was not in the payload`];
    if (kind === 'date' && !isDate(values[n])) return [`${n} read ${JSON.stringify(values[n])}, not a date`];
    return [];
  });
  const asText = await spGet(`${at}/items(${itemId})/FieldValuesAsText`);
  const textOf = (n) => (unanswered(asText) ? `UNREAD: ${unanswered(asText)}` : asText.body[n]);
  const schema = await spGet(`${fieldAt('Ndisp')}?$select=SchemaXml`);
  const textFailure = (ns) => (unanswered(asText) ? [`FieldValuesAsText ${unanswered(asText)}`]
    : ns.filter((n) => typeof asText.body[n] !== 'string').map((n) => `FieldValuesAsText.${n} is absent or not text`));
  const schemaFailure = unanswered(schema) ? [`SchemaXml ${unanswered(schema)}`]
    : typeof schema.body.SchemaXml !== 'string' ? ['SchemaXml is absent or not text'] : [];
  const decimals = schemaFailure.length ? `UNREAD: ${schemaFailure[0]}`
    : ((/\bDecimals="([^"]*)"/.exec(schema.body.SchemaXml) || [])[1] ?? 'absent');

  // A fact whose fixture failed was voided already and stays so.
  const live = (id) => (RESULTS.find((r) => r.id === id) || {}).state !== 'void';
  // A fact whose value read failed is open with the failure as its reason, never MEASURED.
  const unresolved = (id, key, question, reasons) => {
    const why = `a value read failed: ${reasons.join('; ')}`;
    FACTS[key] = `INCONCLUSIVE: ${why}`;
    record(id, question, 'NOT ESTABLISHED', why, 'open');
  };
  const overflowRead = unreadOf(OVERFLOW_CASES.map(([n]) => n));
  if (live(F_OVERFLOW) && overflowRead.length) {
    unresolved(F_OVERFLOW, 'date_overflow', 'what DATE gives for a month or day out of range, and a leap day plus one year', overflowRead);
  } else if (live(F_OVERFLOW)) {
    FACTS.date_overflow = Object.fromEntries(OVERFLOW_CASES.map(([n, call]) => [call, cell(n)]));
    record(F_OVERFLOW, 'what DATE gives for a month or day out of range, and a leap day plus one year', 'MEASURED',
      OVERFLOW_CASES.map(([n, call]) => `${call} = ${cell(n)}`).join('; '));
  }
  const blankRead = unreadOf(CASES.slice(0, BLANK_CASES).map((c) => c.name));
  if (live(F_BLANK) && blankRead.length) {
    unresolved(F_BLANK, 'blank_coercion', 'what each operator gives for a blank beside each operand type', blankRead);
  } else if (live(F_BLANK)) {
    const blank = {};
    for (const [code, sign] of OPS) {
      blank[code] = { sign };
      for (const [type] of OPERANDS) blank[code][type] = { left: cell(`B_${code}_${type}_l`), right: cell(`B_${code}_${type}_r`),
          both: cell(`B_${code}_${type}_b`) };
    }
    FACTS.blank_coercion = { operands: { number: ITEM_VALUES[NUM], text: ITEM_VALUES[TXT], date: ITEM_VALUES[DAT], choice: ITEM_VALUES[CHO] }, cases: blank };
    const missing = CASES.slice(0, BLANK_CASES).filter((c) => !present.has(c.name)).length;
    record(F_BLANK, 'what each operator gives for a blank beside each operand type', 'MEASURED',
      `${BLANK_CASES - missing} of ${BLANK_CASES} cases read; ${missing} absent (not created at build)`);
  }
  const textRead = unreadOf(['Teq1', 'Teq2']);
  if (live(F_TEXT) && textRead.length) {
    unresolved(F_TEXT, 'text_equality_case', 'whether text equality ignores case', textRead);
  } else if (live(F_TEXT)) {
    FACTS.text_equality_case = { literal: cell('Teq1'), column: cell('Teq2') };
    record(F_TEXT, 'whether text equality ignores case', 'MEASURED', `"a"="A" gives ${cell('Teq1')}; TextA="ABC" gives ${cell('Teq2')}`);
  }
  const createdRead = unreadOf(['CpdZero', 'CpdOne'], 'date');
  if (zone && live(F_CREATED) && createdRead.length) {
    unresolved(F_CREATED, 'created_plus_days_day', 'whether [Created]+n takes its day in site-local time', createdRead);
  } else if (zone && live(F_CREATED)) {
    const { Bias, StandardBias, DaylightBias } = zoneRead.body.Information;
    const created = Date.parse(item.body.Created);
    const dayAt = (offsetMinutes) => new Date(created + offsetMinutes * 60000).toISOString().slice(0, 10);
    const utc = dayAt(0);
    const standard = dayAt(-(Bias + StandardBias));
    const daylight = dayAt(-(Bias + DaylightBias));
    const zero = day(cell('CpdZero'));
    const discriminates = standard !== utc && daylight !== utc;
    // Minutes east of UTC. The local day differs from the UTC day only in the last (east) or first (west) m minutes of the UTC day, m the smaller offset.
    const east = [-(Bias + StandardBias), -(Bias + DaylightBias)];
    const clock = (minutes) => {
      const v = ((minutes % 1440) + 1440) % 1440;
      return `${String(Math.floor(v / 60)).padStart(2, '0')}:${String(v % 60).padStart(2, '0')}`;
    };
    const m = Math.min(...east.map(Math.abs));
    const [from, to] = east[0] > 0 ? [1440 - m, 1440] : [0, m];
    const buildWindow = east.every((o) => o > 0) || east.every((o) => o < 0)
      ? `${clock(from + east[0])} to ${clock(to + east[0])} local on standard time, ${clock(from + east[1])} to ${clock(to + east[1])} local on daylight time`
      : null;
    const verdict = !zero ? 'UNREADABLE'
      : !discriminates ? `NOT DISCRIMINATED: the local day equals the UTC day; ${buildWindow ? `build again between ${buildWindow}` : 'this zone has no window where the local day differs from the UTC day under both offsets'}`
        : zero === utc ? 'UTC DAY' : [standard, daylight].includes(zero) ? 'SITE-LOCAL DAY' : 'OTHER DAY';
    FACTS.created_plus_days_day = { created: item.body.Created, utc_day: utc, standard_local_day: standard,
      daylight_local_day: daylight, plus_zero: cell('CpdZero'), plus_one: cell('CpdOne'), verdict };
    const settled = discriminates && zero;
    record(F_CREATED, 'whether [Created]+n takes its day in site-local time', settled ? verdict : 'NOT ESTABLISHED',
      `${verdict}; created ${item.body.Created}, +0 reads ${cell('CpdZero')}, +1 reads ${cell('CpdOne')}`, settled ? undefined : 'open');
  }
  const dateRead = [...unreadOf(['Cdr', 'CdrTime'], 'date'), ...textFailure(['Cdr', 'CdrTime', 'Created'])];
  if (live(F_DATE_READ) && dateRead.length) {
    unresolved(F_DATE_READ, 'calculated_date_read', 'how a calculated date reads over REST and as text', dateRead);
  } else if (live(F_DATE_READ)) {
    FACTS.calculated_date_read = { Cdr: { rest: cell('Cdr'), text: textOf('Cdr') },
      CdrTime: { rest: cell('CdrTime'), text: textOf('CdrTime') }, created_text: textOf('Created') };
    record(F_DATE_READ, 'how a calculated date reads over REST and as text', 'MEASURED',
      `Cdr ${cell('Cdr')} as text ${textOf('Cdr')}; CdrTime ${cell('CdrTime')} as text ${textOf('CdrTime')}`);
  }
  const numberRead = [...unreadOf(['Ndisp', 'NdispWhole']), ...textFailure(['Ndisp', 'NdispWhole']), ...schemaFailure];
  if (live(F_NUMBER) && numberRead.length) {
    unresolved(F_NUMBER, 'calculated_number_display', 'how a calculated number with no decimals setting reads and displays', numberRead);
  } else if (live(F_NUMBER)) {
    FACTS.calculated_number_display = { Ndisp: { rest: cell('Ndisp'), text: textOf('Ndisp') },
      NdispWhole: { rest: cell('NdispWhole'), text: textOf('NdispWhole') }, decimals_attribute: decimals };
    record(F_NUMBER, 'how a calculated number with no decimals setting reads and displays', 'MEASURED',
      `Ndisp ${cell('Ndisp')} as text ${textOf('Ndisp')}; NdispWhole ${cell('NdispWhole')} as text ${textOf('NdispWhole')}; Decimals ${decimals}`);
  }

  const base = `${new URL(WEB).origin}${list.body.RootFolder.ServerRelativeUrl}`;
  if (live(M_FORMATTER)) {
    record(M_FORMATTER, 'what the column formatter shows for a calculated date', 'MANUAL',
      `Open ${base}/AllItems.aspx. Screenshot it. Record the four lines the Cdr and CdrTime cells show: the raw value, toLocaleString, toLocaleDateString and displayValue.`);
  }
  if (live(M_BODY)) {
    record(M_BODY, 'what the Display form body shows for a calculated date', 'MANUAL',
      `Open ${base}/DispForm.aspx?ID=${itemId}. Screenshot it. Record what Cdr and CdrTime show, and the Created value beside them.`);
  }
  return finish(true);
})();
