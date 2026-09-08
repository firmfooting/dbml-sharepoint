/**
 * dbml-sharepoint PROBE: CAN A CUSTOM COLUMN BE INDEXED PAST 5,000 ITEMS, AND
 * DOES THE INDEX SERVE THE QUERY?
 *
 * ONE QUESTION, asked four ways:
 *   A document library past the list view threshold refuses a filter or a sort
 *   on any column but Id. Does adding an index to a custom column take, and
 *   does it turn that refusal into an answer?
 *
 * REVISION: af945971
 *
 * THE FIXTURE IS READ, NEVER REBUILT. `library-large-list-fixture-probe.js`
 * builds and owns 'dbmlsp Probe LargeLib': about 5,500 files named
 * dbmlsp-lv-00001.txt upward, carrying LVText, LVChoice, LVNumber, LVDate,
 * LVMultiChoice, LVLookup and the calculated LVCalc, with values a file's own
 * number gives it. That build takes several pastes, so nothing here uploads a
 * file, creates a column or writes an item value. This probe reads the fixture,
 * writes index flags onto its columns, and says so.
 *
 * WHAT IT LEAVES BEHIND, because a later probe will read it. Every column this
 * run indexes STAYS indexed unless REMOVE_INDEXES_AT_END is set on a following
 * paste. An indexed LVChoice changes what a filtered view over this fixture
 * does, so a probe written after this one must read the `Indexed` flag rather
 * than assume the fixture has none. The one other change is a Description
 * marker on LVText, written as the positive control and put back in the same
 * pass.
 *
 * WHAT #472 ALREADY SETTLED, and is therefore not re-asked here.
 * `library-index-threshold-probe.js` ran on 2026-09-08: past the threshold, a
 * selective filter on Id is SERVED, while Title, Name (FileLeafRef), Created,
 * Modified, Author and Editor are each REFUSED with SPQueryThrottledException.
 * Only Id carries a native index. That is the whole reason this probe exists:
 * if a system column cannot serve a query at size and cannot be indexed by
 * hand, the only route left for a filtered or sorted view is a custom column
 * with an index on it, and nothing in this repository has measured whether one
 * can be created past 5,000 items or whether it works when it is.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. All of it files under `library.large-list`,
 * the scope for reading this fixture past the threshold.
 *
 *   library.large-list.fixture-library-present
 *        Is the fixture library there, holding more than 5,000 files, with the
 *        seven contract columns reading back as their types? This probe does
 *        not build it. A library of the right name holding the wrong columns
 *        would answer every question below about something else.
 *   library.large-list.fixture-index-flags-clear
 *        Does every contract column read Indexed=false before this run writes
 *        anything? A column that arrives indexed cannot supply the unindexed
 *        half of a before/after measurement.
 *   library.large-list.control-id-query-served
 *        POSITIVE CONTROL: are a selective filter on Id and a sort on Id both
 *        served past the threshold? Id is the one natively indexed column, so
 *        this establishes that a served answer is observable on this library,
 *        at this size, in both shapes measured below. If it fails, every row
 *        here is void rather than open.
 *   library.large-list.control-absent-column-refused
 *        NEGATIVE CONTROL: is a filter naming a column the library does not
 *        hold refused WITHOUT the throttle signature? Every reading below turns
 *        on telling a throttle apart from a rejected request, and that
 *        discrimination is measured here rather than assumed.
 *   library.large-list.control-unindexed-filter-refused
 *        NEGATIVE CONTROL: is a selective filter on an unindexed contract
 *        column refused with the throttle signature? Without it the library is
 *        not demonstrably enforcing the threshold and nothing served below is
 *        evidence of anything.
 *   library.large-list.control-description-sticks
 *        POSITIVE CONTROL: does a Description MERGE on a contract column read
 *        back? A field MERGE that silently does nothing would report every
 *        column below as unindexable.
 *   library.large-list.control-unknown-property-refused
 *        NEGATIVE CONTROL: is a MERGE naming a property SP.Field does not have
 *        refused? Without it, "the write was accepted" says nothing.
 *   library.large-list.index-text-column
 *   library.large-list.index-number-column
 *   library.large-list.index-choice-column
 *   library.large-list.index-date-column
 *   library.large-list.index-multichoice-column
 *   library.large-list.index-lookup-column
 *   library.large-list.index-calculated-column
 *        QUESTION ONE, once per column: does `Indexed: true` take on a library
 *        already past 5,000 items, and does the flag read back? Three outcomes
 *        are distinguished and they are not the same finding: INDEXED (the
 *        write took and the flag reads true), SILENTLY IGNORED (the write was
 *        accepted and changed nothing, which is the failure class this
 *        repository exists to catch), and REFUSED (the server said no).
 *   library.large-list.index-removes-filter-throttle
 *        QUESTION TWO: on ONE column, measured before and after, does a
 *        selective `$filter` go from refused to served once the column is
 *        indexed?
 *   library.large-list.index-removes-sort-throttle
 *        QUESTION THREE: the same before and after for `$orderby`.
 *   library.large-list.index-is-per-column
 *        QUESTION FOUR: at one moment, is the indexed column's filter served
 *        while an unindexed sibling column's filter is still refused? An index
 *        that behaved as a library-wide switch would serve both, and a view
 *        built on the second column would then work by accident.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the fixture library exists, holds more
 *   than 5,000 files counted from the newest file name, and carries the seven
 *   contract columns as their declared types; every column reads Indexed=false
 *   before anything is written; a filter and a sort on Id are served; a filter
 *   naming an absent column is refused without the throttle signature; a filter
 *   on an unindexed contract column is refused with it; a Description MERGE
 *   sticks and an unknown property is refused.
 *   Observes (recorded, never asserted): whether each column accepts an index,
 *   what `Indexed` and `AutoIndexed` read afterwards, and whether the filter and
 *   the sort are served once the index is on. NOTHING here asserts that an index
 *   takes or that it works. A run where every column refuses an index is a
 *   successful run with an important answer.
 *
 * BEFORE AND AFTER ON THE SAME COLUMN, and why the order of this run is fixed.
 * A filter refused on LVChoice and served on LVNumber compares two columns, not
 * two states, so each of questions two and three sends its query on ONE column
 * with no index, then indexes that column, then sends the same query again.
 * That forces the run order: LVNumber and LVText are indexed first because the
 * before/after pairs need them; LVChoice is indexed LAST because question four
 * needs a column that is still unindexed at the moment the indexed one is
 * served.
 *
 * A BOUNDED WAIT AFTER THE INDEX WRITE. SharePoint builds the index behind the
 * `Indexed` flag, and the flag reading true does not say the build has
 * finished. A query sent the instant the flag flips can still be refused, and
 * reading that as "the index does not remove the throttle" would be the
 * strongest wrong claim this probe could make. So the after half is re-sent up
 * to INDEX_WAIT_ATTEMPTS times, INDEX_WAIT_MS apart, and a row still refused at
 * the end reports NOT ESTABLISHED with the attempts and the elapsed time,
 * never a conclusion. A 429, 408 or 503 stops the wait rather than being
 * retried: the wait is for an index to appear, not for a tenant to calm down.
 *
 * RE-PASTING IS THE FIX FOR A SLOW BUILD, at a price. The index write has
 * already happened, so a second paste measures the after half against a built
 * index. It cannot re-measure the before half, because the column is no longer
 * unindexed, and the rows say exactly that rather than quietly answering half a
 * question. Read the two transcripts together, or set REMOVE_INDEXES_AT_END,
 * re-paste to put the columns back, and then run the whole thing again.
 *
 * WHY OData, AND WHY THE FILTERS ARE SELECTIVE. Both from
 * `library-index-threshold-probe.js` and its live runs: past the threshold an
 * OData `$filter` no index can serve returns HTTP 500 SPQueryThrottledException
 * while the same predicate in CAML returns HTTP 200 with a silently partial
 * answer, so OData is the only surface that reports the threshold; and a result
 * that fills the page is a page ceiling rather than a count, so every filter
 * here matches a handful of known rows, `$top` is 100, and a full page is
 * recorded as answered but uncounted.
 *
 * THE ROW COUNT IS CHECKED AGAINST THE FIXTURE'S OWN FORMULAS. LVNumber is
 * `n % 1000` and LVText is `text-${n % 100}`, so the number of files matching
 * `LVNumber eq 7` is computable from the file count alone. A served answer
 * carrying the wrong number of rows is recorded as NOT ESTABLISHED: it means
 * the query was answered from something other than the fixture this probe
 * thinks it is reading.
 *
 * THE SORT ROW IS JUDGED ON STATUS, NOT ON COUNT. An `$orderby` with no filter
 * returns a page whatever the ordering is, so the count says nothing and the
 * observation is whether the server answered at all.
 *
 * THE HARNESS CLEANUP FLAG DOES NOTHING HERE, on purpose. resetList() is never
 * called and CLEANUP is ignored: it would recycle a fixture that takes six
 * pastes to build. The only teardown is REMOVE_INDEXES_AT_END, which puts the
 * index flags back and touches nothing else.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL is one Microsoft Learn documents,
 * because a wrong spelling returns 404, isRefusal() counts 404 as a refusal,
 * and the probe would then print a claim about SharePoint that was really a
 * typo:
 *   Field read and MERGE via `fields/getbyinternalnameortitle('<name>')`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Items, `$filter`, `$orderby` and `$top`:
 *     "Working with lists and list items with REST"
 *   The threshold and the index model it rests on:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 *
 * SCOPE OF CLAIMS: one tenant, one library, one caller context, one moment. The
 * threshold is documented as an effective figure rather than a constant, and
 * the negative controls are what detect a fixture sitting too close to it.
 *
 * HOW TO RUN: the run plan, in order
 *   1. Open the site holding 'dbmlsp Probe LargeLib'. If it is not built, run
 *      library-large-list-fixture-probe.js first; this probe will not build it.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED and ALLOW_WRITES true. Paste. Expect a couple of minutes,
 *      most of it the bounded waits after the two index writes.
 *   4. If a before/after row reads NOT ESTABLISHED because the query was still
 *      refused, re-paste after a few minutes and read the two transcripts
 *      together.
 *   5. Copy the whole RESULTS block back verbatim.
 *
 * STATUS: NOT YET RUN.
 *
 * WHEN FINISHED: set REMOVE_INDEXES_AT_END with both write gates and re-paste
 * to return the fixture's columns to unindexed. Leaving them indexed is a
 * choice, not a default: say which it was in the transcript.
 */
// finding: large-list-index-fixture-is-read-not-rebuilt - the fixture this
// probe measures costs six pastes to build, so nothing here uploads a file or
// creates a column, CLEANUP is ignored, and resetList() is never called. The
// contract it reads is stated in library-large-list-fixture-probe.js and the
// column types are read back rather than assumed.
// finding: large-list-index-flag-readback-precedes-the-write - every column's
// Indexed and AutoIndexed flags are read before this probe writes anything.
// threshold-index-probe.js watched SharePoint index a column on its own between
// two runs, so a column that arrives indexed is a live possibility and it
// destroys the unindexed half of a before/after pair. The rows that need one
// say so rather than reporting the after half alone.
// finding: large-list-index-build-is-asynchronous-so-the-after-half-waits - the
// Indexed flag reading true does not say the index has been built. The after
// half of each before/after pair is re-sent on a bounded wait and a query still
// refused at the end is recorded as NOT ESTABLISHED with the attempts and the
// elapsed time. Concluding "the index does not remove the throttle" from one
// immediate refusal would be the strongest wrong claim this probe could make.
// finding: large-list-index-leaves-the-fixture-indexed - every column this run
// indexes stays indexed unless REMOVE_INDEXES_AT_END is set on a following
// paste. A probe written after this one must READ the Indexed flag on this
// fixture rather than assume it carries none.
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

  log('INFO', 'probe revision af945971. Quote this when reporting results.');

  // Teardown, and the only thing here that undoes anything: MERGE Indexed
  // false back onto every column this run indexed, so the fixture returns to
  // the state a before/after measurement needs. Off, because a run whose after
  // half is still waiting on an index build needs the index to still be there.
  const REMOVE_INDEXES_AT_END = false;

  // ---- The fixture contract, restated ----------------------------------
  // Owned by library-large-list-fixture-probe.js. Read, never rebuilt.
  const LIB = 'dbmlsp Probe LargeLib';
  const TEXT = 'LVText';
  const CHOICE = 'LVChoice';
  const NUMBER = 'LVNumber';
  const DATE = 'LVDate';
  const MULTI = 'LVMultiChoice';
  const CALC = 'LVCalc';
  const LOOKUP = 'LVLookup';
  // Each column beside the type the fixture created it as. Read back, so a
  // library of the right name holding different columns is caught here rather
  // than reported as a platform finding.
  const COLUMN_TYPES = [
    [TEXT, 'Text'],
    [NUMBER, 'Number'],
    [CHOICE, 'Choice'],
    [DATE, 'DateTime'],
    [MULTI, 'MultiChoice'],
    [LOOKUP, 'Lookup'],
    [CALC, 'Calculated'],
  ];
  // The fixture's value formulas, for the three columns queried below. The
  // predicted row counts come from these and the file count, so a served
  // answer is checked rather than believed.
  const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
  const NUMBER_MATCH = 7;
  const TEXT_MATCH = 'text-7';
  const CHOICE_MATCH = CHOICES[0];

  // More than the documented 5,000, so every query below is asked past it.
  const FLOOR = 5001;
  // Well below any page ceiling, so a query that fills the page is visibly
  // uncounted rather than quietly rounded.
  const PAGE = 100;
  const FILE_NUMBER = /dbmlsp-lv-(\d+)\.txt$/;
  // The two strings a throttled query comes back with. Everything here turns
  // on telling this refusal from a rejected request, which is what
  // control-absent-column-refused measures.
  const THROTTLE = /exceeds the list view threshold|SPQueryThrottledException/i;
  // A column name the library does not hold, for the negative control.
  const ABSENT_COLUMN = 'LVNoSuchColumnAtAll';
  // A name SP.Field does not have. Deliberately not a near-miss of a real
  // property: the control asks whether an unknown name is refused, not whether
  // a typo is tolerated.
  const UNKNOWN_PROPERTY = 'NoSuchFieldPropertyAtAll';
  const DESCRIPTION_MARKER = 'dbmlsp large-list index control marker';
  // One bounded re-read after a write. Same figure and same reasoning as
  // library-index-probe.js: a readback racing a write is a false negative, a
  // retry loop eventually passes anything.
  const REREAD_MS = 1500;
  // The wait for an asynchronous index build. Bounded, and the row reports how
  // long it waited rather than concluding when it runs out.
  const INDEX_WAIT_ATTEMPTS = 10;
  const INDEX_WAIT_MS = 6000;

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const lit = (value) => String(value).replace(/'/g, "''");
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const fieldPath = (name) =>
    `${libPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  // The seven index questions. The table is the only place these ids are
  // written, so the rows registered up front, the rows recorded and
  // probe-catalog.json cannot drift apart.
  //
  // `phase` is the run order and it is not cosmetic. Phase 1 is indexed before
  // the before/after pairs need it; phase 2 is indexed after question four has
  // used LVChoice as a column that is still unindexed.
  const CANDIDATES = [
    {
      id: 'library.large-list.index-text-column',
      question: 'Does Indexed=true take on LVText (Text) past 5,000 items',
      field: TEXT,
      phase: 1,
    },
    {
      id: 'library.large-list.index-number-column',
      question: 'Does Indexed=true take on LVNumber (Number) past 5,000 items',
      field: NUMBER,
      phase: 1,
    },
    {
      id: 'library.large-list.index-choice-column',
      question: 'Does Indexed=true take on LVChoice (Choice) past 5,000 items',
      field: CHOICE,
      phase: 2,
    },
    {
      id: 'library.large-list.index-date-column',
      question: 'Does Indexed=true take on LVDate (DateTime) past 5,000 items',
      field: DATE,
      phase: 2,
    },
    {
      id: 'library.large-list.index-multichoice-column',
      question: 'Does Indexed=true take on LVMultiChoice (MultiChoice) past 5,000 items',
      field: MULTI,
      phase: 2,
    },
    {
      id: 'library.large-list.index-lookup-column',
      question: 'Does Indexed=true take on LVLookup (Lookup) past 5,000 items',
      field: LOOKUP,
      phase: 2,
    },
    {
      id: 'library.large-list.index-calculated-column',
      question: 'Does Indexed=true take on LVCalc (Calculated) past 5,000 items',
      field: CALC,
      phase: 2,
    },
  ];

  if (!CONFIRMED) {
    log('INFO', `Would READ the existing library '${LIB}' on ${WEB}: its file count, its`);
    log('INFO', 'seven columns and their Indexed and AutoIndexed flags. It builds NOTHING.');
    log('INFO', 'It would then MERGE Indexed=true onto each of those seven columns, and');
    log('INFO', `send selective OData filters and sorts reading at most ${PAGE} rows each,`);
    log('INFO', 'before and after the index, to see whether the throttle lifts.');
    log('INFO', 'It also writes a Description marker on one column as a control and puts');
    log('INFO', 'it straight back. No file, item, column or list is created or deleted.');
    log('INFO', REMOVE_INDEXES_AT_END
      ? 'REMOVE_INDEXES_AT_END is ON: the index flags would be put back at the end.'
      : 'REMOVE_INDEXES_AT_END is off: the columns would be LEFT indexed, and a later'
        + ' probe reading this fixture would see that.');
    log('INFO', 'CLEANUP does NOTHING in this probe: it would recycle the fixture.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write index flags.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }
  if (CLEANUP) {
    log('INFO', 'CLEANUP is on and is IGNORED here: it would recycle a fixture that takes');
    log('INFO', 'six pastes to build. The only teardown is REMOVE_INDEXES_AT_END.');
  }

  expect('library.large-list.fixture-library-present', `The fixture library '${LIB}' is present, holds more than 5,000 files and carries the seven contract columns`);
  expect('library.large-list.fixture-index-flags-clear', 'Every contract column reads Indexed=false before this run writes anything');
  expect('library.large-list.control-id-query-served', 'POSITIVE CONTROL: a selective filter on Id and a sort on Id are both served past the threshold');
  expect('library.large-list.control-absent-column-refused', 'NEGATIVE CONTROL: a filter naming a column the library does not hold is refused WITHOUT the throttle signature');
  expect('library.large-list.control-unindexed-filter-refused', 'NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature');
  expect('library.large-list.control-description-sticks', 'POSITIVE CONTROL: a Description MERGE on a contract column reads back');
  expect('library.large-list.control-unknown-property-refused', 'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused');
  for (const row of CANDIDATES) expect(row.id, row.question);
  expect('library.large-list.index-removes-filter-throttle', 'On one column, does a selective $filter go from refused to served once the column is indexed');
  expect('library.large-list.index-removes-sort-throttle', 'On one column, does an $orderby go from refused to served once the column is indexed');
  expect('library.large-list.index-is-per-column', 'With one column indexed, is its filter served while an unindexed sibling column is still refused');

  // Every row still carrying the harness sentinel, stamped with one reason.
  // A run that stops early must not report questions it never asked as
  // merely unreached.
  const abortRemaining = (outcome, why) => {
    for (const row of RESULTS) {
      if (row.evidence === 'the run did not reach this question') {
        record(row.id, row.question, outcome, why);
      }
    }
  };

  // ---- Reading instruments ---------------------------------------------
  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the whole request, and every column would
  // then read as unreadable rather than as missing one property.
  const readField = async (name) => spGet(fieldPath(name));

  const mergeField = async (name, body, type) => {
    const digest = await getDigest();
    return spPost(fieldPath(name), { __metadata: { type }, ...body }, digest, {
      Accept: 'application/json;odata=verbose',
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };

  // The entity type SharePoint itself reports for a field, read verbose
  // because nometadata is defined by not carrying it. Only ever consulted
  // after a refusal, to separate a rejected TYPE from a rejected WRITE.
  const entityTypeOf = async (name) => {
    try {
      const res = await fetch(`${WEB}/_api/${fieldPath(name)}`, {
        headers: { Accept: 'application/json;odata=verbose' },
      });
      if (!res.ok) return null;
      const body = await res.json().catch(() => null);
      return (body && body.d && body.d.__metadata && body.d.__metadata.type) || null;
    } catch {
      return null;
    }
  };

  const indexedNow = (read) => !readFailed(read) && read.body.Indexed === true;

  // One query, classified from the FULL body and quoted from a clipped copy.
  // Classifying from the clipped text would miss a throttle signature that
  // sits past the clip.
  const askQuery = async (query, label) => {
    const r = await spGet(`${libPath}/items?$select=Id&$top=${PAGE}&${query}`);
    const raw = r.body ? JSON.stringify(r.body) : '';
    return {
      ok: r.ok,
      status: r.status,
      label,
      rows: (r.ok && r.body && Array.isArray(r.body.value)) ? r.body.value.length : -1,
      throttled: THROTTLE.test(raw),
      transient: r.status === 429 || r.status === 408 || r.status === 503,
      body: raw ? clip(raw, 260) : '(no body)',
    };
  };
  const askFilter = (filter) =>
    askQuery(`$filter=${encodeURIComponent(filter)}`, `$filter=${filter}`);
  const askSort = (column) =>
    askQuery(`$orderby=${encodeURIComponent(`${column} asc`)}`, `$orderby=${column} asc`);

  // `expected` is the row count the fixture's own formulas give this filter.
  // null means the count is not being compared, which is only ever the case
  // for a filter whose match set is bigger than the page.
  const judge = (result, expected) => {
    if (result.transient) return 'NOT ESTABLISHED (throttled)';
    if (result.throttled) return 'REFUSED (threshold)';
    if (isRefusal(result.status)) return 'REFUSED (request rejected; read the body)';
    if (!result.ok) return `NOT ESTABLISHED (HTTP ${result.status})`;
    if (result.rows === PAGE) return 'SERVED (page full, so the count is unreadable)';
    if (expected !== null && result.rows !== expected) {
      return `NOT ESTABLISHED (served ${result.rows} row(s) where the fixture gives ${expected})`;
    }
    return `SERVED (${result.rows} row(s))`;
  };

  // A sort with no filter returns a page whatever the ordering is, so the
  // count says nothing and the observation is whether the server answered.
  const judgeSort = (result) => {
    if (result.transient) return 'NOT ESTABLISHED (throttled)';
    if (result.throttled) return 'REFUSED (threshold)';
    if (isRefusal(result.status)) return 'REFUSED (request rejected; read the body)';
    if (!result.ok) return `NOT ESTABLISHED (HTTP ${result.status})`;
    return `SERVED (${result.rows} row(s) of the ${PAGE} asked for)`;
  };

  // The bounded wait for an asynchronous index build. A transient status stops
  // it: this waits for an index to appear, not for a tenant to calm down.
  const untilServed = async (ask) => {
    const started = Date.now();
    let attempts = 0;
    let last = null;
    while (attempts < INDEX_WAIT_ATTEMPTS) {
      if (attempts) await sleep(INDEX_WAIT_MS);
      last = await ask();
      attempts += 1;
      if (last.ok || last.transient) break;
    }
    return { result: last, attempts, waitedMs: Date.now() - started };
  };

  // ---- fixture-library-present -----------------------------------------
  const libRead = await spGet(`${libPath}?$select=Title,BaseTemplate,ItemCount`);
  const libOk = !readFailed(libRead);
  // Counted from the newest file NAME, never from ItemCount, and read with the
  // one ordering the fixture probe established is served past the threshold:
  // $orderby=Id desc on the natively indexed Id.
  const newest = libOk
    ? await spGet(`${libPath}/items?$select=Id,FileLeafRef&$orderby=Id desc&$top=1`)
    : null;
  const newestRow = (newest && !readFailed(newest) && Array.isArray(newest.body.value)
    && newest.body.value.length) ? newest.body.value[0] : null;
  const digits = newestRow ? String(newestRow.FileLeafRef || '').match(FILE_NUMBER) : null;
  const count = digits ? Number(digits[1]) : 0;
  const newestId = newestRow ? newestRow.Id : null;

  const flags = {};
  const columnProblems = [];
  if (libOk) {
    for (const [name, wanted] of COLUMN_TYPES) {
      const read = await readField(name);
      const ok = !readFailed(read);
      flags[name] = {
        read: ok,
        status: read.status,
        type: ok ? read.body.TypeAsString : null,
        indexed: ok && typeof read.body.Indexed === 'boolean' ? read.body.Indexed : null,
        auto: ok && typeof read.body.AutoIndexed === 'boolean' ? read.body.AutoIndexed : null,
        description: ok ? read.body.Description : null,
      };
      if (!ok) columnProblems.push(`${name} did not read back (HTTP ${read.status})`);
      else if (flags[name].type !== wanted) {
        columnProblems.push(`${name} is ${show(flags[name].type)}, wanted ${wanted}`);
      }
    }
  }

  const present = libOk && count >= FLOOR && columnProblems.length === 0;
  record('library.large-list.fixture-library-present',
         `The fixture library '${LIB}' is present, holds more than 5,000 files and carries the seven contract columns`,
         !libOk ? 'ABORTED' : count < FLOOR ? 'SHORT' : columnProblems.length ? 'FAIL' : 'PASS',
         (libOk
           ? `the newest file is ${show(newestRow ? newestRow.FileLeafRef : null)}, so the library `
             + `holds ${count} file(s) against the ${FLOOR} this probe needs; ItemCount reads `
             + `${show(libRead.body.ItemCount)} and is not what the count is taken from`
           : `the library did not read back (HTTP ${libRead.status}): ${clip(show(libRead.body), 200)}`)
         + '. '
         + (columnProblems.length
           ? `column problems: ${columnProblems.join('; ')}`
           : libOk ? 'every contract column read back as its declared type' : '')
         + (present
           ? '. This probe does not build the fixture. It is owned by '
             + 'library-large-list-fixture-probe.js.'
           : '. Run library-large-list-fixture-probe.js until its fixture rows read PASS, '
             + 'then re-paste this one.'));

  // ---- fixture-index-flags-clear ---------------------------------------
  const flagNote = (name) => `${name}: Indexed=${show(flags[name] ? flags[name].indexed : null)}`
    + `, AutoIndexed=${show(flags[name] ? flags[name].auto : null)}`;
  const readable = libOk && COLUMN_TYPES.every(([name]) => flags[name] && flags[name].indexed !== null);
  const alreadyIndexed = libOk
    ? COLUMN_TYPES.filter(([name]) => flags[name] && flags[name].indexed === true).map(([name]) => name)
    : [];
  record('library.large-list.fixture-index-flags-clear',
         'Every contract column reads Indexed=false before this run writes anything',
         !readable ? 'ABORTED' : alreadyIndexed.length ? 'ALREADY INDEXED' : 'PASS',
         (libOk ? COLUMN_TYPES.map(([name]) => flagNote(name)).join('; ') : 'no column was read')
         + (alreadyIndexed.length
           ? `. ${alreadyIndexed.join(', ')} arrived indexed, so the unindexed half of any `
             + 'before/after measurement on those columns cannot be taken this run. Set '
             + 'REMOVE_INDEXES_AT_END, re-paste to put them back, then run again.'
           : readable ? '. The before half of every measurement below is therefore real.' : ''),
         // Explicit, because the classifier would read ALREADY INDEXED as
         // settled. The precondition was not met and a later run can meet it,
         // which is open rather than void.
         !readable ? 'open' : alreadyIndexed.length ? 'open' : 'settled');

  if (!present || !readable) {
    abortRemaining('ABORTED',
                   'the fixture was not readable as this probe needs it, so no query was sent '
                   + 'and no index flag was written');
    report();
    return;
  }

  // The predicted row counts, from the fixture's formulas and the file count.
  // A served answer carrying a different number was answered from something
  // other than the fixture this probe thinks it is reading.
  const tally = (predicate) => {
    let total = 0;
    for (let n = 1; n <= count; n += 1) if (predicate(n)) total += 1;
    return total;
  };
  const numberExpected = tally((n) => n % 1000 === NUMBER_MATCH);
  const textExpected = tally((n) => `text-${n % 100}` === TEXT_MATCH);
  // Bigger than the page on any real fixture, so its count is not compared.
  // It is the sibling column, where the observation is served against refused.
  const choiceExpected = tally((n) => CHOICES[n % 4] === CHOICE_MATCH);

  const numberFilter = `${NUMBER} eq ${NUMBER_MATCH}`;
  const textFilter = `${TEXT} eq '${lit(TEXT_MATCH)}'`;
  const choiceFilter = `${CHOICE} eq '${lit(CHOICE_MATCH)}'`;

  // ---- control-id-query-served -----------------------------------------
  const idFilter = await askFilter(`Id eq ${newestId}`);
  const idSort = await askSort('Id');
  const idFilterOutcome = judge(idFilter, 1);
  const idSortOutcome = judgeSort(idSort);
  const idServed = idFilterOutcome.startsWith('SERVED') && idSortOutcome.startsWith('SERVED');
  record('library.large-list.control-id-query-served',
         'POSITIVE CONTROL: a selective filter on Id and a sort on Id are both served past the threshold',
         idServed ? 'SERVED (filter and sort)' : 'CONTROL FAILED, METHOD VOID',
         `${idFilter.label} on ${count} file(s): HTTP ${idFilter.status}, ${idFilterOutcome}; `
         + `${idSort.label}: HTTP ${idSort.status}, ${idSortOutcome}`
         + (idServed
           ? '. A served answer is therefore observable on this library, at this size, in both '
             + 'shapes measured below.'
           : `. Bodies: ${idFilter.body} / ${idSort.body}. Id is the one natively indexed column `
             + '(library-index-threshold-probe.js, 2026-09-08), so a refusal here says the '
             + 'method cannot observe an index at all, not that an index is missing.'));

  // ---- control-absent-column-refused -----------------------------------
  const absent = await askFilter(`${ABSENT_COLUMN} eq 'x'`);
  const absentRefused = isRefusal(absent.status) && !absent.throttled;
  record('library.large-list.control-absent-column-refused',
         'NEGATIVE CONTROL: a filter naming a column the library does not hold is refused WITHOUT the throttle signature',
         absentRefused ? 'REFUSED (request rejected, no throttle signature)'
           : absent.throttled ? 'CONTROL FAILED, METHOD VOID'
             : 'CONTROL FAILED, METHOD VOID',
         `${absent.label}: HTTP ${absent.status}, throttle signature `
         + `${absent.throttled ? 'PRESENT' : 'absent'}: ${absent.body}`
         + (absentRefused
           ? '. A rejected request and a throttled one are therefore distinguishable, which is '
             + 'what every refusal below is read against.'
           : absent.throttled
             ? '. A filter on a column that does not exist came back carrying the throttle '
               + 'signature, so no refusal below can be attributed to the threshold.'
             : '. The server did not refuse a filter on a column that does not exist, so a '
               + 'refusal below cannot be read as the server rejecting the query either.'));

  // ---- control-unindexed-filter-refused --------------------------------
  const choiceBefore = await askFilter(choiceFilter);
  const choiceBeforeOutcome = judge(choiceBefore, null);
  const throttleEnforced = choiceBeforeOutcome.startsWith('REFUSED (threshold)')
    && flags[CHOICE].indexed === false && absentRefused;
  record('library.large-list.control-unindexed-filter-refused',
         'NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature',
         throttleEnforced ? 'REFUSED (threshold)' : 'CONTROL FAILED, METHOD VOID',
         `${choiceBefore.label} on ${count} file(s), matching ${choiceExpected} of them: HTTP `
         + `${choiceBefore.status}, ${choiceBeforeOutcome}. ${flagNote(CHOICE)}: ${choiceBefore.body}`
         + (throttleEnforced
           ? '. The library is therefore past the threshold and throttling is enforced on it, so '
             + 'an answer served after an index is worth something.'
           : '. Without a refusal here nothing served below is evidence of an index: the library '
             + 'may simply not be far enough past the threshold for this tenant to enforce it.'));

  // ---- control-description-sticks --------------------------------------
  // The field MERGE itself, proved on a property whose readback is not in
  // doubt. A MERGE that silently does nothing would report every column below
  // as unindexable.
  const priorDescription = flags[TEXT].description;
  const setDesc = await mergeField(TEXT, { Description: DESCRIPTION_MARKER }, 'SP.Field');
  let descRead = await readField(TEXT);
  let descReRead = false;
  const descriptionNow = () => (readFailed(descRead) ? null : descRead.body.Description);
  if (setDesc.ok && descriptionNow() !== DESCRIPTION_MARKER) {
    await sleep(REREAD_MS);
    descRead = await readField(TEXT);
    descReRead = true;
  }
  const descSticks = setDesc.ok && descriptionNow() === DESCRIPTION_MARKER;
  record('library.large-list.control-description-sticks',
         'POSITIVE CONTROL: a Description MERGE on a contract column reads back',
         descSticks ? 'DESCRIPTION STUCK' : 'CONTROL FAILED, METHOD VOID',
         `MERGE Description on ${TEXT} returned HTTP ${setDesc.status}; it reads back `
         + `${show(descriptionNow())}`
         + (descReRead ? `, on a re-read ${REREAD_MS} ms later` : '')
         + (descSticks
           ? '. A field MERGE reaches this library\'s columns, so a column that does not take an '
             + 'index below is the column refusing and not the method failing.'
           : `: ${clip(setDesc.text, 200)}. Nothing below can distinguish a column that refuses `
             + 'an index from a MERGE that never arrived.'));
  if (descSticks) {
    // The marker is this probe's, not the fixture's. Put it back in the same
    // pass, and say so loudly if that fails.
    const restored = await mergeField(
      TEXT, { Description: priorDescription === null || priorDescription === undefined ? '' : priorDescription },
      'SP.Field');
    log(restored.ok ? 'OK' : 'FAIL',
        restored.ok
          ? `Description on ${TEXT} put back to ${show(priorDescription)}.`
          : `Description on ${TEXT} is still the control marker: the restore returned HTTP `
            + `${restored.status} ${clip(restored.text, 200)}`);
  }

  // ---- control-unknown-property-refused --------------------------------
  const unknown = await mergeField(TEXT, { [UNKNOWN_PROPERTY]: 'x' }, 'SP.Field');
  const unknownRefused = isRefusal(unknown.status);
  record('library.large-list.control-unknown-property-refused',
         'NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused',
         unknownRefused ? 'REFUSED' : 'CONTROL FAILED, METHOD VOID',
         `MERGE ${UNKNOWN_PROPERTY} on ${TEXT} returned HTTP ${unknown.status}: `
         + `${clip(unknown.text, 200)}`
         + (unknownRefused
           ? '. The endpoint therefore rejects a property it does not know, so "the write was '
             + 'accepted" below means the property was recognised.'
           : '. An unknown property was ACCEPTED, so acceptance of Indexed=true below says '
             + 'nothing about whether the property was recognised.'));

  // ---- The unindexed halves, taken before anything is written ----------
  // Both filter candidates and both sort candidates, so the before/after pairs
  // can use whichever column turns out to accept an index.
  const beforeFilter = {};
  beforeFilter[NUMBER] = await askFilter(numberFilter);
  beforeFilter[TEXT] = await askFilter(textFilter);
  const beforeSort = {};
  beforeSort[TEXT] = await askSort(TEXT);
  beforeSort[NUMBER] = await askSort(NUMBER);

  // ---- The seven index writes, phase 1 ---------------------------------
  const indexResults = {};
  const indexColumn = async (name) => {
    const before = flags[name];
    if (before.indexed === true) {
      return {
        outcome: 'NOT ESTABLISHED',
        indexed: true,
        evidence: `${name} already read Indexed=true before this run wrote anything, so a `
          + 'readback of true would say nothing about the write. threshold-index-probe.js '
          + 'measured SharePoint indexing a column on its own between two runs, so this is a '
          + 'live possibility. Set REMOVE_INDEXES_AT_END, re-paste, then run again.',
      };
    }

    const wrote = await mergeField(name, { Indexed: true }, 'SP.Field');
    let after = await readField(name);
    let reRead = false;
    if (wrote.ok && !indexedNow(after)) {
      await sleep(REREAD_MS);
      after = await readField(name);
      reRead = true;
    }
    const afterNote = readFailed(after)
      ? `unreadable after (HTTP ${after.status})`
      : `Indexed=${show(after.body.Indexed)}, AutoIndexed=${show(after.body.AutoIndexed)} after`;

    if (wrote.ok) {
      const stuck = indexedNow(after);
      return {
        outcome: stuck ? 'INDEXED' : 'SILENTLY IGNORED',
        indexed: stuck,
        evidence: `MERGE Indexed:true as SP.Field on a library of ${count} file(s) returned HTTP `
          + `${wrote.status}; ${flagNote(name)} before, ${afterNote}`
          + (reRead ? `, on a re-read ${REREAD_MS} ms later` : '')
          + (stuck ? '' : '. The write was accepted and changed nothing, which is the failure '
            + 'class this repository exists to find'),
      };
    }

    if (!isRefusal(wrote.status)) {
      return {
        outcome: 'NOT ESTABLISHED',
        indexed: false,
        evidence: `the MERGE failed with HTTP ${wrote.status}, which is about who is asking or `
          + `about the moment rather than the server refusing it: ${clip(wrote.text, 200)}`,
      };
    }

    // Refused as SP.Field. Ask once more with the type SharePoint itself
    // reports for this field, because a rejected type hint and a rejected
    // write are otherwise the same observation.
    const ownType = await entityTypeOf(name);
    const retried = ownType && ownType !== 'SP.Field'
      ? await mergeField(name, { Indexed: true }, ownType)
      : null;
    const afterRetry = retried && retried.ok ? await readField(name) : null;
    const retryStuck = afterRetry !== null && indexedNow(afterRetry);
    const asBase = `MERGE Indexed:true as SP.Field was REFUSED, HTTP ${wrote.status}: `
      + clip(wrote.text, 240);
    if (retryStuck) {
      return {
        outcome: 'INDEXED',
        indexed: true,
        evidence: `${asBase}. Retried naming the type SharePoint reports for this field, `
          + `${ownType}: HTTP ${retried.status}, and Indexed read back true. The refusal was the `
          + 'TYPE HINT, not the column. Note the deployer sends SP.Field.',
      };
    }
    return {
      outcome: 'REFUSED',
      indexed: false,
      evidence: `${asBase}. `
        + (retried === null
          ? (ownType === null
            ? 'The field entity type could not be read, so a type mismatch was not ruled out.'
            : `SharePoint reports this field as ${ownType}, the same base type, so there was no `
              + 'type mismatch to rule out.')
          : `Retried as ${ownType}: HTTP ${retried.status}`
            + (retried.ok
              ? `, and Indexed read back `
                + `${afterRetry && !readFailed(afterRetry) ? show(afterRetry.body.Indexed) : 'unreadable'}`
              : `: ${clip(retried.text, 160)}`)
            + '. The refusal is the column, not the type hint.'),
    };
  };

  const runIndex = async (row) => {
    const result = await indexColumn(row.field);
    indexResults[row.field] = result;
    record(row.id, row.question, result.outcome, result.evidence);
  };

  for (const row of CANDIDATES) {
    if (row.phase === 1) await runIndex(row);
  }

  // Which column can carry a before/after pair: it started unindexed and it
  // took an index. Named in preference order, and the row reports which one
  // answered it.
  const usable = (name) => flags[name].indexed === false
    && indexResults[name] !== undefined && indexResults[name].indexed === true;

  // ---- index-removes-filter-throttle -----------------------------------
  const FILTER_TRIES = [
    { field: NUMBER, filter: numberFilter, expected: numberExpected },
    { field: TEXT, filter: textFilter, expected: textExpected },
  ];
  const filterPick = FILTER_TRIES.find((row) => usable(row.field)) || null;
  let servedFilter = null;
  if (!idServed) {
    record('library.large-list.index-removes-filter-throttle',
           'On one column, does a selective $filter go from refused to served once the column is indexed',
           'VOID',
           'the positive control was not served, so this method was never shown to observe a '
           + 'served answer on this library at all',
           'void');
  } else if (filterPick === null) {
    record('library.large-list.index-removes-filter-throttle',
           'On one column, does a selective $filter go from refused to served once the column is indexed',
           'NOT ESTABLISHED',
           `neither ${NUMBER} nor ${TEXT} both started unindexed and took an index `
           + `(${NUMBER}: ${indexResults[NUMBER] ? indexResults[NUMBER].outcome : 'not attempted'}, `
           + `${TEXT}: ${indexResults[TEXT] ? indexResults[TEXT].outcome : 'not attempted'}), so `
           + 'there is no column here whose before and after states are both measurable');
  } else {
    const beforeOutcome = judge(beforeFilter[filterPick.field], filterPick.expected);
    const beforeRefused = beforeOutcome.startsWith('REFUSED (threshold)');
    if (!beforeRefused) {
      record('library.large-list.index-removes-filter-throttle',
             'On one column, does a selective $filter go from refused to served once the column is indexed',
             'NOT ESTABLISHED',
             `${beforeFilter[filterPick.field].label} was ${beforeOutcome} with no index on `
             + `${filterPick.field} (HTTP ${beforeFilter[filterPick.field].status}: `
             + `${beforeFilter[filterPick.field].body}), so there was no throttle for an index to `
             + 'remove and the after half would measure nothing');
    } else {
      const waited = await untilServed(() => askFilter(filterPick.filter));
      const afterOutcome = judge(waited.result, filterPick.expected);
      const served = afterOutcome.startsWith('SERVED');
      if (served) servedFilter = filterPick;
      record('library.large-list.index-removes-filter-throttle',
             'On one column, does a selective $filter go from refused to served once the column is indexed',
             served ? 'INDEX SERVES THE FILTER'
               : `NOT ESTABLISHED (still refused after ${waited.attempts} attempt(s))`,
             `${filterPick.filter} on ${count} file(s), matching ${filterPick.expected} of them. `
             + `Before: HTTP ${beforeFilter[filterPick.field].status}, ${beforeOutcome}. After `
             + `Indexed=true on ${filterPick.field}: HTTP ${waited.result.status}, `
             + `${afterOutcome}, over ${waited.attempts} attempt(s) and ${waited.waitedMs} ms`
             + (served
               ? '. The refusal was the missing index and nothing else about the query changed.'
               : `: ${waited.result.body}. SharePoint builds the index behind the flag, so this `
                 + 'does not establish that the index fails to lift the throttle. Re-paste in a '
                 + 'few minutes: the index is already written, so a second run measures the '
                 + 'after half alone.'));
    }
  }

  // ---- index-removes-sort-throttle -------------------------------------
  const SORT_TRIES = [{ field: TEXT }, { field: NUMBER }];
  const sortPick = SORT_TRIES.find((row) => usable(row.field)) || null;
  if (!idServed) {
    record('library.large-list.index-removes-sort-throttle',
           'On one column, does an $orderby go from refused to served once the column is indexed',
           'VOID',
           'the positive control was not served, so a sort was never shown to be answerable on '
           + 'this library at all',
           'void');
  } else if (sortPick === null) {
    record('library.large-list.index-removes-sort-throttle',
           'On one column, does an $orderby go from refused to served once the column is indexed',
           'NOT ESTABLISHED',
           `neither ${TEXT} nor ${NUMBER} both started unindexed and took an index, so there is `
           + 'no column here whose before and after states are both measurable');
  } else {
    const beforeOutcome = judgeSort(beforeSort[sortPick.field]);
    const beforeRefused = beforeOutcome.startsWith('REFUSED (threshold)');
    if (!beforeRefused) {
      record('library.large-list.index-removes-sort-throttle',
             'On one column, does an $orderby go from refused to served once the column is indexed',
             'NOT ESTABLISHED',
             `${beforeSort[sortPick.field].label} was ${beforeOutcome} with no index on `
             + `${sortPick.field} (HTTP ${beforeSort[sortPick.field].status}: `
             + `${beforeSort[sortPick.field].body}), so there was no throttle for an index to remove`);
    } else {
      const waited = await untilServed(() => askSort(sortPick.field));
      const afterOutcome = judgeSort(waited.result);
      const served = afterOutcome.startsWith('SERVED');
      record('library.large-list.index-removes-sort-throttle',
             'On one column, does an $orderby go from refused to served once the column is indexed',
             served ? 'INDEX SERVES THE SORT'
               : `NOT ESTABLISHED (still refused after ${waited.attempts} attempt(s))`,
             `$orderby=${sortPick.field} asc on ${count} file(s), judged on status rather than on `
             + `row count. Before: HTTP ${beforeSort[sortPick.field].status}, ${beforeOutcome}. `
             + `After Indexed=true on ${sortPick.field}: HTTP ${waited.result.status}, `
             + `${afterOutcome}, over ${waited.attempts} attempt(s) and ${waited.waitedMs} ms`
             + (served
               ? '. A sort refused without an index is answered with one.'
               : `: ${waited.result.body}. The index build is asynchronous, so re-paste in a few `
                 + 'minutes and read the two transcripts together.'));
    }
  }

  // ---- index-is-per-column ---------------------------------------------
  // The pair is sent at ONE moment, with LVChoice still unindexed. That is why
  // LVChoice is a phase 2 write.
  if (servedFilter === null) {
    record('library.large-list.index-is-per-column',
           'With one column indexed, is its filter served while an unindexed sibling column is still refused',
           'NOT ESTABLISHED',
           'no indexed filter was served, so there is no served half to pair an unindexed '
           + 'sibling against');
  } else if (flags[CHOICE].indexed !== false) {
    record('library.large-list.index-is-per-column',
           'With one column indexed, is its filter served while an unindexed sibling column is still refused',
           'NOT ESTABLISHED',
           `${CHOICE} did not start unindexed (${flagNote(CHOICE)}), so it is not an unindexed `
           + 'sibling and the pair compares nothing');
  } else {
    const pairIndexed = await askFilter(servedFilter.filter);
    const pairSibling = await askFilter(choiceFilter);
    const pairIndexedOutcome = judge(pairIndexed, servedFilter.expected);
    const pairSiblingOutcome = judge(pairSibling, null);
    const indexedServed = pairIndexedOutcome.startsWith('SERVED');
    const siblingRefused = pairSiblingOutcome.startsWith('REFUSED (threshold)');
    record('library.large-list.index-is-per-column',
           'With one column indexed, is its filter served while an unindexed sibling column is still refused',
           indexedServed && siblingRefused ? 'PER COLUMN'
             : indexedServed && !siblingRefused ? 'BOTH SERVED'
               : 'NOT ESTABLISHED',
           `at one moment: ${pairIndexed.label} on the indexed ${servedFilter.field} was HTTP `
           + `${pairIndexed.status}, ${pairIndexedOutcome}; ${pairSibling.label} on the unindexed `
           + `${CHOICE} was HTTP ${pairSibling.status}, ${pairSiblingOutcome}. ${flagNote(CHOICE)}`
           + (indexedServed && siblingRefused
             ? '. The index is a property of the column, not a switch that lifts the threshold '
               + 'for the library, so a view filtering on an unindexed column still breaks at '
               + 'this size.'
             : indexedServed
               ? '. The unindexed sibling was served too, so an index cannot be what made the '
                 + 'first query answerable and every served answer here needs another '
                 + 'explanation.'
               : '. The indexed column was not served at this point, so the pair has no served '
                 + 'half and says nothing.'));
  }

  // ---- The seven index writes, phase 2 ---------------------------------
  for (const row of CANDIDATES) {
    if (row.phase === 2) await runIndex(row);
  }

  report();

  // ---- Teardown ---------------------------------------------------------
  const indexedByThisRun = CANDIDATES
    .filter((row) => indexResults[row.field] && indexResults[row.field].indexed
      && flags[row.field].indexed === false)
    .map((row) => row.field);
  if (!REMOVE_INDEXES_AT_END) {
    log('INFO', indexedByThisRun.length
      ? `The fixture's columns are LEFT INDEXED: ${indexedByThisRun.join(', ')}.`
      : 'No column was indexed by this run, so the fixture is unchanged.');
    log('INFO', 'A probe written after this one must READ the Indexed flag on this fixture');
    log('INFO', 'rather than assume it carries none. To put them back, set');
    log('INFO', 'REMOVE_INDEXES_AT_END = true with both write gates and re-paste.');
    return;
  }

  for (const name of indexedByThisRun) {
    const off = await mergeField(name, { Indexed: false }, 'SP.Field');
    const back = await readField(name);
    const cleared = off.ok && !readFailed(back) && back.body.Indexed === false;
    log(cleared ? 'OK' : 'FAIL',
        cleared
          ? `${name}: Indexed is back to false.`
          : `${name}: Indexed is still ${readFailed(back) ? 'unreadable' : show(back.body.Indexed)} `
            + `after HTTP ${off.status} ${clip(off.text, 160)}. The fixture is NOT restored.`);
  }
})();
