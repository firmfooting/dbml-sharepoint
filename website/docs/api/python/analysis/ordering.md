---
title: ordering
sidebar_position: 7
---

# `dbml_sharepoint.analysis.ordering`

*dependency ordering and site filtering*

Two-pass dependency resolution.

Phase 2.1: create lists in topological order, with non-lookup columns and as
many lookup columns as can be resolved (target already created).

Phase 2.2: add the remaining lookup columns — self-references and any side
of a strongly connected component.

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

### `site_tables_in_order`

```python
def site_tables_in_order(schema: dbml_sharepoint.model.parser.Schema, entities: 'dict[str, EntityMapping]', site_role: str) -> list[str]
```

Dependency-ordered table names deployed for this site role.

The one role filter for jsgen, rollbackgen, demogen and assessgen.
Callers pass ``bundle.mapping.entities``; ordering stays parser-pure.

