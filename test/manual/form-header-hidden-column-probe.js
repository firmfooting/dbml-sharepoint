/** ---- dbml-sharepoint PROBE: A FORM HEADER SHOWING A COLUMN HIDDEN FROM THE FORMS ----
 *
 * REVISION: 2d764186
 *
 * QUESTION: when a column is hidden from the Edit and Display forms the way
 * the deploy hides one (a ClientValidationFormula that is true only while
 * [$ID] is empty, so the column shows on New and not on Edit or Display),
 * does a form header formatter that names it still show its value?
 *
 * WHY: a pack hides a flow-written column from the edit form so nobody types
 * it, and wants the value shown in the header beside Status. The deploy never
 * writes ShowInEditForm or ShowInDisplayForm (jsgen.py, _field_reconcile.js.j2).
 * Learn's form configuration page documents the header JSON and [$Field]
 * tokens, not whether a hidden field's value reaches them. The formatter uses
 * no attribute: Learn's formatting syntax reference lists the predefined ones
 * and says an unlisted attribute is an error.
 *
 * TWO PASTES, because a baseline must be seen before the thing under test exists:
 *   MODE = 'baseline'  builds the fixture and writes a formatter holding only a
 *       literal footer. A person records whether the footer shows on each form.
 *   MODE = 'header'    adds the header (a hidden-column line and a visible-Choice
 *       line) to the same formatter. A person records what each form shows.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   text.form-fmt.fixture-hidden-list           a generic list this probe created, read back
 *       with its ownership Description, an item type and its folder URL
 *   text.form-fmt.fixture-hidden-columns        two Choice columns, HiddenResult and ShownResult
 *       (Yes, No), read back with their TypeAsString
 *   text.form-fmt.fixture-hidden-item           the one item, HiddenResult = No, ShownResult = Yes,
 *       read back at the Id the create answered (header mode: the list's only item)
 *   text.form-fmt.control-column-hidden-on-forms HiddenResult's ClientValidationFormula read back
 *       as written; ShownResult carries none
 *   text.form-fmt.control-columns-in-content-type both columns read back as field links of the
 *       default item content type, neither Hidden
 *   text.form-fmt.fixture-footer-baseline       (baseline) the content type's
 *       ClientFormCustomFormatter read back as the footer alone
 *   text.form-fmt.fixture-header-formatter      (header) it read back as the header and the footer
 *
 * OBSERVES (a person's reading, recorded with a screenshot; never asserted)
 *   form.edit-form.footer-baseline-renders, form.display-form.footer-baseline-renders
 *       (baseline) whether the literal footer shows, before any header exists
 *   form.edit-form.header-choice-token-renders, form.display-form.header-choice-token-renders
 *       (header) whether the visible Choice column's line shows its value
 *   form.edit-form.header-hidden-column, form.display-form.header-hidden-column
 *       (header) what the hidden column's line shows
 *
 * HOW TO READ IT: the machine rows settle the fixture and stop; each form row is
 * MANUAL until a person records it.
 *   - Baseline: footer absent means the formatter cannot be shown on that form; stop,
 *     the header run would answer nothing.
 *   - Header, with the baseline footer shown: a footer that is now absent is observed
 *     whole-formatter suppression; a footer shown with no header is observed
 *     whole-header suppression. Both are findings, recorded on the hidden-column row.
 *   - Header rendered: if the visible Choice line is blank, record that on the
 *     choice-token row and the hidden-column row is VOID, since Choice tokens do not
 *     render here at all. Otherwise record what the hidden-column line shows.
 *   - In both modes, HiddenResult still in the form body, or ShownResult missing from
 *     it, voids that form's rows: the hiding or the fixture did not take effect.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again,
 * then open the URLs it prints. Then set MODE = 'header' and paste again. Set
 * CLEANUP to true on a later baseline run to recycle the previous list first; a
 * same-title list without this probe's Description is never touched.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // CLEANUP recycles only this probe's own list, by Id, before the run; it needs CONFIRMED and ALLOW_WRITES too.
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

  // Non-2xx other than 401/403/408/429/503 is the server rejecting the content: this tenant answers refusals 500, not 400.
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 503; // 503: the other documented throttle

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
  //
  // expectedId is OPTIONAL because most callers have no claimed Id to bracket
  // with, and the behaviour without one is unchanged. Supply one and every
  // request below addresses that list Id instead of the title, so a title
  // rebound mid-run cannot redirect the deletes or the recycle onto a list
  // this run never owned.
  //
  // DOCUMENTED: `web/lists(guid'<id>')` is the list resource, and `/items`
  // and `/items(<id>)` hang off it (Working with lists and list items with
  // REST, and the CSOM/REST API index, both checked 2026-09-23).
  // NOT DOCUMENTED: `/recycle` on the by-Id form appears on no Learn page.
  // It is the call this project has live evidence for with only the
  // addressing changed, and an unsupported URL fails visibly here rather
  // than losing somebody's list. One CLEANUP run settles it; see issue #611.
  const resetList = async (title, expectedId = null) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
      return false;
    }
    // An Id that is not a GUID would be spliced into a URL that addresses
    // something else, so it fails closed instead of being sent.
    const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    if (expectedId !== null && !GUID.test(String(expectedId))) {
      log('FAIL', `CLEANUP: '${expectedId}' is not a list Id, so nothing was deleted or `
                  + `recycled under '${title}'.`);
      return false;
    }
    const listPath = expectedId === null
      ? `web/lists/getbytitle('${title}')`
      : `web/lists(guid'${expectedId}')`;
    const found = await spGet(expectedId === null ? listPath : `${listPath}?$select=Id`);
    if (!found.ok) {
      log('INFO', `CLEANUP: no list named '${title}' to remove.`);
      return false;
    }
    // Addressing by Id still gets read back, because every destructive
    // request below rests on this one answer.
    const answeredId = found.body && found.body.Id
      ? String(found.body.Id).replace(/[{}]/g, '').toLowerCase() : null;
    if (expectedId !== null && answeredId !== String(expectedId).toLowerCase()) {
      log('FAIL', `CLEANUP: list ${expectedId} answered as ${answeredId}, so nothing was `
                  + `deleted or recycled under '${title}'.`);
      return false;
    }
    log('INFO', `CLEANUP: removing list '${title}' and its items.`);

    // Items first. Recycling the list takes them with it, but doing this
    // explicitly still clears the data if the list itself cannot be
    // removed. A locked or no-delete list would otherwise leave rows from
    // a previous run answering this run's questions.
    let digest = await getDigest();
    const items = await spGet(`${listPath}/items?$select=Id&$top=5000`);
    const rows = (items.ok && items.body && items.body.value) || [];
    for (const row of rows) {
      digest = await getDigest();
      await spPost(`${listPath}/items(${row.Id})`, {}, digest,
                   { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
    }
    if (rows.length) log('INFO', `CLEANUP: deleted ${rows.length} item(s).`);
    if (rows.length === 5000) {
      log('INFO', 'CLEANUP: hit the 5000-row page limit; re-run to clear the rest.');
    }

    digest = await getDigest();
    const gone = await spPost(`${listPath}/recycle`, {}, digest);
    // The Id is named where there is one, because a repair by hand off the
    // title would go to whatever the title resolves to now.
    const which = expectedId === null ? `'${title}'` : `'${title}' (list ${expectedId})`;
    if (gone.ok) {
      log('OK', `CLEANUP: recycled list ${which}. It is restorable from the recycle bin.`);
    } else {
      log('FAIL', `CLEANUP: could not recycle ${which}: HTTP ${gone.status} ${gone.text.slice(0, 200)}`);
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

  // ---- Fixtures (#559) -----------------------------------------------
  // Why a response carries no reading, or null when it does. Learn documents
  // 429 and 503 as the two SharePoint Online throttle statuses.
  const unanswered = (r) => {
    if (r.ok) {
      return r.body !== null && typeof r.body === 'object'
        ? null : `answered HTTP ${r.status} with no payload`;
    }
    if (r.status === 429 || r.status === 503) return `was throttled (HTTP ${r.status})`;
    if (r.status === 408) return 'timed out (HTTP 408)';
    if (r.status === 401 || r.status === 403) return `was not authorised (HTTP ${r.status})`;
    return isRefusal(r.status) ? `was refused (HTTP ${r.status})` : `did not answer (HTTP ${r.status})`;
  };

  // A voided row keeps its question and is counted apart from open and answered.
  const voidDependents = (ids, reason) => {
    for (const id of ids) {
      const row = RESULTS.find((r) => r.id === id);
      record(id, row ? row.question : id, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // `read` resolves to a harness response ({ ok, status, body }). `declared`
  // maps each property the measurement depends on to a value or a predicate.
  // PASS needs every one read back; otherwise FAIL, void `dependents`, false.
  const establishFixture = async (id, read, declared, dependents) => {
    const row = RESULTS.find((r) => r.id === id);
    const question = row ? row.question : id;
    const problems = [];
    const seen = [];
    let got = null;
    let threw = false;
    try {
      got = await read();
    } catch (err) {
      threw = true;
      problems.push(`the read threw: ${err && err.message ? err.message : String(err)}`);
    }
    if (!threw) {
      const silent = got && typeof got === 'object' ? unanswered(got) : 'returned no response';
      if (silent) problems.push(`the read ${silent}`);
    }
    if (!problems.length) {
      for (const [name, want] of Object.entries(declared)) {
        if (!Object.prototype.hasOwnProperty.call(got.body, name) || got.body[name] === undefined) {
          problems.push(`${name} is absent from the payload`);
          continue;
        }
        const value = got.body[name];
        seen.push(`${name}=${JSON.stringify(value)}`);
        const held = typeof want === 'function' ? want(value) === true : value === want;
        if (!held) {
          problems.push(`${name} differs: read ${JSON.stringify(value)}, declared `
            + (typeof want === 'function' ? 'by a predicate it fails' : JSON.stringify(want)));
        }
      }
    }
    if (!problems.length) {
      record(id, question, 'PASS', `read back ${seen.join(', ')}`);
      return true;
    }
    record(id, question, 'FAIL', problems.join('; ') + (seen.length ? `; read ${seen.join(', ')}` : ''));
    voidDependents(dependents, `the fixture ${id} did not hold: ${problems.join('; ')}`);
    return false;
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
  log('INFO', 'probe revision 2d764186. Quote this when reporting results.');

  // ---- The question ----------------------------------------------------
  const MODE = 'baseline'; // 'baseline' first, a person looks, then 'header'
  const BASELINE = MODE === 'baseline';
  const LIST = 'dbml-probe-header-hidden-column';
  // Ownership is the Description, never the title: a same-title list this probe did not make is left alone.
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint form-header-hidden-column probe scratch list. Safe to delete.';
  const HIDDEN = 'HiddenResult';
  const SHOWN = 'ShownResult';
  // No attributes: Learn's formatting syntax reference lists the predefined ones; lines are told apart by their text.
  const HEADER = {
    elmType: 'div',
    children: [
      { elmType: 'div', txtContent: `hidden-column: [$${HIDDEN}]` },
      { elmType: 'div', txtContent: `visible-choice: [$${SHOWN}]` },
    ],
  };
  const FOOTER = { elmType: 'div', txtContent: 'probe-baseline-footer' };
  // The deploy's own encoding: part OBJECTS under *JSONFormatter keys, the whole thing a JSON string.
  const FOOTER_ONLY = JSON.stringify({ footerJSONFormatter: FOOTER });
  const FORMATTER = BASELINE ? FOOTER_ONLY : JSON.stringify({ headerJSONFormatter: HEADER, footerJSONFormatter: FOOTER });
  // What the generator emits for new: true, existing: false (compose_visibility); pinned by a test.
  const HIDE_ON_EXISTING = "=if([$ID] == '', 'true', 'false')";
  const LIST_FIXTURE = 'text.form-fmt.fixture-hidden-list';
  const COLUMNS = 'text.form-fmt.fixture-hidden-columns';
  const ITEM = 'text.form-fmt.fixture-hidden-item';
  const CONTROL = 'text.form-fmt.control-column-hidden-on-forms';
  const LINKS = 'text.form-fmt.control-columns-in-content-type';
  const FORMATTER_FIXTURE = BASELINE ? 'text.form-fmt.fixture-footer-baseline' : 'text.form-fmt.fixture-header-formatter';
  const FORMATTER_QUESTION = BASELINE ? 'the content type reads back the footer-only formatter as written'
    : 'the content type reads back the header and footer formatter as written';
  const BASE_EDIT = 'form.edit-form.footer-baseline-renders';
  const BASE_DISPLAY = 'form.display-form.footer-baseline-renders';
  const TOKEN_EDIT = 'form.edit-form.header-choice-token-renders';
  const TOKEN_DISPLAY = 'form.display-form.header-choice-token-renders';
  const EDIT = 'form.edit-form.header-hidden-column';
  const DISPLAY = 'form.display-form.header-hidden-column';
  const OBSERVED = BASELINE ? [BASE_EDIT, BASE_DISPLAY] : [TOKEN_EDIT, TOKEN_DISPLAY, EDIT, DISPLAY];
  const ALL_AFTER_LIST = [COLUMNS, ITEM, CONTROL, LINKS, FORMATTER_FIXTURE, ...OBSERVED];

  expect('text.form-fmt.fixture-hidden-list', 'the list reads back with its marker, an item type and its folder URL');
  expect('text.form-fmt.fixture-hidden-columns', 'both Choice columns read back as such');
  expect('text.form-fmt.fixture-hidden-item', 'the item reads back with HiddenResult No and ShownResult Yes');
  expect('text.form-fmt.control-column-hidden-on-forms', 'HiddenResult reads back with the hiding formula and ShownResult with none');
  expect('text.form-fmt.control-columns-in-content-type', 'both columns are field links of the default content type and neither is Hidden');
  if (BASELINE) {
    expect('text.form-fmt.fixture-footer-baseline', 'the content type reads back the footer-only formatter as written');
    expect('form.edit-form.footer-baseline-renders', 'whether the literal footer shows on the Edit form before any header exists');
    expect('form.display-form.footer-baseline-renders', 'whether the literal footer shows on the Display form before any header exists');
  } else {
    expect('text.form-fmt.fixture-header-formatter', 'the content type reads back the header and footer formatter as written');
    expect('form.edit-form.header-choice-token-renders', 'whether the visible Choice column shows its value in the Edit form header');
    expect('form.display-form.header-choice-token-renders', 'whether the visible Choice column shows its value in the Display form header');
    expect('form.edit-form.header-hidden-column', 'whether the Edit form header shows the value of a column hidden from the forms');
    expect('form.display-form.header-hidden-column', 'whether the Display form header shows the value of a column hidden from the forms');
  }

  if (!CONFIRMED || !ALLOW_WRITES) {
    log('INFO', BASELINE
      ? `Would create '${LIST}' with two Choice columns and one item, hide ${HIDDEN} from the Edit and Display forms with a formula, and write a footer-only form formatter, on ${WEB}.`
      : `Would add a header naming both columns to the form formatter of '${LIST}' on ${WEB}.`);
    log('INFO', 'Nothing has been sent. Set CONFIRMED = true and ALLOW_WRITES = true to run it.');
    return report();
  }

  const enc = (t) => encodeURIComponent(t.replace(/'/g, "''"));
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const post = async (path, payload, extra = {}) => spPost(path, payload, await getDigest(), { ...VERBOSE, ...extra });
  const reason = (r) => (r.body && r.body.error && r.body.error.message && r.body.error.message.value) || r.text.slice(0, 160);
  const said = (what, r) => log(r.ok ? 'INFO' : 'FAIL', `${what}: HTTP ${r.status}${r.ok ? '' : ` ${reason(r)}`}`);
  const GUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
  const listAt = `web/lists/getbytitle('${enc(LIST)}')`;

  const refuse = (why) => {
    record(LIST_FIXTURE, 'the list reads back with its marker, an item type and its folder URL', 'FAIL', why);
    voidDependents(ALL_AFTER_LIST, 'the list was not established by this run');
    return report();
  };
  let listId = '';
  if (BASELINE) {
    // A by-title read answers an absent list 404; a standing one is recycled only if it carries the marker.
    const before = await spGet(`${listAt}?$select=Id,Description`);
    if (before.status !== 404) {
      if (!before.ok) return refuse(`could not tell whether '${LIST}' already stands: the read ${unanswered(before)}`);
      if (!before.body || before.body.Description !== OWNERSHIP_DESCRIPTION) {
        return refuse(`a list named '${LIST}' exists without this probe's ownership description; refusing to modify it`);
      }
      if (!CLEANUP) return refuse(`'${LIST}' from an earlier run already stands; set CLEANUP to true to recycle it first`);
      // By the Id read with the marker, so a title rebound since cannot redirect the deletes.
      if (!await resetList(LIST, String(before.body.Id).replace(/[{}]/g, ''))) {
        return refuse(`'${LIST}' from an earlier run could not be recycled`);
      }
      const after = await spGet(`${listAt}?$select=Id`);
      if (after.status !== 404) return refuse(`'${LIST}' still answers HTTP ${after.status} after the recycle`);
    }
    const created = await post('web/lists', { __metadata: { type: 'SP.List' }, Title: LIST,
      BaseTemplate: 100, Description: OWNERSHIP_DESCRIPTION });
    said('list create', created);
    // Only a list this run's create answered for is written to, and only by its Id: the title may be another's now.
    listId = created.ok && created.body && created.body.d ? String(created.body.d.Id).replace(/[{}]/g, '') : '';
    if (!GUID.test(listId)) {
      return refuse(`the list create answered HTTP ${created.status} with no list Id; nothing more was written`);
    }
  } else {
    // The header run writes only to the list the baseline run made, found by title and proved by its marker.
    const standing = await spGet(`${listAt}?$select=Id,Description`);
    if (!standing.ok) return refuse(`the baseline list was not read: the read ${unanswered(standing)}`);
    if (!standing.body || standing.body.Description !== OWNERSHIP_DESCRIPTION) {
      return refuse(`'${LIST}' does not carry this probe's ownership description; run MODE = 'baseline' first`);
    }
    listId = String(standing.body.Id).replace(/[{}]/g, '');
    if (!GUID.test(listId)) return refuse('the list read answered no list Id');
  }
  const at = `web/lists(guid'${listId}')`;
  let list = null;
  if (!await establishFixture(LIST_FIXTURE, async () => (list = await spGet(
    `${at}?$select=Description,ListItemEntityTypeFullName,RootFolder/ServerRelativeUrl&$expand=RootFolder`)),
  { Description: OWNERSHIP_DESCRIPTION, ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0,
    RootFolder: (v) => !!v && typeof v.ServerRelativeUrl === 'string' && v.ServerRelativeUrl.startsWith('/') },
  ALL_AFTER_LIST.filter((id) => id !== LIST_FIXTURE))) return report();
  const dependents = (after) => ALL_AFTER_LIST.slice(ALL_AFTER_LIST.indexOf(after) + 1);

  // Options 9 adds the field to the default content type, without which it reaches no form.
  const addField = (schemaXml) => post(`${at}/fields/createfieldasxml`, { parameters: {
    __metadata: { type: 'SP.XmlSchemaFieldCreationInformation' }, SchemaXml: schemaXml, Options: 9 } });
  if (BASELINE) {
    said('choice column create', await addField(`<Field Type='Choice' Name='${HIDDEN}' DisplayName='${HIDDEN}'>`
      + '<CHOICES><CHOICE>Yes</CHOICE><CHOICE>No</CHOICE></CHOICES></Field>'));
    said('control column create', await addField(`<Field Type='Choice' Name='${SHOWN}' DisplayName='${SHOWN}'>`
      + '<CHOICES><CHOICE>Yes</CHOICE><CHOICE>No</CHOICE></CHOICES></Field>'));
  }
  const kindOf = (rows, name) => { const f = (rows || []).find((r) => r && r.InternalName === name); return f && f.TypeAsString; };
  if (!await establishFixture(COLUMNS, () => spGet(`${at}/fields?$select=InternalName,TypeAsString`
    + `&$filter=InternalName eq '${HIDDEN}' or InternalName eq '${SHOWN}'`),
  { value: (rows) => Array.isArray(rows) && kindOf(rows, HIDDEN) === 'Choice' && kindOf(rows, SHOWN) === 'Choice' },
  dependents(COLUMNS))) return report();

  let itemId = null;
  if (BASELINE) {
    const made = await post(`${at}/items`, { __metadata: { type: list.body.ListItemEntityTypeFullName },
      Title: 'dbml probe header', [HIDDEN]: 'No', [SHOWN]: 'Yes' });
    said('item create', made);
    itemId = made.body && made.body.d ? made.body.d.Id : null;
  } else {
    // The baseline run made exactly one item; the header run finds it rather than assuming its Id.
    const items = await spGet(`${at}/items?$select=Id&$top=2`);
    itemId = !unanswered(items) && Array.isArray(items.body.value) && items.body.value.length === 1
      ? items.body.value[0].Id : null;
  }
  if (!await establishFixture(ITEM, () => (Number.isInteger(itemId)
    ? spGet(`${at}/items(${itemId})?$select=Id,${HIDDEN},${SHOWN}`)
    : { ok: false, status: 0, body: null }),
  { Id: itemId, [HIDDEN]: 'No', [SHOWN]: 'Yes' }, dependents(ITEM))) return report();

  // The deploy's own hiding: a ClientValidationFormula (never ShowIn*Form), read back as written.
  const fieldAt = `${at}/fields/getbyinternalnameortitle('${HIDDEN}')`;
  if (BASELINE) {
    said('hide with a formula', await post(fieldAt, { __metadata: { type: 'SP.Field' },
      ClientValidationFormula: HIDE_ON_EXISTING, ClientValidationMessage: '' }, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }));
  }
  // Both columns are read: the control must carry no formula, or its span could be blank for that reason.
  const formulaOf = (rows, name) => { const f = (rows || []).find((r) => r && r.InternalName === name); return f ? f.ClientValidationFormula : undefined; };
  const controlHeld = (rows) => Array.isArray(rows) && formulaOf(rows, HIDDEN) === HIDE_ON_EXISTING
    && [undefined, null, ''].includes(formulaOf(rows, SHOWN)) && rows.some((r) => r && r.InternalName === SHOWN);
  await establishFixture(CONTROL, () => spGet(`${at}/fields?$select=InternalName,ClientValidationFormula`
    + `&$filter=InternalName eq '${HIDDEN}' or InternalName eq '${SHOWN}'`),
  { value: controlHeld }, dependents(CONTROL));

  // The default item content type, as the deploy finds it: an Item-derived type that is not a folder.
  const types = await spGet(`${at}/contenttypes?$select=Name,StringId&$top=100`);
  const itemType = !unanswered(types) && Array.isArray(types.body.value)
    ? types.body.value.find((t) => t && typeof t.StringId === 'string'
      && t.StringId.startsWith('0x01') && !t.StringId.startsWith('0x0120')) : null;
  if (!itemType || typeof itemType.StringId !== 'string') {
    record(FORMATTER_FIXTURE, FORMATTER_QUESTION, 'FAIL',
      unanswered(types) ? `the content type read ${unanswered(types)}` : 'no default item content type answered');
    voidDependents(OBSERVED, 'the content type was not found');
    return report();
  }
  const typeAt = `${at}/contenttypes('${itemType.StringId}')`;
  // Both columns must be on the type's forms: a column not there, or Hidden, has a blank span for that reason.
  const linkOk = (rows, name) => Array.isArray(rows) && rows.some((l) => l && l.Name === name && l.Hidden !== true);
  await establishFixture(LINKS, () => spGet(`${typeAt}/fieldlinks?$select=Name,Hidden&$top=500`),
    { value: (rows) => linkOk(rows, HIDDEN) && linkOk(rows, SHOWN) }, dependents(LINKS));
  const wrote = await post(typeAt, { __metadata: { type: 'SP.ContentType' }, ClientFormCustomFormatter: FORMATTER },
    { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
  said('form formatter write', wrote);
  // The readback, not the write status, says what the type holds: an exact readback stands after an ambiguous write.
  if (!await establishFixture(FORMATTER_FIXTURE, () => spGet(`${typeAt}?$select=ClientFormCustomFormatter`),
    { ClientFormCustomFormatter: FORMATTER }, OBSERVED)) return report();

  const stateOf = (id) => (RESULTS.find((r) => r.id === id) || {}).state;
  // The folder URL the create answered for: the list's title is not its URL, and a link built from it can open another list.
  const forms = `${new URL(WEB).origin}${list.body.RootFolder.ServerRelativeUrl}`;
  const body = 'VOID that form if HiddenResult is still a field in the form body or ShownResult is missing from it. ';
  const open = (form, page) => `Open the item's ${form} form: ${forms}/${page}?ID=${itemId}. Screenshot it. ${body}`;
  for (const [form, page, ids] of [['Edit', 'EditForm.aspx', [BASE_EDIT, TOKEN_EDIT, EDIT]],
    ['Display', 'DispForm.aspx', [BASE_DISPLAY, TOKEN_DISPLAY, DISPLAY]]]) {
    const [base, token, target] = ids;
    if (BASELINE) {
      if (stateOf(base) !== 'void') {
        record(base, `whether the literal footer shows on the ${form} form before any header exists`, 'MANUAL',
          `${open(form, page)}Record whether the line probe-baseline-footer shows. If it does not, stop: the header run would answer nothing.`);
      }
      continue;
    }
    if (stateOf(token) !== 'void') {
      record(token, `whether the visible Choice column shows its value in the ${form} form header`, 'MANUAL',
        `${open(form, page)}Record whether the line "visible-choice:" shows Yes.`);
    }
    if (stateOf(target) !== 'void') {
      record(target, `whether the ${form} form header shows the value of a column hidden from the forms`, 'MANUAL',
        `${open(form, page)}Record the line "hidden-column:" as shown or blank. VOID it if the visible-choice line is blank `
        + '(Choice tokens do not render here). If the baseline footer is now absent, record whole-formatter suppression; '
        + 'if the footer shows with no header, record whole-header suppression.');
    }
  }
  return report();
})();
