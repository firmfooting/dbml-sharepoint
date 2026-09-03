/**
 * dbml-sharepoint PROBE (READ-ONLY): WHAT INSTANT A DATE-ONLY COLUMN STORES
 *
 * QUESTION: when the modern form saves a date-only value, does SharePoint
 * store it as midnight in the SITE's zone, or as midnight UTC (which reads
 * as 10:00 in a UTC+10 site and so sits after a midnight TODAY())?
 *
 * WHY: a rule `=[D]<=TODAY()` refusing today's date past 10:00 local, on a
 * site in UTC+10 with a correct server clock, is explained by a stored time
 * of day and by nothing else the site settings show.
 *
 * WHAT IT PRINTS (dates and ids only; no titles, no names)
 *   Z   the site's regional time zone and this browser's offset
 *   S   the server's own clock, from a fresh response's Date header
 *   D1  for the newest rows of the first list in READS: its date columns
 *       as stored (UTC instants) beside Created and Modified
 *   D2  the same for the second list, whose date column the SERVER fills
 *       from a [today] default, so the server's own "today at midnight"
 *       is visible here
 *
 * HOW TO READ IT: a value picked as the 2nd stored as ...-01T14:00:00Z is
 * site-local midnight in UTC+10; stored as ...-02T00:00:00Z it is UTC
 * midnight, 10:00 local. Compare a form-picked date with a server-filled one.
 *
 * HOW TO RUN: set LIST1 and LIST2 to name two lists on the site (the defaults
 * are the adoption program's); the date columns printed follow READS below.
 * F12 -> Console, paste, Enter; set CONFIRMED = true and paste again. Copy the
 * RESULTS block back.
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
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT'];
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

  const LIST1 = 'ADOPT_ProgramAction';
  const LIST2 = 'ADOPT_ProgramIssue';
  const COLUMNS1 = 'DueDate,CompletedDate';
  const COLUMNS2 = 'RaisedDate,ResolvedDate';

  // Operator-set: which lists and which date columns to print. LIST1/LIST2
  // and COLUMNS1/COLUMNS2 are simple consts so the agent runner can arm them
  // in memory with --set LIST1='<name>' --set COLUMNS1='A,B'; the split into
  // READS happens here so the arming grammar stays bool/number/string.
  const READS = [
    { list: LIST1, columns: COLUMNS1.split(','), orderBy: 'Modified' },
    { list: LIST2, columns: COLUMNS2.split(','), orderBy: 'Created' },
  ];

  expect('field.date.control-site-time-zone', 'the site zone and this browser\'s offset');
  expect('field.date.control-server-clock', 'the server clock from a response Date header');
  expect('field.date.stored-instant-form-picked', `stored instants of ${READS[0].columns.join(', ')} on the first list`);
  expect('field.date.stored-instant-default-filled', `stored instants of ${READS[1].columns.join(', ')} on the second list`);

  if (!CONFIRMED) {
    log('INFO', `Would read the site zone and the newest rows of ${READS.map((r) => `'${r.list}'`).join(' and ')} on ${WEB}.`);
    log('INFO', 'Nothing is written by this probe. Set CONFIRMED = true and paste again.');
    return;
  }
  const enc = (t) => encodeURIComponent(t.replace(/'/g, "''"));
  // The harness's spGet drops response headers; the server clock needs one.
  const dated = await fetch(`${WEB}/_api/web/regionalsettings/timezone`, {
    headers: { Accept: 'application/json;odata=nometadata' },
  });
  const tz = await dated.json().catch(() => null);
  const info = tz && tz.Information;
  record('field.date.control-site-time-zone', 'the site zone and this browser\'s offset', dated.ok ? 'PASS' : 'FAIL',
    dated.ok
      ? `site zone "${tz.Description}" bias=${info && info.Bias} standard=${info && info.StandardBias} daylight=${info && info.DaylightBias}; browser offset ${-new Date().getTimezoneOffset()} min; browser now ${new Date().toISOString()}`
      : `could not read the site zone: HTTP ${dated.status}`);
  record('field.date.control-server-clock', 'the server clock from a response Date header', 'PASS', `server Date header: ${dated.headers.get('date')}`);

  for (const [index, read] of READS.entries()) {
    const id = `D${index + 1}`;
    const question = `stored instants of ${read.columns.join(', ')} on the ${index ? 'second' : 'first'} list`;
    const select = ['Id', ...read.columns, 'Created', 'Modified'].join(',');
    const rows = await spGet(
      `web/lists/getbytitle('${enc(read.list)}')/items?$select=${select}&$orderby=${read.orderBy} desc&$top=5`);
    if (readFailed(rows)) {
      record(id, question, 'FAIL', `could not read '${read.list}': HTTP ${rows.status}`);
      continue;
    }
    const lines = (rows.body.value || []).map((r) =>
      `id=${r.Id} ${read.columns.map((c) => `${c}=${r[c]}`).join(' ')} Created=${r.Created} Modified=${r.Modified}`);
    record(id, question, lines.length ? 'PASS' : 'NOT ESTABLISHED',
      lines.length ? `'${read.list}': ${lines.join(' | ')}` : `'${read.list}' has no rows`);
  }
  return report();
})();
