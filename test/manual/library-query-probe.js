/**
 * dbml-sharepoint PROBE: DOCUMENT LIBRARY QUERY SURFACE
 *
 * REVISION: 0038cd35
 *
 * ONE QUESTION:
 *   Does the query surface of a document library diverge from a generic list?
 *
 * Round 1 settled what a file, folder, column, and content type are on a
 * library. Round 2 settles how a library interacts with list features. This
 * probe covers the query half of the document-library programme: CAML chain
 * depth, the guarded single-clause pattern, and multi-field order-by, all
 * against the file rows of a document library.
 *
 * The generic-list query surface is already probed by caml-chain-depth-probe.js
 * (ad-hoc and stored Or chains from depth 1 to 40 over a 48-member
 * MultiChoice, wrapper groups, and the ID tautology, query.caml.* and
 * query.caml-adhoc.or-chain-*). None of those rows ran against a document
 * library. This probe asks the divergence question for three shapes and does
 * not re-probe the chain sweep.
 *
 * NO LIST BASELINE FOR ORDER-BY: caml-chain-depth-probe.js measures chain
 * depth, not OrderBy, so there is no sibling list row that ordered by several
 * metadata fields for this probe to compare against. The expected file row
 * order here is computed from the fixture itself: the twelve read-back rows
 * sorted locally by the three OrderBy fields. Successive <FieldRef> elements
 * in an <OrderBy> are documented tie-breakers, so a library returning exactly
 * that order behaves like a generic list (SAME AS LIST), and any other order
 * names how the file model intrudes.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101) and loaded with twelve
 *     files whose metadata differs on a category, a rank and a band column,
 *     so the CAML predicates have rows to select and the order-by has fields
 *     to order on.
 *   library.query.control-missing-column-refused
 *     NEGATIVE CONTROL: a RenderListDataAsStream query naming a column that
 *     does not exist is refused. Without it, every refusal observed below is
 *     unproven.
 *   library.query.caml-chain-depth
 *     CAML chain depth on a library: does a deep Or chain over a metadata
 *     column return one file row per disjunct, the way a generic list does?
 *     query.caml-adhoc.or-chain-12 returns all twelve rows on a list. This
 *     leg sends the same left-folded chain shape over a library text column
 *     whose twelve values each sit on exactly one file: depth 1 first as the
 *     control that GetItems works on the library at all, then depth 12.
 *   library.query.guarded-single-clause
 *     A single Eq guarded by the Or[IsNotNull(ID), IsNull(ID)] tautology on
 *     a library: does it return the same single file row a generic list does?
 *     query.caml.tautology-conjunct-inert measured the tautology inert on a
 *     list; this leg asks whether the file row set keeps it inert.
 *   library.query.order-by-multi-field
 *     Order-by depth on a library: does RenderListDataAsStream order file
 *     rows by three metadata fields in one <OrderBy> (rank, then band, then
 *     category), the way a generic list orders rows? A library leads with
 *     the file (FileLeafRef), so ordering by metadata fields is the question.
 *
 * MICROSOFT LEARN CITATIONS
 *   Document library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Item metadata updates via MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   Ad-hoc CAML queries via POST to `GetItems`:
 *     "List.GetItems method (REST)"
 *   RenderListDataAsStream via POST to
 *     `web/lists/getbytitle(...)/RenderListDataAsStream`:
 *     "SP.List.renderListDataAsStream method"
 *   The <OrderBy> element and successive tie-breaker fields:
 *     "OrderBy Element (Query)"
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

  log('INFO', 'probe revision 0038cd35. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibQuery';
  const listPath = `web/lists/getbytitle('${LIB}')`;
  // Metadata columns: CAT is the chain discriminator (twelve distinct text
  // values, one per file) and the third order-by field; RANK and BAND are
  // the first two order-by fields, each with ties the next field breaks.
  const CAT = 'dbmlspQCat';
  const RANK = 'dbmlspQRank';
  const BAND = 'dbmlspQGroup';
  const FILE_PREFIX = 'dbmlsp-query-';
  const N = 12;
  const QS = ['Q07', 'Q09', 'Q11', 'Q01', 'Q02', 'Q03',
              'Q12', 'Q10', 'Q06', 'Q08', 'Q04', 'Q05'];
  // The twelve category values above are scattered across the twelve files so
  // that no natural order (file name, item id, upload order) lines up with
  // the metadata order the order-by leg expects. Within each (RANK, BAND)
  // pair the higher Q sits on the lower file name, so a server that stops
  // honouring the OrderBy at any field returns a sequence this probe can tell
  // apart from the full one.
  const nameOf = (f0) => `${FILE_PREFIX}${String(f0 + 1).padStart(2, '0')}.txt`;
  const titleOf = (f0) => nameOf(f0).replace(/\.txt$/, '');
  const rankOf = (f0) => (f0 % 3) + 1;
  const bandOf = (f0) => (Math.floor(f0 / 3) <= 1 ? 'G1' : 'G2');
  const GUARD_Q = 'Q01'; // sits on dbmlsp-query-04.txt

  const Q_FIXTURE = 'A document library is created (BaseTemplate 101) and loaded with twelve files whose metadata differs';
  const Q_CONTROL = 'NEGATIVE CONTROL: a RenderListDataAsStream query naming a column that does not exist is refused';
  const Q_CHAIN = 'CAML chain depth on a library: does a deep Or chain over a metadata column return one file row per disjunct, the way a generic list does';
  const Q_GUARD = 'a single Eq guarded by the Or[IsNotNull(ID), IsNull(ID)] tautology on a library: does it return the same single file row a generic list does';
  const Q_ORDER = 'order-by depth on a library: does RenderListDataAsStream order file rows by several metadata fields in one OrderBy, the way a generic list does';

  expect('library.doc-lib.fixture-library-created', Q_FIXTURE);
  expect('library.query.control-missing-column-refused', Q_CONTROL);
  expect('library.query.caml-chain-depth', Q_CHAIN);
  expect('library.query.guarded-single-clause', Q_GUARD);
  expect('library.query.order-by-multi-field', Q_ORDER);

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, add three metadata columns`);
    log('INFO', `(${CAT}, ${RANK}, ${BAND}), upload ${N} files with distinct metadata values,`);
    log('INFO', 'then ask three query questions: whether a deep CAML Or chain returns one');
    log('INFO', 'file row per disjunct, whether a single Eq guarded by the ID tautology');
    log('INFO', 'returns the same single row, and whether RenderListDataAsStream orders');
    log('INFO', 'file rows by three metadata fields the way a generic list does.');
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

  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
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

  const VOIDED = ['library.query.control-missing-column-refused',
                  'library.query.caml-chain-depth',
                  'library.query.guarded-single-clause',
                  'library.query.order-by-multi-field'];
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
      Description: 'dbml-sharepoint query probe library. Safe to delete.',
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

  // ---- Metadata columns ------------------------------------------------
  const addField = async (schemaXml) => {
    digest = await getDigest();
    return spPost(`${listPath}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };
  const fieldExists = async (name) =>
    (await spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')`)).ok;

  const fieldXml = [
    `<Field Type="Text" DisplayName="${CAT}" Name="${CAT}"/>`,
    `<Field Type="Number" DisplayName="${RANK}" Name="${RANK}"/>`,
    `<Field Type="Text" DisplayName="${BAND}" Name="${BAND}"/>`,
  ];
  const FIELD_NAMES = [CAT, RANK, BAND];
  for (let f = 0; f < FIELD_NAMES.length; f += 1) {
    if (!(await fieldExists(FIELD_NAMES[f]))) {
      const colRes = await addField(fieldXml[f]);
      if (!colRes.ok) log('WARN', `Could not add column '${FIELD_NAMES[f]}': HTTP ${colRes.status}`);
    }
  }
  let columnsReady = true;
  for (const name of FIELD_NAMES) {
    if (!(await fieldExists(name))) {
      columnsReady = false;
      log('FAIL', `Column '${name}' is still missing after the create attempt.`);
    }
  }
  if (!columnsReady) {
    await voidAll('the metadata columns a library query needs did not provision, fixture incomplete');
    return report();
  }

  // ---- Upload the twelve files ----------------------------------------
  let uploadErrors = [];
  for (let f0 = 0; f0 < N; f0 += 1) {
    digest = await getDigest();
    const up = await rawPost(
      `web/GetFolderByServerRelativeUrl('${folderUrl}')/Files/add(url='${nameOf(f0)}',overwrite=true)`,
      'dbmlsp query probe file', digest
    );
    if (!up.ok) uploadErrors.push(`${nameOf(f0)}: HTTP ${up.status}`);
  }
  if (uploadErrors.length) {
    log('FAIL', `uploads failed: ${JSON.stringify(uploadErrors)}`);
    await voidAll(`file uploads failed (${uploadErrors.length} of ${N}), fixture incomplete`);
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
  for (let f0 = 0; f0 < N; f0 += 1) {
    const leaf = nameOf(f0);
    const itemId = idOf(leaf);
    if (itemId === null) {
      metaErrors.push(`${leaf}: no list item found after upload`);
      continue;
    }
    digest = await getDigest();
    const set = await spPost(`${listPath}/items(${itemId})`, {
      Title: titleOf(f0),
      [CAT]: QS[f0],
      [RANK]: rankOf(f0),
      [BAND]: bandOf(f0),
    }, digest, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    if (!set.ok) metaErrors.push(`${leaf}: HTTP ${set.status} ${set.text.slice(0, 120)}`);
  }
  if (metaErrors.length) {
    log('FAIL', `metadata writes failed: ${JSON.stringify(metaErrors)}`);
    await voidAll(`metadata writes failed (${metaErrors.length} of ${N}), fixture incomplete`);
    return report();
  }

  // ---- Read the fixture back and check it ------------------------------
  const back = await spGet(
    `${listPath}/items?$select=Id,FileLeafRef,Title,${CAT},${RANK},${BAND}&$top=100&$orderby=Id`
  );
  const keepFile = (r) => {
    const t = r.FSObjType !== undefined ? r.FSObjType
      : (r.FileSystemObjectType !== undefined ? r.FileSystemObjectType : 0);
    return String(t) !== '1';
  };
  const backRows = (back.ok && back.body && Array.isArray(back.body.value))
    ? back.body.value.filter(keepFile)
    : [];
  const plan = backRows.map((r) => ({
    file: r.FileLeafRef || r.FileRef || r.Title || String(r.Id),
    q: String(r[CAT] !== undefined ? r[CAT] : ''),
    rank: Number(r[RANK]),
    band: String(r[BAND] !== undefined ? r[BAND] : ''),
  }));
  const planOk = plan.length === N
    && new Set(plan.map((p) => p.q)).size === N
    && plan.every((p) => QS.includes(p.q))
    && plan.every((p) => p.rank >= 1 && p.rank <= 3)
    && plan.every((p) => p.band === 'G1' || p.band === 'G2');
  if (!planOk) {
    log('FAIL', `fixture read-back: ${plan.length} of ${N} file rows; ` +
      `q values seen=${JSON.stringify(plan.map((p) => p.q))}`);
    await voidAll(`fixture read-back did not match the plan (${plan.length} of ${N} file rows with distinct metadata), fixture incomplete`);
    return report();
  }

  // ---- control-missing-column-refused: NEGATIVE CONTROL -----------------
  digest = await getDigest();
  const junkViewXml =
    '<View><Query><Where><Eq><FieldRef Name="NoSuchQueryColumn"/>'
    + '<Value Type="Text">x</Value></Eq></Where></Query><RowLimit>100</RowLimit></View>';
  const junk = await spPost(`${listPath}/RenderListDataAsStream`, {
    parameters: { ViewXml: junkViewXml },
  }, digest);
  const controlHeld = junk.ok === false && isRefusal(junk.status);
  if (controlHeld) {
    record('library.query.control-missing-column-refused', Q_CONTROL,
           'PASS',
           `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`);
  } else if (junk.ok) {
    record('library.query.control-missing-column-refused', Q_CONTROL,
           'FAIL',
           'a query naming a column that does not exist was ACCEPTED. Every refusal and '
           + 'every order below is unproven; this tenant does not validate query columns.');
  } else {
    record('library.query.control-missing-column-refused', Q_CONTROL,
           'NOT ESTABLISHED',
           `the control request itself failed with non-refusal HTTP ${junk.status}: `
           + junk.text.slice(0, 260));
  }

  // Every content check below stands on the fixture and on that control.
  const guarded = async (id, question, run) => {
    if (!controlHeld) {
      record(id, question, 'NOT ESTABLISHED',
             'controls not established: library.query.control-missing-column-refused did '
             + 'not hold, so refusals and row orders below cannot be read', 'void');
      return;
    }
    await run();
  };

  // ---- Query helpers (both CAML legs use the list baseline surface) ----
  // caml-chain-depth-probe.js sends CamlQuery to GetItems and sorts the
  // returned row titles; this probe sends the same payload shapes and sorts
  // the returned FileLeafRefs instead, because a file row is identified by
  // its leaf name. Two payload shapes are tried because the generic-list
  // probe found both accepted; the first that works is reused.
  let queryShape = null;
  const camlRows = async (where) => {
    const viewXml = `<View><Query><Where>${where}</Where></Query><RowLimit>100</RowLimit></View>`;
    const shapes = [
      ['typed', { query: { __metadata: { type: 'SP.CamlQuery' }, ViewXml: viewXml } }, VERBOSE],
      ['bare', { query: { ViewXml: viewXml } }, {}],
    ];
    for (const [name, payload, headers] of shapes) {
      if (queryShape && queryShape !== name) continue;
      digest = await getDigest();
      const got = await spPost(
        `${listPath}/GetItems?$select=FileLeafRef,Title`, payload, digest, headers
      );
      if (got.ok) {
        queryShape = name;
        return {
          ok: true,
          files: ((got.body && Array.isArray(got.body.value)) ? got.body.value : [])
            .filter(keepFile)
            .map((i) => i.FileLeafRef || i.Title || String(i.Id))
            .sort(),
          error: null,
        };
      }
      if (queryShape) {
        return { ok: false, files: null, error: `HTTP ${got.status} ${got.text.slice(0, 160)}` };
      }
    }
    return { ok: false, files: null, error: 'both CamlQuery payload shapes were refused on the library' };
  };

  const eqText = (col, value) =>
    `<Eq><FieldRef Name="${col}"/><Value Type="Text">${value}</Value></Eq>`;
  // Left fold, the same shape caml-chain-depth-probe.js and the tool's own
  // condition combiner emit. K disjuncts over the FIRST K distinct Q values.
  const chain = (values) => values.slice(1).reduce(
    (acc, v) => `<Or>${acc}${eqText(CAT, v)}</Or>`, eqText(CAT, values[0])
  );
  const chainOf = (k) => chain(QS.slice(0, k));
  const TAUTOLOGY =
    '<Or><IsNotNull><FieldRef Name="ID"/></IsNotNull><IsNull><FieldRef Name="ID"/></IsNull></Or>';
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

  // ---- caml-chain-depth: a deep Or chain over the file rows -------------
  await guarded('library.query.caml-chain-depth', Q_CHAIN, async () => {
    const depth1 = await camlRows(eqText(CAT, QS[0]));
    if (!depth1.ok) {
      record('library.query.caml-chain-depth', Q_CHAIN, 'NOT ESTABLISHED',
             `even the depth-1 control query was refused (${depth1.error}), so GetItems ` +
             'could not be used on this library and chain depth is not measurable on this surface');
      return;
    }
    if (depth1.files.length !== 1 || depth1.files[0] !== nameOf(0)) {
      record('library.query.caml-chain-depth', Q_CHAIN, 'NOT ESTABLISHED',
             `the depth-1 control query for '${QS[0]}' returned ` +
             `${JSON.stringify(depth1.files)}, not the single row for ${nameOf(0)}; ` +
             'the fixture data is not what the chain is judged against', 'void');
      return;
    }
    const deep = await camlRows(chainOf(N));
    if (!deep.ok) {
      record('library.query.caml-chain-depth', Q_CHAIN, 'QUERY REFUSED',
             `a single Eq (depth 1) returned its one file row, and the ${N}-disjunct chain ` +
             `was refused (${deep.error}). On a generic list the same chain returns all ` +
             `${N} rows (query.caml-adhoc.or-chain-12), so the file row set bounds the ` +
             'CAML nesting a library query can carry.');
      return;
    }
    const allNames = plan.map((p) => p.file).sort();
    const ok = same(deep.files, allNames);
    record('library.query.caml-chain-depth', Q_CHAIN,
           ok ? 'SAME AS LIST' : `RETURNED ${deep.files.length} OF ${N}`,
           ok
             ? `the ${N}-disjunct Or chain over ${CAT} returned all ${N} file rows, one per ` +
               'disjunct, exactly as a generic list does. Every disjunct was evaluated.'
             : `the ${N}-disjunct Or chain returned ${deep.files.length} of ${N} file rows; ` +
               `expected ${JSON.stringify(allNames)}, got ${JSON.stringify(deep.files)}. Each ` +
               'disjunct names a category value on exactly one file, so a shortfall is ' +
               'evaluation stopping early and the rows returned say which disjuncts survived.');
  });

  // ---- guarded-single-clause: one Eq guarded by the ID tautology --------
  await guarded('library.query.guarded-single-clause', Q_GUARD, async () => {
    const bare = await camlRows(eqText(CAT, GUARD_Q));
    const guardedXml = `<And>${eqText(CAT, GUARD_Q)}${TAUTOLOGY}</And>`;
    const guardedRows = await camlRows(guardedXml);
    const bareFile = plan.find((p) => p.q === GUARD_Q);
    if (!bareFile) {
      record('library.query.guarded-single-clause', Q_GUARD, 'NOT ESTABLISHED',
             `no file row holds '${GUARD_Q}', so the guard leg has nothing to select`, 'void');
      return;
    }
    if (!bare.ok || !guardedRows.ok) {
      record('library.query.guarded-single-clause', Q_GUARD, 'QUERY REFUSED',
             `bare Eq ${bare.ok ? 'ok' : bare.error}; guarded And[Eq, tautology] ` +
             `${guardedRows.ok ? 'ok' : guardedRows.error}. On a generic list the tautology ` +
             'conjunct is stored and replayed (query.caml.tautology-conjunct-inert), so a ' +
             'library refusing the guarded shape is a divergence in the file row set.');
      return;
    }
    const want = [bareFile.file].sort();
    const ok = same(guardedRows.files, want);
    record('library.query.guarded-single-clause', Q_GUARD,
           ok ? 'SAME AS LIST' : 'GUARD CHANGED THE ROW SET',
           ok
             ? `the bare Eq returned ${bare.files.length} row(s) and the guarded ` +
               `And[Eq('${GUARD_Q}'), Or[IsNotNull(ID), IsNull(ID)]] returned the same ` +
               `${JSON.stringify(guardedRows.files)}: the tautology is inert on the file row ` +
               'set, exactly as it is on a generic list.'
             : `the bare Eq returned ${JSON.stringify(bare.files)} and the guarded clause ` +
               `returned ${JSON.stringify(guardedRows.files)}. On a generic list the ` +
               'tautology conjunct changes nothing (query.caml.tautology-conjunct-inert), so ' +
               'the file row set is not treating the ID tautology as inert.');
  });

  // ---- order-by-multi-field: RenderListDataAsStream over metadata -------
  await guarded('library.query.order-by-multi-field', Q_ORDER, async () => {
    const cmp = (x, y) => (x < y ? -1 : x > y ? 1 : 0);
    const sortPlan = (rows, keys) => rows.slice().sort((a, b) => {
      for (const key of keys) {
        const c = cmp(a[key], b[key]);
        if (c) return c;
      }
      return 0;
    });
    // The expected order comes from the fixture itself: sort the read-back
    // rows by the three OrderBy fields, which is exactly the tie-breaking
    // CAML documents for any list. File name order and item id order are the
    // two orders a library could fall back to if it stops honouring fields.
    const expected = sortPlan(plan, ['rank', 'band', 'q']).map((p) => p.file);
    const rankFile = sortPlan(plan, ['rank', 'file']).map((p) => p.file);
    const rankCat = sortPlan(plan, ['rank', 'q']).map((p) => p.file);
    const fileAsc = sortPlan(plan, ['file']).map((p) => p.file);

    const viewXml =
      `<View><Query><OrderBy><FieldRef Name="${RANK}" Ascending="TRUE"/>` +
      `<FieldRef Name="${BAND}"/><FieldRef Name="${CAT}"/></OrderBy></Query>` +
      `<ViewFields><FieldRef Name="FileLeafRef"/></ViewFields>` +
      '<RowLimit>100</RowLimit></View>';
    digest = await getDigest();
    const rendered = await spPost(`${listPath}/RenderListDataAsStream`, {
      parameters: { ViewXml: viewXml },
    }, digest);
    if (!rendered.ok) {
      record('library.query.order-by-multi-field', Q_ORDER, 'QUERY REFUSED',
             `RenderListDataAsStream refused the three-field OrderBy with HTTP ` +
             `${rendered.status}: ${rendered.text.slice(0, 240)}. A generic list orders by ` +
             'every field it is given, so this is a divergence in the file row set.');
      return;
    }
    const rowArr = (rendered.body && Array.isArray(rendered.body.Row))
      ? rendered.body.Row
      : ((rendered.body && rendered.body.ListData && Array.isArray(rendered.body.ListData.Row))
        ? rendered.body.ListData.Row
        : []);
    const actual = rowArr
      .filter(keepFile)
      .map((r) => r.FileLeafRef || String(r.FileRef || '').split('/').pop() || r.Title)
      .filter((leaf) => leaf);
    if (same(actual, expected)) {
      record('library.query.order-by-multi-field', Q_ORDER, 'SAME AS LIST',
             `RenderListDataAsStream returned ${actual.length} file rows in exactly the ` +
             `${RANK}, then ${BAND}, then ${CAT} order a generic list produces: ` +
             `${actual.join(', ')}. Every listed field acted as the tie-breaker for the ` +
             'field before it.');
    } else if (same(actual, rankFile)) {
      record('library.query.order-by-multi-field', Q_ORDER, 'FILE LEADS THE TIE-BREAKS',
             `the file rows are grouped by ${RANK} (the first OrderBy field), but within a ` +
             `rank the order is the file name (${actual.join(', ')}), not ${BAND} then ` +
             `${CAT}. A generic list orders by every listed field; this library honours ` +
             'the first field and then falls back to the file identity.');
    } else if (same(actual, rankCat)) {
      record('library.query.order-by-multi-field', Q_ORDER, 'MIDDLE FIELD IGNORED',
             `the file rows order by ${RANK} and ${CAT} but not by ${BAND}: ` +
             `${actual.join(', ')}. A generic list honours ${BAND} as the second ` +
             'tie-breaker, so the middle field is being dropped by the file row set.');
    } else if (same(actual, fileAsc)) {
      record('library.query.order-by-multi-field', Q_ORDER, 'ORDER IGNORED',
             `RenderListDataAsStream returned the file rows in plain file-name order ` +
             `(${actual.join(', ')}), as if the OrderBy had no effect. A generic list ` +
             'orders by the fields it is given.');
    } else {
      record('library.query.order-by-multi-field', Q_ORDER, 'ORDER DIVERGES',
             `expected ${expected.join(', ')} but got ${actual.join(', ')}. The order is ` +
             'neither the full metadata order, nor the first-field-then-file order, nor ' +
             'plain file order, so the divergence does not match any simple file-model rule.');
    }
  });

  return report();
})();
