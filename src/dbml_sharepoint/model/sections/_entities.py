# src/dbml_sharepoint/model/sections/_entities.py
"""`entities`, the one required section: which lists a mapping deploys."""

import re
from typing import Any, cast

from dbml_sharepoint.analysis.file_names import invalid_file_name_reason
from dbml_sharepoint.analysis.limits import MAX_DISPLAY_TITLE
from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.mapping_types import (
    ENTITY_KINDS,
    EntityKind,
    EntityMapping,
    FoldersFromEnum,
    FolderSource,
)
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
    "folders", "title", "internal_name",
})

_FOLDER_SOURCE_KEYS = frozenset({"from_enum"})


def read(sc: SectionContext) -> dict[str, Any]:
    entities: dict[str, EntityMapping] = {}
    for name, spec in _require_mapping(
        sc.required("entities"), "entities", allow_absent=False,
    ).items():
        _reject_unknown_keys(spec, _ENTITY_KEYS, f"entities.{name}")
        raw_kind: object = spec.get("kind")
        entities[name] = EntityMapping(
            name=name,
            title=optional_str(spec, "title", f"entities.{name}", record_blank=True),
            internal_name=_internal_name(spec, name),
            kind=_parse_entity_kind(raw_kind, f"entities.{name}"),
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
            # Shape only here; the rest is the validator's.
            folder_source=_folder_source(spec, f"entities.{name}"),
        )
    titles: set[tuple[str, str]] = set()
    roots: set[tuple[str, str]] = set()
    for entity in entities.values():
        title = entity.title or str(sc.loaded.get("prefix", "")) + entity.name
        if (not title.strip() or title != title.strip() or title in {".", ".."}
                or any(c in title for c in "/\\") or re.search(r"[\x00-\x1f]", title)):
            raise MappingValueError(f"entities.{entity.name}.title is not a safe list title")
        if len(title) > MAX_DISPLAY_TITLE:
            raise MappingValueError(
                f"entities.{entity.name}.title must be at most {MAX_DISPLAY_TITLE} characters",
            )
        if entity.internal_name and (entity.renamed_from or sc.loaded.get("previous_prefixes")):
            raise MappingValueError(
                f"entities.{entity.name}: internal_name cannot be combined with "
                "renamed_from or previous_prefixes; "
                "omit internal_name to retain an existing library root during retitling",
            )
        key = (entity.site_role, title.casefold())
        if key in titles:
            raise MappingValueError(f"entities: duplicate deployed title {title!r}")
        titles.add(key)
        # Simple title-derived roots are used by the shipped library fixtures.
        root = entity.internal_name or (
            title if entity.is_library and re.fullmatch(r"[A-Za-z0-9_]+", title) else None
        )
        if root:
            key = (entity.site_role, root.casefold())
            if key in roots:
                raise MappingValueError(
                    f"entities: duplicate library root {root!r}",
                )
            roots.add(key)
    return {"entities": entities}


def _parse_entity_kind(raw_kind: Any, context: str) -> EntityKind:
    """The one admission gate for entity kinds: a typo'd kind must fail the
    build here, not flow into schema_json and silently miss downstream
    comparisons like kind == "DocumentLibrary".

    An absent kind is the shape error the hierarchy names for a required key
    with no value, rather than a word this vocabulary declines.
    """
    if raw_kind is None:
        raise MappingShapeError(
            f"{context}.kind is required, one of "
            f"{', '.join(sorted(ENTITY_KINDS))}",
        )
    # isinstance first: a list or mapping is unhashable, so the membership
    # test below raises the TypeError the CLI deliberately does not catch.
    if not isinstance(raw_kind, str):
        raise MappingShapeError(f"{context}.kind must be a string, got {raw_kind!r}")
    if raw_kind not in ENTITY_KINDS:
        raise MappingValueError(
            f"{context}.kind must be one of "
            f"{', '.join(sorted(ENTITY_KINDS))}; got {raw_kind!r}",
        )
    return cast("EntityKind", raw_kind)


def _folder_source(spec: dict[str, Any], context: str) -> FolderSource:
    """`folders` as a list of names, or as `{from_enum: <enum>}`.

    Both spellings are accepted at the same key rather than at two, so an
    entity cannot declare folders twice over and leave the loader to pick.
    Which enums exist is the validator's question: this family never sees
    the schema.
    """
    value = spec.get("folders")
    if not isinstance(value, dict):
        return optional_str_list(spec, "folders", context)
    _reject_unknown_keys(value, _FOLDER_SOURCE_KEYS, f"{context}.folders")
    return FoldersFromEnum(enum=require_str(value, "from_enum", f"{context}.folders"))


def _internal_name(spec: dict[str, Any], name: str) -> str | None:
    value = optional_str(spec, "internal_name", f"entities.{name}")
    if value is not None:
        reason = invalid_file_name_reason(value)
        if spec.get("kind") != "DocumentLibrary":
            reason = "internal_name is only supported on a document library"
        elif value in {".", ".."} or any(c < " " or c == "\x7f" for c in value):
            reason = "use a decoded folder name without traversal or control characters"
        if reason:
            raise MappingValueError(f"entities.{name}.internal_name: {reason}")
    return value
