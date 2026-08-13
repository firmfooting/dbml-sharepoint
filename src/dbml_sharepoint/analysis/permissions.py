# src/dbml_sharepoint/analysis/permissions.py
"""SP base permissions bitmask + permission-level / group / role-assignment helpers."""

from collections.abc import Iterable
from dataclasses import dataclass

from dbml_sharepoint.model._mapping_types import Mapping

# Per Microsoft.SharePoint.SPBasePermissions (64-bit unsigned). All bit
# positions below 32 land in Low; positions 32..62 land in High. Values
# are the full 64-bit form; we split into (high, low) when emitting.
BASE_PERMISSIONS: dict[str, int] = {
    "EmptyMask":                  0x0000000000000000,
    "ViewListItems":              0x0000000000000001,
    "AddListItems":               0x0000000000000002,
    "EditListItems":              0x0000000000000004,
    "DeleteListItems":            0x0000000000000008,
    "ApproveItems":               0x0000000000000010,
    "OpenItems":                  0x0000000000000020,
    "ViewVersions":               0x0000000000000040,
    "DeleteVersions":             0x0000000000000080,
    "CancelCheckout":             0x0000000000000100,
    "ManagePersonalViews":        0x0000000000000200,
    "ManageLists":                0x0000000000000800,
    "ViewFormPages":              0x0000000000001000,
    "AnonymousSearchAccessList":  0x0000000000002000,
    "Open":                       0x0000000000010000,
    "ViewPages":                  0x0000000000020000,
    "AddAndCustomizePages":       0x0000000000040000,
    "ApplyThemeAndBorder":        0x0000000000080000,
    "ApplyStyleSheets":           0x0000000000100000,
    "ViewUsageData":              0x0000000000200000,
    "CreateSSCSite":              0x0000000000400000,
    "ManageSubwebs":              0x0000000000800000,
    "CreateGroups":               0x0000000001000000,
    "ManagePermissions":          0x0000000002000000,
    "BrowseDirectories":          0x0000000004000000,
    "BrowseUserInfo":             0x0000000008000000,
    "AddDelPrivateWebParts":      0x0000000010000000,
    "UpdatePersonalWebParts":     0x0000000020000000,
    "ManageWeb":                  0x0000000040000000,
    "UseClientIntegration":       0x0000001000000000,
    "UseRemoteAPIs":              0x0000002000000000,
    "ManageAlerts":               0x0000004000000000,
    "CreateAlerts":               0x0000008000000000,
    "EditMyUserInfo":             0x0000010000000000,
    "EnumeratePermissions":       0x4000000000000000,
    "FullMask":                   0x7FFFFFFFFFFFFFFF,
}


@dataclass(frozen=True)
class HighLow:
    high: str   # decimal string of upper-32-bit value
    low: str    # decimal string of lower-32-bit value


def base_permissions_to_high_low(perm_names: list[str]) -> HighLow:
    """Combine a list of permission names into the High/Low decimal strings
    SP REST expects on SP.BasePermissions."""
    if not perm_names:
        return HighLow(high="0", low="0")
    combined = 0
    unknown: list[str] = []
    for name in perm_names:
        if name not in BASE_PERMISSIONS:
            unknown.append(name)
        else:
            combined |= BASE_PERMISSIONS[name]
    if unknown:
        raise ValueError(
            f"Unknown base permission name(s): {', '.join(sorted(unknown))}. "
            f"See dbml_sharepoint.analysis.permissions.BASE_PERMISSIONS for the full list.",
        )
    high = (combined >> 32) & 0xFFFFFFFF
    low = combined & 0xFFFFFFFF
    return HighLow(high=str(high), low=str(low))


# Built-in level names that don't need creation; the deployer just resolves
# them by name when binding role assignments. Also the RESERVED set: a
# mapping may not declare a `permission_levels` entry named after one, because
# `_security_principals.js.j2` reconciles a same-name role definition rather
# than skipping it, and would rewrite the site's copy for every principal.
#
# All eleven from Microsoft Learn, "Permission levels in SharePoint"
# (https://learn.microsoft.com/sharepoint/understanding-permission-levels),
# checked 2026-08-13 rather than written from memory. `View Only` and
# `Web-Only Limited Access` were both missing; the second is in the same Learn
# table and is routinely left out of the commonly-quoted list of ten.
#
# TWO CAVEATS this set cannot express, neither of which it makes worse:
#   - Approve, Manage Hierarchy and Restricted Read are publishing-template
#     levels and may not exist on a modern team or communication site.
#   - Learn says Limited Access "cannot be assigned directly", so accepting it
#     as an assignment level is doubtful. That predates this comment and is
#     tracked separately; nothing here starts relying on it.
#
# The names are ENGLISH. Built-in levels are locale-dependent, so on a
# non-English tenant none of these match and a mapping could still redefine a
# built-in. Closing that means resolving by RoleType or Id against a live
# site. `ENTERPRISE_READER_GROUP_OVER_PRIVILEGED` has the same blind spot.
BUILT_IN_LEVELS: frozenset[str] = frozenset({
    "Read", "Contribute", "Edit", "Design", "Full Control",
    "Limited Access", "Web-Only Limited Access", "Approve",
    "Manage Hierarchy", "Restricted Read", "View Only",
})


def requires_manage_permissions(mapping: Mapping, table_names: Iterable[str]) -> bool:
    """True when deploying `table_names` performs ANY ACL work, and so needs
    the ManagePermissions site right.

    Three call sites each used to answer this on their own: assessgen's
    preflight requirement, the human-readable manifest, and deploy.js's own
    live preflight abort. The manifest and deploy.js already agreed --
    "declares custom permission levels, custom groups, or a per-list ACL
    policy" -- but assessgen tested `declares_break_inheritance` instead of
    "a policy exists", so a `break_inheritance: false` policy (built-in level,
    built-in associated group, inheritance left alone) made assess.js predict
    no ManagePermissions requirement while deploy.js demanded it and aborted.
    See #166 item 5, reproduced against a from-scratch mapping with zero
    validator findings.

    A per-list policy counts even with `break_inheritance: false`: deploy.js
    still binds the declared role assignments on the (inherited) list, which
    still needs the bit. `table_names` should be the entity names actually in
    this build (`analysis.ordering.site_tables_in_order`'s output), not every
    entity in the mapping -- a policy scoped to a site_role this build does
    not deploy must not demand a right the build never exercises.
    """
    perms = mapping.permissions
    if perms is None:
        return False
    if perms.levels or perms.groups:
        return True
    return any(mapping.permissions_for_entity(name) is not None for name in table_names)


def lists_granting_group(
    mapping: Mapping, group_name: str, table_names: Iterable[str],
) -> tuple[list[str], list[str]]:
    """Split `table_names` into those `group_name` is granted on, and those not.

    Resolved per entity through `Mapping.permissions_for_entity`, which is the
    same resolution `jsgen` uses to bind the live role assignments -- so this
    reports what the deploy will actually do rather than restating the
    mapping's shape.

    Deliberately NOT `checks/_permissions._levels_granted_to_group`, which
    unions every policy block. That union answers "does any block grant this
    group at all", and its own docstring records that it lets an override
    exclude the group from one list ON PURPOSE, because an override exists to
    differ. The manifest needs the opposite question, asked per list.

    The manifest said the enterprise reader "can read every list this bundle"
    creates, unconditionally. For a valid custom mapping that grants the
    reader on the default policy and omits it from one override, that told an
    operator the reporting account had fleet-wide access while one list was
    silently unreadable. The shipped families are pinned separately by
    `test_the_reader_group_is_granted_read_on_every_policy_block`; nothing
    constrains a custom one.
    """
    granted: list[str] = []
    excluded: list[str] = []
    for name in table_names:
        policy = mapping.permissions_for_entity(name)
        assignments = policy.assignments if policy is not None else []
        if any(
            a.principal.kind == "group" and a.principal.name == group_name
            for a in assignments
        ):
            granted.append(name)
        else:
            excluded.append(name)
    return granted, excluded
