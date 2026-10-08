"""A mock web for file-move-probe.js, spliced ahead of the probe under node.

It holds one library with its folders, one file and its item, and one site user per account.
What it answers is this mock's own invention, shaped so each branch of each leg is reached;
the probe records whatever a site answers and never compares it with this shape.
`CONFIG.move` decides what a move does to the item, so a kept Id, a new Id, an added version
and a changed Editor are each reachable.
"""

FILE_MOVE_MOCK = r"""
const CONFIG = __CONFIG__;
globalThis.window = { _spPageContextInfo: {
  webAbsoluteUrl: 'https://example.sharepoint.com/sites/probe',
  webServerRelativeUrl: '/sites/probe', userId: CONFIG.me || 7 } };
const SENT = [];
process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
const answer = (status, payload) => {
  const text = typeof payload === 'string' ? payload : JSON.stringify(payload);
  return { ok: status >= 200 && status < 300, status, headers: { get: () => null },
    text: async () => text, json: async () => JSON.parse(text) };
};
const ROOT = '/sites/probe/dbmlspProbeFileMove';
const OWNED = 'dbml-sharepoint file move probe. Safe to delete.';
const LIBRARY_ID = '0b6c4c7e-1d2a-4b8f-9c3e-5a7d2f1e8b90';
const S = Object.assign({ library: false, description: OWNED, fields: [], folders: [], file: null,
  grants: [], links: [], recycle: [], unique: false }, CONFIG.state || {});
const USERS = { 7: 'owner@example.com', 8: 'editor@example.com', 9: 'mover@example.com',
  10: 'other@example.com' };
const me = CONFIG.me || 7;
// The OData string literal after `key=`, its doubled apostrophes undone.
const decoded = (url, key) => {
  const found = url.match(new RegExp(`${key}='((?:[^']|'')*)'`));
  return found ? found[1].replace(/''/g, "'") : '';
};
const userOf = (login) => Number(Object.keys(USERS).find((k) => login.endsWith(USERS[k])) || 0);
const READ = 1073741826;
const itemOf = (f) => {
  const item = { Id: f.id, FileRef: f.path, MoveChoice: null, MovePersonId: null, MoveDate: null,
    MoveFlag: null, MoveLink: null, ...f.values,
    Created: f.created, AuthorId: f.author, Modified: f.modified, EditorId: f.editor,
    HasUniqueRoleAssignments: S.unique };
  for (const name of (f.moved ? CONFIG.omitAfter : CONFIG.omitBefore) || []) delete item[name];
  return item;
};
const LIST = "web/lists/getbytitle('dbmlsp Probe FileMove')";
const refused = (why) => answer(500, { error: { message: { value: why } } });
globalThis.fetch = async (url, opts = {}) => {
  const method = (opts.headers && opts.headers['X-HTTP-Method']) || opts.method || 'GET';
  const sent = decodeURIComponent(String(url).split('/_api/')[1] || '');
  SENT.push({ verb: method, path: sent });
  // The library by Id answers as the library by title does.
  const path = sent.replace(/^web\/lists\(guid'[^']+'\)/, LIST);
  const body = opts.body && typeof opts.body === 'string' && opts.body.startsWith('{')
    ? JSON.parse(opts.body) : opts.body;
  if (path.startsWith('contextinfo')) {
    return answer(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
  }
  if (path.startsWith('web/currentuser')) {
    return answer(200, { Id: me, Email: USERS[me], LoginName: `i:0#.f|membership|${USERS[me]}`,
      Title: `User ${me}` });
  }
  if (path.startsWith('web/ensureuser')) {
    const id = userOf(body.logonName);
    return id ? answer(200, { Id: id }) : answer(404, { error: 'no user' });
  }
  if (path.startsWith('web/siteusers/getbyloginname(@v)')) {
    const id = userOf(decoded(path, '@v'));
    return id ? answer(200, { Id: id }) : answer(404, { error: 'no user' });
  }
  if (path.startsWith('web/roledefinitions/getbytype(2)')) return answer(200, { Id: READ });
  if (path === 'web/lists' && method === 'POST') {
    S.library = true; S.description = body.Description;
    return answer(201, { Id: LIBRARY_ID, BaseTemplate: 101 });
  }
  if (path.startsWith('web/Folders/AddUsingPath')) {
    S.folders.push(decoded(path, 'decodedurl')); return answer(201, {});
  }
  if (path.startsWith(LIST)) {
    const rest = path.slice(LIST.length);
    if (!S.library) return answer(404, { error: 'List does not exist' });
    if (rest.startsWith('/recycle')) { S.library = false; return answer(200, {}); }
    if (rest.startsWith('/fields/createfieldasxml')) {
      S.fields.push(body.parameters.SchemaXml); return answer(201, {});
    }
    if (rest.startsWith('/RootFolder?')) {
      if (CONFIG.rootRefused) return refused('no root');
      return answer(200, CONFIG.rootUrlMissing ? {} : { ServerRelativeUrl: ROOT });
    }
    if (rest.startsWith('/items?')) {
      return answer(200, { value: S.file ? [{ Id: S.file.id }] : [] });
    }
    const item = rest.match(/^\/items\((\d+)\)(.*)$/);
    if (item) {
      const f = S.file && Number(item[1]) === S.file.id ? S.file : null;
      const tail = item[2];
      if (!f) return answer(404, { error: 'Item does not exist' });
      if (tail.startsWith('/versions')) {
        return answer(200, { value: f.versions.map((v) => (
          CONFIG.versionsUnlabelled && f.moved ? {} : { VersionLabel: v })) });
      }
      if (tail.startsWith('/breakroleinheritance')) { S.unique = true; return answer(200, {}); }
      if (tail.startsWith('/roleassignments/addroleassignment')) {
        S.grants.push(Number(tail.match(/principalid=(\d+)/)[1])); return answer(200, {});
      }
      if (tail.startsWith('/roleassignments') && CONFIG.grantsRefused) {
        return refused('cannot read grants');
      }
      if (tail.startsWith('/roleassignments')) {
        const roles = S.grantRoles || {};
        return answer(200, { value: S.grants.map((p) => ({ PrincipalId: p,
          RoleDefinitionBindings: (roles[p] || [READ]).map((Id) => ({ Id })) })) });
      }
      if (tail.startsWith('/ShareLink')) {
        if (CONFIG.linkRefused) return refused('sharing is off');
        S.links.push('https://example.sharepoint.com/:t:/s/probe/link');
        return answer(200, { sharingLinkInfo: { Url: S.links[0] } });
      }
      if (tail.startsWith('/GetSharingInformation')) {
        const links = S.links.map((u) => ({ linkDetails: { Url: u } }));
        if (CONFIG.linksShape === 'nested') {
          return answer(200, { permissionsInformation: { links } });
        }
        if (CONFIG.linksShape === 'none') return answer(200, { canShare: true });
        return answer(200, { links });
      }
      if (method === 'MERGE') {
        const verbose = String(opts.headers['Content-Type']).includes('odata=verbose');
        const link = body.MoveLink && body.MoveLink.__metadata;
        const typed = verbose && body.__metadata && link && link.type === 'SP.FieldUrlValue';
        if (body.MoveLink && !typed) {
          return refused('untyped URL value');
        }
        const { __metadata, ...plain } = body;
        if (CONFIG.dropsDate) delete plain.MoveDate;
        if (CONFIG.dropsEdit) delete plain.MoveChoice;
        Object.assign(f.values, plain);
        f.editor = me; f.versions.push(`${f.versions.length + 1}.0`);
        return answer(204, '');
      }
      if (method === 'DELETE') { S.file = null; return answer(200, {}); }
      return answer(200, itemOf(f));
    }
    return answer(200, { Id: LIBRARY_ID, BaseTemplate: 101, EnableVersioning: true,
      ListItemEntityTypeFullName: 'SP.Data.DbmlspProbeFileMoveItem',
      Title: 'dbmlsp Probe FileMove', Description: S.description });
  }
  if (path.startsWith('web/GetFolderByServerRelativePath')) {
    const folder = decoded(path, 'decodedurl');
    const known = S.folders.includes(folder);
    if (path.includes('/Files/AddUsingPath')) {
      S.file = { id: 41, path: `${folder}/${decoded(path, 'DecodedUrl')}`, values: {},
        versions: ['1.0'], created: '2026-10-01T00:00:00Z', author: me,
        modified: '2026-10-01T00:00:00Z', editor: me };
      return answer(201, { Name: decoded(path, 'DecodedUrl') });
    }
    if (path.includes('/recycle')) {
      if (CONFIG.recycleRefused) return refused('cannot recycle');
      S.folders = S.folders.filter((x) => x !== folder);
      S.recycle.push({ Id: 'bin-1', LeafName: folder.split('/').pop(), DirName: ROOT.slice(1) });
      return answer(200, CONFIG.recycleNoId ? {} : { value: 'bin-1' });
    }
    if (!known) return answer(404, { error: 'File Not Found.' });
    if (path.includes('/ListItemAllFields')) {
      return answer(200, { AuthorId: S.folderAuthor === undefined ? 7 : S.folderAuthor });
    }
    const inside = S.file && S.file.path.startsWith(`${folder}/`) ? 1 : 0;
    if (path.includes('/Files')) return answer(200, { value: inside ? [{ Name: 'x' }] : [] });
    if (path.includes('/Folders')) return answer(200, { value: [] });
    return answer(200, { Name: folder.split('/').pop(), ItemCount: inside });
  }
  if (path.startsWith('web/GetFileByServerRelativePath')) {
    const file = decoded(path, 'decodedurl');
    if (!S.file || S.file.path !== file) return answer(404, { error: 'File Not Found.' });
    if (path.includes('/MoveToUsingPath')) {
      if (CONFIG.moveRefused) return refused('move refused');
      const move = CONFIG.move || {};
      S.file.path = body.newPath.DecodedUrl;
      S.file.moved = true;
      if (move.newId) S.file.id = 99;
      if (move.dropsLabel) S.file.versions = S.file.versions.slice(1);
      if (move.addsVersion) S.file.versions.push(`${S.file.versions.length + 1}.0`);
      if (move.editorBecomesMover) { S.file.editor = me; S.file.modified = '2026-10-07T00:00:00Z'; }
      if (move.dropsValues) S.file.values = {};
      if (move.reordersLink) {
        const { Url, Description } = S.file.values.MoveLink;
        S.file.values.MoveLink = { Description, Url };
      }
      if (move.dropsUnique) { S.unique = false; S.grants = []; }
      if (move.readBecomesEdit) S.grantRoles = { 8: [1073741827] };
      return answer(200, {});
    }
    if (path.includes('/ListItemAllFields')) {
      if (CONFIG.afterReadRefused && S.file.moved) return refused('cannot read');
      return answer(200, itemOf(S.file));
    }
    return answer(200, { Name: file.split('/').pop() });
  }
  if (path.startsWith('web/RecycleBin(')) {
    const id = (path.match(/^web\/RecycleBin\('([^']*)'\)/) || [])[1];
    const entry = S.recycle.find((e) => e.Id === id);
    if (path.endsWith('/restore()')) {
      if (CONFIG.restoreRefused) return refused('cannot restore');
      if (!entry) return answer(404, { error: 'no such entry' });
      S.recycle = S.recycle.filter((e) => e !== entry);
      S.folders.push(`/${entry.DirName}/${entry.LeafName}`);
      return answer(200, {});
    }
    if (CONFIG.binRefused) return refused('cannot read the bin');
    return entry ? answer(200, entry) : answer(404, { error: 'no such entry' });
  }
  return answer(404, { error: `unrouted ${path}` });
};
"""
