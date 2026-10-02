"""A mock web for item-access-probe.js: the versions mock plus role assignments.

The versions mock answers lists, digests and the current user. This adds what the probe
asks of a securable: inheritance, role assignments, effective permissions, groups, levels
and the test user. How each call behaves is this mock's own invention, with a switch per
branch; the probe records whatever a site answers and never compares it with this shape.
"""

from _versions_mock import VERSIONS_MOCK

ITEM_ACL_MOCK = VERSIONS_MOCK + r"""
const LEVELS = { 1073741825: ['Limited Access', 0n, 1n],
  1073741826: ['Read', 176n, 138612833n],
  1073741829: ['Full Control', 2147483647n, 4294967295n] };
const USER = { Id: 20, LoginName: 'i:0#.f|membership|tess@example.com', Title: 'Tess Probe',
  IsSiteAdmin: Boolean(CONFIG.userIsAdmin) };
// Every scope by key: 'web', a list's title, or `${title}|${item Id}`.
const scopes = new Map([['web', { unique: true,
  bindings: [{ principal: 3, level: 1073741829 }] }]]);
const scopeOf = (key) => {
  if (!scopes.has(key)) scopes.set(key, { unique: false, bindings: [] });
  return scopes.get(key);
};
const parentOf = (key) => (key === 'web' ? null : key.includes('|') ? key.split('|')[0] : 'web');
const effective = (key) => (scopeOf(key).unique ? scopeOf(key).bindings
  : effective(parentOf(key)));
const row = (b) => ({ PrincipalId: b.principal,
  Member: { Title: `principal ${b.principal}`, PrincipalType: b.principal === USER.Id ? 1 : 8 },
  RoleDefinitionBindings: [{ Id: b.level, Name: LEVELS[b.level][0] }] });
let nextGroup = 11;
// Groups and levels this run or a seeded STATE 1 made, by name, as getbyname answers them.
const named = { sitegroups: new Map(), roledefinitions: new Map() };
const LIB = 'dbmlsp Probe ItemAccess';
const OWNED = 'dbml-sharepoint item-access probe fixture. Safe to delete.';
const FOREIGN = 'somebody else\'s';
// `heldNames`: by collection, names somebody else already holds on the site.
for (const [collection, names] of Object.entries(CONFIG.heldNames || {})) {
  for (const [at, name] of names.entries()) {
    named[collection].set(name, { Id: 900 + at, Description: FOREIGN });
  }
}
// `stateOne`: what a STATE 1 run leaves, so a STATE 2 or CLEANUP run has something to find.
if (CONFIG.stateOne) {
  const root = `/sites/probe/${LIB}`;
  const files = ['item-access-c1.txt', 'item-access-c6.txt', 'item-access-c3.txt'];
  // `foreignLibrary`, `foreignLevel`: the library or level under the probe's name is another's.
  lists.set(LIB, { Id: guid(LIB), Title: LIB, BaseTemplate: 101,
    Description: CONFIG.foreignLibrary ? FOREIGN : OWNED, root,
    fields: {}, items: files.map((name, at) => ({ Id: at + 1, values: { FileLeafRef: name },
      history: [{}], url: `${root}/${name}` })) });
  LEVELS[1073741930] = ['dbmlsp ItemAccess No Delete', 432n, 134419047n];
  named.roledefinitions.set('dbmlsp ItemAccess No Delete', { Id: 1073741930,
    Description: CONFIG.foreignLevel ? FOREIGN : OWNED });
  // `foreignGroups`: groups under the probe's names whose description is somebody else's.
  const description = CONFIG.foreignGroups ? FOREIGN : OWNED;
  for (const [at, key] of ['A', 'B', 'C'].entries()) {
    named.sitegroups.set(`dbmlsp ItemAccess ${key}`, { Id: 11 + at, Description: description });
  }
  const groups = [{ principal: 3, level: 1073741829 }, { principal: 11, level: 1073741826 },
    { principal: 12, level: 1073741930 }, { principal: 13, level: 1073741826 }];
  const limited = { principal: 20, level: 1073741825 };
  scopes.set(LIB, { unique: true, bindings: [...groups, limited] });
  scopes.get('web').bindings.push(limited);
  scopes.set(`${LIB}|1`, { unique: true, bindings: groups.slice(0, 3) });
  scopes.set(`${LIB}|3`, { unique: true,
    bindings: [...groups, { principal: 20, level: 1073741930 }] });
}
// `ignore`: the writes, by the call they name, that answer 200 and store nothing.
const ignored = (call) => (CONFIG.ignore || []).includes(call);
const COPY = new RegExp("^web/GetFileByServerRelativeUrl\\('(?:[^']|'')+'\\)"
  + "/copyto\\(strnewurl='((?:[^']|'')+)'");
const ADD = /^web\/GetFolderByServerRelativeUrl\('((?:[^']|'')+)'\)\/Files\/add\(url='([^']+)'/;
const SCOPE = new RegExp("^web(?:/lists(?:/getbytitle\\('((?:[^']|'')+)'\\)|\\(guid'([^']+)'\\))"
  + '(?:/items\\((\\d+)\\))?)?(.*)$');
// `virtualClock`: each wait the probe makes advances a clock of the mock's own by `tickMs`.
if (CONFIG.virtualClock) {
  let now = 0;
  Date.now = () => now;
  globalThis.setTimeout = (fn) => { now += CONFIG.tickMs || 2000; setImmediate(fn); return 0; };
}
// Whether a binding is visible yet, for a grant given a delay by `libraryGrantMs` or `fileGrantMs`.
const visible = (b) => !b.visibleAt || b.visibleAt <= Date.now();
let malformed = false;
const GRANT = new RegExp('^/roleassignments/(add|remove)roleassignment'
  + '\\(principalid=(\\d+),roledefid=(\\d+)\\)$');
const aclFetch = async (url, opts = {}) => {
  const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
  const verb = (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET';
  const raw = opts.body ? String(opts.body) : '';
  let sent = {};
  try { sent = raw ? JSON.parse(raw) : {}; } catch { sent = {}; }
  const mine = (status, payload) => {
    SENT.push({ verb, path, body: raw });
    return answer(status, payload);
  };
  // `malformedAfter`: once a request holding this text is seen, assignments carry no levels.
  if (CONFIG.malformedAfter && path.includes(CONFIG.malformedAfter)) malformed = true;
  // `throttle`: every GET whose path holds this text is answered 429, echoing the URL as sent.
  if (CONFIG.throttle && verb === 'GET' && path.includes(CONFIG.throttle)) {
    return mine(429, `throttled: ${String(url)}`);
  }
  if (path === 'web/roledefinitions' && verb === 'POST') {
    const { High, Low } = sent.BasePermissions;
    // `levelAddsDelete`: a create that stores DeleteListItems beside the bits it was sent.
    const extra = CONFIG.levelAddsDelete ? 8n : 0n;
    LEVELS[1073741930] = [sent.Name, BigInt(High), BigInt(Low) | extra];
    // `createDropsDescription`: a group or level create that stores no description.
    named.roledefinitions.set(sent.Name, { Id: 1073741930,
      Description: CONFIG.createDropsDescription ? '' : sent.Description });
    return mine(201, { Id: 1073741930 });
  }
  if (path.startsWith("web/roledefinitions/getbyname('Read')")) {
    return mine(200, { Id: 1073741826 });
  }
  const byName = /^web\/(sitegroups|roledefinitions)\/getbyname\('((?:[^']|'')+)'\)/.exec(path);
  if (byName) {
    const held = named[byName[1]].get(unquote(byName[2]));
    if (held) return mine(200, held);
    // An absent level's getbyname answers 500, as deploy/_security_principals.js.j2 records.
    return byName[1] === 'sitegroups' ? mine(404, 'Group cannot be found.')
      : mine(500, 'Cannot find the role definition.');
  }
  const filtered = /^web\/roledefinitions\?.*\$filter=Name eq '((?:[^']|'')+)'$/.exec(path);
  if (filtered) {
    const held = named.roledefinitions.get(unquote(filtered[1]));
    // `levelTwice`: the level's name is held by two levels, as SharePoint allows.
    const rows = !held ? [] : CONFIG.levelTwice ? [held, { ...held, Id: held.Id + 1 }] : [held];
    return mine(200, { value: rows });
  }
  const levelAt = /^web\/roledefinitions\((\d+)\)(\?.*)?$/.exec(path);
  if (levelAt && verb === 'DELETE') {
    // `ignore` naming 'deleterole' or 'removebyid': a delete that answers 200 and removes nothing.
    if (!ignored('deleterole')) {
      for (const [name, held] of named.roledefinitions) {
        if (held.Id === Number(levelAt[1])) named.roledefinitions.delete(name);
      }
    }
    return mine(200, {});
  }
  if (levelAt) {
    const bits = LEVELS[Number(levelAt[1])];
    return bits ? mine(200, { BasePermissions: { High: String(bits[1]), Low: String(bits[2]) } })
      : mine(404, 'Cannot find the role definition.');
  }
  if (path === 'web/sitegroups' && verb === 'POST') {
    nextGroup += 1;
    named.sitegroups.set(sent.Title, { Id: nextGroup - 1,
      Description: CONFIG.createDropsDescription ? '' : sent.Description });
    return mine(201, { Id: nextGroup - 1, Title: sent.Title });
  }
  const removeById = /^web\/sitegroups\/removebyid\((\d+)\)/.exec(path);
  if (removeById) {
    if (!ignored('removebyid')) {
      for (const [name, held] of named.sitegroups) {
        if (held.Id === Number(removeById[1])) named.sitegroups.delete(name);
      }
    }
    return mine(200, {});
  }
  if (path === 'web/ensureuser') return mine(200, USER);
  const copy = COPY.exec(path);
  const add = ADD.exec(path);
  if (copy || add) {
    const target = copy ? unquote(copy[1]) : `${unquote(add[1])}/${add[2]}`;
    const list = [...lists.values()].find((one) => target.startsWith(`${one.root}/`));
    if (!list) return mine(404, 'File Not Found.');
    const name = target.slice(target.lastIndexOf('/') + 1);
    list.items.push({ Id: list.items.length + 1, values: { FileLeafRef: name }, history: [{}],
      url: target });
    return mine(200, { Name: name, ServerRelativeUrl: target });
  }
  const at = SCOPE.exec(path);
  if (!at) return mockFetch(url, opts);
  const [, byTitle, byId, item, tail] = at;
  const found = byId === undefined ? null : [...lists.values()].find((one) => one.Id === byId);
  if (byId !== undefined && !found) return mockFetch(url, opts);
  const title = found ? found.Title : byTitle === undefined ? undefined : unquote(byTitle);
  const key = title === undefined ? 'web' : item === undefined ? title : `${title}|${item}`;
  if (tail.startsWith('/items?') && item === undefined && title !== undefined) {
    const list = lists.get(title);
    return mine(200, { value: list.items.map((one) => ({ Id: one.Id,
      FileLeafRef: one.values.FileLeafRef,
      HasUniqueRoleAssignments: scopeOf(`${list.Title}|${one.Id}`).unique })) });
  }
  if (tail === '?$select=HasUniqueRoleAssignments') {
    // `fileFlagInheriting`: a file's flag reads false whatever its scope holds.
    if (CONFIG.fileFlagInheriting && key.includes('|')) {
      return mine(200, { HasUniqueRoleAssignments: false });
    }
    return mine(200, { HasUniqueRoleAssignments: scopeOf(key).unique });
  }
  const broke = /^\/breakroleinheritance\(copyRoleAssignments=(true|false)/.exec(tail);
  if (broke) {
    // `breakCopiesNothing`: a file's break that copies no binding, whatever it asked.
    const copied = broke[1] === 'true' && !(CONFIG.breakCopiesNothing && key.includes('|'));
    // `breakCopiesTwinLevel`: a file's break copies the custom level as another of its name.
    const twin = CONFIG.breakCopiesTwinLevel && key.includes('|');
    if (twin) LEVELS[1073741931] = [...LEVELS[1073741930]];
    const bindings = copied ? effective(key).map((b) => ({ ...b,
      level: twin && b.level === 1073741930 ? 1073741931 : b.level })) : [];
    // `bindingsLag`: this many reads of a scope's bindings answer what it held before.
    scopes.set(key, { unique: true, bindings, lag: CONFIG.bindingsLag || 0, stale: [] });
    return mine(200, {});
  }
  if (tail === '/resetroleinheritance') {
    if (ignored('resetroleinheritance')) return mine(200, {});
    // `resetKeepsUser`: a reset that leaves the user's direct grant readable on the file.
    const kept = CONFIG.resetKeepsUser
      ? scopeOf(key).bindings.filter((b) => b.principal === USER.Id) : [];
    scopes.set(key, { unique: false, bindings: kept, keptOnReset: kept.length > 0,
      lag: CONFIG.bindingsLag || 0, stale: effective(key) });
    // `resetDropsLimitedAccess`: a file's reset takes the user's Limited Access off the library.
    if (CONFIG.resetDropsLimitedAccess && key.includes('|')) {
      const up = scopeOf(parentOf(key));
      up.bindings = up.bindings.filter((b) => b.principal !== USER.Id || b.level !== 1073741825);
    }
    return mine(200, {});
  }
  const grant = GRANT.exec(tail);
  if (grant) {
    const binding = { principal: Number(grant[2]), level: Number(grant[3]) };
    const scope = scopeOf(key);
    // `fileGrantIgnored`: a grant on a file that answers 200 and stores nothing.
    if (grant[1] === 'add' && CONFIG.fileGrantIgnored && key.includes('|')) return mine(200, {});
    if (grant[1] === 'remove') {
      if (!ignored('removeroleassignment')) {
        scope.bindings = scope.bindings.filter((b) => b.principal !== binding.principal
          || b.level !== binding.level);
      }
      return mine(200, {});
    }
    const onLibrary = !key.includes('|') && key !== 'web';
    scope.bindings.push(onLibrary && CONFIG.libraryGrantMs
      ? { ...binding, visibleAt: Date.now() + CONFIG.libraryGrantMs } : binding);
    // `grantReachesBrokenFiles`: a library grant that also lands on every file with its own scope.
    if (CONFIG.grantReachesBrokenFiles && onLibrary) {
      for (const [other, held] of scopes) {
        if (other.startsWith(`${key}|`) && held.unique) {
          held.bindings.push({ ...binding, visibleAt: Date.now() + (CONFIG.fileGrantMs || 0) });
        }
      }
    }
    // A user's grant on a file leaves Limited Access at the library and the web.
    if (binding.principal === USER.Id && key.includes('|')) {
      for (const up of [parentOf(key), 'web']) {
        scopeOf(up).bindings.push({ principal: USER.Id, level: 1073741825 });
      }
    }
    return mine(200, {});
  }
  if (tail.startsWith('/roleassignments?')) {
    const scope = scopeOf(key);
    if (scope.lag > 0) {
      scope.lag -= 1;
      return mine(200, { value: scope.stale.map(row) });
    }
    const held = (scope.keptOnReset ? [...effective(parentOf(key)), ...scope.bindings]
      : effective(key)).filter(visible);
    if (malformed) {
      const bare = held.map((b) => ({ PrincipalId: b.principal, Member: row(b).Member }));
      return mine(200, { value: bare });
    }
    return mine(200, { value: held.map(row) });
  }
  const by = /^\/roleassignments\/getbyprincipalid\((\d+)\)\/roledefinitionbindings/.exec(tail);
  if (by) {
    // `levelsMalformed`: a principal's levels answered 200 with no value array.
    if (CONFIG.levelsMalformed) return mine(200, {});
    const levels = effective(key).filter((b) => b.principal === Number(by[1]));
    if (!levels.length) return mine(404, 'Can not find the principal with id');
    return mine(200, { value: levels.map((b) => ({ Name: LEVELS[b.level][0] })) });
  }
  if (tail.startsWith('/getusereffectivepermissions(@user)')) {
    // `userAlreadyReads`: the test user holds Read through a group this mock does not model.
    let high = CONFIG.userAlreadyReads ? 176n : 0n;
    let low = CONFIG.userAlreadyReads ? 138612833n : 0n;
    for (const b of effective(key)) {
      if (b.principal !== USER.Id) continue;
      high |= LEVELS[b.level][1];
      low |= LEVELS[b.level][2];
    }
    return mine(200, { High: String(high), Low: String(low) });
  }
  return mockFetch(url, opts);
};
globalThis.fetch = aclFetch;
"""
