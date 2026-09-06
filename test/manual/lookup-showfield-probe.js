/**
 * dbml-sharepoint PROBE: CAN AN EXISTING LOOKUP BE REPOINTED AT ANOTHER
 * DISPLAY FIELD IN PLACE?
 *
 * QUESTION: a lookup column stores the target column it displays in
 * `LookupField` (the `ShowField` attribute in CAML). Does SharePoint Online
 * accept changing that on an EXISTING lookup, keep the source items' stored
 * target ids, and then materialise and render the new target column?
 *
 * WHY: `analysis/immutable_shape.py:29` lists `LookupField` in
 * `IMMUTABLE_LOOKUP_PROPERTIES`, so `_field_reconcile.js.j2:574` turns a
 * differing display field into a checked mismatch carrying "Lookup targets
 * are immutable; recreate through an explicit migration." Issue #377 records
 * that nothing measured this. Microsoft Learn documents
 * `FieldLookup.LookupField` as `{ get; set; }` and the column settings page
 * offers the change. If the platform does accept the repoint, that message
 * sends an operator to drop and recreate a column, losing every value in it,
 * for a change SharePoint would have taken. AGENTS.md states the rule this
 * would break: an enforced rule must never be stronger than what the
 * reference implementation actually satisfies.
 *
 * SIX SEPARATE THINGS, NEVER ONE PASS. A repoint can succeed at any prefix of
 * this list and fail after it, and collapsing them would report the first as
 * the last:
 *
 *   1. the request was accepted (an HTTP status, nothing more)
 *   2. the stored property changed (a readback of `LookupField`)
 *   3. the source items kept their stored target ids
 *   4. an item-level API returns the new target's text
 *   5. a rendered view shows the new target's text
 *   6. the edit form shows the new target's text
 *
 * A 204 is measured and reported as a 204. It is not evidence that anything
 * changed, which is why question 2 exists and re-reads the field.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. Every question here is about the lookup
 * column type, so nothing files under another surface.
 *
 *   field.lookup.control-showfield-fixture
 *        CONTROL: both lists, the second target column under its internal
 *        name, two target rows, the lookup on Title and the linked source
 *        item are all in place, and the lookup reads back LookupField=Title.
 *        If this fails, everything below is VOID rather than open.
 *   field.lookup.showfield-merge-accepted
 *        Did the field MERGE that sets LookupField to the internal name
 *        'AlternateLabel' come back accepted? HTTP status and body only.
 *   field.lookup.showfield-property-readback
 *        Re-reading the field afterwards, does LookupField hold
 *        'AlternateLabel', still hold 'Title', or could it not be read?
 *   field.lookup.showfield-stored-id-preserved
 *        Is the source item's stored target id identical to the id it held
 *        before the mutation?
 *   field.lookup.showfield-api-display-value
 *        Does a documented item-level API return the new target text for the
 *        lookup? `$expand` returns whichever target column the query names,
 *        so it establishes reachability and cannot answer this on its own.
 *   field.lookup.showfield-rendered-view
 *        Does RenderListDataAsStream, which the modern list page itself
 *        calls, put the AlternateLabel text in the lookup cell?
 *   field.lookup.showfield-edit-form
 *        EYES-ON: what the edit form shows for the lookup. A form is a
 *        rendering surface and no REST call here answers it.
 *   field.lookup.showfield-display-name-spelling
 *        NEGATIVE CONTROL, second armed pass. Learn's `Field element (List)`
 *        warns that ShowField "must be set to the internal field name;
 *        setting it to the display name does not raise an error, but breaks
 *        the field". A silent acceptance that breaks the column is the exact
 *        failure class this repository exists to catch, so it is measured.
 *
 * THE FIXTURE IS DISCRIMINATING BY CONSTRUCTION. The target holds two rows
 * whose Title and AlternateLabel are four different strings, so "the cell
 * shows the alternate label" cannot be satisfied by a stale Title, by the
 * other row, or by an empty cell. The second target column is created with a
 * display title that differs from its internal name, which is what makes the
 * display-name control measurable at all.
 *
 * HOW TO RUN
 *   1. Open a site you own at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Set CONFIRMED, ALLOW_WRITES and CLEANUP to true, paste again. CLEANUP
 *      is wanted here: it recycles this probe's own two lists first, so the
 *      fixture is built rather than inherited from an earlier run whose
 *      lookup may already have been repointed.
 *   4. Do the eyes-on step it prints before doing anything else.
 *   5. Only then, if you want the negative control, set
 *      NEGATIVE_DISPLAY_NAME = true and paste once more. That pass moves the
 *      display field twice and would invalidate the eyes-on observation.
 *   6. Copy the RESULTS block back, and the eyes-on line.
 *
 * WHEN FINISHED: paste once more with CLEANUP = true and nothing else armed,
 * or delete both lists by hand. Cleanup recycles the SOURCE list before the
 * TARGET, and only ever a list carrying this probe's exact description.
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

  // A second armed pass, never the same one as the primary result. It
  // restores the display field to a known-good internal name and then sets
  // the display-name spelling, so a fixture left for the eyes-on step would
  // no longer be in the state that step describes.
  const NEGATIVE_DISPLAY_NAME = false;

  const TARGET = 'dbmlsp Probe ShowFieldTarget';
  const SOURCE = 'dbmlsp Probe ShowFieldSource';
  const LOOKUP = 'ProbeShowField';
  // INTERNAL name and display title differ deliberately, so the negative
  // control has two distinct spellings to send.
  const ALT = 'AlternateLabel';
  const ALT_DISPLAY = 'Alternate Label Display';
  // Ownership is this exact description, never the title. A same-title list
  // somebody else made is refused rather than recycled.
  const OWNERSHIP = 'dbml-sharepoint lookup-showfield probe (issue #377). Safe to recycle.';
  // Four distinct strings, none of which appears anywhere else in the
  // fixture, so finding one in a response is unambiguous.
  const TITLE_ONE = 'dbmlsp-probe-target-title-one';
  const ALT_ONE = 'dbmlsp-probe-alternate-one';
  const TITLE_TWO = 'dbmlsp-probe-target-title-two';
  const ALT_TWO = 'dbmlsp-probe-alternate-two';
  const SOURCE_ROW = 'dbmlsp-probe-source-row';

  const Q = {
    fixture: 'CONTROL: are both lists, the second target column, the two target rows, the lookup and the linked source item in place, with the lookup displaying Title?',
    accepted: 'Does SharePoint accept a MERGE setting an existing lookup\'s LookupField to another target column\'s internal name?',
    readback: 'Re-reading the field afterwards, what does LookupField hold?',
    preserved: 'Did the source item keep the target id it stored before the mutation?',
    api: 'After the mutation, does an item-level API return the new target column\'s text for the lookup?',
    rendered: 'After the mutation, does the rendered list view show the new target column\'s text in the lookup cell?',
    editForm: 'EYES-ON: what does the edit form show for the lookup after the mutation?',
    displayName: 'NEGATIVE CONTROL: what does SharePoint do with a LookupField set to the target column\'s DISPLAY name rather than its internal name?',
  };

  expect('field.lookup.control-showfield-fixture', Q.fixture);
  expect('field.lookup.showfield-merge-accepted', Q.accepted);
  expect('field.lookup.showfield-property-readback', Q.readback);
  expect('field.lookup.showfield-stored-id-preserved', Q.preserved);
  expect('field.lookup.showfield-api-display-value', Q.api);
  expect('field.lookup.showfield-rendered-view', Q.rendered);
  expect('field.lookup.showfield-edit-form', Q.editForm);
  expect('field.lookup.showfield-display-name-spelling', Q.displayName);

  // Every row that a failed fixture control voids rather than leaves open.
  const DEPENDANTS = [
    ['field.lookup.showfield-merge-accepted', Q.accepted],
    ['field.lookup.showfield-property-readback', Q.readback],
    ['field.lookup.showfield-stored-id-preserved', Q.preserved],
    ['field.lookup.showfield-api-display-value', Q.api],
    ['field.lookup.showfield-rendered-view', Q.rendered],
    ['field.lookup.showfield-edit-form', Q.editForm],
    ['field.lookup.showfield-display-name-spelling', Q.displayName],
  ];
  const voidDependants = (why) => {
    for (const [id, question] of DEPENDANTS) {
      record(id, question, 'NOT ESTABLISHED', why, 'void');
    }
  };

  log('INFO', 'probe revision ee8d7bff. Quote this when reporting results.');

  if (!CONFIRMED) {
    log('INFO', `Would create lists '${TARGET}' and '${SOURCE}' on ${WEB}, add a`);
    log('INFO', `text column with internal name '${ALT}' and display title`);
    log('INFO', `'${ALT_DISPLAY}' to the target, create two target rows, add a`);
    log('INFO', `lookup '${LOOKUP}' displaying Title, link one source item to the`);
    log('INFO', `first target row, then MERGE LookupField to '${ALT}' and read`);
    log('INFO', 'back the field, the stored id, an item API and a rendered view.');
    log('INFO', 'Nothing else on the site is touched.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${SOURCE}' then '${TARGET}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is OFF. Turn it on: an inherited fixture may already have');
      log('INFO', 'been repointed, and the fixture control will fail rather than guess.');
    }
    if (NEGATIVE_DISPLAY_NAME) {
      log('INFO', 'NEGATIVE_DISPLAY_NAME is ON, so this pass measures only the');
      log('INFO', 'display-name control and leaves the primary rows unanswered.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  // ---- Transport helpers ----------------------------------------------
  const enc = (value) => encodeURIComponent(String(value).replace(/'/g, "''"));
  const listPath = (title) => `web/lists/getbytitle('${enc(title)}')`;
  const fieldPath = (title, name) =>
    `${listPath(title)}/fields/getbyinternalnameortitle('${enc(name)}')`;
  const MERGE_HEADERS = { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' };
  const bounded = (response) =>
    `HTTP ${response.status} ${String(response.text || '(empty body)').slice(0, 300)}`;

  // ---- Fixture ownership ----------------------------------------------
  // The harness's resetList recycles any list whose title matches, and this
  // probe owns two. Ownership is the exact Description marker, the rule
  // _probe_list_fixture_v1.js.j2 applies for the shared-v2 probes.
  const inspectOwned = async (title) => {
    const found = await spGet(`${listPath(title)}?$select=Id,Description`);
    if (!found.ok) {
      return found.status === 404
        ? { state: 'missing', d: null }
        : { state: 'error', d: null, why: `could not read '${title}': HTTP ${found.status}` };
    }
    if (!found.body || found.body.Description !== OWNERSHIP) {
      return {
        state: 'foreign',
        d: found.body,
        why: `a same-title list '${title}' exists without this probe's exact ownership marker; refusing to modify it`,
      };
    }
    return { state: 'owned', d: found.body };
  };

  // Idempotent: a missing list is a successful no-op, so re-running cleanup
  // is not an error and does not need the caller to know what is there.
  const recycleOwned = async (title) => {
    if (!CLEANUP || !ALLOW_WRITES) return { ok: true, removed: false };
    const inspected = await inspectOwned(title);
    if (inspected.state === 'missing') {
      log('INFO', `CLEANUP: no list named '${title}' to remove.`);
      return { ok: true, removed: false };
    }
    if (inspected.state !== 'owned') {
      log('FAIL', `CLEANUP: ${inspected.why}`);
      return { ok: false, removed: false, why: inspected.why };
    }
    const digest = await getDigest();
    const gone = await spPost(`${listPath(title)}/recycle`, {}, digest);
    log(gone.ok ? 'OK' : 'FAIL', gone.ok
      ? `CLEANUP: recycled '${title}'. It is restorable from the site recycle bin.`
      : `CLEANUP: could not recycle '${title}': ${bounded(gone)}`);
    return { ok: gone.ok, removed: gone.ok };
  };

  const ensureOwnedList = async (title) => {
    const inspected = await inspectOwned(title);
    if (inspected.state === 'owned') {
      log('INFO', `Reusing this probe's list '${title}'.`);
      return { ok: true, d: inspected.d };
    }
    if (inspected.state !== 'missing') return { ok: false, why: inspected.why };
    const digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title, BaseTemplate: 100, Description: OWNERSHIP,
    }, digest);
    if (!made.ok) return { ok: false, why: `could not create '${title}': ${bounded(made)}` };
    log('OK', `Created list '${title}'.`);
    return { ok: true, d: made.body };
  };

  // SOURCE first: it holds a lookup into TARGET, and a target recycled from
  // under a live lookup is a different and untested state.
  await recycleOwned(SOURCE);
  await recycleOwned(TARGET);

  // ---- Fixture -------------------------------------------------------
  // createfieldasxml rather than POST /fields: the harness sends
  // odata=nometadata, which rejects the __metadata hint a typed field
  // creation needs, and SchemaXml is CAML rather than a typed OData entity.
  // Options 8 is AddFieldInternalNameHint, which honours Name as the
  // internal name so it can differ from DisplayName.
  const addFieldAsXml = async (title, schemaXml) => {
    const digest = await getDigest();
    return spPost(`${listPath(title)}/fields/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };
  const addItem = async (title, fields) => {
    const digest = await getDigest();
    return spPost(`${listPath(title)}/items`, fields, digest);
  };
  const readLookupShape = async () => spGet(
    `${fieldPath(SOURCE, LOOKUP)}`
    + '?$select=Id,InternalName,Title,TypeAsString,LookupList,LookupField');

  const setup = { ok: false, why: null };
  const targetList = await ensureOwnedList(TARGET);
  const sourceList = targetList.ok ? await ensureOwnedList(SOURCE) : { ok: false, why: targetList.why };
  if (!sourceList.ok) {
    setup.why = sourceList.why || targetList.why;
  }

  let altShape = null;
  let rowOneId = null;
  let rowTwoId = null;
  let sourceItemId = null;
  let lookupShape = null;
  let storedIdBefore;

  if (!setup.why) {
    const altExists = await spGet(`${fieldPath(TARGET, ALT)}?$select=InternalName`);
    if (!altExists.ok) {
      const made = await addFieldAsXml(
        TARGET,
        `<Field Type="Text" DisplayName="${ALT_DISPLAY}" Name="${ALT}" />`,
      );
      if (!made.ok) setup.why = `could not add the second target column: ${bounded(made)}`;
    }
  }
  if (!setup.why) {
    const read = await spGet(`${fieldPath(TARGET, ALT)}?$select=InternalName,Title`);
    if (readFailed(read)) {
      setup.why = `could not read the second target column back: HTTP ${read.status}`;
    } else {
      altShape = read.body;
      if (altShape.InternalName !== ALT) {
        setup.why = `the second target column read back InternalName `
          + `${JSON.stringify(altShape.InternalName)}, not '${ALT}'. Every mutation `
          + 'below sends an internal name, so there is nothing to point at.';
      }
    }
  }
  if (!setup.why) {
    const one = await addItem(TARGET, { Title: TITLE_ONE, [ALT]: ALT_ONE });
    const two = await addItem(TARGET, { Title: TITLE_TWO, [ALT]: ALT_TWO });
    if (!one.ok || !two.ok) {
      setup.why = `could not create the target rows: HTTP ${one.status}/${two.status}`;
    } else {
      rowOneId = one.body.Id;
      rowTwoId = two.body.Id;
    }
  }
  if (!setup.why) {
    const existing = await spGet(`${fieldPath(SOURCE, LOOKUP)}?$select=InternalName`);
    if (!existing.ok) {
      const digest = await getDigest();
      const made = await spPost(`${listPath(SOURCE)}/fields/addfield`, {
        parameters: {
          Title: LOOKUP,
          FieldTypeKind: 7,
          LookupListId: targetList.d.Id,
          LookupFieldName: 'Title',
        },
      }, digest);
      if (!made.ok) setup.why = `could not add the lookup column: ${bounded(made)}`;
      else log('OK', `Added lookup '${LOOKUP}' -> ${TARGET}.Title.`);
    }
  }
  if (!setup.why) {
    const linked = await addItem(SOURCE, { Title: SOURCE_ROW, [`${LOOKUP}Id`]: rowOneId });
    if (!linked.ok) setup.why = `could not create the linked source item: ${bounded(linked)}`;
    else sourceItemId = linked.body.Id;
  }
  if (!setup.why) {
    const shape = await readLookupShape();
    if (readFailed(shape)) {
      setup.why = `could not read the lookup field back: HTTP ${shape.status}`;
    } else {
      lookupShape = shape.body;
    }
  }

  const readSourceItem = async () => spGet(
    `${listPath(SOURCE)}/items(${sourceItemId})?$select=Id,Title,${LOOKUP}Id`);
  const readSourceItemExpanded = async () => spGet(
    `${listPath(SOURCE)}/items(${sourceItemId})`
    + `?$select=Id,${LOOKUP}Id,${LOOKUP}/Title,${LOOKUP}/${ALT}&$expand=${LOOKUP}`);
  const readValuesAsText = async () => spGet(
    `${listPath(SOURCE)}/items(${sourceItemId})/FieldValuesAsText`);

  if (!setup.why) {
    const item = await readSourceItem();
    if (readFailed(item)) {
      setup.why = `could not read the linked source item back: HTTP ${item.status}`;
    } else if (String(item.body[`${LOOKUP}Id`]) !== String(rowOneId)) {
      setup.why = `the source item stores ${LOOKUP}Id=`
        + `${JSON.stringify(item.body[`${LOOKUP}Id`])}, not the first target row's `
        + `id ${JSON.stringify(rowOneId)}`;
    } else {
      // The id the preservation question compares against, captured as JSON
      // so the comparison is over bytes rather than over a coerced string.
      storedIdBefore = item.body[`${LOOKUP}Id`];
    }
  }
  // The ViewXml FieldRef and the `${LOOKUP}Id` write key are both spelled from
  // LOOKUP, so an internal name SharePoint derived differently would make both
  // name a column that is not this one.
  if (!setup.why && lookupShape.InternalName !== LOOKUP) {
    setup.why = `the lookup read back InternalName `
      + `${JSON.stringify(lookupShape.InternalName)}, not '${LOOKUP}', so the rendered `
      + 'view and the item write below would name a different column';
  }
  // Fixture and initial display field are both things the primary measurement
  // DEPENDS on, so both belong in the control. Whether the repoint takes is
  // what the run observes, and no part of it is asserted here. The negative
  // pass is exempt because it restores 'Title' itself and verifies the
  // readback before it sends anything.
  if (!setup.why && !NEGATIVE_DISPLAY_NAME && lookupShape.LookupField !== 'Title') {
    setup.why = `the lookup already displays `
      + `${JSON.stringify(lookupShape.LookupField)} rather than 'Title'. This is a `
      + 'fixture inherited from an earlier run. Re-run with CLEANUP = true; '
      + 'repairing it here would use the very operation under test.';
  }
  setup.ok = !setup.why;
  const inheritedNote = (setup.ok && lookupShape.LookupField !== 'Title')
    ? ` The lookup did NOT start on 'Title'; the negative pass restores it below.`
    : '';

  record('field.lookup.control-showfield-fixture', Q.fixture,
         setup.ok ? 'PASS' : 'FAIL',
         setup.ok
           ? `lists '${TARGET}' and '${SOURCE}' owned by this probe; target column `
             + `InternalName=${JSON.stringify(altShape.InternalName)} `
             + `Title=${JSON.stringify(altShape.Title)}; target rows `
             + `${rowOneId}=(${JSON.stringify(TITLE_ONE)}, ${JSON.stringify(ALT_ONE)}) and `
             + `${rowTwoId}=(${JSON.stringify(TITLE_TWO)}, ${JSON.stringify(ALT_TWO)}); lookup `
             + `${JSON.stringify(lookupShape.InternalName)} TypeAsString=`
             + `${JSON.stringify(lookupShape.TypeAsString)} LookupList=`
             + `${JSON.stringify(lookupShape.LookupList)} LookupField=`
             + `${JSON.stringify(lookupShape.LookupField)}; source item ${sourceItemId} stores `
             + `${LOOKUP}Id=${JSON.stringify(storedIdBefore)}.${inheritedNote}`
           : setup.why);

  if (!setup.ok) {
    voidDependants('the fixture control did not hold, so nothing below was measured');
    return report();
  }

  // ---- The negative control pass, which measures nothing else ---------
  if (NEGATIVE_DISPLAY_NAME) {
    log('INFO', 'NEGATIVE_DISPLAY_NAME is on. This pass measures the display-name');
    log('INFO', 'control only; the primary rows stay unanswered by design.');
  }

  // ---- Observation helpers --------------------------------------------
  const mergeShowField = async (value, verbose) => {
    const digest = await getDigest();
    return verbose
      ? spPost(fieldPath(SOURCE, LOOKUP),
               { __metadata: { type: 'SP.FieldLookup' }, LookupField: value }, digest,
               { ...MERGE_HEADERS, 'Content-Type': 'application/json;odata=verbose' })
      : spPost(fieldPath(SOURCE, LOOKUP), { LookupField: value }, digest, MERGE_HEADERS);
  };

  // RenderListDataAsStream is what the modern list page itself calls, so it
  // answers "what would a reader see" rather than "what does REST list".
  // ViewFields names the lookup and nothing else beyond ID, so the search
  // scope is the lookup CELL rather than a row carrying unrelated strings.
  const renderLookupCell = async () => {
    const digest = await getDigest();
    const viewXml = '<View><ViewFields>'
      + `<FieldRef Name='ID'/><FieldRef Name='${LOOKUP}'/>`
      + '</ViewFields><Query></Query><RowLimit>50</RowLimit></View>';
    const rendered = await spPost(`${listPath(SOURCE)}/RenderListDataAsStream`,
                                  { parameters: { ViewXml: viewXml } }, digest);
    if (!rendered.ok || !rendered.body || !Array.isArray(rendered.body.Row)) {
      return { ok: false, status: rendered.status, cell: null, note: bounded(rendered) };
    }
    const row = rendered.body.Row.find((candidate) => String(candidate.ID) === String(sourceItemId));
    if (!row) {
      return {
        ok: false, status: rendered.status, cell: null,
        note: `the rendering returned ${rendered.body.Row.length} row(s), none with ID ${sourceItemId}`,
      };
    }
    if (row[LOOKUP] === undefined) {
      return {
        ok: false, status: rendered.status, cell: null,
        note: `the rendered row carries no '${LOOKUP}' key. Keys: `
          + `${JSON.stringify(Object.keys(row)).slice(0, 300)}`,
      };
    }
    return { ok: true, status: rendered.status, cell: JSON.stringify(row[LOOKUP]).slice(0, 300) };
  };

  // Which of the first target row's two strings a bounded piece of text
  // carries. Both are distinct and appear nowhere else in the fixture, so
  // this discriminates without depending on a response shape Microsoft does
  // not document.
  const whichLabel = (text) => {
    if (text === null || text === undefined) return null;
    const carriesTitle = String(text).includes(TITLE_ONE);
    const carriesAlternate = String(text).includes(ALT_ONE);
    if (carriesTitle && carriesAlternate) return 'both';
    if (carriesAlternate) return 'alternate';
    if (carriesTitle) return 'title';
    return 'neither';
  };
  const carriedPhrase = {
    title: "which carries the target's Title",
    alternate: `which carries ${ALT}`,
    both: 'which carries both target strings',
    neither: 'which carries neither target string',
  };

  // ---- Before the mutation --------------------------------------------
  const renderBefore = await renderLookupCell();
  const expandedBefore = await readSourceItemExpanded();
  const textBefore = await readValuesAsText();
  log('INFO', `Before the mutation, the rendered lookup cell is ${renderBefore.ok ? renderBefore.cell : `unreadable (${renderBefore.note})`}.`);

  if (NEGATIVE_DISPLAY_NAME) {
    // Restore a known-good INTERNAL name first, so what follows is measured
    // from a state this run established rather than inherited.
    const restore = await mergeShowField('Title', false);
    const restored = await readLookupShape();
    const restoredTo = readFailed(restored) ? null : restored.body.LookupField;
    if (restoredTo !== 'Title') {
      record('field.lookup.showfield-display-name-spelling', Q.displayName,
             'NOT ESTABLISHED',
             `the field could not be returned to a known-good internal-name state `
             + `before the control was sent: restore ${bounded(restore)}, readback `
             + `LookupField=${JSON.stringify(restoredTo)}. Nothing was sent.`);
      report();
      log('INFO', `Delete '${SOURCE}' and '${TARGET}' when you have finished.`);
      return;
    }
    log('OK', `Restored LookupField to 'Title' before sending the control.`);

    let sent = await mergeShowField(ALT_DISPLAY, false);
    let usedVerbose = false;
    if (!sent.ok) {
      sent = await mergeShowField(ALT_DISPLAY, true);
      usedVerbose = true;
    }
    const after = await readLookupShape();
    const held = readFailed(after) ? null : after.body.LookupField;
    const renderedAfter = await renderLookupCell();
    const carries = renderedAfter.ok ? whichLabel(renderedAfter.cell) : null;
    const transport = `${usedVerbose ? 'nometadata refused, verbose ' : ''}MERGE ${bounded(sent)}`;
    record('field.lookup.showfield-display-name-spelling', Q.displayName,
           held === null ? 'NOT ESTABLISHED'
             : !sent.ok ? (isRefusal(sent.status) ? 'REFUSED' : 'NOT ESTABLISHED')
             : carries === null ? 'ACCEPTED, CELL UNREADABLE'
             : carries === 'neither' ? 'ACCEPTED AND THE CELL LOST ITS LABEL'
             : 'ACCEPTED AND THE CELL STILL RENDERS',
           `sent LookupField=${JSON.stringify(ALT_DISPLAY)}, the display title of the `
           + `column whose internal name is ${JSON.stringify(ALT)}. ${transport}. `
           + `Field readback LookupField=${JSON.stringify(held)}. Rendered cell `
           + `${renderedAfter.ok ? renderedAfter.cell : `unreadable (${renderedAfter.note})`}`
           + `${carries === null ? '' : `, ${carriedPhrase[carries]}`}.`);

    report();
    console.log('\n============ AFTER THE NEGATIVE CONTROL ============');
    console.log('The display field is now whatever the line above says it is.');
    console.log('The primary rows are answered by the primary pass, not by this one.');
    console.log(`Paste again with CLEANUP = true to recycle '${SOURCE}' then '${TARGET}'.`);
    console.log('====================================================');
    return;
  }

  // ---- 1. Was the request accepted ------------------------------------
  // Two spellings, because the harness sends odata=nometadata and a typed
  // property on a derived field type is the case where that has needed a
  // verbose __metadata hint before. A transport refusal reported as a
  // platform refusal would answer the whole question wrongly.
  const first = await mergeShowField(ALT, false);
  const readbackFirst = await readLookupShape();
  const heldFirst = readFailed(readbackFirst) ? null : readbackFirst.body.LookupField;
  let second = null;
  let readbackSecond = null;
  if (heldFirst !== ALT) {
    second = await mergeShowField(ALT, true);
    readbackSecond = await readLookupShape();
  }
  const finalReadback = readbackSecond || readbackFirst;
  const held = readFailed(finalReadback) ? null : finalReadback.body.LookupField;
  const attempts = `nometadata MERGE ${bounded(first)}`
    + (second ? `; verbose MERGE with __metadata SP.FieldLookup ${bounded(second)}` : '');
  const anyAccepted = first.ok || Boolean(second && second.ok);
  const anyRefused = (!first.ok && isRefusal(first.status))
    || Boolean(second && !second.ok && isRefusal(second.status));

  record('field.lookup.showfield-merge-accepted', Q.accepted,
         anyAccepted ? 'ACCEPTED' : anyRefused ? 'REFUSED' : 'NOT ESTABLISHED',
         `${attempts}. An accepted status says the request was taken, never that `
         + 'the property changed; the readback row is what answers that.'
         + (anyAccepted || anyRefused ? '' : ' Neither attempt was a refusal, so the '
           + 'server did not reject the content and this run has no answer.'));

  // ---- 2. Did the stored property change ------------------------------
  record('field.lookup.showfield-property-readback', Q.readback,
         held === null ? 'NOT ESTABLISHED'
           : held === ALT ? 'REPOINTED'
           : held === 'Title' ? 'UNCHANGED'
           : 'CHANGED TO SOMETHING ELSE',
         held === null
           ? `the field could not be read back after the mutation (HTTP `
             + `${finalReadback.status}), so this run cannot say what it holds`
           : `LookupField=${JSON.stringify(held)} after the mutation, from `
             + `${JSON.stringify('Title')} before it. LookupList=`
             + `${JSON.stringify(finalReadback.body.LookupList)}, TypeAsString=`
             + `${JSON.stringify(finalReadback.body.TypeAsString)}. First readback held `
             + `${JSON.stringify(heldFirst)}.`);

  // ---- 3. Did the source item keep its stored id ----------------------
  const itemAfter = await readSourceItem();
  const storedIdAfter = readFailed(itemAfter) ? undefined : itemAfter.body[`${LOOKUP}Id`];
  const identical = JSON.stringify(storedIdBefore) === JSON.stringify(storedIdAfter);
  record('field.lookup.showfield-stored-id-preserved', Q.preserved,
         readFailed(itemAfter) ? 'NOT ESTABLISHED'
           : identical ? 'PRESERVED' : 'CHANGED',
         readFailed(itemAfter)
           ? `the source item could not be re-read after the mutation (HTTP `
             + `${itemAfter.status}), so preservation is unmeasured`
           : `${LOOKUP}Id was ${JSON.stringify(storedIdBefore)} before and `
             + `${JSON.stringify(storedIdAfter)} after, which are `
             + `${identical ? 'identical as JSON' : 'not identical'}. Target row 1 is id `
             + `${rowOneId}.`);

  // ---- 4. Does an item-level API return the new text -------------------
  // $expand is deliberately not the instrument here: it returns whichever
  // target column the query names, so it can only establish reachability.
  // FieldValuesAsText is the item-level surface that returns SharePoint's own
  // display text per field, and whether it materialises a lookup at all is
  // part of what this measures.
  const expandedAfter = await readSourceItemExpanded();
  const textAfter = await readValuesAsText();
  const textCell = (!readFailed(textAfter) && textAfter.body
    && textAfter.body[LOOKUP] !== undefined)
    ? String(textAfter.body[LOOKUP]) : null;
  const textCellBefore = (!readFailed(textBefore) && textBefore.body
    && textBefore.body[LOOKUP] !== undefined)
    ? String(textBefore.body[LOOKUP]) : null;
  const textCarries = whichLabel(textCell);
  const reachability = `$expand before ${readFailed(expandedBefore) ? `HTTP ${expandedBefore.status}` : JSON.stringify(JSON.stringify(expandedBefore.body).slice(0, 200))}`
    + `; $expand after ${readFailed(expandedAfter) ? `HTTP ${expandedAfter.status}` : JSON.stringify(JSON.stringify(expandedAfter.body).slice(0, 200))}`;
  record('field.lookup.showfield-api-display-value', Q.api,
         textCell === null ? 'NOT ESTABLISHED'
           : textCarries === 'alternate' ? 'ALTERNATE LABEL'
           : textCarries === 'title' ? 'TITLE'
           : 'NOT ESTABLISHED',
         textCell === null
           ? `FieldValuesAsText did not return a '${LOOKUP}' value (HTTP `
             + `${textAfter.status}), and $expand cannot answer this on its own `
             + `because it returns whichever target column the query names. `
             + `${reachability}`
           : `FieldValuesAsText['${LOOKUP}'] was ${JSON.stringify(textCellBefore)} before `
             + `and ${JSON.stringify(textCell)} after`
             + (textCarries === 'alternate' || textCarries === 'title'
               ? '.' : `, which carries neither target string, so the API's value is `
                 + 'not one this run can attribute to either column. ')
             + ` ${reachability}`);

  // ---- 5. Does the rendered view show the new text ---------------------
  const renderAfter = await renderLookupCell();
  const renderedCarries = renderAfter.ok ? whichLabel(renderAfter.cell) : null;
  const renderedBeforeCarries = renderBefore.ok ? whichLabel(renderBefore.cell) : null;
  record('field.lookup.showfield-rendered-view', Q.rendered,
         !renderAfter.ok || renderedBeforeCarries !== 'title' ? 'NOT ESTABLISHED'
           : renderedCarries === 'alternate' ? 'RENDERS THE ALTERNATE LABEL'
           : renderedCarries === 'title' ? 'STILL RENDERS THE TITLE'
           : 'NOT ESTABLISHED',
         !renderAfter.ok
           ? `the rendering did not answer after the mutation: ${renderAfter.note}`
           : renderedBeforeCarries !== 'title'
             ? `the cell did not carry ${JSON.stringify(TITLE_ONE)} BEFORE the mutation `
               + `(${renderBefore.ok ? renderBefore.cell : renderBefore.note}), so there is `
               + 'no reference state and an alternate label afterwards would not be a change'
             : `the cell was ${renderBefore.cell} before and ${renderAfter.cell} after, `
               + `${carriedPhrase[renderedCarries]}.`);

  // ---- 6. The edit form, which no REST call here answers ---------------
  const formUrls = await spGet(`${listPath(SOURCE)}?$select=DefaultEditFormUrl`);
  const editUrl = (!readFailed(formUrls) && formUrls.body.DefaultEditFormUrl)
    ? `${window.location.origin}${formUrls.body.DefaultEditFormUrl}?ID=${sourceItemId}`
    : null;
  record('field.lookup.showfield-edit-form', Q.editForm,
         editUrl ? 'MANUAL' : 'NOT ESTABLISHED',
         editUrl
           ? `open ${editUrl} and read the '${LOOKUP}' field. `
             + `${JSON.stringify(TITLE_ONE)} means the form still shows the target's `
             + `Title; ${JSON.stringify(ALT_ONE)} means it shows ${ALT}. Anything else, `
             + 'including a blank cell, a numeric id or an error, is its own answer and '
             + 'is recorded verbatim.'
           : `DefaultEditFormUrl could not be read (HTTP ${formUrls.status}), so this row `
             + 'has no exact URL to send anybody to');

  record('field.lookup.showfield-display-name-spelling', Q.displayName,
         'NOT ESTABLISHED',
         'the display-name control is a separate armed pass and was not run. Take the '
         + 'eyes-on observation first, then set NEGATIVE_DISPLAY_NAME = true and paste '
         + 'again.', 'open');

  report();
  console.log('\n============ EYES-ON ============');
  console.log('Do this BEFORE arming anything else. A form is a rendering surface');
  console.log('and no REST call in this probe answers it.');
  if (editUrl) {
    console.log(`  1. Open ${editUrl}`);
  } else {
    console.log(`  1. Open the item titled '${SOURCE_ROW}' on '${SOURCE}' for editing.`);
    console.log('     (DefaultEditFormUrl could not be read, so there is no exact link.)');
  }
  console.log(`  2. Read the '${LOOKUP}' field.`);
  console.log(`     "${TITLE_ONE}" means the form still shows the target Title.`);
  console.log(`     "${ALT_ONE}" means it shows ${ALT}.`);
  console.log('     Blank, an id, or an error is its own answer. Write it down verbatim.');
  console.log('     what you see: ______________________________________');
  console.log('=================================');
  console.log('');
  console.log('The display-name negative control is a SECOND pass and moves the');
  console.log('display field twice more. Run it only after the line above is filled in:');
  console.log('set NEGATIVE_DISPLAY_NAME = true and paste again.');
  log('INFO', `Paste with CLEANUP = true, or delete '${SOURCE}' then '${TARGET}', when finished.`);
})();
