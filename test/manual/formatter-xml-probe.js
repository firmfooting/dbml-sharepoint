/**
 * dbml-sharepoint PROBE — FORMATTER AND DISPLAY-NAME TEXT THROUGH XML
 *
 * QUESTION: which characters survive a view CustomFormatter, a column
 * CustomFormatter, a form ClientFormCustomFormatter, a field Title, a view
 * Title, a ValidationMessage and a Description — and does the deployer's
 * own drift comparison agree with what SharePoint actually stored?
 *
 * WHY: fixing the bare '&' that broke a live deployment (#178) exposed how
 * much of the surrounding behaviour is assumed rather than measured. #179
 * is the full brief; this probe is what it asks for — characterising the
 * whole surface rather than the one character that bit.
 *
 * SOURCE
 *   Measured, 2026-08-11, live tenant: a view CustomFormatter containing a
 *   bare '&' makes the view MERGE return HTTP 500,
 *   `System.Xml.XmlException: An error occurred while parsing EntityName`,
 *   at the exact character position of the '&'. That is the ONE thing
 *   already known. Everything else below is an assumption wearing the
 *   clothes of a measurement, per #179, and untested until this runs.
 *
 * WHAT IT ASKS
 *   A_*    view CustomFormatter containing &, &amp;, <, >, >=, ", '.
 *          A_AMP IS THE CONTROL. It must FAIL and reproduce the SOURCE
 *          signature above. If it does not, every other row in this run
 *          is suspect — the probe says so loudly, at the point it happens
 *          and again beside the results.
 *   B_*    the same seven characters in a COLUMN CustomFormatter, which
 *          the deployer compares WITHOUT decoding first
 *          (_field_reconcile.js.j2's canonicalJson, no xmlDecode) — unlike
 *          the view comparison a few lines below it. If the readback here
 *          turns out to be entity-encoded, that comparison is wrong today.
 *   C_*    the same seven characters in a form's ClientFormCustomFormatter
 *          (_forms.js.j2's canonicalFormFormatter, also undecoded).
 *          Untested entirely before this probe.
 *   D_TITLE      a field Title containing a bare '&' (tiered-huddle ships
 *                four of these today, unconfirmed).
 *   D_WIDTH      that same ampersand-bearing display name reused as a view
 *                widths key, exercising _views.js.j2's xmlAttr escape path
 *                end to end — ColumnWidth FieldRefs bind by DISPLAY name.
 *   D_VIEWTITLE  a view Title containing a bare '&'.
 *   D_VALMSG     a field ValidationMessage containing a bare '&', compared
 *                by plain string equality — same undecoded shape as B.
 *   D_DESC       a column Description containing a bare '&', same
 *                undecoded comparison.
 *
 * Every A/B/C row folds three observations into one outcome: did the write
 * succeed, what did the readback look like (a heuristic ENCODED/LITERAL
 * label — the full readback string is always quoted beside it so a reader
 * can judge independently of the heuristic), and would the relevant
 * comparison function call it unchanged or drift. Those functions are
 * copied verbatim from the deploy templates, cited at each definition
 * below — this probe does not import them, because a pasted probe is a
 * single self-contained file. If the real ones change, these copies need
 * re-syncing by hand; nothing here checks that automatically, the way
 * test_probes.py checks the threshold probe's JS and Python row generators
 * against each other for a different pair of files.
 *
 * WHAT EACH ANSWER CHANGES (full list in #179)
 *   - &amp; round-trips on the view -> the deployer can escape on write,
 *     and view_formatter_ampersand_breaks_the_view_xml becomes unnecessary
 *     once writes escape instead of refusing.
 *   - </> are ALSO refused -> the rule widens; vehicle-log and
 *     risk-register ship broken today and need fixing.
 *   - </> are fine -> the _views.js.j2 comment gets the date and
 *     provenance it has never had.
 *   - column readback IS entity-encoded (B) -> the reconciler's comparison
 *     is wrong today; fix it before a column formatter containing '<'
 *     reports permanent drift on every redeploy.
 *   - D_TITLE fails -> tiered-huddle is broken today and four display
 *     names need changing.
 *
 * STORING IS NOT RENDERING. Every write below can save cleanly, read back
 * byte-identical, and paint nothing — that is the whole reason this
 * project keeps probes at all. Nothing here is cleaned up until you have
 * LOOKED; the eyes-on checklist at the end says exactly where.
 *
 * HOW TO RUN
 *   1. Open a disposable SharePoint Online site you own.
 *   2. F12 -> Console -> paste -> Enter. The committed defaults only print
 *      the plan; nothing is written yet.
 *   3. Set CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the whole RESULTS block back, THEN work through the EYES-ON
 *      CHECKLIST it prints and fill in every blank.
 *   5. When you are done looking, set CLEANUP = true (with the other two
 *      still true) and paste once more to recycle the probe list — or
 *      delete 'dbmlsp Probe FormatterXML' by hand.
 *
 * STATUS: NOT YET RUN. Every question below is NOT ESTABLISHED until an
 * operator pastes this into a tenant.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // CLEANUP deletes the probe's own list BEFORE the run, so every question
  // is answered by actually creating something rather than reporting
  // "already present" from a previous run — which is much weaker evidence.
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
    console.error('[FATAL] No _spPageContextInfo — paste this into a SharePoint page.');
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
  // so `body !== null` says the response was JSON — never that the call
  // worked. Anything asking "did I actually read this?" must test `ok`.
  const readFailed = (r) => !r.ok || r.body === null;

  // Was this request REFUSED — the server saying no to what was sent — or
  // did it merely fail? A negative control that cannot tell the difference
  // certifies the surface as observable on the strength of a throttle, and
  // every row it guards is then read as evidence.
  //
  // Defined by what it EXCLUDES, because the tempting definition is wrong
  // here. "400 means bad request" is the HTTP convention and it is not what
  // this tenant does: every SharePoint refusal this project has recorded
  // came back 500 —
  //
  //   "To add an item to a document library, use SPFileCollection.Add()"
  //   "One or more column references are not allowed, because the columns
  //    are defined as a data type that is not supported in formulas"
  //   "The formula refers to a column that does not exist"
  //   "This field type does not support..."
  //
  // (analysis/checks/_structure.py, analysis/conditions.py, generators/
  // jsgen.py — each dated and cited to a live run). A 400-only test would
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
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false — not deleting '${title}'.`);
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
    // removed — a locked or no-delete list would otherwise leave rows from
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
  const RESULTS = [];
  const expect = (id, question) => {
    RESULTS.push({ id, question, outcome: 'NOT ESTABLISHED', evidence: 'the run did not reach this question' });
  };
  const record = (id, question, outcome, evidence) => {
    const row = RESULTS.find((r) => r.id === id);
    if (row) {
      Object.assign(row, { question, outcome, evidence });
    } else {
      RESULTS.push({ id, question, outcome, evidence });
    }
    const level = outcome === 'PASS' ? 'OK' : outcome === 'FAIL' ? 'FAIL' : 'INFO';
    log(level, `${id}: ${outcome} — ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };

  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    // PREFIX match, not equality. Outcomes carry their reason —
    // 'NOT ESTABLISHED (throttled)', 'NOT ESTABLISHED (matched 50, expected
    // 60)', 'SHORT (50 of 60, HTTP 200)' — and an equality test counts every
    // one of those as ANSWERED. A results block would then read "47 answered,
    // 0 NOT established" with unresolved rows visible one screen above it,
    // which is the summary lying by omission: the exact failure expect() was
    // added to prevent, reintroduced at the other end of the same function.
    const open = RESULTS.filter(
      (r) => r.outcome.startsWith('NOT ESTABLISHED') || r.outcome.startsWith('SHORT'),
    ).length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} NOT established.`);
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };

  // Printed FIRST, before any gate: see threshold-index-probe.js.j2 for why
  // (a stale clipboard and a fix that did not work produce identical
  // transcripts otherwise).
  log('INFO', 'probe revision c72ab245 — quote this when reporting results.');

  const LIST = 'dbmlsp Probe FormatterXML';
  const FIELD_FMT = 'ProbeFmtField';
  const VIEW = 'dbmlsp probe fmtview';
  const TITLE_WITH_AMP = 'dbmlsp probe & title';
  const VIEW_TITLE_WITH_AMP = 'dbmlsp probe & view';
  const DESC_WITH_AMP = 'Tracks demand & capacity. Safe to delete.';
  const VALMSG_WITH_AMP = 'Value must be positive & non-empty.';

  const listPath = `web/lists/getbytitle('${LIST}')`;
  const fieldsPath = `${listPath}/fields`;

  // ---- The seven characters, asked of every A/B/C surface ---------------
  const CHARS = [
    ['AMP', '&'],
    ['AMPESC', '&amp;'],
    ['LT', '<'],
    ['GT', '>'],
    ['GE', '>='],
    ['QUOT', '"'],
    ['APOS', "'"],
  ];
  const CHAR_DESC = {
    AMP: 'a bare ampersand',
    AMPESC: 'a pre-escaped &amp; entity',
    LT: 'a less-than sign',
    GT: 'a greater-than sign',
    GE: 'a greater-than-or-equal operator (>=)',
    QUOT: 'a double quote',
    APOS: 'a single quote',
  };
  const SURFACE_LABEL = {
    A: 'View CustomFormatter',
    B: 'Column CustomFormatter',
    C: 'Form ClientFormCustomFormatter',
  };
  const questionFor = (prefix, id) => `${SURFACE_LABEL[prefix]} containing ${CHAR_DESC[id]}`;

  // A view/column formatter payload carrying the token as literal text
  // inside a formatter JSON's txtContent — the same shape a real formatter
  // uses for a literal display string ("Demand & Capacity", "x >= 5").
  const formatterWithToken = (token) => JSON.stringify({
    elmType: 'div',
    txtContent: `dbmlsp probe token [${token}] marker`,
  });
  // ClientFormCustomFormatter's pane-native shape nests a part OBJECT under
  // 'header' (_forms.js.j2's docblock: "*JSONFormatter keys hold part
  // OBJECTS"), not a JSON string.
  const formPayloadWithToken = (token) => JSON.stringify({
    header: { elmType: 'div', txtContent: `dbmlsp probe token [${token}] marker` },
  });

  // ---- Comparison functions, copied from the deploy templates -----------
  // xmlDecode and canonicalJson: _field_reconcile.js.j2 / _helpers.js.j2.
  // A calculated Formula is stored in field schema XML and reads back with
  // entities intact; CustomFormatter on a VIEW is stored in the view schema
  // XML the same way (_views.js.j2's comment this probe exists to confirm).
  const xmlDecode = (value) => String(value)
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');
  const canonicalJson = (value) => {
    if (value == null || value === '') return null;
    const sortKeys = (node) => {
      if (Array.isArray(node)) return node.map(sortKeys);
      if (node && typeof node === 'object') {
        return Object.fromEntries(Object.keys(node).sort().map((key) => [key, sortKeys(node[key])]));
      }
      return node;
    };
    let parsed = value;
    if (typeof value === 'string') {
      try { parsed = JSON.parse(value); } catch { return value; }
    }
    return JSON.stringify(sortKeys(parsed));
  };
  // _views.js.j2: decode THEN canonicalise. The only one of the three that
  // decodes before comparing.
  const canonicalViewFormatter = (value) => canonicalJson(typeof value === 'string' ? xmlDecode(value) : value);
  // _forms.js.j2: per-key canonicalise, NO decode.
  const canonicalFormFormatter = (value) => {
    if (value == null || value === '') return null;
    let outer = value;
    if (typeof outer === 'string') {
      try { outer = JSON.parse(outer); } catch { return value; }
    }
    const canon = {};
    for (const key of Object.keys(outer).sort()) {
      let part = outer[key];
      if (typeof part === 'string' && part !== '') {
        try { part = JSON.parse(part); } catch { /* raw string stays */ }
      }
      canon[key] = canonicalJson(part);
    }
    return JSON.stringify(canon);
  };

  // Heuristic label only — depends on the characters actually present in
  // `token`, observes the readback text. The full readback is always
  // quoted beside it in the evidence string, so a reader never has to
  // trust this label on its own.
  const ENTITY_FOR = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&apos;' };
  const describeEncoding = (token, readback) => {
    const text = String(readback);
    const specials = [...new Set(Array.from(token).filter((ch) => ch in ENTITY_FOR))];
    if (specials.length === 0) return 'no XML-special character in this token';
    return specials.map((ch) => {
      const entity = ENTITY_FOR[ch];
      if (text.includes(entity)) return `'${ch}' -> entity-encoded (${entity})`;
      if (text.includes(ch)) return `'${ch}' -> literal, unescaped`;
      return `'${ch}' -> not found verbatim in the readback`;
    }).join('; ');
  };

  // ---- Registration -------------------------------------------------------
  // Literal ids, not built from CHARS in a loop: test_probes.py's
  // reachability check greps the SOURCE TEXT for `expect('ID'` and
  // `record('ID'` — a template-literal id built at runtime is invisible to
  // that regex. The actual record() calls below DO come out of a shared
  // loop (see runFormatterMatrix) because writing twenty-one near-identical
  // write/read/compare blocks by hand is its own source of drift; what
  // matters is that every id that loop can produce is registered here
  // first, which is what makes an aborted run still report the truth.
  expect('A_AMP', 'View CustomFormatter containing a bare ampersand (THE CONTROL)');
  expect('A_AMPESC', 'View CustomFormatter containing a pre-escaped &amp; entity');
  expect('A_LT', 'View CustomFormatter containing a less-than sign');
  expect('A_GT', 'View CustomFormatter containing a greater-than sign');
  expect('A_GE', 'View CustomFormatter containing a greater-than-or-equal operator (>=)');
  expect('A_QUOT', 'View CustomFormatter containing a double quote');
  expect('A_APOS', 'View CustomFormatter containing a single quote');
  expect('B_AMP', 'Column CustomFormatter containing a bare ampersand');
  expect('B_AMPESC', 'Column CustomFormatter containing a pre-escaped &amp; entity');
  expect('B_LT', 'Column CustomFormatter containing a less-than sign');
  expect('B_GT', 'Column CustomFormatter containing a greater-than sign');
  expect('B_GE', 'Column CustomFormatter containing a greater-than-or-equal operator (>=)');
  expect('B_QUOT', 'Column CustomFormatter containing a double quote');
  expect('B_APOS', 'Column CustomFormatter containing a single quote');
  expect('C_AMP', 'Form ClientFormCustomFormatter containing a bare ampersand');
  expect('C_AMPESC', 'Form ClientFormCustomFormatter containing a pre-escaped &amp; entity');
  expect('C_LT', 'Form ClientFormCustomFormatter containing a less-than sign');
  expect('C_GT', 'Form ClientFormCustomFormatter containing a greater-than sign');
  expect('C_GE', 'Form ClientFormCustomFormatter containing a greater-than-or-equal operator (>=)');
  expect('C_QUOT', 'Form ClientFormCustomFormatter containing a double quote');
  expect('C_APOS', 'Form ClientFormCustomFormatter containing a single quote');
  expect('D_TITLE', 'A field Title containing a bare ampersand');
  expect('D_WIDTH', 'That ampersand-bearing display name reused as a view widths key');
  expect('D_VIEWTITLE', 'A view Title containing a bare ampersand');
  expect('D_VALMSG', 'A field ValidationMessage containing a bare ampersand');
  expect('D_DESC', 'A column Description containing a bare ampersand');

  if (!CONFIRMED) {
    log('INFO', `Would create list '${LIST}' with a text field and a view, then`);
    log('INFO', 'write & / &amp; / < / > / >= / " / \' into a view CustomFormatter,');
    log('INFO', 'a column CustomFormatter and a form ClientFormCustomFormatter;');
    log('INFO', 'create a field Title, a view Title, a ValidationMessage and a');
    log('INFO', 'Description each containing a bare ampersand; and reuse the');
    log('INFO', 'ampersand-bearing field title as a view widths key.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  await resetList(LIST);
  let digest = await getDigest();

  // MERGE helper for every write below: SharePoint tunnels MERGE through
  // POST, and a fresh digest per write avoids any expiry question on a
  // probe this long.
  async function mergeProp(url, body) {
    digest = await getDigest();
    return spPost(url, body, digest, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  }

  // ---- Bootstrap: list, probe field, probe view --------------------------
  let listReady = (await spGet(listPath)).ok;
  if (!listReady) {
    digest = await getDigest();
    const madeList = await spPost('web/lists', {
      Title: LIST, BaseTemplate: 100,
      Description: 'dbml-sharepoint formatter-XML probe (issue #179). Safe to recycle.',
    }, digest);
    listReady = madeList.ok;
    if (!madeList.ok) {
      record('BOOTLIST', 'Bootstrap: create the probe list', 'FAIL',
             `HTTP ${madeList.status}: ${madeList.text.slice(0, 400)}`);
    }
  }
  if (!listReady) { report(); return; }

  const fieldExists = async (title) =>
    (await spGet(`${fieldsPath}/getbyinternalnameortitle('${encodeURIComponent(title)}')?$select=Id`)).ok;

  let fieldReady = await fieldExists(FIELD_FMT);
  if (!fieldReady) {
    digest = await getDigest();
    const madeField = await spPost(fieldsPath, { FieldTypeKind: 2, Title: FIELD_FMT, MaxLength: 255 }, digest);
    fieldReady = madeField.ok;
    if (!madeField.ok) {
      record('BOOTFIELD', 'Bootstrap: create the column-formatter probe field', 'FAIL',
             `HTTP ${madeField.status}: ${madeField.text.slice(0, 400)}`);
    }
  }
  const fieldFmtUrl = `${fieldsPath}/getbyinternalnameortitle('${encodeURIComponent(FIELD_FMT)}')`;

  let viewCreated = (await spGet(`${listPath}/views/getbytitle('${encodeURIComponent(VIEW)}')`)).ok;
  if (!viewCreated) {
    digest = await getDigest();
    const madeView = await spPost(`${listPath}/views`, { Title: VIEW, ViewQuery: '', RowLimit: 30 }, digest);
    viewCreated = madeView.ok;
    if (!madeView.ok) {
      record('BOOTVIEW', 'Bootstrap: create the view-formatter probe view', 'FAIL',
             `HTTP ${madeView.status}: ${madeView.text.slice(0, 400)}`);
    }
  }
  const viewUrl = `${listPath}/views/getbytitle('${encodeURIComponent(VIEW)}')`;

  const cts = await spGet(`${listPath}/contenttypes?$select=Id,Name&$top=20`);
  // Accessor stays Id.StringValue: this harness runs odata=nometadata, the
  // spelling document-library-probe.js.j2's L7 proved works under it.
  const ctIdOf = (ct) => String((ct && ct.Id && ct.Id.StringValue) || (ct && ct.Id) || '');
  const ct = ((cts.ok && cts.body && cts.body.value) || [])
    .find((c) => ctIdOf(c).startsWith('0x01') && !ctIdOf(c).startsWith('0x0120'));
  const ctId = ct ? ctIdOf(ct) : null;
  if (!ctId) {
    record('BOOTCT', 'Bootstrap: find the list item content type', 'FAIL',
           `could not find a content type (HTTP ${cts.status})`);
  }

  // ---- The control's loud failure banner ---------------------------------
  let controlHeld = null; // null = never reached; true/false once A_AMP runs
  const loudControlFailure = (detail) => {
    controlHeld = false;
    log('FAIL', '='.repeat(70));
    log('FAIL', `CONTROL (A_AMP) DID NOT REPRODUCE the 2026-08-11 measurement${detail ? `: ${detail}` : '.'}`);
    log('FAIL', 'Something has changed since that run — a platform fix, a tenant');
    log('FAIL', 'setting, or a bug in this probe. EVERY OTHER ROW BELOW IS SUSPECT.');
    log('FAIL', "Read A_AMP's evidence in the RESULTS block before trusting anything else.");
    log('FAIL', '='.repeat(70));
  };

  // ---- Shared A/B/C runner ------------------------------------------------
  // depends on: targetUrl, propertyName, buildPayload, canonicalFn — fixed
  // before each call. observes: HTTP status and the readback text. Only the
  // observed half decides ACCEPTED/REFUSED/drift; the control's expected
  // signature is the one place this probe asserts against a prediction, and
  // that prediction is a literal quote of a live measurement, not a guess.
  async function runFormatterMatrix(prefix, targetUrl, propertyName, buildPayload, canonicalFn, isControlSection) {
    for (const [id, token] of CHARS) {
      const rowId = `${prefix}_${id}`;
      const question = questionFor(prefix, id);
      const payload = buildPayload(token);
      const write = await mergeProp(targetUrl, { [propertyName]: payload });

      if (!write.ok) {
        if (isControlSection && id === 'AMP') {
          const signature = /XmlException/i.test(write.text) && /EntityName/i.test(write.text);
          controlHeld = write.status === 500 && signature;
          record(rowId, question,
                 controlHeld ? 'REFUSED — CONTROL HELD' : 'REFUSED — SIGNATURE DIFFERS FROM 2026-08-11',
                 `HTTP ${write.status}: ${write.text.slice(0, 400)}`);
          if (!controlHeld) loudControlFailure(`refused with a different signature (HTTP ${write.status})`);
          continue;
        }
        record(rowId, question, isRefusal(write.status) ? 'REFUSED' : 'NOT ESTABLISHED',
               `HTTP ${write.status}: ${write.text.slice(0, 400)}`);
        continue;
      }

      if (isControlSection && id === 'AMP') {
        loudControlFailure('the write was ACCEPTED instead of refused');
      }

      const read = await spGet(`${targetUrl}?$select=${propertyName}`);
      if (readFailed(read)) {
        record(rowId, question, 'NOT ESTABLISHED',
               `write returned HTTP ${write.status} but the read-back failed (HTTP ${read.status})`);
        continue;
      }
      const readback = read.body[propertyName];
      const drift = canonicalFn(readback) !== canonicalFn(payload);
      record(rowId, question, `ACCEPTED — ${drift ? 'DRIFT' : 'UNCHANGED'}`,
             `wrote ${JSON.stringify(payload)}; read back ${JSON.stringify(readback)}. `
             + describeEncoding(token, String(readback)));
    }
  }

  // ---- Section A: view CustomFormatter ------------------------------------
  if (viewCreated) {
    await runFormatterMatrix('A', viewUrl, 'CustomFormatter', formatterWithToken, canonicalViewFormatter, true);
  } else {
    for (const [id] of CHARS) {
      record(`A_${id}`, questionFor('A', id), 'NOT ESTABLISHED', 'the probe view could not be created; see BOOTVIEW');
    }
  }

  // ---- Section B: column CustomFormatter ----------------------------------
  if (fieldReady) {
    await runFormatterMatrix('B', fieldFmtUrl, 'CustomFormatter', formatterWithToken, canonicalJson, false);
  } else {
    for (const [id] of CHARS) {
      record(`B_${id}`, questionFor('B', id), 'NOT ESTABLISHED', 'the probe field could not be created; see BOOTFIELD');
    }
  }

  // ---- Section C: form ClientFormCustomFormatter --------------------------
  if (ctId) {
    const ctUrl = `${listPath}/contenttypes('${ctId}')`;
    await runFormatterMatrix('C', ctUrl, 'ClientFormCustomFormatter', formPayloadWithToken, canonicalFormFormatter, false);
  } else {
    for (const [id] of CHARS) {
      record(`C_${id}`, questionFor('C', id), 'NOT ESTABLISHED', 'no content type was found; see BOOTCT');
    }
  }

  // ---- D_TITLE: a field Title containing a bare ampersand -----------------
  let titleFieldInternalName = null;
  let titleFieldActualTitle = null;
  {
    digest = await getDigest();
    const created = await spPost(fieldsPath, { FieldTypeKind: 2, Title: TITLE_WITH_AMP, MaxLength: 255 }, digest);
    if (!created.ok) {
      record('D_TITLE', 'A field Title containing a bare ampersand',
             isRefusal(created.status) ? 'REFUSED' : 'NOT ESTABLISHED',
             `HTTP ${created.status}: ${created.text.slice(0, 400)}`);
    } else {
      const internalName = created.body && created.body.InternalName;
      if (!internalName) {
        record('D_TITLE', 'A field Title containing a bare ampersand', 'NOT ESTABLISHED',
               `field created (HTTP ${created.status}) but the response carried no InternalName `
               + `to read it back by: ${JSON.stringify(created.body).slice(0, 300)}`);
      } else {
        // Fresh read, not the POST echo — the point of this row is what
        // SharePoint actually STORED, not what it handed back synchronously.
        const reread = await spGet(
          `${fieldsPath}/getbyinternalnameortitle('${encodeURIComponent(internalName)}')?$select=Title,InternalName`);
        if (readFailed(reread)) {
          record('D_TITLE', 'A field Title containing a bare ampersand', 'NOT ESTABLISHED',
                 `field created (HTTP ${created.status}) but the read-back failed (HTTP ${reread.status})`);
        } else {
          titleFieldInternalName = reread.body.InternalName;
          titleFieldActualTitle = reread.body.Title;
          record('D_TITLE', 'A field Title containing a bare ampersand',
                 titleFieldActualTitle === TITLE_WITH_AMP ? 'ACCEPTED — ROUND-TRIPPED' : 'ACCEPTED — CHANGED ON READBACK',
                 `declared ${JSON.stringify(TITLE_WITH_AMP)}; read back ${JSON.stringify(titleFieldActualTitle)}; `
                 + `internal name ${JSON.stringify(titleFieldInternalName)}`);
        }
      }
    }
  }

  // ---- D_WIDTH: that display name reused as a widths key ------------------
  {
    if (!viewCreated) {
      record('D_WIDTH', 'That ampersand-bearing display name reused as a view widths key',
             'NOT ESTABLISHED', 'the probe view could not be created; see BOOTVIEW');
    } else if (!titleFieldInternalName || titleFieldActualTitle == null) {
      record('D_WIDTH', 'That ampersand-bearing display name reused as a view widths key',
             'NOT ESTABLISHED', 'the ampersand-titled field could not be created or read back; see D_TITLE');
    } else {
      digest = await getDigest();
      await spPost(`${viewUrl}/viewfields/addviewfield('${encodeURIComponent(titleFieldInternalName)}')`, {}, digest);

      // Same escape and splice as _views.js.j2 lines ~336-349: ColumnWidth
      // FieldRefs bind by DISPLAY name, so the width key is the Title just
      // read back above, xmlAttr-escaped into a FieldRef Name attribute.
      const xmlAttr = (value) => String(value)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
      const currentXmlRes = await spGet(`${viewUrl}?$select=ListViewXml`);
      const currentXml = (currentXmlRes.ok && currentXmlRes.body && String(currentXmlRes.body.ListViewXml)) || '';
      if (readFailed(currentXmlRes) || !currentXml.includes('</View>')) {
        record('D_WIDTH', 'That ampersand-bearing display name reused as a view widths key', 'NOT ESTABLISHED',
               `could not read a usable ListViewXml (HTTP ${currentXmlRes.status})`);
      } else {
        const columnWidthBlock =
          `<ColumnWidth><FieldRef Name="${xmlAttr(titleFieldActualTitle)}" width="120"/></ColumnWidth>`;
        const nextXml = currentXml.includes('<ColumnWidth>')
          ? currentXml.replace(/<ColumnWidth>[\s\S]*?<\/ColumnWidth>/, columnWidthBlock)
          : currentXml.replace('</View>', `${columnWidthBlock}</View>`);
        digest = await getDigest();
        const setRes = await spPost(`${viewUrl}/setviewxml()`, { viewXml: nextXml }, digest);
        if (!setRes.ok) {
          record('D_WIDTH', 'That ampersand-bearing display name reused as a view widths key',
                 isRefusal(setRes.status) ? 'REFUSED' : 'NOT ESTABLISHED',
                 `HTTP ${setRes.status}: ${setRes.text.slice(0, 400)}`);
        } else {
          const afterRes = await spGet(`${viewUrl}?$select=ListViewXml`);
          if (readFailed(afterRes)) {
            record('D_WIDTH', 'That ampersand-bearing display name reused as a view widths key', 'NOT ESTABLISHED',
                   `SetViewXml returned HTTP ${setRes.status} but the read-back failed (HTTP ${afterRes.status})`);
          } else {
            const afterXml = String(afterRes.body.ListViewXml || '');
            const block = afterXml.match(/<ColumnWidth>[\s\S]*?<\/ColumnWidth>/);
            const nameAttr = block && block[0].match(/Name="([^"]*)"/);
            const decodedName = nameAttr ? xmlDecode(nameAttr[1]) : null;
            record('D_WIDTH', 'That ampersand-bearing display name reused as a view widths key',
                   decodedName === titleFieldActualTitle ? 'ACCEPTED — ROUND-TRIPPED' : 'ACCEPTED — DID NOT ROUND-TRIP',
                   `wrote Name=${JSON.stringify(xmlAttr(titleFieldActualTitle))}; readback block `
                   + `${JSON.stringify(block ? block[0] : null)}, decoded name ${JSON.stringify(decodedName)}`);
          }
        }
      }
    }
  }

  // ---- D_VIEWTITLE: a view Title containing a bare ampersand --------------
  {
    digest = await getDigest();
    const created = await spPost(`${listPath}/views`, { Title: VIEW_TITLE_WITH_AMP, ViewQuery: '', RowLimit: 30 }, digest);
    if (!created.ok) {
      record('D_VIEWTITLE', 'A view Title containing a bare ampersand',
             isRefusal(created.status) ? 'REFUSED' : 'NOT ESTABLISHED',
             `HTTP ${created.status}: ${created.text.slice(0, 400)}`);
    } else {
      const reread = await spGet(
        `${listPath}/views/getbytitle('${encodeURIComponent(VIEW_TITLE_WITH_AMP)}')?$select=Title`);
      if (readFailed(reread)) {
        record('D_VIEWTITLE', 'A view Title containing a bare ampersand', 'NOT ESTABLISHED',
               `view created (HTTP ${created.status}) but the read-back failed (HTTP ${reread.status})`);
      } else {
        const actual = reread.body.Title;
        record('D_VIEWTITLE', 'A view Title containing a bare ampersand',
               actual === VIEW_TITLE_WITH_AMP ? 'ACCEPTED — ROUND-TRIPPED' : 'ACCEPTED — CHANGED ON READBACK',
               `declared ${JSON.stringify(VIEW_TITLE_WITH_AMP)}; read back ${JSON.stringify(actual)}`);
      }
    }
  }

  // ---- D_VALMSG: a field ValidationMessage containing a bare ampersand ----
  {
    if (!fieldReady) {
      record('D_VALMSG', 'A field ValidationMessage containing a bare ampersand',
             'NOT ESTABLISHED', 'the probe field could not be created; see BOOTFIELD');
    } else {
      // =FALSE guarantees every save attempt fails validation, so the
      // eyes-on checklist's operator reliably sees the message rendered.
      const setVal = await mergeProp(fieldFmtUrl, { ValidationFormula: '=FALSE', ValidationMessage: VALMSG_WITH_AMP });
      if (!setVal.ok) {
        record('D_VALMSG', 'A field ValidationMessage containing a bare ampersand',
               isRefusal(setVal.status) ? 'REFUSED' : 'NOT ESTABLISHED',
               `HTTP ${setVal.status}: ${setVal.text.slice(0, 400)}`);
      } else {
        const read = await spGet(`${fieldFmtUrl}?$select=ValidationMessage,ValidationFormula`);
        if (readFailed(read)) {
          record('D_VALMSG', 'A field ValidationMessage containing a bare ampersand', 'NOT ESTABLISHED',
                 `write returned HTTP ${setVal.status} but the read-back failed (HTTP ${read.status})`);
        } else {
          // Plain string equality — no decode — the exact comparison
          // _field_reconcile.js.j2 uses for ValidationMessage.
          const actual = read.body.ValidationMessage;
          record('D_VALMSG', 'A field ValidationMessage containing a bare ampersand',
                 actual === VALMSG_WITH_AMP ? 'ACCEPTED — UNCHANGED (plain compare)' : 'ACCEPTED — DRIFT (plain compare)',
                 `declared ${JSON.stringify(VALMSG_WITH_AMP)}; read back ${JSON.stringify(actual)}`);
        }
      }
    }
  }

  // ---- D_DESC: a column Description containing a bare ampersand -----------
  {
    if (!fieldReady) {
      record('D_DESC', 'A column Description containing a bare ampersand',
             'NOT ESTABLISHED', 'the probe field could not be created; see BOOTFIELD');
    } else {
      const setDesc = await mergeProp(fieldFmtUrl, { Description: DESC_WITH_AMP });
      if (!setDesc.ok) {
        record('D_DESC', 'A column Description containing a bare ampersand',
               isRefusal(setDesc.status) ? 'REFUSED' : 'NOT ESTABLISHED',
               `HTTP ${setDesc.status}: ${setDesc.text.slice(0, 400)}`);
      } else {
        const read = await spGet(`${fieldFmtUrl}?$select=Description`);
        if (readFailed(read)) {
          record('D_DESC', 'A column Description containing a bare ampersand', 'NOT ESTABLISHED',
                 `write returned HTTP ${setDesc.status} but the read-back failed (HTTP ${read.status})`);
        } else {
          // Plain equality — normalizeDescription in _field_reconcile.js.j2
          // does not decode either.
          const actual = read.body.Description;
          record('D_DESC', 'A column Description containing a bare ampersand',
                 actual === DESC_WITH_AMP ? 'ACCEPTED — UNCHANGED (plain compare)' : 'ACCEPTED — DRIFT (plain compare)',
                 `declared ${JSON.stringify(DESC_WITH_AMP)}; read back ${JSON.stringify(actual)}`);
        }
      }
    }
  }

  // ---- Report ---------------------------------------------------------
  if (controlHeld === false) {
    log('FAIL', '');
    log('FAIL', 'REMINDER: the control (A_AMP) did not hold. Every row above is');
    log('FAIL', 'suspect until that is understood — do not treat this run as settling #179.');
  } else if (controlHeld === null) {
    log('INFO', 'The control (A_AMP) was never reached — the probe view could not be');
    log('INFO', 'created (see BOOTVIEW). Nothing below is evidence of anything.');
  }
  report();

  console.log('\n============ EYES-ON CHECKLIST — REQUIRED ============');
  console.log('Every row above says only whether SharePoint KEPT the text. None of');
  console.log('them say whether it RENDERS — a formatter can save cleanly, read back');
  console.log('byte-identical, and paint nothing. Open the list and look:\n');
  console.log(`  1. Open the view '${VIEW}' on '${LIST}'. For each of the A_* rows`);
  console.log('     above that came back ACCEPTED, does the marker text with that');
  console.log('     character actually show, or did it store and paint nothing?');
  console.log('     answer: ______________________________________');
  console.log(`  2. Add '${FIELD_FMT}' as a column on that view and look at its`);
  console.log('     formatted cells. Same question for the B_* rows.');
  console.log('     answer: ______________________________________');
  console.log(`  3. Open the New form for '${LIST}'. Does the header/body the C_*`);
  console.log('     rows wrote render, or is the form blank or broken?');
  console.log('     answer: ______________________________________');
  console.log('  4. Open list settings -> columns. Does the D_TITLE field show as');
  console.log(`     "${TITLE_WITH_AMP}", something else, or is it missing entirely?`);
  console.log('     answer: ______________________________________');
  console.log(`  5. In the view '${VIEW}', does the D_WIDTH column actually render`);
  console.log('     at the width that was set, or did the width silently reset');
  console.log('     (_views.js.j2 records exactly that for an internal-name key)?');
  console.log('     answer: ______________________________________');
  console.log('  6. Open the view picker. Does a view titled');
  console.log(`     "${VIEW_TITLE_WITH_AMP}" appear, with its name displaying`);
  console.log('     correctly (D_VIEWTITLE)?');
  console.log('     answer: ______________________________________');
  console.log(`  7. On the New form, put any value into '${FIELD_FMT}' and try to`);
  console.log(`     save. Does the validation message read "${VALMSG_WITH_AMP}"`);
  console.log('     (D_VALMSG), or something else?');
  console.log('     answer: ______________________________________');
  console.log(`  8. Hover the '${FIELD_FMT}' column header for its tooltip. Does the`);
  console.log(`     description read "${DESC_WITH_AMP}" (D_DESC)?`);
  console.log('     answer: ______________________________________');
  console.log('\nReport all eight lines verbatim alongside the RESULTS block.');
  console.log('========================================================');
  log('INFO', `Done. Probe list '${LIST}' remains for you to look at.`);
  log('INFO', 'Set CLEANUP = true (with CONFIRMED and ALLOW_WRITES) and paste again');
  log('INFO', 'to recycle it once you have finished looking, or delete it by hand.');
})();
