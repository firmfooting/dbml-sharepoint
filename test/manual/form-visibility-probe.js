/**
 * FORM VISIBILITY PROBE.
 *
 * Setup measures Q1-Q5 and Q7 and retains one owned list. The catalogue
 * defines the Q6 Edit-columns before/action/after sequence and the required
 * New/Edit/Display evidence. Set RECHECK_ONLY=true only after that UI action.
 *
 * WHAT IT ASKS. Ids follow the grammar in `test/manual/SURFACES.md`:
 * `<surface>.<scope>.<question>`. The old mnemonic each one replaces is given
 * beside it, because the prose above and every run reported against this
 * probe quote the mnemonics.
 *
 *   form.new-form.setter-persists-without-update  (Q1)
 *   form.edit-form.independent-of-new-form        (Q2)
 *   form.new-form.setter-reshows-hidden           (Q3)
 *   form.new-form.setter-on-sealed-field          (Q4)
 *   form.new-form.setter-on-calculated-column     (Q5)
 *   form.panel.edit-columns-writes-attributes     (Q6)
 *   form.new-form.attribute-at-creation           (Q7)
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  // Deliberately NOT a site URL. The web is read from _spPageContextInfo and
  // printed back for you to check; you confirm by flipping this flag. That
  // gives the same "don't run it on the wrong site" protection as pasting a
  // URL, without ever putting a tenant address into a tracked file.
  // CONFIRMED identifies the intended site. ALLOW_WRITES is required for
  // setup or cleanup, while a RECHECK_ONLY run with cleanup off is read-only.
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const PROBE_RETRY_TRANSIENT = true;
  const PROBE_RETRY_ATTEMPTS = 5;
  const PROBE_LIST = 'zzz dbmlsp form visibility probe';
  // Named for its timing: this deletes the list AFTER the run. The shared
  // harness has a CLEANUP that deletes BEFORE one. Same word, opposite
  // moment, so they are kept distinct rather than merged by accident.
  const CLEANUP_AT_END = false;
  const RECHECK_ONLY = false;     // true = read current state only; no setup, no writes
  const PROBE_WRITES = !RECHECK_ONLY || CLEANUP_AT_END;
  // ------------------------------------------------------------------------

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
  expect('form.new-form.setter-persists-without-update', 'setshowinnewform(false) persists with no Update()');
  expect('form.edit-form.independent-of-new-form', 'new=false + edit=true can coexist');
  expect('form.new-form.setter-reshows-hidden', 'setshowinnewform(true) re-shows a hidden field');
  expect('form.new-form.setter-on-sealed-field', 'setters work on a Sealed field');
  expect('form.new-form.setter-on-calculated-column', 'setshowinnewform(false) on a calculated column');
  expect('form.panel.edit-columns-writes-attributes', 'the modern "Edit form columns" panel writes these attributes');
  expect('form.new-form.attribute-at-creation', "AddFieldAsXml with ShowInNewForm='FALSE' at creation");

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
  log('INFO', `probe revision 68d44fa4; core v2; results v1.`);
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
  const OWNERSHIP_DESCRIPTION = 'Throwaway list created by dbml-sharepoint form-visibility-probe.js. Safe to delete.';
  const fieldPath = (name) => `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;
  const listUrl = `${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`;

  // ShowInNewForm/ShowInEditForm/ShowInDisplayForm are NOT properties on
  // SP.Field. The CSOM type exposes only the three Set* methods, so no
  // $select can return them. SchemaXml is the only readable source of
  // truth, and an absent attribute means "shown".
  async function visibility(name) {
    const r = await get(`${fieldPath(name)}?$select=SchemaXml,Sealed`);
    if (!r.ok) return { ok: false, error: `HTTP ${r.status} ${r.error}` };
    const xml = String(r.d.SchemaXml || '');
    return {
      ok: true,
      xml,
      sealed: /Sealed="TRUE"/i.test(xml),
      newForm: !/ShowInNewForm="FALSE"/i.test(xml),
      editForm: !/ShowInEditForm="FALSE"/i.test(xml),
      displayForm: !/ShowInDisplayForm="FALSE"/i.test(xml),
    };
  }
  const shape = (v) => `new=${v.newForm ? 'shown' : 'HIDDEN'} edit=${v.editForm ? 'shown' : 'HIDDEN'} display=${v.displayForm ? 'shown' : 'HIDDEN'}`;

  async function setVis(name, method, value) {
    // Documented REST convention: the URI mimics the CSOM signature and
    // endpoint names are case-insensitive.
    return post(`${fieldPath(name)}/${method}(${value})`);
  }
  async function addTextField(title) {
    return post(`${listPath}/fields`, {
      __metadata: { type: 'SP.Field' }, FieldTypeKind: 2, Title: title,
    });
  }
  async function addFieldAsXml(schemaXml) {
    return post(`${listPath}/fields/createfieldasxml`, {
      parameters: {
        __metadata: { type: 'SP.XmlSchemaFieldCreationInformation' },
        SchemaXml: schemaXml,
        // AddFieldInternalNameHint (8) | AddToDefaultContentType (1). The
        // content-type bit matters: a field in no content type never
        // reaches a form at all, which would confound Q5 and Q7.
        Options: 9,
      },
    });
  }

  const FIELDS = {
    persist: 'ProbePersist',      // Q1 does a setter stick without Update()?
    split:   'ProbeSplit',        // Q2 are new and edit independent?
    reshow:  'ProbeReshow',       // Q3 does setter(true) undo a hide?
    sealed:  'ProbeSealed',       // Q4 does Sealed block the setters?
    calc:    'ProbeCalc',         // Q5 what happens on a calculated column?
    declared:'ProbeDeclared',     // Q7 does creation-time SchemaXml work?
  };

  // === RECHECK_ONLY: report current state, change nothing ===
  if (RECHECK_ONLY) {
    log('INFO', 'RECHECK_ONLY: reading current visibility, making no changes.');
    const exists = await get(`${listPath}?$select=Title,Description`);
    if (!exists.ok) {
      log('ERROR', `Probe list '${PROBE_LIST}' not found. Run once with RECHECK_ONLY = false first.`);
      return { aborted: 'no-probe-list' };
    }
    if (exists.d.Description !== OWNERSHIP_DESCRIPTION) {
      log('ERROR', `A same-title list exists without the probe ownership marker; refusing to modify it.`);
      return { aborted: 'foreign-same-title-list' };
    }
    const q6Readback = [];
    for (const [key, name] of Object.entries(FIELDS)) {
      const v = await visibility(name);
      q6Readback.push({ key, name, visibility: v });
    }
    const q6Readable = q6Readback.every(({ visibility: v }) => v.ok);
    record('form.panel.edit-columns-writes-attributes',
      'the modern "Edit form columns" panel writes these attributes',
      q6Readable ? 'MANUAL: capture New/Edit/Display after states' : 'NOT ESTABLISHED',
      q6Readback.map(({ name, visibility: v }) => `${name}: ${v.ok ? shape(v) : v.error}`).join('; '),
    );
    console.table(results);
    if (CLEANUP_AT_END) {
      const recycled = await recycleOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION);
      log(recycled.ok ? 'INFO' : 'ERROR', recycled.ok
        ? `Probe list '${PROBE_LIST}' recycled.`
        : `CLEANUP_AT_END FAILED (${recycled.error}). Recycle it by hand: ${listUrl}`);
    } else {
      log('WARN', `CLEANUP_AT_END is false, so '${PROBE_LIST}' is still on the site: ${listUrl}`);
    }
    log('DONE', 'Recheck complete. Compare against the values from the probe run.');
    return { results };
  }

  // === Setup ===
  log('INFO', `Creating probe list '${PROBE_LIST}'.`);
  const existing = await get(`${listPath}?$select=Title,Description`);
  if (existing.ok && existing.d.Description !== OWNERSHIP_DESCRIPTION) {
    log('ERROR', 'A same-title list exists without the probe ownership marker; refusing to modify it.');
    return { aborted: 'foreign-same-title-list' };
  }
  if (!existing.ok && existing.status !== 404) {
    log('ERROR', `Could not establish whether the probe list exists: HTTP ${existing.status} ${existing.error}`);
    return { aborted: 'fixture-discovery-failed' };
  }
  if (existing.ok) {
    log('INFO', 'Owned probe list already exists; recycling it before a clean run.');
    const recycled = await recycleOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION);
    if (!recycled.ok) {
      log('ERROR', `Could not recycle the existing probe list: ${recycled.error}`);
      return { aborted: 'stale-probe-list' };
    }
  }
  const created = await post('web/lists', {
    __metadata: { type: 'SP.List' },
    BaseTemplate: 100,
    Title: PROBE_LIST,
    Description: OWNERSHIP_DESCRIPTION,
  });
  if (!created.ok) {
    log('ERROR', `Could not create the probe list: HTTP ${created.status} ${created.error}`);
    return { aborted: 'list-create-failed' };
  }

  for (const name of [FIELDS.persist, FIELDS.split, FIELDS.reshow, FIELDS.sealed]) {
    const r = await addTextField(name);
    if (!r.ok) log('WARN', `Could not create ${name}: HTTP ${r.status} ${r.error}`);
  }
  const calcAdded = await addFieldAsXml(
    `<Field Type='Calculated' DisplayName='${FIELDS.calc}' Name='${FIELDS.calc}' ResultType='Number' ReadOnly='TRUE'><Formula>=1+1</Formula></Field>`,
  );
  if (!calcAdded.ok) log('WARN', `Could not create ${FIELDS.calc}: HTTP ${calcAdded.status} ${calcAdded.error}`);
  const declaredAdded = await addFieldAsXml(
    `<Field Type='Text' DisplayName='${FIELDS.declared}' Name='${FIELDS.declared}' ShowInNewForm='FALSE' ShowInEditForm='TRUE'/>`,
  );
  if (!declaredAdded.ok) log('WARN', `Could not create ${FIELDS.declared}: HTTP ${declaredAdded.status} ${declaredAdded.error}`);

  try {
    // --- setter-persists-without-update (Q1): does a setter persist with no following Update()? ---
    // Undocumented by Microsoft. Over REST each call is its own request, so
    // there is no way to batch an Update() with it. If this reads back
    // FALSE, the single POST is self-sufficient.
    const before1 = await visibility(FIELDS.persist);
    const set1 = await setVis(FIELDS.persist, 'setshowinnewform', false);
    const after1 = await visibility(FIELDS.persist);
    record('form.new-form.setter-persists-without-update', 'setshowinnewform(false) persists with no Update()',
      !set1.ok ? `CALL FAILED (HTTP ${set1.status})`
        : after1.ok && !after1.newForm ? 'YES: read back as hidden' : 'NO: read back still shown',
      `${set1.ok ? 'POST ok' : set1.error}; before ${before1.ok ? shape(before1) : '?'}; after ${after1.ok ? shape(after1) : '?'}`);

    // --- independent-of-new-form (Q2): are new and edit independent? ------
    // This is the whole point of the proposed form_visibility section:
    // hidden at creation, still editable afterwards.
    const setN = await setVis(FIELDS.split, 'setshowinnewform', false);
    const setE = await setVis(FIELDS.split, 'setshowineditform', true);
    const after2 = await visibility(FIELDS.split);
    record('form.edit-form.independent-of-new-form', 'new=false + edit=true can coexist',
      !(setN.ok && setE.ok) ? `CALL FAILED (new ${setN.status}, edit ${setE.status})`
        : after2.ok && !after2.newForm && after2.editForm ? 'YES: independent' : 'NO: coupled or overwritten',
      after2.ok ? shape(after2) : after2.error);

    // --- setter-reshows-hidden (Q3): does setter(true) undo a hide? -------
    // deploy.js only ever calls setter(false) today, so the "re-show" path
    // is entirely unexercised. Reconciliation can only become two-way if
    // this works.
    await setVis(FIELDS.reshow, 'setshowinnewform', false);
    const hidden3 = await visibility(FIELDS.reshow);
    const set3 = await setVis(FIELDS.reshow, 'setshowinnewform', true);
    const after3 = await visibility(FIELDS.reshow);
    record('form.new-form.setter-reshows-hidden', 'setshowinnewform(true) re-shows a hidden field',
      !set3.ok ? `CALL FAILED (HTTP ${set3.status})`
        : after3.ok && after3.newForm ? 'YES: shown again' : 'NO: still hidden',
      `hidden first: ${hidden3.ok ? shape(hidden3) : '?'}; after re-show: ${after3.ok ? shape(after3) : '?'} ${set3.ok ? '' : set3.error}`);

    // --- setter-on-sealed-field (Q4): does Sealed block the setters? ------
    // Decides whether a visibility change needs the deploy's unseal/reseal
    // dance, or can be applied directly to a sealed column.
    const seal = await post(fieldPath(FIELDS.sealed), { __metadata: { type: 'SP.Field' }, Sealed: true },
      { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    const sealedState = await visibility(FIELDS.sealed);
    const set4 = await setVis(FIELDS.sealed, 'setshowinnewform', false);
    const after4 = await visibility(FIELDS.sealed);
    record('form.new-form.setter-on-sealed-field', 'setters work on a Sealed field',
      !seal.ok ? `INCONCLUSIVE: could not seal (HTTP ${seal.status})`
        : !sealedState.sealed ? 'INCONCLUSIVE: Sealed did not stick'
          : set4.ok && after4.ok && !after4.newForm ? 'YES: sealing does not block them'
            : 'NO: blocked while sealed',
      `sealed=${sealedState.sealed}; POST ${set4.ok ? 'ok' : `HTTP ${set4.status} ${set4.error}`}; after ${after4.ok ? shape(after4) : '?'}`);

    // --- setter-on-calculated-column (Q5): what happens on a calculated column? ---
    // The retirement design carves calculated columns OUT of the hide fold
    // because our own validator rejects them. This establishes whether
    // SharePoint itself would have objected.
    const set5 = await setVis(FIELDS.calc, 'setshowinnewform', false);
    const after5 = await visibility(FIELDS.calc);
    record('form.new-form.setter-on-calculated-column', 'setshowinnewform(false) on a calculated column',
      !calcAdded.ok ? 'INCONCLUSIVE: calculated field was not created'
        : !set5.ok ? `REJECTED (HTTP ${set5.status})`
          : after5.ok && !after5.newForm ? 'ACCEPTED and stuck' : 'ACCEPTED but no effect',
      set5.ok ? (after5.ok ? shape(after5) : '?') : set5.error);

    // --- edit-columns-writes-attributes (Q6): manual UI step -------------
    record('form.panel.edit-columns-writes-attributes', 'the modern "Edit form columns" panel writes these attributes',
      'MANUAL: capture panel before/action, then recheck',
      'capture the Edit form columns panel before and immediately before save; after saving, re-run with RECHECK_ONLY=true and capture the New, Edit and Display forms');

    // --- attribute-at-creation (Q7): creation-time SchemaXml ---------------
    // The only form Microsoft actually shows a sample for.
    const after7 = await visibility(FIELDS.declared);
    record('form.new-form.attribute-at-creation', "AddFieldAsXml with ShowInNewForm='FALSE' at creation",
      !declaredAdded.ok ? `FIELD CREATE FAILED (HTTP ${declaredAdded.status})`
        : after7.ok && !after7.newForm ? 'YES: honoured at creation' : 'NO: attribute not retained',
      after7.ok ? shape(after7) : after7.error);

    console.table(results.map(({ id, question, observed, detail }) => ({ id, question, observed, detail })));
  } finally {
    if (CLEANUP_AT_END) {
      const recycled = await recycleOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION);
      if (recycled.ok) {
        log('INFO', `Probe list '${PROBE_LIST}' recycled.`);
      } else {
        log('ERROR', `CLEANUP_AT_END FAILED (${recycled.error}). Recycle it by hand: ${listUrl}`);
      }
    } else {
      log('WARN', `CLEANUP_AT_END is false, so '${PROBE_LIST}' is still on the site: ${listUrl}`);
      log('INFO', 'Manual step for Q6: open the list -> Edit form -> Edit columns, toggle a Probe* column off, then re-run this script with RECHECK_ONLY = true.');
      log('INFO', `Also check whether ${FIELDS.sealed} (Sealed) can be toggled in that panel at all, which answers whether sealing protects form visibility from UI drift.`);
    }
  }

  log('DONE', 'Probe complete. Every row is an OBSERVATION, not a pass/fail.');
  return { results };
})();
