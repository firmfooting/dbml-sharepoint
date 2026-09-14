"""A library metadata control must gate its dependent probe findings."""

import json
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

_DEPENDENT = (
    "library.column.multi-choice-column-on-library",
    "library.column.multi-lookup-column-on-library",
    "library.column.custom-column-formatting",
)
_HARNESS = r"""
const config = __CONFIG__;
globalThis.window = {_spPageContextInfo: {
  webAbsoluteUrl: 'https://example.sharepoint.com/sites/test'
}};
const item = {Id: 1};
const fields = {ColMultiChoice: {}, ColMultiLookup: {}, ColFormat: {}};
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
  if (path.includes("getbytitle('dbmlsp Probe LibColTarget')")) {
    if (path.includes('/items?')) return response(200, {value: [{Id: 4}, {Id: 7}]});
    return response(200, {Id: 'target', BaseTemplate: 100});
  }
  if (path.includes('/RootFolder/Files/add(')) return response(200, {Name: 'file.txt'});
  const field = path.match(/getbyinternalnameortitle\('([^']+)'\)/);
  if (field && fields[field[1]]) {
    if (post) Object.assign(fields[field[1]], JSON.parse(options.body));
    return response(post ? 204 : 200, fields[field[1]]);
  }
  if (path.includes('/items?')) {
    return response(200, {value: config.noItem ? [] : [item]});
  }
  if (path.includes('/items(1)')) {
    if (post) {
      const body = JSON.parse(options.body);
      if ('NoSuchColumnAtAll' in body) {
        if (config.controlStatus === 0) throw new Error('network unavailable');
        return response(config.controlStatus, {});
      }
      Object.assign(item, body);
      return response(204, {});
    }
    return response(200, item);
  }
  if (path === "web/lists/getbytitle('dbmlsp Probe LibColInteractions')") {
    return response(200, {Id: 'library', BaseTemplate: 101});
  }
  throw new Error(`Unexpected request: ${options.method || 'GET'} ${path}`);
};
"""


def _run_probe(control_status: int = 400, *, no_item: bool = False) -> dict[str, Any]:
    source = (MANUAL / "library-column-interactions-probe.js").read_text(encoding="utf-8")
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
def test_library_column_interactions_control_allows_observed_findings(status: int) -> None:
    rows = _run_probe(status)
    assert rows["library.column.control-missing-column-refused"]["outcome"] == "PASS"
    for finding in _DEPENDENT:
        assert rows[finding]["outcome"] == "PASS"
        assert rows[finding]["state"] == "settled"


@pytest.mark.parametrize("status", [200, 204, 401, 403, 408, 429, 0])
def test_library_column_interactions_voids_unestablished_control(status: int) -> None:
    rows = _run_probe(status)
    for finding in _DEPENDENT:
        assert rows[finding]["outcome"] == "NOT ESTABLISHED"
        assert rows[finding]["state"] == "void"
        assert "negative control did not hold; observed: successfully" in rows[finding]["evidence"]
    assert '["Alpha","Beta"]' in rows[_DEPENDENT[0]]["evidence"]
    assert "[4,7]" in rows[_DEPENDENT[1]]["evidence"]


def test_library_column_interactions_voids_control_without_file_item() -> None:
    rows = _run_probe(no_item=True)
    for finding in _DEPENDENT:
        assert rows[finding]["outcome"] == "NOT ESTABLISHED"
        assert rows[finding]["state"] == "void"
    assert "no file item" in rows[_DEPENDENT[0]]["evidence"]
    assert "successfully wrote and read back" in rows[_DEPENDENT[2]]["evidence"]
