/**
 * dbml-sharepoint PROBE: WHAT DefaultValue READS BACK BESIDE A DefaultFormula
 *
 * REVISION: e84e55da
 *
 * ONE QUESTION:
 *   When a column carries a DefaultFormula, what does its DefaultValue
 *   property read back, and does either property survive the other being
 *   MERGEd to null?
 *
 * The deploy writes DefaultFormula beside DefaultValue and reads both back
 * (templates/deploy/_field_defaults.js.j2), and the reconcile compares both
 * on every paste and reverts a hand edit by MERGEing the declared value,
 * null where nothing is declared (templates/deploy/_field_reconcile.js.j2).
 * Both were written on the assumption that a formula-only column reads
 * DefaultValue back null. Microsoft Learn documents a DefaultFormulaValue
 * element beside DefaultFormula on the Field element, and nothing has
 * measured whether the REST property DefaultValue carries the formula's
 * result, its text, or nothing. If it carries anything, the defaults phase
 * refuses every formula column on its first paste and the reconcile reports
 * drift on every paste after it.
 *
 * The write shapes are the deploy's. A column is created by a POST to
 * /fields carrying __metadata, FieldTypeKind and DefaultFormula, which is
 * how generators/jsgen.py builds every field body. A revert is a MERGE of
 * DefaultFormula or DefaultValue to the field, null for an absent
 * declaration.
 *
 * SCOPE AND QUESTIONS
 *   field.default-formula.fixture-list-created
 *     A generic list is created (BaseTemplate 100).
 *   field.default-formula.control-missing-field-read-refused
 *     NEGATIVE CONTROL: a field read naming a column that does not exist is
 *     REFUSED. Without it, a property read below could be any server
 *     answer.
 *   field.default-formula.default-value-beside-formula-on-create
 *     A Number column created with DefaultFormula and no DefaultValue: does
 *     DefaultValue read back null, an empty string, or a value?
 *   field.default-formula.default-value-after-item-create
 *     After a bare item create has filled that column once, does the
 *     field's DefaultValue still read back the same?
 *   field.default-formula.value-and-formula-both-on-create
 *     A Number column created with BOTH a DefaultValue the formula cannot
 *     produce and a DefaultFormula: what does each property read back?
 *   field.default-formula.value-and-formula-which-fills
 *     On that column, which of the two fills a bare item create?
 *   field.default-formula.formula-merge-null-clears
 *     MERGE DefaultFormula:null on the formula-only column: does the formula
 *     clear, and what does DefaultValue read after? This is the reconcile's
 *     revert when the mapping declares no formula.
 *   field.default-formula.value-merge-null-keeps-formula
 *     MERGE DefaultValue:null on the column carrying both: does the value
 *     clear and the formula survive? This is the reconcile's revert of a
 *     hand-set value on a formula column.
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101).
 *   library.field.control-missing-column-refused
 *     NEGATIVE CONTROL: a field read naming a column that does not exist is
 *     REFUSED, on the library.
 *   library.field.default-value-beside-formula-on-create
 *     The formula-only Number column on the library: what does DefaultValue
 *     read back?
 *   library.field.default-value-after-upload
 *     After a bare Files/add upload has filled it once, does the field's
 *     DefaultValue still read back the same?
 *
 * NOT MEASURED HERE
 *   What the column settings page shows for either property, and whether a
 *   hand edit on that page sets one property or both. Those are rendered
 *   surfaces and need a capture, not a machine row.
 *
 * MICROSOFT LEARN CITATIONS
 *   DefaultFormula and DefaultFormulaValue as children of a field:
 *     "Field element (Field)", "DefaultFormula element (List)"
 *   The two REST properties (CSOM):
 *     "Field.DefaultValue Property", "Field.DefaultFormula Property"
 *   List creation via POST to `web/lists` and item creation via `items`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields` and update via MERGE:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   File upload via `Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the list and the library it created.
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

  log('INFO', 'probe revision e84e55da. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Readback List';
  const LIB = 'dbmlsp Probe Readback Library';
  const FILE = 'dbmlsp-readback-probe.txt';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const libPath = `web/lists/getbytitle('${LIB}')`;

  // Internal names equal display names. Created through the same POST to
  // /fields the deploy uses, so the names carry no _x0020_ encoding.
  const FORMULA_COL = 'ReadbackYear';
  const BOTH_COL = 'ReadbackBoth';
  const YEAR_FORMULA = '=YEAR(TODAY())';
  // A value =YEAR(TODAY()) can never produce, so an item filled with 7 names
  // the value and an item filled with a year names the formula.
  const PLAIN_VALUE = '7';

  const Q = {
    listFixture: 'A generic list is created (BaseTemplate 100)',
    listControl: 'NEGATIVE CONTROL: a field read naming a column that does not exist is refused',
    onCreate: 'With DefaultFormula and no DefaultValue sent, what does DefaultValue read back',
    afterItem: 'After a bare item create has filled the column, does DefaultValue still read the same',
    bothOnCreate: 'With DefaultValue and DefaultFormula both sent, what does each read back',
    whichFills: 'With both properties held, which one fills a bare item create',
    formulaNull: 'Does MERGE DefaultFormula:null clear the formula, and what does DefaultValue read after',
    valueNull: 'Does MERGE DefaultValue:null clear the value and leave the formula in place',
    libFixture: 'A document library is created (BaseTemplate 101)',
    libControl: 'NEGATIVE CONTROL: a field read naming a column that does not exist is refused',
    libOnCreate: 'On a library, with DefaultFormula and no DefaultValue sent, what does DefaultValue read back',
    libAfterUpload: 'After a bare Files/add upload has filled the column, does DefaultValue still read the same',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' and a DOCUMENT LIBRARY '${LIB}' on ${WEB}.`);
    log('INFO', 'Would add two Number columns to the list (one with a DefaultFormula, one with a DefaultFormula and a DefaultValue),');
    log('INFO', 'one Number column with a DefaultFormula to the library, create one bare item in the list,');
    log('INFO', `upload '${FILE}' bare into the library, and MERGE each property to null once on the list.`);
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' and '${LIB}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing list and library would be reused.');
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

  const LIST_IDS = [
    'field.default-formula.control-missing-field-read-refused',
    'field.default-formula.default-value-beside-formula-on-create',
    'field.default-formula.default-value-after-item-create',
    'field.default-formula.value-and-formula-both-on-create',
    'field.default-formula.value-and-formula-which-fills',
    'field.default-formula.formula-merge-null-clears',
    'field.default-formula.value-merge-null-keeps-formula',
  ];
  const LIB_IDS = [
    'library.field.control-missing-column-refused',
    'library.field.default-value-beside-formula-on-create',
    'library.field.default-value-after-upload',
  ];

  expect('field.default-formula.fixture-list-created', Q.listFixture);
  expect('field.default-formula.control-missing-field-read-refused', Q.listControl);
  expect('field.default-formula.default-value-beside-formula-on-create', Q.onCreate);
  expect('field.default-formula.default-value-after-item-create', Q.afterItem);
  expect('field.default-formula.value-and-formula-both-on-create', Q.bothOnCreate);
  expect('field.default-formula.value-and-formula-which-fills', Q.whichFills);
  expect('field.default-formula.formula-merge-null-clears', Q.formulaNull);
  expect('field.default-formula.value-merge-null-keeps-formula', Q.valueNull);
  expect('library.doc-lib.fixture-library-created', Q.libFixture);
  expect('library.field.control-missing-column-refused', Q.libControl);
  expect('library.field.default-value-beside-formula-on-create', Q.libOnCreate);
  expect('library.field.default-value-after-upload', Q.libAfterUpload);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };
  const settled = (id) => RESULTS.find((r) => r.id === id).state === 'settled';

  // __metadata is a VERBOSE OData construct, so every write carrying it
  // overrides the harness's default nometadata content type.
  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const MERGE = { ...VERBOSE, 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' };

  const rawPost = async (path, body, digest) => {
    try {
      const res = await fetch(`${WEB}/_api/${path}`, {
        method: 'POST',
        headers: { Accept: 'application/json;odata=nometadata', 'X-RequestDigest': digest },
        body,
      });
      const text = await res.text();
      let parsed = null;
      try { parsed = JSON.parse(text); } catch { /* plain text response */ }
      return { ok: res.ok, status: res.status, body: parsed, text };
    } catch (err) {
      return { ok: false, status: 0, body: null, text: String(err) };
    }
  };

  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;
  const show = (v) => JSON.stringify(v === undefined ? null : v);

  // Reads a field WITHOUT $select, so a property the field does not expose
  // reads as undefined rather than failing the whole read.
  const readField = async (container, name) =>
    spGet(`${container}/fields/getbyinternalnameortitle('${name}')`);
  const fieldPath = (container, name) => `${container}/fields/getbyinternalnameortitle('${name}')`;

  // The deploy's own Number body, plus whichever default properties the
  // row under test sends.
  const numberBody = (name, defaults) => ({
    __metadata: { type: 'SP.FieldNumber' }, Title: name, FieldTypeKind: 9, ...defaults,
  });

  const ensureField = async (container, body) => {
    const have = await readField(container, body.Title);
    if (have.ok) return { ok: true, status: have.status, text: 'already present' };
    const digest = await getDigest();
    return spPost(`${container}/fields`, body, digest, VERBOSE);
  };

  // The head names what DefaultValue holds; the evidence quotes both
  // properties so a later reader can see the formula beside it.
  const valueHead = (v) => {
    if (v === undefined || v === null) return 'DEFAULTVALUE NULL';
    if (v === '') return 'DEFAULTVALUE EMPTY STRING';
    return 'DEFAULTVALUE CARRIES A VALUE';
  };
  const pair = (body) =>
    `DefaultValue reads back ${show(body.DefaultValue)}, DefaultFormula reads back ${show(body.DefaultFormula)}`;
  const absent = (v) => v === undefined || v === null || v === '';

  await resetList(LIST);
  await resetList(LIB);

  // =====================================================================
  // PART 1: the generic list
  // =====================================================================
  let digest = await getDigest();
  const haveList = await spGet(listPath);
  if (haveList.ok) {
    record('field.default-formula.fixture-list-created', Q.listFixture, 'ALREADY PRESENT',
           `reusing an existing list '${LIST}'. Set CLEANUP = true for a clean answer`);
  } else {
    const made = await spPost('web/lists', {
      Title: LIST, BaseTemplate: 100,
      Description: 'dbml-sharepoint default-formula readback probe list. Safe to delete.',
    }, digest);
    record('field.default-formula.fixture-list-created', Q.listFixture,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIST}'` : short(made));
    if (!made.ok) voidAll(LIST_IDS, `fixture incomplete: list creation failed (HTTP ${made.status})`);
  }

  if (settled('field.default-formula.fixture-list-created')
      && RESULTS.find((r) => r.id === LIST_IDS[0]).state !== 'void') {
    // ---- NEGATIVE CONTROL: a field read naming a missing column ---------
    const junk = await readField(listPath, 'dbmlspNoSuchField');
    const controlHeld = !junk.ok && isRefusal(junk.status);
    record('field.default-formula.control-missing-field-read-refused', Q.listControl,
           controlHeld ? 'PASS' : (junk.ok ? 'FAIL' : 'NOT ESTABLISHED'),
           controlHeld ? `refused with HTTP ${junk.status}`
             : (junk.ok ? 'the field read naming a missing column was ACCEPTED, so a property '
                          + 'read below cannot be told from any other server answer'
                        : `the field read failed with non-refusal HTTP ${junk.status}`));
    if (!controlHeld) {
      voidAll(LIST_IDS.slice(1),
              `negative control did not hold (HTTP ${junk.status}), so a property read below `
              + 'could not be told from any other server answer');
    } else {
      // ---- The formula-only column ----------------------------------------
      const madeFormula = await ensureField(listPath, numberBody(FORMULA_COL, { DefaultFormula: YEAR_FORMULA }));
      const formulaBefore = await readField(listPath, FORMULA_COL);
      const formulaStored = !readFailed(formulaBefore) && formulaBefore.body.DefaultFormula === YEAR_FORMULA;
      if (!madeFormula.ok || readFailed(formulaBefore)) {
        voidAll([LIST_IDS[1], LIST_IDS[2], LIST_IDS[5]],
                `${FORMULA_COL} was not created or did not read back (create ${short(madeFormula)}; read HTTP ${formulaBefore.status})`);
      } else if (!formulaStored) {
        voidAll([LIST_IDS[1], LIST_IDS[2], LIST_IDS[5]],
                `the formula did not read back as sent on ${FORMULA_COL} (${pair(formulaBefore.body)}), `
                + 'so DefaultValue beside it is unmeasured');
      } else {
        record('field.default-formula.default-value-beside-formula-on-create', Q.onCreate,
               valueHead(formulaBefore.body.DefaultValue),
               `POST fields with DefaultFormula ${show(YEAR_FORMULA)} and no DefaultValue answered ${short(madeFormula)}; `
               + `TypeAsString=${formulaBefore.body.TypeAsString}; ${pair(formulaBefore.body)}`);
      }

      // ---- The column carrying both --------------------------------------
      const madeBoth = await ensureField(listPath,
        numberBody(BOTH_COL, { DefaultValue: PLAIN_VALUE, DefaultFormula: YEAR_FORMULA }));
      const bothBefore = await readField(listPath, BOTH_COL);
      if (!madeBoth.ok) {
        record('field.default-formula.value-and-formula-both-on-create', Q.bothOnCreate,
               isRefusal(madeBoth.status) ? 'REFUSED' : 'NOT ESTABLISHED',
               `POST fields with DefaultValue ${show(PLAIN_VALUE)} and DefaultFormula ${show(YEAR_FORMULA)} answered ${short(madeBoth)}`);
        voidAll([LIST_IDS[4], LIST_IDS[6]], 'the column carrying both properties was not created');
      } else if (readFailed(bothBefore)) {
        voidAll([LIST_IDS[3], LIST_IDS[4], LIST_IDS[6]],
                `${BOTH_COL} did not read back after its create (HTTP ${bothBefore.status})`);
      } else {
        const v = bothBefore.body.DefaultValue;
        const f = bothBefore.body.DefaultFormula;
        let head = 'NEITHER AS SENT';
        if (v === PLAIN_VALUE && f === YEAR_FORMULA) head = 'BOTH KEPT';
        else if (f === YEAR_FORMULA) head = 'FORMULA KEPT, VALUE DIFFERENT';
        else if (v === PLAIN_VALUE) head = 'VALUE KEPT, FORMULA DIFFERENT';
        record('field.default-formula.value-and-formula-both-on-create', Q.bothOnCreate, head,
               `POST fields with DefaultValue ${show(PLAIN_VALUE)} and DefaultFormula ${show(YEAR_FORMULA)} answered ${short(madeBoth)}; `
               + pair(bothBefore.body));
      }

      // ---- A bare item create: Title only ------------------------------
      const afterItemOpen = settled('field.default-formula.default-value-beside-formula-on-create');
      const whichFillsOpen = settled('field.default-formula.value-and-formula-both-on-create');
      if (afterItemOpen || whichFillsOpen) {
        digest = await getDigest();
        const row = await spPost(`${listPath}/items`, { Title: 'dbmlsp readback row' }, digest);
        const back = (row.ok && row.body)
          ? await spGet(`${listPath}/items(${row.body.Id})?$select=Id,${FORMULA_COL},${BOTH_COL}`)
          : null;
        if (!back || readFailed(back)) {
          const why = back ? `the created item did not read back (HTTP ${back.status})`
                           : `the bare item create failed (${short(row)})`;
          if (afterItemOpen) voidAll([LIST_IDS[2]], why);
          if (whichFillsOpen) voidAll([LIST_IDS[4]], why);
        } else {
          const how = `POST items with Title only answered HTTP ${row.status}`;
          if (afterItemOpen) {
            const formulaAfter = await readField(listPath, FORMULA_COL);
            if (readFailed(formulaAfter)) {
              voidAll([LIST_IDS[2]], `${FORMULA_COL} did not read back after the item create (HTTP ${formulaAfter.status})`);
            } else {
              const same = show(formulaAfter.body.DefaultValue) === show(formulaBefore.body.DefaultValue)
                && show(formulaAfter.body.DefaultFormula) === show(formulaBefore.body.DefaultFormula);
              record('field.default-formula.default-value-after-item-create', Q.afterItem,
                     same ? 'UNCHANGED' : 'CHANGED',
                     `${how}; the item's ${FORMULA_COL} reads back ${show(back.body[FORMULA_COL])}; `
                     + `before the create ${pair(formulaBefore.body)}; after it ${pair(formulaAfter.body)}`);
            }
          }
          if (whichFillsOpen) {
            const filled = back.body[BOTH_COL];
            let head = 'FORMULA FILLS';
            if (absent(filled)) head = 'BLANK';
            else if (String(filled) === PLAIN_VALUE) head = 'VALUE FILLS';
            record('field.default-formula.value-and-formula-which-fills', Q.whichFills, head,
                   `${how}; the item's ${BOTH_COL} reads back ${show(filled)} `
                   + `(DefaultValue sent ${show(PLAIN_VALUE)}; the formula yields the current year)`);
          }
        }
      }

      // ---- The reconcile's two reverts, each a MERGE to null --------------
      if (settled('field.default-formula.default-value-beside-formula-on-create')) {
        digest = await getDigest();
        const clear = await spPost(fieldPath(listPath, FORMULA_COL),
          { __metadata: { type: 'SP.Field' }, DefaultFormula: null }, digest, MERGE);
        const after = await readField(listPath, FORMULA_COL);
        let head = 'NOT ESTABLISHED';
        if (clear.ok && !readFailed(after)) head = absent(after.body.DefaultFormula) ? 'CLEARS' : 'ACCEPTED BUT STAYS';
        else if (!clear.ok && isRefusal(clear.status)) head = 'REFUSED';
        record('field.default-formula.formula-merge-null-clears', Q.formulaNull, head,
               `MERGE DefaultFormula:null answered ${short(clear)}; `
               + (readFailed(after) ? `the field did not read back (HTTP ${after.status})` : pair(after.body)));
      }
      if (settled('field.default-formula.value-and-formula-both-on-create')) {
        digest = await getDigest();
        const clear = await spPost(fieldPath(listPath, BOTH_COL),
          { __metadata: { type: 'SP.Field' }, DefaultValue: null }, digest, MERGE);
        const after = await readField(listPath, BOTH_COL);
        let head = 'NOT ESTABLISHED';
        if (clear.ok && !readFailed(after)) {
          if (!absent(after.body.DefaultValue)) head = 'ACCEPTED BUT VALUE STAYS';
          else head = after.body.DefaultFormula === YEAR_FORMULA ? 'VALUE CLEARED, FORMULA KEPT' : 'VALUE CLEARED, FORMULA LOST';
        } else if (!clear.ok && isRefusal(clear.status)) {
          head = 'REFUSED';
        }
        record('field.default-formula.value-merge-null-keeps-formula', Q.valueNull, head,
               `MERGE DefaultValue:null answered ${short(clear)}; `
               + (readFailed(after) ? `the field did not read back (HTTP ${after.status})` : pair(after.body)));
      }
    }
  }

  // =====================================================================
  // PART 2: the document library
  // =====================================================================
  digest = await getDigest();
  const haveLib = await spGet(libPath);
  if (haveLib.ok) {
    record('library.doc-lib.fixture-library-created', Q.libFixture, 'ALREADY PRESENT',
           `reusing an existing library '${LIB}'. Set CLEANUP = true for a clean answer`);
  } else {
    const made = await spPost('web/lists', {
      Title: LIB, BaseTemplate: 101,
      Description: 'dbml-sharepoint default-formula readback probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', Q.libFixture,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : short(made));
    if (!made.ok) {
      voidAll(LIB_IDS, `fixture incomplete: library creation failed (HTTP ${made.status})`);
      return report();
    }
  }

  // ---- NEGATIVE CONTROL: a field read naming a missing column -----------
  const junkField = await readField(libPath, 'dbmlspNoSuchField');
  const libControlHeld = !junkField.ok && isRefusal(junkField.status);
  record('library.field.control-missing-column-refused', Q.libControl,
         libControlHeld ? 'PASS' : (junkField.ok ? 'FAIL' : 'NOT ESTABLISHED'),
         libControlHeld ? `refused with HTTP ${junkField.status}`
           : (junkField.ok ? 'the field read naming a missing column was ACCEPTED, so the rows '
                             + 'below are unproven'
                           : `the field read failed with non-refusal HTTP ${junkField.status}`));
  if (!libControlHeld) {
    voidAll(LIB_IDS.slice(1),
            `negative control did not hold (HTTP ${junkField.status}), so a property read below `
            + 'could not be told from any other server answer');
    return report();
  }

  const libMade = await ensureField(libPath, numberBody(FORMULA_COL, { DefaultFormula: YEAR_FORMULA }));
  const libBefore = await readField(libPath, FORMULA_COL);
  const libStored = !readFailed(libBefore) && libBefore.body.DefaultFormula === YEAR_FORMULA;
  if (!libMade.ok || readFailed(libBefore)) {
    voidAll(LIB_IDS.slice(1),
            `${FORMULA_COL} was not created or did not read back (create ${short(libMade)}; read HTTP ${libBefore.status})`);
    return report();
  }
  if (!libStored) {
    voidAll(LIB_IDS.slice(1),
            `the formula did not read back as sent on ${FORMULA_COL} (${pair(libBefore.body)}), `
            + 'so DefaultValue beside it is unmeasured');
    return report();
  }
  record('library.field.default-value-beside-formula-on-create', Q.libOnCreate,
         valueHead(libBefore.body.DefaultValue),
         `POST fields with DefaultFormula ${show(YEAR_FORMULA)} and no DefaultValue answered ${short(libMade)}; `
         + `TypeAsString=${libBefore.body.TypeAsString}; ${pair(libBefore.body)}`);

  // ---- A bare upload: no metadata ---------------------------------------
  const root = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  if (!folderUrl) {
    voidAll([LIB_IDS[2]], `the library RootFolder did not read back (HTTP ${root.status})`);
    return report();
  }
  digest = await getDigest();
  const up = await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE}',overwrite=true)`,
    'dbmlsp default-formula readback probe file', digest);
  if (!up.ok) {
    voidAll([LIB_IDS[2]], `Files/add failed (${short(up)})`);
    return report();
  }
  const items = await spGet(`${libPath}/items?$select=Id,FileLeafRef,${FORMULA_COL}&$top=50`);
  const rows = (items.ok && items.body && Array.isArray(items.body.value)) ? items.body.value : [];
  const item = rows.find((r) => r.FileLeafRef === FILE);
  const libAfter = await readField(libPath, FORMULA_COL);
  if (!item || readFailed(libAfter)) {
    voidAll([LIB_IDS[2]], item
      ? `${FORMULA_COL} did not read back after the upload (HTTP ${libAfter.status})`
      : `no list item was found for '${FILE}' after upload (HTTP ${items.status})`);
    return report();
  }
  const libSame = show(libAfter.body.DefaultValue) === show(libBefore.body.DefaultValue)
    && show(libAfter.body.DefaultFormula) === show(libBefore.body.DefaultFormula);
  record('library.field.default-value-after-upload', Q.libAfterUpload,
         libSame ? 'UNCHANGED' : 'CHANGED',
         `Files/add with no metadata answered HTTP ${up.status}; the file's ${FORMULA_COL} reads back ${show(item[FORMULA_COL])}; `
         + `before the upload ${pair(libBefore.body)}; after it ${pair(libAfter.body)}`);

  return report();
})();
