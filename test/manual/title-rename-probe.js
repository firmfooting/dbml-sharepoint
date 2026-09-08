/**
 * dbml-sharepoint PROBE: CAN THE BUILT-IN TITLE COLUMN BE RENAMED OVER REST?
 *
 * ONE QUESTION:
 *   Does a MERGE of a new `Title` property onto a list's built-in Title field
 *   change its display name, leave its internal name alone, and leave the
 *   things that address it by either name still working?
 *
 * REVISION: 709c786d
 *
 * WHY: issue #330 found that `display_names.overrides[<Entity>].Title` was
 * accepted by validation and reached three consumers (the form body section
 * field list, the view column width map and the Power Query rename step)
 * while never reaching the column, so a bundle referenced a display title the
 * deploy did not create. #426 closed it by REFUSING the override with a named
 * finding, `display_title_on_title_column`, and stripping the five family
 * declarations that already carried one. The decision comment gives the
 * reason for choosing refusal over implementing the rename:
 *
 *   "since whether the built-in Title accepts a MERGE rename is unmeasured"
 *
 * This probe measures it. A positive answer is what would let the refusal be
 * replaced by the rename; a negative one settles the refusal permanently and
 * the finding's prose can cite a run instead of an absence.
 *
 * WHAT MAKES TITLE DIFFERENT FROM EVERY OTHER COLUMN. The tool renames a
 * declared column by creating it under its internal name and MERGEing the
 * display title afterwards, which has been running against live tenants for
 * months. Title is not created by the tool at all: it arrives with the base
 * template, it belongs to the list's content type, and `generators/jsgen.py`
 * routes it to its own patch object. Microsoft Learn documents `Field.Title`
 * with a setter and `Field.InternalName` with none, so a rename cannot move
 * the internal name; it does not say whether the built-in Title on a base
 * template accepts the write at all, which is the part that is unmeasured.
 *
 * WHAT THIS PROBE MUST NOT ASSERT. No row asserts that the rename succeeds or
 * that it is refused. Each records the status and the message SharePoint
 * returned, and the values the field reads back as. A probe asserting the
 * refusal would report a harness failure the day the platform changed; a
 * probe asserting the success would kill itself the moment the suspicion
 * turned out to be right, which is the failure mode AGENTS.md names.
 *
 * THE ONE VALUE THAT IS ASSERTED is the fixture: that a scratch list this
 * probe owns exists, and that a column this probe CREATED takes a rename on
 * it. Without that control, a refusal on Title cannot be told from a list, a
 * site or an identity that refuses every rename, and every row after it would
 * be read as evidence about Title when it was evidence about the tenant.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`, under the `field` surface and its new
 * `title` scope. The scope is new because the existing eight name column
 * types and one names the list object; the built-in Title is a column that
 * is neither declared nor of a type this tool chooses.
 *
 *   field.title.fixture-scratch-list      does a scratch list this probe owns
 *       exist, on base template 100, so it has a built-in Title to rename?
 *   field.title.control-declared-rename   POSITIVE CONTROL: does a column
 *       this probe created take a display-title MERGE and read back renamed
 *       with its InternalName unchanged? Without it, a refusal on Title reads
 *       the same as a list that refuses every rename.
 *   field.title.builtin-rename            OBSERVE: what does a MERGE of
 *       {Title: "<new>"} on the built-in Title answer, and what do Title,
 *       InternalName and StaticName read back as afterwards?
 *   field.title.addressable-after-rename  OBSERVE: does
 *       getbyinternalnameortitle('Title') still resolve the column? The
 *       deploy addresses Title that way on every run, so a rename that
 *       breaks the address breaks reconciliation rather than a label.
 *   field.title.item-roundtrip            OBSERVE: does an item POST carrying
 *       `Title` still create a row, and does the value read back? The wire
 *       contract for every flow and every deploy write is the internal name;
 *       if a rename moved it, this is where it shows.
 *   field.title.formula-old-name          OBSERVE: does a calculated column
 *       whose formula says [Title] still save after the rename? This is the
 *       hazard the build has today: SharePoint resolves formulas by DISPLAY
 *       name, jsgen's display map is built from the declared fields only, and
 *       `programme-governance` ships two formulas referencing [Title].
 *   field.title.formula-new-name          OBSERVE: does the same formula save
 *       when it references the NEW display name instead? The pair is the
 *       finding: which spelling a formula must use after a rename decides
 *       whether the display map has to carry Title.
 *   field.title.sealed-rename             OBSERVE: with Sealed:true set on
 *       the built-in Title, is the rename refused, and does the unseal,
 *       rename, re-seal sequence the deploy already runs for this column
 *       leave it renamed and sealed?
 *
 * WHAT IT WRITES. One scratch list, recycled on the way out, carrying this
 * probe's ownership description. Two columns on it that the probe creates,
 * plus renames and calculated-column creates against that list only. It never
 * enumerates or touches anything else, and it never runs against a list it
 * did not create.
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
  log('INFO', 'probe revision 709c786d. Quote this when reporting results.');

  const SCRATCH = 'dbmlsp Probe TitleRename';
  // Ownership is the DESCRIPTION, never the title, which is the rule
  // `_probe_list_fixture_v1.js.j2` states for the other harness. A
  // same-title list this probe did not create is refused rather than
  // recycled: the probe may only ever touch objects it made.
  const OWNERSHIP_DESCRIPTION =
    'dbml-sharepoint title-rename probe scratch list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${SCRATCH}')`;
  const fieldsPath = `${listPath}/fields`;

  // The control column, created by this probe under an internal name and
  // renamed the same way the deploy renames every declared column.
  const CONTROL_COL = 'ProbeControlText';
  const CONTROL_DISPLAY = 'Probe Control Renamed';
  // The new display title for the built-in Title. Deliberately two words
  // with a space: a single token could pass by resolving as an internal
  // name somewhere and hide the question.
  const NEW_TITLE = 'Risk Statement';
  const OLD_FORMULA_COL = 'ProbeFormulaOldName';
  const NEW_FORMULA_COL = 'ProbeFormulaNewName';
  const ITEM_VALUE = 'probe item written by internal name';

  const Q_FIXTURE = 'fixture: a scratch list this probe owns exists, on base template 100, so it has a built-in Title to rename';
  const Q_CONTROL = 'control: does a column this probe created take a display-title MERGE and read back renamed with its InternalName unchanged?';
  const Q_RENAME = 'observe: what does a MERGE of a new Title onto the built-in Title answer, and what do Title, InternalName and StaticName read back as?';
  const Q_ADDRESS = 'observe: does getbyinternalnameortitle(\'Title\') still resolve the column after the rename, which is how the deploy addresses it?';
  const Q_ITEM = 'observe: does an item POST carrying Title still create a row after the rename, and does the value read back?';
  const Q_FORMULA_OLD = 'observe: does a calculated column whose formula says [Title] still save after the rename?';
  const Q_FORMULA_NEW = 'observe: does the same formula save when it references the new display name instead?';
  const Q_SEALED = 'observe: with Sealed:true on the built-in Title, is the rename refused, and does unseal, rename, re-seal leave it renamed and sealed?';

  expect('field.title.fixture-scratch-list', Q_FIXTURE);
  expect('field.title.control-declared-rename', Q_CONTROL);
  expect('field.title.builtin-rename', Q_RENAME);
  expect('field.title.addressable-after-rename', Q_ADDRESS);
  expect('field.title.item-roundtrip', Q_ITEM);
  expect('field.title.formula-old-name', Q_FORMULA_OLD);
  expect('field.title.formula-new-name', Q_FORMULA_NEW);
  expect('field.title.sealed-rename', Q_SEALED);

  // Voided together when the control fails: a refusal on Title then says
  // nothing about Title, because nothing certifies that this list takes a
  // rename at all.
  const AFTER_CONTROL = ['field.title.builtin-rename',
                         'field.title.addressable-after-rename',
                         'field.title.item-roundtrip',
                         'field.title.formula-old-name',
                         'field.title.formula-new-name',
                         'field.title.sealed-rename'];
  // Voided together when the rename itself never applied: every one of them
  // asks what is true AFTER a rename, so on a list whose Title still says
  // 'Title' they would answer about the unrenamed column and read as
  // evidence about the renamed one.
  const AFTER_RENAME = ['field.title.addressable-after-rename',
                        'field.title.item-roundtrip',
                        'field.title.formula-old-name',
                        'field.title.formula-new-name'];

  if (!CONFIRMED) {
    log('INFO', `Would create a scratch list '${SCRATCH}' on ${WEB}, add one text`);
    log('INFO', 'column to it and rename that column by field MERGE (the control),');
    log('INFO', `then MERGE a new display title '${NEW_TITLE}' onto the list's`);
    log('INFO', 'built-in Title and record the status, the message and what Title,');
    log('INFO', 'InternalName and StaticName read back as. It would then ask whether');
    log('INFO', 'the column is still addressable by internal name, whether an item');
    log('INFO', 'POST carrying Title still works, which spelling a calculated formula');
    log('INFO', 'must use, and what a sealed Title does. The scratch list is recycled');
    log('INFO', 'on the way out.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${SCRATCH}' would be RECYCLED first, and only if it`);
      log('INFO', 'carries this probe\'s ownership description.');
    } else {
      log('INFO', 'CLEANUP is off: a leftover list carrying a renamed Title from a');
      log('INFO', 'previous run would answer this run\'s questions, so the probe REFUSES');
      log('INFO', 'to measure on one. Set CLEANUP = true for a clean run.');
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

  // The marker an abort carries when the fixture never built, stripped off
  // again by the handler so the log line reads as a sentence.
  const FIXTURE_ABORT = 'fixture: ';

  // One sentence about a write that was either refused or not, with the
  // message verbatim. A non-refusal failure (401, 403, 408, 429) is about
  // who is asking or about the moment, so it leaves the question open rather
  // than answering it, which is why isRefusal decides the head.
  const headOf = (sent) => {
    if (sent.ok) return 'ACCEPTED';
    return isRefusal(sent.status) ? 'REFUSED' : 'NOT ESTABLISHED';
  };
  const sentence = (sent, description) => `${description}: HTTP ${sent.status}`
    + (sent.ok ? '' : `${isRefusal(sent.status)
      ? ' (a refusal: the server rejecting what was sent)'
      : ' (NOT a refusal: about who is asking, or about the moment)'}`
      + `. Message: ${redact(errorMessage(sent.text))}`);

  // Read the built-in Title by its INTERNAL name, which is how the deploy
  // addresses it and the only address a rename could not have changed.
  const TITLE_SELECT = 'InternalName,StaticName,Title,TypeAsString,Sealed';
  const readTitle = async () => {
    const r = await spGet(
      `${fieldsPath}/getbyinternalnameortitle('Title')?$select=${TITLE_SELECT}`);
    return readFailed(r) ? null : r.body;
  };
  const titleShape = (f) => (f === null
    ? 'the field could not be read back'
    : `Title=${show(f.Title)}, InternalName=${show(f.InternalName)}, `
      + `StaticName=${show(f.StaticName)}, Sealed=${show(f.Sealed)}`);

  // A calculated column referencing one spelling of the title column. The
  // formula is the subject; the column is the vehicle, so it is created and
  // its create status IS the answer.
  const addCalculated = (name, reference) => postVerbose(fieldsPath, {
    __metadata: { type: 'SP.FieldCalculated' },
    Title: name,
    FieldTypeKind: 17,
    OutputType: 2,
    Formula: `=CONCATENATE("x",[${reference}])`,
    Description: 'Formula spelling probe. Safe to delete.',
  });

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
        record('field.title.fixture-scratch-list', Q_FIXTURE, 'FAIL',
               `a list named '${SCRATCH}' exists and does not carry this probe's exact `
               + 'ownership description, so it is not one this probe created. Refusing '
               + 'to modify it. Rename it, or run this probe on a site that does not '
               + 'have one.');
        throw new Error(FIXTURE_ABORT + 'a foreign list holds the scratch title');
      }
      if (!CLEANUP) {
        record('field.title.fixture-scratch-list', Q_FIXTURE, 'FAIL',
               'a scratch list from an earlier run of this probe is still standing and '
               + 'CLEANUP is off. Its already-renamed Title would answer this run\'s '
               + 'questions.');
        throw new Error(FIXTURE_ABORT + 'set CLEANUP = true so the leftover list is recycled first');
      }
      await resetList(SCRATCH);
      if ((await spGet(`${listPath}?$select=Id`)).ok) {
        record('field.title.fixture-scratch-list', Q_FIXTURE, 'FAIL',
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
      record('field.title.fixture-scratch-list', Q_FIXTURE, 'FAIL',
             `create refused with HTTP ${made.status}: ${redact(made.text).slice(0, 300)}`);
      throw new Error(FIXTURE_ABORT + 'the scratch list create was refused');
    }
    created = true;
    const beforeTitle = await readTitle();
    if (beforeTitle === null) {
      record('field.title.fixture-scratch-list', Q_FIXTURE, 'FAIL',
             `created '${SCRATCH}' but its built-in Title could not be read back`);
      throw new Error(FIXTURE_ABORT + 'the built-in Title did not read back after create');
    }
    record('field.title.fixture-scratch-list', Q_FIXTURE, 'PASS',
           `created '${SCRATCH}' carrying this probe's ownership description; its `
           + `built-in Title reads back as ${titleShape(beforeTitle)}`);

    // ---- control-declared-rename ----------------------------------------
    // The shipped route: create under the internal name, MERGE the display
    // title afterwards. If this fails, nothing below is about Title.
    const controlSent = await postVerbose(fieldsPath, {
      __metadata: { type: 'SP.FieldText' },
      Title: CONTROL_COL,
      FieldTypeKind: 2,
      MaxLength: 255,
      Description: 'Positive control for the title-rename probe.',
    });
    let controlOk = false;
    if (!controlSent.ok) {
      record('field.title.control-declared-rename', Q_CONTROL, headOf(controlSent),
             sentence(controlSent, `creating the control column '${CONTROL_COL}'`));
    } else {
      const renamed = await mergeField(CONTROL_COL, { Title: CONTROL_DISPLAY });
      const back = renamed.ok ? await readField(CONTROL_COL) : null;
      controlOk = renamed.ok && back !== null
        && back.Title === CONTROL_DISPLAY && back.InternalName === CONTROL_COL;
      record('field.title.control-declared-rename', Q_CONTROL,
             controlOk ? 'PASS' : headOf(renamed),
             `${sentence(renamed, `MERGE of Title '${CONTROL_DISPLAY}' onto the `
               + `probe-created column '${CONTROL_COL}'`)}`
             + (back === null ? '; the column could not be read back'
               : `; it reads back Title=${show(back.Title)}, `
                 + `InternalName=${show(back.InternalName)}`));
    }
    if (!controlOk) {
      for (const id of AFTER_CONTROL) {
        recordVoid(id, 'not asked: a column this probe created did not take a rename on '
          + 'this list, so a result on the built-in Title would be about the list, the '
          + 'site or the identity rather than about Title.');
      }
      throw new Error(FIXTURE_ABORT + 'the positive control did not rename');
    }

    // ---- builtin-rename --------------------------------------------------
    // The same body and headers the deploy sends for a declared rename, so a
    // refusal here is about the column rather than about a request shape
    // nothing sends. SP.Field rather than SP.FieldText: mergeField is the
    // shipped helper and the entity type is its own, separate question.
    const renameSent = await mergeField('Title', { Title: NEW_TITLE });
    const afterRename = await readTitle();
    const renameApplied = renameSent.ok && afterRename !== null
      && afterRename.Title === NEW_TITLE;
    record('field.title.builtin-rename', Q_RENAME, headOf(renameSent),
           `${sentence(renameSent, `MERGE of Title '${NEW_TITLE}' onto the built-in `
             + 'Title')}; afterwards ${titleShape(afterRename)}`);

    if (!renameApplied) {
      for (const id of AFTER_RENAME) {
        recordVoid(id, 'not asked: the rename did not apply, so every question about '
          + 'what is true afterwards would be answered by an unrenamed column.');
      }
    } else {
      // ---- addressable-after-rename -------------------------------------
      const byInternal = await spGet(
        `${fieldsPath}/getbyinternalnameortitle('Title')?$select=${TITLE_SELECT}`);
      const byDisplay = await spGet(
        `${fieldsPath}/getbyinternalnameortitle('${encodeURIComponent(NEW_TITLE)}')`
        + `?$select=${TITLE_SELECT}`);
      record('field.title.addressable-after-rename', Q_ADDRESS,
             byInternal.ok ? 'RECORDED' : headOf({ ok: false, status: byInternal.status, text: '' }),
             `getbyinternalnameortitle('Title') answers HTTP ${byInternal.status}`
             + (byInternal.ok && byInternal.body
               ? `, Title=${show(byInternal.body.Title)}` : '')
             + ` || the same call on the new display name answers HTTP ${byDisplay.status}`
             + (byDisplay.ok && byDisplay.body
               ? `, InternalName=${show(byDisplay.body.InternalName)}` : ''));

      // ---- item-roundtrip -----------------------------------------------
      const itemDigest = await getDigest();
      const wrote = await spPost(`${listPath}/items`, { Title: ITEM_VALUE }, itemDigest);
      let readBack = null;
      if (wrote.ok && wrote.body && wrote.body.Id !== undefined) {
        const got = await spGet(`${listPath}/items(${wrote.body.Id})?$select=Title`);
        readBack = readFailed(got) ? null : got.body.Title;
      }
      record('field.title.item-roundtrip', Q_ITEM, headOf(wrote),
             `${sentence(wrote, 'POST of an item carrying the internal name Title')}`
             + `; the value reads back as ${show(readBack)}`);

      // ---- formula-old-name / formula-new-name --------------------------
      // SharePoint resolves a formula by DISPLAY name. Both spellings are
      // tried because which one saves is the finding, and asking only one
      // would report a refusal without the comparison that gives it meaning.
      const oldSent = await addCalculated(OLD_FORMULA_COL, 'Title');
      record('field.title.formula-old-name', Q_FORMULA_OLD, headOf(oldSent),
             sentence(oldSent, 'creating a calculated column whose formula references '
               + '[Title], the name the column no longer displays'));
      const newSent = await addCalculated(NEW_FORMULA_COL, NEW_TITLE);
      record('field.title.formula-new-name', Q_FORMULA_NEW, headOf(newSent),
             sentence(newSent, `creating a calculated column whose formula references `
               + `[${NEW_TITLE}], the name it now displays`));
    }

    // ---- sealed-rename ---------------------------------------------------
    // Asked whether or not the plain rename applied: a Title that refuses the
    // rename while unsealed and one that refuses it only when sealed are
    // different findings, and the deploy already runs an unseal for this
    // column (deploy/_maintenance_unseal.js.j2).
    const sealed = await mergeField('Title', { Sealed: true });
    if (!sealed.ok) {
      record('field.title.sealed-rename', Q_SEALED, headOf(sealed),
             sentence(sealed, 'MERGE of Sealed:true onto the built-in Title, which this '
               + 'question needs before it can ask anything'));
    } else {
      const sealedRename = await mergeField('Title', { Title: `${NEW_TITLE} Sealed` });
      const afterSealed = await readTitle();
      const unsealed = await mergeField('Title', { Sealed: false });
      const afterUnseal = unsealed.ok
        ? await mergeField('Title', { Title: `${NEW_TITLE} Unsealed` }) : null;
      const resealed = unsealed.ok ? await mergeField('Title', { Sealed: true }) : null;
      const finalShape = await readTitle();
      record('field.title.sealed-rename', Q_SEALED, headOf(sealedRename),
             `${sentence(sealedRename, 'MERGE of a new Title while Sealed:true')}`
             + `; the field then reads ${titleShape(afterSealed)}`
             + ` || unseal answers HTTP ${unsealed.status}`
             + (afterUnseal === null ? ', so the rename after it was not attempted'
               : `, the rename after it HTTP ${afterUnseal.status}`)
             + (resealed === null ? '' : `, the re-seal HTTP ${resealed.status}`)
             + `; the field finally reads ${titleShape(finalShape)}`);
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
