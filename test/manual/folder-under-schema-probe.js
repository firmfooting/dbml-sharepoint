/**
 * dbml-sharepoint PROBE: WHICH DECLARED SETTING REFUSES A FOLDER
 *
 * REVISION: f31aa573
 *
 * ONE QUESTION:
 *   folders/add is accepted on a bare library and refused on one the deploy
 *   has finished configuring. Which of the settings applied in between is
 *   responsible?
 *
 * folder-create-refusal-probe.js settled that the call itself is sound: a
 * spaced folder name on a library created with ContentTypesEnabled false,
 * which is exactly what the deploy sends, answered HTTP 200 and read back.
 * On a live deploy the same call answered HTTP 500 "Cannot create folder"
 * for all four declared folders. So the cause is not the call and not the
 * name; it is something the run does to the library before Phase 2.2.
 *
 * A folder is a list ITEM (FileSystemObjectType 1). Everything the deploy
 * applies to the library between creating it and creating its folders is
 * therefore something that item may have to satisfy:
 *
 *   1. Role inheritance is broken on the library (exact-mode lists are
 *      isolated early).
 *   2. Columns are created REQUIRED. The shipped family declares five on
 *      the library, two of which have no literal default.
 *   3. Those columns carry their own ValidationFormula, and the list
 *      carries one of its own. A folder that leaves them blank fails both
 *      if either is evaluated for it.
 *
 * This walks one library through those three states in that order and
 * retries the same create after each, so the first refusal names the cause.
 * It then asks two other documented spellings in the final state, because
 * if one of them creates a folder a validated library refuses, that is the
 * fix.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101). Same question
 *     folder-probe.js asks, by the same method, so it keeps the same id.
 *   library.folder.control-add-on-bare-library
 *     CONTROL: folders/add on the library before anything is applied to it.
 *     This is the state folder-create-refusal-probe.js measured. If it
 *     refuses here, this run has a different problem from the one it was
 *     written for and nothing below can be attributed to a setting.
 *   library.folder.add-with-broken-inheritance
 *     The same create after breakroleinheritance.
 *   library.folder.add-with-required-column
 *     The same create after one REQUIRED text column with no default.
 *   library.folder.add-with-column-validation
 *     The same create after that column also carries a ValidationFormula a
 *     blank value fails.
 *   library.folder.add-with-list-validation
 *     The same create after the LIST also carries a ValidationFormula a
 *     blank item fails.
 *   library.folder.add-using-path-under-validation
 *     In that final state, the ResourcePath spelling:
 *     web/Folders/AddUsingPath(decodedurl='<root>/<name>').
 *   library.folder.add-as-list-item-under-validation
 *     In that final state, a folder created as an ITEM: a POST to items
 *     carrying FileSystemObjectType 1 and FileLeafRef.
 *
 * OBSERVED, NEVER ASSERTED
 *   After each create that lands, the folder item's own Id,
 *   FileSystemObjectType and the required column's value, printed as
 *   evidence. Whether a folder inherits a column default is part of what
 *   this is trying to learn, so asserting a value would make the experiment
 *   fail on a tenant that answers differently, which reads exactly like the
 *   refusal being measured.
 *
 * NOT MEASURED HERE
 *   Whether a folder that lands under validation can later be given the
 *   values, and what the library page shows for any of these states. The
 *   deploy never writes metadata to a declared folder.
 *
 * MICROSOFT LEARN CITATIONS
 *   Folder creation via `Folders/add(url=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Folder creation via `Folders/AddUsingPath(decodedurl=)`:
 *     "Supporting % and # in files and folders with the ResourcePath API"
 *   Item creation via `items`, and FileSystemObjectType / FileLeafRef:
 *     "Working with lists and list items with REST",
 *     "FileSystemObjectType enumeration" (CSOM)
 *   Field and list ValidationFormula:
 *     "Field.ValidationFormula Property", "List.ValidationFormula Property"
 *     (CSOM)
 *   Breaking role inheritance:
 *     "SecurableObject.BreakRoleInheritance" (CSOM)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the library it created.
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

  log('INFO', 'probe revision f31aa573. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe Folder Schema';
  const libPath = `web/lists/getbytitle('${LIB}')`;
  const GUARD = 'dbmlspGuard';
  // One folder per state, because a name already taken answers as a no-op
  // (`library.folder.add-under-existing-folder-name`, 2026-09-13) and would
  // read as a pass for a state that never created anything.
  const NAMES = {
    bare: 'dbmlsp bare state',
    acl: 'dbmlsp acl state',
    required: 'dbmlsp required state',
    columnValidation: 'dbmlsp column validation state',
    listValidation: 'dbmlsp list validation state',
    usingPath: 'dbmlsp using path state',
    listItem: 'dbmlsp list item state',
  };

  const Q = {
    fixture: 'A document library is created (BaseTemplate 101)',
    control: 'CONTROL: is folders/add accepted on the bare library, the state the previous probe measured',
    acl: 'Is folders/add still accepted once role inheritance is broken on the library',
    required: 'Is folders/add still accepted once the library carries a REQUIRED column with no default',
    columnValidation: 'Is folders/add still accepted once that column carries a ValidationFormula a blank fails',
    listValidation: 'Is folders/add still accepted once the LIST carries a ValidationFormula a blank item fails',
    usingPath: 'Does Folders/AddUsingPath(decodedurl=) create a folder in that final state',
    listItem: 'Does an items POST carrying FileSystemObjectType 1 and FileLeafRef create a folder in that final state',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, then walk it through`);
    log('INFO', 'broken inheritance, a required column, a column validation formula and a list');
    log('INFO', 'validation formula, creating one differently named folder after each step.');
    log('INFO', 'Two further spellings are then tried in the final state.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing library and its contents would be reused,');
      log('INFO', 'which makes every state after the first unreadable. Set CLEANUP = true.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  const IDS = [
    'library.folder.control-add-on-bare-library',
    'library.folder.add-with-broken-inheritance',
    'library.folder.add-with-required-column',
    'library.folder.add-with-column-validation',
    'library.folder.add-with-list-validation',
    'library.folder.add-using-path-under-validation',
    'library.folder.add-as-list-item-under-validation',
  ];

  expect('library.doc-lib.fixture-library-created', Q.fixture);
  expect('library.folder.control-add-on-bare-library', Q.control);
  expect('library.folder.add-with-broken-inheritance', Q.acl);
  expect('library.folder.add-with-required-column', Q.required);
  expect('library.folder.add-with-column-validation', Q.columnValidation);
  expect('library.folder.add-with-list-validation', Q.listValidation);
  expect('library.folder.add-using-path-under-validation', Q.usingPath);
  expect('library.folder.add-as-list-item-under-validation', Q.listItem);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;
  const pathLiteral = (path) => String(path).replace(/'/g, "''");

  // A field subtype and a list MERGE both need the verbose spelling: the
  // harness posts `odata=nometadata`, under which the server reads a create
  // body as a bare SP.Field and refuses SP.FieldText's own properties. The
  // deploy sends `__metadata` on both writes, so the probe does too, and
  // what is measured is the state and not a transport this project never
  // uses.
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const postVerbose = async (path, body, extraHeaders = {}) => {
    const digest = await getDigest();
    const res = await fetch(`${WEB}/_api/${path}`, {
      method: 'POST',
      headers: { ...VERBOSE, 'X-RequestDigest': digest, ...extraHeaders },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };
  const MERGE = { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' };

  await resetList(LIB);

  // ---- fixture ---------------------------------------------------------
  {
    const existing = await spGet(libPath);
    if (existing.ok) {
      record('library.doc-lib.fixture-library-created', Q.fixture, 'ALREADY PRESENT',
             'reusing an existing library, so every state below may already be applied. '
             + 'Set CLEANUP = true for a clean answer.');
    } else {
      const digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: LIB,
        BaseTemplate: 101,
        Description: 'dbml-sharepoint folder under schema probe. Safe to delete.',
        ContentTypesEnabled: false,
      }, digest);
      record('library.doc-lib.fixture-library-created', Q.fixture,
             made.ok ? 'PASS' : 'FAIL',
             made.ok ? `created '${LIB}'` : short(made));
      if (!made.ok) {
        voidAll(IDS, 'the library fixture did not build, so no state could be applied to it.');
        return report();
      }
    }
  }

  const root = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const rootUrl = readFailed(root) ? null : root.body.ServerRelativeUrl;
  if (!rootUrl) {
    voidAll(IDS, `the library RootFolder did not read back (HTTP ${root.status}), so no folder path could be built.`);
    return report();
  }

  // The folder's own item, for the evidence line. A folder that lands with
  // the required column blank says something the refusal alone does not.
  // The guard column is selected only once it exists: naming an absent column
  // in $select answers HTTP 400, which reads in the evidence as "no item"
  // and would hide the observation this line is here to make.
  let guardExists = false;
  const folderItem = async (name) => {
    const filter = encodeURIComponent(`FileLeafRef eq '${String(name).replace(/'/g, "''")}'`);
    const select = `Id,FileSystemObjectType,FileLeafRef${guardExists ? `,${GUARD}` : ''}`;
    const r = await spGet(`${libPath}/items?$select=${select}&$filter=${filter}&$top=2`);
    if (readFailed(r)) return `the item read failed (HTTP ${r.status})`;
    const rows = r.body.value || [];
    if (!rows.length) return 'no list item was served for that name';
    const row = rows[0];
    const guard = guardExists
      ? `, ${GUARD} ${JSON.stringify(row[GUARD] === undefined ? null : row[GUARD])}`
      : '';
    return `item ${row.Id}, FileSystemObjectType ${row.FileSystemObjectType}${guard}`;
  };

  const addFolder = async (id, question, name) => {
    const digest = await getDigest();
    const res = await spPost(
      `web/GetFolderByServerRelativeUrl('${pathLiteral(rootUrl)}')/folders/add(url='${pathLiteral(name)}')`,
      {}, digest);
    if (!res.ok) {
      record(id, question, isRefusal(res.status) ? 'REFUSED' : 'FAIL', short(res));
      return false;
    }
    record(id, question, 'PASS', `HTTP ${res.status}, and ${await folderItem(name)}`);
    return true;
  };

  // ---- the bare library ------------------------------------------------
  if (!await addFolder('library.folder.control-add-on-bare-library', Q.control, NAMES.bare)) {
    voidAll(IDS.slice(1),
            'the control refused on a bare library, so this run cannot attribute a later refusal '
            + 'to a setting. Something outside these three states is blocking folder creation here.');
    return report();
  }

  // ---- state 1: broken role inheritance --------------------------------
  {
    const digest = await getDigest();
    const broke = await spPost(
      `${libPath}/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)`, {}, digest);
    if (!broke.ok) {
      record('library.folder.add-with-broken-inheritance', Q.acl, 'NOT ESTABLISHED',
             `the library's inheritance could not be broken (${short(broke)}), so this state was never entered.`);
    } else {
      await addFolder('library.folder.add-with-broken-inheritance', Q.acl, NAMES.acl);
    }
  }

  // ---- state 2: a required column with no default ----------------------
  let guardMade = false;
  {
    const made = await postVerbose(`${libPath}/fields`, {
      __metadata: { type: 'SP.FieldText' },
      Title: GUARD,
      FieldTypeKind: 2,
      MaxLength: 64,
      Required: true,
      Description: 'dbmlsp folder under schema probe guard column.',
    });
    guardMade = made.ok;
    guardExists = made.ok;
    if (!made.ok) {
      record('library.folder.add-with-required-column', Q.required, 'NOT ESTABLISHED',
             `the required column could not be created (${short(made)}), so this state was never entered.`);
    } else {
      await addFolder('library.folder.add-with-required-column', Q.required, NAMES.required);
    }
  }

  // ---- state 3: that column carries a validation formula ---------------
  if (!guardMade) {
    record('library.folder.add-with-column-validation', Q.columnValidation, 'NOT ESTABLISHED',
           'the required column was never created, so no column validation could be set on it.');
  } else {
    const set = await postVerbose(
      `${libPath}/fields/getbyinternalnameortitle('${GUARD}')`,
      {
        __metadata: { type: 'SP.FieldText' },
        ValidationFormula: `=[${GUARD}]="ok"`,
        ValidationMessage: 'dbmlsp probe: this column must read ok.',
      },
      MERGE);
    if (!set.ok) {
      record('library.folder.add-with-column-validation', Q.columnValidation, 'NOT ESTABLISHED',
             `the column validation formula was refused at the field set (${short(set)}), so this state was never entered.`);
    } else {
      await addFolder('library.folder.add-with-column-validation', Q.columnValidation, NAMES.columnValidation);
    }
  }

  // ---- state 4: the list carries a validation formula ------------------
  let listValidated = false;
  if (!guardMade) {
    record('library.folder.add-with-list-validation', Q.listValidation, 'NOT ESTABLISHED',
           'the guard column was never created, so a list formula naming it could only be '
           + 'refused for the column being absent, which is not the question.');
  } else {
    // The deploy's own spelling: SP.List metadata, both properties together.
    const set = await postVerbose(libPath, {
      __metadata: { type: 'SP.List' },
      ValidationFormula: `=[${GUARD}]="ok"`,
      ValidationMessage: 'dbmlsp probe: this item must read ok.',
    }, MERGE);
    listValidated = set.ok;
    if (!set.ok) {
      record('library.folder.add-with-list-validation', Q.listValidation, 'NOT ESTABLISHED',
             `the list validation formula was refused (${short(set)}), so this state was never entered.`);
    } else {
      await addFolder('library.folder.add-with-list-validation', Q.listValidation, NAMES.listValidation);
    }
  }

  const finalStateReason = listValidated
    ? null
    : 'the list validation formula never landed, so the final state is not the one this asks about.';

  // ---- the two other spellings, in the final state ---------------------
  if (finalStateReason) {
    record('library.folder.add-using-path-under-validation', Q.usingPath, 'NOT ESTABLISHED', finalStateReason);
  } else {
    const digest = await getDigest();
    const res = await spPost(
      `web/Folders/AddUsingPath(decodedurl='${pathLiteral(`${rootUrl}/${NAMES.usingPath}`)}')`, {}, digest);
    record('library.folder.add-using-path-under-validation', Q.usingPath,
           res.ok ? 'PASS' : isRefusal(res.status) ? 'REFUSED' : 'FAIL',
           res.ok ? `HTTP ${res.status}, and ${await folderItem(NAMES.usingPath)}` : short(res));
  }

  if (finalStateReason) {
    record('library.folder.add-as-list-item-under-validation', Q.listItem, 'NOT ESTABLISHED', finalStateReason);
  } else {
    // An item create names the list's OWN entity type, which is per-list and
    // read rather than spelled: `SP.Data.<something>Item` is derived from the
    // library's URL and guessing it returns a refusal about the type, which
    // would be recorded as an answer about folders.
    const typeRead = await spGet(`${libPath}?$select=ListItemEntityTypeFullName`);
    const itemType = readFailed(typeRead) ? null : typeRead.body.ListItemEntityTypeFullName;
    if (!itemType) {
      record('library.folder.add-as-list-item-under-validation', Q.listItem, 'NOT ESTABLISHED',
             `the list's ListItemEntityTypeFullName did not read back (HTTP ${typeRead.status}), `
             + 'so an item create could not be addressed.');
    } else {
      const res = await postVerbose(`${libPath}/items`, {
        __metadata: { type: itemType },
        FileSystemObjectType: 1,
        FileLeafRef: NAMES.listItem,
      });
      record('library.folder.add-as-list-item-under-validation', Q.listItem,
             res.ok ? 'PASS' : isRefusal(res.status) ? 'REFUSED' : 'FAIL',
             res.ok
               ? `HTTP ${res.status} as ${itemType}, and ${await folderItem(NAMES.listItem)}`
               : `${short(res)} (as ${itemType})`);
    }
  }

  return report();
})();
