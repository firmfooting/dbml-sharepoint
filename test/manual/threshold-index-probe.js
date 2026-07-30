/**
 * dbml-sharepoint PROBE — LIST VIEW THRESHOLD FIXTURE
 *
 * TWO QUESTIONS, both recorded as unknown in analysis/checks/_views.py:
 *
 *   1. Can a null test be served past the list view threshold when the column
 *      IS indexed? Microsoft's threshold guidance is written for comparison
 *      filters and says nothing about presence tests. Four views in the
 *      shipped template library filter on nothing but is_null — the library's
 *      "blank means still open" idiom — so the answer decides whether they can
 *      be fixed at all or only accepted.
 *
 *   2. Do Created, Modified, Author and Editor behave as indexed? The check
 *      excludes all five system columns, and that exclusion rests on the DBML
 *      side, so it is correct either way — but the project cannot currently
 *      say what SharePoint does.
 *
 * A third rides along, because the same fixture answers it: does indexing a
 * PERSON column avert a breach? Microsoft says no, and _LOOKUP_FIELD_TYPES
 * already acts on that, but on documentation alone.
 *
 * WHY A NEW FIXTURE: native-index-probe.js ran on 2026-07-30 and established
 * none of it. Its metadata half is void — SP.Field.Indexed read false for ID
 * itself — and its behavioural half never ran, because the site's largest
 * generic list held 21 items against a threshold of 5,000. The blocker was the
 * fixture, not the method. This builds the fixture.
 *
 * THIS PROBE WRITES. It creates two lists, six columns, four indexes and four
 * views, and the operator then loads 6,000 rows into it. Both write gates must
 * be turned on deliberately. Nothing happens to a pasted, unedited copy.
 *
 * MATCHED SELECTIVITY IS THE DESIGN. Every filter below matches exactly 60 of
 * 6,000 rows, on disjoint row sets, so each differs from the positive control
 * in exactly ONE respect — the index, the operator, or the field type. See the
 * docstring of test/manual/make_threshold_rows.py for what an earlier,
 * unmatched draft would have concluded and why it was wrong.
 *
 * WHAT IT ASKS
 *   RUNCNT  live ItemCount matches a declared checkpoint
 *   CMPIDX  comparison, INDEXED Text          (positive control)
 *   CMPUNI  comparison, UNINDEXED twin        (negative control)
 *   NULIDX  null test, INDEXED DateTime       (the question)
 *   PERSID  comparison, INDEXED Person
 *   LOOKID  comparison, INDEXED Lookup
 *   SYSCRE  comparison on Created             SYSMOD  on Modified
 *   SYSAUT  comparison on Author              SYSEDI  on Editor
 *   AUTOBT  SortBait's Indexed/AutoIndexed flags, across a modern sort
 *
 * HOW TO RUN — the run plan, in order
 *   1. Open a SharePoint site you are willing to put a 6,000-row list on.
 *   2. Set CONFIRMED and ALLOW_WRITES to true. Paste. This provisions
 *      everything and prints the two ids the row generator needs.
 *   3. Locally:  .venv/Scripts/python.exe test/manual/make_threshold_rows.py \
 *                    --owner-id <printed> --parent-id <printed>
 *   4. Load threshold-rows-01-to-1000.csv. Re-paste. Snapshot at 1,000.
 *   5. Load 02. Re-paste with RUN_LABEL='before sort'. Then OPEN the
 *      'Sort bait' view in the browser. Then re-paste with
 *      RUN_LABEL='after sort'. That pair is the only thing that can establish
 *      what AutoIndexed means.
 *   6. Load 03, 04, 05, re-pasting after each. Copy every RESULTS block.
 *
 * Re-pasting is safe at any point: provisioning is idempotent and later runs
 * only measure.
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

  // Set before re-pasting. The probe CANNOT tell one run from another — a
  // fresh JavaScript context has no memory and nowhere to keep one — so the
  // before/after-sort pair, both taken at 3,000 rows, is distinguished by this
  // label and nothing else. Interpreting the pair is the operator's job.
  const RUN_LABEL = '';

  // Ships off so a pasted copy never removes anything. See the cleanup block.
  const CLEANUP_AT_END = false;

  const LIST = 'dbmlsp Probe Threshold';
  const PARENT = 'dbmlsp Probe Threshold Parent';
  const CHECKPOINTS = [1000, 3000, 4900, 5100, 6000];
  const LIST_VIEW_THRESHOLD = 5000;
  const RARE_BUCKET = 'Z';
  // Every filtered population is one row in a hundred. Kept beside the
  // generator's MATCHING_ROWS; test_probes.py pins the two together.
  const MATCHING_ROWS = 60;

  const odata = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));

  // Indexed on purpose, and NOT indexed on purpose. Shadow mirrors Bucket's
  // data exactly, so that pair differs only in this column of the table.
  const COLUMNS = [
    ['Bucket',   true,  '<Field Type="Text" DisplayName="Bucket" Name="Bucket" MaxLength="255"/>'],
    ['Shadow',   false, '<Field Type="Text" DisplayName="Shadow" Name="Shadow" MaxLength="255"/>'],
    ['SortBait', false, '<Field Type="Text" DisplayName="SortBait" Name="SortBait" MaxLength="255"/>'],
    ['ClosedAt', true,  '<Field Type="DateTime" DisplayName="ClosedAt" Name="ClosedAt" Format="DateTime"/>'],
    ['Owner',    true,  '<Field Type="User" DisplayName="Owner" Name="Owner" UserSelectionMode="PeopleOnly"/>'],
  ];

  if (!CONFIRMED) {
    log('INFO', `Would create lists '${PARENT}' and '${LIST}', add 6 columns,`);
    log('INFO', 'set Indexed=true on Bucket, ClosedAt, Owner and Parent, create 4');
    log('INFO', 'views, then print the ids needed by make_threshold_rows.py.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false. Stopping without writes.');
    return;
  }

  // ---- Provision: PARENT FIRST ---------------------------------------
  // The child's Lookup field needs the parent list's id in its schema XML.
  // Cleanup reverses this; see the CLEANUP_AT_END block.
  const listShape = '?$select=Id,ItemCount,ListItemEntityTypeFullName';
  const ensureList = async (title, bootId) => {
    const existing = await spGet(`web/lists/getbytitle('${odata(title)}')${listShape}`);
    if (existing.ok) return existing.body;
    let digest = await getDigest();
    const created = await spPost('web/lists', {
      Title: title,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint list view threshold probe. Safe to recycle.',
    }, digest);
    if (!created.ok) {
      record(bootId, `Create ${title}`, 'FAIL',
             `HTTP ${created.status}: ${created.text.slice(0, 400)}`);
      return null;
    }
    // Re-read: the create response shape varies with OData mode and can be
    // empty, and the child's Lookup schema needs a MEASURED id.
    digest = await getDigest();
    const reread = await spGet(`web/lists/getbytitle('${odata(title)}')${listShape}`);
    if (readFailed(reread) || !reread.body.Id) {
      record(bootId, `Read back ${title}`, 'FAIL',
             `HTTP ${reread.status}: no usable list Id`);
      return null;
    }
    return reread.body;
  };

  // Separate boot ids, not one shared 'BOOT': record() overwrites by id, so a
  // single id would let whichever list failed second erase the first, and the
  // surviving row would name the wrong list.
  const parent = await ensureList(PARENT, 'BOOTPARENT');
  const main = await ensureList(LIST, 'BOOTMAIN');
  if (!parent || !main) {
    report();
    return;
  }

  // ---- Columns and indexes -------------------------------------------
  const fieldsPath = `web/lists/getbytitle('${odata(LIST)}')/fields`;
  const fieldExists = async (name) =>
    (await spGet(`${fieldsPath}/getbyinternalnameortitle('${name}')?$select=Id`)).ok;

  const addField = async (schemaXml) => {
    const digest = await getDigest();
    return spPost(`${fieldsPath}/createfieldasxml`,
                  { parameters: { SchemaXml: schemaXml, Options: 8 } }, digest);
  };

  // Indexed is read/write and documented as "TRUE if the column is indexed for
  // use in view filters". Set on the EMPTY list: Microsoft's troubleshooting
  // guidance puts a 20,000-item ceiling on adding or removing an indexed
  // column, and provisioning first removes the question entirely.
  const setIndexed = async (name) => {
    const digest = await getDigest();
    return spPost(`${fieldsPath}/getbyinternalnameortitle('${name}')`,
                  { Indexed: true }, digest,
                  { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  };

  const schemas = COLUMNS.concat([[
    'Parent', true,
    `<Field Type="Lookup" DisplayName="Parent" Name="Parent" ` +
    `List="{${parent.Id}}" ShowField="Title"/>`,
  ]]);

  for (const [name, indexed, schemaXml] of schemas) {
    if (!(await fieldExists(name))) {
      const made = await addField(schemaXml);
      if (!made.ok) {
        log('FAIL', `Could not create ${name}: HTTP ${made.status} ${made.text.slice(0, 300)}`);
        continue;
      }
    }
    if (!indexed) continue;
    const flagged = await setIndexed(name);
    log(flagged.ok ? 'OK' : 'FAIL',
        `${name}: Indexed=true ${flagged.ok ? 'set' : `FAILED HTTP ${flagged.status}`}`);
  }

  // One parent row for every child row to point at.
  if (parent.ItemCount === 0) {
    const digest = await getDigest();
    const seeded = await spPost(
      `web/lists/getbytitle('${odata(PARENT)}')/items`, { Title: 'Probe parent' }, digest);
    log(seeded.ok ? 'OK' : 'FAIL',
        `parent item ${seeded.ok ? 'created' : `FAILED HTTP ${seeded.status}`}`);
  }

  // ---- Views ----------------------------------------------------------
  // CAML, because a view filter is not an OData filter. The probe measures
  // $filter for a crisp HTTP answer; these exist so the operator can OPEN them
  // and report what a human sees. The two are different code paths and can
  // disagree — a disagreement is itself the finding.
  const VIEWS = [
    ['Cmp indexed',
     `<Where><Eq><FieldRef Name='Bucket'/><Value Type='Text'>${RARE_BUCKET}</Value></Eq></Where>`],
    ['Null indexed',
     "<Where><IsNull><FieldRef Name='ClosedAt'/></IsNull></Where>"],
    ['Cmp unindexed',
     `<Where><Eq><FieldRef Name='Shadow'/><Value Type='Text'>${RARE_BUCKET}</Value></Eq></Where>`],
    ['Sort bait',
     "<OrderBy><FieldRef Name='SortBait'/></OrderBy>"],
  ];
  const viewsPath = `web/lists/getbytitle('${odata(LIST)}')/views`;
  for (const [title, query] of VIEWS) {
    if ((await spGet(`${viewsPath}/getbytitle('${odata(title)}')?$select=Id`)).ok) continue;
    const digest = await getDigest();
    const made = await spPost(viewsPath, {
      Title: title, ViewQuery: query, RowLimit: 30, ViewFields: { results: [] },
    }, digest);
    log(made.ok ? 'OK' : 'FAIL',
        `view '${title}' ${made.ok ? 'created'
          : `FAILED HTTP ${made.status} ${made.text.slice(0, 300)}`}`);
  }

  // ---- Handshake ------------------------------------------------------
  // The generator cannot know these, and the probe cannot know them before the
  // lists exist. Printing them is the handshake between the two halves.
  const me = await spGet('web/currentuser?$select=Id,LoginName');
  const myId = readFailed(me) ? 0 : me.body.Id;
  log('INFO', '=============== FEED THESE TO THE GENERATOR ===============');
  log('INFO', `  .venv/Scripts/python.exe test/manual/make_threshold_rows.py \\`);
  log('INFO', `      --owner-id ${myId || 'UNREADABLE'} --parent-id 1`);
  log('INFO', `  (--parent-id 1 is the first item of '${PARENT}')`);
  log('INFO', `  ListItemEntityTypeFullName: ${main.ListItemEntityTypeFullName}`);
  log('INFO', '  — some batch-create flows need that as the __metadata type.');
  log('INFO', '===========================================================');

  report();
})();
