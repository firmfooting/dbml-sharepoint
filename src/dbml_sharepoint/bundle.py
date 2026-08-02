# src/dbml_sharepoint/bundle.py
"""Bundle-level packaging shared by the core and extension CLIs.

A successful build emits a fixed artifact set — the deployment bundle.
This module owns the cross-cutting concerns: the canonical artifact name
list, stale-artifact clearing (so no failure mode leaves a pasteable
script from an older build), platform-stable content hashing, and the
INDEX.md / checksums.txt writers.

Hashing is of LF-normalised UTF-8 content: ``Path.write_text`` emits CRLF
on Windows and LF elsewhere, so raw-byte hashes would differ by build
platform. Normalising ``\\r\\n`` to ``\\n`` first makes the digests
stable — the same discipline as the release.yaml config_snapshot pins.
"""

import hashlib
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

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

GENERATED_FILES: tuple[str, ...] = (
    DEPLOY_SCRIPT,
    ROLLBACK_SCRIPT,
    ASSESS_SCRIPT,
    DEMO_SCRIPT,
    "deploy-manifest.md",
    "assess-manifest.md",
    "INDEX.md",
    "checksums.txt",
)

# What the scripts were called before the `.js.txt` change. Cleared by
# `clear_generated` alongside the current names, because a directory built
# by an earlier version still holds a pasteable `deploy.js` — and clearing
# only the new names would leave the stale one sitting beside the fresh
# bundle, which is exactly the "stale script an operator could paste"
# failure `clear_generated` exists to prevent. Cheap to keep; the cost of
# dropping it is paid by somebody pasting last month's provisioning run.
_LEGACY_SCRIPTS: tuple[str, ...] = (
    "deploy.js",
    "rollback.js",
    "assess.js",
    "demo-data.js",
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
    "reporting/",
    ("Power Query M, SQL views, REPORTING.md and the data dictionary for "
     "reporting onboarding."),
)

_DEMO_ROW: tuple[str, str] = (
    DEMO_SCRIPT,
    (f"Optional demo rows (built with --seed): paste AFTER {DEPLOY_SCRIPT}. "
     "Every row is '[DEMO] '-marked; delete before active use."),
)


def clear_generated(out: Path, *, reporting: bool = False) -> None:
    """Remove every artifact a previous build may have left in ``out``.

    Runs as the first statement of ``build`` so ANY failure mode — usage
    error, parse crash, validation failure, dry run — leaves at most a
    fresh error manifest, never a stale script an operator could paste.
    Unrelated operator files in the directory are deliberately untouched.
    """
    out.mkdir(parents=True, exist_ok=True)
    for filename in (*GENERATED_FILES, *_LEGACY_SCRIPTS):
        (out / filename).unlink(missing_ok=True)
    if reporting:
        shutil.rmtree(out / "reporting", ignore_errors=True)


def sha256_lf(text: str) -> str:
    """SHA-256 hex digest of ``text`` with CRLF normalised to LF (UTF-8)."""
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def write_checksums(out: Path, relpaths: list[str]) -> None:
    """Write ``checksums.txt``: one ``<sha256>  <relpath>`` line per artifact.

    Plain sha256sum format — no header lines (keeps ``sha256sum -c``
    clean) — sorted by relpath, POSIX separators. The verify one-liner
    ships in INDEX.md.
    """
    lines = [
        f"{sha256_lf((out / relpath).read_text(encoding='utf-8'))}  {relpath}"
        for relpath in sorted(relpaths)
    ]
    # newline="\n", not the platform default. This file is machine-readable
    # input, and the docstring above promises "plain sha256sum format ...
    # keeps `sha256sum -c` clean". Written in text mode on Windows every
    # line gains a CR, which sha256sum takes as part of the FILENAME -- it
    # reports "rollback.js.txt: FAILED open or read" for every entry, so the
    # format claim was false for any bundle built on Windows.
    #
    # Scope, so nobody reads more into this than it does: it makes the file
    # WELL-FORMED, not the bundle sha256sum-verifiable. The digests are of
    # LF-normalised bytes (see sha256_lf), so on a Windows-built bundle
    # whose artifacts sit on disk with CRLF the hashes still will not match
    # bare `sha256sum -c`. That is deliberate, and INDEX.md documents it by
    # advertising an LF-normalising Python one-liner rather than sha256sum.
    # On a POSIX-built bundle the two agree and `-c` works.
    (out / "checksums.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n",
    )


def write_index(out: Path, *, reporting: bool = False, demo: bool = False) -> None:
    """Write ``INDEX.md``: what is in the bundle, one row per artifact."""
    rows = list(_INDEX_ROWS)
    if demo:
        rows.append(_DEMO_ROW)
    if reporting:
        rows.append(_REPORTING_ROW)
    lines = [
        "# Deployment bundle index",
        "",
        "| File | Purpose |",
        "|---|---|",
        *(f"| `{name}` | {purpose} |" for name, purpose in rows),
        "",
        ("Run order: follow **How to run this deployment** in "
         "`deploy-manifest.md`."),
        "",
        "Integrity: `checksums.txt` lists the SHA-256 of each file's",
        "LF-normalised UTF-8 bytes (stable across Windows/POSIX line",
        "endings). Verify a file with:",
        "",
        "```bash",
        ('python -c "import hashlib,sys;'
         "print(hashlib.sha256(open(sys.argv[1],'rb').read()"
         ".replace(b'\\r\\n',b'\\n')).hexdigest())\" <file>"),
        "```",
    ]
    (out / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
) -> str:
    """Emit the full post-validation bundle; returns the success message.

    The one emission sequence — the deploy, rollback and assess scripts and
    the assess manifest, the seed-gated demo script, reporting, INDEX.md and
    checksums.txt — shared by the core CLI and every extension CLI. Raises
    :class:`SeedRequiresDemoItemsError` before writing anything when
    ``seed`` is set but the mapping declares no demo rows.
    """
    # Imports here, not module top: the generators import mapping_loader /
    # parser themselves, and bundle.py stays importable for its pure
    # packaging helpers without pulling the whole generation stack.
    from dbml_sharepoint.generators.assessgen import generate_assess_js, generate_assess_manifest
    from dbml_sharepoint.generators.demogen import generate_demo_js
    from dbml_sharepoint.generators.jsgen import generate_deploy_js
    from dbml_sharepoint.generators.reportgen import emit_reporting
    from dbml_sharepoint.generators.rollbackgen import generate_rollback_js

    if seed and not mapping_bundle.mapping.demo_items:
        raise SeedRequiresDemoItemsError(
            "--seed requested but the mapping declares no demo_items.",
        )

    (out / DEPLOY_SCRIPT).write_text(
        generate_deploy_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, source_mtime=source_mtime,
            generated_at=generated_at,
            extension=extension, site_context=site_context,
        ),
        encoding="utf-8",
    )
    (out / ROLLBACK_SCRIPT).write_text(
        generate_rollback_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, generated_at=generated_at,
        ),
        encoding="utf-8",
    )
    (out / ASSESS_SCRIPT).write_text(
        generate_assess_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, generated_at=generated_at,
        ),
        encoding="utf-8",
    )
    (out / "assess-manifest.md").write_text(
        generate_assess_manifest(
            schema=schema, bundle=mapping_bundle,
            site_url=site_url, site_role=site_role,
        ),
        encoding="utf-8",
    )

    relpaths = [
        "deploy-manifest.md", DEPLOY_SCRIPT, ROLLBACK_SCRIPT,
        ASSESS_SCRIPT, "assess-manifest.md",
    ]
    if seed:
        (out / DEMO_SCRIPT).write_text(
            generate_demo_js(
                schema=schema, bundle=mapping_bundle, release=release,
                site_url=site_url, site_role=site_role,
                source_dbml=schema_name, generated_at=generated_at,
            ),
            encoding="utf-8",
        )
        relpaths.append(DEMO_SCRIPT)
    relpaths += emit_reporting(
        out, schema, mapping_bundle, site_role,
        release=release, generated_at=generated_at,
        source_schema=schema_name, source_mapping=mapping_name,
    )
    write_index(out, reporting=True, demo=seed)
    relpaths.append("INDEX.md")
    write_checksums(out, relpaths)

    return (
        f"Generated deployment bundle ({DEPLOY_SCRIPT}, {ROLLBACK_SCRIPT}, "
        f"{ASSESS_SCRIPT}, {f'{DEMO_SCRIPT}, ' if seed else ''}manifests, "
        f"reporting, INDEX.md, checksums.txt) in {out}."
    )
