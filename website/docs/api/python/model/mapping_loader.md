---
title: mapping_loader
sidebar_position: 2
---

# `dbml_sharepoint.model.mapping_loader`

*load mapping.yaml and referenced config*

Loader for schema/sharepoint-mapping.yaml plus its referenced config YAMLs.

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

### `DERIVED_TYPES`

```python
DERIVED_TYPES = {'logical': 'type logical', 'text': 'type text', 'number': 'type number', 'Int64': 'Int64.Type', 'date': 'type date', 'datetime': 'type datetime', 'datetimezone': 'type datetimezone'}
```

### `DERIVED_AGGREGATES`

```python
DERIVED_AGGREGATES = frozenset({'count', 'max', 'min', 'names'})
```

### `load_mapping`

```python
def load_mapping(mapping_path: pathlib.Path) -> dbml_sharepoint.model.mapping_types.MappingBundle
```

Load the mapping YAML and the referenced configs into a single bundle.

