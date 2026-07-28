# src/dbml_sharepoint/analysis/checks/_permissions.py
"""Permission levels, groups, and per-list policies."""

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.permissions import BASE_PERMISSIONS, BUILT_IN_LEVELS
from dbml_sharepoint.analysis.validator import (
    _ASSOCIATED_GROUP_ALIASES,
    _BUILTIN_SP_GROUPS,
    Finding,
)
from dbml_sharepoint.model.mapping_loader import ListPermissionPolicy


def check(vc: ValidationContext) -> list[Finding]:
    bundle = vc.bundle
    table_names = vc.table_names
    findings: list[Finding] = []
    # === Permissions cross-checks (R4) ===
    if bundle.mapping.permissions is not None:
        perms = bundle.mapping.permissions

        # list_permissions.default.site_role, when declared, must be a known
        # site role — a typo would silently scope the default to nothing. The
        # valid roles are data-driven: those declared on the mapping's
        # entities, plus "default" (no hardcoded any labels you choose.
        scope = perms.default_policy_site_role
        known_roles = {e.site_role for e in bundle.mapping.entities.values()} | {"default"}
        if scope is not None and scope not in known_roles:
            findings.append(Finding(
                "error",
                f"list_permissions.default.site_role: unknown site role "
                f"{scope!r} (mapping declares: {', '.join(sorted(known_roles))}).",
            ))

        # permission_levels[*].name must be unique.
        seen_level_names: set[str] = set()
        for lvl in perms.levels:
            if lvl.name in seen_level_names:
                findings.append(Finding("error", f"permission_levels: duplicate name {lvl.name!r}"))
            seen_level_names.add(lvl.name)

        # permission_levels[*].base_permissions must be known bits.
        for lvl in perms.levels:
            for bit in lvl.base_permissions:
                if bit not in BASE_PERMISSIONS:
                    findings.append(Finding(
                        "error",
                        f"permission_levels[{lvl.name!r}]: unknown base permission {bit!r}",
                    ))

        # groups[*].name must be unique.
        seen_group_names: set[str] = set()
        custom_group_names = {g.name for g in perms.groups}
        for grp in perms.groups:
            if grp.name in seen_group_names:
                findings.append(Finding("error", f"groups: duplicate name {grp.name!r}"))
            seen_group_names.add(grp.name)

        # groups[*].owner_group must be a built-in SP group or a declared custom group.
        for grp in perms.groups:
            owner_ok = (
                grp.owner_group in _BUILTIN_SP_GROUPS
                or grp.owner_group in custom_group_names
            )
            if not owner_ok:
                findings.append(Finding(
                    "error",
                    f"groups[{grp.name!r}]: owner_group {grp.owner_group!r} is not a "
                    f"built-in SP group or a declared custom group",
                ))

        # Collect all valid level names (built-in + declared custom).
        all_level_names = BUILT_IN_LEVELS | seen_level_names
        # Collect all valid group names (declared custom + built-in SP groups).
        all_group_names = custom_group_names | _BUILTIN_SP_GROUPS

        def _check_policy_assignments(policy: ListPermissionPolicy, ctx: str) -> None:
            for i, assignment in enumerate(policy.assignments):
                lvl = assignment.level
                if lvl not in all_level_names:
                    findings.append(Finding(
                        "error",
                        f"{ctx}.assignments[{i}]: level {lvl!r} is not a built-in "
                        f"or declared custom permission level",
                    ))
                principal = assignment.principal
                if principal.kind != "group":
                    continue
                suggested_kind = _ASSOCIATED_GROUP_ALIASES.get(
                    (principal.name or "").casefold(),
                )
                if suggested_kind is not None:
                    # Phase 4.2 resolves kind=group via sitegroups/getbyname(name).
                    # The built-in aliases never exist under these literal names
                    # on real sites (the associated groups are named
                    # '<SiteTitle> Owners' etc.), so the assignment would fail
                    # at deploy time.
                    findings.append(Finding(
                        "error",
                        f"{ctx}.assignments[{i}]: principal group "
                        f"{principal.name!r} is a built-in associated-group "
                        f"alias that cannot be resolved by name at deploy time "
                        f"(real sites name it '<SiteTitle> ...'). Use principal "
                        f"kind {suggested_kind!r} instead.",
                    ))
                elif principal.name not in all_group_names:
                    findings.append(Finding(
                        "error",
                        f"{ctx}.assignments[{i}]: principal group {principal.name!r} "
                        f"is not a built-in or declared custom group",
                    ))

        if perms.default_policy is not None:
            _check_policy_assignments(perms.default_policy, "list_permissions.default")

        # list_permissions.overrides keys must be unprefixed DBML table names.
        for entity_name, override_policy in perms.overrides.items():
            if entity_name not in table_names:
                findings.append(Finding(
                    "error",
                    f"list_permissions.overrides: key {entity_name!r} is not a "
                    "known DBML table name (use unprefixed name, "
                    "e.g. 'Ticket' not 'APP_Ticket')",
                ))
            ctx_key = f"list_permissions.overrides[{entity_name!r}]"
            _check_policy_assignments(override_policy, ctx_key)

    return findings
