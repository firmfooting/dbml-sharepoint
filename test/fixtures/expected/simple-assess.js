/**
 * dbml-sharepoint SITE ASSESSMENT script (READ-ONLY).
 * Generated from: simple.dbml
 * Target site:  https://example.sharepoint.com/sites/test
 * Site role:    default
 * Release tag:  0.1.0-test
 * Schema:       v0.8
 * Deployer:     vdbml-sharepoint/0.1.0
 * Generated at: 2026-05-04T00:00:00Z
 *
 * Probes the site's capabilities against this pack's requirements and
 * prints a COMPATIBLE / DEGRADED / BLOCKED verdict. Makes NO changes:
 * every call is a GET except the contextinfo digest fetch, one read-only
 * CSOM ProcessQuery, and the OData $batch POSTs that carry those GETs, whose
 * parts are all GETs and which the transport below cannot spell any other
 * way.
 */
(async () => {
  const SITE_URL = "https://example.sharepoint.com/sites/test";
  const REQUIREMENTS = [
  {
    "description": "Operator holds ManageLists on the site",
    "key": "manage_lists_bit",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Site is not read-only / locked",
    "key": "site_not_locked",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Base template 100 is creatable on the web",
    "key": "list_template_100",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "List \u0027APP_Project\u0027 is absent or a redeploy target (not a foreign list)",
    "key": "collision:APP_Project",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "List \u0027APP_Task\u0027 is absent or a redeploy target (not a foreign list)",
    "key": "collision:APP_Task",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "List \u0027APP_AppSettings\u0027 is absent or a redeploy target (not a foreign list)",
    "key": "collision:APP_AppSettings",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Existing list \u0027APP_Project\u0027 is under the 5,000-item list view threshold",
    "key": "item_count:APP_Project",
    "level_on_fail": "WARN"
  },
  {
    "description": "Existing list \u0027APP_Task\u0027 is under the 5,000-item list view threshold",
    "key": "item_count:APP_Task",
    "level_on_fail": "WARN"
  },
  {
    "description": "Existing list \u0027APP_AppSettings\u0027 is under the 5,000-item list view threshold",
    "key": "item_count:APP_AppSettings",
    "level_on_fail": "WARN"
  },
  {
    "description": "Existing list \u0027APP_Project\u0027 carries this declaration\u0027s exact provenance marker",
    "key": "provenance_marker:APP_Project",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Existing list \u0027APP_Task\u0027 carries this declaration\u0027s exact provenance marker",
    "key": "provenance_marker:APP_Task",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Existing list \u0027APP_AppSettings\u0027 carries this declaration\u0027s exact provenance marker",
    "key": "provenance_marker:APP_AppSettings",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "Site regional time zone is the users\u0027 zone (dates are stored and shown in it, and the pack\u0027s `today` windows are read against its day)",
    "key": "time_zone",
    "level_on_fail": "WARN"
  },
  {
    "description": "Operator holds ManagePermissions",
    "key": "manage_permissions_bit",
    "level_on_fail": "BLOCKED"
  },
  {
    "description": "CSOM ProcessQuery available (group owner correction)",
    "key": "process_query",
    "level_on_fail": "WARN"
  },
  {
    "description": "SP.Field.CustomFormatter property surface present",
    "key": "custom_formatter_surface",
    "level_on_fail": "WARN"
  },
  {
    "description": "ClientFormCustomFormatter property surface present",
    "key": "form_formatter_surface",
    "level_on_fail": "WARN"
  },
  {
    "description": "Service-managed version auto-trim does not override declared limits",
    "key": "version_trim_mode",
    "level_on_fail": "WARN"
  }
];
  const TARGETS = {
  "base_templates": [
    100
  ],
  "declares_column_formatting": true,
  "declares_form_formatting": true,
  "declares_groups": true,
  "declares_prevent_deletion": false,
  "declares_seal": false,
  "declares_versioning": true,
  "group_renames": [],
  "index_change_ceiling": 20000,
  "level_renames": [],
  "library_folders": [],
  "library_roots": [],
  "list_display_titles": [
    [
      "APP_Project",
      [
        [
          "SortOrder",
          "Sort Order"
        ]
      ]
    ],
    [
      "APP_Task",
      [
        [
          "DueDate",
          "Due Date"
        ]
      ]
    ]
  ],
  "list_markers": [
    [
      "APP_Project",
      "Provisioned by dbml-sharepoint from simple-test for list Project."
    ],
    [
      "APP_Task",
      "Provisioned by dbml-sharepoint from simple-test for list Task."
    ],
    [
      "APP_AppSettings",
      "Provisioned by dbml-sharepoint from simple-test for list AppSettings."
    ]
  ],
  "list_renames": [],
  "list_titles": [
    "APP_Project",
    "APP_Task",
    "APP_AppSettings"
  ],
  "list_unique_columns": [],
  "list_view_threshold": 5000,
  "requires_manage_permissions": true,
  "uses_today": true
};
  const NOT_ASSESSABLE = [
  "Power Automate / Power Apps inventory (lives in Power Platform APIs, no SharePoint REST surface from site context)",
  "Audit settings (SSOM-only; not exposed via CSOM/REST)",
  "Information-barrier segments and mode (tenant-admin only)",
  "Authoritative tenant sharing capability and storage quota ceilings (tenant-admin SiteProperties)",
  "Retention POLICY coverage of the site (only inferable via the Preservation Hold Library signal)",
  "Webhook subscription enumeration (bound to the creating app identity)",
  "Edit-form column-description suppression (SharePoint platform behaviour)",
  "[$Created] view-field resolution in formatters (tenant/locale dependent)",
  "Format-pane JSON display encoding (renders identically either way)"
];

  const log = (level, msg) => console.log(`[SP-ASSESS] [${level}] ${msg}`);

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

  // SharePoint's by-name getters do not uniformly 404 for a missing item:
  // fields/getbyinternalnameortitle ("Column 'X' does not exist") and
  // views/getbytitle ("The specified view is invalid.") both throw
  // System.ArgumentException as HTTP 400 with locale-invariant code
  // -2147024809. Exactly that shape means "absent"; anything else stays
  // fatal in the caller.
  //
  // Here rather than in deploy/_shape_probes.js.j2, where it was, because
  // the maintenance sidecars need the same fact: columns.js.txt read its
  // own successful delete as a failure for want of it (#383, live
  // 2026-09-03). AGENTS.md: where both sides need the same fact, it lives
  // in a shared module.
  const isAbsent400 = (status, text) => {
    if (status !== 400) return false;
    let code = '';
    try { code = String(JSON.parse(text)?.error?.code || ''); } catch { return false; }
    return code.includes('-2147024809') && code.includes('System.ArgumentException');
  };

  // The page a throttled BROWSER is redirected to. Matched on the final URL
  // rather than on the status, because the status is a property of OUR
  // request: the page is HTML and every call here asks for JSON, so it
  // arrives as 406 Not Acceptable. A caller that asked for something else
  // would see a different status and the same throttle. Keying on 406 would
  // also have retried every genuine content-negotiation refusal five times.
  const THROTTLE_PAGE = /\/_layouts\/15\/throttle\.htm(\?|$)/i;
  const isThrottled = (r) => r.status === 429 || r.status === 503
    || THROTTLE_PAGE.test(r.url || '');

  // ONE PAUSE FOR THE WHOLE RUN, not one per lane. `mapLanes` puts four
  // workers through this helper at once, and Learn is explicit that
  // "throttled requests count towards usage limits, so failure to honor
  // Retry-After may result in more throttling" and that an application
  // should "reduce concurrency after throttling". Four independent backoffs
  // keep spending quota against a tenant that is already refusing, and then
  // resume together. The first request to be refused opens this gate; every
  // request waits on it before going out.
  let throttleGate = null;
  async function passThrottleGate() {
    while (throttleGate) await throttleGate;
  }
  function holdEveryLane(seconds) {
    if (!throttleGate) {
      throttleGate = sleep(seconds * 1000).then(() => { throttleGate = null; });
    }
    return throttleGate;
  }

  // Retry-After-aware fetch. Honour the server's Retry-After (seconds),
  // else back off exponentially (capped), up to `attempts` before
  // returning the final response to the caller's own error handling.
  //
  // The defaults are a JUDGEMENT, not a measurement: eight attempts capped at
  // 60s is about four minutes of patience. The browser redirect carries no
  // Retry-After -- it is an HTML page -- so on the path that prompted this
  // there is nothing to honour and the backoff is all there is. Waiting four
  // minutes on a paste is cheap; a deploy abandoned mid-Phase-4 leaves
  // columns unsealed and needs the whole run again.
  //
  // `cache: 'no-store'` on every request, applied AFTER the caller's options
  // so no caller can opt back in. A by-title list read can otherwise answer
  // with a list that no longer exists. MEASURED 2026-09-13, revision
  // c9c55b1f, `transport.cache.id-select-after-recreate` and
  // `transport.cache.shape-select-after-recreate` in
  // list-identity-cache-probe.js: after a hard delete and a create under the
  // same title, which is a rollback then a redeploy, both by-title reads
  // answered the DEAD list, under `Cache-Control: private, max-age=0` and
  // `ETag: "1"`. The enumeration and a unique-parameter read answered the
  // live one, and the same run with the browser's cache disabled was fresh
  // throughout, so the entry is the browser's.
  //
  // Two reads that go stale TOGETHER agree with each other, and then an
  // ownership guard passes while naming an object the run never saw. That is
  // the failure this whole transport is guarded for, so the directive goes
  // here rather than at the call sites that happen to know about it today.
  // All three candidates measured fresh (`remedy-no-store`,
  // `remedy-no-cache-header`, `remedy-reload`); no-store is the one that
  // neither reads an entry nor leaves one.
  async function fetchWithRetry(url, opts, attempts = 8) {
    const t0 = Date.now();
    const init = { ...(opts || {}), cache: 'no-store' };
    for (let i = 0; ; i++) {
      await passThrottleGate();
      const r = await fetch(url, init);
      requestCount += 1;
      if (isThrottled(r) && i < attempts) {
        const ra = Number(r.headers.get('Retry-After')) || Math.min(2 ** i, 60);
        const how = THROTTLE_PAGE.test(r.url || '')
          ? `redirected to the throttling page (HTTP ${r.status})`
          : `HTTP ${r.status}`;
        log('INFO', `Throttled, ${how}; every lane waits ${ra}s, retry ${i + 1}/${attempts}.`);
        await holdEveryLane(ra);
        continue;
      }
      dbg(`${(opts && opts.method) || 'GET'} ${url.length > 160 ? `${url.slice(0, 160)}...` : url} -> ${r.status} in ${Date.now() - t0}ms${i > 0 ? ` (${i} throttle retries)` : ''}`);
      return r;
    }
  }
  const absListUrl = (title) => `${window.location.origin}${WEB}/Lists/${encodeURIComponent(title)}`;
  log('INFO', 'Read-only assessment. No changes are made.');

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

  // The READ half of the $batch transport, and only the read half: this
  // script includes `_http_batch_read.js.j2` where the write-capable scripts
  // include `_http_batch.js.j2`, so the one thing it gains is BatchReader,
  // which spells every part `GET`. `_http_write.js.j2` and its `spHeaders`
  // stay out, which is what keeps the no-write property readable here rather
  // than being a claim about what a shared partial happens to hold.
  // BatchReader's outer request still needs X-RequestDigest even though every
  // part is a read (measured 2026-09-04: without it the identical envelope
  // came back HTTP 403), and getDigest above is where that comes from.

  // The accumulated body is flushed before it passes this, and it is a
  // constructor option. 200 KiB is far under both measured points above, and
  // the digest each part repeats puts roughly 200 operations in it.
  const BATCH_BODY_BUDGET_BYTES = 200 * 1024;
  // What the envelope costs around the parts: the outer boundary, the
  // ChangeSet content type, and both closing boundaries.
  const BATCH_ENVELOPE_BYTES = 256;
  // A boundary token is a fixed shape, so a placeholder of the same length
  // measures a part exactly without committing to the token its request will
  // eventually carry.
  const BATCH_BOUNDARY_SAMPLE = 'changeset_0000000000000000';
  const batchBoundary = (label) => {
    const chunk = () => Math.random().toString(36).slice(2, 10);
    return `${label}_${chunk()}${chunk()}`;
  };
  const utf8Bytes = (text) => new TextEncoder().encode(String(text)).length;

  // The read companion. A $batch envelope carries query parts at the TOP
  // level, outside any ChangeSet, and each answers with its own status line
  // and JSON body, so a phase that verifies N objects can read them all in
  // one request instead of N.
  //
  // MEASURED on a live tenant 2026-09-04, on the same site the index phase
  // runs against: 58 field GETs sent as one $batch answered HTTP 200 with 58
  // part statuses at 200 in 371 ms, where the same 58 GETs issued one at a
  // time took 14.7 s. The outer request still needs X-RequestDigest even
  // though every part is a read: without it the identical envelope came back
  // HTTP 403, "The security validation for this page is invalid".
  //
  // Reads are counted separately from writes and never mixed into one
  // envelope. BatchWriter reads its part statuses by counting every
  // 'HTTP/1.1 nnn' in the response, which a query part's JSON body could
  // otherwise contribute to.
  class BatchReader {
    constructor({ getDigest, fetchWithRetry, apiUrl, log, bodyBudgetBytes = BATCH_BODY_BUDGET_BYTES }) {
      this.getDigest = getDigest;
      this.fetchWithRetry = fetchWithRetry;
      this.apiUrl = apiUrl;
      this.log = log;
      this.bodyBudgetBytes = bodyBudgetBytes;
      this.origin = window.location.origin;
      this.pending = [];
      this.pendingBytes = BATCH_ENVELOPE_BYTES;
      this.requests = 0;
      // Every answered part, in the order add() queued them, across as many
      // requests as the budget forced. A caller compares by position, so a
      // flush must never renumber what came before it.
      this.results = [];
    }

    // `path` is what apiUrl() takes, so a read is spelled here exactly as it
    // would be for a single GET.
    async add(path) {
      const op = { url: `${this.origin}${this.apiUrl(path)}` };
      const cost = utf8Bytes(this._part(op, BATCH_BOUNDARY_SAMPLE));
      if (this.pending.length && this.pendingBytes + cost > this.bodyBudgetBytes) {
        await this.flush();
      }
      this.pending.push(op);
      this.pendingBytes += cost;
    }

    // One top-level application/http part. No digest and no Content-Type: a
    // query part carries no body, and the Accept is what makes the answer
    // verbose OData, the same annotation the single-GET helpers ask for.
    _part(op, outer) {
      return `--${outer}\r\n`
        + 'Content-Type: application/http\r\n'
        + 'Content-Transfer-Encoding: binary\r\n'
        + '\r\n'
        + `GET ${op.url} HTTP/1.1\r\n`
        + 'Accept: application/json;odata=verbose\r\n'
        + '\r\n';
    }

    _encode(ops, outer) {
      return ops.map((op) => this._part(op, outer)).join('') + `--${outer}--\r\n`;
    }

    // Each part's status and body, in order. The boundary is read off the
    // response's own first line rather than its Content-Type header, because
    // that is the one place it is spelled identically whatever the header
    // casing, and a body that does not open with one is not a multipart
    // answer at all.
    _parts(text) {
      const opening = String(text).split('\r\n', 1)[0].trim();
      if (!opening.startsWith('--')) return null;
      const boundary = opening.slice(2).replace(/--$/, '');
      const parts = [];
      for (const chunk of String(text).split(`--${boundary}`)) {
        const at = chunk.indexOf('HTTP/1.1 ');
        if (at === -1) continue;
        const headEnd = chunk.indexOf('\r\n\r\n', at);
        parts.push({
          status: Number(chunk.slice(at + 9, at + 12)),
          body: headEnd === -1 ? '' : chunk.slice(headEnd + 4).replace(/\r\n$/, ''),
        });
      }
      return parts;
    }

    _refuse(message, detail) {
      this.log('ERROR', message);
      const failure = new Error(message);
      Object.assign(failure, detail, { batchFailure: true });
      return failure;
    }

    async flush() {
      if (!this.pending.length) return { requests: 0, answered: 0 };
      const ops = this.pending.splice(0);
      this.pendingBytes = BATCH_ENVELOPE_BYTES;
      const digest = await this.getDigest();
      const outer = batchBoundary('batch');
      const body = this._encode(ops, outer);
      // No Accept on the outer request, for #401's reason: a JSON Accept
      // turns the throttling-page redirect into a 406 only its URL names.
      const response = await this.fetchWithRetry(this.apiUrl('$batch'), {
        method: 'POST',
        headers: {
          'Content-Type': `multipart/mixed; boundary=${outer}`,
          'X-RequestDigest': digest,
        },
        body,
      });
      this.requests += 1;
      const text = await response.text().catch((err) => `body unreadable: ${String(err).slice(0, 200)}`);
      if (isThrottled(response)) {
        throw this._refuse(
          `$batch of ${ops.length} query part(s) was throttled (HTTP ${response.status}) and none answered`,
          { throttled: true, sent: ops.length, answered: 0, refused: ops.length },
        );
      }
      if (!response.ok) {
        throw this._refuse(
          `$batch of ${ops.length} query part(s) was refused: HTTP ${response.status} ${spError(text)}`,
          { throttled: false, sent: ops.length, answered: 0, refused: ops.length },
        );
      }
      const parts = this._parts(text);
      if (!parts || parts.length !== ops.length) {
        throw this._refuse(
          `$batch of ${ops.length} query part(s) answered HTTP ${response.status} with `
          + `${parts ? parts.length : 0} part status(es), so the reads cannot be accounted for`,
          { throttled: false, sent: ops.length, answered: 0, refused: ops.length },
        );
      }
      const refused = parts.filter((part) => !(part.status >= 200 && part.status < 300));
      if (refused.length) {
        const throttledParts = refused.filter((part) => part.status === 429 || part.status === 503);
        throw this._refuse(
          `$batch of ${ops.length} query part(s): ${parts.length - refused.length} answered, `
          + `${refused.length} refused (part statuses ${parts.map((part) => part.status).join(', ')})`,
          {
            throttled: throttledParts.length > 0,
            sent: ops.length, answered: parts.length - refused.length, refused: refused.length,
          },
        );
      }
      for (const part of parts) {
        // The verbose envelope, unwrapped to the payload a single GET returns
        // as `d`. A part that answered 2xx with something unparseable is a
        // read that did not happen, so it refuses rather than yielding null.
        let payload;
        try {
          payload = JSON.parse(part.body);
        } catch {
          throw this._refuse(
            `$batch of ${ops.length} query part(s) answered a part that is not JSON, `
            + 'so the reads cannot be accounted for',
            { throttled: false, sent: ops.length, answered: 0, refused: ops.length },
          );
        }
        this.results.push(payload && Object.prototype.hasOwnProperty.call(payload, 'd')
          ? payload.d : payload);
      }
      dbg(`$batch read ${ops.length} query part(s) in ${utf8Bytes(body)} bytes; all answered.`);
      return { requests: 1, answered: ops.length };
    }

    // Flushes what is left and hands back every part's payload in the order
    // it was queued.
    async done() {
      await this.flush();
      return this.results;
    }
  }

  // The whole assessment, taking its collaborators as an argument so the
  // standalone script and the deploy can share it without a second copy.
  async function assessSite(ctx) {
    const { requirements: REQUIREMENTS, targets: TARGETS,
            notAssessable: NOT_ASSESSABLE, log, web: WEB, origin: ORIGIN,
            fetchWithRetry, apiUrl, odataName, getDigest, getContextWebInformation,
            verdictLevel } = ctx;
    // Fail closed on a caller-built targets: a missing key is a bare TypeError
    // several probes in, and every one of these is read below. The two
    // ceilings are here because a missing one is worse than a TypeError: every
    // comparison against NaN is false, so the item-count probe would report
    // every list as comfortably under a threshold it could not read.
    const missingTargets = ['base_templates', 'list_titles', 'list_markers',
      'declares_seal', 'declares_prevent_deletion', 'declares_column_formatting',
      'declares_form_formatting', 'declares_versioning', 'declares_groups',
      'list_view_threshold', 'index_change_ceiling',
    ].filter((k) => !(k in (TARGETS || {})));
    if (missingTargets.length) throw new Error(`assess-targets-incomplete: ctx.targets is missing ${missingTargets.join(', ')}`);
    // And on the collaborators: a probe inside its own try reports an absent one as the site's answer, not a build fault.
    const missingCollaborators = ['log', 'fetchWithRetry', 'apiUrl', 'odataName',
      'getDigest', 'getContextWebInformation',
    ].filter((k) => typeof ctx[k] !== 'function');
    if (missingCollaborators.length) throw new Error(`assess-context-incomplete: ctx is missing ${missingCollaborators.join(', ')}`);
    // BatchReader comes off the enclosing scope rather than out of ctx, because
    // both hosts include the partial that declares it and neither call site can
    // be changed by a pack. Named here for the same reason as the two checks
    // above: without it the first batched read reports the site as unreadable.
    if (typeof BatchReader !== 'function') throw new Error('assess-transport-incomplete: BatchReader is not in scope; the host script must include _http_batch_read.js.j2');
    const findings = [];
    let verdict = null;
    const finding = (tier, key, level, detail) => {
      findings.push({ tier, key, level, detail });
      log(level, `[T${tier}] ${key}: ${detail}`);
    };
    // A property the site did not return is not a value. Printing it as one
    // put the literal word `undefined` in operator-facing lines.
    const reported = (v, fallback = '(not reported)') => (v == null ? fallback : v);
    // The three requirement keys one list read feeds, spelled once. The
    // verdict loop walks REQUIREMENTS and skips a key nothing filed a finding
    // for, so a key spelled two ways here is a requirement that silently
    // passes. `assessgen.derive_requirements` builds the same three.
    const collisionKey = (title) => `collision:${title}`;
    const markerKey = (title) => `provenance_marker:${title}`;
    const sizeKey = (title) => `item_count:${title}`;

    // Read-only GET helper: returns parsed .d (or the raw json) or null.
    async function probeGet(suffix, continuation = false) {
      try {
        const r = await fetchWithRetry(continuation ? suffix : apiUrl(suffix), { headers: { 'Accept': 'application/json;odata=verbose' } });
        if (!r.ok) return { ok: false, status: r.status };
        const j = await r.json();
        const d = (j && j.d !== undefined) ? j.d : j;
        // Every caller reads a property off `d`, so a 200 with a null body was
        // an `ok` result that threw on the first read. Shape alone is judged,
        // because the call sites take differing response shapes.
        if (d === null || typeof d !== 'object') return { ok: false, error: 'non-object payload' };
        return { ok: true, d };
      } catch (err) {
        return { ok: false, error: err.message };
      }
    }

    // probeGet for many paths at once: one OData $batch of top-level query
    // parts, answered in the order they were queued and in probeGet's shape,
    // where this script used to make one request per declared list and per
    // declared folder. On a large family that is the whole cost of tier 2.
    //
    // The refusal is all-or-nothing ON PURPOSE. BatchReader reads the
    // PER-OPERATION status and refuses the envelope on any non-2xx part or a
    // part count that does not match, because the outer request answers HTTP
    // 200 either way (measured 2026-09-04: 1000 operations came back 200 with
    // 363 of them failed inside the body). A refusal therefore reports every
    // path in that envelope as unanswered, and every caller below records
    // NOT-ASSESSABLE for it rather than a value. Losing the parts that did
    // answer is the price of never recording a finding from a read that
    // cannot be accounted for.
    //
    // Null, not an array of failures, for the one transport failure that says
    // nothing about the paths: the outer $batch request needs X-RequestDigest
    // even though every part is a read (measured 2026-09-04, without it the
    // identical envelope came back HTTP 403), so a site that refuses
    // contextinfo cannot be batched at all and its reads go out singly
    // instead of being reported unassessable.
    async function probeMany(paths) {
      if (!paths.length) return [];
      let payloads;
      try {
        const reader = new BatchReader({ getDigest, fetchWithRetry, apiUrl, log });
        for (const path of paths) await reader.add(path);
        payloads = await reader.done();
      } catch (err) {
        if (err.digestFailure) return null;
        return paths.map(() => ({ ok: false, error: `batched read refused (${err.message})` }));
      }
      // The same shape test probeGet makes, plus a missing entry: a part
      // count BatchReader let through is still not a payload per path.
      return paths.map((_path, at) => {
        const d = payloads[at];
        return (d === null || typeof d !== 'object')
          ? { ok: false, error: 'non-object payload' }
          : { ok: true, d };
      });
    }

    // Which list titles exist, from ONE enumeration, answered
    // case-insensitively and without a getbytitle 404 (a first deploy has every
    // declared list absent, and the browser paints each 404 red). Null means
    // "enumeration refused"; callers fall back to per-list probing.
    const malformedNextPage = (page) => page.__next != null && typeof page.__next !== 'string';
    const assessListTitleSet = async () => {
      const pageSize = 5000;
      const r = await probeGet(`web/lists?$select=Title&$top=${pageSize}`);
      if (!r.ok || malformedNextPage(r.d) || !Array.isArray(r.d.results)
        || r.d.results.some((row) => !row || typeof row.Title !== 'string')) return null;
      const results = r.d.results;
      if (results.length >= pageSize || (typeof r.d.__next === 'string' && r.d.__next !== '')) return null;
      return new Set(results.map((l) => String(l.Title == null ? '' : l.Title).toLowerCase()));
    };

    // ===================================================================
    // Tier 1: always-run enumerations
    // ===================================================================
    log('INFO', 'Tier 1: site capability enumeration.');

    // Site identity & provisioning template, the best single capability tell.
    {
      const web = await probeGet('web?$select=WebTemplate,Configuration,Language,UIVersion');
      if (web.ok) finding(1, 'web_template', 'INFO',
        `Template ${reported(web.d.WebTemplate)}#${reported(web.d.Configuration)}, LCID ${reported(web.d.Language)}.`);
      else finding(1, 'web_template', 'INFO', `Could not read web template (HTTP ${web.status || web.error}).`);
    }

    // Site lock / read-only: a locked site blocks any deploy.
    {
      const site = await probeGet('site?$select=ReadOnly,LockIssue');
      // A payload carrying neither property never said the site was unlocked,
      // and reading it as writable passed a BLOCKED-level requirement unchecked.
      const answered = site.ok && ('ReadOnly' in site.d || 'LockIssue' in site.d);
      if (answered && (site.d.ReadOnly === true || site.d.LockIssue)) {
        finding(1, 'site_not_locked', 'BLOCKED', `Site is read-only/locked: ${site.d.LockIssue || 'ReadOnly'}.`);
      } else if (answered) {
        finding(1, 'site_not_locked', 'PASS', 'Site is writable (not locked).');
      } else if (site.ok) {
        finding(1, 'site_not_locked', 'NOT-ASSESSABLE',
          'The site answered without ReadOnly or LockIssue, so whether it is locked is unknown.');
      } else {
        finding(1, 'site_not_locked', 'WARN', `Could not read lock state (HTTP ${site.status || site.error}).`);
      }
    }

    // Platform build fingerprint, through the shared helper: a second parse here reproduced #282 in both assess paths.
    try {
      const info = await getContextWebInformation();
      finding(1, 'platform_build', 'INFO', `SharePoint build ${reported(info.LibraryVersion)}.`);
    } catch (err) {
      finding(1, 'platform_build', 'INFO', `Could not read build version (${err.message}).`);
    }

    // Effective permissions: decode the bits the deploy needs + NoScript.
    {
      const perms = await probeGet('web?$select=EffectiveBasePermissions');
      // The payload is tested apart from the transport: a 200 carrying no
      // EffectiveBasePermissions took the same arm as a failed request.
      const bits = perms.ok && perms.d ? perms.d.EffectiveBasePermissions : null;
      if (bits) {
        const low = Number(bits.Low || 0);
        const has = (bit) => (low & bit) === bit;
        finding(1, 'manage_lists_bit', has(0x800) ? 'PASS' : 'BLOCKED',
          has(0x800) ? 'Operator holds ManageLists.' : 'Operator LACKS ManageLists, so lists cannot be created.');
        const cu = await probeGet('web/currentuser?$select=IsSiteAdmin');
        const sca = cu.ok && cu.d.IsSiteAdmin === true;
        finding(1, 'manage_permissions_bit', (has(0x2000000) || sca) ? 'PASS' : 'BLOCKED',
          (has(0x2000000) || sca) ? 'Operator holds ManagePermissions (or is a site collection admin).' : 'Operator LACKS ManagePermissions, so ACL/group work cannot run.');
        finding(1, 'noscript', 'INFO',
          has(0x40000) ? 'Custom scripting allowed (AddAndCustomizePages present).' : 'NoScript is ON (AddAndCustomizePages stripped); not required by this pack, but note it.');
      } else {
        // One finding per key: the verdict loop skips a key it has no finding
        // for, so naming one of them let the rest pass unchecked.
        const why = perms.ok
          ? 'the site answered without EffectiveBasePermissions'
          : `HTTP ${perms.status || perms.error}`;
        for (const key of ['manage_lists_bit', 'manage_permissions_bit', 'noscript']) {
          finding(1, key, 'NOT-ASSESSABLE', `Could not read effective permissions (${why}); no check was made for this permission.`);
        }
      }
    }

    // Creatable list templates vs the base templates this pack declares.
    {
      const lt = await probeGet('web/listtemplates?$select=Name,ListTemplateTypeKind,Hidden');
      const available = new Set();
      if (lt.ok && lt.d && Array.isArray(lt.d.results)) {
        for (const t of lt.d.results) available.add(Number(t.ListTemplateTypeKind));
      }
      for (const id of TARGETS.base_templates) {
        // 100 (generic list) and 101 (document library) are universal in SPO;
        // report PASS when present, WARN (not BLOCKED) when the enumeration
        // simply did not list them, since creation may still succeed.
        const key = `list_template_${id}`;
        if (available.has(id)) finding(2, key, 'PASS', `Base template ${id} is creatable.`);
        else if (lt.ok) finding(2, key, 'WARN', `Base template ${id} not listed by web/listtemplates (creation may still work).`);
        else finding(2, key, 'WARN', `Could not enumerate list templates (HTTP ${lt.status || lt.error}).`);
      }
    }

    // Regional settings & languages: locale drives date rendering, and the
    // time zone is the one every date and time is stored and shown in: a
    // date-only value is site-local midnight, and a view window on `today`
    // is read against the site's day. A site left in a zone other than its
    // users' shifts every time they see. This reads the zone and compares it
    // with the browser this is pasted into. The validation clock is a
    // separate matter: MEASURED 2026-09-02, TODAY() and NOW() in a
    // validation formula ran 16 to 20 hours behind an AUS Eastern site
    // whatever this setting said, which is why the build compares date rules
    // with the save instant instead (analysis/save_rules.py).
    {
      const rs = await probeGet('web/regionalsettings?$select=LocaleId');
      if (rs.ok) finding(1, 'regional_settings', 'INFO', `Site LocaleId ${reported(rs.d.LocaleId)}.`);
      const tz = await probeGet('web/regionalsettings/timezone');
      const info = (tz.ok && tz.d && tz.d.Information) || null;
      if (!info) {
        finding(1, 'time_zone', 'NOT-ASSESSABLE',
          "web/regionalsettings/timezone did not report a zone, so which zone this site stores and shows dates in, and reads its 'today' view windows against, is unknown.");
      } else {
        // Windows convention: local + Bias = UTC, so local = UTC - Bias.
        // SharePoint reports both biases without saying which is in force,
        // so both site-local offsets are candidates and either may match.
        const offsets = [...new Set([
          -(info.Bias + (info.StandardBias || 0)),
          -(info.Bias + (info.DaylightBias || 0)),
        ])];
        const browser = -new Date().getTimezoneOffset();
        const spell = (m) => `${m >= 0 ? '+' : ''}${m} min`;
        const zone = `Site time zone "${tz.d.Description || '(no description)'}" (UTC ${offsets.map(spell).join(' / ')}); this browser is UTC ${spell(browser)}.`;
        if (offsets.includes(browser)) {
          finding(1, 'time_zone', 'INFO', `${zone} They agree, so dates and times on this site read the same day this browser does.`);
        } else {
          finding(1, 'time_zone', 'WARN',
            `${zone} They differ: every date and time on this site is stored and shown in the site's zone, and this pack's 'today' view windows are read against the site's day, so a user in this browser's zone sees every time shifted by the difference. Set Site settings > Regional settings > Time zone to the users' zone before deploying, or acknowledge this.`);
        }
      }
      const ml = await probeGet('web?$select=IsMultilingual,SupportedUILanguageIds');
      if (ml.ok) {
        // `${[]}` stringifies to nothing, so an unreported list read as a blank.
        const uiLanguages = (ml.d.SupportedUILanguageIds && ml.d.SupportedUILanguageIds.results) || [];
        finding(1, 'languages', 'INFO',
          `Multilingual ${reported(ml.d.IsMultilingual)}; UI languages ${uiLanguages.length ? uiLanguages.join(', ') : '(none reported)'}.`);
      }
    }

    // Group connection, storage, hub, recycle bin.
    {
      const props = await probeGet('web/allproperties?$select=GroupId');
      if (props.ok && props.d.GroupId && !/^0+(-0+)*$/.test(String(props.d.GroupId).replace(/[{}]/g, ''))) {
        finding(1, 'group_connected', 'INFO', 'Site is Microsoft 365 group-connected.');
      }
      const usage = await probeGet('site/usage');
      if (usage.ok) {
        // `|| 0` reported an unanswered quota as an empty site.
        const measured = usage.d.Storage != null && usage.d.StoragePercentageUsed != null;
        finding(1, 'storage', 'INFO', measured
          ? `Storage used ${Math.round(usage.d.Storage / 1048576)} MB (${Math.round(usage.d.StoragePercentageUsed * 100)}% of quota).`
          : 'site/usage did not report storage figures.');
      }
      const hub = await probeGet('site?$select=IsHubSite,HubSiteId');
      if (hub.ok) finding(1, 'hub', 'INFO', `Hub site ${reported(hub.d.IsHubSite)}; hub id ${reported(hub.d.HubSiteId)}.`);
    }

    // Retention labels available to the site (the UI's own picker call).
    {
      const u = encodeURIComponent(`${ORIGIN}${WEB}`);
      const tags = await probeGet(`SP.CompliancePolicy.SPPolicyStoreProxy.GetAvailableTagsForSite(siteUrl=@u)?@u='${u}'`);
      if (tags.ok) {
        // A payload carrying no `results` is an unanswered question, not an
        // answer of none.
        const rows = tags.d && tags.d.results;
        if (!Array.isArray(rows)) {
          finding(1, 'retention_labels', 'INFO', 'Retention labels not reported by this site.');
        } else {
          const names = rows.map(t => t.TagName).filter(Boolean);
          finding(1, 'retention_labels', 'INFO', names.length ? `Available retention labels: ${names.join(', ')}.` : 'No retention labels available to this site.');
        }
      } else {
        finding(1, 'retention_labels', 'INFO', `Retention-label surface not available (HTTP ${tags.status || tags.error}).`);
      }
    }

    // App catalog + SPFx footprint + search availability.
    {
      const cat = await probeGet('SP_TenantSettings_Current');
      if (cat.ok) {
        // A payload without the property never said there was no catalog.
        const carried = cat.d != null && typeof cat.d === 'object' && 'CorporateCatalogUrl' in cat.d;
        finding(1, 'app_catalog', 'INFO', !carried
          ? 'Tenant app catalog not reported by this site.'
          : (cat.d.CorporateCatalogUrl ? `Tenant app catalog at ${cat.d.CorporateCatalogUrl}.` : 'No tenant app catalog configured.'));
      }
      const uca = await probeGet('web/UserCustomActions?$select=Name,Location,ClientSideComponentId');
      if (uca.ok && uca.d && Array.isArray(uca.d.results)) finding(1, 'custom_actions', 'INFO', `${uca.d.results.length} web custom action(s) / SPFx extension(s) registered.`);
      const search = await probeGet("search/query?querytext='test'&rowlimit=1");
      finding(1, 'search', 'INFO', search.ok ? 'Search service responds.' : `Search probe returned HTTP ${search.status || search.error}.`);
    }

    // ===================================================================
    // Tier 2: pack-driven attempt-probes
    // ===================================================================
    log('INFO', 'Tier 2: pack-driven attempt-probes.');

    // The provenance marker on an EXISTING declared list. Reported, never
    // repaired: this script writes nothing, and that is its whole contract.
    //
    // WHY IT IS HERE AND NOT ONLY IN THE DEPLOY. A missing marker means the
    // list may be foreign. Ordinary deploy must not stamp it, because doing so
    // manufactures the ownership evidence rollback later trusts. Assessment
    // therefore predicts the same fail-closed decision before any write.
    //
    // SUBSTRING, not equality. The deploy compares the whole Description
    // because it owns the note as well; this check owns only discoverability,
    // and a list whose note was reworded but whose marker survives is still
    // found by every report. Firing on that would be noise, and noise gets
    // ignored.
    //
    // The expected text arrives in TARGETS from `analysis.list_description`
    // and is never re-spelled here (see assess_targets' docstring).
    //
    // A Map, because an object literal drops a `__proto__` key and this check
    // then returned silently on a list whose marker was missing.
    const LIST_MARKERS = new Map(TARGETS.list_markers);
    const markerFinding = (title, description, descriptionReported) => {
      const key = markerKey(title);
      const expected = LIST_MARKERS.get(title);
      if (!LIST_MARKERS.has(title)
          || typeof expected !== 'string'
          || expected.length === 0) {
        finding(2, key, 'BLOCKED',
          `'${title}' has no valid generated ownership marker. Rebuild the artifacts; `
          + 'assessment and deploy cannot safely classify the existing list.');
        return;
      }
      // A missing property means the probe did not answer the ownership
      // question. An explicitly reported null or empty value did answer: it
      // carries no marker and therefore blocks ordinary deploy.
      if (!descriptionReported) {
        finding(2, key, 'NOT-ASSESSABLE',
          `'${title}' exists, but its Description was not reported, so ownership `
          + 'could not be assessed. Deploy will make a fresh preflight read.');
        return;
      }
      const held = typeof description === 'string' ? description : '';
      if (held.includes(expected)) {
        finding(2, key, 'PASS', `'${title}' carries its provenance marker.`);
      } else {
        finding(2, key, 'BLOCKED',
          `'${title}' exists but its Description does not carry this declaration's exact `
          + `provenance marker "${expected}". Restore that marker only if this tool created `
          + `the list; otherwise rename the declaration. Deploy will not adopt or stamp it.`);
      }
    };

    // How full an EXISTING declared list already is, against the two list-size
    // bands this pack reports on. A PROXIMITY SIGNAL and never a gate:
    // ItemCount comes from a timer-job cache, and on a library it counts files
    // and folders, so it says roughly how big a list is rather than exactly
    // how many rows it holds. rollback.js.j2 records the same caveat where it
    // refuses to treat the figure as an atomic gate.
    //
    // NEVER BLOCKED, at either band. Microsoft's troubleshooting page calls
    // the larger number the limit for adding or removing an indexed column,
    // and a Microsoft Q&A answer says the index is created in the background
    // over that size instead. One source says refusal and the other says
    // queue, so a BLOCKED verdict here would be a rule stronger than the
    // evidence supports. What would license BLOCKED: a probe that creates an
    // index on a list over the ceiling and reads the refusal back. The two
    // sources are cited in full beside `limits.INDEX_CHANGE_CEILING`.
    const LIST_VIEW_THRESHOLD = Number(TARGETS.list_view_threshold);
    const INDEX_CHANGE_CEILING = Number(TARGETS.index_change_ceiling);
    // Four fifths of the threshold: close enough that ordinary growth crosses
    // it before the next deploy, and still early enough to index for it.
    const ITEM_COUNT_WARN_AT = Math.floor(LIST_VIEW_THRESHOLD * 0.8);
    // Grouped for reading. `toLocaleString` would answer differently per
    // browser locale, and these numbers are quoted back in operator findings.
    const grouped = (n) => String(n).replace(/\B(?=(\d{3})+$)/g, ',');
    const CACHED = 'ItemCount is a cached figure, so read it as a size band rather than an exact total.';
    const itemCountFinding = (title, count, countReported) => {
      const key = sizeKey(title);
      // A property the site did not return answered nothing, which is neither
      // a pass nor a failure. Same separation as the marker check above.
      //
      // `count == null` is not redundant beside the finite test: `Number(null)`
      // is 0, so a key present with a null value would otherwise report the
      // list as holding nothing and pass it as comfortably small. That is the
      // `reported()` convention at the top of this file, which reads `v == null`
      // as "not reported" for exactly this reason.
      if (!countReported || count == null || !Number.isFinite(Number(count))) {
        finding(2, key, 'NOT-ASSESSABLE',
          `'${title}' exists, but its ItemCount was not reported, so its size against the `
          + 'list view threshold could not be assessed.');
        return;
      }
      const held = Number(count);
      const size = `'${title}' currently reports ${grouped(held)} item(s)`;
      if (held >= INDEX_CHANGE_CEILING) {
        finding(2, key, 'WARN',
          `${size}, at or over the ${grouped(INDEX_CHANGE_CEILING)}-item mark Microsoft `
          + 'documents for adding or removing an indexed column, and far past the '
          + `${grouped(LIST_VIEW_THRESHOLD)}-item list view threshold. Views filtering or `
          + 'sorting on an unindexed column fail against it, and index work this deploy '
          + `performs may be refused or queued. ${CACHED}`);
      } else if (held >= LIST_VIEW_THRESHOLD) {
        finding(2, key, 'WARN',
          `${size}, at or over the ${grouped(LIST_VIEW_THRESHOLD)}-item list view threshold. `
          + 'Views filtering, sorting or grouping on an unindexed column fail against it. '
          + `Index the columns the declared views read before deploying. ${CACHED}`);
      } else if (held >= ITEM_COUNT_WARN_AT) {
        finding(2, key, 'WARN',
          `${size}, inside the ${grouped(ITEM_COUNT_WARN_AT)} to `
          + `${grouped(LIST_VIEW_THRESHOLD)} band below the list view threshold. Index the `
          + `columns the declared views filter and sort on before it crosses. ${CACHED}`);
      } else {
        finding(2, key, 'INFO',
          `${size}, under the ${grouped(LIST_VIEW_THRESHOLD)}-item list view threshold.`);
      }
    };

    // Collision probe per declared list. Description and ItemCount ride along
    // on a request already being made, so the marker check above and the size
    // check here cost no probe of their own.
    // Absence is read from the shared title enumeration, never a getbytitle
    // 404, so a first deploy does not paint the console red.
    const knownTitles = await assessListTitleSet();

    // Every tier-2 read below goes through here, so this script costs one
    // request per LOOP rather than one per declared list and per declared
    // folder. Batched only when the enumeration answered: BatchReader refuses
    // a whole envelope on any non-2xx part, and a first deploy is nothing but
    // absent lists, so one 404 would take every other read down with it. With
    // the enumeration refused nothing is known to exist, so the reads go out
    // one at a time as they always did and a 404 still reads as absence.
    //
    // `batchedReadsOff` is set once a batched read has found the digest
    // refused, so the rest of the run stops asking for one the site has
    // already said no to.
    let batchedReadsOff = false;
    const readMany = async (paths) => {
      if (knownTitles && !batchedReadsOff) {
        const batched = await probeMany(paths);
        if (batched) return batched;
        batchedReadsOff = true;
        log('INFO', 'The site refused a request digest, so reads are not batched; this assessment makes one request per declared list.');
      }
      const rows = [];
      for (const path of paths) rows.push(await probeGet(path));
      return rows;
    };

    // The set the loop below actually probes: what the enumeration named, or
    // every declared title when it was refused. The two conditions are exact
    // complements of the `continue` inside the loop, so every title it reads
    // was queued here.
    const listShapePath = (title) => `web/lists/getbytitle('${odataName(title)}')?$select=Title,BaseTemplate,Description,ItemCount`;
    const probedTitles = TARGETS.list_titles.filter(
      (title) => !knownTitles || knownTitles.has(String(title).toLowerCase()));
    const listShapes = new Map();
    {
      const rows = await readMany(probedTitles.map(listShapePath));
      for (let at = 0; at < probedTitles.length; at += 1) listShapes.set(probedTitles[at], rows[at]);
    }
    for (const title of TARGETS.list_titles) {
      const key = collisionKey(title);
      if (knownTitles && !knownTitles.has(String(title).toLowerCase())) {
        finding(2, key, 'PASS', `'${title}' absent, a clean provision target.`);
        continue;
      }
      // Fails closed into the unread arm below rather than throwing, if the
      // queue above and this loop ever disagree about what was probed.
      const list = listShapes.get(title) || { ok: false, error: 'the batched read did not queue this list' };
      if (!list.ok && list.status === 404) {
        // Enumeration refused (knownTitles null): a 404 still means absent,
        // not "could not probe".
        finding(2, key, 'PASS', `'${title}' absent, a clean provision target.`);
      } else if (list.ok) {
        finding(2, key, 'INFO', `'${title}' already exists (BaseTemplate ${reported(list.d.BaseTemplate)}); the ownership check below decides whether deploy may reconcile it.`);
        markerFinding(
          title,
          list.d.Description,
          Object.prototype.hasOwnProperty.call(list.d, 'Description'),
        );
        itemCountFinding(
          title,
          list.d.ItemCount,
          Object.prototype.hasOwnProperty.call(list.d, 'ItemCount'),
        );
      } else {
        // NOT-ASSESSABLE, and for all three keys this one read feeds. A list
        // that did not answer is not a list reported present or absent, and
        // the verdict loop skips a requirement key nothing filed a finding
        // for, so naming the collision alone let ownership and size pass
        // unspoken. A refused batch reports every list in it this way.
        const why = list.status ? `HTTP ${list.status}` : list.error;
        finding(2, key, 'NOT-ASSESSABLE',
          `Could not probe '${title}' (${why}), so whether it already exists was not established.`);
        finding(2, markerKey(title), 'NOT-ASSESSABLE',
          `'${title}' could not be read (${why}), so its ownership marker was not checked.`);
        finding(2, sizeKey(title), 'NOT-ASSESSABLE',
          `'${title}' could not be read (${why}), so its size against the list view threshold was not assessed.`);
      }
    }

    for (const [title, internalName] of (TARGETS.library_roots || [])) {
      const key = `library_root:${title}`;
      const shape = listShapes.get(title);
      if ((knownTitles && !knownTitles.has(title.toLowerCase())) ||
          (shape && !shape.ok && shape.status === 404)) {
        finding(2, key, 'PASS', `'${title}' absent; its declared root will be created.`);
        continue;
      }
      const root = await probeGet(`web/lists/getbytitle('${odataName(title)}')/RootFolder?$select=ServerRelativeUrl`);
      const actual = root.ok && root.d.ServerRelativeUrl;
      const expected = decodeURIComponent(WEB).replace(/\/$/, '') + '/' + internalName;
      if (!shape || !shape.ok || typeof actual !== 'string' || !actual.startsWith('/')) {
        finding(2, key, 'NOT-ASSESSABLE', `Could not verify the immutable root of '${title}'.`);
      } else if (shape.d.BaseTemplate !== 101 || actual !== expected) {
        finding(2, key, 'BLOCKED', `LIBRARY_INTERNAL_NAME_MISMATCH: '${title}' requires '${expected}', read ${JSON.stringify(actual)} (template ${shape.d.BaseTemplate}).`);
      } else {
        finding(2, key, 'PASS', `'${title}' has the declared immutable root '${expected}'.`);
      }
    }

    // Column display titles, compared against what the mapping declares.
    //
    // Between deploys nothing else can see this. Renaming a column needs
    // Manage Lists, which Full Control, Design and Edit all carry, and the
    // deploy silently puts the declared name back at the next run, so a
    // rename lives and dies without anybody being told. That matters most
    // for the built-in Title, which no other surface reports: the maintenance
    // sidecar filters on `isCustom` and Title reads FromBaseType:true.
    //
    // INFO rather than WARN, deliberately. The deploy repairs this, so it is
    // a report and not a gate, and a warning that always resolves itself is
    // how a warning stops meaning anything. Silent when everything matches.
    // MEASURED 2026-09-08, library-index-threshold-probe.js: FileLeafRef filters fail past 5,000 items.
    // https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-folders-and-files-with-rest
    const libraryPathLiteral = (path) => String(path).replace(/'/g, "''");
    async function pathExists(kind, path) {
      const read = kind === 'Folder'
        ? await probeGet(`web/GetFolderByServerRelativeUrl('${libraryPathLiteral(path)}')?$select=Exists,ServerRelativeUrl`)
        : await probeGet(`web/GetFileByServerRelativeUrl('${libraryPathLiteral(path)}')?$select=Exists,ServerRelativeUrl`);
      if (!read.ok && read.status === 404) return { ok: true, exists: false };
      if (!read.ok) return read;
      if (Array.isArray(read.d) || typeof read.d.Exists !== 'boolean'
        || (read.d.Exists && read.d.ServerRelativeUrl !== path)) {
        return { ok: false, error: `malformed ${kind} path response` };
      }
      return { ok: true, exists: read.d.Exists };
    }
    const folderLibraries = (TARGETS.library_folders || []).filter(
      ([title]) => !knownTitles || knownTitles.has(String(title).toLowerCase()));
    const folderRoots = new Map();
    {
      const roots = await readMany(folderLibraries.map(([title]) =>
        `web/lists/getbytitle('${odataName(title)}')/RootFolder?$select=ServerRelativeUrl`));
      for (let at = 0; at < folderLibraries.length; at += 1) folderRoots.set(folderLibraries[at][0], roots[at]);
    }
    for (const [title, folders] of (TARGETS.library_folders || [])) {
      const key = `folder_shape:${title}`;
      if (knownTitles && !knownTitles.has(String(title).toLowerCase())) {
        finding(2, key, 'PASS', `'${title}' absent; its ${folders.length} declared folder(s) will be created.`);
        continue;
      }
      const files = [];
      let unreadable = null;
      const root = folderRoots.get(title);
      const rootUrl = root && root.ok && root.d.ServerRelativeUrl;
      if (typeof rootUrl !== 'string' || !rootUrl.startsWith('/') || rootUrl.endsWith('/')) {
        unreadable = 'missing or malformed library root URL';
      }
      for (const name of folders) {
        if (unreadable !== null) break;
        const path = `${rootUrl}/${name}`;
        const folder = await pathExists('Folder', path);
        if (!folder.ok) { unreadable = folder.status ? `HTTP ${folder.status}` : folder.error; break; }
        if (folder.exists) {
          const item = await probeGet(`web/GetFolderByServerRelativeUrl('${libraryPathLiteral(path)}')/ListItemAllFields?$select=FileSystemObjectType,FileRef`);
          if (!item.ok || Array.isArray(item.d) || item.d.FileSystemObjectType !== 1 || item.d.FileRef !== path) {
            unreadable = 'folder item did not read back as a folder at the declared path'; break;
          }
        } else {
          const file = await pathExists('File', path);
          if (!file.ok) { unreadable = file.status ? `HTTP ${file.status}` : file.error; break; }
          if (file.exists) files.push(name);
        }
      }
      if (unreadable !== null) {
        // NOT-ASSESSABLE rather than WARN. The question is whether a file
        // stands where a folder is declared, and a read that did not answer
        // did not answer it. Both levels degrade the verdict; this one says
        // which way.
        finding(2, key, 'NOT-ASSESSABLE', `Could not read '${title}' for its declared folders (${unreadable}); whether a file stands where a folder is declared was not established.`);
      } else if (files.length) {
        finding(2, key, 'BLOCKED', `'${title}' holds a FILE where a folder is declared: ${files.join(', ')}. Rename or move it; the folder phase refuses to create beside it.`);
      } else {
        finding(2, key, 'PASS', `'${title}': every declared folder is absent or already a folder.`);
      }
    }

    // One request for the column enumerations of every declared list, where
    // this was one per list. Two checks read it, so the titles are the union
    // of the lists each one asks about and the select carries both their
    // properties. An array, not a Set or an object, so a list titled
    // `__proto__` keeps its own entry.
    const columnListTitles = [];
    for (const [title] of [
      ...(TARGETS.list_display_titles || []), ...(TARGETS.list_unique_columns || []),
    ]) {
      if (knownTitles && !knownTitles.has(String(title).toLowerCase())) continue;
      if (!columnListTitles.includes(title)) columnListTitles.push(title);
    }
    // Spelled once, because the request and the truncation test below are
    // wrong the moment they disagree about the page size.
    const COLUMN_PAGE_SIZE = 500;
    const columnShapes = new Map();
    {
      const rows = await readMany(columnListTitles.map((title) =>
        `web/lists/getbytitle('${odataName(title)}')/fields?$select=InternalName,Title,EnforceUniqueValues&$top=${COLUMN_PAGE_SIZE}`));
      for (let at = 0; at < columnListTitles.length; at += 1) columnShapes.set(columnListTitles[at], rows[at]);
    }
    const columnShapeOf = (title) => {
      const live = columnShapes.get(title)
        || { ok: false, error: 'the batched read did not queue this list' };
      // A malformed collection cannot establish that declared columns are absent.
      if (live.ok && (malformedNextPage(live.d) || !Array.isArray(live.d.results)
        || live.d.results.some((row) => !row || typeof row.InternalName !== 'string'))) {
        return { ok: false, error: 'missing or malformed column collection' };
      }
      return live;
    };
    // Whether this page may have left columns unread, which is what decides
    // if a column missing from it is a column the list does not hold.
    //
    // A FULL page is the tell, not a missing `__next`: `$top` is
    // client-driven paging, and Learn's "PageSize, Top and MaxTop" says of it
    // that "there is no nextLink that is returned"
    // (https://learn.microsoft.com/odata/webapi/pagesize-top-maxtop), so an
    // absent `__next` under a `$top` says nothing at all. The same page
    // documents the other direction, a server paging BELOW the asked-for
    // size, which does return one; both are read here and neither is
    // followed. A batch part is one request, and asking for the declared
    // fields directly instead would put a 404 per unprovisioned column into
    // an envelope BatchReader refuses whole, which is a first deploy.
    const columnsTruncated = (live) => {
      const next = live.d && live.d.__next;
      return live.d.results.length >= COLUMN_PAGE_SIZE
        || (typeof next === 'string' && next !== '');
    };
    for (const [title, columns] of (TARGETS.list_display_titles || [])) {
      if (knownTitles && !knownTitles.has(String(title).toLowerCase())) continue;
      const key = `display_titles:${title}`;
      const live = columnShapeOf(title);
      if (!live.ok) {
        // Absent is not drifted. The collision loop above already reported
        // whether this list exists, so staying quiet here avoids two
        // findings for one fact.
        if (live.status !== 404) {
          finding(2, key, 'INFO', `Could not read the columns of '${title}' (HTTP ${live.status || live.error}); declared display titles were not compared.`);
        }
        continue;
      }
      const byInternal = new Map();
      for (const f of live.d.results) {
        byInternal.set(String(f.InternalName), f.Title);
      }
      const drifted = [];
      const unseen = [];
      const truncated = columnsTruncated(live);
      for (const [internal, declaredTitle] of columns) {
        if (!byInternal.has(internal)) {
          // Not provisioned yet, unless the page it is missing from may have
          // ended before the whole list did.
          if (truncated) unseen.push(internal);
          continue;
        }
        const actual = byInternal.get(internal);
        if (actual !== declaredTitle) {
          drifted.push(`${internal} displays as ${JSON.stringify(actual)}, declared ${JSON.stringify(declaredTitle)}`);
        }
      }
      if (drifted.length > 0) {
        finding(2, key, 'INFO', `'${title}': ${drifted.length} column display title(s) differ from the mapping and the next deploy will put them back -- ${drifted.join('; ')}.`);
      }
      if (unseen.length > 0) {
        // Said rather than passed over in silence: this check reports drift
        // it saw, and a column it could not see is not a column that matches.
        finding(2, key, 'INFO', `'${title}': ${unseen.length} declared column(s) were not in a column enumeration that came back at its ${COLUMN_PAGE_SIZE}-row page size -- ${unseen.join(', ')}. Whether they display under the declared titles was not compared.`);
      }
    }

    // Columns declared unique that the site holds unconstrained. #550 made a
    // declared `unique` actually deploy its constraint, so a list provisioned
    // before that fix gains it over data that never carried it.
    //
    // Deliberately the same comparison deploy's preflight makes, in the same
    // declaration order. Preflight says it before any write but does not stop
    // the run, so by the time the field phase asks, the rename, security,
    // logging and list phases have written; this script is read before the
    // paste. Two places on purpose, like the preflight and the field phase.
    for (const [title, columns] of (TARGETS.list_unique_columns || [])) {
      const key = `pending_unique:${title}`;
      const live = columnShapeOf(title);
      // Absent is not unconstrained. A 404 is the same fact when the title
      // enumeration was refused and nothing could be filtered on it.
      const absent = (knownTitles && !knownTitles.has(String(title).toLowerCase()))
        || (!live.ok && live.status === 404);
      if (absent) {
        const rename = (TARGETS.list_renames || []).find(([current]) => current === title);
        const possiblePrevious = rename ? rename[1].filter(([oldTitle]) =>
          !knownTitles || knownTitles.has(String(oldTitle).toLowerCase())) : [];
        // An absent current title can still adopt existing data through a rename.
        if (possiblePrevious.length) {
          finding(2, key, 'NOT-ASSESSABLE', `'${title}' is absent under its current title, but may adopt a previous list (${possiblePrevious.map(([oldTitle]) => oldTitle).join(', ')}). Its declared unique columns were not checked on those previous titles; deploy preflight checks the resolved rename target before writing.`);
          continue;
        }
        finding(2, key, 'PASS', `'${title}' absent; its ${columns.length} declared unique column(s) are provisioned carrying the constraint, not given one over existing data.`);
        continue;
      }
      if (!live.ok) {
        // NOT-ASSESSABLE rather than PASS: a read that did not answer did not
        // say these columns are constrained.
        finding(2, key, 'NOT-ASSESSABLE', `Could not read the columns of '${title}' (${live.status ? `HTTP ${live.status}` : live.error}); whether its declared unique column(s) already carry EnforceUniqueValues was not established.`);
        continue;
      }
      const byInternal = new Map();
      for (const f of live.d.results) {
        byInternal.set(String(f.InternalName), f);
      }
      const pending = [];
      const unread = [];
      const unseen = [];
      const truncated = columnsTruncated(live);
      for (const internal of columns) {
        const row = byInternal.get(internal);
        if (row === undefined) {
          // Not provisioned yet, unless the page it is missing from may have
          // ended before the whole list did, which establishes no absence.
          if (truncated) unseen.push(internal);
          continue;
        }
        // A property the site did not report is not a false one.
        if (typeof row.EnforceUniqueValues !== 'boolean') unread.push(internal);
        else if (!row.EnforceUniqueValues) pending.push(internal);
      }
      if (unread.length > 0 || unseen.length > 0) {
        const why = [];
        if (unread.length > 0) why.push(`the site reported no EnforceUniqueValues for ${unread.join(', ')}`);
        if (unseen.length > 0) why.push(`${unseen.join(', ')} did not appear in a column enumeration that came back at its ${COLUMN_PAGE_SIZE}-row page size, and missing from a page that may be truncated is not missing from the list`);
        const named = [...unread, ...unseen];
        const alsoPending = pending.length > 0
          ? ` ${pending.length} other(s) did read back false: ${pending.join(', ')}.`
          : '';
        finding(2, key, 'NOT-ASSESSABLE', `'${title}': ${why.join('; ')}. Whether the next deploy asks for a constraint on ${named.length > 1 ? 'those columns' : 'that column'} was not established.${alsoPending}`);
      } else if (pending.length > 0) {
        // NOT ESTABLISHED: what SharePoint does with this transition over
        // existing duplicates. `unique-transition-probe.js` asks it and has
        // not been run, so this says only what was measured here.
        finding(2, key, 'WARN', `'${title}': ${pending.length} column(s) declared unique read back EnforceUniqueValues false -- ${pending.join(', ')}. The next deploy's field phase will ask SharePoint to set it on each. This assessment did not count duplicate values in them, so it cannot say whether the request will be accepted; a refused write is reported with the reason SharePoint gave and stops the run.`);
      } else {
        finding(2, key, 'PASS', `'${title}': every declared unique column it already holds carries EnforceUniqueValues.`);
      }
    }

    // The rename decision, predicted. Exactly one previous title carrying
    // its own marker while the current title is absent is the only shape
    // deploy renames; everything else blocks, because a guess here is a
    // list adopted or created over somebody else's.
    // One request for every previous title of every renamed list, where this
    // was one per previous title. Filtered first so the queue and the loop
    // walk the same entries in the same order.
    const renameTargets = (TARGETS.list_renames || []).map(([title, previousTitles]) => [
      title,
      previousTitles.filter(([oldTitle]) => !knownTitles || knownTitles.has(String(oldTitle).toLowerCase())),
    ]);
    const renameShapes = new Map();
    {
      const queue = [];
      for (const [, previousTitles] of renameTargets) {
        for (const [oldTitle] of previousTitles) {
          queue.push(`web/lists/getbytitle('${odataName(oldTitle)}')?$select=Title,Description`);
        }
      }
      const rows = await readMany(queue);
      let at = 0;
      for (const [title, previousTitles] of renameTargets) {
        renameShapes.set(title, rows.slice(at, at + previousTitles.length));
        at += previousTitles.length;
      }
    }
    for (const [title, previousTitles] of renameTargets) {
      const key = `rename:${title}`;
      const present = [];
      let unprobed = null;
      const shapes = renameShapes.get(title) || [];
      for (let at = 0; at < previousTitles.length; at += 1) {
        const [oldTitle, oldMarker] = previousTitles[at];
        const old = shapes[at] || { ok: false, error: 'the batched read did not queue this title' };
        if (!old.ok && old.status === 404) continue;
        if (!old.ok) { unprobed = `${old.status ? `HTTP ${old.status}` : old.error} on '${oldTitle}'`; continue; }
        const held = typeof old.d.Description === 'string' ? old.d.Description : '';
        present.push({ title: oldTitle, marker: oldMarker, carries: held.includes(oldMarker) });
      }
      const currentExists = knownTitles
        ? knownTitles.has(String(title).toLowerCase())
        : (await probeGet(`web/lists/getbytitle('${odataName(title)}')?$select=Title`)).ok;
      const named = present.map((p) => `'${p.title}'`).join(', ');
      if (unprobed) {
        finding(2, key, 'NOT-ASSESSABLE', `A previous title of '${title}' could not be probed (${unprobed}); deploy will make a fresh preflight read.`);
      } else if (present.length === 0) {
        finding(2, key, 'PASS', `No previous title of '${title}' exists; nothing to rename.`);
      } else if (currentExists) {
        finding(2, key, 'BLOCKED', `'${title}' exists and so does its previous title ${named}; deploy cannot tell a rename from a collision. Remove or retitle one of them by hand.`);
      } else if (present.length > 1) {
        finding(2, key, 'BLOCKED', `More than one previous title of '${title}' exists (${named}); deploy cannot choose which to rename.`);
      } else if (!present[0].carries) {
        finding(2, key, 'BLOCKED', `'${present[0].title}' exists but does not carry the exact provenance marker for its previous name "${present[0].marker}". Deploy will not adopt or rename it; restore that marker only if this tool created the list.`);
      } else {
        finding(2, key, 'INFO', `'${present[0].title}' carries the marker for its previous name and will be renamed '${title}' in place, keeping its items, views, lookups and permissions.`);
      }
    }

    // Level and group renames, predicted from one enumeration each: the
    // rules are the list rules, and a guess here is an object adopted or
    // created over somebody else's.
    const renameFinding = async (kind, prefixKey, targetsList, enumerate, nameOf) => {
      if (!targetsList.length) return;
      const rows = await enumerate();
      if (rows === null) {
        for (const [name] of targetsList) finding(2, `${prefixKey}:${name}`, 'NOT-ASSESSABLE', `${kind}s could not be enumerated; deploy will make a fresh read.`);
        return;
      }
      const byName = (name) => rows.filter((row) => String(nameOf(row)).toLowerCase() === String(name).toLowerCase());
      for (const [name, previousNames] of targetsList) {
        const key = `${prefixKey}:${name}`;
        const present = [];
        for (const [oldName, oldMarker] of previousNames) {
          for (const row of byName(oldName)) {
            const held = typeof row.Description === 'string' ? row.Description : '';
            present.push({ name: oldName, marker: oldMarker, carries: held.includes(oldMarker) });
          }
        }
        const named = present.map((p) => `'${p.name}'`).join(', ');
        if (present.length === 0) {
          finding(2, key, 'PASS', `No previous name of ${kind} '${name}' exists; nothing to rename.`);
        } else if (byName(name).length > 0) {
          finding(2, key, 'BLOCKED', `${kind} '${name}' exists and so does its previous name ${named}; deploy cannot tell a rename from a collision. Remove or retitle one of them by hand.`);
        } else if (present.length > 1) {
          finding(2, key, 'BLOCKED', `More than one previous name of ${kind} '${name}' exists (${named}); deploy cannot choose which to rename.`);
        } else if (!present[0].carries) {
          finding(2, key, 'BLOCKED', `${kind} '${present[0].name}' exists but does not carry the exact provenance marker for its previous name "${present[0].marker}". Deploy will not adopt or rename it; restore that marker only if this tool created it.`);
        } else {
          finding(2, key, 'INFO', `${kind} '${present[0].name}' carries the marker for its previous name and will be renamed '${name}' in place, keeping its ${kind === 'site group' ? 'members' : 'assignments'}.`);
        }
      }
    };
    await renameFinding('permission level', 'rename_level', TARGETS.level_renames || [], async () => {
      const r = await probeGet('web/roledefinitions?$select=Name,Description&$top=5000');
      return r.ok && !malformedNextPage(r.d) && !r.d.__next && Array.isArray(r.d.results)
        && r.d.results.length < 5000 ? r.d.results : null;
    }, (row) => row.Name);
    await renameFinding('site group', 'rename_group', TARGETS.group_renames || [], async () => {
      const r = await probeGet('web/sitegroups?$select=Title,Description&$top=5000');
      return r.ok && !malformedNextPage(r.d) && !r.d.__next && Array.isArray(r.d.results)
        && r.d.results.length < 5000 ? r.d.results : null;
    }, (row) => row.Title);

    // Property-surface probes against the first EXISTING declared list, else
    // the site's own lists: 200 PASS, non-200 WARN.
    {
      let probeList = null;
      // The enumeration already read above, rather than a second identical
      // request: it answers the same question and this one is per run.
      const surfaceTitles = knownTitles;
      if (surfaceTitles) {
        probeList = TARGETS.list_titles.find((t) => surfaceTitles.has(String(t).toLowerCase())) || null;
      } else {
        for (const title of TARGETS.list_titles) {
          const l = await probeGet(`web/lists/getbytitle('${odataName(title)}')?$select=Title`);
          if (l.ok) { probeList = title; break; }
        }
      }
      const surfaceProbe = async (key, present, suffixFor) => {
        if (!present) return;
        if (!probeList) { finding(2, key, 'INFO', 'No existing declared list to probe; surface will be exercised at deploy time.'); return; }
        const r = await probeGet(suffixFor(probeList));
        finding(2, key, r.ok ? 'PASS' : 'WARN', r.ok ? 'Property surface present.' : `Property surface differs (HTTP ${r.status || r.error}); deploy step may fail.`);
      };
      await surfaceProbe('sealed_surface', TARGETS.declares_seal,
        (t) => `web/lists/getbytitle('${odataName(t)}')/fields?$select=Sealed&$top=1`);
      await surfaceProbe('allow_deletion_surface', TARGETS.declares_prevent_deletion,
        (t) => `web/lists/getbytitle('${odataName(t)}')?$select=AllowDeletion`);
      await surfaceProbe('custom_formatter_surface', TARGETS.declares_column_formatting,
        (t) => `web/lists/getbytitle('${odataName(t)}')/fields?$select=CustomFormatter&$top=1`);
      await surfaceProbe('form_formatter_surface', TARGETS.declares_form_formatting,
        (t) => `web/lists/getbytitle('${odataName(t)}')/contenttypes?$select=ClientFormCustomFormatter&$top=1`);
      // Intelligent-versioning trim: WARN if service-managed auto-trim governs.
      if (TARGETS.declares_versioning && probeList) {
        const vp = await probeGet(`web/lists/getbytitle('${odataName(probeList)}')?$expand=VersionPolicies&$select=VersionPolicies/DefaultTrimMode`);
        // An unreported DefaultTrimMode is not a trim mode of none, and reading
        // it as one passed this requirement having checked nothing.
        if (!vp.ok) {
          finding(2, 'version_trim_mode', 'INFO', 'VersionPolicies surface not present on this tenant.');
        } else if (!vp.d.VersionPolicies || vp.d.VersionPolicies.DefaultTrimMode == null) {
          finding(2, 'version_trim_mode', 'NOT-ASSESSABLE',
            'The list answered without VersionPolicies/DefaultTrimMode, so whether service-managed auto-trim overrides the declared MajorVersionLimit is unknown.');
        } else if (Number(vp.d.VersionPolicies.DefaultTrimMode) === 2) {
          finding(2, 'version_trim_mode', 'WARN', 'Service-managed auto-trim is ON and can override the declared MajorVersionLimit.');
        } else {
          finding(2, 'version_trim_mode', 'PASS', 'No service-managed auto-trim overriding declared version limits.');
        }
      } else if (TARGETS.declares_versioning) {
        finding(2, 'version_trim_mode', 'INFO', 'No existing declared list to read version policy; checked at deploy time.');
      }
    }

    // CSOM ProcessQuery availability (read-only Current-Web-Title query),
    // needed for group owner correction when the pack declares groups.
    if (TARGETS.declares_groups) {
      try {
        const digest = await getDigest();
        const body =
          '<Request xmlns="http://schemas.microsoft.com/sharepoint/clientquery/2009" SchemaVersion="15.0.0.0" LibraryVersion="16.0.0.0" ApplicationName="dbml-sharepoint-assess">'
          + '<Actions><Query Id="1" ObjectPathId="0"><Query SelectAllProperties="false"><Properties><Property Name="Title" ScalarProperty="true" /></Properties></Query></Query></Actions>'
          + '<ObjectPaths><Property Id="0" ParentId="-1" Name="Web" /><StaticProperty Id="-1" TypeId="{3747adcd-a3c3-41b9-bfab-4a64dd2f1e0a}" Name="Current" /></ObjectPaths>'
          + '</Request>';
        const r = await fetchWithRetry(apiUrl('ProcessQuery'), {
          method: 'POST',
          headers: { 'Accept': 'application/json;odata=verbose', 'Content-Type': 'text/xml', 'X-RequestDigest': digest },
          body,
        });
        finding(2, 'process_query', r.ok ? 'PASS' : 'WARN', r.ok ? 'CSOM ProcessQuery responds (group owner correction available).' : `ProcessQuery returned HTTP ${r.status}; owner correction will be degraded.`);
      } catch (err) {
        finding(2, 'process_query', 'WARN', `ProcessQuery probe failed (${err.message}); owner correction will be degraded.`);
      }
    }

    // Applied sensitivity label + Preservation Hold Library signal (governance INFO).
    {
      const sl = await probeGet('site/SensitivityLabelInfo');
      if (sl.ok && sl.d && sl.d.DisplayName) finding(2, 'sensitivity_label', 'INFO', `Site sensitivity label: ${sl.d.DisplayName}.`);
      const phl = await probeGet("web/lists/getbytitle('Preservation Hold Library')?$select=Title");
      if (phl.ok) finding(2, 'preservation_hold', 'INFO', 'Preservation Hold Library present; the site is under a retention policy or hold.');
    }

    // ===================================================================
    // Tier 3: not assessable (printed honesty block)
    // ===================================================================
    log('INFO', 'Tier 3: not assessable from operator site context.');
    for (const item of NOT_ASSESSABLE) finding(3, 'not_assessable', 'NOT-ASSESSABLE', item);

    // ===================================================================
    // Verdict: worst outcome over the pack's requirement keys.
    // ===================================================================
    const byKey = {};
    for (const f of findings) {
      // NOT-ASSESSABLE is kept: dropping it let the loop below read a
      // requirement nobody could check as a pass. Tier 3's shared key
      // `not_assessable` is not a requirement key, so it is never read.
      if (f.level === 'INFO') continue;
      byKey[f.key] = f;
    }
    let blocked = null;
    let warnings = 0;
    let unassessed = null;
    for (const req of REQUIREMENTS) {
      const f = byKey[req.key];
      if (!f) continue;
      if (f.level === 'BLOCKED') { if (!blocked) blocked = req; }
      else if (f.level === 'WARN') warnings += 1;
      // This is neither BLOCKED, since nothing says the requirement is unmet,
      // nor a pass, since something the pack requires went unchecked.
      else if (f.level === 'NOT-ASSESSABLE') { if (!unassessed) unassessed = req; }
    }
    const prefix = (TARGETS.list_titles[0] || '').split('_')[0] + '_';
    // The level comes from the caller: 'DONE' is deploy's terminal signal, so a
    // deploy including this partial must not print it before it provisions.
    if (blocked) {
      verdict = 'BLOCKED';
      log(verdictLevel, `${prefix} pack: BLOCKED (${blocked.key}: ${blocked.description}). Resolve before deploying.`);
    } else if (warnings > 0 || unassessed) {
      verdict = 'DEGRADED';
      const why = warnings > 0 ? `${warnings} warning(s)` : '';
      const unchecked = unassessed
        ? `${why ? ', ' : ''}${unassessed.key} could not be assessed`
        : '';
      log(verdictLevel, `${prefix} pack: DEGRADED (${why}${unchecked}). Deployable; review the findings above.`);
    } else {
      verdict = 'COMPATIBLE';
      log(verdictLevel, `${prefix} pack: COMPATIBLE. No blocking or degrading findings.`);
    }

    return { findings, verdict };
  }

  let summary;
  // The same guard the deploy gate has: a throw is a broken probe, not a
  // verdict, and this script died with a stack trace instead. BLOCKED, because
  // a site nobody could read is not a site to deploy to.
  try {
    summary = await assessSite({
      requirements: REQUIREMENTS, targets: TARGETS, notAssessable: NOT_ASSESSABLE,
      log, web: WEB, origin: window.location.origin, fetchWithRetry, apiUrl,
      odataName, getDigest, getContextWebInformation, verdictLevel: 'DONE',
    });
  } catch (err) {
    log('ERROR', `The assessment could not run (${err.message}); nothing was assessed.`);
    summary = { findings: [], verdict: 'BLOCKED', aborted: 'assessment-failed' };
  }
  console.log(summary);
  return summary;
})();
