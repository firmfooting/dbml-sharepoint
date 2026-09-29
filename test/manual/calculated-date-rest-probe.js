
/** ---- dbml-sharepoint PROBE: THE RAW VALUE REST RETURNS FOR A CALCULATED DATE ----
 *
 * REVISION: 55702554
 *
 * QUESTION: what raw value does the list items endpoint return for a
 * calculated date column (`=[Created]+14`, OutputType DateTime), under
 * odata=nometadata and under odata=verbose, for an item created now?
 *
 * WHY: a flow reduces every calculated date to a site-local date before it
 * compares it. Whether SharePoint returns the value as an instant or as a
 * local calendar date decides how. The answer only discriminates when the
 * item's Created falls on different dates in UTC and in the site's zone,
 * which the evidence states.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   field.date.fixture-calc-date-list    a generic list this probe created
 *   field.date.fixture-calc-date-column  CalcDue reads back Calculated,
 *       OutputType 4 (DateTime) and the formula =Created+14
 *   field.date.fixture-calc-date-item    one item, whose Id and Created read back
 *   field.date.control-site-time-zone    the site's zone and biases, recorded
 *
 * OBSERVES (recorded verbatim with the raw answer, never compared with an expected value)
 *   field.date.calc-date-local-and-utc-dates-differ  Created's date in UTC and
 *       on the site's own clock (utctolocaltime), and whether they differ
 *   field.date.calc-date-rest-nometadata  CalcDue and Created as odata=nometadata returns them
 *   field.date.calc-date-rest-verbose     CalcDue and Created as odata=verbose returns them
 *
 * HOW TO RUN: on a site in a zone away from UTC, at a time when the local
 * and UTC dates differ (a UTC+10 site before 10:00 local, for example), F12
 * -> Console, paste, Enter; it prints its plan and stops. Set CONFIRMED and
 * ALLOW_WRITES to true and paste again (CLEANUP = true recycles a list left
 * by an earlier run first). Copy the RESULTS block back verbatim.
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
  log('INFO', 'probe revision 55702554. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe CalcDate';
  // Ownership is the Description, never the title: a same-title list this probe did not make is left alone.
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint calculated-date probe scratch list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const CALC = 'CalcDue';
  const FORMULA = '=[Created]+14';

  const Q = {
    list: 'a generic list this probe created, carrying its ownership description',
    column: `${CALC} reads back Calculated, OutputType 4 and the formula ${FORMULA}`,
    item: 'one item created now, whose Id and Created read back',
    zone: 'the site zone and its biases',
    differ: 'do Created\'s UTC date and its date on the site\'s own clock differ',
    nometadata: `the raw ${CALC} and Created that odata=nometadata returns`,
    verbose: `the raw ${CALC} and Created that odata=verbose returns`,
  };
  expect('field.date.fixture-calc-date-list', Q.list);
  expect('field.date.fixture-calc-date-column', Q.column);
  expect('field.date.fixture-calc-date-item', Q.item);
  expect('field.date.control-site-time-zone', Q.zone);
  expect('field.date.calc-date-local-and-utc-dates-differ', Q.differ);
  expect('field.date.calc-date-rest-nometadata', Q.nometadata);
  expect('field.date.calc-date-rest-verbose', Q.verbose);

  const AFTER_ITEM = ['field.date.calc-date-local-and-utc-dates-differ',
    'field.date.calc-date-rest-nometadata', 'field.date.calc-date-rest-verbose'];
  const AFTER_COLUMN = ['field.date.fixture-calc-date-item', ...AFTER_ITEM];
  const AFTER_LIST = ['field.date.fixture-calc-date-column', ...AFTER_COLUMN];

  if (!CONFIRMED) {
    log('INFO', `Would create a list '${LIST}' on ${WEB} with one calculated date column`);
    log('INFO', `(${CALC} ${FORMULA}), create one item, and read it back under odata=nometadata`);
    log('INFO', 'and odata=verbose. The list is recycled on the way out.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const canonical = (formula) => String(formula).replace(/[[\]]/g, '');
  const show = (value) => (value === undefined ? '(absent)' : JSON.stringify(value));
  const said = (res) => redactTenant(res.text).slice(0, 400);
  // A fixture read keeps its answer, so a refusal is never mistaken for a missing column or item.
  const readBack = async (path) => {
    const res = await sendRaw(path);
    const head = rawHead(res);
    const parsed = !head && res.parsed && typeof res.parsed === 'object' ? res.parsed : null;
    return { parsed, read: head ? head.why
      : parsed ? `HTTP ${res.status}` : `HTTP ${res.status} carried no JSON: ${said(res)}` };
  };
  let created = false;
  let dateFormat;
  let itemId = null;

  try {
    const zone = await sendRaw('web/RegionalSettings/TimeZone');
    const zoneBody = zone.ok && zone.parsed && typeof zone.parsed === 'object' ? zone.parsed : null;
    const info = zoneBody && zoneBody.Information ? zoneBody.Information : null;
    const zoneHead = rawHead(zone);
    record('field.date.control-site-time-zone', Q.zone,
      info ? 'PASS' : (zoneHead && zoneHead.outcome === 'NOT ESTABLISHED' ? 'NOT ESTABLISHED' : 'FAIL'),
      info
        ? `site zone "${zoneBody.Description}" bias=${info.Bias} standard=${info.StandardBias} `
          + `daylight=${info.DaylightBias}; browser offset ${-new Date().getTimezoneOffset()} min`
        : (zoneHead ? zoneHead.why : `HTTP ${zone.status} carried no Information: ${said(zone)}`));

    const pre = await spGet(`${listPath}?$select=Id,Description`);
    if (pre.ok) {
      if (!pre.body || pre.body.Description !== OWNERSHIP_DESCRIPTION) {
        record('field.date.fixture-calc-date-list', Q.list, 'FAIL',
          `a list named '${LIST}' exists without this probe's ownership description; refusing to modify it`);
        voidDependents(AFTER_LIST, 'the scratch list is not one this probe created');
        return;
      }
      if (!CLEANUP) {
        record('field.date.fixture-calc-date-list', Q.list, 'FAIL',
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
      record('field.date.fixture-calc-date-list', Q.list, 'FAIL',
        `the list create answered HTTP ${made.status}: ${redactTenant(made.text).slice(0, 300)}`);
      voidDependents(AFTER_LIST, 'the scratch list was not created');
      return;
    }
    if (!await establishFixture('field.date.fixture-calc-date-list',
      () => spGet(`${listPath}?$select=BaseTemplate,Description`),
      { BaseTemplate: 100, Description: OWNERSHIP_DESCRIPTION }, AFTER_LIST)) {
      return;
    }

    // The deploy's create body for a calculated date (generators/jsgen.py), DateFormat left to SharePoint.
    const column = await spPost(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldCalculated' }, Title: CALC, FieldTypeKind: 17, Required: false,
      OutputType: 4, Formula: FORMULA,
    }, await getDigest(), VERBOSE);
    log('INFO', `create ${CALC}: HTTP ${column.status}${column.ok ? '' : ` ${redactTenant(column.text).slice(0, 200)}`}`);
    const fieldPath = `${listPath}/fields/getbyinternalnameortitle('${CALC}')`;
    if (!await establishFixture('field.date.fixture-calc-date-column', async () => {
      const typed = await readBack(`${fieldPath}?$select=InternalName,TypeAsString`);
      const body = { Read: typed.read };
      if (!typed.parsed) return { ok: true, status: 200, body };
      body.TypeAsString = typed.parsed.TypeAsString;
      // OutputType, Formula and DateFormat are SP.FieldCalculated's, so another type is never asked.
      if (body.TypeAsString !== 'Calculated') return { ok: true, status: 200, body };
      const calc = await readBack(`${fieldPath}?$select=OutputType,Formula,DateFormat`);
      body.CalculatedRead = calc.read;
      if (calc.parsed) {
        body.OutputType = calc.parsed.OutputType;
        body.Formula = calc.parsed.Formula;
        dateFormat = calc.parsed.DateFormat;
      }
      return { ok: true, status: 200, body };
    }, { Read: 'HTTP 200', TypeAsString: 'Calculated', CalculatedRead: 'HTTP 200', OutputType: 4,
      Formula: (v) => canonical(v) === canonical(FORMULA) }, AFTER_COLUMN)) {
      return;
    }

    const item = await spPost(`${listPath}/items`, { Title: 'dbmlsp calc date 1' }, await getDigest());
    const body = item.body && typeof item.body === 'object' ? item.body : {};
    itemId = body.Id !== undefined ? body.Id : (body.d && body.d.Id !== undefined ? body.d.Id : null);
    log('INFO', `create item: HTTP ${item.status}, Id ${show(itemId)}`);
    let createdAt = null;
    if (!await establishFixture('field.date.fixture-calc-date-item', async () => {
      // With no Id there is nothing to read, so the create's own answer stands in the evidence.
      if (itemId === null) {
        const answered = `the item create answered HTTP ${item.status}: ${said(item)}`;
        return { ok: true, status: 200, body: { Read: answered } };
      }
      const read = await readBack(`${listPath}/items(${itemId})?$select=Id,Created`);
      if (!read.parsed) return { ok: true, status: 200, body: { Read: read.read } };
      createdAt = read.parsed.Created;
      return { ok: true, status: 200, body: { Read: read.read, Id: read.parsed.Id, Created: createdAt } };
    }, { Read: 'HTTP 200', Id: itemId,
      Created: (v) => typeof v === 'string' && !Number.isNaN(Date.parse(v)) }, AFTER_ITEM)) {
      return;
    }

    // The site's own conversion, in the two GET shapes site-zone-transitions-probe.js asks.
    const stamp = encodeURIComponent(new Date(createdAt).toISOString());
    let wall = null;
    let wallSaid = '';
    const wallMisses = [];
    for (const [shape, query] of [
      [`utctolocaltime('${decodeURIComponent(stamp)}')`, `utctolocaltime('${stamp}')`],
      ['utctolocaltime(@d)', `utctolocaltime(@d)?@d='${stamp}'`],
    ]) {
      const res = await sendRaw(`web/RegionalSettings/TimeZone/${query}`);
      const head = rawHead(res);
      const value = res.parsed && typeof res.parsed === 'object' ? res.parsed.value : undefined;
      if (!head && typeof value === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(value)) {
        wall = value;
        wallSaid = said(res);
        break;
      }
      wallMisses.push(`${shape}: `
        + (head ? head.why : `HTTP ${res.status} carried no wall clock: ${said(res)}`));
    }
    const utcDate = new Date(createdAt).toISOString().slice(0, 10);
    record('field.date.calc-date-local-and-utc-dates-differ', Q.differ,
      wall === null ? 'NOT ESTABLISHED' : (wall.slice(0, 10) === utcDate ? 'SAME DATE' : 'DATES DIFFER'),
      wall === null
        ? `neither utctolocaltime shape answered a parseable wall clock: ${wallMisses.join('; ')}`
        : `Created ${createdAt}: UTC date ${utcDate}; the site's clock reads ${wall}, `
          + `date ${wall.slice(0, 10)}; answered ${wallSaid}`);

    const itemPath = `${listPath}/items(${itemId})?$select=Id,Created,${CALC}`;
    for (const [id, question, accept, pick] of [
      ['field.date.calc-date-rest-nometadata', Q.nometadata, 'application/json;odata=nometadata',
        (parsed) => parsed],
      ['field.date.calc-date-rest-verbose', Q.verbose, 'application/json;odata=verbose',
        (parsed) => (parsed.d && typeof parsed.d === 'object' ? parsed.d : null)],
    ]) {
      const res = await sendRaw(itemPath, { accept });
      const head = rawHead(res);
      const entity = !head && res.parsed && typeof res.parsed === 'object' ? pick(res.parsed) : null;
      if (head) {
        record(id, question, head.outcome, head.why);
      } else if (!entity || entity[CALC] === undefined) {
        record(id, question, 'NOT ESTABLISHED', `HTTP ${res.status} carried no ${CALC}: ${said(res)}`);
      } else {
        record(id, question, 'OBSERVED', `HTTP ${res.status}: ${CALC}=${show(entity[CALC])} `
          + `(${typeof entity[CALC]}), Created=${show(entity.Created)}; the column reads `
          + `DateFormat=${show(dateFormat)}; answered ${said(res)}`);
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
