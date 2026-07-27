/**
 * dbml-sharepoint FORM VISIBILITY — INTERACTIVE SURFACE PROBE
 *
 * Walks the whole form-visibility surface one question at a time. It asks
 * about a single column, you answer with one letter, it asks the next.
 * No JSON, no lists to assemble by hand.
 *
 * WHY: SharePoint records "is this column on the form?" in at least two
 * places — the field's own SchemaXml (written by SetShowIn*Form) and the
 * content type's FieldLink.Hidden (written by the modern
 * "Edit form -> Edit columns" panel). They disagree, sealing protects only
 * the first, and which one actually drives rendering decides whether a
 * declarative `form_visibility:` feature is worth building at all.
 *
 * WHAT IT WRITES: one list, named by PROBE_LIST, plus one item in it.
 * Nothing else is touched. cleanup() removes it.
 *
 * HOW TO RUN
 *   1. Set SITE_URL below.
 *   2. Open that site's /_layouts/15/settings.aspx as a Site Owner.
 *   3. F12 -> Console -> `allow pasting` if asked -> paste -> Enter.
 *
 * ANSWERING — just type the word and press Enter. No brackets, no quotes.
 *   y          yes, I can see that column on this form
 *   n          no, it is not on this form
 *   undo       go back one question
 *   skipform   stop asking about this form, move on
 *   ok         acknowledge an instruction and continue
 *
 * ANY TIME
 *   state()    re-print what each store currently says
 *   urls()     re-print the form links
 *   cleanup()  delete the probe list
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const SITE_URL = '';
  const PROBE_LIST = 'zzz dbmlsp form visibility interactive';
  // ------------------------------------------------------------------------

  const log = (m) => console.log(`%c[PROBE] ${m}`, 'color:#0a7');
  const say = (m) => console.log(m);
  const rule = () => console.log('%c' + '─'.repeat(66), 'color:#888');
  const bold = (m) => console.log(`%c${m}`, 'font-weight:bold;font-size:13px');

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
  const expOrigin = new URL(SITE_URL).origin;
  const expPath = new URL(SITE_URL).pathname.replace(/\/$/, '');
  const actPath = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (window.location.origin !== expOrigin || actPath !== expPath) {
    console.error(`[PROBE] Site mismatch. Expected ${expOrigin}${expPath}, found ${window.location.origin}${actPath}.`);
    return { aborted: 'site-mismatch' };
  }
  const WEB = actPath;
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

  const MATRIX = [
    { name: 'Ctl',     note: 'control — nothing done to it' },
    { name: 'NewOff',  note: 'setshowinnewform(false)' },
    { name: 'EditOff', note: 'setshowineditform(false)' },
    { name: 'DispOff', note: 'setshowindisplayform(false)' },
    { name: 'BothWay', note: 'setshowinnewform(false), then FieldLink.Hidden forced back to false' },
    { name: 'DeclOff', note: "created with ShowInNewForm='FALSE'" },
    { name: 'SealedF', note: 'sealed; visibility never touched' },
    { name: 'Calc',    note: 'calculated column' },
  ];
  const NOTE = new Map(MATRIX.map((m) => [m.name, m.note]));
  const NAMES = ['Title', ...MATRIX.map((m) => m.name)];

  // === One-word answering =================================================
  // Defined as window getters, so `y` + Enter is enough — no parentheses.
  let gate = null;
  const wait = () => new Promise((res) => { gate = res; });
  const answer = (v) => {
    if (!gate) return 'Nothing is waiting for an answer right now.';
    const g = gate; gate = null; g(v);
    return v === 'y' ? '✓ visible' : v === 'n' ? '✓ not visible' : `✓ ${v}`;
  };
  for (const word of ['y', 'n', 'undo', 'skipform', 'ok']) {
    Object.defineProperty(window, word, { configurable: true, get: () => answer(word) });
  }
  window.cleanup = async () => {
    const r = await post(listPath, undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
    return r.ok ? `Deleted '${PROBE_LIST}'.` : `Delete failed (HTTP ${r.status} ${r.error}). Remove it here: ${base}`;
  };

  // === Store readers ======================================================
  const parseXml = (x) => new DOMParser().parseFromString(String(x || '<Field/>'), 'application/xml');
  const isFalse = (el, n) => (el.getAttribute(n) || '').toUpperCase() === 'FALSE';
  async function readStores() {
    const out = new Map();
    const fr = await get(`${listPath}/fields?$select=InternalName,Sealed,SchemaXml&$top=500`);
    if (!fr.ok) { console.error(`[PROBE] field read failed: HTTP ${fr.status} ${fr.error}`); return out; }
    for (const f of fr.d.results || []) {
      if (!NAMES.includes(f.InternalName)) continue;
      const el = parseXml(f.SchemaXml).documentElement;
      out.set(f.InternalName, {
        sealed: !!f.Sealed,
        xml: { new: !isFalse(el, 'ShowInNewForm'), edit: !isFalse(el, 'ShowInEditForm'), display: !isFalse(el, 'ShowInDisplayForm') },
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
  let stores = new Map();
  function showTable(title) {
    rule(); log(title);
    console.table(NAMES.filter((n) => stores.has(n)).map((n) => {
      const s = stores.get(n);
      return {
        column: n, sealed: s.sealed ? 'YES' : '',
        'xml new': mark(s.xml.new), 'xml edit': mark(s.xml.edit), 'xml display': mark(s.xml.display),
        'FieldLink.Hidden': s.linkHidden === null ? '(none)' : (s.linkHidden ? 'HIDDEN' : 'shown'),
      };
    }));
  }
  const formUrl = (f) => `${base}/${f === 'new' ? 'NewForm.aspx' : f === 'edit' ? 'EditForm.aspx?ID=1' : 'DispForm.aspx?ID=1'}`;
  function urlsBanner() {
    rule();
    say(`  NEW form      ${formUrl('new')}`);
    say(`  EDIT form     ${formUrl('edit')}`);
    say(`  DISPLAY form  ${formUrl('display')}`);
    rule();
  }
  window.urls = () => { urlsBanner(); return 'printed'; };
  window.state = async () => { stores = await readStores(); showTable('Current stores'); return 'printed'; };

  // === The question loop ==================================================
  const observations = [];
  async function askForm(form, columns) {
    rule();
    bold(`${form.toUpperCase()} FORM`);
    say(`Open:  ${formUrl(form)}`);
    say('(middle-click so this console stays alive)');
    say('');
    say('For each column, answer whether you can SEE it on that form.');
    say('Type  y  or  n  then Enter.   undo = back one.   skipform = skip the rest.');
    const answers = new Map();
    let i = 0;
    while (i < columns.length) {
      const name = columns[i];
      rule();
      console.log(`%c  Q${i + 1}/${columns.length} · ${form.toUpperCase()} form — can you see:   %c${name}`,
        'color:#888', 'font-weight:bold;font-size:14px;color:#06c');
      if (NOTE.get(name)) say(`        (${NOTE.get(name)})`);
      console.log('%c        y   or   n', 'color:#0a7;font-weight:bold');
      const a = await wait();
      if (a === 'undo') { i = Math.max(0, i - 1); answers.delete(columns[i]); continue; }
      if (a === 'skipform') { log(`Skipping the rest of the ${form} form.`); break; }
      if (a !== 'y' && a !== 'n') { console.warn('[PROBE] Please answer y or n.'); continue; }
      answers.set(name, a === 'y');
      i += 1;
    }
    for (const [column, visible] of answers) observations.push({ form, column, visible });
    return answers;
  }

  // Score each candidate store against what was actually seen.
  function analyse(form, answers) {
    if (!answers.size) return null;
    const rows = []; let xmlHits = 0; let linkHits = 0; let andHits = 0;
    for (const [name, visible] of answers) {
      const s = stores.get(name); if (!s) continue;
      const xmlSays = s.xml[form];
      const linkSays = s.linkHidden === null ? true : !s.linkHidden;
      const andSays = xmlSays && linkSays;
      if (xmlSays === visible) xmlHits += 1;
      if (linkSays === visible) linkHits += 1;
      if (andSays === visible) andHits += 1;
      rows.push({
        column: name, YOU_SAW: visible ? 'visible' : 'not visible',
        'SchemaXml predicts': mark(xmlSays), 'FieldLink predicts': mark(linkSays), 'both predict': mark(andSays),
      });
    }
    const n = rows.length;
    rule(); log(`${form.toUpperCase()} form — predicted vs what you saw`);
    console.table(rows);
    log(`Agreement:  SchemaXml ${xmlHits}/${n} · FieldLink ${linkHits}/${n} · AND-of-both ${andHits}/${n}`);
    const best = Math.max(xmlHits, linkHits, andHits);
    const win = [];
    if (andHits === best) win.push('AND-of-both');
    if (linkHits === best) win.push('FieldLink.Hidden');
    if (xmlHits === best) win.push('SchemaXml');
    log(`Best explanation: ${win.join(' or ')}${best < n ? ' — but nothing explains every column' : ''}`);
    return { form, n, xmlHits, linkHits, andHits };
  }

  async function instruct(lines) {
    rule();
    for (const l of lines) say(l);
    console.log('%c   type  ok  when done', 'color:#0a7;font-weight:bold');
    await wait();
  }

  // === Setup ==============================================================
  rule();
  log('Setting up: one list, eight columns, one item. Nothing else is touched.');
  if ((await get(`${listPath}?$select=Title`)).ok) {
    log('A previous probe list exists — deleting it for a clean run.');
    const del = await post(listPath, undefined, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' });
    if (!del.ok) { console.error(`[PROBE] could not delete it: HTTP ${del.status} ${del.error}`); return { aborted: 'stale-list' }; }
  }
  const made = await post('web/lists', {
    __metadata: { type: 'SP.List' }, BaseTemplate: 100, Title: PROBE_LIST,
    Description: 'Throwaway list from dbml-sharepoint form-visibility-interactive.js. Safe to delete.',
  });
  if (!made.ok) { console.error(`[PROBE] could not create the list: HTTP ${made.status} ${made.error}`); return { aborted: 'list-create' }; }

  const asXml = (xml) => post(`${listPath}/fields/createfieldasxml`, {
    parameters: { __metadata: { type: 'SP.XmlSchemaFieldCreationInformation' }, SchemaXml: xml, Options: 9 },
  });
  for (const m of MATRIX) {
    const r = m.name === 'Calc'
      ? await asXml("<Field Type='Calculated' DisplayName='Calc' Name='Calc' ResultType='Number' ReadOnly='TRUE'><Formula>=1+1</Formula></Field>")
      : m.name === 'DeclOff'
        ? await asXml("<Field Type='Text' DisplayName='DeclOff' Name='DeclOff' ShowInNewForm='FALSE'/>")
        : await post(`${listPath}/fields`, { __metadata: { type: 'SP.Field' }, FieldTypeKind: 2, Title: m.name });
    if (!r.ok) console.warn(`[PROBE] could not create ${m.name}: HTTP ${r.status} ${r.error}`);
  }
  const setVis = (n, method, v) => post(`${fieldPath(n)}/${method}(${v})`);
  await setVis('NewOff', 'setshowinnewform', false);
  await setVis('EditOff', 'setshowineditform', false);
  await setVis('DispOff', 'setshowindisplayform', false);
  await setVis('BothWay', 'setshowinnewform', false);
  await post(fieldPath('SealedF'), { __metadata: { type: 'SP.Field' }, Sealed: true }, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });

  const setLinkHidden = async (name, hidden) => {
    const s = (await readStores()).get(name);
    if (!s || !s.linkId) return 'no FieldLink found';
    const r = await post(`${listPath}/contenttypes('${encodeURIComponent(s.ctId)}')/fieldlinks('${s.linkId}')`,
      { __metadata: { type: 'SP.FieldLink' }, Hidden: hidden }, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    if (!r.ok) return `MERGE rejected: HTTP ${r.status} ${r.error}`;
    const after = (await readStores()).get(name);
    return after.linkHidden === hidden ? `FieldLink.Hidden set to ${hidden}` : 'MERGE returned OK but the value did not change (silent no-op)';
  };
  const bothWayNote = await setLinkHidden('BothWay', false);
  log(`BothWay: ${bothWayNote}`);

  const et = await get(`${listPath}?$select=ListItemEntityTypeFullName`);
  if (et.ok) await post(`${listPath}/items`, { __metadata: { type: et.d.ListItemEntityTypeFullName }, Title: 'probe row' });

  stores = await readStores();
  showTable('Baseline — what each store says');
  rule();
  bold('THE MATRIX');
  for (const m of MATRIX) say(`  ${m.name.padEnd(8)} ${m.note}`);
  urlsBanner();

  // === Round 1 ============================================================
  bold('ROUND 1 of 3 — what do the forms actually render?');
  const cols = NAMES.filter((n) => stores.has(n));
  const r1 = [];
  for (const form of ['new', 'edit', 'display']) r1.push(analyse(form, await askForm(form, cols)));

  // === Round 2 ============================================================
  rule();
  bold('ROUND 2 of 3 — where does the modern UI write?');
  await instruct([
    'In the list, open an item and choose "Edit form" -> "Edit columns".',
    'UNTICK these two, then save:',
    '',
    '    Ctl        an ordinary column',
    '    SealedF    a SEALED column — note whether the UI even lets you',
    '',
  ]);
  const before = stores;
  stores = await readStores();
  showTable('After your UI change');
  rule();
  for (const n of ['Ctl', 'SealedF']) {
    const b = before.get(n); const a = stores.get(n);
    if (!b || !a) continue;
    const xmlMoved = ['new', 'edit', 'display'].some((f) => b.xml[f] !== a.xml[f]);
    log(`${n}: SchemaXml ${xmlMoved ? 'CHANGED' : 'unchanged'} · FieldLink.Hidden ${b.linkHidden !== a.linkHidden ? `CHANGED (${b.linkHidden} -> ${a.linkHidden})` : 'unchanged'}${a.sealed ? ' · SEALED' : ''}`);
  }
  const r2 = analyse('new', await askForm('new', ['Ctl', 'SealedF']));

  // === Round 3 ============================================================
  rule();
  bold('ROUND 3 of 3 — can the API undo a UI hide?');
  const undoNote = await setLinkHidden('Ctl', false);
  log(`Un-hiding Ctl via FieldLink.Hidden=false → ${undoNote}`);
  const sealedUndo = await setVis('SealedF', 'setshowinnewform', true);
  log(`setshowinnewform(true) on the sealed column → HTTP ${sealedUndo.status}${sealedUndo.ok ? '' : ` ${sealedUndo.error}`}`);
  stores = await readStores();
  showTable('After the API tried to undo');
  await instruct(['Reload the NEW form.']);
  const r3 = analyse('new', await askForm('new', ['Ctl', 'SealedF']));

  // === Summary ============================================================
  rule();
  bold('SUMMARY');
  console.table([...r1, r2, r3].filter(Boolean).map((r, i) => ({
    round: i < 3 ? 1 : i === 3 ? 2 : 3,
    form: r.form, columns: r.n,
    'SchemaXml agrees': `${r.xmlHits}/${r.n}`,
    'FieldLink agrees': `${r.linkHits}/${r.n}`,
    'both agree': `${r.andHits}/${r.n}`,
  })));
  log(`BothWay setup: ${bothWayNote}`);
  log(`Undo a UI hide: ${undoNote}`);
  rule();
  say('Copy this whole console back. When finished, run:');
  console.log('%c  cleanup()', 'color:#06c;font-weight:bold');
  return { observations, bothWayNote, undoNote };
})();
