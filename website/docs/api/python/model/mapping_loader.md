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

### `KNOWN_SECTIONS`

```python
KNOWN_SECTIONS = frozenset({'calculated_formulas', 'column_formatting', 'column_validation', 'cross_site_reference_columns', 'demo_items', 'display_names', 'entities', 'enum_sources', 'extension', 'extensions', 'field…
```

### `load_mapping`

```python
def load_mapping(mapping_path: pathlib.Path) -> dbml_sharepoint.model._mapping_types.MappingBundle
```

Load the mapping YAML and the referenced configs into a single bundle.

