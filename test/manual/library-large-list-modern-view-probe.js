/**
 * dbml-sharepoint PROBE: DOES THE MODERN LIBRARY PAGE RENDER A GROUPED VIEW
 * PAST 5,000 ITEMS, WHERE EVERY REST SURFACE REFUSES ONE?
 *
 * REVISION: d542c916
 *
 * ONE QUESTION, AND IT IS ABOUT A DIFFERENT LAYER FROM EVERY LARGE-LIST PROBE
 * BEFORE IT. #472, #478, #479, #480, #481 and #483 all measured the REST layer:
 * an OData `$filter`, and a `<GroupBy>` sent through `RenderListDataAsStream`.
 * This probe measures the layer a person sees, which is the modern document
 * library page rendering a view in a browser. Microsoft's own guidance for
 * large lists describes an effective threshold for the modern experience that
 * is higher than the 5,000 the query surfaces enforce, and a live observation
 * published by Joanne Klein in 2017 and updated since reported grouped views
 * still rendering in the modern UI at about 6,500 items. Nothing in this
 * repository has measured that, and nothing here assumes it.
 *
 * WHY IT MATTERS, and this is the decision it serves. The layout generator's
 * refusal to emit a group-by on a container past the threshold is justified by
 * REST-layer evidence alone. If the modern page renders a grouped view at this
 * size, then the correct rule is not "refuse group-by". It is "a group-by is a
 * UI-experience feature backed by predictive indexing, and every REST caller,
 * meaning API flows, Power BI and automation, must use a filtered view
 * instead". Those are different rules, they produce different emitted views,
 * and the difference is invisible to every gate this project runs. This probe
 * decides between them.
 *
 * WHAT IS ALREADY SETTLED AT THE REST LAYER, cited and never re-measured here.
 *   #472, `library-index-threshold-probe.js`, run 2026-09-08: past the
 *   threshold a selective OData filter on Id is SERVED, while Title, Name,
 *   Created, Modified, Author and Editor are each REFUSED with
 *   SPQueryThrottledException. An OData `$filter` reports the threshold as an
 *   error; the same predicate in CAML returns HTTP 200 and a silently partial
 *   answer.
 *   #478, `library-large-list-index-probe.js`, run 2026-09-08: `Indexed=true`
 *   is accepted on a library already past 5,000 files, and an index turns a
 *   refused filter or sort into a served one, for its own column only.
 *   #479 and #480, run 2026-09-08: a group-by on an unindexed Choice column,
 *   and a group-by on Id, the one natively indexed column, were both REFUSED
 *   with the threshold signature. The default view rendered its first page. A
 *   group-by over an Id-narrowed six-row set was HONOURED.
 *   #481, run 2026-09-08: the same single-level group-by, re-sent over
 *   176,814 ms with the filter on the same column interleaved, was REFUSED
 *   every time while the filter was SERVED every time.
 *   #483, `library-large-list-preindex-group-view-probe.js`, run 2026-09-08:
 *   the same question asked of 'dbmlsp Probe PreIndex', whose Choice column was
 *   indexed at 4,900 files and carried past the threshold. Still REFUSED, over
 *   32,582 ms of re-sends, while the filter on that same index served in the
 *   same request pairs. Writing the index before the crossing does not change
 *   the answer, so the ordering the index guidance names is not the variable.
 *
 * So the REST answer is settled across two fixtures and two index orderings:
 * a group-by past 5,000 is refused. Every row this probe records about the
 * rendered page is compared against that, and against nothing this probe
 * measures for itself.
 *
 * THE FIXTURE IS READ. The one thing it writes is two views.
 * `library-large-list-preindex-fixture-probe.js` builds and owns
 * 'dbmlsp Probe PreIndex': 5,100 files named dbmlsp-pre-00001.txt upward,
 * carrying PChoice (Choice, Alpha..Delta, from the file number modulo 4) and
 * PNumber (Number, the file number modulo 1000). PChoice was MERGEd
 * Indexed=true while the library still held 4,900 files, and the count and the
 * moment of that write are stamped into PChoice's Description. PNumber is
 * unindexed and stays that way. This probe uploads no file, writes no item
 * value, creates no column and sends no field MERGE. It creates two views,
 * because the views a person would open do not exist yet, and it removes them
 * again on request.
 *
 * THE A/B THE REST PROBES COULD NEVER TAKE. Both views live on the SAME library
 * at the SAME size. One groups on the indexed column and one on the unindexed
 * one, so a difference between them cannot be a difference between two
 * libraries built on different days, which is the confound #483 had to write
 * its own caveat about.
 *
 * WHAT THE VIEW WRITE COULD BREAK, AND THE CONTROL THAT WATCHES IT. Both
 * fixture probes resume and verify from the NEWEST FILE NAME, read with
 * `$orderby=Id desc&$top=1`, and both fail closed when that name does not match
 * their file-name pattern: `library-large-list-preindex-fixture-probe.js`
 * returns "the library holds something this probe did not put there" and its
 * header states that a failed resume read is fatal rather than falling back to
 * zero. So anything this probe adds to that library's item collection would
 * make a 5,100-file fixture, six pastes of work, unverifiable by its owner.
 * Whether an `AddView` puts anything in that collection is NOT assumed either
 * way. The newest file name is read before the views are created and again
 * afterwards, and `control-ui-fixture-readable-after-view-writes` compares
 * them. A run where they differ says so, and the cleanup path removes the two
 * views.
 *
 * WHY THE FOLDER-SCOPED STATE IS REGISTERED AND OPEN. Folder scoping is the
 * case Klein reported working, and answering it needs a folder holding fewer
 * than 5,000 files INSIDE a library holding more than 5,000. Neither permanent
 * fixture has one: 'dbmlsp Probe PreIndex' holds 5,100 contiguous files at its
 * root and 'dbmlsp Probe LargeLib' holds 5,500, both by contract. Creating one
 * would mean adding a folder to a fixture whose owner fails closed on an
 * unrecognised newest item, for the reason above, and no probe should risk that
 * to save a fixture build. `ui-group-by-indexed-column-folder-scoped` is
 * therefore registered, recorded open with that reason, and left for a fixture
 * probe that builds a large library WITH folders. Naming it and leaving it open
 * is the honest form; quietly dropping it would leave the enumeration looking
 * complete.
 *
 * THE CAPTURE CONTROL IS THE MOST IMPORTANT ROW IN THIS PROBE.
 * `view-aggregations-probe.js` provisions its fixture with
 * `ListExperienceOptions: 2`, classic, and says why in a comment: the modern
 * list web part does not render under the capture browser. If that still holds,
 * then a blank grid on the fixture library is the capture lane failing and
 * looks exactly like the modern UI refusing to render past 5,000. Those two are
 * the same picture and the opposite finding. So STATE 1 reads the same
 * instrument on a library UNDER the threshold, and every rendered row declares
 * a dependency on it. A run where STATE 1 finds nothing rendered voids the
 * rendered rows rather than reporting a threshold result.
 *
 * HOW A RENDER IS READ, and what is reported rather than asserted. Every DOM
 * instrument below returns WHAT IT FOUND, in both directions, and no verdict
 * rests on a single class name, automation id or English sentence.
 *
 *   EXPERIENCE. The classic candidates are ASP.NET WebForms facts rather than
 *   SharePoint ones: a `form#aspnetForm`, ids prefixed `ctl00_`, and the
 *   classic workspace container. MODERN is recorded only when every classic
 *   candidate is ABSENT and at least one modern candidate is present. Both
 *   families present, or both absent, is MANUAL. A probe that asserted one
 *   automation id would answer NOT ESTABLISHED the moment Microsoft renamed it,
 *   and that is indistinguishable from the page not rendering.
 *
 *   IDENTITY. Read from the page's own JavaScript context and compared against
 *   the library's Id read over REST in the same paste. The URL is RECORDED and
 *   is never part of a verdict: a modern list page rewrites its own URL, and a
 *   view parameter in a URL says what was asked for rather than what rendered.
 *
 *   GROUPS. For the Choice column the four labels are known exactly. A group
 *   HEADER renders as one element reading "<column>: <label> (<count>)", so
 *   the instrument looks for a leaf element whose text carries the label
 *   followed by a parenthesised count, and quotes what it found. A leaf whose
 *   text IS the bare label is a column CELL in a file row rather than a header,
 *   so those hits are reported separately and are not the verdict. For the
 *   Number column the labels are integers, which no text scan can tell from any
 *   other integer on the page, so that state's label test is not run and is
 *   said not to be run. Both states also report how many elements carry
 *   `aria-expanded`, which is an ARIA convention for a collapsible region
 *   rather than a SharePoint marker.
 *
 *   ROWS. Counted from the fixture's own file-name stem, `dbmlsp-pre-NNNNN.txt`,
 *   which is a fact about the fixture and cannot be renamed by a UI update. A
 *   `role="row"` count is reported beside it and is never the verdict on its
 *   own, because a header is a row too.
 *
 *   THE BANNER. A candidate list of phrases, all matches reported, plus the
 *   text of anything carrying `role="alert"`. The phrases are English, so the
 *   UI culture is read and printed with them: on a non-English tenant an absent
 *   phrase means nothing at all, which is the distinction
 *   `view-edit-page-probe.js` had to draw for its own English markers.
 *   `ui-threshold-banner-text` exists to capture the exact wording, because a
 *   deploy that could recognise the rendered refusal is a different capability
 *   from one that can recognise the REST refusal, and nothing here knows the
 *   wording yet.
 *
 * WHY THE UNINDEXED WITNESS IS A WITNESS AND NOT A CONTROL. PNumber holds a
 * thousand distinct values over 5,100 files, so a group-by on it asks for about
 * a thousand groups. A refusal there is therefore not attributable to the index
 * alone: the group count is itself a load. It is reported as a witness beside
 * the indexed column, and nothing declares a dependency on it. The same
 * argument #479, #480, #481 and #483 each made for their own refused group-bys
 * applies unchanged: a group-by refused at this size is the result three probes
 * have recorded, so spelling it as a control would make a finding
 * indistinguishable from a broken instrument.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED.
 *   Depends on (asserted, read back): the fixture library is present, holds
 *   more than 5,000 files counted from the newest file name, and carries
 *   PChoice and PNumber as their declared types; PChoice reads Indexed=true and
 *   its Description carries a stamp naming a count below 5,000; PNumber reads
 *   Indexed=false; both created views read back carrying a `<GroupBy>` on the
 *   column they name; neither created view is the default view and the default
 *   view is the one it was before; the newest file name is unchanged by the
 *   view writes; the capture browser renders a modern library page under the
 *   threshold; and the rendered page identifies itself as the fixture library.
 *   Observes (recorded, never asserted): whether the default view renders past
 *   the threshold; whether either grouped view renders, and with what group
 *   labels and counts; what a threshold banner says if one appears; how many
 *   file rows a first page shows; whether a column-header filter serves; and
 *   which experience the page reports itself as. NOTHING here asserts that the
 *   modern UI renders any of it. A run where every state shows the banner is a
 *   successful run and it confirms the REST result at the layer a person sees.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. All of it files under `library.large-list`,
 * the scope for reading a document library past the list view threshold. The
 * questions are about that same container, asked on the rendered page rather
 * than over REST, so they take the `ui-` question stem rather than a new scope.
 * Three ids are already registered by the fixture probe and are kept, because
 * the question and the method are the same and one question takes one id
 * however many probes ask it.
 *
 *   library.large-list.fixture-preindex-library-present
 *        Is the pre-indexed fixture there, past 5,000 files, with both contract
 *        columns reading back as their types?
 *   library.large-list.fixture-preindex-index-written-under-threshold
 *        Does PChoice read Indexed=true, AND does its Description carry the
 *        stamp saying the flag was written below 5,000 files?
 *   library.large-list.fixture-preindex-witness-unindexed
 *        Does PNumber read Indexed=false, so the unindexed side of the A/B is
 *        really unindexed?
 *   library.large-list.fixture-ui-grouped-views-created
 *        Do both views exist and read back carrying a single-level `<GroupBy>`
 *        on the column they name, collapsed, with the row limit asked for?
 *   library.large-list.control-ui-fixture-readable-after-view-writes
 *        CONTROL: is the newest file name the same after the view writes as
 *        before them, so the fixture's owner can still resume and verify it?
 *   library.large-list.control-ui-default-view-unchanged
 *        CONTROL: is the library's default view the one it was before this
 *        probe wrote anything?
 *   library.large-list.control-ui-modern-renders-below-threshold
 *        CONTROL: does this browser render a modern document library page at
 *        all, on a library UNDER the threshold? Without it a blank grid past
 *        5,000 cannot be told from a capture lane that renders nothing.
 *   library.large-list.control-ui-page-identity-matches-fixture
 *        CONTROL: does the rendered page say, in its own JavaScript context,
 *        that it belongs to the fixture library?
 *   library.large-list.control-ui-experience-is-modern
 *        CONTROL: is the fixture library's page the modern experience rather
 *        than the classic one? A classic render answers a different question.
 *   library.large-list.ui-default-view-renders-past-threshold
 *        Does the default view render file rows on the page at 5,100 files?
 *   library.large-list.ui-group-by-indexed-column-renders
 *        THE CRUX: does a grouped view on the INDEXED PChoice render group
 *        headers at 5,100 files, and are group counts visible beside them?
 *   library.large-list.ui-group-by-unindexed-column-renders
 *        WITNESS: does the grouped view on the unindexed PNumber render?
 *   library.large-list.ui-group-by-indexed-column-folder-scoped
 *        Does folder scoping change any of it? Registered and OPEN: neither
 *        fixture holds a folder and neither can be given one safely.
 *   library.large-list.ui-column-header-filter-past-threshold
 *        Does the column-header filter on PChoice offer values past 5,000?
 *   library.large-list.ui-threshold-banner-text
 *        What does the rendered refusal actually say, where one appears?
 *
 * HOW TO RUN. Six pastes, one per state, and the probe prints the URL for each.
 *   1. Open the site holding 'dbmlsp Probe PreIndex'. If it is not built, run
 *      library-large-list-preindex-fixture-probe.js until its rows read PASS.
 *      This probe will not build it and will not repair it.
 *   2. STATE = 0, CONFIRMED = true, ALLOW_WRITES = true. Paste on any page of
 *      that site. It checks the fixture, creates the two views, verifies the
 *      fixture is still readable, and prints the URL for every state below.
 *   3. STATE = 1, CONFIRMED = true. Open a document library on this site
 *      holding AT LEAST ONE file and fewer than 5,000, let it finish rendering,
 *      then paste. An empty library renders no file row however well the
 *      browser works, so it cannot answer this control. This is the capture
 *      control and it comes first on purpose.
 *   4. STATE = 2, 3 and 4 in turn. Open the URL the setup printed, let the page
 *      finish rendering, then paste. ALLOW_WRITES is not needed from here on
 *      and nothing after STATE 0 writes.
 *   5. STATE = 5, optional. On the 'UI By PChoice' page, open the PChoice
 *      column header menu and its filter pane by hand, then paste. If the pane
 *      will not open, report the row MANUAL rather than guessing.
 *   6. Screenshot every state, and copy each RESULTS block back verbatim. One
 *      paste answers one state; the rows it did not reach print NOT REACHED and
 *      that is what they are. A NOT REACHED row is a row this paste did not
 *      ask, so anything merging the six transcripts into one summary must KEEP
 *      THE FIRST SETTLED VALUE for a row and never let a later leg's NOT
 *      REACHED overwrite it.
 *
 * WHEN FINISHED: re-paste with STATE = 0, CLEANUP = true, CONFIRMED = true and
 * ALLOW_WRITES = true to remove the two views. Leave the library itself, its
 * files and PChoice's index exactly as they are. An operator who clears that
 * index has destroyed the only thing that distinguishes this library from the
 * one #480 and #481 measured.
 *
 * SCOPE OF CLAIMS: one tenant, one library, one caller identity, one browser.
 * The modern experience is a client render, so a result here is about this
 * browser as much as about SharePoint, which is exactly why STATE 1 exists.
 *
 * STATUS: RUN TWICE. 2026-09-08 reached STATE 0 only. 2026-09-09 drove STATES
 * 1 to 4 and settled, on the rendered page: the fixture library's page is
 * MODERN and identifies itself as the fixture; the default view RENDERS its
 * first page at 5,100 files; the grouped view on the unindexed PNumber is
 * REFUSED with a threshold banner, whose English wording is now captured. The
 * crux row read MANUAL, while the screenshot beside it shows the header
 * "PChoice: Alpha (100+)" over file rows with no banner and the raw reading
 * records 29 fixture file names and no banner phrase. That gap is a defect in
 * the instrument, fixed below. STATE 5, the column-header filter pane, has not
 * been opened.
 */
// finding: modern-view-rest-refusal-is-settled-across-both-index-orderings -
// #481 measured a group-by refused past 5,000 on a Choice column indexed AFTER
// the library crossed, over 176,814 ms; #483 measured the same refusal on a
// Choice column indexed at 4,900 files and carried past, over 32,582 ms, with
// the filter on that same index serving in the same request pairs. Two
// fixtures, two orderings, one answer. This probe re-measures none of it and
// compares every rendered row against it.
// finding: modern-view-the-blank-grid-ambiguity - a modern list page that
// renders nothing and a modern list page refusing to render past 5,000 produce
// the same screenshot. view-aggregations-probe.js provisions its fixture
// classic and records that the modern list web part does not render under the
// capture browser, so this is a live constraint rather than a hypothetical.
// control-ui-modern-renders-below-threshold reads the same instrument on a
// library under the threshold and every rendered row depends on it. Run 2,
// 2026-09-09: that control was pasted on the site's EMPTY Documents library,
// which holds 0 items, and read DOES NOT RENDER off 1 element with role="row".
// An empty library has no file row to render, so the control needs a POPULATED
// under-threshold library and now refuses one holding no file at all.
// finding: modern-view-a-fixture-write-can-break-its-owners-resume-read - both
// large-library fixture probes resume from the newest file name read with
// `$orderby=Id desc&$top=1` and fail closed on a name their pattern does not
// match, which is why neither may be given a folder or a file by another probe.
// Whether creating a VIEW touches that item collection is not assumed here: the
// name is read before and after the two AddView calls and compared.
// finding: modern-view-folder-scoping-needs-a-fixture-nobody-has-built - the
// folder-scoped state needs a folder under 5,000 files inside a library over
// 5,000, and neither permanent fixture holds one. The row is registered and
// recorded open with that reason rather than dropped, because a missing row
// reads as a completed enumeration.
// finding: modern-view-markers-are-reported-not-asserted - five of thirty-five
// Fluent icon names this project asserted from memory did not exist. Every DOM
// instrument here reports what it found in both directions, the experience
// verdict requires the ASP.NET WebForms markers to be ABSENT rather than a
// modern automation id to be present, and the row count is taken from the
// fixture's own file-name stem, which no UI update can rename. Run 2,
// 2026-09-09, taught the same lesson about the group instrument: a leaf whose
// text IS the label matched a PChoice CELL in a file row, and the digits beside
// it were read out of the file name as the group count "Alpha=00004". The
// header on the page reads "PChoice: Alpha (100+)", one element, so the label
// is now looked for with a parenthesised count after it and the bare-label hits
// are reported apart from the verdict.
// finding: modern-view-a-modern-grouped-page-materialises-one-group - run 2,
// 2026-09-09, STATE 3: the page showed the first group expanded with 29 file
// rows under it and the other three group headers were not in the DOM at all.
// Requiring two of the four labels therefore fails on a page that is grouping
// correctly, so one header carrying a count is what the row is read from and
// how many of the four were found is reported beside it.
// finding: modern-view-the-url-is-recorded-and-never-a-verdict - a modern list
// page rewrites its own URL, and a view parameter says what was asked for
// rather than what rendered. Page identity is taken from the page's JavaScript
// context and compared against the library Id read over REST in the same paste.
// finding: modern-view-the-unindexed-witness-carries-a-thousand-groups -
// PNumber is the file number modulo 1000, so a group-by on it asks for about a
// thousand groups over 5,100 files. A refusal there is not attributable to the
// missing index alone, which is why it is a witness beside the indexed column
// and nothing depends on it.
// finding: modern-view-banner-phrases-are-english-and-say-so - the threshold
// banner is display text. view-edit-page-probe.js run 1, 2026-08-17, measured
// _spPageContextInfo.currentUICultureName reading "en-US" while the page's
// <html lang> read "en-AU", so the two disagree and only the first governs
// which language a message arrives in. The culture is printed beside every
// phrase scan, and on a non-English tenant an absent phrase means nothing.
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

  // Printed before any gate: a stale clipboard and a fix that did not work
  // produce identical transcripts otherwise.
  log('INFO', 'probe revision d542c916. Quote this when reporting results.');

  // ---- Operator settings -------------------------------------------------
  // Which leg of the run this paste is. One paste answers one state, because a
  // pasted script cannot navigate the page it is running in and come back.
  //
  //   0  SETUP. REST only. Checks the fixture, creates the two views, verifies
  //      the fixture is still readable, prints the URL for every state below.
  //      Needs CONFIRMED and ALLOW_WRITES. This is the only state that writes.
  //   1  CONTROL. Paste on a rendered library page holding AT LEAST ONE file
  //      and fewer than 5,000. Establishes that this browser renders a modern
  //      library at all. An empty library cannot: it has no row to render.
  //   2  The default view at the root of the fixture library.
  //   3  'UI By PChoice', the grouped view on the INDEXED column.
  //   4  'UI By PNumber', the grouped view on the unindexed column.
  //   5  'UI By PChoice' with the PChoice column-header filter pane open.
  const STATE = 0;
  // ------------------------------------------------------------------------

  // ---- The fixture contract, restated ------------------------------------
  // Owned by library-large-list-preindex-fixture-probe.js. Read, never built,
  // never repaired. Changing any of these reads a different library rather than
  // adjusting this one.
  const LIB = 'dbmlsp Probe PreIndex';
  const CHOICE = 'PChoice';
  const NUMBER = 'PNumber';
  const COLUMN_TYPES = [
    [CHOICE, 'Choice'],
    [NUMBER, 'Number'],
  ];
  const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
  const TARGET_FILES = 5100;
  const THRESHOLD = 5000;
  // The capture control needs a library that has something to render. An empty
  // one shows a header row and nothing else, which is the same picture as a
  // browser that renders no modern list at all. See the blank-grid finding.
  const CONTROL_FLOOR = 1;
  // More than the documented 5,000, so every page below is opened past it.
  const FLOOR = 5001;
  const FILE_NUMBER = /dbmlsp-pre-(\d+)\.txt$/;
  // The same stem as it appears anywhere in rendered page text. This is the row
  // counter: a fact about the fixture rather than about the renderer.
  const FILE_IN_TEXT = /dbmlsp-pre-\d{5}\.txt/g;
  // The stamp the fixture's indexing pass left on PChoice's Description.
  // Indexed=true on its own cannot say WHEN it was written.
  const STAMP_RE = /dbmlsp preindex: Indexed:true written at (\d+) file\(s\) on (\S+)/;

  // ---- What this probe creates -------------------------------------------
  // Two views a person would actually make, on the library that already exists.
  // The titles are exact and the cleanup path refuses anything else, so a
  // mistyped or stale CLEANUP cannot reach a view this probe did not create.
  const VIEW_CHOICE = 'UI By PChoice';
  const VIEW_NUMBER = 'UI By PNumber';
  const PROBE_VIEWS = [VIEW_CHOICE, VIEW_NUMBER];
  // The default shape of a grouped view: collapsed, one level, item limit 100.
  // Both numbers are read back and reported, because how many rows and how many
  // groups a first page is allowed to show is a value the reading depends on.
  const VIEW_ROW_LIMIT = 100;
  const GROUP_LIMIT = 100;

  // ---- Reading a rendered page -------------------------------------------
  // Candidates, in both directions, all reported. See the markers finding.
  //
  // The classic side is ASP.NET WebForms rather than SharePoint: a WebForms
  // page carries one server-side form and control ids built from the page's
  // control tree. A page carrying none of these is not being served by that
  // renderer, which is a stronger statement than any modern marker being
  // present.
  const CLASSIC_MARKERS = [
    'form#aspnetForm',
    '[id^="ctl00_"]',
    '#s4-workspace',
    '#onetidDoclibViewTbl0',
  ];
  // Present-side candidates. No verdict rests on any ONE of these; they say
  // that something client-rendered is on the page.
  const MODERN_MARKERS = [
    '[data-automationid]',
    '[data-viewport-id]',
    'div[role="grid"]',
    'div[role="presentation"] [role="row"]',
  ];
  // Display text, and English. Reported with the UI culture beside it.
  const BANNER_PHRASES = [
    'cannot be displayed',
    'exceeds the list view threshold',
    'list view threshold',
    'too many items',
    'This view cannot be displayed',
    'SPQueryThrottledException',
  ];
  // How much rendered text to quote per row. A library page carries a lot of
  // chrome and an uncapped quote buries the reading.
  const TEXT_CAP = 240;
  const ROW_CAP = 8;

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const guid = (value) => String(value === null || value === undefined ? '' : value)
    .replace(/[{}]/g, '').toLowerCase();

  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const fieldPath = (name) =>
    `${libPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  expect('library.large-list.fixture-preindex-library-present', `The fixture library '${LIB}' is present, holds more than 5,000 files and carries both contract columns`);
  expect('library.large-list.fixture-preindex-index-written-under-threshold', `${CHOICE} reads Indexed=true and its Description carries the stamp saying the flag was written below ${THRESHOLD} files`);
  expect('library.large-list.fixture-preindex-witness-unindexed', `${NUMBER} reads Indexed=false, so the unindexed side of the comparison really is unindexed`);
  expect('library.large-list.fixture-ui-grouped-views-created', 'Both grouped views exist and read back carrying a single-level <GroupBy> on the column they name');
  expect('library.large-list.control-ui-fixture-readable-after-view-writes', "CONTROL: is the newest file name the same after the view writes as before them, so the fixture's owner can still resume and verify it");
  expect('library.large-list.control-ui-default-view-unchanged', "CONTROL: is the library's default view the one it was before this probe wrote anything");
  expect('library.large-list.control-ui-modern-renders-below-threshold', 'CONTROL: does this browser render a modern document library page at all, on a library UNDER the threshold');
  expect('library.large-list.control-ui-page-identity-matches-fixture', 'CONTROL: does the rendered page say, in its own JavaScript context, that it belongs to the fixture library');
  expect('library.large-list.control-ui-experience-is-modern', "CONTROL: is the fixture library's page the modern experience rather than the classic one");
  expect('library.large-list.ui-default-view-renders-past-threshold', `Does the default view render file rows on the page at ${TARGET_FILES} files`);
  expect('library.large-list.ui-group-by-indexed-column-renders', `THE CRUX: does the grouped view on the indexed ${CHOICE} render group headers at ${TARGET_FILES} files, and are group counts visible`);
  expect('library.large-list.ui-group-by-unindexed-column-renders', `WITNESS: does the grouped view on the unindexed ${NUMBER} render at ${TARGET_FILES} files`);
  expect('library.large-list.ui-group-by-indexed-column-folder-scoped', 'Does scoping the grouped view inside a folder holding fewer than 5,000 files change the answer');
  expect('library.large-list.ui-column-header-filter-past-threshold', `Does the column-header filter on ${CHOICE} offer values past ${THRESHOLD} items`);
  expect('library.large-list.ui-threshold-banner-text', 'What does the rendered threshold refusal actually say, where one appears');

  // Every row still carrying the harness sentinel, stamped with one reason. A
  // paste that answers one state must not report the other states' questions as
  // merely unreached without saying which paste answers them.
  const stampRemaining = (outcome, why) => {
    for (const row of RESULTS) {
      if (row.evidence === 'the run did not reach this question') {
        record(row.id, row.question, outcome, why);
      }
    }
  };

  // ---- Fixture instruments (REST) ----------------------------------------
  // No $select on a field or list read, for the reason native-index-probe.js
  // records: one unrecognised name errors the whole request, and every property
  // would then read as unreadable rather than one being missing.
  const readField = async (name) => spGet(fieldPath(name));

  // The newest file NAME, never ItemCount, and ordered on Id, which #472
  // measured to be the one ordering a library past the threshold serves.
  const newestFile = async () => {
    const newest = await spGet(
      `${libPath}/items?$select=Id,FileLeafRef&$orderby=Id desc&$top=1`);
    if (readFailed(newest) || !Array.isArray(newest.body.value)) {
      return { ok: false, number: 0, name: null,
               why: `the newest item could not be read (HTTP ${newest.status})` };
    }
    const rows = newest.body.value;
    if (rows.length === 0) return { ok: true, number: 0, name: null, why: 'the library is empty' };
    const name = String(rows[0].FileLeafRef || '');
    const digits = name.match(FILE_NUMBER);
    if (!digits) {
      return { ok: false, number: 0, name,
               why: `the newest item is named ${show(name)}, which is not one of this fixture's `
                 + 'file names, so the library holds something the fixture probe did not put there' };
    }
    return { ok: true, number: Number(digits[1]), name, why: `${name} is the newest file` };
  };

  const choiceState = async () => {
    const read = await readField(CHOICE);
    if (readFailed(read)) {
      return { ok: false, status: read.status, indexed: null, description: null, stamp: null };
    }
    const description = typeof read.body.Description === 'string' ? read.body.Description : '';
    const found = STAMP_RE.exec(description);
    return {
      ok: true,
      status: read.status,
      indexed: typeof read.body.Indexed === 'boolean' ? read.body.Indexed : null,
      description,
      stamp: found === null ? null : { held: Number(found[1]), at: found[2], text: found[0] },
    };
  };

  // ---- DOM instruments ----------------------------------------------------
  // Reported, never asserted. Each returns what it FOUND, and every verdict is
  // formed from a combination so that one renamed marker costs a row rather
  // than the run.

  // innerText needs layout and textContent does not, so a page that laid out
  // and one that only parsed are distinguishable here rather than silently
  // equivalent. Which one was used is part of the evidence.
  const pageText = () => {
    const laid = document.body ? String(document.body.innerText || '') : '';
    if (laid.trim().length) return { text: laid, source: 'innerText' };
    const parsed = document.body ? String(document.body.textContent || '') : '';
    return { text: parsed, source: parsed.trim().length ? 'textContent (innerText was empty)' : 'nothing' };
  };

  const countOf = (selector) => {
    try {
      return document.querySelectorAll(selector).length;
    } catch {
      return -1;
    }
  };

  const experienceScan = () => {
    const classic = CLASSIC_MARKERS.map((s) => [s, countOf(s)]);
    const modern = MODERN_MARKERS.map((s) => [s, countOf(s)]);
    const classicSeen = classic.filter(([, n]) => n > 0).map(([s]) => s);
    const modernSeen = modern.filter(([, n]) => n > 0).map(([s]) => s);
    // MODERN needs every classic candidate absent. That is the direction that
    // survives a renamed automation id: a page served by the WebForms renderer
    // cannot hide these, while a modern page can rename anything it likes.
    const verdict = classicSeen.length === 0 && modernSeen.length > 0
      ? 'MODERN'
      : classicSeen.length > 0 && modernSeen.length === 0
        ? 'CLASSIC'
        : 'AMBIGUOUS';
    return { verdict, classic, modern, classicSeen, modernSeen,
      detail: `classic candidates ${JSON.stringify(classic)}; modern candidates ${JSON.stringify(modern)}` };
  };

  const bannerScan = () => {
    const seen = pageText();
    const matched = BANNER_PHRASES.filter((p) => seen.text.includes(p));
    const at = matched.length ? seen.text.indexOf(matched[0]) : -1;
    const around = at < 0 ? '' : clip(seen.text.slice(Math.max(0, at - 60)), TEXT_CAP);
    const alerts = [];
    for (const node of document.querySelectorAll('[role="alert"]')) {
      const text = String(node.textContent || '').trim();
      if (text) alerts.push(clip(text, 160));
      if (alerts.length >= ROW_CAP) break;
    }
    return { matched, around, alerts, textSource: seen.source, length: seen.text.length,
      culture: pageCtx.currentUICultureName || null };
  };

  // Count the fixture's own file names in the rendered text, which is what a
  // file row shows. `role="row"` is reported beside it and is never the verdict
  // on its own, because a column header is a row too.
  const rowScan = () => {
    const seen = pageText();
    const names = seen.text.match(FILE_IN_TEXT) || [];
    const distinct = names.filter((n, at) => names.indexOf(n) === at);
    return { fileNames: distinct.length, sample: distinct.slice(0, 4),
      roleRows: countOf('[role="row"]'), roleGrids: countOf('[role="grid"]'),
      textSource: seen.source, textLength: seen.text.length };
  };

  // A group HEADER is one leaf element reading "<column>: <label> (<count>)".
  // A leaf whose text IS the bare label is a column CELL in a file row, which
  // is what run 2 matched, so the two are read apart: the header shape is the
  // verdict and the bare-label hits are reported beside it. `labels` is null
  // where the column's values are bare integers and no text scan can tell one
  // from any other number on the page.
  const escapeRe = (text) => String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  // The count is captured as SHOWN, digits and any trailing "+", because
  // "(100+)" is a group limit reached rather than a group size.
  const headerRe = (label) =>
    new RegExp(`(?:^|[^A-Za-z0-9])${escapeRe(label)}\\s*\\((\\d[\\d,]*\\+?)\\)\\s*$`);
  const groupScan = (labels) => {
    const expanders = [];
    for (const node of document.querySelectorAll('[aria-expanded]')) {
      const text = String(node.textContent || '').trim();
      expanders.push(clip(text || '(no text)', 60));
      if (expanders.length >= ROW_CAP) break;
    }
    const expanderCount = countOf('[aria-expanded]');
    if (labels === null) {
      return { labels: null, headers: [], headerTexts: [], counted: [], cells: [],
        expanderCount, expanders,
        detail: 'the label test is NOT run for this column: its values are integers and a text '
          + 'scan cannot tell a group label from any other number on the page' };
    }
    const headers = [];
    const headerTexts = [];
    const counted = [];
    const cells = [];
    const leaves = [];
    for (const node of document.querySelectorAll('*')) {
      if (node.children.length) continue;
      leaves.push(clip(String(node.textContent || '').trim(), 120));
    }
    for (const label of labels) {
      const pattern = headerRe(label);
      const header = leaves.find((text) => pattern.test(text));
      if (header !== undefined) {
        headers.push(label);
        headerTexts.push(header);
        counted.push(`${label}=${header.match(pattern)[1]}`);
      }
      if (leaves.includes(label)) cells.push(label);
    }
    return { labels, headers, headerTexts, counted, cells, expanderCount, expanders,
      detail: `group header(s) found for ${JSON.stringify(headers)} of `
        + `${JSON.stringify(labels)}, reading ${JSON.stringify(headerTexts)}, so the count as `
        + `SHOWN is ${JSON.stringify(counted)}. A modern grouped page materialises the groups `
        + 'near the viewport and expands the first, so a label absent here is not a group absent '
        + `from the view. Reported and NOT the verdict: ${JSON.stringify(cells)} appear as a bare `
        + 'label on some leaf element, which is what a column cell in a file row looks like' };
  };

  // Which list the PAGE says it is showing, taken from its own JavaScript
  // context. The URL is recorded and is never part of the verdict.
  const pageIdentity = () => {
    const candidates = [
      ['_spPageContextInfo.listId', pageCtx.listId],
      ['_spPageContextInfo.pageListId', pageCtx.pageListId],
      ['_spPageContextInfo.listUrl', pageCtx.listUrl],
      ['_spPageContextInfo.listTitle', pageCtx.listTitle],
    ];
    const ids = [pageCtx.listId, pageCtx.pageListId].map(guid).filter((g) => g.length > 0);
    return { candidates, ids,
      url: String(window.location.href),
      title: String(document.title || ''),
      detail: `page context ${JSON.stringify(candidates)}; document.title ${show(String(document.title || ''))}; `
        + `OBSERVED ONLY, never part of the verdict: location ${show(String(window.location.href))}` };
  };

  // Whichever of the created view titles the page is showing, if the page says
  // so at all. Reported: the identity that is ASSERTED is the LIST, because a
  // view title is display text and a person can rename one.
  const viewHint = (title) => {
    const seen = pageText();
    return { inText: seen.text.includes(title), inTitle: String(document.title || '').includes(title) };
  };

  // ---------------------------------------------------------------------------
  // STATE 0: the setup leg. REST only, and the only leg that writes.
  // ---------------------------------------------------------------------------
  if (STATE === 0) {
    if (!CONFIRMED) {
      log('INFO', `Would READ the existing library '${LIB}' on ${WEB}: its file count, its two`);
      log('INFO', `columns ${CHOICE} and ${NUMBER}, their Indexed flags and the index stamp on`);
      log('INFO', `${CHOICE}'s Description. It builds NO library, uploads NO file and writes NO`);
      log('INFO', 'item value, column or field MERGE.');
      log('INFO', `It would then CREATE two views on that library, '${VIEW_CHOICE}' and`);
      log('INFO', `'${VIEW_NUMBER}', each a single-level collapsed <GroupBy> with a row limit of`);
      log('INFO', `${VIEW_ROW_LIMIT}, read both back, and check that the library's newest file name and`);
      log('INFO', 'its default view are unchanged by those two writes.');
      log('INFO', `In particular it does NOT clear the index on ${CHOICE}: that flag was written`);
      log('INFO', `below ${THRESHOLD} files and cannot be put back without rebuilding the library.`);
      log('INFO', 'Set CONFIRMED and ALLOW_WRITES to true to run it.');
      log('INFO', 'Then paste again with STATE = 1..5, one paste per rendered page.');
      report();
      return;
    }

    // ---- Cleanup: the two views this probe created, and nothing else ------
    if (CLEANUP) {
      if (!ALLOW_WRITES) {
        log('INFO', 'CLEANUP is on but ALLOW_WRITES is false, so no view is removed.');
        report();
        return;
      }
      const held = await spGet(`${libPath}/views?$top=200`);
      const known = (!readFailed(held) && Array.isArray(held.body.value)) ? held.body.value : [];
      for (const title of PROBE_VIEWS) {
        // Exact title membership, not a prefix. A prefix test would let a
        // mistyped or stale cleanup reach a view somebody else made, and a
        // default view is refused outright whatever it is called.
        const view = known.find((v) => v.Title === title);
        if (!view) {
          log('INFO', `CLEANUP: no view titled '${title}' on '${LIB}'. Nothing to do.`);
          continue;
        }
        if (view.DefaultView === true) {
          log('FAIL', `CLEANUP: '${title}' is the library's DEFAULT view, so it is NOT removed. `
            + 'Set another view as default by hand first, then re-run cleanup.');
          continue;
        }
        const digest = await getDigest();
        const gone = await spPost(`${libPath}/views/getbytitle('${odataName(title)}')`, {}, digest,
                                  { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
        log(gone.ok ? 'OK' : 'FAIL', gone.ok
          ? `CLEANUP: removed the view '${title}'.`
          : `CLEANUP: could not remove '${title}': HTTP ${gone.status} ${clip(gone.text, 200)}`);
      }
      const after = await newestFile();
      log('INFO', `After cleanup the newest file reads ${show(after.name)} (${after.why}). The `
        + 'library, its files and the index on ' + CHOICE + ' are untouched.');
      report();
      return;
    }

    // ---- The fixture, read -----------------------------------------------
    const libRead = await spGet(libPath);
    const libOk = !readFailed(libRead);
    const libId = libOk ? guid(libRead.body.Id) : null;
    const before = await newestFile();
    const count = before.ok ? before.number : 0;
    const present = libOk && before.ok && count >= FLOOR;

    const columnProblems = [];
    const flags = [];
    for (const [name, wanted] of COLUMN_TYPES) {
      const read = await readField(name);
      if (readFailed(read)) {
        columnProblems.push(`${name} did not read back (HTTP ${read.status})`);
        continue;
      }
      const kind = read.body.TypeAsString;
      if (kind !== wanted) columnProblems.push(`${name} reads ${show(kind)} where the contract gives ${show(wanted)}`);
      flags.push(`${name} Indexed=${show(read.body.Indexed)}`);
    }

    record('library.large-list.fixture-preindex-library-present',
           `The fixture library '${LIB}' is present, holds more than 5,000 files and carries both contract columns`,
           !libOk || !before.ok ? 'ABORTED' : count < FLOOR ? 'SHORT' : columnProblems.length ? 'FAIL' : 'PASS',
           (libOk
             ? `the newest file is ${show(before.name)}, so the library holds ${count} file(s) against `
               + `the ${FLOOR} this probe needs and the ${TARGET_FILES} the fixture contract gives; `
               + `ItemCount reads ${show(libRead.body.ItemCount)} and is not what the count is taken from; `
               + `list Id ${show(libId)}`
             : `the library did not read back (HTTP ${libRead.status}): ${clip(show(libRead.body), 200)}`)
           + '. ' + (before.ok ? '' : `${before.why}. `)
           + (columnProblems.length
             ? `column problems: ${columnProblems.join('; ')}`
             : libOk ? `both contract columns read back as their declared types, and their index flags are ${flags.join(', ')}` : '')
           + (present
             ? '. This probe does not build the fixture, does not repair it and writes nothing to it '
               + 'except two views. It is owned by library-large-list-preindex-fixture-probe.js.'
             : '. Run library-large-list-preindex-fixture-probe.js until its fixture rows read PASS, '
               + 'then re-paste this one.'));

    if (!present) {
      stampRemaining('ABORTED', 'the fixture library was not present and past the threshold, so nothing was created and no page was read');
      report();
      return;
    }

    const choice = await choiceState();
    const stamped = choice.ok && choice.stamp !== null && choice.stamp.held < THRESHOLD;
    record('library.large-list.fixture-preindex-index-written-under-threshold',
           `${CHOICE} reads Indexed=true and its Description carries the stamp saying the flag was written below ${THRESHOLD} files`,
           !choice.ok ? 'NOT ESTABLISHED'
             : choice.indexed !== true ? 'NOT INDEXED'
               : stamped ? 'INDEXED UNDER THRESHOLD' : 'INDEXED, MOMENT NOT RECORDED',
           !choice.ok
             ? `${CHOICE} did not read back (HTTP ${choice.status}).`
             : `Indexed=${show(choice.indexed)}; Description ${show(clip(choice.description, 200))}; `
               + `stamp ${show(choice.stamp && choice.stamp.text)}. `
               + (stamped
                 ? `The flag was written at ${choice.stamp.held} file(s), below ${THRESHOLD}, which is the `
                   + 'ordering that separates this library from the one #480 and #481 measured.'
                 : 'Indexed=true on its own is equally consistent with a flag written at 4,900 files and '
                   + 'one written at 5,099, so the crux below is about an index of unknown provenance.'));

    const witness = await readField(NUMBER);
    const witnessOk = !readFailed(witness);
    record('library.large-list.fixture-preindex-witness-unindexed',
           `${NUMBER} reads Indexed=false, so the unindexed side of the comparison really is unindexed`,
           !witnessOk ? 'NOT ESTABLISHED' : witness.body.Indexed === false ? 'UNINDEXED' : 'INDEXED',
           !witnessOk
             ? `${NUMBER} did not read back (HTTP ${witness.status}).`
             : `Indexed=${show(witness.body.Indexed)}, AutoIndexed=${show(witness.body.AutoIndexed)}. `
               + (witness.body.Indexed === false
                 ? 'So the two grouped views differ in exactly the way this probe claims they do.'
                 : 'The witness column carries an index, so the two views no longer differ in the way '
                   + 'this probe is built on and neither rendered result can be attributed to the index.'));

    // ---- The two views ---------------------------------------------------
    const viewsBefore = await spGet(`${libPath}/views?$top=200`);
    const knownBefore = (!readFailed(viewsBefore) && Array.isArray(viewsBefore.body.value))
      ? viewsBefore.body.value : [];
    const defaultBefore = knownBefore.find((v) => v.DefaultView === true) || null;

    if (!ALLOW_WRITES) {
      record('library.large-list.fixture-ui-grouped-views-created',
             'Both grouped views exist and read back carrying a single-level <GroupBy> on the column they name',
             'ABORTED',
             'ALLOW_WRITES is false, so no view was created. The fixture rows above were still read. '
               + 'Set ALLOW_WRITES to true and paste again.');
      stampRemaining('NOT REACHED', 'the two views were not created, so no page was opened');
      report();
      return;
    }

    const viewErrors = [];
    for (const [title, column] of [[VIEW_CHOICE, CHOICE], [VIEW_NUMBER, NUMBER]]) {
      if (knownBefore.some((v) => v.Title === title)) {
        log('INFO', `'${title}' already exists on '${LIB}'. It is read back rather than re-created.`);
        continue;
      }
      // The `<Query>` children go Where then GroupBy, the order the syntax block
      // in "Query element (List)" gives them. There is no Where here: this is
      // the view a person makes, and narrowing it would answer the question
      // #480 already answered over an Id-narrowed row set.
      const query = `<GroupBy Collapse="TRUE" GroupLimit="${GROUP_LIMIT}">`
        + `<FieldRef Name="${column}"/></GroupBy>`;
      const digest = await getDigest();
      // The three properties `library-grouping-probe.js` and
      // `formatter-xml-probe.js` have both sent and had accepted, and nothing
      // more. DefaultView and PersonalView are left to their defaults and read
      // back below rather than asserted into the payload.
      const made = await spPost(`${libPath}/views`, {
        Title: title, RowLimit: VIEW_ROW_LIMIT, ViewQuery: query,
      }, digest);
      if (!made.ok) {
        viewErrors.push(`${title}: HTTP ${made.status} ${clip(made.text, 160)}`);
        continue;
      }
      // The grouped column has to be projected for a person to see the value
      // the header names. A failure here is recorded and does not stop the run,
      // because the grouping is what the page is being opened for.
      const withField = await getDigest();
      const added = await spPost(
        `${libPath}/views/getbytitle('${odataName(title)}')/viewfields/addviewfield('${odataName(column)}')`,
        {}, withField);
      if (!added.ok) {
        log('INFO', `'${title}': ${column} could not be added to ViewFields: HTTP ${added.status} `
          + clip(added.text, 160));
      }
    }

    // Read back rather than trusting the POST. A view found by title is not
    // proof it holds the query that was sent, which is the lesson
    // view-edit-page-probe.js records as Q1.
    const viewsAfter = await spGet(`${libPath}/views?$top=200`);
    const knownAfter = (!readFailed(viewsAfter) && Array.isArray(viewsAfter.body.value))
      ? viewsAfter.body.value : [];
    const shapes = [];
    const shapeProblems = [];
    const urls = {};
    for (const [title, column] of [[VIEW_CHOICE, CHOICE], [VIEW_NUMBER, NUMBER]]) {
      const view = knownAfter.find((v) => v.Title === title) || null;
      if (view === null) {
        shapeProblems.push(`${title} is not on the library after the write`);
        continue;
      }
      urls[title] = view.ServerRelativeUrl || null;
      const stored = String(view.ViewQuery || '');
      const grouped = stored.includes('<GroupBy') && stored.includes(`Name="${column}"`);
      const levels = (stored.match(/<FieldRef/g) || []).length;
      shapes.push(`${title}: ViewQuery ${show(clip(stored, 160))}, RowLimit ${show(view.RowLimit)}, `
        + `DefaultView ${show(view.DefaultView)}, ServerRelativeUrl ${show(view.ServerRelativeUrl)}`);
      if (!grouped) shapeProblems.push(`${title} does not carry a <GroupBy> naming ${column}`);
      if (levels !== 1) shapeProblems.push(`${title} carries ${levels} <FieldRef> in its query where one level was sent`);
      if (view.DefaultView === true) shapeProblems.push(`${title} came back as the DEFAULT view, which it must not be`);
    }
    record('library.large-list.fixture-ui-grouped-views-created',
           'Both grouped views exist and read back carrying a single-level <GroupBy> on the column they name',
           viewErrors.length ? 'FAIL' : shapeProblems.length ? 'FAIL' : 'PASS',
           `creation errors ${JSON.stringify(viewErrors)}; read back: ${shapes.join(' | ')}. `
           + (shapeProblems.length
             ? `problems: ${shapeProblems.join('; ')}. A view that did not really take voids its browser `
               + 'row, so do not open the page until this reads PASS.'
             : `Both views carry one <GroupBy>, collapsed, group limit ${GROUP_LIMIT}, row limit `
               + `${VIEW_ROW_LIMIT}, and neither is the default view. The stored query is what the page `
               + 'below renders, so the browser rows are about the shape named here.'));

    const after = await newestFile();
    const unchanged = before.ok && after.ok && after.name === before.name && after.number === before.number;
    record('library.large-list.control-ui-fixture-readable-after-view-writes',
           "CONTROL: is the newest file name the same after the view writes as before them, so the fixture's owner can still resume and verify it",
           !after.ok ? 'FAIL' : unchanged ? 'UNCHANGED' : 'CHANGED',
           `before: ${show(before.name)} (${before.number}). after: ${show(after.name)} (${after.number}). `
           + `${after.why}. `
           + (unchanged
             ? 'So creating a view added nothing this library\'s resume read can see, and '
               + 'library-large-list-preindex-fixture-probe.js can still verify its own fixture.'
             : "The newest item read by the fixture's own resume query CHANGED. That probe fails closed "
               + 'on a name its pattern does not match, so a 5,100-file fixture is now unverifiable by '
               + `its owner. Re-paste with STATE = 0 and CLEANUP = true to remove the two views, then `
               + 'report this row before anything else.'));

    const viewsForDefault = knownAfter.length ? knownAfter : knownBefore;
    const defaultAfter = viewsForDefault.find((v) => v.DefaultView === true) || null;
    const sameDefault = defaultBefore !== null && defaultAfter !== null
      && String(defaultBefore.Id) === String(defaultAfter.Id);
    record('library.large-list.control-ui-default-view-unchanged',
           "CONTROL: is the library's default view the one it was before this probe wrote anything",
           (defaultBefore === null || defaultAfter === null) ? 'NOT ESTABLISHED'
             : sameDefault ? 'UNCHANGED' : 'CHANGED',
           `before: ${show(defaultBefore && defaultBefore.Title)} (${show(defaultBefore && defaultBefore.Id)}). `
           + `after: ${show(defaultAfter && defaultAfter.Title)} (${show(defaultAfter && defaultAfter.Id)}). `
           + (sameDefault
             ? 'So a person opening this library still lands where they did before, and STATE 2 opens the '
               + 'view it means to.'
             : 'The default view MOVED, so every person using this library now lands somewhere else. '
               + 'Remove the two views with CLEANUP and set the original default back by hand.'));

    // Registered and open. See the folder-scoping finding: neither permanent
    // fixture holds a folder and neither can be given one without breaking the
    // resume read its owner depends on.
    record('library.large-list.ui-group-by-indexed-column-folder-scoped',
           'Does scoping the grouped view inside a folder holding fewer than 5,000 files change the answer',
           'NOT ESTABLISHED',
           'This run cannot ask it. The question needs a folder holding fewer than 5,000 files inside a '
           + `library holding more than 5,000, and neither permanent fixture has one: '${LIB}' holds `
           + `${TARGET_FILES} contiguous files at its root and 'dbmlsp Probe LargeLib' holds 5,500, both `
           + 'by contract. Both fixture probes resume and verify from the newest file name and fail closed '
           + 'on a name their pattern does not match, so adding a folder here would leave a fixture that '
           + 'takes six pastes to build unverifiable by its owner. Answering this needs a large library '
           + 'built WITH folders, which is a fixture probe rather than a change to this one.');

    stampRemaining('NOT REACHED', `STATE was ${STATE}, the setup leg. Each of these is read by opening a page and pasting again.`);

    log('INFO', '');
    log('INFO', 'THE RUN PLAN. One paste per page. Let each page finish rendering first.');
    log('INFO', `  STATE = 1  a document library on this site holding AT LEAST ${CONTROL_FLOOR} file and`);
    log('INFO', `             fewer than ${THRESHOLD}. An empty one cannot answer it. This is the`);
    log('INFO', '             capture control and it comes first on purpose.');
    log('INFO', `  STATE = 2  ${window.location.origin}${(defaultAfter && defaultAfter.ServerRelativeUrl) || '(the default view URL did not read back)'}`);
    log('INFO', `  STATE = 3  ${window.location.origin}${urls[VIEW_CHOICE] || '(not created)'}`);
    log('INFO', `  STATE = 4  ${window.location.origin}${urls[VIEW_NUMBER] || '(not created)'}`);
    log('INFO', `  STATE = 5  the STATE 3 page, with the ${CHOICE} column-header filter pane open.`);
    log('INFO', 'Screenshot every state. A state whose DOM read is ambiguous is MANUAL, not a pass.');
    log('INFO', `When finished, re-paste STATE = 0 with CLEANUP = true to remove '${VIEW_CHOICE}' and '${VIEW_NUMBER}'.`);
    report();
    return;
  }

  // ---------------------------------------------------------------------------
  // STATES 1 to 5: the rendered legs. Nothing below writes.
  // ---------------------------------------------------------------------------
  if (!CONFIRMED) {
    log('INFO', `Would READ the page you are on: its experience markers, its rendered text, its`);
    log('INFO', 'group headers and its row count. It writes nothing at all, on any surface.');
    log('INFO', `STATE is ${STATE}. Open the page that state names, let it finish rendering, set`);
    log('INFO', 'CONFIRMED to true and paste again.');
    report();
    return;
  }

  const identity = pageIdentity();
  const experience = experienceScan();
  const banner = bannerScan();
  const rows = rowScan();

  // ---- STATE 1: the capture control -------------------------------------
  // Read on a library UNDER the threshold, so a blank grid past 5,000 can be
  // told from a browser that renders no modern list at all.
  if (STATE === 1) {
    const listId = identity.ids[0] || null;
    const onFixture = listId !== null && await (async () => {
      const read = await spGet(libPath);
      return !readFailed(read) && guid(read.body.Id) === listId;
    })();
    const small = listId === null ? null : await spGet(`web/lists(guid'${listId}')`);
    const smallOk = small !== null && !readFailed(small);
    const items = smallOk ? Number(small.body.ItemCount) : NaN;
    const usable = smallOk && !onFixture && Number.isFinite(items)
      && items >= CONTROL_FLOOR && items < THRESHOLD;
    const rendered = experience.verdict === 'MODERN' && rows.roleRows > 1;
    record('library.large-list.control-ui-modern-renders-below-threshold',
           'CONTROL: does this browser render a modern document library page at all, on a library UNDER the threshold',
           !usable ? 'NOT ESTABLISHED' : rendered ? 'RENDERS' : 'DOES NOT RENDER',
           (!usable
             ? `this page is not a populated library under the threshold: list id ${show(listId)}, `
               + `ItemCount ${show(smallOk ? small.body.ItemCount : null)}, is the fixture library `
               + `${show(onFixture)}. Open a document library on this site holding at least `
               + `${CONTROL_FLOOR} file and fewer than ${THRESHOLD}, and paste again. An EMPTY `
               + 'library renders no file row however well this browser works, so it reads the '
               + 'same as a browser that renders nothing and cannot answer this control.'
             : `'${show(small.body.Title)}' holds ${items} item(s), under the ${THRESHOLD} threshold. `)
           + `experience ${experience.verdict}: ${experience.detail}. `
           + `rows: ${rows.roleRows} element(s) with role="row", ${rows.roleGrids} with role="grid", `
           + `page text ${rows.textLength} char(s) from ${rows.textSource}. `
           + (!usable ? ''
             : rendered
               ? 'So this browser does render a modern library page, and a page past the threshold that '
                 + 'shows nothing is a finding about the threshold rather than about the capture lane. '
                 + 'Every rendered row below depends on this one.'
               : 'This browser renders NOTHING usable on a library it is not being throttled on, so a '
                 + 'blank grid past 5,000 would say nothing at all. view-aggregations-probe.js records '
                 + 'the same constraint and provisions its fixture classic because of it. Every rendered '
                 + 'row below is VOID until this reads RENDERS.'));
    stampRemaining('NOT REACHED', 'STATE was 1, the capture control. Open the fixture pages and paste again with STATE 2, 3, 4 and 5.');
    report();
    return;
  }

  // ---- STATES 2 to 5 all read the fixture library's own page -------------
  const libRead = await spGet(libPath);
  const libId = !readFailed(libRead) ? guid(libRead.body.Id) : null;
  const matched = libId !== null && identity.ids.includes(libId);
  record('library.large-list.control-ui-page-identity-matches-fixture',
         'CONTROL: does the rendered page say, in its own JavaScript context, that it belongs to the fixture library',
         libId === null ? 'NOT ESTABLISHED' : matched ? 'MATCHES' : 'DOES NOT MATCH',
         `'${LIB}' reads list Id ${show(libId)} over REST. ${identity.detail}. `
         + (matched
           ? 'So the page under measurement is the fixture library, established from the page rather '
             + 'than from the address bar.'
           : 'The rendered page does not claim to be the fixture library, so whatever it shows is about '
             + 'some other container. Open the URL the setup leg printed and paste again.'));

  record('library.large-list.control-ui-experience-is-modern',
         "CONTROL: is the fixture library's page the modern experience rather than the classic one",
         experience.verdict === 'MODERN' ? 'MODERN'
           : experience.verdict === 'CLASSIC' ? 'CLASSIC' : 'NOT ESTABLISHED',
         `${experience.detail}. classic candidates present ${JSON.stringify(experience.classicSeen)}; `
         + `modern candidates present ${JSON.stringify(experience.modernSeen)}. `
         + (experience.verdict === 'MODERN'
           ? 'Every classic candidate is absent and something client-rendered is present, which is the '
             + 'direction that survives a renamed automation id.'
           : experience.verdict === 'CLASSIC'
             ? 'This is the classic renderer, whose threshold behaviour is what the REST probes already '
               + 'measured. A rendered result here does not answer the question this probe was written for.'
             : 'Both marker families are present, or neither is, so which renderer served this page is '
               + 'not established and the rows below are read against the screenshot rather than alone.'));

  if (banner.matched.length) {
    record('library.large-list.ui-threshold-banner-text',
           'What does the rendered threshold refusal actually say, where one appears',
           'FOUND',
           `phrases matched ${JSON.stringify(banner.matched)}; text around the first match `
           + `${show(banner.around)}; role="alert" text ${JSON.stringify(banner.alerts)}; `
           + `UI culture ${show(banner.culture)}. These are English phrases, so on a non-English tenant `
           + 'this row says nothing. Quote the wording into a finding line: recognising the RENDERED '
           + 'refusal is a different capability from recognising the REST one, and nothing in this '
           + 'repository knows the wording yet.');
  }

  const compare = 'Compare against the REST answer: #481 and #483 both measured this group-by REFUSED '
    + 'with SPQueryThrottledException past 5,000, on an index written after the crossing and on one '
    + 'written before it.';

  // A rendered state is only readable when the page is the fixture library and
  // something rendered. Otherwise the row is void rather than a threshold
  // result: a page that did not arrive and a page that refused look identical.
  const readable = matched && experience.verdict !== 'CLASSIC';
  const voidWhy = !matched
    ? 'the rendered page did not identify itself as the fixture library, so this row is about some '
      + 'other container'
    : 'the page rendered as CLASSIC, so this row would be about the renderer the REST probes already '
      + 'answer for';

  if (STATE === 2) {
    const served = rows.fileNames > 0;
    record('library.large-list.ui-default-view-renders-past-threshold',
           `Does the default view render file rows on the page at ${TARGET_FILES} files`,
           !readable ? 'NOT ESTABLISHED' : banner.matched.length ? 'REFUSED (banner)'
             : served ? 'RENDERS' : 'NOTHING RENDERED',
           !readable ? voidWhy
             : `${rows.fileNames} distinct fixture file name(s) in the rendered text, sample `
               + `${JSON.stringify(rows.sample)}; ${rows.roleRows} element(s) with role="row"; page text `
               + `${rows.textLength} char(s) from ${rows.textSource}; banner phrases `
               + `${JSON.stringify(banner.matched)}. `
               + (banner.matched.length
                 ? 'The default view shows the threshold refusal, which contradicts #480 measuring the '
                   + 'default view rendering its first page over REST on the other fixture.'
                 : served
                   ? 'The default view serves its first page to a person, which is what #480 measured '
                     + 'over REST on the other fixture. This is the baseline the grouped states are read '
                     + 'against: a grouped view failing where this one works is about the grouping.'
                   : 'Nothing rendered and no banner appeared, so this state is the ambiguous case the '
                     + 'capture control exists to separate. Read it beside STATE 1 and the screenshot.'),
           readable ? undefined : 'void');
    stampRemaining('NOT REACHED', 'STATE was 2, the default view. Open the grouped views and paste again with STATE 3, 4 and 5.');
    report();
    return;
  }

  if (STATE === 3) {
    const groups = groupScan(CHOICES);
    const hint = viewHint(VIEW_CHOICE);
    // ONE header carrying a count is the reading. A modern grouped page
    // materialises the groups near the viewport, so demanding two of the four
    // fails on a page that is grouping correctly: see the one-group finding.
    const rendered = groups.headers.length >= 1;
    const maybe = !rendered && groups.expanderCount >= 2;
    record('library.large-list.ui-group-by-indexed-column-renders',
           `THE CRUX: does the grouped view on the indexed ${CHOICE} render group headers at ${TARGET_FILES} files, and are group counts visible`,
           !readable ? 'NOT ESTABLISHED'
             : banner.matched.length ? 'REFUSED (banner)'
               : rendered ? (groups.counted.length ? 'GROUPS AND COUNTS RENDER' : 'GROUPS RENDER, NO COUNTS READ')
                 : maybe ? 'MANUAL' : 'NOTHING GROUPED RENDERED',
           !readable ? voidWhy
             : `${groups.detail}. ${groups.expanderCount} element(s) carry aria-expanded, showing `
               + `${JSON.stringify(groups.expanders)}. ${rows.fileNames} fixture file name(s) rendered `
               + `(a collapsed group shows none, so zero here is not a failure). banner phrases `
               + `${JSON.stringify(banner.matched)}; UI culture ${show(banner.culture)}. the view title `
               + `appears in page text ${show(hint.inText)} and in document.title ${show(hint.inTitle)}, `
               + 'which is reported and is not part of the verdict because a view title is display text. '
               + (banner.matched.length
                 ? `The modern page refuses this grouped view too. ${compare} So the refusal is not a `
                   + 'REST-surface artefact and the generator rule stays "refuse group-by past the '
                   + 'threshold".'
                 : rendered
                   ? `The modern page RENDERS a grouped view where every REST surface refuses one. ${compare} `
                     + 'If this holds on a second run, the generator rule is wrong as stated: a group-by '
                     + 'is a UI-experience feature and it is the REST callers, meaning API flows, Power BI '
                     + 'and automation, that need a filtered view instead. Report the screenshot with it.'
                   : maybe
                     ? 'Collapsible regions are on the page but no leaf element read as a group header, '
                       + 'meaning a label followed by a parenthesised count, so what rendered is not '
                       + 'established from the DOM. Read the screenshot and report which it is.'
                     : 'Neither group labels nor a banner. Read this beside STATE 1 and the screenshot '
                       + 'rather than as a threshold result.'),
           readable ? undefined : 'void');
    stampRemaining('NOT REACHED', 'STATE was 3, the indexed grouped view. Paste again with STATE 4 and STATE 5.');
    report();
    return;
  }

  if (STATE === 4) {
    // labels null: PNumber's values are integers and a text scan cannot tell a
    // group label from any other number on the page.
    const groups = groupScan(null);
    const hint = viewHint(VIEW_NUMBER);
    const grouped = groups.expanderCount >= 2 && rows.fileNames === 0;
    record('library.large-list.ui-group-by-unindexed-column-renders',
           `WITNESS: does the grouped view on the unindexed ${NUMBER} render at ${TARGET_FILES} files`,
           !readable ? 'NOT ESTABLISHED'
             : banner.matched.length ? 'REFUSED (banner)'
               : grouped ? 'GROUPS RENDER' : 'MANUAL',
           !readable ? voidWhy
             : `${groups.detail}. ${groups.expanderCount} element(s) carry aria-expanded, showing `
               + `${JSON.stringify(groups.expanders)}. ${rows.fileNames} fixture file name(s) rendered; `
               + `${rows.roleRows} element(s) with role="row"; banner phrases `
               + `${JSON.stringify(banner.matched)}. the view title appears in page text `
               + `${show(hint.inText)}. `
               + `${NUMBER} is the file number modulo 1000, so this view asks for about a thousand groups `
               + 'over 5,100 files and the group count is itself a load. A refusal here is therefore NOT '
               + 'attributable to the missing index alone, which is why this row is a witness beside the '
               + 'indexed one and nothing depends on it. What it is good for is the pair: the two views '
               + 'differ only in the index, on one library at one size, which is the comparison no REST '
               + 'probe could take.',
           readable ? undefined : 'void');
    stampRemaining('NOT REACHED', 'STATE was 4, the unindexed witness. Paste again with STATE 5 if the filter pane opens.');
    report();
    return;
  }

  if (STATE === 5) {
    const panes = [];
    for (const node of document.querySelectorAll('[role="dialog"], [role="menu"], [role="listbox"]')) {
      const text = String(node.textContent || '').trim();
      if (text) panes.push(clip(text, 160));
      if (panes.length >= ROW_CAP) break;
    }
    const inPane = CHOICES.filter((c) => panes.some((p) => p.includes(c)));
    const offered = inPane.length >= 2;
    record('library.large-list.ui-column-header-filter-past-threshold',
           `Does the column-header filter on ${CHOICE} offer values past ${THRESHOLD} items`,
           !readable ? 'NOT ESTABLISHED'
             : banner.matched.length ? 'REFUSED (banner)'
               : offered ? 'VALUES OFFERED' : 'MANUAL',
           !readable ? voidWhy
             : `${panes.length} pane-like element(s) found, showing ${JSON.stringify(panes)}; of the four `
               + `${CHOICE} values, ${JSON.stringify(inPane)} appear inside one. banner phrases `
               + `${JSON.stringify(banner.matched)}. `
               + (offered
                 ? 'The filter pane offers values past the threshold, which is a distinct-value read over '
                   + `${TARGET_FILES} files and is the same shape of aggregation a group-by asks for. `
                   + 'Report it beside STATE 3: the two agreeing is a stronger statement than either.'
                 : 'The pane was not read cleanly. This row is MANUAL by design rather than guessed at: '
                   + 'report what the screenshot shows, and if the pane would not open at all say that '
                   + 'instead of reporting a refusal.'),
           readable ? undefined : 'void');
    stampRemaining('NOT REACHED', 'STATE was 5, the filter pane. Every other row is read at its own state.');
    report();
    return;
  }

  log('FAIL', `STATE is ${STATE}, which is not one of 0, 1, 2, 3, 4 or 5. Nothing was read.`);
  report();
})();
