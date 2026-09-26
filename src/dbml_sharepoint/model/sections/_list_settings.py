# src/dbml_sharepoint/model/sections/_list_settings.py
"""`versioning`, `item_security`, `seal_columns`, `prevent_list_deletion`
and `attachments`: how every deployed list behaves.

The first two take a default and per-entity overrides; the three flags
apply to every list the mapping deploys.
"""

from typing import Any

from dbml_sharepoint.model._keys import _known_keys, _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.mapping_types import ITEM_SECURITY_SCOPES, ItemSecurity, Versioning
from dbml_sharepoint.model.reading import drop_blank_keys, optional_bool, strict_bool
from dbml_sharepoint.model.sections.context import SectionContext

_VERSIONING_KEYS = frozenset({
    "enable_versioning", "major_version_limit", "enable_minor_versions",
})
_ITEM_SECURITY_KEYS = frozenset({"read", "write"})


def read(sc: SectionContext) -> dict[str, Any]:
    versioning = _require_mapping(sc.block("versioning"), "versioning")
    _reject_unknown_keys(versioning, {"default", "overrides"}, "versioning")
    default_v = _versioning_values(
        _require_mapping(versioning.get("default"), "versioning.default"),
        "versioning.default", Versioning(),
    )
    # Every absent-key fallback is `Versioning`'s own field default, named
    # rather than typed out again. The 500 in particular was restated in
    # `test/_model.py` as well, which is how a default ends up with three
    # homes and no way to tell which one is authoritative.
    versioning_default = Versioning(
        enable_versioning=strict_bool(
            default_v, "enable_versioning", "versioning.default",
            default=Versioning.enable_versioning,
        ),
        major_version_limit=int(default_v.get(
            "major_version_limit", Versioning.major_version_limit,
        )),
        enable_minor_versions=optional_bool(
            default_v, "enable_minor_versions", "versioning.default",
            default=Versioning.enable_minor_versions,
        ),
    )
    # Overrides reach the generators as a RAW dict and are read there with
    # bool()/int(), so their values are checked here and nowhere else.
    #
    # NORMALISED TO `{}` ON THE WAY IN, which is the whole reason this builds
    # a dict rather than storing `versioning.overrides` verbatim. YAML parses
    # a bare `Project:` with nothing under it as `None`, and the value-check
    # below already tolerated that with `override or {}` -- so a null override
    # was ACCEPTED and then stored as `None`. Every reader does
    # `overrides.get(entity, {})`, which returns the stored `None` rather than
    # the default, and the next `.get` on it raises AttributeError in the
    # middle of generating a deploy script. An empty override block means "no
    # overrides for this entity", so say that once, here, instead of leaving
    # each reader to survive a shape the loader let through.
    versioning_overrides: dict[str, dict[str, Any]] = {}
    for override_entity, override in _require_mapping(
        versioning.get("overrides"), "versioning.overrides",
    ).items():
        context = f"versioning.overrides.{override_entity}"
        versioning_overrides[override_entity] = _versioning_values(
            override or {}, context, versioning_default,
        )

    # Item-level trimming, same default/overrides shape as versioning and the
    # same reason for normalising a null override to `{}`.
    item_security = _require_mapping(sc.block("item_security"), "item_security")
    _reject_unknown_keys(item_security, {"default", "overrides"}, "item_security")
    default_is = _item_security_values(
        _require_mapping(item_security.get("default"), "item_security.default"),
        "item_security.default", ItemSecurity(),
    )
    item_security_default = ItemSecurity(
        read=str(default_is.get("read", ItemSecurity.read)),
        write=str(default_is.get("write", ItemSecurity.write)),
    )
    item_security_overrides: dict[str, dict[str, Any]] = {}
    for override_entity, override in _require_mapping(
        item_security.get("overrides"), "item_security.overrides",
    ).items():
        context = f"item_security.overrides.{override_entity}"
        item_security_overrides[override_entity] = _item_security_values(
            override or {}, context, item_security_default,
        )

    return {
        "versioning_default": versioning_default,
        "versioning_overrides": versioning_overrides,
        "item_security_default": item_security_default,
        "item_security_overrides": item_security_overrides,
        "seal_columns": optional_bool(sc.blocks, "seal_columns", "mapping"),
        "prevent_list_deletion": optional_bool(sc.blocks, "prevent_list_deletion", "mapping"),
        # True is SharePoint's default, so the absent key and `attachments:
        # true` both mean "write nothing".
        "attachments": optional_bool(sc.blocks, "attachments", "mapping", default=True),
    }


def _versioning_values(block: Any, context: str, fallback: Versioning) -> dict[str, Any]:
    """Type-check one versioning block (default or override), without its blanks.

    A blank key takes `fallback`'s value: the dataclass default for
    `versioning.default`, and the resolved default for an override.
    """
    declared = drop_blank_keys(_known_keys(block, _VERSIONING_KEYS, context), context, {
        "enable_versioning": fallback.enable_versioning,
        "major_version_limit": fallback.major_version_limit,
        "enable_minor_versions": fallback.enable_minor_versions,
    })
    for key in ("enable_versioning", "enable_minor_versions"):
        if key in declared and not isinstance(declared[key], bool):
            raise MappingShapeError(
                f"{context}.{key}: expected true or false, got {declared[key]!r}",
            )
    limit = declared.get("major_version_limit")
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int)):
        raise MappingShapeError(
            f"{context}.major_version_limit: expected an integer, got {limit!r}",
        )
    return declared


def _item_security_values(
    block: Any, context: str, fallback: ItemSecurity,
) -> dict[str, Any]:
    """Type-check one item_security block (default or override), without its blanks.

    The values are refused rather than coerced: `read: created_by` is exactly
    the spelling somebody reaches for, and silently reading it as `all` would
    ship a list whose rows are visible to everyone while the mapping says
    otherwise. That is the failure class this repository exists to close.
    A blank key takes `fallback`'s value, as `_versioning_values` says.
    """
    declared = drop_blank_keys(_known_keys(block, _ITEM_SECURITY_KEYS, context), context, {
        "read": fallback.read, "write": fallback.write,
    })
    for key in ("read", "write"):
        if key not in declared:
            continue
        value = declared[key]
        # The shape before the word, as `scope` and `totals` do: a list is
        # unhashable, and `read: 2` is a type rather than a scope declined.
        if not isinstance(value, str):
            raise MappingShapeError(
                f"{context}.{key}: expected a string, got {value!r}",
            )
        if value not in ITEM_SECURITY_SCOPES:
            raise MappingValueError(
                f"{context}.{key}: expected one of "
                f"{', '.join(sorted(ITEM_SECURITY_SCOPES))}, got {value!r}",
            )
    return declared
