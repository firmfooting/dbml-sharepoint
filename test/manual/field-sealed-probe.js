/**
 * dbml-sharepoint PROBE: DOES SEALING A COLUMN SET CanBeDeleted FALSE
 *
 * REVISION: 29611c87
 *
 * ONE QUESTION:
 *   Sealing a column is believed to be what makes SharePoint report
 *   `CanBeDeleted: false`, and unsealing it is believed to restore
 *   `CanBeDeleted: true`. Does one field, sealed and unsealed in each order,
 *   answer that way, and what does SharePoint say to a delete attempt in
 *   each state?
 *
 * One observation on one live list is what the maintenance surface rests on
 * today: 2026-09-03, eleven sealed columns reading `CanBeDeleted: false` and
 * three unsealed custom ones reading `true`. `_maintain_list.js.j2` filters
 * its column menu on `(f.CanBeDeleted !== false || f.Sealed === true)`
 * because of it, and its delete path unseals, reads back and then deletes.
 * If unsealing did not restore deletability, that script would fail at the
 * delete rather than at the menu, which is better and still wrong.
 *
 * Microsoft Learn does not settle it, and says three different things about
 * the two properties. `Field element (Field)`: Sealed "marks the field as
 * irremovable. The Change Column page has no Delete button. Users cannot
 * delete the field." `Field element (DeploymentManifest -
 * DeploymentFieldTemplate)` describes the same attribute as indicating
 * "whether other fields can be derived from the field". `Field.Sealed` is
 * `public bool Sealed { get; set; }` and `Field.CanBeDeleted` is
 * `public bool CanBeDeleted { get; }`, read-only, with nothing said about
 * what sets it. Three pages, no relationship, and one of the two properties
 * can only be written through whatever the other one does.
 *
 * ONE FIELD, BOTH ORDERS, which is what the issue's newest comment asks for
 * and supersedes the column-of-every-type sweep in its body. Order A writes
 * `Sealed` and reads `CanBeDeleted` back. Order B writes `CanBeDeleted` and
 * reads `Sealed` back, including one MERGE carrying the contradictory pair,
 * because a property SharePoint derives and a property it stores answer
 * that differently.
 *
 * SCOPE AND QUESTIONS
 *   field.sealed.fixture-list-created
 *     A generic list is created (BaseTemplate 100).
 *   field.sealed.fixture-subject-column
 *     One Text column is created and reads back Sealed false, Hidden false
 *     and FromBaseType false. Every row below is about that column starting
 *     unsealed and custom.
 *   field.sealed.control-unknown-property-refused
 *     NEGATIVE CONTROL: a field MERGE carrying a property SP.Field does not
 *     define is REFUSED. Without it, an accepted MERGE below cannot be told
 *     from a body the server ignored.
 *   field.sealed.control-description-sticks
 *     POSITIVE CONTROL: a MERGE of Description on the same field is accepted
 *     and reads back. Without it, a CanBeDeleted write that changes nothing
 *     cannot be told from a MERGE that does not land on this field at all.
 *   field.sealed.seal-write-readback
 *     DEPENDENCY: a MERGE of Sealed true reads back Sealed true. The seal
 *     write is what the measurement depends on, so it is asserted.
 *   field.sealed.canbedeleted-after-seal
 *     OBSERVE: what CanBeDeleted reads once the column is sealed.
 *   field.sealed.unseal-write-readback
 *     DEPENDENCY: a MERGE of Sealed false reads back Sealed false.
 *   field.sealed.canbedeleted-after-unseal
 *     OBSERVE: what CanBeDeleted reads once the column is unsealed again.
 *   field.sealed.canbedeleted-write-while-unsealed
 *     OBSERVE: what a MERGE of CanBeDeleted false answers on an UNSEALED
 *     column, and what Sealed and CanBeDeleted read afterwards.
 *   field.sealed.fixture-reseal-written
 *     DEPENDENCY: the column is sealed again, read back, for the write below.
 *   field.sealed.canbedeleted-write-while-sealed
 *     OBSERVE: what a MERGE of CanBeDeleted true answers on a SEALED column,
 *     and whether it unseals anything.
 *   field.sealed.both-properties-in-one-merge
 *     OBSERVE: what one MERGE carrying Sealed false and CanBeDeleted false
 *     together answers, and which half of the pair the readback shows.
 *   field.sealed.control-plain-column-deleted
 *     POSITIVE CONTROL: a second column, never sealed, is created and
 *     deleted, and a follow-up read no longer finds it. Without it, a
 *     refused delete below could be this identity, this list or the request
 *     shape rather than the seal.
 *   field.sealed.fixture-sealed-for-delete
 *     DEPENDENCY: the subject column is sealed and reads back sealed,
 *     immediately before the delete attempt.
 *   field.sealed.delete-while-sealed
 *     OBSERVE: what a DELETE of the sealed column answers, and whether the
 *     column is still there afterwards.
 *   field.sealed.fixture-subject-restored
 *     The column is rebuilt if the attempt above removed it, so the unsealed
 *     half still has a subject. NOT APPLICABLE when nothing was removed.
 *   field.sealed.fixture-unsealed-for-delete
 *     DEPENDENCY: the subject column is unsealed and reads back unsealed,
 *     immediately before the second delete attempt.
 *   field.sealed.delete-while-unsealed
 *     OBSERVE: what a DELETE of the unsealed column answers, and whether a
 *     follow-up read still finds it.
 *
 * OBSERVED, NEVER ASSERTED
 *   CanBeDeleted, at every point it is read. The answer to each delete
 *   attempt. The answer to each CanBeDeleted write, and what the field reads
 *   afterwards. The Sealed and AllowDeletion attributes as they appear in
 *   the field's own SchemaXml. Those are the measurement. What the run
 *   DEPENDS on is the seal and unseal writes, and each of those is read back
 *   and asserted. Asserting CanBeDeleted would make the experiment kill
 *   itself the moment it started working, and a probe that fails because the
 *   platform agreed with it is indistinguishable from a broken one.
 *
 * NOT MEASURED HERE
 *   Whether the Change Column page shows a Delete button in each state.
 *   That is a rendered surface, it needs a capture, and this run ends with
 *   the column deleted, so it needs a probe that stops with the column in
 *   one state and waits. Also not measured: whether the relationship holds
 *   across column types, since the superseding comment asks for one field
 *   rather than one of each; a site column at web scope rather than a list
 *   column; and AllowDeletion, which is read out of SchemaXml as an
 *   observation and never written.
 *
 * MICROSOFT LEARN CITATIONS
 *   Sealed as a schema attribute, and AllowDeletion beside it:
 *     "Field element (Field)", "Field element (List)"
 *   The same attribute described as controlling derivation:
 *     "Field element (DeploymentManifest - DeploymentFieldTemplate)"
 *   The two properties over REST:
 *     "Field.Sealed Property", "Field.CanBeDeleted Property" (CSOM)
 *   List creation via POST to `web/lists`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields`, and field MERGE and DELETE:
 *     "Fields REST API reference", dn600182(v=office.15)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
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

  log('INFO', 'probe revision 29611c87. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Sealed Field';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  // Internal names equal display names: created through the same POST to
  // /fields the deploy uses, so they carry no _x0020_ encoding.
  const SUBJECT = 'SealSubject';
  const WITNESS = 'DeleteWitness';
  const DESCRIPTION = 'dbmlsp probe: a description written to prove a MERGE lands';

  const Q = {
    fixture: 'A generic list is created (BaseTemplate 100)',
    subject: 'One Text column is created and reads back Sealed false, Hidden false and FromBaseType false',
    unknown: 'NEGATIVE CONTROL: a field MERGE carrying a property SP.Field does not define is refused',
    description: 'POSITIVE CONTROL: a MERGE of Description on the same field is accepted and reads back',
    seal: 'DEPENDENCY: a MERGE of Sealed true reads back Sealed true',
    afterSeal: 'What does CanBeDeleted read once the column is sealed',
    unseal: 'DEPENDENCY: a MERGE of Sealed false reads back Sealed false',
    afterUnseal: 'What does CanBeDeleted read once the column is unsealed again',
    writeUnsealed: 'What does a MERGE of CanBeDeleted false answer on an unsealed column, and what reads back',
    reseal: 'DEPENDENCY: the column is sealed again and reads back sealed',
    writeSealed: 'What does a MERGE of CanBeDeleted true answer on a sealed column, and what reads back',
    bothAtOnce: 'What does one MERGE carrying Sealed false and CanBeDeleted false together answer',
    control: 'POSITIVE CONTROL: a second column, never sealed, is created and deleted, and no longer reads back',
    sealedForDelete: 'DEPENDENCY: the subject column is sealed and reads back sealed before the delete attempt',
    deleteSealed: 'What does a DELETE of the sealed column answer, and is the column still there',
    restored: 'Was the column rebuilt after the sealed delete attempt removed it',
    unsealedForDelete: 'DEPENDENCY: the subject column is unsealed and reads back unsealed before the delete attempt',
    deleteUnsealed: 'What does a DELETE of the unsealed column answer, and is the column still there',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' on ${WEB} with two Text columns,`);
    log('INFO', `'${SUBJECT}' and '${WITNESS}'.`);
    log('INFO', `Would flip Sealed on '${SUBJECT}' in both directions, attempt to write CanBeDeleted`);
    log('INFO', 'in each state, then DELETE both columns: the witness unsealed, the subject once');
    log('INFO', 'sealed and once unsealed. Only columns this probe created are deleted.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing list would be reused. A column left sealed by a');
      log('INFO', 'previous run is reported by the fixture row rather than quietly measured.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('field.sealed.fixture-list-created', Q.fixture);
  expect('field.sealed.fixture-subject-column', Q.subject);
  expect('field.sealed.control-unknown-property-refused', Q.unknown);
  expect('field.sealed.control-description-sticks', Q.description);
  expect('field.sealed.seal-write-readback', Q.seal);
  expect('field.sealed.canbedeleted-after-seal', Q.afterSeal);
  expect('field.sealed.unseal-write-readback', Q.unseal);
  expect('field.sealed.canbedeleted-after-unseal', Q.afterUnseal);
  expect('field.sealed.canbedeleted-write-while-unsealed', Q.writeUnsealed);
  expect('field.sealed.fixture-reseal-written', Q.reseal);
  expect('field.sealed.canbedeleted-write-while-sealed', Q.writeSealed);
  expect('field.sealed.both-properties-in-one-merge', Q.bothAtOnce);
  expect('field.sealed.control-plain-column-deleted', Q.control);
  expect('field.sealed.fixture-sealed-for-delete', Q.sealedForDelete);
  expect('field.sealed.delete-while-sealed', Q.deleteSealed);
  expect('field.sealed.fixture-subject-restored', Q.restored);
  expect('field.sealed.fixture-unsealed-for-delete', Q.unsealedForDelete);
  expect('field.sealed.delete-while-unsealed', Q.deleteUnsealed);

  const AFTER_LIST = [
    'field.sealed.fixture-subject-column',
    'field.sealed.control-unknown-property-refused',
    'field.sealed.control-description-sticks',
    'field.sealed.seal-write-readback',
    'field.sealed.canbedeleted-after-seal',
    'field.sealed.unseal-write-readback',
    'field.sealed.canbedeleted-after-unseal',
    'field.sealed.canbedeleted-write-while-unsealed',
    'field.sealed.fixture-reseal-written',
    'field.sealed.canbedeleted-write-while-sealed',
    'field.sealed.both-properties-in-one-merge',
    'field.sealed.control-plain-column-deleted',
    'field.sealed.fixture-sealed-for-delete',
    'field.sealed.delete-while-sealed',
    'field.sealed.fixture-subject-restored',
    'field.sealed.fixture-unsealed-for-delete',
    'field.sealed.delete-while-unsealed',
  ];
  const WRITE_ROWS = [
    'field.sealed.canbedeleted-write-while-unsealed',
    'field.sealed.fixture-reseal-written',
    'field.sealed.canbedeleted-write-while-sealed',
    'field.sealed.both-properties-in-one-merge',
  ];
  const DELETE_ROWS = [
    'field.sealed.fixture-sealed-for-delete',
    'field.sealed.delete-while-sealed',
    'field.sealed.fixture-subject-restored',
    'field.sealed.fixture-unsealed-for-delete',
    'field.sealed.delete-while-unsealed',
  ];

  const questionFor = (id) => RESULTS.find((r) => r.id === id).question;
  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, questionFor(id), 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // __metadata is a VERBOSE OData construct, so every field write carrying
  // it overrides the harness's default nometadata content type.
  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;
  const show = (value) => (value === undefined ? 'absent' : JSON.stringify(value));

  const fieldPath = (name) => `${listPath}/fields/getbyinternalnameortitle('${name}')`;
  // Sealed and CanBeDeleted sit beside the three properties _maintain_list
  // filters on, so a run reports the whole shape its consumer reads.
  const FIELD_SELECT = 'InternalName,Title,TypeAsString,Hidden,FromBaseType,'
    + 'ReadOnlyField,Sealed,CanBeDeleted,Description';

  const readField = async (name) => {
    const r = await spGet(`${fieldPath(name)}?$select=${FIELD_SELECT}`);
    return readFailed(r) ? null : r.body;
  };
  const describeField = (f) => (f === null
    ? 'the field did not read back'
    : `Sealed=${show(f.Sealed)}, CanBeDeleted=${show(f.CanBeDeleted)}, `
      + `ReadOnlyField=${show(f.ReadOnlyField)}, Hidden=${show(f.Hidden)}, `
      + `FromBaseType=${show(f.FromBaseType)}`);

  const readSchema = async (name) => {
    const r = await spGet(`${fieldPath(name)}?$select=SchemaXml`);
    return readFailed(r) ? null : String(r.body.SchemaXml || '');
  };
  // The two schema attributes behind the properties, quoted as they read.
  const schemaAttrs = (xml) => {
    if (xml === null) return 'SchemaXml did not read back';
    const attr = (name) => {
      const found = new RegExp(`\\b${name}="([^"]*)"`, 'i').exec(xml);
      return found ? `${name}="${found[1]}"` : `${name} absent`;
    };
    return `${attr('Sealed')}, ${attr('AllowDeletion')}`;
  };

  const mergeField = async (name, body) => spPost(fieldPath(name), {
    __metadata: { type: 'SP.Field' }, ...body,
  }, await getDigest(), { ...VERBOSE, 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });

  const deleteField = async (name) => spPost(fieldPath(name), {}, await getDigest(),
                                             { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });

  const createTextColumn = async (name) => spPost(`${listPath}/fields`, {
    __metadata: { type: 'SP.FieldText' }, Title: name, FieldTypeKind: 2,
  }, await getDigest(), VERBOSE);

  // The seal writes are the dependency, so each one is read back and
  // asserted. CanBeDeleted travels in the evidence and decides nothing.
  const writeSealed = async (id, want) => {
    const sent = await mergeField(SUBJECT, { Sealed: want });
    const back = await readField(SUBJECT);
    const held = back !== null && back.Sealed === want;
    record(id, questionFor(id), held ? 'PASS' : 'FAIL',
           `MERGE of Sealed:${want} answered ${short(sent)}; the field reads ${describeField(back)}`);
    return held;
  };

  const observeCanBeDeleted = async (id, state) => {
    const back = await readField(SUBJECT);
    const xml = await readSchema(SUBJECT);
    const head = (back !== null && typeof back.CanBeDeleted === 'boolean')
      ? (back.CanBeDeleted ? 'CANBEDELETED TRUE' : 'CANBEDELETED FALSE')
      : 'NOT ESTABLISHED';
    record(id, questionFor(id), head,
           `with the column ${state}: ${describeField(back)}; SchemaXml carries ${schemaAttrs(xml)}`);
  };

  const observeWrite = async (id, body, state) => {
    const sent = await mergeField(SUBJECT, body);
    const back = await readField(SUBJECT);
    const head = sent.ok
      ? 'MERGE ACCEPTED'
      : (isRefusal(sent.status) ? 'MERGE REFUSED' : 'NOT ESTABLISHED');
    record(id, questionFor(id), head,
           `MERGE of ${JSON.stringify(body)} sent while the column was ${state} answered `
           + `${short(sent)}; the field then reads ${describeField(back)}`);
  };

  // Returns whether the column is gone, so the run knows what it still has.
  const observeDelete = async (id, state) => {
    const attempt = await deleteField(SUBJECT);
    const after = await spGet(`${fieldPath(SUBJECT)}?$select=${FIELD_SELECT}`);
    const head = attempt.ok
      ? (after.ok ? 'DELETE ACCEPTED, COLUMN STILL THERE' : 'DELETE SUCCEEDED')
      : (isRefusal(attempt.status) ? 'DELETE REFUSED' : 'NOT ESTABLISHED');
    record(id, questionFor(id), head,
           `DELETE sent while the column was ${state} answered ${short(attempt)}; `
           + `a follow-up read answered HTTP ${after.status}`);
    return !after.ok;
  };

  await resetList(LIST);

  const haveList = await spGet(listPath);
  if (haveList.ok) {
    record('field.sealed.fixture-list-created', Q.fixture, 'ALREADY PRESENT',
           `reusing an existing list '${LIST}'. Set CLEANUP = true for a clean answer`);
  } else {
    const made = await spPost('web/lists', {
      Title: LIST, BaseTemplate: 100,
      Description: 'dbml-sharepoint field-sealed probe list. Safe to delete.',
    }, await getDigest());
    record('field.sealed.fixture-list-created', Q.fixture, made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIST}'` : short(made));
    if (!made.ok) {
      voidAll(AFTER_LIST, `fixture incomplete: list creation failed (HTTP ${made.status})`);
      return report();
    }
  }

  // ---- The subject column, unsealed and custom --------------------------
  const haveSubject = await readField(SUBJECT);
  let madeSubject = { ok: true, status: 'present', text: 'already present' };
  if (haveSubject === null) {
    madeSubject = await createTextColumn(SUBJECT);
  }
  const subject = await readField(SUBJECT);
  const usable = subject !== null && subject.Sealed === false
    && subject.Hidden === false && subject.FromBaseType === false;
  record('field.sealed.fixture-subject-column', Q.subject, usable ? 'PASS' : 'FAIL',
         `POST fields answered ${short(madeSubject)}; the field reads ${describeField(subject)}`
         + (subject !== null && subject.Sealed === true
           ? '. A previous run left it SEALED: set CLEANUP = true and run again'
           : ''));
  if (!usable) {
    voidAll(AFTER_LIST.slice(1),
            'there is no unsealed custom column to flip, so no row below is about one');
    return report();
  }

  // ---- NEGATIVE CONTROL: a property SP.Field does not define ------------
  const junk = await mergeField(SUBJECT, { dbmlspNoSuchProperty: true });
  const junkRefused = !junk.ok && isRefusal(junk.status);
  record('field.sealed.control-unknown-property-refused', Q.unknown,
         junkRefused ? 'PASS' : (junk.ok ? 'FAIL' : 'NOT ESTABLISHED'),
         junkRefused
           ? `refused with ${short(junk)}`
           : (junk.ok
             ? 'a MERGE naming a property SP.Field does not define was ACCEPTED, so an accepted '
               + 'MERGE below cannot be told from a body the server ignored'
             : `the MERGE failed with non-refusal ${short(junk)}`));
  if (!junkRefused) {
    voidAll(AFTER_LIST.slice(2),
            `the negative control did not hold (HTTP ${junk.status}), so no MERGE answer below `
            + 'can be read as the server acting on what it was sent');
    return report();
  }

  // ---- POSITIVE CONTROL: a MERGE on this field does land ----------------
  const described = await mergeField(SUBJECT, { Description: DESCRIPTION });
  const describedBack = await readField(SUBJECT);
  const sticks = describedBack !== null && describedBack.Description === DESCRIPTION;
  record('field.sealed.control-description-sticks', Q.description, sticks ? 'PASS' : 'FAIL',
         `MERGE of Description answered ${short(described)}; it reads back `
         + `${show(describedBack === null ? undefined : describedBack.Description)}`);

  // ---- Order A: write Sealed, read CanBeDeleted -------------------------
  const sealed = await writeSealed('field.sealed.seal-write-readback', true);
  if (sealed) {
    await observeCanBeDeleted('field.sealed.canbedeleted-after-seal', 'sealed');
  } else {
    voidAll(['field.sealed.canbedeleted-after-seal'],
            'the seal write did not read back, so CanBeDeleted was not read on a sealed column');
  }

  const unsealed = await writeSealed('field.sealed.unseal-write-readback', false);
  if (unsealed) {
    await observeCanBeDeleted('field.sealed.canbedeleted-after-unseal', 'unsealed again');
  } else {
    voidAll(['field.sealed.canbedeleted-after-unseal'],
            'the unseal write did not read back, so CanBeDeleted was not read on an unsealed column');
  }

  // ---- Order B: write CanBeDeleted, read Sealed -------------------------
  if (!sticks) {
    voidAll(WRITE_ROWS,
            'the positive control did not hold, so a CanBeDeleted write that changed nothing '
            + 'could not be told from a MERGE that does not land on this field');
  } else if (!unsealed) {
    voidAll(WRITE_ROWS,
            'the column is not in a known state, so a CanBeDeleted write cannot be attributed');
  } else {
    await observeWrite('field.sealed.canbedeleted-write-while-unsealed',
                       { CanBeDeleted: false }, 'unsealed');
    const resealed = await writeSealed('field.sealed.fixture-reseal-written', true);
    if (resealed) {
      await observeWrite('field.sealed.canbedeleted-write-while-sealed',
                         { CanBeDeleted: true }, 'sealed');
    } else {
      voidAll(['field.sealed.canbedeleted-write-while-sealed'],
              'the column could not be sealed again, so the write was not sent at a sealed column');
    }
    await observeWrite('field.sealed.both-properties-in-one-merge',
                       { Sealed: false, CanBeDeleted: false }, 'in whichever state the pair found it');
  }

  // ---- POSITIVE CONTROL: the delete path works at all -------------------
  const madeWitness = (await readField(WITNESS)) === null
    ? await createTextColumn(WITNESS)
    : { ok: true, status: 'present', text: 'already present' };
  let witnessGone = false;
  let removeWitness = { ok: false, status: 0, text: 'not attempted' };
  if (madeWitness.ok) {
    removeWitness = await deleteField(WITNESS);
    witnessGone = (await readField(WITNESS)) === null;
  }
  record('field.sealed.control-plain-column-deleted', Q.control,
         witnessGone ? 'PASS' : 'FAIL',
         `creating '${WITNESS}' answered ${short(madeWitness)}; DELETE answered `
         + `${short(removeWitness)}; the column ${witnessGone ? 'no longer reads back' : 'still reads back'}`);
  if (!witnessGone) {
    voidAll(DELETE_ROWS,
            'a never-sealed column could not be deleted either, so a refusal below would say '
            + 'nothing about the seal');
    return report();
  }

  // ---- The delete attempts, one per state ------------------------------
  if (!await writeSealed('field.sealed.fixture-sealed-for-delete', true)) {
    voidAll(DELETE_ROWS.slice(1),
            'the column could not be sealed, so the delete attempts were not made in a known state');
    return report();
  }
  const removedWhileSealed = await observeDelete('field.sealed.delete-while-sealed', 'sealed');

  if (!removedWhileSealed) {
    record('field.sealed.fixture-subject-restored', Q.restored, 'NOT APPLICABLE',
           'the sealed delete attempt left the column in place, so nothing had to be rebuilt');
  } else {
    const rebuilt = await createTextColumn(SUBJECT);
    const back = await readField(SUBJECT);
    record('field.sealed.fixture-subject-restored', Q.restored,
           back === null ? 'FAIL' : 'PASS',
           `the sealed delete removed the column; recreating it answered ${short(rebuilt)} and it `
           + `reads ${describeField(back)}`);
    if (back === null) {
      voidAll(['field.sealed.fixture-unsealed-for-delete', 'field.sealed.delete-while-unsealed'],
              'the column could not be rebuilt, so the unsealed delete had no subject');
      return report();
    }
  }

  if (!await writeSealed('field.sealed.fixture-unsealed-for-delete', false)) {
    voidAll(['field.sealed.delete-while-unsealed'],
            'the column could not be unsealed, so the second delete was not made on an unsealed column');
    return report();
  }
  await observeDelete('field.sealed.delete-while-unsealed', 'unsealed');

  return report();
})();
