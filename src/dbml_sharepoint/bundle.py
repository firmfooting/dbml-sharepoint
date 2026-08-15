# src/dbml_sharepoint/bundle.py
"""Bundle-level packaging shared by the core and extension CLIs.

A successful build emits a fixed artifact set — the deployment bundle.
This module owns the cross-cutting concerns: the canonical artifact name
list, stale-artifact clearing, platform-stable content hashing, and the
index.md / checksums.txt writers.

The clearing guarantee is about staleness and starts once a build has
accepted its inputs: from that point no failure leaves a pasteable script
from an older build. It deliberately does NOT extend to a refusal that
happens first — a malformed ``--site-url``, an unreadable file — because
such a run has read nothing and made nothing stale, and ``--out`` is
routinely the directory holding the bundle the operator is part-way
through pasting. See ``clear_generated``.

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
"""

import hashlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from dbml_sharepoint.model.env_file import NO_ENV_FILE, EnvProvenance, describe_env_provenance

if TYPE_CHECKING:
    from dbml_sharepoint.extension import DeploymentExtension, SiteContext
    from dbml_sharepoint.model.mapping_loader import MappingBundle
    from dbml_sharepoint.model.parser import Schema
    from dbml_sharepoint.model.release import Release


class SeedRequiresDemoItemsError(ValueError):
    """--seed was requested but the mapping declares no demo_items."""

# The pasteable scripts carry a `.js.txt` double extension, not `.js`.
#
# These files exist to be OPENED and COPIED, never executed from disk. On
# Windows a `.js` file is associated with Windows Script Host, so
# double-clicking the deliverable runs it outside the browser instead of
# opening it — the one thing an operator must not do with a provisioning
# script. `.js.txt` opens in the default text editor everywhere, and the
# inner `.js` keeps the artifact self-describing.
#
# Named constants rather than literals at each write site: the name appears
# in the emission, the INDEX row, the checksum manifest and the operator
# instructions, and those four drifting apart is how a manifest comes to
# tell somebody to paste a file the build did not write.
DEPLOY_SCRIPT = "deploy.js.txt"
ROLLBACK_SCRIPT = "rollback.js.txt"
ASSESS_SCRIPT = "assess.js.txt"
DEMO_SCRIPT = "demo-data.js.txt"

# The reporting artifacts, for the reason given directly above -- they were
# the one set still spelled as literals at each write site, and they drifted
# exactly as that comment predicts: `guide.md` was written while six places,
# including the INDEX row and the emitted T-SQL header, still said
# `reporting.md`.
REPORT_DIR = "reporting"
REPORT_GUIDE = "guide.md"
REPORT_DICTIONARY = "data-dictionary.md"
REPORT_VIEWS_SQL = "views.sql"

GENERATED_FILES: tuple[str, ...] = (
    DEPLOY_SCRIPT,
    ROLLBACK_SCRIPT,
    ASSESS_SCRIPT,
    DEMO_SCRIPT,
    "deploy-manifest.md",
    "assess-manifest.md",
    "index.md",
    "checksums.txt",
)

# Every name this bundle has ever emitted, cleared alongside the current
# ones. A directory built by an earlier version still holds a pasteable
# `deploy.js` and an `INDEX.md` that both describe a build that no longer
# exists; clearing only the current names leaves them sitting beside the
# fresh bundle, which is exactly the "stale artifact an operator could
# read, or paste" failure `clear_generated` exists to prevent.
#
# Cheap to keep and additive by nature — a rename adds a row here rather
# than replacing one, because someone may be rebuilding over a bundle from
# any earlier version, not only the immediately preceding one.
_LEGACY_ARTIFACTS: tuple[str, ...] = (
    # Before the `.js.txt` change.
    "deploy.js",
    "rollback.js",
    "assess.js",
    "demo-data.js",
    # Before filenames were normalised out of screaming case.
    "INDEX.md",
)

# INDEX rows: what each artifact IS. The manifest stays authoritative for
# HOW to run the bundle — INDEX carries one pointer line, no step
# duplication, so the run sequence cannot drift between the two.
_INDEX_ROWS: tuple[tuple[str, str], ...] = (
    ("deploy-manifest.md",
     "Build report and the numbered run sequence — read first."),
    (ASSESS_SCRIPT,
     ("Read-only site capability probe; paste in the target site's console "
      "before deploying.")),
    ("assess-manifest.md",
     (f"What {ASSESS_SCRIPT} checks and how to read its COMPATIBLE / "
      "DEGRADED / BLOCKED verdict.")),
    (DEPLOY_SCRIPT,
     ("The provisioning script; paste only after the assess verdict and "
      "manifest review.")),
    (ROLLBACK_SCRIPT,
     ("Deletes this pack's lists; ONLY for a failed first provision on an "
      "empty site.")),
    ("checksums.txt",
     "SHA-256 integrity hashes for every bundle file (see below)."),
)

_REPORTING_ROW: tuple[str, str] = (
    f"{REPORT_DIR}/",
    (f"Power Query M, SQL views, {REPORT_GUIDE} and the data dictionary for "
     "reporting onboarding."),
)

_DEMO_ROW: tuple[str, str] = (
    DEMO_SCRIPT,
    (f"Optional demo rows (built with --seed): paste AFTER {DEPLOY_SCRIPT}. "
     "Every row is '[DEMO] '-marked; delete before active use."),
)


def clear_generated(out: Path, *, reporting: bool = False) -> None:
    """Remove every artifact a previous build may have left in ``out``.

    The guarantee is about *staleness*, not about position: once a build has
    accepted its inputs, every later failure — validation errors, a seed
    refusal, a generator raise — leaves at most a fresh manifest describing
    the findings, never a stale script an operator could paste beside it.

    A ``--dry-run`` is not a failure and is grouped here only because it too
    withholds the scripts: it succeeds, writes a fresh ``deploy-manifest.md``
    carrying the deployment plan, and clears the previous scripts for the
    same reason — the manifest would otherwise describe one build while the
    scripts beside it came from another.

    So ``build`` calls this at the point it commits to writing, not as its
    first statement. It used to be first, on the reasoning that ANY failure
    should clear; but a refusal that happens before a single input file is
    read has not made anything stale, and ``--out`` is routinely the
    directory holding the bundle the operator is part-way through pasting. A
    mistyped ``--site-url`` deleting it was a real loss bought for no
    guarantee. ``report`` never made that trade; ``build`` now matches it.

    Unrelated operator files in the directory are deliberately untouched.
    """
    out.mkdir(parents=True, exist_ok=True)
    for filename in (*GENERATED_FILES, *_LEGACY_ARTIFACTS):
        (out / filename).unlink(missing_ok=True)
    if reporting:
        shutil.rmtree(out / "reporting", ignore_errors=True)


def write_artifact(path: Path, text: str) -> None:
    """Write one bundle artifact: UTF-8, LF, no BOM. The only writer.

    ``newline="\\n"`` is the whole reason this exists. Fourteen call sites
    each spelled ``write_text(text, encoding="utf-8")`` and silently
    inherited the platform newline, which is how a Windows build came to
    produce a bundle no standard checksum tool could verify. A default
    nobody states at the call site is a default nobody reviews.

    The CONTENT is normalised too, not just the newline translation.
    ``newline="\\n"`` only stops Python turning ``\\n`` into ``\\r\\n`` on the
    way out; a ``\\r`` already inside the string passes straight through. A
    template checked out with CRLF, or a mapping value carrying one, would
    put CR bytes in the artifact while ``sha256_lf`` hashed them away —
    which is the exact divergence between the digest and the bytes on disk
    that this whole path exists to close. Normalising here means the
    guarantee holds for any input, not just for inputs that were already
    clean.

    Creates parent directories: reporting writes into ``reporting/sql/``
    and ``reporting/powerquery/``, and having the writer own that keeps
    every caller from repeating the mkdir.
    """
    normalised = text.replace("\r\n", "\n").replace("\r", "\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(normalised, encoding="utf-8", newline="\n")


def sha256_lf(text: str) -> str:
    """SHA-256 hex digest of ``text`` with CRLF normalised to LF (UTF-8)."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def write_checksums(out: Path, relpaths: list[str]) -> None:
    """Write ``checksums.txt``: one ``<sha256>  <relpath>`` line per artifact.

    Plain sha256sum format — no header lines (keeps ``sha256sum -c``
    clean) — sorted by relpath, POSIX separators.

    That claim is now true on every platform, which it was not before:
    ``checksums.txt`` itself gained a CR per line on Windows, and sha256sum
    reads a trailing CR as part of the FILENAME, so it reported "FAILED
    open or read" for every entry. Both this file and the artifacts it
    describes go through ``write_artifact`` and are LF everywhere, so the
    recorded digest matches the bytes on disk and the standard tools agree.
    ``test_a_windows_built_bundle_verifies_with_raw_byte_hashing`` pins it.
    """
    # Hash the BYTES on disk, which is what a verifier hashes. Digesting
    # the string through sha256_lf made the manifest describe normalised
    # content rather than the file, so the two could disagree while every
    # test that used sha256_lf on both sides still passed. Reading back is
    # also the only thing that proves what was actually written.
    lines = [
        f"{hashlib.sha256((out / relpath).read_bytes()).hexdigest()}  {relpath}"
        for relpath in sorted(relpaths)
    ]
    write_artifact(out / "checksums.txt", "\n".join(lines) + "\n")


def write_index(
    out: Path,
    *,
    reporting: bool = False,
    demo: bool = False,
    env_provenance: EnvProvenance = NO_ENV_FILE,
) -> None:
    """Write ``index.md``: what is in the bundle, one row per artifact.

    ``env_provenance`` defaults to ``NO_ENV_FILE``: this is a documented
    composition point extension CLIs call directly, and a required
    parameter would break every one of them.
    """
    rows = list(_INDEX_ROWS)
    if demo:
        rows.append(_DEMO_ROW)
    if reporting:
        rows.append(_REPORTING_ROW)
    lines = [
        "# Deployment bundle index",
        "",
        f"**Env file:** {describe_env_provenance(env_provenance)}",
        "",
        "| File | Purpose |",
        "|---|---|",
        *(f"| `{name}` | {purpose} |" for name, purpose in rows),
        "",
        ("Run order: follow **How to run this deployment** in "
         "`deploy-manifest.md`."),
        "",
        ("Integrity: `checksums.txt` lists the SHA-256 of every file, in "
         "plain"),
        ("`sha256sum` format. Every artifact is written UTF-8 with LF on "
         "every"),
        ("platform, so the digests describe the bytes on disk and a bundle "
         "built"),
        "on Windows and one built on Linux are identical.",
        "",
        "Verify the whole bundle from this directory:",
        "",
        "```bash",
        "sha256sum -c checksums.txt",
        "```",
        "",
        "PowerShell, with no extra tools installed:",
        "",
        "```powershell",
        ("Get-Content checksums.txt | ForEach-Object { $h, $f = $_ -split "
         "'  ', 2"),
        ("  if ((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash -ine "
         "$h) { \"FAILED: $f\" } }"),
        "```",
    ]
    write_artifact(out / "index.md", "\n".join(lines) + "\n")


def emit_bundle(
    out: Path,
    *,
    schema: "Schema",
    mapping_bundle: "MappingBundle",
    release: "Release",
    site_url: str,
    site_role: str,
    schema_name: str,
    mapping_name: str,
    source_mtime: str,
    generated_at: str,
    seed: bool,
    extension: "DeploymentExtension | None" = None,
    site_context: "SiteContext | None" = None,
    enterprise_reader: str | None = None,
    env_provenance: EnvProvenance = NO_ENV_FILE,
) -> str:
    """Emit the full post-validation bundle; returns the success message.

    The one emission sequence — the deploy, rollback and assess scripts and
    the assess manifest, the seed-gated demo script, reporting, index.md and
    checksums.txt — shared by the core CLI and every extension CLI. Raises
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
    """
    # Imports here, not module top: the generators import mapping_loader /
    # parser themselves, and bundle.py stays importable for its pure
    # packaging helpers without pulling the whole generation stack.
    from dbml_sharepoint.generators.assessgen import (  # noqa: PLC0415
        generate_assess_js,
        generate_assess_manifest,
    )
    from dbml_sharepoint.generators.demogen import generate_demo_js  # noqa: PLC0415
    from dbml_sharepoint.generators.jsgen import generate_deploy_js  # noqa: PLC0415
    from dbml_sharepoint.generators.reportgen import emit_reporting  # noqa: PLC0415
    from dbml_sharepoint.generators.rollbackgen import generate_rollback_js  # noqa: PLC0415

    if seed and not mapping_bundle.mapping.demo_items:
        raise SeedRequiresDemoItemsError(
            "--seed requested but the mapping declares no demo_items.",
        )

    write_artifact(
        out / DEPLOY_SCRIPT,
        generate_deploy_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, source_mtime=source_mtime,
            generated_at=generated_at,
            extension=extension, site_context=site_context,
            enterprise_reader=enterprise_reader,
            env_provenance=env_provenance,
        ),
    )
    write_artifact(
        out / ROLLBACK_SCRIPT,
        generate_rollback_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, generated_at=generated_at,
        ),
    )
    write_artifact(
        out / ASSESS_SCRIPT,
        generate_assess_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, generated_at=generated_at,
        ),
    )
    write_artifact(
        out / "assess-manifest.md",
        generate_assess_manifest(
            schema=schema, bundle=mapping_bundle,
            site_url=site_url, site_role=site_role,
        ),
    )

    relpaths = [
        "deploy-manifest.md", DEPLOY_SCRIPT, ROLLBACK_SCRIPT,
        ASSESS_SCRIPT, "assess-manifest.md",
    ]
    if seed:
        write_artifact(
            out / DEMO_SCRIPT,
            generate_demo_js(
                schema=schema, bundle=mapping_bundle, release=release,
                site_url=site_url, site_role=site_role,
                source_dbml=schema_name, generated_at=generated_at,
            ),
        )
        relpaths.append(DEMO_SCRIPT)
    relpaths += emit_reporting(
        out, schema, mapping_bundle, site_role,
        release=release, generated_at=generated_at,
        source_schema=schema_name, source_mapping=mapping_name,
        # The build knows where this is going, so the reporting pack does
        # not have to ask. Only `report`, which has no site, falls back to
        # the SiteUrl parameter.
        site_url=site_url,
    )
    write_index(out, reporting=True, demo=seed, env_provenance=env_provenance)
    relpaths.append("index.md")
    write_checksums(out, relpaths)

    return (
        f"Generated deployment bundle ({DEPLOY_SCRIPT}, {ROLLBACK_SCRIPT}, "
        f"{ASSESS_SCRIPT}, {f'{DEMO_SCRIPT}, ' if seed else ''}manifests, "
        f"reporting, index.md, checksums.txt) in {out}."
    )
