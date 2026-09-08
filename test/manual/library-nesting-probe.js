/**
 * dbml-sharepoint PROBE: HOW DOES A DOCUMENT LIBRARY NEST FOLDERS?
 *
 * REVISION: 722212ee
 *
 * ONE QUESTION, on the depth nothing has measured:
 *   `folder-probe.js` created ONE folder at the library root and settled what a
 *   folder is made of. `library-view-probe.js` grouped a view by folder at that
 *   same one level. Nothing has asked what the library or its view does when a
 *   folder holds a folder. A layout generator will emit folder structures, so
 *   the depth behaviour decides what an operator sees on the page.
 *
 * WHY: a view that shows only the direct children of the folder it is pointed
 * at, and a view that shows every file at every depth, are not variants of one
 * another. A generator that emits `a/b/c` and a default view that lists the
 * root folder alone would provision files nobody can see from the page they
 * were provisioned for, and every deploy phase would pass. Nothing in the build
 * or the deploy can observe a rendered view, so the depth behaviour has to be
 * measured on a live site or it is not known.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. The folder questions file under
 * `library.folder.*` beside the six rows `folder-probe.js` holds there. The two
 * grouping CONTROLS keep the ids `library-grouping-probe.js` registers for the
 * same questions by the same method, because one question with two records is
 * one id.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)? The same
 *        question by the same method as `folder-probe.js` and the rest, so it
 *        keeps their id.
 *   library.folder.control-missing-parent-refused
 *        NEGATIVE CONTROL: is a folder creation addressed at a PARENT that does
 *        not exist refused? Without it a folder creation that quietly did
 *        nothing would read the same as one that worked, and the nesting rows
 *        would be about this probe rather than about SharePoint.
 *   library.folder.fixture-nested-folders-created
 *        Do the three folders exist, and does each one read back at the nested
 *        path it was asked for rather than beside its parent? Asked of folders
 *        THIS run created: the ladder is recycled before it is built, and a
 *        folder that survives that is recorded rather than built on.
 *   library.folder.fixture-files-placed
 *        Do the four files exist at the three depths they were uploaded to, and
 *        does each read back holding the choice value written to it?
 *   library.folder.nesting-depth
 *        Can the library hold `a/b/c`, and does the folder endpoint accept
 *        creating a folder whose parent is a folder? Records WHICH endpoint
 *        spelling answered, because Learn documents three and a tenant is not
 *        obliged to accept all of them.
 *   library.folder.file-in-nested-folder
 *        Can a file be uploaded into a folder three deep through the ordinary
 *        `Files/add` path, and do `FileRef` and `FileDirRef` read back carrying
 *        the nested path?
 *   library.folder.view-flattens-depth
 *        Does a view show files at any depth, or only the direct children of
 *        the folder it is pointed at? Asked once per documented `Scope` value
 *        and once with the attribute absent.
 *   library.view.control-missing-group-column-ungrouped
 *        NEGATIVE CONTROL: does a group-by naming a column that does not exist
 *        come back UNGROUPED? A group-by is never refused, so the discriminator
 *        is the shape of the answer. Same question, same method, same id as
 *        `library-grouping-probe.js`.
 *   library.view.control-group-by-single-value-column
 *        POSITIVE CONTROL: group-by on the single-value Choice column, the case
 *        already measured working on a library. It proves THIS probe can read
 *        the shape of a group that works, and it records what a working group
 *        row looks like on a library that holds nested folders.
 *   library.folder.group-by-path-depth
 *        A file three deep, in a view grouped by the folder path column. Does
 *        it group under the FULL path, under the LEAF folder name, or under the
 *        TOP folder of its branch? What does the group label carry?
 *   library.folder.nesting-with-metadata-group-by
 *        A view grouped by a metadata column on a library that also holds
 *        nested folders. Do the folder dimension and the metadata dimension
 *        compose, or does one clobber the other?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the library exists; the choice column
 *   exists and reads back as a Choice; a folder creation addressed at a parent
 *   that does not exist is refused; the three folders read back at their nested
 *   paths; the four files read back at the depths they were uploaded to holding
 *   the values written to them; a group-by naming a missing column comes back
 *   in the same shape as the same query with no group-by at all; a group-by on
 *   the single-value column returns group rows this probe can read.
 *   Observes (recorded, never asserted): which endpoint spelling created a
 *   folder under a folder; what `FileRef` and `FileDirRef` carry for a file
 *   three deep; how many rows each `Scope` value returns and which files are
 *   among them; whether a group-by on the path column is honoured, and what its
 *   labels carry; whether a two-field group-by groups by one field, both, or
 *   neither. NOTHING here asserts that a view flattens, that it does not, or
 *   that a library groups by folder path at all. A run where every group-by is
 *   ignored is a successful run with an important answer.
 *
 * HOW A GROUPING IS READ. Each grouped question sends the SAME query three
 * times and varies only the grouping: collapsed, expanded, and with no
 * `<GroupBy>` at all. The third is the flat shape the first two are compared
 * against, measured in this run rather than assumed to be one row per file. See
 * the inherited findings below for the two live runs that taught this.
 *
 * ABORTED VERSUS VOID. A fixture that never built records ABORTED downstream,
 * which is open: a re-run can clear it. A control that did not hold records the
 * observation it made and marks the row void, because on this site, by this
 * method, the row cannot be answered however many times it is re-run.
 *
 * MICROSOFT LEARN CITATIONS. Every URL and attribute below is one Learn
 * documents rather than one assembled from memory, because a wrong spelling
 * returns 404, `isRefusal` counts 404 as a refusal, and the probe would then
 * print a claim about SharePoint that was really a typo:
 *
 *   List and library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   `FolderCollection.Add`, spelled `/add(url)`, whose own example adds
 *   `/Shared Documents/Folder A/Folder B`, a folder whose parent is a folder,
 *   and the `Folders` and `ParentFolder` properties of a Folder:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Folder creation by POST to `web/folders` with a `ServerRelativeUrl`:
 *     "Working with folders and files with REST"
 *   File upload via `Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   The `Scope` attribute of `<View>`, whose documented values are `FilesOnly`
 *   (files of a specific folder), `Recursive` (all files of all folders) and
 *   `RecursiveAll` (all files and all subfolders of all folders), and whose
 *   absence displays "only the files and subfolders of a specific folder":
 *     "View element (List)"
 *   Grouping a query, and the `Collapse` attribute:
 *     "GroupBy element (Query)"
 *   Reading a view's rows without opening the page:
 *     "SP.List.renderListDataAsStream method"
 *   Pointing that read at one folder, which this probe does not need but a
 *   reader of these results will:
 *     "RenderListDataParameters.FolderServerRelativeUrl Property"
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the library it created. Recycling the library takes the
 * folders and their files with it.
 */
// finding: library-nesting-a-group-by-is-never-refused - inherited from
// library-grouping-probe.js, whose first live run on 2026-09-08 sent a
// <GroupBy> naming a column that does not exist and got HTTP 200 back with flat
// rows. The discriminator a group-by needs is not refused against accepted but
// HONOURED against IGNORED: an honoured group-by returns rows carrying the
// markers `<Field>.COUNT.group`, `<Field>.newgroup` and `<Field>.groupindex`,
// and an ignored one returns the rows the same query returns with no <GroupBy>
// at all. Every grouped question here sends both queries for that reason.
// finding: library-nesting-a-collapsed-row-carries-no-file-name - inherited
// from library-grouping-probe.js, second live run 2026-09-08: a collapsed
// query's rows did not carry the FileLeafRef its ViewFields named, the first
// being `{"PreviewThumbnailsQualitySets":""}`. Nothing here reads a file name
// off a collapsed row, and no verdict is a clause about one.
// finding: library-nesting-client-side-partition-is-not-evidence - inherited
// from library-grouping-probe.js: a probe that sends a grouped query, gets flat
// rows back and sorts them into buckets by reading each row's value has
// measured its own arithmetic. Every observation reasoned from here is
// server-produced: the collapsed query's rows and their keys, and the row count
// of the same query sent with no <GroupBy>.
// finding: library-nesting-two-group-by-fields-are-undocumented - "GroupBy
// element (Query)" documents one FieldRef child and says nothing about a
// second, so the composition question is an experiment rather than a check of
// documented behaviour. The row records what came back and names no expected
// answer, and a run where the second field is dropped is a successful run.
// finding: library-nesting-folder-is-not-a-column - library-view-probe.js
// grouped by `<FieldRef Name="Folder"/>`, which is not a column a library
// holds. This probe groups by the parent-folder column and READS THAT COLUMN
// BACK first, because a group-by over a column the library does not hold is the
// negative control rather than a measurement.
// finding: library-nesting-a-folder-read-answers-for-a-folder-that-is-not-there
// - first live run 2026-09-08, revision 3937f7ae, against a library this run
// had just created, so no ladder folder could have been in it. A read of
// `GetFolderByServerRelativeUrl('<library root>/nestlevel-alpha')?$select=Exists`
// answered HTTP 200 at all three levels, and the negative control's read of
// `?$select=Exists,ServerRelativeUrl` answered HTTP 200 for a folder under a
// parent that does not exist. The same three folders, read with
// `$select=Name,ServerRelativeUrl,Exists,ItemCount`, returned 404. HTTP ok is
// therefore not presence on this surface. folderIsThere() below reads the body
// rather than the status, and is right whichever way a tenant answers.
// finding: library-nesting-a-dirty-fixture-aborts-the-probe - the same run
// recorded 3 settled, 1 failed and 7 aborted. Reading HTTP 200 as presence sent
// all three folder creations down an "already present" path, so nothing was
// built, the ladder read back 404, and every question under the fixture
// aborted. The negative control failed the same way, reporting REFUSED, BUT THE
// FOLDER EXISTS about a folder that was not there. Two changes, because either
// alone leaves the failure available: the ladder and the control's folders are
// RECYCLED before anything is built, so a folder an earlier run left cannot
// answer this run's question, and the reuse path is gone, so a folder still
// present after the reset is recorded rather than built on. A fixture that
// reuses what it finds measures the previous run.
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

  log('INFO', 'probe revision 722212ee. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibNest';
  const COL = 'NestChoice';
  // Never created. The negative control names it, and a run that finds this
  // column present would be reading somebody else's column.
  const MISSING = 'NestNoSuchColumnAtAll';
  // The parent-folder column a library holds. Read back before anything groups
  // by it. See the folder-is-not-a-column finding above.
  const PATH_COL = 'FileDirRef';
  // Three distinct tokens, and no one of them a substring of another, so a
  // group label naming the full path, the leaf folder and the top folder are
  // three different string tests rather than one ambiguous one.
  const LEVELS = ['nestlevel-alpha', 'nestlevel-bravo', 'nestlevel-charlie'];
  // Never created either. The folder negative control addresses it as a parent.
  const MISSING_PARENT = 'nestlevel-never-created';
  const CHOICES = ['Alpha', 'Beta'];
  const ROW_LIMIT = 50;
  // Every documented value of the View Scope attribute, and the attribute
  // absent, which Learn documents as its own behaviour rather than a default
  // spelling of one of the three.
  const SCOPES = [null, 'FilesOnly', 'Recursive', 'RecursiveAll'];
  // The scope every grouped query runs at. A grouping question asked at a scope
  // that returns only the root folder's files would report the scope.
  const DEEP_SCOPE = 'RecursiveAll';
  // Named once: each control's question is quoted in more than one place, and
  // two spellings of one question is how a summary stops matching a row.
  const Q = {
    library: 'A document library is created (BaseTemplate 101)',
    missingParent: 'NEGATIVE CONTROL: a folder creation addressed at a parent folder that does not exist is refused',
    folders: 'The three folders exist and read back at the nested paths they were asked for',
    files: 'The four files exist at the depths they were uploaded to, holding the values written to them',
    depth: 'Can the library hold a folder three deep, and which endpoint spelling creates a folder under a folder?',
    nestedFile: 'Does a file upload into a folder three deep, and do FileRef and FileDirRef carry the nested path?',
    flatten: 'Does a view show files at any depth or only the direct children of one folder, and what does each Scope value return?',
    ungrouped: 'NEGATIVE CONTROL: a group-by naming a column that does not exist comes back ungrouped, in the shape the same query returns with no group-by',
    grouped: 'POSITIVE CONTROL: a group-by on a single-value Choice column returns group rows this probe can read',
    pathDepth: 'Group-by on the folder path with a file three deep: the full path, the leaf folder, or the top folder?',
    compose: 'A metadata group-by on a library holding nested folders: do the two dimensions compose, or does one clobber the other?',
  };

  // Four files over three depths and two choice values, so that no candidate
  // answer is the same shape as another:
  //   the metadata groups SPAN depths (Alpha at the root and three deep)
  //   the deepest folder holds BOTH values, so a folder group is not a
  //   metadata group by coincidence
  //   the root holds one file, so a view showing only direct children returns
  //   a row count nothing else produces
  const FILES = [
    { name: 'dbmlsp-nest-root.txt', depth: 0, choice: 'Alpha' },
    { name: 'dbmlsp-nest-one.txt', depth: 1, choice: 'Beta' },
    { name: 'dbmlsp-nest-three-alpha.txt', depth: 3, choice: 'Alpha' },
    { name: 'dbmlsp-nest-three-beta.txt', depth: 3, choice: 'Beta' },
  ];

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, with a Choice`);
    log('INFO', `column '${COL}', then the folders '${LEVELS[0]}',`);
    log('INFO', `'${LEVELS[0]}/${LEVELS[1]}' and '${LEVELS.join('/')}' through the`);
    log('INFO', `folder endpoint, and ${FILES.length} small text files at three depths.`);
    log('INFO', 'Would then read the library back through one query per documented');
    log('INFO', 'View Scope value, and send grouped queries over the folder path');
    log('INFO', 'column, the choice column, and the two together.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first, with its folders.`);
    } else {
      log('INFO', `CLEANUP is off: an existing '${LIB}' would be reused. Set`);
      log('INFO', 'CLEANUP = true to start from no library at all.');
    }
    log('INFO', `Either way, the folders '${LEVELS[0]}' and '${MISSING_PARENT}'`);
    log('INFO', 'inside that library are RECYCLED before the ladder is built,');
    log('INFO', 'because a ladder built on leftovers measures the previous run.');
    log('INFO', 'They are restorable from the site recycle bin.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('library.doc-lib.fixture-library-created', Q.library);
  expect('library.folder.control-missing-parent-refused', Q.missingParent);
  expect('library.folder.fixture-nested-folders-created', Q.folders);
  expect('library.folder.fixture-files-placed', Q.files);
  expect('library.folder.nesting-depth', Q.depth);
  expect('library.folder.file-in-nested-folder', Q.nestedFile);
  expect('library.folder.view-flattens-depth', Q.flatten);
  expect('library.view.control-missing-group-column-ungrouped', Q.ungrouped);
  expect('library.view.control-group-by-single-value-column', Q.grouped);
  expect('library.folder.group-by-path-depth', Q.pathDepth);
  expect('library.folder.nesting-with-metadata-group-by', Q.compose);

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);

  let digest = await getDigest();

  // A raw request body, not JSON: Files/add takes the file's bytes.
  const rawPost = async (path, body, extraHeaders = {}) => {
    digest = await getDigest();
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

  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the WHOLE request, so a column missing one
  // property would read as a column that cannot be read at all.
  const readField = async (name) =>
    spGet(`${libPath}/fields/getbyinternalnameortitle('${odataName(name)}')`);

  const mergeItem = async (itemId, body) => {
    digest = await getDigest();
    return spPost(`${libPath}/items(${itemId})`, body, digest, {
      'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*',
    });
  };

  // ---- fixture-library-created -----------------------------------------
  await resetList(LIB);

  const found = await spGet(libPath);
  let libraryReady = found.ok;
  if (found.ok) {
    record('library.doc-lib.fixture-library-created', Q.library, 'ALREADY PRESENT',
           'reusing an existing library. Set CLEANUP = true for a clean answer');
  } else {
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: LIB, BaseTemplate: 101,
      Description: 'dbml-sharepoint library-nesting probe library. Safe to delete.',
    }, digest);
    libraryReady = made.ok;
    record('library.doc-lib.fixture-library-created', Q.library,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${clip(made.text, 300)}`);
  }

  // Everything this probe measures, so an abort can report the truth about all
  // of it rather than about the rows it happened to reach.
  const MEASUREMENTS = [
    ['library.folder.nesting-depth', Q.depth],
    ['library.folder.file-in-nested-folder', Q.nestedFile],
    ['library.folder.view-flattens-depth', Q.flatten],
    ['library.view.control-missing-group-column-ungrouped', Q.ungrouped],
    ['library.view.control-group-by-single-value-column', Q.grouped],
    ['library.folder.group-by-path-depth', Q.pathDepth],
    ['library.folder.nesting-with-metadata-group-by', Q.compose],
  ];
  // ABORTED is open, not void: the fixture never built, so no question was
  // asked, and a re-run can clear every row this touches.
  const abortEverything = (reason) => {
    for (const [id, question] of MEASUREMENTS) {
      record(id, question, 'ABORTED', reason);
    }
    return report();
  };

  if (!libraryReady) {
    record('library.folder.control-missing-parent-refused', Q.missingParent,
           'ABORTED', 'the library was never created, so no folder was addressed');
    record('library.folder.fixture-nested-folders-created', Q.folders,
           'ABORTED', 'the library was never created');
    record('library.folder.fixture-files-placed', Q.files,
           'ABORTED', 'the library was never created');
    return abortEverything('the scratch library was never created');
  }

  const root = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (!readFailed(root)) ? root.body.ServerRelativeUrl : null;
  if (folderUrl === null) {
    record('library.folder.control-missing-parent-refused', Q.missingParent,
           'ABORTED', `the library RootFolder did not read back (HTTP ${root.status})`);
    record('library.folder.fixture-nested-folders-created', Q.folders,
           'ABORTED', `the library RootFolder did not read back (HTTP ${root.status})`);
    record('library.folder.fixture-files-placed', Q.files,
           'ABORTED', 'no folder path was known, so no file was uploaded');
    return abortEverything('the library RootFolder did not read back, so no path was known');
  }

  // The server-relative path of the folder `depth` levels down the ladder.
  const pathAt = (depth) => (depth === 0
    ? folderUrl
    : `${folderUrl}/${LEVELS.slice(0, depth).join('/')}`);

  // Is a folder THERE? Not "did the endpoint answer": see the folder-read
  // finding above, where a read of a folder that could not be there came back
  // HTTP 200. Both signals in the body are taken, because the live run recorded
  // the 404 only for the select naming Name and ItemCount. A folder is there
  // when the body carries a Name and does not say Exists is false, which is
  // right whether a tenant refuses the read or answers it.
  const readFolder = async (path) => spGet(
    `web/GetFolderByServerRelativeUrl('${path}')`
    + '?$select=Name,ServerRelativeUrl,Exists,ItemCount');
  const folderIsThere = (read) => !readFailed(read)
    && read.body.Name !== undefined && read.body.Exists !== false;

  // Both spellings folder-probe.js tries, in its order. RECYCLED rather than
  // deleted, so anything this clears is restorable from the site recycle bin.
  const recycleFolder = async (path) => {
    digest = await getDigest();
    const gone = await spPost(
      `web/GetFolderByServerRelativeUrl('${path}')/recycle`, {}, digest);
    if (gone.ok) return gone;
    digest = await getDigest();
    return spPost(`web/GetFolderByServerRelativeUrl('${path}')/recycle()`, {}, digest);
  };

  // ---- Pre-run reset of the folder ladder ------------------------------
  // The library outlives a run, whether CLEANUP is off or an earlier run left
  // it behind, and so do the folders in it. See the dirty-fixture finding
  // above. Only the folders NAMED here are touched, nothing is enumerated, and
  // the deepest goes first so that no row rests on a recycle taking children
  // with it. The control's two folders are cleared as well: a leftover there
  // makes a refusal and a read-back contradict each other.
  const stalePaths = [];
  for (let level = LEVELS.length; level >= 1; level -= 1) stalePaths.push(pathAt(level));
  stalePaths.push(`${pathAt(0)}/${MISSING_PARENT}/${LEVELS[0]}`);
  stalePaths.push(`${pathAt(0)}/${MISSING_PARENT}`);
  const resetNotes = [];
  for (const path of stalePaths) {
    if (!folderIsThere(await readFolder(path))) continue;
    const gone = await recycleFolder(path);
    resetNotes.push(`'${path}' was left by an earlier run: recycle HTTP `
      + `${gone.status}, and it now reads `
      + `${folderIsThere(await readFolder(path)) ? 'STILL PRESENT' : 'absent'}`);
  }
  if (resetNotes.length === 0) {
    resetNotes.push('no folder from an earlier run was found to clear');
  }

  // ---- control-missing-parent-refused: NEGATIVE CONTROL ----------------
  // Addressed at a parent that was never created, and named so that the ladder
  // below cannot create it later. The FolderCollection spelling is used rather
  // than the full-path one because Learn's own full-path example spans two
  // levels, so a full-path create under a missing parent could legitimately
  // succeed by creating both, which would be a finding and not a control.
  // Read BEFORE the create as well as after. A folder already sitting at the
  // path makes the refusal and the read-back contradict each other, and that
  // contradiction reads exactly like SharePoint refusing a create it performed
  // anyway. It is a leftover, so the row records it and voids rather than
  // reporting a SharePoint that does two things at once.
  const orphanPath = `${pathAt(0)}/${MISSING_PARENT}/${LEVELS[0]}`;
  const orphanBefore = await readFolder(orphanPath);
  const orphanWasThere = folderIsThere(orphanBefore);
  digest = await getDigest();
  const orphan = await spPost(
    `web/GetFolderByServerRelativeUrl('${pathAt(0)}/${MISSING_PARENT}')`
    + `/folders/add(url='${LEVELS[0]}')`, {}, digest);
  const orphanBack = await readFolder(orphanPath);
  const orphanIsThere = folderIsThere(orphanBack);
  const folderControlHeld = !orphanWasThere && !orphan.ok
    && isRefusal(orphan.status) && !orphanIsThere;
  record('library.folder.control-missing-parent-refused', Q.missingParent,
         orphanWasThere
           ? 'DIRTY FIXTURE, THE FOLDER WAS THERE BEFORE THE CREATE'
           : orphan.ok
             ? 'FAIL'
             : isRefusal(orphan.status)
               ? (orphanIsThere ? 'REFUSED, BUT THE FOLDER EXISTS' : 'PASS')
               : 'NOT ESTABLISHED',
         `${resetNotes.join('; ')}. A folder creation under '${MISSING_PARENT}', `
         + `which this probe never creates, returned HTTP ${orphan.status}`
         + (orphan.ok ? '' : `: ${clip(orphan.text, 220)}`)
         + `; the folder it would have made read HTTP ${orphanBefore.status} as `
         + `${clip(show(orphanBefore.body), 200)} before the create and HTTP `
         + `${orphanBack.status} as ${clip(show(orphanBack.body), 200)} after. `
         + (orphanWasThere
           ? 'The folder was there BEFORE the create, so this run cannot read the '
             + 'read-back as a consequence of the create. The row records what it saw '
             + 'and is void: the reset could not clear a folder an earlier run left.'
           : orphan.ok
             ? 'A creation addressed at a parent that does not exist was ACCEPTED, so '
               + 'this probe cannot tell a folder it created from one it did not, and the '
               + 'nesting rows are void whichever way they go.'
             : isRefusal(orphan.status) && !orphanIsThere
               ? 'A failed folder creation is observable, so a nesting row below is about '
                 + 'SharePoint rather than about this probe.'
               : 'Neither signature: the refusal was not the server rejecting the '
                 + 'content, or the folder exists anyway.'),
         orphanWasThere ? 'void' : undefined);

  // ---- fixture: the choice column --------------------------------------
  const notes = [];
  const beforeCol = await readField(COL);
  let madeCol = null;
  if (!beforeCol.ok) {
    digest = await getDigest();
    madeCol = await spPost(`${libPath}/fields/createfieldasxml`, {
      parameters: {
        SchemaXml: `<Field Type="Choice" DisplayName="${COL}" Name="${COL}">`
          + `<CHOICES>${CHOICES.map((c) => `<CHOICE>${c}</CHOICE>`).join('')}</CHOICES></Field>`,
        Options: 8,
      },
    }, digest);
  }
  const colBack = beforeCol.ok ? beforeCol : await readField(COL);
  const colReady = !readFailed(colBack) && colBack.body.TypeAsString === 'Choice';
  notes.push(`${COL}: `
    + (madeCol === null ? 'already present' : `create HTTP ${madeCol.status}`)
    + '; readback ' + (readFailed(colBack)
      ? `failed HTTP ${colBack.status}`
      : `TypeAsString=${show(colBack.body.TypeAsString)}`));

  // ---- fixture-nested-folders-created, and nesting-depth ---------------
  // One folder at a time, each addressed at the folder above it, so the run
  // records what happened at every level rather than at the deepest only.
  const spellings = [];
  const madeFolders = [];
  const leftovers = [];
  for (let level = 0; level < LEVELS.length; level += 1) {
    const parent = pathAt(level);
    const name = LEVELS[level];
    // No reuse path, deliberately. The reset above cleared what an earlier run
    // left, so a folder still here is one this probe could not clear, and
    // building the ladder on it would answer this run's question with somebody
    // else's folder. See the dirty-fixture finding above.
    const before = await readFolder(pathAt(level + 1));
    if (folderIsThere(before)) {
      leftovers.push(`'${name}' survived the pre-run reset, so this run did not create it`);
      spellings.push(`'${name}' NOT CREATED: it was already there after the reset`);
      madeFolders.push({ level, spelling: 'left over', res: before });
      continue;
    }
    // The three spellings Learn documents, in the order it documents them.
    // Which one answers is an observation, not a premise.
    digest = await getDigest();
    let spelling = 'parent folders/add(url=)';
    let attempt = await spPost(
      `web/GetFolderByServerRelativeUrl('${parent}')/folders/add(url='${name}')`,
      {}, digest);
    if (!attempt.ok) {
      digest = await getDigest();
      spelling = 'web/folders/add(full path)';
      attempt = await spPost(`web/folders/add('${pathAt(level + 1)}')`, {}, digest);
    }
    if (!attempt.ok) {
      digest = await getDigest();
      spelling = 'web/folders ServerRelativeUrl';
      attempt = await spPost('web/folders',
                             { ServerRelativeUrl: pathAt(level + 1) }, digest);
    }
    spellings.push(attempt.ok
      ? `'${name}' created by ${spelling} (HTTP ${attempt.status})`
      : `'${name}' FAILED, last attempt ${spelling} HTTP ${attempt.status}: `
        + clip(attempt.text, 160));
    madeFolders.push({ level, spelling, res: attempt });
  }

  // Read every level back as a folder entity, which is the only thing that says
  // the folder landed at the nested path rather than beside its parent.
  const levelReads = [];
  for (let level = 1; level <= LEVELS.length; level += 1) {
    const read = await readFolder(pathAt(level));
    levelReads.push({
      level,
      status: read.status,
      body: readFailed(read) ? null : read.body,
      // folderIsThere first: a path this read merely echoed back is not a
      // folder at that path. See the folder-read finding above.
      at: folderIsThere(read) && read.body.ServerRelativeUrl === pathAt(level),
    });
  }
  // The parent's own Folders collection, which is what makes the deepest folder
  // a CHILD of the one above rather than a folder that happens to share a path.
  const parentChildren = await spGet(
    `web/GetFolderByServerRelativeUrl('${pathAt(2)}')/Folders?$select=Name,ServerRelativeUrl`);
  const childNames = (!readFailed(parentChildren) && Array.isArray(parentChildren.body.value))
    ? parentChildren.body.value.map((child) => child.Name)
    : [];

  const foldersReady = colReady && leftovers.length === 0
    && levelReads.every((read) => read.at);
  record('library.folder.fixture-nested-folders-created', Q.folders,
         foldersReady ? 'PASS' : 'FAIL',
         `${notes.join('; ')}. ${resetNotes.join('; ')}. ${spellings.join('; ')}. `
         + `Read back: ${levelReads.map((read) => `level ${read.level} HTTP ${read.status} `
           + `${show(read.body)}`).join('; ')}. `
         + `The Folders collection of '${LEVELS[1]}' holds ${show(childNames)}.`
         + (leftovers.length
           ? ` DIRTY FIXTURE: ${leftovers.join('; ')}, so this row is about a folder `
             + 'an earlier run left rather than about SharePoint.'
           : ''));

  if (!foldersReady) {
    record('library.folder.fixture-files-placed', Q.files,
           'ABORTED', 'the folder ladder did not build, so no file was uploaded into it');
    return abortEverything(
      `the folder ladder did not build, so nothing below is about depth: ${spellings.join('; ')}`);
  }

  // ---- nesting-depth ---------------------------------------------------
  const deepest = levelReads[levelReads.length - 1];
  const nestedSpellings = madeFolders.filter((made) => made.level > 0)
    .map((made) => made.spelling);
  const nestingOutcome = deepest.at
    ? 'NESTS THREE DEEP'
    : deepest.body === null ? 'NOT ESTABLISHED' : 'CREATED SOMEWHERE ELSE';
  // The folder control decides whether this row ANSWERS the question or only
  // records what was seen. The observation is kept either way.
  const folderState = folderControlHeld ? undefined : 'void';
  record('library.folder.nesting-depth', Q.depth,
         nestingOutcome,
         `'${LEVELS.join('/')}' read back HTTP ${deepest.status} as ${show(deepest.body)}, `
         + `asked for ${show(pathAt(LEVELS.length))}. The spelling that created each folder `
         + `whose parent is a folder: ${show(nestedSpellings)}. `
         + `The Folders collection of '${LEVELS[1]}' holds ${show(childNames)}, so the `
         + 'deepest folder is reachable as a child of the one above it rather than only by '
         + 'its path.'
         + (folderControlHeld
           ? ''
           : ' The folder negative control did not hold, so this row records what was '
             + 'seen rather than answering the question.'),
         folderState);

  // ---- fixture-files-placed --------------------------------------------
  const uploads = [];
  for (const file of FILES) {
    const uploaded = await rawPost(
      `web/GetFolderByServerRelativeUrl('${pathAt(file.depth)}')`
      + `/Files/add(url='${file.name}',overwrite=true)`,
      `dbml-sharepoint library-nesting probe payload for ${file.name}`,
      { 'Content-Type': 'text/plain' });
    uploads.push(uploaded.ok
      ? `uploaded '${file.name}' at depth ${file.depth}`
      : `upload of '${file.name}' at depth ${file.depth} FAILED HTTP ${uploaded.status}: `
        + clip(uploaded.text, 160));
  }

  // The path columns are selected together, and the read is repeated without
  // FileDirRef if that fails: one unrecognised name errors the whole request,
  // so a column this probe cannot select would otherwise read as a library with
  // no items in it at all.
  const WIDE = `$select=Id,FileLeafRef,FileRef,FileDirRef,FileSystemObjectType&$top=100`;
  const NARROW = `$select=Id,FileLeafRef,FileRef,FileSystemObjectType&$top=100`;
  let itemsRead = await spGet(`${libPath}/items?${WIDE}`);
  const dirRefSelectable = !readFailed(itemsRead);
  if (!dirRefSelectable) {
    itemsRead = await spGet(`${libPath}/items?${NARROW}`);
  }
  const itemRows = (!readFailed(itemsRead) && Array.isArray(itemsRead.body.value))
    ? itemsRead.body.value
    : [];
  const rowFor = (name) => itemRows.find((row) => row.FileLeafRef === name) || null;

  const writeNotes = [];
  for (const file of FILES) {
    const row = rowFor(file.name);
    if (row === null) {
      writeNotes.push(`'${file.name}' has no list item, so nothing was written to it`);
      continue;
    }
    const wrote = await mergeItem(row.Id, { [COL]: file.choice });
    writeNotes.push(wrote.ok
      ? `'${file.name}' ${COL} write HTTP ${wrote.status}`
      : `'${file.name}' ${COL} write FAILED HTTP ${wrote.status}: ${clip(wrote.text, 160)}`);
  }

  const backRead = await spGet(
    `${libPath}/items?$select=Id,FileLeafRef,FileRef,${COL}&$top=100`);
  const backRows = (!readFailed(backRead) && Array.isArray(backRead.body.value))
    ? backRead.body.value
    : [];
  const mismatches = [];
  for (const file of FILES) {
    const row = backRows.find((candidate) => candidate.FileLeafRef === file.name);
    if (!row) {
      mismatches.push(`'${file.name}' is not in the library`);
      continue;
    }
    if (row[COL] !== file.choice) {
      mismatches.push(`'${file.name}' ${COL} read back ${show(row[COL])}, wrote ${show(file.choice)}`);
    }
    const wanted = `${pathAt(file.depth)}/${file.name}`;
    if (String(row.FileRef) !== wanted) {
      mismatches.push(`'${file.name}' FileRef read back ${show(row.FileRef)}, uploaded to ${show(wanted)}`);
    }
  }

  const filesReady = mismatches.length === 0;
  record('library.folder.fixture-files-placed', Q.files,
         filesReady ? 'PASS' : 'FAIL',
         `${uploads.join('; ')}. ${writeNotes.join('; ')}. `
         + `The ordinary items collection returned ${itemRows.length} row(s) over `
         + `${FILES.length} file(s) and ${LEVELS.length} folder(s), with FileDirRef `
         + `${dirRefSelectable ? 'selectable' : 'NOT selectable, so it was dropped from the read'}. `
         + (mismatches.length
           ? `readback mismatches: ${mismatches.join('; ')}`
           : 'every file read back at the path it was uploaded to, holding the value written to it'));

  if (!filesReady) {
    return abortEverything(
      'the files did not read back at the depths they were uploaded to, so a query over '
      + `them would report the fixture rather than SharePoint: ${mismatches.join('; ')}`);
  }

  // ---- file-in-nested-folder -------------------------------------------
  const deepFile = FILES.find((file) => file.depth === LEVELS.length);
  const deepRow = rowFor(deepFile.name);
  const wantedRef = `${pathAt(deepFile.depth)}/${deepFile.name}`;
  const refCorrect = deepRow !== null && String(deepRow.FileRef) === wantedRef;
  const dirCorrect = deepRow !== null && dirRefSelectable
    && String(deepRow.FileDirRef) === pathAt(deepFile.depth);
  record('library.folder.file-in-nested-folder', Q.nestedFile,
         deepRow === null
           ? 'NOT ESTABLISHED'
           : refCorrect && dirCorrect
             ? 'UPLOADED, AND BOTH PATH COLUMNS CARRY THE NESTED PATH'
             : refCorrect && !dirRefSelectable
               ? 'UPLOADED, FileRef CARRIES THE PATH, FileDirRef NOT SELECTABLE'
               : refCorrect
                 ? 'UPLOADED, FileRef CARRIES THE PATH, FileDirRef DOES NOT'
                 : 'UPLOADED SOMEWHERE ELSE',
         `'${deepFile.name}' was uploaded through Files/add on the folder `
         + `${show(pathAt(deepFile.depth))} and reads back as ${show(deepRow)}. `
         + `FileRef expected ${show(wantedRef)}, FileDirRef expected `
         + `${show(pathAt(deepFile.depth))}, FileDirRef selectable: ${dirRefSelectable}.`
         + (folderControlHeld
           ? ''
           : ' The folder negative control did not hold, so this row records what was '
             + 'seen rather than answering the question.'),
         folderState);

  // ---- Reading a view --------------------------------------------------
  const rowsOf = (res) => {
    if (readFailed(res)) return [];
    if (Array.isArray(res.body.Row)) return res.body.Row;
    if (res.body.ListData && Array.isArray(res.body.ListData.Row)) return res.body.ListData.Row;
    return [];
  };

  const VIEW_FIELDS = ['FileLeafRef', 'FileRef'];

  // One RenderListDataAsStream query. `fieldNames` empty sends no <GroupBy> at
  // all, which is the flat shape every grouped answer is compared against.
  const askView = async (fieldNames, collapse, scope, fields) => {
    const scoped = scope === null ? '' : ` Scope="${scope}"`;
    const grouping = fieldNames.length
      ? `<GroupBy Collapse="${collapse}">`
        + fieldNames.map((name) => `<FieldRef Name="${name}"/>`).join('')
        + '</GroupBy>'
      : '';
    const viewXml = `<View${scoped}><Query>${grouping}</Query><ViewFields>`
      + (fields || VIEW_FIELDS).map((name) => `<FieldRef Name="${name}"/>`).join('')
      + `</ViewFields><RowLimit>${ROW_LIMIT}</RowLimit></View>`;
    digest = await getDigest();
    const res = await spPost(`${libPath}/RenderListDataAsStream`,
                             { parameters: { ViewXml: viewXml } }, digest);
    return { res, rows: rowsOf(res) };
  };

  // The keys an honoured group-by carries, named rather than matched on the
  // column name: every column in this fixture is called Nest*, so a /group/i
  // test over a label key would report a grouping that is only a coincidence.
  const GROUP_MARKER = /\.COUNT\.group$|\.newgroup$|\.groupindex$/;
  const markersIn = (rows) => {
    const seen = [];
    for (const row of rows) {
      for (const key of Object.keys(row)) {
        if (GROUP_MARKER.test(key) && !seen.includes(key)) seen.push(key);
      }
    }
    return seen;
  };
  const namedKeysIn = (rows, name) => {
    const seen = [];
    for (const row of rows) {
      for (const key of Object.keys(row)) {
        if ((key === name || key.startsWith(`${name}.`)) && !seen.includes(key)) {
          seen.push(key);
        }
      }
    }
    return seen;
  };

  // Everything the SERVER said about one grouping, and nothing this probe
  // worked out for itself. See the client-side-partition finding in the header.
  const observe = async (fieldNames, fields) => {
    const collapsed = await askView(fieldNames, 'TRUE', DEEP_SCOPE, fields);
    const expanded = await askView(fieldNames, 'FALSE', DEEP_SCOPE, fields);
    const flat = await askView([], 'TRUE', DEEP_SCOPE, fields);
    const labels = collapsed.rows.map(
      (row) => fieldNames.map((name) => (name in row ? row[name] : undefined)));
    const markers = markersIn(collapsed.rows);
    const seen = {
      collapsed, expanded, flat, labels, markers,
      refused: !collapsed.res.ok && isRefusal(collapsed.res.status),
      // HONOURED against IGNORED. See the never-refused finding in the header.
      honoured: collapsed.res.ok && markers.length > 0,
      ignored: collapsed.res.ok && markers.length === 0 && flat.res.ok
        && collapsed.rows.length === flat.rows.length,
    };
    seen.text = `collapsed HTTP ${collapsed.res.status} returned ${collapsed.rows.length} `
      + `row(s), labels ${clip(show(labels), 300)}, grouping markers `
      + `${clip(show(markers), 300)}, first row `
      + `${clip(show(collapsed.rows.length ? collapsed.rows[0] : null), 400)}; `
      + `expanded HTTP ${expanded.res.status} returned ${expanded.rows.length} row(s) over `
      + `${FILES.length} file(s); the same query with no <GroupBy> returned HTTP `
      + `${flat.res.status} with ${flat.rows.length} row(s)`
      + (collapsed.res.ok ? '' : `; collapsed body ${clip(collapsed.res.text, 220)}`);
    return seen;
  };

  // ---- view-flattens-depth ---------------------------------------------
  // No <GroupBy> anywhere in this row: it is a question about which rows a view
  // returns, and a grouped query's rows do not carry a file name.
  const byScope = [];
  for (const scope of SCOPES) {
    const seen = await askView([], 'TRUE', scope, VIEW_FIELDS);
    const names = seen.rows.map((row) => String(row.FileLeafRef === undefined
      ? '' : row.FileLeafRef));
    byScope.push({
      scope,
      status: seen.res.status,
      rows: seen.rows.length,
      files: FILES.filter((file) => names.includes(file.name)).map((file) => file.name),
      folders: LEVELS.filter((level) => names.includes(level)),
      deepest: FILES.filter((file) => file.depth === LEVELS.length)
        .every((file) => names.includes(file.name)),
      all: FILES.every((file) => names.includes(file.name)),
    });
  }
  const defaultScope = byScope[0];
  const flattening = byScope.find((seen) => seen.all) || null;
  record('library.folder.view-flattens-depth', Q.flatten,
         byScope.every((seen) => !seen.status || seen.status >= 400)
           ? 'NOT ESTABLISHED'
           : defaultScope.deepest
             ? 'FLATTENS BY DEFAULT'
             : flattening === null
               ? 'DIRECT CHILDREN ONLY, NO SCOPE RETURNED EVERY FILE'
               : `DIRECT CHILDREN BY DEFAULT, FLATTENED BY Scope="${flattening.scope}"`,
         `${FILES.length} file(s) at depths ${show(FILES.map((file) => file.depth))} and `
         + `${LEVELS.length} nested folder(s). `
         + byScope.map((seen) => `Scope=${show(seen.scope)}: HTTP ${seen.status}, `
           + `${seen.rows} row(s), files ${show(seen.files)}, folder rows ${show(seen.folders)}`)
           .join('; ')
         + `. The ordinary items collection returned ${itemRows.length} row(s) for the same `
         + 'library, so any difference here is the VIEW rather than the item store.');

  // ---- control-missing-group-column-ungrouped: NEGATIVE CONTROL --------
  // The premise, read back rather than assumed. A column somebody else made
  // under this name would make the rows below a real grouping.
  const missingField = await readField(MISSING);
  const missingSeen = await askView([MISSING], 'TRUE', DEEP_SCOPE, ['FileLeafRef']);
  const ungroupedSeen = await askView([], 'TRUE', DEEP_SCOPE, ['FileLeafRef']);
  const missingMarkers = markersIn(missingSeen.rows)
    .concat(namedKeysIn(missingSeen.rows, MISSING));
  const flatSignature = !missingField.ok
    && missingSeen.res.ok && ungroupedSeen.res.ok
    && missingMarkers.length === 0
    && missingSeen.rows.length === ungroupedSeen.rows.length;
  record('library.view.control-missing-group-column-ungrouped', Q.ungrouped,
         flatSignature ? 'PASS' : missingMarkers.length ? 'FAIL' : 'NOT ESTABLISHED',
         `'${MISSING}' read back HTTP ${missingField.status}`
         + `${missingField.ok ? ', so the column EXISTS and this is not a control' : ''}; `
         + `a group-by naming it returned HTTP ${missingSeen.res.status} with `
         + `${missingSeen.rows.length} row(s), grouping markers `
         + `${clip(show(missingMarkers), 300)}, first row `
         + `${clip(show(missingSeen.rows.length ? missingSeen.rows[0] : null), 400)}; `
         + `the same query with no <GroupBy> returned HTTP ${ungroupedSeen.res.status} with `
         + `${ungroupedSeen.rows.length} row(s)`
         + (missingSeen.res.ok ? '' : `; body ${clip(missingSeen.res.text, 220)}`)
         + (flatSignature
           ? '. Flat rows carrying no group label, as many as the same query returns with no '
             + '<GroupBy> at all, so a group-by SharePoint ignored is observable and is not '
             + 'the group rows the positive control reads.'
           : missingMarkers.length
             ? '. The rows carry the markers an honoured group-by carries, so this run cannot '
               + 'tell a group-by SharePoint honoured from one it ignored, and every group-by '
               + 'answer below is void.'
             : '. Neither signature: the ignored one was not observed, so a flat answer below '
               + 'cannot be read as a group-by SharePoint ignored.'));

  // ---- control-group-by-single-value-column: POSITIVE CONTROL ----------
  const controlSeen = await observe([COL], ['FileLeafRef', COL]);
  const controlLabels = controlSeen.labels.map(
    (label) => String(label[0] === null || label[0] === undefined ? '' : label[0]));
  const positiveHeld = controlSeen.collapsed.res.ok
    && controlSeen.collapsed.rows.length >= CHOICES.length
    && CHOICES.every((choice) => controlLabels.some((label) => label.includes(choice)));
  record('library.view.control-group-by-single-value-column', Q.grouped,
         positiveHeld ? 'PASS' : 'CONTROL FAILED, METHOD VOID',
         `${COL} at Scope="${DEEP_SCOPE}", over ${CHOICES.length} value(s) `
         + `${show(CHOICES)}. ${controlSeen.text}`
         + (positiveHeld
           ? ''
           : '. A group-by on the column kind already measured working on a library did not '
             + 'return group rows this probe could read, so nothing below is a statement '
             + 'about folder depth.'));

  const controlsHeld = flatSignature && positiveHeld;
  const controlReason = flatSignature
    ? 'the positive control did not hold, so this run cannot read the shape of a group that works'
    : 'the negative control did not hold, so this run cannot tell a group-by SharePoint honoured from one it ignored';

  // Publish one measurement, keeping the observation either way. A void row
  // still carries what was seen: the reader loses the verdict, not the data.
  const publish = (id, question, outcome, evidence) => {
    if (controlsHeld) {
      record(id, question, outcome, evidence);
      return;
    }
    record(id, question, 'NOT ESTABLISHED',
           `${evidence}. Recorded rather than answered: ${controlReason}.`, 'void');
  };

  // ---- group-by-path-depth ---------------------------------------------
  // The premise again: a group-by over a column the library does not hold would
  // be the negative control a second time rather than a measurement.
  const pathField = await readField(PATH_COL);
  const pathSeen = await observe([PATH_COL], ['FileLeafRef', PATH_COL]);
  const pathLabels = pathSeen.labels.map(
    (label) => String(label[0] === null || label[0] === undefined ? '' : label[0]));
  const namesFullPath = pathLabels.some(
    (label) => LEVELS.every((level) => label.includes(level)));
  const namesLeaf = pathLabels.some(
    (label) => label.includes(LEVELS[2]) && !label.includes(LEVELS[0]));
  const namesTop = pathLabels.some(
    (label) => label.includes(LEVELS[0]) && !label.includes(LEVELS[2]));
  publish('library.folder.group-by-path-depth', Q.pathDepth,
          !pathField.ok
            ? 'NOT ESTABLISHED'
            : pathSeen.refused
              ? 'REFUSED'
              : pathSeen.ignored
                ? 'ACCEPTED AND IGNORED'
                : !pathSeen.honoured
                  ? 'NOT ESTABLISHED'
                  : namesFullPath
                    ? 'GROUPED UNDER THE FULL PATH'
                    : namesLeaf
                      ? 'GROUPED UNDER THE LEAF FOLDER'
                      : namesTop
                        ? 'GROUPED UNDER THE TOP FOLDER'
                        : 'HONOURED, LABELS NAME NONE OF THE THREE',
          `'${PATH_COL}' read back HTTP ${pathField.status}`
          + (pathField.ok ? '' : ', so the library does not hold the column this row groups by')
          + `. The file three deep sits under ${show(pathAt(LEVELS.length))}, whose full path `
          + `names ${show(LEVELS)}, whose leaf folder is ${show(LEVELS[2])} and whose top `
          + `folder is ${show(LEVELS[0])}. ${pathSeen.text}`);

  // ---- nesting-with-metadata-group-by ----------------------------------
  // Two observations. The first asks whether a metadata group-by reaches the
  // files inside folders at all; the second asks what happens when the folder
  // path and the metadata column are named in ONE <GroupBy>. See the
  // two-fields finding in the header for why the second is an experiment.
  const deepNames = FILES.filter((file) => file.depth > 0).map((file) => file.name);
  const spanRows = controlSeen.expanded.rows.map(
    (row) => String(row.FileLeafRef === undefined ? '' : row.FileLeafRef));
  const spansDepth = deepNames.every((name) => spanRows.includes(name));

  const bothSeen = await observe([PATH_COL, COL], ['FileLeafRef', PATH_COL, COL]);
  const pathKeys = markersIn(bothSeen.collapsed.rows)
    .filter((key) => key.startsWith(`${PATH_COL}.`));
  const colKeys = markersIn(bothSeen.collapsed.rows)
    .filter((key) => key.startsWith(`${COL}.`));
  publish('library.folder.nesting-with-metadata-group-by', Q.compose,
          bothSeen.refused
            ? 'REFUSED'
            : bothSeen.ignored
              ? 'ACCEPTED AND IGNORED'
              : pathKeys.length && colKeys.length
                ? 'BOTH DIMENSIONS GROUP'
                : pathKeys.length
                  ? 'ONLY THE FOLDER PATH GROUPS'
                  : colKeys.length
                    ? 'ONLY THE METADATA COLUMN GROUPS'
                    : 'NOT ESTABLISHED',
          `Grouping by ${COL} alone at Scope="${DEEP_SCOPE}" returned the file(s) inside `
          + `folders: ${spansDepth}, over ${show(deepNames)}. `
          + `A <GroupBy> naming ${PATH_COL} then ${COL}: markers for the path column `
          + `${show(pathKeys)}, markers for the metadata column ${show(colKeys)}. `
          + `${bothSeen.text}`);

  return report();
})();
