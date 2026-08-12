/**
 * dbml-sharepoint PROBE — SEARCH AS A FLEET DISCOVERY MECHANISM
 *
 * STATUS: RUN TWICE, both on 2026-08-12, both BY THE REPORTING SERVICE
 * ACCOUNT, both read-only (ALLOW_WRITES off) with RUNNING_AS_READER = true,
 * on two DIFFERENT sites. S1-S10 ANSWERED. S11/S12 still NOT ESTABLISHED.
 *
 *   RUN 1 — probe revision 1c65a683, pasted ON THE ACCOUNT'S OWN ONEDRIVE
 *   rather than on a register site. S1-S9 answered. S10 REFUSED, correctly,
 *   and for a reason nobody had anticipated: a user is ALWAYS site
 *   collection administrator of their own OneDrive, so IsSiteAdmin came
 *   back true and carried no information about privilege at all.
 *
 *   RUN 2 — probe revision ac2ea2a0, pasted ON A REGISTER SITE, which is
 *   the configuration RUN A was always meant to use. IsSiteAdmin came back
 *   FALSE. S10 IS ANSWERED, and it is the central question of this file.
 *   S9's interval closed from above. And S11 exposed a defect in its own
 *   prerequisite, since fixed — see the S11/S12 section.
 *
 * Everything this block does not list is still NOT ESTABLISHED. Do not cite
 * a row it does not say was measured, and do not let a plausible-sounding
 * expectation in a comment be read as a result.
 *
 * ---- WHAT RUN 1 MEASURED (2026-08-12, on the account's OneDrive) -------
 *   S1  CONTROL HELD. `_api/search/query` answered this caller: a trivial
 *       query came back with a reported TotalRows in the low thousands. So
 *       the rows below are about the questions they asked rather than about
 *       the endpoint — and the reporting identity is NOT refused search.
 *   S2  `contentclass:STS_List` RETURNS ROWS. Reported total 1665. The
 *       mechanism enumerates LISTS; Learn only ever sampled STS_Site.
 *   S3  THE DECISIVE ONE, AND IT WENT THE CHEAP WAY. A single STS_List row
 *       carries a stable list GUID AND a web URL TOGETHER. Present BY
 *       DEFAULT, with no `selectproperties` at all: ListId, WebId, SiteId,
 *       SPWebUrl, Path, OriginalPath, Title, Description, WebTemplate,
 *       contentclass, LastModifiedTime, ParentLink. SPSiteUrl was ABSENT by
 *       default but returned a non-empty value when REQUESTED explicitly
 *       through selectproperties. So a consumer can build a REST path from
 *       ONE search row with NO SECOND CALL — which is precisely what
 *       separated this from the N+1 per-site approach the design exists to
 *       avoid.
 *   S4  NO FALSE POSITIVES OBSERVED, ON A TENANT THAT DID NOT CONTAIN THE
 *       CASE THAT WOULD PRODUCE THEM. Three query variants — Title as a
 *       quoted phrase, Title bare, and free-text quoted — each returned
 *       exactly ONE row, whose title equalled the sought title character
 *       for character, and zero non-matching rows.
 *       THE EVIDENCE IS WEAK AND MUST BE QUOTED AS SUCH. This tenant holds
 *       no list whose title is a PREFIX of another list's title, and that
 *       is the case word-breaking would expose. THIS RUN DOES NOT ESTABLISH
 *       THAT TITLE MATCHING IS EXACT; it establishes that nothing spurious
 *       came back on a tenant that had nothing spurious to give. Learn
 *       still documents KQL text properties as word-broken unless
 *       "Complete matching" is turned on.
 *   S5  LIST `Description` IS CRAWLED AND RETURNED. Of 50 rows, all 50
 *       carried a Description cell and 15 carried a NON-EMPTY value. So a
 *       marker token planted in a list description is a viable discovery
 *       key. Whether such a token matches EXACTLY is S6, still unrun.
 *   S7  THE ROW CEILING IS 500, AND DISCOVERY MUST PAGE. rowlimit=1 gave 1,
 *       10 gave 10, 500 gave 500, and 1000 GAVE 500. The reported total was
 *       1665, far above the ceiling, so a fleet discovery query on this
 *       tenant CANNOT be a single call. `startrow` PAGING WORKED: page 2
 *       held rows none of which were on page 1, compared over the whole
 *       row rather than on one property.
 *   S8  THE `STS_Site` FALLBACK WORKS TOO. 36 sites reported, each carrying
 *       SPSiteUrl, Title, WebTemplate, and Description where one was set.
 *       Plan B exists and has been measured, not assumed.
 *   S9  CRAWL LATENCY IS GREATER THAN ~2.4 HOURS, AND THAT IS A LOWER BOUND
 *       ONLY. A list created about 2.4 hours before the run was NOT in the
 *       index at run time. That bounds latency FROM BELOW and says nothing
 *       about how much longer than 2.4 hours it is. Run 2 supplied the
 *       upper bound; see below. Anyone quoting "2.4 hours" as the latency
 *       is quoting the bound as the value.
 *   S10 NOT ESTABLISHED, and the refusal was RIGHT. See the next section.
 *       Run 2 answered it.
 *   S11 NOT ESTABLISHED, and S12 with it: unmet prerequisite, unchanged.
 *       PAGING_FIXTURE_LIST is not on the site that was pasted into. Both
 *       still need the operator run, RUN B.
 *   S6  Did not run: ALLOW_WRITES was off.
 *
 * ---- WHAT RUN 2 MEASURED (2026-08-12, on a register site) -------------
 * SAME ACCOUNT, SAME FLAG, DIFFERENT SITE — and that is the whole point of
 * the repeat. Read it alongside run 1 rather than instead of it: the two
 * corroborate each other where they overlap, and only run 2 can speak to
 * S10.
 *
 *   S10 ANSWERED, AND IT IS THE CENTRAL QUESTION OF THIS PROBE.
 *       `IsSiteAdmin` came back FALSE, so the caller really was the
 *       list-only reporting identity: not a member of any site, holding
 *       Read at list scope plus whatever Limited Access SharePoint derives
 *       at web scope. The endpoint SERVED it and it RETURNED ROWS.
 *       PERMISSION-TRIMMED DISCOVERY IS REACHABLE FROM LEAST PRIVILEGE on
 *       this tenant. That is the finding the design was waiting for.
 *       AND IT IS ONE ACCOUNT, ONE SITE, ONE MOMENT. It is a data point,
 *       not a rule about SharePoint trimming, and the probe's own caveat
 *       travels with it wherever it is quoted.
 *   S4  THE READER FOUND ITS OWN GRANTED LIST BY TITLE. Run as this
 *       identity, all three query variants returned exactly ONE row for the
 *       sought title, character for character, with zero non-matching rows.
 *       That is the discovery mechanism working END TO END under the
 *       configuration the design would actually ship. The tokenisation
 *       caveat from run 1 is UNCHANGED — this tenant still holds no title
 *       that is a prefix of another — so this says the mechanism works
 *       here, not that title matching is exact.
 *   S1  S2  S7  S8  SAME TOTALS AS RUN 1, AND THAT IS THE EXPECTED RESULT.
 *       STS_List reported 1665, STS_Site 36, and the trivial control query
 *       1645 — identical to run 1, from a different pasting site. Search
 *       trims on the IDENTITY, not on the site the console was opened on,
 *       so identical totals across two sites is what should happen. It
 *       corroborates both runs rather than adding a new fact.
 *   S9  CRAWL LATENCY IS NOW BOUNDED ON BOTH SIDES: somewhere between
 *       roughly 2.4 AND 15 HOURS on this tenant. A list created 15.0 hours
 *       before run 2 WAS present in the index.
 *       READ IT AS AN INTERVAL ESTIMATE, NOT AS A MEASUREMENT. The two
 *       bounds come from TWO DIFFERENT LISTS — one absent at ~2.4 hours in
 *       run 1, a different one present at 15.0 hours in run 2 — so nothing
 *       here tracked a single list's journey into the index. The true
 *       latency for any one list may sit anywhere in that band or outside
 *       it; what is established is that this tenant does crawl new lists
 *       within a working day, and does not do it within a couple of hours.
 *   S11 STILL NOT ESTABLISHED, and S12 with it — but for a reason worth
 *       recording, because the row as written would have reported it as a
 *       platform catastrophe. See the next section but one.
 *   S6  Did not run: ALLOW_WRITES was off.
 *
 * ---- THE BREADTH OF THE TRIMMED SET IS A DESIGN CONSTRAINT ------------
 * The reader's own view spanned MANY SITES — intranet and hub content, and
 * another user's personal site. Almost certainly because that content is
 * readable by ANY AUTHENTICATED USER on this tenant.
 *
 * RECORD IT NEUTRALLY. It is NOT evidence that the reader tier leaks, and
 * it is not evidence that it does not: THIS PROBE CANNOT TELL "BROADLY
 * READABLE" FROM "OVER-GRANTED". Only whoever made the grants can. Saying
 * more than that from a result set would be inventing a security finding.
 *
 * WHAT IT DOES ESTABLISH IS A REQUIREMENT, and it is hard: A BARE
 * `contentclass:STS_List` QUERY IS NOWHERE NEAR "OUR" LISTS. Fleet
 * discovery MUST be constrained by something specific — a planted marker
 * token, an exact title, or a path prefix — and must never treat what a
 * bare query returns as the fleet.
 *
 * ---- WHERE RUN 1 WAS PASTED, AND WHY IT MATTERS -----------------------
 * ON THE SERVICE ACCOUNT'S OWN ONEDRIVE — a personal site, on the `-my.`
 * host under a `/personal/<account>` path — and NOT on a register site it
 * had been granted lists on. A USER IS ALWAYS SITE COLLECTION ADMINISTRATOR
 * OF THEIR OWN ONEDRIVE, so web/currentuser reported IsSiteAdmin=true, and
 * S10 refused to file the run as a least-privilege measurement.
 *
 * THE REFUSAL STANDS AND HAS NOT BEEN WEAKENED. What changed is its
 * REASONING. As written, S10 read IsSiteAdmin=true as evidence that the
 * caller was not the least-privilege identity — and on a personal site that
 * inference is simply wrong. Every account is an administrator there, so
 * the bit carries NO information about tenant-wide privilege. Left as it
 * was, S10 would have refused every future run for the wrong reason and
 * sent the operator hunting a privilege problem that does not exist. It now
 * detects a personal site and says which of the two cases it is in.
 *
 * RUN A WAS THEREFORE REPEATED, on a NON-PERSONAL register site where the
 * reporting account is not an administrator. That is run 2, above, and it
 * is where S10's answer comes from. This section is kept because the trap
 * is easy to fall into again — see HOW TO RUN.
 *
 * IT IS NOW MEANT TO BE PASTED BY THE REPORTING SERVICE ACCOUNT, not by an
 * operator. This file was written assuming the opposite, and the change is
 * not administrative — it changes what the central question measures.
 *
 * That account holds ONLY list-scoped `Read` plus the `Limited Access`
 * SharePoint derives at web scope. IT IS NOT A MEMBER OF ANY SITE. On
 * 2026-08-12 it nonetheless ran a console probe on a site it does not
 * belong to: it loaded the page, called REST, enumerated `web/siteusers`,
 * read the site collection features and POSTed `web/ensureuser`. It WAS
 * REFUSED `getusereffectivepermissions` for a named principal at both web
 * and list scope — HTTP 403, UnauthorizedAccessException — because it does
 * not hold `EnumeratePermissions`. (See enterprise-reader-probe.js.j2,
 * run 2. That is an observation about one account on one site, not a rule
 * about SharePoint.)
 *
 * Three consequences, all of them wired into the code below:
 *
 *   S10 CHANGES MEANING ENTIRELY. "Not answerable" is the honest answer
 *       for a PRIVILEGED caller and the wrong one for this account. Run by
 *       the list-only reporting identity, THE RESULT SET IS THE
 *       MEASUREMENT: what comes back IS the trimmed view, and whether it
 *       contains anything at all is what decides whether search-driven
 *       discovery can work under least privilege. Set RUNNING_AS_READER =
 *       true so S10 knows which run this is. THE FLAG IS NOT TRUSTED ON
 *       ITS OWN: web/currentuser is read every run and the caller's login
 *       printed beside the answer, and S10 refuses to answer at all if the
 *       flag says reader while the caller reads back as a site collection
 *       administrator.
 *   A 403 IS A FINDING, NOT A BROKEN PROBE. Several questions may now be
 *       refused outright. "The reporting identity is refused this
 *       endpoint" is precisely what the design needs to know, so a 401/403
 *       is recorded as an OBSERVED refusal ATTRIBUTABLE TO THIS CALLER'S
 *       PRIVILEGE — never as a fact about SharePoint in general, and never
 *       as the run having failed.
 *   S1 GATES EVERY OTHER SEARCH ROW. If the control does not hold, the
 *       rest record NOT ESTABLISHED (control open) and carry whatever they
 *       read as supporting detail only — the same downgrade
 *       enterprise-reader-probe.js.j2 now applies to its A3 and A4, added
 *       there because a row that contradicts its own control had recorded
 *       itself as OBSERVED.
 *
 * ---- WHY THIS PROBE EXISTS --------------------------------------------
 * The generated Power BI pack needs one query per list per site, written by
 * hand and duplicated for every site added. The fleet is 100+ sites and
 * unbounded, so that does not scale and every new site is a query edit.
 *
 * What we want instead is DATA-DRIVEN, PERMISSION-TRIMMED discovery:
 * granting the reporting service account access to another site makes its
 * data appear with NO query edits at all.
 *
 * The candidate mechanism is SharePoint Search, because Learn confirms it
 * is security-trimmed at query time — the account submitting the query
 * sees only what it may see, which is exactly the property the design
 * needs. The DECISIVE UNKNOWN is whether search can enumerate LISTS
 * cheaply enough to avoid falling back to a per-site probe: if discovery
 * costs one call per site, it is no better than what we have.
 *
 * ---- WHAT IS ALREADY ESTABLISHED ON MICROSOFT LEARN --------------------
 * Cited, NOT re-derived. These are the reason the questions below are the
 * right questions; none of them is what this probe measures.
 *
 *   - The Search REST service lives at `_api/search/query` (GET) and
 *     `_api/search/postquery` (POST), with a second endpoint `suggest`.
 *     ("SharePoint Search REST API overview"; "What's new in SharePoint
 *     search for developers".)
 *   - GET parameter spellings, all taken from that overview page rather
 *     than from memory: `querytext='...'`, `selectproperties='A,B'`,
 *     `rowlimit=N`, `rowsperpage=N`, `startrow=N`, `sortlist='...'`.
 *     JSON comes back only if you ask: `accept: application/json;odata=
 *     verbose`, or `;odata=nometadata` if you do not want metadata.
 *     Default is XML.
 *   - `contentclass:"STS_Site"` is a documented, Microsoft-sampled filter,
 *     and `Title`, `SPSiteUrl`, `Description` and `WebTemplate` are
 *     selectable there. ("Search customizations for SharePoint", the
 *     KeywordQuery/SelectProperties sample; "Personalize search results
 *     sample SharePoint Add-in".)
 *   - Search performs SECURITY TRIMMING based on the identity submitting
 *     the query. This is the whole reason the mechanism is a candidate.
 *   - 500 rows is the documented boundary for the number of rows in a
 *     result set, raisable to 10,000 via MaxRowLimit, and `StartRow` is
 *     capped at 50,000. ("Search limits for SharePoint"; "Software
 *     boundaries and limits"; "Pagination for large result sets", which
 *     also documents the `indexdocid`+`sortlist='[docid]:ascending'` idiom
 *     for paging past that.)
 *   - KQL text properties are WORD-BROKEN AND TOKENISED, so an exact match
 *     on a text property is NOT guaranteed. Learn's search-schema page
 *     documents "Complete matching" as a per-managed-property setting that
 *     has to be turned ON to get exact matches instead of partial ones,
 *     and a full crawl or reindex after changing it.
 *
 * ---- WHAT IS *NOT* ESTABLISHED, AND IS THE POINT OF THIS FILE ----------
 * THE ORIGINAL FIVE UNKNOWNS, ANNOTATED WITH WHAT THE TWO 2026-08-12 RUNS
 * DID AND DID NOT CLOSE. They are kept rather than deleted, because the
 * shape of the question is what makes the answer readable.
 *
 *   1. That `contentclass:STS_List` enumerates LISTS at all. Learn samples
 *      STS_Site. It says nothing here about STS_List.
 *      CLOSED 2026-08-12 — it does, on one tenant, for one identity (S2).
 *   2. What identity properties come back WITH a list row. The design
 *      needs a stable list GUID and a site/web URL IN THE SAME ROW, so a
 *      consumer can build a REST path without a second call per hit. If
 *      that costs a second call, the mechanism has not bought anything.
 *      CLOSED 2026-08-12 — ListId and SPWebUrl both arrive by default, no
 *      second call needed (S3).
 *   3. Whether a list's Description is crawled, and whether a marker token
 *      planted in one is exact-matchable — the candidate way to tag which
 *      lists are ours without relying on titles.
 *      HALF CLOSED 2026-08-12 — Description IS crawled and returned (S5).
 *      Whether a token in one is EXACT-matchable is S6 and is still open;
 *      it needs the two-paste procedure and a crawl interval now bracketed
 *      by S9 at roughly 2.4 to 15 hours, so plan the second paste for the
 *      next day rather than the same afternoon.
 *   4. Whether ANY of it is reachable by the reporting service account —
 *      the identity the whole design would run as. See the STATUS block.
 *      CLOSED 2026-08-12 BY RUN 2 — pasted on a register site, IsSiteAdmin
 *      false, the endpoint served the account and returned rows, and the
 *      list it had been granted came back by title (S10, S4). A LIST-SCOPED
 *      GRANT IS ENOUGH TO MAKE A LIST DISCOVERABLE, on this tenant, for
 *      this account, at this moment.
 *   5. Whether SharePoint REST on this tenant emits a SERVER-DRIVEN
 *      continuation at all. Unrelated to search; see the paging section
 *      below for why it is asked here.
 *      STILL OPEN — S11/S12 had an unmet prerequisite on BOTH 2026-08-12
 *      runs and need RUN B, pasted by an operator who can read the
 *      fixture's ITEMS and not merely its metadata.
 *
 * And one unknown the runs ADDED, which nobody had written down: whether a
 * discovery query can be constrained tightly enough to return only the
 * fleet. Run 2 turned that from a question into a REQUIREMENT — see "the
 * breadth of the trimmed set" in the STATUS block.
 *
 * ---- THE ONE RULE THIS FILE IS BUILT AROUND ---------------------------
 * A measurement's inputs and its outputs are different kinds of value.
 *
 *   DEPENDS ON — the query sent, the constants the operator set, the site
 *   pasted into, the endpoint spelling. Wrong values here invalidate the
 *   run, so these ARE checked, and a bad one is reported as an unmet
 *   PREREQUISITE rather than as a finding about SharePoint.
 *
 *   OBSERVES — the row count, the total, the property names that come
 *   back, the titles that come back, the status code. NOTHING in this file
 *   asserts over any of these. Not one row says PASS or FAIL on the
 *   strength of a number it went looking for.
 *
 * That distinction is not a style preference. A probe here already broke
 * this rule and had to be rewritten: it asserted over a value it was
 * measuring, so the experiment killed itself the moment it started
 * working, and the failure was indistinguishable from a real one. So every
 * row below is `OBSERVED — <what was seen>`, and the evidence carries the
 * numbers. A reader decides what it means; the probe does not.
 *
 * ---- WHAT IT ASKS -----------------------------------------------------
 *
 * READ-ONLY. These run with the write flag OFF and write nothing.
 *
 *   S1  CONTROL, AND IT GATES THE REST. Does `_api/search/query` answer
 *       THIS caller at all, for a trivial query? Without it, every search
 *       row below is a fact about the endpoint rather than about the
 *       question it was asked — so while S1 is open, S2-S9 record NOT
 *       ESTABLISHED (control open) and print what they read as supporting
 *       detail. NOTE: zero rows still answers S1 — the control is about
 *       the endpoint ANSWERING, and requiring rows would make the control
 *       assert over an observation. A 403 here IS an answer to S1: it says
 *       this caller is refused the endpoint, which for the reporting
 *       identity is one of the two outcomes the design is waiting on.
 *   S2  Does `contentclass:STS_List` return rows? How many, and what total
 *       does the result set report?
 *   S3  For the first row, EVERY property name returned and its value.
 *       Nothing is assumed to exist — not ListId, not WebId, not Path, not
 *       SPSiteUrl, not SPWebUrl. The dump IS the answer. A second query
 *       then explicitly REQUESTS a candidate set, and requesting a name is
 *       recorded as a request, never as evidence the name exists.
 *   S4  Tokenisation, and whether a list TITLE can be a search key at all.
 *       Queries for the configured title and records EVERY title that came
 *       back, not merely whether the expected one did. A query that also
 *       returns `<Title> Archive` IS THE FINDING, and a probe that only
 *       looked for its own title would have thrown it away.
 *   S5  Is a list's Description returned by an STS_List query? Guarded by
 *       a PREREQUISITE: if no list in reach has a description at all, that
 *       is an unmet prerequisite and is recorded as one. It is NOT
 *       "descriptions are not crawled", and the two look identical from
 *       the result set alone.
 *   S7  The row-limit ceiling and how the result set pages. Returned row
 *       count against reported total, at several limits including one
 *       above Learn's documented 500-row boundary.
 *   S8  The `contentclass:"STS_Site"` fallback — plan B, and the mechanism
 *       Learn actually documents. Measured EVEN IF S2 succeeds: a design
 *       that has only measured its plan A has no plan B.
 *   S9  Crawl latency. Records the run timestamp and whether recently
 *       created content is in the index yet, so a SECOND run can bound it.
 *       ONE RUN CANNOT ANSWER THIS and the row says so in its own
 *       evidence.
 *   S10 Security trimming, AND WHAT IT MEANS DEPENDS ON WHO PASTED IT.
 *       From a privileged account it is not answerable and says so. From
 *       the list-only reporting identity the returned set IS the trimmed
 *       view and therefore IS the answer. See the S10 section below.
 *   S11 SERVER-DRIVEN PAGING, measured against a 6,000-row fixture that
 *       already exists. Reads that list's items with NO `$top` at all and
 *       records how many rows came back and whether a continuation link
 *       came with them. Guarded by a PREREQUISITE that asks whether this
 *       caller can see ANY item in the fixture, because a trimmed caller
 *       and a truncating server look identical from a row count alone.
 *       See the paging section below for what this does and does not
 *       settle, and who should run it.
 *   S12 Follows that link once, and records whether the second page holds
 *       DIFFERENT rows — because a second page that repeats the first
 *       would look like paging and would not be.
 *
 * WRITE-GATED. Default OFF; the run is useful without it.
 *
 *   S6  The marker question. CREATES A LIST whose Description carries a
 *       distinctive machine-readable token, then queries for that token
 *       and records whether it matched EXACTLY, PARTIALLY, or NOT AT ALL.
 *       See the two warnings below — they are the difference between an
 *       answer and a fabricated one.
 *
 * ---- S10: TWO RUNS, TWO MEANINGS, AND ONLY ONE OF THEM IS AN ANSWER ----
 * ANSWERED ON 2026-08-12 BY RUN 2, and this section is kept because it is
 * what makes that answer readable. The first branch below is the one run 1
 * hit; the last is the one run 2 hit.
 *
 * PASTED BY A PRIVILEGED ACCOUNT, S10 IS NOT ANSWERABLE. Trimming cannot
 * be demonstrated by an account that can see everything: a trimmed result
 * and an untrimmed result ARE IDENTICAL to such a caller — both return
 * everything that account may see, which is everything. Running this as a
 * site collection administrator and getting a full result set is not weak
 * evidence that trimming works; it is no evidence at all. That branch is
 * still in the code, unchanged, and it still refuses.
 *
 * PASTED BY THE LIST-ONLY REPORTING IDENTITY, S10 IS THE MEASUREMENT THE
 * DESIGN IS WAITING FOR. That account is not a member of any site and
 * holds Read on lists only. Whatever `_api/search/query` hands it IS the
 * trimmed view, by definition — there is no untrimmed view to compare
 * against and none is needed. Three outcomes, all real answers:
 *
 *   - Rows come back. Search-driven, permission-trimmed discovery is
 *     REACHABLE from least privilege on this tenant, and the rows say
 *     which sites and lists reached it.
 *     THIS IS THE OUTCOME RUN 2 OBSERVED, 2026-08-12.
 *   - Zero rows, endpoint answering. The mechanism is reachable and the
 *     account sees nothing through it — which would mean granting list
 *     Read is not enough to make a list discoverable, and the design needs
 *     a different grant or a different mechanism.
 *   - HTTP 401/403. The account is refused the endpoint outright. That
 *     kills search as a least-privilege discovery mechanism as configured,
 *     and it is a finding, not a failed run.
 *
 * WHICH RUN THIS IS comes from RUNNING_AS_READER, a constant the person
 * pasting sets, default false. A script cannot reliably tell which
 * identity is driving it, so it does not pretend to — but it does not take
 * the flag on faith either: web/currentuser is read every run and the
 * caller's LoginName, Title and IsSiteAdmin are printed beside the answer,
 * so the transcript shows who actually ran it. If the flag says reader and
 * the caller reads back as a site collection administrator, S10 records
 * NOT ESTABLISHED and names the contradiction rather than filing a
 * privileged result set as a least-privilege measurement.
 *
 * AND IsSiteAdmin MEANS TWO DIFFERENT THINGS DEPENDING ON THE SITE, which
 * run 1 found out the hard way. A USER IS ALWAYS SITE
 * COLLECTION ADMINISTRATOR OF THEIR OWN ONEDRIVE. So on a PERSONAL site —
 * the `-my.` host, a `/personal/<account>` path — IsSiteAdmin=true is
 * universal and expected, and it is NOT evidence of privilege of any kind.
 * S10 detects that case and says so in those words. IT STILL REFUSES: the
 * pasted site is the wrong site, not the wrong account, and the fix is to
 * repeat the run on a register site rather than to reason about the bit.
 * On a NON-personal site IsSiteAdmin=true keeps its stronger meaning and
 * the original wording.
 *
 * ---- S11/S12: SERVER-DRIVEN PAGING, AND WHY IT IS ASKED HERE ----------
 * `_security_principals.js.j2` and `_reader_enrolment.js.j2` both page a
 * collection with `$top=5000` and follow `d.__next`. NOBODY HAS CONFIRMED
 * THAT SHAREPOINT REST EMITS `__next` ON SERVER TRUNCATION AT ALL. If it
 * does not, both templates read a first page and stop, silently.
 *
 * The obvious experiment — a site group with more members than the server
 * page size — HAS BEEN DECLINED, on sound grounds: putting a large group
 * into a site's permissions to satisfy a probe would expose many real
 * people to development work. That is settled. It is not asked for here
 * and it is not asked for again anywhere else.
 *
 * So this measures the same platform behaviour against a fixture that
 * ALREADY EXISTS on the tenant and costs nothing: the list named by
 * PAGING_FIXTURE_LIST below, holding 6,000 rows, left in place by the list
 * view threshold work. READ-ONLY. Nothing in this probe writes to it, and
 * IT MUST NOT BE RECYCLED while anything is still being measured against
 * it — rebuilding it costs five batch loads, reading it costs one paste.
 *
 * WHAT S11 AND S12 SETTLE, AND WHAT THEY DO NOT. This is the LIST-ITEMS
 * collection, NOT `sitegroups/users`. A continuation link here establishes
 * that THIS TENANT'S REST EMITS SERVER-DRIVEN PAGING AT ALL, which is the
 * question underneath both templates. It does NOT settle the site-group
 * case: that collection may page differently or not at all, and it remains
 * UNMEASURED and — given the exposure objection above — UNMEASURABLE. Say
 * both halves whenever these rows are quoted.
 *
 * AND AN ABSENT LINK IS NOT PROOF EVERYTHING CAME BACK. On this same
 * fixture an unindexed presence test was measured returning 50 ROWS
 * INSTEAD OF 60, AT HTTP 200 WITH NO ERROR (2026-07-31, see
 * threshold-index-probe.js.j2 and analysis/checks/_views.py). This tenant
 * is already known to truncate silently. So S11 records the row count, the
 * list's ItemCount and the link's presence as three separate observations
 * and draws no conclusion from the absence of the third.
 *
 * RUN THESE TWO AS AN OPERATOR WHO CAN READ THE FIXTURE'S ITEMS. S11 and
 * S12 are IDENTITY-INDEPENDENT PLATFORM QUESTIONS — whether the server
 * emits a continuation token when it truncates does not depend on who
 * asked — so the reporting account is simply the wrong identity to ask
 * them from, and asking anyway produces a row that looks like a platform
 * finding and is not. This is RUN B; see HOW TO RUN.
 *
 * ---- THE S11 PREREQUISITE DEFECT, FOUND AND FIXED 2026-08-12 ----------
 * ITEMCOUNT IS NOT A PREREQUISITE FOR READING ITEMS, and S11 used to treat
 * it as one. Run 2 read the fixture's ItemCount as 5614, requested its
 * items with no `$top`, and got 0 ROWS, HTTP 200, NO CONTINUATION LINK, on
 * both OData flavours. As the row was written that would have been filed —
 * and quoted — as CATASTROPHIC SILENT TRUNCATION.
 *
 * IT ALMOST CERTAINLY WAS NOT. SharePoint trims the LIST-ITEMS collection
 * PER ITEM, and run 2's caller was the reporting service account, which
 * holds no grant on a development fixture. ZERO VISIBLE ITEMS IS THE
 * CORRECT AND EXPECTED OUTCOME for that caller. `ItemCount` is LIST
 * METADATA and reads back without any item access at all, so the
 * prerequisite passed on a signal that does not imply the caller can see a
 * single row.
 *
 * Two changes, both in the code below. The prerequisite now asks the
 * question directly — can this caller see ANY item here, one is enough —
 * and a caller who cannot is an unmet PREREQUISITE, not a result. And a
 * zero-row read is never recorded as a truncation finding: it records NOT
 * ESTABLISHED with item-level trimming named as the leading hypothesis.
 *
 * ---- S6: TWO WARNINGS -------------------------------------------------
 * FIRST: THIS CREATES A LIST. One list, on the site you pasted into,
 * titled by MARKER_LIST_TITLE below. It is RECYCLED, NOT PURGED, when you
 * finally clean up — it goes to the site recycle bin and is restorable.
 * Use a site you are content to leave a probe list on.
 *
 * SECOND, AND IT DECIDES WHETHER S6 MEANS ANYTHING: CRAWL LATENCY ALMOST
 * CERTAINLY MEANS THE ANSWER NEEDS A SECOND PASTE, LATER. A brand-new
 * list's Description is not in the search index the instant it is written.
 * So the expected first-run outcome is "the marker did not match yet", and
 * THAT IS NOT AN ANSWER TO S6. Reporting it as "markers do not work" would
 * be a fabricated platform verdict of exactly the kind this repository
 * exists to prevent.
 *
 * So the run RECORDS THAT EXPECTATION rather than a verdict, and the
 * procedure is:
 *   - Run once with ALLOW_WRITES = true. The list is created and the
 *     marker query almost certainly finds nothing. S6 records the create,
 *     the list's Created timestamp, and NOT ESTABLISHED (awaiting a second
 *     paste).
 *   - LEAVE THE LIST IN PLACE. Come back hours or a day later and paste
 *     the SAME FILE with the SAME MARKER_TOKEN. The second run finds the
 *     list already present, does not recreate it, and queries again. That
 *     run is the one that can answer S6.
 *   - Only when you are finished, set CLEANUP = true for a final tidy-up
 *     run, which recycles the list and answers nothing.
 *
 * NOTE THE DEVIATION FROM THE OTHER PROBES HERE. Elsewhere CLEANUP resets
 * before the run so every question is answered by creating something
 * fresh. THIS PROBE MUST NOT DO THAT: the measurement spans two pastes, so
 * a pre-run reset would destroy the very thing being measured and restart
 * the crawl clock, and the operator would never get an answer no matter
 * how many times they came back. Here CLEANUP is a pure tidy-up switch —
 * it recycles and does not recreate.
 *
 * ---- HOW TO RUN: TWO RUNS, BY TWO DIFFERENT IDENTITIES -----------------
 * This file asks two kinds of question and they do NOT want the same
 * account. Running it once, as either identity, leaves half of it open.
 *
 *   S1-S10 measure WHO IS ASKING. Search trims on the caller's identity,
 *   so only the reporting service account's own result set answers them.
 *   An operator sees everything and would produce a confident wrong
 *   answer -- which is why S10 refuses to read an operator run as a pass.
 *
 *   S11-S12 measure WHAT THE SERVER DOES: whether SharePoint emits a
 *   continuation token when it truncates a 6,000-row read. The identity is
 *   IRRELEVANT to that. An operator measures it exactly as well.
 *
 *   S11 AND S12 MUST BE RUN BY AN OPERATOR WHO CAN READ THE FIXTURE'S
 *   ITEMS, not merely reach the list. SharePoint trims list items PER ITEM,
 *   so a caller with no grant on them is served an empty collection at HTTP
 *   200 — which is correct for that caller and says NOTHING about paging.
 *   Run 2 on 2026-08-12 hit exactly that; the row now detects it and
 *   reports an unmet prerequisite instead of a truncation finding.
 *
 *   RUN A -- as the REPORTING SERVICE ACCOUNT, on a site holding lists it
 *   has actually been granted. Set RUNNING_AS_READER = true and point
 *   LIST_TITLE at one of those granted lists. S11/S12 will report an unmet
 *   prerequisite because that account cannot read the paging fixture's
 *   items. THAT IS CORRECT, not a failure -- take S1-S10 from this run.
 *
 *   RUN A MUST BE PASTED ON A SITE WHERE THE REPORTING ACCOUNT IS NOT AN
 *   ADMINISTRATOR -- i.e. one of the REGISTER SITES it was granted lists
 *   on. Navigate to that site's URL explicitly and check the address bar
 *   before pasting.
 *
 *   THE TRAP, and it is the one that swallowed run 1 on 2026-08-12: OPENING
 *   THE MICROSOFT LISTS APP LANDS ON THE ACCOUNT'S OWN ONEDRIVE. The URL is
 *   on the `-my.` host under `/personal/<account>`, it looks like a
 *   perfectly ordinary SharePoint site, and A USER IS ALWAYS SITE
 *   COLLECTION ADMINISTRATOR OF THEIR OWN ONEDRIVE -- so the run reads back
 *   IsSiteAdmin=true and S10 cannot answer. S1-S9 still measured fine from
 *   there, because search trims on the IDENTITY rather than on the site
 *   pasted into; S10 is the row that needs the right site.
 *
 *   RUN B -- as an OPERATOR WHO CAN READ THE ITEMS OF PAGING_FIXTURE_LIST,
 *   on the site holding it. Leave RUNNING_AS_READER = false. The search
 *   rows will show an untrimmed view and S10 will say so rather than
 *   claiming an answer -- take S11/S12 from this run. STILL OUTSTANDING as
 *   of 2026-08-12: both 2026-08-12 runs were RUN A.
 *
 *   DO NOT GRANT THE READER ACCESS TO THE PAGING FIXTURE to collapse this
 *   into one run. It would not make the paging answer any truer, because
 *   server-side truncation does not depend on who is asking, and it would
 *   put a reporting account on a development fixture for nothing.
 *
 *   1. Edit the constants under CONFIGURATION. LIST_TITLE and MARKER_TOKEN
 *      ship as obvious placeholders, and the questions that need them
 *      refuse to run and say which constant to set, so an unedited paste
 *      never produces a row that looks like a measurement. Set
 *      RUNNING_AS_READER = true if and only if you are signed in as the
 *      reporting service account. There is deliberately NO SITE URL: the
 *      probe reads the site it was pasted into.
 *   2. Open the site for whichever run this is -- a site with granted
 *      lists for RUN A, the site holding PAGING_FIXTURE_LIST for RUN B.
 *      F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED = true and paste again. That answers everything
 *      except S6 and writes nothing.
 *   4. Optionally, on a site you are content to leave a list on: set
 *      ALLOW_WRITES = true as well and paste once more. Then read the S6
 *      warnings above — you will need to come back. The reporting service
 *      account is unlikely to be able to create a list at all; if it is
 *      refused, that refusal is itself a recorded observation.
 *   5. Copy the whole RESULTS block back verbatim, including the evidence
 *      lines. The property dump IS the finding for S3 and S8; a summary of
 *      it is not. The transcript stays OUT of this repository.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // CLEANUP deletes the probe's own list BEFORE the run, so every question
  // is answered by actually creating something rather than reporting
  // "already present" from a previous run — which is much weaker evidence.
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
    console.error('[FATAL] No _spPageContextInfo — paste this into a SharePoint page.');
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
  // so `body !== null` says the response was JSON — never that the call
  // worked. Anything asking "did I actually read this?" must test `ok`.
  const readFailed = (r) => !r.ok || r.body === null;

  // Was this request REFUSED — the server saying no to what was sent — or
  // did it merely fail? A negative control that cannot tell the difference
  // certifies the surface as observable on the strength of a throttle, and
  // every row it guards is then read as evidence.
  //
  // Defined by what it EXCLUDES, because the tempting definition is wrong
  // here. "400 means bad request" is the HTTP convention and it is not what
  // this tenant does: every SharePoint refusal this project has recorded
  // came back 500 —
  //
  //   "To add an item to a document library, use SPFileCollection.Add()"
  //   "One or more column references are not allowed, because the columns
  //    are defined as a data type that is not supported in formulas"
  //   "The formula refers to a column that does not exist"
  //   "This field type does not support..."
  //
  // (analysis/checks/_structure.py, analysis/conditions.py, generators/
  // jsgen.py — each dated and cited to a live run). A 400-only test would
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
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false — not deleting '${title}'.`);
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
    // removed — a locked or no-delete list would otherwise leave rows from
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
  const RESULTS = [];
  const expect = (id, question) => {
    RESULTS.push({ id, question, outcome: 'NOT ESTABLISHED', evidence: 'the run did not reach this question' });
  };
  const record = (id, question, outcome, evidence) => {
    const row = RESULTS.find((r) => r.id === id);
    if (row) {
      Object.assign(row, { question, outcome, evidence });
    } else {
      RESULTS.push({ id, question, outcome, evidence });
    }
    const level = outcome === 'PASS' ? 'OK' : outcome === 'FAIL' ? 'FAIL' : 'INFO';
    log(level, `${id}: ${outcome} — ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };

  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    // PREFIX match, not equality. Outcomes carry their reason —
    // 'NOT ESTABLISHED (throttled)', 'NOT ESTABLISHED (matched 50, expected
    // 60)', 'SHORT (50 of 60, HTTP 200)' — and an equality test counts every
    // one of those as ANSWERED. A results block would then read "47 answered,
    // 0 NOT established" with unresolved rows visible one screen above it,
    // which is the summary lying by omission: the exact failure expect() was
    // added to prevent, reintroduced at the other end of the same function.
    const open = RESULTS.filter(
      (r) => r.outcome.startsWith('NOT ESTABLISHED') || r.outcome.startsWith('SHORT'),
    ).length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} NOT established.`);
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };

  // Printed FIRST, before any gate: a stale clipboard and a fix that did
  // not work produce identical transcripts otherwise.
  log('INFO', 'probe revision c0c47549 — quote this when reporting results.');

  // ---- CONFIGURATION ---------------------------------------------------
  // NO SITE URL, deliberately — see the harness.

  // A list title to search for, for S4. Use a REAL list title from this
  // tenant, ideally one whose name is a prefix of another list's name —
  // that is the case that decides whether a title is usable as a key.
  const LIST_TITLE = 'CHANGE ME - a real list title on this tenant';

  // The marker token S6 stamps into a list Description. Replace CHANGEME
  // with something random — hex, a short GUID fragment — so no earlier run
  // and no unrelated content can answer for it.
  //
  // KEEP THE VALUE YOU PICK. The follow-up paste MUST use the same token
  // or it is measuring a different, freshly written marker and the crawl
  // clock starts again from zero. Write it down.
  const MARKER_TOKEN = 'dbmlspmarkerCHANGEME';

  // The probe's own list. Not a placeholder — the probe owns this name,
  // and CLEANUP only ever touches this one list.
  const MARKER_LIST_TITLE = 'dbml-sharepoint search marker probe';

  // WHO IS PASTING THIS. Leave it false for an operator, a site owner or a
  // site collection administrator. Set it to true ONLY if you are signed
  // in AS the reporting service account — the list-only reader described
  // in the docblock. It changes what S10 means and NOTHING else: no extra
  // call is made, nothing is written, and no other row reads it.
  //
  // THE FLAG IS NOT TAKEN ON FAITH. Every run reads web/currentuser and
  // prints the caller's LoginName, Title and IsSiteAdmin, so the
  // transcript shows who actually ran it; and S10 refuses to answer if the
  // flag says reader while the caller reads back as a site collection
  // administrator.
  const RUNNING_AS_READER = false;

  // The list S11 and S12 page against. NOT a placeholder — it names a
  // fixture that ALREADY EXISTS on the tenant, 6,000 rows left in place by
  // the list view threshold work. Change it only to point at a different
  // large list, and say so when you report, because the row counts mean
  // nothing without knowing which list produced them.
  //
  // READ-ONLY HERE, AND IT MUST NOT BE RECYCLED. Nothing in this probe
  // writes to it, and other measurements still depend on it existing at
  // exactly 6,000 rows.
  const PAGING_FIXTURE_LIST = 'dbmlsp Probe Threshold';

  const PLACEHOLDER = /CHANGE ME|CHANGEME/;

  // ---- Registration ----------------------------------------------------
  // Every question, up front, before anything can throw. A probe that
  // registers as it goes reports only what it reached and prints "0 not
  // established" over questions it never asked.
  expect('S1', 'CONTROL: does _api/search/query answer this caller at all, for a trivial query?');
  expect('S2', 'Does contentclass:STS_List return rows, how many, and what total is reported?');
  expect('S3', 'For the first STS_List row: EVERY property name returned, and its value.');
  expect('S4', 'Querying for a list title: EVERY title that comes back, not just the expected one.');
  expect('S5', 'Is a list Description returned at all by an STS_List query?');
  expect('S6', 'Does a marker token planted in a list Description match exactly, partially, or not at all?');
  expect('S7', 'The row-limit ceiling: returned row count against reported total, and behaviour at a high limit.');
  expect('S8', 'Does the contentclass:"STS_Site" fallback work, and what identity comes back per site?');
  expect('S9', 'Crawl latency: is recently created content in the index yet, at this run timestamp?');
  expect('S10', 'Is the result set security-trimmed for the querying identity?');
  expect('S11', 'With NO $top, how many list items come back, and is there a server-driven continuation link?');
  expect('S12', 'Does following that continuation link return a further page of DIFFERENT items?');

  if (!CONFIRMED) {
    log('INFO', 'Would READ, writing nothing: several _api/search/query GETs — a');
    log('INFO', 'trivial control query, contentclass:STS_List at a few row limits,');
    log('INFO', 'a query for the configured list title, and contentclass:"STS_Site".');
    log('INFO', 'Also web/lists on this site, to tell an unmet prerequisite (no list');
    log('INFO', 'here HAS a description) from a finding (descriptions are not');
    log('INFO', 'returned); web/currentuser, so the transcript records who ran it;');
    log('INFO', `and the items of '${PAGING_FIXTURE_LIST}' with no $top, to see`);
    log('INFO', 'whether the SERVER emits a continuation link. That list is read and');
    log('INFO', 'never written, and it must not be recycled.');
    log('INFO', 'Every recorded URL has the site host stripped first.');
    log('INFO', 'Would ADDITIONALLY, only with ALLOW_WRITES = true, CREATE ONE LIST');
    log('INFO', `named '${MARKER_LIST_TITLE}' carrying a marker token in its`);
    log('INFO', 'Description, and query for that token. That list is RECYCLED, not');
    log('INFO', 'purged, and only on a later run with CLEANUP = true — read the S6');
    log('INFO', 'warnings in the docblock, because it needs a SECOND paste later.');
    log('INFO', 'Nothing has been read or written. Set CONFIRMED = true.');
    return;
  }

  // Everything measured sits inside this try; see the `finally` at the end.
  try {

  // ---- Redaction -------------------------------------------------------
  // A tenant URL has leaked out of this repository TWICE. This probe is the
  // worst case for it yet: unlike every other probe here, its results come
  // from ACROSS THE TENANT, so redacting only the pasted site's own URL
  // would leave every OTHER site's absolute URL — same host, different
  // path — sitting in the transcript. So the HOST ORIGIN is stripped too.
  //
  // Two different replacements on purpose, longest first:
  //   <site>   this web, the one the probe was pasted into
  //   <tenant> the scheme+host, anywhere else it appears
  // which keeps the PATH visible. That is deliberate: whether a row carries
  // a distinct per-site path is half of what S3 and S8 are asking, and a
  // blanket redaction of the whole URL would erase the finding along with
  // the tenant.
  //
  // Derived by string slicing, and matched with indexOf, CASE-INSENSITIVELY.
  // Not a RegExp built from a URL: that would mean escaping a URL correctly
  // inside the one function whose entire job is not leaking the tenant, and
  // a case-sensitive match would miss a host SharePoint echoed back in a
  // different case than _spPageContextInfo reports it.
  const ORIGIN = (() => {
    const afterScheme = WEB.indexOf('//');
    if (afterScheme === -1) return WEB;
    const firstSlash = WEB.indexOf('/', afterScheme + 2);
    return firstSlash === -1 ? WEB : WEB.slice(0, firstSlash);
  })();

  const replaceAllCI = (haystack, needle, replacement) => {
    if (!needle) return haystack;
    const hay = haystack.toLowerCase();
    const find = needle.toLowerCase();
    let out = '';
    let from = 0;
    for (;;) {
      const at = hay.indexOf(find, from);
      if (at === -1) return out + haystack.slice(from);
      out += haystack.slice(from, at) + replacement;
      from = at + find.length;
    }
  };

  const redact = (value) => {
    if (typeof value !== 'string') return value;
    return replaceAllCI(replaceAllCI(value, WEB, '<site>'), ORIGIN, '<tenant>');
  };

  // Everything printed goes through this, not through JSON.stringify
  // directly. One choke point, so a new evidence line cannot forget.
  const show = (value, limit = 200) => {
    const text = typeof value === 'string' ? value : JSON.stringify(value);
    if (text == null) return 'null';
    const clean = redact(text);
    return clean.length > limit ? `${clean.slice(0, limit)}…[truncated, ${clean.length} chars]` : clean;
  };

  // ---- Query helpers ---------------------------------------------------
  // OData string literal: double the single quotes, then percent-encode.
  // encodeURIComponent leaves "'" alone, so the doubling survives.
  const odataLiteral = (value) => encodeURIComponent(String(value).replace(/'/g, "''"));

  // Every failure is reported AS ITS STATUS WITH ITS BODY. A probe here
  // once collapsed an unexplained HTTP error into "REFUSED" and produced a
  // transcript that read like a measured platform verdict. isRefusal
  // (harness) already carves out identity and throttling; even a real
  // refusal keeps its status and body attached.
  const httpDetail = (r) => `HTTP ${r.status}: ${show(r.text == null ? JSON.stringify(r.body) : r.text, 500)}`;
  const failureOutcome = (r) => (isRefusal(r.status) ? `REFUSED (HTTP ${r.status})` : `NOT ESTABLISHED (HTTP ${r.status})`);

  // A 401 or 403 IS A FINDING IN THIS RUN, and that is a deliberate
  // departure from the harness's isRefusal, which excludes both because
  // they are about WHO is asking rather than about what was sent.
  //
  // Here, who is asking IS THE QUESTION. This file is meant to be pasted by
  // the reporting service account, and "that identity is refused this
  // endpoint" is exactly what the design needs to know — so it is recorded
  // as an OBSERVED refusal attributable to this caller's privilege, not as
  // NOT ESTABLISHED, which would file the answer under "we never found
  // out". Everything else keeps the harness's reading.
  //
  // What it must NOT be read as: a fact about SharePoint. It is a fact
  // about this account, on this site, at this moment, and the outcome
  // string says "for this caller" so a quoted row carries that with it.
  const privilegeRefusal = (status) => status === 401 || status === 403;
  const outcomeFor = (r) => (privilegeRefusal(r.status)
    ? `OBSERVED — REFUSED (HTTP ${r.status}) for this caller`
    : failureOutcome(r));
  const privilegeNote = (r) => (privilegeRefusal(r.status)
    ? ` HTTP ${r.status} is an identity refusal: it is attributable to THIS CALLER'S PRIVILEGE on this `
      + 'site and is recorded as an observation, not as the probe failing. It says nothing about what a '
      + 'more privileged account would get, and nothing about SharePoint in general.'
    : '');

  // Learn documents the endpoint, the GET parameter spellings and the two
  // JSON Accept headers. It does NOT, as far as this author could find,
  // document the response BODY SHAPE for either flavour. So the shape is
  // treated as an observation: both flavours are tried, every shape this
  // ladder knows is tested, the one that ANSWERED is named in the
  // evidence, and the raw payload is printed so a reader can see a shape
  // the ladder does not know about.
  const searchGet = async (params, flavour) => {
    const res = await fetch(`${WEB}/_api/search/query?${params}`, {
      headers: { Accept: `application/json;odata=${flavour}` },
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent XML or plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text, flavour };
  };

  // The harness's spGet sends odata=nometadata. S11 has to reproduce what
  // the DEPLOY TEMPLATES send, and `d.__next` is a VERBOSE construct, so
  // verbose gets its own helper rather than being bolted onto spGet. Same
  // contract as the harness: `body` is the parsed payload whether or not
  // the request succeeded, so only `ok` says the call worked.
  const spGetVerbose = async (path) => {
    const res = await fetch(`${WEB}/_api/${path}`, {
      headers: { Accept: 'application/json;odata=verbose' },
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };

  // `results`-wrapped arrays are a VERBOSE construct; nometadata gives bare
  // arrays. Neither is assumed.
  const unwrap = (node) => {
    if (Array.isArray(node)) return node;
    if (node && Array.isArray(node.results)) return node.results;
    return null;
  };

  const relevantResults = (payload) => {
    const candidates = [
      ['flat', payload],
      ['d', payload && payload.d],
      ['query', payload && payload.query],
      ['d.query', payload && payload.d && payload.d.query],
    ];
    for (const [shape, node] of candidates) {
      const rel = node && node.PrimaryQueryResult && node.PrimaryQueryResult.RelevantResults;
      if (rel) return { shape, rel };
    }
    return null;
  };

  // One call, fully decoded, or a named reason why not. Callers never touch
  // the payload shape themselves.
  const runQuery = async (kql, extra = '') => {
    const params = `querytext='${odataLiteral(kql)}'${extra}`;
    let res = await searchGet(params, 'nometadata');
    let found = res.ok ? relevantResults(res.body) : null;
    if (!found) {
      // Retry in the other flavour before concluding anything. A nometadata
      // shape this ladder does not know would otherwise be reported as the
      // query failing, which is a fabricated verdict about KQL.
      const verbose = await searchGet(params, 'verbose');
      const foundVerbose = verbose.ok ? relevantResults(verbose.body) : null;
      if (foundVerbose) { res = verbose; found = foundVerbose; }
      else if (!res.ok && verbose.ok) { res = verbose; }
    }
    if (!found) {
      return { ok: false, res, kql, params, unknownShape: res.ok };
    }
    const table = found.rel.Table;
    const rows = (table && unwrap(table.Rows)) || [];
    return {
      ok: true, res, kql, params,
      shape: `${found.shape} (odata=${res.flavour})`,
      rows,
      rowCount: found.rel.RowCount,
      totalRows: found.rel.TotalRows,
      totalIncludingDuplicates: found.rel.TotalRowsIncludingDuplicates,
    };
  };

  // A row is a bag of cells. Which cells, and what they are called, is the
  // question — so nothing here looks for a name it expects.
  const cellsOf = (row) => unwrap(row && row.Cells) || [];
  const cellNames = (row) => cellsOf(row).map((c) => String(c.Key));
  const cellValue = (row, key) => {
    const want = String(key).toLowerCase();
    const hit = cellsOf(row).find((c) => String(c.Key).toLowerCase() === want);
    return hit ? hit.Value : undefined;
  };
  const nonEmpty = (value) => value != null && String(value) !== '';

  // The full dump. This IS the answer to S3 and half of S8, so it prints
  // every cell — including the empty ones, because "the name came back with
  // no value" and "the name did not come back" are different facts and a
  // dump that hides the first cannot tell them apart.
  const dumpRow = (row) => cellsOf(row)
    .map((c) => `      ${String(c.Key)} = ${nonEmpty(c.Value) ? show(c.Value) : '(empty)'}`)
    .join('\n');

  const describeQuery = (q) => `query ${JSON.stringify(q.kql)} answered via ${q.shape}; `
    + `RowCount=${JSON.stringify(q.rowCount)}, TotalRows=${JSON.stringify(q.totalRows)}, `
    + `TotalRowsIncludingDuplicates=${JSON.stringify(q.totalIncludingDuplicates)}, `
    + `rows actually returned: ${q.rows.length}`;

  const queryFailure = (q) => (q.unknownShape
    ? `HTTP ${q.res.status} but no PrimaryQueryResult.RelevantResults found in either odata flavour. `
      + `Raw (odata=${q.res.flavour}): ${show(q.res.text, 600)}`
    : `${httpDetail(q.res)}${privilegeNote(q.res)}`);
  const queryOutcome = (q) => (q.unknownShape
    ? 'NOT ESTABLISHED (unrecognised response shape)'
    : outcomeFor(q.res));

  // ---- Who is actually running this ------------------------------------
  // Read ONCE, before anything else, and printed immediately. Two reasons,
  // and neither is bookkeeping: S10's whole meaning depends on which
  // identity ran the queries, and RUNNING_AS_READER is a hand-set constant
  // that can be wrong or stale. The transcript therefore carries the
  // caller's own words for who it is, and S10 cross-checks the flag
  // against IsSiteAdmin rather than believing it.
  const callerRes = await spGet('web/currentuser?$select=LoginName,Title,IsSiteAdmin');
  const callerOk = !readFailed(callerRes);
  const callerLogin = callerOk ? String(callerRes.body.LoginName == null ? '' : callerRes.body.LoginName) : '';
  const callerIsSiteAdmin = callerOk ? callerRes.body.IsSiteAdmin : null;
  const whoRan = callerOk
    ? `the caller is LoginName ${JSON.stringify(callerLogin)}, Title `
      + `${JSON.stringify(callerRes.body.Title)}, IsSiteAdmin=${JSON.stringify(callerIsSiteAdmin)}`
    : `web/currentuser could not be read (${httpDetail(callerRes)})`;
  // ---- Is this a PERSONAL site? ----------------------------------------
  // ADDED 2026-08-12, after a run was pasted onto the reporting account's
  // OWN ONEDRIVE. A USER IS ALWAYS SITE COLLECTION ADMINISTRATOR OF THEIR
  // OWN ONEDRIVE, so IsSiteAdmin came back true and S10 refused — rightly,
  // but for a reason that would have been wrong: it read the bit as
  // evidence of tenant-wide privilege, and on a personal site the bit
  // carries no such information. Detecting the site kind is what lets S10
  // refuse for the true reason.
  //
  // TWO SIGNALS, EITHER SUFFICIENT, and neither is a documented contract:
  // a `-my.` OneDrive host, and a `/personal/` path segment. Both are
  // observed spellings, so this is a HEURISTIC and it is only ever used to
  // choose which REFUSAL to print — never to admit a run that would
  // otherwise be refused. A false positive costs a differently worded
  // refusal; a false negative costs the old wording. Neither can turn a
  // non-answer into an answer.
  const PERSONAL_HOST = ORIGIN.toLowerCase().includes('-my.');
  const PERSONAL_PATH = WEB.toLowerCase().includes('/personal/');
  const isPersonalSite = PERSONAL_HOST || PERSONAL_PATH;
  const siteKind = isPersonalSite
    ? `this looks like a PERSONAL (OneDrive) site — ${PERSONAL_HOST ? 'the host carries "-my."' : ''}`
      + `${PERSONAL_HOST && PERSONAL_PATH ? ' and ' : ''}`
      + `${PERSONAL_PATH ? 'the path carries "/personal/"' : ''}`
    : 'this does not look like a personal (OneDrive) site';

  log('INFO', `RUNNING_AS_READER = ${RUNNING_AS_READER}; ${whoRan}`);
  log('INFO', `Site kind: ${siteKind}.`);
  if (!callerOk) {
    log('INFO', 'The caller could not be identified. S10 will not answer without that — see its row.');
  }

  // ---- The control's verdict, threaded into every search row -----------
  // Set by S1 below. A row that contradicts its own control must not read
  // as a finding: enterprise-reader-probe.js.j2 recorded exactly that on
  // 2026-08-12 — an A3 reading OBSERVED while A2, the same endpoint for
  // the same login, had been refused — and a caveat in prose beside a row
  // that says OBSERVED loses to the row. So the downgrade is mechanical
  // here rather than written out in each evidence string.
  //
  // NOTHING IS THROWN AWAY. Whatever the row read is still printed, as
  // supporting detail for a re-run to compare against.
  let searchAnswers = false;
  let controlWhy = 'S1 did not run';
  let controlStatus = null;
  const searchRecord = (id, question, outcome, evidence) => {
    if (searchAnswers || outcome.startsWith('NOT ESTABLISHED')) {
      record(id, question, outcome, evidence);
      return;
    }
    record(id, question, 'NOT ESTABLISHED (control open)',
           'NOT a finding about search discovery: S1, the control, has not been shown to answer this '
           + `caller — ${controlWhy}. While that is open, this row is about the endpoint rather than `
           + `about the question it was asked. Supporting detail only: ${outcome}; ${evidence}`);
  };

  // ================= S1 — THE CONTROL ===================================
  // depends on: the endpoint spelling and this caller's session.
  // observes:   the status, the response shape, and the counts.
  //
  // A trivial query. Learn's own sample query text is used rather than a
  // clever one, so a failure here is about the endpoint and not about KQL.
  //
  // ZERO ROWS STILL ANSWERS S1. The control asks whether the endpoint
  // ANSWERS THIS CALLER — requiring rows would be asserting over an
  // observation, and on a small or freshly crawled tenant it would report
  // the control as broken while it was working perfectly.
  //
  // A 401/403 ALSO ANSWERS S1, in the other direction: it says this caller
  // is refused the endpoint. For the reporting service account that is one
  // of the two outcomes the whole design is waiting on, so it is recorded
  // as OBSERVED — and it still leaves searchAnswers false, because a
  // refused control cannot license any row below it.
  {
    const S1_Q = 'CONTROL: does _api/search/query answer this caller at all, for a trivial query?';
    const q = await runQuery('sharepoint', '&rowlimit=1');
    controlStatus = q.res.status;
    if (!q.ok) {
      controlWhy = q.unknownShape
        ? `S1 got HTTP ${q.res.status} but no result set it could recognise`
        : `S1 got HTTP ${q.res.status}`;
      record('S1', S1_Q, queryOutcome(q),
             `${queryFailure(q)} ${whoRan}. EVERY OTHER SEARCH ROW IN THIS RUN IS NOW ABOUT THE `
             + 'ENDPOINT, NOT ABOUT the question it was asked, and S2-S9 will say so themselves rather '
             + 'than leaving it to this sentence. S11 and S12 are unaffected — they do not use search.');
    } else {
      searchAnswers = true;
      record('S1', S1_Q, 'OBSERVED — the endpoint answered',
             `${describeQuery(q)}. ${whoRan}. A row count of 0 is still an answer to THIS question: it `
             + 'says the endpoint served the caller. What it does not say is anything about the index.');
    }
  }

  // ================= S2 / S3 — CAN SEARCH ENUMERATE LISTS? ==============
  // Deliberately sent with NO selectproperties. Naming the properties we
  // want would decide what comes back, and what comes back BY DEFAULT is
  // exactly what S3 is asking. Constraining the answer and then reporting
  // it as the answer is how a probe measures its own input.
  let firstListRow = null;
  // Kept for S10: when the reporting identity runs this, the rows THIS
  // query returned are the trimmed view, so S10 reads them rather than
  // issuing the same query again from a second position in the run.
  let listQuery = null;
  {
    const S2_Q = 'Does contentclass:STS_List return rows, how many, and what total is reported?';
    const S3_Q = 'For the first STS_List row: EVERY property name returned, and its value.';
    const q = await runQuery('contentclass:STS_List', '&rowlimit=10');
    listQuery = q;
    if (!q.ok) {
      const detail = queryFailure(q);
      searchRecord('S2', S2_Q, queryOutcome(q),
             `${detail}. This is the decisive unknown, so be careful reading it: the query FAILING is `
             + 'not the same as STS_List not being a content class. Check S1 first, then S8 — if the '
             + 'documented STS_Site query works and this one does not, THAT is the finding.');
      record('S3', S3_Q, 'NOT ESTABLISHED (prerequisite)', 'S2 returned no result set to inspect.');
    } else {
      searchRecord('S2', S2_Q, `OBSERVED — ${q.rows.length} row(s) returned`,
             `${describeQuery(q)}. rowlimit was 10, so a returned count of 10 is the LIMIT talking, `
             + 'not the population — the reported total is the number to read, and S7 pushes on it.');
      if (q.rows.length === 0) {
        record('S3', S3_Q, 'NOT ESTABLISHED (prerequisite)',
               'the STS_List query returned no rows, so there was no row to dump. See S2 — and note '
               + 'that an empty result set on a caller who can see everything is itself worth '
               + 'reporting, but it is not an answer to S3.');
      } else {
        firstListRow = q.rows[0];
        const names = cellNames(firstListRow);
        // The candidate set the DESIGN would like to exist. Requested in a
        // separate query, and labelled as a request: asking for a name is
        // not evidence the name exists, and a name that comes back empty
        // may be unmapped, not absent.
        const CANDIDATES = ['ListId', 'WebId', 'SiteId', 'SPSiteUrl', 'SPWebUrl', 'Path',
                            'OriginalPath', 'Title', 'Description', 'WebTemplate', 'contentclass',
                            'LastModifiedTime', 'ParentLink'];
        const present = CANDIDATES.filter((c) => names.some((n) => n.toLowerCase() === c.toLowerCase()));
        const absent = CANDIDATES.filter((c) => !present.includes(c));

        // One combined request first. If the server rejects the whole
        // select — which it may do for a single unknown or non-retrievable
        // name — fall back to one query per name, so one bad name cannot
        // blind the other twelve.
        let selectNote;
        const combined = await runQuery('contentclass:STS_List',
                                        `&rowlimit=1&selectproperties='${odataLiteral(CANDIDATES.join(','))}'`);
        if (combined.ok && combined.rows.length) {
          const got = cellNames(combined.rows[0]);
          const served = CANDIDATES.filter((c) => got.some((n) => n.toLowerCase() === c.toLowerCase()
            && nonEmpty(cellValue(combined.rows[0], c))));
          selectNote = `explicitly REQUESTING all ${CANDIDATES.length} candidates in one query was `
            + `accepted, and these came back with a non-empty value: ${served.join(', ') || '(none)'}. `
            + `Full cell list from that query: ${got.join(', ')}`;
        } else {
          const perName = [];
          for (const name of CANDIDATES) {
            const one = await runQuery('contentclass:STS_List',
                                       `&rowlimit=1&selectproperties='${odataLiteral(name)}'`);
            perName.push(`${name}: ${one.ok
              ? (one.rows.length && nonEmpty(cellValue(one.rows[0], name)) ? 'non-empty' : 'accepted but empty')
              : `rejected (HTTP ${one.res.status})`}`);
          }
          selectNote = 'the combined select was NOT accepted '
            + `(${combined.ok ? 'it returned no rows' : `HTTP ${combined.res.status}`}), so each name was `
            + `requested on its own: ${perName.join('; ')}`;
        }

        searchRecord('S3', S3_Q, `OBSERVED — ${names.length} propert${names.length === 1 ? 'y' : 'ies'} on the first row`,
               `${describeQuery(q)}\n      --- every cell on row 1, site host redacted ---\n${dumpRow(firstListRow)}\n`
               + `      --- end of dump ---\n      property NAMES: ${names.join(', ')}\n`
               + `      Of the names the design would like: PRESENT ${present.join(', ') || '(none)'}; `
               + `NOT IN THIS ROW ${absent.join(', ') || '(none)'} — which says they were not returned `
               + 'by default HERE, not that they do not exist.\n'
               + `      ${selectNote}\n`
               + '      THE DUMP IS THE ANSWER. What the design needs is a stable list GUID and a '
               + 'site/web URL IN THE SAME ROW; read the dump for whether it got both.');
      }
    }
  }

  // ================= S4 — TOKENISATION AND TITLES =======================
  // The question is NOT "did my list come back". It is "WHAT came back",
  // because Learn documents that text managed properties are word-broken
  // and that exact matching is an opt-in per-property setting. A query for
  // `Widgets` that also returns `Widgets Archive` is the finding, and a
  // probe that only checked for its own title would discard it.
  {
    const S4_Q = 'Querying for a list title: EVERY title that comes back, not just the expected one.';
    if (PLACEHOLDER.test(LIST_TITLE)) {
      record('S4', S4_Q, 'NOT ESTABLISHED (prerequisite)',
             'LIST_TITLE is still the placeholder. Set it to a real list title on this tenant — '
             + 'ideally one that is a prefix of another list\'s title, which is the case that decides '
             + 'whether a title can be a key at all.');
    } else {
      const variants = [
        ['Title property, quoted phrase', `contentclass:STS_List Title:"${LIST_TITLE}"`],
        ['Title property, bare', `contentclass:STS_List Title:${LIST_TITLE}`],
        ['free text, quoted phrase', `contentclass:STS_List "${LIST_TITLE}"`],
      ];
      const lines = [];
      let anyAnswered = false;
      for (const [label, kql] of variants) {
        const q = await runQuery(kql, '&rowlimit=50');
        if (!q.ok) {
          lines.push(`      ${label}: ${queryFailure(q)}`);
          continue;
        }
        anyAnswered = true;
        // EVERY title, in order, with no filtering whatsoever.
        const titles = q.rows.map((row) => {
          const t = cellValue(row, 'Title');
          return t === undefined ? '(no Title cell on this row)' : show(t, 120);
        });
        const exact = titles.filter((t) => t === LIST_TITLE).length;
        lines.push(`      ${label}: ${describeQuery(q)}`);
        lines.push(`        every title returned, verbatim and unfiltered: ${JSON.stringify(titles)}`);
        lines.push(`        of those, ${exact} equal${exact === 1 ? 's' : ''} LIST_TITLE character for `
                   + `character; ${titles.length - exact} do not. The ones that do NOT are the finding.`);
      }
      searchRecord('S4', S4_Q,
             anyAnswered ? 'OBSERVED — see every title returned, per query variant' : 'NOT ESTABLISHED (no variant answered)',
             `LIST_TITLE was ${JSON.stringify(LIST_TITLE)}.\n${lines.join('\n')}\n`
             + '      Read this against Learn: text managed properties are word-broken, and "Complete '
             + 'matching" is an opt-in per-property setting requiring a reindex. Extra titles here are '
             + 'therefore the EXPECTED platform behaviour, not a fault — and they are precisely what '
             + 'would make a title unusable as a discovery key.');
    }
  }

  // ================= Local list facts, for S5 and S9 =====================
  // Read from the REST list API, NOT from search. Its whole job is to tell
  // an unmet prerequisite from a finding: "no list in reach even HAS a
  // description" and "descriptions are not returned by search" produce the
  // same empty result set, and calling the first one the second would be a
  // fabricated verdict about crawling.
  const localLists = await spGet(
    'web/lists?$select=Title,Description,Created,Hidden,BaseTemplate,ItemCount&$top=5000');
  const localRows = (!readFailed(localLists) && Array.isArray(localLists.body.value))
    ? localLists.body.value.filter((l) => l.Hidden === false)
    : null;

  // ================= S5 — IS DESCRIPTION RETURNED? ======================
  {
    const S5_Q = 'Is a list Description returned at all by an STS_List query?';
    const described = localRows ? localRows.filter((l) => nonEmpty(l.Description)) : [];
    if (localRows === null) {
      record('S5', S5_Q, 'NOT ESTABLISHED (prerequisite)',
             `could not read web/lists to establish whether any list here HAS a description: `
             + `${httpDetail(localLists)}.${privilegeNote(localLists)} Without that, an empty `
             + 'Description column in the search result cannot be told from there being nothing to '
             + 'crawl. Whether the reporting identity can enumerate web/lists at all is a live '
             + 'question in its own right — the Power BI SharePoint Online List connector does '
             + 'exactly that read — so quote this line if it refused.');
    } else if (described.length === 0) {
      record('S5', S5_Q, 'NOT ESTABLISHED (prerequisite: no list in reach has a description)',
             `${localRows.length} visible list(s) on this site were read directly from web/lists and `
             + 'NOT ONE has a non-empty Description. So there is nothing for search to have crawled, '
             + 'and this run cannot answer S5. THIS IS NOT "descriptions are not crawled" — recording '
             + 'it that way would be a fabricated verdict. Give a list a description, wait for a crawl, '
             + 'and paste again; or answer this through S6, which plants one deliberately.');
    } else {
      const q = await runQuery('contentclass:STS_List', '&rowlimit=50');
      const explicit = await runQuery('contentclass:STS_List',
                                      "&rowlimit=50&selectproperties='Title,Description'");
      if (!q.ok && !explicit.ok) {
        searchRecord('S5', S5_Q, queryOutcome(q), `neither the default nor the explicit-select query `
               + `answered: ${queryFailure(q)}`);
      } else {
        const summarise = (label, result) => {
          if (!result.ok) return `      ${label}: ${queryFailure(result)}`;
          const withCell = result.rows.filter((r) => cellValue(r, 'Description') !== undefined);
          const withValue = result.rows.filter((r) => nonEmpty(cellValue(r, 'Description')));
          const samples = withValue.slice(0, 3).map((r) => show(cellValue(r, 'Description'), 120));
          return `      ${label}: ${result.rows.length} row(s); ${withCell.length} carried a Description `
            + `CELL; ${withValue.length} carried a non-empty value. Up to three verbatim: `
            + `${JSON.stringify(samples)}`;
        };
        searchRecord('S5', S5_Q, 'OBSERVED — see the per-query counts',
               `PREREQUISITE MET: ${described.length} of ${localRows.length} visible list(s) on this `
               + `site have a description, so there IS something to find. Their titles, for cross-`
               + `reference: ${JSON.stringify(described.slice(0, 10).map((l) => show(l.Title, 80)))}\n`
               + `${summarise('default properties', q)}\n${summarise("selectproperties='Title,Description'", explicit)}\n`
               + '      A Description cell that comes back EMPTY for a list known to have one is a real '
               + 'finding — but check S9 first, because an uncrawled list looks exactly the same.');
      }
    }
  }

  // ================= S7 — THE ROW-LIMIT CEILING =========================
  // Learn gives 500 as the documented boundary for rows in a result set,
  // raisable to 10,000 via MaxRowLimit, with StartRow capped at 50,000.
  // That is CONTEXT, not an expectation: this row asserts nothing about
  // where the ceiling actually falls on this tenant, and a limit that is
  // honoured, clamped or refused are all equally real answers.
  {
    const S7_Q = 'The row-limit ceiling: returned row count against reported total, and behaviour at a high limit.';
    const limits = [1, 10, 500, 1000];
    const lines = [];
    let answered = 0;
    let firstTotal = null;
    for (const limit of limits) {
      const q = await runQuery('contentclass:STS_List', `&rowlimit=${limit}`);
      if (!q.ok) {
        lines.push(`      rowlimit=${limit}: ${queryFailure(q)}`);
        continue;
      }
      answered += 1;
      if (firstTotal === null) firstTotal = q.totalRows;
      lines.push(`      rowlimit=${limit}: returned ${q.rows.length} row(s); RowCount=`
                 + `${JSON.stringify(q.rowCount)}; TotalRows=${JSON.stringify(q.totalRows)}; `
                 + `TotalRowsIncludingDuplicates=${JSON.stringify(q.totalIncludingDuplicates)}`);
    }
    // One paging step, using the documented startrow parameter. Whether the
    // second page holds DIFFERENT rows is the question; a second page that
    // repeats the first would look like paging and would not be.
    const page1 = await runQuery('contentclass:STS_List', '&rowlimit=5&startrow=0');
    const page2 = await runQuery('contentclass:STS_List', '&rowlimit=5&startrow=5');
    if (page1.ok && page2.ok) {
      const keyOf = (row) => cellNames(row).map((n) => `${n}=${cellValue(row, n)}`).join('|');
      const seen = new Set(page1.rows.map(keyOf));
      const fresh = page2.rows.filter((r) => !seen.has(keyOf(r))).length;
      lines.push(`      paging via startrow: page 1 (startrow=0) held ${page1.rows.length} row(s); `
                 + `page 2 (startrow=5) held ${page2.rows.length}, of which ${fresh} were not on page 1. `
                 + 'Compared over the WHOLE row, not the first cell — a repeated page in a different '
                 + 'order would otherwise read as successful paging.');
    } else {
      lines.push(`      paging via startrow: not answered — page 1 ${page1.ok ? 'ok' : queryFailure(page1)}; `
                 + `page 2 ${page2.ok ? 'ok' : queryFailure(page2)}`);
    }
    searchRecord('S7', S7_Q,
           answered ? `OBSERVED — ${answered} of ${limits.length} row limits answered` : 'NOT ESTABLISHED (no row limit answered)',
           `${lines.join('\n')}\n      For context only, and asserted nowhere above: Learn documents 500 `
           + 'as the boundary for rows in a result set (raisable to 10,000 via MaxRowLimit) and caps '
           + 'StartRow at 50,000, with `indexdocid` + sortlist=\'[docid]:ascending\' as the idiom for '
           + `paging past it. What this tenant actually did is in the lines above.${firstTotal === null ? ''
              : ` The reported total was ${JSON.stringify(firstTotal)} — if the returned count never `
                + 'reaches it, the ceiling is what the fleet design has to page against.'}`);
  }

  // ================= S8 — THE DOCUMENTED FALLBACK =======================
  // Measured EVEN IF S2 SUCCEEDED. This is the mechanism Learn actually
  // samples and it is the design's plan B; a plan B nobody measured is not
  // a plan. Same two-part treatment as S3: dump the DEFAULT cell set, then
  // separately request the four properties Learn's sample selects.
  let siteQuery = null;
  {
    const S8_Q = 'Does the contentclass:"STS_Site" fallback work, and what identity comes back per site?';
    const q = await runQuery('contentclass:"STS_Site"', '&rowlimit=10');
    siteQuery = q;
    if (!q.ok) {
      searchRecord('S8', S8_Q, queryOutcome(q),
             `${queryFailure(q)}. Note what this would mean if S2 also failed: the DOCUMENTED, `
             + 'Microsoft-sampled query did not work either, which points at the endpoint or this '
             + 'caller rather than at STS_List.');
    } else if (q.rows.length === 0) {
      searchRecord('S8', S8_Q, 'OBSERVED — 0 rows',
             `${describeQuery(q)}. The query was accepted and returned nothing. On a caller who can `
             + 'see many sites that is worth reporting; it is not, on its own, a fact about STS_Site.');
    } else {
      // Learn's sample selects exactly these four for STS_Site.
      const SAMPLED = ['Title', 'SPSiteUrl', 'Description', 'WebTemplate'];
      const sampled = await runQuery('contentclass:"STS_Site"',
                                     `&rowlimit=10&selectproperties='${odataLiteral(SAMPLED.join(','))}'`);
      const perSite = sampled.ok
        ? sampled.rows.map((row, i) => `        site ${i + 1}: `
            + SAMPLED.map((p) => `${p}=${nonEmpty(cellValue(row, p)) ? show(cellValue(row, p), 100) : '(empty)'}`).join(', ')).join('\n')
        : `        the Learn-sampled select did not answer: ${queryFailure(sampled)}`;
      searchRecord('S8', S8_Q, `OBSERVED — ${q.rows.length} site row(s) returned`,
             `${describeQuery(q)}\n      --- every cell on site row 1, site host redacted ---\n`
             + `${dumpRow(q.rows[0])}\n      --- end of dump ---\n`
             + `      property NAMES: ${cellNames(q.rows[0]).join(', ')}\n`
             + '      Learn\'s own sample selects Title, SPSiteUrl, Description, WebTemplate for '
             + `STS_Site. Requested explicitly, per site:\n${perSite}\n`
             + '      What matters for the design is whether each row carries an identity a consumer '
             + 'could build a REST path from WITHOUT another call. Read the dump, not this sentence.');
    }
  }

  // ================= S9 — CRAWL LATENCY =================================
  // ONE RUN CANNOT ANSWER THIS. What one run can do is stamp a timestamp
  // and record whether known-recent content is in the index yet, so a
  // SECOND run bounds it from the other side. The row says so itself,
  // because a single "not found yet" quoted without that caveat reads like
  // a measured latency and is not one.
  const RUN_AT = new Date().toISOString();
  {
    const S9_Q = 'Crawl latency: is recently created content in the index yet, at this run timestamp?';
    if (localRows === null) {
      record('S9', S9_Q, 'NOT ESTABLISHED (prerequisite)',
             `could not read web/lists to find the most recently created list: ${httpDetail(localLists)}. `
             + `Run timestamp was ${RUN_AT}.`);
    } else if (localRows.length === 0) {
      record('S9', S9_Q, 'NOT ESTABLISHED (prerequisite)',
             `no visible list on this site to test with. Run timestamp was ${RUN_AT}.`);
    } else {
      const newest = localRows.slice().sort(
        (a, b) => String(b.Created || '').localeCompare(String(a.Created || '')))[0];
      const ageHours = (Date.now() - Date.parse(newest.Created)) / 3600000;
      const q = await runQuery(`contentclass:STS_List Title:"${newest.Title}"`, '&rowlimit=50');
      const titles = q.ok
        ? q.rows.map((r) => show(cellValue(r, 'Title'), 120))
        : null;
      const hit = titles ? titles.some((t) => t === newest.Title) : false;
      searchRecord('S9', S9_Q, `OBSERVED — at ${RUN_AT}, the newest list here is ${hit ? 'IN' : 'NOT IN'} the result set`,
             `run timestamp ${RUN_AT}. The most recently created visible list on this site is `
             + `${JSON.stringify(show(newest.Title, 80))}, Created ${JSON.stringify(newest.Created)} — `
             + `about ${Number.isFinite(ageHours) ? ageHours.toFixed(1) : '?'} hour(s) before this run. `
             + `Searching for it ${q.ok ? `returned ${JSON.stringify(titles)}` : `failed: ${queryFailure(q)}`}.\n`
             + '      ONE RUN CANNOT ANSWER THIS QUESTION and this row does not claim to. A miss bounds '
             + 'latency from BELOW only (it was still absent at this age); a hit bounds it from ABOVE '
             + '(it was present by this age). Paste this file again later, without changing anything, '
             + 'and quote both timestamps to close the interval.');
    }
  }

  // ================= S10 — SECURITY TRIMMING ============================
  // TWO RUNS, TWO MEANINGS, and only one of them is an answer. See the S10
  // section in the docblock. From a privileged caller this row still
  // refuses, in the same words it always did. From the list-only reporting
  // identity the result set IS the trimmed view and therefore IS the
  // measurement — which is why RUNNING_AS_READER exists, and why the flag
  // is cross-checked against the caller rather than believed.
  //
  // THE CROSS-CHECK ITSELF IS CROSS-CHECKED, as of 2026-08-12: IsSiteAdmin
  // is universal on a personal site, so on one it is reported as expected
  // and NOT as evidence of privilege. The refusal is unchanged either way.
  {
    const S10_Q = 'Is the result set security-trimmed for the querying identity?';

    // The rows S2 and S8 already returned. Nothing is re-queried: for a
    // least-privilege caller these ARE the trimmed view, there is no
    // untrimmed view to diff against, and asking twice would only invite a
    // reader to treat the second answer as a comparison.
    const listRows = (listQuery && listQuery.ok) ? listQuery.rows : [];
    const siteRows = (siteQuery && siteQuery.ok) ? siteQuery.rows : [];
    const SITE_CELLS = ['SPSiteUrl', 'SPWebUrl', 'Path', 'OriginalPath'];
    const located = [...new Set(listRows.concat(siteRows).flatMap(
      (row) => SITE_CELLS
        .filter((key) => nonEmpty(cellValue(row, key)))
        .map((key) => `${key}=${show(cellValue(row, key), 160)}`)))];
    const seenLine = `S2's STS_List query returned ${listRows.length} row(s) and S8's STS_Site query `
      + `${siteRows.length}. Every distinct site/web/path value across both, host redacted, up to 40: `
      + `${JSON.stringify(located.slice(0, 40))}`
      + `${located.length > 40 ? ` (and ${located.length - 40} more)` : ''}`;

    if (!callerOk) {
      record('S10', S10_Q, 'NOT ESTABLISHED (the caller could not be identified)',
             `${whoRan}. Without knowing WHICH identity ran the queries, a result set says nothing `
             + 'about trimming — the same rows mean opposite things depending on who asked for them. '
             + `RUNNING_AS_READER was ${RUNNING_AS_READER}, but this row will not answer on the flag `
             + `alone. ${seenLine}`);
    } else if (!RUNNING_AS_READER) {
      record('S10', S10_Q, 'NOT ESTABLISHED (not answerable from a privileged account)',
             `${whoRan}, and RUNNING_AS_READER is false, so this is an OPERATOR run. IT CANNOT ANSWER `
             + 'THIS AND DID NOT TRY. A trimmed result set and an untrimmed one are IDENTICAL to a '
             + 'caller who can see everything: both return everything that account may see. So a full '
             + 'result set here is not weak evidence that trimming works — it is no evidence at all, '
             + 'and quoting it as reassurance would be worse than leaving the question open.\n'
             + '      WHAT WOULD ANSWER IT, and it is no longer out of reach: paste this same file '
             + 'while SIGNED IN AS THE REPORTING SERVICE ACCOUNT and set RUNNING_AS_READER = true. That '
             + 'account holds list-scoped Read and nothing else, so whatever comes back to it IS the '
             + `trimmed view. For the re-run to compare against: ${seenLine}`);
    } else if (callerIsSiteAdmin === true && isPersonalSite) {
      // MEASURED 2026-08-12: this is the branch the first run hit, and
      // before this branch existed it fell into the one below and blamed
      // the account. The refusal is identical; only the diagnosis changed.
      record('S10', S10_Q, 'NOT ESTABLISHED (pasted on the caller\'s own personal site)',
             `${whoRan}, and ${siteKind}. IsSiteAdmin IS TRUE HERE AND THAT IS EXPECTED AND UNIVERSAL: `
             + 'A USER IS ALWAYS SITE COLLECTION ADMINISTRATOR OF THEIR OWN ONEDRIVE. So this bit says '
             + 'NOTHING about tenant-wide privilege, IT IS NOT EVIDENCE THAT THIS ACCOUNT HAS BROAD '
             + 'ACCESS, and it must not be reported as such — it is a property of the site that was '
             + 'pasted into, not of the account that pasted.\n'
             + '      THE ROW STILL REFUSES, for the real reason: a caller who administers the site it '
             + 'is querying from is not the configuration this question is about, and no trimming '
             + 'verdict can be read off it either way.\n'
             + '      WHAT TO DO: REPEAT THIS RUN ON A NON-PERSONAL SITE where this account is NOT an '
             + 'administrator — one of the register sites it was actually granted lists on. Navigate to '
             + 'that site explicitly and check the address bar first. OPENING THE MICROSOFT LISTS APP '
             + 'LANDS ON YOUR OWN ONEDRIVE, which is how this run ended up here. S1-S9 are unaffected: '
             + `search trims on the identity, not on the site pasted into. ${seenLine}`);
    } else if (callerIsSiteAdmin === true) {
      record('S10', S10_Q, 'NOT ESTABLISHED (the flag contradicts the caller)',
             `RUNNING_AS_READER was set to true, but ${whoRan} — IsSiteAdmin is true, so this is not `
             + 'the list-only reporting identity. Filing a site collection administrator\'s result set '
             + 'as a least-privilege measurement is exactly the fabrication this row exists to refuse, '
             + 'so it refuses. Either paste this as the service account, or set RUNNING_AS_READER back '
             + `to false and read the operator wording instead. ${seenLine}`);
    } else if (!searchAnswers && privilegeRefusal(controlStatus)) {
      record('S10', S10_Q,
             `OBSERVED — the reporting identity was REFUSED the search endpoint (HTTP ${controlStatus})`,
             `${whoRan}. S1, a trivial query, came back HTTP ${controlStatus} — ${controlWhy}. THAT IS `
             + 'AN ANSWER, not a failed run: this identity cannot call _api/search/query on this site '
             + 'at all, so SEARCH-DRIVEN DISCOVERY CANNOT WORK UNDER LEAST PRIVILEGE AS CONFIGURED '
             + 'HERE. Read it narrowly — it is a fact about this account on this site, with these '
             + 'grants, at this moment. It does not say search never trims, and it does not say another '
             + 'grant would not open the endpoint. What it does say is that the fleet design cannot '
             + 'assume the endpoint is available to the identity it would run as. Nothing in S2-S9 can '
             + `be read as a search finding on this run; see their own rows. ${seenLine}`);
    } else if (!searchAnswers) {
      record('S10', S10_Q, 'NOT ESTABLISHED (control open)',
             `${whoRan}, running as the reader. S1 did not hold and not because of an identity `
             + `refusal — ${controlWhy} — so the empty or partial result set below is about the `
             + 'endpoint, not about trimming. A caller who is served nothing because the endpoint is '
             + 'broken and a caller who is served nothing because it may see nothing produce the same '
             + `rows. Re-run before reading anything into it. ${seenLine}`);
    } else {
      record('S10', S10_Q,
             `OBSERVED — the trimmed view for this identity: ${listRows.length} STS_List row(s), `
             + `${siteRows.length} STS_Site row(s)`,
             `${whoRan}, RUNNING_AS_READER is true and IsSiteAdmin came back `
             + `${JSON.stringify(callerIsSiteAdmin)}, so this caller is the list-only reporting `
             + 'identity: it is not a member of any site and holds Read at list scope plus whatever '
             + 'Limited Access SharePoint derives at web scope. THE RESULT SET ABOVE IS THEREFORE THE '
             + 'TRIMMED VIEW BY DEFINITION. There is nothing to compare it against and nothing needs '
             + `to be.\n      ${seenLine}\n`
             + `      WHAT IT IMPLIES, and read the counts rather than this sentence: ${
                  listRows.length + siteRows.length === 0
                    ? 'the endpoint SERVED this identity and returned NOTHING. If the account really '
                      + 'does hold Read on lists reachable from here, that is a finding — list Read '
                      + 'alone would not be enough to make a list DISCOVERABLE through search, and the '
                      + 'fleet design needs a different grant or a different mechanism. Before '
                      + 'concluding it, check S9: an uncrawled tenant looks exactly the same, and check '
                      + 'that this account has in fact been granted Read on something here.'
                    : 'the endpoint served this identity and returned rows, so permission-trimmed '
                      + 'discovery IS REACHABLE from least privilege on this site. What the design '
                      + 'still needs is whether those rows carry a list GUID and a web URL together '
                      + '(S3), and whether the sites listed above are exactly the ones this account was '
                      + 'granted — which only the person who made the grants can confirm. Say so when '
                      + 'you report.'}\n`
             + '      ONE ACCOUNT, ONE SITE, ONE MOMENT. This is a data point, not a rule about '
             + 'SharePoint trimming, which Learn already documents and this probe does not test.');
    }
  }

  // ================= S11 / S12 — SERVER-DRIVEN PAGING ===================
  // NOT A SEARCH QUESTION, and deliberately so. See the S11/S12 section in
  // the docblock: `_security_principals.js.j2` and `_reader_enrolment.js.j2`
  // both page with `$top=5000` and follow `d.__next`, and nobody has
  // confirmed SharePoint REST emits `__next` on server truncation at all.
  //
  // The experiment that WOULD settle it for site groups — a group with more
  // members than the server page size — has been declined, because adding a
  // large group to a site's permissions would expose many real people to
  // development work. It is not asked for here.
  //
  // So this measures the same platform behaviour against a fixture that
  // already exists and costs nothing: 6,000 rows, read-only, never written
  // to and never recycled by this probe.
  {
    const S11_Q = 'With NO $top, how many list items come back, and is there a server-driven continuation link?';
    const S12_Q = 'Does following that continuation link return a further page of DIFFERENT items?';
    const SCOPE_NOTE = 'SCOPE, and it must travel with this row: this is the LIST-ITEMS collection, NOT '
      + 'sitegroups/users. It establishes whether THIS TENANT\'S REST EMITS SERVER-DRIVEN PAGING AT ALL, '
      + 'which is the assumption underneath both deploy templates. It does NOT settle the site-group '
      + 'case — that collection may page differently or not at all, and it stays UNMEASURED.';
    const TRUNCATION_NOTE = 'AND AN ABSENT LINK IS NOT PROOF EVERYTHING CAME BACK. On this same fixture '
      + 'an unindexed presence test was measured returning 50 rows instead of 60, at HTTP 200 with no '
      + 'error (2026-07-31). This tenant is already known to truncate silently, so the row count, the '
      + 'ItemCount and the link are three separate observations here and no conclusion is drawn from '
      + 'the absence of the third.';
    // ADDED 2026-08-12 — see "THE S11 PREREQUISITE DEFECT" in the docblock.
    const TRIMMING_NOTE = 'SHAREPOINT TRIMS THE LIST-ITEMS COLLECTION PER ITEM, so a caller holding no '
      + 'grant on this fixture\'s items is served an EMPTY collection at HTTP 200. That is the CORRECT '
      + 'outcome for such a caller and not a platform defect. ItemCount is LIST METADATA and reads back '
      + 'without any item access at all, so it cannot stand in for "this caller can see items".';
    const OPERATOR_NOTE = 'RUN S11 AND S12 AS AN OPERATOR WHO CAN READ THIS FIXTURE\'S ITEMS. They are '
      + 'IDENTITY-INDEPENDENT platform questions — whether the server offers a continuation token when it '
      + 'truncates does not depend on who asked — so the reporting service account is the wrong identity '
      + 'to ask them from. That is RUN B; see HOW TO RUN in the docblock.';

    const listRef = `web/lists/getbytitle('${odataLiteral(PAGING_FIXTURE_LIST)}')`;
    const fixture = await spGet(`${listRef}?$select=Title,ItemCount`);

    // THE PREREQUISITE THIS ROW ACTUALLY NEEDS, AND `ItemCount` IS NOT IT.
    // ADDED 2026-08-12, after run 2 read ItemCount=5614 and then got zero
    // rows back at HTTP 200 with no continuation link on both flavours —
    // which the row below would have filed as catastrophic silent
    // truncation. It was almost certainly nothing of the kind: that caller
    // was the reporting account, which holds no grant on a development
    // fixture, and items are trimmed per item.
    //
    // So ask directly: can this caller see ANY item here? One is enough.
    // `$top=1` is legitimate HERE and nowhere else in this block, because
    // this is not the paging measurement — it is the check that the paging
    // measurement means anything at all.
    const visible = readFailed(fixture) ? null : await spGet(`${listRef}/items?$top=1&$select=Id`);
    const visibleRows = (visible !== null && !readFailed(visible) && Array.isArray(visible.body.value))
      ? visible.body.value.length : null;

    if (readFailed(fixture)) {
      // PREREQUISITE, NEVER A FINDING. A list that is absent, renamed or
      // unreadable by this caller cannot say anything about paging, and
      // recording it as "paging does not work" would be a fabricated
      // platform verdict of exactly the kind this repository exists to stop.
      const why = `the fixture list ${JSON.stringify(PAGING_FIXTURE_LIST)} could not be read on this `
        + `site: ${httpDetail(fixture)}.${privilegeNote(fixture)} It may not exist here, it may have `
        + 'been renamed, or this caller may not be able to read it — PASTE THIS INTO THE SITE THAT '
        + 'HOLDS IT, or point PAGING_FIXTURE_LIST at another large list and say which. THIS IS NOT '
        + '"paging does not work"; nothing was measured.';
      record('S11', S11_Q, 'NOT ESTABLISHED (prerequisite: the fixture list could not be read)', why);
      record('S12', S12_Q, 'NOT ESTABLISHED (prerequisite)', why);
    } else if (visibleRows === null || visibleRows === 0) {
      // PREREQUISITE, NEVER A FINDING — and this is the branch that stops a
      // trimmed caller producing a truncation verdict.
      const why = `the fixture list ${JSON.stringify(PAGING_FIXTURE_LIST)} was reachable — it reports `
        + `ItemCount=${JSON.stringify(fixture.body.ItemCount)} — but THIS CALLER CANNOT READ ITS ITEMS. `
        + `${visibleRows === null
             ? `A one-item read did not return an item collection: ${httpDetail(visible)}`
               + `${privilegeNote(visible)}`
             : 'A one-item read came back with ZERO items.'}\n`
        + `      ${TRIMMING_NOTE} So the plain reading is that this caller simply has NO GRANT on this `
        + 'fixture\'s items. NOTHING ABOUT PAGING WAS MEASURED, and the 6,000-row read was not even '
        + `attempted.\n      ${OPERATOR_NOTE}\n      ${SCOPE_NOTE}`;
      record('S11', S11_Q, 'NOT ESTABLISHED (prerequisite: this caller cannot read the fixture\'s items)', why);
      record('S12', S12_Q, 'NOT ESTABLISHED (prerequisite)', why);
    } else {
      const itemCount = fixture.body.ItemCount;
      // NO $top AT ALL — the only form that can answer this. `$top` is
      // CLIENT-driven paging: Learn ("PageSize, Top and MaxTop") says no
      // nextLink is returned for it, and ("Server-driven Paging in ASP.NET
      // Core OData 8") that a $top below the page size returns that many
      // items with no next link. With no $top the SERVER alone decides
      // where the page ends.
      //
      // $select=Id IS a projection, not a page size: it keeps the payload
      // survivable at 6,000 rows and cannot create or suppress a link.
      //
      // Both flavours, because `d.__next` is a VERBOSE construct — what the
      // deploy templates send — while the harness sends nometadata, where
      // the same thing is spelled `odata.nextLink`. Which of them this
      // tenant emits is an observation, not something to assume.
      const itemsPath = `${listRef}/items?$select=Id`;
      const verboseRes = await spGetVerbose(itemsPath);
      const nometaRes = await spGet(itemsPath);

      const verboseRows = (verboseRes.ok && verboseRes.body && verboseRes.body.d
                           && Array.isArray(verboseRes.body.d.results)) ? verboseRes.body.d.results : null;
      const verboseNextRaw = (verboseRes.ok && verboseRes.body && verboseRes.body.d)
        ? verboseRes.body.d.__next : undefined;
      const verboseNext = (typeof verboseNextRaw === 'string' && verboseNextRaw !== '') ? verboseNextRaw : null;

      const nometaRows = (!readFailed(nometaRes) && Array.isArray(nometaRes.body.value))
        ? nometaRes.body.value : null;
      const nometaNextRaw = (!readFailed(nometaRes) && nometaRes.body)
        ? (nometaRes.body['odata.nextLink'] || nometaRes.body['@odata.nextLink']) : undefined;
      const nometaNext = (typeof nometaNextRaw === 'string' && nometaNextRaw !== '') ? nometaNextRaw : null;

      const perFlavour = `odata=verbose: ${verboseRows === null
          ? `no d.results — ${httpDetail(verboseRes)}${privilegeNote(verboseRes)}`
          : `${verboseRows.length} row(s); typeof d.__next = ${typeof verboseNextRaw}; value with the `
            + `host redacted: ${verboseNext === null ? '(absent or empty)' : show(verboseNext, 300)}`}\n`
        + `      odata=nometadata: ${nometaRows === null
          ? `no value array — ${httpDetail(nometaRes)}${privilegeNote(nometaRes)}`
          : `${nometaRows.length} row(s); typeof odata.nextLink = ${typeof nometaNextRaw}; value with `
            + `the host redacted: ${nometaNext === null ? '(absent or empty)' : show(nometaNext, 300)}`}`;

      if (verboseRows === null && nometaRows === null) {
        const why = `neither flavour returned an item collection from ${JSON.stringify(PAGING_FIXTURE_LIST)}.\n`
          + `      ${perFlavour}\n      Nothing about paging was measured. ${SCOPE_NOTE}`;
        record('S11', S11_Q, 'NOT ESTABLISHED (prerequisite: the items could not be read)', why);
        record('S12', S12_Q, 'NOT ESTABLISHED (prerequisite)', why);
      } else {
        // Follow the VERBOSE link if there is one — that is the construct
        // both deploy templates depend on. Fall back to the nometadata
        // link, and say which was followed, because the two are not the
        // same claim about the platform.
        const pageOne = verboseNext !== null ? verboseRows : nometaRows;
        const link = verboseNext !== null ? verboseNext : nometaNext;
        const linkKind = verboseNext !== null ? 'd.__next (odata=verbose)' : 'odata.nextLink (odata=nometadata)';
        const returned = (verboseRows === null ? nometaRows : verboseRows).length;
        const wholeList = Number.isInteger(itemCount) && returned >= itemCount;

        if (returned === 0) {
          // BELT AND BRACES. The prerequisite above should already have
          // caught this, but a zero-row read must NEVER reach the truncation
          // wording by any path — that is the whole defect this fixes, and a
          // caller whose one-item read succeeded while the full read came
          // back empty is stranger still, not more conclusive.
          record('S11', S11_Q, 'NOT ESTABLISHED (zero items came back — this caller may see none of them)',
                 `${JSON.stringify(PAGING_FIXTURE_LIST)} reports ItemCount=${JSON.stringify(itemCount)} and `
                 + 'the no-$top read returned ZERO rows. THIS IS NOT A TRUNCATION FINDING and must not be '
                 + `quoted as one.\n      THE LEADING HYPOTHESIS IS ITEM-LEVEL TRIMMING. ${TRIMMING_NOTE} `
                 + 'Said plainly: THIS CALLER MAY SIMPLY HAVE NO GRANT ON THIS FIXTURE\'S ITEMS, and an '
                 + 'empty page with no continuation link is exactly what that looks like.\n'
                 + `      ${perFlavour}\n      ${OPERATOR_NOTE}\n      ${SCOPE_NOTE}\n      ${TRUNCATION_NOTE}`);
          record('S12', S12_Q, 'NOT ESTABLISHED (prerequisite)',
                 'S11 got no items back, so there is no page to continue from; see its row.');
        } else if (wholeList) {
          // The server never had to page, so an absent link is expected and
          // says nothing. Recording it as a finding is the mistake the
          // 2026-08-11 enterprise-reader run made and had to withdraw.
          record('S11', S11_Q,
                 'NOT ESTABLISHED (the collection was not larger than the server page size)',
                 `${JSON.stringify(PAGING_FIXTURE_LIST)} reports ItemCount=${JSON.stringify(itemCount)} `
                 + `and the no-$top read returned ${returned} row(s) — the whole list. The server never `
                 + `had to page, so whether a link came back says NOTHING about whether this endpoint `
                 + `pages.\n      ${perFlavour}\n      Point PAGING_FIXTURE_LIST at a list with more `
                 + `items than the server page size, which SharePoint does not document. Do NOT read `
                 + `this row as "the endpoint does not page". ${SCOPE_NOTE}`);
          record('S12', S12_Q, 'NOT ESTABLISHED (prerequisite)',
                 'S11 could not discriminate, so there is nothing to follow; see its row.');
        } else {
          record('S11', S11_Q,
                 `OBSERVED — ${returned} of ItemCount ${JSON.stringify(itemCount)} row(s) with no $top; `
                 + `continuation link ${link === null ? 'ABSENT' : `PRESENT via ${linkKind}`}`,
                 `${JSON.stringify(PAGING_FIXTURE_LIST)} reports ItemCount=${JSON.stringify(itemCount)}. `
                 + `No $top was sent, so the SERVER ended the page.\n      ${perFlavour}\n`
                 + `      ${link === null
                      ? 'A TRUNCATED PAGE WITH NO CONTINUATION would be a finding about both deploy '
                        + 'templates: each stops when its link is absent, so on a collection this size '
                        + 'they would silently read a PARTIAL result and report success. Check S12 and '
                        + 'the raw counts above before quoting it, and read the next paragraph.'
                      : 'The server truncated AND offered a continuation, which is the behaviour both '
                        + 'deploy templates assume. S12 follows it once.'}\n`
                 + `      ${SCOPE_NOTE}\n      ${TRUNCATION_NOTE}`);

          if (link === null) {
            record('S12', S12_Q, 'NOT ESTABLISHED (prerequisite)',
                   'there was no continuation link to follow; see S11, which records what that does and '
                   + 'does not mean.');
          } else {
            // Passed straight back to fetch, the way the deploy templates
            // pass d.__next, rather than rebuilding a URL — a rebuilt URL
            // would be measuring this probe instead of the platform.
            const res2 = await fetch(link, {
              headers: { Accept: `application/json;odata=${verboseNext !== null ? 'verbose' : 'nometadata'}` },
            });
            const text2 = await res2.text();
            let body2 = null;
            try { body2 = JSON.parse(text2); } catch { /* not JSON */ }
            const page2 = res2.ok && body2
              ? ((body2.d && Array.isArray(body2.d.results) && body2.d.results)
                 || (Array.isArray(body2.value) && body2.value) || null)
              : null;
            if (page2 === null) {
              record('S12', S12_Q, outcomeFor({ status: res2.status }),
                     `following ${linkKind} returned HTTP ${res2.status}: ${show(text2, 400)}`
                     + `${privilegeNote({ status: res2.status })}`);
            } else {
              // Whole-set comparison on Id, not first-row: a second page
              // that repeated the first in a different order would read as
              // successful paging and would not be.
              const seen = new Set((pageOne || []).map((r) => r.Id));
              const fresh = page2.filter((r) => !seen.has(r.Id)).length;
              const next2 = body2.d ? body2.d.__next : (body2['odata.nextLink'] || body2['@odata.nextLink']);
              record('S12', S12_Q,
                     `OBSERVED — page 2 held ${page2.length} row(s), ${fresh} of them NOT on page 1`,
                     `followed ${linkKind}. Page 1 held ${(pageOne || []).length} row(s); page 2 held `
                     + `${page2.length}, of which ${fresh} carried an Id page 1 did not. A further link `
                     + `on page 2: ${JSON.stringify(typeof next2 === 'string' && next2 !== '')}. Running `
                     + `total ${seen.size + fresh} against ItemCount ${JSON.stringify(itemCount)}.\n`
                     + `      ${SCOPE_NOTE}`);
            }
          }
        }
      }
    }
  }

  // ================= S6 — THE MARKER, WRITE-GATED =======================
  const S6_Q = 'Does a marker token planted in a list Description match exactly, partially, or not at all?';
  const listPath = `web/lists/getbytitle('${MARKER_LIST_TITLE.replace(/'/g, "''")}')`;

  if (CLEANUP && ALLOW_WRITES) {
    // Tidy-up mode, and nothing else. Unlike the other probes here, this
    // does NOT go on to recreate the list: the S6 measurement spans two
    // pastes, so a reset-then-recreate would restart the crawl clock and
    // the operator would never reach an answer. See the docblock.
    log('INFO', 'CLEANUP is on: this is a TIDY-UP run. S6 will be recycled, not measured.');
    const found = await spGet(listPath);
    if (!found.ok) {
      record('S6', S6_Q, 'NOT ESTABLISHED (cleanup run)',
             `CLEANUP was on, so nothing was measured. There was no list named `
             + `${JSON.stringify(MARKER_LIST_TITLE)} to remove (${httpDetail(found)}).`);
    } else {
      const digest = await getDigest();
      const gone = await spPost(`${listPath}/recycle`, {}, digest);
      record('S6', S6_Q, 'NOT ESTABLISHED (cleanup run)',
             `CLEANUP was on, so nothing was measured. Recycling ${JSON.stringify(MARKER_LIST_TITLE)}: `
             + `${gone.ok ? 'done — it is restorable from the site recycle bin, not purged' : httpDetail(gone)}. `
             + 'Turn CLEANUP off to measure S6 again.');
    }
  } else if (!ALLOW_WRITES) {
    record('S6', S6_Q, 'NOT ESTABLISHED (write flag off)',
           `S6 CREATES A LIST named ${JSON.stringify(MARKER_LIST_TITLE)} on the site you paste into, `
           + 'carrying a marker token in its Description, so it is gated. The list is RECYCLED, not '
           + 'purged, on a later CLEANUP run. Set ALLOW_WRITES = true on a site you are content to '
           + 'leave a probe list on — and read the S6 warnings first, because crawl latency means the '
           + 'answer needs a SECOND paste some time later.');
  } else if (PLACEHOLDER.test(MARKER_TOKEN)) {
    record('S6', S6_Q, 'NOT ESTABLISHED (prerequisite)',
           'MARKER_TOKEN is still the placeholder. Replace CHANGEME with something random, write the '
           + 'value down, and use the SAME value on the follow-up paste — a fresh token restarts the '
           + 'crawl clock and the follow-up would measure nothing.');
  } else {
    const DESCRIPTION = `dbml-sharepoint search discovery probe. Marker: ${MARKER_TOKEN}. Safe to delete.`;
    let created = null;
    let listInfo = await spGet(`${listPath}?$select=Id,Title,Description,Created`);
    if (!listInfo.ok) {
      const digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: MARKER_LIST_TITLE,
        BaseTemplate: 100,
        Description: DESCRIPTION,
      }, digest);
      if (!made.ok) {
        // The reporting service account is unlikely to be able to create a
        // list at all. That refusal is an observation about this caller,
        // recorded as one — not a fact about markers, and not a broken run.
        record('S6', S6_Q, outcomeFor(made),
               `could not create ${JSON.stringify(MARKER_LIST_TITLE)}: ${httpDetail(made)}`
               + `${privilegeNote(made)} Nothing is concluded about crawling or about markers.`);
        listInfo = null;
      } else {
        created = 'this run';
        // Read back and verify, rather than trusting the write.
        listInfo = await spGet(`${listPath}?$select=Id,Title,Description,Created`);
      }
    } else {
      created = 'an earlier run';
    }

    if (listInfo && !listInfo.ok) {
      record('S6', S6_Q, outcomeFor(listInfo),
             `the list could not be read back after being created: ${httpDetail(listInfo)}`
             + `${privilegeNote(listInfo)} Nothing is concluded about the marker — the fixture itself `
             + 'is unverified.');
    } else if (listInfo) {
      const storedDescription = String(listInfo.body.Description == null ? '' : listInfo.body.Description);
      const stampedOk = storedDescription.includes(MARKER_TOKEN);
      const createdAt = listInfo.body.Created;
      const ageHours = (Date.now() - Date.parse(createdAt)) / 3600000;
      if (!stampedOk) {
        record('S6', S6_Q, 'NOT ESTABLISHED (prerequisite: the marker is not in the stored description)',
               `the list exists but its Description read back as ${show(storedDescription, 200)}, which `
               + `does not contain ${JSON.stringify(MARKER_TOKEN)}. Most likely it was created by an `
               + 'earlier run with a DIFFERENT token. Either restore that token, or set CLEANUP = true '
               + 'for one tidy-up run and start again. Nothing is concluded about crawling.');
      } else {
        const variants = [
          ['bare token', MARKER_TOKEN],
          ['quoted phrase', `"${MARKER_TOKEN}"`],
          ['Description property', `Description:"${MARKER_TOKEN}"`],
          ['Description property, within STS_List', `contentclass:STS_List Description:"${MARKER_TOKEN}"`],
        ];
        const lines = [];
        let exactHits = 0;
        let anyRows = 0;
        for (const [label, kql] of variants) {
          const q = await runQuery(kql, '&rowlimit=20');
          if (!q.ok) { lines.push(`      ${label}: ${queryFailure(q)}`); continue; }
          anyRows += q.rows.length;
          // EXACT means: a row came back whose Description actually
          // contains the token. Rows that come back WITHOUT it are the
          // partial-match case, and they are recorded rather than filtered
          // out — a tokeniser that split the marker and matched something
          // else is exactly the finding this question is for.
          const withToken = q.rows.filter((r) => String(cellValue(r, 'Description') || '').includes(MARKER_TOKEN));
          const titles = q.rows.map((r) => show(cellValue(r, 'Title'), 80));
          exactHits += withToken.length;
          lines.push(`      ${label}: ${q.rows.length} row(s); ${withToken.length} carried the full token `
                     + `in a returned Description. Titles: ${JSON.stringify(titles)}`);
        }
        const verdict = exactHits > 0 ? 'EXACT — the full token came back in a Description'
          : anyRows > 0 ? 'PARTIAL — rows matched but none carried the full token'
          : 'NO MATCH YET';
        const young = !Number.isFinite(ageHours) || ageHours < 24;
        searchRecord('S6', S6_Q,
               exactHits > 0 || anyRows > 0
                 ? `OBSERVED — ${verdict}`
                 : `NOT ESTABLISHED (no match yet${young ? '; the list is too new to read as an answer' : ''})`,
               `the list was created by ${created}; Created ${JSON.stringify(createdAt)}, about `
               + `${Number.isFinite(ageHours) ? ageHours.toFixed(1) : '?'} hour(s) before this run at `
               + `${RUN_AT}. Its stored Description read back as ${show(storedDescription, 200)}, `
               + `so the fixture is verified.\n${lines.join('\n')}\n`
               + `      ${anyRows === 0
                    ? 'NO MATCH IS THE EXPECTED FIRST-RUN RESULT AND IS NOT AN ANSWER. A new list\'s '
                      + 'description is not in the index the instant it is written. DO NOT RECORD THIS AS '
                      + '"markers do not work". Leave the list in place, keep MARKER_TOKEN exactly as it '
                      + 'is, and paste this file again in a few hours or a day.'
                    : 'Compare this against S9: a match here bounds crawl latency from above for this '
                      + 'list, and the titles above say whether anything OTHER than the marker list came '
                      + 'back — which is the tokenisation half of the question.'}`);
      }
    }
  }

  } finally {
    // ---- Report --------------------------------------------------------
    // In a `finally`, so a throw anywhere above still prints every question
    // answered before it. A probe that loses its whole transcript to one
    // failed call has wasted the operator's paste.
    report();
  }

  console.log('\n============ WHAT TO SEND BACK ============');
  console.log('1. The whole RESULTS block above, VERBATIM, including the indented');
  console.log('   evidence lines. For S3 and S8 the property dump IS the finding —');
  console.log('   a summary of it answers nothing, and "it looked fine" answers less.');
  console.log('2. WHICH ACCOUNT you pasted this as — the reporting service account, or');
  console.log('   an operator/site owner — and what RUNNING_AS_READER was set to. S10');
  console.log('   means opposite things for the two, and the flag is only believed as');
  console.log('   far as the caller printed beside it agrees with it.');
  console.log('   answer: ______________________________________');
  console.log('3. Which constants you set, and to what (LIST_TITLE, MARKER_TOKEN, and');
  console.log('   PAGING_FIXTURE_LIST if you changed it).');
  console.log('   answer: ______________________________________');
  console.log('4. Whether ALLOW_WRITES was on for this run (S6 is blank if not), and');
  console.log('   whether this was a FIRST paste or the follow-up.');
  console.log('   answer: ______________________________________');
  console.log('5. Which sites this account was actually GRANTED access to. S10 can say');
  console.log('   what came back; only you can say whether that is the right set.');
  console.log('   EXPECT MORE SITES THAN YOU GRANTED, and it is not a leak: intranet and');
  console.log('   hub content readable by any authenticated user shows up too (observed');
  console.log('   2026-08-12). It does mean a bare contentclass:STS_List query is NOT');
  console.log('   self-limiting — say which of the rows you recognise as yours.');
  console.log('   answer: ______________________________________');
  console.log('6. Any 401 or 403 above is a FINDING, not a failed run — send it. Those');
  console.log('   rows say what the reporting identity is refused, which is half of');
  console.log('   what this probe is for.');
  console.log('\nThe site host has been stripped from every URL printed above. If you');
  console.log('see a tenant host anywhere in this transcript, that is a BUG in the');
  console.log('probe — say so, and redact it before sending.');
  console.log('\nThe CALLER\'S LOGIN IS PRINTED DELIBERATELY, so the transcript records');
  console.log('who ran it rather than trusting a hand-set flag. It is an account name:');
  console.log('redact it if this leaves your organisation, and never commit it.');
  console.log('\nDo NOT commit this transcript. Quote the findings into the STATUS');
  console.log('block at the top of the template instead.');
})();
