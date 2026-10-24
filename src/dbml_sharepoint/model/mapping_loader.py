# src/dbml_sharepoint/model/mapping_loader.py
"""Loader for schema/sharepoint-mapping.yaml plus its referenced config YAMLs.

Generic core loader. Every top-level section is read by one family module
under `model/sections/`, through the ordered registry there; this module
runs the registry. It reads the document, refuses a section no family
declares, hands each family only the blocks it declared, and assembles the
typed bundle from what the families produce.

Relative config paths (enum_sources values, retention_policies_source, the
section pointers) resolve relative to the mapping YAML's own directory, so
the deployer can be invoked from any working directory. Project-specific
config lives under `extensions: {<name>: {...}}` and is passed through
untyped as `MappingBundle.extension_configs`. This module knows nothing
about what any particular extension's block means, and selection by name is
deferred to `MappingBundle.extension_config_for` so it honors the RESOLVED
extension (a CLI `--extension` override may differ from the mapping's own
`extension:` key).
"""

from pathlib import Path

from dbml_sharepoint.model._keys import _text_key
from dbml_sharepoint.model._retirement import _apply_retirement
from dbml_sharepoint.model.errors import UnknownMappingKeyError
from dbml_sharepoint.model.lists_forms import read_lists_forms_file
from dbml_sharepoint.model.mapping_types import _REMOVED_SECTIONS, Mapping, MappingBundle
from dbml_sharepoint.model.reading import load_yaml, recording_blank_defaults
from dbml_sharepoint.model.sections import KNOWN_SECTIONS, SECTION_FAMILIES, section_context
from dbml_sharepoint.model.sections._form_file import read_form_file
from dbml_sharepoint.model.sections.context import LoadedFields


def load_mapping(mapping_path: Path) -> MappingBundle:
    """Load the mapping YAML and the referenced configs into a single bundle."""
    mapping_path = mapping_path.resolve()
    read = load_yaml(mapping_path)
    base_dir = mapping_path.parent

    # Before any family runs, so the highest-signal error is the one
    # reported: a misspelled section used to lose to a shape error anywhere
    # in the sections parsed ahead of this gate.
    raw = {_text_key(key, "mapping"): value for key, value in read.items()}
    unknown_sections = set(raw) - KNOWN_SECTIONS
    if unknown_sections:
        raise UnknownMappingKeyError(
            f"unknown mapping section(s) {sorted(unknown_sections)}. "
            f"Unknown keys used to be ignored, so a misspelled section "
            f"silently deployed nothing.",
        )
    for removed, replacement in _REMOVED_SECTIONS.items():
        if removed in raw:
            raise UnknownMappingKeyError(f"{removed!r} has been replaced by {replacement}")

    # Before the families, so they read the form as if the mapping declared it.
    form = read_form_file(base_dir, raw)
    raw.update(form.sections())

    loaded = LoadedFields()
    with recording_blank_defaults() as blank_defaults:
        for family in SECTION_FAMILIES:
            loaded.update(family.read(section_context(family, raw, base_dir, loaded)))

    form.add_tree_only_entities(loaded["form_formatting"])

    # Every family fills its keys on every load, so each is present here.
    mapping = Mapping(
        prefix=loaded["prefix"],
        prefix_owner=loaded["prefix_owner"],
        entities=loaded["entities"],
        cross_site_reference_columns=loaded["cross_site_reference_columns"],
        versioning_default=loaded["versioning_default"],
        versioning_overrides=loaded["versioning_overrides"],
        enum_sources=loaded["enum_sources"],
        watched_lists=loaded["watched_lists"],
        polymorphic_patterns=loaded["polymorphic_patterns"],
        retention_policies_source=loaded["retention_policies_source"],
        extension=loaded["extension"],
        permissions=loaded["permissions"],
        identities=loaded["identities"],
        previous_prefixes=loaded["previous_prefixes"],
        calculated_formulas=loaded["calculated_formulas"],
        default_formulas=loaded["default_formulas"],
        lookup_projections=loaded["lookup_projections"],
        derived_columns=loaded["derived_columns"],
        form_visibility=loaded["form_visibility"],
        column_validation=loaded["column_validation"],
        views=loaded["views"],
        field_sets=loaded["field_sets"],
        demo_items=loaded["demo_items"],
        display_name_mode=loaded["display_name_mode"],
        display_name_overrides=loaded["display_name_overrides"],
        reporting=loaded["reporting"],
        column_style_specs=loaded["column_style_specs"],
        column_formatting=loaded["column_formatting"],
        form_formatting=loaded["form_formatting"],
        list_validation=loaded["list_validation"],
        retired_columns=loaded["retired_columns"],
        blank_defaults=blank_defaults,
        seal_columns=loaded["seal_columns"],
        prevent_list_deletion=loaded["prevent_list_deletion"],
        attachments=loaded["attachments"],
        item_security_default=loaded["item_security_default"],
        item_security_overrides=loaded["item_security_overrides"],
    )
    # Retirement resolves ONCE, here, into the structures the generators
    # already consume. `field_sets` expansion rewrites views[].fields
    # BEFORE this call, so retirement filters the expanded list.
    _apply_retirement(mapping)

    source_paths: dict[str, Path] = {
        "mapping": mapping_path,
        **{f"enum:{name}": path for name, path in mapping.enum_sources.items()},
    }
    if mapping.retention_policies_source is not None:
        source_paths["retention"] = mapping.retention_policies_source

    return MappingBundle(
        mapping=mapping,
        source_paths=source_paths,
        enum_choices=loaded["enum_choices"],
        retention_policies=loaded["retention_policies"],
        retention_list_defaults=loaded["retention_list_defaults"],
        extension_configs=loaded["extension_configs"],
        governance=loaded["governance"],
        form_trees=form.trees,
        lists_forms=read_lists_forms_file(base_dir),
    )
