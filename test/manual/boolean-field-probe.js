/**
 * dbml-sharepoint PROBE: HOW IS A YES/NO COLUMN CREATED OVER REST?
 *
 * ONE QUESTION:
 *   Which spelling does the AddField endpoint accept for a Boolean column
 *   (FieldTypeKind 8), and once such a column exists, can it be indexed and
 *   given a default?
 *
 * REVISION: 68d2de89
 *
 * WHY: on 2026-09-06 a live deploy stopped part-way through provisioning the
 * tool-owned change log. `POST .../fields` answered HTTP 400 on the ninth of
 * the list's ten declared columns, and that create loop stops on the first
 * failure, so the tenth was never attempted. Eight columns landed, and every
 * one of them is Text (SP.FieldText, FieldTypeKind 2) or DateTime
 * (SP.FieldDateTime, FieldTypeKind 4); both of those types succeeded more
 * than once in the same loop. The column that failed is the only Boolean in
 * the set. `analysis/sidecars.py` declares it and the phase POSTs it as:
 *
 *   {"__metadata": {"type": "SP.FieldBoolean"}, "Title": "IsCurrent",
 *    "FieldTypeKind": 8, "Description": "Whether this row is the current
 *    one for its key."}
 *
 * `Indexed: true` is part of that declaration and not part of that body:
 * `deploy/_logging.js.j2` strips it before the POST and asserts it with the
 * field MERGE `deploy/_indexes.js.j2` uses, so it is not a candidate cause
 * of the 400 and is asked here as its own question instead.
 *
 * WHY THE ANSWER MATTERS BEYOND ONE COLUMN. IsCurrent is indexed because the
 * type-2 close reads `$filter=ChangeKey eq '...' and IsCurrent eq true`, and
 * both sides of an AND have to be indexed for that filter to survive the
 * 5,000-item list view threshold. A change log gains a row per change
 * forever, so an unindexable Boolean there is not a cosmetic loss.
 *
 * WHAT THIS PROBE MUST NOT ASSERT. This repository already spells the type
 * two ways. `generators/jsgen.py` maps Boolean to `SP.Field`, and it has
 * been provisioning columns against live tenants for months;
 * `analysis/sidecars.py` sends `SP.FieldBoolean`. That disagreement makes
 * `SP.FieldBoolean` a suspect and not a finding. No row here asserts that a
 * create is refused or accepted. Each records the status and the message
 * SharePoint returned. A probe asserting the refusal would report a harness
 * failure the day the platform changed, and a probe asserting the success
 * would kill itself the moment the suspicion turned out to be right, which
 * is the failure mode AGENTS.md names.
 *
 * THE ONE VALUE THAT IS ASSERTED is `FieldTypeKind` reading back as 8, and
 * only when deciding which create route won the right to answer the index
 * and default questions. A column that was accepted and is not a Boolean
 * would answer those two about something else while the transcript said
 * otherwise, which is worse than no answer. `multilookup-probe.js` draws
 * the same line, for the same reason, around `AllowMultipleValues`.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`, under the `field` surface and its new
 * `boolean` scope. The scope is new because the six type scopes already
 * there (`multichoice`, `multilookup`, `lookup`, `person`, `note`, `date`)
 * name column types, and Yes/No is the type this is about.
 *
 *   field.boolean.fixture-scratch-list      does a scratch list this probe
 *       owns exist for the routes to add columns to?
 *   field.boolean.control-text-create       POSITIVE CONTROL: does an
 *       SP.FieldText create with FieldTypeKind 2, the shape that succeeded
 *       eight times in the failing deploy, apply and read back here? Without
 *       it, a run where every create is refused reads the same as a run
 *       where only the Boolean is.
 *   field.boolean.control-text-indexed      POSITIVE CONTROL: does
 *       `Indexed: true` by field MERGE apply and read back on that text
 *       column? Without it, "a Boolean cannot be indexed" cannot be told
 *       from "nothing can be indexed on this list".
 *   field.boolean.fieldboolean-entity-type  OBSERVE: what does the endpoint
 *       answer to the exact body the change log sends?
 *   field.boolean.spfield-entity-type       OBSERVE: what does it answer to
 *       the same column declared `SP.Field` with FieldTypeKind 8, the
 *       spelling `jsgen` uses, and what do TypeAsString, FieldTypeKind and
 *       InternalName read back as?
 *   field.boolean.addfieldasxml-type-boolean OBSERVE: what does
 *       `createfieldasxml` answer to `<Field Type="Boolean"/>`, and what
 *       does the column read back as?
 *   field.boolean.indexed-property          OBSERVE: does the winning
 *       column take `Indexed: true`, and does it read back true?
 *   field.boolean.default-value-spelling    OBSERVE: does a Boolean column
 *       accept `DefaultValue`, in the create body and by MERGE, and in
 *       which spelling?
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the scratch list exists and this probe
 *   created it (fixture); a text column create applies and is visible to the
 *   same field read the observations use (create control); an index MERGE
 *   applies and reads back on that text column (index control).
 *   Observes (recorded, never asserted): the status, refusal classification
 *   and `error.message.value` of each of the three create routes; what the
 *   accepted columns read back as; whether an index MERGE on a Boolean is
 *   accepted and whether it sticks; what `DefaultValue` reads back as for
 *   each spelling written.
 *
 * THE MESSAGE IS THE FINDING. Every create records
 * `error.message.value` verbatim, not a classification of it. "HTTP 400" is
 * what the deploy already reported and it is what left the cause open.
 *
 * SCOPE OF CLAIMS: one tenant, one site, one scratch list, as Site Owner,
 * at one moment. A spelling accepted here is evidence about this tenant. It
 * is not evidence about a list somebody else built under a policy, and a
 * route that lands here is not a promise about the next release.
 *
 * WHAT IS NOT ASKED. Whether a Boolean column accepts a
 * `ValidationFormula`. `jsgen._COLUMN_VALIDATION_UNSUPPORTED_FIELD_KINDS`
 * deliberately excludes kind 8 and says why, and settling it needs its own
 * fixture rather than a row bolted onto this one.
 *
 * HOW TO RUN
 *   1. Open the sandbox site you own.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true (CLEANUP = true recycles a
 *      leftover scratch list first; a clean fixture needs a list carrying
 *      none of a previous run's columns), paste again.
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
  log('INFO', 'probe revision 68d2de89. Quote this when reporting results.');

  const SCRATCH = 'dbmlsp Probe BooleanField';
  // Ownership is the DESCRIPTION, never the title, which is the rule
  // `_probe_list_fixture_v1.js.j2` states for the other harness. A
  // same-title list this probe did not create is refused rather than
  // recycled: the probe may only ever touch objects it made.
  const OWNERSHIP_DESCRIPTION =
    'dbml-sharepoint boolean-field probe scratch list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${SCRATCH}')`;
  const fieldsPath = `${listPath}/fields`;

  // The change log's own Description for IsCurrent, carried by both JSON
  // routes so that the only difference between them is the entity type name.
  const DESC = 'Whether this row is the current one for its key.';
  const CONTROL_COL = 'ProbeControlText';
  const SUBTYPE_COL = 'IsCurrent';
  const BASETYPE_COL = 'IsCurrentSpField';
  const XML_COL = 'IsCurrentXml';
  const DEFAULT_COL = 'IsCurrentDefault';

  const Q_FIXTURE = 'fixture: a scratch list this probe owns exists for the routes to add columns to';
  const Q_CONTROL_CREATE = 'control: does an SP.FieldText create with FieldTypeKind 2, the shape that succeeded eight times in the failing deploy, apply and read back on this list?';
  const Q_CONTROL_INDEX = 'control: does Indexed:true by field MERGE apply and read back on that text column?';
  const Q_SUBTYPE = 'observe: what does the AddField endpoint answer to the exact body the change log sends, __metadata type SP.FieldBoolean with FieldTypeKind 8?';
  const Q_BASETYPE = 'observe: what does it answer to the same column declared SP.Field with FieldTypeKind 8, and what do TypeAsString, FieldTypeKind and InternalName read back as?';
  const Q_XML = 'observe: what does createfieldasxml answer to <Field Type="Boolean"/>, and what does the column read back as?';
  const Q_INDEX = 'observe: does a Boolean column take Indexed:true by field MERGE, and does Indexed read back true?';
  const Q_DEFAULT = 'observe: does a Boolean column accept DefaultValue, in the create body and by MERGE, and in which spelling?';

  expect('field.boolean.fixture-scratch-list', Q_FIXTURE);
  expect('field.boolean.control-text-create', Q_CONTROL_CREATE);
  expect('field.boolean.control-text-indexed', Q_CONTROL_INDEX);
  expect('field.boolean.fieldboolean-entity-type', Q_SUBTYPE);
  expect('field.boolean.spfield-entity-type', Q_BASETYPE);
  expect('field.boolean.addfieldasxml-type-boolean', Q_XML);
  expect('field.boolean.indexed-property', Q_INDEX);
  expect('field.boolean.default-value-spelling', Q_DEFAULT);

  // Voided together when the create control fails: a refusal then says
  // nothing about the Boolean, because nothing certifies that this list
  // takes a column at all.
  const AFTER_CREATE_CONTROL = ['field.boolean.control-text-indexed',
                                'field.boolean.fieldboolean-entity-type',
                                'field.boolean.spfield-entity-type',
                                'field.boolean.addfieldasxml-type-boolean',
                                'field.boolean.indexed-property',
                                'field.boolean.default-value-spelling'];

  if (!CONFIRMED) {
    log('INFO', `Would create a scratch list '${SCRATCH}' on ${WEB}, add one text`);
    log('INFO', 'column to it and index that column (the two controls), then try three');
    log('INFO', 'ways of creating a Yes/No column on the same list: the SP.FieldBoolean');
    log('INFO', 'body the change log sends, the same column as SP.Field, and');
    log('INFO', 'createfieldasxml with <Field Type="Boolean"/>. It would record each');
    log('INFO', 'status and error message verbatim, then ask whether the column that');
    log('INFO', 'exists can be indexed and given a default. The scratch list is');
    log('INFO', 'recycled on the way out.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${SCRATCH}' would be RECYCLED first, and only if it`);
      log('INFO', 'carries this probe\'s ownership description.');
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
  // A SharePoint error message can quote the request URL, and the recorded
  // evidence must not name the tenant. The scheme and host are replaced with
  // [TENANT] wherever they appear, case-insensitively, leaving the path.
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

  // ---- Transport --------------------------------------------------------
  // Verbose OData, because every body below carries __metadata and the
  // harness's default nometadata content type makes SharePoint answer 400
  // on the transport rather than on the field, which would answer this
  // probe's questions with the probe's own bug.
  const VERBOSE = {
    'Accept': 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const postVerbose = async (path, body, extraHeaders = {}) => {
    let res;
    try {
      const digest = await getDigest();
      res = await fetch(`${WEB}/_api/${path}`, {
        method: 'POST',
        headers: { ...VERBOSE, 'X-RequestDigest': digest, ...extraHeaders },
        body: JSON.stringify(body),
      });
    } catch (err) {
      return { ok: false, status: 0, text: String(err) };
    }
    return { ok: res.ok, status: res.status, text: await res.text() };
  };

  // The message, which is the finding, rather than a classification of it.
  // Verbose spells the error {error: {code, message: {lang, value}}} and
  // nometadata spells it {'odata.error': {...}}; both are read, and the raw
  // text is kept when neither parses, because a plain-text refusal is still
  // the answer.
  const errorMessage = (text) => {
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { return String(text).slice(0, 500); }
    const err = (parsed && (parsed.error || parsed['odata.error'])) || null;
    const message = err && err.message;
    const value = message && (typeof message === 'string' ? message : message.value);
    return value ? String(value) : String(text).slice(0, 500);
  };

  const FIELD_SELECT = 'InternalName,Title,TypeAsString,FieldTypeKind,Indexed,DefaultValue';
  const fieldPath = (name) => `${fieldsPath}/getbyinternalnameortitle('${name}')`;
  const readField = async (name) => {
    const r = await spGet(`${fieldPath(name)}?$select=${FIELD_SELECT}`);
    return readFailed(r) ? null : r.body;
  };

  // The shipped spelling: deploy/_indexes.js.j2 sends this body and these
  // headers for every declared index, so a refusal here is about the column
  // rather than about a request shape nothing sends.
  const mergeField = (name, patch) => postVerbose(
    fieldPath(name),
    { __metadata: { type: 'SP.Field' }, ...patch },
    { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' },
  );

  const show = (value) => (value === undefined ? '(absent)' : JSON.stringify(value));
  const qOf = (id) => RESULTS.find((row) => row.id === id).question;
  const recordVoid = (id, evidence) =>
    record(id, qOf(id), 'NOT ESTABLISHED', evidence, 'void');

  // What a create route did, in one sentence, with the message verbatim.
  // A non-refusal failure (401, 403, 408, 429) is about who is asking or
  // about the moment, so it leaves the question open rather than answering
  // it, which is why isRefusal decides the head.
  const outcomeOf = (attempt) => {
    if (attempt.sent.ok) return attempt.back === null ? 'NOT ESTABLISHED' : 'ACCEPTED';
    return isRefusal(attempt.sent.status) ? 'REFUSED' : 'NOT ESTABLISHED';
  };
  const evidenceOf = (attempt, description) => {
    if (!attempt.sent.ok) {
      return `${description}: HTTP ${attempt.sent.status}`
        + `${isRefusal(attempt.sent.status)
          ? ' (a refusal: the server rejecting what was sent)'
          : ' (NOT a refusal: about who is asking, or about the moment)'}`
        + `. Message: ${redact(errorMessage(attempt.sent.text))}`;
    }
    if (attempt.back === null) {
      return `${description}: the create answered HTTP ${attempt.sent.status} but the `
        + 'column could not be read back, so what was created is unknown';
    }
    return `${description}: the create answered HTTP ${attempt.sent.status}; the column `
      + `reads back InternalName=${show(attempt.back.InternalName)}, `
      + `TypeAsString=${show(attempt.back.TypeAsString)}, `
      + `FieldTypeKind=${show(attempt.back.FieldTypeKind)}`;
  };

  // The marker an abort carries when the fixture never built, stripped off
  // again by the handler so the log line reads as a sentence.
  const FIXTURE_ABORT = 'fixture: ';

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
    // ---- fixture-scratch-list -------------------------------------------
    const pre = await spGet(`${listPath}?$select=Id,Description`);
    if (pre.ok) {
      const description = (pre.body && pre.body.Description) || '';
      if (description !== OWNERSHIP_DESCRIPTION) {
        record('field.boolean.fixture-scratch-list', Q_FIXTURE, 'FAIL',
               `a list named '${SCRATCH}' exists and does not carry this probe's exact `
               + 'ownership description, so it is not one this probe created. Refusing '
               + 'to modify it. Rename it, or run this probe on a site that does not '
               + 'have one.');
        throw new Error(FIXTURE_ABORT + 'a foreign list holds the scratch title');
      }
      if (!CLEANUP) {
        record('field.boolean.fixture-scratch-list', Q_FIXTURE, 'FAIL',
               `a scratch list from an earlier run of this probe is still standing and `
               + 'CLEANUP is off. Its columns would answer this run\'s questions.');
        throw new Error(FIXTURE_ABORT + 'set CLEANUP = true so the leftover list is recycled first');
      }
      await resetList(SCRATCH);
      if ((await spGet(`${listPath}?$select=Id`)).ok) {
        record('field.boolean.fixture-scratch-list', Q_FIXTURE, 'FAIL',
               `CLEANUP did not remove the earlier scratch list '${SCRATCH}'.`);
        throw new Error(FIXTURE_ABORT + 'the leftover scratch list could not be recycled');
      }
    }
    const digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: SCRATCH,
      BaseTemplate: 100,
      Description: OWNERSHIP_DESCRIPTION,
    }, digest);
    if (!made.ok) {
      record('field.boolean.fixture-scratch-list', Q_FIXTURE, 'FAIL',
             `create refused with HTTP ${made.status}: ${redact(made.text).slice(0, 300)}`);
      throw new Error(FIXTURE_ABORT + 'the scratch list create was refused');
    }
    created = true;
    if (!(await spGet(`${listPath}?$select=Id`)).ok) {
      record('field.boolean.fixture-scratch-list', Q_FIXTURE, 'FAIL',
             `created '${SCRATCH}' but the read-back failed`);
      throw new Error(FIXTURE_ABORT + 'the scratch list did not read back after create');
    }
    record('field.boolean.fixture-scratch-list', Q_FIXTURE, 'PASS',
           `created '${SCRATCH}' carrying this probe's ownership description (read back OK)`);

    // ---- control-text-create --------------------------------------------
    // The type that succeeded eight times in the deploy that failed, sent
    // through the same helper the Boolean routes use.
    const textSent = await postVerbose(fieldsPath, {
      __metadata: { type: 'SP.FieldText' },
      Title: CONTROL_COL,
      FieldTypeKind: 2,
      MaxLength: 255,
      Description: 'Positive control for the boolean-field probe.',
    });
    const textBack = textSent.ok ? await readField(CONTROL_COL) : null;
    const createControlOk = textSent.ok && textBack !== null
      && textBack.InternalName === CONTROL_COL;
    record('field.boolean.control-text-create', Q_CONTROL_CREATE,
           createControlOk ? 'PASS' : 'FAIL',
           createControlOk
             ? `an SP.FieldText create answered HTTP ${textSent.status} and '${CONTROL_COL}' `
               + 'reads back, so the transport, the digest and the field read are all good '
               + 'on this list'
             : evidenceOf({ sent: textSent, back: textBack },
                          'the SP.FieldText control'));

    if (!createControlOk) {
      for (const id of AFTER_CREATE_CONTROL) {
        recordVoid(id, 'control-text-create failed, so nothing certifies that this list '
          + 'takes a column at all and a refusal below would say nothing about the type');
      }
      return report();
    }

    // ---- control-text-indexed -------------------------------------------
    const textIndexSent = await mergeField(CONTROL_COL, { Indexed: true });
    const textIndexBack = textIndexSent.ok ? await readField(CONTROL_COL) : null;
    const indexControlOk = textIndexSent.ok && textIndexBack !== null
      && textIndexBack.Indexed === true;
    record('field.boolean.control-text-indexed', Q_CONTROL_INDEX,
           indexControlOk ? 'PASS' : 'FAIL',
           indexControlOk
             ? `Indexed:true on '${CONTROL_COL}' answered HTTP ${textIndexSent.status} and `
               + 'reads back true, so the index method works on this list'
             : `Indexed:true on '${CONTROL_COL}' answered HTTP ${textIndexSent.status}`
               + `${textIndexSent.ok
                 ? `, and Indexed reads back ${show(textIndexBack && textIndexBack.Indexed)}`
                 : `. Message: ${redact(errorMessage(textIndexSent.text))}`}`);

    // ---- fieldboolean-entity-type ---------------------------------------
    // The exact body from analysis/sidecars.py, Indexed stripped the way the
    // phase strips it, so this is the request that answered 400 on 2026-09-06.
    const subtype = { sent: await postVerbose(fieldsPath, {
      __metadata: { type: 'SP.FieldBoolean' },
      Title: SUBTYPE_COL,
      FieldTypeKind: 8,
      Description: DESC,
    }) };
    subtype.back = subtype.sent.ok ? await readField(SUBTYPE_COL) : null;
    record('field.boolean.fieldboolean-entity-type', Q_SUBTYPE, outcomeOf(subtype),
           evidenceOf(subtype, 'the change log\'s own body, __metadata type '
             + 'SP.FieldBoolean with FieldTypeKind 8'));

    // ---- spfield-entity-type --------------------------------------------
    // The same column, differing only in the entity type name, which is the
    // spelling generators/jsgen.py has been sending.
    const basetype = { sent: await postVerbose(fieldsPath, {
      __metadata: { type: 'SP.Field' },
      Title: BASETYPE_COL,
      FieldTypeKind: 8,
      Description: DESC,
    }) };
    basetype.back = basetype.sent.ok ? await readField(BASETYPE_COL) : null;
    record('field.boolean.spfield-entity-type', Q_BASETYPE, outcomeOf(basetype),
           evidenceOf(basetype, '__metadata type SP.Field with FieldTypeKind 8'));

    // ---- addfieldasxml-type-boolean --------------------------------------
    // Options: 8 is AddFieldInternalNameHint, the value every createfieldasxml
    // call in this repository sends. No Description attribute: a refusal here
    // has to be about the type, and an attribute the schema may not take
    // would be a second possible cause.
    const xml = { sent: await postVerbose(`${fieldsPath}/createfieldasxml`, {
      parameters: {
        SchemaXml: `<Field Type="Boolean" DisplayName="${XML_COL}" Name="${XML_COL}"/>`,
        Options: 8,
      },
    }) };
    xml.back = xml.sent.ok ? await readField(XML_COL) : null;
    record('field.boolean.addfieldasxml-type-boolean', Q_XML, outcomeOf(xml),
           evidenceOf(xml, 'createfieldasxml with <Field Type="Boolean"/>'));

    // ---- Which route won -------------------------------------------------
    // Declaration order, so the body the deploy actually sends gets first
    // claim on the two questions below if it turns out to work. FieldTypeKind
    // is the one observed value asserted, and only here: see the header.
    const CANDIDATES = [
      { column: SUBTYPE_COL, route: 'the SP.FieldBoolean body', json: 'SP.FieldBoolean',
        attempt: subtype },
      { column: BASETYPE_COL, route: 'the SP.Field body', json: 'SP.Field',
        attempt: basetype },
      { column: XML_COL, route: 'createfieldasxml', json: null, attempt: xml },
    ];
    const winner = CANDIDATES.find(
      (c) => c.attempt.back !== null && c.attempt.back.FieldTypeKind === 8) || null;
    const routeSummary = CANDIDATES.map(
      (c) => `${c.route}: ${outcomeOf(c.attempt)}`).join('; ');
    if (winner) {
      log('INFO', `${winner.route} produced a column reading back FieldTypeKind 8; the `
        + 'index and default questions are asked of it.');
    }

    // ---- indexed-property ------------------------------------------------
    if (!indexControlOk) {
      recordVoid('field.boolean.indexed-property',
        'control-text-indexed failed, so a refusal here would say nothing about the '
        + 'column type. Routes recorded: ' + routeSummary);
    } else if (winner === null) {
      record('field.boolean.indexed-property', Q_INDEX, 'ABORTED',
        'no create route produced a column reading back FieldTypeKind 8, so there was '
        + 'no Boolean to index. Routes recorded: ' + routeSummary);
    } else {
      const indexSent = await mergeField(winner.column, { Indexed: true });
      const indexBack = indexSent.ok ? await readField(winner.column) : null;
      const stuck = indexBack !== null && indexBack.Indexed === true;
      const head = indexSent.ok
        ? (indexBack === null
          ? 'NOT ESTABLISHED'
          : (stuck ? 'INDEXED' : 'ACCEPTED BUT DID NOT STICK'))
        : (isRefusal(indexSent.status) ? 'REFUSED' : 'NOT ESTABLISHED');
      // The verbatim message goes LAST, so nothing this probe writes runs on
      // after a SharePoint sentence that already ends in punctuation.
      record('field.boolean.indexed-property', Q_INDEX, head,
        `Indexed:true on '${winner.column}' (created by ${winner.route}) answered HTTP `
        + `${indexSent.status}`
        + (indexSent.ok
          ? `, and Indexed reads back ${show(indexBack && indexBack.Indexed)}`
          : '')
        + `. The same MERGE on the text control read back `
        + `${show(textIndexBack.Indexed)}.`
        + (indexSent.ok ? '' : ` Message: ${redact(errorMessage(indexSent.text))}`));
    }

    // ---- default-value-spelling ------------------------------------------
    // Two halves. The create half asks the question the deploy asks, because
    // jsgen puts DefaultValue in the create body ('1' or '0', from
    // _bool_default_to_sp). It needs a JSON route, so it is skipped and said
    // to be skipped when only the XML route produced a column. The MERGE half
    // asks the same of a spelling the field schema uses in prose, 'true'.
    if (winner === null) {
      record('field.boolean.default-value-spelling', Q_DEFAULT, 'ABORTED',
        'no create route produced a column reading back FieldTypeKind 8, so there was '
        + 'no Boolean to give a default to. Routes recorded: ' + routeSummary);
    } else {
      let createHalf = `not asked: ${winner.route} is the only route that produced a `
        + 'Boolean and it carries no JSON create body';
      let mergeTarget = winner.column;
      if (winner.json !== null) {
        const withDefault = await postVerbose(fieldsPath, {
          __metadata: { type: winner.json },
          Title: DEFAULT_COL,
          FieldTypeKind: 8,
          DefaultValue: '1',
          Description: DESC,
        });
        const defaultBack = withDefault.ok ? await readField(DEFAULT_COL) : null;
        createHalf = `create carrying DefaultValue '1' under ${winner.json}: HTTP `
          + `${withDefault.status}`
          + (withDefault.ok
            ? `, DefaultValue reads back ${show(defaultBack && defaultBack.DefaultValue)}`
            : `. Message: ${redact(errorMessage(withDefault.text))}`);
        if (defaultBack !== null) mergeTarget = DEFAULT_COL;
      }
      const mergedDefault = await mergeField(mergeTarget, { DefaultValue: 'true' });
      const mergedBack = mergedDefault.ok ? await readField(mergeTarget) : null;
      const mergeHalf = `MERGE of DefaultValue 'true' on '${mergeTarget}': HTTP `
        + `${mergedDefault.status}`
        + (mergedDefault.ok
          ? `, DefaultValue reads back ${show(mergedBack && mergedBack.DefaultValue)}`
          : `. Message: ${redact(errorMessage(mergedDefault.text))}`);
      record('field.boolean.default-value-spelling', Q_DEFAULT, 'RECORDED',
        `${createHalf} || ${mergeHalf}`);
    }
  } catch (err) {
    const message = redact(String((err && err.message) || err));
    if (message.indexOf(FIXTURE_ABORT) === 0) {
      // The fixture row was recorded FAIL above; the rows that were never
      // asked keep the harness default and stay open for a clean re-run.
      log('INFO', `${message.slice(FIXTURE_ABORT.length)} The unasked rows stay open.`);
    } else {
      log('FAIL', `probe aborted with an uncaught error: ${message.slice(0, 240)}`);
    }
  } finally {
    if (created) await recycleScratch();
  }

  return report();
})();
