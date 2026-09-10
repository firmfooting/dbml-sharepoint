# src/dbml_sharepoint/model/sections/_permissions.py
"""`groups`, `permission_levels` and `list_permissions`.

Declared as three top-level sections, not one nested `permissions:` block.
Group and level names take the `{prefix}` placeholder, which is why this
family reads what identity produced: it runs after identity, by registry
order, and expands every name under the current prefix and each previous
one.
"""

from typing import Any, cast

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.mapping_types import (
    PRINCIPAL_KIND_LIST,
    PRINCIPAL_KINDS,
    CustomPermissionLevel,
    ListPermissionPolicy,
    PermissionsConfig,
    Principal,
    PrincipalKind,
    ReconcileMode,
    RoleAssignment,
    SiteGroup,
)
from dbml_sharepoint.model.prefix import expand_prefix, previous_object_names
from dbml_sharepoint.model.reading import optional_bool, optional_str_list, strict_bool
from dbml_sharepoint.model.sections.context import SectionContext

_GROUP_KEYS = frozenset({
    "name", "description", "owner_group", "allow_members_edit_membership",
    "allow_request_to_join_leave", "auto_accept_request_to_join_leave",
    "only_allow_members_view_membership", "require_empty_at_deploy",
    "enroll_operator_during_deploy", "enroll_enterprise_reader", "renamed_from",
})
# `site_role` scopes the DEFAULT policy (which entities it applies to) and
# is read only there. On an override it was parsed and silently discarded,
# so an author who had seen it work on the default reasonably expected it to
# narrow an override too and got a list that was not scoped at all. Rejected
# rather than implemented: an override is already keyed BY entity, so a
# site-role scope on one is either redundant or contradicts its own key.
_POLICY_KEYS = frozenset({"break_inheritance", "reconcile", "assignments"})
_DEFAULT_POLICY_KEYS = _POLICY_KEYS | {"site_role"}


def read(sc: SectionContext) -> dict[str, Any]:
    prefix = sc.loaded["prefix"]
    previous_prefixes = sc.loaded["previous_prefixes"]

    # All three sections are optional; default to empty / no default policy.
    raw_levels = sc.block("permission_levels", [])
    raw_groups = sc.block("groups", [])
    raw_list_perms = _require_mapping(sc.block("list_permissions"), "list_permissions")
    _reject_unknown_keys(raw_list_perms, {"default", "overrides"}, "list_permissions")

    for i, lvl in enumerate(raw_levels):
        _reject_unknown_keys(
            lvl, {"name", "description", "base_permissions", "renamed_from"},
            f"permission_levels[{i}]",
        )
    for i, grp in enumerate(raw_groups):
        _reject_unknown_keys(grp, _GROUP_KEYS, f"groups[{i}]")

    levels = [
        CustomPermissionLevel(
            name=expand_prefix(lvl["name"], prefix, f"permission_levels[{i}].name"),
            description=lvl.get("description", ""),
            base_permissions=list(lvl.get("base_permissions", [])),
            renamed_from=optional_str_list(lvl, "renamed_from", f"permission_levels[{i}]"),
            previous_names=previous_object_names(
                lvl["name"], optional_str_list(lvl, "renamed_from", f"permission_levels[{i}]"),
                prefix, previous_prefixes, f"permission_levels[{i}].renamed_from",
            ),
        )
        for i, lvl in enumerate(raw_levels)
    ]

    groups = [
        SiteGroup(
            name=expand_prefix(grp["name"], prefix, f"groups[{i}].name"),
            description=grp.get("description", ""),
            owner_group=expand_prefix(
                grp.get("owner_group", "Site Owners"), prefix, f"groups[{i}].owner_group",
            ),
            allow_members_edit_membership=optional_bool(
                grp, "allow_members_edit_membership", f"groups[{i}]",
            ),
            allow_request_to_join_leave=optional_bool(
                grp, "allow_request_to_join_leave", f"groups[{i}]",
            ),
            auto_accept_request_to_join_leave=optional_bool(
                grp, "auto_accept_request_to_join_leave", f"groups[{i}]",
            ),
            only_allow_members_view_membership=optional_bool(
                grp, "only_allow_members_view_membership", f"groups[{i}]",
            ),
            require_empty_at_deploy=optional_bool(
                grp, "require_empty_at_deploy", f"groups[{i}]",
            ),
            enroll_operator_during_deploy=optional_bool(
                grp, "enroll_operator_during_deploy", f"groups[{i}]",
            ),
            enroll_enterprise_reader=optional_bool(
                grp, "enroll_enterprise_reader", f"groups[{i}]",
            ),
            renamed_from=optional_str_list(grp, "renamed_from", f"groups[{i}]"),
            previous_names=previous_object_names(
                grp["name"], optional_str_list(grp, "renamed_from", f"groups[{i}]"),
                prefix, previous_prefixes, f"groups[{i}].renamed_from",
            ),
        )
        for i, grp in enumerate(raw_groups)
    ]

    default_policy: ListPermissionPolicy | None = None
    default_policy_site_role: str | None = None
    raw_default = raw_list_perms.get("default")
    if raw_default is not None:
        default_policy = _parse_policy(
            raw_default, "list_permissions.default", allow_site_role=True, prefix=prefix,
        )
        raw_scope = raw_default.get("site_role")
        default_policy_site_role = str(raw_scope) if raw_scope is not None else None

    overrides: dict[str, ListPermissionPolicy] = {}
    for entity_name, raw_policy in _require_mapping(
        raw_list_perms.get("overrides"), "list_permissions.overrides",
    ).items():
        ctx = f"list_permissions.overrides.{entity_name}"
        overrides[entity_name] = _parse_policy(raw_policy, ctx, prefix=prefix)

    return {
        "permissions": PermissionsConfig(
            levels=levels,
            groups=groups,
            default_policy=default_policy,
            overrides=overrides,
            default_policy_site_role=default_policy_site_role,
        ),
    }


def _parse_principal(raw_principal: Any, context: str, prefix: str = "") -> Principal:
    """Parse a principal dict into a Principal dataclass.

    The admission gate reads `PRINCIPAL_KINDS`, derived from the
    `PrincipalKind` Literal, and the message reads the same set. Both used to
    be typed out here -- the set once and the four names again as error text
    -- so a fifth kind would have type-checked and then been refused at load,
    by a message still naming four.
    """
    if not isinstance(raw_principal, dict):
        raise ValueError(
            f"{context}: principal must be a mapping, "
            f"got {type(raw_principal).__name__}",
        )
    _reject_unknown_keys(raw_principal, {"kind", "name"}, context)
    kind = raw_principal.get("kind")
    if kind not in PRINCIPAL_KINDS:
        raise ValueError(
            f"{context}: principal kind must be one of "
            f"{PRINCIPAL_KIND_LIST}; got {kind!r}",
        )
    name = raw_principal.get("name")
    if isinstance(name, str):
        name = expand_prefix(name, prefix, f"{context}.name")
    if kind == "group" and not name:
        raise ValueError(f"{context}: principal kind=group requires a 'name'")
    return Principal(
        kind=cast("PrincipalKind", kind),
        name=name if kind == "group" else None,
    )


def _parse_policy(
    raw_policy: Any, context: str, *, allow_site_role: bool = False, prefix: str = "",
) -> ListPermissionPolicy:
    """Parse a list permission policy dict."""
    _reject_unknown_keys(
        raw_policy,
        _DEFAULT_POLICY_KEYS if allow_site_role else _POLICY_KEYS,
        context,
    )
    # Read STRICTLY, and before the reconcile guard below. bool("false") is
    # True, so a lenient read coerces the quoted spelling to True and the
    # guard then tests the coerced value, breaking inheritance the author
    # asked to keep.
    break_inheritance = strict_bool(raw_policy, "break_inheritance", context)
    reconcile_mode = cast("ReconcileMode", str(raw_policy.get("reconcile", "configured")))
    if reconcile_mode not in {"configured", "exact"}:
        raise ValueError(
            f"{context}.reconcile must be 'configured' or 'exact', "
            f"got {reconcile_mode!r}",
        )
    if reconcile_mode == "exact" and not break_inheritance:
        raise ValueError(
            f"{context}: reconcile 'exact' requires break_inheritance: true; "
            "an inherited ACL cannot be reconciled as a list-scoped allowlist",
        )
    assignments: list[RoleAssignment] = []
    for i, raw_a in enumerate(raw_policy.get("assignments", [])):
        _reject_unknown_keys(raw_a, {"principal", "level"}, f"{context}.assignments[{i}]")
        principal = _parse_principal(
            raw_a.get("principal", {}), f"{context}.assignments[{i}].principal", prefix,
        )
        level = raw_a.get("level")
        if isinstance(level, str):
            level = expand_prefix(level, prefix, f"{context}.assignments[{i}].level")
        if not level:
            raise ValueError(f"{context}.assignments[{i}]: 'level' is required")
        assignments.append(RoleAssignment(principal=principal, level=level))
    return ListPermissionPolicy(
        break_inheritance=break_inheritance,
        assignments=assignments,
        reconcile_mode=reconcile_mode,
    )
