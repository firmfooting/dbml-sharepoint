
/** ---- dbml-sharepoint PROBE: AN ODATA FILTER ON A CALCULATED COLUMN ----
 *
 * REVISION: 4ca95440
 *
 * QUESTION: what does the list items endpoint answer when `$filter` or
 * `$orderby` names a calculated date column, beside the stored-column filter
 * forms a reminder flow sends (a Yes/No column `eq 0`, a date `ne null`,
 * Choice equality, and a date `le` a datetime literal)?
 *
 * WHY: a flow that filters stored columns on the server and calculated
 * columns in the flow rests on the server not serving the second kind.
 * Learn's "Use OData query operations in SharePoint REST requests" lists
 * the supported operators and says nothing about calculated columns.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   query.odata.fixture-calc-filter-list      a generic list this probe created
 *   query.odata.fixture-calc-filter-columns   a Yes/No, a Choice and a date-only
 *       column, and two calculated date columns: one over Created, one over
 *       the stored date, each reading back its type, OutputType and formula
 *   query.odata.fixture-calc-filter-items     three items whose stored values
 *       read back as written; the calculated values they carry are recorded
 *       in each row's evidence and never compared with an expected value
 *   query.odata.control-stored-boolean-eq-filter  ProbeFlag eq 0 serves A and C
 *   query.odata.control-stored-choice-eq-filter   ProbeChoice eq 'Q1' serves A
 *   query.odata.control-stored-date-ne-null-filter  ProbeDate ne null serves A and C
 *   query.odata.control-stored-date-le-datetime-filter  ProbeDate le the subject's
 *       datetime literal serves A and C
 *   The Boolean and Choice controls gate every subject; each date control
 *   gates only the subjects that send its operator. A control that FAILs voids
 *   the subjects it gates; one NOT ESTABLISHED leaves them open and unasked.
 *
 * OBSERVES (status, head, the rows served, the raw answer and the unfiltered fill count)
 *   query.odata.calc-over-created-ne-null-filter     ProbeCalcCreated ne null
 *   query.odata.calc-over-created-le-datetime-filter ProbeCalcCreated le a date
 *       thirty days ahead, which every item's value is before
 *   query.odata.calc-over-stored-ne-null-filter      ProbeCalcStored ne null
 *   query.odata.calc-over-created-orderby            $orderby=ProbeCalcCreated desc
 *
 * HOW TO READ IT: ACCEPTED is the server serving the filter, with the rows
 * it served. ACCEPTED, NO ROWS beside an unfiltered read holding the column
 * filled is the silent case. REFUSED is a refusal, and its text says why.
 * NOT ESTABLISHED is about who asked or when, or a request that never
 * answered.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again
 * (CLEANUP = true recycles a list left by an earlier run first). Copy the
 * RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing to delete. The probe recycles its list before it
 * reports.
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
  // ---- Raw requests (v1) ----------------------------------------------
  // The text is kept whole, since a refusal is often not JSON and its text is the finding.
  const sendRaw = async (path, options = {}) => {
    const method = options.method || 'GET';
    const accept = options.accept || 'application/json;odata=nometadata';
    let res;
    try {
      res = await fetch(`${WEB}/_api/${path}`, {
        method,
        headers: { Accept: accept, ...(options.headers || {}) },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
    } catch (err) {
      // A request that never answered is a row with no status, so the table still prints.
      return { ok: false, status: null, parsed: null, date: null,
        text: `no response: ${err && err.message ? err.message : String(err)}` };
    }
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* not JSON; the text is kept */ }
    const date = res.headers && typeof res.headers.get === 'function' ? res.headers.get('date') : null;
    return { ok: res.ok, status: res.status, text, parsed, date };
  };

  // An error message can quote the request URL, and evidence must not name the tenant.
  const TENANT_ORIGIN = (() => {
    const scheme = WEB.indexOf('//');
    const slash = scheme === -1 ? -1 : WEB.indexOf('/', scheme + 2);
    return slash === -1 ? WEB : WEB.slice(0, slash);
  })();
  // A JSON body can escape the origin's slashes, and a host can appear with no scheme at all.
  const TENANT_PATTERN = (() => {
    const scheme = TENANT_ORIGIN.indexOf('//');
    const host = scheme === -1 ? '' : TENANT_ORIGIN.slice(scheme + 2);
    const needles = [TENANT_ORIGIN, TENANT_ORIGIN.replace(/\//g, '\\/'), host].filter((n) => n);
    const literal = (n) => n.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
    return needles.length ? new RegExp(needles.map(literal).join('|'), 'gi') : null;
  })();
  const redactTenant = (value) => {
    const text = String(value);
    return TENANT_PATTERN ? text.replace(TENANT_PATTERN, '[TENANT]') : text;
  };

  // The head a non-2xx or unanswered request earns, or null when its payload decides.
  const rawHead = (res) => {
    if (res.status === null) return { outcome: 'NOT ESTABLISHED', why: redactTenant(res.text) };
    if (res.ok) return null;
    const said = redactTenant(res.text).slice(0, 400);
    if (isRefusal(res.status)) return { outcome: 'REFUSED', why: `HTTP ${res.status}: ${said}` };
    const reason = unanswered({ ok: false, status: res.status, body: res.parsed });
    return { outcome: 'NOT ESTABLISHED', why: `the request ${reason}: ${said}` };
  };

  // contextinfo wraps its answer in d under odata=verbose and not under nometadata.
  const issueDigest = async () => {
    const res = await sendRaw('contextinfo', { method: 'POST', accept: 'application/json;odata=verbose' });
    const parsed = res.parsed && typeof res.parsed === 'object' ? res.parsed : null;
    const info = parsed && parsed.d ? parsed.d.GetContextWebInformation : parsed;
    const digest = res.ok && info && typeof info.FormDigestValue === 'string'
      ? info.FormDigestValue : null;
    return { res, digest };
  };
  log('INFO', 'probe revision 4ca95440. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe CalcFilter';
  // Ownership is the Description, never the title: a same-title list this probe did not make is left alone.
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint calculated-filter probe scratch list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const FLAG = 'ProbeFlag';
  const CHOICE = 'ProbeChoice';
  const DATE = 'ProbeDate';
  const CALC_CREATED = 'ProbeCalcCreated';
  const CALC_STORED = 'ProbeCalcStored';
  const CALC_FORMULAS = { [CALC_CREATED]: '=[Created]+14', [CALC_STORED]: `=[${DATE}]+365` };
  // The deploy's create bodies (generators/jsgen.py), so a refusal is about the column, not the request.
  const COLUMNS = [
    { name: FLAG, type: 'Boolean', body: { __metadata: { type: 'SP.Field' }, FieldTypeKind: 8 } },
    { name: CHOICE, type: 'Choice', body: { __metadata: { type: 'SP.FieldChoice' }, FieldTypeKind: 6,
      Choices: { results: ['Q1', 'Q2'] }, FillInChoice: false } },
    { name: DATE, type: 'DateTime', body: { __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4,
      DisplayFormat: 0 } },
    ...[CALC_CREATED, CALC_STORED].map((name) => ({ name, type: 'Calculated',
      body: { __metadata: { type: 'SP.FieldCalculated' }, FieldTypeKind: 17, OutputType: 4,
        Formula: CALC_FORMULAS[name] } })),
  ];
  const SEEDS = [
    { key: 'A', Title: 'dbmlsp calc filter A', [FLAG]: false, [CHOICE]: 'Q1', [DATE]: '2026-01-15T00:00:00Z' },
    { key: 'B', Title: 'dbmlsp calc filter B', [FLAG]: true, [CHOICE]: 'Q2', [DATE]: null },
    { key: 'C', Title: 'dbmlsp calc filter C', [FLAG]: false, [CHOICE]: 'Q2', [DATE]: '2026-02-15T00:00:00Z' },
  ];

  const Q = {
    list: 'a generic list this probe created, carrying its ownership description',
    columns: 'the stored and calculated columns read back with the declared type, OutputType and formula',
    items: 'three seeded items read back with the stored values written',
    boolean: `CONTROL: $filter=${FLAG} eq 0 serves the items written false`,
    choice: `CONTROL: $filter=${CHOICE} eq 'Q1' serves the item written Q1`,
    date: `CONTROL: $filter=${DATE} ne null serves the items written a date`,
    dateLe: `CONTROL: $filter=${DATE} le a date thirty days ahead serves the items written a date`,
    createdNeNull: `what $filter=${CALC_CREATED} ne null answers, the column calculated over Created`,
    createdLe: `what $filter=${CALC_CREATED} le a date thirty days ahead answers`,
    storedNeNull: `what $filter=${CALC_STORED} ne null answers, the column calculated over a stored date`,
    createdOrderBy: `what $orderby=${CALC_CREATED} desc answers`,
  };
  expect('query.odata.fixture-calc-filter-list', Q.list);
  expect('query.odata.fixture-calc-filter-columns', Q.columns);
  expect('query.odata.fixture-calc-filter-items', Q.items);
  expect('query.odata.control-stored-boolean-eq-filter', Q.boolean);
  expect('query.odata.control-stored-choice-eq-filter', Q.choice);
  expect('query.odata.control-stored-date-ne-null-filter', Q.date);
  expect('query.odata.control-stored-date-le-datetime-filter', Q.dateLe);
  expect('query.odata.calc-over-created-ne-null-filter', Q.createdNeNull);
  expect('query.odata.calc-over-created-le-datetime-filter', Q.createdLe);
  expect('query.odata.calc-over-stored-ne-null-filter', Q.storedNeNull);
  expect('query.odata.calc-over-created-orderby', Q.createdOrderBy);

  const SUBJECTS = [
    'query.odata.calc-over-created-ne-null-filter',
    'query.odata.calc-over-created-le-datetime-filter',
    'query.odata.calc-over-stored-ne-null-filter',
    'query.odata.calc-over-created-orderby',
  ];
  // Boolean and Choice gate every subject; a date control gates the subjects sending its operator.
  const GENERAL = ['query.odata.control-stored-boolean-eq-filter', 'query.odata.control-stored-choice-eq-filter'];
  const DATE_NE_NULL = 'query.odata.control-stored-date-ne-null-filter';
  const DATE_LE = 'query.odata.control-stored-date-le-datetime-filter';
  const CONTROLS = [...GENERAL, DATE_NE_NULL, DATE_LE];
  const AFTER_ITEMS = [...CONTROLS, ...SUBJECTS];
  const AFTER_COLUMNS = ['query.odata.fixture-calc-filter-items', ...AFTER_ITEMS];
  const AFTER_LIST = ['query.odata.fixture-calc-filter-columns', ...AFTER_COLUMNS];

  if (!CONFIRMED) {
    log('INFO', `Would create a list '${LIST}' on ${WEB} with a Yes/No, a Choice and a date column`);
    log('INFO', 'and two calculated date columns, seed three items, then send four stored-column');
    log('INFO', 'filters and four calculated-column queries. The list is recycled on the way out.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const canonical = (formula) => String(formula).replace(/[[\]]/g, '');
  const filled = (value) => value !== null && value !== undefined && value !== '';
  let created = false;
  let seeded = [];

  try {
    const pre = await spGet(`${listPath}?$select=Id,Description`);
    if (pre.ok) {
      if (!pre.body || pre.body.Description !== OWNERSHIP_DESCRIPTION) {
        record('query.odata.fixture-calc-filter-list', Q.list, 'FAIL',
          `a list named '${LIST}' exists without this probe's ownership description; refusing to modify it`);
        voidDependents(AFTER_LIST, 'the scratch list is not one this probe created');
        return;
      }
      if (!CLEANUP) {
        record('query.odata.fixture-calc-filter-list', Q.list, 'FAIL',
          `a list '${LIST}' from an earlier run is standing and CLEANUP is off`);
        voidDependents(AFTER_LIST, 'a leftover list would answer this run\'s questions');
        return;
      }
      await resetList(LIST);
    }
    const made = await spPost('web/lists',
      { Title: LIST, BaseTemplate: 100, Description: OWNERSHIP_DESCRIPTION }, await getDigest());
    created = made.ok;
    if (!made.ok) {
      record('query.odata.fixture-calc-filter-list', Q.list, 'FAIL',
        `the list create answered HTTP ${made.status}: ${redactTenant(made.text).slice(0, 300)}`);
      voidDependents(AFTER_LIST, 'the scratch list was not created');
      return;
    }
    if (!await establishFixture('query.odata.fixture-calc-filter-list',
      () => spGet(`${listPath}?$select=BaseTemplate,Description`),
      { BaseTemplate: 100, Description: OWNERSHIP_DESCRIPTION }, AFTER_LIST)) {
      return;
    }

    for (const column of COLUMNS) {
      const sent = await spPost(`${listPath}/fields`,
        { ...column.body, Title: column.name, Required: false }, await getDigest(), VERBOSE);
      log('INFO', `create ${column.name}: HTTP ${sent.status}${sent.ok ? '' : ` ${redactTenant(sent.text).slice(0, 200)}`}`);
    }
    const declaredColumns = {};
    for (const column of COLUMNS) {
      declaredColumns[`${column.name}.Read`] = 'HTTP 200';
      declaredColumns[`${column.name}.TypeAsString`] = column.type;
    }
    for (const name of [CALC_CREATED, CALC_STORED]) {
      declaredColumns[`${name}.OutputType`] = 4;
      declaredColumns[`${name}.Formula`] = (v) => canonical(v) === canonical(CALC_FORMULAS[name]);
    }
    if (!await establishFixture('query.odata.fixture-calc-filter-columns', async () => {
      const body = {};
      for (const column of COLUMNS) {
        // OutputType and Formula belong to SP.FieldCalculated, so a stored column is never asked for them.
        const select = column.type === 'Calculated'
          ? 'InternalName,TypeAsString,OutputType,Formula' : 'InternalName,TypeAsString';
        const res = await sendRaw(`${listPath}/fields/getbyinternalnameortitle('${column.name}')`
          + `?$select=${select}`);
        const head = rawHead(res);
        const field = !head && res.parsed && typeof res.parsed === 'object' ? res.parsed : null;
        // The answer is kept, so a refused read is not mistaken for a column that was never created.
        body[`${column.name}.Read`] = head ? head.why : field ? `HTTP ${res.status}`
          : `HTTP ${res.status} carried no JSON: ${redactTenant(res.text).slice(0, 400)}`;
        if (!field) continue;
        body[`${column.name}.TypeAsString`] = field.TypeAsString;
        if (column.type === 'Calculated') {
          body[`${column.name}.OutputType`] = field.OutputType;
          body[`${column.name}.Formula`] = field.Formula;
        }
      }
      return { ok: true, status: 200, body };
    }, declaredColumns, AFTER_COLUMNS)) {
      return;
    }

    for (const seed of SEEDS) {
      const body = { Title: seed.Title, [FLAG]: seed[FLAG], [CHOICE]: seed[CHOICE] };
      if (seed[DATE] !== null) body[DATE] = seed[DATE];
      const sent = await spPost(`${listPath}/items`, body, await getDigest());
      log('INFO', `seed ${seed.key}: HTTP ${sent.status}${sent.ok ? '' : ` ${redactTenant(sent.text).slice(0, 200)}`}`);
    }
    const declaredItems = { Items: SEEDS.length };
    for (const seed of SEEDS) {
      declaredItems[`${seed.key}.${FLAG}`] = seed[FLAG];
      declaredItems[`${seed.key}.${CHOICE}`] = seed[CHOICE];
      declaredItems[`${seed.key}.${DATE}Filled`] = seed[DATE] !== null;
    }
    if (!await establishFixture('query.odata.fixture-calc-filter-items', async () => {
      const read = await spGet(`${listPath}/items?$select=Id,Title,${FLAG},${CHOICE},${DATE},`
        + `${CALC_CREATED},${CALC_STORED}&$orderby=Id&$top=100`);
      if (unanswered(read) !== null) return read;
      if (!Array.isArray(read.body.value)) return { ok: true, status: read.status, body: {} };
      seeded = read.body.value;
      const body = { Items: seeded.length };
      for (const seed of SEEDS) {
        const row = seeded.find((item) => item.Title === seed.Title);
        if (!row) continue;
        body[`${seed.key}.${FLAG}`] = row[FLAG];
        body[`${seed.key}.${CHOICE}`] = row[CHOICE];
        body[`${seed.key}.${DATE}Filled`] = filled(row[DATE]);
      }
      return { ok: true, status: 200, body };
    }, declaredItems, AFTER_ITEMS)) {
      return;
    }

    const idOf = (key) => {
      const row = seeded.find((item) => item.Title === SEEDS.find((seed) => seed.key === key).Title);
      return row ? row.Id : null;
    };
    const keyOf = (id) => {
      const row = seeded.find((item) => item.Id === id);
      const seed = row ? SEEDS.find((candidate) => candidate.Title === row.Title) : null;
      return seed ? seed.key : `Id ${id}`;
    };
    const query = async (option, value) => {
      const res = await sendRaw(`${listPath}/items?$select=Id&$top=100&${option}=${encodeURIComponent(value)}`);
      const rows = !rawHead(res) && res.parsed && Array.isArray(res.parsed.value) ? res.parsed.value : null;
      return { res, keys: rows ? rows.map((row) => keyOf(row.Id)) : null };
    };

    // The subject's own literal, so a refusal of the literal shows on a stored date first.
    const ahead = `datetime'${new Date(Date.now() + 30 * 86400000).toISOString().slice(0, 10)}T00:00:00Z'`;
    const failedControls = new Set();
    const unreadControls = new Map();
    for (const [id, question, option, value, want] of [
      [GENERAL[0], Q.boolean, '$filter', `${FLAG} eq 0`, ['A', 'C']],
      [GENERAL[1], Q.choice, '$filter', `${CHOICE} eq 'Q1'`, ['A']],
      [DATE_NE_NULL, Q.date, '$filter', `${DATE} ne null`, ['A', 'C']],
      [DATE_LE, Q.dateLe, '$filter', `${DATE} le ${ahead}`, ['A', 'C']],
    ]) {
      const { res, keys } = await query(option, value);
      const head = rawHead(res);
      const held = keys !== null && [...keys].sort().join(',') === want.join(',');
      const outcome = held ? 'PASS' : (head && head.outcome === 'NOT ESTABLISHED' ? 'NOT ESTABLISHED' : 'FAIL');
      record(id, question, outcome, `${option}=${value}: `
        + (head ? head.why : keys === null
          ? `HTTP ${res.status} carried no rows: ${redactTenant(res.text).slice(0, 400)}`
          : `HTTP ${res.status}, served ${keys.join(', ') || 'no rows'}; written ${want.join(', ')}`));
      if (outcome === 'FAIL') failedControls.add(id);
      if (outcome === 'NOT ESTABLISHED') unreadControls.set(id, head.why);
    }

    const fillOf = (column) => `the unfiltered read holds ${seeded.filter((item) => filled(item[column])).length}`
      + ` of ${seeded.length} item(s) with ${column} filled (${seeded.map((item) => `${keyOf(item.Id)}=`
      + `${JSON.stringify(item[column] === undefined ? null : item[column])}`).join(', ')})`;
    for (const [id, question, option, value, column, rests] of [
      ['query.odata.calc-over-created-ne-null-filter', Q.createdNeNull, '$filter',
        `${CALC_CREATED} ne null`, CALC_CREATED, [...GENERAL, DATE_NE_NULL]],
      ['query.odata.calc-over-created-le-datetime-filter', Q.createdLe, '$filter',
        `${CALC_CREATED} le ${ahead}`, CALC_CREATED, [...GENERAL, DATE_LE]],
      ['query.odata.calc-over-stored-ne-null-filter', Q.storedNeNull, '$filter',
        `${CALC_STORED} ne null`, CALC_STORED, [...GENERAL, DATE_NE_NULL]],
      ['query.odata.calc-over-created-orderby', Q.createdOrderBy, '$orderby',
        `${CALC_CREATED} desc`, CALC_CREATED, GENERAL],
    ]) {
      const failed = rests.filter((control) => failedControls.has(control));
      if (failed.length) {
        voidDependents([id], `the stored-column control ${failed.join(', ')} did not serve the rows `
          + 'written, so a calculated-column answer would say nothing about the column');
        continue;
      }
      // A throttle, a denial or a lost request can clear on a re-run, so the subject stays open.
      const unread = rests.filter((control) => unreadControls.has(control));
      if (unread.length) {
        record(id, question, 'NOT ESTABLISHED', unread.map((control) => `not asked: control ${control} `
          + `not established (${unreadControls.get(control)})`).join('; ') + '; a re-run can ask it');
        continue;
      }
      const { res, keys } = await query(option, value);
      const head = rawHead(res);
      if (head) {
        record(id, question, head.outcome, `${option}=${value}: ${head.why}; ${fillOf(column)}`);
      } else if (keys === null) {
        record(id, question, 'NOT ESTABLISHED', `${option}=${value}: HTTP ${res.status} carried no `
          + `rows: ${redactTenant(res.text).slice(0, 400)}; ${fillOf(column)}`);
      } else {
        // The raw answer is kept beside the keys, so a reader can re-read what the server sent.
        record(id, question, keys.length ? 'ACCEPTED' : 'ACCEPTED, NO ROWS',
          `${option}=${value}: HTTP ${res.status}, served ${keys.join(', ') || 'no rows'}; `
          + `${fillOf(column)}; answered ${redactTenant(res.text).slice(0, 400)}`);
      }
    }
  } catch (err) {
    log('FAIL', `probe aborted: ${redactTenant(String((err && err.message) || err)).slice(0, 240)}. `
      + 'The unasked rows stay open.');
  } finally {
    if (created) {
      let gone;
      try {
        gone = await spPost(`${listPath}/recycle`, {}, await getDigest());
      } catch (err) {
        gone = { ok: false, status: null, text: String((err && err.message) || err) };
      }
      // A request that threw has no status, so its message is what the operator is shown.
      const why = gone.status === null ? redactTenant(gone.text).slice(0, 240) : `HTTP ${gone.status}`;
      log(gone.ok ? 'OK' : 'FAIL', gone.ok
        ? `recycled '${LIST}'; it is restorable from the recycle bin.`
        : `could not recycle '${LIST}' (${why}); recycle it by hand.`);
    }
    // Reported here, after the recycle, so every path prints the recycle line above the table.
    report();
  }
})();
