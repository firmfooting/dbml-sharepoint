"""A mock web for version-editor-email-probe.js, spliced ahead of it under node.

It answers the requests the probe makes and nothing else. The Editor and
person shapes are this mock's own, chosen so each branch is reached; the
probe records the relations a site answers and never compares them with
these values. A read answers the nometadata shape and a write the verbose
one, as the probe asks for each.
"""

EDITOR_MOCK = r"""
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
const SECOND = { Id: 12, Title: 'Second Probe' };
const user = CONFIG.user || { Email: 'second@example.com',
  UserPrincipalName: 'second.login@example.onmicrosoft.com',
  LoginName: 'i:0#.f|membership|second.login@example.onmicrosoft.com' };
const editor = CONFIG.editor || { LookupId: 12, LookupValue: SECOND.Title, Email: user.Email };
const person = CONFIG.person === undefined
  ? { LookupId: 12, LookupValue: SECOND.Title, Email: user.Email } : CONFIG.person;
const LIST = "getbytitle('dbml-probe-version-editor')";
// `existing` is 'owned' (an earlier run's list, with the probe's marker) or 'foreign'.
const OWNER = 'dbml-sharepoint version-editor-email probe scratch list. Safe to delete.';
const LIST_ID = '00000000-0000-4000-8000-000000000abc';
const BY_ID = `lists(guid'${LIST_ID}')`;
let standing = CONFIG.existing === 'foreign' ? { Description: 'A list the probe did not make.' }
  : CONFIG.existing ? { Description: OWNER } : null;
const itemId = CONFIG.itemId || 1;
const older = CONFIG.older || { LookupId: 7, LookupValue: 'Ada Probe', Email: 'ada@example.com' };
// `field` overrides what the person column's definition reads back as.
const field = { InternalName: 'ProbePerson', TypeAsString: 'User', FieldTypeKind: 20,
  AllowMultipleValues: false, ...(CONFIG.field || {}) };
const missing = () => answer(404, { error: { message: { value: 'List does not exist.' } } });
// Everything under the list, whether it was addressed by title or by Id.
const underList = (rest, method, tunnelled) => {
  if (!standing) return missing();
  if (rest.startsWith('/recycle')) {
    standing = null;
    return answer(200, { d: { Recycle: 'ok' } });
  }
  if (rest.startsWith('/items?')) return answer(200, { value: [] });
  if (rest.includes('/versions')) return answer(200, { value: [
    { VersionId: 1024, VersionLabel: '2.0', Editor: editor, ProbePerson: person },
    { VersionId: 512, VersionLabel: '1.0', Editor: older, ProbePerson: person } ] });
  if (rest.startsWith('/fields/getbyinternalnameortitle(')) return answer(200, field);
  if (rest.startsWith('/fields') && method === 'POST') return answer(201, { d: {
    InternalName: 'ProbePerson', TypeAsString: 'User' } });
  if (rest.startsWith('/items') && method === 'POST') return answer(201, { d: { Id: itemId,
    ProbePersonId: SECOND.Id } });
  const read = /^\/items\((\d+)\)/.exec(rest);
  if (read) return answer(200, { Id: Number(read[1]), ProbePersonId: SECOND.Id });
  if (method === 'POST' && tunnelled === 'MERGE') return answer(204, '');
  return answer(200, { Id: LIST_ID, Title: 'dbml-probe-version-editor',
    Description: standing.Description, EnableVersioning: true,
    ListItemEntityTypeFullName: 'SP.Data.ProbeListItem' });
};
globalThis.fetch = async (url, init = {}) => {
  const path = String(url).replace(/^https:\/\/example\.sharepoint\.com\/sites\/probe/, '');
  const method = init.method || 'GET';
  const tunnelled = (init.headers || {})['X-HTTP-Method'];
  SENT.push({ method, path });
  if (CONFIG.refuse && path.includes(CONFIG.refuse)) return answer(403, { error: {
    message: { value: 'Access denied.' } } });
  if (path.endsWith('/_api/contextinfo')) return answer(200, { d: {
    GetContextWebInformation: { FormDigestValue: 'digest' } } });
  if (path.includes('/ensureuser')) return answer(200, { d: { Id: SECOND.Id,
    Email: user.Email, LoginName: user.LoginName } });
  // `accountId` is the Id the sign-in name resolves to, when a test makes it another user's.
  if (path.includes('/siteusers/getbyloginname(')) return answer(200, {
    Id: CONFIG.accountId || SECOND.Id });
  if (path.includes('/siteusers/getbyid(')) return answer(200, { Id: SECOND.Id, ...user });
  if (path.endsWith('/_api/web/lists') && method === 'POST') {
    // `raced` has another actor take the title between the absence read and the create.
    if (CONFIG.raced) {
      standing = { Description: 'A list the probe did not make.' };
      return answer(500, { error: { message: { value: 'That title is taken.' } } });
    }
    standing = { Description: JSON.parse(init.body).Description };
    return answer(201, { d: { Id: LIST_ID, Title: 'dbml-probe-version-editor' } });
  }
  for (const head of [BY_ID, LIST]) {
    const at = path.indexOf(head);
    if (at >= 0) return underList(path.slice(at + head.length), method, tunnelled);
  }
  return answer(404, { error: { message: { value: `mock has no ${method} ${path}` } } });
};
"""
