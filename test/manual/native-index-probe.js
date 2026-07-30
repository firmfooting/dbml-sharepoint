/**
 * dbml-sharepoint PROBE — NATIVE INDEXES AND NULL-TEST FILTERS
 *
 * TWO QUESTIONS, both raised by the filtered-view index check in
 * analysis/checks/_views.py, and both currently recorded there as unknown:
 *
 *   1. Do SharePoint's built-in Created, Modified, Author and Editor columns
 *      carry an index the platform maintains, the way ID does? The check
 *      currently treats ONLY ID as natively indexed and stays silent about
 *      the other four rather than guessing either way.
 *
 *   2. Can a null test — CAML <IsNull>, OData `eq null` — be served past the
 *      list view threshold when the column IS indexed? Microsoft's threshold
 *      guidance is written for comparison filters and says nothing about
 *      presence tests. The check therefore warns about the exposure but
 *      refuses to recommend an index for a null-only filter.
 *
 * WHY IT MATTERS: on question 1, a warning naming a system column would
 * demand a remedy nobody can carry out — `indexes { Created }` is rejected by
 * the DBML parser, because a system column is not a DBML column. On question
 * 2, four views in the shipped template library filter on nothing but
 * `is_null` (the library's "blank means still open" idiom), and the answer
 * decides whether they can be fixed at all.
 *
 * SOURCE for what IS documented
 *   https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 *   https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59
 *
 * WHAT IT ASKS
 *   NATID   ID        — the CONTROL; read its answer FIRST (see below)
 *   NATCRE  Created   NATMOD  Modified
 *   NATAUT  Author    NATEDI  Editor
 *   CMPIDX  indexed column, COMPARISON filter, list past the threshold
 *   NULLIDX indexed column, NULL filter, the same list
 *
 * READ NATID FIRST. SharePoint maintains an index on ID, so if `Indexed`
 * reads false there, the property measures "somebody added an index" and NOT
 * "the platform can serve a query from one" — and NATCRE/NATMOD/NATAUT/NATEDI
 * are then evidence about the wrong thing and must not be read as answers.
 * That is the whole reason ID is asked about at all.
 *
 * THIS PROBE IS READ-ONLY. Every request is a GET. It creates nothing,
 * changes nothing and deletes nothing, so the inherited CONFIRMED /
 * ALLOW_WRITES / CLEANUP gates below are never consulted — they come from the
 * shared harness and are left in place rather than deleted, so one probe
 * cannot drift from the others. spPost() and resetList() are never called.
 *
 * It reads OTHER PEOPLE'S LISTS, which no other probe in this directory does.
 * That is deliberate and it is the only way to answer either question without
 * writing: question 1 needs built-in columns on lists this probe did not
 * make, and question 2 needs a list already past the threshold. It reads
 * titles, item counts, field metadata, and at most one item id per query.
 * It never reads item CONTENT.
 *
 * HOW TO RUN
 *   1. Open the SharePoint site you want the answer for.
 *   2. F12 -> Console -> paste -> Enter. There is nothing to enable.
 *   3. Copy the complete RESULTS block back verbatim.
 *
 * STATUS: NOT YET RUN as of 2026-07-30.
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
    const open = RESULTS.filter((r) => r.outcome === 'NOT ESTABLISHED').length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} NOT established.`);
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };

  // How many lists to sample for question 1. A single list cannot answer it:
  // `Indexed: true` on one list may be an index its own owner added, so the
  // evidence is the DISTRIBUTION across several. Uniform false across a dozen
  // lists is a real answer; one list is an anecdote.
  const SAMPLE_LISTS = 12;

  // Read the documented figure, not a guess. Kept beside the check's own
  // constant in analysis/checks/_views.py.
  const LIST_VIEW_THRESHOLD = 5000;

  const SYSTEM_COLUMNS = ['ID', 'Created', 'Modified', 'Author', 'Editor'];
  const QUESTION_FOR_COLUMN = {
    ID: 'NATID', Created: 'NATCRE', Modified: 'NATMOD',
    Author: 'NATAUT', Editor: 'NATEDI',
  };

  expect('NATID', 'ID reports Indexed — the control for the four below');
  expect('NATCRE', 'Created carries a platform-maintained index');
  expect('NATMOD', 'Modified carries a platform-maintained index');
  expect('NATAUT', 'Author carries a platform-maintained index');
  expect('NATEDI', 'Editor carries a platform-maintained index');
  expect('CMPIDX', 'Comparison filter on an indexed column survives the threshold');
  expect('NULLIDX', 'Null filter on an indexed column survives the threshold');

  const odata = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));

  // ---- Enumerate candidate lists -------------------------------------
  const lists = await spGet(
    'web/lists?$select=Title,ItemCount,BaseTemplate,Hidden&$top=5000');
  if (readFailed(lists)) {
    log('FAIL', `Could not enumerate lists: HTTP ${lists.status}. Nothing can be asked.`);
    report();
    return;
  }
  // BaseTemplate 100 is the generic list — the only shape this tool builds,
  // and the shape the check's warning is about.
  const candidates = (lists.body.value || [])
    .filter((l) => l.Hidden === false && l.BaseTemplate === 100);
  log('INFO', `${candidates.length} visible generic list(s) on this web.`);
  if (!candidates.length) {
    log('FAIL', 'No visible generic list on this web, so no built-in column to read.');
    report();
    return;
  }

  // ---- Question 1: are the built-in columns indexed? -----------------
  // Widest lists first: a list somebody has actually tuned is likelier to
  // carry author-added indexes, and seeing those is how the distribution
  // becomes readable rather than a row of identical falses.
  const sample = candidates
    .slice()
    .sort((a, b) => b.ItemCount - a.ItemCount)
    .slice(0, SAMPLE_LISTS);

  // {column: {true: n, false: n, unread: n}}
  const tally = {};
  for (const column of SYSTEM_COLUMNS) tally[column] = { yes: [], no: [], unread: 0 };

  for (const list of sample) {
    for (const column of SYSTEM_COLUMNS) {
      const field = await spGet(
        `web/lists/getbytitle('${odata(list.Title)}')/fields/` +
        `getbyinternalnameortitle('${column}')?$select=InternalName,Indexed,TypeAsString`);
      // `Indexed` absent is NOT `Indexed: false`. An older $select shape or a
      // field the account cannot read would otherwise be counted as a
      // measured "no" and quietly become half the evidence.
      if (readFailed(field) || typeof field.body.Indexed !== 'boolean') {
        tally[column].unread += 1;
        continue;
      }
      tally[column][field.body.Indexed ? 'yes' : 'no'].push(list.Title);
    }
  }

  for (const column of SYSTEM_COLUMNS) {
    const t = tally[column];
    const read = t.yes.length + t.no.length;
    const evidence =
      `${read} of ${sample.length} list(s) read: Indexed true on ${t.yes.length}, ` +
      `false on ${t.no.length}, unreadable on ${t.unread}` +
      (t.yes.length ? ` — true on: ${t.yes.slice(0, 5).join(', ')}` : '');
    // ACCEPTED / REFUSED are the wrong vocabulary for a property read, so
    // this reports what it saw: uniform either way is an answer, a mixture is
    // per-list configuration rather than platform behaviour, and no reads at
    // all is not an answer.
    const outcome =
      read === 0 ? 'NOT ESTABLISHED'
      : t.no.length === 0 ? 'INDEXED ON ALL'
      : t.yes.length === 0 ? 'INDEXED ON NONE'
      : 'MIXED — PER LIST';
    record(QUESTION_FOR_COLUMN[column], `${column}: platform index?`, outcome, evidence);
  }

  // ---- Question 2: does an index serve a null test past the threshold? ----
  const big = candidates
    .filter((l) => l.ItemCount > LIST_VIEW_THRESHOLD)
    .sort((a, b) => b.ItemCount - a.ItemCount)[0];
  if (!big) {
    const largest = Math.max(...candidates.map((l) => l.ItemCount));
    const why =
      `no visible generic list on this web exceeds ${LIST_VIEW_THRESHOLD} items ` +
      `(largest is ${largest}). Both threshold questions need a list already ` +
      `past it; this probe will not create one.`;
    record('CMPIDX', 'Comparison filter on an indexed column survives the threshold',
           'NOT ESTABLISHED', why);
    record('NULLIDX', 'Null filter on an indexed column survives the threshold',
           'NOT ESTABLISHED', why);
    report();
    return;
  }
  log('INFO', `Threshold questions will use '${big.Title}' (${big.ItemCount} items).`);

  const fields = await spGet(
    `web/lists/getbytitle('${odata(big.Title)}')/fields` +
    `?$select=InternalName,Indexed,TypeAsString,Hidden&$top=5000`);
  if (readFailed(fields)) {
    const why = `could not read fields of '${big.Title}': HTTP ${fields.status}`;
    record('CMPIDX', 'Comparison filter on an indexed column survives the threshold',
           'NOT ESTABLISHED', why);
    record('NULLIDX', 'Null filter on an indexed column survives the threshold',
           'NOT ESTABLISHED', why);
    report();
    return;
  }
  // Lookup and User are excluded because Microsoft already documents that
  // indexing them does not avert the threshold — including one here would
  // make a failure ambiguous between "null tests cannot use an index" and
  // "this was a lookup field all along", which is the whole finding.
  const usable = (fields.body.value || []).find(
    (f) => f.Indexed === true
      && f.Hidden === false
      && !['Lookup', 'User', 'LookupMulti', 'UserMulti', 'TaxonomyFieldType']
        .includes(f.TypeAsString)
      && f.InternalName !== 'ID',
  );
  if (!usable) {
    const why =
      `'${big.Title}' has no indexed, visible, non-lookup column to test with. ` +
      `Add an index to a Text, Number, Choice or Date column on it and re-run.`;
    record('CMPIDX', 'Comparison filter on an indexed column survives the threshold',
           'NOT ESTABLISHED', why);
    record('NULLIDX', 'Null filter on an indexed column survives the threshold',
           'NOT ESTABLISHED', why);
    report();
    return;
  }
  const col = usable.InternalName;
  log('INFO', `Filtering on indexed ${usable.TypeAsString} column '${col}'.`);

  const items = `web/lists/getbytitle('${odata(big.Title)}')/items`;
  // $top=1 and $select=Id: this reads AT MOST one item id per query and never
  // item content. The question is whether SharePoint answers at all.
  const ask = async (id, question, filter) => {
    const r = await spGet(`${items}?$select=Id&$top=1&$filter=${encodeURIComponent(filter)}`);
    const body = r.body ? JSON.stringify(r.body).slice(0, 400) : '(no JSON body)';
    record(
      id, question,
      r.ok ? 'SERVED' : (isRefusal(r.status) ? 'REFUSED' : 'NOT ESTABLISHED'),
      `$filter=${filter} on ${big.ItemCount} items — HTTP ${r.status}: ${body}`,
    );
    return r.ok;
  };

  // The comparison filter FIRST, as the positive control. If the documented
  // case is itself refused on this list, the null result below says nothing
  // about null tests — it says this list cannot be queried by filter at all.
  const compared = await ask(
    'CMPIDX', 'Comparison filter on an indexed column survives the threshold',
    `${col} ne null`);
  if (!compared) {
    log('WARN', 'The documented comparison case was refused, so the null result');
    log('WARN', 'below is NOT evidence about null tests. Report both rows together.');
  }
  await ask(
    'NULLIDX', 'Null filter on an indexed column survives the threshold',
    `${col} eq null`);

  report();
  log('INFO', 'Read-only run complete. Nothing on this site was changed.');
})();
