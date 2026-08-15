---
title: demogen
sidebar_position: 19
---

# `dbml_sharepoint.generators.demogen`

*demo-data.js*

Render demo-data.js — declared demo/sample rows, emitted with --seed.

The plan is generation-time typed: each field carries a `kind` so the
script knows whether to write a literal, resolve the deploying operator
(person columns take `<Name>Id`), resolve a demo_ref to a created item's
Id (lookups also take `<Name>Id`), or compute a run-time date from a
`today±N` offset — cadence-derived demo surfaces (Review due, overdue
formatting, Tolerance due) must land on whatever day the demo runs.
The '[DEMO] ' Title marker (validated mandatory) is the in-record notice
and the teardown contract.

### `DEMO_TITLE_PREFIX`

```python
DEMO_TITLE_PREFIX = '[DEMO] '
```

### `generate_demo_js`

```python
def generate_demo_js(*, schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model._mapping_types.MappingBundle, release: dbml_sharepoint.model.release.Release, site_url: str, site_role: str, source_dbml: str, generated_at: str) -> str
```

