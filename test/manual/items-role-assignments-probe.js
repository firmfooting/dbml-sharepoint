
/** ---- dbml-sharepoint PROBE: A PAGE OF LIBRARY ITEMS WITH EACH ITEM'S ROLE ASSIGNMENTS EXPANDED ----
 *
 * REVISION: beb0f399
 *
 * WHY: a flow that reads a whole library through Send an HTTP request to
 * SharePoint, 100 items to a page, wants each item's role assignments in the
 * same read so it sends one request per page rather than one per item. Learn
 * ("Use OData query operations in SharePoint REST requests") says bulk
 * expansion of related items is not supported and documents $top and
 * $skiptoken paging; it says nothing about expanding RoleAssignments on an
 * items collection. These rows ask.
 *
 * QUESTIONS (OBSERVES, recorded verbatim, never compared with an expected value)
 *   access.item-acl.items-expand-role-assignments  C7, shape A: the flow's read
 *       with ProbeOwnerId selected, every page to the end: each page's status,
 *       Retry-After, item count, nextLink, how many items carry RoleAssignments,
 *       and six sampled items' bindings beside the per-item read
 *   access.item-acl.items-expand-role-assignments-by-login  C7, shape B: the same
 *       read with ProbeOwner expanded and ProbeOwner/Name selected
 *
 * DEPENDS ON (read back, voiding what rests on them when they do not hold)
 *   access.item-acl.items-fixture-library       a document library this run created
 *   access.item-acl.items-fixture-files         at least 120 files, counted by a paged
 *       read that expands nothing, over at least two pages
 *   access.item-acl.items-fixture-owner-column  a User column ProbeOwner on the library
 *   access.item-acl.items-fixture-broken        three files (the 10th, the 100th and
 *       the 111th by Id) unique, holding this account at Read and naming it in
 *       ProbeOwner; three more (the first, the 101st and the last) inheriting; each
 *       read per item, which is the CONTROL the pages are set beside
 *
 * HOW TO RUN: on a site you own, F12 -> Console. Paste; it prints its plan and
 * stops. Set CONFIRMED and ALLOW_WRITES to true and paste again. Copy the
 * RESULTS block back verbatim.
 *
 * WHEN FINISHED: paste with CLEANUP, CONFIRMED and ALLOW_WRITES true. It
 * recycles the library only when its description is this probe's.
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
    // An answer's JSON may spell a non-ASCII letter as a \u escape, so that spelling is masked too.
    const escaped = text.replace(/[^\x20-\x7e]/g, (c) => `\\u${c.charCodeAt(0).toString(16).padStart(4, '0')}`);
    if (escaped !== text) IDENTITIES.push({ text: escaped, mask, whole });
    IDENTITIES.sort((a, b) => b.text.length - a.text.length);
  };
  const literal = (text) => text.replace(/[.*+?^$()|[\]\\{}]/g, '\\$&');
  const pattern = ({ text, whole }) => (whole
    ? new RegExp(`(?<![\\p{L}\\p{N}_])${literal(text)}(?![\\p{L}\\p{N}_])`, 'giu')
    : new RegExp(literal(text), 'gi'));
  // Logins and emails go first, even ones never learned, so a display name inside one cannot break it up.
  // A login's value runs through apostrophes and a backslash before a letter or digit (a Windows claim's
  // domain\user, escaped or not), and stops at a backslash before anything else, so JSON escapes survive.
  // An address's local part is RFC 5322's atext and dots, with any letter or digit (RFC 6531).
  const scrub = (value) => {
    let out = redactTenant(value)
      .replace(/(i:0[^|\s'"]*\|([^|\s'"]+\|)?)(?:[^\s"|\\]|\\+(?=[\p{L}\p{N}]))+/giu, '$1<account>')
      .replace(/[\p{L}\p{N}!#$%&'*+/=?^_`{|}~.-]+@[^\s'"<>\\]+/giu, '<account>');
    for (const known of IDENTITIES) out = out.replace(pattern(known), known.mask);
    return out;
  };
  // The one switch: set once this account's display name is not learned, since no mask can then be complete.
  let withheld = false;
  const WITHHELD = '(text withheld: this account\'s display name was not learned)';
  // Text from an answer, masked, or withheld once masking cannot be complete.
  const quote = (text) => (withheld ? WITHHELD : scrub(text));
  // Every answer's text once text is withheld, so a fixture can tell a value read from one from its own.
  const ANSWERS = [];
  // A value from an answer as JSON; one holding any text is withheld with it, since a number names nobody.
  const quoteValue = (value) => {
    const json = JSON.stringify(value);
    return withheld && typeof json === 'string' && json.includes('"') ? WITHHELD : scrub(json);
  };
  // Every answer maskedHead found unanswered or refused, so a fixture can tell an unanswered request, which
  // leaves it open, from a refusal, which is settled.
  const UNHEARD = [];
  const REFUSED = [];
  // Set by an unanswered write and cleared by beginFixture, since an absence after one may be that write unlanded.
  let writeUnheard = false;
  // An answer that a thing is not there: a 404, or the absent-field 400 that rollback.js.j2 also accepts.
  const absenceOf = (status, parsed) => {
    const error = parsed && typeof parsed === 'object' ? parsed['odata.error'] || parsed.error : null;
    const code = String((error && error.code) || '');
    return status === 404 || (status === 400 && code.includes('-2147024809')
      && code.includes('System.ArgumentException'));
  };
  // rawHead cuts a response's text short, so the text is masked first and a cut never splits a name unmasked.
  const maskedHead = (res, write = false) => {
    // A request that never answered carries its error, not an answer, in its text.
    const head = rawHead({ ...res, text: res.status === null ? scrub(res.text) : quote(res.text) });
    if (withheld && res.status !== null) ANSWERS.push(String(res.text));
    if (head && head.outcome === 'NOT ESTABLISHED') {
      UNHEARD.push(head.why);
      if (write) writeUnheard = true;
    } else if (head && head.outcome === 'REFUSED') {
      if (write || !writeUnheard || !absenceOf(res.status, res.parsed !== undefined ? res.parsed : res.body)) {
        REFUSED.push(head.why);
      } else UNHEARD.push(`${head.why}, after a write that went unanswered`);
    }
    return head;
  };
  // A single-entity read's body when it is a JSON object, or null, so no property is read off anything else.
  const recordBody = (res) => (res.parsed && typeof res.parsed === 'object' && !Array.isArray(res.parsed)
    ? res.parsed : null);
  // A read answered 2xx with no JSON object has nothing to read, which the harness's unanswered counts as none.
  const readHead = (res) => {
    const head = maskedHead(res);
    if (!head && recordBody(res) === null) UNHEARD.push(`the read answered HTTP ${res.status} with no JSON object`);
    return head;
  };
  // Reads this account before any mask for its display name exists, so nothing of a failed answer is quoted,
  // and withholds every later answer's text when no display name of two or more characters comes back.
  const readAccount = async () => {
    const res = await sendRaw('web/currentuser?$select=Id,Email,LoginName,Title');
    const account = res.ok ? recordBody(res) : null;
    const said = res.status === null ? 'the account read never answered'
      : `the account read answered HTTP ${res.status}${res.ok && !account ? ' with no JSON object' : ''}`;
    if (!account && (res.status === null || res.ok || !isRefusal(res.status))) UNHEARD.push(said);
    if (account) {
      knowIdentity(account.Email, '<account>');
      knowIdentity(account.LoginName, '<account>');
      knowIdentity(account.Title, '<name>', true);
    }
    const named = account && typeof account.Title === 'string' && account.Title.length >= 2;
    if (!named) {
      withheld = true;
      log('INFO', `this account's display name was not learned (${account ? 'no display name to mask came back'
        : said}), so no text from an answer is quoted for the rest of this run; statuses still are.`);
    }
    return { account, said: account ? `HTTP ${res.status}` : said };
  };
  // For a probe with no current-user fixture: learns this account so its display name is masked too.
  const learnIdentity = async () => {
    await readAccount();
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
  // Whether two arrays hold the same elements as often each, compared by ===, never by a serialised form.
  const sameElements = (a, b) => Array.isArray(a) && Array.isArray(b) && a.length === b.length
    && a.every((x) => a.filter((y) => y === x).length === b.filter((y) => y === x).length);
  // A title or server-relative path inside an OData string literal, its apostrophes doubled as deploy/_folders does.
  const pathLiteral = (path) => String(path).replace(/'/g, "''");
  // A 2xx body's value array when every entry is a JSON object; otherwise rows is null and shape says why.
  const entriesOf = (parsed) => {
    if (!parsed || typeof parsed !== 'object' || !Array.isArray(parsed.value)) {
      return { rows: null, shape: 'carried no value array' };
    }
    const bad = parsed.value.findIndex((row) => !row || typeof row !== 'object' || Array.isArray(row));
    return bad === -1 ? { rows: parsed.value, shape: null } : { rows: null, shape: `carried entry ${bad + 1} `
      + `of its value array as ${quoteValue(parsed.value[bad]).slice(0, 80)}, not an object` };
  };
  // A continuation link in the three spellings the search-discovery probe reads plus a bare __next, or null.
  const continuationOf = (parsed) => {
    if (!parsed || typeof parsed !== 'object') return null;
    const link = parsed['odata.nextLink'] || parsed['@odata.nextLink'] || parsed.__next
      || (parsed.d && typeof parsed.d === 'object' ? parsed.d.__next : undefined);
    return typeof link === 'string' && link ? link : null;
  };
  // voidDependents, except that a row already void keeps its first reason: void is terminal.
  const voidRows = (ids, reason) => voidDependents(ids.filter((one) => {
    const row = RESULTS.find((r) => r.id === one);
    return !row || row.state !== 'void';
  }), reason);
  // The numeric Id a 2xx create answered, or null; a 2xx with no JSON object is noted as unanswered.
  const createdId = (made) => {
    if (!made.ok) return null;
    const body = recordBody({ parsed: made.body });
    if (body === null) UNHEARD.push(`the create answered HTTP ${made.status} with no JSON object`);
    return body && Number.isInteger(body.Id) ? body.Id : null;
  };
  // Where the requests of the fixture about to be established begin in UNHEARD.
  let fixtureStart = 0;
  let refusedStart = 0;
  const beginFixture = () => {
    fixtureStart = UNHEARD.length;
    refusedStart = REFUSED.length;
    writeUnheard = false;
  };
  // A write's answer is noted, so a fixture can tell an unanswered write from a refused one.
  const spWrite = async (...args) => {
    const res = await spPost(...args);
    maskedHead(res, true);
    return res;
  };
  // establishFixture, except that a fixture any of whose requests since beginFixture went unanswered is left
  // open with its dependents, since an unanswered request says nothing about the fixture.
  const settleFixture = async (id, read, declared, dependents) => {
    const start = fixtureStart;
    const refusedFrom = refusedStart;
    // Rows an earlier fixture voided are put back as they were, since establishFixture voids them again.
    const earlier = RESULTS.filter((r) => dependents.includes(r.id) && r.state === 'void').map((r) => ({ ...r }));
    // The harness prints every value it reads, so once text is withheld a declared value holding text found in
    // an answer is judged here and handed on as a verdict; one equal to its declared literal stays.
    const HELD = '(text withheld; it held)';
    const textsOf = (v) => (typeof v === 'string' ? [v]
      : v && typeof v === 'object' ? Object.values(v).flatMap(textsOf) : []);
    const answered = (value) => textsOf(value).some((s) => s.length > 0
      && ANSWERS.some((a) => a.includes(s) || a.includes(JSON.stringify(s).slice(1, -1))));
    const judged = (body) => (!withheld || !body || typeof body !== 'object' ? body
      : Object.fromEntries(Object.entries(body).map(([name, value]) => {
        const want = declared[name];
        if (want === undefined || value === want || !answered(value)) return [name, value];
        return [name, typeof want === 'function' && want(value) === true ? HELD : WITHHELD];
      })));
    const verdicts = Object.fromEntries(Object.entries(declared).map(([name, want]) => [name,
      typeof want === 'function' ? (v) => v === HELD || (v !== WITHHELD && want(v)) : want]));
    // A read that throws never answered, so it counts as unanswered like a throttle.
    const heard = async () => {
      try {
        const got = await read();
        return got && typeof got === 'object' ? { ...got, body: judged(got.body) } : got;
      } catch (err) {
        UNHEARD.push(`the read never answered (${scrub(String((err && err.message) || err)).slice(0, 200)})`);
        throw err;
      }
    };
    const held = await establishFixture(id, heard, verdicts, dependents);
    const restore = () => earlier.forEach((was) => Object.assign(RESULTS.find((r) => r.id === was.id), was));
    if (held) return true;
    // A refusal is a settled answer, so it keeps the FAIL even beside a request that went unanswered.
    if (UNHEARD.length === start || REFUSED.length > refusedFrom) {
      restore();
      return false;
    }
    const why = `${[...new Set(UNHEARD.slice(start))].join('; ')}; a re-run can ask it`;
    const row = RESULTS.find((r) => r.id === id);
    record(id, row ? row.question : id, 'NOT ESTABLISHED', why);
    for (const one of dependents) {
      if (earlier.some((was) => was.id === one)) continue;
      const dependent = RESULTS.find((r) => r.id === one);
      record(one, dependent ? dependent.question : one, 'NOT ESTABLISHED', `not asked: ${why}`);
    }
    restore();
    return false;
  };
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
    if (absenceOf(res.status, res.body)) return { gone: true, why: null };
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
    if (pre.ok && recordBody({ parsed: pre.body }) === null) {
      return leaveOpen(`the ownership read of '${title}' answered HTTP ${pre.status} with no JSON; `
        + 'nothing was created');
    }
    if (pre.ok) {
      // A title ending in this run's token names no list before this run makes one, so a list found here is
      // not this run's, whatever its description, and is never recycled or built over.
      record(id, question, 'FAIL', `a list named '${title}' already exists`
        + `${pre.body.Description === description ? ' with this probe\'s description' : ''}; refusing to modify it`);
      voidRows(dependents, 'the scratch list is not one this run created');
      return { held: false, merge: null, body: null };
    } else if (isRefusal(pre.status) && pre.status !== 404) {
      // A refused ownership read is an answer, so nothing is created and the claim fails with its reason.
      record(id, question, 'FAIL', `the ownership read of '${title}' was refused (HTTP ${pre.status})`
        + `${pre.body ? `: ${quoteValue(pre.body).slice(0, 200)}` : ''}; nothing was created`);
      voidRows(dependents, 'the scratch list was not created');
      return { held: false, merge: null, body: null };
    } else if (pre.status !== 404) {
      // A by-title read answers an absent list 404 (the live finding rollback.js.j2 cites); anything else is unknown.
      return leaveOpen(`the ownership read of '${title}' ${unanswered(pre)}`
        + `${pre.body ? `: ${quoteValue(pre.body).slice(0, 200)}` : ''}; nothing was created`);
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
    if (!made.ok && isRefusal(made.status)) {
      // A refused create may still have made the list, so its title is read back before it is let go.
      let back;
      try {
        back = await spGet(`${path}?$select=Id,Description`);
      } catch (err) {
        back = { ok: false, status: null, why: `never answered (${scrub(String((err && err.message) || err))})` };
      }
      const found = back.ok ? recordBody({ parsed: back.body }) : null;
      const landedId = found && found.Description === description ? guidOf(found.Id) : null;
      if (landedId !== null) CREATED_LISTS.push({ title, id: landedId });
      else if (back.status !== 404) CREATED_LISTS.push({ title, id: null });
      const unknown = back.why || (!back.ok ? unanswered(back) : found === null
        ? `answered HTTP ${back.status} with no JSON object` : 'found it with another description');
      const landing = landedId !== null ? `, but a list '${title}' with this probe's description reads back `
        + `(list ${landedId}), so it is recycled` : back.status === 404 ? `; no list holds '${title}'`
        : `; whether a list '${title}' landed is unknown (the read-back ${unknown}), so check it by hand`;
      record(id, question, 'FAIL',
        `the list create answered HTTP ${made.status}: ${quote(made.text).slice(0, 300)}${landing}`);
      voidRows(dependents, 'the scratch list was not created');
      return { held: false, merge: null, body: null };
    }
    if (!made.ok) {
      // Throttled, unauthorised or unavailable is no answer, and the list may exist, so the title is kept.
      CREATED_LISTS.push({ title, id: null });
      return leaveOpen(`the list create ${unanswered({ ok: false, status: made.status })}: `
        + `${quote(made.text).slice(0, 200)}, so a list '${title}' may now exist`);
    }
    if (recordBody({ parsed: made.body }) === null) {
      CREATED_LISTS.push({ title, id: null });
      return leaveOpen(`the list create answered HTTP ${made.status} with no JSON object, so a list '${title}' `
        + 'may now exist');
    }
    const created = { title, id: guidOf(made.body.Id) };
    // Two creates answering one Id would send both lists' writes to one list, so the second is not built on.
    if (created.id !== null && CREATED_LISTS.some((one) => one.id === created.id)) {
      log('FAIL', `'${title}' answered list ${created.id}, which another list this run created holds; `
        + `recycle '${title}' by hand.`);
      record(id, question, 'FAIL', `the list create answered HTTP ${made.status} with the Id of another list `
        + `this run created (${created.id}), so nothing was written to it; recycle it by hand`);
      voidRows(dependents, 'the scratch list answered the Id of another list this run created');
      return { held: false, merge: null, body: null };
    }
    // Without the create's own Id a title read could name a rebound list, so nothing more is written.
    if (created.id === null) {
      CREATED_LISTS.push(created);
      record(id, question, 'FAIL', `the list create answered HTTP ${made.status} with no list Id, so nothing `
        + `ties '${title}' to the list it made; nothing was written to it`);
      voidRows(dependents, 'the scratch list answered no Id to address it by');
      return { held: false, merge: null, body: null };
    }
    // The answered Id is written to or recycled only once it reads back this run's title and this probe's
    // Description, since a wrong Id would point both at a list this run did not make.
    let mine;
    try {
      mine = await spGet(`web/lists(guid'${created.id}')?$select=Id,Title,Description`);
    } catch (err) {
      mine = { ok: false, status: null, why: `never answered (${scrub(String((err && err.message) || err))})` };
    }
    const own = mine.ok ? recordBody({ parsed: mine.body }) : null;
    const proved = own !== null && own.Title === title && own.Description === description
      && guidOf(own.Id) === created.id;
    if (!proved) {
      const said = mine.why || (own !== null ? `reads back Title ${quoteValue(own.Title)} and `
        + `${own.Description === description ? 'this probe\'s Description' : 'another Description'}, not '${title}' `
        + 'with this probe\'s' : mine.ok ? `answered HTTP ${mine.status} with no JSON object`
        : absenceOf(mine.status, mine.body) ? 'answered that no list holds it' : unanswered(mine));
      const why = own !== null ? `list ${created.id} ${said}` : `the read of list ${created.id} ${said}`;
      // Named for a check by hand, never recycled by an Id this run did not prove its own.
      CREATED_LISTS.push({ title, id: null, why: `answered list ${created.id}, which did not read back as this `
        + 'run\'s list' });
      // A contradicting read or a refusal settles it; a read that said nothing leaves it open.
      if (own === null && (mine.why || mine.ok || !isRefusal(mine.status))) {
        return leaveOpen(`${why}, so nothing was written to it`);
      }
      record(id, question, 'FAIL', `${why}; nothing was written to it`);
      voidRows(dependents, 'the scratch list did not read back as this run\'s');
      return { held: false, merge: null, body: null };
    }
    CREATED_LISTS.push(created);
    let merge = null;
    beginFixture();
    if (settings !== null) {
      // Sent by Id, so a title rebound cannot take this list's settings.
      merge = await spWrite(`web/lists(guid'${created.id}')`, { __metadata: { type: 'SP.List' }, ...settings },
        await getDigest(), { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
      log('INFO', `list settings MERGE on '${title}': HTTP ${merge.status}`
        + `${merge.ok ? '' : ` ${quote(merge.text).slice(0, 200)}`}`);
    }
    const select = [...new Set(['Id', 'BaseTemplate', 'Description', ...Object.keys(declared)])].join(',');
    // The MERGE's answer joins the read-back, so a refused setting shows its reason in RESULTS.
    const answered = merge === null ? {} : { Settings: `HTTP ${merge.status}`
      + `${merge.ok ? '' : `: ${quote(merge.text).slice(0, 200)}`}` };
    // Recorded, never judged: what the MERGE answered is an observation, and the read-back decides.
    const settled = merge === null ? {} : { Settings: (v) => typeof v === 'string' };
    let read = null;
    const held = await settleFixture(id, async () => {
      read = await spGet(`${path}?$select=${select}`);
      readHead({ ...read, parsed: read.body, text: JSON.stringify(read.body) });
      // A body that is not a JSON object is no answer; the harness would read a property off it.
      if (read.ok && recordBody({ parsed: read.body }) === null) read = { ...read, body: null };
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
    for (const { title, id, why } of [...CREATED_LISTS].reverse()) {
      if (id === null) {
        log('FAIL', `'${title}' ${why || 'never answered a list Id'}, so it was not recycled; if it stands, `
          + 'recycle it by hand.');
        continue;
      }
      // By Id, so a title rebound cannot redirect it.
      await recycleList(title, id);
    }
  };
  log('INFO', 'probe revision beb0f399. Quote this when reporting results.');

  // A fixed name, so CLEANUP finds what a run made; it is claimed by its description.
  const LIB = 'dbmlsp Probe ItemsAcl';
  const OWNERSHIP = 'dbml-sharepoint items role-assignments probe fixture. Safe to delete.';
  const OWNER = 'ProbeOwner';
  // 130 files, so the flow's 100-item page is followed by a second.
  const FILE_COUNT = 130;
  const MIN_FILES = 120;
  // A nextLink that never ends is cut here, well past the two pages the fixture needs.
  const MAX_PAGES = 20;
  const ROLES = 'RoleAssignments/PrincipalId,RoleAssignments/Member/PrincipalType,'
    + 'RoleAssignments/Member/LoginName,RoleAssignments/RoleDefinitionBindings/Id,'
    + 'RoleAssignments/RoleDefinitionBindings/Name';
  const EXPAND = 'RoleAssignments/Member,RoleAssignments/RoleDefinitionBindings';
  const byTitle = `web/lists/getbytitle('${pathLiteral(LIB)}')`;

  const Q = {
    library: 'a document library this run created',
    files: `at least ${MIN_FILES} files, counted by a paged read that expands nothing, over at least two pages`,
    column: `a User column ${OWNER} on the library`,
    broken: 'three files unique, each holding this account at Read and naming it in ProbeOwner, and three '
      + 'inheriting, each read per item as the CONTROL the pages are set beside',
    byId: 'Does a page of items read with RoleAssignments expanded and ProbeOwnerId selected carry each '
      + 'item\'s bindings, as a per-item read returns them?',
    byLogin: 'Does a page of items read with ProbeOwner and RoleAssignments expanded carry each item\'s '
      + 'bindings, as a per-item read returns them?',
  };
  expect('access.item-acl.items-fixture-library', Q.library);
  expect('access.item-acl.items-fixture-files', Q.files);
  expect('access.item-acl.items-fixture-owner-column', Q.column);
  expect('access.item-acl.items-fixture-broken', Q.broken);
  expect('access.item-acl.items-expand-role-assignments', Q.byId);
  expect('access.item-acl.items-expand-role-assignments-by-login', Q.byLogin);

  const ROWS = ['access.item-acl.items-expand-role-assignments',
    'access.item-acl.items-expand-role-assignments-by-login'];
  const AFTER_COLUMN = ['access.item-acl.items-fixture-broken', ...ROWS];
  const AFTER_FILES = ['access.item-acl.items-fixture-owner-column', ...AFTER_COLUMN];
  const AFTER_LIBRARY = ['access.item-acl.items-fixture-files', ...AFTER_FILES];

  if (!CONFIRMED) {
    log('INFO', `This creates a library '${LIB}' on ${WEB} with ${FILE_COUNT} small text files and a`);
    log('INFO', `User column ${OWNER}, breaks inheritance on three files and binds this account to Read on`);
    log('INFO', 'each, then reads every page of the library twice, as a flow would, with each item\'s role');
    log('INFO', 'assignments expanded. CLEANUP recycles the library.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  let digest = null;
  const write = async (path, body = {}, extra = {}) => {
    digest = digest || await getDigest();
    return spWrite(path, body, digest, extra);
  };
  // Files/add takes the file's bytes as its body, so the text goes raw as text/plain, as the large-library fixture sends it.
  const upload = async (path, text) => {
    digest = digest || await getDigest();
    let res;
    try {
      const sent = await fetch(`${WEB}/_api/${path}`, { method: 'POST', body: text, headers: {
        Accept: 'application/json;odata=nometadata', 'Content-Type': 'text/plain', 'X-RequestDigest': digest } });
      res = { ok: sent.ok, status: sent.status, text: await sent.text() };
    } catch (err) {
      res = { ok: false, status: null, text: `no response: ${err && err.message ? err.message : String(err)}` };
    }
    maskedHead({ ...res, parsed: null }, true);
  };

  // ---- CLEANUP: recycle the library, only when its description is this probe's ----
  if (CLEANUP) {
    const held = await sendRaw(`${byTitle}?$select=Id,Description`);
    const head = readHead(held);
    const body = head ? null : recordBody(held);
    if (body && body.Description === OWNERSHIP && guidOf(body.Id)) {
      await recycleList(LIB, guidOf(body.Id));
    } else if (held.status === 404 || (body && body.Description !== OWNERSHIP)) {
      log('INFO', `CLEANUP: no library '${LIB}' of this probe's to remove`
        + `${body ? ' (its description differs)' : ''}.`);
    } else {
      // Only a 404 says the library is gone, so any other answer leaves it for a second paste.
      const why = head ? head.why : body ? 'the read answered no list Id'
        : `the read answered HTTP ${held.status} with no JSON object`;
      log('FAIL', `CLEANUP: could not tell whether '${LIB}' is this probe's (${why}); nothing was recycled. `
        + 'Paste CLEANUP again.');
    }
    for (const row of RESULTS) record(row.id, row.question, 'NOT REACHED', 'a CLEANUP paste asks nothing');
    report();
    return;
  }

  // One read as a flow sends it, with the Retry-After header a throttle carries.
  const readPage = async (path) => {
    let res;
    try {
      res = await fetch(`${WEB}/_api/${path}`, { headers: { Accept: 'application/json;odata=nometadata' } });
    } catch (err) {
      return { ok: false, status: null, parsed: null, retryAfter: null,
        text: `no response: ${err && err.message ? err.message : String(err)}` };
    }
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* not JSON; the text is kept */ }
    const retryAfter = res.headers && typeof res.headers.get === 'function' ? res.headers.get('Retry-After') : null;
    return { ok: res.ok, status: res.status, text, parsed, retryAfter };
  };
  // Every page from `first`, following odata.nextLink as a flow's Do until would, up to MAX_PAGES.
  const readAll = async (first) => {
    const pages = [];
    const items = new Map();
    let path = first;
    let stop = null;
    while (path && pages.length < MAX_PAGES) {
      const res = await readPage(path);
      const page = { n: pages.length + 1, status: res.status, retryAfter: res.retryAfter };
      pages.push(page);
      const head = maskedHead(res);
      const { rows, shape } = head ? { rows: null, shape: null } : entriesOf(res.parsed);
      if (head || rows === null) {
        // A 2xx with no value array is no answer, so a fixture resting on this read stays open.
        if (!head) UNHEARD.push(`page ${page.n} answered HTTP ${res.status} but ${shape}`);
        stop = { status: res.status, head: head || { outcome: 'NOT ESTABLISHED',
          why: `page ${page.n} answered HTTP ${res.status} but ${shape}` } };
        break;
      }
      const next = continuationOf(res.parsed);
      Object.assign(page, { items: rows.length, next: next !== null,
        carrying: rows.filter((r) => Array.isArray(r.RoleAssignments)).length,
        unique: rows.filter((r) => r.HasUniqueRoleAssignments === true).length });
      for (const row of rows) items.set(row.Id, { page: page.n, row });
      // A link this probe cannot turn into a path on this site is not followed, so nothing else answers for it.
      if (next !== null && next.indexOf('/_api/') === -1) {
        const why = `page ${page.n} answered a nextLink with no /_api/ path, which this probe cannot follow`;
        UNHEARD.push(why);
        stop = { status: res.status, head: { outcome: 'NOT ESTABLISHED', why } };
        break;
      }
      path = next ? next.slice(next.indexOf('/_api/') + 6) : null;
    }
    return { pages, items, stop, capped: stop === null && path !== null };
  };
  // Bindings as `principal:level Id`, sorted, from a role assignment array.
  const keysOf = (assignments) => assignments.flatMap((a) => (a && Array.isArray(a.RoleDefinitionBindings)
    ? a.RoleDefinitionBindings.map((b) => `${a.PrincipalId}:${b && b.Id}`) : [])).sort();
  const pageLine = (p) => `page ${p.n}: HTTP ${p.status === null ? 'none' : p.status}`
    + `${p.items === undefined ? '' : `, ${p.items} item(s), ${p.carrying} carrying RoleAssignments, `
      + `${p.unique} unique, nextLink ${p.next ? 'present' : 'absent'}`}`
    + `${p.retryAfter ? `, Retry-After ${scrub(p.retryAfter)}` : ''}`;

  try {
    const heardFrom = UNHEARD.length;
    const { account } = await readAccount();
    // Kept for the fixture that binds this account, which an unanswered account read leaves open.
    const accountUnheard = UNHEARD.slice(heardFrom);
    const me = account && Number.isInteger(account.Id) ? account.Id : null;
    const library = await claimScratchList({ id: 'access.item-acl.items-fixture-library', question: Q.library,
      title: LIB, description: OWNERSHIP, dependents: AFTER_LIBRARY, baseTemplate: 101,
      declared: { ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 } });
    if (!library.held) return;
    const lib = library.path;

    // ---- the files: FILE_COUNT text files, counted by a read that expands nothing ----
    beginFixture();
    const rootRead = await sendRaw(`${lib}/RootFolder?$select=ServerRelativeUrl`);
    const root = readHead(rootRead) ? null : (recordBody(rootRead) || {}).ServerRelativeUrl;
    if (root) {
      const folder = `web/GetFolderByServerRelativeUrl('${pathLiteral(root)}')/Files`;
      for (let n = 1; n <= FILE_COUNT; n += 1) {
        await upload(`${folder}/add(url='items-acl-${String(n).padStart(3, '0')}.txt',overwrite=true)`,
          'dbmlsp items role-assignments probe file');
      }
    }
    let ids = [];
    if (!await settleFixture('access.item-acl.items-fixture-files', async () => {
      const counted = await readAll(`${byTitle}/items?$select=Id&$top=100`);
      ids = [...counted.items.keys()].sort((a, b) => a - b);
      // Integers, since each sampled Id is spliced into a write URL.
      return { ok: true, status: 200, body: { Count: ids.length, Pages: counted.pages.length,
        Integers: ids.every((v) => Number.isInteger(v) && v > 0),
        Read: counted.stop ? counted.stop.head.why : counted.capped ? `cut at ${MAX_PAGES} pages` : 'complete' } };
    }, { Count: (v) => v >= MIN_FILES, Pages: (v) => v >= 2, Integers: true, Read: 'complete' },
    AFTER_FILES)) return;

    // ---- the owner column ----
    beginFixture();
    const made = await write(`${lib}/fields`, { __metadata: { type: 'SP.FieldUser' }, FieldTypeKind: 20,
      SelectionMode: 0, Title: OWNER, Required: false }, { ...VERBOSE_WRITE });
    log('INFO', `create ${OWNER}: HTTP ${made.status}`);
    if (!await settleFixture('access.item-acl.items-fixture-owner-column', async () => {
      const read = await sendRaw(`${lib}/fields/getbyinternalnameortitle('${OWNER}')`
        + '?$select=InternalName,TypeAsString');
      return { ok: read.ok, status: read.status, body: readHead(read) ? null : recordBody(read) };
    }, { InternalName: OWNER, TypeAsString: 'User' }, AFTER_COLUMN)) return;

    // ---- three files broken, bound to this account at Read and naming it; three left inheriting ----
    const SAMPLES = [[9, true], [99, true], [110, true], [0, false], [100, false], [ids.length - 1, false]]
      .map(([at, broken]) => ({ id: ids[at], broken, keys: null, label: `${broken ? 'broken' : 'inheriting'} `
        + `item ${ids[at]}` }));
    beginFixture();
    UNHEARD.push(...accountUnheard);
    const readLevel = await sendRaw("web/roledefinitions/getbyname('Read')?$select=Id");
    const readId = readHead(readLevel) ? null : (recordBody(readLevel) || {}).Id;
    // An Id that is not a whole number would be spliced into the grant's URL, so nothing is granted.
    if (Number.isInteger(readId) && me !== null) {
      for (const sample of SAMPLES.filter((s) => s.broken)) {
        const item = `${lib}/items(${sample.id})`;
        await write(`${item}/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)`);
        await write(`${item}/roleassignments/addroleassignment(principalid=${me},roledefid=${readId})`);
        await write(item, { __metadata: { type: library.body.ListItemEntityTypeFullName }, [`${OWNER}Id`]: me },
          { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
      }
    }
    if (!await settleFixture('access.item-acl.items-fixture-broken', async () => {
      const held = { Unique: 0, UserRead: 0, Owner: 0, Inheriting: 0, Controls: 0 };
      for (const sample of SAMPLES) {
        const item = `${lib}/items(${sample.id})`;
        const read = await sendRaw(`${item}?$select=HasUniqueRoleAssignments,${OWNER}Id`);
        const body = readHead(read) ? null : recordBody(read);
        const bound = await sendRaw(`${item}/roleassignments?$expand=Member,RoleDefinitionBindings`);
        const rows = readHead(bound) ? null : entriesOf(bound.parsed).rows;
        // A 2xx with no value array is no answer, so the fixture stays open rather than failing.
        if (bound.ok && rows === null) UNHEARD.push(`the bindings read of item ${sample.id} carried no value array`);
        sample.keys = rows === null ? null : keysOf(rows);
        if (rows !== null) held.Controls += 1;
        if (!sample.broken) {
          if (body && body.HasUniqueRoleAssignments === false) held.Inheriting += 1;
          continue;
        }
        if (body && body.HasUniqueRoleAssignments === true) held.Unique += 1;
        if (body && me !== null && body[`${OWNER}Id`] === me) held.Owner += 1;
        if (sample.keys && sample.keys.includes(`${me}:${readId}`)) held.UserRead += 1;
      }
      return { ok: true, status: 200, body: Object.fromEntries(Object.entries(held)
        .map(([name, n]) => [name, `${n} of ${name === 'Controls' ? SAMPLES.length : 3}`])) };
    }, { Unique: '3 of 3', UserRead: '3 of 3', Owner: '3 of 3', Inheriting: '3 of 3', Controls: '6 of 6' },
    ROWS)) return;

    // ---- C7: each shape's read, every page to the end, set beside the per-item reads ----
    const ask = async (id, question, select, expand, ownerOf) => {
      const got = await readAll(`${byTitle}/items?$select=Id,HasUniqueRoleAssignments,${select},${ROLES}`
        + `&$expand=${expand}${EXPAND}&$top=100`);
      if (got.stop) {
        const last = got.pages[got.pages.length - 1];
        const throttled = got.stop.status === 429 || got.stop.status === 503;
        record(id, question, throttled ? 'THROTTLED' : got.stop.head.outcome,
          `${got.pages.map(pageLine).join('; ')}; the read stopped: ${got.stop.head.why}`
          + `${throttled && !last.retryAfter ? '; no Retry-After header' : ''}`, throttled ? 'open' : undefined);
        return;
      }
      const total = got.pages.reduce((sum, p) => sum + p.items, 0);
      const carrying = got.pages.reduce((sum, p) => sum + p.carrying, 0);
      const bare = [...got.items.entries()].filter(([, at]) => !Array.isArray(at.row.RoleAssignments))
        .map(([itemId]) => itemId);
      const samples = SAMPLES.map((sample) => {
        const at = got.items.get(sample.id);
        const carried = at && Array.isArray(at.row.RoleAssignments) ? keysOf(at.row.RoleAssignments) : null;
        const same = carried !== null && carried.join(' ') === sample.keys.join(' ');
        const owner = at && sample.broken ? `; ${ownerOf(at.row)}` : '';
        return { same, line: `${sample.label} ${at ? `(page ${at.page})` : 'on no page'}: the page `
          + `${carried === null ? 'carried no RoleAssignments' : `held ${carried.join(' ') || 'none'}`}, the `
          + `per-item read ${sample.keys.join(' ') || 'none'}${carried === null ? '' : same ? ', the same'
            : ', different'}${owner}` };
      });
      // By Id, so an item read twice cannot stand in for one never read.
      const every = carrying === total && ids.every((one) => got.items.has(one)) && !got.capped
        && samples.every((s) => s.same);
      // Scrubbed whole, since its Ids and bindings are values from the answer.
      record(id, question,
        total > 0 && carrying === 0 ? 'NO ITEM CARRIES BINDINGS' : every ? 'EVERY ITEM CARRIES ITS BINDINGS' : 'PARTIAL',
        scrub(`${got.pages.map(pageLine).join('; ')}; ${total} item(s) read of the ${ids.length} counted`
        + `${got.capped ? `, the nextLink still present after ${MAX_PAGES} pages` : ''}`
        + `${carrying > 0 && bare.length ? `; without RoleAssignments: items ${bare.slice(0, 10).join(', ')}`
          + `${bare.length > 10 ? ` and ${bare.length - 10} more` : ''}` : ''}`
        + `; ${samples.map((s) => s.line).join('; ')}`));
    };
    const logins = (row) => (Array.isArray(row.RoleAssignments) ? row.RoleAssignments : [])
      .map((a) => a && a.Member && a.Member.LoginName);
    await ask('access.item-acl.items-expand-role-assignments', Q.byId, `${OWNER}Id`, '',
      (row) => `${OWNER}Id ${quoteValue(row[`${OWNER}Id`])}, among the page's principals: `
        + `${(Array.isArray(row.RoleAssignments) ? row.RoleAssignments : [])
          .some((a) => a && a.PrincipalId === row[`${OWNER}Id`]) ? 'yes' : 'no'}`);
    await ask('access.item-acl.items-expand-role-assignments-by-login', Q.byLogin, `${OWNER}/Name`, `${OWNER},`,
      (row) => {
        const name = row[OWNER] && typeof row[OWNER] === 'object' ? row[OWNER].Name : undefined;
        return `${OWNER}/Name ${quoteValue(name)}, among the page's logins: `
          + `${name !== undefined && logins(row).includes(name) ? 'yes' : 'no'}`;
      });
  } catch (err) {
    log('FAIL', `probe aborted: ${scrub(String((err && err.message) || err)).slice(0, 240)}. `
      + 'The unasked rows stay open; paste with CLEANUP to remove what was made.');
  } finally {
    report();
  }
})();
