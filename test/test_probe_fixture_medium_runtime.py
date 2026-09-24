"""Execute the large-list builders and the document-library probes of #559 against a mock.

Each probe reused a container found by title and recorded it 'ALREADY
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
    const newList = (title, template, contentTypes = false) => {
      const n = nextList;
      nextList += 1;
      const list = { Id: `0000000${n}-aaaa-bbbb-cccc-00000000000${n}`, Title: title,
        BaseTemplate: template, ContentTypesEnabled: contentTypes, root: `/sites/test/L${n}`,
        fields: new Map(), items: [], nextItem: 1 };
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
      const list = newList(title, shape.template, shape.contentTypes === true);
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
        const list = newList(sent.Title, sent.BaseTemplate, sent.ContentTypesEnabled === true);
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
        // A file lands in a library's root folder as an item named by FileLeafRef.
        const file = /^\\/Files\\/add\\(url='([^']+)'/.exec(rest);
        const library = [...lists.values()]
          .find((held) => held.root === folder && held.BaseTemplate === 101);
        if (file && method === 'POST' && library) {
          const held = library.items.find((item) => item.FileLeafRef === file[1]);
          if (!held) {
            library.items.push({ Id: library.nextItem, FileLeafRef: file[1], Title: null });
            library.nextItem += 1;
          }
          return jsonResponse(200, { Name: file[1], ServerRelativeUrl: `${folder}/${file[1]}` });
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
        const whole = { Id: list.Id, Title: list.Title, BaseTemplate: list.BaseTemplate,
          ContentTypesEnabled: list.ContentTypesEnabled, ItemCount: list.items.length,
          ListItemEntityTypeFullName: 'SP.Data.LibItem' };
        // A $select is served only the properties it names, as a live read is.
        const select = /\\$select=([^&]+)/.exec(rest);
        if (!select) return jsonResponse(200, whole);
        return jsonResponse(200, Object.fromEntries(select[1].split(',')
          .filter((name) => name in whole).map((name) => [name, whole[name]])));
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
      if (rest.startsWith('/items(')) return refusal(404, `unmocked ${path}`);
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


@pytest.mark.parametrize("output_type", [2, "Number"])
def test_fixture_voids_its_rows_on_a_calculated_column_of_another_output_type(
    output_type: object,
) -> None:
    """Only the Learn-documented 9 is Number; an unobserved string form fails closed."""
    calc = {"TypeAsString": "Calculated", "OutputType": output_type}
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


# --------------------------------------------------------------------------
# The document-library probes: each library fixture, reused and created.
# --------------------------------------------------------------------------
_LIST_FIXTURE = "field.default-formula.fixture-list-created"
#: Each probe's library by title.
_LIBRARIES = {
    "default-formula-readback-probe.js": "dbmlsp Probe Readback Library",
    "file-operations-probe.js": "dbmlsp Probe FileOps",
    "folder-probe.js": "dbmlsp Probe Folder",
    "folder-shape-probe.js": "dbmlsp Probe Shape Library",
    "folder-under-schema-probe.js": "dbmlsp Probe Folder Schema",
    "library-builtin-view-probe.js": "dbmlsp Probe Builtin View",
    "library-column-interactions-probe.js": "dbmlsp Probe LibColInteractions",
    "library-columns-probe.js": "dbmlsp Probe LibCols",
    "library-content-type-probe.js": "dbmlsp Probe ContentType",
    "library-field-probe.js": "dbmlsp Probe LibField",
    "library-form-probe.js": "dbmlsp Probe LibForm",
    "library-formula-probe.js": "dbmlsp Probe LibFormula",
    "library-grouping-probe.js": "dbmlsp Probe LibGroup",
    "library-guards-probe.js": "dbmlsp Probe Guards Library",
    "library-header-token-probe.js": "dbmlsp Probe Header Tokens",
    "library-index-probe.js": "dbmlsp Probe LibIndex",
    "library-index-threshold-probe.js": "dbmlsp Probe LibIdxThreshold",
    "library-lookup-write-probe.js": "dbmlsp Probe LibWrite Lib",
    "library-nesting-probe.js": "dbmlsp Probe LibNest",
    "library-query-probe.js": "dbmlsp Probe LibQuery",
    "library-view-interaction-probe.js": "dbmlsp Probe LibViewInt",
    "library-view-search-probe.js": "dbmlsp Probe LibViewSearch",
    "view-scope-revert-probe.js": "dbmlsp Probe Scope Library",
}
#: The two probes that also build a generic list as a comparison container.
_GENERIC_LISTS = {
    "default-formula-readback-probe.js": "dbmlsp Probe Readback List",
    "library-guards-probe.js": "dbmlsp Probe Guards List",
}
#: The probes that create their library with content types off and declare it.
_CONTENT_TYPES_OFF = [
    "folder-under-schema-probe.js", "library-builtin-view-probe.js",
    "library-header-token-probe.js",
]


def _voided_by(rows: dict[str, dict[str, str]], fixture: str) -> set[str]:
    return {row_id for row_id in _void_ids(rows)
            if f"the fixture {fixture} did not hold" in rows[row_id]["evidence"]}


def _assert_stopped_at(
    rows: dict[str, dict[str, str]], sent: list[dict[str, str]],
    probe: str, title: str, named: str,
) -> None:
    assert rows[_DOC_LIB]["outcome"] == "FAIL", rows[_DOC_LIB]
    assert named in rows[_DOC_LIB]["evidence"], rows[_DOC_LIB]
    dependents = _catalogued_dependents(probe, _DOC_LIB)
    assert _voided_by(rows, _DOC_LIB) == dependents
    # The list half of a two-fixture probe runs first here, and voids only its own rows.
    others = _void_ids(rows) - dependents
    assert all(row_id.startswith("field.default-formula.") for row_id in others), others
    assert not others or probe in _GENERIC_LISTS, others
    assert not _writes_to(sent, title)


@pytest.mark.parametrize(("probe", "title"), list(_LIBRARIES.items()), ids=list(_LIBRARIES))
def test_a_generic_list_under_a_probe_library_name_voids_its_rows(probe: str, title: str) -> None:
    rows, sent = _run_probe(_MOCK, _generic(title), probe)

    _assert_stopped_at(rows, sent, probe, title, "BaseTemplate differs: read 100, declared 101")


@pytest.mark.parametrize(
    ("probe", "title"), list(_GENERIC_LISTS.items()), ids=list(_GENERIC_LISTS))
def test_a_library_under_a_probe_list_name_voids_the_list_rows(probe: str, title: str) -> None:
    rows, sent = _run_probe(_MOCK, {"existing": {title: {"template": 101}}}, probe)

    assert rows[_LIST_FIXTURE]["outcome"] == "FAIL", rows[_LIST_FIXTURE]
    assert "BaseTemplate differs: read 101, declared 100" in rows[_LIST_FIXTURE]["evidence"]
    assert _voided_by(rows, _LIST_FIXTURE) == _catalogued_dependents(probe, _LIST_FIXTURE)
    assert not _writes_to(sent, title, uploads=False)


@pytest.mark.parametrize("probe", _CONTENT_TYPES_OFF)
def test_a_library_with_content_types_on_voids_the_rows_that_rest_on_them_off(probe: str) -> None:
    title = _LIBRARIES[probe]
    config = {"existing": {title: {"template": 101, "contentTypes": True}}}
    rows, sent = _run_probe(_MOCK, config, probe)

    _assert_stopped_at(rows, sent, probe, title,
                       "ContentTypesEnabled differs: read true, declared false")


@pytest.mark.parametrize("probe", _CONTENT_TYPES_OFF)
def test_a_content_types_off_library_is_created_and_read_back_with_them_off(probe: str) -> None:
    rows, sent = _run_probe(_MOCK, {}, probe)

    [create] = [r for r in sent if r["path"] == "web/lists" and _LIBRARIES[probe] in r["body"]]
    assert '"ContentTypesEnabled":false' in create["body"]
    assert "ContentTypesEnabled=false" in rows[_DOC_LIB]["evidence"], rows[_DOC_LIB]


@pytest.mark.parametrize("probe", list(_LIBRARIES))
@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_a_probe_library_that_holds_establishes(probe: str, reused: bool) -> None:
    existing = {_LIBRARIES[probe]: {"template": 101}}
    if probe in _GENERIC_LISTS:
        existing[_GENERIC_LISTS[probe]] = {"template": 100}
    rows, _ = _run_probe(_MOCK, {"existing": existing} if reused else {}, probe)

    assert rows[_DOC_LIB]["outcome"] == "PASS", rows[_DOC_LIB]
    assert "BaseTemplate=101" in rows[_DOC_LIB]["evidence"]
    assert not _voided_by(rows, _DOC_LIB)
    if probe in _GENERIC_LISTS:
        assert rows[_LIST_FIXTURE]["outcome"] == "PASS", rows[_LIST_FIXTURE]
        assert not _voided_by(rows, _LIST_FIXTURE)


# --------------------------------------------------------------------------
# library-formula's lookup target, and library-index-threshold's two columns.
# --------------------------------------------------------------------------
_FORMULA = "library-formula-probe.js"
_FORMULA_TARGET = "dbmlsp Probe LibFormula Target"
_TARGET_ROW = "library.formula.fixture-target-list-created"
#: A lookup column's create, as its SchemaXml reads inside the JSON body.
_LOOKUP_CREATE = 'Type=\\"Lookup\\"'


def test_formula_voids_the_lookup_leg_on_a_target_that_is_not_a_generic_list() -> None:
    rows, sent = _run_probe(_MOCK, {"existing": {_FORMULA_TARGET: {"template": 101}}}, _FORMULA)

    assert rows[_TARGET_ROW]["outcome"] == "FAIL", rows[_TARGET_ROW]
    assert "BaseTemplate differs: read 101, declared 100" in rows[_TARGET_ROW]["evidence"]
    assert _voided_by(rows, _TARGET_ROW) == _catalogued_dependents(_FORMULA, _TARGET_ROW)
    assert not _writes_to(sent, _FORMULA_TARGET, uploads=False)
    # The library does not rest on the target, so it still builds, and no lookup points there.
    assert rows[_DOC_LIB]["outcome"] == "PASS", rows[_DOC_LIB]
    assert not [r for r in sent if _LOOKUP_CREATE in r["body"]]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_formula_establishes_a_target_that_is_a_generic_list(reused: bool) -> None:
    config = {"existing": {_FORMULA_TARGET: {"template": 100}}} if reused else {}
    rows, sent = _run_probe(_MOCK, config, _FORMULA)

    assert rows[_TARGET_ROW]["outcome"] == "PASS", rows[_TARGET_ROW]
    assert "BaseTemplate=100" in rows[_TARGET_ROW]["evidence"]
    assert not _voided_by(rows, _TARGET_ROW)
    assert [r for r in sent if _LOOKUP_CREATE in r["body"]]


_THRESHOLD = "library-index-threshold-probe.js"
_THRESHOLD_LIB = "dbmlsp Probe LibIdxThreshold"
_THRESHOLD_COLUMNS = "library.index.fixture-probe-columns-created"


@pytest.mark.parametrize(
    ("column", "wrong"),
    [("TidxUnindexedText", "Note"), ("TidxUnindexedPerson", "Text")],
    ids=["text", "person"],
)
def test_threshold_voids_its_rows_on_a_probe_column_of_another_type(
    column: str, wrong: str,
) -> None:
    config = {"existing": {_THRESHOLD_LIB: {
        "template": 101, "fields": {column: {"TypeAsString": wrong}}}}}
    rows, sent = _run_probe(_MOCK, config, _THRESHOLD, _BUILD_GATES)

    assert rows[_DOC_LIB]["outcome"] == "PASS", rows[_DOC_LIB]
    assert rows[_THRESHOLD_COLUMNS]["outcome"] == "FAIL", rows[_THRESHOLD_COLUMNS]
    assert f"{column}.TypeAsString differs" in rows[_THRESHOLD_COLUMNS]["evidence"]
    assert _void_ids(rows) == _catalogued_dependents(_THRESHOLD, _THRESHOLD_COLUMNS)
    assert not [r for r in sent if "/Files/add" in r["path"] or r["verb"] == "MERGE"]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_threshold_establishes_probe_columns_of_the_declared_types(reused: bool) -> None:
    fields = {"TidxUnindexedText": {"TypeAsString": "Text"},
              "TidxUnindexedPerson": {"TypeAsString": "User"}}
    config = {"existing": {_THRESHOLD_LIB: {"template": 101, "fields": fields}}}
    rows, _ = _run_probe(_MOCK, config if reused else {}, _THRESHOLD)

    assert rows[_THRESHOLD_COLUMNS]["outcome"] == "PASS", rows[_THRESHOLD_COLUMNS]
    assert 'TidxUnindexedPerson.TypeAsString="User"' in rows[_THRESHOLD_COLUMNS]["evidence"]
    assert not _voided_by(rows, _THRESHOLD_COLUMNS)
