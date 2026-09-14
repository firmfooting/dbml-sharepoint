"""A failed metadata control cannot establish library content type findings."""

import json
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_DEPENDENT = (
    "library.content-type.custom-content-type-on-library",
    "library.content-type.content-type-at-upload",
    "library.content-type.column-bound-to-one-content-type",
)
_HARNESS = r"""
const config = __CONFIG__;
globalThis.window = {_spPageContextInfo: {
  webAbsoluteUrl: 'https://example.sharepoint.com/sites/test'
}};
const pathRoot = "web/lists/getbytitle('dbmlsp Probe ContentType')";
const custom = {Name: 'dbmlsp Custom DocType', StringId: '0x010100ABC'};
const contentTypes = [
  {Name: 'Document', StringId: '0x0101'}, {Name: 'Folder', StringId: '0x0120'}
];
const uploadItem = {Id: 2, ContentTypeId: '0x0101'};
const links = {'0x0101': [], '0x0120': []};
const response = (status, payload) => ({
  ok: status >= 200 && status < 300, status,
  json: async () => payload, text: async () => JSON.stringify(payload)
});
globalThis.fetch = async (url, options = {}) => {
  const path = String(url).split('/_api/')[1];
  const post = options.method === 'POST';
  if (path === 'contextinfo') {
    return response(200, {d: {GetContextWebInformation: {FormDigestValue: 'digest'}}});
  }
  if (path === pathRoot) return response(post ? 204 : 200, {BaseTemplate: 101});
  if (path.includes('/RootFolder/Files/add(')) return response(200, {});
  if (path.startsWith('web/contenttypes?')) return response(200, {value: [custom]});
  if (path === pathRoot + '/contenttypes/addAvailableContentType') {
    contentTypes.push(custom);
    return response(200, custom);
  }
  if (path === pathRoot + '/contenttypes' || path.startsWith(pathRoot + '/contenttypes?')) {
    return response(200, {value: contentTypes});
  }
  if (path === pathRoot + '/fields/createfieldasxml') return response(200, {});
  const contentType = path.match(/contenttypes\('([^']+)'\)\/fieldlinks/);
  if (contentType && contentType[1] in links) {
    if (post) links[contentType[1]].push({Name: JSON.parse(options.body).FieldInternalName});
    return response(post ? 201 : 200, {value: links[contentType[1]]});
  }
  if (path.startsWith(pathRoot + '/items?')) {
    const initial = path.includes("FileLeafRef eq 'dbmlsp-content-type-probe.txt'");
    return response(200, {value: initial ? (config.noItem ? [] : [{Id: 1}]) : [uploadItem]});
  }
  if (path === pathRoot + '/items(1)' && post) {
    const body = JSON.parse(options.body);
    if ('NoSuchColumnAtAll' in body) {
      if (config.controlStatus === 0) throw new Error('network unavailable');
      return response(config.controlStatus, {});
    }
  }
  if (path.startsWith(pathRoot + '/items(2)')) {
    if (post) Object.assign(uploadItem, JSON.parse(options.body));
    return response(post ? 204 : 200, uploadItem);
  }
  throw new Error(`Unexpected request: ${options.method || 'GET'} ${path}`);
};
"""


def _run_probe(control_status: int = 400, *, no_item: bool = False) -> dict[str, Any]:
    source = (MANUAL / "library-content-type-probe.js").read_text(encoding="utf-8")
    source = source.replace("const CONFIRMED = false;", "const CONFIRMED = true;")
    source = source.replace("const ALLOW_WRITES = false;", "const ALLOW_WRITES = true;")
    source = source.replace(
        "const report = () => {",
        "const report = () => { console.log('__ROWS__' + JSON.stringify(RESULTS));",
    )
    config = json.dumps({"controlStatus": control_status, "noItem": no_item})
    output = run_node(_HARNESS.replace("__CONFIG__", config) + source)
    rows = [line.removeprefix("__ROWS__") for line in output.splitlines()
            if line.startswith("__ROWS__")]
    assert len(rows) == 1, output
    return {row["id"]: row for row in json.loads(rows[0])}


@pytest.mark.parametrize("status", [400, 500])
def test_library_content_type_control_allows_observed_findings(status: int) -> None:
    rows = _run_probe(status)
    assert rows["library.content-type.control-missing-column-refused"]["outcome"] == "PASS"
    assert rows[_DEPENDENT[0]]["outcome"] == "PASS"
    assert rows[_DEPENDENT[1]]["outcome"] == (
        "UPLOAD LANDS AS DEFAULT DOCUMENT; CHANGED VIA ITEM MERGE"
    )
    assert rows[_DEPENDENT[2]]["outcome"] == "BOUND TO DOCUMENT ONLY (PER-CONTENT-TYPE)"
    for finding in _DEPENDENT:
        assert rows[finding]["state"] == "settled"


@pytest.mark.parametrize("status", [200, 204, 401, 403, 408, 429, 0])
def test_library_content_type_voids_unestablished_control(status: int) -> None:
    rows = _run_probe(status)
    for finding in _DEPENDENT:
        assert rows[finding]["outcome"] == "NOT ESTABLISHED"
        assert rows[finding]["state"] == "void"
        assert "negative control did not hold; observed:" in rows[finding]["evidence"]
    assert "list-scoped content type ID: 0x010100ABC" in rows[_DEPENDENT[0]]["evidence"]
    assert "updated the item to 0x010100ABC" in rows[_DEPENDENT[1]]["evidence"]
    assert "Folder (0x0120): absent" in rows[_DEPENDENT[2]]["evidence"]
    assert rows["library.content-type.default-content-types"]["state"] == "settled"


def test_library_content_type_voids_control_without_file_item() -> None:
    rows = _run_probe(no_item=True)
    assert rows["library.content-type.control-missing-column-refused"]["outcome"] == (
        "NOT ESTABLISHED"
    )
    for finding in _DEPENDENT:
        assert rows[finding]["outcome"] == "NOT ESTABLISHED"
        assert rows[finding]["state"] == "void"
    assert rows["library.content-type.default-content-types"]["state"] == "settled"
