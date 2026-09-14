/**
 * dbml-sharepoint PROBE: METADATA COLUMNS AND VALIDATION ON A DOCUMENT LIBRARY
 *
 * QUESTION: A document library stores files alongside metadata columns. Do
 * Choice, Lookup, and Calculated columns behave the same on a library as on a
 * generic list, does a required column enforce during file upload, and does a
 * list ValidationFormula enforce against file metadata?
 *
 * WHY: `document-library-probe.js` established that a fileless POST to /items is
 * refused, and `file-operations-probe.js` settled what a file is over REST.
 * This probe takes the next step into the `library` surface by examining
 * metadata columns and validation rules. It establishes whether the column types
 * dbml-sharepoint emits for generic lists behave identically on document
 * libraries, how required columns interact with file uploads, and whether
 * list-level ValidationFormula rules enforce when metadata is updated.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)? The same
 *        question `document-library-probe.js` and `file-operations-probe.js` ask,
 *        by the same method, keeping the same id per SURFACES.md.
 *   library.column.control-missing-column-refused
 *        NEGATIVE CONTROL: Is a MERGE naming a column that does not exist,
 *        sent to a library file's list item, REFUSED? Establishes that this
 *        probe can detect a failed metadata write on a file item. Without it,
 *        every refusal observed below is unproven.
 *   library.column.choice-column-on-library
 *        Does a choice column behave the same on a library (create the field,
 *        write a value via item MERGE, and read it back)?
 *   library.column.lookup-column-on-library
 *        Does a lookup column behave the same on a library (create the field
 *        pointing to a target list, write a lookup ID, and read it back)?
 *   library.column.calculated-column-on-library
 *        Does a calculated column behave the same on a library (create the
 *        field referencing another column, and read back the calculated value)?
 *   library.column.required-column-enforced-on-upload
 *        Is a required column enforced when a file is uploaded without it?
 *        Observes whether Files/add is refused, or accepted with checkout,
 *        or accepted without checkout.
 *   library.validation.validation-formula-on-library
 *        Does a list ValidationFormula enforce against a library's items
 *        (the file's metadata row), or is it inert on a document library?
 *
 * READ THE CONTROL FIRST. It runs after the fixture library is created and an
 * initial file is uploaded, because a metadata write needs an existing item to
 * address. If a MERGE naming a nonexistent column is ACCEPTED, this probe
 * cannot distinguish a refused write from a successful one, and write-refusal
 * answers are void.
 *
 * RETIRED QUESTION:
 *   library.column.column-default-on-folder
 *   Why retired: Location-based column defaults (defaults per folder) are not
 *   exposed as a writable REST endpoint on SP.Folder or SP.List in the
 *   SharePoint REST API (/_api/). In SharePoint, folder metadata defaults are
 *   managed through the server-side Microsoft.Office.DocumentManagement.MetadataDefaults
 *   API and stored in an internal XML configuration file
 *   (/Forms/client_side_location_based_defaults.html) processed by synchronous
 *   event receivers. Standard SharePoint REST provides no endpoint to set or
 *   cascade folder column defaults. Asking this over REST is unaskable without
 *   reverse-engineering internal XML file placement.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL below is the one Microsoft Learn
 * documents, not one assembled from memory, because a wrong spelling returns
 * 404, `isRefusal` counts 404 as a refusal, and the probe would then print a
 * claim about SharePoint that was really a typo:
 *
 *   List creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Item metadata updates via MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   List ValidationFormula via MERGE to `web/lists/getbytitle(...)`:
 *     "SP.List.validationFormula property (sp.js)", dn531432(v=office.15)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the libraries it created.
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

  log('INFO', 'probe revision 269f2c8e. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibCols';
  const TARGET_LIB = 'dbmlsp Probe LibCols Target';
  const FILE = 'dbmlsp-columns-probe.txt';
  const REQUIRED_FILE = 'dbmlsp-required-probe.txt';
  const listPath = `web/lists/getbytitle('${LIB}')`;
  const targetPath = `web/lists/getbytitle('${TARGET_LIB}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' and TARGET LIST '${TARGET_LIB}' on ${WEB}.`);
    log('INFO', `Would create choice, lookup, and calculated columns on '${LIB}'.`);
    log('INFO', `Would upload test file '${FILE}', send a negative control write, write choice`);
    log('INFO', 'and lookup values, read back calculated values, test required column upload');
    log('INFO', 'enforcement, and test list ValidationFormula enforcement on file metadata.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${TARGET_LIB}' and '${LIB}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: existing lists would be reused.');
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
  expect('library.column.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused');
  expect('library.column.choice-column-on-library', 'Does a choice column behave the same on a document library');
  expect('library.column.lookup-column-on-library', 'Does a lookup column behave the same on a document library');
  expect('library.column.calculated-column-on-library', 'Does a calculated column behave the same on a document library');
  expect('library.column.required-column-enforced-on-upload', 'Is a required column enforced when a file is uploaded without it');
  expect('library.validation.validation-formula-on-library', 'Does a list ValidationFormula enforce against a library items metadata');

  await resetList(TARGET_LIB);
  await resetList(LIB);

  let digest = await getDigest();

  // ---- Bootstrap target list for lookup column ------------------------
  const existingTarget = await spGet(targetPath);
  let targetListId = null;
  if (existingTarget.ok && existingTarget.body) {
    targetListId = existingTarget.body.Id;
  } else {
    digest = await getDigest();
    const madeTarget = await spPost('web/lists', {
      Title: TARGET_LIB,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint target list for library lookup column probe. Safe to delete.',
    }, digest);
    if (madeTarget.ok && madeTarget.body) {
      targetListId = madeTarget.body.Id;
    } else {
      log('WARN', `Could not create target list '${TARGET_LIB}': HTTP ${madeTarget.status}`);
    }
  }

  let targetRowId = null;
  if (targetListId) {
    const targetRows = await spGet(`${targetPath}/items?$select=Id,Title&$top=1`);
    if (targetRows.ok && targetRows.body && Array.isArray(targetRows.body.value) && targetRows.body.value.length > 0) {
      targetRowId = targetRows.body.value[0].Id;
    } else {
      digest = await getDigest();
      const madeRow = await spPost(`${targetPath}/items`, { Title: 'Target Row 1' }, digest);
      if (madeRow.ok && madeRow.body) {
        targetRowId = madeRow.body.Id;
      }
    }
  }

  // ---- fixture-library-created: the library ---------------------------
  const existing = await spGet(listPath);
  if (existing.ok) {
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)', 'ALREADY PRESENT',
           'reusing an existing library. Set CLEANUP = true for a clean answer');
  } else {
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint library-columns probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  const addField = async (schemaXml) => {
    digest = await getDigest();
    return spPost(`${listPath}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };

  const fieldExists = async (name) =>
    (await spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')`)).ok;

  // Each row below is about a column of a PARTICULAR type, and a column of the
  // right name is not that. CLEANUP ships false, so one an earlier run left as
  // another type is the normal path, and the write that follows would read
  // back as that type behaving the same on a library. The whole field is read
  // because `$select` naming a property the entity does not have answers 400.
  const fieldOfType = async (name, typeAsString) => {
    const back = await spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')`);
    const body = (back.ok && back.body) ? back.body : null;
    return {
      body,
      held: body !== null && body.TypeAsString === typeAsString,
      line: body === null
        ? `${name} did not read back (HTTP ${back.status})`
        : `${name} reads back TypeAsString=${body.TypeAsString}, and these rows are about a ${typeAsString} column`,
    };
  };
  // `!body.X` is true both for a property that is unset and for one the site
  // never served, and only the first says the column carries nothing.
  const unset = (body, prop) => prop in body && !body[prop];

  // A null schema means this run had nothing to create the column from.
  const ensureField = async (name, typeAsString, schemaXml) => {
    let sent = schemaXml === null
      ? `${name} could not be created by this run`
      : `${name} was already present, so this run sent no create`;
    if (schemaXml !== null && !(await fieldExists(name))) {
      const made = await addField(schemaXml);
      sent = `the ${name} create answered HTTP ${made.status}`;
    }
    const shape = await fieldOfType(name, typeAsString);
    return { ...shape, line: `${sent}; ${shape.line}` };
  };

  // ---- Choice column setup --------------------------------------------
  const choiceShape = await ensureField('ColChoice', 'Choice',
    '<Field Type="Choice" DisplayName="ColChoice" Name="ColChoice" Format="Dropdown">'
    + '<CHOICES><CHOICE>Alpha</CHOICE><CHOICE>Beta</CHOICE><CHOICE>Gamma</CHOICE></CHOICES>'
    + '<Default>Alpha</Default></Field>');
  const choiceCreated = choiceShape.held;

  // ---- Lookup column setup --------------------------------------------
  const lookupShape = await ensureField('ColLookup', 'Lookup', targetListId
    ? `<Field Type="Lookup" DisplayName="ColLookup" Name="ColLookup"`
      + ` List="{${targetListId}}" ShowField="Title"/>`
    : null);
  const lookupCreated = lookupShape.held;

  // ---- Calculated column setup ----------------------------------------
  const calcShape = await ensureField('ColCalc', 'Calculated',
    '<Field Type="Calculated" DisplayName="ColCalc" Name="ColCalc" ResultType="Text">'
    + '<Formula>=[ColChoice]&amp;" - calc"</Formula>'
    + '<FieldRefs><FieldRef Name="ColChoice"/></FieldRefs></Field>');
  const calcCreated = calcShape.held;

  // ---- Upload initial file for metadata tests -------------------------
  digest = await getDigest();
  const uploadRes = await rawPost(
    `${listPath}/RootFolder/Files/add(url='${FILE}',overwrite=true)`,
    'dbml-sharepoint library columns probe payload',
    digest
  );
  if (!uploadRes.ok) {
    log('FAIL', `Upload of '${FILE}' failed: HTTP ${uploadRes.status}`);
  }

  const items = await spGet(
    `${listPath}/items?$select=Id,Title,FileLeafRef,ColChoice,ColCalc,ColLookupId`
    + `&$filter=FileLeafRef eq '${FILE}'`
  );
  const rows = (items.ok && items.body && Array.isArray(items.body.value)) ? items.body.value : [];
  const row = rows.length ? rows[0] : null;
  const itemId = row ? row.Id : null;

  // ---- control-missing-column-refused: NEGATIVE CONTROL ---------------
  let controlHeld = false;
  if (itemId === null) {
    record('library.column.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused', 'NOT ESTABLISHED',
           `no list item was found for '${FILE}' (HTTP ${items.status}), so there was `
           + 'nothing to send a test write to. Every refusal below this line is '
           + 'unproven rather than answered.');
  } else {
    digest = await getDigest();
    const junk = await spPost(`${listPath}/items(${itemId})`,
                              { NoSuchColumnAtAll: 'x' }, digest,
                              { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }).catch((error) => ({ ok: false, status: 0, text: String(error) }));
    controlHeld = !junk.ok && isRefusal(junk.status);
    record('library.column.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused',
           junk.ok ? 'FAIL' : isRefusal(junk.status) ? 'PASS' : 'NOT ESTABLISHED',
           junk.ok
             ? 'a MERGE naming a column that does not exist was ACCEPTED on a library item. '
               + 'This probe cannot tell a refused metadata write from a successful one, '
               + 'so later refusal answers are void.'
             : isRefusal(junk.status)
               ? `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`
               : `the request failed with HTTP ${junk.status}, which is not the server `
                 + 'refusing the write. The rows depending on this control are '
                 + `unproven rather than answered: ${junk.text.slice(0, 200)}`);
  }

  // ---- choice-column-on-library ---------------------------------------
  if (!choiceCreated || itemId === null) {
    record('library.column.choice-column-on-library', 'Does a choice column behave the same on a document library',
           'VOID', `${choiceShape.line}; file item ${itemId === null ? 'was not found' : `is ${itemId}`}`, 'void');
  } else {
    digest = await getDigest();
    const writeChoice = await spPost(
      `${listPath}/items(${itemId})`,
      { ColChoice: 'Beta' },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    if (!writeChoice.ok) {
      // A refused write answers the question; a 401, 403, 408 or 429 does not,
      // and FAIL would settle the row as the column behaving differently here.
      record('library.column.choice-column-on-library', 'Does a choice column behave the same on a document library',
             isRefusal(writeChoice.status) ? 'FAIL' : 'NOT ESTABLISHED',
             `MERGE with ColChoice="Beta" failed: HTTP ${writeChoice.status} ${writeChoice.text.slice(0, 200)}`);
    } else {
      const readChoice = await spGet(`${listPath}/items(${itemId})?$select=Id,ColChoice`);
      // FAIL is the claim that a choice column behaves differently on a
      // library, and a read that never answered is not that claim's evidence.
      if (readFailed(readChoice)) {
        record('library.column.choice-column-on-library', 'Does a choice column behave the same on a document library',
               'NOT ESTABLISHED',
               `the MERGE answered HTTP ${writeChoice.status}, but item ${itemId} did not read back `
               + `(HTTP ${readChoice.status})`);
      } else {
        const val = readChoice.body.ColChoice;
        record('library.column.choice-column-on-library', 'Does a choice column behave the same on a document library',
               val === 'Beta' ? 'PASS' : 'FAIL',
               val === 'Beta'
                 ? 'choice column created, value written via item MERGE, and read back as written'
                 : `read back unexpected value: ${JSON.stringify(val)} (HTTP ${readChoice.status})`);
      }
    }
  }

  // ---- lookup-column-on-library ---------------------------------------
  if (!lookupCreated || itemId === null || targetRowId === null) {
    record('library.column.lookup-column-on-library', 'Does a lookup column behave the same on a document library',
           'VOID', `lookup column setup incomplete (${lookupShape.line}; itemId=${itemId}, targetRowId=${targetRowId})`, 'void');
  } else {
    digest = await getDigest();
    const writeLookup = await spPost(
      `${listPath}/items(${itemId})`,
      { ColLookupId: targetRowId },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    if (!writeLookup.ok) {
      record('library.column.lookup-column-on-library', 'Does a lookup column behave the same on a document library',
             isRefusal(writeLookup.status) ? 'FAIL' : 'NOT ESTABLISHED',
             `MERGE with ColLookupId=${targetRowId} failed: HTTP ${writeLookup.status} ${writeLookup.text.slice(0, 200)}`);
    } else {
      const readLookup = await spGet(
        `${listPath}/items(${itemId})?$select=Id,ColLookupId`
      );
      if (readFailed(readLookup)) {
        record('library.column.lookup-column-on-library', 'Does a lookup column behave the same on a document library',
               'NOT ESTABLISHED',
               `the MERGE answered HTTP ${writeLookup.status}, but item ${itemId} did not read back `
               + `(HTTP ${readLookup.status})`);
      } else {
        const readId = readLookup.body.ColLookupId;
        record('library.column.lookup-column-on-library', 'Does a lookup column behave the same on a document library',
               readId === targetRowId ? 'PASS' : 'FAIL',
               readId === targetRowId
                 ? `lookup column created, set to target ID ${targetRowId} via item MERGE, and read back as written`
                 : `read back unexpected ColLookupId: ${JSON.stringify(readId)} (HTTP ${readLookup.status})`);
      }
    }
  }

  // ---- calculated-column-on-library -----------------------------------
  if (!calcCreated || itemId === null) {
    record('library.column.calculated-column-on-library', 'Does a calculated column behave the same on a document library',
           'VOID', `${calcShape.line}; file item ${itemId === null ? 'was not found' : `is ${itemId}`}`, 'void');
  } else {
    const readCalc = await spGet(`${listPath}/items(${itemId})?$select=Id,ColChoice,ColCalc`);
    const expectedVal = 'Beta - calc';
    if (readFailed(readCalc)) {
      record('library.column.calculated-column-on-library', 'Does a calculated column behave the same on a document library',
             'NOT ESTABLISHED',
             `item ${itemId} did not read back (HTTP ${readCalc.status}), so no computed value was seen`);
    } else {
      const calcVal = readCalc.body.ColCalc;
      record('library.column.calculated-column-on-library', 'Does a calculated column behave the same on a document library',
             calcVal === expectedVal ? 'PASS' : 'FAIL',
             calcVal === expectedVal
               ? `calculated column evaluated operand [ColChoice] and read back as "${calcVal}"`
               : `calculated column read back "${calcVal}", expected "${expectedVal}" (HTTP ${readCalc.status})`);
    }
  }

  // ---- required-column-enforced-on-upload -----------------------------
  // Required is the whole question, so it is READ BACK off the column rather
  // than taken from the create's status or from a column of that name being
  // present. CLEANUP ships false, so a ColRequired left by an earlier run is
  // the normal path; if it is not required, an accepted upload says nothing.
  // The whole field is read: `$select` naming a property the entity does not
  // have answers HTTP 400, which would read as an absent column.
  //
  // A default and a rule of its own are part of the shape too. The upload
  // sends no metadata, so a column carrying a default is never blank on the
  // file that lands and an accepted upload is not an upload past a required
  // column, while a column rule refuses the same upload for a reason this
  // never asked about. Each is read as served-and-falsy, because a property
  // the site withheld is not a property that is unset.
  let resReq = { ok: true, status: 0 };
  let reqSent = 'ColRequired was already present, so this run sent no create';
  if (!(await fieldExists('ColRequired'))) {
    resReq = await addField(
      '<Field Type="Text" DisplayName="ColRequired" Name="ColRequired" Required="TRUE"/>'
    );
    reqSent = `the ColRequired create answered HTTP ${resReq.status}`;
  }
  const reqBack = await spGet(`${listPath}/fields/getbyinternalnameortitle('ColRequired')`);
  const reqCreated = reqBack.ok && !!reqBack.body && reqBack.body.Required === true
    && unset(reqBack.body, 'DefaultValue') && unset(reqBack.body, 'ValidationFormula');

  if (!reqCreated) {
    record('library.column.required-column-enforced-on-upload', 'Is a required column enforced when a file is uploaded without it',
           'NOT ESTABLISHED',
           `the library carries no blank required column (${reqSent}; `
           + `${reqBack.ok && reqBack.body
             ? `ColRequired reads back TypeAsString=${reqBack.body.TypeAsString} Required=${reqBack.body.Required}`
               + ` DefaultValue=${JSON.stringify(reqBack.body.DefaultValue)}`
               + ` ValidationFormula=${JSON.stringify(reqBack.body.ValidationFormula)}`
             : `ColRequired did not read back, HTTP ${reqBack.status}`}), `
           + 'so an accepted upload is not an upload past a required column.',
           'void');
  } else {
    digest = await getDigest();
    const reqUpload = await rawPost(
      `${listPath}/RootFolder/Files/add(url='${REQUIRED_FILE}',overwrite=true)`,
      'dbml-sharepoint required column upload test',
      digest
    );
    if (!reqUpload.ok) {
      // UPLOAD REFUSED is the finding that a required column blocks a file, so
      // a throttle or an authorization failure must not be able to produce it.
      const refusal = isRefusal(reqUpload.status);
      record('library.column.required-column-enforced-on-upload', 'Is a required column enforced when a file is uploaded without it',
             refusal ? 'UPLOAD REFUSED' : 'NOT ESTABLISHED',
             `Files/add ${refusal ? 'was refused with' : 'failed with'} HTTP ${reqUpload.status}: ${reqUpload.text.slice(0, 260)}`);
    } else {
      const reqItems = await spGet(
        `${listPath}/items?$select=Id,FileLeafRef,ColRequired&$filter=FileLeafRef eq '${REQUIRED_FILE}'`
      );
      const reqRows = (!readFailed(reqItems) && Array.isArray(reqItems.body.value)) ? reqItems.body.value : [];
      const reqRow = reqRows.length ? reqRows[0] : null;
      const fileProps = await spGet(
        `${listPath}/RootFolder/Files('${REQUIRED_FILE}')?$select=CheckOutType,MajorVersion`
      );
      // Both outcome heads below name what the upload left behind, so the
      // property has to be in hand: a 2xx with no payload, and a payload that
      // withheld CheckOutType, both used to read as 'not checked out'.
      const served = !readFailed(fileProps) && 'CheckOutType' in fileProps.body;
      const colLine = readFailed(reqItems)
        ? `the uploaded file's item did not read back (HTTP ${reqItems.status})`
        : reqRow
          ? `ColRequired value is ${JSON.stringify(reqRow.ColRequired)}`
          : 'no list item was served for the uploaded file';
      if (!served) {
        const why = readFailed(fileProps)
          ? `the file's properties did not read back (HTTP ${fileProps.status})`
          : 'the payload carried no CheckOutType property';
        record('library.column.required-column-enforced-on-upload', 'Is a required column enforced when a file is uploaded without it',
               'NOT ESTABLISHED',
               `Files/add succeeded (HTTP ${reqUpload.status}), but ${why}, so what the upload `
               + `left behind was never seen. ${colLine}`);
      } else {
        const checkOutType = fileProps.body.CheckOutType;
        const checkedOut = checkOutType === 0;
        record('library.column.required-column-enforced-on-upload', 'Is a required column enforced when a file is uploaded without it',
               checkedOut ? 'UPLOAD ACCEPTED WITH CHECKOUT' : 'UPLOAD ACCEPTED WITHOUT CHECKOUT',
               `Files/add succeeded (HTTP ${reqUpload.status}). CheckOutType=${checkOutType}`
               + ` (${checkedOut ? 'checked out to author' : 'not checked out'}),`
               + ` ${colLine}`);
      }
    }
  }

  // ---- validation-formula-on-library ----------------------------------
  const RULE = '=[ColChoice]<>"InvalidValue"';
  digest = await getDigest();
  const setRule = await spPost(
    listPath,
    {
      __metadata: { type: 'SP.List' },
      ValidationFormula: RULE,
      ValidationMessage: 'ColChoice cannot be InvalidValue',
    },
    digest,
    {
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    }
  );
  // The rule is read back, because INERT is exactly what a rule that never
  // landed produces: the violating write is accepted, and the row reports
  // that a list ValidationFormula does not enforce on a library. A MERGE
  // answers 204 either way.
  // MEASURED 2026-09-02 (save-instant-paths-probe): SharePoint stores
  // `[DM]<=[Modified]` and reads it back as `DM<=Modified`, so the comparison
  // ignores the brackets, as the deployer's own readback does.
  const canonical = (formula) => String(formula || '').replace(/[[\]]/g, '');
  const ruleBack = await spGet(`${listPath}?$select=ValidationFormula`);
  const ruleStored = setRule.ok && ruleBack.ok && ruleBack.body
    && canonical(ruleBack.body.ValidationFormula) === canonical(RULE);

  if (!ruleStored) {
    record('library.validation.validation-formula-on-library', 'Does a list ValidationFormula enforce against a library items metadata',
           'NOT ESTABLISHED',
           `the library carries no such rule (MERGE answered HTTP ${setRule.status}`
           + `${setRule.ok ? '' : `: ${setRule.text.slice(0, 200)}`}; `
           + `${ruleBack.ok && ruleBack.body
             ? `ValidationFormula reads back ${JSON.stringify(ruleBack.body.ValidationFormula)}`
             : `ValidationFormula did not read back, HTTP ${ruleBack.status}`}), `
           + 'so an accepted violating write would say the rule is inert when there is no rule.',
           'void');
  } else if (itemId === null) {
    record('library.validation.validation-formula-on-library', 'Does a list ValidationFormula enforce against a library items metadata',
           'VOID', 'ValidationFormula was set, but no test file item exists to test enforcement against', 'void');
  } else {
    digest = await getDigest();
    const badWrite = await spPost(
      `${listPath}/items(${itemId})`,
      { ColChoice: 'InvalidValue' },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    const refused = !badWrite.ok && isRefusal(badWrite.status);

    if (refused) {
      digest = await getDigest();
      const goodWrite = await spPost(
        `${listPath}/items(${itemId})`,
        { ColChoice: 'Alpha' },
        digest,
        { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
      );
      record('library.validation.validation-formula-on-library', 'Does a list ValidationFormula enforce against a library items metadata',
             'ENFORCED',
             `violating write refused with HTTP ${badWrite.status} (${badWrite.text.slice(0, 160)});`
             + ` valid write returned HTTP ${goodWrite.status}`);
    } else if (badWrite.ok) {
      record('library.validation.validation-formula-on-library', 'Does a list ValidationFormula enforce against a library items metadata',
             'INERT',
             'the violating write was ACCEPTED; list ValidationFormula does not enforce against library item updates');
    } else {
      record('library.validation.validation-formula-on-library', 'Does a list ValidationFormula enforce against a library items metadata',
             'NOT ESTABLISHED',
             `violating write failed with non-refusal HTTP ${badWrite.status}: ${badWrite.text.slice(0, 200)}`);
    }
  }

  // Keep observations, but a failed control cannot license dependent verdicts.
  if (!controlHeld) {
    for (const id of [
      'library.column.choice-column-on-library',
      'library.column.lookup-column-on-library',
      'library.column.calculated-column-on-library',
      'library.column.required-column-enforced-on-upload',
      'library.validation.validation-formula-on-library',
    ]) {
      const observed = RESULTS.find((result) => result.id === id);
      record(id, observed.question, 'NOT ESTABLISHED',
             `negative control did not hold; observed ${observed.outcome}: ${observed.evidence}`, 'void');
    }
  }

  report();
})();
