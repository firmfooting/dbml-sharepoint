"""Execute the large-list builders, the document-library and the generic-list probes of #559.

Each probe reused a container found by title and recorded it 'ALREADY
PRESENT', or took a PASS from the create's status, without reading anything
back. Each now reads its containers back on create and on reuse, so a list of
the wrong kind voids exactly the rows the catalogue says rest on it and is
never written to.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL
from test_probe_fixture_runtime import _catalogued_dependents, _run_probe, _void_ids
from test_probe_library_identity_runtime import _SITE_MOCK
from test_probe_library_identity_runtime import _run as _run_on_site
from test_probe_runtime import (
    _CALC_CHOICE_HARNESS,
    _CALC_CHOICE_HEALTHY,
    _CROSS_WEB_HARNESS,
    _CROSS_WEB_HEALTHY,
    _TRANSITION_HARNESS,
    _TRANSITION_HEALTHY,
    _fixture_probe_js,
    _fixture_rows,
)
from test_probe_runtime import _HARNESS as _THRESHOLD_INDEX_HARNESS
from test_probe_runtime import _HEALTHY as _THRESHOLD_INDEX_HEALTHY

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
      // Failure modes a live read can produce: a payload missing Id, and a RootFolder read refused.
      list.omitId = shape.omitId === true;
      list.rootFolderStatus = shape.rootFolderStatus || null;
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
        if (list.omitId) delete whole.Id;
        // A $select is served only the properties it names, as a live read is.
        const select = /\\$select=([^&]+)/.exec(rest);
        if (!select) return jsonResponse(200, whole);
        return jsonResponse(200, Object.fromEntries(select[1].split(',')
          .filter((name) => name in whole).map((name) => [name, whole[name]])));
      }
      if (rest.startsWith('/RootFolder')) {
        if (list.rootFolderStatus) return refusal(list.rootFolderStatus, 'Throttled.');
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


def test_formula_voids_the_lookup_leg_on_a_target_read_that_serves_no_id() -> None:
    """A target read without Id set targetListId to undefined and built a lookup on it."""
    config = {"existing": {_FORMULA_TARGET: {"template": 100, "omitId": True}}}
    rows, sent = _run_probe(_MOCK, config, _FORMULA)

    assert rows[_TARGET_ROW]["outcome"] == "FAIL", rows[_TARGET_ROW]
    assert "Id" in rows[_TARGET_ROW]["evidence"]
    assert _voided_by(rows, _TARGET_ROW) == _catalogued_dependents(_FORMULA, _TARGET_ROW)
    assert not [r for r in sent if _LOOKUP_CREATE in r["body"]]


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


def test_threshold_keeps_settled_fixtures_when_the_root_folder_read_fails() -> None:
    """A RootFolder failure after both fixtures passed was reported as the library failing."""
    fields = {"TidxUnindexedText": {"TypeAsString": "Text"},
              "TidxUnindexedPerson": {"TypeAsString": "User"}}
    config = {"existing": {_THRESHOLD_LIB: {
        "template": 101, "fields": fields, "rootFolderStatus": 503}}}
    rows, sent = _run_probe(_MOCK, config, _THRESHOLD)

    assert rows[_DOC_LIB]["outcome"] == "PASS", rows[_DOC_LIB]
    assert rows[_THRESHOLD_COLUMNS]["outcome"] == "PASS", rows[_THRESHOLD_COLUMNS]
    assert rows["library.index.fixture-file-count"]["outcome"] == "ABORTED"
    assert "RootFolder" in rows["library.index.fixture-file-count"]["evidence"]
    assert not [r for r in sent if "/Files/add" in r["path"]]


# --------------------------------------------------------------------------
# The generic-list probes (#559 part C).
# --------------------------------------------------------------------------
#: Generic lists with their fields and items. A field is served with the
#: properties SP.Field carries, projected by $select; an item POST naming a
#: column the list lacks is refused, and so is a MERGE naming a property the
#: entity lacks. A [today] default fills a REST create only when `fillToday`
#: says so, since that is the question today-source asks.
_LIST_MOCK = textwrap.dedent(r"""
    const CONFIG = __CONFIG__;
    globalThis._spPageContextInfo = window._spPageContextInfo;
    const lists = new Map();
    let nextList = 1;
    const respond = (status, payload, verbose = false) => {
      const body = verbose ? { d: payload } : payload;
      return { ok: status >= 200 && status < 300, status,
        headers: { get: () => 'Thu, 24 Sep 2026 09:00:00 GMT' },
        json: async () => body, text: async () => JSON.stringify(body) };
    };
    const refusal = (status, value) => respond(status, { 'odata.error': { message: { value } } });
    const KINDS = { 2: 'Text', 3: 'Note', 4: 'DateTime', 6: 'Choice', 7: 'Lookup', 8: 'Boolean',
      9: 'Number', 20: 'User' };
    const FIELD_PROPS = new Set(['Title', 'Description', 'Required', 'Hidden', 'Indexed',
      'EnforceUniqueValues', 'ValidationFormula', 'ValidationMessage', 'Sealed', 'DefaultValue',
      'DefaultFormula', 'ClientValidationFormula', 'DisplayFormat', 'Choices', 'FillInChoice']);
    const LIST_PROPS = new Set(['Title', 'Description', 'ValidationFormula', 'ValidationMessage']);
    const newField = (name, props) => ({ InternalName: name, Title: name, TypeAsString: 'Text',
      Required: false, Hidden: false, FromBaseType: false, Sealed: false, ReadOnlyField: false,
      CanBeDeleted: true, Indexed: false, EnforceUniqueValues: false, DefaultValue: null,
      DefaultFormula: null, ValidationFormula: null, Description: '', ...props });
    const newList = (title, template, description) => {
      const n = nextList;
      nextList += 1;
      const list = { Id: `0000000${n}-aaaa-bbbb-cccc-00000000000${n}`, Title: title,
        BaseTemplate: template, Description: description || '', ValidationFormula: '',
        fields: new Map([['Title', newField('Title', { FromBaseType: true })]]),
        items: [], nextItem: 1 };
      lists.set(title, list);
      return list;
    };
    for (const [title, shape] of Object.entries(CONFIG.existing || {})) {
      const list = newList(title, shape.template, shape.description);
      // A read that serves no Id, which a failure case sets.
      list.omitId = shape.omitId === true;
      for (const [name, props] of Object.entries(shape.fields || {})) {
        list.fields.set(name, newField(name, props));
      }
    }
    const project = (whole, rest) => {
      const select = /[?&]\$select=([^&]+)/.exec(rest);
      if (!select) return whole;
      return Object.fromEntries(select[1].split(',').filter((name) => name in whole)
        .map((name) => [name, whole[name]]));
    };
    const plain = (sent) => Object.fromEntries(Object.entries(sent)
      .filter(([key]) => key !== '__metadata'));
    const attr = (xml, name) => {
      const found = new RegExp(` ${name}="([^"]*)"`).exec(xml);
      return found ? found[1] : null;
    };
    const LIST = /^web\/lists\/getbytitle\('((?:[^']|'')+)'\)(.*)$/;
    const FIELD = /^\/fields\/getbyinternalnameortitle\('([^']+)'\)(.*)$/;
    const ITEM = /^\/items\((\d+)\)(.*)$/;

    globalThis.fetch = async (url, opts = {}) => {
      const headers = opts.headers || {};
      const method = opts.method || 'GET';
      const verb = headers['X-HTTP-Method'] || method;
      const verbose = String(headers.Accept || headers.accept || '').includes('verbose');
      const raw = opts.body === undefined ? '' : String(opts.body);
      let sent = {};
      try { sent = raw ? JSON.parse(raw) : {}; } catch { sent = {}; }
      const path = decodeURIComponent(String(url).split('/_api/')[1] || '');
      SENT.push({ verb, path, body: raw });

      if (path.startsWith('contextinfo')) {
        return respond(200, { d: { GetContextWebInformation: { FormDigestValue: 'digest' } } });
      }
      if (/regionalsettings\/timezone/i.test(path)) {
        return respond(200, { Description: '(UTC) Coordinated Universal Time',
          Information: { Bias: 0, StandardBias: 0, DaylightBias: 0 } });
      }
      if (path.startsWith('SP.UserProfiles.PeopleManager/GetMyProperties')) {
        return respond(200, { UserProfileProperties: [] });
      }
      if (path === 'web/lists' && method === 'POST') {
        const made = newList(sent.Title, sent.BaseTemplate, sent.Description);
        return respond(201, { Id: made.Id, Title: made.Title }, verbose);
      }
      const named = LIST.exec(path);
      if (!named) return refusal(404, `unmocked ${path}`);
      const list = lists.get(named[1].replace(/''/g, "'"));
      if (!list) return refusal(404, 'List does not exist.');
      const rest = named[2];
      if (rest === '' || rest.startsWith('?')) {
        if (verb === 'MERGE') {
          const props = plain(sent);
          const unknown = Object.keys(props).find((key) => !LIST_PROPS.has(key));
          if (unknown) return refusal(400, `The property '${unknown}' does not exist.`);
          Object.assign(list, props);
          return respond(204, {});
        }
        const { fields, items, nextItem, omitId, ...whole } = list;
        if (omitId) delete whole.Id;
        return respond(200, project({ ...whole, ItemCount: items.length,
          ListItemEntityTypeFullName: 'SP.Data.ProbeListItem' }, rest), verbose);
      }
      if (rest === '/recycle' && method === 'POST') {
        lists.delete(list.Title);
        return respond(200, {});
      }
      if (rest === '/fields' && method === 'POST') {
        const { FieldTypeKind, ...props } = plain(sent);
        if (list.fields.has(props.Title)) return refusal(400, 'A duplicate field name was found.');
        list.fields.set(props.Title, newField(props.Title, { ...props,
          TypeAsString: KINDS[FieldTypeKind] }));
        return respond(201, { InternalName: props.Title }, verbose);
      }
      if (rest === '/fields/createfieldasxml' && method === 'POST') {
        const xml = String((sent.parameters || {}).SchemaXml || '');
        const name = attr(xml, 'Name');
        if (list.fields.has(name)) return refusal(400, 'A duplicate field name was found.');
        const type = attr(xml, 'Type');
        const format = attr(xml, 'Format');
        list.fields.set(name, newField(name, { TypeAsString: type,
          ...(type === 'DateTime' ? { DisplayFormat: format === 'DateOnly' ? 0 : 1 } : {}),
          ...(type === 'Lookup' ? { LookupList: attr(xml, 'List') } : {}) }));
        return respond(201, { InternalName: name }, verbose);
      }
      if (rest.startsWith('/fields?') || rest === '/fields') {
        return respond(200, { value: [...list.fields.values()].map((f) => project(f, rest)) });
      }
      const field = FIELD.exec(rest);
      if (field) {
        const held = list.fields.get(field[1]);
        if (!held) return refusal(400, `Column '${field[1]}' does not exist.`);
        if (verb === 'MERGE') {
          const props = plain(sent);
          const unknown = Object.keys(props).find((key) => !FIELD_PROPS.has(key));
          if (unknown) return refusal(400, `The property '${unknown}' does not exist.`);
          Object.assign(held, props);
          return respond(204, {});
        }
        if (verb === 'DELETE') {
          list.fields.delete(field[1]);
          return respond(200, {});
        }
        return respond(200, project(held, field[2]), verbose);
      }
      if (rest === '/items' && method === 'POST') {
        if (CONFIG.refuseItems) return refusal(400, 'List data validation failed.');
        const props = plain(sent);
        const unknown = Object.keys(props).find((key) => !list.fields.has(key)
          && !(key.endsWith('Id') && list.fields.has(key.slice(0, -2))));
        if (unknown) {
          return refusal(400, `The property '${unknown}' does not exist on the item type.`);
        }
        const item = { Id: list.nextItem, ...props };
        list.nextItem += 1;
        for (const held of list.fields.values()) {
          if (held.InternalName === 'Title' || item[held.InternalName] !== undefined) continue;
          const today = CONFIG.fillToday && held.DefaultValue === '[today]';
          item[held.InternalName] = today ? '2026-09-24T00:00:00Z' : null;
        }
        list.items.push(item);
        return respond(201, item, verbose);
      }
      const item = ITEM.exec(rest);
      if (item) {
        const held = list.items.find((row) => row.Id === Number(item[1]));
        return held ? respond(200, project(held, item[2]), verbose)
          : refusal(404, 'Item does not exist.');
      }
      if (rest.startsWith('/items')) {
        return respond(200, { value: list.items.map((row) => project(row, rest)) }, verbose);
      }
      if (rest === '/getitems' && method === 'POST') return respond(200, { results: [] }, true);
      return refusal(404, `unmocked ${path}`);
    };
""")

#: Records every request, for the mocks of other modules that keep no log of their own.
_RECORD = textwrap.dedent("""
    const SENT_LOG = [];
    process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT_LOG)));
    const mockedFetch = globalThis.fetch;
    globalThis.fetch = async (url, opts = {}) => {
      SENT_LOG.push({ verb: (opts.headers || {})['X-HTTP-Method'] || opts.method || 'GET',
        path: decodeURIComponent(String(url).split('/_api/')[1] || ''),
        body: opts.body === undefined ? '' : String(opts.body) });
      return mockedFetch(url, opts);
    };
""")


def _run_recorded(
    mock: str, config: dict[str, Any], probe: str,
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    """Run `probe` on a mock of another module, with every request it sends recorded."""
    script = (mock.replace("__CONFIG__", json.dumps(config)) + _RECORD
              + "\n" + _fixture_probe_js(MANUAL / probe))
    output = run_node(script)
    line = next(ln for ln in output.splitlines() if ln.startswith("__SENT__"))
    return _fixture_rows(output), list(json.loads(line.removeprefix("__SENT__")))


def _healthy(base: dict[str, Any], **changes: Any) -> dict[str, Any]:
    config: dict[str, Any] = json.loads(json.dumps(base))
    config.update(changes)
    return config


def _library(*titles: str) -> dict[str, Any]:
    return {"existing": {title: {"template": 101} for title in titles}}


def _nothing_written(sent: list[dict[str, str]]) -> bool:
    return not [r for r in sent if r["verb"] != "GET" and not r["path"].startswith("contextinfo")]


def _assert_held(rows: dict[str, dict[str, str]], fixture: str) -> None:
    assert rows[fixture]["outcome"] == "PASS", rows[fixture]
    assert not _voided_by(rows, fixture)


def _assert_voids_catalogued(
    rows: dict[str, dict[str, str]], probe: str, fixture: str, named: str,
) -> None:
    assert rows[fixture]["outcome"] == "FAIL", rows[fixture]
    assert named in rows[fixture]["evidence"], rows[fixture]
    assert _voided_by(rows, fixture) == _catalogued_dependents(probe, fixture)


#: Each generic-list probe on the generic mock: the fixture, and every title it reads back.
_GENERIC_LIST_PROBES = {
    "default-formula-functions-probe.js": (
        "field.default-formula.fixture-list-created", ["dbmlsp Probe Functions List"]),
    "blank-operand-probe.js": (
        "formula.validation.fixture-list-created", ["dbmlsp Probe Blank Operand"]),
    "field-sealed-probe.js": ("field.sealed.fixture-list-created", ["dbmlsp Probe Sealed Field"]),
    "unique-blanks-probe.js": ("field.unique.fixture-list-created", ["dbmlsp Probe Unique List"]),
    "lookup-acl-probe.js": (
        "access.lookup-acl.fixture-lists-created",
        ["dbmlsp Probe LookupTarget", "dbmlsp Probe LookupSource"]),
}
_GENERIC_CASES = [(probe, fixture, title)
                  for probe, (fixture, titles) in _GENERIC_LIST_PROBES.items()
                  for title in titles]


@pytest.mark.parametrize(("probe", "fixture", "title"), _GENERIC_CASES,
                         ids=[f"{p}:{t}" for p, _, t in _GENERIC_CASES])
def test_a_library_under_a_generic_list_name_voids_its_rows(
    probe: str, fixture: str, title: str,
) -> None:
    rows, sent = _run_probe(_LIST_MOCK, _library(title), probe)

    _assert_voids_catalogued(rows, probe, fixture, "BaseTemplate differs: read 101, declared 100")
    assert not _writes_to(sent, title, uploads=False)
    assert not [r for r in rows.values() if r["state"] == "open"]


@pytest.mark.parametrize("probe", list(_GENERIC_LIST_PROBES))
@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_a_generic_list_that_holds_establishes(probe: str, reused: bool) -> None:
    fixture, titles = _GENERIC_LIST_PROBES[probe]
    config = {"existing": {t: {"template": 100} for t in titles}} if reused else {}
    rows, _ = _run_probe(_LIST_MOCK, config, probe)

    _assert_held(rows, fixture)
    assert "BaseTemplate=100" in rows[fixture]["evidence"]


def test_lookup_acl_voids_its_rows_on_a_target_read_that_serves_no_id() -> None:
    """The lookup took the create's Id, so a target read with no Id built against undefined."""
    target, source = _GENERIC_LIST_PROBES["lookup-acl-probe.js"][1]
    config = {"existing": {target: {"template": 100, "omitId": True}}}
    rows, sent = _run_probe(_LIST_MOCK, config, "lookup-acl-probe.js")

    _assert_voids_catalogued(rows, "lookup-acl-probe.js",
                             "access.lookup-acl.fixture-lists-created", "target.Id")
    assert not _writes_to(sent, target, uploads=False)
    assert not _writes_to(sent, source, uploads=False)


# ---- Columns reused by name, read back as their declared shape -----------
_FUNCTIONS = "default-formula-functions-probe.js"
_FUNCTIONS_LIST = "dbmlsp Probe Functions List"
_FUNCTIONS_COLUMNS = "field.default-formula.fixture-columns-typed"


@pytest.mark.parametrize(
    ("props", "named"),
    [({"TypeAsString": "Text", "DefaultFormula": "=DAY(TODAY())"},
      'FnDay.TypeAsString differs: read "Text", declared "Number"'),
     ({"TypeAsString": "Number", "DefaultFormula": "=1"},
      'FnDay.DefaultFormula differs: read "=1", declared "=DAY(TODAY())"')],
    ids=["type", "formula"],
)
def test_functions_voids_the_fills_on_a_reused_column_of_another_shape(
    props: dict[str, Any], named: str,
) -> None:
    config = {"existing": {_FUNCTIONS_LIST: {"template": 100, "fields": {"FnDay": props}}}}
    rows, sent = _run_probe(_LIST_MOCK, config, _FUNCTIONS)

    _assert_voids_catalogued(rows, _FUNCTIONS, _FUNCTIONS_COLUMNS, named)
    # The negative control's item is the only one sent; no bare item is created.
    items = [r for r in sent if r["verb"] == "POST" and r["path"].endswith("/items")]
    assert len(items) == 1, items
    assert "dbmlspNoSuchColumn" in items[0]["body"], items


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_functions_establishes_columns_of_the_declared_shape(reused: bool) -> None:
    fields = {"FnDay": {"TypeAsString": "Number", "DefaultFormula": "=DAY(TODAY())"}}
    config = {"existing": {_FUNCTIONS_LIST: {"template": 100, "fields": fields}}}
    rows, _ = _run_probe(_LIST_MOCK, config if reused else {}, _FUNCTIONS)

    _assert_held(rows, _FUNCTIONS_COLUMNS)
    evidence = rows[_FUNCTIONS_COLUMNS]["evidence"]
    assert "FnDateTime.DisplayFormat=1" in evidence
    # A reused column's formula is a precondition; a created one's is the observation.
    assert ("FnDay.DefaultFormula" in evidence) is reused


_UNIQUE = "unique-blanks-probe.js"
_UNIQUE_COLUMN = "field.unique.fixture-unique-text-column"


def _unique(column: dict[str, Any]) -> dict[str, Any]:
    return {"existing": {"dbmlsp Probe Unique List": {
        "template": 100, "fields": {"UniqueRef": column}}}}


def test_unique_blanks_voids_its_rows_on_a_reused_column_of_another_type() -> None:
    column = {"TypeAsString": "Note", "EnforceUniqueValues": True, "Indexed": True}
    rows, sent = _run_probe(_LIST_MOCK, _unique(column), _UNIQUE)

    _assert_voids_catalogued(rows, _UNIQUE, _UNIQUE_COLUMN,
                             'TypeAsString differs: read "Note", declared "Text"')
    assert not [r for r in sent if r["verb"] != "GET" and "UniqueRef" in r["body"]]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_unique_blanks_establishes_a_unique_indexed_text_column(reused: bool) -> None:
    column = {"TypeAsString": "Text", "EnforceUniqueValues": True, "Indexed": True}
    rows, _ = _run_probe(_LIST_MOCK, _unique(column) if reused else {}, _UNIQUE)

    _assert_held(rows, _UNIQUE_COLUMN)


_SEALED = "field-sealed-probe.js"
_SEALED_SUBJECT = "field.sealed.fixture-subject-column"


def _sealed(subject_type: str) -> dict[str, Any]:
    return {"existing": {"dbmlsp Probe Sealed Field": {
        "template": 100, "fields": {"SealSubject": {"TypeAsString": subject_type}}}}}


def test_field_sealed_voids_its_rows_on_a_reused_subject_that_is_not_text() -> None:
    rows, sent = _run_probe(_LIST_MOCK, _sealed("Note"), _SEALED)

    subject = rows[_SEALED_SUBJECT]
    assert subject["outcome"] == "FAIL", subject
    assert 'TypeAsString="Note"' in subject["evidence"], subject
    assert _void_ids(rows) == _catalogued_dependents(_SEALED, _SEALED_SUBJECT)
    assert not [r for r in sent if r["verb"] in {"MERGE", "DELETE"}]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_field_sealed_establishes_an_unsealed_text_subject(reused: bool) -> None:
    rows, _ = _run_probe(_LIST_MOCK, _sealed("Text") if reused else {}, _SEALED)

    assert rows[_SEALED_SUBJECT]["outcome"] == "PASS", rows[_SEALED_SUBJECT]


# ---- today-source: DM, TD, and what the REST fill records ----------------
_TODAY = "today-source-probe.js"
_DM = "query.caml-adhoc.fixture-dm-column"
_TD = "field.date.fixture-td-column"
_FILL = "field.date.dynamic-default-rest-fill"
_TODAY_GATES = ("CONFIRMED", "ALLOW_WRITES", "ADD_DEFAULT_COLUMN")
_DATE = {"TypeAsString": "DateTime", "DisplayFormat": 0}
_TD_HEALTHY = {**_DATE, "DefaultValue": "[today]"}


def _today(fields: dict[str, Any], **changes: Any) -> dict[str, Any]:
    return {"existing": {"dbml-probe-today-semantics": {"template": 100, "fields": fields}},
            **changes}


#: What a column of each name is written with: DM seeds two dated rows, TD's row is bare.
_TODAY_WRITES = {_DM: '"DM":', _TD: '"Title":"default-today"'}


@pytest.mark.parametrize(
    ("fixture", "fields", "named"),
    [(_DM, {"DM": {**_DATE, "DisplayFormat": 1}}, "DisplayFormat differs: read 1, declared 0"),
     (_TD, {"DM": _DATE, "TD": {**_TD_HEALTHY, "DefaultValue": None}},
      'DefaultValue differs: read null, declared "[today]"'),
     (_TD, {"DM": _DATE, "TD": {**_TD_HEALTHY, "TypeAsString": "Text"}},
      'TypeAsString differs: read "Text", declared "DateTime"')],
    ids=["dm-date-and-time", "td-no-default", "td-text"],
)
def test_today_source_voids_the_rows_on_a_reused_column_of_another_shape(
    fixture: str, fields: dict[str, Any], named: str,
) -> None:
    rows, sent = _run_probe(_LIST_MOCK, _today(fields), _TODAY, _TODAY_GATES)

    _assert_voids_catalogued(rows, _TODAY, fixture, named)
    assert not [r for r in sent if r["verb"] == "POST" and _TODAY_WRITES[fixture] in r["body"]]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_today_source_establishes_dm_and_td_of_the_declared_shape(reused: bool) -> None:
    fields = {"DM": _DATE, "TD": _TD_HEALTHY} if reused else {}
    rows, _ = _run_probe(_LIST_MOCK, _today(fields), _TODAY, _TODAY_GATES)

    _assert_held(rows, _DM)
    _assert_held(rows, _TD)


@pytest.mark.parametrize(("fill", "outcome"), [(True, "FILLED"), (False, "BLANK")])
def test_today_source_records_the_rest_fill_from_the_item_it_read_back(
    fill: bool, outcome: str,
) -> None:
    """The item carried no TD, so what TD reads back is the answer; a literal PASS said nothing."""
    rows, _ = _run_probe(_LIST_MOCK, _today({}, fillToday=fill), _TODAY, _TODAY_GATES)

    row = rows[_FILL]
    assert row["outcome"] == outcome, row
    assert row["state"] == "settled", row
    assert f"TD ([today]) = {'2026-09-24T00:00:00Z' if fill else 'null'}" in row["evidence"]


def test_today_source_leaves_the_rest_fill_open_when_the_item_is_refused() -> None:
    """A refused create observed no fill, so it is neither FAIL nor an answer."""
    rows, _ = _run_probe(_LIST_MOCK, _today({}, refuseItems=True), _TODAY, _TODAY_GATES)

    _assert_held(rows, _TD)
    assert rows[_FILL]["outcome"] == "NOT ESTABLISHED", rows[_FILL]
    assert rows[_FILL]["state"] == "open", rows[_FILL]


def test_today_source_does_not_ask_the_fill_without_add_default_column() -> None:
    rows, sent = _run_probe(_LIST_MOCK, _today({"DM": _DATE}), _TODAY)

    assert rows[_TD]["outcome"] == "NOT REACHED", rows[_TD]
    assert rows[_FILL]["outcome"] == "NOT REACHED", rows[_FILL]
    assert not [r for r in sent if "TD" in r["body"]]


# ---- calculated-operand, on the shared-v2 core ---------------------------
_OPERAND = "calculated-operand-probe.js"
_OPERAND_ROW = "formula.calc.fixture-lists-created"
_OPERAND_OWNER = "dbml-sharepoint calculated-operand probe. Safe to recycle."
_OPERAND_LISTS = ("dbmlsp Probe CalcOperands", "dbmlsp Probe CalcOperands Target")
_V2_WINDOW = (
    "globalThis.window = { location: { origin: 'https://example.sharepoint.com' }, "
    "_spPageContextInfo: { webServerRelativeUrl: '/sites/test', "
    "webAbsoluteUrl: 'https://example.sharepoint.com/sites/test' } };\n"
    "const SENT = [];\n"
    "process.on('exit', () => console.log('__SENT__' + JSON.stringify(SENT)));\n"
)


def _run_operand(
    existing: dict[str, int],
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    """The v2 core prints its table through console.table, so the dump is spliced there."""
    js = (MANUAL / _OPERAND).read_text(encoding="utf-8")
    for gate in ("CONFIRMED", "ALLOW_WRITES"):
        opened = js.replace(f"  const {gate} = false;", f"  const {gate} = true;", 1)
        assert opened != js, f"the {gate} gate is not spelled as this test expects"
        js = opened
    js = js.replace("console.table(results);",
                    "console.log('__ROWS__' + JSON.stringify(results)); console.table(results);")
    config = {"existing": {title: {"template": template, "description": _OPERAND_OWNER}
                           for title, template in existing.items()}}
    output = run_node(_V2_WINDOW + _LIST_MOCK.replace("__CONFIG__", json.dumps(config))
                      + "\n" + js)
    table = [ln for ln in output.splitlines() if ln.startswith("__ROWS__")][-1]
    rows = {row["id"]: {"outcome": row["observed"], "evidence": row["detail"],
                        "state": row["state"]}
            for row in json.loads(table.removeprefix("__ROWS__"))}
    sent = next(ln for ln in output.splitlines() if ln.startswith("__SENT__"))
    return rows, list(json.loads(sent.removeprefix("__SENT__")))


@pytest.mark.parametrize("title", _OPERAND_LISTS, ids=["main", "target"])
def test_calculated_operand_voids_every_operand_on_a_library_of_a_list_name(title: str) -> None:
    rows, sent = _run_operand({title: 101})

    row = rows[_OPERAND_ROW]
    assert row["outcome"] == "FAIL", row
    assert f"'{title}' BaseTemplate=101" in row["evidence"], row
    voided = {row_id for row_id, r in rows.items() if r["state"] == "void"}
    assert voided == _catalogued_dependents(_OPERAND, _OPERAND_ROW)
    assert not [r for r in sent if "createfieldasxml" in r["path"]]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_calculated_operand_establishes_two_generic_lists(reused: bool) -> None:
    rows, _ = _run_operand(dict.fromkeys(_OPERAND_LISTS, 100) if reused else {})

    assert rows[_OPERAND_ROW]["outcome"] == "PASS", rows[_OPERAND_ROW]
    assert not [r for r in rows.values() if r["state"] == "void"]


# ---- The probes that keep a runtime mock of their own ---------------------
_CHOICE = "calculated-choice-operand.js"
_CHOICE_LIST = "dbmlsp Probe CalcChoice"
_CHOICE_ROW = "formula.choice.fixture-list-created"
_CHOICE_TARGET_ROW = "formula.calc.fixture-target-list-created"


@pytest.mark.parametrize(
    ("title", "fixture"),
    [(_CHOICE_LIST, _CHOICE_ROW), (f"{_CHOICE_LIST} Target", _CHOICE_TARGET_ROW)],
    ids=["list", "target"],
)
def test_calc_choice_voids_the_rows_on_a_library_under_a_list_name(
    title: str, fixture: str,
) -> None:
    config = _healthy(_CALC_CHOICE_HEALTHY, existingLists=[title], listTemplates={title: 101})
    rows, sent = _run_recorded(_CALC_CHOICE_HARNESS, config, _CHOICE)

    _assert_voids_catalogued(rows, _CHOICE, fixture, "BaseTemplate differs: read 101, declared 100")
    assert not _writes_to(sent, title, uploads=False)
    # Only the lookup leg rests on the target, and no lookup is pointed at it.
    assert not [r for r in sent if _LOOKUP_CREATE in r["body"]]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_calc_choice_establishes_its_two_generic_lists(reused: bool) -> None:
    lists = [_CHOICE_LIST, f"{_CHOICE_LIST} Target"] if reused else []
    rows, _ = _run_recorded(_CALC_CHOICE_HARNESS,
                            _healthy(_CALC_CHOICE_HEALTHY, existingLists=lists), _CHOICE)

    _assert_held(rows, _CHOICE_ROW)
    _assert_held(rows, _CHOICE_TARGET_ROW)


_TRANSITION = "unique-transition-probe.js"
_TRANSITION_ROW = "field.unique.fixture-transition-list"


def test_unique_transition_voids_its_rows_on_a_library_under_its_name() -> None:
    config = _healthy(_TRANSITION_HEALTHY, listExists=True, listTemplate=101)
    rows, sent = _run_recorded(_TRANSITION_HARNESS, config, _TRANSITION)

    _assert_voids_catalogued(rows, _TRANSITION, _TRANSITION_ROW,
                             "BaseTemplate differs: read 101, declared 100")
    assert _nothing_written(sent)


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_unique_transition_establishes_a_generic_list(reused: bool) -> None:
    rows, _ = _run_recorded(_TRANSITION_HARNESS,
                            _healthy(_TRANSITION_HEALTHY, listExists=reused), _TRANSITION)

    _assert_held(rows, _TRANSITION_ROW)
    _assert_held(rows, "field.unique.fixture-unconstrained-columns")


_PROJECTED = "projected-lookup-probe.js"
_PROJECTED_ROW = "field.lookup.fixture-lists-created"


@pytest.mark.parametrize("title", ["dbmlsp Probe ProjTarget", "dbmlsp Probe ProjSource"],
                         ids=["target", "source"])
def test_projected_lookup_voids_its_rows_on_a_library_under_a_list_name(title: str) -> None:
    config = _healthy(_CROSS_WEB_HEALTHY, listsExist=True, listTemplates={title: 101})
    rows, sent = _run_recorded(_CROSS_WEB_HARNESS, config, _PROJECTED)

    _assert_voids_catalogued(rows, _PROJECTED, _PROJECTED_ROW, f"'{title}' BaseTemplate=101")
    assert _nothing_written(sent)


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_projected_lookup_establishes_two_generic_lists(reused: bool) -> None:
    rows, _ = _run_recorded(_CROSS_WEB_HARNESS,
                            _healthy(_CROSS_WEB_HEALTHY, listsExist=reused), _PROJECTED)

    _assert_held(rows, _PROJECTED_ROW)
    assert rows["field.lookup.control-primary-lookup-created"]["outcome"] == "PASS"


_CROSS = "cross-lookup-probe.js"
_CROSS_ROW = "library.lookup.fixture-lists-generic"


@pytest.mark.parametrize("title", ["dbmlsp Probe XLookup Target", "dbmlsp Probe XLookup List"],
                         ids=["target", "source"])
def test_cross_lookup_voids_its_rows_on_a_library_under_a_list_name(title: str) -> None:
    rows, sent = _run_on_site(_SITE_MOCK, {"lists": {title: 101}}, _CROSS)

    _assert_voids_catalogued(rows, _CROSS, _CROSS_ROW,
                             "BaseTemplate differs: read 101, declared 100")
    assert not _writes_to(sent, title, uploads=False)
    assert not [r for r in sent if "createfieldasxml" in r["path"]]


@pytest.mark.parametrize("reused", [False, True], ids=["created", "reused"])
def test_cross_lookup_establishes_its_generic_lists(reused: bool) -> None:
    lists = {"dbmlsp Probe XLookup Target": 100, "dbmlsp Probe XLookup List": 100}
    rows, _ = _run_on_site(_SITE_MOCK, {"lists": lists if reused else {}}, _CROSS)

    _assert_held(rows, _CROSS_ROW)
    assert rows["library.lookup.fixture-containers-ready"]["outcome"] == "PASS"


# ---- threshold-index: both lists, the probe columns, and Parent's target --
_THRESHOLD_INDEX = "threshold-index-probe.js"
_TI_LISTS = "scale.threshold.fixture-lists-created"
_TI_COLUMNS = "scale.index.fixture-columns-typed"


@pytest.mark.parametrize(
    ("changes", "fixture", "named"),
    [({"mainTemplate": 101}, _TI_LISTS, "main.BaseTemplate differs: read 101, declared 100"),
     ({"parentTemplate": 101}, _TI_LISTS, "parent.BaseTemplate differs: read 101, declared 100"),
     ({"fieldTypes": {"ClosedAt": "Text"}}, _TI_COLUMNS,
      'ClosedAt.TypeAsString differs: read "Text", declared "DateTime"'),
     ({"parentLookup": "{0000000b-0000-4000-8000-00000000000b}"}, _TI_COLUMNS,
      "Parent.LookupList differs"),
     ({"parentLookup": "{00000000-0000-0000-0000-000000000000}"}, _TI_COLUMNS,
      "Parent.LookupList differs")],
    ids=["main-library", "parent-library", "column-type", "parent-bound-to-main",
         "parent-unbound"],
)
def test_threshold_index_voids_every_row_on_a_fixture_that_does_not_hold(
    changes: dict[str, Any], fixture: str, named: str,
) -> None:
    rows, sent = _run_recorded(_THRESHOLD_INDEX_HARNESS,
                               _healthy(_THRESHOLD_INDEX_HEALTHY, **changes), _THRESHOLD_INDEX)

    _assert_voids_catalogued(rows, _THRESHOLD_INDEX, fixture, named)
    assert not [r for r in sent if r["verb"] == "MERGE" or "$batch" in r["path"]
                or (r["verb"] == "POST" and r["path"].endswith("/items"))]


def test_threshold_index_establishes_its_lists_and_columns() -> None:
    """Parent's LookupList is served braced, and still matches the parent list's bare Id."""
    rows, _ = _run_recorded(_THRESHOLD_INDEX_HARNESS, _healthy(_THRESHOLD_INDEX_HEALTHY),
                            _THRESHOLD_INDEX)

    _assert_held(rows, _TI_LISTS)
    _assert_held(rows, _TI_COLUMNS)
    assert rows["scale.index.fixture-indexes-set"]["outcome"] == "CONFIRMED"
