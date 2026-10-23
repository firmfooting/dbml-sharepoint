# src/dbml_sharepoint/model/sections/_entities.py
"""`entities`, the one required section: which lists a mapping deploys."""

import re
from collections.abc import Mapping

from dbml_sharepoint.analysis.file_names import invalid_file_name_reason
from dbml_sharepoint.analysis.limits import MAX_DISPLAY_TITLE
from dbml_sharepoint.analysis.list_url import (
    implicit_list_root,
    list_url_key,
    list_url_path,
)
from dbml_sharepoint.model._keys import _known_keys, _require_mapping
from dbml_sharepoint.model.errors import (
    MappingShapeError,
    MappingValueError,
)
from dbml_sharepoint.model.mapping_types import (
    DRAFT_VISIBILITY_VALUES,
    ENTITY_KINDS,
    DraftVisibility,
    EntityKind,
    EntityMapping,
    FoldersFromEnum,
    FolderSource,
    LibrarySettings,
    is_draft_visibility,
    is_entity_kind,
)
from dbml_sharepoint.model.reading import (
    optional_bool,
    optional_str,
    optional_str_list,
    optional_value,
    require_int,
    require_str,
)
from dbml_sharepoint.model.sections.context import LoadedFields, SectionContext

_ENTITY_KEYS = frozenset({
    "kind", "base_template", "site_role", "singleton", "display_column",
    "accept_unindexable_display_column", "hide_from_all_items", "renamed_from",
    "folders", "title", "internal_name", "settings", "folder_defaults",
})

_FOLDER_SOURCE_KEYS = frozenset({"from_enum"})


def read(sc: SectionContext) -> LoadedFields:
    entities: dict[str, EntityMapping] = {}
    for name, raw_spec in _require_mapping(
        sc.required("entities"), "entities", allow_absent=False,
    ).items():
        spec = _known_keys(raw_spec, _ENTITY_KEYS, f"entities.{name}")
        entities[name] = EntityMapping(
            name=name,
            title=optional_str(spec, "title", f"entities.{name}", record_blank=True),
            internal_name=_internal_name(spec, name),
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
            # Shape only here; the rest is the validator's.
            folder_source=_folder_source(spec, f"entities.{name}"),
            settings=_library_settings(spec, f"entities.{name}"),
            folder_defaults=_folder_defaults(spec, f"entities.{name}"),
        )
    titles: set[tuple[str, str]] = set()
    roots: set[tuple[str, str]] = set()
    for entity in entities.values():
        title = entity.title or sc.loaded.get("prefix", "") + entity.name
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
        root = entity.internal_name or implicit_list_root(title, is_library=entity.is_library)
        if root:
            key = (entity.site_role, list_url_key(root))
            if key in roots:
                raise MappingValueError(
                    f"entities: duplicate list or library root {root!r}",
                )
            roots.add(key)
    return {"entities": entities}


def _parse_entity_kind(raw_kind: object, context: str) -> EntityKind:
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
    if not is_entity_kind(raw_kind):
        raise MappingValueError(
            f"{context}.kind must be one of "
            f"{', '.join(sorted(ENTITY_KINDS))}; got {raw_kind!r}",
        )
    return raw_kind


def _library_settings(spec: Mapping[str, object], context: str) -> LibrarySettings | None:
    """`settings`, a closed shape. Absent is None; a blank `require_checkout` is unmanaged."""
    if "settings" not in spec:
        return None
    where = f"{context}.settings"
    block = _known_keys(
        spec["settings"],
        {"require_checkout", "enable_folder_creation", "draft_version_visibility",
         "content_approval"}, where,
    )
    return LibrarySettings(
        require_checkout=_setting_bool(block, "require_checkout", where),
        enable_folder_creation=_setting_bool(block, "enable_folder_creation", where),
        draft_version_visibility=_draft_visibility(block, where),
        content_approval=_setting_bool(block, "content_approval", where),
    )


def _setting_bool(block: Mapping[str, object], key: str, where: str) -> bool | None:
    value = optional_value(block, key, where)
    if value is not None and not isinstance(value, bool):
        raise MappingShapeError(f"{where}.{key} must be a boolean, got {value!r}")
    return value


def _draft_visibility(block: Mapping[str, object], where: str) -> DraftVisibility | None:
    value = optional_value(block, "draft_version_visibility", where)
    if value is None:
        return None
    # isinstance first: an unhashable value would raise at the membership test.
    if not (isinstance(value, str) and is_draft_visibility(value)):
        raise MappingValueError(
            f"{where}.draft_version_visibility must be one of "
            f"{', '.join(DRAFT_VISIBILITY_VALUES)}; got {value!r}",
        )
    return value


def _folder_defaults(spec: Mapping[str, object], context: str) -> dict[str, dict[str, str]]:
    """`folder_defaults`: folder -> column -> value, every value held as text."""
    if "folder_defaults" not in spec:
        return {}
    where = f"{context}.folder_defaults"
    raw = _require_mapping(spec["folder_defaults"], where)
    out: dict[str, dict[str, str]] = {}
    for folder, columns in raw.items():
        if not isinstance(folder, str):
            raise MappingShapeError(f"{where} keys must be folder names, got {folder!r}")
        values: dict[str, str] = {}
        for column, value in _require_mapping(columns, f"{where}.{folder}").items():
            # bool is an int subclass; a YAML `yes` must not become "True".
            if not isinstance(column, str) or isinstance(value, bool) or not isinstance(
                value, str | int | float,
            ):
                raise MappingShapeError(
                    f"{where}.{folder}.{column} must be a text or number value, got {value!r}",
                )
            values[column] = str(value)
        out[folder] = values
    return out


def _folder_source(spec: Mapping[str, object], context: str) -> FolderSource:
    """`folders` as a list of names, or as `{from_enum: <enum>}`.

    Both spellings are accepted at the same key rather than at two, so an
    entity cannot declare folders twice over and leave the loader to pick.
    Which enums exist is the validator's question: this family never sees
    the schema.
    """
    value = spec.get("folders")
    if not isinstance(value, dict):
        return optional_str_list(spec, "folders", context)
    folders = _known_keys(value, _FOLDER_SOURCE_KEYS, f"{context}.folders")
    return FoldersFromEnum(enum=require_str(folders, "from_enum", f"{context}.folders"))


def _internal_name(spec: Mapping[str, object], name: str) -> str | None:
    value = optional_str(spec, "internal_name", f"entities.{name}")
    if value is not None:
        reason = None
        if spec.get("kind") == "DocumentLibrary":
            reason = invalid_file_name_reason(value)
            if value in {".", ".."} or any(c < " " or c == "\x7f" for c in value):
                reason = "use a decoded folder name without traversal or control characters"
        else:
            try:
                value = list_url_path(value)
            except ValueError as exc:
                reason = str(exc)
        if reason:
            raise MappingValueError(f"entities.{name}.internal_name: {reason}")
    return value
