# dbml-sharepoint

Turn a [DBML](https://dbml.dbdiagram.io/docs/) schema plus a YAML mapping into
an **idempotent, fail-closed, browser-console `deploy.js.txt`** that provisions
SharePoint Online lists, columns, lookups, indexes, permission levels, groups
and ACLs — with **no tenant admin rights, no premium licence, and nothing
installed on the target**. If you can open the site and press F12, you can
deploy.

```
schema.dbml + mapping.yaml + release.yaml
        │
        ▼   dbml-sharepoint build
┌──────────────────────────────┐
│ deploy-manifest.md  ← read   │
│ deploy.js.txt           ← paste  │
│ rollback.js.txt         ← escape │
└──────────────────────────────┘
        │
        ▼   paste into the site's browser console (F12)
   SharePoint Online lists, ready to use
```

**Documentation: [shauneccles.github.io/dbml-sharepoint](https://shauneccles.github.io/dbml-sharepoint/)** —
getting started, concepts, per-artifact contracts, the full mapping /
DBML / CLI reference, a generated API reference, and the development
philosophy.

## Why

- **Design as code.** Your list schema lives in DBML — reviewable, diffable,
  renderable as an ERD on [dbdiagram.io](https://dbdiagram.io), with indexes
  declared beside their tables. Deployment and presentation mapping
  (prefixes, templates, versioning, views, ACLs) lives in YAML next to it.
- **Deploy with nothing but a browser.** The generated script runs in the
  site's own console under your own login, calling only documented SharePoint
  REST/CSOM endpoints. No PnP, no CSOM installs, no app registrations, no
  Graph consent — see [why not PnP, site scripts, or
  Graph?](website/docs/concepts/comparison.md) for an honest comparison.
- **Fail closed, rerun safely.** Every write is preceded by read-only
  preflights: wrong site aborts, existing lists/fields are adopted only when
  their immutable shape provably matches, mutable drift is narrowly
  reconciled and read back. Reruns skip work the script can verify is
  already correct — which it decides by reading the live site, not by
  comparing release tags.
- **Real column support.** Text, note, choice (+ defaults), person, date,
  number, boolean, hyperlink, same-site lookups (including deferred circular
  and self-lookups), **calculated columns** (formulas in the mapping),
  indexes, and unique constraints.
- **Security is part of the schema.** Custom permission levels, site groups
  (with automated owner assignment via CSOM and optional run-scoped operator
  self-enrolment), broken-inheritance list ACLs with an exact allowlist
  reconciliation mode that removes undeclared grants.

## Install

**Not published to PyPI yet.** Install from the repository:

```bash
uv tool install git+https://github.com/shauneccles/dbml-sharepoint
# or: pip install git+https://github.com/shauneccles/dbml-sharepoint
```

The 30 solution templates are part of the package, so an install is all you
need to use them — no clone required.

Or work from a clone, if you are contributing:

```bash
git clone https://github.com/shauneccles/dbml-sharepoint
cd dbml-sharepoint
uv sync
uv run dbml-sharepoint version
```

## Quickstart

Run it with no arguments and pick one of the 31 shipped templates:

```bash
dbml-sharepoint
```

The wizard copies the template you choose into a project directory of your
own, sets your list-name prefix and site URL, and offers to build it. It
changes identity only — the schema and the mapping structure are the tested
artifacts and are copied as they ship. Everything it does is also available
as flags; it prompts only at a terminal, and prints help in CI or a pipe.

### Or drive it with flags

A complete worked example lives in [`examples/project-tracker`](examples/project-tracker):

```bash
dbml-sharepoint build \
  --schema examples/project-tracker/schema.dbml \
  --mapping examples/project-tracker/mapping.yaml \
  --release examples/project-tracker/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

Then:

1. Read `build/deploy-manifest.md` — it opens with step-by-step run
   instructions and must show **0 validation errors**. (`build/index.md`
   lists every artifact, including the `reporting/` queries.)
2. Open `https://yourtenant.sharepoint.com/sites/your-site/_layouts/15/settings.aspx`
   (a classic page; the script's wrong-site guard needs `_spPageContextInfo`)
   signed in as a Site Owner.
3. F12 → Console → paste the whole of `build/deploy.js.txt` → Enter.
4. Watch the `[SP-DEPLOY]` lines; success ends with a summary and `errors: []`.

> The pasteable scripts end in **`.js.txt`**, not `.js`. They exist to be
> opened and copied, never executed from disk — and on Windows a `.js` file
> is bound to Windows Script Host, so double-clicking one runs a
> provisioning script outside the browser. `.js.txt` opens in a text editor
> everywhere. Editors that colour by extension will treat them as plain
> text; rename a copy if you want highlighting while reviewing.

## The three inputs

| File | Owns |
|---|---|
| `schema.dbml` | Tables, columns, types, enums (→ Choice), refs (→ Lookup), indexes, notes (→ column descriptions) |
| `mapping.yaml` | List prefix, entity kind/template/site-role, views, versioning, calculated-column formulas, permission levels, groups, per-list ACLs |
| `release.yaml` | Release tag + schema version stamped into every artefact for provenance |

See [`examples/project-tracker/README.md`](examples/project-tracker/README.md)
for a guided tour of all three.

## What the generated script does

Phased, logged (`[SP-DEPLOY]`), each phase fail-closed:

0. Read-only preflights (site identity, rights, existing-schema shape), then
   permission levels and site groups (settings reconciled; owner corrected
   via CSOM where possible; optional operator self-enrolment).
1. Lists and non-lookup columns (existing fields verified immutable-shape,
   mutable settings reconciled and read back).
2. Deferred lookups (circular/self references).
3. Indexes and field defaults.
4. Broken-inheritance ACL assignment; `reconcile: exact` removes undeclared
   direct grants.
5. Optional seed rows (via the extension protocol).

Phases are numbered from the phases manifest
(`src/dbml_sharepoint/analysis/phases.py`) — reference steps by name;
numbers renumber automatically when the structure changes.

`rollback.js.txt` deletes the declared lists. It exists for one case: a failed
**first** provision on a site with no real data. Never run it against real
records.

Styling: every mapping inherits the fleet style standard — semantic
severity tokens, icons and shapes on SharePoint's own formatting classes;
see the [style guide](website/docs/reference/style-guide.md).

Assessment: every build emits a **read-only** `assess.js.txt` (+
`assess-manifest.md`) that probes a target site's capabilities across
three tiers — always-run enumerations (permissions, list templates,
lock state, retention labels, locale, features), pack-driven
attempt-probes (sealed/AllowDeletion/formatter surfaces, list
collisions, version-trim, CSOM availability), and a printed
not-assessable honesty block — then prints a
`COMPATIBLE / DEGRADED / BLOCKED` verdict for the pack. It makes no
changes; paste it in the site's console before a first deploy.

Reporting: every build also ships `build/reporting/` — one Power Query
(M) file per list (plus dictionary, model-info and user-added-column
audit queries), a SQLCMD views script for warehouse-landed copies,
`guide.md` with the Power BI relationship table, and
`data-dictionary.md`. Point the queries' `SiteUrl` parameter at the
deployed site. `dbml-sharepoint report` emits the same queries without
needing a site URL (schema-only layout: `powerquery/`, `sql/`,
`guide.md`, `data-dictionary.md`).

## Extension protocol

Organisation-specific behaviour (identity seeding, classification projection,
per-site policy) stays out of the core. Implement `DeploymentExtension`
(hooks: `expand_column`, `seed_lists`, `extra_validators`, `manifest_extras`)
in your own package and register it under the `dbml_sharepoint.extensions`
entry-point group:

```toml
[project.entry-points."dbml_sharepoint.extensions"]
my_org = "my_org_deployer.extension:MyOrgExtension"
```

The core CLI resolves `--extension my_org`; or ship your own thin CLI that
composes the core pipeline programmatically (see `dbml_sharepoint.cli` for
the composition points).

## Limitations (honest ones)

- SharePoint **Online** only, same-site lookups only (SharePoint cannot span
  webs with a lookup).
- Clean first provision + same-release resume. A schema *upgrade* whose
  immutable shapes changed (field types, lookup targets, list templates)
  fails closed for explicit migration rather than guessing.
- Calculated columns can't reference Lookup/Person columns or `[Today]` —
  SharePoint's rules. The validator checks that every reference *names a
  column of the entity*, which catches `[Today]` and typos but **not** a
  Lookup or Person operand: `'=[Owner]'` builds exit 0 and fails at paste
  time with an HTTP 500. Check operand types yourself; see the
  [DBML reference](website/docs/reference/dbml.md#constraints-sharepoint-imposes).
- The browser-paste model means an interactive operator; that is the point
  (no stored credentials, no app principal), but it is not unattended CI.

## Repository map

One module per concern, grouped into layer packages; the packaging
spine sits at the package root:

| Layer | Modules | Responsibility |
|---|---|---|
| `model/` | `parser` · `mapping_loader` · `release` | Parse DBML, the mapping YAML (+ enums/retention), release.yaml into typed objects |
| `analysis/` | `validator` · `ordering` · `typemap` · `phases` · `permissions` · `styles` | Build-time rules (fail-closed), dependency ordering, SP type/formatter/permission projections |
| `generators/` | `jsgen` · `rollbackgen` · `assessgen` · `demogen` · `manifestgen` · `reportgen` | Each renders one artifact family from model + analysis |
| root | `bundle` · `templating` · `cli` · `wizard` · `catalogue` · `extension` | The one emission sequence (`emit_bundle`), stale clearing, INDEX/checksums, the shared Jinja env, the CLI and its interactive wizard, the extension protocol |

The 31 shipped solution templates live in `src/dbml_sharepoint/solutions/`
— inside the package, because only files under it reach the wheel and the
wizard's audience is somebody who ran `uvx dbml-sharepoint` and never
cloned this repository. Not to be confused with `templates/` below, which
is Jinja.

Templates mirror that: `templates/*.js.j2` are the four pasteable scripts;
`templates/_*.js.j2` are shared partials (provenance header, site guard +
`apiUrl`/`odataName`, cached digest, read transport, write headers);
`templates/deploy/_*.js.j2` are deploy.js.txt's phase bodies. Not every
partial goes into every script — `assess.js.txt` deliberately omits
`_http_write.js.j2`, which is what makes its read-only guarantee
structural rather than a promise.

Conventions: underscore-prefixed names are module-private — anything
imported across modules is public and unprefixed. Extension CLIs
compose `clear_generated` → validate → manifest → `emit_bundle` rather
than re-implementing emission.

Full documentation lives at
[shauneccles.github.io/dbml-sharepoint](https://shauneccles.github.io/dbml-sharepoint/),
built from [`website/`](website) — a Docusaurus site; `cd website &&
npm install && npm start` to browse it locally.

## Development

```bash
uv sync
uv run pytest                               # full suite (incl. the semantic Jinja template lint)
uv run ruff check src test website/scripts  # lint
uv run mypy                                 # strict typing: src, test, website/scripts
uv run j2lint --ignore jinja-statements-indentation single-statement-per-line -- src/dbml_sharepoint/templates
```

## License

MIT — see [LICENSE](LICENSE).
