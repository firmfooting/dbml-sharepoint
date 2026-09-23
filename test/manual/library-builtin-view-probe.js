/**
 * dbml-sharepoint PROBE: THE VIEW ALREADY SITTING ON AllItems.aspx
 *
 * REVISION: 68554a4f
 *
 * ONE QUESTION:
 *   A library ships with a built-in view. The deploy's generated All Items
 *   view is created at AllItems.aspx and cannot land there. What is the
 *   view already on that URL, and can the deploy adopt it instead?
 *
 * MEASURED on a live deploy 2026-09-13: Phase 3.1 created the generated
 * All Items view on a document library and the URL drift gate failed it
 * closed, "declared AllItems.aspx; readback AllItems1.aspx". The same
 * phase on a generic list in the same run ADOPTED its built-in All Items
 * and wrote no new page. The asymmetry is the whole question.
 *
 * `templates/deploy/_views.js.j2` finds an existing view by TITLE
 * (case-insensitively), plus declared `renamed_from` titles, plus a
 * half-migrated view titled with the URL slug. A library's built-in view
 * matches none of those, so it is FOREIGN to that matcher, and the comment
 * above the match says what then happens: "the create below would get a
 * suffixed .aspx and the URL drift gate fails the view closed". It did.
 *
 * The built-in view's TITLE is exactly the value this probe must not
 * assume. It is read and printed, never asserted, because a tenant or a
 * locale that answers differently would otherwise look like a refusal.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101). Same question
 *     folder-probe.js asks, by the same method, so it keeps the same id.
 *   library.view.builtin-view-inventory
 *     OBSERVATION: every view a bare library ships with, by Title, URL
 *     basename, DefaultView, Hidden and Scope. This is the row the fix is
 *     designed from.
 *   library.view.builtin-occupies-allitems
 *     Is AllItems.aspx already taken on a bare library?
 *   library.view.control-list-builtin-occupies-allitems
 *     CONTROL: the same two readings on a generic list (BaseTemplate 100),
 *     which is the shape the deploy already adopts. If a list answers the
 *     same way a library does, the live asymmetry has another cause and
 *     nothing below explains it.
 *   library.view.create-allitems-title-on-library
 *     Creating a view titled 'AllItems' on the bare library, which is
 *     exactly what Phase 3.1 sends: what basename is minted? This
 *     reproduces the live failure on a library nothing else has touched.
 *   library.view.builtin-title-rename
 *     Can the built-in view's Title be MERGEd, and does its URL stay put?
 *     Adoption renames, so this is the first thing a fix needs.
 *   library.view.builtin-getbytitle-after-rename
 *     Does views/getbytitle resolve the renamed view? Every write in Phase
 *     3.1 after the rename addresses the view by its declared title.
 *   library.view.builtin-scope-merge
 *     Can Scope 1 be MERGEd onto the built-in view? A library's generated
 *     All Items is recursive.
 *   library.view.builtin-viewfields-replace
 *     Can its ViewFields be emptied and rebuilt? Adoption reconciles the
 *     declared field list onto whatever the view already renders.
 *   library.view.builtin-hidden-while-default
 *     Can Hidden be set on the built-in view while it is still the default?
 *   library.view.builtin-hidden-once-not-default
 *     The same MERGE once another view holds DefaultView. This is the state
 *     the deploy is actually in: an authored default is written first and
 *     the generated All Items is hidden behind it.
 *   library.view.builtin-delete-once-not-default
 *     Can the built-in view be DELETED once it is not the default? This is
 *     the alternative fix, and the URL-migration path in Phase 3.1 already
 *     deletes a view to move it. Measured last, because it destroys the
 *     subject of every row above.
 *
 * OBSERVED, NEVER ASSERTED
 *   The built-in view's Title, its basename, and the basename minted for a
 *   colliding create. Those three values are the finding. Asserting any of
 *   them would make this probe fail on the tenant it was written to measure.
 *
 * NOT MEASURED HERE
 *   What the library page renders for a renamed or hidden built-in view,
 *   and whether anybody's saved link to the old page still resolves. Both
 *   are consequences of the fix rather than inputs to it.
 *
 * MICROSOFT LEARN CITATIONS
 *   View creation, Title, Hidden, DefaultView, ViewQuery, RowLimit:
 *     "SP.View properties", "Working with lists and list items with REST"
 *   View field collection, removeallviewfields / addviewfield:
 *     "ViewFieldCollection methods" (CSOM), mirrored on the REST surface
 *   SP.View.Scope and folder scope:
 *     "ViewScope enumeration" (CSOM)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the library and the list it created.
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

  log('INFO', 'probe revision 68554a4f. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe Builtin View';
  const LIST = 'dbmlsp Probe Builtin View List';
  const libPath = `web/lists/getbytitle('${LIB}')`;
  const listPath = `web/lists/getbytitle('${LIST}')`;
  // The title Phase 3.1 creates under. The deploy creates every view with
  // Title set to the URL slug and renames afterwards, so the .aspx name is
  // minted from this and not from the declared display title.
  const SLUG = 'AllItems';
  const DECLARED = 'All Items';
  const OTHER = 'dbmlsp Other View';

  const Q = {
    fixture: 'A document library is created (BaseTemplate 101)',
    inventory: 'OBSERVATION: which views does a bare document library ship with',
    occupies: 'Is AllItems.aspx already occupied on a bare document library',
    controlList: 'CONTROL: is AllItems.aspx occupied on a generic list, and under which Title',
    collide: "Creating a view titled 'AllItems' on the bare library, which .aspx basename is minted",
    rename: "Can the built-in view's Title be MERGEd, and does its URL stay unchanged",
    getByTitle: 'Does views/getbytitle resolve the built-in view under its new Title',
    scope: 'Can Scope 1 be MERGEd onto the built-in view, and does it read back',
    viewFields: "Can the built-in view's ViewFields be emptied and rebuilt",
    hiddenDefault: 'Can Hidden be set on the built-in view while it still holds DefaultView',
    hiddenNotDefault: 'Can Hidden be set on the built-in view once another view holds DefaultView',
    del: 'Can the built-in view be DELETED once it is not the default',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' and a LIST '${LIST}' on ${WEB},`);
    log('INFO', 'read every view each ships with, then try to create a view titled');
    log('INFO', `'${SLUG}' on the library to reproduce the live URL collision.`);
    log('INFO', 'It then renames, rescopes, refields, hides and finally DELETES the');
    log('INFO', "library's built-in view, to measure whether the deploy could adopt it.");
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' and '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: existing fixtures would be reused, and a built-in view');
      log('INFO', 'a previous run already renamed answers nothing. Set CLEANUP = true.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  const IDS = [
    'library.view.builtin-view-inventory',
    'library.view.builtin-occupies-allitems',
    'library.view.control-list-builtin-occupies-allitems',
    'library.view.create-allitems-title-on-library',
    'library.view.builtin-title-rename',
    'library.view.builtin-getbytitle-after-rename',
    'library.view.builtin-scope-merge',
    'library.view.builtin-viewfields-replace',
    'library.view.builtin-hidden-while-default',
    'library.view.builtin-hidden-once-not-default',
    'library.view.builtin-delete-once-not-default',
  ];

  expect('library.doc-lib.fixture-library-created', Q.fixture);
  expect('library.view.builtin-view-inventory', Q.inventory);
  expect('library.view.builtin-occupies-allitems', Q.occupies);
  expect('library.view.control-list-builtin-occupies-allitems', Q.controlList);
  expect('library.view.create-allitems-title-on-library', Q.collide);
  expect('library.view.builtin-title-rename', Q.rename);
  expect('library.view.builtin-getbytitle-after-rename', Q.getByTitle);
  expect('library.view.builtin-scope-merge', Q.scope);
  expect('library.view.builtin-viewfields-replace', Q.viewFields);
  expect('library.view.builtin-hidden-while-default', Q.hiddenDefault);
  expect('library.view.builtin-hidden-once-not-default', Q.hiddenNotDefault);
  expect('library.view.builtin-delete-once-not-default', Q.del);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 220)}`;
  const basename = (v) => String((v && v.ServerRelativeUrl) || '').split('/').pop();
  const odataName = (s) => String(s).replace(/'/g, "''");
  const isAllItems = (v) => basename(v).toLowerCase() === `${SLUG}.aspx`.toLowerCase();

  // A view MERGE needs the verbose spelling: the harness posts
  // `odata=nometadata`, under which the server reads the body as an
  // untyped entity and refuses SP.View's own properties. The deploy sends
  // `__metadata` on every view write, so the probe does too, and what is
  // measured is the surface and not a transport this project never uses.
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const postVerbose = async (path, body, extraHeaders = {}) => {
    const digest = await getDigest();
    const res = await fetch(`${WEB}/_api/${path}`, {
      method: 'POST',
      headers: { ...VERBOSE, 'X-RequestDigest': digest, ...extraHeaders },
      body: body === null ? undefined : JSON.stringify(body),
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };
  const MERGE = { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' };
  const DELETE = { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' };

  const VIEW_SELECT = '$select=Id,Title,ServerRelativeUrl,DefaultView,Hidden,Scope,PersonalView';
  const readViews = async (path) => {
    const r = await spGet(`${path}/views?${VIEW_SELECT}&$top=50`);
    if (readFailed(r)) return null;
    return (r.body.value || []).filter((v) => !v.PersonalView);
  };
  const describe = (v) => `'${v.Title}' at ${basename(v)}`
    + ` (DefaultView ${v.DefaultView}, Hidden ${v.Hidden}, Scope ${v.Scope})`;

  await resetList(LIB);
  await resetList(LIST);

  // ---- fixtures --------------------------------------------------------
  {
    const existing = await spGet(libPath);
    if (existing.ok) {
      record('library.doc-lib.fixture-library-created', Q.fixture, 'ALREADY PRESENT',
             'reusing an existing library, so its built-in view may already carry a '
             + "previous run's writes. Set CLEANUP = true for a clean answer.");
    } else {
      const digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: LIB,
        BaseTemplate: 101,
        Description: 'dbml-sharepoint built-in view probe. Safe to delete.',
        ContentTypesEnabled: false,
      }, digest);
      record('library.doc-lib.fixture-library-created', Q.fixture,
             made.ok ? 'PASS' : 'FAIL',
             made.ok ? `created '${LIB}'` : short(made));
      if (!made.ok) {
        voidAll(IDS, 'the library fixture did not build, so it has no views to read.');
        return report();
      }
    }
  }

  // ---- the inventory, which is the finding ------------------------------
  const libViews = await readViews(libPath);
  if (!libViews) {
    voidAll(IDS, 'the library view collection did not read back, so nothing below could be asked.');
    return report();
  }
  record('library.view.builtin-view-inventory', Q.inventory, 'OBSERVED',
         `${libViews.length} public view(s): ${libViews.map(describe).join('; ')}`);

  // Only the view actually on that URL. Falling back to the default view
  // would aim every adoption write below at a page nobody asked about.
  const builtin = libViews.find(isAllItems) || null;
  record('library.view.builtin-occupies-allitems', Q.occupies,
         builtin ? 'OCCUPIED' : 'FREE',
         builtin ? `the view on that URL is ${describe(builtin)}`
                 : `no public view on a bare library reports ${SLUG}.aspx`);

  // ---- control: the same reading on a generic list ----------------------
  {
    let listOk = (await spGet(listPath)).ok;
    if (!listOk) {
      const digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: LIST,
        BaseTemplate: 100,
        Description: 'dbml-sharepoint built-in view probe control. Safe to delete.',
      }, digest);
      listOk = made.ok;
      if (!made.ok) {
        record('library.view.control-list-builtin-occupies-allitems', Q.controlList,
               'NOT ESTABLISHED', `the control list did not build: ${short(made)}`, 'void');
      }
    }
    if (listOk) {
      const listViews = await readViews(listPath);
      if (!listViews) {
        record('library.view.control-list-builtin-occupies-allitems', Q.controlList,
               'NOT ESTABLISHED', 'the control list view collection did not read back', 'void');
      } else {
        const onUrl = listViews.find(isAllItems);
        record('library.view.control-list-builtin-occupies-allitems', Q.controlList,
               onUrl ? 'OCCUPIED' : 'FREE',
               `${listViews.length} public view(s): ${listViews.map(describe).join('; ')}`);
      }
    }
  }

  // ---- reproduce the live collision ------------------------------------
  {
    const made = await postVerbose(`${libPath}/views`, {
      __metadata: { type: 'SP.View' },
      Title: SLUG,
      PersonalView: false,
      Paged: true,
    });
    if (!made.ok) {
      record('library.view.create-allitems-title-on-library', Q.collide, 'REFUSED',
             `the create itself was refused: ${short(made)}`);
    } else {
      const after = await readViews(libPath);
      const mine = (after || []).find((v) => v.Title === SLUG) || null;
      const got = mine ? basename(mine) : null;
      // SUFFIXED is a basename this run SAW, so a create nothing read back
      // answers nothing. The live adoption rule cites this row.
      if (!got) {
        record('library.view.create-allitems-title-on-library', Q.collide, 'NOT ESTABLISHED',
               (after ? `the create answered OK but no view titled '${SLUG}' read back`
                      : 'the create answered OK but the view collection did not read back')
               + ', so no basename was observed');
      } else {
        record('library.view.create-allitems-title-on-library', Q.collide,
               isAllItems(mine) ? 'LANDED' : 'SUFFIXED',
               `a view titled '${SLUG}' was minted at ${got}`);
      }
    }
  }

  if (!builtin) {
    voidAll(IDS.slice(4),
            `no public view holds ${SLUG}.aspx, so none of the adoption writes below had `
            + 'the view this probe asks about to aim at.');
    return report();
  }

  const builtinUrl = `${libPath}/views('${builtin.Id}')`;
  const reread = async () => {
    const r = await spGet(`${builtinUrl}?${VIEW_SELECT}`);
    return readFailed(r) ? null : r.body;
  };

  // ---- can the deploy adopt it? -----------------------------------------
  // The getbytitle row below asks about a view under its NEW title, so a
  // rename that never took leaves it measuring the unmet prerequisite.
  let renamedTitle = false;
  {
    const merged = await postVerbose(builtinUrl,
      { __metadata: { type: 'SP.View' }, Title: DECLARED }, MERGE);
    const after = merged.ok ? await reread() : null;
    const moved = after && basename(after) !== basename(builtin);
    renamedTitle = Boolean(merged.ok && after && after.Title === DECLARED);
    record('library.view.builtin-title-rename', Q.rename,
           renamedTitle && !moved ? 'PASS' : 'FAIL',
           !merged.ok ? short(merged)
             : !after ? 'the MERGE answered but the view did not read back'
             : `Title reads ${JSON.stringify(after.Title)}, URL ${basename(after)}`
               + ` (was ${basename(builtin)})`);
  }

  if (!renamedTitle) {
    record('library.view.builtin-getbytitle-after-rename', Q.getByTitle, 'NOT ESTABLISHED',
           `the view did not read back under ${JSON.stringify(DECLARED)}, so a getbytitle `
           + 'result here would report the failed rename rather than the lookup.', 'void');
  } else {
    const r = await spGet(`${libPath}/views/getbytitle('${odataName(DECLARED)}')?${VIEW_SELECT}`);
    record('library.view.builtin-getbytitle-after-rename', Q.getByTitle,
           !readFailed(r) && r.body.Id === builtin.Id ? 'PASS' : 'FAIL',
           readFailed(r) ? short(r)
             : `resolved to ${describe(r.body)}, `
               + `${r.body.Id === builtin.Id ? 'the same view' : 'a DIFFERENT view'}`);
  }

  {
    const merged = await postVerbose(builtinUrl,
      { __metadata: { type: 'SP.View' }, Scope: 1 }, MERGE);
    const after = merged.ok ? await reread() : null;
    record('library.view.builtin-scope-merge', Q.scope,
           merged.ok && after && after.Scope === 1 ? 'PASS' : 'FAIL',
           !merged.ok ? short(merged)
             : !after ? 'the MERGE answered but the view did not read back'
             : `Scope reads ${after.Scope}`);
  }

  {
    const WANTED = ['FileLeafRef'];
    const cleared = await postVerbose(`${builtinUrl}/ViewFields/removeallviewfields`, null);
    const added = cleared.ok
      ? await postVerbose(`${builtinUrl}/ViewFields/addviewfield('${WANTED[0]}')`, null)
      : null;
    const fields = await spGet(`${builtinUrl}/ViewFields?$select=Items`);
    const raw = readFailed(fields) ? null : fields.body.Items;
    const names = raw && raw.results ? raw.results : (Array.isArray(raw) ? raw : null);
    // The names asked for, in that order. A count alone reads a surviving
    // field as the one this run added.
    const exact = Boolean(names) && names.length === WANTED.length
      && WANTED.every((want, i) => names[i] === want);
    record('library.view.builtin-viewfields-replace', Q.viewFields,
           cleared.ok && added && added.ok && exact ? 'PASS' : 'FAIL',
           !cleared.ok ? `removeallviewfields: ${short(cleared)}`
             : !added || !added.ok ? `addviewfield: ${short(added || cleared)}`
             : `ViewFields now ${JSON.stringify(names)}`
               + (exact ? '' : `, not the requested ${JSON.stringify(WANTED)}`));
  }

  // The second hidden row starts from a visible view, so a restore that only
  // answered OK would let that row read the state this one left behind.
  let visibleAgain = true;
  {
    const merged = await postVerbose(builtinUrl,
      { __metadata: { type: 'SP.View' }, Hidden: true }, MERGE);
    const after = merged.ok ? await reread() : null;
    const hidden = Boolean(merged.ok && after && after.Hidden === true);
    // The question is Hidden WHILE default, so a view that stopped being the
    // default answers the next row's question rather than this one's.
    const stillDefault = Boolean(after && after.DefaultView === true);
    record('library.view.builtin-hidden-while-default', Q.hiddenDefault,
           hidden && stillDefault ? 'PASS' : hidden ? 'NOT ESTABLISHED' : 'REFUSED',
           !merged.ok ? short(merged)
             : !after ? 'the MERGE answered but the view did not read back'
             : `Hidden reads ${after.Hidden}, DefaultView ${after.DefaultView}`
               + (hidden && !stillDefault
                  ? '; the MERGE took but DefaultView moved off it, so this is not the'
                    + ' state the question names'
                  : ''));
    // Put it back, so the next row measures its own MERGE and not this one.
    if (merged.ok) {
      const back = await postVerbose(builtinUrl,
        { __metadata: { type: 'SP.View' }, Hidden: false }, MERGE);
      const now = back.ok ? await reread() : null;
      visibleAgain = Boolean(back.ok && now && now.Hidden === false);
    }
  }

  // ---- move DefaultView off it, then the same write ---------------------
  {
    const made = await postVerbose(`${libPath}/views`, {
      __metadata: { type: 'SP.View' },
      Title: OTHER,
      PersonalView: false,
      Paged: true,
    });
    let promoted = false;
    if (made.ok) {
      const other = (await readViews(libPath) || []).find((v) => v.Title === OTHER);
      if (other) {
        const set = await postVerbose(`${libPath}/views('${other.Id}')`,
          { __metadata: { type: 'SP.View' }, DefaultView: true }, MERGE);
        const check = await reread();
        promoted = set.ok && check && check.DefaultView === false;
      }
    }
    if (!promoted) {
      const reason = 'DefaultView could not be moved off the built-in view, so the two '
        + "rows below would measure the default state again rather than the deploy's.";
      record('library.view.builtin-hidden-once-not-default', Q.hiddenNotDefault,
             'NOT ESTABLISHED', reason, 'void');
      record('library.view.builtin-delete-once-not-default', Q.del,
             'NOT ESTABLISHED', reason, 'void');
      return report();
    }

    if (!visibleAgain) {
      record('library.view.builtin-hidden-once-not-default', Q.hiddenNotDefault,
             'NOT ESTABLISHED',
             'Hidden did not read back false after the row above, so a MERGE that did '
             + 'nothing would still read back true here.', 'void');
    } else {
      const merged = await postVerbose(builtinUrl,
        { __metadata: { type: 'SP.View' }, Hidden: true }, MERGE);
      const after = merged.ok ? await reread() : null;
      record('library.view.builtin-hidden-once-not-default', Q.hiddenNotDefault,
             merged.ok && after && after.Hidden === true ? 'PASS' : 'REFUSED',
             !merged.ok ? short(merged)
               : !after ? 'the MERGE answered but the view did not read back'
               : `Hidden reads ${after.Hidden}, DefaultView ${after.DefaultView}`);
    }
  }

  // ---- last, because it destroys the subject of every row above ---------
  {
    const gone = await postVerbose(builtinUrl, null, DELETE);
    // The status is kept rather than folded into reread()'s null, because
    // absence is what proves a delete and a 500 or a throttle proves nothing.
    const after = await spGet(`${builtinUrl}?${VIEW_SELECT}`);
    const present = !readFailed(after);
    const absent = after.status === 404;
    const views = await readViews(libPath);
    const stillThere = (views || []).some(isAllItems);
    record('library.view.builtin-delete-once-not-default', Q.del,
           !gone.ok || present ? 'REFUSED'
             : absent && views ? 'PASS'
             : 'NOT ESTABLISHED',
           !gone.ok ? short(gone)
             : present ? 'the DELETE answered OK but the view still reads back'
             : !absent ? 'the DELETE answered OK but the view neither read back nor read '
                         + `as absent (HTTP ${after.status}), so it was not observed to be gone`
             : !views ? 'the view is gone, but the view collection did not read back, so '
                        + `whether ${SLUG}.aspx is free was not observed`
             : `deleted; ${SLUG}.aspx is ${stillThere ? 'STILL occupied' : 'now free'}`);
  }

  return report();
})();
