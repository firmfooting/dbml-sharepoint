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
    from dbml_sharepoint.mapping_loader import MappingBundle
    from dbml_sharepoint.parser import Schema
    from dbml_sharepoint.release import Release


class SeedRequiresDemoItems(ValueError):
    """--seed was requested but the mapping declares no demo_items."""

GENERATED_FILES: tuple[str, ...] = (
    "deploy.js",
    "rollback.js",
    "assess.js",
    "demo-data.js",
    "deploy-manifest.md",
    "assess-manifest.md",
    "INDEX.md",
    "checksums.txt",
)

# INDEX rows: what each artifact IS. The manifest stays authoritative for
# HOW to run the bundle — INDEX carries one pointer line, no step
# duplication, so the run sequence cannot drift between the two.
_INDEX_ROWS: tuple[tuple[str, str], ...] = (
    ("deploy-manifest.md",
     "Build report and the numbered run sequence — read first."),
    ("assess.js",
     "Read-only site capability probe; paste in the target site's console "
     "before deploying."),
    ("assess-manifest.md",
     "What assess.js checks and how to read its COMPATIBLE / DEGRADED / "
     "BLOCKED verdict."),
    ("deploy.js",
     "The provisioning script; paste only after the assess verdict and "
     "manifest review."),
    ("rollback.js",
     "Deletes this pack's lists; ONLY for a failed first provision on an "
     "empty site."),
    ("checksums.txt",
     "SHA-256 integrity hashes for every bundle file (see below)."),
)

_REPORTING_ROW: tuple[str, str] = (
    "reporting/",
    "Power Query M, SQL views, REPORTING.md and the data dictionary for "
    "reporting onboarding.",
)

_DEMO_ROW: tuple[str, str] = (
    "demo-data.js",
    "Optional demo rows (built with --seed): paste AFTER deploy.js. Every "
    "row is '[DEMO] '-marked; delete before active use.",
)


def clear_generated(out: Path, *, reporting: bool = False) -> None:
    """Remove every artifact a previous build may have left in ``out``.

    Runs as the first statement of ``build`` so ANY failure mode — usage
    error, parse crash, validation failure, dry run — leaves at most a
    fresh error manifest, never a stale script an operator could paste.
    Unrelated operator files in the directory are deliberately untouched.
    """
    out.mkdir(parents=True, exist_ok=True)
    for filename in GENERATED_FILES:
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
    (out / "checksums.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


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
        "Run order: follow **How to run this deployment** in "
        "`deploy-manifest.md`.",
        "",
        "Integrity: `checksums.txt` lists the SHA-256 of each file's",
        "LF-normalised UTF-8 bytes (stable across Windows/POSIX line",
        "endings). Verify a file with:",
        "",
        "```bash",
        'python -c "import hashlib,sys;'
        "print(hashlib.sha256(open(sys.argv[1],'rb').read()"
        ".replace(b'\\r\\n',b'\\n')).hexdigest())\" <file>",
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

    The one emission sequence — deploy.js, rollback.js, assess.js and its
    manifest, the seed-gated demo-data.js, reporting, INDEX.md and
    checksums.txt — previously duplicated across the core CLI and every
    extension CLI. Raises :class:`SeedRequiresDemoItems` before writing
    anything when ``seed`` is set but the mapping declares no demo rows.
    """
    # Imports here, not module top: the generators import mapping_loader /
    # parser themselves, and bundle.py stays importable for its pure
    # packaging helpers without pulling the whole generation stack.
    from dbml_sharepoint.assessgen import generate_assess_js, generate_assess_manifest
    from dbml_sharepoint.demogen import generate_demo_js
    from dbml_sharepoint.jsgen import generate_deploy_js
    from dbml_sharepoint.reportgen import emit_reporting
    from dbml_sharepoint.rollbackgen import generate_rollback_js

    if seed and not mapping_bundle.mapping.demo_items:
        raise SeedRequiresDemoItems(
            "--seed requested but the mapping declares no demo_items.",
        )

    (out / "deploy.js").write_text(
        generate_deploy_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, source_mtime=source_mtime,
            generated_at=generated_at,
            extension=extension, site_context=site_context,
        ),
        encoding="utf-8",
    )
    (out / "rollback.js").write_text(
        generate_rollback_js(
            schema=schema, bundle=mapping_bundle, release=release,
            site_url=site_url, site_role=site_role,
            source_dbml=schema_name, generated_at=generated_at,
        ),
        encoding="utf-8",
    )
    (out / "assess.js").write_text(
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
        "deploy-manifest.md", "deploy.js", "rollback.js",
        "assess.js", "assess-manifest.md",
    ]
    if seed:
        (out / "demo-data.js").write_text(
            generate_demo_js(
                schema=schema, bundle=mapping_bundle, release=release,
                site_url=site_url, site_role=site_role,
                source_dbml=schema_name, generated_at=generated_at,
            ),
            encoding="utf-8",
        )
        relpaths.append("demo-data.js")
    relpaths += emit_reporting(
        out, schema, mapping_bundle, site_role,
        release=release, generated_at=generated_at,
        source_schema=schema_name, source_mapping=mapping_name,
    )
    write_index(out, reporting=True, demo=seed)
    relpaths.append("INDEX.md")
    write_checksums(out, relpaths)

    return (
        f"Generated deployment bundle (deploy.js, rollback.js, assess.js, "
        f"{'demo-data.js, ' if seed else ''}manifests, reporting, INDEX.md, "
        f"checksums.txt) in {out}."
    )
