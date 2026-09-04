/**
 * dbml-sharepoint PROBE: DOCUMENT LIBRARY VIEW TOTALS AND SEARCH DISCOVERY
 *
 * REVISION: 9e764550
 *
 * ONE QUESTION:
 *   Do a document library's view totals and its search discoverability
 *   diverge from a generic list?
 *
 * The library programme has settled what a file, a folder, a column, a view
 * grouping, and a query are on a document library. Two list capabilities
 * have never been asked of a library: whether a library's view accepts an
 * aggregation over a numeric metadata column and returns a computed total the
 * way a list does, and whether a library (and a file inside it) is
 * discoverable through the search index the way a list is.
 *
 * The generic-list totals surface is probed by view-aggregations-probe.js
 * (view.totals: two rows seeded 10 and 32, a totals view accepted and read
 * back, and a total of 42 observed to render). That probe stores the
 * Aggregations on a view and looks at the rendered grid. This probe asks the
 * other side of the same mechanism: RenderListDataAsStream carrying an
 * <Aggregations> block inside its ViewXml returns a totals cell (the column
 * name with a .SUM suffix) from a plain list, so a document library can be
 * compared with that stream shape directly. To keep the comparison honest, a
 * twin plain list is seeded in the SAME run with the same numeric column and
 * two rows of 10 and 32, and the identical ViewXml is sent to the twin and
 * to the library. If both streams return the same SUM cell, the library
 * totals exactly as a list does; if only the twin does, that is the
 * divergence, measured against a same-run baseline rather than asserted from
 * documentation.
 *
 * The generic-list search surface is probed by search-discovery-probe.js
 * (search.discovery: a list's own STS_List row is found by its title, crawl
 * latency measured in hours on this tenant). This probe asks the same
 * discovery question of a document library: a query for the library's title
 * should return the library's STS_List row, and a query for a fixture file's
 * name should return rows under the library's folder path. Search indexing
 * is asynchronous, so a run that happens minutes after the fixture was
 * created can legitimately return nothing; that reads NOT ESTABLISHED with a
 * re-run note, never a divergence claim from a cold index.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101) with three files whose
 *     numeric metadata (10, 14, 18) sums to 42, and a twin plain list of two
 *     rows (10, 32) holds the same sum for the totals leg to compare against.
 *   library.view.control-missing-column-refused
 *     NEGATIVE CONTROL: a RenderListDataAsStream query naming a column that
 *     does not exist is refused. The refusal is what makes the refusals and
 *     totals observed below readable.
 *   library.view.totals-on-library
 *     Does RenderListDataAsStream compute a SUM over a numeric metadata
 *     column from the file rows of a document library, when the identical
 *     ViewXml returns a totals cell from a plain list? The file rows lead
 *     with the file, so whether the aggregation still computes over the
 *     metadata is the question.
 *   library.search.discovery-on-library
 *     Is a document library, and a file inside it, discoverable through the
 *     search index the way a generic list is? A list's STS_List row is found
 *     by title (search.discovery.title-match-exactness); this leg asks
 *     whether the library's own row and a fixture file come back the same.
 *
 * MICROSOFT LEARN CITATIONS
 *   Document library and list creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Item metadata updates via MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   The <Aggregations> element and its per-function FieldRef children:
 *     "Aggregations Element (List)"
 *   Search REST queries against `_api/search/query`:
 *     "Search REST API reference"
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the library it created ('dbmlsp Probe LibViewSearch')
 * and the twin list it created ('dbmlsp Probe LibViewSearchRows').
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

  log('INFO', 'probe revision 9e764550. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibViewSearch';
  const TWIN = 'dbmlsp Probe LibViewSearchRows';
  const listPath = `web/lists/getbytitle('${LIB}')`;
  const twinPath = `web/lists/getbytitle('${TWIN}')`;
  const AMOUNT = 'dbmlspVSAmount';
  const EXPECTED_SUM = 42;
  const TWIN_AMOUNTS = [10, 32];
  // Three files whose amounts sum to the same 42 the twin and the generic
  // list totals run both used, so SAME AS LIST is one figure on all sides.
  const FILES = [
    { leaf: 'dbmlspVSSeedA.txt', amount: 10 },
    { leaf: 'dbmlspVSSeedB.txt', amount: 14 },
    { leaf: 'dbmlspVSSeedC.txt', amount: 18 },
  ];
  // The name the search leg queries for: a single word-broken token.
  const FILE_TOKEN = FILES[0].leaf.replace(/\.txt$/, '');

  const Q_FIXTURE = 'A document library is created (BaseTemplate 101) with three files whose numeric metadata (10, 14, 18) sums to 42, and a twin plain list of two rows (10, 32) holds the same sum for the totals leg to compare the library against';
  const Q_CONTROL = 'NEGATIVE CONTROL: a RenderListDataAsStream query naming a column that does not exist is refused';
  const Q_TOTALS = 'does RenderListDataAsStream compute a SUM over a numeric metadata column from the file rows of a document library, when the identical ViewXml returns a totals cell from a plain list';
  const Q_DISCOVERY = 'is a document library, and a file inside it, discoverable through the search index the way a generic list is';

  expect('library.doc-lib.fixture-library-created', Q_FIXTURE);
  expect('library.view.control-missing-column-refused', Q_CONTROL);
  expect('library.view.totals-on-library', Q_TOTALS);
  expect('library.search.discovery-on-library', Q_DISCOVERY);

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, add a numeric metadata`);
    log('INFO', `column (${AMOUNT}), upload ${FILES.length} files with the amounts 10, 14 and 18,`);
    log('INFO', `and create a twin plain list '${TWIN}' of two rows (10, 32). It would then ask`);
    log('INFO', 'two questions: whether RenderListDataAsStream computes a SUM over the numeric');
    log('INFO', 'metadata column from the library file rows the way the twin list computes it,');
    log('INFO', 'and whether the library and one of its files are discoverable through search.');
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

  const VOIDED = ['library.view.control-missing-column-refused',
                  'library.view.totals-on-library',
                  'library.search.discovery-on-library'];
  const voidAll = async (evidence) => {
    for (const id of VOIDED) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', evidence, 'void');
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
      Description: 'dbml-sharepoint view-search probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', Q_FIXTURE,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
    if (!made.ok) return report();
  }

  // ---- RootFolder path -------------------------------------------------
  const root = await spGet(`${listPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  if (!folderUrl) {
    log('FAIL', `Could not read RootFolder for '${LIB}': HTTP ${root.status}`);
    await voidAll(`library RootFolder did not read back (HTTP ${root.status}), fixture incomplete`);
    return report();
  }

  // ---- The numeric metadata column -------------------------------------
  const addField = async (path, schemaXml) => {
    digest = await getDigest();
    return spPost(`${path}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };
  const fieldExists = async (path, name) =>
    (await spGet(`${path}/fields/getbyinternalnameortitle('${name}')`)).ok;

  if (!(await fieldExists(listPath, AMOUNT))) {
    const colRes = await addField(listPath,
      `<Field Type="Number" DisplayName="${AMOUNT}" Name="${AMOUNT}"/>`);
    if (!colRes.ok) log('WARN', `Could not add column '${AMOUNT}': HTTP ${colRes.status}`);
  }
  if (!(await fieldExists(listPath, AMOUNT))) {
    log('FAIL', `Column '${AMOUNT}' is still missing after the create attempt.`);
    await voidAll(`the numeric metadata column a library total needs did not provision, fixture incomplete`);
    return report();
  }

  // ---- Upload the three files ------------------------------------------
  const keepFile = (r) => {
    const t = r.FSObjType !== undefined ? r.FSObjType
      : (r.FileSystemObjectType !== undefined ? r.FileSystemObjectType : 0);
    return String(t) !== '1';
  };
  const uploadErrors = [];
  for (const f of FILES) {
    digest = await getDigest();
    const up = await rawPost(
      `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${f.leaf}',overwrite=true)`,
      'dbmlsp view-search probe file', digest
    );
    if (!up.ok) uploadErrors.push(`${f.leaf}: HTTP ${up.status}`);
  }
  if (uploadErrors.length) {
    log('FAIL', `uploads failed: ${JSON.stringify(uploadErrors)}`);
    await voidAll(`file uploads failed (${uploadErrors.length} of ${FILES.length}), fixture incomplete`);
    return report();
  }

  // ---- Set the per-file metadata ---------------------------------------
  const listed = await spGet(`${listPath}/items?$select=Id,FileLeafRef&$top=100`);
  const listedRows = (listed.ok && listed.body && Array.isArray(listed.body.value))
    ? listed.body.value
    : [];
  const idOf = (leaf) => {
    const row = listedRows.find((i) => i.FileLeafRef === leaf);
    return row ? row.Id : null;
  };
  const metaErrors = [];
  for (const f of FILES) {
    const itemId = idOf(f.leaf);
    if (itemId === null) {
      metaErrors.push(`${f.leaf}: no list item found after upload`);
      continue;
    }
    digest = await getDigest();
    const set = await spPost(`${listPath}/items(${itemId})`, {
      Title: FILE_TOKEN,
      [AMOUNT]: f.amount,
    }, digest, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    if (!set.ok) metaErrors.push(`${f.leaf}: HTTP ${set.status} ${set.text.slice(0, 120)}`);
  }
  if (metaErrors.length) {
    log('FAIL', `metadata writes failed: ${JSON.stringify(metaErrors)}`);
    await voidAll(`metadata writes failed (${metaErrors.length} of ${FILES.length}), fixture incomplete`);
    return report();
  }

  // ---- Read the fixture back and check it ------------------------------
  const back = await spGet(
    `${listPath}/items?$select=Id,FileLeafRef,Title,${AMOUNT}&$top=100&$orderby=Id`
  );
  const backRows = (back.ok && back.body && Array.isArray(back.body.value))
    ? back.body.value.filter(keepFile)
    : [];
  const plan = backRows.map((r) => ({
    file: r.FileLeafRef || String(r.Id),
    amount: Number(r[AMOUNT]),
  }));
  const planOk = plan.length === FILES.length
    && plan.every((p) => Number.isFinite(p.amount))
    && plan.reduce((sum, p) => sum + p.amount, 0) === EXPECTED_SUM;
  if (!planOk) {
    log('FAIL', `fixture read-back: ${plan.length} of ${FILES.length} file rows; ` +
      `amounts=${JSON.stringify(plan.map((p) => p.amount))}`);
    await voidAll(`fixture read-back did not match the plan (${plan.length} of ${FILES.length} file rows summing to ${EXPECTED_SUM}), fixture incomplete`);
    return report();
  }

  // ---- control-missing-column-refused: NEGATIVE CONTROL -----------------
  digest = await getDigest();
  // The missing column is named in an <Aggregations> block and in the Where
  // clause, so the refused query is an aggregation/view query exactly.
  const junkViewXml =
    '<View><Query><Where><Eq><FieldRef Name="NoSuchQueryColumn"/>'
    + '<Value Type="Text">x</Value></Eq></Where></Query>'
    + '<Aggregations Value="On"><FieldRef Name="NoSuchQueryColumn" Type="SUM"/></Aggregations>'
    + '<RowLimit>100</RowLimit></View>';
  const junk = await spPost(`${listPath}/RenderListDataAsStream`, {
    parameters: { ViewXml: junkViewXml },
  }, digest);
  const controlHeld = junk.ok === false && isRefusal(junk.status);
  if (controlHeld) {
    record('library.view.control-missing-column-refused', Q_CONTROL,
           'PASS',
           `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`);
  } else if (junk.ok) {
    record('library.view.control-missing-column-refused', Q_CONTROL,
           'FAIL',
           'a query naming a column that does not exist was ACCEPTED. Every refusal and '
           + 'every total below is unproven; this tenant does not validate query columns.');
  } else {
    record('library.view.control-missing-column-refused', Q_CONTROL,
           'NOT ESTABLISHED',
           `the control request itself failed with non-refusal HTTP ${junk.status}: `
           + junk.text.slice(0, 260));
  }

  // Every content check below stands on the fixture and on that control.
  const guarded = async (id, question, run) => {
    if (!controlHeld) {
      record(id, question, 'NOT ESTABLISHED',
             'controls not established: library.view.control-missing-column-refused did '
             + 'not hold, so refusals and totals below cannot be read', 'void');
      return;
    }
    await run();
  };

  // ---- Totals helpers (the twin list and the library share them) ------
  // RenderListDataAsStream answers a ViewXml that carries an <Aggregations>
  // block with a row whose cell key is the column name plus a .SUM suffix
  // (the grouped variant appends .agg). The response shape is walked rather
  // than assumed: every object and array in the payload is scanned for a key
  // of that shape, and the raw figure is printed beside the parsed one.
  const rowsOf = (body) => {
    if (body && Array.isArray(body.Row)) return body.Row;
    if (body && body.ListData && Array.isArray(body.ListData.Row)) return body.ListData.Row;
    return [];
  };
  const totalsOf = (payload) => {
    const found = [];
    const KEY = new RegExp(`^${AMOUNT}\\.SUM(\\.agg)?$`, 'i');
    const walk = (node, depth) => {
      if (!node || depth > 6) return;
      if (Array.isArray(node)) {
        for (const v of node) walk(v, depth + 1);
        return;
      }
      if (typeof node !== 'object') return;
      for (const key of Object.keys(node)) {
        if (KEY.test(key)) {
          const value = node[key];
          const numeric = (typeof value === 'number') ? value
            : Number(String(value).replace(/[^0-9.\-]/g, ''));
          if (Number.isFinite(numeric)) found.push({ key, raw: value, numeric });
        }
        walk(node[key], depth + 1);
      }
    };
    walk(payload, 0);
    return found;
  };
  const describeCells = (cells) => cells.length
    ? cells.map((c) => `${c.key}=${String(c.raw).slice(0, 40)}`).join(', ')
    : 'none';
  const totalsXml =
    '<View><Aggregations Value="On"><FieldRef Name="' + AMOUNT + '" Type="SUM"/></Aggregations>'
    + '<ViewFields><FieldRef Name="FileLeafRef"/><FieldRef Name="' + AMOUNT + '"/></ViewFields>'
    + '<RowLimit>10</RowLimit></View>';
  const totalsStream = async (path) => {
    digest = await getDigest();
    const r = await spPost(`${path}/RenderListDataAsStream`, {
      parameters: { ViewXml: totalsXml },
    }, digest);
    if (!r.ok) return { ok: false, status: r.status, text: r.text.slice(0, 260) };
    return { ok: true, status: r.status, rows: rowsOf(r.body), cells: totalsOf(r.body) };
  };

  // ---- Twin list setup (plain list, rows 10 and 32) --------------------
  const deleteAllItems = async (path) => {
    digest = await getDigest();
    const listed = await spGet(`${path}/items?$select=Id&$top=100`);
    const rows = (listed.ok && listed.body && Array.isArray(listed.body.value))
      ? listed.body.value
      : [];
    for (const row of rows) {
      digest = await getDigest();
      await spPost(`${path}/items(${row.Id})`, {}, digest,
                   { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    }
    return rows.length;
  };
  const ensureTwin = async () => {
    if (!(await spGet(`${twinPath}?$select=Title`)).ok) {
      digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: TWIN,
        BaseTemplate: 100,
        Description: 'dbml-sharepoint view-search probe twin list. Safe to delete.',
      }, digest);
      if (!made.ok) {
        return `could not create the twin list '${TWIN}': HTTP ${made.status} ${made.text.slice(0, 200)}`;
      }
    }
    if (!(await fieldExists(twinPath, AMOUNT))) {
      const colRes = await addField(twinPath,
        `<Field Type="Number" DisplayName="${AMOUNT}" Name="${AMOUNT}"/>`);
      if (!colRes.ok) {
        return `could not add '${AMOUNT}' to the twin list: HTTP ${colRes.status} ${colRes.text.slice(0, 200)}`;
      }
    }
    await deleteAllItems(twinPath);
    for (const amount of TWIN_AMOUNTS) {
      digest = await getDigest();
      const add = await spPost(`${twinPath}/items`, {
        Title: `twin ${amount}`,
        [AMOUNT]: amount,
      }, digest);
      if (!add.ok) {
        return `could not seed the twin row for ${amount}: HTTP ${add.status} ${add.text.slice(0, 200)}`;
      }
    }
    const twinBack = await spGet(`${twinPath}/items?$select=Id,Title,${AMOUNT}&$top=100`);
    const twinVals = (twinBack.ok && twinBack.body && Array.isArray(twinBack.body.value))
      ? twinBack.body.value.map((r) => Number(r[AMOUNT])).sort((a, b) => a - b)
      : [];
    if (twinVals.length !== 2 || twinVals[0] !== 10 || twinVals[1] !== 32) {
      return `the twin list read back amounts ${JSON.stringify(twinVals)}, not 10 and 32`;
    }
    return null;
  };

  // ---- totals-on-library: SUM over the file rows vs the twin ------------
  await guarded('library.view.totals-on-library', Q_TOTALS, async () => {
    const twinError = await ensureTwin();
    if (twinError) {
      record('library.view.totals-on-library', Q_TOTALS, 'NOT ESTABLISHED',
             `${twinError}. Without a same-run twin the library stream has no baseline to ` +
             'compare against, so no verdict is recorded.');
      return;
    }
    const twinStream = await totalsStream(twinPath);
    if (!twinStream.ok) {
      record('library.view.totals-on-library', Q_TOTALS, 'NOT ESTABLISHED',
             `the twin plain list refused the aggregation ViewXml with HTTP ${twinStream.status}: ` +
             `${twinStream.text}. A refusal on the plain list leaves no same-run baseline ` +
             'for the library stream, so no verdict is recorded.');
      return;
    }
    if (twinStream.cells.length === 0) {
      record('library.view.totals-on-library', Q_TOTALS, 'NOT ESTABLISHED',
             `the twin plain list served the aggregation ViewXml but returned no ${AMOUNT}.SUM ` +
             'cell in any row, so this tenant does not surface the stream totals shape this ' +
             'probe compares with. No verdict is recorded.');
      return;
    }
    if (twinStream.cells[0].numeric !== EXPECTED_SUM) {
      record('library.view.totals-on-library', Q_TOTALS, 'NOT ESTABLISHED',
             `the twin list returned ${describeCells(twinStream.cells)}, not the seeded sum ` +
             `${EXPECTED_SUM}, so the twin fixture is not the baseline it was built to be. ` +
             'No verdict is recorded.');
      return;
    }
    const libStream = await totalsStream(listPath);
    if (!libStream.ok) {
      if (isRefusal(libStream.status)) {
        record('library.view.totals-on-library', Q_TOTALS, 'REFUSED',
               `the twin plain list returned ${describeCells(twinStream.cells)} for the ` +
               `identical ViewXml, and the library refused the same stream with HTTP ` +
               `${libStream.status}: ${libStream.text}. That is the divergence: a library ` +
               'answers the aggregation ViewXml differently from a plain list.');
      } else {
        record('library.view.totals-on-library', Q_TOTALS, 'NOT ESTABLISHED',
               `the library stream call itself failed with non-refusal HTTP ` +
               `${libStream.status}: ${libStream.text}`);
      }
      return;
    }
    if (libStream.cells.length === 0) {
      record('library.view.totals-on-library', Q_TOTALS, 'NO TOTAL CELL',
             `the twin list returned ${describeCells(twinStream.cells)} and the library ` +
             `returned ${libStream.rows.length} file row(s) with no ${AMOUNT}.SUM cell in ` +
             'any of them, for the identical ViewXml in the same run. The file row set is ' +
             'not being aggregated the way a plain list row set is.');
      return;
    }
    const libTotal = libStream.cells[0].numeric;
    if (libTotal === EXPECTED_SUM) {
      record('library.view.totals-on-library', Q_TOTALS, 'SAME AS LIST',
             `the identical aggregation ViewXml returned ${describeCells(twinStream.cells)} ` +
             `from the twin list (rows 10 and 32) and ${describeCells(libStream.cells)} from ` +
             `the library (file rows ${plan.map((p) => p.amount).join(', ')}), both summing to ` +
             `${EXPECTED_SUM}. A library totals a numeric metadata column exactly as a list does.`);
    } else {
      record('library.view.totals-on-library', Q_TOTALS, 'TOTAL DIFFERS',
             `the twin list returned ${describeCells(twinStream.cells)} and the library ` +
             `returned ${describeCells(libStream.cells)} for the identical ViewXml in the ` +
             `same run. The library computed ${libTotal} where the seeded file rows sum to ` +
             `${EXPECTED_SUM}, so the aggregation is not summing the metadata it was asked to.`);
    }
  });

  // ---- Search helpers (GET _api/search/query, both odata flavours) ------
  // The harness spGet sends nometadata and returns no response text, so the
  // search calls use their own fetch: a query that fails has to say why.
  const odataLiteral = (value) => encodeURIComponent(String(value).replace(/'/g, "''"));
  const searchGet = async (params, flavour) => {
    const res = await fetch(`${WEB}/_api/search/query?${params}`, {
      headers: { Accept: `application/json;odata=${flavour}` },
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent XML or plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text: text.slice(0, 260) };
  };
  const unwrap = (node) => {
    if (Array.isArray(node)) return node;
    if (node && Array.isArray(node.results)) return node.results;
    return null;
  };
  const relevantResults = (payload) => {
    const candidates = [
      ['flat', payload],
      ['d', payload && payload.d],
      ['query', payload && payload.query],
      ['d.query', payload && payload.d && payload.d.query],
    ];
    for (const [shape, node] of candidates) {
      const rel = node && node.PrimaryQueryResult && node.PrimaryQueryResult.RelevantResults;
      if (rel) return { shape, rel };
    }
    return null;
  };
  const runQuery = async (kql, extra = '') => {
    const params = `querytext='${odataLiteral(kql)}'${extra}`;
    let res = await searchGet(params, 'nometadata');
    let found = res.ok ? relevantResults(res.body) : null;
    if (!found) {
      const verbose = await searchGet(params, 'verbose');
      const foundVerbose = verbose.ok ? relevantResults(verbose.body) : null;
      if (foundVerbose) { res = verbose; found = foundVerbose; }
      else if (!res.ok && verbose.ok) { res = verbose; }
    }
    if (!found) {
      return { ok: false, status: res.status, note: res.ok ? 'no result set recognised' : 'request failed' };
    }
    const table = found.rel.Table;
    const rows = (table && unwrap(table.Rows)) || [];
    const keep = [];
    for (const row of rows) {
      const cells = unwrap(row && row.Cells) || [];
      const bag = {};
      for (const c of cells) bag[String(c.Key)] = c.Value;
      keep.push(bag);
    }
    return { ok: true, status: res.status, rows: keep };
  };
  const cell = (bag, key) => {
    const hit = Object.keys(bag).find((k) => String(k).toLowerCase() === key.toLowerCase());
    return hit === undefined ? '' : String(bag[hit]);
  };

  // ---- discovery-on-library: title row and a file row in search ---------
  await guarded('library.search.discovery-on-library', Q_DISCOVERY, async () => {
    const controlQ = await runQuery('sharepoint', '&rowlimit=1');
    if (!controlQ.ok) {
      record('library.search.discovery-on-library', Q_DISCOVERY, 'NOT ESTABLISHED',
             `the search endpoint did not answer the trivial control query (HTTP ` +
             `${controlQ.status}, ${controlQ.note}). While that is open this row is about ` +
             'the endpoint, not about whether the library is discoverable.');
      return;
    }
    const titleQ = await runQuery(`"${LIB}"`, '&rowlimit=50');
    const fileQ = await runQuery(FILE_TOKEN, '&rowlimit=50');
    if (!titleQ.ok || !fileQ.ok) {
      record('library.search.discovery-on-library', Q_DISCOVERY, 'NOT ESTABLISHED',
             `the title query ${titleQ.ok ? 'answered' : `failed (HTTP ${titleQ.status}, ${titleQ.note})`} ` +
             `and the file query ${fileQ.ok ? 'answered' : `failed (HTTP ${fileQ.status}, ${fileQ.note})`}, ` +
             'so discovery could not be asked of the index.');
      return;
    }
    const libHits = [];
    const fileHits = [];
    for (const q of [titleQ, fileQ]) {
      for (const row of q.rows) {
        const cs = cell(row, 'contentclass');
        const title = cell(row, 'Title');
        const path = cell(row, 'Path') || cell(row, 'OriginalPath');
        if (cs === 'STS_List' && title.toLowerCase() === LIB.toLowerCase()) {
          if (libHits.indexOf(title) === -1) libHits.push(title);
        }
        if (path.indexOf(`${folderUrl}/`) !== -1 && fileHits.indexOf(path) === -1) {
          fileHits.push(path);
        }
      }
    }
    const zeroRows = libHits.length === 0 && fileHits.length === 0;
    if (zeroRows) {
      record('library.search.discovery-on-library', Q_DISCOVERY, 'NOT ESTABLISHED',
             `both search queries answered (title query '"${LIB}"', file query ` +
             `'${FILE_TOKEN}') but returned no row for the library or a fixture file. The ` +
             'fixture was created minutes ago and search indexing is asynchronous: this is ' +
             'consistent with crawl latency and establishes nothing about crawlability. ' +
             'Re-run tomorrow against the retained fixture before reading a zero-row ' +
             'result as a divergence.');
      return;
    }
    const bits = [];
    if (libHits.length) {
      bits.push(`the title query returned the library's own STS_List row for '${LIB}'`);
    }
    if (fileHits.length) {
      bits.push(`the file query returned ${fileHits.length} row(s) under the library folder path`);
    }
    record('library.search.discovery-on-library', Q_DISCOVERY, 'SAME AS LIST',
           `${bits.join('; ')}. A library and its files are discoverable through search ` +
           'the way a generic list and its items are (search-discovery-probe.js found a ' +
           "list's STS_List row by its title).");
  });

  return report();
})();
