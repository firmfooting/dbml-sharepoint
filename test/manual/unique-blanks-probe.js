/**
 * dbml-sharepoint PROBE: DOES A UNIQUE TEXT COLUMN ACCEPT MORE THAN ONE BLANK
 *
 * REVISION: 258d8046
 *
 * ONE QUESTION:
 *   On a single-line text column with EnforceUniqueValues, do two items that
 *   leave the column blank both land, or is the second refused as a
 *   duplicate of the first?
 *
 * A `[unique]` column without `[not null]` is a shape the validator warns on
 * (`unique_without_not_null`: "uniqueness enforced only on populated
 * values") and a shipped family relies on: legal-compliance-register's
 * `Topic.ExternalRef` is unique and its note says to leave it blank when the
 * portal export has no identifier. That wording is a claim about what the
 * platform does with two blanks under the constraint, and nothing has
 * measured it. SQL Server, which backs the content database, treats two
 * NULLs as equal under a UNIQUE constraint (Learn: "Unique constraints and
 * check constraints"), so the plausible answer and the assumed answer
 * disagree, which is exactly the case the evidence rule exists for.
 *
 * The write shapes are the deploy's. The column is created by a POST to
 * /fields carrying __metadata, FieldTypeKind 2, EnforceUniqueValues and
 * Indexed together, which is how generators/jsgen.py builds a [unique] Text
 * column. Items are created by a POST to /items, once omitting the column
 * and once sending it as an empty string, because a form save and a seeded
 * row can spell "blank" either way.
 *
 * SCOPE AND QUESTIONS
 *   field.unique.fixture-list-created
 *     A generic list is created (BaseTemplate 100).
 *   field.unique.control-missing-column-refused
 *     NEGATIVE CONTROL: an item POST naming a column that does not exist is
 *     REFUSED. Without it, an accepted write below could be the server
 *     ignoring the column.
 *   field.unique.fixture-unique-text-column
 *     A Text column created with EnforceUniqueValues and Indexed reads both
 *     back true. Every row below is about that constraint, so a column
 *     without it answers nothing.
 *   field.unique.control-duplicate-value-refused
 *     POSITIVE CONTROL: a second item carrying the same non-blank value is
 *     REFUSED. Without it, two blanks landing could mean the constraint is
 *     not enforced at all.
 *   field.unique.blank-values-coexist
 *     Two items that OMIT the column: do both land?
 *   field.unique.empty-string-values-coexist
 *     Two items that send the column as "": do both land?
 *
 * NOT MEASURED HERE
 *   What the form shows when it refuses a duplicate, and whether Quick edit
 *   sends a cleared cell as an omission or as an empty string. Those are
 *   rendered surfaces and need a capture.
 *
 * MICROSOFT LEARN CITATIONS
 *   EnforceUniqueValues and Indexed (CSOM):
 *     "Field.EnforceUniqueValues Property", "Field.Indexed Property"
 *   List creation via POST to `web/lists` and item creation via `items`:
 *     "Working with lists and list items with REST"
 *   Field creation via POST to `fields`:
 *     "Fields REST API reference", dn600182(v=office.15)
 *   Two NULLs are equal under a SQL Server UNIQUE constraint:
 *     "Unique constraints and check constraints" (SQL Server)
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

  log('INFO', 'probe revision 258d8046. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Unique List';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  // Internal name equals display name: created through the same POST to
  // /fields the deploy uses, so it carries no _x0020_ encoding.
  const COL = 'UniqueRef';
  const VALUE = 'dbmlsp-unique-1';

  const Q = {
    fixture: 'A generic list is created (BaseTemplate 100)',
    control: 'NEGATIVE CONTROL: an item POST naming a column that does not exist is refused',
    column: 'A Text column created with EnforceUniqueValues and Indexed reads both back true',
    duplicate: 'POSITIVE CONTROL: a second item carrying the same non-blank value is refused',
    blanks: 'Do two items that omit the unique column both land',
    empties: 'Do two items that send the unique column as an empty string both land',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' on ${WEB} with one unique, indexed Text column,`);
    log('INFO', 'then create up to six items: two with the same value, two omitting the column, two sending it empty.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing list would be reused, and items from a previous run');
      log('INFO', 'would make the duplicate control refuse on the FIRST write. Set CLEANUP = true.');
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
    'field.unique.control-missing-column-refused',
    'field.unique.fixture-unique-text-column',
    'field.unique.control-duplicate-value-refused',
    'field.unique.blank-values-coexist',
    'field.unique.empty-string-values-coexist',
  ];

  expect('field.unique.fixture-list-created', Q.fixture);
  expect('field.unique.control-missing-column-refused', Q.control);
  expect('field.unique.fixture-unique-text-column', Q.column);
  expect('field.unique.control-duplicate-value-refused', Q.duplicate);
  expect('field.unique.blank-values-coexist', Q.blanks);
  expect('field.unique.empty-string-values-coexist', Q.empties);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  // __metadata is a VERBOSE OData construct, so the field create carrying
  // it overrides the harness's default nometadata content type.
  const VERBOSE = { 'Content-Type': 'application/json;odata=verbose' };
  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;

  const readField = async (name) =>
    spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')?$select=Title,TypeAsString,EnforceUniqueValues,Indexed`);

  // Two writes, reported as one row: the head says whether the second
  // landed, and the evidence quotes both answers so a first-write failure
  // is visible as what it is rather than as a refusal.
  const twoWrites = async (id, question, body, describe) => {
    let digest = await getDigest();
    const first = await spPost(`${listPath}/items`, { Title: `${describe} 1`, ...body }, digest);
    if (!first.ok) {
      record(id, question, 'NOT ESTABLISHED',
             `the FIRST item ${describe} was not accepted (${short(first)}), so there was nothing for a second to collide with`);
      return;
    }
    digest = await getDigest();
    const second = await spPost(`${listPath}/items`, { Title: `${describe} 2`, ...body }, digest);
    let head = 'NOT ESTABLISHED';
    if (second.ok) head = 'BOTH LAND';
    else if (isRefusal(second.status)) head = 'SECOND REFUSED';
    record(id, question, head,
           `first item ${describe} answered HTTP ${first.status}; second answered ${short(second)}`);
  };

  await resetList(LIST);

  let digest = await getDigest();
  const haveList = await spGet(listPath);
  if (haveList.ok) {
    record('field.unique.fixture-list-created', Q.fixture, 'ALREADY PRESENT',
           `reusing an existing list '${LIST}'. Set CLEANUP = true for a clean answer`);
  } else {
    const made = await spPost('web/lists', {
      Title: LIST, BaseTemplate: 100,
      Description: 'dbml-sharepoint unique-blanks probe list. Safe to delete.',
    }, digest);
    record('field.unique.fixture-list-created', Q.fixture,
           made.ok ? 'PASS' : 'FAIL',
           made.ok ? `created '${LIST}'` : short(made));
    if (!made.ok) {
      voidAll(IDS, `fixture incomplete: list creation failed (HTTP ${made.status})`);
      return report();
    }
  }

  // ---- NEGATIVE CONTROL: an item POST naming a missing column -----------
  digest = await getDigest();
  const junk = await spPost(`${listPath}/items`,
    { Title: 'dbmlsp unique control', dbmlspNoSuchColumn: 'x' }, digest);
  const controlHeld = !junk.ok && isRefusal(junk.status);
  record('field.unique.control-missing-column-refused', Q.control,
         controlHeld ? 'PASS' : (junk.ok ? 'FAIL' : 'NOT ESTABLISHED'),
         controlHeld ? `refused with ${short(junk)}`
           : (junk.ok ? 'the item POST naming a missing column was ACCEPTED, so an accepted write '
                        + 'below cannot be told from a column the server ignored'
                      : `the item POST failed with non-refusal ${short(junk)}`));
  if (!controlHeld) {
    voidAll(IDS.slice(1),
            `negative control did not hold (HTTP ${junk.status}), so an accepted write below could `
            + 'not be told from any other server answer');
    return report();
  }

  // ---- The unique, indexed Text column: the deploy's create shape --------
  const have = await readField(COL);
  let made = { ok: true, status: have.status, text: 'already present' };
  if (!have.ok) {
    digest = await getDigest();
    made = await spPost(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldText' }, Title: COL, FieldTypeKind: 2,
      EnforceUniqueValues: true, Indexed: true,
    }, digest, VERBOSE);
  }
  const back = await readField(COL);
  const constrained = !readFailed(back) && back.body.EnforceUniqueValues === true && back.body.Indexed === true;
  record('field.unique.fixture-unique-text-column', Q.column,
         constrained ? 'PASS' : 'FAIL',
         `POST fields with EnforceUniqueValues:true and Indexed:true answered ${short(made)}; `
         + (readFailed(back)
           ? `the column did not read back (HTTP ${back.status})`
           : `reads back TypeAsString=${back.body.TypeAsString}, EnforceUniqueValues=${back.body.EnforceUniqueValues}, Indexed=${back.body.Indexed}`));
  if (!constrained) {
    voidAll(IDS.slice(2), 'the column does not carry the constraint, so nothing below is about it');
    return report();
  }

  // ---- POSITIVE CONTROL: the same value twice ---------------------------
  digest = await getDigest();
  const firstValue = await spPost(`${listPath}/items`, { Title: 'dbmlsp unique value 1', [COL]: VALUE }, digest);
  if (!firstValue.ok) {
    record('field.unique.control-duplicate-value-refused', Q.duplicate, 'NOT ESTABLISHED',
           `the FIRST item carrying ${JSON.stringify(VALUE)} was refused (${short(firstValue)}). `
           + 'A previous run left the value behind: set CLEANUP = true and run again');
    voidAll(IDS.slice(3), 'the positive control could not be asked, so a blank landing below is unproven');
    return report();
  }
  digest = await getDigest();
  const secondValue = await spPost(`${listPath}/items`, { Title: 'dbmlsp unique value 2', [COL]: VALUE }, digest);
  const duplicateRefused = !secondValue.ok && isRefusal(secondValue.status);
  record('field.unique.control-duplicate-value-refused', Q.duplicate,
         duplicateRefused ? 'PASS' : (secondValue.ok ? 'FAIL' : 'NOT ESTABLISHED'),
         `first item carrying ${JSON.stringify(VALUE)} answered HTTP ${firstValue.status}; `
         + `second carrying the same value answered ${short(secondValue)}`
         + (secondValue.ok ? '. The duplicate was ACCEPTED, so the constraint is not enforced on this write path' : ''));
  if (!duplicateRefused) {
    voidAll(IDS.slice(3), 'the positive control did not hold, so two blanks landing would say nothing about the constraint');
    return report();
  }

  // ---- The question, spelled both ways a blank arrives ------------------
  await twoWrites('field.unique.blank-values-coexist', Q.blanks, {}, 'omitting the column');
  await twoWrites('field.unique.empty-string-values-coexist', Q.empties, { [COL]: '' }, 'sending the column as ""');

  return report();
})();
