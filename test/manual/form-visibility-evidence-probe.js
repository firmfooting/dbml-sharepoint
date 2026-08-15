/**
 * dbml-sharepoint FORM VISIBILITY: EVIDENCE PROBE
 *
 * Captures everything the form_visibility spec still needs verified.
 * Supersedes form-order-conditional-probe.js (field order + which store
 * holds the conditional formula), and adds the open questions:
 *
 *   A. COLLISION: does SharePoint's modern COLUMN VALIDATION UI write
 *      ClientValidationFormula? If it does, this design would silently
 *      destroy validation rules and the mechanism needs rethinking. This
 *      is the one risk that invalidates rather than adjusts the design.
 *   B. CANONICAL SYNTAX: what exact expression does SharePoint itself
 *      generate for dates, people, lookups, OR, nesting and awkward
 *      values? The spec rejects those operands today because their
 *      projection is unverified. Reading back what the UI writes is how
 *      that restriction gets lifted with evidence instead of guesswork.
 *   C. ROUND-TRIP FIDELITY: is a written formula read back byte-identical
 *      or normalised? Decides whether reconciliation needs
 *      canonicalisation, as the calculated-formula comparison already does.
 *   D. LENGTH LIMIT: the real ceiling for ClientValidationFormula. The
 *      spec assumes 1024 by analogy; assumptions in formula limits have
 *      already bitten once.
 *
 * SELF-CONTAINED. With ALLOW_WRITES on it builds its own list, the
 * visibility matrix and the typed columns the checklist references, so no
 * other script is needed. Every bootstrap step checks first, so re-running
 * adds what is missing rather than rebuilding. Analysis (A, B) is read-only
 * once the list exists; the write tests (C, D) need ALLOW_WRITES.
 *
 * HOW TO RUN
 *   1. Open the target site's /_layouts/15/settings.aspx as a Site Owner.
 *   2. F12 -> Console -> paste -> Enter. It prints the web and stops.
 *   3. Set CONFIRMED = true and ALLOW_WRITES = true, paste again. It builds
 *      the list and prints the CHECKLIST.
 *   4. Work through the checklist in the SharePoint UI.
 *   5. Paste again to harvest. ALLOW_WRITES can go back to false for this,
 *      because sections 1-4 only read.
 *
 * WHEN FINISHED: delete the list in the UI. Everything lives in it.
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

  // === 0. Bootstrap =======================================================
  // Self-contained: builds the list, the visibility matrix and the typed
  // columns the checklist references. Safe to re-run, because every step checks
  // first, so an existing list is added to rather than rebuilt.
  const listExists = async () => (await get(`${listPath}?$select=Title`)).ok;
  const existedAtStart = await listExists();
  if (!existedAtStart && !ALLOW_WRITES) {
    console.error(`[EVIDENCE] List '${PROBE_LIST}' does not exist and ALLOW_WRITES is false.`);
    console.error('[EVIDENCE] Set ALLOW_WRITES = true and this script will build it, or point');
    console.error('[EVIDENCE] PROBE_LIST at a list you already have.');
    return { aborted: 'no-list' };
  }

  if (ALLOW_WRITES) {
    rule();
    bold('0. BOOTSTRAP');
    if (!existedAtStart) {
      const made = await post('web/lists', {
        __metadata: { type: 'SP.List' }, BaseTemplate: 100, Title: PROBE_LIST,
        Description: 'Throwaway list from dbml-sharepoint form-visibility-evidence-probe.js. Safe to delete.',
      });
      if (!made.ok) {
        console.error(`[EVIDENCE] Could not create the list: HTTP ${made.status} ${made.error}`);
        return { aborted: 'list-create-failed' };
      }
      log(`Created list '${PROBE_LIST}'.`);
    } else {
      log(`List '${PROBE_LIST}' already exists, adding anything missing.`);
    }

    const seen = await get(`${listPath}/fields?$select=InternalName&$top=500`);
    const have = new Set((seen.ok ? seen.d.results || [] : []).map((f) => f.InternalName));
    const listId = (await get(`${listPath}?$select=Id`)).d?.Id;
    const made = [];
    const addField = async (name, body) => {
      if (have.has(name)) return;
      const r = await post(`${listPath}/fields`, body);
      made.push(`${name}${r.ok ? '' : ` (FAILED HTTP ${r.status} ${r.error})`}`);
    };
    const addXml = async (name, xml) => {
      if (have.has(name)) return;
      const r = await post(`${listPath}/fields/createfieldasxml`, {
        parameters: { __metadata: { type: 'SP.XmlSchemaFieldCreationInformation' }, SchemaXml: xml, Options: 9 },
      });
      made.push(`${name}${r.ok ? '' : ` (FAILED HTTP ${r.status} ${r.error})`}`);
    };
    const text = (n) => ({ __metadata: { type: 'SP.Field' }, FieldTypeKind: 2, Title: n });

    // The visibility matrix, holders for the checklist's formulas.
    for (const n of ['Ctl', 'NewOff', 'EditOff', 'DispOff', 'BothWay', 'SealedF']) await addField(n, text(n));
    await addXml('DeclOff', "<Field Type='Text' DisplayName='DeclOff' Name='DeclOff' ShowInNewForm='FALSE'/>");
    await addXml('Calc', "<Field Type='Calculated' DisplayName='Calc' Name='Calc' ResultType='Number' ReadOnly='TRUE'><Formula>=1+1</Formula></Field>");

    // Typed columns, seeded only to be REFERENCED by the checklist's
    // formulas. The matrix is all Text, so without these there is nothing
    // to write a date, person or lookup condition against.
    await addField('ZZDate', { __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: 'ZZDate' });
    await addField('ZZNumber', { __metadata: { type: 'SP.FieldNumber' }, FieldTypeKind: 9, Title: 'ZZNumber' });
    await addField('ZZPerson', { __metadata: { type: 'SP.FieldUser' }, FieldTypeKind: 20, Title: 'ZZPerson' });
    await addField('ZZChoice', {
      __metadata: { type: 'SP.FieldChoice' }, FieldTypeKind: 6, Title: 'ZZChoice',
      Choices: { results: ['Normal', "O'Brien"] },
    });
    if (listId) {
      // Self-lookup: a target without a second list to create or clean up.
      await addXml('ZZLookup', `<Field Type='Lookup' DisplayName='ZZLookup' Name='ZZLookup' List='{${String(listId).replace(/[{}]/g, '')}}' ShowField='Title'/>`);
    }
    log(made.length ? `Added: ${made.join(', ')}` : 'All expected columns already present.');

    // SchemaXml visibility states, so the matrix means something. Idempotent.
    const setVis = (n, m, v) => post(`${fieldPath(n)}/${m}(${v})`);
    await setVis('NewOff', 'setshowinnewform', false);
    await setVis('BothWay', 'setshowinnewform', false);
    await setVis('EditOff', 'setshowineditform', false);
    await setVis('DispOff', 'setshowindisplayform', false);
    // Seal LAST: a sealed field discards later writes silently.
    await post(fieldPath('SealedF'), { __metadata: { type: 'SP.Field' }, Sealed: true },
      { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    log('Applied the visibility matrix and sealed SealedF.');

    // One item, so the Edit and Display forms are reachable.
    const items = await get(`${listPath}/items?$select=Id&$top=1`);
    if (items.ok && !(items.d.results || []).length) {
      const et = await get(`${listPath}?$select=ListItemEntityTypeFullName`);
      if (et.ok) {
        await post(`${listPath}/items`, { __metadata: { type: et.d.ListItemEntityTypeFullName }, Title: 'probe row' });
        log('Created one item so the Edit and Display forms are reachable.');
      }
    }
    const base = `${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`;
    say(`  NEW form      ${base}/NewForm.aspx`);
    say(`  EDIT form     ${base}/EditForm.aspx?ID=1`);
    say(`  DISPLAY form  ${base}/DispForm.aspx?ID=1`);
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
  // definition of "a column on this form". A name-prefix denylist is not.
  // An earlier version of this probe used one and the table came back with
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
    log(`Showing ${fields.length} of ${all.length} fields, the rest are list plumbing `
      + 'the content type does not link.');
  }

  // === 1. Field order =====================================================
  rule();
  bold('1. FIELD ORDER');
  say('List field collection:');
  say(`  ${fields.map((f) => f.InternalName).join(' → ')}`);
  say('Content type FieldLink order (what the form follows, absent body sections):');
  say(`  ${linkOrder.join(' → ')}`);

  // === 2. The full store map ==============================================
  rule();
  bold('2. STORE MAP  (every property that could hold visibility or validation)');
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
  bold('3. COLLISION: does column VALIDATION write ClientValidationFormula?');
  const withVal = fields.filter((f) => f.ValidationFormula);
  const withClient = fields.filter((f) => f.ClientValidationFormula);
  const withBoth = fields.filter((f) => f.ValidationFormula && f.ClientValidationFormula);
  log(`columns with ValidationFormula (column validation):      ${withVal.map((f) => f.InternalName).join(', ') || '(none)'}`);
  log(`columns with ClientValidationFormula (conditional vis):  ${withClient.map((f) => f.InternalName).join(', ') || '(none)'}`);
  log(`columns with BOTH:                                       ${withBoth.map((f) => f.InternalName).join(', ') || '(none)'}`);
  if (!withVal.length) {
    log('VERDICT: inconclusive, no column has a validation rule yet. See the CHECKLIST.');
  } else if (withBoth.length) {
    log('VERDICT: SAFE. A column holds validation and conditional visibility SIMULTANEOUSLY '
      + 'in two different properties. They do not collide.');
  } else {
    const valOnly = withVal.filter((f) => !f.ClientValidationFormula);
    log(valOnly.length
      ? 'VERDICT: LIKELY SAFE. Validation lands in ValidationFormula and left '
        + 'ClientValidationFormula empty. Confirm by adding conditional visibility to that '
        + 'same column and re-running (the BOTH row should then be populated).'
      : 'VERDICT: DANGER. Validation appears to have written ClientValidationFormula. '
        + 'STOP: the form_visibility mechanism would destroy validation rules.');
  }

  // === 4. Canonical syntax harvest =======================================
  rule();
  bold('4. CANONICAL SYNTAX  (what SharePoint itself generates)');
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
    bold('5. WRITE TESTS  (round-trip fidelity and length limit)')

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

    // C: round-trip fidelity.
    const probeFormula = "=if(and([$Title] != '', [$Title] != 'x'), 'true', 'false')";
    const wrote = await setFormula(probeFormula);
    const readBack = wrote.ok ? await readFormula() : null;
    writeResults.roundTrip = !wrote.ok ? `write rejected: HTTP ${wrote.status} ${wrote.error}`
      : readBack === probeFormula ? 'BYTE-IDENTICAL, no canonicalisation needed'
        : `NORMALISED, reconciliation must canonicalise.\n    wrote: ${probeFormula}\n    read:  ${readBack}`;
    log(`Round-trip: ${writeResults.roundTrip}`);

    // D: length limit, by binary search on accepted-and-retained length.
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
      log(`Length limit: INCONCLUSIVE, even a 100-char formula failed (${floor.why}).`);
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
        + `${best < 1024 ? ', BELOW the assumed 1024; the spec must be corrected' : ''}`);
    }
    await setFormula('');
    const gone = await post(fieldPath(COL), undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
    log(gone.ok ? `Removed the throwaway column ${COL}.`
      : `Could not remove ${COL} (HTTP ${gone.status} ${gone.error}). Delete it in list settings.`);
  } else {
    rule();
    log('Write tests skipped (ALLOW_WRITES = false). Round-trip fidelity and the '
      + 'length limit cannot be measured read-only.');
  }

  // === CHECKLIST ==========================================================
  rule();
  bold('CHECKLIST: exactly what to set, and where');
  say('');
  say('Never use SealedF. A sealed column accepts the write, reports success and');
  say('discards it, so anything you configure there measures nothing.');
  say('');
  console.log('%cWHERE THE TWO DIALOGS LIVE', 'font-weight:bold');
  say('  COLUMN VALIDATION:   gear icon -> List settings -> click the column name');
  say('                       -> "Column Validation" -> Formula + User message -> OK');
  say('  CONDITIONAL VISIBILITY:  open any item -> Edit all -> "Edit form" (top');
  say('                       right) -> "Edit columns" -> hover the column -> the');
  say('                       "..." -> "Edit conditional formula" -> paste -> Save');
  say('');
  say('The conditional formula box VALIDATES as you save. A rejection is itself a');
  say('result worth reporting: it tells us that operand class is unusable.');
  say('');
  console.log('%cSTEP 1: THE BLOCKING TEST (do this one first)', 'font-weight:bold;color:#c30');
  say('  1a. Column VALIDATION on  Ctl');
  console.log("%c        =[Ctl] <> 'forbidden'", 'color:#06c');
  say('      Message: anything, e.g.  no');
  say('      Re-run this script. Section 3 must show Ctl under ValidationFormula');
  say('      and NOT under ClientValidationFormula.');
  say('');
  say('  1b. Then CONDITIONAL VISIBILITY on the SAME column  Ctl');
  console.log("%c        =if([$Title] != '', 'true', 'false')", 'color:#06c');
  say('      Re-run. Ctl must now appear in the BOTH row. That is the proof the two');
  say('      features occupy different properties and cannot destroy each other.');
  say('');
  console.log('%cSTEP 2: CANONICAL SYNTAX (one holder column each)', 'font-weight:bold');
  say('  Set CONDITIONAL VISIBILITY on each holder below, pasting the formula shown.');
  say('  Each references one of the ZZ* columns seeded in section 5.');
  say('');
  say('  DispOff:    DATE operand');
  console.log("%c        =if([$ZZDate] > '2026-01-01', 'true', 'false')", 'color:#06c');
  say('      If rejected, try:');
  console.log("%c        =if(Number([$ZZDate]) > Number('2026-01-01'), 'true', 'false')", 'color:#06c');
  say('');
  say('  EditOff:    PERSON operand');
  console.log("%c        =if([$ZZPerson.title] != '', 'true', 'false')", 'color:#06c');
  say('      If rejected, try  [$ZZPerson.email]  or bare  [$ZZPerson]');
  say('');
  say('  NewOff:     LOOKUP operand');
  console.log("%c        =if([$ZZLookup.lookupValue] != '', 'true', 'false')", 'color:#06c');
  say('      If rejected, try  [$ZZLookup.lookupId]  or bare  [$ZZLookup]');
  say('');
  say("  BothWay:    APOSTROPHE in a value (ZZChoice offers Normal and O'Brien)");
  console.log("%c        =if([$ZZChoice] == 'O''Brien', 'true', 'false')", 'color:#06c');
  say("      If rejected, try a backslash:  'O\\'Brien'");
  say('      This decides how the tool must escape apostrophes, or whether it must');
  say('      keep refusing them.');
  say('');
  say('  DeclOff:    OR and NESTING');
  console.log("%c        =if(or([$Title] == 'x', and([$ZZNumber] > 5, [$Ctl] != '')), 'true', 'false')",
    'color:#06c');
  say('      Confirms and()/or() nest, which the shared condition grammar assumes.');
  say('');
  say('Then paste this script again. Section 4 prints each stored formula verbatim.');
  say('Anything you could not set stays a rejected operand class in the spec, and');
  say('that is a correct, evidenced outcome, not a gap.');
  rule();
  return { fields: fields.map((f) => f.InternalName), linkOrder, writeResults };
})();
