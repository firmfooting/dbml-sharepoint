"""A mock web for the item-versions probes, spliced ahead of a probe under node.

It holds lists and libraries, their fields, folders, files and items, and records a version
of an item on every create and MERGE, and of a file on every content upload unless a test
says otherwise. What a version entry carries is this mock's own invention, shaped so each probe
branch can be reached; the probes record whatever a site answers and never compare it with
this shape.
"""


def mock_list_id(title: str) -> str:
    """The Id the mock gives a list it creates under `title`."""
    return f"00000000-0000-4000-8000-{sum(map(ord, title)):012x}"


VERSIONS_MOCK = r"""
const CONFIG = __CONFIG__;
globalThis.window = { _spPageContextInfo: {
  webAbsoluteUrl: 'https://example.sharepoint.com/sites/probe' } };
const SENT = [];
process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
const answer = (status, payload) => {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
  return { ok: status >= 200 && status < 300, status, headers: { get: () => null },
    text: async () => text, json: async () => JSON.parse(text) };
};
const ME = CONFIG.me || { Id: 7, Email: 'ada@example.com',
  LoginName: 'i:0#.f|membership|ada@example.com', Title: 'Ada Probe' };
const lists = new Map(Object.entries(CONFIG.lists || {}));
// A list Id spelled as a GUID and derived from the title, as mock_list_id derives it.
const guid = (title) => '00000000-0000-4000-8000-'
  + [...title].reduce((sum, c) => sum + c.charCodeAt(0), 0).toString(16).padStart(12, '0');
const folders = new Set();
let digests = 0;
let versionReads = 0;
const KINDS = { 2: 'Text', 4: 'DateTime', 6: 'Choice', 7: 'Lookup', 8: 'Boolean', 9: 'Number',
  15: 'MultiChoice', 20: 'User' };
// `versionEmail` spells a version's person with an email the probe never learned.
const person = (id) => ({ LookupId: id, LookupValue: ME.Title,
  Email: CONFIG.versionEmail === undefined ? ME.Email : CONFIG.versionEmail });
// One version entry as this mock spells it; the omit list lets a test drop a column.
const versionOf = (list, item, n) => {
  // `versionIds` lets a test make the VersionIds fall, or spell them as text.
  const id = CONFIG.versionIds === 'falling' ? (item.history.length - n + 1) * 512 : n * 512;
  // `labelsUnparsed` spells each label so it is not major.minor.
  const label = CONFIG.labelsUnparsed ? `v${n}` : `${n}.0`;
  const entry = { VersionId: CONFIG.versionIds === 'text' ? String(id) : id, VersionLabel: label,
    IsCurrentVersion: n === item.history.length, Modified: `2026-09-30T0${n}:00:00Z`,
    Editor: person(ME.Id) };
  for (const [name, value] of Object.entries(item.history[n - 1])) {
    if ((CONFIG.versionsOmit || []).includes(name)) continue;
    if (name.endsWith('Id') && name !== 'Id') {
      const column = name.slice(0, -2);
      const field = list.fields[column];
      if (field && (field.TypeAsString === 'User' || field.TypeAsString === 'UserMulti')) {
        entry[column] = Array.isArray(value) ? value.map(person)
          : value === null ? null : person(value);
      } else {
        entry[column] = value === null ? null : { LookupId: value, LookupValue: `target ${value}` };
      }
      continue;
    }
    entry[name] = value;
  }
  return entry;
};
const plain = (body) => {
  const out = {};
  for (const [key, value] of Object.entries(body)) {
    if (key === '__metadata') continue;
    const collection = value && typeof value === 'object' && Array.isArray(value.results);
    out[key] = collection ? value.results : value;
  }
  return out;
};
const orderQuery = (rest) => {
  const query = rest.includes('?') ? rest.slice(rest.indexOf('?') + 1) : '';
  const params = {};
  for (const pair of query.split('&')) {
    const at = pair.indexOf('=');
    if (at > 0) params[pair.slice(0, at)] = pair.slice(at + 1);
  }
  return params;
};
const mockFetch = async (url, opts = {}) => {
  const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
  const verb = (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET';
  const raw = opts.body ? String(opts.body) : '';
  let sent = {};
  try { sent = raw ? JSON.parse(raw) : {}; } catch { sent = {}; }
  SENT.push({ verb, path, body: raw });
  for (const rule of CONFIG.rules || []) {
    if (!path.includes(rule.contains)) continue;
    if (rule.verb && rule.verb !== verb) continue;
    if (rule.bodyContains && !raw.includes(rule.bodyContains)) continue;
    if (rule.reject) throw new TypeError('Failed to fetch');
    return answer(rule.status, rule.text);
  }
  if (path === 'contextinfo') {
    digests += 1;
    if (CONFIG.digestsAllowed !== undefined && digests > CONFIG.digestsAllowed) {
      return answer(403, 'denied');
    }
    return answer(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
  }
  if (path.startsWith('web/currentuser')) return answer(200, ME);
  if (path === 'web/lists' && verb === 'POST') {
    lists.set(sent.Title, { Id: guid(sent.Title), BaseTemplate: sent.BaseTemplate,
      Description: sent.Description, EnableVersioning: false, EnableMinorVersions: false,
      MajorVersionLimit: 50,
      ListItemEntityTypeFullName: `SP.Data.${sent.Title.replace(/ /g, '')}ListItem`,
      root: `/sites/probe/${sent.Title}`, fields: {}, items: [] });
    // `listDefaults`: values a new list starts with, so a refused MERGE can still leave it usable.
    Object.assign(lists.get(sent.Title), CONFIG.listDefaults || {});
    // `createAnswersNoId`: a create whose answer carries no Id, so the read-back supplies it.
    return answer(201, CONFIG.createAnswersNoId ? {} : { Id: guid(sent.Title) });
  }
  if (path === 'web/folders' && verb === 'POST') {
    folders.add(sent.ServerRelativeUrl);
    return answer(201, { ServerRelativeUrl: sent.ServerRelativeUrl });
  }
  // A library's file, found by the server-relative URL its path names.
  const fileAt = (url) => {
    for (const list of lists.values()) {
      const item = (list.items || []).find((one) => one.url === url);
      if (item) return { list, item };
    }
    return null;
  };
  const folderAt = /^web\/GetFolderByServerRelativeUrl\('([^']+)'\)(.*)$/.exec(path);
  if (folderAt) {
    const [, url, tail] = folderAt;
    if (!folders.has(url)) return answer(404, 'File Not Found.');
    const add = /^\/Files\/add\(url='([^']+)',overwrite=(true|false)\)$/.exec(tail);
    if (add && verb === 'POST') {
      const list = [...lists.values()].find((one) => url.startsWith(`${one.root}/`));
      const item = { Id: list.items.length + 1, values: {}, history: [{}], content: raw,
        url: `${url}/${add[1]}` };
      list.items.push(item);
      return answer(200, { Name: add[1], ServerRelativeUrl: item.url });
    }
    return answer(200, { Name: url.slice(url.lastIndexOf('/') + 1), ServerRelativeUrl: url });
  }
  const fileOf = /^web\/GetFileByServerRelativeUrl\('([^']+)'\)(.*)$/.exec(path);
  if (fileOf) {
    const found = fileAt(fileOf[1]);
    if (!found) return answer(404, 'File Not Found.');
    if (fileOf[2] === '/$value' && verb === 'PUT') {
      found.item.content = raw;
      // `uploadSetsValues` and `uploadDropsValues`: an upload that changes or drops a property.
      Object.assign(found.item.values, CONFIG.uploadSetsValues || {});
      for (const name of CONFIG.uploadDropsValues || []) delete found.item.values[name];
      // Whether an upload makes a version is the probe's question; the mock takes either side.
      if (!CONFIG.uploadAddsNoVersion) found.item.history.push({ ...found.item.values });
      return answer(204, '');
    }
    if (fileOf[2] === '/$value') return answer(200, found.item.content);
    if (fileOf[2].startsWith('/ListItemAllFields')) {
      return answer(200, { Id: found.item.Id, ...found.item.values });
    }
    return answer(200, { Name: found.item.url.slice(found.item.url.lastIndexOf('/') + 1) });
  }
  const at = /^web\/lists\/getbytitle\('([^']+)'\)(.*)$/.exec(path);
  const byId = /^web\/lists\(guid'([^']+)'\)(.*)$/.exec(path);
  if (!at && !byId) return answer(404, 'no such endpoint in the mock: ' + path);
  const named = (id) => [...lists.keys()].find((name) => lists.get(name).Id === id);
  const [, title, rest] = at || [null, named(byId[1]), byId[2]];
  const list = lists.get(title);
  if (!list) return answer(404, 'List does not exist.');
  if (rest === '' && verb === 'MERGE') {
    const merged = { ...plain(sent), ...(CONFIG.listMerge || {}),
      ...(list.BaseTemplate === 101 ? CONFIG.libraryMerge || {} : {}) };
    Object.assign(list, merged);
    return answer(204, '');
  }
  if (rest === '' || rest.startsWith('?')) {
    const { fields, items, root, ...shape } = list;
    return answer(200, shape);
  }
  if (rest.startsWith('/RootFolder')) return answer(200, { ServerRelativeUrl: list.root });
  if (rest === '/recycle') { lists.delete(title); return answer(200, {}); }
  if (rest === '/fields' && verb === 'POST') {
    list.fields[sent.Title] = { InternalName: sent.Title, TypeAsString: KINDS[sent.FieldTypeKind] };
    return answer(201, { d: { Title: sent.Title } });
  }
  if (rest === '/fields/addfield' && verb === 'POST') {
    const name = sent.parameters.Title;
    list.fields[name] = { InternalName: name, TypeAsString: 'Lookup' };
    return answer(200, { Title: name });
  }
  if (rest === '/fields/createfieldasxml' && verb === 'POST') {
    const xml = sent.parameters.SchemaXml;
    const name = /Name="([^"]+)"/.exec(xml.replace(/DisplayName="[^"]+"/, ''))[1];
    list.fields[name] = { InternalName: name, TypeAsString: /Type="([^"]+)"/.exec(xml)[1],
      AllowMultipleValues: xml.includes('Mult="TRUE"') };
    return answer(200, { Title: name });
  }
  const field = /^\/fields\/getbyinternalnameortitle\('([^']+)'\)/.exec(rest);
  if (field) {
    const found = list.fields[field[1]];
    if (!found) {
      return answer(400, { 'odata.error': { message: { value: 'Column does not exist.' } } });
    }
    return answer(200, found);
  }
  if (rest === '/items' && verb === 'POST') {
    const values = plain(sent);
    const item = { Id: list.items.length + 1, values, history: [{ ...values }] };
    list.items.push(item);
    return answer(201, { Id: item.Id, Title: values.Title });
  }
  if (rest.startsWith('/items?')) {
    const params = orderQuery(rest);
    let rows = list.items.map((item) => ({ Id: item.Id, ...item.values }));
    const filter = /^Id eq (\d+)$/.exec(params.$filter || '');
    if (filter) rows = rows.filter((row) => row.Id === Number(filter[1]));
    if (params.$orderby === 'Id desc') rows = [...rows].sort((a, b) => b.Id - a.Id);
    if (params.$top) rows = rows.slice(0, Number(params.$top));
    return answer(200, { value: rows });
  }
  const one = /^\/items\((\d+)\)(.*)$/.exec(rest);
  if (one) {
    const item = list.items[Number(one[1]) - 1];
    if (!item) return answer(404, 'Item does not exist.');
    if (one[2] === '' && verb === 'MERGE') {
      Object.assign(item.values, plain(sent));
      item.history.push({ ...item.values });
      return answer(204, '');
    }
    if (one[2].startsWith('/versions')) {
      const params = orderQuery(one[2]);
      versionReads += 1;
      // Keeping only the newest versions is this mock's fiction; `trimAfterReads` delays it.
      const keep = CONFIG.keepVersions || (CONFIG.trimToLimit ? list.MajorVersionLimit : null);
      const trimming = keep !== null && versionReads > (CONFIG.trimAfterReads || 0);
      const first = trimming ? Math.max(1, item.history.length - keep + 1) : 1;
      let entries = [];
      for (let n = item.history.length; n >= first; n -= 1) entries.push(versionOf(list, item, n));
      if (CONFIG.versionsAscending) entries.reverse();
      if (!CONFIG.versionsIgnoreOptions) {
        const gt = /^VersionId gt (\d+)$/.exec(params.$filter || '');
        if (gt) entries = entries.filter((entry) => entry.VersionId > Number(gt[1]));
        const order = /^VersionId (asc|desc)$/.exec(params.$orderby || '');
        const sign = order && order[1] === 'asc' ? 1 : -1;
        if (order) entries.sort((a, b) => sign * (a.VersionId - b.VersionId));
        if (params.$top) entries = entries.slice(0, Number(params.$top));
      }
      return answer(200, { value: entries });
    }
    return answer(200, { Id: item.Id, ...item.values });
  }
  return answer(404, 'no such endpoint in the mock: ' + path);
};
globalThis.fetch = mockFetch;
if (CONFIG.unprojected) {
  // A site that ignores $select, so this case replaces the prelude's projecting accessor.
  Object.defineProperty(globalThis, 'fetch',
    { configurable: true, writable: true, value: mockFetch });
}
"""
