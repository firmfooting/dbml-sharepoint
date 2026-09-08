/**
 * dbml-sharepoint PROBE: HOW DO A VIEW'S FILTER, GROUP-BY AND FOLDER SCOPE INTERACT?
 *
 * REVISION: e81bc6cb
 *
 * ONE QUESTION, on the composition nothing has measured:
 *   `library-view-probe.js` measured a filter on a single-value column and a
 *   group-by on one, separately. `library-grouping-probe.js` measured which
 *   column kinds a group-by reaches. `library-nesting-probe.js` measured what a
 *   view does with folder depth. Each of the three mechanisms is measured
 *   ALONE. A layout generator emits views that filter and group over a library
 *   that holds folders, so what the three do TOGETHER decides the page, and
 *   nothing has asked it.
 *
 * WHY: the candidate behaviours are not variants of one another. A filter that
 * runs before the group produces group headings for the values that survived
 * it; a group built over every row produces a heading for a value the filter
 * removed, with nothing under it. Both are a saved view that reads back
 * byte-identical, deploys clean, and renders differently. Nothing in the build
 * or the deploy can see a rendered view, so the composition has to be measured
 * on a live site or it is not known.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. Every question here is a view question and
 * files under `library.view.*`, beside the rows the three probes above hold.
 * The FOUR CONTROLS keep the ids those probes already register for the same
 * questions by the same method, because one question with two records is one
 * id. The folder fixture is not re-asked as a folder question:
 * `library-nesting-probe.js` settled that a library nests and that a create
 * under a parent that does not exist is refused, so this probe reads its
 * folders back at the paths it asked for and stops there.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)? The same
 *        question by the same method as the library probes before it, so it
 *        keeps their id.
 *   library.view.fixture-interaction-columns-created
 *        Do the filter column and the group column exist, and do they read back
 *        as the types they were created as?
 *   library.view.fixture-interaction-folders-created
 *        Do the two folders exist, and does each read back at the nested path it
 *        was asked for rather than beside its parent?
 *   library.view.fixture-interaction-files-placed
 *        Do the six files exist at the three depths they were uploaded to, each
 *        holding the filter value and the group value written to it?
 *   library.view.control-missing-column-refused
 *        NEGATIVE CONTROL: is a RenderListDataAsStream query whose `<Where>`
 *        names a column that does not exist refused? A measurement below that
 *        comes back REFUSED means nothing unless a refusal is observable. Same
 *        question, same method, same id as `library-view-probe.js`.
 *   library.view.control-filter-single-value-column
 *        POSITIVE CONTROL: does a `<Where><Eq>` on the single-value filter
 *        column return the rows holding that value and no others? This is the
 *        control the composition rows rest on: without it, a filter that was
 *        never applied and a filter that was applied and changed nothing read
 *        the same.
 *   library.view.control-missing-group-column-ungrouped
 *        NEGATIVE CONTROL: does a group-by naming a column that does not exist
 *        come back UNGROUPED? A group-by is never refused, so the discriminator
 *        is the shape of the answer. Same question, same method, same id as
 *        `library-grouping-probe.js`.
 *   library.view.control-group-by-single-value-column
 *        POSITIVE CONTROL: group-by on the single-value Choice column, the case
 *        already measured working. It proves THIS probe can read the shape of a
 *        group that works.
 *   library.view.filter-with-group-by
 *        Does the filter run BEFORE the group, so the group labels and counts
 *        carry only the rows that survived it, or is the group built over EVERY
 *        row? Measured by filtering out every file holding one group value and
 *        reading whether that value still comes back as a group label.
 *   library.view.filter-in-folder-scope
 *        Is a filter folder-scoped or library-wide? Measured by sending the same
 *        filtered query twice, once with no folder named and once pointed at a
 *        nested folder, and reading which rows each returns.
 *   library.view.filter-group-by-and-folder-scope
 *        The three-way. A filtered, grouped query pointed at a nested folder in
 *        a library that holds folders: do all three compose, and which one is
 *        dropped if they do not?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the library exists; both columns exist and
 *   read back as the types they were made as; both folders read back at their
 *   nested paths; the six files read back at the depths they were uploaded to
 *   holding the values written to them; a `<Where>` naming a column that does
 *   not exist is refused; a `<Where>` on the filter column returns exactly the
 *   rows holding that value; a group-by naming a missing column comes back in
 *   the same shape as the same query with no group-by; a group-by on the
 *   single-value column returns group rows this probe can read.
 *   Observes (recorded, never asserted): which group labels and counts a
 *   filtered grouped query returns; which rows a filtered query returns at the
 *   library root and inside a folder; whether the folder parameter narrows the
 *   read at all, and whether it descends below the folder it names; which of the
 *   three mechanisms survives when all three are sent at once. NOTHING here
 *   asserts that a filter precedes a group, that a folder scopes a filter, or
 *   that the three compose. A run where the group is built over every row is a
 *   successful run with an important answer, and so is a run where the folder
 *   parameter changes nothing.
 *
 * WHY THE FIXTURE IS SHAPED AS IT IS. Six files over three depths, two filter
 * values and two group values, chosen so that no candidate answer has the same
 * signature as another. One group value (Green) is carried ONLY by files the
 * filter removes, so a Green label surviving the filter is the direct signature
 * of a group built over every row and cannot be produced any other way. The
 * counts are 6 at the library, 3 filtered, 4 inside the folder and 2 filtered
 * inside the folder, all distinct, so a row count alone says which query was
 * answered.
 *
 * HOW A GROUPING IS READ. Each grouped question sends the SAME query three
 * times and varies only the grouping: collapsed, expanded, and with no
 * `<GroupBy>` at all. The third is the flat shape the first two are compared
 * against, measured in this run rather than assumed. Verdicts about WHICH ROWS
 * came back are read off the EXPANDED query, because a collapsed row does not
 * carry a file name. See the inherited findings below.
 *
 * ABORTED VERSUS VOID. A fixture that never built records ABORTED downstream,
 * which is open: a re-run can clear it. A control that did not hold records the
 * observation it made and marks the row void, because on this site, by this
 * method, the row cannot be answered however many times it is re-run.
 *
 * MICROSOFT LEARN CITATIONS. Every URL, element and attribute below is one Learn
 * documents rather than one assembled from memory, because a wrong spelling
 * returns 404, `isRefusal` counts 404 as a refusal, and the probe would then
 * print a claim about SharePoint that was really a typo:
 *
 *   List and library creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields/createfieldasxml`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   `FolderCollection.Add`, spelled `/add(url)`, and file upload via
 *   `Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *   Folder creation by POST to `web/folders` with a `ServerRelativeUrl`:
 *     "Working with folders and files with REST"
 *   The `<Query>` children this probe sends, in the order the syntax block
 *   gives them (`Where`, then `GroupBy`, then `OrderBy`):
 *     "Query element (List)"
 *   The comparison, its operands, and the `Type` attribute of a value:
 *     "Eq element (Query)", "FieldRef element (Query)", "Value element (Query)"
 *   Grouping a query, and the `Collapse` attribute:
 *     "GroupBy element (Query)"
 *   The `Scope` attribute of `<View>`, whose documented values are `FilesOnly`
 *   (files of a specific folder), `Recursive` (all files of all folders) and
 *   `RecursiveAll` (all files and all subfolders of all folders), and whose
 *   absence displays "only the files and subfolders of a specific folder":
 *     "View element (List)"
 *   Reading a view's rows without opening the page:
 *     "SP.List.renderListDataAsStream method"
 *   Pointing that read at one folder:
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
// finding: library-view-interaction-a-group-by-is-never-refused - inherited from
// library-grouping-probe.js, whose first live run on 2026-09-08 sent a
// <GroupBy> naming a column that does not exist and got HTTP 200 back with flat
// rows. The discriminator a group-by needs is not refused against accepted but
// HONOURED against IGNORED: an honoured group-by returns rows carrying the
// markers `<Field>.COUNT.group`, `<Field>.newgroup` and `<Field>.groupindex`,
// and an ignored one returns the rows the same query returns with no <GroupBy>
// at all. Every grouped question here sends both queries for that reason.
// finding: library-view-interaction-a-collapsed-row-carries-no-file-name -
// inherited from library-grouping-probe.js, second live run 2026-09-08: a
// collapsed query's rows did not carry the FileLeafRef its ViewFields named, the
// first being `{"PreviewThumbnailsQualitySets":""}`. Every verdict here about
// WHICH FILES came back is read off the expanded query, and the collapsed rows
// are read only for their labels and their group markers.
// finding: library-view-interaction-client-side-partition-is-not-evidence -
// inherited from library-grouping-probe.js: a probe that sends a grouped query,
// gets flat rows back and sorts them into buckets by reading each row's value
// has measured its own arithmetic. Every observation reasoned from here is
// server-produced: the collapsed query's labels and keys, the expanded query's
// rows, and the row count of the same query sent with no <GroupBy>.
// finding: library-view-interaction-view-flattens-only-at-recursive-scope -
// inherited from library-nesting-probe.js, run 2026-09-08: a view read with no
// Scope returns only direct children and Scope="FilesOnly" only the root file;
// Scope="Recursive" and Scope="RecursiveAll" are what flatten the files at
// depth. Every query here runs at Scope="Recursive", so a query that returns
// only the root files is reporting the scope rather than the filter. Recursive
// is used rather than RecursiveAll because RecursiveAll adds SUBFOLDER rows,
// which would land in the group counts this probe reads.
// finding: library-view-interaction-a-folder-read-answers-for-a-folder-that-is-not-there
// - inherited from library-nesting-probe.js, run 2026-09-08, revision 3937f7ae:
// a read of `GetFolderByServerRelativeUrl('<library root>/<name>')?$select=Exists`
// answered HTTP 200 for folders that could not have been there. HTTP ok is not
// presence on this surface. folderIsThere() below reads the BODY, and is right
// whichever way a tenant answers.
// finding: library-view-interaction-a-dirty-fixture-measures-the-previous-run -
// inherited from library-nesting-probe.js, same run: reading HTTP 200 as
// presence sent every folder creation down an "already present" path, nothing
// was built, and seven rows aborted. The folders here are RECYCLED before they
// are built, deepest first, and there is no reuse path: a folder still present
// after the reset is RECORDED rather than built on.
// finding: library-view-interaction-value-type-names-a-data-type - "Value
// element (Query)" documents Type as "the data type for the value contained by
// this element" and spells `Type="Text"` in its syntax block. It documents no
// mapping from a Choice column to a type name. So the FILTER column here is a
// Text column, where `Type="Text"` is the spelling Learn gives, and a filter
// that does not apply is SharePoint's answer rather than a guess about a type
// name. The GROUP column stays a Choice column, because that is the column kind
// the positive grouping control was established on and the control has to keep
// its method.
// finding: library-view-interaction-folder-parameter-is-not-a-view-attribute -
// FolderServerRelativeUrl is a property of RenderListDataParameters, not an
// attribute of <View>, so the folder scope travels BESIDE the ViewXml rather
// than inside it. Nothing has measured what a tenant does when the parameter and
// a Scope attribute are both set, which is why the folder rows below record the
// row sets rather than asserting a precedence, and why a read pointed at a
// folder that was never created is recorded as evidence: a parameter SharePoint
// ignores answers the same rows as one it never received.
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

  log('INFO', 'probe revision e81bc6cb. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe LibViewInt';
  // Text, so that <Value Type="Text"> is the spelling Learn documents rather
  // than a guess. See the value-type finding above.
  const FILTER_COL = 'IntStage';
  // Choice, the column kind the positive grouping control was established on.
  const GROUP_COL = 'IntTeam';
  // Never created. Both negative controls name it, one in a <Where> and one in
  // a <GroupBy>, and a run that finds it present is reading somebody else's
  // column.
  const MISSING = 'IntNoSuchColumnAtAll';
  // The filter keeps KEEP and removes DROP.
  const KEEP = 'Alpha';
  const DROP = 'Beta';
  // TEAMS[1] is carried ONLY by files the filter removes. A group label naming
  // it in a filtered query is the signature of a group built over every row.
  const TEAMS = ['Red', 'Green'];
  const FOLDERS = ['intlevel-outer', 'intlevel-inner'];
  // Never created. The folder reads name it to show what an ignored folder
  // parameter answers.
  const MISSING_FOLDER = 'intlevel-never-created';
  const ROW_LIMIT = 50;
  // See the recursive-scope finding above for why this value and not the other.
  const DEEP_SCOPE = 'Recursive';

  // Named once: each question is quoted in more than one place, and two
  // spellings of one question is how a summary stops matching a row.
  const Q = {
    library: 'A document library is created (BaseTemplate 101)',
    columns: 'The filter column and the group column exist and read back as the types they were created as',
    folders: 'The two folders exist and read back at the nested paths they were asked for',
    files: 'The six files exist at the depths they were uploaded to, holding the values written to them',
    refusal: 'NEGATIVE CONTROL: a RenderListDataAsStream query naming a missing column is refused',
    filtered: 'POSITIVE CONTROL: a view filter on a single-value column returns the rows holding that value and no others',
    ungrouped: 'NEGATIVE CONTROL: a group-by naming a column that does not exist comes back ungrouped, in the shape the same query returns with no group-by',
    grouped: 'POSITIVE CONTROL: a group-by on a single-value Choice column returns group rows this probe can read',
    order: 'Does the filter run before the group, or is the group built over every row?',
    folderScope: 'Is a view filter folder-scoped or library-wide when the read is pointed at a nested folder?',
    threeWay: 'A filtered, grouped query pointed at a nested folder: do all three compose, and which is dropped if not?',
  };

  // Six files over three depths, two filter values and two group values. The
  // shape is deliberate:
  //   TEAMS[1] is held only by files the filter removes, so a group label for it
  //   in a filtered query cannot be a coincidence
  //   the folder subtree holds both group values and both filter values, so a
  //   folder-scoped answer is not a filtered answer by accident
  //   the four candidate row counts (6 at the library, 3 filtered, 4 in the
  //   folder, 2 filtered in the folder) are all distinct
  const FILES = [
    { name: 'dbmlsp-int-root-keep.txt', depth: 0, stage: KEEP, team: TEAMS[0] },
    { name: 'dbmlsp-int-root-drop.txt', depth: 0, stage: DROP, team: TEAMS[1] },
    { name: 'dbmlsp-int-outer-keep.txt', depth: 1, stage: KEEP, team: TEAMS[0] },
    { name: 'dbmlsp-int-outer-drop.txt', depth: 1, stage: DROP, team: TEAMS[0] },
    { name: 'dbmlsp-int-inner-keep.txt', depth: 2, stage: KEEP, team: TEAMS[0] },
    { name: 'dbmlsp-int-inner-drop.txt', depth: 2, stage: DROP, team: TEAMS[1] },
  ];

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, with a Text`);
    log('INFO', `column '${FILTER_COL}' and a Choice column '${GROUP_COL}', then the`);
    log('INFO', `folders '${FOLDERS[0]}' and '${FOLDERS.join('/')}' through the folder`);
    log('INFO', `endpoint, and ${FILES.length} small text files at three depths.`);
    log('INFO', 'Would then read the library back through filtered, grouped and');
    log('INFO', 'folder-scoped RenderListDataAsStream queries, and the three together.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first, with its folders.`);
    } else {
      log('INFO', `CLEANUP is off: an existing '${LIB}' would be reused. Set`);
      log('INFO', 'CLEANUP = true to start from no library at all.');
    }
    log('INFO', `Either way, the folder '${FOLDERS[0]}' inside that library is`);
    log('INFO', 'RECYCLED before the fixture is built, because a fixture built on');
    log('INFO', 'leftovers measures the previous run. It is restorable from the');
    log('INFO', 'site recycle bin.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('library.doc-lib.fixture-library-created', Q.library);
  expect('library.view.fixture-interaction-columns-created', Q.columns);
  expect('library.view.fixture-interaction-folders-created', Q.folders);
  expect('library.view.fixture-interaction-files-placed', Q.files);
  expect('library.view.control-missing-column-refused', Q.refusal);
  expect('library.view.control-filter-single-value-column', Q.filtered);
  expect('library.view.control-missing-group-column-ungrouped', Q.ungrouped);
  expect('library.view.control-group-by-single-value-column', Q.grouped);
  expect('library.view.filter-with-group-by', Q.order);
  expect('library.view.filter-in-folder-scope', Q.folderScope);
  expect('library.view.filter-group-by-and-folder-scope', Q.threeWay);

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
      Description: 'dbml-sharepoint library-view-interaction probe library. Safe to delete.',
    }, digest);
    libraryReady = made.ok;
    record('library.doc-lib.fixture-library-created', Q.library,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${clip(made.text, 300)}`);
  }

  // Everything this probe measures, so an abort can report the truth about all
  // of it rather than about the rows it happened to reach.
  const MEASUREMENTS = [
    ['library.view.control-missing-column-refused', Q.refusal],
    ['library.view.control-filter-single-value-column', Q.filtered],
    ['library.view.control-missing-group-column-ungrouped', Q.ungrouped],
    ['library.view.control-group-by-single-value-column', Q.grouped],
    ['library.view.filter-with-group-by', Q.order],
    ['library.view.filter-in-folder-scope', Q.folderScope],
    ['library.view.filter-group-by-and-folder-scope', Q.threeWay],
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
    record('library.view.fixture-interaction-columns-created', Q.columns,
           'ABORTED', 'the library was never created');
    record('library.view.fixture-interaction-folders-created', Q.folders,
           'ABORTED', 'the library was never created');
    record('library.view.fixture-interaction-files-placed', Q.files,
           'ABORTED', 'the library was never created');
    return abortEverything('the scratch library was never created');
  }

  const root = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
  const folderUrl = (!readFailed(root)) ? root.body.ServerRelativeUrl : null;
  if (folderUrl === null) {
    record('library.view.fixture-interaction-columns-created', Q.columns,
           'ABORTED', `the library RootFolder did not read back (HTTP ${root.status})`);
    record('library.view.fixture-interaction-folders-created', Q.folders,
           'ABORTED', `the library RootFolder did not read back (HTTP ${root.status})`);
    record('library.view.fixture-interaction-files-placed', Q.files,
           'ABORTED', 'no folder path was known, so no file was uploaded');
    return abortEverything('the library RootFolder did not read back, so no path was known');
  }

  // The server-relative path of the folder `depth` levels down.
  const pathAt = (depth) => (depth === 0
    ? folderUrl
    : `${folderUrl}/${FOLDERS.slice(0, depth).join('/')}`);

  // Is a folder THERE? Not "did the endpoint answer": see the folder-read
  // finding in the header, where a read of a folder that could not be there
  // came back HTTP 200. A folder is there when the body carries a Name and does
  // not say Exists is false, which is right whether a tenant refuses the read or
  // answers it.
  const readFolder = async (path) => spGet(
    `web/GetFolderByServerRelativeUrl('${path}')`
    + '?$select=Name,ServerRelativeUrl,Exists,ItemCount');
  const folderIsThere = (read) => !readFailed(read)
    && read.body.Name !== undefined && read.body.Exists !== false;

  // RECYCLED rather than deleted, so anything this clears is restorable from
  // the site recycle bin. Both spellings folder-probe.js tries, in its order.
  const recycleFolder = async (path) => {
    digest = await getDigest();
    const gone = await spPost(
      `web/GetFolderByServerRelativeUrl('${path}')/recycle`, {}, digest);
    if (gone.ok) return gone;
    digest = await getDigest();
    return spPost(`web/GetFolderByServerRelativeUrl('${path}')/recycle()`, {}, digest);
  };

  // ---- fixture: the two columns ----------------------------------------
  const colNotes = [];
  const makeColumn = async (name, xml, wanted) => {
    const before = await readField(name);
    let made = null;
    if (!before.ok) {
      digest = await getDigest();
      made = await spPost(`${libPath}/fields/createfieldasxml`, {
        parameters: { SchemaXml: xml, Options: 8 },
      }, digest);
    }
    const back = before.ok ? before : await readField(name);
    const ready = !readFailed(back) && back.body.TypeAsString === wanted;
    colNotes.push(`${name}: `
      + (made === null ? 'already present' : `create HTTP ${made.status}`)
      + '; readback ' + (readFailed(back)
        ? `failed HTTP ${back.status}`
        : `TypeAsString=${show(back.body.TypeAsString)}, wanted ${show(wanted)}`));
    return ready;
  };
  const filterColReady = await makeColumn(
    FILTER_COL,
    `<Field Type="Text" DisplayName="${FILTER_COL}" Name="${FILTER_COL}"/>`,
    'Text');
  const groupColReady = await makeColumn(
    GROUP_COL,
    `<Field Type="Choice" DisplayName="${GROUP_COL}" Name="${GROUP_COL}">`
    + `<CHOICES>${TEAMS.map((team) => `<CHOICE>${team}</CHOICE>`).join('')}</CHOICES></Field>`,
    'Choice');
  const columnsReady = filterColReady && groupColReady;
  record('library.view.fixture-interaction-columns-created', Q.columns,
         columnsReady ? 'PASS' : 'FAIL', colNotes.join('; '));

  if (!columnsReady) {
    record('library.view.fixture-interaction-folders-created', Q.folders,
           'ABORTED', 'the columns did not read back, so no fixture was built');
    record('library.view.fixture-interaction-files-placed', Q.files,
           'ABORTED', 'the columns did not read back, so no file was uploaded');
    return abortEverything(
      `the fixture columns did not read back as their types: ${colNotes.join('; ')}`);
  }

  // ---- Pre-run reset of the folders ------------------------------------
  // The library outlives a run, whether CLEANUP is off or an earlier run left
  // it behind, and so do the folders in it. See the dirty-fixture finding in
  // the header. Only the folders NAMED here are touched, nothing is enumerated,
  // and the deepest goes first so that no row rests on a recycle taking children
  // with it.
  const resetNotes = [];
  for (let level = FOLDERS.length; level >= 1; level -= 1) {
    const path = pathAt(level);
    if (!folderIsThere(await readFolder(path))) continue;
    const gone = await recycleFolder(path);
    resetNotes.push(`'${path}' was left by an earlier run: recycle HTTP `
      + `${gone.status}, and it now reads `
      + `${folderIsThere(await readFolder(path)) ? 'STILL PRESENT' : 'absent'}`);
  }
  if (resetNotes.length === 0) {
    resetNotes.push('no folder from an earlier run was found to clear');
  }

  // ---- fixture-interaction-folders-created -----------------------------
  // One folder at a time, each addressed at the folder above it. No reuse path,
  // deliberately: a folder still here after the reset is one this probe could
  // not clear, and building on it would answer this run's question with somebody
  // else's folder.
  const spellings = [];
  const leftovers = [];
  for (let level = 0; level < FOLDERS.length; level += 1) {
    const parent = pathAt(level);
    const name = FOLDERS[level];
    if (folderIsThere(await readFolder(pathAt(level + 1)))) {
      leftovers.push(`'${name}' survived the pre-run reset, so this run did not create it`);
      spellings.push(`'${name}' NOT CREATED: it was already there after the reset`);
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
  }

  // Read each level back as a folder entity, which is the only thing that says
  // the folder landed at the nested path rather than beside its parent.
  const levelReads = [];
  for (let level = 1; level <= FOLDERS.length; level += 1) {
    const read = await readFolder(pathAt(level));
    levelReads.push({
      level,
      status: read.status,
      body: readFailed(read) ? null : read.body,
      at: folderIsThere(read) && read.body.ServerRelativeUrl === pathAt(level),
    });
  }
  const foldersReady = leftovers.length === 0 && levelReads.every((read) => read.at);
  record('library.view.fixture-interaction-folders-created', Q.folders,
         foldersReady ? 'PASS' : 'FAIL',
         `${resetNotes.join('; ')}. ${spellings.join('; ')}. `
         + `Read back: ${levelReads.map((read) => `level ${read.level} HTTP ${read.status} `
           + `${show(read.body)}`).join('; ')}.`
         + (leftovers.length
           ? ` DIRTY FIXTURE: ${leftovers.join('; ')}, so this row is about a folder `
             + 'an earlier run left rather than about SharePoint.'
           : ''));

  if (!foldersReady) {
    record('library.view.fixture-interaction-files-placed', Q.files,
           'ABORTED', 'the folders did not build, so no file was uploaded into them');
    return abortEverything(
      `the folders did not build, so nothing below is about a folder scope: ${spellings.join('; ')}`);
  }

  // ---- fixture-interaction-files-placed --------------------------------
  const uploads = [];
  for (const file of FILES) {
    const uploaded = await rawPost(
      `web/GetFolderByServerRelativeUrl('${pathAt(file.depth)}')`
      + `/Files/add(url='${file.name}',overwrite=true)`,
      `dbml-sharepoint library-view-interaction probe payload for ${file.name}`,
      { 'Content-Type': 'text/plain' });
    uploads.push(uploaded.ok
      ? `uploaded '${file.name}' at depth ${file.depth}`
      : `upload of '${file.name}' at depth ${file.depth} FAILED HTTP ${uploaded.status}: `
        + clip(uploaded.text, 160));
  }

  const itemsRead = await spGet(
    `${libPath}/items?$select=Id,FileLeafRef,FileRef&$top=100`);
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
    const wrote = await mergeItem(row.Id,
                                  { [FILTER_COL]: file.stage, [GROUP_COL]: file.team });
    writeNotes.push(wrote.ok
      ? `'${file.name}' value write HTTP ${wrote.status}`
      : `'${file.name}' value write FAILED HTTP ${wrote.status}: ${clip(wrote.text, 160)}`);
  }

  const backRead = await spGet(
    `${libPath}/items?$select=Id,FileLeafRef,FileRef,${FILTER_COL},${GROUP_COL}&$top=100`);
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
    if (row[FILTER_COL] !== file.stage) {
      mismatches.push(`'${file.name}' ${FILTER_COL} read back ${show(row[FILTER_COL])}, `
        + `wrote ${show(file.stage)}`);
    }
    if (row[GROUP_COL] !== file.team) {
      mismatches.push(`'${file.name}' ${GROUP_COL} read back ${show(row[GROUP_COL])}, `
        + `wrote ${show(file.team)}`);
    }
    const wanted = `${pathAt(file.depth)}/${file.name}`;
    if (String(row.FileRef) !== wanted) {
      mismatches.push(`'${file.name}' FileRef read back ${show(row.FileRef)}, `
        + `uploaded to ${show(wanted)}`);
    }
  }

  const filesReady = mismatches.length === 0;
  record('library.view.fixture-interaction-files-placed', Q.files,
         filesReady ? 'PASS' : 'FAIL',
         `${uploads.join('; ')}. ${writeNotes.join('; ')}. `
         + `The ordinary items collection returned ${itemRows.length} row(s) over `
         + `${FILES.length} file(s) and ${FOLDERS.length} folder(s). `
         + (mismatches.length
           ? `readback mismatches: ${mismatches.join('; ')}`
           : 'every file read back at the path it was uploaded to, holding both values '
             + 'written to it'));

  if (!filesReady) {
    return abortEverything(
      'the files did not read back at the depths and values they were given, so a query over '
      + `them would report the fixture rather than SharePoint: ${mismatches.join('; ')}`);
  }

  // ---- Reading a view --------------------------------------------------
  const rowsOf = (res) => {
    if (readFailed(res)) return [];
    if (Array.isArray(res.body.Row)) return res.body.Row;
    if (res.body.ListData && Array.isArray(res.body.ListData.Row)) return res.body.ListData.Row;
    return [];
  };

  const VIEW_FIELDS = ['FileLeafRef', 'FileRef', FILTER_COL, GROUP_COL];

  // One RenderListDataAsStream query. Every part is optional and every part is
  // named by the caller, because the whole subject here is which combination
  // was sent. `<Query>` children go Where then GroupBy, the order the syntax
  // block in "Query element (List)" gives them. The folder travels beside the
  // ViewXml rather than inside it: see the folder-parameter finding in the
  // header.
  const askView = async (opts) => {
    const scope = opts.scope === undefined ? DEEP_SCOPE : opts.scope;
    const scoped = scope === null ? '' : ` Scope="${scope}"`;
    const where = opts.filterOn
      ? `<Where><Eq><FieldRef Name="${opts.filterOn}"/>`
        + `<Value Type="Text">${opts.filterValue}</Value></Eq></Where>`
      : '';
    const names = opts.groupBy || [];
    const grouping = names.length
      ? `<GroupBy Collapse="${opts.collapse || 'TRUE'}">`
        + names.map((name) => `<FieldRef Name="${name}"/>`).join('')
        + '</GroupBy>'
      : '';
    const viewXml = `<View${scoped}><Query>${where}${grouping}</Query><ViewFields>`
      + (opts.fields || VIEW_FIELDS).map((name) => `<FieldRef Name="${name}"/>`).join('')
      + `</ViewFields><RowLimit>${ROW_LIMIT}</RowLimit></View>`;
    const parameters = { ViewXml: viewXml };
    if (opts.folder) parameters.FolderServerRelativeUrl = opts.folder;
    digest = await getDigest();
    const res = await spPost(`${libPath}/RenderListDataAsStream`, { parameters }, digest);
    return { res, rows: rowsOf(res), folder: opts.folder || null };
  };

  // The keys an honoured group-by carries, named rather than matched on the
  // column name: every column in this fixture is called Int*, so a /group/i test
  // over a label key would report a grouping that is only a coincidence.
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

  // The file names a query returned, server-produced and read only off rows
  // that carry one. A collapsed row does not, which is why no verdict below
  // reads names off one. See the collapsed-row finding in the header.
  const namesOf = (rows) => rows
    .map((row) => String(row.FileLeafRef === undefined ? '' : row.FileLeafRef))
    .filter((name) => name !== '');
  const sameSet = (left, right) => left.length === right.length
    && left.every((name) => right.includes(name));
  const within = (names, allowed) => names.length > 0
    && names.every((name) => allowed.includes(name));

  const ALL_NAMES = FILES.map((file) => file.name);
  const KEPT_NAMES = FILES.filter((file) => file.stage === KEEP).map((file) => file.name);
  // Everything in the folder subtree, at either depth below the root.
  const FOLDER_NAMES = FILES.filter((file) => file.depth >= 1).map((file) => file.name);
  const FOLDER_KEPT = FILES.filter((file) => file.depth >= 1 && file.stage === KEEP)
    .map((file) => file.name);
  const DEEPEST_NAMES = FILES.filter((file) => file.depth === FOLDERS.length)
    .map((file) => file.name);

  // Everything the SERVER said about one grouping, and nothing this probe
  // worked out for itself. See the client-side-partition finding in the header.
  const observe = async (opts) => {
    const collapsed = await askView({ ...opts, collapse: 'TRUE' });
    const expanded = await askView({ ...opts, collapse: 'FALSE' });
    const flat = await askView({ ...opts, groupBy: [] });
    const names = opts.groupBy || [];
    const labels = collapsed.rows.map(
      (row) => names.map((name) => (name in row ? row[name] : undefined)));
    const markers = markersIn(collapsed.rows);
    const seen = {
      collapsed, expanded, flat, labels, markers,
      names: namesOf(expanded.rows),
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
      + `expanded HTTP ${expanded.res.status} returned ${expanded.rows.length} row(s) `
      + `naming ${clip(show(seen.names), 300)}; the same query with no <GroupBy> returned `
      + `HTTP ${flat.res.status} with ${flat.rows.length} row(s)`
      + (collapsed.res.ok ? '' : `; collapsed body ${clip(collapsed.res.text, 220)}`);
    return seen;
  };

  // ---- control-missing-column-refused: NEGATIVE CONTROL ----------------
  // The premise, read back rather than assumed: a column somebody else made
  // under this name would make the query below a real filter.
  const missingField = await readField(MISSING);
  const junk = await askView({ filterOn: MISSING, filterValue: 'x',
                               fields: ['FileLeafRef'] });
  const refusalHeld = !missingField.ok && !junk.res.ok && isRefusal(junk.res.status);
  record('library.view.control-missing-column-refused', Q.refusal,
         junk.res.ok ? 'FAIL' : isRefusal(junk.res.status) ? 'PASS' : 'NOT ESTABLISHED',
         `'${MISSING}' read back HTTP ${missingField.status}`
         + `${missingField.ok ? ', so the column EXISTS and this is not a control' : ''}; `
         + `a <Where> naming it returned HTTP ${junk.res.status} with `
         + `${junk.rows.length} row(s)`
         + (junk.res.ok ? '' : `: ${clip(junk.res.text, 220)}`)
         + (junk.res.ok
           ? '. RenderListDataAsStream accepted a query naming a column that does not exist, '
             + 'so a REFUSED verdict below would say nothing about what was sent.'
           : isRefusal(junk.res.status)
             ? '. A refused query is observable, so a REFUSED verdict below is the server '
               + 'rejecting what was sent.'
             : '. Neither signature: the failure was about who is asking or about the moment, '
               + 'so it does not establish that a refusal is observable.'));

  // ---- control-filter-single-value-column: POSITIVE CONTROL ------------
  // The control the composition rows rest on. Without it, a filter that was
  // never applied and a filter that was applied and changed nothing read the
  // same, and every row below would be a statement about this probe.
  const plainRoot = await askView({});
  const filteredRoot = await askView({ filterOn: FILTER_COL, filterValue: KEEP });
  const plainNames = namesOf(plainRoot.rows);
  const filteredNames = namesOf(filteredRoot.rows);
  const filterHeld = plainRoot.res.ok && filteredRoot.res.ok
    && sameSet(plainNames, ALL_NAMES) && sameSet(filteredNames, KEPT_NAMES);
  record('library.view.control-filter-single-value-column', Q.filtered,
         filterHeld
           ? 'PASS'
           : filteredRoot.res.ok && sameSet(filteredNames, plainNames)
             ? 'FAIL, THE FILTER CHANGED NOTHING'
             : 'NOT ESTABLISHED',
         `At Scope="${DEEP_SCOPE}" with no folder named, the unfiltered query returned HTTP `
         + `${plainRoot.res.status} with ${plainRoot.rows.length} row(s) naming `
         + `${clip(show(plainNames), 300)} over ${FILES.length} file(s); the same query with `
         + `<Where><Eq> on ${FILTER_COL} = ${show(KEEP)} returned HTTP `
         + `${filteredRoot.res.status} with ${filteredRoot.rows.length} row(s) naming `
         + `${clip(show(filteredNames), 300)}, wanted ${clip(show(KEPT_NAMES), 300)}`
         + (filteredRoot.res.ok ? '' : `: ${clip(filteredRoot.res.text, 220)}`)
         + (filterHeld
           ? '. A filter that applies is observable, so a filtered answer below is the filter '
             + 'rather than the fixture.'
           : '. This run cannot tell a filter that was applied from one that was not, so every '
             + 'composition row below is void.'));

  // ---- control-missing-group-column-ungrouped: NEGATIVE CONTROL --------
  const missingSeen = await askView({ groupBy: [MISSING], fields: ['FileLeafRef'] });
  const ungroupedSeen = await askView({ fields: ['FileLeafRef'] });
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
  const groupSeen = await observe({ groupBy: [GROUP_COL] });
  const groupLabels = groupSeen.labels.map(
    (label) => String(label[0] === null || label[0] === undefined ? '' : label[0]));
  const groupHeld = groupSeen.collapsed.res.ok
    && groupSeen.collapsed.rows.length >= TEAMS.length
    && TEAMS.every((team) => groupLabels.some((label) => label.includes(team)));
  record('library.view.control-group-by-single-value-column', Q.grouped,
         groupHeld ? 'PASS' : 'CONTROL FAILED, METHOD VOID',
         `${GROUP_COL} at Scope="${DEEP_SCOPE}", over ${TEAMS.length} value(s) `
         + `${show(TEAMS)} with no filter and no folder named. ${groupSeen.text}`
         + (groupHeld
           ? ''
           : '. A group-by on the column kind already measured working on a library did not '
             + 'return group rows this probe could read, so nothing below is a statement '
             + 'about a group.'));

  const controlsHeld = filterHeld && flatSignature && groupHeld;
  const controlReason = !filterHeld
    ? 'the filter positive control did not hold, so this run cannot tell a filter that applied from one that did not'
    : !flatSignature
      ? 'the group-by negative control did not hold, so this run cannot tell a group-by SharePoint honoured from one it ignored'
      : 'the group-by positive control did not hold, so this run cannot read the shape of a group that works';

  // Publish one measurement, keeping the observation either way. A void row
  // still carries what was seen: the reader loses the verdict, not the data.
  // A REFUSED verdict is voided separately, because the control that makes a
  // refusal observable is a different control from the three above, and it only
  // matters for a row that came back refused.
  const publish = (id, question, outcome, evidence) => {
    if (!controlsHeld) {
      record(id, question, 'NOT ESTABLISHED',
             `${evidence}. Recorded rather than answered: ${controlReason}.`, 'void');
      return;
    }
    if (outcome === 'REFUSED' && !refusalHeld) {
      record(id, question, 'NOT ESTABLISHED',
             `${evidence}. Recorded rather than answered: the query was refused, and the `
             + 'refusal control did not hold, so this run cannot read a refusal as the server '
             + 'rejecting what was sent.', 'void');
      return;
    }
    record(id, question, outcome, evidence);
  };

  // ---- filter-with-group-by --------------------------------------------
  // Both queries group by the same column at the same scope, and differ only in
  // the <Where>. TEAMS[1] is carried only by files the filter removes, so its
  // presence as a label in the filtered answer is the whole discriminator.
  const filteredGroup = await observe({
    groupBy: [GROUP_COL], filterOn: FILTER_COL, filterValue: KEEP,
  });
  const filteredGroupLabels = filteredGroup.labels.map(
    (label) => String(label[0] === null || label[0] === undefined ? '' : label[0]));
  const droppedTeamSurvives = filteredGroupLabels.some(
    (label) => label.includes(TEAMS[1]));
  const filterAppliedHere = sameSet(filteredGroup.names, KEPT_NAMES);
  const filterDroppedHere = sameSet(filteredGroup.names, ALL_NAMES);
  publish('library.view.filter-with-group-by', Q.order,
          filteredGroup.refused
            ? 'REFUSED'
            : filteredGroup.ignored
              ? 'ACCEPTED AND IGNORED'
              : !filteredGroup.honoured
                ? 'NOT ESTABLISHED'
                : filteredGroup.names.length === 0
                  ? 'NOT ESTABLISHED, NO ROW CARRIED A FILE NAME'
                  : filterDroppedHere
                    ? 'THE FILTER IS DROPPED WHEN THE QUERY GROUPS'
                    : !filterAppliedHere
                      ? 'NOT ESTABLISHED, THE ROWS ARE NEITHER SET'
                      : droppedTeamSurvives
                        ? 'THE GROUP IS BUILT OVER EVERY ROW'
                        : 'THE FILTER RUNS BEFORE THE GROUP',
          `${show(TEAMS[1])} is carried only by the ${FILES.filter(
            (file) => file.team === TEAMS[1]).length} file(s) the filter removes, so a `
          + `${show(TEAMS[1])} label in a filtered answer can only come from a group built `
          + `over rows the filter took out. Grouped by ${GROUP_COL} with no filter: `
          + `${groupSeen.text}. The same query with <Where><Eq> on ${FILTER_COL} = `
          + `${show(KEEP)}: ${filteredGroup.text}. The expanded filtered rows name `
          + `${clip(show(filteredGroup.names), 300)}, wanted ${clip(show(KEPT_NAMES), 300)} if `
          + `the filter applied and ${clip(show(ALL_NAMES), 300)} if it was dropped.`);

  // ---- filter-in-folder-scope ------------------------------------------
  // Four reads over one filter: the library and the folder, each filtered and
  // unfiltered. A fifth names a folder that was never created, because a
  // parameter SharePoint ignores answers the same rows as one it never
  // received, and that read is what tells the two apart.
  const folderPath = pathAt(1);
  const plainFolder = await askView({ folder: folderPath });
  const filteredFolder = await askView({
    folder: folderPath, filterOn: FILTER_COL, filterValue: KEEP,
  });
  const bogusFolder = await askView({ folder: `${pathAt(0)}/${MISSING_FOLDER}` });
  const plainFolderNames = namesOf(plainFolder.rows);
  const filteredFolderNames = namesOf(filteredFolder.rows);
  const bogusNames = namesOf(bogusFolder.rows);
  const folderScopes = within(plainFolderNames, FOLDER_NAMES);
  const folderIgnored = plainFolder.res.ok && sameSet(plainFolderNames, plainNames);
  const filterInsideFolder = within(filteredFolderNames, FOLDER_KEPT)
    && filteredFolderNames.length < plainFolderNames.length;
  const folderFilterInert = filteredFolder.res.ok
    && sameSet(filteredFolderNames, plainFolderNames);
  publish('library.view.filter-in-folder-scope', Q.folderScope,
          (!plainFolder.res.ok && isRefusal(plainFolder.res.status))
            || (!filteredFolder.res.ok && isRefusal(filteredFolder.res.status))
            ? 'REFUSED'
            : plainFolderNames.length === 0 || filteredFolderNames.length === 0
              ? 'NOT ESTABLISHED'
              : folderIgnored
                ? 'THE FOLDER PARAMETER CHANGED NOTHING, THE READ IS LIBRARY-WIDE'
                : !folderScopes
                  ? 'NOT ESTABLISHED, THE FOLDER READ NAMES FILES FROM OUTSIDE IT'
                  : filterInsideFolder
                    ? 'THE FILTER APPLIES INSIDE THE FOLDER'
                    : folderFilterInert
                      ? 'THE FOLDER SCOPES, THE FILTER DID NOT APPLY'
                      : 'NOT ESTABLISHED, NEITHER SIGNATURE',
          `The folder ${show(folderPath)} holds ${clip(show(FOLDER_NAMES), 300)}, of which `
          + `${clip(show(FOLDER_KEPT), 300)} carry ${FILTER_COL} = ${show(KEEP)}, and the `
          + `library also holds ${clip(show(FILES.filter((file) => file.depth === 0)
            .map((file) => file.name)), 200)} at its root. `
          + `No folder named: unfiltered HTTP ${plainRoot.res.status} naming `
          + `${clip(show(plainNames), 300)}, filtered HTTP ${filteredRoot.res.status} naming `
          + `${clip(show(filteredNames), 300)}. Pointed at the folder: unfiltered HTTP `
          + `${plainFolder.res.status} naming ${clip(show(plainFolderNames), 300)}, filtered `
          + `HTTP ${filteredFolder.res.status} naming `
          + `${clip(show(filteredFolderNames), 300)}`
          + (filteredFolder.res.ok ? '' : `: ${clip(filteredFolder.res.text, 220)}`)
          + `. Pointed at ${show(MISSING_FOLDER)}, which this probe never creates: HTTP `
          + `${bogusFolder.res.status} naming ${clip(show(bogusNames), 300)}`
          + (sameSet(bogusNames, plainNames)
            ? ', the same rows as the read with no folder named, so a folder parameter this '
              + 'tenant cannot resolve is answered library-wide rather than refused'
            : '')
          + `. The folder read ${plainFolderNames.some(
            (name) => DEEPEST_NAMES.includes(name))
            ? 'DID' : 'did NOT'} descend past the folder it named, into `
          + `${clip(show(DEEPEST_NAMES), 200)}.`);

  // ---- filter-group-by-and-folder-scope --------------------------------
  // All three at once, against the same fixture the three pairwise reads above
  // ran on, so a mechanism that survives alone and is dropped here is visible as
  // a difference between two rows of this table rather than between two runs.
  const threeWay = await observe({
    groupBy: [GROUP_COL], filterOn: FILTER_COL, filterValue: KEEP, folder: folderPath,
  });
  const threeWayLabels = threeWay.labels.map(
    (label) => String(label[0] === null || label[0] === undefined ? '' : label[0]));
  const threeWayFolderHeld = within(threeWay.names, FOLDER_NAMES);
  const threeWayFilterHeld = within(threeWay.names, KEPT_NAMES);
  const threeWayGroupHeld = threeWay.honoured;
  const heldParts = [
    `folder scope ${threeWayFolderHeld ? 'held' : 'did NOT hold'}`,
    `filter ${threeWayFilterHeld ? 'held' : 'did NOT hold'}`,
    `group ${threeWayGroupHeld ? 'held' : 'did NOT hold'}`,
  ];
  publish('library.view.filter-group-by-and-folder-scope', Q.threeWay,
          threeWay.refused
            ? 'REFUSED'
            : threeWay.names.length === 0
              ? 'NOT ESTABLISHED, NO ROW CARRIED A FILE NAME'
              : threeWayFolderHeld && threeWayFilterHeld && threeWayGroupHeld
                ? 'ALL THREE COMPOSE'
                : threeWayFilterHeld && threeWayGroupHeld
                  ? 'THE FOLDER SCOPE IS DROPPED'
                  : threeWayFolderHeld && threeWayGroupHeld
                    ? 'THE FILTER IS DROPPED'
                    : threeWayFolderHeld && threeWayFilterHeld
                      ? 'THE GROUP IS DROPPED'
                      : `NOT ESTABLISHED, ${heldParts.join(', ')}`,
          `A <Where> on ${FILTER_COL} = ${show(KEEP)} and a <GroupBy> on ${GROUP_COL}, at `
          + `Scope="${DEEP_SCOPE}", pointed at ${show(folderPath)}. The rows that satisfy all `
          + `three are ${clip(show(FOLDER_KEPT), 300)}; the folder subtree alone is `
          + `${clip(show(FOLDER_NAMES), 300)} and the filter alone is `
          + `${clip(show(KEPT_NAMES), 300)}, so which mechanism was dropped is readable off `
          + `which set came back. ${threeWay.text}. Collapsed labels `
          + `${clip(show(threeWayLabels), 300)}. Each mechanism on its own, from the rows `
          + `above: the filter alone named ${clip(show(filteredNames), 200)}, the folder alone `
          + `named ${clip(show(plainFolderNames), 200)}, and the group alone returned `
          + `${groupSeen.collapsed.rows.length} collapsed row(s).`);

  return report();
})();
