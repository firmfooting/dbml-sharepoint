/**
 * dbml-sharepoint FORM VISIBILITY PROBE (creates and deletes its own list).
 *
 * Answers the questions Microsoft's documentation does not, before
 * `form_visibility:` is built into the tool. SetShowInNewForm /
 * SetShowInEditForm / SetShowInDisplayForm are bare stubs on Learn with no
 * Remarks, no examples and no statement about persistence, so every
 * assumption below has to be established empirically per tenant.
 *
 * WHAT IT WRITES: one list, named by PROBE_LIST below, created at start and
 * deleted at end. It never reads, writes or enumerates any other list. If
 * cleanup fails it says so loudly and prints the URL to delete by hand.
 *
 * HOW TO RUN
 *   1. Paste it once: it prints the web and stops. Set CONFIRMED = true.
 *   2. Open that site's classic settings page — /_layouts/15/settings.aspx —
 *      signed in as a Site Owner. The site guard needs _spPageContextInfo.
 *   3. F12 -> Console -> type `allow pasting` if the browser objects ->
 *      paste this whole file -> Enter.
 *   4. Read the RESULTS table. Every row prints OBSERVED, not expected:
 *      this is a probe, not a test suite. Nothing here asserts a verdict.
 *
 * THE MANUAL STEP (Q6 cannot be done from script)
 *   Set CLEANUP = false, run once, then in the list UI open
 *   "Edit form" -> "Edit columns" and toggle a probe column off. Then set
 *   RECHECK_ONLY = true and re-run: it reports whether the UI wrote
 *   ShowInNewForm/ShowInEditForm, and whether Sealed stopped it.
 *   Set CLEANUP = true on the final run to remove the list.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  // Deliberately NOT a site URL. The web is read from _spPageContextInfo and
  // printed back for you to check; you confirm by flipping this flag. That
  // gives the same "don't run it on the wrong site" protection as pasting a
  // URL, without ever putting a tenant address into a tracked file.
  // One gate, not two: CONFIRMED returns before anything below runs, so a
  // second ALLOW_WRITES flag here would gate nothing and imply a protection
  // that does not exist.
  const CONFIRMED = false;
  const PROBE_LIST = 'zzz dbmlsp form visibility probe';
  const CLEANUP = false;           // false keeps the list for the manual UI step
  const RECHECK_ONLY = true;     // true = read current state only; no setup, no writes
  // ------------------------------------------------------------------------

  const log = (level, msg) => console.log(`[SP-PROBE] [${level}] ${msg}`);
  const results = [];
  const record = (id, question, observed, detail) => {
    results.push({ id, question, observed, detail: detail || '' });
    log('INFO', `${id}: ${observed}${detail ? ` — ${detail}` : ''}`);
  };

  // === Preflight: confirm the site ===
  // SP REST '/_api/...' is routed by the path prefix BEFORE '_api'. A bare
  // '/_api/web/...' targets the tenant root web — NOT the sub-site you are
  // viewing. Prefix every call with the current web's server-relative URL.
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
  const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
  // SP getbytitle/getbyname take a single-quoted OData literal, where an
  // embedded apostrophe must be DOUBLED; encodeURIComponent does not do it.
  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  log('INFO', `Running as ${_spPageContextInfo.userLoginName || '(unknown)'} on web '${WEB || '(root)'}'.`);

  // === Transport ===
  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
  const spError = (text) => {
    try {
      return JSON.parse(text)?.error?.message?.value || String(text).slice(0, 300);
    } catch {
      return String(text).slice(0, 300);
    }
  };
  async function fetchWithRetry(url, opts, attempts = 5) {
    for (let i = 0; ; i++) {
      const r = await fetch(url, opts);
      if ((r.status === 429 || r.status === 503) && i < attempts) {
        const ra = Number(r.headers.get('Retry-After')) || Math.min(2 ** i, 30);
        log('INFO', `Throttled (HTTP ${r.status}); retry ${i + 1}/${attempts} in ${ra}s.`);
        await sleep(ra * 1000);
        continue;
      }
      return r;
    }
  }
  let cachedDigest = null;
  let digestExpiresAt = 0;
  async function getDigest() {
    if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;
    const r = await fetchWithRetry(apiUrl('contextinfo'), {
      method: 'POST', headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const info = (await r.json()).d.GetContextWebInformation;
    cachedDigest = info.FormDigestValue;
    digestExpiresAt = Date.now() + Math.max((Number(info.FormDigestTimeoutSeconds) || 1800) - 60, 60) * 1000;
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
    const r = await fetchWithRetry(apiUrl(suffix), {
      method: 'POST',
      headers: spHeaders(digest, extraHeaders || {}),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = r.ok ? '' : await r.text();
    return { ok: r.ok, status: r.status, error: r.ok ? null : spError(text) };
  }
  async function get(suffix) {
    const r = await fetchWithRetry(apiUrl(suffix), { headers: { 'Accept': 'application/json;odata=verbose' } });
    if (!r.ok) return { ok: false, status: r.status, error: spError(await r.text()) };
    const j = await r.json();
    return { ok: true, d: (j && j.d !== undefined) ? j.d : j };
  }

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const fieldPath = (name) => `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;
  const listUrl = `${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`;

  // ShowInNewForm/ShowInEditForm/ShowInDisplayForm are NOT properties on
  // SP.Field — the CSOM type exposes only the three Set* methods, so no
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
    log('INFO', 'RECHECK_ONLY — reading current visibility, making no changes.');
    const exists = await get(`${listPath}?$select=Title`);
    if (!exists.ok) {
      log('ERROR', `Probe list '${PROBE_LIST}' not found. Run once with CLEANUP = false first.`);
      return { aborted: 'no-probe-list' };
    }
    for (const [key, name] of Object.entries(FIELDS)) {
      const v = await visibility(name);
      record(`RECHECK.${key}`, name, v.ok ? shape(v) : 'READ FAILED', v.ok ? (v.sealed ? 'sealed' : 'not sealed') : v.error);
    }
    console.table(results);
    if (CLEANUP) {
      const del = await post(listPath, undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
      log(del.ok ? 'INFO' : 'ERROR', del.ok
        ? `Probe list '${PROBE_LIST}' deleted.`
        : `CLEANUP FAILED (HTTP ${del.status} ${del.error}). Delete it by hand: ${listUrl}`);
    } else {
      log('WARN', `CLEANUP is false — '${PROBE_LIST}' is still on the site: ${listUrl}`);
    }
    log('DONE', 'Recheck complete. Compare against the values from the probe run.');
    return { results };
  }

  // === Setup ===
  log('INFO', `Creating probe list '${PROBE_LIST}'.`);
  const existing = await get(`${listPath}?$select=Title`);
  if (existing.ok) {
    log('INFO', 'Probe list already exists; deleting it before a clean run.');
    const del = await post(listPath, undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
    if (!del.ok) {
      log('ERROR', `Could not delete the existing probe list: HTTP ${del.status} ${del.error}`);
      return { aborted: 'stale-probe-list' };
    }
  }
  const created = await post('web/lists', {
    __metadata: { type: 'SP.List' },
    BaseTemplate: 100,
    Title: PROBE_LIST,
    Description: 'Throwaway list created by dbml-sharepoint form-visibility-probe.js. Safe to delete.',
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
    // --- Q1: does a setter persist with no following Update()? ------------
    // Undocumented by Microsoft. Over REST each call is its own request, so
    // there is no way to batch an Update() with it — if this reads back
    // FALSE, the single POST is self-sufficient.
    const before1 = await visibility(FIELDS.persist);
    const set1 = await setVis(FIELDS.persist, 'setshowinnewform', false);
    const after1 = await visibility(FIELDS.persist);
    record('Q1', 'setshowinnewform(false) persists with no Update()',
      !set1.ok ? `CALL FAILED (HTTP ${set1.status})`
        : after1.ok && !after1.newForm ? 'YES — read back as hidden' : 'NO — read back still shown',
      `${set1.ok ? 'POST ok' : set1.error}; before ${before1.ok ? shape(before1) : '?'}; after ${after1.ok ? shape(after1) : '?'}`);

    // --- Q2: are new and edit independent? --------------------------------
    // This is the whole point of the proposed form_visibility section:
    // hidden at creation, still editable afterwards.
    const setN = await setVis(FIELDS.split, 'setshowinnewform', false);
    const setE = await setVis(FIELDS.split, 'setshowineditform', true);
    const after2 = await visibility(FIELDS.split);
    record('Q2', 'new=false + edit=true can coexist',
      !(setN.ok && setE.ok) ? `CALL FAILED (new ${setN.status}, edit ${setE.status})`
        : after2.ok && !after2.newForm && after2.editForm ? 'YES — independent' : 'NO — coupled or overwritten',
      after2.ok ? shape(after2) : after2.error);

    // --- Q3: does setter(true) undo a hide? -------------------------------
    // deploy.js only ever calls setter(false) today, so the "re-show" path
    // is entirely unexercised. Reconciliation can only become two-way if
    // this works.
    await setVis(FIELDS.reshow, 'setshowinnewform', false);
    const hidden3 = await visibility(FIELDS.reshow);
    const set3 = await setVis(FIELDS.reshow, 'setshowinnewform', true);
    const after3 = await visibility(FIELDS.reshow);
    record('Q3', 'setshowinnewform(true) re-shows a hidden field',
      !set3.ok ? `CALL FAILED (HTTP ${set3.status})`
        : after3.ok && after3.newForm ? 'YES — shown again' : 'NO — still hidden',
      `hidden first: ${hidden3.ok ? shape(hidden3) : '?'}; after re-show: ${after3.ok ? shape(after3) : '?'} ${set3.ok ? '' : set3.error}`);

    // --- Q4: does Sealed block the setters? -------------------------------
    // Decides whether a visibility change needs the deploy's unseal/reseal
    // dance, or can be applied directly to a sealed column.
    const seal = await post(fieldPath(FIELDS.sealed), { __metadata: { type: 'SP.Field' }, Sealed: true },
      { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    const sealedState = await visibility(FIELDS.sealed);
    const set4 = await setVis(FIELDS.sealed, 'setshowinnewform', false);
    const after4 = await visibility(FIELDS.sealed);
    record('Q4', 'setters work on a Sealed field',
      !seal.ok ? `INCONCLUSIVE — could not seal (HTTP ${seal.status})`
        : !sealedState.sealed ? 'INCONCLUSIVE — Sealed did not stick'
          : set4.ok && after4.ok && !after4.newForm ? 'YES — sealing does not block them'
            : 'NO — blocked while sealed',
      `sealed=${sealedState.sealed}; POST ${set4.ok ? 'ok' : `HTTP ${set4.status} ${set4.error}`}; after ${after4.ok ? shape(after4) : '?'}`);

    // --- Q5: what happens on a calculated column? -------------------------
    // The retirement design carves calculated columns OUT of the hide fold
    // because our own validator rejects them. This establishes whether
    // SharePoint itself would have objected.
    const set5 = await setVis(FIELDS.calc, 'setshowinnewform', false);
    const after5 = await visibility(FIELDS.calc);
    record('Q5', 'setshowinnewform(false) on a calculated column',
      !calcAdded.ok ? 'INCONCLUSIVE — calculated field was not created'
        : !set5.ok ? `REJECTED (HTTP ${set5.status})`
          : after5.ok && !after5.newForm ? 'ACCEPTED and stuck' : 'ACCEPTED but no effect',
      set5.ok ? (after5.ok ? shape(after5) : '?') : set5.error);

    // --- Q6: manual UI step ----------------------------------------------
    record('Q6', 'the modern "Edit form columns" panel writes these attributes',
      'MANUAL — see instructions below', 'cannot be exercised from script');

    // --- Q7: creation-time SchemaXml ---------------------------------------
    // The only form Microsoft actually shows a sample for.
    const after7 = await visibility(FIELDS.declared);
    record('Q7', "AddFieldAsXml with ShowInNewForm='FALSE' at creation",
      !declaredAdded.ok ? `FIELD CREATE FAILED (HTTP ${declaredAdded.status})`
        : after7.ok && !after7.newForm ? 'YES — honoured at creation' : 'NO — attribute not retained',
      after7.ok ? shape(after7) : after7.error);

    console.table(results.map(({ id, question, observed, detail }) => ({ id, question, observed, detail })));
  } finally {
    if (CLEANUP) {
      const del = await post(listPath, undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
      if (del.ok) {
        log('INFO', `Probe list '${PROBE_LIST}' deleted.`);
      } else {
        log('ERROR', `CLEANUP FAILED (HTTP ${del.status} ${del.error}). Delete it by hand: ${listUrl}`);
      }
    } else {
      log('WARN', `CLEANUP is false — '${PROBE_LIST}' is still on the site: ${listUrl}`);
      log('INFO', 'Manual step for Q6: open the list -> Edit form -> Edit columns, toggle a Probe* column off, then re-run this script with RECHECK_ONLY = true.');
      log('INFO', `Also check whether ${FIELDS.sealed} (Sealed) can be toggled in that panel at all — that answers whether sealing protects form visibility from UI drift.`);
    }
  }

  log('DONE', 'Probe complete. Every row is an OBSERVATION, not a pass/fail.');
  return { results };
})();
