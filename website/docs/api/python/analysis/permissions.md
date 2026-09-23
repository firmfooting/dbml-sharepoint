---
title: permissions
sidebar_position: 21
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

### `ENTERPRISE_READER_REQUIRED_PERMISSIONS`

```python
ENTERPRISE_READER_REQUIRED_PERMISSIONS = ('ViewListItems', 'ViewFormPages', 'Open')
```

### `ENTERPRISE_READER_ADVISORY_PERMISSIONS`

```python
ENTERPRISE_READER_ADVISORY_PERMISSIONS = ('BrowseUserInfo', 'UseRemoteAPIs')
```

### `ENTERPRISE_READER_ELEVATED_PERMISSIONS`

```python
ENTERPRISE_READER_ELEVATED_PERMISSIONS = ('AddListItems', 'EditListItems', 'DeleteListItems', 'ApproveItems', 'DeleteVersions', 'CancelCheckout', 'ManageLists', 'AddAndCustomizePages', 'ApplyThemeAndBorder', 'ApplyStyleSheets', 'AddDelPrivat…
```

### `permission_bit_table`

```python
def permission_bit_table(perm_names: collections.abc.Iterable[str]) -> list[dict[str, str]]
```

`{name, high, low}` per permission, for a runtime bitmap test.

Split the same way `base_permissions_to_high_low` splits a level, because
SP.BasePermissions is read back as two Int64 halves and the emitted script
compares against each half separately.

### `BUILTIN_SP_GROUPS`

```python
BUILTIN_SP_GROUPS = frozenset({'Members', 'Owners', 'Site Members', 'Site Owners', 'Site Visitors', 'Visitors'})
```

### `ASSOCIATED_GROUP_ALIASES`

```python
ASSOCIATED_GROUP_ALIASES = {'site owners': 'associated_owner_group', 'site members': 'associated_member_group', 'site visitors': 'associated_visitor_group'}
```

### `requires_manage_permissions`

```python
def requires_manage_permissions(resolved: dbml_sharepoint.analysis.resolve.ResolvedMapping, table_names: collections.abc.Iterable[str]) -> bool
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
still needs the bit. What it does NOT do is count the policy's existence,
which was a proxy for the ACL work it performs: a policy that breaks no
inheritance, declares no assignment and reconciles `configured` makes
`reconcileScope` read and write nothing, and demanding the right for it
made both the assessment and deploy.js's live preflight reject an
operator holding every right the deployment exercises. `_policy_writes`
asks the effective question for both scopes.

`table_names` should be the entity names actually in this build
(`analysis.ordering.site_tables_in_order`'s output), not every entity in
the mapping -- a policy scoped to a site_role this build does not deploy
must not demand a right the build never exercises. `groups` is
`resolved.groups`, for the same reason -- and no `require_resolved()`
call precedes reading it: an unresolved source is reported by its own
validator rule, and this function must stay exactly as lenient as
`resolved.groups` already is rather than fail closed on a mapping-wide
check a `table_names`-scoped question never asked.

### `GroupReach`

Where a group is granted across the lists a caller asked about.

Three ways, not two: a folder grant binds inside the declared folders and
nowhere else, so a caller that cannot tell it from a list grant reports
access to a whole library the deploy never binds.

### `lists_granting_group`

```python
def lists_granting_group(resolved: dbml_sharepoint.analysis.resolve.ResolvedMapping, group_name: str, table_names: collections.abc.Iterable[str]) -> dbml_sharepoint.analysis.permissions.GroupReach
```

Split `table_names` by where `group_name` is granted, if anywhere.

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
creates, unconditionally, and later said it of a list whose only grant
was on the declared folders inside it. For a valid custom mapping that grants the
reader on the default policy and omits it from one override, that told an
operator the reporting account had fleet-wide access while one list was
silently unreadable. The shipped families are pinned separately by
`test_the_reader_group_is_granted_read_on_every_policy_block`; nothing
constrains a custom one.

Folder policies are read through `require_folder_policies`, which keeps
the scope `analysis/folders.py::folder_policies` had: an entity with no
`list_permissions.folders` entry answers `()` whatever its folder source
resolves to, and one whose policy's folders depend on an enum that did
not resolve raises `UnknownFolderEnumError`. Subscripting
`resolved.folder_policies` instead raised for every unresolved entity,
including the ones with no folder policy, and raised `KeyError`:
`pipeline` calls this at the reader gate BEFORE `validate_all`, so a
mapping whose only defect is a misspelled `folders.from_enum` died on a
bare traceback instead of reporting `folder_enum_unknown` with its
findings manifest. No `require_resolved()` call precedes this either --
`table_names` is scoped to one build's site role, and this must judge
exactly that scope rather than fail the whole mapping over an entity
this call was never asked about.

