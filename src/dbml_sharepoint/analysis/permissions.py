# src/dbml_sharepoint/analysis/permissions.py
"""SP base permissions bitmask + permission-level / group / role-assignment helpers."""

from dataclasses import dataclass

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
# them by name when binding role assignments.
BUILT_IN_LEVELS: frozenset[str] = frozenset({
    "Read", "Contribute", "Edit", "Design", "Full Control",
    "Limited Access", "Approve", "Manage Hierarchy", "Restricted Read",
})
