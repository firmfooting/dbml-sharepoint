# src/dbml_sharepoint/model/mapping_types.py
"""The shapes a mapping.yaml parses into.

Declarations only: every dataclass the loader produces, the closed
vocabularies they are constrained to, and the few pure helpers that derive
one field from another. No parsing and no file access live here, so a
reader answering "what does this section become?" does not have to read the
parser to find out.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, get_args

from dbml_sharepoint.model.conditions import Condition

# Closed vocabularies as Literal types: the loader is the ONE gate that
# admits these strings, so everything downstream (generators, reporting,
# comparisons like kind == "DocumentLibrary") type-checks against the
# real value set instead of trusting a comment.
type EntityKind = Literal["List", "DocumentLibrary", "HubOnlyList"]
type SortDirection = Literal["asc", "desc"]
type PrincipalKind = Literal[
    "group",
    "associated_owner_group",
    "associated_member_group",
    "associated_visitor_group",
]
type ReconcileMode = Literal["configured", "exact"]

ENTITY_KINDS: frozenset[str] = frozenset(get_args(EntityKind.__value__))

#: Derived from the `Literal` above for the same reason `ENTITY_KINDS` is:
#: `mapping_loader` needs a runtime set to admit a raw YAML string against,
#: and it had a hand-restated `frozenset` of the same four names one screen
#: from a `Literal` that already held them -- plus the four names AGAIN as
#: literal text in the error message, and a fourth copy in `Principal`'s
#: docstring. A fifth principal kind added to the type would have type-checked
#: everywhere and been refused at load.
PRINCIPAL_KINDS: frozenset[str] = frozenset(get_args(PrincipalKind.__value__))

#: The same vocabulary spelled for a human to read, so an error message
#: naming the legal values cannot list a different four from the ones the
#: gate accepts. Same pattern as `typemap.CALCULATED_TYPE_LIST`.
PRINCIPAL_KIND_LIST = ", ".join(repr(kind) for kind in sorted(PRINCIPAL_KINDS))

# Word boundaries for display-name auto mode: break before an uppercase that
# follows a lowercase/digit, and before the LAST capital of an acronym run
# ("RiskIDNumber" -> "Risk ID Number").
_DISPLAY_WORD_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


# Appended to a retired column's display title. Deliberately a constant and
# not configurable: "retired" must read identically on every list in every
# template, and the suffixed title participates in the per-entity
# display-title uniqueness check like any other.
RETIRED_SUFFIX = " (retired)"


def auto_display_name(internal_name: str) -> str:
    """Human-readable display title derived from a PascalCase internal name."""
    return _DISPLAY_WORD_BREAK.sub(" ", internal_name)


def view_url_slug(title: str) -> str:
    """URL-safe view page name derived from the declared view title.

    A view's .aspx file name is fixed at creation from its Title, so views
    are created with this slug and renamed to the declared title afterwards
    ("Open by score" lives at OpenByScore.aspx, not Open%20by%20score.aspx,
    the same create-then-rename trick fields use for display titles)."""
    words = re.split(r"[^A-Za-z0-9]+", title)
    return "".join(w[:1].upper() + w[1:] for w in words if w)


@dataclass(frozen=True)
class EntityMapping:
    """SP physical mapping for one entity (kind, base template, site role)."""

    name: str
    kind: EntityKind
    base_template: int
    site_role: str      # any labels you choose, e.g. default | admin
    singleton: bool = False
    # The column a lookup INTO this entity should display (SP LookupField). A SP
    # list has one primary display field; declare it here when it is not the
    # built-in "Title" (e.g. Membership uses DisplayName). Absent -> "Title".
    display_column: str | None = None
    # The author's deliberate acceptance that this entity's display column is
    # calculated, and therefore cannot be indexed, so a lookup into this list
    # stops being settable once it passes ~5,000 items. Legitimate for a list
    # that will stay small. Silences the warning completely; the acceptance is
    # visible here, where a reviewer sees it.
    accept_unindexable_display_column: bool = False
    # Columns the GENERATED `All Items` view must not render. The only reason
    # accepted is the list view LOOKUP threshold: an entity may legitimately
    # carry more than 12 join-bearing columns while no declared view needs that
    # many, and without this the build refuses a schema over a view nobody
    # wrote. Every named column must be join-bearing and rendered (see
    # analysis/checks/_views.py) because `All Items` renders everything for a
    # reason and this is not a general hide-this feature. Declared views are
    # unaffected; they keep every field they declare.
    hide_from_all_items: tuple[str, ...] = ()
    # Previous entity names this list was deployed under. When no list carries
    # the current title, the deploy adopts one carrying a previous title and
    # the exact provenance marker for that previous name, then retitles it.
    # A previous title without that marker, or present beside the current
    # one, is refused at assessment and at preflight.
    renamed_from: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossSiteRef:
    """A column to expand into the Choice + URL cross-site triple."""

    entity: str
    column: str


@dataclass(frozen=True)
class PolymorphicPattern:
    """A polymorphic column pattern.

    ``list`` is the unprefixed entity name whose ``field`` holds a logical FK
    discriminated by ``discriminator``. Referential integrity is not enforced
    by SharePoint; the manifest surfaces these so downstream flows validate
    them at write time.
    """

    list: str
    field: str
    discriminator: str


@dataclass(frozen=True)
class Versioning:
    """SP list versioning settings, defaults included.

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
    """

    # THE THREE DEFAULTS ARE THE LOADER'S. Each is what `mapping_loader`
    # substitutes when `versioning.default` omits the key, so the dataclass
    # and the parser cannot disagree about what an unstated setting means --
    # the loader reads these attributes rather than restating the values.
    #
    # `enable_versioning` defaults ON, which is NOT SharePoint's own default.
    # It is this tool's: `_strict_bool` has always treated an absent flag as
    # true, and every shipped mapping declares versioning on. Changing it is
    # a behaviour change to every mapping that omits the key, not a tidy-up.
    enable_versioning: bool = True
    major_version_limit: int = 500
    enable_minor_versions: bool = False


@dataclass(frozen=True)
class WatchedList:
    """A (entity, column) pair watched by W10 status capture."""

    entity: str
    column: str


@dataclass(frozen=True)
class FormVisibility:
    """One column's declared form behaviour.

    `existing` covers the Edit form AND the Display form, which SharePoint
    does not let us separate. The modern Display form reads ShowInEditForm
    and ignores ShowInDisplayForm entirely. The key is named for what it
    does rather than for the form an author might expect.
    """

    new: bool = True
    existing: bool = True
    when: "Condition | None" = None


@dataclass(frozen=True)
class ColumnValidation:
    """One column's save-time rule. The message is the feature: without it
    a failed save shows SharePoint's generic text, which tells the person
    filling in the form nothing."""

    when: "Condition"
    message: str


@dataclass(frozen=True)
class EntitySection[T]:
    """A per-entity block of column declarations plus its reconcile mode.

    `exact` (the default) makes the declaration authoritative for the whole
    entity: a column with no entry has its value cleared, so deployed state
    is a function of the declaration rather than of declaration history.
    `declared` touches only what is listed, for mappings running
    seal_columns: false where an operator may have set something by hand.
    """

    reconcile: str = "exact"
    columns: dict[str, T] = field(default_factory=dict)


@dataclass(frozen=True)
class ViewSort:
    """One <OrderBy> entry of a declared view."""

    field: str
    direction: SortDirection  # enforced structurally at load


@dataclass(frozen=True)
class ViewGroupBy:
    """The <GroupBy> of a declared view.

    SharePoint groups by up to two levels. Authoring accepts `field:` for
    one or `fields:` for one or two; both land here as a list, because two
    accessors for one concept is how the two drift apart.
    """

    fields: list[str]
    collapsed: bool = False


@dataclass(frozen=True)
class ViewDef:
    """One declared SharePoint list view (mapping `views:` section)."""

    title: str
    fields: list[str]
    # Prior managed titles accepted during a one-way rename migration. A
    # matching live view is adopted and reconciled under `title`; aliases are
    # never created and must remain declared so old sites can still upgrade.
    renamed_from: list[str] = field(default_factory=list)
    default: bool = False
    # A condition tree from the shared grammar; None when undeclared.
    where: Condition | None = None
    sort: list[ViewSort] = field(default_factory=list)
    group_by: ViewGroupBy | None = None
    row_limit: int | None = None
    # Optional SP row-formatting JSON (SP.View.CustomFormatter); None = the
    # live property is never touched.
    formatting: dict[str, Any] | None = None
    # Optional per-column pixel widths, INTERNAL names (jsgen rewrites to
    # display titles; SP's ColumnWidth binds by display name). Empty = the
    # live widths are never touched.
    widths: dict[str, int] = field(default_factory=dict)
    # Optional per-column aggregations, INTERNAL names, values from
    # typemap.TOTAL_FUNCTIONS. Empty = the live Aggregations property is
    # never touched, matching widths and formatting, so DELETING a totals
    # block does not remove a total from an already-deployed view.
    totals: dict[str, str] = field(default_factory=dict)
    # The `field_sets` entries this view's `fields` was expanded from, in
    # reference order, de-duplicated. Populated by _expand_field_sets at
    # load; empty when the view named its columns directly. The manifest
    # prints it as the footnote on the RESOLVED field list, and the
    # validator uses it to warn about a declared set no view references.
    expanded_sets: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class DemoItem:
    """One declared demo/sample row (mapping `demo_items:` section).

    `values` are authored with INTERNAL column names. The value grammar
    ("@me" (deploying operator) on person columns, "today+N"/"today-N" on
    date columns, {demo_ref: key} on lookups) is resolved by the generated
    demo-data.js at RUN time; semantic rules live in the validator. Every
    Title must start with the configured demo prefix so sample data is visible
    in every view and form. Rollback requires per-list confirmation before every delete."""

    key: str
    values: dict[str, Any]


@dataclass(frozen=True)
class FormFormatting:
    """Declared list-form layout parts (SP ClientFormCustomFormatter).

    Each part is a formatter JSON object; at least one must be declared.
    Body section field lists are authored with INTERNAL names; jsgen
    rewrites them to display titles (SP matches form fields by display)."""

    header: dict[str, Any] | None = None
    body: dict[str, Any] | None = None
    footer: dict[str, Any] | None = None


@dataclass(frozen=True)
class ListValidation:
    """Declared SP list validation (ValidationFormula/ValidationMessage).

    Cross-column: unlike `column_validation`, the condition may name any
    column on the list. Authored as a condition tree. The raw `formula:`
    key is gone, because it was the last surface where an author wrote
    SharePoint syntax by hand and so the last place the quoting and
    operator differences between the targets could bite them.
    """

    when: "Condition"
    message: str


@dataclass(frozen=True)
class RetiredColumn:
    """One retired column (mapping `retired_columns:` section).

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
    """

    column: str
    retired: str = ""
    superseded_by: str | None = None
    reason: str = ""
    hide_existing: bool = False


@dataclass(frozen=True)
class RetirementStrip:
    """One declared reference to a retired column that `_apply_retirement`
    removed or replaced. The structure no longer carries the reference, so
    the record is kept here for the validator: retirement must never break
    a build, but a stale declaration is worth telling the author about.

    `context` is the human-readable declaration site, e.g.
    "views[Tier3Board].Last 14 days fields".
    """

    entity: str
    column: str
    context: str


@dataclass(frozen=True)
class CustomPermissionLevel:
    """A custom permission level to create at the site."""

    name: str
    description: str
    base_permissions: list[str]


@dataclass(frozen=True)
class SiteGroup:
    """A SharePoint site group to create at the site."""

    name: str
    description: str
    owner_group: str
    allow_members_edit_membership: bool
    allow_request_to_join_leave: bool
    auto_accept_request_to_join_leave: bool
    only_allow_members_view_membership: bool
    # Optional clean-provision gate. When true, deploy.js proves the reconciled
    # group has no members during Phase 1.3 and aborts before list creation if it
    # does. False preserves the existing, non-destructive membership behaviour.
    require_empty_at_deploy: bool = False
    # Optional operator self-enrolment. When true, deploy.js adds the running
    # operator to this group after Phase 1.3 (so later phases hold the group's
    # list grants, e.g. an empty-by-default Full Control admin group) and
    # removes them again at the end of the run, unless they were already a
    # member, in which case membership is left untouched.
    enroll_operator_during_deploy: bool = False
    # Optional enterprise-reader enrolment target. When true, `build
    # --enterprise-reader <upn>` adds that ONE named account to this group in
    # Phase 1.5 and LEAVES IT THERE -- unlike operator enrolment above, which
    # is undone at the end of the run. Membership is otherwise operator-owned:
    # the deploy adds, verifies, and never removes anyone.
    enroll_enterprise_reader: bool = False


@dataclass(frozen=True)
class Principal:
    """A role-assignment target.

    `kind` is a `PrincipalKind` -- the members are on that type and are not
    listed again here, because a docstring enumerating a closed vocabulary is
    a copy of it that no reader can tell has gone stale. `group` means a named
    site group, custom or built-in like 'Site Owners'; the three
    `associated_*` kinds resolve through the site's own owner/member/visitor
    group endpoints.

    `name` is required for kind=group, ignored otherwise.
    """

    kind: PrincipalKind
    name: str | None = None


@dataclass(frozen=True)
class RoleAssignment:
    principal: Principal
    level: str   # built-in name or custom level name


@dataclass(frozen=True)
class ListPermissionPolicy:
    break_inheritance: bool
    assignments: list[RoleAssignment]
    # configured: reconcile stale role levels only for declared principals.
    # exact: treat declared principal/role pairs as an allowlist and remove
    # every other direct role binding (except SharePoint's derived Limited
    # Access binding). Exact is the recommended fail-closed baseline.
    reconcile_mode: ReconcileMode = "configured"


@dataclass
class PermissionsConfig:
    levels: list[CustomPermissionLevel]
    groups: list[SiteGroup]
    default_policy: ListPermissionPolicy | None
    overrides: dict[str, ListPermissionPolicy]
    # Optional site-role scope for default_policy (from
    # list_permissions.default.site_role). When set, the default applies only
    # to entities of that site_role; None means every entity. Overrides are
    # explicit per-entity and are never scope-filtered.
    default_policy_site_role: str | None = None


@dataclass(frozen=True)
class ReportingOptions:
    """The `reporting:` section: what the reporting pack adds beyond the
    schema's own columns. Everything defaults off, so a pack regenerated
    from an unchanged mapping keeps its shape."""

    # Created By, Created, Modified By and Modified on every list query,
    # SQL view and dictionary entry.
    system_columns: bool = False
    # A `_Users.pq` dimension over the site's user information list, and a
    # `... Key` on every person column that joins it.
    users_table: bool = False


@dataclass
class Mapping:
    """The full schema/sharepoint-mapping.yaml structure."""

    prefix: str
    prefix_owner: str
    prefix_registry: str
    entities: dict[str, EntityMapping]
    cross_site_reference_columns: list[CrossSiteRef]
    versioning_default: Versioning
    versioning_overrides: dict[str, dict[str, Any]]
    enum_sources: dict[str, Path]
    watched_lists: list[WatchedList]
    polymorphic_patterns: list[PolymorphicPattern] = field(default_factory=list)
    retention_policies_source: Path | None = None
    extension: str | None = None
    permissions: "PermissionsConfig | None" = None
    # {entity: {column: formula}} for calculated_text/calculated_number
    # columns (SP.FieldCalculated). Formulas stay out of DBML (pydbml has no
    # attribute to carry them); the validator enforces the pairing.
    calculated_formulas: dict[str, dict[str, str]] = field(default_factory=dict)
    # {entity: {column: (target columns)}} for a lookup column's additional
    # projected (dependent) fields. Each target column is projected onto the
    # source list as a read-only Lookup whose ShowField is that target column,
    # linked back to the primary lookup by its FieldRef. This is how a view
    # shows a target's real Title while the picker shows a calculated display
    # column (e.g. LiveRiskTitle). See analysis/joins.py for why projections
    # are join-free, and test/manual/projected-lookup-probe.js for the
    # createfieldasxml shape that proves the linkage is scriptable.
    lookup_projections: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    # {entity: EntitySection[FormVisibility]} (declared form behaviour).
    form_visibility: dict[str, EntitySection[FormVisibility]] = field(default_factory=dict)
    # {entity: EntitySection[ColumnValidation]} (per-column save rules).
    column_validation: dict[str, EntitySection[ColumnValidation]] = field(
        default_factory=dict,
    )
    # {entity: [ViewDef]} (declared list views). Semantic rules (field
    # existence, operator allowlist, single default) live in the validator.
    views: dict[str, list[ViewDef]] = field(default_factory=dict)
    # {entity: {set name: [columns]}} (named, reusable column lists that a
    # view's `fields` pulls in with "@setname"). Expanded into ViewDef.fields
    # at load time (see _expand_field_sets); retained here as the
    # authoritative declaration for the manifest footnote and the
    # validator's unreferenced-set warning.
    field_sets: dict[str, dict[str, list[str]]] = field(default_factory=dict)
    # {entity: [DemoItem]} (declared demo/sample rows), emitted as
    # demo-data.js ONLY when the build passes --seed. Empty = feature off.
    demo_items: dict[str, list[DemoItem]] = field(default_factory=dict)
    # display_names section: internal names stay authoritative; display
    # titles are renamed after create. mode "auto" splits PascalCase, with
    # {entity: {column: "Display"}} overrides winning. None = feature off.
    display_name_mode: str | None = None
    display_name_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    # reporting section: switches for the generated reporting pack.
    reporting: ReportingOptions = field(default_factory=ReportingOptions)
    # Raw style specs (dicts with a 'style' key) as declared, kept beside
    # the expanded formatter JSON so the validator can check map keys
    # against enum members after load-time expansion.
    column_style_specs: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # {entity: {column: formatter-JSON dict}}, SP CustomFormatter, declared
    # per column. Reconciled as a mutable field property; absent = the live
    # property is never touched.
    column_formatting: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # {entity: FormFormatting} (declared list-form layouts). Absent = the
    # live content type's form formatter is never touched.
    form_formatting: dict[str, FormFormatting] = field(default_factory=dict)
    # {entity: ListValidation} (save-time enforcement). Absent = untouched.
    list_validation: dict[str, ListValidation] = field(default_factory=dict)
    # {entity: {column: RetiredColumn}}, the authoritative retirement
    # record. _apply_retirement folds these into form_visibility,
    # display_name_overrides, each ViewDef and each form body at load time;
    # the dict itself is retained for the manifest, the data dictionary and
    # the validator.
    retired_columns: dict[str, dict[str, RetiredColumn]] = field(default_factory=dict)
    # References to retired columns that _apply_retirement removed or
    # replaced, kept so the validator can warn about declarations the fold
    # silently rewrote.
    retirement_strips: list[RetirementStrip] = field(default_factory=list)
    # UI hardening (friction, not enforcement; site admins can undo via
    # API): seal every deployed column (blocks UI schema edits even for
    # admins; the deployer unseals for its own runs) and block UI deletion
    # of the list objects.
    seal_columns: bool = False
    prevent_list_deletion: bool = False

    def display_name_for(self, entity_name: str, column_name: str) -> str:
        """Display title for a rendered column: override, else auto-split
        PascalCase when mode is auto, else the internal name unchanged."""
        if self.display_name_mode != "auto":
            return column_name
        override = self.display_name_overrides.get(entity_name, {}).get(column_name)
        return override if override is not None else auto_display_name(column_name)

    def is_retired(self, entity_name: str, column_name: str) -> bool:
        """True when `retired_columns` declares this column for this entity."""
        return column_name in self.retired_columns.get(entity_name, {})

    def entity(self, name: str) -> EntityMapping:
        if name not in self.entities:
            raise KeyError(f"Unknown entity in mapping: {name!r}")
        return self.entities[name]

    def cross_site_keys(self) -> set[tuple[str, str]]:
        """`{(entity, column)}` for every declared cross-site reference.

        The same three-line comprehension stood at four call sites (`jsgen`,
        `reportgen` three times over, and `checks/_naming`), each turning the
        list of `CrossSiteRef` into the pair set every consumer actually
        wants. Nothing was wrong with any copy; a method is simply where the
        shape belongs once four callers need it, and it is the fact `jsgen`
        and `reportgen` MUST agree on (a column expanded into a Choice + URL
        pair on one side and treated as a Lookup on the other produces a
        report that expands a field the list does not have).
        """
        return {
            (xref.entity, xref.column)
            for xref in self.cross_site_reference_columns
        }

    def projections_for(self, entity_name: str, column_name: str) -> list[str]:
        """Projected target columns for a lookup column, empty when none.

        The lookup shape for `lookup_projections`. Consumers must agree on
        the projected field's generated internal name; `jsgen` and `reportgen`
        both derive it as ``f"{column}{target}"``, so a projection only ever
        adds columns, never renames the lookup itself.
        """
        return list(self.lookup_projections.get(entity_name, {}).get(column_name, ()))

    def versioning_for(self, entity_name: str) -> Versioning:
        """The versioning settings this entity's list is provisioned with.

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
        """
        override = self.versioning_overrides.get(entity_name, {})
        default = self.versioning_default
        return Versioning(
            enable_versioning=bool(
                override.get("enable_versioning", default.enable_versioning),
            ),
            major_version_limit=int(
                override.get("major_version_limit", default.major_version_limit),
            ),
            enable_minor_versions=bool(
                override.get("enable_minor_versions", default.enable_minor_versions),
            ),
        )

    def permissions_for_entity(self, entity_name: str) -> "ListPermissionPolicy | None":
        """Return the per-list permission policy for the given entity name.

        Returns override if present, else the default policy, but the default
        only applies when its site-role scope (if any) matches the entity's
        site_role. A default scoped to one role must not re-ACL lists
        belonging to another role.
        """
        if self.permissions is None:
            return None
        if entity_name in self.permissions.overrides:
            return self.permissions.overrides[entity_name]
        scope = self.permissions.default_policy_site_role
        if scope is not None:
            entity = self.entities.get(entity_name)
            if entity is None or entity.site_role != scope:
                return None
        return self.permissions.default_policy


@dataclass(frozen=True)
class RetentionPolicy:
    """One policy from config/retention-policies.yaml."""

    name: str
    description: str
    sp_label: str
    retain_years: int | None
    retain_days: int | None
    trigger: str


@dataclass
class MappingBundle:
    """Mapping + the generic configs it references, all loaded."""

    mapping: Mapping
    enum_choices: dict[str, list[str]]
    retention_policies: dict[str, RetentionPolicy]
    retention_list_defaults: dict[str, str]
    # The FULL `extensions: {<name>: {...}}` map, untyped passthrough.
    # Selection is by RESOLVED extension name via
    # extension_config_for(), not pre-selected at load time: the active
    # extension may come from the CLI `--extension` override rather than the
    # mapping's own `extension:` key.
    extension_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    source_paths: dict[str, Path] = field(default_factory=dict)

    def extension_config_for(self, name: str | None) -> dict[str, Any]:
        """The named extension's config block; {} when name is None or the
        mapping declares no block for it. Extensions should call this with
        their own ``name`` so config selection always matches the extension
        actually running, regardless of how it was resolved."""
        if name is None:
            return {}
        return self.extension_configs.get(name, {})


# Sections that once existed and are now rejected by name, so a mapping
# carrying one gets a migration message instead of the generic unknown-key
# error. Kept as data because the allow-list is asserted against the
# loader's readers, and these have no reader by design.
_REMOVED_SECTIONS: dict[str, str] = {
    "indexed_columns": (
        "DBML table indexes. Move each mapped column into its table declaration:\n"
        "\n"
        "    Table <Entity> {\n"
        "      <Column> nvarchar\n"
        "\n"
        "      indexes {\n"
        "        <Column>\n"
        "      }\n"
        "    }"
    ),
    "hidden_on_forms": (
        "form_visibility. A column listed there becomes:\n"
        "\n"
        "    form_visibility:\n"
        "      <Entity>:\n"
        "        columns:\n"
        "          <Column>: hidden\n"
        "\n"
        "The `columns:` level is required."
    ),
    "hidden_on_display": (
        "nothing -- it never worked on modern lists, which read ShowInEditForm and "
        "ignore ShowInDisplayForm, so the setting was written, verified and had no "
        "effect. Hide from the Edit form instead, accepting that this hides the "
        "column from Display too:\n"
        "\n"
        "    form_visibility:\n"
        "      <Entity>:\n"
        "        columns:\n"
        "          <Column>: hidden\n"
    ),
}
