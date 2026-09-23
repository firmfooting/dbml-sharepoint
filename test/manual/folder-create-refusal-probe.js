/**
 * dbml-sharepoint PROBE: WHY A DECLARED FOLDER CREATE IS REFUSED
 *
 * REVISION: efacd22c
 *
 * ONE QUESTION:
 *   folders/add(url=) is measured working. On a live deploy it answered
 *   HTTP 500 "Cannot create folder" for every declared folder. Which of the
 *   two things that changed since the measurement is responsible?
 *
 * `library.folder.creation-path` (2026-09-03, folder-probe.js) measured the
 * call as accepted, and templates/deploy/_folders.js.j2 rests on it. That
 * measurement created a folder named `dbmlsp-folder-probe` in a library
 * created by POSTing `{Title, BaseTemplate: 101, Description}`. What the
 * deploy sends differs in two ways at once, and either could be the cause:
 *
 *   1. The folder NAME carries spaces. Every folder the shipped
 *      legal-compliance-register declares does ("Clinical services"), and no
 *      probe has created a folder whose name is not a single hyphenated word.
 *   2. The LIBRARY was created with `ContentTypesEnabled: false`, which
 *      generators/jsgen.py sets on every list it declares and which no probe
 *      has put on a library before creating a folder in it.
 *
 * So this is a two by two over those variables, with the measured
 * combination as the control. A single run says which cell refuses.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     Two document libraries are created (BaseTemplate 101), one with the
 *     content types switch left alone and one with it off. The same question
 *     folder-probe.js asks, by the same method, so it keeps the same id.
 *   library.folder.control-plain-name-default-library
 *     CONTROL: folders/add(url='dbmlsp-plain-name') on the library built the
 *     way the 2026-09-03 run built one. This is that measurement, repeated
 *     here. If this cell refuses, the cause is neither variable and nothing
 *     below can be read as evidence about either.
 *   library.folder.spaced-name-default-library
 *     The name varied alone: folders/add(url='dbmlsp spaced name') on the
 *     same library.
 *   library.folder.plain-name-content-types-disabled
 *     The library varied alone: the hyphenated name on the library created
 *     with ContentTypesEnabled false.
 *   library.folder.spaced-name-content-types-disabled
 *     Both varied, which is exactly what the deploy sends and what answered
 *     HTTP 500.
 *   library.folder.add-using-path-spaced-name
 *     The documented ResourcePath spelling for the same write, on the same
 *     library: web/Folders/AddUsingPath(decodedurl='<root>/<spaced name>').
 *     Asked whatever the cells above say, because a spelling that works
 *     everywhere is worth knowing about even when the legacy one does too.
 *
 * OBSERVED, NEVER ASSERTED
 *   Each library's ContentTypesEnabled, EnableFolderCreation and
 *   BaseTemplate as they read back after creation, and each created folder's
 *   ServerRelativeUrl. These are recorded in the evidence of the rows above.
 *   Asserting a value this probe did not set would make the experiment fail
 *   the moment the tenant's defaults differ, which looks identical to the
 *   refusal being measured.
 *
 * NOT MEASURED HERE
 *   A name carrying characters analysis/file_names.py already refuses (`#`,
 *   `%`), a name longer than the path budget, and whether the switch can be
 *   turned back on after creation. Nothing here changes a setting after a
 *   library is made.
 *
 * MICROSOFT LEARN CITATIONS
 *   Folder creation via `Folders/add(url=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Folder creation via `Folders/AddUsingPath(decodedurl=)`, and the
 *   ResourcePath APIs generally:
 *     "Supporting % and # in files and folders with the ResourcePath API"
 *   List creation via POST to `web/lists`, and ContentTypesEnabled:
 *     "Working with lists and list items with REST", "List.ContentTypesEnabled
 *     Property" (CSOM)
 *   EnableFolderCreation:
 *     "List.EnableFolderCreation Property" (CSOM)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the two libraries it created.
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
  //
  // expectedId is OPTIONAL because most callers have no claimed Id to bracket
  // with, and the behaviour without one is unchanged. Supply one and every
  // request below addresses that list Id instead of the title, so a title
  // rebound mid-run cannot redirect the deletes or the recycle onto a list
  // this run never owned.
  //
  // DOCUMENTED: `web/lists(guid'<id>')` is the list resource, and `/items`
  // and `/items(<id>)` hang off it (Working with lists and list items with
  // REST, and the CSOM/REST API index, both checked 2026-09-23).
  // NOT DOCUMENTED: `/recycle` on the by-Id form appears on no Learn page.
  // It is the call this project has live evidence for with only the
  // addressing changed, and an unsupported URL fails visibly here rather
  // than losing somebody's list. One CLEANUP run settles it; see issue #611.
  const resetList = async (title, expectedId = null) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
      return false;
    }
    // An Id that is not a GUID would be spliced into a URL that addresses
    // something else, so it fails closed instead of being sent.
    const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (expectedId !== null && !GUID.test(String(expectedId))) {
      log('FAIL', `CLEANUP: '${expectedId}' is not a list Id, so nothing was deleted or `
                  + `recycled under '${title}'.`);
      return false;
    }
    const listPath = expectedId === null
      ? `web/lists/getbytitle('${title}')`
      : `web/lists(guid'${expectedId}')`;
    const found = await spGet(expectedId === null ? listPath : `${listPath}?$select=Id`);
    if (!found.ok) {
      log('INFO', `CLEANUP: no list named '${title}' to remove.`);
      return false;
    }
    // Addressing by Id still gets read back, because every destructive
    // request below rests on this one answer.
    const answeredId = found.body && found.body.Id
      ? String(found.body.Id).replace(/[{}]/g, '').toLowerCase() : null;
    if (expectedId !== null && answeredId !== String(expectedId).toLowerCase()) {
      log('FAIL', `CLEANUP: list ${expectedId} answered as ${answeredId}, so nothing was `
                  + `deleted or recycled under '${title}'.`);
      return false;
    }
    log('INFO', `CLEANUP: removing list '${title}' and its items.`);

    // Items first. Recycling the list takes them with it, but doing this
    // explicitly still clears the data if the list itself cannot be
    // removed. A locked or no-delete list would otherwise leave rows from
    // a previous run answering this run's questions.
    let digest = await getDigest();
    const items = await spGet(`${listPath}/items?$select=Id&$top=5000`);
    const rows = (items.ok && items.body && items.body.value) || [];
    for (const row of rows) {
      digest = await getDigest();
      await spPost(`${listPath}/items(${row.Id})`, {}, digest,
                   { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    }
    if (rows.length) log('INFO', `CLEANUP: deleted ${rows.length} item(s).`);
    if (rows.length === 5000) {
      log('INFO', 'CLEANUP: hit the 5000-row page limit; re-run to clear the rest.');
    }

    digest = await getDigest();
    const gone = await spPost(`${listPath}/recycle`, {}, digest);
    // The Id is named where there is one, because a repair by hand off the
    // title would go to whatever the title resolves to now.
    const which = expectedId === null ? `'${title}'` : `'${title}' (list ${expectedId})`;
    if (gone.ok) {
      log('OK', `CLEANUP: recycled list ${which}. It is restorable from the recycle bin.`);
    } else {
      log('FAIL', `CLEANUP: could not recycle ${which}: HTTP ${gone.status} ${gone.text.slice(0, 200)}`);
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

  log('INFO', 'probe revision efacd22c. Quote this when reporting results.');

  const LIB_DEFAULT = 'dbmlsp Probe Folder Default';
  const LIB_NOCT = 'dbmlsp Probe Folder NoCT';
  const PLAIN = 'dbmlsp-plain-name';
  const SPACED = 'dbmlsp spaced name';
  const PATH_SPACED = 'dbmlsp spaced path name';

  const listPath = (title) => `web/lists/getbytitle('${title}')`;

  const Q = {
    fixture: 'Two document libraries are created (BaseTemplate 101), one with ContentTypesEnabled left alone and one with it false',
    control: 'CONTROL: does folders/add(url=<hyphenated name>) still answer on a library created the way the 2026-09-03 run created one',
    spacedDefault: 'Does folders/add(url=<name with spaces>) answer on that same library',
    plainNoCt: 'Does folders/add(url=<hyphenated name>) answer on a library created with ContentTypesEnabled false',
    spacedNoCt: 'Does folders/add(url=<name with spaces>) answer on a library created with ContentTypesEnabled false, which is what the deploy sends',
    addUsingPath: 'Does the documented Folders/AddUsingPath(decodedurl=) spelling create a spaced name on that library',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create two DOCUMENT LIBRARIES on ${WEB}: '${LIB_DEFAULT}' with the`);
    log('INFO', `content types switch left alone, and '${LIB_NOCT}' with ContentTypesEnabled false.`);
    log('INFO', `Would then attempt folders/add for '${PLAIN}' and '${SPACED}' in each,`);
    log('INFO', `and Folders/AddUsingPath for '${PATH_SPACED}' in '${LIB_NOCT}'.`);
    if (CLEANUP) {
      log('INFO', 'CLEANUP is ON: both libraries would be RECYCLED first.');
    } else {
      log('INFO', 'CLEANUP is off: existing libraries and their contents would be reused.');
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
    'library.folder.control-plain-name-default-library',
    'library.folder.spaced-name-default-library',
    'library.folder.plain-name-content-types-disabled',
    'library.folder.spaced-name-content-types-disabled',
    'library.folder.add-using-path-spaced-name',
  ];

  expect('library.doc-lib.fixture-library-created', Q.fixture);
  expect('library.folder.control-plain-name-default-library', Q.control);
  expect('library.folder.spaced-name-default-library', Q.spacedDefault);
  expect('library.folder.plain-name-content-types-disabled', Q.plainNoCt);
  expect('library.folder.spaced-name-content-types-disabled', Q.spacedNoCt);
  expect('library.folder.add-using-path-spaced-name', Q.addUsingPath);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;
  // Quotes doubled, slashes and spaces left for fetch to encode. The deploy's
  // own spelling, so what is measured here is the endpoint and not a second
  // encoding this project does not send.
  const pathLiteral = (path) => String(path).replace(/'/g, "''");

  await resetList(LIB_DEFAULT);
  await resetList(LIB_NOCT);

  // ---- fixture: the two libraries --------------------------------------
  const makeLibrary = async (title, extra) => {
    const existing = await spGet(listPath(title));
    if (existing.ok) return { made: true, reused: true };
    const digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint folder create refusal probe. Safe to delete.',
      ...extra,
    }, digest);
    return { made: made.ok, reused: false, detail: made.ok ? null : short(made) };
  };

  const libDefault = await makeLibrary(LIB_DEFAULT, {});
  const libNoCt = await makeLibrary(LIB_NOCT, { ContentTypesEnabled: false });
  if (!libDefault.made || !libNoCt.made) {
    record('library.doc-lib.fixture-library-created', Q.fixture, 'FAIL',
           `'${LIB_DEFAULT}': ${libDefault.made ? 'ok' : libDefault.detail}; `
           + `'${LIB_NOCT}': ${libNoCt.made ? 'ok' : libNoCt.detail}`);
    voidAll(IDS, 'the library fixtures did not both build, so no cell can be compared with another.');
    return report();
  }

  // Read back what each library actually is. OBSERVED, not asserted: the
  // tenant's defaults are what this probe is trying to learn, so a mismatch
  // here is a finding to print rather than a reason to stop.
  const describe = async (title) => {
    const r = await spGet(`${listPath(title)}?$select=BaseTemplate,ContentTypesEnabled,EnableFolderCreation`);
    if (readFailed(r)) return `'${title}' did not read back (HTTP ${r.status})`;
    return `'${title}' BaseTemplate ${r.body.BaseTemplate}, ContentTypesEnabled ${r.body.ContentTypesEnabled}, EnableFolderCreation ${r.body.EnableFolderCreation}`;
  };
  const shapes = `${await describe(LIB_DEFAULT)}; ${await describe(LIB_NOCT)}`;
  record('library.doc-lib.fixture-library-created', Q.fixture, 'PASS',
         `${libDefault.reused ? 'reused' : 'created'} '${LIB_DEFAULT}', `
         + `${libNoCt.reused ? 'reused' : 'created'} '${LIB_NOCT}'. ${shapes}`);

  const rootOf = async (title) => {
    const r = await spGet(`${listPath(title)}/RootFolder?$select=ServerRelativeUrl`);
    return readFailed(r) ? null : r.body.ServerRelativeUrl;
  };
  const rootDefault = await rootOf(LIB_DEFAULT);
  const rootNoCt = await rootOf(LIB_NOCT);
  if (!rootDefault || !rootNoCt) {
    voidAll(IDS, 'a library RootFolder did not read back, so no folder path could be built.');
    return report();
  }

  // ---- one cell of the two by two --------------------------------------
  // Recorded as PASS when the call is accepted AND the folder reads back,
  // because a 200 that leaves nothing behind is the silent failure this
  // project exists to catch.
  const addFolder = async (id, question, title, root, name) => {
    const digest = await getDigest();
    const res = await spPost(
      `web/GetFolderByServerRelativeUrl('${pathLiteral(root)}')/folders/add(url='${pathLiteral(name)}')`,
      {}, digest);
    if (!res.ok) {
      record(id, question, isRefusal(res.status) ? 'REFUSED' : 'FAIL', short(res));
      return false;
    }
    const back = await spGet(`web/GetFolderByServerRelativeUrl('${pathLiteral(`${root}/${name}`)}')?$select=Exists,Name,ServerRelativeUrl`);
    const exists = !readFailed(back) && back.body.Exists === true;
    record(id, question, exists ? 'PASS' : 'FAIL',
           exists
             ? `HTTP ${res.status}, and the folder reads back at ${back.body.ServerRelativeUrl}`
             : `HTTP ${res.status} accepted the write, but the folder did not read back (HTTP ${back.status})`);
    return exists;
  };

  const controlHeld = await addFolder(
    'library.folder.control-plain-name-default-library', Q.control,
    LIB_DEFAULT, rootDefault, PLAIN);
  if (!controlHeld) {
    voidAll(IDS.slice(1),
            'the control cell refused, so this run cannot attribute a refusal to the name or to the '
            + 'content types switch. Something outside both variables is blocking folder creation here.');
    return report();
  }

  await addFolder('library.folder.spaced-name-default-library', Q.spacedDefault,
                  LIB_DEFAULT, rootDefault, SPACED);
  await addFolder('library.folder.plain-name-content-types-disabled', Q.plainNoCt,
                  LIB_NOCT, rootNoCt, PLAIN);
  await addFolder('library.folder.spaced-name-content-types-disabled', Q.spacedNoCt,
                  LIB_NOCT, rootNoCt, SPACED);

  // ---- the documented ResourcePath spelling ----------------------------
  {
    const digest = await getDigest();
    const res = await spPost(
      `web/Folders/AddUsingPath(decodedurl='${pathLiteral(`${rootNoCt}/${PATH_SPACED}`)}')`,
      {}, digest);
    if (!res.ok) {
      record('library.folder.add-using-path-spaced-name', Q.addUsingPath,
             isRefusal(res.status) ? 'REFUSED' : 'FAIL', short(res));
    } else {
      const back = await spGet(`web/GetFolderByServerRelativeUrl('${pathLiteral(`${rootNoCt}/${PATH_SPACED}`)}')?$select=Exists,ServerRelativeUrl`);
      const exists = !readFailed(back) && back.body.Exists === true;
      record('library.folder.add-using-path-spaced-name', Q.addUsingPath,
             exists ? 'PASS' : 'FAIL',
             exists
               ? `HTTP ${res.status}, and the folder reads back at ${back.body.ServerRelativeUrl}`
               : `HTTP ${res.status} accepted the write, but the folder did not read back (HTTP ${back.status})`);
    }
  }

  return report();
})();
