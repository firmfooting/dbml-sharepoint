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
  // Set to true and paste again to deploy onto a site the assessment called
  // DEGRADED. Defaults to refusing, like every probe's CONFIRMED flag.
  const ACKNOWLEDGE_DEGRADED = false;
  const RELEASE_TAG = "0.1.0-test";
  const SCHEMA_VERSION = "0.8";
  const ASSESS_REQUIREMENTS = [
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
  const ASSESS_TARGETS = {
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
  "level_renames": [],
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
  "requires_manage_permissions": true,
  "uses_today": true
};
  const ASSESS_NOT_ASSESSABLE = [
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

  const log = (level, msg) => console.log(`[SP-DEPLOY] [${level}] ${msg}`);
  // Baked in at build time from the dbml-sharepoint.env this run read (or
  // that it read none) -- a log() line, not a header comment, because the
  // operator pastes back the console transcript, not the file.
  log('INFO', "No dbml-sharepoint.env file was read.");
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
    listsRenamed: [],
    levelsRenamed: [],
    groupsRenamed: [],
    listsSkipped: [],
    columnsCreated: 0,
    columnsSkipped: 0,
    errors: [],
    // The logging phase's OWN failure list, deliberately not `errors`.
    // `errors` is the abort bus every phase gate reads, and the registers
    // this deploy maintains must never depend on the logs that document
    // them: a change row that would not write must not stop a deploy that
    // otherwise succeeded. Declared here, beside `errors`, so the summary
    // has one shape whether or not the logging phase renders.
    loggingFailures: [],
    releaseTag: RELEASE_TAG,
    schemaVersion: SCHEMA_VERSION,
  };


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
  async function fetchWithRetry(url, opts, attempts = 8) {
    const t0 = Date.now();
    for (let i = 0; ; i++) {
      await passThrottleGate();
      const r = await fetch(url, opts);
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

  // Verbose-OData headers for SP writes; `extra` carries method overrides
  // such as { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }.
  const spHeaders = (digest, extra = {}) => ({
    'Accept': 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
    'X-RequestDigest': digest,
    ...extra,
  });

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

  // Collapses many single writes into one $batch request. The JS equivalent
  // of a context manager, since a script pasted into a console has no
  // `with`: add() accumulates, flush() sends, done() sends what is left.
  class BatchWriter {
    constructor({ getDigest, fetchWithRetry, apiUrl, log, bodyBudgetBytes = BATCH_BODY_BUDGET_BYTES }) {
      this.getDigest = getDigest;
      this.fetchWithRetry = fetchWithRetry;
      this.apiUrl = apiUrl;
      this.log = log;
      this.bodyBudgetBytes = bodyBudgetBytes;
      // The protocol wants an absolute operation URL in each request line and
      // that is the spelling the probe proved. Safe to read off the page:
      // _site_guard.js.j2 has already refused to run unless this origin is
      // the one the script was built for.
      this.origin = window.location.origin;
      this.pending = [];
      this.pendingBytes = BATCH_ENVELOPE_BYTES;
      this.requests = 0;
      this.opsSent = 0;
    }

    // `path` is what apiUrl() takes, so an operation is spelled here exactly
    // as it would be for a single write. Awaitable because a batch that has
    // reached the budget is flushed here rather than at the caller's
    // discretion.
    async add(method, path, body, extraHeaders = {}) {
      const op = {
        method,
        url: `${this.origin}${this.apiUrl(path)}`,
        // null, not '{}': a function invocation such as addroleassignment is
        // a POST with no body as a single write, and a part reproduces it.
        payload: body === undefined ? null : JSON.stringify(body),
        extraHeaders,
      };
      // Measured off the encoder rather than from a table of header sizes, so
      // the estimate cannot drift from what actually goes out. The digest is
      // cached, so asking for it here costs no extra request.
      const cost = utf8Bytes(this._part(op, await this.getDigest(), BATCH_BOUNDARY_SAMPLE));
      // Flush BEFORE adding, so the request that goes out is the one already
      // measured to fit rather than the one that just passed the budget.
      if (this.pending.length && this.pendingBytes + cost > this.bodyBudgetBytes) {
        await this.flush();
      }
      this.pending.push(op);
      this.pendingBytes += cost;
    }

    // One application/http part: a full request line, the same verbose-OData
    // write headers the single write sends, and the JSON body. Sending the
    // single write's own headers is what keeps the body it was handed valid:
    // a field body carries `__metadata`, which only exists in verbose OData,
    // so a part declaring nometadata is refused HTTP 400 for a property that
    // "does not exist on type 'SP.FieldText'" (live finding 2026-09-04).
    _part(op, digest, inner) {
      // A single SharePoint write tunnels MERGE and DELETE through
      // X-HTTP-Method on a POST, but a ChangeSet part carries the verb in its
      // own request line. OData v3 batch processing is explicit that a batch
      // request MUST NOT include an X-HTTP-Method header; Learn's batch
      // example spells a delete `DELETE <url> HTTP/1.1` with If-Match, and
      // PnPjs (pnp/pnpjs packages/sp/batching.ts) reads X-HTTP-Method off the
      // request, uses it as the request-line method and DELETES the header
      // before writing the part. Measured to be required rather than merely
      // documented: a part left carrying the header reaches SharePoint as a
      // POST to the entity, which reads the body keys as method arguments and
      // refuses with "The parameter Description does not exist in method
      // GetById" (live finding 2026-09-04). Translating here is what lets a
      // caller hand add() the same method and headers the single-write helper
      // sends.
      const extra = { ...(op.extraHeaders || {}) };
      const tunnelled = extra['X-HTTP-Method'];
      delete extra['X-HTTP-Method'];
      const headers = Object.entries(spHeaders(digest, extra))
        .map(([name, value]) => `${name}: ${value}\r\n`).join('');
      return `--${inner}\r\n`
        + 'Content-Type: application/http\r\n'
        + 'Content-Transfer-Encoding: binary\r\n'
        + '\r\n'
        + `${tunnelled || op.method} ${op.url} HTTP/1.1\r\n`
        + headers
        + '\r\n'
        + (op.payload === null ? '' : `${op.payload}\r\n`);
    }

    // The multipart/mixed envelope holding one ChangeSet of those parts.
    _encode(ops, digest, outer, inner) {
      return `--${outer}\r\n`
        + `Content-Type: multipart/mixed; boundary=${inner}\r\n`
        + '\r\n'
        + ops.map((op) => this._part(op, digest, inner)).join('')
        + `--${inner}--\r\n`
        + `--${outer}--\r\n`;
    }

    // Every part's status line, in order. The response echoes no request
    // line, so each match is one operation's outcome.
    _statuses(text) {
      const statuses = [];
      const statusRe = /HTTP\/1\.1\s+(\d{3})/g;
      let match;
      while ((match = statusRe.exec(text)) !== null) statuses.push(Number(match[1]));
      return statuses;
    }

    // Refusals are logged as well as thrown: the transcript is what an
    // operator pastes back, and a caller that swallows the error would
    // otherwise leave no trace of writes that never landed.
    _refuse(message, detail) {
      this.log('ERROR', message);
      const failure = new Error(message);
      Object.assign(failure, detail, { batchFailure: true });
      return failure;
    }

    async flush() {
      if (!this.pending.length) return { requests: 0, landed: 0, statuses: [] };
      // Taken before the request, so a throw cannot leave the same operations
      // queued to be written a second time.
      const ops = this.pending.splice(0);
      this.pendingBytes = BATCH_ENVELOPE_BYTES;
      const digest = await this.getDigest();
      const outer = batchBoundary('batch');
      const inner = batchBoundary('changeset');
      const body = this._encode(ops, digest, outer, inner);
      // No Accept header on purpose: #401 showed a JSON Accept turns the
      // throttling-page redirect into a 406 that only its URL identifies.
      // Omitting it keeps the redirect a plain page load.
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
      // A throttle that outlasted fetchWithRetry's retries is a tenant state
      // the surrounding phase has to pace against, not a refused write. It is
      // reported as its own thing so a caller can tell the two apart.
      if (isThrottled(response)) {
        throw this._refuse(
          `$batch of ${ops.length} operation(s) was throttled (HTTP ${response.status}) and none landed`,
          { throttled: true, sent: ops.length, landed: 0, refused: ops.length, statuses: [] },
        );
      }
      if (!response.ok) {
        throw this._refuse(
          `$batch of ${ops.length} operation(s) was refused: HTTP ${response.status} ${spError(text)}`,
          { throttled: false, sent: ops.length, landed: 0, refused: ops.length, statuses: [] },
        );
      }
      // The outer request answers 200 even when ChangeSet parts fail, so the
      // per-part statuses are the only thing that says a write landed. A
      // plain ok() here would report success while silently dropping writes.
      const statuses = this._statuses(text);
      if (statuses.length !== ops.length) {
        throw this._refuse(
          `$batch of ${ops.length} operation(s) answered HTTP ${response.status} with `
          + `${statuses.length} part status(es), so the writes cannot be accounted for`,
          { throttled: false, sent: ops.length, landed: 0, refused: ops.length, statuses },
        );
      }
      const landed = statuses.filter((status) => status >= 200 && status < 300).length;
      const refused = statuses.length - landed;
      this.opsSent += landed;
      if (refused) {
        const throttledParts = statuses.filter((status) => status === 429 || status === 503).length;
        throw this._refuse(
          `$batch of ${ops.length} operation(s): ${landed} landed, ${refused} refused `
          + `(part statuses ${statuses.join(', ')})`,
          { throttled: throttledParts > 0, sent: ops.length, landed, refused, statuses },
        );
      }
      dbg(`$batch sent ${ops.length} operation(s) in ${utf8Bytes(body)} bytes; all landed.`);
      return { requests: 1, landed, statuses };
    }

    // The close. flush() is already a no-op on an empty queue, so this takes
    // no second emptiness check that could disagree with it about one.
    async done() {
      return this.flush();
    }
  }

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

  // The whole assessment, taking its collaborators as an argument so the
  // standalone script and the deploy can share it without a second copy.
  async function assessSite(ctx) {
    const { requirements: REQUIREMENTS, targets: TARGETS,
            notAssessable: NOT_ASSESSABLE, log, web: WEB, origin: ORIGIN,
            fetchWithRetry, apiUrl, odataName, getDigest, getContextWebInformation,
            verdictLevel } = ctx;
    // Fail closed on a caller-built targets: a missing key is a bare TypeError
    // several probes in, and every one of these is read below.
    const missingTargets = ['base_templates', 'list_titles', 'list_markers',
      'declares_seal', 'declares_prevent_deletion', 'declares_column_formatting',
      'declares_form_formatting', 'declares_versioning', 'declares_groups',
    ].filter((k) => !(k in (TARGETS || {})));
    if (missingTargets.length) throw new Error(`assess-targets-incomplete: ctx.targets is missing ${missingTargets.join(', ')}`);
    // And on the collaborators: a probe inside its own try reports an absent one as the site's answer, not a build fault.
    const missingCollaborators = ['log', 'fetchWithRetry', 'apiUrl', 'odataName',
      'getDigest', 'getContextWebInformation',
    ].filter((k) => typeof ctx[k] !== 'function');
    if (missingCollaborators.length) throw new Error(`assess-context-incomplete: ctx is missing ${missingCollaborators.join(', ')}`);
    const findings = [];
    let verdict = null;
    const finding = (tier, key, level, detail) => {
      findings.push({ tier, key, level, detail });
      log(level, `[T${tier}] ${key}: ${detail}`);
    };
    // A property the site did not return is not a value. Printing it as one
    // put the literal word `undefined` in operator-facing lines.
    const reported = (v, fallback = '(not reported)') => (v == null ? fallback : v);

    // Read-only GET helper: returns parsed .d (or the raw json) or null.
    async function probeGet(suffix) {
      try {
        const r = await fetchWithRetry(apiUrl(suffix), { headers: { 'Accept': 'application/json;odata=verbose' } });
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

    // Which list titles exist, from ONE enumeration, answered
    // case-insensitively and without a getbytitle 404 (a first deploy has every
    // declared list absent, and the browser paints each 404 red). Null means
    // "enumeration refused"; callers fall back to per-list probing.
    const assessListTitleSet = async () => {
      const r = await probeGet('web/lists?$select=Title&$top=5000');
      if (!r.ok) return null;
      const results = (r.d && r.d.results) || [];
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
      const key = `provenance_marker:${title}`;
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

    // Collision probe per declared list. Description rides along on a request
    // already being made, so the marker check above costs no probe of its own.
    // Absence is read from the shared title enumeration, never a getbytitle
    // 404, so a first deploy does not paint the console red.
    const knownTitles = await assessListTitleSet();
    for (const title of TARGETS.list_titles) {
      const key = `collision:${title}`;
      if (knownTitles && !knownTitles.has(String(title).toLowerCase())) {
        finding(2, key, 'PASS', `'${title}' absent, a clean provision target.`);
        continue;
      }
      const list = await probeGet(`web/lists/getbytitle('${odataName(title)}')?$select=Title,BaseTemplate,Description`);
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
      } else {
        finding(2, key, 'WARN', `Could not probe '${title}' (HTTP ${list.status || list.error}).`);
      }
    }

    // The rename decision, predicted. Exactly one previous title carrying
    // its own marker while the current title is absent is the only shape
    // deploy renames; everything else blocks, because a guess here is a
    // list adopted or created over somebody else's.
    for (const [title, previousTitles] of (TARGETS.list_renames || [])) {
      const key = `rename:${title}`;
      const present = [];
      let unprobed = null;
      for (const [oldTitle, oldMarker] of previousTitles) {
        if (knownTitles && !knownTitles.has(String(oldTitle).toLowerCase())) continue;
        const old = await probeGet(`web/lists/getbytitle('${odataName(oldTitle)}')?$select=Title,Description`);
        if (!old.ok && old.status === 404) continue;
        if (!old.ok) { unprobed = `HTTP ${old.status || old.error} on '${oldTitle}'`; continue; }
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
      return r.ok && r.d && Array.isArray(r.d.results) ? r.d.results : null;
    }, (row) => row.Name);
    await renameFinding('site group', 'rename_group', TARGETS.group_renames || [], async () => {
      const r = await probeGet('web/sitegroups?$select=Title,Description&$top=5000');
      return r.ok && r.d && Array.isArray(r.d.results) ? r.d.results : null;
    }, (row) => row.Title);

    // Property-surface probes against the first EXISTING declared list, else
    // the site's own lists: 200 PASS, non-200 WARN.
    {
      let probeList = null;
      const surfaceTitles = await assessListTitleSet();
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

  // SharePoint resolves a list title, a field name and a site group name
  // CASE-INSENSITIVELY, and enforces their uniqueness the same way. Every
  // local index of those names must therefore match the same way: a
  // case-sensitive Set reports an existing 'or_opportunity' absent when the
  // mapping declares 'OR_Opportunity', and the run then tries to CREATE it
  // and fails on a name collision it could have adopted.
  const nameKey = (value) => String(value == null ? '' : value).toLowerCase();
  const nameSet = (values) => new Set((values || []).map(nameKey));
  const hasName = (set, value) => Boolean(set) && set.has(nameKey(value));

  // Which list titles exist, from ONE enumeration. A by-title GET for a list
  // that is not there answers 404, which the browser paints red and an
  // operator reads as a failure; on a first deploy EVERY list probe is that
  // 404. Enumerating once tells us absence locally, so a clean run stays
  // clean. Null means "not yet known"; invalidateListShapes() after any
  // list create or delete.
  let knownListTitles = null;
  const invalidateListShapes = () => { knownListTitles = null; };
  async function ensureKnownListTitles(force = false) {
    if (knownListTitles && !force) return knownListTitles;
    const r = await fetchWithRetry(apiUrl('web/lists?$select=Title&$top=5000'), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    // Deliberately not fatal: if the enumeration is refused we fall back to
    // per-list probing, which is noisier but still correct.
    if (!r.ok) return null;
    const j = await r.json();
    knownListTitles = nameSet(
      ((j && j.d && j.d.results) || []).map((l) => l.Title).filter((t) => typeof t === 'string'),
    );
    return knownListTitles;
  }

  // The by-title read and its fail-closed shape gate, with nothing in front
  // of it. Held apart from readListShape so a caller for whom an absent list
  // is FATAL can spend one request rather than two: see
  // assertDeclaredListOwnedNow, which argues why that is safe there.
  async function probeListShapeByTitle(name) {
    // Description rides along on a request already being made: it is a
    // declared, reconciled setting (it carries the provenance marker), so
    // reading it here is what lets reconcileListDescription compare without
    // spending a probe of its own.
    const select = [
      'Id', 'Title', 'BaseTemplate', 'ContentTypesEnabled', 'Description',
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
        || !(shape.Description == null || typeof shape.Description === 'string')
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

  async function readListShape(name, fresh = false) {
    // The existence check runs first for every caller that comes through
    // here, because asking getbytitle for an absent list answers 404, which
    // the browser paints red and an operator reads as a failure. `fresh`
    // re-enumerates rather than trusting the cache (a verification after a
    // write must never have its own write confirmed by a cache); either way
    // absence is learned from the enumeration, never a red 404.
    const titles = await ensureKnownListTitles(fresh);
    if (titles && !hasName(titles, name)) return null;
    return probeListShapeByTitle(name);
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
  // reflect PHASE-START state; each field-touching phase opens with
  // invalidateFieldShapes(); verify-after-write reads pass fresh=true and
  // bypass the cache entirely (verification never trusts a cache). An
  // absent LIST yields an uncached empty result; the list may be created
  // later in this same run.
  const _FIELD_SHAPE_SELECT = [
    'Id', 'InternalName', 'Title', 'TypeAsString', 'Description', 'Required',
    'EnforceUniqueValues', 'Indexed', 'ReadOnlyField', 'Sealed', 'DefaultValue', 'CustomFormatter',
  ].join(',');
  let fieldShapesByList = Object.create(null);
  // No argument: full reset (phase starts). With a list name: drop only
  // that list's snapshot, so lanes refresh their own list after writes
  // without thrashing the other lanes' caches.
  const invalidateFieldShapes = (listName) => {
    if (listName == null) { fieldShapesByList = Object.create(null); return; }
    delete fieldShapesByList[listName];
  };
  async function listFieldShapes(listName) {
    if (listName in fieldShapesByList) return fieldShapesByList[listName];
    // A list we already know is absent has no fields, and asking anyway
    // costs a 404 the browser paints red: on a first deploy, once per
    // declared list in maintenance unseal, before a single list exists.
    // The enumeration is already in hand for exactly this reason; this
    // just spends it here too.
    const titles = await ensureKnownListTitles();
    if (titles && !hasName(titles, listName)) {
      const empty = { get: () => undefined, size: 0 };
      fieldShapesByList[listName] = empty;
      return empty;
    }
    // `$top=500` for the same reason _verify_body.js.j2:141 carries it: with
    // no explicit page size the page size is the server's, and this read is
    // UNFILTERED, so an ordinary list's ~40 built-in fields plus its
    // declared ones sit close to the default. A truncated map reads exactly
    // like a list missing columns, and this map is what every phase's
    // create-or-reconcile decision is made from.
    const r = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(listName)}')/fields?$select=${_FIELD_SHAPE_SELECT}&$top=500`), {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!r.ok) {
      const text = await r.text();
      if (r.status === 404 || isAbsent400(r.status, text)) {
        // Cache the ABSENCE too. Leaving it uncached made every column in a
        // bulk loop re-enumerate an absent list: a first deploy paid one
        // 404 per declared column per phase (88 red console lines in
        // maintenance unseal alone), which is the exact cost this cache
        // exists to remove. Safe because every field-touching phase opens
        // with invalidateFieldShapes(), so a list created later in the run
        // is re-read at the next phase boundary rather than staying absent.
        const empty = { get: () => undefined, size: 0 };
        fieldShapesByList[listName] = empty;
        return empty;
      }
      throw new Error(`Field enumeration for '${listName}' failed: HTTP ${r.status} ${text}`);
    }
    const j = await r.json();
    // TWO indexes, not one keyspace. getbyinternalnameortitle resolves an
    // internal name first, so folding both into a single map lets one
    // field's display Title shadow another field's InternalName whenever
    // they match case-insensitively, and the loser is then read as an
    // impostor by the immutable-shape check, aborting preflight over a
    // field SharePoint can resolve perfectly well. First writer wins
    // WITHIN each index; internal names win BETWEEN them, matching the
    // endpoint this cache stands in for.
    const byInternal = new Map();
    const byTitle = new Map();
    for (const f of (j && j.d && j.d.results) || []) {
      if (f.InternalName && !byInternal.has(nameKey(f.InternalName))) {
        byInternal.set(nameKey(f.InternalName), f);
      }
      if (f.Title && !byTitle.has(nameKey(f.Title))) byTitle.set(nameKey(f.Title), f);
    }
    const shapes = {
      get: (name) => byInternal.get(nameKey(name)) || byTitle.get(nameKey(name)) || undefined,
      size: byInternal.size + byTitle.size,
    };
    fieldShapesByList[listName] = shapes;
    return shapes;
  }

  // getbyinternalnameortitle makes a renamed display Title repairable while
  // still letting the immutable InternalName check reject a same-title
  // impostor field. Shared so a batched read-back addresses a field by the
  // same spelling the single-GET probe does rather than a second one that
  // could drift from it.
  const fieldShapePath = (listName, columnName) =>
    `web/lists/getbytitle('${odataName(listName)}')/fields/getbyinternalnameortitle('${odataName(columnName)}')`;

  async function readFieldShape(listName, columnName, declaredField = null, fresh = false) {
    const fieldPath = fieldShapePath(listName, columnName);
    let shape;
    if (!fresh) {
      shape = (await listFieldShapes(listName)).get(columnName) || null;
      if (!shape) return null;
      // Cached entries were validated at enumeration time by the same checks
      // below; re-validate anyway, one shared gate for both paths.
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
    const derivedSelect = ["MaxLength", "RichText", "NumberOfLines", "AppendOnly", "Choices", "FillInChoice", "DisplayFormat", "SelectionMode", "Formula", "OutputType", "AllowMultipleValues"]
      .filter(name => Object.prototype.hasOwnProperty.call(body, name));
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
      const derivedKinds = new Map(Object.entries({"AllowMultipleValues": "boolean", "AppendOnly": "boolean", "Choices": "strings", "FillInChoice": "boolean", "Formula": "string", "RichText": "boolean"}));
      for (const name of derivedSelect) {
        const value = derived[name];
        const kind = derivedKinds.get(name) || 'integer';
        if (kind === 'strings') {
          if (!value || !Array.isArray(value.results) || value.results.some(item => typeof item !== 'string')) {
            throw new Error(`Field '${listName}.${columnName}' ${name} probe returned an invalid response`);
          }
        } else if (kind === 'boolean') {
          if (typeof value !== 'boolean') {
            throw new Error(`Field '${listName}.${columnName}' ${name} probe returned an invalid response`);
          }
        } else if (kind === 'string') {
          if (typeof value !== 'string') {
            throw new Error(`Field '${listName}.${columnName}' ${name} probe returned an invalid response`);
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
  // save conflicts, but different lists are fully independent. So the unit
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

  const sharePointGuid = (value, label) => {
    const held = String(value || '');
    if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(held)) {
      throw new Error(`Invalid ${label} GUID returned by SharePoint`);
    }
    return held;
  };

  // The ONE spelling of a field MERGE: address and headers both. A phase that
  // batches its field writes hands these to BatchWriter.add() instead of
  // calling patchFieldById, so the batched part and the single write cannot
  // drift into addressing different objects or sending different headers.
  // Both GUIDs are validated here, on the path every caller of either form
  // goes through.
  const fieldMergePath = (listId, fieldId) => `web/lists(guid'${sharePointGuid(listId, 'list')}')/fields(guid'${sharePointGuid(fieldId, 'field')}')`;
  const FIELD_MERGE_HEADERS = { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' };

  async function patchFieldById(listId, fieldId, body, digest) {
    const safeFieldId = sharePointGuid(fieldId, 'field');
    const url = apiUrl(fieldMergePath(listId, fieldId));
    const r = await fetchWithRetry(url, {
      method: 'POST',
      headers: spHeaders(digest, FIELD_MERGE_HEADERS),
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Field ${safeFieldId} MERGE failed: HTTP ${r.status} ${text}`);
    }
  }

  async function patchListById(listId, body, digest) {
    const safeListId = sharePointGuid(listId, 'list');
    const url = apiUrl(`web/lists(guid'${safeListId}')`);
    const r = await fetchWithRetry(url, {
      method: 'POST',
      headers: spHeaders(digest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`List ${safeListId} MERGE failed: HTTP ${r.status} ${text}`);
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
  // recursively, stringify; whitespace and key order differences are not
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
      "description": "Test group. Provisioned by dbml-sharepoint from simple-test for group List Maintainer.",
      "enroll_enterprise_reader": false,
      "enroll_operator_during_deploy": false,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for group List Maintainer.",
      "name": "List Maintainer",
      "only_allow_members_view_membership": false,
      "owner_group": "Site Owners",
      "previous_names": [],
      "require_empty_at_deploy": true
    }
  ],
  "indexed_columns": [
    {
      "field": "Title",
      "list": "APP_Project"
    },
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
      "description": "Parser-fixture projects, each with a status and a sort order. Provisioned by dbml-sharepoint from simple-test for list Project.",
      "enable_minor_versions": false,
      "enable_versioning": true,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for list Project.",
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
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": "{\"$schema\":\"https://developer.microsoft.com/json-schemas/sp/v2/column-formatting.schema.json\",\"attributes\":{\"class\":\"=if(@currentField == \u0027Open\u0027, \u0027sp-css-backgroundColor-BgLightBlue\u0027, \u0027sp-css-backgroundColor-BgMintGreen\u0027)\"},\"elmType\":\"div\",\"txtContent\":\"@currentField\"}",
          "display_title": "Status",
          "seal": false,
          "title": "Status",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
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
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": null,
          "display_title": "Sort Order",
          "seal": false,
          "title": "SortOrder",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
        }
      ],
      "item_security": null,
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "renamed_from": [],
      "title": "APP_Project",
      "title_patch": {
        "Description": "Project name.",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_described": "(NOT(Status eq \u0027Closed\u0027) OR SortOrder geq 0)",
      "validation_formula": "=OR([Status]\u003c\u003e\"Closed\",[Sort Order]\u003e=0)",
      "validation_hoisted": [],
      "validation_message": "A closed project needs a non-negative sort order."
    },
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "Parser-fixture tasks, each belonging to one project and optionally due on a date. Provisioned by dbml-sharepoint from simple-test for list Task.",
      "enable_minor_versions": false,
      "enable_versioning": true,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for list Task.",
      "fields_phase1": [
        {
          "body": {
            "AllowMultipleValues": false,
            "FieldTypeKind": 7,
            "LookupField": "Title",
            "Required": true,
            "Title": "Project",
            "__metadata": {
              "type": "SP.FieldLookup"
            }
          },
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": null,
          "display_title": "Project",
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
          "title": "Project",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
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
          "client_validation_formula": "__dbmlsp_unmanaged__",
          "custom_formatter": null,
          "display_title": "Due Date",
          "seal": false,
          "title": "DueDate",
          "validation_formula": "__dbmlsp_unmanaged__",
          "validation_message": "__dbmlsp_unmanaged__"
        }
      ],
      "item_security": null,
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "renamed_from": [],
      "title": "APP_Task",
      "title_patch": {
        "Description": "",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_described": null,
      "validation_formula": null,
      "validation_hoisted": [],
      "validation_message": null
    },
    {
      "base_template": 100,
      "content_types_enabled": false,
      "description": "Parser-fixture singleton settings list, one row holding the fixture configuration. Provisioned by dbml-sharepoint from simple-test for list AppSettings.",
      "enable_minor_versions": false,
      "enable_versioning": true,
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for list AppSettings.",
      "fields_phase1": [],
      "item_security": null,
      "kind": "List",
      "major_version_limit": 500,
      "prevent_deletion": false,
      "renamed_from": [],
      "title": "APP_AppSettings",
      "title_patch": {
        "Description": "App Settings singleton.",
        "Required": true,
        "__metadata": {
          "type": "SP.FieldText"
        }
      },
      "validation_described": null,
      "validation_formula": null,
      "validation_hoisted": [],
      "validation_message": null
    }
  ],
  "permission_levels": [
    {
      "base_permissions": {
        "high": "0",
        "low": "2049"
      },
      "description": "Test permission level. Provisioned by dbml-sharepoint from simple-test for level Schema Manager.",
      "expected_marker": "Provisioned by dbml-sharepoint from simple-test for level Schema Manager.",
      "name": "Schema Manager",
      "previous_names": []
    }
  ],
  "phase2_lookups": [],
  "requires_manage_permissions": true,
  "seed_items": [],
  "views": [
    {
      "aggregations": "",
      "caml_query": "\u003cWhere\u003e\u003cAnd\u003e\u003cOr\u003e\u003cIsNull\u003e\u003cFieldRef Name=\"Status\"/\u003e\u003c/IsNull\u003e\u003cNeq\u003e\u003cFieldRef Name=\"Status\"/\u003e\u003cValue Type=\"Text\"\u003eClosed\u003c/Value\u003e\u003c/Neq\u003e\u003c/Or\u003e\u003cOr\u003e\u003cIsNotNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNotNull\u003e\u003cIsNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNull\u003e\u003c/Or\u003e\u003c/And\u003e\u003c/Where\u003e\u003cOrderBy\u003e\u003cFieldRef Name=\"SortOrder\"/\u003e\u003c/OrderBy\u003e",
      "formatting": "{\"additionalRowClass\":\"=if([$Status] == \u0027Closed\u0027, \u0027sp-css-backgroundColor-BgLightGray\u0027, \u0027\u0027)\"}",
      "hidden": false,
      "list": "APP_Project",
      "renamed_from": [],
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
      "aggregations": "",
      "caml_query": "",
      "formatting": null,
      "hidden": true,
      "list": "APP_Project",
      "renamed_from": [],
      "row_limit": null,
      "set_default": false,
      "title": "All Items",
      "url_slug": "AllItems",
      "view_fields": [
        "ID",
        "Title",
        "Status",
        "SortOrder",
        "Created",
        "Modified",
        "Author",
        "Editor"
      ],
      "widths": null
    },
    {
      "aggregations": "",
      "caml_query": "",
      "formatting": null,
      "hidden": false,
      "list": "APP_Task",
      "renamed_from": [],
      "row_limit": null,
      "set_default": true,
      "title": "All Items",
      "url_slug": "AllItems",
      "view_fields": [
        "ID",
        "Title",
        "Project",
        "DueDate",
        "Created",
        "Modified",
        "Author",
        "Editor"
      ],
      "widths": null
    },
    {
      "aggregations": "",
      "caml_query": "\u003cGroupBy Collapse=\"FALSE\"\u003e\u003cFieldRef Name=\"Project\"/\u003e\u003c/GroupBy\u003e\u003cWhere\u003e\u003cAnd\u003e\u003cLeq\u003e\u003cFieldRef Name=\"DueDate\"/\u003e\u003cValue Type=\"DateTime\"\u003e\u003cToday OffsetDays=\"30\"/\u003e\u003c/Value\u003e\u003c/Leq\u003e\u003cOr\u003e\u003cIsNotNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNotNull\u003e\u003cIsNull\u003e\u003cFieldRef Name=\"ID\"/\u003e\u003c/IsNull\u003e\u003c/Or\u003e\u003c/And\u003e\u003c/Where\u003e\u003cOrderBy\u003e\u003cFieldRef Name=\"DueDate\"/\u003e\u003c/OrderBy\u003e",
      "formatting": null,
      "hidden": false,
      "list": "APP_Task",
      "renamed_from": [],
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
    },
    {
      "aggregations": "",
      "caml_query": "",
      "formatting": null,
      "hidden": false,
      "list": "APP_AppSettings",
      "renamed_from": [],
      "row_limit": null,
      "set_default": true,
      "title": "All Items",
      "url_slug": "AllItems",
      "view_fields": [
        "ID",
        "Title",
        "Created",
        "Modified",
        "Author",
        "Editor"
      ],
      "widths": null
    }
  ]
};

  const TYPE_AS_STRING_BY_KIND = new Map([[2, "Text"], [3, "Note"], [4, "DateTime"], [6, "Choice"], [7, "Lookup"], [8, "Boolean"], [9, "Number"], [11, "URL"], [15, "MultiChoice"], [17, "Calculated"], [20, "User"]]);
  const MULTI_TYPE_AS_STRING_BY_KIND = new Map([[7, "LookupMulti"]]);
  const BASE_TYPE_AS_STRING = new Map([["LookupMulti", "Lookup"]]);
  const baseTypeAsString = (name) => BASE_TYPE_AS_STRING.get(name) || name;
  const indexedFieldKeys = new Set(
    SCHEMA.indexed_columns.map(idx => `${idx.list}\u0000${idx.field}`),
  );
  const normalizeGuid = (value) => String(value).replace(/[{}]/g, '').toLowerCase();
  // Null and '' are the same absent description; everything else compares as
  // stored. Used for FIELD descriptions and, since 2026-08-12, for the LIST
  // Description that carries the provenance marker.
  //
  // A raw byte compare, which the surface supports: MEASURED 2026-08-14 by
  // test/manual/list-description-probe.js, a list Description returns
  // unchanged through both the create and the MERGE path, including an
  // ampersand, a run of two spaces, a bare LF and a CRLF, at 1018 characters.
  // ValidationFormula is the counter-example that made this worth measuring,
  // since SharePoint does normalise those and canonicalFormula exists for it.
  const normalizeDescription = (value) => value == null ? '' : String(value);
  const normalizeDefaultValue = (value) => value == null || value === '' ? null : String(value);
  const DERIVED_FIELD_PROPERTIES = ["MaxLength", "RichText", "NumberOfLines", "AppendOnly", "Choices", "FillInChoice", "DisplayFormat", "SelectionMode", "Formula", "OutputType", "AllowMultipleValues"];

  // Distinguishes "clear this value" from "not managed here". Declared
  // before any consumer: the synthetic Title patch in _lists.js.j2 needs it
  // too, and a caller that omits it is treated as managed.
  const UNMANAGED = "__dbmlsp_unmanaged__";

  // Every field this run changed from sealed to unsealed. The value retains
  // the pair while the key makes repeat encounters idempotent. Exit cleanup
  // restores exactly these fields and never seals one it found open.
  const fieldsUnsealedForRun = new Map();

  // The restoration itself, called from the finally in deploy.js.j2 rather
  // than from PROTECTION. Every phase between PREPARE and PROTECTION can
  // return early by design (schema errors, lookup errors, ACL errors all
  // abort before touching more of the site), and each of those returns
  // used to skip the re-seal, ending the run with a column LESS protected
  // than it found it. A failed run must not weaken a site, so the
  // guarantee has to sit on the exit path, which is the only path every
  // abort shares. Idempotent by construction: PROTECTION normally seals
  // these on the way past, and this writes only what it finds still open,
  // so the success path pays one field enumeration per affected list.
  async function restoreUnsealedFields() {
    const byList = new Map();
    for (const [listTitle, columnTitle, listId, fieldId] of fieldsUnsealedForRun.values()) {
      if (!byList.has(listTitle)) byList.set(listTitle, []);
      byList.get(listTitle).push([columnTitle, listId, fieldId]);
    }
    for (const [listTitle, columns] of byList.entries()) {
      invalidateFieldShapes(listTitle);  // never trust phase-start state
      for (const [columnTitle, listId, fieldId] of columns) {
        try {
          const list = SCHEMA.lists.find(candidate => candidate.title === listTitle);
          if (!list) throw new Error(`No declaration found for list '${listTitle}'`);
          const currentList = await readListShape(listTitle, true);
          if (!currentList) {
            log('WARN', `Could not re-seal '${listTitle}.${columnTitle}': the original list no longer exists.`);
            continue;
          }
          assertListAdoptable(list, currentList);
          if (currentList.Id !== listId) {
            throw new Error(`List '${listTitle}' changed identity before exit cleanup`);
          }
          const shape = await readFieldShape(listTitle, columnTitle, null, true);
          if (!shape) {
            log('WARN', `Could not re-seal '${listTitle}.${columnTitle}': the original field no longer exists.`);
            continue;
          }
          if (shape.Id !== fieldId) {
            throw new Error(`Field '${listTitle}.${columnTitle}' changed identity before exit cleanup`);
          }
          if (shape.Sealed === true) continue;
          const digest = await getDigest();
          await patchFieldById(
            listId, fieldId, { __metadata: { type: 'SP.Field' }, Sealed: true }, digest,
          );
          invalidateFieldShapes(listTitle);
          const verify = await readFieldShape(listTitle, columnTitle, null, true);
          if (!verify || verify.Id !== fieldId || verify.Sealed !== true) {
            throw new Error(`Field '${listTitle}.${columnTitle}' did not retain sealed state during exit cleanup`);
          }
          log('WARN', `Re-sealed '${listTitle}.${columnTitle}' while exiting: the run opened it and did not reach the seal phase.`);
        } catch (err) {
          // Loud, and recorded: the operator has to know the site was left
          // open, because nothing else in the run will say so.
          log('ERROR', `Could not re-seal '${listTitle}.${columnTitle}': ${err.message}. The column is left UNSEALED; re-seal it before handing the site back.`);
          summary.errors.push({ phase: 'exit', list: listTitle, column: columnTitle, error: err.message });
        }
      }
    }
  }

  // The ONE constructor for the synthetic Title field. Title is not a
  // declared column (it arrives as list.title_patch), so every consumer of
  // a declared field has to synthesise one. Keep it here: a second copy
  // elsewhere will drift out of step with this one.
  function syntheticTitleField(list) {
    return {
      title: 'Title',
      body: { ...list.title_patch, FieldTypeKind: 2 },
      // Title is not a declared field, so it carries no declared formulas.
      // All three sentinels must be explicit: `undefined !== UNMANAGED`
      // reads as "managed", which MERGEs an empty message onto the built-in
      // Title column and aborts the phase.
      client_validation_formula: UNMANAGED,
      validation_formula: UNMANAGED,
      validation_message: UNMANAGED,
      // Answers the impostor guard only. The built-in Title exists on every
      // SharePoint list and can never be a same-named impostor, so a sealed
      // Title must not fail the shape check. The tool does not own Title's
      // seal state: the PREPARE unseal opens it only if it is already
      // sealed, and PROTECTION restores exactly what was found.
      seal: true,
    };
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
    // Arity first, because one FieldTypeKind can name two types. A declared
    // AllowMultipleValues on a kind with no multi spelling is a generator bug
    // and fails closed here rather than comparing against `undefined`.
    const multiValued = field.body.AllowMultipleValues === true;
    const typeAsString = multiValued
      ? MULTI_TYPE_AS_STRING_BY_KIND.get(field.body.FieldTypeKind)
      : TYPE_AS_STRING_BY_KIND.get(field.body.FieldTypeKind);
    if (!typeAsString) {
      throw new Error(`Field '${listName}.${field.title}' has unsupported declared FieldTypeKind ${field.body.FieldTypeKind}${multiValued ? ' with AllowMultipleValues' : ''}`);
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

  // The ONE create call for a declared lookup, both arities, because the two
  // phases that create one (_lists.js.j2 for the acyclic ones, _lookups.js.j2
  // for the deferred ones) would otherwise each hold their own copy of the
  // route choice.
  //
  // AddField CANNOT MAKE A MULTI-VALUE LOOKUP. SP.FieldCreationInformation has
  // no AllowMultipleValues property and the POST is refused HTTP 400
  // (measured 2026-09-02, test/manual/multilookup-probe.js,
  // `field.multilookup.create-readback-type`). createfieldasxml with
  // Type="LookupMulti" Mult="TRUE" and Options 8 returned HTTP 201 and read
  // back TypeAsString="LookupMulti", FieldTypeKind=7,
  // AllowMultipleValues=true, entity type SP.FieldLookup.
  //
  // Neither route can carry Description, and the XML route cannot carry
  // Required either. Both are applied by the reconcileDeclaredField MERGE the
  // callers issue straight after, which is already how a [unique] single-value
  // lookup gets EnforceUniqueValues and Indexed.
  async function createDeclaredLookupField(listName, field, targetGuid, digest) {
    const listPath = `web/lists/getbytitle('${odataName(listName)}')`;
    if (field.lookup_creation_xml) {
      const spec = field.lookup_creation_xml;
      const xml = `<Field Type="${spec.type}" Mult="TRUE" DisplayName="${spec.name}" `
        + `Name="${spec.name}" List="{${targetGuid}}" ShowField="${spec.show_field}"/>`;
      await postJson(
        apiUrl(`${listPath}/fields/createfieldasxml`),
        { parameters: { SchemaXml: xml, Options: 8 } },
        digest,
      );
      return;
    }
    await postJson(
      apiUrl(`${listPath}/fields/addfield`),
      { parameters: { ...field.lookup_creation_parameters, LookupListId: targetGuid } },
      digest,
    );
  }

  function declaredFieldsForList(list) {
    const titleField = syntheticTitleField(list);
    const deferred = SCHEMA.phase2_lookups
      .filter(lookup => lookup.list === list.title)
      .map(lookup => lookup.field);
    return [titleField, ...list.fields_phase1, ...deferred];
  }

  // A property that could not be compared is not a difference, and printing it
  // as one sends the operator to fix a column nobody looked at.
  function describeMismatch(m) {
    if (!m || !m.property) return String((m && m.message) || m);
    if (!m.checked) return `${m.property}: NOT CHECKED (${m.message})`;
    // The message rides along: an absent lookup target compares a declared list
    // TITLE against a readback GUID, which without it reads as a wrong value.
    return `${m.property}: declared ${JSON.stringify(m.declared)}, readback ${JSON.stringify(m.actual)} (${m.message})`;
  }

  // One entry per mismatched property. The throwing wrapper below keeps every
  // caller's semantics; nothing else reads the returned array yet.
  function immutableListMismatches(list, actual) {
    const mismatches = [];
    if (actual.BaseTemplate !== list.base_template) {
      mismatches.push({
        property: 'BaseTemplate',
        declared: list.base_template,
        actual: actual.BaseTemplate,
        message: `Existing '${list.title}' has BaseTemplate ${actual.BaseTemplate}; expected ${list.base_template} for declared kind '${list.kind}'. `
          + 'SharePoint list/library templates are immutable; provision a clean object or perform an explicit migration.',
        // Same key the field entries carry, so one consumer filter fits both.
        checked: true,
      });
    }
    return mismatches;
  }

  function listOwnershipMismatches(list, actual) {
    const expected = list.expected_marker;
    const held = actual && actual.Description;
    if (typeof expected === 'string'
        && expected.length > 0
        && typeof held === 'string'
        && held.includes(expected)) return [];
    return [{
      property: 'Description',
      declared: expected,
      actual: held,
      message: `Existing '${list.title}' does not carry its exact provenance marker. `
        + 'A matching title, template, schema or item count is not ownership authority; '
        + 'restore the exact marker only if this tool created the list, otherwise rename the declaration.',
      checked: true,
    }];
  }

  function listAdoptionMismatches(list, actual) {
    return [
      ...immutableListMismatches(list, actual),
      ...listOwnershipMismatches(list, actual),
    ];
  }

  function assertListAdoptable(list, actual) {
    const mismatches = listAdoptionMismatches(list, actual);
    if (mismatches.length > 0) {
      throw new Error([...new Set(mismatches.map(m => m.message))].join(' '));
    }
  }

  // ONE request per call, by probing the list by title with no enumeration
  // ahead of it. `readListShape(name, true)` spends a forced
  // web/lists?$select=Title enumeration first so that an absent list is
  // answered locally instead of by a 404 the browser paints red. That trade
  // is right where absence is the expected answer: a clean first provision,
  // or surveyOwnedListsForWrites's allowAbsent branch, which both keep it.
  // Here absence is FATAL. This guard runs only for a list this run has
  // already created or adopted, so a miss costs the one 404 and then aborts
  // the caller, while a hit is every call the guard actually makes on a
  // healthy site. MEASURED on a ten-list family: 462 calls, 2 GETs each, 924
  // of ~4,400 requests, the run's largest single bucket at 21%. Probing
  // first drops 462 of them, about a tenth of the deploy, and the miss still
  // costs one.
  //
  // Nothing weakens: the enumeration was never the authority for existence.
  // It is capped at $top=5000, and ensureKnownListTitles already falls back
  // to trusting this same probe whenever the enumeration is refused, so
  // getbytitle has always been what decides. On a miss the cached title set
  // is dropped rather than re-read: re-reading it cannot change the answer,
  // and a re-read that failed would replace this function's precise absence
  // message with a transport error.
  async function assertDeclaredListOwnedNow(listName) {
    const list = SCHEMA.lists.find(candidate => candidate.title === listName);
    if (!list) throw new Error(`No declaration found for list '${listName}'`);
    const actual = await probeListShapeByTitle(listName);
    if (!actual) {
      invalidateListShapes();  // it still claims a list that is not there
      throw new Error(`Declared list '${listName}' disappeared before a field write`);
    }
    assertListAdoptable(list, actual);
    return actual;
  }

  async function assertDeclaredFieldOwnedNow(listName, field) {
    await assertDeclaredListOwnedNow(listName);
    const target = field.target_list
      ? await assertDeclaredListOwnedNow(field.target_list)
      : null;
    return target ? target.Id : null;
  }

  async function assertDeclaredFieldTargetNow(listName, field, targetGuid) {
    const freshTargetGuid = await assertDeclaredFieldOwnedNow(listName, field);
    if (field.target_list && freshTargetGuid !== targetGuid) {
      throw new Error(
        `Lookup target '${field.target_list}' changed identity before reconciling '${listName}.${field.title}'`,
      );
    }
  }

  // === Live ownership guard for the post-schema write phases (#305) ===
  // Schema reconciliation proves ownership and then stops. Index writes,
  // sealing, ACL reconciliation and seeding all ran afterwards addressing
  // their target by TITLE, so a marker removed or a same-titled list swapped
  // in between phases was written to by a run that had never proved it owned
  // that object. ACL removals and seeding are the worst of those, because
  // neither is recoverable by rerunning. The three functions below are the
  // one guard every such phase uses.

  // One declared list's live identity, immediately before a write group:
  // assertDeclaredListOwnedNow's cache-bypassing read and exact marker check,
  // plus the binding to an identity an earlier check in this phase captured.
  // The marker alone cannot see a same-titled replacement, since a
  // replacement can carry a copied Description; the list Id is what separates
  // them.
  async function ownedListIdentity(listName, expectedId = null, when = 'before a write') {
    const actual = await assertDeclaredListOwnedNow(listName);
    const listId = sharePointGuid(actual.Id, 'list');
    if (expectedId != null && listId !== sharePointGuid(expectedId, 'list')) {
      throw new Error(`List '${listName}' changed identity ${when}`);
    }
    return actual;
  }

  // The ownership survey for a whole write batch, run before ANY list in it
  // is mutated: one list's failure must not leave the lists surveyed ahead of
  // it written and the ones behind it refused. Returns title -> live Id, or
  // null when any list failed, which is the caller's signal to abort the
  // phase. `allowAbsent` is for the phases that legitimately run before a
  // list exists (a clean first provision); absence is not a failure there.
  async function surveyOwnedListsForWrites(listTitles, phaseNumber, label, allowAbsent = false) {
    const identities = new Map();
    let failed = false;
    await mapLanes([...new Set(listTitles)], title => title, async (listTitle) => {
      try {
        if (!allowAbsent) {
          identities.set(listTitle, (await assertDeclaredListOwnedNow(listTitle)).Id);
          return;
        }
        const list = SCHEMA.lists.find(candidate => candidate.title === listTitle);
        if (!list) throw new Error(`No declaration found for list '${listTitle}'`);
        const actual = await readListShape(listTitle, true);
        if (!actual) return;
        assertListAdoptable(list, actual);
        identities.set(listTitle, actual.Id);
      } catch (err) {
        failed = true;
        log('ERROR', `${label} ownership survey '${listTitle}': ${err.message}`);
        summary.errors.push({ phase: phaseNumber, list: listTitle, error: err.message });
      }
    }, 4);
    return failed ? null : identities;
  }

  // The live field a MERGE is addressed by, bound to both identities: the
  // list is re-proved owned and unchanged, then the field's own Id is read so
  // the write goes to /lists(guid)/fields(guid) rather than to two names a
  // replacement object answers to just as well. `fresh` is false where the
  // caller has already refreshed the per-list field enumeration this probe
  // reads from, so a bulk lane does not pay one GET per column for evidence
  // it already holds.
  async function ownedFieldIdentity(listName, columnName, expectedListId, fresh = true) {
    const owned = await ownedListIdentity(
      listName, expectedListId, `before writing '${listName}.${columnName}'`,
    );
    const shape = await readFieldShape(listName, columnName, null, fresh);
    if (!shape) {
      throw new Error(`Declared column '${listName}.${columnName}' disappeared before a write`);
    }
    return { listId: owned.Id, field: shape };
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
  // and renaming, so merging it with the pre-field list settings fails with
  // "The formula refers to a column that does not exist". Declared-null
  // means "never touch" (a hand-set validation survives).
  async function reconcileListValidation(list, digest) {
    if (list.validation_formula == null) return;
    const actual = await readListShape(list.title, true);
    if (!actual) throw new Error(`Declared list '${list.title}' disappeared before validation reconcile`);
    assertListAdoptable(list, actual);
    const formulaSame = canonicalFormula(actual.ValidationFormula || '') === canonicalFormula(list.validation_formula);
    const messageSame = (actual.ValidationMessage || '') === (list.validation_message || '');
    if (formulaSame && messageSame) return;
    await patchListById(actual.Id, {
      __metadata: { type: 'SP.List' },
      ValidationFormula: list.validation_formula,
      ValidationMessage: list.validation_message,
    }, digest);
    const verify = await readListShape(list.title, true);
    if (verify) assertListAdoptable(list, verify);
    if (!verify
        || canonicalFormula(verify.ValidationFormula || '') !== canonicalFormula(list.validation_formula)
        || (verify.ValidationMessage || '') !== (list.validation_message || '')) {
      throw new Error(`List '${list.title}' did not retain declared validation (declared ${JSON.stringify(list.validation_formula)}; readback ${JSON.stringify(verify && verify.ValidationFormula)})`);
    }
    log('INFO', `List '${list.title}' declared validation reconciled.`);
  }

  // Declared list-deletion block: AllowDeletion=false rejects UI deletion
  // of the LIST object even for admins (friction, not enforcement; an
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
    const owned = await assertDeclaredListOwnedNow(list.title);
    await patchListById(owned.Id, { __metadata: { type: 'SP.List' }, AllowDeletion: false }, digest);
    const verifyResp = await fetchWithRetry(adUrl, {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const verifyJson = verifyResp.ok ? await verifyResp.json() : null;
    if (!verifyJson || !verifyJson.d || verifyJson.d.AllowDeletion !== false) {
      throw new Error(`List '${list.title}' did not retain AllowDeletion = false`);
    }
    log('INFO', `List '${list.title}' deletion block applied (AllowDeletion = false).`);
  }

  // Declared ITEM-level trimming: ReadSecurity / WriteSecurity, each 1 ("all
  // items") or 2 ("items created by the user"). They narrow what a LIST-level
  // grant reaches, which is how a drop box is built -- Contribute plus
  // ReadSecurity=2 is "add rows, read back only your own".
  //
  // Its own probe/MERGE rather than a line in desiredListSettings, for the
  // same reason reconcileListDeletionBlock has one: these two properties are
  // not part of the shape probe every list pays for, they are declared by one
  // family, and an unsupported tenant surface should fail this step alone
  // rather than every list's settings reconcile. Null declaration means the
  // properties are never read and never written.
  //
  // The read-back is the control, not ceremony. A MERGE that answers 200
  // while the stored value stays 1 leaves a list that accepts every row and
  // shows every row to everybody, while the deploy reports the drop box was
  // built. This throws instead.
  async function reconcileListItemSecurity(list, digest) {
    if (!list.item_security) return;
    const desired = {
      ReadSecurity: list.item_security.read_security,
      WriteSecurity: list.item_security.write_security,
    };
    const isUrl = apiUrl(`web/lists/getbytitle('${odataName(list.title)}')?$select=ReadSecurity,WriteSecurity`);
    const isResp = await fetchWithRetry(isUrl, {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    if (!isResp.ok) {
      const text = await isResp.text();
      throw new Error(`ReadSecurity/WriteSecurity probe failed: HTTP ${isResp.status} ${text}`);
    }
    const isJson = await isResp.json();
    const actual = (isJson && isJson.d) || {};
    if (!Number.isInteger(actual.ReadSecurity) || !Number.isInteger(actual.WriteSecurity)) {
      throw new Error(
        `List '${list.title}' item-security probe returned no ReadSecurity/WriteSecurity; `
        + `this tenant does not expose the properties the declared item_security needs.`,
      );
    }
    if (actual.ReadSecurity === desired.ReadSecurity
        && actual.WriteSecurity === desired.WriteSecurity) {
      return;
    }
    const owned = await assertDeclaredListOwnedNow(list.title);
    await patchListById(owned.Id, { __metadata: { type: 'SP.List' }, ...desired }, digest);
    const verifyResp = await fetchWithRetry(isUrl, {
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const verify = verifyResp.ok ? ((await verifyResp.json()).d || {}) : {};
    if (verify.ReadSecurity !== desired.ReadSecurity
        || verify.WriteSecurity !== desired.WriteSecurity) {
      throw new Error(
        `List '${list.title}' did not retain declared item security `
        + `(declared read ${desired.ReadSecurity} / write ${desired.WriteSecurity}; `
        + `readback read ${verify.ReadSecurity} / write ${verify.WriteSecurity})`,
      );
    }
    log('INFO', `List '${list.title}' item security reconciled: reads ${list.item_security.read}, `
      + `writes ${list.item_security.write}.`);
    logChange({ key: `item security: ${list.title}`, kind: 'permission', target: list.title,
      oldValue: `read ${actual.ReadSecurity}, write ${actual.WriteSecurity}`,
      newValue: `read ${desired.ReadSecurity}, write ${desired.WriteSecurity}` });
  }

  // The declared list Description carries the provenance marker. Ownership is
  // established before this function runs. Reconciliation may repair human
  // prose around a retained marker, but must never add a missing marker to an
  // object ordinary deploy found by title.
  //
  // There is no lock to lean on. Fields have Sealed and lists have
  // AllowDeletion; SharePoint offers no equivalent for a Description.
  // SP.List.Description is a plain read-write property updated by the same
  // MERGE as any other list setting (Learn, checked 2026-08-12:
  // learn.microsoft.com/dotnet/api/microsoft.sharepoint.client.list.description
  // and .../sp-add-ins/working-with-lists-and-list-items-with-rest). So
  // reconcile-and-read-back is the entire control, and the read-back is
  // real rather than ceremonial: a MERGE that answers 200 while the
  // stored value stays stale reports success on a list that is still
  // invisible, which is precisely the failure class this repository exists
  // to catch.
  //
  // `actual` is the shape reconcileListShape already holds, so an unchanged
  // description costs no request at all; a re-paste must not churn every
  // list it looks at. Only a repair pays the MERGE and its fresh re-read.
  async function reconcileListDescription(list, actual, digest) {
    const desired = normalizeDescription(list.description);
    actual = await assertDeclaredListOwnedNow(list.title);
    if (normalizeDescription(actual.Description) === desired) return actual;
    await patchListById(actual.Id, {
      __metadata: { type: 'SP.List' },
      Description: desired,
    }, digest);
    const verify = await readListShape(list.title, true);
    if (!verify) {
      throw new Error(`Declared list '${list.title}' disappeared after the Description MERGE`);
    }
    assertListAdoptable(list, verify);
    if (verify.Id !== actual.Id) {
      throw new Error(`List '${list.title}' changed identity after the Description MERGE`);
    }
    if (normalizeDescription(verify.Description) !== desired) {
      throw new Error(
        `List '${list.title}' did not retain its declared Description `
        + `(declared ${JSON.stringify(desired)}; readback ${JSON.stringify(verify.Description)}). `
        + 'Without it the list carries no provenance marker and no report can find it.',
      );
    }
    log('INFO', `List '${list.title}' description reconciled (was ${JSON.stringify(normalizeDescription(actual.Description))}).`);
    return verify;
  }

  async function reconcileListShape(list, digest) {
    let actual = await assertDeclaredListOwnedNow(list.title);
    const desired = desiredListSettings(list);
    if (listSettingsMismatch(actual, desired)) {
      actual = await assertDeclaredListOwnedNow(list.title);
      const patchedListId = actual.Id;
      await patchListById(actual.Id, {
        __metadata: { type: 'SP.List' },
        ...desired,
      }, digest);
      actual = await readListShape(list.title, true);
      if (!actual) throw new Error(`Declared list '${list.title}' disappeared after settings MERGE`);
      assertListAdoptable(list, actual);
      if (actual.Id !== patchedListId) {
        throw new Error(`List '${list.title}' changed identity after settings MERGE`);
      }
      if (listSettingsMismatch(actual, desired)) {
        const drifted = Object.keys(desired).filter(key => actual[key] !== desired[key]);
        throw new Error(`List '${list.title}' did not retain declared setting(s): ${drifted.join(', ')}`);
      }
      log('INFO', `List '${list.title}' declared versioning/content-type settings reconciled.`);
    } else {
      log('INFO', `List '${list.title}' immutable template and declared settings verified.`);
    }
    // After the settings MERGE, so it compares against the freshest shape,
    // and on BOTH paths: a list created moments ago had its Description in
    // the creation POST, and nothing had ever read that write back.
    actual = await reconcileListDescription(list, actual, digest);
    await reconcileListItemSecurity(list, digest);
    await reconcileListDeletionBlock(list, digest);
    return actual;
  }

  // `resolveTitle` maps a DECLARED list title to the one the site holds it
  // under right now. Preflight runs BEFORE the renames phase, so on an
  // unmigrated site the target is still under a previous title, and reading it
  // by the declared title reported the FIELD missing when the LIST was.
  // Null means identity, which is every caller after the renames have run.
  async function expectedLookupFieldInternalName(listName, field, resolveTitle = null) {
    const targetTitle = resolveTitle ? resolveTitle(field.target_list) : field.target_list;
    const targetDisplay = await readFieldShape(
      targetTitle,
      field.body.LookupField,
      null,
    );
    if (!targetDisplay) {
      throw new Error(
        `Lookup '${listName}.${field.title}' target display field '${targetTitle}.${field.body.LookupField}' does not exist`,
      );
    }
    if (targetDisplay.InternalName !== field.body.LookupField) {
      throw new Error(
        `Lookup '${listName}.${field.title}' target display field resolves to immutable InternalName '${targetDisplay.InternalName}'; expected '${field.body.LookupField}'`,
      );
    }
    return targetDisplay.InternalName;
  }

  async function immutableFieldMismatches(
    listName, field, actual, targetGuid, targetState = null, resolveTitle = null,
  ) {
    const desired = declaredFieldState(listName, field);
    const mismatches = [];
    // checked:true means compared and differed; checked:false means it could not
    // be compared, which the report must not present as a difference.
    const mismatch = (property, declared, actualValue, message) => mismatches.push({
      property, declared, actual: actualValue, message, checked: true,
    });
    const notChecked = (property, declared, message) => mismatches.push({
      property, declared, actual: null, message, checked: false,
    });
    if (actual.InternalName !== field.title) {
      mismatch('InternalName', field.title, actual.InternalName,
        `Existing field '${listName}.${field.title}' resolves to immutable InternalName '${actual.InternalName}'; expected '${field.title}'`);
    }
    // COMPARED AS BASE TYPES. What is immutable is that a Lookup can never
    // become a Text; arity is not, so a single-value lookup widened to
    // multi-value in the DBML must reconcile rather than abort. The arity
    // itself is verified as a derived property (AllowMultipleValues), read
    // back and drift-reported like any other.
    if (baseTypeAsString(actual.TypeAsString) !== baseTypeAsString(desired.typeAsString)) {
      mismatch('TypeAsString', desired.typeAsString, actual.TypeAsString,
        `Existing field '${listName}.${field.title}' has immutable TypeAsString '${actual.TypeAsString}'; expected '${desired.typeAsString}'`);
    }
    // SP.FieldCalculated is intrinsically ReadOnlyField=true (users never
    // write it); on every other declared type read-only means an impostor.
    const expectReadOnly = desired.typeAsString === 'Calculated';
    if (actual.ReadOnlyField !== expectReadOnly) {
      mismatch('ReadOnlyField', expectReadOnly, actual.ReadOnlyField,
        `Existing field '${listName}.${field.title}' ReadOnlyField is ${actual.ReadOnlyField}; expected ${expectReadOnly} for declared type '${desired.typeAsString}'`);
    }
    // Declared-seal fields are legitimately sealed between runs (the
    // maintenance unseal opens them for this run's writes; Phase 4.1
    // re-seals). Sealed WITHOUT a declaration still means an impostor.
    if (actual.Sealed && !field.seal) {
      mismatch('Sealed', false, actual.Sealed,
        `Existing field '${listName}.${field.title}' is sealed; expected an unsealed declared field`);
    }
    if (!field.target_list) return mismatches;
    if (!targetGuid) {
      // Absent is a certain refusal. Anything else means nobody resolved the
      // target, and "does not exist" would point at the wrong list.
      if (targetState == null || targetState === 'absent') {
        mismatch('LookupList', field.target_list, actual.LookupList,
          `Existing lookup '${listName}.${field.title}' cannot be adopted because declared target list '${field.target_list}' does not yet exist`);
      } else if (targetState === 'unreadable') {
        notChecked('LookupList', field.target_list,
          `Existing lookup '${listName}.${field.title}' was not checked because declared target list '${field.target_list}' could not be read`);
      } else {
        notChecked('LookupList', field.target_list,
          `Existing lookup '${listName}.${field.title}' was not checked because declared target list '${field.target_list}' resolved to no list identifier`);
      }
      return mismatches;
    }
    // Compared before the display-field probe, so a wrong target list survives a
    // throw from resolving the declared target's display field.
    const listDiffers = normalizeGuid(actual.LookupList) !== normalizeGuid(targetGuid);
    let expectedLookupField;
    try {
      expectedLookupField = await expectedLookupFieldInternalName(listName, field, resolveTitle);
    } catch (err) {
      // Recorded, not propagated: a throw would discard this column's other mismatches.
      if (listDiffers) {
        mismatch('LookupList', targetGuid, actual.LookupList,
          `Existing lookup '${listName}.${field.title}' targets list '${actual.LookupList}'; expected '${targetGuid}'. Lookup targets are immutable; recreate through an explicit migration.`);
      }
      notChecked('LookupField', field.body.LookupField, err.message);
      return mismatches;
    }
    // One entry per differing property: a single entry hard-coded 'LookupList',
    // so a column differing only in LookupField reported the wrong property and
    // two GUIDs that normalizeGuid exists to call equal.
    const fieldDiffers = actual.LookupField !== expectedLookupField;
    if (listDiffers || fieldDiffers) {
      const message = `Existing lookup '${listName}.${field.title}' targets list '${actual.LookupList}' field '${actual.LookupField}'; `
        + `expected list '${targetGuid}' field '${expectedLookupField}'. Lookup targets are immutable; recreate through an explicit migration.`;
      if (listDiffers) mismatch('LookupList', targetGuid, actual.LookupList, message);
      if (fieldDiffers) mismatch('LookupField', expectedLookupField, actual.LookupField, message);
    }
    return mismatches;
  }

  async function assertFieldImmutableShape(listName, field, actual, targetGuid) {
    const mismatches = await immutableFieldMismatches(listName, field, actual, targetGuid);
    // De-duplicated: the two lookup properties share one message, and the joined
    // text must stay what a single-property mismatch has always said.
    if (mismatches.length > 0) throw new Error([...new Set(mismatches.map(m => m.message))].join(' '));
  }

  // Declared form behaviour. Two properties, opposite round-trip
  // behaviour, both verified against a live tenant:
  //
  //   ClientValidationFormula  conditional + per-form visibility.
  //                            Reads back BYTE-IDENTICAL, so compare raw.
  //   ValidationFormula        save-time rule. NORMALISED on save (brackets
  //                            stripped, whitespace removed), so compare
  //                            canonically or every redeploy reports drift
  //                            that is not there.
  //
  // SchemaXml's ShowInNewForm/ShowInEditForm are deliberately NOT written.
  // Saving the form designer migrates them into FieldLink.Hidden, which
  // hides a column from EVERY form and is not writable over REST, so a
  // per-form declaration would silently become hide-everywhere the first
  // time anyone opened the designer.
  async function enforceDeclaredFormulas(listName, field, digest, targetGuid) {
    const url = apiUrl(`web/lists/getbytitle('${odataName(listName)}')/fields/getbyinternalnameortitle('${odataName(field.title)}')`);
    const read = async () => {
      const r = await fetchWithRetry(`${url}?$select=ClientValidationFormula,ClientValidationMessage,ValidationFormula,ValidationMessage`, {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!r.ok) throw new Error(`formula probe failed: HTTP ${r.status} ${await r.text()}`);
      return (await r.json()).d;
    };

    const body = { '__metadata': { 'type': 'SP.Field' } };
    let wanted = false;
    if (field.client_validation_formula !== UNMANAGED) {
      body.ClientValidationFormula = field.client_validation_formula;
      // Cleared alongside: a message beside a visibility formula is a
      // property whose interaction with it was never observed, and leaving
      // one in an unknown state next to a repurposed property is how a
      // surprise arrives later.
      body.ClientValidationMessage = '';
      wanted = true;
    }
    if (field.validation_formula !== UNMANAGED) {
      body.ValidationFormula = field.validation_formula;
      body.ValidationMessage = field.validation_message;
      wanted = true;
    }
    if (!wanted) return;

    const before = await read();
    const same = (a, b) => (a || '') === (b || '');
    const alreadyRight =
      (field.client_validation_formula === UNMANAGED
        || (same(before.ClientValidationFormula, field.client_validation_formula)
            && same(before.ClientValidationMessage, '')))
      && (field.validation_formula === UNMANAGED
        || (canonicalFormula(before.ValidationFormula || '') === canonicalFormula(field.validation_formula)
            && same(before.ValidationMessage, field.validation_message)));
    if (alreadyRight) return;

    // Log what is being REPLACED before replacing it. `before` was read,
    // compared and discarded, and on success nothing was logged at all,
    // so a deploy that removed or rewrote an existing formula left no
    // record of what had been there. Under `reconcile: exact` an
    // undeclared column's formula is cleared outright, which is precisely
    // the case where the prior value is the only thing anyone would want
    // back. Only non-empty priors are logged: a first-time write has
    // nothing to say.
    const replaced = [];
    if (field.client_validation_formula !== UNMANAGED
        && (before.ClientValidationFormula || '') !== ''
        && !same(before.ClientValidationFormula, field.client_validation_formula)) {
      replaced.push(`ClientValidationFormula was ${JSON.stringify(before.ClientValidationFormula)}`);
    }
    if (field.validation_formula !== UNMANAGED
        && (before.ValidationFormula || '') !== ''
        && canonicalFormula(before.ValidationFormula || '') !== canonicalFormula(field.validation_formula)) {
      replaced.push(`ValidationFormula was ${JSON.stringify(before.ValidationFormula)}`);
    }
    if (field.validation_formula !== UNMANAGED
        && (before.ValidationMessage || '') !== ''
        && !same(before.ValidationMessage, field.validation_message)) {
      replaced.push(`ValidationMessage was ${JSON.stringify(before.ValidationMessage)}`);
    }
    if (replaced.length > 0) {
      const action = field.client_validation_formula === '' && field.validation_formula === ''
        ? 'clearing' : 'overwriting';
      log('INFO', `Field '${listName}.${field.title}' ${action} declared formulas: ${replaced.join('; ')}`);
    }

    await assertDeclaredFieldTargetNow(listName, field, targetGuid);
    const r = await fetchWithRetry(url, {
      method: 'POST',
      headers: spHeaders(digest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
      body: JSON.stringify(body),
    });
    if (!r.ok) {
      const text = await r.text();
      // CLEARING a formula from a field type that cannot carry one is a
      // no-op, not a failure: the desired end state (no formula) already
      // holds, and SharePoint is refusing the property rather than the
      // value. Aborting a whole paste over it means one URL column stops a
      // deploy that has nothing wrong with it.
      //
      // Narrow on purpose. It applies only when every declared formula in
      // this body is the empty string, so a SET is never swallowed; the
      // generator's own unsupported-kind list normally prevents the request
      // entirely, and this is what stops the next kind missing from that
      // hand-kept list becoming an aborted paste rather than a log line.
      const clearingOnly = (field.validation_formula === '' || field.validation_formula === UNMANAGED)
        && (field.client_validation_formula === '' || field.client_validation_formula === UNMANAGED);
      if (clearingOnly && /does not support validation formulas/i.test(text)) {
        // A MERGE is atomic, so the refusal applied NONE of this body,
        // including any ClientValidationFormula clear it also carried,
        // which a URL field does support. Returning here would report
        // success while a stale show/hide rule stayed live and the
        // read-back below never ran. So retry with only the properties
        // this field type accepts, then fall through and verify.
        const clientOnly = { '__metadata': body.__metadata };
        if ('ClientValidationFormula' in body) {
          clientOnly.ClientValidationFormula = body.ClientValidationFormula;
          clientOnly.ClientValidationMessage = body.ClientValidationMessage;
        }
        if (Object.keys(clientOnly).length > 1) {
          await assertDeclaredFieldTargetNow(listName, field, targetGuid);
          const retry = await fetchWithRetry(url, {
            method: 'POST',
            headers: spHeaders(digest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
            body: JSON.stringify(clientOnly),
          });
          if (!retry.ok) {
            throw new Error(`declared formulas MERGE failed: HTTP ${r.status} ${text}; client-only retry also failed: HTTP ${retry.status} ${await retry.text()}`);
          }
        }
        log('INFO', `Field '${listName}.${field.title}': field type carries no validation formula, so there is none to clear; continuing.`);
      } else {
        throw new Error(`declared formulas MERGE failed: HTTP ${r.status} ${text}`);
      }
    }

    // A SEALED column accepts the write, reports success and discards it,
    // so the read-back is the only evidence the change landed.
    const after = await read();
    if (field.client_validation_formula !== UNMANAGED
        && !same(after.ClientValidationFormula, field.client_validation_formula)) {
      throw new Error(
        `Field '${listName}.${field.title}' did not retain ClientValidationFormula `
        + `(declared ${JSON.stringify(field.client_validation_formula)}; readback ${JSON.stringify(after.ClientValidationFormula)})`,
      );
    }
    if (field.client_validation_formula !== UNMANAGED
        && !same(after.ClientValidationMessage, '')) {
      throw new Error(
        `Field '${listName}.${field.title}' did not retain ClientValidationMessage `
        + `(declared ""; readback ${JSON.stringify(after.ClientValidationMessage)})`,
      );
    }
    if (field.validation_formula !== UNMANAGED
        && canonicalFormula(after.ValidationFormula || '') !== canonicalFormula(field.validation_formula)) {
      // Both values are logged: SharePoint's normalisation may do more than
      // has been observed, and a bare failure would need another probe.
      throw new Error(
        `Field '${listName}.${field.title}' did not retain ValidationFormula `
        + `(declared ${JSON.stringify(field.validation_formula)}; readback ${JSON.stringify(after.ValidationFormula)})`,
      );
    }
    if (field.validation_formula !== UNMANAGED
        && !same(after.ValidationMessage, field.validation_message)) {
      throw new Error(
        `Field '${listName}.${field.title}' did not retain ValidationMessage `
        + `(declared ${JSON.stringify(field.validation_message)}; readback ${JSON.stringify(after.ValidationMessage)})`,
      );
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
      await assertDeclaredFieldTargetNow(listName, field, targetGuid);
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
    await enforceDeclaredFormulas(listName, field, digest, targetGuid);
    return true;
  }

  async function verifyDependentField(listName, dependentName, showField, primaryId, targetGuid) {
    // A projected dependent field must be a genuine dependent Lookup linked
    // back to its primary by FieldRef, targeting the same list, and read-only.
    // Existence alone is not enough: a same-named impostor field would be
    // adopted silently. See test/manual/projected-lookup-probe.js for the
    // measured create shape and the properties verified here.
    const fieldPath = `web/lists/getbytitle('${odataName(listName)}')/fields/getbyinternalnameortitle('${odataName(dependentName)}')`;
    const r = await fetchWithRetry(apiUrl(
      `${fieldPath}?$select=IsDependentLookup,PrimaryFieldId,LookupList,LookupField,ReadOnlyField`,
    ), { headers: { 'Accept': 'application/json;odata=verbose' } });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Dependent field '${listName}.${dependentName}' probe failed: HTTP ${r.status} ${text}`);
    }
    const j = await r.json();
    const s = j && j.d;
    const mismatches = [];
    const check = (name, ok, detail) => { if (!ok) mismatches.push(`${name} ${detail}`); };
    check('IsDependentLookup', s.IsDependentLookup === true,
      `(readback ${JSON.stringify(s.IsDependentLookup)})`);
    check('PrimaryFieldId', normalizeGuid(s.PrimaryFieldId) === normalizeGuid(primaryId),
      `(readback ${JSON.stringify(s.PrimaryFieldId)}; expected primary '${primaryId}')`);
    check('LookupList', normalizeGuid(s.LookupList) === normalizeGuid(targetGuid),
      `(readback ${JSON.stringify(s.LookupList)}; expected target '${targetGuid}')`);
    check('LookupField', s.LookupField === showField,
      `(readback ${JSON.stringify(s.LookupField)}; expected '${showField}')`);
    check('ReadOnlyField', s.ReadOnlyField === true,
      `(readback ${JSON.stringify(s.ReadOnlyField)})`);
    if (mismatches.length) {
      throw new Error(`Dependent field '${listName}.${dependentName}' is misconfigured: ${mismatches.join(', ')}`);
    }
  }

  // === Preflight: ManageLists (+ ManagePermissions when the schema has ACL work) ===
  // ManageLists is Low bit 0x800; ManagePermissions is Low bit 0x2000000.
  // (Previous check incorrectly tested High; ManageLists lives in Low.)
  // ManagePermissions is only demanded when the schema actually performs
  // Phase 1.3/4 permission work, so an operator who can manage lists but not
  // ACLs is not rejected on a list-only deployment. SCHEMA.requires_manage_permissions
  // is computed once in Python (requires_manage_permissions in
  // analysis/permissions.py) and shared with assess.js's own preflight and
  // the manifest, rather than re-derived here -- see #166 item 5.
  const needsPermissions = SCHEMA.requires_manage_permissions;
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
  // Run-scoped privilege is exit-scoped too. Keep the state and cleanup
  // outside the phase try so an unexpected throw can still remove every
  // membership this deployment added.
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
  // Enterprise reader enrolment cleanup (#213 form 1). Declared here,
  // unconditionally, so an ordinary build with no reader flag still has
  // this list and drain function: _reader_enrolment.js.j2 wraps its whole
  // phase body in a template conditional on enterprise_reader, and a
  // declaration made only inside that block would be a ReferenceError in
  // the finally below on every build that never emits it.
  //
  // Unlike the operator's run-scoped enrolment, the reader account is meant
  // to outlive the run, but only if the run REACHES the end: two concurrent
  // deploys naming different reader addresses can each add their own
  // account and each then abort at the strays check a phase later, and
  // without this both accounts stayed enrolled forever. runReachedTheEnd is
  // set once, on the success path in deploy/_seeds.js.j2, after every abort
  // gate in the phase chain has been passed.
  const readerEnrollments = [];
  let runReachedTheEnd = false;
  async function removeReaderEnrollments() {
    if (runReachedTheEnd) {
      // The run reached the end: this is a permanent grant now, not
      // something to undo. Cleared rather than left for a stale reference.
      readerEnrollments.length = 0;
      return;
    }
    for (const enrollment of readerEnrollments.splice(0)) {
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
        log('INFO', `Removed the enterprise reader this run enrolled into '${enrollment.groupName}', because the run did not reach the end.`);
      } catch (err) {
        log('ERROR', `Could not remove the enterprise reader from '${enrollment.groupName}': ${err.message}. Remove it in Site permissions > Groups.`);
      }
    }
  }
  // Deployment run/change logging. The shim pair is declared here,
  // unconditionally, for the same reason the reader-enrolment drain is:
  // renames (phase 1.3) run BEFORE the logging phase (1.5), so changes
  // raised there must not be lost, and the finally below must be able to
  // call finishRunLog on every build even when the logging phase never
  // emitted (abort before phase 1.5 leaves nothing to stamp into).
  // logChange buffers until _logging.js.j2 replaces it with the real
  // writer; finishRunLog stays a no-op unless that phase completed its
  // setup, because a run that died before it cannot stamp a list that
  // was never ensured.
  const DEPLOY_CHANGES = [];
  let logChange = (change) => { DEPLOY_CHANGES.push(change); };
  let finishRunLog = async () => {};

  // Every phase runs inside this try so that the finally below is reached
  // by EVERY exit: the normal `return summary` at the end of the last
  // phase, the early returns that abort a broken run, and a throw
  // nobody caught. Anything a run must hand back regardless of outcome
  // belongs in that finally and nowhere else; putting it on the success
  // path is how a failed run came to leave a Title unsealed. The phase
  // bodies keep their own indentation: they are 3,000 lines of included
  // partials, and re-indenting them to sit under this try would bury the
  // change in whitespace.
  try {
  markPhase('Phase 1.1: site assessment');
  // Runs the site assessment and refuses a verdict the operator has not accepted.
  log('INFO', 'Group 1: PREPARE');
  log('INFO', 'Starting Phase 1.1: site assessment.');
  let assessment;
  // A throw is a broken probe, not a verdict, and every other phase hands back
  // a structured summary when it aborts.
  try {
    assessment = await assessSite({
      requirements: ASSESS_REQUIREMENTS, targets: ASSESS_TARGETS,
      notAssessable: ASSESS_NOT_ASSESSABLE, log, web: WEB,
      origin: window.location.origin, verdictLevel: 'INFO',
      fetchWithRetry, apiUrl, odataName, getDigest, getContextWebInformation,
    });
  } catch (err) {
    log('ERROR', `The assessment could not run (${err.message}); no deployment writes were attempted.`);
    return { ...summary, aborted: 'assessment-failed' };
  }
  // Its own key: summary.errors.length gates the later phase aborts, and a
  // finding is not a deployment error.
  summary.assessment = assessment;
  // Every blocking finding, not the first: the verdict keeps only one
  // requirement, and a site blocked three ways would otherwise name one.
  const assessBlocking = assessment.findings.filter(f => f.level === 'BLOCKED');
  // The verdict alone, never assessBlocking.length: the verdict is the only
  // thing that knows which findings THIS pack requires, and a BLOCKED finding
  // it does not require must not stop a deploy the assessment calls deployable.
  if (assessment.verdict === 'BLOCKED') {
    // Re-stated at ERROR because the body logged the verdict at INFO, and a
    // console filtered to errors would show the abort with nothing naming it.
    for (const f of assessBlocking) log('ERROR', `  ${f.key}: ${f.detail}`);
    log('ERROR', 'The assessment found a blocking condition; no deployment writes were attempted.');
    return { ...summary, aborted: 'assessment-blocked' };
  }
  if (assessment.verdict === 'DEGRADED' && !ACKNOWLEDGE_DEGRADED) {
    // Every level the verdict degrades on, not WARN alone: NOT-ASSESSABLE
    // degrades it too, and a site degrading only that way named nothing here.
    // BLOCKED is included because a blocking finding the pack does not require
    // is still worth reading, and Tier 3 is not, because it is the same list on
    // every site and would bury the findings that are about this one.
    const degrading = new Set(['WARN', 'BLOCKED', 'NOT-ASSESSABLE']);
    for (const f of assessment.findings.filter(f => f.tier !== 3 && degrading.has(f.level))) {
      log('ERROR', `  ${f.key}: ${f.detail}`);
    }
    log('ERROR', 'The assessment found degrading conditions. Review them, set ACKNOWLEDGE_DEGRADED = true at the top of this script, and paste again.');
    return { ...summary, aborted: 'assessment-degraded-unacknowledged' };
  }
  markPhase('Phase 1.2: read-only preflight');
  // === Preflight: fail-closed adoption of existing schema objects ===
  // A matching display name is not proof that an existing list or field was
  // created from this schema. Before Phase 1.3 performs its first write, every
  // existing list must carry this declaration's exact provenance marker and
  // every immutable shape must agree. Mutable settings are reconciled only
  // after both checks pass.
  log('INFO', 'Starting Phase 1.2: read-only preflight.');
  invalidateFieldShapes();  // probes reflect phase-start state
  // Read-only, so lanes are free of write races, but the field wave still
  // waits for ALL list shapes: lookup fields validate against their target
  // list's GUID, which another lane may still be reading.
  const preflightListShapes = Object.create(null);
  // Three outcomes: 'absent' (no such list), 'unreadable' (its probe failed),
  // 'ok' (a shape was read, whether or not that shape matched). A fourth,
  // 'mismatch', was removed: a mismatched list still has its shape stored, so
  // neither consumer could ever tell it from 'ok'.
  // Null-prototype, so a list titled 'constructor' or 'toString' cannot read
  // truthy from Object.prototype without ever being assigned.
  const listOutcomes = Object.create(null);
  // Lists found under a previous title carrying that title's own marker,
  // keyed by the current title. The renames phase acts on it; nothing here
  // writes. A previous title without its marker, present beside the current
  // title, or present twice over is an error, never a guess.
  const renamePlan = Object.create(null);
  // By declared TITLE, so a lookup can resolve its target the same way the
  // owning list resolves itself. Renames have not run yet at preflight.
  const probeTitle = (title) => (renamePlan[title] ? renamePlan[title].from : title);
  const probeTitleFor = (list) => probeTitle(list.title);
  async function previousTitleShapes(list) {
    const found = [];
    for (const previous of (list.renamed_from || [])) {
      const shape = await readListShape(previous.title);
      if (!shape) continue;
      const held = typeof shape.Description === 'string' ? shape.Description : '';
      found.push({
        title: previous.title, marker: previous.expected_marker, shape,
        carries: previous.expected_marker.length > 0 && held.includes(previous.expected_marker),
      });
    }
    return found;
  }
  await mapLanes(SCHEMA.lists, (list) => list.title, async (list) => {
    try {
      let actual = await readListShape(list.title);
      const previous = await previousTitleShapes(list);
      if (!actual && previous.length === 0) { listOutcomes[list.title] = 'absent'; return; }
      let renamedFrom = null;
      if (previous.length > 0) {
        const titles = previous.map((p) => `'${p.title}'`).join(', ');
        let refusal = null;
        if (actual) {
          refusal = `'${list.title}' exists and so does its previous title ${titles}; deploy cannot tell a rename from a collision. Remove or retitle one of them by hand.`;
        } else if (previous.length > 1) {
          refusal = `more than one previous title of '${list.title}' exists (${titles}); deploy cannot choose which to rename. Remove or retitle all but one by hand.`;
        } else if (!previous[0].carries) {
          refusal = `'${previous[0].title}' exists but does not carry the exact provenance marker for its previous name ("${previous[0].marker}"). Deploy will not adopt or rename it; restore that marker only if this tool created the list.`;
        }
        if (refusal) {
          listOutcomes[list.title] = 'ok';
          log('ERROR', `Existing-schema list '${list.title}': ${refusal}`);
          summary.errors.push({ phase: 'preflight', list: list.title, error: refusal, mismatches: [] });
          return;
        }
        renamedFrom = previous[0];
        actual = renamedFrom.shape;
        renamePlan[list.title] = { from: renamedFrom.title, marker: renamedFrom.marker, id: actual.Id };
        log('INFO', `'${renamedFrom.title}' carries the marker for its previous name; the renames phase will retitle it '${list.title}'.`);
      }
      // Stored BEFORE the shape is judged: a list with a wrong BaseTemplate
      // still resolves lookup GUIDs and its columns are still worth reporting.
      preflightListShapes[list.title] = actual;
      listOutcomes[list.title] = 'ok';
      // readListShape also fail-closes malformed or omitted mutable settings;
      // drift itself is safe to repair later and is reported for visibility.
      if (listSettingsMismatch(actual, desiredListSettings(list))) {
        log('INFO', `Existing list '${list.title}' has mutable versioning/content-type drift; Phase 2.1 will reconcile it.`);
      }
      // Ownership of a planned rename was proved by the PREVIOUS marker
      // above; the current marker is written by the renames phase.
      const mismatches = renamedFrom
        ? immutableListMismatches(list, actual)
        : listAdoptionMismatches(list, actual);
      if (mismatches.length === 0) return;
      const message = [...new Set(mismatches.map(m => m.message))].join(' ');
      log('ERROR', `Existing-schema list '${list.title}': ${message}`);
      // Last statement in the try, as in the field lane below: anything that
      // threw after this push would give one list a second entry, and the
      // grouped report reads only the first.
      summary.errors.push({
        phase: 'preflight', list: list.title, error: message, mismatches,
      });
    } catch (err) {
      listOutcomes[list.title] = 'unreadable';
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
        const actual = await readFieldShape(probeTitleFor(list), field.title, field);
        if (!actual) continue;
        const targetGuid = field.target_list
          ? preflightListShapes[field.target_list]?.Id
          : null;
        const mismatches = await immutableFieldMismatches(
          list.title, field, actual, targetGuid,
          field.target_list ? listOutcomes[field.target_list] : null,
          probeTitle,
        );
        if (mismatches.length === 0) continue;
        const message = [...new Set(mismatches.map(m => m.message))].join(' ');
        log('ERROR', `Existing-schema field '${list.title}.${field.title}': ${message}`);
        summary.errors.push({
          phase: 'preflight', list: list.title, column: field.title,
          error: message, mismatches,
        });
      } catch (err) {
        log('ERROR', `Existing-schema field '${list.title}.${field.title}': ${err.message}`);
        summary.errors.push({
          phase: 'preflight', list: list.title, column: field.title, error: err.message,
        });
      }
    }
  }, 4);

  if (summary.errors.length > 0) {
    // Four lanes interleave their own ERROR lines, so the whole delta is
    // regrouped here in declaration order and printed once.
    const preflight = summary.errors.filter(e => e.phase === 'preflight');
    log('ERROR', 'Existing-schema shape delta:');
    for (const list of SCHEMA.lists) {
      const own = preflight.find(e => e.list === list.title && !e.column);
      const columns = preflight.filter(e => e.list === list.title && e.column);
      if (!own && columns.length === 0) continue;
      log('ERROR', `  ${list.title}`);
      if (listOutcomes[list.title] === 'unreadable') {
        log('ERROR', `    NOT CHECKED: ${own?.error ?? 'the list shape could not be read'}`);
        log('ERROR', '    No column was checked, because the list shape could not be read.');
        continue;
      }
      if (own) {
        const entries = own.mismatches ?? [];
        if (entries.length === 0) log('ERROR', `    ${own.error}`);
        for (const m of entries) log('ERROR', `    ${describeMismatch(m)}`);
      }
      for (const column of columns) {
        log('ERROR', `    ${column.column}`);
        const entries = column.mismatches ?? [];
        if (entries.length === 0) log('ERROR', `      NOT CHECKED: ${column.error}`);
        for (const m of entries) log('ERROR', `      ${describeMismatch(m)}`);
      }
    }
    log('ERROR', 'Existing-schema shape preflight failed; no deployment writes were attempted.');
    return { ...summary, aborted: 'existing-schema-shape-errors' };
  }

  markPhase('Phase 1.3: list renames');
  // === Phase 1.3: list renames ===
  log('INFO', 'Starting Phase 1.3: list renames.');
  {
    const planned = Object.entries(renamePlan);
    if (planned.length === 0) {
      log('INFO', 'No list is under a previous title; nothing to rename.');
    }
    for (const [newTitle, plan] of planned) {
      const list = SCHEMA.lists.find((candidate) => candidate.title === newTitle);
      try {
        // Re-read at write time: the preflight's answer is not authority over
        // a list something else may have touched since.
        const fresh = await readListShape(plan.from, true);
        const held = fresh && typeof fresh.Description === 'string' ? fresh.Description : '';
        if (!fresh || fresh.Id !== plan.id || !held.includes(plan.marker)) {
          throw new Error(`'${plan.from}' no longer carries the marker for its previous name, or is no longer the list the preflight read; nothing was renamed.`);
        }
        if (await readListShape(newTitle, true)) {
          throw new Error(`'${newTitle}' appeared since the preflight; deploy cannot tell a rename from a collision.`);
        }
        // SP.List Title and Description are plain read-write properties written
        // by the same MERGE as any other list setting; the readback by id is
        // the control.
        const digest = await getDigest();
        await patchListById(fresh.Id, {
          __metadata: { type: 'SP.List' }, Title: newTitle, Description: list.description || '',
        }, digest);
        const r = await fetchWithRetry(apiUrl(`web/lists(guid'${fresh.Id}')?$select=Id,Title,Description`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!r.ok) throw new Error(`readback after the retitle failed: HTTP ${r.status} ${spError(await r.text())}`);
        const back = ((await r.json()) || {}).d || {};
        if (back.Title !== newTitle || back.Description !== (list.description || '')) {
          throw new Error(`'${plan.from}' read back as '${back.Title}' with Description ${JSON.stringify(back.Description)} after writing '${newTitle}'; the retitle did not take.`);
        }
        invalidateListShapes();
        summary.listsRenamed.push({ from: plan.from, to: newTitle });
        log('INFO', `Renamed '${plan.from}' to '${newTitle}' in place (read back by list id).`);
        logChange({ key: `list: ${plan.from}`, kind: 'rename', target: plan.from,
          oldValue: plan.from, newValue: newTitle });
      } catch (err) {
        summary.errors.push({ phase: '1.3', list: newTitle, error: err.message });
        log('ERROR', `Rename '${plan.from}' -> '${newTitle}': ${err.message}`);
        return { ...summary, aborted: 'rename-errors' };
      }
    }
  }
  markPhase('Phase 1.4: permission levels and site groups');
  // === Phase 1.4: custom permission levels + site groups ===
  log('INFO', 'Starting Phase 1.4: permission levels and site groups.');
  {
    // A digest the phase takes for itself is outside every per-object catch, so a refusal rejected the deploy (#282).
    async function phaseDigest() {
      try {
        return await getDigest();
      } catch (err) {
        log('ERROR', `Phase 1.4: ${err.message}`);
        summary.errors.push({ phase: '1.4', error: err.message });
        return null;
      }
    }
    let digest0 = await phaseDigest();

    // A built-in owner group always exists (it is the site's own associated
    // group), so resolveGroupOwner's Associated*Group branches never 404.
    // Used below to decide whether an adopt-path owner resolve is safe
    // during survey, or must be deferred to apply.
    const BUILTIN_OWNER_GROUPS = new Set(['Site Owners', 'Site Members', 'Site Visitors']);

    // Existence probe via $filter: getbyname returns HTTP 500 (not 404) for
    // a missing role definition, so a getbyname probe cannot distinguish
    // "absent" from a real failure. The filter form returns 200 with empty
    // results when absent. getbyname is still used below for the MERGE,
    // where the level is known to exist. Description is selected alongside
    // Id because the adoption gate below reads it; selecting Id alone would
    // give the gate nothing to test. Shared with the create path's Id
    // fallback, so both ask SharePoint the identical question.
    //
    // OPEN QUESTION, 2026-08-15: whether $filter=Name eq '...' matches
    // case-sensitively is not documented on Microsoft Learn and was not one
    // of the ten questions test/manual/role-definition-probe.js asked. If it
    // is case-sensitive, a site level named 'schema manager' reads as absent
    // against a declared 'Schema Manager', so this probe returns no rows,
    // the create path runs, and the adoption gate below never sees the
    // existing level. That is NOT a gate fail-open: nothing is written to
    // the existing level, which is the same behaviour as before this
    // branch. The residual is real, though: the create either collides with
    // the existing level and errors, or leaves two case-variant levels in
    // place, and _acls.js.j2's resolveRoleDefId, which resolves a level by
    // name through its own getbyname call, then binds whichever one
    // SharePoint's name resolution picks. The group path further below in
    // this file was given nameSet/hasName for exactly this hazard, at the
    // site-group enumeration; this path has no equivalent, because it is
    // not yet known whether one is needed. A question for the next
    // test/manual/role-definition-probe.js run.
    async function probeLevelExistence(name) {
      const resp = await fetchWithRetry(apiUrl(`web/roledefinitions?$select=Id,Description&$filter=Name eq '${odataName(name)}'`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Probe for permission level '${name}' failed: HTTP ${resp.status} ${text}`);
      }
      const json = await resp.json();
      const rows = json?.d?.results;
      if (!Array.isArray(rows)) {
        throw new Error(`Probe for permission level '${name}' returned an invalid response`);
      }
      return rows;
    }

    // WEB SCOPE ONLY, and this count NEVER decides whether to adopt. This
    // tool assigns its levels at LIST scope through _acls.js.j2, and
    // access.role-def.web-assignments-enumerable of role-definition-probe.js
    // measured web scope alone, so a zero here does not mean unused. It is
    // reported to tell the operator what they are looking at.
    async function countWebAssignmentsUsing(levelId) {
      let total = 0;
      let url = apiUrl('web/roleassignments?$select=PrincipalId&$expand=RoleDefinitionBindings&$top=200');
      while (url) {
        const resp = await fetchWithRetry(url, { headers: { 'Accept': 'application/json;odata=verbose' } });
        if (!resp.ok) {
          const text = await resp.text();
          throw new Error(`Role assignment enumeration failed: HTTP ${resp.status} ${text}`);
        }
        const json = await resp.json();
        if (!json || !json.d || !Array.isArray(json.d.results)) {
          throw new Error('Role assignment enumeration returned an invalid response');
        }
        for (const row of json.d.results) {
          // Verbose is expected to render an expanded navigation property as
          // `{ results: [...] }`. That is inferred from _acls.js.j2's own
          // expanded reads under verbose, not measured here:
          // access.role-def.web-assignments-enumerable probed this same URL
          // under odata=nometadata, whose shape differs. Tolerating a bare array
          // too, like the probe's own bindingsOf, means a wrong inference
          // only degrades the refusal message below; an unreadable row still
          // throws rather than counting as clean.
          const raw = row.RoleDefinitionBindings;
          const bindings = Array.isArray(raw) ? raw : (raw && raw.results);
          if (!Array.isArray(bindings)) {
            // A row whose bindings cannot be read is usage this cannot see.
            // access.role-def.web-assignments-enumerable took the same
            // position and recorded NOT ESTABLISHED rather than counting it
            // as clean.
            throw new Error('A role assignment returned bindings this script cannot read; the usage report would be incomplete');
          }
          if (bindings.some((b) => String(b.Id) === String(levelId))) total += 1;
        }
        url = json.d.__next || null;
      }
      return total;
    }

    // access.role-def.basepermissions-readback
    // (test/manual/role-definition-probe.js, 2026-08-14): Description and
    // both bitmap halves round-trip exactly as written, so this compare is
    // exact rather than fuzzy. Bitmap halves are compared as strings: the
    // tenant represents SP.BasePermissions.High/Low as Int64, which OData
    // verbose serialises as a string, and the declared value already is one
    // (analysis.permissions.HighLow).
    async function verifyLevelSettings(lvl, levelId) {
      const resp = await fetchWithRetry(
        apiUrl(`web/roledefinitions(${levelId})?$select=Id,Description,BasePermissions`),
        { headers: { 'Accept': 'application/json;odata=verbose' } },
      );
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Permission level '${lvl.name}' read-back failed: HTTP ${resp.status} ${text}`);
      }
      const got = (await resp.json()).d || {};
      const gotPerms = got.BasePermissions || {};
      const mismatches = [];
      if (got.Description !== lvl.description) {
        mismatches.push(`Description: sent ${JSON.stringify(lvl.description)}, stored ${JSON.stringify(got.Description)}`);
      }
      if (String(gotPerms.High) !== String(lvl.base_permissions.high)) {
        mismatches.push(`BasePermissions.High: sent ${lvl.base_permissions.high}, stored ${gotPerms.High}`);
      }
      if (String(gotPerms.Low) !== String(lvl.base_permissions.low)) {
        mismatches.push(`BasePermissions.Low: sent ${lvl.base_permissions.low}, stored ${gotPerms.Low}`);
      }
      if (mismatches.length) {
        throw new Error(
          `Permission level '${lvl.name}' did not store what was written. The request was accepted, `
          + `so this is a silent divergence rather than an error the tenant reported. `
          + mismatches.join('; '));
      }
    }

    // Decision shape: { kind: 'create'|'adopt'|'refuse', object: 'level'|'group', name, reason?, ...state }.
    // A refusal is returned as data, not thrown, so a later caller can act on
    // every survey before any write happens. A genuine failure (unreadable
    // response, enumeration error) still throws.
    async function surveyLevel(lvl) {
      const existingLevels = await probeLevelExistence(lvl.name);
      if (existingLevels.length === 0) {
        return { kind: 'create', object: 'level', name: lvl.name, lvl };
      }
      const existingId = existingLevels[0].Id;
      const existingDescription = typeof existingLevels[0].Description === 'string'
        ? existingLevels[0].Description
        : '';
      // #224. A role definition is SITE-SCOPED: adopting one this tool
      // did not create would overwrite its bitmap for every list it is
      // already assigned on, including lists this deploy never reads.
      // MARKER ONLY, deliberately, and a usage count never clears this
      // gate: `_acls.js.j2` assigns every level at LIST scope, and only
      // web-scope usage can be measured
      // (access.role-def.web-assignments-enumerable), so a web-scope zero
      // does not mean the level is unused.
      if (typeof lvl.expected_marker !== 'string' || lvl.expected_marker === '') {
        return {
          kind: 'refuse',
          object: 'level',
          name: lvl.name,
          reason: `SCHEMA.permission_levels['${lvl.name}'].expected_marker is missing or empty; refusing to adopt any level against it.`,
        };
      }
      if (existingDescription.indexOf(lvl.expected_marker) === -1) {
        // MARKER ONLY, deliberately. A usage count cannot clear this gate
        // because usage cannot be measured completely: assignments live at
        // LIST scope and only web scope was measured.
        const atWebScope = await countWebAssignmentsUsing(existingId);
        return {
          kind: 'refuse',
          object: 'level',
          name: lvl.name,
          reason: `Permission level '${lvl.name}' already exists and carries no '${lvl.expected_marker}' marker, `
            + `so it was not created by this declaration. A permission level is site-wide, and reconciling it `
            + `would change what it grants everywhere it is assigned, including lists this deploy does not `
            + `manage and never reads. It is used by ${atWebScope} role assignment(s) AT WEB SCOPE; `
            + `assignments on individual lists are not counted, so treat that as a floor rather than a total. `
            + `Nothing has been written to this level. Rename the level in your mapping so this deploy creates `
            + `its own.`,
        };
      }
      return { kind: 'adopt', object: 'level', name: lvl.name, lvl, existingId };
    }

    async function applyLevelDecision(decision) {
      const lvl = decision.lvl;
      if (decision.kind === 'create') {
        log('INFO', `Creating permission level '${lvl.name}'...`);
        const createResp = await postJson(apiUrl('web/roledefinitions'), {
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
        let newLevelId = createResp?.d?.Id;
        if (!Number.isInteger(newLevelId)) {
          // The create response carried no Id. Resolve it by name through
          // the same $filter probe rather than skip verification silently.
          // test/manual/role-definition-probe.js hit exactly this case and
          // carries the same fallback.
          const resolved = await probeLevelExistence(lvl.name);
          if (resolved.length !== 1 || !Number.isInteger(resolved[0].Id)) {
            throw new Error(`Permission level '${lvl.name}' was created but its Id could not be resolved for verification`);
          }
          newLevelId = resolved[0].Id;
          log('INFO', `Create returned no Id for '${lvl.name}'; resolved it by name to verify it.`);
        }
        await verifyLevelSettings(lvl, newLevelId);
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
        await verifyLevelSettings(lvl, decision.existingId);
        log('INFO', `Permission level '${lvl.name}' already exists; declared permissions reconciled.`);
      }
    }

    // Every object below (level or group) is surveyed before ANY of them is
    // applied. decisions collects only the decisions that CAN be applied
    // ('create'/'adopt'); a 'refuse' is turned into a thrown error right
    // here, on the same per-object catch a genuine survey failure already
    // used, so both land in summary.errors identically and the gate further
    // down treats them alike.
    // === Renames in place, before any survey ===
    // A level or group found under a previous name carrying that name's own
    // marker, with the current name absent, is retitled by id and read
    // back. Every rename is planned read-only first, and one refusal
    // anywhere aborts before any of them is written.
    const verbose = { headers: { 'Accept': 'application/json;odata=verbose' } };
    const principalRenames = [];
    // Counted apart from summary.errors: a refused phase digest is already
    // recorded above, belongs to the phase's own gate, and must not read
    // as a rename refusal.
    let renameFailures = 0;
    if (summary.errors.length === 0) {
      const refusals = [];
      const decide = (label, current, currentExists, found) => {
        const names = found.map((f) => `'${f.name}'`).join(', ');
        if (found.length === 0) return null;
        if (currentExists) {
          return `${label} '${current}' exists and so does its previous name ${names}; deploy cannot tell a rename from a collision. Remove or retitle one of them by hand.`;
        }
        if (found.length > 1) {
          return `more than one previous name of ${label} '${current}' exists (${names}); deploy cannot choose which to rename. Remove or retitle all but one by hand.`;
        }
        if (!found[0].carries) {
          return `${label} '${found[0].name}' exists but does not carry the exact provenance marker for its previous name ("${found[0].marker}"). Deploy will not adopt or rename it; restore that marker only if this tool created it.`;
        }
        return null;
      };
      const carries = (description, marker) => typeof description === 'string' && marker.length > 0 && description.indexOf(marker) !== -1;
      try {
        for (const lvl of SCHEMA.permission_levels) {
          if (!(lvl.previous_names || []).length) continue;
          const found = [];
          for (const previous of lvl.previous_names) {
            for (const row of await probeLevelExistence(previous.name)) {
              found.push({ name: previous.name, marker: previous.expected_marker, id: row.Id, carries: carries(row.Description, previous.expected_marker) });
            }
          }
          if (found.length === 0) continue;
          const currentExists = (await probeLevelExistence(lvl.name)).length > 0;
          const refusal = decide('permission level', lvl.name, currentExists, found);
          if (refusal) refusals.push(refusal);
          else principalRenames.push({ object: 'level', from: found[0].name, to: lvl.name, id: found[0].id, marker: found[0].marker, description: lvl.description });
        }
        if (SCHEMA.groups.some((g) => (g.previous_names || []).length)) {
          // One enumeration with descriptions, so the marker check costs no
          // probe per previous name.
          const r = await fetchWithRetry(apiUrl('web/sitegroups?$select=Id,Title,Description&$top=5000'), verbose);
          if (!r.ok) throw new Error(`site group enumeration for renames failed: HTTP ${r.status} ${spError(await r.text())}`);
          const rows = (((await r.json()) || {}).d || {}).results || [];
          const byName = (name) => rows.filter((g) => nameKey(g.Title) === nameKey(name));
          for (const grp of SCHEMA.groups) {
            if (!(grp.previous_names || []).length) continue;
            const found = [];
            for (const previous of grp.previous_names) {
              for (const row of byName(previous.name)) {
                found.push({ name: previous.name, marker: previous.expected_marker, id: row.Id, carries: carries(row.Description, previous.expected_marker) });
              }
            }
            if (found.length === 0) continue;
            const refusal = decide('site group', grp.name, byName(grp.name).length > 0, found);
            if (refusal) refusals.push(refusal);
            else principalRenames.push({ object: 'group', from: found[0].name, to: grp.name, id: found[0].id, marker: found[0].marker, description: grp.description });
          }
        }
      } catch (err) {
        refusals.push(`rename planning failed: ${err.message}`);
      }
      for (const reason of refusals) {
        log('ERROR', `Phase 1.4 rename: ${reason}`);
        summary.errors.push({ phase: '1.4', error: reason });
        renameFailures += 1;
      }
      if (refusals.length === 0) {
        for (const plan of principalRenames) {
          const label = plan.object === 'level' ? 'permission level' : 'site group';
          const nameKeyOf = plan.object === 'level' ? 'Name' : 'Title';
          // Two literal shapes rather than one interpolated path, so the
          // endpoint inventory in test_template_lint.py can see both.
          const renameUrl = (q = '') => (plan.object === 'level'
            ? apiUrl(`web/roledefinitions(${plan.id})${q}`)
            : apiUrl(`web/sitegroups(${plan.id})${q}`));
          try {
            // Re-read at write time: the plan is not authority over an object
            // something else may have touched since.
            const before = await fetchWithRetry(renameUrl(`?$select=Id,${nameKeyOf},Description`), verbose);
            if (!before.ok) throw new Error(`could not re-read ${label} '${plan.from}' before the rename: HTTP ${before.status}`);
            const held = (((await before.json()) || {}).d || {});
            if (nameKey(held[nameKeyOf]) !== nameKey(plan.from) || !carries(held.Description, plan.marker)) {
              throw new Error(`${label} '${plan.from}' no longer carries the marker for its previous name, or is no longer the object the plan read; nothing was renamed.`);
            }
            const digest = await getDigest();
            const body = plan.object === 'level'
              ? { __metadata: { type: 'SP.RoleDefinition' }, Name: plan.to, Description: plan.description }
              : { __metadata: { type: 'SP.Group' }, Title: plan.to, Description: plan.description };
            const merged = await fetchWithRetry(renameUrl(), {
              method: 'POST',
              headers: spHeaders(digest, { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' }),
              body: JSON.stringify(body),
            });
            if (!merged.ok) throw new Error(`rename MERGE failed: HTTP ${merged.status} ${spError(await merged.text())}`);
            const after = await fetchWithRetry(renameUrl(`?$select=Id,${nameKeyOf},Description`), verbose);
            if (!after.ok) throw new Error(`readback after the rename failed: HTTP ${after.status}`);
            const back = (((await after.json()) || {}).d || {});
            if (back[nameKeyOf] !== plan.to || back.Description !== plan.description) {
              throw new Error(`${label} '${plan.from}' read back as '${back[nameKeyOf]}' with Description ${JSON.stringify(back.Description)} after writing '${plan.to}'; the rename did not take.`);
            }
            (plan.object === 'level' ? summary.levelsRenamed : summary.groupsRenamed).push({ from: plan.from, to: plan.to });
            logChange({ key: `${plan.object}: ${plan.from}`, kind: 'rename',
              target: plan.from, oldValue: plan.from, newValue: plan.to });
            log('INFO', `Renamed ${label} '${plan.from}' to '${plan.to}' in place (read back by id).`);
          } catch (err) {
            log('ERROR', `Phase 1.4 rename '${plan.from}' -> '${plan.to}': ${err.message}`);
            summary.errors.push({ phase: '1.4', error: err.message });
            renameFailures += 1;
            break;
          }
        }
      }
    }
    if (renameFailures > 0) {
      log('ERROR', 'Phase 1.4 rename planning or rename failed; aborting before any level or group is surveyed.');
      return { ...summary, aborted: 'phase-0-rename-errors' };
    }

    const decisions = [];

    for (const lvl of SCHEMA.permission_levels) {
      try {
        const decision = await surveyLevel(lvl);
        if (decision.kind === 'refuse') throw new Error(decision.reason);
        decisions.push(decision);
      } catch (err) {
        log('ERROR', `Phase 1.4 permission level '${lvl.name}': ${err.message}`);
        summary.errors.push({ phase: '1.4', permissionLevel: lvl.name, error: err.message });
      }
    }

    // Which groups exist, from ONE enumeration. A by-name GET for a group
    // that is not there answers 404, which the browser paints red and an
    // operator reads as a failure, and on a first deploy EVERY declared
    // group is that 404. Same treatment the list and view probes already
    // get: enumerate once, answer absence locally, keep a clean run clean.
    // Not fatal if refused; we fall back to probing, which is noisier and
    // still correct.
    let knownGroupNames = null;
    {
      const r = await fetchWithRetry(apiUrl('web/sitegroups?$select=Title&$top=5000'), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (r.ok) {
        const j = await r.json();
        // nameSet/hasName: SharePoint group names are unique and resolved
        // case-insensitively, so an existing 'or list administrators'
        // must not read as absent against a declared 'OR List
        // Administrators'; that turns an adoptable group into a create
        // that fails on a name collision.
        knownGroupNames = nameSet(
          ((j && j.d && j.d.results) || []).map((g) => g.Title).filter((t) => typeof t === 'string'),
        );
      }
    }

    // Enumerate every page. A group larger than one page would otherwise read
    // as smaller than it is, and both callers fail closed on the count.
    async function countGroupMembers(groupName) {
      let total = 0;
      let membersUrl = apiUrl(`web/sitegroups/getbyname('${odataName(groupName)}')/users?$select=Id&$top=5000`);
      while (membersUrl) {
        const membersResp = await fetchWithRetry(membersUrl, {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
        if (!membersResp.ok) {
          const text = await membersResp.text();
          throw new Error(`Group '${groupName}' membership enumeration failed: HTTP ${membersResp.status} ${text}`);
        }
        const membersJson = await membersResp.json();
        if (!membersJson.d || !Array.isArray(membersJson.d.results)) {
          throw new Error(`Group '${groupName}' membership enumeration returned an invalid response`);
        }
        total += membersJson.d.results.length;
        membersUrl = membersJson.d.__next || null;
      }
      return total;
    }

    // MEASURED by test/manual/group-description-probe.js, 2026-08-13 and
    // 2026-08-14: Description round-trips byte-identically, so this compare
    // is exact rather than fuzzy. The $select projection itself is not
    // measured; every question in that probe read the group back
    // unprojected. It is inferred from the owner-verification calls below,
    // which already project a site group with $select=Id,Title,PrincipalType.
    // Id is unused here, kept only so this GET's URL shape matches theirs
    // exactly, which is what test_a_first_deploy_probes_no_absent_group_or_field_by_name
    // excludes as "already resolved, not a probe for something absent."
    async function verifyGroupSettings(grp) {
      const select = 'Id,Description,AllowMembersEditMembership,AllowRequestToJoinLeave'
        + ',AutoAcceptRequestToJoinLeave,OnlyAllowMembersViewMembership';
      const resp = await fetchWithRetry(
        apiUrl(`web/sitegroups/getbyname('${odataName(grp.name)}')?$select=${select}`),
        { headers: { 'Accept': 'application/json;odata=verbose' } },
      );
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(`Group '${grp.name}' read-back failed: HTTP ${resp.status} ${text}`);
      }
      const got = (await resp.json()).d || {};
      // The tenant forces auto-accept off when requests-to-join is off,
      // measured against a contradictory pair sent deliberately
      // (test/manual/group-description-probe.js,
      // text.group-desc.membership-flags-merge, then confirmed
      // non-ambiguous by text.group-desc.autoaccept-prerequisite,
      // 2026-08-13/14), so the expected value is the coerced one, not
      // the one sent.
      const expectedAutoAccept = grp.allow_request_to_join_leave
        ? grp.auto_accept_request_to_join_leave
        : false;
      const mismatches = [];
      if (got.Description !== grp.description) {
        mismatches.push(`Description: sent ${JSON.stringify(grp.description)}, stored ${JSON.stringify(got.Description)}`);
      }
      if (got.AllowMembersEditMembership !== grp.allow_members_edit_membership) {
        mismatches.push(`AllowMembersEditMembership: sent ${grp.allow_members_edit_membership}, stored ${got.AllowMembersEditMembership}`);
      }
      if (got.AllowRequestToJoinLeave !== grp.allow_request_to_join_leave) {
        mismatches.push(`AllowRequestToJoinLeave: sent ${grp.allow_request_to_join_leave}, stored ${got.AllowRequestToJoinLeave}`);
      }
      if (got.AutoAcceptRequestToJoinLeave !== expectedAutoAccept) {
        mismatches.push(`AutoAcceptRequestToJoinLeave: expected ${expectedAutoAccept}, stored ${got.AutoAcceptRequestToJoinLeave}`);
      }
      if (got.OnlyAllowMembersViewMembership !== grp.only_allow_members_view_membership) {
        mismatches.push(`OnlyAllowMembersViewMembership: sent ${grp.only_allow_members_view_membership}, stored ${got.OnlyAllowMembersViewMembership}`);
      }
      if (mismatches.length) {
        throw new Error(
          `Site group '${grp.name}' did not store what was written. The request was accepted, `
          + `so this is a silent divergence rather than an error the tenant reported. `
          + mismatches.join('; '));
      }
    }

    // Owner verification, with automated correction. Plain REST cannot MERGE
    // Group.Owner (read-only through that surface), but the documented CSOM
    // protocol (MS-CSOM ProcessQuery, the same mechanism PnP's Set-PnPGroup
    // uses) can set it. Both the target and the governed group must already
    // exist, so this reads on an adopt decision (survey) and after the
    // create (apply); either way, by the time it runs the group is there.
    async function resolveGroupOwner(grp) {
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
      const ownerMismatch = currentOwner.Id !== targetOwner.Id
        || currentOwner.PrincipalType !== targetOwner.PrincipalType;
      return { targetOwner, governedGroup, currentOwner, ownerMismatch };
    }

    // The correction itself is a write (CSOM ProcessQuery, then a re-verify
    // through the documented read-only /owner resource), so unlike the read
    // above, this always belongs to the apply, never the survey.
    async function correctGroupOwner(grp, ownerState) {
      const { targetOwner, governedGroup, currentOwner, ownerMismatch } = ownerState;
      if (!ownerMismatch) {
        log('INFO', `Site group '${grp.name}' owner verified as '${targetOwner.Title}'.`);
        return;
      }
      let ownerCorrected = false;
      // Automated correction only targets site-group owners (type 8): every
      // declared owner_group resolves to a site group.
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
            // Re-verify through the same documented read-only probe: the
            // CSOM response alone is not trusted as success evidence.
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
    }

    // Optional clean-provision/activation gate. Membership remains an
    // operator-owned concern: enumerate every page and fail closed rather
    // than silently removing an unexpected user or directory group. Read-only,
    // so like the owner resolve above it runs on an adopt decision (survey)
    // and after the create (apply).
    async function ensureGroupEmptyIfRequired(grp) {
      if (!grp.require_empty_at_deploy) return;
      const memberCount = await countGroupMembers(grp.name);
      if (memberCount > 0) {
        throw new Error(`Group '${grp.name}' requires empty membership at deploy, but contains ${memberCount} member(s); remove them or use a mapping that does not declare the clean-provision gate`);
      }
    }

    // Decision shape: { kind: 'create'|'adopt'|'refuse', object: 'level'|'group', name, reason?, ...state }.
    // Unlike surveyLevel, an adopt decision here also carries ownerState and
    // has already run the empty-membership gate: both need the group to
    // exist, which on an adopt decision it already does. A create decision
    // does neither; owner resolution and the empty check 404 for a group
    // that is not there yet, so they are owed to applyGroupDecision, after
    // the create.
    async function surveyGroup(grp, decidedCreates) {
      // decidedCreates covers a name this same pass already decided to
      // create, which the one-time enumeration in knownGroupNames cannot
      // see. SharePoint resolves site group names case-insensitively, so
      // two declarations differing only in case are ONE group to the
      // tenant: the group named by decidedCreates does not exist yet, so a
      // probe for it still answers 404 and would survey a SECOND 'create'
      // decision, colliding with the first once both are applied. Refuse
      // here instead, before any probe or write.
      if (hasName(decidedCreates, grp.name)) {
        return {
          kind: 'refuse',
          object: 'group',
          name: grp.name,
          reason: `Site group '${grp.name}' matches a name this same declaration already decided to create, differing only in case. SharePoint resolves site group names case-insensitively, so these are one group to the tenant; the second create would collide with the first once applied. Nothing has been written for either. Rename one of them so this deploy creates only one group.`,
        };
      }
      // null status means "known absent without asking".
      const isKnown = knownGroupNames && hasName(knownGroupNames, grp.name);
      const checkResp = knownGroupNames && !isKnown
        ? { status: 404, ok: false }
        : await fetchWithRetry(apiUrl(`web/sitegroups/getbyname('${odataName(grp.name)}')`), {
          headers: { 'Accept': 'application/json;odata=verbose' },
        });
      if (checkResp.status === 404) {
        return { kind: 'create', object: 'group', name: grp.name, grp };
      }
      if (!checkResp.ok) {
        throw new Error(`Probe for site group '${grp.name}' failed: HTTP ${checkResp.status}`);
      }

      // #209. This branch adopts a group by NAME and the ACL phase then
      // grants it whatever the mapping declares, which for the
      // administrators group is Full Control on every list. Adopt only a
      // group this tool created, or one holding nobody.
      //
      // PROVENANCE, NOT AUTHENTICATION, 2026-08-14: the marker is evidence
      // this tool wrote the group, not a secret. Anyone who can edit a
      // site group's Description can satisfy it, and editing a site
      // group already needs site-owner rights on the target site, which
      // this gate assumes rather than re-checks.
      //
      // EXACT MARKER, NOT A SHARED PREFIX. Every family's marker starts
      // with the same "Provisioned by dbml-sharepoint" text, so testing
      // that shared text let a group ANY family stamped pass the gate
      // for EVERY family. Comparing the exact marker this declaration
      // expects (grp.expected_marker) closes that: a group family B
      // declares cannot be satisfied by a marker family A left on it.
      // The tool-owned groups still work here, because every family
      // computes the same expected_marker for them.
      //
      // Empty expected_marker would make indexOf('') return 0 for every
      // description below, adopting every group unmarked. undefined
      // already fails closed there; only the empty string is dangerous.
      // jsgen always sets a value, so this only matters for a
      // hand-edited bundle.
      if (typeof grp.expected_marker !== 'string' || grp.expected_marker === '') {
        return {
          kind: 'refuse',
          object: 'group',
          name: grp.name,
          reason: `Site group '${grp.name}' has no expected_marker; refusing to adopt any group against it.`,
        };
      }
      const existingJson = await checkResp.json();
      const existingDescription = (existingJson.d && typeof existingJson.d.Description === 'string')
        ? existingJson.d.Description
        : '';
      // SUBSTRING SEARCH, NOT A PREFIX TEST. group_description() appends
      // the marker AFTER any declared text, so a composed description
      // does not START with it. indexOf finds the marker anywhere in the
      // string; changing this to startsWith would refuse every group
      // that also carries a declared description.
      if (existingDescription.indexOf(grp.expected_marker) === -1) {
        const memberCount = await countGroupMembers(grp.name);
        if (memberCount > 0) {
          return {
            kind: 'refuse',
            object: 'group',
            name: grp.name,
            reason: `Site group '${grp.name}' already exists, carries no '${grp.expected_marker}' `
              + `marker, and holds ${memberCount} member(s). It was not created by this tool, and `
              + `adopting it would grant those members the access this family declares for the group. `
              + `Nothing has been written to this group. Either empty the group, or rename it so `
              + `this deploy creates its own.`,
          };
        }
      }

      // ensureGroupEmptyIfRequired only reads the governed group, already
      // proven to exist on this path, so it is always safe here. Owner
      // resolution reads a SECOND group: grp.owner_group can name a custom
      // group this same declaration decided to create, and every survey in
      // this phase runs before every create, so that group may not exist on
      // the site yet. Resolving it now would 404 and abort the whole phase
      // for a group this deploy is about to create anyway: the same class
      // as decidedCreates above, one level deeper. Resolve now only when
      // the owner group is a built-in or is already known to exist from
      // the one-time enumeration; otherwise defer to
      // applyGroupDecision, which runs after every create in this phase has
      // applied. Do not "tidy" this back to an unconditional resolve.
      const ownerGroupKnownToExist = BUILTIN_OWNER_GROUPS.has(grp.owner_group)
        || (knownGroupNames !== null && hasName(knownGroupNames, grp.owner_group));
      const ownerState = ownerGroupKnownToExist ? await resolveGroupOwner(grp) : null;
      await ensureGroupEmptyIfRequired(grp);

      return { kind: 'adopt', object: 'group', name: grp.name, grp, ownerState };
    }

    async function applyGroupDecision(decision) {
      const grp = decision.grp;
      if (decision.kind === 'create') {
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
        await verifyGroupSettings(grp);

        // Owed to here from the survey: both need the group to exist, and
        // before this line it did not.
        const ownerState = await resolveGroupOwner(grp);
        await correctGroupOwner(grp, ownerState);
        await ensureGroupEmptyIfRequired(grp);
        if (grp.require_empty_at_deploy) {
          log('INFO', `Site group '${grp.name}' is empty as required for deployment.`);
        }
      } else {
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
        await verifyGroupSettings(grp);

        // decision.ownerState is null when the survey deferred the resolve
        // (see surveyGroup): grp.owner_group named a custom group not yet
        // known to exist, most likely because this same pass decided to
        // create it. Every create in the phase has applied by the time this
        // line runs, so the resolve is safe here. When ownerState WAS read
        // by the survey, it was read before every other object in this
        // phase was written, so on the no-mismatch path below the 'owner
        // verified' log reports evidence that may have aged by the time
        // this line runs. The mismatch path is unaffected either way: it
        // re-reads the owner after its own CSOM write, rather than trusting
        // this state.
        const ownerState = decision.ownerState || await resolveGroupOwner(grp);
        await correctGroupOwner(grp, ownerState);
        if (grp.require_empty_at_deploy) {
          log('INFO', `Site group '${grp.name}' is empty as required for deployment.`);
        }
      }
    }

    // decidedCreates: the write-side knownGroupNames.add() this replaces
    // (formerly here, after a create) mutated a snapshot a later iteration
    // read. All-surveys-before-all-creates would destroy that, so instead
    // each iteration folds its own 'create' decision into this set before
    // moving on, and surveyGroup consults it to refuse a later case-variant
    // declaration outright. The build already refuses two declarations
    // differing only in case within one mapping, so this only protects a
    // mapping built before that rule existed.
    const decidedCreates = new Set();
    for (const grp of SCHEMA.groups) {
      try {
        const decision = await surveyGroup(grp, decidedCreates);
        if (decision.kind === 'create') decidedCreates.add(nameKey(grp.name));
        if (decision.kind === 'refuse') throw new Error(decision.reason);
        decisions.push(decision);
      } catch (err) {
        log('ERROR', `Phase 1.4 site group '${grp.name}': ${err.message}`);
        summary.errors.push({ phase: '1.4', group: grp.name, error: err.message });
      }
    }

    // The decision table (#32): every object BOTH loops above decided to
    // create or adopt, printed before any of them is applied. A refusal
    // already logged its own ERROR line in the survey loop that found it,
    // so this table reads the same whether the run goes on to apply or
    // aborts on the gate below -- a clean run shows create/adopt for
    // everything, a refusing run shows this table for whatever DID survey
    // successfully, interleaved with the refusals that already printed.
    // This phase decides no list and no ACL, so neither appears here.
    if (decisions.length > 0) {
      log('INFO', `Phase 1.4 decisions (nothing applied yet):`);
      for (const decision of decisions) {
        const label = decision.object === 'level' ? 'permission level' : 'site group';
        const verb = decision.kind === 'create' ? 'create' : 'adopt';
        log('INFO', `  ${verb} ${label} '${decision.name}'.`);
      }
    }

    // Gate: apply only if every survey above succeeded and nothing refused.
    // A refused or unsurveyable object is not a decision to proceed on, and
    // this is what stops one refusal from letting every OTHER object still
    // get written before the run reports it.
    //
    // This buys atomicity of DECISION, not of effect. SharePoint offers no
    // transaction: the site can still change between this gate and the
    // apply loop below, and an apply can still fail part way through even
    // when every survey passed. A refusal here is also not a promise the
    // site stays untouched by everything this run does afterward;
    // correctGroupOwner's manual-action refusal happens during apply and is
    // unsurveyable by construction.
    if (summary.errors.length === 0) {
      // digest0 was captured near the top of this phase, before every level
      // probe, the group enumeration, and every adopt-path owner read and
      // membership count -- survey work that did not exist between the
      // fetch and the first write before this phase split decision from
      // effect. FormDigestValue expires after ~30 minutes (_seeds.js.j2,
      // 'Fresh digest per seed'), so the apply pass takes its own fresh one
      // here, before its first write, rather than trusting whatever the
      // survey left behind.
      digest0 = await phaseDigest();
    }
    // Re-tested after that fetch: a refused digest is recorded rather than thrown, and there is nothing to write with.
    if (summary.errors.length === 0) {
      for (const decision of decisions) {
        try {
          if (decision.object === 'level') {
            await applyLevelDecision(decision);
          } else {
            await applyGroupDecision(decision);
          }
        } catch (err) {
          // Continue after object errors, but a digest failure makes every later write unsafe.
          const label = decision.object === 'level' ? 'permission level' : 'site group';
          log('ERROR', `Phase 1.4 ${label} '${decision.name}': ${err.message}`);
          if (decision.object === 'level') {
            summary.errors.push({ phase: '1.4', permissionLevel: decision.name, error: err.message });
          } else {
            summary.errors.push({ phase: '1.4', group: decision.name, error: err.message });
          }
          if (err && err.digestFailure) break;
        }
      }
    }
  }

  // Permission-level or group failures make every later ACL assertion
  // untrustworthy. Stop before creating content-bearing lists or seed rows.
  if (summary.errors.length > 0) {
    log('ERROR', 'Phase 1.4 security reconciliation failed; aborting before list creation.');
    return { ...summary, aborted: 'phase-0-security-errors' };
  }

  markPhase('Phase 1.5: operator self-enrolment');
  // === Operator self-enrolment (groups[].enroll_operator_during_deploy) ===
  // Some mappings route all list administration through an empty-by-default
  // admin group (Owners hold only Contribute on the lists). Later phases
  // (field reconciliation, indexes, ACL work) then need the operator to hold
  // that group's grants, so the script enrols the operator for the duration
  // of the run and removes them at the end. An operator who was ALREADY a
  // member is left untouched. Only principals who can already manage the
  // group (its Site-Owners owner) can benefit; this adds no new authority.
  log('INFO', 'Starting Phase 1.5: operator self-enrolment.');
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
        summary.errors.push({ phase: '1.5', group: grp.name, error: err.message });
      }
    }
  }
  if (summary.errors.length > 0) {
    log('ERROR', 'Operator self-enrolment failed; aborting before list creation.');
    return { ...summary, aborted: 'operator-enrolment-errors' };
  }
  markPhase('Phase 1.6: enterprise reader enrolment');
  markPhase('Phase 1.7: deployment run and change logs');
  // --no-sidecars with no central log named: no run log, no change log, no
  // external stamps. The shim logChange still buffers whatever renames
  // raise, and nothing drains it: a build that declines every sink records
  // nothing.
  markPhase('Phase 1.8: maintenance unseal');
  // === Maintenance unseal (declared-seal columns) ===
  // Sealed columns reject UI schema edits even for site admins; the ONLY
  // legitimate maintenance path is this script. Unseal declared fields so
  // the run's write phases work unchanged; Phase 4.1 re-seals and
  // verifies after every field write is done.
  log('INFO', 'Starting Phase 1.8: maintenance unseal.');
  invalidateFieldShapes();  // probes reflect phase-start state
  {
    const sealDeclared = [];
    for (const list of SCHEMA.lists) {
      for (const col of list.fields_phase1) {
        if (col.seal) sealDeclared.push([list.title, col]);
      }
    }
    for (const lookup of SCHEMA.phase2_lookups) {
      if (lookup.field.seal) sealDeclared.push([lookup.list, lookup.field]);
    }
    // The built-in Title is not a declared column, so it was never in this
    // set, and Phase 1 writes list.title_patch to it. A Title sealed by
    // anything other than this tool therefore made the run un-completable
    // and un-repairable: the write failed, and the only maintenance path
    // that can unseal walked declared columns only. Probed unconditionally
    // (the loop below writes ONLY if it finds Sealed true), so a normal
    // site pays one read and nothing changes.
    for (const list of SCHEMA.lists) {
      if (list.title_patch) sealDeclared.push([list.title, syntheticTitleField(list)]);
    }
    if (sealDeclared.length > 0) {
      // Preflight ownership can change before this first list mutation. Re-read
      // every list this phase may touch and gate the whole unseal batch before
      // opening one field. An absent list is a clean first-provision target,
      // so the survey tolerates absence here; the identities it does capture
      // are carried into the write lane below, which refuses a list that has
      // become a different object since.
      const unsealOwned = await surveyOwnedListsForWrites(
        sealDeclared.map(([listTitle]) => listTitle),
        '1.8', 'Maintenance ownership recheck', true,
      );
      if (!unsealOwned) {
        log('ERROR', 'Maintenance ownership recheck failed; aborting before any field is unsealed or structural phase begins.');
        return { ...summary, aborted: 'maintenance-ownership-errors' };
      }
      log('INFO', `Maintenance unseal: checking ${sealDeclared.length} declared-seal column(s).`);
      let unsealedCount = 0;
      // One lane per list: same-list field MERGEs race into save conflicts;
      // different lists unseal concurrently.
      const errorsBeforeUnseal = summary.errors.length;
      await mapLanes(sealDeclared, ([listTitle]) => listTitle, async ([listTitle, field]) => {
        try {
          const list = SCHEMA.lists.find(candidate => candidate.title === listTitle);
          if (!list) throw new Error(`No declaration found for list '${listTitle}'`);
          // A list the survey found is required to still be the same object;
          // one it did not find may still be absent, since this phase runs
          // before the structural phases create it.
          const surveyedId = unsealOwned.get(listTitle);
          let currentList;
          if (surveyedId == null) {
            currentList = await readListShape(listTitle, true);
            if (!currentList) return;
            assertListAdoptable(list, currentList);
          } else {
            currentList = await ownedListIdentity(
              listTitle, surveyedId, 'before maintenance unseal',
            );
          }
          const shape = await readFieldShape(listTitle, field.title, field, true);
          // A partial first provision may not have created this deferred
          // lookup yet. With no live field there is nothing to unseal, and its
          // target is allowed to remain absent until the structural phases.
          if (!shape) return;
          let targetGuid = null;
          if (field.target_list) {
            const target = SCHEMA.lists.find(candidate => candidate.title === field.target_list);
            if (!target) throw new Error(`No declaration found for lookup target '${field.target_list}'`);
            const targetShape = await readListShape(target.title, true);
            if (!targetShape) throw new Error(`Lookup target '${target.title}' disappeared before maintenance unseal`);
            assertListAdoptable(target, targetShape);
            targetGuid = targetShape.Id;
          }
          await assertFieldImmutableShape(listTitle, field, shape, targetGuid);
          if (shape.Sealed) {
            const unsealDigest = await getDigest();
            // Record before the request. If SharePoint commits the MERGE but
            // the response is lost, exit cleanup must still re-seal it. A
            // redundant Sealed=true write is safe when the MERGE never landed.
            fieldsUnsealedForRun.set(
              `${listTitle}\u0000${field.title}`,
              [listTitle, field.title, currentList.Id, shape.Id],
            );
            await patchFieldById(currentList.Id, shape.Id, { __metadata: { type: 'SP.Field' }, Sealed: false }, unsealDigest);
            unsealedCount += 1;
          }
        } catch (err) {
          log('ERROR', `Maintenance unseal '${listTitle}.${field.title}': ${err.message}`);
          summary.errors.push({ phase: '1.8', list: listTitle, column: field.title, error: err.message });
        }
      }, 4);
      if (summary.errors.length > errorsBeforeUnseal) {
        log('ERROR', 'Maintenance unseal failed; aborting before any structural phase begins. Exit cleanup will re-seal fields this run may have opened.');
        return { ...summary, aborted: 'maintenance-unseal-errors' };
      }
      log('INFO', `Maintenance unseal complete (${unsealedCount} column(s) unsealed for this run).`);
    }
  }
  markPhase('Phase 2.1: list creation');
  // === Phase 2.1: lists + non-lookup columns + same-site lookups ===
  log('INFO', 'Group 2: STRUCTURE');
  log('INFO', `Starting Phase 2.1: list creation. Release ${RELEASE_TAG}.`);
  invalidateFieldShapes();  // probes reflect phase-start state
  let digest = await getDigest();
  const listGuids = Object.create(null);
  const earlyIsolationLists = new Set(SCHEMA.list_assignments
    .filter(la => la.break_inheritance && la.reconcile_mode === 'exact')
    .map(la => la.list));

  // Wave 1 is sequential, in dependency order: list existence, declared
  // list shape, GUID capture, early ACL isolation. Sequential because
  // wave 2's same-site lookup fields need every target list's GUID.
  const fieldWork = [];
  const errorsBeforeWaveOne = summary.errors.length;
  for (const list of SCHEMA.lists) {
    try {
      // Refresh the digest per list: a long Phase 2.1 (hundreds of field POSTs)
      // can outlive a single FormDigestValue (~30 min), so re-fetch per list
      // rather than reuse the one fetched before the loop.
      digest = await getDigest();
      let createdThisRun = false;
      let listShape = await readListShape(list.title);
      if (listShape) {
        // The read-only preflight already rejected immutable template drift;
        // re-read here to close the preflight/write race and then reconcile
        // only the declared mutable list settings.
        assertListAdoptable(list, listShape);
        log('INFO', `List '${list.title}' is owned; validating and reconciling declared shape.`);
        summary.listsSkipped.push(list.title);
      } else {
        log('INFO', `Creating list '${list.title}' (${list.kind})...`);
        const body = {
          __metadata: { type: 'SP.List' },
          Title: list.title,
          BaseTemplate: list.base_template,
          // The create request carries ownership evidence from the first
          // write. ReconcileListShape reads it back before any field work.
          // Existing lists reach that function only after proving they already
          // carry the exact marker; ordinary deploy never manufactures it.
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
        invalidateListShapes();  // the enumeration no longer knows every list
        summary.listsCreated.push(list.title);
        logChange({ key: `list: ${list.title}`, kind: 'create', target: list.title,
          oldValue: '', newValue: `created by ${RELEASE_TAG}` });
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

  if (summary.errors.length > errorsBeforeWaveOne) {
    log('ERROR', 'Wave 1 list reconciliation failed; aborting before any field work.');
    return { ...summary, aborted: 'wave-1-schema-errors' };
  }

  // Wave 1 can be long enough for an earlier list's ownership to change while
  // later lists are reconciled. Re-survey every field-work list as one batch;
  // no field write starts unless all still carry exact ownership and shape.
  let fieldWaveOwnershipFailed = false;
  await mapLanes(fieldWork, list => list.title, async (list) => {
    try {
      const actual = await readListShape(list.title, true);
      if (!actual) throw new Error(`Declared list '${list.title}' disappeared before field work`);
      assertListAdoptable(list, actual);
      listGuids[list.title] = actual.Id;
    } catch (err) {
      fieldWaveOwnershipFailed = true;
      log('ERROR', `Field-wave ownership recheck '${list.title}': ${err.message}`);
      summary.errors.push({
        phase: '2.1', list: list.title, error: err.message,
      });
    }
  }, 4);
  if (fieldWaveOwnershipFailed) {
    log('ERROR', 'Field-wave ownership recheck failed; aborting before any field write.');
    return { ...summary, aborted: 'field-wave-ownership-errors' };
  }

  // Wave 2 is field provisioning, one lane per list: every target GUID now
  // exists, and concurrent schema writes to the SAME list race into save
  // conflicts while different lists are independent, so each list's fields
  // run sequentially inside a lane and the lanes run concurrently.
  //
  // Ownership loss inside the wave is phase-wide, not one field's business.
  // The per-field catch below records an error and moves to the next column,
  // which for a transient 403 is right and for a lost marker means writing on
  // past a KNOWN ownership loss, in this lane and in every other one still
  // running. So it is marked on the error, re-thrown past that catch, and
  // latched here where every lane can see it.
  let fieldWaveOwnershipLoss = null;
  const stopFieldWave = (listName, err) => {
    fieldWaveOwnershipLoss = fieldWaveOwnershipLoss
      || { list: listName, error: err.message };
    err.ownershipLoss = true;
    return err;
  };
  await mapLanes(fieldWork, (list) => list.title, async (list) => {
    try {
      // Called before every write in this lane, so the latch is what stops
      // the wave: a lane that has not failed itself stops at its next check.
      const assertLaneOwnership = async () => {
        if (fieldWaveOwnershipLoss) {
          throw stopFieldWave(list.title, new Error(
            `field wave stopped by ownership loss on '${fieldWaveOwnershipLoss.list}'`,
          ));
        }
        try {
          const owned = await assertDeclaredListOwnedNow(list.title);
          listGuids[list.title] = owned.Id;
        } catch (err) {
          throw stopFieldWave(list.title, err);
        }
      };
      await assertLaneOwnership();
      let laneDigest = await getDigest();
      for (const col of list.fields_phase1) {
        // Guard each field independently: one field's failure (a transient
        // 429/403, or a missing lookup target) must not abandon the list's
        // remaining columns and its Title patch. Existing fields are never
        // trusted by name alone: immutable identity is checked before safely
        // mutable declared settings are reconciled and read back.
        try {
          await assertLaneOwnership();
          laneDigest = await getDigest();
          const resolveTargetGuid = async () => {
            if (!col.target_list) return null;
            try {
              const targetOwned = await assertDeclaredListOwnedNow(col.target_list);
              listGuids[col.target_list] = targetOwned.Id;
              return targetOwned.Id;
            } catch (err) {
              // The target is written to as surely as the lane's own list:
              // its GUID becomes the LookupListId of every field created here.
              throw stopFieldWave(col.target_list, err);
            }
          };
          let targetGuid = await resolveTargetGuid();
          if (await reconcileDeclaredField(
            list.title, col, targetGuid, laneDigest, true,
          )) {
            summary.columnsSkipped += 1;
          } else {
            await assertLaneOwnership();
            targetGuid = await resolveTargetGuid();
            if (col.target_list) {
              // SharePoint rejects POSTing an SP.FieldLookup directly to
              // /fields ("Please use addfield to add a lookup field"), and
              // refuses AddField outright for a multi-value one. Both routes
              // live in createDeclaredLookupField; properties neither can
              // carry are MERGEd and read back by reconcileDeclaredField
              // immediately below.
              await createDeclaredLookupField(list.title, col, targetGuid, laneDigest);
            } else {
              await postJson(
                apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/fields`),
                col.body,
                laneDigest,
              );
            }
            invalidateFieldShapes();  // new field: next probe re-enumerates
            await assertLaneOwnership();
            targetGuid = await resolveTargetGuid();
            await reconcileDeclaredField(
              list.title, col, targetGuid, laneDigest, false,
            );
            summary.columnsCreated += 1;
          }
          // Projected dependent fields, created after the primary lookup
          // exists so its Id is known. Each is a read-only Lookup linked back
          // by FieldRef and created via createfieldasxml, because the FieldRef
          // linkage cannot be expressed through AddField. Read-only fields do
          // not drift, so they are checked for existence only. See
          // test/manual/projected-lookup-probe.js for the measured create shape.
          if (col.projections && col.projections.length) {
            laneDigest = await getDigest();
            const primaryShape = await readFieldShape(list.title, col.title, null, true);
            for (const proj of col.projections) {
              if (!(await readFieldShape(list.title, proj.name, null, true))) {
                await assertLaneOwnership();
                targetGuid = await resolveTargetGuid();
                laneDigest = await getDigest();
                const xml = `<Field Type="Lookup" DisplayName="${proj.display_title}" `
                  + `Name="${proj.name}" List="{${targetGuid}}" ShowField="${proj.show_field}" `
                  + `FieldRef="{${primaryShape.Id}}" ReadOnly="TRUE"/>`;
                await postJson(
                  apiUrl(`web/lists/getbytitle('${odataName(list.title)}')/fields/createfieldasxml`),
                  { parameters: { SchemaXml: xml, Options: 8 } },
                  laneDigest,
                );
                summary.columnsCreated += 1;
              }
              await verifyDependentField(list.title, proj.name, proj.show_field, primaryShape.Id, targetGuid);
            }
          }
        } catch (err) {
          // Recorded per field and carried on, EXCEPT for ownership loss:
          // that one leaves the lane, and the wave, without another write.
          if (err.ownershipLoss) throw err;
          log('ERROR', `Phase 2.1 field '${list.title}.${col.title}': ${err.message}`);
          summary.errors.push({
            phase: '2.1', list: list.title, column: col.title, error: err.message,
          });
        }
      }

      if (list.title_patch) {
        await assertLaneOwnership();
        await reconcileDeclaredField(
          list.title, syntheticTitleField(list), null, laneDigest, false,
        );
      }

      laneDigest = await getDigest();
      await assertLaneOwnership();
      await reconcileListValidation(list, laneDigest);
    } catch (err) {
      // One named phase error for the whole wave, recorded after mapLanes:
      // every lane stops on the same loss, and one per lane would report a
      // site-wide refusal as a list-by-list failure.
      if (err.ownershipLoss) return;
      log('ERROR', `Phase 2.1 '${list.title}': ${err.message}`);
      summary.errors.push({ phase: '2.1', list: list.title, error: err.message });
    }
  }, 4);

  if (fieldWaveOwnershipLoss) {
    log('ERROR', `Phase 2.1 lost ownership of '${fieldWaveOwnershipLoss.list}' mid-wave; aborting every lane before any further field write.`);
    summary.errors.push({
      phase: '2.1', list: fieldWaveOwnershipLoss.list,
      error: fieldWaveOwnershipLoss.error,
    });
    return { ...summary, aborted: 'field-wave-ownership-loss' };
  }

  if (summary.errors.length > 0) {
    log('ERROR', 'Phase 2.1 schema reconciliation failed; aborting before deferred lookups and ACL work.');
    return { ...summary, aborted: 'phase-1-schema-errors' };
  }
  markPhase('Phase 2.2: deferred lookups');
  // === Phase 2.2: deferred lookups ===
  log('INFO', 'Starting Phase 2.2: deferred lookups.');
  invalidateFieldShapes();  // probes reflect phase-start state
  digest = await getDigest();

  // listGuids is a title -> GUID map the field wave filled, and the field
  // wave is long enough for a list to lose its marker after being read into
  // it. Re-survey every deferred lookup's own list AND its target as one
  // batch, refresh the map from that read, and abort the whole batch before
  // any write if a single one no longer proves ownership.
  let deferredOwnershipFailed = false;
  const deferredOwnedLists = [...new Set(SCHEMA.phase2_lookups
    .flatMap(lookup => [lookup.list, lookup.target_list]))];
  await mapLanes(deferredOwnedLists, listName => listName, async (listName) => {
    try {
      const owned = await assertDeclaredListOwnedNow(listName);
      listGuids[listName] = owned.Id;
    } catch (err) {
      deferredOwnershipFailed = true;
      log('ERROR', `Deferred-lookup ownership recheck '${listName}': ${err.message}`);
      summary.errors.push({
        phase: '2.2', list: listName, error: err.message,
      });
    }
  }, 4);
  if (deferredOwnershipFailed) {
    log('ERROR', 'Deferred-lookup ownership recheck failed; aborting before any lookup write.');
    return { ...summary, aborted: 'deferred-lookup-ownership-errors' };
  }

  for (const lookup of SCHEMA.phase2_lookups) {
    try {
      digest = await getDigest();  // refresh per item (digest lifetime)
      const targetGuid = listGuids[lookup.target_list];
      if (!targetGuid) throw new Error(`Lookup target ${lookup.target_list} missing.`);
      if (await reconcileDeclaredField(
        lookup.list, lookup.field, targetGuid, digest, true,
      )) {
        summary.columnsSkipped += 1;
      } else {
        await createDeclaredLookupField(lookup.list, lookup.field, targetGuid, digest);
        invalidateFieldShapes();  // new field: next probe re-enumerates
        await reconcileDeclaredField(
          lookup.list, lookup.field, targetGuid, digest, false,
        );
        summary.columnsCreated += 1;
      }
      // Projected dependent fields, created after the primary exists so its
      // Id is known. Each is a read-only Lookup linked back by FieldRef and
      // created via createfieldasxml, because the FieldRef linkage cannot be
      // expressed through AddField. Read-only fields do not drift, so they are
      // checked for existence only, never reconciled. See the probe
      // test/manual/projected-lookup-probe.js for the measured create shape.
      if (lookup.projections && lookup.projections.length) {
        digest = await getDigest();
        const primaryShape = await readFieldShape(lookup.list, lookup.field.title, null, true);
        for (const proj of lookup.projections) {
          if (!(await readFieldShape(lookup.list, proj.name, null, true))) {
            digest = await getDigest();
            const xml = `<Field Type="Lookup" DisplayName="${proj.display_title}" `
              + `Name="${proj.name}" List="{${targetGuid}}" ShowField="${proj.show_field}" `
              + `FieldRef="{${primaryShape.Id}}" ReadOnly="TRUE"/>`;
            await postJson(
              apiUrl(`web/lists/getbytitle('${odataName(lookup.list)}')/fields/createfieldasxml`),
              { parameters: { SchemaXml: xml, Options: 8 } },
              digest,
            );
            summary.columnsCreated += 1;
          }
          await verifyDependentField(lookup.list, proj.name, proj.show_field, primaryShape.Id, targetGuid);
        }
      }
    } catch (err) {
      log('ERROR', `Phase 2.2 ${lookup.list}.${lookup.field.title}: ${err.message}`);
      summary.errors.push({
        phase: '2.2', list: lookup.list, column: lookup.field.title, error: err.message,
      });
    }
  }

  if (summary.errors.length > 0) {
    log('ERROR', 'Phase 2.2 lookup reconciliation failed; aborting before indexes and ACL work.');
    return { ...summary, aborted: 'phase-2-schema-errors' };
  }
  markPhase('Phase 2.3: indexed columns');
  // === Phase 2.3: indexed columns ===
  log('INFO', 'Starting Phase 2.3: indexed columns.');
  {
    // Index writes are the first mutation after schema reconciliation ends,
    // so the ownership it proved is no longer current. Survey every source
    // list as one batch before the first write: a failure here must stop the
    // batch rather than index the lists ahead of it and refuse the rest.
    const indexOwned = SCHEMA.indexed_columns.length > 0
      ? await surveyOwnedListsForWrites(
        SCHEMA.indexed_columns.map(idx => idx.list), '2.3', 'Index',
      )
      : new Map();
    if (!indexOwned) {
      log('ERROR', 'Index ownership survey failed; aborting before any index write.');
      return { ...summary, aborted: 'index-ownership-errors' };
    }
    // Every target is resolved before the first write. Approving a field is a
    // read, and once approved these MERGEs depend on nothing between them, so
    // they travel as ChangeSet parts rather than one POST each.
    const indexTargets = [];
    for (const idx of SCHEMA.indexed_columns) {
      try {
        indexTargets.push({
          idx,
          target: await ownedFieldIdentity(idx.list, idx.field, indexOwned.get(idx.list)),
        });
      } catch (err) {
        log('ERROR', `Index ${idx.list}.${idx.field}: ${err.message}`);
        summary.errors.push({ list: idx.list, column: idx.field, error: err.message });
      }
    }
    // One $batch per list, the same boundary the seal phase draws. Lists are
    // independent; same-list field writes are the ones that race into save
    // conflicts, so the list stays the unit a ChangeSet is drawn around and
    // this phase makes no claim the seal phase has not already made.
    const indexByList = new Map();
    for (const entry of indexTargets) {
      if (!indexByList.has(entry.idx.list)) indexByList.set(entry.idx.list, []);
      indexByList.get(entry.idx.list).push(entry);
    }
    for (const [listTitle, entries] of indexByList) {
      const indexBatch = new BatchWriter({ getDigest, fetchWithRetry, apiUrl, log });
      try {
        for (const entry of entries) {
          // fieldMergePath and FIELD_MERGE_HEADERS are what patchFieldById
          // sends, so only the transport differs: still by-Id, still a MERGE.
          await indexBatch.add(
            'POST',
            fieldMergePath(entry.target.listId, entry.target.field.Id),
            { __metadata: { type: 'SP.Field' }, Indexed: true },
            FIELD_MERGE_HEADERS,
          );
        }
        await indexBatch.done();
      } catch (err) {
        // Named at list level with the columns it covered, not attributed to
        // one of them: SharePoint does not roll a ChangeSet back, and the
        // refusal reports part statuses in queue order rather than saying
        // which column each belongs to.
        log('ERROR', `Index ${listTitle}: ${err.message}`);
        summary.errors.push({
          list: listTitle, columns: entries.map(entry => entry.idx.field),
          error: err.message,
        });
      }
    }
    // Every column is still read back and compared. What changed is the
    // transport and where each of the two facts comes from: the list identity
    // is re-proved once per list now that all the writes have landed, and the
    // field identities travel as top-level $batch query parts. Per column
    // this was one forced list enumeration, one list GET and one field GET,
    // sequentially, which is what made this the longest phase in the deploy.
    if (indexTargets.length > 0) {
      // Re-proved per LIST rather than per column. A list swapped between two
      // columns' read-backs is still caught: the field read below addresses
      // the field through the list TITLE, so a replacement answers with a
      // different field Id, or with none, and fails that column's comparison.
      const verifyOwned = await surveyOwnedListsForWrites(
        indexTargets.map(entry => entry.idx.list), '2.3', 'Index readback',
      );
      let shapes = null;
      try {
        const indexReader = new BatchReader({ getDigest, fetchWithRetry, apiUrl, log });
        for (const { idx } of indexTargets) {
          await indexReader.add(`${fieldShapePath(idx.list, idx.field)}?$select=Id`);
        }
        shapes = await indexReader.done();
      } catch (err) {
        // Fails closed, as a refused write batch does. Every column below then
        // records that it was not read back, rather than the phase quietly
        // reporting columns it never verified.
        log('ERROR', `Index readback: ${err.message}`);
      }
      for (let position = 0; position < indexTargets.length; position += 1) {
        const { idx, target } = indexTargets[position];
        try {
          if (!verifyOwned) {
            throw new Error('the list ownership re-check failed, so this column was not read back');
          }
          const listId = verifyOwned.get(idx.list);
          if (listId == null) {
            throw new Error(`Declared list '${idx.list}' disappeared across the index write`);
          }
          if (sharePointGuid(listId, 'list') !== sharePointGuid(target.listId, 'list')) {
            throw new Error(`List '${idx.list}' changed identity across the index write`);
          }
          if (!shapes) {
            throw new Error('the batched read-back did not answer, so this column was not read back');
          }
          // Identity read-back, not a value read-back. What SharePoint reports
          // for Indexed immediately after the MERGE has not been measured here
          // (it builds the index behind the flag asynchronously), so asserting
          // it would be a guess; what IS asserted is that the write landed on
          // the list and field the pre-write check approved.
          const after = shapes[position];
          if (!after || typeof after.Id !== 'string') {
            throw new Error(`Declared column '${idx.list}.${idx.field}' disappeared across the index write`);
          }
          if (after.Id !== target.field.Id) {
            throw new Error(`column changed identity across the index write (was ${target.field.Id}, now ${after.Id})`);
          }
        } catch (err) {
          log('ERROR', `Index ${idx.list}.${idx.field}: ${err.message}`);
          summary.errors.push({ list: idx.list, column: idx.field, error: err.message });
        }
      }
    }
  }

  markPhase('Phase 2.4: field defaults');
  // === Phase 2.4: reconcile declared field defaults ===
  // Defaults are included in create-field bodies, but existing columns are
  // skipped in Phase 2.1. Re-applying the declared value makes upgrades
  // idempotent and lets a provisioned constant replace after-create flows.
  log('INFO', 'Starting Phase 2.4: field defaults.');
  {
    // Post-schema, so the same batch gate as the other write phases: prove
    // every target list before the first MERGE, and refuse the phase instead
    // of writing defaults into the lists ahead of the failing one.
    const defaultsOwned = SCHEMA.field_defaults.length > 0
      ? await surveyOwnedListsForWrites(
        SCHEMA.field_defaults.map(fieldDefault => fieldDefault.list),
        '2.4', 'Field default',
      )
      : new Map();
    if (!defaultsOwned) {
      log('ERROR', 'Field-default ownership survey failed; aborting before any default is written.');
      return { ...summary, aborted: 'default-ownership-errors' };
    }
    // Approving a target is a read, and every one of them happens before the
    // first write: the MERGEs that follow depend on nothing between them, so
    // they travel as ChangeSet parts rather than one POST each.
    const defaultTargets = [];
    for (const fieldDefault of SCHEMA.field_defaults) {
      try {
        defaultTargets.push({
          fieldDefault,
          target: await ownedFieldIdentity(
            fieldDefault.list, fieldDefault.field, defaultsOwned.get(fieldDefault.list),
          ),
        });
      } catch (err) {
        log('ERROR', `Default ${fieldDefault.list}.${fieldDefault.field}: ${err.message}`);
        summary.errors.push({
          list: fieldDefault.list,
          column: fieldDefault.field,
          error: err.message,
        });
      }
    }
    // One $batch per list, the boundary the seal phase draws: lists are
    // independent, and same-list field writes are the ones that race into
    // save conflicts, so no wider claim is made here than there.
    const defaultsByList = new Map();
    for (const entry of defaultTargets) {
      const listTitle = entry.fieldDefault.list;
      if (!defaultsByList.has(listTitle)) defaultsByList.set(listTitle, []);
      defaultsByList.get(listTitle).push(entry);
    }
    for (const [listTitle, entries] of defaultsByList) {
      const defaultsBatch = new BatchWriter({ getDigest, fetchWithRetry, apiUrl, log });
      try {
        for (const entry of entries) {
          // fieldMergePath and FIELD_MERGE_HEADERS are what patchFieldById
          // sends, so only the transport differs: still by-Id, still a MERGE.
          await defaultsBatch.add(
            'POST',
            fieldMergePath(entry.target.listId, entry.target.field.Id),
            {
              __metadata: { type: entry.fieldDefault.metadata_type },
              DefaultValue: entry.fieldDefault.default_value,
            },
            FIELD_MERGE_HEADERS,
          );
        }
        await defaultsBatch.done();
      } catch (err) {
        // Recorded at list level and not attributed to a column: SharePoint
        // does not roll a ChangeSet back, so some of these may have landed.
        // The per-column readback below is the finer evidence, and it is what
        // turns a part that never landed into a named failure.
        log('ERROR', `Default ${listTitle}: ${err.message}`);
        summary.errors.push({ list: listTitle, error: err.message });
      }
    }
    for (const { fieldDefault, target } of defaultTargets) {
      try {
        const actual = await readFieldShape(fieldDefault.list, fieldDefault.field, null, true);
        if (!actual
            || normalizeDefaultValue(actual.DefaultValue)
               !== normalizeDefaultValue(fieldDefault.default_value)) {
          throw new Error('DefaultValue readback did not match the declared value');
        }
        // The readback resolves list and column by name, so it is only
        // evidence about the field just written if both still resolve to it.
        if (actual.Id !== target.field.Id) {
          throw new Error(`column changed identity across the default write (was ${target.field.Id}, now ${actual.Id})`);
        }
        await ownedListIdentity(
          fieldDefault.list, target.listId,
          `after writing the default for '${fieldDefault.list}.${fieldDefault.field}'`,
        );
      } catch (err) {
        log('ERROR', `Default ${fieldDefault.list}.${fieldDefault.field}: ${err.message}`);
        summary.errors.push({
          list: fieldDefault.list,
          column: fieldDefault.field,
          error: err.message,
        });
      }
    }
  }

  markPhase('Phase 3.1: views');
  // === Phase 3.1: managed views ===
  // Fields created through the REST field collection join no view, so a
  // fresh list shows a Title-only default view. Every list gets a generated,
  // unfiltered All Items recovery view containing its complete rendered
  // schema; when an authored default exists the recovery view is hidden from
  // the modern view bar. Authored views are managed alongside it. Other views
  // are user content and are never touched (unlike exact-mode ACLs).
  log('INFO', 'Group 3: PRESENTATION');
  log('INFO', 'Starting Phase 3.1: views.');
  // Readback normalization: SP collapses nothing between tags but DOES write
  // self-closing tags with a space (`<FieldRef Name="X" />`); compare both
  // sides with inter-tag whitespace and the pre-`/>` space collapsed.
  const normalizeViewQuery = (value) => xmlDecode(String(value || '')).replace(/>\s+</g, '><').replace(/\s+\/>/g, '/>').trim();
  // The view CustomFormatter is stored in the view schema XML like
  // ViewQuery, so its readback is XML-entity-encoded ('>=' returns as
  // '&gt;='): decode before the canonical JSON comparison, both sides.
  //
  // That claim arrived with the initial public tree and carried no date or
  // probe for a year. MEASURED at last on 2026-08-11 by
  // test/manual/formatter-xml-probe.js, and it is correct: '>' is written
  // back as '&gt;' and '>=' as '&gt;='.
  //
  // The same run establishes why the COLUMN formatter below is compared
  // WITHOUT this decode, which reads like an oversight and is not. A column's
  // CustomFormatter keeps '&', '<', '>' and both quotes literally -- it is not
  // XML-stored. Decoding it would corrupt a formatter that legitimately
  // contains '&amp;' as text.
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
    const r = await fetchWithRetry(`${viewUrl}?$select=Id,Title,DefaultView,Hidden,RowLimit,ViewQuery,PersonalView,CustomFormatter,Aggregations,AggregationsStatus,ServerRelativeUrl,ViewFields&$expand=ViewFields`, {
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
  // though isAbsent400 handles it; operators read those lines as failures.
  const viewShapesByList = {};
  async function listViewShapes(listPath) {
    if (!(listPath in viewShapesByList)) {
      // `$top=500`: a read with no explicit page size takes the server's,
      // and a truncated enumeration reads as "that view does not exist",
      // which is the one answer this function must never get wrong.
      const r = await fetchWithRetry(apiUrl(`${listPath}/views?$select=Id,Title,DefaultView,Hidden,RowLimit,ViewQuery,PersonalView,CustomFormatter,Aggregations,AggregationsStatus,ServerRelativeUrl,ViewFields&$expand=ViewFields&$top=500`), {
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
      // Lane-level rather than per-request, unlike the ACL phase. Every URL
      // below hangs off the list title, and a view lane issues tens of them;
      // one cache-bypassing list read per request would cost what the seal
      // phase measured and removed. So the lane is bracketed: owned before
      // the first read, and the title proved to still resolve to the same Id
      // after the last write, before this view is reported verified.
      const viewListId = viewsOwned.get(view.list);
      await ownedListIdentity(view.list, viewListId, `before writing views on '${view.list}'`);
      let viewDigest = await getDigest();
      const listPath = `web/lists/getbytitle('${odataName(view.list)}')`;
      // Kept as a path as well as a URL: apiUrl() is what a $batch part takes,
      // so the batched field writes below address the view by the same
      // spelling every single write here does rather than a second one.
      const viewPath = `${listPath}/views/getbytitle('${odataName(view.title)}')`;
      const viewUrl = apiUrl(viewPath);
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
          Hidden: view.hidden,
          Paged: true,
          ViewQuery: view.caml_query,
        };
        if (view.row_limit != null) createBody.RowLimit = view.row_limit;
        await postJson(apiUrl(`${listPath}/views`), createBody, viewDigest);
      };
      const listedViews = await listViewShapes(listPath);
      // FINDING a view matches case-insensitively, because SharePoint
      // resolves views/getbytitle that way and will not let two views on
      // one list differ only in case. Matching exactly here would read an
      // existing 'open by score' as absent, then try to create the
      // declared 'Open by score' beside it.
      //
      // The title DRIFT check further down stays exact on purpose: once
      // the view is found, a casing difference is drift the deployer owns
      // and renames, which is the opposite question.
      let existing = listedViews.find((v) => nameKey(v.Title) === nameKey(view.title)) || null;
      // A previous title is only interesting on a DIFFERENT view. Excluding
      // the one already matched as current is what makes a casing-only
      // rename possible: `title: Open` with `renamed_from: [open]` matches
      // the same live view twice under case-insensitive comparison, and the
      // conflict check below would then refuse to choose between a view and
      // itself, on every run, so the rename could never land.
      const previousMatches = listedViews.filter(
        (v) => (!existing || v.Id !== existing.Id)
          && view.renamed_from.some((t) => nameKey(t) === nameKey(v.Title)),
      );
      if (previousMatches.length > 1) {
        throw new Error(`multiple previous-title views exist for '${view.title}': ${previousMatches.map((v) => v.Title).join(', ')}`);
      }
      if (existing && previousMatches.length > 0) {
        throw new Error(`both current view '${view.title}' and previous-title view '${previousMatches[0].Title}' exist; refusing to choose or delete either`);
      }
      if (!existing && previousMatches.length === 1) {
        existing = previousMatches[0];
        log('INFO', `[Phase 3.1] Adopting previous view title '${existing.Title}' on '${view.list}' as '${view.title}'.`);
      }
      // A slug-titled view already sitting on the clean URL is our own
      // half-finished migration (we only ever create with Title=slug):
      // adopt it instead of creating a second page. A FOREIGN view on that
      // URL is never touched: the create below would get a suffixed .aspx
      // and the URL drift gate fails the view closed.
      const halfMigrated = listedViews.find(
        (v) => nameKey(v.Title) === nameKey(view.url_slug) && urlBasename(v) === desiredBasename,
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
          // deployer-owned: every setting is reasserted below; only
          // bookmarks to the old URL break (one-time, noted in deploy.md).
          log('INFO', `[Phase 3.1] Migrating view '${view.title}' on '${view.list}' from ${urlBasename(existing)} to ${desiredBasename}...`);
          if (!halfMigrated) await createViewWithCleanUrl();
          if (existing.DefaultView) {
            // Transfer the flag first: SP refuses to delete a default view.
            await mergeView(slugUrl, { __metadata: { type: 'SP.View' }, DefaultView: true }, viewDigest);
          }
          // The one request in this phase that destroys an existing object,
          // so it is rechecked on its own rather than riding the lane bracket.
          await ownedListIdentity(view.list, viewListId, `before deleting the migrated view on '${view.list}'`);
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
        } else if (existing.Title !== view.title) {
          // A rename whose old and new titles collapse to the same URL slug
          // needs no page recreation; update by immutable view Id because
          // getbytitle(new) cannot resolve until after this write.
          const viewByIdUrl = apiUrl(`${listPath}/views('${existing.Id}')`);
          await mergeView(
            viewByIdUrl,
            { __metadata: { type: 'SP.View' }, Title: view.title },
            viewDigest,
          );
          existing = await readViewShape(viewUrl);
          if (!existing) throw new Error('view disappeared during title migration');
        }
        // Narrow MERGE: send only drifted declared settings.
        const patchBody = { __metadata: { type: 'SP.View' } };
        if (normalizeViewQuery(existing.ViewQuery) !== normalizeViewQuery(view.caml_query)) {
          patchBody.ViewQuery = view.caml_query;
        }
        if (view.row_limit != null && existing.RowLimit !== view.row_limit) {
          patchBody.RowLimit = view.row_limit;
        }
        if (existing.Hidden !== view.hidden) {
          patchBody.Hidden = view.hidden;
        }
        // Declared totals only. A view with none keeps whatever is live,
        if (Object.keys(patchBody).length > 1) {
          await mergeView(viewUrl, patchBody, viewDigest);
        }
      }
      // MEASURED on 2026-08-14 by test/manual/view-aggregations-probe.js,
      // revisions aa79f6c4 and 96d0a67a on two sites, reproducing 2026-07-29:
      // `seeded=ok mechanism=patch readback=ok rendered=yes`.
      // Q5/Q6: internal names bound; two totals rendered in declaration order.
      // An empty aggregated column renders no footer until a row carries a value.
      // Declared totals. OUTSIDE the create/adopt branch above, like
      // ViewFields, formatting and the default flag: createViewWithCleanUrl
      // does not send Aggregations, so a newly created view would otherwise
      // reach the verify below with none and fail its own first deploy.
      //
      // A view with no declaration keeps whatever is live, matching
      // CustomFormatter and widths, so deleting a totals block does NOT
      // clear a deployed total.
      //
      // normalizeViewQuery is required here, not tidiness: SP reads back
      // `<FieldRef Name="X" Type="Sum" />` for the `...Type="Sum"/>` it was
      // sent, which is the pre-`/>` space that normaliser exists for.
      // Compared raw, a correct view drifts on every redeploy, rewrites,
      // reads the same difference back and fails the phase closed.
      //
      // The status is part of the CONDITION, not just the payload: SP
      // renders no figure when AggregationsStatus is Off, so a view whose
      // XML already matched while the status read Off would be refused by
      // the verify below and never repaired by this write.
      if (view.aggregations) {
        const beforeTotals = existing || await readViewShape(viewUrl);
        if (!beforeTotals) throw new Error('view disappeared before totals reconciliation');
        if (normalizeViewQuery(beforeTotals.Aggregations) !== normalizeViewQuery(view.aggregations)
            || beforeTotals.AggregationsStatus !== 'On') {
          await mergeView(viewUrl, {
            __metadata: { type: 'SP.View' },
            Aggregations: view.aggregations,
            AggregationsStatus: 'On',
          }, viewDigest);
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
        // One ChangeSet per view rather than one POST per column: the largest
        // single bucket of requests in the whole deploy (445 of this phase's
        // 1,221 on a ten-list family), and the deploy is throttle-bound, so
        // the count is what costs.
        //
        // This depends on ORDER being preserved inside a ChangeSet, which
        // OData v3 does not promise (it says order is "not significant" and a
        // service MAY reorder) and which #410 deliberately left unproven for
        // the phases whose writes commute. A view's column order is a
        // declared, verified setting, so it was MEASURED instead: a live
        // tenant, 2026-09-04, four runs, two scrambled orders per run that
        // matched neither creation nor alphabetical order. removeallviewfields
        // plus six addviewfield parts in ONE ChangeSet were accepted 7/7 and
        // read back in the order sent, every run. Cost over twelve columns,
        // same four runs: 0.33/0.46/0.47/0.36 s batched against
        // 1.99/1.31/0.95/4.33 s sequential.
        //
        // Safe against that claim turning out to be tenant-specific: the
        // readback below compares the column list position by position and
        // fails this view closed, so a service that ever does reorder is
        // reported rather than shipped.
        const fieldBatch = new BatchWriter({ getDigest, fetchWithRetry, apiUrl, log });
        await fieldBatch.add('POST', `${viewPath}/viewfields/removeallviewfields`, {});
        for (const name of view.view_fields) {
          await fieldBatch.add('POST', `${viewPath}/viewfields/addviewfield('${odataName(name)}')`, {});
        }
        await fieldBatch.done();
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
      // phase-start shape decides: nothing this lane writes clears a
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
      if (actual.Hidden !== view.hidden) {
        drifted.push(`Hidden (declared ${view.hidden}; readback ${actual.Hidden})`);
      }
      if (view.formatting != null
          && canonicalViewFormatter(actual.CustomFormatter) !== canonicalViewFormatter(view.formatting)) {
        drifted.push(`CustomFormatter (declared ${JSON.stringify(view.formatting)}; readback ${JSON.stringify(actual.CustomFormatter)})`);
      }
      // Both halves are verified: SP renders nothing without the status,
      // so an Aggregations that matched while the status read Off would be
      // a view the deploy called correct and the reader sees no total on.
      if (view.aggregations) {
        if (normalizeViewQuery(actual.Aggregations) !== normalizeViewQuery(view.aggregations)) {
          drifted.push(`Aggregations (declared ${JSON.stringify(view.aggregations)}; readback ${JSON.stringify(actual.Aggregations)})`);
        }
        if (actual.AggregationsStatus !== 'On') {
          drifted.push(`AggregationsStatus (declared On; readback ${JSON.stringify(actual.AggregationsStatus)})`);
        }
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
      // surface, the call the modern Lists UI makes when saving a dragged
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
      // Closes the lane bracket: the readbacks above resolved the list by
      // title, so they are evidence about the owned list only if the title
      // still answers with the Id this lane started from.
      await ownedListIdentity(view.list, viewListId, `after writing views on '${view.list}'`);
      log('INFO', `[Phase 3.1] View '${view.title}' on '${view.list}' verified.`);
    } catch (err) {
      log('ERROR', `Phase 3.1 view '${view.list}'.'${view.title}': ${err.message}`);
      summary.errors.push({ phase: '3.1', list: view.list, view: view.title, error: err.message });
    }
  };
  // Post-schema, so the same batch gate: prove every list carrying a declared
  // view before the first one is written, and refuse the phase rather than
  // reconcile the lists ahead of the failing one.
  const viewsOwned = SCHEMA.views.length > 0
    ? await surveyOwnedListsForWrites(
      SCHEMA.views.map((view) => view.list), '3.1', 'View',
    )
    : new Map();
  if (!viewsOwned) {
    log('ERROR', 'View ownership survey failed; aborting before any view is written.');
    return { ...summary, aborted: 'view-ownership-errors' };
  }
  // One lane per list: views live in the list schema, and concurrent schema
  // writes to the same list race into save conflicts; different lists are
  // independent, so their lanes run concurrently.
  await mapLanes(SCHEMA.views, (view) => view.list, deployView, 4);

  // ---- Confirm the editor still refuses the guard -----------------------
  // The readback above proves each stored ViewQuery is the declared one. It
  // cannot show whether this tenant's editor still refuses that shape, which
  // is a property of SharePoint's UI on the day of the deploy. See #267.
  //
  // The editor's own form controls, as the `name` ATTRIBUTE the probe read.
  // A bare substring would also match the word in page script, and would then
  // report a protected view as editable and abort the run.
  // Measured 2026-08-17, view-edit-page-probe.js `pinned-control-discriminates`
  // and `second-control-agrees` (C1 and C2): both are present on an editable
  // page and on an unfiltered one, and absent from a refused one. Two of them
  // because C2's result is that they agree; disagreement is the signal that
  // the markup moved.
  const EDITOR_CONTROLS = ['name="FieldPicker1"', 'name="OperatorPicker1"'];
  // `control-non-editor-page` (C6): a request for a view that does not exist
  // answers HTTP 200 on this URL with no editor controls, and with `ViewEdit`
  // and `ctl00` present and `ViewFilter` absent. So this is the only one of
  // the three that can gate an absence test.
  const EDITOR_PAGE_SENTINEL = 'ViewFilter';
  // A response cut short after the sentinel and before the controls carries
  // neither, and absence is the whole predicate, so a page that stopped early
  // has to be told from one that renders no editor. C6 rejects a page that is
  // not a view and records the truncated shape as still unmeasured, naming a
  // length or completeness test as what would close it. Both are required
  // here: the document closed (both closing tags, in order), and it is the
  // size of a settings page. That page measured 501,773 characters on
  // 2026-08-17, so this floor sits an order of magnitude under it and rejects
  // a login stub or an error page without resting on a size SharePoint owns.
  const EDITOR_PAGE_MIN_CHARS = 50000;

  // Fail closed. A check that could not read the page is not evidence the
  // view is unprotected, and it is not evidence that it is protected either.
  // This is the only thing that asks, so an unanswered check is an error on
  // the run rather than a warning under it: the alternative is a deployment
  // reporting clean while the one property it could not verify is the one an
  // operator destroys by pressing Save. Supersedes the ruling of 2026-08-17,
  // which warned here.
  const unverified = (why, view) => {
    const message = 'could not confirm the filter editor refuses the emitted shape'
      + ` (${why}), so the filter is unverified rather than protected`;
    log('ERROR', `[Phase 3.1] ${message}`);
    summary.errors.push({
      phase: '3.1', list: view ? view.list : null,
      view: view ? view.title : null, check: 'filter-editor-refusal', error: message,
    });
  };

  const listIdByPath = {};
  async function readListId(listPath) {
    if (!(listPath in listIdByPath)) {
      const r = await fetchWithRetry(apiUrl(`${listPath}?$select=Id`), {
        headers: { 'Accept': 'application/json;odata=verbose' },
      });
      if (!r.ok) throw new Error(`list read HTTP ${r.status}: ${spError(await r.text())}`);
      const j = await r.json();
      const id = j && j.d && j.d.Id;
      if (!id) throw new Error('the list read carried no Id');
      listIdByPath[listPath] = id;
    }
    return listIdByPath[listPath];
  }

  // Which of EDITOR_CONTROLS the view's settings page carries, or the reason
  // the page could not be read. `present` is meaningful only when `why` is
  // null: every other return says the question went unanswered.
  //
  // `ownedId` is the Id the write lane proved it owned for this view's list.
  // Every read below addresses the list by TITLE and this runs after the
  // lanes closed their brackets, so a same-titled replacement landing since
  // would have its settings page read and reported under the owned list's
  // name. Nothing downstream can see that the wrong list was asked, so the
  // resolved Id is compared before anything else is read.
  async function readEditorControls(view, ownedId) {
    const listPath = `web/lists/getbytitle('${odataName(view.list)}')`;
    let listId = null;
    let viewId = null;
    try {
      listId = await readListId(listPath);
      if (ownedId == null
          || sharePointGuid(listId, 'list') !== sharePointGuid(ownedId, 'list')) {
        return { present: null, why: `list '${view.list}' changed identity before the filter`
          + ` editor was read for '${view.title}': the write lane owned`
          + ` ${ownedId == null ? 'no proven Id' : ownedId}, and the title now resolves to`
          + ` ${listId}` };
      }
      const shape = (await listViewShapes(listPath)).find((s) => s.Title === view.title);
      viewId = shape && shape.Id;
    } catch (err) {
      // Surfaced, not swallowed. A discarded message here leaves an operator
      // with "could not identify" and nothing to act on.
      return { present: null, why: `could not identify '${view.title}' on '${view.list}':`
        + ` ${(err && err.message) || String(err)}` };
    }
    if (!listId || !viewId) {
      return { present: null,
        why: `'${view.title}' is not among '${view.list}' views after deployment` };
    }
    const pageUrl = `${WEB}/_layouts/15/ViewEdit.aspx?List=${encodeURIComponent(`{${listId}}`)}`
      + `&View=${encodeURIComponent(`{${viewId}}`)}`;
    let res;
    let body;
    try {
      // Through fetchWithRetry like every other request in this script: the
      // settings page is throttled the same way, and a bare fetch would turn
      // a 429 into "could not confirm" on a run that only needed to wait.
      res = await fetchWithRetry(pageUrl, { credentials: 'same-origin' });
      body = await res.text();
    } catch (err) {
      return { present: null,
        why: `could not read the settings page for '${view.title}': ${err.message}` };
    }
    // A login or modern-settings redirect answers 200, so res.ok alone would
    // hand the wrong HTML to the test below. A response carrying no final URL
    // cannot show it came from the endpoint asked for, so it does not land.
    const landed = res.ok && !res.redirected && String(res.url || '').includes('ViewEdit.aspx');
    // The document closed when both closing tags arrived in their nesting
    // order and nothing after the last one resumes the page. `endsWith` was
    // wrong because SharePoint served trailing markup after the close on
    // 2026-08-27 and read a whole 556 KB page as cut short; bare containment
    // is wrong the dangerous way round, because an `</html>` literal in page
    // script stands in for a document that never closed. The editor's
    // controls live inside `<body>`, so a response cut before them cannot
    // have closed it.
    const bodyClose = body.lastIndexOf('</body>');
    const htmlClose = body.lastIndexOf('</html>');
    const afterClose = htmlClose < 0 ? '' : body.slice(htmlClose + '</html>'.length);
    const closed = bodyClose >= 0 && bodyClose < htmlClose
      && !['<input', '<body', '</body>', '<html'].some((m) => afterClose.includes(m));
    const complete = closed && body.length >= EDITOR_PAGE_MIN_CHARS;
    const sentinel = body.includes(EDITOR_PAGE_SENTINEL);
    if (!landed || !complete || !sentinel) {
      return { present: null, why: `the settings page for '${view.title}' on '${view.list}'`
        + ` is not usable: HTTP ${res.status}, redirected=${res.redirected},`
        + ` complete=${complete}, ${body.length} chars, sentinel=${sentinel}` };
    }
    return { present: EDITOR_CONTROLS.filter((control) => body.includes(control)), why: null };
  }

  const isFiltered = (view) => (view.caml_query || '').includes('<Where>');

  async function confirmEditorRefusesTheGuard() {
    const filtered = SCHEMA.views.filter(isFiltered);
    if (filtered.length === 0) {
      log('INFO', `[Phase 3.1] No filtered view declared, so nothing to confirm.`);
      return;
    }
    // The cached enumerations were taken BEFORE this run's writes, so they
    // hold no view this run created and a rename still under its old title.
    // Dropped once, here: listViewShapes then reads each list exactly once
    // more, and one lane per list keeps that read serial. views/getbytitle
    // would paint the console red on a miss for operators to read as a
    // failure.
    for (const view of SCHEMA.views) {
      delete viewShapesByList[`web/lists/getbytitle('${odataName(view.list)}')`];
    }

    // The CONTROL, and the reason absence can be read as refusal at all. A
    // SharePoint revision that renamed both controls while leaving the
    // sentinel in place would otherwise report every view protected, which is
    // the one wrong answer nothing downstream can see. An unfiltered view is
    // editable and carries both markers (measured 2026-08-17,
    // view-edit-page-probe.js `pinned-control-discriminates` and
    // `control-unfiltered-view`, C1 and F7), so it says whether the markers
    // still exist on this tenant's build today.
    const filteredLists = new Set(filtered.map((view) => view.list));
    const unfiltered = SCHEMA.views.filter((view) => !isFiltered(view));
    const control = unfiltered.find((view) => filteredLists.has(view.list)) || unfiltered[0];
    if (!control) {
      unverified('no unfiltered view is declared, so nothing establishes that the'
        + " editor's control names still exist on this tenant", filtered[0]);
      return;
    }
    const controlRead = await readEditorControls(control, viewsOwned.get(control.list));
    if (controlRead.why) {
      unverified(`the editable control read failed: ${controlRead.why}`, control);
      return;
    }
    const missing = EDITOR_CONTROLS.filter((name) => !controlRead.present.includes(name));
    if (missing.length > 0) {
      unverified(`${missing.join(', ')} absent from '${control.title}' on '${control.list}',`
        + ' which declares no filter and is editable, so absence on a guarded view is'
        + ' marker drift rather than evidence of protection', control);
      return;
    }

    // EVERY filtered view, not a sample. The guard is identical across them,
    // but what the editor refuses is a property of the whole stored filter,
    // and a view whose authored tree already refuses (30 of the 192 shipped
    // views did before this change) answers only for itself. One settings
    // page is roughly half a megabyte, so this is the expensive part of the
    // phase and its size is stated rather than silently capped.
    log('INFO', `[Phase 3.1] Reading ${filtered.length} view settings page(s)`
      + ' to confirm the filter editor refuses each declared filter.');
    let refused = 0;
    await mapLanes(filtered, (view) => view.list, async (view) => {
      const read = await readEditorControls(view, viewsOwned.get(view.list));
      if (read.why) {
        unverified(read.why, view);
        return;
      }
      if (read.present.length > 0) {
        // The page arrived and the editor is on it, so the filter is editable
        // and an operator can truncate it. The check answered, so this fails
        // the run on the determination rather than on the absence of one.
        const message = `view '${view.title}' on '${view.list}' is still editable in the filter`
          + ` editor (${read.present.join(', ')}), so its filter can be truncated by an operator`
          + ' pressing Save';
        log('ERROR', `[Phase 3.1] ${message}`);
        summary.errors.push({
          phase: '3.1', list: view.list, view: view.title,
          check: 'filter-editor-refusal', error: message,
        });
        return;
      }
      refused += 1;
    }, 4);
    log('INFO', `[Phase 3.1] Filter editor refuses ${refused} of`
      + ` ${filtered.length} declared filter(s), so those filters cannot be truncated`
      + ' from view settings.');
  }
  await confirmEditorRefusesTheGuard();
  markPhase('Phase 3.2: form formatting');
  // === Phase 3.2: form formatting ===
  // Declared list-form layouts (header/body/footer JSON) live on the list's
  // default item content type as ClientFormCustomFormatter, a JSON string
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
  {
    // Post-schema, so the same batch gate: prove every list with declared form
    // formatting before the first content-type MERGE, and refuse the phase
    // rather than format the lists ahead of the failing one.
    const formsOwned = SCHEMA.form_formatting.length > 0
      ? await surveyOwnedListsForWrites(
        SCHEMA.form_formatting.map((form) => form.list), '3.2', 'Form',
      )
      : new Map();
    if (!formsOwned) {
      log('ERROR', 'Form-formatting ownership survey failed; aborting before any form is written.');
      return { ...summary, aborted: 'form-ownership-errors' };
    }
    const formListPath = (title) => `web/lists/getbytitle('${odataName(title)}')`;
    const formFailed = (form, err) => {
      log('ERROR', `Phase 3.2 form '${form.list}': ${err.message}`);
      summary.errors.push({ phase: '3.2', list: form.list, error: err.message });
    };
    // Which content type each layout is written to, resolved for every list
    // before the first write. The MERGE URL carries the content type's
    // StringId, so this read has to happen first either way; batching it
    // costs one request rather than one per list.
    const formTargets = [];
    if (SCHEMA.form_formatting.length > 0) {
      let contentTypes = null;
      try {
        const ctReader = new BatchReader({ getDigest, fetchWithRetry, apiUrl, log });
        for (const form of SCHEMA.form_formatting) {
          // `$top=500` for the same reason every other enumeration carries
          // it: no explicit page size means the server's, and a truncated
          // read here reads as "this list has no such content type".
          await ctReader.add(`${formListPath(form.list)}/contenttypes?$select=Name,StringId,ClientFormCustomFormatter&$top=500`);
        }
        contentTypes = await ctReader.done();
      } catch (err) {
        // Fails closed: every list below then records that its content type
        // was never resolved, rather than the phase skipping them silently.
        log('ERROR', `Form content-type read: ${err.message}`);
      }
      for (let position = 0; position < SCHEMA.form_formatting.length; position += 1) {
        const form = SCHEMA.form_formatting[position];
        try {
          if (!contentTypes) {
            throw new Error('the batched content-type read did not answer, so this list was not formatted');
          }
          const listed = (contentTypes[position] && contentTypes[position].results) || [];
          const target = listed.find((ct) => ct.StringId && ct.StringId.startsWith('0x01') && !ct.StringId.startsWith('0x0120'));
          if (!target) throw new Error('no default item content type found on the list');
          // The survey above cannot see a same-titled replacement that copied
          // the marker; only a second live read compared against the Id the
          // survey captured can. Kept per list and kept BEFORE the write
          // batch, so a list that fails it is dropped here and never reaches
          // a ChangeSet part.
          await ownedListIdentity(
            form.list, formsOwned.get(form.list),
            `before writing form formatting on '${form.list}'`,
          );
          formTargets.push({ form, target });
        } catch (err) {
          formFailed(form, err);
        }
      }
    }
    // ONE ChangeSet across every list, unlike the seal and index phases. The
    // boundary those draw is the list, because same-list FIELD writes race
    // into save conflicts; here each list takes at most one write, so there
    // is no same-list pair to race and nothing that boundary would protect.
    const drifted = formTargets.filter(({ form, target }) =>
      canonicalFormFormatter(target.ClientFormCustomFormatter)
        !== canonicalFormFormatter(form.client_form_custom_formatter));
    if (drifted.length > 0) {
      const formBatch = new BatchWriter({ getDigest, fetchWithRetry, apiUrl, log });
      try {
        for (const { form, target } of drifted) {
          // The same MERGE the single write sent, transport aside: same URL,
          // same concrete metadata type, same tunnelled verb and IF-MATCH.
          await formBatch.add(
            'POST',
            `${formListPath(form.list)}/contenttypes('${target.StringId}')`,
            { __metadata: { type: 'SP.ContentType' }, ClientFormCustomFormatter: form.client_form_custom_formatter },
            { 'IF-MATCH': '*', 'X-HTTP-Method': 'MERGE' },
          );
        }
        await formBatch.done();
      } catch (err) {
        // Named at phase level with the lists it covered. SharePoint does not
        // roll a ChangeSet back and reports part statuses in queue order
        // without saying which list each belongs to, so attributing the
        // refusal to one of them would be a guess. Every list is still read
        // back below, which is what says whether its layout landed.
        log('ERROR', `Form formatting: ${err.message}`);
      }
    }
    // Read back every declared layout and re-prove every list's identity, the
    // shape the index phase established: the list is re-proved once now that
    // all the writes have landed rather than bracketing each write, and the
    // readbacks travel as top-level query parts. A list swapped between two
    // readbacks is still caught, because the readback addresses the content
    // type THROUGH the list title and a replacement answers with a different
    // StringId, or with none.
    if (formTargets.length > 0) {
      const verifyOwned = await surveyOwnedListsForWrites(
        formTargets.map(({ form }) => form.list), '3.2', 'Form readback',
      );
      let readbacks = null;
      try {
        const formReader = new BatchReader({ getDigest, fetchWithRetry, apiUrl, log });
        for (const { form, target } of formTargets) {
          await formReader.add(`${formListPath(form.list)}/contenttypes('${target.StringId}')?$select=ClientFormCustomFormatter`);
        }
        readbacks = await formReader.done();
      } catch (err) {
        log('ERROR', `Form formatting readback: ${err.message}`);
      }
      for (let position = 0; position < formTargets.length; position += 1) {
        const { form } = formTargets[position];
        try {
          if (!verifyOwned) {
            throw new Error('the list ownership re-check failed, so this list was not read back');
          }
          const listId = verifyOwned.get(form.list);
          if (listId == null) {
            throw new Error(`Declared list '${form.list}' disappeared across the form write`);
          }
          if (sharePointGuid(listId, 'list') !== sharePointGuid(formsOwned.get(form.list), 'list')) {
            throw new Error(`List '${form.list}' changed identity across the form write`);
          }
          if (!readbacks) {
            throw new Error('the batched readback did not answer, so this list was not read back');
          }
          const readback = readbacks[position] && readbacks[position].ClientFormCustomFormatter;
          if (canonicalFormFormatter(readback) !== canonicalFormFormatter(form.client_form_custom_formatter)) {
            throw new Error(`did not retain declared form formatting (declared ${JSON.stringify(form.client_form_custom_formatter)}; readback ${JSON.stringify(readback)})`);
          }
          log('INFO', `[Phase 3.2] Form formatting on '${form.list}' verified.`);
        } catch (err) {
          formFailed(form, err);
        }
      }
    }
  }

  markPhase('Phase 4.1: seal declared columns');
  // === Phase 4.1: seal declared columns ===
  // Re-seal after every field write (1/2/3/3b/3d): sealed columns block UI
  // schema edits and deletion even for site admins, the strongest defense
  // when team owners are unavoidably site collection admins. Friction, not
  // enforcement: an admin can unseal via API, which is deliberate work, not
  // an accident.
  log('INFO', 'Group 4: PROTECTION');
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
    // Declared fields are already present above. Add the built-in Titles
    // PREPARE opened; the tool does not otherwise own their seal state.
    for (const [listTitle, columnTitle] of fieldsUnsealedForRun.values()) {
      if (columnTitle === 'Title') sealDeclared.push([listTitle, columnTitle]);
    }
    let sealedCount = 0;
    // One lane per list (field MERGEs on the same list race into save
    // conflicts; lists are independent). After a lane's writes, ONE fresh
    // per-list enumeration serves every column's verify readback; the
    // per-field fresh GETs paid ~one round-trip per column for the same
    // server evidence (live DEBUG timing: this phase alone was 13.3s of a
    // 52s run). Verification still never trusts phase-start state: the
    // per-list invalidation forces a post-write re-enumeration.
    //
    // The lane boundary is also the batch boundary, so one list's seals are
    // one ChangeSet. NOT PROVEN: that SharePoint applies same-list field
    // MERGEs in a ChangeSet without the save conflicts concurrent single
    // writes hit. OData v3 says the order of requests within a ChangeSet is
    // not significant and a service MAY process them in any order, and
    // test/manual/throttle-batch-probe.js batches item creates rather than
    // schema writes, so neither settles it. The per-column verify below is
    // what turns a conflict into a named failure instead of a silent one.
    const sealByList = new Map();
    for (const [listTitle, columnTitle] of sealDeclared) {
      if (!sealByList.has(listTitle)) sealByList.set(listTitle, []);
      sealByList.get(listTitle).push(columnTitle);
    }
    // Sealing is a write, so it gets the same batch gate as every other
    // post-schema write phase: prove ownership of every list first, and refuse
    // the phase rather than seal the lists ahead of the failing one. Without
    // it, a same-titled replacement dropped in after the structural phases
    // would be sealed by this run, which hands it the tool's own protection.
    const sealOwned = await surveyOwnedListsForWrites(
      [...sealByList.keys()], '4.1', 'Seal',
    );
    if (!sealOwned) {
      log('ERROR', 'Seal ownership survey failed; aborting before any column is sealed.');
      return { ...summary, aborted: 'seal-ownership-errors' };
    }
    await mapLanes([...sealByList.entries()], ([listTitle]) => listTitle, async ([listTitle, columns]) => {
      const failed = new Set();
      const writtenIds = new Map();
      let laneListId;
      try {
        // Once per lane, not once per column: every write below addresses
        // /lists(guid)/fields(guid), which no title rebind can redirect, so
        // re-proving the list per column would buy nothing the by-Id address
        // does not already give.
        laneListId = (await ownedListIdentity(
          listTitle, sealOwned.get(listTitle), `before sealing '${listTitle}'`,
        )).Id;
      } catch (err) {
        log('ERROR', `Phase 4.1 seal '${listTitle}': ${err.message}`);
        summary.errors.push({ phase: '4.1', list: listTitle, error: err.message });
        return;
      }
      // The lane's seals go out as ONE $batch rather than one MERGE per
      // column. They are independent writes with nothing read between them,
      // and the burst is the shape that got a nine-list run throttled mid
      // phase (#401). fieldMergePath and FIELD_MERGE_HEADERS are the same
      // address and headers patchFieldById sends, so only the transport
      // changes; the ChangeSet still addresses /lists(guid)/fields(guid),
      // which no title rebind can redirect.
      const sealBatch = new BatchWriter({ getDigest, fetchWithRetry, apiUrl, log });
      for (const columnTitle of columns) {
        try {
          const shape = await readFieldShape(listTitle, columnTitle, null);
          if (!shape) throw new Error('declared column missing at seal time');
          writtenIds.set(columnTitle, sharePointGuid(shape.Id, 'field'));
          if (!shape.Sealed) {
            await sealBatch.add(
              'POST',
              fieldMergePath(laneListId, writtenIds.get(columnTitle)),
              { __metadata: { type: 'SP.Field' }, Sealed: true },
              FIELD_MERGE_HEADERS,
            );
          }
        } catch (err) {
          failed.add(columnTitle);
          log('ERROR', `Phase 4.1 seal '${listTitle}.${columnTitle}': ${err.message}`);
          summary.errors.push({ phase: '4.1', list: listTitle, column: columnTitle, error: err.message });
        }
      }
      try {
        await sealBatch.done();
      } catch (err) {
        // Recorded at lane level and not attributed to a column: SharePoint
        // does not roll a ChangeSet back (Learn, "Make batch requests with
        // the REST APIs"), so some of these writes may have landed. The
        // verify pass below reads every column back and is the finer
        // evidence about which ones did.
        log('ERROR', `Phase 4.1 seal '${listTitle}': ${err.message}`);
        summary.errors.push({ phase: '4.1', list: listTitle, error: err.message });
      }
      // What the batch reports landed, not what the loop queued: a refused
      // part must not be counted as a column this run sealed.
      sealedCount += sealBatch.opsSent;
      invalidateFieldShapes(listTitle);  // verify from post-write state
      try {
        // The verify readback resolves the list by title, so the title has to
        // still answer with the identity that was written to.
        await ownedListIdentity(listTitle, laneListId, `after sealing '${listTitle}'`);
      } catch (err) {
        log('ERROR', `Phase 4.1 seal '${listTitle}': ${err.message}`);
        summary.errors.push({ phase: '4.1', list: listTitle, error: err.message });
        return;
      }
      for (const columnTitle of columns) {
        if (failed.has(columnTitle)) continue;
        try {
          const verify = await readFieldShape(listTitle, columnTitle, null);
          if (!verify || verify.Sealed !== true) {
            throw new Error(`did not retain sealed state (readback ${verify && verify.Sealed})`);
          }
          if (verify.Id !== writtenIds.get(columnTitle)) {
            throw new Error(`column changed identity across the seal write (was ${writtenIds.get(columnTitle)}, now ${verify.Id})`);
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
  markPhase('Phase 4.2: role inheritance and assignments');
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

    // Ownership was last proved by the structural phases, and everything
    // below addresses a list by title. Survey the whole batch first: a list
    // that has lost its marker or been replaced must stop the phase before
    // the lists ahead of it in the loop have their permissions rewritten.
    const aclOwned = await surveyOwnedListsForWrites(
      SCHEMA.list_assignments.map(la => la.list), '4.2', 'ACL',
    );
    if (!aclOwned) {
      log('ERROR', 'ACL ownership survey failed; aborting before any role assignment changes.');
      return { ...summary, aborted: 'acl-ownership-errors' };
    }

    // Every role-assignment endpoint SharePoint documents is addressed by
    // list title; there is no by-Id form to switch these to the way a field
    // MERGE can be. What is available is to bracket the request: prove the
    // title resolves to the surveyed list immediately before it, and prove it
    // still does immediately after. A rebind can then only produce a failed
    // phase, never a grant or a removal applied to a stranger.
    const withOwnedList = async (listTitle, expectedId, what, request) => {
      await ownedListIdentity(listTitle, expectedId, `before ${what}`);
      const result = await request();
      await ownedListIdentity(listTitle, expectedId, `after ${what}`);
      return result;
    };

    for (const la of SCHEMA.list_assignments) {
      log('INFO', `[Phase 4.2] Processing role assignments for '${la.list}'...`);
      try {
        const aclListId = aclOwned.get(la.list);
        // Before the first READ, not just the first write: exact mode turns
        // the enumeration below into a removal list, so a snapshot taken from
        // the wrong object is as dangerous as a write to it.
        await ownedListIdentity(la.list, aclListId, `before reading ACL state for '${la.list}'`);
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
            await withOwnedList(la.list, aclListId, `breakroleinheritance on '${la.list}'`, async () => {
              digest4 = await getDigest();
              const breakResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/breakroleinheritance(copyRoleAssignments=false,clearSubscopes=false)`), {
                method: 'POST',
                headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 },
              });
              if (!breakResp.ok) {
                const text = await breakResp.text();
                throw new Error(`breakroleinheritance failed: HTTP ${breakResp.status} ${text}`);
              }
            });
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

        // The one irreversible operation in this phase, so it carries the
        // strictest bracket: nothing is removed unless the title still
        // resolves to the surveyed list at the moment of the request.
        const removeBinding = async (principalId, roleDefId, reason) => {
          await withOwnedList(la.list, aclListId, `removeroleassignment (${reason}) on '${la.list}'`, async () => {
            digest4 = await getDigest();
            const rmResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments/removeroleassignment(principalid=${principalId},roleDefId=${roleDefId})`), {
              method: 'POST',
              headers: { 'Accept': 'application/json;odata=verbose', 'X-RequestDigest': digest4 },
            });
            if (!rmResp.ok) {
              const text = await rmResp.text();
              throw new Error(`removeroleassignment (${reason}, principal ${principalId}, binding ${roleDefId}) failed: HTTP ${rmResp.status} ${text}`);
            }
          });
          log('INFO', `[Phase 4.2] '${la.list}' removed ${reason} binding ${roleDefId} for principal ${principalId}.`);
        };

        // Establish every desired grant before pruning. This keeps at least the
        // declared owner path in place when breakroleinheritance(false) has
        // temporarily granted the current operator direct Full Control. Any add
        // failure aborts the list before exact mode removes a single binding.
        // GetByPrincipalId is positional in SharePoint REST; add/remove role
        // assignment methods below use their documented named parameters.
        // ONE enumeration answers every question below. getbyprincipalid
        // answers 404 for a principal that has no assignment on this list
        // yet (which every declared principal is on a first deploy), and
        // the browser paints that red whether or not the script handles it.
        // Same treatment lists, views and site groups already get.
        //
        // Deliberately not fatal: if the enumeration is refused we fall
        // back to per-principal probing, which is noisier and still
        // correct. Exact mode below reuses this same snapshot; it was
        // taken BEFORE the adds, which changes no removal because a
        // binding this run adds is by definition declared, and exact mode
        // only removes bindings that are not.
        let existingAssignments = null;
        {
          const collected = [];
          let pageUrl = apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments?$expand=Member,RoleDefinitionBindings&$select=Member/Id,Member/Title,RoleDefinitionBindings/Id,RoleDefinitionBindings/Name`);
          let ok = true;
          while (pageUrl && ok) {
            const pageResp = await fetchWithRetry(pageUrl, {
              headers: { 'Accept': 'application/json;odata=verbose' },
            });
            if (!pageResp.ok) { ok = false; break; }
            const pageJson = await pageResp.json();
            collected.push(...((pageJson.d && pageJson.d.results) || []));
            pageUrl = (pageJson.d && pageJson.d.__next) || null;
          }
          if (ok) existingAssignments = collected;
        }
        const bindingsFor = (principalId) => {
          if (!existingAssignments) return null;
          const hit = existingAssignments.find(
            (a) => a.Member && a.Member.Id === principalId,
          );
          return (hit && hit.RoleDefinitionBindings && hit.RoleDefinitionBindings.results) || [];
        };

        // Which grants are missing is a question of reads, and it is settled
        // for every declared assignment before the first add: the adds are
        // independent of one another, so they go out as ONE $batch rather
        // than one POST each. breakroleinheritance above and every removal
        // below stay single, because those are ordered against the reads
        // around them.
        const missingGrants = [];
        for (const resolved of resolvedAssignments) {
          let desiredBindings = bindingsFor(resolved.principalId);
          if (desiredBindings === null) {
            const desiredResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments/getbyprincipalid(${resolved.principalId})?$expand=RoleDefinitionBindings&$select=RoleDefinitionBindings/Id`), {
              headers: { 'Accept': 'application/json;odata=verbose' },
            });
            if (desiredResp.ok) {
              const desiredJson = await desiredResp.json();
              desiredBindings = (desiredJson.d && desiredJson.d.RoleDefinitionBindings && desiredJson.d.RoleDefinitionBindings.results) || [];
            } else if (desiredResp.status === 404) {
              desiredBindings = [];
            } else {
              const text = await desiredResp.text();
              throw new Error(`desired binding probe failed: HTTP ${desiredResp.status} ${text}`);
            }
          }
          const desiredPresent = desiredBindings.some(binding => binding.Id === resolved.roleDefId);
          if (!desiredPresent) missingGrants.push(resolved);
        }
        if (missingGrants.length > 0) {
          // The bracket is no weaker for holding a batch, only wider: the
          // title is proved to be the surveyed list immediately before the
          // request and immediately after it, and every add sits inside that
          // window, including one the body budget flushes early. A rebind can
          // still only produce a failed phase, never a grant on a stranger.
          await withOwnedList(la.list, aclListId, `addroleassignment on '${la.list}'`, async () => {
            const addBatch = new BatchWriter({ getDigest, fetchWithRetry, apiUrl, log });
            try {
              for (const resolved of missingGrants) {
                // No body: addroleassignment takes its arguments in the URL,
                // exactly as the single POST this replaces did.
                await addBatch.add('POST', `web/lists/getbytitle('${odataName(la.list)}')/roleassignments/addroleassignment(principalid=${resolved.principalId},roleDefId=${resolved.roleDefId})`);
              }
              await addBatch.done();
            } catch (err) {
              // Still fatal for this list, and still before a single removal:
              // exact mode must never prune against a desired state it failed
              // to establish. SharePoint does not roll a ChangeSet back, so
              // some grants may have landed; the phase is rerunnable and the
              // next run reads the bindings again.
              throw new Error(`addroleassignment batch failed before reconciliation: ${err.message}`);
            }
          });
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
          // Reuses the snapshot taken above when it succeeded. Exact mode
          // is an allowlist, so it must never run on a PARTIAL view of the
          // bindings: if that enumeration was refused, this one repeats it
          // and stays fatal on failure rather than pruning against
          // whatever it managed to read.
          let allAssignments = existingAssignments;
          if (allAssignments === null) {
            allAssignments = [];
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
              allAssignments.push(...((allJson.d && allJson.d.results) || []));
              assignmentsUrl = (allJson.d && allJson.d.__next) || null;
            }
          }
          // The snapshot above may have been taken before the adds; either
          // way it is the allowlist this loop prunes against, so the title it
          // was read through has to still be the surveyed list.
          await ownedListIdentity(la.list, aclListId, `before exact-mode pruning on '${la.list}'`);
          for (const existing of allAssignments) {
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
            let bindings = bindingsFor(resolved.principalId);
            if (bindings === null) {
              const raResp = await fetchWithRetry(apiUrl(`web/lists/getbytitle('${odataName(la.list)}')/roleassignments/getbyprincipalid(${resolved.principalId})?$expand=RoleDefinitionBindings&$select=RoleDefinitionBindings/Id,RoleDefinitionBindings/Name`), {
                headers: { 'Accept': 'application/json;odata=verbose' },
              });
              if (raResp.ok) {
                const raJson = await raResp.json();
                bindings = (raJson.d && raJson.d.RoleDefinitionBindings && raJson.d.RoleDefinitionBindings.results) || [];
              } else if (raResp.status === 404) {
                bindings = [];
              } else {
                const text = await raResp.text();
                throw new Error(`role assignment probe failed: HTTP ${raResp.status} ${text}`);
              }
            }
            for (const binding of bindings) {
              if (binding.Name !== 'Limited Access' && binding.Id !== resolved.roleDefId) {
                await removeBinding(resolved.principalId, binding.Id, 'stale');
              }
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
    return { ...summary, aborted: 'pre-seed-errors' };
  }
  markPhase('Phase 5.1: seed items');
  // === Phase 5.1: seed singleton list items (extension-provided) ===
  log('INFO', 'Group 5: DATA');
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

  {
    // The last write phase, and the only one that inserts data. An insert into
    // a replaced list is not repairable by rerunning, so the batch is gated on
    // ownership before the first row: a failure here must leave every seed
    // target untouched rather than seed the ones ahead of it in the loop. A
    // seed target that is not a declared list of this run fails the survey by
    // construction, which is the intent; nothing else has ever proved it owned.
    const seedOwned = SCHEMA.seed_items.length > 0
      ? await surveyOwnedListsForWrites(
        SCHEMA.seed_items.map(seed => seed.title), '5.1', 'Seed',
      )
      : new Map();
    if (!seedOwned) {
      log('ERROR', 'Seed ownership survey failed; aborting before any row is inserted.');
      return { ...summary, aborted: 'seed-ownership-errors' };
    }
    for (const seed of SCHEMA.seed_items) {
      // Fresh digest per seed: FormDigestValue expires (~30 min), so a
      // long run must not reuse one digest across every POST (rollback.js.txt
      // per-operation getDigest pattern).
      const digest5 = await getDigest();
      try {
        const seedListId = seedOwned.get(seed.title);
        // Before the probe as well as the insert: skip_if_has_rows decides
        // whether to write at all from what it reads here, so reading a
        // stranger's rows can suppress a real seed as easily as it can permit
        // an insert into one.
        await ownedListIdentity(seed.title, seedListId, `before reading '${seed.title}'`);
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
        // correct for ANY list title: SharePoint encodes non-alphanumeric
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
        // The item-creation endpoint SharePoint documents is addressed by list
        // title, so the insert is bracketed instead: owned immediately before
        // the POST, and the title still resolving to the same list immediately
        // after it, which is also what makes the readback below evidence about
        // the row this run just wrote.
        await ownedListIdentity(seed.title, seedListId, `before inserting into '${seed.title}'`);
        await postJson(apiUrl(`web/lists/getbytitle('${odataName(seed.title)}')/items`), body, digest5);
        await ownedListIdentity(seed.title, seedListId, `after inserting into '${seed.title}'`);
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
  }

  if (summary.errors.length > 0) {
    log('ERROR', 'Singleton seed verification failed; deployment is not activation-ready.');
    return { ...summary, aborted: 'phase-5-seed-errors' };
  }

  // The explicit success signal: every abort gate in the phase chain has
  // now been passed, so the enterprise reader this run enrolled (if any)
  // is a permanent grant, not a failed run's leftover. Set here rather than
  // read from `summary.errors.length === 0` in the finally, because
  // restoreUnsealedFields runs first in that finally and can still push to
  // that array on the way out -- reading it there would misread a failed
  // exit re-seal as a reason to unenrol a reader this successful deploy
  // just added.
  runReachedTheEnd = true;
  await removeSelfEnrollments();

  // Operator-perspective diagnostic (after enrolment cleanup, so the
  // run-scoped admin membership does not inflate the numbers): list ACLs
  // can LOOK correct while the signed-in account still deletes happily:
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
      log('INFO', `Operator effective rights on '${listTitle}': delete items = ${canDelete}, manage list = ${canManage}, site collection admin = ${isSiteAdmin}. Site collection admins and Full Control holders bypass list ACLs (owners of a group-connected site are site collection admins, invisible in Check Permissions). Verify member behaviour with an ordinary member account.`);
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
  // The IIFE is opened AND closed in deploy.js.j2, which is also where the
  // try wrapping every phase closes. A phase partial that emitted `})();`
  // itself would close the function before that finally could run.
  return summary;
  } catch (err) {
    // Convert every uncaught phase failure into the same returned summary contract (#282).
    const detail = String((err && err.message) || err).slice(0, 300);
    log('ERROR', `${currentPhaseLabel || 'Deploy'}: ${detail}`);
    summary.errors.push({ phase: currentPhaseLabel || 'deploy', error: detail });
    if (!summary.aborted) summary.aborted = 'uncaught-phase-error';
    return summary;
  } finally {
    // Each exit cleanup is guarded on its own: one throwing must not skip a
    // later one, because the operator's run-scoped membership is the LAST
    // drain and the exact thing a failed run must not leave behind. Order
    // still matters -- the stop stamp rides the run's own operator
    // enrolment (removeSelfEnrollments drains LAST), restore field
    // protection while the temporary membership still authorises the
    // write, then drain the reader before the operator.
    try {
      await restoreUnsealedFields();
    } catch (err) {
      log('ERROR', `Could not restore field protection on exit: ${err.message}`);
    }
    try {
      await finishRunLog();
    } catch (err) {
      log('ERROR', `Could not write the run's stop record: ${err.message}`);
    }
    try {
      await removeReaderEnrollments();
    } catch (err) {
      log('ERROR', `Could not remove the enterprise reader on exit: ${err.message}`);
    }
    try {
      await removeSelfEnrollments();
    } catch (err) {
      log('ERROR', `Could not remove the operator's run-scoped enrolment on exit: ${err.message}. Remove yourself in Site permissions > Groups.`);
    }
  }
})();
