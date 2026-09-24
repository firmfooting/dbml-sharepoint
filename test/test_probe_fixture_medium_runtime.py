"""Execute the three large-list builder probes of #559 against a mock SharePoint.

Each builder reused a container found by title and recorded it 'ALREADY
PRESENT', or took a PASS from the create's status, without reading anything
back. Each now reads its containers back on create and on reuse, so a list of
the wrong kind voids exactly the rows the catalogue says rest on it and is
never written to.
"""

import textwrap
from typing import Any

import pytest
from _node import NODE
from test_probe_fixture_runtime import _catalogued_dependents, _run_probe, _void_ids

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

#: Lists and libraries with their fields, items and folders. A field is built
#: from its schema XML and served whole; a MERGE naming a property SP.Field
#: lacks is refused, and a field or folder absent by name is refused.
_MOCK = textwrap.dedent("""
    const CONFIG = __CONFIG__;
    const lists = new Map();
    const folders = new Set();
    let nextList = 1;
    const parse = (raw) => { try { return JSON.parse(raw); } catch { return null; } };
    const refusal = (status, value) =>
      jsonResponse(status, { 'odata.error': { message: { value } } });
    const FIELD_PROPS = new Set(['Description', 'Indexed', 'Title', 'Required']);
    const newList = (title, template) => {
      const n = nextList;
      nextList += 1;
      const list = { Id: `0000000${n}-aaaa-bbbb-cccc-00000000000${n}`, Title: title,
        BaseTemplate: template, root: `/sites/test/L${n}`, fields: new Map(), items: [],
        nextItem: 1 };
      folders.add(list.root);
      lists.set(title, list);
      return list;
    };
    const attr = (xml, name) => {
      const found = new RegExp(`${name}="([^"]*)"`).exec(xml);
      return found ? found[1] : null;
    };
    const fieldFrom = (xml) => {
      const type = attr(xml, 'Type');
      const list = attr(xml, 'List');
      return { InternalName: attr(xml, 'Name'), TypeAsString: type, Indexed: false,
        Description: '',
        // Served braced while a list Id is served bare, so the comparison must normalise.
        LookupList: type === 'Lookup' && list ? `{${list.replace(/[{}]/g, '')}}` : '',
        OutputType: type === 'Calculated' ? { Number: 9, Text: 2 }[attr(xml, 'ResultType')] : 0 };
    };
    for (const [title, shape] of Object.entries(CONFIG.existing || {})) {
      const list = newList(title, shape.template);
      for (const [name, props] of Object.entries(shape.fields || {})) {
        const other = props.LookupList === 'OTHER'
          ? `{${newList(`other ${name}`, 100).Id}}` : props.LookupList;
        list.fields.set(name, { InternalName: name, Indexed: false, Description: '',
          ...props, LookupList: other });
      }
    }
    const LIST = /^web\\/lists\\/getbytitle\\('([^']+)'\\)(.*)$/;
    const FOLDER = /^web\\/GetFolderByServerRelativeUrl\\('([^']+)'\\)(.*)$/;
    const FIELD = /^\\/fields\\/getbyinternalnameortitle\\('([^']+)'\\)/;

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const verb = (opts.headers || {})['X-HTTP-Method'] || method;
      const raw = opts.body === undefined ? '' : String(opts.body);
      const sent = parse(raw) || {};
      const path = decodeURIComponent(u.split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });

      if (path.startsWith('contextinfo')) return digestResponse();
      if (path.startsWith('web/RegionalSettings/TimeZone')) {
        return jsonResponse(200, { Description: '(UTC) Coordinated Universal Time',
          Information: { Bias: 0, StandardBias: 0, DaylightBias: 0 } });
      }
      if (path === 'web/lists' && method === 'POST') {
        const list = newList(sent.Title, sent.BaseTemplate);
        return jsonResponse(201, { Id: list.Id, Title: list.Title });
      }
      const inFolder = FOLDER.exec(path);
      if (inFolder) {
        const [, folder, rest] = inFolder;
        const sub = /^\\/folders\\/add\\(url='([^']+)'\\)/.exec(rest);
        if (sub && method === 'POST') {
          folders.add(`${folder}/${sub[1]}`);
          return jsonResponse(200, { Name: sub[1], ServerRelativeUrl: `${folder}/${sub[1]}` });
        }
        if (method !== 'GET') return refusal(404, `unmocked ${path}`);
        if (!folders.has(folder)) return refusal(404, 'File Not Found.');
        return jsonResponse(200, { Exists: true, ServerRelativeUrl: folder, ItemCount: 0 });
      }
      if (path.startsWith('web/GetFileByServerRelativeUrl')) {
        return refusal(404, 'File Not Found.');
      }
      const inList = LIST.exec(path);
      if (!inList) return refusal(404, `unmocked ${path}`);
      const list = lists.get(inList[1]);
      if (!list) return refusal(404, 'List does not exist.');
      const rest = inList[2];
      if (rest === '' || rest.startsWith('?')) {
        return jsonResponse(200, { Id: list.Id, Title: list.Title,
          BaseTemplate: list.BaseTemplate, ItemCount: list.items.length,
          ListItemEntityTypeFullName: 'SP.Data.LibItem' });
      }
      if (rest.startsWith('/RootFolder')) {
        return jsonResponse(200, { ServerRelativeUrl: list.root });
      }
      if (rest === '/fields/createfieldasxml') {
        const field = fieldFrom(sent.parameters.SchemaXml);
        list.fields.set(field.InternalName, field);
        return jsonResponse(201, { InternalName: field.InternalName });
      }
      const named = FIELD.exec(rest);
      if (named) {
        const held = list.fields.get(named[1]);
        if (!held) return refusal(400, `Column '${named[1]}' does not exist.`);
        if (verb !== 'MERGE') return jsonResponse(200, held);
        const { __metadata, ...props } = sent;
        const unknown = Object.keys(props).find((k) => !FIELD_PROPS.has(k));
        if (unknown) return refusal(400, `The property '${unknown}' does not exist.`);
        Object.assign(held, props);
        return jsonResponse(204, {});
      }
      if (rest.startsWith('/items') && method === 'POST') {
        const item = { Id: list.nextItem, Title: sent.Title };
        list.nextItem += 1;
        list.items.push(item);
        return jsonResponse(201, item);
      }
      if (rest.startsWith('/items')) {
        const rows = [...list.items].sort((a, b) => b.Id - a.Id);
        return jsonResponse(200, { value: rows });
      }
      return refusal(404, `unmocked ${path}`);
    };
""")

_GATES = ("CONFIRMED", "ALLOW_WRITES")
#: The upload gate is opened in every run that must stop, so "sent no write" covers files too.
_BUILD_GATES = (*_GATES, "BUILD_FIXTURE")

_DOC_LIB = "library.doc-lib.fixture-library-created"
_FIXTURE = "library-large-list-fixture-probe.js"
_FIXTURE_LIB = "dbmlsp Probe LargeLib"
_FIXTURE_TGT = "dbmlsp Probe LargeLib Target"
_TARGET = "library.large-list.fixture-target-list-seeded"
_COLUMNS = "library.large-list.fixture-columns-created"
_FOLDERED = "library-large-list-foldered-fixture-probe.js"
_FOLDERED_LIB = "dbmlsp Probe Foldered"
_MULTILEVEL_LIB = "dbmlsp Probe MultiLevel"
_MULTILEVEL = "library.large-list.fixture-multilevel-library-created"
_PREINDEX = "library-large-list-preindex-fixture-probe.js"
_PREINDEX_LIB = "dbmlsp Probe PreIndex"


def _writes_to(
    sent: list[dict[str, str]], title: str, uploads: bool = True,
) -> list[dict[str, str]]:
    """Writes addressed to the list titled `title`, and with `uploads` every file or folder add."""
    prefix = f"web/lists/getbytitle('{title}')"
    return [r for r in sent if r["verb"] != "GET" and (
        r["path"].startswith(prefix)
        or (uploads and ("/Files/add" in r["path"] or "folders/add" in r["path"].lower())))]


def _generic(title: str) -> dict[str, Any]:
    return {"existing": {title: {"template": 100}}}


# --------------------------------------------------------------------------
# A generic list reused under a library's name, one case per library fixture.
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("probe", "title", "fixture"),
    [
        (_FIXTURE, _FIXTURE_LIB, _DOC_LIB),
        (_FOLDERED, _FOLDERED_LIB, _DOC_LIB),
        (_FOLDERED, _MULTILEVEL_LIB, _MULTILEVEL),
        (_PREINDEX, _PREINDEX_LIB, _DOC_LIB),
    ],
    ids=["fixture", "foldered-large", "foldered-small", "preindex"],
)
def test_a_generic_list_under_the_library_name_voids_its_rows(
    probe: str, title: str, fixture: str,
) -> None:
    # The foldered probe goes on to build its other library, and this mock serves no upload.
    rows, sent = _run_probe(
        _MOCK, _generic(title), probe, _GATES if probe == _FOLDERED else _BUILD_GATES)

    assert rows[fixture]["outcome"] == "FAIL", rows[fixture]
    assert "BaseTemplate differs: read 100, declared 101" in rows[fixture]["evidence"]
    voided = _void_ids(rows)
    assert voided == _catalogued_dependents(probe, fixture)
    assert all(fixture in rows[row_id]["evidence"] for row_id in voided)
    # Either foldered library stopping leaves the other building, so only its own path is checked.
    assert not _writes_to(sent, title, uploads=probe != _FOLDERED)


def test_foldered_builds_the_large_library_when_the_small_one_did_not_hold() -> None:
    """The two libraries answer different halves of the pairing, so one failing leaves the other."""
    rows, _ = _run_probe(_MOCK, _generic(_MULTILEVEL_LIB), _FOLDERED)

    assert rows[_DOC_LIB]["outcome"] == "PASS", rows[_DOC_LIB]
    assert rows["library.large-list.fixture-foldered-columns-created"]["outcome"] == "PASS"


# --------------------------------------------------------------------------
# The large-library fixture's two further fixtures: the target and the columns.
# --------------------------------------------------------------------------
def test_fixture_voids_its_rows_on_a_target_that_is_not_a_generic_list() -> None:
    config = {"existing": {_FIXTURE_TGT: {"template": 101}}}
    rows, sent = _run_probe(_MOCK, config, _FIXTURE, _BUILD_GATES)

    assert rows[_DOC_LIB]["outcome"] == "PASS", rows[_DOC_LIB]
    assert rows[_TARGET]["outcome"] == "FAIL", rows[_TARGET]
    assert "BaseTemplate differs: read 101, declared 100" in rows[_TARGET]["evidence"]
    assert _void_ids(rows) == _catalogued_dependents(_FIXTURE, _TARGET)
    assert not _writes_to(sent, _FIXTURE_TGT)
    assert not [r for r in _writes_to(sent, _FIXTURE_LIB) if "createfieldasxml" in r["path"]]


def test_fixture_voids_its_rows_on_a_lookup_bound_to_another_list() -> None:
    lookup = {"TypeAsString": "Lookup", "LookupList": "OTHER"}
    config = {"existing": {_FIXTURE_LIB: {"template": 101, "fields": {"LVLookup": lookup}}}}
    rows, sent = _run_probe(_MOCK, config, _FIXTURE, _BUILD_GATES)

    assert rows[_TARGET]["outcome"] == "PASS", rows[_TARGET]
    assert rows[_COLUMNS]["outcome"] == "FAIL", rows[_COLUMNS]
    assert "LVLookup.LookupList differs" in rows[_COLUMNS]["evidence"]
    assert _void_ids(rows) == _catalogued_dependents(_FIXTURE, _COLUMNS)
    assert not [r for r in sent if "/Files/add" in r["path"] or r["verb"] == "MERGE"]


def test_fixture_voids_its_rows_on_a_calculated_column_of_another_output_type() -> None:
    calc = {"TypeAsString": "Calculated", "OutputType": 2}
    config = {"existing": {_FIXTURE_LIB: {"template": 101, "fields": {"LVCalc": calc}}}}
    rows, _ = _run_probe(_MOCK, config, _FIXTURE, _BUILD_GATES)

    assert rows[_COLUMNS]["outcome"] == "FAIL", rows[_COLUMNS]
    assert "LVCalc.OutputType differs" in rows[_COLUMNS]["evidence"]
    assert _void_ids(rows) == _catalogued_dependents(_FIXTURE, _COLUMNS)


# --------------------------------------------------------------------------
# Healthy controls: created fresh, and reused as the right kind of list.
# --------------------------------------------------------------------------
_HEALTHY = {
    _FIXTURE: ([_DOC_LIB, _TARGET, _COLUMNS],
               {_FIXTURE_LIB: {"template": 101}, _FIXTURE_TGT: {"template": 100}}),
    _FOLDERED: ([_DOC_LIB, _MULTILEVEL],
                {_FOLDERED_LIB: {"template": 101}, _MULTILEVEL_LIB: {"template": 101}}),
    _PREINDEX: ([_DOC_LIB], {_PREINDEX_LIB: {"template": 101}}),
}


@pytest.mark.parametrize("probe", list(_HEALTHY))
@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_a_builder_establishes_the_containers_it_reads_back(probe: str, reused: bool) -> None:
    fixtures, existing = _HEALTHY[probe]
    rows, _ = _run_probe(_MOCK, {"existing": existing} if reused else {}, probe)

    for fixture in fixtures:
        assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    assert "BaseTemplate=101" in rows[_DOC_LIB]["evidence"]
    assert not _void_ids(rows)
