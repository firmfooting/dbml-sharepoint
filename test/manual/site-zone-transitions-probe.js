/**
 * dbml-sharepoint PROBE (READ-ONLY): DOES SHAREPOINT AGREE WITH THE SHIPPED
 * TRANSITION TABLE
 *
 * QUESTION: the reporting pack ships a declared IANA zone's daylight-saving
 * transitions, generated from Python's zoneinfo, and converts UTC timestamps
 * by them (reporting.time_zone; analysis/timezones.py). On a site set to that
 * zone, does SharePoint's own conversion, utctolocaltime, apply the offset
 * the table names one minute before each sampled transition, and the new
 * offset at the transition itself? And are the two offsets the site reports
 * as biases exactly the offsets the table uses, which is what the emitted
 * Zone[resolved] check requires?
 *
 * WHY: Power Query has no time zone database and the site's TimeZone object
 * carries Bias, StandardBias and DaylightBias only, so nothing in a refresh
 * can check the table. The only place it can be checked against the
 * platform's own answer is here, where utctolocaltime is one request away.
 *
 * WHAT IT PRINTS (offsets and instants only; no titles, no names)
 *   Z   the site's regional time zone and its three biases
 *   U   whether utctolocaltime answers a parseable wall clock at all
 *   B   whether the declared zone's offsets equal the site's two candidates
 *   T1  for each sampled transition, the offset SharePoint applies one
 *       minute BEFORE it, beside the offset the table says was in force
 *   T2  the same AT the transition instant, beside the table's new offset
 *   Each T row also prints this browser's own answer for the zone through
 *   Intl, a third database, so a disagreement can be placed.
 *
 * HOW TO READ IT: SharePoint answers with a wall clock carrying no zone, so
 * the offset is that wall clock minus the instant sent, in minutes. A T row
 * PASSES when every sampled instant comes back with the table's offset.
 *
 * HOW TO RUN: set ZONE to the IANA name the mapping declares; it must be a
 * key of SAMPLES below and the zone the site is set to. F12 -> Console,
 * paste, Enter; set CONFIRMED = true and paste again. Copy the RESULTS
 * block back.
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

  // Operator-set: the IANA zone the mapping declares. Must be one of the
  // keys of SAMPLES, and the zone the site's regional settings name.
  const ZONE = 'Australia/Melbourne';

  // Three transitions per zone, each as the pack's own SiteTransitions row
  // (the UTC instant the offset changes, and the minutes east of UTC from
  // then on) beside the offset in force before it. COPIED from what
  // analysis/timezones.py derives, and test_site_zone pins every row here
  // against that derivation, so the probe cannot drift from what ships.
  const SAMPLES = {
    'Australia/Melbourne': [
      { at: '2025-10-04T16:00:00Z', before: 600, after: 660 },
      { at: '2026-04-04T16:00:00Z', before: 660, after: 600 },
      { at: '2026-10-03T16:00:00Z', before: 600, after: 660 },
    ],
    'Australia/Lord_Howe': [
      { at: '2025-10-04T15:30:00Z', before: 630, after: 660 },
      { at: '2026-04-04T15:00:00Z', before: 660, after: 630 },
      { at: '2026-10-03T15:30:00Z', before: 630, after: 660 },
    ],
    'Europe/London': [
      { at: '2025-10-26T01:00:00Z', before: 60, after: 0 },
      { at: '2026-03-29T01:00:00Z', before: 0, after: 60 },
      { at: '2026-10-25T01:00:00Z', before: 60, after: 0 },
    ],
    'America/New_York': [
      { at: '2025-11-02T06:00:00Z', before: -240, after: -300 },
      { at: '2026-03-08T07:00:00Z', before: -300, after: -240 },
      { at: '2026-11-01T06:00:00Z', before: -240, after: -300 },
    ],
  };
  const rows = SAMPLES[ZONE] || [];

  expect('field.date.control-site-time-zone', 'the site zone and its biases');
  expect('field.date.control-utctolocaltime-answers', 'utctolocaltime answers a parseable wall clock');
  expect('field.date.shipped-offsets-match-site-biases', `the offsets ${ZONE} uses equal the site's two candidates`);
  expect('field.date.shipped-transition-offset-before', `SharePoint's offset one minute before each sampled ${ZONE} transition`);
  expect('field.date.shipped-transition-offset-after', `SharePoint's offset at each sampled ${ZONE} transition`);

  if (!CONFIRMED) {
    log('INFO', `Would read the site zone on ${WEB} and ask utctolocaltime for ${rows.length * 2 + 1} instants around ${ZONE}'s transitions.`);
    log('INFO', 'Nothing is written by this probe. Set CONFIRMED = true and paste again.');
    return;
  }
  if (!rows.length) {
    log('FAIL', `ZONE '${ZONE}' is not a key of SAMPLES; nothing to compare against.`);
    return report();
  }

  const tz = await spGet('web/RegionalSettings/TimeZone');
  const info = (tz.ok && tz.body && tz.body.Information) || null;
  record('field.date.control-site-time-zone', 'the site zone and its biases', info ? 'PASS' : 'FAIL',
    info
      ? `site zone "${tz.body.Description}" bias=${info.Bias} standard=${info.StandardBias} daylight=${info.DaylightBias}; declared ${ZONE}`
      : `could not read the site zone: HTTP ${tz.status}`);

  // Ask SharePoint to render a known UTC instant in the site's own zone. The
  // reply is a WALL CLOCK carrying no zone, so it is read through Date.UTC
  // to keep it one; parsing the string directly would apply this browser's
  // offset and answer a different question. Same two URL shapes as
  // datetime-sentinel-probe.js, which measured both on a live tenant.
  const siteLocalOffsetMin = async (whenUtc) => {
    const stamp = encodeURIComponent(whenUtc.toISOString());
    for (const path of [
      `web/RegionalSettings/TimeZone/utctolocaltime('${stamp}')`,
      `web/RegionalSettings/TimeZone/utctolocaltime(@d)?@d='${stamp}'`,
    ]) {
      const r = await spGet(path);
      if (readFailed(r)) continue;
      const value = typeof r.body === 'string' ? r.body
        : r.body.value !== undefined ? r.body.value : r.body.UTCToLocalTime;
      const parts = typeof value === 'string'
        && value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/);
      if (!parts) continue;
      const wall = Date.UTC(+parts[1], +parts[2] - 1, +parts[3], +parts[4], +parts[5], +parts[6]);
      return { offsetMin: Math.round((wall - whenUtc.getTime()) / 60000), value };
    }
    return null;
  };

  // This browser's own zone database, as a third opinion beside the table
  // and SharePoint. Evidence only: nothing here passes or fails on it.
  const intlOffsetMin = (whenUtc) => {
    try {
      const parts = new Intl.DateTimeFormat('en-US', {
        timeZone: ZONE, hourCycle: 'h23', year: 'numeric', month: 'numeric',
        day: 'numeric', hour: 'numeric', minute: 'numeric', second: 'numeric',
      }).formatToParts(whenUtc);
      const get = (type) => +parts.find((p) => p.type === type).value;
      const wall = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'));
      return Math.round((wall - whenUtc.getTime()) / 60000);
    } catch {
      return null;
    }
  };

  const control = await siteLocalOffsetMin(new Date('2026-01-15T00:00:00Z'));
  record('field.date.control-utctolocaltime-answers', 'utctolocaltime answers a parseable wall clock',
    control ? 'PASS' : 'FAIL',
    control
      ? `2026-01-15T00:00:00Z -> "${control.value}", offset ${control.offsetMin} min`
      : 'neither utctolocaltime URL shape answered a parseable datetime');

  // The check the emitted query makes: the site's two candidates, as the
  // query builds them (minutes EAST of UTC, so the Win32 sign is flipped),
  // must be exactly the distinct offsets the shipped table uses.
  const distinctSorted = (values) => [...new Set(values)].sort((a, b) => a - b);
  const declared = distinctSorted(rows.flatMap((r) => [r.before, r.after]));
  if (info) {
    const site = distinctSorted([-(info.Bias + info.StandardBias), -(info.Bias + info.DaylightBias)]);
    const agree = site.length === declared.length && site.every((v, i) => v === declared[i]);
    record('field.date.shipped-offsets-match-site-biases', `the offsets ${ZONE} uses equal the site's two candidates`,
      agree ? 'PASS' : 'FAIL',
      `site candidates {${site.join(', ')}}; ${ZONE} uses {${declared.join(', ')}}`);
  } else {
    record('field.date.shipped-offsets-match-site-biases', `the offsets ${ZONE} uses equal the site's two candidates`,
      'NOT ESTABLISHED', 'the site zone was not read, so there are no candidates to compare', 'void');
  }

  if (!control) {
    for (const id of ['field.date.shipped-transition-offset-before', 'field.date.shipped-transition-offset-after']) {
      record(id, `SharePoint's offset around each sampled ${ZONE} transition`,
        'NOT ESTABLISHED', 'utctolocaltime did not answer, so no offset was observed', 'void');
    }
    return report();
  }

  // One request per instant, so a throttled or refused call reads as a
  // missing observation for THAT instant rather than as a disagreement.
  const before = [];
  const after = [];
  for (const row of rows) {
    const at = new Date(row.at);
    const minuteBefore = new Date(at.getTime() - 60000);
    const spBefore = await siteLocalOffsetMin(minuteBefore);
    const spAt = await siteLocalOffsetMin(at);
    before.push({
      row, observed: spBefore, expected: row.before, intl: intlOffsetMin(minuteBefore),
    });
    after.push({ row, observed: spAt, expected: row.after, intl: intlOffsetMin(at) });
  }
  const verdict = (checks) => {
    if (checks.some((c) => c.observed === null)) return 'NOT ESTABLISHED';
    return checks.every((c) => c.observed.offsetMin === c.expected) ? 'PASS' : 'FAIL';
  };
  const describe = (checks, when) => checks.map((c) =>
    `${c.row.at} ${when}: SharePoint ${c.observed ? c.observed.offsetMin : 'no answer'}, table ${c.expected}, browser Intl ${c.intl === null ? 'unavailable' : c.intl}`).join(' | ');
  record('field.date.shipped-transition-offset-before',
    `SharePoint's offset one minute before each sampled ${ZONE} transition`,
    verdict(before), describe(before, '-1 min'));
  record('field.date.shipped-transition-offset-after',
    `SharePoint's offset at each sampled ${ZONE} transition`,
    verdict(after), describe(after, 'at'));
  return report();
})();
