/**
 * dbml-sharepoint PROBE: DOCUMENT LIBRARY COLUMN INTERACTIONS
 *
 * REVISION: 9c5ee9ae
 *
 * ONE QUESTION:
 *   How do multi-value columns and custom column formatting behave on a document library?
 *
 * Round 1 settled what a file, folder, column, and content type are on a library.
 * Round 2 settles how a library interacts with the list features a first-class
 * `kind: DocumentLibrary` must co-operate with. This probe covers the column
 * half: multi-value columns and custom column formatting.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101).
 *   library.column.control-missing-column-refused
 *     NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused.
 *   library.column.multi-choice-column-on-library
 *     Does a multi-value choice column work on a document library?
 *   library.column.multi-lookup-column-on-library
 *     Does a multi-value lookup column work on a document library?
 *   library.column.custom-column-formatting
 *     Can a column on a document library carry JSON column formatting?
 *
 * MICROSOFT LEARN CITATIONS
 *   Document library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Multi-choice and Multi-lookup fields in CAML:
 *     "Field Element (List)"
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Item metadata updates via MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   Column formatting:
 *     "Use column formatting to customize SharePoint"
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
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT'];
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

  log('INFO', 'probe revision 9c5ee9ae. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibColInteractions';
  const TARGET_LIB = 'dbmlsp Probe LibColTarget';
  const FILE = 'dbmlsp-col-interactions-doc.txt';
  const listPath = `web/lists/getbytitle('${LIB}')`;
  const targetPath = `web/lists/getbytitle('${TARGET_LIB}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' and TARGET LIST '${TARGET_LIB}' on ${WEB}.`);
    log('INFO', `Would create multi-choice, multi-lookup, and formatting columns on '${LIB}'.`);
    log('INFO', `Would upload test file '${FILE}', send a negative control write, write multi-choice`);
    log('INFO', 'and multi-lookup values, read them back, and write and read back JSON column formatting.');
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

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.column.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused');
  expect('library.column.multi-choice-column-on-library', 'Does a multi-value choice column work on a document library');
  expect('library.column.multi-lookup-column-on-library', 'Does a multi-value lookup column work on a document library');
  expect('library.column.custom-column-formatting', 'Can a column on a document library carry JSON column formatting');

  await resetList(TARGET_LIB);
  await resetList(LIB);

  let digest = await getDigest();

  // ---- Bootstrap target list for multi-lookup column ------------------
  const existingTarget = await spGet(targetPath);
  let targetListId = null;
  if (existingTarget.ok && existingTarget.body) {
    targetListId = existingTarget.body.Id;
  } else {
    digest = await getDigest();
    const madeTarget = await spPost('web/lists', {
      Title: TARGET_LIB,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint target list for library multi-lookup column probe. Safe to delete.',
    }, digest);
    if (madeTarget.ok && madeTarget.body) {
      targetListId = madeTarget.body.Id;
    } else {
      log('WARN', `Could not create target list '${TARGET_LIB}': HTTP ${madeTarget.status}`);
    }
  }

  const targetRowIds = [];
  if (targetListId) {
    const targetRows = await spGet(`${targetPath}/items?$select=Id,Title&$top=2`);
    if (targetRows.ok && targetRows.body && Array.isArray(targetRows.body.value)) {
      for (const row of targetRows.body.value) {
        targetRowIds.push(row.Id);
      }
    }
    while (targetRowIds.length < 2) {
      digest = await getDigest();
      const madeRow = await spPost(
        `${targetPath}/items`,
        { Title: `Target Row ${targetRowIds.length + 1}` },
        digest
      );
      if (madeRow.ok && madeRow.body) {
        targetRowIds.push(madeRow.body.Id);
      } else {
        log('WARN', `Could not create target row: HTTP ${madeRow.status}`);
        break;
      }
    }
  }

  // ---- fixture-library-created: the library ---------------------------
  const existing = await spGet(listPath);
  if (existing.ok) {
    record(
      'library.doc-lib.fixture-library-created',
      'A document library is created (BaseTemplate 101)',
      'ALREADY PRESENT',
      'reusing an existing library. Set CLEANUP = true for a clean answer'
    );
  } else {
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint library-column-interactions probe library. Safe to delete.',
    }, digest);
    record(
      'library.doc-lib.fixture-library-created',
      'A document library is created (BaseTemplate 101)',
      made.ok ? 'PASS' : 'FAIL',
      made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`
    );
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

  // ---- Multi-choice column setup --------------------------------------
  let multiChoiceCreated = false;
  if (!(await fieldExists('ColMultiChoice'))) {
    const resMultiChoice = await addField(
      '<Field Type="MultiChoice" DisplayName="ColMultiChoice" Name="ColMultiChoice">'
      + '<CHOICES><CHOICE>Alpha</CHOICE><CHOICE>Beta</CHOICE><CHOICE>Gamma</CHOICE></CHOICES>'
      + '<Default>Alpha</Default></Field>'
    );
    multiChoiceCreated = resMultiChoice.ok;
  } else {
    multiChoiceCreated = true;
  }

  // ---- Multi-lookup column setup --------------------------------------
  let multiLookupCreated = false;
  if (targetListId && !(await fieldExists('ColMultiLookup'))) {
    const resMultiLookup = await addField(
      `<Field Type="LookupMulti" Mult="TRUE" DisplayName="ColMultiLookup" Name="ColMultiLookup"`
      + ` List="{${targetListId}}" ShowField="Title"/>`
    );
    multiLookupCreated = resMultiLookup.ok;
  } else if (targetListId) {
    multiLookupCreated = true;
  }

  // ---- Formatted column setup -----------------------------------------
  let formatColCreated = false;
  if (!(await fieldExists('ColFormat'))) {
    const resFormat = await addField(
      '<Field Type="Text" DisplayName="ColFormat" Name="ColFormat" MaxLength="255"/>'
    );
    formatColCreated = resFormat.ok;
  } else {
    formatColCreated = true;
  }

  // ---- Upload initial file for metadata tests -------------------------
  digest = await getDigest();
  const uploadRes = await rawPost(
    `${listPath}/RootFolder/Files/add(url='${FILE}',overwrite=true)`,
    'dbml-sharepoint library column interactions probe payload',
    digest
  );
  if (!uploadRes.ok) {
    log('FAIL', `Upload of '${FILE}' failed: HTTP ${uploadRes.status}`);
  }

  const items = await spGet(
    `${listPath}/items?$select=Id,Title,FileLeafRef,ColMultiChoice,ColMultiLookupId,ColFormat`
    + `&$filter=FileLeafRef eq '${FILE}'`
  );
  const rows = (items.ok && items.body && Array.isArray(items.body.value)) ? items.body.value : [];
  const row = rows.length ? rows[0] : null;
  const itemId = row ? row.Id : null;

  // ---- control-missing-column-refused: NEGATIVE CONTROL ---------------
  let controlHeld = false;
  if (itemId === null) {
    record(
      'library.column.control-missing-column-refused',
      'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused',
      'NOT ESTABLISHED',
      `no list item was found for '${FILE}' (HTTP ${items.status}), so there was `
      + 'nothing to send a test write to. Every refusal below this line is '
      + 'unproven rather than answered.'
    );
  } else {
    digest = await getDigest();
    const junk = await spPost(
      `${listPath}/items(${itemId})`,
      { NoSuchColumnAtAll: 'x' },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    controlHeld = !junk.ok && isRefusal(junk.status);
    record(
      'library.column.control-missing-column-refused',
      'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused',
      junk.ok ? 'FAIL' : isRefusal(junk.status) ? 'PASS' : 'NOT ESTABLISHED',
      junk.ok
        ? 'a MERGE naming a column that does not exist was ACCEPTED on a library item. '
          + 'This probe cannot tell a refused metadata write from a successful one, '
          + 'so later refusal answers are void.'
        : isRefusal(junk.status)
          ? `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`
          : `the request failed with HTTP ${junk.status}, which is not the server `
            + 'refusing the write. The rows depending on this control are '
            + `unproven rather than answered: ${junk.text.slice(0, 200)}`
    );
  }

  // ---- multi-choice-column-on-library ---------------------------------
  if (!multiChoiceCreated || itemId === null) {
    record(
      'library.column.multi-choice-column-on-library',
      'Does a multi-value choice column work on a document library',
      multiChoiceCreated ? 'NOT ESTABLISHED' : 'FAIL',
      multiChoiceCreated
        ? 'multi-choice column was created, but no file item was available to test'
        : 'multi-choice column could not be created'
    );
  } else {
    digest = await getDigest();
    const choiceValues = ['Alpha', 'Beta'];
    let writeRes = await spPost(
      `${listPath}/items(${itemId})`,
      { ColMultiChoice: choiceValues },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    if (!writeRes.ok) {
      digest = await getDigest();
      const fallbackRes = await spPost(
        `${listPath}/items(${itemId})`,
        { ColMultiChoice: { results: choiceValues } },
        digest,
        { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
      );
      if (fallbackRes.ok) {
        writeRes = fallbackRes;
      }
    }

    if (!writeRes.ok) {
      record(
        'library.column.multi-choice-column-on-library',
        'Does a multi-value choice column work on a document library',
        isRefusal(writeRes.status) ? 'FAIL' : 'NOT ESTABLISHED',
        `write failed with HTTP ${writeRes.status}: ${writeRes.text.slice(0, 300)}`
      );
    } else {
      const readRes = await spGet(`${listPath}/items(${itemId})?$select=ColMultiChoice`);
      const val = (readRes.ok && readRes.body) ? readRes.body.ColMultiChoice : null;
      const actualValues = Array.isArray(val)
        ? val
        : (val && Array.isArray(val.results))
          ? val.results
          : null;
      const matches = actualValues !== null
        && actualValues.length === choiceValues.length
        && choiceValues.every((v) => actualValues.includes(v));
      record(
        'library.column.multi-choice-column-on-library',
        'Does a multi-value choice column work on a document library',
        matches ? 'PASS' : 'FAIL',
        matches
          ? `successfully updated and read back ColMultiChoice=${JSON.stringify(actualValues)} on library item`
          : `read back ${JSON.stringify(val)}, expected ${JSON.stringify(choiceValues)} (read HTTP ${readRes.status})`
      );
    }
  }

  // ---- multi-lookup-column-on-library ---------------------------------
  if (!multiLookupCreated || itemId === null || targetRowIds.length < 2) {
    record(
      'library.column.multi-lookup-column-on-library',
      'Does a multi-value lookup column work on a document library',
      multiLookupCreated && itemId !== null ? 'NOT ESTABLISHED' : 'FAIL',
      !multiLookupCreated
        ? 'multi-lookup column could not be created'
        : itemId === null
          ? 'multi-lookup column was created, but no file item was available to test'
          : `target list only has ${targetRowIds.length} item(s), need at least 2 to test multi-lookup`
    );
  } else {
    digest = await getDigest();
    let writeRes = await spPost(
      `${listPath}/items(${itemId})`,
      { ColMultiLookupId: targetRowIds },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    if (!writeRes.ok) {
      digest = await getDigest();
      const fallbackRes = await spPost(
        `${listPath}/items(${itemId})`,
        { ColMultiLookupId: { results: targetRowIds } },
        digest,
        { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
      );
      if (fallbackRes.ok) {
        writeRes = fallbackRes;
      }
    }

    if (!writeRes.ok) {
      record(
        'library.column.multi-lookup-column-on-library',
        'Does a multi-value lookup column work on a document library',
        isRefusal(writeRes.status) ? 'FAIL' : 'NOT ESTABLISHED',
        `write failed with HTTP ${writeRes.status}: ${writeRes.text.slice(0, 300)}`
      );
    } else {
      const readRes = await spGet(`${listPath}/items(${itemId})?$select=ColMultiLookupId`);
      const val = (readRes.ok && readRes.body) ? readRes.body.ColMultiLookupId : null;
      const actualIds = Array.isArray(val)
        ? val
        : (val && Array.isArray(val.results))
          ? val.results
          : null;
      const matches = actualIds !== null
        && actualIds.length === targetRowIds.length
        && targetRowIds.every((id) => actualIds.includes(id));
      record(
        'library.column.multi-lookup-column-on-library',
        'Does a multi-value lookup column work on a document library',
        matches ? 'PASS' : 'FAIL',
        matches
          ? `successfully updated and read back ColMultiLookupId=${JSON.stringify(actualIds)} on library item`
          : `read back ${JSON.stringify(val)}, expected ${JSON.stringify(targetRowIds)} (read HTTP ${readRes.status})`
      );
    }
  }

  // ---- custom-column-formatting ---------------------------------------
  if (!formatColCreated) {
    record(
      'library.column.custom-column-formatting',
      'Can a column on a document library carry JSON column formatting',
      'FAIL',
      'ColFormat column could not be created'
    );
  } else {
    digest = await getDigest();
    const sampleFormatter = JSON.stringify({
      $schema: 'https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json',
      elmType: 'div',
      txtContent: '@currentField',
    });
    const writeFmtRes = await spPost(
      `${listPath}/fields/getbyinternalnameortitle('ColFormat')`,
      { CustomFormatter: sampleFormatter },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    if (!writeFmtRes.ok) {
      record(
        'library.column.custom-column-formatting',
        'Can a column on a document library carry JSON column formatting',
        isRefusal(writeFmtRes.status) ? 'FAIL' : 'NOT ESTABLISHED',
        `write failed with HTTP ${writeFmtRes.status}: ${writeFmtRes.text.slice(0, 300)}`
      );
    } else {
      const readFmtRes = await spGet(
        `${listPath}/fields/getbyinternalnameortitle('ColFormat')?$select=CustomFormatter`
      );
      const backFmt = (readFmtRes.ok && readFmtRes.body) ? readFmtRes.body.CustomFormatter : null;
      let matches = false;
      if (typeof backFmt === 'string') {
        try {
          matches = canonicalJson(backFmt) === canonicalJson(sampleFormatter);
        } catch {
          matches = backFmt === sampleFormatter;
        }
      }
      record(
        'library.column.custom-column-formatting',
        'Can a column on a document library carry JSON column formatting',
        matches ? 'PASS' : 'FAIL',
        matches
          ? "successfully wrote and read back CustomFormatter on library column 'ColFormat'"
          : `read back ${JSON.stringify(backFmt)}, expected ${JSON.stringify(sampleFormatter)} (read HTTP ${readFmtRes.status})`
      );
    }
  }

  report();
})();
