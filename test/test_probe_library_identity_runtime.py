"""Run the probes that measure a document library found by title (#559, items 9 and 12).

Each of them reused its library by title, or read `BaseTemplate` and never
compared it, while every finding it records is phrased "on a document
library". A generic list under the same name accepts the fileless item POST
`document-library-probe.js`'s headline refusal rests on, so a reused list of
the wrong kind produced confident findings about libraries that were really
about lists.

Each probe now reads the library back through `establishFixture` with
`BaseTemplate: 101` before anything measures against it. Every probe is run
healthy, on the create path and the reuse path where it has both, and then
with a generic list (BaseTemplate 100) under the library's name, which must
void exactly the rows that rest on the library and send none of their writes.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

WINDOW = (
    "globalThis.window = { _spPageContextInfo: "
    "{ webAbsoluteUrl: 'https://example.sharepoint.com/sites/test' }, "
    "location: { origin: 'https://example.sharepoint.com' } };\n"
)

#: A fetch response, a record of every request, and waits that cost nothing.
_RESPONSES = textwrap.dedent("""
    const SENT = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));
    const jsonResponse = (status, payload) => ({
      ok: status >= 200 && status < 300,
      status,
      headers: { get: () => 'Thu, 24 Sep 2026 09:00:00 GMT' },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    const spError = (status, message) => jsonResponse(status, {
      'odata.error': { message: { lang: 'en-US', value: message } } });
    const realSetTimeout = setTimeout;
    globalThis.setTimeout = (fn, ms, ...rest) => realSetTimeout(fn, 0, ...rest);
""")

#: A site holding the scratch containers the five item-12 probes create or
#: reuse. Only the calls those probes send on a healthy run are answered.
_SITE_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const ROOT = '/sites/test';
    // Settings every list reads before list-settings-probe writes to it.
    const DEFAULTS = {
      EnableAttachments: true, EnableVersioning: false, EnableMinorVersions: false,
      EnableModeration: false, EnableFolderCreation: false, NoCrawl: false,
      Direction: 'none', ContentTypesEnabled: false, ReadSecurity: 1,
      WriteSecurity: 1, IrmEnabled: false, IrmExpire: false, IrmReject: false,
    };
    const OWNERS = 3;
    const FULL_CONTROL = 1073741829;
    const lists = new Map();
    let nextList = 1;
    const addList = (title, baseTemplate, description) => {
      const n = nextList;
      nextList += 1;
      const id = `0000000${n}-0000-4000-8000-00000000000${n}`;
      const fields = new Map([['Title', { InternalName: 'Title', TypeAsString: 'Text' }]]);
      if (baseTemplate === 101) {
        fields.set('FileLeafRef', { InternalName: 'FileLeafRef', TypeAsString: 'File' });
      }
      const list = {
        id, title, baseTemplate, rootUrl: `${ROOT}/${title.replace(/ /g, '')}`,
        props: { ...DEFAULTS, Description: description || '' },
        fields, items: new Map(), nextItem: 1, views: new Map(), unique: false,
        grants: [], formatter: '',
      };
      lists.set(title, list);
      return list;
    };
    for (const [title, baseTemplate] of Object.entries(CONFIG.lists || {})) {
      addList(title, baseTemplate, 'left by an earlier run');
    }
    const byId = (guid) => [...lists.values()].find(
      (l) => l.id === String(guid).replace(/[{}]/g, '').toLowerCase());
    const entity = (list) => ({
      Id: list.id, Title: list.title, BaseTemplate: list.baseTemplate,
      ItemCount: list.items.size, HasUniqueRoleAssignments: list.unique, ...list.props,
    });
    const addRow = (list, row) => {
      const id = list.nextItem;
      list.nextItem += 1;
      const full = { Id: id, ID: id, Title: null, HasUniqueRoleAssignments: false, grants: [],
                     ...row };
      list.items.set(id, full);
      return full;
    };
    const fileRow = (list, name, folder) => addRow(list, {
      FileLeafRef: name, FileRef: `${list.rootUrl}${folder ? `/${folder}` : ''}/${name}`,
      FileSystemObjectType: 0, FSObjType: 0 });
    const folderAt = (url) => {
      const bare = String(url);
      for (const list of lists.values()) {
        if (bare === list.title || bare === list.rootUrl) return { list, sub: null };
        if (bare.startsWith(`${list.rootUrl}/`)) {
          return { list, sub: bare.slice(list.rootUrl.length + 1) };
        }
      }
      return null;
    };
    const selectOf = (rest) => {
      const m = /[?&]\\$select=([^&]*)/.exec(rest);
      return m ? m[1].split(',') : null;
    };
    const expandOf = (rest) => {
      const m = /[?&]\\$expand=([^&]*)/.exec(rest);
      return m ? m[1].split(',') : [];
    };
    const withLookups = (list, row, expand) => {
      const out = { ...row };
      delete out.grants;
      for (const name of expand) {
        const field = list.fields.get(name);
        if (!field || field.TypeAsString !== 'Lookup') continue;
        const target = byId(field.LookupList);
        const hit = target && target.items.get(out[`${name}Id`]);
        out[name] = hit ? { Title: hit.Title, FileLeafRef: hit.FileLeafRef } : null;
      }
      return out;
    };
    // The names an item write may carry: its fields, and a lookup's Id twin.
    const writable = (list, name) => list.fields.has(name)
      || (name.endsWith('Id')
          && (list.fields.get(name.slice(0, -2)) || {}).TypeAsString === 'Lookup');
    const noProperty = (name) => spError(400,
      `The property '${name}' does not exist on type 'SP.Data.ListItem'.`);
    // The lookup threshold, 12 by default, as threshold-index-probe measured it on a list.
    const LOOKUP_THRESHOLD = 12;
    const BINDING = { Id: FULL_CONTROL, Name: 'Full Control' };
    const bindings = (grants) => grants.map((principal) => ({
      PrincipalId: principal, RoleDefinitionBindings: [BINDING] }));

    const onList = async (list, rest, verb, sent, raw, headers) => {
      const select = selectOf(rest);
      if (rest === '' || rest.startsWith('?')) {
        if (verb === 'MERGE') {
          for (const [name, value] of Object.entries(sent)) {
            if (name === '__metadata') continue;
            if (!(name in list.props)) {
              return spError(400, `The property '${name}' does not exist on type 'SP.List'.`);
            }
            list.props[name] = value;
          }
          return jsonResponse(204, {});
        }
        const whole = entity(list);
        const missing = (select || []).find((name) => !(name in whole));
        if (missing) {
          return spError(400, `The property '${missing}' does not exist on type 'SP.List'.`);
        }
        return jsonResponse(200, whole);
      }
      if (rest.startsWith('/RootFolder/Files/add(')) {
        const name = /url='([^']+)'/.exec(rest)[1];
        fileRow(list, name, null);
        return jsonResponse(200, { Name: name, ServerRelativeUrl: `${list.rootUrl}/${name}` });
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: list.rootUrl });
      }
      if (rest.startsWith('/breakroleinheritance')) {
        list.unique = true;
        list.grants = [];
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/resetroleinheritance')) {
        list.unique = false;
        return jsonResponse(200, {});
      }
      const grant = /^\\/roleassignments\\/addroleassignment\\(principalid=(\\d+),roledefid=(\\d+)/
        .exec(rest);
      if (grant) {
        // The live status for an unknown principal is unrecorded; any refusal serves the control.
        if (Number(grant[1]) !== OWNERS || Number(grant[2]) !== FULL_CONTROL) {
          return spError(500, 'Value does not fall within the expected range.');
        }
        list.grants.push(OWNERS);
        return jsonResponse(200, {});
      }
      if (rest.startsWith('/roleassignments')) {
        if (/verbose/.test(headers.Accept || '')) {
          return jsonResponse(200, { d: { results: list.grants.map((p) => ({
            PrincipalId: p, RoleDefinitionBindings: { results: [BINDING] } })) } });
        }
        return jsonResponse(200, { value: bindings(list.grants) });
      }
      const item = /^\\/items\\((\\d+)\\)(.*)$/.exec(rest);
      if (item) {
        const row = list.items.get(Number(item[1]));
        if (!row) return spError(404, 'Item does not exist.');
        const tail = item[2];
        if (tail.startsWith('/breakroleinheritance')) {
          row.HasUniqueRoleAssignments = true;
          row.grants = [];
          return jsonResponse(200, {});
        }
        if (tail.startsWith('/resetroleinheritance')) {
          row.HasUniqueRoleAssignments = false;
          return jsonResponse(200, {});
        }
        if (tail.startsWith('/roleassignments/addroleassignment')) {
          row.grants.push(OWNERS);
          return jsonResponse(200, {});
        }
        if (tail.startsWith('/roleassignments')) {
          if (/verbose/.test(headers.Accept || '')) {
            return jsonResponse(200, { d: { results: [] } });
          }
          return jsonResponse(200, { value: bindings(row.grants) });
        }
        if (verb === 'MERGE') {
          for (const [name, value] of Object.entries(sent)) {
            if (!writable(list, name)) return noProperty(name);
            const field = list.fields.get(name.slice(0, -2));
            // Measured 2026-09-07: a list's lookup into a library cannot be set by MERGE.
            if (field && field.TypeAsString === 'Lookup' && list.baseTemplate !== 101
                && byId(field.LookupList).baseTemplate === 101) {
              return spError(500, 'Invalid lookup value.');
            }
            row[name] = value;
          }
          return jsonResponse(204, {});
        }
        return jsonResponse(200, withLookups(list, row, expandOf(tail)));
      }
      if (rest.startsWith('/items')) {
        if (verb === 'POST') {
          const unknown = Object.keys(sent).find((name) => !writable(list, name));
          if (unknown) return noProperty(unknown);
          if (list.baseTemplate === 101) {
            return spError(500, 'To add an item to a document library, use SPFileCollection.Add()');
          }
          const row = addRow(list, { ...sent });
          return jsonResponse(201, { Id: row.Id, Title: row.Title });
        }
        const filter = /\\$filter=(\\w+) eq '([^']*)'/.exec(rest);
        const rows = [...list.items.values()]
          .filter((row) => !filter || String(row[filter[1]]) === filter[2])
          .map((row) => withLookups(list, row, []));
        return jsonResponse(200, { value: rows });
      }
      const field = /^\\/fields\\/getby(?:internalnameortitle|title)\\('([^']+)'\\)/.exec(rest);
      if (field) {
        const held = list.fields.get(field[1]);
        if (!held) {
          return spError(400, `Column '${field[1]}' does not exist. It may have been deleted `
            + 'by another user.');
        }
        if (verb === 'MERGE') {
          if ('Indexed' in sent) held.Indexed = sent.Indexed === true;
          return jsonResponse(204, {});
        }
        if (/verbose/.test(headers.Accept || '')) {
          const type = `SP.Field${held.TypeAsString}`;
          return jsonResponse(200, { d: { ...held, __metadata: { type } } });
        }
        return jsonResponse(200, held);
      }
      if (rest === '/fields/createfieldasxml') {
        const xml = sent.parameters.SchemaXml;
        const attr = (name) => (new RegExp(`${name}="([^"]*)"`).exec(xml) || [])[1];
        const name = attr('Name');
        if (list.fields.has(name)) return spError(500, 'A duplicate field name was found.');
        const type = attr('Type');
        const formula = /<Formula>=\\[([^\\]]+)\\]<\\/Formula>/.exec(xml);
        if (type === 'Calculated' && formula
            && (list.fields.get(formula[1]) || {}).TypeAsString === 'Lookup') {
          return spError(500, 'One or more column references are not allowed, because the columns '
            + 'are defined as a data type that is not supported in formulas.');
        }
        list.fields.set(name, {
          InternalName: name, Title: attr('DisplayName'), TypeAsString: type, Indexed: false,
          ...(type === 'Lookup' ? { LookupList: attr('List'), LookupField: attr('ShowField'),
                                    AllowMultipleValues: false } : {}),
        });
        return jsonResponse(201, { InternalName: name, TypeAsString: type });
      }
      if (rest === '/views') {
        list.views.set(sent.Title, { Title: sent.Title, ViewQuery: sent.ViewQuery, fields: [] });
        return jsonResponse(201, { Title: sent.Title });
      }
      const view = /^\\/views\\/getbytitle\\('([^']+)'\\)\\/viewfields(.*)$/.exec(rest);
      if (view) {
        const held = list.views.get(view[1]);
        if (!held) return spError(400, 'The specified view is invalid.');
        const add = /addviewfield\\('([^']+)'\\)/.exec(view[2]);
        if (add) {
          if (!list.fields.has(add[1])) return spError(400, `Column '${add[1]}' does not exist.`);
          held.fields.push(add[1]);
          return jsonResponse(200, {});
        }
        return jsonResponse(200, { Items: ['DocIcon', 'LinkFilename', ...held.fields],
                                   SchemaXml: '<FieldRef Name="DocIcon" />' });
      }
      if (rest.startsWith('/defaultview')) {
        return jsonResponse(200, { Id: 'view-1', Title: 'All Documents',
          ViewQuery: '<OrderBy><FieldRef Name="FileLeafRef" /></OrderBy>',
          ListViewXml: '<View Name="{view-1}" DefaultView="TRUE" />' });
      }
      const ctRead = /^\\/contenttypes\\('([^']+)'\\)/.exec(rest);
      if (ctRead) {
        if (verb === 'MERGE') {
          list.formatter = sent.ClientFormCustomFormatter;
          return jsonResponse(204, {});
        }
        return jsonResponse(200, { ClientFormCustomFormatter: list.formatter });
      }
      if (rest.startsWith('/contenttypes')) {
        return jsonResponse(200, { value: [
          { Id: { StringValue: '0x0120001122' }, Name: 'Folder' },
          { Id: { StringValue: '0x0101003344' }, Name: 'Document' },
        ] });
      }
      if (rest === '/RenderListDataAsStream') {
        const parameters = sent.parameters || {};
        const xml = String(parameters.ViewXml || '');
        const named = [...xml.matchAll(/FieldRef Name=["']([^"']+)["']/g)].map((m) => m[1]);
        const absent = named.find((name) => !list.fields.has(name)
          && !['FileLeafRef', 'FileRef', 'ID'].includes(name));
        if (absent) return spError(500, `Field or property "${absent}" does not exist.`);
        const lookups = named.filter(
          (name) => (list.fields.get(name) || {}).TypeAsString === 'Lookup');
        if (lookups.length > LOOKUP_THRESHOLD) {
          return spError(500, 'The query cannot be completed because the number of lookup columns '
            + 'it contains exceeds the lookup column threshold enforced by the administrator.');
        }
        const Row = [...list.items.values()].map((row) => {
          const out = { ID: String(row.Id), FileLeafRef: row.FileLeafRef,
                        FSObjType: String(row.FSObjType) };
          for (const name of named) out[name] = row[name] === undefined ? '' : row[name];
          return out;
        });
        return jsonResponse(200, { Row });
      }
      return spError(404, `unrouted ${verb} ${rest}`);
    };

    globalThis.fetch = async (url, opts = {}) => {
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const verb = headers['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });
      let sent = {};
      try { sent = raw ? JSON.parse(raw) : {}; } catch { sent = {}; }

      if (path.startsWith('contextinfo')) {
        return jsonResponse(200, {
          d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      if (path === 'web/lists' && method === 'POST') {
        const made = addList(sent.Title, sent.BaseTemplate, sent.Description);
        return jsonResponse(201, { Id: made.id, Title: made.title });
      }
      if (path.startsWith('web/associatedownergroup')) {
        return jsonResponse(200, { Id: OWNERS, Title: 'Probe Site Owners' });
      }
      const folder = new RegExp("^web/GetFolderByServerRelativeUrl\\\\('([^']+)'\\\\)"
        + "/(Files|folders)/add\\\\(url='([^']+)'").exec(path);
      if (folder) {
        const at = folderAt(folder[1]);
        if (!at) return spError(404, 'File Not Found.');
        if (folder[2] === 'folders') {
          addRow(at.list, { FileLeafRef: folder[3], FileSystemObjectType: 1, FSObjType: 1 });
        } else {
          fileRow(at.list, folder[3], at.sub);
        }
        return jsonResponse(200, { Name: folder[3],
                                   ServerRelativeUrl: `${at.list.rootUrl}/${folder[3]}` });
      }
      const named = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/.exec(path);
      if (named) {
        const list = lists.get(named[1].replace(/''/g, "'"));
        if (!list) {
          return spError(404, `List '${named[1]}' does not exist at site with URL '${ROOT}'.`);
        }
        return onList(list, named[2], verb, sent, raw, headers);
      }
      return spError(404, `unrouted ${verb} ${path}`);
    };
""")


def _probe_js(name: str, gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES")) -> str:
    """The committed probe with its write gates opened and its result table dumped."""
    js = (MANUAL / name).read_text(encoding="utf-8")
    for gate in gates:
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    exposed = js.replace(
        "  const report = () => {\n",
        "  const report = () => {\n    console.log('__ROWS__' + JSON.stringify(RESULTS));\n",
        1,
    )
    assert exposed != js, "the result table dump did not splice into report()"
    return exposed


def _last(output: str, marker: str) -> Any:
    lines = [ln for ln in output.splitlines() if ln.startswith(marker)]
    assert lines, f"nothing was printed after {marker}:\n{output[-3000:]}"
    return json.loads(lines[-1].removeprefix(marker))


def _run(mock: str, config: dict[str, Any], name: str,
         gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"),
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    script = (WINDOW + _RESPONSES + mock.replace("__CONFIG__", json.dumps(config))
              + "\n" + _probe_js(name, gates))
    output = run_node(script)
    rows = {row["id"]: row for row in _last(output, "__ROWS__")}
    return rows, list(_last(output, "__SENT__"))


def _voided(rows: dict[str, dict[str, str]]) -> set[str]:
    return {row_id for row_id, row in rows.items() if row["state"] == "void"}


def _writes(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    """Every request that is not a read or a digest."""
    return [r for r in sent if r["verb"] != "GET" and not r["path"].startswith("contextinfo")]


def _assert_generic_list_voids(
    rows: dict[str, dict[str, str]], fixture: str, dependents: set[str],
) -> None:
    held = rows[fixture]
    assert held["outcome"] == "FAIL", held
    assert "BaseTemplate differs: read 100, declared 101" in held["evidence"], held
    assert _voided(rows) == dependents
    assert all(fixture in rows[row_id]["evidence"] for row_id in dependents)


def _catalog_dependents(probe: str, fixture: str) -> set[str]:
    """The rows the catalogue says rest on `fixture`, which the run must void exactly."""
    catalog = json.loads((MANUAL / "probe-catalog.json").read_text(encoding="utf-8"))
    descriptor = next(p for p in catalog["probes"] if p["file"] == probe)
    return {finding["id"] for scenario in descriptor["scenarios"]
            for finding in scenario["findings"] if fixture in finding["depends_on"]}


# --------------------------------------------------------------------------
# Item 12: the five probes that create or reuse their own library.
# --------------------------------------------------------------------------
DOC_LIB = "library.doc-lib.fixture-library-created"
_CREATED_OR_REUSED = pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])

_DOCUMENT_LIBRARY = "dbmlsp Probe DocLib"
_DOCUMENT_LIBRARY_ROWS = {
    "library.file-vs-item.control-missing-column-refused",
    "library.file-vs-item.fileless-item-post",
    "library.file-vs-item.fileless-item-readback",
    "library.file-vs-item.fileless-item-visible",
    "library.file-vs-item.title-after-upload",
    "library.doc-lib.view-fileleafref",
    "library.doc-lib.header-fileleafref",
}


@_CREATED_OR_REUSED
def test_document_library_probe_measures_on_a_library_it_read_back(reused: bool) -> None:
    lists = {_DOCUMENT_LIBRARY: 101} if reused else {}
    rows, sent = _run(_SITE_MOCK, {"lists": lists}, "document-library-probe.js")

    assert rows[DOC_LIB]["outcome"] == "PASS", rows[DOC_LIB]
    assert "BaseTemplate=101" in rows[DOC_LIB]["evidence"]
    assert rows["library.file-vs-item.fileless-item-post"]["outcome"] == "REFUSED, AND SAYS WHY"
    assert rows["library.file-vs-item.title-after-upload"]["outcome"].startswith("TITLE IS EMPTY")
    assert rows["library.doc-lib.header-fileleafref"]["outcome"] == "STORED"
    assert not _voided(rows)
    assert [r for r in _writes(sent) if r["path"].endswith("/items")]


def test_document_library_probe_voids_its_rows_on_a_generic_list_of_the_same_name() -> None:
    """A generic list ACCEPTS the fileless POST, which would invert the headline."""
    rows, sent = _run(_SITE_MOCK, {"lists": {_DOCUMENT_LIBRARY: 100}}, "document-library-probe.js")

    _assert_generic_list_voids(rows, DOC_LIB, _DOCUMENT_LIBRARY_ROWS)
    assert not _writes(sent)


_ACCESS_LIBRARY = "dbmlsp Probe LibAccess"
_ACCESS_ROWS = {
    "library.access.control-missing-column-refused",
    "library.access.unique-permissions-library",
    "library.access.role-assignment-library",
    "library.access.file-scoped-unique-permission",
}


@_CREATED_OR_REUSED
def test_library_access_probe_measures_on_a_library_it_read_back(reused: bool) -> None:
    lists = {_ACCESS_LIBRARY: 101} if reused else {}
    rows, sent = _run(_SITE_MOCK, {"lists": lists}, "library-access-probe.js")

    assert rows[DOC_LIB]["outcome"] == "PASS", rows[DOC_LIB]
    assert rows["library.access.control-missing-column-refused"]["outcome"] == "PASS"
    assert rows["library.access.unique-permissions-library"]["outcome"] == "SAME AS LIST"
    assert rows["library.access.file-scoped-unique-permission"]["outcome"] == "SAME AS LIST"
    assert not _voided(rows)
    assert [r for r in _writes(sent) if "breakroleinheritance" in r["path"]]


def test_library_access_probe_voids_its_rows_on_a_generic_list_of_the_same_name() -> None:
    rows, sent = _run(_SITE_MOCK, {"lists": {_ACCESS_LIBRARY: 100}}, "library-access-probe.js")

    _assert_generic_list_voids(rows, DOC_LIB, _ACCESS_ROWS)
    assert not _writes(sent)


_VIEW_LIBRARY = "dbmlsp Probe LibView"
_VIEW_ROWS = {
    "library.view.control-missing-column-refused",
    "library.view.group-by-metadata-column",
    "library.view.group-by-folder",
}


@_CREATED_OR_REUSED
def test_library_view_probe_measures_on_a_library_it_read_back(reused: bool) -> None:
    lists = {_VIEW_LIBRARY: 101} if reused else {}
    rows, sent = _run(_SITE_MOCK, {"lists": lists}, "library-view-probe.js")

    assert rows[DOC_LIB]["outcome"] == "PASS", rows[DOC_LIB]
    assert rows["library.view.control-missing-column-refused"]["outcome"] == "PASS"
    assert rows["library.view.group-by-metadata-column"]["outcome"] == "SAME AS LIST"
    assert not _voided(rows)
    assert [r for r in _writes(sent) if "/Files/add(" in r["path"]]


def test_library_view_probe_voids_its_rows_on_a_generic_list_of_the_same_name() -> None:
    rows, sent = _run(_SITE_MOCK, {"lists": {_VIEW_LIBRARY: 100}}, "library-view-probe.js")

    _assert_generic_list_voids(rows, DOC_LIB, _VIEW_ROWS)
    assert not _writes(sent)


_CROSS_LIBRARY = "dbmlsp Probe XLookup Lib"


@_CREATED_OR_REUSED
def test_cross_lookup_probe_measures_on_a_library_it_read_back(reused: bool) -> None:
    lists = {_CROSS_LIBRARY: 101} if reused else {}
    rows, sent = _run(_SITE_MOCK, {"lists": lists}, "cross-lookup-probe.js")

    assert rows[DOC_LIB]["outcome"] == "PASS", rows[DOC_LIB]
    assert rows["library.lookup.fixture-containers-ready"]["outcome"] == "PASS"
    assert rows["library.lookup.library-to-list-item-write"]["outcome"] == "HELD"
    assert rows["library.lookup.list-to-library-item-write"]["outcome"] == "REFUSED"
    assert rows["scale.join.library-lookup-ceiling"]["outcome"] == "CEILING 12"
    assert rows["scale.join.list-to-library-costs-a-join"]["outcome"] == "COSTS 1"
    assert not _voided(rows)
    assert [r for r in _writes(sent) if r["path"].endswith("/fields/createfieldasxml")]


def test_cross_lookup_probe_voids_every_catalogued_row_on_a_generic_list_of_its_name() -> None:
    """The run stops before the list-to-list controls too, so no catalogued dependent stays open."""
    rows, sent = _run(_SITE_MOCK, {"lists": {_CROSS_LIBRARY: 100}}, "cross-lookup-probe.js")

    dependents = _catalog_dependents("cross-lookup-probe.js", DOC_LIB)
    assert "library.lookup.control-list-to-list-lookup-created" in dependents
    _assert_generic_list_voids(rows, DOC_LIB, dependents)
    assert not [row_id for row_id, row in rows.items() if row["state"] == "open"]
    assert not _writes(sent)


_SETTINGS_LIST = "dbmlsp Probe ListSettings"
_SETTINGS_LIBRARY = "dbmlsp Probe ListSettings Lib"
_SETTINGS_SETTINGS = (
    "attachments", "versioning", "minor-versions", "moderation", "folder-creation", "nocrawl",
    "direction", "content-types", "irm-enabled", "irm-expire", "irm-reject",
)
_SETTINGS_LIBRARY_ROWS = {
    "library.doc-lib.control-description-sticks",
    "library.doc-lib.control-unknown-property-refused",
    "library.doc-lib.property-enumeration",
    "access.item-acl.read-security-on-library",
    "access.item-acl.write-security-on-library",
    *(f"library.doc-lib.{name}-sticks" for name in _SETTINGS_SETTINGS),
}
_SETTINGS_LIST_ROWS = {
    "field.list.control-description-sticks",
    "field.list.control-unknown-property-refused",
    "field.list.property-enumeration",
    "access.item-acl.read-security-on-list",
    "access.item-acl.write-security-on-list",
    *(f"field.list.{name}-sticks" for name in _SETTINGS_SETTINGS),
}


@_CREATED_OR_REUSED
def test_list_settings_probe_reads_each_container_back_as_its_own_template(reused: bool) -> None:
    lists = {_SETTINGS_LIST: 100, _SETTINGS_LIBRARY: 101} if reused else {}
    rows, sent = _run(_SITE_MOCK, {"lists": lists}, "list-settings-probe.js")

    assert rows["field.list.fixture-scratch-list"]["outcome"] == "PASS"
    assert "BaseTemplate=100" in rows["field.list.fixture-scratch-list"]["evidence"]
    assert rows[DOC_LIB]["outcome"] == "PASS"
    assert "BaseTemplate=101" in rows[DOC_LIB]["evidence"]
    assert rows["library.doc-lib.versioning-sticks"]["outcome"] == "STICKS"
    assert not _voided(rows)
    assert [r for r in _writes(sent) if _SETTINGS_LIBRARY in r["path"]]


def test_list_settings_probe_voids_only_the_library_rows_on_a_generic_list_of_its_name() -> None:
    """The generic list's rows still run; nothing is written to the impostor."""
    rows, sent = _run(_SITE_MOCK, {"lists": {_SETTINGS_LIBRARY: 100}}, "list-settings-probe.js")

    _assert_generic_list_voids(rows, DOC_LIB, _SETTINGS_LIBRARY_ROWS)
    assert rows["field.list.versioning-sticks"]["outcome"] == "STICKS"
    assert not [r for r in _writes(sent) if _SETTINGS_LIBRARY in r["path"]]


def test_list_settings_probe_declares_a_generic_list_where_its_rows_want_one() -> None:
    """The list rows rest on BaseTemplate 100, so a library under the list's name voids them."""
    rows, sent = _run(_SITE_MOCK, {"lists": {_SETTINGS_LIST: 101}}, "list-settings-probe.js")

    held = rows["field.list.fixture-scratch-list"]
    assert held["outcome"] == "FAIL", held
    assert "BaseTemplate differs: read 101, declared 100" in held["evidence"]
    assert _voided(rows) == _SETTINGS_LIST_ROWS
    assert rows["library.doc-lib.versioning-sticks"]["outcome"] == "STICKS"
    assert not [r for r in _writes(sent) if f"'{_SETTINGS_LIST}')" in r["path"]]


# --------------------------------------------------------------------------
# Item 9: the large-list probes, which read a fixture another probe built.
# They have no create path, so the healthy run is the reuse path.
# --------------------------------------------------------------------------
#: The fixture libraries past the threshold. Every filter or render the run
#: sends is refused with the throttle a live run gave unless it is on Id.
_LARGE_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const libs = new Map(Object.entries(CONFIG.libraries));
    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FIELD = /^\\/fields\\/getbyinternalnameortitle\\('([^']+)'\\)$/;
    const throttled = () => jsonResponse(500, { 'odata.error': {
      code: '-2147024860, Microsoft.SharePoint.SPQueryThrottledException',
      message: { lang: 'en-US', value: 'The attempted operation is prohibited because it '
        + 'exceeds the list view threshold.' } } });
    const views = new Map();

    globalThis.fetch = async (url, opts = {}) => {
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const verb = headers['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });
      let sent = {};
      try { sent = raw ? JSON.parse(raw) : {}; } catch { sent = {}; }

      if (path.startsWith('contextinfo')) {
        return jsonResponse(200, {
          d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      const folder = /^web\\/GetFolderByServerRelativeUrl\\('([^']+)'\\)/.exec(path);
      if (folder) {
        const name = folder[1].split('/').pop();
        return jsonResponse(200, { Exists: true, ItemCount: 1752, Name: name });
      }
      const named = LIST.exec(path);
      if (!named) return spError(404, `unrouted ${verb} ${path}`);
      const lib = libs.get(named[1]);
      if (!lib) return spError(404, `List '${named[1]}' does not exist.`);
      const rest = named[2];
      if (rest === '' || rest.startsWith('?')) {
        return jsonResponse(200, { Id: lib.id, Title: named[1], BaseTemplate: lib.baseTemplate,
                                   ItemCount: lib.count });
      }
      if (rest.startsWith('/RootFolder')) return jsonResponse(200, { ServerRelativeUrl: lib.root });
      const field = FIELD.exec(rest);
      if (field) {
        const held = lib.fields[field[1]];
        if (!held) return spError(400, `Column '${field[1]}' does not exist.`);
        if (verb === 'MERGE') {
          const unknown = Object.keys(sent).find(
            (key) => !['__metadata', 'Indexed', 'Description'].includes(key));
          if (unknown) {
            return spError(400, `The property '${unknown}' does not exist on type 'SP.Field'.`);
          }
          Object.assign(held, sent);
          delete held.__metadata;
          return jsonResponse(204, {});
        }
        const body = { InternalName: field[1], AutoIndexed: false, Description: '', ...held };
        if (/verbose/.test(headers.Accept || '')) {
          const type = `SP.Field${held.TypeAsString}`;
          return jsonResponse(200, { d: { ...body, __metadata: { type } } });
        }
        return jsonResponse(200, body);
      }
      if (rest.startsWith('/items')) {
        if (/\\$orderby=Id desc/.test(rest)) {
          return jsonResponse(200, { value: [{ Id: lib.count + 3, FileLeafRef: lib.newest }] });
        }
        const idFilter = /\\$filter=Id eq (\\d+)/.exec(rest);
        if (idFilter) return jsonResponse(200, { value: [{ Id: Number(idFilter[1]) }] });
        return throttled();
      }
      if (rest.startsWith('/views')) {
        const list = views.get(named[1]) || [{ Id: 'v0', Title: 'All Documents', DefaultView: true,
          ViewQuery: '', RowLimit: 30, ServerRelativeUrl: `${lib.root}/Forms/AllItems.aspx` }];
        views.set(named[1], list);
        if (rest === '/views' && verb === 'POST') {
          list.push({ Id: `v${list.length}`, Title: sent.Title, DefaultView: false,
                      ViewQuery: sent.ViewQuery, RowLimit: sent.RowLimit,
                      ServerRelativeUrl: `${lib.root}/Forms/${sent.Title}.aspx` });
          return jsonResponse(201, { Title: sent.Title });
        }
        if (verb !== 'GET') return jsonResponse(200, {});
        return jsonResponse(200, { value: list });
      }
      if (rest === '/RenderListDataAsStream') {
        const xml = String((sent.parameters || {}).ViewXml || '');
        if (/NoSuchColumnAtAll/.test(xml)) return spError(500, 'Field or property does not exist.');
        if (/FieldRef Name=.ID/.test(xml) && /<Where>/.test(xml)) {
          return jsonResponse(200, { Row: [] });
        }
        return throttled();
      }
      return spError(404, `unrouted ${verb} ${rest}`);
    };
""")

_LV_COLUMNS = {
    "LVText": "Text", "LVNumber": "Number", "LVChoice": "Choice", "LVDate": "DateTime",
    "LVMultiChoice": "MultiChoice", "LVLookup": "Lookup", "LVCalc": "Calculated",
}


def _library(count: int, newest: str, root: str, fields: dict[str, dict[str, Any]],
             base_template: int = 101) -> dict[str, Any]:
    return {"id": f"guid-{root}", "baseTemplate": base_template, "count": count,
            "newest": newest, "root": f"/sites/test/{root}", "fields": fields}


def _large_lib(base_template: int = 101) -> dict[str, Any]:
    fields = {name: {"TypeAsString": kind, "Indexed": False} for name, kind in _LV_COLUMNS.items()}
    fields["LVCalc"]["Formula"] = "=[LVNumber]*2"
    return {"dbmlsp Probe LargeLib": _library(
        5500, "dbmlsp-lv-05500.txt", "LargeLib", fields, base_template)}


def _preindex_lib(base_template: int = 101) -> dict[str, Any]:
    return {"dbmlsp Probe PreIndex": _library(5100, "dbmlsp-pre-05100.txt", "PreIndex", {
        "PChoice": {"TypeAsString": "Choice", "Indexed": True,
                    "Description": "dbmlsp preindex: Indexed:true written at 4900 file(s) on "
                                   "2026-09-10"},
        "PNumber": {"TypeAsString": "Number", "Indexed": False},
    }, base_template)}


def _foldered_libs(big: int = 101, small: int = 101) -> dict[str, Any]:
    return {
        "dbmlsp Probe Foldered": _library(5256, "dbmlsp-fld-05256.txt", "Foldered", {
            "PChoice": {"TypeAsString": "Choice", "Indexed": True,
                        "Description": "dbmlsp foldered: Indexed:true written at 4900 file(s) "
                                       "on 2026-09-12"},
            "PNumber": {"TypeAsString": "Number", "Indexed": False},
        }, big),
        "dbmlsp Probe MultiLevel": _library(240, "dbmlsp-ml-00240.txt", "MultiLevel", {
            "MChoice": {"TypeAsString": "Choice", "Indexed": False},
            "MFlag": {"TypeAsString": "Boolean", "Indexed": False},
            "MText": {"TypeAsString": "Text", "Indexed": False},
        }, small),
    }


def _no_query_or_write(sent: list[dict[str, str]]) -> None:
    assert not [r for r in sent if r["verb"] != "GET" or "$filter=" in r["path"]], sent


LARGE_LIST = "library.large-list.fixture-document-library"

#: (probe, the fixtures it reads, the row that reads the fixture's contract).
_LARGE_LIST_PROBES = [
    ("library-large-list-calculated-probe.js", _large_lib,
     "library.large-list.fixture-library-present"),
    ("library-large-list-group-view-probe.js", _large_lib,
     "library.large-list.fixture-library-present"),
    ("library-large-list-multilevel-group-view-probe.js", _large_lib,
     "library.large-list.fixture-library-present"),
    ("library-large-list-index-probe.js", _large_lib,
     "library.large-list.fixture-library-present"),
    ("library-large-list-preindex-group-view-probe.js", _preindex_lib,
     "library.large-list.fixture-preindex-library-present"),
    ("library-large-list-modern-view-probe.js", _preindex_lib,
     "library.large-list.fixture-preindex-library-present"),
]


@pytest.mark.parametrize(("probe", "libraries", "present"), _LARGE_LIST_PROBES,
                         ids=[p[0].removesuffix("-probe.js") for p in _LARGE_LIST_PROBES])
def test_a_large_list_probe_measures_on_a_library_it_read_back(
    probe: str, libraries: Any, present: str,
) -> None:
    """Controls further down may fail against this mock; none may fail in the fixture's name."""
    rows, sent = _run(_LARGE_MOCK, {"libraries": libraries()}, probe)

    assert rows[LARGE_LIST]["outcome"] == "PASS", rows[LARGE_LIST]
    assert "BaseTemplate=101" in rows[LARGE_LIST]["evidence"]
    assert rows[present]["outcome"] == "PASS", rows[present]
    assert not [row_id for row_id, row in rows.items() if LARGE_LIST in row["evidence"]
                and row_id != LARGE_LIST]
    assert [r for r in sent if "/fields/" in r["path"]]


@pytest.mark.parametrize(("probe", "libraries", "present"), _LARGE_LIST_PROBES,
                         ids=[p[0].removesuffix("-probe.js") for p in _LARGE_LIST_PROBES])
def test_a_large_list_probe_voids_its_rows_on_a_generic_list_of_the_fixture_name(
    probe: str, libraries: Any, present: str,
) -> None:
    rows, sent = _run(_LARGE_MOCK, {"libraries": libraries(100)}, probe)

    dependents = _catalog_dependents(probe, LARGE_LIST)
    assert present in dependents
    _assert_generic_list_voids(rows, LARGE_LIST, dependents)
    _no_query_or_write(sent)


FOLDERED = "library.large-list.fixture-foldered-document-library"
MULTILEVEL = "library.large-list.fixture-multilevel-document-library"
_FOLDERED_PROBE = "library-large-list-foldered-group-view-probe.js"


def test_the_foldered_probe_measures_on_two_libraries_it_read_back() -> None:
    rows, sent = _run(_LARGE_MOCK, {"libraries": _foldered_libs()}, _FOLDERED_PROBE)

    for fixture in (FOLDERED, MULTILEVEL):
        assert rows[fixture]["outcome"] == "PASS", rows[fixture]
        assert not [row_id for row_id, row in rows.items() if fixture in row["evidence"]
                    and row_id != fixture]
    assert rows["library.large-list.fixture-foldered-file-count"]["outcome"] == "PASS"
    assert rows["library.large-list.fixture-multilevel-file-count"]["outcome"] == "PASS"
    assert [r for r in sent if r["path"].endswith("/RenderListDataAsStream")]


def test_the_foldered_probe_voids_the_large_library_rows_on_a_generic_list_of_its_name() -> None:
    rows, sent = _run(_LARGE_MOCK, {"libraries": _foldered_libs(big=100)}, _FOLDERED_PROBE)

    _assert_generic_list_voids(rows, FOLDERED, _catalog_dependents(_FOLDERED_PROBE, FOLDERED))
    _no_query_or_write(sent)


def test_the_foldered_probe_voids_the_small_library_rows_on_a_generic_list_of_its_name() -> None:
    """The large library's own fixture rows still read, and nothing is queried on either."""
    rows, sent = _run(_LARGE_MOCK, {"libraries": _foldered_libs(small=100)}, _FOLDERED_PROBE)

    assert rows[FOLDERED]["outcome"] == "PASS"
    assert rows["library.large-list.fixture-foldered-file-count"]["outcome"] == "PASS"
    _assert_generic_list_voids(rows, MULTILEVEL, _catalog_dependents(_FOLDERED_PROBE, MULTILEVEL))
    _no_query_or_write(sent)


# --------------------------------------------------------------------------
# The rendered states, pasted on a page after the setup leg. Each paste finds
# its fixture by title afresh, so it must read the template back itself.
# --------------------------------------------------------------------------
#: A page the probe reads through its DOM instruments. Each element is a leaf
#: carrying its text and the selectors it answers to.
_PAGE = textwrap.dedent("""
    const PAGE = __PAGE__;
    globalThis.window = {
      _spPageContextInfo: { webAbsoluteUrl: 'https://example.sharepoint.com/sites/test',
                            listId: PAGE.listId, currentUICultureName: 'en-US' },
      location: { origin: 'https://example.sharepoint.com', href: PAGE.href },
    };
    const nodes = PAGE.elements.map((e) => ({ sel: e.sel, textContent: e.text, children: [] }));
    const text = nodes.map((n) => n.textContent).join('\\n');
    globalThis.document = {
      title: PAGE.title,
      body: { innerText: text, textContent: text },
      querySelectorAll: (selector) => (selector === '*' ? nodes
        : nodes.filter((n) => selector.split(', ').some((s) => n.sel.includes(s)))),
    };
""")

_GRID = {"sel": ["[data-automationid]", 'div[role="grid"]', '[role="grid"]'], "text": ""}


def _rows(*names: str) -> list[dict[str, Any]]:
    return [{"sel": ['[role="row"]'], "text": name} for name in names]


def _expanders(*texts: str) -> list[dict[str, Any]]:
    return [{"sel": ["[aria-expanded]"], "text": text} for text in texts]


def _run_rendered(probe: str, libraries: dict[str, Any], state: int, list_id: str,
                  elements: list[dict[str, Any]],
                  ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    page = {"listId": list_id, "title": "Documents", "elements": elements,
            "href": "https://example.sharepoint.com/sites/test/Forms/AllItems.aspx"}
    js = _probe_js(probe, ("CONFIRMED",))
    staged = js.replace("  const STATE = 0;", f"  const STATE = {state};", 1)
    assert staged != js, "the STATE constant is not spelled as this test expects"
    script = (_PAGE.replace("__PAGE__", json.dumps(page)) + _RESPONSES
              + _LARGE_MOCK.replace("__CONFIG__", json.dumps({"libraries": libraries}))
              + "\n" + staged)
    output = run_node(script)
    rows = {row["id"]: row for row in _last(output, "__ROWS__")}
    return rows, list(_last(output, "__SENT__"))


_MODERN_PROBE = "library-large-list-modern-view-probe.js"
_PREINDEX_ID = "guid-PreIndex"
#: (state, the page it reads, the row that state settles, the outcome it gives).
_MODERN_STATES = [
    (2, [_GRID, *_rows("dbmlsp-pre-05100.txt", "dbmlsp-pre-05099.txt")],
     "library.large-list.ui-default-view-renders-past-threshold", "RENDERS"),
    (3, [_GRID, *_expanders("PChoice: Alpha (1275)", "PChoice: Beta (1275)")],
     "library.large-list.ui-group-by-indexed-column-renders", "GROUPS AND COUNTS RENDER"),
    (4, [_GRID, *_expanders("PNumber: 1 (5)", "PNumber: 2 (5)")],
     "library.large-list.ui-group-by-unindexed-column-renders", "GROUPS RENDER"),
    (5, [_GRID, {"sel": ['[role="dialog"]'], "text": "Alpha Beta Gamma Delta"}],
     "library.large-list.ui-column-header-filter-past-threshold", "VALUES OFFERED"),
]
_MODERN_IDS = [f"state-{s[0]}" for s in _MODERN_STATES]


@pytest.mark.parametrize(("state", "elements", "measured", "outcome"), _MODERN_STATES,
                         ids=_MODERN_IDS)
def test_the_modern_probe_reads_the_library_back_before_a_rendered_state(
    state: int, elements: list[dict[str, Any]], measured: str, outcome: str,
) -> None:
    rows, sent = _run_rendered(_MODERN_PROBE, _preindex_lib(), state, _PREINDEX_ID, elements)

    assert rows[LARGE_LIST]["outcome"] == "PASS", rows[LARGE_LIST]
    assert "BaseTemplate=101" in rows[LARGE_LIST]["evidence"]
    identity = rows["library.large-list.control-ui-page-identity-matches-fixture"]
    assert identity["outcome"] == "MATCHES", identity
    assert rows[measured]["outcome"] == outcome, rows[measured]
    assert rows[measured]["state"] == "settled"
    assert not _voided(rows)
    _no_query_or_write(sent)


@pytest.mark.parametrize(("state", "elements", "measured"), [s[:3] for s in _MODERN_STATES],
                         ids=_MODERN_IDS)
def test_the_modern_probe_voids_a_rendered_state_on_a_generic_list_of_the_fixture_name(
    state: int, elements: list[dict[str, Any]], measured: str,
) -> None:
    """The page's Id matches the list, so only the template can say it is not the fixture."""
    rows, sent = _run_rendered(_MODERN_PROBE, _preindex_lib(100), state, _PREINDEX_ID, elements)

    _assert_generic_list_voids(rows, LARGE_LIST, _catalog_dependents(_MODERN_PROBE, LARGE_LIST))
    assert rows[measured]["state"] == "void", rows[measured]
    assert [row_id for row_id, row in rows.items() if row["state"] == "settled"] == [LARGE_LIST]
    _no_query_or_write(sent)


def test_the_modern_probe_voids_a_rendered_state_when_the_fixture_does_not_read() -> None:
    rows, sent = _run_rendered(_MODERN_PROBE, {}, 3, _PREINDEX_ID, _MODERN_STATES[1][1])

    held = rows[LARGE_LIST]
    assert held["outcome"] == "FAIL", held
    assert "HTTP 404" in held["evidence"], held
    assert _voided(rows) == _catalog_dependents(_MODERN_PROBE, LARGE_LIST)
    _no_query_or_write(sent)


_FOLDERED_ID = "guid-Foldered"
_MULTILEVEL_ID = "guid-MultiLevel"
#: (state, the fixture it reads, the page's list id, the page, the row it settles, the outcome).
_FOLDERED_STATES = [
    (2, FOLDERED, _FOLDERED_ID,
     [_GRID, *_rows("dbmlsp-fld-00003.txt", "dbmlsp-fld-00006.txt"),
      *_expanders("PChoice: Alpha (40)")],
     "library.large-list.ui-group-by-indexed-column-folder-scoped", "GROUPS AND COUNTS RENDER"),
    (3, MULTILEVEL, _MULTILEVEL_ID,
     [_GRID, *_expanders("MChoice: Alpha (60)", "MFlag: Yes (20)", "MText: mtext-0 (4)")],
     "library.large-list.ui-group-by-multilevel-renders", "3 OF 3 LEVELS RENDER HEADERS"),
]
_FOLDERED_IDS = [f"state-{s[0]}" for s in _FOLDERED_STATES]


@pytest.mark.parametrize(("state", "fixture", "list_id", "elements", "measured", "outcome"),
                         _FOLDERED_STATES, ids=_FOLDERED_IDS)
def test_the_foldered_probe_reads_the_selected_library_back_before_a_rendered_state(
    state: int, fixture: str, list_id: str, elements: list[dict[str, Any]], measured: str,
    outcome: str,
) -> None:
    rows, sent = _run_rendered(_FOLDERED_PROBE, _foldered_libs(), state, list_id, elements)

    assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    assert "BaseTemplate=101" in rows[fixture]["evidence"]
    assert rows["library.large-list.control-ui-foldered-page-identity"]["outcome"] == "MATCHES"
    assert rows[measured]["outcome"] == outcome, rows[measured]
    assert rows[measured]["state"] == "settled"
    assert not _voided(rows)
    _no_query_or_write(sent)


@pytest.mark.parametrize(("state", "fixture", "list_id", "elements", "measured"),
                         [s[:5] for s in _FOLDERED_STATES], ids=_FOLDERED_IDS)
def test_the_foldered_probe_voids_a_rendered_state_on_a_generic_list_of_the_selected_name(
    state: int, fixture: str, list_id: str, elements: list[dict[str, Any]], measured: str,
) -> None:
    """Only the library the state selects is swapped, and only its rows are voided."""
    libraries = _foldered_libs(big=100) if state == 2 else _foldered_libs(small=100)
    rows, sent = _run_rendered(_FOLDERED_PROBE, libraries, state, list_id, elements)

    _assert_generic_list_voids(rows, fixture, _catalog_dependents(_FOLDERED_PROBE, fixture))
    assert rows[measured]["state"] == "void", rows[measured]
    assert [row_id for row_id, row in rows.items() if row["state"] == "settled"] == [fixture]
    _no_query_or_write(sent)
