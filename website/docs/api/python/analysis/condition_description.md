---
title: condition_description
sidebar_position: 21
---

# `dbml_sharepoint.analysis.condition_description`

*human-readable condition prose*

How a condition tree reads in prose, for the manifest and the reporting pack.

Split out of `analysis/conditions.py` (#168), which is normalisation,
validation and three SharePoint renderings in one 1,900-line module. This
concern shares none of that: no target, no capability table, no finding, no
column type. It is a pure recursive walk over the authored tree.

The split is worth having because of who calls it. `generators.manifestgen` and
`generators.reportgen` want one sentence per rule, and importing `describe`
used to pull in the whole validation stack, including the finding vocabulary a
generator has no business with. So the dependency here is the grammar's own
types and nothing else, and `test_condition_description.py` gates that by
importing this module in a fresh interpreter and reading back what got loaded.

BREAKING API MOVE (#168): the canonical import is now
`dbml_sharepoint.analysis.condition_description.describe`, not
`dbml_sharepoint.analysis.conditions.describe`. There is deliberately no
compatibility re-export: this package gives each public name one importable
home, and keeping the old path would recreate the shim the architecture work
is removing.

`VALUELESS_OPS` comes from `model.conditions` rather than being restated here.
A private copy would agree with the renderers' copy right up until somebody
edited one of them, and the disagreement would show as a manifest line printing
`None` after an operator that never had a value.

### `describe`

```python
def describe(node: Condition) -> str
```

A human-readable summary for manifests and documentation.

Deliberately not any target's syntax: an operator reads as its declared
name, so an operator a reader does not recognise sends them to the
grammar reference rather than to a SharePoint dialect they would then
have to identify.

