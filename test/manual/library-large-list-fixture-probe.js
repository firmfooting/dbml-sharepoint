/**
 * dbml-sharepoint PROBE: BUILD THE PERSISTENT LARGE-LIBRARY FIXTURE.
 *
 * REVISION: 9804d6f0
 *
 * THIS PROBE ANSWERS NO QUESTION ABOUT SHAREPOINT. It builds a document
 * library that later probes measure, and every row it records is a
 * `fixture-` row: a statement that the thing later probes depend on is
 * actually there and actually holds the values they will read. A run that
 * reports every row PASS has produced a fixture, not a finding.
 *
 * WHAT IT BUILDS, and this is a CONTRACT. The library name, the target list
 * name, the column names, the file names and the value formulas below are read
 * by later probes in the beyond-5,000 enumeration work. Changing any of them
 * invalidates the fixture rather than adjusting it, so a change here is a
 * change to every probe that reads it.
 *
 *   Library:     'dbmlsp Probe LargeLib'
 *   Target list: 'dbmlsp Probe LargeLib Target', 10 rows titled
 *                'lvtarget-1' .. 'lvtarget-10'
 *   Files:       'dbmlsp-lv-00001.txt' .. 'dbmlsp-lv-05500.txt', a few bytes
 *                of text each, contiguous and zero-padded to five digits
 *   Columns, all set on every file, where i is the file's sequence number
 *   counting from 1:
 *
 *     LVText         Text                        `text-{i%100}`
 *     LVChoice       Choice Alpha..Delta         values[i%4]
 *     LVNumber       Number                      i%1000
 *     LVDate         DateTime                    2020-01-01Z plus (i%365) days
 *     LVMultiChoice  MultiChoice Alpha..Delta    [values[i%4], values[(i+1)%4]]
 *     LVCalc         Calculated, number          =[LVNumber]*2
 *     LVLookup       Lookup into the target      the (i%10 + 1)th target row
 *
 * WHY THOSE DISTRIBUTIONS. A filter on one LVChoice value selects about a
 * quarter of the library, roughly 1,375 files of 5,500. That is selective
 * enough to be a real query and small enough that a page ceiling is not
 * mistaken for it, while the library total stays over 5,000 so every query a
 * later probe sends is sent past the list view threshold. The other columns
 * give a later probe a low-cardinality text column, a numeric range, a date
 * range spanning a year, a multi-value column and a lookup, each with a value
 * count it can predict without querying.
 *
 * THE LOOKUP VALUE IS RESOLVED, NEVER ASSUMED. `i%10 + 1` names the (i%10+1)th
 * TARGET ROW, not the list item id 10 of them happen to get on a list nobody
 * has ever written to. The ten row ids are read back at run time and the
 * mapping is printed in the fixture row, because a later probe reading this
 * library needs the ids and cannot derive them.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. `library.large-list` is a new scope and it is
 * the fixture's own: the questions later probes ask against this library are
 * about ENUMERATING a container past 5,000 rows, which is neither
 * `library.index` (whether a column carries an index) nor `scale.index` (what a
 * generic list does with the `Indexed` flag). The library-creation row keeps
 * the id the other library probes share.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)?
 *   library.large-list.fixture-target-list-seeded
 *        Does the target list exist and hold its ten rows, and what id does
 *        each one carry?
 *   library.large-list.fixture-columns-created
 *        Do the seven columns exist on the library and read back as the types
 *        they were asked for?
 *   library.large-list.fixture-file-count
 *        Does the library hold all TARGET_FILES files, counted from the newest
 *        file name rather than from ItemCount?
 *   library.large-list.fixture-values-written
 *        Do the sampled files read back holding the values the formulas above
 *        give them, and which multi-value item payload shape took?
 *   library.large-list.fixture-calculated-column-computes
 *        Does LVCalc, the one column nothing writes, read back as LVNumber
 *        doubled, and in what serialised form?
 *   library.large-list.fixture-distribution
 *        Does the value distribution meet what later probes depend on: over
 *        5,000 files in total, and each LVChoice value selecting a proper
 *        fraction of them?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED. Every row here is a depends-on,
 * because the whole probe is a fixture. What is nonetheless OBSERVED and never
 * asserted: which multi-value payload shape SharePoint accepts, what form a
 * calculated number is serialised in, which zone a date reads back rendered in,
 * and what ids the target rows take. Those are recorded in the evidence of the
 * rows above and no outcome turns on any of them being a particular value.
 *
 * VERIFICATION IS SAMPLED, and that is a deliberate narrowing rather than an
 * oversight. Reading every one of 5,500 files back would double an already long
 * build. So: every MERGE's status is checked and a non-2xx stops the run;
 * every VERIFY_EVERY-th file is read back during the build and a mismatch stops
 * the run; and after the build a fixed SAMPLE spanning every wrap boundary in
 * the formulas (the 4 of LVChoice, the 10 of LVLookup, the 100 of LVText, the
 * 365 of LVDate and the 1000 of LVNumber) is read back and compared. The
 * fixture row names the files it checked, so a reader can see the size of what
 * was verified rather than inferring it.
 *
 * THE BUILD IS RESUMABLE, and it has to be. Five thousand five hundred serial
 * uploads from a browser console take a long time and a tenant will throttle
 * somewhere in the middle. So: BUILD_FIXTURE gates the upload, a run uploads at
 * most UPLOAD_CAP files and then reports how far it got, and the resume point
 * is READ rather than assumed. A run that reaches TARGET_FILES reports the
 * build PASS; a run that stops short reports where it stopped and says to
 * re-paste.
 *
 * THE RESUME POINT IS THE NEWEST FILE NAME, NEVER ItemCount. `ItemCount` is
 * served from a timer-job cache and lags a fresh upload burst by minutes, so a
 * resume computed from it re-uploads work that is already done and, worse,
 * reports a short library as complete once the cache catches up.
 * `library-index-threshold-probe.js` records the same thing and reads the same
 * signal. The newest file's own values are then checked, because a file whose
 * upload took and whose metadata MERGE did not is the one gap a name-based
 * resume would step over; see the resume finding below.
 *
 * A BOUNDED RETRY ON THROTTLING, and only on the upload. Throttling on the way
 * to a fixture is weather rather than a finding, so an upload that comes back
 * 429 or 503 waits and is sent again a bounded number of times. Nothing else is
 * retried.
 *
 * THERE IS NO CLEANUP PATH IN THIS PROBE, on purpose. The fixture is the
 * product. `resetList` is never called and the harness CLEANUP flag is ignored
 * with a message. Removing this library is a separate deliberate act by an
 * operator who has decided the enumeration work is finished.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL below is one Microsoft Learn
 * documents rather than one assembled from memory, because a wrong spelling
 * returns 404, `isRefusal` counts 404 as a refusal, and the probe would then
 * print a claim about SharePoint that was really a typo:
 *
 *   List and library creation via POST to `web/lists`, and item updates via
 *   MERGE to `items(...)`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`, and the `List`,
 *   `ShowField`, `ResultType` and `Formula` parts of a field schema:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   File upload via `GetFolderByServerRelativeUrl(...)/Files/add(url=,overwrite=)`
 *   and the item behind a file via `GetFileByServerRelativeUrl(...)/ListItemAllFields`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   The site's zone and the `Bias`, `StandardBias` and `DaylightBias` a bare
 *   date read-back is resolved against, via `web/RegionalSettings/TimeZone`:
 *     the same endpoint datetime-sentinel-probe.js reads, which returned an
 *     Information block carrying all three on the 2026-09-03 live run.
 *   The list view threshold this fixture is built to sit past:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *
 * SCOPE OF CLAIMS: one tenant, one library, one caller context. The threshold
 * is documented as an effective figure rather than a constant, so a later probe
 * measuring against this fixture owns its own controls. This probe establishes
 * only that the fixture is present and correct.
 *
 * HOW TO RUN
 *   1. Open a site you are willing to leave a permanent 5,500-file library on.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED, ALLOW_WRITES and BUILD_FIXTURE true. Paste. Expect a long
 *      run that stops at the upload cap.
 *   4. Re-paste until `library.large-list.fixture-file-count` reads PASS. Each
 *      paste resumes where the last one stopped.
 *   5. Copy the whole RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing. Leave the fixture in place.
 */
// finding: large-list-fixture-resume-must-verify-the-newest-file - a resume
// point read from the newest file NAME steps over a file whose Files/add took
// and whose metadata MERGE did not, and that file then sits in the fixture with
// null columns for every later probe to filter on. The newest file's values are
// therefore read back before the resume point is fixed: complete means resume
// after it, incomplete means resume AT it and let overwrite=true redo the pair.
// finding: large-list-fixture-orderby-id-is-the-served-ordering - the resume
// read is `$orderby=Id desc&$top=1`, and past 5,000 items that is not a free
// choice. library-index-threshold-probe.js measured on 2026-09-08 that a
// document library past the threshold serves a selective filter on Id and
// refuses one on Title, Name, Created, Modified, Author and Editor, so Id is
// the one ordering this read can rely on. A read that FAILS is fatal here
// rather than falling back to zero: a fallback would restart the upload at file
// one and quietly rewrite a fixture that was already correct.
// finding: large-list-fixture-multi-value-write-shape-is-not-documented - Learn
// documents no item payload for a multi-value column, and the shape that took
// on a generic list is not evidence for a document library.
// library-grouping-probe.js established the method rather than the answer: try
// the candidate shapes in order, keep the first that writes AND READS BACK, and
// treat an HTTP 200 that reads back empty as a shape that did not take. The
// same three candidates are tried here, once per paste, and the winner is
// reused for the rest of that paste's files.
// finding: large-list-fixture-values-are-a-pure-function-of-the-file-number -
// every column's value is computed from the file's sequence number alone, with
// no run-time state. That is what lets a later probe predict a filter's result
// count without querying, lets this probe verify a sample rather than the whole
// library, and lets a resumed build produce exactly the file the interrupted one
// would have produced.
// finding: large-list-fixture-datetime-reads-back-in-a-zone-it-does-not-name -
// on the 2026-09-08 run a file written LVDate="2020-01-02T00:00:00.000Z" read
// back from ListItemAllFields as "2020-01-01T16:00:00": the same instant,
// rendered in the site's own zone (480 minutes behind UTC on that date) and
// carrying no Z and no offset. An offset-less stamp handed to Date.parse is read
// in the BROWSER's zone, which is a third zone belonging to nobody in the
// comparison, so the run called a correct write a lost one. The cost was not
// only a false FAIL: the resume point redid file one on every paste, and the
// multi-value shape experiment concluded that no shape worked. LVDate is
// therefore compared as an INSTANT, a stamp naming no zone is read through
// Date.UTC and resolved against the site's own candidate offsets, and the form
// it came back in is printed rather than assumed.
// finding: large-list-fixture-shape-experiment-is-decided-on-its-own-column -
// a candidate payload shape is a statement about LVMultiChoice, so it is kept or
// discarded on whether THAT column read back. The read-back used to be compared
// over every column, which is the depends-on / observes split AGENTS.md warns
// about: on 2026-09-08 a shape that wrote HTTP 204 and stored its values was
// discarded because LVDate compared wrong, and the run reported that no shape
// took. A mismatch in another column now stops the build under its own name.
// finding: large-list-fixture-upload-exceeds-the-run-timeout - the harness caps
// a run at 900s. The metadata-writing build (Files/add plus a seven-column MERGE
// per file, with a readback every 250 files) fits about 1250 files in that
// window; a UPLOAD_CAP of 2000 overshot it, so the first post-fix run was killed
// mid-upload and reported "crashed" with 0 settled even though 1250 files had
// been written. UPLOAD_CAP is 1000 so a paste finishes inside the run window.
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

  log('INFO', 'probe revision 9804d6f0. Quote this when reporting results.');

  // The expensive half. Off, so a paste that only wants to check an
  // already-built fixture never starts five thousand uploads.
  const BUILD_FIXTURE = false;

  // ---- The contract ----------------------------------------------------
  // Read by later probes. See the header: changing any of these invalidates
  // the fixture rather than adjusting it.
  const LIB = 'dbmlsp Probe LargeLib';
  const TGT = 'dbmlsp Probe LargeLib Target';
  const TARGET_FILES = 5500;
  const TGT_ROW_COUNT = 10;
  const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
  const TEXT = 'LVText';
  const CHOICE = 'LVChoice';
  const NUMBER = 'LVNumber';
  const DATE = 'LVDate';
  const MULTI = 'LVMultiChoice';
  const CALC = 'LVCalc';
  const LOOKUP = 'LVLookup';
  // Fixed, and part of the contract: a base date derived from the clock would
  // give two pastes of the same build different values for the same file.
  const BASE_DATE_MS = Date.UTC(2020, 0, 1);
  const DAY_MS = 86400000;

  // ---- Run shape -------------------------------------------------------
  // At most this many files per paste, so a run is bounded and an operator
  // gets a progress report instead of a hung tab. 1000, not 2000: the harness
  // caps a run at 900s, and the metadata-writing build (upload + a seven-column
  // MERGE per file) fits about 1250 files in that window; 2000 overshoots it.
  // See the run-timeout finding in the header.
  const UPLOAD_CAP = 1000;
  // A form digest lives about thirty minutes, so it is refreshed per block of
  // files rather than per file.
  const DIGEST_EVERY = 200;
  const PROGRESS_EVERY = 250;
  // A throttled upload waits and is sent again, bounded.
  const RETRY_MS = 2000;
  const MAX_RETRIES = 3;
  // How often the build stops to read a file back. See the sampling paragraph
  // in the header.
  const VERIFY_EVERY = 250;
  // The sample the fixture rows are decided on: every wrap boundary in the
  // formulas, and both sides of each. A file number over the current count is
  // dropped rather than read, so a short build still reports a real sample.
  const SAMPLE = [1, 2, 3, 4, 5, 10, 11, 100, 101, 365, 366, 1000, 1001,
                  4999, 5000, 5001, TARGET_FILES];

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const lit = (value) => String(value).replace(/'/g, "''");
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const fileName = (n) => `dbmlsp-lv-${String(n).padStart(5, '0')}.txt`;
  const FILE_NUMBER = /dbmlsp-lv-(\d+)\.txt$/;
  const targetTitle = (index) => `lvtarget-${index + 1}`;

  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const tgtPath = `web/lists/getbytitle('${odataName(TGT)}')`;

  // Every value the fixture holds for one file, from the file's number alone.
  // `lookupIndex` is an index INTO the target rows, not a list item id; the ids
  // are read back and applied where the payload is built.
  // `dateMs` is the instant, `date` the UTC stamp written. Both are carried
  // because the write needs a string and the comparison needs a number: the
  // read-back does not come back in the form it went in as, so re-parsing the
  // written string to compare against it would be parsing the wrong side.
  const wantedFor = (n) => {
    const dateMs = BASE_DATE_MS + (n % 365) * DAY_MS;
    return {
      text: `text-${n % 100}`,
      choice: CHOICES[n % 4],
      number: n % 1000,
      dateMs,
      date: new Date(dateMs).toISOString(),
      multi: [CHOICES[n % 4], CHOICES[(n + 1) % 4]],
      lookupIndex: n % 10,
      calc: (n % 1000) * 2,
    };
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${TGT}' with ${TGT_ROW_COUNT} rows on ${WEB} and a`);
    log('INFO', `DOCUMENT LIBRARY '${LIB}' holding ${TARGET_FILES} small text files,`);
    log('INFO', `at most ${UPLOAD_CAP} per paste, each carrying seven columns:`);
    log('INFO', `${TEXT}, ${CHOICE}, ${NUMBER}, ${DATE}, ${MULTI}, ${CALC}, ${LOOKUP}.`);
    log('INFO', BUILD_FIXTURE
      ? 'BUILD_FIXTURE is ON: the upload would run.'
      : 'BUILD_FIXTURE is off: no file would be uploaded, and the fixture would be');
    if (!BUILD_FIXTURE) {
      log('INFO', 'checked only as far as it has already been built.');
    }
    log('INFO', 'THIS FIXTURE IS PERMANENT. There is no cleanup path in this probe, and');
    log('INFO', 'the CLEANUP flag does nothing here. Later probes read what it leaves.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }
  if (CLEANUP) {
    log('INFO', 'CLEANUP is on and is IGNORED here. This probe builds a fixture that later');
    log('INFO', 'probes read, and emptying it is a separate deliberate act.');
  }

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.large-list.fixture-target-list-seeded', `The lookup target list holds its ${TGT_ROW_COUNT} rows, and their ids are known`);
  expect('library.large-list.fixture-columns-created', 'The seven fixture columns exist on the library and read back as their asked-for types');
  expect('library.large-list.fixture-file-count', `The library holds ${TARGET_FILES} files, counted from the newest file name`);
  expect('library.large-list.fixture-values-written', 'Every sampled file reads back holding the values its file number gives it');
  expect('library.large-list.fixture-calculated-column-computes', 'LVCalc reads back as LVNumber doubled on every sampled file');
  expect('library.large-list.fixture-distribution', 'The fixture holds more than 5,000 files and each LVChoice value selects a proper fraction of them');

  // Everything after the library, so an abort reports the truth about all of
  // it rather than about the rows the run happened to reach.
  const DOWNSTREAM = [
    ['library.large-list.fixture-target-list-seeded', `The lookup target list holds its ${TGT_ROW_COUNT} rows, and their ids are known`],
    ['library.large-list.fixture-columns-created', 'The seven fixture columns exist on the library and read back as their asked-for types'],
    ['library.large-list.fixture-file-count', `The library holds ${TARGET_FILES} files, counted from the newest file name`],
    ['library.large-list.fixture-values-written', 'Every sampled file reads back holding the values its file number gives it'],
    ['library.large-list.fixture-calculated-column-computes', 'LVCalc reads back as LVNumber doubled on every sampled file'],
    ['library.large-list.fixture-distribution', 'The fixture holds more than 5,000 files and each LVChoice value selects a proper fraction of them'],
  ];
  // ABORTED is open, not settled: the fixture did not build, so a re-paste can
  // clear every row this touches.
  const abortFrom = (id, reason) => {
    let seen = false;
    for (const [rowId, question] of DOWNSTREAM) {
      if (rowId === id) seen = true;
      if (seen) record(rowId, question, 'ABORTED', reason);
    }
    return report();
  };

  let digest = await getDigest();

  // A raw request body, not JSON. Files/add takes the file's bytes as the body,
  // and spPost JSON-encodes whatever it is given, which would upload the quotes
  // along with the text.
  const rawPost = async (path, body, extraHeaders = {}) => {
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
    digest = await getDigest();
    return spPost(`${container}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };

  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the WHOLE request, so a column missing one
  // property would read as a column that cannot be read at all.
  const readField = async (container, name) =>
    spGet(`${container}/fields/getbyinternalnameortitle('${odataName(name)}')`);

  // Deliberately reuses the digest the loop holds rather than fetching one.
  // getDigest is a POST to /contextinfo that THROWS on failure, so refreshing
  // per file would add 5,500 requests to the build and turn one bad minute on
  // the tenant into an unhandled rejection halfway through it. The loop
  // refreshes every DIGEST_EVERY files, which is the bound.
  const mergeItem = async (itemId, body) =>
    spPost(`${libPath}/items(${itemId})`, body, digest, {
      'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*',
    });

  // The verbose write, for the one candidate shape carrying `__metadata`. That
  // is a verbose OData construct and the harness's nometadata Content-Type
  // REJECTS it rather than ignoring it: threshold-index-probe.js lost a whole
  // live run to exactly this, and test_a_probe_sending_metadata_uses_verbose_odata
  // pins the pairing.
  let itemEntityType = null;
  const mergeItemVerbose = async (itemId, body) => {
    if (itemEntityType === null) {
      return {
        ok: false, status: 0, body: null,
        text: 'the library item entity type could not be read, so no verbose write was sent',
      };
    }
    return spPost(`${libPath}/items(${itemId})`, { __metadata: { type: itemEntityType }, ...body }, digest, {
      Accept: 'application/json;odata=verbose',
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*',
    });
  };

  // ---- fixture-library-created -----------------------------------------
  const ensureContainer = async (path, title, template, description) => {
    const found = await spGet(path);
    if (found.ok && found.body) {
      return { made: null, id: found.body.Id, note: `'${title}' already present` };
    }
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title, BaseTemplate: template, Description: description,
    }, digest);
    return {
      made,
      id: made.ok && made.body ? made.body.Id : null,
      note: made.ok
        ? `created '${title}'`
        : `'${title}' FAILED HTTP ${made.status}: ${clip(made.text, 200)}`,
    };
  };

  const library = await ensureContainer(libPath, LIB, 101,
    'dbml-sharepoint large-library fixture. Read by the beyond-5,000 probes. Do not delete.');
  record('library.doc-lib.fixture-library-created',
         'A document library is created (BaseTemplate 101)',
         library.id === null ? 'FAIL' : library.made === null ? 'ALREADY PRESENT' : 'PASS',
         library.made === null && library.id !== null
           ? `reusing '${LIB}'. That is the intent here: the fixture is permanent and a `
             + 'second paste resumes the build rather than starting one'
           : library.note);
  if (library.id === null) {
    return abortFrom('library.large-list.fixture-target-list-seeded',
                     `the fixture library was never created: ${library.note}`);
  }

  // ---- fixture-target-list-seeded --------------------------------------
  const target = await ensureContainer(tgtPath, TGT, 100,
    'dbml-sharepoint large-library fixture lookup target. Read by the beyond-5,000 probes. Do not delete.');
  const targetRowIds = [];
  const targetNotes = [target.note];
  if (target.id !== null) {
    const existing = await spGet(`${tgtPath}/items?$select=Id,Title&$top=100`);
    const rows = (!readFailed(existing) && Array.isArray(existing.body.value))
      ? existing.body.value : [];
    for (let index = 0; index < TGT_ROW_COUNT; index += 1) {
      const title = targetTitle(index);
      const found = rows.find((row) => row.Title === title);
      if (found) {
        targetRowIds.push(found.Id);
        continue;
      }
      digest = await getDigest();
      const made = await spPost(`${tgtPath}/items`, { Title: title }, digest);
      if (made.ok && made.body) {
        targetRowIds.push(made.body.Id);
      } else {
        targetNotes.push(`'${title}' FAILED HTTP ${made.status}: ${clip(made.text, 160)}`);
        break;
      }
    }
  }
  const targetReady = target.id !== null && targetRowIds.length === TGT_ROW_COUNT;
  // The mapping, printed rather than derived, because a later probe reading
  // this library needs the ids and `i%10 + 1` names a ROW rather than an id.
  const targetMap = {};
  targetRowIds.forEach((id, index) => { targetMap[targetTitle(index)] = id; });
  record('library.large-list.fixture-target-list-seeded',
         `The lookup target list holds its ${TGT_ROW_COUNT} rows, and their ids are known`,
         targetReady ? 'PASS' : 'FAIL',
         `${targetNotes.join('; ')}; ${targetRowIds.length}/${TGT_ROW_COUNT} row(s). `
         + `Row title to item id: ${show(targetMap)}. A file numbered i holds the row `
         + 'lvtarget-(i%10 + 1).');
  if (!targetReady) {
    return abortFrom('library.large-list.fixture-columns-created',
                     `the lookup target list did not build, so ${LOOKUP} has nothing to point `
                     + `at: ${targetNotes.join('; ')}`);
  }

  // ---- fixture-columns-created -----------------------------------------
  const choiceXml = (type, name) =>
    `<Field Type="${type}" DisplayName="${name}" Name="${name}">`
    + `<CHOICES>${CHOICES.map((choice) => `<CHOICE>${choice}</CHOICE>`).join('')}</CHOICES></Field>`;

  // Create one column and read it back, returning what the row wants to print.
  // Says nothing about whether the result is good: the caller owns the verdict.
  const ensureColumn = async (name, schemaXml, wantedType) => {
    const before = await readField(libPath, name);
    const made = before.ok ? null : await addField(libPath, schemaXml);
    const read = before.ok ? before : await readField(libPath, name);
    const ok = !readFailed(read) && read.body.TypeAsString === wantedType;
    return {
      ok,
      note: `${name}: ` + (made === null ? 'already present' : `create HTTP ${made.status}`)
        + (made === null || made.ok ? '' : ` ${clip(made.text, 160)}`)
        + '; readback ' + (readFailed(read)
          ? `failed HTTP ${read.status}`
          : `TypeAsString=${show(read.body.TypeAsString)}`
            + ` LookupList=${show(read.body.LookupList)}`
            + ` OutputType=${show(read.body.OutputType)}`),
    };
  };

  // Ordered, and the order is a dependency rather than a preference: LVCalc
  // computes from LVNumber and LVLookup points at the target list, so neither
  // can be created before what it names exists.
  const COLUMNS = [
    [TEXT, `<Field Type="Text" DisplayName="${TEXT}" Name="${TEXT}" MaxLength="255"/>`, 'Text'],
    [CHOICE, choiceXml('Choice', CHOICE), 'Choice'],
    [NUMBER, `<Field Type="Number" DisplayName="${NUMBER}" Name="${NUMBER}"/>`, 'Number'],
    [DATE, `<Field Type="DateTime" DisplayName="${DATE}" Name="${DATE}" Format="DateTime"/>`, 'DateTime'],
    [MULTI, choiceXml('MultiChoice', MULTI), 'MultiChoice'],
    [CALC,
     `<Field Type="Calculated" DisplayName="${CALC}" Name="${CALC}" ResultType="Number">`
     + `<Formula>=[${NUMBER}]*2</Formula>`
     + `<FieldRefs><FieldRef Name="${NUMBER}"/></FieldRefs></Field>`,
     'Calculated'],
    [LOOKUP,
     `<Field Type="Lookup" DisplayName="${LOOKUP}" Name="${LOOKUP}"`
     + ` List="{${target.id}}" ShowField="Title"/>`,
     'Lookup'],
  ];

  const columnNotes = [];
  let columnsReady = true;
  for (const [name, schemaXml, wantedType] of COLUMNS) {
    const built = await ensureColumn(name, schemaXml, wantedType);
    columnNotes.push(built.note);
    if (!built.ok) columnsReady = false;
  }
  record('library.large-list.fixture-columns-created',
         'The seven fixture columns exist on the library and read back as their asked-for types',
         columnsReady ? 'PASS' : 'FAIL',
         columnNotes.join('; '));
  if (!columnsReady) {
    return abortFrom('library.large-list.fixture-file-count',
                     `the fixture columns are not all present, so no file could be written `
                     + `correctly: ${columnNotes.join('; ')}`);
  }

  const entityRead = await spGet(`${libPath}?$select=ListItemEntityTypeFullName`);
  itemEntityType = (!readFailed(entityRead)) ? entityRead.body.ListItemEntityTypeFullName : null;

  // Read, never assembled. SharePoint derives a library's folder name from its
  // title at creation and the web may sit under /sites/<name>, so a path built
  // here would be a guess wearing an address's clothes.
  const rootRead = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (!readFailed(rootRead)) ? rootRead.body.ServerRelativeUrl : null;
  if (folderUrl === null) {
    return abortFrom('library.large-list.fixture-file-count',
                     `the library RootFolder did not read back (HTTP ${rootRead.status}), so `
                     + 'there is no address to upload to');
  }

  // ---- The zone a bare date read-back is rendered in --------------------
  // See the read-back-zone finding in the header: LVDate can come back as a
  // wall clock in the SITE's zone naming no zone at all, so the offsets such a
  // stamp may carry are read from the site rather than assumed.
  const zoneRead = await spGet('web/RegionalSettings/TimeZone');
  const zoneInfo = (!readFailed(zoneRead) && zoneRead.body.Information) || null;
  if (zoneInfo === null || typeof zoneInfo.Bias !== 'number') {
    return abortFrom('library.large-list.fixture-file-count',
                     `web/RegionalSettings/TimeZone did not read back a Bias (HTTP `
                     + `${zoneRead.status}), so a ${DATE} stamp naming no zone could not be `
                     + 'resolved to an instant. Nothing was uploaded, because a date comparison '
                     + 'guessing its own zone would either redo a correct fixture or certify a '
                     + 'broken one.');
  }
  // Windows convention: UTC = local + Bias + (Standard|Daylight)Bias, so local
  // is UTC minus the two. Which of the two is in force on a given date is not
  // stated and this fixture spans a year, so both stay candidates. Zero is a
  // candidate as well: a bare stamp that is already UTC is the same instant and
  // must not read as a lost write.
  const BARE_OFFSETS_MIN = [...new Set([
    0,
    -(zoneInfo.Bias + (zoneInfo.StandardBias || 0)),
    -(zoneInfo.Bias + (zoneInfo.DaylightBias || 0)),
  ])];
  const offsetLabel = (min) => `${min >= 0 ? '+' : ''}${min}min`;
  // Accepting a stamp under any of several offsets is only sound while those
  // offsets span less than a day, because consecutive file numbers are exactly
  // a day apart and a wider spread would let one file's date satisfy another's.
  // A real zone spans about fifteen hours at most, counting zero; anything
  // wider is a zone this probe cannot reason about rather than one to guess at.
  const offsetSpread = Math.max(...BARE_OFFSETS_MIN) - Math.min(...BARE_OFFSETS_MIN);
  if (offsetSpread >= 1440) {
    return abortFrom('library.large-list.fixture-file-count',
                     `the site zone's candidate offsets span ${offsetSpread} minutes, a full day `
                     + `or more, so a ${DATE} stamp naming no zone cannot be told from the next `
                     + `file's. Information reads ${show(zoneInfo)}.`);
  }

  // ---- Reading one file back -------------------------------------------
  // The six written columns in one call, and LVCalc in its own. Separated so a
  // problem selecting a calculated column cannot make the written columns read
  // as unreadable: one unrecognised name errors the whole request.
  const WRITTEN_SELECT =
    `Id,FileLeafRef,${TEXT},${CHOICE},${NUMBER},${DATE},${MULTI},${LOOKUP}Id`;

  const valuesOf = (raw) => {
    if (Array.isArray(raw)) return raw;
    if (raw && Array.isArray(raw.results)) return raw.results;
    return null;
  };
  const sameSet = (left, right) => left !== null
    && left.length === right.length
    && right.every((value) => left.some((held) => String(held) === String(value)));

  // Which form the date came back in. Observed and printed, never asserted: no
  // outcome below turns on it being any one of them.
  const dateFormsSeen = new Set();
  const ISO_STAMP =
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,7}))?(Z|[+-]\d{2}:?\d{2})?$/;

  // Does this read-back hold the instant the file number asks for? A stamp that
  // names its zone is unambiguous and Date.parse reads it. A stamp that names
  // none is a wall clock, so it is read through Date.UTC, which keeps it one,
  // and then matched against the site's own offsets. Date.parse must never see
  // it: on an offset-less string it applies the browser's zone.
  const dateHolds = (held, wantedMs) => {
    const parts = typeof held === 'string' ? held.match(ISO_STAMP) : null;
    if (!parts) return false;
    if (parts[8]) {
      if (Date.parse(held) !== wantedMs) return false;
      dateFormsSeen.add(`${show(held)}, which names its own zone`);
      return true;
    }
    const wall = Date.UTC(+parts[1], +parts[2] - 1, +parts[3], +parts[4], +parts[5], +parts[6],
                          parts[7] ? Number(`${parts[7]}000`.slice(0, 3)) : 0);
    const matched = BARE_OFFSETS_MIN.find((min) => wall - min * 60000 === wantedMs);
    if (matched === undefined) return false;
    dateFormsSeen.add(`${show(held)}, a wall clock naming no zone, `
      + `${offsetLabel(matched)} from the instant written`);
    return true;
  };

  // What is wrong with one file, as a list of sentences. Empty means correct.
  // Compared by VALUE rather than by string: a number may come back as a
  // number or as its decimal text, and a date comes back as an instant that
  // may be rendered in a zone it does not name, so a string comparison would
  // report a rendering difference as a lost write.
  const mismatchesFor = (n, row) => {
    const want = wantedFor(n);
    const problems = [];
    if (row[TEXT] !== want.text) {
      problems.push(`${TEXT}=${show(row[TEXT])} wanted ${show(want.text)}`);
    }
    if (row[CHOICE] !== want.choice) {
      problems.push(`${CHOICE}=${show(row[CHOICE])} wanted ${show(want.choice)}`);
    }
    if (Number(row[NUMBER]) !== want.number) {
      problems.push(`${NUMBER}=${show(row[NUMBER])} wanted ${show(want.number)}`);
    }
    if (!dateHolds(row[DATE], want.dateMs)) {
      problems.push(`${DATE}=${show(row[DATE])} wanted the instant ${show(want.date)}`);
    }
    if (!sameSet(valuesOf(row[MULTI]), want.multi)) {
      problems.push(`${MULTI}=${show(row[MULTI])} wanted ${show(want.multi)}`);
    }
    const wantedRowId = targetRowIds[want.lookupIndex];
    if (row[`${LOOKUP}Id`] !== wantedRowId) {
      problems.push(`${LOOKUP}Id=${show(row[`${LOOKUP}Id`])} wanted ${show(wantedRowId)}`);
    }
    return problems;
  };

  // A file's item, addressed through the FILE. Direct addressing rather than a
  // $filter on FileLeafRef, which a library past the threshold refuses:
  // library-index-threshold-probe.js measured that on 2026-09-08.
  const itemFor = async (n, select) => {
    const read = await spGet(
      `web/GetFileByServerRelativeUrl('${folderUrl}/${lit(fileName(n))}')`
      + `/ListItemAllFields?$select=${select}`);
    return readFailed(read) ? null : read.body;
  };

  // ---- The multi-value payload shape -----------------------------------
  // Learn documents no multi-value item payload at all, so the shape is an
  // ordered experiment. See the write-shape finding in the header.
  const MULTI_SHAPES = [
    { name: 'bare-array', verbose: false, build: (values) => values },
    { name: 'bare-results', verbose: false, build: (values) => ({ results: values }) },
    {
      name: 'collection-metadata',
      verbose: true,
      build: (values) => ({ __metadata: { type: 'Collection(Edm.String)' }, results: values }),
    },
  ];
  let winningShape = null;
  const shapeNotes = [];

  const payloadFor = (n, shape) => {
    const want = wantedFor(n);
    const body = {};
    body[TEXT] = want.text;
    body[CHOICE] = want.choice;
    body[NUMBER] = want.number;
    body[DATE] = want.date;
    body[`${LOOKUP}Id`] = targetRowIds[want.lookupIndex];
    body[MULTI] = shape.build(want.multi);
    return body;
  };

  const writeValues = async (n, itemId, shape) => (
    shape.verbose
      ? mergeItemVerbose(itemId, payloadFor(n, shape))
      : mergeItem(itemId, payloadFor(n, shape))
  );

  // Try each shape in order and keep the first that WRITES AND READS BACK.
  // Stopping at HTTP 200 alone would count a write that silently kept nothing
  // as a success, which is the failure class this project exists to close.
  //
  // Decided on MULTI ALONE, for the reason in the shape-experiment finding: a
  // shape is a statement about the multi-value payload, so letting another
  // column disqualify one lets an unrelated defect pick the winner. The other
  // columns are still compared, and returned so the caller can stop on them
  // under their own name rather than as a shape that did not take.
  const discoverShape = async (n, itemId) => {
    for (const shape of MULTI_SHAPES) {
      const wrote = await writeValues(n, itemId, shape);
      if (!wrote.ok) {
        shapeNotes.push(`${shape.name}: write HTTP ${wrote.status} ${clip(wrote.text, 120)}`);
        continue;
      }
      const back = await itemFor(n, WRITTEN_SELECT);
      if (back === null) {
        shapeNotes.push(`${shape.name}: wrote HTTP ${wrote.status} but the item did not read back`);
        continue;
      }
      const problems = mismatchesFor(n, back);
      const multiProblem = problems.find((problem) => problem.startsWith(`${MULTI}=`));
      if (multiProblem !== undefined) {
        shapeNotes.push(`${shape.name}: wrote HTTP ${wrote.status} but read back ${multiProblem}`);
        continue;
      }
      const others = problems.filter((problem) => problem !== multiProblem);
      shapeNotes.push(`${shape.name}: took, and ${fileName(n)} read back `
        + (others.length ? `${MULTI} correct but ${others.join(', ')}` : 'complete'));
      return { shape, others };
    }
    return { shape: null, others: [] };
  };

  // ---- fixture-file-count ----------------------------------------------
  const CONTENT = 'dbml-sharepoint large-library fixture file. Read by the beyond-5,000 probes.';

  const uploadOne = async (n) => {
    let attempt = 0;
    let last = null;
    while (attempt <= MAX_RETRIES) {
      last = await rawPost(
        `web/GetFolderByServerRelativeUrl('${folderUrl}')`
        + `/Files/add(url='${lit(fileName(n))}',overwrite=true)`, CONTENT,
        { 'Content-Type': 'text/plain' });
      if (last.ok) return last;
      // Throttling on the way to a fixture is weather, not a finding. Anything
      // else is returned unretried, because retrying a refusal repeats it.
      if (last.status !== 429 && last.status !== 503) return last;
      attempt += 1;
      await sleep(RETRY_MS * attempt);
    }
    return last;
  };

  // Where to resume. Read from the newest file the library already holds, and
  // then that file's own values, for the reasons in the two resume findings.
  // A read that FAILS is fatal rather than falling back to zero.
  const resumePoint = async () => {
    const newest = await spGet(
      `${libPath}/items?$select=Id,FileLeafRef&$orderby=Id desc&$top=1`);
    if (readFailed(newest) || !Array.isArray(newest.body.value)) {
      return {
        ok: false, from: null, held: 0,
        why: `the newest file could not be read (HTTP ${newest.status}), so the resume point `
          + 'is unknown. Restarting at file one would rewrite a fixture that may already be '
          + 'correct, so nothing was uploaded.',
      };
    }
    const rows = newest.body.value;
    if (rows.length === 0) return { ok: true, from: 1, held: 0, why: 'the library is empty' };
    const digits = String(rows[0].FileLeafRef || '').match(FILE_NUMBER);
    if (!digits) {
      return {
        ok: false, from: null, held: 0,
        why: `the newest file is named ${show(rows[0].FileLeafRef)}, which is not one of this `
          + 'fixture\'s names, so the library holds something this probe did not put there and '
          + 'the resume point cannot be computed',
      };
    }
    const held = Number(digits[1]);
    const back = await itemFor(held, WRITTEN_SELECT);
    const problems = back === null
      ? ['the item did not read back']
      : mismatchesFor(held, back);
    return {
      ok: true,
      // Complete means resume after it. Incomplete means resume AT it, and
      // overwrite=true redoes the upload and the write as a pair.
      from: problems.length === 0 ? held + 1 : held,
      held,
      why: problems.length === 0
        ? `${fileName(held)} is the newest file and reads back complete`
        : `${fileName(held)} is the newest file and is incomplete (${problems.join(', ')}), so `
          + 'this run redoes it',
    };
  };

  const resume = await resumePoint();
  if (!resume.ok) {
    return abortFrom('library.large-list.fixture-file-count', resume.why);
  }

  const buildNotes = [resume.why];
  let uploaded = 0;
  let stoppedAt = null;
  let stopReason = null;
  if (!BUILD_FIXTURE) {
    buildNotes.push('BUILD_FIXTURE is off, so nothing was uploaded this run');
  } else if (resume.from > TARGET_FILES) {
    buildNotes.push('the fixture was already complete, so nothing was uploaded this run');
  } else {
    for (let n = resume.from; n <= TARGET_FILES && uploaded < UPLOAD_CAP; n += 1) {
      if (uploaded > 0 && uploaded % DIGEST_EVERY === 0) digest = await getDigest();
      const sent = await uploadOne(n);
      if (!sent.ok) {
        stoppedAt = n;
        stopReason = `the upload of ${fileName(n)} returned HTTP ${sent.status}: ${clip(sent.text, 200)}`;
        break;
      }
      // Prefer the address SharePoint returned over one assembled from parts.
      const returned = sent.body && sent.body.ServerRelativeUrl
        ? sent.body.ServerRelativeUrl : null;
      const itemUrl = returned === null ? `${folderUrl}/${lit(fileName(n))}` : lit(returned);
      const idRead = await spGet(
        `web/GetFileByServerRelativeUrl('${itemUrl}')/ListItemAllFields?$select=Id`);
      if (readFailed(idRead) || typeof idRead.body.Id !== 'number') {
        stoppedAt = n;
        stopReason = `${fileName(n)} uploaded but the item behind it did not read back `
          + `(HTTP ${idRead.status}), so its columns could not be written`;
        break;
      }
      const itemId = idRead.body.Id;
      if (winningShape === null) {
        const found = await discoverShape(n, itemId);
        winningShape = found.shape;
        if (winningShape === null) {
          stoppedAt = n;
          stopReason = `no multi-value item payload shape wrote ${MULTI} and read it back on `
            + `${fileName(n)}: ${shapeNotes.join('; ')}`;
          break;
        }
        if (found.others.length) {
          stoppedAt = n;
          stopReason = `the '${winningShape.name}' shape wrote ${MULTI} and read it back, but `
            + `${fileName(n)} read back ${found.others.join(', ')}. That is a column write `
            + 'failing rather than a payload shape that did not take.';
          break;
        }
      } else {
        const wrote = await writeValues(n, itemId, winningShape);
        if (!wrote.ok) {
          stoppedAt = n;
          stopReason = `the column write on ${fileName(n)} returned HTTP ${wrote.status}: `
            + `${clip(wrote.text, 200)}`;
          break;
        }
      }
      uploaded += 1;
      // A spot check during the build, so a write that stops taking is caught
      // at the next checkpoint rather than at the end of a long run.
      if (n % VERIFY_EVERY === 0) {
        const back = await itemFor(n, WRITTEN_SELECT);
        const problems = back === null ? ['the item did not read back'] : mismatchesFor(n, back);
        if (problems.length) {
          stoppedAt = n;
          stopReason = `${fileName(n)} was written and read back ${problems.join(', ')}`;
          break;
        }
      }
      if (uploaded % PROGRESS_EVERY === 0) {
        log('INFO', `${uploaded} file(s) built this run; at ${fileName(n)}.`);
      }
    }
    buildNotes.push(`${uploaded} file(s) built this run`);
    if (stoppedAt !== null) {
      buildNotes.push(`the pass stopped at ${fileName(stoppedAt)}: ${stopReason}`);
    } else if (uploaded >= UPLOAD_CAP) {
      buildNotes.push(`the pass hit the per-run cap of ${UPLOAD_CAP}`);
    }
    if (winningShape !== null) {
      buildNotes.push(`the multi-value payload shape in use is '${winningShape.name}'`);
    }
  }

  // Counted from the newest file name, never from ItemCount. See the header.
  const after = await resumePoint();
  const count = after.ok ? after.held : 0;
  const complete = after.ok && count >= TARGET_FILES && after.from > TARGET_FILES;
  record('library.large-list.fixture-file-count',
         `The library holds ${TARGET_FILES} files, counted from the newest file name`,
         // ABORTED rather than SHORT when the count could not be read at all:
         // SHORT would claim the library is short, which is a different thing
         // from not knowing how long it is.
         !after.ok ? 'ABORTED' : complete ? 'PASS' : 'SHORT',
         `${buildNotes.join('; ')}. `
         + (after.ok
           ? `The newest file is now number ${count} of the ${TARGET_FILES} wanted; ${after.why}`
           : after.why)
         + (complete
           ? '. The fixture is built. Leave it in place.'
           : '. Re-paste with BUILD_FIXTURE = true until this reads PASS. Each paste resumes '
             + 'where the last one stopped.'));

  // ---- fixture-values-written ------------------------------------------
  // The sample, clamped to what exists: a short build still reports a real
  // sample rather than a row of files that were never uploaded.
  const sampled = SAMPLE.filter((n) => n <= count);
  const sampleNotes = [];
  const sampleProblems = [];
  const calcNotes = [];
  const calcProblems = [];
  for (const n of sampled) {
    const row = await itemFor(n, WRITTEN_SELECT);
    if (row === null) {
      sampleProblems.push(`${fileName(n)} did not read back`);
      continue;
    }
    const problems = mismatchesFor(n, row);
    if (problems.length) {
      sampleProblems.push(`${fileName(n)}: ${problems.join(', ')}`);
    } else {
      sampleNotes.push(fileName(n));
    }
    // LVCalc in its own read: see WRITTEN_SELECT above.
    const calcRow = await itemFor(n, `Id,${CALC}`);
    const wantedCalc = wantedFor(n).calc;
    if (calcRow === null) {
      calcProblems.push(`${fileName(n)}: ${CALC} did not read back`);
    } else if (Number(calcRow[CALC]) !== wantedCalc) {
      calcProblems.push(`${fileName(n)}: ${CALC}=${show(calcRow[CALC])} wanted ${wantedCalc}`);
    } else {
      calcNotes.push(`${fileName(n)} ${CALC}=${show(calcRow[CALC])}`);
    }
  }

  const shapeNote = winningShape === null
    ? `no shape was tried this run${shapeNotes.length ? `: ${shapeNotes.join('; ')}` : ''}`
    : `the shape that took is '${winningShape.name}' (${shapeNotes.join('; ')})`;
  // Observed, never asserted. The site's candidates are printed beside the
  // forms seen so a reader can check the resolution rather than take it.
  const dateFormNote = `${DATE} came back as `
    + (dateFormsSeen.size === 0
      ? 'no value that held the instant asked for, so the form a correct one takes '
        + 'was not observed this run'
      : `${clip(show([...dateFormsSeen]), 300)}; the site's candidate offsets are `
        + `${BARE_OFFSETS_MIN.map(offsetLabel).join(' / ')}`);
  record('library.large-list.fixture-values-written',
         'Every sampled file reads back holding the values its file number gives it',
         sampleProblems.length ? 'FAIL' : sampled.length === 0 ? 'ABORTED' : complete ? 'PASS' : 'SHORT',
         `${sampled.length} of ${SAMPLE.length} sample file(s) exist and were read back: `
         + `${show(sampled.map(fileName))}. Multi-value item payload: ${shapeNote}. `
         + `${dateFormNote}. `
         + (sampleProblems.length
           ? `mismatches: ${sampleProblems.join('; ')}`
           : `every sampled file read back as its file number says it should. `
             + `Correct: ${show(sampleNotes)}`)
         + (complete || sampled.length === 0
           ? ''
           : '. The build is incomplete, so this reports the files uploaded so far.'));

  // ---- fixture-calculated-column-computes ------------------------------
  // LVCalc is the one column nothing writes, so it is its own question: a
  // correct write and a formula that does not compute look identical in the
  // row above.
  record('library.large-list.fixture-calculated-column-computes',
         'LVCalc reads back as LVNumber doubled on every sampled file',
         calcProblems.length ? 'FAIL' : sampled.length === 0 ? 'ABORTED' : complete ? 'PASS' : 'SHORT',
         `over ${sampled.length} sampled file(s). `
         + (calcProblems.length
           ? `mismatches: ${calcProblems.join('; ')}`
           : `serialised as ${clip(show(calcNotes), 400)}`)
         + (sampled.length === 0
           ? '. No file exists yet, so nothing was read.'
           : ''));

  // ---- fixture-distribution --------------------------------------------
  // Counted over the file numbers rather than queried. Every value is a pure
  // function of the file number, so the tally is exact for a library holding
  // files 1..count, and a query for it would be one a library past the
  // threshold refuses on an unindexed column anyway. It is a statement about
  // the fixture's shape, and the row says which count it was computed over.
  const choiceTally = {};
  const lookupTally = {};
  for (const choice of CHOICES) choiceTally[choice] = 0;
  for (let index = 0; index < TGT_ROW_COUNT; index += 1) lookupTally[targetTitle(index)] = 0;
  for (let n = 1; n <= count; n += 1) {
    const want = wantedFor(n);
    choiceTally[want.choice] += 1;
    lookupTally[targetTitle(want.lookupIndex)] += 1;
  }
  const choiceCounts = CHOICES.map((choice) => choiceTally[choice]);
  const smallest = choiceCounts.length ? Math.min(...choiceCounts) : 0;
  const largest = choiceCounts.length ? Math.max(...choiceCounts) : 0;
  const selective = smallest > 0 && largest < count;
  const pastThreshold = count > 5000;
  record('library.large-list.fixture-distribution',
         'The fixture holds more than 5,000 files and each LVChoice value selects a proper fraction of them',
         pastThreshold && selective && complete ? 'PASS'
           : count === 0 ? 'ABORTED'
             : 'SHORT',
         `computed over the ${count} contiguously numbered file(s) the library holds. ${CHOICE}: `
         + `${show(choiceTally)}, so one value selects between ${smallest} and ${largest} of `
         + `${count}. ${LOOKUP}: ${show(lookupTally)}. ${TEXT} takes ${Math.min(100, count)} `
         + `distinct value(s), ${NUMBER} ${Math.min(1000, count)}, ${DATE} `
         + `${Math.min(365, count)}.`
         + (pastThreshold
           ? ' The library is over 5,000 files, so a query against it is sent past the list view threshold.'
           : ' The library is NOT over 5,000 files, so a query against it is not past the threshold. Re-paste with BUILD_FIXTURE = true.'));

  report();
  log('INFO', `The fixture library '${LIB}' and the list '${TGT}' are left in place.`);
  log('INFO', 'There is no cleanup path in this probe. Later probes read what it built.');
})();
