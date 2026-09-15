/**
 * Library sharing probe, revision b6e5d5e7. Not yet run live.
 * This script only reads. It does not change permissions or send invitations.
 *
 * Prepare disposable content using the intended permission layout:
 * 1. Break library inheritance, retaining only dedicated administration and
 *    platform-owner groups. Remove default Owners, Members and Visitors grants.
 * 2. Create Division A and Division B folders with unique permissions. Retain
 *    administration/platform-owner groups and grant each division group its
 *    intended permission level on its own folder. Files inherit their folder.
 * 3. Put test.txt in each folder. Use ordinary accounts A and B, each enrolled
 *    only in its division group, plus an excluded site Owners-group account
 *    if available. None of these test accounts should be site administrators.
 *    Record each division group's numeric SharePoint ID as administrator.
 *    Exclude administration, platform-owner and other division memberships.
 * 4. Paste on a page in this SharePoint web. Confirm the printed site by setting
 *    CONFIRMED=true, then run as administrator, A and B in separate sessions.
 *    Enter the same library title and decoded server-relative paths each time:
 *    the two folders and their two files, separated by newlines. Do not paste
 *    sharing links or Forms/AllItems.aspx URLs. Label each run before or after.
 *    Enter the prepared division group ID for A or B; leave it blank for an
 *    administrator snapshot. Extra group memberships void division findings.
 * 5. Confirm A can open and save its file, but cannot open B's folder/file.
 *    Confirm B cannot open A's folder/file before the sharing attempt.
 * 6. As A, try granting B access to A's folder using Share > Specific people,
 *    and separately to its file. Disable email notification where available.
 *    Record whether it grants access, refuses, or requests owner approval.
 *    Also test an organisation link if offered. Existing-access links are a
 *    control: copying one does not establish that new access was granted.
 * 7. Test each resulting link as B in a separate browser session, then repeat
 *    the administrator and B snapshots. Keep folder/file attempts separate:
 *    remove any test grant in Manage access and verify B loses access before
 *    the next attempt. Repeat with the actual staff permission level if varied.
 * 8. Return the RESULTS JSON and observed edit/share/open outcomes. Remove the
 *    disposable library when finished. Do not change site sharing settings.
 *
 * Permission masks and ACLs are observations, not a sharing verdict. A denied
 * ACL read is not a denied document read; a 404 can also mean a wrong path.
 * Administrators must first confirm each target exists. UI and recipient
 * access are required to establish the outcome. Group enumeration does not
 * expand nested Entra groups. Confirm the prepared accounts have no nested
 * privileged memberships or direct grants outside the prepared division.
 * Failed or incomplete group reads void sharing findings.
 * This is a targeted snapshot, not a full audit.
 *
 * Sources:
 * https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/set-custom-permissions-on-a-list-by-using-the-rest-interface
 * https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/working-with-folders-and-files-with-rest
 * https://learn.microsoft.com/en-us/dotnet/api/microsoft.sharepoint.client.permissionkind?view=sharepoint-csom
 * https://learn.microsoft.com/en-us/previous-versions/microsoft-365/solutions/microsoft-365-limit-sharing?view=o365-worldwide
 */
(async () => {
  const CONFIRMED = false;
  const ALLOW_WRITES = false;
  const PROBE_WRITES = false;
  const PROBE_RETRY_TRANSIENT = false;
  const PROBE_RETRY_ATTEMPTS = 0;

  // Shared result registry v1. Register findings before any network work.
  //
  // STATE carries the coarse answer alongside the prose, from the five-value
  // vocabulary in test/manual/SURFACES.md: settled, open, awaiting-capture,
  // void, needs-human. An explicit state passed to record() always wins; the
  // classifier is the default for the rows nobody has ruled on yet.
  // ABORTED is open: it means the fixture never built, so the question was
  // never asked and the run has nothing to settle it with.
  const OPEN_HEADS = ['NOT ESTABLISHED', 'SHORT', 'ABORTED'];
  const AWAITING_CAPTURE_HEADS = ['MANUAL', 'NOT REACHED'];
  const stateFor = (observed) => {
    if (AWAITING_CAPTURE_HEADS.some((p) => observed.startsWith(p))) return 'awaiting-capture';
    if (OPEN_HEADS.some((p) => observed.startsWith(p))) return 'open';
    return 'settled';
  };
  const results = [];
  const expect = (id, question) => {
    results.push({
      id,
      question,
      observed: 'NOT ESTABLISHED',
      detail: 'the run did not reach this question',
      state: 'open',
    });
  };
  const record = (id, question, observed, detail, state) => {
    const next = {
      question, observed, detail: detail || '', state: state || stateFor(observed),
    };
    const row = results.find((candidate) => candidate.id === id);
    if (row) {
      Object.assign(row, next);
    } else {
      results.push({ id, ...next });
    }
    log('INFO', `${id}: ${observed}${detail ? `: ${detail}` : ''}`);
  };
  expect('access.effective-perms.control-current-identity', 'the current account and its site-administrator status are readable');
  expect('access.effective-perms.control-ordinary-actor', 'the non-administrator belongs only to the prepared division group, which is not associated Owners');
  expect('library.access.permission-snapshot', 'library, folder and file ACL and effective-permission responses are captured');
  expect('library.access.control-own-file-edit', 'the ordinary division account opens, edits and saves its own test file');
  expect('library.access.control-recipient-denied', 'the intended recipient cannot open the test object before each sharing attempt');
  expect('library.access.division-isolation', 'the division account can use its own content and cannot open the other division content');
  expect('library.access.folder-resharing', 'a division editor attempts to grant another division access to its folder');
  expect('library.access.file-resharing', 'a division editor attempts to grant another division access to its file');

  // Shared probe core v2: context guard, bounded transport and REST helpers.
  const log = (level, msg) => console.log(`[SP-PROBE] [${level}] ${msg}`);
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
  const probeWrites = typeof PROBE_WRITES === 'undefined' ? true : PROBE_WRITES;
  if (probeWrites && !ALLOW_WRITES) {
    log('INFO', 'This probe writes only its declared fixture. Set ALLOW_WRITES = true to proceed.');
    return { aborted: 'writes-disabled' };
  }
  const apiUrl = (suffix) => `${WEB}/_api/${suffix}`;
  const odataName = (name) => encodeURIComponent(String(name).replace(/'/g, "''"));
  log('INFO', `probe revision b6e5d5e7; core v2; results v1.`);
  log('INFO', `Running as ${_spPageContextInfo.userLoginName || '(unknown)'} on web '${WEB || '(root)'}'.`);

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const spError = (text) => {
    try {
      const parsed = JSON.parse(text);
      return parsed?.error?.message?.value
        || parsed?.odata?.error?.message?.value
        || String(text).slice(0, 300);
    } catch {
      return String(text).slice(0, 300);
    }
  };
  const isRefusal = (status) =>
    status >= 400 && status !== 401 && status !== 403
    && status !== 408 && status !== 429 && status !== 503;
  async function fetchWithRetry(url, options, attempts = PROBE_RETRY_ATTEMPTS) {
    for (let attempt = 0; ; attempt += 1) {
      const response = await fetch(url, options);
      const transient = response.status === 429 || response.status === 503;
      if (PROBE_RETRY_TRANSIENT && transient && attempt < attempts) {
        const retryAfter = Number(response.headers.get('Retry-After'))
          || Math.min(2 ** attempt, 30);
        log('INFO', `Throttled (HTTP ${response.status}); retry ${attempt + 1}/${attempts} in ${retryAfter}s.`);
        await sleep(retryAfter * 1000);
        continue;
      }
      return response;
    }
  }
  let cachedDigest = null;
  let digestExpiresAt = 0;
  async function getDigest() {
    if (cachedDigest && Date.now() < digestExpiresAt) return cachedDigest;
    const response = await fetchWithRetry(apiUrl('contextinfo'), {
      method: 'POST',
      headers: { 'Accept': 'application/json;odata=verbose' },
    });
    const text = await response.text();
    if (!response.ok) {
      throw new Error(`contextinfo failed HTTP ${response.status}: ${spError(text)}`);
    }
    const info = JSON.parse(text)?.d?.GetContextWebInformation;
    if (!info?.FormDigestValue) throw new Error('contextinfo omitted FormDigestValue');
    cachedDigest = info.FormDigestValue;
    digestExpiresAt = Date.now()
      + Math.max((Number(info.FormDigestTimeoutSeconds) || 1800) - 60, 60) * 1000;
    return cachedDigest;
  }
  const spHeaders = (digest, extra = {}) => ({
    'Accept': 'application/json;odata=verbose',
    'Content-Type': 'application/json;odata=verbose',
    'X-RequestDigest': digest,
    ...extra,
  });
  async function post(suffix, body, extraHeaders) {
    const digest = await getDigest();
    const response = await fetchWithRetry(apiUrl(suffix), {
      method: 'POST',
      headers: spHeaders(digest, extraHeaders || {}),
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const text = await response.text();
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: spError(text),
        d: null,
      };
    }
    let d = null;
    try {
      d = text ? JSON.parse(text).d : null;
    } catch {
      d = null;
    }
    return { ok: true, status: response.status, error: null, d };
  }
  async function get(suffix, accept) {
    const response = await fetchWithRetry(apiUrl(suffix), {
      method: 'GET',
      headers: { 'Accept': accept || 'application/json;odata=verbose' },
    });
    const text = await response.text();
    if (!response.ok) {
      return {
        ok: false,
        status: response.status,
        error: spError(text),
        d: null,
      };
    }
    const parsed = JSON.parse(text);
    return {
      ok: true,
      status: response.status,
      error: null,
      d: parsed.d !== undefined ? parsed.d : parsed,
    };
  }
  const merge = (suffix, body) => post(
    suffix,
    body,
    { 'X-HTTP-Method': 'MERGE', 'IF-MATCH': '*' },
  );
  async function entityTypeFor(listTitle) {
    const response = await get(
      `web/lists/getbytitle('${odataName(listTitle)}')?$select=ListItemEntityTypeFullName`,
    );
    if (!response.ok) {
      throw new Error(`could not resolve the item entity type: ${response.error}`);
    }
    return response.d.ListItemEntityTypeFullName;
  }
  const report = {
    revision: 'b6e5d5e7', capturedAt: new Date().toISOString(),
    sharingVerdict: 'NOT ESTABLISHED: requires edit, share and recipient-open observations',
    reads: {}, targets: [], errors: [], results,
  };
  const emit = () => {
    console.table(results);
    console.log('LIBRARY SHARING RESULTS\n' + JSON.stringify(report, null, 2));
  };
  const voidDependants = (control) => {
    for (const row of results) {
      if (row.id === control || row.state !== 'open') continue;
      row.observed = 'VOID';
      row.state = 'void';
      row.detail = `failed control: ${control}`;
    }
  };
  try {
    const context = window._spPageContextInfo;
    if (!context?.webAbsoluteUrl) throw new Error('NO_PAGE_CONTEXT: open a SharePoint page');
    const web = new URL(context.webAbsoluteUrl);
    if (web.origin !== window.location.origin) throw new Error('WRONG_ORIGIN: web context differs');
    const title = window.prompt('Library display title (not its URL):');
    if (!title?.trim()) throw new Error('CANCELLED: library title required');
    report.label = window.prompt('Run label, e.g. administrator before, division A before, division B after:') || '';
    const entered = window.prompt('Decoded server-relative folder and file paths, one per line (maximum 8):');
    if (!entered?.trim()) throw new Error('CANCELLED: target paths required');
    const paths = [...new Set(entered.split(/\r?\n/).map(value => value.trim()).filter(Boolean))];
    if (paths.length > 8) throw new Error('TOO_MANY_TARGETS: maximum 8');
    const divisionInput = window.prompt('Intended division SharePoint group ID, confirmed by the administrator (blank for snapshot only):')?.trim() ?? '';
    report.expectedDivisionGroupId = /^[1-9]\d*$/.test(divisionInput) && Number.isSafeInteger(Number(divisionInput))
      ? Number(divisionInput) : null;
    const literal = value => "'" + encodeURIComponent(value.replace(/'/g, "''")).replace(/'/g, '%27') + "'";
    const read = async path => {
      try {
        const response = await get(path);
        return { ok: response.ok, status: response.status, body: response.d, error: response.error };
      } catch (error) {
        return { ok: false, status: null, error: String(error) };
      }
    };
    const permissions = value => {
      const mask = value?.EffectiveBasePermissions ?? value;
      if (!/^-?\d+$/.test(String(mask?.Low)) || !/^-?\d+$/.test(String(mask?.High))) return null;
      const bits = (BigInt(mask.High) & 0xffffffffn) << 32n | (BigInt(mask.Low) & 0xffffffffn);
      const kinds = { ViewListItems: 1, AddListItems: 2, EditListItems: 3, DeleteListItems: 4,
        ManageLists: 12, ManagePermissions: 26, ManageWeb: 31, EnumeratePermissions: 63 };
      return Object.fromEntries(Object.entries(kinds).map(([name, kind]) =>
        [name, (bits & (1n << BigInt(kind - 1))) !== 0n]));
    };
    const acl = async resource => {
      const result = await read(resource + '/RoleAssignments?$expand=Member,RoleDefinitionBindings&$top=100');
      const body = result.body;
      const rows = body?.value ?? body?.results;
      if (result.ok && Array.isArray(rows)) {
        result.partial = Boolean(body['odata.nextLink'] || body['@odata.nextLink'] || body.__next);
        result.assignments = rows.map(row => ({
          principal: row.Member,
          roles: (row.RoleDefinitionBindings?.results ?? row.RoleDefinitionBindings ?? []).map(role => ({
            Id: role.Id, Name: role.Name, RoleTypeKind: role.RoleTypeKind,
            BasePermissions: role.BasePermissions, decoded: permissions(role.BasePermissions),
          })),
        }));
        delete result.body;
      }
      return result;
    };
    const scope = async resource => {
      const [inheritance, effective, assignments] = await Promise.all([
        read(resource + '?$select=HasUniqueRoleAssignments'),
        read(resource + '/EffectiveBasePermissions'), acl(resource),
      ]);
      return { inheritance, effective, decoded: effective.ok ? permissions(effective.body) : null, assignments };
    };
    const library = 'web/lists/getbytitle(' + literal(title.trim()) + ')';
    const entries = await Promise.all([
      read('web/currentuser?$select=Id,Title,LoginName,IsSiteAdmin'),
      read('web/currentuser/groups?$select=Id,Title&$top=100'),
      read('web?$select=MembersCanShare'),
      read('web/AssociatedOwnerGroup?$select=Id,Title'),
      read(library + '?$select=Id,Title,BaseTemplate,RootFolder/ServerRelativeUrl&$expand=RootFolder'),
    ]);
    ['actor', 'actorSharePointGroups', 'webSharingSetting', 'associatedOwners', 'library'].forEach((key, index) => {
      report.reads[key] = entries[index];
    });
    const identityKnown = entries[0].ok && typeof entries[0].body?.IsSiteAdmin === 'boolean';
    const groupBody = entries[1].body;
    const groups = groupBody?.value ?? groupBody?.results;
    const validId = value => Number.isSafeInteger(value) && value > 0;
    const groupsKnown = entries[1].ok && Array.isArray(groups) && groups.every(group => validId(group?.Id)) &&
      !groupBody['odata.nextLink'] && !groupBody['@odata.nextLink'] && !groupBody.__next;
    const ownersId = entries[3].body?.Id;
    const ownersKnown = entries[3].ok && validId(ownersId);
    const onlyDivision = groupsKnown && validId(report.expectedDivisionGroupId) &&
      groups.length === 1 && groups[0].Id === report.expectedDivisionGroupId;
    const ordinary = identityKnown && entries[0].body.IsSiteAdmin === false &&
      onlyDivision && ownersKnown && report.expectedDivisionGroupId !== ownersId;
    record('access.effective-perms.control-current-identity', 'current identity', identityKnown ? 'PASS' : 'FAIL', JSON.stringify(entries[0]));
    if (!identityKnown) {
      voidDependants('access.effective-perms.control-current-identity');
    } else {
      record('access.effective-perms.control-ordinary-actor', 'ordinary observer', ordinary ? 'PASS' : 'FAIL',
        JSON.stringify({ IsSiteAdmin: entries[0].body.IsSiteAdmin, groupsKnown, ownersKnown, ownersId,
          expectedDivisionGroupId: report.expectedDivisionGroupId, onlyDivision }));
      if (!ordinary) {
        for (const row of results) {
          if (row.id === 'library.access.permission-snapshot' || row.state !== 'open') continue;
          row.observed = 'VOID';
          row.state = 'void';
          row.detail = 'ordinary actor not established: requires non-administrator belonging only to the prepared division group, not associated Owners';
        }
      }
    }
    report.reads.libraryScope = await scope(library);
    const root = entries[4].body?.RootFolder?.ServerRelativeUrl;
    report.libraryRootVerified = entries[4].ok && typeof root === 'string' &&
      root.startsWith(web.pathname.replace(/\/$/, '') + '/') &&
      !root.startsWith('//') && !/[?#\\]/.test(root) &&
      !root.split('/').some(part => part === '..' || part === '.') &&
      entries[4].body.BaseTemplate === 101;
    if (!report.libraryRootVerified) {
      voidDependants('library.access.permission-snapshot');
      throw new Error('LIBRARY_ROOT_UNVERIFIED: sharing findings require a verified document-library root');
    }
    const boundary = root;
    for (const path of paths) {
      if (!path.startsWith(boundary + '/') || path.startsWith('//') || /[?#\\]/.test(path) || path.split('/').some(part => part === '..' || part === '.')) {
        throw new Error('INVALID_TARGET: use decoded paths beneath this library; this probe excludes # and ? names');
      }
    }
    report.administratorControl = entries[0].body?.IsSiteAdmin;
    for (const path of paths) {
      const target = { path };
      report.targets.push(target);
      const folder = 'web/GetFolderByServerRelativeUrl(' + literal(path) + ')';
      const file = 'web/GetFileByServerRelativeUrl(' + literal(path) + ')';
      const [folderRead, fileRead] = await Promise.all([
        read(folder + '?$select=Name,ServerRelativeUrl'),
        read(file + '?$select=Name,ServerRelativeUrl'),
      ]);
      Object.assign(target, { folderRead, fileRead });
      const isFolder = folderRead.ok && folderRead.body?.ServerRelativeUrl === path;
      const isFile = fileRead.ok && fileRead.body?.ServerRelativeUrl === path;
      if (isFolder !== isFile) {
        target.kind = isFolder ? 'folder' : 'file';
        target.scope = await scope((isFolder ? folder : file) + '/ListItemAllFields');
      } else {
        target.observation = 'UNRESOLVED: access denied, missing path or ambiguous object type; see HTTP results';
      }
    }
    if (identityKnown) {
      record('library.access.permission-snapshot', 'targeted permission responses', 'CAPTURED', 'see reads and targets; HTTP errors and partial ACL pages remain explicit; this is not a sharing verdict');
      if (ordinary) {
        record('library.access.control-own-file-edit', 'own file edit', 'MANUAL', 'capture successful save and reopen as the ordinary division editor');
        record('library.access.control-recipient-denied', 'recipient baseline', 'MANUAL', 'capture recipient denied access immediately before each sharing attempt');
        record('library.access.division-isolation', 'division isolation', 'MANUAL', 'capture own-division success and other-division denial with administrator-confirmed paths');
        record('library.access.folder-resharing', 'folder sharing', 'MANUAL', 'capture editor sharing action and recipient opening the resulting folder link');
        record('library.access.file-resharing', 'file sharing', 'MANUAL', 'capture editor sharing action and recipient opening the resulting file link after restoring baseline');
      }
    }
  } catch (error) {
    report.errors.push(String(error));
  } finally {
    emit();
  }
})();
