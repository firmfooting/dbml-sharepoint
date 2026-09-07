/**
 * dbml-sharepoint PROBE: DOES A DOCUMENT LIBRARY COLUMN INDEX LIKE A LIST ONE?
 *
 * ONE QUESTION:
 *   `threshold-index-probe.js` established on a GENERIC LIST that a MERGE of
 *   `Indexed: true` is accepted and reads back true, on Text, Choice, Person
 *   and Lookup columns alike. Does the same write, by the same method, do the
 *   same thing on a DOCUMENT LIBRARY, and does it reach the two columns a
 *   library has that a list does not name the same way, `FileLeafRef` (the
 *   Name column) and `Title`?
 *
 * REVISION: ba066b77
 *
 * WHY: `templates/deploy/_indexes.js.j2` asserts `Indexed: true` on every
 * declared indexed column and verifies the write by reading the field back.
 * What it reads back is IDENTITY, not value: its own comment says so, because
 * SharePoint builds the index behind the flag asynchronously and asserting the
 * value there would have been a guess. A library declared with `indexes { }`
 * therefore travels the same phase as a list, and if a library column takes
 * the flag with a 2xx and does not keep it, the deploy reports success and the
 * index does not exist. Nothing downstream of the deploy can see that.
 *
 * THE HAZARD, NAMED. This is the failure class in AGENTS.md: a write that is
 * accepted, reads back clean enough to pass every deploy phase, and does
 * nothing. `caml-chain-depth-probe.js` already found one such property
 * (`ReadOnlyView`) and `list-settings-probe.js` exists to enumerate them on
 * SP.List. This probe asks the same kind of question of one SP.Field property
 * on one container that has never been measured for it.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. A question belongs under `library` when it
 * is about how a document library diverges from a generic list, which is this
 * probe's whole subject, so the measurements file under `library.index.*`.
 * The library-creation row keeps the id five other library probes share.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)? The same
 *        question by the same method as `library-columns-probe.js`,
 *        `file-operations-probe.js`, `folder-probe.js`,
 *        `library-content-type-probe.js` and `library-form-probe.js`, so it
 *        keeps their id.
 *   library.index.fixture-columns-created
 *        Do the three columns this probe indexes exist on the library, and
 *        did the lookup target list they need get built?
 *   library.index.control-description-sticks
 *        POSITIVE CONTROL: does a MERGE of `Description` on a LIBRARY COLUMN
 *        change the column and read back? `Description` is a property the
 *        deployer MERGEs onto fields against live tenants on every run and
 *        verifies by readback (`_field_reconcile.js.j2`), so a Description
 *        MERGE that does not take says the METHOD failed on this container,
 *        not that `Indexed` is special. Every row below is then void rather
 *        than open. The readback is retried ONCE, for the reason
 *        `list-settings-probe.js` records at its own control.
 *   library.index.control-unknown-property-refused
 *        NEGATIVE CONTROL: is a MERGE naming a property SP.Field does not
 *        have refused? Establishes that this probe can tell a refusal from a
 *        success on a library field. Without it a REFUSED row below is not a
 *        finding, so this control voids as well as informs.
 *   library.index.text-column-indexed
 *   library.index.choice-column-indexed
 *   library.index.lookup-column-indexed
 *        Does `Indexed: true` stick on a Text, a Choice and a Lookup column
 *        of a document library, each created by this probe?
 *   library.index.name-column-indexed
 *        Does it stick on `FileLeafRef`, the Name column, which a library has
 *        and a generic list does not?
 *   library.index.title-column-indexed
 *        Does it stick on `Title`, which a library carries from the Document
 *        content type rather than as its own item title?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the scratch library exists; the three
 *   columns exist; a `Description` MERGE on a library column changes it and
 *   reads back, on the first read or on one re-read; a MERGE naming a
 *   property SP.Field does not have is refused.
 *   Observes (recorded, never asserted): for each of the five columns,
 *   whether the MERGE was accepted, what `Indexed` read before the write and
 *   after it, the HTTP status and the error text. NOTHING here asserts that
 *   the flag sticks anywhere. A run where a library refuses every one of them
 *   is a successful run with an important answer, and a probe that asserted
 *   otherwise would kill the experiment the moment it started working.
 *
 * THE MEASUREMENT, per column:
 *   1. Read the field with no `$select`. An unrecognised name in `$select`
 *      errors the WHOLE request, which would read as a permissions problem
 *      rather than as one absent property (`native-index-probe.js`).
 *   2. If it already reads `Indexed: true`, the row records NOT ESTABLISHED
 *      and writes nothing. A readback of true after a write that had nothing
 *      to change is not evidence, and `threshold-index-probe.js` measured
 *      SharePoint auto-indexing a column between two runs, so a column
 *      already carrying the flag is a live possibility rather than a
 *      theoretical one.
 *   3. MERGE `Indexed: true`, then read it back and compare. One re-read,
 *      bounded at one, before an accepted write is called silently ignored.
 *   4. ON A REFUSAL ONLY, retry once with the field's OWN entity type in
 *      `__metadata` instead of the base `SP.Field`, and read back again.
 *      Without this step a type mismatch and a system-column refusal are the
 *      same observation, and the probe would report the first as the second.
 *      The retry is a measurement, not a workaround: if it succeeds, the
 *      finding is that a library column takes the flag only when the MERGE
 *      names its own type.
 *
 * `SP.Field` IS THE BASE TYPE ON PURPOSE for the first attempt, because that
 * is the body `_indexes.js.j2` ships and the body `threshold-index-probe.js`
 * sent on the list side. Sending anything else first would measure a method
 * this project does not use.
 *
 * VERBOSE OData ON EVERY WRITE. `__metadata` is a verbose construct and the
 * harness defaults to `odata=nometadata`, which REJECTS the type hint rather
 * than ignoring it. The threshold probe's first live run failed all four of
 * its index MERGEs exactly this way. `test_a_probe_sending_metadata_uses_
 * verbose_odata` pins it.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL below is the one Microsoft Learn
 * documents, not one assembled from memory, because a wrong spelling returns
 * 404, `isRefusal` counts 404 as a refusal, and the probe would then print a
 * claim about SharePoint that was really a typo:
 *
 *   List and library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Field MERGE via `fields/getbyinternalnameortitle(...)`, and `Indexed`
 *   itself, read/write, "TRUE if the column is indexed for use in view
 *   filters": the same Fields reference.
 *   The index model the flag reports on:
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 *
 * WHAT THIS PROBE DOES NOT ASK, and why the gap is deliberate rather than an
 * omission, is recorded as a finding below.
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the library and the target list it created.
 */
// finding: library-index-threshold-filter-deferred - the heavy half of this
// question, whether an unindexed lookup filter past the 5,000-item threshold
// is refused on a library the way it is on a list, is NOT asked here and
// cannot reuse the list fixture. A library's rows are files:
// `document-library-probe.js` recorded that a fileless POST to a library's
// /items is refused ("To add an item to a document library, use
// SPFileCollection.Add()"), so the 5,614 rows `threshold-index-probe.js` and
// `native-index-probe.js` build with item POSTs are not a library fixture at
// any price. A library-sized equivalent is 5,000+ file uploads and belongs in
// its own gated probe with its own run plan, not bolted onto this one.
// finding: library-index-deploy-verifies-identity-not-value - the shipped
// index phase (`templates/deploy/_indexes.js.j2`) reads each field back after
// the MERGE and compares its Id, deliberately not its `Indexed` value. So a
// container that accepts the flag and drops it passes the deploy silently,
// which is what makes the light half of this question worth asking on its own.
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

  log('INFO', 'probe revision ba066b77. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibIndex';
  const TARGET = 'dbmlsp Probe LibIndex Target';
  const TEXT_COL = 'IdxText';
  const CHOICE_COL = 'IdxChoice';
  const LOOKUP_COL = 'IdxLookup';
  // A name SP.Field does not have, for the negative control. Deliberately not
  // a near-miss of a real property: the control asks whether an unknown name
  // is refused, not whether a typo is tolerated.
  const UNKNOWN_PROPERTY = 'NoSuchFieldPropertyAtAll';
  // How long the one bounded re-read waits. Same figure and same reasoning as
  // list-settings-probe.js: a readback racing a write is a false negative, a
  // retry loop eventually passes anything.
  const REREAD_MS = 1500;

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const listPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const targetPath = `web/lists/getbytitle('${odataName(TARGET)}')`;
  const fieldPath = (name) =>
    `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' and a TARGET LIST '${TARGET}' on ${WEB}.`);
    log('INFO', `Would create ${TEXT_COL}, ${CHOICE_COL} and ${LOOKUP_COL} on the library,`);
    log('INFO', 'MERGE a Description onto one of them as a positive control, MERGE an');
    log('INFO', 'unknown property as a negative control, then MERGE Indexed=true onto');
    log('INFO', `each of those three and onto FileLeafRef and Title, reading each back.`);
    log('INFO', 'No item, file or folder is created. Nothing outside these two lists is touched.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${TARGET}' and '${LIB}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: existing lists would be reused, and a column that already');
      log('INFO', 'reads Indexed=true answers nothing. Set CLEANUP = true for a clean run.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  // The five columns, and the one question each is asked. The table is the
  // only place these ids are written, so the rows registered up front, the
  // rows recorded, and probe-catalog.json cannot drift apart.
  const CANDIDATES = [
    {
      id: 'library.index.text-column-indexed',
      field: TEXT_COL,
      question: 'Does Indexed=true stick on a Text column of a document library',
    },
    {
      id: 'library.index.choice-column-indexed',
      field: CHOICE_COL,
      question: 'Does Indexed=true stick on a Choice column of a document library',
    },
    {
      id: 'library.index.lookup-column-indexed',
      field: LOOKUP_COL,
      question: 'Does Indexed=true stick on a Lookup column of a document library',
    },
    {
      id: 'library.index.name-column-indexed',
      field: 'FileLeafRef',
      question: 'Does Indexed=true stick on FileLeafRef, the Name column of a library',
    },
    {
      id: 'library.index.title-column-indexed',
      field: 'Title',
      question: 'Does Indexed=true stick on Title on a document library',
    },
  ];

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.index.fixture-columns-created', 'The three columns to be indexed exist on the library');
  expect('library.index.control-description-sticks', 'POSITIVE CONTROL: a MERGE of Description on a library column changes it and reads back');
  expect('library.index.control-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused');
  for (const row of CANDIDATES) expect(row.id, row.question);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));

  // No $select, for the reason native-index-probe.js records: one unrecognised
  // name errors the whole request, and every column would then read as
  // unreadable rather than as missing one property.
  const readField = async (name) => spGet(fieldPath(name));

  const mergeField = async (name, body, type) => {
    const digest = await getDigest();
    return spPost(fieldPath(name), { __metadata: { type }, ...body }, digest, {
      Accept: 'application/json;odata=verbose',
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };

  // The entity type SharePoint itself reports for a field, read verbose
  // because nometadata is defined by not carrying it. Only ever consulted
  // after a refusal, to separate a rejected TYPE from a rejected WRITE.
  const entityTypeOf = async (name) => {
    try {
      const res = await fetch(`${WEB}/_api/${fieldPath(name)}`, {
        headers: { Accept: 'application/json;odata=verbose' },
      });
      if (!res.ok) return null;
      const body = await res.json().catch(() => null);
      return (body && body.d && body.d.__metadata && body.d.__metadata.type) || null;
    } catch {
      return null;
    }
  };

  const indexedNow = (read) => !readFailed(read) && read.body.Indexed === true;

  await resetList(TARGET);
  await resetList(LIB);

  // ---- fixture-library-created ----------------------------------------
  let digest = await getDigest();
  const existing = await spGet(listPath);
  let libraryReady = false;
  if (existing.ok) {
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
           'ALREADY PRESENT',
           `reusing an existing '${LIB}'. Its columns may carry an earlier run's `
           + 'index flags. Set CLEANUP = true for a clean answer');
    libraryReady = true;
  } else {
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint library-index probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    libraryReady = made.ok;
  }

  const abortEverything = (reason) => {
    record('library.index.fixture-columns-created', 'The three columns to be indexed exist on the library',
           'ABORTED', reason);
    record('library.index.control-description-sticks', 'POSITIVE CONTROL: a MERGE of Description on a library column changes it and reads back',
           'ABORTED', reason);
    record('library.index.control-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused',
           'ABORTED', reason);
    for (const row of CANDIDATES) record(row.id, row.question, 'ABORTED', reason);
    return report();
  };

  if (!libraryReady) {
    return abortEverything('the scratch library was never created, so nothing could be written to it');
  }

  // ---- fixture-columns-created -----------------------------------------
  // The lookup target is a generic list, because a lookup needs rows and a
  // library's rows are files. It carries no answer of its own; it exists so
  // the lookup column has somewhere to point.
  let targetId = null;
  const foundTarget = await spGet(targetPath);
  if (foundTarget.ok && foundTarget.body) {
    targetId = foundTarget.body.Id;
  } else {
    digest = await getDigest();
    const madeTarget = await spPost('web/lists', {
      Title: TARGET,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint library-index probe lookup target. Safe to delete.',
    }, digest);
    if (madeTarget.ok && madeTarget.body) targetId = madeTarget.body.Id;
  }

  const addField = async (schemaXml) => {
    digest = await getDigest();
    return spPost(`${listPath}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };

  const ensureField = async (name, schemaXml) => {
    if (!readFailed(await readField(name))) return { made: true, note: `${name} already present` };
    const created = await addField(schemaXml);
    return {
      made: created.ok,
      note: created.ok ? `${name} created`
        : `${name} FAILED HTTP ${created.status}: ${created.text.slice(0, 160)}`,
    };
  };

  const built = [];
  built.push(await ensureField(TEXT_COL,
    `<Field Type="Text" DisplayName="${TEXT_COL}" Name="${TEXT_COL}" MaxLength="255"/>`));
  built.push(await ensureField(CHOICE_COL,
    `<Field Type="Choice" DisplayName="${CHOICE_COL}" Name="${CHOICE_COL}" Format="Dropdown">`
    + '<CHOICES><CHOICE>Alpha</CHOICE><CHOICE>Beta</CHOICE></CHOICES></Field>'));
  if (targetId) {
    built.push(await ensureField(LOOKUP_COL,
      `<Field Type="Lookup" DisplayName="${LOOKUP_COL}" Name="${LOOKUP_COL}"`
      + ` List="{${targetId}}" ShowField="Title"/>`));
  } else {
    built.push({ made: false, note: `${LOOKUP_COL} FAILED: the lookup target list was not created` });
  }
  const notes = built.map((entry) => entry.note).join('; ');
  const columnsReady = built.every((entry) => entry.made);
  record('library.index.fixture-columns-created', 'The three columns to be indexed exist on the library',
         columnsReady ? 'PASS' : 'FAIL', notes);

  if (!(await readField(TEXT_COL)).ok) {
    return abortEverything(
      `${TEXT_COL} does not exist, and both controls are measured on it, so the `
      + 'method could not be established and no index write was attempted: ' + notes);
  }

  // ---- POSITIVE CONTROL: does a field MERGE take at all on a library? ----
  // Description, because the deployer MERGEs it onto fields against live
  // tenants on every run and verifies it by readback. A Description MERGE
  // that does not take says the method failed on this container, which is a
  // different statement from "Indexed does not stick here".
  const marker = `dbmlsp library-index probe-control-${Date.now()}`;
  const setDesc = await mergeField(TEXT_COL, { Description: marker }, 'SP.Field');
  let readDesc = await readField(TEXT_COL);
  const holdsMarker = (read) => !readFailed(read) && read.body.Description === marker;
  let controlReRead = false;
  if (setDesc.ok && !holdsMarker(readDesc)) {
    await sleep(REREAD_MS);
    readDesc = await readField(TEXT_COL);
    controlReRead = true;
  }
  const methodHolds = setDesc.ok && holdsMarker(readDesc);
  record('library.index.control-description-sticks', 'POSITIVE CONTROL: a MERGE of Description on a library column changes it and reads back',
         methodHolds ? 'PASS' : 'CONTROL FAILED, METHOD VOID',
         methodHolds
           ? `Description MERGE on ${TEXT_COL} returned HTTP ${setDesc.status} and read back byte-identical`
             + (controlReRead ? `, after one re-read ${REREAD_MS} ms later` : '')
           : `MERGE HTTP ${setDesc.status}${setDesc.ok ? '' : `: ${setDesc.text.slice(0, 200)}`}; `
             + `readback ${readFailed(readDesc) ? `failed HTTP ${readDesc.status}` : show(readDesc.body.Description)}`
             + (controlReRead ? `, still differing ${REREAD_MS} ms later` : '')
             + `; the marker written was ${show(marker)}`);

  // ---- NEGATIVE CONTROL: is an unknown property refused? -----------------
  const unknown = await mergeField(TEXT_COL, { [UNKNOWN_PROPERTY]: 'x' }, 'SP.Field');
  const refusalDetectable = !unknown.ok && isRefusal(unknown.status);
  record('library.index.control-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused',
         unknown.ok ? 'CONTROL FAILED, METHOD VOID'
           : refusalDetectable ? 'REFUSED' : 'CONTROL FAILED, METHOD VOID',
         unknown.ok
           ? `a MERGE setting '${UNKNOWN_PROPERTY}' on ${TEXT_COL} returned HTTP ${unknown.status}. `
             + 'This probe cannot tell a refused field write from an accepted one, so no '
             + 'refusal below would be a finding.'
           : refusalDetectable
             ? `HTTP ${unknown.status}: ${unknown.text.slice(0, 240)}`
             : `the request failed with HTTP ${unknown.status}, which is about who is asking or `
               + `about the moment, not the server refusing the content: ${unknown.text.slice(0, 200)}`);

  // ---- The five measurements --------------------------------------------
  // Both controls must hold. The positive one says a field MERGE reaches this
  // container at all; the negative one says an accepted write and a refused
  // write are distinguishable. Without either, an outcome here is a reading of
  // the probe rather than of SharePoint, and this repository fails closed.
  const controlsHold = methodHolds && refusalDetectable;
  const voidReason = methodHolds
    ? 'the negative control did not refuse, so a refusal here could not be told from a failure'
    : 'the positive control did not read back, so a field MERGE was never shown to reach this library';

  for (const row of CANDIDATES) {
    if (!controlsHold) {
      record(row.id, row.question, 'VOID', voidReason, 'void');
      continue;
    }
    const before = await readField(row.field);
    if (readFailed(before) || typeof before.body.Indexed !== 'boolean') {
      record(row.id, row.question, 'NOT ESTABLISHED',
             `${row.field} could not be read as a field carrying an Indexed property `
             + `(HTTP ${before.status}), so nothing was written to it`);
      continue;
    }
    if (before.body.Indexed === true) {
      record(row.id, row.question, 'NOT ESTABLISHED',
             `${row.field} already read Indexed=true before this run wrote anything, so a `
             + 'readback of true would say nothing about the write. threshold-index-probe.js '
             + 'measured SharePoint indexing a column on its own between two runs, so this is '
             + 'a live possibility. Re-run with CLEANUP = true.');
      continue;
    }

    const wrote = await mergeField(row.field, { Indexed: true }, 'SP.Field');
    let after = await readField(row.field);
    let reRead = false;
    if (wrote.ok && !indexedNow(after)) {
      await sleep(REREAD_MS);
      after = await readField(row.field);
      reRead = true;
    }

    if (wrote.ok) {
      const stuck = indexedNow(after);
      record(row.id, row.question, stuck ? 'INDEXED' : 'SILENTLY IGNORED',
             `MERGE Indexed:true as SP.Field returned HTTP ${wrote.status}; `
             + `Indexed read false before and `
             + `${readFailed(after) ? `unreadable after (HTTP ${after.status})` : show(after.body.Indexed)} after`
             + (reRead ? `, on a re-read ${REREAD_MS} ms later` : '')
             + (stuck ? '' : '. The write was accepted and changed nothing, which is the '
               + 'failure class this probe exists to find'));
      continue;
    }

    if (!isRefusal(wrote.status)) {
      record(row.id, row.question, 'NOT ESTABLISHED',
             `the MERGE failed with HTTP ${wrote.status}, which is about who is asking or about `
             + `the moment rather than the server refusing it: ${wrote.text.slice(0, 200)}`);
      continue;
    }

    // Refused as SP.Field. Ask once more with the type SharePoint itself
    // reports for this field, because a rejected type hint and a rejected
    // write are otherwise the same observation.
    const ownType = await entityTypeOf(row.field);
    const retried = ownType && ownType !== 'SP.Field'
      ? await mergeField(row.field, { Indexed: true }, ownType)
      : null;
    const afterRetry = retried && retried.ok ? await readField(row.field) : null;
    const retryStuck = afterRetry !== null && indexedNow(afterRetry);
    const asBase = `MERGE Indexed:true as SP.Field was REFUSED, HTTP ${wrote.status}: `
      + wrote.text.slice(0, 240);
    if (retryStuck) {
      record(row.id, row.question, 'INDEXED',
             `${asBase}. Retried naming the type SharePoint reports for this field, `
             + `${ownType}: HTTP ${retried.status}, and Indexed read back true. The refusal was `
             + 'the TYPE HINT, not the column. Note the deployer sends SP.Field.');
    } else {
      record(row.id, row.question, 'REFUSED',
             `${asBase}. `
             + (retried === null
               ? (ownType === null
                 ? 'The field entity type could not be read, so a type mismatch was not ruled out.'
                 : `SharePoint reports this field as ${ownType}, the same base type, so there was `
                   + 'no type mismatch to rule out.')
               : `Retried as ${ownType}: HTTP ${retried.status}`
                 + (retried.ok
                   ? `, and Indexed read back `
                     + `${afterRetry && !readFailed(afterRetry) ? show(afterRetry.body.Indexed) : 'unreadable'}`
                   : `: ${retried.text.slice(0, 160)}`)
                 + '. The refusal is the column, not the type hint.'));
    }
  }

  report();
})();
