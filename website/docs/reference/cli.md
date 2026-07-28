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

- Validation errors refuse the build — the manifest lists every finding.
- `--site-role` is checked against the roles the mapping actually
  declares; a misspelled role is an error, never a silently empty
  deploy plan.
- `--dry-run` still writes `deploy-manifest.md`, so you can read the
  findings and the deployment plan. It is the JS that is withheld.
- An extension that requires its own project CLI causes `build` to exit
  with instructions rather than emitting a half-configured bundle.

## Exit codes

Measured, because a CI gate keys on these:

| Code | Meaning |
|---|---|
| `0` | Success, including a `--dry-run` that found no errors |
| `1` | The build refused: validation errors, or an unreadable/invalid input file |
| `2` | Usage error — a missing required option, or a `--site-role` the mapping does not declare |

A validation failure exits **1**, not 2. `2` is the usage-error code
`typer` raises before the pipeline runs at all. Gate on non-zero rather
than on a specific code.

An invalid `mapping.yaml` currently prints a Python traceback above the
one useful sentence. The message at the bottom is the actionable part; the
frames above it are noise, not a crash.

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
