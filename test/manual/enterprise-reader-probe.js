/**
 * dbml-sharepoint PROBE — THE ENTERPRISE READER TIER
 *
 * STATUS: NOT YET RUN. Every question below is NOT ESTABLISHED until an
 * operator pastes this into a live tenant and reports the transcript.
 * Nothing in this file records an answer yet, and nothing in it predicts
 * one. When it has been run, record the date and the findings HERE, the
 * way formatter-xml-probe.js.j2 and threshold-index-probe.js.j2 do.
 *
 *   RUN:      (not yet)
 *   FINDINGS: (not yet)
 *
 * WHY THIS EXISTS. The `feat/enterprise-reader` branch gives each of the 31
 * shipped families an empty '<XX> Enterprise Readers' site group holding the
 * built-in `Read` on every list, and `build --enterprise-reader <upn>` puts
 * one named service account into it. Because those lists BREAK INHERITANCE,
 * the account ends up with `Read` at LIST scope and only SharePoint's derived
 * `Limited Access` at WEB scope. The customer then points Power BI Pro at
 * many such sites using an Entra user service account.
 *
 * Three things that whole design rests on have never been measured on a
 * tenant. This probe measures them and asserts none of them.
 *
 * ---- WHAT IS ALREADY ESTABLISHED ON MICROSOFT LEARN --------------------
 * These are cited, not re-derived, and they are the reason the questions
 * below are the RIGHT questions:
 *
 *   - `_api/web/getusereffectivepermissions(@user)?@user='<claims login>'`
 *     returns an SP.BasePermissions — a High/Low bitfield. The same method
 *     exists on a list. (SharePoint .NET Server, CSOM, JSOM and REST API
 *     index; Web/List.GetUserEffectivePermissions.)
 *   - Built-in `Read` carries `Use Remote Interfaces`. `Restricted Read`
 *     does not. ("Permission levels in SharePoint".)
 *   - `Limited Access` carries `Use Remote Interfaces` BY DEFAULT, and
 *     LOCKDOWN MODE STRIPS IT. Lockdown mode ("Limited-access user
 *     permission lockdown mode") is ON BY DEFAULT FOR PUBLISHING SITES.
 *     (Same page, "Lockdown mode" section, and the troubleshooting article
 *     "Creating a team site from SharePoint Home doesn't finish", which
 *     names UseRemoteAPI as the permission lockdown mode removes.)
 *
 * So the feature is safe iff the account really does hold UseRemoteAPIs at
 * web scope and ViewListItems at list scope, on the sites it will be
 * pointed at. That is question group A, and nobody has looked.
 *
 * ---- WHAT IT ASKS -----------------------------------------------------
 *
 * GROUP A — the decisive one. Read-only; runs with the write flag OFF.
 *   A1  Does the nominated account resolve READ-ONLY in this site's User
 *       Information List, and to what claims LoginName? A prerequisite for
 *       A2/A3, recorded as its own row so an unresolvable account reads as
 *       "not asked" rather than as a permission finding.
 *   A2  CONTROL: does getusereffectivepermissions work AT ALL for the
 *       account pasting this, at web scope? Without it, a blank A3 is
 *       indistinguishable from an endpoint the caller cannot use. It
 *       OBSERVES the decode; it asserts nothing about which bits come back.
 *   A3  The reader's effective permissions at WEB scope, decoded into
 *       named permissions. HEADLINE OBSERVATION: is UseRemoteAPIs present?
 *   A4  The reader's effective permissions at LIST scope for the nominated
 *       list, decoded. HEADLINE OBSERVATION: is ViewListItems present?
 *   A5  Is the 'Limited-access user permission lockdown mode' site
 *       collection feature active? See the LOCKDOWN MODE note below — the
 *       feature GUID is documented, the REST spelling for reading it is
 *       not, so this row is best-effort and says so in its own evidence.
 *
 * GROUP B — the two claim encodings this branch deliberately did not guess.
 *   WRITE-GATED. Default OFF.
 *   `_reader_enrolment.js.j2` step 3 refuses tenant-wide claims by matching
 *   three login-name needles, which cover two of the four claims Learn
 *   names ("Grant the Everyone claim to external users in Microsoft 365"):
 *   Everyone, Everyone except external users, All Authenticated Users, All
 *   Forms Users. Learn publishes no login-name encoding for the last two,
 *   so they were left out ON PURPOSE with a dated KNOWN LIMIT comment
 *   rather than invented from plausibility.
 *   B1..B4 call `web/ensureuser` for each of the four DISPLAY NAMES and
 *   RECORD the LoginName, Title and PrincipalType that come back, or the
 *   exact failure if it refuses. Each row also reports whether the three
 *   needles the deploy template ships today would have matched what came
 *   back — an observation about the existing guard, not a requirement.
 *
 *   NOTHING HERE IS A PREDICTION. If a claim resolves, that is the answer.
 *   If it refuses, that is equally the answer, and the status and body are
 *   printed verbatim either way.
 *
 * GROUP C — a paging assumption this branch inherited but never measured.
 *   Read-only.
 *   `_security_principals.js.j2` and `_reader_enrolment.js.j2` both page a
 *   site group's members with `web/sitegroups(<id>)/users?$top=5000` and
 *   follow `d.__next`. Nobody has confirmed that endpoint pages with
 *   `__next` at all, or in that shape. C1 checks the group has enough
 *   members for the question to mean anything; C2 asks for $top=1 and
 *   reports whether `d.__next` came back and what shape it is; C3 follows
 *   it and reports whether the second member arrives.
 *
 * ---- WHAT THE WRITE FLAG GUARDS ---------------------------------------
 * ALLOW_WRITES gates GROUP B AND NOTHING ELSE. Groups A and C are pure
 * reads and run with it off.
 *
 * `web/ensureuser` IS A WRITE. It materialises the principal in this
 * site's User Information List (hidden list 'User Information List'), which
 * is why the deploy template takes a form digest for it. IT GRANTS
 * NOTHING — it does not add anybody to a group, does not create a role
 * assignment, and does not change any permission. The side effect is that
 * up to four claim principals may afterwards appear in this site's people
 * picker and in `web/siteusers`. On a disposable probe site that is
 * harmless; on a real site it is untidy and hard to fully undo, so RUN
 * GROUP B ON A SITE YOU ARE WILLING TO THROW AWAY.
 *
 * ---- LOCKDOWN MODE: WHAT IS NOT ESTABLISHED ---------------------------
 * Learn documents the FEATURE (site collection feature "Limited-access
 * user permission lockdown mode") and documents its ID as
 * 7C637B23-06C4-472D-9A9A-7C175762C5C4 under the display name
 * ViewFormPagesLockDown ("SPMT supported SharePoint site features").
 * Learn also documents `Site.Features` as a CSOM property.
 *
 * WHAT LEARN DOES NOT PUBLISH, as far as this author could find, is a REST
 * spelling for reading that feature collection. A5 therefore TRIES the
 * OData mapping of Site.Features and reports exactly what came back,
 * including a non-2xx status and its body. A failed read is recorded as
 * NOT ESTABLISHED, never as "lockdown is off" — absence of evidence here
 * is not evidence of absence, and getting that backwards would report the
 * dangerous configuration as the safe one. If A5 comes back NOT
 * ESTABLISHED, read lockdown mode by eye instead: Site settings > Site
 * collection features, and say which it was.
 *
 * ---- HOW TO RUN -------------------------------------------------------
 *   1. Edit the four constants under CONFIGURATION below. Every one ships
 *      as an obvious placeholder and the probe refuses the group that
 *      needs it until it has been changed. There is deliberately no site
 *      URL: the probe reads the site it is pasted into.
 *   2. Open the target SharePoint site as somebody who can read
 *      permissions there (a site owner or site collection administrator).
 *      F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED = true and paste again. That runs GROUPS A AND C,
 *      which write nothing.
 *   4. ONLY on a disposable site, and only if you want group B answered:
 *      set ALLOW_WRITES = true as well and paste once more.
 *   5. Copy the whole RESULTS block back verbatim, including the raw
 *      payload lines. The transcript stays OUT of this repository — quote
 *      findings into the STATUS block at the top of this file instead.
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
  log('INFO', 'probe revision 678fb34e — quote this when reporting results.');

  // ---- CONFIGURATION ---------------------------------------------------
  // All three are obvious placeholders. Each group refuses to run against
  // an unedited one and says which constant to set, so an unedited paste
  // never produces a row that looks like a measurement.
  //
  // NO SITE URL, deliberately — see the harness.

  // The service account the customer would point Power BI at. A UPN.
  const READER_UPN = 'reporting-service-account@contoso.com';

  // Optional: the claims LoginName, if you already have it (it looks like
  // 'i:0#.f|membership|someone@contoso.com'). Leave empty and A1 resolves
  // it read-only from the site's existing users instead.
  const READER_LOGIN_NAME = '';

  // A list this bundle provisioned — one that BROKE INHERITANCE and carries
  // the Enterprise Readers group's Read grant. That is the whole point of
  // A4: web scope and list scope are expected to differ.
  const LIST_TITLE = 'CHANGE ME - a list this bundle provisioned';

  // The site group to measure paging against, for group C. Any group with
  // at least two members will do; it does NOT have to be the readers group,
  // and C1 says so if the one you picked is too small.
  const GROUP_NAME = 'CHANGE ME - a site group with 2+ members';

  const PLACEHOLDER = /CHANGE ME|reporting-service-account@contoso\.com/;

  // ---- Registration ----------------------------------------------------
  expect('A1', 'Does the nominated account resolve read-only, and to what claims LoginName?');
  expect('A2', 'CONTROL: does getusereffectivepermissions work at all for the account running this?');
  expect('A3', 'The reader\'s effective permissions at WEB scope — is UseRemoteAPIs present?');
  expect('A4', 'The reader\'s effective permissions at LIST scope — is ViewListItems present?');
  expect('A5', 'Is the limited-access user permission lockdown mode site collection feature active?');
  expect('B1', 'What does web/ensureuser return for the display name "Everyone"?');
  expect('B2', 'What does web/ensureuser return for "Everyone except external users"?');
  expect('B3', 'What does web/ensureuser return for "All Authenticated Users"?');
  expect('B4', 'What does web/ensureuser return for "All Forms Users"?');
  expect('C1', 'Does the nominated site group hold at least two members?');
  expect('C2', 'With $top=1, does web/sitegroups(id)/users return d.__next, and in what shape?');
  expect('C3', 'Does following d.__next return the SECOND member?');

  if (!CONFIRMED) {
    log('INFO', 'Would READ, writing nothing: the nominated account\'s effective');
    log('INFO', 'permissions at web scope and at list scope, decoded into named');
    log('INFO', 'permissions; the lockdown-mode site collection feature; and one');
    log('INFO', 'site group\'s membership at $top=1 to see whether it pages.');
    log('INFO', 'Would ADDITIONALLY, only with ALLOW_WRITES = true, call');
    log('INFO', 'web/ensureuser for four tenant-wide claim display names. That is a');
    log('INFO', 'WRITE — it materialises each principal in this site\'s User');
    log('INFO', 'Information List — but it GRANTS NOTHING: no group membership, no');
    log('INFO', 'role assignment, no permission change. Use a disposable site.');
    log('INFO', 'Nothing has been read or written. Set CONFIRMED = true.');
    return;
  }

  // ---- SP.BasePermissions decoding -------------------------------------
  // MIRRORED, NOT INVENTED. Every value below is copied character for
  // character from src/dbml_sharepoint/analysis/permissions.py's
  // BASE_PERMISSIONS, which the deployer already uses to EMIT permission
  // levels — so the probe reads permissions with the same bit positions the
  // tool writes them with, and a divergence would be a bug in one file
  // rather than two independent guesses. Kept in the same order as the
  // Python dict so the two can be diffed by eye.
  //
  // BigInt, because these are 64-bit and JavaScript's bitwise operators are
  // 32-bit: `0x4000000000000000 & x` with plain numbers is silently wrong.
  const BASE_PERMISSIONS = [
    ['ViewListItems',             0x0000000000000001n],
    ['AddListItems',              0x0000000000000002n],
    ['EditListItems',             0x0000000000000004n],
    ['DeleteListItems',           0x0000000000000008n],
    ['ApproveItems',              0x0000000000000010n],
    ['OpenItems',                 0x0000000000000020n],
    ['ViewVersions',              0x0000000000000040n],
    ['DeleteVersions',            0x0000000000000080n],
    ['CancelCheckout',            0x0000000000000100n],
    ['ManagePersonalViews',       0x0000000000000200n],
    ['ManageLists',               0x0000000000000800n],
    ['ViewFormPages',             0x0000000000001000n],
    ['AnonymousSearchAccessList', 0x0000000000002000n],
    ['Open',                      0x0000000000010000n],
    ['ViewPages',                 0x0000000000020000n],
    ['AddAndCustomizePages',      0x0000000000040000n],
    ['ApplyThemeAndBorder',       0x0000000000080000n],
    ['ApplyStyleSheets',          0x0000000000100000n],
    ['ViewUsageData',             0x0000000000200000n],
    ['CreateSSCSite',             0x0000000000400000n],
    ['ManageSubwebs',             0x0000000000800000n],
    ['CreateGroups',              0x0000000001000000n],
    ['ManagePermissions',         0x0000000002000000n],
    ['BrowseDirectories',         0x0000000004000000n],
    ['BrowseUserInfo',            0x0000000008000000n],
    ['AddDelPrivateWebParts',     0x0000000010000000n],
    ['UpdatePersonalWebParts',    0x0000000020000000n],
    ['ManageWeb',                 0x0000000040000000n],
    ['UseClientIntegration',      0x0000001000000000n],
    ['UseRemoteAPIs',             0x0000002000000000n],
    ['ManageAlerts',              0x0000004000000000n],
    ['CreateAlerts',              0x0000008000000000n],
    ['EditMyUserInfo',            0x0000010000000000n],
    ['EnumeratePermissions',      0x4000000000000000n],
  ];
  // EmptyMask (0) and FullMask are in the Python table too and are left out
  // of the loop above on purpose: a zero mask matches every value, so
  // including it would put 'EmptyMask' in the decoded list of literally
  // every result, and FullMask is reported separately below.
  const FULL_MASK = 0x7FFFFFFFFFFFFFFFn;

  // High/Low may arrive as strings or as numbers depending on the OData
  // flavour, so both are coerced through String first. Each is at most
  // 2^32, so no precision is lost on the way in.
  const toMask = (high, low) => (BigInt(String(high)) << 32n) | BigInt(String(low));
  const decodeMask = (mask) => BASE_PERMISSIONS
    .filter(([, bit]) => (mask & bit) === bit)
    .map(([name]) => name);

  // The RESPONSE SHAPE of getusereffectivepermissions is itself an
  // observation, not something this probe knows. Verbose wraps the result
  // under d.<MethodName>; nometadata is flat; some endpoints wrap in
  // 'value'. Every shape this can find is tried and the one that WORKED is
  // reported alongside the numbers, and the raw payload is always printed
  // so a reader can see a shape this ladder does not know about.
  const extractHighLow = (payload) => {
    const candidates = [
      ['flat', payload],
      ['value', payload && payload.value],
      ['d', payload && payload.d],
      ['d.GetUserEffectivePermissions', payload && payload.d && payload.d.GetUserEffectivePermissions],
      ['GetUserEffectivePermissions', payload && payload.GetUserEffectivePermissions],
    ];
    for (const [shape, node] of candidates) {
      if (node && node.High != null && node.Low != null) {
        return { shape, high: node.High, low: node.Low };
      }
    }
    return null;
  };

  // ---- Read helpers ----------------------------------------------------
  // The harness's spGet sends odata=nometadata. Group C has to reproduce
  // what the DEPLOY TEMPLATES send, and `d.__next` is a VERBOSE construct,
  // so verbose gets its own helper rather than being bolted onto spGet.
  // Both keep the harness's contract: `body` is the parsed payload whether
  // or not the request succeeded, so only `ok` says the call worked.
  const spGetVerbose = async (path) => {
    const res = await fetch(`${WEB}/_api/${path}`, {
      headers: { Accept: 'application/json;odata=verbose' },
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };

  // OData string literal: double the single quotes, then percent-encode.
  // encodeURIComponent leaves "'" alone, so the doubling survives — and it
  // DOES encode '#' and '|', which every claims login name contains and
  // which would otherwise truncate the URL at the fragment.
  const odataLiteral = (value) => encodeURIComponent(String(value).replace(/'/g, "''"));

  // Every failure in this probe is reported AS ITS STATUS WITH ITS BODY.
  // A previous probe here collapsed an unexplained HTTP error into
  // "REFUSED" and produced a transcript that read like a measured platform
  // verdict; the ampersand it blamed had nothing to do with it. isRefusal
  // (harness) already carves out identity and throttling, and even a real
  // refusal keeps its status and body attached.
  const httpDetail = (r) => `HTTP ${r.status}: ${String(r.text == null ? JSON.stringify(r.body) : r.text).slice(0, 500)}`;
  const failureOutcome = (r) => (isRefusal(r.status) ? `REFUSED (HTTP ${r.status})` : `NOT ESTABLISHED (HTTP ${r.status})`);

  // ================= GROUP A — read-only ================================

  // ---- A1: resolve the account WITHOUT writing --------------------------
  // `ensureuser` would resolve anything, but it is a write — and group A
  // has to be answerable with the write flag off. So this reads the users
  // the site already knows about. If the account has never touched the
  // site it will not be there, and that is a PREREQUISITE NOT MET, not a
  // permission finding: the difference is the whole reason this is its own
  // row.
  let readerLogin = READER_LOGIN_NAME;
  {
    if (readerLogin) {
      record('A1', 'Does the nominated account resolve read-only, and to what claims LoginName?',
             'OBSERVED — supplied by the operator',
             `READER_LOGIN_NAME was set, so no lookup was needed: ${JSON.stringify(readerLogin)}`);
    } else if (PLACEHOLDER.test(READER_UPN)) {
      record('A1', 'Does the nominated account resolve read-only, and to what claims LoginName?',
             'NOT ESTABLISHED (prerequisite)',
             'READER_UPN is still the placeholder. Set it to the service account UPN and paste again.');
    } else {
      // Two reads, cheapest first. Both are recorded so a reader can see
      // WHICH one answered — the $filter form is the one worth reusing in
      // the deployer if it works, and its working is an observation.
      const wanted = READER_UPN.toLowerCase();
      const filtered = await spGet(
        `web/siteusers?$select=Id,LoginName,Title,Email,PrincipalType&$filter=Email eq '${odataLiteral(READER_UPN)}'`);
      let via = "$filter=Email eq '...'";
      let match = null;
      if (!readFailed(filtered) && Array.isArray(filtered.body.value)) {
        match = filtered.body.value.find((u) => String(u.Email || '').toLowerCase() === wanted) || null;
      }
      let enumerated = null;
      if (!match) {
        // Fall back to the whole collection and match the same two ways
        // _reader_enrolment.js.j2 step 4 does — the mailbox Email, and the
        // UPN the claims LoginName ends in. They are routinely different
        // for the same account.
        via = 'enumerating web/siteusers';
        enumerated = await spGet('web/siteusers?$select=Id,LoginName,Title,Email,PrincipalType&$top=5000');
        const upnPart = (name) => {
          const parts = String(name).split('|');
          return parts[parts.length - 1];
        };
        const rows = (!readFailed(enumerated) && Array.isArray(enumerated.body.value)) ? enumerated.body.value : [];
        match = rows.find((u) => [u.Email, upnPart(u.LoginName)]
          .map((v) => String(v == null ? '' : v).toLowerCase())
          .includes(wanted)) || null;
      }
      if (match && typeof match.LoginName === 'string' && match.LoginName !== '') {
        readerLogin = match.LoginName;
        record('A1', 'Does the nominated account resolve read-only, and to what claims LoginName?',
               'OBSERVED — resolved',
               `via ${via}: LoginName ${JSON.stringify(match.LoginName)}, Title `
               + `${JSON.stringify(match.Title)}, PrincipalType ${JSON.stringify(match.PrincipalType)}`);
      } else {
        const detail = enumerated
          ? `$filter read ${readFailed(filtered) ? httpDetail(filtered) : 'succeeded but matched nobody'}; `
            + `enumeration ${readFailed(enumerated) ? httpDetail(enumerated) : 'succeeded but matched nobody'}`
          : `$filter read ${readFailed(filtered) ? httpDetail(filtered) : 'succeeded but matched nobody'}`;
        record('A1', 'Does the nominated account resolve read-only, and to what claims LoginName?',
               'NOT ESTABLISHED (prerequisite)',
               `${detail}. The account may simply never have been added to this site — that is not a `
               + 'permission finding. Add it (or run the deploy with --enterprise-reader), or paste its '
               + 'claims login into READER_LOGIN_NAME, and run again.');
      }
    }
  }

  // ---- Shared effective-permissions reader ------------------------------
  // depends on: the scope path and the login name, both fixed by the
  // caller. observes: the HTTP status, the response SHAPE, and the bits.
  // Nothing here compares an observed bit against an expectation — the
  // outcome string names what was seen and the decode is printed in full.
  const readEffectivePermissions = async (scopePath, login) => {
    const path = `${scopePath}/getusereffectivepermissions(@user)?@user='${odataLiteral(login)}'`;
    const res = await spGet(path);
    if (readFailed(res)) return { ok: false, res, path };
    const found = extractHighLow(res.body);
    if (!found) return { ok: false, res, path, unknownShape: true };
    const mask = toMask(found.high, found.low);
    return {
      ok: true, res, path, mask, shape: found.shape,
      high: String(found.high), low: String(found.low),
      names: decodeMask(mask), full: mask === FULL_MASK,
    };
  };
  const describePerms = (r) => `High=${r.high} Low=${r.low} (response shape: ${r.shape}); `
    + `decoded: ${r.names.length ? r.names.join(', ') : '(no named permission bit set)'}`
    + `${r.full ? '; this is FullMask' : ''}; raw ${JSON.stringify(r.res.body).slice(0, 400)}`;

  // ---- A2: the control --------------------------------------------------
  // Answered for whoever is pasting, not for the reader. Its job is to
  // separate "the endpoint does not work for this caller" from "the reader
  // holds nothing" — two states that produce identical-looking empty rows.
  // It reports WHAT it decoded and does not require any particular bit:
  // asserting over an observed value is how a control kills its own
  // experiment the moment it starts working.
  {
    const me = await spGet('web/currentuser?$select=LoginName,Title');
    if (readFailed(me) || typeof me.body.LoginName !== 'string') {
      record('A2', 'CONTROL: does getusereffectivepermissions work at all for the account running this?',
             'NOT ESTABLISHED', `could not read web/currentuser: ${httpDetail(me)}`);
    } else {
      const mine = await readEffectivePermissions('web', me.body.LoginName);
      if (!mine.ok) {
        record('A2', 'CONTROL: does getusereffectivepermissions work at all for the account running this?',
               mine.unknownShape ? 'NOT ESTABLISHED (unrecognised response shape)' : failureOutcome(mine.res),
               `${mine.unknownShape ? 'HTTP 200 but no High/Low found in ' + JSON.stringify(mine.res.body).slice(0, 400)
                                    : httpDetail(mine.res)}. `
               + 'A3 and A4 below cannot be read as findings about the reader while this row is open — the '
               + 'endpoint has not been shown to work for the caller at all.');
      } else {
        record('A2', 'CONTROL: does getusereffectivepermissions work at all for the account running this?',
               'OBSERVED — the endpoint answered',
               `for the CALLER ${JSON.stringify(me.body.Title)}: ${describePerms(mine)}`);
      }
    }
  }

  // ---- A3: WEB scope ----------------------------------------------------
  {
    const question = 'The reader\'s effective permissions at WEB scope — is UseRemoteAPIs present?';
    if (!readerLogin) {
      record('A3', question, 'NOT ESTABLISHED (prerequisite)', 'the account did not resolve; see A1');
    } else {
      const r = await readEffectivePermissions('web', readerLogin);
      if (!r.ok) {
        record('A3', question,
               r.unknownShape ? 'NOT ESTABLISHED (unrecognised response shape)' : failureOutcome(r.res),
               r.unknownShape
                 ? `HTTP 200 but no High/Low found in ${JSON.stringify(r.res.body).slice(0, 400)}`
                 : httpDetail(r.res));
      } else {
        const has = r.names.includes('UseRemoteAPIs');
        record('A3', question,
               `OBSERVED — UseRemoteAPIs ${has ? 'PRESENT' : 'ABSENT'}`,
               describePerms(r));
      }
    }
  }

  // ---- A4: LIST scope ---------------------------------------------------
  {
    const question = 'The reader\'s effective permissions at LIST scope — is ViewListItems present?';
    if (PLACEHOLDER.test(LIST_TITLE)) {
      record('A4', question, 'NOT ESTABLISHED (prerequisite)',
             'LIST_TITLE is still the placeholder. Set it to a list this bundle provisioned.');
    } else if (!readerLogin) {
      record('A4', question, 'NOT ESTABLISHED (prerequisite)', 'the account did not resolve; see A1');
    } else {
      // Confirm the list exists FIRST, so a typo reads as a typo. Without
      // this, a 404 for a misspelled title and a genuine refusal look the
      // same in the transcript, and the wrong one is much more alarming.
      const listRes = await spGet(
        `web/lists/getbytitle('${odataLiteral(LIST_TITLE)}')?$select=Title,HasUniqueRoleAssignments`);
      if (readFailed(listRes)) {
        record('A4', question, 'NOT ESTABLISHED (prerequisite)',
               `no list titled ${JSON.stringify(LIST_TITLE)} could be read here: ${httpDetail(listRes)}`);
      } else {
        // Recorded, not required: whether the list actually broke
        // inheritance is the thing that makes list scope differ from web
        // scope, so it belongs in the evidence — but a list that inherits
        // is still a real answer about a real list.
        const unique = listRes.body.HasUniqueRoleAssignments;
        const r = await readEffectivePermissions(
          `web/lists/getbytitle('${odataLiteral(LIST_TITLE)}')`, readerLogin);
        if (!r.ok) {
          record('A4', question,
                 r.unknownShape ? 'NOT ESTABLISHED (unrecognised response shape)' : failureOutcome(r.res),
                 r.unknownShape
                   ? `HTTP 200 but no High/Low found in ${JSON.stringify(r.res.body).slice(0, 400)}`
                   : httpDetail(r.res));
        } else {
          const has = r.names.includes('ViewListItems');
          record('A4', question,
                 `OBSERVED — ViewListItems ${has ? 'PRESENT' : 'ABSENT'}`,
                 `list ${JSON.stringify(LIST_TITLE)}, HasUniqueRoleAssignments=${JSON.stringify(unique)}; `
                 + describePerms(r));
        }
      }
    }
  }

  // ---- A5: lockdown mode, best-effort -----------------------------------
  // See the LOCKDOWN MODE note in the docblock. The feature ID is
  // documented; the REST spelling for reading the collection is not, so
  // the read itself is part of what is being observed. A failure here is
  // recorded as NOT ESTABLISHED and never as "lockdown is off".
  {
    const question = 'Is the limited-access user permission lockdown mode site collection feature active?';
    const LOCKDOWN_ID = '7c637b23-06c4-472d-9a9a-7c175762c5c4';
    const res = await spGet('site/features?$select=DefinitionId&$top=500');
    const rows = (!readFailed(res) && Array.isArray(res.body && res.body.value)) ? res.body.value : null;
    if (rows === null) {
      record('A5', question, 'NOT ESTABLISHED',
             `${readFailed(res) ? httpDetail(res)
                                : `HTTP ${res.status} but no feature array in ${JSON.stringify(res.body).slice(0, 300)}`}`
             + '. This is NOT evidence that lockdown mode is off — the REST spelling used here is not '
             + 'documented on Learn, and the caller may simply not be able to read site features. Check by '
             + 'eye instead: Site settings > Site collection features > "Limited-access user permission '
             + 'lockdown mode", and report Active or Not Active.');
    } else {
      const ids = rows
        .map((f) => String((f && (f.DefinitionId || (f.DefinitionId === 0 ? 0 : ''))) || '').toLowerCase())
        .filter((id) => id !== '');
      const active = ids.includes(LOCKDOWN_ID);
      record('A5', question,
             `OBSERVED — lockdown mode ${active ? 'ACTIVE' : 'NOT LISTED AS ACTIVE'}`,
             `read ${rows.length} site collection feature(s); looked for ${LOCKDOWN_ID} `
             + '(ViewFormPagesLockDown, per Learn\'s SPMT supported site features table). '
             + `${active ? 'It is present.' : 'It is absent from the list that came back.'} `
             + 'Confirm by eye in Site settings > Site collection features before relying on this — the '
             + 'endpoint spelling is undocumented and the collection may be filtered for the caller.');
    }
  }

  // ================= GROUP C — read-only ================================
  // Placed before group B so that a run with ALLOW_WRITES off still ends
  // having answered everything it can.
  {
    const CLAIM_SHAPE_Q = 'With $top=1, does web/sitegroups(id)/users return d.__next, and in what shape?';
    if (PLACEHOLDER.test(GROUP_NAME)) {
      const why = 'GROUP_NAME is still the placeholder. Set it to a site group with at least two members.';
      record('C1', 'Does the nominated site group hold at least two members?', 'NOT ESTABLISHED (prerequisite)', why);
      record('C2', CLAIM_SHAPE_Q, 'NOT ESTABLISHED (prerequisite)', why);
      record('C3', 'Does following d.__next return the SECOND member?', 'NOT ESTABLISHED (prerequisite)', why);
    } else {
      const grpRes = await spGetVerbose(`web/sitegroups/getbyname('${odataLiteral(GROUP_NAME)}')?$select=Id`);
      const groupId = (grpRes.ok && grpRes.body && grpRes.body.d && grpRes.body.d.Id);
      if (!Number.isInteger(groupId)) {
        const why = `could not resolve site group ${JSON.stringify(GROUP_NAME)}: ${httpDetail(grpRes)}`;
        record('C1', 'Does the nominated site group hold at least two members?', 'NOT ESTABLISHED (prerequisite)', why);
        record('C2', CLAIM_SHAPE_Q, 'NOT ESTABLISHED (prerequisite)', why);
        record('C3', 'Does following d.__next return the SECOND member?', 'NOT ESTABLISHED (prerequisite)', why);
      } else {
        // C1 — the prerequisite, read exactly the way the deploy templates
        // read it. A group with fewer than two members cannot answer C2 or
        // C3 either way, and reporting "no __next" from a one-member group
        // as a finding about the ENDPOINT would be a false negative.
        const allRes = await spGetVerbose(`web/sitegroups(${groupId})/users?$select=Id,LoginName,Title&$top=5000`);
        const all = (allRes.ok && allRes.body && allRes.body.d && Array.isArray(allRes.body.d.results))
          ? allRes.body.d.results : null;
        if (all === null) {
          const why = `membership read failed or was not in the d.results shape: ${httpDetail(allRes)}`;
          record('C1', 'Does the nominated site group hold at least two members?', failureOutcome(allRes), why);
          record('C2', CLAIM_SHAPE_Q, 'NOT ESTABLISHED (prerequisite)', why);
          record('C3', 'Does following d.__next return the SECOND member?', 'NOT ESTABLISHED (prerequisite)', why);
        } else if (all.length < 2) {
          const why = `group ${JSON.stringify(GROUP_NAME)} holds ${all.length} member(s) at $top=5000. `
            + 'C2 and C3 need at least two: with one member there is nothing to page to, so an absent '
            + '__next would say nothing about the endpoint. Pick a bigger group and run again.';
          record('C1', 'Does the nominated site group hold at least two members?', 'NOT ESTABLISHED (prerequisite)', why);
          record('C2', CLAIM_SHAPE_Q, 'NOT ESTABLISHED (prerequisite)', why);
          record('C3', 'Does following d.__next return the SECOND member?', 'NOT ESTABLISHED (prerequisite)', why);
        } else {
          record('C1', 'Does the nominated site group hold at least two members?',
                 'OBSERVED — enough members',
                 `${all.length} member(s) read in one page at $top=5000, in the d.results shape both deploy `
                 + 'templates assume');

          // C2 — identical to the deploy's request except for $top.
          const firstRes = await spGetVerbose(`web/sitegroups(${groupId})/users?$select=Id,LoginName,Title&$top=1`);
          const firstPage = (firstRes.ok && firstRes.body && firstRes.body.d
                             && Array.isArray(firstRes.body.d.results)) ? firstRes.body.d.results : null;
          if (firstPage === null) {
            const why = `$top=1 read failed or was not in the d.results shape: ${httpDetail(firstRes)}`;
            record('C2', CLAIM_SHAPE_Q, failureOutcome(firstRes), why);
            record('C3', 'Does following d.__next return the SECOND member?', 'NOT ESTABLISHED (prerequisite)', why);
          } else {
            const next = firstRes.body.d.__next;
            // The site host is stripped before printing. __next is an
            // absolute URL, so quoting it raw would put the tenant into the
            // transcript — this repository has leaked one twice. Whether it
            // WAS absolute is still recorded, because that is the part the
            // deploy's `membersUrl = json.d.__next` depends on.
            const redacted = typeof next === 'string' ? next.split(WEB).join('<site>') : next;
            const present = typeof next === 'string' && next !== '';
            record('C2', CLAIM_SHAPE_Q,
                   `OBSERVED — d.__next ${present ? 'PRESENT' : 'ABSENT'}`,
                   `$top=1 returned ${firstPage.length} row(s); typeof d.__next = ${typeof next}; `
                   + `absolute (starts with this site's URL): ${present ? String(next.startsWith(WEB)) : 'n/a'}; `
                   + `value with the site host redacted: ${JSON.stringify(redacted)}`);

            // C3 — follow it. The deploy passes d.__next straight back to
            // fetch, so this does too, rather than rebuilding a URL.
            const q3 = 'Does following d.__next return the SECOND member?';
            if (!present) {
              record('C3', q3, 'NOT ESTABLISHED (prerequisite)',
                     'there was no d.__next to follow; see C2. NOTE: both _security_principals.js.j2 and '
                     + '_reader_enrolment.js.j2 stop paging when __next is absent, so this run says their '
                     + 'loops would have read only the first page of this group.');
            } else {
              const res2 = await fetch(next, { headers: { Accept: 'application/json;odata=verbose' } });
              const text2 = await res2.text();
              let body2 = null;
              try { body2 = JSON.parse(text2); } catch { /* not JSON */ }
              const page2 = (res2.ok && body2 && body2.d && Array.isArray(body2.d.results)) ? body2.d.results : null;
              if (page2 === null) {
                record('C3', q3,
                       isRefusal(res2.status) ? `REFUSED (HTTP ${res2.status})` : `NOT ESTABLISHED (HTTP ${res2.status})`,
                       `following d.__next returned HTTP ${res2.status}: ${text2.slice(0, 400)}`);
              } else {
                const firstId = firstPage.length ? firstPage[0].Id : null;
                const secondId = page2.length ? page2[0].Id : null;
                const isSecond = page2.length > 0 && secondId !== firstId;
                record('C3', q3,
                       `OBSERVED — second page ${page2.length ? 'returned' : 'empty'}`
                       + `${page2.length ? (isSecond ? ', a DIFFERENT member' : ', the SAME member again') : ''}`,
                       `page 1 member Id ${JSON.stringify(firstId)}; page 2 held ${page2.length} row(s), `
                       + `first Id ${JSON.stringify(secondId)}; page 2 __next present: `
                       + `${JSON.stringify(typeof body2.d.__next === 'string' && body2.d.__next !== '')}`);
              }
            }
          }
        }
      }
    }
  }

  // ================= GROUP B — WRITE-GATED ==============================
  const CLAIM_NAMES = [
    ['B1', 'Everyone'],
    ['B2', 'Everyone except external users'],
    ['B3', 'All Authenticated Users'],
    ['B4', 'All Forms Users'],
  ];
  const claimQuestion = (display) => `What does web/ensureuser return for the display name "${display}"?`;

  if (!ALLOW_WRITES) {
    for (const [id, display] of CLAIM_NAMES) {
      record(id, claimQuestion(display), 'NOT ESTABLISHED (write flag off)',
             'ensureuser materialises the principal in this site\'s User Information List, so it is a '
             + 'write and is gated. It GRANTS NOTHING — no group membership, no role assignment, no '
             + 'permission change. Set ALLOW_WRITES = true on a DISPOSABLE site to answer this.');
    }
  } else {
    log('INFO', 'ALLOW_WRITES is on: calling web/ensureuser for four claim display names.');
    log('INFO', 'This materialises each resolved principal in this site\'s User Information');
    log('INFO', 'List. It grants nothing, but the principals may afterwards appear in this');
    log('INFO', 'site\'s people picker and in web/siteusers.');

    // The three needles _reader_enrolment.js.j2 step 3 ships TODAY. Copied
    // verbatim so each row can report whether the guard as it stands would
    // have caught what came back. That is an OBSERVATION about the guard,
    // not a requirement on the answer — a claim that no needle matches is
    // exactly the finding this probe exists to produce.
    const SHIPPED_NEEDLES = ['spo-grid-all-users', 'c:0(.s|true', 'c:0-.f|rolemanager'];

    // Two flavours, because the deploy sends verbose and the harness sends
    // nometadata, and which of them ensureuser accepts is not something to
    // assume: a nometadata rejection reported as "the claim was refused"
    // would be a fabricated platform verdict. Whichever answered is named
    // in the evidence.
    const ensureUser = async (logonName) => {
      const select = 'web/ensureuser?$select=Id,LoginName,Title,Email,PrincipalType';
      const digestA = await getDigest();
      const flat = await spPost(select, { logonName }, digestA);
      if (flat.ok) return { attempt: 'odata=nometadata', res: flat, node: flat.body };
      const digestB = await getDigest();
      const verbose = await spPost(select, { logonName }, digestB, {
        Accept: 'application/json;odata=verbose',
        'Content-Type': 'application/json;odata=verbose',
      });
      if (verbose.ok) {
        return { attempt: 'odata=verbose (nometadata was refused first)', res: verbose,
                 node: verbose.body && verbose.body.d };
      }
      return { attempt: 'both', res: flat, fallback: verbose, node: null };
    };

    for (const [id, display] of CLAIM_NAMES) {
      const question = claimQuestion(display);
      const out = await ensureUser(display);
      if (!out.node) {
        const extra = out.fallback
          ? ` The odata=verbose retry also failed: ${httpDetail(out.fallback)}.`
          : '';
        record(id, question, failureOutcome(out.res),
               `${httpDetail(out.res)}.${extra} Reported as the status it actually returned — this row `
               + 'says what the platform did, not whether the claim "should" exist.');
        continue;
      }
      const login = String(out.node.LoginName == null ? '' : out.node.LoginName);
      const matched = SHIPPED_NEEDLES.filter((n) => login.toLowerCase().includes(n));
      record(id, question, 'OBSERVED — resolved',
             `via ${out.attempt}: LoginName ${JSON.stringify(out.node.LoginName)}, Title `
             + `${JSON.stringify(out.node.Title)}, PrincipalType ${JSON.stringify(out.node.PrincipalType)}, `
             + `Email ${JSON.stringify(out.node.Email)}, Id ${JSON.stringify(out.node.Id)}. `
             + `The three needles _reader_enrolment.js.j2 ships today would ${matched.length
                 ? `MATCH this (${matched.join(', ')})` : 'NOT match this'}.`);
    }
  }

  // ---- Report ----------------------------------------------------------
  report();

  console.log('\n============ WHAT TO SEND BACK ============');
  console.log('1. The whole RESULTS block above, verbatim, including the evidence');
  console.log('   lines — the decoded permission names are the finding, not the');
  console.log('   PRESENT/ABSENT word beside them.');
  console.log('2. Whether the site you pasted this into is a PUBLISHING site.');
  console.log('   Lockdown mode is on by default for those, and that is exactly');
  console.log('   what would strip UseRemoteAPIs from Limited Access.');
  console.log('   answer: ______________________________________');
  console.log('3. If A5 came back NOT ESTABLISHED: Site settings > Site collection');
  console.log('   features > "Limited-access user permission lockdown mode" —');
  console.log('   Active or Not Active?');
  console.log('   answer: ______________________________________');
  console.log('4. Whether ALLOW_WRITES was on for this run (group B is blank if not).');
  console.log('   answer: ______________________________________');
  console.log('\nDo NOT commit this transcript. It carries the site host, the account');
  console.log('UPN and real principal ids. Quote the findings into the STATUS block');
  console.log('at the top of enterprise-reader-probe.js.j2 instead.');
  console.log('===========================================');
})();
