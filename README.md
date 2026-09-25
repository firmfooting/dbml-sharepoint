<h1>
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/firmfooting/branding/main/lockups/dbml-sharepoint_dark.svg">
  <img alt="dbml-sharepoint, by firmfooting"
    src="https://raw.githubusercontent.com/firmfooting/branding/main/lockups/dbml-sharepoint.svg"
    height="56">
</picture>
</h1>

Turn a DBML schema and a YAML mapping into a fail-closed script that
provisions SharePoint Online lists from the browser console.

[![CI](https://github.com/firmfooting/dbml-sharepoint/actions/workflows/ci.yml/badge.svg)](https://github.com/firmfooting/dbml-sharepoint/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/dbml-sharepoint?color=2A6B64)](https://pypi.org/project/dbml-sharepoint/)
[![Python](https://img.shields.io/badge/python-3.13%2B-2A6B64)](https://github.com/firmfooting/dbml-sharepoint/blob/main/pyproject.toml)
[![Licence](https://img.shields.io/badge/licence-MIT-2A6B64)](https://github.com/firmfooting/dbml-sharepoint/blob/main/LICENSE)
[![Docs](https://img.shields.io/badge/docs-firmfooting.github.io-2A6B64)][docs]

`dbml-sharepoint` reads a [DBML](https://dbml.dbdiagram.io/docs/) schema, a
YAML mapping and a release file, and builds an **idempotent, fail-closed,
browser-console `deploy.js.txt`**. That script provisions SharePoint Online
lists and document libraries, with their columns, lookups, views, indexes,
permission levels, groups and ACLs.

It is for site owners and M365 operators who need real lists on a site they
own, and have **no tenant admin rights, no premium licence, and nothing
installed on the target**. If you can open the site and press F12, you can
deploy.

[docs]: https://firmfooting.github.io/dbml-sharepoint/

## At a glance

```text
schema.dbml + mapping.yaml + release.yaml
        |
        v   dbml-sharepoint build
+---------------------------------------------------+
| deploy-manifest.md   <- read first                |
| assess.js.txt        <- probe the site, read-only |
| assess-manifest.md   <- how to read the verdict   |
| deploy.js.txt        <- paste to provision        |
| verify.js.txt        <- check the clock rules     |
| demo-data.js.txt     <- demonstrate (--seed)      |
| rollback.js.txt      <- escape a failed first run |
| reporting/           <- Power BI and SQL          |
| index.md             <- what is in the bundle     |
| checksums.txt        <- SHA-256 of every file     |
+---------------------------------------------------+
        |
        v   paste into the site's browser console (F12)
   SharePoint Online lists, ready to use
```

`verify.js.txt` is emitted only when the pack reads a clock (a `today` or
`now` save rule, a `today` view window, or a `[today]` default).
`demo-data.js.txt` is emitted only with `--seed`. Everything else comes
with every build.

| Artifact | What it is for |
| --- | --- |
| `deploy-manifest.md` | The build report. It opens with the numbered run sequence and must show **0 validation errors**. |
| `assess.js.txt` | A **read-only** probe of the target site's capabilities in three tiers: always-run enumerations (permissions, list templates, lock state, retention labels, locale, features), pack-driven attempt-probes (sealed/AllowDeletion/formatter surfaces, list collisions, version-trim, CSOM availability), and a printed not-assessable block. It prints a `COMPATIBLE / DEGRADED / BLOCKED` verdict for the pack and makes no changes. Paste it in the site's console before a first deploy. `deploy.js.txt` runs the same assessment as its first step. |
| `assess-manifest.md` | What `assess.js.txt` checks, and how to read its verdict. |
| `deploy.js.txt` | The provisioning script. It runs in five phase groups (PREPARE, STRUCTURE, PRESENTATION, PROTECTION, DATA), logs with `[SP-DEPLOY]`, and fails closed phase by phase. |
| `verify.js.txt` | Exercises every date rule, view window and `[today]` default the pack relies on, on one hidden scratch list, and prints `VERIFIED / MISMATCH / NOT-VERIFIED`. Paste it after `deploy.js.txt`. It touches no declared list. |
| `demo-data.js.txt` | Creates the mapping's `[DEMO]`-marked sample rows. |
| `rollback.js.txt` | Deletes the declared lists. It exists for one case: a failed **first** provision on a site with no real data. Never run it against real records. |
| `reporting/` | One Power Query (M) file per list (plus dictionary, model-info and user-added-column audit queries), a SQLCMD views script for warehouse-landed copies, `guide.md` with the Power BI relationship table, and `data-dictionary.md`. The build writes the target site into every query. `dbml-sharepoint report` emits the same queries from the schema alone, with a `SiteUrl` parameter to fill in (layout: `powerquery/`, `sql/`, `guide.md`, `data-dictionary.md`). |
| `index.md`, `checksums.txt` | Every file in the bundle, and the SHA-256 of each. |

## Why

- **Design as code.** Your list schema lives in DBML: reviewable, diffable,
  renderable as an ERD on [dbdiagram.io](https://dbdiagram.io), with indexes
  declared beside their tables. Deployment and presentation mapping
  (prefixes, templates, versioning, views, formatting, ACLs) lives in YAML
  next to it.
- **Deploy with nothing but a browser.** The generated script runs in the
  site's own console under your own login, calling SharePoint REST and CSOM
  endpoints. No PnP, no CSOM installs, no app registrations, no Graph
  consent, no stored credentials. See the [security model][security] and,
  for an honest look at what PnP, site scripts and Graph offer that this
  tool does not, [why not PnP, site scripts, or Graph?][comparison]
- **Fail closed, rerun safely.** Every write is preceded by read-only
  preflights. The wrong site aborts. An existing list needs the exact
  provenance marker and matching immutable shape, and an existing field
  needs matching immutable shape. Mutable drift is narrowly reconciled and
  read back. Reruns skip work the script can verify is already correct,
  which it decides by reading the live site rather than by comparing
  release tags. See the [safety model][safety].
- **Real column support.** Text, note, choice (with defaults), person, date,
  number, boolean, hyperlink, same-site lookups (including deferred
  circular and self-lookups), **calculated columns** (formulas in the
  mapping), indexes, and unique constraints.
- **Security is part of the schema.** Custom permission levels, site groups
  (with automated owner assignment via CSOM and optional run-scoped
  operator self-enrolment), and broken-inheritance list ACLs with an exact
  allowlist reconciliation mode (`reconcile: exact`) that removes
  undeclared direct grants.
- **The whole lifecycle ships in the bundle.** A read-only site assessment
  before you deploy, optional demo data to demonstrate with, a
  retention-aware rollback to tear down, and a reporting pack for Power BI
  and SQL.

[security]: https://firmfooting.github.io/dbml-sharepoint/concepts/security-model
[comparison]: https://firmfooting.github.io/dbml-sharepoint/concepts/comparison
[safety]: https://firmfooting.github.io/dbml-sharepoint/concepts/safety-model

## Install

```bash
uv tool install dbml-sharepoint
# or: pip install dbml-sharepoint
# or, without installing anything: uvx dbml-sharepoint
```

Check it with `dbml-sharepoint version`. The solution templates are part of
the package, so an install is all you need to use them, no clone required.

This page documents `main`, which can be ahead of the latest release on
PyPI. If the released version refuses a flag or a mapping key you see here,
check the [changelog](CHANGELOG.md) or take `main` directly:

```bash
uv tool install git+https://github.com/firmfooting/dbml-sharepoint
```

## Quickstart

Run it with no arguments and pick one of the shipped templates:

```bash
dbml-sharepoint
```

The wizard copies the template you choose into a project directory of your
own, sets your site URL, time zone and (optionally) a list-name prefix,
and offers to build it. It changes identity only. The schema and the
mapping structure are the tested artifacts and are copied as they ship.
Everything it does is also available as flags. It prompts only at a
terminal, and prints help in CI or a pipe.

### Or drive it with flags

A complete worked example lives in
[`examples/project-tracker`](examples/project-tracker):

```bash
dbml-sharepoint build \
  --schema examples/project-tracker/schema.dbml \
  --mapping examples/project-tracker/mapping.yaml \
  --release examples/project-tracker/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --time-zone Region/City \
  --site-role default \
  --out ./build
```

Then:

1. Read `build/deploy-manifest.md`. It opens with step-by-step run
   instructions and must show **0 validation errors**. (`build/index.md`
   lists every artifact, including the `reporting/` queries.)
2. Open `https://yourtenant.sharepoint.com/sites/your-site/_layouts/15/settings.aspx`
   signed in as a Site Owner. It is a classic page, because the script's
   wrong-site guard needs `_spPageContextInfo`.
3. F12 -> Console -> paste the whole of `build/deploy.js.txt` -> Enter.
4. Watch the `[SP-DEPLOY]` lines. Success ends with a summary and
   `errors: []`.
5. If the build emitted `build/verify.js.txt`, paste it next, on the same
   site, and read its verdict.

> The pasteable scripts end in **`.js.txt`**, not `.js`. They exist to be
> opened and copied, never executed from disk, and on Windows a `.js` file
> is bound to Windows Script Host, so double-clicking one runs a
> provisioning script outside the browser. `.js.txt` opens in a text editor
> everywhere. Editors that colour by extension will treat them as plain
> text; rename a copy if you want highlighting while reviewing.

### The three inputs

| File | Owns |
| --- | --- |
| `schema.dbml` | Tables, columns, types, enums (-> Choice), refs (-> Lookup), indexes, notes (-> column descriptions) |
| `mapping.yaml` | List prefix, entity kind/template/site-role, views, versioning, calculated-column formulas, permission levels, groups, per-list ACLs |
| `release.yaml` | Release tag + schema version stamped into every artefact for provenance |

See [`examples/project-tracker/README.md`](examples/project-tracker/README.md)
for a guided tour of all three.

## Documentation

The full documentation is at [firmfooting.github.io/dbml-sharepoint][docs].

| To | Read |
| --- | --- |
| Install, build and run a first deploy | [Getting started](https://firmfooting.github.io/dbml-sharepoint/getting-started) |
| Check a schema against SharePoint's ceilings before you design it | [SharePoint limits you must know](https://firmfooting.github.io/dbml-sharepoint/concepts/sharepoint-limits) |
| Understand how the pipeline and the generated scripts work | [Concepts](https://firmfooting.github.io/dbml-sharepoint/concepts/architecture) |
| Know exactly what each generated file does | [Artifacts](https://firmfooting.github.io/dbml-sharepoint/artifacts/deploy) |
| Look up a DBML construct, mapping key or CLI flag | [DBML](https://firmfooting.github.io/dbml-sharepoint/reference/dbml), [mapping](https://firmfooting.github.io/dbml-sharepoint/reference/mapping) and [CLI](https://firmfooting.github.io/dbml-sharepoint/reference/cli) reference |
| Find out what a validation finding means | [Findings](https://firmfooting.github.io/dbml-sharepoint/reference/findings), or `dbml-sharepoint explain` |
| Style lists consistently | [Style guide](https://firmfooting.github.io/dbml-sharepoint/reference/style-guide). Every mapping inherits the fleet style standard: semantic severity tokens, icons and shapes on SharePoint's own formatting classes. |
| Add organisation-specific behaviour (identity seeding, classification projection, per-site policy) | [The extension protocol](https://firmfooting.github.io/dbml-sharepoint/concepts/architecture#the-extension-protocol) |
| Use the Python API or read a template contract | [API reference](https://firmfooting.github.io/dbml-sharepoint/api/) |
| Contribute | [Development](https://firmfooting.github.io/dbml-sharepoint/development/philosophy) and [CONTRIBUTING.md](CONTRIBUTING.md) |

## Limitations

- SharePoint **Online** only.
- Same-site lookups only. A relationship into a list on another site needs
  the mapping's `cross_site_reference_columns` pattern (a Choice and URL
  pair) instead of a real Lookup.
- Clean first provision + same-release resume. A schema *upgrade* whose
  immutable shapes changed (field types, lookup targets, list templates)
  fails closed for explicit migration rather than guessing.
- Calculated columns cannot reference Lookup, Person, multi-line text, rich
  text, hyperlink or multi-value Choice columns, or `[Today]`. These are
  SharePoint's rules. The build refuses each of them, naming the column and
  the operand, before any script is emitted. See the
  [DBML reference](https://firmfooting.github.io/dbml-sharepoint/reference/dbml#constraints-sharepoint-imposes).
- The browser-paste model means an interactive operator. That is the point
  (no stored credentials, no app principal), but it is not unattended CI.

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md). It covers setup, the gates every
change must pass, and how pull requests are titled and merged. The module
layout and conventions are on the docs site under
[Architecture](https://firmfooting.github.io/dbml-sharepoint/concepts/architecture)
and [Development](https://firmfooting.github.io/dbml-sharepoint/development/philosophy).
Report security issues as described in [SECURITY.md](SECURITY.md).

## Licence

MIT: see [LICENSE](LICENSE).

<!-- markdownlint-disable MD013 -->
---

<sub>Part of <a href="https://github.com/firmfooting">firmfooting</a>: safe, plain tooling for M365 and SharePoint operators. Not affiliated with or endorsed by Microsoft.</sub>
