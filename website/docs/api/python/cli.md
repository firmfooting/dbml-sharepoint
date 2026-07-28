---
title: cli
sidebar_position: 22
---

# `dbml_sharepoint.cli`

*Packaging — the command-line interface*

Command-line interface for dbml-sharepoint.

### `validate_site_url`

```python
def validate_site_url(site_url: str) -> None
```

Reject a malformed or non-https ``--site-url`` at parse time.

The URL is interpolated into the generated deploy.js (as ``SITE_URL`` and in
the site-match preflight comparison), so it must be a well-formed absolute
``https://`` URL with a host. Catches typos (``http://``, a bare path, a
missing host) before the operator pastes into a privileged console. Shared
by the core CLI and any extension project CLIs that compose it. Raises
``typer.BadParameter`` (exit 2) on failure.

### `build`

```python
def build(schema: pathlib.Path = ..., mapping: pathlib.Path = ..., release: pathlib.Path = ..., site_url: str = ..., site_role: str = ..., out: pathlib.Path = ..., dry_run: bool = ..., seed: bool = ..., extension: str | None = ...) -> None
```

Generate deploy.js + manifest from the DBML schema and mapping.

### `report`

```python
def report(schema: pathlib.Path = ..., mapping: pathlib.Path = ..., site_role: str = ..., out: pathlib.Path = ..., release: pathlib.Path | None = ...) -> None
```

Generate reporting queries (Power Query M + SQL views) from the schema.

Emits one .pq file per list, a SQLCMD views script, REPORTING.md with
usage instructions and the Power BI relationship table, and a
DATA-DICTIONARY.md companion. Assumes a schema that `build` accepts;
run `build --dry-run` first if unsure.

### `version`

```python
def version() -> None
```

Print the deployer version.

