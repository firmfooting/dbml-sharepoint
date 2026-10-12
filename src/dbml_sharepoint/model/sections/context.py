# src/dbml_sharepoint/model/sections/context.py
"""What one section family is allowed to see.

A family reads the top-level keys it declared in its registry entry and
nothing else. The runner builds one of these per family, holding only that
family's blocks, so a reader cannot reach a section it did not declare and
a section no family declared cannot be read. Holding those two directions
equal is what the registry is for.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    CrossSiteRef,
    DemoItem,
    DerivedColumn,
    EntityMapping,
    EntitySection,
    FormFormatting,
    FormVisibility,
    Governance,
    IdentityDeclaration,
    ItemSecurity,
    ItemSecurityOverride,
    ListValidation,
    PermissionsConfig,
    PolymorphicPattern,
    ReportingOptions,
    RetentionPolicy,
    RetiredColumn,
    Versioning,
    VersioningOverride,
    ViewDef,
    WatchedList,
)


class LoadedFields(TypedDict, total=False, closed=True):
    """What the families produce: the `Mapping` fields and the `MappingBundle` fields.

    Every family fills the keys of the sections it declared, so a key a family
    does not own is absent here. The loader reads them by name into the two
    dataclasses; `retirement_strips`, `blank_defaults`, `source_paths` and
    `mapping` are the runner's own.
    """

    prefix: str
    prefix_owner: str
    previous_prefixes: tuple[str, ...]
    entities: dict[str, EntityMapping]
    cross_site_reference_columns: list[CrossSiteRef]
    polymorphic_patterns: list[PolymorphicPattern]
    watched_lists: list[WatchedList]
    lookup_projections: dict[str, dict[str, list[str]]]
    calculated_formulas: dict[str, dict[str, str]]
    default_formulas: dict[str, dict[str, str]]
    derived_columns: dict[str, list[DerivedColumn]]
    reporting: ReportingOptions
    versioning_default: Versioning
    versioning_overrides: dict[str, VersioningOverride]
    item_security_default: ItemSecurity
    item_security_overrides: dict[str, ItemSecurityOverride]
    seal_columns: bool
    prevent_list_deletion: bool
    attachments: bool
    enum_sources: dict[str, Path]
    enum_choices: dict[str, list[str]]
    retention_policies_source: Path | None
    retention_policies: dict[str, RetentionPolicy]
    retention_list_defaults: dict[str, str]
    extension: str | None
    extension_configs: dict[str, dict[object, object]]
    permissions: PermissionsConfig | None
    column_style_specs: dict[str, dict[str, dict[str, object]]]
    column_formatting: dict[str, dict[str, dict[str, object]]]
    form_formatting: dict[str, FormFormatting]
    field_sets: dict[str, dict[str, list[str]]]
    views: dict[str, list[ViewDef]]
    form_visibility: dict[str, EntitySection[FormVisibility]]
    column_validation: dict[str, EntitySection[ColumnValidation]]
    list_validation: dict[str, ListValidation]
    display_name_mode: str | None
    display_name_overrides: dict[str, dict[str, str]]
    demo_items: dict[str, list[DemoItem]]
    retired_columns: dict[str, dict[str, RetiredColumn]]
    identities: dict[str, IdentityDeclaration]
    governance: Governance


@dataclass(frozen=True)
class SectionContext:
    """One family's view of the mapping being loaded.

    `blocks` holds those of the family's declared keys that the document
    actually carries, already taken from the file the family's pointer names
    when the mapping used one. An absent key is absent here too, and
    `required` refuses it.

    `loaded` is what earlier families produced, keyed by field name. It
    exists for the one dependency that crosses families: permissions expand
    the `{prefix}` placeholder, so identity runs first and permissions read
    `loaded["prefix"]`.
    """

    base_dir: Path
    keys: tuple[str, ...]
    blocks: Mapping[str, object]
    loaded: LoadedFields

    def block(self, key: str, default: object = None) -> object:
        """The block under `key`, or `default` when the mapping omits it."""
        self._declared(key)
        return self.blocks.get(key, default)

    def required(self, key: str) -> object:
        """The block under `key`, refusing a mapping that omits it.

        A `MappingShapeError` and not the bare `KeyError` this raised before
        #170: the class advertises "a required key absent" as one of its
        cases, and an absent `prefix:` or `entities:` is the most ordinary way
        a mapping is wrong, so a caller catching `MappingError` has to see it.
        The sentence is the one the CLI already printed for the KeyError.
        """
        self._declared(key)
        if key not in self.blocks:
            raise MappingShapeError(f"missing required key {key!r}")
        return self.blocks[key]

    def _declared(self, key: str) -> None:
        # A LookupError and not a KeyError: this is a defect in a family, not
        # in the mapping, and the CLI must keep the traceback for it.
        if key not in self.keys:
            raise LookupError(
                f"{key!r} is not a section this family declared; it reads {self.keys}",
            )
