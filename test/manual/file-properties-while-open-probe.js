/** ---- dbml-sharepoint PROBE: A FILE PROPERTY UPDATE WHILE THE WORKBOOK IS OPEN ----
 *
 * REVISION: c3315e97
 *
 * QUESTION: while a second account has a library workbook open in Excel for the
 * web (or in Excel desktop), can the first account set a column on that file,
 * and what does the request answer?
 *
 * WHY: a person sets Status to Complete while the workbook may still be open,
 * and a flow then runs an Office Script on it. If the property update is
 * refused while the workbook is open, the flow's lock case cannot arise from
 * that save. Learn does not say what a co-authoring session does to a list
 * item update on the same file.
 *
 * SETUP (by hand): put a small .xlsx in a library on this site that has a text
 * column ProbeNotes. Sign a second account in, in another browser, and open the
 * workbook in Excel for the web (OPENED_IN = 'web') or Excel desktop
 * (OPENED_IN = 'desktop'); keep it open while the STATE = 'open' paste runs.
 *
 * DEPENDS ON
 *   library.file.fixture-open-workbook          WORKBOOK_URL reads back as a file with a list
 *       item that has an integer Id, an item type and ProbeNotes
 *   library.file.control-properties-update-closed  the same MERGE, sent with STATE = 'closed'
 *       after the second account has closed the workbook, answers 2xx and reads back
 *
 * OBSERVES (recorded verbatim, never compared with an expected value)
 *   library.file.properties-update-while-open-web      with OPENED_IN = 'web': the MERGE's status,
 *       its body's first 300 characters, its duration, and ProbeNotes read back after it
 *   library.file.properties-update-while-open-desktop  the same with OPENED_IN = 'desktop'
 *
 * HOW TO RUN: F12 -> Console. Set CONFIRMED, ALLOW_WRITES, WORKBOOK_URL (the
 * file's server-relative path), OPENED_IN, STATE ('open' first, 'closed' after)
 * and SECOND_ACCOUNT_HAS_IT_OPEN (true for the open paste) or
 * SECOND_ACCOUNT_HAS_CLOSED_IT (true for the closed one); paste; Enter. Copy the
 * RESULTS block back verbatim. Both pastes overwrite ProbeNotes, and the open
 * paste's fixture row records its original value: restore it by hand afterwards.
 */
(async () => {
  // Gates default false: an unedited paste prints its plan and sends nothing.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

  // No SITE_URL constant: a tenant URL committed to this repo has leaked before, so the probe reads the page's site.
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

  // `body` is the parsed payload even on failure, so `body !== null` never means the call worked; test `ok`.
  const readFailed = (r) => !r.ok || r.body === null;

  // Refusal means the server rejected the content; 401/403/408/429/503 are about who or when, so never refusals.
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 503 // 503: the other documented throttle
    && status !== 502 && status !== 504; // gateway failures: no content-specific answer

  // extraHeaders carries X-HTTP-Method: SharePoint tunnels MERGE and DELETE through POST.
  const spPost = async (path, payload, digest, extraHeaders = {}) => {
    if (!ALLOW_WRITES) throw new Error('spPost refused: ALLOW_WRITES is false.');
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
  // The response text is returned rather than thrown, because a refusal is often the finding.
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };

  // Evidence is recorded apart from outcome; questions are registered up front as NOT ESTABLISHED and record() overwrites; state is one of settled, open, awaiting-capture, void, needs-human (SURFACES.md); ABORTED is open.
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

  // Why a response carries no reading, or null when it does; 429 and 503 are Learn's throttle statuses.
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

  // `read` resolves to { ok, status, body }; PASS needs every declared property read back, else FAIL and void `dependents`.
  const establishFixture = async (id, read, declared, dependents) => {
    const row = RESULTS.find((r) => r.id === id);
    const question = row ? row.question : id;
    const problems = [];
    const seen = [];
    let got = null;
    let silentWhy = null; // a read that said nothing about the fixture: a re-run can clear it
    try {
      got = await read();
    } catch (err) {
      silentWhy = `the read threw: ${err && err.message ? err.message : String(err)}`;
    }
    if (!silentWhy) {
      const silent = got && typeof got === 'object' ? unanswered(got) : 'returned no response';
      if (silent && got && typeof got === 'object' && !got.ok && isRefusal(got.status)) problems.push(`the read ${silent}`);
      else if (silent) silentWhy = `the read ${silent}`;
    }
    if (silentWhy && !problems.length) {
      record(id, question, 'NOT ESTABLISHED', silentWhy, 'open');
      return false;
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

  const REVISION = 'c3315e97';
  const report = () => {
    console.log('\n==================== RESULTS ====================');
    console.log(`probe revision ${REVISION}. Quote this when reporting results.`);
    console.log(`target: ${new URL(WEB).origin}${WORKBOOK_URL}`);
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(6)} ${r.state.padEnd(16)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
  // Counted off state so summary and rows agree; void is counted apart because no re-run can clear it.
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

  // ---- The question ----------------------------------------------------
  const STATE = 'open'; // 'open' while the second account has the workbook open, then 'closed'
  const OPENED_IN = ''; // 'web' or 'desktop': where the second account has it open
  // Server-relative path, typed at paste time and never committed.
  const WORKBOOK_URL = '';
  // Nothing the probe sends can see the second account's session, so the operator attests to it.
  const SECOND_ACCOUNT_HAS_IT_OPEN = false;
  // For STATE 'closed'; exactly one of the two attestations is true in a run.
  const SECOND_ACCOUNT_HAS_CLOSED_IT = false;
  const FIXTURE = 'library.file.fixture-open-workbook';
  const CONTROL = 'library.file.control-properties-update-closed';
  const CHECKS = {
    web: 'library.file.properties-update-while-open-web',
    desktop: 'library.file.properties-update-while-open-desktop',
  };
  const NOTE = 'ProbeNotes';
  const RUN = Date.now().toString(36);
  const ASK = 'what a property update answers while a second account has the workbook open';

  expect('library.file.fixture-open-workbook', 'the workbook reads back as a file with a list item that has ProbeNotes');
  expect('library.file.control-properties-update-closed', 'the same property update reads back once the workbook is closed');
  expect('library.file.properties-update-while-open-web', ASK + ' (Excel for the web)');
  expect('library.file.properties-update-while-open-desktop', ASK + ' (Excel desktop)');

  if (!CONFIRMED || !ALLOW_WRITES || !WORKBOOK_URL) {
    log('INFO', `Would set ${NOTE} on the file at WORKBOOK_URL on ${WEB} (STATE = '${STATE}').`);
    log('INFO', 'Nothing has been sent. Set WORKBOOK_URL, OPENED_IN, CONFIRMED and ALLOW_WRITES.');
    return report();
  }
  if (STATE !== 'open' && STATE !== 'closed') {
    log('FAIL', `STATE is '${STATE}'; it must be 'open' or 'closed'. Nothing was sent.`);
    return report();
  }
  if (STATE === 'closed' && (!SECOND_ACCOUNT_HAS_CLOSED_IT || SECOND_ACCOUNT_HAS_IT_OPEN)) {
    log('FAIL', "STATE is 'closed' but SECOND_ACCOUNT_HAS_CLOSED_IT is not true, or SECOND_ACCOUNT_HAS_IT_OPEN is "
      + 'not false; a control sent while the workbook may be open proves nothing. Nothing was sent.');
    return report();
  }
  if (STATE === 'open' && (!SECOND_ACCOUNT_HAS_IT_OPEN || SECOND_ACCOUNT_HAS_CLOSED_IT)) {
    log('FAIL', "STATE is 'open' but SECOND_ACCOUNT_HAS_IT_OPEN is not true (or CLOSED_IT is true); the open paste means nothing "
      + 'unless a second account has the workbook open. Nothing was sent.');
    return report();
  }
  if (!Object.prototype.hasOwnProperty.call(CHECKS, OPENED_IN)) {
    log('FAIL', `OPENED_IN is '${OPENED_IN}'; it must be 'web' or 'desktop'. Nothing was sent.`);
    return report();
  }

  const run = async () => {
  // Apostrophes doubled for OData, then percent-encoded so & , and # reach the server whole.
  const lit = (text) => encodeURIComponent(String(text).replace(/'/g, "''")).replace(/%2F/g, '/');
  const fileAt = `web/GetFileByServerRelativePath(decodedurl='${lit(WORKBOOK_URL)}')`;
  const itemAt = `${fileAt}/ListItemAllFields`;
  const read = () => spGet(`${itemAt}?$select=Id,${NOTE}`);
  // The item type is a property of the containing list, not of the item (Learn, Working with lists and list items with REST).
  const readFixture = async () => {
    const got = await read();
    if (!got.ok || got.body === null) return got;
    const parent = await spGet(`${itemAt}/ParentList?$select=ListItemEntityTypeFullName`);
    if (!parent.ok || parent.body === null) return parent;
    return { ok: true, status: got.status, body: { ...got.body,
      ListItemEntityTypeFullName: parent.body.ListItemEntityTypeFullName } };
  };
  const dependents = [CONTROL, CHECKS.web, CHECKS.desktop];
  const CONTROL_Q = 'the same property update reads back once the workbook is closed';

  let item = null;
  if (!await establishFixture(FIXTURE, async () => (item = await readFixture()), {
    Id: (v) => Number.isInteger(v),
    ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0,
    [NOTE]: (v) => v === null || typeof v === 'string',
  }, dependents)) return report();

  // The write is verbose with the item type, as the other probes write list items.
  const write = async () => {
    const digest = await getDigest();
    const started = Date.now();
    try {
      const res = await spPost(itemAt, { __metadata: { type: item.body.ListItemEntityTypeFullName }, [NOTE]: RUN },
        digest, {
          Accept: 'application/json;odata=verbose',
          'Content-Type': 'application/json;odata=verbose',
          'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE',
        });
      return { res, ms: Date.now() - started };
    } catch (err) {
      // The request may have been committed before the browser lost the answer, so the caller reads back.
      return { res: null, ms: Date.now() - started, err: err && err.message ? err.message : String(err) };
    }
  };
  // Whether the per-run token is present after a request that never answered.
  const tokenRead = async () => {
    try { return describe(await read()).replace('requested', 'token'); } catch (e2) {
      return `the read back threw: ${e2 && e2.message ? e2.message : String(e2)}`;
    }
  };
  const uncertain = async (err, ms) => {
    const back = await tokenRead();
    return `the MERGE rejected after ${ms} ms before any answer (${err}); the write is uncertain; ${back}`;
  };
  // Non-answering statuses say nothing about the update, and a SharePoint refusal is a 500 only with an error payload.
  const hasErrorPayload = (r) => !!(r.body && (r.body.error || r.body['odata.error']));
  const bare500 = (r) => r.status === 500 && !hasErrorPayload(r);
  const noAnswer = (r) => !r.ok && (!isRefusal(r.status) || bare500(r));
  const silentWhy = (r) => (bare500(r) ? 'answered HTTP 500 with no SharePoint error payload' : unanswered(r));
  // File.LockedByUser is documented but its meaning under co-authoring is not, so only whether a user is named is recorded.
  const lockState = async () => {
    try {
      const r = await spGet(`${fileAt}/LockedByUser?$select=Id`);
      const named = r.ok && r.body && typeof r.body === 'object' && Number.isInteger(r.body.Id);
      const why = !r.ok ? 'unanswered' : !r.body || typeof r.body !== 'object' ? 'no readable payload'
        : 'the payload carried no integer Id';
      return `LockedByUser read: HTTP ${r.status}, ${named ? 'a user is named' : why}`;
    } catch (err) {
      return `LockedByUser read threw: ${err && err.message ? err.message : String(err)}`;
    }
  };
  const codeOf = (r) => {
    const e = r.body && (r.body.error || r.body['odata.error']);
    return e && e.code !== undefined ? String(e.code) : 'none';
  };
  const hasNote = (back) => !!(back.ok && back.body && Object.prototype.hasOwnProperty.call(back.body, NOTE));
  const describe = (back) => (hasNote(back)
    ? `read back: ${JSON.stringify(back.body[NOTE])} (requested ${JSON.stringify(RUN)})`
    : back.ok && back.body ? `the read back payload carries no ${NOTE}` : `the read back ${unanswered(back)}`);
  const answeredBy = (res, ms) => `HTTP ${res.status} in ${ms} ms; error.code: ${codeOf(res)}; body: ${res.text.slice(0, 300)}`;

  if (STATE === 'closed') {
    const { res, ms, err } = await write();
    if (!res) {
      record(CONTROL, CONTROL_Q, 'NOT ESTABLISHED', await uncertain(err, ms));
      return report();
    }
    if (noAnswer(res)) {
      record(CONTROL, CONTROL_Q, 'NOT ESTABLISHED',
        `the update ${silentWhy(res)}; ${answeredBy(res, ms)}; the write is uncertain; ${await tokenRead()}`);
      return report();
    }
    let back = null;
    try { back = res.ok ? await read() : null; } catch (e2) {
      back = { ok: false, status: 0, body: null, threw: e2 && e2.message ? e2.message : String(e2) };
    }
    // A readback that did not answer says nothing about the request shape, so it is not a failure of the control.
    if (back && (!back.ok || unanswered(back) || !hasNote(back))) {
      record(CONTROL, CONTROL_Q, 'NOT ESTABLISHED',
        `${answeredBy(res, ms)}; ${back.threw ? `the read back threw: ${back.threw}` : describe(back)}`);
      return report();
    }
    const held = res.ok && back.body && back.body[NOTE] === RUN;
    record(CONTROL, CONTROL_Q, held ? 'PASS' : 'FAIL',
      `${answeredBy(res, ms)}${back ? `; ${describe(back)}` : ''}`);
    if (!held) voidDependents([CHECKS.web, CHECKS.desktop], 'the closed control did not hold, so the same request proves nothing');
    return report();
  }

  const lockBefore = await lockState();
  const { res, ms, err } = await write();
  if (!res) {
    record(CHECKS[OPENED_IN], ASK, 'NOT ESTABLISHED', await uncertain(err, ms));
    return report();
  }
  if (noAnswer(res)) {
    record(CHECKS[OPENED_IN], ASK, 'NOT ESTABLISHED',
      `the update ${silentWhy(res)}; ${answeredBy(res, ms)}; the write is uncertain; ${await tokenRead()}`);
    return report();
  }
  // A malformed request is refused like a lock, so the row stays open until the closed control passes with this shape.
  const SETTLE = 'settled only when the closed control passes with the same request';
  const answered = answeredBy(res, ms);
  // Recorded before any further request, so the write's own answer survives a failure after it.
  record(CHECKS[OPENED_IN], ASK, 'OBSERVED', `${answered}; ${SETTLE}`, 'open');
  let back = null;
  let said = 'the read back threw';
  try { back = await read(); said = describe(back); } catch (err) { said = `the read back threw: ${err && err.message ? err.message : String(err)}`; }
  // An accepted update whose value was not read back is unverified, so it is not a finding.
  const unread = res.ok && !(back && hasNote(back));
  record(CHECKS[OPENED_IN], ASK, unread ? 'NOT ESTABLISHED' : 'OBSERVED',
    `${answered}; ${said}; before: ${lockBefore}; after: ${await lockState()}; ${SETTLE}`, 'open');
  record(CONTROL, CONTROL_Q, 'NOT ESTABLISHED',
    "close the workbook in the second account, then paste again with STATE = 'closed'", 'open');
  return report();
  };
  try {
    return await run();
  } catch (err) {
    log('FAIL', `the probe stopped: ${err && err.message ? err.message : String(err)}`);
    return report();
  }
})();
