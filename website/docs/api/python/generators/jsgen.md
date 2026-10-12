---
title: jsgen
sidebar_position: 38
---

# `dbml_sharepoint.generators.jsgen`

*deploy.js*

Render deploy.js from the schema, mapping bundle, and release.

### `generate_deploy_js`

```python
def generate_deploy_js(*, schema: Schema, bundle: MappingBundle, resolved: ResolvedMapping, release: Release, site_url: str, site_role: str, source_dbml: str, source_mtime: str, generated_at: str, extension: DeploymentExtension | None = None, site_context: SiteContext | None = None, identities: AbcMapping[str, tuple[IdentityValue, ...]] = mappingproxy({}), env_provenance: EnvProvenance = EnvProvenance(path=None, digest=None, values=()), deployment_log_list: str = '', deployment_log_change_list: str = '', deployment_log_site: str = '', sidecar_run_log_title: str | None = None, sidecar_run_log_marker: str | None = None, sidecar_run_log_fields: Sequence[Mapping[str, object]] | None = None, sidecar_change_log_title: str | None = None, sidecar_change_log_marker: str | None = None, sidecar_change_fields: Sequence[Mapping[str, object]] | None = None, application: str = 'dbml-sharepoint') -> str
```

### `UNMANAGED`

```python
UNMANAGED = '__dbmlsp_unmanaged__'
```

### `FieldSpecError`

A field spec the generator cannot emit: an extension's malformed one, or a broken typemap.

### `build_schema_json`

```python
def build_schema_json(schema: Schema, bundle: MappingBundle, site_role: str, *, resolved: ResolvedMapping, site_url: str = '', release: Release | None = None, extension: DeploymentExtension | None = None, site_context: SiteContext | None = None) -> SchemaJson
```

