/**
 * MULTI-VALUE COLUMN PROBE.
 *
 * Creates one owned list and measures MultiChoice creation, item shapes,
 * indexing, CAML membership/null behavior, stored views, unsupported formula
 * operands and rendered severity formatting. The catalogue owns the finding
 * inventory and visible state matrix. Historical runs belong in evidence.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const PROBE_RETRY_TRANSIENT = true;
  const PROBE_RETRY_ATTEMPTS = 5;
  const PROBE_LIST = 'zzz dbmlsp multi value probe';
  const CLEANUP_AT_END = false;
  // ------------------------------------------------------------------------

  // The multi-value column under test, and its single-value twin, which is
  // the control for I1/I2. Both carry the SAME choice set so a difference in
  // behaviour can only be the multiplicity.
  const MULTI = 'Evt';
  const SINGLE = 'EvtSingle';
  const CHOICES = ['View', 'Edit', 'Export', 'Delete', 'PermissionChange'];

  // The CAML fixture. Titles are the identity every C row reports, so they
  // say what the row CONTAINS and a reader never has to hold the mapping in
  // their head. R4 is deliberately empty: three-valued logic is where the
  // negative predicates get interesting, and the deployer already wraps `neq`
  // in <Or><IsNull> for exactly that reason on single-value columns.
  const ROWS = [
    { title: 'R1 {View}', values: ['View'] },
    { title: 'R2 {View,Edit}', values: ['View', 'Edit'] },
    { title: 'R3 {Edit,Export}', values: ['Edit', 'Export'] },
    { title: 'R4 {}', values: [] },
  ];

  // Shared result registry v1. Register findings before any network work.
  const results = [];
  const expect = (id, question) => {
    results.push({
      id,
      question,
      observed: 'NOT ESTABLISHED',
      detail: 'the run did not reach this question',
    });
  };
  const record = (id, question, observed, detail) => {
    const row = results.find((candidate) => candidate.id === id);
    if (row) {
      Object.assign(row, { question, observed, detail: detail || '' });
    } else {
      results.push({ id, question, observed, detail: detail || '' });
    }
    log('INFO', `${id}: ${observed}${detail ? `: ${detail}` : ''}`);
  };
  const chainedViewOutcome = (controls) => {
    const unavailable = [];
    if (!controls.fixtureUsable) unavailable.push('CAML fixture');
    if (!controls.viewCreateOk) unavailable.push('view creation');
    if (!controls.viewReadOk) unavailable.push('view readback request');
    if (!controls.storedViewQuery) unavailable.push('stored ViewQuery');
    if (!controls.sentOk) unavailable.push('sent-query response');
    if (!controls.replayOk) unavailable.push('stored-query replay response');
    if (!controls.columnOnViewOk) unavailable.push('column-on-view request');
    if (!controls.viewUrl) unavailable.push('stored view URL');
    if (unavailable.length) {
      return {
        observed: 'NOT ESTABLISHED',
        detail: `NOT ESTABLISHED: unavailable control(s): ${unavailable.join(', ')}. Nothing is established about chained-predicate storage.`,
      };
    }
    const sameRows = JSON.stringify(controls.sentTitles) === JSON.stringify(controls.replayTitles);
    return sameRows
      ? {
        observed: 'MANUAL',
        detail: 'All machine controls succeeded and the sent and replayed row sets match.',
      }
      : {
        observed: 'CHANGED',
        detail: 'Storage changed the predicate result after all machine controls succeeded.',
      };
  };
  expect('Q0', 'the fixture actually built: two fields, four rows, seeded sets as asked');
  expect('M1', 'a MultiChoice field is created by a plain POST to /fields');
  expect('M2', 'the created field reads back as MultiChoice');
  expect('M3', 'which item WRITE shape SharePoint accepts');
  expect('M4', 'what an item value READS BACK as');
  expect('M5', 'a re-write round-trips, and member order survives');
  expect('I1', 'Indexed:true on a MultiChoice: accepted? and what does it read back as?');
  expect('I1C', 'CONTROL: Indexed:true on the SINGLE-value Choice, where Learn says it is supported');
  expect('I2', 'EnforceUniqueValues:true on a MultiChoice: accepted? readback?');
  expect('C1', 'CAML <Eq> "View" returns which rows');
  expect('C2', 'CAML <Eq> "View;#Edit" returns which rows');
  expect('C3', 'CAML <Contains> "View" returns which rows');
  expect('C4', 'CAML <Includes> "View" returns which rows');
  expect('C5', 'CAML <NotIncludes> "View" returns which rows');
  expect('C6', 'CAML <IsNull> returns which rows');
  expect('C7', 'CAML <IsNotNull> returns which rows');
  expect('C8', 'the winning predicate survives being STORED as a view ViewQuery (manual: look)');
  expect('C9', 'CAML <Neq> "View" returns which rows');
  expect('C10', 'CAML <Or><Neq><IsNull> "View" -- the deployer\'s own neq wrapper -- returns which rows');
  expect('C11', 'CAML <And> over two membership tests: does it mean "contains BOTH"?');
  expect('C12', 'CAML <Or> over two membership tests: does it mean "contains EITHER"?');
  expect('C13', 'CAML <Eq> against an EMPTY value: is it itself a null test?');
  expect('C14', 'a chained any_of predicate survives being STORED as a view ViewQuery');
  expect('V1', 'a ValidationFormula may reference a MultiChoice column');
  expect('F1', 'a calculated column formula may reference a MultiChoice column');
  expect('X1', 'the severity formatter this repo generates, on an array (manual: look)');

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
  log('INFO', `probe revision 5d3f21e4; core v2; results v1.`);
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

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const fieldPath = (name) => `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;
  // Written on create and checked before any delete: the probe will only
  // remove a list it can prove is its own, and says so rather than guessing.
  const PROBE_DESCRIPTION = 'dbml-sharepoint multi-value column probe. Safe to delete.';
  let createdList = false;
  let viewUrl = null;
  let listDefaultUrl = null;


  // The four candidate item-value shapes, most-likely first. Learn's list-item
  // REST page documents none of them for a multi-value column, so this is an
  // ordered experiment rather than a lookup, and the probe reports WHICH index
  // won rather than assuming the first.
  const writeShapes = [
    { name: 'collection-metadata', build: (v) => ({ __metadata: { type: 'Collection(Edm.String)' }, results: v }) },
    { name: 'bare-results', build: (v) => ({ results: v }) },
    { name: 'bare-array', build: (v) => v },
    { name: 'delimited-string', build: (v) => (v.length ? `;#${v.join(';#')};#` : '') },
  ];

  const show = (value) => {
    try { return JSON.stringify(value); } catch { return String(value); }
  };

  try {
    // === Setup: the list ==================================================
    // A cleanup re-run arrives with last run's list still there. Creating
    // over it fails on the title conflict, which would leave `createdList`
    // false and make the `finally` below skip the delete -- so the documented
    // "re-run with CLEANUP_AT_END = true" would never actually clean up and
    // the operator would be told it had. Remove the previous list first, and
    // only when it proves to be this probe's own by its Description.
    if (CLEANUP_AT_END) {
      const prior = await get(`${listPath}?$select=Title,Description`);
      if (prior.ok && prior.d?.Description === PROBE_DESCRIPTION) {
        const swept = await recycleOwnedList(PROBE_LIST, PROBE_DESCRIPTION);
        log(swept.ok ? 'INFO' : 'ERROR', swept.ok
          ? 'Recycled the list left behind by the previous run.'
          : `Could not recycle the previous run's list (${swept.error}). `
            + `Recycle it by hand: ${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`);
      } else if (prior.ok) {
        log('ERROR', `A list titled '${PROBE_LIST}' exists but its Description is `
          + `${show(prior.d?.Description)}, not this probe's. Refusing to delete a list this probe `
          + 'cannot prove it owns. Rename or remove it by hand, then re-run.');
        return { aborted: 'foreign-list-in-the-way' };
      }
    }
    const made = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: PROBE_LIST,
      Description: PROBE_DESCRIPTION,
    });
    if (!made.ok) {
      record('Q0', 'the fixture actually built', 'ABORTED', `could not create the probe list: HTTP ${made.status} ${made.error}`);
      throw new Error('setup failed');
    }
    createdList = true;
    listDefaultUrl = made.d?.DefaultViewUrl || null;
    log('INFO', `Created '${PROBE_LIST}'.`);

    // === M1: the deployer's own create path, unchanged =====================
    // This is deliberately the SAME shape jsgen._field_body builds for a
    // single-value Choice (POST the whole body to /fields), with only
    // FieldTypeKind and __metadata.type changed. If a MultiChoice needs the
    // AddField treatment a Lookup needs, this is where that shows up, and the
    // specification's "no new creation machinery" claim collapses.
    const createdMulti = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldMultiChoice' },
      FieldTypeKind: 15,
      Title: MULTI,
      Choices: { results: CHOICES },
      FillInChoice: false,
    });
    record(
      'M1',
      'a MultiChoice field is created by a plain POST to /fields',
      createdMulti.ok ? 'ACCEPTED' : 'REFUSED',
      createdMulti.ok
        ? `HTTP ${createdMulti.status}: the existing create path needs no AddField treatment`
        : `HTTP ${createdMulti.status}: ${createdMulti.error}`,
    );
    if (!createdMulti.ok) {
      record('Q0', 'the fixture actually built', 'ABORTED', 'the MultiChoice field could not be created, so nothing below can be asked');
      throw new Error('setup failed');
    }

    // The single-value control, created exactly as the tool creates one today.
    // It is I1C's concern and nothing else's: if it fails, the index rows go
    // VOID and every other row must carry on unaffected. So its failure is
    // said out loud here, and no other measurement is allowed to name it.
    const createdSingle = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldChoice' },
      FieldTypeKind: 6,
      Title: SINGLE,
      Choices: { results: CHOICES },
      FillInChoice: false,
    });
    if (!createdSingle.ok) {
      log('ERROR', `The single-value control field '${SINGLE}' was not created `
        + `(HTTP ${createdSingle.status} ${createdSingle.error}). I1/I1C go VOID. Item writes below `
        + 'omit it, so the multi-value rows are still answerable.');
    }

    // A POST to /fields creates the column but does NOT put it on the default
    // view. Found on run 2, where X1 could not be answered from `All Items`
    // because there was no Evt column there to look at -- the question is about
    // how the column RENDERS, so a column nobody can see answers nothing. The
    // deployer builds its views explicitly and declares their fields, so this
    // never bites a real build; it bites a probe that assumed otherwise.
    const onDefaultView = [];
    let multiOnDefaultView = { ok: false, status: 0, error: 'not attempted' };
    for (const name of [MULTI, SINGLE]) {
      if (name === SINGLE && !createdSingle.ok) continue;
      const added = await post(
        `${listPath}/DefaultView/viewfields/addviewfield('${odataName(name)}')`,
      );
      if (name === MULTI) multiOnDefaultView = added;
      onDefaultView.push(`${name}=${added.ok ? 'shown' : `HTTP ${added.status} ${added.error}`}`);
    }
    log('INFO', `Added to the default view: ${onDefaultView.join(' ')}`);

    // === M2: what did we actually get? =====================================
    const shape = await get(
      `${fieldPath(MULTI)}?$select=InternalName,TypeAsString,FieldTypeKind,Choices,FillInChoice,Indexed,EnforceUniqueValues`,
    );
    record(
      'M2',
      'the created field reads back as MultiChoice',
      shape.ok ? 'READ' : 'UNREADABLE',
      shape.ok
        ? `TypeAsString=${show(shape.d.TypeAsString)} FieldTypeKind=${show(shape.d.FieldTypeKind)} `
          + `Choices=${show(shape.d.Choices)} Indexed=${show(shape.d.Indexed)} `
          + `EnforceUniqueValues=${show(shape.d.EnforceUniqueValues)}`
        : `HTTP ${shape.status}: ${shape.error}`,
    );

    // === M3: which write shape does SharePoint take? =======================
    // R2 is the seeding row for this question because it has two members, and
    // a one-member set cannot distinguish a collection from a scalar.
    const itemType = await entityTypeFor(PROBE_LIST);
    let winningShape = null;
    let winningError = '';
    for (const candidate of writeShapes) {
      const body = {
        __metadata: { type: itemType },
        Title: ROWS[1].title,
        [MULTI]: candidate.build(ROWS[1].values),
      };
      // Only name the control field if it exists. Naming a field that was
      // never created makes SharePoint refuse the item for a reason that has
      // nothing to do with the multi-value shape, and all four candidates
      // would fail identically -- which reads as M3's answer.
      if (createdSingle.ok) body[SINGLE] = ROWS[1].values[0];
      const attempt = await post(`${listPath}/items`, body);
      if (attempt.ok) { winningShape = candidate; break; }
      winningError += `${candidate.name}: HTTP ${attempt.status} ${attempt.error}; `;
    }
    record(
      'M3',
      'which item WRITE shape SharePoint accepts',
      winningShape ? `ACCEPTED: ${winningShape.name}` : 'ALL FOUR REFUSED',
      winningShape
        ? `tried in order ${writeShapes.map((s) => s.name).join(', ')}; ${winningShape.name} won. `
          + `Earlier refusals: ${winningError || '(none, the first shape worked)'}`
        : winningError,
    );
    if (!winningShape) {
      record('Q0', 'the fixture actually built', 'ABORTED', 'no write shape was accepted, so no fixture exists and no C row means anything');
      throw new Error('setup failed');
    }

    // Seed the remaining three rows with the shape that won.
    const seedErrors = [];
    for (const row of ROWS) {
      if (row.title === ROWS[1].title) continue;
      const body = { __metadata: { type: itemType }, Title: row.title };
      if (row.values.length) {
        body[MULTI] = winningShape.build(row.values);
        if (createdSingle.ok) body[SINGLE] = row.values[0];
      }
      const seeded = await post(`${listPath}/items`, body);
      if (!seeded.ok) seedErrors.push(`${row.title}: HTTP ${seeded.status} ${seeded.error}`);
    }

    // === M4: what does it read back as? ====================================
    // Both content types, because the deployer speaks verbose and the reporting
    // layer's Power Query speaks nometadata, and they need not agree.
    // `Id` is selected because M5 re-writes R2 by id. The first run of this
    // probe selected only Title and the multi field, so `r2.Id` was undefined
    // and M5 POSTed to `items(undefined)` -- a 400 that reads exactly like
    // SharePoint refusing the re-write, when nothing had been asked of it.
    // The two requests differ ONLY in their Accept header, so any difference
    // in the answer is the content type's doing and nothing else's.
    const itemQuery = `${listPath}/items?$select=Id,Title,${odataName(MULTI)}&$orderby=Id`;
    const backVerbose = await get(itemQuery);
    const backNoMeta = await get(itemQuery, 'application/json;odata=nometadata');
    const verboseRows = backVerbose.d?.results || [];
    const noMetaRows = backNoMeta.d?.value || backNoMeta.d?.results || [];
    // A refused nometadata GET leaves noMetaRows empty, which is
    // indistinguishable from SharePoint answering with nothing in it. Say
    // which happened; half an answer here is worse than none.
    const noMetaDetail = backNoMeta.ok
      ? `nometadata: ${show(noMetaRows.map((r) => ({ [r.Title]: r[MULTI] })))}`
      : `nometadata: REQUEST FAILED HTTP ${backNoMeta.status}: ${backNoMeta.error} `
        + '(not observed to be empty, not observed at all)';
    record(
      'M4',
      'what an item value READS BACK as',
      backVerbose.ok && backNoMeta.ok && verboseRows.length
        ? 'READ'
        : (verboseRows.length ? 'READ (verbose only)' : 'UNREADABLE'),
      (backVerbose.ok
        ? `verbose: ${show(verboseRows.map((r) => ({ [r.Title]: r[MULTI] })))}`
        : `verbose: REQUEST FAILED HTTP ${backVerbose.status}: ${backVerbose.error}`)
      + ` || ${noMetaDetail}`,
    );

    // === Q0: the fixture control ===========================================
    // Asserted, because everything below DEPENDS on it. The seeded sets are
    // compared to what was asked for, by member and ignoring order, because
    // order is M5's question, not this one.
    const sameMembers = (a, b) => {
      const norm = (v) => {
        if (v == null) return [];
        if (Array.isArray(v)) return [...v].sort();
        if (Array.isArray(v.results)) return [...v.results].sort();
        if (typeof v === 'string') return v.split(';#').filter(Boolean).sort();
        return [show(v)];
      };
      const [x, y] = [norm(a), norm(b)];
      return x.length === y.length && x.every((value, index) => value === y[index]);
    };
    const wrongRows = ROWS.filter((row) => {
      const got = verboseRows.find((r) => r.Title === row.title);
      return !got || !sameMembers(got[MULTI], row.values);
    });
    // The field's TYPE is a depends-on value, not an observation: if it did
    // not come back MultiChoice, then every C, I, V, F and X row below is
    // about some other kind of column and none of them means what it says.
    // M2 still reports whatever it read, unasserted -- that stays a question.
    const multiTypeOk = shape.ok && shape.d?.TypeAsString === 'MultiChoice';
    // Kept apart from the control field on purpose. A missing single-value
    // control voids I1/I1C and nothing else, so it must not be able to stamp
    // "meaningless" on predicate rows that do not depend on it.
    const fixtureUsable = multiTypeOk && !seedErrors.length && !wrongRows.length
      && verboseRows.length === ROWS.length;
    record(
      'Q0',
      'the fixture actually built: two fields, four rows, seeded sets as asked',
      (fixtureUsable && createdSingle.ok) ? 'BUILT' : 'FAILED',
      `rows=${verboseRows.length}/${ROWS.length} ${MULTI} TypeAsString=${show(shape.d?.TypeAsString)} `
      + `single-value control field=${createdSingle.ok ? 'created' : 'FAILED'} `
      + `mismatched=${show(wrongRows.map((r) => r.title))} ${seedErrors.join('; ')}`,
    );
    if (!multiTypeOk) {
      log('ERROR', `${MULTI} did not read back as MultiChoice (TypeAsString=${show(shape.d?.TypeAsString)}). `
        + 'Every row below is about a different kind of column than the one this probe asks about.');
    }
    if (wrongRows.length || verboseRows.length !== ROWS.length) {
      log('ERROR', 'The fixture is not what the C rows assume. Every predicate result below is meaningless until this is fixed.');
    }

    // === M5: idempotent re-write, and order ================================
    // The deployer's ONLY array comparator (Choices, in _field_reconcile) is
    // order-sensitive. If SharePoint normalises member order on write, a
    // re-run comparing exactly would see permanent drift.
    const r2 = verboseRows.find((r) => r.Title === ROWS[1].title);
    let m5detail = 'R2 was not readable';
    let m5observed = 'NOT ESTABLISHED';
    // C1..C10 read R2's members. M5 is the only row that mutates them, so its
    // restoration is a value those ten rows DEPEND ON, and an unverified
    // restoration would let them record a mutated fixture under the meanings
    // printed beside them. Nothing else touches R2, so it starts true.
    let r2Restored = true;
    let r2RestoreNote = '';
    if (r2) {
      const reversed = [...ROWS[1].values].reverse();
      const rewritten = await merge(`${listPath}/items(${r2.Id})`, {
        __metadata: { type: itemType },
        [MULTI]: winningShape.build(reversed),
      });
      const after = await get(`${listPath}/items(${r2.Id})?$select=${odataName(MULTI)}`);
      // The whole question is what came BACK, so a failed readback answers
      // nothing. Printing `undefined` beside "REWRITTEN" would put a value
      // this run never saw where the observation belongs.
      m5observed = rewritten.ok
        ? (after.ok ? 'REWRITTEN' : 'REWRITTEN, READBACK UNREADABLE')
        : 'WRITE REFUSED';
      m5detail = rewritten.ok
        ? (after.ok
          ? `wrote ${show(reversed)}; read back ${show(after.d?.[MULTI])}. `
            + 'If the readback is in the WRITTEN order, an exact comparison is safe; if it is normalised, '
            + 'the reconciler must compare as a SET or it will report drift on every redeploy.'
          : `wrote ${show(reversed)}; the readback FAILED HTTP ${after.status}: ${after.error}. `
            + 'Whether the value round-trips and whether member order survives are both NOT established '
            + 'by this run.')
        : `HTTP ${rewritten.status}: ${rewritten.error}`;
      // Put R2 back the way the C rows expect it, and PROVE it went back. The
      // readback above is M5's OBSERVATION and is never asserted; this one is
      // a CONTROL over the fixture the C rows inherit, so it is checked by
      // member and the dependent rows fail closed when it does not hold. It
      // runs whether or not the mutation was accepted: a refused MERGE that
      // nevertheless landed would leave R2 reversed just the same.
      const restore = await merge(`${listPath}/items(${r2.Id})`, {
        __metadata: { type: itemType }, [MULTI]: winningShape.build(ROWS[1].values),
      });
      const restoreBack = await get(`${listPath}/items(${r2.Id})?$select=${odataName(MULTI)}`);
      r2Restored = restore.ok && restoreBack.ok && sameMembers(restoreBack.d?.[MULTI], ROWS[1].values);
      r2RestoreNote = r2Restored
        ? ` R2 was restored to ${show(ROWS[1].values)} and read back as such.`
        : ` R2 COULD NOT BE PROVED RESTORED: write ${restore.ok ? `HTTP ${restore.status}` : `REFUSED HTTP ${restore.status} ${restore.error}`}, `
          + `readback ${restoreBack.ok ? show(restoreBack.d?.[MULTI]) : `FAILED HTTP ${restoreBack.status} ${restoreBack.error}`}.`;
      if (!r2Restored) {
        log('ERROR', `R2 was mutated by M5 and could not be proved restored.${r2RestoreNote} `
          + 'C1..C10 read R2, so their rows are NOT ESTABLISHED from this run.');
      }
    }
    record('M5', 'a re-write round-trips, and member order survives', m5observed, m5detail + r2RestoreNote);
    // What the CAML rows actually depend on: the seeded fixture AND R2 having
    // been put back after M5 mutated it.
    const camlFixtureUsable = fixtureUsable && r2Restored;

    // === I1 / I1C: the index question, and its control =====================
    // The GET is kept, not flattened to a placeholder. A readback that never
    // arrived is not an observation of `false`: folding a transport failure
    // into the value would let it print as ACCEPTED BUT DID NOT STICK, which
    // is a statement about SharePoint this run did not make. I2 below already
    // keeps the two apart; I1 now does the same.
    const indexOne = async (name, metaType) => {
      const wrote = await merge(fieldPath(name), { __metadata: { type: metaType }, Indexed: true });
      const back = await get(`${fieldPath(name)}?$select=Indexed`);
      return { wrote, back };
    };
    const notAttempted = { ok: false, status: 0, error: 'control field was never created' };
    const multiIndex = await indexOne(MULTI, 'SP.FieldMultiChoice');
    const singleIndex = createdSingle.ok
      ? await indexOne(SINGLE, 'SP.FieldChoice')
      : { wrote: notAttempted, back: notAttempted };
    const indexReadback = (r) => (r.back.ok
      ? show(r.back.d?.Indexed)
      : `UNREADABLE (HTTP ${r.back.status} ${r.back.error})`);

    // An unreadable control is not a control that failed. Either way I1 is
    // void, but the transcript has to say which, or a reader takes a network
    // failure for evidence about the property.
    const controlHeld = singleIndex.wrote.ok && singleIndex.back.ok && singleIndex.back.d?.Indexed === true;
    record(
      'I1C',
      'CONTROL: Indexed:true on the SINGLE-value Choice, where Learn says it is supported',
      controlHeld
        ? 'STUCK'
        : (singleIndex.wrote.ok && !singleIndex.back.ok ? 'READBACK UNREADABLE' : 'DID NOT STICK'),
      `write ${singleIndex.wrote.ok ? `HTTP ${singleIndex.wrote.status}` : `REFUSED ${singleIndex.wrote.error}`}, `
      + `readback Indexed=${indexReadback(singleIndex)}`,
    );
    record(
      'I1',
      'Indexed:true on a MultiChoice: accepted? and what does it read back as?',
      controlHeld
        ? (multiIndex.wrote.ok
          ? (multiIndex.back.ok
            ? (multiIndex.back.d?.Indexed === true ? 'ACCEPTED AND STUCK' : 'ACCEPTED BUT DID NOT STICK')
            : 'ACCEPTED, READBACK UNREADABLE')
          : 'REFUSED')
        : 'VOID',
      controlHeld
        ? `write ${multiIndex.wrote.ok ? `HTTP ${multiIndex.wrote.status}` : `REFUSED ${multiIndex.wrote.error}`}, `
          + `readback Indexed=${indexReadback(multiIndex)}. `
          + (multiIndex.wrote.ok && !multiIndex.back.ok
            ? 'The write was taken but the readback never arrived, so whether it stuck is NOT established by '
              + 'this run, and this is not the same finding as a property that read back false. '
            : '')
          + 'REFUSED is the good outcome (loud). ACCEPTED BUT DID NOT STICK aborts a deploy part-way, which is '
          + 'survivable. ACCEPTED AND STUCK is the dangerous one: the property claims an index Learn says '
          + 'cannot exist, and nothing in a build or a deploy could ever see the difference.'
        : `the single-value control did not hold (${indexReadback(singleIndex)}), so this property is not `
          + 'reporting what the question needs on this tenant and BOTH index rows are void, exactly the '
          + 'outcome native-index-probe.js hit with its ID control on 2026-07-30. An UNREADABLE control voids '
          + 'them for a different reason than one that read back false; I1C says which.',
    );

    // === I2: uniqueness ====================================================
    // Learn lists "Choice (multi-valued)" as unable to enforce unique values.
    // Whether REST refuses it or silently drops it decides whether the
    // validator's refusal is a convenience or a necessity.
    //
    // EnforceUniqueValues is asked ALONE first. Sending it together with
    // Indexed:true (which I1 may already have found refused on this column)
    // would let one refusal answer for the other, and the transcript could not
    // say which property SharePoint objected to. SharePoint does require an
    // index behind a uniqueness constraint, so if the lone write is refused
    // the paired write is tried too, and BOTH results are reported: a lone
    // refusal that a paired write then satisfies is a different finding from
    // a column that refuses uniqueness however it is asked.
    const uniqueAlone = await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' }, EnforceUniqueValues: true,
    });
    const uniquePaired = uniqueAlone.ok ? null : await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' }, EnforceUniqueValues: true, Indexed: true,
    });
    const uniqueWrite = uniqueAlone.ok ? uniqueAlone : (uniquePaired || uniqueAlone);
    const uniqueBack = await get(`${fieldPath(MULTI)}?$select=EnforceUniqueValues,Indexed`);
    const pairedNote = uniquePaired
      ? `alone: REFUSED HTTP ${uniqueAlone.status} ${uniqueAlone.error}; `
        + `with Indexed:true: ${uniquePaired.ok ? `HTTP ${uniquePaired.status}` : `REFUSED HTTP ${uniquePaired.status} ${uniquePaired.error}`}. `
      : `alone: HTTP ${uniqueAlone.status} (no paired attempt needed). `;
    record(
      'I2',
      'EnforceUniqueValues:true on a MultiChoice: accepted? readback?',
      uniqueWrite.ok
        // An unreadable readback is not the same answer as a readback of
        // false, and reporting it as DID NOT STICK would state a fact this
        // run never observed.
        ? (uniqueBack.ok
          ? (uniqueBack.d?.EnforceUniqueValues === true ? 'ACCEPTED AND STUCK' : 'ACCEPTED BUT DID NOT STICK')
          : 'ACCEPTED, READBACK UNREADABLE')
        : 'REFUSED',
      uniqueWrite.ok
        ? pairedNote + (uniqueBack.ok
          ? `readback EnforceUniqueValues=${show(uniqueBack.d?.EnforceUniqueValues)} `
            + `Indexed=${show(uniqueBack.d?.Indexed)}`
          : `readback FAILED HTTP ${uniqueBack.status}: ${uniqueBack.error}; whether it stuck is `
            + 'NOT established by this run')
        : pairedNote,
    );
    // Leave the field in a known state for the rows below, and PROVE it. C1..C10
    // do not write, so they survive a failed reset; V1's save test does, and a
    // uniqueness constraint left standing would refuse its items for a reason
    // that is not V1's question. So this is read back and the affected rows
    // fail closed individually rather than the run being abandoned, since the other
    // fifteen questions have already cost the operator a live paste.
    const resetWrite = await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' }, EnforceUniqueValues: false, Indexed: false,
    });
    const resetBack = await get(`${fieldPath(MULTI)}?$select=EnforceUniqueValues,Indexed`);
    const fieldStateKnown = resetWrite.ok && resetBack.ok
      && resetBack.d?.EnforceUniqueValues === false && resetBack.d?.Indexed === false;
    if (!fieldStateKnown) {
      log('ERROR', `Could not return ${MULTI} to a known state (unique off, indexed off): `
        + `write ${resetWrite.ok ? `HTTP ${resetWrite.status}` : `REFUSED ${resetWrite.error}`}, `
        + `readback ${resetBack.ok ? show(resetBack.d) : `FAILED ${resetBack.error}`}. `
        + 'V1\'s save test will not run against an unknown field state.');
    }

    // === C1..C7: which rows does each predicate actually return? ===========
    //
    // NOTHING HERE IS ASSERTED. Each row records the titles that came back and
    // the probe prints, beside them, the interpretation each possible answer
    // would carry. Writing the expected set into an assertion would make the
    // experiment fail the moment SharePoint answered something interesting,
    // which is the failure AGENTS.md names.
    //
    // The fixture, for reading the results:
    //   R1 {View}  R2 {View,Edit}  R3 {Edit,Export}  R4 {}
    const ref = `<FieldRef Name="${MULTI}"/>`;
    const textValue = (v) => `<Value Type="Text">${v}</Value>`;
    const predicates = [
      ['C1', 'Eq "View"', `<Eq>${ref}${textValue('View')}</Eq>`,
        'R1 only means Eq compares the WHOLE SET; R1+R2 means Eq behaves as "includes"; nothing means Eq is unusable here'],
      ['C2', 'Eq "View;#Edit"', `<Eq>${ref}${textValue('View;#Edit')}</Eq>`,
        'R2 only would mean the stored value is the ;#-delimited string and Eq matches it literally'],
      ['C3', 'Contains "View"', `<Contains>${ref}${textValue('View')}</Contains>`,
        'Learn documents Contains for Text/Note only. R1+R2 means it works anyway; nothing means it does not'],
      ['C4', 'Includes "View"', `<Includes>${ref}${textValue('View')}</Includes>`,
        'Learn documents Includes for multi-value LOOKUP only. R1+R2 means it also serves MultiChoice, which is '
        + 'the answer the condition grammar needs; nothing means the grammar has no membership operator at all'],
      ['C5', 'NotIncludes "View"', `<NotIncludes>${ref}${textValue('View')}</NotIncludes>`,
        'R3 only means the empty row R4 is EXCLUDED (three-valued, like every other CAML negative); R3+R4 means '
        + 'it is included. The deployer already wraps `neq` in <Or><IsNull> for exactly this reason'],
      ['C6', 'IsNull', `<IsNull>${ref}</IsNull>`, 'R4 only is the expected shape of a working null test'],
      ['C7', 'IsNotNull', `<IsNotNull>${ref}</IsNotNull>`, 'R1+R2+R3 is the expected shape'],
      // Added after the first live run, which left NEGATION with no working
      // predicate at all: <NotIncludes> returned nothing, and <Eq> turned out
      // to mean "includes" -- so its negation is the obvious candidate and was
      // never asked. If this also returns nothing, the condition grammar must
      // REFUSE every negative operator on a multi-value column by name, rather
      // than emit a filter that silently shows an empty view.
      ['C9', 'Neq "View"', `<Neq>${ref}${textValue('View')}</Neq>`,
        'R3 only means Neq is the negative membership operator and excludes the empty row R4, like every other '
        + 'CAML negative; R3+R4 means it includes it; nothing means negation is unavailable and must be refused'],
      // The mirror of C9 in the shape the deployer actually emits for `neq`.
      // If C9 works but this does not, the wrapper is the problem, not Neq.
      ['C10', 'Or[Neq "View", IsNull]',
        `<Or><Neq>${ref}${textValue('View')}</Neq><IsNull>${ref}</IsNull></Or>`,
        'R3+R4 is what the deployer\'s existing `neq` wrapper is for -- it exists so a null row is not silently '
        + 'dropped by a negative. Anything else means the wrapper does not compose with a multi-value column'],
      // C11..C13 added after run 3, from an operator building filters by hand
      // in the list UI. Run 3 asked only about SINGLE predicates, so nothing
      // here was measured, and the UI pane cannot answer them either: it does
      // not show the CAML it generates, so "it worked in the pane" leaves the
      // emitted spelling unknown. These ask in the one place the answer is
      // usable, which is the XML the deployer would have to write.
      //
      // C11 and C12 are the interesting pair BECAUSE Eq means "includes"
      // here. Composition over a set is not the same question as composition
      // over a scalar, and a grammar that offers `and` on a multi-value
      // column without measuring it would be guessing which of the two it is.
      ['C11', 'And[Eq "View", Eq "Edit"]',
        `<And><Eq>${ref}${textValue('View')}</Eq><Eq>${ref}${textValue('Edit')}</Eq></And>`,
        'R2 only means And over two membership tests is "contains BOTH", which is the useful reading and the '
        + 'one the grammar would expose. Nothing means SharePoint cannot conjoin two predicates over the same '
        + 'multi-value column at all, and `and` must be refused on one'],
      ['C12', 'Or[Eq "View", Eq "Export"]',
        `<Or><Eq>${ref}${textValue('View')}</Eq><Eq>${ref}${textValue('Export')}</Eq></Or>`,
        'R1+R2+R3 means Or is "contains EITHER". Anything narrower means Or does not distribute over membership '
        + 'the way it does over a scalar equality, and the grammar must say so rather than emit it'],
      // The operator reported that an "is equal to" with the value box left
      // EMPTY returns the empty row, i.e. it behaves as a null test. That is
      // the same ROWS as C6, but not necessarily the same PREDICATE: the pane
      // may have rewritten it to <IsNull/>. Which one it is decides what the
      // renderer must emit for `col eq ''`, so it is asked directly here.
      ['C13', 'Eq "" (empty value)', `<Eq>${ref}${textValue('')}</Eq>`,
        'R4 means an empty-valued Eq is itself a null test on this type, so `col eq \'\'` may render literally. '
        + 'Nothing means only <IsNull> tests null and the renderer must translate, which is what the UI pane '
        + 'appears to do. Either way C6 remains the operator the grammar should emit'],
    ];
    const camlRows = async (where) => {
      const r = await post(`${listPath}/GetItems?$select=Title`, {
        query: {
          __metadata: { type: 'SP.CamlQuery' },
          ViewXml: `<View><Query><Where>${where}</Where></Query><RowLimit>50</RowLimit></View>`,
        },
      });
      if (!r.ok) return { ok: false, error: `HTTP ${r.status} ${r.error}`, titles: null };
      return { ok: true, error: null, titles: (r.d?.results || []).map((i) => i.Title).sort() };
    };
    // Only a SINGLE predicate may be the membership winner. A compound can
    // reach the same two rows by FAILING: if <And> ignored its second arm,
    // C11 would return exactly R1+R2 and be crowned, C8 would then store a
    // broken compound, and the verdict line would report it as
    // caml_membership. C1 wins first in practice; this makes that structural
    // rather than a consequence of array order.
    const MEMBERSHIP_CANDIDATES = new Set(['C1', 'C2', 'C3', 'C4', 'C5']);
    let membershipWinner = null;
    for (const [id, label, where, meaning] of predicates) {
      const got = await camlRows(where);
      record(
        id,
        `CAML <${label.split(' ')[0]}> returns which rows`,
        got.ok ? (camlFixtureUsable ? 'RETURNED' : 'NOT ESTABLISHED') : 'QUERY REFUSED',
        got.ok
          ? `${label} -> ${show(got.titles)} || `
            + (camlFixtureUsable
              ? meaning
              : 'the fixture these rows are read against is not established (see Q0 and M5), so this row '
                + 'is a list of titles and not an answer. Do not read the meaning off it; fix and re-run.')
          : `${label} -> ${got.error}`,
      );
      // Remember whichever membership predicate returned BOTH View-bearing
      // rows, for the stored-view confirmation in C8. Observed, not asserted:
      // if none does, C8 records that there was nothing to confirm.
      if (!membershipWinner && got.ok && MEMBERSHIP_CANDIDATES.has(id)
          && got.titles.length === 2
          && got.titles.includes(ROWS[0].title) && got.titles.includes(ROWS[1].title)) {
        membershipWinner = { id, label, where };
      }
    }

    // === C8: does it survive being STORED? =================================
    // Every C row above used an ad-hoc CamlQuery. The deployer writes a VIEW's
    // ViewQuery, and SharePoint rewrites that XML on save. datetime-sentinel-
    // probe.js found an element that worked in one position and silently
    // returned nothing in the other. So the predicate that matters is stored,
    // read back, and looked at.
    const VIEW_TITLE = 'Probe membership';
    if (membershipWinner) {
      const view = await post(`${listPath}/views`, {
        __metadata: { type: 'SP.View' },
        Title: VIEW_TITLE,
        ViewQuery: `<Where>${membershipWinner.where}</Where>`,
        RowLimit: 50,
      });
      const views = await get(`${listPath}/views?$select=Id,Title,ServerRelativeUrl,ViewQuery`);
      const stored = (views.d?.results || []).find((v) => v.Title === VIEW_TITLE);
      viewUrl = stored?.ServerRelativeUrl || null;
      // Addressed by TITLE, which is the form Learn's AddViewField page
      // actually documents: `views/getbytitle('<view>')/ViewFields/
      // AddViewField('<internal name>')`. A bare `views('<guid>')` indexer is
      // not documented anywhere, and the title is known exactly: this probe
      // just created the view under it. The result is checked, because C8 is
      // a LOOK at a view and a view missing the tested column answers nothing.
      const columnOnView = stored
        ? await post(`${listPath}/views/getbytitle('${odataName(VIEW_TITLE)}')/viewfields/addviewfield('${odataName(MULTI)}')`)
        : { ok: false, status: 0, error: 'the view was never created' };
      record(
        'C8',
        'the winning predicate survives being STORED as a view ViewQuery (manual: look)',
        view.ok && stored && columnOnView.ok && camlFixtureUsable ? 'MANUAL' : 'NOT ESTABLISHED',
        view.ok && stored && columnOnView.ok
          ? `stored ${membershipWinner.label}; SharePoint read the query back as ${show(stored.ViewQuery)}. `
            + (camlFixtureUsable
              ? `OPEN ${window.location.origin}${viewUrl} and confirm it lists exactly R1 and R2. `
                + 'A view that lists everything, or nothing, means the predicate does not survive storage and '
                + 'the condition grammar must refuse it however well GetItems behaved.'
              : 'The fixture is not established (Q0 FAILED, or M5 could not prove R2 restored), so the rows '
                + 'this view would be judged against are not the fixture the winning predicate was chosen '
                + 'from. Do not read this view as an answer; fix the fixture and re-run.')
          : `could not create, read or populate the view: ${view.ok
            ? (stored
              ? `${MULTI} could not be added to it (HTTP ${columnOnView.status} ${columnOnView.error}), so there `
                + 'is nothing to look at'
              : 'not found after create')
            : `HTTP ${view.status} ${view.error}`}`,
      );
    } else {
      record(
        'C8',
        'the winning predicate survives being STORED as a view ViewQuery',
        'NOT REACHED',
        'no predicate above returned exactly the two View-bearing rows, so there was nothing to confirm. '
        + 'That is itself the finding: the condition grammar would have no membership operator to render.',
      );
    }

    // === C14: does a CHAINED predicate survive storage? ====================
    // C8 stored ONE <Eq>. But <Includes> returned nothing here, so this
    // grammar has no set operator and tells authors to build one out of
    // all_of/any_of instead -- the refusal message says so in as many words.
    // CAML's And and Or are strictly binary (documented), so any_of over K
    // members emits a left-folded tree K-1 deep, and NOTHING measures how
    // deep that may go. Learn asserts "the server supports unlimited
    // complicated queries" on both the And and the Or pages, which is a claim
    // about a server, not about what SharePoint Online's view save does to
    // the XML on the way past.
    //
    // That is the risk worth asking about, and it is not the depth ceiling.
    // A view rewritten on save into something that still parses and returns
    // the wrong rows is silent, and it is exactly what datetime-sentinel-
    // probe.js caught in the other direction. So: store a COMPOUND predicate,
    // read the XML back, and replay what SharePoint stored rather than what
    // was sent. If the two disagree about rows, storage changed the meaning.
    //
    // The depth CEILING needs a wider enum than this fixture's five members
    // (four is the deepest honest chain here, nowhere near any plausible
    // limit) and is tracked by #266. This row asks the cheap half.
    const CHAIN_VIEW = 'Probe chained membership';
    // Padded with two members no row holds, so the expected rows are C1's and
    // only the DEPTH differs. A chain that changes the answer changes it
    // because it is a chain, not because the predicate means something else.
    const chainWhere = `<Or><Or><Eq>${ref}${textValue('View')}</Eq>`
      + `<Eq>${ref}${textValue('Delete')}</Eq></Or>`
      + `<Eq>${ref}${textValue('PermissionChange')}</Eq></Or>`;
    const chainSent = await camlRows(chainWhere);
    const chainView = await post(`${listPath}/views`, {
      __metadata: { type: 'SP.View' },
      Title: CHAIN_VIEW,
      ViewQuery: `<Where>${chainWhere}</Where>`,
      RowLimit: 50,
    });
    const chainViews = chainView.ok
      ? await get(`${listPath}/views?$select=Title,ViewQuery,ServerRelativeUrl`)
      : null;
    const chainStored = (chainViews?.d?.results || []).find((v) => v.Title === CHAIN_VIEW);
    const chainViewUrl = chainStored?.ServerRelativeUrl || null;
    const chainColumnOnView = chainStored
      ? await post(`${listPath}/views/getbytitle('${odataName(CHAIN_VIEW)}')/viewfields/addviewfield('${odataName(MULTI)}')`)
      : { ok: false, status: 0, error: 'the chained view was not read back' };
    // Replay what was STORED, not what was sent. Same helper, so a difference
    // in rows can only come from a difference in the XML.
    const chainReplay = chainStored
      ? await camlRows(String(chainStored.ViewQuery).replace(/^<Where>|<\/Where>$/g, ''))
      : null;
    // Every request and fixture control must succeed before semantic or manual
    // guidance is reachable. A failed control is neutral evidence, even if the
    // partial row values happen to differ.
    const c14Outcome = chainedViewOutcome({
      fixtureUsable: camlFixtureUsable,
      viewCreateOk: chainView.ok,
      viewReadOk: !!chainViews?.ok,
      storedViewQuery: chainStored?.ViewQuery || null,
      sentOk: chainSent.ok,
      sentTitles: chainSent.titles,
      replayOk: !!chainReplay?.ok,
      replayTitles: chainReplay?.titles,
      columnOnViewOk: chainColumnOnView.ok,
      viewUrl: chainViewUrl,
    });
    record(
      'C14',
      'a chained any_of predicate survives being STORED as a view ViewQuery',
      c14Outcome.observed,
      c14Outcome.observed === 'NOT ESTABLISHED'
        ? c14Outcome.detail
        : `sent ${show(chainWhere)} and got ${show(chainSent.titles)}; SharePoint stored `
          + `${show(chainStored.ViewQuery)} which replays to ${show(chainReplay?.titles)}. `
          + (c14Outcome.observed === 'MANUAL'
            ? (chainColumnOnView.ok && chainViewUrl
              ? `OPEN ${window.location.origin}${chainViewUrl} and capture the stored chained view. Confirm `
                + 'R1 {View} and R2 {View,Edit} are visible, while R3 {Edit,Export} and R4 {} are absent. '
              : `The replay returned the expected rows, but the visible state is unreachable: column-on-view=${chainColumnOnView.ok}, URL=${chainViewUrl || '(missing)'}. `)
              + 'Same rows are weaker than they look. The padding members '
              + 'Delete and PermissionChange are held by no row, so dropping either arm during storage '
              + 'leaves the result identical: this row cannot tell a surviving chain from a truncated '
              + 'one. It establishes only that the view stored and still answers. Nor does it speak to '
              + 'all_of: only a nested Or was stored here. test/manual/caml-chain-depth-probe.js seeds '
              + 'one row per member so the COUNT is the measurement, and it is what actually settled '
              + 'this: no query-side ceiling to 40 disjuncts, and a filter editor that truncates at ten.'
            : `${c14Outcome.detail} The grammar must refuse `
              + 'chained membership on a multi-value column rather than emit a view that quietly '
              + 'answers a different question.'),
    );

    // === V1: validation formula operand ====================================
    // mapping.md already records that validation formulas refuse Lookup and
    // Person operands. Multi-value is not documented either way.
    //
    // Accepting the MERGE is NOT the answer. An accepted-but-inert formula
    // (one that saves, reads back byte-identical and never blocks anything)
    // is the exact failure class this directory exists to catch, so the row
    // that used to say "accepted" and caveat itself in prose now asks all
    // three questions: does SharePoint take it, does it keep it, does it FIRE.
    const VALIDATION_FORMULA = `=NOT(ISBLANK([${MULTI}]))`;
    const validation = await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' },
      ValidationFormula: VALIDATION_FORMULA,
      ValidationMessage: 'probe',
    });
    const validationBack = validation.ok
      ? await get(`${fieldPath(MULTI)}?$select=ValidationFormula`)
      : null;
    // Both sides, because only one of them is diagnostic on its own: a refused
    // violating save proves the rule fires, and an accepted compliant save
    // proves the refusal was the rule rather than the column. Neither is
    // asserted. Whatever happens is recorded and both rows are removed again.
    let firing = 'not attempted';
    if (validation.ok && fieldStateKnown) {
      const violating = await post(`${listPath}/items`, {
        __metadata: { type: itemType }, Title: 'V1 violating (no members)',
      });
      const compliant = await post(`${listPath}/items`, {
        __metadata: { type: itemType }, Title: 'V1 compliant (one member)',
        [MULTI]: winningShape.build([CHOICES[0]]),
      });
      firing = `violating save ${violating.ok
        ? `ACCEPTED HTTP ${violating.status}, so the stored rule did NOT fire`
        : `REFUSED HTTP ${violating.status} (${violating.error})`}; `
        + `compliant save ${compliant.ok
          ? `ACCEPTED HTTP ${compliant.status}`
          : `REFUSED HTTP ${compliant.status} (${compliant.error}), so a refusal above cannot be `
            + 'attributed to the rule'}`;
      for (const made of [violating, compliant]) {
        if (made.ok && made.d?.Id !== undefined) {
          await post(`${listPath}/items(${made.d.Id})`, undefined,
            { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
        }
      }
    } else if (validation.ok) {
      firing = `NOT attempted: ${MULTI} is not in a known state (see the reset error above), so a refused `
        + 'save could be a leftover uniqueness constraint rather than the validation formula';
    }
    record(
      'V1',
      'a ValidationFormula may reference a MultiChoice column',
      validation.ok ? 'ACCEPTED' : 'REFUSED',
      validation.ok
        ? `HTTP ${validation.status} stored. Read back as ${show(validationBack?.d?.ValidationFormula)} `
          + `(wrote ${show(VALIDATION_FORMULA)}). Does it FIRE: ${firing}. `
          + 'ACCEPTED with a rule that does not fire is the worst outcome here, not the best: nothing in a '
          + 'build or a deploy could ever see it, and the validator would be free to emit a rule that does '
          + 'nothing.'
        : `HTTP ${validation.status}: ${validation.error}`,
    );
    if (validation.ok) {
      await merge(fieldPath(MULTI), {
        __metadata: { type: 'SP.FieldMultiChoice' }, ValidationFormula: '', ValidationMessage: '',
      });
    }

    // === F1: calculated-column operand =====================================
    // The same question calculated-operand-probe.js asked of every other type
    // on 2026-07-30, asked of the one type that did not exist then.
    // Same discipline as V1: a field-creation 200 says the formula was taken,
    // not that it survived intact or that it evaluates. SharePoint normalises
    // formulas on save, and a calculated column can also store fine and then
    // render an error value in every row. Both are read.
    const CALC_FIELD = 'CalcOverMulti';
    const CALC_FORMULA = `=[${MULTI}]`;
    const calc = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldCalculated' },
      FieldTypeKind: 17,
      Title: CALC_FIELD,
      OutputType: 2,
      Formula: CALC_FORMULA,
    });
    const calcBack = calc.ok
      ? await get(`${listPath}/fields/getbyinternalnameortitle('${odataName(CALC_FIELD)}')?$select=Formula,OutputType`)
      : null;
    const calcValues = calc.ok
      ? await get(`${listPath}/items?$select=Title,${odataName(CALC_FIELD)}&$orderby=Id`)
      : null;
    record(
      'F1',
      'a calculated column formula may reference a MultiChoice column',
      calc.ok ? 'ACCEPTED' : 'REFUSED',
      calc.ok
        ? `HTTP ${calc.status} stored. Formula read back as ${show(calcBack?.d?.Formula)} `
          + `(wrote ${show(CALC_FORMULA)}). Evaluated per row: ${calcValues?.ok
            ? show((calcValues.d?.results || []).map((r) => ({ [r.Title]: r[CALC_FIELD] })))
            : `NOT READ (HTTP ${calcValues?.status} ${calcValues?.error})`}. `
          + 'The operand matrix in reference/dbml.md gains a row only if the formula survived AND every row '
          + 'evaluated to a value rather than an error.'
        : `HTTP ${calc.status}: ${calc.error}`,
    );

    // === X1: the formatter this repository actually generates ==============
    // Not an invented formatter, but the exact shape analysis/styles.py::_severity
    // emits, with the =if(@currentField == 'X', ...) chain its _condition()
    // builds. Learn documents @currentField on a MultiChoice as an ARRAY, so
    // every branch of an == comparison against a quoted string should be false
    // and the cell should render unstyled. That is precisely the failure
    // STYLE_ON_BOOLEAN_MATCHES_NOTHING already names for Yes/No columns. This
    // asks whether the array case behaves the same way, and it can only be
    // answered by looking.
    const severityFormatter = {
      $schema: 'https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json',
      elmType: 'div',
      style: { display: "=if(@currentField == '', 'none', 'flex')", 'border-radius': '4px' },
      attributes: {
        class: "=if(@currentField == 'View', 'sp-field-severity--good', "
          + "if(@currentField == 'Edit', 'sp-field-severity--warning', 'ms-bgColor-neutralLight'))",
      },
      children: [{ elmType: 'span', txtContent: '@currentField' }],
    };
    const formatted = await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' },
      CustomFormatter: JSON.stringify(severityFormatter),
    });
    // A 200 says the property was taken, not that THIS formatter is the one
    // the operator will be looking at. An absent, emptied or rewritten
    // CustomFormatter renders the default cell, and a default cell reported as
    // "the repository formatter did nothing" is a false verdict of exactly the
    // kind X1 exists to catch. So the stored formatter is read back and
    // compared -- it is what the measurement DEPENDS ON. What the cell then
    // LOOKS like stays the observation, and is not asserted.
    //
    // The WHOLE object, not the two expressions that pick the colour. X1 asks
    // four questions and one of them is what TEXT the cell shows, which is
    // `children[0].txtContent`; `elmType` decides whether there is a box to
    // colour at all. A comparison that covered only `class` and `style` would
    // let a dropped child produce a missing-text answer attributed to
    // MultiChoice, which is the same false verdict one level down.
    //
    // Deep-equal on the PARSED objects, so key order and whitespace are not
    // the test. If SharePoint normalises the formatter in some way that turns
    // out to be harmless, this row says NOT ESTABLISHED and prints what came
    // back -- enough to tighten the comparison knowingly on the next run,
    // rather than a MANUAL verdict about a formatter nobody compared.
    const formatterBack = formatted.ok
      ? await get(`${fieldPath(MULTI)}?$select=CustomFormatter`)
      : null;
    let storedFormatter = null;
    try {
      storedFormatter = JSON.parse(formatterBack?.d?.CustomFormatter || 'null');
    } catch (err) {
      storedFormatter = null;
    }
    const sameJson = (a, b) => {
      if (a === b) return true;
      if (a === null || b === null || typeof a !== 'object' || typeof b !== 'object') return false;
      if (Array.isArray(a) !== Array.isArray(b)) return false;
      const [ka, kb] = [Object.keys(a), Object.keys(b)];
      return ka.length === kb.length && ka.every((k) => sameJson(a[k], b[k]));
    };
    const formatterHeld = sameJson(storedFormatter, severityFormatter);
    // Gated on the column actually being ON the view the operator is sent to.
    // Run 2 answered X1 from a view with no Evt column in it, which is not a
    // weaker answer than the real one -- it is a different question. A
    // formatter write that succeeds over an invisible column establishes
    // nothing about rendering.
    record(
      'X1',
      'the severity formatter this repo generates, on an array (manual: look)',
      formatted.ok && formatterHeld && multiOnDefaultView.ok
        ? 'MANUAL'
        : (formatted.ok ? 'NOT ESTABLISHED' : 'WRITE REFUSED'),
      !formatted.ok
        ? `HTTP ${formatted.status}: ${formatted.error}`
        : !formatterHeld
          ? `the MERGE was accepted (HTTP ${formatted.status}) but the formatter this row is about is NOT the `
            + `one now on the column: readback ${formatterBack?.ok
              ? show(formatterBack.d?.CustomFormatter)
              : `FAILED HTTP ${formatterBack?.status} ${formatterBack?.error}`}. `
            + `wrote ${show(JSON.stringify(severityFormatter))}. `
            + 'Looking at the cell would report how SOME other formatter (or none) renders, so no rendering '
            + 'answer is established by this run. If the difference turns out to be a harmless '
            + 'normalisation, tighten the comparison to ignore that part and re-run; do not read a verdict '
            + 'off a formatter this run did not confirm.'
          : !multiOnDefaultView.ok
            ? `the formatter was stored and read back intact (HTTP ${formatted.status}), but ${MULTI} could not `
              + `be added to the default view (HTTP ${multiOnDefaultView.status} ${multiOnDefaultView.error}), `
              + 'so there is no cell to look at. Add the column to the view by hand and re-read this row, or '
              + 'fix the failure and re-run; do NOT report a rendering answer from a view that does not show '
              + 'the column.'
            : `OPEN ${window.location.origin}${listDefaultUrl || `${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`} `
          + `and look at the ${MULTI} column. Report FOUR things: (a) does R1 {View} get a GREEN pill; `
          + '(b) does R2 {View,Edit} get any pill at all; (c) what TEXT does each cell show, whether both members, '
          + 'one member, or something like "View,Edit" run together; and (d) is the cell background PLAIN, '
          + 'or filled a flat grey. (d) separates the two ways this can fail and they need different '
          + 'answers: a plain cell means the formatter matched nothing and rendered nothing, while a grey '
          + 'fill means it matched a neutral default and rendered a wrong answer confidently, which is worse '
          + 'because it looks like a verdict. Anything other than a green pill on R1 means the existing '
          + 'severity machinery cannot serve a multi-value column, and the specification needs a refusal '
          + 'rather than array-aware behaviour.',
    );

    // === Verdict ===========================================================
    console.table(results.map(({ id, question, observed, detail }) => ({ id, question, observed, detail })));
    const fixtureOk = results.find((r) => r.id === 'Q0')?.observed === 'BUILT';
    log(
      'VERDICT',
      `fixture=${fixtureOk ? 'ok' : 'FAILED'} `
      + `create=${results.find((r) => r.id === 'M1').observed} `
      + `write_shape=${winningShape ? winningShape.name : 'none'} `
      + `indexed=${results.find((r) => r.id === 'I1').observed} `
      + `unique=${results.find((r) => r.id === 'I2').observed} `
      + `validation=${results.find((r) => r.id === 'V1').observed} `
      + `calculated=${results.find((r) => r.id === 'F1').observed}`,
    );
    // The VERDICT lines are what gets pasted back, so a value here is read as
    // the finding whatever the table beside it says. `membershipWinner` is
    // chosen from whichever predicate returned the two View-bearing rows --
    // which an incomplete or mutated fixture can produce by accident -- so it
    // is only a membership answer while the fixture it was chosen from is
    // established. The C rows already say NOT ESTABLISHED individually; this
    // line was still naming a winner.
    log(
      'VERDICT',
      `caml_membership=${camlFixtureUsable
        ? (membershipWinner ? membershipWinner.label : 'NONE FOUND')
        : 'NOT ESTABLISHED (fixture failed - do not report this run)'} `
      + 'stored_view=<fill in after looking> formatter=<fill in after looking>',
    );
    if (!camlFixtureUsable) {
      log('ERROR', 'fixture=FAILED. The C rows assume four rows with known sets on a MultiChoice column, and R2 restored after M5, so their answers mean nothing from this run. Fix the fixture and re-run before reporting.');
    } else if (!fixtureOk) {
      log('ERROR', `fixture=FAILED on the single-value CONTROL field only. The C, M, V, F and X rows do not depend on it and stand; I1 and I1C are VOID. Fix '${SINGLE}' and re-run if the index question matters.`);
    }
    log('INFO', 'Paste both VERDICT lines back, with the two <fill in> values set after doing the manual steps.');
    return { results, winningShape: winningShape?.name || null, viewUrl, chainViewUrl };
  } finally {
    if (createdList && CLEANUP_AT_END) {
      const gone = await recycleOwnedList(PROBE_LIST, PROBE_DESCRIPTION);
      if (gone.ok) {
        log('INFO', `Recycled '${PROBE_LIST}'.`);
      } else {
        log('ERROR', `COULD NOT RECYCLE '${PROBE_LIST}' (${gone.error}). Recycle it by hand: ${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`);
      }
    } else if (createdList) {
      log('INFO', `Left '${PROBE_LIST}' in place for the manual steps (X1 and C8). Re-run with CLEANUP_AT_END = true to remove it.`);
    }
  }
})();
