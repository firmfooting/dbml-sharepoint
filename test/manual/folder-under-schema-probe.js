/**
 * dbml-sharepoint PROBE: WHICH DECLARED SETTING REFUSES A FOLDER
 *
 * REVISION: 0fa4c9ba
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
 * If none of them does, the only shape left is to open the library, create
 * the declared folders and close it again, which is what Phase 1.8 and
 * Phase 4.1 already do for a sealed column. The last four rows measure
 * whether that shape is safe rather than assuming it.
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
 *   library.folder.clear-list-validation-to-create
 *     With the list formula cleared again, is the create accepted? This is
 *     the first half of the only shape a fix can take.
 *   library.folder.restore-list-validation-after-folders
 *     Is the formula accepted back onto a library that now holds folders,
 *     and does it read back?
 *   library.folder.folder-survives-restored-validation
 *     Does the folder created in that window still read back afterwards?
 *   library.folder.control-restored-validation-refuses-a-folder
 *     CONTROL: does the restored formula refuse a NEW folder again? A
 *     restore that silently did nothing would make the three rows above
 *     pass while leaving the library unguarded, and they would then be
 *     evidence about the wrong list.
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
    && status !== 408 && status !== 429 && status !== 503; // 503: the other documented throttle

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

  // ---- Fixtures (#559) -----------------------------------------------
  // Why a response carries no reading, or null when it does. Learn documents
  // 429 and 503 as the two SharePoint Online throttle statuses.
  const unanswered = (r) => {
    if (r.ok) {
      return r.body !== null && typeof r.body === 'object'
        ? null : `answered HTTP ${r.status} with no payload`;
    }
    if (r.status === 429 || r.status === 503) return `was throttled (HTTP ${r.status})`;
    if (r.status === 408) return 'timed out (HTTP 408)';
    if (r.status === 401 || r.status === 403) return `was not authorised (HTTP ${r.status})`;
    return isRefusal(r.status) ? `was refused (HTTP ${r.status})` : `did not answer (HTTP ${r.status})`;
  };

  // A voided row keeps its question and is counted apart from open and answered.
  const voidDependents = (ids, reason) => {
    for (const id of ids) {
      const row = RESULTS.find((r) => r.id === id);
      record(id, row ? row.question : id, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // `read` resolves to a harness response ({ ok, status, body }). `declared`
  // maps each property the measurement depends on to a value or a predicate.
  // PASS needs every one read back; otherwise FAIL, void `dependents`, false.
  const establishFixture = async (id, read, declared, dependents) => {
    const row = RESULTS.find((r) => r.id === id);
    const question = row ? row.question : id;
    const problems = [];
    const seen = [];
    let got = null;
    let threw = false;
    try {
      got = await read();
    } catch (err) {
      threw = true;
      problems.push(`the read threw: ${err && err.message ? err.message : String(err)}`);
    }
    if (!threw) {
      const silent = got && typeof got === 'object' ? unanswered(got) : 'returned no response';
      if (silent) problems.push(`the read ${silent}`);
    }
    if (!problems.length) {
      for (const [name, want] of Object.entries(declared)) {
        if (!Object.prototype.hasOwnProperty.call(got.body, name) || got.body[name] === undefined) {
          problems.push(`${name} is absent from the payload`);
          continue;
        }
        const value = got.body[name];
        seen.push(`${name}=${JSON.stringify(value)}`);
        const held = typeof want === 'function' ? want(value) === true : value === want;
        if (!held) {
          problems.push(`${name} differs: read ${JSON.stringify(value)}, declared `
            + (typeof want === 'function' ? 'by a predicate it fails' : JSON.stringify(want)));
        }
      }
    }
    if (!problems.length) {
      record(id, question, 'PASS', `read back ${seen.join(', ')}`);
      return true;
    }
    record(id, question, 'FAIL', problems.join('; ') + (seen.length ? `; read ${seen.join(', ')}` : ''));
    voidDependents(dependents, `the fixture ${id} did not hold: ${problems.join('; ')}`);
    return false;
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

  log('INFO', 'probe revision 0fa4c9ba. Quote this when reporting results.');

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
    window: 'dbmlsp cleared window state',
    afterRestore: 'dbmlsp after restore state',
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
    cleared: 'With the list ValidationFormula cleared again, is folders/add accepted',
    restored: 'Is the list ValidationFormula accepted back onto a library that now holds folders, and does it read back',
    survives: 'Does the folder created while the formula was cleared still read back after it is restored',
    controlRestored: 'CONTROL: does the restored formula refuse a NEW folder again, which is what says the restore took effect',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, then walk it through`);
    log('INFO', 'broken inheritance, a required column, a column validation formula and a list');
    log('INFO', 'validation formula, creating one differently named folder after each step.');
    log('INFO', 'Two further spellings are then tried in the final state, and then the');
    log('INFO', 'formula is cleared, a folder created, and the formula put back.');
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
    'library.folder.clear-list-validation-to-create',
    'library.folder.restore-list-validation-after-folders',
    'library.folder.folder-survives-restored-validation',
    'library.folder.control-restored-validation-refuses-a-folder',
  ];

  expect('library.doc-lib.fixture-library-created', Q.fixture);
  expect('library.folder.control-add-on-bare-library', Q.control);
  expect('library.folder.add-with-broken-inheritance', Q.acl);
  expect('library.folder.add-with-required-column', Q.required);
  expect('library.folder.add-with-column-validation', Q.columnValidation);
  expect('library.folder.add-with-list-validation', Q.listValidation);
  expect('library.folder.add-using-path-under-validation', Q.usingPath);
  expect('library.folder.add-as-list-item-under-validation', Q.listItem);
  expect('library.folder.clear-list-validation-to-create', Q.cleared);
  expect('library.folder.restore-list-validation-after-folders', Q.restored);
  expect('library.folder.folder-survives-restored-validation', Q.survives);
  expect('library.folder.control-restored-validation-refuses-a-folder', Q.controlRestored);

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
    const made = existing.ok ? null : await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint folder under schema probe. Safe to delete.',
      ContentTypesEnabled: false,
    }, await getDigest());
    if (made !== null && !made.ok) {
      record('library.doc-lib.fixture-library-created', Q.fixture, 'FAIL', short(made));
      voidAll(IDS, 'the library fixture did not build, so no state could be applied to it.');
      return report();
    }
    log('INFO', made === null
      ? 'reusing an existing library, so every state below may already be applied. '
        + 'Set CLEANUP = true for a clean answer.'
      : `created '${LIB}'`);
    // The control repeats a measurement taken on a library created with content types off.
    if (!await establishFixture('library.doc-lib.fixture-library-created',
      () => spGet(`${libPath}?$select=BaseTemplate,ContentTypesEnabled`),
      { BaseTemplate: 101, ContentTypesEnabled: false }, IDS)) {
      return report();
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

  // Does the folder this run asked for exist under the library root now? The
  // create's own status is not that: `folder-create-refusal-probe` settled
  // that the call answers 200, and a 200 with nothing under the root is the
  // shape every row here would otherwise report as a state that accepted a
  // folder.
  const folderExists = async (name) => {
    const r = await spGet(
      `web/GetFolderByServerRelativeUrl('${pathLiteral(`${rootUrl}/${name}`)}')?$select=Exists,ServerRelativeUrl`);
    // `absent` is what folder-shape-probe classifies as a path nothing
    // occupies; any other reading leaves the name unknown rather than free.
    if (readFailed(r)) {
      return {
        present: false, absent: r.status === 404,
        line: `the folder did not read back (HTTP ${r.status})`,
      };
    }
    return {
      present: r.body.Exists === true,
      absent: r.body.Exists === false,
      line: `the folder reads back Exists=${r.body.Exists} at ${r.body.ServerRelativeUrl}`,
    };
  };

  // MEASURED 2026-09-13, `library.folder.add-under-existing-folder-name`: a
  // create on a name a folder already holds answers HTTP 200 and returns that
  // folder. CLEANUP ships false, so on the second run every state meets the
  // folder the first run left, and a no-op reads as the state taking one.
  const freeName = async (id, question, name) => {
    const before = await folderExists(name);
    if (before.absent) return true;
    record(id, question, 'NOT ESTABLISHED',
           `'${name}' was not read as free before the create (${before.line}), and a create over `
           + 'a folder that is already there answers 200 and returns it. Set CLEANUP = true.');
    return false;
  };

  const addFolder = async (id, question, name) => {
    if (!await freeName(id, question, name)) return false;
    const digest = await getDigest();
    const res = await spPost(
      `web/GetFolderByServerRelativeUrl('${pathLiteral(rootUrl)}')/folders/add(url='${pathLiteral(name)}')`,
      {}, digest);
    if (!res.ok) {
      // A 401, 403, 408 or 429 says nothing about whether this state takes a
      // folder, and FAIL settles the row as though it did.
      record(id, question, isRefusal(res.status) ? 'REFUSED' : 'NOT ESTABLISHED', short(res));
      return false;
    }
    const back = await folderExists(name);
    if (!back.present) {
      record(id, question, 'NOT ESTABLISHED',
             `HTTP ${res.status}, but ${back.line}. An accepted call that left no folder is not `
             + 'this state accepting a folder.');
      return false;
    }
    record(id, question, 'PASS', `HTTP ${res.status}, ${back.line}, and ${await folderItem(name)}`);
    return true;
  };

  // ---- the bare library ------------------------------------------------
  if (!await addFolder('library.folder.control-add-on-bare-library', Q.control, NAMES.bare)) {
    voidAll(IDS.slice(1),
            'the control did not record a folder created on a bare library, so this run cannot '
            + 'attribute a later refusal to a setting. Its own row says what stopped it.');
    return report();
  }

  // Every row here names the state the library was in, so each state is READ
  // BACK before the folder create that reports on it. A 2xx from the write
  // that was meant to enter the state is not the state: a row recorded off one
  // would attribute a refusal, or an acceptance, to a setting that is not
  // there. The list formula's own restore below already worked this way.
  const GUARD_FORMULA = `=[${GUARD}]="ok"`;
  const canonical = (formula) => String(formula || '').replace(/[[\]]/g, '');
  // `!body.X` is true both for a property that is unset and for one the site
  // never served, and only the first says the column carries nothing.
  const unset = (body, prop) => prop in body && !body[prop];

  // ---- state 1: broken role inheritance --------------------------------
  {
    const digest = await getDigest();
    const broke = await spPost(
      `${libPath}/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)`, {}, digest);
    const back = await spGet(`${libPath}?$select=HasUniqueRoleAssignments`);
    const unique = !readFailed(back) && back.body.HasUniqueRoleAssignments === true;
    if (!broke.ok || !unique) {
      record('library.folder.add-with-broken-inheritance', Q.acl, 'NOT ESTABLISHED',
             `the library's inheritance was not broken (${broke.ok ? `HTTP ${broke.status}` : short(broke)}; `
             + `${readFailed(back)
               ? `HasUniqueRoleAssignments did not read back, HTTP ${back.status}`
               : `HasUniqueRoleAssignments reads back ${back.body.HasUniqueRoleAssignments}`}), `
             + 'so this state was never entered.');
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
    // The whole field, not a $select: naming a property the entity does not
    // have answers HTTP 400, which would read as an absent column rather than
    // as one of the wrong type left by an earlier run.
    //
    // The state is REQUIRED with NO default and NO rule of its own, which is
    // what the shipped family declares for two of its five library columns. A
    // column left by an earlier run carrying either is the state the NEXT row
    // names, and a refusal under it would be recorded against requiredness.
    // Each is read as served-and-falsy, because a column carrying neither
    // reads back either way and a property the site withheld is not evidence.
    const back = await spGet(`${libPath}/fields/getbyinternalnameortitle('${GUARD}')`);
    guardMade = !readFailed(back) && back.body.Required === true
      && back.body.TypeAsString === 'Text'
      && unset(back.body, 'DefaultValue') && unset(back.body, 'ValidationFormula');
    guardExists = !readFailed(back);
    if (!guardMade) {
      record('library.folder.add-with-required-column', Q.required, 'NOT ESTABLISHED',
             `the required column with no default and no rule of its own is not on the library (create answered ${made.ok ? `HTTP ${made.status}` : short(made)}; `
             + `${readFailed(back)
               ? `the column did not read back, HTTP ${back.status}`
               : `it reads back TypeAsString=${back.body.TypeAsString} Required=${back.body.Required}`
                 + ` DefaultValue=${JSON.stringify(back.body.DefaultValue)}`
                 + ` ValidationFormula=${JSON.stringify(back.body.ValidationFormula)}`}), `
             + 'so this state was never entered.');
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
        ValidationFormula: GUARD_FORMULA,
        ValidationMessage: 'dbmlsp probe: this column must read ok.',
      },
      MERGE);
    const back = await spGet(
      `${libPath}/fields/getbyinternalnameortitle('${GUARD}')?$select=ValidationFormula`);
    const held = set.ok && !readFailed(back)
      && canonical(back.body.ValidationFormula) === canonical(GUARD_FORMULA);
    if (!held) {
      record('library.folder.add-with-column-validation', Q.columnValidation, 'NOT ESTABLISHED',
             `the column validation formula is not on ${GUARD} (MERGE answered ${set.ok ? `HTTP ${set.status}` : short(set)}; `
             + `${readFailed(back)
               ? `ValidationFormula did not read back, HTTP ${back.status}`
               : `it reads back ${JSON.stringify(back.body.ValidationFormula)}`}), `
             + 'so this state was never entered.');
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
      ValidationFormula: GUARD_FORMULA,
      ValidationMessage: 'dbmlsp probe: this item must read ok.',
    }, MERGE);
    const back = await spGet(`${libPath}?$select=ValidationFormula`);
    listValidated = set.ok && !readFailed(back)
      && canonical(back.body.ValidationFormula) === canonical(GUARD_FORMULA);
    if (!listValidated) {
      record('library.folder.add-with-list-validation', Q.listValidation, 'NOT ESTABLISHED',
             `the list validation formula is not on the library (MERGE answered ${set.ok ? `HTTP ${set.status}` : short(set)}; `
             + `${readFailed(back)
               ? `ValidationFormula did not read back, HTTP ${back.status}`
               : `it reads back ${JSON.stringify(back.body.ValidationFormula)}`}), `
             + 'so this state was never entered.');
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
  } else if (await freeName('library.folder.add-using-path-under-validation', Q.usingPath, NAMES.usingPath)) {
    const digest = await getDigest();
    const res = await spPost(
      `web/Folders/AddUsingPath(decodedurl='${pathLiteral(`${rootUrl}/${NAMES.usingPath}`)}')`, {}, digest);
    const back = res.ok ? await folderExists(NAMES.usingPath) : null;
    record('library.folder.add-using-path-under-validation', Q.usingPath,
           !res.ok ? (isRefusal(res.status) ? 'REFUSED' : 'NOT ESTABLISHED')
             : back.present ? 'PASS' : 'NOT ESTABLISHED',
           !res.ok ? short(res)
             : back.present
               ? `HTTP ${res.status}, ${back.line}, and ${await folderItem(NAMES.usingPath)}`
               : `HTTP ${res.status}, but ${back.line}. An accepted call that left no folder is `
                 + 'not this spelling creating one.');
  }

  if (finalStateReason) {
    record('library.folder.add-as-list-item-under-validation', Q.listItem, 'NOT ESTABLISHED', finalStateReason);
  } else if (await freeName('library.folder.add-as-list-item-under-validation', Q.listItem, NAMES.listItem)) {
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
      const back = res.ok ? await folderExists(NAMES.listItem) : null;
      record('library.folder.add-as-list-item-under-validation', Q.listItem,
             !res.ok ? (isRefusal(res.status) ? 'REFUSED' : 'NOT ESTABLISHED')
               : back.present ? 'PASS' : 'NOT ESTABLISHED',
             !res.ok ? `${short(res)} (as ${itemType})`
               : back.present
                 ? `HTTP ${res.status} as ${itemType}, ${back.line}, and ${await folderItem(NAMES.listItem)}`
                 : `HTTP ${res.status} as ${itemType}, but ${back.line}. An accepted item POST that `
                   + 'left no folder is not this spelling creating one.');
    }
  }

  // ---- the shape of the fix: clear, create, restore --------------------
  // If a list formula is what refuses a folder, the deploy has to open the
  // library, create its declared folders and close it again, which is the
  // shape Phase 1.8 and Phase 4.1 already use for a sealed column. Three
  // things have to hold for that to be safe, and none is measured: the
  // cleared list accepts the create, the formula goes back onto a library
  // that now holds folders, and the folder survives the restore. The fourth
  // row is the control that says the restore actually took effect, because
  // a restore that silently did nothing would make the three above pass
  // while leaving the library unguarded.
  const CLEARED_REASON = 'the list validation formula never landed, so there is nothing to clear.';
  const RESTORE_IDS = [
    'library.folder.clear-list-validation-to-create',
    'library.folder.restore-list-validation-after-folders',
    'library.folder.folder-survives-restored-validation',
    'library.folder.control-restored-validation-refuses-a-folder',
  ];
  if (!listValidated) {
    voidAll(RESTORE_IDS, CLEARED_REASON);
    return report();
  }

  const setListFormula = (formula, message) => postVerbose(libPath, {
    __metadata: { type: 'SP.List' },
    ValidationFormula: formula,
    ValidationMessage: message,
  }, MERGE);

  const cleared = await setListFormula('', '');
  // Read back, because the whole window rests on the formula being GONE. A
  // MERGE that answered 204 and kept the formula would make the create below
  // report on the guarded library while the row says it was cleared.
  const clearedBack = await spGet(`${libPath}?$select=ValidationFormula`);
  const isClear = cleared.ok && !readFailed(clearedBack) && !canonical(clearedBack.body.ValidationFormula);
  if (!isClear) {
    voidAll(RESTORE_IDS, 'the list validation formula was not cleared (MERGE answered '
            + `${cleared.ok ? `HTTP ${cleared.status}` : short(cleared)}; `
            + `${readFailed(clearedBack)
              ? `ValidationFormula did not read back, HTTP ${clearedBack.status}`
              : `it still reads back ${JSON.stringify(clearedBack.body.ValidationFormula)}`}), `
            + 'so the clear-create-restore shape could not be tried at all.');
    return report();
  }
  const madeInWindow = await addFolder(
    'library.folder.clear-list-validation-to-create', Q.cleared, NAMES.window);

  const restored = await setListFormula(
    `=[${GUARD}]="ok"`, 'dbmlsp probe: this item must read ok.');
  const readBack = await spGet(`${libPath}?$select=ValidationFormula`);
  const formulaBack = readFailed(readBack) ? null : readBack.body.ValidationFormula;
  const restoredOk = restored.ok && typeof formulaBack === 'string' && formulaBack.includes(GUARD);
  record('library.folder.restore-list-validation-after-folders', Q.restored,
         restoredOk ? 'PASS' : restored.ok ? 'FAIL'
           : isRefusal(restored.status) ? 'REFUSED' : 'NOT ESTABLISHED',
         restored.ok
           ? `HTTP ${restored.status}, and ValidationFormula reads back ${JSON.stringify(formulaBack)}`
           : short(restored));

  if (!madeInWindow) {
    record('library.folder.folder-survives-restored-validation', Q.survives, 'NOT ESTABLISHED',
           'no folder was created while the formula was cleared, so nothing could survive the restore.');
  } else {
    const still = await spGet(`web/GetFolderByServerRelativeUrl('${pathLiteral(`${rootUrl}/${NAMES.window}`)}')?$select=Exists,ServerRelativeUrl`);
    const exists = !readFailed(still) && still.body.Exists === true;
    record('library.folder.folder-survives-restored-validation', Q.survives,
           exists ? 'PASS' : 'FAIL',
           exists
             ? `the folder still reads back at ${still.body.ServerRelativeUrl}`
             : `the folder did not read back after the restore (HTTP ${still.status})`);
  }

  if (!restoredOk) {
    record('library.folder.control-restored-validation-refuses-a-folder', Q.controlRestored,
           'NOT ESTABLISHED',
           'the formula did not read back after the restore, so a refusal here would say nothing '
           + 'about whether a restored guard is in force.');
  } else if (await freeName('library.folder.control-restored-validation-refuses-a-folder',
                            Q.controlRestored, NAMES.afterRestore)) {
    const digest = await getDigest();
    const after = await spPost(
      `web/GetFolderByServerRelativeUrl('${pathLiteral(rootUrl)}')/folders/add(url='${pathLiteral(NAMES.afterRestore)}')`,
      {}, digest);
    record('library.folder.control-restored-validation-refuses-a-folder', Q.controlRestored,
           after.ok ? 'FAIL' : isRefusal(after.status) ? 'PASS' : 'NOT ESTABLISHED',
           after.ok
             ? `HTTP ${after.status}: the create was ACCEPTED, so the restored formula is not in force `
               + 'and the three rows above are about an unguarded library'
             : short(after));
  }

  return report();
})();
