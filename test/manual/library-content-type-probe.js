/**
 * dbml-sharepoint PROBE: CONTENT TYPES ON A DOCUMENT LIBRARY
 *
 * QUESTION: A document library carries content types to govern item schemas
 * and behaviors. What content types does a freshly created library carry by
 * default, can a custom content type be created and added to a library over
 * REST, does an uploaded file attach a custom content type at upload time or
 * must it be changed afterwards, and can a metadata column be bound to one
 * content type but not another?
 *
 * WHY: `document-library-probe.js` established that a fileless POST to /items
 * is refused; `file-operations-probe.js` settled what a file is over REST;
 * `library-columns-probe.js` settled metadata columns and list validation;
 * `folder-probe.js` settled what a folder is. This probe is the fourth and final
 * probe taking the library surface from almost entirely unprobed to first-class,
 * and it takes the `content-type` scope.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)? The same
 *        question `document-library-probe.js`, `file-operations-probe.js`,
 *        `library-columns-probe.js`, and `folder-probe.js` ask, by the same
 *        method, keeping the same id per SURFACES.md.
 *   library.content-type.control-missing-column-refused
 *        NEGATIVE CONTROL: Is a MERGE naming a column that does not exist,
 *        sent to a library file's list item, REFUSED? Establishes that this
 *        probe can detect a failed metadata write on a library item.
 *   library.content-type.default-content-types
 *        Which content types does a freshly created library carry by default?
 *        Reads the list and records the ids, titles, and ordering.
 *   library.content-type.custom-content-type-on-library
 *        Can a custom content type be created and added to a library over
 *        REST, and does it read back in the library's content type list?
 *   library.content-type.content-type-at-upload
 *        Can a file be uploaded already carrying a custom content type via
 *        Files/add, or does the upload always land as Document and the content
 *        type has to be changed afterwards?
 *   library.content-type.column-bound-to-one-content-type
 *        Can a column be added to one content type (Document) but not another
 *        (Folder)? Reads back both to confirm the binding is per-content-type,
 *        not per-library.
 *
 * READ THE CONTROL FIRST. It runs after creating the library and uploading an
 * initial file, because a metadata write needs an existing item to target. If
 * a MERGE naming a nonexistent column is accepted, this probe cannot tell a
 * refused write from a successful one and subsequent refusal answers are void.
 *
 * NOTHING IS RETIRED. All five required content type questions and the library
 * fixture question are probed directly over REST.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL below is the one Microsoft Learn
 * documents, not one assembled from memory, because a wrong spelling returns
 * 404, `isRefusal` counts 404 as a refusal, and the probe would then print a
 * claim about SharePoint that was really a typo:
 *
 *   List creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   List ContentTypes collection via `web/lists/getbytitle(...)/contenttypes`:
 *     "SP.List.contentTypes property (sp.js)", dn531432(v=office.15)
 *   Content type creation via POST to `web/contenttypes`:
 *     "SP.ContentTypeCollection.add Method (sp.js)"
 *   Adding content type to list via `contenttypes/addAvailableContentType`:
 *     "SP.ContentTypeCollection.addExistingContentType Method (sp.js)", jj246551(v=office.15)
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Item ContentTypeId update via MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   FieldLinks collection on ContentType via `contenttypes(...)/fieldlinks`:
 *     "SP.ContentType.fieldLinks property (sp.js)", jj246293(v=office.15)
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

  log('INFO', 'probe revision 4d9021d8. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe ContentType';
  const FILE = 'dbmlsp-content-type-probe.txt';
  const UPLOAD_FILE = 'dbmlsp-ct-upload-test.txt';
  const CUSTOM_CT_NAME = 'dbmlsp Custom DocType';
  const CUSTOM_CT_DESC = 'dbml-sharepoint custom document content type probe';
  const CUSTOM_CT_GROUP = 'dbmlsp Probes';
  const COL_NAME = 'dbmlspDocOnlyCol';
  const listPath = `web/lists/getbytitle('${LIB}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, inspect its`);
    log('INFO', 'default content types, test a negative control write on a file item,');
    log('INFO', `create and add custom content type '${CUSTOM_CT_NAME}' to the library,`);
    log('INFO', 'test whether a file upload can attach the custom content type or');
    log('INFO', `requires a post-upload item update, and test whether column '${COL_NAME}'`);
    log('INFO', 'binds to Document without binding to Folder.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' and any existing test site content type would be recycled or deleted first.`);
    } else {
      log('INFO', `CLEANUP is off: an existing '${LIB}' would be reused.`);
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

  // Raw request body helper for endpoints expecting unquoted text or streams.
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
      try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
      return { ok: res.ok, status: res.status, body: parsed, text };
    } catch (err) {
      return { ok: false, status: 0, body: null, text: String(err) };
    }
  };

  const ctIdOf = (ct) => String(
    (ct && ct.Id && ct.Id.StringValue)
    || (ct && ct.StringId)
    || (ct && ct.Id)
    || ''
  );

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.content-type.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a library item is refused');
  expect('library.content-type.default-content-types', 'Default content types carried by a freshly created document library');
  expect('library.content-type.custom-content-type-on-library', 'Can a custom content type be created and added to a library over REST');
  expect('library.content-type.content-type-at-upload', 'Can a file upload attach a custom content type or is post-upload update required');
  expect('library.content-type.column-bound-to-one-content-type', 'Can a column bind to Document without binding to Folder');

  await resetList(LIB);
  let digest = await getDigest();

  // If CLEANUP is requested, also clean any leftover site content type from a previous run
  if (CLEANUP && ALLOW_WRITES) {
    const existingSiteCt = await spGet(
      `web/contenttypes?$filter=Name eq '${CUSTOM_CT_NAME}'`
    );
    const siteRows = (existingSiteCt.ok && existingSiteCt.body && Array.isArray(existingSiteCt.body.value))
      ? existingSiteCt.body.value
      : [];
    for (const row of siteRows) {
      const rowId = ctIdOf(row);
      if (rowId) {
        digest = await getDigest();
        await spPost(`web/contenttypes('${rowId}')`, {}, digest, {
          'X-HTTP-Method': 'DELETE',
          'Content-Length': '0',
        });
      }
    }
  }

  // ---- fixture-library-created: the library fixture --------------------
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
      Description: 'dbml-sharepoint content-type probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created',
           'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  // ---- default-content-types: inspect initial content types -----------
  const defaultCtsResp = await spGet(`${listPath}/contenttypes?$select=Id,StringId,Name,Description,Group,Hidden`);
  const defaultCts = (defaultCtsResp.ok && defaultCtsResp.body && Array.isArray(defaultCtsResp.body.value))
    ? defaultCtsResp.body.value
    : [];
  if (readFailed(defaultCtsResp) || defaultCts.length === 0) {
    record('library.content-type.default-content-types',
           'Default content types carried by a freshly created document library',
           'NOT ESTABLISHED',
           `the content type collection could not be read (HTTP ${defaultCtsResp.status})`);
  } else {
    const summary = defaultCts.map((ct) => ({
      name: ct.Name,
      id: ctIdOf(ct),
      group: ct.Group,
      hidden: ct.Hidden,
    }));
    const names = defaultCts.map((ct) => ct.Name);
    const hasDoc = names.includes('Document');
    const hasFolder = names.includes('Folder');
    const outcome = (hasDoc && hasFolder)
      ? 'DOCUMENT AND FOLDER PRESENT'
      : (hasDoc ? 'DOCUMENT ONLY' : 'UNEXPECTED CONTENT TYPES');
    record('library.content-type.default-content-types',
           'Default content types carried by a freshly created document library',
           outcome,
           `found ${defaultCts.length} content type(s): ${JSON.stringify(summary)}. `
           + `Names in order: ${JSON.stringify(names)}.`);
  }

  // ---- Upload initial file for negative control -----------------------
  digest = await getDigest();
  const initialUpload = await rawPost(
    `${listPath}/RootFolder/Files/add(url='${FILE}',overwrite=true)`,
    'dbml-sharepoint content-type probe initial file',
    digest
  );
  if (!initialUpload.ok) {
    log('FAIL', `Initial upload of '${FILE}' failed: HTTP ${initialUpload.status}`);
  }

  const items = await spGet(
    `${listPath}/items?$select=Id,Title,FileLeafRef,ContentTypeId&$filter=FileLeafRef eq '${FILE}'`
  );
  const rows = (items.ok && items.body && Array.isArray(items.body.value)) ? items.body.value : [];
  const initialItem = rows.length ? rows[0] : null;
  const initialItemId = initialItem ? initialItem.Id : null;

  // ---- control-missing-column-refused: NEGATIVE CONTROL ---------------
  let controlHeld = false;
  if (initialItemId === null) {
    record('library.content-type.control-missing-column-refused',
           'NEGATIVE CONTROL: a MERGE naming a missing column on a library item is refused',
           'NOT ESTABLISHED',
           `no list item was found for '${FILE}' (HTTP ${items.status}), so there was `
           + 'nothing to send a test write to. Every refusal below this line is '
           + 'unproven rather than answered.');
  } else {
    digest = await getDigest();
    const junk = await spPost(`${listPath}/items(${initialItemId})`,
                              { NoSuchColumnAtAll: 'x' }, digest,
                              { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    controlHeld = !junk.ok && isRefusal(junk.status);
    record('library.content-type.control-missing-column-refused',
           'NEGATIVE CONTROL: a MERGE naming a missing column on a library item is refused',
           junk.ok ? 'FAIL' : isRefusal(junk.status) ? 'PASS' : 'NOT ESTABLISHED',
           junk.ok
             ? 'a MERGE naming a column that does not exist was ACCEPTED on a file '
               + 'item. This probe cannot tell a refused metadata write from a '
               + 'successful one, so subsequent refusal answers are void.'
             : isRefusal(junk.status)
               ? `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`
               : `the request failed with HTTP ${junk.status}, which is not the server `
                 + 'refusing the write. The rows depending on this control are '
                 + `unproven rather than answered: ${junk.text.slice(0, 200)}`);
  }

  // ---- custom-content-type-on-library ---------------------------------
  // Enable content types on the library first so custom content types can be attached
  digest = await getDigest();
  await spPost(listPath, { ContentTypesEnabled: true }, digest,
               { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });

  let siteCtId = null;
  const checkSiteCt = await spGet(`web/contenttypes?$filter=Name eq '${CUSTOM_CT_NAME}'`);
  if (checkSiteCt.ok && checkSiteCt.body && Array.isArray(checkSiteCt.body.value) && checkSiteCt.body.value.length > 0) {
    siteCtId = ctIdOf(checkSiteCt.body.value[0]);
  }

  let ctCreated = false;
  let createStatus = 0;
  let createText = '';
  if (!siteCtId) {
    digest = await getDigest();
    const ctPayload = {
      Name: CUSTOM_CT_NAME,
      Description: CUSTOM_CT_DESC,
      Group: CUSTOM_CT_GROUP,
      Id: {
        StringValue: '0x0101004C8E77B1E8434A9B8971F1A581335912',
      },
    };
    const makeCt = await spPost('web/contenttypes', ctPayload, digest);
    createStatus = makeCt.status;
    createText = makeCt.text;
    if (makeCt.ok && makeCt.body) {
      siteCtId = ctIdOf(makeCt.body);
      ctCreated = true;
    } else {
      digest = await getDigest();
      const makeCt2 = await spPost('web/contenttypes', {
        parameters: {
          Name: CUSTOM_CT_NAME,
          Description: CUSTOM_CT_DESC,
          Group: CUSTOM_CT_GROUP,
          ParentContentTypeId: '0x0101',
        },
      }, digest);
      if (makeCt2.ok && makeCt2.body) {
        siteCtId = ctIdOf(makeCt2.body);
        ctCreated = true;
      } else {
        createStatus = makeCt2.status;
        createText = makeCt2.text;
      }
    }
  } else {
    ctCreated = true;
  }

  let addOk = false;
  let addStatus = 0;
  let addText = '';
  let listScopedCtId = null;
  if (siteCtId) {
    digest = await getDigest();
    const addRes = await spPost(`${listPath}/contenttypes/addAvailableContentType`, {
      contentTypeId: siteCtId,
    }, digest);
    addStatus = addRes.status;
    addText = addRes.text;
    if (addRes.ok && addRes.body) {
      addOk = true;
      listScopedCtId = ctIdOf(addRes.body);
    } else if (addRes.status === 500 && addRes.text && addRes.text.includes('already exists')) {
      addOk = true;
    }
  }

  const readBackCts = await spGet(`${listPath}/contenttypes`);
  const readBackList = (readBackCts.ok && readBackCts.body && Array.isArray(readBackCts.body.value))
    ? readBackCts.body.value
    : [];
  const foundOnList = readBackList.find((c) => c.Name === CUSTOM_CT_NAME || (siteCtId && ctIdOf(c).startsWith(siteCtId)));
  if (foundOnList && !listScopedCtId) {
    listScopedCtId = ctIdOf(foundOnList);
  }

  if (!siteCtId && !foundOnList) {
    record('library.content-type.custom-content-type-on-library',
           'Can a custom content type be created and added to a library over REST',
           isRefusal(createStatus) ? 'REFUSED' : 'NOT ESTABLISHED',
           `creating site content type failed: HTTP ${createStatus}: ${createText.slice(0, 240)}`);
  } else if (!addOk && !foundOnList) {
    record('library.content-type.custom-content-type-on-library',
           'Can a custom content type be created and added to a library over REST',
           isRefusal(addStatus) ? 'REFUSED' : 'NOT ESTABLISHED',
           `site content type exists (${siteCtId}), but addAvailableContentType failed: `
           + `HTTP ${addStatus}: ${addText.slice(0, 240)}`);
  } else if (foundOnList) {
    record('library.content-type.custom-content-type-on-library',
           'Can a custom content type be created and added to a library over REST',
           'PASS',
           `custom content type '${CUSTOM_CT_NAME}' is present on the library. `
           + `Site content type ID: ${siteCtId}, list-scoped content type ID: ${listScopedCtId || ctIdOf(foundOnList)}.`);
  } else {
    record('library.content-type.custom-content-type-on-library',
           'Can a custom content type be created and added to a library over REST',
           'NOT ESTABLISHED',
           `add call completed but readback returned HTTP ${readBackCts.status} and `
           + `'${CUSTOM_CT_NAME}' was not found in ${readBackList.length} library content type(s).`);
  }

  // ---- content-type-at-upload -----------------------------------------
  digest = await getDigest();
  const testUpload = await rawPost(
    `${listPath}/RootFolder/Files/add(url='${UPLOAD_FILE}',overwrite=true)`,
    'dbml-sharepoint content-type upload test payload',
    digest
  );
  const uploadItemResp = await spGet(
    `${listPath}/items?$select=Id,FileLeafRef,ContentTypeId&$filter=FileLeafRef eq '${UPLOAD_FILE}'`
  );
  const uploadRows = (uploadItemResp.ok && uploadItemResp.body && Array.isArray(uploadItemResp.body.value))
    ? uploadItemResp.body.value
    : [];
  const uploadRow = uploadRows.length ? uploadRows[0] : null;
  const uploadItemId = uploadRow ? uploadRow.Id : null;
  const initialCtId = uploadRow ? uploadRow.ContentTypeId : null;

  if (!testUpload.ok || !uploadItemId || !initialCtId) {
    record('library.content-type.content-type-at-upload',
           'Can a file upload attach a custom content type or is post-upload update required',
           'NOT ESTABLISHED',
           `upload or readback failed: upload HTTP ${testUpload.status}, `
           + `items readback HTTP ${uploadItemResp.status}.`);
  } else {
    let postMergeCtId = null;
    let mergeOk = false;
    let mergeStatus = 0;
    let mergeText = '';
    if (listScopedCtId) {
      digest = await getDigest();
      const mergeCt = await spPost(`${listPath}/items(${uploadItemId})`,
                                   { ContentTypeId: listScopedCtId }, digest,
                                   { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
      mergeStatus = mergeCt.status;
      mergeText = mergeCt.text;
      mergeOk = mergeCt.ok;
      if (mergeOk) {
        const verifyItem = await spGet(
          `${listPath}/items(${uploadItemId})?$select=Id,FileLeafRef,ContentTypeId`
        );
        if (verifyItem.ok && verifyItem.body) {
          postMergeCtId = verifyItem.body.ContentTypeId;
        }
      }
    }

    const landsAsDoc = initialCtId.startsWith('0x0101');
    const changedToCustom = postMergeCtId === listScopedCtId;
    record('library.content-type.content-type-at-upload',
           'Can a file upload attach a custom content type or is post-upload update required',
           landsAsDoc && changedToCustom
             ? 'UPLOAD LANDS AS DEFAULT DOCUMENT; CHANGED VIA ITEM MERGE'
             : landsAsDoc
               ? 'UPLOAD LANDS AS DEFAULT DOCUMENT'
               : 'UPLOAD LANDED WITH NON-DEFAULT CONTENT TYPE',
           `Initial upload ContentTypeId was ${initialCtId} (Document base 0x0101). `
           + (listScopedCtId
             ? (changedToCustom
               ? `Post-upload MERGE with ContentTypeId ${listScopedCtId} updated the item to ${postMergeCtId}. `
                 + 'Files/add takes url and overwrite parameters (dn450841); assigning a non-default content type requires a post-upload item MERGE.'
               : `Post-upload MERGE returned HTTP ${mergeStatus}: ${mergeText.slice(0, 160)}. ContentTypeId after write: ${postMergeCtId}.`)
             : 'Custom content type was not available on the library, so post-upload item MERGE was skipped.'));
  }

  // ---- column-bound-to-one-content-type --------------------------------
  const allCurrentCtsResp = await spGet(`${listPath}/contenttypes?$select=Id,StringId,Name`);
  const allCurrentCts = (allCurrentCtsResp.ok && allCurrentCtsResp.body && Array.isArray(allCurrentCtsResp.body.value))
    ? allCurrentCtsResp.body.value
    : [];
  const docCt = allCurrentCts.find((c) => c.Name === 'Document' || (ctIdOf(c).startsWith('0x0101') && !ctIdOf(c).startsWith('0x010100')));
  const folderCt = allCurrentCts.find((c) => c.Name === 'Folder' || ctIdOf(c).startsWith('0x0120'));
  const docCtId = docCt ? ctIdOf(docCt) : null;
  const folderCtId = folderCt ? ctIdOf(folderCt) : null;

  const colXml = `<Field Type="Text" Name="${COL_NAME}" DisplayName="${COL_NAME}" />`;
  digest = await getDigest();
  await spPost(`${listPath}/fields/createfieldasxml`, {
    parameters: { SchemaXml: colXml, Options: 8 },
  }, digest);

  if (docCtId) {
    digest = await getDigest();
    await spPost(`${listPath}/contenttypes('${docCtId}')/fieldlinks`, {
      FieldInternalName: COL_NAME,
    }, digest);
  }

  const docLinksResp = docCtId ? await spGet(`${listPath}/contenttypes('${docCtId}')/fieldlinks?$select=Name`) : null;
  const folderLinksResp = folderCtId ? await spGet(`${listPath}/contenttypes('${folderCtId}')/fieldlinks?$select=Name`) : null;

  const docLinks = (docLinksResp && docLinksResp.ok && docLinksResp.body && Array.isArray(docLinksResp.body.value))
    ? docLinksResp.body.value.map((f) => f.Name)
    : [];
  const folderLinks = (folderLinksResp && folderLinksResp.ok && folderLinksResp.body && Array.isArray(folderLinksResp.body.value))
    ? folderLinksResp.body.value.map((f) => f.Name)
    : [];

  const inDoc = docLinks.includes(COL_NAME);
  const inFolder = folderLinks.includes(COL_NAME);

  if (!docCtId || !folderCtId || !docLinksResp || !docLinksResp.ok || !folderLinksResp || !folderLinksResp.ok) {
    record('library.content-type.column-bound-to-one-content-type',
           'Can a column bind to Document without binding to Folder',
           'NOT ESTABLISHED',
           `could not read fieldlinks for Document (${docCtId}, HTTP ${docLinksResp ? docLinksResp.status : 'n/a'}) `
           + `or Folder (${folderCtId}, HTTP ${folderLinksResp ? folderLinksResp.status : 'n/a'})`);
  } else {
    const outcome = (inDoc && !inFolder)
      ? 'BOUND TO DOCUMENT ONLY (PER-CONTENT-TYPE)'
      : (inDoc && inFolder)
        ? 'BOUND TO BOTH (PER-LIBRARY)'
        : (!inDoc && !inFolder)
          ? 'NOT BOUND TO EITHER'
          : 'BOUND TO FOLDER ONLY';
    record('library.content-type.column-bound-to-one-content-type',
           'Can a column bind to Document without binding to Folder',
           outcome,
           `Column '${COL_NAME}' on Document (${docCtId}): ${inDoc ? 'present' : 'absent'}. `
           + `Column '${COL_NAME}' on Folder (${folderCtId}): ${inFolder ? 'present' : 'absent'}. `
           + `Document has ${docLinks.length} fieldlink(s); Folder has ${folderLinks.length} fieldlink(s).`);
  }

  report();
})();
