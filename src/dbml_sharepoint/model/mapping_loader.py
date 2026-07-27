# src/dbml_sharepoint/model/mapping_loader.py
"""Loader for schema/sharepoint-mapping.yaml plus its referenced config YAMLs.

Generic core loader. Resolves relative config paths
(enum_sources values, retention_policies_source) relative to the mapping
YAML's own directory, so the deployer can be invoked from any working
directory. Project-specific config lives under `extensions: {<name>: {...}}`
and is passed through untyped as `MappingBundle.extension_configs` — this
module knows nothing about what any particular extension's block means, and
selection by name is deferred to `MappingBundle.extension_config_for` so it
honors the RESOLVED extension (a CLI `--extension` override may differ from
the mapping's own `extension:` key).
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml

from dbml_sharepoint.analysis import styles
from dbml_sharepoint.model.conditions import Condition, parse_condition

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

# Word boundaries for display-name auto mode: break before an uppercase that
# follows a lowercase/digit, and before the LAST capital of an acronym run
# ("RiskIDNumber" -> "Risk ID Number").
_DISPLAY_WORD_BREAK = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def auto_display_name(internal_name: str) -> str:
    """Human-readable display title derived from a PascalCase internal name."""
    return _DISPLAY_WORD_BREAK.sub(" ", internal_name)


def view_url_slug(title: str) -> str:
    """URL-safe view page name derived from the declared view title.

    A view's .aspx file name is fixed at creation from its Title, so views
    are created with this slug and renamed to the declared title afterwards
    ("Open by score" lives at OpenByScore.aspx, not Open%20by%20score.aspx —
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
    # built-in "Title" (e.g. Membership uses DisplayName). Absent → "Title".
    display_column: str | None = None


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
    """Default SP list versioning settings."""

    enable_versioning: bool
    major_version_limit: int
    enable_minor_versions: bool


@dataclass(frozen=True)
class WatchedList:
    """A (entity, column) pair watched by W10 status capture."""

    entity: str
    column: str


@dataclass(frozen=True)
class FormVisibility:
    """One column's declared form behaviour.

    `existing` covers the Edit form AND the Display form, which SharePoint
    does not let us separate — the modern Display form reads ShowInEditForm
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
    """The <GroupBy> of a declared view."""

    field: str
    collapsed: bool = False


@dataclass(frozen=True)
class ViewDef:
    """One declared SharePoint list view (mapping `views:` section)."""

    title: str
    fields: list[str]
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
    # display titles — SP's ColumnWidth binds by display name). Empty = the
    # live widths are never touched.
    widths: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class DemoItem:
    """One declared demo/sample row (mapping `demo_items:` section).

    `values` are authored with INTERNAL column names. The value grammar —
    "@me" (deploying operator) on person columns, "today+N"/"today-N" on
    date columns, {demo_ref: key} on lookups — is resolved by the generated
    demo-data.js at RUN time; semantic rules live in the validator. Every
    Title must start with "[DEMO] ": that marker is what the teardown
    trusts to distinguish demo rows from real records."""

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
    column on the list. Authored as a condition tree — the raw `formula:`
    key is gone, because it was the last surface where an author wrote
    SharePoint syntax by hand and so the last place the quoting and
    operator differences between the targets could bite them.
    """

    when: "Condition"
    message: str


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
    # group has no members during Phase 1.2 and aborts before list creation if it
    # does. False preserves the existing, non-destructive membership behaviour.
    require_empty_at_deploy: bool = False
    # Optional operator self-enrolment. When true, deploy.js adds the running
    # operator to this group after Phase 1.2 (so later phases hold the group's
    # list grants, e.g. an empty-by-default Full Control admin group) and
    # removes them again at the end of the run — unless they were already a
    # member, in which case membership is left untouched.
    enroll_operator_during_deploy: bool = False


@dataclass(frozen=True)
class Principal:
    """A role-assignment target. `kind` is one of:
    'group' (a named site group, custom or built-in like 'Site Owners'),
    'associated_owner_group', 'associated_member_group', 'associated_visitor_group'.
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


@dataclass
class Mapping:
    """The full schema/sharepoint-mapping.yaml structure."""

    prefix: str
    prefix_owner: str
    prefix_registry: str
    entities: dict[str, EntityMapping]
    cross_site_reference_columns: list[CrossSiteRef]
    indexed_columns: dict[str, list[str]]
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
    # {entity: EntitySection[FormVisibility]} — declared form behaviour.
    form_visibility: dict[str, EntitySection[FormVisibility]] = field(default_factory=dict)
    # {entity: EntitySection[ColumnValidation]} — per-column save rules.
    column_validation: dict[str, EntitySection[ColumnValidation]] = field(
        default_factory=dict,
    )
    # {entity: [ViewDef]} — declared list views. Semantic rules (field
    # existence, operator allowlist, single default) live in the validator.
    views: dict[str, list[ViewDef]] = field(default_factory=dict)
    # {entity: [DemoItem]} — declared demo/sample rows, emitted as
    # demo-data.js ONLY when the build passes --seed. Empty = feature off.
    demo_items: dict[str, list[DemoItem]] = field(default_factory=dict)
    # display_names section: internal names stay authoritative; display
    # titles are renamed after create. mode "auto" splits PascalCase, with
    # {entity: {column: "Display"}} overrides winning. None = feature off.
    display_name_mode: str | None = None
    display_name_overrides: dict[str, dict[str, str]] = field(default_factory=dict)
    # Raw style specs (dicts with a 'style' key) as declared, kept beside
    # the expanded formatter JSON so the validator can check map keys
    # against enum members after load-time expansion.
    column_style_specs: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # {entity: {column: formatter-JSON dict}} — SP CustomFormatter, declared
    # per column. Reconciled as a mutable field property; absent = the live
    # property is never touched.
    column_formatting: dict[str, dict[str, dict[str, Any]]] = field(default_factory=dict)
    # {entity: FormFormatting} — declared list-form layouts. Absent = the
    # live content type's form formatter is never touched.
    form_formatting: dict[str, FormFormatting] = field(default_factory=dict)
    # {entity: ListValidation} — save-time enforcement. Absent = untouched.
    list_validation: dict[str, ListValidation] = field(default_factory=dict)
    # {entity: [columns]} hidden from NEW and EDIT forms (display form keeps
    # them for audit). For auto-stamped columns with declared defaults.
    # {entity: [columns]} hidden from the DISPLAY form too — for system
    # scores that belong in views, not on the item form. Calculated columns
    # are valid here (they render on display, never on new/edit).
    # UI hardening (friction, not enforcement — site admins can undo via
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

    def entity(self, name: str) -> EntityMapping:
        if name not in self.entities:
            raise KeyError(f"Unknown entity in mapping: {name!r}")
        return self.entities[name]

    def permissions_for_entity(self, entity_name: str) -> "ListPermissionPolicy | None":
        """Return the per-list permission policy for the given entity name.

        Returns override if present, else the default policy — but the default
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


def load_mapping(mapping_path: Path) -> MappingBundle:
    """Load the mapping YAML and the referenced configs into a single bundle."""
    mapping_path = mapping_path.resolve()
    raw = _load_yaml(mapping_path)

    base_dir = mapping_path.parent

    entities = {
        name: EntityMapping(
            name=name,
            kind=_parse_entity_kind(spec.get("kind"), f"entities.{name}"),
            base_template=int(spec["base_template"]),
            site_role=spec["site_role"],
            singleton=bool(spec.get("singleton", False)),
            display_column=spec.get("display_column"),
        )
        for name, spec in raw["entities"].items()
    }

    cross_site = [
        CrossSiteRef(entity=item["entity"], column=item["column"])
        for item in raw.get("cross_site_reference_columns", [])
    ]

    polymorphic = [
        PolymorphicPattern(
            list=item["list"],
            field=item["field"],
            discriminator=item["discriminator"],
        )
        for item in raw.get("polymorphic_patterns", [])
    ]

    versioning = raw.get("versioning") or {}
    default_v = versioning.get("default") or {}
    versioning_default = Versioning(
        enable_versioning=bool(default_v.get("enable_versioning", True)),
        major_version_limit=int(default_v.get("major_version_limit", 500)),
        enable_minor_versions=bool(default_v.get("enable_minor_versions", False)),
    )

    watched = [
        WatchedList(entity=item["entity"], column=item["column"])
        for item in raw.get("watched_lists", [])
    ]

    enum_choices, enum_source_paths = _load_enum_choices(
        base_dir, raw.get("enum_sources") or {},
    )

    retention_source = raw.get("retention_policies_source")
    retention_path = (base_dir / retention_source).resolve() if retention_source else None
    if retention_path is not None:
        retention_policies, retention_list_defaults = _load_retention(retention_path)
    else:
        retention_policies, retention_list_defaults = {}, {}

    extension = raw.get("extension")
    extensions_block: dict[str, Any] = raw.get("extensions") or {}

    permissions_config = _parse_permissions(raw)

    # Column formatting: a dict with a 'style' key is a style spec (fleet
    # style standard, website/docs/reference/style-guide.md) expanded here
    # library; a str stays a JSON file path and a plain dict an inline
    # formatter. Raw specs are kept for the validator's enum-map checks.
    style_theme = styles.parse_theme(raw.get("style_theme"), "style_theme")
    column_formatting: dict[str, dict[str, dict[str, Any]]] = {}
    column_style_specs: dict[str, dict[str, dict[str, Any]]] = {}
    for cf_entity, cf_cols in (raw.get("column_formatting") or {}).items():
        for cf_col, cf_value in (cf_cols or {}).items():
            cf_ctx = f"column_formatting.{cf_entity}.{cf_col}"
            if isinstance(cf_value, dict) and "style" in cf_value:
                column_style_specs.setdefault(cf_entity, {})[cf_col] = dict(cf_value)
                expanded = styles.expand_style(cf_value, cf_ctx, theme=style_theme)
            else:
                expanded = _load_json_value(base_dir, cf_value, cf_ctx)
            column_formatting.setdefault(cf_entity, {})[cf_col] = expanded

    for removed, replacement in (
        ("hidden_on_forms", "form_visibility, e.g. `Column: hidden`"),
        (
            "hidden_on_display",
            "nothing — it never worked on modern lists, which read ShowInEditForm and "
            "ignore ShowInDisplayForm; hide from the Edit form instead",
        ),
    ):
        if removed in raw:
            raise ValueError(f"{removed!r} has been replaced by {replacement}")

    mapping = Mapping(
        prefix=raw["prefix"],
        prefix_owner=raw.get("prefix_owner", ""),
        prefix_registry=raw.get("prefix_registry", ""),
        entities=entities,
        cross_site_reference_columns=cross_site,
        indexed_columns={k: list(v) for k, v in (raw.get("indexed_columns") or {}).items()},
        versioning_default=versioning_default,
        versioning_overrides=dict(versioning.get("overrides") or {}),
        enum_sources=enum_source_paths,
        watched_lists=watched,
        polymorphic_patterns=polymorphic,
        retention_policies_source=retention_path,
        extension=extension,
        permissions=permissions_config,
        calculated_formulas={
            entity: {col: str(formula) for col, formula in (cols or {}).items()}
            for entity, cols in (raw.get("calculated_formulas") or {}).items()
        },
        form_visibility={
            entity: _parse_form_visibility(block, f"form_visibility.{entity}")
            for entity, block in (raw.get("form_visibility") or {}).items()
        },
        column_validation={
            entity: _parse_column_validation(block, f"column_validation.{entity}")
            for entity, block in (raw.get("column_validation") or {}).items()
        },
        views={
            entity: [
                _parse_view(item, f"views.{entity}[{i}]", base_dir)
                for i, item in enumerate(items or [])
            ]
            for entity, items in (raw.get("views") or {}).items()
        },
        demo_items={
            entity: [
                _parse_demo_item(item, f"demo_items.{entity}[{i}]")
                for i, item in enumerate(items or [])
            ]
            for entity, items in (raw.get("demo_items") or {}).items()
        },
        display_name_mode=_parse_display_name_mode(raw),
        display_name_overrides={
            entity: {col: str(name) for col, name in (cols or {}).items()}
            for entity, cols in ((raw.get("display_names") or {}).get("overrides") or {}).items()
        },
        column_formatting=column_formatting,
        column_style_specs=column_style_specs,
        form_formatting={
            entity: _parse_form_formatting(
                base_dir, parts, f"form_formatting.{entity}",
            )
            for entity, parts in (raw.get("form_formatting") or {}).items()
        },
        list_validation={
            entity: _parse_list_validation(rule, f"list_validation.{entity}")
            for entity, rule in (raw.get("list_validation") or {}).items()
        },
        seal_columns=_optional_bool(raw, "seal_columns", "mapping"),
        prevent_list_deletion=_optional_bool(raw, "prevent_list_deletion", "mapping"),
    )

    extension_configs: dict[str, dict[str, Any]] = {
        name: dict(block or {}) for name, block in extensions_block.items()
    }

    source_paths: dict[str, Path] = {
        "mapping": mapping_path,
        **{f"enum:{name}": path for name, path in enum_source_paths.items()},
    }
    if retention_path is not None:
        source_paths["retention"] = retention_path

    return MappingBundle(
        mapping=mapping,
        enum_choices=enum_choices,
        retention_policies=retention_policies,
        retention_list_defaults=retention_list_defaults,
        extension_configs=extension_configs,
        source_paths=source_paths,
    )


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file; require a top-level mapping (dict)."""
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at the top level, got {type(raw).__name__}",
        )
    return raw


def _load_enum_choices(
    base_dir: Path, enum_sources: dict[str, str],
) -> tuple[dict[str, list[str]], dict[str, Path]]:
    """Load every `enum_sources` entry into a name -> list[str] map.

    Values are `path#fragment`, where `fragment` names a
    top-level key in the target YAML and defaults to `choices` when omitted.
    Paths resolve relative to base_dir, the same rule as the other config
    sources. Returns (enum_choices, resolved_paths); the latter becomes
    Mapping.enum_sources (fragment stripped, for display/source-tracking).
    """
    choices: dict[str, list[str]] = {}
    resolved: dict[str, Path] = {}
    for name, spec in enum_sources.items():
        path_part, _, fragment = spec.partition("#")
        fragment = fragment or "choices"
        path = (base_dir / path_part).resolve()
        resolved[name] = path
        source = _load_yaml(path)
        values = source.get(fragment)
        if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
            raise ValueError(
                f"{path}: {fragment!r} must be a list of strings "
                f"(enum_sources[{name!r}])",
            )
        choices[name] = list(values)
    return choices, resolved


def _load_json_value(base_dir: Path, value: Any, context: str) -> dict[str, Any]:
    """A formatter declaration: a relative path to a JSON file (resolved
    against the mapping's directory, like enum_sources) or an inline
    mapping. Anything else — or malformed JSON — is a load error naming the
    offending declaration."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        path = (base_dir / value).resolve()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"{context}: cannot read {value!r}: {exc}") from exc
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{context}: {value!r} is not valid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ValueError(f"{context}: {value!r} must contain a JSON object")
        return parsed
    raise ValueError(
        f"{context}: expected a relative .json path or an inline mapping, "
        f"got {type(value).__name__}",
    )


def _parse_list_validation(rule: Any, context: str) -> ListValidation:
    if not isinstance(rule, dict):
        raise ValueError(f"{context}: expected a mapping with 'when' and 'message'")
    unknown = set(rule) - {"when", "message"}
    if "formula" in unknown:
        raise ValueError(
            f"{context}: 'formula' has been replaced by 'when', which takes a condition "
            f"tree instead of a SharePoint formula — see the conditions reference",
        )
    if unknown:
        raise ValueError(f"{context}: unknown key(s) {sorted(unknown)}")
    for key in ("when", "message"):
        if not rule.get(key):
            raise ValueError(f"{context}: {key!r} is required")
    return ListValidation(
        when=parse_condition(rule["when"], f"{context}.when"),
        message=str(rule["message"]),
    )


def _parse_form_formatting(base_dir: Path, parts: Any, context: str) -> FormFormatting:
    if not isinstance(parts, dict):
        raise ValueError(f"{context}: expected a mapping of header/body/footer parts")
    unknown = set(parts) - {"header", "body", "footer"}
    if unknown:
        raise ValueError(f"{context}: unknown part(s) {sorted(unknown)}")
    loaded = {
        name: _load_json_value(base_dir, value, f"{context}.{name}")
        for name, value in parts.items()
        if value is not None
    }
    if not loaded:
        raise ValueError(f"{context}: declare at least one of header/body/footer")
    return FormFormatting(
        header=loaded.get("header"),
        body=loaded.get("body"),
        footer=loaded.get("footer"),
    )


def _parse_display_name_mode(raw: dict[str, Any]) -> str | None:
    section = raw.get("display_names")
    if section is None:
        return None
    mode = section.get("mode")
    if mode != "auto":
        raise ValueError(
            f"display_names.mode must be 'auto' (got {mode!r}); omit the "
            f"display_names section to leave display titles untouched",
        )
    return "auto"



def _entity_section(block: Any, context: str) -> tuple[str, dict[str, Any]]:
    if not isinstance(block, dict):
        raise ValueError(f"{context}: expected a mapping with 'columns'")
    unknown = set(block) - {"reconcile", "columns"}
    if unknown:
        raise ValueError(f"{context}: unknown key(s) {sorted(unknown)}")
    reconcile = str(block.get("reconcile", "exact"))
    if reconcile not in ("exact", "declared"):
        raise ValueError(
            f"{context}.reconcile: expected 'exact' or 'declared', got {reconcile!r}",
        )
    columns = block.get("columns") or {}
    if not isinstance(columns, dict):
        raise ValueError(f"{context}.columns: expected a mapping of column name to declaration")
    return reconcile, columns


def _strict_bool(raw: dict[str, Any], key: str, context: str) -> bool:
    """Read a boolean without truthiness-coercing malformed YAML.

    `bool("false")` is True, so a quoted boolean would silently mean its
    opposite — and a visibility flag reading backwards hides nothing while
    reporting success.
    """
    value = raw.get(key, True)
    if not isinstance(value, bool):
        raise ValueError(f"{context}.{key}: expected true or false, got {value!r}")
    return value


def _parse_form_visibility(block: Any, context: str) -> EntitySection[FormVisibility]:
    reconcile, raw_columns = _entity_section(block, context)
    columns: dict[str, FormVisibility] = {}
    for name, raw in raw_columns.items():
        where = f"{context}.columns.{name}"
        if isinstance(raw, str):
            if raw not in ("hidden", "visible"):
                raise ValueError(
                    f"{where}: expected 'hidden', 'visible' or a mapping, got {raw!r}",
                )
            columns[name] = FormVisibility(new=raw == "visible", existing=raw == "visible")
            continue
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: expected 'hidden', 'visible' or a mapping")
        unknown = set(raw) - {"new", "existing", "when"}
        if unknown:
            raise ValueError(f"{where}: unknown key(s) {sorted(unknown)}")
        columns[name] = FormVisibility(
            new=_strict_bool(raw, "new", where),
            existing=_strict_bool(raw, "existing", where),
            # M13: an empty `when` is a mistake, not an absence — the same
            # declaration errors in column_validation and as an empty group.
            when=parse_condition(raw["when"], f"{where}.when") if "when" in raw else None,
        )
    return EntitySection(reconcile=reconcile, columns=columns)


def _parse_column_validation(block: Any, context: str) -> EntitySection[ColumnValidation]:
    reconcile, raw_columns = _entity_section(block, context)
    columns: dict[str, ColumnValidation] = {}
    for name, raw in raw_columns.items():
        where = f"{context}.columns.{name}"
        if not isinstance(raw, dict):
            raise ValueError(f"{where}: expected a mapping with 'when' and 'message'")
        unknown = set(raw) - {"when", "message"}
        if unknown:
            raise ValueError(f"{where}: unknown key(s) {sorted(unknown)}")
        for key in ("when", "message"):
            if not raw.get(key):
                raise ValueError(
                    f"{where}: {key!r} is required — a rule with no message fails the save "
                    f"with SharePoint's generic text, which tells the author nothing",
                )
        columns[name] = ColumnValidation(
            when=parse_condition(raw["when"], f"{where}.when"),
            message=str(raw["message"]),
        )
    return EntitySection(reconcile=reconcile, columns=columns)


def _parse_view(raw_view: Any, context: str, base_dir: Path) -> ViewDef:
    """Parse one declared view. Structural checks only (title/fields present,
    sort direction shape); semantic rules need the schema and live in
    validate_against_mapping."""
    if not isinstance(raw_view, dict):
        raise ValueError(f"{context}: view must be a mapping, got {type(raw_view).__name__}")
    title = raw_view.get("title")
    if not title:
        raise ValueError(f"{context}: view 'title' is required")
    fields = raw_view.get("fields")
    if not isinstance(fields, list) or not fields or not all(isinstance(f, str) for f in fields):
        raise ValueError(f"{context}: view 'fields' must be a non-empty list of column names")
    raw_where = raw_view.get("where")
    where = parse_condition(raw_where, f"{context}.where") if raw_where else None
    sort: list[ViewSort] = []
    for entry in raw_view.get("sort") or []:
        direction = str(entry.get("direction", "asc"))
        if direction not in {"asc", "desc"}:
            raise ValueError(
                f"{context}: sort direction must be 'asc' or 'desc', got {direction!r}",
            )
        sort.append(ViewSort(field=str(entry["field"]), direction=cast("SortDirection", direction)))
    raw_group = raw_view.get("group_by")
    group_by = (
        ViewGroupBy(
            field=str(raw_group["field"]),
            collapsed=bool(raw_group.get("collapsed", False)),
        )
        if raw_group is not None
        else None
    )
    raw_limit = raw_view.get("row_limit")
    raw_formatting = raw_view.get("formatting")
    raw_widths = raw_view.get("widths")
    widths: dict[str, int] = {}
    if raw_widths is not None:
        if not isinstance(raw_widths, dict):
            raise ValueError(
                f"{context}: 'widths' must be a mapping of column name to "
                f"pixel width, got {type(raw_widths).__name__}",
            )
        for col, px in raw_widths.items():
            if isinstance(px, bool) or not isinstance(px, int):
                raise ValueError(
                    f"{context}: widths[{col}] must be an integer pixel "
                    f"width, got {px!r}",
                )
            widths[str(col)] = px
    return ViewDef(
        title=str(title),
        fields=[str(f) for f in fields],
        default=bool(raw_view.get("default", False)),
        where=where,
        sort=sort,
        group_by=group_by,
        row_limit=int(raw_limit) if raw_limit is not None else None,
        formatting=(
            _load_json_value(base_dir, raw_formatting, f"{context}.formatting")
            if raw_formatting is not None
            else None
        ),
        widths=widths,
    )


def _parse_demo_item(raw_item: Any, context: str) -> DemoItem:
    """Structural parse of one demo row (title marker, value grammar and
    column semantics are validated against the schema in the validator)."""
    if not isinstance(raw_item, dict):
        raise ValueError(
            f"{context}: demo item must be a mapping, got {type(raw_item).__name__}",
        )
    key = raw_item.get("key")
    if not key or not isinstance(key, str):
        raise ValueError(f"{context}: demo item 'key' is required (a string)")
    values = raw_item.get("values")
    if not isinstance(values, dict) or not values:
        raise ValueError(
            f"{context}: demo item 'values' must be a non-empty mapping of "
            f"column name to value",
        )
    return DemoItem(key=str(key), values={str(col): v for col, v in values.items()})


def _parse_entity_kind(raw_kind: Any, context: str) -> EntityKind:
    """The one admission gate for entity kinds: a typo'd kind must fail the
    build here, not flow into schema_json and silently miss downstream
    comparisons like kind == "DocumentLibrary"."""
    if raw_kind not in ENTITY_KINDS:
        raise ValueError(
            f"{context}.kind must be one of "
            f"{', '.join(sorted(ENTITY_KINDS))}; got {raw_kind!r}",
        )
    return cast("EntityKind", raw_kind)


_PRINCIPAL_KINDS = frozenset({
    "group",
    "associated_owner_group",
    "associated_member_group",
    "associated_visitor_group",
})


def _parse_principal(raw_principal: Any, context: str) -> Principal:
    """Parse a principal dict into a Principal dataclass."""
    if not isinstance(raw_principal, dict):
        raise ValueError(
            f"{context}: principal must be a mapping, "
            f"got {type(raw_principal).__name__}",
        )
    kind = raw_principal.get("kind")
    if kind not in _PRINCIPAL_KINDS:
        raise ValueError(
            f"{context}: principal kind must be one of 'group', "
            f"'associated_owner_group', 'associated_member_group', "
            f"'associated_visitor_group'; got {kind!r}",
        )
    name = raw_principal.get("name")
    if kind == "group" and not name:
        raise ValueError(f"{context}: principal kind=group requires a 'name'")
    return Principal(
        kind=cast("PrincipalKind", kind),
        name=name if kind == "group" else None,
    )


def _parse_policy(raw_policy: Any, context: str) -> ListPermissionPolicy:
    """Parse a list permission policy dict."""
    break_inheritance = bool(raw_policy.get("break_inheritance", True))
    reconcile_mode = cast("ReconcileMode", str(raw_policy.get("reconcile", "configured")))
    if reconcile_mode not in {"configured", "exact"}:
        raise ValueError(
            f"{context}.reconcile must be 'configured' or 'exact', "
            f"got {reconcile_mode!r}",
        )
    if reconcile_mode == "exact" and not break_inheritance:
        raise ValueError(
            f"{context}: reconcile 'exact' requires break_inheritance: true; "
            "an inherited ACL cannot be reconciled as a list-scoped allowlist",
        )
    assignments: list[RoleAssignment] = []
    for i, raw_a in enumerate(raw_policy.get("assignments", [])):
        principal = _parse_principal(raw_a.get("principal", {}), f"{context}.assignments[{i}]")
        level = raw_a.get("level")
        if not level:
            raise ValueError(f"{context}.assignments[{i}]: 'level' is required")
        assignments.append(RoleAssignment(principal=principal, level=level))
    return ListPermissionPolicy(
        break_inheritance=break_inheritance,
        assignments=assignments,
        reconcile_mode=reconcile_mode,
    )


def _optional_bool(raw: dict[str, Any], key: str, context: str) -> bool:
    """Read an optional boolean without truthiness-coercing malformed YAML."""
    value = raw.get(key, False)
    if not isinstance(value, bool):
        raise ValueError(f"{context}.{key} must be a boolean, got {value!r}")
    return value


def _parse_permissions(raw: dict[str, Any]) -> PermissionsConfig | None:
    """Parse permission_levels, groups, list_permissions from the raw YAML dict."""
    # All three sections are optional; default to empty / no default policy.
    raw_levels = raw.get("permission_levels", [])
    raw_groups = raw.get("groups", [])
    raw_list_perms = raw.get("list_permissions") or {}

    levels = [
        CustomPermissionLevel(
            name=lvl["name"],
            description=lvl.get("description", ""),
            base_permissions=list(lvl.get("base_permissions", [])),
        )
        for lvl in raw_levels
    ]

    groups = [
        SiteGroup(
            name=grp["name"],
            description=grp.get("description", ""),
            owner_group=grp.get("owner_group", "Site Owners"),
            allow_members_edit_membership=bool(
                grp.get("allow_members_edit_membership", False),
            ),
            allow_request_to_join_leave=bool(
                grp.get("allow_request_to_join_leave", False),
            ),
            auto_accept_request_to_join_leave=bool(
                grp.get("auto_accept_request_to_join_leave", False),
            ),
            only_allow_members_view_membership=bool(
                grp.get("only_allow_members_view_membership", False),
            ),
            require_empty_at_deploy=_optional_bool(
                grp, "require_empty_at_deploy", f"groups[{i}]",
            ),
            enroll_operator_during_deploy=_optional_bool(
                grp, "enroll_operator_during_deploy", f"groups[{i}]",
            ),
        )
        for i, grp in enumerate(raw_groups)
    ]

    default_policy: ListPermissionPolicy | None = None
    default_policy_site_role: str | None = None
    raw_default = raw_list_perms.get("default")
    if raw_default is not None:
        default_policy = _parse_policy(raw_default, "list_permissions.default")
        raw_scope = raw_default.get("site_role")
        default_policy_site_role = str(raw_scope) if raw_scope is not None else None

    overrides: dict[str, ListPermissionPolicy] = {}
    for entity_name, raw_policy in (raw_list_perms.get("overrides") or {}).items():
        ctx = f"list_permissions.overrides.{entity_name}"
        overrides[entity_name] = _parse_policy(raw_policy, ctx)

    return PermissionsConfig(
        levels=levels,
        groups=groups,
        default_policy=default_policy,
        overrides=overrides,
        default_policy_site_role=default_policy_site_role,
    )


def _load_retention(path: Path) -> tuple[dict[str, RetentionPolicy], dict[str, str]]:
    """Load config/retention-policies.yaml; returns (policies, list_defaults)."""
    raw = _load_yaml(path)
    policies = {
        name: RetentionPolicy(
            name=name,
            description=spec.get("description", ""),
            sp_label=spec.get("sp_label", ""),
            retain_years=spec.get("retain_years"),
            retain_days=spec.get("retain_days"),
            trigger=spec.get("trigger", "creation"),
        )
        for name, spec in raw["policies"].items()
    }
    list_defaults = dict(raw.get("list_defaults") or {})
    return policies, list_defaults
