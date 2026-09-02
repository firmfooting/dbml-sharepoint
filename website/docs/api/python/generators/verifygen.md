---
title: verifygen
sidebar_position: 30
---

# `dbml_sharepoint.generators.verifygen`

*verify.js: each clock cell a pack uses, on a scratch list*

verify.js.txt: each clock cell a pack uses, exercised on a scratch list.

The deploy writes a rule and reads the bytes back; it cannot see whether
SharePoint evaluates the rule the way the mapping meant. This script can.
For every clock cell the pack uses (`analysis/clock_usage.py`) it puts one
column carrying that cell's exact rendering on a hidden scratch list, saves
at the boundaries the cell promises, queries with the elements a view would,
and reports whether the site kept the promise.

The checks are cells, not the pack's rules: the same handful of columns and
cases verify any pack, and the table in `analysis/clock_cells.py` is what
both the build and the check read.

### `DATE_ONLY`

```python
DATE_ONLY = 0
```

### `DATE_AND_TIME`

```python
DATE_AND_TIME = 1
```

### `HOUR`

```python
HOUR = 3600
```

### `verify_targets`

```python
def verify_targets(schema: 'Schema', bundle: 'MappingBundle', site_role: 'str') -> 'dict[str, Any]'
```

The data the verify script loops over, derived from the pack's clock use.

### `generate_verify_js`

```python
def generate_verify_js(*, schema: 'Schema', bundle: 'MappingBundle', release: 'Release', site_url: 'str', site_role: 'str', source_dbml: 'str', generated_at: 'str') -> 'str'
```

