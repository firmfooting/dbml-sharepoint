/**
 * dbml-sharepoint FORM VISIBILITY — EVIDENCE PROBE
 *
 * Captures everything the form_visibility spec still needs verified.
 * Supersedes form-order-conditional-probe.js (field order + which store
 * holds the conditional formula), and adds the open questions:
 *
 *   A. COLLISION — does SharePoint's modern COLUMN VALIDATION UI write
 *      ClientValidationFormula? If it does, this design would silently
 *      destroy validation rules and the mechanism needs rethinking. This
 *      is the one risk that invalidates rather than adjusts the design.
 *   B. CANONICAL SYNTAX — what exact expression does SharePoint itself
 *      generate for dates, people, lookups, OR, nesting and awkward
 *      values? The spec rejects those operands today because their
 *      projection is unverified. Reading back what the UI writes is how
 *      that restriction gets lifted with evidence instead of guesswork.
 *   C. ROUND-TRIP FIDELITY — is a written formula read back byte-identical
 *      or normalised? Decides whether reconciliation needs
 *      canonicalisation, as the calculated-formula comparison already does.
 *   D. LENGTH LIMIT — the real ceiling for ClientValidationFormula. The
 *      spec assumes 1024 by analogy; assumptions in formula limits have
 *      already bitten once.
 *
 * A and B are READ-ONLY: you configure things in the UI, this reads what
 * SharePoint stored. C and D require writes and are OFF by default.
 *
 * HOW TO RUN
 *   1. Open the target site's /_layouts/15/settings.aspx as a Site Owner.
 *   2. F12 -> Console -> paste -> Enter. It prints the web and stops.
 *   3. Set CONFIRMED = true, paste again.
 *   4. Work through the CHECKLIST it prints, then paste again to harvest.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const PROBE_LIST = 'zzz dbmlsp form visibility interactive';
  // Writes! Creates one throwaway column and writes formulas to it to
  // answer C and D. Leave false for a purely read-only run.
  const ALLOW_WRITES = false;
  // ------------------------------------------------------------------------

  const log = (m) => console.log(`%c[EVIDENCE] ${m}`, 'color:#0a7');
  const say = (m) => console.log(m);
  const rule = () => console.log('%c' + '─'.repeat(70), 'color:#888');
  const bold = (m) => console.log(`%c${m}`, 'font-weight:bold;font-size:13px');

  if (typeof _spPageContextInfo === 'undefined') {
    console.error('[EVIDENCE] _spPageContextInfo unavailable. Open /_layouts/15/settings.aspx and retry.');
    return { aborted: 'no-sp-page-context' };
  }
  const actPath = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (!CONFIRMED) {
    console.error(`[EVIDENCE] Target web:  ${window.location.origin}${actPath}`);
    console.error(`[EVIDENCE] Target list: ${PROBE_LIST}`);
    console.error(`[EVIDENCE] Writes: ${ALLOW_WRITES ? 'ENABLED' : 'disabled (read-only)'}`);
    console.error('[EVIDENCE] If that is right, set CONFIRMED = true and paste again.');
    return { aborted: 'not-confirmed' };
  }
  const WEB = actPath;
  const apiUrl = (s) => `${WEB}/_api/${s}`;
  const odataName = (n) => encodeURIComponent(String(n).replace(/'/g, "''"));
  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const fieldPath = (n) => `${listPath}/fields/getbyinternalnameortitle('${odataName(n)}')`;

  async function get(s) {
    const r = await fetch(apiUrl(s), { headers: { Accept: 'application/json;odata=verbose' } });
    if (!r.ok) {
      let d = '';
      try { d = JSON.parse(await r.text())?.error?.message?.value || ''; } catch { /* ignore */ }
      return { ok: false, status: r.status, error: d };
    }
    const j = await r.json();
    return { ok: true, d: j && j.d !== undefined ? j.d : j };
  }
  let digest = null;
  async function getDigest() {
    if (digest) return digest;
    const r = await fetch(apiUrl('contextinfo'), { method: 'POST', headers: { Accept: 'application/json;odata=verbose' } });
    digest = (await r.json()).d.GetContextWebInformation.FormDigestValue;
    return digest;
  }
  async function post(s, body, extra) {
    const d = await getDigest();
    const r = await fetch(apiUrl(s), {
      method: 'POST',
      headers: { Accept: 'application/json;odata=verbose', 'Content-Type': 'application/json;odata=verbose', 'X-RequestDigest': d, ...(extra || {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (r.ok) return { ok: true, status: r.status };
    let e = '';
    try { e = JSON.parse(await r.text())?.error?.message?.value || ''; } catch { /* ignore */ }
    return { ok: false, status: r.status, error: e };
  }

  if (!(await get(`${listPath}?$select=Title`)).ok) {
    console.error(`[EVIDENCE] List '${PROBE_LIST}' not found. Set PROBE_LIST at the top.`);
    return { aborted: 'no-list' };
  }

  // Every property that could plausibly carry visibility or validation.
  const PROPS = [
    'InternalName', 'TypeAsString', 'Sealed', 'Hidden', 'Required', 'DefaultValue',
    'ValidationFormula', 'ValidationMessage',
    'ClientValidationFormula', 'ClientValidationMessage',
    'CustomFormatter', 'ClientSideComponentProperties', 'SchemaXml',
  ];

  const fieldsResp = await get(`${listPath}/fields?$select=${PROPS.join(',')}&$top=500`);
  if (!fieldsResp.ok) {
    console.error(`[EVIDENCE] Field read failed: HTTP ${fieldsResp.status} ${fieldsResp.error}`);
    return { aborted: 'fields-read-failed' };
  }
  const all = fieldsResp.d.results || [];
  const parseXml = (x) => new DOMParser().parseFromString(String(x || '<Field/>'), 'application/xml');
  const isFalse = (el, n) => (el.getAttribute(n) || '').toUpperCase() === 'FALSE';

  // === Content type field links (order + Hidden) ==========================
  // Read BEFORE filtering: the content type's field link set is the honest
  // definition of "a column on this form". A name-prefix denylist is not —
  // an earlier version of this probe used one and the table came back with
  // fifty rows of owshiddenversion, LinkTitle2, MetaInfo and friends.
  const ctResp = await get(`${listPath}/contenttypes?$select=Name,StringId`);
  const cts = ctResp.ok ? (ctResp.d.results || []).filter((c) => c.Name !== 'Folder') : [];
  const linkByName = new Map();
  let linkOrder = [];
  for (const ct of cts) {
    const fl = await get(`${listPath}/contenttypes('${encodeURIComponent(ct.StringId)}')/fieldlinks?$select=Name,Id,Hidden&$top=500`);
    if (!fl.ok) continue;
    const links = fl.d.results || [];
    if (!linkOrder.length) linkOrder = links.map((l) => l.Name);
    for (const l of links) if (!linkByName.has(l.Name)) linkByName.set(l.Name, l);
  }

  // Show a field if the content type links it (it can reach a form), or if
  // it carries evidence (never hide a formula from the harvest), or if it is
  // this probe's own scratch column.
  const relevant = (f) => linkByName.has(f.InternalName)
    || f.ValidationFormula || f.ClientValidationFormula || f.ClientValidationMessage
    || f.InternalName === 'ZZEvidence';
  const fields = all.filter(relevant);
  if (all.length !== fields.length) {
    log(`Showing ${fields.length} of ${all.length} fields — the rest are list plumbing `
      + 'the content type does not link.');
  }

  // === 1. Field order =====================================================
  rule();
  bold('1 — FIELD ORDER');
  say('List field collection:');
  say(`  ${fields.map((f) => f.InternalName).join(' → ')}`);
  say('Content type FieldLink order (what the form follows, absent body sections):');
  say(`  ${linkOrder.join(' → ')}`);

  // === 2. The full store map ==============================================
  rule();
  bold('2 — STORE MAP  (every property that could hold visibility or validation)');
  const short = (v, n = 46) => {
    const s = v === undefined || v === null ? '' : String(v);
    return s.length > n ? `${s.slice(0, n)}…` : s;
  };
  console.table(fields.map((f) => {
    const el = parseXml(f.SchemaXml).documentElement;
    const link = linkByName.get(f.InternalName);
    return {
      column: f.InternalName,
      type: f.TypeAsString,
      sealed: f.Sealed ? 'Y' : '',
      req: f.Required ? 'Y' : '',
      'xml new': isFalse(el, 'ShowInNewForm') ? 'HIDDEN' : 'shown',
      'xml edit': isFalse(el, 'ShowInEditForm') ? 'HIDDEN' : 'shown',
      'FieldLink.Hidden': link ? (link.Hidden ? 'HIDDEN' : 'shown') : '(none)',
      ValidationFormula: short(f.ValidationFormula),
      ClientValidationFormula: short(f.ClientValidationFormula),
      ClientValidationMessage: short(f.ClientValidationMessage, 20),
    };
  }));

  // === 3. COLLISION VERDICT ==============================================
  rule();
  bold('3 — COLLISION: does column VALIDATION write ClientValidationFormula?');
  const withVal = fields.filter((f) => f.ValidationFormula);
  const withClient = fields.filter((f) => f.ClientValidationFormula);
  const withBoth = fields.filter((f) => f.ValidationFormula && f.ClientValidationFormula);
  log(`columns with ValidationFormula (column validation):      ${withVal.map((f) => f.InternalName).join(', ') || '(none)'}`);
  log(`columns with ClientValidationFormula (conditional vis):  ${withClient.map((f) => f.InternalName).join(', ') || '(none)'}`);
  log(`columns with BOTH:                                       ${withBoth.map((f) => f.InternalName).join(', ') || '(none)'}`);
  if (!withVal.length) {
    log('VERDICT: inconclusive — no column has a validation rule yet. See the CHECKLIST.');
  } else if (withBoth.length) {
    log('VERDICT: SAFE — a column holds validation and conditional visibility SIMULTANEOUSLY '
      + 'in two different properties. They do not collide.');
  } else {
    const valOnly = withVal.filter((f) => !f.ClientValidationFormula);
    log(valOnly.length
      ? 'VERDICT: LIKELY SAFE — validation lands in ValidationFormula and left '
        + 'ClientValidationFormula empty. Confirm by adding conditional visibility to that '
        + 'same column and re-running (the BOTH row should then be populated).'
      : 'VERDICT: DANGER — validation appears to have written ClientValidationFormula. '
        + 'STOP: the form_visibility mechanism would destroy validation rules.');
  }

  // === 4. Canonical syntax harvest =======================================
  rule();
  bold('4 — CANONICAL SYNTAX  (what SharePoint itself generates)');
  if (!withClient.length) {
    log('No conditional visibility formulas found yet. See the CHECKLIST.');
  } else {
    for (const f of withClient) {
      say(`  ${f.InternalName}  (${f.TypeAsString}, ${String(f.ClientValidationFormula).length} chars)`);
      console.log(`%c    ${f.ClientValidationFormula}`, 'color:#06c');
    }
    log('These are SharePoint\'s own projections. Each one that covers a rejected '
      + 'operand class (date, person, lookup, apostrophe) is the evidence needed to '
      + 'lift that restriction in the spec.');
  }

  // === 5. Optional write tests ===========================================
  const writeResults = {};
  if (ALLOW_WRITES) {
    rule();
    bold('5 — WRITE TESTS  (round-trip fidelity and length limit)');
    const COL = 'ZZEvidence';
    if (!fields.some((f) => f.InternalName === COL)) {
      const made = await post(`${listPath}/fields`, { __metadata: { type: 'SP.Field' }, FieldTypeKind: 2, Title: COL });
      log(made.ok ? `Created throwaway column ${COL}.` : `Could not create ${COL}: HTTP ${made.status} ${made.error}`);
    }
    const setFormula = async (formula) => post(fieldPath(COL),
      { __metadata: { type: 'SP.Field' }, ClientValidationFormula: formula },
      { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    const readFormula = async () => {
      const r = await get(`${fieldPath(COL)}?$select=ClientValidationFormula`);
      return r.ok ? String(r.d.ClientValidationFormula || '') : null;
    };

    // C — round-trip fidelity.
    const probeFormula = "=if(and([$Title] != '', [$Title] != 'x'), 'true', 'false')";
    const wrote = await setFormula(probeFormula);
    const readBack = wrote.ok ? await readFormula() : null;
    writeResults.roundTrip = !wrote.ok ? `write rejected: HTTP ${wrote.status} ${wrote.error}`
      : readBack === probeFormula ? 'BYTE-IDENTICAL — no canonicalisation needed'
        : `NORMALISED — reconciliation must canonicalise.\n    wrote: ${probeFormula}\n    read:  ${readBack}`;
    log(`Round-trip: ${writeResults.roundTrip}`);

    // D — length limit, by binary search on accepted-and-retained length.
    // ~13 write+read pairs, so it logs each step: a silent 30 seconds is
    // indistinguishable from a hang.
    const build = (n) => {
      const head = "=if([$Title] == '";
      const tail = "', 'true', 'false')";
      return head + 'a'.repeat(Math.max(n - head.length - tail.length, 1)) + tail;
    };
    const accepts = async (n) => {
      const f = build(n);
      const w = await setFormula(f);
      if (!w.ok) return { ok: false, why: `HTTP ${w.status} ${w.error}` };
      const rb = await readFormula();
      return rb === f ? { ok: true, len: f.length } : { ok: false, why: 'written but not retained' };
    };
    const floor = await accepts(100);
    if (!floor.ok) {
      writeResults.maxLength = null;
      log(`Length limit: INCONCLUSIVE — even a 100-char formula failed (${floor.why}).`);
    } else {
      let lo = 100; let hi = 8192; let best = floor.len;
      while (lo <= hi) {
        const mid = Math.floor((lo + hi) / 2);
        const r = await accepts(mid);
        log(`  probing ${String(mid).padStart(4)} chars → ${r.ok ? 'accepted' : `rejected (${r.why})`}`);
        if (r.ok) { best = r.len; lo = mid + 1; } else { hi = mid - 1; }
      }
      writeResults.maxLength = best;
      log(`Length limit: longest formula written AND read back intact = ${best} chars`
        + `${best < 1024 ? ' — BELOW the assumed 1024; the spec must be corrected' : ''}`);
    }
    await setFormula('');
    const gone = await post(fieldPath(COL), undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
    log(gone.ok ? `Removed the throwaway column ${COL}.`
      : `Could not remove ${COL} (HTTP ${gone.status} ${gone.error}) — delete it in list settings.`);
  } else {
    rule();
    log('Write tests skipped (ALLOW_WRITES = false). Round-trip fidelity and the '
      + 'length limit cannot be measured read-only.');
  }

  // === CHECKLIST ==========================================================
  rule();
  bold('CHECKLIST — configure these in the UI, then paste this script again');
  say('Each line fills a gap the spec currently guesses at. Use UNSEALED columns:');
  say('a sealed column discards writes silently, so nothing you set will persist.');
  say('');
  say('  1. COLLISION (the blocking one)');
  say('     Pick one column. Set a COLUMN VALIDATION rule on it (list settings ->');
  say('     the column -> Column validation). Re-run: section 3 should show it under');
  say('     ValidationFormula and NOT under ClientValidationFormula.');
  say('  2. Then add CONDITIONAL VISIBILITY to that SAME column. Re-run: it should');
  say('     appear in the BOTH row, proving the two coexist.');
  say('');
  say('  3. DATE operand    — conditional visibility comparing a date column');
  say('  4. PERSON operand  — conditional visibility referencing a person column');
  say('  5. LOOKUP operand  — conditional visibility referencing a lookup column');
  say('  6. OR / nesting    — a formula combining conditions with or()');
  say('  7. AWKWARD VALUE   — a text value containing an apostrophe');
  say('');
  say('Sections 3 and 4 then carry the evidence. Anything still absent stays a');
  say('rejected operand class in the spec — which is the correct outcome, not a gap.');
  rule();
  return { fields: fields.map((f) => f.InternalName), linkOrder, writeResults };
})();
