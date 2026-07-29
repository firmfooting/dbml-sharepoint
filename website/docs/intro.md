---
title: Introduction
sidebar_position: 1
slug: /
---

# dbml-sharepoint

Turn a [DBML](https://dbml.dbdiagram.io/docs/) schema plus a YAML mapping
into an **idempotent, fail-closed, browser-console `deploy.js`** that
provisions SharePoint Online lists, columns, lookups, views, indexes,
permission levels, groups and ACLs — with **no tenant admin rights, no
premium licence, and nothing installed on the target**. If you can open
the site and press F12, you can deploy.

```
schema.dbml + mapping.yaml + release.yaml
        │
        ▼   dbml-sharepoint build
┌────────────────────────────────────┐
│ deploy-manifest.md   ← read first  │
│ assess.js            ← probe       │
│ deploy.js            ← paste       │
│ demo-data.js         ← demonstrate │
│ rollback.js          ← escape      │
│ reporting/           ← analyse     │
└────────────────────────────────────┘
        │
        ▼   paste into the site's browser console (F12)
   SharePoint Online lists, ready to use
```

## Why

- **Design as code.** Your list schema lives in DBML — reviewable,
  diffable, renderable as an ERD on [dbdiagram.io](https://dbdiagram.io),
  with indexes declared beside their tables. Deployment and presentation
  mapping (prefixes, templates, versioning, views, formatting, ACLs) lives
  in YAML next to it.
- **Deploy with nothing but a browser.** The generated script runs in the
  site's own console under your own login, calling SharePoint REST/CSOM
  endpoints. No PnP, no CSOM installs, no app registrations, no Graph
  consent, no stored credentials. See the
  [security model](concepts/security-model.md).
- **Fail closed, rerun safely.** Every write is preceded by read-only
  preflights: the wrong site aborts, existing lists and fields are adopted
  only when their immutable shape provably matches, mutable drift is
  narrowly reconciled and read back. Reruns of the same release skip
  verified work. See the [safety model](concepts/safety-model.md).
- **The whole lifecycle ships in the bundle.** A read-only
  [site assessment](artifacts/assess.md) before you deploy, optional
  [demo data](artifacts/demo-data.md) to demonstrate with, a
  retention-aware [rollback](artifacts/rollback.md) to tear down, and a
  [reporting pack](artifacts/reporting.md) for Power BI and SQL.

## Where to go next

- [Getting started](getting-started.md) — install, build, first deploy.
- [Concepts](concepts/architecture.md) — how the pipeline and the
  generated scripts work.
- [Artifacts](artifacts/deploy.md) — the contract of every generated
  file.
- [Reference](reference/mapping.md) — every DBML construct, mapping key
  and CLI flag.
- [API reference](api/index.md) — generated from the source: Python
  modules and template contracts.
- [Development](development/philosophy.md) — the engineering doctrine
  behind the project, and how to contribute safely.
