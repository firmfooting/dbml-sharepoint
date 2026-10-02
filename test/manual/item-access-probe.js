
/** ---- dbml-sharepoint PROBE: A FILE'S OWN ROLE ASSIGNMENTS IN A LIBRARY WITH UNIQUE PERMISSIONS ----
 *
 * REVISION: 2aabdd87
 *
 * WHY: a flow that grants item-level access breaks inheritance on one file,
 * binds one user to a custom level there, later removes that binding, and
 * returns the file to inheritance when it holds nothing the library does
 * not. Learn documents each REST call (SP.SecurableObject breakRoleInheritance
 * and resetRoleInheritance, SP.RoleAssignmentCollection addRoleAssignment and
 * removeRoleAssignment) but not what each leaves on the file, the library and
 * the web. These rows ask.
 *
 * QUESTIONS (OBSERVES, recorded verbatim, never compared with an expected value)
 *   access.item-acl.break-copies-parent-groups  C1, STATE 1: after
 *       breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true) on a
 *       file, its bindings beside the library's, read over the settle window
 *   access.item-acl.parent-grant-after-break  C2, STATE 1: the broken file's
 *       bindings after a third group is granted at the library
 *   access.item-acl.custom-level-user-grant  C3, STATE 1: the test user's
 *       binding on a file, its effective permissions on the file, the library
 *       and the web, and the levels the grant left at the library and the web;
 *       then BY HAND, as the test user: an edit, the version history, and a
 *       delete tried on a second file bound the same way, so STATE 2 keeps the first
 *   access.item-acl.item-only-user-views  C4, STATE 1: the test user's effective
 *       permissions on the library; then BY HAND, whether the library's view
 *       shows the user the file
 *   access.item-acl.user-binding-removal  C5, STATE 2: the file's bindings after
 *       removeroleassignment, over the window; the user's levels at the library
 *       and the web, and its effective permissions on the file, afterwards
 *   access.item-acl.reset-restores-parent  C6, STATE 2: after
 *       resetroleinheritance on a file holding a user grant and copied groups,
 *       HasUniqueRoleAssignments over the window, the file's bindings beside the
 *       library's, the user's effective permissions, and its levels left
 *
 * DEPENDS ON (read back, voiding what rests on them when they do not hold)
 *   access.item-acl.fixture-library        STATE 1: a document library this run created
 *   access.item-acl.fixture-library-groups STATE 1: the library reads unique and holds
 *       group A at Read and group B at the probe's custom level
 *   access.item-acl.fixture-level-permissions  STATE 1: the custom level reads back with
 *       the BasePermissions this probe sent
 *   access.item-acl.fixture-files          STATE 1: the C1, C6 and delete-trial text
 *       files and the C3 file, each inheriting
 *   access.item-acl.fixture-test-user      STATE 1: TEST_USER_LOGIN resolves to a site
 *       user that is not a site collection administrator
 *   access.item-acl.control-test-user-denied  STATE 1, CONTROL: before any grant, the
 *       test user's effective permissions on the C3 file carry no ViewListItems
 *   access.item-acl.fixture-state-one      STATE 2: the library, the level, the user and
 *       the user's binding on the C3 file that STATE 1 left, each read back as this
 *       probe's
 *
 * HOW TO RUN: on a site you own, F12 -> Console. Set TEST_USER_LOGIN to the
 * claims login of a licensed test account with no access to this site. For
 * C3's Excel half, set WORKBOOK_URL to the server-relative URL of a small
 * .xlsx on this site; left empty, C3's file is a text file. Paste; it prints
 * its plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again
 * with STATE = 1. Do the steps it prints as the test user, in a second browser
 * session. Then paste with STATE = 2. Copy each RESULTS block back verbatim,
 * with what you saw as the test user.
 *
 * WHEN FINISHED: paste with CLEANUP, CONFIRMED and ALLOW_WRITES true. It
 * recycles the library and deletes the three groups and the level, each only
 * when its description is this probe's. The test user stays in the site's
 * user list, where `ensureuser` put it.
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
  log('INFO', 'probe revision 2aabdd87. Quote this when reporting results.');

  // 1: build the fixture and ask C1 to C4. 2: ask C5 and C6 on what STATE 1 left.
  const STATE = 1;
  // The claims login of a licensed test account with no access to this site.
  const TEST_USER_LOGIN = 'CHANGE ME - the test user claims login';
  // Optional: a small .xlsx on this site for C3's Excel for the web half; empty uploads a text file.
  const WORKBOOK_URL = '';
  const PLACEHOLDER = /^CHANGE ME/;
  // Fifteen reads two seconds apart: the 30-second window a flow would allow itself.
  const SETTLE_READS = 15;
  const SETTLE_MS = 2000;

  // Fixed names, so STATE 2 and CLEANUP find what STATE 1 made; each is claimed by its description.
  const LIB = 'dbmlsp Probe ItemAccess';
  const OWNERSHIP = 'dbml-sharepoint item-access probe fixture. Safe to delete.';
  const GROUP = { a: 'dbmlsp ItemAccess A', b: 'dbmlsp ItemAccess B', c: 'dbmlsp ItemAccess C' };
  const LEVEL = 'dbmlsp ItemAccess No Delete';
  // `trial` takes C3's delete attempt, so a delete that succeeds cannot remove the C3 file STATE 2 needs.
  const NAMES = { plain: 'item-access-c1.txt', reset: 'item-access-c6.txt',
    book: WORKBOOK_URL ? 'item-access-c3.xlsx' : 'item-access-c3.txt', trial: 'item-access-c3-delete.txt' };
  // What STATE 1 and STATE 2 do to each file, by the key NAMES uses, so the plan names every file made.
  const FILE_PLAN = {
    plain: 'STATE 1 breaks its inheritance, copying the library\'s groups (C1, C2)',
    reset: 'STATE 2 breaks its inheritance, grants TEST_USER_LOGIN the custom level, then resets it (C6)',
    book: 'STATE 1 breaks its inheritance and grants TEST_USER_LOGIN the custom level (C3, C4); STATE 2 '
      + 'removes that grant (C5)',
    trial: 'STATE 1 breaks its inheritance and grants TEST_USER_LOGIN the custom level, for C3\'s delete trial',
  };
  // Add, edit and read items and versions, no delete: dbml_sharepoint.analysis.permissions computes
  // these halves for ViewListItems, AddListItems, EditListItems, OpenItems, ViewVersions,
  // ViewFormPages, Open, ViewPages, BrowseUserInfo, UseClientIntegration, UseRemoteAPIs,
  // CreateAlerts, ManagePersonalViews and EditMyUserInfo.
  const LEVEL_HIGH = '432';
  const LEVEL_LOW = '134419047';
  const VIEW_LIST_ITEMS = 1n;
  const DELETE_LIST_ITEMS = 8n;

  const Q = {
    library: 'a document library this run created',
    groups: 'the library reads unique and holds group A at Read and group B at the custom level',
    levelBits: 'the custom level reads back with the BasePermissions this probe sent',
    files: 'the C1, C6 and delete-trial text files and the C3 file, each read back by name and inheriting',
    user: 'TEST_USER_LOGIN resolves to a site user that is not a site collection administrator',
    denied: 'CONTROL: before any grant, the test user\'s effective permissions on the C3 file '
      + 'carry no ViewListItems',
    stateOne: 'the library, level, test user and the user\'s binding on the C3 file that STATE 1 '
      + 'left, each read back as this probe\'s',
    c1: 'Does breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true) on a file copy the '
      + 'library\'s group bindings, levels included?',
    c2: 'Does a group granted at the library after a file broke inheritance reach the file?',
    c3: 'Does a user bound to the custom no-delete level on one file edit it, see its versions and '
      + 'fail to delete it, while seeing nothing else?',
    c4: 'Can a user granted only on one file open the library\'s view and see that file?',
    c5: 'Does removeroleassignment on the file take, and what remains at the library and the web?',
    c6: 'Does resetroleinheritance on a broken file restore exactly the library\'s bindings and drop '
      + 'its direct user grant?',
  };
  expect('access.item-acl.fixture-library', Q.library);
  expect('access.item-acl.fixture-library-groups', Q.groups);
  expect('access.item-acl.fixture-level-permissions', Q.levelBits);
  expect('access.item-acl.fixture-files', Q.files);
  expect('access.item-acl.fixture-test-user', Q.user);
  expect('access.item-acl.control-test-user-denied', Q.denied);
  expect('access.item-acl.fixture-state-one', Q.stateOne);
  expect('access.item-acl.break-copies-parent-groups', Q.c1);
  expect('access.item-acl.parent-grant-after-break', Q.c2);
  expect('access.item-acl.custom-level-user-grant', Q.c3);
  expect('access.item-acl.item-only-user-views', Q.c4);
  expect('access.item-acl.user-binding-removal', Q.c5);
  expect('access.item-acl.reset-restores-parent', Q.c6);

  const USER_ROWS = ['access.item-acl.control-test-user-denied',
    'access.item-acl.custom-level-user-grant', 'access.item-acl.item-only-user-views'];
  const AFTER_FILES = ['access.item-acl.fixture-test-user', 'access.item-acl.break-copies-parent-groups',
    'access.item-acl.parent-grant-after-break', ...USER_ROWS];
  const AFTER_GROUPS = ['access.item-acl.fixture-level-permissions', 'access.item-acl.fixture-files',
    ...AFTER_FILES];
  const AFTER_LIBRARY = ['access.item-acl.fixture-library-groups', ...AFTER_GROUPS];
  const STATE_TWO_ROWS = ['access.item-acl.user-binding-removal', 'access.item-acl.reset-restores-parent'];

  // Every row still carrying the harness sentinel, stamped with the paste that answers it.
  const stampRemaining = (outcome, why) => {
    for (const row of RESULTS) {
      if (row.evidence === 'the run did not reach this question') record(row.id, row.question, outcome, why);
    }
  };

  if (STATE !== 1 && STATE !== 2) {
    log('FAIL', `STATE must be the number 1 or 2, not ${JSON.stringify(STATE)}. Nothing was sent.`);
    return;
  }
  if (!CONFIRMED) {
    log('INFO', `STATE 1 creates a library '${LIB}' on ${WEB} with unique permissions, the groups `
      + `${Object.values(GROUP).map((one) => `'${one}'`).join(', ')} and the custom level '${LEVEL}'. It grants `
      + 'the library group A at Read and group B at the custom level, and later group C at Read (C2). It adds '
      + 'TEST_USER_LOGIN to the site\'s user list.');
    log('INFO', `It adds ${Object.keys(NAMES).length} files to the library:`);
    for (const [key, name] of Object.entries(NAMES)) {
      const made = key === 'book' && WORKBOOK_URL ? `copied from ${WORKBOOK_URL}` : 'uploaded as text';
      log('INFO', `  ${name} (${made}): ${FILE_PLAN[key]}.`);
    }
    log('INFO', 'CLEANUP removes what STATE 1 made.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  const sleep = (ms) => new Promise((resolve) => { setTimeout(resolve, ms); });
  // OData string literal: quotes doubled, then percent-encoded, so a claims login's '#' and '|' survive.
  const odataLiteral = (value) => encodeURIComponent(String(value).replace(/'/g, "''"));
  // By title until the library is claimed or read back as this probe's, then by its Id.
  let lib = `web/lists/getbytitle('${pathLiteral(LIB)}')`;
  let digest = null;
  const write = async (path, body = {}, extra = {}) => {
    digest = digest || await getDigest();
    return spWrite(path, body, digest, extra);
  };

  // Every binding a scope holds, with its level's name and Id, paged to the end; null with why when unread.
  const bindingsOf = async (scope) => {
    const rows = [];
    let path = `${scope}/roleassignments?$expand=Member,RoleDefinitionBindings`
      + '&$select=PrincipalId,Member/Title,Member/PrincipalType,RoleDefinitionBindings/Id,'
      + 'RoleDefinitionBindings/Name';
    while (path) {
      const read = await sendRaw(path);
      const head = readHead(read);
      if (head) return { rows: null, why: scrub(head.why) };
      const { rows: page, shape } = entriesOf(read.parsed);
      if (page === null) return { rows: null, why: `HTTP ${read.status} ${shape}` };
      for (const row of page) {
        // An assignment without its level bindings, or a level without an Id, is no reading of the scope.
        const levels = row.RoleDefinitionBindings;
        if (!Array.isArray(levels) || !levels.every((one) => one && Number.isInteger(one.Id))) {
          return { rows: null, why: `HTTP ${read.status} carried an assignment without RoleDefinitionBindings Ids` };
        }
        for (const level of levels) {
          rows.push({ principal: row.PrincipalId, level: level.Name, levelId: level.Id });
        }
      }
      const next = continuationOf(read.parsed);
      path = next ? next.slice(next.indexOf('/_api/') + 6) : null;
    }
    return { rows, why: null };
  };
  // Bindings compared by principal and level Id, since two levels may share a name.
  const keysOf = (rows) => rows.map((r) => `${r.principal}:${r.levelId}`).sort();
  const textOf = (r) => `${r.principal}:${quote(String(r.level))}`;
  // Whether `rows` bind `principal` to the level with Id `levelId`; an Id that is not an integer matches nothing.
  const holds = (rows, principal, levelId) => rows !== null && Number.isInteger(levelId)
    && rows.some((r) => r.principal === principal && r.levelId === levelId);
  // Bindings for the evidence as `principal:level name`, each name from an answer passed through quote().
  const listed = (rows) => rows.map(textOf).sort().join(', ') || 'none';
  const shown = (bound) => (bound.rows === null ? `unread (${bound.why})` : listed(bound.rows));
  // Whether two binding sets hold the same principal and level Id pairs.
  const sameBindings = (a, b) => a !== null && b !== null
    && JSON.stringify(keysOf(a)) === JSON.stringify(keysOf(b));
  const uniqueOf = async (scope) => {
    const read = await sendRaw(`${scope}?$select=HasUniqueRoleAssignments`);
    const head = readHead(read);
    const body = head ? null : recordBody(read);
    return body ? body.HasUniqueRoleAssignments : `unread (${head ? scrub(head.why) : 'no JSON object'})`;
  };
  // Re-reads until `done` holds or the window ends, and says how many reads and how long it took.
  const settle = async (read, done) => {
    const started = Date.now();
    let last = null;
    for (let n = 1; n <= SETTLE_READS; n += 1) {
      if (n > 1) await sleep(SETTLE_MS);
      last = await read();
      if (done(last)) return { last, held: true, reads: n, ms: Date.now() - started };
    }
    return { last, held: false, reads: SETTLE_READS, ms: Date.now() - started };
  };
  const effectiveOf = async (scope, login) => {
    const read = await sendRaw(`${scope}/getusereffectivepermissions(@user)?@user='${odataLiteral(login)}'`);
    const head = readHead(read);
    const body = head ? null : recordBody(read);
    const node = body && (body.GetUserEffectivePermissions || body);
    // Each half must be a decimal integer, since BigInt reads an empty string as 0, which would read as denied.
    const decimal = (half) => (typeof half === 'string' || typeof half === 'number') && /^\d+$/.test(String(half));
    if (!node || !decimal(node.High) || !decimal(node.Low)) {
      return { mask: null, text: `unread (${head ? scrub(head.why)
        : `HTTP ${read.status} with High and Low that are not decimal integers`})` };
    }
    const mask = (BigInt(String(node.High)) << 32n) | BigInt(String(node.Low));
    return { mask, text: `High=${node.High} Low=${node.Low}` };
  };
  // A principal's levels on a scope as names; 'none' when SharePoint answers that it holds none there.
  const levelsOf = async (scope, principal) => {
    const read = await sendRaw(`${scope}/roleassignments/getbyprincipalid(${principal})`
      + '/roledefinitionbindings?$select=Name');
    if (read.status === 404) return 'none';
    const head = readHead(read);
    if (head) return `unread (${scrub(head.why)})`;
    const { rows, shape } = entriesOf(read.parsed);
    if (rows === null) return `unread (HTTP ${read.status} ${shape})`;
    return rows.map((r) => quote(String(r.Name))).join(', ') || 'none';
  };
  // A group or level by name: absent, mine, foreign, duplicate or unheard, with its Id only when mine.
  const lookUp = async (collection, name) => {
    const judge = (body) => (body.Description !== OWNERSHIP
      ? { state: 'foreign', id: null, why: 'not this probe\'s (its description differs)' }
      : Number.isInteger(body.Id) ? { state: 'mine', id: body.Id, why: null }
        : { state: 'unheard', id: null, why: 'no Id' });
    if (collection === 'sitegroups') {
      const read = await sendRaw(`web/sitegroups/getbyname('${pathLiteral(name)}')?$select=Id,Description`);
      if (read.status === 404) return { state: 'absent', id: null, why: 'absent' };
      const head = readHead(read);
      const body = head ? null : recordBody(read);
      return body ? judge(body) : { state: 'unheard', id: null, why: head ? scrub(head.why) : 'no JSON object' };
    }
    // A level by $filter, as the deployer reads one: getbyname answers 500 for an absent level, not 404.
    const read = await sendRaw('web/roledefinitions?$select=Id,Description'
      + `&$filter=Name eq '${odataLiteral(name)}'`);
    const head = readHead(read);
    const { rows, shape } = head ? { rows: null, shape: null } : entriesOf(read.parsed);
    if (rows === null) return { state: 'unheard', id: null, why: head ? scrub(head.why) : `HTTP ${read.status} ${shape}` };
    if (rows.length === 0) return { state: 'absent', id: null, why: 'absent' };
    if (rows.length > 1) return { state: 'duplicate', id: null, why: `held ${rows.length} times` };
    return judge(rows[0]);
  };
  const ownedByName = async (collection, name) => {
    const found = await lookUp(collection, name);
    return { id: found.id, why: found.why };
  };
  const resolveUser = async () => {
    if (PLACEHOLDER.test(TEST_USER_LOGIN)) return null;
    knowIdentity(TEST_USER_LOGIN, '<test user>');
    knowIdentity(odataLiteral(TEST_USER_LOGIN), '<test user>');
    const ensured = await write('web/ensureuser', { logonName: TEST_USER_LOGIN });
    const body = ensured.ok ? recordBody({ parsed: ensured.body }) : null;
    if (!body) return null;
    knowIdentity(body.Title, '<test user name>', true);
    knowIdentity(body.Email, '<test user>');
    if (typeof body.LoginName === 'string') {
      knowIdentity(body.LoginName, '<test user>');
      knowIdentity(odataLiteral(body.LoginName), '<test user>');
    }
    return { id: body.Id, login: body.LoginName || TEST_USER_LOGIN, admin: body.IsSiteAdmin };
  };
  const filesOf = async () => {
    const read = await sendRaw(`${lib}/items?$select=Id,FileLeafRef,HasUniqueRoleAssignments&$top=50`);
    const rows = readHead(read) ? [] : entriesOf(read.parsed).rows || [];
    const found = {};
    for (const [key, name] of Object.entries(NAMES)) {
      const row = rows.find((r) => r.FileLeafRef === name);
      if (row) found[key] = { id: row.Id, unique: row.HasUniqueRoleAssignments };
    }
    return found;
  };

  // ---- CLEANUP: remove what STATE 1 made, each only when its description is this probe's ----
  // Returns early, deleting nothing more, whenever what a later step rests on did not hold.
  const cleanUp = async () => {
    const held = await sendRaw(`${lib}?$select=Id,Description`);
    const head = held.status === 404 ? null : readHead(held);
    const body = held.status === 404 || head ? null : recordBody(held);
    // An unread ownership says nothing about the library, so nothing is deleted on it.
    if (held.status !== 404 && !body) {
      log('FAIL', `CLEANUP stopped: the library's ownership read ${head ? scrub(head.why) : 'carried no JSON object'}`
        + ', so nothing was deleted. Paste again with CLEANUP.');
      return;
    }
    if (body && body.Description === OWNERSHIP) {
      // The groups and level stay while the library stands, so its permissions are never dismantled under it.
      if (!await resetList(LIB, guidOf(body.Id))) {
        log('FAIL', 'CLEANUP stopped: the library was not recycled, so its groups and level were kept. '
          + 'Paste again with CLEANUP.');
        return;
      }
    } else log('INFO', `CLEANUP: no library '${LIB}' of this probe's to remove.`);
    // Logs OK only once the name reads back absent.
    const readBackGone = async (what, collection, name, sent) => {
      const after = await lookUp(collection, name);
      log(after.state === 'absent' ? 'OK' : 'FAIL', after.state === 'absent'
        ? `CLEANUP: ${what} '${name}' ${sent} and read back absent.`
        : `CLEANUP: ${what} '${name}' ${sent}, but it reads back ${after.state} (${after.why}).`);
    };
    for (const name of Object.values(GROUP)) {
      const group = await ownedByName('sitegroups', name);
      if (group.id === null) {
        log('INFO', `CLEANUP: group '${name}' left: ${group.why}.`);
        continue;
      }
      const gone = await write(`web/sitegroups/removebyid(${group.id})`);
      if (gone.ok) await readBackGone('group', 'sitegroups', name, 'removed');
      else log('FAIL', `CLEANUP: group '${name}' not removed: HTTP ${gone.status}`);
    }
    const level = await ownedByName('roledefinitions', LEVEL);
    if (level.id === null) {
      log('INFO', `CLEANUP: level '${LEVEL}' left: ${level.why}.`);
    } else {
      const gone = await write(`web/roledefinitions(${level.id})`, {},
        { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
      if (gone.ok) await readBackGone('level', 'roledefinitions', LEVEL, 'deleted');
      else log('FAIL', `CLEANUP: level '${LEVEL}' not deleted: HTTP ${gone.status}`);
    }
  };
  if (CLEANUP) {
    try {
      await cleanUp();
    } catch (err) {
      log('FAIL', `CLEANUP aborted: ${scrub(String((err && err.message) || err)).slice(0, 240)}. `
        + 'Some of what STATE 1 made may remain; paste again with CLEANUP.');
    } finally {
      stampRemaining('NOT REACHED', 'a CLEANUP paste asks nothing');
      report();
    }
    return;
  }

  try {
    await learnIdentity();
    if (STATE === 1) {
      // Each fixed name is read before anything is made, since SharePoint accepts a duplicate level name.
      const found = { mine: [], other: [], unheard: [] };
      for (const [collection, name] of [['roledefinitions', LEVEL],
        ...Object.values(GROUP).map((one) => ['sitegroups', one])]) {
        const one = await lookUp(collection, name);
        if (one.state === 'mine') found.mine.push(`'${name}'`);
        else if (one.state === 'foreign' || one.state === 'duplicate') found.other.push(`'${name}' (${one.why})`);
        else if (one.state === 'unheard') found.unheard.push(`'${name}' (${one.why})`);
      }
      if (found.mine.length || found.other.length || found.unheard.length) {
        const why = [
          found.mine.length ? `left by an earlier run of this probe: ${found.mine.join(', ')}; run CLEANUP `
            + 'first, then STATE 1 again' : '',
          found.other.length ? `held by something other than this probe, which CLEANUP leaves by design: `
            + `${found.other.join(', ')}; remove or rename it by hand, or run this probe on another site` : '',
          found.unheard.length ? `not read as absent: ${found.unheard.join(', ')}; a re-run can ask it` : '',
        ].filter(Boolean).join('; ');
        const held = found.mine.length > 0 || found.other.length > 0;
        record('access.item-acl.fixture-library-groups', Q.groups, held ? 'FAIL' : 'NOT ESTABLISHED',
          `nothing was created: ${why}`);
        record('access.item-acl.fixture-library', Q.library, 'NOT ESTABLISHED',
          'not created: the probe\'s fixed group and level names were not all free');
        voidRows(AFTER_GROUPS, 'the library\'s groups and level were not made');
        return;
      }
      const library = await claimScratchList({ id: 'access.item-acl.fixture-library', question: Q.library,
        title: LIB, description: OWNERSHIP, dependents: AFTER_LIBRARY, baseTemplate: 101 });
      if (!library.held) return;
      // Every later request goes to the list this run proved its own, by Id, so a rebound title cannot redirect it.
      lib = library.path;

      // ---- the library: unique, with group A at Read and group B at the custom level ----
      beginFixture();
      const level = createdId(await write('web/roledefinitions', {
        __metadata: { type: 'SP.RoleDefinition' }, Name: LEVEL, Description: OWNERSHIP, Order: 100,
        BasePermissions: { __metadata: { type: 'SP.BasePermissions' }, High: LEVEL_HIGH, Low: LEVEL_LOW },
      }, { ...VERBOSE_WRITE }));
      const groups = {};
      for (const key of ['a', 'b', 'c']) {
        groups[key] = createdId(await write('web/sitegroups', { __metadata: { type: 'SP.Group' },
          Title: GROUP[key], Description: OWNERSHIP }, { ...VERBOSE_WRITE }));
      }
      const readLevel = await sendRaw("web/roledefinitions/getbyname('Read')?$select=Id");
      const readId = readHead(readLevel) ? null : (recordBody(readLevel) || {}).Id;
      const broke = await write(`${lib}/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)`);
      log('INFO', `library break: HTTP ${broke.status}`);
      if (groups.a !== null && readId) {
        await write(`${lib}/roleassignments/addroleassignment(principalid=${groups.a},roledefid=${readId})`);
      }
      if (groups.b !== null && level !== null) {
        await write(`${lib}/roleassignments/addroleassignment(principalid=${groups.b},roledefid=${level})`);
      }
      let libraryRows = null;
      if (!await settleFixture('access.item-acl.fixture-library-groups', async () => {
        // CLEANUP removes only what carries this probe's description, so each create must read back with it.
        const unowned = [];
        for (const [collection, name, id] of [['roledefinitions', LEVEL, level],
          ...['a', 'b', 'c'].map((key) => ['sitegroups', GROUP[key], groups[key]])]) {
          const back = await lookUp(collection, name);
          if (back.state !== 'mine' || back.id !== id) unowned.push(`'${name}' (${back.why || 'another Id'})`);
        }
        const got = await settle(async () => ({ unique: await uniqueOf(lib), bound: await bindingsOf(lib) }),
          (r) => r.unique === true && holds(r.bound.rows, groups.a, readId)
            && holds(r.bound.rows, groups.b, level));
        libraryRows = got.last.bound.rows;
        return { ok: true, status: 200, body: { Unique: got.last.unique, Held: got.held,
          Bindings: shown(got.last.bound), Unowned: unowned.join(', ') || 'none' } };
      }, { Unique: true, Held: true, Bindings: (v) => typeof v === 'string', Unowned: 'none' },
      AFTER_GROUPS)) return;

      // ---- the custom level: read back with the bits it was sent, which C3 and C4 rest on ----
      beginFixture();
      const levelHeld = await settleFixture('access.item-acl.fixture-level-permissions', async () => {
        const read = await sendRaw(`web/roledefinitions(${level})?$select=BasePermissions`);
        const head = readHead(read);
        const bits = head ? null : (recordBody(read) || {}).BasePermissions;
        return { ok: Boolean(bits), status: read.status,
          body: bits ? { High: String(bits.High), Low: String(bits.Low) } : null };
      }, { High: LEVEL_HIGH, Low: LEVEL_LOW }, USER_ROWS.slice(1));

      // ---- the files: two text files and the C3 file, each inheriting ----
      beginFixture();
      const rootRead = await sendRaw(`${lib}/RootFolder?$select=ServerRelativeUrl`);
      const root = readHead(rootRead) ? null : (recordBody(rootRead) || {}).ServerRelativeUrl;
      if (root) {
        const folder = `web/GetFolderByServerRelativeUrl('${pathLiteral(root)}')/Files`;
        for (const key of WORKBOOK_URL ? ['plain', 'reset', 'trial'] : ['plain', 'reset', 'book', 'trial']) {
          await write(`${folder}/add(url='${NAMES[key]}',overwrite=true)`, 'dbmlsp item access probe file');
        }
        if (WORKBOOK_URL) {
          await write(`web/GetFileByServerRelativeUrl('${pathLiteral(WORKBOOK_URL)}')/copyto(strnewurl=`
            + `'${pathLiteral(`${root}/${NAMES.book}`)}',boverwrite=true)`);
        }
      }
      let files = {};
      if (!await settleFixture('access.item-acl.fixture-files', async () => {
        files = await filesOf();
        const inheriting = (key) => (files[key] ? files[key].unique === false : false);
        return { ok: true, status: 200, body: { Plain: inheriting('plain'), Reset: inheriting('reset'),
          Book: inheriting('book'), Trial: inheriting('trial') } };
      }, { Plain: true, Reset: true, Book: true, Trial: true }, AFTER_FILES)) return;
      const fileOf = (key) => `${lib}/items(${files[key].id})`;

      // ---- C1: the break copies the library's groups ----
      const c1Broke = await write(`${fileOf('plain')}/breakroleinheritance(copyRoleAssignments=true,`
        + 'clearSubscopes=true)');
      const libraryHeld = libraryRows.filter((r) => r.level !== 'Limited Access');
      // The library's bindings the file does not hold, by level Id, or null while the file's are unread.
      const missingOf = (bound) => (bound.rows === null ? null : libraryHeld.filter((r) => !keysOf(bound.rows)
        .includes(keysOf([r])[0])));
      // The window waits for the flag and the copied bindings together, so their order is never a finding.
      const c1 = await settle(async () => ({ unique: await uniqueOf(fileOf('plain')),
        bound: await bindingsOf(fileOf('plain')) }),
      (r) => r.unique === true && missingOf(r.bound) !== null && missingOf(r.bound).length === 0);
      const missing = missingOf(c1.last.bound);
      record('access.item-acl.break-copies-parent-groups', Q.c1,
        typeof c1.last.unique !== 'boolean' ? 'NOT ESTABLISHED'
          : c1.last.unique !== true ? 'STILL INHERITING' : missing === null ? 'NOT ESTABLISHED'
          : missing.length ? 'NOT ALL COPIED' : 'COPIED',
        `the break answered HTTP ${c1Broke.status}; after ${c1.reads} read(s), ${c1.ms} ms `
        + `HasUniqueRoleAssignments read ${c1.last.unique}; the library holds ${listed(libraryHeld)}; the file `
        + `holds ${shown(c1.last.bound)}`
        + `${missing && missing.length ? `; not on the file: ${listed(missing)}` : ''}`);

      // ---- C2: a group granted at the library after the break ----
      if (c1.last.unique !== true) {
        voidRows(['access.item-acl.parent-grant-after-break'], 'C1\'s file never read as broken');
      } else if (groups.c === null || !readId) {
        record('access.item-acl.parent-grant-after-break', Q.c2, 'NOT ESTABLISHED',
          'group C or the Read level was not available, so nothing was granted');
      } else {
        // Group C must read absent from both scopes first, or a binding already there would read as reaching the file.
        const prior = { library: await bindingsOf(lib), file: await bindingsOf(fileOf('plain')) };
        const boundC = (bound) => (bound.rows === null ? null : bound.rows.some((r) => r.principal === groups.c));
        const found = [boundC(prior.library), boundC(prior.file)];
        if (found.includes(true) || found.includes(null)) {
          record('access.item-acl.parent-grant-after-break', Q.c2, 'NOT ESTABLISHED',
            `${found.includes(true) ? 'group C was already bound before the grant'
              : 'a read before the grant was unread'}, so nothing was granted; the library holds `
            + `${shown(prior.library)}; the file holds ${shown(prior.file)}`);
        } else {
          const added = await write(`${lib}/roleassignments/addroleassignment(principalid=${groups.c},`
            + `roledefid=${readId})`);
          // One window for both scopes: the library's grant is the prerequisite, the file's bindings the observation.
          let onLibrary = 0;
          const c2 = await settle(async () => {
            const both = { library: await bindingsOf(lib), file: await bindingsOf(fileOf('plain')) };
            if (!onLibrary && holds(both.library.rows, groups.c, readId)) onLibrary = 1;
            return both;
          }, (r) => onLibrary === 1 && holds(r.file.rows, groups.c, readId));
          record('access.item-acl.parent-grant-after-break', Q.c2,
            !onLibrary || c2.last.file.rows === null ? 'NOT ESTABLISHED'
              : c2.held ? 'REACHED THE FILE' : 'NOT ON THE FILE',
            `group C read absent from the library and the file before the grant; the library grant answered `
            + `HTTP ${added.status}; the library ${onLibrary ? 'read it' : 'never read it'} within the window; `
            + `after ${c2.reads} read(s), ${c2.ms} ms the file holds ${shown(c2.last.file)}`);
        }
      }

      // ---- the test user: resolved, not an administrator, and denied before any grant ----
      beginFixture();
      const user = await resolveUser();
      if (!await settleFixture('access.item-acl.fixture-test-user', async () => ({ ok: true, status: 200,
        body: { Resolved: user !== null && Number.isInteger(user.id),
          SiteAdmin: user === null ? 'TEST_USER_LOGIN is unset or unresolved' : user.admin } }),
      { Resolved: true, SiteAdmin: false }, USER_ROWS)) return;
      const before = await effectiveOf(fileOf('book'), user.login);
      const denied = before.mask !== null && (before.mask & VIEW_LIST_ITEMS) === 0n;
      record('access.item-acl.control-test-user-denied', Q.denied,
        before.mask === null ? 'NOT ESTABLISHED' : denied ? 'PASS' : 'FAIL',
        `before any grant, on the C3 file: ${before.text}`);
      if (!denied) {
        voidRows(USER_ROWS.slice(1), 'the test user was not shown denied before the grant');
        stampRemaining('NOT REACHED', 'STATE 2 asks this, on what STATE 1 leaves');
        return;
      }

      if (!levelHeld) {
        stampRemaining('NOT REACHED', 'STATE 2 asks this, on what STATE 1 leaves');
        return;
      }

      // ---- C3 and C4: the user bound to the custom level on the C3 file and the delete-trial file ----
      const bookBroke = await write(`${fileOf('book')}/breakroleinheritance(copyRoleAssignments=true,`
        + 'clearSubscopes=true)');
      const granted = await write(`${fileOf('book')}/roleassignments/addroleassignment(`
        + `principalid=${user.id},roledefid=${level})`);
      const trialBroke = await write(`${fileOf('trial')}/breakroleinheritance(copyRoleAssignments=true,`
        + 'clearSubscopes=true)');
      const trialGranted = await write(`${fileOf('trial')}/roleassignments/addroleassignment(`
        + `principalid=${user.id},roledefid=${level})`);
      // Each grant counts only on a file that reads unique, since the manual half tests a direct file grant.
      const c3 = await settle(async () => ({ book: await bindingsOf(fileOf('book')),
        trial: await bindingsOf(fileOf('trial')), bookUnique: await uniqueOf(fileOf('book')),
        trialUnique: await uniqueOf(fileOf('trial')) }),
      (r) => r.bookUnique === true && r.trialUnique === true
        && holds(r.book.rows, user.id, level) && holds(r.trial.rows, user.id, level));
      const grants = `break HTTP ${bookBroke.status}, grant HTTP ${granted.status} on ${NAMES.book}; break `
        + `HTTP ${trialBroke.status}, grant HTTP ${trialGranted.status} on ${NAMES.trial}; after ${c3.reads} `
        + `read(s), ${c3.ms} ms ${NAMES.book} holds ${shown(c3.last.book)} and ${NAMES.trial} holds `
        + `${shown(c3.last.trial)}; HasUniqueRoleAssignments read ${c3.last.bookUnique} and ${c3.last.trialUnique}`;
      // The manual half asks what the grant allows, so it is not asked until both grants read back.
      if (!c3.held) {
        for (const [id, question] of [['access.item-acl.custom-level-user-grant', Q.c3],
          ['access.item-acl.item-only-user-views', Q.c4]]) {
          record(id, question, 'NOT ESTABLISHED', `the user's grants never both read back: ${grants}`);
        }
        stampRemaining('NOT REACHED', 'STATE 2 asks this, on what STATE 1 leaves');
        return;
      }
      const onBook = await effectiveOf(fileOf('book'), user.login);
      const onLib = await effectiveOf(lib, user.login);
      const onWeb = await effectiveOf('web', user.login);
      const canDelete = onBook.mask === null ? 'unread'
        : String((onBook.mask & DELETE_LIST_ITEMS) !== 0n);
      record('access.item-acl.custom-level-user-grant', Q.c3, 'MANUAL',
        `${grants}; effective on ${NAMES.book} ${onBook.text} (DeleteListItems ${canDelete}), on the `
        + `library ${onLib.text}, on the web ${onWeb.text}; the user's levels at the library `
        + `${await levelsOf(lib, user.id)}, at the web ${await levelsOf('web', user.id)}. By hand, as the `
        + `test user: on ${NAMES.book} an edit saved and the version history opened; on ${NAMES.trial} a `
        + 'delete tried.');
      record('access.item-acl.item-only-user-views', Q.c4, 'MANUAL',
        `effective on the library ${onLib.text}. By hand, as the test user: open the library's default `
        + `view and say whether ${NAMES.book} is listed.`);
      stampRemaining('NOT REACHED', 'STATE 2 asks this, on what STATE 1 leaves');

      console.log('\n==================== MANUAL HALF (C3, C4) ====================');
      console.log('Sign in as the test user in a second browser session, then:');
      console.log(`  1. Open ${new URL(WEB).origin}${root}/Forms/AllItems.aspx. C4: is ${NAMES.book} listed?`);
      console.log(`  2. Open ${NAMES.book} in the browser, change it, close it, reopen it. C3: kept?`);
      console.log('  3. Open its version history. C3: does it open and list your save?');
      console.log(`  4. Try to delete ${NAMES.trial}, not ${NAMES.book}. C3: refused, and with what message?`);
      console.log(`  5. Try to open ${NAMES.plain}. C3: denied?`);
      console.log('Then paste this probe with STATE = 2. Write what you saw beside the RESULTS block.');
      console.log('==============================================================\n');
      return;
    }

    // ---- STATE 2: what STATE 1 left, read back as this probe's ----
    beginFixture();
    const owned = await sendRaw(`${lib}?$select=Id,Description`);
    const ownedBody = readHead(owned) ? null : recordBody(owned);
    const ownedId = ownedBody ? guidOf(ownedBody.Id) : null;
    const mine = Boolean(ownedBody && ownedBody.Description === OWNERSHIP && ownedId);
    if (mine) lib = `web/lists(guid'${ownedId}')`;
    const level = await ownedByName('roledefinitions', LEVEL);
    const user = mine ? await resolveUser() : null;
    const files = user ? await filesOf() : {};
    const bound = files.book ? await bindingsOf(`${lib}/items(${files.book.id})`)
      : { rows: null, why: 'no C3 file' };
    const granted = user !== null && holds(bound.rows, user.id, level.id);
    if (!await settleFixture('access.item-acl.fixture-state-one', async () => ({ ok: true, status: 200,
      body: { Library: mine, Level: level.id !== null, User: user !== null && user.admin === false,
        Files: Boolean(files.book && files.reset), Granted: granted } }),
    { Library: true, Level: true, User: true, Files: true, Granted: true }, STATE_TWO_ROWS)) {
      stampRemaining('NOT REACHED', 'STATE 1 asks this');
      return;
    }
    const fileOf = (key) => `${lib}/items(${files[key].id})`;

    // ---- C5: the user's binding removed ----
    const removed = await write(`${fileOf('book')}/roleassignments/removeroleassignment(`
      + `principalid=${user.id},roledefid=${level.id})`);
    const c5 = await settle(() => bindingsOf(fileOf('book')),
      (r) => r.rows !== null && !holds(r.rows, user.id, level.id));
    const afterBook = await effectiveOf(fileOf('book'), user.login);
    record('access.item-acl.user-binding-removal', Q.c5,
      c5.last.rows === null ? 'NOT ESTABLISHED' : c5.held ? 'REMOVED' : 'STILL BOUND',
      `removeroleassignment answered HTTP ${removed.status}; after ${c5.reads} read(s), ${c5.ms} ms the `
      + `file holds ${shown(c5.last)}; effective on the file ${afterBook.text}; the user's levels at the `
      + `library ${await levelsOf(lib, user.id)}, at the web ${await levelsOf('web', user.id)}`);

    // ---- C6: a file holding a user grant and copied groups, reset ----
    await write(`${fileOf('reset')}/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)`);
    await write(`${fileOf('reset')}/roleassignments/addroleassignment(principalid=${user.id},`
      + `roledefid=${level.id})`);
    const c6Before = await settle(() => bindingsOf(fileOf('reset')), (r) => holds(r.rows, user.id, level.id));
    if (!c6Before.held) {
      record('access.item-acl.reset-restores-parent', Q.c6, 'NOT ESTABLISHED',
        `the user's grant on the C6 file never read back (${shown(c6Before.last)}), so no reset was sent`);
    } else {
      const reset = await write(`${fileOf('reset')}/resetroleinheritance`);
      // The flag, the file and the library are read together, so the file is compared with the library as it is now.
      const c6 = await settle(async () => ({ unique: await uniqueOf(fileOf('reset')),
        bound: await bindingsOf(fileOf('reset')), library: await bindingsOf(lib) }),
      (r) => r.unique === false && sameBindings(r.bound.rows, r.library.rows));
      const fileNow = c6.last.bound;
      const libraryNow = c6.last.library;
      const afterReset = await effectiveOf(fileOf('reset'), user.login);
      const unread = libraryNow.rows === null || fileNow.rows === null;
      // An unread value is no answer, so the row rests on nothing and is not established.
      record('access.item-acl.reset-restores-parent', Q.c6,
        typeof c6.last.unique !== 'boolean' ? 'NOT ESTABLISHED' : c6.last.unique !== false ? 'STILL UNIQUE'
          : unread ? 'NOT ESTABLISHED'
            : sameBindings(fileNow.rows, libraryNow.rows) ? 'MATCHES THE LIBRARY' : 'DIFFERS FROM THE LIBRARY',
        `the reset answered HTTP ${reset.status}; after ${c6.reads} read(s), ${c6.ms} ms `
        + `HasUniqueRoleAssignments read ${c6.last.unique}; the library holds ${shown(libraryNow)}; the file `
        + `holds ${shown(fileNow)}; effective on the file ${afterReset.text}; the user's levels at the library `
        + `${await levelsOf(lib, user.id)}`);
    }
    stampRemaining('NOT REACHED', 'STATE 1 asks this');
  } catch (err) {
    log('FAIL', `probe aborted: ${scrub(String((err && err.message) || err)).slice(0, 240)}. `
      + 'The unasked rows stay open; paste with CLEANUP to remove what was made.');
  } finally {
    report();
  }
})();
