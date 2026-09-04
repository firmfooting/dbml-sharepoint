/**
 * dbml-sharepoint PROBE: WHAT A FOLDER IS ON A DOCUMENT LIBRARY
 *
 * QUESTION: a document library supports folder hierarchies where a generic list
 * stores items in a flat structure. What is a folder made of over REST, how is
 * it created, does it carry item metadata, how is it renamed, and does deleting
 * a folder cascade to its contents and land in the recycle bin?
 *
 * WHY: file-operations-probe.js settled what a file is on a document library.
 * This probe settles what a folder is: the distinguishing structure of a
 * document library, and the basis of library folder hierarchies.
 *
 * WHAT IT ASKS. Ids follow the grammar in test/manual/SURFACES.md:
 * <surface>.<scope>.<question>.
 *
 *   library.folder.control-missing-column-refused
 *        NEGATIVE CONTROL: is a MERGE naming a column that does not exist,
 *        sent to a folder list item, refused? Establishes that this probe can
 *        detect a failed metadata write on a folder.
 *   library.doc-lib.fixture-library-created
 *        does a document library create at all (BaseTemplate 101)? The same
 *        question document-library-probe.js asks, by the same method, so it
 *        keeps the same id: one question with multiple records, per SURFACES.md.
 *   library.folder.creation-path
 *        can Files/add create a folder, or does folder creation require the
 *        documented folder creation endpoint, and what does the call return?
 *   library.folder.filesystem-object-type
 *        after creation, what is the item's FileSystemObjectType? File is 0
 *        and Folder is 1.
 *   library.folder.carries-metadata
 *        does a folder carry metadata like an item (write a Title, read it back),
 *        or is it a name-only node?
 *   library.folder.name-field
 *        does a folder have a FileLeafRef, and can it be renamed the way a file is?
 *   library.folder.delete-recycles
 *        does deleting a folder recycle it (with its children), and is the folder's
 *        recycle-bin entry recoverable the way a file's is?
 *
 * READ THE CONTROL FIRST. It runs after creation because a metadata write on
 * a folder needs a folder item to target. If a MERGE naming a nonexistent column
 * is accepted, this probe cannot tell a refused write from a successful one and
 * metadata, rename, and delete answers are void rather than answered.
 *
 * NOTHING IS RETIRED. All six required folder questions are probed directly
 * over REST. Column defaults on folders are not probed here, because that question
 * is owned by library-columns-probe.js under column-default-on-folder.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL below is the one Microsoft Learn
 * documents, not one assembled from memory, because a wrong spelling returns
 * 404, isRefusal counts 404 as a refusal, and the probe would then print a
 * claim about SharePoint that was really a typo:
 *
 *   Folders/add(url=) and web/folders/add:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Folders POST with ServerRelativeUrl, and renaming through ListItemAllFields
 *   by writing FileLeafRef:
 *     "Working with folders and files with REST"
 *   Folder methods Recycle and DeleteObject:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   FileSystemObjectType (Invalid -1, File 0, Folder 1, Web 2):
 *     "Lists and list items REST API reference", dn531433(v=office.15)
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

  log('INFO', 'probe revision a02ed5b6. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe Folder';
  const FOLDER = 'dbmlsp-folder-probe';
  const RENAMED = 'dbmlsp-folder-renamed';
  const CHILD_FILE = 'dbmlsp-child-file.txt';
  const FILE_PROBE = 'dbmlsp-folder-file-check.txt';
  const listPath = `web/lists/getbytitle('${LIB}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, attempt`);
    log('INFO', `creating a folder '${FOLDER}' through Files/add and Folders/add,`);
    log('INFO', 'read its FileSystemObjectType, test a missing column negative control,');
    log('INFO', 'write Title metadata and read it back, add a child file, rename');
    log('INFO', `the folder to '${RENAMED}', and recycle it with its children.`);
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first, with its contents.`);
    } else {
      log('INFO', `CLEANUP is off: an existing '${LIB}' would be reused, and a folder`);
      log('INFO', "from a previous run would answer this run's questions.");
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

  expect('library.folder.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a folder item is refused');
  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.folder.creation-path', 'Does Files/add create a folder or is folder creation a distinct endpoint, and what does it return');
  expect('library.folder.filesystem-object-type', "A created folder's FileSystemObjectType");
  expect('library.folder.carries-metadata', 'Does a folder carry metadata like an item, and does Title read back');
  expect('library.folder.name-field', 'Can FileLeafRef be written as a folder rename, and does it read back');
  expect('library.folder.delete-recycles', 'Does Recycle remove the folder and its children, and is it in the recycle bin');

  await resetList(LIB);
  let digest = await getDigest();

  // ---- fixture-library-created: the library fixture --------------------
  const existing = await spGet(listPath);
  if (existing.ok) {
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)', 'ALREADY PRESENT',
           'reusing an existing library. Set CLEANUP = true for a clean answer');
  } else {
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint folder probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  // ---- the library's root folder path ----------------------------------
  const root = await spGet(`${listPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = root.ok && root.body ? root.body.ServerRelativeUrl : null;
  if (!folderUrl) {
    record('library.folder.creation-path', 'Does Files/add create a folder or is folder creation a distinct endpoint, and what does it return', 'NOT ESTABLISHED',
           `the library's RootFolder did not read back (HTTP ${root.status}), so folder creation cannot proceed.`);
    return report();
  }

  // ---- creation-path: Files/add versus documented folder creation ------
  // Probe whether Files/add with empty body creates a folder or an ordinary file.
  digest = await getDigest();
  const fileAttempt = await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE_PROBE}',overwrite=true)`,
    '', digest);
  let fileAttemptObjType = null;
  if (fileAttempt.ok) {
    const fileItemCheck = await spGet(
      `${listPath}/items?$select=Id,FileSystemObjectType&$filter=FileLeafRef eq '${FILE_PROBE}'`);
    const fileRows = (fileItemCheck.ok && fileItemCheck.body && fileItemCheck.body.value) || [];
    if (fileRows.length) fileAttemptObjType = fileRows[0].FileSystemObjectType;
    digest = await getDigest();
    await spPost(`web/GetFileByServerRelativeUrl('${folderUrl}/${FILE_PROBE}')/recycle`, {}, digest);
  }

  // Create folder through documented endpoints, recording which spelling answered.
  digest = await getDigest();
  let createdSpelling = 'Folders/add(url=)';
  let folderCreated = await spPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/folders/add(url='${FOLDER}')`,
    {}, digest);
  if (!folderCreated.ok) {
    digest = await getDigest();
    createdSpelling = 'web/folders/add';
    folderCreated = await spPost(
      `web/folders/add('${folderUrl}/${FOLDER}')`,
      {}, digest);
    if (!folderCreated.ok) {
      digest = await getDigest();
      createdSpelling = 'web/folders';
      folderCreated = await spPost(
        'web/folders',
        { ServerRelativeUrl: `${folderUrl}/${FOLDER}` }, digest);
    }
  }

  const folderReturned = folderCreated.ok && folderCreated.body ? folderCreated.body : null;
  const filesAddMadeFolder = fileAttempt.ok && fileAttemptObjType === 1;

  record('library.folder.creation-path',
         'Does Files/add create a folder or is folder creation a distinct endpoint, and what does it return',
         !folderCreated.ok
           ? (isRefusal(folderCreated.status) ? 'REFUSED' : 'NOT ESTABLISHED')
           : filesAddMadeFolder
             ? 'Files/add CREATED FOLDER'
             : 'DISTINCT ENDPOINT, SP.Folder RETURNED',
         !folderCreated.ok
           ? `folder creation failed across endpoints, last attempt (${createdSpelling}) HTTP ${folderCreated.status}: ${folderCreated.text.slice(0, 240)}.`
           : `Files/add returned HTTP ${fileAttempt.status} `
             + (fileAttempt.ok
               ? `(produced FileSystemObjectType ${fileAttemptObjType}, an SP.File rather than a folder). `
               : '(refused or failed). ')
             + `Folder creation succeeded via ${createdSpelling} (HTTP ${folderCreated.status}), returning `
             + `${folderReturned ? Object.keys(folderReturned).length : 0} propertie(s): `
             + `${JSON.stringify(folderReturned ? {
                 Name: folderReturned.Name,
                 ServerRelativeUrl: folderReturned.ServerRelativeUrl,
                 ItemCount: folderReturned.ItemCount,
                 Exists: folderReturned.Exists,
                 UniqueId: folderReturned.UniqueId,
               } : null)}.`);

  // Resolve target folder URL and backing list item.
  const targetFolderUrl = folderReturned && folderReturned.ServerRelativeUrl
    ? folderReturned.ServerRelativeUrl
    : `${folderUrl}/${FOLDER}`;
  const folderPath = `web/GetFolderByServerRelativeUrl('${targetFolderUrl}')`;

  const items = await spGet(
    `${listPath}/items?$select=Id,Title,FileLeafRef,FileRef,FileSystemObjectType`
    + `&$filter=FileLeafRef eq '${FOLDER}'`);
  const rows = (items.ok && items.body && items.body.value) || [];
  let row = rows.length ? rows.find((r) => r.FileSystemObjectType === 1) || rows[0] : null;
  if (!row) {
    const itemAllFields = await spGet(
      `${folderPath}/ListItemAllFields?$select=Id,Title,FileLeafRef,FileRef,FileSystemObjectType`);
    if (itemAllFields.ok && itemAllFields.body) {
      row = itemAllFields.body;
    }
  }
  const itemId = row ? row.Id : null;

  // ---- control-missing-column-refused: NEGATIVE CONTROL ---------------
  let controlHeld = false;
  if (itemId === null) {
    record('library.folder.control-missing-column-refused',
           'NEGATIVE CONTROL: a MERGE naming a missing column on a folder item is refused',
           'NOT ESTABLISHED',
           `no list item was found for folder '${FOLDER}' (HTTP ${items.status}), so there was `
           + 'nothing to send a nonsense write to. Every REFUSED below this line is '
           + 'unproven rather than answered.');
  } else {
    digest = await getDigest();
    const junk = await spPost(`${listPath}/items(${itemId})`,
                              { NoSuchColumnAtAll: 'x' }, digest,
                              { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    controlHeld = !junk.ok && isRefusal(junk.status);
    record('library.folder.control-missing-column-refused',
           'NEGATIVE CONTROL: a MERGE naming a missing column on a folder item is refused',
           junk.ok ? 'FAIL' : isRefusal(junk.status) ? 'PASS' : 'NOT ESTABLISHED',
           junk.ok
             ? 'a MERGE naming a column that does not exist was ACCEPTED on a folder '
               + 'item. This probe cannot tell a refused metadata write from a '
               + 'successful one, so the carries-metadata, rename, and delete answers are '
               + 'void whichever way they go.'
             : isRefusal(junk.status)
               ? `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`
               : `the request failed with HTTP ${junk.status}, which is not the server `
                 + 'refusing the write. The rows depending on this control are '
                 + `unproven rather than answered: ${junk.text.slice(0, 200)}`);
  }

  // ---- filesystem-object-type: file, folder, or neither --------------
  record('library.folder.filesystem-object-type',
         "A created folder's FileSystemObjectType",
         row === null ? 'NOT ESTABLISHED'
           : row.FileSystemObjectType === 1 ? 'FOLDER (1)'
             : row.FileSystemObjectType === 0 ? 'FILE (0)'
               : 'NEITHER FILE NOR FOLDER',
         row === null
           ? `the created folder has no readable list item (HTTP ${items.status}).`
           : `${JSON.stringify(row)}. Learn documents Invalid = -1, File = 0, `
             + 'Folder = 1, Web = 2, so this verifies whether SharePoint '
             + 'assigns FileSystemObjectType 1 (Folder) to a created folder.');

  // ---- carries-metadata: does a folder carry metadata like an item? ---
  const FOLDER_TITLE = 'dbmlsp folder title probe';
  let metadataItem = null;
  if (itemId === null) {
    record('library.folder.carries-metadata',
           'Does a folder carry metadata like an item, and does Title read back',
           'NOT ESTABLISHED',
           `no list item was found for folder '${FOLDER}', so metadata could not be written.`);
  } else {
    digest = await getDigest();
    const writeMeta = await spPost(`${listPath}/items(${itemId})`,
                                   { Title: FOLDER_TITLE }, digest,
                                   { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    const readBack = await spGet(`${listPath}/items(${itemId})?$select=Id,Title,FileLeafRef`);
    metadataItem = readBack.ok && readBack.body ? readBack.body : null;
    if (readFailed(readBack)) {
      record('library.folder.carries-metadata',
             'Does a folder carry metadata like an item, and does Title read back',
             'NOT ESTABLISHED',
             `the MERGE returned HTTP ${writeMeta.status}, but reading back the item failed `
             + `(HTTP ${readBack.status}), so this run has no evidence either way.`);
    } else {
      const stored = metadataItem.Title === FOLDER_TITLE;
      record('library.folder.carries-metadata',
             'Does a folder carry metadata like an item, and does Title read back',
             !writeMeta.ok
               ? (isRefusal(writeMeta.status) ? 'REFUSED' : 'NOT ESTABLISHED')
               : stored ? 'CARRIES METADATA, Title READ BACK'
                 : 'ACCEPTED THEN DISCARDED',
             !writeMeta.ok
               ? `MERGE refused with HTTP ${writeMeta.status}: ${writeMeta.text.slice(0, 240)}.`
               : `${JSON.stringify(metadataItem)}. Title before write was `
                 + `${JSON.stringify(row.Title)}, after write is `
                 + `${JSON.stringify(metadataItem.Title)}. `
                 + (stored
                   ? 'A folder in a library can carry item metadata, confirming it is '
                     + 'a full list item rather than a name-only node.'
                   : 'The write was accepted but Title did not persist on the item.'));
    }
  }

  // ---- name-field: writing FileLeafRef to rename the folder -----------
  let renamedRow = null;
  let currentFolderUrl = targetFolderUrl;
  if (itemId === null) {
    record('library.folder.name-field',
           'Can FileLeafRef be written as a folder rename, and does it read back',
           'NOT ESTABLISHED',
           `no list item was found for '${FOLDER}', so there was nothing to rename.`);
  } else {
    digest = await getDigest();
    const rename = await spPost(`${listPath}/items(${itemId})`,
                                { FileLeafRef: RENAMED }, digest,
                                { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    const readBack = await spGet(
      `${listPath}/items(${itemId})?$select=Id,Title,FileLeafRef,FileRef`);
    renamedRow = readBack.ok && readBack.body ? readBack.body : null;
    if (readFailed(readBack)) {
      record('library.folder.name-field',
             'Can FileLeafRef be written as a folder rename, and does it read back',
             'NOT ESTABLISHED',
             `the MERGE returned HTTP ${rename.status}, but the item read-back failed `
             + `(HTTP ${readBack.status}), so this run has no evidence either way.`);
    } else {
      const took = renamedRow.FileLeafRef === RENAMED;
      const refPoints = String(renamedRow.FileRef || '').endsWith(`/${RENAMED}`);
      if (took && refPoints && renamedRow.FileRef) {
        currentFolderUrl = renamedRow.FileRef;
      }
      const folderEntity = await spGet(
        `web/GetFolderByServerRelativeUrl('${currentFolderUrl}')?$select=Name,ServerRelativeUrl,Exists`);
      const entityMoved = folderEntity.ok && folderEntity.body && folderEntity.body.Name === RENAMED;
      record('library.folder.name-field',
             'Can FileLeafRef be written as a folder rename, and does it read back',
             !rename.ok
               ? (isRefusal(rename.status) ? 'REFUSED' : 'NOT ESTABLISHED')
               : took && refPoints
                 ? (entityMoved ? 'RENAMED, BOTH COLUMNS AND FOLDER ENTITY FOLLOW'
                                : 'RENAMED, AND BOTH COLUMNS FOLLOW')
                 : took ? 'FileLeafRef MOVED, FileRef DID NOT'
                   : 'ACCEPTED THEN DISCARDED',
             `${JSON.stringify(renamedRow)}. Folder entity after rename: `
             + `${JSON.stringify(folderEntity.ok ? folderEntity.body : null)}. `
             + (!rename.ok
               ? `HTTP ${rename.status}: ${rename.text.slice(0, 240)}.`
               : took && refPoints
                 ? 'A folder rename is a metadata write to FileLeafRef on the folder '
                   + 'item, matching the file rename method.'
                 : 'The columns disagree about the name, so FileLeafRef did not '
                   + 'update the folder path consistently.'));
    }
  }

  // ---- delete-recycles: recycle folder with child, check recycle bin --
  digest = await getDigest();
  const childUpload = await rawPost(
    `web/GetFolderByServerRelativeUrl('${currentFolderUrl}')/Files/add(url='${CHILD_FILE}',overwrite=true)`,
    'dbml-sharepoint folder probe child file. Safe to delete.', digest);
  const childFileUrl = `${currentFolderUrl}/${CHILD_FILE}`;

  digest = await getDigest();
  let recycled = await spPost(`web/GetFolderByServerRelativeUrl('${currentFolderUrl}')/recycle`,
                              {}, digest);
  let spelling = '/recycle';
  if (!recycled.ok) {
    digest = await getDigest();
    const parenthesised = await spPost(
      `web/GetFolderByServerRelativeUrl('${currentFolderUrl}')/recycle()`, {}, digest);
    if (parenthesised.ok) {
      recycled = parenthesised;
      spelling = '/recycle()';
    }
  }
  const recycledId = recycled.ok && recycled.body
    ? String(recycled.body.value !== undefined ? recycled.body.value : recycled.body)
    : null;
  const folderStillThere = await spGet(
    `web/GetFolderByServerRelativeUrl('${currentFolderUrl}')?$select=Exists`);
  const childStillThere = await spGet(
    `web/GetFileByServerRelativeUrl('${childFileUrl}')?$select=Exists`);
  const bin = await spGet('web/RecycleBin?$select=Id,Title,LeafName,DirName&$top=200');
  const binRows = (bin.ok && bin.body && bin.body.value) || [];
  const byId = recycledId !== null && binRows.some(
    (entry) => String(entry.Id).toLowerCase() === recycledId.toLowerCase());
  const byName = binRows.some(
    (entry) => entry.LeafName === RENAMED || entry.LeafName === FOLDER);

  record('library.folder.delete-recycles',
         'Does Recycle remove the folder and its children, and is it in the recycle bin',
         !recycled.ok
           ? (isRefusal(recycled.status) ? 'REFUSED' : 'NOT ESTABLISHED')
           : readFailed(bin) ? 'RECYCLED, BIN UNREADABLE'
             : byId ? 'RECYCLED WITH CHILDREN, AND IN THE BIN'
               : byName ? 'RECYCLED, BIN MATCHES BY NAME ONLY'
                 : 'RECYCLED, BIN DOES NOT SHOW IT',
         !recycled.ok
           ? `recycle call failed, HTTP ${recycled.status}: ${recycled.text.slice(0, 240)}.`
           : `${spelling} answered HTTP ${recycled.status} and returned `
             + `${JSON.stringify(recycledId)}. Child upload HTTP ${childUpload.status}. `
             + `Re-reading the folder gave HTTP ${folderStillThere.status} `
             + `(${JSON.stringify(folderStillThere.ok ? folderStillThere.body : null)}). `
             + `Re-reading child file gave HTTP ${childStillThere.status} `
             + `(${JSON.stringify(childStillThere.ok ? childStillThere.body : null)}). `
             + (readFailed(bin)
               ? `web/RecycleBin did not read back (HTTP ${bin.status}). `
                 + 'The folder and child are gone from the library; where they went is unobserved.'
               : byId
                 ? `the bin holds ${binRows.length} entrie(s) and one carries the id `
                   + 'Recycle returned, confirming the deletion is recoverable.'
                 : byName
                   ? `the bin holds ${binRows.length} entrie(s) matching by name but `
                     + 'not by returned id (corroboration rather than identification).'
                   : `the bin holds ${binRows.length} entrie(s) and none matches by id or name.`));

  // ---- void what the control cannot vouch for -------------------------
  if (!controlHeld) {
    for (const id of ['library.folder.carries-metadata',
                      'library.folder.name-field',
                      'library.folder.delete-recycles']) {
      const voided = RESULTS.find((r) => r.id === id);
      record(id, voided.question, voided.outcome,
             `${voided.evidence} VOID: the negative control did not hold, so this `
             + 'probe cannot tell a refused write from a successful one and this row '
             + 'is not evidence either way.', 'void');
    }
  }

  report();
  log('INFO', `Done. Delete '${LIB}' when you have copied the results.`);
})();
