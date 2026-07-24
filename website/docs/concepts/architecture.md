---
title: Architecture
sidebar_position: 1
---

# Architecture

The build is a straight pipeline. Every stage is a plain module with a
readable role; nothing is hidden behind frameworks.

```
schema.dbml ──▶ parser ─┐
mapping.yaml ─▶ mapping_loader ─┼─▶ validator ─▶ ordering / typemap /
release.yaml ─▶ release ────────┘               phases / permissions /
                                                styles
                                                     │
                     ┌───────────────────────────────┘
                     ▼
        jsgen · rollbackgen · assessgen · demogen ·
        manifestgen · reportgen        (one artifact family each)
                     │
                     ▼
        bundle.emit_bundle()  — the ONE emission sequence:
        stale clearing, INDEX.md, checksums.txt, provenance
```

## Repository map

Flat, one module per concern — the role is readable from the name:

| Layer | Modules | Responsibility |
|---|---|---|
| Model | `parser` · `mapping_loader` · `release` | Parse DBML, the mapping YAML (+ enums/retention), release.yaml into typed objects |
| Analysis | `validator` · `ordering` · `typemap` · `phases` · `permissions` · `styles` | Build-time rules (fail-closed), dependency ordering, SP type/formatter/permission projections |
| Generators (`*gen`) | `jsgen` · `rollbackgen` · `assessgen` · `demogen` · `manifestgen` · `reportgen` | Each renders one artifact family from model + analysis |
| Packaging | `bundle` · `templating` · `cli` · `extension` | The one emission sequence (`emit_bundle`), stale clearing, INDEX/checksums, the shared Jinja env, the CLI, the extension protocol |

The flat layout is deliberate: a module per concern, no sub-packages to
navigate, and the [generated API reference](../api/index.md) documents
each module's public surface.

## Templates mirror the layout

`templates/*.js.j2` are the pasteable entry-point scripts;
`templates/_*.js.j2` are shared partials (provenance header, site guard,
HTTP transport, write headers, cached digest) included by all of them;
`templates/deploy/_*.js.j2` are deploy.js's phase bodies. Each template
opens with a contract comment — extracted verbatim into the
[template reference](../api/templates.md).

A shared partial exists only when **every** including script needs it
**identically** (identity, guard, digest, HTTP transport). Phase and
domain logic stays with its phase — see the
[development philosophy](../development/philosophy.md) for why that line
is drawn where it is.

## The phases manifest

`phases.py` is the single source of phase truth. Group and step numbers
derive from position in `DEPLOY_GROUPS`; add or move a step and every
consumer renumbers automatically — deploy.js banners, `[Phase X.Y]`
error tags, the manifest's phase references, and test expectations.
Reference steps by name or key, never by number.

## The extension protocol

Organisation-specific behaviour (identity seeding, classification
projection, per-site policy) stays out of the core. Implement
`DeploymentExtension` (hooks: `expand_column`, `seed_lists`,
`extra_validators`, `manifest_extras`) in your own package and register
it under the `dbml_sharepoint.extensions` entry-point group:

```toml
[project.entry-points."dbml_sharepoint.extensions"]
my_org = "my_org_deployer.extension:MyOrgExtension"
```

The core CLI resolves `--extension my_org`; or ship your own thin CLI
that composes the core pipeline programmatically — `clear_generated` →
validate → manifest → `emit_bundle` — rather than re-implementing
emission. The composition points are public functions; see the
[bundle](../api/python/bundle.md) and [cli](../api/python/cli.md) API
pages.
