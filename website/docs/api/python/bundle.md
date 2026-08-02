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

**Every artifact is written UTF-8 with LF, on every platform** — through
``write_artifact``, which is the only writer the emission path may use.

``Path.write_text`` defaults to text mode, so it emits CRLF on Windows and
LF elsewhere. That gave a bundle whose bytes depended on the machine that
built it, and two consequences fell out of it:

1. Raw-byte digests would differ by build platform, so ``sha256_lf``
   hashes LF-normalised content to keep them stable.
2. On Windows that stable digest then described content that was NOT on
   disk, so ``sha256sum -c``, ``Get-FileHash`` and ``certutil`` all
   disagreed with ``checksums.txt``. The bundle could only be verified by
   a bespoke normalising one-liner.

Writing LF unconditionally removes the discrepancy rather than
compensating for it: normalised content IS the content on disk, so the
digests stay platform-stable AND every standard tool validates the bundle.

``sha256_lf`` is deliberately kept. It is a no-op for anything written
through ``write_artifact``, and that is the point — it is the guard for a
writer that bypasses it, which is exactly how the CRLF got in.

### `SeedRequiresDemoItemsError`

--seed was requested but the mapping declares no demo_items.

### `DEPLOY_SCRIPT`

```python
DEPLOY_SCRIPT = 'deploy.js.txt'
```

### `ROLLBACK_SCRIPT`

```python
ROLLBACK_SCRIPT = 'rollback.js.txt'
```

### `ASSESS_SCRIPT`

```python
ASSESS_SCRIPT = 'assess.js.txt'
```

### `DEMO_SCRIPT`

```python
DEMO_SCRIPT = 'demo-data.js.txt'
```

### `GENERATED_FILES`

```python
GENERATED_FILES = ('deploy.js.txt', 'rollback.js.txt', 'assess.js.txt', 'demo-data.js.txt', 'deploy-manifest.md', 'assess-manifest.md', 'INDEX.md', 'checksums.txt')
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

### `write_artifact`

```python
def write_artifact(path: pathlib.Path, text: str) -> None
```

Write one bundle artifact: UTF-8, LF, no BOM. The only writer.

``newline="\n"`` is the whole reason this exists. Fourteen call sites
each spelled ``write_text(text, encoding="utf-8")`` and silently
inherited the platform newline, which is how a Windows build came to
produce a bundle no standard checksum tool could verify. A default
nobody states at the call site is a default nobody reviews.

Creates parent directories: reporting writes into ``reporting/sql/``
and ``reporting/powerquery/``, and having the writer own that keeps
every caller from repeating the mkdir.

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
clean) — sorted by relpath, POSIX separators.

That claim is now true on every platform, which it was not before:
``checksums.txt`` itself gained a CR per line on Windows, and sha256sum
reads a trailing CR as part of the FILENAME, so it reported "FAILED
open or read" for every entry. Both this file and the artifacts it
describes go through ``write_artifact`` and are LF everywhere, so the
recorded digest matches the bytes on disk and the standard tools agree.
``test_a_windows_built_bundle_verifies_with_raw_byte_hashing`` pins it.

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

The one emission sequence — the deploy, rollback and assess scripts and
the assess manifest, the seed-gated demo script, reporting, INDEX.md and
checksums.txt — shared by the core CLI and every extension CLI. Raises
:class:`SeedRequiresDemoItemsError` before writing anything when
``seed`` is set but the mapping declares no demo rows.

