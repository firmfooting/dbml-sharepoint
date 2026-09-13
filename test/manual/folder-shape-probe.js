/**
 * dbml-sharepoint PROBE: WHAT THE FOLDER STEP SEES WHEN A FILE IS IN THE WAY
 *
 * REVISION: 993cf930
 *
 * ONE QUESTION:
 *   When a FILE stands at the path where the deploy declared a folder, what
 *   does each read and write the folder step makes answer?
 *
 * templates/deploy/_folders.js.j2 reads each declared folder through
 * GetFolderByServerRelativeUrl, treats 404, an absent-400 and Exists=false
 * as "not there", verifies a present folder's list item by filtering the
 * library on FileLeafRef and requiring FileSystemObjectType 1, and creates
 * an absent one through folders/add. Every one of those calls was measured
 * on a folder (library.folder.* in folder-probe.js). None was measured with
 * a file at the path, and the step refuses a file where a folder was
 * declared on the strength of what it assumes those answers are. This probe
 * uploads one file and asks each call about it.
 *
 * The write shapes are the deploy's: the same GetFolderByServerRelativeUrl
 * read with $select=Exists,Name,ServerRelativeUrl, the same items filter,
 * and the same folders/add(url=) POST.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101).
 *   library.folder.control-missing-path-read
 *     CONTROL: a folder read on a path nothing occupies answers 404, an
 *     absent-400 or Exists=false, which is what the deploy takes as "not
 *     there". If a missing path reads as present, nothing below can be
 *     told apart.
 *   library.folder.folder-read-on-file-path
 *     A folder read on the uploaded FILE's path: absent, present, or
 *     refused?
 *   library.folder.item-shape-of-file-by-name
 *     The items filter FileLeafRef eq '<file>': is the file's item served,
 *     and does it read FileSystemObjectType 0?
 *   library.folder.add-under-existing-file-name
 *     folders/add(url='<file>') with the file already there: refused, or
 *     accepted, and what stands at the path afterwards?
 *   library.folder.add-under-existing-folder-name
 *     folders/add(url='<folder>') with the folder already there: refused,
 *     or accepted as a no-op?
 *
 * NOT MEASURED HERE
 *   A file INSIDE the declared folder, which the deploy never touches, and
 *   what the library page shows for any of these states.
 *
 * MICROSOFT LEARN CITATIONS
 *   Folder read, folder creation and file upload:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   FileSystemObjectType values (Invalid -1, File 0, Folder 1, Web 2):
 *     "FileSystemObjectType enumeration" (CSOM)
 *   List creation via POST to `web/lists` and items via `items`:
 *     "Working with lists and list items with REST"
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

  log('INFO', 'probe revision 993cf930. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe Shape Library';
  const libPath = `web/lists/getbytitle('${LIB}')`;
  const FILE = 'dbmlsp-shape-probe.txt';
  const FOLDER = 'dbmlsp-shape-folder';
  const MISSING = 'dbmlsp-shape-nothing-here';

  const Q = {
    fixture: 'A document library is created (BaseTemplate 101)',
    control: 'CONTROL: does a folder read on a path nothing occupies answer as absent (404, absent-400 or Exists=false)',
    fileRead: 'What does a folder read on the path of a FILE answer',
    fileShape: 'Does the items filter FileLeafRef eq <file> serve the file, and with FileSystemObjectType 0',
    addOverFile: 'Is folders/add(url=<file>) refused when a file of that name is already there, and what stands at the path after',
    addOverFolder: 'Is folders/add(url=<folder>) refused when the folder is already there',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, upload '${FILE}' to its root,`);
    log('INFO', `create the folder '${FOLDER}' beside it, then attempt folders/add under both names.`);
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing library and its contents would be reused.');
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

  const IDS = [
    'library.folder.control-missing-path-read',
    'library.folder.folder-read-on-file-path',
    'library.folder.item-shape-of-file-by-name',
    'library.folder.add-under-existing-file-name',
    'library.folder.add-under-existing-folder-name',
  ];

  expect('library.doc-lib.fixture-library-created', Q.fixture);
  expect('library.folder.control-missing-path-read', Q.control);
  expect('library.folder.folder-read-on-file-path', Q.fileRead);
  expect('library.folder.item-shape-of-file-by-name', Q.fileShape);
  expect('library.folder.add-under-existing-file-name', Q.addOverFile);
  expect('library.folder.add-under-existing-folder-name', Q.addOverFolder);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;
  const show = (v) => JSON.stringify(v === undefined ? null : v);
  // Quotes doubled, slashes left raw: the deploy's own path spelling.
  const pathLiteral = (path) => String(path).replace(/'/g, "''");

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

  // The deploy's folder read, and how it classifies the answer.
  const readFolder = async (serverRelativeUrl) =>
    spGet(`web/GetFolderByServerRelativeUrl('${pathLiteral(serverRelativeUrl)}')?$select=Exists,Name,ServerRelativeUrl`);
  const classifyRead = (r) => {
    if (r.status === 404) return 'ABSENT (404)';
    if (r.ok && r.body && r.body.Exists === true) return 'PRESENT (Exists true)';
    if (r.ok && r.body && r.body.Exists === false) return 'ABSENT (Exists false)';
    if (r.ok) return 'ANSWERED WITHOUT Exists';
    return isRefusal(r.status) ? `REFUSED (HTTP ${r.status})` : 'NOT ESTABLISHED';
  };
  const describeRead = (r) =>
    `HTTP ${r.status}, ${r.body ? `Exists=${show(r.body.Exists)}, Name=${show(r.body.Name)}` : `body ${show(r.text ? r.text.slice(0, 160) : null)}`}`;
  // The deploy's shape probe: the library filtered on FileLeafRef.
  const itemShape = async (name) => {
    const filter = encodeURIComponent(`FileLeafRef eq '${String(name).replace(/'/g, "''")}'`);
    const r = await spGet(`${libPath}/items?$select=Id,FileSystemObjectType,FileLeafRef&$filter=${filter}&$top=2`);
    const rows = (r.ok && r.body && Array.isArray(r.body.value)) ? r.body.value : [];
    return { r, rows };
  };
  const addFolder = async (rootUrl, name) => {
    const digest = await getDigest();
    return spPost(`web/GetFolderByServerRelativeUrl('${pathLiteral(rootUrl)}')/folders/add(url='${pathLiteral(name)}')`, {}, digest);
  };

  await resetList(LIB);

  let digest = await getDigest();
  const haveLib = await spGet(libPath);
  if (haveLib.ok) {
    record('library.doc-lib.fixture-library-created', Q.fixture, 'ALREADY PRESENT',
           `reusing an existing library '${LIB}'. Set CLEANUP = true for a clean answer`);
  } else {
    const made = await spPost('web/lists', {
      Title: LIB, BaseTemplate: 101,
      Description: 'dbml-sharepoint folder shape probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', Q.fixture,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : short(made));
    if (!made.ok) {
      voidAll(IDS, `fixture incomplete: library creation failed (HTTP ${made.status})`);
      return report();
    }
  }

  const root = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const rootUrl = (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  if (!rootUrl) {
    voidAll(IDS, `the library RootFolder did not read back (HTTP ${root.status})`);
    return report();
  }

  // ---- CONTROL: a path nothing occupies -----------------------------------
  const missing = await readFolder(`${rootUrl}/${MISSING}`);
  const missingHead = classifyRead(missing);
  const controlHeld = missingHead.startsWith('ABSENT');
  record('library.folder.control-missing-path-read', Q.control,
         controlHeld ? 'PASS' : (missingHead.startsWith('PRESENT') ? 'FAIL' : 'NOT ESTABLISHED'),
         `GetFolderByServerRelativeUrl on '${MISSING}' answered ${describeRead(missing)} (${missingHead})`);
  if (!controlHeld) {
    voidAll(IDS.slice(1),
            `the control did not hold (${missingHead}), so an answer below could not be told from a missing path`);
    return report();
  }

  // ---- The file, and each call the deploy would make about it ------------
  digest = await getDigest();
  const up = await rawPost(
    `web/GetFolderByServerRelativeUrl('${pathLiteral(rootUrl)}')/Files/add(url='${FILE}',overwrite=true)`,
    'dbmlsp folder shape probe file', digest);
  if (!up.ok) {
    voidAll(IDS.slice(1, 4), `Files/add failed (${short(up)}), so no file stood at the path`);
  } else {
    const onFile = await readFolder(`${rootUrl}/${FILE}`);
    record('library.folder.folder-read-on-file-path', Q.fileRead, classifyRead(onFile),
           `Files/add answered HTTP ${up.status}; GetFolderByServerRelativeUrl on the file's path answered ${describeRead(onFile)}`);

    const { r: shapeRead, rows } = await itemShape(FILE);
    let shapeHead = 'NOT ESTABLISHED';
    if (shapeRead.ok && rows.length === 0) shapeHead = 'NOT SERVED';
    else if (shapeRead.ok && rows.length) shapeHead = rows[0].FileSystemObjectType === 0 ? 'FILE (0)' : `SERVED AS ${show(rows[0].FileSystemObjectType)}`;
    else if (isRefusal(shapeRead.status)) shapeHead = 'REFUSED';
    record('library.folder.item-shape-of-file-by-name', Q.fileShape, shapeHead,
           `items?$filter=FileLeafRef eq '${FILE}' answered HTTP ${shapeRead.status} with ${rows.length} row(s)`
           + (rows.length ? `; first row FileSystemObjectType=${show(rows[0].FileSystemObjectType)}, FileLeafRef=${show(rows[0].FileLeafRef)}` : ''));

    const addOver = await addFolder(rootUrl, FILE);
    const afterAdd = await readFolder(`${rootUrl}/${FILE}`);
    const { rows: afterRows } = await itemShape(FILE);
    let addHead = 'NOT ESTABLISHED';
    if (!addOver.ok && isRefusal(addOver.status)) addHead = 'REFUSED';
    else if (addOver.ok) {
      const kinds = afterRows.map((row) => row.FileSystemObjectType);
      addHead = kinds.includes(1) ? (kinds.includes(0) ? 'ACCEPTED, FILE AND FOLDER BOTH SERVED' : 'ACCEPTED, FOLDER REPLACED THE FILE') : 'ACCEPTED, FILE STILL THE ONLY ITEM';
    }
    record('library.folder.add-under-existing-file-name', Q.addOverFile, addHead,
           `folders/add(url='${FILE}') with the file in place answered ${short(addOver)}; `
           + `the folder read after answered ${describeRead(afterAdd)}; the items filter served ${afterRows.length} row(s) `
           + `with FileSystemObjectType ${show(afterRows.map((row) => row.FileSystemObjectType))}`);
  }

  // ---- A folder, then folders/add under its name again -------------------
  const madeFolder = await addFolder(rootUrl, FOLDER);
  const folderRead = await readFolder(`${rootUrl}/${FOLDER}`);
  if (!(madeFolder.ok && classifyRead(folderRead).startsWith('PRESENT'))) {
    voidAll([IDS[4]], `the folder to collide with was not created (${short(madeFolder)}; read ${describeRead(folderRead)})`);
    return report();
  }
  const again = await addFolder(rootUrl, FOLDER);
  const readAgain = await readFolder(`${rootUrl}/${FOLDER}`);
  record('library.folder.add-under-existing-folder-name', Q.addOverFolder,
         again.ok ? 'ACCEPTED' : (isRefusal(again.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
         `folders/add(url='${FOLDER}') created the folder (HTTP ${madeFolder.status}); the same call again answered ${short(again)}; `
         + `the folder read after answered ${describeRead(readAgain)}`);

  return report();
})();
