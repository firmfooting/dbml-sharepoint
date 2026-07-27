/**
 * dbml-sharepoint FORM ORDER + CONDITIONAL VISIBILITY PROBE (READ-ONLY)
 *
 * Two questions the earlier probes did not cover:
 *
 *   1. FIELD ORDER. Where does the order of fields on a form come from,
 *      and does hiding/showing a column move it? The deployer controls
 *      VIEW field order (CAML FieldRefs) but does nothing about FORM
 *      order today, so if the order is volatile that is undetected drift.
 *
 *   2. CONDITIONAL VISIBILITY. The modern form's "show/hide column based
 *      on other columns" formula (e.g. =true()) is persisted SOMEWHERE.
 *      Until we know where, a form_visibility feature could silently
 *      fight with it, or clobber it on redeploy.
 *
 * MAKES NO CHANGES. Every request is a GET.
 *
 * HOW TO USE
 *   Run it against a list where you have ALREADY set a conditional
 *   visibility formula on at least one column, leaving another column
 *   without one. It dumps every candidate store for both, so whichever
 *   one differs is the answer.
 *
 *   1. Set PROBE_LIST to that list's title.
 *   2. Open the site's /_layouts/15/settings.aspx as a Site Owner.
 *   3. F12 -> Console -> paste -> Enter.
 *   4. It prints the web and stops; set CONFIRMED = true and paste again.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const PROBE_LIST = 'zzz dbmlsp form visibility interactive';
  // Columns to compare. Put the one WITH a conditional formula first.
  const WITH_FORMULA = 'SealedF';
  const WITHOUT_FORMULA = 'Ctl';
  // ------------------------------------------------------------------------

  const log = (m) => console.log(`%c[ORDER] ${m}`, 'color:#0a7');
  const say = (m) => console.log(m);
  const rule = () => console.log('%c' + '─'.repeat(66), 'color:#888');
  const bold = (m) => console.log(`%c${m}`, 'font-weight:bold;font-size:13px');

  if (typeof _spPageContextInfo === 'undefined') {
    console.error('[ORDER] _spPageContextInfo unavailable. Open /_layouts/15/settings.aspx and retry.');
    return { aborted: 'no-sp-page-context' };
  }
  const actPath = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (!CONFIRMED) {
    console.error(`[ORDER] Read-only probe against:  ${window.location.origin}${actPath}`);
    console.error('[ORDER] If that is right, set CONFIRMED = true at the top and paste again.');
    return { aborted: 'not-confirmed' };
  }
  const WEB = actPath;
  const apiUrl = (s) => `${WEB}/_api/${s}`;
  const odataName = (n) => encodeURIComponent(String(n).replace(/'/g, "''"));
  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;

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

  if (!(await get(`${listPath}?$select=Title`)).ok) {
    console.error(`[ORDER] List '${PROBE_LIST}' not found. Set PROBE_LIST at the top.`);
    return { aborted: 'no-list' };
  }

  // === 1. FIELD ORDER, from every source that could define it ============
  rule();
  bold('1 — FIELD ORDER');

  // (a) The list's field collection order.
  const fieldsResp = await get(`${listPath}/fields?$select=InternalName,Title,Hidden,ReadOnlyField&$top=500`);
  const listOrder = fieldsResp.ok
    ? (fieldsResp.d.results || []).filter((f) => !f.Hidden && !f.ReadOnlyField).map((f) => f.InternalName)
    : [];

  // (b) The content type's FieldLink order — this is what the form follows
  //     unless a form customizer overrides it.
  const ctResp = await get(`${listPath}/contenttypes?$select=Name,StringId,SchemaXml,ClientFormCustomFormatter`);
  const cts = ctResp.ok ? (ctResp.d.results || []).filter((c) => c.Name !== 'Folder') : [];
  const perCt = [];
  for (const ct of cts) {
    const links = await get(`${listPath}/contenttypes('${encodeURIComponent(ct.StringId)}')/fieldlinks?$select=Name,Id,Hidden,Required&$top=500`);
    const linkOrder = links.ok ? (links.d.results || []).map((l) => l.Name) : [];
    const xmlRefs = [...new DOMParser().parseFromString(String(ct.SchemaXml || '<x/>'), 'application/xml')
      .getElementsByTagName('FieldRef')].map((e) => e.getAttribute('Name'));
    perCt.push({ ct, linkOrder, xmlRefs, links: links.ok ? links.d.results || [] : [] });
  }

  say('List field collection order (visible, writable):');
  say(`  ${listOrder.join(' → ') || '(none)'}`);
  for (const p of perCt) {
    say(`Content type '${p.ct.Name}' FieldLink order:`);
    say(`  ${p.linkOrder.join(' → ') || '(none)'}`);
    say(`Content type '${p.ct.Name}' SchemaXml <FieldRef> order:`);
    say(`  ${p.xmlRefs.join(' → ') || '(none)'}`);
    const sameAsList = JSON.stringify(p.linkOrder.filter((n) => listOrder.includes(n))) === JSON.stringify(listOrder.filter((n) => p.linkOrder.includes(n)));
    log(`FieldLink order ${sameAsList ? 'MATCHES' : 'DIFFERS FROM'} the list field order.`);
  }
  log('The form follows the CONTENT TYPE FieldLink order unless a form '
    + 'customizer (ClientFormCustomFormatter body sections) overrides it. '
    + 'If that order is not what you see on the form, the customizer is winning.');

  // === 2. CONDITIONAL VISIBILITY — where is it stored? ===================
  rule();
  bold('2 — CONDITIONAL VISIBILITY: which store differs?');
  say(`Comparing  ${WITH_FORMULA}  (has a formula)  vs  ${WITHOUT_FORMULA}  (has none).`);

  const FIELD_PROPS = [
    'InternalName', 'Title', 'Sealed', 'Hidden', 'SchemaXml', 'CustomFormatter',
    'ClientValidationFormula', 'ClientValidationMessage',
    'ClientSideComponentId', 'ClientSideComponentProperties',
  ];
  const dumpField = async (name) => {
    const r = await get(`${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')?$select=${FIELD_PROPS.join(',')}`);
    return r.ok ? r.d : { error: `HTTP ${r.status} ${r.error}` };
  };
  const a = await dumpField(WITH_FORMULA);
  const b = await dumpField(WITHOUT_FORMULA);

  const rows = [];
  for (const k of FIELD_PROPS) {
    const av = a[k] === undefined || a[k] === null ? '' : String(a[k]);
    const bv = b[k] === undefined || b[k] === null ? '' : String(b[k]);
    rows.push({
      property: k,
      [WITH_FORMULA]: av.length > 90 ? `${av.slice(0, 90)}…` : av,
      [WITHOUT_FORMULA]: bv.length > 90 ? `${bv.slice(0, 90)}…` : bv,
      DIFFERS: av === bv ? '' : '◄ HERE',
    });
  }
  console.table(rows);

  // FieldLink-level properties, per content type.
  for (const p of perCt) {
    const la = p.links.find((l) => l.Name === WITH_FORMULA);
    const lb = p.links.find((l) => l.Name === WITHOUT_FORMULA);
    if (!la && !lb) continue;
    log(`FieldLink on '${p.ct.Name}':  ${WITH_FORMULA} = ${JSON.stringify(la || null)}`);
    log(`FieldLink on '${p.ct.Name}':  ${WITHOUT_FORMULA} = ${JSON.stringify(lb || null)}`);
  }

  // The form customizer JSON — the most likely home.
  rule();
  for (const p of perCt) {
    const f = p.ct.ClientFormCustomFormatter;
    if (!f) { log(`Content type '${p.ct.Name}': no ClientFormCustomFormatter.`); continue; }
    log(`Content type '${p.ct.Name}' ClientFormCustomFormatter (${String(f).length} chars):`);
    try { console.log(JSON.stringify(JSON.parse(f), null, 2)); } catch { console.log(f); }
    for (const n of [WITH_FORMULA, WITHOUT_FORMULA]) {
      log(`  mentions ${n}: ${String(f).includes(n) ? 'YES' : 'no'}`);
    }
  }

  rule();
  log('Read the DIFFERS column: whichever property differs between the two '
    + 'columns is where the conditional formula lives. If nothing differs at '
    + 'field level, it is in the content type ClientFormCustomFormatter above.');
  return { listOrder, contentTypes: perCt.map((p) => ({ name: p.ct.Name, linkOrder: p.linkOrder })) };
})();
