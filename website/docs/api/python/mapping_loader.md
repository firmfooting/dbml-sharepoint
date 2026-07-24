---
title: mapping_loader
sidebar_position: 2
---

# `dbml_sharepoint.mapping_loader`

*Model — load mapping.yaml and referenced config*

Loader for schema/sharepoint-mapping.yaml plus its referenced config YAMLs.

Generic core loader. Resolves relative config paths
(enum_sources values, retention_policies_source) relative to the mapping
YAML's own directory, so the deployer can be invoked from any working
directory. Project-specific config lives under `extensions: {<name>: {...}}`
and is passed through untyped as `MappingBundle.extension_configs` — this
module knows nothing about what any particular extension's block means, and
selection by name is deferred to `MappingBundle.extension_config_for` so it
honors the RESOLVED extension (a CLI `--extension` override may differ from
the mapping's own `extension:` key).

### `ENTITY_KINDS`

```python
ENTITY_KINDS = frozenset({'DocumentLibrary', 'HubOnlyList', 'List'})
```

### `auto_display_name`

```python
def auto_display_name(internal_name: str) -> str
```

Human-readable display title derived from a PascalCase internal name.

### `view_url_slug`

```python
def view_url_slug(title: str) -> str
```

URL-safe view page name derived from the declared view title.

A view's .aspx file name is fixed at creation from its Title, so views
are created with this slug and renamed to the declared title afterwards
("Open by score" lives at OpenByScore.aspx, not Open%20by%20score.aspx —
the same create-then-rename trick fields use for display titles).

### `EntityMapping`

```python
@dataclass
class EntityMapping:
    name: str
    kind: EntityKind
    base_template: int
    site_role: str
    singleton: bool = False
    display_column: str | None = None
```

SP physical mapping for one entity (kind, base template, site role).

### `CrossSiteRef`

```python
@dataclass
class CrossSiteRef:
    entity: str
    column: str
```

A column to expand into the Choice + URL cross-site triple.

### `PolymorphicPattern`

```python
@dataclass
class PolymorphicPattern:
    list: str
    field: str
    discriminator: str
```

A polymorphic column pattern.

``list`` is the unprefixed entity name whose ``field`` holds a logical FK
discriminated by ``discriminator``. Referential integrity is not enforced
by SharePoint; the manifest surfaces these so downstream flows validate
them at write time.

### `Versioning`

```python
@dataclass
class Versioning:
    enable_versioning: bool
    major_version_limit: int
    enable_minor_versions: bool
```

Default SP list versioning settings.

### `WatchedList`

```python
@dataclass
class WatchedList:
    entity: str
    column: str
```

A (entity, column) pair watched by W10 status capture.

### `ViewCondition`

```python
@dataclass
class ViewCondition:
    field: str
    op: str
    value: Any = None
```

One &lt;Where> condition of a declared view. Conditions are ANDed.

`op` is validated against the DSL allowlist by validate_against_mapping;
`value` is absent for is_null/is_not_null and may be the `today`,
`today+N` or `today-N` sentinel on date/datetime columns.

### `ViewSort`

```python
@dataclass
class ViewSort:
    field: str
    direction: SortDirection
```

One &lt;OrderBy> entry of a declared view.

### `ViewGroupBy`

```python
@dataclass
class ViewGroupBy:
    field: str
    collapsed: bool = False
```

The &lt;GroupBy> of a declared view.

### `ViewDef`

```python
@dataclass
class ViewDef:
    title: str
    fields: list[str]
    default: bool = False
    where: list[dbml_sharepoint.mapping_loader.ViewCondition] = list()
    sort: list[dbml_sharepoint.mapping_loader.ViewSort] = list()
    group_by: dbml_sharepoint.mapping_loader.ViewGroupBy | None = None
    row_limit: int | None = None
    formatting: dict[str, typing.Any] | None = None
    widths: dict[str, int] = dict()
```

One declared SharePoint list view (mapping `views:` section).

### `DemoItem`

```python
@dataclass
class DemoItem:
    key: str
    values: dict[str, typing.Any]
```

One declared demo/sample row (mapping `demo_items:` section).

`values` are authored with INTERNAL column names. The value grammar —
"@me" (deploying operator) on person columns, "today+N"/"today-N" on
date columns, {demo_ref: key} on lookups — is resolved by the generated
demo-data.js at RUN time; semantic rules live in the validator. Every
Title must start with "[DEMO] ": that marker is what the teardown
trusts to distinguish demo rows from real records.

### `FormFormatting`

```python
@dataclass
class FormFormatting:
    header: dict[str, typing.Any] | None = None
    body: dict[str, typing.Any] | None = None
    footer: dict[str, typing.Any] | None = None
```

Declared list-form layout parts (SP ClientFormCustomFormatter).

Each part is a formatter JSON object; at least one must be declared.
Body section field lists are authored with INTERNAL names; jsgen
rewrites them to display titles (SP matches form fields by display).

### `ListValidation`

```python
@dataclass
class ListValidation:
    formula: str
    message: str
```

Declared SP list validation (ValidationFormula/ValidationMessage).

Authored with INTERNAL column names; jsgen rewrites references to
display names (SP resolves validation formulas by display, like
calculated formulas).

### `CustomPermissionLevel`

```python
@dataclass
class CustomPermissionLevel:
    name: str
    description: str
    base_permissions: list[str]
```

A custom permission level to create at the site.

### `SiteGroup`

```python
@dataclass
class SiteGroup:
    name: str
    description: str
    owner_group: str
    allow_members_edit_membership: bool
    allow_request_to_join_leave: bool
    auto_accept_request_to_join_leave: bool
    only_allow_members_view_membership: bool
    require_empty_at_deploy: bool = False
    enroll_operator_during_deploy: bool = False
```

A SharePoint site group to create at the site.

### `Principal`

```python
@dataclass
class Principal:
    kind: PrincipalKind
    name: str | None = None
```

A role-assignment target. `kind` is one of:
'group' (a named site group, custom or built-in like 'Site Owners'),
'associated_owner_group', 'associated_member_group', 'associated_visitor_group'.
`name` is required for kind=group, ignored otherwise.

### `RoleAssignment`

```python
@dataclass
class RoleAssignment:
    principal: Principal
    level: str
```

RoleAssignment(principal: dbml_sharepoint.mapping_loader.Principal, level: str)

### `ListPermissionPolicy`

```python
@dataclass
class ListPermissionPolicy:
    break_inheritance: bool
    assignments: list[dbml_sharepoint.mapping_loader.RoleAssignment]
    reconcile_mode: ReconcileMode = 'configured'
```

ListPermissionPolicy(break_inheritance: bool, assignments: list[dbml_sharepoint.mapping_loader.RoleAssignment], reconcile_mode: ReconcileMode = 'configured')

### `PermissionsConfig`

```python
@dataclass
class PermissionsConfig:
    levels: list[dbml_sharepoint.mapping_loader.CustomPermissionLevel]
    groups: list[dbml_sharepoint.mapping_loader.SiteGroup]
    default_policy: dbml_sharepoint.mapping_loader.ListPermissionPolicy | None
    overrides: dict[str, dbml_sharepoint.mapping_loader.ListPermissionPolicy]
    default_policy_site_role: str | None = None
```

PermissionsConfig(levels: list[dbml_sharepoint.mapping_loader.CustomPermissionLevel], groups: list[dbml_sharepoint.mapping_loader.SiteGroup], default_policy: dbml_sharepoint.mapping_loader.ListPermissionPolicy | None, overrides: dict[str, dbml_sharepoint.mapping_loader.ListPermissionPolicy], default_policy_site_role: str | None = None)

### `Mapping`

```python
@dataclass
class Mapping:
    prefix: str
    prefix_owner: str
    prefix_registry: str
    entities: dict[str, dbml_sharepoint.mapping_loader.EntityMapping]
    cross_site_reference_columns: list[dbml_sharepoint.mapping_loader.CrossSiteRef]
    indexed_columns: dict[str, list[str]]
    versioning_default: Versioning
    versioning_overrides: dict[str, dict[str, typing.Any]]
    enum_sources: dict[str, pathlib.Path]
    watched_lists: list[dbml_sharepoint.mapping_loader.WatchedList]
    polymorphic_patterns: list[dbml_sharepoint.mapping_loader.PolymorphicPattern] = list()
    retention_policies_source: pathlib.Path | None = None
    extension: str | None = None
    permissions: PermissionsConfig | None = None
    calculated_formulas: dict[str, dict[str, str]] = dict()
    views: dict[str, list[dbml_sharepoint.mapping_loader.ViewDef]] = dict()
    demo_items: dict[str, list[dbml_sharepoint.mapping_loader.DemoItem]] = dict()
    display_name_mode: str | None = None
    display_name_overrides: dict[str, dict[str, str]] = dict()
    column_style_specs: dict[str, dict[str, dict[str, typing.Any]]] = dict()
    column_formatting: dict[str, dict[str, dict[str, typing.Any]]] = dict()
    form_formatting: dict[str, dbml_sharepoint.mapping_loader.FormFormatting] = dict()
    list_validation: dict[str, dbml_sharepoint.mapping_loader.ListValidation] = dict()
    hidden_on_forms: dict[str, list[str]] = dict()
    hidden_on_display: dict[str, list[str]] = dict()
    seal_columns: bool = False
    prevent_list_deletion: bool = False
```

The full schema/sharepoint-mapping.yaml structure.

#### `Mapping.display_name_for`

```python
def display_name_for(self, entity_name: str, column_name: str) -> str
```

Display title for a rendered column: override, else auto-split
PascalCase when mode is auto, else the internal name unchanged.

#### `Mapping.entity`

```python
def entity(self, name: str) -> dbml_sharepoint.mapping_loader.EntityMapping
```

#### `Mapping.permissions_for_entity`

```python
def permissions_for_entity(self, entity_name: str) -> 'ListPermissionPolicy | None'
```

Return the per-list permission policy for the given entity name.

Returns override if present, else the default policy — but the default
only applies when its site-role scope (if any) matches the entity's
site_role. A default scoped to one role must not re-ACL lists
belonging to another role.

### `RetentionPolicy`

```python
@dataclass
class RetentionPolicy:
    name: str
    description: str
    sp_label: str
    retain_years: int | None
    retain_days: int | None
    trigger: str
```

One policy from config/retention-policies.yaml.

### `MappingBundle`

```python
@dataclass
class MappingBundle:
    mapping: Mapping
    enum_choices: dict[str, list[str]]
    retention_policies: dict[str, dbml_sharepoint.mapping_loader.RetentionPolicy]
    retention_list_defaults: dict[str, str]
    extension_configs: dict[str, dict[str, typing.Any]] = dict()
    source_paths: dict[str, pathlib.Path] = dict()
```

Mapping + the generic configs it references, all loaded.

#### `MappingBundle.extension_config_for`

```python
def extension_config_for(self, name: str | None) -> dict[str, typing.Any]
```

The named extension's config block; {} when name is None or the
mapping declares no block for it. Extensions should call this with
their own ``name`` so config selection always matches the extension
actually running, regardless of how it was resolved.

### `load_mapping`

```python
def load_mapping(mapping_path: pathlib.Path) -> dbml_sharepoint.mapping_loader.MappingBundle
```

Load the mapping YAML and the referenced configs into a single bundle.

