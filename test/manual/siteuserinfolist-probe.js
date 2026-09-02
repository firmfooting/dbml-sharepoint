/**
 * dbml-sharepoint PROBE (READ-ONLY): THE SITE USER INFORMATION LIST AS A
 * REPORTING DIMENSION
 *
 * QUESTION: can the reporting pack build a `_Users` table from this site's
 * user information list, and do the ids a person column carries resolve to
 * rows in it?
 *
 * WHY: `_Users.pq` (behind `reporting.users_table`) selects internal field
 * names, joins on the id a person column carries, and has to be readable by
 * the reporting account. None of that is documented as REST internal names,
 * and this project does not guess at SharePoint.
 *
 * WHAT IT ASKS
 *   U1  can the account running this read /_api/web/siteuserinfolist, and
 *       what is that account (site admin or not, permission mask)?
 *   U2  which candidate internal field names exist on that list?
 *   U3  how many rows, of which principal kinds, with which fields populated?
 *   U4  do the ids in a real person column on one of this site's lists
 *       resolve to rows in the user information list with the same Title?
 *   U5  what shape does /items give Created, Modified, Author and Editor?
 *
 * Every request is a GET. It prints counts, field names, list titles and
 * column names, never a person's name, email or login.
 *
 * HOW TO RUN: open the site, F12 -> Console, paste, Enter; it prints the
 * web it would read. Set CONFIRMED = true and paste again. Copy the RESULTS
 * block back verbatim. Run it a second time as a READER-tier account so U1
 * answers the permission question for reporting readers.
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

  expect('access.principal.userinfolist-readable', 'siteuserinfolist is readable by this account');
  expect('access.principal.userinfolist-fields-present', 'which candidate internal fields the list has');
  expect('access.principal.userinfolist-principal-mix', 'row count, principal kinds and populated fields');
  expect('access.principal.person-column-ids-resolve', 'a person column\'s ids resolve to rows with the same Title');
  expect('field.person.system-columns-item-shape', 'the shape /items gives Created, Modified, Author and Editor');

  if (!CONFIRMED) {
    log('INFO', `Would read the user information list and one list's items on ${WEB}.`);
    log('INFO', 'Nothing is written by this probe. Set CONFIRMED = true and paste again.');
    return;
  }
  const enc = (t) => encodeURIComponent(t.replace(/'/g, "''"));
  const brief = (r) => `HTTP ${r.status} ${JSON.stringify(r.body || '').slice(0, 160)}`;

  // ---- U1: readable, and by whom --------------------------------------
  const me = await spGet('web/currentuser?$select=Id,IsSiteAdmin');
  const perms = await spGet('web/effectivebasepermissions');
  const list = await spGet('web/siteuserinfolist?$select=Title,ItemCount,Hidden');
  if (readFailed(list)) {
    record('access.principal.userinfolist-readable', 'siteuserinfolist is readable by this account', 'FAIL',
      `not readable: ${brief(list)}; current user Id=${me.body && me.body.Id} IsSiteAdmin=${me.body && me.body.IsSiteAdmin}`);
    return report();
  }
  record('access.principal.userinfolist-readable', 'siteuserinfolist is readable by this account', 'PASS',
    `Title="${list.body.Title}" ItemCount=${list.body.ItemCount} Hidden=${list.body.Hidden}; `
    + `current user Id=${me.body && me.body.Id} IsSiteAdmin=${me.body && me.body.IsSiteAdmin}; `
    + `effective permissions High=${perms.body && perms.body.High} Low=${perms.body && perms.body.Low}`);

  // ---- U2: which candidate fields exist -------------------------------
  const CANDIDATE_FIELDS = [
    'Title', 'Name', 'EMail', 'UserName', 'Department', 'JobTitle', 'Office',
    'FirstName', 'LastName', 'WorkPhone', 'MobilePhone', 'SipAddress',
    'Picture', 'IsSiteAdmin', 'Deleted', 'UserInfoHidden', 'ContentTypeId',
  ];
  const fields = await spGet(
    'web/siteuserinfolist/fields?$select=InternalName,TypeAsString,Hidden,ReadOnlyField&$top=500');
  if (readFailed(fields)) {
    record('access.principal.userinfolist-fields-present', 'which candidate internal fields the list has', 'FAIL', `fields not readable: ${brief(fields)}`);
    return report();
  }
  const byName = new Map((fields.body.value || []).map((f) => [f.InternalName, f]));
  const present = CANDIDATE_FIELDS.filter((n) => byName.has(n));
  const absent = CANDIDATE_FIELDS.filter((n) => !byName.has(n));
  record('access.principal.userinfolist-fields-present', 'which candidate internal fields the list has', 'PASS',
    'present: ' + present.map((n) => {
      const f = byName.get(n);
      return `${n}(${f.TypeAsString}${f.Hidden ? ',hidden' : ''}${f.ReadOnlyField ? ',readonly' : ''})`;
    }).join(', ') + ` | absent: ${absent.join(', ') || 'none'} | fields on list: ${byName.size}`);

  // ---- U3: rows, principal mix, populated counts ---------------------
  const selectable = present.filter((n) => n !== 'ContentTypeId');
  const items = await spGet(
    `web/siteuserinfolist/items?$select=Id,ContentTypeId,${selectable.join(',')}&$top=5000`);
  if (readFailed(items)) {
    record('access.principal.userinfolist-principal-mix', 'row count, principal kinds and populated fields', 'FAIL', `items not readable: ${brief(items)}`);
  } else {
    const rows = items.body.value || [];
    const populated = (v) => {
      if (v === null || v === undefined) return false;
      if (typeof v === 'string') return v.trim() !== '';
      if (typeof v === 'object') return Boolean(v.Url || v.Description);
      return true;
    };
    const counts = selectable.map((n) => `${n}=${rows.filter((r) => populated(r[n])).length}`);
    // Content type ids: 0x010A a person, 0x010B a SharePoint group, 0x010C a domain group.
    const kind = (ct) => {
      if (!ct) return 'unknown';
      if (ct.startsWith('0x010A')) return 'Person';
      if (ct.startsWith('0x010B')) return 'SharePointGroup';
      if (ct.startsWith('0x010C')) return 'DomainGroup';
      return `other(${ct.slice(0, 6)})`;
    };
    const mix = {};
    for (const r of rows) mix[kind(r.ContentTypeId)] = (mix[kind(r.ContentTypeId)] || 0) + 1;
    record('access.principal.userinfolist-principal-mix', 'row count, principal kinds and populated fields', 'PASS',
      `rows=${rows.length}${rows.length === 5000 ? ' (page limit hit)' : ''}; `
      + `principals: ${Object.entries(mix).map(([k, v]) => `${k}=${v}`).join(', ')}; `
      + `populated: ${counts.join(', ')}`);
  }

  // ---- U4: a real person column's ids resolve in the list --------------
  const lists = await spGet('web/lists?$select=Title,ItemCount,BaseTemplate,Hidden&$top=200');
  let verdict = null;
  let probeList = null;
  if (!readFailed(lists)) {
    const generic = (lists.body.value || [])
      .filter((l) => !l.Hidden && l.BaseTemplate === 100 && l.ItemCount > 0)
      .slice(0, 25);
    for (const l of generic) {
      const lf = await spGet(
        `web/lists/getbytitle('${enc(l.Title)}')/fields?$select=InternalName,TypeAsString,Hidden&$top=500`);
      if (readFailed(lf)) continue;
      const person = (lf.body.value || []).find((f) => f.TypeAsString === 'User'
        && !f.Hidden && f.InternalName !== 'Author' && f.InternalName !== 'Editor');
      if (!person) continue;
      const col = person.InternalName;
      const sample = await spGet(
        `web/lists/getbytitle('${enc(l.Title)}')/items?$select=Id,${col}Id,${col}/Title&$expand=${col}&$top=10`);
      if (readFailed(sample)) {
        verdict = ['FAIL', `list "${l.Title}" column ${col}: sample read failed: ${brief(sample)}`];
        break;
      }
      const pairs = [];
      for (const r of sample.body.value || []) {
        const ids = Array.isArray(r[`${col}Id`]) ? r[`${col}Id`] : [r[`${col}Id`]];
        const titles = Array.isArray(r[col]) ? r[col].map((x) => x && x.Title) : [r[col] && r[col].Title];
        ids.forEach((id, i) => { if (id !== null && id !== undefined) pairs.push([id, titles[i]]); });
      }
      if (!pairs.length) continue;
      probeList = l.Title;
      let matched = 0;
      const seen = new Set();
      for (const [id, title] of pairs) {
        if (seen.has(id)) continue;
        seen.add(id);
        const u = await spGet(`web/siteuserinfolist/items(${id})?$select=Id,Title`);
        if (!readFailed(u) && u.body.Title === title) matched += 1;
      }
      verdict = [matched === seen.size ? 'PASS' : 'FAIL',
        `list "${l.Title}" column ${col}: ${seen.size} distinct id(s) checked, `
        + `${matched} resolved in siteuserinfolist with the same Title`];
      break;
    }
  }
  record('access.principal.person-column-ids-resolve', 'a person column\'s ids resolve to rows with the same Title',
    verdict ? verdict[0] : 'NOT ESTABLISHED',
    verdict ? verdict[1] : 'no visible generic list with rows and a person column was found');

  // ---- U5: system columns on /items -----------------------------------
  const candidates = (lists.body && lists.body.value) || [];
  const target = probeList
    || (candidates.find((l) => !l.Hidden && l.BaseTemplate === 100 && l.ItemCount > 0) || {}).Title;
  if (!target) {
    record('field.person.system-columns-item-shape', 'the shape /items gives Created, Modified, Author and Editor', 'NOT ESTABLISHED',
      'no visible generic list with rows to read one item from');
  } else {
    const one = await spGet(
      `web/lists/getbytitle('${enc(target)}')/items`
      + '?$select=Id,Created,Modified,AuthorId,Author/Title,EditorId,Editor/Title&$expand=Author,Editor&$top=1');
    const row = !readFailed(one) && one.body.value && one.body.value[0];
    if (!row) {
      record('field.person.system-columns-item-shape', 'the shape /items gives Created, Modified, Author and Editor', 'FAIL', `list "${target}": ${brief(one)}`);
    } else {
      const keys = Object.keys(row).sort().join(',');
      const shape = (v) => (typeof v === 'string' ? v.replace(/\d/g, '9') : typeof v);
      record('field.person.system-columns-item-shape', 'the shape /items gives Created, Modified, Author and Editor', 'PASS',
        `list "${target}": keys=${keys}; `
        + `Author.Title ${row.Author && 'Title' in row.Author ? 'present' : 'absent'}; `
        + `Editor.Title ${row.Editor && 'Title' in row.Editor ? 'present' : 'absent'}; `
        + `Created shape=${shape(row.Created)}; Modified shape=${shape(row.Modified)}; `
        + `AuthorId type=${typeof row.AuthorId}; EditorId type=${typeof row.EditorId}`);
    }
  }
  return report();
})();
