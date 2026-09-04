/**
 * dbml-sharepoint PROBE: WHAT A FILE IS ON A DOCUMENT LIBRARY
 *
 * QUESTION: a document library stores files where a generic list stores
 * items. What is a file made of over REST, which parts of one can a script
 * write, and which does SharePoint own?
 *
 * WHY: `document-library-probe.js` settled one decision, that a
 * `kind: DocumentLibrary` cannot carry demo rows because a fileless POST to
 * /items is refused. It never asked what a file IS. Everything else
 * first-class library support needs is unasked: which column holds the name,
 * whether a rename is a write this tool could emit, whether versioning and
 * check-out are reachable at all, and what a delete does with the bytes.
 * `test/manual/SURFACES.md` says as much out loud, that `library` holding one
 * probe is the statement that document libraries are almost entirely
 * unprobed. This is the first of four probes closing that, and it takes the
 * `file` scope.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`.
 *
 *   library.file.control-missing-column-refused
 *        NEGATIVE CONTROL: is a MERGE naming a column that does not exist,
 *        sent to a FILE's list item, REFUSED? Establishes that this probe can
 *        see a failed metadata write on a file at all. Without it, every
 *        REFUSED below is a claim about SharePoint resting on nothing.
 *   library.doc-lib.fixture-library-created
 *        does a document library create at all (BaseTemplate 101)? The same
 *        question `document-library-probe.js` asks, by the same method, so it
 *        keeps the same id: one question with two records, per SURFACES.md.
 *   library.file.name-field-is-leafref
 *        is the library's Name column actually FileLeafRef? Reads the field
 *        schema (InternalName, StaticName, Title, TypeAsString, ReadOnlyField)
 *        and decides whether this tool may treat FileLeafRef as the file name
 *        field, or whether the mapping between the two is looser than that.
 *   library.file.upload-path-files-add
 *        does Files/add upload a real file, and what does the call hand back?
 *        The canonical upload path, and the entity it returns is what any
 *        later step has to address the file by.
 *   library.file.file-system-object-type
 *        after a real upload, what is the item's FileSystemObjectType? File is
 *        0 and Folder is 1, so this separates a real file from a folder and
 *        from the fileless ghost the other probe went looking for.
 *   library.file.versioning-read-back
 *        does the library expose a version collection over REST, and does a
 *        content update create a new version? Asked before check-out, so the
 *        delta belongs to the update alone.
 *   library.file.check-out-check-in
 *        do CheckOut and CheckIn apply to a file over REST, and what does
 *        CheckOutType read back as at each step?
 *   library.file.file-rename
 *        can FileLeafRef be written through the file's list item (a rename),
 *        and does it read back on both FileLeafRef and FileRef?
 *   library.file.file-delete
 *        does Recycle remove the file, and does it land in the site recycle
 *        bin? Recycled, never purged, so a mistake stays recoverable.
 *
 * READ THE CONTROL FIRST. It runs third rather than first, because a metadata
 * write on a file needs a file to write to, so the library and the upload come
 * before it. If a MERGE naming a nonexistent column is ACCEPTED, this probe
 * cannot tell a refused write from a successful one and every REFUSED below is
 * void rather than answered.
 *
 * NOTHING IS RETIRED, and one question is narrower than it looks.
 * `upload-path-files-add` asks what Files/add returns, not whether the upload
 * populates Title. Title after a real upload is already settled, by the same
 * method, at `library.file-vs-item.title-after-upload`, and re-asking it here
 * under a second id would put one question in the catalogue twice.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL below is the one Microsoft Learn
 * documents, not one assembled from memory, because a wrong spelling returns
 * 404, `isRefusal` counts 404 as a refusal, and the probe would then print a
 * claim about SharePoint that was really a typo:
 *
 *   Files/add(url=,overwrite=), $value with X-HTTP-Method PUT, /checkout,
 *   /checkin(comment=,checkintype=), /undocheckout, /recycle, /moveto,
 *   Versions, and the File properties CheckOutType (Online 0, Offline 1,
 *   None 2), Level (Published 1, Draft 2, Checkout 255), MajorVersion:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Renaming through ListItemAllFields by writing FileLeafRef:
 *     "Working with folders and files with REST"
 *   FileSystemObjectType (Invalid -1, File 0, Folder 1, Web 2):
 *     "Lists and list items REST API reference", dn531433(v=office.15)
 *
 * The one endpoint with no citation is `web/RecycleBin`, so the delete
 * question turns on what Recycle returned and treats the bin read as
 * corroboration that may itself be unavailable.
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

  log('INFO', 'probe revision 72891ca3. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe FileOps';
  const FILE = 'dbmlsp-fileops-probe.txt';
  const RENAMED = 'dbmlsp-fileops-renamed.txt';
  const listPath = `web/lists/getbytitle('${LIB}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, upload one`);
    log('INFO', `text file '${FILE}' to it through Files/add, then read the file`);
    log('INFO', 'back as an entity and as a list item, try a metadata write naming');
    log('INFO', 'a column that does not exist, replace the file content, check it');
    log('INFO', `out and back in, rename it to '${RENAMED}', and recycle it.`);
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first, with its contents.`);
    } else {
      log('INFO', `CLEANUP is off: an existing '${LIB}' would be reused, and a file`);
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

  // A raw request body, not JSON. Files/add and $value both take the file's
  // bytes as the body, and the harness's spPost JSON-encodes whatever it is
  // given, which would upload the quotes along with the text.
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

  // How many versions the collection holds, or null when it could not be read.
  // null and 0 are different answers and must not collapse: 0 is "versioning
  // is on and there are none yet", null is "this run did not find out".
  const versionCount = (response) => (
    response.ok && response.body && Array.isArray(response.body.value)
      ? response.body.value.length
      : null
  );

  expect('library.file.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused');
  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.file.name-field-is-leafref', "Is the library's Name column FileLeafRef");
  expect('library.file.upload-path-files-add', 'What Files/add uploads and what it hands back');
  expect('library.file.file-system-object-type', "An uploaded file's FileSystemObjectType");
  expect('library.file.versioning-read-back', 'Does REST expose versions, and does a content update add one');
  expect('library.file.check-out-check-in', 'Do CheckOut and CheckIn apply to a file over REST');
  expect('library.file.file-rename', 'Can FileLeafRef be written as a rename, and does it read back');
  expect('library.file.file-delete', 'Does Recycle remove the file and put it in the recycle bin');

  await resetList(LIB);
  let digest = await getDigest();

  // ---- fixture-library-created: the library ---------------------------
  const existing = await spGet(listPath);
  if (existing.ok) {
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)', 'ALREADY PRESENT',
           'reusing an existing library. Set CLEANUP = true for a clean answer');
  } else {
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint file-operations probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  // ---- name-field-is-leafref: which column is the file name? ----------
  // Reads the whole field collection rather than $select-ing the properties
  // of interest. A $select naming a property SharePoint does not have refuses
  // the entire GET, so the question would come back unanswerable rather than
  // answered, and the answer would look like a platform finding.
  //
  // The Title comparison is deliberately not asserted against 'Name': a
  // non-English tenant titles the column differently, and this probe reports
  // what the titles ARE rather than checking them against an English one.
  const fields = await spGet(`${listPath}/fields?$top=500`);
  const allFields = (fields.ok && fields.body && fields.body.value) || [];
  const leafRef = allFields.find((f) => f.InternalName === 'FileLeafRef') || null;
  const titledName = allFields
    .filter((f) => f.Title === 'Name')
    .map((f) => f.InternalName);
  if (readFailed(fields) || !leafRef) {
    record('library.file.name-field-is-leafref', "Is the library's Name column FileLeafRef", 'NOT ESTABLISHED',
           readFailed(fields)
             ? `the field collection could not be read (HTTP ${fields.status})`
             : `the field collection read back ${allFields.length} field(s) and none `
               + 'of them is named FileLeafRef, so this library does not have the '
               + 'column the tool would key a file name to');
  } else {
    const shape = {
      InternalName: leafRef.InternalName, StaticName: leafRef.StaticName,
      Title: leafRef.Title, TypeAsString: leafRef.TypeAsString,
      ReadOnlyField: leafRef.ReadOnlyField, Hidden: leafRef.Hidden,
      Sealed: leafRef.Sealed, Required: leafRef.Required,
    };
    record('library.file.name-field-is-leafref', "Is the library's Name column FileLeafRef",
           titledName.includes('FileLeafRef')
             ? 'THE COLUMN TITLED Name IS FileLeafRef'
             : 'FileLeafRef EXISTS UNDER ANOTHER TITLE',
           `${JSON.stringify(shape)}. Field(s) titled 'Name': `
           + `${JSON.stringify(titledName)}. ReadOnlyField is what decides whether `
           + 'a rename can be written through it at all, so read it beside '
           + 'library.file.file-rename rather than on its own.');
  }

  // ---- the library's own folder, read rather than assembled -----------
  // SharePoint derives a library's folder name from its title at creation and
  // the web may sit under /sites/<name>, so a server-relative path built here
  // would be a guess wearing an address's clothes. Every later call addresses
  // the file through what this read returns.
  const root = await spGet(`${listPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = root.ok && root.body ? root.body.ServerRelativeUrl : null;
  if (!folderUrl) {
    record('library.file.upload-path-files-add', 'What Files/add uploads and what it hands back', 'NOT ESTABLISHED',
           `the library's RootFolder did not read back (HTTP ${root.status}), so `
           + 'there is no address to upload to. Nothing after this was attempted.');
    return report();
  }

  // ---- upload-path-files-add: the canonical upload --------------------
  digest = await getDigest();
  const uploaded = await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')`
    + `/Files/add(url='${FILE}',overwrite=true)`,
    'dbml-sharepoint file-operations probe. Safe to delete.', digest);
  const returned = uploaded.ok && uploaded.body ? uploaded.body : null;
  record('library.file.upload-path-files-add', 'What Files/add uploads and what it hands back',
         uploaded.ok ? (returned ? 'UPLOADED, ENTITY RETURNED'
                                 : 'UPLOADED, NO ENTITY PARSED')
                     : isRefusal(uploaded.status) ? 'REFUSED' : 'NOT ESTABLISHED',
         uploaded.ok
           ? (returned
             ? `HTTP ${uploaded.status}. The call returned ${Object.keys(returned).length} `
               + `propertie(s): ${JSON.stringify(Object.keys(returned))}. Of those, `
               + `${JSON.stringify({
                 Name: returned.Name, ServerRelativeUrl: returned.ServerRelativeUrl,
                 Length: returned.Length, MajorVersion: returned.MajorVersion,
                 MinorVersion: returned.MinorVersion, CheckOutType: returned.CheckOutType,
                 Level: returned.Level, Exists: returned.Exists,
                 UniqueId: returned.UniqueId,
               })}. This is the entity every later question addresses the file by.`
             : `HTTP ${uploaded.status}, but the response body did not parse as JSON: `
               + `${uploaded.text.slice(0, 220)}. The upload happened; what the call `
               + 'hands back is unobserved on this run.')
           : isRefusal(uploaded.status)
             ? `HTTP ${uploaded.status}: ${uploaded.text.slice(0, 300)}. Read the body `
               + 'before treating this as the library answer, because a 404 here is a '
               + 'wrong address rather than a refusal.'
             : `HTTP ${uploaded.status}: ${uploaded.text.slice(0, 300)}. Not the server `
               + 'refusing the content, so this run has not established what Files/add '
               + 'does. Re-run.');

  // Prefer the address SharePoint returned over one assembled from parts. The
  // fallback is recorded wherever it is used, so a reader can tell which of
  // the two a later verdict rested on.
  const fromServer = Boolean(returned && returned.ServerRelativeUrl);
  const fileUrl = fromServer ? returned.ServerRelativeUrl : `${folderUrl}/${FILE}`;
  const filePath = `web/GetFileByServerRelativeUrl('${fileUrl}')`;

  const items = await spGet(
    `${listPath}/items?$select=Id,Title,FileLeafRef,FileRef,FileSystemObjectType`
    + `&$filter=FileLeafRef eq '${FILE}'`);
  // An empty result is `undefined`, not null, and `undefined === null` is
  // false, so every guard below would sail past and dereference nothing.
  const rows = (items.ok && items.body && items.body.value) || [];
  const row = rows.length ? rows[0] : null;
  const itemId = row ? row.Id : null;

  // ---- control-missing-column-refused: NEGATIVE CONTROL ---------------
  let controlHeld = false;
  if (itemId === null) {
    record('library.file.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused', 'NOT ESTABLISHED',
           `no list item was found for '${FILE}' (HTTP ${items.status}), so there was `
           + 'nothing to send a nonsense write to. Every REFUSED below this line is '
           + 'unproven rather than answered.');
  } else {
    digest = await getDigest();
    const junk = await spPost(`${listPath}/items(${itemId})`,
                              { NoSuchColumnAtAll: 'x' }, digest,
                              { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    controlHeld = !junk.ok && isRefusal(junk.status);
    record('library.file.control-missing-column-refused', 'NEGATIVE CONTROL: a MERGE naming a missing column on a file item is refused',
           junk.ok ? 'FAIL' : isRefusal(junk.status) ? 'PASS' : 'NOT ESTABLISHED',
           junk.ok
             ? 'a MERGE naming a column that does not exist was ACCEPTED on a file '
               + "item. This probe cannot tell a refused metadata write from a "
               + 'successful one, so the rename and the check-out answers are void '
               + 'whichever way they go'
             : isRefusal(junk.status)
               ? `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`
               : `the request failed with HTTP ${junk.status}, which is not the server `
                 + 'refusing the write. The rows depending on this control are '
                 + `unproven rather than answered: ${junk.text.slice(0, 200)}`);
  }

  // ---- file-system-object-type: file, folder, or neither --------------
  record('library.file.file-system-object-type', "An uploaded file's FileSystemObjectType",
         row === null ? 'NOT ESTABLISHED'
           : row.FileSystemObjectType === 0 ? 'FILE (0)'
             : row.FileSystemObjectType === 1 ? 'FOLDER (1)'
               : 'NEITHER FILE NOR FOLDER',
         row === null
           ? `the uploaded file has no readable list item (HTTP ${items.status})`
           : `${JSON.stringify(row)}. Learn documents Invalid = -1, File = 0, `
             + 'Folder = 1, Web = 2, so this says which of the four SharePoint '
             + 'thinks a Files/add upload produced.');

  // ---- versioning-read-back: does an update make a version? -----------
  // Asked BEFORE check-out, so any change in the count belongs to the content
  // update alone. A check-in creates a version too, and running it first would
  // leave two causes and one observation.
  const listMeta = await spGet(
    `${listPath}?$select=EnableVersioning,EnableMinorVersions,MajorVersionLimit`);
  const settings = listMeta.ok && listMeta.body ? listMeta.body : null;
  const fileBefore = await spGet(
    `${filePath}?$select=MajorVersion,MinorVersion,UiVersionLabel,Length`);
  const versionsBefore = await spGet(`${filePath}/Versions`);
  const countBefore = versionCount(versionsBefore);

  digest = await getDigest();
  const rewritten = await rawPost(
    `${filePath}/$value`,
    'dbml-sharepoint file-operations probe, second revision. Safe to delete.',
    digest, { 'X-HTTP-Method': 'PUT' });
  const versionsAfter = await spGet(`${filePath}/Versions`);
  const countAfter = versionCount(versionsAfter);
  const fileAfter = await spGet(
    `${filePath}?$select=MajorVersion,MinorVersion,UiVersionLabel,Length`);
  const versionEvidence =
    `list settings ${JSON.stringify(settings)}; file before `
    + `${JSON.stringify(fileBefore.ok ? fileBefore.body : null)}, after `
    + `${JSON.stringify(fileAfter.ok ? fileAfter.body : null)}; Versions count `
    + `${countBefore} -> ${countAfter} (null means the collection was not read: `
    + `HTTP ${versionsBefore.status} then HTTP ${versionsAfter.status})`;
  if (!rewritten.ok) {
    record('library.file.versioning-read-back', 'Does REST expose versions, and does a content update add one',
           isRefusal(rewritten.status) ? 'CONTENT UPDATE REFUSED' : 'NOT ESTABLISHED',
           `the $value PUT came back HTTP ${rewritten.status}: `
           + `${rewritten.text.slice(0, 240)}. Nothing changed the file, so a count `
           + `that did not move says nothing about versioning. ${versionEvidence}`);
  } else if (countBefore === null || countAfter === null) {
    record('library.file.versioning-read-back', 'Does REST expose versions, and does a content update add one',
           'NOT ESTABLISHED',
           'the content update succeeded but the version collection was not read on '
           + `at least one side, so there is no before-and-after. ${versionEvidence}`);
  } else {
    record('library.file.versioning-read-back', 'Does REST expose versions, and does a content update add one',
           countAfter > countBefore ? 'A CONTENT UPDATE ADDS A VERSION'
                                    : 'NO NEW VERSION',
           countAfter > countBefore
             ? `REST exposes the collection and the update added ${countAfter - countBefore} `
               + `version(s). ${versionEvidence}`
             : 'REST exposes the collection and the update added nothing to it. Read '
               + 'EnableVersioning in the settings below before treating this as a '
               + `platform limit rather than a library that has versioning off. ${versionEvidence}`);
  }

  // ---- check-out-check-in: does the lock model reach REST? ------------
  digest = await getDigest();
  const checkedOut = await spPost(`${filePath}/checkout`, {}, digest);
  const whileOut = await spGet(`${filePath}?$select=CheckOutType,Level`);
  let checkedIn = null;
  let undone = null;
  if (checkedOut.ok) {
    digest = await getDigest();
    checkedIn = await spPost(
      `${filePath}/checkin(comment='dbml-sharepoint probe',checkintype=1)`, {}, digest);
    if (!checkedIn.ok) {
      // Housekeeping, not a question. A file left checked out would refuse the
      // rename and the delete below for a reason that has nothing to do with
      // either of them, and both would report a platform finding about it.
      digest = await getDigest();
      undone = await spPost(`${filePath}/undocheckout`, {}, digest);
    }
  }
  const afterCheckIn = await spGet(`${filePath}?$select=CheckOutType,Level`);
  const lockEvidence =
    `checkout HTTP ${checkedOut.status}; while out `
    + `${JSON.stringify(whileOut.ok ? whileOut.body : null)}; checkin HTTP `
    + `${checkedIn ? checkedIn.status : 'not attempted'}; after `
    + `${JSON.stringify(afterCheckIn.ok ? afterCheckIn.body : null)}`
    + (undone ? `; undocheckout HTTP ${undone.status}` : '')
    + '. CheckOutType is Online 0, Offline 1, None 2 and Level is Published 1, '
    + 'Draft 2, Checkout 255.';
  if (!checkedOut.ok) {
    record('library.file.check-out-check-in', 'Do CheckOut and CheckIn apply to a file over REST',
           isRefusal(checkedOut.status) ? 'CHECKOUT REFUSED' : 'NOT ESTABLISHED',
           `${checkedOut.text.slice(0, 240)}. ${lockEvidence} A 404 here would be the `
           + 'endpoint spelling rather than a refusal, so read the body.');
  } else if (readFailed(whileOut) || readFailed(afterCheckIn)) {
    record('library.file.check-out-check-in', 'Do CheckOut and CheckIn apply to a file over REST',
           'NOT ESTABLISHED',
           `the calls were accepted but a CheckOutType read-back failed, so the state `
           + `they produced is unobserved. ${lockEvidence}`);
  } else if (!checkedIn.ok) {
    record('library.file.check-out-check-in', 'Do CheckOut and CheckIn apply to a file over REST',
           'CHECKED OUT, CHECK-IN REFUSED',
           `CheckOut worked and CheckIn did not: ${checkedIn.text.slice(0, 240)}. `
           + `${lockEvidence} The rename and delete below ran against whatever state `
           + 'the after read reports, which is why it is printed.');
  } else {
    record('library.file.check-out-check-in', 'Do CheckOut and CheckIn apply to a file over REST',
           whileOut.body.CheckOutType === 0 && afterCheckIn.body.CheckOutType === 2
             ? 'BOTH APPLY, AND THE STATE READS BACK'
             : 'BOTH ACCEPTED, STATE DID NOT MOVE AS DOCUMENTED',
           lockEvidence);
  }

  // ---- file-rename: writing FileLeafRef through the list item ---------
  // The path Learn documents for renaming: reach the file as a list item and
  // write FileLeafRef. /moveto(newurl=,flags=) is the other documented path
  // and is a different method, so it is a different question and is not asked
  // here. If this one is refused, that is the probe to write next.
  const lockBeforeRename = afterCheckIn.ok && afterCheckIn.body
    ? afterCheckIn.body.CheckOutType : null;
  let renamedRow = null;
  if (itemId === null) {
    record('library.file.file-rename', 'Can FileLeafRef be written as a rename, and does it read back', 'NOT ESTABLISHED',
           `no list item was found for '${FILE}', so there was nothing to rename`);
  } else {
    digest = await getDigest();
    const rename = await spPost(`${listPath}/items(${itemId})`,
                                { FileLeafRef: RENAMED }, digest,
                                { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    const readBack = await spGet(
      `${listPath}/items(${itemId})?$select=Id,Title,FileLeafRef,FileRef`);
    renamedRow = readBack.ok && readBack.body ? readBack.body : null;
    // A failed read-back is not a discard. Conflating them would let a
    // throttled GET print a claim about what SharePoint stored.
    if (readFailed(readBack)) {
      record('library.file.file-rename', 'Can FileLeafRef be written as a rename, and does it read back', 'NOT ESTABLISHED',
             `the MERGE returned HTTP ${rename.status}, but the item read-back failed `
             + `(HTTP ${readBack.status}), so this run has no evidence either way.`);
    } else {
      const took = renamedRow.FileLeafRef === RENAMED;
      const refPoints = String(renamedRow.FileRef || '').endsWith(`/${RENAMED}`);
      record('library.file.file-rename', 'Can FileLeafRef be written as a rename, and does it read back',
             !rename.ok
               ? (isRefusal(rename.status) ? 'REFUSED' : 'NOT ESTABLISHED')
               : took && refPoints ? 'RENAMED, AND BOTH COLUMNS FOLLOW'
                 : took ? 'FileLeafRef MOVED, FileRef DID NOT'
                   : 'ACCEPTED THEN DISCARDED',
             `${JSON.stringify(renamedRow)}. CheckOutType before the attempt was `
             + `${lockBeforeRename}. `
             + (!rename.ok
               ? `HTTP ${rename.status}: ${rename.text.slice(0, 240)}. /moveto is the `
                 + 'other documented rename path, is a different method, and is '
                 + 'unprobed.'
               : took && refPoints
                 ? 'A rename is an ordinary metadata write on a library, which is a '
                   + 'write this tool could emit.'
                 : 'The two columns disagree about the name, so one of them is not '
                   + 'the file name this tool can key to.'));
    }
  }

  // ---- file-delete: recycle, and does the bin show it? ----------------
  // Recycled, never purged, the same rule rollback.js.j2 follows: a mistake
  // has to stay recoverable from the site recycle bin.
  //
  // Two spellings are tried because getting this wrong is indistinguishable
  // from a finding. Learn documents `/recycle` for a file and rollback.js.j2
  // uses `/recycle()` on a list item; a 404 from the wrong one would be read
  // as a refusal by isRefusal and print as a claim about SharePoint. Which
  // spelling answered is recorded, so nothing rests on the guess.
  const targetUrl = (renamedRow && renamedRow.FileRef) || fileUrl;
  digest = await getDigest();
  let recycled = await spPost(`web/GetFileByServerRelativeUrl('${targetUrl}')/recycle`,
                              {}, digest);
  let spelling = '/recycle';
  if (!recycled.ok) {
    digest = await getDigest();
    const parenthesised = await spPost(
      `web/GetFileByServerRelativeUrl('${targetUrl}')/recycle()`, {}, digest);
    if (parenthesised.ok) {
      recycled = parenthesised;
      spelling = '/recycle()';
    }
  }
  const recycledId = recycled.ok && recycled.body
    ? String(recycled.body.value !== undefined ? recycled.body.value : recycled.body)
    : null;
  const bin = await spGet('web/RecycleBin?$select=Id,Title,LeafName,DirName&$top=200');
  const binRows = (bin.ok && bin.body && bin.body.value) || [];
  // Two matches, kept apart on purpose. The id Recycle returned identifies THIS
  // deletion; a leaf name matches an entry a previous run left in the bin just
  // as well, so a name-only match is corroboration and is reported as such.
  const byId = recycledId !== null && binRows.some(
    (entry) => String(entry.Id).toLowerCase() === recycledId.toLowerCase());
  const byName = binRows.some(
    (entry) => entry.LeafName === RENAMED || entry.LeafName === FILE);
  const stillThere = await spGet(`web/GetFileByServerRelativeUrl('${targetUrl}')?$select=Exists`);
  record('library.file.file-delete', 'Does Recycle remove the file and put it in the recycle bin',
         !recycled.ok
           ? (isRefusal(recycled.status) ? 'REFUSED' : 'NOT ESTABLISHED')
           : readFailed(bin) ? 'RECYCLED, BIN UNREADABLE'
             : byId ? 'RECYCLED, AND IN THE BIN'
               : byName ? 'RECYCLED, BIN MATCHES BY NAME ONLY'
                 : 'RECYCLED, BIN DOES NOT SHOW IT',
         !recycled.ok
           ? `both spellings failed, last HTTP ${recycled.status}: `
             + `${recycled.text.slice(0, 240)}. Addressed '${targetUrl}', which came `
             + `from ${renamedRow ? 'the renamed item' : fromServer ? 'the upload response'
               : 'a path assembled from the library folder'}.`
           : `${spelling} answered HTTP ${recycled.status} and returned `
             + `${JSON.stringify(recycledId)}. Re-reading the file gave HTTP `
             + `${stillThere.status} (${JSON.stringify(stillThere.ok ? stillThere.body : null)}). `
             + (readFailed(bin)
               ? `web/RecycleBin did not read back (HTTP ${bin.status}). That endpoint `
                 + 'is the one URL in this probe with no Learn citation, so a failure '
                 + 'here may be the spelling and not the tenant. The file is gone from '
                 + 'the library either way; where it went is unobserved.'
               : byId
                 ? `the bin holds ${binRows.length} entrie(s) and one of them carries `
                   + 'the id Recycle returned, so this deletion is recoverable.'
                 : byName
                   ? `the bin holds ${binRows.length} entrie(s) and one of them has this `
                     + "file's leaf name, but not the id Recycle returned. A previous "
                     + 'run leaves an entry with the same name, so this is corroboration '
                     + 'rather than identification.'
                   : `the bin holds ${binRows.length} entrie(s) and none of them matches `
                     + 'this file by id or by leaf name. Read this before treating a '
                     + 'library delete as recoverable.'));

  // ---- void what the control cannot vouch for -------------------------
  // The control decides whether a REFUSED above is an answer about SharePoint
  // or a sentence with nothing behind it. The evidence on each row already
  // says so in prose, and prose is not what a reader downstream sorts on, so
  // the state is corrected here too. VOID is not an outcome head the
  // classifier knows, so it is passed rather than read off the prose.
  if (!controlHeld) {
    for (const id of ['library.file.versioning-read-back',
                      'library.file.check-out-check-in',
                      'library.file.file-rename',
                      'library.file.file-delete']) {
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
