/**
 * dbml-sharepoint FORM VISIBILITY STORAGE PROBE (READ-ONLY).
 *
 * Companion to form-visibility-probe.js. That probe established what the
 * SetShowIn*Form API does to a field's SchemaXml. This one answers a
 * different and more awkward question:
 *
 *   When you hide a column using the modern list UI
 *   ("Edit form" -> "Edit columns"), WHERE does SharePoint record it?
 *
 * It is not the field's SchemaXml — a sealed field, which the API refuses
 * to modify, can still be hidden through that panel, and the field's
 * SchemaXml comes back unchanged afterwards. So there is a second store,
 * and anything that reconciles form visibility has to know about it or it
 * is reconciling a value nobody is reading.
 *
 * Candidate stores, all dumped below for every Probe* column:
 *   1. Field.SchemaXml            <Field ... ShowInNewForm="FALSE">
 *   2. ContentType.SchemaXml      <FieldRef ... ShowInNewForm="FALSE">
 *   3. FieldLink.Hidden           per-content-type field link
 *   4. ContentType.ClientFormCustomFormatter  the modern form's own JSON
 *
 * MAKES NO CHANGES. Every request is a GET.
 *
 * HOW TO RUN
 *   1. Run form-visibility-probe.js first with CLEANUP = false.
 *   2. In the list UI, hide some columns via Edit form -> Edit columns.
 *   3. Set SITE_URL below, paste this on the site's
 *      /_layouts/15/settings.aspx page.
 *   4. Read the STORAGE table: for each column it shows what each of the
 *      four stores claims, so the one the UI actually wrote is obvious.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const SITE_URL = '';   // REQUIRED, same site the probe list lives on
  const PROBE_LIST = 'zzz dbmlsp form visibility probe';
  // ------------------------------------------------------------------------

  const log = (level, msg) => console.log(`[SP-STORE] [${level}] ${msg}`);

  if (!SITE_URL) {
    const guess = (typeof _spPageContextInfo !== 'undefined')
      ? `${window.location.origin}${_spPageContextInfo.webServerRelativeUrl || ''}`
      : '(could not detect)';
    log('ERROR', `Set SITE_URL at the top of this script first. This web looks like: ${guess}`);
    return { aborted: 'site-url-unset' };
  }
  if (typeof _spPageContextInfo === 'undefined') {
    log('ERROR', '_spPageContextInfo is not available on this page. Open /_layouts/15/settings.aspx and retry.');
    return { aborted: 'no-sp-page-context' };
  }
  const expectedOrigin = new URL(SITE_URL).origin;
  const expectedPath = new URL(SITE_URL).pathname.replace(/\/$/, '');
  const actualPath = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (window.location.origin !== expectedOrigin || actualPath !== expectedPath) {
    log('ERROR', `Site mismatch. Expected ${expectedOrigin}${expectedPath}, found ${window.location.origin}${actualPath}.`);
    return { aborted: 'site-mismatch' };
  }
  const WEB = actualPath;
  const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  log('INFO', `Read-only. Running as ${_spPageContextInfo.userLoginName || '(unknown)'} on web '${WEB || '(root)'}'.`);

  async function get(suffix) {
    const r = await fetch(apiUrl(suffix), { headers: { 'Accept': 'application/json;odata=verbose' } });
    if (!r.ok) {
      let detail = '';
      try { detail = JSON.parse(await r.text())?.error?.message?.value || ''; } catch { /* ignore */ }
      return { ok: false, status: r.status, error: detail };
    }
    const j = await r.json();
    return { ok: true, d: (j && j.d !== undefined) ? j.d : j };
  }

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const listCheck = await get(`${listPath}?$select=Title`);
  if (!listCheck.ok) {
    log('ERROR', `Probe list '${PROBE_LIST}' not found (HTTP ${listCheck.status}). Run form-visibility-probe.js with CLEANUP = false first.`);
    return { aborted: 'no-probe-list' };
  }

  // Attribute readers. DOMParser rather than regex: these are real XML
  // documents and attribute order/spacing is not guaranteed.
  const parseXml = (xml) => new DOMParser().parseFromString(String(xml || '<Field/>'), 'application/xml');
  const visFromAttrs = (el) => {
    if (!el) return null;
    const attr = (n) => (el.getAttribute(n) || '').toUpperCase();
    return {
      new: attr('ShowInNewForm') === 'FALSE' ? 'HIDDEN' : 'shown',
      edit: attr('ShowInEditForm') === 'FALSE' ? 'HIDDEN' : 'shown',
      display: attr('ShowInDisplayForm') === 'FALSE' ? 'HIDDEN' : 'shown',
    };
  };
  const fmt = (v) => (v ? `new=${v.new} edit=${v.edit} display=${v.display}` : '(not present)');

  // === Store 1: each field's own SchemaXml ===
  const fieldsResp = await get(`${listPath}/fields?$select=InternalName,Title,Sealed,Hidden,SchemaXml&$top=500`);
  if (!fieldsResp.ok) {
    log('ERROR', `Could not read fields: HTTP ${fieldsResp.status} ${fieldsResp.error}`);
    return { aborted: 'fields-read-failed' };
  }
  const allFields = fieldsResp.d.results || [];
  const probeFields = allFields.filter((f) => /^Probe/i.test(f.InternalName) || f.InternalName === 'Title');
  const fieldSchema = new Map();
  for (const f of probeFields) {
    const el = parseXml(f.SchemaXml).documentElement;
    fieldSchema.set(f.InternalName, { vis: visFromAttrs(el), sealed: !!f.Sealed, hidden: !!f.Hidden });
  }

  // === Stores 2-4: the list's content types ===
  const ctResp = await get(`${listPath}/contenttypes?$select=Name,StringId,SchemaXml,ClientFormCustomFormatter`);
  if (!ctResp.ok) {
    log('ERROR', `Could not read content types: HTTP ${ctResp.status} ${ctResp.error}`);
    return { aborted: 'ct-read-failed' };
  }
  const contentTypes = ctResp.d.results || [];
  log('INFO', `List has ${contentTypes.length} content type(s): ${contentTypes.map((c) => c.Name).join(', ')}.`);

  const ctFieldRef = new Map();   // internalName -> vis, from ContentType.SchemaXml FieldRefs
  const fieldLinkInfo = new Map(); // internalName -> {hidden, required, showInDisplayForm}
  let formatterText = '';

  for (const ct of contentTypes) {
    for (const ref of parseXml(ct.SchemaXml).getElementsByTagName('FieldRef')) {
      const name = ref.getAttribute('Name');
      if (name && !ctFieldRef.has(name)) {
        ctFieldRef.set(name, { ...visFromAttrs(ref), ctHidden: (ref.getAttribute('Hidden') || '').toUpperCase() === 'TRUE' });
      }
    }
    if (ct.ClientFormCustomFormatter) formatterText += String(ct.ClientFormCustomFormatter);

    const links = await get(`${listPath}/contenttypes('${encodeURIComponent(ct.StringId)}')/fieldlinks?$select=Name,Hidden,Required,ShowInDisplayForm&$top=500`);
    if (links.ok) {
      for (const l of (links.d.results || [])) {
        if (!fieldLinkInfo.has(l.Name)) {
          fieldLinkInfo.set(l.Name, {
            hidden: l.Hidden === true,
            required: l.Required === true,
            showInDisplayForm: l.ShowInDisplayForm,
          });
        }
      }
    } else {
      log('WARN', `Could not read fieldlinks for '${ct.Name}': HTTP ${links.status} ${links.error}`);
    }
  }

  // === The comparison ===
  const rows = [];
  for (const f of probeFields) {
    const n = f.InternalName;
    const fs = fieldSchema.get(n) || {};
    const cr = ctFieldRef.get(n);
    const fl = fieldLinkInfo.get(n);
    rows.push({
      column: n,
      sealed: fs.sealed ? 'YES' : '',
      '1. Field.SchemaXml': fmt(fs.vis),
      '2. ContentType FieldRef': cr ? `${fmt(cr)}${cr.ctHidden ? ' +Hidden' : ''}` : '(no FieldRef)',
      '3. FieldLink.Hidden': fl ? (fl.hidden ? 'HIDDEN' : 'shown') : '(no FieldLink)',
      '4. in form formatter JSON': formatterText.includes(n) ? 'mentioned' : '',
    });
  }
  console.table(rows);

  log('INFO', `Form formatter JSON present on a content type: ${formatterText ? `YES (${formatterText.length} chars)` : 'no'}`);
  if (formatterText) {
    log('INFO', 'Formatter JSON follows — look for a fields/sections/fieldsettings block naming the hidden columns:');
    try {
      console.log(JSON.stringify(JSON.parse(formatterText), null, 2));
    } catch {
      console.log(formatterText);
    }
  }

  log('DONE', [
    'Read the table left to right for a column you hid in the UI.',
    'Whichever of stores 1-4 changed is where the modern form panel writes,',
    'and that is the store any form_visibility reconciliation must read.',
  ].join(' '));
  return { rows, contentTypes: contentTypes.map((c) => c.Name), formatterLength: formatterText.length };
})();
