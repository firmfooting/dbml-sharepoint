
/** ---- dbml-sharepoint PROBE: WHAT AN ITEM'S VERSIONS CARRY, PER COLUMN KIND ----
 *
 * REVISION: 8920f785
 *
 * QUESTION: what does `items(id)/versions` return for a choice, multi-choice,
 * person, multi-person, lookup, date-only, date-and-time, number and Yes/No
 * column, and does each version carry VersionId, VersionLabel, Editor and
 * Modified? For a file in a library's subfolder, does a content-only upload
 * between two property edits add a version, and what does that version hold?
 *
 * WHY: a flow that records every change to a watched column reads the item's
 * versions once per run and renders each value to text by its column kind.
 * "Working with lists and list items with REST" does not cover item versions,
 * so the spelling of each kind in a version is measured here. A watched
 * library is read the same way. "Working with folders and files with REST"
 * documents creating a folder (POST web/folders), adding a file (Files/add),
 * replacing its content (a PUT to $value) and reaching a file's metadata as a
 * list item; it does not say whether a content upload makes an item version.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   field.version.control-current-user          this account's Id reads back
 *   field.version.fixture-payload-target-list   a list holding two items the lookup points at
 *   field.version.fixture-payload-list          a generic list with versioning on
 *   field.version.fixture-payload-columns       eight columns read back with their TypeAsString
 *   field.version.fixture-payload-people-column a multi-person column (UserMulti); only
 *       the people write and field.version.payload-people rest on it
 *   field.version.fixture-payload-item          one item created empty and then written
 *       twice, each set of values read back before the next is sent
 *   field.version.fixture-payload-people-write  the multi-person column written as
 *       { results: [Id] } in both writes and read back; a refusal leaves it and
 *       field.version.payload-people NOT ESTABLISHED, and the other kinds are written without it
 *   field.version.control-payload-versions-read the versions read answers a list of entries
 *   The library case, each row resting on every one before it:
 *   field.version.fixture-library               a document library (BaseTemplate 101) this
 *       probe created, with versioning on and minor versions off
 *   field.version.fixture-library-column        a Choice column on the library
 *   field.version.fixture-library-folder        a folder in the library, read back by name
 *   field.version.fixture-library-file          a file added to that folder, whose item Id
 *       reads back through ListItemAllFields (the form Learn shows for a folder)
 *   field.version.fixture-library-edit-first    the file's Choice edited to Q1, read back
 *   field.version.fixture-library-upload        the file's content replaced by a PUT to
 *       $value; the new content reads back, and a read of the item carries the Choice
 *   field.version.fixture-library-edit-second   the file's Choice edited to Q2, read back
 *   field.version.control-library-versions-read the file's versions read answers entries
 *
 * OBSERVES (recorded verbatim per version, never compared with an expected value)
 *   field.version.payload-choice, -multichoice, -person, -people, -lookup, -date,
 *       -datetime, -number, -boolean   every property of each version whose name
 *       begins with the column's name, and its raw value
 *   field.version.payload-version-fields  VersionId, VersionLabel, Editor and Modified
 *       on each version, and every property name the version with the greatest
 *       VersionLabel carries
 *   field.version.versionid-follows-label  whether VersionId rises as VersionLabel does
 *   field.version.library-upload-adds-version  the file's versions read just before and
 *       just after the upload, the entries the second read adds, the Choice as read after
 *       the upload, and the versions after the second edit with the Choice each holds
 *   field.version.library-upload-version-fields  every property of the upload's version
 *
 * HOW TO READ IT: OBSERVED is the column's properties as each version carried
 * them. ABSENT is a versions answer carrying no property named for the column.
 * INCREASES WITH LABEL, DOES NOT INCREASE WITH LABEL and NOT COMPARABLE name
 * how the VersionIds fall when the versions are put in label order.
 * UPLOAD ADDED A VERSION, UPLOAD ADDED MORE THAN ONE VERSION and UPLOAD ADDED
 * NO VERSION count the entries (VersionId and VersionLabel together) that the
 * read just after the upload has and the read just before it lacks. There,
 * NOT COMPARABLE is an earlier entry gone from the later read or an entry with
 * no VersionId, and NOT ESTABLISHED, left open, is either read unanswered.
 * NOT IDENTIFIED is the fields row when no version is the upload's alone.
 * NOT COMPARABLE, left open, is a versions read carrying a continuation link,
 * which the probe records and does not follow.
 * Email addresses, claims logins and this account's display name are masked.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Set CONFIRMED and ALLOW_WRITES to true and paste again
 * (CLEANUP = true recycles lists left by an earlier run first). Copy the
 * RESULTS block back verbatim.
 *
 * WHEN FINISHED: nothing to delete. The probe recycles both lists and the
 * library before it reports.
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

  // Creates a list or library (generic unless `baseTemplate` says otherwise) owned by `description`, then reads it back.
  const claimScratchList = async ({ id, question, title, description, dependents,
    settings = null, declared = {}, baseTemplate = 100 }) => {
    const path = `web/lists/getbytitle('${title}')`;
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
      // A recycle answered 2xx is not the list gone, and a create over a standing leftover would not be new.
      const after = await listGone(leftover);
      if (after.gone === false) {
        record(id, question, 'FAIL', `the leftover list '${title}' (list ${leftover}) answered its recycle, `
          + `but ${after.why}; recycle it by hand`);
        voidDependents(dependents, 'a leftover list would answer this run\'s questions');
        return { held: false, merge: null, body: null };
      }
      if (after.gone === null) {
        return leaveOpen(`the leftover list '${title}' (list ${leftover}) answered its recycle, but ${after.why}; `
          + 'nothing was created');
      }
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
      merge = await spPost(`web/lists(guid'${created.id}')`, { __metadata: { type: 'SP.List' }, ...settings }, await getDigest(),
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
        log('FAIL', `'${title}' never answered a list Id, so it was not recycled; if it stands, recycle it by hand.`);
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
      if (!gone.ok) {
        log('FAIL', `could not recycle '${title}' (list ${id}, ${why}); recycle it by hand.`);
        continue;
      }
      // A recycle answered 2xx is reported done only once the list no longer reads back by its Id.
      const after = await listGone(id);
      log(after.gone ? 'OK' : 'FAIL', after.gone
        ? `recycled '${title}' (list ${id}); it is restorable from the recycle bin.`
        : `the recycle of '${title}' (list ${id}) answered ${why}, but ${after.why}; check it and recycle it by hand.`);
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
  log('INFO', 'probe revision 8920f785. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Versions';
  const TARGET = 'dbmlsp Probe VersionsTarget';
  // Ownership is the Description, never the title: a same-title list this probe did not make is left alone.
  const OWNERSHIP = 'dbml-sharepoint item-versions probe scratch list. Safe to delete.';
  const TARGET_OWNERSHIP = 'dbml-sharepoint item-versions probe lookup target. Safe to delete.';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const targetPath = `web/lists/getbytitle('${TARGET}')`;
  const PEOPLE = 'ProbePeople';
  const LIBRARY = 'dbmlsp Probe VersionsLibrary';
  const LIBRARY_OWNERSHIP = 'dbml-sharepoint item-versions probe scratch library. Safe to delete.';
  const libraryPath = `web/lists/getbytitle('${LIBRARY}')`;
  const LIB_COLUMN = 'ProbeLibChoice';
  const FOLDER_NAME = 'dbmlsp-subfolder';
  const FILE_NAME = 'dbmlsp-versions.txt';
  const CONTENT = ['dbmlsp versions content 1', 'dbmlsp versions content 2'];
  // The deploy's create bodies (generators/jsgen.py), so a refusal is about the column, not the request.
  const COLUMNS = [
    { name: 'ProbeChoice', kind: 'choice', type: 'Choice', body: { __metadata: { type: 'SP.FieldChoice' },
      FieldTypeKind: 6, Choices: { results: ['Q1', 'Q2'] }, FillInChoice: false } },
    { name: 'ProbeMulti', kind: 'multichoice', type: 'MultiChoice', body: {
      __metadata: { type: 'SP.FieldMultiChoice' }, FieldTypeKind: 15, Choices: { results: ['Q1', 'Q2'] },
      FillInChoice: false } },
    { name: 'ProbePerson', kind: 'person', type: 'User', body: { __metadata: { type: 'SP.FieldUser' },
      FieldTypeKind: 20, SelectionMode: 0 } },
    { name: 'ProbeLookup', kind: 'lookup', type: 'Lookup', body: null },
    { name: 'ProbeDate', kind: 'date', type: 'DateTime', body: { __metadata: { type: 'SP.FieldDateTime' },
      FieldTypeKind: 4, DisplayFormat: 0 } },
    { name: 'ProbeStamp', kind: 'datetime', type: 'DateTime', body: {
      __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, DisplayFormat: 1 } },
    { name: 'ProbeNumber', kind: 'number', type: 'Number', body: { __metadata: { type: 'SP.FieldNumber' },
      FieldTypeKind: 9 } },
    { name: 'ProbeFlag', kind: 'boolean', type: 'Boolean', body: { __metadata: { type: 'SP.Field' },
      FieldTypeKind: 8 } },
  ];

  const Q = {
    user: 'this account\'s Id reads back from web/currentuser',
    target: 'a lookup target list this probe created, holding two items',
    list: 'a generic list this probe created, with versioning on',
    columns: 'the eight columns read back with their declared TypeAsString',
    peopleColumn: `${PEOPLE} reads back as a multi-person column (UserMulti, AllowMultipleValues true)`,
    item: 'one item created empty and written twice, each set of values read back before the next',
    peopleWrite: `${PEOPLE}Id written as { results: [this account's Id] } in both writes, read back`,
    read: 'CONTROL: items(id)/versions answers a list of version entries',
    choice: 'what each version carries for a Choice column',
    multichoice: 'what each version carries for a multi-choice column',
    person: 'what each version carries for a person column',
    people: 'what each version carries for a multi-person column',
    lookup: 'what each version carries for a lookup column',
    date: 'what each version carries for a date-only column',
    datetime: 'what each version carries for a date-and-time column',
    number: 'what each version carries for a Number column',
    boolean: 'what each version carries for a Yes/No column',
    fields: 'VersionId, VersionLabel, Editor and Modified on each version, and the property names of the version '
      + 'with the greatest VersionLabel',
    order: 'whether VersionId rises as VersionLabel does across the versions answered',
    library: 'a document library this probe created, with versioning on and minor versions off',
    libraryColumn: `${LIB_COLUMN} reads back as a Choice column on the library`,
    libraryFolder: `a folder ${FOLDER_NAME} created in the library and read back`,
    libraryFile: `a file ${FILE_NAME} added to the folder, whose list item Id reads back`,
    libraryFirst: `the file's ${LIB_COLUMN} edited to Q1 and read back`,
    libraryUpload: 'the file\'s content replaced by a PUT to $value, and its content read back',
    librarySecond: `the file's ${LIB_COLUMN} edited to Q2 and read back`,
    libraryRead: 'CONTROL: items(id)/versions answers a list of version entries for the file',
    libraryAdds: 'whether the content-only upload between the two edits added a version',
    libraryFields: 'every property the upload\'s version carries, and its value',
  };
  expect('field.version.control-current-user', Q.user);
  expect('field.version.fixture-payload-target-list', Q.target);
  expect('field.version.fixture-payload-list', Q.list);
  expect('field.version.fixture-payload-columns', Q.columns);
  expect('field.version.fixture-payload-people-column', Q.peopleColumn);
  expect('field.version.fixture-payload-item', Q.item);
  expect('field.version.fixture-payload-people-write', Q.peopleWrite);
  expect('field.version.control-payload-versions-read', Q.read);
  expect('field.version.payload-choice', Q.choice);
  expect('field.version.payload-multichoice', Q.multichoice);
  expect('field.version.payload-person', Q.person);
  expect('field.version.payload-people', Q.people);
  expect('field.version.payload-lookup', Q.lookup);
  expect('field.version.payload-date', Q.date);
  expect('field.version.payload-datetime', Q.datetime);
  expect('field.version.payload-number', Q.number);
  expect('field.version.payload-boolean', Q.boolean);
  expect('field.version.payload-version-fields', Q.fields);
  expect('field.version.versionid-follows-label', Q.order);
  // The library rows in the order they rest on each other; each voids every row after it.
  const LIB = {
    library: 'field.version.fixture-library',
    libraryColumn: 'field.version.fixture-library-column',
    libraryFolder: 'field.version.fixture-library-folder',
    libraryFile: 'field.version.fixture-library-file',
    libraryFirst: 'field.version.fixture-library-edit-first',
    libraryUpload: 'field.version.fixture-library-upload',
    librarySecond: 'field.version.fixture-library-edit-second',
    libraryRead: 'field.version.control-library-versions-read',
    libraryAdds: 'field.version.library-upload-adds-version',
    libraryFields: 'field.version.library-upload-version-fields',
  };
  expect('field.version.fixture-library', Q.library);
  expect('field.version.fixture-library-column', Q.libraryColumn);
  expect('field.version.fixture-library-folder', Q.libraryFolder);
  expect('field.version.fixture-library-file', Q.libraryFile);
  expect('field.version.fixture-library-edit-first', Q.libraryFirst);
  expect('field.version.fixture-library-upload', Q.libraryUpload);
  expect('field.version.fixture-library-edit-second', Q.librarySecond);
  expect('field.version.control-library-versions-read', Q.libraryRead);
  expect('field.version.library-upload-adds-version', Q.libraryAdds);
  expect('field.version.library-upload-version-fields', Q.libraryFields);
  const LIB_CHAIN = Object.values(LIB);
  const afterLib = (id) => LIB_CHAIN.slice(LIB_CHAIN.indexOf(id) + 1);

  const SUBJECTS = {
    choice: 'field.version.payload-choice',
    multichoice: 'field.version.payload-multichoice',
    person: 'field.version.payload-person',
    people: 'field.version.payload-people',
    lookup: 'field.version.payload-lookup',
    date: 'field.version.payload-date',
    datetime: 'field.version.payload-datetime',
    number: 'field.version.payload-number',
    boolean: 'field.version.payload-boolean',
    fields: 'field.version.payload-version-fields',
    order: 'field.version.versionid-follows-label',
  };
  const AFTER_READ = Object.values(SUBJECTS);
  const PEOPLE_WRITE = 'field.version.fixture-payload-people-write';
  const AFTER_ITEM = [PEOPLE_WRITE, 'field.version.control-payload-versions-read', ...AFTER_READ];
  const AFTER_COLUMNS = ['field.version.fixture-payload-people-column', 'field.version.fixture-payload-item',
    ...AFTER_ITEM];
  const AFTER_LIST = ['field.version.fixture-payload-columns', ...AFTER_COLUMNS];
  const AFTER_TARGET = ['field.version.fixture-payload-list', ...AFTER_LIST];
  const AFTER_USER = ['field.version.fixture-payload-target-list', ...AFTER_TARGET, ...LIB_CHAIN];

  if (!CONFIRMED) {
    log('INFO', `Would create a list '${TARGET}' holding two items and a list '${LIST}' on ${WEB}`);
    log('INFO', 'with versioning on and nine columns (choice, multi-choice, person, multi-person,');
    log('INFO', 'lookup, date, date-and-time, number, Yes/No), create one item and write it twice,');
    log('INFO', `then read its versions. It then creates a library '${LIBRARY}' with a folder, adds a`);
    log('INFO', 'file there, edits a property, replaces the content, edits the property again, and');
    log('INFO', 'reads the file\'s versions. The lists and the library are recycled on the way out.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write. Stopping.');
    return;
  }

  const show = (value) => (value === undefined ? '(absent)' : scrub(JSON.stringify(value)));
  const members = (value) => (Array.isArray(value) ? value
    : value && typeof value === 'object' && Array.isArray(value.results) ? value.results : null);
  const sameMembers = (value, want) => {
    const got = members(value);
    return got !== null && [...got].sort().join('|') === [...want].sort().join('|');
  };
  // A read keeps its answer, so a refused read is never mistaken for a missing object.
  const readBack = async (path) => {
    const res = await sendRaw(path);
    const head = rawHead(res);
    const parsed = !head && res.parsed && typeof res.parsed === 'object' ? res.parsed : null;
    return { parsed, read: head ? scrub(head.why) : parsed ? `HTTP ${res.status}`
      : `HTTP ${res.status} carried no JSON: ${scrub(res.text).slice(0, 400)}` };
  };

  let meId = null;
  let peopleHeld = false;
  let peopleWritten = false;

  const labelOf = (row) => (row.VersionLabel === undefined ? '(no VersionLabel)' : String(row.VersionLabel));
  // A label is major.minor, compared as a pair so that 10.0 follows 9.0.
  const labelPair = (row) => {
    const match = /^(\d+)\.(\d+)$/.exec(String(row.VersionLabel));
    return match ? [Number(match[1]), Number(match[2])] : null;
  };
  // A versions read is the control its observations rest on: a refusal voids them, a throttle leaves them open.
  const recordVersionsRead = (id, question, versions, observed, what) => {
    const held = versions.rows !== null && versions.rows.length > 0;
    const outcome = held ? 'PASS'
      : (versions.head && versions.head.outcome === 'NOT ESTABLISHED' ? 'NOT ESTABLISHED' : 'FAIL');
    record(id, question, outcome, versions.head
      ? scrub(versions.head.why)
      : `HTTP ${versions.res.status}, ${versions.rows === null ? 'no value array' : `${versions.rows.length} entries`}`
        + `: ${scrub(versions.res.text).slice(0, 400)}`);
    if (outcome === 'FAIL') voidDependents(observed, `the ${what} answered no version entries`);
    if (outcome === 'NOT ESTABLISHED') {
      for (const one of observed) {
        const row = RESULTS.find((r) => r.id === one);
        record(one, row.question, 'NOT ESTABLISHED',
          `not asked: the ${what} was not established (${scrub(versions.head.why)}); a re-run can ask it`);
      }
    }
    return held;
  };

  // The list case: nine column kinds on one item created empty and written twice.
  const listCase = async () => {
    const target = await claimScratchList({ id: 'field.version.fixture-payload-target-list',
      question: Q.target, title: TARGET, description: TARGET_OWNERSHIP, dependents: AFTER_TARGET,
      declared: { ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 } });
    if (!target.held) return;
    const targetIds = [];
    for (const title of ['dbmlsp versions target A', 'dbmlsp versions target B']) {
      const made = await spPost(`${targetPath}/items`,
        { __metadata: { type: target.body.ListItemEntityTypeFullName }, Title: title },
        await getDigest(), VERBOSE_WRITE);
      log('INFO', `seed ${title}: HTTP ${made.status}`);
      if (made.ok && made.body && Number.isInteger(made.body.Id)) targetIds.push(made.body.Id);
    }
    if (targetIds.length !== 2) {
      record('field.version.fixture-payload-target-list', Q.target, 'FAIL',
        `the target list was created but ${targetIds.length} of its two items answered an Id`);
      voidDependents(AFTER_TARGET, 'the lookup target does not hold the two items the lookup is written to');
      return;
    }

    const list = await claimScratchList({ id: 'field.version.fixture-payload-list', question: Q.list,
      title: LIST, description: OWNERSHIP, dependents: AFTER_LIST, settings: { EnableVersioning: true },
      declared: { EnableVersioning: true,
        ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 } });
    if (!list.held) return;
    const itemType = list.body.ListItemEntityTypeFullName;

    for (const column of COLUMNS) {
      const sent = column.body === null
        ? await spPost(`${listPath}/fields/addfield`, { parameters: { Title: column.name, FieldTypeKind: 7,
          LookupListId: target.body.Id, LookupFieldName: 'Title' } }, await getDigest())
        : await spPost(`${listPath}/fields`, { ...column.body, Title: column.name, Required: false },
          await getDigest(), VERBOSE_WRITE);
      log('INFO', `create ${column.name}: HTTP ${sent.status}`
        + `${sent.ok ? '' : ` ${scrub(sent.text).slice(0, 200)}`}`);
    }
    const declaredColumns = {};
    for (const column of COLUMNS) {
      declaredColumns[`${column.name}.Read`] = 'HTTP 200';
      declaredColumns[`${column.name}.TypeAsString`] = column.type;
    }
    if (!await establishFixture('field.version.fixture-payload-columns', async () => {
      const body = {};
      for (const column of COLUMNS) {
        const read = await readBack(`${listPath}/fields/getbyinternalnameortitle('${column.name}')`
          + '?$select=InternalName,TypeAsString');
        body[`${column.name}.Read`] = read.read;
        if (read.parsed) body[`${column.name}.TypeAsString`] = read.parsed.TypeAsString;
      }
      return { ok: true, status: 200, body };
    }, declaredColumns, AFTER_COLUMNS)) {
      return;
    }

    // The schema XML route, as the deploy creates a multi-value lookup, since AddField has no arity.
    const peopleSent = await spPost(`${listPath}/fields/createfieldasxml`, { parameters: {
      SchemaXml: `<Field Type="UserMulti" Mult="TRUE" UserSelectionMode="PeopleOnly" DisplayName="${PEOPLE}" `
        + `Name="${PEOPLE}"/>`,
      Options: 8 } }, await getDigest());
    log('INFO', `create ${PEOPLE}: HTTP ${peopleSent.status}`
      + `${peopleSent.ok ? '' : ` ${scrub(peopleSent.text).slice(0, 200)}`}`);
    peopleHeld = await establishFixture('field.version.fixture-payload-people-column', async () => {
      const read = await readBack(`${listPath}/fields/getbyinternalnameortitle('${PEOPLE}')`
        + '?$select=InternalName,TypeAsString,AllowMultipleValues');
      if (!read.parsed) return { ok: true, status: 200, body: { Read: read.read } };
      return { ok: true, status: 200, body: { Read: read.read, TypeAsString: read.parsed.TypeAsString,
        AllowMultipleValues: read.parsed.AllowMultipleValues } };
    }, { Read: 'HTTP 200', TypeAsString: 'UserMulti', AllowMultipleValues: true },
    [PEOPLE_WRITE, SUBJECTS.people]);

    // Version 1 holds every column empty; versions 2 and 3 write set A, then set B.
    const SETS = [
      { ProbeChoice: 'Q1', ProbeMulti: ['Q1'], ProbeLookupId: targetIds[0],
        ProbeDate: '2026-01-15T00:00:00Z', ProbeStamp: '2026-01-15T09:30:00Z', ProbeNumber: 1.5,
        ProbeFlag: false },
      { ProbeChoice: 'Q2', ProbeMulti: ['Q1', 'Q2'], ProbeLookupId: targetIds[1],
        ProbeDate: '2026-02-20T00:00:00Z', ProbeStamp: '2026-02-20T17:45:00Z', ProbeNumber: 2.25,
        ProbeFlag: true },
    ];
    const bodyOf = (set, withPeople) => ({
      __metadata: { type: itemType }, ...set,
      // A multi-value column takes a collection, the shape the demo writer sends.
      ProbeMulti: { __metadata: { type: 'Collection(Edm.String)' }, results: set.ProbeMulti },
      ProbePersonId: meId,
      // The multi-value lookup shape; for a multi-person column it is the question the people write asks.
      ...(withPeople ? { [`${PEOPLE}Id`]: { results: [meId] } } : {}),
    });
    // What a set reads back as once written; a date only needs a value, since its stored form is a question.
    // The people value is left to its own fixture, so a refusal of that shape never fails the other kinds.
    const wantOf = (set) => ({
      ProbeChoice: set.ProbeChoice, ProbeMulti: (v) => sameMembers(v, set.ProbeMulti), ProbePersonId: meId,
      ProbeLookupId: set.ProbeLookupId, ProbeDate: (v) => typeof v === 'string' && v.length > 0,
      ProbeStamp: (v) => typeof v === 'string' && v.length > 0, ProbeNumber: set.ProbeNumber,
      ProbeFlag: set.ProbeFlag,
    });
    // What differs between the item and a set just written, or null when the whole set reads back.
    const unlanded = async (set) => {
      const want = wantOf(set);
      const read = await readBack(`${listPath}/items(${itemId})?$select=Id,${Object.keys(want).join(',')}`);
      if (!read.parsed) return `the read-back ${read.read}`;
      const off = Object.entries(want).filter(([key, value]) => (typeof value === 'function'
        ? value(read.parsed[key]) !== true : read.parsed[key] !== value));
      return off.length ? off.map(([key]) => `${key} reads back ${show(read.parsed[key])}`).join(', ') : null;
    };
    let written = 0;
    const missed = [];
    let itemId = null;
    let peopleRefusal = null;
    const made = await spPost(`${listPath}/items`, { __metadata: { type: itemType },
      Title: 'dbmlsp versions item' }, await getDigest(), VERBOSE_WRITE);
    if (made.ok && made.body && Number.isInteger(made.body.Id)) itemId = made.body.Id;
    if (itemId !== null) written += 1;
    else {
      missed.push(`the create: HTTP ${made.status}`
        + `${made.ok ? ' carried no numeric Id' : `: ${scrub(made.text).slice(0, 300)}`}`);
    }
    const merge = async (set, withPeople) => spPost(`${listPath}/items(${itemId})`, bodyOf(set, withPeople),
      await getDigest(), { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    // Each set is read back before the next is sent, so set B never replaces a set A that did not land.
    for (const [i, set] of (itemId === null ? [] : SETS).entries()) {
      const withPeople = peopleHeld && peopleRefusal === null;
      let sent = await merge(set, withPeople);
      if (withPeople && !sent.ok && isRefusal(sent.status)) {
        // Sent again without the people value, so a refusal is pinned on it and the other kinds still land.
        const without = await merge(set, false);
        if (without.ok) {
          peopleRefusal = `HTTP ${sent.status}: ${scrub(sent.text).slice(0, 300)}`;
          log('INFO', `the ${PEOPLE}Id write was refused (${peopleRefusal}); the values were written without it`);
        }
        sent = without;
      }
      const what = `set ${'AB'[i]}: HTTP ${sent.status}`;
      const off = sent.ok ? await unlanded(set) : scrub(sent.text).slice(0, 300);
      if (sent.ok && off === null) {
        written += 1;
        continue;
      }
      missed.push(`${what}${sent.ok ? `, but ${off}` : `: ${off}`}`);
      break;
    }
    const last = SETS[1];
    const declaredItem = { Written: 3, Missed: (v) => typeof v === 'string', ...wantOf(last) };
    const selected = Object.keys(declaredItem).filter((key) => key !== 'Written' && key !== 'Missed');
    if (!await establishFixture('field.version.fixture-payload-item', async () => {
      // The sets that did not land join the read-back, so each shows its reason in RESULTS.
      const body = { Written: written, Missed: missed.join('; ') || 'none' };
      if (itemId === null) return { ok: true, status: 200, body };
      const read = await readBack(`${listPath}/items(${itemId})?$select=Id,${selected.join(',')}`);
      if (!read.parsed) return { ok: true, status: 200, body: { ...body, Read: read.read } };
      for (const key of selected) body[key] = read.parsed[key];
      return { ok: true, status: 200, body };
    }, declaredItem, AFTER_ITEM)) {
      return;
    }

    if (peopleHeld && peopleRefusal !== null) {
      // A refused write shape leaves the question open for a re-run with another shape, never the probe failed.
      record(PEOPLE_WRITE, Q.peopleWrite, 'NOT ESTABLISHED', `the write was refused: ${peopleRefusal}; `
        + 'each value set was written again without it, so the other kinds are unaffected');
      record(SUBJECTS.people, Q.people, 'NOT ESTABLISHED', `not asked: the ${PEOPLE}Id write shape was `
        + 'refused, so no version carries a value written to it; a re-run with another shape can ask it');
    } else if (peopleHeld) {
      peopleWritten = await establishFixture(PEOPLE_WRITE, async () => {
        const read = await readBack(`${listPath}/items(${itemId})?$select=Id,${PEOPLE}Id`);
        if (!read.parsed) return { ok: true, status: 200, body: { Read: read.read } };
        return { ok: true, status: 200, body: { Read: read.read, [`${PEOPLE}Id`]: read.parsed[`${PEOPLE}Id`] } };
      }, { Read: 'HTTP 200', [`${PEOPLE}Id`]: (v) => sameMembers(v, [meId]) }, [SUBJECTS.people]);
    }

    const versions = await readVersions(listPath, itemId);
    const asked = AFTER_READ.filter((id) => peopleWritten || id !== SUBJECTS.people);
    if (!recordVersionsRead('field.version.control-payload-versions-read', Q.read, versions, asked,
      'versions read')) {
      return;
    }

    if (versions.next !== null) {
      for (const id of asked) {
        const row = RESULTS.find((r) => r.id === id);
        record(id, row.question, 'NOT COMPARABLE', pagedSaid(versions), 'open');
      }
      return;
    }
    const rows = versions.rows;
    const observed = [...COLUMNS.map((c) => ({ name: c.name, kind: c.kind })),
      ...(peopleWritten ? [{ name: PEOPLE, kind: 'people' }] : [])];
    for (const column of observed) {
      const keys = [...new Set(rows.flatMap((row) => Object.keys(row)
        .filter((key) => key.startsWith(column.name))))].sort();
      const perVersion = rows.map((row) => `${labelOf(row)}: {${keys.map((key) => `${key}=${show(row[key])}`)
        .join(', ')}}`);
      record(SUBJECTS[column.kind], Q[column.kind], keys.length ? 'OBSERVED' : 'ABSENT',
        `${rows.length} version(s) in the order answered; properties beginning ${column.name}: `
        + `${keys.join(', ') || 'none'}; ${perVersion.join('; ')}`);
    }
    const FOUR = ['VersionId', 'VersionLabel', 'Editor', 'Modified'];
    const presence = FOUR.map((key) => `${key} on ${rows.filter((row) => row[key] !== undefined).length}`
      + ` of ${rows.length}`);
    const perVersion = rows.map((row) => FOUR.map((key) => `${key}=${show(row[key])}`).join(', '));
    // Named by its label, never by its place in the answer, since the order versions come back in is a question.
    const labelled = rows.every((row) => labelPair(row) !== null);
    const greatest = labelled ? rows.reduce((top, row) => (labelPair(row)[0] - labelPair(top)[0]
      || labelPair(row)[1] - labelPair(top)[1]) > 0 ? row : top) : null;
    const named = greatest
      ? `The entry with the greatest VersionLabel, ${labelOf(greatest)}, carries: ${Object.keys(greatest).sort().join(', ')}`
      : 'Not every VersionLabel is major.minor, so no entry is named the greatest; the entries together carry: '
        + `${[...new Set(rows.flatMap((row) => Object.keys(row)))].sort().join(', ')}`;
    record(SUBJECTS.fields, Q.fields, 'OBSERVED', `${presence.join('; ')}. Per version: `
      + `${perVersion.join(' | ')}. ${named}`);

    const pairs = rows.map((row) => ({ at: labelPair(row), id: versionIdOf(row), label: labelOf(row) }));
    const comparable = rows.length > 1 && pairs.every((p) => p.at !== null && typeof p.id === 'number');
    const byLabel = comparable ? [...pairs].sort((a, b) => a.at[0] - b.at[0] || a.at[1] - b.at[1]) : pairs;
    const rising = comparable && byLabel.slice(1).every((p, i) => p.id > byLabel[i].id);
    record(SUBJECTS.order, Q.order,
      !comparable ? 'NOT COMPARABLE' : rising ? 'INCREASES WITH LABEL' : 'DOES NOT INCREASE WITH LABEL',
      `${rows.length} version(s)${comparable ? ', in label order' : ', in the order answered'}: `
      + `${byLabel.map((p) => `${p.label}=${show(p.id)}`).join(', ')}`);
  };

  // A file's content goes as text, so the body is never JSON-encoded as spPost would.
  const sendText = async (path, text, extraHeaders = {}) => {
    const res = await fetch(`${WEB}/_api/${path}`, { method: 'POST', body: text, headers: {
      Accept: 'application/json;odata=nometadata', 'X-RequestDigest': await getDigest(), ...extraHeaders } });
    return { ok: res.ok, status: res.status, text: await res.text() };
  };
  const answered = (res) => `HTTP ${res.status}`;
  const is2xx = (v) => /^HTTP 2\d\d$/.test(v);

  // The library case: a file in a folder, a property edit, a content-only upload, then another edit.
  const libraryCase = async () => {
    const library = await claimScratchList({ id: LIB.library, question: Q.library, title: LIBRARY,
      description: LIBRARY_OWNERSHIP, dependents: afterLib(LIB.library), baseTemplate: 101,
      settings: { EnableVersioning: true },
      declared: { EnableVersioning: true, EnableMinorVersions: false,
        ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 } });
    if (!library.held) return;
    const itemType = library.body.ListItemEntityTypeFullName;

    const choice = COLUMNS.find((column) => column.kind === 'choice').body;
    const made = await spPost(`${libraryPath}/fields`, { ...choice, Title: LIB_COLUMN, Required: false },
      await getDigest(), VERBOSE_WRITE);
    log('INFO', `create ${LIB_COLUMN}: HTTP ${made.status}${made.ok ? '' : ` ${scrub(made.text).slice(0, 200)}`}`);
    if (!await establishFixture(LIB.libraryColumn, async () => {
      const read = await readBack(`${libraryPath}/fields/getbyinternalnameortitle('${LIB_COLUMN}')`
        + '?$select=InternalName,TypeAsString');
      return { ok: true, status: 200, body: { Read: read.read,
        TypeAsString: read.parsed ? read.parsed.TypeAsString : undefined } };
    }, { Read: 'HTTP 200', TypeAsString: 'Choice' }, afterLib(LIB.libraryColumn))) {
      return;
    }

    let folder = null;
    if (!await establishFixture(LIB.libraryFolder, async () => {
      const root = await readBack(`${libraryPath}/RootFolder?$select=ServerRelativeUrl`);
      if (!root.parsed || typeof root.parsed.ServerRelativeUrl !== 'string') {
        return { ok: true, status: 200, body: { RootRead: root.read } };
      }
      folder = `${root.parsed.ServerRelativeUrl}/${FOLDER_NAME}`;
      const sent = await spPost('web/folders', { __metadata: { type: 'SP.Folder' }, ServerRelativeUrl: folder },
        await getDigest(), VERBOSE_WRITE);
      log('INFO', `create folder ${FOLDER_NAME}: HTTP ${sent.status}`);
      const read = await readBack(`web/GetFolderByServerRelativeUrl('${folder}')?$select=Name,ServerRelativeUrl`);
      return { ok: true, status: 200, body: { RootRead: root.read, Read: read.read,
        Name: read.parsed ? read.parsed.Name : undefined } };
    }, { RootRead: 'HTTP 200', Read: 'HTTP 200', Name: FOLDER_NAME }, afterLib(LIB.libraryFolder))) {
      return;
    }

    const file = `${folder}/${FILE_NAME}`;
    let fileId = null;
    const added = await sendText(`web/GetFolderByServerRelativeUrl('${folder}')/Files/add(url='${FILE_NAME}',`
      + 'overwrite=false)', CONTENT[0]);
    if (!await establishFixture(LIB.libraryFile, async () => {
      const read = await readBack(`web/GetFileByServerRelativeUrl('${file}')/ListItemAllFields?$select=Id`);
      if (read.parsed && Number.isInteger(read.parsed.Id)) fileId = read.parsed.Id;
      return { ok: true, status: 200, body: { Added: answered(added), Read: read.read,
        Id: read.parsed ? read.parsed.Id : undefined } };
    }, { Added: is2xx, Read: 'HTTP 200', Id: (v) => Number.isInteger(v) && v > 0 }, afterLib(LIB.libraryFile))) {
      return;
    }

    const itemPath = `${libraryPath}/items(${fileId})`;
    const choiceNow = async () => {
      const read = await readBack(`${itemPath}?$select=Id,${LIB_COLUMN}`);
      return { Read: read.read, [LIB_COLUMN]: read.parsed ? read.parsed[LIB_COLUMN] : undefined };
    };
    const edit = async (id, value) => {
      const sent = await spPost(itemPath, { __metadata: { type: itemType }, [LIB_COLUMN]: value },
        await getDigest(), { ...VERBOSE_WRITE, 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
      return establishFixture(id, async () => ({ ok: true, status: 200,
        body: { Written: answered(sent), ...await choiceNow() } }),
      { Written: is2xx, Read: 'HTTP 200', [LIB_COLUMN]: value }, afterLib(id));
    };
    if (!await edit(LIB.libraryFirst, 'Q1')) return;
    // The upload's version is what the reads either side of it differ by, never a value it holds.
    const beforeUpload = await readVersions(libraryPath, fileId);
    const uploaded = await sendText(`web/GetFileByServerRelativeUrl('${file}')/$value`, CONTENT[1],
      { 'X-HTTP-Method': 'PUT' });
    // The read must carry the Choice, but its value is observed, never declared: the upload's version is asked.
    let afterUpload;
    if (!await establishFixture(LIB.libraryUpload, async () => {
      const res = await fetch(`${WEB}/_api/web/GetFileByServerRelativeUrl('${file}')/$value`);
      const content = res.ok ? await res.text() : `HTTP ${res.status}`;
      const now = await choiceNow();
      afterUpload = now[LIB_COLUMN];
      return { ok: true, status: 200, body: { Uploaded: answered(uploaded), Content: content, ...now } };
    }, { Uploaded: is2xx, Content: CONTENT[1], Read: 'HTTP 200', [LIB_COLUMN]: () => true },
    afterLib(LIB.libraryUpload))) {
      return;
    }
    const afterUploadRead = await readVersions(libraryPath, fileId);
    if (!await edit(LIB.librarySecond, 'Q2')) return;

    const versions = await readVersions(libraryPath, fileId);
    if (!recordVersionsRead(LIB.libraryRead, Q.libraryRead, versions, [LIB.libraryAdds, LIB.libraryFields],
      'library versions read')) {
      return;
    }

    if (versions.next !== null) {
      record(LIB.libraryAdds, Q.libraryAdds, 'NOT COMPARABLE', pagedSaid(versions), 'open');
      record(LIB.libraryFields, Q.libraryFields, 'NOT COMPARABLE', pagedSaid(versions), 'open');
      return;
    }
    const rows = versions.rows;
    const ordered = rows.every((row) => labelPair(row) !== null)
      ? [...rows].sort((a, b) => labelPair(a)[0] - labelPair(b)[0] || labelPair(a)[1] - labelPair(b)[1]) : rows;
    const sequence = ordered.map((row) => `${labelOf(row)}=${show(row[LIB_COLUMN])}`).join(', ');
    const after = `after the second edit, ${ordered === rows ? 'in the order answered' : 'in label order'}: `
      + sequence;
    // Why the reads either side of the upload cannot be compared, or null when they can.
    const unread = (read, when) => {
      if (read.head || read.rows === null) {
        return { head: 'NOT ESTABLISHED', state: 'open', why: `the versions read ${when} the upload `
          + `${read.head ? `was not answered: ${scrub(read.head.why)}` : `answered HTTP ${read.res.status} `
            + 'with no value array'}; a re-run can ask it` };
      }
      if (read.next !== null) {
        return { head: 'NOT COMPARABLE', state: 'open', why: `the versions read ${when} the upload: ${pagedSaid(read)}` };
      }
      return read.rows.some((row) => versionIdOf(row) === null) ? { head: 'NOT COMPARABLE', state: undefined,
        why: `the versions read ${when} the upload answered an entry with no VersionId` } : null;
    };
    const blocked = unread(beforeUpload, 'before') || unread(afterUploadRead, 'after');
    if (blocked) {
      record(LIB.libraryAdds, Q.libraryAdds, blocked.head, `${blocked.why}; ${after}`, blocked.state);
      // An open reason (unanswered, or a continuation link) heads both rows alike, as the final read's does.
      record(LIB.libraryFields, Q.libraryFields, blocked.state === 'open' ? blocked.head : 'NOT IDENTIFIED',
        `the upload's version was not looked for: ${blocked.why}`, blocked.state);
      return;
    }
    // A VersionId and VersionLabel together name an entry, so a renumbered one reads as gone, never as kept.
    const keyOf = (row) => JSON.stringify([versionIdOf(row), row.VersionLabel]);
    const listed = (entries) => entries.map((row) => `${labelOf(row)}=${show(versionIdOf(row))}`).join(', ');
    const had = new Set(beforeUpload.rows.map(keyOf));
    const kept = new Set(afterUploadRead.rows.map(keyOf));
    const fresh = afterUploadRead.rows.filter((row) => !had.has(keyOf(row)));
    const lost = beforeUpload.rows.filter((row) => !kept.has(keyOf(row)));
    const head = lost.length ? 'NOT COMPARABLE' : !fresh.length ? 'UPLOAD ADDED NO VERSION'
      : fresh.length === 1 ? 'UPLOAD ADDED A VERSION' : 'UPLOAD ADDED MORE THAN ONE VERSION';
    record(LIB.libraryAdds, Q.libraryAdds, head, `before the upload ${beforeUpload.rows.length} version(s) `
      + `(${listed(beforeUpload.rows)}), after it ${afterUploadRead.rows.length} (${listed(afterUploadRead.rows)}); `
      + `new: ${listed(fresh) || 'none'}${lost.length ? `; gone: ${listed(lost)}` : ''}; `
      + `${LIB_COLUMN} read ${show(afterUpload)} after the upload; ${after}`);
    const upload = head === 'UPLOAD ADDED A VERSION' ? fresh[0] : null;
    record(LIB.libraryFields, Q.libraryFields, upload ? 'OBSERVED' : 'NOT IDENTIFIED', upload
      ? `${labelOf(upload)} carries: ${Object.keys(upload).sort().map((key) => `${key}=${show(upload[key])}`)
        .join('; ')}`.slice(0, 1500)
      : `no version is the upload's alone (${head})`);
  };

  try {
    if (!await establishFixture('field.version.control-current-user', async () => {
      const me = await readBack('web/currentuser?$select=Id,Email,LoginName,Title');
      if (!me.parsed) return { ok: true, status: 200, body: { Read: me.read } };
      knowIdentity(me.parsed.Email, '<account>');
      knowIdentity(me.parsed.LoginName, '<account>');
      knowIdentity(me.parsed.Title, '<name>', true);
      meId = me.parsed.Id;
      return { ok: true, status: 200, body: { Read: me.read, Id: me.parsed.Id } };
    }, { Read: 'HTTP 200', Id: (v) => Number.isInteger(v) && v > 0 }, AFTER_USER)) {
      return;
    }

    await listCase();
    await libraryCase();
  } catch (err) {
    log('FAIL', `probe aborted: ${scrub(String((err && err.message) || err)).slice(0, 240)}. `
      + 'The unasked rows stay open.');
  } finally {
    await recycleScratchLists();
    // Reported here, after the recycle, so every path prints the recycle line above the table.
    report();
  }
})();
