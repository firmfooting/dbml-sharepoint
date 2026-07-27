---
title: mapping_loader
sidebar_position: 2
---

# `dbml_sharepoint.model.mapping_loader`

*load mapping.yaml and referenced config*

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

### `RETIRED_SUFFIX`

```python
RETIRED_SUFFIX = ' (retired)'
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

### `FormVisibility`

```python
@dataclass
class FormVisibility:
    new: bool = True
    existing: bool = True
    when: Condition | None = None
```

One column's declared form behaviour.

`existing` covers the Edit form AND the Display form, which SharePoint
does not let us separate — the modern Display form reads ShowInEditForm
and ignores ShowInDisplayForm entirely. The key is named for what it
does rather than for the form an author might expect.

### `ColumnValidation`

```python
@dataclass
class ColumnValidation:
    when: Condition
    message: str
```

One column's save-time rule. The message is the feature: without it
a failed save shows SharePoint's generic text, which tells the person
filling in the form nothing.

### `EntitySection`

```python
@dataclass
class EntitySection:
    reconcile: str = 'exact'
    columns: dict[str, T] = dict()
```

A per-entity block of column declarations plus its reconcile mode.

`exact` (the default) makes the declaration authoritative for the whole
entity: a column with no entry has its value cleared, so deployed state
is a function of the declaration rather than of declaration history.
`declared` touches only what is listed, for mappings running
seal_columns: false where an operator may have set something by hand.

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
    where: Condition | None = None
    sort: list[dbml_sharepoint.model.mapping_loader.ViewSort] = list()
    group_by: dbml_sharepoint.model.mapping_loader.ViewGroupBy | None = None
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
    when: Condition
    message: str
```

Declared SP list validation (ValidationFormula/ValidationMessage).

Cross-column: unlike `column_validation`, the condition may name any
column on the list. Authored as a condition tree — the raw `formula:`
key is gone, because it was the last surface where an author wrote
SharePoint syntax by hand and so the last place the quoting and
operator differences between the targets could bite them.

### `RetiredColumn`

```python
@dataclass
class RetiredColumn:
    column: str
    retired: str = ''
    superseded_by: str | None = None
    reason: str = ''
    hide_existing: bool = False
```

One retired column (mapping `retired_columns:` section).

Retirement is a deployment-lifecycle fact, not a logical-model one: the
column stays declared in the DBML and keeps its data — deleting the
declaration would leave a live, deletable column the schema no longer
knows about, which the generated `_UserAddedColumns.pq` drift audit
would report forever — but it leaves the New form and every declared
view, and its display title carries RETIRED_SUFFIX.

`hide_existing` additionally hides it from the Edit form, which on a
modern list also hides it from the Display form: SharePoint reads
ShowInEditForm for both and there is no way to separate them (the
reason the old `hidden_on_display:` section was removed). Default false,
so the history a retired column exists to preserve stays readable.

`retired` is the declared ISO date; it is "" for the bare-list
shorthand, which carries no date. Format checking, column existence and
supersession targets need the schema and live in the validator.

### `RetirementStrip`

```python
@dataclass
class RetirementStrip:
    entity: str
    column: str
    context: str
```

One declared reference to a retired column that `_apply_retirement`
removed or replaced. The structure no longer carries the reference, so
the record is kept here for the validator: retirement must never break
a build, but a stale declaration is worth telling the author about.

`context` is the human-readable declaration site, e.g.
"views[Tier3Board].Last 14 days fields".

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

RoleAssignment(principal: dbml_sharepoint.model.mapping_loader.Principal, level: str)

### `ListPermissionPolicy`

```python
@dataclass
class ListPermissionPolicy:
    break_inheritance: bool
    assignments: list[dbml_sharepoint.model.mapping_loader.RoleAssignment]
    reconcile_mode: ReconcileMode = 'configured'
```

ListPermissionPolicy(break_inheritance: bool, assignments: list[dbml_sharepoint.model.mapping_loader.RoleAssignment], reconcile_mode: ReconcileMode = 'configured')

### `PermissionsConfig`

```python
@dataclass
class PermissionsConfig:
    levels: list[dbml_sharepoint.model.mapping_loader.CustomPermissionLevel]
    groups: list[dbml_sharepoint.model.mapping_loader.SiteGroup]
    default_policy: dbml_sharepoint.model.mapping_loader.ListPermissionPolicy | None
    overrides: dict[str, dbml_sharepoint.model.mapping_loader.ListPermissionPolicy]
    default_policy_site_role: str | None = None
```

PermissionsConfig(levels: list[dbml_sharepoint.model.mapping_loader.CustomPermissionLevel], groups: list[dbml_sharepoint.model.mapping_loader.SiteGroup], default_policy: dbml_sharepoint.model.mapping_loader.ListPermissionPolicy | None, overrides: dict[str, dbml_sharepoint.model.mapping_loader.ListPermissionPolicy], default_policy_site_role: str | None = None)

### `Mapping`

```python
@dataclass
class Mapping:
    prefix: str
    prefix_owner: str
    prefix_registry: str
    entities: dict[str, dbml_sharepoint.model.mapping_loader.EntityMapping]
    cross_site_reference_columns: list[dbml_sharepoint.model.mapping_loader.CrossSiteRef]
    indexed_columns: dict[str, list[str]]
    versioning_default: Versioning
    versioning_overrides: dict[str, dict[str, typing.Any]]
    enum_sources: dict[str, pathlib.Path]
    watched_lists: list[dbml_sharepoint.model.mapping_loader.WatchedList]
    polymorphic_patterns: list[dbml_sharepoint.model.mapping_loader.PolymorphicPattern] = list()
    retention_policies_source: pathlib.Path | None = None
    extension: str | None = None
    permissions: PermissionsConfig | None = None
    calculated_formulas: dict[str, dict[str, str]] = dict()
    form_visibility: dict[str, dbml_sharepoint.model.mapping_loader.EntitySection[dbml_sharepoint.model.mapping_loader.FormVisibility]] = dict()
    column_validation: dict[str, dbml_sharepoint.model.mapping_loader.EntitySection[dbml_sharepoint.model.mapping_loader.ColumnValidation]] = dict()
    views: dict[str, list[dbml_sharepoint.model.mapping_loader.ViewDef]] = dict()
    demo_items: dict[str, list[dbml_sharepoint.model.mapping_loader.DemoItem]] = dict()
    display_name_mode: str | None = None
    display_name_overrides: dict[str, dict[str, str]] = dict()
    column_style_specs: dict[str, dict[str, dict[str, typing.Any]]] = dict()
    column_formatting: dict[str, dict[str, dict[str, typing.Any]]] = dict()
    form_formatting: dict[str, dbml_sharepoint.model.mapping_loader.FormFormatting] = dict()
    list_validation: dict[str, dbml_sharepoint.model.mapping_loader.ListValidation] = dict()
    retired_columns: dict[str, dict[str, dbml_sharepoint.model.mapping_loader.RetiredColumn]] = dict()
    retirement_strips: list[dbml_sharepoint.model.mapping_loader.RetirementStrip] = list()
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
def entity(self, name: str) -> dbml_sharepoint.model.mapping_loader.EntityMapping
```

#### `Mapping.is_retired`

```python
def is_retired(self, entity_name: str, column_name: str) -> bool
```

True when `retired_columns` declares this column for this entity.

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
    retention_policies: dict[str, dbml_sharepoint.model.mapping_loader.RetentionPolicy]
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

### `KNOWN_SECTIONS`

```python
KNOWN_SECTIONS = frozenset({'calculated_formulas', 'column_formatting', 'column_validation', 'cross_site_reference_columns', 'demo_items', 'display_names', 'entities', 'enum_sources', 'extension', 'extensions', 'form_…
```

### `load_mapping`

```python
def load_mapping(mapping_path: pathlib.Path) -> dbml_sharepoint.model.mapping_loader.MappingBundle
```

Load the mapping YAML and the referenced configs into a single bundle.

