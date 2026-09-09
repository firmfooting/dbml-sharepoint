/**
 * dbml-sharepoint PROBE: BUILD THE LARGE LIBRARY THAT HOLDS ITS FILES IN
 * FOLDERS, AND THE SMALL LIBRARY THAT PAIRS WITH IT.
 *
 * REVISION: cd01086f
 *
 * THIS PROBE ANSWERS NO QUESTION ABOUT SHAREPOINT. It builds two document
 * libraries that a later probe measures, and every row it records is a
 * `fixture-` row or a method control: a statement that the thing the later
 * probe depends on is actually there and actually holds the value it will read.
 * A run that reports every row PASS has produced a fixture, not a finding.
 *
 * WHY A THIRD AND A FOURTH LIBRARY, when 'dbmlsp Probe LargeLib' and
 * 'dbmlsp Probe PreIndex' already exist. Two questions are registered against
 * the modern document library page and neither permanent fixture can carry
 * them:
 *
 *   library.large-list.ui-group-by-indexed-column-folder-scoped needs a FOLDER
 *   holding fewer than 5,000 files inside a LIBRARY holding more than 5,000.
 *   Both existing fixtures are flat, and adding a folder to either would break
 *   the `$orderby=Id desc&$top=1` resume read they fail closed on, because a
 *   folder is an item too and would come back as the newest row.
 *
 *   The three-level group-by control was refused on the flat 5,500-file library
 *   even narrowed to a handful of ids, so the two rows depending on it went
 *   void. A SMALL library carrying three columns of the right kinds gives that
 *   control somewhere to succeed, and the pair of runs then separates the shape
 *   from the size.
 *
 * IT TOUCHES NEITHER EXISTING FIXTURE. 'dbmlsp Probe LargeLib' and 'dbmlsp
 * Probe PreIndex' are separately owned and their file names carry the prefixes
 * `dbmlsp-lv-` and `dbmlsp-pre-`. Nothing below reads or writes them: the
 * library names, the file-name prefixes and the folder names here are all
 * different, and every resume read refuses a container holding names this
 * probe did not put there.
 *
 * WHAT IT BUILDS, and this is a CONTRACT. The library names, the folder names,
 * the column names, the file names and the value formulas below are read by the
 * measurement probes that follow. Changing any of them invalidates the fixture
 * rather than adjusting it, so a change here is a change to every probe that
 * reads it.
 *
 *   Library:  'dbmlsp Probe Foldered'
 *   Folders:  'Alpha-F', 'Beta-F', 'Gamma-F', all at the library root
 *   Files:    'dbmlsp-fld-00001.txt' .. 'dbmlsp-fld-05256.txt', a few bytes of
 *             text each, contiguous and zero-padded to five digits, each in the
 *             folder its own number names
 *   Columns, both set on every file, where i is the file's sequence number
 *   counting from 1:
 *
 *     PChoice   Choice Alpha..Delta   values[i%4]   INDEXED at 4,900 files
 *     PNumber   Number                i%1000       left unindexed, on purpose
 *     folder                          folders[i%3] which folder it is uploaded to
 *
 *   Library:  'dbmlsp Probe MultiLevel'
 *   Files:    'dbmlsp-ml-00001.txt' .. 'dbmlsp-ml-00240.txt', at the root, no
 *             folders, no index, and deliberately far under the threshold
 *   Columns, all three set on every file:
 *
 *     MChoice   Choice Alpha..Delta   values[i%4]
 *     MFlag     Yes/No                i%3 === 0
 *     MText     Text                  'mtext-' + i%5
 *
 * WHY 5,256 AND 1,752. The library has to be over 5,000 and each folder well
 * under it, which 5,256 across three folders satisfies with 1,752 apiece. The
 * exact figure is 12 x 438, and 12 is the wrap of the folder and choice
 * formulas together, so every folder holds exactly 438 files of each PChoice
 * value. A measurement probe can therefore predict a folder-scoped group-by's
 * bucket sizes without querying, and a bucket that comes back the wrong size is
 * a finding rather than a rounding argument.
 *
 * WHY 240 ON THE SMALL LIBRARY. Its three columns wrap at 4, 3 and 5, which are
 * pairwise coprime, so the three levels of a group-by cut the file set
 * independently and every combination of the three values is non-empty. 240 is
 * four whole turns of the 60-file cycle those moduli make together, so each
 * combination holds the same count as every other combination with the same
 * MFlag value. That is what a three-level group-by needs to demonstrate
 * anything: three levels that each actually partition what the level above
 * them left.
 *
 * THE TWO COLUMNS ON THE LARGE LIBRARY HAVE DIFFERENT JOBS, the same two jobs
 * they have on 'dbmlsp Probe PreIndex'. PChoice is the group-by column and the
 * subject, and it is a SINGLE-VALUE Choice offering four values, which is the
 * shape the fixture it pairs against carries. PNumber is the witness and the
 * negative control: it stays unindexed for the fixture's whole life, so a
 * measurement run that finds everything served can tell an index doing its job
 * from a tenant not enforcing the threshold at all.
 *
 * THE INDEX WRITE IS SANDWICHED, exactly as it is in
 * `library-large-list-preindex-fixture-probe.js`, and for the same reason. It
 * is sent after file 4,900 exists and before file 4,901 is uploaded. The count
 * it is sandwiched between is READ from the newest file name at that moment
 * rather than inferred from the loop counter, and the write is REFUSED BY THIS
 * PROBE if that read comes back at or past 5,000. The guidance an operator
 * meets says to index before the container grows past 5,000, so a fixture built
 * for a folder-scoping question has to be indexed in that order too, or a
 * difference between this library and the flat ones would have two causes.
 *
 * THE MOMENT IS STAMPED ON THE COLUMN, because a resumable build cannot prove
 * it from a later pass. The pass that writes the index observes the count;
 * every pass after it can only see that the flag is true, which does not say
 * when it was set. So the same pass writes the observed count and an ISO
 * timestamp into PChoice's own Description, and a later pass reports the index
 * row by quoting that stamp. A library whose PChoice reads Indexed=true with no
 * stamp is reported as INDEXED, MOMENT NOT RECORDED and stays open.
 *
 * THE DESCRIPTION CONTROL IS ON PNumber, NOT ON PChoice, and the separation is
 * deliberate. PChoice's Description carries the stamp, so a control that wrote
 * a marker there and put it back would risk clobbering the one durable piece of
 * evidence this fixture holds.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. All of it files under `library.large-list`,
 * the scope for a document library past the list view threshold, except the
 * library-creation row which keeps the id the other library probes share.
 *
 *   library.large-list.fixture-multilevel-library-created
 *        Does the small pairing library exist?
 *   library.large-list.fixture-multilevel-columns-created
 *        Do MChoice, MFlag and MText exist on it and read back as their types?
 *   library.large-list.fixture-multilevel-file-count
 *        Does it hold all SMALL_FILES files?
 *   library.large-list.fixture-multilevel-values-written
 *        Do the sampled files read back holding the values the formulas give
 *        them?
 *   library.large-list.fixture-multilevel-under-threshold
 *        Is it still UNDER the threshold, which is the only reason it is worth
 *        pairing against, and does each of the three columns partition it?
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)?
 *   library.large-list.fixture-foldered-columns-created
 *        Do PChoice and PNumber exist on the large library and read back as the
 *        types they were asked for?
 *   library.large-list.control-foldered-description-sticks
 *        POSITIVE CONTROL: does a Description MERGE on a contract column read
 *        back? A field MERGE that silently did nothing would report the index
 *        write below as a column refusing an index.
 *   library.large-list.control-foldered-unknown-property-refused
 *        NEGATIVE CONTROL: is a MERGE naming a property SP.Field does not have
 *        refused? Without it, "the write was accepted" says nothing.
 *   library.large-list.fixture-foldered-folders-created
 *        Do the three folders exist at the library root, and does the endpoint
 *        that made them return the address they are at?
 *   library.large-list.fixture-foldered-index-written-under-threshold
 *        Was Indexed=true written on PChoice while the library held fewer than
 *        5,000 files, and does the flag read back true?
 *   library.large-list.fixture-foldered-witness-unindexed
 *        Does PNumber still read Indexed=false?
 *   library.large-list.fixture-foldered-file-count
 *        Does the library hold all TARGET_FILES files, counted from the newest
 *        file name rather than from ItemCount?
 *   library.large-list.fixture-foldered-files-in-folders
 *        Does each sampled file's FileDirRef name the folder its own number
 *        gives it, so the files are really in the folders and not at the root?
 *   library.large-list.fixture-foldered-folder-counts
 *        Does each folder hold fewer than 5,000 files while the library holds
 *        more, which is the whole inequality this fixture exists to present?
 *   library.large-list.fixture-foldered-values-written
 *        Do the sampled files read back holding the values the formulas give
 *        them?
 *   library.large-list.fixture-foldered-distribution
 *        Does the value distribution meet what the measurement probe depends
 *        on?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED. Every fixture row here is a
 * depends-on, because the whole probe is a fixture. What is nonetheless
 * OBSERVED and never asserted: what HTTP status the index MERGE comes back
 * with, what AutoIndexed reads afterwards, which of the two documented folder
 * spellings answered, what each folder's own ItemCount says, and how many
 * pastes the build took. Those are recorded in the evidence and no outcome
 * turns on any of them being a particular value. Folder ItemCount is on that
 * list for a specific reason: it is served from the same timer-job cache
 * `ItemCount` on a list is, so the folder-count row is decided on the file
 * numbering and on FileDirRef, and the cached figure is printed beside it.
 *
 * THE RESUME POINT IS THE NEWEST FILE NAME, NEVER ItemCount, and here it is
 * read past three folder rows. `ItemCount` lags a fresh upload burst by
 * minutes, so a resume computed from it re-uploads work that is already done
 * and reports a short library as complete once the cache catches up. The
 * complication a foldered library adds is that a folder IS an item, so
 * `$orderby=Id desc&$top=1` can return a folder rather than a file. The read
 * here therefore takes the newest few rows and walks them newest-first, taking
 * the first whose name is one of this fixture's files, skipping a row named
 * after one of the three folders, and FAILING CLOSED on anything else. The
 * folders are created before the first file, so their ids are the three lowest
 * in the library and a page of eight rows can only be all-folders on a library
 * holding nothing else.
 *
 * THE ORDERING IS Id, and past 5,000 items that is not a free choice.
 * `library-index-threshold-probe.js` measured on 2026-09-08 that a document
 * library past the threshold serves a selective filter on Id and refuses one on
 * Title, Name, Created, Modified, Author and Editor. A read that FAILS is fatal
 * here rather than falling back to zero: a fallback would restart the upload at
 * file one and quietly rewrite a fixture that was already correct.
 *
 * FileDirRef IS READ RATHER THAN ASSUMED, because a file uploaded to a folder
 * and a file uploaded to the root are the same file to everything else in this
 * probe. `library-nesting-probe.js` measured on 2026-09-08 that FileDirRef
 * reads back the containing folder's full server-relative path, so the sample
 * compares it against the folder the file's own number names.
 *
 * A BOUNDED RETRY ON THROTTLING, and only on the upload. Throttling on the way
 * to a fixture is weather rather than a finding, so an upload that comes back
 * 429 or 503 waits and is sent again a bounded number of times. Nothing else is
 * retried.
 *
 * THE BUILD IS RESUMABLE, and it has to be. Five and a half thousand serial
 * uploads from a browser console take a long time and the harness caps a run at
 * 900 s. So: BUILD_FIXTURE gates the upload, a run uploads at most UPLOAD_CAP
 * files across BOTH libraries and then reports how far it got, and each resume
 * point is READ rather than assumed. The small library is built first and draws
 * from the same cap, which costs the first paste a quarter of its budget and
 * means the pairing fixture is ready after one paste instead of after six.
 * Expect roughly six pastes in total.
 *
 * THERE IS NO CLEANUP PATH IN THIS PROBE, on purpose, which is the convention
 * both other fixture builders follow. The fixtures are the product. `resetList`
 * is never called and the harness CLEANUP flag is ignored with a message.
 * Removing either library is a separate deliberate act by an operator who has
 * decided the enumeration work is finished.
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
 *   File upload via `GetFolderByServerRelativeUrl(...)/Files/add(url=,overwrite=)`,
 *   folder creation via `GetFolderByServerRelativeUrl(...)/Folders/add(url=)`
 *   and `web/folders/add(...)`, and the item behind a file via
 *   `GetFileByServerRelativeUrl(...)/ListItemAllFields`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   The list view threshold this fixture is built to straddle, and the index
 *   guidance the ordering comes from:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 *
 * SCOPE OF CLAIMS: one tenant, two libraries, one caller context. The threshold
 * is documented as an effective figure rather than a constant, so the probe
 * that measures against these fixtures owns its own controls. This probe
 * establishes only that the fixtures are present, correct, foldered as
 * specified, and indexed under the threshold.
 *
 * HOW TO RUN
 *   1. Open a site you are willing to leave a permanent 5,256-file library and
 *      a permanent 240-file library on. It can be the same site that holds
 *      'dbmlsp Probe LargeLib' and 'dbmlsp Probe PreIndex'; this probe never
 *      touches either.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED, ALLOW_WRITES and BUILD_FIXTURE true. Paste. Expect a long
 *      run that stops at the upload cap.
 *   4. Re-paste until `library.large-list.fixture-foldered-file-count` reads
 *      PASS. Each paste resumes where the last one stopped. One of those pastes
 *      crosses file 4,900 and writes the index; read that transcript's
 *      `fixture-foldered-index-written-under-threshold` row carefully, because
 *      it is the one moment no later paste can re-observe.
 *   5. Copy the whole RESULTS block back verbatim, from every paste.
 *
 * WHEN FINISHED: nothing. Leave both fixtures in place, one indexed and one
 * not. An operator who clears PChoice's index, moves a file out of its folder
 * or tops the small library past 5,000 has destroyed what distinguishes these
 * libraries from the two that already existed.
 */
// finding: foldered-fixture-resume-read-walks-past-the-folder-rows - a folder
// is an item, so the `$orderby=Id desc&$top=1` read both flat fixture builders
// resume on returns a folder rather than a file on a foldered library, and
// those builders fail closed on a name they did not write. This one reads the
// newest few rows instead and takes the first that is one of its files,
// skipping a row named after one of its own three folders and failing closed on
// anything else. The folders are created before the first file, so a page of
// eight rows can only be all-folders on a library holding nothing else.
// finding: foldered-fixture-index-write-is-refused-at-or-past-the-threshold -
// the write is gated on a count READ at the moment it is sent, and a count at
// or past 5,000 stops the pass rather than indexing anyway. The guidance an
// operator meets says to index before the container grows past 5,000, so a
// fixture built to ask a folder-scoping question has to be indexed in that
// order too. A library indexed after crossing would differ from the flat
// fixtures in two ways at once, and the folder scoping could not be credited
// with anything. The gate reads the INDEX FLAG BEFORE THE COUNT for the reason
// the pre-index builder records: the intended end state is a library past 5,000
// with the index already on, and a gate that checked the count first reported
// the finished fixture as a fatal failure on every pass after the one that
// built it.
// finding: foldered-fixture-moment-is-stamped-because-a-later-pass-cannot-see-it
// - the build takes about six pastes and only one of them writes the index.
// Every pass after it sees Indexed=true and nothing else, which is equally
// consistent with an index written at 4,900 files and one written at 5,255. The
// observed count and an ISO timestamp are therefore written into PChoice's
// Description in the same pass as the index, and a later pass reports the row by
// quoting that stamp. Indexed=true with no stamp is reported open.
// finding: foldered-fixture-folder-membership-is-read-not-assumed - an upload
// addressed to a folder that silently landed at the root would produce a
// library with the right file count, the right column values and no folder
// scoping at all, and every row but one would still pass. So the sample reads
// FileDirRef back and compares it against the folder the file's own number
// names. library-nesting-probe.js measured on 2026-09-08 that FileDirRef
// carries the containing folder's full server-relative path.
// finding: foldered-fixture-folder-counts-are-computed-not-queried - the
// per-folder tally is computed over the file numbering rather than read from a
// folder's ItemCount, which is served from the same timer-job cache the list
// figure is and lags a burst by minutes. The cached figure is printed beside the
// row as an observation, and no outcome turns on it.
// finding: foldered-fixture-file-count-is-twelve-hundred-per-choice-per-folder -
// 5,256 is 12 x 438 and 12 is the wrap of the folder and choice formulas
// together, so each of the three folders holds exactly 438 files of each of the
// four PChoice values. A measurement probe can predict a folder-scoped
// group-by's bucket sizes without querying, and a bucket of the wrong size is
// then a finding rather than an argument about rounding.
// finding: foldered-fixture-small-library-moduli-are-coprime - MChoice, MFlag
// and MText wrap at 4, 3 and 5, which are pairwise coprime, so each level of a
// three-level group-by partitions what the level above it left and every
// combination of the three values is non-empty. Moduli sharing a factor would
// produce a second level that never splits a first-level group, and a
// three-level group-by that rendered as two would be indistinguishable from one
// the platform had refused a level of.
// finding: foldered-fixture-small-library-is-built-first - it is 240 files
// against 5,256 and it draws from the same per-paste cap, so building it first
// costs the opening paste a quarter of its budget and makes the pairing fixture
// ready after one paste rather than after six. The three-level control can then
// be measured while the large build is still running.
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

  log('INFO', 'probe revision cd01086f. Quote this when reporting results.');

  // The expensive half. Off, so a paste that only wants to check an
  // already-built fixture never starts five thousand uploads.
  const BUILD_FIXTURE = false;

  // ---- The contract ----------------------------------------------------
  // Read by the measurement probes that follow. See the header: changing any
  // of these invalidates the fixture rather than adjusting it.
  const LIB = 'dbmlsp Probe Foldered';
  const TARGET_FILES = 5256;
  const FOLDERS = ['Alpha-F', 'Beta-F', 'Gamma-F'];
  const PER_FOLDER = TARGET_FILES / FOLDERS.length;
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

  // The small pairing library. Under the threshold on purpose, and no index.
  const SMALL = 'dbmlsp Probe MultiLevel';
  const SMALL_FILES = 240;
  const M_CHOICE = 'MChoice';
  const M_FLAG = 'MFlag';
  const M_TEXT = 'MText';
  // 4, 3 and 5: pairwise coprime, so the three group-by levels cut the file
  // set independently. See the coprime-moduli finding.
  const M_TEXTS = 5;

  // ---- Run shape -------------------------------------------------------
  // At most this many files per paste ACROSS BOTH LIBRARIES, so a run is
  // bounded and an operator gets a progress report instead of a hung tab. The
  // pre-index builder measured that a two-column build of about this size fits
  // inside the 900 s run window; this one writes three columns on 240 of the
  // files and two on the rest, so the figure carries over.
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
  // How many rows the resume read takes. Enough that the three folder rows
  // cannot fill it, small enough to stay a cheap top-of-list read. See the
  // resume finding.
  const NEWEST_TOP = FOLDERS.length + 5;
  // The sample the large fixture's rows are decided on: every wrap boundary in
  // the formulas, both sides of the index write and of the threshold, and
  // enough of the first files to reach all three folders and all four choices.
  // A file number over the current count is dropped rather than read, so a
  // short build still reports a real sample.
  const SAMPLE = [1, 2, 3, 4, 5, 6, 7, 12, 13, 100, 101, 999, 1000, 1001,
                  INDEX_AT - 1, INDEX_AT, INDEX_AT + 1,
                  THRESHOLD, THRESHOLD + 1, TARGET_FILES];
  // The same idea on the small library, whose formulas wrap together at 60.
  const SMALL_SAMPLE = [1, 2, 3, 4, 5, 6, 15, 16, 30, 31, 60, 61, SMALL_FILES];

  const DESCRIPTION_MARKER = 'dbmlsp foldered fixture control marker';
  // A name SP.Field does not have. Deliberately not a near-miss of a real
  // property: the control asks whether an unknown name is refused, not whether
  // a typo is tolerated.
  const UNKNOWN_PROPERTY = 'NoSuchFieldPropertyAtAll';
  // The stamp the indexing pass leaves on PChoice, and the pattern a later
  // pass reads it back with. See the stamping finding.
  const STAMP_HEAD = 'dbmlsp foldered: Indexed:true written at ';
  const STAMP_RE = /dbmlsp foldered: Indexed:true written at (\d+) file\(s\) on (\S+)/;
  const stampFor = (held) => `${STAMP_HEAD}${held} file(s) on ${new Date().toISOString()}`;

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const lit = (value) => String(value).replace(/'/g, "''");
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const fileName = (n) => `dbmlsp-fld-${String(n).padStart(5, '0')}.txt`;
  const FILE_NUMBER = /dbmlsp-fld-(\d+)\.txt$/;
  const smallName = (n) => `dbmlsp-ml-${String(n).padStart(5, '0')}.txt`;
  const SMALL_NUMBER = /dbmlsp-ml-(\d+)\.txt$/;

  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const smallPath = `web/lists/getbytitle('${odataName(SMALL)}')`;
  const fieldPath = (listPath, name) =>
    `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  // Every value the fixture holds for one file, from the file's number alone.
  const wantedFor = (n) => ({
    choice: CHOICES[n % 4],
    number: n % 1000,
    folder: FOLDERS[n % FOLDERS.length],
  });
  const smallWantedFor = (n) => ({
    choice: CHOICES[n % 4],
    flag: n % 3 === 0,
    text: `mtext-${n % M_TEXTS}`,
  });

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB} holding`);
    log('INFO', `${TARGET_FILES} small text files spread over ${FOLDERS.length} folders`);
    log('INFO', `(${FOLDERS.join(', ')}), ${PER_FOLDER} files each, at most ${UPLOAD_CAP} files`);
    log('INFO', `per paste, and each carrying two columns: ${CHOICE} and ${NUMBER}.`);
    log('INFO', `It would MERGE Indexed=true onto ${CHOICE} once, after file ${INDEX_AT}`);
    log('INFO', `and before file ${INDEX_AT + 1}, and refuse to send it if the library is`);
    log('INFO', `already at or past ${THRESHOLD} files. ${NUMBER} is left unindexed.`);
    log('INFO', `It would also create a SECOND DOCUMENT LIBRARY '${SMALL}' holding`);
    log('INFO', `${SMALL_FILES} files at its root, no folders and no index, carrying`);
    log('INFO', `${M_CHOICE}, ${M_FLAG} and ${M_TEXT}: three levels for a group-by, on a`);
    log('INFO', `library deliberately far UNDER ${THRESHOLD} files.`);
    log('INFO', BUILD_FIXTURE
      ? 'BUILD_FIXTURE is ON: the upload would run.'
      : 'BUILD_FIXTURE is off: no file would be uploaded, no index would be written,');
    if (!BUILD_FIXTURE) {
      log('INFO', 'and the fixtures would be checked only as far as they are already built.');
    }
    log('INFO', "It does NOT touch 'dbmlsp Probe LargeLib' or 'dbmlsp Probe PreIndex'. Those");
    log('INFO', 'are different libraries with different column and file names, owned by');
    log('INFO', 'library-large-list-fixture-probe.js and the pre-index builder.');
    log('INFO', 'THESE FIXTURES ARE PERMANENT. There is no cleanup path in this probe, and');
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
    log('INFO', 'CLEANUP is on and is IGNORED here. This probe builds two fixtures that later');
    log('INFO', 'probes read, and emptying either is a separate deliberate act.');
  }

  expect('library.large-list.fixture-multilevel-library-created', `The small pairing library '${SMALL}' exists`);
  expect('library.large-list.fixture-multilevel-columns-created', `${M_CHOICE}, ${M_FLAG} and ${M_TEXT} exist on it and read back as their asked-for types`);
  expect('library.large-list.fixture-multilevel-file-count', `The small library holds ${SMALL_FILES} files, counted from the newest file name`);
  expect('library.large-list.fixture-multilevel-values-written', 'Every sampled small-library file reads back holding the values its file number gives it');
  expect('library.large-list.fixture-multilevel-under-threshold', `The small library is under ${THRESHOLD} files and each of its three columns partitions it`);
  expect('library.doc-lib.fixture-library-created', 'A document library is created (BaseTemplate 101)');
  expect('library.large-list.fixture-foldered-columns-created', `${CHOICE} and ${NUMBER} exist on the large library and read back as their asked-for types`);
  expect('library.large-list.control-foldered-description-sticks', 'POSITIVE CONTROL: a Description MERGE on a contract column reads back');
  expect('library.large-list.control-foldered-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused');
  expect('library.large-list.fixture-foldered-folders-created', `The ${FOLDERS.length} fixture folders exist at the large library's root`);
  expect('library.large-list.fixture-foldered-index-written-under-threshold', `Indexed=true was written on ${CHOICE} while the large library held fewer than ${THRESHOLD} files, and the flag reads back true`);
  expect('library.large-list.fixture-foldered-witness-unindexed', `${NUMBER} reads Indexed=false, so the measurement probe has an unindexed column to witness the throttle with`);
  expect('library.large-list.fixture-foldered-file-count', `The large library holds ${TARGET_FILES} files, counted from the newest file name`);
  expect('library.large-list.fixture-foldered-files-in-folders', "Every sampled file's FileDirRef names the folder its file number gives it");
  expect('library.large-list.fixture-foldered-folder-counts', `Each folder holds fewer than ${THRESHOLD} files while the library holds more`);
  expect('library.large-list.fixture-foldered-values-written', 'Every sampled file reads back holding the values its file number gives it');
  expect('library.large-list.fixture-foldered-distribution', `The large fixture holds more than ${THRESHOLD} files and each ${CHOICE} value selects a proper fraction of them`);

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

  const addField = async (listPath, schemaXml) => {
    digest = await getDigest();
    return spPost(`${listPath}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };

  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the WHOLE request, so a column missing one
  // property would read as a column that cannot be read at all.
  const readField = async (listPath, name) => spGet(fieldPath(listPath, name));

  // The verbose write, because `__metadata` is a verbose OData construct and
  // the harness's nometadata Content-Type REJECTS it rather than ignoring it:
  // threshold-index-probe.js lost a whole live run to exactly this, and
  // test_a_probe_sending_metadata_uses_verbose_odata pins the pairing.
  const mergeField = async (listPath, name, body, type) => {
    const fresh = await getDigest();
    return spPost(fieldPath(listPath, name), { __metadata: { type }, ...body }, fresh, {
      Accept: 'application/json;odata=verbose',
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };

  // Deliberately reuses the digest the loop holds rather than fetching one.
  // getDigest is a POST to /contextinfo that THROWS on failure, so refreshing
  // per file would add thousands of requests to the build and turn one bad
  // minute on the tenant into an unhandled rejection halfway through it. The
  // loop refreshes every DIGEST_EVERY files, which is the bound.
  const mergeItem = async (listPath, itemId, body) =>
    spPost(`${listPath}/items(${itemId})`, body, digest, {
      'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*',
    });

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

  // Create one column and read it back, returning what the row wants to print.
  // Says nothing about whether the result is good: the caller owns the verdict.
  //
  // NO SCHEMA HERE CARRIES AN INDEX. The index on PChoice is a separate,
  // deliberate write at INDEX_AT files, and creating the column pre-indexed
  // would answer the fixture's own question at file zero.
  const ensureColumn = async (listPath, name, schemaXml, wantedType) => {
    const before = await readField(listPath, name);
    const made = before.ok ? null : await addField(listPath, schemaXml);
    const read = before.ok ? before : await readField(listPath, name);
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

  const choiceXml = (name) => `<Field Type="Choice" DisplayName="${name}" Name="${name}">`
    + `<CHOICES>${CHOICES.map((choice) => `<CHOICE>${choice}</CHOICE>`).join('')}</CHOICES></Field>`;

  // ---- Reading the newest numbered file --------------------------------
  // The resume signal for both libraries, and never ItemCount. On the foldered
  // library a folder is an item too, so the newest few rows are walked
  // newest-first and a row named after one of this fixture's own folders is
  // skipped. Anything else fails closed. See the resume finding.
  const newestNumbered = async (listPath, pattern, skippable) => {
    const newest = await spGet(
      `${listPath}/items?$select=Id,FileLeafRef&$orderby=Id desc&$top=${NEWEST_TOP}`);
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
    const skipped = [];
    for (const row of rows) {
      const name = String(row.FileLeafRef || '');
      const digits = name.match(pattern);
      if (digits) {
        return {
          ok: true, number: Number(digits[1]), name,
          why: `${name} is the newest file`
            + (skipped.length ? `, past ${show(skipped)}` : ''),
        };
      }
      if (skippable.includes(name)) {
        skipped.push(name);
        continue;
      }
      return {
        ok: false, number: 0, name,
        why: `the newest ${rows.length} row(s) include ${show(name)}, which is neither one of `
          + "this fixture's file names nor one of its folders, so the library holds something "
          + 'this probe did not put there',
      };
    }
    // Every row was one of this fixture's folders. The folders are created
    // before the first file and NEWEST_TOP is larger than their number, so this
    // is a library holding folders and no files rather than a short read.
    return {
      ok: true, number: 0, name: null,
      why: `the library holds ${show(skipped)} and no file of this fixture's`,
    };
  };

  // ---- The small pairing library ---------------------------------------
  // Built first and from the same cap: 240 files against 5,256, so the pairing
  // fixture is ready after one paste. See the small-library-first finding.
  const M_SELECT = `Id,FileLeafRef,${M_CHOICE},${M_FLAG},${M_TEXT}`;
  const SMALL_CONTENT = 'dbml-sharepoint multilevel group-by fixture file. '
    + 'A small library on purpose. Read by the group-by probes.';

  // What is wrong with one small-library file, as a list of sentences. Empty
  // means correct. The Yes/No is compared as a truth value rather than as a
  // string, because it may render as a boolean or as its 1 or 0 and a string
  // comparison would report a rendering difference as a lost write.
  const smallMismatchesFor = (n, row) => {
    const want = smallWantedFor(n);
    const problems = [];
    if (row[M_CHOICE] !== want.choice) {
      problems.push(`${M_CHOICE}=${show(row[M_CHOICE])} wanted ${show(want.choice)}`);
    }
    const flag = row[M_FLAG];
    if (flag === null || flag === undefined || Boolean(flag) !== want.flag) {
      problems.push(`${M_FLAG}=${show(flag)} wanted ${show(want.flag)}`);
    }
    if (row[M_TEXT] !== want.text) {
      problems.push(`${M_TEXT}=${show(row[M_TEXT])} wanted ${show(want.text)}`);
    }
    return problems;
  };

  // How many files this paste has left to spend, across both libraries.
  let budget = UPLOAD_CAP;

  const buildMultiLevel = async () => {
    const MULTILEVEL_ROWS = [
      ['library.large-list.fixture-multilevel-columns-created', `${M_CHOICE}, ${M_FLAG} and ${M_TEXT} exist on it and read back as their asked-for types`],
      ['library.large-list.fixture-multilevel-file-count', `The small library holds ${SMALL_FILES} files, counted from the newest file name`],
      ['library.large-list.fixture-multilevel-values-written', 'Every sampled small-library file reads back holding the values its file number gives it'],
      ['library.large-list.fixture-multilevel-under-threshold', `The small library is under ${THRESHOLD} files and each of its three columns partitions it`],
    ];
    // ABORTED is open, not settled: this fixture did not build, so a re-paste
    // can clear every row it touches. The large library is built either way,
    // because the two fixtures answer different halves of the pairing.
    const abortSmall = (id, reason) => {
      let seen = false;
      for (const [rowId, question] of MULTILEVEL_ROWS) {
        if (rowId === id) seen = true;
        if (seen) record(rowId, question, 'ABORTED', reason);
      }
    };

    const container = await ensureContainer(smallPath, SMALL, 101,
      'dbml-sharepoint multilevel group-by fixture. Deliberately under 5,000 files, with '
      + 'three columns for a three-level group-by. Do not delete and do not grow.');
    record('library.large-list.fixture-multilevel-library-created',
           `The small pairing library '${SMALL}' exists`,
           container.id === null ? 'FAIL' : container.made === null ? 'ALREADY PRESENT' : 'PASS',
           container.made === null && container.id !== null
             ? `reusing '${SMALL}'. That is the intent here: the fixture is permanent and a `
               + 'second paste resumes the build rather than starting one'
             : container.note);
    if (container.id === null) {
      abortSmall('library.large-list.fixture-multilevel-columns-created',
                 `the small library was never created: ${container.note}`);
      return;
    }

    const columns = [
      [M_CHOICE, choiceXml(M_CHOICE), 'Choice'],
      [M_FLAG, `<Field Type="Boolean" DisplayName="${M_FLAG}" Name="${M_FLAG}"/>`, 'Boolean'],
      [M_TEXT, `<Field Type="Text" DisplayName="${M_TEXT}" Name="${M_TEXT}"/>`, 'Text'],
    ];
    const notes = [];
    let ready = true;
    for (const [name, schemaXml, wantedType] of columns) {
      const built = await ensureColumn(smallPath, name, schemaXml, wantedType);
      notes.push(built.note);
      if (!built.ok) ready = false;
    }
    record('library.large-list.fixture-multilevel-columns-created',
           `${M_CHOICE}, ${M_FLAG} and ${M_TEXT} exist on it and read back as their asked-for types`,
           ready ? 'PASS' : 'FAIL',
           `${notes.join('; ')}. None is indexed and none needs to be: this library is under `
           + `${THRESHOLD} files, which is the only reason it is worth pairing against.`);
    if (!ready) {
      abortSmall('library.large-list.fixture-multilevel-file-count',
                 'the small library\'s columns are not all present, so no file could be written '
                 + `correctly: ${notes.join('; ')}`);
      return;
    }

    // Read, never assembled. SharePoint derives a library's folder name from
    // its title at creation and the web may sit under /sites/<name>, so a path
    // built here would be a guess wearing an address's clothes.
    const rootRead = await spGet(`${smallPath}/RootFolder?$select=ServerRelativeUrl`);
    const root = (!readFailed(rootRead)) ? rootRead.body.ServerRelativeUrl : null;
    if (root === null) {
      abortSmall('library.large-list.fixture-multilevel-file-count',
                 `the small library's RootFolder did not read back (HTTP ${rootRead.status}), so `
                 + 'there is no address to upload to and its build never started');
      return;
    }

    const itemFor = async (n) => {
      const read = await spGet(
        `web/GetFileByServerRelativeUrl('${root}/${lit(smallName(n))}')`
        + `/ListItemAllFields?$select=${M_SELECT}`);
      return readFailed(read) ? null : read.body;
    };

    const resumeFrom = async () => {
      const newest = await newestNumbered(smallPath, SMALL_NUMBER, []);
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
      const back = await itemFor(newest.number);
      const problems = back === null
        ? ['the item did not read back']
        : smallMismatchesFor(newest.number, back);
      return {
        ok: true,
        from: problems.length === 0 ? newest.number + 1 : newest.number,
        held: newest.number,
        why: problems.length === 0
          ? `${newest.name} is the newest file and reads back complete`
          : `${newest.name} is the newest file and is incomplete (${problems.join(', ')}), so `
            + 'this run redoes it',
      };
    };

    const resume = await resumeFrom();
    if (!resume.ok) {
      abortSmall('library.large-list.fixture-multilevel-file-count', resume.why);
      return;
    }

    const buildNotes = [resume.why];
    let uploaded = 0;
    let stopReason = null;
    if (!BUILD_FIXTURE) {
      buildNotes.push('BUILD_FIXTURE is off, so nothing was uploaded this run');
    } else if (resume.from > SMALL_FILES) {
      buildNotes.push('the small fixture was already complete, so nothing was uploaded this run');
    } else {
      for (let n = resume.from; n <= SMALL_FILES && budget > 0; n += 1) {
        if (uploaded > 0 && uploaded % DIGEST_EVERY === 0) digest = await getDigest();
        let sent = null;
        for (let attempt = 0; attempt <= MAX_RETRIES; attempt += 1) {
          sent = await rawPost(
            `web/GetFolderByServerRelativeUrl('${root}')`
            + `/Files/add(url='${lit(smallName(n))}',overwrite=true)`, SMALL_CONTENT,
            { 'Content-Type': 'text/plain' });
          // Throttling on the way to a fixture is weather, not a finding.
          // Anything else is left unretried, because retrying a refusal
          // repeats it.
          if (sent.ok || (sent.status !== 429 && sent.status !== 503)) break;
          await sleep(RETRY_MS * (attempt + 1));
        }
        if (!sent.ok) {
          stopReason = `the upload of ${smallName(n)} returned HTTP ${sent.status}: `
            + `${clip(sent.text, 200)}`;
          break;
        }
        // Prefer the address SharePoint returned over one assembled from parts.
        const returned = sent.body && sent.body.ServerRelativeUrl
          ? sent.body.ServerRelativeUrl : null;
        const itemUrl = returned === null ? `${root}/${lit(smallName(n))}` : lit(returned);
        const idRead = await spGet(
          `web/GetFileByServerRelativeUrl('${itemUrl}')/ListItemAllFields?$select=Id`);
        if (readFailed(idRead) || typeof idRead.body.Id !== 'number') {
          stopReason = `${smallName(n)} uploaded but the item behind it did not read back `
            + `(HTTP ${idRead.status}), so its columns could not be written`;
          break;
        }
        const want = smallWantedFor(n);
        const wrote = await mergeItem(smallPath, idRead.body.Id, {
          [M_CHOICE]: want.choice,
          [M_FLAG]: want.flag,
          [M_TEXT]: want.text,
        });
        if (!wrote.ok) {
          stopReason = `the column write on ${smallName(n)} returned HTTP ${wrote.status}: `
            + `${clip(wrote.text, 200)}`;
          break;
        }
        uploaded += 1;
        budget -= 1;
      }
      buildNotes.push(`${uploaded} small-library file(s) built this run`);
      if (stopReason !== null) buildNotes.push(`the pass stopped: ${stopReason}`);
      if (budget === 0 && stopReason === null) {
        buildNotes.push(`the pass hit the shared per-run cap of ${UPLOAD_CAP}`);
      }
    }

    const after = await resumeFrom();
    const count = after.ok ? after.held : 0;
    const complete = after.ok && count >= SMALL_FILES && after.from > SMALL_FILES;
    record('library.large-list.fixture-multilevel-file-count',
           `The small library holds ${SMALL_FILES} files, counted from the newest file name`,
           // ABORTED rather than SHORT when the count could not be read at all:
           // SHORT would claim the library is short, which is a different thing
           // from not knowing how long it is.
           !after.ok ? 'ABORTED' : complete ? 'PASS' : 'SHORT',
           `${buildNotes.join('; ')}. `
           + (after.ok
             ? `The newest file is now number ${count} of the ${SMALL_FILES} wanted; ${after.why}`
             : after.why)
           + (complete
             ? '. The small fixture is built. Leave it in place and do not grow it.'
             : '. Re-paste with BUILD_FIXTURE = true until this reads PASS.'));

    const sampled = SMALL_SAMPLE.filter((n) => n <= count);
    const correct = [];
    const problems = [];
    for (const n of sampled) {
      const row = await itemFor(n);
      if (row === null) {
        problems.push(`${smallName(n)} did not read back`);
        continue;
      }
      const wrong = smallMismatchesFor(n, row);
      if (wrong.length) problems.push(`${smallName(n)}: ${wrong.join(', ')}`);
      else correct.push(smallName(n));
    }
    record('library.large-list.fixture-multilevel-values-written',
           'Every sampled small-library file reads back holding the values its file number gives it',
           problems.length ? 'FAIL'
             : sampled.length === 0 ? 'ABORTED'
               : complete ? 'PASS' : 'SHORT',
           `${sampled.length} of ${SMALL_SAMPLE.length} sample file(s) exist and were read back: `
           + `${show(sampled.map(smallName))}. `
           + (problems.length
             ? `mismatches: ${problems.join('; ')}`
             : sampled.length === 0
               ? 'No sample file exists yet, so nothing was compared and this says nothing '
                 + 'about what the fixture holds.'
               : 'every sampled file read back as its file number says it should. Correct: '
                 + `${show(correct)}`)
           + (complete || sampled.length === 0
             ? ''
             : '. The build is incomplete, so this reports the files uploaded so far.'));

    // Counted over the file numbers rather than queried. Every value is a pure
    // function of the file number, so the tally is exact for a library holding
    // files 1..count.
    const groups = {};
    for (let n = 1; n <= count; n += 1) {
      const want = smallWantedFor(n);
      const key = `${want.choice}/${want.flag}/${want.text}`;
      groups[key] = (groups[key] || 0) + 1;
    }
    const filled = Object.keys(groups).length;
    const wantedGroups = CHOICES.length * 2 * M_TEXTS;
    const sizes = Object.values(groups);
    const smallest = sizes.length ? Math.min(...sizes) : 0;
    const largest = sizes.length ? Math.max(...sizes) : 0;
    const partitions = filled === wantedGroups && smallest > 0 && largest < count;
    record('library.large-list.fixture-multilevel-under-threshold',
           `The small library is under ${THRESHOLD} files and each of its three columns partitions it`,
           count === 0 ? 'ABORTED'
             : complete && count < THRESHOLD && partitions ? 'PASS'
               : count >= THRESHOLD ? 'FAIL' : 'SHORT',
           `computed over the ${count} contiguously numbered file(s) the library holds. The three `
           + `columns take ${filled} of the ${wantedGroups} possible value combinations, holding `
           + `between ${smallest} and ${largest} file(s) each`
           + (count === 0
             ? '. The library holds no file of this fixture\'s yet, so neither the size nor the '
               + 'partition can be read off it.'
             : count < THRESHOLD
               ? `. The library is ${THRESHOLD - count} file(s) under ${THRESHOLD}, so a group-by `
               + 'sent at it is not sent past the list view threshold and a refusal there is '
               + 'about the shape of the query rather than the size of the container.'
               : `. The library is AT OR PAST ${THRESHOLD}, which destroys the only thing it was `
                 + 'built for. It cannot be the under-threshold half of the pair.'));
  };

  await buildMultiLevel();

  // ---- fixture-library-created -----------------------------------------
  const FOLDERED_ROWS = [
    ['library.large-list.fixture-foldered-columns-created', `${CHOICE} and ${NUMBER} exist on the large library and read back as their asked-for types`],
    ['library.large-list.control-foldered-description-sticks', 'POSITIVE CONTROL: a Description MERGE on a contract column reads back'],
    ['library.large-list.control-foldered-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused'],
    ['library.large-list.fixture-foldered-folders-created', `The ${FOLDERS.length} fixture folders exist at the large library's root`],
    ['library.large-list.fixture-foldered-index-written-under-threshold', `Indexed=true was written on ${CHOICE} while the large library held fewer than ${THRESHOLD} files, and the flag reads back true`],
    ['library.large-list.fixture-foldered-witness-unindexed', `${NUMBER} reads Indexed=false, so the measurement probe has an unindexed column to witness the throttle with`],
    ['library.large-list.fixture-foldered-file-count', `The large library holds ${TARGET_FILES} files, counted from the newest file name`],
    ['library.large-list.fixture-foldered-files-in-folders', "Every sampled file's FileDirRef names the folder its file number gives it"],
    ['library.large-list.fixture-foldered-folder-counts', `Each folder holds fewer than ${THRESHOLD} files while the library holds more`],
    ['library.large-list.fixture-foldered-values-written', 'Every sampled file reads back holding the values its file number gives it'],
    ['library.large-list.fixture-foldered-distribution', `The large fixture holds more than ${THRESHOLD} files and each ${CHOICE} value selects a proper fraction of them`],
  ];
  // ABORTED is open, not settled: the fixture did not build, so a re-paste can
  // clear every row this touches.
  const abortFrom = (id, reason) => {
    let seen = false;
    for (const [rowId, question] of FOLDERED_ROWS) {
      if (rowId === id) seen = true;
      if (seen) record(rowId, question, 'ABORTED', reason);
    }
    return report();
  };

  const library = await ensureContainer(libPath, LIB, 101,
    'dbml-sharepoint foldered large-library fixture. Over 5,000 files in three folders, '
    + 'each folder under 5,000, group-by column indexed below 5,000. Do not delete.');
  record('library.doc-lib.fixture-library-created',
         'A document library is created (BaseTemplate 101)',
         library.id === null ? 'FAIL' : library.made === null ? 'ALREADY PRESENT' : 'PASS',
         library.made === null && library.id !== null
           ? `reusing '${LIB}'. That is the intent here: the fixture is permanent and a `
             + 'second paste resumes the build rather than starting one'
           : library.note);
  if (library.id === null) {
    return abortFrom('library.large-list.fixture-foldered-columns-created',
                     `the fixture library was never created: ${library.note}`);
  }

  // ---- fixture-foldered-columns-created --------------------------------
  const COLUMNS = [
    [CHOICE, choiceXml(CHOICE), 'Choice'],
    [NUMBER, `<Field Type="Number" DisplayName="${NUMBER}" Name="${NUMBER}"/>`, 'Number'],
  ];

  const columnNotes = [];
  let columnsReady = true;
  for (const [name, schemaXml, wantedType] of COLUMNS) {
    const built = await ensureColumn(libPath, name, schemaXml, wantedType);
    columnNotes.push(built.note);
    if (!built.ok) columnsReady = false;
  }
  record('library.large-list.fixture-foldered-columns-created',
         `${CHOICE} and ${NUMBER} exist on the large library and read back as their asked-for types`,
         columnsReady ? 'PASS' : 'FAIL',
         `${columnNotes.join('; ')}. Neither schema asks for an index: the one on ${CHOICE} is `
         + `written separately at ${INDEX_AT} files.`);
  if (!columnsReady) {
    return abortFrom('library.large-list.control-foldered-description-sticks',
                     'the fixture columns are not both present, so no file could be written '
                     + `correctly and no index could be written: ${columnNotes.join('; ')}`);
  }

  // ---- control-foldered-description-sticks -----------------------------
  // The field MERGE itself, proved on a property whose readback is not in
  // doubt. A MERGE that silently does nothing would report the index write
  // below as a column refusing an index.
  //
  // On PNumber, not on PChoice: PChoice's Description carries this fixture's
  // one irreplaceable value.
  const priorRead = await readField(libPath, NUMBER);
  const priorDescription = readFailed(priorRead) ? null : priorRead.body.Description;
  const setDesc = await mergeField(libPath, NUMBER, { Description: DESCRIPTION_MARKER }, 'SP.Field');
  let descRead = await readField(libPath, NUMBER);
  let descReRead = false;
  const descriptionNow = () => (readFailed(descRead) ? null : descRead.body.Description);
  if (setDesc.ok && descriptionNow() !== DESCRIPTION_MARKER) {
    await sleep(REREAD_MS);
    descRead = await readField(libPath, NUMBER);
    descReRead = true;
  }
  const descSticks = setDesc.ok && descriptionNow() === DESCRIPTION_MARKER;
  record('library.large-list.control-foldered-description-sticks',
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
      libPath,
      NUMBER,
      { Description: priorDescription === null || priorDescription === undefined ? '' : priorDescription },
      'SP.Field');
    log(restored.ok ? 'OK' : 'FAIL',
        restored.ok
          ? `Description on ${NUMBER} put back to ${show(priorDescription)}.`
          : `Description on ${NUMBER} is still the control marker: the restore returned HTTP `
            + `${restored.status} ${clip(restored.text, 200)}`);
  }

  // ---- control-foldered-unknown-property-refused -----------------------
  const unknown = await mergeField(libPath, NUMBER, { [UNKNOWN_PROPERTY]: 'x' }, 'SP.Field');
  const unknownRefused = isRefusal(unknown.status);
  record('library.large-list.control-foldered-unknown-property-refused',
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

  // Read, never assembled, for the reason the small library's root is.
  const rootRead = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const rootUrl = (!readFailed(rootRead)) ? rootRead.body.ServerRelativeUrl : null;
  if (rootUrl === null) {
    return abortFrom('library.large-list.fixture-foldered-folders-created',
                     `the library RootFolder did not read back (HTTP ${rootRead.status}), so `
                     + 'there is no address to create folders under and the build never started');
  }

  // ---- fixture-foldered-folders-created --------------------------------
  // Before the first file, and that ordering is what lets the resume read walk
  // past them: created first, the three folders hold the three lowest ids in
  // the library. Two documented spellings are tried and the one that answered
  // is recorded, because which endpoint made a folder is observed here rather
  // than asserted; folder-probe.js owns that question.
  const ensureFolder = async (name) => {
    const path = `web/GetFolderByServerRelativeUrl('${lit(`${rootUrl}/${name}`)}')`;
    const found = await spGet(path);
    if (!readFailed(found) && typeof found.body.ServerRelativeUrl === 'string') {
      return { ok: true, url: found.body.ServerRelativeUrl, note: `${name}: already present` };
    }
    digest = await getDigest();
    let spelling = 'Folders/add(url=)';
    let made = await spPost(
      `web/GetFolderByServerRelativeUrl('${lit(rootUrl)}')/folders/add(url='${lit(name)}')`,
      {}, digest);
    if (!made.ok) {
      digest = await getDigest();
      spelling = 'web/folders/add';
      made = await spPost(`web/folders/add('${lit(`${rootUrl}/${name}`)}')`, {}, digest);
    }
    const back = await spGet(path);
    const url = (!readFailed(back) && typeof back.body.ServerRelativeUrl === 'string')
      ? back.body.ServerRelativeUrl : null;
    return {
      ok: url !== null,
      url,
      note: `${name}: ${spelling} returned HTTP ${made.status}`
        + (made.ok ? '' : ` ${clip(made.text, 160)}`)
        + `; it reads back at ${show(url)}`,
    };
  };

  const folderUrls = {};
  const folderNotes = [];
  let foldersReady = true;
  for (const name of FOLDERS) {
    const built = await ensureFolder(name);
    folderNotes.push(built.note);
    if (built.ok) folderUrls[name] = built.url;
    else foldersReady = false;
  }
  record('library.large-list.fixture-foldered-folders-created',
         `The ${FOLDERS.length} fixture folders exist at the large library's root`,
         foldersReady ? 'PASS' : 'FAIL',
         `${folderNotes.join('; ')}. Each address is READ back rather than assembled, because `
         + 'an upload sent to a folder that does not exist at the address this probe guessed '
         + 'would land at the root and produce a library with the right file count and no '
         + 'folder scoping at all.');
  if (!foldersReady) {
    return abortFrom('library.large-list.fixture-foldered-index-written-under-threshold',
                     `the fixture folders are not all present, so no file could be uploaded into `
                     + `one: ${folderNotes.join('; ')}`);
  }

  // ---- Reading one file back -------------------------------------------
  // FileDirRef is selected alongside the metadata columns because folder
  // membership is the thing this fixture adds and nothing else in the run
  // would notice a file that landed at the root. library-nesting-probe.js
  // measured on 2026-09-08 that it reads back the containing folder's full
  // server-relative path.
  const WRITTEN_SELECT = `Id,FileLeafRef,FileDirRef,${CHOICE},${NUMBER}`;

  // A file's item, addressed through the FILE. Direct addressing rather than a
  // $filter on FileLeafRef, which a library past the threshold refuses:
  // library-index-threshold-probe.js measured that on 2026-09-08.
  const itemFor = async (n) => {
    const read = await spGet(
      `web/GetFileByServerRelativeUrl('${folderUrls[wantedFor(n).folder]}/${lit(fileName(n))}')`
      + `/ListItemAllFields?$select=${WRITTEN_SELECT}`);
    return readFailed(read) ? null : read.body;
  };

  // What is wrong with one file's COLUMNS, as a list of sentences. Empty means
  // correct. Compared by VALUE rather than by string: a number may come back as
  // a number or as its decimal text, and a string comparison would report a
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

  // What is wrong with one file's FOLDER, separately, because the two say
  // different things: a column mismatch is a lost write and a folder mismatch
  // is a fixture that has no folder scoping to measure.
  const folderMismatchFor = (n, row) => {
    const wanted = folderUrls[wantedFor(n).folder];
    const held = row.FileDirRef;
    const path = held && typeof held === 'object' ? held.Url : held;
    if (typeof path !== 'string') {
      return `${fileName(n)}: FileDirRef read back ${show(held)}, which is not a path`;
    }
    return path === wanted
      ? null
      : `${fileName(n)}: FileDirRef=${show(path)} wanted ${show(wanted)}`;
  };

  const newestFile = async () => newestNumbered(libPath, FILE_NUMBER, FOLDERS);

  // ---- PChoice's index flag and its stamp -------------------------------
  const choiceState = async () => {
    const read = await readField(libPath, CHOICE);
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
  const preIndex = { outcome: null, evidence: null, state: null };
  const settleIndex = (outcome, evidence, state) => {
    preIndex.outcome = outcome;
    preIndex.evidence = evidence;
    preIndex.state = state || null;
    return outcome === 'PASS';
  };

  const writePreIndex = async () => {
    // THE FLAG IS READ BEFORE THE COUNT, and the order is not cosmetic. The
    // count check below refuses to write at or past THRESHOLD, and the
    // fixture's intended end state is a library that IS past THRESHOLD with the
    // index already on. Reading the count first would report the finished
    // fixture as a fatal failure on every pass after the one that built it.
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
        + `Indexed=${show(before.indexed)}. Nothing was written. An index sent now would differ `
        + 'from the flat fixtures in two ways at once, the ordering and the folders, and the '
        + 'folder scoping could not be credited with anything a measurement found. This library '
        + 'cannot become the foldered fixture: build a new one under a new name.');
    }

    const wrote = await mergeField(libPath, CHOICE, { Indexed: true }, 'SP.Field');
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
        + 'specified and a folder-scoped group-by measured on it could not be attributed to the '
        + 'index at all.',
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
    const stamped = await mergeField(libPath, CHOICE, { Description: stampText }, 'SP.Field');
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

  // ---- fixture-foldered-file-count -------------------------------------
  const CONTENT = 'dbml-sharepoint foldered large-library fixture file. '
    + 'Read by the folder-scoped beyond-5,000 probes.';

  const uploadOne = async (n) => {
    const into = folderUrls[wantedFor(n).folder];
    let attempt = 0;
    let last = null;
    while (attempt <= MAX_RETRIES) {
      last = await rawPost(
        `web/GetFolderByServerRelativeUrl('${into}')`
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

  // Where to resume: the newest file, and then that file's own values and
  // folder, because a file whose upload took and whose metadata MERGE did not
  // is the one gap a name-based resume would step over. Complete means resume
  // after it; incomplete means resume AT it, and overwrite=true redoes the
  // pair.
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
    const back = await itemFor(newest.number);
    const problems = back === null
      ? ['the item did not read back']
      : mismatchesFor(newest.number, back);
    if (back !== null) {
      const wrongFolder = folderMismatchFor(newest.number, back);
      if (wrongFolder !== null) problems.push(wrongFolder);
    }
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
    return abortFrom('library.large-list.fixture-foldered-index-written-under-threshold',
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
  } else if (budget <= 0) {
    buildNotes.push(`the small library used the whole per-run cap of ${UPLOAD_CAP} this pass`);
  } else {
    for (let n = resume.from; n <= TARGET_FILES && budget > 0; n += 1) {
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
      const itemUrl = returned === null
        ? `${folderUrls[wantedFor(n).folder]}/${lit(fileName(n))}`
        : lit(returned);
      const idRead = await spGet(
        `web/GetFileByServerRelativeUrl('${itemUrl}')/ListItemAllFields?$select=Id`);
      if (readFailed(idRead) || typeof idRead.body.Id !== 'number') {
        stoppedAt = n;
        stopReason = `${fileName(n)} uploaded but the item behind it did not read back `
          + `(HTTP ${idRead.status}), so its columns could not be written`;
        break;
      }
      const want = wantedFor(n);
      const wrote = await mergeItem(libPath, idRead.body.Id, {
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
      budget -= 1;
      // A spot check during the build, so a write that stops taking or an
      // upload that stops landing in its folder is caught at the next
      // checkpoint rather than at the end of a long run.
      if (n % VERIFY_EVERY === 0) {
        const back = await itemFor(n);
        const problems = back === null ? ['the item did not read back'] : mismatchesFor(n, back);
        if (back !== null) {
          const wrongFolder = folderMismatchFor(n, back);
          if (wrongFolder !== null) problems.push(wrongFolder);
        }
        if (problems.length) {
          stoppedAt = n;
          stopReason = `${fileName(n)} was written and read back ${problems.join(', ')}`;
          break;
        }
      }
      if (uploaded % PROGRESS_EVERY === 0) {
        log('INFO', `${uploaded} file(s) built this run; at ${fileName(n)} in `
                    + `${wantedFor(n).folder}.`);
      }
    }
    buildNotes.push(`${uploaded} file(s) built this run`);
    if (stoppedAt !== null) {
      buildNotes.push(`the pass stopped at ${fileName(stoppedAt)}: ${stopReason}`);
    } else if (budget <= 0) {
      buildNotes.push(`the pass hit the shared per-run cap of ${UPLOAD_CAP}`);
    }
  }

  // ---- fixture-foldered-index-written-under-threshold ------------------
  // The gate speaks for the pass that wrote the index. Every other pass reads
  // the flag and the stamp, and says which of the two it is reporting from.
  const INDEX_QUESTION = `Indexed=true was written on ${CHOICE} while the large library held fewer than ${THRESHOLD} files, and the flag reads back true`;
  const finalChoice = await choiceState();
  const afterBuild = await newestFile();
  const count = afterBuild.ok ? afterBuild.number : 0;
  if (preIndex.outcome !== null) {
    record('library.large-list.fixture-foldered-index-written-under-threshold',
           INDEX_QUESTION, preIndex.outcome, preIndex.evidence, preIndex.state);
  } else if (!finalChoice.ok) {
    record('library.large-list.fixture-foldered-index-written-under-threshold',
           INDEX_QUESTION, 'ABORTED',
           `${CHOICE} did not read back (HTTP ${finalChoice.status}), so neither its index flag `
           + 'nor the stamp beside it could be read this pass');
  } else if (finalChoice.indexed === true && finalChoice.stamp !== null) {
    record('library.large-list.fixture-foldered-index-written-under-threshold',
           INDEX_QUESTION,
           finalChoice.stamp.held < THRESHOLD ? 'PASS' : 'FAIL',
           `${CHOICE} reads Indexed=${show(finalChoice.indexed)}, `
           + `AutoIndexed=${show(finalChoice.auto)}, and carries the stamp `
           + `${show(finalChoice.stamp.text)} left by the pass that wrote it. The library held `
           + `${finalChoice.stamp.held} file(s) at that moment and holds ${count} now`
           + (finalChoice.stamp.held < THRESHOLD
             ? `. The write therefore landed ${THRESHOLD - finalChoice.stamp.held} file(s) under `
               + 'the threshold, which is the ordering the two flat fixtures can be compared '
               + 'against without the ordering itself being a second difference.'
             : `. That is AT OR PAST the ${THRESHOLD} the write had to be under, so a measurement `
               + 'on this library cannot attribute anything to the folders.'));
  } else if (finalChoice.indexed === true) {
    record('library.large-list.fixture-foldered-index-written-under-threshold',
           INDEX_QUESTION, 'INDEXED, MOMENT NOT RECORDED',
           `${CHOICE} reads Indexed=${show(finalChoice.indexed)} and its Description is `
           + `${show(clip(finalChoice.description, 200))}, which carries no stamp. The flag is `
           + 'there and nothing on the tenant says it was set under the threshold, so this pass '
           + 'cannot tell an index written at 4,900 files from one written at 5,255. Read the '
           + 'transcript of the pass that wrote it, and stamp the column by hand if that '
           + 'transcript confirms the count.',
           // Explicit: the classifier reads this head as settled, and the
           // question it asks was not answered.
           'open');
  } else if (count >= THRESHOLD) {
    record('library.large-list.fixture-foldered-index-written-under-threshold',
           INDEX_QUESTION, 'FAIL',
           `the library holds ${count} file(s), at or past ${THRESHOLD}, and ${CHOICE} reads `
           + `Indexed=${show(finalChoice.indexed)}. It crossed the threshold unindexed, so an `
           + 'index written now would differ from the flat fixtures in the ordering as well as '
           + 'in the folders. This library cannot become the foldered fixture: build a new one '
           + 'under a new name.');
  } else {
    record('library.large-list.fixture-foldered-index-written-under-threshold',
           INDEX_QUESTION, 'SHORT',
           `the library holds ${count} file(s) and ${CHOICE} reads `
           + `Indexed=${show(finalChoice.indexed)}. The index write is sent when the build `
           + `crosses ${INDEX_AT}, which this run has not reached. Re-paste with `
           + 'BUILD_FIXTURE = true.');
  }

  // ---- fixture-foldered-witness-unindexed ------------------------------
  // The measurement probe's negative control, checked on every pass because
  // threshold-index-probe.js watched SharePoint index a column on its own
  // between two runs. A witness that quietly acquired an index would let a
  // measurement run report everything served and conclude nothing.
  const witness = await readField(libPath, NUMBER);
  const witnessIndexed = readFailed(witness) || typeof witness.body.Indexed !== 'boolean'
    ? null : witness.body.Indexed;
  record('library.large-list.fixture-foldered-witness-unindexed',
         `${NUMBER} reads Indexed=false, so the measurement probe has an unindexed column to witness the throttle with`,
         witnessIndexed === null ? 'ABORTED' : witnessIndexed === false ? 'PASS' : 'FAIL',
         witnessIndexed === null
           ? `${NUMBER} did not read back an Indexed flag (HTTP ${witness.status})`
           : `${NUMBER}: Indexed=${show(witness.body.Indexed)}, `
             + `AutoIndexed=${show(witness.body.AutoIndexed)}`
             + (witnessIndexed === false
               ? '. Nothing in this probe indexes it, and a measurement run can use it as the '
                 + 'column that still throttles, at the root scope and inside a folder alike.'
               : '. The witness is indexed, so a measurement run against this fixture has no '
                 + 'column left to demonstrate the threshold with. Clear it before measuring.'));

  // ---- fixture-foldered-file-count -------------------------------------
  const after = await resumePoint();
  const complete = after.ok && count >= TARGET_FILES && after.from > TARGET_FILES;
  record('library.large-list.fixture-foldered-file-count',
         `The large library holds ${TARGET_FILES} files, counted from the newest file name`,
         // ABORTED rather than SHORT when the count could not be read at all:
         // SHORT would claim the library is short, which is a different thing
         // from not knowing how long it is.
         !after.ok ? 'ABORTED' : complete ? 'PASS' : 'SHORT',
         `${buildNotes.join('; ')}. `
         + (after.ok
           ? `The newest file is now number ${count} of the ${TARGET_FILES} wanted; ${after.why}`
           : after.why)
         + (complete
           ? '. The fixture is built. Leave it in place, indexed and foldered.'
           : '. Re-paste with BUILD_FIXTURE = true until this reads PASS. Each paste resumes '
             + 'where the last one stopped.'));

  // ---- The sample, read once and read by three rows ---------------------
  // Clamped to what exists, so a short build still reports a real sample rather
  // than a row of files that were never uploaded.
  const sampled = SAMPLE.filter((n) => n <= count);
  const valueNotes = [];
  const valueProblems = [];
  const folderNames = [];
  const folderProblems = [];
  for (const n of sampled) {
    const row = await itemFor(n);
    if (row === null) {
      valueProblems.push(`${fileName(n)} did not read back`);
      folderProblems.push(`${fileName(n)} did not read back`);
      continue;
    }
    const problems = mismatchesFor(n, row);
    if (problems.length) valueProblems.push(`${fileName(n)}: ${problems.join(', ')}`);
    else valueNotes.push(fileName(n));
    const wrongFolder = folderMismatchFor(n, row);
    if (wrongFolder !== null) folderProblems.push(wrongFolder);
    else folderNames.push(`${fileName(n)} in ${wantedFor(n).folder}`);
  }

  // ---- fixture-foldered-files-in-folders -------------------------------
  record('library.large-list.fixture-foldered-files-in-folders',
         "Every sampled file's FileDirRef names the folder its file number gives it",
         folderProblems.length ? 'FAIL'
           : sampled.length === 0 ? 'ABORTED'
             : complete ? 'PASS' : 'SHORT',
         `${sampled.length} of ${SAMPLE.length} sample file(s) exist and their FileDirRef was `
         + 'read back. '
         + (folderProblems.length
           ? `mismatches: ${folderProblems.join('; ')}. An upload that lands at the root produces `
             + 'a library with the right file count, the right column values and no folder '
             + 'scoping at all, so this row failing voids the fixture rather than blemishing it.'
           : sampled.length === 0
             ? 'No sample file exists yet, so no FileDirRef was compared and this says nothing '
               + 'about where the fixture\'s files sit.'
             : `every sampled file sits in the folder its number names: ${show(folderNames)}`)
         + (complete || sampled.length === 0
           ? ''
           : '. The build is incomplete, so this reports the files uploaded so far.'));

  // ---- fixture-foldered-folder-counts ----------------------------------
  // Counted over the file numbers rather than queried, for the reason the
  // folder-counts finding gives: a folder's own ItemCount is served from the
  // same timer-job cache the list figure is. The cached figures are read and
  // printed as an observation, and no outcome turns on them.
  const folderTally = {};
  for (const name of FOLDERS) folderTally[name] = 0;
  for (let n = 1; n <= count; n += 1) folderTally[wantedFor(n).folder] += 1;
  const folderSizes = FOLDERS.map((name) => folderTally[name]);
  const biggestFolder = folderSizes.length ? Math.max(...folderSizes) : 0;
  const smallestFolder = folderSizes.length ? Math.min(...folderSizes) : 0;
  const cached = [];
  for (const name of FOLDERS) {
    const read = await spGet(`web/GetFolderByServerRelativeUrl('${folderUrls[name]}')`);
    cached.push(`${name}=${readFailed(read) ? `unreadable HTTP ${read.status}` : show(read.body.ItemCount)}`);
  }
  const inequality = count > THRESHOLD && biggestFolder < THRESHOLD && smallestFolder > 0;
  record('library.large-list.fixture-foldered-folder-counts',
         `Each folder holds fewer than ${THRESHOLD} files while the library holds more`,
         count === 0 ? 'ABORTED'
           : inequality && complete ? 'PASS'
             : count > THRESHOLD && biggestFolder >= THRESHOLD ? 'FAIL'
               : 'SHORT',
         `computed over the ${count} contiguously numbered file(s) the library holds, each `
         + `uploaded to the folder its number names: ${show(folderTally)}. The library holds `
         + `${count} and the largest folder holds ${biggestFolder}`
         + (inequality
           ? `, so the library is over ${THRESHOLD} and every folder is under it, which is the `
             + 'inequality a folder-scoped query is measured against.'
           : `, which does not yet present the inequality: the library must be over ${THRESHOLD} `
             + 'and every folder under it.')
         + ` OBSERVED and not asserted, each folder's own cached ItemCount: ${cached.join(', ')}.`
         + ' That figure comes from the same timer-job cache the list count does and can lag a '
         + 'build by minutes, so nothing above turns on it.');

  // ---- fixture-foldered-values-written ---------------------------------
  record('library.large-list.fixture-foldered-values-written',
         'Every sampled file reads back holding the values its file number gives it',
         valueProblems.length ? 'FAIL'
           : sampled.length === 0 ? 'ABORTED'
             : complete ? 'PASS' : 'SHORT',
         `${sampled.length} of ${SAMPLE.length} sample file(s) exist and were read back: `
         + `${show(sampled.map(fileName))}. `
         + (valueProblems.length
           ? `mismatches: ${valueProblems.join('; ')}`
           : sampled.length === 0
             ? 'No sample file exists yet, so nothing was compared and this says nothing about '
               + 'what the fixture holds.'
             : 'every sampled file read back as its file number says it should. Correct: '
               + `${show(valueNotes)}`)
         + (complete || sampled.length === 0
           ? ''
           : '. The build is incomplete, so this reports the files uploaded so far.'));

  // ---- fixture-foldered-distribution -----------------------------------
  // Counted over the file numbers rather than queried. Every value is a pure
  // function of the file number, so the tally is exact for a library holding
  // files 1..count, and a query for it would be one a library past the
  // threshold refuses on an unindexed column anyway.
  const choiceTally = {};
  const pairTally = {};
  for (const choice of CHOICES) choiceTally[choice] = 0;
  for (let n = 1; n <= count; n += 1) {
    const want = wantedFor(n);
    choiceTally[want.choice] += 1;
    const key = `${want.folder}/${want.choice}`;
    pairTally[key] = (pairTally[key] || 0) + 1;
  }
  const choiceCounts = CHOICES.map((choice) => choiceTally[choice]);
  const smallest = choiceCounts.length ? Math.min(...choiceCounts) : 0;
  const largest = choiceCounts.length ? Math.max(...choiceCounts) : 0;
  const pairSizes = Object.values(pairTally);
  const pairsFilled = pairSizes.length;
  const evenPairs = pairsFilled === FOLDERS.length * CHOICES.length
    && Math.min(...pairSizes) === Math.max(...pairSizes);
  const selective = smallest > 0 && largest < count;
  const pastThreshold = count > THRESHOLD;
  record('library.large-list.fixture-foldered-distribution',
         `The large fixture holds more than ${THRESHOLD} files and each ${CHOICE} value selects a proper fraction of them`,
         pastThreshold && selective && complete ? 'PASS'
           : count === 0 ? 'ABORTED'
             : 'SHORT',
         `computed over the ${count} contiguously numbered file(s) the library holds. ${CHOICE}: `
         + `${show(choiceTally)}, so one value selects between ${smallest} and ${largest} of `
         + `${count}. ${NUMBER} takes ${Math.min(1000, count)} distinct value(s). Folder and `
         + `${CHOICE} together fill ${pairsFilled} of the `
         + `${FOLDERS.length * CHOICES.length} possible pairs: ${show(pairTally)}`
         + (evenPairs
           ? ', every one of them the same size, so a folder-scoped group-by has a bucket size a '
             + 'measurement probe can predict without querying.'
           : ', which are not all the same size yet; a complete build makes them equal.')
         + (pastThreshold
           ? ` The library is over ${THRESHOLD} files, so a query against it is sent past the `
             + 'list view threshold while a query scoped to one folder is not.'
           : ` The library is NOT over ${THRESHOLD} files, so a query against it is not past the `
             + 'threshold. Re-paste with BUILD_FIXTURE = true.'));

  report();
  log('INFO', `The fixture library '${LIB}' is left in place, with ${CHOICE} indexed,`);
  log('INFO', `${NUMBER} unindexed and its files in ${FOLDERS.join(', ')}.`);
  log('INFO', `The pairing library '${SMALL}' is left in place, under the threshold and`);
  log('INFO', 'unindexed. There is no cleanup path in this probe.');
  log('INFO', "It has not touched 'dbmlsp Probe LargeLib' or 'dbmlsp Probe PreIndex'.");
})();
