/**
 * dbml-sharepoint HYPERLINK VALIDATION OPERAND PROBE (creates and deletes
 * its own list).
 *
 * Answers one question the documentation does not: does a SharePoint list
 * validation formula honour a HYPERLINK (URL) column operand — and if it
 * does, which half of the column does it compare?
 *
 * WHY THIS EXISTS. `templates/audit-actions` shipped a rule requiring an
 * EvidenceUrl before a recommendation could be closed. Nobody had ever
 * read one back from a live tenant. A URL column is not a scalar: it
 * stores a Url AND a Description, and no first-party source says which a
 * formula sees, or whether ISBLANK on one means anything at all. The rule
 * may have been passing everything it was written to stop, for as long as
 * it shipped — which is this repository's worst failure mode, because a
 * save rule that never fires looks exactly like a save rule that is never
 * broken.
 *
 * The build now refuses the operand outright
 * (`analysis/conditions.py`, `_UNVERIFIED_OPERAND_TYPES`). This probe is
 * how that refusal gets lifted, or confirmed. Microsoft's published
 * unsupported-type list for CONDITIONAL SHOW/HIDE does not name Hyperlink,
 * but that governs a different surface and is not evidence about this one.
 *
 * WHAT IT WRITES: one list, named by PROBE_LIST below, created at start
 * and deleted at end (unless CLEANUP_AT_END = false). It never reads,
 * writes or enumerates any other list. If cleanup fails it says so loudly
 * and prints the URL to delete by hand.
 *
 * HOW TO RUN
 *   1. Paste it once: it prints the web and stops. Set CONFIRMED = true.
 *   2. Open that site's classic settings page — /_layouts/15/settings.aspx —
 *      signed in as a Site Owner. The site guard needs _spPageContextInfo.
 *   3. F12 -> Console -> type `allow pasting` if the browser objects ->
 *      paste this whole file -> Enter.
 *   4. Read the RESULTS table and paste the [VERDICT] line back.
 *   5. Re-run with CLEANUP_AT_END = true to remove the probe list. It
 *      ships false so that pasting this file cannot delete anything on
 *      the tenant of whoever ran it.
 *
 * NOTHING HERE IS MANUAL. Unlike the aggregations probe, every question is
 * answered by whether SharePoint accepts or refuses a write, so the script
 * settles it end to end — there is nothing to go and look at.
 *
 * READ Q2 FIRST. It is the whole question. Q1 only asks whether SharePoint
 * stores the formula, and a stored formula that never fires is precisely
 * the thing being tested for: it reads back byte-identical, passes every
 * deploy check, and enforces nothing.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const PROBE_LIST = 'zzz dbmlsp hyperlink validation probe';
  // Committed false, and test/test_probes.py enforces that: a probe whose
  // cleanup flag ships flipped deletes a list on the tenant of whoever
  // pastes it, without asking. Set it true on your final run.
  const CLEANUP_AT_END = false;
  // ------------------------------------------------------------------------

  const log = (level, msg) => console.log(`[SP-PROBE] [${level}] ${msg}`);
  const results = [];
  const expect = (id, question) => {
    results.push({ id, question, observed: 'NOT ESTABLISHED', detail: 'the run did not reach this question' });
  };
  const record = (id, question, observed, detail) => {
    const row = results.find((r) => r.id === id);
    if (row) {
      Object.assign(row, { question, observed, detail: detail || '' });
    } else {
      results.push({ id, question, observed, detail: detail || '' });
    }
    log('INFO', `${id}: ${observed}${detail ? ` — ${detail}` : ''}`);
  };
  expect('Q0', 'the probe list, its URL column and a control row are set up');
  expect('Q1', 'SharePoint ACCEPTS a ValidationFormula referencing a URL column');
  expect('Q2', 'the rule FIRES: a violating row is refused');
  expect('Q3', 'the rule PASSES a compliant row (not simply refusing everything)');
  expect('Q4', 'ISBLANK sees a Url with an EMPTY description as present');
  expect('Q5', 'an equality comparison matches the Url rather than the Description');

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
    const r = await fetchWithRetry(apiUrl(suffix), {
      method: 'GET', headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!r.ok) return { ok: false, status: r.status, error: spError(await r.text()) };
    return { ok: true, status: r.status, d: (await r.json()).d };
  }
  const merge = (suffix, body) => post(suffix, body, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  // An item POST's __metadata.type must be the LIST'S OWN entity type,
  // never the generic SP.Data.ListItem — that mistake cost the aggregations
  // probe two silent HTTP 400s.
  async function entityTypeFor(listTitle) {
    const r = await get(
      `web/lists/getbytitle('${odataName(listTitle)}')?$select=ListItemEntityTypeFullName`,
    );
    if (!r.ok) throw new Error(`could not resolve the item entity type: ${r.error}`);
    return r.d.ListItemEntityTypeFullName;
  }

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
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
    log('INFO', `  ${label}: ${r.ok ? 'ACCEPTED' : `REFUSED (HTTP ${r.status})`}`);
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
    // === Q0: setup =======================================================
    const made = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: PROBE_LIST,
      Description: 'dbml-sharepoint hyperlink validation probe. Safe to delete.',
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
      set1.ok ? 'ACCEPTED' : 'REFUSED',
      set1.ok
        ? `HTTP ${set1.status}; stored as ${JSON.stringify(set1.stored)}`
        : `HTTP ${set1.status} — ${set1.error}`,
    );

    if (set1.ok) {
      // === Q2: does it FIRE? ============================================
      // THE question. An ACCEPTED row here means the rule is stored,
      // reads back byte-identical, and does nothing — the silent failure
      // that made audit-actions' evidence requirement untrustworthy.
      const violating = await tryCreate('Doc empty, rule requires it', { Title: 'violating' });
      record(
        'Q2',
        'the rule FIRES: a violating row is refused',
        violating.ok ? 'DID NOT FIRE' : 'FIRED',
        violating.ok
          ? 'the row was ACCEPTED with Doc blank — the rule is stored and inert, which is exactly the failure the build refuses the operand to avoid'
          : `refused with HTTP ${violating.status}: ${violating.error}`,
      );

      // === Q3: does it pass a compliant row? ============================
      // Guards against the opposite error — a rule that refuses everything
      // would also "fire" on Q2 while being equally useless.
      const compliant = await tryCreate('Doc filled', {
        Title: 'compliant', Doc: urlValue(EVIDENCE),
      });
      record(
        'Q3',
        'the rule PASSES a compliant row (not simply refusing everything)',
        compliant.ok ? 'PASSED' : 'REFUSED EVERYTHING',
        compliant.ok
          ? 'a filled Doc saves, so the rule discriminates'
          : `a filled Doc was ALSO refused (HTTP ${compliant.status}: ${compliant.error}) — the formula rejects every row regardless, which is not enforcement`,
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
        noDescription.ok ? 'SEES THE URL' : 'SEES THE DESCRIPTION',
        noDescription.ok
          ? 'a Url with no Description satisfies NOT(ISBLANK(...)), so the formula reads the Url'
          : `refused (HTTP ${noDescription.status}) — the formula is reading the DESCRIPTION, so a pasted link with no label would be rejected as missing`,
      );

      // === Q5: which half does an equality comparison see? ==============
      // Set a rule matching the URL exactly, then offer a row whose
      // DESCRIPTION is that string and whose Url is different. Accepted
      // means the comparison saw the description.
      const eqRule = `=[Doc]="${EVIDENCE}"`;
      const set2 = await setRule(eqRule, 'Doc must be the evidence URL.');
      if (!set2.ok) {
        record('Q5', 'an equality comparison matches the Url rather than the Description', 'NOT ESTABLISHED', `could not set the equality rule: HTTP ${set2.status} ${set2.error}`);
      } else {
        const byUrl = await tryCreate('Url matches, Description differs', {
          Title: 'by-url', Doc: urlValue(EVIDENCE, 'a label'),
        });
        const byDescription = await tryCreate('Description matches, Url differs', {
          Title: 'by-description', Doc: urlValue(OTHER, EVIDENCE),
        });
        const observed = byUrl.ok && !byDescription.ok ? 'MATCHES THE URL'
          : !byUrl.ok && byDescription.ok ? 'MATCHES THE DESCRIPTION'
            : byUrl.ok && byDescription.ok ? 'MATCHES EITHER'
              : 'MATCHES NEITHER';
        record(
          'Q5',
          'an equality comparison matches the Url rather than the Description',
          observed,
          `url-match row ${byUrl.ok ? 'accepted' : 'refused'}; description-match row ${byDescription.ok ? 'accepted' : 'refused'}`,
        );
      }
    } else {
      for (const id of ['Q2', 'Q3', 'Q4', 'Q5']) {
        record(id, results.find((r) => r.id === id).question, 'NOT REACHED', 'SharePoint refused the formula at Q1, which settles it: the operand is unusable');
      }
    }

    // === Verdict =========================================================
    const q = (id) => results.find((r) => r.id === id)?.observed;
    const usable = q('Q1') === 'ACCEPTED' && q('Q2') === 'FIRED' && q('Q3') === 'PASSED';
    console.table(results.map(({ id, question, observed, detail }) => ({ id, question, observed, detail })));
    log(
      'VERDICT',
      `accepted=${q('Q1')} fires=${q('Q2')} discriminates=${q('Q3')} `
      + `blank_reads=${q('Q4')} equality_reads=${q('Q5')} => operand_usable=${usable ? 'YES' : 'NO'}`,
    );
    log(
      'INFO',
      usable
        ? 'Usable. Remove the "hyperlink" entry from _UNVERIFIED_OPERAND_TYPES in analysis/conditions.py, restore audit-actions\' EvidenceUrl rule, and cite this run.'
        : 'NOT usable. Leave the build refusal in place and keep the requirement as a governance check.',
    );
    return { usable, results };
  } finally {
    if (createdList && CLEANUP_AT_END) {
      // The validation formula must go first: a list rule can otherwise
      // interfere with the delete on some tenants, and clearing it costs
      // one call.
      await merge(listPath, { __metadata: { type: 'SP.List' }, ValidationFormula: '', ValidationMessage: '' });
      const gone = await post(listPath, undefined, { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
      if (gone.ok) {
        log('INFO', `Deleted '${PROBE_LIST}'.`);
      } else {
        log('ERROR', `COULD NOT DELETE '${PROBE_LIST}' (HTTP ${gone.status} ${gone.error}). Delete it by hand: ${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`);
      }
    } else if (createdList) {
      log('INFO', `Left '${PROBE_LIST}' in place. Re-run with CLEANUP_AT_END = true to remove it.`);
    }
  }
})();
