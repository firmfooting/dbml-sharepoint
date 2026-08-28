/**
 * VIEW AGGREGATIONS PROBE.
 *
 * Creates one owned list and settles storage/readback of view aggregations.
 * The catalogue defines the rendered totals state required for Q4-Q6.
 * Historical runs belong in evidence rather than this executable source.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const PROBE_RETRY_TRANSIENT = true;
  const PROBE_RETRY_ATTEMPTS = 5;
  const PROBE_LIST = 'zzz dbmlsp view aggregations probe';
  const CLEANUP_AT_END = false;
  // What the totals row should show once one of the attempts lands.
  const AGG_FIELD = 'Amount';
  // Uppercase: the classic view renderer matches aggregation types by exact
  // case, and a capitalised 'Sum' stored fine but rendered 'Count= undefined'
  // (live finding 2026-08-27). 'AVG' already matched.
  const AGG_TYPE = 'SUM';
  // ------------------------------------------------------------------------

  // Shared result registry v1. Register findings before any network work.
  //
  // STATE carries the coarse answer alongside the prose, from the five-value
  // vocabulary in test/manual/SURFACES.md: settled, open, awaiting-capture,
  // void, needs-human. An explicit state passed to record() always wins; the
  // classifier is the default for the rows nobody has ruled on yet.
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT'];
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
  expect('Q0', 'two rows actually seeded, so the manual check has something to total');
  expect('Q1', 'REST PATCH of SP.View Aggregations/AggregationsStatus is accepted');
  expect('Q2', 'GetViewXml/SetViewXml carries an <Aggregations> block');
  expect('Q3', 'the written property reads back unchanged');
  expect('Q4', 'a totals row actually RENDERS (manual: open the view URL and look)');
  expect('Q5', 'Aggregations binds by INTERNAL name, not display title (manual: look)');
  expect('Q6', 'two totalled columns both render, in declaration order (manual: look)');

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
  log('INFO', `probe revision a6dfa267; core v2; results v1.`);
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
  // Shared by Q3 and the Q4-Q6 outcome gate. SharePoint stores the aggregation
  // XML with a space before self-closing `/>` and quote normalisation, the same
  // storage form that bit the threshold probe's ViewQuery readback.
  const normalizeAgg = (xml) => String(xml || '')
    .replace(/\s+/g, ' ').replace(/"/g, "'").replace(/> </g, '><').replace(/ \/>/g, '/>').trim();
  const aggregationManualOutcome = (controls) => {
    const seedsHeld = Array.isArray(controls.seedValues)
      && controls.seedValues.length === 2
      && controls.seedValues[0] === 1
      && controls.seedValues[1] === 3;
    const viewFieldsHeld = Array.isArray(controls.viewFieldNames)
      && Array.isArray(controls.expectedViewFields)
      && controls.expectedViewFields.every((name) => controls.viewFieldNames.includes(name));
    const renamedTitleHeld = controls.fieldTitle === controls.expectedFieldTitle;
    const ready = controls.setupReady
      && controls.writeOk
      && normalizeAgg(controls.aggregationXml) === normalizeAgg(controls.expectedXml)
      && controls.aggregationStatus === 'On'
      && seedsHeld
      && viewFieldsHeld
      && renamedTitleHeld;
    return ready ? 'MANUAL' : 'NOT ESTABLISHED';
  };

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint aggregations probe. Safe to delete.';
  let createdList = false;
  let viewId = null;
  let viewUrl = null;

  try {
    const prepared = await prepareOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION, CLEANUP_AT_END);
    if (!prepared.ok) {
      record('Q0', 'setup', 'ABORTED', prepared.error);
      throw new Error('fixture ownership or reset failed');
    }
    if (prepared.existing) {
      record(
        'Q0',
        'setup',
        'ABORTED',
        `The owned fixture '${PROBE_LIST}' is retained for visible evidence. Re-run with CLEANUP_AT_END=true to recycle it before a fresh run.`,
      );
      console.table(results);
      return { seeded: 0, mechanism: 'none', readback: 'not-run', viewUrl: null, results };
    }

    // === Setup: a list, a number column, two rows, and a view =============
    const made = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: PROBE_LIST,
      Description: OWNERSHIP_DESCRIPTION,
      // Classic experience, so the retained fixture renders server-side and the
      // visible findings (Q4-Q6) are capturable by the harness's capture-visible
      // step. The modern list web part does not render under Camofox.
      ListExperienceOptions: 2,
    });
    if (!made.ok) {
      record('Q1', 'setup', 'ABORTED', `could not create the probe list: HTTP ${made.status} ${made.error}`);
      throw new Error('setup failed');
    }
    createdList = true;
    log('INFO', `Created '${PROBE_LIST}'.`);

    const field = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldNumber' },
      FieldTypeKind: 9,
      Title: AGG_FIELD,
    });
    if (!field.ok) {
      record('Q1', 'setup', 'ABORTED', `could not add ${AGG_FIELD}: HTTP ${field.status} ${field.error}`);
      throw new Error('setup failed');
    }
    // Seed, and CHECK. The first version of this probe fired these two
    // posts, ignored their responses and logged "Seeded two rows"; both had
    // returned HTTP 400 and the list was empty for the manual step that
    // followed. A probe that reports an unchecked claim is worse than no
    // probe, so the seeded count is now a recorded question of its own and
    // is read back from the list rather than assumed.
    const itemType = await entityTypeFor(PROBE_LIST);
    const seedErrors = [];
    for (const amount of [10, 32]) {
      const seeded = await post(`${listPath}/items`, {
        __metadata: { type: itemType },
        Title: `probe ${amount}`,
        [AGG_FIELD]: amount,
      });
      if (!seeded.ok) seedErrors.push(`${amount}: HTTP ${seeded.status} ${seeded.error}`);
    }
    const counted = await get(`${listPath}/ItemCount`);
    const rowCount = counted.ok ? Number(counted.d.ItemCount) : NaN;
    record(
      'Q0',
      'two rows actually seeded, so the manual check has something to total',
      rowCount === 2 ? 'SEEDED' : 'FAILED',
      seedErrors.length
        ? `${seedErrors.join('; ')} (ItemCount=${rowCount})`
        : `ItemCount=${rowCount}; ${AGG_TYPE} of ${AGG_FIELD} should be 42`,
    );
    if (rowCount !== 2) {
      log('ERROR', 'The list is not correctly seeded. Q4 cannot be answered by looking at it. Fix this before trusting the verdict.');
    }

    const view = await post(`${listPath}/views`, {
      __metadata: { type: 'SP.View' },
      Title: 'Probe totals',
      ViewQuery: '',
      RowLimit: 30,
    });
    if (!view.ok) {
      record('Q1', 'setup', 'ABORTED', `could not create the view: HTTP ${view.status} ${view.error}`);
      throw new Error('setup failed');
    }
    const views = await get(`${listPath}/views?$select=Id,Title,ServerRelativeUrl,Aggregations,AggregationsStatus`);
    const probeView = (views.d?.results || []).find((v) => v.Title === 'Probe totals');
    viewId = probeView?.Id;
    viewUrl = probeView?.ServerRelativeUrl;
    // The Amount column must be IN the view or there is nothing to total.
    const amountOnView = await post(
      `${listPath}/views('${viewId}')/viewfields/addviewfield('${odataName(AGG_FIELD)}')`,
    );
    const initialViewFields = await get(`${listPath}/views('${viewId}')/viewfields`);
    const initialViewFieldNames = initialViewFields.ok
      && Array.isArray(initialViewFields.d?.Items?.results)
      ? initialViewFields.d.Items.results
      : null;
    const amountMembershipHeld = Array.isArray(initialViewFieldNames)
      && initialViewFieldNames.includes(AGG_FIELD);
    log('INFO', `View ready at ${window.location.origin}${viewUrl}`);

    const AGG_XML = `<FieldRef Name="${AGG_FIELD}" Type="${AGG_TYPE}"/>`;

    // === Q1: REST PATCH of the SP.View properties ========================
    const patched = await post(
      `${listPath}/views('${viewId}')`,
      { __metadata: { type: 'SP.View' }, Aggregations: AGG_XML, AggregationsStatus: 'On' },
      { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
    );
    record(
      'Q1',
      'REST PATCH of SP.View Aggregations/AggregationsStatus is accepted',
      patched.ok ? 'ACCEPTED' : 'REFUSED',
      patched.ok ? `HTTP ${patched.status}` : `HTTP ${patched.status} (${patched.error})`,
    );

    // === Q2: the SetViewXml path, guarded exactly as widths are ==========
    // Only attempted if the PATCH was refused: if PATCH works it is the
    // simpler mechanism and the one the deployer should use.
    let xmlWorked = false;
    if (!patched.ok) {
      const current = await post(`${listPath}/views('${viewId}')/renderashtml`);
      const xmlGet = await get(`${listPath}/views('${viewId}')?$select=ListViewXml`);
      const currentXml = xmlGet.d?.ListViewXml || '';
      if (!currentXml) {
        record('Q2', 'GetViewXml/SetViewXml carries an <Aggregations> block', 'NOT ESTABLISHED', 'could not read ListViewXml');
      } else {
        const block = `<Aggregations Value="On">${AGG_XML}</Aggregations>`;
        const strip = (xml) => xml.replace(/<Aggregations[\s\S]*?<\/Aggregations>/, '');
        const nextXml = currentXml.includes('<Aggregations')
          ? currentXml.replace(/<Aggregations[\s\S]*?<\/Aggregations>/, block)
          : currentXml.replace('</View>', `${block}</View>`);
        // Same guard the deployer's width splice uses: refuse if anything
        // outside the spliced region would change.
        if (strip(nextXml) !== strip(currentXml)) {
          record('Q2', 'GetViewXml/SetViewXml carries an <Aggregations> block', 'ABORTED', 'splice guard tripped: non-Aggregations content would change');
        } else {
          const set = await post(
            `${listPath}/views('${viewId}')`,
            { __metadata: { type: 'SP.View' }, ListViewXml: nextXml },
            { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
          );
          xmlWorked = set.ok;
          record(
            'Q2',
            'GetViewXml/SetViewXml carries an <Aggregations> block',
            set.ok ? 'ACCEPTED' : 'REFUSED',
            set.ok ? `HTTP ${set.status}` : `HTTP ${set.status} (${set.error})`,
          );
        }
      }
    } else {
      record('Q2', 'GetViewXml/SetViewXml carries an <Aggregations> block', 'NOT ATTEMPTED', 'the PATCH in Q1 was accepted, so the simpler mechanism wins');
    }

    // === Q3: read it back ================================================
    const after = await get(`${listPath}/views('${viewId}')?$select=Aggregations,AggregationsStatus`);
    const gotAgg = after.d?.Aggregations || '(null)';
    const gotStatus = after.d?.AggregationsStatus || '(null)';
    // Compared on the normalised form (normalizeAgg above) because SharePoint
    // stores the XML with a space before self-closing `/>` and quote changes.
    const matches = normalizeAgg(gotAgg) === normalizeAgg(AGG_XML) && gotStatus === 'On';
    record(
      'Q3',
      'the written property reads back unchanged',
      matches ? 'ROUND-TRIPPED' : 'MISMATCH',
      `Aggregations=${gotAgg} AggregationsStatus=${gotStatus}`,
    );

    const mechanism = patched.ok ? 'patch' : (xmlWorked ? 'setviewxml' : 'none');
    const visibleSetupReady = rowCount === 2 && !!viewId && !!viewUrl
      && amountOnView.ok && initialViewFields.ok && amountMembershipHeld;

    // === Q5/Q6: the naming question, and two columns at once =============
    //
    // WHY Q5 MATTERS MORE THAN THE REST. The sibling ColumnWidth property
    // binds by DISPLAY title. Internal names are accepted and silently
    // reset the widths (live finding, see jsgen). Aggregations is written
    // with INTERNAL names on the assumption that it does not behave the
    // same way, and the original run of this probe could not tell: it
    // created a field whose Title equalled its internal name, so the two
    // hypotheses were indistinguishable.
    //
    // Every template that ships totals uses display_names: auto, so every
    // totalled column's display title DIFFERS from its internal name,
    // i.e. all of them are in the case this probe never covered. If the
    // property binds by display title, the XML round-trips, both verify
    // halves pass, and no figure renders. That is the exact silent
    // failure this repository exists to prevent.
    const SECOND = 'SecondAmount';
    const SECOND_DISPLAY = 'Second Amount Display';
    const second = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldNumber' }, FieldTypeKind: 9, Title: SECOND,
    });
    if (second.ok) {
      // Rename the DISPLAY title, leaving the internal name as created,
      // the same create-then-rename trick deploy.js uses for every column.
      const renamed = await post(
        `${listPath}/fields/getbyinternalnameortitle('${odataName(SECOND)}')`,
        { __metadata: { type: 'SP.FieldNumber' }, Title: SECOND_DISPLAY },
        { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
      );
      const secondOnView = await post(
        `${listPath}/views('${viewId}')/viewfields/addviewfield('${odataName(SECOND)}')`,
      );
      const finalViewFields = await get(`${listPath}/views('${viewId}')/viewfields`);
      const finalViewFieldNames = finalViewFields.ok
        && Array.isArray(finalViewFields.d?.Items?.results)
        ? finalViewFields.d.Items.results
        : null;
      const renamedField = await get(
        `${listPath}/fields/getbyinternalnameortitle('${odataName(SECOND)}')?$select=InternalName,Title`,
      );

      // SEED THE SECOND COLUMN, because run 1 could not answer its own
      // question without it. The field is created after the rows, so both
      // were empty, and SharePoint renders NOTHING for an aggregation over
      // an empty column (no label, no zero). An operator looking for a
      // figure under "Second Amount Display" therefore saw exactly what a
      // FAILED BINDING would look like, and Q5 could only be settled by
      // hand-typing values into the list. That ambiguity is the probe's
      // fault; these two writes remove it.
      const secondValues = [1, 3];  // AVG 2, distinct from Amount's Sum 42
      const seededRows = await get(`${listPath}/items?$select=Id&$orderby=Id&$top=10`);
      const seededIds = (seededRows.ok && seededRows.d && seededRows.d.results
        ? seededRows.d.results.map((r) => r.Id) : []);
      const secondWrites = [];
      for (let i = 0; i < seededIds.length && i < secondValues.length; i += 1) {
        secondWrites.push(await post(
          `${listPath}/items(${seededIds[i]})`,
          { __metadata: { type: itemType }, [SECOND]: secondValues[i] },
          { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
        ));
      }
      const secondSeeded = seededIds.length === secondValues.length
        && secondWrites.length === secondValues.length
        && secondWrites.every((result) => result.ok);
      const secondSeedBack = await get(
        `${listPath}/items?$select=Id,${SECOND}&$orderby=Id&$top=2`,
      );
      const secondSeedValues = secondSeedBack.ok && secondSeedBack.d?.results
        ? secondSeedBack.d.results.map((row) => row[SECOND])
        : null;
      const secondControlsReady = visibleSetupReady && second.ok
        && renamed.ok && secondOnView.ok && finalViewFields.ok && renamedField.ok
        && secondSeeded;
      const both = `<FieldRef Name="${AGG_FIELD}" Type="${AGG_TYPE}"/>`
        + `<FieldRef Name="${SECOND}" Type="AVG"/>`;
      const wrote = await post(
        `${listPath}/views('${viewId}')`,
        { __metadata: { type: 'SP.View' }, Aggregations: both, AggregationsStatus: 'On' },
        { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
      );
      const back = await get(
        `${listPath}/views('${viewId}')?$select=Aggregations,AggregationsStatus`,
      );
      const manualOutcome = aggregationManualOutcome({
        setupReady: secondControlsReady,
        writeOk: wrote.ok && back.ok,
        aggregationXml: back.d?.Aggregations,
        expectedXml: both,
        aggregationStatus: back.d?.AggregationsStatus,
        seedValues: secondSeedValues,
        viewFieldNames: finalViewFieldNames,
        expectedViewFields: [AGG_FIELD, SECOND],
        fieldTitle: renamedField.d?.Title,
        expectedFieldTitle: SECOND_DISPLAY,
      });
      const q4ManualOutcome = aggregationManualOutcome({
        setupReady: secondControlsReady,
        writeOk: mechanism !== 'none' && after.ok,
        aggregationXml: gotAgg,
        expectedXml: AGG_XML,
        aggregationStatus: gotStatus,
        seedValues: secondSeedValues,
        viewFieldNames: finalViewFieldNames,
        expectedViewFields: [AGG_FIELD, SECOND],
        fieldTitle: renamedField.d?.Title,
        expectedFieldTitle: SECOND_DISPLAY,
      });
      record(
        'Q4',
        'a totals row actually RENDERS',
        q4ManualOutcome,
        q4ManualOutcome === 'MANUAL'
          ? `open ${window.location.origin}${viewUrl} and look for a total of 42 under ${AGG_FIELD}`
          : `controls not established: seeded=${rowCount === 2}, view=${!!viewId && !!viewUrl}, `
            + `amount-add-response=${amountOnView.ok}, initial-fields=${JSON.stringify(initialViewFieldNames)}, `
            + `second-add-response=${secondOnView.ok}, final-fields=${JSON.stringify(finalViewFieldNames)}, `
            + `rename-response=${renamed.ok}, final-title=${JSON.stringify(renamedField.d?.Title)}, `
            + `mechanism=${mechanism}, aggregation-readback=${matches}`,
      );
      record(
        'Q5',
        'Aggregations binds by INTERNAL name, not display title',
        manualOutcome,
        manualOutcome === 'MANUAL'
          ? `wrote Name="${SECOND}" while its DISPLAY title is "Second Amount Display"; `
            + `readback ${JSON.stringify(back.d.Aggregations)} with status On and seeds 1,3. `
            + `OPEN THE VIEW: a figure under "Second Amount Display" means INTERNAL names bind `
            + `(what the tool assumes). No figure under it means DISPLAY titles bind, and every `
            + `shipped totals view is silently empty.`
          : `controls not established: rename-response=${renamed.ok}, add-response=${secondOnView.ok}, `
            + `final-fields=${JSON.stringify(finalViewFieldNames)}, final-title=${JSON.stringify(renamedField.d?.Title)}, `
            + `second-seed-write=${secondSeeded}, second-seed-read=${JSON.stringify(secondSeedValues)}, `
            + `write=${wrote.ok}, aggregation=${JSON.stringify(back.d?.Aggregations)}, `
            + `status=${JSON.stringify(back.d?.AggregationsStatus)}`,
      );
      record(
        'Q6',
        'two totalled columns both render, in declaration order',
        manualOutcome,
        manualOutcome === 'MANUAL'
          ? 'the same view now declares two aggregations; confirm BOTH figures appear, and that '
            + 'the readback above preserved declaration order. The deployer compares the string '
            + 'exactly, so a reordered readback would drift on every redeploy'
          : `controls not established: rename-response=${renamed.ok}, add-response=${secondOnView.ok}, `
            + `final-fields=${JSON.stringify(finalViewFieldNames)}, final-title=${JSON.stringify(renamedField.d?.Title)}, `
            + `second-seed-write=${secondSeeded}, second-seed-read=${JSON.stringify(secondSeedValues)}, `
            + `write=${wrote.ok}, aggregation=${JSON.stringify(back.d?.Aggregations)}, `
            + `status=${JSON.stringify(back.d?.AggregationsStatus)}`,
      );
    } else {
      record('Q4', 'a totals row actually RENDERS', 'NOT ESTABLISHED', `controls not established: could not add ${SECOND}: HTTP ${second.status} ${second.error}`);
      record('Q5', 'Aggregations binds by INTERNAL name, not display title', 'NOT ESTABLISHED', `could not add ${SECOND}: HTTP ${second.status} ${second.error}`);
      record('Q6', 'two totalled columns both render, in declaration order', 'NOT ESTABLISHED', 'the second column could not be created');
    }

    // === Verdict =========================================================
    console.table(results.map(({ id, question, observed, detail }) => ({ id, question, observed, detail })));
    log(
      'VERDICT',
      `seeded=${rowCount === 2 ? 'ok' : 'FAILED'} mechanism=${mechanism} `
      + `readback=${matches ? 'ok' : 'mismatch'} rendered=<fill in after looking>`,
    );
    if (rowCount !== 2) {
      log('ERROR', 'seeded=FAILED. An empty list shows no totals row whether the feature works or not, so `rendered=no` from this run would mean nothing. Fix the seeding and re-run before reporting.');
    }
    log('INFO', 'Paste the VERDICT line back, with rendered= set to yes or no.');
    return { seeded: rowCount, mechanism, readback: matches ? 'ok' : 'mismatch', viewUrl, results };
  } finally {
    if (createdList && CLEANUP_AT_END) {
      const gone = await recycleOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION);
      if (gone.ok) {
        log('INFO', `Recycled '${PROBE_LIST}'.`);
      } else {
        log('ERROR', `COULD NOT RECYCLE '${PROBE_LIST}' (${gone.error}). Recycle it by hand: ${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`);
      }
    } else if (createdList) {
      log('INFO', `Left '${PROBE_LIST}' in place for the manual step. Re-run with CLEANUP_AT_END = true to remove it.`);
    }
  }
})();
