---
title: immutable_shape
sidebar_position: 14
---

# `dbml_sharepoint.analysis.immutable_shape`

*the properties a deploy refuses to change*

The field and list properties SharePoint will not let a deploy change.

`deploy.js.txt` refuses to reconcile these: a mismatch aborts before anything is
written, because the platform offers no in-place change and the tool will not
delete and recreate an object holding somebody's data. The comparisons live in
`templates/deploy/_field_reconcile.js.j2`; this module is the list of what they
cover, so the delta report and the deployment record can iterate it instead of
restating it. `test/test_immutable_shape.py` fails if the two ever disagree.

### `IMMUTABLE_FIELD_PROPERTIES`

```python
IMMUTABLE_FIELD_PROPERTIES = ('InternalName', 'TypeAsString', 'ReadOnlyField', 'Sealed')
```

### `IMMUTABLE_LOOKUP_PROPERTIES`

```python
IMMUTABLE_LOOKUP_PROPERTIES = ('LookupList', 'LookupField')
```

### `IMMUTABLE_LIST_PROPERTIES`

```python
IMMUTABLE_LIST_PROPERTIES = ('BaseTemplate',)
```

