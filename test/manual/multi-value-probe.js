/**
 * dbml-sharepoint MULTI-VALUE COLUMN PROBE (creates and deletes its own list).
 *
 * This tool emits no multi-value column of any kind. `SPField.selection_mode`
 * exists but is hard-wired to 0 and is set only for Person; there is no
 * MultiChoice, no multi-value lookup, no multi-value Person. A capability
 * specification for MULTICHOICE is written against the documentation below,
 * and everything the documentation does not answer is asked here rather than
 * assumed.
 *
 * WHAT MICROSOFT ALREADY DOCUMENTS — none of it is re-asked:
 *
 *   FieldType.MultiChoice = 15, and SP.FieldChoice DERIVES from
 *   SP.FieldMultiChoice (so `Choices` is a FieldMultiChoice property).
 *     https://learn.microsoft.com/dotnet/api/microsoft.sharepoint.client.fieldtype?view=sharepoint-csom
 *     https://learn.microsoft.com/dotnet/api/microsoft.sharepoint.client.fieldchoice?view=sharepoint-csom
 *     https://learn.microsoft.com/dotnet/api/microsoft.sharepoint.client.fieldmultichoice.choices?view=sharepoint-csom
 *
 *   The Field element's Type vocabulary: `MultiChoice` is "a Choice field
 *   that implements check boxes and allows the user to select multiple
 *   values", stored as ntext. `LookupMulti` and `UserMulti` are the sibling
 *   spellings for the other two multi-value kinds.
 *     https://learn.microsoft.com/sharepoint/dev/schema/field-element-list
 *
 *   A multi-valued Choice CANNOT be indexed and CANNOT enforce unique values.
 *     https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0
 *     https://support.microsoft.com/en-US/SharePoint/lists/data-and-lists/create-list-relationships-by-using-lookup-columns
 *
 *   Conditional show/hide does not support "Choice with multiple selections".
 *     https://learn.microsoft.com/sharepoint/dev/declarative-customization/list-form-conditional-show-hide
 *
 *   Column formatting DOES support Multi-Choice, and `@currentField` on one is
 *   an ARRAY: `length` counts its members and `join` concatenates them.
 *     https://learn.microsoft.com/sharepoint/dev/declarative-customization/column-formatting
 *     https://learn.microsoft.com/sharepoint/dev/declarative-customization/formatting-syntax-reference
 *
 *   CAML `Includes` / `NotIncludes` are documented ONLY for "a Lookup field
 *   that allows multiple values" — MultiChoice is not mentioned. CAML
 *   `Contains` is documented only for "a column that holds Text or Note field
 *   type values". So on a MultiChoice column all three are UNDOCUMENTED, which
 *   is why C1..C7 below exist.
 *     https://learn.microsoft.com/sharepoint/dev/schema/includes-element-query
 *     https://learn.microsoft.com/sharepoint/dev/schema/notincludes-element-query
 *     https://learn.microsoft.com/sharepoint/dev/schema/contains-element-query
 *
 * WHAT IS NOT DOCUMENTED, AND IS WHAT THIS PROBE ASKS:
 *
 *   M1  whether the deployer's EXISTING create path — a plain POST of a field
 *       body to /fields — takes a MultiChoice, or whether it needs the
 *       AddField/AddFieldAsXml treatment a Lookup needs (issue #31).
 *   M2  what the created field reads back as.
 *   M3  the item WRITE shape. Learn's list-item REST page documents no
 *       multi-value example at all, so four candidate shapes are tried in
 *       order and the probe records which one SharePoint took.
 *   M4  the item READ-BACK shape, under both odata=verbose and odata=nometadata.
 *   M5  whether a re-write of the same value round-trips, and whether member
 *       ORDER survives — the deployer's only array comparator is
 *       order-sensitive.
 *   I1  whether `Indexed: true` is ACCEPTED and what it then READS BACK.
 *   I2  the same for `EnforceUniqueValues`.
 *   C1..C7  which rows each CAML predicate actually returns.
 *   V1  whether a ValidationFormula may reference a MultiChoice column.
 *   F1  whether a calculated column's formula may reference one.
 *   X1  what the repository's own `severity` formatter does when it meets an
 *       array (manual: look).
 *
 * WHY I1 IS THE DANGEROUS ONE. Learn says a multi-valued Choice is not an
 * indexable column type. It does not say what the REST property DOES when you
 * set it anyway. If `Indexed: true` is accepted and reads back `false`, a
 * declared index on such a column would abort a deploy part-way through
 * (which is survivable and loud); if it is accepted and reads back TRUE while
 * no index exists, nothing in a build or a deploy can ever see it. So I1
 * carries a CONTROL: the same write is made to a SINGLE-value Choice on the
 * same list, where indexing IS documented as supported. If the control also
 * fails to stick, the property is not reporting what this probe needs and BOTH
 * rows are void — the probe records that itself rather than trusting a reader
 * to remember this paragraph.
 *
 * THE SEPARATION THIS FILE KEEPS. Values the measurement DEPENDS ON are
 * asserted: the list exists, both fields exist, four rows were seeded, and the
 * seeded sets are what was asked for. Values the measurement OBSERVES are
 * never asserted: which write shape wins, what the readback looks like, what
 * Indexed reads back, and which rows a predicate returns. Asserting over the
 * second kind kills the experiment the moment it starts working, and that is
 * indistinguishable from a real failure.
 *
 * WHAT IT WRITES: one list, named by PROBE_LIST below, created at start and
 * deleted at end. It never reads, writes or enumerates any other list. If
 * cleanup fails it says so loudly and prints the URL to delete by hand.
 *
 * HOW TO RUN
 *   1. Paste it once: it prints the web and stops. Set CONFIRMED = true.
 *   2. Open that site's classic settings page — /_layouts/15/settings.aspx —
 *      signed in as a Site Owner. The site guard needs _spPageContextInfo.
 *   3. F12 -> Console -> type `allow pasting` if the browser objects ->
 *      paste this whole file -> Enter.
 *   4. Read the RESULTS table, then do THE MANUAL STEPS below.
 *   5. Paste the [VERDICT] lines back to whoever asked for this probe.
 *
 * THE MANUAL STEPS (X1 and C8 cannot be answered from script)
 *   Set CLEANUP_AT_END = false, run, then OPEN the two URLs the probe prints.
 *     X1 — does the multi-value column render as a coloured severity pill,
 *          and what text does the cell show? A property that round-trips and
 *          renders nothing is the failure class this repository exists to
 *          close.
 *     C8 — does the STORED view (as opposed to the ad-hoc CamlQuery the other
 *          C rows use) list the rows C-whichever-won predicted? SharePoint
 *          rewrites ViewQuery XML on save, so a predicate proven only through
 *          GetItems is not yet proven where the deployer writes it. This is
 *          the same C6/C7 discipline datetime-sentinel-probe.js used.
 *   Re-run with CLEANUP_AT_END = true to remove the list.
 *
 * STATUS: NOT YET RUN. Every row below is a question, not a finding.
 */
(async () => {
  // ---- Operator settings -------------------------------------------------
  const CONFIRMED = false;
  const PROBE_LIST = 'zzz dbmlsp multi value probe';
  const CLEANUP_AT_END = false;
  // ------------------------------------------------------------------------

  // The multi-value column under test, and its single-value twin, which is
  // the control for I1/I2. Both carry the SAME choice set so a difference in
  // behaviour can only be the multiplicity.
  const MULTI = 'Evt';
  const SINGLE = 'EvtSingle';
  const CHOICES = ['View', 'Edit', 'Export', 'Delete', 'PermissionChange'];

  // The CAML fixture. Titles are the identity every C row reports, so they
  // say what the row CONTAINS and a reader never has to hold the mapping in
  // their head. R4 is deliberately empty: three-valued logic is where the
  // negative predicates get interesting, and the deployer already wraps `neq`
  // in <Or><IsNull> for exactly that reason on single-value columns.
  const ROWS = [
    { title: 'R1 {View}', values: ['View'] },
    { title: 'R2 {View,Edit}', values: ['View', 'Edit'] },
    { title: 'R3 {Edit,Export}', values: ['Edit', 'Export'] },
    { title: 'R4 {}', values: [] },
  ];

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

  expect('Q0', 'the fixture actually built: two fields, four rows, seeded sets as asked');
  expect('M1', 'a MultiChoice field is created by a plain POST to /fields');
  expect('M2', 'the created field reads back as MultiChoice');
  expect('M3', 'which item WRITE shape SharePoint accepts');
  expect('M4', 'what an item value READS BACK as');
  expect('M5', 'a re-write round-trips, and member order survives');
  expect('I1', 'Indexed:true on a MultiChoice — accepted? and what does it read back as?');
  expect('I1C', 'CONTROL: Indexed:true on the SINGLE-value Choice, where Learn says it is supported');
  expect('I2', 'EnforceUniqueValues:true on a MultiChoice — accepted? readback?');
  expect('C1', 'CAML <Eq> "View" returns which rows');
  expect('C2', 'CAML <Eq> "View;#Edit" returns which rows');
  expect('C3', 'CAML <Contains> "View" returns which rows');
  expect('C4', 'CAML <Includes> "View" returns which rows');
  expect('C5', 'CAML <NotIncludes> "View" returns which rows');
  expect('C6', 'CAML <IsNull> returns which rows');
  expect('C7', 'CAML <IsNotNull> returns which rows');
  expect('C8', 'the winning predicate survives being STORED as a view ViewQuery (manual: look)');
  expect('V1', 'a ValidationFormula may reference a MultiChoice column');
  expect('F1', 'a calculated column formula may reference a MultiChoice column');
  expect('X1', 'the severity formatter this repo generates, on an array (manual: look)');

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
  // Returns the parsed body on success too — M3 and M4 need to SEE what came
  // back, not merely whether it was accepted.
  async function post(suffix, body, extraHeaders) {
    const digest = await getDigest();
    const r = await fetchWithRetry(apiUrl(suffix), {
      method: 'POST',
      headers: spHeaders(digest, extraHeaders || {}),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!r.ok) return { ok: false, status: r.status, error: spError(await r.text()), d: null };
    const text = await r.text();
    let d = null;
    try { d = text ? JSON.parse(text).d : null; } catch { d = null; }
    return { ok: true, status: r.status, error: null, d };
  }
  async function get(suffix, accept) {
    const r = await fetchWithRetry(apiUrl(suffix), {
      method: 'GET', headers: { 'Accept': accept || 'application/json;odata=verbose' },
    });
    if (!r.ok) return { ok: false, status: r.status, error: spError(await r.text()), d: null };
    const parsed = await r.json();
    return { ok: true, status: r.status, error: null, d: parsed.d !== undefined ? parsed.d : parsed };
  }
  async function merge(suffix, body) {
    return post(suffix, body, { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' });
  }
  // An item POST's __metadata.type must be the LIST'S OWN entity type
  // (SP.Data.<MangledListName>ListItem), not the generic SP.Data.ListItem.
  async function entityTypeFor(listTitle) {
    const r = await get(`web/lists/getbytitle('${odataName(listTitle)}')?$select=ListItemEntityTypeFullName`);
    if (!r.ok) throw new Error(`could not resolve the item entity type: ${r.error}`);
    return r.d.ListItemEntityTypeFullName;
  }

  const listPath = `web/lists/getbytitle('${odataName(PROBE_LIST)}')`;
  const fieldPath = (name) => `${listPath}/fields/getbyinternalnameortitle('${odataName(name)}')`;
  let createdList = false;
  let viewUrl = null;
  let listDefaultUrl = null;

  // The four candidate item-value shapes, most-likely first. Learn's list-item
  // REST page documents none of them for a multi-value column, so this is an
  // ordered experiment rather than a lookup, and the probe reports WHICH index
  // won rather than assuming the first.
  const writeShapes = [
    { name: 'collection-metadata', build: (v) => ({ __metadata: { type: 'Collection(Edm.String)' }, results: v }) },
    { name: 'bare-results', build: (v) => ({ results: v }) },
    { name: 'bare-array', build: (v) => v },
    { name: 'delimited-string', build: (v) => (v.length ? `;#${v.join(';#')};#` : '') },
  ];

  const show = (value) => {
    try { return JSON.stringify(value); } catch { return String(value); }
  };

  try {
    // === Setup: the list ==================================================
    const made = await post('web/lists', {
      __metadata: { type: 'SP.List' },
      BaseTemplate: 100,
      Title: PROBE_LIST,
      Description: 'dbml-sharepoint multi-value column probe. Safe to delete.',
    });
    if (!made.ok) {
      record('Q0', 'the fixture actually built', 'ABORTED', `could not create the probe list: HTTP ${made.status} ${made.error}`);
      throw new Error('setup failed');
    }
    createdList = true;
    listDefaultUrl = made.d?.DefaultViewUrl || null;
    log('INFO', `Created '${PROBE_LIST}'.`);

    // === M1: the deployer's own create path, unchanged =====================
    // This is deliberately the SAME shape jsgen._field_body builds for a
    // single-value Choice — POST the whole body to /fields — with only
    // FieldTypeKind and __metadata.type changed. If a MultiChoice needs the
    // AddField treatment a Lookup needs, this is where that shows up, and the
    // specification's "no new creation machinery" claim collapses.
    const createdMulti = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldMultiChoice' },
      FieldTypeKind: 15,
      Title: MULTI,
      Choices: { results: CHOICES },
      FillInChoice: false,
    });
    record(
      'M1',
      'a MultiChoice field is created by a plain POST to /fields',
      createdMulti.ok ? 'ACCEPTED' : 'REFUSED',
      createdMulti.ok
        ? `HTTP ${createdMulti.status} — the existing create path needs no AddField treatment`
        : `HTTP ${createdMulti.status} — ${createdMulti.error}`,
    );
    if (!createdMulti.ok) {
      record('Q0', 'the fixture actually built', 'ABORTED', 'the MultiChoice field could not be created, so nothing below can be asked');
      throw new Error('setup failed');
    }

    // The single-value control, created exactly as the tool creates one today.
    const createdSingle = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldChoice' },
      FieldTypeKind: 6,
      Title: SINGLE,
      Choices: { results: CHOICES },
      FillInChoice: false,
    });

    // === M2: what did we actually get? =====================================
    const shape = await get(
      `${fieldPath(MULTI)}?$select=InternalName,TypeAsString,FieldTypeKind,Choices,FillInChoice,Indexed,EnforceUniqueValues`,
    );
    record(
      'M2',
      'the created field reads back as MultiChoice',
      shape.ok ? 'READ' : 'UNREADABLE',
      shape.ok
        ? `TypeAsString=${show(shape.d.TypeAsString)} FieldTypeKind=${show(shape.d.FieldTypeKind)} `
          + `Choices=${show(shape.d.Choices)} Indexed=${show(shape.d.Indexed)} `
          + `EnforceUniqueValues=${show(shape.d.EnforceUniqueValues)}`
        : `HTTP ${shape.status} — ${shape.error}`,
    );

    // === M3: which write shape does SharePoint take? =======================
    // R2 is the seeding row for this question because it has two members —
    // a one-member set cannot distinguish a collection from a scalar.
    const itemType = await entityTypeFor(PROBE_LIST);
    let winningShape = null;
    let winningError = '';
    for (const candidate of writeShapes) {
      const attempt = await post(`${listPath}/items`, {
        __metadata: { type: itemType },
        Title: ROWS[1].title,
        [MULTI]: candidate.build(ROWS[1].values),
        [SINGLE]: ROWS[1].values[0],
      });
      if (attempt.ok) { winningShape = candidate; break; }
      winningError += `${candidate.name}: HTTP ${attempt.status} ${attempt.error}; `;
    }
    record(
      'M3',
      'which item WRITE shape SharePoint accepts',
      winningShape ? `ACCEPTED: ${winningShape.name}` : 'ALL FOUR REFUSED',
      winningShape
        ? `tried in order ${writeShapes.map((s) => s.name).join(', ')}; ${winningShape.name} won. `
          + `Earlier refusals: ${winningError || '(none — the first shape worked)'}`
        : winningError,
    );
    if (!winningShape) {
      record('Q0', 'the fixture actually built', 'ABORTED', 'no write shape was accepted, so no fixture exists and no C row means anything');
      throw new Error('setup failed');
    }

    // Seed the remaining three rows with the shape that won.
    const seedErrors = [];
    for (const row of ROWS) {
      if (row.title === ROWS[1].title) continue;
      const body = { __metadata: { type: itemType }, Title: row.title };
      if (row.values.length) {
        body[MULTI] = winningShape.build(row.values);
        body[SINGLE] = row.values[0];
      }
      const seeded = await post(`${listPath}/items`, body);
      if (!seeded.ok) seedErrors.push(`${row.title}: HTTP ${seeded.status} ${seeded.error}`);
    }

    // === M4: what does it read back as? ====================================
    // Both content types, because the deployer speaks verbose and the reporting
    // layer's Power Query speaks nometadata, and they need not agree.
    const backVerbose = await get(`${listPath}/items?$select=Title,${odataName(MULTI)}&$orderby=Id`);
    const backNoMeta = await get(
      `${listPath}/items?$select=Title,${odataName(MULTI)}&$orderby=Id`,
      'application/json;odata=nometadata',
    );
    const verboseRows = backVerbose.d?.results || [];
    const noMetaRows = backNoMeta.d?.value || backNoMeta.d?.results || [];
    record(
      'M4',
      'what an item value READS BACK as',
      verboseRows.length ? 'READ' : 'UNREADABLE',
      `verbose: ${show(verboseRows.map((r) => ({ [r.Title]: r[MULTI] })))} || `
      + `nometadata: ${show(noMetaRows.map((r) => ({ [r.Title]: r[MULTI] })))}`,
    );

    // === Q0: the fixture control ===========================================
    // Asserted, because everything below DEPENDS on it. The seeded sets are
    // compared to what was asked for, by member and ignoring order — order is
    // M5's question, not this one.
    const sameMembers = (a, b) => {
      const norm = (v) => {
        if (v == null) return [];
        if (Array.isArray(v)) return [...v].sort();
        if (Array.isArray(v.results)) return [...v.results].sort();
        if (typeof v === 'string') return v.split(';#').filter(Boolean).sort();
        return [show(v)];
      };
      const [x, y] = [norm(a), norm(b)];
      return x.length === y.length && x.every((value, index) => value === y[index]);
    };
    const wrongRows = ROWS.filter((row) => {
      const got = verboseRows.find((r) => r.Title === row.title);
      return !got || !sameMembers(got[MULTI], row.values);
    });
    record(
      'Q0',
      'the fixture actually built: two fields, four rows, seeded sets as asked',
      (!seedErrors.length && !wrongRows.length && verboseRows.length === ROWS.length && createdSingle.ok)
        ? 'BUILT' : 'FAILED',
      `rows=${verboseRows.length}/${ROWS.length} single-value control field=${createdSingle.ok ? 'created' : 'FAILED'} `
      + `mismatched=${show(wrongRows.map((r) => r.title))} ${seedErrors.join('; ')}`,
    );
    if (wrongRows.length || verboseRows.length !== ROWS.length) {
      log('ERROR', 'The fixture is not what the C rows assume. Every predicate result below is meaningless until this is fixed.');
    }

    // === M5: idempotent re-write, and order ================================
    // The deployer's ONLY array comparator (Choices, in _field_reconcile) is
    // order-sensitive. If SharePoint normalises member order on write, a
    // re-run comparing exactly would see permanent drift.
    const r2 = verboseRows.find((r) => r.Title === ROWS[1].title);
    let m5detail = 'R2 was not readable';
    let m5observed = 'NOT ESTABLISHED';
    if (r2) {
      const reversed = [...ROWS[1].values].reverse();
      const rewritten = await merge(`${listPath}/items(${r2.Id})`, {
        __metadata: { type: itemType },
        [MULTI]: winningShape.build(reversed),
      });
      const after = await get(`${listPath}/items(${r2.Id})?$select=${odataName(MULTI)}`);
      m5observed = rewritten.ok ? 'REWRITTEN' : 'WRITE REFUSED';
      m5detail = rewritten.ok
        ? `wrote ${show(reversed)}; read back ${show(after.d?.[MULTI])}. `
          + 'If the readback is in the WRITTEN order, an exact comparison is safe; if it is normalised, '
          + 'the reconciler must compare as a SET or it will report drift on every redeploy.'
        : `HTTP ${rewritten.status} — ${rewritten.error}`;
      // Put R2 back the way the C rows expect it.
      if (rewritten.ok) {
        await merge(`${listPath}/items(${r2.Id})`, {
          __metadata: { type: itemType }, [MULTI]: winningShape.build(ROWS[1].values),
        });
      }
    }
    record('M5', 'a re-write round-trips, and member order survives', m5observed, m5detail);

    // === I1 / I1C: the index question, and its control =====================
    const indexOne = async (name, metaType) => {
      const wrote = await merge(fieldPath(name), { __metadata: { type: metaType }, Indexed: true });
      const back = await get(`${fieldPath(name)}?$select=Indexed`);
      return { wrote, readback: back.ok ? back.d.Indexed : '(unreadable)' };
    };
    const multiIndex = await indexOne(MULTI, 'SP.FieldMultiChoice');
    const singleIndex = createdSingle.ok
      ? await indexOne(SINGLE, 'SP.FieldChoice')
      : { wrote: { ok: false, status: 0, error: 'control field was never created' }, readback: '(not attempted)' };

    const controlHeld = singleIndex.wrote.ok && singleIndex.readback === true;
    record(
      'I1C',
      'CONTROL: Indexed:true on the SINGLE-value Choice, where Learn says it is supported',
      controlHeld ? 'STUCK' : 'DID NOT STICK',
      `write ${singleIndex.wrote.ok ? `HTTP ${singleIndex.wrote.status}` : `REFUSED ${singleIndex.wrote.error}`}, `
      + `readback Indexed=${show(singleIndex.readback)}`,
    );
    record(
      'I1',
      'Indexed:true on a MultiChoice — accepted? and what does it read back as?',
      controlHeld
        ? (multiIndex.wrote.ok
          ? (multiIndex.readback === true ? 'ACCEPTED AND STUCK' : 'ACCEPTED BUT DID NOT STICK')
          : 'REFUSED')
        : 'VOID',
      controlHeld
        ? `write ${multiIndex.wrote.ok ? `HTTP ${multiIndex.wrote.status}` : `REFUSED ${multiIndex.wrote.error}`}, `
          + `readback Indexed=${show(multiIndex.readback)}. `
          + 'REFUSED is the good outcome (loud). ACCEPTED BUT DID NOT STICK aborts a deploy part-way, which is '
          + 'survivable. ACCEPTED AND STUCK is the dangerous one: the property claims an index Learn says '
          + 'cannot exist, and nothing in a build or a deploy could ever see the difference.'
        : 'the single-value control did not stick either, so this property is not reporting what the question '
          + 'needs on this tenant and BOTH index rows are void — exactly the outcome native-index-probe.js hit '
          + 'with its ID control on 2026-07-30.',
    );

    // === I2: uniqueness ====================================================
    // Learn lists "Choice (multi-valued)" as unable to enforce unique values.
    // Whether REST refuses it or silently drops it decides whether the
    // validator's refusal is a convenience or a necessity.
    const uniqueWrite = await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' }, EnforceUniqueValues: true, Indexed: true,
    });
    const uniqueBack = await get(`${fieldPath(MULTI)}?$select=EnforceUniqueValues,Indexed`);
    record(
      'I2',
      'EnforceUniqueValues:true on a MultiChoice — accepted? readback?',
      uniqueWrite.ok ? (uniqueBack.d?.EnforceUniqueValues === true ? 'ACCEPTED AND STUCK' : 'ACCEPTED BUT DID NOT STICK') : 'REFUSED',
      uniqueWrite.ok
        ? `HTTP ${uniqueWrite.status}, readback EnforceUniqueValues=${show(uniqueBack.d?.EnforceUniqueValues)} `
          + `Indexed=${show(uniqueBack.d?.Indexed)}`
        : `HTTP ${uniqueWrite.status} — ${uniqueWrite.error}`,
    );
    // Leave the field in a known state for the C rows regardless of the above.
    await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' }, EnforceUniqueValues: false, Indexed: false,
    });

    // === C1..C7: which rows does each predicate actually return? ===========
    //
    // NOTHING HERE IS ASSERTED. Each row records the titles that came back and
    // the probe prints, beside them, the interpretation each possible answer
    // would carry. Writing the expected set into an assertion would make the
    // experiment fail the moment SharePoint answered something interesting,
    // which is the trap AGENTS.md names.
    //
    // The fixture, for reading the results:
    //   R1 {View}  R2 {View,Edit}  R3 {Edit,Export}  R4 {}
    const ref = `<FieldRef Name="${MULTI}"/>`;
    const textValue = (v) => `<Value Type="Text">${v}</Value>`;
    const predicates = [
      ['C1', 'Eq "View"', `<Eq>${ref}${textValue('View')}</Eq>`,
        'R1 only means Eq compares the WHOLE SET; R1+R2 means Eq behaves as "includes"; nothing means Eq is unusable here'],
      ['C2', 'Eq "View;#Edit"', `<Eq>${ref}${textValue('View;#Edit')}</Eq>`,
        'R2 only would mean the stored value is the ;#-delimited string and Eq matches it literally'],
      ['C3', 'Contains "View"', `<Contains>${ref}${textValue('View')}</Contains>`,
        'Learn documents Contains for Text/Note only. R1+R2 means it works anyway; nothing means it does not'],
      ['C4', 'Includes "View"', `<Includes>${ref}${textValue('View')}</Includes>`,
        'Learn documents Includes for multi-value LOOKUP only. R1+R2 means it also serves MultiChoice, which is '
        + 'the answer the condition grammar needs; nothing means the grammar has no membership operator at all'],
      ['C5', 'NotIncludes "View"', `<NotIncludes>${ref}${textValue('View')}</NotIncludes>`,
        'R3 only means the empty row R4 is EXCLUDED (three-valued, like every other CAML negative); R3+R4 means '
        + 'it is included. The deployer already wraps `neq` in <Or><IsNull> for exactly this reason'],
      ['C6', 'IsNull', `<IsNull>${ref}</IsNull>`, 'R4 only is the expected shape of a working null test'],
      ['C7', 'IsNotNull', `<IsNotNull>${ref}</IsNotNull>`, 'R1+R2+R3 is the expected shape'],
    ];
    const camlRows = async (where) => {
      const r = await post(`${listPath}/GetItems?$select=Title`, {
        query: {
          __metadata: { type: 'SP.CamlQuery' },
          ViewXml: `<View><Query><Where>${where}</Where></Query><RowLimit>50</RowLimit></View>`,
        },
      });
      if (!r.ok) return { ok: false, error: `HTTP ${r.status} ${r.error}`, titles: null };
      return { ok: true, error: null, titles: (r.d?.results || []).map((i) => i.Title).sort() };
    };
    let membershipWinner = null;
    for (const [id, label, where, meaning] of predicates) {
      const got = await camlRows(where);
      record(
        id,
        `CAML <${label.split(' ')[0]}> returns which rows`,
        got.ok ? 'RETURNED' : 'QUERY REFUSED',
        got.ok ? `${label} -> ${show(got.titles)} || ${meaning}` : `${label} -> ${got.error}`,
      );
      // Remember whichever membership predicate returned BOTH View-bearing
      // rows, for the stored-view confirmation in C8. Observed, not asserted:
      // if none does, C8 records that there was nothing to confirm.
      if (!membershipWinner && got.ok
          && got.titles.length === 2
          && got.titles.includes(ROWS[0].title) && got.titles.includes(ROWS[1].title)) {
        membershipWinner = { id, label, where };
      }
    }

    // === C8: does it survive being STORED? =================================
    // Every C row above used an ad-hoc CamlQuery. The deployer writes a VIEW's
    // ViewQuery, and SharePoint rewrites that XML on save — datetime-sentinel-
    // probe.js found an element that worked in one position and silently
    // returned nothing in the other. So the predicate that matters is stored,
    // read back, and looked at.
    if (membershipWinner) {
      const view = await post(`${listPath}/views`, {
        __metadata: { type: 'SP.View' },
        Title: 'Probe membership',
        ViewQuery: `<Where>${membershipWinner.where}</Where>`,
        RowLimit: 50,
      });
      const views = await get(`${listPath}/views?$select=Id,Title,ServerRelativeUrl,ViewQuery`);
      const stored = (views.d?.results || []).find((v) => v.Title === 'Probe membership');
      viewUrl = stored?.ServerRelativeUrl || null;
      if (stored) {
        await post(`${listPath}/views('${stored.Id}')/viewfields/addviewfield('${odataName(MULTI)}')`);
      }
      record(
        'C8',
        'the winning predicate survives being STORED as a view ViewQuery (manual: look)',
        view.ok && stored ? 'MANUAL' : 'NOT ESTABLISHED',
        view.ok && stored
          ? `stored ${membershipWinner.label}; SharePoint read the query back as ${show(stored.ViewQuery)}. `
            + `OPEN ${window.location.origin}${viewUrl} and confirm it lists exactly R1 and R2. `
            + 'A view that lists everything, or nothing, means the predicate does not survive storage and the '
            + 'condition grammar must refuse it however well GetItems behaved.'
          : `could not create or read the view: ${view.ok ? 'not found after create' : `HTTP ${view.status} ${view.error}`}`,
      );
    } else {
      record(
        'C8',
        'the winning predicate survives being STORED as a view ViewQuery',
        'NOT REACHED',
        'no predicate above returned exactly the two View-bearing rows, so there was nothing to confirm. '
        + 'That is itself the finding: the condition grammar would have no membership operator to render.',
      );
    }

    // === V1: validation formula operand ====================================
    // mapping.md already records that validation formulas refuse Lookup and
    // Person operands. Multi-value is not documented either way.
    const validation = await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' },
      ValidationFormula: `=NOT(ISBLANK([${MULTI}]))`,
      ValidationMessage: 'probe',
    });
    record(
      'V1',
      'a ValidationFormula may reference a MultiChoice column',
      validation.ok ? 'ACCEPTED' : 'REFUSED',
      validation.ok
        ? `HTTP ${validation.status} — accepted. NOTE this only shows SharePoint STORED it; whether the rule `
          + 'actually blocks a save is a separate observation, and an accepted-but-inert formula is the failure '
          + 'class this directory exists to catch.'
        : `HTTP ${validation.status} — ${validation.error}`,
    );
    if (validation.ok) {
      await merge(fieldPath(MULTI), {
        __metadata: { type: 'SP.FieldMultiChoice' }, ValidationFormula: '', ValidationMessage: '',
      });
    }

    // === F1: calculated-column operand =====================================
    // The same question calculated-operand-probe.js asked of every other type
    // on 2026-07-30, asked of the one type that did not exist then.
    const calc = await post(`${listPath}/fields`, {
      __metadata: { type: 'SP.FieldCalculated' },
      FieldTypeKind: 17,
      Title: 'CalcOverMulti',
      OutputType: 2,
      Formula: `=[${MULTI}]`,
    });
    record(
      'F1',
      'a calculated column formula may reference a MultiChoice column',
      calc.ok ? 'ACCEPTED' : 'REFUSED',
      calc.ok
        ? `HTTP ${calc.status} — accepted; the operand matrix in reference/dbml.md gains a row`
        : `HTTP ${calc.status} — ${calc.error}`,
    );

    // === X1: the formatter this repository actually generates ==============
    // Not an invented formatter — the exact shape analysis/styles.py::_severity
    // emits, with the =if(@currentField == 'X', ...) chain its _condition()
    // builds. Learn documents @currentField on a MultiChoice as an ARRAY, so
    // every branch of an == comparison against a quoted string should be false
    // and the cell should render unstyled. That is precisely the failure
    // STYLE_ON_BOOLEAN_MATCHES_NOTHING already names for Yes/No columns. This
    // asks whether the array case behaves the same way — and it can only be
    // answered by looking.
    const severityFormatter = {
      $schema: 'https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json',
      elmType: 'div',
      style: { display: "=if(@currentField == '', 'none', 'flex')", 'border-radius': '4px' },
      attributes: {
        class: "=if(@currentField == 'View', 'sp-field-severity--good', "
          + "if(@currentField == 'Edit', 'sp-field-severity--warning', 'ms-bgColor-neutralLight'))",
      },
      children: [{ elmType: 'span', txtContent: '@currentField' }],
    };
    const formatted = await merge(fieldPath(MULTI), {
      __metadata: { type: 'SP.FieldMultiChoice' },
      CustomFormatter: JSON.stringify(severityFormatter),
    });
    record(
      'X1',
      'the severity formatter this repo generates, on an array (manual: look)',
      formatted.ok ? 'MANUAL' : 'WRITE REFUSED',
      formatted.ok
        ? `OPEN ${window.location.origin}${listDefaultUrl || `${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`} `
          + `and look at the ${MULTI} column. Report THREE things: (a) does R1 {View} get a GREEN pill; `
          + '(b) does R2 {View,Edit} get any pill at all; (c) what TEXT does each cell show — both members, '
          + 'one member, or something like "View,Edit" run together. Anything other than a green pill on R1 '
          + 'means the existing severity machinery silently renders nothing on a multi-value column, and the '
          + 'specification needs a refusal rather than array-aware behaviour.'
        : `HTTP ${formatted.status} — ${formatted.error}`,
    );

    // === Verdict ===========================================================
    console.table(results.map(({ id, question, observed, detail }) => ({ id, question, observed, detail })));
    const fixtureOk = results.find((r) => r.id === 'Q0')?.observed === 'BUILT';
    log(
      'VERDICT',
      `fixture=${fixtureOk ? 'ok' : 'FAILED'} `
      + `create=${results.find((r) => r.id === 'M1').observed} `
      + `write_shape=${winningShape ? winningShape.name : 'none'} `
      + `indexed=${results.find((r) => r.id === 'I1').observed} `
      + `unique=${results.find((r) => r.id === 'I2').observed} `
      + `validation=${results.find((r) => r.id === 'V1').observed} `
      + `calculated=${results.find((r) => r.id === 'F1').observed}`,
    );
    log(
      'VERDICT',
      `caml_membership=${membershipWinner ? membershipWinner.label : 'NONE FOUND'} `
      + 'stored_view=<fill in after looking> formatter=<fill in after looking>',
    );
    if (!fixtureOk) {
      log('ERROR', 'fixture=FAILED — the C rows assume four rows with known sets, so their answers mean nothing from this run. Fix the fixture and re-run before reporting.');
    }
    log('INFO', 'Paste both VERDICT lines back, with the two <fill in> values set after doing the manual steps.');
    return { results, winningShape: winningShape?.name || null, viewUrl };
  } finally {
    if (createdList && CLEANUP_AT_END) {
      const gone = await post(listPath, undefined, { 'X-HTTP-Method': 'DELETE', 'IF-MATCH': '*' });
      if (gone.ok) {
        log('INFO', `Deleted '${PROBE_LIST}'.`);
      } else {
        log('ERROR', `COULD NOT DELETE '${PROBE_LIST}' (HTTP ${gone.status} ${gone.error}). Delete it by hand: ${window.location.origin}${WEB}/Lists/${encodeURIComponent(PROBE_LIST)}`);
      }
    } else if (createdList) {
      log('INFO', `Left '${PROBE_LIST}' in place for the manual steps (X1 and C8). Re-run with CLEANUP_AT_END = true to remove it.`);
    }
  }
})();
