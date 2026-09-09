/**
 * dbml-sharepoint PROBE: DOES A COLUMN INDEXED BEFORE 5,000 ITEMS SERVE A
 * GROUP-BY THAT A COLUMN INDEXED AFTER 5,000 ITEMS CANNOT?
 *
 * ONE QUESTION. #481 measured, on a Choice column indexed while the library was
 * ALREADY past 5,000 files: the OData filter on that column was SERVED while the
 * <GroupBy> on the same column was REFUSED with the threshold signature, in the
 * same pair of requests, at every timestamp from 646 ms to 176,814 ms. The
 * guidance an operator meets says to index the column BEFORE the library passes
 * 5,000. If that ordering matters, a column indexed at 4,900 files and carried
 * past the threshold should serve a group-by that a post-hoc index does not. If
 * it does not matter, the two libraries answer the same way and the guidance is
 * about the index build rather than about what an aggregation is given.
 *
 * REVISION: 329bb72b
 *
 * THE FIXTURE IS READ. IT IS NEVER BUILT, WRITTEN TO, OR TORN DOWN.
 * `library-large-list-preindex-fixture-probe.js` builds and owns
 * 'dbmlsp Probe PreIndex': 5,100 files named dbmlsp-pre-00001.txt upward,
 * carrying PChoice (Choice, Alpha..Delta, from the file number modulo 4) and
 * PNumber (Number, the file number modulo 1000). PChoice was MERGEd
 * Indexed=true while the library still held 4,900 files, below the threshold,
 * and the count and the moment of that write are stamped into PChoice's
 * Description. PNumber is unindexed and stays that way, because an unindexed
 * column is the only thing that can witness the throttle.
 *
 * WHAT IT LEAVES BEHIND: nothing at all. This probe sends no MERGE, creates no
 * column, uploads no file and writes no item value. ALLOW_WRITES is never
 * consulted and CLEANUP does nothing. PChoice's index is the one irreplaceable
 * value in this fixture: it cannot be re-created without rebuilding the library
 * from empty, because writing it again past 5,000 files would produce exactly
 * the post-hoc index #481 already measured. Nothing here clears it.
 *
 * WHAT IS ALREADY SETTLED, and is therefore not re-derived here.
 *   #472, `library-index-threshold-probe.js`, run 2026-09-08: past the threshold
 *   a selective OData filter on Id is SERVED, while Title, Name (FileLeafRef),
 *   Created, Modified, Author and Editor are each REFUSED with
 *   SPQueryThrottledException. Only Id carries a native index. An OData $filter
 *   reports the threshold as an error; the same predicate in CAML returns HTTP
 *   200 with a silently partial answer.
 *   #478, `library-large-list-index-probe.js`, run 2026-09-08: a MERGE of
 *   Indexed=true is accepted on a Text, Number, Choice, DateTime or Lookup
 *   column of a library already past 5,000 files, an index turns a refused
 *   filter or sort into a served one, and it lifts its own column only.
 *   #479, `library-large-list-calculated-probe.js`, run 2026-09-08: a group-by
 *   on an unindexed Choice column came back HTTP 500 with the threshold
 *   signature.
 *   #480, `library-large-list-group-view-probe.js`, run 2026-09-08: a group-by
 *   on Id, the one natively indexed column, was REFUSED; a group-by on a Choice
 *   column was still refused after the column was indexed and the filter on it
 *   had started serving; the default view rendered its first page; Scope changed
 *   nothing; and a group-by over an Id-narrowed six-row set was HONOURED.
 *   #481, `library-large-list-multilevel-group-view-probe.js`, run 2026-09-08:
 *   the same single-level group-by, re-sent for 176,814 ms across 12 attempts
 *   with the filter interleaved, was REFUSED (threshold) every time while the
 *   filter was SERVED every time. A THREE-level <GroupBy> is a different failure
 *   again: HTTP 500, code -2147467259, no SPQueryThrottledException, over three
 *   field orders and over an Id-narrowed six-row set alike. The query engine
 *   rejects that shape before the threshold applies, which is why this probe
 *   sends one level and only one level.
 *
 * WHAT THIS PROBE ADDS, and what it cannot add. It changes exactly one thing
 * against #481: WHEN the index was written. Same method, same discriminators,
 * same signature discipline, a library of 5,100 files rather than about 5,500,
 * and a Choice column of the same four values. If the group-by is served here
 * and was refused there, the ordering is the whole finding. If it is refused
 * here too, then the guidance about indexing before 5,000 does not reach
 * aggregation, and two independent fixtures say so. What one run cannot do is
 * separate the ordering from every other difference between two libraries built
 * on different days, so a served answer here would want a second run before it
 * is read as a rule.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. All of it files under `library.large-list`,
 * the scope for reading a library past the threshold. Five ids are already
 * registered by the fixture probe or by #480 and are kept, because the question
 * and the method are the same and one question takes one id however many probes
 * answer it.
 *
 *   library.large-list.fixture-preindex-library-present
 *        Is the pre-indexed fixture there, holding more than 5,000 files, with
 *        both contract columns reading back as their types?
 *   library.large-list.fixture-preindex-index-written-under-threshold
 *        Does PChoice read Indexed=true, AND does its Description carry the
 *        stamp saying the flag was written below 5,000 files? Indexed=true on
 *        its own is equally consistent with an index written at 4,900 files and
 *        one written at 5,099, which is the only difference this probe is about.
 *   library.large-list.fixture-preindex-witness-unindexed
 *        Does PNumber read Indexed=false, so the throttle has a witness?
 *   library.large-list.control-id-query-served
 *        POSITIVE CONTROL: is a selective OData filter on Id served past the
 *        threshold? Id is the one natively indexed column, so this establishes
 *        that a served answer is observable on this library at this size.
 *   library.large-list.control-absent-column-refused
 *        NEGATIVE CONTROL: is an OData filter naming a column the library does
 *        not hold refused WITHOUT the throttle signature?
 *   library.large-list.control-unindexed-filter-refused
 *        NEGATIVE CONTROL: is a selective OData filter on the unindexed PNumber
 *        refused WITH the throttle signature? Without it this library is not
 *        demonstrably enforcing the threshold, and every refusal below could be
 *        something else.
 *   library.large-list.control-render-where-absent-refused
 *        NEGATIVE CONTROL: is a RenderListDataAsStream query whose <Where> names
 *        a column the library does not hold refused, and refused WITHOUT the
 *        throttle signature? That is the same discrimination on the surface
 *        every grouped question uses.
 *   library.large-list.control-missing-group-column-ungrouped
 *        Is a group-by naming a column the library does not hold ignored, with
 *        the rows the same query returns with no <GroupBy> at all, or refused?
 *        It was written as a negative control expecting IGNORED. Past 5,000
 *        items it is refused instead, so it reports what it read.
 *   library.large-list.control-preindex-filter-serves
 *        POSITIVE CONTROL: is the OData filter on PChoice served? The index is
 *        days old by the time this runs, so this is not a build wait. It is the
 *        reading that says the index is live at all, and without it a refused
 *        group-by below says nothing about aggregation.
 *   library.large-list.control-preindex-group-by-narrowed-honoured
 *        POSITIVE CONTROL: is the single-level <GroupBy> on PChoice honoured
 *        once a <Where> on the natively indexed Id has narrowed the rows to a
 *        handful? #480 measured that composition honoured on the other fixture.
 *        It is re-proved here because this is a different library with different
 *        column names, and without it a refusal at full size could be the
 *        request rather than the size.
 *   library.large-list.preindex-group-by-indexed-column
 *        THE CRUX: is a <GroupBy> on PChoice, indexed before the library crossed
 *        5,000 files, honoured, ignored or refused at 5,100 files? Collapsed and
 *        expanded, with a flat baseline beside them.
 *   library.large-list.preindex-filter-serves-while-group-by-refused
 *        At ONE moment, is the filter on PChoice served while the group-by on
 *        that same column is refused? Two readings taken a minute apart cannot
 *        say that. This is the observation #481 took on a post-hoc index, asked
 *        again of a pre-threshold one.
 *   library.large-list.preindex-group-by-unindexed-column
 *        Is the group-by on the unindexed PNumber still refused on this library
 *        at this size? The throttle has to be in force for the crux to mean
 *        anything, and this is the grouped-surface reading of that.
 *   library.large-list.group-by-native-index-column
 *        Is a group-by on Id refused here as it was on the other fixture? #480's
 *        id, same question, same method, second library.
 *   library.large-list.preindex-group-by-refusal-signature
 *        Does every refusal this run collects carry SPQueryThrottledException,
 *        or does one carry something else? A request rejected for its shape and
 *        one rejected for the threshold are separable only in the body.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the fixture library exists, holds more
 *   than 5,000 files counted from the newest file name, and carries PChoice and
 *   PNumber as their declared types; PChoice reads Indexed=true and its
 *   Description carries a stamp naming a count below 5,000; PNumber reads
 *   Indexed=false; an OData filter on Id is served; an OData filter naming an
 *   absent column is refused without the throttle signature; an OData filter on
 *   PNumber is refused with it; a rendered query whose <Where> names an absent
 *   column is refused; a group-by naming an absent column is ignored; the filter
 *   on PChoice is served; and the group-by on PChoice is honoured over an
 *   Id-narrowed row set.
 *   Observes (recorded, never asserted): whether the group-by on PChoice is
 *   honoured, ignored or refused at full size; whether the filter and the
 *   group-by disagree within one pair of requests; whether the group-by on
 *   PNumber and on Id are refused; how many attempts and how much elapsed time
 *   each reading took; and what each refusal body says. NOTHING here asserts
 *   that the group-by is honoured at full size. A run in which it is refused is
 *   a successful run, and it is the result #481 points at.
 *
 * WHY THE UNINDEXED AND Id GROUP-BYS ARE SUBJECTS AND NOT CONTROLS. A control
 * that fails voids what depends on it, so the two must not be spelled the same
 * way. #479, #480 and #481 all measured a group-by refused at this size, so a
 * refusal here is a result rather than a broken instrument, and nothing declares
 * a dependency on either row. The one grouping this probe does need to work is
 * the narrowed control, which is narrowed precisely so that the threshold cannot
 * reach it.
 *
 * HOW A GROUPING IS READ, inherited from `library-grouping-probe.js`. A
 * <GroupBy> naming a column that does not exist came back HTTP 200 with flat
 * rows on 2026-09-08, so a group-by is never refused FOR ITS COLUMN NAME and
 * "accepted" means nothing. The discriminator is HONOURED against IGNORED: an
 * honoured group-by returns rows carrying `<Field>.COUNT.group`,
 * `<Field>.newgroup` and `<Field>.groupindex`, and an ignored one returns what
 * the same query returns with no <GroupBy>. A throttle is a third thing and
 * carries the threshold signature in the body. Every grouped question therefore
 * sends the collapsed query, the expanded query and one flat baseline. A
 * collapsed row carries no file name, so nothing here reads file names off one.
 *
 * ViewFields NAME ONLY THE COLUMN UNDER MEASUREMENT. #481 sent an unindexed
 * Number column in <ViewFields> on every grouped query, including the ones
 * grouped on the indexed Choice column. That was harmless there because every
 * answer was a refusal attributed to the group-by, and it would not be harmless
 * here: a refusal on the crux query with an unindexed column named in
 * <ViewFields> could be about the projection rather than about the grouping, and
 * this probe exists to read exactly that verdict. So every grouped query names
 * FileLeafRef and the grouped column, and nothing else.
 *
 * WHY THERE IS NO INDEX-BUILD WAIT. #480 and #481 both had to wait, because both
 * wrote the index in the same run that measured it and SharePoint builds the
 * index behind the flag. This probe writes nothing: PChoice's index was written
 * during the fixture build, which takes about six pastes, so it has had at least
 * the remainder of that build to finish and in practice much longer. The
 * bounded re-send below is not a build wait. It is there so the crux is not a
 * single sample, and so each attempt can pair the group-by with the filter.
 *
 * WHY THE FILTER AND THE GROUP-BY ARE INTERLEAVED. A filter read at 09:00 and a
 * group-by read at 09:03 cannot say the index was live for one and not the
 * other. So each attempt sends the grouped query and then immediately the OData
 * filter on the same column, and each pair is recorded with the elapsed time it
 * was taken at. That is the shape #481 used to separate "the index has not
 * built" from "the index does not serve an aggregation".
 *
 * WHY OData FOR THE FILTER CONTROLS. From `library-index-threshold-probe.js`:
 * past the threshold an OData `$filter` no index can serve returns HTTP 500
 * SPQueryThrottledException while the same predicate in CAML returns HTTP 200
 * with a silently partial answer, so OData is the surface that reports the
 * threshold as an error. The grouped questions have to use the rendered view
 * surface, because a <GroupBy> has nowhere else to live, and that is why the
 * refusal discrimination is established separately on both surfaces.
 *
 * WHERE THE ENDPOINTS COME FROM. Every URL, element and attribute is one
 * Microsoft Learn documents, because a wrong spelling returns 404, isRefusal()
 * counts 404 as a refusal, and the probe would then print a claim about
 * SharePoint that was really a typo:
 *   Field read via `fields/getbyinternalnameortitle('<name>')`:
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
 *   The threshold, the index model, and the instruction to index before the
 *   list grows past the limit:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 * Whether the ordering of the index write changes what a group-by is given is
 * NOT taken from any of those. It is the thing being measured.
 *
 * SCOPE OF CLAIMS: one tenant, two libraries, one caller context, one moment.
 * The threshold is documented as an effective figure rather than a constant, and
 * the negative controls are what detect a fixture sitting too close to it.
 *
 * HOW TO RUN: the run plan, in order
 *   1. Open the site holding 'dbmlsp Probe PreIndex'. If it is not built, run
 *      library-large-list-preindex-fixture-probe.js until its rows read PASS.
 *      This probe will not build it and will not repair it.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED true. ALLOW_WRITES is NOT needed and is never consulted.
 *      Paste again. Expect about a minute, most of it the bounded re-send.
 *   4. Copy the whole RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing. Leave the fixture exactly as it is, indexed. An
 * operator who clears PChoice's index has destroyed the only thing that
 * distinguishes this library from the one #480 and #481 measured.
 *
 * STATUS: NOT YET RUN. Authored against the merged findings of #472, #478, #479,
 * #480 and #481. Nothing below has been observed on a live site, and the finding
 * lines are inherited or about method until it has.
 */
// finding: preindex-group-view-writes-nothing-at-all - this probe sends no
// MERGE, no field create and no item write. The index on PChoice was written
// below 5,000 files during the fixture build and cannot be re-created without
// rebuilding the library from empty, because writing it again at 5,100 files
// produces the post-hoc index #481 already measured.
// finding: preindex-group-view-indexed-true-alone-does-not-say-when - a later
// pass sees Indexed=true and nothing else, which is equally consistent with a
// flag written at 4,900 files and one written at 5,099. The fixture probe
// therefore stamps the observed count and an ISO timestamp into PChoice's
// Description in the same pass as the index, and this probe reads that stamp
// back and voids the crux without it. The stamp is the only evidence that this
// library differs from 'dbmlsp Probe LargeLib' in the way the probe claims.
// finding: preindex-group-view-a-group-by-is-never-refused-for-its-column -
// inherited from library-grouping-probe.js, first live run 2026-09-08: a
// <GroupBy> naming a column that does not exist returned HTTP 200 with flat
// rows. That is what makes "accepted" meaningless and the honoured/ignored pair
// the discriminator. A THROTTLE is a different refusal and carries the threshold
// signature in the body, which is why control-render-where-absent-refused exists.
// finding: preindex-group-view-absent-column-group-by-is-refused-here -
// measured 2026-09-08 on this library, twice, and on LargeLib: that same
// <GroupBy> returns HTTP 500 carrying Microsoft.SharePoint.Client.UnknownError
// and no threshold signature, while library-grouping, library-nesting and
// library-view-interaction each read HTTP 200 with flat rows on a library
// holding under ten files the same day. The request is identical, so the
// refusal belongs to the container. The row therefore reports what the absent
// column did rather than failing for not being ignored, and the grouped rows
// below read HONOURED off server-produced group markers rather than off a
// comparison with the flat query, so none of them rests on this one.
// finding: preindex-group-view-collapsed-rows-carry-no-file-name - inherited
// from library-grouping-probe.js, second live run 2026-09-08: a collapsed
// query's rows did not carry the FileLeafRef its ViewFields named. Nothing here
// reads a file name off a collapsed row, and a label count is read against the
// RowLimit, never as a distinct-value count.
// finding: preindex-group-view-narrowed-grouping-is-the-only-instrument - #480,
// run 2026-09-08: an Id-guarded <Where> (Id >= newest-5, six rows) with a
// group-by is SERVED where every grouped query at full size in that run was not.
// A narrowed row set is the only place a grouping can be watched working past
// the threshold, and it is re-proved on THIS library rather than cited from that
// one, because the column names and the build differ.
// finding: preindex-group-view-one-moment-is-what-the-comparison-needs -
// inherited from #481, run 2026-09-08: at every timestamp from 646 ms to
// 176,814 ms the filter on the indexed column was SERVED while the group-by on
// it was REFUSED, in the same pair of requests. Readings taken minutes apart
// could not have said that. The same pairing is used here.
// finding: preindex-group-view-post-hoc-index-does-not-lift-a-group-by -
// measured by #481 on 2026-09-08 and the reason this probe exists: on a Choice
// column indexed while the library was already past 5,000 files, a single-level
// <GroupBy> was re-sent for 176,814 ms across 12 attempts and came back REFUSED
// (threshold) every time. This probe asks the same question of a column indexed
// before the crossing, and nothing else about the query changes.
// finding: preindex-group-view-one-level-only-because-three-is-rejected -
// #481, run 2026-09-08: a three-FieldRef <GroupBy> returned HTTP 500 with code
// -2147467259 and NO SPQueryThrottledException, over three field orders and over
// an Id-narrowed six-row set alike. The query engine rejects that shape before
// the threshold applies, so a multi-level grouping would answer a different
// question here and this probe sends one level only.
// finding: preindex-group-view-viewfields-name-only-the-measured-column - a
// grouped query that also projects an unindexed column could be refused for the
// projection rather than for the grouping, and the two are indistinguishable in
// the body. Every grouped query here names FileLeafRef and the grouped column
// and nothing else, which is a departure from #480 and #481 and is deliberate:
// those runs read every answer as a refusal, and this one may not.
// finding: preindex-group-view-no-index-build-wait-is-needed - #480 and #481 had
// to wait because both wrote the index in the run that measured it. This probe
// writes nothing and the index is as old as the fixture build, so the bounded
// re-send below is a second sample and an interleave, not a build wait, and it
// is reported as elapsed time rather than as a settling period.
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

  log('INFO', 'probe revision 329bb72b. Quote this when reporting results.');

  // ---- The fixture contract, restated ----------------------------------
  // Owned by library-large-list-preindex-fixture-probe.js. Read, never built,
  // never written to, never cleared. Changing any of these reads a different
  // library rather than adjusting this one.
  const LIB = 'dbmlsp Probe PreIndex';
  const CHOICE = 'PChoice';
  const NUMBER = 'PNumber';
  // Each column beside the type the fixture created it as. Read back, so a
  // library of the right name holding different columns is caught here rather
  // than reported as a platform finding.
  const COLUMN_TYPES = [
    [CHOICE, 'Choice'],
    [NUMBER, 'Number'],
  ];
  const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
  const CHOICE_MATCH = CHOICES[0];
  const NUMBER_MATCH = 7;
  // The count the fixture builds to, and the count below which its index was
  // written. Both are the fixture's contract and are reported against what is
  // read rather than assumed.
  const TARGET_FILES = 5100;
  const THRESHOLD = 5000;
  const FILE_NUMBER = /dbmlsp-pre-(\d+)\.txt$/;
  // The stamp the fixture's indexing pass left on PChoice's Description, and the
  // pattern it is read back with. See the stamp finding: Indexed=true on its own
  // cannot say WHEN, and when is the whole subject.
  const STAMP_RE = /dbmlsp preindex: Indexed:true written at (\d+) file\(s\) on (\S+)/;

  // More than the documented 5,000, so every query below is asked past it.
  const FLOOR = 5001;
  // Well below any page ceiling, so a query that fills the page is visibly
  // uncounted rather than quietly rounded.
  const PAGE = 100;
  // The same figure for a rendered view, and for the same reason.
  const ROW_LIMIT = 100;
  // The two strings a throttled query comes back with, and each on its own.
  // THROTTLE classifies a response; the two halves answer the signature question,
  // which is about which of them a refusal actually carried.
  const THROTTLE_EXCEPTION = /SPQueryThrottledException/;
  const THRESHOLD_PROSE = /exceeds the list view threshold/i;
  const THROTTLE = /exceeds the list view threshold|SPQueryThrottledException/i;
  // A column name the library does not hold, for the negative controls.
  const ABSENT_COLUMN = 'PNoSuchColumnAtAll';
  // The keys an honoured group-by carries, named rather than matched on the
  // column name: a /group/i test over a label key would report a grouping that
  // is only a coincidence of spelling.
  const GROUP_MARKER = /\.COUNT\.group$|\.newgroup$|\.groupindex$/;
  // How far back from the newest item id the narrowed control's <Where> reaches.
  // Small enough that the grouping runs over a handful of rows, and the row
  // count is READ rather than predicted: item ids need not be contiguous.
  const GUARD_SPAN = 5;
  // Both documented spellings for a counter value, tried in turn: a
  // <Value Type=...> spelled wrongly comes back as a rejected request, which is
  // the same shape as the refusal that would be the finding.
  const ID_VALUE_TYPES = ['Counter', 'Integer'];
  // The bounded re-send. NOT a build wait; see the no-build-wait finding. Four
  // attempts ten seconds apart is about thirty seconds, enough that the crux is
  // not a single sample and that the interleave has several pairs in it.
  const PAIR_ATTEMPTS = 4;
  const PAIR_WAIT_MS = 10000;

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
    log('INFO', `two columns ${CHOICE} and ${NUMBER}, their Indexed flags and the index`);
    log('INFO', `stamp on ${CHOICE}'s Description. It builds NOTHING and REPAIRS NOTHING.`);
    log('INFO', `It would then send selective OData filters reading at most ${PAGE} rows`);
    log('INFO', `each, and rendered view reads of at most ${ROW_LIMIT} rows: flat, grouped`);
    log('INFO', 'on one column, and grouped over an Id-narrowed row set.');
    log('INFO', 'IT WRITES NOTHING. No MERGE, no field, no item, no file, no folder, no');
    log('INFO', 'list. ALLOW_WRITES is never consulted and CLEANUP does nothing here.');
    log('INFO', `In particular it does NOT clear the index on ${CHOICE}: that flag was`);
    log('INFO', `written below ${THRESHOLD} files and cannot be put back without`);
    log('INFO', 'rebuilding the library from empty.');
    log('INFO', `Expect about a minute, most of it ${PAIR_ATTEMPTS} paired readings`);
    log('INFO', `${PAIR_WAIT_MS} ms apart.`);
    log('INFO', "It does NOT touch 'dbmlsp Probe LargeLib'. That is a different library");
    log('INFO', 'with different column names, measured by #478 through #481.');
    log('INFO', 'Nothing has been read. Set CONFIRMED to true.');
    return;
  }
  if (CLEANUP) {
    log('INFO', 'CLEANUP is on and is IGNORED here: it would recycle a permanent fixture');
    log('INFO', 'that takes six pastes to build and whose index cannot be rebuilt at all.');
  }

  expect('library.large-list.fixture-preindex-library-present', `The fixture library '${LIB}' is present, holds more than 5,000 files and carries both contract columns`);
  expect('library.large-list.fixture-preindex-index-written-under-threshold', `${CHOICE} reads Indexed=true and its Description carries the stamp saying the flag was written below ${THRESHOLD} files`);
  expect('library.large-list.fixture-preindex-witness-unindexed', `${NUMBER} reads Indexed=false, so this run has an unindexed column to witness the throttle with`);
  expect('library.large-list.control-id-query-served', 'POSITIVE CONTROL: a selective filter on Id is served past the threshold');
  expect('library.large-list.control-absent-column-refused', 'NEGATIVE CONTROL: a filter naming a column the library does not hold is refused WITHOUT the throttle signature');
  expect('library.large-list.control-unindexed-filter-refused', 'NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature');
  expect('library.large-list.control-render-where-absent-refused', 'NEGATIVE CONTROL: a rendered query whose <Where> names a column the library does not hold is refused WITHOUT the throttle signature');
  expect('library.large-list.control-missing-group-column-ungrouped', 'Is a group-by naming a column the library does not hold ignored or refused past 5,000 items');
  expect('library.large-list.control-preindex-filter-serves', `POSITIVE CONTROL: the filter on the pre-indexed ${CHOICE} is served, so the index is live`);
  expect('library.large-list.control-preindex-group-by-narrowed-honoured', `POSITIVE CONTROL: a <GroupBy> on ${CHOICE} is honoured once a <Where> on Id has narrowed the rows to a handful`);
  expect('library.large-list.preindex-group-by-indexed-column', `Is a group-by on ${CHOICE}, indexed before the library crossed 5,000 files, honoured, ignored or refused at this size`);
  expect('library.large-list.preindex-filter-serves-while-group-by-refused', `At one moment, is the filter on the pre-indexed ${CHOICE} served while the group-by on it is refused`);
  expect('library.large-list.preindex-group-by-unindexed-column', `Is a group-by on the unindexed ${NUMBER} honoured, ignored or refused on this library at this size`);
  expect('library.large-list.group-by-native-index-column', 'Is a group-by on Id, the one natively indexed column, served past 5,000 items');
  expect('library.large-list.preindex-group-by-refusal-signature', 'Does every grouped refusal carry SPQueryThrottledException, or does one carry something else');

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

  // Every refusal a grouped query in this run came back with, kept whole so the
  // signature question is answered from the bodies rather than from a verdict
  // string.
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

  // `expected` is the row count the fixture's own formulas give this filter.
  // null means the count is not being compared, which is the case for a filter
  // whose match set is bigger than the page.
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

  // ---- Reading a rendered view -----------------------------------------
  const rowsOf = (res) => {
    if (readFailed(res)) return [];
    if (Array.isArray(res.body.Row)) return res.body.Row;
    if (res.body.ListData && Array.isArray(res.body.ListData.Row)) return res.body.ListData.Row;
    return [];
  };

  const groupFields = (opts) => {
    if (opts.groupBy === undefined || opts.groupBy === null) return [];
    return Array.isArray(opts.groupBy) ? opts.groupBy : [opts.groupBy];
  };

  // One ViewXml. Every part is optional and every part is named by the caller,
  // because the whole subject here is which combination was sent. `<Query>`
  // children go Where then GroupBy, the order the syntax block in "Query element
  // (List)" gives them. The DEFAULT ViewFields names FileLeafRef and the grouped
  // column alone; see the viewfields finding. The absent-column controls pass
  // their own `fields`, so a column that does not exist is named ONLY in the
  // clause under measurement and never in <ViewFields>, where a refusal would be
  // about the wrong clause: the rule library-grouping-probe.js set for the same
  // control.
  const viewXmlFor = (opts) => {
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
    const fields = uniq(opts.fields || ['FileLeafRef'].concat(grouped));
    return `<View><Query>${where}${grouping}</Query><ViewFields>`
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

  const markersIn = (rows) => {
    const seen = [];
    for (const row of rows) {
      for (const key of Object.keys(row)) {
        if (GROUP_MARKER.test(key) && !seen.includes(key)) seen.push(key);
      }
    }
    return seen;
  };

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
    const labels = labelsFor(collapsed.rows, grouped);
    const served = judgeView(collapsed);
    // An honoured grouping is read off the markers AND off a non-empty expanded
    // row set: a collapsed answer carrying markers over no rows at all would be
    // an honoured grouping of nothing, which is not what the question asks.
    const verdict = !served.startsWith('SERVED') ? served
      : markers.length
        ? (expanded.res.ok && expanded.rows.length
          ? 'HONOURED'
          : 'HONOURED (collapsed only; the expanded query returned no rows)')
        : (flat.res.ok && collapsed.rows.length === flat.rows.length) ? 'IGNORED'
          : 'NOT ESTABLISHED (no group markers, and the flat baseline did not answer)';
    return {
      collapsed, expanded, flat, markers, labels, verdict, grouped,
      text: `collapsed HTTP ${collapsed.res.status} returned ${collapsed.rows.length} row(s) `
        + `against a RowLimit of ${ROW_LIMIT}, labels ${clip(show(labels), 300)}, grouping `
        + `markers ${clip(show(markers), 240)}, first row `
        + `${clip(show(collapsed.rows.length ? collapsed.rows[0] : null), 300)}; expanded HTTP `
        + `${expanded.res.status} returned ${expanded.rows.length} row(s); the same query with no `
        + `<GroupBy> returned HTTP ${flat.res.status} with ${flat.rows.length} row(s); ViewXml `
        + `${clip(collapsed.xml, 320)}`
        + (collapsed.res.ok ? '' : `; collapsed body ${clip(collapsed.res.text, 220)}`),
    };
  };

  // The bounded re-send, with the OData query on the SAME column sent
  // immediately after each grouped attempt. That pairing is what makes the
  // one-moment row answerable. `ask` may be null, for a reading with nothing to
  // interleave.
  const pairedReadings = async (opts, ask) => {
    const started = Date.now();
    const legs = [];
    let attempts = 0;
    let last = null;
    let lastAsked = null;
    while (attempts < PAIR_ATTEMPTS) {
      if (attempts) await sleep(PAIR_WAIT_MS);
      last = await observeGroup(opts);
      lastAsked = ask === null ? null : await ask();
      attempts += 1;
      legs.push({
        atMs: Date.now() - started,
        group: last.verdict,
        asked: lastAsked === null ? null : judge(lastAsked, null),
      });
      log('INFO', `  attempt ${attempts}/${PAIR_ATTEMPTS} at ${Date.now() - started} ms: `
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

  // ---- fixture-preindex-library-present --------------------------------
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
  record('library.large-list.fixture-preindex-library-present',
         `The fixture library '${LIB}' is present, holds more than 5,000 files and carries both contract columns`,
         !libOk ? 'ABORTED' : count < FLOOR ? 'SHORT' : columnProblems.length ? 'FAIL' : 'PASS',
         (libOk
           ? `the newest file is ${show(newestRow ? newestRow.FileLeafRef : null)}, so the library `
             + `holds ${count} file(s) against the ${FLOOR} this probe needs and the `
             + `${TARGET_FILES} the fixture contract gives; ItemCount reads `
             + `${show(libRead.body.ItemCount)} and is not what the count is taken from`
           : `the library did not read back (HTTP ${libRead.status}): ${clip(show(libRead.body), 200)}`)
         + '. '
         + (columnProblems.length
           ? `column problems: ${columnProblems.join('; ')}`
           : libOk
             ? `both contract columns read back as their declared types, and their index flags are ${allFlags()}`
             : '')
         + (present
           ? '. This probe does not build the fixture, does not repair it and does not write to '
             + 'it. It is owned by library-large-list-preindex-fixture-probe.js.'
           : '. Run library-large-list-preindex-fixture-probe.js until its fixture rows read '
             + 'PASS, then re-paste this one.'));

  if (!present) {
    abortRemaining('ABORTED',
                   'the fixture was not readable as this probe needs it, so no query was sent');
    report();
    return;
  }

  // ---- fixture-preindex-index-written-under-threshold ------------------
  // Indexed=true and the stamp, together. Either alone is not the precondition:
  // the flag says an index exists and the stamp says when it was written, and
  // WHEN is the only thing separating this library from the one #481 measured.
  const stamp = STAMP_RE.exec(String(flags[CHOICE].description || ''));
  const stampedAt = stamp ? Number(stamp[1]) : null;
  const stampedOn = stamp ? stamp[2] : null;
  const choiceIndexed = flags[CHOICE].indexed === true;
  const preindexProved = choiceIndexed && stampedAt !== null && stampedAt < THRESHOLD;
  record('library.large-list.fixture-preindex-index-written-under-threshold',
         `${CHOICE} reads Indexed=true and its Description carries the stamp saying the flag was written below ${THRESHOLD} files`,
         preindexProved ? 'PASS'
           : !choiceIndexed ? 'FAIL'
             : stamp === null ? 'NOT ESTABLISHED' : 'FAIL',
         `${flagNote(CHOICE)}; its Description reads `
         + `${show(clip(flags[CHOICE].description, 200))}`
         + (stamp === null
           ? `, which does not match the fixture's stamp pattern ${String(STAMP_RE)}`
           : `, so the flag was written at ${stampedAt} file(s) on ${stampedOn}`)
         + '. '
         + (preindexProved
           ? `The index therefore predates the crossing of ${THRESHOLD} files by `
             + `${THRESHOLD - stampedAt} file(s), which is the one thing distinguishing this `
             + "library from 'dbmlsp Probe LargeLib' and the only reason the crux below is worth "
             + 'asking.'
           : !choiceIndexed
             ? 'Without the index there is no pre-indexed column to measure at all. Something '
               + 'has cleared it, and it cannot be put back: writing Indexed=true now would be a '
               + 'post-threshold index, which is what #481 already measured. The fixture has to '
               + 'be rebuilt from empty.'
             : stamp === null
               ? 'Indexed=true with no stamp is equally consistent with a flag written at 4,900 '
                 + 'files and one written at 5,099, so this run cannot say the index is a '
                 + 'pre-threshold one and the crux below is voided rather than answered.'
               : `The stamp names ${stampedAt} file(s), which is not below ${THRESHOLD}, so this `
                 + 'library is a second copy of the post-hoc case rather than the comparison it '
                 + 'was built to be.'));

  if (!choiceIndexed) {
    abortRemaining('ABORTED',
                   `${CHOICE} does not carry an index, so there is no pre-indexed column to `
                   + 'measure and no query below would mean anything');
    report();
    return;
  }

  // ---- fixture-preindex-witness-unindexed ------------------------------
  const witnessClear = flags[NUMBER].indexed === false;
  record('library.large-list.fixture-preindex-witness-unindexed',
         `${NUMBER} reads Indexed=false, so this run has an unindexed column to witness the throttle with`,
         witnessClear ? 'PASS' : 'FAIL',
         `${flagNote(NUMBER)}`
         + (witnessClear
           ? '. The throttle therefore has a witness on this library, which is what the negative '
             + 'controls below rest on.'
           : '. Without an unindexed column nothing on this library can show the threshold being '
             + 'enforced, so a served answer on the indexed column says nothing. #478 measured '
             + 'that SharePoint can index a column on its own, and threshold-index-probe.js '
             + 'watched it happen between two runs, so this is read rather than assumed.'));

  // The predicted row counts, from the fixture's formulas and the file count. A
  // served answer carrying a different number was answered from something other
  // than the fixture this probe thinks it is reading.
  const tally = (predicate) => {
    let total = 0;
    for (let n = 1; n <= count; n += 1) if (predicate(n)) total += 1;
    return total;
  };
  const numberExpected = tally((n) => n % 1000 === NUMBER_MATCH);
  // Bigger than the page on any fixture of this size, so its count is not
  // compared and a full page is reported as a full page.
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
             + 'surface, which is what every filter verdict below is read against.'
           : absent.throttled
             ? '. A filter on a column that does not exist came back carrying the throttle '
               + 'signature, so no refusal below can be attributed to the threshold.'
             : '. The server did not refuse a filter on a column that does not exist, so a '
               + 'refusal below cannot be read as the server rejecting the query either.'));

  // ---- control-unindexed-filter-refused --------------------------------
  // PNumber is the witness, and it is the only candidate: this fixture carries
  // two columns and the other one is the subject.
  const witnessSeen = witnessClear ? await askFilter(numberFilter) : null;
  const witnessOutcome = witnessSeen === null ? null : judge(witnessSeen, numberExpected);
  const throttleEnforced = witnessOutcome !== null
    && witnessOutcome.startsWith('REFUSED (threshold)') && absentRefused;
  record('library.large-list.control-unindexed-filter-refused',
         'NEGATIVE CONTROL: a selective filter on an unindexed contract column is refused WITH the throttle signature',
         witnessSeen === null ? 'NOT ESTABLISHED'
           : throttleEnforced ? 'REFUSED (threshold)' : 'CONTROL FAILED, METHOD VOID',
         witnessSeen === null
           ? `${NUMBER} did not read Indexed=false, so this fixture has no unindexed column left `
             + `to witness a throttle with: flags were ${allFlags()}`
           : `${witnessSeen.label} on ${count} file(s), matching ${numberExpected} of them: HTTP `
             + `${witnessSeen.status}, ${witnessOutcome}. ${flagNote(NUMBER)}: `
             + `${witnessSeen.body}`
             + (throttleEnforced
               ? '. The library is therefore past the threshold and throttling is enforced on it, '
                 + 'so a refusal below is the threshold and an answer served below is worth '
                 + 'something.'
               : '. Without a refusal here nothing below is evidence of the threshold: the '
                 + 'library may simply not be far enough past it for this tenant to enforce it, '
                 + 'and a served group-by would then be a small library answering rather than a '
                 + 'pre-threshold index working.'));

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
                                           fields: ['FileLeafRef', CHOICE],
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

  // ---- control-preindex-filter-serves ----------------------------------
  // The reading that says the index is live. It is a single reading rather than
  // a wait, because nothing in this run wrote the flag: see the no-build-wait
  // finding.
  const choiceFilterSeen = await askFilter(choiceFilter);
  const choiceFilterOutcome = judge(choiceFilterSeen, null);
  const choiceFilterServes = choiceFilterOutcome.startsWith('SERVED');
  record('library.large-list.control-preindex-filter-serves',
         `POSITIVE CONTROL: the filter on the pre-indexed ${CHOICE} is served, so the index is live`,
         choiceFilterServes ? 'SERVED' : 'CONTROL FAILED, METHOD VOID',
         `${choiceFilterSeen.label} on ${count} file(s), matching ${choiceExpected} of them, which `
         + `is more than the ${PAGE}-row page this asks for: HTTP ${choiceFilterSeen.status}, `
         + `${choiceFilterOutcome}. ${flagNote(CHOICE)}, stamped at `
         + `${show(stampedAt)} file(s)`
         + (choiceFilterServes
           ? '. The index is therefore live and doing what #478 measured an index doing, so a '
             + 'group-by refused below is refused with a working index behind it rather than with '
             + 'an index that has not built. Nothing was waited for: this run did not write the '
             + 'flag.'
           : `: ${choiceFilterSeen.body}. An index that does not serve its own filter cannot be `
             + 'asked whether it serves an aggregation, so every reading below is voided rather '
             + 'than answered. Read this row against the unindexed witness above: if both are '
             + 'refused, the flag is set on a column whose index is gone.'));

  // ---- control-preindex-group-by-narrowed-honoured ---------------------
  // The grouping instrument, proved where the threshold cannot reach it. The Id
  // value type is tried rather than assumed: a wrong spelling comes back as a
  // rejected request, the same shape as the refusal that would be the finding.
  const minId = newestId - GUARD_SPAN;
  const idTypeAttempts = [];
  let idType = null;
  for (const type of ID_VALUE_TYPES) {
    const seen = await askView({ minId, idType: type, fields: ['FileLeafRef', CHOICE] });
    idTypeAttempts.push(`Type="${type}": HTTP ${seen.res.status}, ${judgeView(seen)}`
      + (seen.res.ok ? '' : ` ${clip(seen.res.text, 160)}`));
    if (seen.res.ok || seen.throttled) {
      idType = type;
      break;
    }
  }

  const narrowedVoid = !idServed
    ? 'the positive control on Id was not served, so an Id clause cannot narrow anything on this '
      + 'run and a narrowed grouping measures nothing'
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
    record('library.large-list.control-preindex-group-by-narrowed-honoured',
           `POSITIVE CONTROL: a <GroupBy> on ${CHOICE} is honoured once a <Where> on Id has narrowed the rows to a handful`,
           'CONTROL FAILED, METHOD VOID', narrowedVoid, 'void');
  } else {
    narrowed = await observeGroup({
      minId, idType, groupBy: CHOICE,
      fields: ['FileLeafRef', CHOICE],
      label: `group-by on ${CHOICE} over an Id-narrowed row set`,
    });
    narrowedHeld = narrowed.verdict.startsWith('HONOURED');
    record('library.large-list.control-preindex-group-by-narrowed-honoured',
           `POSITIVE CONTROL: a <GroupBy> on ${CHOICE} is honoured once a <Where> on Id has narrowed the rows to a handful`,
           narrowedHeld ? 'HONOURED' : 'CONTROL FAILED, METHOD VOID',
           `<Where><Geq> on ID at ${minId} (the newest item id ${newestId} less ${GUARD_SPAN}), `
           + `grouping on ${CHOICE}. The counter spelling was tried rather than assumed: `
           + `${idTypeAttempts.join('; ')}, so Type="${idType}" is what answered. ${narrowed.text}`
           + (narrowedHeld
             ? '. A <GroupBy> on this column is therefore a request this server accepts and acts '
               + 'on, so a refusal of the same shape at full size below is about the size. #480 '
               + 'measured the same composition honoured on the other fixture; it is re-proved '
               + 'here because the column names and the build differ.'
             : '. The grouping was not honoured even over a handful of rows, so a refusal of the '
               + 'same shape at full size cannot be attributed to the threshold: it may be the '
               + 'request. Read the collapsed body above before reading anything below it.'));
  }

  // ---- preindex-group-by-indexed-column: THE CRUX ----------------------
  // Every reason this reading could not be attributed, in the order a reader
  // would want them. The first one that applies is the reason the row is void.
  const cruxVoid = !throttleEnforced
    ? 'the unindexed witness was not refused with the threshold signature, so this library is not '
      + 'demonstrably enforcing the threshold and neither a served nor a refused group-by here '
      + 'could be attributed to it'
    : !choiceFilterServes
      ? `the filter on ${CHOICE} was not served, so the index behind the group-by is not `
        + 'demonstrably live and a refusal here would say nothing about aggregation'
      : !narrowedHeld
        ? 'the narrowed control did not hold, so a refusal here cannot be told from the server '
          + 'rejecting the request'
        : !preindexProved
          ? `${CHOICE} carries an index, but this run could not read a stamp placing the write `
            + `below ${THRESHOLD} files, so a reading here cannot be distinguished from the `
            + 'post-hoc case #481 already measured'
          : null;

  log('INFO', `Sending the group-by on the pre-indexed ${CHOICE} up to ${PAIR_ATTEMPTS} time(s) `
    + `${PAIR_WAIT_MS} ms apart, with ${choiceFilter} immediately after each one.`);
  const crux = await pairedReadings({ groupBy: CHOICE,
                                      fields: ['FileLeafRef', CHOICE],
                                      label: `group-by on the pre-indexed ${CHOICE}` },
                                    () => askFilter(choiceFilter));
  const cruxSeen = crux.seen;
  record('library.large-list.preindex-group-by-indexed-column',
         `Is a group-by on ${CHOICE}, indexed before the library crossed 5,000 files, honoured, ignored or refused at this size`,
         cruxVoid === null ? cruxSeen.verdict : 'VOID',
         (cruxVoid === null ? '' : `${cruxVoid}. What was observed anyway: `)
         + `${flagNote(CHOICE)}, stamped at ${show(stampedAt)} file(s) on ${show(stampedOn)}, over `
         + `${count} file(s) and the four values ${show(CHOICES)}. The grouped query was sent `
         + `${crux.attempts} time(s) over ${crux.waitedMs} ms: ${legNote(crux.legs)}. Last `
         + `reading: ${cruxSeen.text}`
         + (cruxVoid !== null
           ? ''
           : cruxSeen.verdict.startsWith('HONOURED')
             ? `. #481 measured this same query REFUSED (threshold) for 176814 ms on a Choice `
               + 'column indexed AFTER its library passed 5,000 files. Here it is honoured, and '
               + 'the one thing that differs is when the index was written, so the guidance about '
               + 'indexing before the crossing reaches aggregation and not only filtering. One '
               + 'run on one pair of libraries cannot rule out every other difference between '
               + 'them, so this wants a second run before it is read as a rule.'
             : cruxSeen.verdict.startsWith('REFUSED')
               ? '. #481 measured this same query refused on a column indexed AFTER the crossing. '
                 + 'It is refused here too, on a column indexed before it, so the ordering does '
                 + 'not change what an aggregation is given and the guidance about indexing '
                 + 'before 5,000 items is about the filter rather than about the group-by. Two '
                 + 'independently built fixtures now say the same thing.'
               : '. Neither honoured nor refused, so read the collapsed body and the flat '
                 + 'baseline above before reading this beside #481.'),
         cruxVoid === null ? undefined : 'void');

  // ---- preindex-filter-serves-while-group-by-refused -------------------
  const bothLeg = crux.legs.find(
    (leg) => leg.asked !== null && leg.asked.startsWith('SERVED')
      && leg.group.startsWith('REFUSED (threshold)'));
  const servedLeg = crux.legs.find(
    (leg) => leg.asked !== null && leg.asked.startsWith('SERVED')
      && leg.group.startsWith('HONOURED'));
  const anyFilterServed = crux.legs.some(
    (leg) => leg.asked !== null && leg.asked.startsWith('SERVED'));
  const momentVoid = !throttleEnforced
    ? 'the unindexed witness was not refused with the threshold signature, so a refusal in either '
      + 'half of a pair cannot be attributed to the threshold'
    : !preindexProved
      ? `this run could not read a stamp placing ${CHOICE}'s index below ${THRESHOLD} files, so a `
        + 'pair observed here is not distinguishable from the post-hoc pairs #481 recorded'
      : null;
  record('library.large-list.preindex-filter-serves-while-group-by-refused',
         `At one moment, is the filter on the pre-indexed ${CHOICE} served while the group-by on it is refused`,
         momentVoid !== null ? 'VOID'
           : bothLeg !== undefined
             ? 'THE FILTER SERVES WHILE THE GROUP-BY IS REFUSED'
             : servedLeg !== undefined
               ? 'BOTH SERVED'
               : anyFilterServed
                 ? 'NOT ESTABLISHED (the filter served, but the grouped query was never refused with the threshold signature)'
                 : 'NOT ESTABLISHED (the filter never served, so there was nothing to interleave)',
         (momentVoid === null ? '' : `${momentVoid}. What was observed anyway: `)
         + `each attempt sent the grouped query and then ${choiceFilter} immediately after it, on `
         + `the same column, whose index was written at ${show(stampedAt)} file(s): `
         + `${legNote(crux.legs)}`
         + (momentVoid !== null
           ? ''
           : bothLeg !== undefined
             ? `. At ${bothLeg.atMs} ms a pre-threshold index answered a filter and refused an `
               + 'aggregation in the same pair of requests. That is exactly what #481 recorded on '
               + 'a post-threshold index, so the two orderings behave the same way and the '
               + 'difference between them is not what an aggregation is given.'
             : servedLeg !== undefined
               ? '. Both were served in the same pair, so this index serves an aggregation as '
                 + 'well as a filter, which no post-hoc index in #480 or #481 did.'
               : '. Without one pair in which the filter answered and the grouped query was '
                 + 'refused with the threshold signature, nothing here says the index was live '
                 + 'for one and not the other.'),
         momentVoid === null ? undefined : 'void');

  // ---- preindex-group-by-unindexed-column ------------------------------
  // A subject, not a control: #479, #480 and #481 all measured this refused, so
  // a refusal is the expected result and nothing declares a dependency on it.
  const unindexedGroup = await observeGroup({
    groupBy: NUMBER,
    fields: ['FileLeafRef', NUMBER],
    label: `group-by on the unindexed ${NUMBER}`,
  });
  record('library.large-list.preindex-group-by-unindexed-column',
         `Is a group-by on the unindexed ${NUMBER} honoured, ignored or refused on this library at this size`,
         narrowedHeld ? unindexedGroup.verdict : 'VOID',
         (narrowedHeld
           ? ''
           : 'the narrowed control did not hold, so a refusal here cannot be told from the server '
             + 'rejecting the request. What was observed anyway: ')
         + `with ${flagNote(NUMBER)} over ${count} file(s), where ${NUMBER} holds the file number `
         + `modulo 1000 and therefore about 1000 distinct values: ${unindexedGroup.text}`
         + (!narrowedHeld
           ? ''
           : unindexedGroup.verdict.startsWith('REFUSED')
             ? '. The throttle is in force on the grouped surface of this library, which is what '
               + 'makes the crux row above a comparison rather than a reading of a library that '
               + 'is not enforcing anything.'
             : '. A group-by on an UNINDEXED column was not refused at this size, which contradicts '
               + '#479, #480 and #481 by the same method. Read the crux row above against this '
               + 'one: if both are served, this library is not enforcing the threshold on the '
               + 'grouped surface at all and the index is not what answered.'),
         narrowedHeld ? undefined : 'void');

  // ---- group-by-native-index-column ------------------------------------
  // #480's id, asked of the second library. Id carries the one native index, so
  // it is the strongest case a group-by has that does not depend on any write.
  const idGroup = await observeGroup({
    groupBy: 'ID',
    fields: ['FileLeafRef', CHOICE],
    label: 'group-by on Id',
  });
  record('library.large-list.group-by-native-index-column',
         'Is a group-by on Id, the one natively indexed column, served past 5,000 items',
         narrowedHeld ? idGroup.verdict : 'VOID',
         (narrowedHeld
           ? ''
           : 'the narrowed control did not hold, so a refusal here cannot be told from the server '
             + 'rejecting the request. What was observed anyway: ')
         + `Id is natively indexed on every list and library (library-index-threshold-probe.js, `
         + `2026-09-08), and no write in this run touched it: ${idGroup.text}`
         + (!narrowedHeld
           ? ''
           : idGroup.verdict.startsWith('REFUSED')
             ? '. #480 measured the same refusal on the other fixture. A native index does not '
               + 'lift a group-by either, on either library, which is the reading the crux row '
               + 'above sits beside.'
             : '. #480 measured this REFUSED on the other fixture, so a different answer here is '
               + 'a difference between the two libraries rather than a property of Id, and the '
               + 'transcripts have to be read together.'),
         narrowedHeld ? undefined : 'void');

  // ---- preindex-group-by-refusal-signature -----------------------------
  const refusalNote = REFUSALS.length === 0
    ? 'no grouped query in this run was refused at all'
    : REFUSALS.map((row) => `${row.label}: HTTP ${row.status}, SPQueryThrottledException `
      + `${row.exception ? 'PRESENT' : 'absent'}, threshold prose `
      + `${row.prose ? 'PRESENT' : 'absent'}: ${row.body}`).join('; ');
  const neither = REFUSALS.filter((row) => !row.exception && !row.prose);
  const proseOnly = REFUSALS.filter((row) => !row.exception && row.prose);
  record('library.large-list.preindex-group-by-refusal-signature',
         'Does every grouped refusal carry SPQueryThrottledException, or does one carry something else',
         REFUSALS.length === 0 ? 'NO REFUSAL TO CLASSIFY'
           : neither.length ? 'A REFUSAL CARRIES NEITHER THRESHOLD SIGNATURE'
             : proseOnly.length ? 'SOME REFUSALS NAME THE THRESHOLD WITHOUT NAMING THE EXCEPTION'
               : 'EVERY REFUSAL CARRIES SPQueryThrottledException',
         `${REFUSALS.length} refusal(s) collected across every grouped query this run sent. `
         + `${refusalNote}`
         + (REFUSALS.length === 0
           ? '. Every grouped query was answered, so there is no refusal to attribute and the rows '
             + 'above stand on their served readings. On this library that is itself the finding, '
             + 'because #479, #480 and #481 all collected refusals by the same method.'
           : neither.length
             ? '. At least one refusal named neither the exception nor the threshold, so it is a '
               + 'different finding from a throttle and the rows that rest on it have to be read '
               + 'against its body. #481 measured exactly that shape for a three-level <GroupBy>, '
               + 'HTTP 500 with code -2147467259, which is why this probe sends one level.'
             : proseOnly.length
               ? '. Every refusal named the threshold, but not all of them named the exception '
                 + 'type, so a reader matching on the class name alone would miss some of them.'
               : '. The refusals are the throttle by its own name, not an error that merely reads '
                 + 'like one.'));

  report();

  // ---- Teardown ---------------------------------------------------------
  // There is none, and that is the point. Nothing was written, so there is
  // nothing to put back, and the one thing an operator might be tempted to tidy
  // away is the thing the fixture exists for.
  log('OK', `Nothing was written. ${CHOICE} keeps the index the fixture build wrote below `
    + `${THRESHOLD} files, and ${NUMBER} keeps none. Leave both exactly as they are: the index `
    + 'cannot be re-created without rebuilding the library from empty.');
})();
