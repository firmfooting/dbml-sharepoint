import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from dbml_sharepoint import __version__
from dbml_sharepoint.bundle import sha256_lf
from dbml_sharepoint.cli import app
from dbml_sharepoint.extension import BaseExtension

runner = CliRunner()
FIXTURES = Path(__file__).parent / "fixtures"


def test_help_lists_build_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "build" in result.stdout


def test_version_command_available_on_direct_module_run() -> None:
    """Regression: the `version` command must be registered *before* the
    ``if __name__ == "__main__"`` guard. When the module is run directly
    (``python -m dbml_sharepoint.cli``), the guard executes ``app()`` inline, so
    any command defined after it is never registered in that execution mode.
    """
    result = subprocess.run(
        [sys.executable, "-m", "dbml_sharepoint.cli", "version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    # Compare against the package version rather than a literal so
    # release-please version bumps cannot break this regression test.
    assert __version__ in result.stdout


def test_build_writes_deploy_js_and_manifest(tmp_path: Path) -> None:
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    assert (out / "deploy.js").exists()
    assert (out / "deploy-manifest.md").exists()


def test_build_writes_full_bundle(tmp_path: Path) -> None:
    """A plain build (no flags) emits the complete bundle: scripts, both
    manifests, INDEX.md and checksums.txt."""
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    for name in ("deploy.js", "rollback.js", "assess.js", "deploy-manifest.md",
                 "assess-manifest.md", "INDEX.md", "checksums.txt"):
        assert (out / name).exists(), name
    # assess.js stays read-only (no write verbs).
    assert "X-HTTP-Method" not in (out / "assess.js").read_text(encoding="utf-8")
    # The always-generated scripts carry the provenance timestamp.
    assert "Generated at:" in (out / "rollback.js").read_text(encoding="utf-8")
    assert "Generated at:" in (out / "assess.js").read_text(encoding="utf-8")
    # Reporting ships with every build.
    assert (out / "reporting" / "REPORTING.md").exists()
    assert (out / "reporting" / "data-dictionary.md").exists()
    assert (out / "reporting" / "sql" / "views.sql").exists()
    assert list((out / "reporting" / "powerquery").glob("*.pq"))
    assert "`reporting/`" in (out / "INDEX.md").read_text(encoding="utf-8")


def test_build_checksums_validate_and_cover_the_bundle(tmp_path: Path) -> None:
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    lines = (out / "checksums.txt").read_text(encoding="utf-8").splitlines()
    listed = {}
    for line in lines:
        digest, _, relpath = line.partition("  ")
        listed[relpath] = digest
    base = {
        "deploy.js", "rollback.js", "assess.js",
        "deploy-manifest.md", "assess-manifest.md", "INDEX.md",
    }
    assert base <= set(listed)
    assert "reporting/sql/views.sql" in listed
    assert "reporting/REPORTING.md" in listed
    assert "reporting/data-dictionary.md" in listed
    assert any(p.startswith("reporting/powerquery/") for p in listed)
    assert not any("\\" in p for p in listed)
    for relpath, digest in listed.items():
        assert digest == sha256_lf((out / relpath).read_text(encoding="utf-8")), relpath


def test_validation_failure_clears_stale_artifacts(tmp_path: Path) -> None:
    """A failed build must leave only its error manifest — a stale script
    or stale INDEX/checksums beside it could send an operator to the wrong
    release."""
    out = tmp_path / "build"
    out.mkdir()
    for name in ("deploy.js", "rollback.js", "assess.js", "assess-manifest.md",
                 "INDEX.md", "checksums.txt"):
        (out / name).write_text("stale", encoding="utf-8")
    (out / "reporting").mkdir()
    (out / "reporting" / "stale.pq").write_text("stale", encoding="utf-8")
    (out / "operator-notes.txt").write_text("preserve me", encoding="utf-8")
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        (FIXTURES / "simple.dbml")
        .read_text(encoding="utf-8")
        .replace("Status    status     [not null, default: 'Open']", "Status    choice"),
        encoding="utf-8",
    )
    result = runner.invoke(app, [
        "build",
        "--schema", str(bad),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 1
    for name in ("deploy.js", "rollback.js", "assess.js", "assess-manifest.md",
                 "INDEX.md", "checksums.txt"):
        assert not (out / name).exists(), name
    assert not (out / "reporting").exists()
    assert (out / "deploy-manifest.md").exists()
    assert (out / "operator-notes.txt").read_text(encoding="utf-8") == "preserve me"


def test_build_rejects_invalid_site_role(tmp_path: Path) -> None:
    """Regression: a misspelled --site-role must fail fast instead of being
    silently filtered to an empty deploy plan that still exits 0."""
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "commitee",
        "--out", str(out),
    ])
    assert result.exit_code != 0
    assert not (out / "deploy.js").exists()


def test_build_rejects_extension_that_requires_project_cli(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    """A project-only extension must fail before creating any artifact."""

    class ProjectOnlyExtension(BaseExtension):
        name = "project_only"
        requires_project_cli = True

    def resolve_project_only(_name: str | None) -> BaseExtension:
        return ProjectOnlyExtension()

    monkeypatch.setattr(  # type: ignore[attr-defined]
        "dbml_sharepoint.cli.resolve_extension",
        resolve_project_only,
    )
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--extension", "project_only",
    ])

    assert result.exit_code == 2
    assert "requires its project-specific CLI" in result.output
    assert "Use the extension's project CLI instead" in result.output
    # clear_generated ran first (creating out), but nothing was generated.
    assert not any(out.iterdir())


def test_build_rejects_non_https_site_url(tmp_path: Path) -> None:
    """A5: a non-https / malformed --site-url is rejected at parse time (it is
    interpolated into deploy.js and drives the site-match preflight)."""
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "http://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code != 0
    assert not (out / "deploy.js").exists()


def test_build_reports_validation_errors_without_crashing(tmp_path: Path) -> None:
    """Regression: a schema with an unsupported column type must exit via the
    validation-error path (writing a findings manifest, exit 1), not crash
    inside ``build_schema_json`` when ``map_column`` raises ``ValueError``
    before the error-reporting branch runs.
    """
    bad = tmp_path / "bad.dbml"
    bad.write_text(
        (FIXTURES / "simple.dbml")
        .read_text(encoding="utf-8")
        .replace("Status    status     [not null, default: 'Open']", "Status    choice"),
        encoding="utf-8",
    )
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(bad),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 1
    # Must be the deliberate abort, not an unhandled crash in schema rendering.
    assert not isinstance(result.exception, ValueError), result.output
    # The findings manifest is still written before aborting.
    assert (out / "deploy-manifest.md").exists()
    assert not (out / "deploy.js").exists()


def test_build_dry_run_writes_manifest_but_no_js(tmp_path: Path) -> None:
    out = tmp_path / "build"
    out.mkdir()
    for name in ("deploy.js", "rollback.js", "assess.js", "INDEX.md", "checksums.txt"):
        (out / name).write_text("stale", encoding="utf-8")
    (out / "reporting").mkdir()
    (out / "reporting" / "stale.pq").write_text("stale", encoding="utf-8")
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--site-role", "default",
        "--out", str(out),
        "--dry-run",
    ])
    assert result.exit_code == 0, result.output
    for name in ("deploy.js", "rollback.js", "assess.js", "INDEX.md", "checksums.txt"):
        assert not (out / name).exists(), name
    assert not (out / "reporting").exists()
    assert (out / "deploy-manifest.md").exists()
