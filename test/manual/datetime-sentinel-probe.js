/**
 * dbml-sharepoint PROBE — TIME OF DAY: NOW(), <Now/>, AND IncludeTimeValue
 *
 * QUESTION: can this tool express "not in the future" on a DATETIME column
 * exactly, rather than to the nearest day — and is there a `now` sentinel
 * worth adding beside `today`?
 *
 * WHY: `analysis/conditions.py` has one date sentinel, `today`, compiled
 * three ways — `<Today OffsetDays="N"/>` for CAML, `TODAY()+N` for a
 * validation formula, and refused outright on the client-side expression
 * target. Because `TODAY()` is midnight, a "not in the future" rule on a
 * datetime column cannot be written `<= TODAY()`: that would reject
 * everything stamped after 00:00. Five templates work around it with a
 * `today+1` midnight allowance — visitor-log's `SignedInAt`,
 * switchboard-log's `AnnouncedAt` and `AllClearAt`, and
 * service-evidence-register's `OccurredAt` among them — each with a comment
 * asserting the behaviour but citing no observation.
 *
 * Two documents point in different directions and neither has been tested
 * against a live list:
 *
 *   - Microsoft's "Introduction to SharePoint formulas and functions" says
 *     "Lists and libraries do not support the RAND and NOW functions",
 *     which would close the validation question permanently.
 *   - "Now element (Query)" documents <Now/> as a valid child of <Value>,
 *     alongside <Today/> — but with no attributes table and parents listed
 *     only as "Numerous", which is unusually thin.
 *
 * This is the failure class the project keeps meeting: a rule that saves,
 * reads back byte-identical, passes every deploy phase and then filters the
 * wrong rows or never fires. Documentation alone has been wrong here before.
 *
 * WHAT IT ASKS
 *
 *   TZ0  what time zone does the SITE run in, and does it match this
 *        browser? <Today/> renders in the SERVER's zone, so every same-day
 *        question below is read through this row. Not a pass/fail.
 *
 *   -- Validation formulas ------------------------------------------------
 *   VN   NEGATIVE CONTROL — is a ValidationFormula naming a column that
 *        does not exist REFUSED? If garbage is accepted, no refusal below
 *        means anything.
 *   V1   is NOW() in a ValidationFormula refused, as the docs imply?
 *   V2   ...and if it is ACCEPTED, does it actually reject a future
 *        timestamp, or is it accepted-but-inert? Accepted-and-inert is the
 *        worst outcome available and the one worth knowing about.
 *   V3   THE LOAD-BEARING ROW. Under `=[ProbeWhen] <= TODAY()`, is an item
 *        stamped EARLIER TODAY rejected? Five shipped templates assume yes.
 *        If it saves, every `today+1` allowance in the library is an
 *        unnecessary 24-hour hole.
 *   V4   Under `<= TODAY()+1`, does an item stamped LATER TODAY save? This
 *        is the shipped idiom's positive case.
 *   V5   Under `<= TODAY()+1`, is an item stamped TWO DAYS out rejected?
 *   V6   Under `<= TODAY()+1`, what is the exact ceiling — does TOMORROW
 *        23:00 save? This decides whether the allowance is about 24 hours
 *        or about 48, which is what the comments in five templates should
 *        say and currently do not.
 *
 *   -- CAML view filters ---------------------------------------------------
 *   CN   NEGATIVE CONTROL — is a CAML query containing a bogus <Nowww/>
 *        element refused? If SharePoint accepts nonsense in a ViewQuery,
 *        C1 through C5 prove nothing.
 *   C1   does a VIEW whose ViewQuery contains <Now/> save, and read back
 *        still containing it? This is the deploy surface: deploy.js writes
 *        ViewQuery and verifies by read-back.
 *   C2   does <Now/> WITHOUT IncludeTimeValue discriminate an item stamped
 *        earlier today from one stamped later today?
 *   C3   does <Now/> WITH IncludeTimeValue='TRUE' discriminate them?
 *   C4   does <Today/> WITH IncludeTimeValue='TRUE' behave as midnight, or
 *        as the current instant? Widely-repeated blog advice says the
 *        latter; Learn implies the former. They give OPPOSITE answers for
 *        an item stamped earlier today, so one of them is wrong.
 *   C5   BASELINE — <Today/> without IncludeTimeValue, which is what the
 *        tool emits today. Confirms date granularity is what seven shipped
 *        views are actually getting.
 *
 *   -- The client-side expression target ------------------------------------
 *   E1   is @now accepted and stored in a ClientValidationFormula
 *        (conditional show/hide)? conditions.py refuses the `today`
 *        sentinel there for want of "a verified client-side equivalent".
 *
 *   -- RIDING ALONG: how a validation literal escapes a double quote -------
 *   Not a time question, and here anyway. `_validation_literal` in
 *   conditions.py wraps every text literal in double quotes and escapes an
 *   embedded one by DOUBLING it, with the comment: "the Excel convention
 *   but was NOT among the harvested formulas — see the spec's open items".
 *   It is a shipped code path that has never been observed, it needs the
 *   same list and the same MERGE machinery this probe already has, and a
 *   separate paste for three questions would simply never be run.
 *
 *   Q1   is a ValidationFormula whose literal doubles an embedded " ("")
 *        accepted and stored?
 *   Q2   ...and does it match the RIGHT value — i.e. does it reject an item
 *        holding exactly He said "hi"? Accepted is not parsed: a formula
 *        that reads the literal as something else would still save.
 *   Q3   ...and does it leave a DIFFERENT value alone? Q2 alone cannot
 *        distinguish "escaped correctly" from "rejects everything".
 *   Q4   what happens to the backslash convention instead? If both are
 *        accepted, the tool's choice is safe; if backslash is accepted and
 *        mis-parses, that is a trap worth naming in the code.
 *
 * READ VN AND CN FIRST. They are the only rows establishing that this probe
 * can tell acceptance from refusal on each surface. If either NEGATIVE
 * CONTROL is itself accepted, treat every result on that surface as
 * unproven rather than as evidence.
 *
 * TIME-OF-DAY GATE: the same-day questions need "three hours ago" and
 * "three hours from now" to fall on the SAME server-local day. Run this
 * between about 04:00 and 20:00 site-local. Outside that window the probe
 * refuses to guess and reports those rows NOT ESTABLISHED rather than
 * producing an answer nobody should trust.
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim, including the TZ0 row.
 *
 * WHEN FINISHED: delete the list it created. Everything lives in it.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // CLEANUP deletes the probe's own list BEFORE the run, so every question
  // is answered by actually creating something rather than reporting
  // "already present" from a previous run — which is much weaker evidence.
  //
  // It is destructive and needs CONFIRMED and ALLOW_WRITES as well. It only
  // ever touches the single list the probe declares; it never enumerates or
  // deletes anything else. The list is RECYCLED, not purged, so a mistake
  // is recoverable from the site recycle bin.
  const CLEANUP = false;

  // No SITE_URL constant, deliberately. The probe reads the site it was
  // pasted into. A tenant URL committed to this repo has leaked twice, and
  // the field was the vector both times.
  const pageCtx = window._spPageContextInfo;
  if (!pageCtx) {
    console.error('[FATAL] No _spPageContextInfo — paste this into a SharePoint page.');
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
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false — not deleting '${title}'.`);
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
    // removed — a locked or no-delete list would otherwise leave rows from
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
  const RESULTS = [];
  const expect = (id, question) => {
    RESULTS.push({ id, question, outcome: 'NOT ESTABLISHED', evidence: 'the run did not reach this question' });
  };
  const record = (id, question, outcome, evidence) => {
    const row = RESULTS.find((r) => r.id === id);
    if (row) {
      Object.assign(row, { question, outcome, evidence });
    } else {
      RESULTS.push({ id, question, outcome, evidence });
    }
    const level = outcome === 'PASS' ? 'OK' : outcome === 'FAIL' ? 'FAIL' : 'INFO';
    log(level, `${id}: ${outcome} — ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };

  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    const open = RESULTS.filter((r) => r.outcome === 'NOT ESTABLISHED').length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} NOT established.`);
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };

  const LIST = 'dbmlsp Probe DateTimeSentinel';
  const FIELD = 'ProbeWhen';
  const fieldsPath = `web/lists/getbytitle('${LIST}')/fields`;
  const itemsPath = `web/lists/getbytitle('${LIST}')/items`;

  if (!CONFIRMED) {
    log('INFO', `Would create list '${LIST}' on ${WEB} with one DateTime`);
    log('INFO', 'column, then set several validation formulas on it and try to');
    log('INFO', 'save items stamped earlier today, later today, two days out');
    log('INFO', 'and tomorrow night — recording which SharePoint refuses. Then');
    log('INFO', 'it runs five CAML queries testing <Now/>, <Today/> and');
    log('INFO', 'IncludeTimeValue, plus two negative controls.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first, with its items.`);
    } else {
      log('INFO', `CLEANUP is off: an existing '${LIST}' would be topped up, and`);
      log('INFO', 'rows from a previous run would answer this run\'s CAML');
      log('INFO', 'questions. Set CLEANUP = true for a clean run.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  // Declared before anything can fail, so an abort reports the questions it
  // never reached instead of only the ones it managed to ask.
  expect('TZ0', 'Site time zone, and whether this browser shares it');
  expect('VN', 'NEGATIVE CONTROL: a ValidationFormula naming a missing column is refused');
  expect('V1', 'NOW() in a ValidationFormula');
  expect('V2', 'If NOW() was accepted, does it reject a future timestamp');
  expect('V3', 'Under <= TODAY(), an item stamped EARLIER TODAY is rejected');
  expect('V4', 'Under <= TODAY()+1, an item stamped LATER TODAY saves');
  expect('V5', 'Under <= TODAY()+1, an item stamped TWO DAYS out is rejected');
  expect('V6', 'Under <= TODAY()+1, the exact ceiling (tomorrow 23:00)');
  expect('CN', 'NEGATIVE CONTROL: CAML containing a bogus <Nowww/> is refused');
  expect('C1', 'A view ViewQuery containing <Now/> saves and reads back intact');
  expect('C2', '<Now/> WITHOUT IncludeTimeValue discriminates within one day');
  expect('C3', "<Now/> WITH IncludeTimeValue='TRUE' discriminates within one day");
  expect('C4', "<Today/> WITH IncludeTimeValue='TRUE': midnight, or current instant");
  expect('C5', 'BASELINE: <Today/> without IncludeTimeValue is date-granular');
  expect('E1', '@now is accepted and stored in a ClientValidationFormula');
  expect('Q1', 'A validation literal doubling an embedded " is accepted');
  expect('Q2', '...and rejects an item holding exactly that value');
  expect('Q3', '...and leaves a different value alone');
  expect('Q4', 'The backslash convention instead: accepted, and does it parse');

  await resetList(LIST);
  let digest = await getDigest();

  // ---- TZ0: whose clock are we reading? -------------------------------
  // <Today/> renders in the SERVER's local zone, not the browser's. If the
  // two differ, an item this browser calls "later today" may be tomorrow to
  // SharePoint, and the same-day rows would be answering a question nobody
  // asked. SharePoint reports Bias and DaylightBias but does not say which
  // is in force right now, so BOTH candidate server hours are computed and
  // the gate demands both be safe.
  const tz = await spGet('web/RegionalSettings/TimeZone');
  const info = (tz.ok && tz.body && tz.body.Information) || null;
  const utcHour = new Date().getUTCHours() + new Date().getUTCMinutes() / 60;
  const browserOffsetMin = -new Date().getTimezoneOffset();
  let serverHours = [];
  let tzEvidence = '';
  if (info) {
    // Windows convention: local + Bias = UTC, so local = UTC - Bias.
    const standardMin = -(info.Bias + (info.StandardBias || 0));
    const daylightMin = -(info.Bias + (info.DaylightBias || 0));
    serverHours = [...new Set([standardMin, daylightMin])].map(
      (m) => ((utcHour + m / 60) % 24 + 24) % 24);
    const desc = (tz.body.Description || '(no description)');
    tzEvidence = `site zone "${desc}"; candidate site-local offsets `
      + `${[...new Set([standardMin, daylightMin])].map((m) => `${m >= 0 ? '+' : ''}${m}min`).join(' / ')}; `
      + `this browser ${browserOffsetMin >= 0 ? '+' : ''}${browserOffsetMin}min; `
      + `site-local hour now ~${serverHours.map((h) => h.toFixed(1)).join(' or ')}`;
    const shares = [standardMin, daylightMin].includes(browserOffsetMin);
    record('TZ0', 'Site time zone, and whether this browser shares it',
           shares ? 'SAME ZONE' : 'DIFFERENT ZONE', tzEvidence);
  } else {
    record('TZ0', 'Site time zone, and whether this browser shares it', 'NOT ESTABLISHED',
           `could not read web/RegionalSettings/TimeZone (HTTP ${tz.status}) — `
           + 'the same-day rows below cannot be interpreted safely');
  }

  // Both candidate site-local hours must leave room for -3h and +3h to stay
  // on the same site-local day.
  const SAME_DAY_OK = serverHours.length > 0
    && serverHours.every((h) => h >= 4 && h <= 20);
  if (!SAME_DAY_OK) {
    log('INFO', 'TIME-OF-DAY GATE CLOSED: the same-day questions (V3, V4, C2, C3,');
    log('INFO', 'C4, C5) cannot be answered safely at this hour. They will be');
    log('INFO', 'reported NOT ESTABLISHED. Re-run between 04:00 and 20:00 site time.');
  }

  // ---- Bootstrap ------------------------------------------------------
  const existing = await spGet(`web/lists/getbytitle('${LIST}')`);
  if (!existing.ok) {
    const made = await spPost('web/lists', {
      Title: LIST,
      BaseTemplate: 100,
      Description: 'dbml-sharepoint probe list. Safe to delete.',
    }, digest);
    if (!made.ok) {
      record('BOOT', 'Create the probe list', 'FAIL',
             `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
      return report();
    }
    log('OK', `Created list '${LIST}'.`);
  } else {
    log('INFO', `List '${LIST}' already exists — topping up.`);
  }

  const addField = async (schemaXml) => {
    digest = await getDigest();
    // No __metadata: the harness sends odata=nometadata, which REJECTS the
    // type hint rather than ignoring it.
    return spPost(`${fieldsPath}/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };
  const fieldExists = async (name) =>
    (await spGet(`${fieldsPath}/getbyinternalnameortitle('${name}')`)).ok;

  // Format="DateTime" is what makes this a date AND TIME column. A plain
  // Format="DateOnly" would have no time portion to argue about, and every
  // question below would be vacuous.
  if (!(await fieldExists(FIELD))) {
    const made = await addField(
      `<Field Type="DateTime" DisplayName="${FIELD}" Name="${FIELD}" Format="DateTime" />`);
    if (!made.ok) {
      record('BOOT', 'Create the DateTime column', 'FAIL',
             `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
      return report();
    }
    log('OK', `Created DateTime column '${FIELD}'.`);
  }

  // ---- Timestamps -----------------------------------------------------
  // Written as UTC ISO, which is how SharePoint stores and how REST wants
  // them. The site-local day they land on is TZ0's business.
  const at = (ms) => new Date(Date.now() + ms).toISOString();
  const HOUR = 3600 * 1000;
  const EARLIER_TODAY = at(-3 * HOUR);
  const LATER_TODAY = at(3 * HOUR);
  const YESTERDAY = at(-27 * HOUR);
  const TWO_DAYS = at(51 * HOUR);
  // Tomorrow at 23:00 in THIS browser's zone, converted to UTC. Read
  // alongside TZ0: if the zones differ this may be a different site-local
  // hour, which V6's evidence line records rather than hides.
  const tomorrowLate = new Date();
  tomorrowLate.setDate(tomorrowLate.getDate() + 1);
  tomorrowLate.setHours(23, 0, 0, 0);
  const TOMORROW_2300 = tomorrowLate.toISOString();

  const setValidation = async (formula) => {
    digest = await getDigest();
    return spPost(`${fieldsPath}/getbyinternalnameortitle('${FIELD}')`, {
      ValidationFormula: formula,
      ValidationMessage: 'probe rule',
    }, digest, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  };
  const clearValidation = () => setValidation('');

  const addItem = async (title, when) => {
    digest = await getDigest();
    const body = { Title: title };
    if (when) body[FIELD] = when;
    return spPost(itemsPath, body, digest);
  };

  // A save REFUSED by a validation formula and a save refused because the
  // probe is broken look identical if you only check `ok`. The message is
  // the discriminator, so it is always carried into the evidence.
  const trySave = async (title, when) => {
    const res = await addItem(title, when);
    return {
      saved: res.ok,
      detail: res.ok
        ? `saved as item ${res.body && res.body.Id}`
        : `HTTP ${res.status}: ${res.text.slice(0, 260)}`,
      id: res.ok && res.body ? res.body.Id : null,
    };
  };

  // ---- VN: NEGATIVE CONTROL for the validation surface ----------------
  const bogus = await setValidation('=[NoSuchColumnHere]>0');
  record('VN', 'NEGATIVE CONTROL: a ValidationFormula naming a missing column is refused',
         bogus.ok ? 'FAIL' : 'PASS',
         bogus.ok
           ? 'a formula referencing a non-existent column was ACCEPTED — this probe '
             + 'cannot detect a refused ValidationFormula, so treat V1 as unproven'
           : `refused with HTTP ${bogus.status}: ${bogus.text.slice(0, 260)}`);
  await clearValidation();

  // ---- V1 / V2: NOW() -------------------------------------------------
  const nowFormula = await setValidation(`=[${FIELD}]<=NOW()`);
  if (!nowFormula.ok) {
    record('V1', 'NOW() in a ValidationFormula', 'REFUSED',
           `HTTP ${nowFormula.status}: ${nowFormula.text.slice(0, 300)}`);
    record('V2', 'If NOW() was accepted, does it reject a future timestamp',
           'NOT APPLICABLE', 'NOW() was refused at V1, so there is nothing to evaluate');
  } else {
    // Accepted is the surprising branch. Read it back before believing it:
    // accepted-then-discarded is a distinct and worse outcome than either.
    const back = await spGet(
      `${fieldsPath}/getbyinternalnameortitle('${FIELD}')?$select=ValidationFormula`);
    const stored = back.ok && back.body ? back.body.ValidationFormula : null;
    record('V1', 'NOW() in a ValidationFormula',
           stored ? 'ACCEPTED' : 'ACCEPTED THEN DISCARDED',
           `HTTP ${nowFormula.status}; reads back ${JSON.stringify(stored)}`);
    // Inert is the outcome that would fool a deploy: it saves, it reads back
    // equal, every phase passes, and the rule never fires.
    const future = await trySave('V2 future by three hours', LATER_TODAY);
    record('V2', 'If NOW() was accepted, does it reject a future timestamp',
           future.saved ? 'ACCEPTED BUT INERT' : 'ENFORCED',
           future.saved
             ? `a timestamp three hours in the future SAVED despite the rule — ${future.detail}`
             : `refused as intended — ${future.detail}`);
  }
  await clearValidation();

  // ---- V3: the load-bearing assumption --------------------------------
  if (!SAME_DAY_OK) {
    record('V3', 'Under <= TODAY(), an item stamped EARLIER TODAY is rejected',
           'NOT ESTABLISHED', 'time-of-day gate closed — see TZ0');
  } else {
    const todayRule = await setValidation(`=[${FIELD}]<=TODAY()`);
    if (!todayRule.ok) {
      record('V3', 'Under <= TODAY(), an item stamped EARLIER TODAY is rejected',
             'NOT ESTABLISHED',
             `could not set the rule: HTTP ${todayRule.status} ${todayRule.text.slice(0, 200)}`);
    } else {
      const earlier = await trySave('V3 earlier today', EARLIER_TODAY);
      record('V3', 'Under <= TODAY(), an item stamped EARLIER TODAY is rejected',
             earlier.saved ? 'SAVED — assumption WRONG' : 'REJECTED — assumption HOLDS',
             earlier.saved
               ? 'a timestamp from earlier TODAY was accepted under <= TODAY(). Five '
                 + 'templates carry a today+1 allowance that may be unnecessary. '
                 + earlier.detail
               : 'TODAY() is midnight and rejects same-day timestamps, which is why '
                 + 'the today+1 allowance exists. ' + earlier.detail);
    }
    await clearValidation();
  }

  // ---- V4 / V5 / V6: the shipped idiom, and its exact ceiling ---------
  const allowance = await setValidation(`=[${FIELD}]<=TODAY()+1`);
  if (!allowance.ok) {
    for (const id of ['V4', 'V5', 'V6']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED',
             `could not set <= TODAY()+1: HTTP ${allowance.status} ${allowance.text.slice(0, 200)}`);
    }
  } else {
    if (!SAME_DAY_OK) {
      record('V4', 'Under <= TODAY()+1, an item stamped LATER TODAY saves',
             'NOT ESTABLISHED', 'time-of-day gate closed — see TZ0');
    } else {
      const later = await trySave('V4 later today', LATER_TODAY);
      record('V4', 'Under <= TODAY()+1, an item stamped LATER TODAY saves',
             later.saved ? 'PASS' : 'FAIL',
             later.saved
               ? 'the shipped idiom accepts a same-day timestamp, as intended. ' + later.detail
               : 'the shipped idiom REJECTS a same-day timestamp — five templates would '
                 + 'refuse ordinary entries. ' + later.detail);
    }

    const twoDays = await trySave('V5 two days out', TWO_DAYS);
    record('V5', 'Under <= TODAY()+1, an item stamped TWO DAYS out is rejected',
           twoDays.saved ? 'FAIL' : 'PASS',
           twoDays.saved
             ? 'the allowance is wider than one day — it did NOT reject +51 hours. ' + twoDays.detail
             : 'rejected as intended. ' + twoDays.detail);

    // The comments in five templates say "any time today passes, next month
    // does not" and are silent on tomorrow. This is the row that lets them
    // say something true about the actual ceiling.
    const tomorrowNight = await trySave('V6 tomorrow 23:00', TOMORROW_2300);
    record('V6', 'Under <= TODAY()+1, the exact ceiling (tomorrow 23:00)',
           tomorrowNight.saved ? 'ALLOWANCE IS ~48H' : 'ALLOWANCE IS ~24H',
           `${TOMORROW_2300} (23:00 tomorrow in THIS browser's zone; read with TZ0) `
           + (tomorrowNight.saved
             ? 'SAVED, so TODAY()+1 permits the whole of tomorrow — the allowance is '
               + 'about 48 hours, not 24, and the template comments should say so. '
             : 'was REJECTED, so TODAY()+1 is a midnight ceiling and the allowance is '
               + 'about 24 hours. ')
           + tomorrowNight.detail);
  }
  await clearValidation();

  // ---- Seed the two rows the CAML questions compare -------------------
  // Created AFTER validation is cleared, so a leftover rule cannot silently
  // stop the CAML fixtures from existing.
  const seeded = {
    earlier: (await trySave('CAML earlier today', EARLIER_TODAY)),
    later: (await trySave('CAML later today', LATER_TODAY)),
    yesterday: (await trySave('CAML yesterday', YESTERDAY)),
  };
  const camlReady = seeded.earlier.saved && seeded.later.saved && seeded.yesterday.saved;
  if (!camlReady) {
    log('FAIL', 'Could not seed the CAML fixture rows; C-rows will report NOT ESTABLISHED.');
    log('INFO', `earlier: ${seeded.earlier.detail}`);
    log('INFO', `later:   ${seeded.later.detail}`);
    log('INFO', `yesterday: ${seeded.yesterday.detail}`);
  }

  // CamlQuery is one of the few endpoints that still wants odata=verbose:
  // the entity needs its __metadata type hint, which nometadata rejects.
  const caml = async (whereXml, includeTime) => {
    digest = await getDigest();
    const viewXml = `<View><Query><Where>${whereXml}</Where></Query><RowLimit>100</RowLimit></View>`;
    const res = await spPost(`web/lists/getbytitle('${LIST}')/getitems`, {
      query: { __metadata: { type: 'SP.CamlQuery' }, ViewXml: viewXml },
    }, digest, {
      Accept: 'application/json;odata=verbose',
      'Content-Type': 'application/json;odata=verbose',
    });
    const rows = res.ok && res.body && res.body.d ? (res.body.d.results || []) : [];
    return {
      ok: res.ok,
      status: res.status,
      titles: rows.map((r) => r.Title).sort(),
      text: res.text,
      viewXml,
      includeTime,
    };
  };
  const value = (inner, includeTime) =>
    `<Value Type="DateTime"${includeTime ? " IncludeTimeValue='TRUE'" : ''}>${inner}</Value>`;
  const ltWhen = (inner, includeTime) =>
    `<Lt><FieldRef Name="${FIELD}"/>${value(inner, includeTime)}</Lt>`;

  const has = (titles, t) => titles.includes(t);
  // The whole point: "earlier today" in and "later today" out. Anything
  // else means the comparison is not seeing the time portion.
  const verdictFor = (r) => {
    const e = has(r.titles, 'CAML earlier today');
    const l = has(r.titles, 'CAML later today');
    if (e && !l) return 'DISCRIMINATES (time compared)';
    if (e && l) return 'BOTH RETURNED (time ignored, compared as a later boundary)';
    if (!e && !l) return 'NEITHER RETURNED (time ignored, compared as midnight)';
    return 'INVERTED — later-today returned but earlier-today did not';
  };

  // ---- CN: NEGATIVE CONTROL for the CAML surface ----------------------
  if (!camlReady) {
    record('CN', 'NEGATIVE CONTROL: CAML containing a bogus <Nowww/> is refused',
           'NOT ESTABLISHED', 'the fixture rows could not be created');
  } else {
    const junk = await caml(ltWhen('<Nowww/>', false), false);
    record('CN', 'NEGATIVE CONTROL: CAML containing a bogus <Nowww/> is refused',
           junk.ok ? 'FAIL' : 'PASS',
           junk.ok
             ? `a query containing <Nowww/> was ACCEPTED and returned ${junk.titles.length} `
               + 'row(s) — SharePoint is not validating this element, so C1-C5 prove '
               + 'nothing about <Now/> being real'
             : `refused with HTTP ${junk.status}: ${junk.text.slice(0, 260)}`);
  }

  // ---- C1: the deploy surface -----------------------------------------
  // deploy.js writes ViewQuery and verifies by read-back, so "saves and
  // survives the round trip" is the question that decides whether a `now`
  // sentinel could be shipped at all.
  const VIEW = 'dbmlsp probe now view';
  digest = await getDigest();
  const viewQuery = `<Where>${ltWhen('<Now/>', true)}</Where>`;
  const madeView = await spPost(`web/lists/getbytitle('${LIST}')/views`, {
    Title: VIEW,
    ViewQuery: viewQuery,
    RowLimit: 100,
  }, digest);
  if (!madeView.ok) {
    record('C1', 'A view ViewQuery containing <Now/> saves and reads back intact',
           'REFUSED', `HTTP ${madeView.status}: ${madeView.text.slice(0, 300)}`);
  } else {
    const back = await spGet(
      `web/lists/getbytitle('${LIST}')/views/getbytitle('${VIEW}')?$select=ViewQuery`);
    const stored = back.ok && back.body ? (back.body.ViewQuery || '') : '';
    record('C1', 'A view ViewQuery containing <Now/> saves and reads back intact',
           stored.includes('<Now') ? 'PASS' : 'ACCEPTED THEN REWRITTEN',
           `sent ${JSON.stringify(viewQuery)}; stored ${JSON.stringify(stored)}`);
  }

  // ---- C2-C5: what the comparison actually does -----------------------
  const camlRows = [
    ['C2', '<Now/> WITHOUT IncludeTimeValue discriminates within one day', '<Now/>', false],
    ['C3', "<Now/> WITH IncludeTimeValue='TRUE' discriminates within one day", '<Now/>', true],
    ['C4', "<Today/> WITH IncludeTimeValue='TRUE': midnight, or current instant", '<Today/>', true],
    ['C5', 'BASELINE: <Today/> without IncludeTimeValue is date-granular', '<Today/>', false],
  ];
  for (const [id, question, inner, includeTime] of camlRows) {
    if (!camlReady || !SAME_DAY_OK) {
      record(id, question, 'NOT ESTABLISHED',
             !camlReady ? 'the fixture rows could not be created'
                        : 'time-of-day gate closed — see TZ0');
      continue;
    }
    const r = await caml(ltWhen(inner, includeTime), includeTime);
    if (!r.ok) {
      record(id, question, 'REFUSED', `HTTP ${r.status}: ${r.text.slice(0, 260)}`);
      continue;
    }
    // Yesterday's row is the sanity check: any sane "< now-ish" filter must
    // return it. If it does not, the query ran but is not doing what its
    // shape suggests, and the earlier/later reading is not worth having.
    const sane = has(r.titles, 'CAML yesterday');
    record(id, question, sane ? verdictFor(r) : 'SUSPECT — yesterday not returned',
           `${r.viewXml} -> ${JSON.stringify(r.titles)}`);
  }

  // ---- E1: the client-side expression target --------------------------
  // Storage only. Whether a show/hide rule FIRES is a rendering behaviour
  // no headless probe can see — form-visibility-interactive.js exists
  // precisely because this project learned that the hard way. A PASS here
  // means "SharePoint kept the formula", never "the rule works".
  const clientRule = await spPost(
    `${fieldsPath}/getbyinternalnameortitle('${FIELD}')`,
    { ClientValidationFormula: `=if(@now > [$${FIELD}], 'true', 'false')` },
    await getDigest(), { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  if (!clientRule.ok) {
    record('E1', '@now is accepted and stored in a ClientValidationFormula',
           'REFUSED', `HTTP ${clientRule.status}: ${clientRule.text.slice(0, 300)}`);
  } else {
    const back = await spGet(
      `${fieldsPath}/getbyinternalnameortitle('${FIELD}')?$select=ClientValidationFormula`);
    const stored = back.ok && back.body ? back.body.ClientValidationFormula : null;
    record('E1', '@now is accepted and stored in a ClientValidationFormula',
           stored && String(stored).includes('@now') ? 'STORED' : 'ACCEPTED THEN DISCARDED',
           `reads back ${JSON.stringify(stored)}. STORAGE ONLY — whether the rule `
           + 'actually fires needs an eyes-on check in the form designer, exactly as '
           + 'form-visibility-interactive.js does.');
  }

  // ---- Q1-Q4: escaping a double quote in a validation literal ---------
  // The subject is a CHOICE column, because that is where an awkward value
  // realistically comes from: a template author writes an enum member with
  // an apostrophe or a quote in it and the tool renders it into a rule.
  const QUOTED = 'He said "hi"';
  const PLAIN = 'plain';
  const QFIELD = 'ProbeQuote';
  const xmlAttr = (s) => String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  if (!(await fieldExists(QFIELD))) {
    await addField(
      `<Field Type="Choice" DisplayName="${QFIELD}" Name="${QFIELD}" Format="Dropdown">`
      + `<CHOICES><CHOICE>${xmlAttr(PLAIN)}</CHOICE>`
      + `<CHOICE>${xmlAttr(QUOTED)}</CHOICE></CHOICES></Field>`);
  }
  const quoteReady = await fieldExists(QFIELD);

  const setQuoteRule = async (formula) => {
    digest = await getDigest();
    return spPost(`${fieldsPath}/getbyinternalnameortitle('${QFIELD}')`, {
      ValidationFormula: formula,
      ValidationMessage: 'probe quote rule',
    }, digest, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  };
  const addQuoteItem = async (title, choice) => {
    digest = await getDigest();
    const res = await spPost(itemsPath, { Title: title, [QFIELD]: choice }, digest);
    return { saved: res.ok, detail: res.ok ? `saved as ${res.body && res.body.Id}`
                                           : `HTTP ${res.status}: ${res.text.slice(0, 220)}` };
  };

  if (!quoteReady) {
    for (const id of ['Q1', 'Q2', 'Q3', 'Q4']) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED',
             `could not create the '${QFIELD}' Choice column`);
    }
  } else {
    // This is exactly what _validation_literal emits today.
    const doubled = `=[${QFIELD}]<>"He said ""hi"""`;
    const setDoubled = await setQuoteRule(doubled);
    if (!setDoubled.ok) {
      record('Q1', 'A validation literal doubling an embedded " is accepted', 'REFUSED',
             `sent ${JSON.stringify(doubled)}; HTTP ${setDoubled.status}: `
             + setDoubled.text.slice(0, 260));
      for (const id of ['Q2', 'Q3']) {
        record(id, RESULTS.find((r) => r.id === id).question, 'NOT APPLICABLE',
               'the doubled-quote formula was refused at Q1');
      }
    } else {
      const back = await spGet(
        `${fieldsPath}/getbyinternalnameortitle('${QFIELD}')?$select=ValidationFormula`);
      const stored = back.ok && back.body ? back.body.ValidationFormula : null;
      record('Q1', 'A validation literal doubling an embedded " is accepted',
             stored ? 'ACCEPTED' : 'ACCEPTED THEN DISCARDED',
             `sent ${JSON.stringify(doubled)}; stored ${JSON.stringify(stored)}`);

      // Accepted is not parsed. If the literal were read as He said "" hi ""
      // or truncated at the first quote, the rule would still save happily
      // and simply never match the value it was written for.
      const rejected = await addQuoteItem('Q2 quoted value', QUOTED);
      record('Q2', '...and rejects an item holding exactly that value',
             rejected.saved ? 'FAIL — literal did NOT match' : 'PASS — literal matched',
             rejected.saved
               ? `an item set to ${JSON.stringify(QUOTED)} SAVED under a rule that `
                 + 'forbids exactly that value, so the doubled escape does not parse '
                 + `to the intended literal. ${rejected.detail}`
               : `refused as intended. ${rejected.detail}`);

      // Without this, "rejects everything" would read as a pass above.
      const allowed = await addQuoteItem('Q3 plain value', PLAIN);
      record('Q3', '...and leaves a different value alone',
             allowed.saved ? 'PASS' : 'FAIL — rule rejects everything',
             allowed.saved
               ? `a different value saved, so Q2 was a real match rather than a `
                 + `blanket refusal. ${allowed.detail}`
               : `the rule refused an unrelated value too, so Q2 proves nothing. `
                 + allowed.detail);
    }

    // The alternative convention. Accepted-and-wrong is the interesting
    // outcome: it would mean an author could write a formula by hand that
    // saves, reads back and quietly never fires.
    const backslash = `=[${QFIELD}]<>"He said \\"hi\\""`;
    const setBackslash = await setQuoteRule(backslash);
    if (!setBackslash.ok) {
      record('Q4', 'The backslash convention instead: accepted, and does it parse',
             'REFUSED — doubling is the only convention',
             `sent ${JSON.stringify(backslash)}; HTTP ${setBackslash.status}: `
             + setBackslash.text.slice(0, 260));
    } else {
      const hit = await addQuoteItem('Q4 quoted value under backslash rule', QUOTED);
      record('Q4', 'The backslash convention instead: accepted, and does it parse',
             hit.saved ? 'ACCEPTED BUT DOES NOT MATCH' : 'ACCEPTED AND MATCHES',
             hit.saved
               ? 'the backslash form saved but did NOT reject the value it names — a '
                 + `hand-written rule using it would never fire. ${hit.detail}`
               : `the backslash form also parses correctly. ${hit.detail}`);
    }
    await setQuoteRule('');
  }

  report();
  console.log('\nHOW TO READ THIS RUN');
  console.log('  VN and CN must both be PASS. If either is FAIL, the surface it');
  console.log('  guards proved nothing and its rows are unproven, not wrong.');
  console.log('  V3 decides whether the today+1 allowance in five templates is');
  console.log('  necessary. V6 decides whether it is a 24-hour or 48-hour window.');
  console.log('  C2/C3 decide whether a `now` sentinel could do anything a view');
  console.log('  cannot already do; C5 confirms what seven shipped views get today.');
  log('INFO', `Done. Delete '${LIST}' when you have copied the results.`);
})();
