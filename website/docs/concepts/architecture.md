---
title: Architecture
sidebar_position: 1
---

# Architecture

The build is a straight pipeline. Every stage is a plain module with a
readable role; nothing is hidden behind frameworks.

```text
schema.dbml ──▶ model/parser ─┐
mapping.yaml ─▶ model/mapping_loader ─┼─▶ analysis/  validator,
release.yaml ─▶ model/release ────────┘   ordering, typemap, phases,
                                          permissions, styles
                     ┌────────────────────────┘
                     ▼
        generators/  jsgen · rollbackgen · assessgen ·
        demogen · manifestgen · reportgen   (one artifact family each)
                     │
                     ▼
        bundle.emit_bundle()  — the ONE emission sequence:
        stale clearing, index.md, checksums.txt, provenance
```

## Repository map

One module per concern, grouped into layer packages that mirror the
pipeline; the packaging spine sits at the package root:

| Layer | Modules | Responsibility |
| --- | --- | --- |
| `model/` | `parser` · `mapping_loader` · `release` | Parse DBML, the mapping YAML (+ enums/retention), release.yaml into typed objects |
| `analysis/` | `validator` · `ordering` · `typemap` · `phases` · `permissions` · `styles` | Build-time rules (fail-closed), dependency ordering, SP type/formatter/permission projections |
| `generators/` | `jsgen` · `rollbackgen` · `assessgen` · `demogen` · `manifestgen` · `reportgen` | Each renders one artifact family from model + analysis |
| root | `bundle` · `templating` · `cli` · `extension` | The one emission sequence (`emit_bundle`), stale clearing, INDEX/checksums, the shared Jinja env, the CLI, the extension protocol |

Data flows downward — analysis knows nothing of generators — and the root
modules orchestrate. The [generated API reference](../api/index.md)
documents each module's public surface, organised the same way.

**One upward edge exists**, and it is deliberate rather than accidental
drift: `model/mapping_loader.py` imports `analysis.styles`, because
parsing a `column_formatting` style spec means validating it against the
style vocabulary, and that vocabulary is analysis's to own. Treat the rule
as "no layer reaches down past its neighbour" rather than as a strict
acyclic import graph, and check the imports rather than trusting this
paragraph if it matters to you.

## Templates mirror the layout

`templates/*.js.j2` are the pasteable entry-point scripts;
`templates/_*.js.j2` are shared partials (provenance header, site guard,
HTTP transport, write headers, cached digest); `templates/deploy/_*.js.j2`
are deploy.js.txt's phase bodies.

**"Shared" means available to every script, not present in every script.**
`deploy.js.txt`, `rollback.js.txt` and `demo-data.js.txt` include all five top-level
partials. `assess.js.txt` includes four: it omits `_http_write.js.j2`, so the
write-header helper (`spHeaders`) and every mutation path it feeds are
simply absent from the emitted file. That omission is what makes the
read-only guarantee structural — you can check it by grepping the artifact
rather than by trusting the phase logic. (`assess.js.txt` still issues two
POSTs: the `contextinfo` digest fetch, and a CSOM `ProcessQuery`
availability probe that reads `Web.Title`. Both are reads; POST is just
how SharePoint spells them.) Each template
opens with a contract comment — extracted verbatim into the
[template reference](../api/templates.md).

A shared partial exists only when **every** including script needs it
**identically** (identity, guard, digest, HTTP transport). Phase and
domain logic stays with its phase — see the
[development philosophy](../development/philosophy.md) for why that line
is drawn where it is.

## The phases manifest

`analysis/phases.py` is the single source of phase truth. Group and step numbers
derive from position in `DEPLOY_GROUPS`; add or move a step and every
consumer renumbers automatically — deploy.js.txt banners, `[Phase X.Y]`
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
