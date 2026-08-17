---
title: ordering
sidebar_position: 12
---

# `dbml_sharepoint.analysis.ordering`

*dependency ordering and site filtering*

Two-pass dependency resolution.

Phase 2.1: create lists in topological order, with non-lookup columns and as
many lookup columns as can be resolved (target already created).

Phase 2.2: add the remaining lookup columns (self-references and any side
of a strongly connected component).

### `DeployPlan`

```python
@dataclass
class DeployPlan:
    list_creation_order: list[str] = field(default_factory=list)
    phase2_lookups: list[tuple[str, str]] = field(default_factory=list)
```

DeployPlan(list_creation_order: list[str] = &lt;factory>, phase2_lookups: list[tuple[str, str]] = &lt;factory>)

### `compute_phases`

```python
def compute_phases(schema: dbml_sharepoint.model.parser.Schema) -> dbml_sharepoint.analysis.ordering.DeployPlan
```

### `is_deployed_here`

```python
def is_deployed_here(entities: 'dict[str, EntityMapping]', name: str, site_role: str) -> bool
```

Is this entity provisioned at a site of this role?

THE role predicate, for every consumer. Two things make an entity absent
from a site: no mapping entry at all, and a mapping entry belonging to a
different role. Both must be excluded, and a caller that checks only the
second raises `KeyError` on the first.

`site_tables_in_order` below applies it in dependency order for the
generators that DEPLOY. `generators.reportgen` applies it in declaration
order, because a report has no creation sequence to respect. The
ordering legitimately differs and the membership question does not, which
is why the predicate is factored out and the ordering is not.

reportgen used to open-code this, and said so in its own docstring
("same filter as jsgen"). A comment claiming two implementations agree is
the shape this repository keeps finding to be false.

### `site_tables_in_order`

```python
def site_tables_in_order(schema: dbml_sharepoint.model.parser.Schema, entities: 'dict[str, EntityMapping]', site_role: str) -> list[str]
```

Dependency-ordered table names deployed for this site role.

The one role filter for jsgen, rollbackgen, demogen and assessgen.
Callers pass ``bundle.mapping.entities``; ordering stays parser-pure.

