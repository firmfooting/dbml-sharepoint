/**
 * dbml-sharepoint FORM VISIBILITY — INTERACTIVE SURFACE PROBE
 *
 * One script, run once, that walks you through the whole form-visibility
 * surface. It pauses at each step, tells you exactly what to click, and
 * waits for you to come back to the console and type a command.
 *
 * WHY: SharePoint records "is this column on the form?" in at least two
 * places — the field's own SchemaXml (written by SetShowIn*Form) and the
 * content type's FieldLink.Hidden (written by the modern
 * "Edit form -> Edit columns" panel). They disagree, sealing protects only
 * the first, and which one actually drives rendering decides whether a
 * declarative `form_visibility:` feature is worth building.
 *
 * WHAT IT WRITES: one list, named by PROBE_LIST, plus one item in it. It
 * touches nothing else, and offers to delete itself at the end.
 *
 * HOW TO RUN
 *   1. Set SITE_URL below.
 *   2. Open that site's /_layouts/15/settings.aspx as a Site Owner.
 *   3. F12 -> Console -> `allow pasting` if asked -> paste -> Enter.
 *   4. Follow the instructions. The console tells you what to type.
 *
 * COMMANDS (available once it starts)
 *   done()                      continue to the next step
 *   report({new:'A, B', edit:'A, B, C', display:'A'})
 *                               record which columns you can SEE, then
 *                               continue. Names are case-insensitive and
 *                               partial matches are fine.
 *   state()                     re-print the store table at any time
 *   urls()                      re-print the form links
 *   abandon()                   end the run early (list is left in place)
 *   cleanup()                   delete the probe list when you are done
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const SITE_URL = '';
  const PROBE_LIST = 'zzz dbmlsp form visibility interactive';
  // ------------------------------------------------------------------------

  const log = (msg) => console.log(`%c[PROBE] ${msg}`, 'color:#0a7');
  const say = (msg) => console.log(msg);
  const rule = () => console.log('%c' + '─'.repeat(72), 'color:#888');

  if (!SITE_URL) {
    const guess = (typeof _spPageContextInfo !== 'undefined')
      ? `${window.location.origin}${_spPageContextInfo.webServerRelativeUrl || ''}` : '(unknown)';
    console.error(`[PROBE] Set SITE_URL at the top of this script. This web looks like: ${guess}`);
    return { aborted: 'site-url-unset' };
  }
  if (typeof _spPageContextInfo === 'undefined') {
    console.error('[PROBE] _spPageContextInfo unavailable. Open /_layouts/15/settings.aspx and retry.');
    return { aborted: 'no-sp-page-context' };
  }
  const expectedOrigin = new URL(SITE_URL).origin;
  const expectedPath = new URL(SITE_URL).pathname.replace(/\/$/, '');
  const actualPath = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (window.location.origin !== expectedOrigin || actualPath !== expectedPath) {
    console.error(`[PROBE] Site mismatch. Expected ${expectedOrigin}${expectedPath}, found ${window.location.origin}${actualPath}.`);
    return { aborted: 'site-mismatch' };
  }
  const WEB = actualPath;
  const apiUrl = (s) => `${WEB}/_api/${s}`;
  const odataName = (n) => encodeURIComponent(String(n).replace(/'/g, "''"));

  // === Transport ===
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const spError = (t) => { try { return JSON.parse(t)?.error?.message?.value || String(t).slice(0, 200); } catch { return String(t).slice(0, 200); } };
  async function fetchWithRetry(url, opts, attempts = 5) {
    for (let i = 0; ; i++) {
      const r = await fetch(url, opts);
      if ((r.status === 429 || r.status === 503) && i < attempts) {
        await sleep((Number(r.headers.get('Retry-After')) || Math.min(2 ** i, 30)) * 1000);
        continue;
      }
      return r;
    }
  }
  let digest = null; let digestExp = 0;
  async function getDigest() {
    if (digest && Date.now() < digestExp) return digest;
    const r = await fetchWithRetry(apiUrl('contextinfo'), { method: 'POST', headers: { Accept: 'application/json;odata=verbose' } });
    const i = (await r.json()).d.GetContextWebInformation;
    digest = i.FormDigestValue;
    digestExp = Date.now() + Math.max((Number(i.FormDigestTimeoutSeconds) || 1800) - 60, 60) * 1000;
    return digest;
  }
  async function get(s) {
    const r = await fetchWithRetry(apiUrl(s), { headers: { Accept: 'application/json;odata=verbose' } });
    if (!r.ok) return { ok: false, status: r.status, error: spError(await r.text()) };
    const j = await r.json();
    return { ok: true, d: j && j.d !== undefined ? j.d : j };
  }
  async function post(s, body, extra) {
    const d = await getDigest();
    const r = await fetchWithRetry(apiUrl(s), {
      method: 'POST',
      headers: { Accept: 'application/json;odata=verbose', 'Content-Type': 'application/json;odata=verbose', 'X-RequestDigest': d, ...(extra || {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return r.ok ? { ok: true, status: r.status } : { ok: false, status: r.status, error: spError(await r.text()) };
  }

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const fieldPath = (n) => `${listPath}/fields/getbyinternalnameortitle('${odataName(n)}')`;
  const base = `${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`;

  // === The field matrix. Short names so they are quick to type back. ======
  const MATRIX = [
    { name: 'Ctl',      note: 'control — nothing done to it' },
    { name: 'NewOff',   note: 'setshowinnewform(false)' },
    { name: 'EditOff',  note: 'setshowineditform(false)' },
    { name: 'DispOff',  note: 'setshowindisplayform(false)' },
    { name: 'BothWay',  note: 'setshowinnewform(false) THEN FieldLink.Hidden=false — the decisive one' },
    { name: 'DeclOff',  note: "created with ShowInNewForm='FALSE'" },
    { name: 'SealedF',  note: 'sealed, visibility untouched' },
    { name: 'Calc',     note: 'calculated column' },
  ];
  const NAMES = MATRIX.map((m) => m.name).concat('Title');

  // === Interaction gate ===================================================
  let gate = null;
  const wait = () => new Promise((res) => { gate = res; });
  const release = (value) => {
    if (!gate) { console.warn('[PROBE] Nothing is waiting right now.'); return 'nothing waiting'; }
    const g = gate; gate = null; g(value);
    return 'continuing…';
  };
  window.done = () => release(null);
  window.report = (obs) => {
    if (!obs || typeof obs !== 'object') {
      console.warn("[PROBE] Usage: report({new:'Title, Ctl', edit:'Title, Ctl', display:'Title'})");
      return 'bad arguments';
    }
    return release(obs);
  };
  // Named `abandon`, not `stop`: window.stop is a standard DOM method that
  // halts page loading, and shadowing it from a console script is rude.
  window.abandon = () => { aborted = true; return release(null); };
  let aborted = false;
  window.cleanup = async () => {
    const r = await post(listPath, undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
    return r.ok ? `Deleted '${PROBE_LIST}'.` : `Delete failed (HTTP ${r.status} ${r.error}). Remove it in the UI: ${base}`;
  };

  // Lenient name matching: case-insensitive, partial, comma or space split.
  const parseSeen = (text) => {
    const tokens = String(text || '').split(/[,;\s]+/).map((t) => t.trim()).filter(Boolean);
    const seen = new Set();
    for (const t of tokens) {
      const hit = NAMES.find((n) => n.toLowerCase() === t.toLowerCase())
        || NAMES.find((n) => n.toLowerCase().startsWith(t.toLowerCase()));
      if (hit) seen.add(hit); else console.warn(`[PROBE] Ignoring unrecognised column '${t}'.`);
    }
    return seen;
  };

  // === Store readers ======================================================
  const parseXml = (x) => new DOMParser().parseFromString(String(x || '<Field/>'), 'application/xml');
  const attrHidden = (el, n) => (el.getAttribute(n) || '').toUpperCase() === 'FALSE';

  async function readStores() {
    const out = new Map();
    const fr = await get(`${listPath}/fields?$select=InternalName,Sealed,SchemaXml&$top=500`);
    if (!fr.ok) { console.error(`[PROBE] field read failed: HTTP ${fr.status} ${fr.error}`); return out; }
    for (const f of fr.d.results || []) {
      if (!NAMES.includes(f.InternalName)) continue;
      const el = parseXml(f.SchemaXml).documentElement;
      out.set(f.InternalName, {
        sealed: !!f.Sealed,
        xmlNew: !attrHidden(el, 'ShowInNewForm'),
        xmlEdit: !attrHidden(el, 'ShowInEditForm'),
        xmlDisplay: !attrHidden(el, 'ShowInDisplayForm'),
        linkHidden: null, linkId: null, ctId: null,
      });
    }
    const ct = await get(`${listPath}/contenttypes?$select=Name,StringId`);
    if (ct.ok) {
      for (const c of ct.d.results || []) {
        if (c.Name === 'Folder') continue;
        const fl = await get(`${listPath}/contenttypes('${encodeURIComponent(c.StringId)}')/fieldlinks?$select=Name,Id,Hidden&$top=500`);
        if (!fl.ok) continue;
        for (const l of fl.d.results || []) {
          const rec = out.get(l.Name);
          if (rec && rec.linkHidden === null) { rec.linkHidden = l.Hidden === true; rec.linkId = l.Id; rec.ctId = c.StringId; }
        }
      }
    }
    return out;
  }

  const mark = (b) => (b ? 'shown' : 'HIDDEN');
  function showTable(stores, title) {
    rule(); log(title);
    console.table(NAMES.filter((n) => stores.has(n)).map((n) => {
      const s = stores.get(n);
      return {
        column: n,
        sealed: s.sealed ? 'YES' : '',
        'SchemaXml new': mark(s.xmlNew),
        'SchemaXml edit': mark(s.xmlEdit),
        'SchemaXml display': mark(s.xmlDisplay),
        'FieldLink.Hidden': s.linkHidden === null ? '(none)' : (s.linkHidden ? 'HIDDEN' : 'shown'),
      };
    }));
  }

  // Which store explains what the operator actually sees?
  function analyse(stores, form, seen) {
    const key = { new: 'xmlNew', edit: 'xmlEdit', display: 'xmlDisplay' }[form];
    const rows = []; let xmlHits = 0, linkHits = 0, bothHits = 0, n = 0;
    for (const name of NAMES) {
      const s = stores.get(name); if (!s) continue;
      const visible = seen.has(name);
      const xmlSays = s[key];
      const linkSays = s.linkHidden === null ? true : !s.linkHidden;
      const bothSays = xmlSays && linkSays;
      n += 1;
      if (xmlSays === visible) xmlHits += 1;
      if (linkSays === visible) linkHits += 1;
      if (bothSays === visible) bothHits += 1;
      rows.push({
        column: name,
        OBSERVED: visible ? 'visible' : 'not visible',
        'SchemaXml predicts': mark(xmlSays),
        'FieldLink predicts': mark(linkSays),
        'AND of both predicts': mark(bothSays),
      });
    }
    rule(); log(`${form.toUpperCase()} form — predicted vs observed`);
    console.table(rows);
    const score = (h) => `${h}/${n}`;
    log(`Agreement: SchemaXml ${score(xmlHits)} · FieldLink ${score(linkHits)} · AND-of-both ${score(bothHits)}`);
    const best = Math.max(xmlHits, linkHits, bothHits);
    const winners = [];
    if (bothHits === best) winners.push('AND-of-both');
    if (linkHits === best) winners.push('FieldLink.Hidden');
    if (xmlHits === best) winners.push('SchemaXml');
    log(`Best explanation for the ${form} form: ${winners.join(' or ')}${best < n ? ' (still imperfect — no store explains everything)' : ''}`);
    return { form, n, xmlHits, linkHits, bothHits, seen: [...seen] };
  }

  function urlsBanner() {
    rule();
    say(`  New form:     ${base}/NewForm.aspx`);
    say(`  Edit form:    ${base}/EditForm.aspx?ID=1`);
    say(`  Display form: ${base}/DispForm.aspx?ID=1`);
    say(`  Edit columns: open the list -> Edit form (top right of the form) -> Edit columns`);
    rule();
  }
  window.urls = () => { urlsBanner(); return 'printed'; };
  window.state = async () => { showTable(await readStores(), 'Current stores'); return 'printed'; };

  // === Setup ==============================================================
  rule();
  log('Setting up. This creates one list and one item; nothing else is touched.');
  const existing = await get(`${listPath}?$select=Title`);
  if (existing.ok) {
    log('A previous probe list exists — deleting it for a clean run.');
    const del = await post(listPath, undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
    if (!del.ok) { console.error(`[PROBE] Could not delete it: HTTP ${del.status} ${del.error}`); return { aborted: 'stale-list' }; }
  }
  const made = await post('web/lists', {
    __metadata: { type: 'SP.List' }, BaseTemplate: 100, Title: PROBE_LIST,
    Description: 'Throwaway list from dbml-sharepoint form-visibility-interactive.js. Safe to delete.',
  });
  if (!made.ok) { console.error(`[PROBE] Could not create the list: HTTP ${made.status} ${made.error}`); return { aborted: 'list-create' }; }

  for (const m of MATRIX) {
    let r;
    if (m.name === 'Calc') {
      r = await post(`${listPath}/fields/createfieldasxml`, {
        parameters: { __metadata: { type: 'SP.XmlSchemaFieldCreationInformation' },
          SchemaXml: `<Field Type='Calculated' DisplayName='Calc' Name='Calc' ResultType='Number' ReadOnly='TRUE'><Formula>=1+1</Formula></Field>`,
          Options: 9 },
      });
    } else if (m.name === 'DeclOff') {
      r = await post(`${listPath}/fields/createfieldasxml`, {
        parameters: { __metadata: { type: 'SP.XmlSchemaFieldCreationInformation' },
          SchemaXml: `<Field Type='Text' DisplayName='DeclOff' Name='DeclOff' ShowInNewForm='FALSE'/>`,
          Options: 9 },
      });
    } else {
      r = await post(`${listPath}/fields`, { __metadata: { type: 'SP.Field' }, FieldTypeKind: 2, Title: m.name });
    }
    if (!r.ok) console.warn(`[PROBE] could not create ${m.name}: HTTP ${r.status} ${r.error}`);
  }

  // Apply the API operations that define the matrix.
  const setVis = (n, method, v) => post(`${fieldPath(n)}/${method}(${v})`);
  await setVis('NewOff', 'setshowinnewform', false);
  await setVis('EditOff', 'setshowineditform', false);
  await setVis('DispOff', 'setshowindisplayform', false);
  await setVis('BothWay', 'setshowinnewform', false);
  await post(fieldPath('SealedF'), { __metadata: { type: 'SP.Field' }, Sealed: true }, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });

  // BothWay: undo the field-link side effect, keeping SchemaXml new=HIDDEN.
  // This is the decisive test for `{new: false, edit: true}`.
  let bothWayNote = '';
  {
    const s = await readStores();
    const b = s.get('BothWay');
    if (!b || b.linkId === null) {
      bothWayNote = 'could not locate its FieldLink';
    } else if (b.linkHidden === false) {
      bothWayNote = 'setter did not hide the FieldLink, so nothing to undo';
    } else {
      const r = await post(`${listPath}/contenttypes('${encodeURIComponent(b.ctId)}')/fieldlinks('${b.linkId}')`,
        { __metadata: { type: 'SP.FieldLink' }, Hidden: false }, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
      const after = (await readStores()).get('BothWay');
      bothWayNote = !r.ok ? `MERGE rejected: HTTP ${r.status} ${r.error}`
        : after && after.linkHidden === false ? 'FieldLink.Hidden set back to false — SchemaXml still hides it from New'
          : 'MERGE returned OK but FieldLink.Hidden did not change (silent no-op)';
    }
    log(`BothWay: ${bothWayNote}`);
  }

  // One item, so the Edit and Display forms are reachable.
  const et = await get(`${listPath}?$select=ListItemEntityTypeFullName`);
  if (et.ok) {
    await post(`${listPath}/items`, { __metadata: { type: et.d.ListItemEntityTypeFullName }, Title: 'probe row' });
  }

  const findings = [];
  let stores = await readStores();
  showTable(stores, 'Baseline — what each store says after setup');
  rule();
  console.log('%cMATRIX', 'font-weight:bold');
  for (const m of MATRIX) say(`  ${m.name.padEnd(9)} ${m.note}`);

  // === Step 1 =============================================================
  rule();
  console.log('%cSTEP 1 of 3 — what do the forms actually render?', 'font-weight:bold;font-size:13px');
  urlsBanner();
  say('Open each form (middle-click to keep this console alive), note which of the');
  say('columns above you can SEE, then come back here and type:');
  say('');
  console.log("%c  report({new:'Title, Ctl', edit:'Title, Ctl, NewOff', display:'Title, Ctl'})", 'color:#06c');
  say('');
  say('List only what IS visible. Names are case-insensitive; partials are fine.');
  const obs1 = await wait();
  if (aborted) return { aborted: 'stopped' };
  if (obs1) {
    for (const form of ['new', 'edit', 'display']) {
      if (obs1[form] === undefined) continue;
      findings.push(analyse(stores, form, parseSeen(obs1[form])));
    }
  }

  // === Step 2 =============================================================
  rule();
  console.log('%cSTEP 2 of 3 — where does the UI write?', 'font-weight:bold;font-size:13px');
  say('In the list UI: open an item, choose "Edit form" -> "Edit columns",');
  say('then UNTICK these two and save:');
  say('');
  console.log('%c  Ctl        (an ordinary column)', 'color:#06c');
  console.log('%c  SealedF    (a SEALED column — note whether the UI even lets you)', 'color:#06c');
  say('');
  say('Then type:  done()      (or report({new:"…"}) if you also re-checked the form)');
  const obs2 = await wait();
  if (aborted) return { aborted: 'stopped' };
  const before = stores;
  stores = await readStores();
  showTable(stores, 'After your UI change');
  rule();
  for (const n of ['Ctl', 'SealedF']) {
    const b = before.get(n); const a = stores.get(n);
    if (!b || !a) continue;
    const xmlMoved = b.xmlNew !== a.xmlNew || b.xmlEdit !== a.xmlEdit || b.xmlDisplay !== a.xmlDisplay;
    const linkMoved = b.linkHidden !== a.linkHidden;
    log(`${n}: SchemaXml ${xmlMoved ? 'CHANGED' : 'unchanged'} · FieldLink.Hidden ${linkMoved ? `CHANGED (${b.linkHidden} -> ${a.linkHidden})` : 'unchanged'}${a.sealed ? ' · field is SEALED' : ''}`);
  }
  if (obs2) for (const form of ['new', 'edit', 'display']) {
    if (obs2[form] !== undefined) findings.push(analyse(stores, form, parseSeen(obs2[form])));
  }

  // === Step 3 =============================================================
  rule();
  console.log('%cSTEP 3 of 3 — can the API undo a UI hide?', 'font-weight:bold;font-size:13px');
  const ctl = stores.get('Ctl');
  let undoNote = 'skipped — Ctl has no FieldLink';
  if (ctl && ctl.linkId) {
    const r = await post(`${listPath}/contenttypes('${encodeURIComponent(ctl.ctId)}')/fieldlinks('${ctl.linkId}')`,
      { __metadata: { type: 'SP.FieldLink' }, Hidden: false }, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    const after = (await readStores()).get('Ctl');
    undoNote = !r.ok ? `MERGE rejected: HTTP ${r.status} ${r.error}`
      : after.linkHidden === false ? 'FieldLink.Hidden reset to false'
        : 'MERGE returned OK but the value did not change (silent no-op)';
  }
  log(`Attempted to un-hide Ctl via FieldLink.Hidden=false → ${undoNote}`);
  await setVis('SealedF', 'setshowinnewform', true);
  stores = await readStores();
  showTable(stores, 'After the API tried to undo');
  say('');
  say('Reload the New form and report what you see now:');
  console.log("%c  report({new:'Title, Ctl'})", 'color:#06c');
  const obs3 = await wait();
  if (aborted) return { aborted: 'stopped' };
  if (obs3) for (const form of ['new', 'edit', 'display']) {
    if (obs3[form] !== undefined) findings.push(analyse(stores, form, parseSeen(obs3[form])));
  }

  // === Wrap up ============================================================
  rule();
  console.log('%cSUMMARY', 'font-weight:bold;font-size:13px');
  console.table(findings.map((f) => ({
    form: f.form,
    columns: f.n,
    'SchemaXml agrees': `${f.xmlHits}/${f.n}`,
    'FieldLink agrees': `${f.linkHits}/${f.n}`,
    'AND-of-both agrees': `${f.bothHits}/${f.n}`,
  })));
  log(`BothWay outcome: ${bothWayNote}`);
  log(`Undo-a-UI-hide outcome: ${undoNote}`);
  rule();
  say('Send this whole console output back. When you are finished with the list:');
  console.log('%c  cleanup()', 'color:#06c');
  say(`  …or delete it in the UI: ${base}`);
  return { findings, bothWayNote, undoNote };
})();
