/**
 * HYPERLINK VALIDATION OPERAND PROBE.
 *
 * Creates one owned list and asks whether list validation accepts a URL
 * operand and, only if accepted, whether the rule fires and which URL value
 * it compares. The committed catalogue defines its six findings, write scope
 * and cleanup policy. Historical conclusions belong in evidence, not here.
 *
 * Set CONFIRMED=true only after the script prints the intended web. Set
 * CLEANUP_AT_END=true on a later run to remove a retained fixture.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const PROBE_LIST = 'zzz dbmlsp hyperlink validation probe';
  // Committed false, and test/test_probes.py enforces that: a probe whose
  // cleanup flag ships flipped deletes a list on the tenant of whoever
  // pastes it, without asking. Set it true on your final run.
  const CLEANUP_AT_END = false;
  const PROBE_RETRY_TRANSIENT = true;
  const PROBE_RETRY_ATTEMPTS = 5;
  // ------------------------------------------------------------------------

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
  expect('Q0', 'the probe list, its URL column and a control row are set up');
  expect('Q1', 'SharePoint ACCEPTS a ValidationFormula referencing a URL column');
  expect('Q2', 'the rule FIRES: a violating row is refused');
  expect('Q3', 'the rule PASSES a compliant row (not simply refusing everything)');
  expect('Q4', 'ISBLANK sees a Url with an EMPTY description as present');
  expect('Q5', 'an equality comparison matches the Url rather than the Description');

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
  log('INFO', `probe revision c54b23c0; core v2; results v1.`);
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
  // SharePoint list/formula validation refusals are HTTP 400. Other failures
  // cannot establish application behavior and must not be described as refusals.
  const isSharePointBehavioralRefusal = (r) => !r.ok && r.status === 400;
  const classifyAttempt = (r, accepted, refused) => r.ok
    ? accepted : isSharePointBehavioralRefusal(r) ? refused : 'NOT ESTABLISHED';
  const describeAttempt = (r, accepted, refused) => r.ok
    ? accepted
    : isSharePointBehavioralRefusal(r)
      ? refused
      : `NOT ESTABLISHED: HTTP ${r.status} ${r.error}`;
  const describeDisposition = (r) => r.ok
    ? 'accepted'
    : isSharePointBehavioralRefusal(r)
      ? 'behaviorally refused'
      : `NOT ESTABLISHED (HTTP ${r.status} ${r.error})`;
  const hyperlinkOperandVerdict = ({ Q1, Q2, Q3 }) => {
    if (Q1 === 'ACCEPTED' && Q2 === 'FIRED' && Q3 === 'PASSED') {
      return {
        operandUsable: 'YES',
        guidance: 'Usable. Remove the "hyperlink" entry from _FORBIDDEN_OPERAND_TYPES[VALIDATION] in analysis/conditions.py, restore audit-actions\' EvidenceUrl rule, and cite this run.',
      };
    }
    if ([Q1, Q2, Q3].includes('NOT ESTABLISHED')) {
      return {
        operandUsable: 'NOT ESTABLISHED',
        guidance: 'Evidence is inconclusive. Do not change build behavior from this run; repeat the probe after resolving the failed request.',
      };
    }
    if (Q1 === 'REFUSED' || Q2 === 'DID NOT FIRE' || Q3 === 'REFUSED EVERYTHING') {
      return {
        operandUsable: 'NO',
        guidance: 'NOT usable. Leave the build refusal in place and keep the requirement as a governance check.',
      };
    }
    return {
      operandUsable: 'NOT ESTABLISHED',
      guidance: 'Evidence is inconclusive. Do not change build behavior from this run; repeat the probe after resolving the failed request.',
    };
  };

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const OWNERSHIP_DESCRIPTION = 'dbml-sharepoint hyperlink validation probe. Safe to delete.';
  const EVIDENCE = 'https://example.invalid/evidence.pdf';
  const OTHER = 'https://example.invalid/other.pdf';
  let createdList = false;
  let itemType = null;

  // A URL column takes a record, not a string.
  const urlValue = (url, description) => ({
    __metadata: { type: 'SP.FieldUrlValue' },
    Url: url,
    Description: description === undefined ? url : description,
  });
  // Every attempt below is "does SharePoint let this row be created?".
  // REFUSED is the interesting answer, so the helper reports both plainly.
  async function tryCreate(label, fields) {
    const r = await post(`${listPath}/items`, { __metadata: { type: itemType }, ...fields });
    log('INFO', `  ${label}: ${r.ok ? 'ACCEPTED'
      : isSharePointBehavioralRefusal(r) ? `REFUSED (HTTP ${r.status})`
        : `NOT ESTABLISHED (HTTP ${r.status})`}`);
    return r;
  }
  async function setRule(formula, message) {
    const r = await merge(listPath, {
      __metadata: { type: 'SP.List' },
      ValidationFormula: formula,
      ValidationMessage: message,
    });
    if (r.ok) {
      // Read back: a formula SharePoint stores unchanged is not the same as
      // a formula SharePoint honours, and this probe is about the gap
      // between those two.
      const back = await get(`${listPath}?$select=ValidationFormula`);
      return { ...r, stored: back.ok ? back.d.ValidationFormula : '(unreadable)' };
    }
    return { ...r, stored: null };
  }

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
        `The owned fixture '${PROBE_LIST}' is retained for evidence. Re-run with CLEANUP_AT_END=true to recycle it before a fresh run.`,
      );
      console.table(results);
      return { usable: false, results };
    }

    // === Q0: setup =======================================================
    const made = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: PROBE_LIST,
      Description: OWNERSHIP_DESCRIPTION,
    });
    if (!made.ok) {
      record('Q0', 'setup', 'ABORTED', `could not create the probe list: HTTP ${made.status} ${made.error}`);
      throw new Error('setup failed');
    }
    createdList = true;

    const field = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldUrl' },
      FieldTypeKind: 11,          // URL
      Title: 'Doc',
    });
    if (!field.ok) {
      record('Q0', 'setup', 'ABORTED', `could not add the Doc URL column: HTTP ${field.status} ${field.error}`);
      throw new Error('setup failed');
    }
    itemType = await entityTypeFor(PROBE_LIST);
    // A control row created BEFORE any rule exists, proving the list
    // accepts items at all. Without it, a later REFUSED could mean the
    // rule fired or could mean the list was broken all along.
    const control = await tryCreate('control row, no rule set', { Title: 'control' });
    record(
      'Q0',
      'the probe list, its URL column and a control row are set up',
      control.ok ? 'READY' : 'ABORTED',
      control.ok ? 'Doc is FieldTypeKind 11 (URL)' : `control row refused: HTTP ${control.status} ${control.error}`,
    );
    if (!control.ok) throw new Error('setup failed');

    // === Q1: will SharePoint STORE the formula? ==========================
    // The audit-actions shape, reduced to its hyperlink half.
    const blankRule = '=NOT(ISBLANK([Doc]))';
    const set1 = await setRule(blankRule, 'Doc is required.');
    record(
      'Q1',
      'SharePoint ACCEPTS a ValidationFormula referencing a URL column',
      classifyAttempt(set1, 'ACCEPTED', 'REFUSED'),
      describeAttempt(
        set1,
        `HTTP ${set1.status}; stored as ${JSON.stringify(set1.stored)}`,
        `SharePoint refused the validation formula (HTTP ${set1.status}: ${set1.error})`,
      ),
    );

    if (set1.ok) {
      // === Q2: does it FIRE? ============================================
      // THE question. An ACCEPTED row here means the rule is stored,
      // reads back byte-identical, and does nothing, the silent failure
      // that made audit-actions' evidence requirement untrustworthy.
      const violating = await tryCreate('Doc empty, rule requires it', { Title: 'violating' });
      record(
        'Q2',
        'the rule FIRES: a violating row is refused',
        classifyAttempt(violating, 'DID NOT FIRE', 'FIRED'),
        describeAttempt(
          violating,
          'the row was ACCEPTED with Doc blank, so the rule is stored and inert, which is exactly the failure the build refuses the operand to avoid',
          `the rule behaviorally refused the row (HTTP ${violating.status}: ${violating.error})`,
        ),
      );

      // === Q3: does it pass a compliant row? ============================
      // Guards against the opposite error, a rule that refuses everything
      // would also "fire" on Q2 while being equally useless.
      const compliant = await tryCreate('Doc filled', {
        Title: 'compliant', Doc: urlValue(EVIDENCE),
      });
      record(
        'Q3',
        'the rule PASSES a compliant row (not simply refusing everything)',
        classifyAttempt(compliant, 'PASSED', 'REFUSED EVERYTHING'),
        describeAttempt(
          compliant,
          'a filled Doc saves, so the rule discriminates',
          `a filled Doc was behaviorally refused (HTTP ${compliant.status}: ${compliant.error}), so the formula rejects every row regardless, which is not enforcement`,
        ),
      );

      // === Q4: Url present, Description empty ===========================
      // The half-populated case a real author produces by pasting a link
      // without typing a label. If ISBLANK reads the DESCRIPTION, this row
      // is refused despite carrying a perfectly good URL.
      const noDescription = await tryCreate('Doc Url set, Description empty', {
        Title: 'no-description', Doc: urlValue(OTHER, ''),
      });
      record(
        'Q4',
        'ISBLANK sees a Url with an EMPTY description as present',
        classifyAttempt(noDescription, 'SEES THE URL', 'SEES THE DESCRIPTION'),
        describeAttempt(
          noDescription,
          'a Url with no Description satisfies NOT(ISBLANK(...)), so the formula reads the Url',
          `behaviorally refused (HTTP ${noDescription.status}), so the formula is reading the DESCRIPTION, and a pasted link with no label would be rejected as missing`,
        ),
      );

      // === Q5: which half does an equality comparison see? ==============
      // Set a rule matching the URL exactly, then offer a row whose
      // DESCRIPTION is that string and whose Url is different. Accepted
      // means the comparison saw the description.
      const eqRule = `=[Doc]="${EVIDENCE}"`;
      const set2 = await setRule(eqRule, 'Doc must be the evidence URL.');
      if (!set2.ok) {
        record(
          'Q5',
          'an equality comparison matches the Url rather than the Description',
          isSharePointBehavioralRefusal(set2) ? 'NOT APPLICABLE' : 'NOT ESTABLISHED',
          describeAttempt(
            set2,
            'the equality rule was set',
            `SharePoint refused the equality formula (HTTP ${set2.status}: ${set2.error})`,
          ),
        );
      } else {
        const byUrl = await tryCreate('Url matches, Description differs', {
          Title: 'by-url', Doc: urlValue(EVIDENCE, 'a label'),
        });
        const byDescription = await tryCreate('Description matches, Url differs', {
          Title: 'by-description', Doc: urlValue(OTHER, EVIDENCE),
        });
        const rowsAreSemantic = [byUrl, byDescription]
          .every((r) => r.ok || isSharePointBehavioralRefusal(r));
        const observed = !rowsAreSemantic ? 'NOT ESTABLISHED'
          : byUrl.ok && isSharePointBehavioralRefusal(byDescription) ? 'MATCHES THE URL'
            : isSharePointBehavioralRefusal(byUrl) && byDescription.ok ? 'MATCHES THE DESCRIPTION'
              : byUrl.ok && byDescription.ok ? 'MATCHES EITHER'
                : 'MATCHES NEITHER';
        record(
          'Q5',
          'an equality comparison matches the Url rather than the Description',
          observed,
          `url-match row ${describeDisposition(byUrl)}; description-match row ${describeDisposition(byDescription)}`,
        );
      }
    } else {
      for (const id of ['Q2', 'Q3', 'Q4', 'Q5']) {
        record(
          id,
          results.find((r) => r.id === id).question,
          isSharePointBehavioralRefusal(set1) ? 'NOT APPLICABLE' : 'NOT ESTABLISHED',
          isSharePointBehavioralRefusal(set1)
            ? 'SharePoint refused the formula at Q1, so the conditional downstream question has no executable subject'
            : `Q1 failed without a semantic response (HTTP ${set1.status} ${set1.error})`,
        );
      }
    }

    // === Verdict =========================================================
    const q = (id) => results.find((r) => r.id === id)?.observed;
    const verdict = hyperlinkOperandVerdict({ Q1: q('Q1'), Q2: q('Q2'), Q3: q('Q3') });
    console.table(results.map(({ id, question, observed, detail }) => ({ id, question, observed, detail })));
    log(
      'VERDICT',
      `accepted=${q('Q1')} fires=${q('Q2')} discriminates=${q('Q3')} `
      + `blank_reads=${q('Q4')} equality_reads=${q('Q5')} => operand_usable=${verdict.operandUsable}`,
    );
    log('INFO', verdict.guidance);
    return { operandUsable: verdict.operandUsable, results };
  } finally {
    if (createdList && CLEANUP_AT_END) {
      // The validation formula must go first: a list rule can otherwise
      // interfere with the delete on some tenants, and clearing it costs
      // one call.
      await merge(listPath, { __metadata: { type: 'SP.List' }, ValidationFormula: '', ValidationMessage: '' });
      const gone = await recycleOwnedList(PROBE_LIST, OWNERSHIP_DESCRIPTION);
      if (gone.ok) {
        log('INFO', `Recycled '${PROBE_LIST}'.`);
      } else {
        log('ERROR', `COULD NOT RECYCLE '${PROBE_LIST}' (${gone.error}). Recycle it by hand: ${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`);
      }
    } else if (createdList) {
      log('INFO', `Left '${PROBE_LIST}' in place. Re-run with CLEANUP_AT_END = true to remove it.`);
    }
  }
})();
