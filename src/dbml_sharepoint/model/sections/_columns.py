# src/dbml_sharepoint/model/sections/_columns.py
"""Column-level declarations: `cross_site_reference_columns`,
`polymorphic_patterns`, `watched_lists`, `lookup_projections` and
`calculated_formulas`.

Each names a column and says how it deploys. Shape only: whether the entity
and the column exist is the validator's question.
"""

from typing import Any

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_types import CrossSiteRef, PolymorphicPattern, WatchedList
from dbml_sharepoint.model.reading import require_str
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    cross_site = []
    for i, item in enumerate(sc.block("cross_site_reference_columns") or []):
        where = f"cross_site_reference_columns[{i}]"
        _reject_unknown_keys(item, {"entity", "column"}, where)
        cross_site.append(CrossSiteRef(
            entity=require_str(item, "entity", where),
            column=require_str(item, "column", where),
        ))

    polymorphic = []
    for i, item in enumerate(sc.block("polymorphic_patterns") or []):
        where = f"polymorphic_patterns[{i}]"
        _reject_unknown_keys(item, {"list", "field", "discriminator"}, where)
        polymorphic.append(PolymorphicPattern(
            list=require_str(item, "list", where),
            field=require_str(item, "field", where),
            discriminator=require_str(item, "discriminator", where),
        ))

    lookup_projections: dict[str, dict[str, list[str]]] = {}
    for entity, cols in _require_mapping(
        sc.block("lookup_projections"), "lookup_projections",
    ).items():
        entity_proj: dict[str, list[str]] = {}
        for column, targets in _require_mapping(
            cols, f"lookup_projections.{entity}",
        ).items():
            if not isinstance(targets, list) or not all(
                isinstance(t, str) for t in targets
            ):
                raise MappingShapeError(
                    f"lookup_projections.{entity}.{column} must be a list of "
                    f"strings, got {targets!r}",
                )
            entity_proj[column] = list(targets)
        lookup_projections[entity] = entity_proj

    watched = []
    for i, item in enumerate(sc.block("watched_lists") or []):
        where = f"watched_lists[{i}]"
        _reject_unknown_keys(item, {"entity", "column"}, where)
        watched.append(WatchedList(
            entity=require_str(item, "entity", where),
            column=require_str(item, "column", where),
        ))

    calculated_formulas = {
        entity: {
            col: str(formula)
            for col, formula in _require_mapping(
                cols, f"calculated_formulas.{entity}",
            ).items()
        }
        for entity, cols in _require_mapping(
            sc.block("calculated_formulas"), "calculated_formulas",
        ).items()
    }

    return {
        "cross_site_reference_columns": cross_site,
        "polymorphic_patterns": polymorphic,
        "lookup_projections": lookup_projections,
        "watched_lists": watched,
        "calculated_formulas": calculated_formulas,
    }
