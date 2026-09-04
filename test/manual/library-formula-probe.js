/**
 * dbml-sharepoint PROBE: DOCUMENT LIBRARY FORMULA SURFACE
 *
 * REVISION: 1d2bf1e1
 *
 * ONE QUESTION:
 *   Does the formula surface of a document library diverge from a generic list?
 *
 * Round 1 settled what a file, folder, column, and content type are on a library.
 * Round 2 settles how a library interacts with list features. This probe covers the
 * formula half (probe 8 of the document-library programme): calculated columns,
 * datetime sentinels, and validation formulas on a library.
 *
 * The generic-list formula surface is already probed: calculated operands and
 * choice operands (calculated-operand-probe.js, calculated-choice-operand.js),
 * datetime sentinels (datetime-sentinel-probe.js), validation formulas
 * (form-validation-probe.js), and URL operands in validation formulas
 * (hyperlink-validation-operand-probe.js). None of those runs touched a
 * document library. This probe asks the divergence question for three shapes,
 * and does not re-probe the whole formula surface.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101).
 *   library.formula.control-missing-column-refused
 *     NEGATIVE CONTROL: a MERGE naming a column that does not exist, sent to a
 *     library file's list item, is REFUSED. Without it, every refusal observed
 *     below is unproven.
 *   library.formula.calc-datetime-sentinel
 *     Calculated datetime sentinel on a library: does the =NOW()/=TODAY()
 *     sentinel in a calculated column evaluate to a resolved datetime rather
 *     than stay literal or be refused? Microsoft Learn says lists and libraries
 *     do not support the NOW function and that TODAY is not supported in
 *     calculated columns, so a resolved datetime would be the divergence.
 *   library.formula.calc-choice-lookup-operand
 *     Calculated choice/lookup operand on a library: does a calculated column
 *     accept and resolve a Choice or Lookup operand the way a generic list
 *     calculated column does? On a generic list the Choice operand is accepted
 *     and renders, and the Lookup operand is refused at provisioning (recorded
 *     by calculated-choice-operand.js). Each leg is compared to that baseline.
 *   library.formula.validation-url-operand
 *     ValidationFormula naming a URL column on a library: does it enforce on
 *     item metadata writes the way a generic list rule does? library-columns-
 *     probe.js already established that a plain ValidationFormula is enforced
 *     on list-item writes to a library but NOT on Files/add upload. That fact
 *     is not re-probed; this check is only about the URL operand.
 *
 * NOTHING IS RETIRED:
 *   All four checks above are probed directly. The Files/add enforcement fact
 *   was retired before authoring because library-columns-probe.js records it.
 *
 * MICROSOFT LEARN CITATIONS
 *   Calculated column formulas and the unsupported functions:
 *     "Introduction to SharePoint formulas and functions"
 *   Document library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Item metadata updates via MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   List ValidationFormula via MERGE to `web/lists/getbytitle(...)`:
 *     "List object (REST)", dn531146(v=office.15)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the library and the small target list it created.
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

  log('INFO', 'probe revision 1d2bf1e1. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibFormula';
  const TARGET = 'dbmlsp Probe LibFormula Target';
  const FILE = 'dbmlsp-formula-probe.txt';
  const RULE_FILE = 'dbmlsp-formula-url-rule.txt';
  const listPath = `web/lists/getbytitle('${LIB}')`;
  const targetPath = `web/lists/getbytitle('${TARGET}')`;

  // The three columns the checks resolve against, and the four calculated
  // columns that ask the questions. Display names equal internal names so no
  // formula rewrite intervenes.
  const CHOICE = 'dbmlspFChoice';
  const LOOKUP = 'dbmlspFLookup';
  const URLCOL = 'dbmlspFUrl';
  const NOW_CALC = 'dbmlspFNow';
  const TODAY_CALC = 'dbmlspFToday';
  const CHOICE_CALC = 'dbmlspFCalcChoice';
  const LOOKUP_CALC = 'dbmlspFCalcLookup';

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}.`);
    log('INFO', `Would create a small target list '${TARGET}' for the lookup leg,`);
    log('INFO', 'add choice, lookup, URL and calculated columns to the library,');
    log('INFO', 'upload two test files, send a negative control write, and ask');
    log('INFO', 'three formula divergence questions about the library.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' and '${TARGET}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing library would be reused.');
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

  const rawPost = async (path, body, digest, extraHeaders = {}) => {
    try {
      const res = await fetch(`${WEB}/_api/${path}`, {
        method: 'POST',
        headers: {
          Accept: 'application/json;odata=nometadata',
          'X-RequestDigest': digest,
          ...extraHeaders,
        },
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

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.formula.control-missing-column-refused',
         'NEGATIVE CONTROL: a MERGE naming a missing column on a library file item is refused');
  expect('library.formula.calc-datetime-sentinel',
         'Calculated datetime sentinel on a library: does a =NOW()/=TODAY() calculated column resolve to a datetime rather than stay literal');
  expect('library.formula.calc-choice-lookup-operand',
         'Calculated choice/lookup operand on a library: does a calculated column accept and resolve a Choice or Lookup operand the way a generic list does');
  expect('library.formula.validation-url-operand',
         'ValidationFormula naming a URL column on a library: does it enforce on item metadata writes the way a generic list rule does');

  await resetList(TARGET);
  await resetList(LIB);

  let digest = await getDigest();

  // ---- fixture-library-created: the library and its lookup target ------
  // The lookup leg needs a target list with one row, exactly as
  // calculated-choice-operand.js builds '${LIST} Target'.
  const existingTarget = await spGet(targetPath);
  let targetListId = (existingTarget.ok && existingTarget.body) ? existingTarget.body.Id : null;
  let targetRowId = null;
  if (targetListId === null) {
    digest = await getDigest();
    const madeTarget = await spPost('web/lists', {
      Title: TARGET,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint formula probe lookup target. Safe to delete.',
    }, digest);
    if (madeTarget.ok && madeTarget.body) {
      targetListId = madeTarget.body.Id;
      digest = await getDigest();
      const row = await spPost(`${targetPath}/items`, { Title: 'row one' }, digest);
      targetRowId = (row.ok && row.body) ? row.body.Id : null;
    } else {
      log('WARN', `Could not create target list '${TARGET}': HTTP ${madeTarget.status}`);
    }
  } else {
    const rows = await spGet(`${targetPath}/items?$select=Id&$top=1`);
    targetRowId = (rows.ok && rows.body && rows.body.value && rows.body.value[0])
      ? rows.body.value[0].Id
      : null;
  }

  const existing = await spGet(listPath);
  if (existing.ok) {
    record('library.doc-lib.fixture-library-created',
           'A document library is created (BaseTemplate 101)',
           'ALREADY PRESENT',
           'reusing an existing library. Set CLEANUP = true for a clean answer');
  } else {
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint formula probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created',
           'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  // ---- Bootstrap columns and the fixture file -------------------------
  const root = await spGet(`${listPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  if (!folderUrl) {
    log('FAIL', `Could not read RootFolder for '${LIB}': HTTP ${root.status}`);
    for (const id of ['library.formula.control-missing-column-refused',
                      'library.formula.calc-datetime-sentinel',
                      'library.formula.calc-choice-lookup-operand',
                      'library.formula.validation-url-operand']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED',
             `fixture incomplete: library RootFolder did not read back (HTTP ${root.status})`,
             'void');
    }
    return report();
  }

  const addField = async (schemaXml) => {
    digest = await getDigest();
    return spPost(`${listPath}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };
  const fieldExists = async (name) =>
    (await spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')`)).ok;

  const choiceXml =
    `<Field Type="Choice" DisplayName="${CHOICE}" Name="${CHOICE}" Format="Dropdown">` +
    '<CHOICES><CHOICE>Alpha</CHOICE><CHOICE>Beta</CHOICE><CHOICE>Gamma</CHOICE></CHOICES>' +
    '</Field>';
  if (!(await fieldExists(CHOICE))) {
    const colRes = await addField(choiceXml);
    if (!colRes.ok) log('WARN', `Could not add column '${CHOICE}': HTTP ${colRes.status}`);
  }
  if (!(await fieldExists(URLCOL))) {
    const colRes = await addField(
      `<Field Type="URL" DisplayName="${URLCOL}" Name="${URLCOL}" Format="Hyperlink"/>`);
    if (!colRes.ok) log('WARN', `Could not add column '${URLCOL}': HTTP ${colRes.status}`);
  }
  if (targetListId === null) {
    log('WARN', `Lookup column '${LOOKUP}' not added: target list '${TARGET}' is unavailable`);
  } else if (!(await fieldExists(LOOKUP))) {
    // The lookup column targets the web list id read back at bootstrap.
    const colRes = await addField(
      `<Field Type="Lookup" DisplayName="${LOOKUP}" Name="${LOOKUP}" ` +
      `List="{${targetListId}}" ShowField="Title"/>`);
    if (!colRes.ok) log('WARN', `Could not add column '${LOOKUP}': HTTP ${colRes.status}`);
  }

  digest = await getDigest();
  await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE}',overwrite=true)`,
    'dbmlsp formula probe file',
    digest
  );

  const findItem = async (name) => {
    const items = await spGet(`${listPath}/items?$select=Id,FileLeafRef&$top=50`);
    const rows = (items.ok && items.body && Array.isArray(items.body.value))
      ? items.body.value
      : [];
    const match = rows.find((i) => i.FileLeafRef === name);
    return match ? match.Id : null;
  };

  const itemId = await findItem(FILE);
  if (itemId === null) {
    for (const id of ['library.formula.control-missing-column-refused',
                      'library.formula.calc-datetime-sentinel',
                      'library.formula.calc-choice-lookup-operand',
                      'library.formula.validation-url-operand']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED',
             `fixture incomplete: no list item was found for '${FILE}' after upload`,
             'void');
    }
    return report();
  }

  // ---- control-missing-column-refused: NEGATIVE CONTROL ----------------
  digest = await getDigest();
  const junk = await spPost(`${listPath}/items(${itemId})`, { NoSuchFormulaColumn: 'x' }, digest,
                            { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  if (!junk.ok && isRefusal(junk.status)) {
    record('library.formula.control-missing-column-refused',
           'NEGATIVE CONTROL: a MERGE naming a missing column on a library file item is refused',
           'PASS',
           `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`);
  } else {
    record('library.formula.control-missing-column-refused',
           'NEGATIVE CONTROL: a MERGE naming a missing column on a library file item is refused',
           junk.ok ? 'FAIL' : 'NOT ESTABLISHED',
           junk.ok
             ? 'the write naming a missing column was ACCEPTED. This probe cannot '
               + 'detect a refusal, so every row below is unproven'
             : `the write failed with non-refusal HTTP ${junk.status}: ${junk.text.slice(0, 200)}`);
  }

  digest = await getDigest();
  const lookupReady = await fieldExists(LOOKUP);

  // ---- Q1: calculated datetime sentinel --------------------------------
  // Learn: "Lists and libraries do not support the RAND and NOW functions.
  // The TODAY and ME functions are not supported in calculated columns but are
  // supported in the default value setting of a column." A calculated column
  // that resolves =NOW() or =TODAY() to a datetime would contradict that.
  // FieldRefs is empty: the formulas reference no other column.
  const xmlEscape = (s) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
     .replace(/"/g, '&quot;').replace(/'/g, '&apos;');
  const calcXml = (name, formula, refs, resultType) =>
    `<Field Type="Calculated" DisplayName="${xmlEscape(name)}" Name="${xmlEscape(name)}" ` +
    `ResultType="${resultType}">` +
    `<Formula>${xmlEscape(formula)}</Formula>` +
    `<FieldRefs>${refs.map((r) => `<FieldRef Name="${xmlEscape(r)}"/>`).join('')}</FieldRefs>` +
    `</Field>`;

  const createSentinelCalc = async (name, formula) => {
    if (await fieldExists(name)) {
      return { already: true, ok: true, status: 200, text: 'already present from an earlier run' };
    }
    const made = await addField(calcXml(name, formula, [], 'DateTime'));
    return made;
  };

  const nowMade = await createSentinelCalc(NOW_CALC, '=NOW()');
  const todayMade = await createSentinelCalc(TODAY_CALC, '=TODAY()');
  const describeMade = (made) => made.already
    ? 'already present from an earlier run'
    : (made.ok ? `accepted with HTTP ${made.status}` : `refused with HTTP ${made.status}: ${made.text.slice(0, 220)}`);

  // A metadata save forces the calculated columns to recompute on the file's
  // item row. The Choice value is written later, by the operand recalc, so
  // that save is always a real change on a fresh run.
  digest = await getDigest();
  const metaBody = {
    Title: 'dbmlsp formula probe file',
  };
  if (targetRowId !== null && lookupReady) metaBody[`${LOOKUP}Id`] = targetRowId;
  const metaWrite = await spPost(`${listPath}/items(${itemId})`, metaBody, digest,
                                 { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });

  const sentinelRead = metaWrite.ok
    ? await spGet(`${listPath}/items(${itemId})?$select=${NOW_CALC},${TODAY_CALC}`)
    : { ok: false };
  const nowValue = (sentinelRead.ok && sentinelRead.body) ? sentinelRead.body[NOW_CALC] : null;
  const todayValue = (sentinelRead.ok && sentinelRead.body) ? sentinelRead.body[TODAY_CALC] : null;
  const isResolved = (v) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v);

  const nowLeg = nowMade.ok ? (isResolved(nowValue) ? 'resolved' : 'not evaluated') : 'refused';
  const todayLeg = todayMade.ok ? (isResolved(todayValue) ? 'resolved' : 'not evaluated') : 'refused';

  if (!metaWrite.ok) {
    record('library.formula.calc-datetime-sentinel',
           'Calculated datetime sentinel on a library: does a =NOW()/=TODAY() calculated column resolve to a datetime rather than stay literal',
           'NOT ESTABLISHED',
           `the metadata save that would compute the sentinel columns was refused ` +
           `(HTTP ${metaWrite.status}: ${metaWrite.text.slice(0, 200)}). ` +
           `=NOW() column: ${describeMade(nowMade)}; =TODAY() column: ${describeMade(todayMade)}.`);
  } else if (nowMade.ok && todayMade.ok && nowLeg === 'resolved' && todayLeg === 'resolved') {
    record('library.formula.calc-datetime-sentinel',
           'Calculated datetime sentinel on a library: does a =NOW()/=TODAY() calculated column resolve to a datetime rather than stay literal',
           'RESOLVED TO DATETIME',
           `both calculated columns were accepted and computed real datetimes on the file's ` +
           `item row (=NOW() gave ${JSON.stringify(nowValue)}, =TODAY() gave ` +
           `${JSON.stringify(todayValue)}). Learn says NOW is not supported by lists and ` +
           'libraries and TODAY is not supported in calculated columns, so this is the divergence.');
  } else if (!nowMade.ok && !todayMade.ok) {
    record('library.formula.calc-datetime-sentinel',
           'Calculated datetime sentinel on a library: does a =NOW()/=TODAY() calculated column resolve to a datetime rather than stay literal',
           'REFUSED',
           `provisioning refused both sentinel calculated columns: =NOW() ` +
           `${describeMade(nowMade)}; =TODAY() ${describeMade(todayMade)}. This matches ` +
           'Learn and the recorded generic-list behaviour of refusing unsupported formulas at provisioning.');
  } else {
    record('library.formula.calc-datetime-sentinel',
           'Calculated datetime sentinel on a library: does a =NOW()/=TODAY() calculated column resolve to a datetime rather than stay literal',
           'PARTLY RESOLVED',
           `=NOW() leg: ${nowLeg === 'resolved' ? `resolved to ${JSON.stringify(nowValue)}` : describeMade(nowMade)}; ` +
           `=TODAY() leg: ${todayLeg === 'resolved' ? `resolved to ${JSON.stringify(todayValue)}` : describeMade(todayMade)}.`);
  }

  // ---- Q2: calculated choice/lookup operand ----------------------------
  // The generic-list baselines recorded by calculated-choice-operand.js: a
  // Choice operand in a calculated formula is accepted and renders, and a
  // Lookup operand is refused at provisioning. SAME AS LIST is only recorded
  // when both legs match those baselines.
  const choiceCalcMade = (await fieldExists(CHOICE_CALC))
    ? { already: true, ok: true, status: 200, text: '' }
    : await addField(calcXml(CHOICE_CALC, `=[${CHOICE}]&" - c"`, [CHOICE], 'Text'));

  let lookupCalcMade = null;
  if (await fieldExists(LOOKUP_CALC)) {
    lookupCalcMade = { already: true, ok: true, status: 200, text: '' };
  } else if (lookupReady) {
    lookupCalcMade = await addField(calcXml(LOOKUP_CALC, `=[${LOOKUP}]&" x"`, [LOOKUP], 'Text'));
  }

  // Force recalculation now that the operand calculated columns exist. The
  // Choice value flips from blank (or an earlier run's value) to Beta, so the
  // save is a real change and the calculated column has to compute.
  digest = await getDigest();
  const recalc = await spPost(`${listPath}/items(${itemId})`, { [CHOICE]: 'Beta' }, digest,
                              { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  const choiceRead = recalc.ok
    ? await spGet(`${listPath}/items(${itemId})?$select=${CHOICE_CALC}`)
    : { ok: false };
  const choiceValue = (choiceRead.ok && choiceRead.body) ? choiceRead.body[CHOICE_CALC] : null;
  const choiceResolved = choiceCalcMade.ok && choiceValue === 'Beta - c';

  const Q2_EVIDENCE_BASE =
    `choice calc column ${choiceCalcMade.ok
      ? (choiceCalcMade.already ? 'was already present' : `accepted with HTTP ${choiceCalcMade.status}`)
      : `refused with HTTP ${choiceCalcMade.status}: ${choiceCalcMade.text.slice(0, 220)}`}; ` +
    (lookupCalcMade === null
      ? 'lookup leg not asked (no lookup column on the library)'
      : `lookup calc column ${lookupCalcMade.ok
        ? (lookupCalcMade.already ? 'was already present' : `accepted with HTTP ${lookupCalcMade.status}`)
        : `refused with HTTP ${lookupCalcMade.status}: ${lookupCalcMade.text.slice(0, 220)}`}`);

  if (!recalc.ok) {
    record('library.formula.calc-choice-lookup-operand',
           'Calculated choice/lookup operand on a library: does a calculated column accept and resolve a Choice or Lookup operand the way a generic list does',
           'NOT ESTABLISHED',
           `the metadata save that would compute the operand columns was refused ` +
           `(HTTP ${recalc.status}). ${Q2_EVIDENCE_BASE}`);
  } else if (lookupCalcMade === null) {
    record('library.formula.calc-choice-lookup-operand',
           'Calculated choice/lookup operand on a library: does a calculated column accept and resolve a Choice or Lookup operand the way a generic list does',
           'NOT ESTABLISHED',
           `${Q2_EVIDENCE_BASE}; rendered value was ${JSON.stringify(choiceValue)}, ` +
           'but the lookup leg cannot be compared without a lookup column.');
  } else if (!choiceCalcMade.ok) {
    record('library.formula.calc-choice-lookup-operand',
           'Calculated choice/lookup operand on a library: does a calculated column accept and resolve a Choice or Lookup operand the way a generic list does',
           'CHOICE OPERAND REFUSED',
           `${Q2_EVIDENCE_BASE}. On a generic list the same Choice operand formula is ` +
           'accepted and renders (calculated-choice-operand.js, formula.choice.calc-column-accepted), so the library diverges.');
  } else if (!choiceResolved) {
    record('library.formula.calc-choice-lookup-operand',
           'Calculated choice/lookup operand on a library: does a calculated column accept and resolve a Choice or Lookup operand the way a generic list does',
           'CHOICE OPERAND NOT RESOLVED',
           `${Q2_EVIDENCE_BASE}. The calculated column was accepted but rendered ` +
           `${JSON.stringify(choiceValue)} for Choice = Beta, not "Beta - c".`);
  } else if (!lookupCalcMade.ok) {
    record('library.formula.calc-choice-lookup-operand',
           'Calculated choice/lookup operand on a library: does a calculated column accept and resolve a Choice or Lookup operand the way a generic list does',
           'SAME AS LIST',
           `${Q2_EVIDENCE_BASE}. The Choice operand rendered "Beta - c" exactly as a ` +
           'generic list calculated column renders it, and the Lookup operand was refused ' +
           'at provisioning exactly as calculated-choice-operand.js records for a generic list.');
  } else {
    record('library.formula.calc-choice-lookup-operand',
           'Calculated choice/lookup operand on a library: does a calculated column accept and resolve a Choice or Lookup operand the way a generic list does',
           'LOOKUP OPERAND ACCEPTED',
           `${Q2_EVIDENCE_BASE}; the Choice operand rendered ${JSON.stringify(choiceValue)}. ` +
           'On a generic list the Lookup operand in a calculated formula is refused at ' +
           'provisioning (calculated-choice-operand.js, formula.calc.lookup-operand-accepted), ' +
           'so an accepted library lookup formula is the divergence.');
  }

  // ---- Q3: validation URL operand --------------------------------------
  // The rule is set at the library level, the same shape library-columns-probe
  // used. A file uploaded under the rule is expected to be accepted (Files/add
  // ignores ValidationFormula, already recorded) and an item metadata write
  // leaving the URL column blank is expected to be refused.
  const urlRule = '=NOT(ISBLANK([' + URLCOL + ']))';
  digest = await getDigest();
  const setRule = await spPost(
    listPath,
    {
      __metadata: { type: 'SP.List' },
      ValidationFormula: urlRule,
      ValidationMessage: URLCOL + ' is required by the probe rule',
    },
    digest,
    {
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    }
  );

  if (!setRule.ok) {
    record('library.formula.validation-url-operand',
           'ValidationFormula naming a URL column on a library: does it enforce on item metadata writes the way a generic list rule does',
           'URL OPERAND REFUSED AT FIELD-SET',
           `setting the library ValidationFormula naming the URL column was refused ` +
           `(HTTP ${setRule.status}: ${setRule.text.slice(0, 260)}). On a generic list the ` +
           'same list-level formula is accepted (hyperlink-validation-operand-probe.js, ' +
           'formula.validation.url-operand-accepted), so the library diverges.');
  } else {
    digest = await getDigest();
    await rawPost(
      `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${RULE_FILE}',overwrite=true)`,
      'dbmlsp formula url rule file',
      digest
    );
    const ruleItemId = await findItem(RULE_FILE);
    if (ruleItemId === null) {
      record('library.formula.validation-url-operand',
             'ValidationFormula naming a URL column on a library: does it enforce on item metadata writes the way a generic list rule does',
             'NOT ESTABLISHED',
             `the rule was stored but no list item was found for '${RULE_FILE}', so there was ` +
             'nothing to test enforcement against');
    } else {
      digest = await getDigest();
      const violate = await spPost(
        `${listPath}/items(${ruleItemId})`,
        { Title: 'dbmlsp url rule violation' },
        digest,
        { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
      );
      const refused = !violate.ok && isRefusal(violate.status);
      if (!refused) {
        record('library.formula.validation-url-operand',
               'ValidationFormula naming a URL column on a library: does it enforce on item metadata writes the way a generic list rule does',
               'INERT ON ITEM WRITES',
               violate.ok
                 ? 'the violating item write (URL blank) was ACCEPTED, so the URL operand rule '
                   + 'does not enforce on library item writes the way it does on a generic list'
                 : `the violating item write failed with non-refusal HTTP ${violate.status}: ${violate.text.slice(0, 200)}`);
      } else {
        digest = await getDigest();
        const comply = await spPost(
          `${listPath}/items(${ruleItemId})`,
          { [URLCOL]: { Url: 'https://dbmlsp.example.invalid/probe', Description: 'dbmlsp formula probe' } },
          digest,
          { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
        );
        if (comply.ok) {
          record('library.formula.validation-url-operand',
                 'ValidationFormula naming a URL column on a library: does it enforce on item metadata writes the way a generic list rule does',
                 'SAME AS LIST',
                 `the violating write (URL blank) was refused with HTTP ${violate.status} and the ` +
                 'compliant write (URL set) was accepted, exactly as the generic list rule in ' +
                 'hyperlink-validation-operand-probe.js behaves. The rule is enforced on item ' +
                 'metadata writes, and the URL operand is what the rule reads.');
        } else {
          record('library.formula.validation-url-operand',
                 'ValidationFormula naming a URL column on a library: does it enforce on item metadata writes the way a generic list rule does',
                 'REFUSES COMPLIANT WRITES TOO',
                 `the violating write was refused (HTTP ${violate.status}) but the compliant write ` +
                 `was also refused (HTTP ${comply.status}: ${comply.text.slice(0, 200)}), so the rule ` +
                 'fires on everything or the URL value shape was rejected. The URL operand is ' +
                 'accepted at field-set and the rule discriminates on item writes, but a ' +
                 'compliant value could not be demonstrated.');
        }
      }
    }
  }

  report();
})();
