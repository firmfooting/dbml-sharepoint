---
title: bundle
sidebar_position: 34
---

# `dbml_sharepoint.bundle`

*Packaging: the one emission sequence*

Bundle-level packaging shared by the core and extension CLIs.

A successful build emits a fixed artifact set, the deployment bundle.
This module owns the cross-cutting concerns: the canonical artifact name
list, stale-artifact clearing, platform-stable content hashing, and the
index.md / checksums.txt writers.

The clearing guarantee is about staleness and starts once a build has
accepted its inputs: from that point no failure leaves a pasteable script
from an older build. It deliberately does NOT extend to a refusal that
happens first (a malformed ``--site-url``, an unreadable file), because
such a run has read nothing and made nothing stale, and ``--out`` is
routinely the directory holding the bundle the operator is part-way
through pasting. See ``clear_generated``.

**Every artifact is written UTF-8 with LF, on every platform**, through
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
through ``write_artifact``, and that is the point. It is the guard for a
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

### `VERIFY_SCRIPT`

```python
VERIFY_SCRIPT = 'verify.js.txt'
```

### `REPORT_DIR`

```python
REPORT_DIR = 'reporting'
```

### `REPORT_GUIDE`

```python
REPORT_GUIDE = 'guide.md'
```

### `REPORT_DICTIONARY`

```python
REPORT_DICTIONARY = 'data-dictionary.md'
```

### `REPORT_VIEWS_SQL`

```python
REPORT_VIEWS_SQL = 'views.sql'
```

### `GENERATED_FILES`

```python
GENERATED_FILES = ('deploy.js.txt', 'rollback.js.txt', 'assess.js.txt', 'demo-data.js.txt', 'verify.js.txt', 'deploy-manifest.md', 'assess-manifest.md', 'index.md', 'checksums.txt')
```

### `clear_generated`

```python
def clear_generated(out: pathlib.Path, *, reporting: bool = False) -> None
```

Remove every artifact a previous build may have left in ``out``.

The guarantee is about *staleness*, not about position: once a build has
accepted its inputs, every later failure (validation errors, a seed
refusal, a generator raise) leaves at most a fresh manifest describing
the findings, never a stale script an operator could paste beside it.

A ``--dry-run`` is not a failure and is grouped here only because it too
withholds the scripts: it succeeds, writes a fresh ``deploy-manifest.md``
carrying the deployment plan, and clears the previous scripts for the
same reason. The manifest would otherwise describe one build while the
scripts beside it came from another.

So ``build`` calls this at the point it commits to writing, not as its
first statement. It used to be first, on the reasoning that ANY failure
should clear; but a refusal that happens before a single input file is
read has not made anything stale, and ``--out`` is routinely the
directory holding the bundle the operator is part-way through pasting. A
mistyped ``--site-url`` deleting it was a real loss bought for no
guarantee. ``report`` never made that trade; ``build`` now matches it.

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

The CONTENT is normalised too, not just the newline translation.
``newline="\n"`` only stops Python turning ``\n`` into ``\r\n`` on the
way out; a ``\r`` already inside the string passes straight through. A
template checked out with CRLF, or a mapping value carrying one, would
put CR bytes in the artifact while ``sha256_lf`` hashed them away,
which is the exact divergence between the digest and the bytes on disk
that this whole path exists to close. Normalising here means the
guarantee holds for any input, not just for inputs that were already
clean.

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

Plain sha256sum format, no header lines (keeps ``sha256sum -c``
clean), sorted by relpath, POSIX separators.

That claim is now true on every platform, which it was not before:
``checksums.txt`` itself gained a CR per line on Windows, and sha256sum
reads a trailing CR as part of the FILENAME, so it reported "FAILED
open or read" for every entry. Both this file and the artifacts it
describes go through ``write_artifact`` and are LF everywhere, so the
recorded digest matches the bytes on disk and the standard tools agree.
``test_a_windows_built_bundle_verifies_with_raw_byte_hashing`` pins it.

### `write_index`

```python
def write_index(out: pathlib.Path, *, reporting: bool = False, demo: bool = False, verify: bool = False, env_provenance: dbml_sharepoint.model.env_file.EnvProvenance = EnvProvenance(path=None, digest=None, values=())) -> None
```

Write ``index.md``: what is in the bundle, one row per artifact.

``env_provenance`` defaults to ``NO_ENV_FILE``: this is a documented
composition point extension CLIs call directly, and a required
parameter would break every one of them.

### `emit_bundle`

```python
def emit_bundle(out: pathlib.Path, *, schema: 'Schema', mapping_bundle: 'MappingBundle', release: 'Release', site_url: str, site_role: str, schema_name: str, mapping_name: str, source_mtime: str, generated_at: str, seed: bool, extension: 'DeploymentExtension | None' = None, site_context: 'SiteContext | None' = None, enterprise_reader: str | None = None, env_provenance: dbml_sharepoint.model.env_file.EnvProvenance = EnvProvenance(path=None, digest=None, values=()), deployment_log_list: str | None = None, deployment_log_site: str | None = None, change_log_list: str | None = None, no_sidecars: bool = False) -> str
```

Emit the full post-validation bundle; returns the success message.

The one emission sequence (the deploy, rollback and assess scripts and
the assess manifest, the seed-gated demo script, reporting, index.md and
checksums.txt) shared by the core CLI and every extension CLI. Raises
:class:`SeedRequiresDemoItemsError` before writing anything when
``seed`` is set but the mapping declares no demo rows.

``enterprise_reader`` is already validated by the caller (a malformed
address or a mapping with no ``enroll_enterprise_reader`` group both
refuse before this function is reached); it is passed through unchecked
to ``generate_deploy_js`` so the deploy render context carries it.

``env_provenance`` defaults to ``NO_ENV_FILE`` and is passed through to
``generate_deploy_js`` (the console transcript) and ``write_index``: this
is a documented composition point extension CLIs call directly, and a
required parameter would break every one of them.

