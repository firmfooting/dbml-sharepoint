/** ---- dbml-sharepoint PROBE: A FILE PROPERTY UPDATE WHILE THE WORKBOOK IS OPEN ----
 *
 * REVISION: 32744000
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
 * column ProbeNote. Sign a second account in, in another browser, and open the
 * workbook in Excel for the web (OPENED_IN = 'web') or Excel desktop
 * (OPENED_IN = 'desktop'); keep it open while the STATE = 'open' paste runs.
 *
 * DEPENDS ON
 *   library.file.fixture-open-workbook          WORKBOOK_URL reads back as a file with a list
 *       item that has an integer Id, an item type and ProbeNote
 *   library.file.control-properties-update-closed  the same MERGE, sent with STATE = 'closed'
 *       after the second account has closed the workbook, answers 2xx and reads back
 *
 * OBSERVES (recorded verbatim, never compared with an expected value)
 *   library.file.properties-update-while-open-web      with OPENED_IN = 'web': the MERGE's status,
 *       its body's first 300 characters, its duration, and ProbeNote read back after it
 *   library.file.properties-update-while-open-desktop  the same with OPENED_IN = 'desktop'
 *
 * HOW TO RUN: F12 -> Console. Set CONFIRMED, ALLOW_WRITES, WORKBOOK_URL (the
 * file's server-relative path), OPENED_IN and STATE ('open' first, 'closed'
 * after); paste; Enter. Copy the RESULTS block back verbatim.
 */
(async () => {
  // ---- Operator gate -------------------------------------------------
  // All default false. Pasting an unedited probe prints its plan and
  // stops; nothing touches the tenant until the operator opts in.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;

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

  // ---- The question ----------------------------------------------------
  const STATE = 'open'; // 'open' while the second account has the workbook open, then 'closed'
  const OPENED_IN = ''; // 'web' or 'desktop': where the second account has it open
  // The workbook's server-relative path, typed at paste time and never committed.
  const WORKBOOK_URL = '';
  const FIXTURE = 'library.file.fixture-open-workbook';
  const CONTROL = 'library.file.control-properties-update-closed';
  const CHECKS = {
    web: 'library.file.properties-update-while-open-web',
    desktop: 'library.file.properties-update-while-open-desktop',
  };
  const NOTE = 'ProbeNote';
  const RUN = Date.now().toString(36);
  const ASK = 'what a property update answers while a second account has the workbook open';

  expect('library.file.fixture-open-workbook', 'the workbook reads back as a file with a list item that has ProbeNote');
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
  if (!Object.prototype.hasOwnProperty.call(CHECKS, OPENED_IN)) {
    log('FAIL', `OPENED_IN is '${OPENED_IN}'; it must be 'web' or 'desktop'. Nothing was sent.`);
    return report();
  }

  // Apostrophes doubled for OData, then percent-encoded so & , and # reach the server whole.
  const lit = (text) => encodeURIComponent(String(text).replace(/'/g, "''")).replace(/%2F/g, '/');
  const itemAt = `web/GetFileByServerRelativePath(decodedurl='${lit(WORKBOOK_URL)}')/ListItemAllFields`;
  const read = () => spGet(`${itemAt}?$select=Id,${NOTE},ListItemEntityTypeFullName`);
  const dependents = [CONTROL, CHECKS[OPENED_IN]];

  let item = null;
  if (!await establishFixture(FIXTURE, async () => (item = await read()), {
    Id: (v) => Number.isInteger(v),
    ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0,
    [NOTE]: (v) => v === null || typeof v === 'string',
  }, dependents)) return report();

  // The write is verbose with the item type, as the other probes write list items.
  const write = async () => {
    const started = Date.now();
    const res = await spPost(itemAt, { __metadata: { type: item.body.ListItemEntityTypeFullName }, [NOTE]: RUN },
      await getDigest(), {
        Accept: 'application/json;odata=verbose',
        'Content-Type': 'application/json;odata=verbose',
        'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE',
      });
    return { res, ms: Date.now() - started };
  };
  const readBack = async () => {
    const back = await read();
    return back.ok && back.body ? `read back: ${JSON.stringify(back.body[NOTE])} (wrote ${JSON.stringify(RUN)})`
      : `the read back ${unanswered(back)}`;
  };

  if (STATE === 'closed') {
    const { res, ms } = await write();
    const back = res.ok ? await read() : null;
    const held = res.ok && back.ok && back.body && back.body[NOTE] === RUN;
    record(CONTROL, 'the same property update reads back once the workbook is closed',
      held ? 'PASS' : 'FAIL', `HTTP ${res.status} in ${ms} ms; ${back ? await readBack() : res.text.slice(0, 300)}`);
    return report();
  }

  const { res, ms } = await write();
  // OBSERVED whatever the status: a refusal is the finding, so it is never a failure of the probe.
  const answered = `HTTP ${res.status} in ${ms} ms; body: ${res.text.slice(0, 300)}`;
  record(CHECKS[OPENED_IN], ASK, 'OBSERVED', `${answered}; ${await readBack()}`);
  record(CONTROL, 'the same property update reads back once the workbook is closed', 'MANUAL',
    "close the workbook in the second account, then paste again with STATE = 'closed'");
  return report();
})();
