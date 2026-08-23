---
title: jsgen
sidebar_position: 21
---

# `dbml_sharepoint.generators.jsgen`

*deploy.js*

Render deploy.js from the schema, mapping bundle, and release.

### `generate_deploy_js`

```python
def generate_deploy_js(*, schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, release: dbml_sharepoint.model.release.Release, site_url: str, site_role: str, source_dbml: str, source_mtime: str, generated_at: str, extension: dbml_sharepoint.extension.DeploymentExtension | None = None, site_context: dbml_sharepoint.extension.SiteContext | None = None, enterprise_reader: str | None = None, env_provenance: dbml_sharepoint.model.env_file.EnvProvenance = EnvProvenance(path=None, digest=None, values=())) -> str
```

### `UNMANAGED`

```python
UNMANAGED = '__dbmlsp_unmanaged__'
```

### `build_schema_json`

```python
def build_schema_json(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str, *, site_url: str = '', release: dbml_sharepoint.model.release.Release | None = None, extension: dbml_sharepoint.extension.DeploymentExtension | None = None, site_context: dbml_sharepoint.extension.SiteContext | None = None) -> dict[str, typing.Any]
```

