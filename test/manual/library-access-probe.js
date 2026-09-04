/**
 * dbml-sharepoint PROBE: DOCUMENT LIBRARY ACCESS SURFACE
 *
 * REVISION: 3dbd758a
 *
 * ONE QUESTION:
 *   Does the permission model of a document library diverge from a generic list?
 *
 * The generic-list access surface is already probed: role bindings and the
 * inheritance shape (reader-bindings-probe.js), role definitions and
 * assignments (role-definition-probe.js), effective permissions for a second
 * account (enterprise-reader-probe.js), list-scope ACLs after a break
 * (lookup-acl-probe.js) and the site user information list
 * (siteuserinfolist-probe.js). None of those runs touched a document library.
 * This probe asks the divergence question for the access surface: does a
 * library's permission model (unique permissions, role assignments, broken
 * inheritance) behave the same as a list's, or does the file/folder model
 * change it?
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101) and holds one uploaded
 *     file, so a file-scoped object exists for the file question.
 *   library.access.control-missing-column-refused
 *     NEGATIVE CONTROL: a role-assignment call naming a principal and a role
 *     level that do not exist is REFUSED. Without it, every role-assignment
 *     attach below is unproven: a server that accepted an assignment to a
 *     nonexistent principal or level could not be trusted to have attached
 *     the assignments this probe reads back.
 *   library.access.unique-permissions-library
 *     Can a document library break role inheritance and hold unique
 *     permissions over REST, the way a list can? Sends the same
 *     breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)
 *     call lookup-acl-probe.js sends to a generic list.
 *   library.access.role-assignment-library
 *     Does a role assignment (a permission level bound to a principal)
 *     attach to a document library and read back, the way it does on a list?
 *     Uses the same roleassignments/addroleassignment attach and expanded
 *     read-back shape lookup-acl-probe.js and reader-bindings-probe.js use
 *     at list scope.
 *   library.access.file-scoped-unique-permission
 *     A library's security-scoped objects are files and folders, not list
 *     items. Does a unique permission set on a single file inside the
 *     library read back with that file as the security-scoped object
 *     (SecurableObject), or does the library diverge from the item-scoped
 *     model?
 *
 * NOTHING IS RETIRED: this is the first access probe to run against a
 * document library. Reader-visibility (what a second account can see after a
 * break) is deliberately NOT re-opened here: reader-bindings-probe.js and
 * enterprise-reader-probe.js already cover it on generic lists, and this
 * probe stays in the owner lane, which can break inheritance, grant a role
 * and read the assignment back on its own.
 *
 * MICROSOFT LEARN CITATIONS
 *   List and library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Breaking and restoring role inheritance:
 *     "SP.SecurableObject.breakRoleInheritance method"
 *     "SP.SecurableObject.resetRoleInheritance method"
 *   Attaching a role assignment:
 *     "SP.RoleAssignmentCollection.addRoleAssignment(principalId, roleDefId)
 *      method"
 *   Reading role assignments back:
 *     "SP.RoleAssignmentCollection object"
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * This probe breaks inheritance on the library and on the file it uploads,
 * and restores inheritance on both before it finishes, so a normal run leaves
 * the sandbox inheriting. A run interrupted mid-write (the browser closing
 * between a break and its restore) can leave the library unique: re-run to
 * restore, or delete the library.
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

  log('INFO', 'probe revision 3dbd758a. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibAccess';
  const FILE = 'probe-access-doc.txt';
  const listPath = `web/lists/getbytitle('${LIB}')`;

  const Q_FIXTURE = 'A document library is created (BaseTemplate 101)';
  const Q_CONTROL = 'NEGATIVE CONTROL: a role-assignment call naming a principal and a role level that do not exist is refused';
  const Q_UNIQUE = 'Can a document library break role inheritance and hold unique permissions over REST, the way a list can';
  const Q_ROLE_ATTACH = 'Does a role assignment (a permission level bound to a principal) attach to a document library and read back, the way it does on a list';
  const Q_FILE_SCOPE = 'Does a unique permission set on a single file inside the library read back with that file as the security-scoped object (SecurableObject), as the item-scoped model does on a generic list';

  expect('library.doc-lib.fixture-library-created', Q_FIXTURE);
  expect('library.access.control-missing-column-refused', Q_CONTROL);
  expect('library.access.unique-permissions-library', Q_UNIQUE);
  expect('library.access.role-assignment-library', Q_ROLE_ATTACH);
  expect('library.access.file-scoped-unique-permission', Q_FILE_SCOPE);

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, upload the file '${FILE}',`);
    log('INFO', 'then ask three access questions: whether the library can break role');
    log('INFO', 'inheritance and hold unique permissions, whether a role assignment');
    log('INFO', 'attaches to the library and reads back, and whether a unique');
    log('INFO', 'permission set on a single file reads back with that file as the');
    log('INFO', 'security-scoped object. Inheritance is restored before finishing.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing library would be reused.');
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

  // Track what this run breaks so the restore pass knows what to reset. A
  // run that never breaks anything has nothing to restore.
  let libraryBroken = false;
  let fileBroken = false;
  let fileItem = null;

  const rawPost = async (path, body, digest) => {
    try {
      const res = await fetch(`${WEB}/_api/${path}`, {
        method: 'POST',
        headers: {
          Accept: 'application/json;odata=nometadata',
          'X-RequestDigest': digest,
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

  // The restore pass. Runs on every path out of the access questions, so a
  // break that happened is always paired with its reset. The file is reset
  // first (it inherits from the library), then the library (which inherits
  // from the web). Reading HasUniqueRoleAssignments first means a reset is
  // only sent where one is needed.
  const restoreInheritance = async () => {
    try {
      if (fileBroken && fileItem) {
        let digest = await getDigest();
        const fileReset = await spPost(
          `${listPath}/items(${fileItem.Id})/resetroleinheritance`, {}, digest);
        if (fileReset.ok) {
          const fileAfter = await spGet(`${listPath}/items(${fileItem.Id})?$select=Id,HasUniqueRoleAssignments`);
          const nowInheriting = fileAfter.ok && fileAfter.body
            && fileAfter.body.HasUniqueRoleAssignments === false;
          log(nowInheriting ? 'OK' : 'FAIL',
              nowInheriting
                ? `file '${FILE}' restored to inherited permissions.`
                : `file '${FILE}' reset answered HTTP ${fileAfter.status}; verify by hand.`);
        } else {
          log('FAIL', `Could not restore '${FILE}': HTTP ${fileReset.status} ${fileReset.text.slice(0, 200)}`);
        }
      }
      const libState = await spGet(`${listPath}?$select=Title,HasUniqueRoleAssignments`);
      if (libState.ok && libState.body && libState.body.HasUniqueRoleAssignments === true) {
        let digest = await getDigest();
        const libReset = await spPost(`${listPath}/resetroleinheritance`, {}, digest);
        if (libReset.ok) {
          const libAfter = await spGet(`${listPath}?$select=Title,HasUniqueRoleAssignments`);
          const nowInheriting = libAfter.ok && libAfter.body
            && libAfter.body.HasUniqueRoleAssignments === false;
          log(nowInheriting ? 'OK' : 'FAIL',
              nowInheriting
                ? `library '${LIB}' restored to inherited permissions.`
                : `library '${LIB}' reset answered HTTP ${libAfter.status}; verify by hand.`);
        } else {
          log('FAIL', `Could not restore '${LIB}': HTTP ${libReset.status} ${libReset.text.slice(0, 200)}`);
        }
      } else {
        log('OK', `'${LIB}' already inherits; nothing to restore.`);
      }
    } catch (err) {
      log('FAIL', `restore pass failed: ${String(err)}`);
    }
  };

  await resetList(LIB);
  let digest = await getDigest();

  // ---- fixture-library-created: the library ---------------------------
  const existing = await spGet(`${listPath}?$select=Title`);
  if (existing.ok) {
    record('library.doc-lib.fixture-library-created', Q_FIXTURE,
           'ALREADY PRESENT',
           'reusing an existing library. Set CLEANUP = true for a clean answer');
  } else {
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint library-access probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', Q_FIXTURE,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  // ---- RootFolder path ------------------------------------------------
  const root = await spGet(`${listPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  if (!folderUrl) {
    log('FAIL', `Could not read RootFolder for '${LIB}': HTTP ${root.status}`);
    record('library.access.control-missing-column-refused', Q_CONTROL,
           'NOT ESTABLISHED', `library RootFolder did not read back (HTTP ${root.status}), fixture incomplete`, 'void');
    record('library.access.unique-permissions-library', Q_UNIQUE,
           'NOT ESTABLISHED', 'fixture incomplete: RootFolder did not read back', 'void');
    record('library.access.role-assignment-library', Q_ROLE_ATTACH,
           'NOT ESTABLISHED', 'fixture incomplete: RootFolder did not read back', 'void');
    record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
           'NOT ESTABLISHED', 'fixture incomplete: RootFolder did not read back', 'void');
    return report();
  }

  // ---- Upload one file (a file-scoped object for the file question) ---
  digest = await getDigest();
  const up = await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE}',overwrite=true)`,
    'dbmlsp probe access file: permission scope control document',
    digest
  );
  log(up.ok ? 'OK' : 'FAIL', `uploaded '${FILE}': HTTP ${up.status}`);
  const itemsResp = await spGet(`${listPath}/items?$select=Id,FileLeafRef&$top=50`);
  if (itemsResp.ok && itemsResp.body && Array.isArray(itemsResp.body.value)) {
    fileItem = itemsResp.body.value.find((i) => i.FileLeafRef === FILE) || null;
  }
  if (!fileItem) {
    log('FAIL', `the uploaded file '${FILE}' did not read back as a list item.`);
    record('library.access.control-missing-column-refused', Q_CONTROL,
           'NOT ESTABLISHED', `file upload answered HTTP ${up.status} and no item read back, fixture incomplete`, 'void');
    record('library.access.unique-permissions-library', Q_UNIQUE,
           'NOT ESTABLISHED', 'fixture incomplete: no file item read back', 'void');
    record('library.access.role-assignment-library', Q_ROLE_ATTACH,
           'NOT ESTABLISHED', 'fixture incomplete: no file item read back', 'void');
    record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
           'NOT ESTABLISHED', 'fixture incomplete: no file item read back', 'void');
    return report();
  }
  log('OK', `'${FILE}' read back as item Id ${fileItem.Id}.`);

  // ---- control-missing-column-refused: NEGATIVE CONTROL ---------------
  // A role-assignment attach naming a principal and a role level that do not
  // exist must be refused. 42424242 is far above any real principal or role
  // definition id on a tenant. If the server accepts it, the machine lane
  // cannot trust ANY attach below, and every question is voided.
  digest = await getDigest();
  const bogus = await spPost(
    `${listPath}/roleassignments/addroleassignment(principalid=42424242,roledefid=42424242)`,
    {}, digest);
  const controlHeld = !bogus.ok && isRefusal(bogus.status);
  record('library.access.control-missing-column-refused', Q_CONTROL,
         bogus.ok ? 'FAIL' : isRefusal(bogus.status) ? 'PASS' : 'NOT ESTABLISHED',
         bogus.ok
           ? 'addroleassignment accepted a nonexistent principal and role level with HTTP 200. '
             + 'The server did not validate the principal or the level, so every attach below is void.'
           : isRefusal(bogus.status)
             ? `refused with HTTP ${bogus.status}: ${bogus.text.slice(0, 260)}`
             : `the request failed with HTTP ${bogus.status}, which is not the server ` + 'rejecting the payload. Refusal answers below this line are void.');

  try {
    if (!controlHeld) {
      // A FAILED control (an accepted bogus attach) may itself have flipped
      // the library to unique permissions, so the restore pass still runs.
      record('library.access.unique-permissions-library', Q_UNIQUE,
             'NOT ESTABLISHED', 'negative control did not hold, so no break on this library is trustworthy', 'void');
      record('library.access.role-assignment-library', Q_ROLE_ATTACH,
             'NOT ESTABLISHED', 'negative control did not hold, so no role-assignment attach is trustworthy', 'void');
      record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
             'NOT ESTABLISHED', 'negative control did not hold, so no file-scope attach is trustworthy', 'void');
    } else {
      // ---- unique-permissions-library + role-assignment-library --------
      // One shared break: the library must hold unique permissions before a
      // role assignment can attach at library scope. The break and the
      // owners grant run back to back: after a break with no copied
      // assignments the caller keeps access only once the owners group holds
      // Full Control at library scope again (the same shape lookup-acl-probe
      // uses to keep the operator in the list it breaks).
      const before = await spGet(`${listPath}?$select=Title,HasUniqueRoleAssignments`);
      const alreadyUnique = before.ok && before.body
        && before.body.HasUniqueRoleAssignments === true;
      if (!alreadyUnique) {
        digest = await getDigest();
        const broke = await spPost(
          `${listPath}/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)`,
          {}, digest);
        if (broke.ok) {
          libraryBroken = true;
        } else {
          record('library.access.unique-permissions-library', Q_UNIQUE,
                 isRefusal(broke.status) ? 'REFUSED' : 'NOT ESTABLISHED',
                 `breakroleinheritance on the library answered HTTP ${broke.status} `
                 + `${broke.text.slice(0, 200)}. A list accepts this call, so a library that `
                 + 'refuses it is a divergence.' + (isRefusal(broke.status) ? '' : ' The status is not a refusal.'));
          record('library.access.role-assignment-library', Q_ROLE_ATTACH,
                 'NOT ESTABLISHED', 'the library never held unique permissions, so nothing could attach at library scope', 'void');
          record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
                 'NOT ESTABLISHED', 'the library never held unique permissions, so the file scope was never tested', 'void');
        }
      } else {
        libraryBroken = true;
        log('INFO', `'${LIB}' already held unique permissions; reusing the broken state.`);
      }

      if (libraryBroken) {
        const owners = await spGet('web/associatedownergroup?$select=Id,Title');
        if (!owners.ok || !owners.body || !owners.body.Id) {
          log('FAIL', 'Could not read the associated owner group. If the library was just '
                      + `broken, grant yourself access to '${LIB}' by hand.`);
          record('library.access.unique-permissions-library', Q_UNIQUE,
                 'NOT ESTABLISHED', 'the break ran but the owner group did not read back (HTTP '
                 + `${owners.status}), so the unique-permission state could not be verified`, 'void');
          record('library.access.role-assignment-library', Q_ROLE_ATTACH,
                 'NOT ESTABLISHED', 'the owner group did not read back, so no role assignment could be attached', 'void');
          record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
                 'NOT ESTABLISHED', 'the owner group did not read back, so no file-scope attach could be made', 'void');
        } else {
          // Attach Full Control for the owners group at LIBRARY scope and read
          // it back. This is both the Q2 experiment and the safety grant that
          // keeps the operator inside the broken library.
          digest = await getDigest();
          const grant = await spPost(
            `${listPath}/roleassignments/addroleassignment(principalid=${owners.body.Id},roledefid=1073741829)`,
            {}, digest);
          if (!grant.ok) {
            log('FAIL', `Could not grant the owners group on '${LIB}': HTTP ${grant.status}. `
                        + 'If this run cannot restore, delete the library.');
            record('library.access.unique-permissions-library', Q_UNIQUE,
                   'NOT ESTABLISHED',
                   `the owners grant answered HTTP ${grant.status}, so the library may be locked ` + 'down and its unique state is unverifiable',
                   'void');
            record('library.access.role-assignment-library', Q_ROLE_ATTACH,
                   isRefusal(grant.status) ? 'REFUSED' : 'NOT ESTABLISHED',
                   `addroleassignment at library scope answered HTTP ${grant.status} `
                   + `${grant.text.slice(0, 200)}. A list accepts this call, so a library that `
                   + 'refuses it is a divergence.' + (isRefusal(grant.status) ? '' : ' The status is not a refusal.'));
            record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
                   'NOT ESTABLISHED', 'the library-scope grant failed, so the file scope was never reached', 'void');
          } else {
            // Q1 verdict: the library read back as holding unique permissions.
            const libCheck = await spGet(`${listPath}?$select=Title,HasUniqueRoleAssignments`);
            const uniqueNow = libCheck.ok && libCheck.body
              && libCheck.body.HasUniqueRoleAssignments === true;
            record('library.access.unique-permissions-library', Q_UNIQUE,
                   uniqueNow ? 'SAME AS LIST' : 'NOT ESTABLISHED',
                   uniqueNow
                     ? `breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true) succeeded on `
                       + `'${LIB}' and HasUniqueRoleAssignments read back true, exactly as the same `
                       + 'call behaves on a generic list (lookup-acl-probe.js).'
                     : 'after the break the library read HasUniqueRoleAssignments='
                       + ((libCheck.ok && libCheck.body)
                         ? libCheck.body.HasUniqueRoleAssignments
                         : 'unreadable')
                       + ` (HTTP ${libCheck.status})`);

            // Q2 verdict: the assignment attached at library scope and read back.
            const assignResp = await spGet(
              `${listPath}/roleassignments?$select=PrincipalId&$expand=RoleDefinitionBindings&$top=200`);
            const rows = (assignResp.ok && assignResp.body && Array.isArray(assignResp.body.value))
              ? assignResp.body.value : [];
            const ownersRow = rows.find((r) =>
              Number(r.PrincipalId) === Number(owners.body.Id)
              && Array.isArray(r.RoleDefinitionBindings)
              && r.RoleDefinitionBindings.some((b) => b.Name === 'Full Control'));
            record('library.access.role-assignment-library', Q_ROLE_ATTACH,
                   ownersRow ? 'SAME AS LIST' : 'ASSIGNMENT NOT READ BACK',
                   ownersRow
                     ? `addroleassignment(principalid=${owners.body.Id},roledefid=1073741829) succeeded `
                       + `on '${LIB}' and the library's roleassignments read back ${rows.length} row(s) `
                       + `including the owners group bound to Full Control, exactly as a generic list `
                       + 'reads an assignment back (reader-bindings-probe.js).'
                     : `the library roleassignments read answered HTTP ${assignResp.status} with `
                       + `${rows.length} row(s), but none bound principal ${owners.body.Id} to Full Control. `
                       + 'A list would have read the assignment back; this is a divergence.');

            // ---- file-scoped-unique-permission --------------------------
            // The file is the library's item analogue. Break inheritance on
            // the single file and grant the owners group Full Control at the
            // FILE's scope, then read the file's own roleassignments: the row
            // enumerating under items(fileItemId) is the proof that the file,
            // not a list item elsewhere, is the security-scoped object.
            const fBefore = await spGet(
              `${listPath}/items(${fileItem.Id})?$select=Id,HasUniqueRoleAssignments`);
            const fileAlready = fBefore.ok && fBefore.body
              && fBefore.body.HasUniqueRoleAssignments === true;
            if (!fileAlready) {
              digest = await getDigest();
              const fBroke = await spPost(
                `${listPath}/items(${fileItem.Id})/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=true)`,
                {}, digest);
              if (fBroke.ok) {
                fileBroken = true;
              } else {
                record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
                       isRefusal(fBroke.status) ? 'REFUSED' : 'NOT ESTABLISHED',
                       `breakroleinheritance on the file item ${fileItem.Id} answered HTTP `
                       + `${fBroke.status} ${fBroke.text.slice(0, 200)}. A generic list item accepts `
                       + 'this call, so a library file that refuses it is a divergence.'
                       + (isRefusal(fBroke.status) ? '' : ' The status is not a refusal.'));
              }
            } else {
              fileBroken = true;
              log('INFO', `file '${FILE}' already held unique permissions; reusing the broken state.`);
            }

            if (fileBroken) {
              // Break then grant, back to back, for the same reason as the
              // library: after the break no assignment reaches the file.
              digest = await getDigest();
              const fGrant = await spPost(
                `${listPath}/items(${fileItem.Id})/roleassignments/addroleassignment(principalid=${owners.body.Id},roledefid=1073741829)`,
                {}, digest);
              if (!fGrant.ok) {
                record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
                       isRefusal(fGrant.status) ? 'REFUSED' : 'NOT ESTABLISHED',
                       `addroleassignment at the file's scope answered HTTP ${fGrant.status} `
                       + `${fGrant.text.slice(0, 200)}. A list item accepts this call, so a library `
                       + 'file that refuses it is a divergence.'
                       + (isRefusal(fGrant.status) ? '' : ' The status is not a refusal.'));
              } else {
                const fCheck = await spGet(
                  `${listPath}/items(${fileItem.Id})?$select=Id,HasUniqueRoleAssignments`);
                const fileUnique = fCheck.ok && fCheck.body
                  && fCheck.body.HasUniqueRoleAssignments === true;
                const fAssignResp = await spGet(
                  `${listPath}/items(${fileItem.Id})/roleassignments?$select=PrincipalId&$expand=RoleDefinitionBindings&$top=50`);
                const fRows = (fAssignResp.ok && fAssignResp.body && Array.isArray(fAssignResp.body.value))
                  ? fAssignResp.body.value : [];
                const fileOwnersRow = fRows.find((r) =>
                  Number(r.PrincipalId) === Number(owners.body.Id)
                  && Array.isArray(r.RoleDefinitionBindings)
                  && r.RoleDefinitionBindings.some((b) => b.Name === 'Full Control'));
                record('library.access.file-scoped-unique-permission', Q_FILE_SCOPE,
                       (fileUnique && fileOwnersRow) ? 'SAME AS LIST' : 'ASSIGNMENT NOT READ BACK',
                       (fileUnique && fileOwnersRow)
                         ? `the file '${FILE}' (item Id ${fileItem.Id}) broke inheritance and read `
                           + `HasUniqueRoleAssignments=true, and its OWN roleassignments read back `
                           + `${fRows.length} row(s) including the owners group bound to Full Control. `
                           + 'The file is the security-scoped object, exactly as a list item is on a '
                           + 'generic list: the library does not diverge from the item-scoped model.'
                         : `file unique read ${fileUnique === true ? 'true' : `failed (HTTP ${fCheck.status})`} and `
                           + `its roleassignments answered HTTP ${fAssignResp.status} with ${fRows.length} `
                           + `row(s); the owners-Full Control row did not read back under items(${fileItem.Id}). `
                           + 'A list item would have read the assignment back; this is a divergence.');
              }
            }
          }
        }
      }
    }
  } catch (err) {
    log('FAIL', `access pass aborted: ${err && err.message ? err.message : String(err)}`);
  } finally {
    await restoreInheritance();
  }

  return report();
})();
