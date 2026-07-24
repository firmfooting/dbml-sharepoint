---
title: demogen
sidebar_position: 13
---

# `dbml_sharepoint.demogen`

*Generator — demo-data.js*

Render demo-data.js — declared demo/sample rows, emitted with --seed.

The plan is generation-time typed: each field carries a `kind` so the
script knows whether to write a literal, resolve the deploying operator
(person columns take `<Name>Id`), resolve a demo_ref to a created item's
Id (lookups also take `<Name>Id`), or compute a run-time date from a
`today±N` offset — cadence-derived demo surfaces (Reviews due, overdue
formatting, Tolerance expiring) must land on whatever day the demo runs.
The '[DEMO] ' Title marker (validated mandatory) is the in-record notice
and the teardown contract.

### `DEMO_TITLE_PREFIX`

```python
DEMO_TITLE_PREFIX = '[DEMO] '
```

### `generate_demo_js`

```python
def generate_demo_js(*, schema: dbml_sharepoint.parser.Schema, bundle: dbml_sharepoint.mapping_loader.MappingBundle, release: dbml_sharepoint.release.Release, site_url: str, site_role: str, source_dbml: str, generated_at: str) -> str
```

