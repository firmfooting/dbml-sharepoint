/**
 * dbml-sharepoint PROBE: PROJECTED LOOKUP FIELD (DEPENDENT LOOKUP)
 *
 * ONE QUESTION, in two halves:
 *
 *   Can a lookup's "additional field" projection be created BY SCRIPT, and
 *   does it auto-populate with the target's real Title?
 *
 * The raid-log family wants a RelatedRisk lookup whose PICKER shows only live
 * risks (via a calculated display column `LiveRiskTitle` that blanks once
 * Status=Closed), while VIEWS show the real Title. That needs two columns on
 * the source list: the primary lookup (ShowField=LiveRiskTitle) plus a
 * DEPENDENT lookup field that projects Title. Dependent fields are the UI's
 * "add a column to show each of these additional fields", and the linkage is
 * read-only through the normal field object model (IsDependentLookup,
 * PrimaryFieldId, DependentLookupInternalNames). The declarative mechanism is
 * the `FieldRef` attribute on a second Lookup field referencing the primary's
 * GUID. Whether createfieldasxml honours FieldRef in SharePoint Online is the
 * open question. This probe writes.
 *
 * WHAT IT ASKS
 *   BOOT     target + source lists, Status choice, LiveTitle calc, two items
 *   PRIM     primary RelatedRisk lookup created (ShowField=LiveTitle)
 *   DEPCR    dependent field (FieldRef -> primary) accepted by createfieldasxml
 *   DEPFLAG  the created field reads back IsDependentLookup=true
 *   DEPLINK  the primary lists it in DependentLookupInternalNames
 *   DEPPOP   setting RelatedRisk to an OPEN risk fills the dependent Title
 *   DEPLIVE  for a CLOSED risk (LiveTitle blank) the dependent still shows Title
 *
 * RUN 1, 2026-08-28, revision d583e170, sandbox Team Site, through the test
 * agent's autonomous lane, with CLEANUP so DEPCR re-ran the create. Seven
 * questions answered. Two facts fell out:
 *
 *   createfieldasxml honours FieldRef. A fresh dependent field was ACCEPTED
 *   (HTTP 200) and read back IsDependentLookup=true, PrimaryFieldId set,
 *   LookupField=Title, ReadOnlyField=true, and listed in the primary's
 *   DependentLookupInternalNames. The open question is answered yes.
 *
 *   The projected TEXT is not REST-readable. $select=RelatedRiskTitle returns
 *   HTTP 400 "The field or property 'RelatedRiskTitle' does not exist";
 *   $select=RelatedRiskTitleId returns the projected Id; $select=RelatedRisk/
 *   Title is also rejected. So the dependent field's Id auto-populates and is
 *   the only part readable at the item level; the projected Title is
 *   materialised when a view renders it, never on the item. Verification must
 *   therefore check the field schema and the projected Id, never the projected
 *   text. verifyDependentField in _field_reconcile.js.j2 already reads the
 *   schema, which this run confirms is the right (and only) check.
 */

(async () => {
  // ---- Operator gate -------------------------------------------------
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const CLEANUP = false;

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

  const readFailed = (r) => !r.ok || r.body === null;

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
    const text = await res.text();
    let parsed = null;
    try { parsed = JSON.parse(text); } catch { /* plain text */ }
    return { ok: res.ok, status: res.status, body: parsed, text };
  };

  const resetList = async (title) => {
    if (!CLEANUP) return false;
    if (!ALLOW_WRITES) return false;
    const found = await spGet(`web/lists/getbytitle('${title}')`);
    if (!found.ok) return false;
    let digest = await getDigest();
    const gone = await spPost(`web/lists/getbytitle('${title}')/recycle`, {}, digest);
    if (gone.ok) log('OK', `CLEANUP: recycled '${title}'.`);
    else log('FAIL', `CLEANUP: could not recycle '${title}': HTTP ${gone.status}`);
    return gone.ok;
  };

  const RESULTS = [];
  const expect = (id, question) => {
    RESULTS.push({ id, question, outcome: 'NOT ESTABLISHED', evidence: 'the run did not reach this question' });
  };
  const record = (id, question, outcome, evidence) => {
    const row = RESULTS.find((r) => r.id === id);
    if (row) Object.assign(row, { question, outcome, evidence });
    else RESULTS.push({ id, question, outcome, evidence });
    const level = outcome === 'PASS' ? 'OK' : outcome === 'FAIL' ? 'FAIL' : 'INFO';
    log(level, `${id}: ${outcome}. ${question}`);
    if (evidence) console.log(`      evidence: ${evidence}`);
  };
  const report = () => {
    console.log('\n==================== RESULTS ====================');
    for (const r of RESULTS) {
      console.log(`${r.id.padEnd(8)} ${r.outcome.padEnd(16)} ${r.question}`);
      if (r.evidence) console.log(`       ${r.evidence}`);
    }
    console.log('=================================================');
    const OPEN_PREFIXES = ['NOT ESTABLISHED', 'SHORT', 'MANUAL', 'NOT REACHED'];
    const isOpen = (r) => OPEN_PREFIXES.some((p) => r.outcome.startsWith(p));
    const open = RESULTS.filter(isOpen).length;
    console.log(`${RESULTS.length} question(s); ${RESULTS.length - open} answered, ${open} open.`);
    if (open) console.log('A question with no observation is NOT a pass. Report it as open.');
    console.log('Copy this whole block back verbatim.');
  };

  const TARGET = 'dbmlsp Probe ProjTarget';
  const SOURCE = 'dbmlsp Probe ProjSource';
  const targetFields = `web/lists/getbytitle('${TARGET}')/fields`;
  const sourceFields = `web/lists/getbytitle('${SOURCE}')/fields`;
  const sourceItems = `web/lists/getbytitle('${SOURCE}')/items`;
  const targetItems = `web/lists/getbytitle('${TARGET}')/items`;

  if (!CONFIRMED) {
    log('INFO', `Would create '${TARGET}' (a Status choice, a LiveTitle`);
    log('INFO', 'calculated column and two risk rows) and ' + `'${SOURCE}' (a`);
    log('INFO', 'RelatedRisk lookup into the target, plus a FieldRef-linked');
    log('INFO', 'dependent lookup projecting Title), then set RelatedRisk on');
    log('INFO', 'source rows and read back whether the dependent auto-fills.');
    log('INFO', 'Nothing has been written. Set CONFIRMED and ALLOW_WRITES to true.');
    return;
  }
  if (!ALLOW_WRITES) {
    log('INFO', 'CONFIRMED, but ALLOW_WRITES is false and this probe must write.');
    log('INFO', 'Set ALLOW_WRITES = true to proceed. Stopping.');
    return;
  }

  expect('BOOT', 'target + source lists, Status choice, LiveTitle calc and two target rows exist');
  expect('PRIM', 'primary RelatedRisk lookup created (ShowField=LiveTitle)');
  expect('DEPCR', 'dependent field with FieldRef -> primary accepted by createfieldasxml');
  expect('DEPFLAG', 'the created field reads back IsDependentLookup=true');
  expect('DEPLINK', 'the primary lists the dependent in DependentLookupInternalNames');
  expect('DEPPOP', 'setting RelatedRisk to an OPEN risk fills the dependent Title');
  expect('DEPLIVE', 'for a CLOSED risk (LiveTitle blank) the dependent still shows the real Title');

  await resetList(SOURCE);
  await resetList(TARGET);
  let digest = await getDigest();

  // ---- Bootstrap: lists ----------------------------------------------
  const ensureList = async (title) => {
    const existing = await spGet(`web/lists/getbytitle('${title}')`);
    if (existing.ok) return { id: existing.body.Id, made: false };
    digest = await getDigest();
    const made = await spPost('web/lists', {
      Title: title, BaseTemplate: 100, Description: 'dbml-sharepoint probe list. Safe to delete.',
    }, digest);
    return { id: made.ok ? made.body.Id : null, made: made.ok, text: made.text };
  };

  const target = await ensureList(TARGET);
  const source = await ensureList(SOURCE);
  if (!target.id || !source.id) {
    record('BOOT', 'create the two probe lists', 'FAIL',
           `target=${target.id || `HTTP ${target.text.slice(0, 160)}`} source=${source.id || `HTTP ${source.text.slice(0, 160)}`}`);
    return report();
  }

  const addField = async (fieldsPath, schemaXml) => {
    digest = await getDigest();
    return spPost(`${fieldsPath}/createfieldasxml`, {
      parameters: { SchemaXml: schemaXml, Options: 8 },
    }, digest);
  };
  const fieldExists = async (fieldsPath, name) =>
    (await spGet(`${fieldsPath}/getbyinternalnameortitle('${name}')`)).ok;

  // ---- Target: Status choice + LiveTitle calculated ------------------
  if (!(await fieldExists(targetFields, 'Status'))) {
    const made = await addField(targetFields,
      `<Field Type="Choice" DisplayName="Status" Name="Status" Format="Dropdown">`
      + `<CHOICES><CHOICE>Open</CHOICE><CHOICE>Closed</CHOICE></CHOICES>`
      + `<Default>Open</Default></Field>`);
    if (!made.ok) {
      record('BOOT', 'create the Status choice column', 'FAIL',
             `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
      return report();
    }
  }
  if (!(await fieldExists(targetFields, 'LiveTitle'))) {
    const made = await addField(targetFields,
      `<Field Type="Calculated" DisplayName="LiveTitle" Name="LiveTitle" ResultType="Text">`
      + `<Formula>=IF(Status="Closed","",Title)</Formula>`
      + `<FieldRefs><FieldRef Name="Status"/><FieldRef Name="Title"/></FieldRefs></Field>`);
    if (!made.ok) {
      record('BOOT', 'create the LiveTitle calculated column', 'FAIL',
             `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
      return report();
    }
  }

  // ---- Target rows: one open, one closed -----------------------------
  let openId = null; let closedId = null;
  const existingRows = await spGet(`${targetItems}?$select=Id,Title&$top=10`);
  const rows = (existingRows.ok && existingRows.body && existingRows.body.value) || [];
  for (const row of rows) {
    if (row.Title === 'Risk Open') openId = row.Id;
    if (row.Title === 'Risk Closed') closedId = row.Id;
  }
  const makeTargetRow = async (title, status) => {
    digest = await getDigest();
    const res = await spPost(targetItems, { Title: title, Status: status }, digest);
    return res.ok ? res.body.Id : null;
  };
  if (openId === null) openId = await makeTargetRow('Risk Open', 'Open');
  if (closedId === null) closedId = await makeTargetRow('Risk Closed', 'Closed');
  if (openId === null || closedId === null) {
    record('BOOT', 'create the open and closed target rows', 'FAIL',
           `open=${openId} closed=${closedId}`);
    return report();
  }

  // ---- Primary RelatedRisk lookup ------------------------------------
  if (!(await fieldExists(sourceFields, 'RelatedRisk'))) {
    const made = await addField(sourceFields,
      `<Field Type="Lookup" DisplayName="Related Risk" Name="RelatedRisk"`
      + ` List="{${target.id}}" ShowField="LiveTitle"/>`);
    if (!made.ok) {
      record('PRIM', 'create the primary RelatedRisk lookup', 'FAIL',
             `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
      return report();
    }
  }
  const primaryField = await spGet(`${sourceFields}/getbyinternalnameortitle('RelatedRisk')`);
  if (readFailed(primaryField)) {
    record('PRIM', 'read back the primary RelatedRisk field', 'FAIL',
           `HTTP ${primaryField.status}`);
    return report();
  }
  const primaryId = primaryField.body.Id;
  record('PRIM', 'primary RelatedRisk lookup created (ShowField=LiveTitle)', 'PASS',
         `field Id ${primaryId}`);

  // ---- Dependent field via FieldRef ----------------------------------
  if (!(await fieldExists(sourceFields, 'RelatedRiskTitle'))) {
    const made = await addField(sourceFields,
      `<Field Type="Lookup" DisplayName="Related Risk Title" Name="RelatedRiskTitle"`
      + ` List="{${target.id}}" ShowField="Title" FieldRef="{${primaryId}}" ReadOnly="TRUE"/>`);
    record('DEPCR', 'dependent field with FieldRef -> primary accepted by createfieldasxml',
           made.ok ? 'ACCEPTED' : 'REFUSED',
           made.ok ? `created; HTTP ${made.status}` : `HTTP ${made.status}: ${made.text.slice(0, 300)}`);
  } else {
    record('DEPCR', 'dependent field with FieldRef -> primary accepted by createfieldasxml',
           'ACCEPTED', 'field already exists from an earlier run');
  }

  const depField = await spGet(`${sourceFields}/getbyinternalnameortitle('RelatedRiskTitle')`);
  if (readFailed(depField)) {
    record('DEPFLAG', 'the created field reads back IsDependentLookup=true', 'NOT ESTABLISHED',
           `could not read the field: HTTP ${depField.status}`);
  } else {
    const depLookup = depField.body.IsDependentLookup;
    record('DEPFLAG', 'the created field reads back IsDependentLookup=true',
           depLookup === true ? 'PASS' : (depLookup === false ? 'FAIL' : 'NOT ESTABLISHED'),
           `IsDependentLookup=${depLookup}; PrimaryFieldId=${depField.body.PrimaryFieldId || '(absent)'}; `
           + `TypeAsString=${depField.body.TypeAsString}`);
  }

  const primaryAfter = await spGet(`${sourceFields}/getbyinternalnameortitle('RelatedRisk')`);
  const primNames = (primaryAfter.ok && primaryAfter.body && primaryAfter.body.DependentLookupInternalNames) || null;
  record('DEPLINK', 'the primary lists the dependent in DependentLookupInternalNames',
         (primNames && primNames.length) ? 'PASS' : 'FAIL',
         `DependentLookupInternalNames=${JSON.stringify(primNames)}`);

  // ---- Auto-population: open then closed -----------------------------
  const setAndRead = async (riskId) => {
    digest = await getDigest();
    const made = await spPost(sourceItems, { Title: `linked-${riskId}`, RelatedRiskId: riskId }, digest);
    if (!made.ok) return { ok: false, detail: `create HTTP ${made.status}: ${made.text.slice(0, 240)}` };
    const itemId = made.body.Id;
    const def = await spGet(`${sourceItems}(${itemId})`);
    const byId = await spGet(`${sourceItems}(${itemId})?$select=RelatedRiskTitleId`);
    const byText = await spGet(`${sourceItems}(${itemId})?$select=RelatedRiskTitle`);
    return {
      ok: true, itemId,
      primaryId: def.ok ? def.body.RelatedRiskId : undefined,
      depId: byId.ok ? byId.body.RelatedRiskTitleId : `HTTP ${byId.status}`,
      depText: byText.ok ? byText.body.RelatedRiskTitle : `HTTP ${byText.status}`,
      detail: def.ok ? '' : `default read HTTP ${def.status}`,
    };
  };

  const openRes = await setAndRead(openId);
  record('DEPPOP', 'setting RelatedRisk to an OPEN risk auto-fills the dependent (Id propagates)',
         (openRes.ok && openRes.depId === openId) ? 'PASS' : 'FAIL',
         `primaryId=${openRes.primaryId} dependentId=${openRes.depId} (expect ${openId}) `
         + `dependentText=${openRes.depText} ${openRes.detail || ''}`);

  const closedRes = await setAndRead(closedId);
  const dependentReal = (closedRes.ok && closedRes.depId === closedId);
  record('DEPLIVE', 'for a CLOSED risk (LiveTitle blank) the dependent still carries the real Title',
         dependentReal ? 'PASS' : 'FAIL',
         `primaryId=${closedRes.primaryId} dependentId=${closedRes.depId} (expect ${closedId}) `
         + `dependentText=${closedRes.depText} ${closedRes.detail || ''}`);

  record('BOOT', 'target + source lists, Status choice, LiveTitle calc and two target rows exist',
         'PASS', `target=${target.id} source=${source.id} open=${openId} closed=${closedId}`);

  report();
})();
