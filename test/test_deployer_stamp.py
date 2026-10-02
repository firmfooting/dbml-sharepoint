# test/test_deployer_stamp.py
"""The deployer a build stamps is the installed package, not a release.yaml value (#687)."""

import importlib.metadata
import tomllib
from collections.abc import Callable
from pathlib import Path

import pytest
from _paths import FIXTURES, REPO_ROOT
from typer.testing import CliRunner

from dbml_sharepoint import APPLICATION_NAME, COMMAND_NAME, DISTRIBUTION
from dbml_sharepoint.analysis.provenance import MARKER_PREFIX
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.cli import app
from dbml_sharepoint.extract.sources import LIVE_FORMAT
from dbml_sharepoint.generators.demogen import generate_demo_js
from dbml_sharepoint.generators.extractgen import generate_extract_js
from dbml_sharepoint.generators.identifygen import PAYLOAD_FORMAT, generate_identify_js
from dbml_sharepoint.generators.maintaingen import (
    generate_columns_js,
    generate_list_js,
    generate_protection_js,
)
from dbml_sharepoint.generators.report_m import (
    generate_dictionary_powerquery,
    generate_powerquery,
)
from dbml_sharepoint.generators.report_md import generate_data_dictionary, generate_reporting_md
from dbml_sharepoint.generators.report_sql import generate_dictionary_sql, generate_sql_views
from dbml_sharepoint.model.env_file import ENV_FILENAME
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release
from dbml_sharepoint.pipeline import execute_build
from dbml_sharepoint.templating import ApplicationNameError, script_env

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


@pytest.mark.parametrize("name", ["Acme's deployer", "a&b", 'say "hi"', "", "x" * 65])
def test_an_application_name_that_could_break_a_script_is_refused(name: str) -> None:
    """The name is rendered into JavaScript strings, CSOM XML and OData filters."""
    with pytest.raises(ApplicationNameError):
        script_env(name)


@pytest.mark.parametrize("generate", [
    generate_powerquery, generate_dictionary_powerquery, generate_sql_views,
    generate_dictionary_sql, generate_reporting_md, generate_data_dictionary,
])
def test_a_reporting_generator_refuses_an_unsafe_application_name(
    generate: Callable[..., object],
) -> None:
    """The reports render the name into SQL and M comments without going through script_env."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    with pytest.raises(ApplicationNameError):
        generate(
            schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
            application="x\nDROP TABLE t",
        ) if generate is generate_data_dictionary else generate(
            schema, bundle, "default", application="x\nDROP TABLE t",
        )


def test_an_unsafe_application_name_leaves_the_last_bundle_in_place(tmp_path: Path) -> None:
    """A refused input must not clear the bundle the operator may be part-way through pasting."""
    out = tmp_path / "build"
    out.mkdir()
    (out / "deploy.js.txt").write_text("the last good bundle", encoding="utf-8", newline="\n")
    with pytest.raises(ApplicationNameError):
        execute_build(
            schema=FIXTURES / "simple.dbml",
            mapping=FIXTURES / "sharepoint-mapping.yaml",
            release=FIXTURES / "release.yaml",
            site_url="https://example.sharepoint.com/sites/test",
            time_zone="UTC",
            site_role="default",
            out=out,
            application="x y",
        )
    assert (out / "deploy.js.txt").read_text(encoding="utf-8") == "the last good bundle"


_OTHER = "other-application"

#: Genuine references to this package that stay whatever identity a build stamps.
_PACKAGE_REFERENCES = (
    MARKER_PREFIX,  # the provenance marker, matched against objects already on live sites
    f"{MARKER_PREFIX.removeprefix('Provisioned by ')} provenance marker",  # names that marker
    ENV_FILENAME,  # the defaults file the command reads
    f"{COMMAND_NAME} extract",  # the command the operator runs next
    f"{COMMAND_NAME} report",
    LIVE_FORMAT,  # the extract payload's format, read back by the command
    PAYLOAD_FORMAT,  # the identify payload's format
)


def _outputs_under_another_identity(tmp_path: Path) -> dict[str, str]:
    """Every file a build writes, plus every script generated outside one."""
    out = tmp_path / "build"
    execute_build(
        schema=FIXTURES / "simple.dbml",
        mapping=FIXTURES / "sharepoint-mapping.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/test",
        time_zone="UTC",
        site_role="default",
        out=out,
        application=_OTHER,
    )
    outputs = {
        path.relative_to(out).as_posix(): path.read_text(encoding="utf-8")
        for path in out.rglob("*")
        if path.is_file()
    }
    site_url = "https://example.sharepoint.com/sites/test"
    outputs["demo-data.js.txt"] = generate_demo_js(
        schema=parse_dbml(FIXTURES / "simple.dbml"),
        bundle=load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url=site_url, site_role="default",
        source_dbml="simple.dbml", generated_at="2026-05-04T00:00:00Z", application=_OTHER,
    )
    outputs["extract.js.txt"] = generate_extract_js(
        site_url=site_url, list_paths=["/sites/test/Lists/Risk"],
        generated_at="2026-05-04T00:00:00Z", application=_OTHER,
    )
    outputs["identify.js.txt"] = generate_identify_js(
        generated_at="2026-05-04T00:00:00Z", application=_OTHER,
    )
    outputs["protection.js.txt"] = generate_protection_js(
        site_url=site_url, list_title="Risk", list_path="/sites/test/Lists/Risk",
        generated_at="2026-05-04T00:00:00Z", application=_OTHER,
    )
    outputs["columns.js.txt"] = generate_columns_js(
        site_url=site_url, list_title="Risk", list_path="/sites/test/Lists/Risk",
        generated_at="2026-05-04T00:00:00Z", application=_OTHER,
    )
    outputs["list.js.txt"] = generate_list_js(
        site_url=site_url, list_title="Risk", list_path="/sites/test/Lists/Risk",
        generated_at="2026-05-04T00:00:00Z", application=_OTHER,
    )
    return outputs


def test_every_stamp_follows_the_application_it_is_given(tmp_path: Path) -> None:
    """The identity comes from the caller; only the version comes from the distribution."""
    outputs = _outputs_under_another_identity(tmp_path)
    # A new identity stamp needs its marker here, or this test cannot see it.
    stamp_markers = (
        "DeployerVersion =", "ApplicationName=", "const APPLICATION =",
        "const EXTERNAL_ROW_PREFIX =", "**Deployer version:**", "Generator",
        "generated by", "Generated by",
    )
    stamps = [
        f"{name}: {line}"
        for name, text in outputs.items()
        for line in text.splitlines()
        if any(marker in line for marker in stamp_markers)
    ]
    found = {marker for marker in stamp_markers if any(marker in line for line in stamps)}
    assert found == set(stamp_markers)
    # deploy.js's security phase and inlined assessment, and assess.js.
    assert sum("ApplicationName=" in line for line in stamps) == 3
    banners = [
        f"{name}: {text.splitlines()[1]}"
        for name, text in outputs.items()
        if name.endswith(".js.txt")
    ]
    assert len(banners) == 10
    for line in (*stamps, *banners):
        assert _OTHER in line, line


def test_no_product_name_survives_under_another_identity(tmp_path: Path) -> None:
    """Only a reference to the package itself may still name it."""
    for name, text in _outputs_under_another_identity(tmp_path).items():
        for reference in _PACKAGE_REFERENCES:
            text = text.replace(reference, "")
        leftovers = [line.strip() for line in text.splitlines() if APPLICATION_NAME in line]
        assert leftovers == [], f"{name}: {leftovers}"


def test_the_command_name_is_the_console_script_pyproject_declares() -> None:
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert COMMAND_NAME in project["project"]["scripts"]


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
