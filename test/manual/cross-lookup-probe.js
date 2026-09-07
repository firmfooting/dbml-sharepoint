/**
 * dbml-sharepoint PROBE: DOES A DOCUMENT LIBRARY JOIN LIKE A LIST DOES?
 *
 * ONE QUESTION, in two directions:
 *   `projected-lookup-probe.js` and `multilookup-probe.js` measured lookups
 *   whose SOURCE and TARGET were both generic lists. A lookup held ON a
 *   document library, and a lookup whose TARGET is a document library, are
 *   unmeasured. Does either one create, hold a value, project through a view
 *   and take an index the way the list-to-list shape does?
 *
 * REVISION: 8db68e8e
 *
 * WHY: `analysis/joins.py` counts every lookup the same way and the deploy
 * emits every lookup the same way, whichever container is at each end. A
 * library is the container this project knows least about, and the two
 * directions are not one question: `list -> library` points at rows that are
 * FILES, and `library -> list` puts a lookup on a container whose rows cannot
 * be created by an item POST at all (`document-library-probe.js` recorded the
 * refusal: "To add an item to a document library, use SPFileCollection.Add()").
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. A question belongs under `library` when it
 * is about how a document library diverges from a generic list, which is what
 * both directions are about, so the measurements file under `library.lookup.*`.
 * The three join rows file under `scale.join.*`, because a ceiling on how many
 * lookups one view may project is a join question wherever it is measured, and
 * `multilookup-probe.js` files its own join rows there for the same reason.
 * The library-creation row keeps the id the other library probes share.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)? The same
 *        question by the same method as `library-columns-probe.js`,
 *        `file-operations-probe.js`, `folder-probe.js`,
 *        `library-content-type-probe.js` and `library-form-probe.js`, so it
 *        keeps their id.
 *   library.lookup.fixture-containers-ready
 *        Do the three containers, the two target rows, the uploaded file, the
 *        folder and the source row all exist?
 *   library.lookup.control-list-to-list-lookup-created
 *        POSITIVE CONTROL: does the shape this probe sends, a Lookup created
 *        by `createfieldasxml` naming a target by GUID, work at all here when
 *        both ends are generic lists? That is the shape
 *        `projected-lookup-probe.js` already measured, so a failure says the
 *        METHOD did not work on this site, not that a library is special.
 *        Every cross-container row is then void rather than open.
 *   library.lookup.control-unsupported-operand-refused
 *        NEGATIVE CONTROL: does the same `createfieldasxml` call refuse a
 *        schema SharePoint rejects, visibly enough for this probe to read the
 *        refusal? Without it an ACCEPTED row below is not a finding, because
 *        this probe could not tell a created column from a refused one. The
 *        schema sent is a Calculated column whose formula names the positive
 *        control's Lookup, which `analysis/checks/_structure.py` records
 *        SharePoint refusing on a live tenant on 2026-08-10 with HTTP 500,
 *        "One or more column references are not allowed, because the columns
 *        are defined as a data type that is not supported in formulas". It
 *        runs after the positive control, because the operand it names is the
 *        column the positive control creates.
 *   library.lookup.library-to-list-created
 *        LIBRARY -> LIST: is a Lookup column on a document library, targeting
 *        a generic list's `Title`, created, and does it read back as a Lookup
 *        bound to that list and that field?
 *   library.lookup.library-to-list-item-write
 *        What is the write shape on a library? The row being written is a
 *        FILE, reached through the library's `items(id)` rather than created
 *        by an item POST. Does setting `<name>Id` on it take and read back?
 *   library.lookup.library-to-list-indexed
 *        Does `Indexed: true` stick on that column?
 *   library.lookup.list-to-library-title-created
 *        LIST -> LIBRARY: is a Lookup column on a generic list, targeting a
 *        document library's `Title`, created and bound?
 *   library.lookup.list-to-library-name-created
 *        The same, targeting `FileLeafRef`, the Name column a library has and
 *        a generic list does not. This is where the containers differ, so it
 *        is asked as its own question rather than folded into the row above.
 *   library.lookup.list-to-library-item-write
 *        Does setting that lookup to a FILE's item id take, read back, and
 *        project a label through `$expand`?
 *   library.lookup.list-to-library-folder-row-selectable
 *        Does the same lookup accept a FOLDER's item id? A folder is an item
 *        of the library and is not a file, so this is the machine half of
 *        "files or items": if a folder row is settable the lookup ranges over
 *        ITEMS, and if it is refused the lookup ranges over FILES.
 *   library.lookup.list-to-library-indexed
 *        Does `Indexed: true` stick on a lookup whose target is a library?
 *   library.lookup.picker-enumerates-files
 *        The visible half of the same question: what does the picker actually
 *        OFFER? Needs a capture; see the finding below for why.
 *   scale.join.control-list-lookup-ceiling
 *        CONTROL and baseline: how many single-value list-to-list lookups can
 *        one view project on this fixture? The ceiling was only ever measured
 *        past the item threshold, so if none appears here the two rows below
 *        have nothing to compare against and are void.
 *   scale.join.library-lookup-ceiling
 *        The same walk on a DOCUMENT LIBRARY. Reports a number, and the
 *        comparison with the row above is the answer.
 *   scale.join.list-to-library-costs-a-join
 *        Walk the baseline lookups again with the list-to-library lookup
 *        appended. The difference between the two walks is its cost.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the three containers exist; the target
 *   rows, the file and the folder exist; a list-to-list Lookup is created and
 *   reads back bound to its target; the same `createfieldasxml` call refuses a
 *   Calculated column whose formula names a Lookup operand.
 *   Observes (recorded, never asserted): whether each cross-container Lookup
 *   is accepted, what `LookupList`, `LookupField` and `TypeAsString` read
 *   back, whether an item write takes, what `$expand` projects, whether a
 *   folder row is settable, whether `Indexed` sticks, and the two join
 *   ceilings. NOTHING here asserts that a library takes part in a lookup at
 *   all. A run where every cross-container create is refused is a successful
 *   run with an important answer.
 *
 * THE FIXTURE IS ACYCLIC ON PURPOSE, and the reason is recorded as a finding
 * below. Three containers, and every lookup points one way:
 *
 *     source list --------> target list      (the baseline and the control)
 *     source list --------> library          (list -> library, two of them)
 *     library ------------> target list      (library -> list)
 *
 * VERBOSE OData ON THE INDEX WRITES. `__metadata` is a verbose construct and
 * the harness defaults to `odata=nometadata`, which REJECTS the type hint
 * rather than ignoring it. `threshold-index-probe.js` lost a whole live run to
 * exactly this. `test_a_probe_sending_metadata_uses_verbose_odata` pins it.
 *
 * MICROSOFT LEARN CITATIONS. Every URL below is one Learn documents rather
 * than one assembled from memory, because a wrong spelling returns 404,
 * `isRefusal` counts 404 as a refusal, and the probe would then print a claim
 * about SharePoint that was really a typo:
 *
 *   List and library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`, and the `List`,
 *   `ShowField` and `Mult` attributes of a Lookup field:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Field MERGE via `fields/getbyinternalnameortitle(...)`, and `Indexed`
 *   itself, read/write, "TRUE if the column is indexed for use in view
 *   filters": the same Fields reference.
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Folder creation via `RootFolder/folders/add(url=)`:
 *     "Working with folders and files with REST"
 *   Item metadata updates via MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   Projecting a view's columns without the view object:
 *     "SP.List.renderListDataAsStream method"
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the source list FIRST, then the library, then the
 * target list. That order is not tidiness; see the acyclic finding below.
 */
// finding: cross-lookup-dangling-list-guid-accepted - a lookup column naming a
// List GUID no list on the web has is ACCEPTED at creation and read back,
// rather than refused. Measured on 2026-09-07: createfieldasxml answered HTTP
// 200 and the column read back LookupList holding the GUID that names nothing.
// This is the observation that broke the original negative control, which was
// written on the assumption of a refusal and therefore reported CONTROL
// FAILED, METHOD VOID and voided every measurement under it. A lookup's `List`
// is stored as written and resolved later, so acceptance of a create says
// nothing about the target existing. The control was rewritten to a case
// SharePoint is measured to refuse; see the row itself. No lookup-specific
// refusal was available to use instead: the two candidates are both known not
// to refuse, this one by the run above and a wrong `ShowField` by Learn's
// `Field element (List)`, which lookup-showfield-probe.js records as warning
// that a display name there "does not raise an error, but breaks the field".
// finding: cross-lookup-fixture-must-be-acyclic - the three containers are
// arranged so no two look up into each other. `multilookup-probe.js` records
// that SharePoint refuses to recycle a list another list's lookup points into,
// which is why it recycles its probe list before its target. A probe measuring
// both directions between the SAME two containers would make each one the
// other's target, and neither could then be recycled: the operator would be
// left with two containers they cannot remove and no message saying why. Any
// later cross-container probe has to keep this shape, and CLEANUP here deletes
// source before library before target for the same reason.
// finding: cross-lookup-library-join-cost-not-subtractable - the cost of a
// lookup is measured by subtracting two walks, which needs a lookup of KNOWN
// cost to walk with. On a generic list that exists: a list-to-list lookup is
// the shape `analysis/joins.py` counts as one. On a document library every
// lookup is a cross-container lookup, so a walk built from them and a column
// under test drawn from the same family would return 1 by construction and
// measure nothing. The library side therefore reports a CEILING, next to the
// list's ceiling on the same fixture, and the comparison is the finding.
// finding: cross-lookup-picker-enumeration-is-a-visible-question - what a
// lookup picker OFFERS is rendered by the browser and is not exposed as a
// candidate set over REST, so the machine lane cannot read it. What the
// machine lane can do is ask whether a FOLDER row of the library is a settable
// value, which separates "ranges over items" from "ranges over files" by
// behaviour rather than by appearance. The enumeration itself stays
// awaiting-capture, with the machine row beside it as its control.
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

  log('INFO', 'probe revision 8db68e8e. Quote this when reporting results.');

  // Three containers, never two. See the acyclic finding in the header.
  const LIB = 'dbmlsp Probe XLookup Lib';
  const SRC = 'dbmlsp Probe XLookup List';
  const TGT = 'dbmlsp Probe XLookup Target';
  const FILE = 'dbmlsp-xlookup.txt';
  const FOLDER = 'dbmlsp-xlookup-folder';
  const SRC_ROW = 'dbmlsp xlookup source row';
  const TGT_ROWS = ['dbmlsp xlookup target A', 'dbmlsp xlookup target B'];

  const LIB_TO_LIST = 'XLibToList';
  const LIST_TO_LIB_TITLE = 'XListToLibTitle';
  const LIST_TO_LIB_NAME = 'XListToLibName';
  const CONTROL_LOOKUP = 'XListToList';
  // The negative control's column. A Calculated field whose formula names a
  // Lookup operand, which is one of the five operand types
  // calculated-operand-probe.js measured SharePoint refusing at field
  // creation. Not a lookup naming a target that does not exist: that case was
  // measured ACCEPTED, and the dangling-GUID finding in the header records it.
  const CONTROL_CALC = 'XCalcOverLookup';

  // How many empty lookups each join walk creates to walk up to a ceiling
  // with. 14 is the figure threshold-index-probe.js used to find 12, so a
  // ceiling of 12 is reachable and a ceiling above 14 reports NO CEILING
  // FOUND rather than a wrong number.
  const JOIN_COLUMNS = 14;
  // How long the one bounded re-read waits. Same figure and same reasoning as
  // list-settings-probe.js: a readback racing a write is a false negative, a
  // retry loop eventually passes anything.
  const REREAD_MS = 1500;

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const srcPath = `web/lists/getbytitle('${odataName(SRC)}')`;
  const tgtPath = `web/lists/getbytitle('${odataName(TGT)}')`;
  const fieldPath = (container, name) =>
    `${container}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' and two generic lists,`);
    log('INFO', `'${SRC}' and '${TGT}', on ${WEB}.`);
    log('INFO', `Would upload one text file and create one folder in '${LIB}',`);
    log('INFO', `seed ${TGT_ROWS.length} rows in '${TGT}' and one row in '${SRC}'.`);
    log('INFO', `Would create ${LIB_TO_LIST} on the LIBRARY pointing at '${TGT}',`);
    log('INFO', `${LIST_TO_LIB_TITLE} and ${LIST_TO_LIB_NAME} on '${SRC}' pointing at the`);
    log('INFO', `LIBRARY, and ${CONTROL_LOOKUP} on '${SRC}' pointing at '${TGT}' as a positive`);
    log('INFO', `control. Would then send ${CONTROL_CALC}, a Calculated column computing from`);
    log('INFO', `${CONTROL_LOOKUP}, as a negative control, which SharePoint is measured to refuse.`);
    log('INFO', 'Would then write a value through each direction, MERGE Indexed=true onto');
    log('INFO', `each cross-container lookup, and create up to ${JOIN_COLUMNS} empty lookups`);
    log('INFO', 'on the library and on the source list to walk each one to its join ceiling.');
    log('INFO', 'Nothing outside these three lists is touched.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${SRC}', then '${LIB}', then '${TGT}' would be RECYCLED`);
      log('INFO', 'first, in that order, because a list a lookup points into cannot be removed.');
    } else {
      log('INFO', 'CLEANUP is off: existing lists would be reused, and a lookup column that');
      log('INFO', 'already exists answers nothing about creating one. Set CLEANUP = true.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.lookup.fixture-containers-ready', 'The three containers, the target rows, the file and the folder all exist');
  expect('library.lookup.control-list-to-list-lookup-created', 'POSITIVE CONTROL: a Lookup created by createfieldasxml between two generic lists is created and reads back bound');
  expect('library.lookup.control-unsupported-operand-refused', 'NEGATIVE CONTROL: the same createfieldasxml call refuses a Calculated column whose formula names a Lookup operand');
  expect('library.lookup.library-to-list-created', 'LIBRARY -> LIST: is a Lookup on a document library, targeting a list Title, created and bound?');
  expect('library.lookup.library-to-list-item-write', 'Does setting that lookup on a FILE row of the library take and read back?');
  expect('library.lookup.library-to-list-indexed', 'Does Indexed=true stick on a lookup column held by a document library?');
  expect('library.lookup.list-to-library-title-created', 'LIST -> LIBRARY: is a Lookup on a generic list, targeting a library Title, created and bound?');
  expect('library.lookup.list-to-library-name-created', 'Is the same Lookup created against FileLeafRef, the Name column a library has and a list does not?');
  expect('library.lookup.list-to-library-item-write', 'Does setting that lookup to a FILE row take, read back, and project a label through $expand?');
  expect('library.lookup.list-to-library-folder-row-selectable', 'Does the same lookup accept a FOLDER row of the library, which is an item and not a file?');
  expect('library.lookup.list-to-library-indexed', 'Does Indexed=true stick on a lookup column whose target is a document library?');
  expect('library.lookup.picker-enumerates-files', 'Does the picker for a list-to-library lookup offer files, or every item including folders?');
  expect('scale.join.control-list-lookup-ceiling', 'CONTROL: how many single-value list-to-list lookups can one view project on this fixture?');
  expect('scale.join.library-lookup-ceiling', 'How many lookups can one view project on a DOCUMENT LIBRARY?');
  expect('scale.join.list-to-library-costs-a-join', 'How many joins does a lookup whose target is a library cost against the view ceiling?');

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  // LookupList reads back braced and SharePoint is not consistent about case,
  // so a string comparison of two spellings of one GUID would report a wrong
  // binding on a correct column.
  const sameGuid = (left, right) => {
    const bare = (value) => String(value === null || value === undefined ? '' : value)
      .replace(/[{}]/g, '').toLowerCase();
    return bare(left) !== '' && bare(left) === bare(right);
  };

  // A raw request body, not JSON: Files/add takes the file's bytes.
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

  const addField = async (container, schemaXml) => {
    const digest = await getDigest();
    return spPost(`${container}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };

  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the WHOLE request, so a column missing one
  // property would read as a column that cannot be read at all.
  const readField = async (container, name) => spGet(fieldPath(container, name));

  const mergeField = async (container, name, body, type) => {
    const digest = await getDigest();
    return spPost(fieldPath(container, name), { __metadata: { type }, ...body }, digest, {
      Accept: 'application/json;odata=verbose',
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };

  const mergeItem = async (container, itemId, body) => {
    const digest = await getDigest();
    return spPost(`${container}/items(${itemId})`, body, digest, {
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };

  // The entity type SharePoint itself reports for a field, read verbose
  // because nometadata is defined by not carrying it. Only ever consulted
  // after a refusal, to separate a rejected TYPE from a rejected WRITE.
  const entityTypeOf = async (container, name) => {
    try {
      const res = await fetch(`${WEB}/_api/${fieldPath(container, name)}`, {
        headers: { Accept: 'application/json;odata=verbose' },
      });
      if (!res.ok) return null;
      const body = await res.json().catch(() => null);
      return (body && body.d && body.d.__metadata && body.d.__metadata.type) || null;
    } catch {
      return null;
    }
  };

  const lookupXml = (name, targetId, showField) =>
    `<Field Type="Lookup" DisplayName="${name}" Name="${name}"`
    + ` List="{${targetId}}" ShowField="${showField}"/>`;

  // Create one lookup and read it back, returning everything a row might want
  // to print. Says nothing about whether the result is good: the caller owns
  // the verdict, because the same shape is a control in one place and the
  // measurement in another.
  const makeLookup = async (container, name, targetId, showField) => {
    const made = await addField(container, lookupXml(name, targetId, showField));
    const read = await readField(container, name);
    const bound = !readFailed(read)
      && read.body.TypeAsString === 'Lookup'
      && sameGuid(read.body.LookupList, targetId)
      && read.body.LookupField === showField;
    return {
      made,
      read,
      bound,
      description: `create HTTP ${made.status}`
        + (made.ok ? '' : `: ${clip(made.text, 200)}`)
        + '; readback '
        + (readFailed(read)
          ? `failed HTTP ${read.status}`
          : `TypeAsString=${show(read.body.TypeAsString)} `
            + `LookupList=${show(read.body.LookupList)} `
            + `LookupField=${show(read.body.LookupField)} `
            + `AllowMultipleValues=${show(read.body.AllowMultipleValues)}`),
    };
  };

  // MERGE Indexed:true and say what happened, in the four outcomes the list
  // side already distinguishes. The first attempt names SP.Field because that
  // is the body `templates/deploy/_indexes.js.j2` ships; sending anything else
  // first would measure a method this project does not use.
  const indexedNow = (read) => !readFailed(read) && read.body.Indexed === true;
  const tryIndex = async (container, name) => {
    const before = await readField(container, name);
    if (readFailed(before) || typeof before.body.Indexed !== 'boolean') {
      return {
        outcome: 'NOT ESTABLISHED',
        evidence: `${name} could not be read as a field carrying an Indexed property `
          + `(HTTP ${before.status}), so nothing was written to it`,
      };
    }
    if (before.body.Indexed === true) {
      return {
        outcome: 'NOT ESTABLISHED',
        evidence: `${name} already read Indexed=true before this run wrote anything, so a `
          + 'readback of true would say nothing about the write. threshold-index-probe.js '
          + 'measured SharePoint indexing a column on its own between two runs, so this is '
          + 'a live possibility. Re-run with CLEANUP = true.',
      };
    }
    const wrote = await mergeField(container, name, { Indexed: true }, 'SP.Field');
    let after = await readField(container, name);
    let reRead = false;
    if (wrote.ok && !indexedNow(after)) {
      await sleep(REREAD_MS);
      after = await readField(container, name);
      reRead = true;
    }
    if (wrote.ok) {
      const stuck = indexedNow(after);
      return {
        outcome: stuck ? 'INDEXED' : 'SILENTLY IGNORED',
        evidence: `MERGE Indexed:true as SP.Field returned HTTP ${wrote.status}; `
          + 'Indexed read false before and '
          + `${readFailed(after) ? `unreadable after (HTTP ${after.status})` : show(after.body.Indexed)} after`
          + (reRead ? `, on a re-read ${REREAD_MS} ms later` : '')
          + (stuck ? '' : '. The write was accepted and changed nothing, which is the '
            + 'failure class this repository exists to close'),
      };
    }
    if (!isRefusal(wrote.status)) {
      return {
        outcome: 'NOT ESTABLISHED',
        evidence: `the MERGE failed with HTTP ${wrote.status}, which is about who is asking or `
          + `about the moment rather than the server refusing it: ${clip(wrote.text, 200)}`,
      };
    }
    // Refused as SP.Field. Ask once more with the type SharePoint reports for
    // this field, because a rejected type hint and a rejected write are
    // otherwise the same observation.
    const ownType = await entityTypeOf(container, name);
    const retried = ownType && ownType !== 'SP.Field'
      ? await mergeField(container, name, { Indexed: true }, ownType)
      : null;
    const afterRetry = retried && retried.ok ? await readField(container, name) : null;
    const asBase = `MERGE Indexed:true as SP.Field was REFUSED, HTTP ${wrote.status}: `
      + clip(wrote.text, 240);
    if (afterRetry !== null && indexedNow(afterRetry)) {
      return {
        outcome: 'INDEXED',
        evidence: `${asBase}. Retried naming the type SharePoint reports for this field, `
          + `${ownType}: HTTP ${retried.status}, and Indexed read back true. The refusal was `
          + 'the TYPE HINT, not the column. Note the deployer sends SP.Field.',
      };
    }
    return {
      outcome: 'REFUSED',
      evidence: `${asBase}. `
        + (retried === null
          ? (ownType === null
            ? 'The field entity type could not be read, so a type mismatch was not ruled out.'
            : `SharePoint reports this field as ${ownType}, the same base type, so there was `
              + 'no type mismatch to rule out.')
          : `Retried as ${ownType}: HTTP ${retried.status}`
            + (retried.ok
              ? ', and Indexed read back '
                + `${afterRetry && !readFailed(afterRetry) ? show(afterRetry.body.Indexed) : 'unreadable'}`
              : `: ${clip(retried.text, 160)}`)
            + '. The refusal is the column, not the type hint.'),
    };
  };

  // Project a set of columns without a stored view, so All Items' automatic
  // Author and Editor are not in the count and the only variable across rows
  // is how many lookups are asked for. Read at odata=nometadata, as
  // multilookup-probe.js and threshold-index-probe.js both read it, so the
  // three join measurements are made through one dialect rather than three.
  const renderStream = async (container, fields) => {
    const viewXml = '<View><Query></Query>'
      + `<ViewFields>${fields.map((f) => `<FieldRef Name='${f}'/>`).join('')}</ViewFields>`
      + '<RowLimit>50</RowLimit></View>';
    const digest = await getDigest();
    const res = await spPost(`${container}/RenderListDataAsStream`,
      { parameters: { ViewXml: viewXml } }, digest,
      { 'Content-Type': 'application/json;odata=verbose' });
    if (!res.ok) {
      return { ok: false, status: res.status, error: clip(res.text, 200), present: () => false, rows: 0 };
    }
    const rows = res.body && Array.isArray(res.body.Row) ? res.body.Row : [];
    const keys = rows.length ? Object.keys(rows[0]) : [];
    // A view that renders is only evidence about join cost if the column under
    // test was actually PROJECTED. A silently dropped ViewField looks exactly
    // like a join that was free, and threshold-index-probe.js was caught by
    // that once on its own fixture.
    const present = (name) => keys.some(
      (k) => k === name || k.startsWith(`${name}.`) || k === `${name}Id`,
    );
    return { ok: true, status: res.status, error: null, present, rows: rows.length };
  };

  // Create up to JOIN_COLUMNS empty lookups on one container and walk the
  // widths until a render stops projecting the newest one. Stops at the FIRST
  // failure, because the ceiling is what the first failure means. The columns
  // are never written to: whether an empty lookup still costs a join is part
  // of the question, and threshold-index-probe.js measured its ceiling the
  // same way, so the runs are comparable.
  const walkCeiling = async (container, prefix, targetId, trailing) => {
    const columns = [];
    const createErrors = [];
    for (let n = 1; n <= JOIN_COLUMNS; n += 1) {
      const name = `${prefix}${n}`;
      const made = await addField(container, lookupXml(name, targetId, 'Title'));
      if (made.ok || !readFailed(await readField(container, name))) {
        columns.push(name);
      } else {
        createErrors.push(`${name}: HTTP ${made.status} ${clip(made.text, 120)}`);
        break;
      }
    }
    const last = trailing || null;
    let reached = last ? -1 : 0;
    let failure = '';
    for (let n = last ? 0 : 1; n <= columns.length; n += 1) {
      const asked = ['Title', ...columns.slice(0, n)];
      if (last) asked.push(last);
      const rendered = await renderStream(container, asked);
      const wanted = last || columns[n - 1];
      if (rendered.ok && rendered.present(wanted)) { reached = n; continue; }
      failure = rendered.ok
        ? `HTTP ${rendered.status} but '${wanted}' was not projected (${rendered.rows} row(s) returned)`
        : `HTTP ${rendered.status} ${rendered.error}`;
      break;
    }
    return { columns, createErrors, reached, failure };
  };

  // CLEANUP order is the acyclic finding in reverse: the source list holds
  // lookups into the library and into the target, and the library holds one
  // into the target, so a container is only removable once nothing points at
  // it. Taking the target first would fail and leave all three behind.
  await resetList(SRC);
  await resetList(LIB);
  await resetList(TGT);

  // ---- fixture-library-created -----------------------------------------
  let digest = await getDigest();
  const existingLib = await spGet(libPath);
  let libraryReady = false;
  if (existingLib.ok) {
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
           'ALREADY PRESENT',
           `reusing an existing '${LIB}'. Its columns may carry an earlier run's lookups. `
           + 'Set CLEANUP = true for a clean answer');
    libraryReady = true;
  } else {
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint cross-lookup probe library. Safe to delete.',
    }, digest);
    record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${clip(made.text, 300)}`);
    libraryReady = made.ok;
  }

  // Every id this probe can still answer once the library is known to exist.
  // Named here rather than assembled, so an abort reports the same set the
  // catalogue declares.
  const abortEverything = (reason) => {
    record('library.lookup.fixture-containers-ready', 'The three containers, the target rows, the file and the folder all exist', 'ABORTED', reason);
    record('library.lookup.control-list-to-list-lookup-created', 'POSITIVE CONTROL: a Lookup created by createfieldasxml between two generic lists is created and reads back bound', 'ABORTED', reason);
    record('library.lookup.control-unsupported-operand-refused', 'NEGATIVE CONTROL: the same createfieldasxml call refuses a Calculated column whose formula names a Lookup operand', 'ABORTED', reason);
    record('library.lookup.library-to-list-created', 'LIBRARY -> LIST: is a Lookup on a document library, targeting a list Title, created and bound?', 'ABORTED', reason);
    record('library.lookup.library-to-list-item-write', 'Does setting that lookup on a FILE row of the library take and read back?', 'ABORTED', reason);
    record('library.lookup.library-to-list-indexed', 'Does Indexed=true stick on a lookup column held by a document library?', 'ABORTED', reason);
    record('library.lookup.list-to-library-title-created', 'LIST -> LIBRARY: is a Lookup on a generic list, targeting a library Title, created and bound?', 'ABORTED', reason);
    record('library.lookup.list-to-library-name-created', 'Is the same Lookup created against FileLeafRef, the Name column a library has and a list does not?', 'ABORTED', reason);
    record('library.lookup.list-to-library-item-write', 'Does setting that lookup to a FILE row take, read back, and project a label through $expand?', 'ABORTED', reason);
    record('library.lookup.list-to-library-folder-row-selectable', 'Does the same lookup accept a FOLDER row of the library, which is an item and not a file?', 'ABORTED', reason);
    record('library.lookup.list-to-library-indexed', 'Does Indexed=true stick on a lookup column whose target is a document library?', 'ABORTED', reason);
    record('library.lookup.picker-enumerates-files', 'Does the picker for a list-to-library lookup offer files, or every item including folders?', 'ABORTED', reason);
    record('scale.join.control-list-lookup-ceiling', 'CONTROL: how many single-value list-to-list lookups can one view project on this fixture?', 'ABORTED', reason);
    record('scale.join.library-lookup-ceiling', 'How many lookups can one view project on a DOCUMENT LIBRARY?', 'ABORTED', reason);
    record('scale.join.list-to-library-costs-a-join', 'How many joins does a lookup whose target is a library cost against the view ceiling?', 'ABORTED', reason);
    return report();
  };

  if (!libraryReady) {
    return abortEverything('the scratch library was never created, so neither direction had a library to measure');
  }

  // ---- fixture-containers-ready ----------------------------------------
  const ensureList = async (path, title, description) => {
    const found = await spGet(path);
    if (found.ok && found.body) return { id: found.body.Id, note: `'${title}' already present` };
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title, BaseTemplate: 100, Description: description,
    }, digest);
    return {
      id: made.ok && made.body ? made.body.Id : null,
      note: made.ok ? `created '${title}'` : `'${title}' FAILED HTTP ${made.status}: ${clip(made.text, 160)}`,
    };
  };

  const notes = [];
  const target = await ensureList(tgtPath, TGT,
    'dbml-sharepoint cross-lookup probe lookup target. Safe to delete.');
  notes.push(target.note);
  const source = await ensureList(srcPath, SRC,
    'dbml-sharepoint cross-lookup probe source list. Safe to delete.');
  notes.push(source.note);
  const libRead = await spGet(libPath);
  const libId = libRead.ok && libRead.body ? libRead.body.Id : null;
  notes.push(libId ? `library id read` : `library id could NOT be read (HTTP ${libRead.status})`);

  // Rows in the target, so a lookup into it has something to point at.
  const targetRowIds = [];
  if (target.id) {
    const existingRows = await spGet(`${tgtPath}/items?$select=Id,Title&$top=50`);
    const rows = (existingRows.ok && existingRows.body && existingRows.body.value) || [];
    for (const row of rows) {
      if (TGT_ROWS.includes(row.Title)) targetRowIds.push(row.Id);
    }
    for (const title of TGT_ROWS) {
      if (targetRowIds.length >= TGT_ROWS.length) break;
      digest = await getDigest();
      const made = await spPost(`${tgtPath}/items`, { Title: title }, digest);
      if (made.ok && made.body) targetRowIds.push(made.body.Id);
    }
    notes.push(`${targetRowIds.length}/${TGT_ROWS.length} target row(s)`);
  }

  // One row in the source list, to write the list-to-library lookups on.
  let sourceRowId = null;
  if (source.id) {
    const existingRows = await spGet(
      `${srcPath}/items?$select=Id,Title&$filter=Title eq '${odataName(SRC_ROW)}'`);
    const rows = (existingRows.ok && existingRows.body && existingRows.body.value) || [];
    if (rows.length) {
      sourceRowId = rows[0].Id;
    } else {
      digest = await getDigest();
      const made = await spPost(`${srcPath}/items`, { Title: SRC_ROW }, digest);
      if (made.ok && made.body) sourceRowId = made.body.Id;
    }
    notes.push(sourceRowId === null ? 'source row FAILED' : `source row id ${sourceRowId}`);
  }

  // A file and a folder in the library. The file is the row a lookup into the
  // library is expected to reach; the folder is the row that separates "ranges
  // over items" from "ranges over files".
  digest = await getDigest();
  const upload = await rawPost(
    `${libPath}/RootFolder/Files/add(url='${FILE}',overwrite=true)`,
    'dbml-sharepoint cross-lookup probe payload',
    digest,
    { 'Content-Type': 'text/plain' });
  notes.push(upload.ok ? `uploaded '${FILE}'`
    : `upload of '${FILE}' FAILED HTTP ${upload.status}: ${clip(upload.text, 160)}`);

  const libFolder = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const libFolderUrl = libFolder.ok && libFolder.body ? libFolder.body.ServerRelativeUrl : null;
  let folderMade = false;
  if (libFolderUrl) {
    digest = await getDigest();
    const made = await spPost(
      `web/GetFolderByServerRelativeUrl('${libFolderUrl}')/folders/add(url='${FOLDER}')`,
      {}, digest);
    folderMade = made.ok;
    notes.push(made.ok ? `created folder '${FOLDER}'`
      : `folder '${FOLDER}' FAILED HTTP ${made.status}: ${clip(made.text, 160)}`);
  } else {
    notes.push(`the library RootFolder url could not be read (HTTP ${libFolder.status})`);
  }

  // The two library rows, by their own item ids. FSObjType tells a folder row
  // from a file row, and it is read rather than assumed because which row the
  // folder lands on is exactly what the folder question is about.
  const libRows = await spGet(
    `${libPath}/items?$select=Id,FileLeafRef,FSObjType&$top=50`);
  const libRowList = (libRows.ok && libRows.body && libRows.body.value) || [];
  const fileRow = libRowList.find((row) => row.FileLeafRef === FILE) || null;
  const folderRow = libRowList.find((row) => row.FileLeafRef === FOLDER) || null;
  const fileItemId = fileRow ? fileRow.Id : null;
  const folderItemId = folderRow ? folderRow.Id : null;
  notes.push(`file item id ${show(fileItemId)} FSObjType ${show(fileRow ? fileRow.FSObjType : null)}`);
  notes.push(`folder item id ${show(folderItemId)} FSObjType ${show(folderRow ? folderRow.FSObjType : null)}`);

  const fixtureReady = target.id !== null && source.id !== null && libId !== null
    && targetRowIds.length === TGT_ROWS.length && sourceRowId !== null
    && upload.ok && folderMade && fileItemId !== null && folderItemId !== null;
  record('library.lookup.fixture-containers-ready', 'The three containers, the target rows, the file and the folder all exist',
         fixtureReady ? 'PASS' : 'FAIL', notes.join('; '));

  if (target.id === null || source.id === null || libId === null) {
    return abortEverything(
      'a container this probe points at or writes on was never created, so no lookup could '
      + `be created in either direction: ${notes.join('; ')}`);
  }

  // ---- POSITIVE CONTROL: does this Lookup shape work here at all? --------
  // Both ends generic lists, which is the shape projected-lookup-probe.js
  // already measured. A failure says the METHOD did not work on this site,
  // which is a different statement from "a library will not take part".
  const control = await makeLookup(srcPath, CONTROL_LOOKUP, target.id, 'Title');
  record('library.lookup.control-list-to-list-lookup-created', 'POSITIVE CONTROL: a Lookup created by createfieldasxml between two generic lists is created and reads back bound',
         control.bound ? 'PASS' : 'CONTROL FAILED, METHOD VOID',
         `${CONTROL_LOOKUP} on '${SRC}' -> '${TGT}'.Title: ${control.description}`
         + (control.bound ? ''
           : '. Nothing below can be read as a statement about document libraries, because '
             + 'the same call did not work between two generic lists.'));

  // ---- NEGATIVE CONTROL: does this call ever say no here? ----------------
  // The SAME createfieldasxml POST, on the same list, carrying a schema
  // SharePoint is measured to refuse: a Calculated column computing from a
  // Lookup. calculated-operand-probe.js sent that shape against a live tenant
  // on 2026-08-10 and got HTTP 500, "One or more column references are not
  // allowed, because the columns are defined as a data type that is not
  // supported in formulas", which analysis/checks/_structure.py cites as the
  // reason CALCULATED_FORMULA_UNSUPPORTED_OPERAND is an error. The operand is
  // the positive control's own lookup, so this runs after it.
  const calcOverLookupXml =
    `<Field Type="Calculated" DisplayName="${CONTROL_CALC}" Name="${CONTROL_CALC}" `
    + 'ResultType="Text">'
    + `<Formula>=[${CONTROL_LOOKUP}]</Formula>`
    + `<FieldRefs><FieldRef Name="${CONTROL_LOOKUP}"/></FieldRefs></Field>`;
  // A leftover column from an earlier run would be refused as a duplicate
  // name, and this row would then report REFUSED on a refusal that says
  // nothing about the operand. Checked rather than assumed away by CLEANUP.
  const calcAlready = control.bound && !readFailed(await readField(srcPath, CONTROL_CALC));
  const notSent = !control.bound
    ? `${CONTROL_LOOKUP} was never created, so the operand this control computes from does not `
      + 'exist and a refusal here would be a different refusal. The positive control row above '
      + 'already voids everything this one guards.'
    : calcAlready
      ? `${CONTROL_CALC} already exists on '${SRC}', so this create would be refused as a `
        + 'duplicate name whatever SharePoint thinks of the operand. Re-run with CLEANUP = true.'
      : null;
  const negative = notSent === null ? await addField(srcPath, calcOverLookupXml) : null;
  const refusalDetectable = negative !== null && !negative.ok && isRefusal(negative.status);
  record('library.lookup.control-unsupported-operand-refused', 'NEGATIVE CONTROL: the same createfieldasxml call refuses a Calculated column whose formula names a Lookup operand',
         negative === null ? 'NOT ESTABLISHED'
           : refusalDetectable ? 'REFUSED' : 'CONTROL FAILED, METHOD VOID',
         negative === null
           ? notSent
           : refusalDetectable
             ? `${CONTROL_CALC}, a Calculated column computing from the Lookup ${CONTROL_LOOKUP}, `
               + `was REFUSED: HTTP ${negative.status}: ${clip(negative.text, 240)}. An accepted `
               + 'create and a refused one are distinguishable on this site, so an ACCEPTED row '
               + 'below is an observation about SharePoint rather than about this probe.'
             : negative.ok
               ? `${CONTROL_CALC}, a Calculated column computing from the Lookup `
                 + `${CONTROL_LOOKUP}, was ACCEPTED with HTTP ${negative.status}. SharePoint `
                 + 'refused that operand on a live tenant on 2026-08-10, so an acceptance here '
                 + 'says this probe cannot tell a created column from a refused one and no '
                 + 'ACCEPTED row below would be a finding.'
               : `the request failed with HTTP ${negative.status}, which is about who is asking `
                 + 'or about the moment, not the server refusing the content: '
                 + `${clip(negative.text, 200)}`);

  // Both controls must hold. The positive one says the call reaches a field
  // collection at all; the negative one says an accepted create and a refused
  // create are distinguishable. Without either, an outcome below is a reading
  // of the probe rather than of SharePoint, and this repository fails closed.
  const controlsHold = control.bound && refusalDetectable;
  const voidReason = control.bound
    ? 'the negative control did not refuse, so a create that was accepted here could not be '
      + 'told from one that was not'
    : 'the positive control did not create a bound lookup between two generic lists, so the '
      + 'method was never shown to work on this site';

  // ---- LIBRARY -> LIST ---------------------------------------------------
  let libToListMade = false;
  if (!controlsHold) {
    record('library.lookup.library-to-list-created', 'LIBRARY -> LIST: is a Lookup on a document library, targeting a list Title, created and bound?',
           'VOID', voidReason, 'void');
  } else {
    const libToList = await makeLookup(libPath, LIB_TO_LIST, target.id, 'Title');
    libToListMade = libToList.bound;
    record('library.lookup.library-to-list-created', 'LIBRARY -> LIST: is a Lookup on a document library, targeting a list Title, created and bound?',
           libToList.bound ? 'BOUND'
             : libToList.made.ok ? 'ACCEPTED BUT NOT BOUND'
               : isRefusal(libToList.made.status) ? 'REFUSED' : 'NOT ESTABLISHED',
           `${LIB_TO_LIST} on the LIBRARY -> '${TGT}'.Title: ${libToList.description}`
           + (libToList.made.ok && !libToList.bound
             ? '. The create was accepted and the column does not read back bound to the target, '
               + 'which is the failure class this repository exists to close'
             : ''));
  }

  if (!libToListMade) {
    record('library.lookup.library-to-list-item-write', 'Does setting that lookup on a FILE row of the library take and read back?',
           'NOT ESTABLISHED',
           `${LIB_TO_LIST} is not a lookup bound to '${TGT}', so there was nothing to write`);
    record('library.lookup.library-to-list-indexed', 'Does Indexed=true stick on a lookup column held by a document library?',
           'NOT ESTABLISHED',
           `${LIB_TO_LIST} is not a lookup bound to '${TGT}', so no index write was attempted`);
  } else if (fileItemId === null || targetRowIds.length === 0) {
    record('library.lookup.library-to-list-item-write', 'Does setting that lookup on a FILE row of the library take and read back?',
           'NOT ESTABLISHED',
           `no file row (${show(fileItemId)}) or no target row (${targetRowIds.length}) to join, `
           + 'so the write was not attempted');
    const indexed = await tryIndex(libPath, LIB_TO_LIST);
    record('library.lookup.library-to-list-indexed', 'Does Indexed=true stick on a lookup column held by a document library?',
           indexed.outcome, indexed.evidence);
  } else {
    const wrote = await mergeItem(libPath, fileItemId, { [`${LIB_TO_LIST}Id`]: targetRowIds[0] });
    const readBack = await spGet(
      `${libPath}/items(${fileItemId})?$select=${LIB_TO_LIST}Id,${LIB_TO_LIST}/Title&$expand=${LIB_TO_LIST}`);
    const readId = !readFailed(readBack) ? readBack.body[`${LIB_TO_LIST}Id`] : undefined;
    const projected = !readFailed(readBack) && readBack.body[LIB_TO_LIST]
      ? readBack.body[LIB_TO_LIST].Title : undefined;
    const held = readId === targetRowIds[0];
    record('library.lookup.library-to-list-item-write', 'Does setting that lookup on a FILE row of the library take and read back?',
           wrote.ok ? (held ? 'HELD' : 'ACCEPTED BUT NOT HELD')
             : isRefusal(wrote.status) ? 'REFUSED' : 'NOT ESTABLISHED',
           `MERGE ${LIB_TO_LIST}Id=${targetRowIds[0]} on the library's items(${fileItemId}), `
           + `which is the FILE '${FILE}': HTTP ${wrote.status}`
           + (wrote.ok ? '' : `: ${clip(wrote.text, 200)}`)
           + `; readback ${readFailed(readBack) ? `failed HTTP ${readBack.status}` : `id ${show(readId)}`}`
           + `, $expand projected ${show(projected)}. `
           + 'The row written to was reached through the library\'s items(id), not created by an '
           + 'item POST, which document-library-probe.js recorded as refused.');
    const indexed = await tryIndex(libPath, LIB_TO_LIST);
    record('library.lookup.library-to-list-indexed', 'Does Indexed=true stick on a lookup column held by a document library?',
           indexed.outcome, indexed.evidence);
  }

  // ---- LIST -> LIBRARY ---------------------------------------------------
  let listToLibMade = false;
  if (!controlsHold) {
    record('library.lookup.list-to-library-title-created', 'LIST -> LIBRARY: is a Lookup on a generic list, targeting a library Title, created and bound?',
           'VOID', voidReason, 'void');
    record('library.lookup.list-to-library-name-created', 'Is the same Lookup created against FileLeafRef, the Name column a library has and a list does not?',
           'VOID', voidReason, 'void');
  } else {
    const byTitle = await makeLookup(srcPath, LIST_TO_LIB_TITLE, libId, 'Title');
    listToLibMade = byTitle.bound;
    record('library.lookup.list-to-library-title-created', 'LIST -> LIBRARY: is a Lookup on a generic list, targeting a library Title, created and bound?',
           byTitle.bound ? 'BOUND'
             : byTitle.made.ok ? 'ACCEPTED BUT NOT BOUND'
               : isRefusal(byTitle.made.status) ? 'REFUSED' : 'NOT ESTABLISHED',
           `${LIST_TO_LIB_TITLE} on '${SRC}' -> the LIBRARY.Title: ${byTitle.description}`);

    const byName = await makeLookup(srcPath, LIST_TO_LIB_NAME, libId, 'FileLeafRef');
    record('library.lookup.list-to-library-name-created', 'Is the same Lookup created against FileLeafRef, the Name column a library has and a list does not?',
           byName.bound ? 'BOUND'
             : byName.made.ok ? 'ACCEPTED BUT NOT BOUND'
               : isRefusal(byName.made.status) ? 'REFUSED' : 'NOT ESTABLISHED',
           `${LIST_TO_LIB_NAME} on '${SRC}' -> the LIBRARY.FileLeafRef: ${byName.description}. `
           + 'FileLeafRef is the Name column, which a generic list does not carry, so a refusal '
           + 'here and a BOUND above would say a library is joinable only through Title.');
  }

  if (!listToLibMade) {
    const reason = `${LIST_TO_LIB_TITLE} is not a lookup bound to the library, so there was `
      + 'nothing to write to';
    record('library.lookup.list-to-library-item-write', 'Does setting that lookup to a FILE row take, read back, and project a label through $expand?',
           'NOT ESTABLISHED', reason);
    record('library.lookup.list-to-library-folder-row-selectable', 'Does the same lookup accept a FOLDER row of the library, which is an item and not a file?',
           'NOT ESTABLISHED', reason);
    record('library.lookup.list-to-library-indexed', 'Does Indexed=true stick on a lookup column whose target is a document library?',
           'NOT ESTABLISHED', reason);
  } else {
    const key = `${LIST_TO_LIB_TITLE}Id`;
    const readRow = async () => spGet(
      `${srcPath}/items(${sourceRowId})?$select=${key},${LIST_TO_LIB_TITLE}/Title,`
      + `${LIST_TO_LIB_TITLE}/FileLeafRef&$expand=${LIST_TO_LIB_TITLE}`);

    if (sourceRowId === null || fileItemId === null) {
      record('library.lookup.list-to-library-item-write', 'Does setting that lookup to a FILE row take, read back, and project a label through $expand?',
             'NOT ESTABLISHED',
             `no source row (${show(sourceRowId)}) or no file row (${show(fileItemId)}), so the `
             + 'write was not attempted');
    } else {
      const wrote = await mergeItem(srcPath, sourceRowId, { [key]: fileItemId });
      const readBack = await readRow();
      const readId = !readFailed(readBack) ? readBack.body[key] : undefined;
      const expanded = !readFailed(readBack) ? readBack.body[LIST_TO_LIB_TITLE] : null;
      const held = readId === fileItemId;
      record('library.lookup.list-to-library-item-write', 'Does setting that lookup to a FILE row take, read back, and project a label through $expand?',
             wrote.ok ? (held ? 'HELD' : 'ACCEPTED BUT NOT HELD')
               : isRefusal(wrote.status) ? 'REFUSED' : 'NOT ESTABLISHED',
             `MERGE ${key}=${fileItemId}, the file '${FILE}', on '${SRC}' items(${sourceRowId}): `
             + `HTTP ${wrote.status}`
             + (wrote.ok ? '' : `: ${clip(wrote.text, 200)}`)
             + `; readback ${readFailed(readBack) ? `failed HTTP ${readBack.status}` : `id ${show(readId)}`}`
             + `, $expand projected Title=${show(expanded ? expanded.Title : undefined)} `
             + `FileLeafRef=${show(expanded ? expanded.FileLeafRef : undefined)}. `
             + 'A file whose Title is empty and whose FileLeafRef is not is the shape that would '
             + 'make a Title-bound lookup into a library render blank rows.');
    }

    // The machine half of "files or items". A folder is an item of the library
    // and is not a file, so whether the same lookup accepts its id separates
    // the two readings by behaviour. Attempted only after the file write, so a
    // refusal here cannot be confused with the column not working at all.
    if (sourceRowId === null || folderItemId === null) {
      record('library.lookup.list-to-library-folder-row-selectable', 'Does the same lookup accept a FOLDER row of the library, which is an item and not a file?',
             'NOT ESTABLISHED',
             `no source row (${show(sourceRowId)}) or no folder row (${show(folderItemId)}), so `
             + 'the write was not attempted');
    } else {
      const wroteFolder = await mergeItem(srcPath, sourceRowId, { [key]: folderItemId });
      const readBack = await readRow();
      const readId = !readFailed(readBack) ? readBack.body[key] : undefined;
      const expanded = !readFailed(readBack) ? readBack.body[LIST_TO_LIB_TITLE] : null;
      const held = readId === folderItemId;
      record('library.lookup.list-to-library-folder-row-selectable', 'Does the same lookup accept a FOLDER row of the library, which is an item and not a file?',
             wroteFolder.ok ? (held ? 'FOLDER IS SETTABLE' : 'ACCEPTED BUT NOT HELD')
               : isRefusal(wroteFolder.status) ? 'REFUSED' : 'NOT ESTABLISHED',
             `MERGE ${key}=${folderItemId}, the FOLDER '${FOLDER}' (FSObjType `
             + `${show(folderRow ? folderRow.FSObjType : null)}), on '${SRC}' items(${sourceRowId}): `
             + `HTTP ${wroteFolder.status}`
             + (wroteFolder.ok ? '' : `: ${clip(wroteFolder.text, 200)}`)
             + `; readback ${readFailed(readBack) ? `failed HTTP ${readBack.status}` : `id ${show(readId)}`}`
             + `, $expand projected FileLeafRef=${show(expanded ? expanded.FileLeafRef : undefined)}. `
             + 'FOLDER IS SETTABLE says the lookup ranges over ITEMS; REFUSED says it ranges over '
             + 'FILES. Either way it is a write, not the picker, and the picker row records what '
             + 'still has to be seen.');
    }

    const indexed = await tryIndex(srcPath, LIST_TO_LIB_TITLE);
    record('library.lookup.list-to-library-indexed', 'Does Indexed=true stick on a lookup column whose target is a document library?',
           indexed.outcome, indexed.evidence);
  }

  // ---- The picker, which nobody can read over REST -----------------------
  record('library.lookup.picker-enumerates-files', 'Does the picker for a list-to-library lookup offer files, or every item including folders?',
         listToLibMade ? 'MANUAL' : 'NOT ESTABLISHED',
         listToLibMade
           ? `OPEN ${WEB}/Lists/${encodeURIComponent(SRC)}/NewForm.aspx and open the `
             + `${LIST_TO_LIB_TITLE} dropdown. The library holds exactly two rows, the file `
             + `'${FILE}' and the folder '${FOLDER}'. Record how many entries the dropdown `
             + 'offers and what each one is labelled. Two entries means the picker enumerates '
             + 'ITEMS; one means it enumerates FILES; a blank label means the target rows have '
             + 'no Title, which is the library divergence this pair of rows exists to catch. '
             + 'The candidate set is rendered by the browser and is not exposed over REST, so '
             + 'this cannot be answered by a machine run.'
           : `${LIST_TO_LIB_TITLE} was not created, so there is no picker to open`);

  // ---- The three join rows ----------------------------------------------
  if (!controlsHold) {
    record('scale.join.control-list-lookup-ceiling', 'CONTROL: how many single-value list-to-list lookups can one view project on this fixture?',
           'VOID', voidReason, 'void');
    record('scale.join.library-lookup-ceiling', 'How many lookups can one view project on a DOCUMENT LIBRARY?',
           'VOID', voidReason, 'void');
    record('scale.join.list-to-library-costs-a-join', 'How many joins does a lookup whose target is a library cost against the view ceiling?',
           'VOID', voidReason, 'void');
  } else {
    // The baseline first: how many list-to-list lookups can this view project?
    // That is the shape analysis/joins.py counts as one join each, so it is
    // both the control and the unit the cost row is read against.
    const listWalk = await walkCeiling(srcPath, 'XJoinL', target.id, null);
    const listCeilingFound = listWalk.reached > 0 && listWalk.reached < listWalk.columns.length;
    record('scale.join.control-list-lookup-ceiling', 'CONTROL: how many single-value list-to-list lookups can one view project on this fixture?',
           listWalk.columns.length === 0 ? 'NOT ESTABLISHED'
             : listCeilingFound ? `CEILING ${listWalk.reached}`
               : `NO CEILING FOUND (${listWalk.reached} projected of ${listWalk.columns.length})`,
           `${listWalk.columns.length} empty single-value lookup(s) created on '${SRC}'`
           + `${listWalk.createErrors.length ? `, then ${listWalk.createErrors.join('; ')}` : ''}. `
           + `${listWalk.reached} render(s); ${listWalk.reached + 1} `
           + `${listWalk.failure || 'was not reachable'}. `
           + 'This list holds one item, nowhere near the 5,000-item threshold. NO CEILING FOUND '
           + 'means the limit needs size and this fixture cannot reach it, which leaves the cost '
           + 'row below with nothing to sit at. threshold-index-probe.js found a ceiling of 12 '
           + 'on a 6,000-row fixture on 2026-07-31.');

    // The same walk on a document library. A number, not a boolean, and it is
    // recorded whatever the list answered: a library that finds a ceiling
    // where a list does not is itself the divergence this probe is looking for.
    const libWalk = await walkCeiling(libPath, 'XJoinB', target.id, null);
    const libCeilingFound = libWalk.reached > 0 && libWalk.reached < libWalk.columns.length;
    record('scale.join.library-lookup-ceiling', 'How many lookups can one view project on a DOCUMENT LIBRARY?',
           libWalk.columns.length === 0 ? 'NOT ESTABLISHED'
             : libCeilingFound ? `CEILING ${libWalk.reached}`
               : `NO CEILING FOUND (${libWalk.reached} projected of ${libWalk.columns.length})`,
           `${libWalk.columns.length} empty lookup(s) created on the LIBRARY`
           + `${libWalk.createErrors.length ? `, then ${libWalk.createErrors.join('; ')}` : ''}. `
           + `${libWalk.reached} render(s); ${libWalk.reached + 1} `
           + `${libWalk.failure || 'was not reachable'}. `
           + `The generic list answered ${listWalk.reached} on the same fixture through the same `
           + `walk (${listCeilingFound ? 'a ceiling' : 'no ceiling found'}). The same number says `
           + 'a library joins like a list; a different one says analysis/joins.py is counting '
           + 'the wrong ceiling for one of the two containers. NOT ESTABLISHED here means no '
           + 'lookup could be created on the library at all, which the library-to-list row '
           + 'above reports on directly.');

    // The cost of a lookup INTO a library, by subtraction. The walk columns
    // are list-to-list lookups, which analysis/joins.py counts as one each;
    // the column under test is the list-to-library lookup. If it costs c joins
    // then reached + c = ceiling, so the cost is the difference. The library
    // side is deliberately not measured this way; see the header finding.
    const costWalk = listCeilingFound && listToLibMade
      ? await walkCeiling(srcPath, 'XJoinL', target.id, LIST_TO_LIB_TITLE)
      : null;
    const joinCost = costWalk && costWalk.reached >= 0
      ? listWalk.reached - costWalk.reached : null;
    record('scale.join.list-to-library-costs-a-join', 'How many joins does a lookup whose target is a library cost against the view ceiling?',
           joinCost === null ? 'NOT ESTABLISHED'
             : joinCost < 0 ? `SHORT: the two walks disagree (${joinCost})` : `COSTS ${joinCost}`,
           joinCost === null
             ? (!listToLibMade
               ? 'no lookup into the library was created, so there was nothing to add to the view.'
               : !listCeilingFound
                 ? 'no ceiling was found on the generic list, so there is nothing to sit at and '
                   + 'the difference between the two walks would be meaningless.'
                 : `'${LIST_TO_LIB_TITLE}' could not be projected even on its own: `
                   + `${costWalk.failure}. A column that will not render alone says nothing `
                   + 'about what it costs.')
             : `${listWalk.reached} list-to-list lookup(s) render alone; ${costWalk.reached} `
               + `render alongside '${LIST_TO_LIB_TITLE}', and ${costWalk.reached + 1} `
               + `${costWalk.failure || 'was not reachable, which is why this number may be a floor'}. `
               + `The difference is the cost, so a lookup into a library counts as ${joinCost} `
               + 'join(s). analysis/joins.py counts every lookup as ONE whichever container it '
               + 'points at. COSTS 1 confirms that. Any other number contradicts it, and '
               + 'JOIN_LIMIT, JOIN_WARN_AT and the docstring all have to change together. A '
               + 'negative difference is not an answer: it means the two walks measured '
               + 'different things, and the run has to be repeated on a fresh fixture.',
           joinCost === null ? 'void' : undefined);
  }

  report();
  log('INFO', `Delete '${SRC}' FIRST, then '${LIB}', then '${TGT}'. A container a lookup points `
    + 'into cannot be removed while the lookup exists.');
})();
