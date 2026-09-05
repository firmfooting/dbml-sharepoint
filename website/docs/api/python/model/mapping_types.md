---
title: mapping_types
sidebar_position: 3
---

# `dbml_sharepoint.model.mapping_types`

*the mapping vocabulary an extension hook receives*

The shapes a mapping.yaml parses into.

Declarations only: every dataclass the loader produces, the closed
vocabularies they are constrained to, and the few pure helpers that derive
one field from another. No parsing and no file access live here, so a
reader answering "what does this section become?" does not have to read the
parser to find out.

### `ENTITY_KINDS`

```python
ENTITY_KINDS = frozenset({'DocumentLibrary', 'HubOnlyList', 'List'})
```

### `PRINCIPAL_KINDS`

```python
PRINCIPAL_KINDS = frozenset({'associated_member_group', 'associated_owner_group', 'associated_visitor_group', 'group'})
```

### `PRINCIPAL_KIND_LIST`

```python
PRINCIPAL_KIND_LIST = "'associated_member_group', 'associated_owner_group', 'associated_visitor_group', 'group'"
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
("Open by score" lives at OpenByScore.aspx, not Open%20by%20score.aspx,
the same create-then-rename trick fields use for display titles).

### `EntityMapping`

```python
@dataclass(frozen=True)
class EntityMapping:
    name: str
    kind: EntityKind
    base_template: int
    site_role: str
    singleton: bool = False
    display_column: str | None = None
    accept_unindexable_display_column: bool = False
    hide_from_all_items: tuple[str, ...] = ()
    renamed_from: tuple[str, ...] = ()
```

SP physical mapping for one entity (kind, base template, site role).

### `CrossSiteRef`

```python
@dataclass(frozen=True)
class CrossSiteRef:
    entity: str
    column: str
```

A column to expand into the Choice + URL cross-site triple.

### `PolymorphicPattern`

```python
@dataclass(frozen=True)
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
@dataclass(frozen=True)
class Versioning:
    enable_versioning: bool = True
    major_version_limit: int = 500
    enable_minor_versions: bool = False
```

SP list versioning settings, defaults included.

THE DEFAULTS LIVE HERE, on the dataclass, and that is the point. With all
three fields required, the default for each had nowhere to live but the
caller, so `versioning.default.major_version_limit` absent meant every
reader wrote `500` for itself, and the merge of a per-entity override onto
the default was open-coded three times over (`jsgen`, `reportgen`,
`assessgen`) in three different spellings. The third used bare truthiness
with no fallback at all, so the copies were not merely duplicated, they
disagreed.

`Mapping.versioning_for` is now the one merge. See it for the shape an
override takes.

### `ItemSecurity`

```python
@dataclass(frozen=True)
class ItemSecurity:
    read: str = 'all'
    write: str = 'all'
```

SP list ITEM-level permissions: whose items a principal may see and edit.

Two settings on `SP.List`, `ReadSecurity` and `WriteSecurity`, each taking
1 ("all items") or 2 ("items created by the user"). They narrow what a
principal's LIST-level grant reaches, so a group holding Contribute on a
list with `read: own` can add rows and read back only its own.

`all` on both is SharePoint's own default and this tool's, so a mapping
that says nothing declares nothing and the deploy never touches the two
properties. Only a mapping that asks for trimming gets the reconcile.

NOT MODELLED: `WriteSecurity` = 4, which is documented as "no items". It
is left out because nothing here needs it and this repository does not
emit a SharePoint value it has not measured. Adding it means a probe
under `test/manual/` first.

THE ONE THING THIS CANNOT PROMISE is which levels bypass the trim.
Elevated principals (Full Control, and by report anything holding
ManageLists) are widely said to see every item regardless, and that has
NOT been measured here. `deployment-log`'s `30-deploy/deploy.md` carries
the probe that has to run before any reader posture leans on it.

### `ITEM_SECURITY_SCOPES`

```python
ITEM_SECURITY_SCOPES = frozenset({'all', 'own'})
```

### `WatchedList`

```python
@dataclass(frozen=True)
class WatchedList:
    entity: str
    column: str
```

A (entity, column) pair watched by W10 status capture.

### `FormVisibility`

```python
@dataclass(frozen=True)
class FormVisibility:
    new: bool = True
    existing: bool = True
    when: Condition | None = None
```

One column's declared form behaviour.

`existing` covers the Edit form AND the Display form, which SharePoint
does not let us separate. The modern Display form reads ShowInEditForm
and ignores ShowInDisplayForm entirely. The key is named for what it
does rather than for the form an author might expect.

### `ColumnValidation`

```python
@dataclass(frozen=True)
class ColumnValidation:
    when: Condition
    message: str
```

One column's save-time rule. The message is the feature: without it
a failed save shows SharePoint's generic text, which tells the person
filling in the form nothing.

### `EntitySection`

```python
@dataclass(frozen=True)
class EntitySection:
    reconcile: str = 'exact'
    columns: dict[str, T] = field(default_factory=dict)
```

A per-entity block of column declarations plus its reconcile mode.

`exact` (the default) makes the declaration authoritative for the whole
entity: a column with no entry has its value cleared, so deployed state
is a function of the declaration rather than of declaration history.
`declared` touches only what is listed, for mappings running
seal_columns: false where an operator may have set something by hand.

### `ViewSort`

```python
@dataclass(frozen=True)
class ViewSort:
    field: str
    direction: SortDirection
```

One &lt;OrderBy> entry of a declared view.

### `ViewGroupBy`

```python
@dataclass(frozen=True)
class ViewGroupBy:
    fields: list[str]
    collapsed: bool = False
```

The &lt;GroupBy> of a declared view.

SharePoint groups by up to two levels. Authoring accepts `field:` for
one or `fields:` for one or two; both land here as a list, because two
accessors for one concept is how the two drift apart.

### `ViewDef`

```python
@dataclass(frozen=True)
class ViewDef:
    title: str
    fields: list[str]
    renamed_from: list[str] = field(default_factory=list)
    default: bool = False
    where: Condition | None = None
    sort: list[dbml_sharepoint.model.mapping_types.ViewSort] = field(default_factory=list)
    group_by: dbml_sharepoint.model.mapping_types.ViewGroupBy | None = None
    row_limit: int | None = None
    formatting: dict[str, typing.Any] | None = None
    widths: dict[str, int] = field(default_factory=dict)
    totals: dict[str, str] = field(default_factory=dict)
    expanded_sets: list[str] = field(default_factory=list)
```

One declared SharePoint list view (mapping `views:` section).

### `DemoItem`

```python
@dataclass(frozen=True)
class DemoItem:
    key: str
    values: dict[str, typing.Any]
```

One declared demo/sample row (mapping `demo_items:` section).

`values` are authored with INTERNAL column names. The value grammar
("@me" (deploying operator) on person columns, "today+N"/"today-N" on
date columns, {demo_ref: key} on lookups) is resolved by the generated
demo-data.js at RUN time; semantic rules live in the validator. Every
Title must start with the configured demo prefix so sample data is visible
in every view and form. Rollback requires per-list confirmation before every delete.

### `FormFormatting`

```python
@dataclass(frozen=True)
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
@dataclass(frozen=True)
class ListValidation:
    when: Condition
    message: str
```

Declared SP list validation (ValidationFormula/ValidationMessage).

Cross-column: unlike `column_validation`, the condition may name any
column on the list. Authored as a condition tree. The raw `formula:`
key is gone, because it was the last surface where an author wrote
SharePoint syntax by hand and so the last place the quoting and
operator differences between the targets could bite them.

### `RetiredColumn`

```python
@dataclass(frozen=True)
class RetiredColumn:
    column: str
    retired: str = ''
    superseded_by: str | None = None
    reason: str = ''
    hide_existing: bool = False
```

One retired column (mapping `retired_columns:` section).

Retirement is a deployment-lifecycle fact, not a logical-model one: the
column stays declared in the DBML and keeps its data (deleting the
declaration would leave a live, deletable column the schema no longer
knows about, which the generated `_UserAddedColumns.pq` drift audit
would report forever), but it leaves the New form and every declared
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
@dataclass(frozen=True)
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
@dataclass(frozen=True)
class CustomPermissionLevel:
    name: str
    description: str
    base_permissions: list[str]
    renamed_from: tuple[str, ...] = ()
    previous_names: tuple[str, ...] = ()
```

A custom permission level to create at the site.

### `SiteGroup`

```python
@dataclass(frozen=True)
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
    enroll_enterprise_reader: bool = False
    renamed_from: tuple[str, ...] = ()
    previous_names: tuple[str, ...] = ()
```

A SharePoint site group to create at the site.

### `Principal`

```python
@dataclass(frozen=True)
class Principal:
    kind: PrincipalKind
    name: str | None = None
```

A role-assignment target.

`kind` is a `PrincipalKind` -- the members are on that type and are not
listed again here, because a docstring enumerating a closed vocabulary is
a copy of it that no reader can tell has gone stale. `group` means a named
site group, custom or built-in like 'Site Owners'; the three
`associated_*` kinds resolve through the site's own owner/member/visitor
group endpoints.

`name` is required for kind=group, ignored otherwise.

### `RoleAssignment`

```python
@dataclass(frozen=True)
class RoleAssignment:
    principal: Principal
    level: str
```

RoleAssignment(principal: dbml_sharepoint.model.mapping_types.Principal, level: str)

### `ListPermissionPolicy`

```python
@dataclass(frozen=True)
class ListPermissionPolicy:
    break_inheritance: bool
    assignments: list[dbml_sharepoint.model.mapping_types.RoleAssignment]
    reconcile_mode: ReconcileMode = 'configured'
```

ListPermissionPolicy(break_inheritance: bool, assignments: list[dbml_sharepoint.model.mapping_types.RoleAssignment], reconcile_mode: ReconcileMode = 'configured')

### `PermissionsConfig`

```python
@dataclass
class PermissionsConfig:
    levels: list[dbml_sharepoint.model.mapping_types.CustomPermissionLevel]
    groups: list[dbml_sharepoint.model.mapping_types.SiteGroup]
    default_policy: dbml_sharepoint.model.mapping_types.ListPermissionPolicy | None
    overrides: dict[str, dbml_sharepoint.model.mapping_types.ListPermissionPolicy]
    default_policy_site_role: str | None = None
```

PermissionsConfig(levels: list[dbml_sharepoint.model.mapping_types.CustomPermissionLevel], groups: list[dbml_sharepoint.model.mapping_types.SiteGroup], default_policy: dbml_sharepoint.model.mapping_types.ListPermissionPolicy | None, overrides: dict[str, dbml_sharepoint.model.mapping_types.ListPermissionPolicy], default_policy_site_role: str | None = None)

### `ReportingOptions`

```python
@dataclass(frozen=True)
class ReportingOptions:
    system_columns: bool = False
    users_table: bool = False
```

The `reporting:` section: what the reporting pack adds beyond the
schema's own columns. Everything defaults off, so a pack regenerated
from an unchanged mapping keeps its shape.

### `Mapping`

```python
@dataclass
class Mapping:
    prefix: str
    prefix_owner: str
    prefix_registry: str
    entities: dict[str, dbml_sharepoint.model.mapping_types.EntityMapping]
    cross_site_reference_columns: list[dbml_sharepoint.model.mapping_types.CrossSiteRef]
    versioning_default: Versioning
    versioning_overrides: dict[str, dict[str, typing.Any]]
    enum_sources: dict[str, pathlib.Path]
    watched_lists: list[dbml_sharepoint.model.mapping_types.WatchedList]
    polymorphic_patterns: list[dbml_sharepoint.model.mapping_types.PolymorphicPattern] = field(default_factory=list)
    retention_policies_source: pathlib.Path | None = None
    extension: str | None = None
    permissions: PermissionsConfig | None = None
    previous_prefixes: tuple[str, ...] = ()
    calculated_formulas: dict[str, dict[str, str]] = field(default_factory=dict)
    lookup_projections: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    form_visibility: dict[str, dbml_sharepoint.model.mapping_types.EntitySection[dbml_sharepoint.model.mapping_types.FormVisibility]] = field(default_factory=dict)
    column_validation: dict[str, dbml_sharepoint.model.mapping_types.EntitySection[dbml_sharepoint.model.mapping_types.ColumnValidation]] = field(default_factory=dict)
    views: dict[str, list[dbml_sharepoint.model.mapping_types.ViewDef]] = field(default_factory=dict)
    field_sets: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    demo_items: dict[str, list[dbml_sharepoint.model.mapping_types.DemoItem]] = field(default_factory=dict)
    display_name_mode: str | None = None
    display_name_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    reporting: ReportingOptions = field(default_factory=ReportingOptions)
    column_style_specs: dict[str, dict[str, dict[str, typing.Any]]] = field(default_factory=dict)
    column_formatting: dict[str, dict[str, dict[str, typing.Any]]] = field(default_factory=dict)
    form_formatting: dict[str, dbml_sharepoint.model.mapping_types.FormFormatting] = field(default_factory=dict)
    list_validation: dict[str, dbml_sharepoint.model.mapping_types.ListValidation] = field(default_factory=dict)
    retired_columns: dict[str, dict[str, dbml_sharepoint.model.mapping_types.RetiredColumn]] = field(default_factory=dict)
    retirement_strips: list[dbml_sharepoint.model.mapping_types.RetirementStrip] = field(default_factory=list)
    seal_columns: bool = False
    prevent_list_deletion: bool = False
    item_security_default: ItemSecurity = field(default_factory=ItemSecurity)
    item_security_overrides: dict[str, dict[str, typing.Any]] = field(default_factory=dict)
```

The full schema/sharepoint-mapping.yaml structure.

#### `Mapping.cross_site_keys`

```python
def cross_site_keys(self) -> set[tuple[str, str]]
```

`{(entity, column)}` for every declared cross-site reference.

The same three-line comprehension stood at four call sites (`jsgen`,
`reportgen` three times over, and `checks/_naming`), each turning the
list of `CrossSiteRef` into the pair set every consumer actually
wants. Nothing was wrong with any copy; a method is simply where the
shape belongs once four callers need it, and it is the fact `jsgen`
and `reportgen` MUST agree on (a column expanded into a Choice + URL
pair on one side and treated as a Lookup on the other produces a
report that expands a field the list does not have).

#### `Mapping.declares_item_read_trimming`

```python
def declares_item_read_trimming(self) -> bool
```

True when ANY list in this mapping trims reads to the caller's own
items.

Asked by the enterprise-reader rule in `checks/_permissions.py`, which
needs the mapping-wide answer rather than a per-entity one: it sees a
grant as a (level, origin) pair with no entity attached, because an
override's assignments are keyed by entity while the default's are not.

#### `Mapping.display_name_for`

```python
def display_name_for(self, entity_name: str, column_name: str) -> str
```

Display title for a rendered column: override, else auto-split
PascalCase when mode is auto, else the internal name unchanged.

#### `Mapping.entity`

```python
def entity(self, name: str) -> dbml_sharepoint.model.mapping_types.EntityMapping
```

#### `Mapping.is_retired`

```python
def is_retired(self, entity_name: str, column_name: str) -> bool
```

True when `retired_columns` declares this column for this entity.

#### `Mapping.item_security_for`

```python
def item_security_for(self, entity_name: str) -> dbml_sharepoint.model.mapping_types.ItemSecurity
```

The item-level trimming this entity's list is provisioned with.

The per-entity override merged onto the default, key by key, the same
way `versioning_for` merges: an override naming only `read` keeps the
default's `write`.

#### `Mapping.permissions_for_entity`

```python
def permissions_for_entity(self, entity_name: str) -> 'ListPermissionPolicy | None'
```

Return the per-list permission policy for the given entity name.

Returns override if present, else the default policy, but the default
only applies when its site-role scope (if any) matches the entity's
site_role. A default scoped to one role must not re-ACL lists
belonging to another role.

#### `Mapping.previous_titles`

```python
def previous_titles(self, entity_name: str) -> list[tuple[str, str]]
```

Every title this list may be found under on a site that has not
migrated, each paired with the entity name whose marker it must carry.

Order: the current prefix with each previous name, then each previous
prefix with the current name and each previous name. The current
title is never a candidate, and nothing is listed twice.

#### `Mapping.projections_for`

```python
def projections_for(self, entity_name: str, column_name: str) -> list[str]
```

Projected target columns for a lookup column, empty when none.

The lookup shape for `lookup_projections`. Consumers must agree on
the projected field's generated internal name; `jsgen` and `reportgen`
both derive it as ``f"{column}{target}"``, so a projection only ever
adds columns, never renames the lookup itself.

#### `Mapping.versioning_for`

```python
def versioning_for(self, entity_name: str) -> dbml_sharepoint.model.mapping_types.Versioning
```

The versioning settings this entity's list is provisioned with.

The per-entity override merged onto the default, key by key: an
override block naming only `major_version_limit` keeps the default's
two booleans. THE one merge: `jsgen`, `reportgen` and `assessgen`
each re-derived it, and the third did so with bare truthiness and no
default fallback, which is the divergence a shared accessor removes
rather than merely tidies.

`Mapping` already had this shape for permissions
(`permissions_for_entity`); versioning was the missing fifth
accessor.

Overrides are still stored RAW (`dict[str, Any]`), because
`mapping_loader` validates their values without narrowing their
types; the coercions here are the ones the three call sites were
each performing.

### `RetentionPolicy`

```python
@dataclass(frozen=True)
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
    retention_policies: dict[str, dbml_sharepoint.model.mapping_types.RetentionPolicy]
    retention_list_defaults: dict[str, str]
    extension_configs: dict[str, dict[str, typing.Any]] = field(default_factory=dict)
    source_paths: dict[str, pathlib.Path] = field(default_factory=dict)
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

