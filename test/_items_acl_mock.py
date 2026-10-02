"""A mock web for items-role-assignments-probe.js: the versions mock plus item bindings.

The versions mock answers lists, fields, digests, item MERGEs and the current user. This
adds what the probe asks of a library's items: files added to its root folder, paged reads
with an `odata.nextLink`, each item's role assignments expanded or not, per-item breaks,
grants and binding reads, and a page that answers an error with a Retry-After header. How
each call behaves is this mock's own invention, with a switch per branch; the probe records
whatever a site answers and never compares it with this shape.
"""

from _versions_mock import VERSIONS_MOCK

ITEMS_ACL_MOCK = VERSIONS_MOCK + r"""
// The library's bindings, which an inheriting item answers and a break copies.
const LIBRARY = [{ principal: 3, level: 1073741829 }, { principal: 5, level: 1073741826 }];
const LEVEL_NAMES = { 1073741826: 'Read', 1073741829: 'Full Control' };
const LOGINS = { 3: 'Probe Owners', 5: 'Probe Members', [ME.Id]: ME.LoginName };
// Items with their own bindings, by Id; every other item inherits LIBRARY.
const unique = new Map();
const bindingsOf = (id) => unique.get(id) || LIBRARY;
// Bindings as a roleassignments read answers them: one entry per principal.
const assignments = (bindings) => [...new Set(bindings.map((b) => b.principal))].map((p) => ({
  PrincipalId: p, Member: { PrincipalType: p === ME.Id ? 1 : 8, LoginName: LOGINS[p] },
  RoleDefinitionBindings: bindings.filter((b) => b.principal === p)
    .map((b) => ({ Id: b.level, Name: LEVEL_NAMES[b.level] })) }));
// Page reads so far that hold the `failPage.query` text.
let pageReads = 0;
const headed = (res, headers) => ({ ...res,
  headers: { get: (name) => headers[name.toLowerCase()] ?? null } });
const ITEMS = /^web\/lists(?:\/getbytitle\('((?:[^']|'')+)'\)|\(guid'([^']+)'\))\/items(.*)$/;
const ADD = /^web\/GetFolderByServerRelativeUrl\('((?:[^']|'')+)'\)\/Files\/add\(url='([^']+)'/;
const GRANT = /^\/roleassignments\/addroleassignment\(principalid=(\d+),roledefid=(\d+)\)$/;
const itemsFetch = async (url, opts = {}) => {
  const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
  const verb = (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET';
  const mine = (status, payload) => {
    SENT.push({ verb, path, body: opts.body ? String(opts.body) : '' });
    return answer(status, payload);
  };
  // A path a `rules` entry names goes to the versions mock, which applies the rule.
  const ruled = (CONFIG.rules || []).some((rule) => path.includes(rule.contains));
  if (ruled) return mockFetch(url, opts);
  if (path.startsWith("web/roledefinitions/getbyname('Read')")) {
    return mine(200, { Id: 1073741826 });
  }
  // A file added to a library's root folder, which the versions mock answers only in a subfolder.
  const add = ADD.exec(path);
  const into = add && [...lists.values()].find((one) => one.root === unquote(add[1]));
  if (into) {
    // `filesKept`: how many adds are stored; every later one answers 200 and stores nothing.
    if (CONFIG.filesKept === undefined || into.items.length < CONFIG.filesKept) {
      into.items.push({ Id: into.items.length + 1, values: {}, history: [{}],
        url: `${into.root}/${add[2]}` });
    }
    return mine(200, { Name: add[2], ServerRelativeUrl: `${into.root}/${add[2]}` });
  }
  const at = ITEMS.exec(path);
  if (!at) return mockFetch(url, opts);
  const list = at[1] !== undefined ? lists.get(unquote(at[1]))
    : [...lists.values()].find((one) => one.Id === at[2]);
  if (!list) return mockFetch(url, opts);
  const tail = at[3];
  if (tail.startsWith('?')) {
    const reads = !CONFIG.failPage || path.includes(CONFIG.failPage.query);
    if (reads) pageReads += 1;
    // `failPage`: the nth page read holding `query` answers `status`, `text` and `retryAfter`,
    // or, with `reject`, never answers.
    if (reads && CONFIG.failPage && CONFIG.failPage.page === pageReads) {
      const failed = CONFIG.failPage;
      SENT.push({ verb, path, body: '' });
      if (failed.reject) throw new TypeError('Failed to fetch');
      return headed(answer(failed.status, failed.text),
        failed.retryAfter ? { 'retry-after': failed.retryAfter } : {});
    }
    const after = Number((/p_ID=(\d+)/.exec(tail) || [0, 0])[1]);
    const top = Number((/\$top=(\d+)/.exec(tail) || [0, 100])[1]);
    const ordered = [...list.items].sort((a, b) => a.Id - b.Id).filter((one) => one.Id > after);
    const page = ordered.slice(0, top);
    // `expand`: 'every' item carries its bindings (the default), 'none', 'firstPage' only, or
    // 'inheritedEmpty', where an inheriting item carries an empty array.
    const mode = CONFIG.expand || 'every';
    const carries = tail.includes('RoleAssignments') && mode !== 'none'
      && (mode !== 'firstPage' || after === 0);
    const rows = page.map((item) => {
      const row = { Id: item.Id, HasUniqueRoleAssignments: unique.has(item.Id) };
      const owner = item.values.ProbeOwnerId === undefined ? null : item.values.ProbeOwnerId;
      if (tail.includes('ProbeOwner/Name')) {
        row.ProbeOwner = owner === null ? null : { Name: ME.LoginName };
      } else if (tail.includes('ProbeOwnerId')) row.ProbeOwnerId = owner;
      if (carries) {
        row.RoleAssignments = mode === 'inheritedEmpty' && !unique.has(item.Id)
          ? [] : assignments(bindingsOf(item.Id));
      }
      return row;
    });
    const rest = tail.slice(1).replace(/^\$skiptoken=Paged=TRUE&p_ID=\d+&/, '');
    // `nextLoops`: a read holding this text links every page back to the first, so only the
    // probe's page cap stops it.
    const loops = Boolean(CONFIG.nextLoops) && path.includes(CONFIG.nextLoops);
    const token = loops ? 0 : page.length ? page[page.length - 1].Id : after;
    const link = 'https://example.sharepoint.com/sites/probe/_api/web/lists/'
      + `getbytitle('${list.Title}')/items?%24skiptoken=Paged%3dTRUE%26p_ID%3d${token}&${rest}`;
    const more = loops || ordered.length > page.length;
    return mine(200, { value: rows, ...(more ? { 'odata.nextLink': link } : {}) });
  }
  const one = /^\((\d+)\)(.*)$/.exec(tail);
  if (!one) return mockFetch(url, opts);
  const id = Number(one[1]);
  const item = list.items.find((each) => each.Id === id);
  if (!item) return mockFetch(url, opts);
  const rest = one[2];
  if (rest.startsWith('?')) {
    return mine(200, { HasUniqueRoleAssignments: unique.has(id),
      ProbeOwnerId: item.values.ProbeOwnerId === undefined ? null : item.values.ProbeOwnerId });
  }
  if (rest.startsWith('/breakroleinheritance(copyRoleAssignments=true')) {
    unique.set(id, LIBRARY.map((b) => ({ ...b })));
    return mine(200, {});
  }
  const grant = GRANT.exec(rest);
  if (grant) {
    if (!unique.has(id)) return mine(400, 'This operation is not allowed on an inheriting item.');
    unique.get(id).push({ principal: Number(grant[1]), level: Number(grant[2]) });
    return mine(200, {});
  }
  if (rest.startsWith('/roleassignments?')) {
    return mine(200, { value: assignments(bindingsOf(id)) });
  }
  return mockFetch(url, opts);
};
globalThis.fetch = itemsFetch;
"""
