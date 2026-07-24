---
title: jsgen
sidebar_position: 10
---

# `dbml_sharepoint.jsgen`

*Generator — deploy.js*

Render deploy.js from the schema, mapping bundle, and release.

### `generate_deploy_js`

```python
def generate_deploy_js(*, schema: dbml_sharepoint.parser.Schema, bundle: dbml_sharepoint.mapping_loader.MappingBundle, release: dbml_sharepoint.release.Release, site_url: str, site_role: str, source_dbml: str, source_mtime: str, generated_at: str, extension: dbml_sharepoint.extension.DeploymentExtension | None = None, site_context: dbml_sharepoint.extension.SiteContext | None = None) -> str
```

### `build_schema_json`

```python
def build_schema_json(schema: dbml_sharepoint.parser.Schema, bundle: dbml_sharepoint.mapping_loader.MappingBundle, site_role: str, *, site_url: str = '', release: dbml_sharepoint.release.Release | None = None, extension: dbml_sharepoint.extension.DeploymentExtension | None = None, site_context: dbml_sharepoint.extension.SiteContext | None = None) -> dict[str, typing.Any]
```

