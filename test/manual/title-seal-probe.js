/**
 * dbml-sharepoint PROBE: CAN A LIST'S BUILT-IN TITLE EVER BE SEALED?
 *
 * ONE QUESTION:
 *   Is there any route by which the built-in Title column of a list comes to
 *   carry Sealed = true, and does any live list on this site have one?
 *
 * REVISION: 7a65b1bb
 *
 * WHY: 32f5600 (2026-07-27, "a sealed built-in Title no longer makes a site
 * un-deployable") added a whole branch for this state. PREPARE probes Title
 * and unseals it if it is already sealed; PROTECTION re-seals exactly the set
 * PREPARE recorded; `syntheticTitleField` carries `seal: true` to answer the
 * impostor guard. The commit message is explicit that the state was
 * reproduced in a NEW MOCK rather than found on a site:
 *
 *   "Reproduced first: the new adopted-site harness produces exactly
 *    'Existing field APP_Project.Title is sealed; expected an unsealed
 *    declared field' on all three lists"
 *
 * That harness seeds `Sealed: true` in its own `titleState`. It is, as far as
 * this repository's evidence goes, the only place a sealed Title has ever
 * existed.
 *
 * Then on 2026-09-07 test/manual/title-rename-probe.js asked a neighbouring
 * question and got an answer that puts the branch in doubt:
 *
 *   field.title.sealed-rename: MERGE of Sealed:true onto the built-in Title:
 *   HTTP 400 (a refusal). Message: "Operation is not valid due to the current
 *   state of the object."
 *
 * If nothing can seal a Title, that branch is unreachable, and unreachable
 * code that guards a live-site failure mode is worse than absent: it reads as
 * a handled case. If something CAN, the branch is right and the route is
 * worth recording beside it.
 *
 * WHAT THIS PROBE MUST NOT ASSERT. No row asserts that a route works or is
 * refused, and no row asserts what the census will find. The 400 above is a
 * suspicion, not a finding: it was one route, with one entity type, on one
 * fresh list. Each row records the status, the message and what reads back.
 *
 * THE ONE VALUE THAT IS ASSERTED is the control: that a column this probe
 * created DOES take Sealed:true and read it back on this list. Without it,
 * every refusal below is a statement about the list, the site or the
 * identity rather than about Title, and the census would be measuring a
 * tenant that seals nothing.
 *
 * WHAT IT DELIBERATELY DOES NOT ASK. Whether the WEB-level Title site column
 * accepts a seal. That object is shared by every list in the site collection
 * and a probe has no business writing to it; the read below is as far as this
 * goes, and it is enough to say whether the platform ships it sealed.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`, under the `field` surface and the `title`
 * scope that title-rename-probe.js introduced.
 *
 *   field.title.seal-fixture-list        does a scratch list this probe owns
 *       exist, on base template 100, with a built-in Title to work on?
 *   field.title.seal-control-declared    POSITIVE CONTROL: does a column this
 *       probe created take Sealed:true by field MERGE and read it back? This
 *       is what earns the right to read a refusal on Title as being about
 *       Title.
 *   field.title.seal-merge-spfield       OBSERVE: the shipped shape. What does
 *       MERGE {__metadata: SP.Field, Sealed: true} answer on the built-in
 *       Title, and what does Sealed read back as? This is the exact request
 *       that answered 400 on 2026-09-07, asked again so this probe stands on
 *       its own evidence.
 *   field.title.seal-merge-spfieldtext   OBSERVE: the same write declared as
 *       SP.FieldText, which is what Title actually is. A refusal that turns
 *       on the entity type rather than on the column is the single most
 *       likely reason the shipped shape failed, and it is one line apart.
 *   field.title.seal-schemaxml           OBSERVE: the field's own SchemaXml,
 *       re-sent with Sealed="TRUE" added. Sealed is a schema attribute before
 *       it is a REST property, so this asks the question in the form the
 *       platform stores it.
 *   field.title.seal-web-site-column     OBSERVE (read only): what do Sealed,
 *       FromBaseType, CanBeDeleted and ReadOnlyField read as on the WEB-level
 *       Title site column? If the platform ships that one sealed while every
 *       list's copy is unsealed, then seal does not descend, and that is the
 *       answer to how a list Title could ever have one.
 *   field.title.seal-census              OBSERVE (read only): across the
 *       visible lists on this site, what does Sealed read as on each built-in
 *       Title, and on which BaseTemplate? The empirical half. A single sealed
 *       one makes the branch real; none across a site this tool has deployed
 *       to is the strongest evidence available that it is not. The template
 *       travels with the verdict because WHICH lists carry one is the
 *       finding: a generic list (100) and a document library (101) are
 *       different answers about different objects.
 *
 * WHAT IT WRITES. One scratch list, recycled on the way out, and two columns
 * plus seal attempts on that list only. Every other request is a GET. It
 * never enumerates or modifies anything it did not create, apart from reading
 * list and field properties for the census.
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
  log('INFO', 'probe revision 7a65b1bb. Quote this when reporting results.');

  const SCRATCH = 'dbmlsp Probe TitleSeal';
  // Ownership is the DESCRIPTION, never the title. A same-title list this
  // probe did not create is refused rather than recycled: the probe may only
  // ever modify objects it made.
  const OWNERSHIP_DESCRIPTION =
    'dbml-sharepoint title-seal probe scratch list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${SCRATCH}')`;
  const fieldsPath = `${listPath}/fields`;

  const CONTROL_COL = 'ProbeControlText';
  // How many lists the census reads at most. A site with hundreds would
  // otherwise turn a read-only question into a long run; the answer this
  // wants is "does ANY list have one", and a bounded sweep that says how far
  // it got answers that honestly.
  //
  // Raised from 40 after the 2026-09-07 run capped out at 40 of 43 and left
  // three lists unasked, which is exactly the shape that hides the one
  // counterexample a census exists to find.
  const CENSUS_LIMIT = 250;

  const Q_FIXTURE = 'fixture: a scratch list this probe owns exists, on base template 100, with a built-in Title to work on';
  const Q_CONTROL = 'control: does a column this probe created take Sealed:true by field MERGE and read it back on this list?';
  const Q_SPFIELD = 'observe: what does MERGE {__metadata: SP.Field, Sealed: true} answer on the built-in Title, and what does Sealed read back as?';
  const Q_SPFIELDTEXT = 'observe: what does the same write declared as SP.FieldText, which is what Title actually is, answer?';
  const Q_SCHEMAXML = 'observe: what does re-sending the field\'s own SchemaXml with Sealed="TRUE" added answer, and does Sealed read back true?';
  const Q_WEBCOLUMN = 'observe: what do Sealed, FromBaseType, CanBeDeleted and ReadOnlyField read as on the WEB-level Title site column?';
  const Q_CENSUS = 'observe: across the visible lists on this site, what does Sealed read as on each built-in Title?';

  expect('field.title.seal-fixture-list', Q_FIXTURE);
  expect('field.title.seal-control-declared', Q_CONTROL);
  expect('field.title.seal-merge-spfield', Q_SPFIELD);
  expect('field.title.seal-merge-spfieldtext', Q_SPFIELDTEXT);
  expect('field.title.seal-schemaxml', Q_SCHEMAXML);
  expect('field.title.seal-web-site-column', Q_WEBCOLUMN);
  expect('field.title.seal-census', Q_CENSUS);

  // Voided together when the control fails: a refusal on Title would then be
  // about the list, the site or the identity, and the census would be
  // measuring a tenant that seals nothing rather than a Title that cannot be
  // sealed. The two read-only rows survive, because a GET does not depend on
  // this site accepting a seal from this account.
  const AFTER_CONTROL = ['field.title.seal-merge-spfield',
                         'field.title.seal-merge-spfieldtext',
                         'field.title.seal-schemaxml'];

  if (!CONFIRMED) {
    log('INFO', `Would create a scratch list '${SCRATCH}' on ${WEB}, add one text`);
    log('INFO', 'column and seal it (the control), then try three ways of sealing the');
    log('INFO', "list's built-in Title: the shipped SP.Field MERGE, the same write as");
    log('INFO', 'SP.FieldText, and the field\'s own SchemaXml with Sealed="TRUE". It');
    log('INFO', 'would record each status and message verbatim. It then READS, and');
    log('INFO', 'does not write, the web-level Title site column and the built-in');
    log('INFO', `Title of up to ${CENSUS_LIMIT} visible lists on this site. The scratch`);
    log('INFO', 'list is recycled on the way out.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${SCRATCH}' would be RECYCLED first, and only if it`);
      log('INFO', 'carries this probe\'s ownership description.');
    } else {
      log('INFO', 'CLEANUP is off: a leftover list from a previous run would answer');
      log('INFO', 'this run\'s questions, so the probe REFUSES to measure on one.');
      log('INFO', 'Set CLEANUP = true for a clean run.');
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

  // Sealed is in the list because it is what this probe is about; the
  // shared helper's default set does not carry it, and readField would
  // otherwise answer undefined for every seal question.
  const FIELD_SELECT = 'InternalName,Title,TypeAsString,FieldTypeKind,Indexed,DefaultValue,Sealed';
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

  // The marker an abort carries when the fixture never built, stripped off
  // again by the handler so the log line reads as a sentence.
  const FIXTURE_ABORT = 'fixture: ';

  const headOf = (sent) => {
    if (sent.ok) return 'ACCEPTED';
    return isRefusal(sent.status) ? 'REFUSED' : 'NOT ESTABLISHED';
  };
  const sentence = (sent, description) => `${description}: HTTP ${sent.status}`
    + (sent.ok ? '' : `${isRefusal(sent.status)
      ? ' (a refusal: the server rejecting what was sent)'
      : ' (NOT a refusal: about who is asking, or about the moment)'}`
      + `. Message: ${redact(errorMessage(sent.text))}`);

  const TITLE_SELECT = 'InternalName,Title,Sealed,FromBaseType,CanBeDeleted,'
    + 'ReadOnlyField,TypeAsString';
  const titlePathOf = (path) => `${path}/fields/getbyinternalnameortitle('Title')`;
  const readTitleOf = async (path, select) => {
    const r = await spGet(`${titlePathOf(path)}?$select=${select || TITLE_SELECT}`);
    return readFailed(r) ? null : r.body;
  };
  const sealShape = (f) => (f === null
    ? 'the field could not be read back'
    : `Sealed=${show(f.Sealed)}, FromBaseType=${show(f.FromBaseType)}, `
      + `CanBeDeleted=${show(f.CanBeDeleted)}, ReadOnlyField=${show(f.ReadOnlyField)}`);

  // A seal attempt against the built-in Title, one entity type per call. The
  // readback is what decides the row: a 200 that does not stick answers the
  // question differently from a 200 that does, and only one of those is a
  // route.
  const trySeal = async (metadataType) => {
    const sent = await postVerbose(
      titlePathOf(listPath),
      { __metadata: { type: metadataType }, Sealed: true },
      { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' },
    );
    return { sent, back: await readTitleOf(listPath) };
  };
  const sealEvidence = (attempt, description) =>
    `${sentence(attempt.sent, description)}; afterwards ${sealShape(attempt.back)}`;

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

  // ---- The two read-only rows ------------------------------------------
  // Run BEFORE the fixture, and outside its try/catch, because neither one
  // depends on a scratch list existing. A site that refuses the list create
  // can still answer both, and those answers are most of what this probe is
  // for.
  const webTitle = await spGet(
    `web/fields/getbyinternalnameortitle('Title')?$select=${TITLE_SELECT},Group`);
  if (readFailed(webTitle)) {
    record('field.title.seal-web-site-column', Q_WEBCOLUMN, 'NOT ESTABLISHED',
           `the web-level Title site column could not be read: HTTP ${webTitle.status}`);
  } else {
    record('field.title.seal-web-site-column', Q_WEBCOLUMN, 'RECORDED',
           `the site collection's Title site column reads `
           + `${sealShape(webTitle.body)}, Group=${show(webTitle.body.Group)}`);
  }

  const listing = await spGet('web/lists?$select=Title,Hidden,BaseTemplate&$top=5000');
  if (readFailed(listing)) {
    record('field.title.seal-census', Q_CENSUS, 'NOT ESTABLISHED',
           `the site's lists could not be enumerated: HTTP ${listing.status}`);
  } else {
    const all = (listing.body && listing.body.value) || [];
    const visible = all.filter((l) => l.Hidden !== true);
    const looked = visible.slice(0, CENSUS_LIMIT);
    const sealedOnes = [];
    const unreadable = [];
    const unsealedTemplates = Object.create(null);
    let unsealed = 0;
    for (const list of looked) {
      const field = await readTitleOf(
        `web/lists/getbytitle('${encodeURIComponent(list.Title).replace(/'/g, "''")}')`);
      if (field === null) { unreadable.push(list.Title); continue; }
      // BaseTemplate travels with the verdict. The 2026-09-07 run reported
      // four sealed Titles by NAME (Documents, Form Templates, Site Assets,
      // Style Library) and every one of them reads as a document library, but
      // the row carried no template, so that was an inference from four names
      // rather than a measurement. 100 is a generic list; a library is 101
      // and its relatives.
      const where = `${list.Title} (BaseTemplate ${list.BaseTemplate})`;
      if (field.Sealed === true) {
        sealedOnes.push(where);
      } else {
        unsealed += 1;
        unsealedTemplates[list.BaseTemplate] =
          (unsealedTemplates[list.BaseTemplate] || 0) + 1;
      }
    }
    // Titles are named only when SEALED, and that is the whole reason this
    // row can be quoted: an unsealed list contributes a count, a sealed one
    // is the finding and has to be identifiable. A site name is not a tenant
    // name; see the redaction note in the harness above.
    record('field.title.seal-census', Q_CENSUS,
           sealedOnes.length ? 'SEALED FOUND' : 'NONE SEALED',
           `${visible.length} visible list(s) on this site, ${looked.length} read`
           + `${visible.length > looked.length
             ? ` (capped at ${CENSUS_LIMIT}; re-run with a higher cap to finish)` : ''}`
           + `: ${sealedOnes.length} with Sealed=true`
           + `${sealedOnes.length ? ` (${sealedOnes.join(', ')})` : ''}, `
           + `${unsealed} with Sealed=false`
           + ` (by BaseTemplate: ${Object.keys(unsealedTemplates).sort()
             .map((t) => `${t}x${unsealedTemplates[t]}`).join(' ') || 'none'})`
           + `${unreadable.length ? `, ${unreadable.length} unreadable` : ''}`);
  }

  try {
    // ---- seal-fixture-list ------------------------------------------------
    const pre = await spGet(`${listPath}?$select=Id,Description`);
    if (pre.ok) {
      const description = (pre.body && pre.body.Description) || '';
      if (description !== OWNERSHIP_DESCRIPTION) {
        record('field.title.seal-fixture-list', Q_FIXTURE, 'FAIL',
               `a list named '${SCRATCH}' exists and does not carry this probe's exact `
               + 'ownership description, so it is not one this probe created. Refusing '
               + 'to modify it. Rename it, or run this probe on a site that does not '
               + 'have one.');
        throw new Error(FIXTURE_ABORT + 'a foreign list holds the scratch title');
      }
      if (!CLEANUP) {
        record('field.title.seal-fixture-list', Q_FIXTURE, 'FAIL',
               'a scratch list from an earlier run of this probe is still standing and '
               + 'CLEANUP is off. Its Title may already carry a seal this run is '
               + 'supposed to be trying to apply.');
        throw new Error(FIXTURE_ABORT + 'set CLEANUP = true so the leftover list is recycled first');
      }
      await resetList(SCRATCH);
      if ((await spGet(`${listPath}?$select=Id`)).ok) {
        record('field.title.seal-fixture-list', Q_FIXTURE, 'FAIL',
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
      record('field.title.seal-fixture-list', Q_FIXTURE, 'FAIL',
             `create refused with HTTP ${made.status}: ${redact(made.text).slice(0, 300)}`);
      throw new Error(FIXTURE_ABORT + 'the scratch list create was refused');
    }
    created = true;
    const fresh = await readTitleOf(listPath);
    if (fresh === null) {
      record('field.title.seal-fixture-list', Q_FIXTURE, 'FAIL',
             `created '${SCRATCH}' but its built-in Title could not be read back`);
      throw new Error(FIXTURE_ABORT + 'the built-in Title did not read back after create');
    }
    record('field.title.seal-fixture-list', Q_FIXTURE, 'PASS',
           `created '${SCRATCH}'; its built-in Title reads ${sealShape(fresh)}`);

    // ---- seal-control-declared -------------------------------------------
    const controlSent = await postVerbose(fieldsPath, {
      __metadata: { type: 'SP.FieldText' },
      Title: CONTROL_COL,
      FieldTypeKind: 2,
      MaxLength: 255,
      Description: 'Positive control for the title-seal probe.',
    });
    let controlOk = false;
    if (!controlSent.ok) {
      record('field.title.seal-control-declared', Q_CONTROL, headOf(controlSent),
             sentence(controlSent, `creating the control column '${CONTROL_COL}'`));
    } else {
      const sealed = await mergeField(CONTROL_COL, { Sealed: true });
      const back = sealed.ok ? await readField(CONTROL_COL) : null;
      controlOk = sealed.ok && back !== null && back.Sealed === true;
      record('field.title.seal-control-declared', Q_CONTROL,
             controlOk ? 'PASS' : headOf(sealed),
             `${sentence(sealed, `MERGE of Sealed:true onto the probe-created column `
               + `'${CONTROL_COL}'`)}`
             + (back === null ? '; the column could not be read back'
               : `; Sealed reads back ${show(back.Sealed)}`));
    }
    if (!controlOk) {
      for (const id of AFTER_CONTROL) {
        recordVoid(id, 'not asked: a column this probe created did not take a seal on '
          + 'this list, so a refusal on the built-in Title would be about the list, the '
          + 'site or the identity rather than about Title.');
      }
      throw new Error(FIXTURE_ABORT + 'the positive control did not seal');
    }

    // ---- seal-merge-spfield ----------------------------------------------
    const asField = await trySeal('SP.Field');
    record('field.title.seal-merge-spfield', Q_SPFIELD, headOf(asField.sent),
           sealEvidence(asField, 'MERGE of Sealed:true declared as SP.Field, the shape '
             + 'deploy/_indexes.js.j2 and the field reconcile both send'));

    // ---- seal-merge-spfieldtext ------------------------------------------
    const asText = await trySeal('SP.FieldText');
    record('field.title.seal-merge-spfieldtext', Q_SPFIELDTEXT, headOf(asText.sent),
           sealEvidence(asText, 'MERGE of Sealed:true declared as SP.FieldText, which is '
             + 'the type the built-in Title actually is'));

    // ---- seal-schemaxml ---------------------------------------------------
    // The field's OWN SchemaXml, with one attribute added, so the only
    // difference between what is sent and what the platform already holds is
    // the thing being asked about.
    const withXml = await readTitleOf(listPath, 'SchemaXml');
    const xml = withXml === null ? null : withXml.SchemaXml;
    if (typeof xml !== 'string' || xml.indexOf('<Field ') !== 0) {
      record('field.title.seal-schemaxml', Q_SCHEMAXML, 'NOT ESTABLISHED',
             'the field\'s SchemaXml could not be read, or did not start with a '
             + `<Field element, so there was nothing to re-send: ${show(xml)}`);
    } else if (/\bSealed\s*=/i.test(xml)) {
      // Nothing to add, and overwriting an existing attribute would be a
      // different question from adding one.
      record('field.title.seal-schemaxml', Q_SCHEMAXML, 'RECORDED',
             'not attempted: the field\'s own SchemaXml already carries a Sealed '
             + `attribute, so there was nothing to add. It reads: ${redact(xml).slice(0, 300)}`);
    } else {
      const sealedXml = xml.replace('<Field ', '<Field Sealed="TRUE" ');
      const sent = await postVerbose(
        titlePathOf(listPath),
        { __metadata: { type: 'SP.FieldText' }, SchemaXml: sealedXml },
        { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' },
      );
      const back = await readTitleOf(listPath);
      record('field.title.seal-schemaxml', Q_SCHEMAXML, headOf(sent),
             `${sentence(sent, 'MERGE of the field\'s own SchemaXml with Sealed="TRUE" '
               + 'added')}; afterwards ${sealShape(back)}`);
    }
  } catch (err) {
    const message = redact(String((err && err.message) || err));
    if (message.indexOf(FIXTURE_ABORT) === 0) {
      log('INFO', `${message.slice(FIXTURE_ABORT.length)} The unasked rows stay open.`);
    } else {
      log('FAIL', `probe aborted with an uncaught error: ${message.slice(0, 240)}`);
    }
  } finally {
    if (created) await recycleScratch();
  }

  return report();
})();
