/**
 * dbml-sharepoint PROBE: CAN A LIST'S LOOKUP INTO A LIBRARY BE SET AT ALL?
 *
 * ONE QUESTION, asked through every write path a real user or script has:
 *   `cross-lookup-probe.js` (run of 2026-09-07) created a lookup on a generic
 *   list pointing at a document library, bound to `Title` and bound to
 *   `FileLeafRef` alike, and then found the item MERGE REFUSED when it tried
 *   to set the Title-bound one to a file's item id, HTTP 500 "Cannot complete
 *   this action." The Name-bound column was never written to, the form's own
 *   endpoint was never tried, the deploy's own create shape was never tried,
 *   and the file the write pointed at had no Title. So the refusal was
 *   measured for ONE column, ONE method and ONE file shape, and a family
 *   that shipped two such columns rested on the create alone.
 *
 * REVISION: 7ea273e8
 *
 * WHY: `analysis/checks/_naming.py` accepts `display_column: FileLeafRef` on a
 * document library because the create is measured. Whether a user can then
 * pick a file in the form, whether a seeded row can carry one, and whether
 * `$expand` projects `FileLeafRef` through the lookup, are what this probe
 * measures. Each row either lifts a hedge or turns it into a documented limit.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. Every row is about how a document library
 * diverges from a generic list as a lookup TARGET, so all of them file under
 * `library.lookup.*`. The library-creation id is reused from the other
 * library probes, because it asks the same question by the same method. The
 * two lookup creates take their own ids, because this probe creates them by
 * the deploy's route and `cross-lookup-probe.js` by `createfieldasxml`.
 *
 *   library.doc-lib.fixture-library-created
 *        Does a document library create at all (BaseTemplate 101)? The same
 *        question by the same method as the other library probes, so it
 *        keeps their id.
 *   library.lookup.fixture-write-containers-ready
 *        Do the three containers, the target row, the two source rows, the
 *        untitled file and the titled file all exist, and does the titled
 *        file read back with the Title this probe set on it?
 *   library.lookup.control-whole-item-read-before-lookups
 *        CONTROL: does `items(id)` with no `$select` answer on a source row
 *        BEFORE any lookup column exists on the list? The 2026-09-18 runs
 *        saw that read fail with a Title-bound value held, on a list that
 *        also carried an empty Name-bound column, so which of the two is the
 *        cause was not separable. The three whole-item rows separate it.
 *   library.lookup.whole-item-read-with-title-lookup-column
 *        The same read once the control and Title-bound lookups EXIST, with
 *        no value set.
 *   library.lookup.whole-item-read-with-name-lookup-column
 *        The same read once the Name-bound lookup exists too, still with no
 *        value set. Created LAST, after every Title-bound row, so no
 *        Title-bound measurement is taken with that column on the list.
 *   library.lookup.control-text-column-item-writes
 *        CONTROL for the two write controls below: do the bare MERGE and the
 *        deploy's typed POST set a plain Text column on this list? Both were
 *        refused on a lookup three times on 2026-09-18 while the form
 *        endpoint set it; this says whether item writes on this list work
 *        at all, or only writes carrying a lookup id.
 *   library.lookup.control-list-to-list-create-write-string-id
 *        The deploy's POST again with `<name>Id` spelled as the string "1"
 *        rather than the number 1, because the refusal on 2026-09-18 was
 *        "-1, System.FormatException: Input string was not in a correct
 *        format", which is what a parser says of a value it did not expect.
 *   library.lookup.control-list-to-list-merge-write
 *        POSITIVE CONTROL for the MERGE rows: does an item MERGE of
 *        `<name>Id` set a list-to-list lookup on this site and read back?
 *        Sent twice if needed: first the bare `odata=nometadata` body the
 *        2026-09-07 run sent, then the shape Learn's "Update list item"
 *        documents and `demo.js.j2` ships, `odata=verbose` with
 *        `__metadata.type` set to the list's `ListItemEntityTypeFullName`.
 *        Records which one took. If neither does, the MERGE rows are void.
 *   library.lookup.control-list-to-list-create-write
 *        POSITIVE CONTROL for the create rows: does an item POST carrying
 *        `<name>Id`, the one write the deploy makes to seed a list row,
 *        create a row whose list-to-list lookup reads back?
 *   library.lookup.control-list-to-list-form-write
 *        POSITIVE CONTROL for the form rows: does `ValidateUpdateListItem`,
 *        the endpoint the modern form saves through, set the same
 *        list-to-list lookup and read back? Also records WHICH spelling of
 *        the value the endpoint took, a bare id or `id;#label`, because
 *        Learn documents the method and not the lookup value format.
 *   library.lookup.list-to-library-title-addfield-created
 *        Fixture: the Title-bound lookup into the library is created and
 *        bound, by `fields/addfield` with `SP.FieldCreationInformation`,
 *        which is how the deploy creates every single-value lookup. The
 *        `createfieldasxml` route was BOUND on 2026-09-07 and 2026-09-18
 *        under `list-to-library-title-created`; a different method takes a
 *        different id.
 *   library.lookup.list-to-library-name-addfield-created
 *        The same for the FileLeafRef-bound lookup, the column the family
 *        ships.
 *   library.formula.calc-name-operand
 *        Does a Calculated column on the LIBRARY whose formula is `=[Name]`,
 *        or `=[FileLeafRef]`, create with the body the deploy sends for one
 *        and read back the file name for a file with no Title and for a
 *        file with one? The 2026-09-03 formula probe never used the name as
 *        an operand. Files under `library.formula` because it is a question
 *        about what a library formula can read, not about lookups.
 *   library.lookup.list-to-library-calc-name-addfield-created
 *        Is a lookup on the source list, bound to that calculated column,
 *        created by the deploy's route and read back bound?
 *   library.lookup.list-to-library-calc-name-form-write
 *        `ValidateUpdateListItem` setting it to the untitled file: the write
 *        a user makes when they pick a file whose label is its name.
 *   library.lookup.calc-name-bound-row-read-after-write
 *        The six reads of the row holding that value. The Name-bound value
 *        failed three of them; a calculated text value is what
 *        `analysis.checks._structure` already accepts as a display column.
 *   library.lookup.list-to-library-calc-name-create-write
 *        The deploy's seed POST with the calc-bound lookup set.
 *   library.lookup.list-to-library-calc-name-expand-projects
 *        Does `$select=<name>/XCalcName&$expand=<name>` answer with the file
 *        name? `is_expand_queryable` measured calculated-text accepted
 *        through a list-to-list lookup on 2026-09-10; this is the library.
 *   library.lookup.calc-name-bound-picker-labels-files
 *        The visible half: what does the picker for the calc-bound lookup
 *        OFFER, and how is each entry labelled? Needs a capture.
 *   library.lookup.list-to-library-name-merge-write
 *        MERGE the NAME-bound lookup to the untitled file's item id, in the
 *        shape the control found working.
 *   library.lookup.list-to-library-titled-file-merge-write
 *        MERGE the TITLE-bound lookup to a file that HAS a Title. The
 *        2026-09-07 target had none, so this separates "a Title-bound
 *        lookup cannot point at a file" from "it cannot point at a file
 *        whose Title is empty".
 *   library.lookup.list-to-library-name-create-write
 *        POST a new row with the NAME-bound lookup set, the deploy's list
 *        seed shape. This is the row that decides whether a seeded evidence
 *        row can carry a file.
 *   library.lookup.list-to-library-title-create-write
 *        The same for the TITLE-bound lookup and the titled file.
 *   library.lookup.list-to-library-title-form-write
 *        `ValidateUpdateListItem` on an EXISTING row setting the Title-bound
 *        lookup to the titled file.
 *   library.lookup.title-bound-row-read-after-write
 *        With that value held: does the row still read over REST, by
 *        `items(id)?$select=Id`, by `items(id)` whole, by the collection
 *        with and without the column selected, and by
 *        `RenderListDataAsStream` projecting the column? The deploy verifies
 *        every write by reading it back and the reporting pack reads the
 *        collection, so a value that makes its row unreadable is a value
 *        nothing shipped can carry.
 *   library.lookup.list-to-library-name-form-write
 *        The same write for the Name-bound lookup and the untitled file.
 *        This is the write a user makes when they pick a file in the form.
 *   library.lookup.name-bound-row-read-after-write
 *        The same five reads with the Name-bound value held. On 2026-09-18
 *        `items(id)` answered HTTP 500 with and without `$select` on two
 *        such rows; this row says which reads survive and what the error
 *        says.
 *   library.lookup.list-to-library-new-form-write
 *        `AddValidateUpdateItemUsingPath` on a NEW row with the Name-bound
 *        lookup set. This is what the new-item form sends.
 *   library.lookup.list-to-library-name-expand-projects
 *        Once any write to the Name-bound lookup has held: does
 *        `$select=<name>/FileLeafRef&$expand=<name>` answer, and with what?
 *        The reporting plan joins the library's query instead of asking
 *        this; a PROJECTS here lets it stop.
 *   library.lookup.name-bound-picker-labels-files
 *        The visible half: what does the picker for the Name-bound lookup
 *        OFFER, and how is each entry labelled? Needs a capture.
 *
 * READBACKS ARE REPORTED WITH THEIR STATUS. The 2026-09-18 run printed
 * "readback id undefined" for two accepted form writes and this probe called
 * them REFUSED; the value was never read because the `$select=<name>Id` GET
 * itself failed, which is a different observation. Every readback below
 * carries its HTTP status, and an accepted write whose readback fails is
 * recorded as exactly that, with a second read of the whole item to say
 * whether the key exists at all.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the three containers, the rows and the
 *   two files exist; the titled file carries the Title set on it; a
 *   list-to-list lookup is settable by MERGE, by POST and by the form
 *   endpoint; the two library-targeted lookups are created and read back
 *   bound.
 *   Observes (recorded, never asserted): whether each write to a
 *   library-targeted lookup is accepted, whether and how it reads back,
 *   which value spelling and which MERGE shape the site took, what `$expand`
 *   projects. NOTHING here asserts that a lookup into a library can be set.
 *   A run where every such write is refused is a successful run, and its
 *   answer retires two columns from a shipped family.
 *
 * THE FIXTURE IS ACYCLIC, for the reason `cross-lookup-probe.js` records:
 * SharePoint refuses to recycle a list another list's lookup points into.
 *
 *     source list --------> target list      (the three controls)
 *     source list --------> library          (the three columns under test)
 *
 * VERBOSE OData ON THE `__metadata` WRITES. A body carrying `__metadata` is
 * a verbose construct, and `odata=nometadata` REJECTS the type hint rather
 * than ignoring it. Every such call sets the verbose Content-Type.
 *
 * MICROSOFT LEARN CITATIONS. Every URL below is one Learn documents:
 *   List and library creation, item create ("Create list item"), item
 *   update by MERGE with `__metadata.type` set to the list's
 *   `ListItemEntityTypeFullName` ("Update list item"), and the
 *   `AddValidateUpdateItemUsingPath` request shape with `formValues`:
 *     "Working with lists and list items with REST"
 *   `ValidateUpdateListItem(formValues, bNewDocumentUpdate, checkInComment)`:
 *     "ListItem.ValidateUpdateListItem Method", Microsoft.SharePoint.Client.
 *     Addressed over REST by the method's own name under `items(id)`, as
 *     every `_api` method is. Learn gives no value format for a Lookup in
 *     `formValues`, which is why the control row tries two and records
 *     which one took.
 *   Field creation via `fields/addfield` with `SP.FieldCreationInformation`
 *   (`FieldTypeKind`, `LookupListId`, `LookupFieldName`):
 *     "Fields REST API reference", dn600182(v=office.15)
 *   File upload via `RootFolder/Files/add(url=,overwrite=)`:
 *     "Files and folders REST API reference", dn450841(v=office.15)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED, ALLOW_WRITES and CLEANUP to true, paste again.
 *   4. Copy the RESULTS block back verbatim, then open the new-item form the
 *      picker row names and record what the dropdown offers.
 *
 * WHEN FINISHED: delete the source list FIRST, then the library, then the
 * target list. A container a lookup points into cannot be removed.
 */
// finding: library-lookup-write-form-value-format-undocumented - Learn
// documents ValidateUpdateListItem's signature and AddValidateUpdateItemUsingPath's
// request shape, and neither says how a Lookup value is spelled in formValues.
// The control row sends a bare id first and `id;#label` second, and records
// which one the endpoint accepted. Measured 2026-09-18: the bare id took, on
// the first attempt, HTTP 200 with no exception, and read back.
// finding: library-lookup-write-bare-merge-fails-on-list-rows - the item MERGE
// the 2026-09-07 run sent, `odata=nometadata` with `{"<name>Id": n}` and no
// `__metadata.type`, was REFUSED on 2026-09-18 for a LIST-TO-LIST lookup on a
// generic list row, HTTP 500 "Cannot complete this action.", the same error
// the earlier run attributed to the library target. The same shape HELD on a
// library row in both runs. So that attribution is withdrawn: what was
// measured is that this MERGE shape fails on a generic list's row whatever the
// lookup points at, and the library-targeted MERGE rows of 2026-09-07 are
// void for want of a control. The deploy never sends that shape to a list: it
// POSTs a list row with its values in one verbose body carrying the entity
// type, and MERGEs only a library file's item. This revision sends the
// deploy's shapes and keeps the bare one as the first attempt of the control.
// finding: library-lookup-write-name-bound-picker-lists-every-file - observed
// by the operator on 2026-09-18 on the new-item form of the source list: the
// FileLeafRef-bound lookup's dropdown offered every file in the library,
// labelled by file name, including the file whose Title was empty; the
// Title-bound lookup's dropdown offered titles only; the list-to-list control
// offered its target row. The capture row stays awaiting-capture until the
// probes repo records it, but the observation is what the family standard's
// `[$FileLeafRef]` rule predicted and the deploy relies on.
// finding: library-lookup-write-title-bound-form-write-held - measured
// 2026-09-18, twice: ValidateUpdateListItem on an existing list row set a
// Title-bound lookup into a library to a file that had a Title, HTTP 200, no
// exception, and `$select=<name>Id` read the file's item id back.
// finding: library-lookup-write-name-bound-row-unreadable - measured
// 2026-09-18, revision 960aea15: after ValidateUpdateListItem accepted the
// FileLeafRef-bound lookup with a file's item id (HTTP 200, no exception), the
// row answered HTTP 500 to `items(id)?$select=<name>Id` AND to `items(id)`
// with no $select, on the existing row and on a row the new-item endpoint had
// just created, while the same row had read HTTP 200 moments earlier with the
// Title-bound value held. The error text was not captured; this revision
// captures it and asks which read shapes survive. Until that answers, a
// FileLeafRef-bound lookup is a column whose value the deploy cannot read
// back, and no family may seed one.
// finding: library-lookup-write-item-writes-refused-on-this-list - measured
// 2026-09-18 three times, the last (revision d466172a) on lookups created by
// the deploy's own fields/addfield route: the item MERGE was refused in the
// bare and in the typed verbose shape (HTTP 500 "Cannot complete this
// action.") and the deploy's seed POST carrying `<name>Id` was refused HTTP
// 500 "-1, System.FormatException: Input string was not in a correct
// format.", while ValidateUpdateListItem set the same column every time. The
// deploy seeds shipped families by that POST on other sites, so the creation
// route is ruled out and the list, the site or the value spelling remain.
// This revision adds a Text-column write control and a string-spelled id.
// finding: library-lookup-write-calculated-name-refused - measured
// 2026-09-18, revision 8027e148: `=[Name]` on the library answered HTTP 500
// "The formula refers to a column that does not exist", and the refused
// create still left a Calculated column behind with Formula `=""`. A lookup
// bound to that column wrote, read back through every shape and expanded,
// with a blank value, and the operator saw its picker offer nothing. So a
// calculated copy of the name cannot label a picker; the display name is
// what a formula resolves against, and the internal spelling
// `=[FileLeafRef]` is tried by this revision for completeness.
// finding: library-lookup-write-name-column-breaks-its-host-list - measured
// 2026-09-18, revision 8027e148, the first run to create the FileLeafRef-bound
// column LAST: with it present and no value set, `items(id)` with no $select
// answered HTTP 500 on a row that had answered with the Title-bound value
// held, and on the fresh list without it the deploy's seed POST and the bare
// item MERGE both HELD, list-to-list and Title-bound alike. The three earlier
// runs wrote with that column already on the list, so the refusals they
// recorded are attributed to its presence rather than to the site, with the
// caveat that those runs also reused their lists.
// finding: library-lookup-write-calculated-name-is-the-candidate - a
// FileLeafRef binding labels the picker by file name and then cannot be read
// back; a Title binding reads back and labels the picker by a value nobody
// fills on upload (`library.file-vs-item.title-after-upload`: TITLE IS EMPTY,
// 2026-09-03). A Calculated column `=[Name]` on the library, used as the
// display column, would give the first picker with the second value shape,
// and the tool already accepts a calculated display column behind
// accept_unindexable_display_column. Whether a library formula can read the
// name at all, and whether the lookup into it reads back, are the rows above.
// finding: library-lookup-write-name-bound-value-unreadable-and-misrendered -
// measured 2026-09-18, revision d466172a, lookup created by fields/addfield:
// with a FileLeafRef-bound value held, `items(id)?$select=<name>Id`, `items(id)`
// and `items?$select=Id,<name>Id` all answered HTTP 500 "Cannot complete this
// action.", `items(id)?$select=Id` and `items?$select=Id,Title` answered 200,
// and RenderListDataAsStream projected lookupValue "2_.000" for a file named
// dbmlsp-libwrite-plain.txt. The Title-bound value on the same row moments
// earlier read through every $select shape and rendered its title. So the
// binding is the variable, and analysis/checks/_naming.py now refuses it.
// The one Title-bound read that failed, `items(id)` with no $select, was
// taken with the empty Name-bound column already on the list; the three
// whole-item rows above attribute it.
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
    && status !== 408 && status !== 429 && status !== 503; // 503: the other documented throttle

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
  //
  // expectedId is OPTIONAL because most callers have no claimed Id to bracket
  // with, and the behaviour without one is unchanged. Supply one and every
  // request below addresses that list Id instead of the title, so a title
  // rebound mid-run cannot redirect the deletes or the recycle onto a list
  // this run never owned.
  //
  // DOCUMENTED: `web/lists(guid'<id>')` is the list resource, and `/items`
  // and `/items(<id>)` hang off it (Working with lists and list items with
  // REST, and the CSOM/REST API index, both checked 2026-09-23).
  // NOT DOCUMENTED: `/recycle` on the by-Id form appears on no Learn page.
  // It is the call this project has live evidence for with only the
  // addressing changed, and an unsupported URL fails visibly here rather
  // than losing somebody's list. One CLEANUP run settles it; see issue #611.
  const resetList = async (title, expectedId = null) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
      return false;
    }
    // An Id that is not a GUID would be spliced into a URL that addresses
    // something else, so it fails closed instead of being sent.
    const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (expectedId !== null && !GUID.test(String(expectedId))) {
      log('FAIL', `CLEANUP: '${expectedId}' is not a list Id, so nothing was deleted or `
                  + `recycled under '${title}'.`);
      return false;
    }
    const listPath = expectedId === null
      ? `web/lists/getbytitle('${title}')`
      : `web/lists(guid'${expectedId}')`;
    const found = await spGet(expectedId === null ? listPath : `${listPath}?$select=Id`);
    if (!found.ok) {
      log('INFO', `CLEANUP: no list named '${title}' to remove.`);
      return false;
    }
    // Addressing by Id still gets read back, because every destructive
    // request below rests on this one answer.
    const answeredId = found.body && found.body.Id
      ? String(found.body.Id).replace(/[{}]/g, '').toLowerCase() : null;
    if (expectedId !== null && answeredId !== String(expectedId).toLowerCase()) {
      log('FAIL', `CLEANUP: list ${expectedId} answered as ${answeredId}, so nothing was `
                  + `deleted or recycled under '${title}'.`);
      return false;
    }
    log('INFO', `CLEANUP: removing list '${title}' and its items.`);

    // Items first. Recycling the list takes them with it, but doing this
    // explicitly still clears the data if the list itself cannot be
    // removed. A locked or no-delete list would otherwise leave rows from
    // a previous run answering this run's questions.
    let digest = await getDigest();
    const items = await spGet(`${listPath}/items?$select=Id&$top=5000`);
    const rows = (items.ok && items.body && items.body.value) || [];
    for (const row of rows) {
      digest = await getDigest();
      await spPost(`${listPath}/items(${row.Id})`, {}, digest,
                   { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    }
    if (rows.length) log('INFO', `CLEANUP: deleted ${rows.length} item(s).`);
    if (rows.length === 5000) {
      log('INFO', 'CLEANUP: hit the 5000-row page limit; re-run to clear the rest.');
    }

    digest = await getDigest();
    const gone = await spPost(`${listPath}/recycle`, {}, digest);
    // The Id is named where there is one, because a repair by hand off the
    // title would go to whatever the title resolves to now.
    const which = expectedId === null ? `'${title}'` : `'${title}' (list ${expectedId})`;
    if (gone.ok) {
      log('OK', `CLEANUP: recycled list ${which}. It is restorable from the recycle bin.`);
    } else {
      log('FAIL', `CLEANUP: could not recycle ${which}: HTTP ${gone.status} ${gone.text.slice(0, 200)}`);
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

  // ---- Fixtures (#559) -----------------------------------------------
  // Why a response carries no reading, or null when it does. Learn documents
  // 429 and 503 as the two SharePoint Online throttle statuses.
  const unanswered = (r) => {
    if (r.ok) {
      return r.body !== null && typeof r.body === 'object'
        ? null : `answered HTTP ${r.status} with no payload`;
    }
    if (r.status === 429 || r.status === 503) return `was throttled (HTTP ${r.status})`;
    if (r.status === 408) return 'timed out (HTTP 408)';
    if (r.status === 401 || r.status === 403) return `was not authorised (HTTP ${r.status})`;
    return isRefusal(r.status) ? `was refused (HTTP ${r.status})` : `did not answer (HTTP ${r.status})`;
  };

  // A voided row keeps its question and is counted apart from open and answered.
  const voidDependents = (ids, reason) => {
    for (const id of ids) {
      const row = RESULTS.find((r) => r.id === id);
      record(id, row ? row.question : id, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // `read` resolves to a harness response ({ ok, status, body }). `declared`
  // maps each property the measurement depends on to a value or a predicate.
  // PASS needs every one read back; otherwise FAIL, void `dependents`, false.
  const establishFixture = async (id, read, declared, dependents) => {
    const row = RESULTS.find((r) => r.id === id);
    const question = row ? row.question : id;
    const problems = [];
    const seen = [];
    let got = null;
    let threw = false;
    try {
      got = await read();
    } catch (err) {
      threw = true;
      problems.push(`the read threw: ${err && err.message ? err.message : String(err)}`);
    }
    if (!threw) {
      const silent = got && typeof got === 'object' ? unanswered(got) : 'returned no response';
      if (silent) problems.push(`the read ${silent}`);
    }
    if (!problems.length) {
      for (const [name, want] of Object.entries(declared)) {
        if (!Object.prototype.hasOwnProperty.call(got.body, name) || got.body[name] === undefined) {
          problems.push(`${name} is absent from the payload`);
          continue;
        }
        const value = got.body[name];
        seen.push(`${name}=${JSON.stringify(value)}`);
        const held = typeof want === 'function' ? want(value) === true : value === want;
        if (!held) {
          problems.push(`${name} differs: read ${JSON.stringify(value)}, declared `
            + (typeof want === 'function' ? 'by a predicate it fails' : JSON.stringify(want)));
        }
      }
    }
    if (!problems.length) {
      record(id, question, 'PASS', `read back ${seen.join(', ')}`);
      return true;
    }
    record(id, question, 'FAIL', problems.join('; ') + (seen.length ? `; read ${seen.join(', ')}` : ''));
    voidDependents(dependents, `the fixture ${id} did not hold: ${problems.join('; ')}`);
    return false;
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

  log('INFO', 'probe revision 7ea273e8. Quote this when reporting results.');

  // Three containers, never two. See the acyclic note in the header.
  const LIB = 'dbmlsp Probe LibWrite Lib';
  const SRC = 'dbmlsp Probe LibWrite List';
  const TGT = 'dbmlsp Probe LibWrite Target';
  const FILE_PLAIN = 'dbmlsp-libwrite-plain.txt';
  const FILE_TITLED = 'dbmlsp-libwrite-titled.txt';
  const TITLED_TITLE = 'dbmlsp libwrite titled file';
  const SRC_ROWS = ['dbmlsp libwrite merge row', 'dbmlsp libwrite form row'];
  const TGT_ROW = 'dbmlsp libwrite target row';

  const CONTROL_LOOKUP = 'XWriteListToList';
  const LIB_TITLE_LOOKUP = 'XWriteLibTitle';
  const LIB_NAME_LOOKUP = 'XWriteLibName';
  const CALC_NAME = 'XCalcName';
  const LIB_CALC_LOOKUP = 'XWriteLibCalc';

  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  const libPath = `web/lists/getbytitle('${odataName(LIB)}')`;
  const srcPath = `web/lists/getbytitle('${odataName(SRC)}')`;
  const tgtPath = `web/lists/getbytitle('${odataName(TGT)}')`;
  const fieldPath = (container, name) =>
    `${container}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' and two generic lists,`);
    log('INFO', `'${SRC}' and '${TGT}', on ${WEB}.`);
    log('INFO', `Would upload two text files to '${LIB}' and set a Title on one of them,`);
    log('INFO', `seed one row in '${TGT}' and ${SRC_ROWS.length} rows in '${SRC}'.`);
    log('INFO', `Would create ${CONTROL_LOOKUP} on '${SRC}' pointing at '${TGT}' as the control,`);
    log('INFO', `and ${LIB_TITLE_LOOKUP}, ${LIB_CALC_LOOKUP} and ${LIB_NAME_LOOKUP} on '${SRC}' pointing at`);
    log('INFO', `the LIBRARY, the middle one at a Calculated column ${CALC_NAME} = [Name] created on it.`);
    log('INFO', 'Would then write to each lookup through the item MERGE, through an item');
    log('INFO', 'POST, through ValidateUpdateListItem on an existing row, and through');
    log('INFO', 'AddValidateUpdateItemUsingPath on a new row, reading each back.');
    log('INFO', 'Nothing outside these three lists is touched.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${SRC}', then '${LIB}', then '${TGT}' would be RECYCLED`);
      log('INFO', 'first, in that order, because a list a lookup points into cannot be removed.');
    } else {
      log('INFO', 'CLEANUP is off: existing lists would be reused, and a lookup column that');
      log('INFO', 'already exists answers nothing about creating one. Set CLEANUP = true.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  const QUESTIONS = {
    'library.doc-lib.fixture-library-created': 'A document library is created (BaseTemplate 101)',
    'library.lookup.fixture-write-containers-ready': 'The three containers, the rows, the two files and the titled file\'s Title all exist',
    'library.lookup.control-whole-item-read-before-lookups': 'CONTROL: does items(id) with no $select answer on a source row before any lookup column exists?',
    'library.lookup.whole-item-read-with-title-lookup-column': 'Does items(id) with no $select answer once the control and Title-bound lookup columns exist, with no value set?',
    'library.lookup.whole-item-read-with-name-lookup-column': 'Does items(id) with no $select answer once the Name-bound lookup column exists too, with no value set?',
    'library.lookup.control-text-column-item-writes': 'CONTROL: do the bare MERGE and the deploy\'s typed POST set a plain Text column on this list?',
    'library.lookup.control-list-to-list-create-write-string-id': 'Does the deploy\'s POST create a row whose list-to-list lookup reads back when <name>Id is sent as the string "1"?',
    'library.lookup.control-list-to-list-merge-write': 'POSITIVE CONTROL: an item MERGE of <name>Id sets a list-to-list lookup and reads back, and in which body shape',
    'library.lookup.control-list-to-list-create-write': 'POSITIVE CONTROL: an item POST carrying <name>Id, the deploy\'s seed shape, creates a row whose list-to-list lookup reads back',
    'library.lookup.control-list-to-list-form-write': 'POSITIVE CONTROL: ValidateUpdateListItem sets the same list-to-list lookup, and which value spelling it takes',
    'library.lookup.list-to-library-title-addfield-created': 'LIST -> LIBRARY: is a Lookup on a generic list, targeting a library Title, created and bound by fields/addfield, the deploy\'s route?',
    'library.lookup.list-to-library-name-addfield-created': 'Is the same addfield Lookup created against FileLeafRef, the Name column a library has and a list does not?',
    'library.formula.calc-name-operand': 'Does a Calculated column =[Name], or =[FileLeafRef], on the library create with the deploy\'s body and read back each file\'s name?',
    'library.lookup.list-to-library-calc-name-addfield-created': 'Is a lookup bound to that calculated column created by fields/addfield and read back bound?',
    'library.lookup.list-to-library-calc-name-form-write': 'Does ValidateUpdateListItem set the CALC-NAME-bound lookup on an existing row, and read back?',
    'library.lookup.calc-name-bound-row-read-after-write': 'With a CALC-NAME-bound value held, which REST reads of the row still answer?',
    'library.lookup.list-to-library-calc-name-create-write': 'Does the deploy\'s seed POST create a row with the CALC-NAME-bound lookup set, and read back?',
    'library.lookup.list-to-library-calc-name-expand-projects': 'Does $select=<name>/XCalcName&$expand=<name> answer through the CALC-NAME-bound lookup with the file name?',
    'library.lookup.calc-name-bound-picker-labels-files': 'What does the picker for the CALC-NAME-bound lookup offer, and how is each entry labelled?',
    'library.lookup.list-to-library-name-merge-write': 'Does an item MERGE set the NAME-bound lookup to a file\'s item id, and read back?',
    'library.lookup.list-to-library-titled-file-merge-write': 'Does an item MERGE set the TITLE-bound lookup to a file that HAS a Title, and read back?',
    'library.lookup.list-to-library-name-create-write': 'Does an item POST in the deploy\'s seed shape create a row with the NAME-bound lookup set, and read back?',
    'library.lookup.list-to-library-title-create-write': 'Does the same POST create a row with the TITLE-bound lookup set to a titled file, and read back?',
    'library.lookup.list-to-library-title-form-write': 'Does ValidateUpdateListItem set the TITLE-bound lookup on an existing row, and read back?',
    'library.lookup.title-bound-row-read-after-write': 'With a TITLE-bound value held, which REST reads of the row still answer?',
    'library.lookup.list-to-library-name-form-write': 'Does ValidateUpdateListItem set the NAME-bound lookup on an existing row, and read back?',
    'library.lookup.name-bound-row-read-after-write': 'With a NAME-bound value held, which REST reads of the row still answer, and what does a failure say?',
    'library.lookup.list-to-library-new-form-write': 'Does AddValidateUpdateItemUsingPath create a row with the NAME-bound lookup set, and read back?',
    'library.lookup.list-to-library-name-expand-projects': 'Does $select=<name>/FileLeafRef&$expand=<name> answer through the NAME-bound lookup, and with what?',
    'library.lookup.name-bound-picker-labels-files': 'What does the picker for the NAME-bound lookup offer, and how is each entry labelled?',
  };
  expect('library.doc-lib.fixture-library-created', QUESTIONS['library.doc-lib.fixture-library-created']);
  expect('library.lookup.fixture-write-containers-ready', QUESTIONS['library.lookup.fixture-write-containers-ready']);
  expect('library.lookup.control-whole-item-read-before-lookups', QUESTIONS['library.lookup.control-whole-item-read-before-lookups']);
  expect('library.lookup.whole-item-read-with-title-lookup-column', QUESTIONS['library.lookup.whole-item-read-with-title-lookup-column']);
  expect('library.lookup.whole-item-read-with-name-lookup-column', QUESTIONS['library.lookup.whole-item-read-with-name-lookup-column']);
  expect('library.lookup.control-text-column-item-writes', QUESTIONS['library.lookup.control-text-column-item-writes']);
  expect('library.lookup.control-list-to-list-create-write-string-id', QUESTIONS['library.lookup.control-list-to-list-create-write-string-id']);
  expect('library.lookup.control-list-to-list-merge-write', QUESTIONS['library.lookup.control-list-to-list-merge-write']);
  expect('library.lookup.control-list-to-list-create-write', QUESTIONS['library.lookup.control-list-to-list-create-write']);
  expect('library.lookup.control-list-to-list-form-write', QUESTIONS['library.lookup.control-list-to-list-form-write']);
  expect('library.lookup.list-to-library-title-addfield-created', QUESTIONS['library.lookup.list-to-library-title-addfield-created']);
  expect('library.lookup.list-to-library-name-addfield-created', QUESTIONS['library.lookup.list-to-library-name-addfield-created']);
  expect('library.formula.calc-name-operand', QUESTIONS['library.formula.calc-name-operand']);
  expect('library.lookup.list-to-library-calc-name-addfield-created', QUESTIONS['library.lookup.list-to-library-calc-name-addfield-created']);
  expect('library.lookup.list-to-library-calc-name-form-write', QUESTIONS['library.lookup.list-to-library-calc-name-form-write']);
  expect('library.lookup.calc-name-bound-row-read-after-write', QUESTIONS['library.lookup.calc-name-bound-row-read-after-write']);
  expect('library.lookup.list-to-library-calc-name-create-write', QUESTIONS['library.lookup.list-to-library-calc-name-create-write']);
  expect('library.lookup.list-to-library-calc-name-expand-projects', QUESTIONS['library.lookup.list-to-library-calc-name-expand-projects']);
  expect('library.lookup.calc-name-bound-picker-labels-files', QUESTIONS['library.lookup.calc-name-bound-picker-labels-files']);
  expect('library.lookup.list-to-library-name-merge-write', QUESTIONS['library.lookup.list-to-library-name-merge-write']);
  expect('library.lookup.list-to-library-titled-file-merge-write', QUESTIONS['library.lookup.list-to-library-titled-file-merge-write']);
  expect('library.lookup.list-to-library-name-create-write', QUESTIONS['library.lookup.list-to-library-name-create-write']);
  expect('library.lookup.list-to-library-title-create-write', QUESTIONS['library.lookup.list-to-library-title-create-write']);
  expect('library.lookup.list-to-library-title-form-write', QUESTIONS['library.lookup.list-to-library-title-form-write']);
  expect('library.lookup.title-bound-row-read-after-write', QUESTIONS['library.lookup.title-bound-row-read-after-write']);
  expect('library.lookup.list-to-library-name-form-write', QUESTIONS['library.lookup.list-to-library-name-form-write']);
  expect('library.lookup.name-bound-row-read-after-write', QUESTIONS['library.lookup.name-bound-row-read-after-write']);
  expect('library.lookup.list-to-library-new-form-write', QUESTIONS['library.lookup.list-to-library-new-form-write']);
  expect('library.lookup.list-to-library-name-expand-projects', QUESTIONS['library.lookup.list-to-library-name-expand-projects']);
  expect('library.lookup.name-bound-picker-labels-files', QUESTIONS['library.lookup.name-bound-picker-labels-files']);
  // Every record() below names its id as a literal so the catalogue gate
  // can read it; the question text is looked up so the two cannot drift.
  const answer = (id, outcome, evidence, state) => record(id, QUESTIONS[id], outcome, evidence, state);

  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const sameGuid = (left, right) => {
    const bare = (value) => String(value === null || value === undefined ? '' : value)
      .replace(/[{}]/g, '').toLowerCase();
    return bare(left) !== '' && bare(left) === bare(right);
  };
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };

  // A raw request body, not JSON: Files/add takes the file's bytes.
  const rawPost = async (path, body, digest, extraHeaders = {}) => {
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

  // The harness's spGet drops the response text, and a refused READ is the
  // finding on two rows below, so this one keeps it.
  const spGetText = async (path) => {
    try {
      const res = await fetch(`${WEB}/_api/${path}`, {
        headers: { Accept: 'application/json;odata=nometadata' },
      });
      const text = await res.text();
      let parsed = null;
      try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
      return { ok: res.ok, status: res.status, body: parsed, text };
    } catch (err) {
      return { ok: false, status: 0, body: null, text: String(err) };
    }
  };
  const spError = (res) => {
    const err = res.body && (res.body['odata.error'] || res.body.error);
    const message = err && err.message && (err.message.value || err.message);
    return clip(message || res.text, 160);
  };

  // The deploy's route for a single-value lookup: `fields/addfield` with the
  // same SP.FieldCreationInformation body `generators/jsgen.py` emits, verbose
  // because the body carries `__metadata`.
  const addLookup = async (container, name, targetId, showField) => {
    const digest = await getDigest();
    return spPost(`${container}/fields/addfield`, {
      parameters: {
        __metadata: { type: 'SP.FieldCreationInformation' },
        FieldTypeKind: 7,
        Title: name,
        Required: false,
        LookupFieldName: showField,
        LookupListId: targetId,
      },
    }, digest, VERBOSE);
  };
  const readField = async (container, name) => spGet(fieldPath(container, name));

  // The bare shape the 2026-09-07 run sent.
  const mergeItem = async (container, itemId, body) => {
    const digest = await getDigest();
    return spPost(`${container}/items(${itemId})`, body, digest, {
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };
  // The list's item entity type, which Learn's "Update list item" and the
  // deploy's seeder both put in `__metadata.type`.
  const entityTypeOf = async (container) => {
    const res = await spGet(`${container}?$select=ListItemEntityTypeFullName`);
    return !readFailed(res) ? res.body.ListItemEntityTypeFullName : null;
  };
  const mergeItemTyped = async (container, itemId, body, entityType) => {
    const digest = await getDigest();
    return spPost(`${container}/items(${itemId})`, { __metadata: { type: entityType }, ...body }, digest, {
      ...VERBOSE,
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };
  // The deploy's list seed: one POST, verbose, carrying the entity type.
  const createItemTyped = async (container, body, entityType) => {
    const digest = await getDigest();
    return spPost(`${container}/items`, { __metadata: { type: entityType }, ...body }, digest, VERBOSE);
  };
  const createdId = (res) => {
    if (readFailed(res)) return null;
    const d = res.body.d || res.body;
    return Number.isInteger(d.Id) ? d.Id : null;
  };

  const makeLookup = async (container, name, targetId, showField) => {
    const made = await addLookup(container, name, targetId, showField);
    const read = await readField(container, name);
    const bound = !readFailed(read)
      && read.body.TypeAsString === 'Lookup'
      && sameGuid(read.body.LookupList, targetId)
      && read.body.LookupField === showField;
    return {
      made,
      bound,
      description: `create HTTP ${made.status}`
        + (made.ok ? '' : `: ${clip(made.text, 200)}`)
        + '; readback '
        + (readFailed(read)
          ? `failed HTTP ${read.status}`
          : `TypeAsString=${show(read.body.TypeAsString)} `
            + `LookupList=${show(read.body.LookupList)} `
            + `LookupField=${show(read.body.LookupField)} `
            + `AllowMultipleValues=${show(read.body.AllowMultipleValues)}`),
    };
  };

  // A lookup's stored id, read two ways. The narrow read is what every
  // consumer sends; when it fails, the whole item says whether the key is
  // there at all, so a refused $select is not reported as a refused write.
  const readBack = async (container, itemId, name) => {
    const key = `${name}Id`;
    const narrow = await spGetText(`${container}/items(${itemId})?$select=${key}`);
    if (!readFailed(narrow)) {
      return { ok: true, id: narrow.body[key], description: `readback HTTP ${narrow.status}, ${key}=${show(narrow.body[key])}` };
    }
    const whole = await spGetText(`${container}/items(${itemId})`);
    const present = !readFailed(whole) && Object.prototype.hasOwnProperty.call(whole.body, key);
    return {
      ok: !readFailed(whole),
      id: present ? whole.body[key] : undefined,
      description: `readback $select=${key} FAILED HTTP ${narrow.status} ${spError(narrow)}; `
        + `the whole item read HTTP ${whole.status}`
        + (readFailed(whole) ? ` ${spError(whole)}` : `, ${key} ${present ? `present as ${show(whole.body[key])}` : 'ABSENT'}`),
    };
  };

  // Five reads of one row, each the shape a shipped consumer sends: the
  // deploy's readback, a whole-item read, the reporting pack's collection
  // read with and without the column, and the view renderer. Recorded per
  // shape so a value that breaks one read and not another is described
  // rather than summarised.
  const rowReadShapes = async (rowId, name) => {
    const key = `${name}Id`;
    const shapes = [
      ['items(id)?$select=Id', `${srcPath}/items(${rowId})?$select=Id`],
      [`items(id)?$select=${key}`, `${srcPath}/items(${rowId})?$select=${key}`],
      ['items(id)', `${srcPath}/items(${rowId})`],
      ['items?$select=Id,Title', `${srcPath}/items?$select=Id,Title&$top=50`],
      [`items?$select=Id,${key}`, `${srcPath}/items?$select=Id,${key}&$top=50`],
    ];
    const results = [];
    for (const [label, path] of shapes) {
      const res = await spGetText(path);
      results.push({ label, ok: !readFailed(res), status: res.status, error: readFailed(res) ? spError(res) : '' });
    }
    const viewXml = '<View><Query></Query>'
      + `<ViewFields><FieldRef Name='ID'/><FieldRef Name='${name}'/></ViewFields>`
      + '<RowLimit>50</RowLimit></View>';
    const digest = await getDigest();
    const rendered = await spPost(`${srcPath}/RenderListDataAsStream`,
      { parameters: { ViewXml: viewXml } }, digest,
      { 'Content-Type': 'application/json;odata=verbose' });
    const rows = rendered.ok && rendered.body && Array.isArray(rendered.body.Row) ? rendered.body.Row : [];
    const rendersRow = rows.find((r) => String(r.ID) === String(rowId)) || null;
    results.push({
      label: `RenderListDataAsStream projecting ${name}`,
      ok: rendered.ok && rendersRow !== null,
      status: rendered.status,
      error: rendered.ok ? (rendersRow ? '' : 'the row was not among those rendered') : clip(rendered.text, 160),
      value: rendersRow ? rendersRow[name] : undefined,
    });
    const failed = results.filter((r) => !r.ok);
    return {
      outcome: failed.length === 0 ? 'ALL READS ANSWER'
        : failed.length === results.length ? 'NO READ ANSWERS'
          : `${failed.length} OF ${results.length} READS FAIL`,
      evidence: results.map((r) => `${r.label}: HTTP ${r.status}`
        + (r.ok ? (r.value !== undefined ? ` value ${show(r.value)}` : '') : ` ${r.error}`)).join(' | '),
    };
  };
  const writeHead = (res, back, wanted) => {
    if (!res.ok) return isRefusal(res.status) ? 'REFUSED' : 'NOT ESTABLISHED';
    if (!back.ok) return 'ACCEPTED, READBACK FAILED';
    return back.id === wanted ? 'HELD' : 'ACCEPTED BUT NOT HELD';
  };

  // The form endpoint reports a refusal INSIDE a 200: the payload is the
  // answer. Read under either OData dialect, because the new-item form
  // endpoint has to be sent verbose (its payload carries __metadata) and
  // the existing-item one is sent nometadata like every other write here.
  const formRows = (res) => {
    if (readFailed(res)) return null;
    if (Array.isArray(res.body.value)) return res.body.value;
    const d = res.body.d || {};
    const nested = d.ValidateUpdateListItem || d.AddValidateUpdateItemUsingPath;
    return nested && Array.isArray(nested.results) ? nested.results : null;
  };
  const formErrors = (rows) => rows.filter((x) => x.HasException)
    .map((x) => `${x.FieldName}: ${x.ErrorMessage}`);

  const validateUpdate = async (container, itemId, fieldName, fieldValue) => {
    const digest = await getDigest();
    return spPost(`${container}/items(${itemId})/ValidateUpdateListItem`, {
      formValues: [{ FieldName: fieldName, FieldValue: fieldValue }],
      bNewDocumentUpdate: false,
    }, digest);
  };

  // ---- Pre-run reset ------------------------------------------------------
  // Source first: it holds every lookup, so nothing points into it.
  await resetList(SRC);
  await resetList(LIB);
  await resetList(TGT);

  // ---- fixture-library-created ---------------------------------------------
  let digest = await getDigest();
  const existingLib = await spGet(libPath);
  let libraryReady = false;
  if (existingLib.ok) {
    answer('library.doc-lib.fixture-library-created', 'ALREADY PRESENT',
           `reusing an existing '${LIB}'. Set CLEANUP = true for a clean answer`);
    libraryReady = true;
  } else {
    const made = await spPost('web/lists', {
      Title: LIB,
      BaseTemplate: 101,
      Description: 'dbml-sharepoint library-lookup-write probe library. Safe to delete.',
    }, digest);
    answer('library.doc-lib.fixture-library-created', made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIB}'` : `HTTP ${made.status}: ${clip(made.text, 300)}`);
    libraryReady = made.ok;
  }

  const abortEverything = (reason) => {
    for (const id of Object.keys(QUESTIONS)) {
      if (id === 'library.doc-lib.fixture-library-created') continue;
      const row = RESULTS.find((r) => r.id === id);
      if (row && row.outcome === 'NOT ESTABLISHED') {
        Object.assign(row, { outcome: 'ABORTED', evidence: reason, state: 'open' });
      }
    }
    return report();
  };

  if (!libraryReady) {
    return abortEverything('the scratch library was never created, so no lookup had a library to point at');
  }

  // ---- fixture-write-containers-ready --------------------------------------
  const ensureList = async (path, title, description) => {
    const found = await spGet(path);
    if (found.ok && found.body) return { id: found.body.Id, note: `'${title}' already present` };
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title, BaseTemplate: 100, Description: description,
    }, digest);
    return {
      id: made.ok && made.body ? made.body.Id : null,
      note: made.ok ? `created '${title}'` : `'${title}' FAILED HTTP ${made.status}: ${clip(made.text, 160)}`,
    };
  };
  const ensureRow = async (path, title) => {
    const existing = await spGet(`${path}/items?$select=Id,Title&$filter=Title eq '${odataName(title)}'`);
    const rows = (existing.ok && existing.body && existing.body.value) || [];
    if (rows.length) return rows[0].Id;
    digest = await getDigest();
    const made = await spPost(`${path}/items`, { Title: title }, digest);
    return made.ok && made.body ? made.body.Id : null;
  };

  const notes = [];
  const target = await ensureList(tgtPath, TGT,
    'dbml-sharepoint library-lookup-write probe lookup target. Safe to delete.');
  notes.push(target.note);
  const source = await ensureList(srcPath, SRC,
    'dbml-sharepoint library-lookup-write probe source list. Safe to delete.');
  notes.push(source.note);
  const libRead = await spGet(libPath);
  const libId = libRead.ok && libRead.body ? libRead.body.Id : null;
  notes.push(libId ? 'library id read' : `library id could NOT be read (HTTP ${libRead.status})`);
  const srcType = source.id ? await entityTypeOf(srcPath) : null;
  notes.push(srcType ? `source entity type ${srcType}` : 'source ListItemEntityTypeFullName could NOT be read');

  const targetRowId = target.id ? await ensureRow(tgtPath, TGT_ROW) : null;
  notes.push(targetRowId === null ? 'target row FAILED' : `target row id ${targetRowId}`);
  const mergeRowId = source.id ? await ensureRow(srcPath, SRC_ROWS[0]) : null;
  const formRowId = source.id ? await ensureRow(srcPath, SRC_ROWS[1]) : null;
  notes.push(`source rows ${show(mergeRowId)}, ${show(formRowId)}`);

  // Two files: one left as uploaded (Title null, the shape 2026-09-07 hit)
  // and one given a Title, so the Title-bound rows can vary that alone.
  const upload = async (name) => {
    digest = await getDigest();
    return rawPost(
      `${libPath}/RootFolder/Files/add(url='${name}',overwrite=true)`,
      'dbml-sharepoint library-lookup-write probe payload',
      digest,
      { 'Content-Type': 'text/plain' });
  };
  const plainUpload = await upload(FILE_PLAIN);
  const titledUpload = await upload(FILE_TITLED);
  notes.push(plainUpload.ok ? `uploaded '${FILE_PLAIN}'` : `upload of '${FILE_PLAIN}' FAILED HTTP ${plainUpload.status}`);
  notes.push(titledUpload.ok ? `uploaded '${FILE_TITLED}'` : `upload of '${FILE_TITLED}' FAILED HTTP ${titledUpload.status}`);

  const libRows = await spGet(`${libPath}/items?$select=Id,FileLeafRef,Title&$top=50`);
  const libRowList = (libRows.ok && libRows.body && libRows.body.value) || [];
  const plainRow = libRowList.find((row) => row.FileLeafRef === FILE_PLAIN) || null;
  const titledRow = libRowList.find((row) => row.FileLeafRef === FILE_TITLED) || null;
  const plainId = plainRow ? plainRow.Id : null;
  const titledId = titledRow ? titledRow.Id : null;
  let titledTitle = null;
  if (titledId !== null) {
    const setTitle = await mergeItem(libPath, titledId, { Title: TITLED_TITLE });
    const back = await spGet(`${libPath}/items(${titledId})?$select=Title`);
    titledTitle = !readFailed(back) ? back.body.Title : null;
    notes.push(`Title on '${FILE_TITLED}': MERGE HTTP ${setTitle.status}, reads back ${show(titledTitle)}`);
  }
  notes.push(`untitled file id ${show(plainId)} Title ${show(plainRow ? plainRow.Title : null)}`);

  const fixtureReady = target.id !== null && source.id !== null && libId !== null && srcType !== null
    && targetRowId !== null && mergeRowId !== null && formRowId !== null
    && plainId !== null && titledId !== null && titledTitle === TITLED_TITLE;
  answer('library.lookup.fixture-write-containers-ready', fixtureReady ? 'PASS' : 'FAIL', notes.join('; '));
  if (target.id === null || source.id === null || libId === null || mergeRowId === null || formRowId === null) {
    return abortEverything(`a container or row this probe writes on was never created: ${notes.join('; ')}`);
  }

  // A whole-item read, the one shape no shipped consumer sends, asked three
  // times as the list gains columns so a failure can be attributed.
  const wholeRead = async (id, when) => {
    const res = await spGetText(`${srcPath}/items(${mergeRowId})`);
    answer(id, readFailed(res) ? 'FAILS' : 'ANSWERS',
           `items(${mergeRowId}) with no $select, ${when}: HTTP ${res.status}`
           + (readFailed(res) ? ` ${spError(res)}` : ''));
  };
  await wholeRead('library.lookup.control-whole-item-read-before-lookups',
    'before any lookup column exists on the list');

  // ---- The control and the Title-bound lookup; the Name-bound one comes last --
  const control = await makeLookup(srcPath, CONTROL_LOOKUP, target.id, 'Title');
  const byTitle = await makeLookup(srcPath, LIB_TITLE_LOOKUP, libId, 'Title');
  const createHead = (made) => (made.bound ? 'BOUND'
    : made.made.ok ? 'ACCEPTED BUT NOT BOUND'
      : isRefusal(made.made.status) ? 'REFUSED' : 'NOT ESTABLISHED');
  answer('library.lookup.list-to-library-title-addfield-created', createHead(byTitle),
         `${LIB_TITLE_LOOKUP} on '${SRC}' -> the LIBRARY.Title, by fields/addfield: ${byTitle.description}`);
  await wholeRead('library.lookup.whole-item-read-with-title-lookup-column',
    `with ${CONTROL_LOOKUP} and ${LIB_TITLE_LOOKUP} on the list and no value set`);

  const noControl = `${CONTROL_LOOKUP} on '${SRC}' -> '${TGT}'.Title: ${control.description}. No `
    + 'list-to-list lookup exists to write to, so no write method was shown to work here.';

  // ---- POSITIVE CONTROL: the MERGE method, in two shapes -------------------
  // Bare nometadata first, because that is what the 2026-09-07 run sent and
  // this row has to say whether THAT was the problem. Then the typed verbose
  // shape Learn documents and the deploy ships. The shape that holds is the
  // one the MERGE rows send.
  let mergeShape = null;
  const mergeIn = async (shape, itemId, body) => (shape === 'typed'
    ? mergeItemTyped(srcPath, itemId, body, srcType)
    : mergeItem(srcPath, itemId, body));
  if (!control.bound || targetRowId === null) {
    answer('library.lookup.control-list-to-list-merge-write', 'CONTROL FAILED, METHOD VOID', noControl);
  } else {
    const attempts = [];
    for (const shape of ['bare', 'typed']) {
      if (shape === 'typed' && srcType === null) break;
      const wrote = await mergeIn(shape, mergeRowId, { [`${CONTROL_LOOKUP}Id`]: targetRowId });
      const back = await readBack(srcPath, mergeRowId, CONTROL_LOOKUP);
      const held = wrote.ok && back.ok && back.id === targetRowId;
      attempts.push(`${shape}: HTTP ${wrote.status}${wrote.ok ? '' : ` ${clip(wrote.text, 160)}`}; ${back.description}`);
      if (held) { mergeShape = shape; break; }
    }
    answer('library.lookup.control-list-to-list-merge-write',
           mergeShape ? `HELD (${mergeShape})` : 'CONTROL FAILED, METHOD VOID',
           `MERGE ${CONTROL_LOOKUP}Id=${targetRowId} on '${SRC}' items(${mergeRowId}). ${attempts.join(' | ')}. `
           + (mergeShape ? `The MERGE rows send the ${mergeShape} shape.`
             : 'The MERGE rows below are void: a refusal there could not be told from this method '
               + 'not working on this site. On 2026-09-18 the bare shape failed HTTP 500 here.'));
  }

  // ---- POSITIVE CONTROL: the deploy's create shape --------------------------
  let createMethodHolds = false;
  if (!control.bound || targetRowId === null) {
    answer('library.lookup.control-list-to-list-create-write', 'CONTROL FAILED, METHOD VOID', noControl);
  } else if (srcType === null) {
    answer('library.lookup.control-list-to-list-create-write', 'NOT ESTABLISHED',
           'the source list\'s ListItemEntityTypeFullName could not be read, so the deploy\'s body could not be built');
  } else {
    const made = await createItemTyped(srcPath, {
      Title: 'dbmlsp libwrite create control row', [`${CONTROL_LOOKUP}Id`]: targetRowId,
    }, srcType);
    const newId = createdId(made);
    const back = newId === null ? { ok: false, id: undefined, description: 'no row id to read' }
      : await readBack(srcPath, newId, CONTROL_LOOKUP);
    createMethodHolds = made.ok && back.ok && back.id === targetRowId;
    answer('library.lookup.control-list-to-list-create-write',
           createMethodHolds ? 'HELD' : 'CONTROL FAILED, METHOD VOID',
           `POST '${SRC}' items with ${CONTROL_LOOKUP}Id=${targetRowId}, verbose, __metadata.type=${srcType}: `
           + `HTTP ${made.status}${made.ok ? `, created id ${show(newId)}` : ` ${clip(made.text, 160)}`}; ${back.description}`
           + (createMethodHolds ? '' : '. The create rows below are void.'));
  }

  // ---- POSITIVE CONTROL: the form method, and its value spelling -----------
  let formSpelling = null;
  const tryFormSpellings = async (rowId, name, itemId, label) => {
    const attempts = [];
    const spellings = formSpelling !== null ? [formSpelling] : ['bare-id', 'id-label'];
    for (const spelling of spellings) {
      const value = spelling === 'bare-id' ? String(itemId) : `${itemId};#${label}`;
      const res = await validateUpdate(srcPath, rowId, name, value);
      const rows = formRows(res);
      const errors = rows ? formErrors(rows) : null;
      const accepted = res.ok && rows !== null && errors.length === 0;
      const back = await readBack(srcPath, rowId, name);
      const held = accepted && back.ok && back.id === itemId;
      attempts.push({ spelling, value, res, rows, errors, accepted, back, held });
      if (held) break;
    }
    return attempts;
  };
  const describeAttempts = (attempts) => attempts.map((a) =>
    `FieldValue=${show(a.value)} (${a.spelling}): HTTP ${a.res.status}`
    + (!a.res.ok ? ` ${clip(a.res.text, 160)}`
      : a.rows === null ? ', no formValues results in the response'
        : a.errors.length ? `, refused by the endpoint: ${a.errors.join('; ')}` : ', accepted')
    + `; ${a.back.description}`).join(' | ');
  const formHead = (attempts) => {
    if (attempts.some((a) => a.held)) return 'HELD';
    if (attempts.some((a) => a.accepted && !a.back.ok)) return 'ACCEPTED, READBACK FAILED';
    if (attempts.some((a) => a.accepted)) return 'ACCEPTED BUT NOT HELD';
    if (attempts.every((a) => (a.res.ok && a.rows !== null) || isRefusal(a.res.status))) return 'REFUSED';
    return 'NOT ESTABLISHED';
  };

  let formMethodHolds = false;
  if (!control.bound || targetRowId === null) {
    answer('library.lookup.control-list-to-list-form-write', 'CONTROL FAILED, METHOD VOID', noControl);
  } else {
    const attempts = await tryFormSpellings(formRowId, CONTROL_LOOKUP, targetRowId, TGT_ROW);
    const held = attempts.find((a) => a.held) || null;
    formMethodHolds = held !== null;
    if (held) formSpelling = held.spelling;
    answer('library.lookup.control-list-to-list-form-write',
           formMethodHolds ? `HELD (${held.spelling})` : 'CONTROL FAILED, METHOD VOID',
           `ValidateUpdateListItem on '${SRC}' items(${formRowId}) setting ${CONTROL_LOOKUP}: `
           + describeAttempts(attempts)
           + (formMethodHolds ? `. The form rows send the ${held.spelling} spelling.`
             : '. The form rows below are void: a refusal there could not be told from '
               + 'this endpoint not setting any lookup on this site.'));
  }

  // ---- CONTROL: do item writes work on this list at all? --------------------
  // A plain Text column, created with the body the deploy sends for one,
  // written by the same bare MERGE and the same typed POST the lookup
  // controls send. If these hold, the refusals above are about the lookup
  // value; if they fail too, they are about this list or this site.
  {
    const TEXT = 'XWriteText';
    digest = await getDigest();
    const madeText = await spPost(`${srcPath}/fields`, {
      __metadata: { type: 'SP.FieldText' }, FieldTypeKind: 2, Title: TEXT,
    }, digest, VERBOSE);
    if (!madeText.ok) {
      answer('library.lookup.control-text-column-item-writes', 'NOT ESTABLISHED',
             `the Text column could not be created: HTTP ${madeText.status} ${clip(madeText.text, 160)}`);
    } else {
      const merged = await mergeItem(srcPath, mergeRowId, { [TEXT]: 'merge' });
      const afterMerge = await spGetText(`${srcPath}/items(${mergeRowId})?$select=${TEXT}`);
      const mergeHeld = merged.ok && !readFailed(afterMerge) && afterMerge.body[TEXT] === 'merge';
      const posted = srcType === null ? null
        : await createItemTyped(srcPath, { Title: 'dbmlsp libwrite text control row', [TEXT]: 'post' }, srcType);
      const postId = posted === null ? null : createdId(posted);
      const afterPost = postId === null ? null : await spGetText(`${srcPath}/items(${postId})?$select=${TEXT}`);
      const postHeld = posted !== null && posted.ok && afterPost !== null && !readFailed(afterPost) && afterPost.body[TEXT] === 'post';
      answer('library.lookup.control-text-column-item-writes',
             mergeHeld && postHeld ? 'BOTH HELD'
               : mergeHeld ? 'MERGE HELD, POST FAILED'
                 : postHeld ? 'POST HELD, MERGE FAILED' : 'CONTROL FAILED, ITEM WRITES DO NOT WORK HERE',
             `bare MERGE ${TEXT}='merge' on items(${mergeRowId}): HTTP ${merged.status}`
             + (merged.ok ? '' : ` ${clip(merged.text, 160)}`)
             + `, reads back ${readFailed(afterMerge) ? `unreadable HTTP ${afterMerge.status}` : show(afterMerge.body[TEXT])}`
             + ' | typed POST '
             + (posted === null ? 'not sent, no entity type'
               : `HTTP ${posted.status}${posted.ok ? `, created id ${show(postId)}` : ` ${clip(posted.text, 160)}`}`
                 + `, reads back ${afterPost === null ? 'nothing to read' : readFailed(afterPost) ? `unreadable HTTP ${afterPost.status}` : show(afterPost.body[TEXT])}`)
             + '. A held Text write beside a refused lookup write says the lookup VALUE is what this list refuses.');
    }
  }

  // ---- CONTROL: the deploy's POST with the id spelled as a string ------------
  if (!control.bound || targetRowId === null) {
    answer('library.lookup.control-list-to-list-create-write-string-id', 'CONTROL FAILED, METHOD VOID', noControl);
  } else if (srcType === null) {
    answer('library.lookup.control-list-to-list-create-write-string-id', 'NOT ESTABLISHED',
           'the source list\'s ListItemEntityTypeFullName could not be read, so the deploy\'s body could not be built');
  } else {
    const made = await createItemTyped(srcPath, {
      Title: 'dbmlsp libwrite create control row, string id', [`${CONTROL_LOOKUP}Id`]: String(targetRowId),
    }, srcType);
    const newId = createdId(made);
    const back = newId === null ? { ok: false, id: undefined, description: 'no row id to read' }
      : await readBack(srcPath, newId, CONTROL_LOOKUP);
    const held = made.ok && back.ok && back.id === targetRowId;
    if (held && !createMethodHolds) createMethodHolds = true;
    answer('library.lookup.control-list-to-list-create-write-string-id', writeHead(made, back, targetRowId),
           `POST '${SRC}' items with ${CONTROL_LOOKUP}Id="${targetRowId}" (a string), verbose, __metadata.type=${srcType}: `
           + `HTTP ${made.status}${made.ok ? `, created id ${show(newId)}` : ` ${clip(made.text, 160)}`}; ${back.description}`
           + (held ? '. The create rows below send the string spelling.' : ''));
  }
  const createIdValue = (itemId) => (createMethodHolds && RESULTS.find(
    (r) => r.id === 'library.lookup.control-list-to-list-create-write').outcome !== 'HELD'
    ? String(itemId) : itemId);

  // One expand row for the two bindings that need it, so the request shape
  // and the verdict cannot drift between them. `column` is the target
  // column the display is bound to; the projection is compared with the
  // untitled file's name, which is what both bindings should show.
  const expandRow = async (id, name, rowId, column) => {
    if (rowId === null) {
      answer(id, 'NOT ESTABLISHED', `no write to ${name} held on any row, so there was no value to expand`);
      return;
    }
    const expanded = async (target) => spGetText(
      `${srcPath}/items(${rowId})?$select=${name}Id,${name}/${target}&$expand=${name}`);
    const via = await expanded(column);
    const viaTitle = await expanded('Title');
    const projected = (res, key) => (readFailed(res) ? undefined
      : res.body[name] ? res.body[name][key] : null);
    answer(id,
           !readFailed(via) ? (projected(via, column) === FILE_PLAIN ? 'PROJECTS' : 'ACCEPTED BUT NOT THE NAME')
             : isRefusal(via.status) ? 'REFUSED' : 'NOT ESTABLISHED',
           `on items(${rowId}): $select=${name}/${column}&$expand=${name}: HTTP ${via.status}, `
           + `${column}=${show(projected(via, column))}${readFailed(via) ? ` ${spError(via)}` : ''}`
           + `; the same through /Title: HTTP ${viaTitle.status}, Title=${show(projected(viaTitle, 'Title'))}. `
           + 'PROJECTS is what lets analysis/reporting/plan.py expand this lookup like any other.');
  };

  // ---- The MERGE rows -------------------------------------------------------
  const mergeRow = async (id, name, made, itemId, fileName) => {
    if (mergeShape === null) {
      answer(id, 'VOID', 'the MERGE control did not hold, so a refusal here could not be attributed', 'void');
      return false;
    }
    if (!made.bound) {
      answer(id, 'NOT ESTABLISHED', `${name} is not a lookup bound to the library, so there was nothing to write to`);
      return false;
    }
    const wrote = await mergeIn(mergeShape, mergeRowId, { [`${name}Id`]: itemId });
    const back = await readBack(srcPath, mergeRowId, name);
    answer(id, writeHead(wrote, back, itemId),
           `MERGE (${mergeShape}) ${name}Id=${itemId}, the file '${fileName}', on '${SRC}' items(${mergeRowId}): `
           + `HTTP ${wrote.status}${wrote.ok ? '' : `: ${clip(wrote.text, 200)}`}; ${back.description}`);
    return wrote.ok && back.ok && back.id === itemId;
  };
  await mergeRow('library.lookup.list-to-library-titled-file-merge-write',
    LIB_TITLE_LOOKUP, byTitle, titledId, FILE_TITLED);

  // ---- The create rows, in the deploy's seed shape ----------------------------
  let nameCreateRowId = null;
  const createRow = async (id, name, made, itemId, fileName) => {
    if (!createMethodHolds) {
      answer(id, 'VOID', 'the create control did not hold, so a refusal here could not be attributed', 'void');
      return null;
    }
    if (!made.bound) {
      answer(id, 'NOT ESTABLISHED', `${name} is not a lookup bound to the library, so there was nothing to set`);
      return null;
    }
    const wrote = await createItemTyped(srcPath, {
      Title: `dbmlsp libwrite create row ${name}`, [`${name}Id`]: createIdValue(itemId),
    }, srcType);
    const newId = createdId(wrote);
    const back = newId === null ? { ok: false, id: undefined, description: 'no row id to read' }
      : await readBack(srcPath, newId, name);
    answer(id, writeHead(wrote, back, itemId),
           `POST '${SRC}' items with ${name}Id=${itemId}, the file '${fileName}', verbose, `
           + `__metadata.type=${srcType}: HTTP ${wrote.status}`
           + (wrote.ok ? `, created id ${show(newId)}` : `: ${clip(wrote.text, 200)}`) + `; ${back.description}. `
           + 'This is the write demo.js.j2 makes for a seeded list row, so HELD here is what lets a family seed one.');
    return wrote.ok && back.ok && back.id === itemId ? newId : null;
  };
  await createRow('library.lookup.list-to-library-title-create-write',
    LIB_TITLE_LOOKUP, byTitle, titledId, FILE_TITLED);

  // ---- The form rows on an existing item -----------------------------------
  const formRow = async (id, name, made, itemId, label) => {
    if (!formMethodHolds) {
      answer(id, 'VOID', 'the form control did not hold, so a refusal here could not be attributed', 'void');
      return false;
    }
    if (!made.bound) {
      answer(id, 'NOT ESTABLISHED', `${name} is not a lookup bound to the library, so there was nothing to set`);
      return false;
    }
    const attempts = await tryFormSpellings(formRowId, name, itemId, label);
    answer(id, formHead(attempts),
           `ValidateUpdateListItem on '${SRC}' items(${formRowId}) setting ${name} to item ${itemId} `
           + `('${label}'): ${describeAttempts(attempts)}`);
    return attempts.some((a) => a.held);
  };
  const titleFormHeld = await formRow('library.lookup.list-to-library-title-form-write',
    LIB_TITLE_LOOKUP, byTitle, titledId, TITLED_TITLE);
  if (titleFormHeld) {
    const reads = await rowReadShapes(formRowId, LIB_TITLE_LOOKUP);
    answer('library.lookup.title-bound-row-read-after-write', reads.outcome,
           `items(${formRowId}) holding ${LIB_TITLE_LOOKUP}Id=${titledId}. ${reads.evidence}`);
  } else {
    answer('library.lookup.title-bound-row-read-after-write', 'NOT ESTABLISHED',
           'no Title-bound value was held on the form row, so there was nothing to read');
  }

  // ---- A Calculated column =[Name] on the library, and a lookup bound to it --
  // Created with the body the deploy sends for a calculated column (see
  // generators/jsgen.py: OutputType 2 is Text). `[Name]` is the display name
  // of FileLeafRef, which is how a formula names a column.
  // Two spellings: the display name, which is what a formula resolves
  // against, and the internal name, in case the parser takes either. Each
  // is its own column because a refused create can leave a column behind
  // (2026-09-18: Formula `=""`), and that must not be mistaken for the other.
  const calcColumn = async (name, formula) => {
    digest = await getDigest();
    const made = await spPost(`${libPath}/fields`, {
      __metadata: { type: 'SP.FieldCalculated' }, FieldTypeKind: 17, Title: name,
      OutputType: 2, Formula: formula,
    }, digest, VERBOSE);
    const read = await readField(libPath, name);
    const values = await spGetText(`${libPath}/items?$select=Id,FileLeafRef,${name}&$top=50`);
    const rows = !readFailed(values) && Array.isArray(values.body.value) ? values.body.value : [];
    const plain = (rows.find((r) => r.Id === plainId) || {})[name];
    const titled = (rows.find((r) => r.Id === titledId) || {})[name];
    return {
      name,
      formula,
      made,
      resolves: made.ok && plain === FILE_PLAIN && titled === FILE_TITLED,
      description: `POST ${name} ${formula} (SP.FieldCalculated, OutputType 2): HTTP ${made.status}`
        + (made.ok ? '' : ` ${clip(made.text, 200)}`)
        + `; field readback ${readFailed(read) ? `failed HTTP ${read.status}` : `TypeAsString=${show(read.body.TypeAsString)} Formula=${show(read.body.Formula)}`}`
        + `; items?$select=${name}: HTTP ${values.status}${readFailed(values) ? ` ${spError(values)}` : ''}`
        + `, untitled file ${show(plain)}, titled file ${show(titled)}`,
    };
  };
  const byDisplay = await calcColumn(CALC_NAME, '=[Name]');
  const byInternal = await calcColumn(`${CALC_NAME}Leaf`, '=[FileLeafRef]');
  const resolved = [byDisplay, byInternal].find((c) => c.resolves) || null;
  const calcNameHolds = resolved !== null;
  answer('library.formula.calc-name-operand',
         resolved ? `RESOLVES TO THE FILE NAME (${resolved.formula})`
           : !byDisplay.made.ok && !byInternal.made.ok
             ? (isRefusal(byDisplay.made.status) && isRefusal(byInternal.made.status) ? 'REFUSED, BOTH SPELLINGS' : 'NOT ESTABLISHED')
             : 'CREATED BUT DOES NOT RESOLVE',
         `on the LIBRARY, ${byDisplay.description} | ${byInternal.description}`);
  // The lookup binds to the spelling that resolved, else to the display-name
  // column, so the rows below still measure the mechanics of a calc binding.
  const calcTarget = resolved ? resolved.name : CALC_NAME;
  const byCalc = await makeLookup(srcPath, LIB_CALC_LOOKUP, libId, calcTarget);
  answer('library.lookup.list-to-library-calc-name-addfield-created', createHead(byCalc),
         `${LIB_CALC_LOOKUP} on '${SRC}' -> the LIBRARY.${calcTarget}, by fields/addfield: ${byCalc.description}`
         + (calcNameHolds ? '' : `. ${calcTarget} did not resolve to the file name, so a bound lookup here labels nothing useful`));
  const calcFormHeld = await formRow('library.lookup.list-to-library-calc-name-form-write',
    LIB_CALC_LOOKUP, byCalc, plainId, FILE_PLAIN);
  const calcFormRow = RESULTS.find((r) => r.id === 'library.lookup.list-to-library-calc-name-form-write');
  if (calcFormHeld || (calcFormRow && calcFormRow.outcome.startsWith('ACCEPTED'))) {
    const reads = await rowReadShapes(formRowId, LIB_CALC_LOOKUP);
    answer('library.lookup.calc-name-bound-row-read-after-write', reads.outcome,
           `items(${formRowId}) after the endpoint accepted ${LIB_CALC_LOOKUP}=${plainId}. ${reads.evidence}`);
  } else {
    answer('library.lookup.calc-name-bound-row-read-after-write', 'NOT ESTABLISHED',
           'the endpoint did not accept a calc-name-bound value on the form row, so there was nothing to read');
  }
  const calcCreateRowId = await createRow('library.lookup.list-to-library-calc-name-create-write',
    LIB_CALC_LOOKUP, byCalc, plainId, FILE_PLAIN);
  await expandRow('library.lookup.list-to-library-calc-name-expand-projects', LIB_CALC_LOOKUP,
    calcFormHeld ? formRowId : calcCreateRowId, calcTarget);

  // ---- The Name-bound lookup, created only now -----------------------------
  const byName = await makeLookup(srcPath, LIB_NAME_LOOKUP, libId, 'FileLeafRef');
  answer('library.lookup.list-to-library-name-addfield-created', createHead(byName),
         `${LIB_NAME_LOOKUP} on '${SRC}' -> the LIBRARY.FileLeafRef, by fields/addfield: ${byName.description}`);
  await wholeRead('library.lookup.whole-item-read-with-name-lookup-column',
    `with ${LIB_NAME_LOOKUP} on the list as well and no value set`);
  const nameMergeHeld = await mergeRow('library.lookup.list-to-library-name-merge-write',
    LIB_NAME_LOOKUP, byName, plainId, FILE_PLAIN);
  nameCreateRowId = await createRow('library.lookup.list-to-library-name-create-write',
    LIB_NAME_LOOKUP, byName, plainId, FILE_PLAIN);
  const nameFormHeld = await formRow('library.lookup.list-to-library-name-form-write',
    LIB_NAME_LOOKUP, byName, plainId, FILE_PLAIN);
  const nameFormRow = RESULTS.find((r) => r.id === 'library.lookup.list-to-library-name-form-write');
  if (nameFormHeld || (nameFormRow && nameFormRow.outcome.startsWith('ACCEPTED'))) {
    const reads = await rowReadShapes(formRowId, LIB_NAME_LOOKUP);
    answer('library.lookup.name-bound-row-read-after-write', reads.outcome,
           `items(${formRowId}) after the endpoint accepted ${LIB_NAME_LOOKUP}=${plainId}. ${reads.evidence}. `
           + 'Before that write the same row answered every read with the Title-bound value held'
           + (calcFormHeld ? ' and the calc-bound one beside it.' : '.'));
  } else {
    answer('library.lookup.name-bound-row-read-after-write', 'NOT ESTABLISHED',
           'the endpoint did not accept a Name-bound value on the form row, so there was nothing to read');
  }

  // ---- The form row on a NEW item ------------------------------------------
  let newFormRowId = null;
  if (!formMethodHolds) {
    answer('library.lookup.list-to-library-new-form-write', 'VOID',
           'the form control did not hold, so a refusal here could not be attributed', 'void');
  } else if (!byName.bound) {
    answer('library.lookup.list-to-library-new-form-write', 'NOT ESTABLISHED',
           `${LIB_NAME_LOOKUP} is not a lookup bound to the library, so there was nothing to set`);
  } else {
    const folder = await spGet(`${srcPath}/RootFolder?$select=ServerRelativeUrl`);
    const folderUrl = folder.ok && folder.body ? folder.body.ServerRelativeUrl : null;
    if (!folderUrl) {
      answer('library.lookup.list-to-library-new-form-write', 'NOT ESTABLISHED',
             `the source list's RootFolder could not be read (HTTP ${folder.status}), so the new-item endpoint had no folder to create in`);
    } else {
      const value = formSpelling === 'id-label' ? `${plainId};#${FILE_PLAIN}` : String(plainId);
      digest = await getDigest();
      const created = await spPost(`${srcPath}/AddValidateUpdateItemUsingPath`, {
        listItemCreateInfo: {
          __metadata: { type: 'SP.ListItemCreationInformationUsingPath' },
          FolderPath: { __metadata: { type: 'SP.ResourcePath' }, DecodedUrl: folderUrl },
        },
        formValues: [
          { FieldName: 'Title', FieldValue: 'dbmlsp libwrite new form row' },
          { FieldName: LIB_NAME_LOOKUP, FieldValue: value },
        ],
        bNewDocumentUpdate: false,
      }, digest, VERBOSE);
      const rows = formRows(created);
      const errors = rows ? formErrors(rows) : null;
      const accepted = created.ok && rows !== null && errors.length === 0;
      const newId = rows ? Number((rows.find((x) => x.FieldName === 'Id') || {}).FieldValue) : NaN;
      const back = Number.isInteger(newId) ? await readBack(srcPath, newId, LIB_NAME_LOOKUP)
        : { ok: false, id: undefined, description: 'no row id in the response to read' };
      const held = accepted && back.ok && back.id === plainId;
      if (held) newFormRowId = newId;
      answer('library.lookup.list-to-library-new-form-write',
             held ? 'HELD'
               : accepted ? (back.ok ? 'ACCEPTED BUT NOT HELD' : 'ACCEPTED, READBACK FAILED')
                 : (created.ok && rows !== null) || isRefusal(created.status) ? 'REFUSED' : 'NOT ESTABLISHED',
             `AddValidateUpdateItemUsingPath on '${SRC}' with ${LIB_NAME_LOOKUP}=${show(value)}: `
             + `HTTP ${created.status}`
             + (!created.ok ? ` ${clip(created.text, 200)}`
               : rows === null ? ', no formValues results in the response'
                 : errors.length ? `, refused by the endpoint: ${errors.join('; ')}` : `, created id ${newId}`)
             + `; ${back.description}`);
    }
  }

  // ---- $expand through the Name-bound lookup --------------------------------
  const expandRowId = nameMergeHeld ? mergeRowId
    : nameFormHeld ? formRowId
      : nameCreateRowId !== null ? nameCreateRowId
        : newFormRowId;
  await expandRow('library.lookup.list-to-library-name-expand-projects', LIB_NAME_LOOKUP, expandRowId, 'FileLeafRef');

  // ---- The pickers, which nobody can read over REST ---------------------------
  answer('library.lookup.calc-name-bound-picker-labels-files',
         byCalc.bound ? 'MANUAL' : 'NOT ESTABLISHED',
         byCalc.bound
           ? `OPEN ${WEB}/Lists/${encodeURIComponent(SRC)}/NewForm.aspx and open the ${LIB_CALC_LOOKUP} `
             + `dropdown. Record how many entries it offers and the exact label of each: file names say `
             + `the calculated column feeds the picker; blanks say it does not. Then pick '${FILE_PLAIN}', `
             + 'save, and record whether the form saved and what the row shows in the list view.'
           : `${LIB_CALC_LOOKUP} was not created, so there is no picker to open`);
  answer('library.lookup.name-bound-picker-labels-files',
         byName.bound ? 'MANUAL' : 'NOT ESTABLISHED',
         byName.bound
           ? `OPEN ${WEB}/Lists/${encodeURIComponent(SRC)}/NewForm.aspx and open the ${LIB_NAME_LOOKUP} `
             + `dropdown. The library holds exactly two files, '${FILE_PLAIN}' (no Title) and `
             + `'${FILE_TITLED}' (Title '${TITLED_TITLE}'). Record how many entries the dropdown offers `
             + 'and the exact label of each. File names as labels say the picker reads FileLeafRef; '
             + `a blank entry says it does not; then pick '${FILE_PLAIN}', save, and record whether `
             + 'the form saved and what the row shows. The candidate set is rendered by the browser '
             + 'and is not exposed over REST, so a machine run cannot answer this.'
           : `${LIB_NAME_LOOKUP} was not created, so there is no picker to open`);

  report();
  log('INFO', `Delete '${SRC}' FIRST, then '${LIB}', then '${TGT}'. A container a lookup points `
    + 'into cannot be removed while the lookup exists.');
})();
