/**
 * dbml-sharepoint PROBE: BUILD THE LIBRARY WHOSE INDEX WAS WRITTEN BEFORE IT
 * CROSSED 5,000 ITEMS.
 *
 * REVISION: e53d0e7e
 *
 * THIS PROBE ANSWERS NO QUESTION ABOUT SHAREPOINT. It builds a second document
 * library that a later probe measures, and every row it records is a
 * `fixture-` row or a method control: a statement that the thing the later
 * probe depends on is actually there and actually holds the value it will read.
 * A run that reports every row PASS has produced a fixture, not a finding.
 *
 * WHY A SECOND FIXTURE, when 'dbmlsp Probe LargeLib' already exists. Every
 * index this repository has measured past the list view threshold was written
 * AFTER the library was already past it. #472, #478, #479, #480 and #481 all
 * indexed a column on a library holding 5,500 files. The guidance an operator
 * actually meets says to add the index BEFORE the container grows past 5,000,
 * and nothing here has measured whether the two orders produce the same
 * behaviour. This fixture is the other order: the index write lands while the
 * library holds fewer than 5,000 files, and the top-up then carries it past.
 * A measurement probe reading both fixtures can then ask whether a group-by on
 * a column indexed before crossing is served where one indexed after throttled.
 *
 * IT DOES NOT TOUCH 'dbmlsp Probe LargeLib'. That library is a separate,
 * separately owned fixture and its columns are named LV*. Nothing below reads
 * or writes it: the name, the file-name prefix and the column names here are
 * all different, and the resume read refuses a library holding file names this
 * probe did not put there.
 *
 * WHAT IT BUILDS, and this is a CONTRACT. The library name, the column names,
 * the file names and the value formulas below are read by the measurement probe
 * that follows. Changing any of them invalidates the fixture rather than
 * adjusting it, so a change here is a change to every probe that reads it.
 *
 *   Library:  'dbmlsp Probe PreIndex'
 *   Files:    'dbmlsp-pre-00001.txt' .. 'dbmlsp-pre-05100.txt', a few bytes of
 *             text each, contiguous and zero-padded to five digits
 *   Columns, both set on every file, where i is the file's sequence number
 *   counting from 1:
 *
 *     PChoice   Choice Alpha..Delta   values[i%4]   INDEXED at 4,900 files
 *     PNumber   Number                i%1000       left unindexed, on purpose
 *
 * THE TWO COLUMNS HAVE DIFFERENT JOBS. PChoice is the group-by column and the
 * subject: it is the one this probe indexes, and it is indexed while the
 * library is still under the threshold. PNumber is the witness and the negative
 * control for the measurement probe: it stays unindexed for the fixture's whole
 * life, so a measurement run that finds everything served can tell an index
 * doing its job from a tenant not enforcing the threshold at all.
 *
 * WHY THOSE DISTRIBUTIONS. A filter on one PChoice value selects about a
 * quarter of the library, roughly 1,275 files of 5,100, which is selective
 * enough to be a real query and small enough that a page ceiling is not
 * mistaken for it. PNumber wraps at 1000, so one value selects five or six
 * files. Both are pure functions of the file number, which is what lets the
 * measurement probe predict a result count without querying and lets this probe
 * verify a sample rather than every file.
 *
 * THE INDEX WRITE IS SANDWICHED, and that is the whole point of the probe.
 * It is sent after file 4,900 exists and before file 4,901 is uploaded. The
 * count it is sandwiched between is READ from the newest file name at that
 * moment rather than inferred from the loop counter, and the write is REFUSED
 * BY THIS PROBE if that read comes back at or past 5,000: an index written past
 * the threshold would produce a library indistinguishable from the one that
 * already exists, and the measurement it is being built for would compare a
 * fixture against itself.
 *
 * THE MOMENT IS STAMPED ON THE COLUMN, because a resumable build cannot prove
 * it from a later pass. The pass that writes the index observes the count; every
 * pass after it can only see that the flag is true, which does not say when it
 * was set. So the same pass writes the observed count and an ISO timestamp into
 * PChoice's own Description, and a later pass reports the index row by quoting
 * that stamp. A library whose PChoice reads Indexed=true with no stamp is
 * reported as INDEXED, MOMENT NOT RECORDED and stays open: the flag is there and
 * nothing on the tenant says it was set under the threshold.
 *
 * THE DESCRIPTION CONTROL IS ON PNumber, NOT ON PChoice, and the separation is
 * deliberate. PChoice's Description carries the stamp, so a control that wrote a
 * marker there and put it back would risk clobbering the one durable piece of
 * evidence this fixture holds. The control writes its marker on PNumber, whose
 * Description nothing reads, and puts it back in the same pass.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. All of it files under `library.large-list`,
 * the scope for a document library past the list view threshold, except the
 * library-creation row which keeps the id the other library probes share.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)?
 *   library.large-list.fixture-preindex-columns-created
 *        Do PChoice and PNumber exist on the library and read back as the types
 *        they were asked for?
 *   library.large-list.control-preindex-description-sticks
 *        POSITIVE CONTROL: does a Description MERGE on a contract column read
 *        back? A field MERGE that silently did nothing would report the index
 *        write below as a column refusing an index.
 *   library.large-list.control-preindex-unknown-property-refused
 *        NEGATIVE CONTROL: is a MERGE naming a property SP.Field does not have
 *        refused? Without it, "the write was accepted" says nothing.
 *   library.large-list.fixture-preindex-index-written-under-threshold
 *        Was Indexed=true written on PChoice while the library held fewer than
 *        5,000 files, and does the flag read back true?
 *   library.large-list.fixture-preindex-witness-unindexed
 *        Does PNumber still read Indexed=false, so the measurement probe has an
 *        unindexed column to witness the throttle with?
 *   library.large-list.fixture-preindex-file-count
 *        Does the library hold all TARGET_FILES files, counted from the newest
 *        file name rather than from ItemCount?
 *   library.large-list.fixture-preindex-values-written
 *        Do the sampled files read back holding the values the formulas above
 *        give them?
 *   library.large-list.fixture-preindex-distribution
 *        Does the value distribution meet what the measurement probe depends
 *        on: over 5,000 files in total, and each PChoice value selecting a
 *        proper fraction of them?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED. Every fixture row here is a
 * depends-on, because the whole probe is a fixture. What is nonetheless
 * OBSERVED and never asserted: what HTTP status the index MERGE comes back
 * with, what AutoIndexed reads afterwards, exactly how many files the library
 * held at the moment of the write, and how many pastes the build took. Those
 * are recorded in the evidence and no outcome turns on any of them being a
 * particular value. The one thing that IS asserted about the moment is the
 * inequality: the count read at the write must be under 5,000, and a run where
 * it is not writes nothing.
 *
 * VERIFICATION IS SAMPLED, deliberately. Reading every one of 5,100 files back
 * would double an already long build. So: every MERGE's status is checked and a
 * non-2xx stops the run; every VERIFY_EVERY-th file is read back during the
 * build and a mismatch stops the run; and after the build a fixed SAMPLE
 * spanning every wrap boundary in the formulas and both sides of the index
 * write and of the threshold is read back and compared. The fixture row names
 * the files it checked, so a reader can see the size of what was verified.
 *
 * THE BUILD IS RESUMABLE, and it has to be. Five thousand one hundred serial
 * uploads from a browser console take a long time and the harness caps a run at
 * 900 s. So: BUILD_FIXTURE gates the upload, a run uploads at most UPLOAD_CAP
 * files and then reports how far it got, and the resume point is READ rather
 * than assumed. Expect roughly six pastes. A run that reaches TARGET_FILES
 * reports the build PASS; a run that stops short says where it stopped.
 *
 * THE RESUME POINT IS THE NEWEST FILE NAME, NEVER ItemCount. `ItemCount` is
 * served from a timer-job cache and lags a fresh upload burst by minutes, so a
 * resume computed from it re-uploads work that is already done and, worse,
 * reports a short library as complete once the cache catches up. Two probes
 * record the same thing and read the same signal,
 * `library-index-threshold-probe.js` and `library-large-list-fixture-probe.js`.
 * The newest file's own values are then checked, because a file whose upload
 * took and whose metadata MERGE did not is the one gap a name-based resume
 * would step over.
 *
 * THE RESUME READ IS `$orderby=Id desc&$top=1`, and past 5,000 items that is
 * not a free choice. `library-index-threshold-probe.js` measured on 2026-09-08
 * that a document library past the threshold serves a selective filter on Id
 * and refuses one on Title, Name, Created, Modified, Author and Editor, so Id
 * is the one ordering this read can rely on once the top-up crosses. A read
 * that FAILS is fatal here rather than falling back to zero: a fallback would
 * restart the upload at file one and quietly rewrite a fixture that was already
 * correct.
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
 *   Library creation via POST to `web/lists`, and item updates via MERGE to
 *   `items(...)`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`, and the field read
 *   and MERGE via `fields/getbyinternalnameortitle('<name>')`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   File upload via `GetFolderByServerRelativeUrl(...)/Files/add(url=,overwrite=)`
 *   and the item behind a file via `GetFileByServerRelativeUrl(...)/ListItemAllFields`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   The list view threshold this fixture is built to straddle, and the index
 *   guidance the ordering question comes from:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 *
 * SCOPE OF CLAIMS: one tenant, one library, one caller context. The threshold
 * is documented as an effective figure rather than a constant, so the probe
 * that measures against this fixture owns its own controls. This probe
 * establishes only that the fixture is present, correct, and indexed under the
 * threshold.
 *
 * HOW TO RUN
 *   1. Open a site you are willing to leave a permanent 5,100-file library on.
 *      It can be the same site that holds 'dbmlsp Probe LargeLib'; this probe
 *      never touches that library.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED, ALLOW_WRITES and BUILD_FIXTURE true. Paste. Expect a long
 *      run that stops at the upload cap.
 *   4. Re-paste until `library.large-list.fixture-preindex-file-count` reads
 *      PASS. Each paste resumes where the last one stopped. One of those pastes
 *      crosses file 4,900 and writes the index; read that transcript's
 *      `fixture-preindex-index-written-under-threshold` row carefully, because
 *      it is the one moment no later paste can re-observe.
 *   5. Copy the whole RESULTS block back verbatim, from every paste.
 *
 * WHEN FINISHED: nothing. Leave the fixture in place, indexed. An operator who
 * clears PChoice's index has destroyed the only thing that distinguishes this
 * library from the one built after the threshold.
 */
// finding: preindex-fixture-index-write-is-refused-at-or-past-the-threshold -
// the write is gated on a count READ at the moment it is sent, and a count at or
// past 5,000 stops the pass rather than indexing anyway. An index written past
// the threshold produces a library identical in every measurable way to
// 'dbmlsp Probe LargeLib', so the fixture would silently become a copy of the
// thing it exists to be compared against, and the measurement would report a
// difference of zero as a finding. The gate reads the INDEX FLAG BEFORE THE
// COUNT for the same reason in reverse: the fixture's intended end state is a
// library past 5,000 with the index already on, and a gate that checked the
// count first reported the finished fixture as a fatal failure on every pass
// after the one that built it.
// finding: preindex-fixture-moment-is-stamped-because-a-later-pass-cannot-see-it
// - the build takes about six pastes and only one of them writes the index. Every
// pass after it sees Indexed=true and nothing else, which is equally consistent
// with an index written at 4,900 files and one written at 5,099. The observed
// count and an ISO timestamp are therefore written into PChoice's Description in
// the same pass as the index, and a later pass reports the row by quoting that
// stamp. Indexed=true with no stamp is reported open, never as a pass.
// finding: preindex-fixture-control-marker-avoids-the-stamped-column - the
// Description control writes its marker on PNumber rather than on PChoice.
// PChoice's Description is the fixture's durable evidence, and a control that
// wrote over it and put it back would put the one irreplaceable value in this
// fixture at the mercy of a restore that has already failed once elsewhere.
// finding: preindex-fixture-witness-column-must-stay-unindexed - PNumber is
// never indexed by this probe and its Indexed flag is reported on every pass. A
// measurement probe reading this fixture needs a column that throttles, or a
// served answer on PChoice says nothing about the index; the LargeLib runs on
// 2026-09-08 established that the flag is per column, so the witness has to be a
// real unindexed sibling rather than an argument.
// finding: preindex-fixture-values-are-a-pure-function-of-the-file-number -
// both columns are computed from the file's sequence number alone, with no
// run-time state. That is what lets the measurement probe predict a filter's
// result count without querying, lets this probe verify a sample rather than the
// whole library, and lets a resumed build produce exactly the file the
// interrupted one would have produced.
// finding: preindex-fixture-upload-exceeds-the-run-timeout - the harness caps a
// run at 900 s. The metadata-writing build of the seven-column LargeLib fixture
// fitted about 1,250 files in that window and a UPLOAD_CAP of 2,000 overshot it.
// This fixture writes two columns rather than seven but sends the same three
// requests per file, so UPLOAD_CAP stays at 1,000 and a paste finishes inside
// the run window.
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

  log('INFO', 'probe revision e53d0e7e. Quote this when reporting results.');

  // The expensive half. Off, so a paste that only wants to check an
  // already-built fixture never starts five thousand uploads.
  const BUILD_FIXTURE = false;

  // ---- The contract ----------------------------------------------------
  // Read by the measurement probe that follows. See the header: changing any
  // of these invalidates the fixture rather than adjusting it.
  const LIB = 'dbmlsp Probe PreIndex';
  const TARGET_FILES = 5100;
  // The count the index write is sandwiched after. Under THRESHOLD by 100
  // files, which is one PROGRESS_EVERY block: close enough that the write is
  // plainly a pre-threshold one, far enough that a resume landing a few files
  // either side of it still writes the index below the line.
  const INDEX_AT = 4900;
  // The documented list view threshold. An effective figure rather than a
  // constant, which is why the gate compares against a count it READ.
  const THRESHOLD = 5000;
  const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
  const CHOICE = 'PChoice';
  const NUMBER = 'PNumber';

  // ---- Run shape -------------------------------------------------------
  // At most this many files per paste, so a run is bounded and an operator
  // gets a progress report instead of a hung tab. See the run-timeout finding.
  const UPLOAD_CAP = 1000;
  // A form digest lives about thirty minutes, so it is refreshed per block of
  // files rather than per file.
  const DIGEST_EVERY = 200;
  const PROGRESS_EVERY = 250;
  // A throttled upload waits and is sent again, bounded.
  const RETRY_MS = 2000;
  const MAX_RETRIES = 3;
  // How often the build stops to read a file back.
  const VERIFY_EVERY = 250;
  // One bounded re-read after a field write. Same figure and same reasoning as
  // library-large-list-index-probe.js: a readback racing a write is a false
  // negative, a retry loop eventually passes anything.
  const REREAD_MS = 1500;
  // The sample the fixture rows are decided on: every wrap boundary in the
  // formulas, and both sides of the index write and of the threshold. A file
  // number over the current count is dropped rather than read, so a short build
  // still reports a real sample.
  const SAMPLE = [1, 2, 3, 4, 5, 100, 101, 999, 1000, 1001,
                  INDEX_AT - 1, INDEX_AT, INDEX_AT + 1,
                  THRESHOLD, THRESHOLD + 1, TARGET_FILES];

  const DESCRIPTION_MARKER = 'dbmlsp preindex fixture control marker';
  // A name SP.Field does not have. Deliberately not a near-miss of a real
  // property: the control asks whether an unknown name is refused, not whether
  // a typo is tolerated.
  const UNKNOWN_PROPERTY = 'NoSuchFieldPropertyAtAll';
  // The stamp the indexing pass leaves on PChoice, and the pattern a later
  // pass reads it back with. See the stamping finding.
  const STAMP_HEAD = 'dbmlsp preindex: Indexed:true written at ';
  const STAMP_RE = /dbmlsp preindex: Indexed:true written at (\d+) file\(s\) on (\S+)/;
  const stampFor = (held) => `${STAMP_HEAD}${held} file(s) on ${new Date().toISOString()}`;

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const lit = (value) => String(value).replace(/'/g, "''");
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const fileName = (n) => `dbmlsp-pre-${String(n).padStart(5, '0')}.txt`;
  const FILE_NUMBER = /dbmlsp-pre-(\d+)\.txt$/;

  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const fieldPath = (name) =>
    `${libPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  // Every value the fixture holds for one file, from the file's number alone.
  const wantedFor = (n) => ({
    choice: CHOICES[n % 4],
    number: n % 1000,
  });

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB} holding`);
    log('INFO', `${TARGET_FILES} small text files, at most ${UPLOAD_CAP} per paste, each`);
    log('INFO', `carrying two columns: ${CHOICE} and ${NUMBER}.`);
    log('INFO', `It would MERGE Indexed=true onto ${CHOICE} once, after file ${INDEX_AT}`);
    log('INFO', `and before file ${INDEX_AT + 1}, and refuse to send it if the library is`);
    log('INFO', `already at or past ${THRESHOLD} files. ${NUMBER} is left unindexed.`);
    log('INFO', BUILD_FIXTURE
      ? 'BUILD_FIXTURE is ON: the upload would run.'
      : 'BUILD_FIXTURE is off: no file would be uploaded, no index would be written,');
    if (!BUILD_FIXTURE) {
      log('INFO', 'and the fixture would be checked only as far as it has already been built.');
    }
    log('INFO', "It does NOT touch 'dbmlsp Probe LargeLib'. That is a different library with");
    log('INFO', 'different column names, owned by library-large-list-fixture-probe.js.');
    log('INFO', 'THIS FIXTURE IS PERMANENT. There is no cleanup path in this probe, and');
    log('INFO', 'the CLEANUP flag does nothing here. A later probe reads what it leaves.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }
  if (CLEANUP) {
    log('INFO', 'CLEANUP is on and is IGNORED here. This probe builds a fixture that a later');
    log('INFO', 'probe reads, and emptying it is a separate deliberate act.');
  }

  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.large-list.fixture-preindex-columns-created', `${CHOICE} and ${NUMBER} exist on the library and read back as their asked-for types`);
  expect('library.large-list.control-preindex-description-sticks', 'POSITIVE CONTROL: a Description MERGE on a contract column reads back');
  expect('library.large-list.control-preindex-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused');
  expect('library.large-list.fixture-preindex-index-written-under-threshold', `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`);
  expect('library.large-list.fixture-preindex-witness-unindexed', `${NUMBER} reads Indexed=false, so the measurement probe has an unindexed column to witness the throttle with`);
  expect('library.large-list.fixture-preindex-file-count', `The library holds ${TARGET_FILES} files, counted from the newest file name`);
  expect('library.large-list.fixture-preindex-values-written', 'Every sampled file reads back holding the values its file number gives it');
  expect('library.large-list.fixture-preindex-distribution', `The fixture holds more than ${THRESHOLD} files and each ${CHOICE} value selects a proper fraction of them`);

  // Everything after the library, so an abort reports the truth about all of
  // it rather than about the rows the run happened to reach.
  const DOWNSTREAM = [
    ['library.large-list.fixture-preindex-columns-created', `${CHOICE} and ${NUMBER} exist on the library and read back as their asked-for types`],
    ['library.large-list.control-preindex-description-sticks', 'POSITIVE CONTROL: a Description MERGE on a contract column reads back'],
    ['library.large-list.control-preindex-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused'],
    ['library.large-list.fixture-preindex-index-written-under-threshold', `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`],
    ['library.large-list.fixture-preindex-witness-unindexed', `${NUMBER} reads Indexed=false, so the measurement probe has an unindexed column to witness the throttle with`],
    ['library.large-list.fixture-preindex-file-count', `The library holds ${TARGET_FILES} files, counted from the newest file name`],
    ['library.large-list.fixture-preindex-values-written', 'Every sampled file reads back holding the values its file number gives it'],
    ['library.large-list.fixture-preindex-distribution', `The fixture holds more than ${THRESHOLD} files and each ${CHOICE} value selects a proper fraction of them`],
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

  const addField = async (schemaXml) => {
    digest = await getDigest();
    return spPost(`${libPath}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };

  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the WHOLE request, so a column missing one
  // property would read as a column that cannot be read at all.
  const readField = async (name) => spGet(fieldPath(name));

  // The verbose write, because `__metadata` is a verbose OData construct and
  // the harness's nometadata Content-Type REJECTS it rather than ignoring it:
  // threshold-index-probe.js lost a whole live run to exactly this, and
  // test_a_probe_sending_metadata_uses_verbose_odata pins the pairing.
  const mergeField = async (name, body, type) => {
    const fresh = await getDigest();
    return spPost(fieldPath(name), { __metadata: { type }, ...body }, fresh, {
      Accept: 'application/json;odata=verbose',
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };

  // Deliberately reuses the digest the loop holds rather than fetching one.
  // getDigest is a POST to /contextinfo that THROWS on failure, so refreshing
  // per file would add 5,100 requests to the build and turn one bad minute on
  // the tenant into an unhandled rejection halfway through it. The loop
  // refreshes every DIGEST_EVERY files, which is the bound.
  const mergeItem = async (itemId, body) =>
    spPost(`${libPath}/items(${itemId})`, body, digest, {
      'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*',
    });

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
    'dbml-sharepoint pre-index large-library fixture. Its group-by column is indexed '
    + 'below 5,000 files. Read by the beyond-5,000 probes. Do not delete.');
  record('library.doc-lib.fixture-library-created',
         'A document library is created (BaseTemplate 101)',
         library.id === null ? 'FAIL' : library.made === null ? 'ALREADY PRESENT' : 'PASS',
         library.made === null && library.id !== null
           ? `reusing '${LIB}'. That is the intent here: the fixture is permanent and a `
             + 'second paste resumes the build rather than starting one'
           : library.note);
  if (library.id === null) {
    return abortFrom('library.large-list.fixture-preindex-columns-created',
                     `the fixture library was never created: ${library.note}`);
  }

  // ---- fixture-preindex-columns-created --------------------------------
  // Create one column and read it back, returning what the row wants to print.
  // Says nothing about whether the result is good: the caller owns the verdict.
  //
  // NEITHER SCHEMA CARRIES AN INDEX. The index on PChoice is a separate,
  // deliberate write at INDEX_AT files, and creating the column pre-indexed
  // would answer the fixture's own question at file zero.
  const ensureColumn = async (name, schemaXml, wantedType) => {
    const before = await readField(name);
    const made = before.ok ? null : await addField(schemaXml);
    const read = before.ok ? before : await readField(name);
    const ok = !readFailed(read) && read.body.TypeAsString === wantedType;
    return {
      ok,
      note: `${name}: ` + (made === null ? 'already present' : `create HTTP ${made.status}`)
        + (made === null || made.ok ? '' : ` ${clip(made.text, 160)}`)
        + '; readback ' + (readFailed(read)
          ? `failed HTTP ${read.status}`
          : `TypeAsString=${show(read.body.TypeAsString)}`
            + ` Indexed=${show(read.body.Indexed)}`),
    };
  };

  const choiceXml = `<Field Type="Choice" DisplayName="${CHOICE}" Name="${CHOICE}">`
    + `<CHOICES>${CHOICES.map((choice) => `<CHOICE>${choice}</CHOICE>`).join('')}</CHOICES></Field>`;
  const COLUMNS = [
    [CHOICE, choiceXml, 'Choice'],
    [NUMBER, `<Field Type="Number" DisplayName="${NUMBER}" Name="${NUMBER}"/>`, 'Number'],
  ];

  const columnNotes = [];
  let columnsReady = true;
  for (const [name, schemaXml, wantedType] of COLUMNS) {
    const built = await ensureColumn(name, schemaXml, wantedType);
    columnNotes.push(built.note);
    if (!built.ok) columnsReady = false;
  }
  record('library.large-list.fixture-preindex-columns-created',
         `${CHOICE} and ${NUMBER} exist on the library and read back as their asked-for types`,
         columnsReady ? 'PASS' : 'FAIL',
         `${columnNotes.join('; ')}. Neither schema asks for an index: the one on ${CHOICE} is `
         + `written separately at ${INDEX_AT} files.`);
  if (!columnsReady) {
    return abortFrom('library.large-list.control-preindex-description-sticks',
                     'the fixture columns are not both present, so no file could be written '
                     + `correctly and no index could be written: ${columnNotes.join('; ')}`);
  }

  // ---- control-preindex-description-sticks -----------------------------
  // The field MERGE itself, proved on a property whose readback is not in
  // doubt. A MERGE that silently does nothing would report the index write
  // below as a column refusing an index.
  //
  // On PNumber, not on PChoice: see the control-marker finding. PChoice's
  // Description carries this fixture's one irreplaceable value.
  const priorRead = await readField(NUMBER);
  const priorDescription = readFailed(priorRead) ? null : priorRead.body.Description;
  const setDesc = await mergeField(NUMBER, { Description: DESCRIPTION_MARKER }, 'SP.Field');
  let descRead = await readField(NUMBER);
  let descReRead = false;
  const descriptionNow = () => (readFailed(descRead) ? null : descRead.body.Description);
  if (setDesc.ok && descriptionNow() !== DESCRIPTION_MARKER) {
    await sleep(REREAD_MS);
    descRead = await readField(NUMBER);
    descReRead = true;
  }
  const descSticks = setDesc.ok && descriptionNow() === DESCRIPTION_MARKER;
  record('library.large-list.control-preindex-description-sticks',
         'POSITIVE CONTROL: a Description MERGE on a contract column reads back',
         descSticks ? 'DESCRIPTION STUCK' : 'CONTROL FAILED, METHOD VOID',
         `MERGE Description on ${NUMBER} returned HTTP ${setDesc.status}; it reads back `
         + `${show(descriptionNow())}`
         + (descReRead ? `, on a re-read ${REREAD_MS} ms later` : '')
         + (descSticks
           ? `. A field MERGE reaches this library's columns, so a ${CHOICE} that does not take `
             + 'an index below is the column refusing and not the method failing.'
           : `: ${clip(setDesc.text, 200)}. Nothing below can distinguish a column that refuses `
             + 'an index from a MERGE that never arrived.'));
  if (descSticks) {
    // The marker is this probe's, not the fixture's. Put it back in the same
    // pass, and say so loudly if that fails.
    const restored = await mergeField(
      NUMBER,
      { Description: priorDescription === null || priorDescription === undefined ? '' : priorDescription },
      'SP.Field');
    log(restored.ok ? 'OK' : 'FAIL',
        restored.ok
          ? `Description on ${NUMBER} put back to ${show(priorDescription)}.`
          : `Description on ${NUMBER} is still the control marker: the restore returned HTTP `
            + `${restored.status} ${clip(restored.text, 200)}`);
  }

  // ---- control-preindex-unknown-property-refused -----------------------
  const unknown = await mergeField(NUMBER, { [UNKNOWN_PROPERTY]: 'x' }, 'SP.Field');
  const unknownRefused = isRefusal(unknown.status);
  record('library.large-list.control-preindex-unknown-property-refused',
         'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused',
         unknownRefused ? 'REFUSED' : 'CONTROL FAILED, METHOD VOID',
         `MERGE ${UNKNOWN_PROPERTY} on ${NUMBER} returned HTTP ${unknown.status}: `
         + `${clip(unknown.text, 200)}`
         + (unknownRefused
           ? '. The endpoint therefore rejects a property it does not know, so "the write was '
             + 'accepted" below means the property was recognised.'
           : '. An unknown property was ACCEPTED, so acceptance of Indexed=true below says '
             + 'nothing about whether the property was recognised.'));

  // SILENTLY IGNORED is the one verdict below that both method controls have to
  // hold for. A write that changed nothing and a write that never arrived look
  // identical, and only these two separate them.
  const methodControlsHeld = descSticks && unknownRefused;

  // Read, never assembled. SharePoint derives a library's folder name from its
  // title at creation and the web may sit under /sites/<name>, so a path built
  // here would be a guess wearing an address's clothes.
  const rootRead = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (!readFailed(rootRead)) ? rootRead.body.ServerRelativeUrl : null;
  if (folderUrl === null) {
    return abortFrom('library.large-list.fixture-preindex-index-written-under-threshold',
                     `the library RootFolder did not read back (HTTP ${rootRead.status}), so `
                     + 'there is no address to upload to and the build never started');
  }

  // ---- Reading one file back -------------------------------------------
  const WRITTEN_SELECT = `Id,FileLeafRef,${CHOICE},${NUMBER}`;

  // A file's item, addressed through the FILE. Direct addressing rather than a
  // $filter on FileLeafRef, which a library past the threshold refuses:
  // library-index-threshold-probe.js measured that on 2026-09-08.
  const itemFor = async (n, select) => {
    const read = await spGet(
      `web/GetFileByServerRelativeUrl('${folderUrl}/${lit(fileName(n))}')`
      + `/ListItemAllFields?$select=${select}`);
    return readFailed(read) ? null : read.body;
  };

  // What is wrong with one file, as a list of sentences. Empty means correct.
  // Compared by VALUE rather than by string: a number may come back as a
  // number or as its decimal text, and a string comparison would report a
  // rendering difference as a lost write.
  const mismatchesFor = (n, row) => {
    const want = wantedFor(n);
    const problems = [];
    if (row[CHOICE] !== want.choice) {
      problems.push(`${CHOICE}=${show(row[CHOICE])} wanted ${show(want.choice)}`);
    }
    if (Number(row[NUMBER]) !== want.number) {
      problems.push(`${NUMBER}=${show(row[NUMBER])} wanted ${show(want.number)}`);
    }
    return problems;
  };

  // ---- How many files the library holds, right now ---------------------
  // The newest file NAME, never ItemCount, and ordered on Id, which is the one
  // ordering a library past the threshold serves. See the header.
  const newestFile = async () => {
    const newest = await spGet(
      `${libPath}/items?$select=Id,FileLeafRef&$orderby=Id desc&$top=1`);
    if (readFailed(newest) || !Array.isArray(newest.body.value)) {
      return {
        ok: false, number: 0, name: null,
        why: `the newest file could not be read (HTTP ${newest.status})`,
      };
    }
    const rows = newest.body.value;
    if (rows.length === 0) {
      return { ok: true, number: 0, name: null, why: 'the library is empty' };
    }
    const name = String(rows[0].FileLeafRef || '');
    const digits = name.match(FILE_NUMBER);
    if (!digits) {
      return {
        ok: false, number: 0, name,
        why: `the newest file is named ${show(name)}, which is not one of this fixture's names, `
          + 'so the library holds something this probe did not put there',
      };
    }
    return {
      ok: true, number: Number(digits[1]), name,
      why: `${name} is the newest file`,
    };
  };

  // ---- PChoice's index flag and its stamp -------------------------------
  const choiceState = async () => {
    const read = await readField(CHOICE);
    if (readFailed(read)) {
      return { ok: false, status: read.status, indexed: null, auto: null,
               description: null, stamp: null };
    }
    const description = typeof read.body.Description === 'string' ? read.body.Description : '';
    const found = STAMP_RE.exec(description);
    return {
      ok: true,
      status: read.status,
      indexed: typeof read.body.Indexed === 'boolean' ? read.body.Indexed : null,
      auto: typeof read.body.AutoIndexed === 'boolean' ? read.body.AutoIndexed : null,
      description,
      stamp: found === null ? null : { held: Number(found[1]), at: found[2], text: found[0] },
    };
  };

  // ---- The index write, sandwiched --------------------------------------
  // Sent after file INDEX_AT and before file INDEX_AT+1, on a count READ at
  // that moment, and refused at or past THRESHOLD. See the two findings above.
  //
  // Sets `preIndex.outcome` when it runs, which is what tells the row below
  // that this pass is the one that can speak to the moment. Returns whether
  // the build may continue past INDEX_AT.
  const preIndex = { outcome: null, evidence: null, state: null };
  const settleIndex = (outcome, evidence, state) => {
    preIndex.outcome = outcome;
    preIndex.evidence = evidence;
    preIndex.state = state || null;
    return outcome === 'PASS';
  };

  const writePreIndex = async () => {
    // THE FLAG IS READ BEFORE THE COUNT, and the order is not cosmetic. The
    // count check below refuses to write at or past THRESHOLD, and the fixture's
    // whole intended end state is a library that IS past THRESHOLD with the
    // index already on. Reading the count first made the gate report the
    // finished fixture as a fatal failure on every pass after the one that
    // built it, which is the depends-on / observes confusion the repository's
    // own rule names: a run that kills itself the moment it starts working.
    const before = await choiceState();
    if (!before.ok) {
      return settleIndex('ABORTED',
        `${CHOICE} did not read back (HTTP ${before.status}), so the flag it started with is `
        + 'unknown and a readback of true afterwards would say nothing about the write');
    }
    if (before.indexed === true) {
      // An earlier pass wrote it. This pass leaves preIndex.outcome null, so
      // the row below reports from the stamp, which is the only thing that can
      // still speak to the count at the moment of the write.
      return true;
    }

    const held = await newestFile();
    if (!held.ok) {
      return settleIndex('ABORTED',
        `${held.why}, so the count the index write has to be under could not be established. `
        + 'Nothing was written and no file past the sandwich point was uploaded.');
    }
    if (held.number >= THRESHOLD) {
      return settleIndex('FAIL',
        `the library already holds ${held.number} file(s), at or past the ${THRESHOLD} this `
        + `fixture's index must be written BELOW, and ${CHOICE} reads `
        + `Indexed=${show(before.indexed)}. Nothing was written. An index sent now would `
        + "produce a library indistinguishable from 'dbmlsp Probe LargeLib', which is the thing "
        + 'this fixture exists to be compared against, so the measurement it is being built for '
        + 'would compare a fixture with itself. This library cannot become the pre-index fixture: '
        + 'build a new one under a new name.');
    }

    const wrote = await mergeField(CHOICE, { Indexed: true }, 'SP.Field');
    let after = await choiceState();
    let reRead = false;
    if (wrote.ok && after.ok && after.indexed !== true) {
      await sleep(REREAD_MS);
      after = await choiceState();
      reRead = true;
    }
    const afterNote = after.ok
      ? `Indexed=${show(after.indexed)}, AutoIndexed=${show(after.auto)} after`
      : `unreadable after (HTTP ${after.status})`;
    const sent = `MERGE Indexed:true as SP.Field on a library of ${held.number} file(s), which is `
      + `${THRESHOLD - held.number} under the ${THRESHOLD} threshold, returned HTTP `
      + `${wrote.status}; ${CHOICE} read Indexed=${show(before.indexed)}, `
      + `AutoIndexed=${show(before.auto)} before, ${afterNote}`
      + (reRead ? `, on a re-read ${REREAD_MS} ms later` : '');

    if (!wrote.ok && !isRefusal(wrote.status)) {
      return settleIndex('NOT ESTABLISHED',
        `${sent}. HTTP ${wrote.status} is about who is asking or about the moment rather than `
        + `the server refusing the write: ${clip(wrote.text, 200)}. Re-paste to try again; the `
        + `library is still under the threshold at ${held.number} file(s).`);
    }
    if (!wrote.ok) {
      return settleIndex('REFUSED',
        `${sent}. The server refused it: ${clip(wrote.text, 240)}. A Choice column under the `
        + 'threshold would not take an index on this tenant, so this fixture cannot be built as '
        + 'specified and the difference it exists to measure has no before half.',
        'settled');
    }
    if (after.indexed !== true) {
      return settleIndex('SILENTLY IGNORED',
        `${sent}. The write was accepted and changed nothing, which is the failure class this `
        + 'repository exists to find.',
        methodControlsHeld ? 'settled' : 'void');
    }

    // The moment, written where a later pass can read it. See the stamping
    // finding: no pass after this one can observe the count that mattered.
    const stampText = stampFor(held.number);
    const stamped = await mergeField(CHOICE, { Description: stampText }, 'SP.Field');
    const stampBack = await choiceState();
    const stampLanded = stamped.ok && stampBack.ok && stampBack.stamp !== null;
    if (!stampLanded) {
      log('FAIL',
          `${CHOICE} is indexed but the moment was NOT stamped on it (HTTP ${stamped.status} `
          + `${clip(stamped.text, 160)}). Later pastes will report the index row as open. Set `
          + `${CHOICE}'s Description to: ${stampText}`);
    }
    return settleIndex('PASS',
      `${sent}. ${stampLanded
        ? `The moment is stamped on ${CHOICE}'s Description as ${show(stampBack.stamp.text)}, so a `
          + 'later paste can quote it rather than infer it.'
        : `The moment could NOT be stamped on ${CHOICE}'s Description (HTTP ${stamped.status}: `
          + `${clip(stamped.text, 160)}), so this transcript is the only record that the write `
          + `happened under the threshold. Set the Description by hand to: ${stampText}`}`);
  };

  // ---- fixture-preindex-file-count -------------------------------------
  const CONTENT = 'dbml-sharepoint pre-index large-library fixture file. '
    + 'Read by the beyond-5,000 probes.';

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

  // Where to resume: the newest file, and then that file's own values, because
  // a file whose Files/add took and whose metadata MERGE did not is the one gap
  // a name-based resume would step over. Complete means resume after it;
  // incomplete means resume AT it, and overwrite=true redoes the pair.
  const resumePoint = async () => {
    const newest = await newestFile();
    if (!newest.ok) {
      return {
        ok: false, from: null, held: 0,
        why: `${newest.why}, so the resume point is unknown. Restarting at file one would `
          + 'rewrite a fixture that may already be correct, so nothing was uploaded.',
      };
    }
    if (newest.number === 0) {
      return { ok: true, from: 1, held: 0, why: newest.why };
    }
    const back = await itemFor(newest.number, WRITTEN_SELECT);
    const problems = back === null
      ? ['the item did not read back']
      : mismatchesFor(newest.number, back);
    return {
      ok: true,
      from: problems.length === 0 ? newest.number + 1 : newest.number,
      held: newest.number,
      why: problems.length === 0
        ? `${newest.name} is the newest file and reads back complete`
        : `${newest.name} is the newest file and is incomplete (${problems.join(', ')}), so this `
          + 'run redoes it',
    };
  };

  const resume = await resumePoint();
  if (!resume.ok) {
    return abortFrom('library.large-list.fixture-preindex-index-written-under-threshold',
                     resume.why);
  }

  const buildNotes = [resume.why];
  let uploaded = 0;
  let stoppedAt = null;
  let stopReason = null;
  // Starts false on every paste rather than being carried over, so the gate
  // reads the flag off the column instead of trusting a previous run's word
  // for it. writePreIndex returns true immediately when it is already set, so
  // the cost of starting false is one field read per paste.
  let indexIsOn = false;
  if (!BUILD_FIXTURE) {
    buildNotes.push('BUILD_FIXTURE is off, so nothing was uploaded this run');
  } else if (resume.from > TARGET_FILES) {
    buildNotes.push('the fixture was already complete, so nothing was uploaded this run');
  } else {
    for (let n = resume.from; n <= TARGET_FILES && uploaded < UPLOAD_CAP; n += 1) {
      // The sandwich. Before the first file past INDEX_AT is uploaded, and only
      // once: writePreIndex returns true immediately when the flag is already
      // set. A pass that ends exactly at INDEX_AT leaves this to the next one.
      if (n > INDEX_AT && !indexIsOn) {
        const proceed = await writePreIndex();
        if (!proceed) {
          stoppedAt = n;
          stopReason = `the index write on ${CHOICE} did not leave the column indexed, and the `
            + `build must not carry the library past ${THRESHOLD} without it: ${preIndex.outcome}`;
          break;
        }
        indexIsOn = true;
      }
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
      const want = wantedFor(n);
      const wrote = await mergeItem(idRead.body.Id, {
        [CHOICE]: want.choice,
        [NUMBER]: want.number,
      });
      if (!wrote.ok) {
        stoppedAt = n;
        stopReason = `the column write on ${fileName(n)} returned HTTP ${wrote.status}: `
          + `${clip(wrote.text, 200)}`;
        break;
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
  }

  // ---- fixture-preindex-index-written-under-threshold ------------------
  // The gate speaks for the pass that wrote the index. Every other pass reads
  // the flag and the stamp, and says which of the two it is reporting from.
  const finalChoice = await choiceState();
  const afterBuild = await newestFile();
  const count = afterBuild.ok ? afterBuild.number : 0;
  if (preIndex.outcome !== null) {
    record('library.large-list.fixture-preindex-index-written-under-threshold',
           `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`,
           preIndex.outcome, preIndex.evidence, preIndex.state);
  } else if (!finalChoice.ok) {
    record('library.large-list.fixture-preindex-index-written-under-threshold',
           `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`,
           'ABORTED',
           `${CHOICE} did not read back (HTTP ${finalChoice.status}), so neither its index flag `
           + 'nor the stamp beside it could be read this pass');
  } else if (finalChoice.indexed === true && finalChoice.stamp !== null) {
    record('library.large-list.fixture-preindex-index-written-under-threshold',
           `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`,
           finalChoice.stamp.held < THRESHOLD ? 'PASS' : 'FAIL',
           `${CHOICE} reads Indexed=${show(finalChoice.indexed)}, `
           + `AutoIndexed=${show(finalChoice.auto)}, and carries the stamp `
           + `${show(finalChoice.stamp.text)} left by the pass that wrote it. The library held `
           + `${finalChoice.stamp.held} file(s) at that moment and holds ${count} now`
           + (finalChoice.stamp.held < THRESHOLD
             ? `. The write therefore landed ${THRESHOLD - finalChoice.stamp.held} file(s) under `
               + 'the threshold, which is what distinguishes this fixture from '
               + "'dbmlsp Probe LargeLib'."
             : `. That is AT OR PAST the ${THRESHOLD} the write had to be under, so this library `
               + 'is not a pre-index fixture whatever its name says.'));
  } else if (finalChoice.indexed === true) {
    record('library.large-list.fixture-preindex-index-written-under-threshold',
           `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`,
           'INDEXED, MOMENT NOT RECORDED',
           `${CHOICE} reads Indexed=${show(finalChoice.indexed)} and its Description is `
           + `${show(clip(finalChoice.description, 200))}, which carries no stamp. The flag is `
           + 'there and nothing on the tenant says it was set under the threshold, so this pass '
           + 'cannot tell an index written at 4,900 files from one written at 5,099. Read the '
           + 'transcript of the pass that wrote it, and stamp the column by hand if that '
           + 'transcript confirms the count.',
           // Explicit: the classifier reads this head as settled, and the
           // question it asks was not answered.
           'open');
  } else if (count >= THRESHOLD) {
    record('library.large-list.fixture-preindex-index-written-under-threshold',
           `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`,
           'FAIL',
           `the library holds ${count} file(s), at or past ${THRESHOLD}, and ${CHOICE} reads `
           + `Indexed=${show(finalChoice.indexed)}. It crossed the threshold unindexed, so an `
           + 'index written now would be the same order this fixture exists to be different '
           + 'from. This library cannot become the pre-index fixture: build a new one under a '
           + 'new name.');
  } else {
    record('library.large-list.fixture-preindex-index-written-under-threshold',
           `Indexed=true was written on ${CHOICE} while the library held fewer than ${THRESHOLD} files, and the flag reads back true`,
           'SHORT',
           `the library holds ${count} file(s) and ${CHOICE} reads `
           + `Indexed=${show(finalChoice.indexed)}. The index write is sent when the build `
           + `crosses ${INDEX_AT}, which this run has not reached. Re-paste with `
           + 'BUILD_FIXTURE = true.');
  }

  // ---- fixture-preindex-witness-unindexed ------------------------------
  // The measurement probe's negative control, checked on every pass because
  // threshold-index-probe.js watched SharePoint index a column on its own
  // between two runs. A witness that quietly acquired an index would let a
  // measurement run report everything served and conclude nothing.
  const witness = await readField(NUMBER);
  const witnessIndexed = readFailed(witness) || typeof witness.body.Indexed !== 'boolean'
    ? null : witness.body.Indexed;
  record('library.large-list.fixture-preindex-witness-unindexed',
         `${NUMBER} reads Indexed=false, so the measurement probe has an unindexed column to witness the throttle with`,
         witnessIndexed === null ? 'ABORTED' : witnessIndexed === false ? 'PASS' : 'FAIL',
         witnessIndexed === null
           ? `${NUMBER} did not read back an Indexed flag (HTTP ${witness.status})`
           : `${NUMBER}: Indexed=${show(witness.body.Indexed)}, `
             + `AutoIndexed=${show(witness.body.AutoIndexed)}`
             + (witnessIndexed === false
               ? '. Nothing in this probe indexes it, and a measurement run can use it as the '
                 + 'column that still throttles.'
               : '. The witness is indexed, so a measurement run against this fixture has no '
                 + 'column left to demonstrate the threshold with. Clear it before measuring.'));

  // ---- fixture-preindex-file-count -------------------------------------
  const after = await resumePoint();
  const complete = after.ok && count >= TARGET_FILES && after.from > TARGET_FILES;
  record('library.large-list.fixture-preindex-file-count',
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
           ? '. The fixture is built. Leave it in place, indexed.'
           : '. Re-paste with BUILD_FIXTURE = true until this reads PASS. Each paste resumes '
             + 'where the last one stopped.'));

  // ---- fixture-preindex-values-written ---------------------------------
  // The sample, clamped to what exists: a short build still reports a real
  // sample rather than a row of files that were never uploaded.
  const sampled = SAMPLE.filter((n) => n <= count);
  const sampleNotes = [];
  const sampleProblems = [];
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
  }
  record('library.large-list.fixture-preindex-values-written',
         'Every sampled file reads back holding the values its file number gives it',
         sampleProblems.length ? 'FAIL'
           : sampled.length === 0 ? 'ABORTED'
             : complete ? 'PASS' : 'SHORT',
         `${sampled.length} of ${SAMPLE.length} sample file(s) exist and were read back: `
         + `${show(sampled.map(fileName))}. `
         + (sampleProblems.length
           ? `mismatches: ${sampleProblems.join('; ')}`
           : `every sampled file read back as its file number says it should. Correct: `
             + `${show(sampleNotes)}`)
         + (complete || sampled.length === 0
           ? ''
           : '. The build is incomplete, so this reports the files uploaded so far.'));

  // ---- fixture-preindex-distribution -----------------------------------
  // Counted over the file numbers rather than queried. Every value is a pure
  // function of the file number, so the tally is exact for a library holding
  // files 1..count, and a query for it would be one a library past the
  // threshold refuses on an unindexed column anyway.
  const choiceTally = {};
  for (const choice of CHOICES) choiceTally[choice] = 0;
  for (let n = 1; n <= count; n += 1) choiceTally[wantedFor(n).choice] += 1;
  const choiceCounts = CHOICES.map((choice) => choiceTally[choice]);
  const smallest = choiceCounts.length ? Math.min(...choiceCounts) : 0;
  const largest = choiceCounts.length ? Math.max(...choiceCounts) : 0;
  const selective = smallest > 0 && largest < count;
  const pastThreshold = count > THRESHOLD;
  record('library.large-list.fixture-preindex-distribution',
         `The fixture holds more than ${THRESHOLD} files and each ${CHOICE} value selects a proper fraction of them`,
         pastThreshold && selective && complete ? 'PASS'
           : count === 0 ? 'ABORTED'
             : 'SHORT',
         `computed over the ${count} contiguously numbered file(s) the library holds. ${CHOICE}: `
         + `${show(choiceTally)}, so one value selects between ${smallest} and ${largest} of `
         + `${count}. ${NUMBER} takes ${Math.min(1000, count)} distinct value(s).`
         + (pastThreshold
           ? ` The library is over ${THRESHOLD} files, so a query against it is sent past the `
             + 'list view threshold.'
           : ` The library is NOT over ${THRESHOLD} files, so a query against it is not past the `
             + 'threshold. Re-paste with BUILD_FIXTURE = true.'));

  report();
  log('INFO', `The fixture library '${LIB}' is left in place, with ${CHOICE} indexed and`);
  log('INFO', `${NUMBER} unindexed. There is no cleanup path in this probe.`);
  log('INFO', "It has not touched 'dbmlsp Probe LargeLib'.");
})();
