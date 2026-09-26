# src/dbml_sharepoint/model/sections/_permissions.py
"""`groups`, `permission_levels` and `list_permissions`.

Declared as three top-level sections, not one nested `permissions:` block.
Group and level names take the `{prefix}` placeholder, which is why this
family reads what identity produced: it runs after identity, by registry
order, and expands every name under the current prefix and each previous
one.
"""

from collections.abc import Sequence
from typing import Any, cast

from dbml_sharepoint.model._keys import (
    _known_keys,
    _reject_unknown_keys,
    _require_list,
    _require_mapping,
)
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.mapping_types import (
    PRINCIPAL_KIND_LIST,
    PRINCIPAL_KINDS,
    CustomPermissionLevel,
    GroupsFromEnum,
    ListPermissionPolicy,
    PermissionsConfig,
    Principal,
    PrincipalKind,
    ReconcileMode,
    RoleAssignment,
    SiteGroup,
)
from dbml_sharepoint.model.prefix import (
    MEMBER_PLACEHOLDER,
    MEMBER_SAFE_PLACEHOLDER,
    expand_prefix,
    previous_object_names,
)
from dbml_sharepoint.model.reading import (
    optional_bool,
    optional_str,
    optional_str_list,
    optional_value,
    require_str,
    strict_bool,
    strict_str,
)
from dbml_sharepoint.model.sections.context import SectionContext

_GROUP_KEYS = frozenset({
    "name", "description", "owner_group", "allow_members_edit_membership",
    "allow_request_to_join_leave", "auto_accept_request_to_join_leave",
    "only_allow_members_view_membership", "require_empty_at_deploy",
    "enroll_operator_during_deploy", "enroll_enterprise_reader", "renamed_from",
    # `from_enum` turns one declaration into one group per enum member. At
    # the same key as the rest of the group, the way `entities.*.folders`
    # takes both spellings at one key, so a group cannot be declared twice
    # over and leave the loader to pick.
    "from_enum",
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
    raw_levels = _require_list(sc.block("permission_levels"), "permission_levels")
    raw_groups = _require_list(sc.block("groups"), "groups")
    raw_list_perms = _require_mapping(sc.block("list_permissions"), "list_permissions")
    _reject_unknown_keys(
        raw_list_perms, {"default", "overrides", "folders"}, "list_permissions",
    )

    level_blocks = [
        _known_keys(
            lvl, {"name", "description", "base_permissions", "renamed_from"},
            f"permission_levels[{i}]",
        )
        for i, lvl in enumerate(raw_levels)
    ]
    group_blocks = [
        _known_keys(grp, _GROUP_KEYS, f"groups[{i}]") for i, grp in enumerate(raw_groups)
    ]

    levels = [
        CustomPermissionLevel(
            name=expand_prefix(
                require_str(lvl, "name", f"permission_levels[{i}]"),
                prefix, f"permission_levels[{i}].name",
            ),
            description=optional_str(lvl, "description", f"permission_levels[{i}]") or "",
            # A bare string iterates character by character, and `null` was a
            # TypeError from `list(None)` that `CONFIG_ERRORS` does not catch.
            base_permissions=list(
                optional_str_list(lvl, "base_permissions", f"permission_levels[{i}]"),
            ),
            renamed_from=optional_str_list(lvl, "renamed_from", f"permission_levels[{i}]"),
            previous_names=previous_object_names(
                require_str(lvl, "name", f"permission_levels[{i}]"),
                optional_str_list(lvl, "renamed_from", f"permission_levels[{i}]"),
                prefix, previous_prefixes, f"permission_levels[{i}].renamed_from",
            ),
        )
        for i, lvl in enumerate(level_blocks)
    ]

    groups: list[SiteGroup] = []
    group_sources: list[GroupsFromEnum] = []
    for i, grp in enumerate(group_blocks):
        group = _parse_group(grp, f"groups[{i}]", prefix, previous_prefixes)
        # A blank `from_enum:` is a literal group, which the load records. A
        # `{member}` left in its name is still refused below.
        if optional_value(grp, "from_enum", f"groups[{i}]") is None:
            _reject_member_placeholders(group, f"groups[{i}]")
            groups.append(group)
            continue
        group_sources.append(GroupsFromEnum(
            enum=require_str(grp, "from_enum", f"groups[{i}]"), template=group,
            after=len(groups),
        ))

    default_policy: ListPermissionPolicy | None = None
    default_policy_site_role: str | None = None
    raw_default = raw_list_perms.get("default")
    if raw_default is not None:
        default_policy = _parse_policy(
            raw_default, "list_permissions.default", allow_site_role=True, prefix=prefix,
        )
        raw_scope: object = raw_default.get("site_role")
        default_policy_site_role = str(raw_scope) if raw_scope is not None else None

    overrides: dict[str, ListPermissionPolicy] = {}
    for entity_name, raw_policy in _require_mapping(
        raw_list_perms.get("overrides"), "list_permissions.overrides",
    ).items():
        ctx = f"list_permissions.overrides.{entity_name}"
        overrides[entity_name] = _parse_policy(raw_policy, ctx, prefix=prefix)

    # One policy per entity, applied to every folder that entity declares.
    # Not keyed by folder name on purpose: the folders are already declared
    # on the entity, so a second list here could disagree with the first.
    folder_policies: dict[str, ListPermissionPolicy] = {}
    for entity_name, raw_policy in _require_mapping(
        raw_list_perms.get("folders"), "list_permissions.folders",
    ).items():
        ctx = f"list_permissions.folders.{entity_name}"
        folder_policies[entity_name] = _parse_policy(raw_policy, ctx, prefix=prefix)

    return {
        "permissions": PermissionsConfig(
            levels=levels,
            groups=groups,
            default_policy=default_policy,
            overrides=overrides,
            default_policy_site_role=default_policy_site_role,
            group_sources=tuple(group_sources),
            folder_policies=folder_policies,
        ),
    }


def _reject_member_placeholders(group: SiteGroup, context: str) -> None:
    """A member placeholder on a group with no `from_enum` to expand it.

    Nothing downstream expands one, and a brace is not a character
    SharePoint refuses in a group name, so the deploy would create a group
    called `{member}` and read it back byte-identical. Only the fields
    `analysis.groups.group_for_member` expands are checked, because those
    are the only ones a `from_enum` would have changed.
    """
    fields: list[tuple[str, str]] = [
        ("name", group.name),
        ("description", group.description),
        ("owner_group", group.owner_group),
        *(
            (f"renamed_from[{i}]", name)
            for i, name in enumerate(group.renamed_from)
        ),
    ]
    for key, value in fields:
        for placeholder in (MEMBER_SAFE_PLACEHOLDER, MEMBER_PLACEHOLDER):
            if placeholder in value:
                raise MappingValueError(
                    f"{context}.{key}: {placeholder} is expanded only on a "
                    f"group declaring 'from_enum'; got {value!r}",
                )


def _parse_group(
    grp: dict[str, Any], context: str, prefix: str, previous_prefixes: Sequence[str],
) -> SiteGroup:
    """One `groups[i]` entry, whether it names itself or an enum.

    A `{member}` placeholder in the name or description is left alone here.
    The loader never sees the schema, so which members exist is
    `analysis/groups.py`'s answer, not this family's.
    """
    return SiteGroup(
        name=expand_prefix(
            require_str(grp, "name", context), prefix, f"{context}.name",
        ),
        description=optional_str(grp, "description", context) or "",
        # `strict_str`, so a blank takes the default rather than reaching `expand_prefix` as None.
        owner_group=expand_prefix(
            strict_str(grp, "owner_group", context, default="Site Owners"),
            prefix, f"{context}.owner_group",
        ),
        allow_members_edit_membership=optional_bool(
            grp, "allow_members_edit_membership", context,
        ),
        allow_request_to_join_leave=optional_bool(
            grp, "allow_request_to_join_leave", context,
        ),
        auto_accept_request_to_join_leave=optional_bool(
            grp, "auto_accept_request_to_join_leave", context,
        ),
        only_allow_members_view_membership=optional_bool(
            grp, "only_allow_members_view_membership", context,
        ),
        require_empty_at_deploy=optional_bool(grp, "require_empty_at_deploy", context),
        enroll_operator_during_deploy=optional_bool(
            grp, "enroll_operator_during_deploy", context,
        ),
        enroll_enterprise_reader=optional_bool(
            grp, "enroll_enterprise_reader", context,
        ),
        renamed_from=optional_str_list(grp, "renamed_from", context),
        previous_names=previous_object_names(
            require_str(grp, "name", context),
            optional_str_list(grp, "renamed_from", context),
            prefix, previous_prefixes, f"{context}.renamed_from",
        ),
    )


def _parse_principal(raw_principal: Any, context: str, prefix: str = "") -> Principal:
    """Parse a principal dict into a Principal dataclass.

    The admission gate reads `PRINCIPAL_KINDS`, derived from the
    `PrincipalKind` Literal, and the message reads the same set. Both used to
    be typed out here -- the set once and the four names again as error text
    -- so a fifth kind would have type-checked and then been refused at load,
    by a message still naming four.
    """
    if not isinstance(raw_principal, dict):
        raise MappingShapeError(
            f"{context}: principal must be a mapping, "
            f"got {type(raw_principal).__name__}",
        )
    _reject_unknown_keys(raw_principal, {"kind", "name"}, context)
    kind = raw_principal.get("kind")
    # An assignment with no principal reaches here as `{}`, so absent is a
    # required key missing rather than a word this vocabulary declines.
    if kind is None:
        raise MappingShapeError(
            f"{context}: principal 'kind' is required, one of "
            f"{PRINCIPAL_KIND_LIST}",
        )
    # isinstance first: a list or mapping is unhashable, so the membership
    # test below raises the TypeError the CLI deliberately does not catch.
    if not isinstance(kind, str):
        raise MappingShapeError(f"{context}: principal kind must be a string, got {kind!r}")
    if kind not in PRINCIPAL_KINDS:
        raise MappingValueError(
            f"{context}: principal kind must be one of "
            f"{PRINCIPAL_KIND_LIST}; got {kind!r}",
        )
    name = raw_principal.get("name")
    # A number or a list was carried through as the group name the deploy looks up.
    if name is not None and not isinstance(name, str):
        raise MappingShapeError(f"{context}: principal name must be a string, got {name!r}")
    if isinstance(name, str):
        name = expand_prefix(name, prefix, f"{context}.name")
    if kind == "group" and not name:
        raise MappingShapeError(f"{context}: principal kind=group requires a 'name'")
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
    # The shape before the word, as the other two vocabulary readers do, and
    # `strict_str` so a blank `reconcile:` is recorded: its default is the
    # mode that leaves an existing ACL alone.
    reconcile_mode = cast(
        "ReconcileMode",
        strict_str(raw_policy, "reconcile", context, default="configured"),
    )
    if reconcile_mode not in {"configured", "exact"}:
        raise MappingValueError(
            f"{context}.reconcile must be 'configured' or 'exact', "
            f"got {reconcile_mode!r}",
        )
    if reconcile_mode == "exact" and not break_inheritance:
        raise MappingShapeError(
            f"{context}: reconcile 'exact' requires break_inheritance: true; "
            "an inherited ACL cannot be reconciled as a list-scoped allowlist",
        )
    assignments: list[RoleAssignment] = []
    # A blank `assignments:` grants nothing, and is recorded because under
    # `reconcile: exact` an empty grant list strips every grant the list has.
    raw_assignments: object = optional_value(
        raw_policy, "assignments", context, default=list[object](),
    )
    if not isinstance(raw_assignments, list):
        raise MappingShapeError(
            f"{context}.assignments must be a list, got {raw_assignments!r}",
        )
    entries: list[object] = raw_assignments
    for i, raw_a in enumerate(entries):
        assignment = _known_keys(raw_a, {"principal", "level"}, f"{context}.assignments[{i}]")
        # A blank `principal:` is an absent one, refused the same way below.
        raw_principal = assignment.get("principal")
        principal = _parse_principal(
            {} if raw_principal is None else raw_principal,
            f"{context}.assignments[{i}].principal", prefix,
        )
        level = assignment.get("level")
        if level is not None and not isinstance(level, str):
            raise MappingShapeError(
                f"{context}.assignments[{i}].level must be a string, got {level!r}",
            )
        if isinstance(level, str):
            level = expand_prefix(level, prefix, f"{context}.assignments[{i}].level")
        if not level:
            raise MappingShapeError(f"{context}.assignments[{i}]: 'level' is required")
        assignments.append(RoleAssignment(principal=principal, level=level))
    return ListPermissionPolicy(
        break_inheritance=break_inheritance,
        assignments=assignments,
        reconcile_mode=reconcile_mode,
    )
