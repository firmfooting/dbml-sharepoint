/**
 * dbml-sharepoint CLOCK VERIFICATION script (WRITES TO ONE SCRATCH LIST).
 * Generated from: simple.dbml
 * Target site:  https://example.sharepoint.com/sites/test
 * Site role:    default
 * Release tag:  0.1.0-test
 * Schema:       v0.8
 * Deployer:     vdbml-sharepoint/0.1.0
 * Generated at: 2026-05-04T00:00:00Z
 *
 * Exercises every clock cell this pack uses (a `today` or `now` rule, a
 * `today` view window, a `[today]` default) on a hidden scratch list named
 * `_dbml-verify`, and prints a VERIFIED /
 * MISMATCH / NOT-VERIFIED verdict. It creates that list if absent, reuses it
 * when its Description carries the tool's marker, and never touches any
 * other list. Paste after deploy.js.txt, on the same site.
 */
(async () => {
  const SITE_URL = "https://example.sharepoint.com/sites/test";
  const TARGETS = {
  "checks": [
    {
      "cell": "caml/date/today_offset",
      "element": "\u003cValue Type=\"DateTime\"\u003e\u003cToday OffsetDays=\"30\"/\u003e\u003c/Value\u003e",
      "expect": [
        "cd-day-30"
      ],
      "field": "CD",
      "key": "caml_date_today_offset_30",
      "kind": "query",
      "op": "Eq"
    },
    {
      "cell": "formula-clock",
      "column": {
        "default_formula": "=TODAY()",
        "display_format": 0,
        "kind": "date",
        "name": "LT"
      },
      "key": "formula_clock_lag",
      "kind": "lag",
      "row": "lt-bare"
    }
  ],
  "columns": [
    {
      "display_format": 0,
      "kind": "date",
      "name": "CD"
    },
    {
      "default_formula": "=TODAY()",
      "display_format": 0,
      "kind": "date",
      "name": "LT"
    }
  ],
  "list_title": "_dbml-verify",
  "marker": "Provisioned by dbml-sharepoint for scratch _dbml-verify.",
  "rows": [
    {
      "column": "CD",
      "id": "cd-day--1",
      "value": {
        "days": -1,
        "kind": "midnight"
      }
    },
    {
      "column": "CD",
      "id": "cd-day-0",
      "value": {
        "days": 0,
        "kind": "midnight"
      }
    },
    {
      "column": "CD",
      "id": "cd-day-1",
      "value": {
        "days": 1,
        "kind": "midnight"
      }
    },
    {
      "column": "CD",
      "id": "cd-day-30",
      "value": {
        "days": 30,
        "kind": "midnight"
      }
    },
    {
      "column": "LT",
      "id": "lt-bare",
      "value": {
        "kind": "none"
      }
    }
  ],
  "rule": null
};

  const log = (level, msg) => console.log(`[SP-VERIFY] [${level}] ${msg}`);

  // === Preflight: site match ===
  // SP REST '/_api/...' is routed by the path prefix BEFORE '_api'. A bare
  // '/_api/web/...' targets the tenant root web, NOT the sub-site or site
  // collection you're viewing. Every API call is prefixed with the current
  // web's server-relative URL so calls hit the web the operator is on.
  const expectedOrigin = new URL(SITE_URL).origin;
  const expectedPath = new URL(SITE_URL).pathname.replace(/\/$/, '');
  const actualOrigin = window.location.origin;
  if (typeof _spPageContextInfo === 'undefined') {
    log('ERROR', '_spPageContextInfo is not available on this page; cannot resolve the SharePoint web context. Aborting.');
    return { aborted: 'no-sp-page-context' };
  }
  const actualPath = (_spPageContextInfo.webServerRelativeUrl || '').replace(/\/$/, '');
  if (actualOrigin !== expectedOrigin || actualPath !== expectedPath) {
    log('ERROR', `Site mismatch. Expected ${expectedOrigin}${expectedPath}, found ${actualOrigin}${actualPath}.`);
    return { aborted: 'site-mismatch', expected: SITE_URL, actual: `${actualOrigin}${actualPath}` };
  }
  const WEB = actualPath;  // '' for the tenant root, '/sites/foo' for a site collection, etc.
  const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
  // OData string-literal encoder: SharePoint getbytitle/getbyname take a
  // single-quoted OData literal, where an embedded apostrophe must be
  // DOUBLED (`''`); encodeURIComponent alone does not escape `'`.
  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  log('INFO', `Running as ${(_spPageContextInfo.userLoginName) || '(unknown)'} on web '${WEB || '(root)'}'.`);

  // Flip to true for per-request timing diagnostics (method, URL, status,
  // ms). Default false keeps the console readable; edit in the pasted
  // script (no rebuild needed). deploy.js.txt additionally prints a per-phase
  // seconds table before DONE when this is on.
  const DEBUG = false;
  const dbg = (msg) => { if (DEBUG) log('DEBUG', msg); };
  let requestCount = 0;
  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

  // SharePoint's REST error body carries the human-readable reason at
  // error.message.value; fall back to (bounded) raw text. A bare HTTP
  // status left a blocked run undiagnosable (live finding 2026-07-24).
  const spError = (text) => {
    let message = text;
    try {
      message = JSON.parse(text)?.error?.message?.value || text;
    } catch {}
    return String(message).slice(0, 300);
  };

  // Retry-After-aware fetch. Honour the server's Retry-After (seconds),
  // else back off exponentially (capped), up to `attempts` before
  // returning the final response to the caller's own error handling.
  async function fetchWithRetry(url, opts, attempts = 5) {
    const t0 = Date.now();
    for (let i = 0; ; i++) {
      const r = await fetch(url, opts);
      requestCount += 1;
      if ((r.status === 429 || r.status === 503) && i < attempts) {
        const ra = Number(r.headers.get('Retry-After')) || Math.min(2 ** i, 30);
        log('INFO', `Throttled (HTTP ${r.status}); retry ${i + 1}/${attempts} in ${ra}s.`);
        await sleep(ra * 1000);
        continue;
      }
      dbg(`${(opts && opts.method) || 'GET'} ${url.length > 160 ? `${url.slice(0, 160)}...` : url} -> ${r.status} in ${Date.now() - t0}ms${i > 0 ? ` (${i} throttle retries)` : ''}`);
      return r;
    }
  }
  // Verbose-OData headers for SP writes; `extra` carries method overrides
  // such as { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }.
  const spHeaders = (digest, extra = {}) => ({
    'Accept': 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
    'X-RequestDigest': digest,
    ...extra,
  });
  log('INFO', `Writes only to the scratch list '${TARGETS.list_title}'. No declared list is touched.`);

  let cachedDigest = null;
  let digestExpiresAt = 0;
  // The one place any script parses a contextinfo response; a second copy of that parse is what reported #282 as a TypeError.
  async function getContextWebInformation() {
    // The bound spError applies, for a failure arriving as a rejection rather than as an error body.
    const bounded = (e) => String((e && e.message) || e).slice(0, 300);
    const failed = (detail) => new Error(`contextinfo (request digest) failed: ${detail}`);
    let r;
    try {
      r = await fetchWithRetry(apiUrl('contextinfo'), {
        method: 'POST',
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
    } catch (err) {
      // fetch rejects outright on a network or CORS failure, so there is no status to report, only the operation.
      throw failed(`no response (${bounded(err)})`);
    }
    // Preserve the operation and status even when the refused body is unreadable (#282).
    if (!r.ok) {
      const body = await r.text().catch((e) => `body unreadable: ${bounded(e)}`);
      throw failed(`HTTP ${r.status} ${spError(body)}`);
    }
    let info = null;
    try {
      info = (await r.json())?.d?.GetContextWebInformation;
    } catch (err) {
      throw failed(`HTTP ${r.status} with an unreadable body (${bounded(err)})`);
    }
    // A 200 carrying no GetContextWebInformation is the same blind dereference one status code further along.
    if (!info || typeof info !== 'object' || Array.isArray(info)) {
      throw failed(`HTTP ${r.status} carried no GetContextWebInformation`);
    }
    if (typeof info.FormDigestValue !== 'string' || !info.FormDigestValue.trim()) {
      throw failed(`HTTP ${r.status} carried no usable FormDigestValue`);
    }
    return info;
  }
  async function getDigest() {
    if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;
    let info;
    try {
      info = await getContextWebInformation();
    } catch (err) {
      const failure = err instanceof Error ? err : new Error(String(err));
      failure.digestFailure = true;
      throw failure;
    }
    cachedDigest = info.FormDigestValue;
    const timeoutSeconds = Number(info.FormDigestTimeoutSeconds) || 1800;
    digestExpiresAt = Date.now() + Math.max(timeoutSeconds - 60, 60) * 1000;
    return cachedDigest;
  }
  // SharePoint stores a calculated field's Formula in the field schema XML
  // and returns it with XML character entities intact (`<>` reads back as
  // `&lt;&gt;`), so a byte comparison never converges: the drift MERGE
  // rewrites the identical formula and the readback still "differs". Compare
  // formulas on their XML-decoded canonical form (both sides), so encoded
  // and decoded readbacks both match. `&amp;` decodes LAST: decoding it
  // earlier would corrupt double-encoded text (`&amp;lt;` must yield the
  // literal `&lt;`, not `<`).
  const xmlDecode = (value) => String(value)
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&apos;/g, "'")
    .replace(/&amp;/g, '&');

  // A second storage canonicalisation (PnP provisioning documents the same
  // trap): SharePoint strips square brackets from column references that do
  // not need delimiting: `[Likelihood]` is stored and read back as
  // `Likelihood`; names with spaces keep their brackets. Strip removable
  // brackets on both sides, but only OUTSIDE string literals (split keeps
  // `"..."` tokens, with `""` as the escaped quote, at odd indices):
  // bracket text inside a quoted constant is data, not a reference.
  const canonicalFormula = (value) => xmlDecode(typeof value === 'string' ? value : '')
    .split(/("(?:""|[^"])*")/)
    .map((token, i) => (i % 2 === 1 ? token : token.replace(/\[([A-Za-z0-9_]+)\]/g, '$1')))
    .join('');

  async function verifySite(ctx) {
    const { targets: T, log, fetchWithRetry, apiUrl, odataName, getDigest, spHeaders,
            spError, canonicalFormula, verdictLevel } = ctx;
    // Fail closed on a caller-built targets or a missing collaborator: a
    // missing key is a bare TypeError several checks in.
    const missingTargets = ['list_title', 'marker', 'columns', 'rows', 'checks', 'rule']
      .filter((k) => !(k in (T || {})));
    if (missingTargets.length) throw new Error(`verify-targets-incomplete: ctx.targets is missing ${missingTargets.join(', ')}`);
    const missingCollaborators = ['log', 'fetchWithRetry', 'apiUrl', 'odataName', 'getDigest',
      'spHeaders', 'spError', 'canonicalFormula',
    ].filter((k) => typeof ctx[k] !== 'function');
    if (missingCollaborators.length) throw new Error(`verify-context-incomplete: ctx is missing ${missingCollaborators.join(', ')}`);

    const findings = [];
    const finding = (key, level, detail, cell) => {
      findings.push({ key, level, detail, cell: cell || null });
      log(level, `${key}${cell ? ` [${cell}]` : ''}: ${detail}`);
    };

    // ---- Transport ------------------------------------------------------
    // Every answer is kept, not thrown: a refusal is the finding.
    const request = async (method, suffix, body, extra) => {
      const digest = await getDigest();
      const r = await fetchWithRetry(apiUrl(suffix), {
        method, headers: spHeaders(digest, extra || {}),
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      const text = await r.text();
      let parsed = null;
      try { parsed = JSON.parse(text); } catch (err) { parsed = { unparsed: String(err.message) }; }
      const d = parsed && parsed.d !== undefined ? parsed.d : parsed;
      return { ok: r.ok, status: r.status, text, d, reason: r.ok ? '' : spError(text) };
    };
    const readJson = async (suffix) => {
      const r = await fetchWithRetry(apiUrl(suffix), { headers: { 'Accept': 'application/json;odata=verbose' } });
      const text = await r.text();
      let parsed = null;
      try { parsed = JSON.parse(text); } catch (err) { parsed = { unparsed: String(err.message) }; }
      return { ok: r.ok, status: r.status, d: parsed && parsed.d !== undefined ? parsed.d : parsed, reason: r.ok ? '' : spError(text) };
    };
    const merge = (suffix, body) => request('POST', suffix, body, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' });
    // 401/403 are about who is asking, 408/429 about the moment: never a
    // refusal of the content. Everything else non-2xx is the server saying no.
    const isRefusal = (status) => status >= 400 && ![401, 403, 408, 429].includes(status);
    const outcomeOf = (r) => (r.ok ? 'saved' : isRefusal(r.status) ? 'refused' : 'failed');

    // ---- 1. The site's zone, and whether this browser shares it --------
    // A date-only value is site-local midnight, so the boundary values are
    // built from the site's own offset. SharePoint reports both biases
    // without saying which is in force, so both are candidates; if this
    // browser matches neither, the date cases cannot be placed exactly and
    // are reported NOT-ASSESSABLE rather than guessed.
    const tz = await readJson('web/regionalsettings/timezone');
    const info = (tz.ok && tz.d && tz.d.Information) || null;
    let siteOffset = null;
    if (!info) {
      finding('site_zone', 'NOT-ASSESSABLE', 'web/regionalsettings/timezone did not report a zone; every date case needs the site\'s midnight and is skipped.');
    } else {
      const offsets = [...new Set([
        -(info.Bias + (info.StandardBias || 0)),
        -(info.Bias + (info.DaylightBias || 0)),
      ])];
      const browser = -new Date().getTimezoneOffset();
      const spell = (m) => `${m >= 0 ? '+' : ''}${m} min`;
      const zone = `Site time zone "${tz.d.Description || '(no description)'}" (UTC ${offsets.map(spell).join(' / ')}); this browser is UTC ${spell(browser)}.`;
      if (offsets.includes(browser)) {
        siteOffset = browser;
        finding('site_zone', 'PASS', `${zone} They agree, so site-local midnights are built from this browser's offset.`);
      } else {
        finding('site_zone', 'NOT-ASSESSABLE', `${zone} They differ, so which of the site's offsets is in force is unknown; every date case is skipped. Paste from a browser in the site's zone.`);
      }
    }
    const midnightUtc = (days) => {
      const shifted = new Date(Date.now() + siteOffset * 60000);
      const utcMidnight = Date.UTC(shifted.getUTCFullYear(), shifted.getUTCMonth(), shifted.getUTCDate() + days);
      return new Date(utcMidnight - siteOffset * 60000).toISOString();
    };
    const instantUtc = (seconds) => new Date(Date.now() + seconds * 1000).toISOString();
    const siteDateOf = (iso) => new Date(new Date(iso).getTime() + (siteOffset || 0) * 60000).toISOString().slice(0, 10);
    // null when the value cannot be placed on this browser.
    const valueFor = (spec) => {
      if (spec.kind === 'instant') return instantUtc(spec.seconds);
      if (spec.kind === 'midnight') return siteOffset === null ? null : midnightUtc(spec.days);
      return undefined;
    };

    // ---- 2. The scratch list ----------------------------------------------
    // One enumeration answers absence without a red 404, and carries the
    // Description the ownership guard compares whole: a list of this title
    // that is not exactly the tool's is somebody's, and the run stops.
    const listPath = `web/lists/getbytitle('${odataName(T.list_title)}')`;
    const listing = await readJson('web/lists?$select=Title,Hidden,Description&$top=5000');
    if (!listing.ok) {
      finding('scratch_list', 'NOT-ASSESSABLE', `Could not enumerate lists (HTTP ${listing.status} ${listing.reason}); nothing was verified.`);
      return { findings, verdict: 'NOT-VERIFIED', aborted: 'lists-unreadable' };
    }
    const lists = (listing.d && listing.d.results) || [];
    const wanted = T.list_title.toLowerCase();
    const found = lists.find((l) => String(l.Title || '').toLowerCase() === wanted) || null;
    let hidden = null;
    if (found) {
      if (String(found.Description || '') !== T.marker) {
        finding('scratch_list', 'FAIL', `A list titled '${T.list_title}' exists and its Description is not this tool's marker. It is not touched; rename or remove it and paste again.`);
        return { findings, verdict: 'NOT-VERIFIED', aborted: 'foreign-list' };
      }
      hidden = Boolean(found.Hidden);
      finding('scratch_list', 'PASS', `Reusing '${T.list_title}' (marker matched).`);
    } else {
      const made = await request('POST', 'web/lists', {
        __metadata: { type: 'SP.List' }, BaseTemplate: 100, Title: T.list_title,
        Description: T.marker, Hidden: true,
      });
      if (!made.ok) {
        finding('scratch_list', 'NOT-ASSESSABLE', `Could not create '${T.list_title}' (HTTP ${made.status} ${made.reason}); nothing was verified.`);
        return { findings, verdict: 'NOT-VERIFIED', aborted: 'list-create-failed' };
      }
      const back = await readJson(`${listPath}?$select=Hidden`);
      hidden = Boolean(back.ok && back.d && back.d.Hidden);
      finding('scratch_list', 'PASS', `Created '${T.list_title}' with the tool's marker.`);
    }
    // Hidden is what keeps the list out of Site contents and the lookup
    // picker; creating one hidden over REST is unmeasured, so what came
    // back is reported rather than assumed.
    finding('scratch_list_hidden', 'INFO', hidden
      ? 'The scratch list reads back Hidden, so it stays out of Site contents.'
      : 'The scratch list reads back VISIBLE; it will appear in Site contents until hidden by hand.');
    const entity = await readJson(`${listPath}?$select=ListItemEntityTypeFullName`);
    const itemType = (entity.ok && entity.d && entity.d.ListItemEntityTypeFullName) || null;
    if (!itemType) {
      finding('scratch_list', 'NOT-ASSESSABLE', `Could not read the list's item type (HTTP ${entity.status} ${entity.reason}); nothing was verified.`);
      return { findings, verdict: 'NOT-VERIFIED', aborted: 'item-type-unreadable' };
    }

    // ---- 3. Columns and the list rule ----------------------------------------
    const fieldsPath = `${listPath}/fields`;
    const have = await readJson(`${fieldsPath}?$select=InternalName&$top=500`);
    const present = new Set(((have.ok && have.d && have.d.results) || []).map((f) => String(f.InternalName).toLowerCase()));
    const unavailable = new Set();
    for (const col of T.columns) {
      if (present.has(col.name.toLowerCase())) continue;
      const body = col.kind === 'calculated_date'
        ? { __metadata: { type: 'SP.FieldCalculated' }, FieldTypeKind: 17, Title: col.name, Formula: col.formula, OutputType: 4 }
        : { __metadata: { type: 'SP.FieldDateTime' }, FieldTypeKind: 4, Title: col.name, DisplayFormat: col.display_format };
      if (col.default_value) body.DefaultValue = col.default_value;
      if (col.default_formula) body.DefaultFormula = col.default_formula;
      const made = await request('POST', fieldsPath, body);
      if (!made.ok) {
        unavailable.add(col.name);
        finding(`column_${col.name}`, 'NOT-ASSESSABLE', `Could not create column ${col.name} (${col.kind}): HTTP ${made.status} ${made.reason}. Its checks are skipped.`);
      }
    }
    if (T.rule) {
      const set = await merge(listPath, {
        __metadata: { type: 'SP.List' }, ValidationFormula: T.rule.formula, ValidationMessage: T.rule.message,
      });
      const back = await readJson(`${listPath}?$select=ValidationFormula`);
      const stored = back.ok && back.d ? back.d.ValidationFormula : null;
      const same = set.ok && stored !== null && canonicalFormula(stored) === canonicalFormula(T.rule.formula);
      finding('list_rule', same ? 'PASS' : 'FAIL', same
        ? `The joined list rule is stored: ${stored}`
        : `The joined list rule did not store as written (HTTP ${set.status} ${set.reason}); stored: ${stored}`);
      if (!same) {
        for (const check of T.checks.filter((c) => c.kind === 'save')) unavailable.add(check.column.name);
      }
    }

    // ---- 4. Rows: recycle this run's rows where the site allows ----------------
    const itemsPath = `${listPath}/items`;
    const existing = await readJson(`${itemsPath}?$select=Id,Title&$top=5000`);
    const byTitle = new Map();
    for (const row of (existing.ok && existing.d && existing.d.results) || []) byTitle.set(String(row.Title), row.Id);
    let recycled = 0;
    let kept = 0;
    const ownTitles = new Set([
      ...T.rows.map((r) => r.id),
      ...T.checks.filter((c) => c.kind === 'save').flatMap((c) => c.cases.map((k) => `${c.key}:${k.id}`)),
    ]);
    for (const [title, id] of byTitle) {
      if (!ownTitles.has(title)) continue;
      const gone = await request('POST', `${itemsPath}(${id})/recycle`, {});
      if (gone.ok) { byTitle.delete(title); recycled += 1; } else { kept += 1; }
    }
    if (recycled || kept) {
      finding('rows_recycled', 'INFO', `${recycled} row(s) from an earlier run recycled${kept ? `; ${kept} could not be and are updated in place` : ''}.`);
    }
    // Create or update one item; returns the transport answer plus its id.
    const save = async (title, column, value) => {
      const body = { __metadata: { type: itemType }, Title: title };
      if (column && value !== undefined) body[column] = value;
      const id = byTitle.get(title);
      if (id !== undefined) {
        const r = await merge(`${itemsPath}(${id})`, body);
        return { ...r, id, updated: true };
      }
      const r = await request('POST', itemsPath, body);
      const newId = r.ok && r.d && r.d.Id;
      if (newId) byTitle.set(title, newId);
      return { ...r, id: newId || null, updated: false };
    };
    const placed = new Set();
    for (const row of T.rows) {
      if (unavailable.has(row.column)) continue;
      const value = valueFor(row.value);
      if (value === null) continue;
      const r = await save(row.id, row.column, value);
      if (r.ok) placed.add(row.id);
      else finding(`row_${row.id}`, 'NOT-ASSESSABLE', `Could not place row ${row.id} (${row.column} = ${value}): HTTP ${r.status} ${r.reason}.`);
    }

    // ---- 5. The checks --------------------------------------------------------
    for (const check of T.checks) {
      if (check.kind === 'save') {
        if (unavailable.has(check.column.name)) {
          finding(check.key, 'NOT-ASSESSABLE', `Column ${check.column.name} is not available on the scratch list.`, check.cell);
          continue;
        }
        const ids = new Map();
        for (const kase of check.cases) {
          const key = `${check.key}.${kase.id}`;
          const value = valueFor(kase.value);
          if (value === null) {
            finding(key, 'NOT-ASSESSABLE', `${kase.op} ${check.column.name} = site-local midnight ${kase.value.days >= 0 ? '+' : ''}${kase.value.days} d needs the site's zone.`, check.cell);
            continue;
          }
          let r;
          if (kase.op === 'update') {
            const target = ids.get(kase.on);
            if (!target) {
              finding(key, 'NOT-ASSESSABLE', `The row to update (${kase.on}) was not created in this run.`, check.cell);
              continue;
            }
            const body = { __metadata: { type: itemType } };
            body[check.column.name] = value;
            r = await merge(`${itemsPath}(${target})`, body);
          } else {
            r = await save(`${check.key}:${kase.id}`, check.column.name, value);
            if (r.ok && r.id) ids.set(kase.id, r.id);
          }
          const outcome = outcomeOf(r);
          const detail = `${kase.op} ${check.column.name} = ${value} under ${check.clause}: ${outcome.toUpperCase()}${r.ok ? '' : ` (HTTP ${r.status} ${r.reason})`}`;
          if (outcome === 'failed') finding(key, 'NOT-ASSESSABLE', detail, check.cell);
          else if (kase.expect === 'info') finding(key, 'INFO', detail, check.cell);
          else {
            const wanted = kase.expect === 'save' ? 'saved' : 'refused';
            finding(key, outcome === wanted ? 'PASS' : 'FAIL', `${detail}; expected ${wanted.toUpperCase()}.`, check.cell);
          }
        }
      } else if (check.kind === 'query') {
        if (unavailable.has(check.field) || siteOffset === null) {
          finding(check.key, 'NOT-ASSESSABLE', unavailable.has(check.field)
            ? `Column ${check.field} is not available on the scratch list.`
            : 'The rows this query reads are placed at site-local midnights, which need the site\'s zone.', check.cell);
          continue;
        }
        const viewXml = `<View><ViewFields><FieldRef Name='Title'/><FieldRef Name='ID'/></ViewFields><Query><Where><${check.op}><FieldRef Name='${check.field}'/>${check.element}</${check.op}></Where></Query><RowLimit>500</RowLimit></View>`;
        const r = await request('POST', `${listPath}/getitems`, {
          query: { __metadata: { type: 'SP.CamlQuery' }, ViewXml: viewXml },
        });
        if (!r.ok) {
          finding(check.key, 'NOT-ASSESSABLE', `The query was not answered (HTTP ${r.status} ${r.reason}).`, check.cell);
          continue;
        }
        const prefix = check.field === 'CW' ? 'cw-' : 'cd-';
        const got = ((r.d && r.d.results) || []).map((x) => String(x.Title)).filter((t) => t.startsWith(prefix) && placed.has(t)).sort();
        const expect = check.expect.filter((t) => placed.has(t)).sort();
        const same = got.length === expect.length && got.every((t, i) => t === expect[i]);
        finding(check.key, same ? 'PASS' : 'FAIL',
          `${check.op} ${check.field} ${check.element} returned [${got.join(', ')}]; expected [${expect.join(', ')}].`, check.cell);
      } else if (check.kind === 'default') {
        if (unavailable.has(check.column.name) || !placed.has(check.row)) {
          finding(check.key, 'NOT-ASSESSABLE', `The bare row for ${check.column.name} was not placed.`, check.cell);
          continue;
        }
        if (check.method === 'today-query') {
          if (siteOffset === null) {
            finding(check.key, 'NOT-ASSESSABLE', 'Reading the default against the site\'s day needs the site\'s zone.', check.cell);
            continue;
          }
          const viewXml = `<View><ViewFields><FieldRef Name='Title'/></ViewFields><Query><Where><Eq><FieldRef Name='${check.column.name}'/><Value Type='DateTime'><Today/></Value></Eq></Where></Query><RowLimit>500</RowLimit></View>`;
          const r = await request('POST', `${listPath}/getitems`, { query: { __metadata: { type: 'SP.CamlQuery' }, ViewXml: viewXml } });
          const titles = ((r.ok && r.d && r.d.results) || []).map((x) => String(x.Title));
          const hit = titles.includes(check.row);
          finding(check.key, r.ok ? (hit ? 'PASS' : 'FAIL') : 'NOT-ASSESSABLE', r.ok
            ? `A bare create filled ${check.column.name} with [today]; Eq <Today/> ${hit ? 'returns' : 'does not return'} it, so the default ${hit ? 'is' : 'is not'} the site's date.`
            : `The query was not answered (HTTP ${r.status} ${r.reason}).`, check.cell);
        } else {
          const id = byTitle.get(check.row);
          const back = await readJson(`${itemsPath}(${id})?$select=${check.column.name},Modified`);
          const filled = back.ok && back.d ? back.d[check.column.name] : null;
          const modified = back.ok && back.d ? back.d.Modified : null;
          const gap = filled && modified ? Math.abs(new Date(filled) - new Date(modified)) / 1000 : null;
          finding(check.key, gap === null ? 'NOT-ASSESSABLE' : gap <= 600 ? 'PASS' : 'FAIL',
            gap === null ? `Could not read the bare row back (HTTP ${back.status} ${back.reason}).`
              : `A bare create filled ${check.column.name} = ${filled}, ${Math.round(gap)} s from Modified ${modified}.`, check.cell);
        }
      } else if (check.kind === 'lag') {
        if (unavailable.has(check.column.name) || !placed.has(check.row) || siteOffset === null) {
          finding(check.key, 'NOT-ASSESSABLE', 'The =TODAY() default row was not placed, or the site\'s zone is unknown.', check.cell);
          continue;
        }
        const id = byTitle.get(check.row);
        const back = await readJson(`${itemsPath}(${id})?$select=${check.column.name},Modified`);
        const filled = back.ok && back.d ? back.d[check.column.name] : null;
        const modified = back.ok && back.d ? back.d.Modified : null;
        if (!filled || !modified) {
          finding(check.key, 'NOT-ASSESSABLE', `Could not read the =TODAY() default back (HTTP ${back.status} ${back.reason}).`, check.cell);
          continue;
        }
        const siteDay = siteDateOf(modified);
        const formulaDay = siteDateOf(filled);
        const behind = Math.round((Date.parse(siteDay) - Date.parse(formulaDay)) / 86400000);
        finding(check.key, 'INFO', behind === 0
          ? `TODAY() in a formula resolved to ${formulaDay}, the site's date.`
          : `TODAY() in a formula resolved to ${formulaDay} while the site's date was ${siteDay}: the formula clock is ${behind} day(s) behind at this hour. The build compares date rules with the save instant for this reason.`, check.cell);
      }
    }

    // ---- 6. Verdict ------------------------------------------------------------
    // Conservative on purpose: a check nobody could make is not a pass, so
    // an unassessed check keeps the verdict at NOT-VERIFIED.
    const levels = findings.map((f) => f.level);
    let verdict;
    if (levels.includes('FAIL')) verdict = 'MISMATCH';
    else if (!levels.includes('PASS') || levels.includes('NOT-ASSESSABLE')) verdict = 'NOT-VERIFIED';
    else verdict = 'VERIFIED';
    console.log('\n==================== VERIFY ====================');
    for (const f of findings) {
      console.log(`${f.level.padEnd(15)} ${f.key}${f.cell ? ` [${f.cell}]` : ''}`);
      console.log(`       ${f.detail}`);
    }
    console.log('================================================');
    const counts = ['PASS', 'FAIL', 'NOT-ASSESSABLE', 'INFO'].map((l) => `${levels.filter((x) => x === l).length} ${l}`).join(', ');
    if (verdict === 'MISMATCH') {
      log(verdictLevel, `${T.list_title}: MISMATCH (${counts}). A clock cell this pack relies on does not behave on this site as measured; read the FAIL lines before trusting the deployed rules.`);
    } else if (verdict === 'NOT-VERIFIED') {
      log(verdictLevel, `${T.list_title}: NOT-VERIFIED (${counts}). Something could not be assessed; the site is not shown wrong, and not shown right either.`);
    } else {
      log(verdictLevel, `${T.list_title}: VERIFIED (${counts}). Every clock cell this pack uses behaves on this site as measured.`);
    }
    return { findings, verdict, list: T.list_title };
  }

  let summary;
  // A throw is a broken probe, not a verdict; NOT-VERIFIED, because a site
  // nobody could exercise has verified nothing.
  try {
    summary = await verifySite({
      targets: TARGETS, log, web: WEB, fetchWithRetry, apiUrl, odataName,
      getDigest, spHeaders, spError, canonicalFormula, verdictLevel: 'DONE',
    });
  } catch (err) {
    log('ERROR', `The verification could not run (${err.message}); nothing was verified.`);
    summary = { findings: [], verdict: 'NOT-VERIFIED', aborted: 'verification-failed' };
  }
  console.log(summary);
  return summary;
})();
