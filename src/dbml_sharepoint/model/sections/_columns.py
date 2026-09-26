# src/dbml_sharepoint/model/sections/_columns.py
"""Column-level declarations: `cross_site_reference_columns`,
`polymorphic_patterns`, `watched_lists`, `lookup_projections` and
`calculated_formulas`.

Each names a column and says how it deploys. Shape only: whether the entity
and the column exist is the validator's question.
"""

from typing import Any

from dbml_sharepoint.model._keys import _known_keys, _require_list, _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_types import CrossSiteRef, PolymorphicPattern, WatchedList
from dbml_sharepoint.model.reading import require_str
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    # `_require_list` for all three lists, where `or []` read `watched_lists: ''` as none.
    cross_site = []
    for i, item in enumerate(_require_list(
        sc.block("cross_site_reference_columns"), "cross_site_reference_columns",
    )):
        where = f"cross_site_reference_columns[{i}]"
        entry = _known_keys(item, {"entity", "column"}, where)
        cross_site.append(CrossSiteRef(
            entity=require_str(entry, "entity", where),
            column=require_str(entry, "column", where),
        ))

    polymorphic = []
    for i, item in enumerate(_require_list(
        sc.block("polymorphic_patterns"), "polymorphic_patterns",
    )):
        where = f"polymorphic_patterns[{i}]"
        entry = _known_keys(item, {"list", "field", "discriminator"}, where)
        polymorphic.append(PolymorphicPattern(
            list=require_str(entry, "list", where),
            field=require_str(entry, "field", where),
            discriminator=require_str(entry, "discriminator", where),
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
    for i, item in enumerate(_require_list(sc.block("watched_lists"), "watched_lists")):
        where = f"watched_lists[{i}]"
        entry = _known_keys(item, {"entity", "column"}, where)
        watched.append(WatchedList(
            entity=require_str(entry, "entity", where),
            column=require_str(entry, "column", where),
        ))

    calculated_formulas: dict[str, dict[str, str]] = {}
    for entity, cols in _require_mapping(
        sc.block("calculated_formulas"), "calculated_formulas",
    ).items():
        formulas = _require_mapping(cols, f"calculated_formulas.{entity}")
        # `require_str`, where `str()` deployed a blank formula as the text "None".
        calculated_formulas[entity] = {
            col: require_str(formulas, col, f"calculated_formulas.{entity}") for col in formulas
        }

    return {
        "cross_site_reference_columns": cross_site,
        "polymorphic_patterns": polymorphic,
        "lookup_projections": lookup_projections,
        "watched_lists": watched,
        "calculated_formulas": calculated_formulas,
    }
