/**
 * dbml-sharepoint PROBE (READ-ONLY unless ALLOW_WRITES): WHERE DOES THE
 * LAGGING `today` COME FROM, AND WHICH SURFACES SHARE IT?
 *
 * QUESTION: TODAY() and NOW() in validation formulas were measured hours
 * behind the site. Is the source the signed-in user's own regional settings
 * (profile properties SPS-RegionalSettings-FollowWeb and SPS-TimeZone), or a
 * clock nobody on the site can change? And do view filters (<Today/>) and
 * column defaults ([today]) read the same clock?
 *
 * Runs against the scratch list `dbml-probe-today-semantics` left by the
 * today-semantics probe, which holds T, a date-only column with default
 * formula =TODAY(). That probe does NOT create DM, the date-only column V2
 * and V3 compare, so with ALLOW_WRITES this one adds DM and seeds yesterday's
 * and today's site-local midnight into it.
 *
 * WHAT IT ASKS
 *   Z    site zone, browser offset, server clock
 *   P    the signed-in user's profile regional properties
 *   V1   CAML `T Eq <Today/>`: ALL rows means <Today/> reads the lagging
 *        clock; NONE means it reads the site's date
 *   V2   CAML `DM Eq <Today/>`: which day's rows it returns. Its evidence
 *        also carries whether DM and its two rows had to be created
 *   V3   CAML `DM Eq <Today OffsetDays='-1'/>`: which day's rows
 *   V4   CAML `Modified Leq <Today IncludeTimeValue='TRUE'/>`: every row was
 *        modified recently, so ALL means the instant is current and NONE
 *        means it is hours behind
 *   D1   (only with ADD_DEFAULT_COLUMN) adds TD, date only, dynamic default
 *        [today], creates a bare item through REST, and prints what the
 *        server filled. Then open the list's New form and read the prefilled
 *        TD yourself: that is the FORM's [today].
 *
 * HOW TO RUN: F12 -> Console on the site, paste, Enter; set CONFIRMED = true
 * and paste again. Backfilling DM needs ALLOW_WRITES, and V2 and V3 cannot be
 * answered without it; D1 needs ADD_DEFAULT_COLUMN on top of that.
 * Copy the RESULTS block back.
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
    // a person records the observation; so does void, which is open for a
    // reason the control row names.
    const open = RESULTS.filter((r) => r.state !== 'settled').length;
    const waiting = RESULTS.filter((r) => r.state === 'awaiting-capture').length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} open.`);
    if (waiting) {
      console.log(`${waiting} of those are waiting on an observation somebody has to make.`);
    }
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };
  const ADD_DEFAULT_COLUMN = false;
  const LIST = 'dbml-probe-today-semantics';

  expect('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock');
  expect('access.principal.profile-regional-settings', 'the signed-in user\'s profile regional properties');
  expect('query.caml-adhoc.today-element-vs-today-function', 'CAML T Eq <Today/> matches the =TODAY()-filled rows');
  expect('query.caml-adhoc.today-element-site-date', 'CAML DM Eq <Today/> returns which day');
  expect('query.caml-adhoc.today-offset-element-previous-day', 'CAML DM Eq <Today OffsetDays=-1/> returns which day');
  expect('query.caml-adhoc.today-include-time-current-instant', 'CAML Modified Leq <Today IncludeTimeValue/> sees recent rows');
  expect('field.date.dynamic-default-rest-fill', 'a [today] dynamic default filled through REST');

  if (!CONFIRMED) {
    log('INFO', `Would read the site zone, the profile, and query '${LIST}' on ${WEB}.`);
    log('INFO', `With ALLOW_WRITES it would add DM and two dated rows to '${LIST}' if absent.`);
    log('INFO', `With ADD_DEFAULT_COLUMN it would also add a column and one item to '${LIST}'.`);
    log('INFO', 'Set CONFIRMED = true and paste again.');
    return;
  }
  const enc = (t) => encodeURIComponent(t.replace(/'/g, "''"));
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };

  const dated = await fetch(`${WEB}/_api/web/regionalsettings/timezone`, {
    headers: { Accept: 'application/json;odata=nometadata' },
  });
  const tz = await dated.json().catch(() => null);
  record('formula.datetime.control-site-time-zone', 'site zone, browser offset and server clock', dated.ok ? 'PASS' : 'FAIL',
    `site zone "${tz && tz.Description}"; browser offset ${-new Date().getTimezoneOffset()} min; browser now ${new Date().toISOString()}; server ${dated.headers.get('date')}`);

  // ---- P: the user's own regional settings, from the profile ----------------
  const me = await spGet('SP.UserProfiles.PeopleManager/GetMyProperties?$select=UserProfileProperties');
  const wanted = ['SPS-RegionalSettings-FollowWeb', 'SPS-RegionalSettings-Initialized', 'SPS-TimeZone', 'SPS-Locale', 'SPS-CalendarType', 'SPS-TimeFormat', 'SPS-Time24'];
  const props = {};
  for (const kv of (me.body && me.body.UserProfileProperties) || []) {
    if (wanted.includes(kv.Key)) props[kv.Key] = kv.Value;
  }
  record('access.principal.profile-regional-settings', 'the signed-in user\'s profile regional properties', readFailed(me) ? 'FAIL' : 'PASS',
    readFailed(me)
      ? `profile not readable: HTTP ${me.status}`
      : wanted.map((k) => `${k}=${props[k] === undefined ? '(absent)' : props[k] === '' ? '(empty)' : props[k]}`).join('; '));

  // ---- V1..V4: what <Today/> means in a CAML query ------------------------
  const listPath = `web/lists/getbytitle('${enc(LIST)}')`;

  // today-semantics creates D, W and T and no DM, so on the 2026-09-02 run V2
  // and V3 came back HTTP 500 "One or more field types are not installed
  // properly" rather than answering. DM is backfilled here instead.
  const nowLocal = new Date();
  const localMidnightUtc = (days) =>
    new Date(nowLocal.getFullYear(), nowLocal.getMonth(), nowLocal.getDate() + days, 0, 0, 0, 0).toISOString();
  const ensureDm = async () => {
    const titles = ((await spGet(`${listPath}/fields?$select=Title&$top=500`)).body?.value || []).map((f) => f.Title);
    const present = titles.includes('DM');
    if (!present) {
      if (!ALLOW_WRITES) return 'DM absent and ALLOW_WRITES is false, so it was not created';
      const made = await spPost(`${listPath}/fields`, {
        __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: 'DM', DisplayFormat: 0,
      }, await getDigest(), VERBOSE);
      if (!made.ok) return `DM create refused: HTTP ${made.status} ${made.text.slice(0, 160)}`;
    }
    const head = `DM ensured (${present ? 'already present' : 'created'})`;
    const before = await spGet(`${listPath}/items?$select=Id,Title,DM&$top=500`);
    if (readFailed(before)) return `${head}; DM values not readable: HTTP ${before.status}`;
    const carrying = (before.body.value || []).filter((r) => r.DM);
    if (carrying.length) {
      return `${head}; rows seeded (${carrying.length} present): ${carrying.map((r) => `#${r.Id} ${r.Title} DM=${r.DM}`).join(', ')}`;
    }
    if (!ALLOW_WRITES) return `${head}; no row carries DM and ALLOW_WRITES is false, so none were seeded`;
    const itemType = (await spGet(`${listPath}?$select=ListItemEntityTypeFullName`)).body?.ListItemEntityTypeFullName;
    for (const [title, value] of [['dm-yesterday', localMidnightUtc(-1)], ['dm-today', localMidnightUtc(0)]]) {
      const made = await spPost(`${listPath}/items`, {
        __metadata: { type: itemType }, Title: title, DM: value,
      }, await getDigest(), VERBOSE);
      if (!made.ok) return `${head}; seeding ${title} refused: HTTP ${made.status} ${made.text.slice(0, 160)}`;
    }
    // Read back rather than trust the writes: the stored value is what V2 and
    // V3 are about to compare.
    const after = await spGet(`${listPath}/items?$select=Id,Title,DM&$top=500`);
    if (readFailed(after)) return `${head}; rows seeded (2) but not readable back: HTTP ${after.status}`;
    return `${head}; rows seeded (2): ${(after.body.value || []).filter((r) => r.DM).map((r) => `#${r.Id} ${r.Title} DM=${r.DM}`).join(', ')}`;
  };
  const dmNote = await ensureDm();

  const caml = async (where, fieldNames) => {
    const digest = await getDigest();
    const viewFields = [...fieldNames, 'ID'].map((f) => `<FieldRef Name='${f}'/>`).join('');
    const r = await spPost(`${listPath}/getitems`, {
      query: {
        __metadata: { type: 'SP.CamlQuery' },
        ViewXml: `<View><ViewFields>${viewFields}</ViewFields><Query><Where>${where}</Where></Query><RowLimit>200</RowLimit></View>`,
      },
    }, digest, VERBOSE);
    if (!r.ok) return { count: null, detail: `query refused: HTTP ${r.status} ${r.text.slice(0, 160)}` };
    const rows = (r.body && r.body.d && r.body.d.results) || [];
    return {
      count: rows.length,
      detail: `${rows.length} row(s): ${rows.map((x) => `#${x.ID}${fieldNames.map((f) => ` ${f}=${x[f]}`).join('')}`).join(', ') || '(none)'}`,
    };
  };
  const rows = [
    ['query.caml-adhoc.today-element-vs-today-function', 'CAML T Eq <Today/> matches the =TODAY()-filled rows', "<Eq><FieldRef Name='T'/><Value Type='DateTime'><Today/></Value></Eq>", ['T']],
    ['query.caml-adhoc.today-element-site-date', 'CAML DM Eq <Today/> returns which day', "<Eq><FieldRef Name='DM'/><Value Type='DateTime'><Today/></Value></Eq>", ['DM']],
    ['query.caml-adhoc.today-offset-element-previous-day', 'CAML DM Eq <Today OffsetDays=-1/> returns which day', "<Eq><FieldRef Name='DM'/><Value Type='DateTime'><Today OffsetDays='-1'/></Value></Eq>", ['DM']],
    ['query.caml-adhoc.today-include-time-current-instant', 'CAML Modified Leq <Today IncludeTimeValue/> sees recent rows', "<Leq><FieldRef Name='Modified'/><Value Type='DateTime' IncludeTimeValue='TRUE'><Today/></Value></Leq>", ['Modified']],
  ];
  for (const [id, question, where, fieldNames] of rows) {
    const got = await caml(where, fieldNames);
    const evidence = id === 'query.caml-adhoc.today-element-site-date'
      ? `${dmNote}; ${got.detail}` : got.detail;
    record(id, question, got.count === null ? 'FAIL' : 'PASS', evidence);
  }

  // ---- D1: the dynamic default, server side ----------------------------------
  if (!ADD_DEFAULT_COLUMN) {
    record('field.date.dynamic-default-rest-fill', 'a [today] dynamic default filled through REST', 'NOT APPLICABLE', 'ADD_DEFAULT_COLUMN is off');
  } else if (!ALLOW_WRITES) {
    record('field.date.dynamic-default-rest-fill', 'a [today] dynamic default filled through REST', 'NOT ESTABLISHED', 'ADD_DEFAULT_COLUMN needs ALLOW_WRITES');
  } else {
    const have = new Set(((await spGet(`${listPath}/fields?$select=Title&$top=500`)).body?.value || []).map((f) => f.Title));
    let created = 'TD already present';
    if (!have.has('TD')) {
      const r = await spPost(`${listPath}/fields`, {
        __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: 'TD', DisplayFormat: 0, DefaultValue: '[today]',
      }, await getDigest(), VERBOSE);
      created = r.ok ? 'TD created with default [today]' : `TD create refused: HTTP ${r.status} ${r.text.slice(0, 160)}`;
    }
    const meta = await spGet(`${listPath}?$select=ListItemEntityTypeFullName`);
    const made = await spPost(`${listPath}/items`, {
      __metadata: { type: meta.body && meta.body.ListItemEntityTypeFullName }, Title: 'default-today',
    }, await getDigest(), VERBOSE);
    if (made.ok) {
      const back = await spGet(`${listPath}/items(${made.body.d.Id})?$select=Id,TD,T,Created`);
      record('field.date.dynamic-default-rest-fill', 'a [today] dynamic default filled through REST', 'PASS',
        `${created}; REST item with no dates: TD ([today]) = ${back.body && back.body.TD}; T (=TODAY() default) = ${back.body && back.body.T}; Created ${back.body && back.body.Created}. Now open New on the list and note the prefilled TD.`);
    } else {
      record('field.date.dynamic-default-rest-fill', 'a [today] dynamic default filled through REST', 'FAIL', `${created}; could not create the item: HTTP ${made.status} ${made.text.slice(0, 160)}`);
    }
  }
  return report();
})();
