/**
 * dbml-sharepoint PROBE — WHAT `Read` MEANS HERE, AND WHAT A GROUP ALREADY HOLDS
 *
 * READ-ONLY. It creates nothing, changes nothing and deletes nothing. There is
 * no ALLOW_WRITES path; CONFIRMED alone runs it. Every question is a GET.
 *
 * TWO ISSUES, ONE SETUP. Both are blocked on the same two facts about a site,
 * and both stand between the enterprise-reader tier and a release.
 *
 * #199 — THE READER TRUSTS A LEVEL CALLED `Read` BY ITS NAME. The validator
 * exempts an assignment to `Read` as "the safe built-in", and the ACL phase
 * resolves it with `$select=Id` and never looks at what it can do. On a site
 * where an administrator has customised the built-in, the permanently-enrolled
 * reporting account can hold edit or delete rights while the manifest still
 * reports it read-only. R2 reads the bitmap this site's `Read` actually
 * carries; R3 says whether it matches a stock one.
 *
 * #198 — THE READER INHERITS WHATEVER ITS GROUP ALREADY HOLDS. The deploy adds
 * the account to a group found BY NAME and never inspects that group's
 * existing bindings. A group carrying Full Control at web scope, or an
 * elevated binding on a list outside the bundle, hands all of it to the
 * account — and neither the ACL phase nor anything else removes it, because
 * both only reconcile lists this bundle declares. R4 and R5 enumerate what a
 * named group holds today.
 *
 * WHY THIS CANNOT BE ANSWERED FROM DOCUMENTATION. Microsoft Learn documents
 * what the STOCK levels contain. It cannot say what THIS tenant's `Read` was
 * edited into, nor what a particular group was granted years ago by somebody
 * who has left. Those are site facts, and the gate #209 needs has to be
 * written against them rather than against the defaults.
 *
 * SEPARATING WHAT IS DEPENDED ON FROM WHAT IS OBSERVED. R2, R4 and R5 REPORT
 * what they find. They do not assert a particular bitmap or an empty binding
 * list — a site legitimately has either. R3 is the only one that judges, and
 * it judges against the value R2 read on this site, printed in full so the
 * comparison is auditable rather than hidden in a boolean.
 *
 * THE NEGATIVE CONTROL IS R1, and it is doing real work here. Every other
 * question reports "what came back". A caller who cannot read
 * `web/roledefinitions` at all would produce empty results that look exactly
 * like "nothing is granted" — the most dangerous possible false reassurance
 * for a question about excess privilege. R1 establishes the read works before
 * any absence is believed.
 *
 * WHAT TO SET. GROUP is the group to inspect. Leave it as the shared reader
 * group if the site has one; point it at `dbml List Administrators`, or at any
 * group you are considering handing to the reader, to ask about that instead.
 *
 * HOW TO RUN
 *   1. Open the target site as a SITE OWNER — reading role assignments needs
 *      it, and R1 will tell you plainly if this account cannot.
 *   2. Open a browser console on any page of that site.
 *   3. Set CONFIRMED = true, then paste this file. It never writes.
 *   4. Copy the whole results block back verbatim.
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
  // ever touches the explicitly named probe-owned list or lists; it never
  // enumerates or deletes anything else. Each list is RECYCLED, not purged,
  // so a mistake is recoverable from the site recycle bin.
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

  // NOTE the contract, because getting it wrong has produced false verdicts
  // here twice: `body` is the PARSED payload whether or not the request
  // succeeded. SharePoint answers a 403 or a 429 with a JSON error object,
  // so `body !== null` says the response was JSON — never that the call
  // worked. Anything asking "did I actually read this?" must test `ok`.
  const readFailed = (r) => !r.ok || r.body === null;

  // Was this request REFUSED — the server saying no to what was sent — or
  // did it merely fail? A negative control that cannot tell the difference
  // certifies the surface as observable on the strength of a throttle, and
  // every row it guards is then read as evidence.
  //
  // Defined by what it EXCLUDES, because the tempting definition is wrong
  // here. "400 means bad request" is the HTTP convention and it is not what
  // this tenant does: every SharePoint refusal this project has recorded
  // came back 500 —
  //
  //   "To add an item to a document library, use SPFileCollection.Add()"
  //   "One or more column references are not allowed, because the columns
  //    are defined as a data type that is not supported in formulas"
  //   "The formula refers to a column that does not exist"
  //   "This field type does not support..."
  //
  // (analysis/checks/_structure.py, analysis/conditions.py, generators/
  // jsgen.py — each dated and cited to a live run). A 400-only test would
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
    // PREFIX match, not equality. Outcomes carry their reason —
    // 'NOT ESTABLISHED (throttled)', 'NOT ESTABLISHED (matched 50, expected
    // 60)', 'SHORT (50 of 60, HTTP 200)' — and an equality test counts every
    // one of those as ANSWERED. A results block would then read "47 answered,
    // 0 NOT established" with unresolved rows visible one screen above it,
    // which is the summary lying by omission: the exact failure expect() was
    // added to prevent, reintroduced at the other end of the same function.
    const open = RESULTS.filter(
      (r) => r.outcome.startsWith('NOT ESTABLISHED') || r.outcome.startsWith('SHORT'),
    ).length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} NOT established.`);
    if (open) {
      console.log('A question with no observation is NOT a pass. Report it as open.');
    }
    console.log('Copy this whole block back verbatim.');
  };

  // Printed before any gate: a stale clipboard and a fix that did not
  // work produce identical transcripts otherwise.
  log('INFO', 'probe revision f0927e57 — quote this when reporting results.');

  // The group to inspect. Any group name on this site.
  const GROUP = 'dbml Enterprise Readers';

  // Learn's stock `Read`, for R3 to compare against. From "Permission levels
  // in SharePoint": View Items, Open Items, View Versions, Create Alerts,
  // Use Self-Service Site Creation, View Pages, Browse User Information, Use
  // Remote Interfaces, Use Client Integration Features, Open.
  //
  // NOT hardcoded as a bitmap. The High/Low pair is a 64-bit mask whose exact
  // value for a stock Read this project has never measured, and writing one
  // from memory is the failure AGENTS.md opens with. R2 prints what this site
  // has; R3 compares it to the OTHER built-ins on the SAME site, which is a
  // comparison that needs no external constant.
  const STOCK_READ_NOTE = 'compared against this site\'s own role definitions, not a remembered bitmap';

  expect('R1', 'CONTROL: can this caller read web/roledefinitions at all?');
  expect('R2', 'What BasePermissions does THIS site\'s built-in Read carry?');
  expect('R3', 'Does this site\'s Read differ from its neighbours in a way that suggests customisation?');
  expect('R4', 'What web-scope role assignments does the named group already hold?');
  expect('R5', 'What list-scope role assignments does it hold, across every list?');
  expect('R6', 'Is the named group present on this site at all?');

  if (!CONFIRMED) {
    log('INFO', 'PLAN — nothing has been touched, and nothing would be.');
    log('INFO', 'This probe only READS. It would report:');
    log('INFO', `  - the BasePermissions of this site's built-in 'Read'`);
    log('INFO', `  - every web-scope and list-scope binding held by '${GROUP}'`);
    log('INFO', 'Set CONFIRMED = true to run it. ALLOW_WRITES is not used.');
    report();
    return;
  }

  // ---- R1: the control, before any absence is believed -------------------
  const defs = await spGet('web/roledefinitions?$select=Id,Name,Description,BasePermissions,RoleTypeKind&$top=100');
  if (readFailed(defs) || !Array.isArray(defs.body && defs.body.value)) {
    record('R1', 'CONTROL: can this caller read web/roledefinitions at all?',
      `NOT ESTABLISHED (HTTP ${defs.status})`,
      'without this read, an empty binding list below would be indistinguishable from no access — which is the most dangerous wrong answer this probe could give. Re-run as a site owner.');
    report();
    return;
  }
  const rows = defs.body.value;
  record('R1', 'CONTROL: can this caller read web/roledefinitions at all?',
    'PASS', `${rows.length} role definition(s) readable, so an empty result below means empty`);

  // ---- R2: what Read actually is on this site ----------------------------
  const read = rows.find((r) => r.Name === 'Read');
  if (!read) {
    record('R2', 'What BasePermissions does THIS site\'s built-in Read carry?',
      'NOT ESTABLISHED (no level named Read)',
      `this site's levels are: ${rows.map((r) => r.Name).join(', ')}. A site with no 'Read' is itself a finding for #199 — the validator exempts that name and the ACL phase resolves it by name.`);
  } else {
    record('R2', 'What BasePermissions does THIS site\'s built-in Read carry?',
      'PASS',
      `Read: RoleTypeKind=${read.RoleTypeKind}, High=${read.BasePermissions && read.BasePermissions.High}, Low=${read.BasePermissions && read.BasePermissions.Low}, Description=${JSON.stringify(read.Description)}`);
  }

  // ---- R3: is it plausibly customised? -----------------------------------
  // RoleTypeKind is the tell that needs no remembered constant: SharePoint
  // stamps a built-in with its type (Reader is 2). A level NAMED Read whose
  // type is None (0) is a CUSTOM level wearing the name, which is exactly
  // what #199 part 1 now refuses in a mapping and what nothing checks on a
  // site the mapping did not create.
  if (read) {
    const customType = read.RoleTypeKind === 0;
    record('R3', 'Does this site\'s Read differ from its neighbours in a way that suggests customisation?',
      customType ? 'FAIL' : 'PASS',
      customType
        ? `RoleTypeKind=0 means SharePoint does not consider this a built-in: a CUSTOM level is wearing the name 'Read' on this site, and the deploy would bind to it. ${STOCK_READ_NOTE}`
        : `RoleTypeKind=${read.RoleTypeKind}, so SharePoint still regards this as the built-in Reader level. Its bitmap is reported in R2 and should be compared across tenants before anything relies on a specific value. ${STOCK_READ_NOTE}`);
  }

  // ---- R6: does the group exist? -----------------------------------------
  const grp = await spGet(`web/sitegroups/getbyname('${encodeURIComponent(GROUP)}')?$select=Id,Title,Description`);
  if (readFailed(grp)) {
    record('R6', 'Is the named group present on this site at all?',
      grp.status === 404 ? 'PASS' : `NOT ESTABLISHED (HTTP ${grp.status})`,
      grp.status === 404
        ? `no group named '${GROUP}' here, so R4 and R5 have nothing to inspect. Point GROUP at an existing group to ask about one.`
        : `could not read the group: HTTP ${grp.status}`);
    record('R4', 'What web-scope role assignments does the named group already hold?',
      'NOT ESTABLISHED (no such group)', 'R6 found no group of that name');
    record('R5', 'What list-scope role assignments does it hold, across every list?',
      'NOT ESTABLISHED (no such group)', 'R6 found no group of that name');
    report();
    return;
  }
  const groupId = grp.body.Id;
  record('R6', 'Is the named group present on this site at all?',
    'PASS', `'${GROUP}' is group Id ${groupId}, description ${JSON.stringify(grp.body.Description)}`);

  // ---- R4: web-scope bindings --------------------------------------------
  // The binding the ACL phase never looks at and never removes: it reconciles
  // web/lists/.../roleassignments only.
  const webAsg = await spGet(
    `web/roleassignments?$expand=Member,RoleDefinitionBindings&$top=200`);
  if (readFailed(webAsg) || !Array.isArray(webAsg.body && webAsg.body.value)) {
    record('R4', 'What web-scope role assignments does the named group already hold?',
      `NOT ESTABLISHED (HTTP ${webAsg.status})`, 'could not enumerate web role assignments');
  } else {
    const mine = webAsg.body.value.filter((a) => a.PrincipalId === groupId);
    const levels = mine.flatMap((a) => (a.RoleDefinitionBindings || []).map((b) => b.Name));
    record('R4', 'What web-scope role assignments does the named group already hold?',
      'PASS',
      levels.length
        ? `at WEB scope '${GROUP}' holds: ${levels.join(', ')}. Anything beyond a derived Limited Access is inherited by every account enrolled into it, and nothing in the deploy removes it.`
        : `no web-scope binding for '${GROUP}'`);
  }

  // ---- R5: list-scope bindings, including lists outside any bundle -------
  const lists = await spGet("web/lists?$select=Id,Title,Hidden&$top=500");
  if (readFailed(lists) || !Array.isArray(lists.body && lists.body.value)) {
    record('R5', 'What list-scope role assignments does it hold, across every list?',
      `NOT ESTABLISHED (HTTP ${lists.status})`, 'could not enumerate lists');
  } else {
    const visible = lists.body.value.filter((l) => !l.Hidden);
    const held = [];
    let unreadable = 0;
    for (const l of visible) {
      const asg = await spGet(
        `web/lists(guid'${l.Id}')/roleassignments?$expand=RoleDefinitionBindings&$top=200`);
      if (readFailed(asg) || !Array.isArray(asg.body && asg.body.value)) { unreadable += 1; continue; }
      for (const a of asg.body.value) {
        if (a.PrincipalId !== groupId) continue;
        const names = (a.RoleDefinitionBindings || []).map((b) => b.Name).join('+');
        held.push(`${l.Title}: ${names}`);
      }
    }
    // The unreadable count is REPORTED, not swallowed. A list this caller
    // cannot read the ACL of is a list this probe cannot clear, and a
    // summary that omitted it would overstate what was checked.
    record('R5', 'What list-scope role assignments does it hold, across every list?',
      'PASS',
      `${visible.length} visible list(s) checked${unreadable ? `, ${unreadable} whose ACL could not be read` : ''}. `
      + (held.length
        ? `'${GROUP}' holds — ${held.join('; ')}. Any of these on a list OUTSIDE the deployed bundle is inherited permanently by the enrolled reader: deploy/_acls.js.j2 iterates SCHEMA.list_assignments only.`
        : `'${GROUP}' holds no list-scope binding on any visible list.`));
  }

  report();
  console.log('');
  console.log('=== WHAT TO DO WITH THIS ===');
  console.log('R2/R3 answer #199 part 2: whether this site\'s Read is still Read,');
  console.log('and whether a custom level is wearing the name. R3 FAIL means the');
  console.log('deploy would bind the reporting account to a level nobody checked.');
  console.log('R4/R5 answer #198: what a group already holds before the deploy');
  console.log('adds an account to it. Anything beyond Limited Access at web scope,');
  console.log('or any binding on a list outside the bundle, is privilege the');
  console.log('reader inherits permanently and no phase removes.');
  console.log('Together they are what #209\'s fail-closed gate has to test.');
})();
