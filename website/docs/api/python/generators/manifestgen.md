---
title: manifestgen
sidebar_position: 32
---

# `dbml_sharepoint.generators.manifestgen`

*deploy-manifest.md*

Render deploy-manifest.md.

### `generate_manifest`

```python
def generate_manifest(*, schema_json: dict[str, typing.Any], findings: list[dbml_sharepoint.analysis.findings.Finding], bundle: dbml_sharepoint.model.mapping_types.MappingBundle, release: dbml_sharepoint.model.release.Release, site_url: str, site_role: str, source_dbml: str, source_mtime: str, generated_at: str, manifest_extras: dbml_sharepoint.extension.ManifestExtras | None = None, enterprise_reader: str | None = None, env_provenance: dbml_sharepoint.model.env_file.EnvProvenance = EnvProvenance(path=None, digest=None, values=()), sidecar_run_log_title: str | None = None, sidecar_change_log_title: str | None = None, deployment_log_list: str = '', deployment_log_site: str = '') -> str
```

Render the deploy manifest for ONE build.

``enterprise_reader`` is the address `build --enterprise-reader` was
given, or None. It is render material, not a build input: the manifest
is the document an operator reads BEFORE pasting anything, and the
reader enrolment is the one thing this bundle does that a rollback does
not undo. Passing it only to ``generate_deploy_js`` left the manifest
unable to say so, and left its group table reporting the permanently
enrolled group as one nothing enrols into.

``env_provenance`` defaults to ``NO_ENV_FILE`` rather than being
required: this function has 19 call sites, and a required parameter
would break every one of them.

The two ``sidecar_*_title`` parameters default to None, the SAME default
``jsgen.generate_deploy_js`` carries. They used to default to the sidecar
titles, so a caller that passed neither to either function got a manifest
promising two log lists the deploy script it documents never emits. The
manifest describes what was built, so the default has to be the built
default and not the module's idea of a title.

