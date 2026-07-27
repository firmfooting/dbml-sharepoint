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

Working from a clone instead — which you want if you are also using the
[templates](https://github.com/shauneccles/dbml-sharepoint/tree/main/templates),
since they ship as files rather than as part of the package:

```bash
git clone https://github.com/shauneccles/dbml-sharepoint
cd dbml-sharepoint
uv sync
uv run dbml-sharepoint version
```

## The three inputs

| File | Owns |
|---|---|
| `schema.dbml` | Tables, columns, types, enums (→ Choice), refs (→ Lookup), notes (→ column descriptions) |
| `mapping.yaml` | List prefix, entity kind/template/site-role, views, widths, indexes, versioning, calculated formulas, formatting, permission levels, groups, per-list ACLs, demo rows |
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
