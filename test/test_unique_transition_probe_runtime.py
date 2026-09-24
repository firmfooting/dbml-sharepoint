"""The unique-transition probe must establish fixtures before measuring them."""

import json
from typing import Any

import pytest
from _node import NODE, run_node
from _paths import MANUAL

_HARNESS = r"""
const config = __CONFIG__;
globalThis.window = {_spPageContextInfo: {webAbsoluteUrl: 'https://example.test'}};
const response = (status, body) => ({
  ok: status >= 200 && status < 300, status,
  json: async () => body, text: async () => JSON.stringify(body),
});
const fields = Object.fromEntries(['DupRef', 'UniqRef', 'IdxRef', 'NoteRef'].map(name => [
  name, {Title: name, TypeAsString: name === 'NoteRef' ? 'Note' : 'Text',
         EnforceUniqueValues: false, Indexed: false, ...(config.fields || {})[name]},
]));
for (const [name, property] of config.omit || []) delete fields[name][property];
const items = [];
let merges = 0;
globalThis.fetch = async (url, options = {}) => {
  const path = url.split('/_api/')[1];
  const sent = JSON.parse(options.body || '{}');
  if (path === 'contextinfo') return response(200, {
    d: {GetContextWebInformation: {FormDigestValue: 'digest'}},
  });
  const field = path.match(/getbyinternalnameortitle\('([^']+)'\)/);
  if (field) {
    const name = field[1];
    if (options.method === 'POST') {
      merges++;
      if (name === 'NoteRef' || name === 'DupRef') return response(400, {});
      Object.assign(fields[name], sent);
    }
    const body = {...fields[name]};
    if (Object.hasOwn(config, 'fieldPayload')) return response(200, config.fieldPayload);
    if (merges && config.omitAfter) delete body[config.omitAfter];
    return response(200, body);
  }
  if (path.includes('/items')) {
    if (options.method === 'POST') {
      items.push({Id: items.length + 1, ...sent});
      return response(201, items.at(-1));
    }
    return response(200, config.omitItems ? {} : {value: items});
  }
  if (path.startsWith('web/lists/getbytitle(')) {
    return response(200, Object.hasOwn(config, 'list') ? config.list : {BaseTemplate: 100});
  }
  throw new Error(`Unhandled ${options.method || 'GET'} ${path}`);
};
"""


def _run_probe(*, mutate: bool = False, **config: Any) -> dict[str, dict[str, str]]:
    script = (MANUAL / 'unique-transition-probe.js').read_text(encoding='utf-8')
    for gate in ('CONFIRMED', 'ALLOW_WRITES'):
        script = script.replace(f'const {gate} = false;', f'const {gate} = true;', 1)
    script = script.replace(
        'const report = () => {',
        "const report = () => { console.log('__ROWS__' + JSON.stringify(RESULTS));",
        1,
    )
    if mutate:
        guard = "declared[`${column.name}.TypeAsString`] = column.name === NOTE ? 'Note' : 'Text';"
        assert guard in script
        script = script.replace(guard, '')
    output = run_node(_HARNESS.replace('__CONFIG__', json.dumps(config)) + script)
    line = next(line for line in output.splitlines() if line.startswith('__ROWS__'))
    return {row['id'].removeprefix('field.unique.'): row for row in json.loads(line[8:])}


pytestmark = pytest.mark.skipif(NODE is None, reason='node is not installed')


def test_unique_transition_healthy_reused_fixture_reaches_measurements() -> None:
    rows = _run_probe()
    assert rows['fixture-unconstrained-columns']['outcome'] == 'PASS'
    assert rows['control-note-column-refused']['outcome'] == 'REFUSED'
    assert rows['control-transition-on-unique-values']['outcome'] == 'ACCEPTED'
    assert rows['transition-on-duplicate-values']['outcome'] == 'REFUSED'


@pytest.mark.parametrize('name', ['NoteRef', 'DupRef', 'UniqRef', 'IdxRef'])
@pytest.mark.parametrize('missing', [False, True])
def test_unique_transition_wrong_or_absent_type_voids_measurements(
    name: str, missing: bool,
) -> None:
    config = {'omit': [[name, 'TypeAsString']]} if missing else {
        'fields': {name: {'TypeAsString': 'Text' if name == 'NoteRef' else 'Note'}},
    }
    rows = _run_probe(**config)
    assert rows['fixture-unconstrained-columns']['outcome'] == 'FAIL'
    assert 'TypeAsString' in rows['fixture-unconstrained-columns']['evidence']
    for key in ('fixture-duplicate-items', 'control-note-column-refused',
                'control-transition-on-unique-values', 'transition-on-duplicate-values',
                'transition-without-index'):
        assert rows[key]['state'] == 'void'


def test_unique_transition_type_guard_mutation_exposes_false_control() -> None:
    rows = _run_probe(mutate=True, fields={'NoteRef': {'TypeAsString': 'Text'}})
    assert rows['control-note-column-refused']['outcome'] == 'REFUSED'
    assert rows['transition-on-duplicate-values']['outcome'] == 'REFUSED'


@pytest.mark.parametrize('property_name', ['EnforceUniqueValues', 'Indexed'])
def test_unique_transition_missing_constraint_is_not_false(property_name: str) -> None:
    rows = _run_probe(omit=[['DupRef', property_name]])
    assert rows['fixture-unconstrained-columns']['outcome'] == 'FAIL'
    assert rows['control-note-column-refused']['state'] == 'void'


@pytest.mark.parametrize('shape', [{}, {'BaseTemplate': 101}, 'broken', 42, False, [], None])
def test_unique_transition_requires_generic_list(shape: Any) -> None:
    rows = _run_probe(list=shape)
    assert rows['fixture-transition-list']['outcome'] == 'FAIL'
    assert rows['fixture-unconstrained-columns']['state'] == 'void'


@pytest.mark.parametrize('shape', ['broken', 42, False, [], None])
def test_unique_transition_malformed_field_payload_voids_measurements(shape: Any) -> None:
    rows = _run_probe(fieldPayload=shape)
    assert rows['fixture-unconstrained-columns']['outcome'] == 'FAIL'
    assert rows['control-note-column-refused']['state'] == 'void'


def test_unique_transition_missing_item_collection_is_not_an_empty_list() -> None:
    rows = _run_probe(omitItems=True)
    assert rows['fixture-duplicate-items']['outcome'] == 'FAIL'
    assert rows['control-note-column-refused']['state'] == 'void'


@pytest.mark.parametrize('property_name', ['EnforceUniqueValues', 'Indexed'])
def test_unique_transition_missing_observation_cannot_settle_acceptance(
    property_name: str,
) -> None:
    rows = _run_probe(omitAfter=property_name)
    assert rows['control-transition-on-unique-values']['outcome'] == 'NOT ESTABLISHED'
    assert rows['transition-on-duplicate-values']['state'] == 'void'
