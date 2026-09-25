---
title: Introduction
sidebar_position: 1
slug: /
---

# dbml-sharepoint

Turn a DBML schema and a YAML mapping into a fail-closed script that
provisions SharePoint Online lists from the browser console.

`dbml-sharepoint` reads a [DBML](https://dbml.dbdiagram.io/docs/) schema, a
YAML mapping and a release file, and builds an **idempotent, fail-closed,
browser-console `deploy.js.txt`**. That script provisions SharePoint Online
lists and document libraries, with their columns, lookups, views, indexes,
permission levels, groups and ACLs.

It is for site owners and M365 operators who need real lists on a site they
own, and have **no tenant admin rights, no premium licence, and nothing
installed on the target**. If you can open the site and press F12, you can
deploy.

The source, issues and releases are on
[GitHub](https://github.com/firmfooting/dbml-sharepoint).

## At a glance

```text
schema.dbml + mapping.yaml + release.yaml
        │
        ▼   dbml-sharepoint build
┌──────────────────────────────────────────────────┐
│ deploy-manifest.md   ← read first                │
│ assess.js.txt        ← probe the site, read-only │
│ assess-manifest.md   ← how to read the verdict   │
│ deploy.js.txt        ← paste to provision        │
│ verify.js.txt        ← check the clock rules     │
│ demo-data.js.txt     ← demonstrate (--seed)      │
│ rollback.js.txt      ← escape a failed first run │
│ reporting/           ← Power BI and SQL          │
│ index.md             ← what is in the bundle     │
│ checksums.txt        ← SHA-256 of every file     │
└──────────────────────────────────────────────────┘
        │
        ▼   paste into the site's browser console (F12)
   SharePoint Online lists, ready to use
```

[`verify.js.txt`](artifacts/verify.md) is emitted only when the pack reads a
clock (a `today` or `now` save rule, a `today` view window, or a `[today]`
default). [`demo-data.js.txt`](artifacts/demo-data.md) is emitted only with
`--seed`. Everything else comes with every build. The
[Artifacts](artifacts/deploy.md) section gives the contract of each file.

## Why

- **Design as code.** Your list schema lives in DBML: reviewable,
  diffable, renderable as an ERD on [dbdiagram.io](https://dbdiagram.io),
  with indexes declared beside their tables. Deployment and presentation
  mapping (prefixes, templates, versioning, views, formatting, ACLs) lives
  in YAML next to it.
- **Deploy with nothing but a browser.** The generated script runs in the
  site's own console under your own login, calling SharePoint REST and CSOM
  endpoints. No PnP, no CSOM installs, no app registrations, no Graph
  consent, no stored credentials. See the
  [security model](concepts/security-model.md) and, for an honest look at
  what PnP, site scripts and Graph offer that this tool does not,
  [why not PnP, site scripts, or Graph?](concepts/comparison.md)
- **Fail closed, rerun safely.** Every write is preceded by read-only
  preflights. The wrong site aborts. An existing list needs the exact
  provenance marker and matching immutable shape, and an existing field
  needs matching immutable shape. Mutable drift is narrowly reconciled and
  read back. Reruns skip work the script can verify is already correct,
  which it decides by reading the live site rather than by comparing
  release tags. See the [safety model](concepts/safety-model.md).
- **Real column support.** Text, note, choice (with defaults), person,
  date, number, boolean, hyperlink, same-site lookups (including deferred
  circular and self-lookups), **calculated columns** (formulas in the
  mapping), indexes, and unique constraints.
- **Security is part of the schema.** Custom permission levels, site
  groups (with automated owner assignment via CSOM and optional run-scoped
  operator self-enrolment), and broken-inheritance list ACLs with an exact
  allowlist reconciliation mode (`reconcile: exact`) that removes
  undeclared direct grants.
- **The whole lifecycle ships in the bundle.** A read-only
  [site assessment](artifacts/assess.md) before you deploy, optional
  [demo data](artifacts/demo-data.md) to demonstrate with, a
  retention-aware [rollback](artifacts/rollback.md) to tear down, and a
  [reporting pack](artifacts/reporting.md) for Power BI and SQL.

## Where to go next

| To | Read |
| --- | --- |
| Install, build and run a first deploy | [Getting started](getting-started.md) |
| Check a schema against SharePoint's ceilings before you design it | [SharePoint limits you must know](concepts/sharepoint-limits.md) |
| Understand how the pipeline and the generated scripts work | [Concepts](concepts/architecture.md) |
| Know exactly what each generated file does | [Artifacts](artifacts/deploy.md) |
| Look up a DBML construct, mapping key or CLI flag | [DBML](reference/dbml.md), [mapping](reference/mapping.md) and [CLI](reference/cli.md) reference |
| Find out what a validation finding means | [Findings](reference/findings.md), or `dbml-sharepoint explain` |
| Style lists consistently | [Style guide](reference/style-guide.md) |
| Add organisation-specific behaviour | [The extension protocol](concepts/architecture.md#the-extension-protocol) |
| Use the Python API or read a template contract | [API reference](api/index.md) |
| Contribute | [Development](development/philosophy.md), and [CONTRIBUTING.md](https://github.com/firmfooting/dbml-sharepoint/blob/main/CONTRIBUTING.md) on GitHub |
| Report a bug or read the release notes | [Issues](https://github.com/firmfooting/dbml-sharepoint/issues) and [CHANGELOG.md](https://github.com/firmfooting/dbml-sharepoint/blob/main/CHANGELOG.md) on GitHub |
