---
title: manifestgen
sidebar_position: 14
---

# `dbml_sharepoint.manifestgen`

*Generator — deploy-manifest.md*

Render deploy-manifest.md.

### `generate_manifest`

```python
def generate_manifest(*, schema_json: dict[str, typing.Any], findings: list[dbml_sharepoint.validator.Finding], bundle: dbml_sharepoint.mapping_loader.MappingBundle, release: dbml_sharepoint.release.Release, site_url: str, site_role: str, source_dbml: str, source_mtime: str, generated_at: str, manifest_extras: dbml_sharepoint.extension.ManifestExtras | None = None) -> str
```

