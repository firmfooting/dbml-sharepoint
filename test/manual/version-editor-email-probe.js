
/** ---- dbml-sharepoint PROBE: WHICH ADDRESS A VERSION'S EDITOR CARRIES ----
 *
 * REVISION: e7f52f83
 *
 * QUESTION: for a user whose sign-in name (UserPrincipalName) differs from
 * their email address, which of the two does `Editor.Email` carry on an
 * entry of `items(id)/versions`? And does a person column's value in the
 * same version carry the same string for the same user?
 *
 * WHY: a flow that alerts on item changes reads who made each change from a
 * version's Editor, and compares it with addresses an operator configured
 * and with a person column on the item. Those addresses must be spelled the
 * way the Editor spells them, and Learn does not say which spelling that is.
 *
 * DEPENDS ON (read back, and voiding what rests on them when they do not hold)
 *   field.version.fixture-editor-list          the list reads back the probe's ownership
 *       Description, EnableVersioning true and an item type; on setup, any list of
 *       that title stood before the run is recycled first only if it carries the
 *       marker and CLEANUP is on, and is otherwise left alone
 *   field.version.fixture-editor-person-write  item 1's person column holds a user Id
 *       (on setup, the item the create answered is item 1 and holds the Id
 *       ensureuser answered for SECOND_ACCOUNT)
 *   field.version.fixture-editor-distinct-names  that user's Email and UserPrincipalName
 *       are both set and differ, ignoring case
 *   field.version.control-editor-versions-read  a plain versions read of item 1
 *       answers at least two entries
 *
 * OBSERVES (recorded as a relation and key names, never an address)
 *   field.version.editor-email-sign-in         EMAIL, SIGN-IN NAME, NEITHER or ABSENT,
 *       over every version whose Editor is that user (MIXED if they disagree)
 *   field.version.person-email-matches-editor  SAME, SAME IGNORING CASE or DIFFERS,
 *       comparing the person column's Email with the Editor's in those versions
 *
 * HOW TO READ IT: EMAIL means configured addresses must be email addresses;
 * SIGN-IN NAME means they must be sign-in names. NOT ESTABLISHED on the
 * question with no void means no version answered was edited by that user:
 * do the manual step and run the report again.
 *
 * HOW TO RUN: F12 -> Console on a site you own, paste, Enter; it prints its
 * plan and stops. Then:
 *   1. Set SECOND_ACCOUNT to the sign-in name of an account whose sign-in
 *      name differs from its email address. Never commit it.
 *   2. Set CONFIRMED and ALLOW_WRITES to true and MODE = 'setup'; paste.
 *   3. Sign in as the second account and change item 1's Title in the list.
 *   4. Back as yourself, set MODE = 'report' and paste again. Copy the
 *      RESULTS block back verbatim.
 * Set CLEANUP to true on a later setup run to recycle the previous list first;
 * a same-title list without this probe's Description is never touched.
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
  log('INFO', 'probe revision e7f52f83. Quote this when reporting results.');

  // ---- The question ----------------------------------------------------
  const MODE = 'setup'; // 'setup' first, then the second account edits, then 'report'
  // The second account's sign-in name, typed at paste time and never committed.
  const SECOND_ACCOUNT = '';
  const LIST = 'dbml-probe-version-editor';
  // Ownership is the Description, never the title: a same-title list this probe did not make is left alone.
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint version-editor-email probe scratch list. Safe to delete.';
  const PERSON_COLUMN = 'ProbePerson';
  const LIST_FIXTURE = 'field.version.fixture-editor-list';
  const PERSON_WRITE = 'field.version.fixture-editor-person-write';
  const DISTINCT = 'field.version.fixture-editor-distinct-names';
  const READ = 'field.version.control-editor-versions-read';
  const QUESTION = 'field.version.editor-email-sign-in';
  const PERSON = 'field.version.person-email-matches-editor';

  expect('field.version.fixture-editor-list', 'the list reads back with versioning on, its marker and an item type');
  expect('field.version.fixture-editor-person-write', 'the person column names the second account');
  expect('field.version.fixture-editor-distinct-names', "the editing user's email and sign-in name differ");
  expect('field.version.control-editor-versions-read', 'the versions read answers at least two versions');
  expect('field.version.editor-email-sign-in', "which address a version's Editor carries in Email");
  expect('field.version.person-email-matches-editor', "whether the person column's Email equals the Editor's for one user");

  if (!CONFIRMED || !ALLOW_WRITES || !SECOND_ACCOUNT) {
    log('INFO', `Would ${MODE === 'setup' ? `create '${LIST}' and name the second account in ${PERSON_COLUMN}` : `read the versions of '${LIST}' item 1`} on ${WEB}.`);
    log('INFO', 'Nothing has been sent. Set SECOND_ACCOUNT, CONFIRMED and ALLOW_WRITES.');
    return report();
  }

  const enc = (t) => encodeURIComponent(t.replace(/'/g, "''"));
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const post = async (path, payload, extra = {}) => spPost(path, payload, await getDigest(), { ...VERBOSE, ...extra });
  const reason = (r) => (r.body && r.body.error && r.body.error.message && r.body.error.message.value) || r.text.slice(0, 160);
  const said = (what, r) => log(r.ok ? 'INFO' : 'FAIL', `${what}: HTTP ${r.status}${r.ok ? '' : ` ${reason(r)}`}`);
  const lower = (v) => String(v ?? '').trim().toLowerCase();
  const keysOf = (v) => (v && typeof v === 'object' ? Object.keys(v).sort().join(', ') || 'none' : String(v));
  const listAt = `web/lists/getbytitle('${enc(LIST)}')`;
  const listRead = () => spGet(`${listAt}?$select=Title,Description,EnableVersioning,ListItemEntityTypeFullName`);
  const versioned = { Description: OWNERSHIP_DESCRIPTION, EnableVersioning: true,
    ListItemEntityTypeFullName: (v) => typeof v === 'string' && v.length > 0 };

  if (MODE === 'setup') {
    const refuse = (why) => {
      record(LIST_FIXTURE, 'the list reads back with versioning on, its marker and an item type', 'FAIL', why);
      voidDependents([PERSON_WRITE, DISTINCT, READ, QUESTION, PERSON], 'the list was not created by this run');
      return report();
    };
    // A by-title read answers an absent list 404; a standing one is recycled only if it carries the marker.
    const before = await spGet(`${listAt}?$select=Id,Description`);
    if (before.status !== 404) {
      if (!before.ok) return refuse(`could not tell whether '${LIST}' already stands: the read ${unanswered(before)}`);
      if (!before.body || before.body.Description !== OWNERSHIP_DESCRIPTION) {
        return refuse(`a list named '${LIST}' exists without this probe's ownership description; refusing to modify it`);
      }
      if (!CLEANUP) return refuse(`'${LIST}' from an earlier run already stands; set CLEANUP to true to recycle it first`);
      // By the Id read with the marker, so a title rebound since cannot redirect the deletes.
      if (!await resetList(LIST, String(before.body.Id).replace(/[{}]/g, ''))) {
        return refuse(`'${LIST}' from an earlier run could not be recycled`);
      }
      const after = await spGet(`${listAt}?$select=Id`);
      if (after.status !== 404) return refuse(`'${LIST}' still answers HTTP ${after.status} after the recycle`);
    }
    said('list create', await post('web/lists', { __metadata: { type: 'SP.List' }, Title: LIST,
      BaseTemplate: 100, Description: OWNERSHIP_DESCRIPTION }));
    said('versioning MERGE', await post(listAt, { __metadata: { type: 'SP.List' }, EnableVersioning: true },
      { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }));
    said('person column create', await post(`${listAt}/fields`, { __metadata: { type: 'SP.FieldUser' },
      Title: PERSON_COLUMN, FieldTypeKind: 20, SelectionMode: 0 }));
    let list = null;
    if (!await establishFixture(LIST_FIXTURE, async () => (list = await listRead()), versioned,
      [PERSON_WRITE, DISTINCT, READ, QUESTION, PERSON])) return report();
    const who = await post('web/ensureuser', { logonName: SECOND_ACCOUNT });
    // Status only: a refusal can quote the account it was given.
    log(who.ok ? 'INFO' : 'FAIL', `ensureuser for the second account: HTTP ${who.status}`);
    const id = who.body && who.body.d ? who.body.d.Id : null;
    const made = await post(`${listAt}/items`, { __metadata: { type: list.body.ListItemEntityTypeFullName },
      Title: 'dbml probe version editor', [`${PERSON_COLUMN}Id`]: id });
    said('item create', made);
    const itemId = made.body && made.body.d ? made.body.d.Id : null;
    // The report run reads item 1, so the item this run made must be item 1.
    if (!await establishFixture(PERSON_WRITE, () => (Number.isInteger(itemId)
      ? spGet(`${listAt}/items(${itemId})?$select=Id,${PERSON_COLUMN}Id`)
      : { ok: false, status: made.status, body: null }),
    { Id: 1, [`${PERSON_COLUMN}Id`]: (v) => Number.isInteger(id) && v === id }, [DISTINCT, QUESTION, PERSON])) {
      return report();
    }
    record(QUESTION, "which address a version's Editor carries", 'MANUAL',
      `sign in as the second account, change item 1's Title in '${LIST}', then run again with MODE = 'report'`);
    return report();
  }

  if (!await establishFixture(LIST_FIXTURE, listRead, versioned,
    [PERSON_WRITE, DISTINCT, READ, QUESTION, PERSON])) return report();
  let item = null;
  if (!await establishFixture(PERSON_WRITE,
    async () => (item = await spGet(`${listAt}/items(1)?$select=Id,${PERSON_COLUMN}Id`)),
    { [`${PERSON_COLUMN}Id`]: (v) => Number.isInteger(v) }, [DISTINCT, QUESTION, PERSON])) return report();
  const second = item.body[`${PERSON_COLUMN}Id`];

  const user = await spGet(`web/siteusers/getbyid(${second})?$select=Email,UserPrincipalName`);
  const email = lower(user.body && user.body.Email);
  const upn = lower(user.body && user.body.UserPrincipalName);
  if (unanswered(user) || !email || !upn || email === upn) {
    record(DISTINCT, "the editing user's names", 'NOT ESTABLISHED', unanswered(user)
      ? `the user read ${unanswered(user)}`
      : !email || !upn ? `the user read carried no Email or no UserPrincipalName (keys: ${keysOf(user.body)})`
        : 'email and sign-in name are the same; name a user whose differ');
    voidDependents([QUESTION, PERSON], 'the fixture user cannot tell the two names apart');
    return report();
  }
  record(DISTINCT, "the editing user's names", 'ESTABLISHED', 'email and sign-in name differ');

  // A plain read: whether versions honour $select is its own open question.
  const versions = await spGet(`${listAt}/items(1)/versions`);
  const entries = unanswered(versions) ? null : versions.body.value;
  if (!Array.isArray(entries) || entries.length < 2) {
    record(READ, 'the versions read', 'NOT ESTABLISHED', unanswered(versions)
      ? `the read ${unanswered(versions)}`
      : `answered ${Array.isArray(entries) ? entries.length : 'no list of'} version(s)`);
    voidDependents([QUESTION, PERSON], 'the versions read did not answer two versions');
    return report();
  }
  record(READ, 'the versions read', 'ESTABLISHED', `${entries.length} versions`);

  // Chosen by Editor, not by position: the order versions come back in is its own open question.
  const mine = entries.filter((v) => v && v.Editor && Number(v.Editor.LookupId) === second);
  if (!mine.length) {
    const why = 'no version answered has the person column\'s user as its Editor; sign in as that account, '
      + `edit item 1, and run the report again (Editor keys: ${[...new Set(entries.map((v) => keysOf(v && v.Editor)))].join(' | ')})`;
    record(QUESTION, "which address a version's Editor carries", 'NOT ESTABLISHED', why);
    record(PERSON, "the person column's Email against the Editor's", 'NOT ESTABLISHED', why);
    return report();
  }
  const headOf = (editor) => {
    const carried = lower(editor.Email);
    if (!('Email' in editor) || carried === '') return 'ABSENT';
    return carried === email ? 'EMAIL' : carried === upn ? 'SIGN-IN NAME' : 'NEITHER';
  };
  const heads = [...new Set(mine.map((v) => headOf(v.Editor)))];
  record(QUESTION, "which address a version's Editor carries", heads.length === 1 ? heads[0] : 'MIXED',
    `${mine.length} of ${entries.length} versions by that user, read as ${heads.join(', ')}; Editor keys: ${keysOf(mine[0].Editor)}`);

  if (heads.includes('ABSENT')) {
    record(PERSON, "the person column's Email against the Editor's", 'NOT ESTABLISHED',
      'a version by that user carries no Editor Email to compare');
    return report();
  }
  const values = mine.map((v) => v[PERSON_COLUMN]);
  if (!values.every((p) => p && typeof p === 'object' && 'Email' in p)) {
    record(PERSON, "the person column's Email against the Editor's", 'NOT ESTABLISHED',
      `a version carries no Email on ${PERSON_COLUMN} (keys: ${[...new Set(values.map(keysOf))].join(' | ')})`);
    return report();
  }
  // Compared only where the column names the same user as the Editor, in every version compared.
  if (!values.every((p) => Number(p.LookupId) === second)) {
    record(PERSON, "the person column's Email against the Editor's", 'NOT ESTABLISHED',
      `a version's ${PERSON_COLUMN} does not name the user item 1's person column holds now`);
    return report();
  }
  const exact = mine.every((v) => typeof v.Editor.Email === 'string' && v.Editor.Email === v[PERSON_COLUMN].Email);
  const folded = mine.every((v) => lower(v.Editor.Email) !== '' && lower(v.Editor.Email) === lower(v[PERSON_COLUMN].Email));
  record(PERSON, "the person column's Email against the Editor's",
    exact ? 'SAME' : folded ? 'SAME IGNORING CASE' : 'DIFFERS',
    `person keys: ${keysOf(values[0])}`);
  return report();
})();
