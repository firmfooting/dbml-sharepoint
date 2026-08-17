/**
 * dbml-sharepoint PROBE: how deep may a CAML And/Or chain go?
 *
 * WHY. `<Includes>` and `<NotIncludes>`, the only two operators Microsoft
 * documents for multi-value columns, return NOTHING against a MultiChoice
 * (test/manual/multi-value-probe.js, C4 and C5, measured 2026-08-10 and
 * re-confirmed 2026-08-17). So this tool has no set operator, and
 * `MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED` tells the author to build one:
 * "combine several with all_of/any_of". That is the shipped remedy.
 *
 * CAML's `And` and `Or` are strictly binary. Both Learn pages say so: "any
 * given And element can have only two conjuncts... If you need to conjoin
 * three or more conditions, you must nest." `_combine` in
 * `analysis/conditions.py` folds left accordingly, so `any_of` over K members
 * emits a tree K-1 deep. `analysis/limits.py` bounds K nowhere.
 *
 * Both Learn pages also say "The server supports unlimited complicated
 * queries." This probe does not doubt that as a statement about a query
 * server. It doubts that it covers the VIEW SAVE, which is a different
 * surface: SharePoint rewrites ViewQuery XML, and a rewrite that still parses
 * and returns different rows is silent. multi-value-probe.js C8 stored one
 * <Eq> and nothing deeper; datetime-sentinel-probe.js already found an
 * element that worked in one position and returned nothing in the other.
 *
 * SCOPE. Depth of a homogeneous Or chain over ONE MultiChoice column, asked
 * at two surfaces: an ad-hoc CamlQuery, and a stored view ViewQuery replayed
 * from the XML SharePoint kept. It does not ask about And chains, mixed
 * trees, chains over several columns, or any other field type. A result here
 * is evidence about Or over MultiChoice and nothing else.
 *
 * WHY A SEPARATE PROBE, and not more rows on multi-value-probe.js: that
 * probe's fixture IS its experiment. Its five-member enum and four rows are
 * what C1 through C14 mean, and widening the enum would change what every one
 * of those rows measures rather than adding to them.
 *
 * THE DESIGN, and the one thing worth understanding before reading a result.
 * Every chain at every depth is padded with members that NO row holds, so the
 * expected answer is identical at depth 1 and at depth 40: the rows holding
 * the single real member. Depth is therefore the only variable, and a change
 * in the answer can only be attributed to depth. Asserting the padding
 * members are absent would be asserting over what is observed; they are
 * seeded absent instead, and Q0 reports what was actually stored.
 *
 * THE CONTROL IS D01. One disjunct is no chain at all, so if D01 does not
 * return the two control rows then the fixture, not the depth, is the
 * finding, and every row below it is void. It says so itself rather than
 * leaving a reader to notice.
 *
 * THE NEGATIVE CONTROLS ARE N1 AND N2. A chain of padding ONLY must return
 * nothing, shallow and deep. Without them "returns the control rows" is
 * consistent with a query that returns everything, and a chain that
 * degenerates into matching every row is one of the ways this can fail.
 *
 * WHAT A FAILURE LOOKS LIKE, since none of them is an HTTP error. A
 * truncated tree, a flattened tree, and a tree that matches everything all
 * parse and all answer 200. Rows are compared, never status codes.
 *
 * WHAT MULTI-VALUE-PROBE.JS ALREADY SETTLED, so this probe does not re-ask
 * it. Run 4 on 2026-08-17 answered C11 through C14 against the five-member
 * fixture: <And> over two membership tests means "contains BOTH", <Or> means
 * "contains EITHER", and a two-deep Or chain SURVIVES being stored as a
 * ViewQuery and replays to the same rows. So chaining works and composes as
 * an author would read it. What is open is only how far it goes, which is why
 * this probe starts where that one stopped.
 *
 * That run also measured the cosmetic rewriting this probe has to allow for:
 * `<FieldRef Name="Evt"/>` was stored as `<FieldRef Name="Evt" />`. A raw
 * string comparison would call every depth REWRITTEN, so whitespace is
 * normalised and REWRITTEN is reserved for a tree that changed shape. The
 * <Or> count is compared as well, because flattening and truncation both
 * change it and both can leave the rows looking right at shallow depth.
 *
 * STATUS: NEVER RUN. Every row below is a question.
 *
 * WHAT IT TOUCHES. One custom list under a run-unique name it prints before
 * doing anything, one MultiChoice column on it, a handful of rows, and one
 * view per depth on that same list. It touches nothing it did not create. If
 * any depth disagrees it LEAVES the list in place, because that is the run
 * worth looking at by hand.
 *
 * HOW TO RUN
 *   1. Open the target site as somebody who can create a list.
 *   2. Open a browser console on any page of that site.
 *   3. Set CONFIRMED = true and ALLOW_WRITES = true, then paste this file.
 *   4. Copy the whole results block back verbatim.
 *
 * WHEN FINISHED: the probe deletes the list it created, unless a depth
 * disagreed. If it aborted early, delete the list whose name it printed in
 * its first line.
 */
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
    log(level, `${id}: ${outcome}. ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };

  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    // PREFIX match, not equality. Outcomes carry their reason:
    // 'NOT ESTABLISHED (throttled)', 'NOT ESTABLISHED (matched 50, expected
    // 60)', 'SHORT (50 of 60, HTTP 200)'. An equality test counts every
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

  // Identifies which version was pasted, since a stale clipboard and a failed fix read the same.
  log('INFO', 'probe revision ad534845. Quote this when reporting results.');

  // Run-unique so the probe never touches a list it did not create.
  const RUN = `${Date.now().toString(36)}`.slice(-6);
  const LIST = `dbmlsp Probe Chain ${RUN}`;
  const COL = 'Chain';

  // 48 members: one that the control rows hold, one second real member so the
  // fixture is not "everything or nothing", and 46 that no row holds and that
  // exist only to make a chain longer.
  const MEMBERS = Array.from({ length: 48 }, (_, i) => `M${String(i + 1).padStart(2, '0')}`);
  const REAL = MEMBERS[0];            // M01, held by the two control rows
  const SECOND = MEMBERS[1];          // M02, held by two rows, never chained
  const PADDING = MEMBERS.slice(2);   // M03.. , held by NOTHING

  // The rows every depth is judged against. Titles carry their own set so a
  // transcript is readable without cross-referencing this block.
  const ROWS = [
    { title: `R1 {${REAL}}`, set: [REAL] },
    { title: `R2 {${REAL},${SECOND}}`, set: [REAL, SECOND] },
    { title: `R3 {${SECOND}}`, set: [SECOND] },
    { title: `R4 {}`, set: [] },
  ];
  // Rows holding REAL, which is what every padded chain must return.
  const CONTROL_ROWS = ROWS.filter((r) => r.set.includes(REAL)).map((r) => r.title).sort();

  const DEPTHS = [1, 2, 3, 4, 6, 8, 12, 16, 24, 32, 40];

  expect('Q0', 'the fixture actually built: a 48-member MultiChoice and four rows with the sets asked for');
  expect('D01', 'ad-hoc CamlQuery: an Or chain of 1 disjunct(s) returns the control rows (CONTROL: no chain at all)');
  expect('D02', 'ad-hoc CamlQuery: an Or chain of 2 disjunct(s) returns the control rows');
  expect('D03', 'ad-hoc CamlQuery: an Or chain of 3 disjunct(s) returns the control rows');
  expect('D04', 'ad-hoc CamlQuery: an Or chain of 4 disjunct(s) returns the control rows');
  expect('D06', 'ad-hoc CamlQuery: an Or chain of 6 disjunct(s) returns the control rows');
  expect('D08', 'ad-hoc CamlQuery: an Or chain of 8 disjunct(s) returns the control rows');
  expect('D12', 'ad-hoc CamlQuery: an Or chain of 12 disjunct(s) returns the control rows');
  expect('D16', 'ad-hoc CamlQuery: an Or chain of 16 disjunct(s) returns the control rows');
  expect('D24', 'ad-hoc CamlQuery: an Or chain of 24 disjunct(s) returns the control rows');
  expect('D32', 'ad-hoc CamlQuery: an Or chain of 32 disjunct(s) returns the control rows');
  expect('D40', 'ad-hoc CamlQuery: an Or chain of 40 disjunct(s) returns the control rows');
  expect('V01', 'stored ViewQuery: an Or chain of 1 disjunct(s) survives being saved and replays to the same rows');
  expect('V02', 'stored ViewQuery: an Or chain of 2 disjunct(s) survives being saved and replays to the same rows');
  expect('V03', 'stored ViewQuery: an Or chain of 3 disjunct(s) survives being saved and replays to the same rows');
  expect('V04', 'stored ViewQuery: an Or chain of 4 disjunct(s) survives being saved and replays to the same rows');
  expect('V06', 'stored ViewQuery: an Or chain of 6 disjunct(s) survives being saved and replays to the same rows');
  expect('V08', 'stored ViewQuery: an Or chain of 8 disjunct(s) survives being saved and replays to the same rows');
  expect('V12', 'stored ViewQuery: an Or chain of 12 disjunct(s) survives being saved and replays to the same rows');
  expect('V16', 'stored ViewQuery: an Or chain of 16 disjunct(s) survives being saved and replays to the same rows');
  expect('V24', 'stored ViewQuery: an Or chain of 24 disjunct(s) survives being saved and replays to the same rows');
  expect('V32', 'stored ViewQuery: an Or chain of 32 disjunct(s) survives being saved and replays to the same rows');
  expect('V40', 'stored ViewQuery: an Or chain of 40 disjunct(s) survives being saved and replays to the same rows');
  expect('N1', 'NEGATIVE CONTROL: a shallow chain of padding only returns NOTHING');
  expect('N2', 'NEGATIVE CONTROL: the deepest chain of padding only returns NOTHING');

  if (!CONFIRMED || !ALLOW_WRITES) {
    log('INFO', 'PLAN. Nothing has been touched.');
    log('INFO', `This probe would create the custom list '${LIST}' with a 48-member`);
    log('INFO', `MultiChoice column '${COL}', seed ${ROWS.length} rows, then run Or chains of`);
    log('INFO', `${DEPTHS.join(', ')} disjuncts as ad-hoc queries and again as stored views.`);
    log('INFO', 'Set CONFIRMED = true and ALLOW_WRITES = true to run it.');
    report();
    return;
  }

  log('INFO', `Creating '${LIST}'. Delete it by hand if this run aborts.`);

  const listPath = `web/lists/getbytitle('${LIST}')`;

  // ---- Bootstrap ---------------------------------------------------------
  let digest = await getDigest();
  const made = await spPost('web/lists', {
    Title: LIST, BaseTemplate: 100, AllowContentTypes: false, ContentTypesEnabled: false,
  }, digest);
  if (!made.ok) {
    record('Q0', 'the fixture actually built', 'NOT ESTABLISHED',
      `the list could not be created: HTTP ${made.status} ${made.text.slice(0, 200)}`);
    report();
    return;
  }

  digest = await getDigest();
  const field = await spPost(`${listPath}/fields`, {
    FieldTypeKind: 15, Title: COL, Choices: { results: MEMBERS },
  }, digest);
  if (!field.ok) {
    record('Q0', 'the fixture actually built', 'NOT ESTABLISHED',
      `the MultiChoice column could not be created: HTTP ${field.status} ${field.text.slice(0, 200)}. `
      + 'multi-value-probe.js M1 created one with a plain POST, so this is a difference worth explaining '
      + 'before reading anything else: that probe used odata=verbose and this harness uses nometadata.');
    report();
    return;
  }

  // WHICH WRITE SHAPE, asked rather than assumed. multi-value-probe.js M3
  // established `collection-metadata` under odata=verbose; this harness talks
  // nometadata, where a bare array is the more likely spelling. Trying in
  // order and reporting the winner costs one request and removes a guess.
  //
  // A shape carrying `__metadata` MUST also send a verbose Content-Type.
  // `__metadata` is meaningless to a nometadata endpoint and SharePoint
  // answers 400, which would read in a transcript as "SharePoint refused this
  // shape" when the probe had simply asked wrongly. Accept stays nometadata,
  // so responses keep the `body.value` form the rest of this file reads.
  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const WRITE_SHAPES = [
    ['collection-metadata', (set) => ({ __metadata: { type: 'Collection(Edm.String)' }, results: set }), VERBOSE],
    ['bare-results', (set) => ({ results: set }), {}],
    ['bare-array', (set) => set, {}],
  ];
  let writeShape = null;
  const seedRow = async (row) => {
    for (const [name, build, headers] of WRITE_SHAPES) {
      if (writeShape && writeShape !== name) continue;
      digest = await getDigest();
      const body = { Title: row.title };
      if (row.set.length) body[COL] = build(row.set);
      const wrote = await spPost(`${listPath}/items`, body, digest, headers);
      if (wrote.ok) { writeShape = name; return { ok: true, shape: name }; }
      if (writeShape) return { ok: false, error: `HTTP ${wrote.status} ${wrote.text.slice(0, 160)}` };
    }
    return { ok: false, error: 'every write shape was refused' };
  };

  const seedErrors = [];
  for (const row of ROWS) {
    const wrote = await seedRow(row);
    if (!wrote.ok) seedErrors.push(`${row.title}: ${wrote.error}`);
  }

  // Read the fixture back rather than trusting the writes. Q0 REPORTS the
  // sets; it does not assert the padding is absent, which is the thing being
  // observed.
  const seeded = await spGet(`${listPath}/items?$select=Title,${COL}&$orderby=Id&$top=100`);
  const seenRows = (!readFailed(seeded) && seeded.body.value) || [];
  const asSet = (v) => (Array.isArray(v) ? v : (v && v.results) || []);
  const seenTitles = seenRows.map((r) => r.Title).sort();
  const wanted = ROWS.map((r) => r.title).sort();
  const mismatched = seenRows
    .filter((r) => {
      const want = ROWS.find((x) => x.title === r.Title);
      return !want || JSON.stringify(asSet(r[COL]).slice().sort()) !== JSON.stringify(want.set.slice().sort());
    })
    .map((r) => `${r.Title} holds ${JSON.stringify(asSet(r[COL]))}`);
  const paddingSeen = seenRows.flatMap((r) => asSet(r[COL])).filter((m) => PADDING.includes(m));
  const fixtureOk = seedErrors.length === 0
    && JSON.stringify(seenTitles) === JSON.stringify(wanted)
    && mismatched.length === 0
    && paddingSeen.length === 0;
  record('Q0', 'the fixture actually built', fixtureOk ? 'BUILT' : 'NOT ESTABLISHED',
    `write shape=${writeShape || 'none accepted'}; rows=${seenRows.length}/${ROWS.length}; `
    + `mismatched=${JSON.stringify(mismatched)}; padding members found on a row=${JSON.stringify(paddingSeen)}; `
    + `seed errors=${JSON.stringify(seedErrors)}. Every depth below is judged against `
    + `${JSON.stringify(CONTROL_ROWS)}, which is the rows holding ${REAL}.`);

  // ---- The chains --------------------------------------------------------
  const ref = `<FieldRef Name="${COL}"/>`;
  const eq = (m) => `<Eq>${ref}<Value Type="Text">${m}</Value></Eq>`;
  // Left fold, matching `_combine` in analysis/conditions.py exactly. A probe
  // folding right would measure a tree this tool never emits.
  const chain = (members) => members.slice(1).reduce((acc, m) => `<Or>${acc}${eq(m)}</Or>`, eq(members[0]));
  // K disjuncts: the real member, then padding. Depth 1 is a bare <Eq>.
  const chainOf = (k) => chain([REAL, ...PADDING.slice(0, k - 1)]);
  const paddingChainOf = (k) => chain(PADDING.slice(0, k));

  // GetItems' payload shape is asked the same way the write shape was.
  let queryShape = null;
  const camlRows = async (where) => {
    const viewXml = `<View><Query><Where>${where}</Where></Query><RowLimit>100</RowLimit></View>`;
    const shapes = [
      ['typed', { query: { __metadata: { type: 'SP.CamlQuery' }, ViewXml: viewXml } }, VERBOSE],
      ['bare', { query: { ViewXml: viewXml } }, {}],
    ];
    for (const [name, payload, headers] of shapes) {
      if (queryShape && queryShape !== name) continue;
      digest = await getDigest();
      const got = await spPost(`${listPath}/GetItems?$select=Title`, payload, digest, headers);
      if (got.ok) {
        queryShape = name;
        return { ok: true, titles: (got.body?.value || []).map((i) => i.Title).sort(), error: null };
      }
      if (queryShape) return { ok: false, titles: null, error: `HTTP ${got.status} ${got.text.slice(0, 160)}` };
    }
    return { ok: false, titles: null, error: 'both CamlQuery payload shapes were refused' };
  };

  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  let anyDisagreement = false;

  // One depth, at the ad-hoc surface.
  const adHoc = async (k) => {
    if (!fixtureOk) {
      return { outcome: 'NOT ESTABLISHED',
        evidence: 'Q0 did not build, so the rows this would be judged against are not the fixture. Fix and re-run.' };
    }
    const where = chainOf(k);
    const got = await camlRows(where);
    if (!got.ok) {
      return { outcome: 'QUERY REFUSED',
        evidence: `${k} disjunct(s), ${where.length} chars: ${got.error}. A refusal is the LOUD outcome. `
          + 'It bounds the depth without anybody having to notice a wrong answer, which is the good way '
          + 'for this to fail.' };
    }
    const ok = same(got.titles, CONTROL_ROWS);
    if (!ok) anyDisagreement = true;
    return {
      outcome: ok ? 'RETURNED THE CONTROL ROWS' : 'DIFFERENT ROWS',
      evidence: `${k} disjunct(s), where clause ${where.length} chars -> ${JSON.stringify(got.titles)}`
        + (ok ? '' : `, expected ${JSON.stringify(CONTROL_ROWS)}. Depth is the only variable between this row `
          + 'and the ones that agreed, so this is where the chain stopped meaning what it says.'),
    };
  };

  // The same depth, stored as a view and replayed from the XML SharePoint
  // KEPT rather than the XML that was sent. A difference in rows can then
  // only come from a difference in the XML.
  const stored = async (k) => {
    if (!fixtureOk) {
      return { outcome: 'NOT ESTABLISHED', evidence: 'Q0 did not build; see that row.' };
    }
    const where = chainOf(k);
    const title = `Chain ${String(k).padStart(2, '0')}`;
    digest = await getDigest();
    const made2 = await spPost(`${listPath}/views`, {
      Title: title, ViewQuery: `<Where>${where}</Where>`, RowLimit: 100,
    }, digest);
    if (!made2.ok) {
      return { outcome: 'VIEW REFUSED',
        evidence: `${k} disjunct(s): HTTP ${made2.status} ${made2.text.slice(0, 200)}. A refusal is the LOUD `
          + 'outcome and the survivable one; it is the silent rewrite below that this probe is for.' };
    }
    const views = await spGet(`${listPath}/views?$select=Title,ViewQuery`);
    const back = (!readFailed(views) && (views.body.value || []).find((v) => v.Title === title)) || null;
    if (!back) {
      return { outcome: 'NOT ESTABLISHED', evidence: `${k} disjunct(s): the view was created but could not be read back.` };
    }
    const storedXml = String(back.ViewQuery || '');
    // SharePoint rewrites the XML COSMETICALLY on save, measured 2026-08-17
    // by multi-value-probe.js C14: `<FieldRef Name="Evt"/>` came back as
    // `<FieldRef Name="Evt" />`. A raw string comparison is therefore false
    // on every row, and "REWRITTEN" would be printed for a run where nothing
    // structural happened, which is a signal that has been spent before it is
    // read. Whitespace is normalised so REWRITTEN means the tree changed.
    const normXml = (x) => x.replace(/\s*\/>/g, '/>').replace(/>\s+</g, '><').trim();
    const identical = normXml(storedXml) === normXml(`<Where>${where}</Where>`);
    // The structural check that actually matters. Flattening and truncation
    // are the two ways a deep tree can come back meaning something else, and
    // both change how many <Or> elements survive. Counting them names the
    // failure even on a row whose rows happen to still agree.
    const orsSent = (where.match(/<Or>/g) || []).length;
    const orsStored = (storedXml.match(/<Or>/g) || []).length;
    const replay = await camlRows(storedXml.replace(/^<Where>/, '').replace(/<\/Where>$/, ''));
    if (!replay.ok) {
      return { outcome: 'NOT ESTABLISHED',
        evidence: `${k} disjunct(s): stored XML could not be replayed: ${replay.error}` };
    }
    const ok = same(replay.titles, CONTROL_ROWS);
    if (!ok) anyDisagreement = true;
    return {
      outcome: ok ? (identical ? 'SURVIVED BYTE-IDENTICAL' : 'SURVIVED, REWRITTEN') : 'DIFFERENT ROWS',
      evidence: `${k} disjunct(s); sent ${where.length} chars with ${orsSent} <Or>, stored `
        + `${storedXml.length} chars with ${orsStored} <Or>`
        + (orsSent === orsStored ? '' : ' -- THE TREE CHANGED SHAPE, which is flattening or truncation')
        + `; ${identical ? 'structurally identical' : 'REWRITTEN on save'}; the stored XML replays to `
        + `${JSON.stringify(replay.titles)}`
        + (ok ? '.' : `, expected ${JSON.stringify(CONTROL_ROWS)}. The save changed what the predicate means, `
          + 'which is the failure this probe exists to catch: it parses, it answers 200, and it is wrong.'),
    };
  };

  {
    const r = await adHoc(1);
    record('D01',
      'ad-hoc CamlQuery: an Or chain of 1 disjunct(s) returns the control rows (CONTROL)',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(2);
    record('D02',
      'ad-hoc CamlQuery: an Or chain of 2 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(3);
    record('D03',
      'ad-hoc CamlQuery: an Or chain of 3 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(4);
    record('D04',
      'ad-hoc CamlQuery: an Or chain of 4 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(6);
    record('D06',
      'ad-hoc CamlQuery: an Or chain of 6 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(8);
    record('D08',
      'ad-hoc CamlQuery: an Or chain of 8 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(12);
    record('D12',
      'ad-hoc CamlQuery: an Or chain of 12 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(16);
    record('D16',
      'ad-hoc CamlQuery: an Or chain of 16 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(24);
    record('D24',
      'ad-hoc CamlQuery: an Or chain of 24 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(32);
    record('D32',
      'ad-hoc CamlQuery: an Or chain of 32 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await adHoc(40);
    record('D40',
      'ad-hoc CamlQuery: an Or chain of 40 disjunct(s) returns the control rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(1);
    record('V01',
      'stored ViewQuery: an Or chain of 1 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(2);
    record('V02',
      'stored ViewQuery: an Or chain of 2 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(3);
    record('V03',
      'stored ViewQuery: an Or chain of 3 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(4);
    record('V04',
      'stored ViewQuery: an Or chain of 4 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(6);
    record('V06',
      'stored ViewQuery: an Or chain of 6 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(8);
    record('V08',
      'stored ViewQuery: an Or chain of 8 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(12);
    record('V12',
      'stored ViewQuery: an Or chain of 12 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(16);
    record('V16',
      'stored ViewQuery: an Or chain of 16 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(24);
    record('V24',
      'stored ViewQuery: an Or chain of 24 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(32);
    record('V32',
      'stored ViewQuery: an Or chain of 32 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }
  {
    const r = await stored(40);
    record('V40',
      'stored ViewQuery: an Or chain of 40 disjunct(s) survives being saved and replays to the same rows',
      r.outcome, r.evidence);
  }

  // ---- Negative controls -------------------------------------------------
  const negative = async (id, k, question) => {
    if (!fixtureOk) { record(id, question, 'NOT ESTABLISHED', 'Q0 did not build; see that row.'); return; }
    const got = await camlRows(paddingChainOf(k));
    if (!got.ok) { record(id, question, 'NOT ESTABLISHED', `${k} disjunct(s): ${got.error}`); return; }
    const empty = got.titles.length === 0;
    if (!empty) anyDisagreement = true;
    record(id, question, empty ? 'RETURNED NOTHING' : 'RETURNED ROWS',
      `${k} padding disjunct(s), none held by any row -> ${JSON.stringify(got.titles)}`
      + (empty
        ? '. So "returns the control rows" above is a real match and not a chain that matches everything.'
        : '. A chain of members NO row holds returned rows, so every positive row above is void: they are '
          + 'consistent with a query that matches everything.'));
  };
  await negative('N1', 2, 'NEGATIVE CONTROL: a shallow chain of padding only returns NOTHING');
  await negative('N2', DEPTHS[DEPTHS.length - 1],
    'NEGATIVE CONTROL: the deepest chain of padding only returns NOTHING');

  report();
  log('INFO', `write shape=${writeShape}, CamlQuery payload shape=${queryShape}. Both were asked, not assumed.`);
  if (anyDisagreement) {
    log('INFO', `KEEPING '${LIST}'. At least one depth disagreed, and that is the run worth opening by hand.`);
    log('INFO', 'Delete it yourself when finished.');
  } else {
    digest = await getDigest();
    const gone = await spPost(`${listPath}/recycle`, {}, digest);
    log('INFO', gone.ok
      ? `Recycled '${LIST}'. It is restorable from the site recycle bin.`
      : `Could not recycle '${LIST}': HTTP ${gone.status}. Delete it by hand.`);
  }
})();
