---
title: Getting started
sidebar_position: 2
---

# Getting started

## Install

**Not on PyPI yet.** Install from the repository:

```bash
uv tool install git+https://github.com/shauneccles/dbml-sharepoint
# or, into an existing environment:
pip install git+https://github.com/shauneccles/dbml-sharepoint
```

Either puts the `dbml-sharepoint` command on your path. Check it with
`dbml-sharepoint version`.

The 30 solution templates are part of the package, so an install is all you
need to use them — no clone required.

Working from a clone instead, if you are contributing:

```bash
git clone https://github.com/shauneccles/dbml-sharepoint
cd dbml-sharepoint
uv sync
uv run dbml-sharepoint version
```

## The fastest route: the wizard

Run the command with no arguments:

```bash
dbml-sharepoint
```

It lists the shipped templates, copies the one you pick into a project
directory of your own, sets your list-name prefix and site URL, and offers
to build straight away. You get the whole family — the schema, the mapping,
and the `DEPLOY.md`, `STAFF-GUIDE.md` and `GOVERNANCE.md` written for that
template.

The wizard changes **identity only**: the prefix, the site URL, and where
the files land. It never edits the schema or the structure of the mapping,
because those are the tested artifacts — every template is built end to end
in CI. Once the files are yours, edit them freely.

It is a front end onto `dbml-sharepoint build`, not a separate path:
anything it produces, the flags below could have produced.

:::note Non-interactive use
The wizard prompts only when both stdin and stdout are a terminal. In CI, a
cron job, a Dockerfile or a pipe, a bare `dbml-sharepoint` prints help and
exits 0 — so scripts that already call it are unaffected. Use
`dbml-sharepoint new` to ask for the wizard explicitly.
:::

## The three inputs

| File | Owns |
|---|---|
| `schema.dbml` | Tables, columns, types, enums (→ Choice), refs (→ Lookup), indexes, notes (→ column descriptions) |
| `mapping.yaml` | List prefix, entity kind/template/site-role, views, widths, versioning, calculated formulas, formatting, permission levels, groups, per-list ACLs, demo rows |
| `release.yaml` | Release tag + schema version stamped into every artifact for provenance |

A complete worked example lives in the repository at
`examples/project-tracker` — schema, mapping and release side by side
with a guided README.

## Build the bundle

```bash
dbml-sharepoint build \
  --schema examples/project-tracker/schema.dbml \
  --mapping examples/project-tracker/mapping.yaml \
  --release examples/project-tracker/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

Add `--seed` to also emit [`demo-data.js`](artifacts/demo-data.md) from
the mapping's `demo_items`. Add `--dry-run` to validate without writing
any JS.

The build refuses to proceed on validation errors — the validator is the
same fail-closed gate the deploy script trusts, run at build time where
mistakes are cheap. See the [CLI reference](reference/cli.md) for every
flag.

## Deploy

1. **Read `build/deploy-manifest.md`.** It opens with step-by-step run
   instructions and must show **0 validation errors**. `build/INDEX.md`
   lists every artifact with checksums.
2. *(Optional but recommended on an unfamiliar site)* paste
   `build/assess.js` in the site's console first — it is
   [read-only](artifacts/assess.md) and prints a
   `COMPATIBLE / DEGRADED / BLOCKED` verdict.
3. Open
   `https://yourtenant.sharepoint.com/sites/your-site/_layouts/15/settings.aspx`
   signed in as a Site Owner. (A classic page: the script's wrong-site
   guard needs `_spPageContextInfo`.)
4. F12 → Console → paste the whole of `build/deploy.js` → Enter.
5. Watch the `[SP-DEPLOY]` lines; success ends with a summary and
   `errors: []`.

Rerunning `deploy.js` is safe: verified work is skipped, drift is
reconciled, and anything that cannot be verified fails closed with a
named error instead of guessing.

## Demonstrate, then tear down

```bash
dbml-sharepoint build ... --seed
```

Paste `demo-data.js` after a successful deploy to create the declared
`[DEMO] `-marked sample rows. When the demonstration is over,
`rollback.js` recognises demo-only content and removes it without
ceremony — see [rollback](artifacts/rollback.md) for the exact gates it
applies to anything that is *not* demo content.

## Browse these docs locally

```bash
cd website
npm install
npm start
```

To refresh the [generated API reference](api/index.md) after source
changes:

```bash
uv run python website/scripts/generate_api.py
```
