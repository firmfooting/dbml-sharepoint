/**
 * dbml-sharepoint PROBE: DO A LIBRARY'S SYSTEM COLUMNS CARRY A NATIVE INDEX?
 *
 * ONE QUESTION, asked eight ways:
 *   Does SharePoint serve a SELECTIVE filter on a document library's system
 *   columns past the 5,000-item list view threshold, with no author-added
 *   index on them? A served filter means an index answered it; a refusal means
 *   the query would have had to scan the whole library.
 *
 * REVISION: 1de597c5
 *
 * THE COLUMNS: Title, Name (FileLeafRef), Created, Modified, Author, Editor,
 * plus ID as the positive control and two probe-owned columns as the negative
 * controls.
 *
 * WHY THE `Indexed` FLAG CANNOT ANSWER THIS. `SP.Field.Indexed` reports
 * author-added indexes only. `native-index-probe.js` ran on 2026-07-30 and its
 * control failed exactly there: `Indexed` read false for ID on 7 of 7 generic
 * lists, and ID is the one column SharePoint is widely held to index for
 * itself. A fresh library reads false on Title and Name too. So the flag is
 * silent on the platform's own indexes and the only instrument left is
 * behavioural: send the query and see whether the server answers it.
 *
 * WHY IT MATTERS. Microsoft's "Manage large lists and libraries" implies Name,
 * and possibly Title, are indexed by default on a library. Nothing in this
 * repository has measured that, and `library-index-probe.js` recorded that a
 * library REFUSES `Indexed: true` on FileLeafRef, so an author cannot add the
 * index that a filtered view on Name would need. If the platform does not
 * supply one either, a view this tool emits over a library's Name column
 * breaks at size and neither the build nor the deploy can see it.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. The question is how a document library
 * DIVERGES from a generic list, so the measurements file under `library.index`
 * rather than under `scale`. The library-creation row keeps the id six other
 * library probes share.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)?
 *   library.index.fixture-file-count
 *        Does the fixture library hold at least 5,001 files, so that every
 *        query below is asked past the threshold?
 *   library.index.fixture-target-seeded
 *        Does the one target file carry the Title marker, the text marker and
 *        the person marker, and does its item read back?
 *   library.index.control-small-library-shapes
 *        CONTROL: does every filter below PARSE, and does each one find its
 *        target, on a small library nothing throttles? A filter SharePoint
 *        rejects for its syntax comes back as a refusal and is otherwise
 *        indistinguishable from a threshold refusal, which would publish a
 *        typo as a platform finding.
 *   library.index.control-threshold-id-served
 *        POSITIVE CONTROL: is a selective filter on ID served past the
 *        threshold? ID is the column whose native index is least in doubt, so
 *        this establishes that a native index CAN be observed this way. If it
 *        is refused, every row below is void rather than open.
 *   library.index.control-unindexed-refused
 *        NEGATIVE CONTROL: is a selective filter on a probe-owned, unindexed
 *        TEXT column refused? This establishes that the library really is past
 *        the threshold and that throttling really is enforced on it. Without
 *        it, "served" says nothing.
 *   library.index.control-unindexed-person-refused
 *        NEGATIVE CONTROL for the two person columns, sent in BOTH shapes: a
 *        selective match on a probe-owned, unindexed PERSON column, and the
 *        zero-match shape the Author and Editor rows are obliged to use. See
 *        THE PERSON PROBLEM below.
 *   library.index.threshold-filter-title
 *   library.index.threshold-filter-name
 *   library.index.threshold-filter-created
 *   library.index.threshold-filter-modified
 *   library.index.threshold-filter-author
 *   library.index.threshold-filter-editor
 *        The six measurements. Each sends one selective filter on one system
 *        column, past the threshold, with no index on it that this probe or
 *        any operator could have added.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the fixture library exists and holds at
 *   least 5,001 files; the target file carries all three markers and its item
 *   reads back; every filter parses and finds its target on the small control
 *   library; ID is served past the threshold; the two probe-owned columns are
 *   refused past the threshold and read `Indexed` false before anything is
 *   measured.
 *   Observes (recorded, never asserted): for each of the six system columns,
 *   whether the filter was served, how many rows came back, the HTTP status
 *   and the error text. NOTHING here asserts that any of them is served. A run
 *   where every one is refused is a successful run with an important answer,
 *   and a probe that asserted otherwise would kill the experiment the moment
 *   it started working.
 *
 * WHY SELECTIVE FILTERS, AND WHY OData. Two lessons from
 * `threshold-index-probe.js`, both from its live runs:
 *
 *   Past the threshold, an OData `$filter` on a column no index can serve came
 *   back HTTP 500 SPQueryThrottledException, a loud refusal, while the same
 *   predicate in CAML came back HTTP 200 with a silently partial answer. OData
 *   is therefore the surface that REPORTS the threshold, and it is what every
 *   measurement here uses.
 *
 *   A result of exactly 5,000 rows is a page ceiling and a threshold breach at
 *   once, and no count can separate them. Its GRDONLY row was read as the
 *   threshold being enforced and did not establish it. So every filter here
 *   matches ONE known row, `$top` is set well below any page ceiling, and a
 *   result that fills the page is recorded as unreadable rather than as an
 *   answer.
 *
 * THE PERSON PROBLEM, and why the Author and Editor rows are weaker than the
 * other four. Every file in this fixture was uploaded by one identity, so
 * `Author/Id eq <that identity>` matches all 5,001 rows and is not selective.
 * There is no second identity to hand. The only selective shape left is a
 * ZERO-match filter, an id no row carries, which is unambiguous against a page
 * ceiling (nought rows is not five thousand) and still needs a full scan when
 * no index exists. What it cannot rule out on its own is that a person filter
 * naming an id that resolves to nothing is answerable without touching the
 * library at all. That is what the matched person control is for: the same
 * zero-match shape on a column known to be unindexed. If the control is served
 * in that shape, the Author and Editor rows are void and say so.
 *
 * BOTH PERSON FILTER SHAPES ARE MEASURED rather than chosen. SharePoint
 * exposes a person column as a scalar `<Name>Id` and as a navigation
 * `<Name>/Id`, and which of the two a `$filter` accepts is not something this
 * project has established. The small control library is asked in both shapes
 * and the one that parses and finds its target is the one used past the
 * threshold. Picking one from memory would report a rejected spelling as a
 * refused column.
 *
 * THE FIXTURE IS FILES, NOT ITEMS. `document-library-probe.js` recorded that a
 * fileless POST to a library's /items is refused ("To add an item to a
 * document library, use SPFileCollection.Add()"), so the 6,000 rows
 * `threshold-index-probe.js` builds with item POSTs are not a library fixture
 * at any price. This probe uploads 5,001 small text files through
 * `Files/add(url=,overwrite=true)`, the shape `file-operations-probe.js`
 * established.
 *
 * THE BUILD IS RESUMABLE, and it has to be. Five thousand serial uploads from
 * a browser console take many minutes and a tenant will throttle somewhere in
 * the middle. So: BUILD_FIXTURE gates the upload apart from the measurement, a
 * run uploads at most UPLOAD_CAP files and then reports how far it got, the
 * resume point is read from the newest file already in the library rather than
 * assumed, and `overwrite=true` makes a repeated name harmless. Re-paste until
 * the file count row reads PASS, then measure.
 *
 * A BOUNDED RETRY ON THROTTLING, deliberately, and only during the build.
 * `throttle-batch-probe.js` refuses to retry because the throttle point is its
 * finding. Here throttling is weather on the way to a fixture, so an upload
 * that comes back 429 or 503 waits and is sent again a bounded number of
 * times. No measurement query is ever retried: a 429 on one of those is
 * recorded as NOT ESTABLISHED, never as a refusal.
 *
 * `Files/add` DOES NOT SET Title, so Title is empty on 5,000 of the 5,001
 * files and carries the marker on one. That is what makes the Title filter
 * selective, and it is why the seed is a separate item MERGE rather than part
 * of the upload.
 *
 * THE HARNESS CLEANUP FLAG DOES NOTHING HERE, on purpose. resetList() is never
 * called. You do not want a 5,001-file fixture emptied because a flag was left
 * on, and the fixture is the expensive part of this experiment. Teardown is
 * CLEANUP_AT_END, at the bottom, and it is a separate deliberate act.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL below is one Microsoft Learn
 * documents, not one assembled from memory, because a wrong spelling returns
 * 404, isRefusal() counts 404 as a refusal, and the probe would then print a
 * claim about SharePoint that was really a typo:
 *
 *   List and library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   File upload via `GetFolderByServerRelativeUrl(...)/Files/add(url=,overwrite=)`
 *   and the item behind a file via `GetFileByServerRelativeUrl(...)/ListItemAllFields`:
 *     "Working with folders and files with REST"
 *   The threshold and the index model it rests on:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 *
 * SCOPE OF CLAIMS: this measures one tenant, one library, one caller context
 * and one moment. The threshold is documented as an effective figure rather
 * than a constant, so a fixture at 5,001 files may sit close enough to it that
 * nothing is throttled. The negative controls are what detect that, and when
 * they fail the run has answered nothing and says so. Raise TARGET_FILES and
 * re-paste; the build is additive.
 *
 * HOW TO RUN: the run plan, in order
 *   1. Open a site you own and are willing to put a 5,001-file library on.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED, ALLOW_WRITES and BUILD_FIXTURE true. Paste. Expect
 *      several minutes and a run that stops at the upload cap.
 *   4. Re-paste until `library.index.fixture-file-count` reads PASS. Each
 *      paste resumes where the last one stopped.
 *   5. Copy the whole RESULTS block back verbatim.
 *
 * STATUS: RUN 1 (2026-09-08), 13/13 settled. Only Id is natively indexed;
 * Title, Name, Created, Modified, Author and Editor all refuse past the
 * threshold (SPQueryThrottledException).
 *
 * WHEN FINISHED: set CLEANUP_AT_END with both write gates and re-paste.
 * Expect more than one pass, because a library past 5,000 items will not empty
 * in a single page.
 */
// finding: library-index-threshold-odata-refuses-where-caml-truncates - the
// choice of surface here is not a preference. threshold-index-probe.js
// measured, on a list past 5,000 rows, that an OData $filter no index can
// serve returns HTTP 500 SPQueryThrottledException while the same predicate in
// CAML returns HTTP 200 with a silently partial answer. Only one of those two
// reports the threshold as an error, so only one can answer a question of the
// form "would SharePoint have to scan this".
// finding: library-index-threshold-page-ceiling-is-not-a-breach - a result of
// exactly 5,000 rows is a page ceiling and a threshold breach at once.
// threshold-index-probe.js read its GRDONLY row that way and had to withdraw
// it. Every filter here matches one known row and $top is 100, so a full page
// is recorded as unreadable rather than as an answer.
// finding: library-index-threshold-name-column-cannot-be-indexed-by-hand -
// library-index-probe.js recorded that Indexed=true is REFUSED on a document
// library's Name column (FileLeafRef), with both of its controls holding. That
// is what makes the Name row here decisive rather than merely interesting: if
// a selective filter on Name is served past the threshold, the index serving
// it cannot be one any author added, and if it is refused, no author can fix
// it either.
// finding: library-index-threshold-native-index-is-id-only - on a document
// library past 5,001 items, a selective $filter on Id is served (HTTP 200)
// while the same filter on Title, Name (FileLeafRef), Created, Modified,
// Author and Editor is each refused with SPQueryThrottledException. Only Id
// carries a native index; every other system column — including Title and
// Name — must be explicitly indexed before it can be queried past the
// threshold (2026-09-08 run, 13/13 settled, both controls held).
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

  log('INFO', 'probe revision 1de597c5. Quote this when reporting results.');

  // The expensive half. Off, so a paste that only wants to measure an
  // already-built library never starts five thousand uploads.
  const BUILD_FIXTURE = false;
  // Teardown, and the only thing in this probe that deletes anything. The
  // harness CLEANUP flag is deliberately not wired to the fixture; see the
  // header.
  const CLEANUP_AT_END = false;

  // One past the documented 5,000-item threshold. The figure is documented as
  // an EFFECTIVE threshold rather than a constant, so this is the smallest
  // fixture that can possibly be past it rather than one that certainly is.
  // The negative controls decide which, and a run where they do not refuse is
  // a run that has answered nothing.
  const TARGET_FILES = 5001;
  // At most this many uploads per paste, so a run is bounded and an operator
  // gets a progress report instead of a hung tab.
  const UPLOAD_CAP = 2000;
  // A form digest lives about thirty minutes, so it is refreshed per block of
  // uploads rather than per upload.
  const DIGEST_EVERY = 200;
  const PROGRESS_EVERY = 250;
  // A throttled upload waits and is sent again, bounded. No MEASUREMENT is
  // ever retried; see the header.
  const RETRY_MS = 2000;
  const MAX_RETRIES = 3;

  // Well below any page ceiling, so a filter that fills the page is visibly
  // unreadable rather than quietly rounded.
  const PAGE = 100;

  const LIB = 'dbmlsp Probe LibIdxThreshold';
  const SMALL = 'dbmlsp Probe LibIdxThreshold Small';
  // Enough files for a filter to have something to miss, and few enough that
  // nothing about this library is near a threshold.
  const SMALL_FILES = 6;

  const UNINDEXED_TEXT = 'TidxUnindexedText';
  const UNINDEXED_PERSON = 'TidxUnindexedPerson';
  const TITLE_MARKER = 'dbmlsp tidx title marker';
  const TEXT_MARKER = 'dbmlsp tidx text marker';
  // A principal id no row can carry. SharePoint's site user info list numbers
  // from 1, so nought is the zero-match literal for both person shapes.
  const ABSENT_PRINCIPAL = 0;

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const lit = (value) => String(value).replace(/'/g, "''");
  const fileName = (n) => `dbmlsp-tidx-${String(n).padStart(5, '0')}.txt`;
  const TARGET_FILE = fileName(1);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const smallPath = `web/lists/getbytitle('${odataName(SMALL)}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB} and upload`);
    log('INFO', `${TARGET_FILES} small text files into it, at most ${UPLOAD_CAP} per paste.`);
    log('INFO', `Would create a second, SMALL library '${SMALL}' of ${SMALL_FILES} files as the`);
    log('INFO', 'filter-shape control, add two probe-owned columns to each, and write Title,');
    log('INFO', 'a text marker and a person marker onto ONE file in each library.');
    log('INFO', 'It would then send one selective OData filter per column, reading at most');
    log('INFO', `${PAGE} rows per query. Every query is a GET; nothing else is written.`);
    log('INFO', BUILD_FIXTURE
      ? 'BUILD_FIXTURE is ON: the upload would run.'
      : 'BUILD_FIXTURE is off: no file would be uploaded, and the measurements would');
    if (!BUILD_FIXTURE) {
      log('INFO', 'run only if the library already holds enough files.');
    }
    log('INFO', 'CLEANUP does NOTHING in this probe. Teardown is CLEANUP_AT_END.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }
  if (CLEANUP) {
    log('INFO', 'CLEANUP is on and is IGNORED here: it would empty the fixture this probe');
    log('INFO', 'spends several minutes building. Teardown is CLEANUP_AT_END, at the bottom.');
  }

  // The six measurements. The table is the only place these ids are written,
  // so the rows registered up front, the rows recorded and probe-catalog.json
  // cannot drift apart.
  //
  // `control` names WHICH negative control a row reads against: the text one
  // for a selective match, the person one for the zero-match shape the two
  // person columns are obliged to use.
  const CANDIDATES = [
    {
      id: 'library.index.threshold-filter-title',
      question: 'Is a selective filter on Title served past the threshold with no index on it',
      column: 'Title',
      control: 'text',
      filter: () => `Title eq '${lit(TITLE_MARKER)}'`,
      expected: 1,
    },
    {
      id: 'library.index.threshold-filter-name',
      question: 'Is a selective filter on Name (FileLeafRef) served past the threshold with no index on it',
      column: 'FileLeafRef',
      control: 'text',
      filter: () => `FileLeafRef eq '${lit(TARGET_FILE)}'`,
      expected: 1,
    },
    {
      id: 'library.index.threshold-filter-created',
      question: 'Is a selective filter on Created served past the threshold with no index on it',
      column: 'Created',
      control: 'text',
      filter: (t) => `Created eq datetime'${lit(t.Created)}'`,
      // Files uploaded within one second share a Created value, so this is
      // selective without being unique. Anything short of the page is
      // unambiguous, which is all the question needs.
      expected: null,
    },
    {
      id: 'library.index.threshold-filter-modified',
      question: 'Is a selective filter on Modified served past the threshold with no index on it',
      column: 'Modified',
      control: 'text',
      filter: (t) => `Modified eq datetime'${lit(t.Modified)}'`,
      expected: null,
    },
    {
      id: 'library.index.threshold-filter-author',
      question: 'Is a zero-match filter on Author served past the threshold with no index on it',
      column: 'Author',
      control: 'person',
      filter: (t) => personFilter('Author', ABSENT_PRINCIPAL, t.personShape),
      expected: 0,
    },
    {
      id: 'library.index.threshold-filter-editor',
      question: 'Is a zero-match filter on Editor served past the threshold with no index on it',
      column: 'Editor',
      control: 'person',
      filter: (t) => personFilter('Editor', ABSENT_PRINCIPAL, t.personShape),
      expected: 0,
    },
  ];

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.index.fixture-file-count', `The fixture library holds at least ${TARGET_FILES} files`);
  expect('library.index.fixture-target-seeded', 'The one target file carries the Title, text and person markers');
  expect('library.index.control-small-library-shapes', 'CONTROL: every filter parses and finds its target on a small library nothing throttles');
  expect('library.index.control-threshold-id-served', 'POSITIVE CONTROL: a selective filter on ID is served past the threshold');
  expect('library.index.control-unindexed-refused', 'NEGATIVE CONTROL: a selective filter on an unindexed probe-owned Text column is refused past the threshold');
  expect('library.index.control-unindexed-person-refused', 'NEGATIVE CONTROL: an unindexed probe-owned Person column is refused past the threshold, in both filter shapes');
  for (const row of CANDIDATES) expect(row.id, row.question);

  // The two spellings SharePoint may accept for a person predicate. Which one
  // a $filter takes is measured on the small library, never assumed.
  function personFilter(column, id, shape) {
    return shape === 'navigation' ? `${column}/Id eq ${id}` : `${column}Id eq ${id}`;
  }
  const PERSON_SHAPES = ['scalar', 'navigation'];

  // ---- Query classification -------------------------------------------
  // Classify from the ERROR BODY, so a row is self-describing in a single
  // transcript. A malformed $filter and a threshold refusal both come back as
  // a status isRefusal() reads as REFUSED, and a filter that was broken all
  // along would then read as a platform answer.
  const classify = (r) => {
    const body = r.body ? JSON.stringify(r.body) : (r.text || '');
    // TRANSIENT FIRST, before the body is inspected. A 429 whose body happens
    // to mention the threshold would otherwise turn a throttle, which is about
    // the moment, into a verdict about the platform.
    if (r.status === 429 || r.status === 408 || r.status === 503) {
      return 'NOT ESTABLISHED (throttled)';
    }
    if (/exceeds the list view threshold|SPQueryThrottledException/i.test(body)) {
      return 'REFUSED (threshold)';
    }
    if (isRefusal(r.status)) return 'REFUSED (request rejected; read the body)';
    return 'NOT ESTABLISHED';
  };

  // One measurement query. Returns everything a caller needs to judge it, and
  // judges nothing itself.
  const askFilter = async (path, filter) => {
    const r = await spGet(
      `${path}/items?$select=Id&$top=${PAGE}&$filter=${encodeURIComponent(filter)}`);
    const rows = (r.ok && r.body && Array.isArray(r.body.value)) ? r.body.value.length : -1;
    const ids = (r.ok && r.body && Array.isArray(r.body.value))
      ? r.body.value.map((row) => row.Id) : [];
    const body = r.body ? JSON.stringify(r.body).slice(0, 260)
      : (r.text ? String(r.text).slice(0, 260) : '(no body)');
    return { ok: r.ok, status: r.status, rows, ids, body, filter };
  };

  // The one place a served answer is turned into an outcome, so the page
  // ceiling can never be read as a row count anywhere.
  const judge = (result, expected, targetId) => {
    if (!result.ok) return classify(result);
    if (result.rows === PAGE) {
      return `NOT ESTABLISHED (${PAGE} rows, the whole page, so this is a page `
        + 'ceiling and not a count)';
    }
    if (expected === 0) {
      return result.rows === 0
        ? 'SERVED (0 rows, as the zero-match shape expects)'
        : `NOT ESTABLISHED (a zero-match filter returned ${result.rows} row(s))`;
    }
    if (targetId !== null && !result.ids.includes(targetId)) {
      return `NOT ESTABLISHED (${result.rows} row(s) served, and the target file `
        + 'was not among them, so the filter did not select what it was built to select)';
    }
    return `SERVED (${result.rows} row(s), the target among them)`;
  };

  // ---- Library and column fixtures --------------------------------------
  const ensureLibrary = async (title, note) => {
    const found = await spGet(`web/lists/getbytitle('${odataName(title)}')`);
    if (found.ok) return { ok: true, made: false, status: found.status, text: '' };
    const digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title,
      BaseTemplate: 101,
      Description: note,
    }, digest);
    return { ok: made.ok, made: true, status: made.status, text: made.text };
  };

  const ensureField = async (path, name, schemaXml) => {
    const found = await spGet(
      `${path}/fields/getbyinternalnameortitle('${odataName(name)}')`);
    if (found.ok) return { ok: true, note: `${name} already present` };
    const digest = await getDigest();
    const made = await spPost(`${path}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
    return {
      ok: made.ok,
      note: made.ok ? `${name} created`
        : `${name} FAILED HTTP ${made.status}: ${made.text.slice(0, 160)}`,
    };
  };

  const ensureProbeColumns = async (path) => {
    const built = [];
    built.push(await ensureField(path, UNINDEXED_TEXT,
      `<Field Type="Text" DisplayName="${UNINDEXED_TEXT}" Name="${UNINDEXED_TEXT}" MaxLength="255"/>`));
    built.push(await ensureField(path, UNINDEXED_PERSON,
      `<Field Type="User" DisplayName="${UNINDEXED_PERSON}" Name="${UNINDEXED_PERSON}"`
      + ' UserSelectionMode="PeopleOnly"/>'));
    return {
      ok: built.every((entry) => entry.ok),
      note: built.map((entry) => entry.note).join('; '),
    };
  };

  // Whether a probe-owned column is carrying an index at the moment of the
  // run, rather than whether it was created without one.
  // threshold-index-probe.js measured SharePoint indexing a column on its own
  // between two runs, which expires a negative control silently.
  const indexFlags = async (path, name) => {
    // No $select, for the reason native-index-probe.js records: one
    // unrecognised name errors the whole request, and the column would read as
    // unreadable rather than as missing one property.
    const field = await spGet(
      `${path}/fields/getbyinternalnameortitle('${odataName(name)}')`);
    if (readFailed(field)) return { read: false, indexed: null, auto: null };
    return {
      read: true,
      indexed: typeof field.body.Indexed === 'boolean' ? field.body.Indexed : null,
      auto: typeof field.body.AutoIndexed === 'boolean' ? field.body.AutoIndexed : null,
    };
  };

  const folderOf = async (path) => {
    // Read, never assembled. SharePoint derives a library's folder name from
    // its title at creation and the web may sit under /sites/<name>, so a path
    // built here would be a guess wearing an address's clothes.
    const root = await spGet(`${path}/RootFolder?$select=ServerRelativeUrl`);
    return (root.ok && root.body) ? root.body.ServerRelativeUrl : null;
  };

  // A raw request body, not JSON. Files/add takes the file's bytes as the
  // body, and spPost JSON-encodes whatever it is given, which would upload the
  // quotes along with the text.
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
      return { ok: res.ok, status: res.status, text };
    } catch (err) {
      return { ok: false, status: 0, text: String(err) };
    }
  };

  const CONTENT = 'dbml-sharepoint library index threshold probe. Safe to delete.';

  const uploadOne = async (folderUrl, name, digest) => {
    let attempt = 0;
    let last = null;
    while (attempt <= MAX_RETRIES) {
      last = await rawPost(
        `web/GetFolderByServerRelativeUrl('${folderUrl}')`
        + `/Files/add(url='${lit(name)}',overwrite=true)`, CONTENT, digest);
      if (last.ok) return last;
      // Throttling on the way to a fixture is weather, not a finding. Anything
      // else is returned unretried, because retrying a refusal would only
      // repeat it.
      if (last.status !== 429 && last.status !== 503) return last;
      attempt += 1;
      await sleep(RETRY_MS * attempt);
    }
    return last;
  };

  // Where to resume. Read from the NEWEST file the library already holds
  // rather than derived from the item count, because a count is right only
  // while nothing has ever failed. Ordering by Id is the one ordering a
  // library past the threshold can be relied on to serve.
  const resumeFrom = async (path, fallback) => {
    const newest = await spGet(
      `${path}/items?$select=Id,FileLeafRef&$orderby=Id desc&$top=1`);
    const rows = (newest.ok && newest.body && newest.body.value) || [];
    const name = rows.length ? String(rows[0].FileLeafRef || '') : '';
    const digits = name.match(/dbmlsp-tidx-(\d+)\.txt$/);
    return digits ? Number(digits[1]) : fallback;
  };

  const uploadUpTo = async (path, folderUrl, wanted, cap) => {
    const before = await spGet(`${path}?$select=ItemCount`);
    const held = (before.ok && before.body) ? before.body.ItemCount : 0;
    const from = (await resumeFrom(path, held)) + 1;
    if (from > wanted) return { uploaded: 0, from, held, stoppedAt: null, reason: 'already built' };
    let digest = await getDigest();
    let uploaded = 0;
    for (let n = from; n <= wanted && uploaded < cap; n += 1) {
      if (uploaded > 0 && uploaded % DIGEST_EVERY === 0) digest = await getDigest();
      const sent = await uploadOne(folderUrl, fileName(n), digest);
      if (!sent.ok) {
        return {
          uploaded, from, held, stoppedAt: n,
          reason: `HTTP ${sent.status}: ${sent.text.slice(0, 200)}`,
        };
      }
      uploaded += 1;
      if (uploaded % PROGRESS_EVERY === 0) {
        log('INFO', `uploaded ${uploaded} file(s) this run; at ${fileName(n)}.`);
      }
    }
    return { uploaded, from, held, stoppedAt: null, reason: uploaded >= cap ? 'hit the per-run cap' : 'reached the target' };
  };

  // The target file's item, addressed through the FILE rather than through a
  // query. A $filter on FileLeafRef is one of the things under test here, so
  // finding the target with it would make the fixture depend on the answer.
  const readTarget = async (folderUrl) => {
    const item = await spGet(
      `web/GetFileByServerRelativeUrl('${folderUrl}/${lit(TARGET_FILE)}')/ListItemAllFields`
      + '?$select=Id,Title,Created,Modified,AuthorId,EditorId,'
      + `${UNINDEXED_TEXT},${UNINDEXED_PERSON}Id`);
    if (readFailed(item)) return { ok: false, status: item.status, item: null };
    return { ok: true, status: item.status, item: item.body };
  };

  const seedTarget = async (path, itemId, authorId) => {
    const digest = await getDigest();
    const payload = { Title: TITLE_MARKER };
    payload[UNINDEXED_TEXT] = TEXT_MARKER;
    payload[`${UNINDEXED_PERSON}Id`] = authorId;
    return spPost(`${path}/items(${itemId})`, payload, digest,
                  { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  };

  // Build one library to the point where every filter has something to select:
  // the library, the two probe-owned columns, the files, and the seeded target.
  const prepare = async (title, path, wanted, cap, note) => {
    const made = await ensureLibrary(title, note);
    if (!made.ok) {
      return { ok: false, why: `library '${title}' does not exist and could not be created `
        + `(HTTP ${made.status}: ${made.text.slice(0, 200)})` };
    }
    const columns = await ensureProbeColumns(path);
    if (!columns.ok) {
      return { ok: false, why: `the probe-owned columns are not on '${title}': ${columns.note}` };
    }
    const folderUrl = await folderOf(path);
    if (!folderUrl) {
      return { ok: false, why: `the RootFolder of '${title}' did not read back, so there is `
        + 'no address to upload to' };
    }
    const build = BUILD_FIXTURE || wanted <= SMALL_FILES
      ? await uploadUpTo(path, folderUrl, wanted, cap)
      : { uploaded: 0, from: 0, held: 0, stoppedAt: null, reason: 'BUILD_FIXTURE is off' };
    // ItemCount is timer-job-cached and lags a fresh upload burst by minutes,
    // so read the live count from the newest FileLeafRef number instead — the
    // same signal resumeFrom already trusts, and the uploads are contiguous.
    const count = await resumeFrom(path, 0);
    return {
      ok: true, folderUrl, count, build,
      created: made.made, columns: columns.note,
    };
  };

  const abortRemaining = (reason, state) => {
    record('library.index.control-small-library-shapes', 'CONTROL: every filter parses and finds its target on a small library nothing throttles',
           'ABORTED', reason, state);
    record('library.index.control-threshold-id-served', 'POSITIVE CONTROL: a selective filter on ID is served past the threshold',
           'ABORTED', reason, state);
    record('library.index.control-unindexed-refused', 'NEGATIVE CONTROL: a selective filter on an unindexed probe-owned Text column is refused past the threshold',
           'ABORTED', reason, state);
    record('library.index.control-unindexed-person-refused', 'NEGATIVE CONTROL: an unindexed probe-owned Person column is refused past the threshold, in both filter shapes',
           'ABORTED', reason, state);
    for (const row of CANDIDATES) record(row.id, row.question, 'ABORTED', reason, state);
    return report();
  };

  // ---- fixture-library-created ------------------------------------------
  const big = await prepare(
    LIB, libPath, TARGET_FILES, UPLOAD_CAP,
    'dbml-sharepoint library index threshold probe fixture. Safe to delete.');
  record('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)',
         big.ok ? (big.created ? 'PASS' : 'ALREADY PRESENT') : 'FAIL',
         big.ok
           ? `'${LIB}' is present with the two probe-owned columns (${big.columns}). `
             + `It holds ${big.count} item(s).`
           : big.why);
  if (!big.ok) {
    record('library.index.fixture-file-count', `The fixture library holds at least ${TARGET_FILES} files`,
           'ABORTED', big.why);
    record('library.index.fixture-target-seeded', 'The one target file carries the Title, text and person markers',
           'ABORTED', big.why);
    return abortRemaining(big.why);
  }

  // ---- fixture-file-count ------------------------------------------------
  const buildNote =
    `${big.build.uploaded} file(s) uploaded this run (${big.build.reason}); the library `
    + `now holds ${big.count} item(s) of the ${TARGET_FILES} wanted`
    + (big.build.stoppedAt === null ? '' : `; the pass stopped at ${fileName(big.build.stoppedAt)}`);
  const pastThreshold = big.count >= TARGET_FILES;
  record('library.index.fixture-file-count', `The fixture library holds at least ${TARGET_FILES} files`,
         pastThreshold ? 'PASS' : 'SHORT',
         pastThreshold
           ? buildNote
           : `${buildNote}. Re-paste with BUILD_FIXTURE = true until this reads PASS. `
             + 'Nothing below this line was measured, because a query on a library that is '
             + 'not past the threshold answers a different question.');
  if (!pastThreshold) {
    const why = `the fixture library holds ${big.count} of ${TARGET_FILES} files, so no `
      + 'query here was asked past the threshold';
    record('library.index.fixture-target-seeded', 'The one target file carries the Title, text and person markers',
           'ABORTED', why);
    return abortRemaining(why);
  }

  // ---- fixture-target-seeded ---------------------------------------------
  const seedLibrary = async (path, folderUrl) => {
    const first = await readTarget(folderUrl);
    if (!first.ok) {
      return { ok: false, why: `the item behind '${TARGET_FILE}' did not read back `
        + `(HTTP ${first.status})` };
    }
    const authorId = first.item.AuthorId;
    if (typeof authorId !== 'number') {
      return { ok: false, why: `the item behind '${TARGET_FILE}' reports no AuthorId, so the `
        + 'person marker has no principal to name' };
    }
    const wrote = await seedTarget(path, first.item.Id, authorId);
    const after = await readTarget(folderUrl);
    if (!after.ok) {
      return { ok: false, why: `the seed MERGE returned HTTP ${wrote.status} and the item did `
        + `not read back afterwards (HTTP ${after.status})` };
    }
    const item = after.item;
    const held = item.Title === TITLE_MARKER
      && item[UNINDEXED_TEXT] === TEXT_MARKER
      && item[`${UNINDEXED_PERSON}Id`] === authorId;
    return {
      ok: held, item, authorId, status: wrote.status,
      why: held ? '' : `the seed MERGE returned HTTP ${wrote.status} and the item read back `
        + `Title=${JSON.stringify(item.Title)}, ${UNINDEXED_TEXT}=`
        + `${JSON.stringify(item[UNINDEXED_TEXT])}, ${UNINDEXED_PERSON}Id=`
        + `${JSON.stringify(item[`${UNINDEXED_PERSON}Id`])}${wrote.ok ? '' : `: ${wrote.text.slice(0, 200)}`}`,
    };
  };

  const bigSeed = await seedLibrary(libPath, big.folderUrl);
  record('library.index.fixture-target-seeded', 'The one target file carries the Title, text and person markers',
         bigSeed.ok ? 'PASS' : 'FAIL',
         bigSeed.ok
           ? `'${TARGET_FILE}' is item ${bigSeed.item.Id}, Created ${bigSeed.item.Created}, `
             + `Modified ${bigSeed.item.Modified}, and holds all three markers. Every filter `
             + 'below selects this one file.'
           : bigSeed.why);
  if (!bigSeed.ok) {
    return abortRemaining(
      `the target file was not seeded, so no filter had a row to select: ${bigSeed.why}`);
  }

  // ---- control-small-library-shapes --------------------------------------
  // Every filter is sent here FIRST, on a library nothing throttles. A filter
  // SharePoint rejects for its syntax comes back as a refusal and would
  // otherwise be published as a threshold refusal, which is a typo wearing a
  // finding's clothes.
  const small = await prepare(
    SMALL, smallPath, SMALL_FILES, SMALL_FILES,
    'dbml-sharepoint library index threshold probe shape control. Safe to delete.');
  let personShape = null;
  let shapesHeld = false;
  const shapeNotes = [];
  const brokenShapes = new Set();

  if (!small.ok || small.count < SMALL_FILES) {
    record('library.index.control-small-library-shapes', 'CONTROL: every filter parses and finds its target on a small library nothing throttles',
           'NOT ESTABLISHED',
           small.ok
             ? `'${SMALL}' holds ${small.count} of ${SMALL_FILES} files, so the shapes were `
               + 'not exercised'
             : small.why);
  } else {
    const smallSeed = await seedLibrary(smallPath, small.folderUrl);
    if (!smallSeed.ok) {
      record('library.index.control-small-library-shapes', 'CONTROL: every filter parses and finds its target on a small library nothing throttles',
             'NOT ESTABLISHED',
             `the small library's target file was not seeded, so no shape could be `
             + `exercised against it: ${smallSeed.why}`);
    } else {
      // Which person spelling does a $filter take? Asked in the POSITIVE form,
      // naming the identity that really is the author, so a shape that parses
      // but selects nothing is not mistaken for one that works.
      for (const shape of PERSON_SHAPES) {
        const tried = await askFilter(
          smallPath, personFilter('Author', smallSeed.authorId, shape));
        shapeNotes.push(
          `person shape '${shape}' on Author: HTTP ${tried.status}, ${tried.rows} row(s)`);
        if (tried.ok && tried.ids.includes(smallSeed.item.Id)) {
          personShape = shape;
          break;
        }
      }
      const smallTarget = {
        Created: smallSeed.item.Created,
        Modified: smallSeed.item.Modified,
        personShape: personShape || PERSON_SHAPES[0],
      };
      // ID and the two probe-owned columns are shape-checked as well, because
      // they carry the controls and a broken control is worse than a broken
      // measurement.
      const shapeChecks = [
        { name: 'Id', filter: `Id eq ${smallSeed.item.Id}`, expected: 1 },
        { name: UNINDEXED_TEXT, filter: `${UNINDEXED_TEXT} eq '${lit(TEXT_MARKER)}'`, expected: 1 },
        {
          name: `${UNINDEXED_PERSON} (selective)`,
          filter: personFilter(UNINDEXED_PERSON, smallSeed.authorId, smallTarget.personShape),
          expected: 1,
        },
        {
          name: `${UNINDEXED_PERSON} (zero-match)`,
          filter: personFilter(UNINDEXED_PERSON, ABSENT_PRINCIPAL, smallTarget.personShape),
          expected: 0,
        },
      ];
      for (const row of CANDIDATES) {
        shapeChecks.push({
          name: row.column, key: row.id,
          filter: row.filter(smallTarget), expected: row.expected,
        });
      }
      for (const check of shapeChecks) {
        const tried = await askFilter(smallPath, check.filter);
        const held = tried.ok
          && tried.rows < PAGE
          && (check.expected === 0
            ? tried.rows === 0
            : tried.ids.includes(smallSeed.item.Id));
        shapeNotes.push(
          `${check.name}: HTTP ${tried.status}, ${tried.rows} row(s), ${held ? 'shape holds' : 'SHAPE FAILED'}`
          + (held ? '' : ` (${tried.body})`));
        if (!held && check.key) brokenShapes.add(check.key);
        if (!held && !check.key) brokenShapes.add(check.name);
      }
      // The control holds when nothing the CONTROLS rest on is broken. A
      // single broken measurement shape does not void the others; it voids its
      // own row, below.
      const controlShapesBroken = ['Id', UNINDEXED_TEXT,
                                   `${UNINDEXED_PERSON} (selective)`,
                                   `${UNINDEXED_PERSON} (zero-match)`]
        .filter((name) => brokenShapes.has(name));
      shapesHeld = controlShapesBroken.length === 0 && personShape !== null;
      record('library.index.control-small-library-shapes', 'CONTROL: every filter parses and finds its target on a small library nothing throttles',
             shapesHeld ? 'PASS' : 'CONTROL FAILED, METHOD VOID',
             `on ${small.count} file(s): ${shapeNotes.join('; ')}`
             + (personShape === null
               ? '. No person filter spelling parsed and matched, so neither person row '
                 + 'below can be read.'
               : `. The person spelling in use is '${personShape}'.`)
             + (controlShapesBroken.length
               ? ` The shapes the CONTROLS rest on failed: ${controlShapesBroken.join(', ')}.`
               : ''));
    }
  }

  if (!shapesHeld) {
    const why = 'the filter shapes were not established on a library nothing throttles, so a '
      + 'refusal past the threshold could not be told from a filter SharePoint rejects '
      + 'whatever the size';
    record('library.index.control-threshold-id-served', 'POSITIVE CONTROL: a selective filter on ID is served past the threshold',
           'VOID', why, 'void');
    record('library.index.control-unindexed-refused', 'NEGATIVE CONTROL: a selective filter on an unindexed probe-owned Text column is refused past the threshold',
           'VOID', why, 'void');
    record('library.index.control-unindexed-person-refused', 'NEGATIVE CONTROL: an unindexed probe-owned Person column is refused past the threshold, in both filter shapes',
           'VOID', why, 'void');
    for (const row of CANDIDATES) record(row.id, row.question, 'VOID', why, 'void');
    report();
    return;
  }

  const target = {
    Created: bigSeed.item.Created,
    Modified: bigSeed.item.Modified,
    personShape,
  };
  const targetId = bigSeed.item.Id;

  // ---- control-threshold-id-served ---------------------------------------
  const idResult = await askFilter(libPath, `Id eq ${targetId}`);
  const idOutcome = judge(idResult, 1, targetId);
  const idServed = idOutcome.startsWith('SERVED');
  record('library.index.control-threshold-id-served', 'POSITIVE CONTROL: a selective filter on ID is served past the threshold',
         idOutcome,
         `$filter=${idResult.filter} on ${big.count} item(s), HTTP ${idResult.status}: ${idResult.body}`
         + (idServed
           ? '. A native index can therefore be observed by this method on this library.'
           : '. ID is the column whose native index is least in doubt, so a refusal here '
             + 'says the method cannot observe one, not that ID lacks an index.'));

  // ---- The two negative controls -----------------------------------------
  // Read the flags BEFORE measuring. A probe-owned column that has silently
  // gained an index is no longer a negative control, and
  // threshold-index-probe.js watched that happen between two runs.
  const textFlags = await indexFlags(libPath, UNINDEXED_TEXT);
  const personFlags = await indexFlags(libPath, UNINDEXED_PERSON);
  const flagNote = (name, flags) =>
    `${name} reads Indexed=${JSON.stringify(flags.indexed)}, `
    + `AutoIndexed=${JSON.stringify(flags.auto)}`;

  const textResult = await askFilter(
    libPath, `${UNINDEXED_TEXT} eq '${lit(TEXT_MARKER)}'`);
  const textOutcome = judge(textResult, 1, targetId);
  const textExpired = textFlags.indexed === true;
  const textRefused = textOutcome.startsWith('REFUSED (threshold)') && !textExpired;
  record('library.index.control-unindexed-refused', 'NEGATIVE CONTROL: a selective filter on an unindexed probe-owned Text column is refused past the threshold',
         textExpired ? 'CONTROL EXPIRED, METHOD VOID'
           : textRefused ? 'REFUSED (threshold)'
             : 'CONTROL FAILED, METHOD VOID',
         `$filter=${textResult.filter} on ${big.count} item(s), HTTP ${textResult.status}: `
         + `${textResult.body}. ${flagNote(UNINDEXED_TEXT, textFlags)}`
         + (textExpired
           ? '. The column carries an index, so it is no longer an unindexed control. '
             + 'Delete both libraries and re-run.'
           : textRefused
             ? '. The library is therefore past the threshold and throttling is enforced on it.'
             : '. Without a refusal here, nothing served below is evidence of an index: the '
               + 'library may simply not be far enough past the threshold. Raise '
               + 'TARGET_FILES and re-paste.'));

  const personSelective = await askFilter(
    libPath, personFilter(UNINDEXED_PERSON, bigSeed.authorId, personShape));
  const personZero = await askFilter(
    libPath, personFilter(UNINDEXED_PERSON, ABSENT_PRINCIPAL, personShape));
  const personSelectiveOutcome = judge(personSelective, 1, targetId);
  const personZeroOutcome = judge(personZero, 0, targetId);
  const personExpired = personFlags.indexed === true;
  const personSelectiveRefused = personSelectiveOutcome.startsWith('REFUSED (threshold)');
  const personZeroRefused = personZeroOutcome.startsWith('REFUSED (threshold)');
  const personRefused = personSelectiveRefused && personZeroRefused && !personExpired;
  record('library.index.control-unindexed-person-refused', 'NEGATIVE CONTROL: an unindexed probe-owned Person column is refused past the threshold, in both filter shapes',
         personExpired ? 'CONTROL EXPIRED, METHOD VOID'
           : personRefused ? 'REFUSED (threshold, both shapes)'
             : personSelectiveRefused && !personZeroRefused
               ? 'ZERO-MATCH SHAPE SERVED ON AN UNINDEXED COLUMN'
               : 'CONTROL FAILED, METHOD VOID',
         `selective: $filter=${personSelective.filter}, HTTP ${personSelective.status}, `
         + `${personSelectiveOutcome}; zero-match: $filter=${personZero.filter}, HTTP `
         + `${personZero.status}, ${personZeroOutcome}. ${flagNote(UNINDEXED_PERSON, personFlags)}`
         + (personExpired
           ? '. The column carries an index, so it is no longer an unindexed control.'
             + ' Delete both libraries and re-run.'
           : personRefused
             ? '. Both shapes need a scan on this library, so a served answer on Author or '
               + 'Editor is an index and not an artefact of the zero-match shape.'
             : personSelectiveRefused && !personZeroRefused
               ? '. A zero-match person filter is answered WITHOUT an index, so the Author and '
                 + 'Editor rows below cannot distinguish an index from that shortcut. They are '
                 + 'void, and this is the reason.'
               : '. Neither shape was refused, so nothing served on a person column below is '
                 + 'evidence of an index.'));

  // ---- The six measurements ----------------------------------------------
  const controlsFor = { text: textRefused, person: personRefused };
  for (const row of CANDIDATES) {
    if (!idServed) {
      record(row.id, row.question, 'VOID',
             'the positive control was not served, so this method was never shown to '
             + 'observe a native index on this library at all', 'void');
      continue;
    }
    if (!controlsFor[row.control]) {
      record(row.id, row.question, 'VOID',
             row.control === 'text'
               ? 'the unindexed Text control was not refused, so a served answer here is not '
                 + 'evidence of an index'
               : 'the unindexed Person control did not refuse both shapes, so a served answer '
                 + 'here is not evidence of an index',
             'void');
      continue;
    }
    if (brokenShapes.has(row.id)) {
      record(row.id, row.question, 'NOT ESTABLISHED',
             `the filter for ${row.column} did not select its target on the small library, so `
             + 'a refusal past the threshold would be this probe rejecting its own filter '
             + 'rather than SharePoint refusing to scan');
      continue;
    }
    const result = await askFilter(libPath, row.filter(target));
    const outcome = judge(result, row.expected, row.expected === 0 ? null : targetId);
    record(row.id, row.question, outcome,
           `$filter=${result.filter} on ${big.count} item(s), HTTP ${result.status}: `
           + `${result.body}`
           + (row.expected === 0
             ? '. This is the zero-match shape; read it beside the person control, which sends '
               + 'the same shape on a column known to carry no index.'
             : ''));
  }

  report();

  // ---- Cleanup ------------------------------------------------------------
  if (!CLEANUP_AT_END) {
    log('INFO', `Fixture libraries remain: '${LIB}' and '${SMALL}'.`);
    log('INFO', 'When finished, set CLEANUP_AT_END = true with both write gates and');
    log('INFO', 're-paste. Expect more than one pass past 5,000 files.');
    return;
  }

  // Past 5,000 items a library will not empty in one page, and a cleanup that
  // silently leaves files behind lets this run's files answer the next run's
  // questions. So: page until empty or until a page stops making progress,
  // then say exactly what is left rather than reporting success.
  const emptyLibrary = async (title, path) => {
    let removed = 0;
    let throttled = 0;
    for (let page = 0; page < 20; page += 1) {
      const found = await spGet(`${path}/items?$select=Id&$top=1000`);
      const rows = (found.ok && found.body && found.body.value) || [];
      if (!rows.length) break;
      // One digest per PAGE, not per item, for the reason
      // threshold-index-probe.js records: request count is the constraint at
      // this size.
      const digest = await getDigest();
      let removedThisPage = 0;
      for (const row of rows) {
        const gone = await spPost(`${path}/items(${row.Id})/recycle`, {}, digest);
        if (gone.ok) removedThisPage += 1;
        else if (gone.status === 429 || gone.status === 503) throttled += 1;
      }
      removed += removedThisPage;
      if (removedThisPage === 0) {
        log('FAIL',
            `CLEANUP '${title}': a page of ${rows.length} row(s) would not recycle `
            + `(${throttled} were throttled). Stopping rather than looping over it.`);
        break;
      }
    }
    const left = await spGet(`${path}?$select=ItemCount`);
    const remaining = (left.ok && left.body) ? left.body.ItemCount : -1;
    log(remaining === 0 ? 'OK' : 'FAIL',
        `CLEANUP '${title}': recycled ${removed} file(s), ${remaining} REMAINING`
        + (remaining === 0 ? '.' : '. Re-run with CLEANUP_AT_END until this reads 0.'));
    return remaining === 0;
  };

  for (const [title, path] of [[SMALL, smallPath], [LIB, libPath]]) {
    await emptyLibrary(title, path);
    const digest = await getDigest();
    const recycled = await spPost(`${path}/recycle`, {}, digest);
    log(recycled.ok ? 'OK' : 'FAIL',
        recycled.ok
          ? `Recycled '${title}'. Restorable from the site recycle bin.`
          : `Could not recycle '${title}': HTTP ${recycled.status} ${recycled.text.slice(0, 300)}`);
  }
})();
