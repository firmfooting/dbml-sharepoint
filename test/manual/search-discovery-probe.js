/**
 * dbml-sharepoint PROBE — SEARCH AS A FLEET DISCOVERY MECHANISM
 *
 * STATUS: NOT YET RUN. Nothing below has been measured on any tenant.
 * EVERY question in this file is NOT ESTABLISHED until an operator pastes
 * it into a live site and sends the transcript back. Until then this file
 * is a list of things nobody here knows — do not cite any row of it, and
 * do not let a plausible-sounding expectation in a comment be read as a
 * result. When it has run, quote the findings into this block, dated, and
 * say which site kind they came from.
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
 *   1. That `contentclass:STS_List` enumerates LISTS at all. Learn samples
 *      STS_Site. It says nothing here about STS_List.
 *   2. What identity properties come back WITH a list row. The design
 *      needs a stable list GUID and a site/web URL IN THE SAME ROW, so a
 *      consumer can build a REST path without a second call per hit. If
 *      that costs a second call, the mechanism has not bought anything.
 *   3. Whether a list's Description is crawled, and whether a marker token
 *      planted in one is exact-matchable — the candidate way to tag which
 *      lists are ours without relying on titles.
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
 *   S1  CONTROL. Does `_api/search/query` answer THIS caller at all, for a
 *       trivial query? Without it, every row below is a fact about the
 *       endpoint rather than about the question it was asked. NOTE: zero
 *       rows still passes S1 — the control is about the endpoint
 *       ANSWERING, and requiring rows would make the control assert over
 *       an observation.
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
 *   S10 Security trimming. CANNOT BE ESTABLISHED FROM A PRIVILEGED
 *       OPERATOR ACCOUNT — see the section below. Registered, and recorded
 *       as NOT ANSWERABLE FROM THIS ACCOUNT.
 *
 * WRITE-GATED. Default OFF; the run is useful without it.
 *
 *   S6  The marker question. CREATES A LIST whose Description carries a
 *       distinctive machine-readable token, then queries for that token
 *       and records whether it matched EXACTLY, PARTIALLY, or NOT AT ALL.
 *       See the two warnings below — they are the difference between an
 *       answer and a fabricated one.
 *
 * ---- S10: WHY IT IS NOT ANSWERABLE HERE, AND MUST NOT READ AS A PASS ---
 * Security trimming cannot be demonstrated by an account that can see
 * everything. A trimmed result and an untrimmed result ARE IDENTICAL to
 * such a caller — both return everything that account may see, which is
 * everything. Running this as a site collection administrator and getting
 * a full result set is not evidence that trimming works; it is not
 * evidence of anything at all about trimming.
 *
 * What WOULD answer it: run the same STS_List query while SIGNED IN AS THE
 * REPORTING SERVICE ACCOUNT, on a tenant where that account has access to
 * some sites and not others, and compare the sites that come back against
 * the sites it was granted. That is a different session, so no revision of
 * this file can close S10 — it can only refuse to pretend.
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
 * ---- HOW TO RUN -------------------------------------------------------
 *   1. Edit the two constants under CONFIGURATION. Both ship as obvious
 *      placeholders, and the questions that need them refuse to run and
 *      say which constant to set, so an unedited paste never produces a
 *      row that looks like a measurement. There is deliberately NO SITE
 *      URL: the probe reads the site it was pasted into.
 *   2. Open the target SharePoint site. F12 -> Console -> paste -> Enter.
 *      It prints its plan and stops.
 *   3. Set CONFIRMED = true and paste again. That answers everything
 *      except S6 and writes nothing.
 *   4. Optionally, on a site you are content to leave a list on: set
 *      ALLOW_WRITES = true as well and paste once more. Then read the S6
 *      warnings above — you will need to come back.
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
  log('INFO', 'probe revision bbeafed3 — quote this when reporting results.');

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

  if (!CONFIRMED) {
    log('INFO', 'Would READ, writing nothing: several _api/search/query GETs — a');
    log('INFO', 'trivial control query, contentclass:STS_List at a few row limits,');
    log('INFO', 'a query for the configured list title, and contentclass:"STS_Site".');
    log('INFO', 'Also web/lists on this site, to tell an unmet prerequisite (no list');
    log('INFO', 'here HAS a description) from a finding (descriptions are not');
    log('INFO', 'returned). Every recorded URL has the site host stripped first.');
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
    : httpDetail(q.res));
  const queryOutcome = (q) => (q.unknownShape
    ? 'NOT ESTABLISHED (unrecognised response shape)'
    : failureOutcome(q.res));

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
  let searchAnswers = false;
  {
    const q = await runQuery('sharepoint', '&rowlimit=1');
    if (!q.ok) {
      record('S1', 'CONTROL: does _api/search/query answer this caller at all, for a trivial query?',
             queryOutcome(q),
             `${queryFailure(q)}. EVERY OTHER ROW IN THIS RUN IS NOW ABOUT THE ENDPOINT, NOT ABOUT `
             + 'the question it was asked. Do not read S2-S9 as findings about search discovery while '
             + 'this row is open.');
    } else {
      searchAnswers = true;
      record('S1', 'CONTROL: does _api/search/query answer this caller at all, for a trivial query?',
             'OBSERVED — the endpoint answered',
             `${describeQuery(q)}. A row count of 0 is still an answer to THIS question: it says the `
             + 'endpoint served the caller. What it does not say is anything about the index.');
    }
  }

  // ================= S2 / S3 — CAN SEARCH ENUMERATE LISTS? ==============
  // Deliberately sent with NO selectproperties. Naming the properties we
  // want would decide what comes back, and what comes back BY DEFAULT is
  // exactly what S3 is asking. Constraining the answer and then reporting
  // it as the answer is how a probe measures its own input.
  let firstListRow = null;
  {
    const S2_Q = 'Does contentclass:STS_List return rows, how many, and what total is reported?';
    const S3_Q = 'For the first STS_List row: EVERY property name returned, and its value.';
    const q = await runQuery('contentclass:STS_List', '&rowlimit=10');
    if (!q.ok) {
      const detail = queryFailure(q);
      record('S2', S2_Q, queryOutcome(q),
             `${detail}. This is the decisive unknown, so be careful reading it: the query FAILING is `
             + 'not the same as STS_List not being a content class. Check S1 first, then S8 — if the '
             + 'documented STS_Site query works and this one does not, THAT is the finding.');
      record('S3', S3_Q, 'NOT ESTABLISHED (prerequisite)', 'S2 returned no result set to inspect.');
    } else {
      record('S2', S2_Q, `OBSERVED — ${q.rows.length} row(s) returned`,
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

        record('S3', S3_Q, `OBSERVED — ${names.length} propert${names.length === 1 ? 'y' : 'ies'} on the first row`,
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
      record('S4', S4_Q,
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
             + `${httpDetail(localLists)}. Without that, an empty Description column in the search `
             + 'result cannot be told from there being nothing to crawl.');
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
        record('S5', S5_Q, queryOutcome(q), `neither the default nor the explicit-select query `
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
        record('S5', S5_Q, 'OBSERVED — see the per-query counts',
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
    record('S7', S7_Q,
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
  {
    const S8_Q = 'Does the contentclass:"STS_Site" fallback work, and what identity comes back per site?';
    const q = await runQuery('contentclass:"STS_Site"', '&rowlimit=10');
    if (!q.ok) {
      record('S8', S8_Q, queryOutcome(q),
             `${queryFailure(q)}. Note what this would mean if S2 also failed: the DOCUMENTED, `
             + 'Microsoft-sampled query did not work either, which points at the endpoint or this '
             + 'caller rather than at STS_List.');
    } else if (q.rows.length === 0) {
      record('S8', S8_Q, 'OBSERVED — 0 rows',
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
      record('S8', S8_Q, `OBSERVED — ${q.rows.length} site row(s) returned`,
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
      record('S9', S9_Q, `OBSERVED — at ${RUN_AT}, the newest list here is ${hit ? 'IN' : 'NOT IN'} the result set`,
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
  // Registered, and deliberately NOT answered. The outcome string starts
  // with NOT ESTABLISHED on purpose: the harness's report() counts those as
  // open, so this stays visible in the summary instead of quietly reading
  // as a pass.
  {
    const S10_Q = 'Is the result set security-trimmed for the querying identity?';
    const me = await spGet('web/currentuser?$select=Title,IsSiteAdmin');
    const who = readFailed(me)
      ? `web/currentuser could not be read (${httpDetail(me)})`
      : `the caller is ${JSON.stringify(show(me.body.Title, 80))}, IsSiteAdmin=${JSON.stringify(me.body.IsSiteAdmin)}`;
    record('S10', S10_Q, 'NOT ESTABLISHED (not answerable from this account)',
           `${who}. THIS RUN CANNOT ANSWER THIS AND DID NOT TRY. A trimmed result set and an untrimmed `
           + 'one are IDENTICAL to a caller who can see everything: both return everything that account '
           + 'may see. So a full result set here is not weak evidence that trimming works — it is no '
           + 'evidence at all, and quoting it as reassurance would be worse than leaving the question '
           + 'open.\n'
           + '      WHAT WOULD ANSWER IT: run the same contentclass:STS_List query while SIGNED IN AS '
           + 'THE REPORTING SERVICE ACCOUNT, on a tenant where it has access to some sites and not '
           + 'others, then compare the sites that come back against the sites it was granted. That is a '
           + 'different session, so no revision of this probe can close it. Learn documents that search '
           + 'trims on the submitting identity; what is unmeasured is this tenant, this account.');
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
        record('S6', S6_Q, failureOutcome(made),
               `could not create ${JSON.stringify(MARKER_LIST_TITLE)}: ${httpDetail(made)}`);
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
      record('S6', S6_Q, failureOutcome(listInfo),
             `the list could not be read back after being created: ${httpDetail(listInfo)}. Nothing is `
             + 'concluded about the marker — the fixture itself is unverified.');
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
        record('S6', S6_Q,
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
  console.log('2. Which constants you set, and to what (LIST_TITLE, MARKER_TOKEN).');
  console.log('   answer: ______________________________________');
  console.log('3. Whether ALLOW_WRITES was on for this run (S6 is blank if not), and');
  console.log('   whether this was a FIRST paste or the follow-up.');
  console.log('   answer: ______________________________________');
  console.log('4. Roughly how many sites and lists this account can see across the');
  console.log('   tenant, and whether you are a site collection admin. S2 and S8 row');
  console.log('   counts mean nothing without it, and S10 depends on it entirely.');
  console.log('   answer: ______________________________________');
  console.log('\nThe site host has been stripped from every URL printed above. If you');
  console.log('see a tenant host anywhere in this transcript, that is a BUG in the');
  console.log('probe — say so, and redact it before sending.');
  console.log('\nDo NOT commit this transcript. Quote the findings into the STATUS');
  console.log('block at the top of the template instead.');
})();
