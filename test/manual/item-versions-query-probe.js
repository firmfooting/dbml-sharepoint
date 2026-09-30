
/** ---- dbml-sharepoint PROBE: WHICH ODATA OPTIONS AN ITEM'S VERSIONS HONOUR ----
 *
 * REVISION: 68a948f0
 *
 * QUESTION: does `items(id)/versions` honour `$select`, `$filter`, `$top` and
 * `$orderby`, and in what order does it return versions when asked for none?
 *
 * WHY: a flow that reads an item's versions once per run would narrow the
 * read on the server if it could, and pairs consecutive versions by order.
 * "Use OData query operations in SharePoint REST requests" documents these
 * options for list items and says nothing about item versions.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   query.odata.fixture-versions-query-list   a generic list with versioning on
 *   query.odata.fixture-versions-query-items  item A created and written twice, item B
 *       created once, each write read back before the next is sent
 *   query.odata.control-versions-read        A's versions read with no options answers
 *       at least two entries, each carrying a numeric VersionId, none repeated
 *   query.odata.control-versions-items-filter      $filter=Id eq A serves A alone
 *   query.odata.control-versions-items-top-orderby $orderby=Id desc&$top=1 serves whichever
 *       of A and B read back with the greater Id, alone
 *   The filter control gates the filter row, the top-and-orderby control gates the
 *   top and orderby rows. A control that FAILs voids them; one NOT ESTABLISHED leaves
 *   them open and unasked.
 *
 * OBSERVES (named from what came back, never compared with an expected value)
 *   query.odata.versions-default-order  the VersionIds in the order the plain read answered
 *   query.odata.versions-select         $select=VersionId,VersionLabel,ProbeChoice: the
 *       property names each entry carried, beside those the plain read carried beyond them
 *   query.odata.versions-filter         $filter=VersionId gt <the lowest>: the VersionIds served
 *   query.odata.versions-top            $top=1: how many entries were served
 *   query.odata.versions-orderby        $orderby=VersionId in the direction opposite to the
 *       plain read's, or ascending when the plain read has no order: the VersionIds in the
 *       order served
 *
 * HOW TO READ IT: each observed row is headed by what the answer looked like
 * (NARROWED, FILTERED, TOPPED and so on) beside the plain read's answer, and
 * REFUSED is a refusal whose text says why. NARROWED needs every entry to carry
 * nothing beyond the selected names and every selected name the plain read
 * carried on all its entries; SELECTED MISSING is an answer lacking one.
 * OTHER ROWS on the select, top and orderby rows is an answer serving
 * versions the plain read did not, or not serving all of those it did.
 * NOT COMPARABLE, left open, is an answer carrying a continuation link, which
 * the probe records and does not follow; on the plain read it holds every
 * option row.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again.
 * Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing to delete. The probe recycles its list before it
 * reports. Each title ends in a token unique to the run, so no run finds,
 * reuses or recycles another run's list; one a run could not recycle is
 * named on the console, with its Id, to recycle by hand.
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
  // Logins and emails go first, even ones never learned, so a display name inside one cannot break it up.
  // A match stops at a backslash so JSON escapes survive.
  const scrub = (value) => {
    let out = redactTenant(value)
      .replace(/(i:0[^|\s'"]*\|([^|\s'"]+\|)?)[^\s'"|\\]+/gi, '$1<account>')
      .replace(/[^\s'"|:<>\\]+@[^\s'"<>\\]+/gi, '<account>');
    for (const known of IDENTITIES) out = out.replace(pattern(known), known.mask);
    return out;
  };
  // rawHead cuts a response's text short, so the text is masked first and a cut never splits a name unmasked.
  const maskedHead = (res) => rawHead({ ...res, text: scrub(res.text) });
  // For a probe with no current-user fixture: learns this account so its display name is masked too.
  const learnIdentity = async () => {
    const read = await sendRaw('web/currentuser?$select=Email,LoginName,Title');
    if (read.ok && read.parsed && typeof read.parsed === 'object') {
      knowIdentity(read.parsed.Email, '<account>');
      knowIdentity(read.parsed.LoginName, '<account>');
      knowIdentity(read.parsed.Title, '<name>', true);
      return;
    }
    const head = maskedHead(read);
    log('INFO', `this account did not read back (${head ? head.why : `HTTP ${read.status} carried no JSON`}), `
      + 'so a display name in an answer is not masked; logins and emails still are.');
  };
  // ---- Scratch lists (v1) ---------------------------------------------
  // Lists this run created, by title and Id, so the recycle touches those and never a list it only found.
  const CREATED_LISTS = [];
  // A token drawn once per run and ending every scratch title, so no run finds, reuses or recycles another's list.
  const RUN = Math.random().toString(36).slice(2, 10);
  const runTitle = (base) => `${base} ${RUN}`;
  // A list Id as a bare lower-case GUID, or null when the value is not one.
  const guidOf = (value) => {
    const bare = value === null || value === undefined ? '' : String(value).replace(/[{}]/g, '').toLowerCase();
    return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(bare) ? bare : null;
  };
  // A title or server-relative path inside an OData string literal, its apostrophes doubled as deploy/_folders does.
  const pathLiteral = (path) => String(path).replace(/'/g, "''");
  // __metadata is verbose OData, so every write carrying it declares the verbose content type.
  const VERBOSE_WRITE = { 'Content-Type': 'application/json;odata=verbose' };
  // A list read by its Id after a recycle: gone true, false, or null with the reason it cannot say.
  const listGone = async (listId) => {
    let res;
    try {
      res = await spGet(`web/lists(guid'${listId}')?$select=Id`);
    } catch (err) {
      return { gone: null, why: `the read-back never answered (${scrub(String((err && err.message) || err))})` };
    }
    if (res.ok) return { gone: false, why: `it still reads back by its Id (HTTP ${res.status})` };
    const error = res.body && typeof res.body === 'object' ? res.body['odata.error'] || res.body.error : null;
    const code = String((error && error.code) || '');
    // Absent is what rollback.js.j2 accepts for a by-Id list read: a 404, or this one ArgumentException 400.
    if (res.status === 404 || (res.status === 400 && code.includes('-2147024809')
      && code.includes('System.ArgumentException'))) return { gone: true, why: null };
    return { gone: null, why: `the read-back that would confirm it ${unanswered(res)}` };
  };
  // Recycles one list by its Id and logs OK only once a by-Id read shows it gone; gone is as listGone's.
  const recycleList = async (title, listId) => {
    let sent;
    try {
      sent = await spPost(`web/lists(guid'${listId}')/recycle`, {}, await getDigest());
    } catch (err) {
      sent = { ok: false, status: null, text: String((err && err.message) || err) };
    }
    // A request that threw has no status, so its message is what the operator is shown.
    const why = sent.status === null ? scrub(sent.text).slice(0, 240) : `HTTP ${sent.status}`;
    if (!sent.ok) {
      log('FAIL', `could not recycle '${title}' (list ${listId}, ${why}); recycle it by hand.`);
      return { gone: false, why: `its recycle was not answered 2xx (${why})` };
    }
    const after = await listGone(listId);
    log(after.gone ? 'OK' : 'FAIL', after.gone
      ? `recycled '${title}' (list ${listId}); it is restorable from the recycle bin.`
      : `the recycle of '${title}' (list ${listId}) answered ${why}, but ${after.why}; `
        + 'check it and recycle it by hand.');
    return { gone: after.gone, why: after.gone ? null : `its recycle answered ${why}, but ${after.why}` };
  };

  // Creates a list or library (generic unless `baseTemplate` says otherwise) owned by `description`, then reads it back.
  const claimScratchList = async ({ id, question, title, description, dependents,
    settings = null, declared = {}, baseTemplate = 100 }) => {
    const path = `web/lists/getbytitle('${pathLiteral(title)}')`;
    // An answer that settles nothing leaves the fixture and its dependents open for a re-run.
    const leaveOpen = (why) => {
      record(id, question, 'NOT ESTABLISHED', `${why}; a re-run can ask it`);
      for (const one of dependents) {
        const row = RESULTS.find((r) => r.id === one);
        // A row an earlier fixture voided keeps its reason.
        if (row && row.state === 'void') continue;
        record(one, row ? row.question : one, 'NOT ESTABLISHED', `not asked: ${why}; a re-run can ask it`);
      }
      return { held: false, merge: null, body: null };
    };
    const pre = await spGet(`${path}?$select=Id,Description`);
    // A 2xx with no JSON says nothing about whose list it is, so it is neither refused nor built over.
    if (pre.ok && (pre.body === null || typeof pre.body !== 'object')) {
      return leaveOpen(`the ownership read of '${title}' answered HTTP ${pre.status} with no JSON; `
        + 'nothing was created');
    }
    if (pre.ok) {
      // A title ending in this run's token names no list before this run makes one, so a list found here is
      // not this run's, whatever its description, and is never recycled or built over.
      record(id, question, 'FAIL', `a list named '${title}' already exists`
        + `${pre.body.Description === description ? ' with this probe\'s description' : ''}; refusing to modify it`);
      voidDependents(dependents, 'the scratch list is not one this run created');
      return { held: false, merge: null, body: null };
    } else if (pre.status !== 404) {
      // A by-title read answers an absent list 404 (the live finding rollback.js.j2 cites); anything else is unknown.
      return leaveOpen(`the ownership read of '${title}' ${unanswered(pre)}`
        + `${pre.body ? `: ${scrub(JSON.stringify(pre.body)).slice(0, 200)}` : ''}; nothing was created`);
    }
    const digest = await getDigest();
    let made;
    try {
      made = await spPost('web/lists', { Title: title, BaseTemplate: baseTemplate, Description: description },
        digest);
    } catch (err) {
      // The create may have reached the server, so the title is kept for the recycle line to name.
      CREATED_LISTS.push({ title, id: null });
      return leaveOpen(`the list create never answered (${scrub(String((err && err.message) || err))}), so a `
        + `list '${title}' may now exist`);
    }
    if (!made.ok) {
      record(id, question, 'FAIL',
        `the list create answered HTTP ${made.status}: ${scrub(made.text).slice(0, 300)}`);
      voidDependents(dependents, 'the scratch list was not created');
      return { held: false, merge: null, body: null };
    }
    const created = { title, id: guidOf(made.body && made.body.Id) };
    CREATED_LISTS.push(created);
    // Without the create's own Id a title read could name a rebound list, so nothing more is written.
    if (created.id === null) {
      record(id, question, 'FAIL', `the list create answered HTTP ${made.status} with no list Id, so nothing `
        + `ties '${title}' to the list it made; nothing was written to it`);
      voidDependents(dependents, 'the scratch list answered no Id to address it by');
      return { held: false, merge: null, body: null };
    }
    let merge = null;
    if (settings !== null) {
      // Sent by Id, so a title rebound cannot take this list's settings.
      merge = await spPost(`web/lists(guid'${created.id}')`, { __metadata: { type: 'SP.List' }, ...settings },
        await getDigest(), { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
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
      return read.ok && read.body && typeof read.body === 'object'
        ? { ...read, body: { ...read.body, ...answered } } : read;
    }, { BaseTemplate: baseTemplate, Description: description, ...declared, ...settled,
      // The title must still name the list this run created, so every write after it reaches that list.
      Id: (v) => guidOf(v) !== null && guidOf(v) === created.id }, dependents);
    // The read-back is handed on, so a caller uses the values the fixture certified, and writes by its Id.
    return { held, merge, body: held ? read.body : null, path: held ? `web/lists(guid'${created.id}')` : null };
  };

  // Recycles every list this run created by its Id, newest first, and says which one to recycle by hand.
  const recycleScratchLists = async () => {
    for (const { title, id } of [...CREATED_LISTS].reverse()) {
      if (id === null) {
        log('FAIL', `'${title}' never answered a list Id, so it was not recycled; if it stands, recycle it by hand.`);
        continue;
      }
      // By Id, so a title rebound cannot redirect it.
      await recycleList(title, id);
    }
  };
  // ---- Item versions (v1) ---------------------------------------------
  // A continuation link in the three spellings the search-discovery probe reads plus a bare __next, or null.
  const continuationOf = (parsed) => {
    if (!parsed || typeof parsed !== 'object') return null;
    const link = parsed['odata.nextLink'] || parsed['@odata.nextLink'] || parsed.__next
      || (parsed.d && typeof parsed.d === 'object' ? parsed.d.__next : undefined);
    return typeof link === 'string' && link ? link : null;
  };
  // One read of an item's versions; `rows` is the value array, or null when the answer carried none.
  const readVersions = async (listPath, itemId, query = '') => {
    const res = await sendRaw(`${listPath}/items(${itemId})/versions${query ? `?${query}` : ''}`);
    const head = maskedHead(res);
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
  // The VersionIds an answer lists more than once, since a count or a set over them would take a repeat for one.
  const repeatedIds = (rows) => {
    const seen = new Set();
    const again = new Set();
    for (const row of rows) {
      const key = JSON.stringify(versionIdOf(row));
      if (seen.has(key)) again.add(key);
      seen.add(key);
    }
    return [...again];
  };

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
  log('INFO', 'probe revision 68a948f0. Quote this when reporting results.');

  const LIST = runTitle('dbmlsp Probe VersionsQuery');
  // The Description marks the list as this probe's for anyone recycling it by hand, and the read-back checks it.
  const OWNERSHIP = 'dbml-sharepoint versions-query probe scratch list. Safe to delete.';
  const CHOICE = 'ProbeChoice';

  const Q = {
    list: 'a generic list this probe created, with versioning on',
    items: 'item A created and written twice, item B created once, each write read back before the next',
    read: 'CONTROL: A\'s versions read with no options answers at least two entries, '
      + 'each carrying a numeric VersionId, none repeated',
    filterControl: 'CONTROL: $filter=Id eq A on the list\'s items serves A alone',
    topControl: 'CONTROL: $orderby=Id desc&$top=1 on the list\'s items serves the item with the greater Id alone',
    order: 'the order the versions read answers when asked for none',
    select: `what $select=VersionId,VersionLabel,${CHOICE} on the versions read answers`,
    filter: 'what $filter=VersionId gt the lowest VersionId on the versions read answers',
    top: 'what $top=1 on the versions read answers',
    orderby: 'what $orderby=VersionId on the versions read answers, asked opposite to the plain read\'s order, '
      + 'or ascending when that read has none',
  };
  expect('query.odata.fixture-versions-query-list', Q.list);
  expect('query.odata.fixture-versions-query-items', Q.items);
  expect('query.odata.control-versions-read', Q.read);
  expect('query.odata.control-versions-items-filter', Q.filterControl);
  expect('query.odata.control-versions-items-top-orderby', Q.topControl);
  expect('query.odata.versions-default-order', Q.order);
  expect('query.odata.versions-select', Q.select);
  expect('query.odata.versions-filter', Q.filter);
  expect('query.odata.versions-top', Q.top);
  expect('query.odata.versions-orderby', Q.orderby);

  const FILTER_CONTROL = 'query.odata.control-versions-items-filter';
  const TOP_CONTROL = 'query.odata.control-versions-items-top-orderby';
  const SUBJECTS = ['query.odata.versions-default-order', 'query.odata.versions-select',
    'query.odata.versions-filter', 'query.odata.versions-top', 'query.odata.versions-orderby'];
  const AFTER_READ = [FILTER_CONTROL, TOP_CONTROL, ...SUBJECTS];
  const AFTER_ITEMS = ['query.odata.control-versions-read', ...AFTER_READ];
  const AFTER_LIST = ['query.odata.fixture-versions-query-items', ...AFTER_ITEMS];

  if (!CONFIRMED) {
    log('INFO', `Would create a list '${LIST}' on ${WEB} with versioning on and one Choice column,`);
    log('INFO', 'create item A and write it twice, create item B, then read A\'s versions with no');
    log('INFO', 'options and with each of $select, $filter, $top and $orderby. The list is recycled');
    log('INFO', 'on the way out. Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  // Refusal text can name the tenant or an account, so it is scrubbed before it is shown.
  const said = (res) => scrub(res.text).slice(0, 400);

  try {
    await learnIdentity();
    const list = await claimScratchList({ id: 'query.odata.fixture-versions-query-list', question: Q.list,
      title: LIST, description: OWNERSHIP, dependents: AFTER_LIST, settings: { EnableVersioning: true },
      declared: { EnableVersioning: true,
        ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 } });
    if (!list.held) return;
    const listPath = list.path;
    const itemType = list.body.ListItemEntityTypeFullName;

    // The deploy's Choice create body (generators/jsgen.py).
    const column = await spPost(`${listPath}/fields`, { __metadata: { type: 'SP.FieldChoice' },
      Title: CHOICE, FieldTypeKind: 6, Required: false, Choices: { results: ['Q1', 'Q2', 'Q3'] },
      FillInChoice: false }, await getDigest(), VERBOSE_WRITE);
    log('INFO', `create ${CHOICE}: HTTP ${column.status}${column.ok ? '' : ` ${said(column)}`}`);

    const ids = {};
    let written = 0;
    const missed = [];
    // A write counts once the item reads back what it set, since the option rows rest on A's three versions.
    const landed = async (what, sent, itemId, want) => {
      if (!sent.ok || itemId === undefined) {
        missed.push(`${what}: HTTP ${sent.status}`
          + `${sent.ok ? ' carried no numeric Id' : `: ${said(sent).slice(0, 160)}`}`);
        return false;
      }
      const read = await sendRaw(`${listPath}/items(${itemId})?$select=Id,Title,${CHOICE}`);
      const head = maskedHead(read);
      const got = !head && read.parsed && typeof read.parsed === 'object' ? read.parsed : null;
      const off = got === null ? null : Object.keys(want).filter((key) => got[key] !== want[key]);
      if (got !== null && off.length === 0) {
        written += 1;
        return true;
      }
      missed.push(`${what}: HTTP ${sent.status}, but ${got === null ? `the read-back ${head ? scrub(head.why)
        : `answered HTTP ${read.status} with no JSON`}` : off.map((key) => `${key} reads back `
        + `${JSON.stringify(got[key])}`).join(', ')}`.slice(0, 240));
      return false;
    };
    for (const [key, title] of [['A', 'dbmlsp versions query A'], ['B', 'dbmlsp versions query B']]) {
      const made = await spPost(`${listPath}/items`, { __metadata: { type: itemType }, Title: title,
        [CHOICE]: 'Q1' }, await getDigest(), VERBOSE_WRITE);
      if (made.ok && made.body && Number.isInteger(made.body.Id)) ids[key] = made.body.Id;
      await landed(`the create of ${key}`, made, ids[key], { Title: title, [CHOICE]: 'Q1' });
    }
    if (ids.A !== undefined) {
      for (const value of ['Q2', 'Q3']) {
        const sent = await spPost(`${listPath}/items(${ids.A})`, { __metadata: { type: itemType },
          [CHOICE]: value }, await getDigest(), { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
        if (!await landed(`A's write of ${value}`, sent, ids.A, { [CHOICE]: value })) break;
      }
    }
    if (!await establishFixture('query.odata.fixture-versions-query-items', async () => {
      // The column create's answer joins the read-back, so a refused create shows its reason in RESULTS.
      const body = { Column: `HTTP ${column.status}${column.ok ? '' : `: ${said(column).slice(0, 200)}`}`,
        Written: written, Missed: missed.join('; ') || 'none' };
      for (const key of ['A', 'B']) {
        if (ids[key] === undefined) continue;
        const read = await sendRaw(`${listPath}/items(${ids[key]})?$select=Id,${CHOICE}`);
        const head = maskedHead(read);
        body[`${key}.${CHOICE}`] = head ? scrub(head.why)
          : read.parsed && typeof read.parsed === 'object' ? read.parsed[CHOICE] : `no JSON: ${said(read)}`;
      }
      return { ok: true, status: 200, body };
    }, { Column: (v) => typeof v === 'string', Written: 4, Missed: (v) => typeof v === 'string',
      [`A.${CHOICE}`]: 'Q3', [`B.${CHOICE}`]: 'Q1' },
    AFTER_ITEMS)) {
      return;
    }

    const plain = await readVersions(listPath, ids.A);
    const plainIds = plain.rows === null ? [] : plain.rows.map(versionIdOf);
    // The option rows need two numeric VersionIds; how many an item answers is the payload probe's question.
    // Each version must be listed once, since every option row compares against these VersionIds as a set.
    const readHeld = plain.rows !== null && plain.rows.length >= 2
      && plainIds.every((v) => typeof v === 'number') && repeatedIds(plain.rows).length === 0;
    // A 2xx with no value array is not an answer about the versions, so it is left open like a throttle.
    const plainUnread = plain.head ? plain.head.outcome === 'NOT ESTABLISHED' : plain.rows === null;
    const readOutcome = readHeld ? 'PASS' : plainUnread ? 'NOT ESTABLISHED' : 'FAIL';
    const entries = (n) => `${n} ${n === 1 ? 'entry' : 'entries'}`;
    record('query.odata.control-versions-read', Q.read, readOutcome, plain.head ? scrub(plain.head.why)
      : `HTTP ${plain.res.status}, ${plain.rows === null ? `no value array: ${said(plain.res)}`
        : `${entries(plain.rows.length)}, VersionIds ${JSON.stringify(plainIds)}`}`);
    if (readOutcome === 'FAIL') {
      voidDependents(AFTER_READ,
        'the plain versions read did not answer at least two entries each carrying a numeric VersionId, '
          + 'none repeated');
      return;
    }
    if (readOutcome === 'NOT ESTABLISHED') {
      for (const id of AFTER_READ) {
        const row = RESULTS.find((r) => r.id === id);
        record(id, row.question, 'NOT ESTABLISHED', 'not asked: the plain versions read was not established '
          + `(${plain.head ? scrub(plain.head.why) : `HTTP ${plain.res.status} carried no value array`}); `
          + 'a re-run can ask it');
      }
      return;
    }

    if (plain.next !== null) {
      // Every option row compares against the plain read, which a continuation link leaves incomplete.
      const why = `the plain versions read is not known to be complete: ${pagedSaid(plain)}`;
      for (const id of AFTER_READ) {
        const row = RESULTS.find((r) => r.id === id);
        if (SUBJECTS.includes(id)) record(id, row.question, 'NOT COMPARABLE', why, 'open');
        else record(id, row.question, 'NOT ESTABLISHED', `not asked: ${why}`);
      }
      return;
    }
    const defaultOrder = orderOf(plainIds);
    record('query.odata.versions-default-order', Q.order, defaultOrder,
      `VersionIds in the order answered: ${JSON.stringify(plainIds)}; labels `
      + `${JSON.stringify(plain.rows.map((row) => row.VersionLabel))}`);

    // What the item-list controls serve decides which option rows are asked at all.
    const controlOf = async (id, question, query, want) => {
      const res = await sendRaw(`${listPath}/items?$select=Id&${query}`);
      const head = maskedHead(res);
      const rows = !head && res.parsed && Array.isArray(res.parsed.value) ? res.parsed.value : null;
      const served = rows === null ? null : rows.map((row) => row.Id);
      // A 2xx with no rows is not an answer about the option, so it is left open like a throttle.
      const outcome = served !== null && served.join(',') === String(want) ? 'PASS'
        : (head ? head.outcome === 'NOT ESTABLISHED' : served === null) ? 'NOT ESTABLISHED' : 'FAIL';
      const why = head ? scrub(head.why) : served === null ? `HTTP ${res.status} carried no rows: ${said(res)}` : '';
      record(id, question, outcome, `${query}: ${why || `served ${JSON.stringify(served)}, want [${want}]`}`);
      return { outcome, why };
    };
    const filterControl = await controlOf(FILTER_CONTROL, Q.filterControl, `$filter=Id eq ${ids.A}`, ids.A);
    // The greater of the two Ids read back, since nothing certifies that B was given the greater one.
    const topControl = await controlOf(TOP_CONTROL, Q.topControl, '$orderby=Id desc&$top=1', Math.max(ids.A, ids.B));

    // `control` is null for an option no item-list control asks first.
    const ask = async (id, question, control, query, describe) => {
      if (control !== null && control.outcome === 'FAIL') {
        voidDependents([id], 'the item-list control asking the same option did not serve the rows written');
        return;
      }
      if (control !== null && control.outcome === 'NOT ESTABLISHED') {
        record(id, question, 'NOT ESTABLISHED',
          `not asked: its item-list control was not established (${control.why}); a re-run can ask it`);
        return;
      }
      const got = await readVersions(listPath, ids.A, query);
      if (got.head) {
        record(id, question, got.head.outcome, `${query}: ${scrub(got.head.why)}`);
        return;
      }
      if (got.rows === null) {
        record(id, question, 'NOT ESTABLISHED', `${query}: HTTP ${got.res.status} carried no value array: `
          + `${said(got.res)}`);
        return;
      }
      if (got.next !== null) {
        record(id, question, 'NOT COMPARABLE', `${query}: ${pagedSaid(got)}; served VersionIds `
          + `${JSON.stringify(got.rows.map(versionIdOf))}`, 'open');
        return;
      }
      const [head, evidence] = describe(got.rows);
      record(id, question, head, `${query}: ${evidence}; the plain read answered VersionIds `
        + `${JSON.stringify(plainIds)}`);
    };

    const SELECTED = ['VersionId', 'VersionLabel', CHOICE];
    const keysOf = (rows) => [...new Set(rows.flatMap((row) => Object.keys(row)))].sort();
    const beyondSelected = (keys) => keys.filter((key) => !SELECTED.includes(key) && !key.startsWith('odata.')
      && !key.startsWith('@odata.') && key !== '__metadata');
    // Narrowing is judged against what the plain read carried beyond the selected names.
    const baseline = beyondSelected(keysOf(plain.rows));
    const carries = (row, key) => Object.prototype.hasOwnProperty.call(row, key);
    // Whether an answer served exactly the versions the plain read did, by VersionId.
    const sameVersions = (rows) => JSON.stringify(rows.map(versionIdOf).map(String).sort())
      === JSON.stringify(plainIds.map(String).sort());
    // A selected name the plain read carried on every entry must come back on every entry.
    const owed = SELECTED.filter((key) => plain.rows.every((row) => carries(row, key)));
    await ask('query.odata.versions-select', Q.select, null, `$select=${SELECTED.join(',')}`,
      (rows) => {
        const keys = keysOf(rows);
        const extra = beyondSelected(keys);
        const missing = owed.filter((key) => !rows.every((row) => carries(row, key)));
        // VersionId is selected, so an answer lacking it heads SELECTED MISSING before its versions are compared.
        const head = !baseline.length ? 'NOT COMPARABLE' : !rows.length ? 'NO VERSIONS'
          : extra.length ? 'NOT NARROWED' : missing.length ? 'SELECTED MISSING'
            : !sameVersions(rows) ? 'OTHER ROWS' : 'NARROWED';
        const why = !baseline.length ? 'the plain read carried nothing beyond the selected names, '
          + 'so an ignored $select would look the same' : `the plain read also carried ${baseline.join(', ')}`;
        const lacking = missing.length ? `; not every entry carries ${missing.join(', ')}, which every entry of `
          + 'the plain read carried' : '';
        return [head, `${entries(rows.length)} carrying ${keys.length ? keys.join(', ') : 'nothing'}; ${why}`
          + `${lacking}; served VersionIds ${JSON.stringify(rows.map(versionIdOf))}`];
      });
    const lowest = Math.min(...plainIds);
    await ask('query.odata.versions-filter', Q.filter, filterControl, `$filter=VersionId gt ${lowest}`,
      (rows) => {
        const served = rows.map(versionIdOf);
        const rest = plainIds.filter((v) => v > lowest);
        const same = (a, b) => [...a].sort().join(',') === [...b].sort().join(',');
        const head = same(served, rest) ? 'FILTERED' : same(served, plainIds) ? 'UNFILTERED' : 'OTHER ROWS';
        return [head, `served VersionIds ${JSON.stringify(served)}`];
      });
    // A served version the plain read did not answer is not one of this item's versions topped.
    const known = (rows) => rows.every((row) => plainIds.some((v) => String(v) === String(versionIdOf(row))));
    await ask('query.odata.versions-top', Q.top, topControl, '$top=1',
      (rows) => [!known(rows) ? 'OTHER ROWS' : rows.length === 1 ? 'TOPPED' : 'NOT TOPPED',
        `served ${entries(rows.length)}, VersionIds ${JSON.stringify(rows.map(versionIdOf))}`]);
    // Only an ordered plain read has an opposite, so an unordered one is asked ascending and said so.
    const opposite = defaultOrder === 'ASCENDING' ? 'desc' : defaultOrder === 'DESCENDING' ? 'asc' : null;
    const direction = opposite || 'asc';
    const askedSaid = opposite ? `asked ${direction}, opposite to the plain read's ${defaultOrder}`
      : `asked asc, since the plain read was ${defaultOrder} and has no opposite`;
    await ask('query.odata.versions-orderby', Q.orderby, topControl, `$orderby=VersionId ${direction}`,
      (rows) => {
        const served = rows.map(versionIdOf);
        // An order is named only over the same versions the plain read answered.
        return [sameVersions(rows) ? orderOf(served) : 'OTHER ROWS',
          `${askedSaid}; served VersionIds ${JSON.stringify(served)}`];
      });
  } catch (err) {
    log('FAIL', `probe aborted: ${scrub(String((err && err.message) || err)).slice(0, 240)}. `
      + 'The unasked rows stay open.');
  } finally {
    await recycleScratchLists();
    // Reported here, after the recycle, so every path prints the recycle line above the table.
    report();
  }
})();
