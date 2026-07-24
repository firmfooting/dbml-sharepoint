/**
 * dbml-sharepoint deployment script.
 * Generated from: simple.dbml (mtime: 2026-05-04T00:00:00Z)
 * Target site:  https://example.sharepoint.com/sites/test
 * Site role:    default
 * Release tag:  0.1.0-test
 * Schema:       v0.8
 * Deployer:     vdbml-sharepoint/0.1.0
 * Generated at: 2026-05-04T00:00:00Z
 *
 * Paste into the SharePoint browser console and press Enter.
 * Wait for the [SP-DEPLOY] [DONE] log line.
 */
(async () => {
  const SITE_URL  = "https://example.sharepoint.com/sites/test";
  const SITE_ROLE = "default";
  const RELEASE_TAG = "0.1.0-test";
  const SCHEMA_VERSION = "0.8";

  const log = (level, msg) => console.log(`[SP-DEPLOY] [${level}] ${msg}`);
  const RUN_STARTED_AT = Date.now();
  // Phase timings record on every run (cheap); they only PRINT under
  // DEBUG (declared in the shared HTTP partial included below).
  const phaseTimings = {};
  let currentPhaseLabel = null;
  let currentPhaseT0 = 0;
  const markPhase = (label) => {
    if (currentPhaseLabel) {
      phaseTimings[currentPhaseLabel] = (phaseTimings[currentPhaseLabel] || 0) + (Date.now() - currentPhaseT0);
    }
    currentPhaseLabel = label;
    currentPhaseT0 = Date.now();
  };
  const summary = {
    listsCreated: [],
    listsSkipped: [],
    columnsCreated: 0,
    columnsSkipped: 0,
    errors: [],
    releaseTag: RELEASE_TAG,
    schemaVersion: SCHEMA_VERSION,
  };


  // === Preflight: site match ===
  // SP REST '/_api/...' is routed by the path prefix BEFORE '_api'. A bare
  // '/_api/web/...' targets the tenant root web — NOT the sub-site or site
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
  // DOUBLED (`''`); encodeURIComponent alone does not escape `'` (A5).
  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  log('INFO', `Running as ${(_spPageContextInfo.userLoginName) || '(unknown)'} on web '${WEB || '(root)'}'.`);

  // Flip to true for per-request timing diagnostics (method, URL, status,
  // ms). Default false keeps the console readable; edit in the pasted
  // script — no rebuild needed. deploy.js additionally prints a per-phase
  // seconds table before DONE when this is on.
  const DEBUG = false;
  const dbg = (msg) => { if (DEBUG) log('DEBUG', msg); };
  let requestCount = 0;
  const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

  // SharePoint's REST error body carries the human-readable reason at
  // error.message.value; fall back to (bounded) raw text — a bare HTTP
  // status left a blocked run undiagnosable (live finding 2026-07-24).
  const spError = (text) => {
    try {
      return JSON.parse(text)?.error?.message?.value || String(text).slice(0, 300);
    } catch {
      return String(text).slice(0, 300);
    }
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
      dbg(`${(opts && opts.method) || 'GET'} ${url.length > 160 ? `${url.slice(0, 160)}…` : url} → ${r.status} in ${Date.now() - t0}ms${i > 0 ? ` (${i} throttle retries)` : ''}`);
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

  let cachedDigest = null;
  let digestExpiresAt = 0;
  async function getDigest() {
    if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;
    const r = await fetchWithRetry(apiUrl('contextinfo'), {
      method: 'POST',
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const j = await r.json();
    const info = j.d.GetContextWebInformation;
    cachedDigest = info.FormDigestValue;
    const timeoutSeconds = Number(info.FormDigestTimeoutSeconds) || 1800;
    digestExpiresAt = Date.now() + Math.max(timeoutSeconds - 60, 60) * 1000;
    return cachedDigest;
  }

  async function readListShape(name) {
    const select = [
      'Id', 'Title', 'BaseTemplate', 'ContentTypesEnabled',
      'EnableVersioning', 'EnableMinorVersions', 'MajorVersionLimit', 'ValidationFormula', 'ValidationMessage',
    ].join(',');
    const r = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(name)}')?$select=${select}`), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (r.status === 404) return null;
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`List '${name}' shape probe failed: HTTP ${r.status} ${text}`);
    }
    const j = await r.json();
    const shape = j && j.d;
    if (!shape
        || typeof shape.Id !== 'string'
        || typeof shape.Title !== 'string'
        || !Number.isInteger(shape.BaseTemplate)
        || typeof shape.ContentTypesEnabled !== 'boolean'
        || typeof shape.EnableVersioning !== 'boolean'
        || typeof shape.EnableMinorVersions !== 'boolean'
        || !Number.isInteger(shape.MajorVersionLimit)
        || !(shape.ValidationFormula == null || typeof shape.ValidationFormula === 'string')
        || !(shape.ValidationMessage == null || typeof shape.ValidationMessage === 'string')) {
      throw new Error(`List '${name}' shape probe returned an invalid response`);
    }
    return shape;
  }

  // SharePoint's by-name getters do not uniformly 404 for a missing item:
  // fields/getbyinternalnameortitle ("Column 'X' does not exist") and
  // views/getbytitle ("The specified view is invalid.") both throw
  // System.ArgumentException as HTTP 400 with locale-invariant code
  // -2147024809. Exactly that shape means "absent"; anything else stays
  // fatal in the caller.
  const isAbsent400 = (status, text) => {
    if (status !== 400) return false;
    let code = '';
    try { code = String(JSON.parse(text)?.error?.code || ''); } catch { return false; }
    return code.includes('-2147024809') && code.includes('System.ArgumentException');
  };

  // Base field shapes come from ONE fields enumeration per list, cached in a
  // name -> shape map (keyed by InternalName AND display Title, matching
  // getbyinternalnameortitle semantics). Two problems solved at once: the
  // by-name getter answers HTTP 400 for an absent field, which browsers
  // paint red and operators read as failures (seen live, twice); and bulk
  // probe loops (preflight / unseal / reconcile / seal over ~52 columns)
  // were paying one GET per column per phase. Freshness contract: probes
  // reflect PHASE-START state — each field-touching phase opens with
  // invalidateFieldShapes(); verify-after-write reads pass fresh=true and
  // bypass the cache entirely (verification never trusts a cache). An
  // absent LIST yields an uncached empty result — the list may be created
  // later in this same run.
  const _FIELD_SHAPE_SELECT = [
    'Id', 'InternalName', 'Title', 'TypeAsString', 'Description', 'Required',
    'EnforceUniqueValues', 'Indexed', 'ReadOnlyField', 'Sealed', 'DefaultValue', 'CustomFormatter',
  ].join(',');
  let fieldShapesByList = {};
  // No argument: full reset (phase starts). With a list name: drop only
  // that list's snapshot — lanes refresh their own list after writes
  // without thrashing the other lanes' caches.
  const invalidateFieldShapes = (listName) => {
    if (listName == null) { fieldShapesByList = {}; return; }
    delete fieldShapesByList[listName];
  };
  async function listFieldShapes(listName) {
    if (listName in fieldShapesByList) return fieldShapesByList[listName];
    const r = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(listName)}')/fields?$select=${_FIELD_SHAPE_SELECT}`), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!r.ok) {
      const text = await r.text();
      if (r.status === 404 || isAbsent400(r.status, text)) return new Map();
      throw new Error(`Field enumeration for '${listName}' failed: HTTP ${r.status} ${text}`);
    }
    const j = await r.json();
    const shapes = new Map();
    for (const f of (j && j.d && j.d.results) || []) {
      if (f.InternalName && !shapes.has(f.InternalName)) shapes.set(f.InternalName, f);
      if (f.Title && !shapes.has(f.Title)) shapes.set(f.Title, f);
    }
    fieldShapesByList[listName] = shapes;
    return shapes;
  }

  async function readFieldShape(listName, columnName, declaredField = null, fresh = false) {
    // getbyinternalnameortitle makes a renamed display Title repairable while
    // still letting the immutable InternalName check below reject a same-title
    // impostor field.
    const fieldPath = `web/lists/getbytitle('${odataName(listName)}')/fields/getbyinternalnameortitle('${odataName(columnName)}')`;
    let shape;
    if (!fresh) {
      shape = (await listFieldShapes(listName)).get(columnName) || null;
      if (!shape) return null;
      // Cached entries were validated at enumeration time by the same checks
      // below; re-validate anyway — one shared gate for both paths.
    } else {
      const r = await fetchWithRetry(apiUrl(`${fieldPath}?$select=${_FIELD_SHAPE_SELECT}`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (r.status === 404) return null;
      if (!r.ok) {
        const text = await r.text();
        if (isAbsent400(r.status, text)) return null;
        throw new Error(`Field '${listName}.${columnName}' shape probe failed: HTTP ${r.status} ${text}`);
      }
      const j = await r.json();
      shape = j && j.d;
    }
    if (!shape
        || typeof shape.Id !== 'string'
        || typeof shape.InternalName !== 'string'
        || typeof shape.Title !== 'string'
        || typeof shape.TypeAsString !== 'string'
        || !(shape.Description === null || typeof shape.Description === 'string')
        || typeof shape.Required !== 'boolean'
        || typeof shape.EnforceUniqueValues !== 'boolean'
        || typeof shape.Indexed !== 'boolean'
        || typeof shape.ReadOnlyField !== 'boolean'
        || typeof shape.Sealed !== 'boolean'
        || !(shape.DefaultValue === null || typeof shape.DefaultValue === 'string')
        || !(shape.CustomFormatter == null || typeof shape.CustomFormatter === 'string')) {
      throw new Error(`Field '${listName}.${columnName}' shape probe returned an invalid response`);
    }
    if (declaredField && declaredField.target_list) {
      const lookupResp = await fetchWithRetry(apiUrl(`${fieldPath}?$select=LookupList,LookupField`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!lookupResp.ok) {
        const text = await lookupResp.text();
        throw new Error(`Lookup field '${listName}.${columnName}' target probe failed: HTTP ${lookupResp.status} ${text}`);
      }
      const lookupJson = await lookupResp.json();
      const lookupShape = lookupJson && lookupJson.d;
      if (!lookupShape
          || typeof lookupShape.LookupList !== 'string'
          || typeof lookupShape.LookupField !== 'string') {
        throw new Error(`Lookup field '${listName}.${columnName}' target probe returned an invalid response`);
      }
      shape.LookupList = lookupShape.LookupList;
      shape.LookupField = lookupShape.LookupField;
    }

    // Derived field properties are not safely selectable from every SP.Field
    // subtype. Query only the properties this declaration actually owns, then
    // reconcile/read them back with the matching concrete metadata type.
    const body = (declaredField && declaredField.body) || {};
    const derivedSelect = [
      'MaxLength', 'RichText', 'NumberOfLines', 'AppendOnly', 'Choices',
      'FillInChoice', 'DisplayFormat', 'SelectionMode',
      'Formula', 'OutputType',
    ].filter(name => Object.prototype.hasOwnProperty.call(body, name));
    if (derivedSelect.length > 0) {
      const derivedResp = await fetchWithRetry(apiUrl(`${fieldPath}?$select=${derivedSelect.join(',')}`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!derivedResp.ok) {
        const text = await derivedResp.text();
        throw new Error(`Field '${listName}.${columnName}' derived-shape probe failed: HTTP ${derivedResp.status} ${text}`);
      }
      const derivedJson = await derivedResp.json();
      const derived = derivedJson && derivedJson.d;
      if (!derived) {
        throw new Error(`Field '${listName}.${columnName}' derived-shape probe returned an invalid response`);
      }
      for (const name of derivedSelect) {
        const value = derived[name];
        if (name === 'Choices') {
          if (!value || !Array.isArray(value.results) || value.results.some(item => typeof item !== 'string')) {
            throw new Error(`Field '${listName}.${columnName}' Choices probe returned an invalid response`);
          }
        } else if (name === 'RichText' || name === 'AppendOnly' || name === 'FillInChoice') {
          if (typeof value !== 'boolean') {
            throw new Error(`Field '${listName}.${columnName}' ${name} probe returned an invalid response`);
          }
        } else if (name === 'Formula') {
          if (typeof value !== 'string') {
            throw new Error(`Field '${listName}.${columnName}' Formula probe returned an invalid response`);
          }
        } else if (!Number.isInteger(value)) {
          throw new Error(`Field '${listName}.${columnName}' ${name} probe returned an invalid response`);
        }
        shape[name] = value;
      }
    }
    return shape;
  }

  // Bounded per-lane parallelism. SharePoint stores fields and views in the
  // list schema, and concurrent schema writes to the SAME list race into
  // save conflicts — but different lists are fully independent. So the unit
  // of parallelism is the list: items are grouped into lanes by key, items
  // within a lane run strictly sequentially, lanes run concurrently up to
  // `limit`. Workers keep their own per-item try/catch, so error
  // attribution and summary.errors are unchanged.
  async function mapLanes(items, laneKey, worker, limit = 4) {
    const lanes = new Map();
    for (const item of items) {
      const key = laneKey(item);
      if (!lanes.has(key)) lanes.set(key, []);
      lanes.get(key).push(item);
    }
    const queues = [...lanes.values()];
    let next = 0;
    const runners = Array.from({ length: Math.min(limit, queues.length) }, async () => {
      for (;;) {
        if (next >= queues.length) return;
        const mine = queues[next];
        next += 1;
        for (const item of mine) await worker(item);
      }
    });
    await Promise.all(runners);
  }

  async function postJson(url, body, digest) {
    const r = await fetchWithRetry(url, {
      method: 'POST', headers: spHeaders(digest), body: JSON.stringify(body),
    });
    if (!r.ok) {
      throw new Error(spError(await r.text()) || `HTTP ${r.status}`);
    }
    return r.json();
  }

  async function patchField(listName, columnName, body, digest) {
    // Callers pass the declared immutable field name. Resolve by internal name
    // or title so a safe display-title drift can be repaired instead of making
    // the preflight discover the field and the subsequent MERGE miss it.
    const url = apiUrl(`web/lists/getbytitle('${odataName(listName)}')/fields/getbyinternalnameortitle('${odataName(columnName)}')`);
    const r = await fetchWithRetry(url, {
      method: 'POST',
      headers: spHeaders(digest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`PATCH ${columnName} failed: HTTP ${r.status} ${text}`);
    }
  }

  async function patchList(listName, body, digest) {
    const url = apiUrl(`web/lists/getbytitle('${odataName(listName)}')`);
    const r = await fetchWithRetry(url, {
      method: 'POST',
      headers: spHeaders(digest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`List '${listName}' settings MERGE failed: HTTP ${r.status} ${text}`);
    }
  }

  // Canonical JSON for declared-vs-readback comparison of formatter blobs
  // (CustomFormatter and friends): parse strings, sort object keys
  // recursively, stringify — whitespace and key order differences are not
  // drift. A non-JSON string compares as itself (fail closed via mismatch).
  const canonicalJson = (value) => {
    if (value == null || value === '') return null;
    const sortKeys = (node) => {
      if (Array.isArray(node)) return node.map(sortKeys);
      if (node && typeof node === 'object') {
        return Object.fromEntries(Object.keys(node).sort().map((key) => [key, sortKeys(node[key])]));
      }
      return node;
    };
    let parsed = value;
    if (typeof value === 'string') {
      try { parsed = JSON.parse(value); } catch { return value; }
    }
    return JSON.stringify(sortKeys(parsed));
  };

  // === Schema definition (rendered from DBML + mapping) ===
  const SCHEMA = {
  "field_defaults": [
    {
      "default_value": "Open",
      "field": "Status",
      "list": "APP_Project",
      "metadata_type": "SP.FieldChoice"
    },
    {
      "default_value": "0",
      "field": "SortOrder",
      "list": "APP_Project",
      "metadata_type": "SP.FieldNumber"
    }
  ],
  "form_formatting": [
    {
      "client_form_custom_formatter": "{\"bodyJSONFormatter\":{\"sections\":[{\"displayname\":\"Project\",\"fields\":[\"Title\",\"Status\",\"Sort Order\"]}]}}",
      "list": "APP_Project"
    }
  ],
  "groups": [
    {
      "allow_members_edit_membership": false,
      "allow_request_to_join_leave": false,
      "auto_accept_request_to_join_leave": false,
      "description": "Test group.",
      "enroll_operator_during_deploy": false,
      "name": "List Maintainer",
      "only_allow_members_view_membership": false,
      "owner_group": "Site Owners",
      "require_empty_at_deploy": true
    }
  ],
  "indexed_columns": [
    {
      "field": "DueDate",
      "list": "APP_Task"
    }
  ],
  "list_assignments": [
    {
      "assignments": [
        {
          "level": "Schema Manager",
          "principal": {
            "kind": "group",
            "name": "List Maintainer"
          }
        },
        {
          "level": "Contribute",
          "principal": {
            "kind": "associated_owner_group"
          }
        },
        {
          "level": "Read",
          "principal": {
            "kind": "associated_visitor_group"
          }
        }
      ],
      "break_inheritance": true,
      "list": "APP_Project",
      "reconcile_mode": "exact"
    },
    {
      "assignments": [
        {
          "level": "Schema Manager",
          "principal": {
            "kind": "group",
            "name": "List Maintainer"
          }
        },
        {
          "level": "Contribute",
          "principal": {
            "kind": "associated_owner_group"
          }
        },
        {
          "level": "Read",
          "principal": {
            "kind": "associated_visitor_group"
          }
        }
      ],
      "break_inheritance": true,
      "list": "APP_Task",
      "reconcile_mode": "exact"
    },
    {
      "assignments": [
        {
          "level": "Schema Manager",
          "principal": {
            "kind": "group",
            "name": "List Maintainer"
          }
        },
        {
          "level": "Contribute",
          "principal": {
            "kind": "associated_owner_group"
          }
        },
        {
          "level": "Read",
          "principal": {
            "kind": "associated_visitor_group"
          }
        }
      ],
      "break_inheritance": true,
      "list": "APP_AppSettings",
      "reconcile_mode": "exact"
    }
  ],
  "lists": [
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "",
      "enable_minor_versions": false,
      "enable_versioning": true,
      "fields_phase1": [
        {
          "body": {
            "Choices": {
              "results": [
                "Open",
                "Closed"
              ]
            },
            "DefaultValue": "Open",
            "FieldTypeKind": 6,
            "FillInChoice": false,
            "Required": true,
            "Title": "Status",
            "__metadata": {
              "type": "SP.FieldChoice"
            }
          },
          "custom_formatter": "{\"$schema\":\"https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json\",\"attributes\":{\"class\":\"=if(@currentField == \u0027Open\u0027, \u0027sp-css-backgroundColor-BgLightBlue\u0027, \u0027sp-css-backgroundColor-BgMintGreen\u0027)\"},\"elmType\":\"div\",\"txtContent\":\"@currentField\"}",
          "display_title": "Status",
          "hide_on_display": false,
          "hide_on_forms": false,
          "seal": false,
          "title": "Status"
        },
        {
          "body": {
            "DefaultValue": "0",
            "FieldTypeKind": 9,
            "Required": true,
            "Title": "SortOrder",
            "__metadata": {
              "type": "SP.FieldNumber"
            }
          },
          "custom_formatter": null,
          "display_title": "Sort Order",
          "hide_on_display": false,
          "hide_on_forms": false,
          "seal": false,
          "title": "SortOrder"
        }
      ],
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "title": "APP_Project",
      "title_patch": {
        "Description": "Project name.",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_formula": "=IF([Status]=\"Closed\",[Sort Order]\u003e=0,TRUE)",
      "validation_message": "A closed project needs a non-negative sort order."
    },
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "",
      "enable_minor_versions": false,
      "enable_versioning": true,
      "fields_phase1": [
        {
          "body": {
            "FieldTypeKind": 7,
            "LookupField": "Title",
            "Required": true,
            "Title": "Project",
            "__metadata": {
              "type": "SP.FieldLookup"
            }
          },
          "custom_formatter": null,
          "display_title": "Project",
          "hide_on_display": false,
          "hide_on_forms": false,
          "lookup_creation_parameters": {
            "FieldTypeKind": 7,
            "LookupFieldName": "Title",
            "Required": true,
            "Title": "Project",
            "__metadata": {
              "type": "SP.FieldCreationInformation"
            }
          },
          "seal": false,
          "target_list": "APP_Project",
          "title": "Project"
        },
        {
          "body": {
            "Description": "Optional due date.",
            "DisplayFormat": 0,
            "FieldTypeKind": 4,
            "Title": "DueDate",
            "__metadata": {
              "type": "SP.FieldDateTime"
            }
          },
          "custom_formatter": null,
          "display_title": "Due Date",
          "hide_on_display": false,
          "hide_on_forms": false,
          "seal": false,
          "title": "DueDate"
        }
      ],
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "title": "APP_Task",
      "title_patch": {
        "Description": "",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_formula": null,
      "validation_message": null
    },
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "",
      "enable_minor_versions": false,
      "enable_versioning": true,
      "fields_phase1": [],
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "title": "APP_AppSettings",
      "title_patch": {
        "Description": "App Settings singleton.",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_formula": null,
      "validation_message": null
    }
  ],
  "permission_levels": [
    {
      "base_permissions": {
        "high": "0",
        "low": "2049"
      },
      "description": "Test permission level.",
      "name": "Schema Manager"
    }
  ],
  "phase2_lookups": [],
  "seed_items": [],
  "views": [
    {
      "caml_query": "\u003cWhere\u003e\u003cNeq\u003e\u003cFieldRef Name=\"Status\"/\u003e\u003cValue Type=\"Text\"\u003eClosed\u003c/Value\u003e\u003c/Neq\u003e\u003c/Where\u003e\u003cOrderBy\u003e\u003cFieldRef Name=\"SortOrder\"/\u003e\u003c/OrderBy\u003e",
      "formatting": "{\"additionalRowClass\":\"=if([$Status] == \u0027Closed\u0027, \u0027sp-css-backgroundColor-BgLightGray\u0027, \u0027\u0027)\"}",
      "list": "APP_Project",
      "row_limit": 100,
      "set_default": true,
      "title": "Open projects",
      "url_slug": "OpenProjects",
      "view_fields": [
        "Title",
        "Status",
        "SortOrder"
      ],
      "widths": null
    },
    {
      "caml_query": "\u003cGroupBy Collapse=\"FALSE\"\u003e\u003cFieldRef Name=\"Project\"/\u003e\u003c/GroupBy\u003e\u003cWhere\u003e\u003cLeq\u003e\u003cFieldRef Name=\"DueDate\"/\u003e\u003cValue Type=\"DateTime\"\u003e\u003cToday OffsetDays=\"30\"/\u003e\u003c/Value\u003e\u003c/Leq\u003e\u003c/Where\u003e\u003cOrderBy\u003e\u003cFieldRef Name=\"DueDate\"/\u003e\u003c/OrderBy\u003e",
      "formatting": null,
      "list": "APP_Task",
      "row_limit": null,
      "set_default": false,
      "title": "Due soon",
      "url_slug": "DueSoon",
      "view_fields": [
        "Title",
        "Project",
        "DueDate"
      ],
      "widths": null
    }
  ]
};

  const TYPE_AS_STRING_BY_KIND = new Map([
    [2, 'Text'], [3, 'Note'], [4, 'DateTime'], [6, 'Choice'],
    [7, 'Lookup'], [8, 'Boolean'], [9, 'Number'], [11, 'URL'], [20, 'User'],
    [17, 'Calculated'],
  ]);
  const indexedFieldKeys = new Set(
    SCHEMA.indexed_columns.map(idx => `${idx.list}\u0000${idx.field}`),
  );
  const normalizeGuid = (value) => String(value).replace(/[{}]/g, '').toLowerCase();
  const normalizeDescription = (value) => value == null ? '' : String(value);
  const normalizeDefaultValue = (value) => value == null || value === '' ? null : String(value);
  const DERIVED_FIELD_PROPERTIES = [
    'MaxLength', 'RichText', 'NumberOfLines', 'AppendOnly', 'Choices',
    'FillInChoice', 'DisplayFormat', 'SelectionMode',
    'Formula', 'OutputType',
  ];

  // SharePoint stores a calculated field's Formula in the field schema XML
  // and returns it with XML character entities intact (`<>` reads back as
  // `&lt;&gt;`), so a byte comparison never converges: the drift MERGE
  // rewrites the identical formula and the readback still "differs". Compare
  // formulas on their XML-decoded canonical form — both sides, so encoded
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
  // not need delimiting — `[Likelihood]` is stored and read back as
  // `Likelihood`; names with spaces keep their brackets. Strip removable
  // brackets on both sides, but only OUTSIDE string literals (split keeps
  // `"..."` tokens, with `""` as the escaped quote, at odd indices):
  // bracket text inside a quoted constant is data, not a reference.
  const canonicalFormula = (value) => xmlDecode(value)
    .split(/("(?:""|[^"])*")/)
    .map((token, i) => (i % 2 === 1 ? token : token.replace(/\[([A-Za-z0-9_]+)\]/g, '$1')))
    .join('');

  function normalizeDerivedValue(name, value) {
    if (name === 'Choices') return value.results;
    if (name === 'Formula') return canonicalFormula(value);
    return value;
  }

  function sameDerivedValue(name, actual, desired) {
    const a = normalizeDerivedValue(name, actual);
    const d = normalizeDerivedValue(name, desired);
    if (name !== 'Choices') return a === d;
    return a.length === d.length && a.every((value, index) => value === d[index]);
  }

  function declaredFieldState(listName, field) {
    const typeAsString = TYPE_AS_STRING_BY_KIND.get(field.body.FieldTypeKind);
    if (!typeAsString) {
      throw new Error(`Field '${listName}.${field.title}' has unsupported declared FieldTypeKind ${field.body.FieldTypeKind}`);
    }
    const enforceUniqueValues = field.body.EnforceUniqueValues === true;
    const derived = Object.fromEntries(
      DERIVED_FIELD_PROPERTIES
        .filter(name => Object.prototype.hasOwnProperty.call(field.body, name))
        .map(name => [name, field.body[name]]),
    );
    return {
      typeAsString,
      description: normalizeDescription(field.body.Description),
      required: field.body.Required === true,
      enforceUniqueValues,
      indexed: enforceUniqueValues || indexedFieldKeys.has(`${listName}\u0000${field.title}`),
      defaultValue: normalizeDefaultValue(field.body.DefaultValue),
      derived,
    };
  }

  function declaredFieldsForList(list) {
    const titleField = {
      title: 'Title',
      body: { ...list.title_patch, FieldTypeKind: 2 },
    };
    const deferred = SCHEMA.phase2_lookups
      .filter(lookup => lookup.list === list.title)
      .map(lookup => lookup.field);
    return [titleField, ...list.fields_phase1, ...deferred];
  }

  function assertListImmutableShape(list, actual) {
    if (actual.BaseTemplate !== list.base_template) {
      throw new Error(
        `Existing '${list.title}' has BaseTemplate ${actual.BaseTemplate}; expected ${list.base_template} for declared kind '${list.kind}'. `
        + 'SharePoint list/library templates are immutable; provision a clean object or perform an explicit migration.',
      );
    }
  }

  function desiredListSettings(list) {
    return {
      ContentTypesEnabled: list.content_types_enabled,
      EnableVersioning: list.enable_versioning,
      EnableMinorVersions: list.enable_minor_versions,
      MajorVersionLimit: list.major_version_limit,
    };
  }

  function listSettingsMismatch(actual, desired) {
    return Object.entries(desired).some(([key, value]) => actual[key] !== value);
  }

  // List validation reconciles AFTER the list's fields exist: the formula
  // references columns (by display name) that the same run may be creating
  // and renaming — merging it with the pre-field list settings fails with
  // "The formula refers to a column that does not exist". Declared-null
  // means "never touch" (a hand-set validation survives).
  async function reconcileListValidation(list, digest) {
    if (list.validation_formula == null) return;
    const actual = await readListShape(list.title);
    if (!actual) throw new Error(`Declared list '${list.title}' disappeared before validation reconcile`);
    const formulaSame = canonicalFormula(actual.ValidationFormula || '') === canonicalFormula(list.validation_formula);
    const messageSame = (actual.ValidationMessage || '') === (list.validation_message || '');
    if (formulaSame && messageSame) return;
    await patchList(list.title, {
      __metadata: { type: 'SP.List' },
      ValidationFormula: list.validation_formula,
      ValidationMessage: list.validation_message,
    }, digest);
    const verify = await readListShape(list.title);
    if (!verify
        || canonicalFormula(verify.ValidationFormula || '') !== canonicalFormula(list.validation_formula)
        || (verify.ValidationMessage || '') !== (list.validation_message || '')) {
      throw new Error(`List '${list.title}' did not retain declared validation (declared ${JSON.stringify(list.validation_formula)}; readback ${JSON.stringify(verify && verify.ValidationFormula)})`);
    }
    log('INFO', `List '${list.title}' declared validation reconciled.`);
  }

  // Declared list-deletion block: AllowDeletion=false rejects UI deletion
  // of the LIST object even for admins (friction, not enforcement — an
  // admin can flip it back via API). Isolated probe/MERGE so an
  // unsupported tenant surface fails only this step.
  async function reconcileListDeletionBlock(list, digest) {
    if (!list.prevent_deletion) return;
    const adUrl = apiUrl(`web/lists/getbytitle('${odataName(list.title)}')?$select=AllowDeletion`);
    const adResp = await fetchWithRetry(adUrl, {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!adResp.ok) {
      const text = await adResp.text();
      throw new Error(`AllowDeletion probe failed: HTTP ${adResp.status} ${text}`);
    }
    const adJson = await adResp.json();
    if (adJson && adJson.d && adJson.d.AllowDeletion === false) return;
    await patchList(list.title, { __metadata: { type: 'SP.List' }, AllowDeletion: false }, digest);
    const verifyResp = await fetchWithRetry(adUrl, {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const verifyJson = verifyResp.ok ? await verifyResp.json() : null;
    if (!verifyJson || !verifyJson.d || verifyJson.d.AllowDeletion !== false) {
      throw new Error(`List '${list.title}' did not retain AllowDeletion = false`);
    }
    log('INFO', `List '${list.title}' deletion block applied (AllowDeletion = false).`);
  }

  async function reconcileListShape(list, digest) {
    let actual = await readListShape(list.title);
    if (!actual) throw new Error(`Declared list '${list.title}' disappeared during deployment`);
    assertListImmutableShape(list, actual);
    const desired = desiredListSettings(list);
    if (listSettingsMismatch(actual, desired)) {
      await patchList(list.title, {
        __metadata: { type: 'SP.List' },
        ...desired,
      }, digest);
      actual = await readListShape(list.title);
      if (!actual) throw new Error(`Declared list '${list.title}' disappeared after settings MERGE`);
      assertListImmutableShape(list, actual);
      if (listSettingsMismatch(actual, desired)) {
        const drifted = Object.keys(desired).filter(key => actual[key] !== desired[key]);
        throw new Error(`List '${list.title}' did not retain declared setting(s): ${drifted.join(', ')}`);
      }
      log('INFO', `List '${list.title}' declared versioning/content-type settings reconciled.`);
    } else {
      log('INFO', `List '${list.title}' immutable template and declared settings verified.`);
    }
    await reconcileListDeletionBlock(list, digest);
    return actual;
  }

  async function expectedLookupFieldInternalName(listName, field) {
    const targetDisplay = await readFieldShape(
      field.target_list,
      field.body.LookupField,
      null,
    );
    if (!targetDisplay) {
      throw new Error(
        `Lookup '${listName}.${field.title}' target display field '${field.target_list}.${field.body.LookupField}' does not exist`,
      );
    }
    if (targetDisplay.InternalName !== field.body.LookupField) {
      throw new Error(
        `Lookup '${listName}.${field.title}' target display field resolves to immutable InternalName '${targetDisplay.InternalName}'; expected '${field.body.LookupField}'`,
      );
    }
    return targetDisplay.InternalName;
  }

  async function assertFieldImmutableShape(listName, field, actual, targetGuid) {
    const desired = declaredFieldState(listName, field);
    if (actual.InternalName !== field.title) {
      throw new Error(
        `Existing field '${listName}.${field.title}' resolves to immutable InternalName '${actual.InternalName}'; expected '${field.title}'`,
      );
    }
    if (actual.TypeAsString !== desired.typeAsString) {
      throw new Error(
        `Existing field '${listName}.${field.title}' has immutable TypeAsString '${actual.TypeAsString}'; expected '${desired.typeAsString}'`,
      );
    }
    // SP.FieldCalculated is intrinsically ReadOnlyField=true (users never
    // write it); on every other declared type read-only means an impostor.
    const expectReadOnly = desired.typeAsString === 'Calculated';
    if (actual.ReadOnlyField !== expectReadOnly) {
      throw new Error(
        `Existing field '${listName}.${field.title}' ReadOnlyField is ${actual.ReadOnlyField}; expected ${expectReadOnly} for declared type '${desired.typeAsString}'`,
      );
    }
    // Declared-seal fields are legitimately sealed between runs (the
    // maintenance unseal opens them for this run's writes; Phase 4.1
    // re-seals). Sealed WITHOUT a declaration still means an impostor.
    if (actual.Sealed && !field.seal) {
      throw new Error(
        `Existing field '${listName}.${field.title}' is sealed; expected an unsealed declared field`,
      );
    }
    if (field.target_list) {
      if (!targetGuid) {
        throw new Error(
          `Existing lookup '${listName}.${field.title}' cannot be adopted because declared target list '${field.target_list}' does not yet exist`,
        );
      }
      const expectedLookupField = await expectedLookupFieldInternalName(listName, field);
      if (normalizeGuid(actual.LookupList) !== normalizeGuid(targetGuid)
          || actual.LookupField !== expectedLookupField) {
        throw new Error(
          `Existing lookup '${listName}.${field.title}' targets list '${actual.LookupList}' field '${actual.LookupField}'; `
          + `expected list '${targetGuid}' field '${expectedLookupField}'. Lookup targets are immutable; recreate through an explicit migration.`,
        );
      }
    }
  }

  // Declared form visibility: auto-stamped columns are removed from the NEW
  // and EDIT forms (the display form keeps them for audit). SP exposes this
  // through POST setter methods, not writable properties; a null read means
  // "shown".
  async function enforceFormVisibility(listName, field, digest) {
    const visUrl = apiUrl(`web/lists/getbytitle('${odataName(listName)}')/fields/getbyinternalnameortitle('${odataName(field.title)}')`);
    // ShowInNewForm/ShowInEditForm are NOT projected by the REST field
    // resource ($select returns neither); the readable source of truth is
    // the SchemaXml attribute — absent means "shown".
    const readVisibility = async () => {
      const r = await fetchWithRetry(`${visUrl}?$select=SchemaXml`, {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`form visibility probe failed: HTTP ${r.status} ${text}`);
      }
      const j = await r.json();
      const xml = String((j && j.d && j.d.SchemaXml) || '');
      return {
        shownOnNew: !/ShowInNewForm="FALSE"/i.test(xml),
        shownOnEdit: !/ShowInEditForm="FALSE"/i.test(xml),
        shownOnDisplay: !/ShowInDisplayForm="FALSE"/i.test(xml),
      };
    };
    const current = await readVisibility();
    const setters = [];
    if (field.hide_on_forms) {
      setters.push([current.shownOnNew, 'setshowinnewform'], [current.shownOnEdit, 'setshowineditform']);
    }
    if (field.hide_on_display) {
      setters.push([current.shownOnDisplay, 'setshowindisplayform']);
    }
    for (const [shown, method] of setters) {
      if (shown) {
        const r = await fetchWithRetry(`${visUrl}/${method}(false)`, {
          method: 'POST', headers: spHeaders(digest),
        });
        if (!r.ok) {
          const text = await r.text();
          throw new Error(`${method}(false) failed: HTTP ${r.status} ${text}`);
        }
      }
    }
    const verify = await readVisibility();
    const stillShown = [];
    if (field.hide_on_forms && verify.shownOnNew) stillShown.push('new form');
    if (field.hide_on_forms && verify.shownOnEdit) stillShown.push('edit form');
    if (field.hide_on_display && verify.shownOnDisplay) stillShown.push('display form');
    if (stillShown.length > 0) {
      throw new Error(`did not retain form visibility (still shown on: ${stillShown.join(', ')})`);
    }
  }

  async function reconcileDeclaredField(listName, field, targetGuid, digest, allowMissing) {
    let actual = await readFieldShape(listName, field.title, field);
    if (!actual) {
      if (allowMissing) return false;
      throw new Error(`Declared field '${listName}.${field.title}' is missing after creation`);
    }
    await assertFieldImmutableShape(listName, field, actual, targetGuid);
    const desired = declaredFieldState(listName, field);
    // Desired display Title is display_title (rename-after-create): fields
    // are created titled with their internal name, then renamed. Synthetic
    // callers (the built-in Title patch) carry no display_title.
    const desiredTitle = field.display_title != null ? field.display_title : field.title;
    const derivedMismatch = Object.entries(desired.derived)
      .some(([name, value]) => !sameDerivedValue(name, actual[name], value));
    const mutableMismatch = (
      actual.Title !== desiredTitle
      || normalizeDescription(actual.Description) !== desired.description
      || actual.Required !== desired.required
      || actual.EnforceUniqueValues !== desired.enforceUniqueValues
      || actual.Indexed !== desired.indexed
      || normalizeDefaultValue(actual.DefaultValue) !== desired.defaultValue
      // Declared-null means "never touch": a hand-applied format survives.
      || (field.custom_formatter != null
          && canonicalJson(actual.CustomFormatter) !== canonicalJson(field.custom_formatter))
      || derivedMismatch
    );
    if (mutableMismatch) {
      // Send only drifted writable properties. Some derived field types reject
      // an otherwise harmless no-op property from SP.Field (for example an
      // indexing flag on Note); a narrow MERGE is both safer and auditable.
      const patchBody = { __metadata: field.body.__metadata };
      if (actual.Title !== desiredTitle) patchBody.Title = desiredTitle;
      if (normalizeDescription(actual.Description) !== desired.description) {
        patchBody.Description = desired.description;
      }
      if (actual.Required !== desired.required) patchBody.Required = desired.required;
      if (actual.EnforceUniqueValues !== desired.enforceUniqueValues) {
        patchBody.EnforceUniqueValues = desired.enforceUniqueValues;
      }
      if (actual.Indexed !== desired.indexed) patchBody.Indexed = desired.indexed;
      if (normalizeDefaultValue(actual.DefaultValue) !== desired.defaultValue) {
        patchBody.DefaultValue = desired.defaultValue;
      }
      if (field.custom_formatter != null
          && canonicalJson(actual.CustomFormatter) !== canonicalJson(field.custom_formatter)) {
        patchBody.CustomFormatter = field.custom_formatter;
      }
      for (const [name, value] of Object.entries(desired.derived)) {
        if (!sameDerivedValue(name, actual[name], value)) patchBody[name] = value;
      }
      await patchField(listName, field.title, patchBody, digest);
      actual = await readFieldShape(listName, field.title, field, true);
      if (!actual) throw new Error(`Field '${listName}.${field.title}' disappeared after reconciliation`);
      await assertFieldImmutableShape(listName, field, actual, targetGuid);
    }
    // Name each surviving drift WITH both values: a setting that will not
    // reconcile is diagnosable from the console log alone, without another
    // paste round-trip.
    const drifted = [];
    const drift = (name, declaredValue, actualValue) => drifted.push(
      `${name} (declared ${JSON.stringify(declaredValue)}; readback ${JSON.stringify(actualValue)})`,
    );
    if (actual.Title !== desiredTitle) drift('Title', desiredTitle, actual.Title);
    if (normalizeDescription(actual.Description) !== desired.description) drift('Description', desired.description, actual.Description);
    if (actual.Required !== desired.required) drift('Required', desired.required, actual.Required);
    if (actual.EnforceUniqueValues !== desired.enforceUniqueValues) drift('EnforceUniqueValues', desired.enforceUniqueValues, actual.EnforceUniqueValues);
    if (actual.Indexed !== desired.indexed) drift('Indexed', desired.indexed, actual.Indexed);
    if (normalizeDefaultValue(actual.DefaultValue) !== desired.defaultValue) drift('DefaultValue', desired.defaultValue, actual.DefaultValue);
    if (field.custom_formatter != null
        && canonicalJson(actual.CustomFormatter) !== canonicalJson(field.custom_formatter)) {
      drift('CustomFormatter', field.custom_formatter, actual.CustomFormatter);
    }
    for (const [name, value] of Object.entries(desired.derived)) {
      if (!sameDerivedValue(name, actual[name], value)) drift(name, value, actual[name]);
    }
    if (drifted.length > 0) {
      throw new Error(`Field '${listName}.${field.title}' did not retain declared mutable setting(s): ${drifted.join(', ')}`);
    }
    if (field.hide_on_forms || field.hide_on_display) {
      await enforceFormVisibility(listName, field, digest);
    }
    return true;
  }

  // === Preflight: ManageLists (+ ManagePermissions when the schema has ACL work) ===
  // ManageLists is Low bit 0x800; ManagePermissions is Low bit 0x2000000.
  // (Previous check incorrectly tested High; ManageLists lives in Low.)
  // ManagePermissions is only demanded when the schema actually performs
  // Phase 1.2/4 permission work, so an operator who can manage lists but not
  // ACLs is not rejected on a list-only deployment.
  const needsPermissions = (
    SCHEMA.permission_levels.length > 0 ||
    SCHEMA.groups.length > 0 ||
    SCHEMA.list_assignments.length > 0
  );
  const permsResp = await fetchWithRetry(apiUrl('web?$select=EffectiveBasePermissions'), {
    headers: { 'Accept': 'application/json;odata=verbose' },
  });
  const permsJson = await permsResp.json();
  const requiredLow = needsPermissions ? (0x800 | 0x2000000) : 0x800;
  const haveLow = Number(permsJson?.d?.EffectiveBasePermissions?.Low || 0);
  if ((haveLow & requiredLow) !== requiredLow) {
    log('ERROR', needsPermissions
      ? 'Current user lacks ManageLists+ManagePermissions on this site.'
      : 'Current user lacks ManageLists on this site.');
    return { aborted: 'insufficient-permissions' };
  }

  markPhase('Phase 1.1 — read-only preflight');
  // === Preflight: fail-closed adoption of existing schema objects ===
  // A matching display name is not proof that an existing list or field was
  // created from this schema. Validate every immutable identity before Phase 1.2
  // performs its first write. Mutable declared settings are reconciled and
  // read back in Phase 2.1, but a wrong template/type/internal-name/lookup target
  // always requires an explicit migration.
  log('INFO', 'Group 1 — PREPARE');
  log('INFO', 'Starting Phase 1.1: read-only preflight.');
  invalidateFieldShapes();  // probes reflect phase-start state
  // Read-only, so lanes are free of write races — but the field wave still
  // waits for ALL list shapes: lookup fields validate against their target
  // list's GUID, which another lane may still be reading.
  const preflightListShapes = {};
  await mapLanes(SCHEMA.lists, (list) => list.title, async (list) => {
    try {
      const actual = await readListShape(list.title);
      if (!actual) return;
      assertListImmutableShape(list, actual);
      // readListShape also fail-closes malformed or omitted mutable settings;
      // drift itself is safe to repair later and is reported for visibility.
      if (listSettingsMismatch(actual, desiredListSettings(list))) {
        log('INFO', `Existing list '${list.title}' has mutable versioning/content-type drift; Phase 2.1 will reconcile it.`);
      }
      preflightListShapes[list.title] = actual;
    } catch (err) {
      log('ERROR', `Existing-schema list '${list.title}': ${err.message}`);
      summary.errors.push({ phase: 'preflight', list: list.title, error: err.message });
    }
  }, 4);

  await mapLanes(
    SCHEMA.lists.filter((list) => preflightListShapes[list.title]),
    (list) => list.title,
    async (list) => {
    for (const field of declaredFieldsForList(list)) {
      try {
        const actual = await readFieldShape(
          list.title,
          field.title,
          field,
        );
        if (!actual) continue;
        const targetGuid = field.target_list
          ? preflightListShapes[field.target_list]?.Id
          : null;
        await assertFieldImmutableShape(list.title, field, actual, targetGuid);
        // Force evaluation of every declared mutable expectation during the
        // read-only preflight; Phase 2.1 performs and verifies any safe MERGE.
        declaredFieldState(list.title, field);
      } catch (err) {
        log('ERROR', `Existing-schema field '${list.title}.${field.title}': ${err.message}`);
        summary.errors.push({
          phase: 'preflight', list: list.title, column: field.title, error: err.message,
        });
      }
    }
  }, 4);

  if (summary.errors.length > 0) {
    log('ERROR', 'Existing-schema shape preflight failed; no deployment writes were attempted.');
    return { ...summary, aborted: 'existing-schema-shape-errors' };
  }

  markPhase('Phase 1.2 — permission levels and site groups');
  // === Phase 1.2: custom permission levels + site groups ===
  log('INFO', 'Starting Phase 1.2: permission levels and site groups.');
  {
    let digest0 = await getDigest();

    for (const lvl of SCHEMA.permission_levels) {
      try {
        // Existence probe via $filter: getbyname returns HTTP 500 (not 404)
        // for a missing role definition, so a getbyname probe cannot
        // distinguish "absent" from a real failure. The filter form returns
        // 200 with empty results when absent. getbyname is still used below
        // for the MERGE, where the level is known to exist.
        const checkResp = await fetchWithRetry(apiUrl(`web/roledefinitions?$select=Id&$filter=Name eq '${odataName(lvl.name)}'`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!checkResp.ok) {
          const text = await checkResp.text();
          throw new Error(`Probe for permission level '${lvl.name}' failed: HTTP ${checkResp.status} ${text}`);
        }
        const checkJson = await checkResp.json();
        const existingLevels = checkJson?.d?.results;
        if (!Array.isArray(existingLevels)) {
          throw new Error(`Probe for permission level '${lvl.name}' returned an invalid response`);
        }
        if (existingLevels.length === 0) {
          log('INFO', `Creating permission level '${lvl.name}'...`);
          await postJson(apiUrl('web/roledefinitions'), {
            __metadata: { type: 'SP.RoleDefinition' },
            Name: lvl.name,
            Description: lvl.description,
            BasePermissions: {
              __metadata: { type: 'SP.BasePermissions' },
              High: lvl.base_permissions.high,
              Low: lvl.base_permissions.low,
            },
            Order: 100,
          }, digest0);
          log('INFO', `Permission level '${lvl.name}' created.`);
        } else {
          // A same-name role definition is not proof that its permissions are
          // still the declared permissions. Reconcile the security-sensitive
          // fields on every run so a drifted level cannot silently retain
          // edit/delete rights.
          digest0 = await getDigest();
          const mergeResp = await fetchWithRetry(apiUrl(`web/roledefinitions/getbyname('${odataName(lvl.name)}')`), {
            method: 'POST',
            headers: spHeaders(digest0, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
            body: JSON.stringify({
              __metadata: { type: 'SP.RoleDefinition' },
              Description: lvl.description,
              BasePermissions: {
                __metadata: { type: 'SP.BasePermissions' },
                High: lvl.base_permissions.high,
                Low: lvl.base_permissions.low,
              },
            }),
          });
          if (!mergeResp.ok) {
            const text = await mergeResp.text();
            throw new Error(`Permission level '${lvl.name}' MERGE failed: HTTP ${mergeResp.status} ${text}`);
          }
          log('INFO', `Permission level '${lvl.name}' already exists; declared permissions reconciled.`);
        }
      } catch (err) {
        log('ERROR', `Phase 1.2 permission level '${lvl.name}': ${err.message}`);
        summary.errors.push({ phase: '1.2', permissionLevel: lvl.name, error: err.message });
      }
    }

    for (const grp of SCHEMA.groups) {
      try {
        const checkResp = await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(grp.name)}')`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (checkResp.status === 404) {
          log('INFO', `Creating site group '${grp.name}'...`);
          await postJson(apiUrl('web/sitegroups'), {
            __metadata: { type: 'SP.Group' },
            Title: grp.name,
            Description: grp.description,
            AllowMembersEditMembership: grp.allow_members_edit_membership,
            AllowRequestToJoinLeave: grp.allow_request_to_join_leave,
            AutoAcceptRequestToJoinLeave: grp.auto_accept_request_to_join_leave,
            OnlyAllowMembersViewMembership: grp.only_allow_members_view_membership,
          }, digest0);
          log('INFO', `Site group '${grp.name}' created.`);
        } else if (checkResp.ok) {
          // Group membership controls are part of the security boundary. A
          // pre-existing group with the right name but permissive flags must
          // not be accepted as compliant.
          digest0 = await getDigest();
          const mergeResp = await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(grp.name)}')`), {
            method: 'POST',
            headers: spHeaders(digest0, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
            body: JSON.stringify({
              __metadata: { type: 'SP.Group' },
              Description: grp.description,
              AllowMembersEditMembership: grp.allow_members_edit_membership,
              AllowRequestToJoinLeave: grp.allow_request_to_join_leave,
              AutoAcceptRequestToJoinLeave: grp.auto_accept_request_to_join_leave,
              OnlyAllowMembersViewMembership: grp.only_allow_members_view_membership,
            }),
          });
          if (!mergeResp.ok) {
            const text = await mergeResp.text();
            throw new Error(`Group '${grp.name}' settings MERGE failed: HTTP ${mergeResp.status} ${text}`);
          }
          log('INFO', `Site group '${grp.name}' already exists; declared membership controls reconciled.`);
        } else {
          throw new Error(`Probe for site group '${grp.name}' failed: HTTP ${checkResp.status}`);
        }

        // Owner verification, with automated correction. Plain REST cannot
        // MERGE Group.Owner (read-only through that surface), but the
        // documented CSOM protocol (MS-CSOM ProcessQuery, the same mechanism
        // PnP's Set-PnPGroup uses) can set it. On mismatch the script
        // attempts the CSOM set, then re-verifies through the documented
        // read-only /owner resource, and fails closed with the manual-action
        // instruction only if the owner still mismatches.
        let targetOwnerResp;
        if (grp.owner_group === 'Site Owners') {
          targetOwnerResp = await fetchWithRetry(apiUrl('web/AssociatedOwnerGroup?$select=Id,Title,PrincipalType'), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
        } else if (grp.owner_group === 'Site Members') {
          targetOwnerResp = await fetchWithRetry(apiUrl('web/AssociatedMemberGroup?$select=Id,Title,PrincipalType'), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
        } else if (grp.owner_group === 'Site Visitors') {
          targetOwnerResp = await fetchWithRetry(apiUrl('web/AssociatedVisitorGroup?$select=Id,Title,PrincipalType'), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
        } else {
          targetOwnerResp = await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(grp.owner_group)}')?$select=Id,Title,PrincipalType`), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
        }
        if (!targetOwnerResp.ok) {
          throw new Error(`Cannot resolve declared owner group '${grp.owner_group}' for '${grp.name}' (HTTP ${targetOwnerResp.status})`);
        }
        const targetOwner = (await targetOwnerResp.json()).d;

        const governedGroupResp = await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(grp.name)}')?$select=Id`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!governedGroupResp.ok) {
          throw new Error(`Cannot resolve governed group '${grp.name}' for owner verification (HTTP ${governedGroupResp.status})`);
        }
        const governedGroup = (await governedGroupResp.json()).d;
        const currentOwnerResp = await fetchWithRetry(apiUrl(`web/sitegroups(${governedGroup.Id})/owner?$select=Id,Title,PrincipalType`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!currentOwnerResp.ok) {
          throw new Error(`Cannot read owner for group '${grp.name}' (HTTP ${currentOwnerResp.status})`);
        }
        const currentOwner = (await currentOwnerResp.json()).d;
        const ownerShapeValid = Number.isInteger(targetOwner.Id)
          && Number.isInteger(targetOwner.PrincipalType)
          && typeof targetOwner.Title === 'string'
          && Number.isInteger(currentOwner.Id)
          && Number.isInteger(currentOwner.PrincipalType)
          && typeof currentOwner.Title === 'string';
        if (!ownerShapeValid) {
          throw new Error(`Owner verification for group '${grp.name}' returned an invalid principal response`);
        }
        if (currentOwner.Id !== targetOwner.Id
            || currentOwner.PrincipalType !== targetOwner.PrincipalType) {
          let ownerCorrected = false;
          // Automated correction only targets site-group owners (type 8) —
          // every declared owner_group resolves to a site group.
          if (targetOwner.PrincipalType === 8) {
            log('INFO', `Group '${grp.name}' owner is '${currentOwner.Title}'; attempting automated correction to '${targetOwner.Title}' via CSOM ProcessQuery...`);
            digest0 = await getDigest();
            const csomXml =
              '<Request xmlns="http://schemas.microsoft.com/sharepoint/clientquery/2009" SchemaVersion="15.0.0.0" LibraryVersion="16.0.0.0" ApplicationName="dbml-sharepoint">'
              + '<Actions>'
              + '<SetProperty Id="10" ObjectPathId="3" Name="Owner"><Parameter ObjectPathId="5" /></SetProperty>'
              + '<Method Name="Update" Id="11" ObjectPathId="3" />'
              + '</Actions>'
              + '<ObjectPaths>'
              + '<StaticProperty Id="0" TypeId="{3747adcd-a3c3-41b9-bfab-4a64dd2f1e0a}" Name="Current" />'
              + '<Property Id="1" ParentId="0" Name="Web" />'
              + '<Property Id="2" ParentId="1" Name="SiteGroups" />'
              + `<Method Id="3" ParentId="2" Name="GetById"><Parameters><Parameter Type="Int32">${governedGroup.Id}</Parameter></Parameters></Method>`
              + `<Method Id="5" ParentId="2" Name="GetById"><Parameters><Parameter Type="Int32">${targetOwner.Id}</Parameter></Parameters></Method>`
              + '</ObjectPaths>'
              + '</Request>';
            const pqResp = await fetchWithRetry(apiUrl('ProcessQuery'), {
              method: 'POST',
              headers: {
                'Accept': 'application/json;odata=verbose',
                'Content-Type': 'text/xml',
                'X-RequestDigest': digest0,
              },
              body: csomXml,
            });
            if (pqResp.ok) {
              let pqJson = null;
              try { pqJson = await pqResp.json(); } catch { pqJson = null; }
              const pqError = Array.isArray(pqJson) && pqJson.length > 0 && pqJson[0] && pqJson[0].ErrorInfo;
              if (!pqError) {
                // Re-verify through the same documented read-only probe —
                // the CSOM response alone is not trusted as success evidence.
                const reReadResp = await fetchWithRetry(apiUrl(`web/sitegroups(${governedGroup.Id})/owner?$select=Id,Title,PrincipalType`), {
                  headers: { 'Accept': 'application/json;odata=verbose' },
                });
                if (reReadResp.ok) {
                  const reRead = (await reReadResp.json()).d;
                  ownerCorrected = reRead
                    && reRead.Id === targetOwner.Id
                    && reRead.PrincipalType === targetOwner.PrincipalType;
                }
              } else {
                log('INFO', `CSOM owner set for '${grp.name}' reported: ${pqError.ErrorMessage || 'unknown error'}.`);
              }
            }
          }
          if (!ownerCorrected) {
            throw new Error(
              `Manual owner action required for group '${grp.name}': current owner '${currentOwner.Title}' `
              + `(Id ${currentOwner.Id}, type ${currentOwner.PrincipalType}) does not match declared owner `
              + `'${targetOwner.Title}' (Id ${targetOwner.Id}, type ${targetOwner.PrincipalType}) and automated `
              + `correction did not take effect. Set the group owner in SharePoint Site permissions, then rerun `
              + `this same script; Phase 2.1 will not start while this mismatch exists.`,
            );
          }
          log('INFO', `Site group '${grp.name}' owner corrected to '${targetOwner.Title}'.`);
        } else {
          log('INFO', `Site group '${grp.name}' owner verified as '${targetOwner.Title}'.`);
        }

        // Optional clean-provision/activation gate. Membership remains an
        // operator-owned concern: enumerate every page and fail closed rather
        // than silently removing an unexpected user or directory group.
        if (grp.require_empty_at_deploy) {
          let memberCount = 0;
          let membersUrl = apiUrl(`web/sitegroups/getbyname('${odataName(grp.name)}')/users?$select=Id&$top=5000`);
          while (membersUrl) {
            const membersResp = await fetchWithRetry(membersUrl, {
              headers: { 'Accept': 'application/json;odata=verbose' },
            });
            if (!membersResp.ok) {
              const text = await membersResp.text();
              throw new Error(`Group '${grp.name}' membership enumeration failed: HTTP ${membersResp.status} ${text}`);
            }
            const membersJson = await membersResp.json();
            if (!membersJson.d || !Array.isArray(membersJson.d.results)) {
              throw new Error(`Group '${grp.name}' membership enumeration returned an invalid response`);
            }
            memberCount += membersJson.d.results.length;
            membersUrl = membersJson.d.__next || null;
          }
          if (memberCount > 0) {
            throw new Error(`Group '${grp.name}' requires empty membership at deploy, but contains ${memberCount} member(s); remove them or use a mapping that does not declare the clean-provision gate`);
          }
          log('INFO', `Site group '${grp.name}' is empty as required for deployment.`);
        }
      } catch (err) {
        log('ERROR', `Phase 1.2 site group '${grp.name}': ${err.message}`);
        summary.errors.push({ phase: '1.2', group: grp.name, error: err.message });
      }
    }
  }

  // Permission-level or group failures make every later ACL assertion
  // untrustworthy. Stop before creating content-bearing lists or seed rows.
  if (summary.errors.length > 0) {
    log('ERROR', 'Phase 1.2 security reconciliation failed; aborting before list creation.');
    return { ...summary, aborted: 'phase-0-security-errors' };
  }

  markPhase('Phase 1.3 — operator self-enrolment');
  // === Operator self-enrolment (groups[].enroll_operator_during_deploy) ===
  // Some mappings route all list administration through an empty-by-default
  // admin group (Owners hold only Contribute on the lists). Later phases —
  // field reconciliation, indexes, ACL work — then need the operator to hold
  // that group's grants, so the script enrols the operator for the duration
  // of the run and removes them at the end. An operator who was ALREADY a
  // member is left untouched. Only principals who can already manage the
  // group (its Site-Owners owner) can benefit; this adds no new authority.
  log('INFO', 'Starting Phase 1.3: operator self-enrolment.');
  const selfEnrollments = [];
  async function removeSelfEnrollments() {
    for (const enrollment of selfEnrollments.splice(0)) {
      try {
        const digestR = await getDigest();
        const removeResp = await fetchWithRetry(apiUrl(`web/sitegroups(${enrollment.groupId})/users/removebyid(${enrollment.userId})`), {
          method: 'POST',
          headers: spHeaders(digestR),
        });
        if (!removeResp.ok) {
          const text = await removeResp.text();
          throw new Error(`HTTP ${removeResp.status} ${text}`);
        }
        log('INFO', `Removed operator from '${enrollment.groupName}' (run-scoped enrolment).`);
      } catch (err) {
        log('ERROR', `Could not remove the operator from '${enrollment.groupName}': ${err.message}. Remove yourself in Site permissions > Groups.`);
      }
    }
  }
  {
    const enrollGroups = SCHEMA.groups.filter(g => g.enroll_operator_during_deploy);
    for (const grp of enrollGroups) {
      try {
        const meResp = await fetchWithRetry(apiUrl('web/currentuser?$select=Id,LoginName,Title'), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!meResp.ok) throw new Error(`current-user probe failed: HTTP ${meResp.status}`);
        const me = (await meResp.json()).d;
        const grpResp = await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(grp.name)}')?$select=Id`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!grpResp.ok) throw new Error(`group probe failed: HTTP ${grpResp.status}`);
        const groupId = (await grpResp.json()).d.Id;
        const memberResp = await fetchWithRetry(apiUrl(`web/sitegroups(${groupId})/users?$filter=Id eq ${me.Id}&$select=Id`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!memberResp.ok) throw new Error(`membership probe failed: HTTP ${memberResp.status}`);
        const alreadyMember = ((await memberResp.json()).d.results || []).length > 0;
        if (alreadyMember) {
          log('INFO', `Operator already a member of '${grp.name}'; membership left untouched.`);
          continue;
        }
        const digestE = await getDigest();
        const addResp = await fetchWithRetry(apiUrl(`web/sitegroups(${groupId})/users`), {
          method: 'POST',
          headers: spHeaders(digestE),
          body: JSON.stringify({ __metadata: { type: 'SP.User' }, LoginName: me.LoginName }),
        });
        if (!addResp.ok) {
          const text = await addResp.text();
          throw new Error(`enrolment failed: HTTP ${addResp.status} ${text}`);
        }
        selfEnrollments.push({ groupId, groupName: grp.name, userId: me.Id });
        log('INFO', `Enrolled operator '${me.Title}' into '${grp.name}' for this run; removed automatically at the end.`);
      } catch (err) {
        log('ERROR', `Operator self-enrolment for '${grp.name}': ${err.message}`);
        summary.errors.push({ phase: '1.3', group: grp.name, error: err.message });
      }
    }
  }
  if (summary.errors.length > 0) {
    log('ERROR', 'Operator self-enrolment failed; aborting before list creation.');
    await removeSelfEnrollments();
    return { ...summary, aborted: 'operator-enrolment-errors' };
  }

  markPhase('Phase 1.4 — maintenance unseal');
  // === Maintenance unseal (declared-seal columns) ===
  // Sealed columns reject UI schema edits even for site admins; the ONLY
  // legitimate maintenance path is this script. Unseal declared fields so
  // the run's write phases work unchanged; Phase 4.1 re-seals and
  // verifies after every field write is done.
  log('INFO', 'Starting Phase 1.4: maintenance unseal.');
  invalidateFieldShapes();  // probes reflect phase-start state
  {
    const sealDeclared = [];
    for (const list of SCHEMA.lists) {
      for (const col of list.fields_phase1) {
        if (col.seal) sealDeclared.push([list.title, col.title]);
      }
    }
    for (const lookup of SCHEMA.phase2_lookups) {
      if (lookup.field.seal) sealDeclared.push([lookup.list, lookup.field.title]);
    }
    if (sealDeclared.length > 0) {
      log('INFO', `Maintenance unseal: checking ${sealDeclared.length} declared-seal column(s).`);
      let unsealedCount = 0;
      // One lane per list: same-list field MERGEs race into save conflicts;
      // different lists unseal concurrently.
      await mapLanes(sealDeclared, ([listTitle]) => listTitle, async ([listTitle, columnTitle]) => {
        try {
          const shape = await readFieldShape(listTitle, columnTitle, null);
          if (shape && shape.Sealed) {
            const unsealDigest = await getDigest();
            await patchField(listTitle, columnTitle, { __metadata: { type: 'SP.Field' }, Sealed: false }, unsealDigest);
            unsealedCount += 1;
          }
        } catch (err) {
          log('ERROR', `Maintenance unseal '${listTitle}.${columnTitle}': ${err.message}`);
          summary.errors.push({ phase: '1.4', list: listTitle, column: columnTitle, error: err.message });
        }
      }, 4);
      log('INFO', `Maintenance unseal complete (${unsealedCount} column(s) unsealed for this run).`);
    }
  }

  markPhase('Phase 2.1 — list creation');
  // === Phase 2.1: lists + non-lookup columns + same-site lookups ===
  log('INFO', 'Group 2 — STRUCTURE');
  log('INFO', `Starting Phase 2.1: list creation. Release ${RELEASE_TAG}.`);
  invalidateFieldShapes();  // probes reflect phase-start state
  let digest = await getDigest();
  const listGuids = {};
  const earlyIsolationLists = new Set(SCHEMA.list_assignments
    .filter(la => la.break_inheritance && la.reconcile_mode === 'exact')
    .map(la => la.list));

  // Wave 1 — sequential, in dependency order: list existence, declared
  // list shape, GUID capture, early ACL isolation. Sequential because
  // wave 2's same-site lookup fields need every target list's GUID.
  const fieldWork = [];
  for (const list of SCHEMA.lists) {
    try {
      // Refresh the digest per list: a long Phase 2.1 (hundreds of field POSTs)
      // can outlive a single FormDigestValue (~30 min), so re-fetch per list
      // rather than reuse the one fetched before the loop (A4).
      digest = await getDigest();
      let createdThisRun = false;
      let listShape = await readListShape(list.title);
      if (listShape) {
        // The read-only preflight already rejected immutable template drift;
        // re-read here to close the preflight/write race and then reconcile
        // only the declared mutable list settings.
        assertListImmutableShape(list, listShape);
        log('INFO', `List '${list.title}' exists; validating and reconciling declared shape.`);
        summary.listsSkipped.push(list.title);
      } else {
        log('INFO', `Creating list '${list.title}' (${list.kind})...`);
        const body = {
          __metadata: { type: 'SP.List' },
          Title: list.title,
          BaseTemplate: list.base_template,
          Description: list.description || '',
          ContentTypesEnabled: list.content_types_enabled,
          EnableVersioning: list.enable_versioning,
          EnableMinorVersions: list.enable_minor_versions,
          MajorVersionLimit: list.major_version_limit,
        };
        const created = await postJson(apiUrl('web/lists'), body, digest);
        if (!created.d || typeof created.d.Id !== 'string') {
          throw new Error(`List '${list.title}' create returned an invalid response`);
        }
        createdThisRun = true;
        summary.listsCreated.push(list.title);
      }
      listShape = await reconcileListShape(list, digest);
      listGuids[list.title] = listShape.Id;

      // Close the provisioning window immediately for exact-mode lists. If
      // the process crashes before Phase 4.2, an inheriting list would otherwise
      // expose newly created fields/content to the site's inherited principals.
      // copyRoleAssignments=false leaves only SharePoint's current-operator
      // safety grant; clearSubscopes=false preserves every descendant scope.
      if (earlyIsolationLists.has(list.title)) {
        const aclResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(list.title)}')?$select=HasUniqueRoleAssignments`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!aclResp.ok) {
          const text = await aclResp.text();
          throw new Error(`early HasUniqueRoleAssignments probe failed: HTTP ${aclResp.status} ${text}`);
        }
        const aclJson = await aclResp.json();
        if (!aclJson.d.HasUniqueRoleAssignments) {
          digest = await getDigest();
          const breakResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)`), {
            method: 'POST',
            headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest },
          });
          if (!breakResp.ok) {
            const text = await breakResp.text();
            throw new Error(`early breakroleinheritance failed: HTTP ${breakResp.status} ${text}`);
          }
          log('INFO', `[Phase 2.1] Broke inheritance early on exact-mode list '${list.title}'.`);
        } else {
          log('INFO', `[Phase 2.1] Exact-mode list '${list.title}' already has unique role assignments.`);
        }

        // BreakRoleInheritance is a separate REST call from list creation, so
        // it cannot be atomic. Re-read ItemCount before adding fields: if a
        // site principal raced that narrow window, fail closed and let the
        // pre-seed gate prevent activation. Never delete the unexpected row.
        if (createdThisRun) {
          const countResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(list.title)}')?$select=ItemCount`), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
          if (!countResp.ok) {
            const text = await countResp.text();
            throw new Error(`post-isolation ItemCount probe failed: HTTP ${countResp.status} ${text}`);
          }
          const countJson = await countResp.json();
          const itemCount = countJson && countJson.d && countJson.d.ItemCount;
          if (!Number.isInteger(itemCount) || itemCount < 0) {
            throw new Error('post-isolation ItemCount probe returned an invalid response');
          }
          if (itemCount !== 0) {
            throw new Error(`new exact-mode list '${list.title}' contains ${itemCount} item(s) after early isolation; review the raced content before rerunning`);
          }
          log('INFO', `[Phase 2.1] New exact-mode list '${list.title}' remains empty after early isolation.`);
        }
      }

      fieldWork.push(list);
    } catch (err) {
      log('ERROR', `Phase 2.1 '${list.title}': ${err.message}`);
      summary.errors.push({ phase: '2.1', list: list.title, error: err.message });
    }
  }

  // Wave 2 — field provisioning, one lane per list: every target GUID now
  // exists, and concurrent schema writes to the SAME list race into save
  // conflicts while different lists are independent, so each list's fields
  // run sequentially inside a lane and the lanes run concurrently.
  await mapLanes(fieldWork, (list) => list.title, async (list) => {
    try {
      let laneDigest = await getDigest();
      for (const col of list.fields_phase1) {
        // Guard each field independently (A4): one field's failure (a transient
        // 429/403, or a missing lookup target) must not abandon the list's
        // remaining columns and its Title patch. Existing fields are never
        // trusted by name alone: immutable identity is checked before safely
        // mutable declared settings are reconciled and read back.
        try {
          laneDigest = await getDigest();
          const targetGuid = col.target_list ? listGuids[col.target_list] : null;
          if (col.target_list && !targetGuid) {
            throw new Error(`Lookup target ${col.target_list} not yet created`);
          }
          if (await reconcileDeclaredField(
            list.title, col, targetGuid, laneDigest, true,
          )) {
            summary.columnsSkipped += 1;
            continue;
          }
          let createUrl = apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/fields`);
          let createBody = col.body;
          if (col.target_list) {
            // SharePoint rejects POSTing an SP.FieldLookup directly to
            // /fields ("Please use addfield to add a lookup field"). Use the
            // supported FieldCollection.AddField REST method and keep its
            // SP.FieldCreationInformation object nested under `parameters`.
            // Properties that type does not carry are MERGEd and read back by
            // reconcileDeclaredField immediately below.
            const parameters = {
              ...col.lookup_creation_parameters,
              LookupListId: targetGuid,
            };
            createUrl = apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/fields/addfield`);
            createBody = { parameters };
          }
          await postJson(
            createUrl,
            createBody,
            laneDigest,
          );
          invalidateFieldShapes();  // new field: next probe re-enumerates
          await reconcileDeclaredField(
            list.title, col, targetGuid, laneDigest, false,
          );
          summary.columnsCreated += 1;
        } catch (err) {
          log('ERROR', `Phase 2.1 field '${list.title}.${col.title}': ${err.message}`);
          summary.errors.push({
            phase: '2.1', list: list.title, column: col.title, error: err.message,
          });
        }
      }

      if (list.title_patch) {
        const titleField = {
          title: 'Title',
          body: { ...list.title_patch, FieldTypeKind: 2 },
        };
        await reconcileDeclaredField(list.title, titleField, null, laneDigest, false);
      }

      laneDigest = await getDigest();
      await reconcileListValidation(list, laneDigest);
    } catch (err) {
      log('ERROR', `Phase 2.1 '${list.title}': ${err.message}`);
      summary.errors.push({ phase: '2.1', list: list.title, error: err.message });
    }
  }, 4);

  if (summary.errors.length > 0) {
    log('ERROR', 'Phase 2.1 schema reconciliation failed; aborting before deferred lookups and ACL work.');
    await removeSelfEnrollments();
    return { ...summary, aborted: 'phase-1-schema-errors' };
  }

  markPhase('Phase 2.2 — deferred lookups');
  // === Phase 2.2: deferred lookups ===
  log('INFO', 'Starting Phase 2.2: deferred lookups.');
  invalidateFieldShapes();  // probes reflect phase-start state
  digest = await getDigest();
  for (const lookup of SCHEMA.phase2_lookups) {
    try {
      digest = await getDigest();  // refresh per item (A4: digest lifetime)
      const targetGuid = listGuids[lookup.target_list];
      if (!targetGuid) throw new Error(`Lookup target ${lookup.target_list} missing.`);
      if (await reconcileDeclaredField(
        lookup.list, lookup.field, targetGuid, digest, true,
      )) {
        summary.columnsSkipped += 1;
        continue;
      }
      const parameters = {
        ...lookup.field.lookup_creation_parameters,
        LookupListId: targetGuid,
      };
      await postJson(
        apiUrl(`web/lists/getbytitle('${odataName(lookup.list)}')/fields/addfield`),
        { parameters },
        digest,
      );
      invalidateFieldShapes();  // new field: next probe re-enumerates
      await reconcileDeclaredField(
        lookup.list, lookup.field, targetGuid, digest, false,
      );
      summary.columnsCreated += 1;
    } catch (err) {
      log('ERROR', `Phase 2.2 ${lookup.list}.${lookup.field.title}: ${err.message}`);
      summary.errors.push({
        phase: '2.2', list: lookup.list, column: lookup.field.title, error: err.message,
      });
    }
  }

  if (summary.errors.length > 0) {
    log('ERROR', 'Phase 2.2 lookup reconciliation failed; aborting before indexes and ACL work.');
    await removeSelfEnrollments();
    return { ...summary, aborted: 'phase-2-schema-errors' };
  }

  markPhase('Phase 2.3 — indexed columns');
  // === Phase 2.3: indexed columns ===
  log('INFO', 'Starting Phase 2.3: indexed columns.');
  digest = await getDigest();
  for (const idx of SCHEMA.indexed_columns) {
    try {
      digest = await getDigest();  // refresh per item (A4: digest lifetime)
      await patchField(idx.list, idx.field, { __metadata: { type: 'SP.Field' }, Indexed: true }, digest);
    } catch (err) {
      log('ERROR', `Index ${idx.list}.${idx.field}: ${err.message}`);
      summary.errors.push({ list: idx.list, column: idx.field, error: err.message });
    }
  }

  markPhase('Phase 2.4 — field defaults');
  // === Phase 2.4: reconcile declared field defaults ===
  // Defaults are included in create-field bodies, but existing columns are
  // skipped in Phase 2.1. Re-applying the declared value makes upgrades
  // idempotent and lets a provisioned constant replace after-create flows.
  log('INFO', 'Starting Phase 2.4: field defaults.');
  for (const fieldDefault of SCHEMA.field_defaults) {
    try {
      digest = await getDigest();
      await patchField(
        fieldDefault.list,
        fieldDefault.field,
        {
          __metadata: { type: fieldDefault.metadata_type },
          DefaultValue: fieldDefault.default_value,
        },
        digest,
      );
      const actual = await readFieldShape(fieldDefault.list, fieldDefault.field, null, true);
      if (!actual
          || normalizeDefaultValue(actual.DefaultValue)
             !== normalizeDefaultValue(fieldDefault.default_value)) {
        throw new Error('DefaultValue readback did not match the declared value');
      }
    } catch (err) {
      log('ERROR', `Default ${fieldDefault.list}.${fieldDefault.field}: ${err.message}`);
      summary.errors.push({
        list: fieldDefault.list,
        column: fieldDefault.field,
        error: err.message,
      });
    }
  }

  markPhase('Phase 3.1 — views');
  // === Phase 3.1: declared views ===
  // Fields created through the REST field collection join no view, so a
  // fresh list shows a Title-only default view. Declared views are part of
  // the physical shape and reconcile like fields. Undeclared views are user
  // content and are never touched (unlike exact-mode ACLs).
  log('INFO', 'Group 3 — PRESENTATION');
  log('INFO', 'Starting Phase 3.1: views.');
  // Readback normalization: SP collapses nothing between tags but DOES write
  // self-closing tags with a space (`<FieldRef Name="X" />`); compare both
  // sides with inter-tag whitespace and the pre-`/>` space collapsed.
  const normalizeViewQuery = (value) => xmlDecode(String(value || '')).replace(/>\s+</g, '><').replace(/\s+\/>/g, '/>').trim();
  // The view CustomFormatter is stored in the view schema XML like
  // ViewQuery, so its readback is XML-entity-encoded ('>=' returns as
  // '&gt;='): decode before the canonical JSON comparison, both sides.
  const canonicalViewFormatter = (value) => canonicalJson(typeof value === 'string' ? xmlDecode(value) : value);
  async function mergeView(viewUrl, body, viewDigest) {
    const r = await fetchWithRetry(viewUrl, {
      method: 'POST',
      headers: spHeaders(viewDigest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`view MERGE failed: HTTP ${r.status} ${text}`);
    }
  }
  async function readViewShape(viewUrl) {
    const r = await fetchWithRetry(`${viewUrl}?$select=Id,Title,DefaultView,RowLimit,ViewQuery,PersonalView,CustomFormatter,ServerRelativeUrl,ViewFields&$expand=ViewFields`, {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (r.status === 404) return null;
    if (!r.ok) {
      const text = await r.text();
      if (isAbsent400(r.status, text)) return null;
      throw new Error(`view shape probe failed: HTTP ${r.status} ${text}`);
    }
    const j = await r.json();
    return j && j.d;
  }
  // Existence checks read ONE enumeration per list: views/getbytitle on an
  // absent view answers HTTP 400, which the browser console paints red even
  // though isAbsent400 handles it — operators read those lines as failures.
  const viewShapesByList = {};
  async function listViewShapes(listPath) {
    if (!(listPath in viewShapesByList)) {
      const r = await fetchWithRetry(apiUrl(`${listPath}/views?$select=Id,Title,DefaultView,RowLimit,ViewQuery,PersonalView,CustomFormatter,ServerRelativeUrl,ViewFields&$expand=ViewFields`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!r.ok) {
        const text = await r.text();
        throw new Error(`view enumeration failed: HTTP ${r.status} ${text}`);
      }
      const j = await r.json();
      viewShapesByList[listPath] = (j && j.d && j.d.results) || [];
    }
    return viewShapesByList[listPath];
  }
  async function readViewFieldNames(viewUrl) {
    const r = await fetchWithRetry(`${viewUrl}/viewfields`, {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`view fields read failed: HTTP ${r.status} ${text}`);
    }
    const j = await r.json();
    return (j && j.d && j.d.Items && j.d.Items.results) || [];
  }
  const deployView = async (view) => {
    try {
      let viewDigest = await getDigest();
      const listPath = `web/lists/getbytitle('${odataName(view.list)}')`;
      const viewUrl = apiUrl(`${listPath}/views/getbytitle('${odataName(view.title)}')`);
      const slugUrl = apiUrl(`${listPath}/views/getbytitle('${odataName(view.url_slug)}')`);
      const desiredBasename = `${view.url_slug}.aspx`;
      const urlBasename = (v) => String(v && v.ServerRelativeUrl || '').split('/').pop();
      // A view's .aspx name is fixed at creation from its Title, so creating
      // with a spaced display title bakes %20 into the URL forever, while a
      // Title rename never touches the URL. Create under the URL slug, then
      // rename to the declared title (same trick as field display titles).
      const createViewWithCleanUrl = async () => {
        const createBody = {
          __metadata: { type: 'SP.View' },
          Title: view.url_slug,
          PersonalView: false,
          Paged: true,
          ViewQuery: view.caml_query,
        };
        if (view.row_limit != null) createBody.RowLimit = view.row_limit;
        await postJson(apiUrl(`${listPath}/views`), createBody, viewDigest);
      };
      let existing = (await listViewShapes(listPath)).find((v) => v.Title === view.title) || null;
      // A slug-titled view already sitting on the clean URL is our own
      // half-finished migration (we only ever create with Title=slug):
      // adopt it instead of creating a second page. A FOREIGN view on that
      // URL is never touched — the create below would get a suffixed .aspx
      // and the URL drift gate fails the view closed.
      const halfMigrated = (await listViewShapes(listPath)).find(
        (v) => v.Title === view.url_slug && urlBasename(v) === desiredBasename,
      ) || null;
      if (!existing) {
        if (halfMigrated) {
          log('INFO', `[Phase 3.1] Adopting half-migrated view '${view.url_slug}' on '${view.list}' as '${view.title}'.`);
        } else {
          log('INFO', `[Phase 3.1] Creating view '${view.title}' on '${view.list}' at ${desiredBasename}...`);
          await createViewWithCleanUrl();
        }
        if (view.url_slug !== view.title) {
          await mergeView(slugUrl, { __metadata: { type: 'SP.View' }, Title: view.title }, viewDigest);
        }
      } else {
        if (existing.PersonalView) {
          throw new Error(`existing view '${view.title}' is a personal view; declared views must be public`);
        }
        if (urlBasename(existing) !== desiredBasename) {
          // URL migration to the clean URL: renames cannot change the .aspx
          // name, so the escaped-URL view is recreated. Declared views are
          // deployer-owned — every setting is reasserted below; only
          // bookmarks to the old URL break (one-time, noted in DEPLOY.md).
          log('INFO', `[Phase 3.1] Migrating view '${view.title}' on '${view.list}' from ${urlBasename(existing)} to ${desiredBasename}...`);
          if (!halfMigrated) await createViewWithCleanUrl();
          if (existing.DefaultView) {
            // Transfer the flag first: SP refuses to delete a default view.
            await mergeView(slugUrl, { __metadata: { type: 'SP.View' }, DefaultView: true }, viewDigest);
          }
          const delResp = await fetchWithRetry(apiUrl(`${listPath}/views('${existing.Id}')`), {
            method: 'POST',
            headers: spHeaders(viewDigest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'DELETE' }),
          });
          if (!delResp.ok) {
            const text = await delResp.text();
            throw new Error(`old view delete during URL migration failed: HTTP ${delResp.status} ${text}`);
          }
          if (view.url_slug !== view.title) {
            await mergeView(slugUrl, { __metadata: { type: 'SP.View' }, Title: view.title }, viewDigest);
          }
          existing = await readViewShape(viewUrl);
          if (!existing) throw new Error('view disappeared during URL migration');
        }
        // Narrow MERGE: send only drifted declared settings.
        const patchBody = { __metadata: { type: 'SP.View' } };
        if (normalizeViewQuery(existing.ViewQuery) !== normalizeViewQuery(view.caml_query)) {
          patchBody.ViewQuery = view.caml_query;
        }
        if (view.row_limit != null && existing.RowLimit !== view.row_limit) {
          patchBody.RowLimit = view.row_limit;
        }
        if (Object.keys(patchBody).length > 1) {
          await mergeView(viewUrl, patchBody, viewDigest);
        }
      }
      // Declared column set and order, reconciled exactly when drifted.
      // The initial read rides the enumeration ($expand=ViewFields); every
      // read after a write stays live.
      const actualFields = (existing && existing.ViewFields && existing.ViewFields.Items && existing.ViewFields.Items.results)
        ? existing.ViewFields.Items.results
        : await readViewFieldNames(viewUrl);
      const sameFields = actualFields.length === view.view_fields.length
        && actualFields.every((name, index) => name === view.view_fields[index]);
      if (!sameFields) {
        await postJson(`${viewUrl}/viewfields/removeallviewfields`, {}, viewDigest);
        for (const name of view.view_fields) {
          await postJson(`${viewUrl}/viewfields/addviewfield('${odataName(name)}')`, {}, viewDigest);
        }
      }
      // Row formatting is a declared view setting; views without a
      // declaration keep any hand-applied format.
      if (view.formatting != null) {
        // Phase-start shape decides (our own writes so far never touch
        // CustomFormatter); the fail-closed verify below always reads fresh.
        const current = existing || await readViewShape(viewUrl);
        if (!current) throw new Error('view disappeared before formatting reconciliation');
        if (canonicalViewFormatter(current.CustomFormatter) !== canonicalViewFormatter(view.formatting)) {
          await mergeView(viewUrl, { __metadata: { type: 'SP.View' }, CustomFormatter: view.formatting }, viewDigest);
        }
      }
      // Default flag last: SharePoint un-defaults the previous default view
      // automatically, and only a declared default may claim it. The
      // phase-start shape decides — nothing this lane writes clears a
      // DefaultView (only ONE declared default exists per list, validated),
      // and the fresh verify below fail-closes any surprise.
      const preFlag = existing || await readViewShape(viewUrl);
      if (!preFlag) throw new Error('view disappeared during reconciliation');
      if (view.set_default && !preFlag.DefaultView) {
        await mergeView(viewUrl, { __metadata: { type: 'SP.View' }, DefaultView: true }, viewDigest);
      }
      // Read back every declared setting and fail closed on any miss. The
      // readback rides ONE fresh GET: ViewFields is $expanded on the shape.
      const actual = await readViewShape(viewUrl);
      if (!actual) throw new Error('view readback failed after reconciliation');
      const readbackFields = (actual.ViewFields && actual.ViewFields.Items && actual.ViewFields.Items.results)
        || await readViewFieldNames(viewUrl);
      const drifted = [];
      if (normalizeViewQuery(actual.ViewQuery) !== normalizeViewQuery(view.caml_query)) {
        drifted.push(`ViewQuery (declared ${JSON.stringify(view.caml_query)}; readback ${JSON.stringify(actual.ViewQuery)})`);
      }
      if (view.row_limit != null && actual.RowLimit !== view.row_limit) {
        drifted.push(`RowLimit (declared ${view.row_limit}; readback ${actual.RowLimit})`);
      }
      if (view.set_default && !actual.DefaultView) drifted.push('DefaultView (declared true; readback false)');
      if (view.formatting != null
          && canonicalViewFormatter(actual.CustomFormatter) !== canonicalViewFormatter(view.formatting)) {
        drifted.push(`CustomFormatter (declared ${JSON.stringify(view.formatting)}; readback ${JSON.stringify(actual.CustomFormatter)})`);
      }
      const fieldsMatch = readbackFields.length === view.view_fields.length
        && readbackFields.every((name, index) => name === view.view_fields[index]);
      if (!fieldsMatch) {
        drifted.push(`ViewFields (declared ${JSON.stringify(view.view_fields)}; readback ${JSON.stringify(readbackFields)})`);
      }
      // Also catches SP auto-suffixing the .aspx name when a foreign view
      // occupies the clean URL.
      if (urlBasename(actual) !== desiredBasename) {
        drifted.push(`Url (declared ${desiredBasename}; readback ${urlBasename(actual)})`);
      }
      if (drifted.length > 0) {
        throw new Error(`did not retain declared view setting(s): ${drifted.join(', ')}`);
      }
      // Declared column widths ride SP's whole-document SetViewXml()
      // surface — the call the modern Lists UI makes when saving a dragged
      // width (live capture 2026-07-24). ColumnWidth FieldRefs bind by
      // DISPLAY name; internal names are accepted and silently reset the
      // widths. A property MERGE of ListViewXml is DESTRUCTIVE (treats the
      // fragment as the whole definition), so the only safe shape is:
      // read the server's full serialization, splice ONLY the ColumnWidth
      // block, refuse the write if anything else would change, write the
      // whole document back, and fail closed on readback drift. Runs after
      // the reconcile above because ViewFields changes reset widths.
      if (view.widths != null) {
        const readListViewXml = async () => {
          const r = await fetchWithRetry(`${viewUrl}?$select=ListViewXml`, {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
          if (!r.ok) {
            const text = await r.text();
            throw new Error(`view ListViewXml read failed: HTTP ${r.status} ${text}`);
          }
          const j = await r.json();
          return String((j && j.d && j.d.ListViewXml) || '');
        };
        const xmlAttr = (value) => String(value)
          .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/"/g, '&quot;');
        const columnWidthBlock = '<ColumnWidth>' + Object.entries(view.widths)
          .map(([name, px]) => `<FieldRef Name="${xmlAttr(name)}" width="${px}"/>`).join('')
          + '</ColumnWidth>';
        const stripColumnWidth = (xml) => xml.replace(/<ColumnWidth>[\s\S]*?<\/ColumnWidth>/, '');
        const normalizeXml = (xml) => xml.replace(/>\s+</g, '><').replace(/\s+\/>/g, '/>').trim();
        const currentXml = await readListViewXml();
        if (!currentXml.includes('</View>')) {
          throw new Error('view ListViewXml readback has no </View>; refusing widths write');
        }
        const nextXml = currentXml.includes('<ColumnWidth>')
          ? currentXml.replace(/<ColumnWidth>[\s\S]*?<\/ColumnWidth>/, columnWidthBlock)
          : currentXml.replace('</View>', `${columnWidthBlock}</View>`);
        if (stripColumnWidth(nextXml) !== stripColumnWidth(currentXml)) {
          throw new Error('widths splice guard tripped: non-ColumnWidth content would change; refusing SetViewXml');
        }
        if (nextXml !== currentXml) {
          viewDigest = await getDigest();
          await postJson(`${viewUrl}/setviewxml()`, { viewXml: nextXml }, viewDigest);
          const afterXml = await readListViewXml();
          if (normalizeXml(stripColumnWidth(afterXml)) !== normalizeXml(stripColumnWidth(currentXml))) {
            throw new Error('widths write altered view content beyond ColumnWidth; inspect the view before re-running');
          }
          const afterBlock = afterXml.match(/<ColumnWidth>[\s\S]*?<\/ColumnWidth>/);
          if (!afterBlock || normalizeXml(afterBlock[0]) !== normalizeXml(columnWidthBlock)) {
            throw new Error(`did not retain declared column widths (readback ${JSON.stringify(afterBlock ? afterBlock[0] : null)})`);
          }
        }
      }
      log('INFO', `[Phase 3.1] View '${view.title}' on '${view.list}' verified.`);
    } catch (err) {
      log('ERROR', `Phase 3.1 view '${view.list}'.'${view.title}': ${err.message}`);
      summary.errors.push({ phase: '3.1', list: view.list, view: view.title, error: err.message });
    }
  };
  // One lane per list: views live in the list schema, and concurrent schema
  // writes to the same list race into save conflicts — different lists are
  // independent, so their lanes run concurrently.
  await mapLanes(SCHEMA.views, (view) => view.list, deployView, 4);

  markPhase('Phase 3.2 — form formatting');
  // === Phase 3.2: form formatting ===
  // Declared list-form layouts (header/body/footer JSON) live on the list's
  // default item content type as ClientFormCustomFormatter — a JSON string
  // whose *JSONFormatter keys hold part OBJECTS (the pane-native encoding;
  // the Format pane displays string-encoded parts escaped). Lists without
  // a declaration are never touched.
  log('INFO', 'Starting Phase 3.2: form formatting.');
  const canonicalFormFormatter = (value) => {
    if (value == null || value === '') return null;
    let outer = value;
    if (typeof outer === 'string') {
      try { outer = JSON.parse(outer); } catch { return value; }
    }
    const canon = {};
    for (const key of Object.keys(outer).sort()) {
      // Encoding-agnostic: pre-pane-native deployments stored part values
      // as JSON STRINGS; parse before canonicalising so both encodings of
      // the same layout compare equal.
      let part = outer[key];
      if (typeof part === 'string' && part !== '') {
        try { part = JSON.parse(part); } catch { /* raw string stays */ }
      }
      canon[key] = canonicalJson(part);
    }
    return JSON.stringify(canon);
  };
  for (const form of SCHEMA.form_formatting) {
    try {
      digest = await getDigest();
      const listPath = `web/lists/getbytitle('${odataName(form.list)}')`;
      const ctResp = await fetchWithRetry(apiUrl(`${listPath}/contenttypes?$select=Name,StringId,ClientFormCustomFormatter`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!ctResp.ok) {
        const text = await ctResp.text();
        throw new Error(`content type enumeration failed: HTTP ${ctResp.status} ${text}`);
      }
      const ctJson = await ctResp.json();
      const contentTypes = (ctJson.d && ctJson.d.results) || [];
      const target = contentTypes.find((ct) => ct.StringId && ct.StringId.startsWith('0x01') && !ct.StringId.startsWith('0x0120'));
      if (!target) throw new Error('no default item content type found on the list');
      if (canonicalFormFormatter(target.ClientFormCustomFormatter) !== canonicalFormFormatter(form.client_form_custom_formatter)) {
        const r = await fetchWithRetry(apiUrl(`${listPath}/contenttypes('${target.StringId}')`), {
          method: 'POST',
          headers: spHeaders(digest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
          body: JSON.stringify({ __metadata: { type: 'SP.ContentType' }, ClientFormCustomFormatter: form.client_form_custom_formatter }),
        });
        if (!r.ok) {
          const text = await r.text();
          throw new Error(`form formatter MERGE failed: HTTP ${r.status} ${text}`);
        }
      }
      const verifyResp = await fetchWithRetry(apiUrl(`${listPath}/contenttypes('${target.StringId}')?$select=ClientFormCustomFormatter`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!verifyResp.ok) {
        const text = await verifyResp.text();
        throw new Error(`form formatter readback failed: HTTP ${verifyResp.status} ${text}`);
      }
      const verifyJson = await verifyResp.json();
      const readback = verifyJson.d && verifyJson.d.ClientFormCustomFormatter;
      if (canonicalFormFormatter(readback) !== canonicalFormFormatter(form.client_form_custom_formatter)) {
        throw new Error(`did not retain declared form formatting (declared ${JSON.stringify(form.client_form_custom_formatter)}; readback ${JSON.stringify(readback)})`);
      }
      log('INFO', `[Phase 3.2] Form formatting on '${form.list}' verified.`);
    } catch (err) {
      log('ERROR', `Phase 3.2 form '${form.list}': ${err.message}`);
      summary.errors.push({ phase: '3.2', list: form.list, error: err.message });
    }
  }

  markPhase('Phase 4.1 — seal declared columns');
  // === Phase 4.1: seal declared columns ===
  // Re-seal after every field write (1/2/3/3b/3d): sealed columns block UI
  // schema edits and deletion even for site admins — the strongest defense
  // when team owners are unavoidably site collection admins. Friction, not
  // enforcement: an admin can unseal via API, which is deliberate work, not
  // an accident.
  log('INFO', 'Group 4 — PROTECTION');
  log('INFO', 'Starting Phase 4.1: seal declared columns.');
  invalidateFieldShapes();  // probes reflect phase-start state
  {
    const sealDeclared = [];
    for (const list of SCHEMA.lists) {
      for (const col of list.fields_phase1) {
        if (col.seal) sealDeclared.push([list.title, col.title]);
      }
    }
    for (const lookup of SCHEMA.phase2_lookups) {
      if (lookup.field.seal) sealDeclared.push([lookup.list, lookup.field.title]);
    }
    let sealedCount = 0;
    // One lane per list (field MERGEs on the same list race into save
    // conflicts; lists are independent). After a lane's writes, ONE fresh
    // per-list enumeration serves every column's verify readback — the
    // per-field fresh GETs paid ~one round-trip per column for the same
    // server evidence (live DEBUG timing: this phase alone was 13.3s of a
    // 52s run). Verification still never trusts phase-start state: the
    // per-list invalidation forces a post-write re-enumeration.
    const sealByList = new Map();
    for (const [listTitle, columnTitle] of sealDeclared) {
      if (!sealByList.has(listTitle)) sealByList.set(listTitle, []);
      sealByList.get(listTitle).push(columnTitle);
    }
    await mapLanes([...sealByList.entries()], ([listTitle]) => listTitle, async ([listTitle, columns]) => {
      const failed = new Set();
      for (const columnTitle of columns) {
        try {
          const shape = await readFieldShape(listTitle, columnTitle, null);
          if (!shape) throw new Error('declared column missing at seal time');
          if (!shape.Sealed) {
            const sealDigest = await getDigest();
            await patchField(listTitle, columnTitle, { __metadata: { type: 'SP.Field' }, Sealed: true }, sealDigest);
            sealedCount += 1;
          }
        } catch (err) {
          failed.add(columnTitle);
          log('ERROR', `Phase 4.1 seal '${listTitle}.${columnTitle}': ${err.message}`);
          summary.errors.push({ phase: '4.1', list: listTitle, column: columnTitle, error: err.message });
        }
      }
      invalidateFieldShapes(listTitle);  // verify from post-write state
      for (const columnTitle of columns) {
        if (failed.has(columnTitle)) continue;
        try {
          const verify = await readFieldShape(listTitle, columnTitle, null);
          if (!verify || verify.Sealed !== true) {
            throw new Error(`did not retain sealed state (readback ${verify && verify.Sealed})`);
          }
        } catch (err) {
          log('ERROR', `Phase 4.1 seal '${listTitle}.${columnTitle}': ${err.message}`);
          summary.errors.push({ phase: '4.1', list: listTitle, column: columnTitle, error: err.message });
        }
      }
    }, 4);
    if (sealDeclared.length > 0) {
      log('INFO', `Phase 4.1 complete: ${sealDeclared.length} column(s) sealed and verified (${sealedCount} newly sealed).`);
    }
  }

  markPhase('Phase 4.2 — role inheritance and assignments');
  // === Phase 4.2: break inheritance + role assignments ===
  log('INFO', 'Starting Phase 4.2: role inheritance and assignments.');
  {
    let digest4 = await getDigest();

    // Cache resolved IDs across assignments to avoid redundant fetches.
    const principalIdCache = {};
    const roleDefIdCache = {};

    async function resolvePrincipalId(principal) {
      const cacheKey = JSON.stringify(principal);
      if (principalIdCache[cacheKey] !== undefined) return principalIdCache[cacheKey];
      let id;
      if (principal.kind === 'group') {
        const r = await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(principal.name)}')?$select=Id`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`Group '${principal.name}' not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else if (principal.kind === 'associated_owner_group') {
        const r = await fetchWithRetry(apiUrl('web/AssociatedOwnerGroup?$select=Id'), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`AssociatedOwnerGroup not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else if (principal.kind === 'associated_member_group') {
        const r = await fetchWithRetry(apiUrl('web/AssociatedMemberGroup?$select=Id'), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`AssociatedMemberGroup not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else if (principal.kind === 'associated_visitor_group') {
        const r = await fetchWithRetry(apiUrl('web/AssociatedVisitorGroup?$select=Id'), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`AssociatedVisitorGroup not found (HTTP ${r.status})`);
        const j = await r.json();
        id = j.d.Id;
      } else {
        throw new Error(`Unknown principal kind: ${principal.kind}`);
      }
      principalIdCache[cacheKey] = id;
      return id;
    }

    async function resolveRoleDefId(levelName) {
      if (roleDefIdCache[levelName] !== undefined) return roleDefIdCache[levelName];
      const r = await fetchWithRetry(apiUrl(`web/roledefinitions/getbyname('${odataName(levelName)}')?$select=Id`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!r.ok) throw new Error(`Role definition '${levelName}' not found (HTTP ${r.status})`);
      const j = await r.json();
      const id = j.d.Id;
      roleDefIdCache[levelName] = id;
      return id;
    }

    async function findDescendantUniqueScopeIds(listTitle) {
      const uniqueScopeIds = [];
      let itemsUrl = apiUrl(`web/lists/getbytitle('${odataName(listTitle)}')/items?$select=Id,HasUniqueRoleAssignments&$top=5000`);
      while (itemsUrl) {
        const itemsResp = await fetchWithRetry(itemsUrl, {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!itemsResp.ok) {
          const text = await itemsResp.text();
          throw new Error(`item/folder permission-scope enumeration failed: HTTP ${itemsResp.status} ${text}`);
        }
        const itemsJson = await itemsResp.json();
        for (const item of ((itemsJson.d && itemsJson.d.results) || [])) {
          if (item.HasUniqueRoleAssignments) uniqueScopeIds.push(item.Id);
        }
        itemsUrl = (itemsJson.d && itemsJson.d.__next) || null;
      }
      return uniqueScopeIds;
    }

    function assertNoDescendantUniqueScopes(listTitle, uniqueScopeIds) {
      if (uniqueScopeIds.length === 0) return;
      const sample = uniqueScopeIds.slice(0, 10).join(', ');
      throw new Error(`${uniqueScopeIds.length} item/folder unique permission scope(s) remain (item IDs: ${sample}${uniqueScopeIds.length > 10 ? ', ...' : ''}); review and remove or explicitly migrate them before rerunning; the deployer will never erase descendant scopes`);
    }

    for (const la of SCHEMA.list_assignments) {
      log('INFO', `[Phase 4.2] Processing role assignments for '${la.list}'...`);
      try {
        // Probe before *any* list ACL mutation. breakroleinheritance with
        // clearSubscopes=true would silently erase descendant exceptions on an
        // adopted/populated inheriting list before the old post-check saw them.
        // Exact mode always fails closed and leaves those scopes untouched.
        if (la.reconcile_mode === 'exact') {
          assertNoDescendantUniqueScopes(
            la.list,
            await findDescendantUniqueScopeIds(la.list),
          );
        }
        if (la.break_inheritance) {
          const checkResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')?$select=HasUniqueRoleAssignments`), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
          if (!checkResp.ok) {
            const text = await checkResp.text();
            throw new Error(`HasUniqueRoleAssignments probe failed: HTTP ${checkResp.status} ${text}`);
          }
          const checkJson = await checkResp.json();
          if (!checkJson.d.HasUniqueRoleAssignments) {
            digest4 = await getDigest();
            const breakResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)`), {
              method: 'POST',
              headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 },
            });
            if (!breakResp.ok) {
              const text = await breakResp.text();
              throw new Error(`breakroleinheritance failed: HTTP ${breakResp.status} ${text}`);
            }
            log('INFO', `[Phase 4.2] Broke inheritance on '${la.list}'.`);
          } else {
            log('INFO', `[Phase 4.2] '${la.list}' already has unique role assignments, reconciling existing bindings.`);
          }
        }

        // Resolve the complete desired state before removing anything. If a
        // principal or role cannot be resolved, fail closed without partially
        // applying an allowlist that could lock out the intended administrators.
        const resolvedAssignments = [];
        for (const assignment of la.assignments) {
          try {
            const principalId = await resolvePrincipalId(assignment.principal);
            const roleDefId = await resolveRoleDefId(assignment.level);
            resolvedAssignments.push({ assignment, principalId, roleDefId });
          } catch (err) {
            throw new Error(`cannot resolve desired assignment principal=${JSON.stringify(assignment.principal)}, level=${assignment.level}: ${err.message}`);
          }
        }

        const removeBinding = async (principalId, roleDefId, reason) => {
          digest4 = await getDigest();
          const rmResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments/removeroleassignment(principalid=${principalId},roleDefId=${roleDefId})`), {
            method: 'POST',
            headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 },
          });
          if (!rmResp.ok) {
            const text = await rmResp.text();
            throw new Error(`removeroleassignment (${reason}, principal ${principalId}, binding ${roleDefId}) failed: HTTP ${rmResp.status} ${text}`);
          }
          log('INFO', `[Phase 4.2] '${la.list}' removed ${reason} binding ${roleDefId} for principal ${principalId}.`);
        };

        // Establish every desired grant before pruning. This keeps at least the
        // declared owner path in place when breakroleinheritance(false) has
        // temporarily granted the current operator direct Full Control. Any add
        // failure aborts the list before exact mode removes a single binding.
        // GetByPrincipalId is positional in SharePoint REST; add/remove role
        // assignment methods below use their documented named parameters.
        for (const resolved of resolvedAssignments) {
          const desiredResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments/getbyprincipalid(${resolved.principalId})?$expand=RoleDefinitionBindings&$select=RoleDefinitionBindings/Id`), {
            headers: { 'Accept': 'application/json;odata=verbose' },
          });
          let desiredPresent = false;
          if (desiredResp.ok) {
            const desiredJson = await desiredResp.json();
            const desiredBindings = (desiredJson.d && desiredJson.d.RoleDefinitionBindings && desiredJson.d.RoleDefinitionBindings.results) || [];
            desiredPresent = desiredBindings.some(binding => binding.Id === resolved.roleDefId);
          } else if (desiredResp.status !== 404) {
            const text = await desiredResp.text();
            throw new Error(`desired binding probe failed: HTTP ${desiredResp.status} ${text}`);
          }
          if (!desiredPresent) {
            digest4 = await getDigest();
            const assignResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments/addroleassignment(principalid=${resolved.principalId},roleDefId=${resolved.roleDefId})`), {
              method: 'POST',
              headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 },
            });
            if (!assignResp.ok) {
              const text = await assignResp.text();
              throw new Error(`addroleassignment (principal ${resolved.principalId}, binding ${resolved.roleDefId}) failed before reconciliation: HTTP ${assignResp.status} ${text}`);
            }
          }
        }

        if (la.reconcile_mode === 'exact') {
          // Exact mode treats the mapping as an allowlist. Enumerate every
          // direct role binding, including principals absent from the mapping,
          // and remove all non-declared pairs. SharePoint's derived "Limited
          // Access" binding is protected: it is created to support lower-scope
          // access and is not a direct permission grant at this list scope.
          const expected = new Set(resolvedAssignments.map(
            x => `${x.principalId}:${x.roleDefId}`,
          ));
          const existingAssignments = [];
          let assignmentsUrl = apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments?$expand=Member,RoleDefinitionBindings&$select=Member/Id,Member/Title,RoleDefinitionBindings/Id,RoleDefinitionBindings/Name`);
          while (assignmentsUrl) {
            const allResp = await fetchWithRetry(assignmentsUrl, {
              headers: { 'Accept': 'application/json;odata=verbose' },
            });
            if (!allResp.ok) {
              const text = await allResp.text();
              throw new Error(`role assignment enumeration failed: HTTP ${allResp.status} ${text}`);
            }
            const allJson = await allResp.json();
            existingAssignments.push(...((allJson.d && allJson.d.results) || []));
            assignmentsUrl = (allJson.d && allJson.d.__next) || null;
          }
          for (const existing of existingAssignments) {
            const principalId = existing.Member && existing.Member.Id;
            if (principalId == null) {
              throw new Error('role assignment enumeration returned an entry without Member.Id');
            }
            const bindings = (existing.RoleDefinitionBindings && existing.RoleDefinitionBindings.results) || [];
            for (const binding of bindings) {
              if (binding.Name === 'Limited Access') {
                continue;
              }
              if (!expected.has(`${principalId}:${binding.Id}`)) {
                await removeBinding(principalId, binding.Id, 'unlisted');
              }
            }
          }
        } else {
          // Backward-compatible configured-principal mode: remove stale levels
          // for declared principals but leave unrelated principals untouched.
          for (const resolved of resolvedAssignments) {
            const raResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments/getbyprincipalid(${resolved.principalId})?$expand=RoleDefinitionBindings&$select=RoleDefinitionBindings/Id,RoleDefinitionBindings/Name`), {
              headers: { 'Accept': 'application/json;odata=verbose' },
            });
            if (raResp.ok) {
              const raJson = await raResp.json();
              const bindings = (raJson.d && raJson.d.RoleDefinitionBindings && raJson.d.RoleDefinitionBindings.results) || [];
              for (const binding of bindings) {
                if (binding.Name !== 'Limited Access' && binding.Id !== resolved.roleDefId) {
                  await removeBinding(resolved.principalId, binding.Id, 'stale');
                }
              }
            } else if (raResp.status !== 404) {
              const text = await raResp.text();
              throw new Error(`role assignment probe failed: HTTP ${raResp.status} ${text}`);
            }
          }
        }

        if (la.reconcile_mode === 'exact') {
          // List-level exact reconciliation is insufficient when a prior run
          // or manual change left item/folder scopes behind. SharePoint does
          // not clear descendant scopes when BreakRoleInheritance is called
          // again on a list that is already unique. Detect those scopes and
          // fail closed for operator review; never erase a potentially
          // deliberate exception automatically.
          assertNoDescendantUniqueScopes(
            la.list,
            await findDescendantUniqueScopeIds(la.list),
          );
        }

      } catch (err) {
        log('ERROR', `[Phase 4.2] '${la.list}': ${err.message}`);
        summary.errors.push({ phase: '4.2', list: la.list, error: err.message });
      }
    }
  }

  // A partial schema or ACL deployment must never be made to look activated
  // by seeding AppSettings. The error summary remains the operator's
  // repair checklist and the rerunnable deployment can be attempted again.
  if (summary.errors.length > 0) {
    log('ERROR', 'Deployment has unresolved schema or ACL errors; aborting before seed items.');
    await removeSelfEnrollments();
    return { ...summary, aborted: 'pre-seed-errors' };
  }

  markPhase('Phase 5.1 — seed items');
  // === Phase 5.1: seed singleton list items (extension-provided) ===
  log('INFO', 'Group 5 — DATA');
  log('INFO', 'Starting Phase 5.1: seed items.');

  function exactSeedValueEqual(actual, expected) {
    if (Object.is(actual, expected)) return true;
    // SharePoint REST serialises an empty single-line value as null even when
    // the create payload declared "". Treat only that storage-level empty-text
    // equivalence as canonical; do not coerce any other scalar values.
    if ((actual === null && expected === '') || (actual === '' && expected === null)) {
      return true;
    }
    if (Array.isArray(actual) || Array.isArray(expected)) {
      return Array.isArray(actual) && Array.isArray(expected)
        && actual.length === expected.length
        && actual.every((value, index) => exactSeedValueEqual(value, expected[index]));
    }
    if (actual && expected && typeof actual === 'object' && typeof expected === 'object') {
      // __metadata is a verbose-REST transport annotation, not stored field
      // state. Compare every logical key and value exactly, independent of
      // object-property order.
      const actualKeys = Object.keys(actual).filter(key => key !== '__metadata').sort();
      const expectedKeys = Object.keys(expected).filter(key => key !== '__metadata').sort();
      return actualKeys.length === expectedKeys.length
        && actualKeys.every((key, index) => key === expectedKeys[index])
        && actualKeys.every(key => exactSeedValueEqual(actual[key], expected[key]));
    }
    return false;
  }

  async function readSeedSingleton(seed) {
    const selectFields = ['Id', ...Object.keys(seed.fields)]
      .map(field => encodeURIComponent(field))
      .join(',');
    const existResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(seed.title)}')/items?$top=2&$select=${selectFields}`), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!existResp.ok) {
      const text = await existResp.text();
      throw new Error(`Cannot inspect singleton seed target '${seed.title}': HTTP ${existResp.status} ${text}`);
    }
    const existJson = await existResp.json();
    if (!existJson.d || !Array.isArray(existJson.d.results)) {
      throw new Error(`Singleton seed target '${seed.title}' returned an invalid response`);
    }
    return {
      rows: existJson.d.results,
      hasMore: Boolean(existJson.d.__next),
    };
  }

  function assertSeedSingletonMatches(seed, singleton) {
    if (singleton.hasMore || singleton.rows.length > 1) {
      throw new Error(`Singleton seed target '${seed.title}' contains multiple rows`);
    }
    if (singleton.rows.length !== 1) {
      throw new Error(`Singleton seed target '${seed.title}' does not contain exactly one row`);
    }
    const existing = singleton.rows[0];
    const mismatchedFields = Object.entries(seed.fields)
      .filter(([field, expected]) => (
        !Object.prototype.hasOwnProperty.call(existing, field)
        || !exactSeedValueEqual(existing[field], expected)
      ))
      .map(([field]) => field);
    if (mismatchedFields.length > 0) {
      throw new Error(`Existing singleton seed row in '${seed.title}' does not exactly match declared field(s): ${mismatchedFields.join(', ')}`);
    }
  }

  for (const seed of SCHEMA.seed_items) {
    // Fresh digest per seed: FormDigestValue expires (~30 min), so a
    // long run must not reuse one digest across every POST (rollback.js
    // per-operation getDigest pattern).
    const digest5 = await getDigest();
    try {
      // Idempotent only when the existing singleton is the declared singleton.
      // An arbitrary, mismatched or duplicate row must never suppress seeding
      // and make a partial/hostile deployment look activated.
      if (seed.skip_if_has_rows) {
        const singleton = await readSeedSingleton(seed);
        if (singleton.hasMore || singleton.rows.length > 1) {
          throw new Error(`Singleton seed target '${seed.title}' contains multiple rows`);
        }
        if (singleton.rows.length === 1) {
          assertSeedSingletonMatches(seed, singleton);
          log('INFO', `Verified existing singleton row in '${seed.title}' exactly matches the declared seed.`);
          continue;
        }
      }
      // Fetch the list's ListItemEntityTypeFullName so __metadata.type is
      // correct for ANY list title — SharePoint encodes non-alphanumeric
      // characters (e.g. '_') in the entity type name, so a hardcoded
      // 'SP.Data.<Title>ListItem' literal is wrong for underscore-containing
      // titles.
      const typeResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(seed.title)}')?$select=ListItemEntityTypeFullName`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!typeResp.ok) {
        throw new Error(`Cannot resolve ListItemEntityTypeFullName for '${seed.title}' (HTTP ${typeResp.status})`);
      }
      const entityType = (await typeResp.json()).d.ListItemEntityTypeFullName;

      const body = { __metadata: { type: entityType }, ...seed.fields };
      await postJson(apiUrl(`web/lists/getbytitle('${odataName(seed.title)}')/items`), body, digest5);
      if (seed.skip_if_has_rows) {
        // Re-read after creation to detect a concurrent insert between the
        // empty probe and POST. A mismatch or second row is an activation
        // failure; it is never auto-deleted.
        assertSeedSingletonMatches(seed, await readSeedSingleton(seed));
      }
      log('INFO', `Seeded and verified '${seed.title}'.`);
    } catch (err) {
      log('ERROR', `Phase 5.1 seed '${seed.title}': ${err.message}`);
      summary.errors.push({ phase: '5.1', list: seed.title, error: err.message });
    }
  }

  if (summary.errors.length > 0) {
    log('ERROR', 'Singleton seed verification failed; deployment is not activation-ready.');
    await removeSelfEnrollments();
    return { ...summary, aborted: 'phase-5-seed-errors' };
  }

  await removeSelfEnrollments();

  // Operator-perspective diagnostic (after enrolment cleanup, so the
  // run-scoped admin membership does not inflate the numbers): list ACLs
  // can LOOK correct while the signed-in account still deletes happily —
  // site collection administrators and Full Control holders bypass list
  // ACLs entirely. Member-level behaviour must be verified with an
  // ordinary member account.
  for (const listTitle of [...new Set(SCHEMA.list_assignments.map((la) => la.list))]) {
    try {
      const r = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(listTitle)}')/effectivebasepermissions`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!r.ok) {
        log('INFO', `Operator effective rights on '${listTitle}': probe returned HTTP ${r.status}.`);
        continue;
      }
      const j = await r.json();
      const low = Number((j && j.d && j.d.EffectiveBasePermissions && j.d.EffectiveBasePermissions.Low) || 0);
      const canDelete = (low & 8) === 8;          // DeleteListItems
      const canManage = (low & 2048) === 2048;    // ManageLists
      const isSiteAdmin = typeof _spPageContextInfo !== 'undefined' && _spPageContextInfo.isSiteAdmin === true;
      log('INFO', `Operator effective rights on '${listTitle}': delete items = ${canDelete}, manage list = ${canManage}, site collection admin = ${isSiteAdmin}. Site collection admins and Full Control holders bypass list ACLs (owners of a group-connected site are site collection admins, invisible in Check Permissions) — verify member behaviour with an ordinary member account.`);
    } catch (err) {
      log('INFO', `Operator effective rights on '${listTitle}': probe failed (${err.message}).`);
    }
  }

  markPhase(null);  // close the last phase's timing window
  summary.elapsedSeconds = Math.round((Date.now() - RUN_STARTED_AT) / 1000);
  if (DEBUG) {
    console.table(Object.entries(phaseTimings).map(([phase, ms]) => ({ phase, seconds: Math.round(ms / 100) / 10 })));
    dbg(`${requestCount} REST requests in ${summary.elapsedSeconds}s.`);
  }
  log('DONE', `Deployment complete. Lists +${summary.listsCreated.length}, columns +${summary.columnsCreated}, skipped ${summary.columnsSkipped}, errors ${summary.errors.length}. Elapsed ${summary.elapsedSeconds}s (${requestCount} requests).`);
  console.log(summary);
  return summary;
})();
