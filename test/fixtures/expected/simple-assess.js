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
 * every call is a GET except the contextinfo digest fetch and one read-only
 * CSOM ProcessQuery.
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
    "description": "List \u0027APP_Project\u0027 still carries the provenance marker fleet reporting finds it by",
    "key": "provenance_marker:APP_Project",
    "level_on_fail": "WARN"
  },
  {
    "description": "List \u0027APP_Task\u0027 still carries the provenance marker fleet reporting finds it by",
    "key": "provenance_marker:APP_Task",
    "level_on_fail": "WARN"
  },
  {
    "description": "List \u0027APP_AppSettings\u0027 still carries the provenance marker fleet reporting finds it by",
    "key": "provenance_marker:APP_AppSettings",
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
  "list_titles": [
    "APP_Project",
    "APP_Task",
    "APP_AppSettings"
  ],
  "requires_manage_permissions": true
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
      dbg(`${(opts && opts.method) || 'GET'} ${url.length > 160 ? `${url.slice(0, 160)}...` : url} -> ${r.status} in ${Date.now() - t0}ms${i > 0 ? ` (${i} throttle retries)` : ''}`);
      return r;
    }
  }
  const absListUrl = (title) => `${window.location.origin}${WEB}/Lists/${encodeURIComponent(title)}`;
  log('INFO', 'Read-only assessment. No changes are made.');

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

  // The whole assessment, taking its collaborators as an argument so the
  // standalone script and the deploy can share it without a second copy.
  async function assessSite(ctx) {
    const { requirements: REQUIREMENTS, targets: TARGETS,
            notAssessable: NOT_ASSESSABLE, log, web: WEB, origin: ORIGIN,
            fetchWithRetry, apiUrl, odataName, getDigest, verdictLevel } = ctx;
    // Fail closed on a caller-built targets: a missing key is a bare TypeError
    // several probes in, and every one of these is read below.
    const missingTargets = ['base_templates', 'list_titles', 'list_markers',
      'declares_seal', 'declares_prevent_deletion', 'declares_column_formatting',
      'declares_form_formatting', 'declares_versioning', 'declares_groups',
    ].filter((k) => !(k in (TARGETS || {})));
    if (missingTargets.length) throw new Error(`assess-targets-incomplete: ctx.targets is missing ${missingTargets.join(', ')}`);
    const findings = [];
    let verdict = null;
    const finding = (tier, key, level, detail) => {
      findings.push({ tier, key, level, detail });
      log(level, `[T${tier}] ${key}: ${detail}`);
    };
    // A property the site did not return is not a value. Printing it as one
    // put the literal word `undefined` in four operator-facing lines.
    const reported = (v, fallback = '(not reported)') => (v == null ? fallback : v);

    // Read-only GET helper: returns parsed .d (or the raw json) or null.
    async function probeGet(suffix) {
      try {
        const r = await fetchWithRetry(apiUrl(suffix), { headers: { 'Accept': 'application/json;odata=verbose' } });
        if (!r.ok) return { ok: false, status: r.status };
        const j = await r.json();
        const d = (j && j.d !== undefined) ? j.d : j;
        // Every caller reads a property off `d`, so a 200 with a null body was
        // an `ok` result that threw on the first read. Only the payload's
        // shape is judged here: the call sites cover three response shapes and
        // per-property validation against the $select would reject two.
        if (d === null || typeof d !== 'object') return { ok: false, error: 'non-object payload' };
        return { ok: true, d };
      } catch (err) {
        return { ok: false, error: err.message };
      }
    }

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

    // Platform build fingerprint (from the digest response).
    try {
      const r = await fetchWithRetry(apiUrl('contextinfo'), { method: 'POST', headers: { 'Accept': 'application/json;odata=verbose' } });
      const j = await r.json();
      finding(1, 'platform_build', 'INFO', `SharePoint build ${reported(j.d.GetContextWebInformation.LibraryVersion)}.`);
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
        // One finding per key, because one finding for three keys left the
        // other two undeclared and the verdict loop skips a key it has no
        // finding for, so a BLOCKED-level requirement passed unchecked.
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

    // Regional settings & languages: locale drives date rendering.
    {
      const rs = await probeGet('web/regionalsettings?$select=LocaleId');
      if (rs.ok) finding(1, 'regional_settings', 'INFO', `Site LocaleId ${reported(rs.d.LocaleId)}.`);
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
        // `|| 0` reported an unanswered quota as an empty site, which is a
        // measurement the surface never made.
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
    // WHY IT IS HERE AND NOT ONLY IN THE DEPLOY. deploy.js reconciles a drifted
    // Description, but only at the NEXT run. In the gap, a list whose
    // description an owner edited in list settings is absent from every fleet
    // report: discovery enumerates `Description`, so that site contributes
    // fewer rows, raises no error, and nothing knows how many there should have
    // been. assess.js is what an operator runs before touching a site, so it is
    // the only thing that can surface this between deploys.
    //
    // WARN, not BLOCKED: the list itself is fine and deploying over it is the
    // repair. Only reporting is affected, which is what DEGRADED means here.
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
    const markerFinding = (title, description) => {
      if (!LIST_MARKERS.has(title)) return;
      const expected = LIST_MARKERS.get(title);
      if (!expected) return;
      const key = `provenance_marker:${title}`;
      // A Description the probe did not report is not a Description that lost
      // its marker. Read as an empty string it warned on every declared list.
      // An empty string that WAS reported still warns: that is the drift this
      // check exists for.
      if (description == null) {
        finding(2, key, 'NOT-ASSESSABLE',
          `'${title}' exists, but its Description was not reported, so whether fleet `
          + 'reporting can see it is unknown.');
        return;
      }
      const held = String(description);
      if (held.includes(expected)) {
        finding(2, key, 'PASS', `'${title}' carries its provenance marker.`);
      } else {
        finding(2, key, 'WARN',
          `'${title}' exists but its Description no longer carries the provenance marker `
          + `"${expected}". Fleet reporting cannot see '${title}' until a deploy restores it.`);
      }
    };

    // Collision probe per declared list. Description rides along on a request
    // already being made, so the marker check above costs no probe of its own.
    for (const title of TARGETS.list_titles) {
      const key = `collision:${title}`;
      const list = await probeGet(`web/lists/getbytitle('${odataName(title)}')?$select=Title,BaseTemplate,Description`);
      if (!list.ok && list.status === 404) {
        finding(2, key, 'PASS', `'${title}' absent, a clean provision target.`);
      } else if (list.ok) {
        finding(2, key, 'INFO', `'${title}' already exists (BaseTemplate ${reported(list.d.BaseTemplate)}), a redeploy/reconcile target.`);
        markerFinding(title, list.d.Description);
      } else {
        finding(2, key, 'WARN', `Could not probe '${title}' (HTTP ${list.status || list.error}).`);
      }
    }

    // Property-surface probes against the first EXISTING declared list, else
    // the site's own lists: 200 PASS, non-200 WARN.
    {
      let probeList = null;
      for (const title of TARGETS.list_titles) {
        const l = await probeGet(`web/lists/getbytitle('${odataName(title)}')?$select=Title`);
        if (l.ok) { probeList = title; break; }
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
      // NOT-ASSESSABLE is kept: dropping it here made a requirement nobody
      // could check indistinguishable from one that was never declared, and
      // the loop below then read it as a pass. Tier 3 shares the key
      // `not_assessable`, which is not a requirement key, so it is never read.
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
      // Not BLOCKED, because nothing here says the requirement is unmet. Not a
      // pass either, because something the pack requires went unchecked.
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
  // verdict, and this script died with a stack trace and told the operator
  // nothing. BLOCKED because a site nobody could read is not a site to deploy
  // to, which is the call the deploy gate already makes.
  try {
    summary = await assessSite({
      requirements: REQUIREMENTS, targets: TARGETS, notAssessable: NOT_ASSESSABLE,
      log, web: WEB, origin: window.location.origin, fetchWithRetry, apiUrl,
      odataName, getDigest, verdictLevel: 'DONE',
    });
  } catch (err) {
    log('ERROR', `The assessment could not run (${err.message}); nothing was assessed.`);
    summary = { findings: [], verdict: 'BLOCKED', aborted: 'assessment-failed' };
  }
  console.log(summary);
  return summary;
})();
