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

from dataclasses import fields
from pathlib import Path
from types import MappingProxyType
from typing import Any

from dbml_sharepoint.model._retirement import _apply_retirement
from dbml_sharepoint.model.mapping_types import _REMOVED_SECTIONS, Mapping, MappingBundle
from dbml_sharepoint.model.reading import load_yaml
from dbml_sharepoint.model.sections import KNOWN_SECTIONS, SECTION_FAMILIES, section_context

#: The M type token each declared type maps to, and so the vocabulary a
#: `derived_columns` entry may name. Deliberately small: every one of these
#: has an unambiguous M literal type, and a kind whose M shape nobody has
#: decided must not resolve to `type any` and load as an Error value in
#: every populated cell.
DERIVED_TYPES: dict[str, str] = {
    "logical": "type logical",
    "text": "type text",
    "number": "type number",
    "Int64": "Int64.Type",
    "date": "type date",
    "datetime": "type datetime",
    "datetimezone": "type datetimezone",
}

#: What a `count` may ask of the child rows. `count` needs no column;
#: the other three name one.
DERIVED_AGGREGATES: frozenset[str] = frozenset(
    {"count", "min", "max", "names"},
)

# The families produce `Mapping` fields and, for the three that load a file
# beside the mapping, `MappingBundle` fields. The two dataclasses share no
# field name, so this is the whole rule for which is which.
_MAPPING_FIELDS = frozenset(f.name for f in fields(Mapping))


def load_mapping(mapping_path: Path) -> MappingBundle:
    """Load the mapping YAML and the referenced configs into a single bundle."""
    mapping_path = mapping_path.resolve()
    raw = load_yaml(mapping_path)
    base_dir = mapping_path.parent

    # Before any family runs, so the highest-signal error is the one
    # reported: a misspelled section used to lose to a shape error anywhere
    # in the sections parsed ahead of this gate.
    unknown_sections = set(raw) - KNOWN_SECTIONS
    if unknown_sections:
        raise ValueError(
            f"unknown mapping section(s) {sorted(unknown_sections)}. Unknown keys used to be "
            f"ignored, so a misspelled section silently deployed nothing.",
        )
    for removed, replacement in _REMOVED_SECTIONS.items():
        if removed in raw:
            raise ValueError(f"{removed!r} has been replaced by {replacement}")

    loaded: dict[str, Any] = {}
    for family in SECTION_FAMILIES:
        loaded.update(family.read(
            section_context(family, raw, base_dir, MappingProxyType(loaded)),
        ))

    mapping = Mapping(**{
        name: value for name, value in loaded.items() if name in _MAPPING_FIELDS
    })
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
        **{name: value for name, value in loaded.items() if name not in _MAPPING_FIELDS},
    )
