/**
 * dbml-sharepoint PROBE: DOES A BLANK NUMBER OPERAND REFUSE THE SAVE
 *
 * REVISION: 82890be5
 *
 * ONE QUESTION:
 *   A save rule comparing a NULLABLE Number column against a limit is stored
 *   as `=[Amount]<=100`. When an item is saved with that column blank, does
 *   SharePoint refuse the save, which turns an optional column into a
 *   required one on a live site and only on a live site, or does it accept
 *   the row?
 *
 * Issue #156 asked this about dates and numbers together. The date half is
 * now closed by construction rather than by measurement: analysis/
 * save_rules.py hoists every column rule that compares a date with the clock
 * onto the LIST rule and wraps it in an `is_null` arm on the way, so no date
 * column in the library was ever exposed to a bare comparison. What is left
 * is the operand type that keeps its rule on the column. Eight numeric call
 * sites carried the unguarded spelling, all eight took the blank arm in one
 * sweep, and `GRANDFATHERED_BLANK_ARMS` is now an empty ratchet. The rule
 * `column_validation_missing_a_blank_arm` fails closed on a new one because
 * the answer here is unknown, which is the only reason it fails closed. This
 * probe is the last open piece of that issue.
 *
 * The formulas are the build's, not a paraphrase. For a `number` column,
 * analysis/condition_rendering.py renders `leq 100` as `=[Amount]<=100` and
 * the `any_of` over `is_null` as `=OR(ISBLANK([Amount]),[Amount]<=100)`,
 * both unquoted, and those two strings are what this probe writes.
 *
 * BOTH PLACEMENTS, because the library writes both. A hoisted rule lands on
 * the list and an operand-bound rule stays on the column, and a rule is not
 * known to behave the same in the two slots. Each cell carries its own
 * over-limit control, so a blank that lands is never confused with a slot
 * that does not enforce anything on this write path.
 *
 * SCOPE AND QUESTIONS
 *   formula.validation.fixture-list-created
 *     A generic list is created (BaseTemplate 100).
 *   formula.validation.fixture-number-column
 *     A Number column created with Required false reads back
 *     TypeAsString Number and Required false. Every row below is about a
 *     blank in a column that is allowed to be blank.
 *   formula.validation.control-missing-column-refused
 *     NEGATIVE CONTROL: an item POST naming a column that does not exist is
 *     REFUSED. Without it, an accepted save below could be the server
 *     ignoring what it was sent.
 *   formula.validation.fixture-no-rule-in-force
 *     Both the column rule and the list rule read back empty before the
 *     first cell, so a refusal in one cell is never a rule left behind by a
 *     previous run.
 *   formula.validation.fixture-bare-column-rule-stored
 *     The COLUMN rule `=[Amount]<=100` is stored and reads back.
 *   formula.validation.control-over-limit-under-bare-column-rule
 *     POSITIVE CONTROL: an item carrying 101 is REFUSED under that rule.
 *     Without it, a blank landing could mean the rule is not enforced on an
 *     item POST at all.
 *   formula.validation.blank-omitted-under-bare-column-rule
 *     THE QUESTION: an item that OMITS the column, under the bare column
 *     rule. Accepted or refused.
 *   formula.validation.blank-null-under-bare-column-rule
 *     The same item with the column sent as null, because a seeded row and a
 *     form save can spell a blank either way.
 *   formula.validation.fixture-guarded-column-rule-stored
 *     The COLUMN rule `=OR(ISBLANK([Amount]),[Amount]<=100)` is stored and
 *     reads back.
 *   formula.validation.control-over-limit-under-guarded-column-rule
 *     POSITIVE CONTROL: 101 is REFUSED under the guarded rule too, so the
 *     guard did not simply switch the rule off.
 *   formula.validation.blank-omitted-under-guarded-column-rule
 *     THE CONTROL FOR THE FIX: the blank arm is what every affected column
 *     now carries, and this is the row that says it behaves as intended
 *     rather than merely differently.
 *   formula.validation.blank-null-under-guarded-column-rule
 *     The same, with the column sent as null.
 *   formula.validation.fixture-column-rule-cleared
 *     The column rule reads back empty before the list cells, so a list-rule
 *     result is never the column rule still firing.
 *   formula.validation.fixture-bare-list-rule-stored
 *     The LIST rule `=[Amount]<=100` is stored and reads back.
 *   formula.validation.control-over-limit-under-bare-list-rule
 *     POSITIVE CONTROL: 101 is REFUSED by the list rule.
 *   formula.validation.blank-omitted-under-bare-list-rule
 *     THE QUESTION, asked of the list slot.
 *   formula.validation.blank-null-under-bare-list-rule
 *     The same, with the column sent as null.
 *   formula.validation.fixture-guarded-list-rule-stored
 *     The LIST rule `=OR(ISBLANK([Amount]),[Amount]<=100)` is stored and
 *     reads back.
 *   formula.validation.control-over-limit-under-guarded-list-rule
 *     POSITIVE CONTROL: 101 is REFUSED by the guarded list rule.
 *   formula.validation.blank-omitted-under-guarded-list-rule
 *     The guarded control, asked of the list slot.
 *   formula.validation.blank-null-under-guarded-list-rule
 *     The same, with the column sent as null.
 *
 * OBSERVED, NEVER ASSERTED
 *   Whether each blank save is accepted or refused, in all four cells, and
 *   the message SharePoint returns when it refuses. Those are the
 *   measurement. The rows the run DEPENDS on are the fixture readbacks (the
 *   column exists and is nullable, each rule reads back as written, each
 *   slot is empty when it should be) and the over-limit controls, and those
 *   are asserted. Asserting the blank outcome would make the probe fail the
 *   moment it answered either way, which looks identical to a broken run.
 *
 * NOT MEASURED HERE
 *   What the modern form does with the same rules. form-validation-probe.js
 *   is the shape for that and it needs a person at a form, where this run is
 *   an item POST end to end. Also not measured: a blank Choice, Text or
 *   Person operand, and whether a rule refuses a blank on an UPDATE that
 *   clears a populated column rather than on a create.
 *
 * MICROSOFT LEARN CITATIONS
 *   Save rules on a column and on a list:
 *     "Field.ValidationFormula Property", "Field.ValidationMessage Property",
 *     "List.ValidationFormula Property", "List.ValidationMessage Property"
 *     (CSOM)
 *   List creation via POST to `web/lists` and item creation via `items`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Required on a column:
 *     "Field.Required Property" (CSOM)
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

  log('INFO', 'probe revision 82890be5. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Blank Operand';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  // Internal name equals display name: created through the same POST to
  // /fields the deploy uses, so it carries no _x0020_ encoding.
  const COL = 'Amount';
  const fieldPath = `${listPath}/fields/getbyinternalnameortitle('${COL}')`;
  const LIMIT = 100;
  const OVER_LIMIT = 101;

  // The two spellings analysis/condition_rendering.py renders for a `number`
  // column, so the probe measures what the build actually writes.
  const BARE = `=[${COL}]<=${LIMIT}`;
  const GUARDED = `=OR(ISBLANK([${COL}]),[${COL}]<=${LIMIT})`;
  const MESSAGE = `dbmlsp probe: ${COL} must be ${LIMIT} or less`;

  const Q = {
    fixture: 'A generic list is created (BaseTemplate 100)',
    column: 'A Number column created with Required false reads back TypeAsString Number and Required false',
    control: 'NEGATIVE CONTROL: an item POST naming a column that does not exist is refused',
    clear: 'Both the column rule and the list rule read back empty before the first cell',
    bareColumnStored: `The COLUMN rule ${BARE} is stored and reads back`,
    bareColumnLimit: `POSITIVE CONTROL: an item carrying ${OVER_LIMIT} is refused under the bare column rule`,
    bareColumnOmitted: 'Does an item that OMITS the column save under the bare column rule',
    bareColumnNull: 'Does an item sending the column as null save under the bare column rule',
    guardedColumnStored: `The COLUMN rule ${GUARDED} is stored and reads back`,
    guardedColumnLimit: `POSITIVE CONTROL: an item carrying ${OVER_LIMIT} is refused under the guarded column rule`,
    guardedColumnOmitted: 'Does an item that OMITS the column save under the guarded column rule',
    guardedColumnNull: 'Does an item sending the column as null save under the guarded column rule',
    columnCleared: 'The column rule reads back empty before the list cells',
    bareListStored: `The LIST rule ${BARE} is stored and reads back`,
    bareListLimit: `POSITIVE CONTROL: an item carrying ${OVER_LIMIT} is refused under the bare list rule`,
    bareListOmitted: 'Does an item that OMITS the column save under the bare list rule',
    bareListNull: 'Does an item sending the column as null save under the bare list rule',
    guardedListStored: `The LIST rule ${GUARDED} is stored and reads back`,
    guardedListLimit: `POSITIVE CONTROL: an item carrying ${OVER_LIMIT} is refused under the guarded list rule`,
    guardedListOmitted: 'Does an item that OMITS the column save under the guarded list rule',
    guardedListNull: 'Does an item sending the column as null save under the guarded list rule',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' on ${WEB} with one nullable Number column '${COL}'.`);
    log('INFO', `Would then store four save rules in turn, ${BARE} and ${GUARDED},`);
    log('INFO', 'each once on the COLUMN and once on the LIST, and after each one save three items:');
    log('INFO', `one carrying ${OVER_LIMIT}, one omitting the column, one sending it as null.`);
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing list would be reused. Its rules are cleared and');
      log('INFO', 'read back before the first cell, so a stale rule is reported rather than obeyed.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('formula.validation.fixture-list-created', Q.fixture);
  expect('formula.validation.fixture-number-column', Q.column);
  expect('formula.validation.control-missing-column-refused', Q.control);
  expect('formula.validation.fixture-no-rule-in-force', Q.clear);
  expect('formula.validation.fixture-bare-column-rule-stored', Q.bareColumnStored);
  expect('formula.validation.control-over-limit-under-bare-column-rule', Q.bareColumnLimit);
  expect('formula.validation.blank-omitted-under-bare-column-rule', Q.bareColumnOmitted);
  expect('formula.validation.blank-null-under-bare-column-rule', Q.bareColumnNull);
  expect('formula.validation.fixture-guarded-column-rule-stored', Q.guardedColumnStored);
  expect('formula.validation.control-over-limit-under-guarded-column-rule', Q.guardedColumnLimit);
  expect('formula.validation.blank-omitted-under-guarded-column-rule', Q.guardedColumnOmitted);
  expect('formula.validation.blank-null-under-guarded-column-rule', Q.guardedColumnNull);
  expect('formula.validation.fixture-column-rule-cleared', Q.columnCleared);
  expect('formula.validation.fixture-bare-list-rule-stored', Q.bareListStored);
  expect('formula.validation.control-over-limit-under-bare-list-rule', Q.bareListLimit);
  expect('formula.validation.blank-omitted-under-bare-list-rule', Q.bareListOmitted);
  expect('formula.validation.blank-null-under-bare-list-rule', Q.bareListNull);
  expect('formula.validation.fixture-guarded-list-rule-stored', Q.guardedListStored);
  expect('formula.validation.control-over-limit-under-guarded-list-rule', Q.guardedListLimit);
  expect('formula.validation.blank-omitted-under-guarded-list-rule', Q.guardedListOmitted);
  expect('formula.validation.blank-null-under-guarded-list-rule', Q.guardedListNull);

  const AFTER_LIST = [
    'formula.validation.fixture-number-column',
    'formula.validation.control-missing-column-refused',
    'formula.validation.fixture-no-rule-in-force',
  ];
  const COLUMN_CELL_IDS = [
    'formula.validation.fixture-bare-column-rule-stored',
    'formula.validation.control-over-limit-under-bare-column-rule',
    'formula.validation.blank-omitted-under-bare-column-rule',
    'formula.validation.blank-null-under-bare-column-rule',
    'formula.validation.fixture-guarded-column-rule-stored',
    'formula.validation.control-over-limit-under-guarded-column-rule',
    'formula.validation.blank-omitted-under-guarded-column-rule',
    'formula.validation.blank-null-under-guarded-column-rule',
  ];
  const LIST_CELL_IDS = [
    'formula.validation.fixture-bare-list-rule-stored',
    'formula.validation.control-over-limit-under-bare-list-rule',
    'formula.validation.blank-omitted-under-bare-list-rule',
    'formula.validation.blank-null-under-bare-list-rule',
    'formula.validation.fixture-guarded-list-rule-stored',
    'formula.validation.control-over-limit-under-guarded-list-rule',
    'formula.validation.blank-omitted-under-guarded-list-rule',
    'formula.validation.blank-null-under-guarded-list-rule',
  ];
  const CLEAR_AND_LIST_IDS = [
    'formula.validation.fixture-column-rule-cleared',
    ...LIST_CELL_IDS,
  ];

  const questionFor = (id) => RESULTS.find((r) => r.id === id).question;
  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, questionFor(id), 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // __metadata is a VERBOSE OData construct, so every field and list write
  // carrying it overrides the harness's default nometadata content type.
  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;

  // SharePoint stores a rule XML-encoded and drops removable brackets, so a
  // byte comparison reports a rule that landed as a write that failed. Both
  // corrections are the ones templates/_formula_canonical.js.j2 makes.
  const canonical = (value) => String(value === null || value === undefined ? '' : value)
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&')
    .replace(/\[([A-Za-z0-9_]+)\]/g, '$1');

  const merge = async (path, payload) => spPost(path, payload, await getDigest(), {
    ...VERBOSE, 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*',
  });

  const setColumnRule = (formula) => merge(fieldPath, {
    __metadata: { type: 'SP.FieldNumber' },
    ValidationFormula: formula,
    ValidationMessage: formula === '' ? '' : MESSAGE,
  });
  const setListRule = (formula) => merge(listPath, {
    __metadata: { type: 'SP.List' },
    ValidationFormula: formula,
    ValidationMessage: formula === '' ? '' : MESSAGE,
  });

  // null means the read itself failed, which is not the same as an empty
  // rule and must never be reported as one.
  const readRule = async (path) => {
    const r = await spGet(`${path}?$select=ValidationFormula`);
    return readFailed(r) ? null : (r.body.ValidationFormula || '');
  };
  const readColumnRule = () => readRule(fieldPath);
  const readListRule = () => readRule(listPath);

  let saved = 0;
  const saveItem = async (body, describe) => {
    saved += 1;
    return spPost(`${listPath}/items`,
                  { Title: `dbmlsp ${describe} ${saved}`, ...body },
                  await getDigest());
  };

  const CELLS = [
    {
      slot: 'column', shape: 'bare', formula: BARE,
      stored: 'formula.validation.fixture-bare-column-rule-stored',
      limit: 'formula.validation.control-over-limit-under-bare-column-rule',
      omitted: 'formula.validation.blank-omitted-under-bare-column-rule',
      nulled: 'formula.validation.blank-null-under-bare-column-rule',
    },
    {
      slot: 'column', shape: 'guarded', formula: GUARDED,
      stored: 'formula.validation.fixture-guarded-column-rule-stored',
      limit: 'formula.validation.control-over-limit-under-guarded-column-rule',
      omitted: 'formula.validation.blank-omitted-under-guarded-column-rule',
      nulled: 'formula.validation.blank-null-under-guarded-column-rule',
    },
    {
      slot: 'list', shape: 'bare', formula: BARE,
      stored: 'formula.validation.fixture-bare-list-rule-stored',
      limit: 'formula.validation.control-over-limit-under-bare-list-rule',
      omitted: 'formula.validation.blank-omitted-under-bare-list-rule',
      nulled: 'formula.validation.blank-null-under-bare-list-rule',
    },
    {
      slot: 'list', shape: 'guarded', formula: GUARDED,
      stored: 'formula.validation.fixture-guarded-list-rule-stored',
      limit: 'formula.validation.control-over-limit-under-guarded-list-rule',
      omitted: 'formula.validation.blank-omitted-under-guarded-list-rule',
      nulled: 'formula.validation.blank-null-under-guarded-list-rule',
    },
  ];

  // One cell: store the rule, prove it bites, then ask the blank twice. The
  // rule readback and the over-limit refusal are what the cell DEPENDS on,
  // so they are asserted; the two blank rows only report what happened.
  const runCell = async (cell) => {
    const write = cell.slot === 'column' ? setColumnRule : setListRule;
    const read = cell.slot === 'column' ? readColumnRule : readListRule;
    const label = `${cell.shape} ${cell.slot} rule`;

    const sent = await write(cell.formula);
    const stored = await read();
    const held = stored !== null && canonical(stored) === canonical(cell.formula);
    record(cell.stored, questionFor(cell.stored), held ? 'PASS' : 'FAIL',
           `MERGE of ${JSON.stringify(cell.formula)} answered ${short(sent)}; `
           + (stored === null
             ? 'the rule did not read back at all'
             : `the ${cell.slot} reads back ${JSON.stringify(stored)}`));
    if (!held) {
      voidAll([cell.limit, cell.omitted, cell.nulled],
              `the ${label} is not in force, so nothing saved under it is about that rule`);
      return;
    }

    const over = await saveItem({ [COL]: OVER_LIMIT }, `${cell.shape}-${cell.slot}-over`);
    const refused = !over.ok && isRefusal(over.status);
    record(cell.limit, questionFor(cell.limit),
           refused ? 'PASS' : (over.ok ? 'FAIL' : 'NOT ESTABLISHED'),
           `an item carrying ${COL}=${OVER_LIMIT} answered ${short(over)}`
           + (over.ok
             ? '. The over-limit value was ACCEPTED, so this slot is not enforcing the rule on an item POST'
             : ''));
    if (!refused) {
      voidAll([cell.omitted, cell.nulled],
              `the ${label} did not refuse ${OVER_LIMIT}, so a blank landing under it says nothing`);
      return;
    }

    const blanks = [
      [cell.omitted, {}, 'omitting the column'],
      [cell.nulled, { [COL]: null }, 'sending the column as null'],
    ];
    for (const [id, body, describe] of blanks) {
      const attempt = await saveItem(body, `${cell.shape}-${cell.slot}-blank`);
      const head = attempt.ok
        ? 'SAVE ACCEPTED'
        : (isRefusal(attempt.status) ? 'SAVE REFUSED' : 'NOT ESTABLISHED');
      record(id, questionFor(id), head,
             `an item ${describe}, under the ${label}, answered ${short(attempt)}`);
    }
  };

  await resetList(LIST);

  const haveList = await spGet(listPath);
  const LIST_DEPENDANTS = [...AFTER_LIST, ...COLUMN_CELL_IDS, ...CLEAR_AND_LIST_IDS];
  const madeList = haveList.ok ? null : await spPost('web/lists', {
    Title: LIST, BaseTemplate: 100,
    Description: 'dbml-sharepoint blank-operand probe list. Safe to delete.',
  }, await getDigest());
  if (madeList !== null && !madeList.ok) {
    record('formula.validation.fixture-list-created', Q.fixture, 'FAIL', short(madeList));
    voidAll(LIST_DEPENDANTS, `fixture incomplete: list creation failed (HTTP ${madeList.status})`);
    return report();
  }
  log('INFO', madeList === null
    ? `reusing an existing list '${LIST}'. Set CLEANUP = true for a clean answer.`
    : `created '${LIST}'`);
  // Read back on reuse as well as on create, because a list found by title may be a library.
  if (!await establishFixture('formula.validation.fixture-list-created',
    () => spGet(`${listPath}?$select=BaseTemplate`), { BaseTemplate: 100 }, LIST_DEPENDANTS)) {
    return report();
  }

  // ---- The nullable Number column, in the deploy's create shape ----------
  const FIELD_SELECT = 'InternalName,Title,TypeAsString,FieldTypeKind,Required';
  const haveColumn = await spGet(`${fieldPath}?$select=${FIELD_SELECT}`);
  let madeColumn = { ok: true, status: haveColumn.status, text: 'already present' };
  if (!haveColumn.ok) {
    madeColumn = await spPost(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldNumber' }, Title: COL, FieldTypeKind: 9, Required: false,
    }, await getDigest(), VERBOSE);
  }
  const column = await spGet(`${fieldPath}?$select=${FIELD_SELECT}`);
  const nullable = !readFailed(column)
    && column.body.TypeAsString === 'Number' && column.body.Required === false;
  record('formula.validation.fixture-number-column', Q.column,
         nullable ? 'PASS' : 'FAIL',
         `POST fields with FieldTypeKind 9 and Required false answered ${short(madeColumn)}; `
         + (readFailed(column)
           ? `the column did not read back (HTTP ${column.status})`
           : `reads back TypeAsString=${column.body.TypeAsString}, Required=${column.body.Required}`));
  if (!nullable) {
    voidAll(['formula.validation.control-missing-column-refused',
             'formula.validation.fixture-no-rule-in-force',
             ...COLUMN_CELL_IDS, ...CLEAR_AND_LIST_IDS],
            'there is no nullable Number column, so no row below is about a blank in one');
    return report();
  }

  // ---- NEGATIVE CONTROL: an item POST naming a missing column -----------
  const junk = await saveItem({ dbmlspNoSuchColumn: 'x' }, 'control');
  const controlHeld = !junk.ok && isRefusal(junk.status);
  record('formula.validation.control-missing-column-refused', Q.control,
         controlHeld ? 'PASS' : (junk.ok ? 'FAIL' : 'NOT ESTABLISHED'),
         controlHeld
           ? `refused with ${short(junk)}`
           : (junk.ok
             ? 'the item POST naming a missing column was ACCEPTED, so an accepted save below '
               + 'cannot be told from a body the server ignored'
             : `the item POST failed with non-refusal ${short(junk)}`));
  if (!controlHeld) {
    voidAll(['formula.validation.fixture-no-rule-in-force',
             ...COLUMN_CELL_IDS, ...CLEAR_AND_LIST_IDS],
            `the negative control did not hold (HTTP ${junk.status}), so an accepted save below `
            + 'could not be told from any other server answer');
    return report();
  }

  // ---- Both slots empty before the first cell ---------------------------
  // A rule left by a previous run would answer this run's questions, and it
  // would answer them with a refusal that looks exactly like the finding.
  await setColumnRule('');
  await setListRule('');
  const columnStart = await readColumnRule();
  const listStart = await readListRule();
  const clean = columnStart === '' && listStart === '';
  record('formula.validation.fixture-no-rule-in-force', Q.clear,
         clean ? 'PASS' : 'FAIL',
         `column rule reads back ${JSON.stringify(columnStart)}; `
         + `list rule reads back ${JSON.stringify(listStart)}`);
  if (!clean) {
    voidAll([...COLUMN_CELL_IDS, ...CLEAR_AND_LIST_IDS],
            'a rule was already in force, so a refusal below could belong to it');
    return report();
  }

  await runCell(CELLS[0]);
  await runCell(CELLS[1]);

  // ---- Hand over to the list slot ---------------------------------------
  await setColumnRule('');
  const columnCleared = await readColumnRule();
  const handedOver = columnCleared === '';
  record('formula.validation.fixture-column-rule-cleared', Q.columnCleared,
         handedOver ? 'PASS' : 'FAIL',
         `the column rule reads back ${JSON.stringify(columnCleared)} after being cleared`);
  if (!handedOver) {
    voidAll(LIST_CELL_IDS,
            'the column rule is still in force, so a list-cell refusal could be the column rule firing');
    return report();
  }

  await runCell(CELLS[2]);
  await runCell(CELLS[3]);

  return report();
})();
