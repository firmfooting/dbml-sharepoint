---
title: permissions
sidebar_position: 11
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
BUILT_IN_LEVELS = frozenset({'Approve', 'Contribute', 'Design', 'Edit', 'Full Control', 'Limited Access', 'Manage Hierarchy', 'Read', 'Restricted Read', 'View Only', 'Web-Only Limited Access'})
```

### `DERIVED_BUILT_IN_LEVELS`

```python
DERIVED_BUILT_IN_LEVELS = frozenset({'Limited Access', 'Web-Only Limited Access'})
```

### `ASSIGNABLE_BUILT_IN_LEVELS`

```python
ASSIGNABLE_BUILT_IN_LEVELS = frozenset({'Approve', 'Contribute', 'Design', 'Edit', 'Full Control', 'Manage Hierarchy', 'Read', 'Restricted Read', 'View Only'})
```

### `requires_manage_permissions`

```python
def requires_manage_permissions(mapping: dbml_sharepoint.model._mapping_types.Mapping, table_names: collections.abc.Iterable[str]) -> bool
```

True when deploying `table_names` performs ANY ACL work, and so needs
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

### `lists_granting_group`

```python
def lists_granting_group(mapping: dbml_sharepoint.model._mapping_types.Mapping, group_name: str, table_names: collections.abc.Iterable[str]) -> tuple[list[str], list[str]]
```

Split `table_names` into those `group_name` is granted on, and those not.

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

