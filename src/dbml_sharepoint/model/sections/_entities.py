# src/dbml_sharepoint/model/sections/_entities.py
"""`entities`, the one required section: which lists a mapping deploys."""

from typing import Any, cast

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.mapping_types import ENTITY_KINDS, EntityKind, EntityMapping
from dbml_sharepoint.model.reading import (
    optional_bool,
    optional_str,
    optional_str_list,
    require_int,
    require_str,
)
from dbml_sharepoint.model.sections.context import SectionContext

_ENTITY_KEYS = frozenset({
    "kind", "base_template", "site_role", "singleton", "display_column",
    "accept_unindexable_display_column", "hide_from_all_items", "renamed_from",
})


def read(sc: SectionContext) -> dict[str, Any]:
    entities: dict[str, EntityMapping] = {}
    for name, spec in _require_mapping(
        sc.required("entities"), "entities", allow_absent=False,
    ).items():
        _reject_unknown_keys(spec, _ENTITY_KEYS, f"entities.{name}")
        entities[name] = EntityMapping(
            name=name,
            kind=_parse_entity_kind(spec.get("kind"), f"entities.{name}"),
            base_template=require_int(spec, "base_template", f"entities.{name}"),
            site_role=require_str(spec, "site_role", f"entities.{name}"),
            singleton=optional_bool(spec, "singleton", f"entities.{name}"),
            display_column=optional_str(
                spec, "display_column", f"entities.{name}",
            ),
            accept_unindexable_display_column=optional_bool(
                spec, "accept_unindexable_display_column", f"entities.{name}",
            ),
            hide_from_all_items=optional_str_list(
                spec, "hide_from_all_items", f"entities.{name}",
            ),
            renamed_from=optional_str_list(
                spec, "renamed_from", f"entities.{name}",
            ),
        )
    return {"entities": entities}


def _parse_entity_kind(raw_kind: Any, context: str) -> EntityKind:
    """The one admission gate for entity kinds: a typo'd kind must fail the
    build here, not flow into schema_json and silently miss downstream
    comparisons like kind == "DocumentLibrary"."""
    if raw_kind not in ENTITY_KINDS:
        raise ValueError(
            f"{context}.kind must be one of "
            f"{', '.join(sorted(ENTITY_KINDS))}; got {raw_kind!r}",
        )
    return cast("EntityKind", raw_kind)
