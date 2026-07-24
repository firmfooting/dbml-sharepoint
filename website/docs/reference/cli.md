---
title: CLI
sidebar_position: 1
---

# CLI reference

```bash
dbml-sharepoint COMMAND [OPTIONS]
```

## `build`

Generate the full deployment bundle (deploy.js, rollback.js, assess.js,
manifests, reporting, INDEX.md, checksums.txt — plus demo-data.js with
`--seed`).

| Option | Default | Meaning |
|---|---|---|
| `--schema PATH` | required | Path to the DBML schema file |
| `--mapping PATH` | required | Path to the mapping YAML |
| `--release PATH` | required | Path to release.yaml |
| `--site-url URL` | required | Target SharePoint site URL |
| `--site-role ROLE` | `default` | Which entities deploy here; must match a `site_role` declared by the mapping's entities |
| `--out PATH` | `./build` | Output directory |
| `--dry-run` | off | Validate only; no JS output |
| `--seed` | off | Also emit demo-data.js from the mapping's `demo_items` |
| `--extension NAME` | mapping's `extension:` | Extension to apply; resolved via entry points |

Behaviour worth knowing:

- Validation errors refuse the build (exit 2) — the manifest lists every
  finding.
- `--site-role` is checked against the roles the mapping actually
  declares; a misspelled role is an error, never a silently empty
  deploy plan.
- An extension that requires its own project CLI causes `build` to exit
  with instructions rather than emitting a half-configured bundle.

## `report`

Emit the reporting pack only (no site URL required): `powerquery/`,
`sql/views.sql`, `REPORTING.md`, `DATA-DICTIONARY.md`.

| Option | Default | Meaning |
|---|---|---|
| `--schema PATH` | required | Path to the DBML schema file |
| `--mapping PATH` | required | Path to the mapping YAML |
| `--site-role ROLE` | `default` | Which entities to include |
| `--out PATH` | `./reports` | Output directory |
| `--release PATH` | optional | Stamp release provenance into the outputs |

## `version`

Print the deployer version.
