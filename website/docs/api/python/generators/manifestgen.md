---
title: manifestgen
sidebar_position: 19
---

# `dbml_sharepoint.generators.manifestgen`

*deploy-manifest.md*

Render deploy-manifest.md.

### `generate_manifest`

```python
def generate_manifest(*, schema_json: dict[str, typing.Any], findings: list[dbml_sharepoint.analysis.findings.Finding], bundle: dbml_sharepoint.model._mapping_types.MappingBundle, release: dbml_sharepoint.model.release.Release, site_url: str, site_role: str, source_dbml: str, source_mtime: str, generated_at: str, manifest_extras: dbml_sharepoint.extension.ManifestExtras | None = None, enterprise_reader: str | None = None) -> str
```

Render the deploy manifest for ONE build.

``enterprise_reader`` is the address `build --enterprise-reader` was
given, or None. It is render material, not a build input: the manifest
is the document an operator reads BEFORE pasting anything, and the
reader enrolment is the one thing this bundle does that a rollback does
not undo. Passing it only to ``generate_deploy_js`` left the manifest
unable to say so, and left its group table reporting the permanently
enrolled group as one nothing enrols into.

