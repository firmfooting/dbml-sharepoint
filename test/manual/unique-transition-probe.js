/**
 * dbml-sharepoint PROBE: IS ENFORCEUNIQUEVALUES REFUSED ON EXISTING DUPLICATES
 *
 * REVISION: 76226145
 *
 * ONE QUESTION:
 *   A single-line text column already holds items, and two of them carry the
 *   same value. Does a MERGE setting EnforceUniqueValues true on that column
 *   get refused, and is the same MERGE accepted on a column whose items are
 *   all distinct?
 *
 * #550 made a declared `unique` column actually deploy its constraint, so a
 * list provisioned before that fix holds the column unconstrained and the
 * field phase now asks SharePoint to add the constraint to data that never
 * carried it. `templates/deploy/_preflight.js.j2` names those columns before
 * anything is written. It deliberately does not say what SharePoint will do,
 * because nothing has measured it: the Learn pages for
 * `Field.EnforceUniqueValues` and `FieldPropertyNames.EnforceUniqueValues`
 * are bare CSOM definitions with no remarks, and the support page that
 * documents unique columns describes what the constraint refuses once it is
 * on, never what adding it to existing rows does. SQL Server, which backs the
 * content database, does state the answer for itself ("If a UNIQUE constraint
 * is added to a column that has duplicate values, the Database Engine returns
 * an error and doesn't add the constraint"), so the plausible answer and the
 * measured answer are again the two different things the evidence rule is
 * about.
 *
 * The write shape is the deploy's. `_field_reconcile.js.j2` sends a MERGE
 * carrying `__metadata` and only the properties that drifted, and on a column
 * that is neither unique nor indexed both `EnforceUniqueValues` and `Indexed`
 * drift together, so that pair is what the duplicate and control cells send.
 *
 * SCOPE AND QUESTIONS
 *   field.unique.fixture-transition-list
 *     A generic list is created (BaseTemplate 100).
 *   field.unique.fixture-unconstrained-columns
 *     Three Text columns and one Note column are created WITHOUT
 *     EnforceUniqueValues and Indexed, and the three Text columns read both
 *     back false. Every row below is about the transition out of that state,
 *     so a column that starts constrained answers nothing.
 *   field.unique.fixture-duplicate-items
 *     Two items are created and read back: `DupRef` carries one value twice,
 *     `UniqRef` and `IdxRef` carry two distinct values each. The duplicate is
 *     the whole independent variable, so it is verified rather than assumed.
 *   field.unique.control-note-column-refused
 *     NEGATIVE CONTROL: the same MERGE on a Multiple lines of text column,
 *     which Microsoft documents as an unsupported column type for unique
 *     columns, is REFUSED. Without it, an accepted MERGE below could not be
 *     told from an endpoint that answers 200 to anything it is sent.
 *   field.unique.control-transition-on-unique-values
 *     POSITIVE CONTROL: the MERGE on `UniqRef`, whose two values differ, is
 *     ACCEPTED and reads back enforced. Without it, a refusal below could be
 *     the transition never working here rather than the duplicate values.
 *   field.unique.transition-on-duplicate-values
 *     The question: the same MERGE on `DupRef`, whose two items carry the
 *     same value.
 *   field.unique.transition-without-index
 *     The index requirement, which is its own failure mode: a MERGE carrying
 *     EnforceUniqueValues ALONE on `IdxRef`, whose values are distinct. The
 *     support page says a unique column must also have an index, and the
 *     deploy only ever sends the pair, so nothing here knows whether the
 *     single-property write is accepted or what `Indexed` then reads.
 *
 * OBSERVED, NEVER ASSERTED
 *   What each MERGE answers, and what `EnforceUniqueValues` and `Indexed`
 *   read back after it. Those are the measurement. The starting state is a
 *   dependency and IS asserted: a column that already carries the constraint
 *   fails the fixture row and voids the rest, because the transition cannot
 *   be measured from it.
 *
 * NOT MEASURED HERE
 *   A list larger than the List View Threshold, which the support page says
 *   is blocked for this write on its own; the other supported column types;
 *   whether removing the constraint afterwards is accepted; and what the
 *   column settings page shows while refusing. Those are separate questions
 *   and two of them need a capture.
 *
 * MICROSOFT CITATIONS
 *   EnforceUniqueValues and Indexed (CSOM), bare definitions with no remarks:
 *     "Field.EnforceUniqueValues Property", "Field.Indexed Property"
 *   A unique column must also have an index; Multiple lines of text is an
 *   unsupported column type for unique columns; making a column unique in an
 *   existing list past the List View Threshold is blocked:
 *     "Create list relationships by using lookup columns",
 *     https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/create-list-relationships-by-using-lookup-columns
 *   List creation via POST to `web/lists` and item creation via `items`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields`, and the MERGE that updates one:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   A UNIQUE constraint added over duplicate values is refused (SQL Server,
 *   the backing store, NOT a statement about SharePoint):
 *     "Unique constraints and check constraints" (SQL Server)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * A SECOND RUN NEEDS CLEANUP = true. The first run leaves the columns
 * carrying whatever its MERGEs achieved, and the transition cannot be asked
 * again of a column that already made it.
 *
 * WHEN FINISHED: delete the list it created.
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

  log('INFO', 'probe revision 76226145. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Unique Transition';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  // Internal name equals display name: created through the same POST to
  // /fields the deploy uses, so it carries no _x0020_ encoding.
  const DUP = 'DupRef';
  const UNIQ = 'UniqRef';
  const IDX = 'IdxRef';
  const NOTE = 'NoteRef';
  const SHARED = 'dbmlsp-shared-value';

  // What each item carries. Two items, because two is what it takes to hold
  // the same value twice, and every extra row is another thing to explain.
  const ITEMS = [
    { Title: 'dbmlsp transition 1', [DUP]: SHARED, [UNIQ]: 'dbmlsp-uniq-1', [IDX]: 'dbmlsp-idx-1' },
    { Title: 'dbmlsp transition 2', [DUP]: SHARED, [UNIQ]: 'dbmlsp-uniq-2', [IDX]: 'dbmlsp-idx-2' },
  ];

  const Q = {
    fixture: 'A generic list is created (BaseTemplate 100)',
    columns: 'Three Text columns and one Note column are created without EnforceUniqueValues and Indexed, and the Text columns read both back false',
    items: 'Two items read back with one value twice in DupRef and two distinct values in each of UniqRef and IdxRef',
    note: 'NEGATIVE CONTROL: is the same MERGE refused on a Multiple lines of text column, which Microsoft documents as unsupported for unique columns',
    control: 'POSITIVE CONTROL: is the MERGE accepted on a column whose existing values are all distinct',
    duplicate: 'Is the MERGE accepted on a column two of whose existing items carry the same value',
    index: 'Is a MERGE carrying EnforceUniqueValues alone accepted, and what does Indexed read back after it',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' on ${WEB} with three unconstrained Text columns`);
    log('INFO', 'and one Note column, then two items carrying one repeated value and two distinct ones,');
    log('INFO', 'then MERGE EnforceUniqueValues onto four columns and read each one back.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing list would be reused, and its columns already');
      log('INFO', 'carry whatever a previous run achieved, so the transition cannot be asked');
      log('INFO', 'of them again. Set CLEANUP = true.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  const IDS = [
    'field.unique.fixture-unconstrained-columns',
    'field.unique.fixture-duplicate-items',
    'field.unique.control-note-column-refused',
    'field.unique.control-transition-on-unique-values',
    'field.unique.transition-on-duplicate-values',
    'field.unique.transition-without-index',
  ];

  expect('field.unique.fixture-transition-list', Q.fixture);
  expect('field.unique.fixture-unconstrained-columns', Q.columns);
  expect('field.unique.fixture-duplicate-items', Q.items);
  expect('field.unique.control-note-column-refused', Q.note);
  expect('field.unique.control-transition-on-unique-values', Q.control);
  expect('field.unique.transition-on-duplicate-values', Q.duplicate);
  expect('field.unique.transition-without-index', Q.index);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // __metadata is a VERBOSE OData construct, so every field write carrying it
  // overrides the harness's default nometadata content type.
  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const MERGE = { ...VERBOSE, 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' };
  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;

  const readField = async (name) =>
    spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')?$select=Title,TypeAsString,EnforceUniqueValues,Indexed`);

  // A readback answers only when the request succeeded AND the payload
  // carries the property, because a body without it reads as undefined and
  // compares unequal to everything, which looks exactly like a wrong value.
  const propertyFault = (read, name, want) => {
    if (readFailed(read)) return `${name} could not be read (HTTP ${read.status})`;
    if (!(name in read.body)) return `the readback payload carries no ${name}`;
    if (read.body[name] !== want) {
      return `${name} reads back ${JSON.stringify(read.body[name])}, not ${JSON.stringify(want)}`;
    }
    return null;
  };

  // The OBSERVED half: what the column carries after a write. No expected
  // value, because that is the thing being measured.
  const constraintAfter = (read) => {
    if (readFailed(read)) return { known: false, why: `the column did not read back (HTTP ${read.status})` };
    if (!('EnforceUniqueValues' in read.body)) {
      return { known: false, why: 'the readback payload carries no EnforceUniqueValues' };
    }
    return {
      known: true,
      enforced: read.body.EnforceUniqueValues === true,
      shape: `EnforceUniqueValues=${JSON.stringify(read.body.EnforceUniqueValues)}, `
             + `Indexed=${JSON.stringify(read.body.Indexed)}`,
    };
  };

  // One cell: send the MERGE, read the column back, record what both said.
  // Returns the head so the controls can gate on it.
  const transition = async (id, question, column, body) => {
    const digest = await getDigest();
    const sent = await spPost(`${listPath}/fields/getbyinternalnameortitle('${column}')`,
      { __metadata: { type: column === NOTE ? 'SP.FieldMultiLineText' : 'SP.FieldText' }, ...body },
      digest, MERGE);
    const seen = constraintAfter(await readField(column));
    const shape = `MERGE ${JSON.stringify(body)} on '${column}'`;
    if (!sent.ok) {
      const head = isRefusal(sent.status) ? 'REFUSED' : 'NOT ESTABLISHED';
      record(id, question, head,
             `${shape} answered ${short(sent)}; `
             + (seen.known ? `the column still reads ${seen.shape}` : seen.why));
      return head;
    }
    if (!seen.known) {
      record(id, question, 'NOT ESTABLISHED',
             `${shape} answered HTTP ${sent.status}, but ${seen.why}, so an accepted write `
             + 'cannot be told from one that changed nothing');
      return 'NOT ESTABLISHED';
    }
    const head = seen.enforced ? 'ACCEPTED' : 'ACCEPTED, NOT APPLIED';
    record(id, question, head,
           `${shape} answered HTTP ${sent.status}; the column reads back ${seen.shape}`);
    return head;
  };

  await resetList(LIST);

  let digest = await getDigest();
  const haveList = await spGet(listPath);
  if (haveList.ok) {
    record('field.unique.fixture-transition-list', Q.fixture, 'ALREADY PRESENT',
           `reusing an existing list '${LIST}'. Set CLEANUP = true for a clean answer`);
  } else {
    const made = await spPost('web/lists', {
      Title: LIST, BaseTemplate: 100,
      Description: 'dbml-sharepoint unique-transition probe list. Safe to delete.',
    }, digest);
    record('field.unique.fixture-transition-list', Q.fixture,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIST}'` : short(made));
    if (!made.ok) {
      voidAll(IDS, `fixture incomplete: list creation failed (HTTP ${made.status})`);
      return report();
    }
  }

  // ---- The four columns, created the way a pre-#550 deploy created them ---
  const COLUMNS = [
    { name: DUP, kind: 2, type: 'SP.FieldText' },
    { name: UNIQ, kind: 2, type: 'SP.FieldText' },
    { name: IDX, kind: 2, type: 'SP.FieldText' },
    { name: NOTE, kind: 3, type: 'SP.FieldMultiLineText' },
  ];
  const creates = [];
  for (const column of COLUMNS) {
    const have = await readField(column.name);
    if (have.ok) {
      creates.push(`'${column.name}' already present`);
      continue;
    }
    digest = await getDigest();
    const made = await spPost(`${listPath}/fields`, {
      __metadata: { type: column.type }, Title: column.name, FieldTypeKind: column.kind,
    }, digest, VERBOSE);
    creates.push(`'${column.name}' create answered ${made.ok ? `HTTP ${made.status}` : short(made)}`);
  }
  const columnFaults = [];
  for (const column of COLUMNS) {
    const back = await readField(column.name);
    if (column.name === NOTE) {
      if (readFailed(back)) columnFaults.push(`'${NOTE}' could not be read (HTTP ${back.status})`);
      continue;
    }
    for (const [property, want] of [['EnforceUniqueValues', false], ['Indexed', false]]) {
      const fault = propertyFault(back, property, want);
      if (fault) columnFaults.push(`'${column.name}': ${fault}`);
    }
  }
  record('field.unique.fixture-unconstrained-columns', Q.columns,
         columnFaults.length === 0 ? 'PASS' : 'FAIL',
         `${creates.join('; ')}. `
         + (columnFaults.length === 0
           ? 'All three Text columns read back EnforceUniqueValues false and Indexed false'
           : `${columnFaults.join('; ')}. A column that does not start unconstrained cannot `
             + 'answer what the transition out of that state does: set CLEANUP = true'));
  if (columnFaults.length > 0) {
    voidAll(IDS.slice(1), 'the columns do not start unconstrained, so nothing below is about the transition');
    return report();
  }

  // ---- The two items, and the duplicate that is the independent variable --
  const before = await spGet(`${listPath}/items?$select=Id&$top=5`);
  if (readFailed(before)) {
    record('field.unique.fixture-duplicate-items', Q.items, 'FAIL',
           `the existing items could not be read (HTTP ${before.status}), so this run cannot `
           + 'tell its own rows from a previous run\'s');
    voidAll(IDS.slice(2), 'the item fixture could not be established');
    return report();
  }
  const already = (before.body.value || []).length;
  if (already > 0) {
    record('field.unique.fixture-duplicate-items', Q.items, 'FAIL',
           `the list already holds ${already} item(s), so the values under test are not the ones `
           + 'this run wrote. Set CLEANUP = true and run again');
    voidAll(IDS.slice(2), 'the item fixture was not built by this run');
    return report();
  }
  const writes = [];
  for (const item of ITEMS) {
    digest = await getDigest();
    const made = await spPost(`${listPath}/items`, item, digest);
    writes.push(`'${item.Title}' answered ${made.ok ? `HTTP ${made.status}` : short(made)}`);
  }
  const rows = await spGet(`${listPath}/items?$select=Id,Title,${DUP},${UNIQ},${IDX}&$top=5`);
  const itemFaults = [];
  if (readFailed(rows)) {
    itemFaults.push(`the items did not read back (HTTP ${rows.status})`);
  } else {
    const values = (rows.body.value || []);
    if (values.length !== ITEMS.length) {
      itemFaults.push(`${values.length} item(s) read back, not ${ITEMS.length}`);
    }
    for (const [column, wanted] of [[DUP, 1], [UNIQ, 2], [IDX, 2]]) {
      const seen = values.map((row) => row[column]);
      if (seen.some((value) => value === undefined)) {
        itemFaults.push(`the item payload carries no ${column}`);
      } else if (new Set(seen).size !== wanted) {
        itemFaults.push(`${column} holds ${JSON.stringify(seen)}, which is not ${wanted} distinct value(s)`);
      }
    }
  }
  record('field.unique.fixture-duplicate-items', Q.items,
         itemFaults.length === 0 ? 'PASS' : 'FAIL',
         `${writes.join('; ')}. `
         + (itemFaults.length === 0
           ? `${DUP} holds one value twice; ${UNIQ} and ${IDX} hold two distinct values each`
           : itemFaults.join('; ')));
  if (itemFaults.length > 0) {
    voidAll(IDS.slice(2), 'the values the transition is asked about are not the ones this run meant to write');
    return report();
  }

  // ---- NEGATIVE CONTROL: a column type documented as unsupported ---------
  // EnforceUniqueValues alone: Note separately rejects an indexing flag, so
  // sending the pair would leave the refusal attributable to either property.
  const noteHead = await transition(
    'field.unique.control-note-column-refused', Q.note, NOTE, { EnforceUniqueValues: true });
  if (noteHead !== 'REFUSED') {
    voidAll(IDS.slice(3),
            `the unsupported column type answered ${noteHead} rather than a refusal, so this `
            + 'endpoint did not refuse a constraint Microsoft documents as impossible, and '
            + 'neither an acceptance nor a refusal below can be read as an answer about the data');
    return report();
  }

  // ---- POSITIVE CONTROL: the same write where the values are distinct ----
  const controlHead = await transition(
    'field.unique.control-transition-on-unique-values', Q.control, UNIQ,
    { EnforceUniqueValues: true, Indexed: true });
  if (controlHead !== 'ACCEPTED') {
    voidAll(IDS.slice(4),
            `the transition answered ${controlHead} on a column whose values are all distinct, `
            + 'so a refusal on the duplicate column would say nothing about the duplicates');
    return report();
  }

  // ---- The question, and the index requirement beside it -----------------
  await transition('field.unique.transition-on-duplicate-values', Q.duplicate, DUP,
                   { EnforceUniqueValues: true, Indexed: true });
  await transition('field.unique.transition-without-index', Q.index, IDX,
                   { EnforceUniqueValues: true });

  return report();
})();
