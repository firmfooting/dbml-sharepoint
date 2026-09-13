/**
 * dbml-sharepoint PROBE: WHICH TOKENS A LIBRARY FORM HEADER CAN READ
 *
 * REVISION: af2a4ff1
 *
 * ONE QUESTION:
 *   A document library's form header is stored and read back byte-identical
 *   and renders nothing. Which column tokens does that header actually
 *   resolve at render time?
 *
 * OBSERVED on a live display form 2026-09-13: the shipped
 * legal-compliance-register library's header title line reads
 * `=if([$FileLeafRef] == '', 'New SAQ', [$FileLeafRef])` and rendered EMPTY,
 * collapsing the header so its description line sat beside the icon.
 *
 * What had been measured is only that a library content type ACCEPTS such a
 * header: `library.doc-lib.header-fileleafref` in document-library-probe.js,
 * whose own comment says "Storage only. Whether the header RENDERS is the
 * checklist's job below." That checklist item was never answered, and the
 * tool shipped a family relying on it. This is the failure class AGENTS.md
 * names first: a formatter that saves, reads back byte-identical, passes
 * every deploy phase, and does nothing on the page.
 *
 * One header carrying every candidate on its own LABELLED line, so a single
 * look at one form answers the whole question rather than one token per
 * deploy. A label with nothing after it is a token that did not resolve.
 *
 * SCOPE AND QUESTIONS
 *   library.doc-lib.fixture-library-created
 *     A document library is created (BaseTemplate 101). Same question
 *     folder-probe.js asks, by the same method, so it keeps the same id.
 *   library.form.header-token-battery-stored
 *     Is the battery header accepted on the library's document content type,
 *     and does it read back byte-identical? Machine-answerable, and it is
 *     the half that was already known to pass.
 *   library.form.header-token-battery-renders
 *     MANUAL: open the uploaded file's display form and copy the header
 *     back. Which labelled lines carry a value? This is the half nobody
 *     had asked, and only eyes can answer it.
 *
 * OBSERVED, NEVER ASSERTED
 *   Every token's rendered value. The point is to learn which resolve, so
 *   asserting any of them in advance would decide the answer in the probe
 *   rather than on the page.
 *
 * NOT MEASURED HERE
 *   What the NEW form header shows (no item exists yet, so every token is
 *   empty there by construction), and whether a token that resolves on a
 *   library also resolves on a list. The deploy emits a different header
 *   per kind, so the list case is a separate question.
 *
 * MICROSOFT LEARN CITATIONS
 *   Form header, body and footer formatting, and the `[$Column]` syntax:
 *     "Configure the list form" (SharePoint list formatting)
 *   ClientFormCustomFormatter on a content type:
 *     "SP.ContentType properties" (CSOM)
 *
 * HOW TO RUN
 *   1. Open a site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true, paste again.
 *   4. Copy the RESULTS block back, THEN open the library, click the
 *      uploaded file, open its details panel and copy the header back too.
 *
 * WHEN FINISHED: delete the library it created.
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
  const resetList = async (title) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) {
      log('INFO', `CLEANUP is on but ALLOW_WRITES is false, so '${title}' is not deleted.`);
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
    // removed. A locked or no-delete list would otherwise leave rows from
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

  log('INFO', 'probe revision af2a4ff1. Quote this when reporting results.');

  const LIB = 'dbmlsp Probe Header Tokens';
  const libPath = `web/lists/getbytitle('${LIB}')`;
  const FILE = 'dbmlsp-header-probe.txt';

  // Every token a library header might plausibly name for the file's
  // identity, each on its own line behind a label that renders whatever
  // happens. A label standing alone is the finding.
  const TOKENS = ['FileLeafRef', 'Title', 'FileRef', 'Name', 'ID', 'Modified'];

  const Q = {
    fixture: 'A document library is created (BaseTemplate 101)',
    stored: "Is a header naming every candidate token accepted, and does it read back byte-identical",
    renders: 'MANUAL: which of those tokens carry a value on the rendered display form',
  };

  if (!CONFIRMED) {
    log('INFO', `Would create a DOCUMENT LIBRARY '${LIB}' on ${WEB}, upload one small`);
    log('INFO', `file '${FILE}' to it, and set a form header on its document content`);
    log('INFO', `type carrying one labelled line per token: ${TOKENS.join(', ')}.`);
    log('INFO', 'Then it asks you to open that file and copy the header back.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIB}' would be RECYCLED first.`);
    } else {
      log('INFO', 'CLEANUP is off: an existing library would be reused, whose content');
      log('INFO', 'type may already carry a header. Set CLEANUP = true.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('library.doc-lib.fixture-library-created', Q.fixture);
  expect('library.form.header-token-battery-stored', Q.stored);
  expect('library.form.header-token-battery-renders', Q.renders);

  const IDS = [
    'library.form.header-token-battery-stored',
    'library.form.header-token-battery-renders',
  ];
  const voidAll = (ids, reason) => {
    for (const id of ids) {
      record(id, RESULTS.find((r) => r.id === id).question, 'NOT ESTABLISHED', reason, 'void');
    }
  };
  const short = (r) => `HTTP ${r.status}: ${(r.text || '').slice(0, 200)}`;

  const header = {
    elmType: 'div',
    children: [
      {
        elmType: 'div',
        attributes: { class: 'ms-fontWeight-bold ms-fontSize-16' },
        txtContent: 'dbmlsp header token probe',
      },
      ...TOKENS.map((token) => ({
        elmType: 'div',
        attributes: { class: 'ms-fontSize-12' },
        txtContent: `=' ${token} -> [' + [$${token}] + ']'`,
      })),
    ],
  };
  const formatter = JSON.stringify({ header });

  await resetList(LIB);

  // ---- fixture ---------------------------------------------------------
  {
    const existing = await spGet(libPath);
    if (!existing.ok) {
      const digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: LIB,
        BaseTemplate: 101,
        Description: 'dbml-sharepoint header token probe. Safe to delete.',
        ContentTypesEnabled: false,
      }, digest);
      record('library.doc-lib.fixture-library-created', Q.fixture,
             made.ok ? 'PASS' : 'FAIL',
             made.ok ? `created '${LIB}'` : short(made));
      if (!made.ok) {
        voidAll(IDS, 'the library fixture did not build, so it has no content type to set.');
        return report();
      }
    } else {
      record('library.doc-lib.fixture-library-created', Q.fixture, 'ALREADY PRESENT',
             'reusing an existing library, whose content type may already carry a header. '
             + 'Set CLEANUP = true for a clean answer.');
    }
  }

  // A file, because a header with no item behind it renders every token
  // empty by construction and would answer the question wrongly.
  {
    const root = await spGet(`${libPath}/RootFolder?$select=ServerRelativeUrl`);
    if (readFailed(root)) {
      voidAll(IDS, `the library RootFolder did not read back (HTTP ${root.status}).`);
      return report();
    }
    const digest = await getDigest();
    const url = `web/GetFolderByServerRelativeUrl('${root.body.ServerRelativeUrl}')`
      + `/Files/add(url='${FILE}',overwrite=true)`;
    const res = await fetch(`${WEB}/_api/${url}`, {
      method: 'POST',
      headers: { Accept: 'application/json;odata=nometadata', 'X-RequestDigest': digest },
      body: 'dbml-sharepoint header token probe. Safe to delete.',
      credentials: 'same-origin',
    });
    if (!res.ok) {
      voidAll(IDS, `the probe file did not upload: HTTP ${res.status} ${(await res.text()).slice(0, 160)}`);
      return report();
    }
  }

  // ---- store the battery on the document content type -------------------
  {
    // The collection is unordered and a library carries a Folder content
    // type as well as a Document one, so the first entry can be the folder,
    // which would store the formatter where no document ever reads it. Same
    // rule the deploy uses: the first id under 0x01 that is not under 0x0120.
    const cts = await spGet(`${libPath}/contenttypes?$select=Id,Name&$top=20`);
    const idOf = (ct) => String((ct && ct.Id && ct.Id.StringValue) || (ct && ct.Id) || '');
    const ct = ((cts.ok && cts.body && cts.body.value) || [])
      .find((c) => idOf(c).startsWith('0x01') && !idOf(c).startsWith('0x0120'));
    if (!ct) {
      voidAll(IDS, `no document content type was found on the library (HTTP ${cts.status}).`);
      return report();
    }
    const digest = await getDigest();
    const set = await spPost(`${libPath}/contenttypes('${idOf(ct)}')`,
      { ClientFormCustomFormatter: formatter }, digest,
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
    if (!set.ok) {
      record('library.form.header-token-battery-stored', Q.stored, 'REFUSED', short(set));
      voidAll(['library.form.header-token-battery-renders'],
              'the header was refused, so there is nothing on the form to look at.');
      return report();
    }
    const back = await spGet(
      `${libPath}/contenttypes('${idOf(ct)}')?$select=ClientFormCustomFormatter`);
    if (readFailed(back)) {
      record('library.form.header-token-battery-stored', Q.stored, 'NOT ESTABLISHED',
             `the read-back failed (HTTP ${back.status}), so storage is unconfirmed`, 'void');
    } else {
      const stored = back.body.ClientFormCustomFormatter;
      record('library.form.header-token-battery-stored', Q.stored,
             stored === formatter ? 'PASS' : 'CHANGED',
             stored === formatter
               ? `stored byte-identical on content type '${ct.Name}'`
               : `wrote ${formatter.length} chars, read back ${JSON.stringify(String(stored).slice(0, 200))}`);
    }
  }

  record('library.form.header-token-battery-renders', Q.renders, 'MANUAL',
         'open the library, click the uploaded file, open its details panel and copy '
         + 'the header back. A label with nothing after it is a token that did not '
         + 'resolve.');

  console.log('\n============ EYES-ON ============');
  console.log(`  Open '${LIB}', click '${FILE}', open its details panel.`);
  console.log('  Copy the header block back verbatim. Expected shape, one per line:');
  for (const token of TOKENS) console.log(`     ${token} -> [<value or empty>]`);
  console.log('  answer: ______________________________________');
  console.log('=================================');

  return report();
})();
