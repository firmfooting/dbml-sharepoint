# src/dbml_sharepoint/analysis/ordering.py
"""Two-pass dependency resolution.

Phase 2.1: create lists in topological order, with non-lookup columns and as
many lookup columns as can be resolved (target already created).

Phase 2.2: add the remaining lookup columns — self-references and any side
of a strongly connected component.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from dbml_sharepoint.model.parser import Schema

if TYPE_CHECKING:
    from dbml_sharepoint.model.mapping_loader import EntityMapping


@dataclass
class DeployPlan:
    list_creation_order: list[str] = field(default_factory=list)
    phase2_lookups: list[tuple[str, str]] = field(default_factory=list)


def compute_phases(schema: Schema) -> DeployPlan:
    table_names = [t.name for t in schema.tables]
    edges: dict[str, set[str]] = defaultdict(set)
    self_refs: set[tuple[str, str]] = set()

    by_name = {t.name: t for t in schema.tables}

    for table in schema.tables:
        for col in table.columns:
            if col.ref is None:
                continue
            target = col.ref.target_table
            if target == table.name:
                self_refs.add((table.name, col.name))
                continue
            if target in by_name:
                edges[table.name].add(target)

    order = _topological(table_names, edges)
    deferred = list(self_refs)

    # For any cycle (Tarjan-style or unresolvable), defer one side's lookups.
    placed: set[str] = set()
    final_order: list[str] = []
    for name in order:
        final_order.append(name)
        placed.add(name)

    # Identify edges that still cross from earlier-placed src to later-placed
    # dst — these are circular-dependency lookups that must be deferred to
    # phase 2. Defer EVERY column from src that points at dst, not just the
    # first one — otherwise a table with multiple lookups to the same later
    # table will fail at deploy time on the second-and-later column.
    for src in table_names:
        for dst in edges[src]:
            if final_order.index(src) < final_order.index(dst):
                for col in by_name[src].columns:
                    if col.ref is not None and col.ref.target_table == dst:
                        deferred.append((src, col.name))

    plan = DeployPlan()
    plan.list_creation_order = final_order
    plan.phase2_lookups = deferred
    return plan


def _topological(nodes: list[str], edges: dict[str, set[str]]) -> list[str]:
    """Tolerant topological sort: cycles are broken by visit order; cyclic
    members appear in some order, and the caller defers offending lookups
    to phase 2."""
    visited: dict[str, int] = {}  # 0=visiting, 1=done
    order: list[str] = []

    def visit(node: str) -> None:
        state = visited.get(node)
        if state == 1:
            return
        if state == 0:
            return  # cycle: leave for phase 2
        visited[node] = 0
        for nxt in sorted(edges.get(node, ())):
            visit(nxt)
        visited[node] = 1
        order.append(node)

    for n in nodes:
        visit(n)
    return order


def site_tables_in_order(
    schema: Schema,
    entities: "dict[str, EntityMapping]",
    site_role: str,
) -> list[str]:
    """Dependency-ordered table names deployed for this site role.

    The one role filter for jsgen, rollbackgen, demogen and assessgen.
    Callers pass ``bundle.mapping.entities``; ordering stays parser-pure."""
    return [
        name
        for name in compute_phases(schema).list_creation_order
        if name in entities and entities[name].site_role == site_role
    ]
