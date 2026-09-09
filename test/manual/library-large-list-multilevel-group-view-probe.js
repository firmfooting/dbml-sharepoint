/**
 * dbml-sharepoint PROBE: DOES AN INDEX EVER LET A GROUP-BY THROUGH PAST 5,000
 * ITEMS, ON ONE LEVEL OR ON THREE?
 *
 * ONE QUESTION, asked four ways:
 *   #480 indexed LVChoice on this fixture and the group-by on it was still
 *   refused 61 seconds later, while the filter on the same column was served in
 *   144 ms. That probe said its own result was not conclusive, because
 *   SharePoint builds the index behind the flag and "still refused just after
 *   the filter served" is not "still refused". So: does a group-by on an indexed
 *   column serve given a wait measured in minutes rather than in seconds, does a
 *   THREE-LEVEL group-by on three indexed columns serve, does the filter keep
 *   serving at the same moment the group-by is refused, and is that refusal
 *   still the threshold rather than something else?
 *
 * REVISION: 2315d2f3
 *
 * THE FIXTURE IS READ, NEVER REBUILT. `library-large-list-fixture-probe.js`
 * builds and owns 'dbmlsp Probe LargeLib': about 5,500 files named
 * dbmlsp-lv-00001.txt upward, carrying LVText, LVChoice (Alpha..Delta),
 * LVNumber, LVDate, LVMultiChoice, LVCalc and LVLookup. Nothing here uploads a
 * file, creates a column, creates a folder or writes an item value.
 *
 * WHAT IT LEAVES BEHIND: nothing. Four writes, all undone in the same pass. A
 * Description marker on LVChoice, put back, and one MERGE of `Indexed: true` on
 * each of LVChoice, LVNumber and LVDate, cleared at the end. Every later probe
 * reading this fixture needs it unindexed, because an unindexed column is the
 * only thing that can witness the throttle, so a run that cannot clear the flags
 * says so loudly rather than leaving a fixture nobody was told had changed.
 *
 * WHAT IS ALREADY SETTLED, and is therefore not re-derived here.
 *   #472, `library-index-threshold-probe.js`, run 2026-09-08: past the
 *   threshold a selective OData filter on Id is SERVED, while Title, Name
 *   (FileLeafRef), Created, Modified, Author and Editor are each REFUSED with
 *   SPQueryThrottledException. Only Id carries a native index.
 *   #478, `library-large-list-index-probe.js`, run 2026-09-08: LVText,
 *   LVNumber, LVChoice, LVDate and LVLookup all accept `Indexed: true` on this
 *   fixture, an index turns a refused filter or sort into a served one, and an
 *   index lifts its own column only. LVMultiChoice and LVCalc are REFUSED.
 *   #479, `library-large-list-calculated-probe.js`, run 2026-09-08: a group-by
 *   on the UNINDEXED LVChoice came back HTTP 500 with the threshold signature.
 *   #480, `library-large-list-group-view-probe.js`, run 2026-09-08: a group-by
 *   on Id, the one natively indexed column, was still refused; a group-by on
 *   LVChoice was still refused after the column was indexed and the filter on it
 *   had started serving; the default view rendered its first page; Scope changed
 *   nothing; and an Id-narrowed group-by over six rows was HONOURED. That last
 *   result is what makes a positive control possible here at all.
 *
 * WHY #480 DID NOT CLOSE THIS. Its after half waited on the FILTER and then
 * re-sent the grouped query up to ten times, six seconds apart, so the longest
 * it ever waited on the group-by was about a minute. A filter index and the
 * aggregation a group-by needs are not obviously the same object and need not
 * finish building together, and #480 wrote its own row to say so. Nothing about
 * a one-minute wait separates "an index does not lift a group-by" from "an index
 * had not finished building". This probe waits minutes and reports the attempts
 * and the elapsed time either way, so a refusal at the end of it is a refusal
 * with a number beside it.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. All of it files under `library.large-list`,
 * the scope for reading this fixture past the threshold. Thirteen ids are
 * already registered by #478, #479 or #480 and are kept, because the question
 * and the method are the same and one question takes one id however many probes
 * answer it.
 *
 *   library.large-list.fixture-library-present
 *        Is the fixture library there, holding more than 5,000 files, with the
 *        seven contract columns reading back as their types?
 *   library.large-list.fixture-index-flags-clear
 *        Does every contract column read Indexed=false before this run writes
 *        anything? A subject column arriving indexed would make the before half
 *        of every measurement below an indexed reading called an unindexed one.
 *   library.large-list.control-id-query-served
 *        POSITIVE CONTROL: is a selective OData filter on Id served past the
 *        threshold? Id is the one natively indexed column, so this establishes
 *        that a served answer is observable on this library at this size.
 *   library.large-list.control-absent-column-refused
 *        NEGATIVE CONTROL: is an OData filter naming a column the library does
 *        not hold refused WITHOUT the throttle signature?
 *   library.large-list.control-unindexed-filter-refused
 *        NEGATIVE CONTROL: is a selective OData filter on an unindexed contract
 *        column refused WITH the throttle signature? Without it the library is
 *        not demonstrably enforcing the threshold.
 *   library.large-list.control-render-where-absent-refused
 *        NEGATIVE CONTROL: is a RenderListDataAsStream query whose `<Where>`
 *        names a column the library does not hold refused, and refused WITHOUT
 *        the throttle signature? That is the same discrimination on the surface
 *        every grouped question uses.
 *   library.large-list.control-missing-group-column-ungrouped
 *        Is a group-by naming a column the library does not hold ignored, with
 *        the rows the same query returns with no <GroupBy> at all, or refused?
 *        It was written as a negative control expecting IGNORED. Past 5,000
 *        items it is refused instead, so it reports what it read.
 *   library.large-list.control-multilevel-group-by-narrowed-honoured
 *        POSITIVE CONTROL, and the one this probe could not have been written
 *        without: is the THREE-LEVEL <GroupBy> honoured once a <Where> on the
 *        natively indexed Id has narrowed the rows to a handful? A <GroupBy>
 *        carrying three <FieldRef> children is a shape nothing in this
 *        repository has sent, so a refusal at full size could otherwise be the
 *        shape rather than the size. #480 measured the single-level version of
 *        this composition HONOURED, which is what makes the control takeable.
 *   library.large-list.control-choice-description-sticks
 *        POSITIVE CONTROL: does a Description MERGE on LVChoice read back? A
 *        MERGE that never reaches a column would report it as unindexable
 *        whatever SharePoint thinks of indexing it.
 *   library.large-list.control-choice-unknown-property-refused
 *        NEGATIVE CONTROL: is a MERGE naming a property SP.Field does not have
 *        refused? Without it, "the write was accepted" says nothing.
 *   library.large-list.control-group-by-single-value-column
 *        The unindexed single-level baseline, re-asked so that the generous-wait
 *        row below has a before half this transcript observed. #479 and #480
 *        both recorded REFUSED (threshold) under this id. It is a SUBJECT here
 *        rather than an instrument, and nothing declares a dependency on it.
 *   library.large-list.multilevel-group-by-unindexed
 *        The three-level group-by on LVChoice, LVNumber and LVDate while all
 *        three are unindexed. Honoured, ignored or refused, and on how many
 *        dimensions?
 *   library.large-list.index-choice-column
 *   library.large-list.index-number-column
 *   library.large-list.index-date-column
 *        The three writes the after halves rest on. #478 recorded all three as
 *        INDEXED. They are re-asked rather than cited so the transcript is
 *        self-contained.
 *   library.large-list.group-by-indexed-column-generous-wait
 *        QUESTION TWO: is a single-level group-by on the indexed LVChoice served
 *        when it is waited out for minutes rather than for one minute? Same
 *        subject as #480's `group-by-indexed-column`, different method, so it
 *        takes its own id: see the two-methods table in SURFACES.md.
 *   library.large-list.indexed-filter-serves-while-group-by-refused
 *        QUESTION THREE: at ONE moment, is the OData filter on the indexed
 *        LVChoice served while the group-by on that same column is refused? Two
 *        readings taken minutes apart cannot say that, and it is the observation
 *        that separates "the index has not built" from "the index does not serve
 *        an aggregation".
 *   library.large-list.multilevel-group-by-indexed
 *        QUESTION ONE: is the three-level group-by served once all three of its
 *        columns are indexed and each index has been waited out?
 *   library.large-list.multilevel-group-by-field-order
 *        Does the ORDER of the three <FieldRef> children change the answer, and
 *        how many of the three come back as grouping dimensions? Both halves,
 *        before the writes and after them.
 *   library.large-list.multilevel-group-by-refusal-signature
 *        QUESTION FOUR: does every refusal this run collects carry
 *        `SPQueryThrottledException` in its body, or does one of them carry
 *        something else? A malformed multi-level <GroupBy> refused for its shape
 *        is a different finding from one refused for the threshold, and the two
 *        are separable only in the body.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the fixture library exists, holds more
 *   than 5,000 files counted from the newest file name, and carries the seven
 *   contract columns as their declared types; LVChoice, LVNumber and LVDate all
 *   read Indexed=false before anything is written; an OData filter on Id is
 *   served; an OData filter naming an absent column is refused without the
 *   throttle signature; an OData filter on an unindexed contract column is
 *   refused with it; a rendered query whose <Where> names an absent column is
 *   refused; a group-by naming an absent column is ignored; the three-level
 *   group-by is honoured over an Id-narrowed row set; a Description MERGE on
 *   LVChoice sticks and an unknown property on it is refused.
 *   Observes (recorded, never asserted): whether a group-by is served, refused
 *   or ignored on one level or on three, before the writes and after them; how
 *   long each wait ran and how many attempts it took; how many of the three
 *   named fields come back as grouping dimensions; which field orders answer;
 *   which columns accept an index; and what each refusal body says. NOTHING here
 *   asserts that a group-by is honoured at any point. A run in which every
 *   grouped query at full size is refused is a successful run, and it is the
 *   result the three probes before this one point at.
 *
 * WHY THE UNINDEXED HALVES ARE SUBJECTS AND NOT CONTROLS. A control that fails
 * voids what depends on it, so the two must not be spelled the same way. On a
 * small library `library-grouping-probe.js` opens with a group-by that works and
 * reads everything else against it. That control cannot be taken at this size,
 * because #479 and #480 both measured that exact query returning the threshold.
 * So the before halves here record what they see and nothing declares a
 * dependency on them: a refusal is this probe's first result rather than a
 * failed instrument. The one grouping this probe does need to work is the
 * narrowed three-level control, which is narrowed precisely so that the
 * threshold cannot reach it.
 *
 * HOW A GROUPING IS READ, inherited from `library-grouping-probe.js`. A
 * <GroupBy> naming a column that does not exist came back HTTP 200 with flat
 * rows on 2026-09-08, so a group-by is never refused FOR ITS COLUMN NAME and
 * "accepted" means nothing. The discriminator is HONOURED against IGNORED: an
 * honoured group-by returns rows carrying `<Field>.COUNT.group`,
 * `<Field>.newgroup` and `<Field>.groupindex`, and an ignored one returns what
 * the same query returns with no <GroupBy>. A throttle is a third thing and
 * carries the threshold signature in the body. Every grouped question sends the
 * collapsed query, the expanded query and one flat baseline for that reason. A
 * collapsed row carries no file name, so nothing here reads file names off one.
 *
 * HOW MANY DIMENSIONS WERE HONOURED IS READ, NEVER ASSUMED. Nothing in this
 * repository has sent a <GroupBy> with three <FieldRef> children, and a request
 * SharePoint accepts while honouring one field of the three would return HTTP
 * 200 with grouping markers on it. So the dimension count is taken from the
 * markers: a field is a dimension if a returned row carries a marker key
 * prefixed with that field's name. It is counted over the collapsed rows and
 * again over the expanded rows, and both numbers are reported, because a
 * collapsed multi-level answer may carry only the outermost level's rows and a
 * count read off those alone would be a floor rather than a total.
 *
 * THE FIELD ORDER IS TRIED, NOT ASSUMED. Three orders of the same three columns
 * are sent, each collapsed. If one order is honoured and another refused, that
 * is the finding and the row names which was which. The orders are rotations
 * rather than all six permutations, because the question is whether order
 * matters at all and six legs would double the run for a second example of the
 * same answer.
 *
 * WHY THE FILTER AND THE GROUP-BY ARE INTERLEAVED. Question three is about ONE
 * moment. A filter read at 09:00 and a group-by read at 09:03 cannot say the
 * index was live for one and not the other, because the index may have finished
 * building in between. So the generous wait sends the grouped query and then
 * immediately the OData filter on the same column, on every attempt, and each
 * pair is recorded with the elapsed time it was taken at.
 *
 * WHY THE DATE INDEX IS WITNESSED WITH A SORT. The wait for an index to build
 * needs a query that goes from refused to served on that column. LVChoice and
 * LVNumber get a selective `$filter`. LVDate gets an `$orderby` instead, because
 * an OData date literal that is a day out or in the wrong zone comes back as a
 * refusal that is really a typo, and `library-large-list-fixture-probe.js`
 * recorded this fixture's dates reading back rendered in the site zone. A sort
 * has no literal to spell. #478 measured a sort going from refused to served on
 * an indexed column, which is what makes it usable as the signal.
 *
 * WHY OData FOR THE FILTER CONTROLS. From `library-index-threshold-probe.js`:
 * past the threshold an OData `$filter` no index can serve returns HTTP 500
 * SPQueryThrottledException while the same predicate in CAML returns HTTP 200
 * with a silently partial answer, so OData is the surface that reports the
 * threshold as an error. The grouped questions have to use the rendered view
 * surface, because a <GroupBy> has nowhere else to live, and that is why the
 * refusal discrimination is established separately on both surfaces.
 *
 * THE HARNESS CLEANUP FLAG DOES NOTHING HERE, on purpose. resetList() is never
 * called and CLEANUP is ignored: it would recycle a fixture that takes six
 * pastes to build.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL, element and attribute is one
 * Microsoft Learn documents, because a wrong spelling returns 404, isRefusal()
 * counts 404 as a refusal, and the probe would then print a claim about
 * SharePoint that was really a typo:
 *   Field read and MERGE via `fields/getbyinternalnameortitle('<name>')`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Items, `$filter`, `$orderby`, `$select` and `$top`:
 *     "Working with lists and list items with REST"
 *   Reading a view's rows without opening the page:
 *     "SP.List.renderListDataAsStream method"
 *   The `<Query>` children, in the order the syntax block gives them:
 *     "Query element (List)"
 *   Grouping a query, and the `Collapse` attribute:
 *     "GroupBy element (Query)"
 *   The comparison, its operands and the `Type` attribute of a value:
 *     "Geq element (Query)", "FieldRef element (Query)", "Value element (Query)"
 *   The threshold and the index model it rests on:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 * How many <FieldRef> children a <GroupBy> honours is NOT taken from any of
 * those. It is the thing being measured, and it is read off the response.
 *
 * SCOPE OF CLAIMS: one tenant, one library, one caller context, one moment. The
 * threshold is documented as an effective figure rather than a constant, and the
 * negative controls are what detect a fixture sitting too close to it.
 *
 * HOW TO RUN: the run plan, in order
 *   1. Open the site holding 'dbmlsp Probe LargeLib'. If it is not built, run
 *      library-large-list-fixture-probe.js first; this probe will not build it.
 *   2. If a previous run left the fixture's columns indexed, run
 *      library-large-list-index-probe.js with REMOVE_INDEXES_AT_END first.
 *   3. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   4. Set CONFIRMED and ALLOW_WRITES true. Paste. Expect up to about ten
 *      minutes, nearly all of it the bounded waits. It logs each wait as it goes,
 *      so a console that has gone quiet for two minutes is working, not hung.
 *   5. Copy the whole RESULTS block back verbatim, including the teardown lines
 *      after it.
 *
 * STATUS: NOT YET RUN. Authored against the merged findings of #472, #478, #479
 * and #480. Nothing below has been observed on a live site, and the finding lines
 * are inherited or about method until it has.
 */
// finding: multilevel-group-view-fixture-is-read-not-rebuilt - the fixture this
// probe measures costs six pastes to build, so nothing here uploads a file,
// creates a column or creates a folder, CLEANUP is ignored, and resetList() is
// never called. The contract it reads is stated in
// library-large-list-fixture-probe.js and the column types are read back.
// finding: multilevel-group-view-leaves-the-fixture-unindexed - this probe
// writes three index flags, on LVChoice, LVNumber and LVDate, and clears all
// three in the same pass. An unindexed column is what witnesses the throttle, so
// a fixture left indexed takes the instrument away from the next probe rather
// than merely changing it.
// finding: multilevel-group-view-index-flags-are-read-not-assumed - #478's
// teardown returns the contract columns to unindexed, and threshold-index-probe.js
// watched SharePoint index a column on its own between two runs. Both mean the
// flags have to be read at the start of every run: a subject column arriving
// indexed would make the before half an indexed reading called an unindexed one.
// finding: multilevel-group-view-a-minute-does-not-settle-an-index-build -
// #480, run 2026-09-08: the group-by on LVChoice was still refused after the
// filter on it had been served, but the longest that run ever waited on the
// grouped query was about a minute, and it recorded its own result as not
// closing the question. A filter index and the aggregation a group-by needs are
// not demonstrably the same object, so this probe waits minutes and prints the
// attempts and the elapsed time beside every verdict.
// finding: multilevel-group-view-a-group-by-is-never-refused-for-its-column -
// inherited from library-grouping-probe.js, first live run 2026-09-08: a
// <GroupBy> naming a column that does not exist returned HTTP 200 with flat rows.
// That is what makes "accepted" meaningless and the honoured/ignored pair the
// discriminator. A THROTTLE is a different refusal and carries the threshold
// signature in the body, which is why control-render-where-absent-refused exists.
// finding: multilevel-group-view-absent-column-group-by-is-refused-here -
// measured 2026-09-08 on this library and on PreIndex: that same <GroupBy>
// returns HTTP 500 carrying Microsoft.SharePoint.Client.UnknownError and no
// threshold signature, while library-grouping, library-nesting and
// library-view-interaction each read HTTP 200 with flat rows on a library
// holding under ten files the same day. The request is identical, so the
// refusal belongs to the container. The row therefore reports what the absent
// column did rather than failing for not being ignored, and every grouped row
// below reads its dimensions off server-produced group markers rather than off
// a comparison with the flat query, so none of them rests on this one.
// finding: multilevel-group-view-collapsed-rows-carry-no-file-name - inherited
// from library-grouping-probe.js, second live run 2026-09-08: a collapsed query's
// rows did not carry the FileLeafRef its ViewFields named. Nothing here reads a
// file name off a collapsed row, and a label count is read against the RowLimit,
// never as a distinct-value count.
// finding: multilevel-group-view-the-narrowed-grouping-is-the-only-instrument -
// #480, run 2026-09-08: an Id-guarded <Where> (Id >= newest-5, six rows) with a
// group-by is SERVED, and every grouped query at full size in that run was not.
// A narrowed row set is therefore the only place this probe can watch a grouping
// work, which is why the three-FieldRef shape is proved there before any refusal
// at full size is attributed to the threshold.
// finding: multilevel-group-view-dimension-count-is-read-off-the-markers -
// nothing in this repository has sent a <GroupBy> with three <FieldRef>
// children, so a request accepted while only the first field is honoured is a
// live possibility and it returns HTTP 200 with markers on it. The count is
// taken from the marker keys, over the collapsed rows and again over the
// expanded rows, and both are reported.
// finding: multilevel-group-view-one-moment-is-what-question-three-needs - a
// filter read at one time and a group-by read minutes later cannot say the index
// was live for one and not the other. The wait sends the grouped query and then
// the filter on the same column on every attempt, and records the pair with the
// elapsed time it was taken at.
// finding: multilevel-group-view-date-index-is-witnessed-with-a-sort - an OData
// date literal a day out or in the wrong zone returns a refusal that is really a
// typo, and library-large-list-fixture-probe.js recorded this fixture's dates
// reading back rendered in the site zone. LVDate's index build is therefore
// watched with an $orderby, which has no literal to spell, and #478 measured a
// sort going from refused to served on an indexed column.
// finding: multilevel-group-view-index-does-not-lift-a-group-by - measured
// 2026-09-08: on LVChoice, whose index write was INDEXED and whose filter was
// SERVED in 212 ms, a single-level <GroupBy> was re-sent for 176814 ms across
// 12 attempts and came back REFUSED (threshold) every time. The answer did not
// change over that window, which is the strongest form the claim can take from
// one run: an index does not lift a group-by.
// finding: multilevel-group-view-one-moment-separates-built-from-unserved -
// measured 2026-09-08: each wait attempt sent the grouped query and then the
// filter on the same indexed column back to back. At every timestamp (646 ms
// through 176814 ms) the filter was SERVED while the group-by was REFUSED in the
// same pair of requests, so "the index has not built" and "the index does not
// serve an aggregation" are told apart, and the latter is what was observed.
// finding: multilevel-group-view-three-level-group-by-is-rejected-not-throttled -
// measured 2026-09-08: a three-FieldRef <GroupBy> returned HTTP 500 with code
// -2147467259 "Cannot complete this action" and NO SPQueryThrottledException,
// over three field orders AND over an Id-narrowed six-row set. A multi-level
// group-by is refused by the query engine before the threshold applies, so it is
// a different failure from the single-level throttle and no index or row count
// rescues it.
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
 
  log('INFO', 'probe revision 2315d2f3. Quote this when reporting results.');

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
  // The three columns the multi-level group-by names, in the order this probe
  // treats as primary: fewest distinct values first, which is the order a person
  // building such a view would choose. LVChoice holds 4 values, LVDate 365 and
  // LVNumber 1000, so the primary order is not sorted by cardinality throughout;
  // it is the order the columns are declared in the fixture contract, and the
  // point of the field-order question is that no order is assumed to be the one
  // SharePoint honours.
  const GROUP_COLUMNS = [CHOICE, NUMBER, DATE];
  // Rotations rather than all six permutations. See the field-order finding.
  const ORDERS = [
    [CHOICE, NUMBER, DATE],
    [DATE, NUMBER, CHOICE],
    [NUMBER, CHOICE, DATE],
  ];
  // The fixture's value formulas, for the columns queried below. The predicted
  // row counts come from these and the file count, so a served answer is
  // checked rather than believed.
  const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
  const CHOICE_MATCH = CHOICES[0];
  const NUMBER_MATCH = 7;
  const TEXT_MATCH = 'text-7';

  // More than the documented 5,000, so every query below is asked past it.
  const FLOOR = 5001;
  // Well below any page ceiling, so a query that fills the page is visibly
  // uncounted rather than quietly rounded.
  const PAGE = 100;
  // The same figure for a rendered view, and for the same reason.
  const ROW_LIMIT = 100;
  const FILE_NUMBER = /dbmlsp-lv-(\d+)\.txt$/;
  // The two strings a throttled query comes back with, and each on its own.
  // THROTTLE classifies a response; the two halves answer question four, which
  // is about which of them a refusal actually carried.
  const THROTTLE_EXCEPTION = /SPQueryThrottledException/;
  const THRESHOLD_PROSE = /exceeds the list view threshold/i;
  const THROTTLE = /exceeds the list view threshold|SPQueryThrottledException/i;
  // A column name the library does not hold, for the negative controls.
  const ABSENT_COLUMN = 'LVNoSuchColumnAtAll';
  // A name SP.Field does not have. Deliberately not a near-miss of a real
  // property: the control asks whether an unknown name is refused, not whether
  // a typo is tolerated.
  const UNKNOWN_PROPERTY = 'NoSuchFieldPropertyAtAll';
  const DESCRIPTION_MARKER = 'dbmlsp multilevel group-view control marker';
  // One bounded re-read after a write. Same figure and same reasoning as
  // library-large-list-index-probe.js: a readback racing a write is a false
  // negative, a retry loop eventually passes anything.
  const REREAD_MS = 1500;
  // The wait for an index to start serving an OData query, which is the signal
  // #478 used that the build had finished. Ten attempts six seconds apart.
  const INDEX_WAIT_ATTEMPTS = 10;
  const INDEX_WAIT_MS = 6000;
  // The generous wait a grouped query gets, and the whole reason this probe
  // exists. Twelve attempts fifteen seconds apart is three minutes, against the
  // one minute #480 gave it.
  const GROUP_WAIT_ATTEMPTS = 12;
  const GROUP_WAIT_MS = 15000;
  // The multi-level after half runs once the single-level wait above has already
  // spent minutes on the same three indexes, so it gets a shorter one.
  const MULTI_WAIT_ATTEMPTS = 6;
  // The keys an honoured group-by carries, named rather than matched on the
  // column name: every column in this fixture is called LV*, so a /group/i test
  // over a label key would report a grouping that is only a coincidence.
  const GROUP_MARKER = /\.COUNT\.group$|\.newgroup$|\.groupindex$/;
  // How far back from the newest item id the narrowed control's <Where> reaches.
  // Small enough that the grouping runs over a handful of rows, and the row
  // count is READ rather than predicted: item ids need not be contiguous.
  const GUARD_SPAN = 5;
  // Both documented spellings for a counter value, tried in turn: a
  // <Value Type=...> spelled wrongly comes back as a rejected request, which is
  // the same shape as the refusal that would be the finding.
  const ID_VALUE_TYPES = ['Counter', 'Integer'];

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const lit = (value) => String(value).replace(/'/g, "''");
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const uniq = (values) => values.filter((value, at) => values.indexOf(value) === at);

  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const fieldPath = (name) =>
    `${libPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  if (!CONFIRMED) {
    log('INFO', `Would READ the existing library '${LIB}' on ${WEB}: its file count, its`);
    log('INFO', 'seven columns and their Indexed flags. It builds NOTHING. It would then send');
    log('INFO', `selective OData filters and sorts reading at most ${PAGE} rows each, and`);
    log('INFO', `rendered view reads of at most ${ROW_LIMIT} rows: flat, grouped on one`);
    log('INFO', 'column, grouped on three, and grouped over an Id-narrowed row set.');
    log('INFO', `It writes four times: a Description marker on ${CHOICE}, put straight back,`);
    log('INFO', `and one MERGE of Indexed=true on each of ${GROUP_COLUMNS.join(', ')}, all`);
    log('INFO', 'cleared before the run ends. No file, item, column, folder or list is');
    log('INFO', 'created or deleted, and no index is left behind.');
    log('INFO', 'It waits, on purpose: up to about ten minutes, nearly all of it bounded');
    log('INFO', 'waits for asynchronous index builds and for grouped queries to be served.');
    log('INFO', 'CLEANUP does NOTHING in this probe: it would recycle the fixture.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write three fields.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }
  if (CLEANUP) {
    log('INFO', 'CLEANUP is on and is IGNORED here: it would recycle a fixture that takes');
    log('INFO', 'six pastes to build. This probe has no destructive path at all.');
  }

  expect('library.large-list.fixture-library-present', `The fixture library '${LIB}' is present, holds more than 5,000 files and carries the seven contract columns`);
  expect('library.large-list.fixture-index-flags-clear', 'Every contract column reads Indexed=false before this run writes anything');
  expect('library.large-list.control-id-query-served', 'POSITIVE CONTROL: a selective filter on Id is served past the threshold');
  expect('library.large-list.control-absent-column-refused', 'NEGATIVE CONTROL: a filter naming a column the library does not hold is refused WITHOUT the throttle signature');
  expect('library.large-list.control-unindexed-filter-refused', 'NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature');
  expect('library.large-list.control-render-where-absent-refused', 'NEGATIVE CONTROL: a rendered query whose <Where> names a column the library does not hold is refused WITHOUT the throttle signature');
  expect('library.large-list.control-missing-group-column-ungrouped', 'Is a group-by naming a column the library does not hold ignored or refused past 5,000 items');
  expect('library.large-list.control-multilevel-group-by-narrowed-honoured', 'POSITIVE CONTROL: a three-level <GroupBy> is honoured once a <Where> on Id has narrowed the rows to a handful');
  expect('library.large-list.control-choice-description-sticks', `POSITIVE CONTROL: a Description MERGE on ${CHOICE} itself reads back`);
  expect('library.large-list.control-choice-unknown-property-refused', `NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused on ${CHOICE}`);
  expect('library.large-list.control-group-by-single-value-column', `Is a group-by on the unindexed ${CHOICE} honoured, ignored or refused past 5,000 items`);
  expect('library.large-list.multilevel-group-by-unindexed', `Is a three-level group-by on ${GROUP_COLUMNS.join(', ')} honoured, ignored or refused while all three are unindexed`);
  expect('library.large-list.index-choice-column', `Does Indexed=true take on ${CHOICE} (Choice) past 5,000 items`);
  expect('library.large-list.index-number-column', `Does Indexed=true take on ${NUMBER} (Number) past 5,000 items`);
  expect('library.large-list.index-date-column', `Does Indexed=true take on ${DATE} (DateTime) past 5,000 items`);
  expect('library.large-list.group-by-indexed-column-generous-wait', `Is a group-by on the indexed ${CHOICE} served when it is waited out for minutes rather than for one minute`);
  expect('library.large-list.indexed-filter-serves-while-group-by-refused', `At one moment, is the filter on the indexed ${CHOICE} served while the group-by on it is refused`);
  expect('library.large-list.multilevel-group-by-indexed', 'Is a three-level group-by served once all three of its columns are indexed');
  expect('library.large-list.multilevel-group-by-field-order', 'Does the order of the three <FieldRef> children change what a three-level group-by is given');
  expect('library.large-list.multilevel-group-by-refusal-signature', 'Does every grouped refusal carry SPQueryThrottledException, or does one carry something else');

  // Every row still carrying the harness sentinel, stamped with one reason. A
  // run that stops early must not report questions it never asked as merely
  // unreached.
  const abortRemaining = (outcome, why) => {
    for (const row of RESULTS) {
      if (row.evidence === 'the run did not reach this question') {
        record(row.id, row.question, outcome, why);
      }
    }
  };

  // ---- Reading instruments ---------------------------------------------
  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the whole request, and every column would then
  // read as unreadable rather than as missing one property.
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

  // The entity type SharePoint itself reports for a field, read verbose because
  // nometadata is defined by not carrying it. Only ever consulted after a
  // refusal, to separate a rejected TYPE from a rejected WRITE.
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

  // Every refusal a grouped query in this run came back with, kept whole so
  // question four is answered from the bodies rather than from a verdict string.
  const REFUSALS = [];
  const noteRefusal = (label, seen) => {
    if (seen.res.ok) return;
    const text = seen.res.text || '';
    REFUSALS.push({
      label,
      status: seen.res.status,
      exception: THROTTLE_EXCEPTION.test(text),
      prose: THRESHOLD_PROSE.test(text),
      body: clip(text, 200),
    });
  };

  // One OData query, classified from the FULL body and quoted from a clipped
  // copy. Classifying from the clipped text would miss a throttle signature that
  // sits past the clip.
  const askQuery = async (query, label, select) => {
    const r = await spGet(`${libPath}/items?$select=${select || 'Id'}&$top=${PAGE}&${query}`);
    const raw = r.body ? JSON.stringify(r.body) : '';
    return {
      ok: r.ok,
      status: r.status,
      label,
      rows: (r.ok && r.body && Array.isArray(r.body.value)) ? r.body.value.length : -1,
      value: (r.ok && r.body && Array.isArray(r.body.value)) ? r.body.value : [],
      throttled: THROTTLE.test(raw),
      transient: r.status === 429 || r.status === 408 || r.status === 503,
      body: raw ? clip(raw, 260) : '(no body)',
    };
  };
  const askFilter = (filter, select) =>
    askQuery(`$filter=${encodeURIComponent(filter)}`, `$filter=${filter}`, select);
  // A sort has no literal to spell. See the date-index finding.
  const askSort = (field) =>
    askQuery(`$orderby=${encodeURIComponent(field)}`, `$orderby=${field}`);

  // `expected` is the row count the fixture's own formulas give this filter.
  // null means the count is not being compared, which is the case for a filter
  // whose match set is bigger than the page and for every sort.
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

  // ---- Reading a rendered view -----------------------------------------
  const rowsOf = (res) => {
    if (readFailed(res)) return [];
    if (Array.isArray(res.body.Row)) return res.body.Row;
    if (res.body.ListData && Array.isArray(res.body.ListData.Row)) return res.body.ListData.Row;
    return [];
  };

  // A group-by may name one field or several, so every caller passes whichever
  // shape it means and this normalises. A null or absent groupBy is the flat
  // baseline the ignored signature is read against.
  const groupFields = (opts) => {
    if (opts.groupBy === undefined || opts.groupBy === null) return [];
    return Array.isArray(opts.groupBy) ? opts.groupBy : [opts.groupBy];
  };

  // One ViewXml. Every part is optional and every part is named by the caller,
  // because the whole subject here is which combination was sent. `<Query>`
  // children go Where then GroupBy, the order the syntax block in "Query element
  // (List)" gives them. The absent-column controls pass their own `fields`, so a
  // column that does not exist is named ONLY in the clause under measurement and
  // never in <ViewFields>, where a refusal would be about the wrong clause: the
  // rule library-grouping-probe.js set for the same control.
  const viewXmlFor = (opts) => {
    const scope = (opts.scope === undefined || opts.scope === null) ? '' : ` Scope="${opts.scope}"`;
    const where = opts.minId === undefined || opts.minId === null
      ? (opts.whereOn
        ? `<Where><Eq><FieldRef Name="${opts.whereOn}"/>`
          + `<Value Type="Text">${opts.whereValue}</Value></Eq></Where>`
        : '')
      : `<Where><Geq><FieldRef Name="ID"/>`
        + `<Value Type="${opts.idType}">${opts.minId}</Value></Geq></Where>`;
    const grouped = groupFields(opts);
    const grouping = grouped.length
      ? `<GroupBy Collapse="${opts.collapse || 'TRUE'}">`
        + grouped.map((name) => `<FieldRef Name="${name}"/>`).join('')
        + '</GroupBy>'
      : '';
    const fields = uniq(opts.fields || ['FileLeafRef', NUMBER].concat(grouped));
    return `<View${scope}><Query>${where}${grouping}</Query><ViewFields>`
      + fields.map((name) => `<FieldRef Name="${name}"/>`).join('')
      + `</ViewFields><RowLimit>${ROW_LIMIT}</RowLimit></View>`;
  };

  const askView = async (opts) => {
    const xml = viewXmlFor(opts);
    const digest = await getDigest();
    const res = await spPost(`${libPath}/RenderListDataAsStream`,
                             { parameters: { ViewXml: xml } }, digest);
    return {
      res,
      rows: rowsOf(res),
      xml,
      throttled: THROTTLE.test(res.text || ''),
      transient: res.status === 429 || res.status === 408 || res.status === 503,
    };
  };

  const judgeView = (seen) => {
    if (seen.transient) return 'NOT ESTABLISHED (throttled)';
    if (seen.throttled) return 'REFUSED (threshold)';
    if (!seen.res.ok && isRefusal(seen.res.status)) {
      return 'REFUSED (request rejected; read the body)';
    }
    if (!seen.res.ok) return `NOT ESTABLISHED (HTTP ${seen.res.status})`;
    if (seen.rows.length === ROW_LIMIT) {
      return `SERVED (${seen.rows.length} row(s), which is the RowLimit, so the count is a page`
        + ' rather than a total)';
    }
    return `SERVED (${seen.rows.length} row(s))`;
  };

  // The coarse class a comparison between two legs is made on. Row counts are
  // recorded beside it rather than folded into it.
  const classOf = (seen) => {
    if (seen.transient) return 'transient';
    if (seen.throttled) return 'refused-threshold';
    if (!seen.res.ok && isRefusal(seen.res.status)) return 'rejected';
    if (!seen.res.ok) return `http-${seen.res.status}`;
    return 'served';
  };

  const markersIn = (rows) => {
    const seen = [];
    for (const row of rows) {
      for (const key of Object.keys(row)) {
        if (GROUP_MARKER.test(key) && !seen.includes(key)) seen.push(key);
      }
    }
    return seen;
  };

  // Which of the fields the <GroupBy> named came back as grouping DIMENSIONS,
  // read off the markers SharePoint added rather than off the request. See the
  // dimension-count finding: a three-field group-by honoured on one field
  // returns HTTP 200 with markers, and only this tells the two apart.
  const dimensionsIn = (rows, fields) => fields.filter(
    (name) => rows.some((row) => Object.keys(row).some(
      (key) => GROUP_MARKER.test(key) && key.indexOf(`${name}.`) === 0)));

  const labelsFor = (rows, fields) => {
    const out = {};
    for (const name of fields) {
      out[name] = rows.map((row) => (name in row ? row[name] : undefined));
    }
    return out;
  };

  // Everything the SERVER said about one grouping, and nothing this probe worked
  // out for itself: a probe that sorts flat rows into buckets by reading each
  // row's value has measured its own arithmetic.
  const observeGroup = async (opts) => {
    const grouped = groupFields(opts);
    const label = opts.label || `group-by on ${grouped.join(' then ')}`;
    const collapsed = await askView({ ...opts, collapse: 'TRUE' });
    const expanded = await askView({ ...opts, collapse: 'FALSE' });
    const flat = await askView({ ...opts, groupBy: null });
    noteRefusal(`${label}, collapsed`, collapsed);
    noteRefusal(`${label}, expanded`, expanded);
    const markers = markersIn(collapsed.rows);
    const collapsedDims = dimensionsIn(collapsed.rows, grouped);
    const expandedDims = dimensionsIn(expanded.rows, grouped);
    const labels = labelsFor(collapsed.rows, grouped);
    const served = judgeView(collapsed);
    const verdict = !served.startsWith('SERVED') ? served
      : markers.length ? 'HONOURED'
        : (flat.res.ok && collapsed.rows.length === flat.rows.length) ? 'IGNORED'
          : 'NOT ESTABLISHED (no group markers, and the flat baseline did not answer)';
    return {
      collapsed, expanded, flat, markers, labels, verdict, grouped,
      collapsedDims, expandedDims,
      text: `collapsed HTTP ${collapsed.res.status} returned ${collapsed.rows.length} row(s) `
        + `against a RowLimit of ${ROW_LIMIT}, labels ${clip(show(labels), 300)}, grouping `
        + `markers ${clip(show(markers), 240)}, dimensions honoured `
        + `${collapsedDims.length} of ${grouped.length} on the collapsed rows `
        + `(${clip(show(collapsedDims), 120)}) and ${expandedDims.length} of ${grouped.length} on `
        + `the expanded rows (${clip(show(expandedDims), 120)}), first row `
        + `${clip(show(collapsed.rows.length ? collapsed.rows[0] : null), 300)}; expanded HTTP `
        + `${expanded.res.status} returned ${expanded.rows.length} row(s); the same query with no `
        + `<GroupBy> returned HTTP ${flat.res.status} with ${flat.rows.length} row(s); ViewXml `
        + `${clip(collapsed.xml, 320)}`
        + (collapsed.res.ok ? '' : `; collapsed body ${clip(collapsed.res.text, 220)}`),
    };
  };

  // The generous wait for a grouped query, with the OData query on the SAME
  // column sent immediately after each grouped attempt. That pairing is question
  // three and it is why the two are not measured separately. `ask` may be null,
  // for a wait with nothing to interleave.
  const untilGrouped = async (opts, ask, attemptsAllowed) => {
    const started = Date.now();
    const legs = [];
    let attempts = 0;
    let last = null;
    let lastAsked = null;
    while (attempts < attemptsAllowed) {
      if (attempts) await sleep(GROUP_WAIT_MS);
      last = await observeGroup(opts);
      lastAsked = ask === null ? null : await ask();
      attempts += 1;
      legs.push({
        atMs: Date.now() - started,
        group: last.verdict,
        asked: lastAsked === null ? null : judge(lastAsked, null),
      });
      log('INFO', `  attempt ${attempts}/${attemptsAllowed} at ${Date.now() - started} ms: `
        + `grouped ${last.verdict}`
        + (lastAsked === null ? '' : `, ${lastAsked.label} ${judge(lastAsked, null)}`));
      if (last.collapsed.res.ok || last.collapsed.transient) break;
    }
    return { seen: last, asked: lastAsked, legs, attempts, waitedMs: Date.now() - started };
  };

  const legNote = (legs) => legs
    .map((leg) => `at ${leg.atMs} ms grouped ${leg.group}`
      + (leg.asked === null ? '' : `, filter ${leg.asked}`))
    .join('; ');

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

  const flagNote = (name) => `${name}: Indexed=${show(flags[name] ? flags[name].indexed : null)}`
    + `, AutoIndexed=${show(flags[name] ? flags[name].auto : null)}`;
  const allFlags = () => COLUMN_TYPES.map(([name]) => flagNote(name)).join('; ');
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
           : libOk
             ? `every contract column read back as its declared type, and their index flags are ${allFlags()}`
             : '')
         + (present
           ? '. This probe does not build the fixture. It is owned by '
             + 'library-large-list-fixture-probe.js.'
           : '. Run library-large-list-fixture-probe.js until its fixture rows read PASS, '
             + 'then re-paste this one.'));

  if (!present) {
    abortRemaining('ABORTED',
                   'the fixture was not readable as this probe needs it, so no query was sent '
                   + 'and no field was written');
    report();
    return;
  }

  // ---- fixture-index-flags-clear ---------------------------------------
  // Read before anything is written. #478 leaves the columns it indexes indexed
  // unless its teardown flag was set, and threshold-index-probe.js watched
  // SharePoint index a column on its own between two runs.
  const indexedAlready = COLUMN_TYPES
    .map(([name]) => name)
    .filter((name) => flags[name].indexed !== false);
  const subjectsIndexed = GROUP_COLUMNS.filter((name) => flags[name].indexed !== false);
  const subjectsClear = subjectsIndexed.length === 0;
  record('library.large-list.fixture-index-flags-clear',
         'Every contract column reads Indexed=false before this run writes anything',
         indexedAlready.length === 0 ? 'PASS' : subjectsClear ? 'FAIL' : 'ABORTED',
         `${allFlags()}`
         + (indexedAlready.length === 0
           ? '. Nothing carries an index, so the unindexed half of every measurement below is '
             + 'takeable and the throttle has a witness.'
           : `. Not clear: ${indexedAlready.join(', ')} did not read Indexed=false. `
             + (subjectsClear
               ? `${GROUP_COLUMNS.join(', ')} are all unindexed, so every question below can still `
                 + 'be asked, and the witness for the throttle is named in the row below.'
               : `${subjectsIndexed.join(', ')} arrived indexed, so the before half of the `
                 + 'grouped questions cannot be measured at all: a group-by taken on them now '
                 + 'would be an indexed reading reported as an unindexed one. Run '
                 + 'library-large-list-index-probe.js with REMOVE_INDEXES_AT_END, then '
                 + 're-paste.')));

  if (!subjectsClear) {
    abortRemaining('ABORTED',
                   `${subjectsIndexed.join(', ')} arrived indexed, so the unindexed half of this `
                   + 'probe cannot be measured and no write was sent. Clear the fixture indexes '
                   + 'and re-paste');
    report();
    return;
  }

  // The predicted row counts, from the fixture's formulas and the file count. A
  // served answer carrying a different number was answered from something other
  // than the fixture this probe thinks it is reading.
  const tally = (predicate) => {
    let total = 0;
    for (let n = 1; n <= count; n += 1) if (predicate(n)) total += 1;
    return total;
  };
  const numberExpected = tally((n) => n % 1000 === NUMBER_MATCH);
  const textExpected = tally((n) => `text-${n % 100}` === TEXT_MATCH);
  // Bigger than the page on any real fixture, so its count is not compared.
  const choiceExpected = tally((n) => CHOICES[n % 4] === CHOICE_MATCH);
  const choiceFilter = `${CHOICE} eq '${lit(CHOICE_MATCH)}'`;
  const numberFilter = `${NUMBER} eq ${NUMBER_MATCH}`;

  // ---- control-id-query-served -----------------------------------------
  const idFilter = await askFilter(`Id eq ${newestId}`);
  const idFilterOutcome = judge(idFilter, 1);
  const idServed = idFilterOutcome.startsWith('SERVED');
  record('library.large-list.control-id-query-served',
         'POSITIVE CONTROL: a selective filter on Id is served past the threshold',
         idServed ? 'SERVED' : 'CONTROL FAILED, METHOD VOID',
         `${idFilter.label} on ${count} file(s): HTTP ${idFilter.status}, ${idFilterOutcome}`
         + (idServed
           ? '. A served answer is therefore observable on this library at this size, which is '
             + 'what the Id-narrowed control below rests on.'
           : `. Body: ${idFilter.body}. Id is the one natively indexed column `
             + '(library-index-threshold-probe.js, 2026-09-08), so a refusal here says the method '
             + 'cannot observe a served answer at all, not that an index is missing.'));

  // ---- control-absent-column-refused -----------------------------------
  const absent = await askFilter(`${ABSENT_COLUMN} eq 'x'`);
  const absentRefused = isRefusal(absent.status) && !absent.throttled;
  record('library.large-list.control-absent-column-refused',
         'NEGATIVE CONTROL: a filter naming a column the library does not hold is refused WITHOUT the throttle signature',
         absentRefused ? 'REFUSED (request rejected, no throttle signature)'
           : 'CONTROL FAILED, METHOD VOID',
         `${absent.label}: HTTP ${absent.status}, throttle signature `
         + `${absent.throttled ? 'PRESENT' : 'absent'}: ${absent.body}`
         + (absentRefused
           ? '. A rejected request and a throttled one are therefore distinguishable on the OData '
             + 'surface, which is what every filter refusal below is read against.'
           : absent.throttled
             ? '. A filter on a column that does not exist came back carrying the throttle '
               + 'signature, so no refusal below can be attributed to the threshold.'
             : '. The server did not refuse a filter on a column that does not exist, so a '
               + 'refusal below cannot be read as the server rejecting the query either.'));

  // ---- control-unindexed-filter-refused --------------------------------
  // The witness is whichever contract column still reads Indexed=false, taken in
  // preference order with the subject column first.
  const WITNESSES = [
    { field: CHOICE, filter: choiceFilter, expected: null, matching: choiceExpected },
    { field: TEXT, filter: `${TEXT} eq '${lit(TEXT_MATCH)}'`, expected: textExpected,
      matching: textExpected },
    { field: NUMBER, filter: numberFilter, expected: numberExpected, matching: numberExpected },
  ];
  const witness = WITNESSES.find((row) => flags[row.field].indexed === false) || null;
  const witnessSeen = witness === null ? null : await askFilter(witness.filter);
  const witnessOutcome = witnessSeen === null ? null : judge(witnessSeen, witness.expected);
  const throttleEnforced = witnessOutcome !== null
    && witnessOutcome.startsWith('REFUSED (threshold)') && absentRefused;
  record('library.large-list.control-unindexed-filter-refused',
         'NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature',
         witness === null ? 'NOT ESTABLISHED'
           : throttleEnforced ? 'REFUSED (threshold)' : 'CONTROL FAILED, METHOD VOID',
         witness === null
           ? 'every contract column read Indexed=true at the start of this run, so there is no '
             + 'unindexed column left to witness a throttle with. Run '
             + 'library-large-list-index-probe.js with REMOVE_INDEXES_AT_END, then re-paste: '
             + `flags were ${allFlags()}`
           : `${witnessSeen.label} on ${count} file(s), matching ${witness.matching} of them: HTTP `
             + `${witnessSeen.status}, ${witnessOutcome}. ${flagNote(witness.field)}: `
             + `${witnessSeen.body}`
             + (throttleEnforced
               ? '. The library is therefore past the threshold and throttling is enforced on it, '
                 + 'so a refusal below is the threshold and an answer served below is worth '
                 + 'something.'
               : '. Without a refusal here nothing below is evidence of the threshold: the '
                 + 'library may simply not be far enough past it for this tenant to enforce it.'));

  // ---- control-render-where-absent-refused -----------------------------
  // The same discrimination as control-absent-column-refused, on the surface the
  // grouped questions use. ViewFields deliberately omits ABSENT_COLUMN: it is
  // named in the <Where> alone, so a refusal is about the clause under
  // measurement.
  const renderAbsent = await askView({ whereOn: ABSENT_COLUMN, whereValue: 'x',
                                       fields: ['FileLeafRef'] });
  const renderAbsentRefused = !renderAbsent.res.ok && isRefusal(renderAbsent.res.status)
    && !renderAbsent.throttled;
  record('library.large-list.control-render-where-absent-refused',
         'NEGATIVE CONTROL: a rendered query whose <Where> names a column the library does not hold is refused WITHOUT the throttle signature',
         renderAbsentRefused ? 'REFUSED (request rejected, no throttle signature)'
           : 'CONTROL FAILED, METHOD VOID',
         `RenderListDataAsStream with <Where> on ${ABSENT_COLUMN}: HTTP `
         + `${renderAbsent.res.status} with ${renderAbsent.rows.length} row(s), throttle signature `
         + `${renderAbsent.throttled ? 'PRESENT' : 'absent'}: ${clip(renderAbsent.res.text, 240)}`
         + (renderAbsentRefused
           ? '. A rejected render and a throttled one are therefore distinguishable, so a REFUSED '
             + '(threshold) verdict on a grouped query below is the threshold rather than the '
             + 'server rejecting the query.'
           : renderAbsent.throttled
             ? '. A rendered query naming a column that does not exist came back carrying the '
               + 'throttle signature, so no grouped refusal below can be attributed to the '
               + 'threshold.'
             : '. The render surface did not refuse a query naming a column that does not exist, '
               + 'so a refusal below cannot be read as the server rejecting what was sent '
               + 'either.'));

  // ---- control-missing-group-column-ungrouped --------------------------
  // ViewFields deliberately omits ABSENT_COLUMN, for the same reason as above.
  const groupAbsent = await observeGroup({ groupBy: ABSENT_COLUMN,
                                           fields: ['FileLeafRef', NUMBER],
                                           label: 'group-by on a column that does not exist' });
  const groupIgnorable = groupAbsent.verdict === 'IGNORED';
  record('library.large-list.control-missing-group-column-ungrouped',
         'Is a group-by naming a column the library does not hold ignored or refused past 5,000 items',
         groupAbsent.verdict,
         `${groupAbsent.verdict}. ${groupAbsent.text}`
         + (groupIgnorable
           ? '. An ignored group-by is therefore observable and is not the same reading as an '
             + 'honoured one, which is the only discriminator a served group-by offers.'
           : '. See the absent-column-refused finding: the same request is served and ignored on '
             + 'a small library, so what changed is the container rather than the request. A '
             + 'grouped row below reads HONOURED off the server-produced group markers rather '
             + 'than off a comparison with the flat query, so it does not need this reading.'));

  // ---- control-multilevel-group-by-narrowed-honoured -------------------
  // The three-FieldRef shape, proved where the threshold cannot reach it. The Id
  // value type is tried rather than assumed: a wrong spelling comes back as a
  // rejected request, the same shape as the refusal that would be the finding.
  const minId = newestId - GUARD_SPAN;
  const idTypeAttempts = [];
  let idType = null;
  for (const type of ID_VALUE_TYPES) {
    const seen = await askView({ minId, idType: type,
                                 fields: ['FileLeafRef', NUMBER, CHOICE] });
    idTypeAttempts.push(`Type="${type}": HTTP ${seen.res.status}, ${judgeView(seen)}`
      + (seen.res.ok ? '' : ` ${clip(seen.res.text, 160)}`));
    if (seen.res.ok || seen.throttled) {
      idType = type;
      break;
    }
  }

  const narrowedVoid = !idServed
    ? 'the positive control was not served, so an Id clause cannot narrow anything on this run '
      + 'and a narrowed grouping measures nothing'
    : !renderAbsentRefused
      ? 'the render surface did not separate a rejected request from a throttled one, so a '
        + 'refusal here could not be read either way'
      : idType === null
        ? 'neither documented counter spelling reached the query planner, so the <Where> this '
          + `control needs was never accepted: ${idTypeAttempts.join('; ')}`
        : null;
  let narrowed = null;
  let narrowedHeld = false;
  if (narrowedVoid !== null) {
    record('library.large-list.control-multilevel-group-by-narrowed-honoured',
           'POSITIVE CONTROL: a three-level <GroupBy> is honoured once a <Where> on Id has narrowed the rows to a handful',
           'CONTROL FAILED, METHOD VOID', narrowedVoid, 'void');
  } else {
    narrowed = await observeGroup({
      minId, idType, groupBy: GROUP_COLUMNS,
      fields: ['FileLeafRef'].concat(GROUP_COLUMNS),
      label: 'three-level group-by over an Id-narrowed row set',
    });
    narrowedHeld = narrowed.verdict === 'HONOURED';
    record('library.large-list.control-multilevel-group-by-narrowed-honoured',
           'POSITIVE CONTROL: a three-level <GroupBy> is honoured once a <Where> on Id has narrowed the rows to a handful',
           narrowedHeld ? 'HONOURED' : 'CONTROL FAILED, METHOD VOID',
           `<Where><Geq> on ID at ${minId} (the newest item id ${newestId} less ${GUARD_SPAN}), `
           + `grouping on ${GROUP_COLUMNS.join(' then ')} with all three unindexed. The counter `
           + `spelling was tried rather than assumed: ${idTypeAttempts.join('; ')}, so `
           + `Type="${idType}" is what answered. ${narrowed.text}`
           + (narrowedHeld
             ? '. A <GroupBy> carrying three <FieldRef> children is therefore a request this '
               + 'server accepts and acts on, so a refusal of the same shape at full size below '
               + 'is about the size. How many of the three came back as dimensions is recorded '
               + 'above and is a finding in its own right, not a condition of this control.'
             : '. The three-FieldRef shape was not honoured even over a handful of rows, so a '
               + 'refusal of the same shape at full size cannot be attributed to the threshold: '
               + 'it may be the shape. Read the collapsed body above before reading anything '
               + 'below it.'));
  }

  // ---- multilevel-group-by-unindexed: the before half ------------------
  const multiBefore = await observeGroup({
    groupBy: GROUP_COLUMNS,
    fields: ['FileLeafRef'].concat(GROUP_COLUMNS),
    label: 'three-level group-by, unindexed',
  });
  if (!narrowedHeld) {
    record('library.large-list.multilevel-group-by-unindexed',
           `Is a three-level group-by on ${GROUP_COLUMNS.join(', ')} honoured, ignored or refused while all three are unindexed`,
           'VOID',
           'the narrowed control did not hold, so a refusal here cannot be told from the server '
           + `rejecting a three-FieldRef <GroupBy>. What was observed anyway: ${multiBefore.text}`,
           'void');
  } else {
    record('library.large-list.multilevel-group-by-unindexed',
           `Is a three-level group-by on ${GROUP_COLUMNS.join(', ')} honoured, ignored or refused while all three are unindexed`,
           multiBefore.verdict,
           `with ${GROUP_COLUMNS.map(flagNote).join('; ')} as read at the start of the run, over `
           + `${count} file(s): ${multiBefore.text}`
           + (multiBefore.verdict.startsWith('REFUSED (threshold)')
             ? '. This is the before half of the index question below, and it is a result rather '
               + 'than a control: nothing declares a dependency on it.'
             : '. A three-level group-by that is not refused with no index on any of its columns '
               + 'leaves the after half nothing to measure, and the row below says so.'));
  }

  // ---- control-group-by-single-value-column: the single-level before ---
  // Re-asked so the generous-wait row below has a before half this transcript
  // observed. #479 and #480 both recorded REFUSED (threshold) under this id.
  const singleBefore = await observeGroup({ groupBy: CHOICE,
                                            label: `group-by on the unindexed ${CHOICE}` });
  record('library.large-list.control-group-by-single-value-column',
         `Is a group-by on the unindexed ${CHOICE} honoured, ignored or refused past 5,000 items`,
         singleBefore.verdict,
         `with ${flagNote(CHOICE)} as read at the start of the run, over ${count} file(s) and the `
         + `four values ${show(CHOICES)}: ${singleBefore.text}`
         + (singleBefore.verdict.startsWith('REFUSED (threshold)')
           ? '. That matches #479 and #480 by the same method, and it is the before half the '
             + 'generous wait below is compared against.'
           : '. #479 and #480 both recorded this same query as REFUSED (threshold) on 2026-09-08, '
             + 'so a different answer here is a change in the fixture or in the tenant and the '
             + 'transcripts have to be read together.'));

  // ---- The field-order legs, before the writes -------------------------
  // Collapsed only, and classified rather than judged in full: the question is
  // whether one order answers where another does not.
  const orderLeg = async (order, when) => {
    const seen = await askView({ groupBy: order, collapse: 'TRUE',
                                 fields: ['FileLeafRef'].concat(order) });
    noteRefusal(`three-level group-by ${order.join('>')} (${when})`, seen);
    return {
      order, when,
      klass: classOf(seen),
      status: seen.res.status,
      rows: seen.rows.length,
      dims: dimensionsIn(seen.rows, order),
      body: seen.res.ok ? '' : clip(seen.res.text, 160),
    };
  };
  const orderLegs = [];
  for (const order of ORDERS) orderLegs.push(await orderLeg(order, 'unindexed'));

  // ---- control-choice-description-sticks -------------------------------
  // The field MERGE itself, proved on one of the columns the index writes target
  // and on a property whose readback is not in doubt. One control covers the
  // three writes, the rule library-large-list-index-probe.js used for seven.
  const priorDescription = flags[CHOICE].description;
  const setDesc = await mergeField(CHOICE, { Description: DESCRIPTION_MARKER }, 'SP.Field');
  let descRead = await readField(CHOICE);
  let descReRead = false;
  const descriptionNow = () => (readFailed(descRead) ? null : descRead.body.Description);
  if (setDesc.ok && descriptionNow() !== DESCRIPTION_MARKER) {
    await sleep(REREAD_MS);
    descRead = await readField(CHOICE);
    descReRead = true;
  }
  const descSticks = setDesc.ok && descriptionNow() === DESCRIPTION_MARKER;
  record('library.large-list.control-choice-description-sticks',
         `POSITIVE CONTROL: a Description MERGE on ${CHOICE} itself reads back`,
         descSticks ? 'DESCRIPTION STUCK' : 'CONTROL FAILED, METHOD VOID',
         `MERGE Description on ${CHOICE} returned HTTP ${setDesc.status}; it reads back `
         + `${show(descriptionNow())}`
         + (descReRead ? `, on a re-read ${REREAD_MS} ms later` : '')
         + (descSticks
           ? '. A field MERGE reaches this column, so an index write below that changes nothing '
             + 'is the column and not a write that never arrived.'
           : `: ${clip(setDesc.text, 200)}. Nothing below can distinguish a column that refuses an `
             + 'index from a MERGE that never arrived.'));
  let descriptionRestored = !descSticks;
  if (descSticks) {
    // The marker is this probe's, not the fixture's. Put it back in the same
    // pass, and say so loudly if that fails.
    const restored = await mergeField(
      CHOICE,
      { Description: priorDescription === null || priorDescription === undefined
        ? '' : priorDescription },
      'SP.Field');
    descriptionRestored = restored.ok;
    log(restored.ok ? 'OK' : 'FAIL',
        restored.ok
          ? `Description on ${CHOICE} put back to ${show(priorDescription)}.`
          : `Description on ${CHOICE} is still the control marker: the restore returned HTTP `
            + `${restored.status} ${clip(restored.text, 200)}`);
  }

  // ---- control-choice-unknown-property-refused -------------------------
  const unknown = await mergeField(CHOICE, { [UNKNOWN_PROPERTY]: 'x' }, 'SP.Field');
  const unknownRefused = isRefusal(unknown.status);
  record('library.large-list.control-choice-unknown-property-refused',
         `NEGATIVE CONTROL: a MERGE naming a property SP.Field does not have is refused on ${CHOICE}`,
         unknownRefused ? 'REFUSED' : 'CONTROL FAILED, METHOD VOID',
         `MERGE ${UNKNOWN_PROPERTY} on ${CHOICE} returned HTTP ${unknown.status}: `
         + `${clip(unknown.text, 200)}`
         + (unknownRefused
           ? '. The endpoint therefore rejects a property it does not know, so "the write was '
             + 'accepted" below would mean the property was recognised.'
           : '. An unknown property was ACCEPTED, so acceptance of Indexed=true below would say '
             + 'nothing about whether the property was recognised.'));

  // ---- The three index writes ------------------------------------------
  // Lifted from library-large-list-index-probe.js, including the retry that
  // names the type SharePoint itself reports for the field: a rejected type hint
  // and a rejected write are otherwise the same observation.
  const methodControlsHeld = descSticks && unknownRefused;
  const indexResults = {};
  const indexColumn = async (name) => {
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
          + (stuck
            ? '. This confirms #478 by the same method. The teardown clears it, so the fixture is '
              + 'left as it was found.'
            : '. The write was accepted and changed nothing, which is the failure class this '
              + 'repository exists to find, and it contradicts #478'),
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
              ? `, and Indexed read back ${afterRetry && !readFailed(afterRetry)
                ? show(afterRetry.body.Indexed) : 'unreadable'}`
              : `: ${clip(retried.text, 160)}`)
            + '. The refusal is the column, not the type hint.')
        + ` This CONTRADICTS #478, which recorded ${name} as taking an index on this fixture.`,
    };
  };

  // SILENTLY IGNORED is the one verdict the method controls have to hold for. A
  // write that changed nothing and a write that never arrived look identical,
  // and only control-choice-description-sticks separates them.
  const runIndex = async (id, question, name) => {
    const result = await indexColumn(name);
    indexResults[name] = result;
    if (result.outcome === 'SILENTLY IGNORED' && !methodControlsHeld) {
      record(id, question, 'VOID',
             `${result.evidence}. The method controls did not hold (a Description MERGE `
             + `${descSticks ? 'stuck' : 'did not stick'} and an unknown property was `
             + `${unknownRefused ? 'refused' : 'accepted'}), so a write that changed nothing `
             + 'cannot be told from a write that never arrived',
             'void');
      return;
    }
    record(id, question, result.outcome, result.evidence);
  };

  await runIndex('library.large-list.index-choice-column',
                 `Does Indexed=true take on ${CHOICE} (Choice) past 5,000 items`, CHOICE);
  await runIndex('library.large-list.index-number-column',
                 `Does Indexed=true take on ${NUMBER} (Number) past 5,000 items`, NUMBER);
  await runIndex('library.large-list.index-date-column',
                 `Does Indexed=true take on ${DATE} (DateTime) past 5,000 items`, DATE);

  const indexed = (name) => indexResults[name] !== undefined && indexResults[name].indexed === true;

  // ---- Waiting for the three indexes to build --------------------------
  // The signal #478 used: an OData query that was refused with no index and is
  // served with one. LVDate gets a sort rather than a filter; see the date-index
  // finding in the header.
  const READY = [
    { field: CHOICE, ask: () => askFilter(choiceFilter), expected: null,
      label: `$filter=${choiceFilter}` },
    { field: NUMBER, ask: () => askFilter(numberFilter), expected: numberExpected,
      label: `$filter=${numberFilter}` },
    { field: DATE, ask: () => askSort(DATE), expected: null, label: `$orderby=${DATE}` },
  ];
  const readiness = {};
  for (const row of READY) {
    if (!indexed(row.field)) {
      readiness[row.field] = { skipped: true,
                               note: `${row.field} did not take an index this run, so nothing `
                                 + 'was waited for on it' };
      continue;
    }
    log('INFO', `Waiting for the index on ${row.field} to serve ${row.label}.`);
    const waited = await untilServed(row.ask);
    const outcome = judge(waited.result, row.expected);
    readiness[row.field] = {
      skipped: false,
      served: outcome.startsWith('SERVED'),
      attempts: waited.attempts,
      waitedMs: waited.waitedMs,
      note: `${row.label} was ${outcome} after ${waited.attempts} attempt(s) and `
        + `${waited.waitedMs} ms`,
    };
    log('INFO', `  ${readiness[row.field].note}.`);
  }
  const readyNote = GROUP_COLUMNS.map((name) => readiness[name].note).join('; ');
  const allReady = GROUP_COLUMNS.every((name) => readiness[name].served === true);

  // ---- group-by-indexed-column-generous-wait, and the interleave -------
  if (!indexed(CHOICE)) {
    const why = `${CHOICE} did not take an index this run `
      + `(index-choice-column: ${indexResults[CHOICE].outcome}), so there is no indexed half to `
      + 'measure and nothing to interleave a filter with';
    record('library.large-list.group-by-indexed-column-generous-wait',
           `Is a group-by on the indexed ${CHOICE} served when it is waited out for minutes rather than for one minute`,
           'NOT ESTABLISHED', why);
    record('library.large-list.indexed-filter-serves-while-group-by-refused',
           `At one moment, is the filter on the indexed ${CHOICE} served while the group-by on it is refused`,
           'NOT ESTABLISHED', why);
  } else {
    log('INFO', `Waiting up to ${GROUP_WAIT_ATTEMPTS} attempt(s) ${GROUP_WAIT_MS} ms apart for the `
      + `group-by on the indexed ${CHOICE}, sending ${choiceFilter} after each one.`);
    const waitedGroup = await untilGrouped({ groupBy: CHOICE,
                                             label: `group-by on the indexed ${CHOICE}` },
                                           () => askFilter(choiceFilter),
                                           GROUP_WAIT_ATTEMPTS);
    const after = waitedGroup.seen;
    const changed = singleBefore.verdict !== after.verdict;
    record('library.large-list.group-by-indexed-column-generous-wait',
           `Is a group-by on the indexed ${CHOICE} served when it is waited out for minutes rather than for one minute`,
           after.verdict,
           `before the index, the same query was ${singleBefore.verdict}. The index write was `
           + `${indexResults[CHOICE].outcome} and ${readiness[CHOICE].note}. The grouped query was `
           + `then re-sent over ${waitedGroup.attempts} attempt(s) and ${waitedGroup.waitedMs} ms, `
           + `against the roughly 61,000 ms #480 gave it: ${legNote(waitedGroup.legs)}. Last `
           + `reading: ${after.text}`
           + (changed
             ? '. The answer changed with the index and nothing else about the query changed, so '
               + 'the index is what the group-by wanted, and #480 stopped waiting too early.'
             : after.verdict.startsWith('REFUSED')
               ? `. The answer did not change over ${waitedGroup.waitedMs} ms. That is a longer `
                 + 'wait than #480 took and it is still a bounded one, so what it settles is that '
                 + 'an index does not lift this group-by within that window, which is the '
                 + 'strongest form the claim can take from one run.'
               : '. The answer did not change because the query was already answered this way '
                 + 'before the index was written, so this run says nothing about what the index '
                 + 'did and the before half is where to read what happened.'));

    const bothLeg = waitedGroup.legs.find(
      (leg) => leg.asked !== null && leg.asked.startsWith('SERVED')
        && leg.group.startsWith('REFUSED (threshold)'));
    const servedLeg = waitedGroup.legs.find(
      (leg) => leg.asked !== null && leg.asked.startsWith('SERVED')
        && leg.group.startsWith('SERVED'));
    const anyFilterServed = waitedGroup.legs.some(
      (leg) => leg.asked !== null && leg.asked.startsWith('SERVED'));
    record('library.large-list.indexed-filter-serves-while-group-by-refused',
           `At one moment, is the filter on the indexed ${CHOICE} served while the group-by on it is refused`,
           bothLeg !== undefined
             ? 'THE FILTER SERVES WHILE THE GROUP-BY IS REFUSED'
             : servedLeg !== undefined
               ? 'BOTH SERVED'
               : anyFilterServed
                 ? 'NOT ESTABLISHED (the filter served, but the grouped query was never refused with the threshold signature)'
                 : 'NOT ESTABLISHED (the filter never served, so there was nothing to interleave)',
           `each attempt sent the grouped query and then ${choiceFilter} immediately after it, on `
           + `the same column, whose index write was ${indexResults[CHOICE].outcome} and whose `
           + `${readiness[CHOICE].note}: ${legNote(waitedGroup.legs)}`
           + (bothLeg !== undefined
             ? `. At ${bothLeg.atMs} ms the index answered a filter and refused an aggregation in `
               + 'the same pair of requests. Two readings taken minutes apart could not say that, '
               + 'and it is what separates "the index has not built" from "the index does not '
               + 'serve an aggregation".'
             : servedLeg !== undefined
               ? '. Both were served in the same pair, so the index serves an aggregation as well '
                 + 'as a filter and the question is answered the other way.'
               : '. Without one pair in which the filter answered and the grouped query was '
                 + 'refused with the threshold signature, nothing here says the index was live '
                 + 'for one and not the other.'));
  }

  // ---- multilevel-group-by-indexed: QUESTION ONE -----------------------
  if (!narrowedHeld) {
    record('library.large-list.multilevel-group-by-indexed',
           'Is a three-level group-by served once all three of its columns are indexed',
           'VOID',
           'the narrowed control did not hold, so a refusal here cannot be told from the server '
           + 'rejecting a three-FieldRef <GroupBy>. Index writes: '
           + `${GROUP_COLUMNS.map((name) => `${name} ${indexResults[name].outcome}`).join(', ')}`,
           'void');
  } else if (!GROUP_COLUMNS.every(indexed)) {
    record('library.large-list.multilevel-group-by-indexed',
           'Is a three-level group-by served once all three of its columns are indexed',
           'NOT ESTABLISHED',
           'not every column the group-by names took an index this run, so there is no '
           + 'all-three-indexed state to measure: '
           + `${GROUP_COLUMNS.map((name) => `${name} ${indexResults[name].outcome}`).join(', ')}. `
           + `Readiness: ${readyNote}`);
  } else {
    log('INFO', `Waiting up to ${MULTI_WAIT_ATTEMPTS} attempt(s) ${GROUP_WAIT_MS} ms apart for the `
      + 'three-level group-by on the indexed columns.');
    const waitedMulti = await untilGrouped({
      groupBy: GROUP_COLUMNS,
      fields: ['FileLeafRef'].concat(GROUP_COLUMNS),
      label: 'three-level group-by, indexed',
    }, null, MULTI_WAIT_ATTEMPTS);
    const multiAfter = waitedMulti.seen;
    const multiChanged = multiBefore.verdict !== multiAfter.verdict;
    record('library.large-list.multilevel-group-by-indexed',
           'Is a three-level group-by served once all three of its columns are indexed',
           multiAfter.verdict,
           `grouping on ${GROUP_COLUMNS.join(' then ')}, all three indexed this run `
           + `(${GROUP_COLUMNS.map((name) => `${name} ${indexResults[name].outcome}`).join(', ')}) `
           + `and each index waited out: ${readyNote}`
           + (allReady ? '' : '. NOT every index was witnessed serving its own OData query, so '
             + 'the wait below may have started before the builds finished')
           + `. Before the writes the same query was ${multiBefore.verdict}. The grouped query was `
           + `re-sent over ${waitedMulti.attempts} attempt(s) and ${waitedMulti.waitedMs} ms, on `
           + 'top of the minutes the single-level wait above had already spent on the same three '
           + `indexes: ${legNote(waitedMulti.legs)}. Last reading: ${multiAfter.text}`
           + (multiChanged
             ? '. The answer changed with the indexes and nothing else about the query changed.'
             : multiAfter.verdict.startsWith('REFUSED')
               ? '. The answer did not change with the indexes. Read it beside the single-level '
                 + 'row above: if neither one level nor three is lifted by an index, an index is '
                 + 'not what a group-by past the threshold wants, whatever the guidance about '
                 + 'indexing a column before a library grows past 5,000 items implies for one.'
               : '. The answer did not change because the query was already answered this way '
                 + 'with none of the three columns indexed, so this run says nothing about what '
                 + 'the indexes did and the before half is where to read what happened.'));

    for (const order of ORDERS) orderLegs.push(await orderLeg(order, 'indexed'));
  }

  // ---- multilevel-group-by-field-order ---------------------------------
  const legsWhen = (when) => orderLegs.filter((leg) => leg.when === when);
  const sameWithin = (legs) => legs.length > 0
    && legs.every((leg) => leg.klass === legs[0].klass);
  const beforeLegs = legsWhen('unindexed');
  const afterLegs = legsWhen('indexed');
  const orderText = (legs) => (legs.length === 0
    ? 'not taken'
    : legs.map((leg) => `${leg.order.join(' > ')}: HTTP ${leg.status} ${leg.klass}, `
      + `${leg.rows} row(s), dimensions ${clip(show(leg.dims), 120)}`
      + (leg.body ? ` ${leg.body}` : '')).join('; '));
  const beforeSame = sameWithin(beforeLegs);
  const afterSame = afterLegs.length === 0 ? null : sameWithin(afterLegs);
  record('library.large-list.multilevel-group-by-field-order',
         'Does the order of the three <FieldRef> children change what a three-level group-by is given',
         beforeSame && afterSame !== false ? 'NO ORDER ANSWERED DIFFERENTLY'
           : 'ORDER CHANGES THE ANSWER',
         `${ORDERS.length} order(s) of the same three columns, each sent collapsed. Unindexed: `
         + `${orderText(beforeLegs)}. Indexed: ${orderText(afterLegs)}`
         + (afterLegs.length === 0
           ? '. The indexed half was not reached, so this row is about the unindexed legs alone.'
           : '')
         + (beforeSame && afterSame !== false
           ? '. Every order was given the same class of answer, so nothing below turns on which '
             + 'order the primary question used, and a view that groups on these three columns '
             + 'cannot be rescued by reordering them.'
           : '. One order was answered where another was not, which makes field order part of '
             + 'the finding rather than an implementation detail. The dimension counts beside '
             + 'each order are what say how much of the request survived.'));

  // ---- multilevel-group-by-refusal-signature: QUESTION FOUR ------------
  const refusalNote = REFUSALS.length === 0
    ? 'no grouped query in this run was refused at all'
    : REFUSALS.map((row) => `${row.label}: HTTP ${row.status}, SPQueryThrottledException `
      + `${row.exception ? 'PRESENT' : 'absent'}, threshold prose `
      + `${row.prose ? 'PRESENT' : 'absent'}: ${row.body}`).join('; ');
  const neither = REFUSALS.filter((row) => !row.exception && !row.prose);
  const proseOnly = REFUSALS.filter((row) => !row.exception && row.prose);
  record('library.large-list.multilevel-group-by-refusal-signature',
         'Does every grouped refusal carry SPQueryThrottledException, or does one carry something else',
         REFUSALS.length === 0 ? 'NO REFUSAL TO CLASSIFY'
           : neither.length ? 'A REFUSAL CARRIES NEITHER THRESHOLD SIGNATURE'
             : proseOnly.length ? 'SOME REFUSALS NAME THE THRESHOLD WITHOUT NAMING THE EXCEPTION'
               : 'EVERY REFUSAL CARRIES SPQueryThrottledException',
         `${REFUSALS.length} refusal(s) collected across every grouped query this run sent. `
         + `${refusalNote}`
         + (REFUSALS.length === 0
           ? '. Every grouped query was answered, so there is no refusal to attribute and the rows '
             + 'above stand on their served readings.'
           : neither.length
             ? '. At least one refusal named neither the exception nor the threshold, so it is a '
               + 'different finding from a throttle and the rows that rest on it have to be read '
               + 'against its body. A malformed multi-level <GroupBy> would look exactly like '
               + 'this, which is what the narrowed control exists to rule out.'
             : proseOnly.length
               ? '. Every refusal named the threshold, but not all of them named the exception '
                 + 'type, so a reader matching on the class name alone would miss some of them.'
               : '. The refusals are the throttle by its own name, not an error that merely reads '
                 + 'like one.'));

  report();

  // ---- Teardown ---------------------------------------------------------
  // Four writes to undo. The Description marker is restored above; this reports
  // whether that worked, and clears every index flag this run wrote. It also
  // names any contract column that arrived indexed, which this run did not put
  // there and does not clear.
  if (!descriptionRestored) {
    log('FAIL', `The Description marker is still on ${CHOICE}. Put it back to `
      + `${show(priorDescription)} by hand: the fixture is not as this run found it.`);
  }
  const toClear = GROUP_COLUMNS.filter(indexed);
  if (!toClear.length) {
    log('OK', 'No index was left on the fixture: no MERGE of Indexed=true was accepted, so the '
      + 'fixture is as this run found it.');
    return;
  }
  const cleared = [];
  const stillIndexed = [];
  for (const name of toClear) {
    const off = await mergeField(name, { Indexed: false }, 'SP.Field');
    const back = await readField(name);
    const isClear = off.ok && !readFailed(back) && back.body.Indexed === false;
    (isClear ? cleared : stillIndexed).push(name);
    log(isClear ? 'OK' : 'FAIL',
        isClear
          ? `${name}: Indexed is back to false.`
          : `${name}: Indexed is still ${readFailed(back) ? 'unreadable' : show(back.body.Indexed)} `
            + `after HTTP ${off.status} ${clip(off.text, 160)}. The fixture is NOT restored.`);
  }
  log(stillIndexed.length ? 'FAIL' : 'OK',
      `Teardown: ${cleared.length} of ${toClear.length} column(s) read Indexed=false on the `
      + `readback${cleared.length ? `: ${cleared.join(', ')}` : ''}`
      + (stillIndexed.length
        ? `. STILL INDEXED: ${stillIndexed.join(', ')}. The next probe reading this library has `
          + 'no unindexed column to witness the throttle with. Clear them by hand, or run '
          + 'library-large-list-index-probe.js with REMOVE_INDEXES_AT_END.'
        : '. The fixture is back to the state the next before/after measurement needs.'));
})();
