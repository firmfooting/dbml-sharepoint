# test/test_deployer_stamp.py
"""The deployer a build stamps is the installed package, not a release.yaml value (#687)."""

import importlib.metadata
import tomllib
from pathlib import Path

import pytest
from _paths import FIXTURES, REPO_ROOT
from typer.testing import CliRunner

from dbml_sharepoint import DISTRIBUTION
from dbml_sharepoint.analysis.sidecars import APPLICATION_NAME
from dbml_sharepoint.cli import app

runner = CliRunner()


def _build(tmp_path: Path, release: Path) -> tuple[Path, str]:
    out = tmp_path / "build"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(FIXTURES / "sharepoint-mapping.yaml"),
        "--release", str(release),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--time-zone", "UTC",
        "--site-role", "default",
        "--out", str(out),
    ])
    assert result.exit_code == 0, result.output
    return out, result.output


def test_the_installed_metadata_is_the_one_pyproject_declares() -> None:
    """A stale install would stamp an old version on every site it builds for."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["name"] == DISTRIBUTION
    assert importlib.metadata.version(DISTRIBUTION) == project["project"]["version"]


def test_the_central_log_application_name_does_not_follow_the_distribution() -> None:
    """The type-2 close matches it against rows on live logs, so a rename must not move it."""
    assert APPLICATION_NAME == "dbml-sharepoint"


@pytest.mark.real_deployer_version
def test_a_build_stamps_the_installed_package_version(tmp_path: Path) -> None:
    version = importlib.metadata.version(DISTRIBUTION)
    out, _ = _build(tmp_path, FIXTURES / "release.yaml")
    deploy = (out / "deploy.js.txt").read_text(encoding="utf-8")
    assert f'body.DeployerVersion = "{DISTRIBUTION}/{version}";' in deploy
    assert f" * Deployer:     v{version}\n" in deploy
    assert f"deployer v{version};" in deploy
    manifest = (out / "deploy-manifest.md").read_text(encoding="utf-8")
    assert f"**Deployer version:** {DISTRIBUTION} {version}" in manifest


def test_a_legacy_deployer_version_is_reported_and_not_stamped(tmp_path: Path) -> None:
    legacy = tmp_path / "release.yaml"
    legacy.write_text(
        (FIXTURES / "release.yaml").read_text(encoding="utf-8")
        + 'deployer_version: "dbml-sharepoint/0.1.0"\n',
        encoding="utf-8",
        newline="\n",
    )
    out, output = _build(tmp_path, legacy)
    assert "release_deployer_version_ignored" in output
    assert "dbml-sharepoint/0.1.0" not in (out / "deploy.js.txt").read_text(encoding="utf-8")
