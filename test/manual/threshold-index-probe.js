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
 * A third rides along: does indexing a PERSON column avert a breach? Microsoft
 * says no — the index article lists "Person or Group (single value) (Lookup)"
 * and the Field element's `Indexed` note says an indexed Lookup column does not
 * prevent exceeding the threshold — and _LOOKUP_FIELD_TYPES already acts on
 * that, but on documentation alone.
 *
 * WHY A NEW FIXTURE: native-index-probe.js ran on 2026-07-30 and established
 * none of it. Its metadata half is void — SP.Field.Indexed read false for ID
 * itself — and its behavioural half never ran, because the site's largest
 * generic list held 21 items against a threshold of 5,000. The blocker was the
 * fixture, not the method.
 *
 * THIS PROBE WRITES. Two lists, six columns, four indexes, four views, and the
 * operator then loads 6,000 rows into it. Both write gates must be turned on
 * deliberately; a pasted, unedited copy prints its plan and stops.
 *
 * MATCHED SELECTIVITY IS THE DESIGN. Five filters match exactly one row in a
 * hundred, on disjoint row sets, so each differs from the positive control in
 * exactly ONE respect — the index, the operator, or the field type. The four
 * system-column filters are NOT matched and cannot be compared with them; each
 * says so in its own evidence, because a comment nobody copies out of the
 * console is not a safeguard.
 *
 * WHAT IT ASKS
 *   RUNCNT  live ItemCount matches a declared checkpoint
 *   IDXSET  the four intended indexes really are set, the two others are not
 *   FLAGS   Indexed/AutoIndexed for all six columns, every run
 *   CMPIDX  OData comparison, INDEXED Text        (positive control)
 *   CMPUNI  OData comparison, UNINDEXED twin      (negative control)
 *   NULIDX  OData null test, INDEXED DateTime
 *   CMPCAM  CAML  comparison, INDEXED Text
 *   NULCAM  CAML  <IsNull>, INDEXED DateTime      (the question as _views.py asks it)
 *   PERSID  OData comparison, INDEXED Person
 *   LOOKID  OData comparison, INDEXED Lookup
 *   SYSCRE  Created     SYSMOD  Modified     SYSAUT  Author     SYSEDI  Editor
 *
 * BOTH OData AND CAML, deliberately. analysis/checks/_views.py asks about a
 * CAML <IsNull>, because that is what a SharePoint VIEW renders. OData $filter
 * is a different code path, and `eq null` is not in Microsoft's documented
 * operator list for the REST service at all. Measuring only OData would leave
 * the recorded unknown untouched while the summary read "all answered".
 *
 * HOW TO RUN — the run plan, in order
 *   1. Open a SharePoint site you are willing to put a 6,000-row list on.
 *   2. Set CONFIRMED and ALLOW_WRITES true. Paste. This provisions everything
 *      and prints the two ids the row generator needs.
 *   3. Locally:  .venv/Scripts/python.exe test/manual/make_threshold_rows.py \
 *                    --owner-id <printed> --parent-id <printed>
 *   4. Set OWNER_ID below to the same value you passed --owner-id.
 *   5. Load threshold-rows-01-to-1000.csv. Re-paste. Snapshot at 1,000.
 *   6. Load 02. Re-paste with RUN_LABEL='before sort'. Then OPEN the
 *      'Sort bait' view in the browser. Then re-paste with
 *      RUN_LABEL='after sort'. That pair is the only thing that can establish
 *      what AutoIndexed means.
 *   7. Load 03, 04, 05, re-pasting after each. Copy every RESULTS block.
 *
 * Re-pasting is safe at any point: provisioning is idempotent and later runs
 * only measure.
 *
 * NOTE: the harness's CLEANUP flag does NOTHING here. This probe never calls
 * resetList(), on purpose — you do not want a 6,000-row fixture silently
 * emptied because a flag was left on. Teardown is CLEANUP_AT_END, at the
 * bottom, and it is a separate deliberate act.
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

  // The id you passed the generator as --owner-id. NOT read from the current
  // user: a later checkpoint pasted from a different account would silently
  // retarget the Person filter at an id no row carries, match nothing, and
  // record SERVED — "a Person index does avert the threshold", contradicting
  // Microsoft on the strength of an empty column.
  const OWNER_ID = 0;

  // Ships off so a pasted copy never removes anything.
  const CLEANUP_AT_END = false;

  const LIST = 'dbmlsp Probe Threshold';
  const PARENT = 'dbmlsp Probe Threshold Parent';
  const CHECKPOINTS = [1000, 3000, 4900, 5100, 6000];
  const LIST_VIEW_THRESHOLD = 5000;
  const RARE_BUCKET = 'Z';
  // The generator's TOTAL and MATCHING_ROWS, and the ratio derived from them
  // rather than written out separately — so a constant that drifts from the
  // generator changes the arithmetic instead of sitting in a comment being
  // wrong. test_probes.py pins both against make_threshold_rows.py.
  const FIXTURE_TOTAL = 6000;
  const MATCHING_ROWS = 60;
  const PER_HUNDRED = FIXTURE_TOTAL / MATCHING_ROWS;
  // Enough headroom to COUNT the matches rather than just prove one exists.
  const PAGE = 200;

  expect('RUNCNT', 'Live ItemCount matches a declared checkpoint');
  expect('IDXSET', 'The intended indexes are set and the controls are not');
  expect('FLAGS', 'Indexed/AutoIndexed for all six columns');
  expect('CMPIDX', 'OData comparison, INDEXED Text (positive control)');
  expect('CMPUNI', 'OData comparison, UNINDEXED twin of Bucket (negative control)');
  expect('NULIDX', 'OData null test, INDEXED DateTime');
  expect('CMPCAM', 'CAML comparison, INDEXED Text');
  expect('NULCAM', 'CAML IsNull, INDEXED DateTime (the question as _views.py asks it)');
  expect('PERSID', 'OData comparison, INDEXED Person');
  expect('LOOKID', 'OData comparison, INDEXED Lookup');
  expect('SYSCRE', 'OData comparison on Created');
  expect('SYSMOD', 'OData comparison on Modified');
  expect('SYSAUT', 'OData comparison on Author');
  expect('SYSEDI', 'OData comparison on Editor');

  const odata = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));

  // [name, should be indexed, schema XML]. Shadow mirrors Bucket's data
  // exactly and is deliberately NOT indexed, so that pair differs only in the
  // index. SortBait is the column a modern-view sort is aimed at.
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
    const digest = await getDigest();
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
  const readField = async (name) =>
    // No $select: an unrecognised property in $select errors the WHOLE
    // request, so asking for AutoIndexed on a tenant that does not expose it
    // would report every column unreadable and read as a permissions problem.
    spGet(`${fieldsPath}/getbyinternalnameortitle('${name}')`);

  const addField = async (schemaXml) => {
    const digest = await getDigest();
    return spPost(`${fieldsPath}/createfieldasxml`,
                  { parameters: { SchemaXml: schemaXml, Options: 8 } }, digest);
  };

  // Indexed is read/write and documented as "TRUE if the column is indexed for
  // use in view filters". Set on the EMPTY list: Microsoft's troubleshooting
  // guidance puts a 20,000-item ceiling on adding or removing an indexed
  // column, and provisioning first removes the question entirely.
  //
  // __metadata carries SP.Field because that is the shape this repo's deployer
  // uses and has verified live (templates/deploy/_indexes.js.j2).
  const setIndexed = async (name) => {
    const digest = await getDigest();
    return spPost(`${fieldsPath}/getbyinternalnameortitle('${name}')`,
                  { __metadata: { type: 'SP.Field' }, Indexed: true }, digest,
                  { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  };

  const schemas = COLUMNS.concat([[
    'Parent', true,
    `<Field Type="Lookup" DisplayName="Parent" Name="Parent" ` +
    `List="{${parent.Id}}" ShowField="Title"/>`,
  ]]);

  for (const [name, indexed, schemaXml] of schemas) {
    if (readFailed(await readField(name))) {
      const made = await addField(schemaXml);
      if (!made.ok) {
        log('FAIL', `Could not create ${name}: HTTP ${made.status} ${made.text.slice(0, 300)}`);
        continue;
      }
    }
    if (!indexed) continue;
    const flagged = await setIndexed(name);
    log(flagged.ok ? 'OK' : 'FAIL',
        `${name}: Indexed=true ${flagged.ok ? 'requested' : `FAILED HTTP ${flagged.status}`}`);
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
  // CAML, because a view filter is not an OData filter. These exist so the
  // operator can OPEN them and report what a human sees; NULCAM below measures
  // the same CAML programmatically. Three sources for one question, because
  // they are three code paths.
  //
  // Paged: true — the RowLimit element's documentation is explicit that an
  // unspecified Paged makes the limit ABSOLUTE with no "show more" link, which
  // is not the shape the template library ships. ViewFields is NOT passed in
  // the create body: the harness sends odata=nometadata, where the verbose
  // {results: []} collection shape is a type mismatch, and this repo's
  // deployer adds fields one at a time afterwards for the same reason.
  const VIEW_FIELDS = ['Title', 'Bucket', 'Shadow', 'ClosedAt'];
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
    let digest = await getDigest();
    const made = await spPost(viewsPath, {
      Title: title, ViewQuery: query, RowLimit: 30, Paged: true, PersonalView: false,
    }, digest);
    if (!made.ok) {
      log('FAIL', `view '${title}' FAILED HTTP ${made.status} ${made.text.slice(0, 300)}`);
      continue;
    }
    for (const field of VIEW_FIELDS) {
      digest = await getDigest();
      await spPost(
        `${viewsPath}/getbytitle('${odata(title)}')/viewfields/addviewfield('${field}')`,
        {}, digest);
    }
    log('OK', `view '${title}' created with ${VIEW_FIELDS.length} field(s)`);
  }

  // ---- Handshake ------------------------------------------------------
  const me = await spGet('web/currentuser?$select=Id,LoginName');
  const whoami = readFailed(me)
    ? '(currentuser unreadable)'
    : `${me.body.Id} / ${me.body.LoginName}`;
  log('INFO', '=============== FEED THESE TO THE GENERATOR ===============');
  log('INFO', `  .venv/Scripts/python.exe test/manual/make_threshold_rows.py \\`);
  log('INFO', `      --owner-id ${readFailed(me) ? 'UNREADABLE' : me.body.Id} --parent-id 1`);
  log('INFO', `  (--parent-id 1 is the first item of '${PARENT}')`);
  log('INFO', `  Then set OWNER_ID in this probe to the same value.`);
  log('INFO', `  ListItemEntityTypeFullName: ${main.ListItemEntityTypeFullName}`);
  log('INFO', '  — some batch-create flows need that as the __metadata type.');
  log('INFO', '===========================================================');

  // ---- Snapshot -------------------------------------------------------
  const live = await spGet(`web/lists/getbytitle('${odata(LIST)}')?$select=ItemCount`);
  const count = readFailed(live) ? -1 : live.body.ItemCount;
  const stamp = `${count} item(s)${RUN_LABEL ? `, run '${RUN_LABEL}'` : ''}`;
  log('INFO', `=== SNAPSHOT at ${stamp}, as ${whoami} ===`);
  if (!RUN_LABEL) {
    log('INFO', 'RUN_LABEL is unset. Step 6 of the run plan needs it: the');
    log('INFO', 'before/after-sort pair is taken at the SAME row count, and');
    log('INFO', 'nothing else distinguishes the two transcripts.');
  }

  // SharePoint's batch API is explicitly non-transactional — "if any of the
  // child operations fails, the others still complete and aren't rolled back"
  // — so a half-loaded batch is SILENT, and every observation below would be
  // filed under a row count the list never actually reached.
  //
  // 0 gets its own outcome: the provisioning run legitimately has an empty
  // list, and crying "a batch load may have partly failed" at every operator's
  // first paste is how a real warning stops being read.
  const onCheckpoint = CHECKPOINTS.includes(count);
  record(
    'RUNCNT', 'Live ItemCount matches a declared checkpoint',
    count < 0 ? 'NOT ESTABLISHED'
      : count === 0 ? 'NOT LOADED YET'
      : onCheckpoint ? 'ON CHECKPOINT' : 'OFF CHECKPOINT',
    `ItemCount=${count}; checkpoints are ${CHECKPOINTS.join(', ')}` + (
      (onCheckpoint || count <= 0) ? '' :
      '. A batch load may have partly failed, or a file was loaded twice. ' +
      'EVERY ROW BELOW IS SUSPECT — reconcile the list first.'
    ),
  );

  // ---- Are the controls actually controls? ----------------------------
  // The whole experiment is an indexed-versus-unindexed comparison, so a MERGE
  // that returned 200 without taking effect would mislabel every row in the
  // table. Read the flags back rather than trusting the status code — the
  // deployer's own index step is documented as "verified by readback" for
  // exactly this reason.
  const flags = [];
  const wrong = [];
  for (const [name, shouldBeIndexed] of schemas) {
    const field = await readField(name);
    if (readFailed(field) || typeof field.body.Indexed !== 'boolean') {
      flags.push(`${name}=unreadable`);
      wrong.push(`${name} (could not read)`);
      continue;
    }
    const auto = typeof field.body.AutoIndexed === 'boolean'
      ? field.body.AutoIndexed : '(not exposed)';
    flags.push(`${name}: Indexed=${field.body.Indexed}, AutoIndexed=${auto}`);
    if (field.body.Indexed !== shouldBeIndexed) {
      wrong.push(`${name} (wanted ${shouldBeIndexed}, is ${field.body.Indexed})`);
    }
  }
  record(
    'IDXSET', 'The intended indexes are set and the controls are not',
    wrong.length ? 'MISLABELLED — TABLE VOID' : 'CONFIRMED',
    wrong.length
      ? `[${stamp}] ${wrong.join('; ')}. Every indexed/unindexed row below is ` +
        'about a column whose index state is not what it claims.'
      : `[${stamp}] Bucket, ClosedAt, Owner, Parent indexed; Shadow, SortBait not.`,
  );
  record(
    'FLAGS', 'Indexed/AutoIndexed for all six columns',
    flags.length ? 'OBSERVED' : 'NOT ESTABLISHED',
    `[${stamp}] ${flags.join(' | ')}. AutoIndexed means nothing on its own: ` +
    'only a CHANGE across the before/after-sort pair establishes what sets it. ' +
    'Shadow is here because if it silently gains an index the negative control ' +
    'has expired and any CMPUNI result below is uninterpretable.',
  );

  // ---- Filters --------------------------------------------------------
  const items = `web/lists/getbytitle('${odata(LIST)}')/items`;

  // Classify from the error body, so a row is self-describing in a single
  // transcript. A malformed $filter and a threshold refusal both come back as
  // a 4xx/5xx that isRefusal() reads as REFUSED, and conclusions get drawn
  // from the LAST transcript — where a filter that was broken at every
  // checkpoint would read as a threshold refusal.
  const classify = (r) => {
    const body = r.body ? JSON.stringify(r.body) : '';
    if (/exceeds the list view threshold|SPQueryThrottledException/i.test(body)) {
      return 'REFUSED (threshold)';
    }
    if (r.status === 429 || r.status === 408) return 'NOT ESTABLISHED (throttled)';
    if (isRefusal(r.status)) return 'REFUSED (request rejected — check the body)';
    return 'NOT ESTABLISHED';
  };

  // expectedRows null means "this filter is not selectivity-matched"; the row
  // then reports what it matched without claiming comparability.
  const judge = (r, expectedRows) => {
    if (!r.ok) return classify(r);
    const matched = (r.body && r.body.value) ? r.body.value.length : -1;
    if (expectedRows === null) return `SERVED (${matched} row(s))`;
    // A filter that matches NOTHING returns 200 and would otherwise read as a
    // clean SERVED — which is how an empty column, or a Flow that dropped a
    // field, becomes "an index on this type does avert the threshold".
    if (matched !== expectedRows) {
      return `NOT ESTABLISHED (matched ${matched}, expected ${expectedRows})`;
    }
    return `SERVED (${matched} row(s), as expected)`;
  };

  const ask = async (id, question, filter, expectedRows) => {
    const r = await spGet(
      `${items}?$select=Id&$top=${PAGE}&$filter=${encodeURIComponent(filter)}`);
    const body = r.body ? JSON.stringify(r.body).slice(0, 300) : '(no JSON body)';
    // A failure at the FIRST checkpoint means the filter is wrong, not that
    // SharePoint refused it. Bounded to checkpoint 1 only: the spec chose
    // 4,900 precisely because the effective threshold is documented as
    // variable, so annotating a refusal there as "broken" would libel a real
    // finding.
    const suspect = count > 0 && count <= CHECKPOINTS[0] && !r.ok;
    record(
      id, question, judge(r, expectedRows),
      `[${stamp}] $filter=${filter} — HTTP ${r.status}: ${body}` + (
        suspect
          ? '  <-- FAILED AT THE FIRST CHECKPOINT, so this is a broken filter, not evidence.'
          : ''
      ),
    );
  };

  // CAML, via the same method the modern UI uses to render a view. This is the
  // path analysis/checks/_views.py actually asks about.
  const askCaml = async (id, question, where, expectedRows) => {
    const digest = await getDigest();
    const viewXml =
      `<View><Query>${where}</Query><RowLimit>${PAGE}</RowLimit></View>`;
    const r = await spPost(
      `web/lists/getbytitle('${odata(LIST)}')/RenderListDataAsStream`,
      { parameters: { ViewXml: viewXml } }, digest);
    const rows = (r.ok && r.body && Array.isArray(r.body.Row)) ? r.body.Row.length : -1;
    let outcome;
    if (!r.ok) {
      outcome = classify(r);
    } else if (rows < 0) {
      outcome = 'NOT ESTABLISHED (no Row array in the response)';
    } else if (expectedRows !== null && rows !== expectedRows) {
      outcome = `NOT ESTABLISHED (matched ${rows}, expected ${expectedRows})`;
    } else {
      outcome = `SERVED (${rows} row(s), as expected)`;
    }
    record(id, question, outcome,
           `[${stamp}] CAML ${where} — HTTP ${r.status}: ${(r.text || '').slice(0, 300)}`);
  };

  // One row in a hundred, so this is the expected match count at any
  // checkpoint — every offset is below 100 and every checkpoint is a multiple
  // of 100, so it is exact at all five, not only at 6,000.
  const matched = count > 0 ? Math.floor(count / PER_HUNDRED) : null;

  await ask('CMPIDX', 'OData comparison, INDEXED Text (positive control)',
            `Bucket eq '${RARE_BUCKET}'`, matched);
  await ask('CMPUNI', 'OData comparison, UNINDEXED twin of Bucket (negative control)',
            `Shadow eq '${RARE_BUCKET}'`, matched);
  // `eq null` is NOT in Microsoft's documented operator list for the SharePoint
  // REST service, and the only Microsoft-hosted statement found says OData
  // there does not support filtering on null, with CAML as the workaround. So
  // this row may well be a 400 at every checkpoint — which is why NULCAM
  // exists, and why the first checkpoint annotates a broken filter as broken.
  await ask('NULIDX', 'OData null test, INDEXED DateTime',
            'ClosedAt eq null', matched);
  // Not asked at all when OWNER_ID is unset. `OwnerId eq 0` matches nothing,
  // returns 200, and would be a SERVED — the exact false positive the constant
  // exists to prevent, so the query does not get to run.
  if (OWNER_ID) {
    await ask('PERSID', 'OData comparison, INDEXED Person',
              `OwnerId eq ${OWNER_ID}`, matched);
  } else {
    record('PERSID', 'OData comparison, INDEXED Person', 'NOT ESTABLISHED',
           'OWNER_ID is 0, so no filter was sent. Asking for `OwnerId eq 0` ' +
           'would match nothing, return HTTP 200 and read as SERVED. Set ' +
           'OWNER_ID to the value passed to --owner-id and re-paste.');
  }
  await ask('LOOKID', 'OData comparison, INDEXED Lookup', 'ParentId eq 1', matched);

  await askCaml(
    'CMPCAM', 'CAML comparison, INDEXED Text',
    `<Where><Eq><FieldRef Name='Bucket'/><Value Type='Text'>${RARE_BUCKET}</Value></Eq></Where>`,
    matched);
  await askCaml(
    'NULCAM', 'CAML IsNull, INDEXED DateTime (the question as _views.py asks it)',
    "<Where><IsNull><FieldRef Name='ClosedAt'/></IsNull></Where>", matched);

  // NOT selectivity-matched, and unfixably so: the loader owns every row, so
  // Author and Editor are the same principal throughout and Created/Modified
  // span one load. Each therefore matches the WHOLE list, which breaches on
  // result-set size alone. Recorded with expectedRows=null and the caveat in
  // the evidence, because a REFUSED here says nothing about indexing while a
  // SERVED would be genuinely surprising.
  const SYS_CAVEAT =
    ' NOTE: this filter matches every row in the list, so a threshold refusal ' +
    'is attributable to result-set size and is NOT evidence about indexing. ' +
    'Only a SERVED is informative here.';
  for (const [id, question, filter] of [
    ['SYSCRE', 'OData comparison on Created', "Created ge datetime'2020-01-01T00:00:00Z'"],
    ['SYSMOD', 'OData comparison on Modified', "Modified ge datetime'2020-01-01T00:00:00Z'"],
    ['SYSAUT', 'OData comparison on Author', `AuthorId ne 0`],
    ['SYSEDI', 'OData comparison on Editor', `EditorId ne 0`],
  ]) {
    const r = await spGet(
      `${items}?$select=Id&$top=${PAGE}&$filter=${encodeURIComponent(filter)}`);
    record(id, question, judge(r, null),
           `[${stamp}] $filter=${filter} — HTTP ${r.status}: ` +
           `${r.body ? JSON.stringify(r.body).slice(0, 200) : '(no JSON body)'}${SYS_CAVEAT}`);
  }

  report();
  if (count > 0 && !onCheckpoint) {
    log('FAIL', '*** ItemCount is not on a checkpoint. The table above is not');
    log('FAIL', '*** evidence until the list is reconciled. See RUNCNT.');
  }

  // ---- Cleanup --------------------------------------------------------
  if (!CLEANUP_AT_END) {
    log('INFO', `Fixture lists remain: '${LIST}' and '${PARENT}'.`);
    log('INFO', 'When finished, set CLEANUP_AT_END=true with both write gates');
    log('INFO', 'and re-paste. Expect more than one pass past 5,000 rows.');
    return;
  }

  // Past 5,000 items a list will not empty in one page, and a cleanup that
  // silently leaves rows behind lets THIS run's rows answer the NEXT run's
  // questions. So: page until empty or until a page stops making progress,
  // then say exactly what is left rather than reporting success.
  const emptyList = async (title) => {
    let removed = 0;
    let throttled = 0;
    for (let page = 0; page < 20; page += 1) {
      const found = await spGet(
        `web/lists/getbytitle('${odata(title)}')/items?$select=Id&$top=1000`);
      const rows = (found.ok && found.body && found.body.value) || [];
      if (!rows.length) break;
      // One digest per PAGE, not per item. A form digest lives about thirty
      // minutes, so refreshing it 6,000 times doubled the request count for
      // nothing — and request count is the binding constraint here.
      const digest = await getDigest();
      let removedThisPage = 0;
      for (const row of rows) {
        const gone = await spPost(
          `web/lists/getbytitle('${odata(title)}')/items(${row.Id})/recycle`, {}, digest);
        if (gone.ok) removedThisPage += 1;
        else if (gone.status === 429) throttled += 1;
      }
      removed += removedThisPage;
      // A page that removed nothing will not do better on the next attempt,
      // and looping twenty times over it would bury the reason.
      if (removedThisPage === 0) {
        log('FAIL',
            `CLEANUP '${title}': a page of ${rows.length} row(s) would not recycle ` +
            `(${throttled} were HTTP 429). Throttling is the likeliest cause at ` +
            `this size; retention, a lock or permissions are the others. Stopping.`);
        break;
      }
    }
    const left = await spGet(`web/lists/getbytitle('${odata(title)}')?$select=ItemCount`);
    const remaining = (left.ok && left.body) ? left.body.ItemCount : -1;
    log(remaining === 0 ? 'OK' : 'FAIL',
        `CLEANUP '${title}': recycled ${removed} item(s), ${remaining} REMAINING` +
        (remaining === 0 ? '.' : ' — re-run with CLEANUP_AT_END until this reads 0.'));
    return remaining === 0;
  };

  // CHILD FIRST. SharePoint refuses to recycle a list that a live Lookup
  // column still targets, so the parent cannot go until the child has. This is
  // the reverse of provisioning order, and calculated-operand-probe.js already
  // learned it the hard way.
  for (const title of [LIST, PARENT]) {
    await emptyList(title);
    const digest = await getDigest();
    const recycled = await spPost(
      `web/lists/getbytitle('${odata(title)}')/recycle`, {}, digest);
    log(recycled.ok ? 'OK' : 'FAIL',
        recycled.ok
          ? `Recycled '${title}'. Restorable from the site recycle bin.`
          : `Could not recycle '${title}': HTTP ${recycled.status} ${recycled.text.slice(0, 300)}`);
  }
})();
