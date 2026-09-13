/**
 * dbml-sharepoint PROBE: THE THREE GUARDS LIBRARY SUPPORT HOLDS CLOSED
 *
 * REVISION: c445a55c
 *
 * ONE QUESTION:
 *   Can the deploy open the three doors it keeps shut on a document library
 *   until each is measured: a default formula on a Number and on a Choice
 *   column, sealing a declared column, and switching folder creation off?
 *
 * Issue #14 lifts the kind: DocumentLibrary refusal. The first shipped family
 * with a library pre-fills a review year (Number) and a review quarter
 * (Choice) from a default formula at upload, seals its declared columns like
 * every other family, and documents hiding the New Folder command. None of
 * those has evidence on a library. The date-column default formula HAS been
 * measured, on a generic list, through a REST item create
 * (formula.datetime.today-function-default-value,
 * field.date.dynamic-default-rest-fill), which is why the date column here
 * is a control and the Number and Choice columns are the questions.
 *
 * The write shapes are the ones the deploy sends. A column is created by a
 * POST to /fields carrying __metadata, FieldTypeKind and (new) DefaultFormula,
 * which is how generators/jsgen.py builds every field body. If that create
 * is refused, the probe creates the column without the formula and MERGEs
 * DefaultFormula afterwards, so the evidence names which write path works.
 * A seal is a MERGE of Sealed:true to the field, which is what
 * templates/deploy/_seal.js.j2 sends. The folder switch is a MERGE of
 * EnableFolderCreation to the list, the same write list-settings-probe.js
 * makes.
 *
 * SCOPE AND QUESTIONS
 *   field.default-formula.fixture-list-created
 *     A generic list is created (BaseTemplate 100) as the comparison
 *     container.
 *   field.default-formula.control-missing-column-refused
 *     NEGATIVE CONTROL: an item POST naming a column that does not exist is
 *     REFUSED. Without it, a blank read below could be any server answer.
 *   field.default-formula.number-property-reads-back
 *   field.default-formula.choice-property-reads-back
 *     Does DefaultFormula survive the create on a Number and on a Choice
 *     column, and read back as sent?
 *   field.default-formula.control-date-fills-on-item-create
 *     POSITIVE CONTROL: =TODAY() on a date column fills on a bare item
 *     create, which is the measured list fact this probe extends.
 *   field.default-formula.number-fills-on-item-create
 *   field.default-formula.choice-fills-on-item-create
 *     Does a bare item create (Title only) come back with the Number and the
 *     Choice column already filled?
 *   field.default-formula.choice-non-member-result
 *     A Choice formula whose result is not one of the choices: blank, or the
 *     literal stored anyway? This is the failure the validator cannot catch
 *     statically, so the platform's answer decides what the finding says.
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101).
 *   library.field.control-missing-column-refused
 *     NEGATIVE CONTROL: a field read naming a column that does not exist is
 *     REFUSED.
 *   library.field.default-formula-number-reads-back
 *   library.field.default-formula-choice-reads-back
 *     The same two property round-trips, on the library.
 *   library.field.default-formula-date-fills-on-upload
 *   library.field.default-formula-number-fills-on-upload
 *   library.field.default-formula-choice-fills-on-upload
 *     A bare Files/add upload, no metadata: does the file's item come back
 *     with the date, the Number and the Choice column filled?
 *   library.field.default-formula-choice-non-member-on-upload
 *     The non-member Choice result, at upload.
 *   library.view.scope-on-create-reads-back
 *   library.view.scope-on-merge-reads-back
 *     SP.View carries a Scope property (Learn: ViewScope, DefaultValue 0,
 *     Recursive 1, RecursiveAll 2, FilesOnly 3), and the View element's
 *     Scope attribute "corresponds to the Scope property of the SPView
 *     class". library-nesting-probe.js measured what each value RETURNS
 *     through a query; nothing has measured writing the property on a
 *     stored view, which is what the deploy's view phase will do. One view
 *     is created with Scope 1 in the body, another is created bare and
 *     MERGEd to 1, and both are read back.
 *   library.column.seal-declared-column-sticks
 *     MERGE Sealed:true to a declared column on the library: does Sealed
 *     read back true? On a generic list's built-in Title the same write is
 *     refused outright (field.title.seal-merge-spfield), and a library's
 *     Title arrives sealed, so a declared column on a library is its own
 *     question.
 *   library.column.seal-declared-column-unseals
 *     MERGE Sealed:false to the same column: does it read back false? The
 *     maintenance script's unseal path depends on this.
 *   library.doc-lib.folder-creation-disabled-sticks
 *     MERGE EnableFolderCreation:false to the library: does it read back
 *     false?
 *   library.folder.creation-blocked-when-disabled
 *     With the switch off, is Folders/add(url=) still accepted over REST, or
 *     refused? This decides whether the deploy's folder step must run before
 *     the switch is set, or whether the switch only hides the command. The
 *     switch is restored to true at the end of the run.
 *
 * NOT MEASURED HERE
 *   Whether the same default formulas fill in Quick edit or on the upload
 *   panel. Those are rendered surfaces and need a capture, not a machine
 *   row.
 *
 * MICROSOFT LEARN CITATIONS
 *   DefaultFormula on a field:
 *     "DefaultFormula element (List)", "Field.DefaultFormula Property" (CSOM)
 *   List creation via POST to `web/lists` and item creation via `items`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   File upload via `Files/add(url=,overwrite=)` and folder creation via
 *   `Folders/add(url=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   EnableFolderCreation:
 *     "List.EnableFolderCreation Property" (CSOM)
 *   View scope:
 *     "View.Scope Property" and "ViewScope Enum" (CSOM), "View element
 *     (List)" for the attribute's correspondence to the property
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

  log('INFO', 'probe revision c445a55c. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Guards List';
  const LIB = 'dbmlsp Probe Guards Library';
  const FILE = 'dbmlsp-guards-probe.txt';
  const FOLDER = 'dbmlsp-guards-folder';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const libPath = `web/lists/getbytitle('${LIB}')`;

  // Internal names equal display names. Created through the same POST to
  // /fields the deploy uses, so the names carry no _x0020_ encoding.
  const YEAR_COL = 'GuardYear';
  const QUARTER_COL = 'GuardQuarter';
  const BAD_COL = 'GuardQuarterBad';
  const DATE_COL = 'GuardToday';
  const QUARTERS = ['Q1', 'Q2', 'Q3', 'Q4'];
  const YEAR_FORMULA = '=YEAR(TODAY())';
  const QUARTER_FORMULA = '="Q"&ROUNDUP(MONTH(TODAY())/3,0)';
  // Always Q11 to Q14, so never a member of QUARTERS.
  const BAD_FORMULA = '="Q"&(ROUNDUP(MONTH(TODAY())/3,0)+10)';
  const TODAY_FORMULA = '=TODAY()';

  // What the browser's clock says the formulas should produce. Reported
  // beside the observed value and NEVER asserted: TODAY() evaluates on the
  // server in the site's regional zone, and a paste near midnight or a
  // quarter boundary can legitimately disagree with this machine. The
  // outcome head is FILLED or BLANK; the match is evidence.
  const now = new Date();
  const expectYear = now.getFullYear();
  const expectQuarter = `Q${Math.ceil((now.getMonth() + 1) / 3)}`;

  const Q = {
    listFixture: 'A generic list is created (BaseTemplate 100) as the comparison container',
    listControl: 'NEGATIVE CONTROL: an item POST naming a column that does not exist is refused',
    listNumberProp: 'Does DefaultFormula on a Number column read back as sent, on a list',
    listChoiceProp: 'Does DefaultFormula on a Choice column read back as sent, on a list',
    listDateFill: 'POSITIVE CONTROL: does =TODAY() on a date column fill on a bare item create',
    listNumberFill: 'Does =YEAR(TODAY()) on a Number column fill on a bare item create',
    listChoiceFill: 'Does a quarter formula on a Choice column fill on a bare item create',
    listBad: 'A Choice formula whose result is not a member: blank, or stored anyway, on a list',
    libFixture: 'A document library is created (BaseTemplate 101)',
    libControl: 'NEGATIVE CONTROL: a field read naming a column that does not exist is refused',
    libNumberProp: 'Does DefaultFormula on a Number column read back as sent, on a library',
    libChoiceProp: 'Does DefaultFormula on a Choice column read back as sent, on a library',
    libDateFill: 'Does =TODAY() on a date column fill on a bare Files/add upload',
    libNumberFill: 'Does =YEAR(TODAY()) on a Number column fill on a bare Files/add upload',
    libChoiceFill: 'Does a quarter formula on a Choice column fill on a bare Files/add upload',
    libBad: 'A Choice formula whose result is not a member: blank, or stored anyway, at upload',
    sealSticks: 'Does MERGE Sealed:true on a declared library column read back true',
    sealUnseals: 'Does MERGE Sealed:false on that column read back false again',
    switchSticks: 'Does MERGE EnableFolderCreation:false on the library read back false',
    folderBlocked: 'With folder creation switched off, is Folders/add(url=) refused or accepted',
    scopeCreate: 'Does a view created with Scope 1 (Recursive) in its body read back Scope 1',
    scopeMerge: 'Does MERGE Scope:1 on a stored view read back Scope 1',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' and a DOCUMENT LIBRARY '${LIB}' on ${WEB}.`);
    log('INFO', 'Would add a Number, two Choice and a date column to each, every one with a DefaultFormula,');
    log('INFO', `create one bare item in the list, upload '${FILE}' bare into the library,`);
    log('INFO', 'seal and unseal one library column, switch folder creation off, try a folder, and switch it back on.');
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
    'field.default-formula.control-missing-column-refused',
    'field.default-formula.number-property-reads-back',
    'field.default-formula.choice-property-reads-back',
    'field.default-formula.control-date-fills-on-item-create',
    'field.default-formula.number-fills-on-item-create',
    'field.default-formula.choice-fills-on-item-create',
    'field.default-formula.choice-non-member-result',
  ];
  const LIB_IDS = [
    'library.field.control-missing-column-refused',
    'library.field.default-formula-number-reads-back',
    'library.field.default-formula-choice-reads-back',
    'library.field.default-formula-date-fills-on-upload',
    'library.field.default-formula-number-fills-on-upload',
    'library.field.default-formula-choice-fills-on-upload',
    'library.field.default-formula-choice-non-member-on-upload',
    'library.column.seal-declared-column-sticks',
    'library.column.seal-declared-column-unseals',
    'library.doc-lib.folder-creation-disabled-sticks',
    'library.folder.creation-blocked-when-disabled',
    'library.view.scope-on-create-reads-back',
    'library.view.scope-on-merge-reads-back',
  ];

  expect('field.default-formula.fixture-list-created', Q.listFixture);
  expect('field.default-formula.control-missing-column-refused', Q.listControl);
  expect('field.default-formula.number-property-reads-back', Q.listNumberProp);
  expect('field.default-formula.choice-property-reads-back', Q.listChoiceProp);
  expect('field.default-formula.control-date-fills-on-item-create', Q.listDateFill);
  expect('field.default-formula.number-fills-on-item-create', Q.listNumberFill);
  expect('field.default-formula.choice-fills-on-item-create', Q.listChoiceFill);
  expect('field.default-formula.choice-non-member-result', Q.listBad);
  expect('library.doc-lib.fixture-library-created', Q.libFixture);
  expect('library.field.control-missing-column-refused', Q.libControl);
  expect('library.field.default-formula-number-reads-back', Q.libNumberProp);
  expect('library.field.default-formula-choice-reads-back', Q.libChoiceProp);
  expect('library.field.default-formula-date-fills-on-upload', Q.libDateFill);
  expect('library.field.default-formula-number-fills-on-upload', Q.libNumberFill);
  expect('library.field.default-formula-choice-fills-on-upload', Q.libChoiceFill);
  expect('library.field.default-formula-choice-non-member-on-upload', Q.libBad);
  expect('library.column.seal-declared-column-sticks', Q.sealSticks);
  expect('library.column.seal-declared-column-unseals', Q.sealUnseals);
  expect('library.doc-lib.folder-creation-disabled-sticks', Q.switchSticks);
  expect('library.folder.creation-blocked-when-disabled', Q.folderBlocked);
  expect('library.view.scope-on-create-reads-back', Q.scopeCreate);
  expect('library.view.scope-on-merge-reads-back', Q.scopeMerge);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

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

  // Reads a field WITHOUT $select. A $select naming a property the field
  // does not expose fails the whole read, and DefaultFormula's presence is
  // part of what is being measured.
  const readField = async (container, name) =>
    spGet(`${container}/fields/getbyinternalnameortitle('${name}')`);

  // ---- Field bodies: the deploy's own shapes, plus DefaultFormula --------
  const numberBody = (formula) => ({
    __metadata: { type: 'SP.FieldNumber' }, Title: YEAR_COL, FieldTypeKind: 9,
    DefaultFormula: formula,
  });
  const choiceBody = (name, formula) => ({
    __metadata: { type: 'SP.FieldChoice' }, Title: name, FieldTypeKind: 6,
    Choices: { results: QUARTERS }, FillInChoice: false, DefaultFormula: formula,
  });
  const dateBody = (formula) => ({
    __metadata: { type: 'SP.FieldDateTime' }, Title: DATE_COL, FieldTypeKind: 4,
    DisplayFormat: 0, DefaultFormula: formula,
  });

  // Create with the formula in the body. If that is refused, create without
  // it and MERGE the formula on, so the row says which write path the deploy
  // has to use. Returns { path, create, merge } for the evidence.
  const ensureFormulaField = async (container, body) => {
    const name = body.Title;
    if ((await readField(container, name)).ok) {
      return { path: 'already present', create: null, merge: null };
    }
    let digest = await getDigest();
    const create = await spPost(`${container}/fields`, body, digest, VERBOSE);
    if (create.ok) return { path: 'create carried DefaultFormula', create, merge: null };
    const { DefaultFormula, ...bare } = body;
    digest = await getDigest();
    const bareCreate = await spPost(`${container}/fields`, bare, digest, VERBOSE);
    if (!bareCreate.ok) {
      return { path: 'create refused with and without the formula', create, merge: null };
    }
    digest = await getDigest();
    const merge = await spPost(`${container}/fields/getbyinternalnameortitle('${name}')`,
      { __metadata: { type: 'SP.Field' }, DefaultFormula }, digest, MERGE);
    return { path: 'create bare, then MERGE DefaultFormula', create, merge };
  };

  const recordProperty = async (id, question, container, name, formula, made) => {
    const back = await readField(container, name);
    if (readFailed(back)) {
      record(id, question, 'NOT ESTABLISHED',
             `${made.path}; the field did not read back (HTTP ${back.status})`);
      return false;
    }
    const stored = back.body.DefaultFormula;
    const same = stored === formula;
    const detail = `${made.path}`
      + (made.create && !made.create.ok ? ` (create with formula: ${short(made.create)})` : '')
      + (made.merge ? ` (MERGE: ${short(made.merge)})` : '')
      + `; TypeAsString=${back.body.TypeAsString}; DefaultFormula reads back `
      + `${JSON.stringify(stored === undefined ? null : stored)} (sent ${JSON.stringify(formula)})`;
    if (stored === undefined || stored === null || stored === '') {
      record(id, question, 'PROPERTY DROPPED', detail);
      return false;
    }
    record(id, question, same ? 'READS BACK AS SENT' : 'READS BACK DIFFERENT', detail);
    return true;
  };

  const fillOutcome = (value, expected) => {
    if (value === null || value === undefined || value === '') return 'BLANK';
    return String(value) === String(expected)
      ? 'FILLED, MATCHES BROWSER CLOCK'
      : 'FILLED, DIFFERS FROM BROWSER CLOCK';
  };
  const fillEvidence = (col, value, expected, how) =>
    `${how}; ${col} reads back ${JSON.stringify(value === undefined ? null : value)}`
    + ` (browser clock expects ${JSON.stringify(expected)})`;
  const badOutcome = (value) => {
    if (value === null || value === undefined || value === '') return 'BLANK';
    return QUARTERS.includes(String(value)) ? 'MEMBER STORED' : 'NON-MEMBER STORED';
  };

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
      Description: 'dbml-sharepoint guards probe list. Safe to delete.',
    }, digest);
    record('field.default-formula.fixture-list-created', Q.listFixture,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIST}'` : short(made));
    if (!made.ok) voidAll(LIST_IDS, `fixture incomplete: list creation failed (HTTP ${made.status})`);
  }

  if (RESULTS.find((r) => r.id === 'field.default-formula.fixture-list-created').state === 'settled'
      && RESULTS.find((r) => r.id === LIST_IDS[0]).state !== 'void') {
    // ---- NEGATIVE CONTROL: an item POST naming a missing column ---------
    digest = await getDigest();
    const junk = await spPost(`${listPath}/items`,
      { Title: 'dbmlsp guards control', dbmlspNoSuchColumn: 1 }, digest);
    const controlHeld = !junk.ok && isRefusal(junk.status);
    record('field.default-formula.control-missing-column-refused', Q.listControl,
           controlHeld ? 'PASS' : (junk.ok ? 'FAIL' : 'NOT ESTABLISHED'),
           controlHeld ? `refused with ${short(junk)}`
             : (junk.ok ? 'the item POST naming a missing column was ACCEPTED, so a blank '
                          + 'below cannot be told from a column the server ignored'
                        : `the item POST failed with non-refusal ${short(junk)}`));
    if (!controlHeld) {
      voidAll(LIST_IDS.slice(1),
              `negative control did not hold (HTTP ${junk.status}), so a blank below could `
              + 'not be told from any other server answer');
    } else {
      const madeYear = await ensureFormulaField(listPath, numberBody(YEAR_FORMULA));
      const madeQuarter = await ensureFormulaField(listPath, choiceBody(QUARTER_COL, QUARTER_FORMULA));
      const madeBad = await ensureFormulaField(listPath, choiceBody(BAD_COL, BAD_FORMULA));
      const madeDate = await ensureFormulaField(listPath, dateBody(TODAY_FORMULA));

      const yearOk = await recordProperty('field.default-formula.number-property-reads-back',
        Q.listNumberProp, listPath, YEAR_COL, YEAR_FORMULA, madeYear);
      const quarterOk = await recordProperty('field.default-formula.choice-property-reads-back',
        Q.listChoiceProp, listPath, QUARTER_COL, QUARTER_FORMULA, madeQuarter);
      const badBack = await readField(listPath, BAD_COL);
      const badOk = !readFailed(badBack) && badBack.body.DefaultFormula === BAD_FORMULA;
      const dateBack = await readField(listPath, DATE_COL);
      const dateOk = !readFailed(dateBack) && dateBack.body.DefaultFormula === TODAY_FORMULA;
      log('INFO', `${BAD_COL} formula ${badOk ? 'stored' : 'NOT stored'} (${madeBad.path}); `
                  + `${DATE_COL} formula ${dateOk ? 'stored' : 'NOT stored'} (${madeDate.path}).`);

      // ---- A bare item create: Title only ------------------------------
      digest = await getDigest();
      const row = await spPost(`${listPath}/items`, { Title: 'dbmlsp guards row' }, digest);
      if (!row.ok || !row.body) {
        voidAll(LIST_IDS.slice(3), `the bare item create failed (${short(row)})`);
      } else {
        const back = await spGet(
          `${listPath}/items(${row.body.Id})?$select=Id,${YEAR_COL},${QUARTER_COL},${BAD_COL},${DATE_COL}`);
        if (readFailed(back)) {
          voidAll(LIST_IDS.slice(3), `the created item did not read back (HTTP ${back.status})`);
        } else {
          const how = `POST items with Title only answered HTTP ${row.status}`;
          const d = back.body[DATE_COL];
          const dateFilled = d !== null && d !== undefined && d !== '';
          record('field.default-formula.control-date-fills-on-item-create', Q.listDateFill,
                 dateOk ? (dateFilled ? 'PASS' : 'FAIL') : 'NOT ESTABLISHED',
                 dateOk ? `${how}; ${DATE_COL} reads back ${JSON.stringify(d === undefined ? null : d)}`
                        : `the =TODAY() formula was not stored on ${DATE_COL}, so its fill is unmeasured`);
          record('field.default-formula.number-fills-on-item-create', Q.listNumberFill,
                 yearOk ? fillOutcome(back.body[YEAR_COL], expectYear) : 'NOT ESTABLISHED',
                 yearOk ? fillEvidence(YEAR_COL, back.body[YEAR_COL], expectYear, how)
                        : 'the formula was not stored on the column, so its fill is unmeasured');
          record('field.default-formula.choice-fills-on-item-create', Q.listChoiceFill,
                 quarterOk ? fillOutcome(back.body[QUARTER_COL], expectQuarter) : 'NOT ESTABLISHED',
                 quarterOk ? fillEvidence(QUARTER_COL, back.body[QUARTER_COL], expectQuarter, how)
                           : 'the formula was not stored on the column, so its fill is unmeasured');
          record('field.default-formula.choice-non-member-result', Q.listBad,
                 badOk ? badOutcome(back.body[BAD_COL]) : 'NOT ESTABLISHED',
                 badOk ? `${how}; ${BAD_COL} (formula ${BAD_FORMULA}, choices ${QUARTERS.join('/')}) `
                         + `reads back ${JSON.stringify(back.body[BAD_COL] === undefined ? null : back.body[BAD_COL])}`
                       : 'the non-member formula was not stored on the column, so its result is unmeasured');
        }
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
      Description: 'dbml-sharepoint guards probe library. Safe to delete.',
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
            `negative control did not hold (HTTP ${junkField.status}), so a refusal below could `
            + 'not be told from any other server answer');
    return report();
  }

  const libYear = await ensureFormulaField(libPath, numberBody(YEAR_FORMULA));
  const libQuarter = await ensureFormulaField(libPath, choiceBody(QUARTER_COL, QUARTER_FORMULA));
  const libBad = await ensureFormulaField(libPath, choiceBody(BAD_COL, BAD_FORMULA));
  const libDate = await ensureFormulaField(libPath, dateBody(TODAY_FORMULA));

  const libYearOk = await recordProperty('library.field.default-formula-number-reads-back',
    Q.libNumberProp, libPath, YEAR_COL, YEAR_FORMULA, libYear);
  const libQuarterOk = await recordProperty('library.field.default-formula-choice-reads-back',
    Q.libChoiceProp, libPath, QUARTER_COL, QUARTER_FORMULA, libQuarter);
  const libBadBack = await readField(libPath, BAD_COL);
  const libBadOk = !readFailed(libBadBack) && libBadBack.body.DefaultFormula === BAD_FORMULA;
  const libDateBack = await readField(libPath, DATE_COL);
  const libDateOk = !readFailed(libDateBack) && libDateBack.body.DefaultFormula === TODAY_FORMULA;
  log('INFO', `${BAD_COL} formula ${libBadOk ? 'stored' : 'NOT stored'} (${libBad.path}); `
              + `${DATE_COL} formula ${libDateOk ? 'stored' : 'NOT stored'} (${libDate.path}).`);

  // ---- A bare upload: no metadata ---------------------------------------
  const root = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  const UPLOAD_IDS = LIB_IDS.slice(3, 7);
  if (!folderUrl) {
    voidAll(UPLOAD_IDS, `the library RootFolder did not read back (HTTP ${root.status})`);
  } else {
    digest = await getDigest();
    const up = await rawPost(
      `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE}',overwrite=true)`,
      'dbmlsp guards probe file', digest);
    if (!up.ok) {
      voidAll(UPLOAD_IDS, `Files/add failed (${short(up)})`);
    } else {
      const items = await spGet(
        `${libPath}/items?$select=Id,FileLeafRef,${YEAR_COL},${QUARTER_COL},${BAD_COL},${DATE_COL}&$top=50`);
      const rows = (items.ok && items.body && Array.isArray(items.body.value)) ? items.body.value : [];
      const item = rows.find((r) => r.FileLeafRef === FILE);
      if (!item) {
        voidAll(UPLOAD_IDS, `no list item was found for '${FILE}' after upload (HTTP ${items.status})`);
      } else {
        const how = `Files/add with no metadata answered HTTP ${up.status}`;
        const d = item[DATE_COL];
        const dateFilled = d !== null && d !== undefined && d !== '';
        record('library.field.default-formula-date-fills-on-upload', Q.libDateFill,
               libDateOk ? (dateFilled ? 'FILLED' : 'BLANK') : 'NOT ESTABLISHED',
               libDateOk ? `${how}; ${DATE_COL} reads back ${JSON.stringify(d === undefined ? null : d)}`
                         : `the =TODAY() formula was not stored on ${DATE_COL}, so its fill is unmeasured`);
        record('library.field.default-formula-number-fills-on-upload', Q.libNumberFill,
               libYearOk ? fillOutcome(item[YEAR_COL], expectYear) : 'NOT ESTABLISHED',
               libYearOk ? fillEvidence(YEAR_COL, item[YEAR_COL], expectYear, how)
                         : 'the formula was not stored on the column, so its fill is unmeasured');
        record('library.field.default-formula-choice-fills-on-upload', Q.libChoiceFill,
               libQuarterOk ? fillOutcome(item[QUARTER_COL], expectQuarter) : 'NOT ESTABLISHED',
               libQuarterOk ? fillEvidence(QUARTER_COL, item[QUARTER_COL], expectQuarter, how)
                            : 'the formula was not stored on the column, so its fill is unmeasured');
        record('library.field.default-formula-choice-non-member-on-upload', Q.libBad,
               libBadOk ? badOutcome(item[BAD_COL]) : 'NOT ESTABLISHED',
               libBadOk ? `${how}; ${BAD_COL} (formula ${BAD_FORMULA}, choices ${QUARTERS.join('/')}) `
                          + `reads back ${JSON.stringify(item[BAD_COL] === undefined ? null : item[BAD_COL])}`
                        : 'the non-member formula was not stored on the column, so its result is unmeasured');
      }
    }
  }

  // ---- View Scope as a stored property: on create, and by MERGE ---------
  // Recursive (1) rather than RecursiveAll (2): the nesting probe showed
  // both flatten files, and RecursiveAll adds subfolder rows a grouped view
  // would count.
  const RECURSIVE = 1;
  const readScope = async (title) => {
    const r = await spGet(`${libPath}/views/getbytitle('${title}')?$select=Title,Scope`);
    return (r.ok && r.body) ? r.body.Scope : `(read failed HTTP ${r.status})`;
  };
  const ensureView = async (title, extra) => {
    const have = await spGet(`${libPath}/views/getbytitle('${title}')?$select=Title`);
    if (have.ok) return { ok: true, status: have.status, text: 'already present' };
    digest = await getDigest();
    return spPost(`${libPath}/views`,
      { __metadata: { type: 'SP.View' }, Title: title, PersonalView: false, ...extra },
      digest, VERBOSE);
  };
  const SCOPE_CREATE_VIEW = 'dbmlsp guards scope create';
  const SCOPE_MERGE_VIEW = 'dbmlsp guards scope merge';

  const madeWithScope = await ensureView(SCOPE_CREATE_VIEW, { Scope: RECURSIVE });
  const createScope = madeWithScope.ok ? await readScope(SCOPE_CREATE_VIEW) : null;
  record('library.view.scope-on-create-reads-back', Q.scopeCreate,
         madeWithScope.ok
           ? (createScope === RECURSIVE ? 'STICKS' : 'ACCEPTED BUT DIFFERENT')
           : (isRefusal(madeWithScope.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
         `POST views with Scope ${RECURSIVE} answered ${short(madeWithScope)}; Scope reads back ${JSON.stringify(createScope)}`);

  const madeBare = await ensureView(SCOPE_MERGE_VIEW, {});
  if (!madeBare.ok) {
    record('library.view.scope-on-merge-reads-back', Q.scopeMerge, 'NOT ESTABLISHED',
           `the bare view to MERGE against was not created (${short(madeBare)})`, 'void');
  } else {
    const scopeBefore = await readScope(SCOPE_MERGE_VIEW);
    digest = await getDigest();
    const merged = await spPost(`${libPath}/views/getbytitle('${SCOPE_MERGE_VIEW}')`,
      { __metadata: { type: 'SP.View' }, Scope: RECURSIVE }, digest, MERGE);
    const scopeAfter = await readScope(SCOPE_MERGE_VIEW);
    record('library.view.scope-on-merge-reads-back', Q.scopeMerge,
           merged.ok
             ? (scopeAfter === RECURSIVE ? 'STICKS' : 'ACCEPTED BUT DIFFERENT')
             : (isRefusal(merged.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
           `Scope read ${JSON.stringify(scopeBefore)} before; MERGE Scope ${RECURSIVE} answered ${short(merged)}; `
           + `Scope reads back ${JSON.stringify(scopeAfter)}`);
  }

  // ---- Seal a declared column, then unseal it ---------------------------
  const sealTarget = `${libPath}/fields/getbyinternalnameortitle('${YEAR_COL}')`;
  const before = await readField(libPath, YEAR_COL);
  if (readFailed(before)) {
    voidAll(LIB_IDS.slice(7, 9), `${YEAR_COL} did not read back before sealing (HTTP ${before.status})`);
  } else {
    digest = await getDigest();
    const seal = await spPost(sealTarget, { __metadata: { type: 'SP.Field' }, Sealed: true }, digest, MERGE);
    const afterSeal = await readField(libPath, YEAR_COL);
    const sealedNow = !readFailed(afterSeal) && afterSeal.body.Sealed === true;
    const sealHead = seal.ok
      ? (sealedNow ? 'STICKS' : 'ACCEPTED BUT IGNORED')
      : (isRefusal(seal.status) ? 'REFUSED' : 'NOT ESTABLISHED');
    record('library.column.seal-declared-column-sticks', Q.sealSticks, sealHead,
           `Sealed read ${before.body.Sealed} before; MERGE Sealed:true answered ${short(seal)}; `
           + `Sealed reads back ${readFailed(afterSeal) ? `(read failed HTTP ${afterSeal.status})` : afterSeal.body.Sealed}`
           + (sealHead === 'ACCEPTED BUT IGNORED'
             ? '. This is the shape a generic list gives a SchemaXml seal of its Title '
               + '(field.title.seal-schemaxml): accepted and unchanged'
             : ''));
    if (!sealedNow) {
      record('library.column.seal-declared-column-unseals', Q.sealUnseals, 'NOT ESTABLISHED',
             'the column never read back sealed, so there was nothing to unseal', 'void');
    } else {
      digest = await getDigest();
      const unseal = await spPost(sealTarget, { __metadata: { type: 'SP.Field' }, Sealed: false }, digest, MERGE);
      const afterUnseal = await readField(libPath, YEAR_COL);
      const openNow = !readFailed(afterUnseal) && afterUnseal.body.Sealed === false;
      record('library.column.seal-declared-column-unseals', Q.sealUnseals,
             unseal.ok ? (openNow ? 'UNSEALS' : 'ACCEPTED BUT STILL SEALED')
                       : (isRefusal(unseal.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
             `MERGE Sealed:false answered ${short(unseal)}; Sealed reads back `
             + `${readFailed(afterUnseal) ? `(read failed HTTP ${afterUnseal.status})` : afterUnseal.body.Sealed}`);
    }
  }

  // ---- Switch folder creation off, try a folder, switch it back on ------
  const switchBefore = await spGet(`${libPath}?$select=EnableFolderCreation`);
  const wasEnabled = switchBefore.ok && switchBefore.body ? switchBefore.body.EnableFolderCreation : null;
  digest = await getDigest();
  const off = await spPost(libPath, { __metadata: { type: 'SP.List' }, EnableFolderCreation: false }, digest, MERGE);
  const switchAfter = await spGet(`${libPath}?$select=EnableFolderCreation`);
  const isOff = switchAfter.ok && switchAfter.body && switchAfter.body.EnableFolderCreation === false;
  record('library.doc-lib.folder-creation-disabled-sticks', Q.switchSticks,
         off.ok ? (isOff ? 'STICKS' : 'ACCEPTED BUT IGNORED')
                : (isRefusal(off.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
         `EnableFolderCreation read ${wasEnabled} before; MERGE false answered ${short(off)}; `
         + `reads back ${switchAfter.ok && switchAfter.body ? switchAfter.body.EnableFolderCreation : `(read failed HTTP ${switchAfter.status})`}`);
  if (!isOff || !folderUrl) {
    record('library.folder.creation-blocked-when-disabled', Q.folderBlocked, 'NOT ESTABLISHED',
           isOff ? 'the library RootFolder did not read back, so no folder path to try'
                 : 'the switch never read back false, so the question could not be asked', 'void');
  } else {
    digest = await getDigest();
    const mk = await spPost(
      `web/GetFolderByServerRelativeUrl('${folderUrl}')/folders/add(url='${FOLDER}')`, {}, digest);
    const check = await spGet(`web/GetFolderByServerRelativeUrl('${folderUrl}/${FOLDER}')?$select=Exists`);
    const exists = check.ok && check.body && check.body.Exists === true;
    record('library.folder.creation-blocked-when-disabled', Q.folderBlocked,
           mk.ok ? (exists ? 'ACCEPTED, FOLDER EXISTS' : 'ACCEPTED, FOLDER ABSENT')
                 : (isRefusal(mk.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
           `Folders/add(url='${FOLDER}') with EnableFolderCreation=false answered ${short(mk)}; `
           + `the folder reads back Exists=${check.ok && check.body ? check.body.Exists : `(read failed HTTP ${check.status})`}`
           + (mk.ok
             ? '. The switch does not gate the REST path, so the deploy may set it in any order'
             : '. The deploy must create declared folders BEFORE it switches folder creation off'));
  }
  // Restore, whatever was measured: a probe library left with the command
  // hidden would mislead the next probe that reuses it.
  if (wasEnabled !== false) {
    digest = await getDigest();
    const on = await spPost(libPath, { __metadata: { type: 'SP.List' }, EnableFolderCreation: true }, digest, MERGE);
    const restored = await spGet(`${libPath}?$select=EnableFolderCreation`);
    const backOn = restored.ok && restored.body && restored.body.EnableFolderCreation === true;
    log(backOn ? 'OK' : 'WARN',
        `EnableFolderCreation restored to true: MERGE answered ${short(on)}; reads back `
        + `${restored.ok && restored.body ? restored.body.EnableFolderCreation : '(read failed)'}.`);
  }

  return report();
})();
