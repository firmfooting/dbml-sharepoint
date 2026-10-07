
/** ---- dbml-sharepoint PROBE: WHAT A MOVE INSIDE ONE LIBRARY KEEPS ----
 *
 * REVISION: 2888798f
 *
 * QUESTION: when File.MoveToUsingPath moves a file from a folder to the root
 * of the same document library, does the item keep its Id, its versions, its
 * column values, Created and Author, its unique permissions and a sharing
 * link; does the move add a version; what happens to Modified and Editor?
 * Does Folder.Recycle on the emptied folder put it in the recycle bin, from
 * where it can be restored?
 *
 * WHY: a library that holds its files in folders is flattened by moving each
 * file to its root. Learn documents MoveToUsingPath's signature (newPath,
 * moveOperations; MoveOperations.None is 0), that the ResourcePath form takes
 * % and # in names, and that a move BETWEEN libraries keeps custom metadata.
 * It does not say what a move inside one library keeps. Learn documents
 * Folder.Recycle; it does not say a recycled folder can be restored. The link
 * is created with linkKind 2, OrganizationView in Learn's SharingLinkKind.
 *
 * FOUR LEGS, each pasted by the account named, then a cleanup:
 *   STATE 1  the owner: the library, its columns, the folder, the file with
 *            two versions and five values, a Read grant to TEST_USER_LOGIN on
 *            the file alone, and an organisation sharing link
 *   STATE 2  TEST_USER_LOGIN: one edit of MoveChoice, the third version
 *   STATE 3  MOVER_LOGIN: reads the file, moves it to the root, reads it by Id
 *   STATE 4  the owner: the grant and link after the move, then the folder
 *   CLEANUP  the owner, CLEANUP true: recycles the library
 * Both logins must be site Members. The three accounts must differ. Every leg
 * after STATE 1 writes only to a library carrying this probe's Description.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   library.file.fixture-move-library      STATE 1: a document library with
 *       versioning on and this probe's Description, where none stood before
 *   library.file.fixture-move-folder       STATE 1: a folder whose name holds & and ,
 *   library.file.fixture-move-values       STATE 1: the file, its values read back
 *   library.file.fixture-move-unique-grant STATE 1: the file's own Read grant to the
 *       test user, read back with HasUniqueRoleAssignments true
 *   library.file.fixture-move-sharing-link STATE 1: a link with a URL on the file
 *   library.file.fixture-move-before       STATE 3: three versions, Author the owner,
 *       Editor the editing account, and the mover a third account
 *   library.file.fixture-move-answered     STATE 3: the move request answered 2xx
 *   library.folder.fixture-recycle-empty   STATE 4: the folder reads empty
 *
 * OBSERVES (recorded as found, never compared with an expected value)
 *   library.file.move-keeps-id-and-versions    the Id and version labels before and after
 *   library.file.move-keeps-column-values      each of the five values before and after
 *   library.file.move-system-fields            Created, Author, Modified, Editor before and after
 *   library.file.move-adds-version             the version count before and after
 *   library.file.move-keeps-unique-permissions the file's bindings and links after the move
 *   library.folder.recycle-empty-restorable    the recycle answer, the bin entry, the restore
 *
 * HOW TO READ IT: a head names what was found (ID AND VERSIONS KEPT, ID
 * CHANGED, VERSIONS CHANGED, EVERY VALUE KEPT, VALUES CHANGED, VERSION ADDED,
 * NO VERSION ADDED, GRANT AND LINK PRESENT, GRANT LOST, LINK LOST, GRANT AND
 * LINK LOST, RECYCLED AND RESTORED, RECYCLED, NOT RESTORED, NOT IN THE BIN).
 * A review decides what a head establishes. Accounts are written as the
 * owner, the editing account and the moving account.
 *
 * HOW TO RUN: F12 -> Console on a site you own; paste; Enter; it prints its
 * plan and stops. Set CONFIRMED, ALLOW_WRITES, STATE and both logins.
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
  log('INFO', 'probe revision 2888798f. Quote this when reporting results.');

  const STATE = 1;
  const TEST_USER_LOGIN = 'CHANGE ME - the editing account claims login';
  const MOVER_LOGIN = 'CHANGE ME - the moving account claims login';
  const PLACEHOLDER = /^CHANGE ME/;
  const LIBRARY = 'dbmlsp Probe FileMove';
  // Ownership is the Description: a same-title library this probe did not make is never written to.
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint file move probe. Safe to delete.';
  const FOLDER = 'Move & Folder, A';
  const FILE = 'dbmlsp move probe.txt';
  const VALUES = { MoveChoice: 'Q1', MoveDate: '2026-01-15T00:00:00Z', MoveFlag: true,
    MoveLink: { Url: 'https://example.org/move-probe', Description: 'move probe' } };
  const LIST = `web/lists/getbytitle('${LIBRARY}')`;
  // Apostrophes doubled for OData, then percent-encoded so & , and a claims login's # reach the server whole.
  const lit = (text) => encodeURIComponent(String(text).replace(/'/g, "''")).replace(/%2F/g, '/');
  const folderAt = (path) => `web/GetFolderByServerRelativePath(decodedurl='${lit(path)}')`;
  const fileAt = (path) => `web/GetFileByServerRelativePath(decodedurl='${lit(path)}')`;
  knowIdentity(TEST_USER_LOGIN, '<editing account>');
  knowIdentity(MOVER_LOGIN, '<moving account>');

  const LIBRARY_ROW = 'library.file.fixture-move-library';
  const FOLDER_ROW = 'library.file.fixture-move-folder';
  const VALUES_ROW = 'library.file.fixture-move-values';
  const GRANT_ROW = 'library.file.fixture-move-unique-grant';
  const LINK_ROW = 'library.file.fixture-move-sharing-link';
  const BEFORE_ROW = 'library.file.fixture-move-before';
  const ANSWERED_ROW = 'library.file.fixture-move-answered';
  const EMPTY_ROW = 'library.folder.fixture-recycle-empty';
  const F1 = 'library.file.move-keeps-id-and-versions';
  const F2 = 'library.file.move-keeps-column-values';
  const F3 = 'library.file.move-system-fields';
  const F4 = 'library.file.move-keeps-unique-permissions';
  const F5 = 'library.file.move-adds-version';
  const F6 = 'library.folder.recycle-empty-restorable';
  const Q = {
    f1: 'Does the item keep its Id and every version label after the move?',
    f2: 'Does the item keep each of its five column values after the move?',
    f3: 'What are Created, Author, Modified and Editor before and after a move by a third account?',
    f4: 'Do the file\'s own grant and its sharing link survive the move?',
    f5: 'Does the move add a version?',
    f6: 'Does Folder.Recycle put the empty folder in the recycle bin, and can it be restored?',
  };
  expect('library.file.fixture-move-library', 'a document library with versioning on and this probe\'s Description');
  expect('library.file.fixture-move-folder', `a folder named ${FOLDER}, read back by name`);
  expect('library.file.fixture-move-values', 'the file in the folder, with MoveChoice, MovePerson, MoveFlag and MoveLink read back');
  expect('library.file.fixture-move-unique-grant', 'a Read grant to the editing account on the file alone, HasUniqueRoleAssignments true');
  expect('library.file.fixture-move-sharing-link', 'a sharing link with a URL, read back on the file');
  expect('library.file.fixture-move-before', 'before the move: three versions, Author the owner, Editor the editing account, a third mover');
  expect('library.file.fixture-move-answered', 'the MoveToUsingPath request answered 2xx');
  expect('library.folder.fixture-recycle-empty', 'the folder reads ItemCount 0, no files and no folders');
  expect('library.file.move-keeps-id-and-versions', Q.f1);
  expect('library.file.move-keeps-column-values', Q.f2);
  expect('library.file.move-system-fields', Q.f3);
  expect('library.file.move-keeps-unique-permissions', Q.f4);
  expect('library.file.move-adds-version', Q.f5);
  expect('library.folder.recycle-empty-restorable', Q.f6);

  // probe-catalog.json's depends_on, which test_file_move_probe_runtime.py holds this table to.
  const DEPENDS = {
    'library.file.fixture-move-folder': ['library.file.fixture-move-library'],
    'library.file.fixture-move-values': ['library.file.fixture-move-library', 'library.file.fixture-move-folder'],
    'library.file.fixture-move-unique-grant': ['library.file.fixture-move-values'],
    'library.file.fixture-move-sharing-link': ['library.file.fixture-move-values'],
    'library.file.fixture-move-before': ['library.file.fixture-move-values'],
    'library.file.fixture-move-answered': ['library.file.fixture-move-before'],
    'library.file.move-keeps-id-and-versions': ['library.file.fixture-move-before', 'library.file.fixture-move-answered'],
    'library.file.move-keeps-column-values': ['library.file.fixture-move-before', 'library.file.fixture-move-answered'],
    'library.file.move-system-fields': ['library.file.fixture-move-before', 'library.file.fixture-move-answered'],
    'library.file.move-adds-version': ['library.file.fixture-move-before', 'library.file.fixture-move-answered'],
    'library.file.move-keeps-unique-permissions': ['library.file.fixture-move-unique-grant',
      'library.file.fixture-move-sharing-link', 'library.file.fixture-move-answered'],
    'library.folder.fixture-recycle-empty': ['library.file.fixture-move-answered'],
    'library.folder.recycle-empty-restorable': ['library.folder.fixture-recycle-empty'],
  };
  // Every row resting on `row`, however far down, so a failed fixture leaves nothing below it open.
  const downstream = (row) => {
    const out = new Set([row]);
    for (let grew = true; grew;) {
      grew = false;
      for (const [rest, on] of Object.entries(DEPENDS)) {
        if (!out.has(rest) && on.some((d) => out.has(d))) { out.add(rest); grew = true; }
      }
    }
    out.delete(row);
    return [...out];
  };

  if (!CONFIRMED || !ALLOW_WRITES) {
    log('INFO', `STATE ${STATE}. Would ${CLEANUP ? `recycle '${LIBRARY}'` : ['', 'build the library, folder and file',
      'edit the file once', 'move the file to the root', 'read its grants and recycle the folder'][STATE]}.`);
    log('INFO', 'Nothing has been sent. Set CONFIRMED and ALLOW_WRITES to true.');
    return report();
  }
  if (!CLEANUP && (PLACEHOLDER.test(TEST_USER_LOGIN) || PLACEHOLDER.test(MOVER_LOGIN))) {
    log('ERROR', 'Set TEST_USER_LOGIN and MOVER_LOGIN first. Nothing has been sent.');
    return report();
  }

  const { digest } = await issueDigest();
  const send = (path, method, body) => sendRaw(path, { method: 'POST', body, headers: {
    'Content-Type': 'application/json;odata=nometadata', 'X-RequestDigest': digest,
    ...(method === 'POST' ? {} : { 'X-HTTP-Method': method, 'IF-MATCH': '*' }) } });
  // An answer's text is masked before rawHead cuts it short, so a cut never splits a login unmasked.
  const said = (res) => {
    const head = rawHead({ ...res, text: scrub(res.text) });
    return head ? head.why : `HTTP ${res.status}`;
  };
  const asRead = (res) => ({ ok: res.ok, status: res.status, body: res.parsed });
  const fixture = (row, read, declared) => establishFixture(row, read, declared, downstream(row));
  const { account } = await readAccount();
  const me = account && Number.isInteger(account.Id) ? account.Id : null;
  // Read-only, so the moving account resolves the editing one without ensureuser, which STATE 1 sends.
  const siteUser = async (login) => {
    const r = await sendRaw(`web/siteusers/getbyloginname(@v)?@v='${lit(login)}'&$select=Id`);
    return r.ok && r.parsed && Number.isInteger(r.parsed.Id) ? r.parsed.Id : null;
  };
  const versionsOf = async (itemId) => {
    // Unselected: whether a versions read honours $select is field.version's own open question.
    const r = await sendRaw(`${LIST}/items(${itemId})/versions`);
    return r.ok && r.parsed && Array.isArray(r.parsed.value) ? r.parsed.value.map((v) => v.VersionLabel) : null;
  };
  // The links array is looked for at the top level and under permissionsInformation; its absence is reported.
  const linksOn = async (itemId) => {
    const res = await send(`${LIST}/items(${itemId})/GetSharingInformation`, 'POST',
      { request: { maxPrincipalsToReturn: 10 } });
    const body = res.ok && res.parsed && typeof res.parsed === 'object' ? res.parsed : null;
    const nested = body && body.permissionsInformation;
    const list = !body ? null : Array.isArray(body.links) ? body.links
      : nested && Array.isArray(nested.links) ? nested.links : null;
    const withUrl = list ? list.filter((l) => l && l.linkDetails && typeof l.linkDetails.Url === 'string'
      && l.linkDetails.Url !== '').length : null;
    return { res, withUrl, entries: list ? list.length : null,
      keys: body ? Object.keys(body).sort().join(', ') || 'none' : said(res) };
  };

  const standing = await sendRaw(`${LIST}?$select=Id,Description`);
  if (CLEANUP || STATE !== 1) {
    const ours = standing.ok && standing.parsed && standing.parsed.Description === OWNERSHIP_DESCRIPTION;
    if (!ours) {
      log('ERROR', `'${LIBRARY}' ${standing.ok ? 'does not carry this probe\'s Description'
        : `read ${said(standing)}`}; nothing was written.`);
      return report();
    }
    if (CLEANUP) {
      // By the Id read with the marker, so a title rebound since cannot redirect the recycle.
      await resetList(LIBRARY, String(standing.parsed.Id).replace(/[{}]/g, ''));
      return report();
    }
  }
  const rootUrl = async () => {
    const r = await sendRaw(`${LIST}/RootFolder?$select=ServerRelativeUrl`);
    return r.ok && r.parsed ? r.parsed.ServerRelativeUrl : null;
  };
  const SELECT = 'Id,MoveChoice,MovePersonId,MoveDate,MoveFlag,MoveLink,Created,AuthorId,Modified,EditorId';
  const COLUMNS = ['MoveChoice', 'MovePersonId', 'MoveDate', 'MoveFlag', 'MoveLink'];
  const who = {};
  const name = (userId) => (userId === null || userId === undefined ? 'nobody' : who[userId] || 'another account');

  if (STATE === 1) {
    if (standing.status !== 404) {
      record(LIBRARY_ROW, 'a document library with versioning on and this probe\'s Description', 'FAIL',
        `a library titled '${LIBRARY}' already answers (${said(standing)}); paste CLEANUP as the owner first`);
      voidDependents(downstream(LIBRARY_ROW), 'the library was not created by this run');
      return report();
    }
    const made = await send('web/lists', 'POST', { Title: LIBRARY, BaseTemplate: 101,
      EnableVersioning: true, Description: OWNERSHIP_DESCRIPTION });
    log(made.ok ? 'INFO' : 'FAIL', `library create: ${said(made)}`);
    if (!await fixture(LIBRARY_ROW, async () => asRead(await sendRaw(`${LIST}?$select=BaseTemplate,EnableVersioning,Description`)),
      { BaseTemplate: 101, EnableVersioning: true, Description: OWNERSHIP_DESCRIPTION })) return report();
    for (const xml of [
      '<Field Type="Choice" Name="MoveChoice" DisplayName="MoveChoice"><CHOICES><CHOICE>Q1</CHOICE><CHOICE>Q2</CHOICE></CHOICES></Field>',
      '<Field Type="User" Name="MovePerson" DisplayName="MovePerson" UserSelectionMode="PeopleOnly" />',
      '<Field Type="DateTime" Name="MoveDate" DisplayName="MoveDate" Format="DateOnly" />',
      '<Field Type="Boolean" Name="MoveFlag" DisplayName="MoveFlag"><Default>0</Default></Field>',
      '<Field Type="URL" Name="MoveLink" DisplayName="MoveLink" Format="Hyperlink" />']) {
      const field = await send(`${LIST}/fields/createfieldasxml`, 'POST', { parameters: { SchemaXml: xml, Options: 8 } });
      log(field.ok ? 'INFO' : 'FAIL', `column create: ${said(field)}`);
    }
    const base = await rootUrl();
    const folder = await send(`web/Folders/AddUsingPath(decodedurl='${lit(`${base}/${FOLDER}`)}')`, 'POST', {});
    log(folder.ok ? 'INFO' : 'FAIL', `folder create: ${said(folder)}`);
    if (!await fixture(FOLDER_ROW, async () => asRead(await sendRaw(`${folderAt(`${base}/${FOLDER}`)}?$select=Name`)),
      { Name: FOLDER })) return report();
    // sendRaw sends its body as JSON, so the file holds a quoted string; nothing reads the content.
    const up = await sendRaw(`${folderAt(`${base}/${FOLDER}`)}/Files/AddUsingPath(DecodedUrl='${lit(FILE)}',Overwrite=false)`,
      { method: 'POST', headers: { 'X-RequestDigest': digest }, body: 'version one' });
    log(up.ok ? 'INFO' : 'FAIL', `file upload: ${said(up)}`);
    const item = await sendRaw(`${fileAt(`${base}/${FOLDER}/${FILE}`)}/ListItemAllFields?$select=Id`);
    const itemId = item.ok && item.parsed && Number.isInteger(item.parsed.Id) ? item.parsed.Id : null;
    if (itemId !== null) {
      const merged = await send(`${LIST}/items(${itemId})`, 'MERGE', { ...VALUES, MovePersonId: me });
      log(merged.ok ? 'INFO' : 'FAIL', `values write: ${said(merged)}`);
    }
    if (!await fixture(VALUES_ROW, async () => (itemId === null ? asRead(item)
      : asRead(await sendRaw(`${LIST}/items(${itemId})?$select=Id,MoveChoice,MovePersonId,MoveFlag,MoveLink`))),
    { MoveChoice: 'Q1', MovePersonId: (v) => me !== null && v === me, MoveFlag: true,
      MoveLink: (v) => Boolean(v) && v.Url === VALUES.MoveLink.Url })) return report();

    const ensured = await send('web/ensureuser', 'POST', { logonName: TEST_USER_LOGIN });
    // Status only: a refusal can quote the login it was given.
    log(ensured.ok ? 'INFO' : 'FAIL', `ensureuser for the editing account: HTTP ${ensured.status}`);
    const editor = ensured.ok && ensured.parsed && Number.isInteger(ensured.parsed.Id) ? ensured.parsed.Id : null;
    const role = await sendRaw('web/roledefinitions/getbytype(2)?$select=Id');
    const roleId = role.ok && role.parsed && Number.isInteger(role.parsed.Id) ? role.parsed.Id : null;
    if (editor !== null && roleId !== null) {
      const broke = await send(`${LIST}/items(${itemId})/breakroleinheritance(copyRoleAssignments=true,clearSubscopes=true)`, 'POST', {});
      log(broke.ok ? 'INFO' : 'FAIL', `break inheritance: ${said(broke)}`);
      const granted = await send(`${LIST}/items(${itemId})/roleassignments/addroleassignment(principalid=${editor},roledefid=${roleId})`, 'POST', {});
      log(granted.ok ? 'INFO' : 'FAIL', `Read grant: ${said(granted)}`);
    }
    await fixture(GRANT_ROW, async () => {
      const unique = await sendRaw(`${LIST}/items(${itemId})?$select=HasUniqueRoleAssignments`);
      const grants = await sendRaw(`${LIST}/items(${itemId})/roleassignments?$select=PrincipalId`);
      const bound = grants.ok && grants.parsed && Array.isArray(grants.parsed.value) && editor !== null
        && grants.parsed.value.some((g) => g.PrincipalId === editor);
      return { ok: unique.ok && grants.ok, status: unique.ok ? grants.status : unique.status, body: {
        HasUniqueRoleAssignments: unique.parsed ? unique.parsed.HasUniqueRoleAssignments : undefined,
        EditingAccountBound: bound } };
    }, { HasUniqueRoleAssignments: true, EditingAccountBound: true });
    const link = await send(`${LIST}/items(${itemId})/ShareLink`, 'POST',
      { request: { createLink: true, settings: { linkKind: 2 } } });
    log(link.ok ? 'INFO' : 'FAIL', `sharing link create: ${said(link)}`);
    await fixture(LINK_ROW, async () => {
      const seen = await linksOn(itemId);
      return { ok: seen.res.ok, status: seen.res.status,
        body: { LinksWithUrl: seen.withUrl === null ? undefined : seen.withUrl } };
    }, { LinksWithUrl: (n) => n > 0 });
    log('INFO', 'STATE 1 done. Paste STATE 2 as the editing account.');
    return report();
  }

  const root = await rootUrl();
  const oldPath = `${root}/${FOLDER}/${FILE}`;
  const newPath = `${root}/${FILE}`;

  if (STATE === 2) {
    const item = await sendRaw(`${fileAt(oldPath)}/ListItemAllFields?$select=Id`);
    const itemId = item.ok && item.parsed && Number.isInteger(item.parsed.Id) ? item.parsed.Id : null;
    if (itemId === null) {
      log('FAIL', `the file in the folder read ${said(item)}; nothing was edited.`);
      return report();
    }
    const edit = await send(`${LIST}/items(${itemId})`, 'MERGE', { MoveChoice: 'Q2' });
    log(edit.ok ? 'OK' : 'FAIL', `the edit answered ${said(edit)}. Paste STATE 3 as the moving account.`);
    return report();
  }

  if (STATE === 3) {
    const editor = await siteUser(TEST_USER_LOGIN);
    const first = await sendRaw(`${fileAt(oldPath)}/ListItemAllFields?$select=${SELECT}`);
    const before = first.ok && first.parsed && Number.isInteger(first.parsed.Id) ? first.parsed : null;
    const labels = before ? await versionsOf(before.Id) : null;
    if (before) who[before.AuthorId] = 'the owner';
    if (editor !== null) who[editor] = 'the editing account';
    if (me !== null) who[me] = who[me] || 'the moving account';
    if (!await fixture(BEFORE_ROW, async () => ({ ok: first.ok, status: first.status, body: {
      Versions: labels ? labels.length : undefined, Author: before ? name(before.AuthorId) : undefined,
      Editor: before ? name(before.EditorId) : undefined, Mover: name(me) } }),
    { Versions: 3, Author: 'the owner', Editor: 'the editing account', Mover: 'the moving account' })) {
      return report();
    }
    const move = await send(`${fileAt(oldPath)}/MoveToUsingPath`, 'POST',
      { newPath: { DecodedUrl: newPath }, moveOperations: 0 });
    if (!await fixture(ANSWERED_ROW, async () => ({ ok: true, status: 200, body: { Answer: said(move) } }),
      { Answer: () => move.ok })) return report();
    const at = await sendRaw(`${fileAt(newPath)}/ListItemAllFields?$select=${SELECT}`);
    const after = at.ok && at.parsed && Number.isInteger(at.parsed.Id) ? at.parsed : null;
    const afterLabels = after ? await versionsOf(after.Id) : null;
    if (!after || !afterLabels) {
      const why = after ? 'the moved item\'s versions did not read' : `the moved file read ${said(at)}`;
      for (const [row, question] of [[F1, Q.f1], [F2, Q.f2], [F3, Q.f3], [F5, Q.f5]]) {
        record(row, question, 'NOT ESTABLISHED', why);
      }
      return report();
    }
    const keptId = after.Id === before.Id;
    const keptVersions = JSON.stringify(afterLabels) === JSON.stringify(labels);
    record(F1, Q.f1, keptId && keptVersions ? 'ID AND VERSIONS KEPT' : !keptId ? 'ID CHANGED' : 'VERSIONS CHANGED',
      `Id ${before.Id} -> ${after.Id}; versions ${labels.join(', ')} -> ${afterLabels.join(', ')}`);
    const changed = COLUMNS.filter((c) => JSON.stringify(before[c]) !== JSON.stringify(after[c]));
    record(F2, Q.f2, changed.length ? 'VALUES CHANGED' : 'EVERY VALUE KEPT',
      COLUMNS.map((c) => `${c}: ${scrub(JSON.stringify(before[c]))} -> ${scrub(JSON.stringify(after[c]))}`).join('; '));
    record(F3, Q.f3, 'OBSERVED',
      `Created: ${before.Created} -> ${after.Created}; Author: ${name(before.AuthorId)} -> ${name(after.AuthorId)}; `
      + `Modified: ${before.Modified} -> ${after.Modified}; Editor: ${name(before.EditorId)} -> ${name(after.EditorId)}`);
    record(F5, Q.f5, afterLabels.length > labels.length ? 'VERSION ADDED' : 'NO VERSION ADDED',
      `${labels.length} version(s) before, ${afterLabels.length} after`);
    log('INFO', 'STATE 3 done. Paste STATE 4 as the owner.');
    return report();
  }

  // STATE 4: the owner.
  const editor = await siteUser(TEST_USER_LOGIN);
  const moved = await sendRaw(`${fileAt(newPath)}/ListItemAllFields?$select=Id,HasUniqueRoleAssignments`);
  if (moved.ok && moved.parsed && Number.isInteger(moved.parsed.Id)) {
    const itemId = moved.parsed.Id;
    const grants = await sendRaw(`${LIST}/items(${itemId})/roleassignments?$select=PrincipalId`);
    const seen = await linksOn(itemId);
    const read = grants.ok && grants.parsed && Array.isArray(grants.parsed.value) && seen.withUrl !== null;
    const held = read && editor !== null && grants.parsed.value.some((g) => g.PrincipalId === editor);
    const linked = read && seen.withUrl > 0;
    const head = !read ? 'NOT ESTABLISHED' : held && linked ? 'GRANT AND LINK PRESENT'
      : !held && !linked ? 'GRANT AND LINK LOST' : !held ? 'GRANT LOST' : 'LINK LOST';
    record(F4, Q.f4, head, `HasUniqueRoleAssignments ${moved.parsed.HasUniqueRoleAssignments}; bindings read `
      + `${grants.ok ? `with the editing account ${held ? 'bound' : 'not bound'}` : said(grants)}; sharing `
      + `information ${seen.entries === null ? `carried no links array (${seen.keys})`
        : `listed ${seen.entries} link(s), ${seen.withUrl} with a URL`}`);
  } else {
    record(F4, Q.f4, 'NOT ESTABLISHED', `the moved file read ${said(moved)}`);
  }
  const at = folderAt(`${root}/${FOLDER}`);
  if (!await fixture(EMPTY_ROW, async () => {
    const meta = await sendRaw(`${at}?$select=ItemCount`);
    const files = await sendRaw(`${at}/Files?$select=Name`);
    const folders = await sendRaw(`${at}/Folders?$select=Name`);
    const count = (r) => (r.ok && r.parsed && Array.isArray(r.parsed.value) ? r.parsed.value.length : undefined);
    const failed = [meta, files, folders].find((r) => !r.ok);
    return { ok: !failed, status: failed ? failed.status : 200,
      body: { ItemCount: meta.parsed ? meta.parsed.ItemCount : undefined, Files: count(files), Folders: count(folders) } };
  }, { ItemCount: 0, Files: 0, Folders: 0 })) return report();
  const recycled = await send(`${at}/recycle`, 'POST', {});
  const refusal = rawHead(recycled);
  if (refusal) {
    record(F6, Q.f6, refusal.outcome, `the recycle ${said(recycled)}; nothing was restored`);
    return report();
  }
  const bin = await sendRaw(`web/RecycleBin?$select=Id,LeafName&$filter=LeafName eq '${lit(FOLDER)}'`);
  const entries = bin.ok && bin.parsed && Array.isArray(bin.parsed.value)
    ? bin.parsed.value.filter((e) => e.LeafName === FOLDER) : null;
  // Two entries of one name cannot be told apart here, so neither is restored.
  if (entries && entries.length > 1) {
    record(F6, Q.f6, 'NOT ESTABLISHED', `recycle HTTP ${recycled.status}; ${entries.length} bin entries `
      + `are named ${FOLDER}, so none was restored; restore this run's by hand`);
    return report();
  }
  const entry = entries && entries.length === 1 ? entries[0] : null;
  const restored = entry ? await send(`web/RecycleBin('${lit(entry.Id)}')/restore`, 'POST', {}) : null;
  const back = await sendRaw(`${at}?$select=Name`);
  record(F6, Q.f6, entries === null ? 'NOT ESTABLISHED' : !entry ? 'NOT IN THE BIN' : back.ok ? 'RECYCLED AND RESTORED' : 'RECYCLED, NOT RESTORED',
    `recycle HTTP ${recycled.status}; bin ${entries ? `entry ${entry ? 'found' : 'absent'}` : `read ${said(bin)}`}; `
    + `restore ${restored ? said(restored) : 'not sent'}; folder ${back.ok ? 'reads back' : said(back)}`);
  return report();
})();
