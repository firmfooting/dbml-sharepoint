/**
 * dbml-sharepoint PROBE: DO ONE LIST'S FIELD CREATES SURVIVE ONE ChangeSet?
 *
 * ONE QUESTION:
 *   The deploy creates a list's columns one POST at a time because
 *   "concurrent schema writes to the SAME list race into save conflicts"
 *   (_lists.js.j2, the wave-2 lane comment). Does that race also apply to
 *   field creates delivered as ChangeSet parts of a single $batch request,
 *   which is one HTTP request rather than many concurrent ones?
 *
 * REVISION: 4d6dd871
 *
 * WHY: issue #332 area 3.2. The plan of 2026-09-03 schedules "Phase 2.1
 * field creation, roughly 78 calls, same shape" as the next phase to batch
 * after the seal phase. It is not the same shape, and this probe exists
 * because the difference is a SharePoint behaviour nobody here has measured.
 *
 * The phases already batched (seal, ACL adds, indexes, field defaults, view
 * fields, form formats) all write to objects that ALREADY EXIST. Field
 * creation mutates the list's field collection itself, which is the write
 * the lane design calls a save-conflict risk. A ChangeSet is one request, so
 * the lane argument may not reach it. It may also not be true that SharePoint
 * processes those parts serially. Both readings are plausible and this
 * project does not ship on plausible.
 *
 * A second unknown rides along. Field creation reaches SharePoint by three
 * different spellings, and only one of them is covered by the part encoding
 * measured on 2026-09-04 (#410): a plain entity POST to /fields. The other
 * two are function POSTs CARRYING A BODY (addfield and createfieldasxml with
 * `{parameters: {...}}`), and the 2026-09-04 run proved only a BODYLESS
 * function POST as a part.
 *
 * A third decides how big the port is. The deploy creates a field titled
 * with its internal name and then RENAMES it to the declared display title,
 * a MERGE whose body is computed from reading the created field back. If a
 * create and a MERGE of that same new field both land inside one ChangeSet,
 * the port is one batched stage; if not, it is a batched create stage
 * followed by single renames, which is what #332's brief already reserves
 * ("renames stay single").
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`, under the existing `transport` surface and
 * its `batch` scope.
 *
 *   transport.batch.fixture-scratch-list        does a fresh scratch list
 *       exist for the passes to add columns to?
 *   transport.batch.control-single-create       CONTROL: does ONE unbatched
 *       field create, with the body shape the deploy sends, apply and read
 *       back on this list? Without it a batched refusal cannot be told from
 *       a bad field body.
 *   transport.batch.changeset-creates-land      OBSERVE: of 40 field creates
 *       sent as one ChangeSet against one list, how many parts answered 2xx
 *       and how many of the columns actually exist afterwards?
 *   transport.batch.changeset-create-refusals   OBSERVE: what did any refused
 *       part say, and did any of it read as a save conflict?
 *   transport.batch.changeset-function-post     OBSERVE: does createfieldasxml,
 *       a function POST carrying a `{parameters: {...}}` body, survive as a
 *       ChangeSet part?
 *   transport.batch.changeset-create-then-merge OBSERVE: does a create,
 *       followed in the SAME ChangeSet by a MERGE renaming that same new
 *       field, land?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the scratch list exists (fixture); a
 *   single unbatched field create applies and is visible to the same field
 *   enumeration the observations read (control).
 *   Observes (recorded, never asserted): how many ChangeSet parts answered
 *   2xx and how many columns exist afterwards, what a refusal said, whether
 *   a body-carrying function POST is accepted as a part, and whether a
 *   create plus a MERGE of that same new field both land in one ChangeSet.
 *   The four observation rows depend on the fixture and the control. If the
 *   control fails, a refusal says nothing about the transport and the rows
 *   are void.
 *
 * WHY 40 COLUMNS: the largest single list in the shipped solutions declares
 * 37 phase-1 columns (measured over the 35 buildable solutions on
 * 2026-09-06), so 40 covers the real worst case with room over it. The body
 * is far under the 200 KiB budget BatchWriter enforces and far under the
 * 750-operation point #404 found stable, so neither is what this measures.
 *
 * SCOPE OF CLAIMS: this measures one tenant, one caller context (the
 * operator's own signed-in browser), one list and one column shape. A
 * ChangeSet that lands here is evidence about THIS TENANT at THIS MOMENT.
 *
 * HOW TO RUN
 *   1. Open the sandbox site you own.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true (CLEANUP = true recycles a
 *      leftover scratch list first; a clean fixture needs a list with no
 *      custom columns on it), paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing to delete. The probe recycles its own scratch list
 * before it reports.
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
  log('INFO', 'probe revision 4d6dd871. Quote this when reporting results.');

  const SCRATCH = 'dbmlsp Probe BatchFieldCreate';
  const listPath = `web/lists/getbytitle('${SCRATCH}')`;
  // Covers the 37-column worst case in the shipped solutions with room over
  // it, without approaching either measured ceiling.
  const BATCH_FIELDS = 40;

  const Q_FIXTURE = 'fixture: a fresh scratch list exists for the passes to add columns to';
  const Q_CONTROL = 'control: does ONE unbatched field create, with the body shape the deploy sends, apply and read back on this list?';
  const Q_LAND = 'observe: of 40 field creates sent as one ChangeSet against one list, how many parts answered 2xx and how many of the columns actually exist afterwards?';
  const Q_REFUSAL = 'observe: what did any refused part say, and did any of it read as a save conflict?';
  const Q_FUNCTION = 'observe: does createfieldasxml, a function POST carrying a {parameters: {...}} body, survive as a ChangeSet part?';
  const Q_MERGE = 'observe: does a create, followed in the SAME ChangeSet by a MERGE renaming that same new field, land?';

  expect('transport.batch.fixture-scratch-list', Q_FIXTURE);
  expect('transport.batch.control-single-create', Q_CONTROL);
  expect('transport.batch.changeset-creates-land', Q_LAND);
  expect('transport.batch.changeset-create-refusals', Q_REFUSAL);
  expect('transport.batch.changeset-function-post', Q_FUNCTION);
  expect('transport.batch.changeset-create-then-merge', Q_MERGE);

  const CONTROL_ID = 'transport.batch.control-single-create';
  const OBSERVE_IDS = ['transport.batch.changeset-creates-land',
                       'transport.batch.changeset-create-refusals',
                       'transport.batch.changeset-function-post',
                       'transport.batch.changeset-create-then-merge'];

  if (!CONFIRMED) {
    log('INFO', `Would create a scratch list '${SCRATCH}' on ${WEB}, add one column to`);
    log('INFO', 'it as a single write (the control), then send four passes of ChangeSet');
    log('INFO', `parts against that one list: ${BATCH_FIELDS} field creates in one $batch,`);
    log('INFO', 'a createfieldasxml function POST carrying a body, and a create paired');
    log('INFO', 'with a MERGE renaming that same new field. It would record how many');
    log('INFO', 'parts answered 2xx, how many columns exist afterwards, and what any');
    log('INFO', 'refusal said. The scratch list is recycled on the way out.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${SCRATCH}' would be RECYCLED first, so the fixture starts clean.`);
    } else {
      log('INFO', 'CLEANUP is off: a leftover list carrying columns from a previous run');
      log('INFO', 'would answer this run\'s questions, so the probe REFUSES to measure on');
      log('INFO', 'one. Set CLEANUP = true for a clean run.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  // ---- Tenant redaction -------------------------------------------------
  // Recorded evidence must not name the tenant, and a $batch part carries an
  // ABSOLUTE operation URL because the protocol requires one. The
  // scheme+host is replaced with [TENANT], case-insensitively, wherever it
  // appears, leaving the path visible.
  const ORIGIN = (() => {
    const afterScheme = WEB.indexOf('//');
    if (afterScheme === -1) return WEB;
    const firstSlash = WEB.indexOf('/', afterScheme + 2);
    return firstSlash === -1 ? WEB : WEB.slice(0, firstSlash);
  })();
  const redact = (value) => {
    const s = String(value);
    if (!ORIGIN) return s;
    const needle = ORIGIN.toLowerCase();
    const hay = s.toLowerCase();
    let out = '';
    let from = 0;
    for (;;) {
      const hit = hay.indexOf(needle, from);
      if (hit === -1) return out + s.slice(from);
      out += s.slice(from, hit) + '[TENANT]';
      from = hit + ORIGIN.length;
    }
  };

  // ---- The part encoding under test -------------------------------------
  // Deliberately a COPY of BatchWriter._part in
  // src/dbml_sharepoint/templates/_http_batch.js.j2 rather than an import:
  // the probe has to be one pasteable file, and a copy that drifts from the
  // shipped encoder would measure a spelling nothing sends. Verbose headers
  // and a __metadata body, verb in the request line, no X-HTTP-Method, all
  // as measured on 2026-09-04.
  const partHeaders = (digest, extra = {}) => ({
    'Accept': 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
    'X-RequestDigest': digest,
    ...extra,
  });
  const boundaryToken = (label) => {
    const rnd = () => Math.random().toString(36).slice(2, 10);
    return `${label}_${rnd()}${rnd()}`;
  };
  const partOf = (op, digest, inner) => {
    const extra = { ...(op.extraHeaders || {}) };
    const tunnelled = extra['X-HTTP-Method'];
    delete extra['X-HTTP-Method'];
    const headers = Object.entries(partHeaders(digest, extra))
      .map(([name, value]) => `${name}: ${value}\r\n`).join('');
    const payload = op.body === undefined ? null : JSON.stringify(op.body);
    return `--${inner}\r\n`
      + 'Content-Type: application/http\r\n'
      + 'Content-Transfer-Encoding: binary\r\n'
      + '\r\n'
      + `${tunnelled || op.method} ${WEB}/_api/${op.path} HTTP/1.1\r\n`
      + headers
      + '\r\n'
      + (payload === null ? '' : `${payload}\r\n`);
  };

  // One $batch request holding one ChangeSet of `ops`. Per-part statuses are
  // counted the way BatchWriter counts them, so a partial landing here reads
  // exactly as it would in a deploy. There is deliberately no retry: a retry
  // would hide a save conflict, which is the thing being looked for.
  const sendChangeSet = async (ops, digest) => {
    const outer = boundaryToken('batch');
    const inner = boundaryToken('changeset');
    const body = `--${outer}\r\n`
      + `Content-Type: multipart/mixed; boundary=${inner}\r\n`
      + '\r\n'
      + ops.map((op) => partOf(op, digest, inner)).join('')
      + `--${inner}--\r\n`
      + `--${outer}--\r\n`;
    let res;
    try {
      // No Accept header, for #401's reason: a JSON Accept turns the
      // throttling-page redirect into a 406 that only its URL identifies.
      res = await fetch(`${WEB}/_api/$batch`, {
        method: 'POST',
        headers: {
          'Content-Type': `multipart/mixed; boundary=${outer}`,
          'X-RequestDigest': digest,
        },
        body,
      });
    } catch (err) {
      return { ok: false, status: 0, url: '', text: String(err), statuses: [] };
    }
    const text = await res.text();
    const statuses = [];
    const statusRe = /HTTP\/1\.1\s+(\d{3})/g;
    let match;
    while ((match = statusRe.exec(text)) !== null) statuses.push(Number(match[1]));
    return { ok: res.ok, status: res.status, url: res.url, text, statuses };
  };

  // ---- Fixture shapes ---------------------------------------------------
  // The body shape the deploy sends for a plain text column, so a refusal is
  // about the transport rather than about a body SharePoint never sees.
  const textFieldBody = (name) => ({
    __metadata: { type: 'SP.FieldText' },
    Title: name,
    FieldTypeKind: 2,
    MaxLength: 255,
  });
  const batchName = (index) => `dbmlspBatchCol${index}`;

  // The enumeration the control certifies and every observation reads. A
  // truncated read would report a column that landed as absent, which is the
  // one answer this must never get wrong, so it carries an explicit $top.
  const readFieldNames = async () => {
    const r = await spGet(`${listPath}/fields?$select=InternalName,Title&$top=500`);
    if (readFailed(r) || !Array.isArray(r.body.value)) return null;
    return r.body.value;
  };

  const qOf = (id) => RESULTS.find((row) => row.id === id).question;
  const recordVoid = (id, evidence) =>
    record(id, qOf(id), 'NOT ESTABLISHED', evidence, 'void');

  // A save conflict is what the lane design says to expect, so the words
  // SharePoint spells it with are looked for by name and the raw text is
  // recorded either way. Matching is a convenience for the reader, never the
  // verdict: the evidence line carries what actually came back.
  const CONFLICT_MARKERS = ['save conflict', 'modified by another user',
                            'has been modified', 'version conflict', '409'];
  const looksLikeConflict = (text) => {
    const low = String(text).toLowerCase();
    return CONFLICT_MARKERS.filter((marker) => low.includes(marker));
  };

  let created = false;
  const recycleScratch = async () => {
    for (let attempt = 0; attempt < 3; attempt++) {
      let gone;
      try {
        const digest = await getDigest();
        gone = await spPost(`${listPath}/recycle`, {}, digest);
      } catch (err) {
        gone = { ok: false, status: 0, text: String(err) };
      }
      if (gone.ok) {
        log('OK', `Recycled scratch list '${SCRATCH}'. Nothing left behind.`);
        return;
      }
      if (attempt === 2) {
        log('FAIL', `Could not recycle '${SCRATCH}': HTTP ${gone.status} `
          + `${redact(gone.text).slice(0, 160)}. Recycle it by hand.`);
      } else {
        log('WARN', `Recycle of '${SCRATCH}' failed (HTTP ${gone.status}); retrying in 5s.`);
        await new Promise((res) => setTimeout(res, 5000));
      }
    }
  };

  try {
    await resetList(SCRATCH);
    let digest = await getDigest();

    // ---- fixture-scratch-list ------------------------------------------
    const pre = await spGet(`${listPath}?$select=Id`);
    if (pre.ok) {
      // resetList only recycles when CLEANUP is on, so reaching this with the
      // list still present means a previous run's columns are still on it.
      record('transport.batch.fixture-scratch-list', Q_FIXTURE, 'FAIL',
             `a list named '${SCRATCH}' already exists (left by a run that did not `
             + 'finish, or a manual creation) and CLEANUP is off. Its columns would '
             + 'answer this run\'s questions.');
      throw new Error('fixture: set CLEANUP = true so the leftover list is recycled first');
    }
    const made = await spPost('web/lists', {
      Title: SCRATCH,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint batch-field-create probe scratch list. Safe to delete.',
    }, digest);
    if (!made.ok) {
      record('transport.batch.fixture-scratch-list', Q_FIXTURE, 'FAIL',
             `create refused with HTTP ${made.status}: ${redact(made.text).slice(0, 300)}`);
      throw new Error('fixture: the scratch list create was refused');
    }
    created = true;
    const back = await spGet(`${listPath}?$select=Id`);
    if (!back.ok) {
      record('transport.batch.fixture-scratch-list', Q_FIXTURE, 'FAIL',
             `created '${SCRATCH}' but the read-back failed with HTTP ${back.status}`);
      throw new Error('fixture: the scratch list did not read back after create');
    }
    record('transport.batch.fixture-scratch-list', Q_FIXTURE, 'PASS',
           `created '${SCRATCH}' (read back OK)`);

    // ---- control-single-create ------------------------------------------
    // One ordinary field create, exactly as the deploy sends it today, then
    // read back through the same enumeration the observations use.
    digest = await getDigest();
    const controlName = 'dbmlspControlCol';
    const single = await fetch(`${WEB}/_api/${listPath}/fields`, {
      method: 'POST',
      headers: partHeaders(digest),
      body: JSON.stringify(textFieldBody(controlName)),
    });
    const singleText = await single.text();
    let controlOutcome;
    let controlEvidence;
    if (!single.ok) {
      controlOutcome = 'FAIL';
      controlEvidence = `the single field create was refused with HTTP ${single.status}: `
        + redact(singleText).slice(0, 300);
    } else {
      const names = await readFieldNames();
      if (names === null) {
        controlOutcome = 'NOT ESTABLISHED';
        controlEvidence = 'the single create answered 2xx but the field enumeration '
          + 'could not be read, so nothing certifies what the observations read from';
      } else if (!names.some((f) => f.InternalName === controlName)) {
        controlOutcome = 'FAIL';
        controlEvidence = `the single create answered HTTP ${single.status} but `
          + `'${controlName}' is absent from the field enumeration, so a 2xx on this `
          + 'list does not mean a column landed';
      } else {
        controlOutcome = 'PASS';
        controlEvidence = `a single unbatched create of '${controlName}' answered HTTP `
          + `${single.status} and the column is present in the field enumeration, so `
          + 'the body shape and the read-back are both good on this list';
      }
    }
    record(CONTROL_ID, Q_CONTROL, controlOutcome, controlEvidence);

    if (controlOutcome !== 'PASS') {
      for (const id of OBSERVE_IDS) {
        recordVoid(id, `control-single-create is ${controlOutcome}: `
          + controlEvidence.slice(0, 200));
      }
      return report();
    }

    // ---- changeset-creates-land and changeset-create-refusals -----------
    digest = await getDigest();
    const createOps = [];
    for (let i = 1; i <= BATCH_FIELDS; i++) {
      createOps.push({ method: 'POST', path: `${listPath}/fields`,
                       body: textFieldBody(batchName(i)) });
    }
    const creates = await sendChangeSet(createOps, digest);
    const afterCreates = await readFieldNames();
    const landedNames = afterCreates === null
      ? null
      : afterCreates.filter((f) => /^dbmlspBatchCol\d+$/.test(f.InternalName || ''));
    const ok2xx = creates.statuses.filter((s) => s >= 200 && s < 300).length;
    const nonOk = creates.statuses.filter((s) => !(s >= 200 && s < 300));

    if (!creates.ok) {
      record('transport.batch.changeset-creates-land', Q_LAND, 'OUTER REQUEST REFUSED',
        `the $batch request carrying ${BATCH_FIELDS} field creates answered HTTP `
        + `${creates.status} and no part status could be read. Body: `
        + redact(creates.text).slice(0, 300));
    } else if (landedNames === null) {
      record('transport.batch.changeset-creates-land', Q_LAND, 'READBACK FAILED',
        `the $batch answered HTTP ${creates.status} with ${creates.statuses.length} part `
        + `status(es), ${ok2xx} of them 2xx, but the field enumeration could not be read `
        + 'afterwards, so how many columns exist is unknown');
    } else {
      record('transport.batch.changeset-creates-land', Q_LAND, 'RECORDED',
        `${BATCH_FIELDS} field creates sent as one ChangeSet against one list: the outer `
        + `request answered HTTP ${creates.status} with ${creates.statuses.length} part `
        + `status(es) (${ok2xx} in the 2xx range), and ${landedNames.length} of the `
        + `${BATCH_FIELDS} columns are present in the field enumeration afterwards. `
        + `Part statuses: ${creates.statuses.join(', ') || 'none parsed'}.`);
    }

    if (nonOk.length === 0 && creates.ok) {
      record('transport.batch.changeset-create-refusals', Q_REFUSAL, 'NO PART REFUSED',
        `every one of the ${creates.statuses.length} part status(es) was in the 2xx `
        + 'range, so there is no refusal text to classify and no save conflict was '
        + 'reported by any part');
    } else {
      const markers = looksLikeConflict(creates.text);
      record('transport.batch.changeset-create-refusals', Q_REFUSAL, 'REFUSAL RECORDED',
        `${nonOk.length} part status(es) outside 2xx (${nonOk.join(', ') || 'outer '
        + `request HTTP ${creates.status}`}). Save-conflict wording `
        + `${markers.length ? `PRESENT (${markers.join(', ')})` : 'not present'} in the `
        + `response. Body: ${redact(creates.text).slice(0, 600)}`);
    }

    // ---- changeset-function-post ----------------------------------------
    // createfieldasxml is how the deploy creates a projected lookup and a
    // multi-value lookup, and it is a function POST WITH a body, which the
    // 2026-09-04 part-encoding run did not cover.
    digest = await getDigest();
    const xmlName = 'dbmlspXmlCol';
    const xmlOps = [{
      method: 'POST',
      path: `${listPath}/fields/createfieldasxml`,
      body: { parameters: {
        SchemaXml: `<Field Type="Text" DisplayName="${xmlName}" Name="${xmlName}"/>`,
        Options: 8,
      } },
    }];
    const xmlBatch = await sendChangeSet(xmlOps, digest);
    const afterXml = await readFieldNames();
    const xmlPresent = afterXml === null
      ? null
      : afterXml.some((f) => f.InternalName === xmlName);
    if (afterXml === null) {
      record('transport.batch.changeset-function-post', Q_FUNCTION, 'READBACK FAILED',
        `the $batch answered HTTP ${xmlBatch.status} with part status(es) `
        + `${xmlBatch.statuses.join(', ') || 'none parsed'}, but the field enumeration `
        + 'could not be read afterwards, so whether the column landed is unknown');
    } else {
      record('transport.batch.changeset-function-post', Q_FUNCTION, 'RECORDED',
        `createfieldasxml sent as a single ChangeSet part with a {parameters: {...}} `
        + `body: the outer request answered HTTP ${xmlBatch.status} with part status(es) `
        + `${xmlBatch.statuses.join(', ') || 'none parsed'}, and '${xmlName}' is `
        + `${xmlPresent ? 'PRESENT' : 'ABSENT'} in the field enumeration afterwards.`
        + (xmlPresent ? '' : ` Body: ${redact(xmlBatch.text).slice(0, 400)}`));
    }

    // ---- changeset-create-then-merge ------------------------------------
    // The rename the deploy performs after every create, asked as the one
    // question that decides whether the port is one batched stage or two.
    digest = await getDigest();
    const mergeName = 'dbmlspMergeCol';
    const mergeTitle = 'Renamed Inside The ChangeSet';
    const mergeOps = [
      { method: 'POST', path: `${listPath}/fields`, body: textFieldBody(mergeName) },
      { method: 'POST',
        path: `${listPath}/fields/getbyinternalnameortitle('${mergeName}')`,
        body: { __metadata: { type: 'SP.FieldText' }, Title: mergeTitle },
        extraHeaders: { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' } },
    ];
    const mergeBatch = await sendChangeSet(mergeOps, digest);
    const afterMerge = await readFieldNames();
    const mergeField = afterMerge === null
      ? null
      : afterMerge.find((f) => f.InternalName === mergeName);
    if (afterMerge === null) {
      record('transport.batch.changeset-create-then-merge', Q_MERGE, 'READBACK FAILED',
        `the $batch answered HTTP ${mergeBatch.status} with part status(es) `
        + `${mergeBatch.statuses.join(', ') || 'none parsed'}, but the field enumeration `
        + 'could not be read afterwards, so the outcome is unknown');
    } else {
      const state = !mergeField
        ? 'the column does not exist at all, so the create part did not land'
        : mergeField.Title === mergeTitle
          ? `the column exists and its Title is '${mergeField.Title}', so BOTH parts landed`
          : `the column exists but its Title is still '${mergeField.Title}', so the `
            + 'create landed and the MERGE did not';
      record('transport.batch.changeset-create-then-merge', Q_MERGE, 'RECORDED',
        `a create of '${mergeName}' and a MERGE renaming it to '${mergeTitle}', both in `
        + `one ChangeSet: the outer request answered HTTP ${mergeBatch.status} with part `
        + `status(es) ${mergeBatch.statuses.join(', ') || 'none parsed'}, and ${state}.`
        + (mergeField && mergeField.Title === mergeTitle
          ? ''
          : ` Body: ${redact(mergeBatch.text).slice(0, 400)}`));
    }
  } catch (err) {
    const message = redact(String((err && err.message) || err));
    if (message.indexOf('fixture:') === 0) {
      // The fixture row was recorded FAIL above; the rows that were never
      // asked keep the harness default and stay open for a clean re-run.
      log('INFO', `${message.slice(7)} The unasked rows stay open.`);
    } else {
      log('FAIL', `probe aborted with an uncaught error: ${message.slice(0, 240)}`);
    }
  } finally {
    if (created) await recycleScratch();
  }

  return report();
})();
