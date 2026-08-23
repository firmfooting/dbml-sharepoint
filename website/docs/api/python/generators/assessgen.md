---
title: assessgen
sidebar_position: 26
---

# `dbml_sharepoint.generators.assessgen`

*assess.js and assess-manifest.md*

Site-assessment generator: read-only assess.js + assess-manifest.md.

Derives a pack's deployment requirements from its schema+mapping and emits
a browser-console script that probes a target site for them across three
tiers (always-run enumerations, pack-driven attempt-probes, and a printed
not-assessable honesty block). STRICTLY read-only. See the read-only
guarantee test. Spec: docs/plans/2026-07-24-tenant-assessment-design.md.

### `Requirement`

```python
@dataclass(frozen=True)
class Requirement:
    key: str
    description: str
    level_on_fail: str
```

Requirement(key: str, description: str, level_on_fail: str)

### `assess_targets`

```python
def assess_targets(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str) -> dict[str, typing.Any]
```

The data-driven inputs the assess.js probes loop over.

`list_markers` pairs each declared list title with the exact provenance
marker its Description must carry. Pairs rather than a mapping, because
the template emits this as a JavaScript object literal and a list titled
`__proto__` would then set the prototype instead of becoming a key. It is
IMPORTED from
`analysis.list_description`, never re-spelled here or in the template: a
second spelling would let assess.js quietly disagree with deploy.js about
the same list, reporting drift on a description the deploy considers
correct (or, worse, staying silent on one it does not).

### `derive_requirements`

```python
def derive_requirements(schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_role: str) -> list[dbml_sharepoint.generators.assessgen.Requirement]
```

The pack's site requirements, worst-case severity on probe failure.

### `NOT_ASSESSABLE`

```python
NOT_ASSESSABLE = ('Power Automate / Power Apps inventory (lives in Power Platform APIs, no SharePoint REST surface from site context)', 'Audit settings (SSOM-only; not exposed via CSOM/REST)', 'Information-barrier seg…
```

### `generate_assess_js`

```python
def generate_assess_js(*, schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, release: dbml_sharepoint.model.release.Release, site_url: str, site_role: str, source_dbml: str, generated_at: str) -> str
```

### `generate_assess_manifest`

```python
def generate_assess_manifest(*, schema: dbml_sharepoint.model.parser.Schema, bundle: dbml_sharepoint.model.mapping_types.MappingBundle, site_url: str, site_role: str) -> str
```

