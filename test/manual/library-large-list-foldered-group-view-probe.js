/**
 * dbml-sharepoint PROBE: DOES SCOPING A GROUP-BY TO A FOLDER UNDER 5,000 FILES
 * SERVE IT INSIDE A LIBRARY OVER 5,000, AND DOES A THREE-LEVEL GROUP-BY WORK
 * WHERE NOTHING IS NEAR THE THRESHOLD?
 *
 * REVISION: 32a05b27
 *
 * TWO QUESTIONS, AND THEY ARE DELIBERATELY ASKED IN ONE RUN. Every large-list
 * probe before this one measured a group-by refused past 5,000 and could not
 * say WHY, because two candidate causes were tangled together. The first is
 * SIZE: the container holds more rows than the threshold allows an aggregation
 * over. The second is SHAPE: #481 measured a three-level <GroupBy> refused with
 * a different signature entirely, over an Id-narrowed six-row set where size
 * could not have reached it. This probe separates them with two fixtures built
 * for the purpose and read in the same paste.
 *
 *   FOLDER SCOPE holds the shape constant and changes the size the query is
 *   given. The same single-level <GroupBy> on the same indexed column of the
 *   same library, sent once against the library root (5,256 files) and once
 *   against one folder (1,752 files), in the same pair of requests.
 *   LEVEL DEPTH holds the size constant and changes the shape. One, two and
 *   three levels on a library of 240 files where nothing is near the threshold.
 *
 * WHAT IS ALREADY SETTLED, and is therefore never re-measured here.
 *   #472, `library-index-threshold-probe.js`, run 2026-09-08: past the
 *   threshold a selective OData filter on Id is SERVED, while Title, Name,
 *   Created, Modified, Author and Editor are each REFUSED with
 *   SPQueryThrottledException. Only Id carries a native index. An OData $filter
 *   reports the threshold as an error; the same predicate in CAML returns HTTP
 *   200 with a silently partial answer.
 *   #478, `library-large-list-index-probe.js`, run 2026-09-08: a MERGE of
 *   Indexed=true is accepted on a library already past 5,000 files, and an index
 *   turns a refused filter or sort into a served one, for its own column only.
 *   #479 and #480, run 2026-09-08: a group-by on an unindexed Choice column and
 *   a group-by on Id were both REFUSED with the threshold signature. The default
 *   view rendered its first page. A group-by over an Id-narrowed six-row set was
 *   HONOURED, and Scope="Recursive" and Scope="RecursiveAll" changed none of it.
 *   #481, `library-large-list-multilevel-group-view-probe.js`, run 2026-09-08:
 *   the single-level group-by, re-sent for 176,814 ms with the filter on the
 *   same column interleaved, was REFUSED every time while the filter was SERVED
 *   every time. A THREE-level <GroupBy> came back HTTP 500, code -2147467259,
 *   with NO SPQueryThrottledException, over three field orders AND over an
 *   Id-narrowed six-row set alike. Its two dependent rows went void, because the
 *   control that would have separated the shape from the size was refused too.
 *   #483, `library-large-list-preindex-group-view-probe.js`, run 2026-09-08:
 *   the same refusal on a Choice column indexed at 4,900 files and carried past
 *   the threshold, over 32,582 ms, while the filter on that same index served in
 *   the same request pairs. Writing the index before the crossing does not
 *   change what an aggregation is given.
 *   #485, `library-large-list-modern-view-probe.js`, run 2026-09-09: on the
 *   rendered page the default view SERVES its first page at 5,100 files and the
 *   grouped view on the unindexed column is REFUSED with a threshold banner. It
 *   registered `ui-group-by-indexed-column-folder-scoped` and recorded it OPEN,
 *   because neither flat fixture holds a folder and neither could be given one.
 *
 * So the REST answer at the library root is settled across two fixtures and two
 * index orderings, and the rendered answer is settled for the ungrouped and the
 * unindexed cases. What no run has been able to ask is what a FOLDER does, and
 * whether a three-level grouping fails for its depth or for its container.
 *
 * THE FIXTURES ARE READ. The one thing this probe writes is two views.
 * `library-large-list-foldered-fixture-probe.js` builds and owns both:
 *
 *   'dbmlsp Probe Foldered': 5,256 files named dbmlsp-fld-00001.txt upward,
 *   spread over three root folders 'Alpha-F', 'Beta-F' and 'Gamma-F' holding
 *   1,752 each, carrying PChoice (Choice, Alpha..Delta, from the file number
 *   modulo 4) and PNumber (Number, the file number modulo 1000). PChoice was
 *   MERGEd Indexed=true while the library still held 4,900 files and the count
 *   and moment are stamped into its Description. PNumber is unindexed and stays
 *   that way, because an unindexed column is the only thing that can witness
 *   the throttle. 5,256 is 12 x 438 and 12 is the wrap of the folder and choice
 *   formulas together, so every folder holds exactly 438 files of each PChoice
 *   value. That figure is DERIVED below from the fixture's own formulas rather
 *   than copied in, so a fixture built to a different count reports a different
 *   prediction instead of failing an arithmetic nobody re-checked.
 *
 *   'dbmlsp Probe MultiLevel': 240 files named dbmlsp-ml-00001.txt upward at
 *   the root, no folders and nothing indexed, carrying MChoice (Choice,
 *   Alpha..Delta, modulo 4), MFlag (Yes/No, true when the number is divisible
 *   by 3) and MText (Text, 'mtext-' plus the number modulo 5). The three moduli
 *   are pairwise coprime, so each level cuts what the level above it left and
 *   every combination of the three values is non-empty.
 *
 * WHAT THE VIEW WRITE COULD BREAK, AND THE CONTROL THAT WATCHES IT. The
 * foldered fixture's resume read takes the newest few rows ordered by Id and
 * walks them newest-first, taking the first whose name is one of its files,
 * skipping a row named after one of the three folders, and FAILING CLOSED on
 * anything else. So anything this probe adds to that item collection would make
 * a 5,256-file fixture, many pastes of work, unverifiable by its owner. #485
 * measured that an AddView does not touch it, on the other library. That is
 * evidence about a different container, so the newest file name is read here
 * before the views are created and again afterwards and the two are compared.
 *
 * HOW A FOLDER SCOPE IS SENT, and every part of it is inherited rather than
 * guessed. `library-view-interaction-probe.js`, run 2026-09-08:
 * FolderServerRelativeUrl is a property of RenderListDataParameters, NOT an
 * attribute of <View>, so the folder travels beside the ViewXml rather than
 * inside it. A filter, a group-by and a folder scope applied together return
 * the rows satisfying all three, and a filter invoked with a folder parameter
 * filters inside that folder rather than across the library.
 *
 * NO Scope ATTRIBUTE IS SENT WITH THE FOLDER PARAMETER, and that is a decision
 * rather than an omission. "View element (List)" documents Scope="FilesOnly",
 * "Recursive" and "RecursiveAll", and documents that its ABSENCE displays only
 * the files and subfolders of a specific folder, which is exactly the scoping
 * this probe is asking about. Nothing has measured what a tenant does when the
 * folder parameter and a Scope attribute are BOTH set, and
 * `library-view-interaction-probe.js` says so in its own header. The fixture's
 * files sit directly inside the three folders with no nesting below them, so
 * the default scope reaches every file the question is about and the untested
 * precedence is not entangled with the measurement.
 *
 * THE FOLDER PATH IS READ, NEVER DERIVED. A library's server-relative address
 * is not a function of its title: it is frozen at creation and a later rename
 * does not move it. So the path is read from the library's own RootFolder and
 * the folder name is appended to that, which is the shape
 * `library-view-interaction-probe.js` used. This matters more than it looks:
 * that probe also measured that a folder read can answer HTTP 200 for a folder
 * that could not have been there, and a parameter SharePoint IGNORES answers
 * the same rows as one it never received. A wrong path would therefore return
 * the whole library and read as a folder scope that failed to narrow, which is
 * one of the two answers this probe exists to distinguish. So the folder scope
 * is PROVED to narrow, on an ungrouped query, before any grouped row is read.
 *
 * THE PREDICTED COUNTS ARE CORROBORATION AND NEVER THE OUTCOME. Each folder
 * holds 438 files of each PChoice value, and that number is worth reading back
 * off a served aggregation. It is not what the row PASSES on. Whether a
 * folder-scoped group-by is honoured, ignored or refused is the OBSERVATION,
 * and a probe that failed its own crux row because a refused query returned no
 * counts would kill the experiment at the moment it started working. The
 * verdict is HONOURED against IGNORED against REFUSED, read off server-produced
 * group markers, and the 438 is quoted beside it.
 *
 * WHY THE ROOT AND THE FOLDER ARE INTERLEAVED. A root query read at 09:00 and a
 * folder query read at 09:03 cannot say the folder was the variable. So each
 * attempt sends the folder-scoped grouped query and then immediately the
 * root-scoped one, identical in every other respect, and each pair is recorded
 * with the elapsed time it was taken at. That is the shape #481 used to separate
 * an index that had not built from an index that does not serve an aggregation,
 * pointed at the one difference this probe is about.
 *
 * WHY THE THREE-LEVEL ROW IS A SUBJECT AND THE SINGLE-LEVEL ROW IS ITS CONTROL.
 * A control that fails voids what depends on it, so the two must not be spelled
 * the same way. #481 measured a three-level <GroupBy> refused on the flat
 * library even Id-narrowed, so a refusal on 240 files is a RESULT rather than a
 * broken instrument, and it is the result that would settle the question: a
 * shape the query engine rejects before size is consulted. What has to work for
 * that reading to mean anything is a SINGLE-level group-by on the same small
 * library, which is `control-multilevel-single-level-honoured`. Without it a
 * three-level refusal could be this library, this column set or this caller.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED.
 *   Depends on (asserted, read back): both fixture libraries are present and
 *   hold the counts their contract gives, counted from the newest file name;
 *   each folder holds fewer than 5,000 files while the library holds more;
 *   PChoice reads Indexed=true with a stamp naming a count below 5,000 and
 *   PNumber reads Indexed=false; the small library is still under the threshold;
 *   an OData filter on Id is served and one on PNumber is refused WITH the
 *   throttle signature; a rendered query naming an absent column is refused
 *   WITHOUT it; the folder path reads back and an ungrouped folder-scoped query
 *   returns only files that folder holds; a single-level group-by is honoured
 *   over an Id-narrowed row set on the large library and over the whole small
 *   one; both created views read back carrying the grouping they were sent; the
 *   newest file name is unchanged by those writes; and the capture browser
 *   renders a modern library page under the threshold.
 *   Observes (recorded, never asserted): whether the folder-scoped group-by is
 *   honoured, ignored or refused, and with what labels and counts; whether the
 *   root-scoped one differs from it in the same pair; how many collapsed rows a
 *   RowLimit of 100 returns and what their group counts read; whether two and
 *   three levels serve on the small library and how many leaf combinations come
 *   back; how many <FieldRef> children a three-level view stores; what each
 *   refusal body says; and what the rendered pages show. NOTHING here asserts
 *   that a folder scope lifts anything. A run in which every grouped query is
 *   refused is a successful run and it says the threshold is a property of the
 *   LIST rather than of the row set a query is pointed at.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. All of it files under `library.large-list`.
 * Six fixture ids are already registered by the fixture probe and are kept,
 * because the question and the method are the same and one question takes one
 * id however many probes answer it. Two more are kept from #485: the capture
 * control is about the browser rather than about either library, and
 * `ui-group-by-indexed-column-folder-scoped` is the row that probe registered
 * and recorded OPEN for want of exactly this fixture. Answering it under a new
 * name would leave the enumeration looking like two questions.
 *
 *   library.large-list.fixture-foldered-file-count
 *        Does the large library hold its contract count, from the newest file
 *        name rather than from ItemCount?
 *   library.large-list.fixture-foldered-folder-counts
 *        Does each folder hold fewer than 5,000 files while the library holds
 *        more, which is the whole inequality this probe measures against?
 *   library.large-list.fixture-foldered-index-written-under-threshold
 *        Does PChoice read Indexed=true with the stamp saying the flag was
 *        written below 5,000 files?
 *   library.large-list.fixture-foldered-witness-unindexed
 *        Does PNumber read Indexed=false, so the throttle has a witness?
 *   library.large-list.fixture-multilevel-file-count
 *        Does the small library hold its contract count?
 *   library.large-list.fixture-multilevel-under-threshold
 *        Is the small library still under the threshold, which is the only
 *        reason a level-depth reading on it means anything?
 *   library.large-list.control-foldered-id-query-served
 *        POSITIVE CONTROL: is a selective OData filter on Id served past the
 *        threshold, so a served answer is observable on this library at all?
 *   library.large-list.control-foldered-unindexed-filter-refused
 *        NEGATIVE CONTROL: is a selective filter on the unindexed PNumber
 *        refused WITH the throttle signature, so the threshold is demonstrably
 *        being enforced here?
 *   library.large-list.control-foldered-render-where-absent-refused
 *        NEGATIVE CONTROL: is a rendered query whose <Where> names a column the
 *        library does not hold refused WITHOUT the throttle signature?
 *   library.large-list.control-foldered-folder-path-narrows
 *        CONTROL: does the folder parameter actually NARROW anything? An
 *        ungrouped query pointed at one folder must return only files that
 *        folder's own numbering gives it. A parameter SharePoint ignores
 *        answers the same rows as one it never received.
 *   library.large-list.control-foldered-group-by-narrowed-honoured
 *        POSITIVE CONTROL: is a single-level <GroupBy> on PChoice honoured once
 *        a <Where> on Id has narrowed the rows to a handful, so a refusal at
 *        size is about the size rather than about the request?
 *   library.large-list.foldered-group-by-root-scoped
 *        The anchor: is the single-level group-by on PChoice refused at the
 *        library root, as #480, #481 and #483 each measured on a flat library?
 *   library.large-list.foldered-group-by-folder-scoped
 *        THE CRUX: is that same group-by honoured, ignored or refused when the
 *        query is pointed at one folder holding 1,752 files? Asked of two
 *        folders, so a served answer on one is not a property of one folder.
 *   library.large-list.foldered-group-by-folder-scoped-counts
 *        Where it serves, how many collapsed rows come back against a RowLimit
 *        of 100, and do their group counts read the 438 the fixture's formulas
 *        give, or the library-wide figure, or something else?
 *   library.large-list.foldered-group-by-refusal-signature
 *        Does every refusal this run collects carry SPQueryThrottledException,
 *        or does one carry something else?
 *   library.large-list.control-multilevel-single-level-honoured
 *        POSITIVE CONTROL: is a ONE-level <GroupBy> honoured on the small
 *        library, so the level-depth rows below are about depth?
 *   library.large-list.multilevel-group-by-two-levels
 *        Do TWO levels serve on 240 files, and do the groups carry the counts
 *        the wrap arithmetic gives?
 *   library.large-list.multilevel-group-by-three-levels
 *        Do THREE levels serve where nothing is near the threshold, and do all
 *        the leaf combinations appear? #481 got HTTP 500 with code -2147467259
 *        and no threshold signature for this shape on a six-row set.
 *   library.large-list.fixture-foldered-ui-views-created
 *        Do both views exist and read back carrying the grouping they were
 *        sent, and how many levels did a three-level query actually store?
 *   library.large-list.control-ui-foldered-fixture-readable-after-view-writes
 *        CONTROL: is the newest file name the same after the view writes as
 *        before them, so the fixture's owner can still resume and verify it?
 *   library.large-list.control-ui-foldered-default-view-unchanged
 *        CONTROL: is each library's default view the one it was before?
 *   library.large-list.control-ui-modern-renders-below-threshold
 *        CONTROL: does this browser render a modern document library page at
 *        all, on a library UNDER the threshold?
 *   library.large-list.control-ui-foldered-page-identity
 *        CONTROL: does the rendered page say, in its own JavaScript context,
 *        which of the two fixture libraries it belongs to?
 *   library.large-list.control-ui-folder-scope-rendered
 *        CONTROL: is the rendered page showing ONE folder? Read from the file
 *        names on the page, mapped to folders by the fixture's own formula,
 *        which is a fact about the fixture that no UI update can rename.
 *   library.large-list.ui-group-by-indexed-column-folder-scoped
 *        THE RENDERED CRUX, and the row #485 registered and left open: does the
 *        modern page render a grouped view scoped to a folder under 5,000 files
 *        inside a library over 5,000?
 *   library.large-list.ui-group-by-multilevel-renders
 *        Does the modern page render three group levels on the small library?
 *   library.large-list.ui-threshold-banner-text
 *        What does the rendered refusal say, where one appears?
 *
 * HOW TO RUN. Four pastes, one per state, and the probe prints the URL for each.
 *   1. Open the site holding both fixtures. If they are not built, run
 *      library-large-list-foldered-fixture-probe.js with BUILD_FIXTURE true
 *      until its rows read PASS. This probe builds nothing and repairs nothing.
 *   2. STATE = 0, CONFIRMED = true, ALLOW_WRITES = true. Paste on any page of
 *      that site. It reads both fixtures, sends every REST question, creates the
 *      two views, re-checks the fixture and prints the URL for every state
 *      below. Expect a minute or two, most of it the bounded re-send.
 *   3. STATE = 1, CONFIRMED = true. Open a document library on this site holding
 *      AT LEAST ONE file and fewer than 5,000, let it finish rendering, then
 *      paste. An empty library renders no file row however well the browser
 *      works, so it cannot answer this control. It comes first on purpose.
 *   4. STATE = 2. Open the grouped view the setup printed and navigate INTO the
 *      folder it names. The address the setup prints for this is a CANDIDATE:
 *      nothing in this repository has measured which query parameter a modern
 *      library page takes a folder on, so if it does not land, click into the
 *      folder by hand and switch to the view by hand. The probe reads which
 *      folder rendered off the file names rather than off the address.
 *   5. STATE = 3. Open the three-level view on the small library, then paste.
 *   6. Screenshot every state and copy each RESULTS block back verbatim. One
 *      paste answers one state; the rows it did not reach print NOT REACHED and
 *      that is what they are. Anything merging the four transcripts must KEEP
 *      THE FIRST SETTLED VALUE for a row and never let a later leg's NOT
 *      REACHED overwrite it.
 *
 * WHEN FINISHED: re-paste with STATE = 0, CLEANUP = true, CONFIRMED = true and
 * ALLOW_WRITES = true to remove the two views. Leave both libraries, their
 * files, their folders and PChoice's index exactly as they are. An operator who
 * clears that index has destroyed the only thing that distinguishes this library
 * from the flat ones, and it cannot be put back without rebuilding from empty.
 *
 * SCOPE OF CLAIMS: one tenant, two libraries, one caller identity, one browser,
 * one moment. The threshold is documented as an effective figure rather than a
 * constant, and the negative controls are what detect a fixture sitting too
 * close to it.
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
 *   Pointing that read at one folder:
 *     "RenderListDataParameters.FolderServerRelativeUrl Property"
 *   The `<Query>` children, in the order the syntax block gives them:
 *     "Query element (List)"
 *   Grouping a query, and the `Collapse` and `GroupLimit` attributes:
 *     "GroupBy element (Query)"
 *   The `Scope` attribute of `<View>` and what its absence displays:
 *     "View element (List)"
 *   The comparison, its operands and the `Type` attribute of a value:
 *     "Geq element (Query)", "FieldRef element (Query)", "Value element (Query)"
 *   The threshold and the index model:
 *     https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 * Whether a folder scope changes what an aggregation is given is NOT taken from
 * any of those. It is the thing being measured.
 *
 * STATUS: NOT YET RUN. Authored against the merged findings of #472, #478, #479,
 * #480, #481, #483 and #485 and against the fixture contract of #489. Nothing
 * below has been observed on a live site, and the finding lines are inherited or
 * about method until it has.
 */
// finding: foldered-group-view-writes-two-views-and-nothing-else - this probe
// sends no MERGE, no field create, no file upload and no item write. It creates
// one view on each fixture library and removes them again on request. The index
// on PChoice was written below 5,000 files during the fixture build and cannot
// be re-created without rebuilding the library from empty, because writing it
// again at 5,256 files produces the post-hoc index #481 already measured.
// finding: foldered-group-view-the-folder-travels-beside-the-viewxml - inherited
// from library-view-interaction-probe.js, run 2026-09-08: FolderServerRelativeUrl
// is a property of RenderListDataParameters and not an attribute of <View>, so a
// folder scope cannot be expressed in ViewXml at all. Every folder-scoped query
// here puts it in the parameters object beside ViewXml.
// finding: foldered-group-view-no-scope-attribute-with-the-folder - "View
// element (List)" documents that the ABSENCE of Scope displays only the files
// and subfolders of a specific folder, which is the scoping under measurement.
// Nothing has measured what a tenant does when the folder parameter and a Scope
// attribute are both set, and library-view-interaction-probe.js records that gap
// in its own header. The fixture's files sit directly in the three folders with
// nothing nested below, so the default scope reaches every file the question is
// about and the untested precedence is left out of the measurement.
// finding: foldered-group-view-the-folder-path-is-read-never-derived - a
// library's server-relative address is frozen at creation and a rename does not
// move it, so it is read from the library's own RootFolder and the folder name
// appended. library-view-interaction-probe.js also measured, run 2026-09-08,
// that a folder read can answer HTTP 200 for a folder that could not have been
// there, and that a parameter SharePoint ignores answers the same rows as one it
// never received. A wrong path would therefore return the whole library and read
// as a folder scope that did not narrow, which is one of the two answers this
// probe exists to tell apart. control-foldered-folder-path-narrows proves the
// narrowing on an UNGROUPED query before any grouped row is read.
// finding: foldered-group-view-the-predicted-count-is-corroboration - each
// folder holds exactly 438 files of each PChoice value, derived here from the
// fixture's own formulas rather than copied in. That number is read back off a
// served aggregation and quoted, and it is NOT what any row passes on. The
// verdict is HONOURED against IGNORED against REFUSED. A probe that failed its
// crux because a refused query returned no counts would kill the experiment at
// the moment it started working, which is the failure mode AGENTS.md names.
// finding: foldered-group-view-a-group-by-is-never-refused-for-its-column -
// inherited from library-grouping-probe.js, first live run 2026-09-08: a
// <GroupBy> naming a column that does not exist returned HTTP 200 with flat
// rows. That is what makes "accepted" meaningless and the honoured/ignored pair
// the discriminator. A THROTTLE is a different refusal and carries the threshold
// signature in the body, which is why the render-where-absent control exists.
// finding: foldered-group-view-collapsed-rows-carry-no-file-name - inherited
// from library-grouping-probe.js, second live run 2026-09-08: a collapsed
// query's rows did not carry the FileLeafRef its ViewFields named. Nothing here
// reads a file name off a collapsed row, and the folder-narrowing control is
// therefore taken on an UNGROUPED query, which is the only kind whose rows carry
// the names the check needs.
// finding: foldered-group-view-root-and-folder-in-one-pair - readings taken
// minutes apart cannot say the folder was the variable. Each attempt sends the
// folder-scoped grouped query and then immediately the root-scoped one,
// identical in every other respect, and each pair carries the elapsed time it
// was taken at. #481 used the same shape to separate an index that had not built
// from an index that does not serve an aggregation.
// finding: foldered-group-view-three-levels-is-a-subject-not-a-control - #481,
// run 2026-09-08: a three-FieldRef <GroupBy> returned HTTP 500 with code
// -2147467259 and NO SPQueryThrottledException, over three field orders and over
// an Id-narrowed six-row set alike, and the two rows depending on it went void.
// A refusal on 240 unindexed files is therefore a RESULT and not a broken
// instrument, so nothing declares a dependency on it. What the depth rows do
// depend on is control-multilevel-single-level-honoured, one level on the same
// small library, which is what separates the depth from the container.
// finding: foldered-group-view-viewfields-name-only-the-measured-columns - a
// grouped query that also projects an unindexed column could be refused for the
// projection rather than for the grouping, and the two are indistinguishable in
// the body. Every grouped query here names FileLeafRef and the grouped columns
// and nothing else. That is the rule #483 set after #481 sent an unindexed
// Number column on every grouped query, which was harmless only because every
// answer there was a refusal.
// finding: foldered-group-view-a-view-write-could-break-a-resume-read - the
// foldered fixture's resume read walks the newest few rows, skips the three
// folders and fails closed on a name its pattern does not match, so a probe that
// added an item to that collection would leave many pastes of work unverifiable
// by its owner. #485 measured that an AddView does not touch it, on a DIFFERENT
// library, so the newest file name is read before and after the two writes here
// and compared rather than assumed to be safe.
// finding: foldered-group-view-a-stored-view-may-hold-fewer-levels-than-sent -
// nothing in this repository has measured how many <FieldRef> children a
// SharePoint view stores from a three-level <GroupBy>. The view is therefore
// READ BACK and the surviving level count is reported, so a rendered page
// showing two levels is read as a view that stored two rather than as a page
// that rendered two of three.
// finding: foldered-group-view-the-blank-grid-ambiguity - inherited from #485: a
// modern list page that renders nothing and one refusing to render past 5,000
// produce the same screenshot, and view-aggregations-probe.js provisions its own
// fixture classic because the modern list web part did not render under the
// capture browser. The capture control reads the same instrument on a library
// under the threshold and every rendered row depends on it. It refuses an EMPTY
// library, which has no file row to render however well the browser works.
// finding: foldered-group-view-which-folder-rendered-is-read-from-the-names -
// nothing here has measured which query parameter a modern library page takes a
// folder on, so the address the setup prints is a candidate and the operator may
// have to navigate by hand. The page's own file names are the instrument
// instead: a file's number gives its folder by the fixture's formula, which is a
// fact about the fixture that no UI update can rename, so a page whose rendered
// names all map to one folder is showing that folder.
// finding: foldered-group-view-banner-phrases-are-english-and-say-so -
// inherited from #485: view-edit-page-probe.js run 1, 2026-08-17, measured
// _spPageContextInfo.currentUICultureName reading "en-US" while the page's
// <html lang> read "en-AU", so the two disagree and only the first governs which
// language a message arrives in. The culture is printed beside every phrase
// scan, and on a non-English tenant an absent phrase means nothing at all.
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
  log('INFO', 'probe revision 32a05b27. Quote this when reporting results.');

  // ---- Operator settings -------------------------------------------------
  // Which leg of the run this paste is. One paste answers one state, because a
  // pasted script cannot navigate the page it is running in and come back.
  //
  //   0  SETUP AND EVERY REST QUESTION. Reads both fixtures, sends the folder
  //      and level-depth queries, creates the two views, re-checks the fixture
  //      and prints the URL for every state below. Needs CONFIRMED, and
  //      ALLOW_WRITES for the two views alone.
  //   1  CONTROL. Paste on a rendered library page holding AT LEAST ONE file
  //      and fewer than 5,000. Establishes that this browser renders a modern
  //      library at all. An empty library cannot: it has no row to render.
  //   2  The grouped view on the large library, opened INSIDE one folder.
  //   3  The three-level view on the small library.
  const STATE = 0;
  // ------------------------------------------------------------------------

  // ---- The fixture contract, restated ------------------------------------
  // Owned by library-large-list-foldered-fixture-probe.js. Read, never built,
  // never repaired, never cleared. Changing any of these reads a different
  // library rather than adjusting this one.
  const LIB = 'dbmlsp Probe Foldered';
  const FOLDERS = ['Alpha-F', 'Beta-F', 'Gamma-F'];
  const CHOICE = 'PChoice';
  const NUMBER = 'PNumber';
  const CHOICES = ['Alpha', 'Beta', 'Gamma', 'Delta'];
  const TARGET_FILES = 5256;
  const FILE_NUMBER = /dbmlsp-fld-(\d+)\.txt$/;
  // The same stem as it appears anywhere in rendered page text. This is how a
  // rendered row is counted and how the rendered folder is identified: a fact
  // about the fixture rather than about the renderer.
  const FILE_IN_TEXT = /dbmlsp-fld-(\d{5})\.txt/g;
  // The stamp the fixture's indexing pass left on PChoice's Description.
  // Indexed=true on its own cannot say WHEN it was written, and when is what
  // separates this library from the post-hoc case #481 measured.
  const STAMP_RE = /dbmlsp foldered: Indexed:true written at (\d+) file\(s\) on (\S+)/;

  const SMALL = 'dbmlsp Probe MultiLevel';
  const SMALL_FILES = 240;
  const M_CHOICE = 'MChoice';
  const M_FLAG = 'MFlag';
  const M_TEXT = 'MText';
  const SMALL_NUMBER = /dbmlsp-ml-(\d+)\.txt$/;
  const SMALL_IN_TEXT = /dbmlsp-ml-\d{5}\.txt/g;
  // The three levels, in the order the brief asks them: the coarsest cut first,
  // so each level partitions what the level above it left.
  const LEVELS = [M_CHOICE, M_FLAG, M_TEXT];

  // ---- Thresholds and page sizes -----------------------------------------
  // More than the documented 5,000, so every query on the large library is
  // asked past it.
  const FLOOR = 5001;
  const THRESHOLD = 5000;
  // The capture control needs a library that has something to render. An empty
  // one shows a header row and nothing else, which is the same picture as a
  // browser that renders no modern list at all.
  const CONTROL_FLOOR = 1;
  // How far the file count may drift from the contract before the run refuses.
  // Zero: the fixture probe builds to an exact number and verifies it, so any
  // drift at all is a fixture that is not the one this probe was written for.
  const COUNT_TOLERANCE = 0;
  // Well below any page ceiling, so a query that fills the page is visibly
  // uncounted rather than quietly rounded.
  const PAGE = 100;
  // The same figure for a rendered view, and for the same reason. The brief
  // asks the collapsed folder-scoped question at exactly this limit.
  const ROW_LIMIT = 100;
  // The two strings a throttled query comes back with, and each on its own.
  // THROTTLE classifies a response; the two halves answer the signature
  // question, which is about which of them a refusal actually carried.
  const THROTTLE_EXCEPTION = /SPQueryThrottledException/;
  const THRESHOLD_PROSE = /exceeds the list view threshold/i;
  const THROTTLE = /exceeds the list view threshold|SPQueryThrottledException/i;
  // A column name neither library holds, for the negative controls.
  const ABSENT_COLUMN = 'PNoSuchColumnAtAll';
  // The keys an honoured group-by carries, named rather than matched on the
  // column name: a /group/i test over a label key would report a grouping that
  // is only a coincidence of spelling.
  const GROUP_MARKER = /\.COUNT\.group$|\.newgroup$|\.groupindex$/;
  // How far back from the newest item id the narrowed control's <Where> reaches.
  // Small enough that the grouping runs over a handful of rows, and the row
  // count is READ rather than predicted: item ids need not be contiguous, and on
  // this library the three folder rows are items too.
  const GUARD_SPAN = 5;
  // Both documented spellings for a counter value, tried in turn: a
  // <Value Type=...> spelled wrongly comes back as a rejected request, which is
  // the same shape as the refusal that would be the finding.
  const ID_VALUE_TYPES = ['Counter', 'Integer'];
  // The bounded re-send. NOT an index-build wait: this probe writes no index and
  // the flag is as old as the fixture build. It is there so the crux is not a
  // single sample and so each attempt can pair the folder against the root.
  const PAIR_ATTEMPTS = 3;
  const PAIR_WAIT_MS = 8000;
  // The two folders the crux is asked of. One served folder could be a property
  // of that folder; two is a symmetry.
  const SCOPED_FOLDERS = [FOLDERS[0], FOLDERS[1]];

  // ---- What this probe creates -------------------------------------------
  // One view a person would actually make on each library. The titles are exact
  // and the cleanup path refuses anything else, so a mistyped or stale CLEANUP
  // cannot reach a view this probe did not create.
  const VIEW_FOLDERED = 'Foldered By PChoice';
  const VIEW_MULTILEVEL = 'MultiLevel By Three';
  const VIEW_ROW_LIMIT = 100;
  const GROUP_LIMIT = 100;

  // ---- Rendered-page markers ---------------------------------------------
  // Candidates, in both directions, all reported. The classic side is ASP.NET
  // WebForms rather than SharePoint: a WebForms page carries one server-side
  // form and control ids built from the page's control tree. A page carrying
  // none of these is not being served by that renderer, which is a stronger
  // statement than any modern marker being present.
  const CLASSIC_MARKERS = [
    'form#aspnetForm',
    '[id^="ctl00_"]',
    '#s4-workspace',
    '#onetidDoclibViewTbl0',
  ];
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
  const lit = (value) => String(value).replace(/'/g, "''");
  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));
  const clip = (text, length) => String(text === undefined ? '' : text).slice(0, length);
  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const uniq = (values) => values.filter((value, at) => values.indexOf(value) === at);
  const guid = (value) => String(value === null || value === undefined ? '' : value)
    .replace(/[{}]/g, '').toLowerCase();

  const pathOf = (title) => `web/lists/getbytitle('${odataName(title)}')`;
  const libPath = pathOf(LIB);
  const smallPath = pathOf(SMALL);
  const fieldPath = (list, name) =>
    `${list}/fields/getbyinternalnameortitle('${odataName(name)}')`;

  // ---- The fixture's own formulas, as functions ---------------------------
  // Every predicted number below is DERIVED from these rather than written in,
  // so a fixture built to a different count reports a different prediction
  // instead of failing an arithmetic nobody re-checked. They are the formulas
  // library-large-list-foldered-fixture-probe.js uploads by, restated.
  const folderOf = (n) => FOLDERS[n % FOLDERS.length];
  const choiceOf = (n) => CHOICES[n % CHOICES.length];
  const mChoiceOf = (n) => CHOICES[n % CHOICES.length];
  const mFlagOf = (n) => n % 3 === 0;
  const mTextOf = (n) => `mtext-${n % 5}`;

  const tally = (upTo, predicate) => {
    let total = 0;
    for (let n = 1; n <= upTo; n += 1) if (predicate(n)) total += 1;
    return total;
  };

  // ---- Reading instruments ------------------------------------------------
  // No $select on a field read, for the reason native-index-probe.js records:
  // one unrecognised name errors the whole request, and every column would then
  // read as unreadable rather than as missing one property.
  const readField = async (list, name) => spGet(fieldPath(list, name));

  // The newest file NAME, never ItemCount, ordered on Id, which #472 measured to
  // be the one ordering a library past the threshold serves. A FOLDER is an item
  // too, so this takes a page of rows and walks it newest-first, skipping a row
  // named after one of this fixture's folders and failing closed on anything
  // else. That is the read the fixture probe's own resume uses.
  const newestFile = async (list, pattern, skippable) => {
    const read = await spGet(
      `${list}/items?$select=Id,FileLeafRef&$orderby=Id desc&$top=${FOLDERS.length + 5}`);
    if (readFailed(read) || !Array.isArray(read.body.value)) {
      return { ok: false, number: 0, name: null, id: null,
               why: `the newest items could not be read (HTTP ${read.status})` };
    }
    const rows = read.body.value;
    if (rows.length === 0) {
      return { ok: true, number: 0, name: null, id: null, why: 'the library is empty' };
    }
    for (const row of rows) {
      const name = String(row.FileLeafRef || '');
      const digits = name.match(pattern);
      if (digits) {
        return { ok: true, number: Number(digits[1]), name, id: row.Id,
                 why: `${name} is the newest file this fixture put there` };
      }
      if (!skippable.includes(name)) {
        return { ok: false, number: 0, name, id: null,
                 why: `the newest item is named ${show(name)}, which is neither one of this `
                   + "fixture's files nor one of its folders, so the library holds something the "
                   + 'fixture probe did not put there' };
      }
    }
    return { ok: false, number: 0, name: null, id: null,
             why: `all ${rows.length} newest rows are folders, so this library holds no file` };
  };

  // Every refusal a query in this run came back with, kept whole so the
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
  const askQuery = async (list, query, label) => {
    const r = await spGet(`${list}/items?$select=Id&$top=${PAGE}&${query}`);
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
  const askFilter = (list, filter) =>
    askQuery(list, `$filter=${encodeURIComponent(filter)}`, `$filter=${filter}`);

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

  // ---- Reading a rendered view --------------------------------------------
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
  // (List)" gives them. NO Scope attribute is ever emitted: see the no-scope
  // finding. The DEFAULT ViewFields names FileLeafRef and the grouped columns
  // alone; the absent-column controls pass their own `fields`, so a column that
  // does not exist is named ONLY in the clause under measurement and never in
  // <ViewFields>, where a refusal would be about the wrong clause.
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

  // The folder travels in the parameters object beside ViewXml, never inside it.
  // See the folder-parameter finding.
  const askView = async (list, opts) => {
    const xml = viewXmlFor(opts);
    const parameters = { ViewXml: xml };
    if (opts.folder) parameters.FolderServerRelativeUrl = opts.folder;
    const digest = await getDigest();
    const res = await spPost(`${list}/RenderListDataAsStream`, { parameters }, digest);
    return {
      res,
      rows: rowsOf(res),
      xml,
      folder: opts.folder || null,
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

  // The group SIZES the server put on the collapsed rows, read off the
  // `<Field>.COUNT.group` key rather than counted here. A probe that sorted flat
  // rows into buckets by reading each row's value would have measured its own
  // arithmetic.
  const countsFor = (rows, field) => rows.map((row) => {
    const key = `${field}.COUNT.group`;
    return { label: field in row ? row[field] : undefined,
             count: key in row ? row[key] : undefined };
  });

  // The file names a query returned, server-produced and read only off rows that
  // carry one. A collapsed row does not, so this is used on ungrouped queries.
  const namesOf = (rows) => rows
    .map((row) => String(row.FileLeafRef === undefined ? '' : row.FileLeafRef))
    .filter((name) => name.length > 0);

  // Everything the SERVER said about one grouping, and nothing this probe worked
  // out for itself.
  const observeGroup = async (list, opts) => {
    const grouped = groupFields(opts);
    const label = opts.label || `group-by on ${grouped.join(' then ')}`;
    const collapsed = await askView(list, { ...opts, collapse: 'TRUE' });
    const expanded = await askView(list, { ...opts, collapse: 'FALSE' });
    const flat = await askView(list, { ...opts, groupBy: null });
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
      folder: collapsed.folder,
      text: `collapsed HTTP ${collapsed.res.status} returned ${collapsed.rows.length} row(s) `
        + `against a RowLimit of ${ROW_LIMIT}, labels ${clip(show(labels), 300)}, grouping `
        + `markers ${clip(show(markers), 240)}, first row `
        + `${clip(show(collapsed.rows.length ? collapsed.rows[0] : null), 300)}; expanded HTTP `
        + `${expanded.res.status} returned ${expanded.rows.length} row(s); the same query with no `
        + `<GroupBy> returned HTTP ${flat.res.status} with ${flat.rows.length} row(s); folder `
        + `parameter ${show(collapsed.folder)}; ViewXml ${clip(collapsed.xml, 320)}`
        + (collapsed.res.ok ? '' : `; collapsed body ${clip(collapsed.res.text, 220)}`),
    };
  };

  // The bounded re-send, with the ROOT-scoped query sent immediately after each
  // folder-scoped attempt. That pairing is what makes the folder the variable.
  // `also` may be null, for a reading with nothing to interleave.
  const pairedReadings = async (list, opts, also) => {
    const started = Date.now();
    const legs = [];
    let attempts = 0;
    let last = null;
    let lastAlso = null;
    while (attempts < PAIR_ATTEMPTS) {
      if (attempts) await sleep(PAIR_WAIT_MS);
      last = await observeGroup(list, opts);
      lastAlso = also === null ? null : await also();
      attempts += 1;
      legs.push({
        atMs: Date.now() - started,
        scoped: last.verdict,
        root: lastAlso === null ? null : lastAlso.verdict,
      });
      log('INFO', `  attempt ${attempts}/${PAIR_ATTEMPTS} at ${Date.now() - started} ms: `
        + `folder-scoped ${last.verdict}`
        + (lastAlso === null ? '' : `, root-scoped ${lastAlso.verdict}`));
      if (last.collapsed.res.ok || last.collapsed.transient) break;
    }
    return { seen: last, root: lastAlso, legs, attempts, waitedMs: Date.now() - started };
  };

  const legNote = (legs) => legs
    .map((leg) => `at ${leg.atMs} ms folder-scoped ${leg.scoped}`
      + (leg.root === null ? '' : `, root-scoped ${leg.root}`))
    .join('; ');

  // ---- DOM instruments ----------------------------------------------------
  // Reported, never asserted. Each returns what it FOUND, and every verdict is
  // formed from a combination so that one renamed marker costs a row rather than
  // the run.

  // innerText needs layout and textContent does not, so a page that laid out and
  // one that only parsed are distinguishable here rather than silently
  // equivalent. Which one was used is part of the evidence.
  const pageText = () => {
    const laid = document.body ? String(document.body.innerText || '') : '';
    if (laid.trim().length) return { text: laid, source: 'innerText' };
    const parsed = document.body ? String(document.body.textContent || '') : '';
    return { text: parsed,
             source: parsed.trim().length ? 'textContent (innerText was empty)' : 'nothing' };
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
    return { verdict, classicSeen, modernSeen,
      detail: `classic candidates ${JSON.stringify(classic)}; `
        + `modern candidates ${JSON.stringify(modern)}` };
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

  // Count the fixture's own file names in the rendered text, and map each one to
  // the folder its own number gives it. `role="row"` is reported beside it and
  // is never the verdict on its own, because a column header is a row too.
  const rowScan = (pattern) => {
    const seen = pageText();
    const found = seen.text.match(pattern) || [];
    const distinct = uniq(found);
    return { fileNames: distinct.length, sample: distinct.slice(0, 4), names: distinct,
      roleRows: countOf('[role="row"]'), roleGrids: countOf('[role="grid"]'),
      textSource: seen.source, textLength: seen.text.length };
  };

  // Which folders the rendered file names belong to, by the fixture's own
  // formula. See the which-folder finding: this is the instrument, not the
  // address bar.
  const foldersRendered = (names) => {
    const seen = {};
    for (const name of names) {
      const digits = name.match(/dbmlsp-fld-(\d{5})\.txt/);
      if (!digits) continue;
      const folder = folderOf(Number(digits[1]));
      seen[folder] = (seen[folder] || 0) + 1;
    }
    return seen;
  };

  // A group HEADER is one leaf element reading "<label> (<count>)". A leaf whose
  // text IS the bare label is a column CELL in a file row, which #485 matched by
  // accident, so the two are read apart: the header shape is the verdict and the
  // bare-label hits are reported beside it. The count is captured as SHOWN,
  // digits and any trailing "+", because "(100+)" is a group limit reached
  // rather than a group size.
  const escapeRe = (text) => String(text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
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
    const leaves = [];
    for (const node of document.querySelectorAll('*')) {
      if (node.children.length) continue;
      leaves.push(clip(String(node.textContent || '').trim(), 120));
    }
    const headers = [];
    const headerTexts = [];
    const counted = [];
    const cells = [];
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
  // context. The URL is recorded and is never part of the verdict: a modern list
  // page rewrites its own URL, and a view parameter says what was asked for
  // rather than what rendered.
  const pageIdentity = () => {
    const candidates = [
      ['_spPageContextInfo.listId', pageCtx.listId],
      ['_spPageContextInfo.pageListId', pageCtx.pageListId],
      ['_spPageContextInfo.listUrl', pageCtx.listUrl],
      ['_spPageContextInfo.listTitle', pageCtx.listTitle],
    ];
    const ids = [pageCtx.listId, pageCtx.pageListId].map(guid).filter((g) => g.length > 0);
    return { candidates, ids,
      detail: `page context ${JSON.stringify(candidates)}; document.title `
        + `${show(String(document.title || ''))}; OBSERVED ONLY, never part of the verdict: `
        + `location ${show(String(window.location.href))}` };
  };

  // ---- The questions ------------------------------------------------------
  expect('library.large-list.fixture-foldered-file-count', `The large library '${LIB}' holds ${TARGET_FILES} files, counted from the newest file name`);
  expect('library.large-list.fixture-foldered-folder-counts', `Each of the ${FOLDERS.length} folders holds fewer than ${THRESHOLD} files while the library holds more`);
  expect('library.large-list.fixture-foldered-index-written-under-threshold', `${CHOICE} reads Indexed=true and its Description carries the stamp saying the flag was written below ${THRESHOLD} files`);
  expect('library.large-list.fixture-foldered-witness-unindexed', `${NUMBER} reads Indexed=false, so this run has an unindexed column to witness the throttle with`);
  expect('library.large-list.fixture-multilevel-file-count', `The small library '${SMALL}' holds ${SMALL_FILES} files, counted from the newest file name`);
  expect('library.large-list.fixture-multilevel-under-threshold', `The small library is still under the ${THRESHOLD} threshold, which is the only reason a level-depth reading on it means anything`);
  expect('library.large-list.control-foldered-id-query-served', 'POSITIVE CONTROL: a selective filter on Id is served past the threshold');
  expect('library.large-list.control-foldered-unindexed-filter-refused', 'NEGATIVE CONTROL: a selective filter on the unindexed contract column is refused WITH the throttle signature');
  expect('library.large-list.control-foldered-render-where-absent-refused', 'NEGATIVE CONTROL: a rendered query whose <Where> names a column the library does not hold is refused WITHOUT the throttle signature');
  expect('library.large-list.control-foldered-folder-path-narrows', 'CONTROL: does the folder parameter actually narrow the query to that folder, read off the file names an ungrouped query returns');
  expect('library.large-list.control-foldered-group-by-narrowed-honoured', `POSITIVE CONTROL: a <GroupBy> on ${CHOICE} is honoured once a <Where> on Id has narrowed the rows to a handful`);
  expect('library.large-list.foldered-group-by-root-scoped', `Is the group-by on ${CHOICE} refused at the library root, as three probes measured on the flat fixtures`);
  expect('library.large-list.foldered-group-by-folder-scoped', `THE CRUX: is that same group-by honoured, ignored or refused when the query is pointed at one folder under ${THRESHOLD} files`);
  expect('library.large-list.foldered-group-by-folder-scoped-counts', `Where a folder-scoped group-by serves, how many collapsed rows come back and what do their group counts read`);
  expect('library.large-list.foldered-group-by-refusal-signature', 'Does every refusal this run collects carry SPQueryThrottledException, or does one carry something else');
  expect('library.large-list.control-multilevel-single-level-honoured', `POSITIVE CONTROL: a ONE-level <GroupBy> is honoured on the small library, so the depth rows below are about depth`);
  expect('library.large-list.multilevel-group-by-two-levels', `Do TWO levels of <GroupBy> serve on ${SMALL_FILES} files, and do the groups carry the counts the wrap arithmetic gives`);
  expect('library.large-list.multilevel-group-by-three-levels', `Do THREE levels of <GroupBy> serve where nothing is near the threshold, and do the leaf combinations appear`);
  expect('library.large-list.fixture-foldered-ui-views-created', 'Both views exist and read back carrying the grouping they were sent, and the stored level count is reported');
  expect('library.large-list.control-ui-foldered-fixture-readable-after-view-writes', "CONTROL: is the newest file name the same after the view writes as before them, so the fixture's owner can still resume and verify it");
  expect('library.large-list.control-ui-foldered-default-view-unchanged', "CONTROL: is each library's default view the one it was before this probe wrote anything");
  expect('library.large-list.control-ui-modern-renders-below-threshold', 'CONTROL: does this browser render a modern document library page at all, on a library UNDER the threshold');
  expect('library.large-list.control-ui-foldered-page-identity', 'CONTROL: does the rendered page say, in its own JavaScript context, which fixture library it belongs to');
  expect('library.large-list.control-ui-folder-scope-rendered', 'CONTROL: is the rendered page showing ONE folder, read from the file names it rendered rather than from its address');
  expect('library.large-list.ui-group-by-indexed-column-folder-scoped', `THE RENDERED CRUX: does the modern page render a grouped view scoped to a folder under ${THRESHOLD} files inside a library over ${THRESHOLD}`);
  expect('library.large-list.ui-group-by-multilevel-renders', 'Does the modern page render three group levels on the small library');
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

  // ==========================================================================
  // STATE 0: the setup leg and every REST question.
  // ==========================================================================
  if (STATE === 0) {
    if (!CONFIRMED) {
      log('INFO', `Would READ the two existing libraries '${LIB}' and '${SMALL}' on ${WEB}:`);
      log('INFO', 'their file counts, their columns, the index flags and the index stamp on');
      log('INFO', `${CHOICE}'s Description. It builds NOTHING and REPAIRS NOTHING.`);
      log('INFO', `It would then send OData filters reading at most ${PAGE} rows each, and`);
      log('INFO', `rendered view reads of at most ${ROW_LIMIT} rows: flat, grouped at the`);
      log('INFO', 'library root, grouped with the query pointed at one folder, grouped over an');
      log('INFO', 'Id-narrowed row set, and grouped at one, two and three levels on the small');
      log('INFO', 'library.');
      log('INFO', `It would CREATE two views, '${VIEW_FOLDERED}' on the large library and`);
      log('INFO', `'${VIEW_MULTILEVEL}' on the small one, read both back, and check that`);
      log('INFO', 'neither library\'s newest file name or default view moved.');
      log('INFO', 'It uploads NO file, writes NO item value, creates NO column and sends NO');
      log('INFO', `field MERGE. In particular it does NOT clear the index on ${CHOICE}: that`);
      log('INFO', `flag was written below ${THRESHOLD} files and cannot be put back without`);
      log('INFO', 'rebuilding the library from empty.');
      log('INFO', `Expect a minute or two, most of it ${PAIR_ATTEMPTS} paired readings`);
      log('INFO', `${PAIR_WAIT_MS} ms apart.`);
      log('INFO', "It does NOT touch 'dbmlsp Probe LargeLib' or 'dbmlsp Probe PreIndex'. Those");
      log('INFO', 'are different libraries, measured by #478 through #485.');
      log('INFO', 'Set CONFIRMED and ALLOW_WRITES to true to run it.');
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
      for (const [list, title] of [[libPath, VIEW_FOLDERED], [smallPath, VIEW_MULTILEVEL]]) {
        const held = await spGet(`${list}/views?$top=200`);
        const known = (!readFailed(held) && Array.isArray(held.body.value)) ? held.body.value : [];
        // Exact title membership, not a prefix. A prefix test would let a
        // mistyped or stale cleanup reach a view somebody else made, and a
        // default view is refused outright whatever it is called.
        const view = known.find((v) => v.Title === title);
        if (!view) {
          log('INFO', `CLEANUP: no view titled '${title}'. Nothing to do.`);
          continue;
        }
        if (view.DefaultView === true) {
          log('FAIL', `CLEANUP: '${title}' is the library's DEFAULT view, so it is NOT removed. `
            + 'Set another view as default by hand first, then re-run cleanup.');
          continue;
        }
        const digest = await getDigest();
        const gone = await spPost(`${list}/views/getbytitle('${odataName(title)}')`, {}, digest,
                                  { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
        log(gone.ok ? 'OK' : 'FAIL', gone.ok
          ? `CLEANUP: removed the view '${title}'.`
          : `CLEANUP: could not remove '${title}': HTTP ${gone.status} ${clip(gone.text, 200)}`);
      }
      const after = await newestFile(libPath, FILE_NUMBER, FOLDERS);
      log('INFO', `After cleanup the newest file reads ${show(after.name)} (${after.why}). Both `
        + `libraries, their files, their folders and the index on ${CHOICE} are untouched.`);
      report();
      return;
    }

    // ---- fixture-foldered-file-count -------------------------------------
    const libRead = await spGet(`${libPath}?$select=Title,BaseTemplate,ItemCount`);
    const libOk = !readFailed(libRead);
    const before = libOk
      ? await newestFile(libPath, FILE_NUMBER, FOLDERS)
      : { ok: false, number: 0, name: null, id: null, why: 'the library did not read back' };
    const count = before.ok ? before.number : 0;
    const newestId = before.id;
    const onContract = Math.abs(count - TARGET_FILES) <= COUNT_TOLERANCE;
    const present = libOk && before.ok && count >= FLOOR && onContract;
    record('library.large-list.fixture-foldered-file-count',
           `The large library '${LIB}' holds ${TARGET_FILES} files, counted from the newest file name`,
           !libOk || !before.ok ? 'ABORTED'
             : count < FLOOR ? 'SHORT'
               : onContract ? 'PASS' : 'FAIL',
           (libOk
             ? `the newest file is ${show(before.name)} at item id ${show(newestId)}, so the `
               + `library holds ${count} file(s) against the ${FLOOR} this probe needs and the `
               + `${TARGET_FILES} the fixture contract gives, a drift of ${count - TARGET_FILES} `
               + `against a tolerance of ${COUNT_TOLERANCE}; ItemCount reads `
               + `${show(libRead.body.ItemCount)} and is not what the count is taken from because `
               + 'it comes from a timer-job cache that lags an upload burst'
             : `the library did not read back (HTTP ${libRead.status}): `
               + `${clip(show(libRead.body), 200)}`)
           + `. ${before.why}. `
           + (present
             ? 'Every folder-scoped prediction below is derived from this count and the fixture '
               + 'formulas, so it is the number the whole run is read against. This probe does '
               + 'not build the fixture, does not repair it and writes nothing to it except one '
               + 'view.'
             : 'Run library-large-list-foldered-fixture-probe.js with BUILD_FIXTURE true until '
               + 'its rows read PASS, then re-paste this one. A library at a different count is '
               + 'not this fixture: the folder and choice bucket sizes below would be wrong and '
               + 'a mismatched bucket would read as a SharePoint finding.'));

    if (!present) {
      stampRemaining('ABORTED',
                     'the large fixture was not readable at its contract count, so no query was '
                     + 'sent and no view was created');
      report();
      return;
    }

    // ---- fixture-foldered-folder-counts ----------------------------------
    // Computed over the file NUMBERING and confirmed against each folder's own
    // Exists read. A folder's ItemCount comes from the same timer-job cache the
    // list figure does, so it is printed as an observation and no outcome turns
    // on it. The library's server-relative address is read rather than derived:
    // it is frozen at creation and a rename does not move it.
    const rootRead = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
    const rootUrl = !readFailed(rootRead) ? String(rootRead.body.ServerRelativeUrl || '') : null;
    const folderPathOf = (name) => (rootUrl === null ? null : `${rootUrl}/${name}`);
    const folderReads = [];
    const folderPredicted = {};
    let foldersOk = rootUrl !== null && rootUrl.length > 0;
    for (const name of FOLDERS) {
      folderPredicted[name] = tally(count, (n) => folderOf(n) === name);
      const path = folderPathOf(name);
      const read = path === null ? null : await spGet(
        `web/GetFolderByServerRelativeUrl('${odataName(path)}')?$select=Exists,ItemCount,Name`);
      const exists = read !== null && !readFailed(read) && read.body.Exists === true;
      if (!exists || folderPredicted[name] >= THRESHOLD) foldersOk = false;
      folderReads.push(`${name} at ${show(path)}: Exists ${show(read && read.body && read.body.Exists)}, `
        + `cached ItemCount ${show(read && read.body && read.body.ItemCount)} (OBSERVED, from the `
        + `same timer-job cache the list figure comes from), and the file numbering gives it `
        + `${folderPredicted[name]} file(s)`);
    }
    const inequality = foldersOk && count > THRESHOLD;
    record('library.large-list.fixture-foldered-folder-counts',
           `Each of the ${FOLDERS.length} folders holds fewer than ${THRESHOLD} files while the library holds more`,
           rootUrl === null ? 'ABORTED' : inequality ? 'PASS' : 'FAIL',
           (rootUrl === null
             ? `the library RootFolder did not read back (HTTP ${rootRead.status}), so no folder `
               + 'path is known and no folder-scoped query can be addressed'
             : `the library root reads ${show(rootUrl)}, READ rather than derived from the title, `
               + `because a library's address is frozen at creation and a rename does not move `
               + `it. ${folderReads.join('. ')}`)
           + '. '
           + (inequality
             ? `The library holds ${count} file(s), past the ${THRESHOLD} threshold, while every `
               + 'folder holds well under it. That inequality is the whole reason this fixture '
               + 'exists and every folder-scoped row below rests on it.'
             : 'Without a folder under the threshold inside a library over it, a folder-scoped '
               + 'answer below would not be about the threshold at all.'));

    // ---- fixture-foldered-index-written-under-threshold ------------------
    const choiceRead = await readField(libPath, CHOICE);
    const choiceOk = !readFailed(choiceRead);
    const description = choiceOk ? String(choiceRead.body.Description || '') : '';
    const stamp = STAMP_RE.exec(description);
    const stampedAt = stamp ? Number(stamp[1]) : null;
    const stampedOn = stamp ? stamp[2] : null;
    const choiceIndexed = choiceOk && choiceRead.body.Indexed === true;
    const preindexProved = choiceIndexed && stampedAt !== null && stampedAt < THRESHOLD;
    record('library.large-list.fixture-foldered-index-written-under-threshold',
           `${CHOICE} reads Indexed=true and its Description carries the stamp saying the flag was written below ${THRESHOLD} files`,
           !choiceOk ? 'ABORTED'
             : preindexProved ? 'PASS'
               : !choiceIndexed ? 'FAIL'
                 : stamp === null ? 'NOT ESTABLISHED' : 'FAIL',
           (!choiceOk
             ? `${CHOICE} did not read back (HTTP ${choiceRead.status})`
             : `${CHOICE}: TypeAsString ${show(choiceRead.body.TypeAsString)}, Indexed `
               + `${show(choiceRead.body.Indexed)}, AutoIndexed `
               + `${show(choiceRead.body.AutoIndexed)}; its Description reads `
               + `${show(clip(description, 200))}`
               + (stamp === null
                 ? `, which does not match the fixture's stamp pattern ${String(STAMP_RE)}`
                 : `, so the flag was written at ${stampedAt} file(s) on ${stampedOn}`))
           + '. '
           + (preindexProved
             ? `The index predates the crossing of ${THRESHOLD} files by ${THRESHOLD - stampedAt} `
               + 'file(s). #483 measured that this ordering does not lift a group-by at the '
               + 'library root, so what the folder rows below add is a smaller row set rather '
               + 'than a better index.'
             : !choiceIndexed
               ? 'Without the index there is no indexed column to scope a group-by on. It cannot '
                 + 'be put back: writing Indexed=true now would be a post-threshold index, which '
                 + 'is what #481 already measured. The fixture has to be rebuilt from empty.'
               : stamp === null
                 ? 'Indexed=true with no stamp is equally consistent with a flag written at 4,900 '
                   + 'files and one written at 5,255, so this run cannot say the index is a '
                   + 'pre-threshold one and the crux is read against an index of unknown '
                   + 'provenance.'
                 : `The stamp names ${stampedAt} file(s), which is not below ${THRESHOLD}, so this `
                   + 'library is a foldered copy of the post-hoc case rather than the comparison '
                   + 'it was built to be.'));

    // ---- fixture-foldered-witness-unindexed ------------------------------
    const numberRead = await readField(libPath, NUMBER);
    const numberOk = !readFailed(numberRead);
    const witnessClear = numberOk && numberRead.body.Indexed === false;
    record('library.large-list.fixture-foldered-witness-unindexed',
           `${NUMBER} reads Indexed=false, so this run has an unindexed column to witness the throttle with`,
           !numberOk ? 'ABORTED' : witnessClear ? 'PASS' : 'FAIL',
           (!numberOk
             ? `${NUMBER} did not read back (HTTP ${numberRead.status})`
             : `${NUMBER}: TypeAsString ${show(numberRead.body.TypeAsString)}, Indexed `
               + `${show(numberRead.body.Indexed)}, AutoIndexed `
               + `${show(numberRead.body.AutoIndexed)}`)
           + '. '
           + (witnessClear
             ? 'The throttle therefore has a witness on this library, which is what the negative '
               + 'controls below rest on.'
             : 'Without an unindexed column nothing on this library can show the threshold being '
               + 'enforced, so a served answer on the indexed column says nothing. #478 measured '
               + 'that SharePoint can index a column on its own, so this is read rather than '
               + 'assumed.'));

    // ---- fixture-multilevel-file-count and under-threshold ---------------
    const smallRead = await spGet(`${smallPath}?$select=Title,BaseTemplate,ItemCount`);
    const smallOk = !readFailed(smallRead);
    const smallNewest = smallOk
      ? await newestFile(smallPath, SMALL_NUMBER, [])
      : { ok: false, number: 0, name: null, id: null, why: 'the library did not read back' };
    const smallCount = smallNewest.ok ? smallNewest.number : 0;
    const smallOnContract = smallCount === SMALL_FILES;
    const smallColumns = [];
    let smallColumnsOk = smallOk;
    for (const [name, wanted] of [[M_CHOICE, 'Choice'], [M_FLAG, 'Boolean'], [M_TEXT, 'Text']]) {
      const read = smallOk ? await readField(smallPath, name) : null;
      const ok = read !== null && !readFailed(read);
      // The TYPE is reported and compared, but a mismatch does not fail this
      // row: what a Yes/No column reads as TypeAsString is a fact about
      // SharePoint that no probe here has pinned, and asserting a spelling from
      // memory is the failure AGENTS.md names. The row is about the COUNT.
      smallColumns.push(`${name}: HTTP ${show(read && read.status)}, TypeAsString `
        + `${show(ok ? read.body.TypeAsString : null)} against the ${wanted} the fixture asked `
        + `for, Indexed ${show(ok ? read.body.Indexed : null)}`);
      if (!ok) smallColumnsOk = false;
    }
    record('library.large-list.fixture-multilevel-file-count',
           `The small library '${SMALL}' holds ${SMALL_FILES} files, counted from the newest file name`,
           !smallOk || !smallNewest.ok ? 'ABORTED'
             : smallOnContract && smallColumnsOk ? 'PASS' : 'FAIL',
           (smallOk
             ? `the newest file is ${show(smallNewest.name)}, so the library holds ${smallCount} `
               + `file(s) against the ${SMALL_FILES} the fixture contract gives; ItemCount reads `
               + `${show(smallRead.body.ItemCount)} and is not what the count is taken from. `
               + `Its three columns read: ${smallColumns.join('; ')}`
             : `the library did not read back (HTTP ${smallRead.status}): `
               + `${clip(show(smallRead.body), 200)}`)
           + `. ${smallNewest.why}. `
           + (smallOnContract && smallColumnsOk
             ? 'The wrap arithmetic every depth prediction below is derived from is a function of '
               + 'this count, so a different count is a different set of predictions rather than '
               + 'a failing one.'
             : 'Run library-large-list-foldered-fixture-probe.js with BUILD_FIXTURE true until '
               + 'its multilevel rows read PASS, then re-paste this one.'));

    const smallUnder = smallOnContract && smallCount < THRESHOLD;
    // The three moduli are pairwise coprime, so each level cuts what the level
    // above it left. The combination sizes are DERIVED here rather than written
    // in, which is what makes a bucket that comes back the wrong size a finding.
    const leafCombos = {};
    const twoLevelCombos = {};
    for (let n = 1; n <= smallCount; n += 1) {
      const leaf = `${mChoiceOf(n)}/${mFlagOf(n) ? 'Yes' : 'No'}/${mTextOf(n)}`;
      const two = `${mChoiceOf(n)}/${mFlagOf(n) ? 'Yes' : 'No'}`;
      leafCombos[leaf] = (leafCombos[leaf] || 0) + 1;
      twoLevelCombos[two] = (twoLevelCombos[two] || 0) + 1;
    }
    const leafKeys = Object.keys(leafCombos);
    const twoKeys = Object.keys(twoLevelCombos);
    const leafSizes = uniq(leafKeys.map((k) => leafCombos[k])).sort((a, b) => a - b);
    const twoSizes = uniq(twoKeys.map((k) => twoLevelCombos[k])).sort((a, b) => a - b);
    const everyLeafFilled = leafKeys.length > 0 && leafKeys.every((k) => leafCombos[k] > 0);
    record('library.large-list.fixture-multilevel-under-threshold',
           `The small library is still under the ${THRESHOLD} threshold, which is the only reason a level-depth reading on it means anything`,
           !smallOnContract ? 'ABORTED'
             : smallUnder && everyLeafFilled ? 'PASS' : 'FAIL',
           `${smallCount} file(s), against the ${THRESHOLD} threshold. ${M_CHOICE} wraps at `
           + `${CHOICES.length}, ${M_FLAG} at 3 and ${M_TEXT} at 5, pairwise coprime, so each `
           + `level cuts what the level above it left. Derived from those formulas over `
           + `${smallCount} files rather than written in: ${leafKeys.length} leaf combination(s) `
           + `of the three values, of size(s) ${show(leafSizes)}, and ${twoKeys.length} `
           + `combination(s) of the first two, of size(s) ${show(twoSizes)}. `
           + (smallUnder && everyLeafFilled
             ? 'Every combination is non-empty, so a level that returns fewer groups than this '
               + 'has dropped something rather than found nothing to show. Nothing on this '
               + 'library is near the threshold, so a refusal here is about the SHAPE of the '
               + 'request.'
             : 'Without a full set of non-empty combinations under the threshold, a depth reading '
               + 'below could be an empty bucket rather than a dropped level.'));

    // The predicted bucket sizes on the large library, derived the same way.
    const perFolderChoice = {};
    for (const folder of FOLDERS) {
      for (const value of CHOICES) {
        perFolderChoice[`${folder}/${value}`] =
          tally(count, (n) => folderOf(n) === folder && choiceOf(n) === value);
      }
    }
    const folderChoiceSizes = uniq(Object.keys(perFolderChoice)
      .map((k) => perFolderChoice[k])).sort((a, b) => a - b);
    const libraryChoice = {};
    for (const value of CHOICES) {
      libraryChoice[value] = tally(count, (n) => choiceOf(n) === value);
    }
    log('INFO', `Derived from the fixture formulas over ${count} file(s): each folder holds `
      + `${show(folderChoiceSizes)} file(s) of each ${CHOICE} value, and the whole library holds `
      + `${show(libraryChoice)}.`);

    // ---- control-foldered-id-query-served --------------------------------
    const idFilter = await askFilter(libPath, `Id eq ${newestId}`);
    const idFilterOutcome = judge(idFilter, 1);
    const idServed = idFilterOutcome.startsWith('SERVED');
    record('library.large-list.control-foldered-id-query-served',
           'POSITIVE CONTROL: a selective filter on Id is served past the threshold',
           idServed ? 'SERVED' : 'CONTROL FAILED, METHOD VOID',
           `${idFilter.label} on ${count} file(s): HTTP ${idFilter.status}, ${idFilterOutcome}`
           + (idServed
             ? '. A served answer is therefore observable on this library at this size, which is '
               + 'what the Id-narrowed control below rests on.'
             : `. Body: ${idFilter.body}. Id is the one natively indexed column `
               + '(library-index-threshold-probe.js, 2026-09-08), so a refusal here says the '
               + 'method cannot observe a served answer at all, not that an index is missing.'));

    // ---- control-foldered-unindexed-filter-refused -----------------------
    const numberExpected = tally(count, (n) => n % 1000 === 7);
    const witnessSeen = witnessClear ? await askFilter(libPath, `${NUMBER} eq 7`) : null;
    const witnessOutcome = witnessSeen === null ? null : judge(witnessSeen, numberExpected);
    const throttleEnforced = witnessOutcome !== null
      && witnessOutcome.startsWith('REFUSED (threshold)');
    record('library.large-list.control-foldered-unindexed-filter-refused',
           'NEGATIVE CONTROL: a selective filter on the unindexed contract column is refused WITH the throttle signature',
           witnessSeen === null ? 'NOT ESTABLISHED'
             : throttleEnforced ? 'REFUSED (threshold)' : 'CONTROL FAILED, METHOD VOID',
           witnessSeen === null
             ? `${NUMBER} did not read Indexed=false, so this fixture has no unindexed column left `
               + 'to witness a throttle with'
             : `${witnessSeen.label} on ${count} file(s), matching ${numberExpected} of them by `
               + `the fixture's own formula: HTTP ${witnessSeen.status}, ${witnessOutcome}: `
               + `${witnessSeen.body}`
               + (throttleEnforced
                 ? '. The library is therefore past the threshold and throttling is enforced on '
                   + 'it, so a refusal below is the threshold and an answer served below is worth '
                   + 'something.'
                 : '. Without a refusal here nothing below is evidence of the threshold: the '
                   + 'library may simply not be far enough past it for this tenant to enforce it, '
                   + 'and a served folder-scoped group-by would then be a small library answering '
                   + 'rather than a folder scope working.'));

    // ---- control-foldered-render-where-absent-refused --------------------
    // The same discrimination on the surface every grouped question uses.
    // ViewFields deliberately omits ABSENT_COLUMN: it is named in the <Where>
    // alone, so a refusal is about the clause under measurement.
    const renderAbsent = await askView(libPath, { whereOn: ABSENT_COLUMN, whereValue: 'x',
                                                  fields: ['FileLeafRef'] });
    const renderAbsentRefused = !renderAbsent.res.ok && isRefusal(renderAbsent.res.status)
      && !renderAbsent.throttled;
    record('library.large-list.control-foldered-render-where-absent-refused',
           'NEGATIVE CONTROL: a rendered query whose <Where> names a column the library does not hold is refused WITHOUT the throttle signature',
           renderAbsentRefused ? 'REFUSED (request rejected, no throttle signature)'
             : 'CONTROL FAILED, METHOD VOID',
           `RenderListDataAsStream with <Where> on ${ABSENT_COLUMN}: HTTP `
           + `${renderAbsent.res.status} with ${renderAbsent.rows.length} row(s), throttle `
           + `signature ${renderAbsent.throttled ? 'PRESENT' : 'absent'}: `
           + `${clip(renderAbsent.res.text, 240)}`
           + (renderAbsentRefused
             ? '. A rejected render and a throttled one are therefore distinguishable, so a '
               + 'REFUSED (threshold) verdict on a grouped query below is the threshold rather '
               + 'than the server rejecting the query.'
             : renderAbsent.throttled
               ? '. A rendered query naming a column that does not exist came back carrying the '
                 + 'throttle signature, so no grouped refusal below can be attributed to the '
                 + 'threshold.'
               : '. The render surface did not refuse a query naming a column that does not '
                 + 'exist, so a refusal below cannot be read as the server rejecting what was '
                 + 'sent either.'));

    // ---- control-foldered-folder-path-narrows ----------------------------
    // The row that separates a folder scope that worked from a parameter the
    // server ignored, and it is taken on an UNGROUPED query because a collapsed
    // row carries no file name. Every returned name is mapped to a folder by the
    // fixture's own formula, so this is the fixture's arithmetic against
    // SharePoint's row set rather than against itself.
    const scopeFolder = SCOPED_FOLDERS[0];
    const scopeFolderPath = folderPathOf(scopeFolder);
    const flatInFolder = scopeFolderPath === null ? null
      : await askView(libPath, { folder: scopeFolderPath, fields: ['FileLeafRef'] });
    const flatAtRoot = await askView(libPath, { fields: ['FileLeafRef'] });
    const scopedNames = flatInFolder === null ? [] : namesOf(flatInFolder.rows);
    const scopedFolders = {};
    let strayNames = 0;
    for (const name of scopedNames) {
      const digits = name.match(FILE_NUMBER);
      if (!digits) {
        strayNames += 1;
        continue;
      }
      const where = folderOf(Number(digits[1]));
      scopedFolders[where] = (scopedFolders[where] || 0) + 1;
    }
    const scopedKeys = Object.keys(scopedFolders);
    const narrows = flatInFolder !== null && flatInFolder.res.ok && scopedNames.length > 0
      && strayNames === 0 && scopedKeys.length === 1 && scopedKeys[0] === scopeFolder;
    record('library.large-list.control-foldered-folder-path-narrows',
           'CONTROL: does the folder parameter actually narrow the query to that folder, read off the file names an ungrouped query returns',
           scopeFolderPath === null ? 'NOT ESTABLISHED'
             : narrows ? 'NARROWS TO THE FOLDER' : 'CONTROL FAILED, METHOD VOID',
           (scopeFolderPath === null
             ? 'the library RootFolder did not read back, so no folder path was known and nothing '
               + 'could be pointed at one'
             : `an UNGROUPED RenderListDataAsStream with FolderServerRelativeUrl `
               + `${show(scopeFolderPath)} and no Scope attribute returned HTTP `
               + `${flatInFolder.res.status} with ${flatInFolder.rows.length} row(s) against a `
               + `RowLimit of ${ROW_LIMIT}, of which ${scopedNames.length} carried a file name. `
               + `Mapping each name through the fixture's own folder formula puts them in `
               + `${show(scopedFolders)}, with ${strayNames} name(s) matching no fixture pattern. `
               + `The same query with NO folder parameter returned HTTP ${flatAtRoot.res.status} `
               + `with ${flatAtRoot.rows.length} row(s)`)
           + '. '
           + (narrows
             ? 'Every named row belongs to the folder that was asked for, so the parameter is '
               + 'being honoured rather than ignored. That matters because a folder read can '
               + 'answer HTTP 200 for a folder that could not have been there '
               + '(library-view-interaction-probe.js, 2026-09-08), and a parameter SharePoint '
               + 'ignores answers the same rows as one it never received. Without this row a '
               + 'refused folder-scoped group-by below could not be told from a folder scope that '
               + 'never applied.'
             : 'The folder parameter did not demonstrably narrow anything, so every folder-scoped '
               + 'row below is void rather than open: a refusal would be indistinguishable from a '
               + 'parameter that never took, and a served answer would be the whole library '
               + 'answering.'));

    // ---- control-foldered-group-by-narrowed-honoured ---------------------
    // The grouping instrument, proved where the threshold cannot reach it. The
    // Id value type is tried rather than assumed: a wrong spelling comes back as
    // a rejected request, the same shape as the refusal that would be the
    // finding.
    const minId = newestId - GUARD_SPAN;
    const idTypeAttempts = [];
    let idType = null;
    for (const type of ID_VALUE_TYPES) {
      const seen = await askView(libPath, { minId, idType: type, fields: ['FileLeafRef', CHOICE] });
      idTypeAttempts.push(`Type="${type}": HTTP ${seen.res.status}, ${judgeView(seen)}`
        + (seen.res.ok ? '' : ` ${clip(seen.res.text, 160)}`));
      if (seen.res.ok || seen.throttled) {
        idType = type;
        break;
      }
    }
    const narrowedVoid = !idServed
      ? 'the positive control on Id was not served, so an Id clause cannot narrow anything on '
        + 'this run and a narrowed grouping measures nothing'
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
      record('library.large-list.control-foldered-group-by-narrowed-honoured',
             `POSITIVE CONTROL: a <GroupBy> on ${CHOICE} is honoured once a <Where> on Id has narrowed the rows to a handful`,
             'CONTROL FAILED, METHOD VOID', narrowedVoid, 'void');
    } else {
      narrowed = await observeGroup(libPath, {
        minId, idType, groupBy: CHOICE,
        fields: ['FileLeafRef', CHOICE],
        label: `group-by on ${CHOICE} over an Id-narrowed row set`,
      });
      narrowedHeld = narrowed.verdict.startsWith('HONOURED');
      record('library.large-list.control-foldered-group-by-narrowed-honoured',
             `POSITIVE CONTROL: a <GroupBy> on ${CHOICE} is honoured once a <Where> on Id has narrowed the rows to a handful`,
             narrowedHeld ? 'HONOURED' : 'CONTROL FAILED, METHOD VOID',
             `<Where><Geq> on ID at ${minId} (the newest item id ${newestId} less ${GUARD_SPAN}), `
             + `grouping on ${CHOICE}. The counter spelling was tried rather than assumed: `
             + `${idTypeAttempts.join('; ')}, so Type="${show(idType)}" is what answered. `
             + `${narrowed.text}`
             + (narrowedHeld
               ? '. A <GroupBy> on this column is therefore a request this server accepts and '
                 + 'acts on, so a refusal of the same shape at size below is about the size. #480 '
                 + 'measured the same composition honoured on the first fixture; it is re-proved '
                 + 'here because this is a third library with its own build.'
               : '. The grouping was not honoured even over a handful of rows, so a refusal of '
                 + 'the same shape below cannot be attributed to the threshold: it may be the '
                 + 'request. Read the collapsed body above before reading anything below it.'));
    }

    // ---- foldered-group-by-root-scoped and the CRUX ----------------------
    // Every reason these readings could not be attributed, in the order a reader
    // would want them. The first one that applies is the reason the row is void.
    const cruxVoid = !throttleEnforced
      ? 'the unindexed witness was not refused with the threshold signature, so this library is '
        + 'not demonstrably enforcing the threshold and neither a served nor a refused group-by '
        + 'here could be attributed to it'
      : !narrowedHeld
        ? 'the narrowed control did not hold, so a refusal here cannot be told from the server '
          + 'rejecting the request'
        : !narrows
          ? 'the folder parameter was not shown to narrow anything, so a folder-scoped reading '
            + 'here is not distinguishable from a root-scoped one'
          : !inequality
            ? 'the folder and library counts do not present the inequality this question is '
              + 'about, so a folder-scoped answer says nothing about the threshold'
            : null;

    log('INFO', `Sending the group-by on ${CHOICE} pointed at ${scopeFolder}, up to `
      + `${PAIR_ATTEMPTS} time(s) ${PAIR_WAIT_MS} ms apart, with the identical ROOT-scoped query `
      + 'immediately after each one.');
    const crux = await pairedReadings(libPath, {
      folder: scopeFolderPath, groupBy: CHOICE,
      fields: ['FileLeafRef', CHOICE],
      label: `group-by on ${CHOICE} scoped to ${scopeFolder}`,
    }, () => observeGroup(libPath, {
      groupBy: CHOICE,
      fields: ['FileLeafRef', CHOICE],
      label: `group-by on ${CHOICE} at the library root`,
    }));
    const rootSeen = crux.root;
    record('library.large-list.foldered-group-by-root-scoped',
           `Is the group-by on ${CHOICE} refused at the library root, as three probes measured on the flat fixtures`,
           cruxVoid !== null ? 'VOID'
             : rootSeen === null ? 'NOT ESTABLISHED' : rootSeen.verdict,
           (cruxVoid === null ? '' : `${cruxVoid}. What was observed anyway: `)
           + (rootSeen === null
             ? 'the paired root-scoped reading was never taken'
             : `the same ViewXml with NO folder parameter, over ${count} file(s) and the four `
               + `values ${show(CHOICES)}, whose library-wide counts the fixture formulas give as `
               + `${show(libraryChoice)}. ${rootSeen.text}`)
           + (cruxVoid !== null || rootSeen === null
             ? ''
             : rootSeen.verdict.startsWith('REFUSED')
               ? '. That is the anchor: #480, #481 and #483 each measured this refusal on a flat '
                 + 'library, and a third independently built fixture answers the same way. So a '
                 + 'different answer from the folder-scoped query beside it is the folder and '
                 + 'nothing else.'
               : '. The root-scoped group-by was NOT refused on this library, which contradicts '
                 + 'three earlier runs by the same method. Read the crux row beside this one: if '
                 + 'both serve, the folder scope is not what answered and this library is not '
                 + 'behaving like the two flat ones.'),
           cruxVoid === null ? undefined : 'void');

    const cruxSeen = crux.seen;
    // The symmetry check: one served folder could be a property of that folder.
    // Read as a second sample, at the same shape, on a folder the first reading
    // never touched.
    const secondFolder = SCOPED_FOLDERS[1];
    const secondPath = folderPathOf(secondFolder);
    const secondSeen = secondPath === null ? null : await observeGroup(libPath, {
      folder: secondPath, groupBy: CHOICE,
      fields: ['FileLeafRef', CHOICE],
      label: `group-by on ${CHOICE} scoped to ${secondFolder}`,
    });
    const agree = cruxSeen !== null && secondSeen !== null
      && cruxSeen.verdict.split(' ')[0] === secondSeen.verdict.split(' ')[0];
    record('library.large-list.foldered-group-by-folder-scoped',
           `THE CRUX: is that same group-by honoured, ignored or refused when the query is pointed at one folder under ${THRESHOLD} files`,
           cruxVoid !== null ? 'VOID'
             : cruxSeen === null ? 'NOT ESTABLISHED'
               : agree ? cruxSeen.verdict : `${cruxSeen.verdict} ON ${scopeFolder}, BUT THE TWO FOLDERS DISAGREE`,
           (cruxVoid === null ? '' : `${cruxVoid}. What was observed anyway: `)
           + `the folder ${show(scopeFolderPath)} holds `
           + `${folderPredicted[scopeFolder]} file(s) by the fixture's numbering, of which `
           + `${show(perFolderChoice[`${scopeFolder}/${CHOICES[0]}`])} carry `
           + `${show(CHOICES[0])}, inside a library of ${count}. The grouped query was sent `
           + `${crux.attempts} time(s) over ${crux.waitedMs} ms with the root-scoped query paired `
           + `after each: ${legNote(crux.legs)}. Last folder-scoped reading: `
           + `${cruxSeen === null ? '(none)' : cruxSeen.text}. Second folder ${secondFolder} at `
           + `${show(secondPath)}: ${secondSeen === null ? '(not read)' : secondSeen.verdict}, `
           + `${secondSeen === null ? '' : secondSeen.text}`
           + (cruxVoid !== null || cruxSeen === null
             ? ''
             : !agree
               ? '. The two folders did not answer the same way, so nothing here is a property of '
                 + 'folder scoping: read both bodies before reading either as a result.'
               : cruxSeen.verdict.startsWith('HONOURED')
                 ? '. A group-by REFUSED at the library root is HONOURED when the same query is '
                   + 'pointed at a folder holding fewer than 5,000 files, on both folders asked. '
                   + 'The threshold is therefore about the row set a query is given rather than '
                   + 'about the size of the list, and the generator rule that refuses a group-by '
                   + 'on a large container is wrong as stated: the correct rule would refuse an '
                   + 'UNSCOPED group-by and allow a folder-scoped one. That is a rule change, so '
                   + 'it wants a second run and the rendered rows beside it before it is acted on.'
                 : cruxSeen.verdict.startsWith('REFUSED')
                   ? '. The folder scope does not lift the group-by. The threshold is a property '
                     + 'of the LIST rather than of the row set a query is pointed at, which is '
                     + 'the reading three flat-library runs already pointed to and which no '
                     + 'folder can now be said to work around. The generator rule stands.'
                   : '. Neither honoured nor refused, so read the collapsed body and the flat '
                     + 'baseline above before reading this beside the root-scoped row.'),
           cruxVoid === null ? undefined : 'void');

    // ---- foldered-group-by-folder-scoped-counts --------------------------
    // Where the crux served, what the SERVER said each group holds, against what
    // the fixture's formulas give. This is the row the 438 belongs in, and it is
    // corroboration: the crux above does not pass or fail on it.
    const cruxCounts = cruxSeen === null ? [] : countsFor(cruxSeen.collapsed.rows, CHOICE);
    const predictedHere = CHOICES.map((value) =>
      `${value}=${perFolderChoice[`${scopeFolder}/${value}`]}`);
    const matchedCounts = cruxCounts.filter((row) => {
      const wanted = perFolderChoice[`${scopeFolder}/${row.label}`];
      return wanted !== undefined && String(row.count) === String(wanted);
    });
    record('library.large-list.foldered-group-by-folder-scoped-counts',
           'Where a folder-scoped group-by serves, how many collapsed rows come back and what do their group counts read',
           cruxVoid !== null ? 'VOID'
             : cruxSeen === null || !cruxSeen.verdict.startsWith('HONOURED')
               ? 'NO SERVED AGGREGATION TO READ'
               : matchedCounts.length === cruxCounts.length && cruxCounts.length > 0
                 ? 'COUNTS MATCH THE FOLDER'
                 : 'COUNTS READ, AND THEY ARE NOT THE FOLDER FIGURES',
           (cruxVoid === null ? '' : `${cruxVoid}. What was observed anyway: `)
           + `at Collapse="TRUE" and RowLimit ${ROW_LIMIT}, the collapsed query returned `
           + `${cruxSeen === null ? 0 : cruxSeen.collapsed.rows.length} row(s) carrying `
           + `${show(cruxCounts)} on the ${CHOICE}.COUNT.group key, which is the SERVER'S own `
           + 'group size and not a count this probe took over the rows. The fixture formulas give '
           + `${show(predictedHere)} inside ${scopeFolder}, against ${show(libraryChoice)} across `
           + 'the whole library. '
           + (cruxSeen === null || !cruxSeen.verdict.startsWith('HONOURED')
             ? 'Nothing served, so there is no aggregation to read. That is a successful run and '
               + 'the crux row above is where the result is.'
             : matchedCounts.length === cruxCounts.length && cruxCounts.length > 0
               ? 'Every group carries the folder figure rather than the library-wide one, so the '
                 + 'aggregation was computed over the folder and not over the list with a folder '
                 + 'filter applied afterwards. That is what makes the crux a folder-scoping '
                 + 'result rather than a paging one.'
               : 'The counts do not read the folder figures. If they read the library-wide ones, '
                 + 'the aggregation was computed across the list and only the ROWS were scoped, '
                 + 'which is a different mechanism and a different rule. If they read a round '
                 + `number near ${ROW_LIMIT}, the GroupLimit was reached rather than the group `
                 + 'counted. Quote the raw values above rather than the verdict.'),
           cruxVoid === null ? undefined : 'void');

    // ---- control-multilevel-single-level-honoured ------------------------
    const smallVoid = !smallOnContract
      ? 'the small library is not at its contract count, so nothing measured on it is about the '
        + 'fixture this probe was written for'
      : !smallUnder
        ? 'the small library is not under the threshold, so a refusal on it could be size rather '
          + 'than shape and the whole comparison collapses'
        : null;
    let oneLevel = null;
    let oneLevelHeld = false;
    if (smallVoid !== null) {
      record('library.large-list.control-multilevel-single-level-honoured',
             'POSITIVE CONTROL: a ONE-level <GroupBy> is honoured on the small library, so the depth rows below are about depth',
             'CONTROL FAILED, METHOD VOID', smallVoid, 'void');
    } else {
      oneLevel = await observeGroup(smallPath, {
        groupBy: M_CHOICE,
        fields: ['FileLeafRef', M_CHOICE],
        label: `one-level group-by on ${M_CHOICE}`,
      });
      oneLevelHeld = oneLevel.verdict.startsWith('HONOURED');
      const oneCounts = countsFor(oneLevel.collapsed.rows, M_CHOICE);
      record('library.large-list.control-multilevel-single-level-honoured',
             'POSITIVE CONTROL: a ONE-level <GroupBy> is honoured on the small library, so the depth rows below are about depth',
             oneLevelHeld ? 'HONOURED' : 'CONTROL FAILED, METHOD VOID',
             `one <FieldRef> on ${M_CHOICE} over ${smallCount} file(s), nothing indexed and `
             + `nothing near the threshold. ${oneLevel.text}. Group counts as the server gave `
             + `them: ${show(oneCounts)}, against ${show(smallCount / CHOICES.length)} per value `
             + 'from the wrap arithmetic. '
             + (oneLevelHeld
               ? 'A <GroupBy> is therefore a request this server accepts and acts on, on THIS '
                 + 'library, with THESE columns and THIS caller. A refusal at two or three levels '
                 + 'below is about the level count and nothing else, which is the separation #481 '
                 + 'could not make because its narrowed three-level control was refused too.'
               : 'One level did not work on a 240-file library where nothing is near the '
                 + 'threshold, so a refusal at two or three levels says nothing about depth. The '
                 + 'two depth rows below are void rather than open. Read the collapsed body '
                 + 'above.'));
    }

    // ---- multilevel-group-by-two-levels ----------------------------------
    const depthVoid = smallVoid !== null ? smallVoid
      : !oneLevelHeld
        ? 'the single-level control did not hold on this library, so a refusal at depth cannot be '
          + 'attributed to the depth'
        : null;
    const twoLevel = smallVoid !== null ? null : await observeGroup(smallPath, {
      groupBy: [M_CHOICE, M_FLAG],
      fields: ['FileLeafRef', M_CHOICE, M_FLAG],
      label: `two-level group-by on ${M_CHOICE} then ${M_FLAG}`,
    });
    const twoCounts = twoLevel === null ? [] : countsFor(twoLevel.collapsed.rows, M_CHOICE);
    record('library.large-list.multilevel-group-by-two-levels',
           `Do TWO levels of <GroupBy> serve on ${SMALL_FILES} files, and do the groups carry the counts the wrap arithmetic gives`,
           depthVoid !== null ? 'VOID' : twoLevel === null ? 'NOT ESTABLISHED' : twoLevel.verdict,
           (depthVoid === null ? '' : `${depthVoid}. What was observed anyway: `)
           + (twoLevel === null ? 'the query was not sent'
             : `two <FieldRef> children, ${M_CHOICE} then ${M_FLAG}, over ${smallCount} file(s). `
               + `${twoLevel.text}. The ${M_CHOICE} group counts the server returned are `
               + `${show(twoCounts)}. Derived from the wrap arithmetic rather than written in: `
               + `${twoKeys.length} combination(s) of the two values, holding `
               + `${show(twoLevelCombos)}, so the levels are uneven because ${M_FLAG} is true on `
               + 'one residue in three and false on two.')
           + (depthVoid !== null || twoLevel === null
             ? ''
             : twoLevel.verdict.startsWith('HONOURED')
               ? ' Two levels serve where one does, so whatever #481 met at three levels is not '
                 + 'met at two.'
               : ' Two levels did NOT serve on a library where one did and where nothing is near '
                 + 'the threshold, so the ceiling on <GroupBy> depth is between one and two rather '
                 + 'than between two and three. That is a stronger statement than #481 could make '
                 + 'and it changes what a layout may emit.'),
           depthVoid === null ? undefined : 'void');

    // ---- multilevel-group-by-three-levels --------------------------------
    const threeLevel = smallVoid !== null ? null : await observeGroup(smallPath, {
      groupBy: LEVELS,
      fields: ['FileLeafRef'].concat(LEVELS),
      label: `three-level group-by on ${LEVELS.join(' then ')}`,
    });
    const threeBody = threeLevel === null ? '' : clip(threeLevel.collapsed.res.text, 240);
    const sameAs481 = threeLevel !== null && !threeLevel.collapsed.res.ok
      && threeBody.includes('-2147467259');
    record('library.large-list.multilevel-group-by-three-levels',
           'Do THREE levels of <GroupBy> serve where nothing is near the threshold, and do the leaf combinations appear',
           depthVoid !== null ? 'VOID'
             : threeLevel === null ? 'NOT ESTABLISHED' : threeLevel.verdict,
           (depthVoid === null ? '' : `${depthVoid}. What was observed anyway: `)
           + (threeLevel === null ? 'the query was not sent'
             : `three <FieldRef> children, ${LEVELS.join(' then ')}, over ${smallCount} file(s) `
               + `where the largest container in this run is ${smallCount} rows. `
               + `${threeLevel.text}. Derived from the wrap arithmetic: ${leafKeys.length} leaf `
               + `combination(s) of the three values, of size(s) ${show(leafSizes)}, every one of `
               + 'them non-empty, so a level that drops out shows as fewer groups rather than as '
               + 'empty ones.')
           + (depthVoid !== null || threeLevel === null
             ? ''
             : threeLevel.verdict.startsWith('HONOURED')
               ? ' THREE levels serve on 240 files. #481 measured this shape refused HTTP 500 '
                 + 'with code -2147467259 on a 5,500-file library, including over an Id-narrowed '
                 + 'six-row set. Both cannot be about the shape, so the difference is the '
                 + 'CONTAINER: a three-level grouping is rejected on a large list even when the '
                 + 'rows are few, which is a property of the list rather than of the query. That '
                 + 'unblocks the two rows #481 had to void.'
               : sameAs481
                 ? ' THREE levels are refused with the SAME code -2147467259 #481 met, on a '
                   + '240-file library where one level is honoured and nothing is near the '
                   + 'threshold. The query engine rejects this shape for its depth, independently '
                   + 'of size, so #481 was measuring a shape limit rather than a threshold one '
                   + 'and a layout must never emit three levels on any container.'
                 : ' THREE levels did not serve, and the body is NOT the code -2147467259 #481 '
                   + 'met. Quote it: a third failure mode at this depth is its own finding.'),
           depthVoid === null ? undefined : 'void');

    // ---- foldered-group-by-refusal-signature -----------------------------
    const refusalNote = REFUSALS.length === 0
      ? 'no query in this run was refused at all'
      : REFUSALS.map((row) => `${row.label}: HTTP ${row.status}, SPQueryThrottledException `
        + `${row.exception ? 'PRESENT' : 'absent'}, threshold prose `
        + `${row.prose ? 'PRESENT' : 'absent'}: ${row.body}`).join('; ');
    const neither = REFUSALS.filter((row) => !row.exception && !row.prose);
    const proseOnly = REFUSALS.filter((row) => !row.exception && row.prose);
    record('library.large-list.foldered-group-by-refusal-signature',
           'Does every refusal this run collects carry SPQueryThrottledException, or does one carry something else',
           REFUSALS.length === 0 ? 'NO REFUSAL TO CLASSIFY'
             : neither.length ? 'A REFUSAL CARRIES NEITHER THRESHOLD SIGNATURE'
               : proseOnly.length ? 'SOME REFUSALS NAME THE THRESHOLD WITHOUT NAMING THE EXCEPTION'
                 : 'EVERY REFUSAL CARRIES SPQueryThrottledException',
           `${REFUSALS.length} refusal(s) collected across every grouped query this run sent, on `
           + `both libraries. ${refusalNote}`
           + (REFUSALS.length === 0
             ? '. Every grouped query was answered, so there is no refusal to attribute and the '
               + 'rows above stand on their served readings. On the large library that is itself '
               + 'the finding, because #479, #480, #481 and #483 all collected refusals by the '
               + 'same method.'
             : neither.length
               ? '. At least one refusal named neither the exception nor the threshold, so it is '
                 + 'a different finding from a throttle and the rows resting on it have to be '
                 + 'read against its body. #481 measured exactly that shape for a three-level '
                 + '<GroupBy>, HTTP 500 with code -2147467259, which is the reading the depth row '
                 + 'above is asked against.'
               : proseOnly.length
                 ? '. Every refusal named the threshold, but not all of them named the exception '
                   + 'type, so a reader matching on the class name alone would miss some.'
                 : '. The refusals are the throttle by its own name, not an error that merely '
                   + 'reads like one.'));

    // ---- The two views ---------------------------------------------------
    const viewsBefore = {};
    const defaultBefore = {};
    for (const [list, title] of [[libPath, LIB], [smallPath, SMALL]]) {
      const held = await spGet(`${list}/views?$top=200`);
      viewsBefore[title] = (!readFailed(held) && Array.isArray(held.body.value))
        ? held.body.value : [];
      defaultBefore[title] = viewsBefore[title].find((v) => v.DefaultView === true) || null;
    }

    if (!ALLOW_WRITES) {
      record('library.large-list.fixture-foldered-ui-views-created',
             'Both views exist and read back carrying the grouping they were sent, and the stored level count is reported',
             'ABORTED',
             'ALLOW_WRITES is false, so no view was created. Every REST row above was still '
               + 'answered, because none of them writes anything. Set ALLOW_WRITES to true and '
               + 'paste again to reach the rendered legs.');
      stampRemaining('NOT REACHED', 'the two views were not created, so no page was opened');
      report();
      return;
    }

    const viewErrors = [];
    const viewPlan = [
      [libPath, LIB, VIEW_FOLDERED, [CHOICE]],
      [smallPath, SMALL, VIEW_MULTILEVEL, LEVELS],
    ];
    for (const [list, title, viewTitle, columns] of viewPlan) {
      if (viewsBefore[title].some((v) => v.Title === viewTitle)) {
        log('INFO', `'${viewTitle}' already exists on '${title}'. It is read back rather than `
          + 're-created.');
        continue;
      }
      // There is no <Where> here: this is the view a person makes, and narrowing
      // it would answer the question the Id-narrowed control already answers.
      const query = `<GroupBy Collapse="TRUE" GroupLimit="${GROUP_LIMIT}">`
        + columns.map((name) => `<FieldRef Name="${name}"/>`).join('')
        + '</GroupBy>';
      const digest = await getDigest();
      // The three properties library-grouping-probe.js and formatter-xml-probe.js
      // have both sent and had accepted, and nothing more. DefaultView and
      // PersonalView are left to their defaults and read back below rather than
      // asserted into the payload.
      const made = await spPost(`${list}/views`, {
        Title: viewTitle, RowLimit: VIEW_ROW_LIMIT, ViewQuery: query,
      }, digest);
      if (!made.ok) {
        viewErrors.push(`${viewTitle}: HTTP ${made.status} ${clip(made.text, 160)}`);
        continue;
      }
      // The grouped columns have to be projected for a person to see the values
      // the headers name. A failure here is recorded and does not stop the run.
      for (const name of columns) {
        const withField = await getDigest();
        const added = await spPost(
          `${list}/views/getbytitle('${odataName(viewTitle)}')/viewfields/`
          + `addviewfield('${odataName(name)}')`, {}, withField);
        if (!added.ok) {
          log('INFO', `'${viewTitle}': ${name} could not be added to ViewFields: HTTP `
            + `${added.status} ${clip(added.text, 160)}`);
        }
      }
    }

    // Read back rather than trusting the POST. A view found by title is not
    // proof it holds the query that was sent, and how many levels a three-level
    // <GroupBy> actually STORES is a thing nothing here has measured.
    const shapes = [];
    const shapeProblems = [];
    const urls = {};
    const storedLevels = {};
    for (const [list, title, viewTitle, columns] of viewPlan) {
      const held = await spGet(`${list}/views?$top=200`);
      const known = (!readFailed(held) && Array.isArray(held.body.value)) ? held.body.value : [];
      const view = known.find((v) => v.Title === viewTitle) || null;
      if (view === null) {
        shapeProblems.push(`${viewTitle} is not on '${title}' after the write`);
        continue;
      }
      urls[viewTitle] = view.ServerRelativeUrl || null;
      const stored = String(view.ViewQuery || '');
      const levels = (stored.match(/<FieldRef/g) || []).length;
      storedLevels[viewTitle] = levels;
      const grouped = stored.includes('<GroupBy')
        && columns.every((name) => stored.includes(`Name="${name}"`));
      shapes.push(`${viewTitle} on '${title}': ViewQuery ${show(clip(stored, 200))}, RowLimit `
        + `${show(view.RowLimit)}, DefaultView ${show(view.DefaultView)}, ServerRelativeUrl `
        + `${show(view.ServerRelativeUrl)}, and it stored ${levels} <FieldRef> where `
        + `${columns.length} were sent`);
      if (!grouped) {
        shapeProblems.push(`${viewTitle} does not carry a <GroupBy> naming every column sent`);
      }
      if (view.DefaultView === true) {
        shapeProblems.push(`${viewTitle} came back as the DEFAULT view, which it must not be`);
      }
    }
    record('library.large-list.fixture-foldered-ui-views-created',
           'Both views exist and read back carrying the grouping they were sent, and the stored level count is reported',
           viewErrors.length || shapeProblems.length ? 'FAIL' : 'PASS',
           `creation errors ${JSON.stringify(viewErrors)}; read back: ${shapes.join(' | ')}. `
           + `Stored level counts ${show(storedLevels)}. Nothing in this repository has measured `
           + 'how many <FieldRef> children a SharePoint view keeps from a three-level <GroupBy>, '
           + 'so the number is REPORTED rather than asserted: a page showing two levels is a view '
           + 'that stored two rather than a page that rendered two of three. '
           + (shapeProblems.length
             ? `problems: ${shapeProblems.join('; ')}. A view that did not really take voids its `
               + 'browser row, so do not open the page until this reads PASS.'
             : 'Both views carry their <GroupBy>, collapsed, group limit '
               + `${GROUP_LIMIT}, row limit ${VIEW_ROW_LIMIT}, and neither is a default view. The `
               + 'stored query is what the pages below render.'));

    const after = await newestFile(libPath, FILE_NUMBER, FOLDERS);
    const smallAfter = await newestFile(smallPath, SMALL_NUMBER, []);
    const unchanged = after.ok && after.name === before.name && after.number === before.number
      && smallAfter.ok && smallAfter.name === smallNewest.name;
    record('library.large-list.control-ui-foldered-fixture-readable-after-view-writes',
           "CONTROL: is the newest file name the same after the view writes as before them, so the fixture's owner can still resume and verify it",
           !after.ok || !smallAfter.ok ? 'FAIL' : unchanged ? 'UNCHANGED' : 'CHANGED',
           `'${LIB}' before: ${show(before.name)} (${before.number}); after: ${show(after.name)} `
           + `(${after.number}); ${after.why}. '${SMALL}' before: ${show(smallNewest.name)}; `
           + `after: ${show(smallAfter.name)}; ${smallAfter.why}. `
           + (unchanged
             ? 'So creating a view added nothing either resume read can see, and '
               + 'library-large-list-foldered-fixture-probe.js can still verify both fixtures. '
               + '#485 measured the same on a different library; this is that reading taken on '
               + 'the container it actually matters for, because this fixture resume has to walk '
               + 'past three folder rows and fails closed on anything it does not recognise.'
             : "The newest item read by a fixture's own resume query CHANGED. That probe fails "
               + 'closed on a name its pattern does not match, so a fixture that took many pastes '
               + 'to build is now unverifiable by its owner. Re-paste with STATE = 0 and CLEANUP '
               + '= true to remove the two views, then report this row before anything else.'));

    const defaultProblems = [];
    const defaultNotes = [];
    for (const [list, title] of [[libPath, LIB], [smallPath, SMALL]]) {
      const held = await spGet(`${list}/views?$top=200`);
      const known = (!readFailed(held) && Array.isArray(held.body.value)) ? held.body.value : [];
      const now = known.find((v) => v.DefaultView === true) || null;
      const was = defaultBefore[title];
      defaultNotes.push(`'${title}' before ${show(was && was.Title)} (${show(was && was.Id)}), `
        + `after ${show(now && now.Title)} (${show(now && now.Id)})`);
      if (was === null || now === null) defaultProblems.push(`${title}: a default view did not read back`);
      else if (String(was.Id) !== String(now.Id)) defaultProblems.push(`${title}: the default view MOVED`);
    }
    record('library.large-list.control-ui-foldered-default-view-unchanged',
           "CONTROL: is each library's default view the one it was before this probe wrote anything",
           defaultProblems.length ? 'CHANGED' : 'UNCHANGED',
           `${defaultNotes.join('. ')}. `
           + (defaultProblems.length
             ? `${defaultProblems.join('; ')}. Everybody using these libraries now lands somewhere `
               + 'else. Remove the two views with CLEANUP and set the original defaults back by '
               + 'hand.'
             : 'So a person opening either library still lands where they did before, and the '
               + 'rendered legs open the views they mean to.'));

    stampRemaining('NOT REACHED',
                   `STATE was ${STATE}, the setup and REST leg. Each of these is read by opening `
                   + 'a page and pasting again.');

    log('INFO', '');
    log('INFO', 'THE RUN PLAN. One paste per page. Let each page finish rendering first.');
    log('INFO', `  STATE = 1  a document library on this site holding AT LEAST ${CONTROL_FLOOR}`);
    log('INFO', `             file and fewer than ${THRESHOLD}. An empty one cannot answer it.`);
    log('INFO', '             This is the capture control and it comes first on purpose.');
    log('INFO', `  STATE = 2  ${window.location.origin}${urls[VIEW_FOLDERED] || '(not created)'}`);
    log('INFO', `             then navigate INTO the folder '${scopeFolder}'.`);
    log('INFO', '             CANDIDATE address, NOT established by anything in this repository:');
    log('INFO', `             ${window.location.origin}${urls[VIEW_FOLDERED] || ''}`
      + `?id=${encodeURIComponent(scopeFolderPath || '')}`);
    log('INFO', '             If that does not land inside the folder, click into the folder by');
    log('INFO', '             hand and switch to the view by hand. The probe reads which folder');
    log('INFO', '             rendered off the file names, never off the address.');
    log('INFO', `  STATE = 3  ${window.location.origin}${urls[VIEW_MULTILEVEL] || '(not created)'}`);
    log('INFO', 'Screenshot every state. A state whose DOM read is ambiguous is MANUAL, not a pass.');
    log('INFO', `When finished, re-paste STATE = 0 with CLEANUP = true to remove '${VIEW_FOLDERED}'`);
    log('INFO', `and '${VIEW_MULTILEVEL}'.`);
    report();
    return;
  }

  // ==========================================================================
  // STATES 1 to 3: the rendered legs. Nothing below writes.
  // ==========================================================================
  if (!CONFIRMED) {
    log('INFO', 'Would READ the page you are on: its experience markers, its rendered text, its');
    log('INFO', 'group headers and its file names. It writes nothing at all, on any surface.');
    log('INFO', `STATE is ${STATE}. Open the page that state names, let it finish rendering, set`);
    log('INFO', 'CONFIRMED to true and paste again.');
    report();
    return;
  }

  const identity = pageIdentity();
  const experience = experienceScan();
  const banner = bannerScan();

  // ---- STATE 1: the capture control ---------------------------------------
  // Read on a library UNDER the threshold, so a blank grid past 5,000 can be
  // told from a browser that renders no modern list at all.
  if (STATE === 1) {
    const rows = rowScan(FILE_IN_TEXT);
    const listId = identity.ids[0] || null;
    const fixtureIds = [];
    for (const list of [libPath, smallPath]) {
      const read = await spGet(list);
      if (!readFailed(read)) fixtureIds.push(guid(read.body.Id));
    }
    const onFixture = listId !== null && fixtureIds.includes(listId);
    const here = listId === null ? null : await spGet(`web/lists(guid'${listId}')`);
    const hereOk = here !== null && !readFailed(here);
    const items = hereOk ? Number(here.body.ItemCount) : NaN;
    const usable = hereOk && !onFixture && Number.isFinite(items)
      && items >= CONTROL_FLOOR && items < THRESHOLD;
    const rendered = experience.verdict === 'MODERN' && rows.roleRows > 1;
    record('library.large-list.control-ui-modern-renders-below-threshold',
           'CONTROL: does this browser render a modern document library page at all, on a library UNDER the threshold',
           !usable ? 'NOT ESTABLISHED' : rendered ? 'RENDERS' : 'DOES NOT RENDER',
           (!usable
             ? `this page is not a populated library under the threshold: list id ${show(listId)}, `
               + `ItemCount ${show(hereOk ? here.body.ItemCount : null)}, is it one of the two `
               + `fixtures ${show(onFixture)}. Open a document library on this site holding at `
               + `least ${CONTROL_FLOOR} file and fewer than ${THRESHOLD}, and paste again. An `
               + 'EMPTY library renders no file row however well this browser works, so it reads '
               + 'the same as a browser that renders nothing and cannot answer this control.'
             : `'${show(here.body.Title)}' holds ${items} item(s), under the ${THRESHOLD} `
               + 'threshold. ')
           + `experience ${experience.verdict}: ${experience.detail}. rows: ${rows.roleRows} `
           + `element(s) with role="row", ${rows.roleGrids} with role="grid", page text `
           + `${rows.textLength} char(s) from ${rows.textSource}. `
           + (!usable ? ''
             : rendered
               ? 'So this browser does render a modern library page, and a page past the '
                 + 'threshold that shows nothing is a finding about the threshold rather than '
                 + 'about the capture lane. Every rendered row below depends on this one.'
               : 'This browser renders NOTHING usable on a library it is not being throttled on, '
                 + 'so a blank grid past 5,000 would say nothing at all. '
                 + 'view-aggregations-probe.js records the same constraint and provisions its '
                 + 'fixture classic because of it. Every rendered row below is VOID until this '
                 + 'reads RENDERS.'));
    stampRemaining('NOT REACHED',
                   'STATE was 1, the capture control. Open the two fixture pages and paste again '
                   + 'with STATE 2 and STATE 3.');
    report();
    return;
  }

  // ---- STATES 2 and 3 both read a fixture library's own page --------------
  const wanted = STATE === 2 ? LIB : SMALL;
  const wantedPath = STATE === 2 ? libPath : smallPath;
  const wantedRead = await spGet(wantedPath);
  const wantedId = !readFailed(wantedRead) ? guid(wantedRead.body.Id) : null;
  const matched = wantedId !== null && identity.ids.includes(wantedId);
  record('library.large-list.control-ui-foldered-page-identity',
         'CONTROL: does the rendered page say, in its own JavaScript context, which fixture library it belongs to',
         wantedId === null ? 'NOT ESTABLISHED' : matched ? 'MATCHES' : 'DOES NOT MATCH',
         `STATE ${STATE} expects '${wanted}', which reads list Id ${show(wantedId)} over REST. `
         + `${identity.detail}. experience ${experience.verdict}: ${experience.detail}. `
         + (matched
           ? 'So the page under measurement is the library this state is about, established from '
             + 'the page rather than from the address bar. A modern list page rewrites its own '
             + 'URL and a view parameter says what was asked for rather than what rendered, which '
             + 'is why the address is recorded and never part of a verdict.'
           : 'The rendered page does not claim to be the library this state is about, so whatever '
             + 'it shows is about some other container. Open the URL the setup leg printed and '
             + 'paste again.'));

  if (banner.matched.length) {
    record('library.large-list.ui-threshold-banner-text',
           'What does the rendered threshold refusal actually say, where one appears',
           'FOUND',
           `phrases matched ${JSON.stringify(banner.matched)}; text around the first match `
           + `${show(banner.around)}; role="alert" text ${JSON.stringify(banner.alerts)}; UI `
           + `culture ${show(banner.culture)}. These are English phrases, so on a non-English `
           + 'tenant this row says nothing. Recognising the RENDERED refusal is a different '
           + 'capability from recognising the REST one.');
  }

  // A rendered state is only readable when the page is the library the state
  // names and something client-rendered served it. Otherwise the row is void
  // rather than a threshold result: a page that did not arrive and a page that
  // refused look identical.
  const readable = matched && experience.verdict !== 'CLASSIC';
  const voidWhy = !matched
    ? 'the rendered page did not identify itself as the library this state is about, so this row '
      + 'is about some other container'
    : 'the page rendered as CLASSIC, so this row would be about the renderer the REST probes '
      + 'already answer for';

  if (STATE === 2) {
    const rows = rowScan(FILE_IN_TEXT);
    const seenFolders = foldersRendered(rows.names);
    const folderKeys = Object.keys(seenFolders);
    const oneFolder = folderKeys.length === 1;
    record('library.large-list.control-ui-folder-scope-rendered',
           'CONTROL: is the rendered page showing ONE folder, read from the file names it rendered rather than from its address',
           !readable ? 'NOT ESTABLISHED'
             : rows.fileNames === 0 ? 'NO FILE NAME RENDERED'
               : oneFolder ? `SCOPED TO ${folderKeys[0]}` : 'NOT SCOPED TO ONE FOLDER',
           !readable ? voidWhy
             : `${rows.fileNames} distinct fixture file name(s) in the rendered text, sample `
               + `${JSON.stringify(rows.sample)}. Mapping each through the fixture's own folder `
               + `formula puts them in ${show(seenFolders)}. ${rows.roleRows} element(s) carry `
               + `role="row". OBSERVED and never part of this verdict: the address is `
               + `${show(String(window.location.href))}. `
               + (rows.fileNames === 0
                 ? 'No file name rendered at all. A COLLAPSED grouped view shows none, so this is '
                   + 'not a failure on its own: read it beside the group headers below and beside '
                   + 'the screenshot. What it does mean is that this row cannot confirm the '
                   + 'folder, so the crux below is reported without it.'
                 : oneFolder
                   ? 'Every rendered name belongs to one folder, so the page is showing that '
                     + 'folder and the crux below is a folder-scoped reading. This is read from '
                     + 'the file numbering, which is a fact about the fixture that no UI update '
                     + 'can rename, because nothing here has measured which query parameter a '
                     + 'modern library page takes a folder on.'
                   : 'Names from more than one folder rendered, so this page is NOT scoped to a '
                     + 'folder and the crux below is a library-wide reading wearing a '
                     + 'folder-scoped label. Navigate into the folder by hand and paste again.'),
           readable ? undefined : 'void');

    const groups = groupScan(CHOICES);
    const scoped = oneFolder;
    const rendered = groups.headers.length >= 1;
    const maybe = !rendered && groups.expanderCount >= 2;
    record('library.large-list.ui-group-by-indexed-column-folder-scoped',
           `THE RENDERED CRUX: does the modern page render a grouped view scoped to a folder under ${THRESHOLD} files inside a library over ${THRESHOLD}`,
           !readable ? 'NOT ESTABLISHED'
             : banner.matched.length ? 'REFUSED (banner)'
               : !scoped ? 'MANUAL (the folder scope was not confirmed)'
                 : rendered
                   ? (groups.counted.length ? 'GROUPS AND COUNTS RENDER' : 'GROUPS RENDER, NO COUNTS READ')
                   : maybe ? 'MANUAL' : 'NOTHING GROUPED RENDERED',
           !readable ? voidWhy
             : `${groups.detail}. ${groups.expanderCount} element(s) carry aria-expanded, showing `
               + `${JSON.stringify(groups.expanders)}. ${rows.fileNames} fixture file name(s) `
               + 'rendered (a collapsed group shows none, so zero here is not a failure). banner '
               + `phrases ${JSON.stringify(banner.matched)}; UI culture ${show(banner.culture)}. `
               + `The folder scope control above read ${show(seenFolders)}. `
               + (banner.matched.length
                 ? 'The modern page refuses this grouped view even inside a folder. Read it '
                   + 'beside the REST crux: if both refuse, the threshold is a property of the '
                   + 'LIST rather than of the row set, at both layers, and the generator rule '
                   + 'that refuses a group-by on a large container is right as stated.'
                 : !scoped
                   ? 'Whatever rendered, this page was not confirmed to be showing one folder, so '
                     + 'it cannot answer a folder-scoping question. Navigate into the folder by '
                     + 'hand and paste again rather than reporting this as a result.'
                   : rendered
                     ? 'The modern page RENDERS a grouped view inside a folder holding fewer than '
                       + '5,000 files, in a library holding more. This is the row #485 registered '
                       + 'and left open for want of exactly this fixture. Read it beside the REST '
                       + 'crux: if REST refuses and the page renders, then a group-by is a '
                       + 'UI-experience feature and every REST caller, meaning API flows, Power '
                       + 'BI and automation, needs a filtered or folder-scoped query instead. '
                       + 'Report the screenshot with it.'
                     : maybe
                       ? 'Collapsible regions are on the page but no leaf element read as a group '
                         + 'header, meaning a label followed by a parenthesised count, so what '
                         + 'rendered is not established from the DOM. Read the screenshot and '
                         + 'report which it is.'
                       : 'Neither group labels nor a banner. Read this beside STATE 1 and the '
                         + 'screenshot rather than as a threshold result.'),
           readable ? undefined : 'void');
    stampRemaining('NOT REACHED',
                   'STATE was 2, the folder-scoped grouped view. Paste again with STATE 3 on the '
                   + 'small library.');
    report();
    return;
  }

  if (STATE === 3) {
    const rows = rowScan(SMALL_IN_TEXT);
    // The first level's labels are the four Choice values and are known exactly.
    // The second level is Yes/No and the third is 'mtext-N', both of which are
    // text a page could carry for other reasons, so all three are scanned and
    // which level each hit belongs to is reported rather than assumed.
    const first = groupScan(CHOICES);
    const second = groupScan(['Yes', 'No']);
    const third = groupScan(['mtext-0', 'mtext-1', 'mtext-2', 'mtext-3', 'mtext-4']);
    const levelsSeen = [first, second, third].filter((scan) => scan.headers.length >= 1).length;
    record('library.large-list.ui-group-by-multilevel-renders',
           'Does the modern page render three group levels on the small library',
           !readable ? 'NOT ESTABLISHED'
             : banner.matched.length ? 'REFUSED (banner)'
               : levelsSeen === 0
                 ? (first.expanderCount >= 2 ? 'MANUAL' : 'NOTHING GROUPED RENDERED')
                 : `${levelsSeen} OF 3 LEVELS RENDER HEADERS`,
           !readable ? voidWhy
             : `level 1 on ${M_CHOICE}: ${first.detail}. level 2 on ${M_FLAG}: ${second.detail}. `
               + `level 3 on ${M_TEXT}: ${third.detail}. ${first.expanderCount} element(s) carry `
               + `aria-expanded, showing ${JSON.stringify(first.expanders)}. ${rows.fileNames} `
               + `fixture file name(s) rendered; ${rows.roleRows} element(s) with role="row"; `
               + `banner phrases ${JSON.stringify(banner.matched)}. This library holds `
               + `${SMALL_FILES} files and nothing on it is near the threshold, so anything that `
               + 'fails here fails for the SHAPE of the view. '
               + 'How many levels the view actually STORED is on the views-created row from '
               + 'STATE 0: a page showing two levels may be a view that stored two, and the two '
               + 'readings have to be quoted together. '
               + (levelsSeen === 3
                 ? 'All three levels put a header on the page, so the modern renderer handles a '
                   + 'depth the REST surface refused on a large library.'
                 : levelsSeen > 0
                   ? 'Fewer than three levels put a header on the page. A modern grouped page '
                     + 'materialises groups near the viewport and expands the first, so a level '
                     + 'absent here is not necessarily a level absent from the view. Read the '
                     + 'screenshot and the stored level count together.'
                   : 'No leaf element read as a group header at any level. Read the screenshot '
                     + 'and report what it shows rather than treating this as a refusal.'),
           readable ? undefined : 'void');
    stampRemaining('NOT REACHED',
                   'STATE was 3, the three-level view. Every other row is read at its own state.');
    report();
    return;
  }

  log('FAIL', `STATE is ${STATE}, which is not one of 0, 1, 2 or 3. Nothing was read.`);
  report();
})();
