/**
 * dbml-sharepoint PROBE: WHAT A COLUMN DOES TO A STRING IT STORES
 *
 * REVISION: 4764f08b
 *
 * ONE QUESTION:
 *   A value written to an item's column and read straight back is compared
 *   byte for byte by both the seeds phase and the demo script. Which column
 *   shapes return the bytes they were given, and for one that does not, is
 *   the change reversible?
 *
 * MEASURED on a live run 2026-09-13: two demo rows failed their read-back on
 * a rich text column, and both differed only in a colon:
 *
 *   written   "...past due and not started: this is what the Overdue view..."
 *   read back "...past due and not started&#58; this is what the Overdue..."
 *
 * Four other rows on the same column passed, and they are the ones whose
 * prose has no colon. So the column stored a numeric character reference
 * for a character that needs no escaping in any markup, and a comparison
 * that is right about every other value called those two rows wrong.
 *
 * `xmlDecode` in `_formula_canonical.js.j2`, which is how a stored FORMULA
 * is compared, decodes the five NAMED entities and no numeric ones, so
 * reusing it here would not recover this. Whether a decode recovers the
 * written string exactly is the thing the fix depends on, and nothing here
 * has measured it.
 *
 * SCOPE AND QUESTIONS
 *   text.item-value.fixture-columns-created
 *     A scratch list with three columns: single-line Text, multi-line Note
 *     with RichText false, and multi-line Note with RichText true. Each
 *     shape is READ BACK from the field before anything is written to it,
 *     because every row below attributes an encoding to plain or to rich
 *     text, and a column that only carries the right NAME cannot support
 *     that attribution.
 *   text.item-value.single-line-roundtrip
 *     OBSERVATION: a battery of awkward characters written to a single-line
 *     Text column and read straight back, printed verbatim on both sides.
 *   text.item-value.plain-note-roundtrip
 *     OBSERVATION: the same battery on a multi-line Note, RichText false.
 *   text.item-value.rich-note-roundtrip
 *     OBSERVATION: the same battery on a multi-line Note, RichText true.
 *     This is the column the live failure was on.
 *   text.item-value.rich-note-colon
 *     The narrow question the live rows asked: does a bare colon read back
 *     as a colon?
 *   text.item-value.control-plain-note-colon
 *     CONTROL: the same colon on the plain Note. If it survives there and
 *     not on the rich one, RichText is the cause; if it is mangled on both,
 *     the fix cannot be scoped to rich text.
 *   text.item-value.rich-note-decode-recovers
 *     Decoding the readback's character references: does it recover the
 *     written string EXACTLY? A comparison can only be made canonical if it
 *     does, and a fix built on a decode that loses or adds a character
 *     would pass a value the column did not store.
 *   text.item-value.rich-note-encoding-idempotent
 *     The readback form written back as-is. Does it store unchanged, or
 *     encode a second time? A redeploy rewrites the declared value, so an
 *     encoding that compounds would drift further on every run.
 *
 * OBSERVED, NEVER ASSERTED
 *   Every readback string, printed whole. Which characters a column
 *   transforms IS the measurement, so a probe that asserted a list of them
 *   would fail on the tenant it was written to measure and would teach
 *   nothing about the ones it did not name.
 *
 * NOT MEASURED HERE
 *   What the rendered page shows for any of these values, and whether the
 *   rich text editor round-trips its own markup. The deploy writes through
 *   REST and compares what REST returns, which is the only surface its
 *   read-back can see.
 *
 * MICROSOFT LEARN CITATIONS
 *   Multi-line columns and the RichText flag:
 *     "SP.FieldMultiLineText properties" (CSOM)
 *   Item creation and field values over REST:
 *     "Working with lists and list items with REST"
 *   Character references in markup, for the decode this probe tries:
 *     W3C "Character references" (HTML), for `&#NN;` and `&#xNN;`
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back verbatim.
 *
 * WHEN FINISHED: delete the list it created.
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

  log('INFO', 'probe revision 4764f08b. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe Item Text';
  const listPath = `web/lists/getbytitle('${LIST}')`;
  const LINE = 'dbmlspLine';
  const PLAIN = 'dbmlspPlain';
  const RICH = 'dbmlspRich';

  // Prose, not a character table: the live failure was prose, and a value
  // written the way a seed is written is what the comparison has to survive.
  // Every character here appears in a shipped demo note or is a markup
  // special that would explain one.
  const BATTERY = 'Colon: semicolon; ampersand & less < greater > '
    + 'quote " apostrophe \' slash / hash # percent % plus + at @ dash - '
    + 'brackets [] braces {} parens () equals = question?';
  const COLON = 'before: after';

  const Q = {
    fixture: 'A list with a single-line Text, a plain Note and a rich Note is created',
    line: 'OBSERVATION: does a single-line Text column return the bytes it was given',
    plain: 'OBSERVATION: does a multi-line Note with RichText false return them',
    rich: 'OBSERVATION: does a multi-line Note with RichText true return them',
    colon: 'Does a bare colon read back as a colon from the rich Note',
    controlColon: 'CONTROL: does the same colon survive the PLAIN Note',
    decode: 'Does decoding the readback recover the written string exactly',
    idempotent: 'Written back as read, does the rich Note store it unchanged or encode again',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a LIST '${LIST}' on ${WEB} with three text columns,`);
    log('INFO', 'write a battery of awkward characters to each, read them back and');
    log('INFO', 'print both sides verbatim. One further item writes the readback form');
    log('INFO', 'again, to see whether an encoding compounds.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' would be RECYCLED first.`);
    } else {
      log('INFO', "CLEANUP is off: an existing list's columns would be reused only if");
      log('INFO', 'they read back with the declared shapes, and its rows would');
      log('INFO', 'accumulate either way. Set CLEANUP = true.');
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
    'text.item-value.single-line-roundtrip',
    'text.item-value.plain-note-roundtrip',
    'text.item-value.rich-note-roundtrip',
    'text.item-value.rich-note-colon',
    'text.item-value.control-plain-note-colon',
    'text.item-value.rich-note-decode-recovers',
    'text.item-value.rich-note-encoding-idempotent',
  ];

  expect('text.item-value.fixture-columns-created', Q.fixture);
  expect('text.item-value.single-line-roundtrip', Q.line);
  expect('text.item-value.plain-note-roundtrip', Q.plain);
  expect('text.item-value.rich-note-roundtrip', Q.rich);
  expect('text.item-value.rich-note-colon', Q.colon);
  expect('text.item-value.control-plain-note-colon', Q.controlColon);
  expect('text.item-value.rich-note-decode-recovers', Q.decode);
  expect('text.item-value.rich-note-encoding-idempotent', Q.idempotent);

  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };

  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 200)}`;

  // Named entities plus the numeric forms `xmlDecode` does not carry. `&amp;`
  // last for the reason it is last there: decoding it earlier would turn
  // `&amp;#58;` into a colon, when the text it stands for is `&#58;`.
  const htmlDecode = (value) => String(value)
    .replace(/&#x([0-9a-fA-F]+);/g, (_, hex) => String.fromCodePoint(parseInt(hex, 16)))
    .replace(/&#(\d+);/g, (_, dec) => String.fromCodePoint(Number(dec)))
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');

  // A field subtype needs the verbose spelling: under `odata=nometadata` the
  // server reads a create body as a bare SP.Field and refuses RichText, which
  // is the one property this probe is about.
  const VERBOSE = {
    Accept: 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
  };
  const postVerbose = async (path, body) => {
    const digest = await getDigest();
    const res = await fetch(`${WEB}/_api/${path}`, {
      method: 'POST',
      headers: { ...VERBOSE, 'X-RequestDigest': digest },
      body: JSON.stringify(body),
      credentials: 'same-origin',
    });
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* SharePoint sent plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };

  await resetList(LIST);

  // ---- fixture ---------------------------------------------------------
  {
    const existing = await spGet(listPath);
    if (!existing.ok) {
      const digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: LIST,
        BaseTemplate: 100,
        Description: 'dbml-sharepoint item text round-trip probe. Safe to delete.',
      }, digest);
      if (!made.ok) {
        record('text.item-value.fixture-columns-created', Q.fixture, 'FAIL', short(made));
        voidAll(IDS, 'the fixture list did not build, so no column could be written.');
        return report();
      }
    }
    const columns = [
      [LINE, { __metadata: { type: 'SP.FieldText' }, FieldTypeKind: 2 }],
      [PLAIN, {
        __metadata: { type: 'SP.FieldMultiLineText' },
        FieldTypeKind: 3, RichText: false, NumberOfLines: 6,
      }],
      [RICH, {
        __metadata: { type: 'SP.FieldMultiLineText' },
        FieldTypeKind: 3, RichText: true, NumberOfLines: 6,
      }],
    ];
    // The shapes every row below depends on, since each one attributes an
    // encoding to plain or to rich text. NumberOfLines is declared and not
    // compared: it changes what the form shows, not what the column stores.
    const REQUIRED = {
      [LINE]: { FieldTypeKind: 2 },
      [PLAIN]: { FieldTypeKind: 3, RichText: false },
      [RICH]: { FieldTypeKind: 3, RichText: true },
    };
    const spell = (name) => `${name} (`
      + Object.entries(REQUIRED[name]).map(([prop, want]) => `${prop} ${want}`).join(', ')
      + ')';
    // A property the field does not carry is a failure, not a match: a shape
    // this probe cannot see is one it cannot attribute a reading to.
    const shapeWrong = (name, field) => {
      const wrong = [];
      for (const [prop, want] of Object.entries(REQUIRED[name])) {
        if (field[prop] === undefined) {
          wrong.push(`${prop} is absent from the field`);
        } else if (field[prop] !== want) {
          wrong.push(`${prop} is ${JSON.stringify(field[prop])}, not ${JSON.stringify(want)}`);
        }
      }
      return wrong.length === 0 ? null : wrong.join(' and ');
    };
    const readField = (name) =>
      spGet(`${listPath}/fields/getbyinternalnameortitle('${name}')`);

    const failures = [];
    for (const [name, body] of columns) {
      let got = await readField(name);
      if (!got.ok) {
        const made = await postVerbose(`${listPath}/fields`, { ...body, Title: name });
        if (!made.ok) {
          failures.push(`${name}: ${short(made)}`);
          continue;
        }
        // A create that answered 200 is not the field's shape, only the
        // server's word that it took the body.
        got = await readField(name);
      }
      if (readFailed(got)) {
        failures.push(`${name}: its shape did not read back: HTTP ${got.status}`);
        continue;
      }
      const wrong = shapeWrong(name, got.body);
      if (wrong !== null) failures.push(`${name}: ${wrong}`);
    }
    record('text.item-value.fixture-columns-created', Q.fixture,
           failures.length === 0 ? 'PASS' : 'FAIL',
           failures.length === 0
             ? `'${LIST}' carries ${[LINE, PLAIN, RICH].map(spell).join(', ')}, `
               + 'each read back from the field itself'
             : failures.join('; '));
    if (failures.length > 0) {
      voidAll(IDS, 'a declared column did not read back with the shape this run '
                   + 'depends on, so no reading could be attributed to it.');
      return report();
    }
  }

  // ---- one item carrying the battery in all three ----------------------
  const writeItem = async (fields) => {
    const made = await postVerbose(`${listPath}/items`, {
      __metadata: { type: 'SP.Data.' },
      ...fields,
    });
    if (made.ok && made.body && made.body.d) return { id: made.body.d.Id };
    // The entity type name is per-list and the create above guesses it, so a
    // refusal here is read rather than assumed: ask the list for its own.
    const shape = await spGet(`${listPath}?$select=ListItemEntityTypeFullName`);
    if (readFailed(shape)) return { error: `the list entity type could not be read: ${short(shape)}` };
    const retry = await postVerbose(`${listPath}/items`, {
      __metadata: { type: shape.body.ListItemEntityTypeFullName },
      ...fields,
    });
    if (!retry.ok) return { error: short(retry) };
    return { id: retry.body && retry.body.d && retry.body.d.Id };
  };

  const readItem = async (id, names) => {
    const r = await spGet(`${listPath}/items(${id})?$select=${names.join(',')}`);
    if (readFailed(r)) return { error: short(r) };
    return { values: r.body };
  };

  const compare = (id, question, written, got) => {
    const same = String(got) === written;
    record(id, question, same ? 'IDENTICAL' : 'CHANGED',
           same ? `returned the bytes it was given: ${JSON.stringify(written)}`
             : `wrote ${JSON.stringify(written)}, read ${JSON.stringify(got)}`);
    return same;
  };

  let richBattery = null;
  {
    const made = await writeItem({ Title: 'battery', [LINE]: BATTERY, [PLAIN]: BATTERY, [RICH]: BATTERY });
    if (made.error || !made.id) {
      voidAll(IDS, `the battery item could not be created: ${made.error || 'no Id came back'}`);
      return report();
    }
    const read = await readItem(made.id, [LINE, PLAIN, RICH]);
    if (read.error) {
      voidAll(IDS, `the battery item did not read back: ${read.error}`);
      return report();
    }
    compare('text.item-value.single-line-roundtrip', Q.line, BATTERY, read.values[LINE]);
    compare('text.item-value.plain-note-roundtrip', Q.plain, BATTERY, read.values[PLAIN]);
    compare('text.item-value.rich-note-roundtrip', Q.rich, BATTERY, read.values[RICH]);
    richBattery = read.values[RICH];

    const decoded = htmlDecode(richBattery);
    record('text.item-value.rich-note-decode-recovers', Q.decode,
           decoded === BATTERY ? 'RECOVERED' : 'NOT RECOVERED',
           decoded === BATTERY
             ? 'decoding the character references returns the written string exactly'
             : `decoded to ${JSON.stringify(decoded)}, which is not the written string`);
  }

  // ---- the narrow colon, on both notes ---------------------------------
  {
    const made = await writeItem({ Title: 'colon', [PLAIN]: COLON, [RICH]: COLON });
    if (made.error || !made.id) {
      voidAll(['text.item-value.rich-note-colon', 'text.item-value.control-plain-note-colon'],
              `the colon item could not be created: ${made.error || 'no Id came back'}`);
    } else {
      const read = await readItem(made.id, [PLAIN, RICH]);
      if (read.error) {
        voidAll(['text.item-value.rich-note-colon', 'text.item-value.control-plain-note-colon'],
                `the colon item did not read back: ${read.error}`);
      } else {
        compare('text.item-value.rich-note-colon', Q.colon, COLON, read.values[RICH]);
        compare('text.item-value.control-plain-note-colon', Q.controlColon,
                COLON, read.values[PLAIN]);
      }
    }
  }

  // ---- does the encoding compound on a redeploy? -----------------------
  {
    if (richBattery === null || String(richBattery) === BATTERY) {
      record('text.item-value.rich-note-encoding-idempotent', Q.idempotent, 'NOT REACHED',
             'the rich column returned what it was given, so there is no encoded '
             + 'form to write back and nothing could compound.');
    } else {
      const made = await writeItem({ Title: 'again', [RICH]: String(richBattery) });
      if (made.error || !made.id) {
        record('text.item-value.rich-note-encoding-idempotent', Q.idempotent,
               'NOT ESTABLISHED',
               `the second item could not be created: ${made.error || 'no Id came back'}`,
               'void');
      } else {
        const read = await readItem(made.id, [RICH]);
        if (read.error) {
          record('text.item-value.rich-note-encoding-idempotent', Q.idempotent,
                 'NOT ESTABLISHED', `it did not read back: ${read.error}`, 'void');
        } else {
          const again = String(read.values[RICH]);
          record('text.item-value.rich-note-encoding-idempotent', Q.idempotent,
                 again === String(richBattery) ? 'STABLE' : 'COMPOUNDED',
                 again === String(richBattery)
                   ? 'the stored form written back stores unchanged, so a redeploy '
                     + 'of the same declared value settles rather than drifting'
                   : `wrote ${JSON.stringify(String(richBattery))},`
                     + ` read ${JSON.stringify(again)}`);
        }
      }
    }
  }

  return report();
})();
