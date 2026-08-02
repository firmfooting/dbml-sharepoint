---
title: bundle
sidebar_position: 20
---

# `dbml_sharepoint.bundle`

*Packaging — the one emission sequence*

Bundle-level packaging shared by the core and extension CLIs.

A successful build emits a fixed artifact set — the deployment bundle.
This module owns the cross-cutting concerns: the canonical artifact name
list, stale-artifact clearing (so no failure mode leaves a pasteable
script from an older build), platform-stable content hashing, and the
INDEX.md / checksums.txt writers.

Hashing is of LF-normalised UTF-8 content: ``Path.write_text`` emits CRLF
on Windows and LF elsewhere, so raw-byte hashes would differ by build
platform. Normalising ``\r\n`` to ``\n`` first makes the digests
stable — the same discipline as the release.yaml config_snapshot pins.

### `SeedRequiresDemoItemsError`

--seed was requested but the mapping declares no demo_items.

### `GENERATED_FILES`

```python
GENERATED_FILES = ('deploy.js', 'rollback.js', 'assess.js', 'demo-data.js', 'deploy-manifest.md', 'assess-manifest.md', 'INDEX.md', 'checksums.txt')
```

### `clear_generated`

```python
def clear_generated(out: pathlib.Path, *, reporting: bool = False) -> None
```

Remove every artifact a previous build may have left in ``out``.

Runs as the first statement of ``build`` so ANY failure mode — usage
error, parse crash, validation failure, dry run — leaves at most a
fresh error manifest, never a stale script an operator could paste.
Unrelated operator files in the directory are deliberately untouched.

### `sha256_lf`

```python
def sha256_lf(text: str) -> str
```

SHA-256 hex digest of ``text`` with CRLF normalised to LF (UTF-8).

### `write_checksums`

```python
def write_checksums(out: pathlib.Path, relpaths: list[str]) -> None
```

Write ``checksums.txt``: one ``&lt;sha256>  &lt;relpath>`` line per artifact.

Plain sha256sum format — no header lines (keeps ``sha256sum -c``
clean) — sorted by relpath, POSIX separators. The verify one-liner
ships in INDEX.md.

### `write_index`

```python
def write_index(out: pathlib.Path, *, reporting: bool = False, demo: bool = False) -> None
```

Write ``INDEX.md``: what is in the bundle, one row per artifact.

### `emit_bundle`

```python
def emit_bundle(out: pathlib.Path, *, schema: 'Schema', mapping_bundle: 'MappingBundle', release: 'Release', site_url: str, site_role: str, schema_name: str, mapping_name: str, source_mtime: str, generated_at: str, seed: bool, extension: 'DeploymentExtension | None' = None, site_context: 'SiteContext | None' = None) -> str
```

Emit the full post-validation bundle; returns the success message.

The one emission sequence — deploy.js, rollback.js, assess.js and its
manifest, the seed-gated demo-data.js, reporting, INDEX.md and
checksums.txt — shared by the core CLI and every extension CLI. Raises
:class:`SeedRequiresDemoItemsError` before writing anything when
``seed`` is set but the mapping declares no demo rows.

