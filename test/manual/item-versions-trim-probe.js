
/** ---- dbml-sharepoint PROBE: AN ITEM'S VERSIONS AFTER THE VERSION LIMIT TRIMS THEM ----
 *
 * REVISION: 1d4921ff
 *
 * QUESTION: once an item has been written more times than its list's
 * MajorVersionLimit, what does `items(id)/versions` return, straight away and
 * a minute later?
 *
 * WHY: a flow that records every change reads the versions since the last one
 * it recorded. When the limit trims versions between two runs, the flow must
 * know which versions remain and what the oldest retained one carries.
 * Learn documents version limits for document libraries and says nothing
 * about what the versions endpoint answers after a list trims.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   field.version.fixture-trim-list  a generic list with versioning on whose
 *       MajorVersionLimit, after asking for 2, reads back a whole number from 1 to 100
 *   field.version.fixture-trim-item  one item created and then written the list's
 *       limit plus three times, every write answered 2xx and the last Title read back
 *
 * OBSERVES (recorded verbatim, never compared with an expected value)
 *   field.version.trim-limit-taken          the MajorVersionLimit the list took, and
 *       what the settings MERGE answered
 *   field.version.trim-versions-at-once     the versions read straight after the last write
 *   field.version.trim-versions-after-wait  the same read after TRIM_WAIT_MS
 *
 * HOW TO READ IT: TRIMMED is as many versions answered as the limit reads
 * back, fewer than the writes that landed. FEWER THAN WRITTEN is a shortfall
 * of any other size, UNTRIMMED is as many as landed. Each carries the
 * VersionIds, labels and Titles, and the property names of the version with
 * the lowest VersionId answered. NOT COMPARABLE, left open, is an answer carrying
 * a continuation link, which the probe records and does not follow.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again
 * (CLEANUP = true recycles a list left by an earlier run first). The run
 * waits a minute before its second read. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing to delete. The probe recycles its list before it
 * reports.
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
  // ---- Raw requests (v1) ----------------------------------------------
  // The text is kept whole, since a refusal is often not JSON and its text is the finding.
  const sendRaw = async (path, options = {}) => {
    const method = options.method || 'GET';
    const accept = options.accept || 'application/json;odata=nometadata';
    let res;
    try {
      res = await fetch(`${WEB}/_api/${path}`, {
        method,
        headers: { Accept: accept, ...(options.headers || {}) },
        body: options.body === undefined ? undefined : JSON.stringify(options.body),
      });
    } catch (err) {
      // A request that never answered is a row with no status, so the table still prints.
      return { ok: false, status: null, parsed: null, date: null,
        text: `no response: ${err && err.message ? err.message : String(err)}` };
    }
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* not JSON; the text is kept */ }
    const date = res.headers && typeof res.headers.get === 'function' ? res.headers.get('date') : null;
    return { ok: res.ok, status: res.status, text, parsed, date };
  };

  // An error message can quote the request URL, and evidence must not name the tenant.
  const TENANT_ORIGIN = (() => {
    const scheme = WEB.indexOf('//');
    const slash = scheme === -1 ? -1 : WEB.indexOf('/', scheme + 2);
    return slash === -1 ? WEB : WEB.slice(0, slash);
  })();
  // A JSON body can escape the origin's slashes, and a host can appear with no scheme at all.
  const TENANT_PATTERN = (() => {
    const scheme = TENANT_ORIGIN.indexOf('//');
    const host = scheme === -1 ? '' : TENANT_ORIGIN.slice(scheme + 2);
    const needles = [TENANT_ORIGIN, TENANT_ORIGIN.replace(/\//g, '\\/'), host].filter((n) => n);
    const literal = (n) => n.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
    return needles.length ? new RegExp(needles.map(literal).join('|'), 'gi') : null;
  })();
  const redactTenant = (value) => {
    const text = String(value);
    return TENANT_PATTERN ? text.replace(TENANT_PATTERN, '[TENANT]') : text;
  };

  // The head a non-2xx or unanswered request earns, or null when its payload decides.
  const rawHead = (res) => {
    if (res.status === null) return { outcome: 'NOT ESTABLISHED', why: redactTenant(res.text) };
    if (res.ok) return null;
    const said = redactTenant(res.text).slice(0, 400);
    if (isRefusal(res.status)) return { outcome: 'REFUSED', why: `HTTP ${res.status}: ${said}` };
    const reason = unanswered({ ok: false, status: res.status, body: res.parsed });
    return { outcome: 'NOT ESTABLISHED', why: `the request ${reason}: ${said}` };
  };

  // contextinfo wraps its answer in d under odata=verbose and not under nometadata.
  const issueDigest = async () => {
    const res = await sendRaw('contextinfo', { method: 'POST', accept: 'application/json;odata=verbose' });
    const parsed = res.parsed && typeof res.parsed === 'object' ? res.parsed : null;
    const info = parsed && parsed.d ? parsed.d.GetContextWebInformation : parsed;
    const digest = res.ok && info && typeof info.FormDigestValue === 'string'
      ? info.FormDigestValue : null;
    return { res, digest };
  };
  // ---- Identity masking (v1) ------------------------------------------
  // Strings that name a person, masked wherever evidence quotes an answer.
  const IDENTITIES = [];
  // `whole` masks the value only where no letter, digit or underscore adjoins it, as a display name needs.
  const knowIdentity = (value, mask, whole = false) => {
    const text = value === null || value === undefined ? '' : String(value);
    if (text.length < 2) return;
    IDENTITIES.push({ text, mask, whole });
    IDENTITIES.sort((a, b) => b.text.length - a.text.length);
  };
  const literal = (text) => text.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
  const pattern = ({ text, whole }) => (whole
    ? new RegExp(`(?<![\\p{L}\\p{N}_])${literal(text)}(?![\\p{L}\\p{N}_])`, 'giu')
    : new RegExp(literal(text), 'gi'));
  // Logins and emails the probe never learned are masked too; a match stops at a backslash so JSON escapes survive.
  const scrub = (value) => {
    let out = redactTenant(value);
    for (const known of IDENTITIES) out = out.replace(pattern(known), known.mask);
    return out
      .replace(/(i:0[^|\s'"]*\|([^|\s'"]+\|)?)[^\s'"|\\]+/gi, '$1<account>')
      .replace(/[^\s'"|:<>\\]+@[^\s'"<>\\]+/gi, '<account>');
  };
  // ---- Scratch lists (v1) ---------------------------------------------
  // Lists this run created, by title and Id, so the recycle touches those and never a list it only found.
  const CREATED_LISTS = [];
  // A list Id as a bare lower-case GUID, or null when the value is not one.
  const guidOf = (value) => {
    const bare = value === null || value === undefined ? '' : String(value).replace(/[{}]/g, '').toLowerCase();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(bare) ? bare : null;
  };
  // __metadata is verbose OData, so every write carrying it declares the verbose content type.
  const VERBOSE_WRITE = { 'Content-Type': 'application/json;odata=verbose' };

  // Creates a list or library (generic unless `baseTemplate` says otherwise) owned by `description`, then reads it back.
  const claimScratchList = async ({ id, question, title, description, dependents,
    settings = null, declared = {}, baseTemplate = 100 }) => {
    const path = `web/lists/getbytitle('${title}')`;
    const pre = await spGet(`${path}?$select=Id,Description`);
    if (pre.ok) {
      if (!pre.body || pre.body.Description !== description) {
        record(id, question, 'FAIL',
          `a list named '${title}' exists without this probe's ownership description; refusing to modify it`);
        voidDependents(dependents, 'the scratch list is not one this probe created');
        return { held: false, merge: null, body: null };
      }
      if (!CLEANUP) {
        record(id, question, 'FAIL', `a list '${title}' from an earlier run is standing and CLEANUP is off`);
        voidDependents(dependents, 'a leftover list would answer this run\'s questions');
        return { held: false, merge: null, body: null };
      }
      // The recycle is pinned to the Id this read found, so a title rebound meanwhile cannot redirect it.
      const leftover = guidOf(pre.body.Id);
      if (leftover === null || !await resetList(title, leftover)) {
        record(id, question, 'FAIL', `the leftover list '${title}' `
          + `${leftover === null ? 'answered no list Id to recycle it by' : `(list ${leftover}) was not recycled`}`);
        voidDependents(dependents, 'a leftover list would answer this run\'s questions');
        return { held: false, merge: null, body: null };
      }
    } else if (pre.status !== 404) {
      // A by-title read answers an absent list 404 (the live finding rollback.js.j2 cites); anything else is unknown.
      const why = `the ownership read of '${title}' ${unanswered(pre)}`
        + `${pre.body ? `: ${scrub(JSON.stringify(pre.body)).slice(0, 200)}` : ''}`;
      record(id, question, 'NOT ESTABLISHED', `${why}; nothing was created, and a re-run can ask it`);
      for (const one of dependents) {
        const row = RESULTS.find((r) => r.id === one);
        // A row an earlier fixture voided keeps its reason.
        if (row && row.state === 'void') continue;
        record(one, row ? row.question : one, 'NOT ESTABLISHED', `not asked: ${why}; a re-run can ask it`);
      }
      return { held: false, merge: null, body: null };
    }
    const made = await spPost('web/lists',
      { Title: title, BaseTemplate: baseTemplate, Description: description }, await getDigest());
    if (!made.ok) {
      record(id, question, 'FAIL',
        `the list create answered HTTP ${made.status}: ${scrub(made.text).slice(0, 300)}`);
      voidDependents(dependents, 'the scratch list was not created');
      return { held: false, merge: null, body: null };
    }
    // What a list POST answers is not measured, so a missing Id is taken from the read-back below.
    const created = { title, id: guidOf(made.body && made.body.Id) };
    CREATED_LISTS.push(created);
    let merge = null;
    if (settings !== null) {
      merge = await spPost(path, { __metadata: { type: 'SP.List' }, ...settings }, await getDigest(),
        { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
      log('INFO', `list settings MERGE on '${title}': HTTP ${merge.status}`
        + `${merge.ok ? '' : ` ${scrub(merge.text).slice(0, 200)}`}`);
    }
    const select = [...new Set(['Id', 'BaseTemplate', 'Description', ...Object.keys(declared)])].join(',');
    // The MERGE's answer joins the read-back, so a refused setting shows its reason in RESULTS.
    const answered = merge === null ? {} : { Settings: `HTTP ${merge.status}`
      + `${merge.ok ? '' : `: ${scrub(merge.text).slice(0, 200)}`}` };
    // Recorded, never judged: what the MERGE answered is an observation, and the read-back decides.
    const settled = merge === null ? {} : { Settings: (v) => typeof v === 'string' };
    let read = null;
    const held = await establishFixture(id, async () => {
      read = await spGet(`${path}?$select=${select}`);
      const found = read.ok && read.body && typeof read.body === 'object' ? guidOf(read.body.Id) : null;
      if (created.id === null) created.id = found;
      return read.ok && read.body && typeof read.body === 'object'
        ? { ...read, body: { ...read.body, ...answered } } : read;
    }, { BaseTemplate: baseTemplate, Description: description, ...declared, ...settled,
      // The title must still name the list this run created, so every write after it reaches that list.
      Id: (v) => guidOf(v) !== null && guidOf(v) === created.id }, dependents);
    // The read-back is handed on, so a caller uses the values the fixture certified.
    return { held, merge, body: held ? read.body : null };
  };

  // Recycles every list this run created by its Id, newest first, and says which one to recycle by hand.
  const recycleScratchLists = async () => {
    for (const { title, id } of [...CREATED_LISTS].reverse()) {
      if (id === null) {
        log('FAIL', `'${title}' never answered a list Id, so it was not recycled; recycle it by hand.`);
        continue;
      }
      let gone;
      try {
        // The by-Id recycle is the one resetList sends, so a title rebound cannot redirect it.
        gone = await spPost(`web/lists(guid'${id}')/recycle`, {}, await getDigest());
      } catch (err) {
        gone = { ok: false, status: null, text: String((err && err.message) || err) };
      }
      // A request that threw has no status, so its message is what the operator is shown.
      const why = gone.status === null ? scrub(gone.text).slice(0, 240) : `HTTP ${gone.status}`;
      log(gone.ok ? 'OK' : 'FAIL', gone.ok
        ? `recycled '${title}' (list ${id}); it is restorable from the recycle bin.`
        : `could not recycle '${title}' (list ${id}, ${why}); recycle it by hand.`);
    }
  };
  // ---- Item versions (v1) ---------------------------------------------
  // A continuation link in any spelling the search-discovery probe reads, or null when there is none.
  const continuationOf = (parsed) => {
    if (!parsed || typeof parsed !== 'object') return null;
    const link = parsed['odata.nextLink'] || parsed['@odata.nextLink'] || parsed.__next
      || (parsed.d && typeof parsed.d === 'object' ? parsed.d.__next : undefined);
    return typeof link === 'string' && link ? link : null;
  };
  // One read of an item's versions; `rows` is the value array, or null when the answer carried none.
  const readVersions = async (listPath, itemId, query = '') => {
    const res = await sendRaw(`${listPath}/items(${itemId})/versions${query ? `?${query}` : ''}`);
    const head = rawHead(res);
    const rows = !head && res.parsed && Array.isArray(res.parsed.value) ? res.parsed.value : null;
    return { res, head, rows, next: head ? null : continuationOf(res.parsed) };
  };
  // Learn documents no paging for item versions, so a continuation link is reported and never followed.
  const pagedSaid = (versions) => (versions.next === null ? null
    : `the answer carried a continuation link (${scrub(versions.next).slice(0, 200)}), which this probe `
      + `does not follow, so its ${versions.rows ? versions.rows.length : 0} entries may not be every version`);

  // A version's VersionId as the answer spelled it, or null when the entry carried none.
  const versionIdOf = (row) => (row && typeof row === 'object' && row.VersionId !== undefined
    ? row.VersionId : null);

  // Names the order a run of VersionIds came back in; it describes and never judges.
  const orderOf = (ids) => {
    if (!ids.length) return 'NO VERSIONS';
    if (ids.length === 1) return 'ONE VERSION';
    if (ids.some((v) => typeof v !== 'number')) return 'NOT NUMBERS';
    const pairs = ids.slice(1).map((v, i) => v - ids[i]);
    if (pairs.every((d) => d > 0)) return 'ASCENDING';
    if (pairs.every((d) => d < 0)) return 'DESCENDING';
    return 'UNORDERED';
  };
  log('INFO', 'probe revision 1d4921ff. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe VersionsTrim';
  // Ownership is the Description, never the title: a same-title list this probe did not make is left alone.
  const OWNERSHIP = 'dbml-sharepoint versions-trim probe scratch list. Safe to delete.';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const ASKED_LIMIT = 2;
  // The most writes the run will send is this plus EXTRA_WRITES, so a list that keeps more is not measured.
  const MAX_LIMIT = 100;
  const EXTRA_WRITES = 3;
  const TRIM_WAIT_MS = 60000;

  const Q = {
    list: `a generic list with versioning on whose MajorVersionLimit, after asking for ${ASKED_LIMIT}, `
      + `reads back a whole number from 1 to ${MAX_LIMIT}`,
    limit: `the MajorVersionLimit the list took after asking for ${ASKED_LIMIT}`,
    item: 'one item created and written the limit plus three times, every write answered 2xx, '
      + 'whose last Title reads back',
    once: 'what items(id)/versions answers straight after the last write',
    wait: `what items(id)/versions answers ${TRIM_WAIT_MS / 1000} seconds later`,
  };
  expect('field.version.fixture-trim-list', Q.list);
  expect('field.version.trim-limit-taken', Q.limit);
  expect('field.version.fixture-trim-item', Q.item);
  expect('field.version.trim-versions-at-once', Q.once);
  expect('field.version.trim-versions-after-wait', Q.wait);

  const AFTER_ITEM = ['field.version.trim-versions-at-once', 'field.version.trim-versions-after-wait'];
  const AFTER_LIST = ['field.version.trim-limit-taken', 'field.version.fixture-trim-item', ...AFTER_ITEM];

  if (!CONFIRMED) {
    log('INFO', `Would create a list '${LIST}' on ${WEB} with versioning on, ask for a`);
    log('INFO', `MajorVersionLimit of ${ASKED_LIMIT}, create one item and write it the limit plus`);
    log('INFO', `${EXTRA_WRITES} times, then read its versions at once and ${TRIM_WAIT_MS / 1000} seconds later.`);
    log('INFO', 'The list is recycled on the way out.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  // Refusal text can name the tenant or an account, so it is scrubbed before it is shown.
  const said = (text) => scrub(text).slice(0, 300);
  const titleOf = (n) => `dbmlsp versions trim ${n}`;
  const describe = (got, written, limit) => {
    if (got.head) return [got.head.outcome, scrub(got.head.why)];
    if (got.rows === null) {
      return ['NOT ESTABLISHED', `HTTP ${got.res.status} carried no value array: ${said(got.res.text)}`];
    }
    const rows = got.rows;
    // TRIMMED needs the limit as its baseline: a shortfall of any other size is described, not explained.
    const head = got.next !== null ? 'NOT COMPARABLE' : rows.length === written ? 'UNTRIMMED'
      : rows.length > written ? 'MORE THAN WRITTEN' : rows.length === limit ? 'TRIMMED' : 'FEWER THAN WRITTEN';
    const listed = rows.map((row) => `${JSON.stringify(row.VersionLabel)}/${JSON.stringify(versionIdOf(row))}`
      + `/${JSON.stringify(row.Title)}`).join(', ');
    // A lowest VersionId is named only when every one answered is a number, since only then is it measured.
    const numeric = rows.length > 0 && rows.every((row) => typeof versionIdOf(row) === 'number');
    const lowest = numeric ? rows.reduce((low, row) => (versionIdOf(row) < versionIdOf(low) ? row : low)) : null;
    const carried = lowest ? `; the lowest VersionId answered carries ${Object.keys(lowest).sort().join(', ')}`
      : rows.length ? '; the VersionIds answered are not all numbers, so no lowest is named' : '';
    const paged = got.next === null ? '' : `${pagedSaid(got)}; `;
    return [head, `${paged}${rows.length} of ${written} version(s) answered, in order: ${listed}${carried}`,
      got.next === null ? undefined : 'open'];
  };

  try {
    const list = await claimScratchList({ id: 'field.version.fixture-trim-list', question: Q.list,
      title: LIST, description: OWNERSHIP, dependents: AFTER_LIST,
      settings: { EnableVersioning: true, MajorVersionLimit: ASKED_LIMIT },
      declared: { EnableVersioning: true,
        MajorVersionLimit: (v) => Number.isInteger(v) && v >= 1 && v <= MAX_LIMIT,
        ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 } });
    if (!list.held) return;
    const limit = list.body.MajorVersionLimit;
    // Recorded whatever the MERGE answered, since the read-back and not the MERGE says which limit holds.
    record('field.version.trim-limit-taken', Q.limit, limit === ASKED_LIMIT ? 'TAKEN AS ASKED' : 'OTHER LIMIT',
      `asked ${ASKED_LIMIT}; the settings MERGE answered HTTP ${list.merge.status}`
      + `${list.merge.ok ? '' : `: ${said(list.merge.text)}`}; MajorVersionLimit reads back ${limit}`);

    const itemType = list.body.ListItemEntityTypeFullName;
    const writes = limit + EXTRA_WRITES;
    // One digest for the run of writes, since a fresh one per write doubles the requests.
    const digest = await getDigest();
    let itemId = null;
    let written = 0;
    const refused = [];
    const made = await spPost(`${listPath}/items`, { __metadata: { type: itemType }, Title: titleOf(1) },
      digest, VERBOSE_WRITE);
    if (made.ok) written += 1;
    else refused.push(`the create: HTTP ${made.status}: ${said(made.text)}`);
    if (made.ok && made.body && Number.isInteger(made.body.Id)) itemId = made.body.Id;
    else if (made.ok) refused.push(`the create: HTTP ${made.status} carried no numeric Id`);
    for (let n = 2; itemId !== null && n <= writes + 1; n += 1) {
      const sent = await spPost(`${listPath}/items(${itemId})`, { __metadata: { type: itemType },
        Title: titleOf(n) }, digest, { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
      if (sent.ok) written += 1;
      else refused.push(`write ${n}: HTTP ${sent.status}: ${said(sent.text)}`);
    }
    if (!await establishFixture('field.version.fixture-trim-item', async () => {
      // The refused writes join the read-back, so a write that did not land shows its reason in RESULTS.
      const shown = refused.slice(0, 3).map((line) => line.slice(0, 160)).join('; ')
        + (refused.length > 3 ? `; and ${refused.length - 3} more` : '');
      const body = { Written: written, Refused: shown || 'none' };
      if (itemId === null) return { ok: true, status: 200, body };
      const read = await sendRaw(`${listPath}/items(${itemId})?$select=Id,Title`);
      const head = rawHead(read);
      body.Title = head ? scrub(head.why) : read.parsed && typeof read.parsed === 'object' ? read.parsed.Title
        : `no JSON: ${said(read.text)}`;
      return { ok: true, status: 200, body };
    }, { Written: writes + 1, Refused: (v) => typeof v === 'string', Title: titleOf(writes + 1) },
    AFTER_ITEM)) {
      return;
    }

    const [onceHead, onceSaid, onceState] = describe(await readVersions(listPath, itemId), written, limit);
    record('field.version.trim-versions-at-once', Q.once, onceHead, `limit ${limit}; ${onceSaid}`, onceState);
    log('INFO', `waiting ${TRIM_WAIT_MS / 1000} seconds before the second read.`);
    const firstRead = Date.now();
    await new Promise((resolve) => { setTimeout(resolve, TRIM_WAIT_MS); });
    const [waitHead, waitSaid, waitState] = describe(await readVersions(listPath, itemId), written, limit);
    // The wait is measured rather than assumed, so the row says how long it actually was.
    const waited = Math.round((Date.now() - firstRead) / 1000);
    record('field.version.trim-versions-after-wait', Q.wait, waitHead,
      `limit ${limit}; ${waitSaid}; read ${waited} second(s) after the first read`, waitState);
  } catch (err) {
    log('FAIL', `probe aborted: ${scrub(String((err && err.message) || err)).slice(0, 240)}. `
      + 'The unasked rows stay open.');
  } finally {
    await recycleScratchLists();
    // Reported here, after the recycle, so every path prints the recycle line above the table.
    report();
  }
})();
