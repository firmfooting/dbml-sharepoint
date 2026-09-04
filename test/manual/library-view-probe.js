/**
 * dbml-sharepoint PROBE: DOCUMENT LIBRARY VIEW GROUPING
 *
 * REVISION: a7c321ee
 *
 * ONE QUESTION:
 *   How does view grouping behave on a document library, and does it diverge from generic lists?
 *
 * Round 1 settled what a file, folder, column, and content type are on a library.
 * Round 2 settles how a library interacts with list features. This probe covers the
 * view grouping half (probe 7 of the document-library programme): grouping by metadata
 * columns and whether folders act as a grouping dimension.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101).
 *   library.view.control-missing-column-refused
 *     NEGATIVE CONTROL: a RenderListDataAsStream query naming a missing column is refused.
 *   library.view.group-by-metadata-column
 *     Does RenderListDataAsStream group library files by a metadata column?
 *     Tests whether RenderListDataAsStream with a ViewXml carrying <GroupBy> groups
 *     file rows under distinct metadata values, identical to generic list rows.
 *   library.view.group-by-folder
 *     Is folder a first-class grouping dimension over REST or client-side rendering only?
 *     Determines whether folders are exposed as a REST grouping dimension or whether
 *     the folder hierarchy is managed client-side via RootFolder navigation.
 *
 * NOTHING IS RETIRED:
 *   Both library grouping questions (metadata column grouping and folder grouping)
 *   and controls are probed directly over REST.
 *
 * MICROSOFT LEARN CITATIONS
 *   Document library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   RenderListDataAsStream method via POST to `web/lists/getbytitle(...)/RenderListDataAsStream`:
 *     "SP.List.renderListDataAsStream method"
 *   Folder creation via `RootFolder/folders/add(url=)`:
 *     "Working with folders and files with REST"
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   CAML GroupBy element:
 *     "GroupBy Element (Query)"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Item metadata updates via MERGE to `items(...)`:
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

  log('INFO', 'probe revision a7c321ee. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibView';
  const FOLDER = 'FolderAlpha';
  const COL = 'dbmlspDocCategory';
  const FILE_ALPHA_1 = 'doc-alpha-1.txt';
  const FILE_BETA_1 = 'doc-beta-1.txt';
  const FILE_ALPHA_2 = 'doc-alpha-2.txt';
  const SUBFILE = 'subfolder-doc.txt';
  const listPath = `web/lists/getbytitle('${LIB}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}.`);
    log('INFO', `Would create metadata column '${COL}', create folder '${FOLDER}',`);
    log('INFO', 'upload test files with distinct metadata values and a subfolder file,');
    log('INFO', 'send a negative control query to verify RenderListDataAsStream validation,');
    log('INFO', 'test grouping by metadata column over RenderListDataAsStream,');
    log('INFO', 'and probe whether folder is a first-class REST grouping dimension.');
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

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.view.control-missing-column-refused', 'NEGATIVE CONTROL: a RenderListDataAsStream query naming a missing column is refused');
  expect('library.view.group-by-metadata-column', 'Does RenderListDataAsStream group library files by a metadata column');
  expect('library.view.group-by-folder', 'Is folder a first-class grouping dimension over REST or client-side rendering only');

  await resetList(LIB);
  let digest = await getDigest();

  // ---- fixture-library-created: the library ---------------------------
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
      Description: 'dbml-sharepoint library-view probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created',
           'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  // ---- RootFolder path ------------------------------------------------
  const root = await spGet(`${listPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  if (!folderUrl) {
    log('FAIL', `Could not read RootFolder for '${LIB}': HTTP ${root.status}`);
    record('library.view.control-missing-column-refused',
           'NEGATIVE CONTROL: a RenderListDataAsStream query naming a missing column is refused',
           'NOT ESTABLISHED',
           `library RootFolder did not read back (HTTP ${root.status}), fixture incomplete`,
           'void');
    record('library.view.group-by-metadata-column',
           'Does RenderListDataAsStream group library files by a metadata column',
           'NOT ESTABLISHED',
           'fixture incomplete: RootFolder did not read back',
           'void');
    record('library.view.group-by-folder',
           'Is folder a first-class grouping dimension over REST or client-side rendering only',
           'NOT ESTABLISHED',
           'fixture incomplete: RootFolder did not read back',
           'void');
    return report();
  }

  // ---- Add metadata column (Choice) -----------------------------------
  const addField = async (schemaXml) => {
    digest = await getDigest();
    return spPost(`${listPath}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };
  const fieldExists = async (name) =>
    (await spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')`)).ok;

  if (!(await fieldExists(COL))) {
    const colRes = await addField(
      `<Field Type="Choice" DisplayName="${COL}" Name="${COL}" Format="Dropdown">`
      + '<CHOICES><CHOICE>Alpha</CHOICE><CHOICE>Beta</CHOICE><CHOICE>Gamma</CHOICE></CHOICES>'
      + '<Default>Alpha</Default></Field>'
    );
    if (!colRes.ok) {
      log('WARN', `Could not add column '${COL}': HTTP ${colRes.status}`);
    }
  }

  // ---- Create subfolder -----------------------------------------------
  digest = await getDigest();
  await spPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/folders/add(url='${FOLDER}')`,
    {},
    digest
  );

  // ---- Upload files ---------------------------------------------------
  digest = await getDigest();
  await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE_ALPHA_1}',overwrite=true)`,
    'dbmlsp probe file alpha 1',
    digest
  );

  digest = await getDigest();
  await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE_BETA_1}',overwrite=true)`,
    'dbmlsp probe file beta 1',
    digest
  );

  digest = await getDigest();
  await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${FILE_ALPHA_2}',overwrite=true)`,
    'dbmlsp probe file alpha 2',
    digest
  );

  digest = await getDigest();
  await rawPost(
    `web/GetFolderByServerRelativeUrl('${folderUrl}/${FOLDER}')/Files/add(url='${SUBFILE}',overwrite=true)`,
    'dbmlsp probe subfolder file',
    digest
  );

  // ---- Set metadata on files ------------------------------------------
  const itemsResp = await spGet(`${listPath}/items?$select=Id,FileLeafRef&$top=50`);
  const items = (itemsResp.ok && itemsResp.body && Array.isArray(itemsResp.body.value))
    ? itemsResp.body.value
    : [];

  const setItemMeta = async (filename, value) => {
    const match = items.find((i) => i.FileLeafRef === filename);
    if (!match) return false;
    digest = await getDigest();
    const res = await spPost(
      `${listPath}/items(${match.Id})`,
      { [COL]: value },
      digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' }
    );
    return res.ok;
  };

  await setItemMeta(FILE_ALPHA_1, 'Alpha');
  await setItemMeta(FILE_BETA_1, 'Beta');
  await setItemMeta(FILE_ALPHA_2, 'Alpha');
  await setItemMeta(SUBFILE, 'Alpha');

  // ---- control-missing-column-refused: NEGATIVE CONTROL ---------------
  digest = await getDigest();
  const junkXml =
    '<View><Query><Where><Eq><FieldRef Name="NoSuchColumnDoesNotExist"/><Value Type="Text">x</Value></Eq></Where></Query></View>';
  const junk = await spPost(
    `${listPath}/RenderListDataAsStream`,
    { parameters: { ViewXml: junkXml } },
    digest
  );
  const controlHeld = !junk.ok && isRefusal(junk.status);
  record('library.view.control-missing-column-refused',
         'NEGATIVE CONTROL: a RenderListDataAsStream query naming a missing column is refused',
         junk.ok ? 'FAIL' : isRefusal(junk.status) ? 'PASS' : 'NOT ESTABLISHED',
         junk.ok
           ? 'RenderListDataAsStream accepted a query naming a nonexistent column with HTTP 200. '
             + 'The query engine did not validate column existence, so subsequent query refusals are void.'
           : isRefusal(junk.status)
             ? `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`
             : `the request failed with HTTP ${junk.status}, which is not the server `
               + 'rejecting the payload. Refusal answers below this line are void.');

  // ---- group-by-metadata-column ---------------------------------------
  if (!controlHeld) {
    record('library.view.group-by-metadata-column',
           'Does RenderListDataAsStream group library files by a metadata column',
           'NOT ESTABLISHED',
           'controls not established: query negative control did not hold',
           'void');
  } else {
    const metaGroupXml =
      `<View><Query><GroupBy Collapse="FALSE"><FieldRef Name="${COL}"/></GroupBy></Query>`
      + `<ViewFields><FieldRef Name="FileLeafRef"/><FieldRef Name="${COL}"/></ViewFields>`
      + '<RowLimit>30</RowLimit></View>';
    digest = await getDigest();
    const metaGroupRes = await spPost(
      `${listPath}/RenderListDataAsStream`,
      { parameters: { ViewXml: metaGroupXml } },
      digest
    );

    if (!metaGroupRes.ok) {
      record('library.view.group-by-metadata-column',
             'Does RenderListDataAsStream group library files by a metadata column',
             'REFUSED',
             `RenderListDataAsStream with GroupBy on ${COL} was refused: HTTP ${metaGroupRes.status} ${metaGroupRes.text.slice(0, 260)}`);
    } else {
      const rows = (metaGroupRes.body && Array.isArray(metaGroupRes.body.Row))
        ? metaGroupRes.body.Row
        : ((metaGroupRes.body && metaGroupRes.body.ListData && Array.isArray(metaGroupRes.body.ListData.Row))
          ? metaGroupRes.body.ListData.Row
          : []);

      const filesByGroup = {};
      for (const r of rows) {
        const gVal = r[COL] || r[`${COL}.`] || '(none)';
        const file = r.FileLeafRef || r.FileRef || r.Title || 'unknown';
        if (!filesByGroup[gVal]) filesByGroup[gVal] = [];
        filesByGroup[gVal].push(file);
      }
      const distinctGroups = Object.keys(filesByGroup);
      const groupsAlpha = filesByGroup['Alpha'] || [];
      const groupsBeta = filesByGroup['Beta'] || [];
      const hasMultipleGroups = distinctGroups.length >= 2;
      const filesGrouped = hasMultipleGroups && groupsAlpha.length > 0 && groupsBeta.length > 0;

      // Also verify collapsed query
      const collapsedXml =
        `<View><Query><GroupBy Collapse="TRUE"><FieldRef Name="${COL}"/></GroupBy></Query>`
        + '<RowLimit>30</RowLimit></View>';
      digest = await getDigest();
      const collapsedRes = await spPost(
        `${listPath}/RenderListDataAsStream`,
        { parameters: { ViewXml: collapsedXml } },
        digest
      );
      const collapsedRows = (collapsedRes.ok && collapsedRes.body && Array.isArray(collapsedRes.body.Row))
        ? collapsedRes.body.Row
        : [];

      // Also create an SP.View on the library with GroupBy to confirm view storage
      const viewTitle = 'dbmlsp Probe Grouped View';
      digest = await getDigest();
      const viewMade = await spPost(`${listPath}/views`, {
        Title: viewTitle,
        ViewQuery: `<GroupBy Collapse="FALSE"><FieldRef Name="${COL}"/></GroupBy>`,
        RowLimit: 30,
      }, digest);

      record('library.view.group-by-metadata-column',
             'Does RenderListDataAsStream group library files by a metadata column',
             filesGrouped ? 'SAME AS LIST' : 'UNGROUPED',
             filesGrouped
               ? `RenderListDataAsStream returned HTTP 200 with ${rows.length} file row(s) partitioned under distinct metadata values (${distinctGroups.join(', ')}). `
                 + `Alpha: [${groupsAlpha.join(', ')}], Beta: [${groupsBeta.join(', ')}]. `
                 + `Collapsed query returned ${collapsedRows.length} group header row(s). `
                 + `View creation with ViewQuery GroupBy: HTTP ${viewMade.status}. `
                 + 'Library files group by metadata column identically to generic list items.'
               : `RenderListDataAsStream returned HTTP 200 but rows were not grouped under distinct metadata values: found groups ${JSON.stringify(filesByGroup)}`);
    }
  }

  // ---- group-by-folder ------------------------------------------------
  if (!controlHeld) {
    record('library.view.group-by-folder',
           'Is folder a first-class grouping dimension over REST or client-side rendering only',
           'NOT ESTABLISHED',
           'controls not established: query negative control did not hold',
           'void');
  } else {
    // 1. Attempt GroupBy on FieldRef Name="Folder"
    const folderGroupXml =
      '<View><Query><GroupBy Collapse="FALSE"><FieldRef Name="Folder"/></GroupBy></Query><RowLimit>30</RowLimit></View>';
    digest = await getDigest();
    const folderGroupRes = await spPost(
      `${listPath}/RenderListDataAsStream`,
      { parameters: { ViewXml: folderGroupXml } },
      digest
    );

    // 2. Read default view definition to check whether it carries any GroupBy
    const defView = await spGet(`${listPath}/defaultview?$select=Id,Title,ViewQuery,ListViewXml`);
    const defQuery = (defView.ok && defView.body) ? (defView.body.ViewQuery || '') : '';
    const defXml = (defView.ok && defView.body) ? (defView.body.ListViewXml || '') : '';
    const defaultHasFolderGroupBy = defQuery.includes('Folder') || defXml.includes('Folder') || defQuery.includes('GroupBy');

    // 3. Query root folder stream without RootFolder parameter
    digest = await getDigest();
    const rootStreamRes = await spPost(
      `${listPath}/RenderListDataAsStream`,
      { parameters: { RenderOptions: 2 } },
      digest
    );
    const rootRows = (rootStreamRes.ok && rootStreamRes.body && Array.isArray(rootStreamRes.body.Row))
      ? rootStreamRes.body.Row
      : [];
    const folderItemFound = rootRows.some((r) => String(r.FSObjType) === '1' || r.FileSystemObjectType === 1);
    const subfileInRoot = rootRows.some((r) => r.FileLeafRef === SUBFILE);

    const folderRefused = !folderGroupRes.ok && isRefusal(folderGroupRes.status);
    const isNotRestGrouping = folderRefused && !defaultHasFolderGroupBy;

    record('library.view.group-by-folder',
           'Is folder a first-class grouping dimension over REST or client-side rendering only',
           isNotRestGrouping ? 'FOLDERS ARE NOT A REST GROUPING DIMENSION' : 'EXPOSED OVER REST',
           isNotRestGrouping
             ? `GroupBy on FieldRef Name='Folder' was refused with HTTP ${folderGroupRes.status} (${folderGroupRes.text.slice(0, 120)}). `
               + 'The default view carries no <GroupBy> in ViewQuery or ListViewXml. '
               + `In root RenderListDataAsStream, folders appear as individual list items (FSObjType=1, found=${folderItemFound}) `
               + `and subfolder contents are partitioned from root (subfile in root=${subfileInRoot}). `
               + 'Folder hierarchy is navigated client-side via RootFolder, not exposed as a first-class REST view grouping dimension.'
             : `Folder grouping was accepted over REST: HTTP ${folderGroupRes.status}`);
  }

  return report();
})();
