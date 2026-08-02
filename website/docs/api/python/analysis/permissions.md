---
title: permissions
sidebar_position: 10
---

# `dbml_sharepoint.analysis.permissions`

*SP base-permission bitmask helpers*

SP base permissions bitmask + permission-level / group / role-assignment helpers.

### `BASE_PERMISSIONS`

```python
BASE_PERMISSIONS = {'EmptyMask': 0, 'ViewListItems': 1, 'AddListItems': 2, 'EditListItems': 4, 'DeleteListItems': 8, 'ApproveItems': 16, 'OpenItems': 32, 'ViewVersions': 64, 'DeleteVersions': 128, 'CancelCheckout': 256,…
```

### `HighLow`

```python
@dataclass(frozen=True)
class HighLow:
    high: str
    low: str
```

HighLow(high: str, low: str)

### `base_permissions_to_high_low`

```python
def base_permissions_to_high_low(perm_names: list[str]) -> dbml_sharepoint.analysis.permissions.HighLow
```

Combine a list of permission names into the High/Low decimal strings
SP REST expects on SP.BasePermissions.

### `BUILT_IN_LEVELS`

```python
BUILT_IN_LEVELS = frozenset({'Approve', 'Contribute', 'Design', 'Edit', 'Full Control', 'Limited Access', 'Manage Hierarchy', 'Read', 'Restricted Read'})
```

