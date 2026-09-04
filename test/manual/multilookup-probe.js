/**
 * MULTI-VALUE LOOKUP PROBE.
 *
 * Creates two owned lists and asks whether a multi-value lookup can be
 * provisioned at all, whether it can be indexed, whether the multiplicity can
 * be changed after the fact, what an item write and read look like, and which
 * CAML predicates a filter over one may be written in. None of that is known
 * today. #409 asks four questions and this probe is the machine half of all
 * four.
 *
 * Ids follow the grammar in `test/manual/SURFACES.md`,
 * `<surface>.<scope>.<question>`. `multilookup` was reserved as a scope under
 * the `field` surface when the grammar landed and nothing has filed under it
 * until now, so there are no mnemonics to carry across:
 *
 *   field.multilookup.fixture-lists-created
 *   field.multilookup.control-single-value-lookup-created
 *   field.multilookup.create-readback-type              (#409 question 1)
 *   field.multilookup.control-single-value-indexed
 *   field.multilookup.indexed-property                  (#409 question 2)
 *   field.multilookup.allow-multiple-values-mutability  (#409 question 3)
 *   field.multilookup.item-write-shape                  (#409 question 4)
 *   field.multilookup.item-read-shape                   (#409 question 4)
 *   field.multilookup.control-source-title-indexed      (index source-carry)
 *   field.multilookup.source-index-carry                (index source-carry)
 *   field.multilookup.source-index-carry-at-create      (index source-carry)
 *   field.lookup.source-index-carry                     (index source-carry)
 *   field.multilookup.fixture-caml-rows-seeded          (CAML grammar)
 *   query.caml-adhoc.multilookup-eq-text                (CAML grammar)
 *   query.caml-adhoc.multilookup-eq-lookupid            (CAML grammar)
 *   query.caml-adhoc.multilookup-includes-text          (CAML grammar)
 *   query.caml-adhoc.multilookup-includes-lookupid      (CAML grammar)
 *   query.caml-adhoc.multilookup-neq-text               (CAML grammar)
 *   query.caml-adhoc.multilookup-neq-lookupid           (CAML grammar)
 *   query.caml-adhoc.multilookup-notincludes-text       (CAML grammar)
 *   query.caml-adhoc.multilookup-notincludes-lookupid   (CAML grammar)
 *   query.caml-adhoc.multilookup-in-text                (CAML grammar)
 *   query.caml-adhoc.multilookup-in-lookupid            (CAML grammar)
 *   query.caml-adhoc.multilookup-isnull                 (CAML grammar)
 *   query.caml-adhoc.multilookup-isnotnull              (CAML grammar)
 *   query.caml-adhoc.multilookup-and-membership         (CAML grammar)
 *   query.caml-adhoc.multilookup-or-membership          (CAML grammar)
 *   query.caml-adhoc.multilookup-neq-isnull-wrapper     (CAML grammar)
 *
 * The two controls ask single-VALUE lookup questions, and they exist only to
 * make the multi-value answers readable, so they take the `multilookup` scope
 * of the questions they guard. That follows
 * `field.multichoice.control-single-value-indexed`, which is a single-value
 * Choice question filed under `multichoice` for the same reason.
 *
 * ONE ROW FILES UNDER ANOTHER SCOPE. `field.lookup.source-index-carry` asks
 * what a SINGLE-value lookup's `Indexed` reads back as over an indexed source,
 * and under SURFACES.md's keying rule a check is keyed to the surface of its
 * own question rather than its probe's. It is not a `control-` row: both of
 * its outcomes are informative, and neither voids anything. It is here because
 * without it "the multi-value one reads false" cannot be told apart from "no
 * lookup's `Indexed` ever mirrors its source", which are different findings
 * and only one of them is about multiplicity.
 *
 * WHAT SOURCE-CARRY IS NOT. `Indexed` reading false does not establish that a
 * query over the column is unindexed at size. That is a `scale.index` question
 * over a list past the 5,000-item threshold, which this fixture is nowhere
 * near, and no row here may be read as answering it.
 *
 * THE PREDICATE ROWS FILE UNDER `query`. Fifteen rows below ask what a CAML
 * predicate over a multi-value lookup returns. The subject of each is the
 * query language rather than the column, so under SURFACES.md's keying rule
 * they take `query.caml-adhoc`, exactly as `multi-value-probe.js`'s predicate
 * rows do from a `field`-surface probe. `caml-adhoc` rather than `caml`
 * because these are issued through `GetItems`, not read off a saved view.
 * The fixture row that builds the four items they are read against stays
 * `field.multilookup`, because seeding a column is a column question.
 *
 * WHY THEY ARE ASKED AT ALL. `analysis/condition_rendering.py` carries a
 * multi-value CAML vocabulary measured on 2026-08-10, where the documented
 * `<Includes>` returned an empty set with no error and the undocumented
 * `<Eq>` did the membership test. That was measured against a MultiChoice
 * column and against nothing else, so `analysis/conditions.py` refuses a
 * filter on a multi-value LOOKUP rather than assume the two share a grammar.
 * The fixture here is a deliberate analogue of that one so the two runs can be
 * compared row for row.
 *
 * THE JOIN ROWS ALSO FILE UNDER ANOTHER SURFACE. #409's remaining question,
 * whether a multi-value lookup costs one join or more against the ceiling of
 * 12 in `analysis/joins.py`, is measured here by the two `scale.join` rows.
 * SURFACES.md gives `scale` the join limits, and the subject is the ceiling
 * rather than the column, so they key there, as `threshold-index-probe.js`'s
 * join rows already do. `analysis/joins.py` counts a multi-value lookup as one
 * join and its docstring records that as inferred rather than measured; these
 * rows report a NUMBER, not a confirmation.
 *
 *   scale.join.control-ceiling-small-list
 *   scale.join.multi-value-lookup-costs-a-join
 *
 * The control is a real control. This list holds four items and the ceiling
 * was only ever measured past the item threshold, so if no ceiling appears
 * here the cost row is void rather than reassuring, and the question goes to
 * `threshold-index-probe.js`'s 6,000-row fixture instead.
 *
 * WHAT THIS PROBE MUST NOT ASSERT. SharePoint has no distinct multi-value
 * lookup entity type: the column is an `SP.FieldLookup` carrying
 * `AllowMultipleValues`. What it then reports as `TypeAsString` and
 * `FieldTypeKind` is the question, so no row here compares either against an
 * expected value. Each records what came back. Asserting the value the
 * question is asking for is the failure AGENTS.md names, and it would make
 * this probe kill itself the moment it started working.
 *
 * THE ONE VALUE THAT IS ASSERTED is `AllowMultipleValues` on read-back, and
 * only when deciding which create path won. A field that was accepted and is
 * not multi-value would answer the index and item questions about a
 * single-value column while the transcript said otherwise, which is worse
 * than no answer. So a candidate only wins if the flag reads back true, and
 * a field that fails that test is deleted before the next candidate runs.
 *
 * RELATED. `library-column-interactions-probe.js` registers
 * `library.column.multi-lookup-column-on-library`, which asks whether a
 * multi-value lookup works on a document LIBRARY, and supplies the
 * `createfieldasxml` spelling reused as a create candidate below. It has no
 * recorded run. Under the "two subjects, two methods, two ids" rule in
 * SURFACES.md a library and a list are different subjects, so neither row
 * settles the other.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const PROBE_RETRY_TRANSIENT = true;
  const PROBE_RETRY_ATTEMPTS = 5;
  // CLEANUP governs both ends: it recycles a fixture left by a previous run
  // before this one starts, and recycles this run's fixture at the end. With
  // it off, a second run finds its own lists still standing and stops rather
  // than reporting "already present" as though it had measured something.
  const CLEANUP = false;
  const TARGET_LIST = 'zzz dbmlsp multilookup target';
  const PROBE_LIST = 'zzz dbmlsp multilookup probe';
  // How many empty single-value lookups the join block creates to walk up to
  // the ceiling with. 14 is what threshold-index-probe.js used to find 12, so
  // it leaves headroom on either side of the documented number. Set it to 0 to
  // skip the join rows and everything they cost.
  const JOIN_COLUMNS = 14;
  // ------------------------------------------------------------------------

  // The three columns on the probe list. All three point at the same target
  // list through the same display field, so a difference in behaviour between
  // them can only be the multiplicity.
  //
  //   SINGLE  the control. Created by the deployer's own AddField path, and
  //           the subject of the index control.
  //   FLIP    created single-valued and then widened, and narrowed again.
  //           Kept apart from SINGLE so the index control is never asked
  //           about a column this probe has mutated.
  //   MULTI   the column under test.
  //
  // Two more are created LATER, once the target's Title has been indexed, so
  // that "created over an indexed source" is asked as its own case rather than
  // inferred from a column that predates the index:
  //
  //   SINGLE_SRC  a single-value lookup over the indexed source, never itself
  //               written to with Indexed. SINGLE cannot do this job: the
  //               index control writes Indexed on it directly, so its `Indexed`
  //               is true for a reason that has nothing to do with the source.
  //   MULTI_SRC   the multi-value column over the indexed source.
  //
  // The join block adds Join1..JoinN last, after every other question has been
  // recorded, because they exist to be counted rather than read and putting
  // twenty lookups on the list earlier would give any refusal above a second
  // possible cause.
  const SINGLE = 'Party';
  const FLIP = 'PartyFlip';
  const MULTI = 'Parties';
  const SINGLE_SRC = 'PartySrc';
  const MULTI_SRC = 'PartiesSrc';
  // Three rows so that "the two that were asked for" is distinguishable from
  // "every row in the target list". The write-shape rows use the first two
  // only; the CAML fixture uses all three, because a predicate that returns
  // everything and a predicate that is right have to look different.
  const TARGET_ROWS = ['Alpha', 'Bravo', 'Charlie'];

  // Shared result registry v1. Register findings before any network work.
  //
  // STATE carries the coarse answer alongside the prose, from the five-value
  // vocabulary in test/manual/SURFACES.md: settled, open, awaiting-capture,
  // void, needs-human. An explicit state passed to record() always wins; the
  // classifier is the default for the rows nobody has ruled on yet.
  // ABORTED is open: it means the fixture never built, so the question was
  // never asked and the run has nothing to settle it with.
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT', 'ABORTED'];
  const AWAITING_CAPTURE_HEADS = ['MANUAL', 'NOT REACHED'];
  const stateFor = (observed) => {
    if (AWAITING_CAPTURE_HEADS.some((p) => observed.startsWith(p))) return 'awaiting-capture';
    if (OPEN_HEADS.some((p) => observed.startsWith(p))) return 'open';
    return 'settled';
  };
  const results = [];
  const expect = (id, question) => {
    results.push({
      id,
      question,
      observed: 'NOT ESTABLISHED',
      detail: 'the run did not reach this question',
      state: 'open',
    });
  };
  const record = (id, question, observed, detail, state) => {
    const next = {
      question, observed, detail: detail || '', state: state || stateFor(observed),
    };
    const row = results.find((candidate) => candidate.id === id);
    if (row) {
      Object.assign(row, next);
    } else {
      results.push({ id, ...next });
    }
    log('INFO', `${id}: ${observed}${detail ? `: ${detail}` : ''}`);
  };
  expect('field.multilookup.fixture-lists-created', 'the fixture actually built: two lists, three target rows, the control columns');
  expect('field.multilookup.control-single-value-lookup-created', 'CONTROL: a plain single-value Lookup into the target is created by the deployer\'s own AddField path');
  expect('field.multilookup.create-readback-type', 'which create path takes AllowMultipleValues:true, and what the field reads back as');
  expect('field.multilookup.control-single-value-indexed', 'CONTROL: Indexed:true on the SINGLE-value Lookup, which this repository already provisions');
  expect('field.multilookup.indexed-property', 'Indexed:true on a multi-value Lookup: accepted? and what does it read back as?');
  expect('field.multilookup.control-source-title-indexed', 'CONTROL: the TARGET list\'s Title, the column a lookup projects, takes Indexed:true');
  expect('field.multilookup.source-index-carry', 'Does an EXISTING multi-value lookup read back Indexed once its source is indexed?');
  expect('field.multilookup.source-index-carry-at-create', 'Does a multi-value lookup CREATED over an indexed source read back Indexed?');
  expect('field.lookup.source-index-carry', 'Does a SINGLE-value lookup over an indexed source read back Indexed?');
  expect('field.multilookup.allow-multiple-values-mutability', 'AllowMultipleValues on an EXISTING lookup: can it be turned on, and can it be turned off again?');
  expect('field.multilookup.item-write-shape', 'which item WRITE shapes SharePoint accepts for a multi-value lookup');
  expect('field.multilookup.item-read-shape', 'what a multi-value lookup value READS BACK as');
  expect('field.multilookup.fixture-caml-rows-seeded', 'the four-row CAML fixture built, and holding the members it was given');
  expect('query.caml-adhoc.multilookup-eq-text', 'CAML <Eq> with a text operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-eq-lookupid', 'CAML <Eq> with a LookupId operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-includes-text', 'CAML <Includes> with a text operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-includes-lookupid', 'CAML <Includes> with a LookupId operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-neq-text', 'CAML <Neq> with a text operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-neq-lookupid', 'CAML <Neq> with a LookupId operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-notincludes-text', 'CAML <NotIncludes> with a text operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-notincludes-lookupid', 'CAML <NotIncludes> with a LookupId operand over a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-in-text', 'CAML <In> over a text <Values> list on a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-in-lookupid', 'CAML <In> over a LookupId <Values> list on a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-isnull', 'CAML <IsNull> on a multi-value lookup: does it find the row that was never given a value?');
  expect('query.caml-adhoc.multilookup-isnotnull', 'CAML <IsNotNull> on a multi-value lookup: which rows?');
  expect('query.caml-adhoc.multilookup-and-membership', 'CAML <And> of two membership tests on one multi-value lookup: is it "contains BOTH"?');
  expect('query.caml-adhoc.multilookup-or-membership', 'CAML <Or> of two membership tests on one multi-value lookup: is it "contains EITHER"?');
  expect('query.caml-adhoc.multilookup-neq-isnull-wrapper', 'the deployer\'s own not_includes wrapper (negation OR IsNull) on a multi-value lookup: which rows?');
  expect('scale.join.control-ceiling-small-list', 'CONTROL: does the join ceiling bite on a SMALL list, or only past the item threshold?');
  expect('scale.join.multi-value-lookup-costs-a-join', 'How many joins does a multi-value lookup cost against the view ceiling?');

  // Shared probe core v2: context guard, bounded transport and REST helpers.
  const log = (level, msg) => console.log(`[SP-PROBE] [${level}] ${msg}`);
  if (typeof _spPageContextInfo === 'undefined') {
    log('ERROR', '_spPageContextInfo is not available on this page; cannot resolve the web context. Open /_layouts/15/settings.aspx and retry.');
    return { aborted: 'no-sp-page-context' };
  }
  const WEB = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (!CONFIRMED) {
    log('INFO', `This page is ${window.location.origin}${WEB || '/'}.`);
    log('INFO', 'If that is the site you want, set CONFIRMED = true and paste again.');
    return { aborted: 'unconfirmed' };
  }
  const probeWrites = typeof PROBE_WRITES === 'undefined' ? true : PROBE_WRITES;
  if (probeWrites && !ALLOW_WRITES) {
    log('INFO', 'This probe writes only its declared fixture. Set ALLOW_WRITES = true to proceed.');
    return { aborted: 'writes-disabled' };
  }
  const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  log('INFO', `probe revision a34d8c1b; core v2; results v1.`);
  log('INFO', `Running as ${_spPageContextInfo.userLoginName || '(unknown)'} on web '${WEB || '(root)'}'.`);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const spError = (text) => {
    try {
      const parsed = JSON.parse(text);
      return parsed?.error?.message?.value
        || parsed?.odata?.error?.message?.value
        || String(text).slice(0, 300);
    } catch {
      return String(text).slice(0, 300);
    }
  };
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 503;
  async function fetchWithRetry(url, options, attempts = PROBE_RETRY_ATTEMPTS) {
    for (let attempt = 0; ; attempt += 1) {
      const response = await fetch(url, options);
      const transient = response.status === 429 || response.status === 503;
      if (PROBE_RETRY_TRANSIENT && transient && attempt < attempts) {
        const retryAfter = Number(response.headers.get('Retry-After'))
          || Math.min(2 ** attempt, 30);
        log('INFO', `Throttled (HTTP ${response.status}); retry ${attempt + 1}/${attempts} in ${retryAfter}s.`);
        await sleep(retryAfter * 1000);
        continue;
      }
      return response;
    }
  }
  let cachedDigest = null;
  let digestExpiresAt = 0;
  async function getDigest() {
    if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;
    const response = await fetchWithRetry(apiUrl('contextinfo'), {
      method: 'POST',
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`contextinfo failed HTTP ${response.status}: ${spError(text)}`);
    }
    const info = JSON.parse(text)?.d?.GetContextWebInformation;
    if (!info?.FormDigestValue) throw new Error('contextinfo omitted FormDigestValue');
    cachedDigest = info.FormDigestValue;
    digestExpiresAt = Date.now()
      + Math.max((Number(info.FormDigestTimeoutSeconds) || 1800) - 60, 60) * 1000;
    return cachedDigest;
  }
  const spHeaders = (digest, extra = {}) => ({
    'Accept': 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
    'X-RequestDigest': digest,
    ...extra,
  });
  async function post(suffix, body, extraHeaders) {
    const digest = await getDigest();
    const response = await fetchWithRetry(apiUrl(suffix), {
      method: 'POST',
      headers: spHeaders(digest, extraHeaders || {}),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: spError(text),
        d: null,
      };
    }
    let d = null;
    try {
      d = text ? JSON.parse(text).d : null;
    } catch {
      d = null;
    }
    return { ok: true, status: response.status, error: null, d };
  }
  async function get(suffix, accept) {
    const response = await fetchWithRetry(apiUrl(suffix), {
      method: 'GET',
      headers: { 'Accept': accept || 'application/json;odata=verbose' },
    });
    const text = await response.text();
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: spError(text),
        d: null,
      };
    }
    const parsed = JSON.parse(text);
    return {
      ok: true,
      status: response.status,
      error: null,
      d: parsed.d !== undefined ? parsed.d : parsed,
    };
  }
  const merge = (suffix, body) => post(
    suffix,
    body,
    { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
  );
  async function entityTypeFor(listTitle) {
    const response = await get(
      `web/lists/getbytitle('${odataName(listTitle)}')?$select=ListItemEntityTypeFullName`,
    );
    if (!response.ok) {
      throw new Error(`could not resolve the item entity type: ${response.error}`);
    }
    return response.d.ListItemEntityTypeFullName;
  }
  // Shared list fixture v1: exact ownership checks and bounded recycle.
  // Title is never treated as ownership. Callers supply a stable description.
  async function inspectOwnedList(title, ownershipDescription) {
    const listPath = `web/lists/getbytitle('${odataName(title)}')`;
    const existing = await get(`${listPath}?$select=Id,Description`);
    if (!existing.ok) {
      if (existing.status === 404) return { state: 'missing', listPath, d: null };
      return {
        state: 'error', listPath, d: null,
        error: `HTTP ${existing.status}: ${existing.error}`,
      };
    }
    if (existing.d.Description !== ownershipDescription) {
      return {
        state: 'foreign', listPath, d: existing.d,
        error: `A same-title list '${title}' exists without the exact probe ownership marker; refusing to modify it.`,
      };
    }
    return { state: 'owned', listPath, d: existing.d };
  }

  async function recycleOwnedList(title, ownershipDescription) {
    const inspected = await inspectOwnedList(title, ownershipDescription);
    if (inspected.state === 'missing') return { ok: true, removed: false };
    if (inspected.state !== 'owned') {
      return { ok: false, removed: false, error: inspected.error };
    }
    const recycled = await post(`${inspected.listPath}/recycle`);
    return {
      ok: recycled.ok,
      removed: recycled.ok,
      error: recycled.ok ? null : `HTTP ${recycled.status}: ${recycled.error}`,
    };
  }

  async function prepareOwnedList(title, ownershipDescription, removeExisting) {
    const inspected = await inspectOwnedList(title, ownershipDescription);
    if (inspected.state === 'foreign' || inspected.state === 'error') {
      return { ok: false, existing: null, error: inspected.error };
    }
    if (inspected.state === 'owned' && removeExisting) {
      const recycled = await recycleOwnedList(title, ownershipDescription);
      if (!recycled.ok) return { ok: false, existing: null, error: recycled.error };
      return { ok: true, existing: null, removed: true };
    }
    return {
      ok: true,
      existing: inspected.state === 'owned' ? inspected.d : null,
      removed: false,
    };
  }

  const TARGET_OWNERSHIP = 'dbml-sharepoint multi-value lookup probe target. Safe to delete.';
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint multi-value lookup probe. Safe to delete.';
  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const targetPath = `web/lists/getbytitle('${odataName(TARGET_LIST)}')`;
  const fieldPath = (name) => `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;
  // Every URL this probe logs is built on a literal placeholder rather than
  // window.location.origin, because the results get pasted back into an issue.
  // The shared pre-flight banner above prints the real host on purpose, and it
  // runs only while CONFIRMED is false, so it is never part of a transcript.
  const TENANT = '[TENANT]';
  let createdProbeList = false;
  let createdTargetList = false;

  const show = (value) => {
    try { return JSON.stringify(value); } catch { return String(value); }
  };
  const httpNote = (r) => (r.ok ? `HTTP ${r.status}` : `REFUSED HTTP ${r.status} ${r.error}`);
  const deleteField = (name) => post(
    fieldPath(name), undefined, { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' },
  );
  const dump = () => console.table(results.map(
    ({ id, question, observed, detail }) => ({ id, question, observed, detail }),
  ));
  // A setup failure returns rather than throwing, so the table still prints.
  // A thrown error would leave every row at its NOT ESTABLISHED placeholder
  // with nothing on screen saying which of them were never asked.
  const bail = (reason) => {
    dump();
    log('ERROR', `Setup failed (${reason}). Nothing below it was measured.`);
    return { aborted: reason, results };
  };

  try {
    // === Setup: two lists =================================================
    // The probe list is prepared FIRST. Its lookups reference the target, and
    // SharePoint refuses to recycle a list another list looks up into, so a
    // cleanup that took the target first would fail and leave both standing.
    const preparedProbe = await prepareOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION, CLEANUP);
    const preparedTarget = await prepareOwnedList(TARGET_LIST, TARGET_OWNERSHIP, CLEANUP);
    if (!preparedProbe.ok || !preparedTarget.ok) {
      record('field.multilookup.fixture-lists-created', 'setup', 'ABORTED',
        `${preparedProbe.error || ''} ${preparedTarget.error || ''}`.trim());
      return bail('fixture-ownership');
    }
    if (preparedProbe.existing || preparedTarget.existing) {
      record('field.multilookup.fixture-lists-created', 'setup', 'ABORTED',
        `A fixture from a previous run is still in place (${preparedProbe.existing ? PROBE_LIST : ''}`
        + `${preparedProbe.existing && preparedTarget.existing ? ', ' : ''}`
        + `${preparedTarget.existing ? TARGET_LIST : ''}). Every question below would be answered by `
        + 'columns that run created, which is much weaker evidence than creating them. Re-run with '
        + 'CLEANUP = true.');
      return bail('fixture-retained');
    }

    const madeTarget = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: TARGET_LIST,
      Description: TARGET_OWNERSHIP,
    });
    if (!madeTarget.ok) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        `could not create the target list: HTTP ${madeTarget.status} ${madeTarget.error}`);
      return bail('target-list-not-created');
    }
    createdTargetList = true;
    const madeProbe = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: PROBE_LIST,
      Description: OWNERSHIP_DESCRIPTION,
    });
    if (!madeProbe.ok) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        `could not create the probe list: HTTP ${madeProbe.status} ${madeProbe.error}`);
      return bail('probe-list-not-created');
    }
    createdProbeList = true;
    // The target's GUID, not its title: a lookup is created by LookupListId,
    // and `List="{...}"` in field XML wants the same value.
    const targetListId = madeTarget.d?.Id || null;
    log('INFO', `Created '${TARGET_LIST}' (${targetListId}) and '${PROBE_LIST}'.`);
    if (!targetListId) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        'the target list was created but its Id was not in the response, so no lookup can name it');
      return bail('target-list-id-unknown');
    }

    // Seed the target. Checked rather than assumed: a lookup into an empty
    // list creates cleanly and then has no id to write, which would read as
    // the item questions failing.
    let targetType = null;
    try {
      targetType = await entityTypeFor(TARGET_LIST);
    } catch (err) {
      record('field.multilookup.fixture-lists-created', 'the fixture actually built', 'ABORTED',
        `could not resolve the target list's item entity type: ${err.message}`);
      return bail('target-entity-type-unknown');
    }
    const seedErrors = [];
    const targetIds = [];
    for (const title of TARGET_ROWS) {
      const seeded = await post(`${targetPath}/items`, {
        __metadata: { type: targetType }, Title: title,
      });
      if (seeded.ok && seeded.d?.Id !== undefined) targetIds.push(seeded.d.Id);
      else seedErrors.push(`${title}: HTTP ${seeded.status} ${seeded.error}`);
    }
    // The two ids every item write below uses. Charlie is deliberately left
    // out so a write that stores every row is distinguishable from one that
    // stores the pair it was given.
    const WRITE_IDS = targetIds.slice(0, 2);

    // === control-single-value-lookup-created ==============================
    // The deployer's own create path, unchanged. SharePoint refuses a plain
    // POST of SP.FieldLookup to /fields ("Please use addfield to add a lookup
    // field"), which is why deploy.js uses FieldCollection.AddField with an
    // SP.FieldCreationInformation nested under `parameters`. See
    // templates/deploy/_lists.js.j2. If this refuses, nothing below can
    // attribute a refusal to multiplicity rather than to the lookup machinery.
    const addLookup = (title, extra) => post(`${listPath}/fields/addfield`, {
      parameters: {
        __metadata: { type: 'SP.FieldCreationInformation' },
        FieldTypeKind: 7,
        Title: title,
        LookupListId: targetListId,
        LookupFieldName: 'Title',
        ...(extra || {}),
      },
    });
    const madeSingle = await addLookup(SINGLE);
    const singleBack = await get(
      `${fieldPath(SINGLE)}?$select=InternalName,TypeAsString,FieldTypeKind,AllowMultipleValues,Indexed,LookupList,LookupField`,
    );
    const controlLookupHeld = madeSingle.ok && singleBack.ok;
    record(
      'field.multilookup.control-single-value-lookup-created',
      'CONTROL: a plain single-value Lookup into the target is created by the deployer\'s own AddField path',
      controlLookupHeld ? 'CREATED' : (madeSingle.ok ? 'CREATED, READBACK UNREADABLE' : 'REFUSED'),
      `AddField ${httpNote(madeSingle)}, readback ${singleBack.ok
        ? `TypeAsString=${show(singleBack.d?.TypeAsString)} FieldTypeKind=${show(singleBack.d?.FieldTypeKind)} `
          + `AllowMultipleValues=${show(singleBack.d?.AllowMultipleValues)} LookupList=${show(singleBack.d?.LookupList)}`
        : `FAILED HTTP ${singleBack.status} ${singleBack.error}`}. `
      + 'A refusal here is about lookups, the target list or this identity, and NOT about multiplicity. '
      + 'Every multi-value row below is void while it stands.',
    );

    // === create-readback-type (#409 question 1) ===========================
    // Three candidate create paths, tried in order and ALL recorded. The
    // ordering is cheapest-first for the deployer: the first would need no new
    // creation machinery at all, the second needs a second create path beside
    // AddField, and the third needs a create followed by a patch.
    //
    // Candidate 1 is the deployer's AddField call with the flag added.
    // SP.FieldCreationInformation is not documented to carry
    // AllowMultipleValues, so the interesting outcome is not a refusal but an
    // ACCEPTED whose readback says false: a create that silently drops the one
    // property being asked for is exactly the failure class this directory
    // exists to catch.
    //
    // Candidate 2 is the createfieldasxml spelling
    // library-column-interactions-probe.js already carries for a library, on
    // the same `Options: 8` call projected-lookup-probe.js proved works for a
    // dependent lookup. A refusal here does not separate "SharePoint Online
    // will not make one this way" from "this attribute spelling is wrong", and
    // the recorded detail says so rather than crediting the stronger reading.
    //
    // Candidate 3 creates a plain lookup and patches the flag on. It uses the
    // same mechanism the mutability row measures independently on its own
    // field, which is a replication rather than waste: if one works and the
    // other does not, that disagreement is itself the finding.
    //
    // Each candidate takes the COLUMN NAME rather than closing over MULTI, so
    // the winner can be replayed for the second multi-value column the
    // source-index rows need. One spelling of each create path, used twice.
    const createCandidates = [
      {
        name: 'addfield-allowmultiplevalues',
        run: (name) => addLookup(name, { AllowMultipleValues: true }),
      },
      {
        name: 'createfieldasxml-lookupmulti',
        run: (name) => post(`${listPath}/fields/createfieldasxml`, {
          parameters: {
            SchemaXml: `<Field Type="LookupMulti" Mult="TRUE" DisplayName="${name}" `
              + `Name="${name}" List="{${targetListId}}" ShowField="Title"/>`,
            Options: 8,
          },
        }),
      },
      {
        name: 'addfield-then-merge-allowmultiplevalues',
        run: async (name) => {
          const made = await addLookup(name);
          if (!made.ok) return made;
          return merge(fieldPath(name), {
            __metadata: { type: 'SP.FieldLookup' }, AllowMultipleValues: true,
          });
        },
      },
    ];
    const FIELD_SELECT = '?$select=Id,InternalName,Title,TypeAsString,FieldTypeKind,'
      + 'AllowMultipleValues,Indexed,EnforceUniqueValues,LookupList,LookupField';
    const createAttempts = [];
    let winningCreate = null;
    let multiShape = null;
    if (controlLookupHeld) {
      for (const candidate of createCandidates) {
        const attempt = await candidate.run(MULTI);
        const back = await get(`${fieldPath(MULTI)}${FIELD_SELECT}`);
        createAttempts.push(
          `${candidate.name}: write ${httpNote(attempt)}, readback ${back.ok
            ? `TypeAsString=${show(back.d?.TypeAsString)} FieldTypeKind=${show(back.d?.FieldTypeKind)} `
              + `AllowMultipleValues=${show(back.d?.AllowMultipleValues)}`
            : `FAILED HTTP ${back.status} ${back.error}`}`,
        );
        if (back.ok && back.d?.AllowMultipleValues === true) {
          winningCreate = candidate;
          multiShape = back;
          break;
        }
        // A field that exists and is not multi-value has to go: it would block
        // the next candidate on its name, and left in place it would answer the
        // index and item rows about a single-value column.
        if (back.ok) {
          const removed = await deleteField(MULTI);
          if (!removed.ok) {
            createAttempts.push(
              `(the field ${candidate.name} left behind could not be deleted: `
              + `HTTP ${removed.status} ${removed.error}, so every candidate after it is blocked on the name)`,
            );
            break;
          }
        }
      }
    }
    record(
      'field.multilookup.create-readback-type',
      'which create path takes AllowMultipleValues:true, and what the field reads back as',
      controlLookupHeld
        ? (winningCreate ? `CREATED: ${winningCreate.name}` : 'NO CREATE PATH ACCEPTED')
        : 'NOT ESTABLISHED',
      controlLookupHeld
        ? `tried in order ${createCandidates.map((c) => c.name).join(', ')}. `
          + `${createAttempts.join(' || ')}. `
          + (winningCreate
            ? `The winning field reads back TypeAsString=${show(multiShape.d?.TypeAsString)} `
              + `FieldTypeKind=${show(multiShape.d?.FieldTypeKind)} `
              + `AllowMultipleValues=${show(multiShape.d?.AllowMultipleValues)} `
              + `Indexed=${show(multiShape.d?.Indexed)} `
              + `EnforceUniqueValues=${show(multiShape.d?.EnforceUniqueValues)} `
              + `LookupList=${show(multiShape.d?.LookupList)} LookupField=${show(multiShape.d?.LookupField)} `
              + `entity type=${show(multiShape.d?.__metadata?.type)}. `
              + 'Report TypeAsString and FieldTypeKind verbatim: the reconciler\'s shape check has to '
              + 'recognise whatever this is, and nothing in the codebase knows it yet.'
            : 'No candidate produced a field that reads back AllowMultipleValues=true, so the index and '
              + 'item rows below have no multi-value column to ask about. A candidate that was ACCEPTED '
              + 'and read back false is the dangerous outcome, not the harmless one: the create would '
              + 'succeed, the deploy would verify, and the column would be single-valued. A refusal of '
              + 'the createfieldasxml candidate does not separate a capability SharePoint Online lacks '
              + 'from an attribute spelling this probe got wrong.')
        : 'the single-value lookup control did not hold, so a refusal here cannot be attributed to '
          + 'multiplicity rather than to lookups on this list or this identity.',
      controlLookupHeld ? undefined : 'void',
    );
    // The entity type SharePoint itself reported for the field, used for every
    // patch below. Guessing it is avoidable here: an SP.FieldLookup that
    // reports some other type would refuse a MERGE naming the wrong one, and
    // that refusal would be recorded as an answer about Indexed.
    const multiMetaType = multiShape?.d?.__metadata?.type || 'SP.FieldLookup';
    // ASCII by construction (`Parties`), but read back rather than assumed:
    // the item write shape is keyed on the INTERNAL name, and a create path
    // that renamed the column would make every item row 400 for a reason that
    // has nothing to do with multiplicity.
    const multiName = multiShape?.d?.InternalName || MULTI;
    const idField = `${multiName}Id`;

    // === control-single-value-indexed / indexed-property (#409 question 2) =
    // The index question and its control, in the shape multi-value-probe.js
    // uses for the same pair. A single-value lookup carrying Indexed is a
    // shipping path here: SP.FieldCreationInformation has no Indexed, so a
    // [unique] lookup gets both Indexed and EnforceUniqueValues from the MERGE
    // reconcileDeclaredField issues straight after AddField. If that control
    // does not hold, the property is not reporting what this question needs on
    // this tenant and both rows are void.
    //
    // The readback GET is kept rather than folded into a default. A readback
    // that never arrived is not an observation of false, and reporting it as
    // "did not stick" would state something this run never saw.
    const indexOne = async (path, metaType) => {
      const wrote = await merge(path, { __metadata: { type: metaType }, Indexed: true });
      const back = await get(`${path}?$select=Indexed`);
      return { wrote, back };
    };
    const notAttempted = { ok: false, status: 0, error: 'the field was never created' };
    const singleIndex = controlLookupHeld
      ? await indexOne(fieldPath(SINGLE), 'SP.FieldLookup')
      : { wrote: notAttempted, back: notAttempted };
    const multiIndex = winningCreate
      ? await indexOne(fieldPath(MULTI), multiMetaType)
      : { wrote: notAttempted, back: notAttempted };
    const indexReadback = (r) => (r.back.ok
      ? show(r.back.d?.Indexed)
      : `UNREADABLE (HTTP ${r.back.status} ${r.back.error})`);
    const indexControlHeld = singleIndex.wrote.ok && singleIndex.back.ok
      && singleIndex.back.d?.Indexed === true;
    record(
      'field.multilookup.control-single-value-indexed',
      'CONTROL: Indexed:true on the SINGLE-value Lookup, which this repository already provisions',
      indexControlHeld
        ? 'STUCK'
        : (singleIndex.wrote.ok && !singleIndex.back.ok ? 'READBACK UNREADABLE' : 'DID NOT STICK'),
      `write ${httpNote(singleIndex.wrote)}, readback Indexed=${indexReadback(singleIndex)}`,
    );
    record(
      'field.multilookup.indexed-property',
      'Indexed:true on a multi-value Lookup: accepted? and what does it read back as?',
      (indexControlHeld && winningCreate)
        ? (multiIndex.wrote.ok
          ? (multiIndex.back.ok
            ? (multiIndex.back.d?.Indexed === true ? 'ACCEPTED AND STUCK' : 'ACCEPTED BUT DID NOT STICK')
            : 'ACCEPTED, READBACK UNREADABLE')
          : 'REFUSED')
        : 'NOT ESTABLISHED',
      (indexControlHeld && winningCreate)
        ? `write ${httpNote(multiIndex.wrote)}, readback Indexed=${indexReadback(multiIndex)}. `
          + (multiIndex.wrote.ok && !multiIndex.back.ok
            ? 'The write was taken and the readback never arrived, so whether it stuck is NOT established '
              + 'by this run, and that is a different finding from a property that read back false. '
            : '')
          + 'REFUSED means every view filtering a multi-value lookup is a threshold hazard and the index '
          + 'validator needs a new refusal by name. ACCEPTED AND STUCK means it does not, and the '
          + 'existing index machinery extends to this column unchanged. ACCEPTED BUT DID NOT STICK is '
          + 'the one that needs a guard rather than a rule: the deploy would claim an index that is not '
          + 'there, and only a readback could ever see the difference.'
        : (winningCreate
          ? `the single-value index control did not hold (Indexed=${indexReadback(singleIndex)}), so this `
            + 'property is not reporting what the question needs on this tenant and the row is void. That '
            + 'is the outcome native-index-probe.js hit with its own control on 2026-07-30.'
          : 'no multi-value lookup column was created, so there was nothing to index.'),
      (indexControlHeld && winningCreate) ? undefined : 'void',
    );

    // === source-index-carry: does an indexed SOURCE show through? =========
    // The row above asks whether the multi-value column takes an index of its
    // own. This asks the question that outcome leaves open, and the answer
    // decides whether the rule the implementation added is "a multi-value
    // lookup can never be indexed" or "it cannot be indexed DIRECTLY, and
    // inherits its source's index".
    //
    // The source is the target list's `Title`, which is the column every
    // lookup here projects through `LookupFieldName`. Indexing it is a write
    // to the OTHER list, and it is the only write this probe makes outside the
    // probe list.
    //
    // Three readings, because creation order could matter and guessing which
    // way is exactly what this directory exists to stop:
    //
    //   MULTI      existed BEFORE the source was indexed. Re-read, and the
    //              direct Indexed:true write re-attempted, because a refusal
    //              that is conditional on the source's index is a different
    //              rule from an unconditional one.
    //   MULTI_SRC  created AFTER. If this reads true and MULTI does not, the
    //              deployer must index the target before creating the lookup.
    //   SINGLE_SRC the comparator, and the reason this block is readable at
    //              all. If a SINGLE-value lookup over the same indexed source
    //              also reads false, then `Indexed` on a lookup field is its
    //              own index and never mirrors its source, which is a fact
    //              about lookups rather than about multiplicity.
    //
    // NOTHING HERE IS ASSERTED. Each row records what came back. In
    // particular, `Indexed=false` is not recorded as "the source index does
    // not help": what a query does at size is a `scale.index` question over a
    // list past the threshold, and this fixture holds a handful of rows.
    const titlePath = `${targetPath}/fields/getbyinternalnameortitle('Title')`;
    // The type is read rather than named. A MERGE quoting the wrong entity
    // type is refused, and that refusal would be recorded as an answer about
    // indexing rather than about the guess that produced it.
    const titleBefore = createdTargetList
      ? await get(`${titlePath}?$select=Indexed,TypeAsString`)
      : { ok: false, status: 0, error: 'the target list was never created', d: null };
    const sourceIndex = titleBefore.ok
      ? await indexOne(titlePath, titleBefore.d?.__metadata?.type || 'SP.Field')
      : { wrote: notAttempted, back: notAttempted };
    const sourceIndexed = sourceIndex.wrote.ok && sourceIndex.back.ok
      && sourceIndex.back.d?.Indexed === true;
    record(
      'field.multilookup.control-source-title-indexed',
      'CONTROL: the TARGET list\'s Title, the column a lookup projects, takes Indexed:true',
      titleBefore.ok
        ? (sourceIndexed
          ? 'STUCK'
          : (sourceIndex.wrote.ok && !sourceIndex.back.ok ? 'READBACK UNREADABLE' : 'DID NOT STICK'))
        : 'NOT ESTABLISHED',
      titleBefore.ok
        ? `'Title' on '${TARGET_LIST}' read back TypeAsString=${show(titleBefore.d?.TypeAsString)} `
          + `Indexed=${show(titleBefore.d?.Indexed)} before the write; write `
          + `${httpNote(sourceIndex.wrote)}, readback Indexed=${indexReadback(sourceIndex)}. `
          + 'Every carry row below is void while this does not hold: with no index on the source there '
          + 'is nothing for a lookup to inherit, and a column reading false would say nothing.'
        : `the source column could not be read (${httpNote(titleBefore)}), so it was never indexed.`,
    );

    // MULTI, re-read and re-asked. Its Indexed BEFORE the source was indexed
    // is whatever the row above observed, so the pair is a before/after on one
    // column and the only thing that changed between them is the source.
    const multiBeforeSource = multiIndex.back.ok ? show(multiIndex.back.d?.Indexed) : 'unread';
    const multiAfterSource = (sourceIndexed && winningCreate)
      ? await get(`${fieldPath(MULTI)}${FIELD_SELECT}`)
      : { ok: false, status: 0, error: 'not attempted', d: null };
    const multiReindex = (sourceIndexed && winningCreate)
      ? await indexOne(fieldPath(MULTI), multiMetaType)
      : { wrote: notAttempted, back: notAttempted };
    record(
      'field.multilookup.source-index-carry',
      'Does an EXISTING multi-value lookup read back Indexed once its source is indexed?',
      (sourceIndexed && winningCreate)
        ? (multiAfterSource.ok
          ? (multiAfterSource.d?.Indexed === true ? 'CARRIES' : 'DOES NOT CARRY')
          : 'READBACK UNREADABLE')
        : 'NOT ESTABLISHED',
      (sourceIndexed && winningCreate)
        ? `'${multiName}' read Indexed=${multiBeforeSource} before the source was indexed and `
          + `Indexed=${multiAfterSource.ok ? show(multiAfterSource.d?.Indexed) : `UNREADABLE HTTP ${multiAfterSource.status} ${multiAfterSource.error}`} `
          + `after, with TypeAsString=${multiAfterSource.ok ? show(multiAfterSource.d?.TypeAsString) : '(unread)'} `
          + `FieldTypeKind=${multiAfterSource.ok ? show(multiAfterSource.d?.FieldTypeKind) : '(unread)'}. `
          + `Re-attempting the direct write with the source now indexed: ${httpNote(multiReindex.wrote)}, `
          + `readback Indexed=${indexReadback(multiReindex)}. `
          + 'A direct write that is refused BOTH times makes the refusal unconditional. One that is taken '
          + 'only now makes it conditional on the source, which is a narrower rule and a different '
          + 'remedy. Report both HTTP statuses verbatim.'
        : (winningCreate
          ? 'the source was never indexed, so there was no index for this column to carry.'
          : 'no multi-value lookup column was created, so there was nothing to read.'),
      (sourceIndexed && winningCreate) ? undefined : 'void',
    );

    // The two columns created over the already-indexed source. Both go through
    // paths this run has already proved: the winning create path for the
    // multi-value one, the deployer's AddField for the single-value one.
    const madeMultiSrc = (sourceIndexed && winningCreate)
      ? await winningCreate.run(MULTI_SRC)
      : notAttempted;
    const multiSrcBack = madeMultiSrc.ok
      ? await get(`${fieldPath(MULTI_SRC)}${FIELD_SELECT}`)
      : { ok: false, status: 0, error: 'the field was never created', d: null };
    const madeSingleSrc = sourceIndexed && controlLookupHeld
      ? await addLookup(SINGLE_SRC)
      : notAttempted;
    const singleSrcBack = madeSingleSrc.ok
      ? await get(`${fieldPath(SINGLE_SRC)}${FIELD_SELECT}`)
      : { ok: false, status: 0, error: 'the field was never created', d: null };
    // Only a field that reads back multi-value answers the multi-value
    // question, for the reason the create row gives: a single-value column
    // answering here would report an index behaviour about the wrong arity.
    const multiSrcIsMulti = multiSrcBack.ok && multiSrcBack.d?.AllowMultipleValues === true;
    record(
      'field.multilookup.source-index-carry-at-create',
      'Does a multi-value lookup CREATED over an indexed source read back Indexed?',
      multiSrcIsMulti
        ? (multiSrcBack.d?.Indexed === true ? 'CARRIES' : 'DOES NOT CARRY')
        : 'NOT ESTABLISHED',
      multiSrcIsMulti
        ? `'${MULTI_SRC}' created by ${winningCreate.name} while '${TARGET_LIST}' Title was indexed: `
          + `Indexed=${show(multiSrcBack.d?.Indexed)} TypeAsString=${show(multiSrcBack.d?.TypeAsString)} `
          + `FieldTypeKind=${show(multiSrcBack.d?.FieldTypeKind)} `
          + `AllowMultipleValues=${show(multiSrcBack.d?.AllowMultipleValues)} `
          + `LookupField=${show(multiSrcBack.d?.LookupField)}. `
          + 'CARRIES here with DOES NOT CARRY above means creation order decides it, and the deployer '
          + 'would have to index the target before creating the lookup rather than after. Read this '
          + 'beside the single-value row: if that one does not carry either, nothing here is about arity.'
        : (!sourceIndexed
          ? 'the source was never indexed, so this column was not created.'
          : (madeMultiSrc.ok
            ? `'${MULTI_SRC}' was created and does not read back AllowMultipleValues=true `
              + `(${multiSrcBack.ok ? show(multiSrcBack.d?.AllowMultipleValues) : `readback failed HTTP ${multiSrcBack.status}`}), `
              + 'so it would answer about a single-value column.'
            : `'${MULTI_SRC}' could not be created: ${httpNote(madeMultiSrc)}.`)),
      multiSrcIsMulti ? undefined : 'void',
    );
    record(
      'field.lookup.source-index-carry',
      'Does a SINGLE-value lookup over an indexed source read back Indexed?',
      singleSrcBack.ok
        ? (singleSrcBack.d?.Indexed === true ? 'CARRIES' : 'DOES NOT CARRY')
        : 'NOT ESTABLISHED',
      singleSrcBack.ok
        ? `'${SINGLE_SRC}' created by AddField while '${TARGET_LIST}' Title was indexed, and never `
          + `written to with Indexed: Indexed=${show(singleSrcBack.d?.Indexed)} `
          + `TypeAsString=${show(singleSrcBack.d?.TypeAsString)} `
          + `LookupField=${show(singleSrcBack.d?.LookupField)}. `
          + 'This is the comparator, not a control: both outcomes are informative. DOES NOT CARRY makes '
          + '`Indexed` on a lookup field its OWN index, mirroring nothing, and the multi-value rows above '
          + 'then say nothing about the source. CARRIES makes the property a source mirror, and a '
          + 'multi-value column reading false beside it IS about multiplicity.'
        : (!sourceIndexed
          ? 'the source was never indexed, so this column was not created.'
          : `'${SINGLE_SRC}' could not be created or read: ${httpNote(madeSingleSrc)}, `
            + `readback HTTP ${singleSrcBack.status} ${singleSrcBack.error}.`),
      singleSrcBack.ok ? undefined : 'void',
    );

    // === allow-multiple-values-mutability (#409 question 3) ===============
    // Asked on a field of its own so the index control is never asked about a
    // column this probe has mutated. Both directions, because the reconciler
    // sees drift either way: a property that widens but will not narrow is an
    // asymmetric finding and decides whether AllowMultipleValues joins
    // IMMUTABLE_LOOKUP_PROPERTIES in one direction or both.
    const madeFlip = controlLookupHeld ? await addLookup(FLIP) : notAttempted;
    const flipOn = madeFlip.ok
      ? await merge(fieldPath(FLIP), {
        __metadata: { type: 'SP.FieldLookup' }, AllowMultipleValues: true,
      })
      : notAttempted;
    const flipOnBack = madeFlip.ok
      ? await get(`${fieldPath(FLIP)}?$select=AllowMultipleValues,TypeAsString`)
      : { ok: false, status: 0, error: 'the field was never created', d: null };
    const widened = flipOn.ok && flipOnBack.ok && flipOnBack.d?.AllowMultipleValues === true;
    // Narrowing is only a question once there is something to narrow. Asked
    // against the type the widened field now reports, for the reason the
    // create readback gives above.
    const flipOff = widened
      ? await merge(fieldPath(FLIP), {
        __metadata: { type: flipOnBack.d?.__metadata?.type || 'SP.FieldLookup' },
        AllowMultipleValues: false,
      })
      : notAttempted;
    const flipOffBack = widened
      ? await get(`${fieldPath(FLIP)}?$select=AllowMultipleValues,TypeAsString`)
      : { ok: false, status: 0, error: 'the field was never widened', d: null };
    const narrowed = flipOff.ok && flipOffBack.ok && flipOffBack.d?.AllowMultipleValues === false;
    record(
      'field.multilookup.allow-multiple-values-mutability',
      'AllowMultipleValues on an EXISTING lookup: can it be turned on, and can it be turned off again?',
      !madeFlip.ok
        ? 'NOT ESTABLISHED'
        : (widened
          ? (narrowed ? 'MUTABLE BOTH WAYS' : 'WIDENS ONLY')
          : (flipOn.ok ? 'WIDEN ACCEPTED BUT DID NOT STICK' : 'WIDEN REFUSED')),
      !madeFlip.ok
        ? `the single-value field '${FLIP}' this row mutates was never created (${httpNote(madeFlip)}), `
          + 'so neither direction was asked.'
        : `single -> multi: write ${httpNote(flipOn)}, readback `
          + `AllowMultipleValues=${flipOnBack.ok ? show(flipOnBack.d?.AllowMultipleValues) : `UNREADABLE HTTP ${flipOnBack.status} ${flipOnBack.error}`} `
          + `TypeAsString=${flipOnBack.ok ? show(flipOnBack.d?.TypeAsString) : '(unread)'}. `
          + `multi -> single: ${widened
            ? `write ${httpNote(flipOff)}, readback `
              + `AllowMultipleValues=${flipOffBack.ok ? show(flipOffBack.d?.AllowMultipleValues) : `UNREADABLE HTTP ${flipOffBack.status} ${flipOffBack.error}`}`
            : 'NOT ASKED, because the field was never widened'}. `
          + 'WIDEN REFUSED puts AllowMultipleValues in IMMUTABLE_LOOKUP_PROPERTIES and means an existing '
          + 'single-value lookup can never be widened in place. WIDENS ONLY puts it there in one '
          + 'direction only, which the reconciler has no vocabulary for today. MUTABLE BOTH WAYS keeps '
          + 'it out and makes it an ordinary reconciled property.',
      madeFlip.ok ? undefined : 'void',
    );

    // === item-write-shape (#409 question 4) ===============================
    // Four candidates, and EVERY one is tried rather than stopping at the
    // first that works. Which shapes SharePoint accepts is more useful than
    // which one happens to be first: an accepted shape that stores the wrong
    // members is the answer worth having, and it is only visible by writing
    // all of them and reading them all back.
    //
    // Each candidate gets its own item, titled after the shape, so the read
    // row below can attribute what it sees.
    let itemType = null;
    if (winningCreate) {
      try {
        itemType = await entityTypeFor(PROBE_LIST);
      } catch (err) {
        log('ERROR', `Could not resolve the probe list's item entity type: ${err.message}`);
      }
    }
    const writeShapes = [
      { name: 'bare-results', build: (ids) => ({ [idField]: { results: ids } }) },
      {
        name: 'collection-metadata',
        build: (ids) => ({
          [idField]: { __metadata: { type: 'Collection(Edm.Int32)' }, results: ids },
        }),
      },
      { name: 'bare-array', build: (ids) => ({ [idField]: ids }) },
      // The field's own name rather than the Id alias. A lookup is written
      // through `<Name>Id` for a single value; whether the collection form
      // insists on the same alias is a separate question and it is cheap.
      { name: 'name-not-id-alias', build: (ids) => ({ [multiName]: { results: ids } }) },
    ];
    const writeAttempts = [];
    const written = [];
    const writesRunnable = !!winningCreate && itemType !== null && WRITE_IDS.length === 2;
    if (writesRunnable) {
      for (const shape of writeShapes) {
        const made = await post(`${listPath}/items`, {
          __metadata: { type: itemType },
          Title: `W ${shape.name}`,
          ...shape.build(WRITE_IDS),
        });
        writeAttempts.push(`${shape.name}: ${httpNote(made)}`);
        if (made.ok) written.push({ shape: shape.name, id: made.d?.Id ?? null });
      }
    }
    record(
      'field.multilookup.item-write-shape',
      'which item WRITE shapes SharePoint accepts for a multi-value lookup',
      writesRunnable
        ? (written.length
          ? `ACCEPTED: ${written.map((w) => w.shape).join(', ')}`
          : 'ALL FOUR REFUSED')
        : 'NOT ESTABLISHED',
      writesRunnable
        ? `wrote ids ${show(WRITE_IDS)} (${TARGET_ROWS[0]}, ${TARGET_ROWS[1]}) through '${idField}'. `
          + `${writeAttempts.join(' || ')}. `
          + 'ACCEPTED is only half the answer. The read row below says whether an accepted shape stored '
          + 'BOTH ids, one, or none, and a shape that is taken and stores the wrong members is the '
          + 'result the deployer must not emit.'
        : (!winningCreate
          ? 'no multi-value lookup column was created, so there was nothing to write to.'
          : (itemType === null
            ? 'the probe list\'s item entity type could not be resolved, so no item body could be built.'
            : `the target list seeded ${targetIds.length} row(s) rather than ${TARGET_ROWS.length}, so `
              + 'there was no pair of ids to write.')),
      writesRunnable ? undefined : 'void',
    );

    // === item-read-shape (#409 question 4) ================================
    // Three reads, because the deployer, the reconciler and the reporting
    // layer do not all speak the same OData dialect, and they need not agree.
    // The first two differ ONLY in their Accept header, so any difference
    // between them is the content type's doing and nothing else's. The third
    // is the $expand form reportgen would use to get labels rather than ids.
    const itemsPath = `${listPath}/items`;
    const idQuery = `${itemsPath}?$select=Id,Title,${idField}&$orderby=Id`;
    const expandQuery = `${itemsPath}?$select=Id,Title,${multiName}/Id,${multiName}/Title`
      + `&$expand=${multiName}&$orderby=Id`;
    const readVerbose = writesRunnable ? await get(idQuery) : null;
    const readNoMeta = writesRunnable
      ? await get(idQuery, 'application/json;odata=nometadata')
      : null;
    const readExpanded = writesRunnable ? await get(expandQuery) : null;
    const rowsOf = (r) => (r?.d?.results || r?.d?.value || []);
    const describe = (r, key) => (r
      ? (r.ok
        ? show(rowsOf(r).map((row) => ({ [row.Title]: row[key] })))
        : `REQUEST FAILED HTTP ${r.status}: ${r.error} (not observed to be empty, not observed at all)`)
      : 'not attempted');
    // Named individually rather than collapsed to one head. A column that is
    // readable under $expand and 400s under a plain $select is a different
    // answer for the reader than one that is readable everywhere, and both
    // would otherwise print as READ.
    const readsThatWorked = [
      ['verbose-select', readVerbose],
      ['nometadata-select', readNoMeta],
      ['verbose-expand', readExpanded],
    ].filter(([, r]) => r?.ok && rowsOf(r).length).map(([name]) => name);
    record(
      'field.multilookup.item-read-shape',
      'what a multi-value lookup value READS BACK as',
      writesRunnable
        ? (readsThatWorked.length ? `READ: ${readsThatWorked.join(', ')}` : 'ALL THREE READS FAILED')
        : 'NOT ESTABLISHED',
      writesRunnable
        ? `verbose $select=${idField}: ${describe(readVerbose, idField)} || `
          + `nometadata $select=${idField}: ${describe(readNoMeta, idField)} || `
          + `verbose $expand=${multiName}: ${describe(readExpanded, multiName)}. `
          + `Each row is keyed by the WRITE shape that produced it. The ids asked for were `
          + `${show(WRITE_IDS)}; a row holding anything else was accepted and stored something other `
          + 'than what it was given. Report all three verbatim: whether the value arrives as an array, '
          + 'a { results: [...] } object or a delimited string decides what extract/decode.py has to '
          + 'read and what reportgen has to flatten, and the three dialects need not agree.'
        : 'no item carrying a multi-value lookup was written, so there was nothing to read.',
      writesRunnable ? undefined : 'void',
    );

    // === The CAML fixture =================================================
    // The rows every query.caml-adhoc row below is read against, shaped as an
    // exact analogue of multi-value-probe.js's MultiChoice fixture so the two
    // measurements are directly comparable. That is the whole point of asking:
    // the multi-value CAML vocabulary in `analysis/condition_rendering.py` was
    // measured on 2026-08-10 against a Choice column and against nothing else,
    // and `analysis/conditions.py` refuses a filter on a multi-value LOOKUP
    // rather than assume the two behave alike.
    //
    //   MultiChoice          here
    //   R1 {View}            L1 {Alpha}
    //   R2 {View,Edit}       L2 {Alpha,Bravo}
    //   R3 {Edit,Export}     L3 {Bravo,Charlie}
    //   R4 {}                L4 {}
    //
    // THE FOUR W ITEMS ARE DELETED FIRST, and that is not tidiness. All four
    // carry the same pair as L2, so every membership predicate below would
    // return five rows where two are the answer and three are noise, on
    // fifteen rows of prose an operator has to read. They have already served
    // the write and read questions above, which are recorded.
    //
    // L4 OMITS THE COLUMN rather than writing an empty collection. "Never
    // given a value" and "given the empty set" are not obviously the same row
    // to SharePoint, and the null tests below are about the first one.
    const acceptedShape = writeShapes.find(
      (shape) => written.some((row) => row.shape === shape.name),
    ) || null;
    // All three target rows are needed, not the two the write shapes used:
    // Charlie is what makes "contains Alpha" and "contains anything" different
    // answers.
    const camlRunnable = writesRunnable && !!acceptedShape
      && targetIds.length === TARGET_ROWS.length;
    const deleteItem = (id) => post(
      `${itemsPath}(${id})`, undefined, { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' },
    );
    const removedWrites = [];
    if (camlRunnable) {
      for (const row of written) {
        if (row.id === null) continue;
        const gone = await deleteItem(row.id);
        removedWrites.push(`${row.shape}: ${httpNote(gone)}`);
      }
    }
    const idFor = (title) => targetIds[TARGET_ROWS.indexOf(title)];
    const CAML_ROWS = [
      { title: 'L1', members: ['Alpha'] },
      { title: 'L2', members: ['Alpha', 'Bravo'] },
      { title: 'L3', members: ['Bravo', 'Charlie'] },
      { title: 'L4', members: [] },
    ];
    const seedCamlErrors = [];
    if (camlRunnable) {
      for (const row of CAML_ROWS) {
        const body = { __metadata: { type: itemType }, Title: row.title };
        if (row.members.length) {
          Object.assign(body, acceptedShape.build(row.members.map(idFor)));
        }
        const made = await post(`${listPath}/items`, body);
        if (!made.ok) seedCamlErrors.push(`${row.title}: HTTP ${made.status} ${made.error}`);
      }
    }
    // Read the fixture back before believing it. An accepted write shape that
    // stored the wrong members would make every predicate below a report about
    // a list nobody has seen, and that reads exactly like a working experiment.
    const camlBack = camlRunnable
      ? await get(`${itemsPath}?$select=Id,Title,${idField}&$orderby=Id`)
      : null;
    // The stored cell's own shape is item-read-shape's question and is not
    // assumed here. Both forms that question could answer are unwrapped, and
    // anything else leaves the fixture unverified rather than reported wrong.
    const idsOf = (cell) => (Array.isArray(cell)
      ? cell
      : (cell && Array.isArray(cell.results) ? cell.results : null));
    const observedRows = camlBack?.ok ? rowsOf(camlBack) : [];
    const camlSeeded = camlRunnable && !seedCamlErrors.length
      && observedRows.length === CAML_ROWS.length;
    const camlVerified = camlSeeded && CAML_ROWS.every((row) => {
      const stored = observedRows.find((candidate) => candidate.Title === row.title);
      if (!stored) return false;
      const ids = idsOf(stored[idField]) || [];
      const wanted = row.members.map(idFor);
      return ids.length === wanted.length && wanted.every((id) => ids.includes(id));
    });
    record(
      'field.multilookup.fixture-caml-rows-seeded',
      'the four-row CAML fixture actually built, and holds the members it was given',
      camlVerified ? 'BUILT' : (camlRunnable ? 'SHORT' : 'NOT ESTABLISHED'),
      camlRunnable
        ? `write shape used: ${acceptedShape.name}. `
          + `target ids ${show(TARGET_ROWS.map((title) => `${title}=${idFor(title)}`))}. `
          + `W items removed: ${removedWrites.length ? removedWrites.join('; ') : 'none to remove'}. `
          + `seed errors: ${seedCamlErrors.length ? seedCamlErrors.join('; ') : 'none'}. `
          + `read back: ${camlBack.ok
            ? show(observedRows.map((row) => ({ [row.Title]: row[idField] })))
            : `FAILED HTTP ${camlBack.status} ${camlBack.error}`}. `
          + 'SHORT means the rows exist and their stored members are not what was asked for, or could '
          + 'not be compared with it at all, which is what happens when the value reads back in a shape '
          + 'neither an array nor { results: [...] }. Every predicate row below is then a list of titles '
          + 'and not an answer, and each says so on its own row rather than relying on this one being '
          + 'read first.'
        : (!writesRunnable
          ? 'no item carrying a multi-value lookup could be written, so there was no fixture to build.'
          : (!acceptedShape
            ? 'no write shape was accepted, so there was no way to give a row its members.'
            : `the target list seeded ${targetIds.length} row(s) rather than ${TARGET_ROWS.length}, `
              + 'so a predicate that matched everything could not be told from one that was right.')),
      camlRunnable ? undefined : 'void',
    );

    // === query.caml-adhoc.multilookup-*: what does each predicate return? ==
    //
    // NOTHING HERE IS ASSERTED, for the reason multi-value-probe.js gives over
    // the same block: writing the expected set into a comparison would make the
    // experiment fail the moment SharePoint answered something interesting.
    // Each row records the titles that came back and, beside them, what each
    // possible answer would mean for the grammar.
    //
    // TWO OPERAND DIALECTS, asked separately for every operator that takes a
    // value. A lookup has both a display value and an id, and CAML spells them
    // differently:
    //
    //   text      <FieldRef Name="X"/>              <Value Type="Lookup">Alpha</Value>
    //   lookupid  <FieldRef Name="X" LookupId="TRUE"/>  <Value Type="Integer">7</Value>
    //
    // Which one a multi-value lookup answers to is the question the deployer
    // has to settle: a mapping names a target row, and whether the emitted
    // filter carries its title or its id decides whether the filter survives a
    // rename. Neither is assumed to work and neither is assumed to fail.
    const camlWhere = (where) => `<View><ViewFields><FieldRef Name="Title"/></ViewFields>`
      + `<Query><Where>${where}</Where></Query><RowLimit>50</RowLimit></View>`;
    // ViewFields is explicit so the projection is one non-join column. Without
    // it the query projects the list's default fields, and this list carries
    // several lookups by the time it gets here; a refusal for join reasons
    // would be indistinguishable from an operator SharePoint will not accept.
    const camlRows = async (where) => {
      const r = await post(`${listPath}/GetItems?$select=Title`, {
        query: { __metadata: { type: 'SP.CamlQuery' }, ViewXml: camlWhere(where) },
      });
      if (!r.ok) return { ok: false, error: `HTTP ${r.status} ${r.error}`, titles: null };
      return { ok: true, error: null, titles: (r.d?.results || []).map((i) => i.Title).sort() };
    };
    const operand = {
      text: (title) => `<FieldRef Name="${multiName}"/><Value Type="Lookup">${title}</Value>`,
      lookupid: (title) => `<FieldRef Name="${multiName}" LookupId="TRUE"/>`
        + `<Value Type="Integer">${idFor(title)}</Value>`,
    };
    const values = (dialect, titles) => `<Values>${titles.map((title) => (dialect === 'text'
      ? `<Value Type="Lookup">${title}</Value>`
      : `<Value Type="Integer">${idFor(title)}</Value>`)).join('')}</Values>`;
    const fieldRef = (dialect) => (dialect === 'text'
      ? `<FieldRef Name="${multiName}"/>`
      : `<FieldRef Name="${multiName}" LookupId="TRUE"/>`);
    const binary = (tag, dialect, title) => `<${tag}>${operand[dialect](title)}</${tag}>`;
    const MEMBER_MEANS = 'L1+L2 is the membership reading: the two rows whose set contains Alpha. '
      + 'L2 alone would mean it compares the WHOLE SET. Nothing means this spelling is unusable and '
      + 'the grammar must not emit it.';
    const NEGATIVE_MEANS = 'L3 only means the negative excludes the empty row L4, like every other '
      + 'CAML negative, and the deployer\'s existing <Or><IsNull> wrapper is what that is for. L3+L4 '
      + 'means it includes it. Nothing means negation has no spelling here and must be refused.';
    const predicates = [
      ['query.caml-adhoc.multilookup-eq-text', 'Eq(text) Alpha',
        binary('Eq', 'text', 'Alpha'),
        `${MEMBER_MEANS} <Eq> is the operator the MultiChoice run crowned on 2026-08-10, so this is `
        + 'the row that says whether the measured Choice grammar transfers to a lookup unchanged.'],
      ['query.caml-adhoc.multilookup-eq-lookupid', 'Eq(lookupid) Alpha',
        binary('Eq', 'lookupid', 'Alpha'),
        `${MEMBER_MEANS} If this works and the text form does not, an emitted filter must carry the `
        + 'target row\'s ID, which survives a rename and needs the id resolved at build time.'],
      ['query.caml-adhoc.multilookup-includes-text', 'Includes(text) Alpha',
        binary('Includes', 'text', 'Alpha'),
        `${MEMBER_MEANS} Learn documents <Includes> for a multi-value LOOKUP specifically, and `
        + 'against a MultiChoice column it returned an EMPTY SET with no error. This is the row that '
        + 'says whether the documented element works on the type it is documented for.'],
      ['query.caml-adhoc.multilookup-includes-lookupid', 'Includes(lookupid) Alpha',
        binary('Includes', 'lookupid', 'Alpha'),
        `${MEMBER_MEANS} The documented element in the id dialect.`],
      ['query.caml-adhoc.multilookup-neq-text', 'Neq(text) Alpha',
        binary('Neq', 'text', 'Alpha'), NEGATIVE_MEANS],
      ['query.caml-adhoc.multilookup-neq-lookupid', 'Neq(lookupid) Alpha',
        binary('Neq', 'lookupid', 'Alpha'), NEGATIVE_MEANS],
      ['query.caml-adhoc.multilookup-notincludes-text', 'NotIncludes(text) Alpha',
        binary('NotIncludes', 'text', 'Alpha'),
        `${NEGATIVE_MEANS} <NotIncludes> is the documented negation of <Includes>; against MultiChoice `
        + 'it returned nothing, which is what left that grammar with no negative at all.'],
      ['query.caml-adhoc.multilookup-notincludes-lookupid', 'NotIncludes(lookupid) Alpha',
        binary('NotIncludes', 'lookupid', 'Alpha'), NEGATIVE_MEANS],
      // <In> over two members, chosen so the answer separates "intersects"
      // from "is exactly one of": Alpha is in L1 and L2, Charlie only in L3.
      ['query.caml-adhoc.multilookup-in-text', 'In(text) [Alpha, Charlie]',
        `<In>${fieldRef('text')}${values('text', ['Alpha', 'Charlie'])}</In>`,
        'L1+L2+L3 means <In> is "the set intersects these", which is any_of in one element rather '
        + 'than a nested <Or>. Anything narrower means it is not that, and any_of must keep composing '
        + 'binary predicates. Nothing means <In> has no spelling here.'],
      ['query.caml-adhoc.multilookup-in-lookupid', 'In(lookupid) [Alpha, Charlie]',
        `<In>${fieldRef('lookupid')}${values('lookupid', ['Alpha', 'Charlie'])}</In>`,
        'The same question in the id dialect. <In> with LookupId is the shape most often quoted for '
        + 'lookups, so a difference between these two rows is the operand answer on its own.'],
      ['query.caml-adhoc.multilookup-isnull', 'IsNull',
        `<IsNull><FieldRef Name="${multiName}"/></IsNull>`,
        'L4 only is the expected shape of a working null test. L4 was written with the column OMITTED '
        + 'rather than set to an empty collection, so this asks about a row that was never given a value.'],
      ['query.caml-adhoc.multilookup-isnotnull', 'IsNotNull',
        `<IsNotNull><FieldRef Name="${multiName}"/></IsNotNull>`,
        'L1+L2+L3 is the expected shape.'],
    ];
    // Only a SINGLE binary predicate in the value dialects may be crowned, and
    // only if it returns EXACTLY the two rows containing Alpha. The compounds
    // below are then written in the winner's operator and dialect, because a
    // conjunction is only meaningful over a membership test that works, and
    // mixing dialects across the arms would make a failure unattributable.
    // <In> is excluded: it is a set operator, and all_of/any_of compose binary
    // predicates.
    const MEMBERSHIP_CANDIDATES = new Map([
      ['query.caml-adhoc.multilookup-eq-text', { tag: 'Eq', negation: 'Neq', dialect: 'text' }],
      ['query.caml-adhoc.multilookup-eq-lookupid', { tag: 'Eq', negation: 'Neq', dialect: 'lookupid' }],
      ['query.caml-adhoc.multilookup-includes-text', { tag: 'Includes', negation: 'NotIncludes', dialect: 'text' }],
      ['query.caml-adhoc.multilookup-includes-lookupid', { tag: 'Includes', negation: 'NotIncludes', dialect: 'lookupid' }],
    ]);
    let membershipWinner = null;
    for (const [id, label, where, meaning] of predicates) {
      const question = `CAML ${label} over a multi-value lookup returns which rows`;
      if (!camlRunnable) {
        // Not asked rather than asked and unanswered. With no column or no
        // rows every query here would fail for a reason that has nothing to do
        // with the operator, and a refusal is the one answer this block is for.
        record(id, question, 'NOT ESTABLISHED',
          'the CAML fixture did not build (see field.multilookup.fixture-caml-rows-seeded), so this '
          + 'predicate was never issued.', 'void');
        continue;
      }
      const got = await camlRows(where);
      record(
        id,
        question,
        got.ok ? (camlVerified ? 'RETURNED' : 'SHORT') : 'QUERY REFUSED',
        got.ok
          ? `${where} -> ${show(got.titles)} || `
            + (camlVerified
              ? meaning
              : 'the fixture these rows are read against did not verify (see '
                + 'field.multilookup.fixture-caml-rows-seeded), so this row is a list of titles and '
                + 'not an answer. Do not read the meaning off it; fix the fixture and re-run.')
          : `${where} -> ${got.error}`,
      );
      if (!membershipWinner && got.ok && camlVerified && MEMBERSHIP_CANDIDATES.has(id)
          && got.titles.length === 2
          && got.titles.includes('L1') && got.titles.includes('L2')) {
        membershipWinner = { id, ...MEMBERSHIP_CANDIDATES.get(id) };
      }
    }

    // The three compounds, in the winning membership spelling. Composition
    // over a SET is not the same question as composition over a scalar, which
    // is why they are asked rather than inferred from the rows above.
    const compound = (tag, dialect, arms) => arms
      .map(([element, title]) => binary(element, dialect, title)).join('');
    const compounds = membershipWinner ? [
      ['query.caml-adhoc.multilookup-and-membership',
        `And[${membershipWinner.tag} Alpha, ${membershipWinner.tag} Bravo]`,
        `<And>${compound(membershipWinner.tag, membershipWinner.dialect, [
          [membershipWinner.tag, 'Alpha'], [membershipWinner.tag, 'Bravo'],
        ])}</And>`,
        'L2 only means <And> over two membership tests is "contains BOTH", which is what all_of would '
        + 'emit. Nothing means SharePoint cannot conjoin two predicates over the same multi-value '
        + 'lookup at all, and all_of must be refused on one.'],
      ['query.caml-adhoc.multilookup-or-membership',
        `Or[${membershipWinner.tag} Alpha, ${membershipWinner.tag} Charlie]`,
        `<Or>${compound(membershipWinner.tag, membershipWinner.dialect, [
          [membershipWinner.tag, 'Alpha'], [membershipWinner.tag, 'Charlie'],
        ])}</Or>`,
        'L1+L2+L3 means <Or> is "contains EITHER", which is what any_of would emit. Anything narrower '
        + 'means it does not distribute over membership and any_of must be refused.'],
      ['query.caml-adhoc.multilookup-neq-isnull-wrapper',
        `Or[${membershipWinner.negation} Alpha, IsNull]`,
        `<Or>${binary(membershipWinner.negation, membershipWinner.dialect, 'Alpha')}`
        + `<IsNull><FieldRef Name="${multiName}"/></IsNull></Or>`,
        'L3+L4 is what the deployer\'s existing not_includes wrapper is for: it exists so a row with '
        + 'no value is not silently dropped by a negative. Anything else means the wrapper does not '
        + 'compose with a multi-value lookup and the emitted spelling has to change.'],
    ] : [];
    for (const [id, label, where, meaning] of compounds) {
      const got = await camlRows(where);
      record(
        id,
        `CAML ${label} over a multi-value lookup returns which rows`,
        got.ok ? 'RETURNED' : 'QUERY REFUSED',
        got.ok ? `${where} -> ${show(got.titles)} || ${meaning}` : `${where} -> ${got.error}`,
      );
    }
    if (!membershipWinner) {
      for (const id of [
        'query.caml-adhoc.multilookup-and-membership',
        'query.caml-adhoc.multilookup-or-membership',
        'query.caml-adhoc.multilookup-neq-isnull-wrapper',
      ]) {
        record(
          id, 'CAML compound membership over a multi-value lookup returns which rows',
          'NOT ESTABLISHED',
          (camlRunnable
            ? 'no single membership predicate returned exactly L1+L2, so there is no working membership '
              + 'spelling to compose. '
            : 'the CAML fixture did not build. ')
          + 'A compound written in a spelling that does not work would return nothing for a reason '
          + 'that has nothing to do with composition.',
          'void',
        );
      }
    }

    // === scale.join.*: how many joins does a multi-value lookup cost? =====
    //
    // `analysis/joins.py` counts a multi-value lookup as ONE join against a
    // ceiling of 12, and says in its own docstring that the row is inferred
    // rather than measured. This block measures it.
    //
    // THE SHAPE IS SELF-CALIBRATING and reports a NUMBER, not a boolean. Walk
    // single-value lookups up until the render stops, giving `worked`, the
    // ceiling on this fixture. Walk again with the multi-value column appended,
    // giving `workedWithMulti`. If the multi-value column costs c joins then
    // workedWithMulti + c = worked, so the cost is the difference.
    //
    // Written this way rather than as "9 singles plus the multi renders" so
    // that nothing here assumes the ceiling is 12. If this tenant answers 8, or
    // 14, the subtraction is still the cost; a fixture pinned to 9 would report
    // the wrong answer confidently. That is also why the walk stops at the
    // first failure rather than testing each width independently: the ceiling
    // is what the first failure means.
    //
    // JOIN COLUMNS ARE EMPTY, never written to. Whether an empty lookup still
    // costs a join is part of the question, and threshold-index-probe.js
    // measured its ceiling the same way, so the two runs are comparable.
    //
    // THE VIEW IS PROJECTED EXPLICITLY, through RenderListDataAsStream with
    // <ViewFields>, so All Items' automatic Author and Editor are not in the
    // count and the only variable across rows is how many lookups are asked
    // for.
    //
    // RenderListDataAsStream is read at odata=nometadata. The shared post()
    // asks for verbose and returns the `d` envelope, and this method's verbose
    // form wraps its payload in a JSON string needing a second parse.
    // threshold-index-probe.js reads it at nometadata too, so the two join
    // measurements are made through one dialect rather than two.
    const renderStream = async (fields) => {
      const viewXml = '<View><Query></Query>'
        + `<ViewFields>${fields.map((f) => `<FieldRef Name='${f}'/>`).join('')}</ViewFields>`
        + '<RowLimit>50</RowLimit></View>';
      const digest = await getDigest();
      const response = await fetchWithRetry(apiUrl(`${listPath}/RenderListDataAsStream`), {
        method: 'POST',
        headers: {
          'Accept': 'application/json;odata=nometadata',
          'Content-Type': 'application/json;odata=verbose',
          'X-RequestDigest': digest,
        },
        body: JSON.stringify({ parameters: { ViewXml: viewXml } }),
      });
      const text = await response.text();
      if (!response.ok) {
        return {
          ok: false, status: response.status, error: spError(text), present: () => false, rows: 0,
        };
      }
      let body = null;
      try { body = JSON.parse(text); } catch { body = null; }
      const rows = Array.isArray(body?.Row) ? body.Row : [];
      const keys = rows.length ? Object.keys(rows[0]) : [];
      // A view that renders is only evidence about join cost if the column
      // under test was actually PROJECTED. A silently dropped ViewField looks
      // exactly like a join that was free, and threshold-index-probe.js was
      // caught by that once on its own fixture.
      const present = (name) => keys.some(
        (k) => k === name || k.startsWith(`${name}.`) || k === `${name}Id`,
      );
      return { ok: true, status: response.status, error: null, present, rows: rows.length };
    };
    const joinColumns = [];
    const joinCreateErrors = [];
    for (let n = 1; n <= JOIN_COLUMNS; n += 1) {
      const name = `Join${n}`;
      const made = await addLookup(name);
      if (made.ok) {
        joinColumns.push(name);
      } else {
        joinCreateErrors.push(`${name}: HTTP ${made.status} ${made.error}`);
        break;
      }
    }
    let joinCeiling = 0;
    let joinFailure = '';
    for (let n = 1; n <= joinColumns.length; n += 1) {
      const r = await renderStream(['Title', ...joinColumns.slice(0, n)]);
      if (r.ok && r.present(joinColumns[n - 1])) { joinCeiling = n; continue; }
      joinFailure = r.ok
        ? `HTTP ${r.status} but '${joinColumns[n - 1]}' was not projected (${r.rows} row(s) returned)`
        : `HTTP ${r.status} ${r.error}`;
      break;
    }
    const ceilingFound = joinCeiling > 0 && joinCeiling < joinColumns.length;
    record(
      'scale.join.control-ceiling-small-list',
      'CONTROL: does the join ceiling bite on a SMALL list, or only past the item threshold?',
      joinColumns.length === 0
        ? 'NOT ESTABLISHED'
        : (ceilingFound ? `CEILING ${joinCeiling}` : `NO CEILING FOUND (${joinCeiling} projected of ${joinColumns.length})`),
      `${joinColumns.length} empty single-value lookup(s) created`
      + `${joinCreateErrors.length ? `, then ${joinCreateErrors.join('; ')}` : ''}. `
      + `${joinCeiling} render(s); ${joinCeiling + 1} ${joinFailure || 'was not reachable'}. `
      + 'This list holds four items, nowhere near the 5,000-item threshold. '
      + '`analysis/joins.py` says the ceiling is a property of the view\'s SHAPE rather than the '
      + 'list\'s SIZE and records that as unmeasured, so a ceiling here settles that claim as a '
      + 'by-product. NO CEILING FOUND means the opposite: the limit needs size, this fixture cannot '
      + 'reach it, and the cost row below is void. Take that question to '
      + 'threshold-index-probe.js, whose 6,000-row fixture found a ceiling of 12 on 2026-07-31.',
      joinColumns.length ? undefined : 'void',
    );
    let joinWithMulti = -1;
    let joinWithMultiFailure = '';
    if (ceilingFound && winningCreate) {
      for (let n = 0; n <= joinColumns.length; n += 1) {
        const r = await renderStream(['Title', ...joinColumns.slice(0, n), multiName]);
        if (r.ok && r.present(multiName)) { joinWithMulti = n; continue; }
        joinWithMultiFailure = r.ok
          ? `HTTP ${r.status} but '${multiName}' was not projected (${r.rows} row(s) returned)`
          : `HTTP ${r.status} ${r.error}`;
        break;
      }
    }
    const joinCost = joinWithMulti >= 0 ? joinCeiling - joinWithMulti : null;
    record(
      'scale.join.multi-value-lookup-costs-a-join',
      'How many joins does a multi-value lookup cost against the view ceiling?',
      joinCost === null
        ? 'NOT ESTABLISHED'
        : (joinCost < 0 ? `SHORT: the two walks disagree (${joinCost})` : `COSTS ${joinCost}`),
      joinCost === null
        ? (!winningCreate
          ? 'no multi-value lookup column was created, so there was nothing to add to the view.'
          : (!ceilingFound
            ? 'no ceiling was found on this list, so there is nothing to sit at and the difference '
              + 'between the two walks would be meaningless.'
            : `'${multiName}' could not be projected even on its own: ${joinWithMultiFailure}. `
              + 'A column that will not render alone says nothing about what it costs.'))
        : `${joinCeiling} single-value lookup(s) render alone; ${joinWithMulti} render(s) alongside `
          + `'${multiName}', and ${joinWithMulti + 1} `
          + `${joinWithMultiFailure || 'was not reachable, which is why this number may be a floor'}. `
          + `The difference is the cost, so this multi-value lookup counts as ${joinCost} join(s). `
          + '`analysis/joins.py` counts it as ONE and says so is inferred rather than measured. '
          + 'COSTS 1 confirms that count. Any other number contradicts it, and JOIN_LIMIT, '
          + 'JOIN_WARN_AT and the docstring all have to change together. A negative difference is '
          + 'not an answer: it means the two walks measured different things, and the run has to be '
          + 'repeated on a fresh fixture before either number is quoted.',
      joinCost === null ? 'void' : undefined,
    );

    // === fixture-lists-created ============================================
    // Recorded last, because it reports on what everything above depended on.
    // Deliberately says nothing about the multi-value column: whether one can
    // exist at all is the create row's question, and folding it in here would
    // let a fixture FAILED stand in for an answer this probe was built to give.
    const targetCount = await get(`${targetPath}/ItemCount`);
    const seededCount = targetCount.ok ? Number(targetCount.d.ItemCount) : NaN;
    const fixtureBuilt = createdProbeList && createdTargetList
      && seededCount === TARGET_ROWS.length && !seedErrors.length && controlLookupHeld;
    record(
      'field.multilookup.fixture-lists-created',
      'the fixture actually built: two lists, three target rows, the control columns',
      fixtureBuilt ? 'BUILT' : 'FAILED',
      `target '${TARGET_LIST}' ItemCount=${seededCount}/${TARGET_ROWS.length} ids=${show(targetIds)} `
      + `probe list='${PROBE_LIST}' single-value control field=${controlLookupHeld ? 'created' : 'FAILED'} `
      + `${seedErrors.join('; ')}`,
    );
    if (!fixtureBuilt) {
      log('ERROR', 'The fixture is not what the rows above assume. Fix it and re-run before reporting.');
    }

    // === Verdict ==========================================================
    dump();
    const observedFor = (id) => results.find((r) => r.id === id)?.observed;
    log(
      'VERDICT',
      `fixture=${fixtureBuilt ? 'ok' : 'FAILED'} `
      + `create=${observedFor('field.multilookup.create-readback-type')} `
      + `type_as_string=${show(multiShape?.d?.TypeAsString)} `
      + `field_type_kind=${show(multiShape?.d?.FieldTypeKind)} `
      + `indexed=${observedFor('field.multilookup.indexed-property')} `
      + `source_index_carry=${observedFor('field.multilookup.source-index-carry')} `
      + `source_index_carry_at_create=${observedFor('field.multilookup.source-index-carry-at-create')} `
      + `single_value_carry=${observedFor('field.lookup.source-index-carry')} `
      + `mutability=${observedFor('field.multilookup.allow-multiple-values-mutability')} `
      + `write_shapes=${written.length ? written.map((w) => w.shape).join('+') : 'none'} `
      + `read=${observedFor('field.multilookup.item-read-shape')} `
      + `caml_fixture=${observedFor('field.multilookup.fixture-caml-rows-seeded')} `
      + `caml_membership=${membershipWinner ? membershipWinner.id : 'none'} `
      + `join_ceiling=${observedFor('scale.join.control-ceiling-small-list')} `
      + `join_cost=${observedFor('scale.join.multi-value-lookup-costs-a-join')}`,
    );
    log('INFO', 'Paste the VERDICT line and the whole table back. The TypeAsString and FieldTypeKind '
      + 'values are the point of the run: nothing in this codebase knows them yet.');
    return { results, winningCreate: winningCreate?.name || null, written };
  } finally {
    // Probe list first: SharePoint refuses to recycle a list that another
    // list's lookup points into, so taking the target first would fail and
    // leave both behind.
    if (CLEANUP) {
      for (const [title, marker, made] of [
        [PROBE_LIST, OWNERSHIP_DESCRIPTION, createdProbeList],
        [TARGET_LIST, TARGET_OWNERSHIP, createdTargetList],
      ]) {
        if (!made) continue;
        const gone = await recycleOwnedList(title, marker);
        if (gone.ok) {
          log('INFO', `Recycled '${title}'.`);
        } else {
          log('ERROR', `COULD NOT RECYCLE '${title}' (${gone.error}). Recycle it by hand: `
            + `${TENANT}${WEB}/Lists/${encodeURIComponent(title)}`);
        }
      }
    } else if (createdProbeList || createdTargetList) {
      log('INFO', `Left '${PROBE_LIST}' and '${TARGET_LIST}' in place. Re-run with CLEANUP = true to `
        + 'recycle them, and recycle the probe list BEFORE the target: a list another list looks up '
        + 'into cannot be removed.');
    }
  }
})();
