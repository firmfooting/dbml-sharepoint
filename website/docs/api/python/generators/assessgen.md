---
title: assessgen
sidebar_position: 40
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

### `AssessTargets`

The payload assess.js loops over. A row is a list, so it compares equal to its JSON.

### `assess_targets`

```python
def assess_targets(schema: Schema, bundle: MappingBundle, site_role: str, *, resolved: ResolvedMapping, identities: AbcMapping[str, tuple[IdentityValue, ...]] = mappingproxy({})) -> AssessTargets
```

The data-driven inputs the assess.js probes loop over; see `_collect`.

### `derive_requirements`

```python
def derive_requirements(schema: Schema, bundle: MappingBundle, site_role: str, *, resolved: ResolvedMapping, identities: AbcMapping[str, tuple[IdentityValue, ...]] = mappingproxy({})) -> list[Requirement]
```

The pack's site requirements, worst-case severity on probe failure.

### `NOT_ASSESSABLE`

```python
NOT_ASSESSABLE = ('Power Automate / Power Apps inventory (lives in Power Platform APIs, no SharePoint REST surface from site context)', 'Audit settings (SSOM-only; not exposed via CSOM/REST)', 'Information-barrier seg…
```

### `generate_assess_js`

```python
def generate_assess_js(*, schema: Schema, bundle: MappingBundle, resolved: ResolvedMapping, release: Release, site_url: str, site_role: str, source_dbml: str, generated_at: str, identities: AbcMapping[str, tuple[IdentityValue, ...]] = mappingproxy({}), application: str = 'dbml-sharepoint') -> str
```

### `generate_assess_manifest`

```python
def generate_assess_manifest(*, schema: Schema, bundle: MappingBundle, resolved: ResolvedMapping, site_url: str, site_role: str) -> str
```

