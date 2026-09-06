/**
 * dbml-sharepoint PROBE: WHICH SP.List SETTINGS ACTUALLY STICK?
 *
 * ONE QUESTION:
 *   For each writeable setting on SP.List, does writing a non-default value
 *   through the ordinary MERGE path actually change the container, on a
 *   GENERIC LIST and on a DOCUMENT LIBRARY, which may not answer the same?
 *
 * REVISION: 7a143beb
 *
 * WHY: attachments are disabled on every list before go-live as a MANUAL
 * step, on ten lists in programme-governance alone, because there is no
 * `attachments` key in mapping.yaml and the deployer neither sets nor
 * reconciles the setting. The declarative `attachments:` setting that would
 * replace that step has been designed but never measured, and the same is
 * true of versioning, content approval and the rest of the settings surface.
 * `.hermes/plans/2026-09-04_library-list-enumeration-plan.md` section 3 names
 * this the highest-value gap for exactly that reason.
 *
 * THE HAZARD THIS EXISTS TO FIND. `caml-chain-depth-probe.js` recorded a
 * property (`ReadOnlyView`) that SharePoint accepts with a 2xx and then
 * reads back unchanged. A setting in that class passes every deploy phase
 * and does nothing, which is the one failure mode nothing downstream can
 * see. This probe's job is to name every member of that class on SP.List,
 * so a declarative setting is only ever built on one that sticks.
 *
 * WHERE THE PROPERTY NAMES COME FROM. Every name below is the one Microsoft
 * Learn documents, not one assembled from memory, because a misspelled
 * property makes `$select` return 400, `isRefusal` counts 400 as a refusal,
 * and the probe would then print a claim about SharePoint that was really a
 * typo. Two names in the original brief were wrong and are corrected here:
 * the attachment flag is `EnableAttachments`, not `Attachments`, and the
 * content-type flag is `ContentTypesEnabled`, not `EnableContentTypes`.
 *
 *   `EnableAttachments`, `EnableVersioning`, `EnableMinorVersions`,
 *   `EnableModeration`, `EnableFolderCreation`, `NoCrawl`, `Direction`,
 *   `ContentTypesEnabled`, each Boolean (Direction String) and each marked
 *   RW: "Lists and list items REST API reference", dn531433(v=office.15).
 *   `ReadSecurity`, `WriteSecurity`, `IrmEnabled`, `IrmExpire`, `IrmReject`:
 *   the SP.List class reference, Microsoft.SharePoint.Client.List. The
 *   REST reference's List table does not carry ReadSecurity or
 *   WriteSecurity, so those two are read through an explicit $select, which
 *   is what `templates/deploy/_field_reconcile.js.j2` already does against a
 *   live tenant.
 *   List MERGE endpoint: "Working with lists and list items with REST".
 *   List creation via POST to `web/lists`: the same page.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. A generic list's settings are questions
 * about the list object, so they file under `field.list.*`, the scope
 * `save-instant-paths-probe.js` already uses for one. A library's file
 * under `library.doc-lib.*`, beside the library-creation control five
 * probes share. `ReadSecurity` and `WriteSecurity` are item-level
 * permission trimming, so both containers' rows file under
 * `access.item-acl.*`, which is what they are about.
 *
 *   <container>.fixture-*                 does the scratch container exist?
 *   <container>.control-description-sticks
 *       POSITIVE CONTROL: does a MERGE of `Description`, a property this
 *       repository's deployer writes against live tenants every run, change
 *       the container and read back? If it does not, the METHOD is broken
 *       and every settings row on that container is void rather than open.
 *   <container>.control-unknown-property-refused
 *       NEGATIVE CONTROL: is a MERGE naming a property that does not exist
 *       on SP.List refused? Establishes that a 2xx means something.
 *   <container>.property-enumeration
 *       OBSERVE: which of the candidate names does a bare GET of the
 *       container actually return, and how many properties in total?
 *   <container>.<setting>-sticks          one row per setting: STICKS,
 *       SILENTLY IGNORED, REFUSED, or NOT ESTABLISHED.
 *
 * THE DEPENDS-ON / OBSERVES SPLIT, STATED:
 *   Depends on (asserted, read back): the scratch list and the scratch
 *   library exist (fixtures); a MERGE of `Description` changes each one and
 *   reads back (positive control, one per container, because the method
 *   could work on a list and not on a library).
 *   Observes (recorded, never asserted): whether an unknown property is
 *   refused; which candidate properties the container exposes; and for each
 *   setting, the value written, the value read back, the value it held
 *   before, the HTTP status and the error text. NOTHING here asserts that a
 *   particular setting sticks. A run where every setting is silently
 *   ignored is a successful run with an important answer, and a probe that
 *   asserted otherwise would kill the experiment the moment it started
 *   working.
 *
 * THE MEASUREMENT, per (container, setting):
 *   1. Read the setting through an explicit `$select`. A 400 here says the
 *      container does not expose that property, and the row stops: nothing
 *      is written against a name the container does not have.
 *   2. Choose a target that DIFFERS from what was just read (the boolean
 *      opposite; 1 or 2, whichever ReadSecurity/WriteSecurity is not;
 *      RTL unless it is already RTL). `EnableAttachments` is the exception:
 *      its target is always `false`, because `false` is the value the
 *      declarative setting needs and "can it be turned off" is the
 *      question. If a container already reads false, the row records that
 *      and establishes nothing, rather than claiming a write stuck when it
 *      wrote what was already there.
 *   3. MERGE it, then read it back and compare with the target.
 *
 * TABLE ORDER IS DELIBERATE. `EnableVersioning` is written before
 * `EnableMinorVersions`, because minor versions are only meaningful while
 * versioning is on. The minor-versions row records the container's observed
 * `EnableVersioning` at the moment it ran, so a reader never has to infer
 * it from the ordering.
 *
 * SCOPE OF CLAIMS: one tenant, one site, one scratch list and one scratch
 * library, as Site Owner. A setting that sticks here is evidence about a
 * container an owner just created, not about a list somebody else built
 * under a policy or a retention label.
 *
 * HOW TO RUN
 *   1. Open the sandbox site you own, at /_layouts/15/settings.aspx.
 *   2. F12 -> Console -> paste -> Enter. It prints its plan and stops.
 *   3. Edit CONFIRMED and ALLOW_WRITES to true (CLEANUP = true recycles a
 *      leftover scratch container first, which is what a clean answer
 *      needs), paste again.
 *   4. Copy the RESULTS block and the SETTINGS ROWS block back verbatim.
 *
 * WHEN FINISHED: set CLEANUP_AT_END = true and paste again to recycle both
 * scratch containers, or recycle them by hand from site contents.
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
  // Recycles the two scratch containers AFTER the run, so a first paste can
  // leave them behind for an operator to look at and a second paste tidies
  // up. Destructive, so it ships false like every other guard.
  const CLEANUP_AT_END = false;

  log('INFO', 'probe revision 7a143beb. Quote this when reporting results.');

  const LIST = 'dbmlsp Probe ListSettings';
  const LIB = 'dbmlsp Probe ListSettings Lib';
  const LIST_PATH = `web/lists/getbytitle('${LIST}')`;
  const LIB_PATH = `web/lists/getbytitle('${LIB}')`;
  const LIST_DESC = 'dbml-sharepoint list-settings probe list. Safe to delete.';
  const LIB_DESC = 'dbml-sharepoint list-settings probe library. Safe to delete.';
  // A name that is not a property of SP.List, for the negative control. The
  // prefix keeps it from ever colliding with a real one.
  const UNKNOWN_PROPERTY = 'DbmlspNotASharePointProperty';

  // Every settings row this probe can answer, with the check id it takes on
  // each container. The block is named CANDIDATES because probe-catalog.json
  // reads a block by that name to learn the ids a probe registers from a
  // table rather than from one expect() per line.
  //
  // mode decides the target value:
  //   'off'       write false, whatever the container reads now
  //   'flip'      write the boolean opposite of what the container reads now
  //   'security'  write 2 when it reads 1, else 1
  //   'direction' write 'RTL' unless it already reads RTL, then 'LTR'
  const CANDIDATES = [
    ['EnableAttachments', 'off',
     'field.list.attachments-sticks', 'library.doc-lib.attachments-sticks',
     'list item attachments', null],
    ['EnableVersioning', 'flip',
     'field.list.versioning-sticks', 'library.doc-lib.versioning-sticks',
     'version history', null],
    ['EnableMinorVersions', 'flip',
     'field.list.minor-versions-sticks', 'library.doc-lib.minor-versions-sticks',
     'draft (minor) versions', 'EnableVersioning'],
    ['EnableModeration', 'flip',
     'field.list.moderation-sticks', 'library.doc-lib.moderation-sticks',
     'content approval', null],
    ['EnableFolderCreation', 'flip',
     'field.list.folder-creation-sticks', 'library.doc-lib.folder-creation-sticks',
     'the New Folder command', null],
    ['NoCrawl', 'flip',
     'field.list.nocrawl-sticks', 'library.doc-lib.nocrawl-sticks',
     'exclusion from the search crawl', null],
    ['Direction', 'direction',
     'field.list.direction-sticks', 'library.doc-lib.direction-sticks',
     'reading order', null],
    ['ContentTypesEnabled', 'flip',
     'field.list.content-types-sticks', 'library.doc-lib.content-types-sticks',
     'management of content types', null],
    ['ReadSecurity', 'security',
     'access.item-acl.read-security-on-list', 'access.item-acl.read-security-on-library',
     'item-level read trimming', null],
    ['WriteSecurity', 'security',
     'access.item-acl.write-security-on-list', 'access.item-acl.write-security-on-library',
     'item-level write trimming', null],
    ['IrmEnabled', 'flip',
     'field.list.irm-enabled-sticks', 'library.doc-lib.irm-enabled-sticks',
     'information rights management', null],
    ['IrmExpire', 'flip',
     'field.list.irm-expire-sticks', 'library.doc-lib.irm-expire-sticks',
     'IRM document expiry', null],
    ['IrmReject', 'flip',
     'field.list.irm-reject-sticks', 'library.doc-lib.irm-reject-sticks',
     'IRM rejection of unsupported clients', null],
  ];

  // The two containers, in the order they run. Each carries the four ids
  // that are about the container itself rather than about one setting.
  const CONTAINERS = [
    {
      kind: 'generic list', title: LIST, path: LIST_PATH,
      baseTemplate: 100, description: LIST_DESC, idIndex: 2,
      fixtureId: 'field.list.fixture-scratch-list',
      controlId: 'field.list.control-description-sticks',
      unknownId: 'field.list.control-unknown-property-refused',
      enumerationId: 'field.list.property-enumeration',
    },
    {
      kind: 'document library', title: LIB, path: LIB_PATH,
      baseTemplate: 101, description: LIB_DESC, idIndex: 3,
      fixtureId: 'library.doc-lib.fixture-library-created',
      controlId: 'library.doc-lib.control-description-sticks',
      unknownId: 'library.doc-lib.control-unknown-property-refused',
      enumerationId: 'library.doc-lib.property-enumeration',
    },
  ];

  if (!CONFIRMED) {
    log('INFO', `Would create a generic list '${LIST}' (BaseTemplate 100) and a document`);
    log('INFO', `library '${LIB}' (BaseTemplate 101) on ${WEB}, then for each of them`);
    log('INFO', `read and write ${CANDIDATES.length} SP.List settings one at a time:`);
    log('INFO', `${CANDIDATES.map((row) => row[0]).join(', ')}.`);
    log('INFO', 'Each setting is read through $select, written to a value that differs');
    log('INFO', 'from what was read, and read back, so a write that is accepted and');
    log('INFO', 'silently ignored is distinguishable from one that sticks. Nothing');
    log('INFO', 'outside the two scratch containers is read or written.');
    if (CLEANUP) {
      log('INFO', `CLEANUP is ON: '${LIST}' and '${LIB}' would be RECYCLED first, so every`);
      log('INFO', 'reading starts from a container this run created.');
    } else {
      log('INFO', 'CLEANUP is off: a leftover container from an earlier run would answer');
      log('INFO', 'with settings that run left behind. Set CLEANUP = true for a clean run.');
    }
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  // The eight container-level ids are written out as literals here and named
  // again in CONTAINERS above. They are the only ids in this probe outside
  // the CANDIDATES table, and test_probe_catalog.py learns a probe's ids from
  // literal expect() heads and that table alone, so an id reachable only
  // through `container.fixtureId` would be registered at run time and stay
  // invisible to the catalogue.
  expect('field.list.fixture-scratch-list',
         'fixture: a scratch generic list exists to read and write settings on');
  expect('field.list.control-description-sticks',
         'control: does a MERGE of Description change the generic list and read back');
  expect('field.list.control-unknown-property-refused',
         'negative control: is a MERGE naming a property SP.List does not have refused on the generic list');
  expect('field.list.property-enumeration',
         'observe: which candidate settings does a bare GET of the generic list return, and how many properties in all');
  expect('library.doc-lib.fixture-library-created',
         'fixture: a scratch document library exists to read and write settings on');
  expect('library.doc-lib.control-description-sticks',
         'control: does a MERGE of Description change the document library and read back');
  expect('library.doc-lib.control-unknown-property-refused',
         'negative control: is a MERGE naming a property SP.List does not have refused on the document library');
  expect('library.doc-lib.property-enumeration',
         'observe: which candidate settings does a bare GET of the document library return, and how many properties in all');

  for (const container of CONTAINERS) {
    for (const row of CANDIDATES) {
      expect(row[container.idIndex],
             `observe: does writing a non-default ${row[0]} (${row[4]}) stick on the ${container.kind}`);
    }
  }

  // One row per (container kind, property), which is the machine-readable
  // table this probe exists to produce. Printed whole at the end so an
  // operator copies a structure rather than transcribing prose.
  const ROWS = [];

  const merge = async (path, payload) => {
    const digest = await getDigest();
    // __metadata is a VERBOSE OData construct. Sent with the harness's
    // default nometadata content type SharePoint answers 400, which is how
    // the threshold probe's first live run failed all four of its MERGEs.
    return spPost(path, { __metadata: { type: 'SP.List' }, ...payload }, digest, {
      'Content-Type': 'application/json;odata=verbose',
      'X-HTTP-Method': 'MERGE',
      'IF-MATCH': '*',
    });
  };

  // Reads ONE property by name. A $select naming a property the container
  // does not expose comes back 400, and that is the answer rather than a
  // failure: it says the setting is not on this container's surface.
  const readProperty = async (container, name) => {
    const got = await spGet(`${container.path}?$select=${name}`);
    if (readFailed(got)) {
      return { ok: false, status: got.status, value: null };
    }
    return { ok: true, status: got.status, value: got.body[name] };
  };

  const targetFor = (mode, before) => {
    if (mode === 'off') {
      return typeof before === 'boolean' ? false : undefined;
    }
    if (mode === 'flip') {
      return typeof before === 'boolean' ? !before : undefined;
    }
    if (mode === 'security') {
      return Number.isInteger(before) ? (before === 2 ? 1 : 2) : undefined;
    }
    if (mode === 'direction') {
      return typeof before !== 'string' ? undefined
        : (before.toUpperCase() === 'RTL' ? 'LTR' : 'RTL');
    }
    return undefined;
  };

  // Direction is compared case-insensitively and the other settings exactly.
  // SharePoint documents Direction as returning NONE / LTR / RTL and this
  // probe writes RTL; a readback differing only in case is the same reading
  // order, and calling that "changed to something else" would report a
  // difference nobody can act on.
  const sameValue = (written, back) =>
    typeof written === 'string' && typeof back === 'string'
      ? written.toUpperCase() === back.toUpperCase()
      : written === back;

  const show = (value) => (value === undefined ? 'undefined' : JSON.stringify(value));

  for (const container of CONTAINERS) {
    const where = container.kind;
    await resetList(container.title);

    // ---- fixture ------------------------------------------------------
    let ready = false;
    const existing = await spGet(container.path);
    if (existing.ok) {
      record(container.fixtureId,
             `fixture: a scratch ${where} exists to read and write settings on`,
             'ALREADY PRESENT',
             `reusing an existing '${container.title}'. Its settings may carry an `
             + 'earlier run\'s writes. Set CLEANUP = true for a clean answer');
      ready = true;
    } else {
      const digest = await getDigest();
      const made = await spPost('web/lists', {
        Title: container.title,
        BaseTemplate: container.baseTemplate,
        Description: container.description,
      }, digest);
      record(container.fixtureId,
             `fixture: a scratch ${where} exists to read and write settings on`,
             made.ok ? 'PASS' : 'FAIL',
             made.ok
               ? `created '${container.title}' (BaseTemplate ${container.baseTemplate})`
               : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
      ready = made.ok;
    }

    if (!ready) {
      const reason = `the scratch ${where} was never created, so nothing could be read or written`;
      record(container.controlId,
             `control: does a MERGE of Description change the ${where} and read back`,
             'ABORTED', reason);
      record(container.unknownId,
             `negative control: is a MERGE naming a property SP.List does not have refused on the ${where}`,
             'ABORTED', reason);
      record(container.enumerationId,
             `observe: which candidate settings does a bare GET of the ${where} return, and how many properties in all`,
             'ABORTED', reason);
      for (const row of CANDIDATES) {
        record(row[container.idIndex],
               `observe: does writing a non-default ${row[0]} (${row[4]}) stick on the ${where}`,
               'ABORTED', reason);
        ROWS.push({
          container: where, property: row[0], written: null, readBack: null,
          before: null, sticks: null, status: null, error: reason,
        });
      }
      continue;
    }

    // ---- positive control: a property known to be writable --------------
    // Description is what `list-description-probe.js` measures and what the
    // deployer writes on every run, so a Description MERGE that does not
    // take says the METHOD failed here, not that this container is unusual.
    const marker = `${container.description} probe-control-${Date.now()}`;
    const setDesc = await merge(container.path, { Description: marker });
    const readDesc = await readProperty(container, 'Description');
    const controlOk = setDesc.ok && readDesc.ok && readDesc.value === marker;
    record(container.controlId,
           `control: does a MERGE of Description change the ${where} and read back`,
           controlOk ? 'PASS' : 'CONTROL FAILED, METHOD VOID',
           controlOk
             ? `Description MERGE returned HTTP ${setDesc.status} and read back byte-identical`
             : `MERGE HTTP ${setDesc.status}${setDesc.ok ? '' : `: ${setDesc.text.slice(0, 200)}`}; `
               + `readback ${readDesc.ok ? show(readDesc.value) : `failed HTTP ${readDesc.status}`}`);

    // ---- negative control: a property SP.List does not have -------------
    const unknown = await merge(container.path, { [UNKNOWN_PROPERTY]: 'x' });
    const unknownRefused = !unknown.ok && isRefusal(unknown.status);
    record(container.unknownId,
           `negative control: is a MERGE naming a property SP.List does not have refused on the ${where}`,
           unknown.ok ? 'ACCEPTED'
             : unknownRefused ? 'REFUSED' : 'NOT ESTABLISHED',
           unknown.ok
             ? `a MERGE setting '${UNKNOWN_PROPERTY}' returned HTTP ${unknown.status}, so an `
               + 'accepted write says nothing on its own and every verdict below rests on the readback'
             : `HTTP ${unknown.status}: ${unknown.text.slice(0, 240)}`);

    // ---- enumeration: what a bare GET returns ---------------------------
    const bare = await spGet(container.path);
    if (readFailed(bare)) {
      record(container.enumerationId,
             `observe: which candidate settings does a bare GET of the ${where} return, and how many properties in all`,
             'NOT ESTABLISHED', `the bare GET failed: HTTP ${bare.status}`);
    } else {
      const names = Object.keys(bare.body);
      const present = CANDIDATES.map((row) => row[0]).filter((name) => names.includes(name));
      const absent = CANDIDATES.map((row) => row[0]).filter((name) => !names.includes(name));
      record(container.enumerationId,
             `observe: which candidate settings does a bare GET of the ${where} return, and how many properties in all`,
             'ENUMERATED',
             `the default projection returned ${names.length} properties. Of the `
             + `${CANDIDATES.length} candidates, present: ${present.join(', ') || 'none'}; `
             + `absent: ${absent.join(', ') || 'none'}. Absent here does not mean absent from `
             + 'SP.List: each candidate is read again below through an explicit $select');
    }

    // ---- one settings row at a time --------------------------------------
    for (const row of CANDIDATES) {
      const [name, mode, , , label, contextName] = row;
      const id = row[container.idIndex];
      const question = `observe: does writing a non-default ${name} (${label}) stick on the ${where}`;
      const push = (written, readBack, before, sticks, status, error) => {
        ROWS.push({ container: where, property: name, written, readBack, before, sticks, status, error });
      };

      if (!controlOk) {
        record(id, question, 'VOID',
               `the Description control failed on this ${where}, so a settings write that `
               + 'appeared not to take cannot be told from a broken method', 'void');
        push(null, null, null, null, null, 'void: the Description control failed');
        continue;
      }

      const before = await readProperty(container, name);
      if (!before.ok) {
        record(id, question, 'NOT ESTABLISHED',
               `reading ${name} through $select returned HTTP ${before.status}, so this `
               + `${where} does not expose it and nothing was written`);
        push(null, null, null, null, before.status, `$select refused: HTTP ${before.status}`);
        continue;
      }

      const target = targetFor(mode, before.value);
      if (target === undefined) {
        record(id, question, 'NOT ESTABLISHED',
               `${name} read back as ${show(before.value)}, which is not the type this row `
               + 'knows how to choose a differing value for, so nothing was written');
        push(null, null, before.value, null, before.status,
             `unexpected type ${typeof before.value}`);
        continue;
      }
      if (sameValue(target, before.value)) {
        record(id, question, 'NOT ESTABLISHED',
               `${name} already reads ${show(before.value)} on this ${where}, which is the `
               + 'value this row would write, so a readback equal to it would prove nothing. '
               + 'Nothing was written');
        push(null, null, before.value, null, before.status, 'already at the target value');
        continue;
      }

      // Minor versions mean nothing while versioning is off, so the row
      // carries the container's versioning state rather than leaving a
      // reader to infer it from the table order.
      let context = '';
      if (contextName) {
        const seen = await readProperty(container, contextName);
        context = seen.ok
          ? `. ${contextName} was ${show(seen.value)} at the time`
          : `. ${contextName} could not be read (HTTP ${seen.status})`;
      }

      const wrote = await merge(container.path, { [name]: target });
      const after = await readProperty(container, name);
      const errorText = wrote.ok ? '' : wrote.text.slice(0, 240);

      if (!after.ok) {
        record(id, question, 'NOT ESTABLISHED',
               `the MERGE returned HTTP ${wrote.status} and reading ${name} back returned `
               + `HTTP ${after.status}, so whether it stuck is unknown${context}`);
        push(target, null, before.value, null, wrote.status,
             errorText || `readback failed HTTP ${after.status}`);
        continue;
      }

      const stuck = sameValue(target, after.value);
      const outcome = stuck ? 'STICKS'
        : wrote.ok ? 'SILENTLY IGNORED'
        : isRefusal(wrote.status) ? 'REFUSED'
        : 'NOT ESTABLISHED';
      const evidence = stuck
        ? `wrote ${show(target)} (was ${show(before.value)}), HTTP ${wrote.status}, read back ${show(after.value)}${context}`
        : outcome === 'SILENTLY IGNORED'
          ? `wrote ${show(target)} (was ${show(before.value)}) and SharePoint answered HTTP `
            + `${wrote.status}, but it reads back ${show(after.value)}. Accepted and inert${context}`
          : outcome === 'REFUSED'
            ? `wrote ${show(target)} (was ${show(before.value)}), refused HTTP ${wrote.status}: `
              + `${errorText}. It still reads back ${show(after.value)}${context}`
            : `wrote ${show(target)} (was ${show(before.value)}), HTTP ${wrote.status}: ${errorText}. `
              + `It reads back ${show(after.value)}, and this status says nothing about the content sent${context}`;
      record(id, question, outcome, evidence);
      push(target, after.value, before.value, stuck, wrote.status, errorText);
    }
  }

  console.log('\n============ SETTINGS ROWS (machine-readable) ============');
  console.log(JSON.stringify(ROWS, null, 1));
  console.log('==========================================================');
  console.table(ROWS);

  report();

  if (CLEANUP_AT_END) {
    for (const container of CONTAINERS) {
      const digest = await getDigest();
      const gone = await spPost(`${container.path}/recycle`, {}, digest);
      log(gone.ok ? 'OK' : 'FAIL',
          gone.ok
            ? `Recycled '${container.title}'. It is recoverable from the site recycle bin.`
            : `Could not recycle '${container.title}': HTTP ${gone.status} ${gone.text.slice(0, 200)}`);
    }
  } else {
    log('INFO', `Scratch containers remain: '${LIST}' and '${LIB}'.`);
    log('INFO', 'After copying both blocks back, set CLEANUP_AT_END = true and paste again.');
  }
})();
