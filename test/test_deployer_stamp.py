# test/test_deployer_stamp.py
"""The deployer a build stamps is the installed package, not a release.yaml value (#687)."""

import importlib.metadata
import tomllib
from pathlib import Path

import pytest
from _paths import FIXTURES, REPO_ROOT
from typer.testing import CliRunner

from dbml_sharepoint import APPLICATION_NAME, DISTRIBUTION
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.cli import app
from dbml_sharepoint.generators.assessgen import generate_assess_js
from dbml_sharepoint.generators.jsgen import build_schema_json, generate_deploy_js
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.generators.report_m import generate_dictionary_powerquery
from dbml_sharepoint.generators.report_md import generate_data_dictionary
from dbml_sharepoint.generators.report_sql import generate_dictionary_sql
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

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


def test_this_package_s_application_name_is_a_literal() -> None:
    """The type-2 close matches it against rows on live logs."""
    assert APPLICATION_NAME == "dbml-sharepoint"


def test_every_stamp_follows_the_application_it_is_given() -> None:
    """The identity comes from the caller; only the version comes from the distribution."""
    other = "other-application"
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    resolved = resolve(schema, bundle.mapping)
    site_url = "https://example.sharepoint.com/sites/test"
    deploy = generate_deploy_js(
        schema=schema, bundle=bundle, release=release, resolved=resolved,
        site_url=site_url, site_role="default",
        source_dbml="simple.dbml", source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", deployment_log_list="Deployments",
        deployment_log_site="logging", application=other,
    )
    assess = generate_assess_js(
        schema=schema, bundle=bundle, resolved=resolved, release=release,
        site_url=site_url, site_role="default",
        source_dbml="simple.dbml", generated_at="2026-05-04T00:00:00Z", application=other,
    )
    manifest = generate_manifest(
        schema_json=build_schema_json(schema, bundle, "default", resolved=resolved),
        resolved=resolved, findings=[], bundle=bundle, release=release,
        site_url=site_url, site_role="default",
        source_dbml="simple.dbml", source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", application=other,
    )
    dictionaries = [
        generate_data_dictionary(
            schema, bundle, "default", resolved=resolved, release=release, application=other,
        ),
        generate_dictionary_powerquery(
            schema, bundle, "default", release=release, application=other,
        )["_ModelInfo.pq"],
        generate_dictionary_sql(schema, bundle, "default", release=release, application=other),
    ]
    stamp_markers = (
        "DeployerVersion =", "ApplicationName=", "const APPLICATION =",
        "const EXTERNAL_ROW_PREFIX =", "**Deployer version:**", "Generator",
    )
    stamps = [
        line
        for text in (deploy, assess, manifest, *dictionaries)
        for line in text.splitlines()
        if any(marker in line for marker in stamp_markers)
    ]
    found = {marker for marker in stamp_markers if any(marker in line for line in stamps)}
    assert found == set(stamp_markers)
    csom = [line for line in stamps if "ApplicationName=" in line]
    assert len(csom) == 3  # deploy's security phase and assessment, and assess.js
    for line in stamps:
        assert other in line, line
        assert APPLICATION_NAME not in line, line


@pytest.mark.real_deployer_version
def test_a_build_stamps_the_installed_package_version(tmp_path: Path) -> None:
    version = importlib.metadata.version(DISTRIBUTION)
    out, _ = _build(tmp_path, FIXTURES / "release.yaml")
    deploy = (out / "deploy.js.txt").read_text(encoding="utf-8")
    assert f'body.DeployerVersion = "{APPLICATION_NAME}/{version}";' in deploy
    assert f" * Deployer:     v{version}\n" in deploy
    assert f"deployer v{version};" in deploy
    manifest = (out / "deploy-manifest.md").read_text(encoding="utf-8")
    assert f"**Deployer version:** {APPLICATION_NAME} {version}" in manifest


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
