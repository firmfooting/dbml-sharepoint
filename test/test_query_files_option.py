# test/test_query_files_option.py
"""`reporting.query_files` and `build --no-query-files`: skip the .pq files only."""

import shutil
from pathlib import Path

import pytest
from _paths import FIXTURES
from typer.testing import CliRunner

from dbml_sharepoint.cli import app
from dbml_sharepoint.generators.report_m import generate_powerquery
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

runner = CliRunner()
BASE = FIXTURES / "sharepoint-mapping.yaml"


def _mapping(tmp_path: Path, setting: str | None) -> Path:
    text = BASE.read_text(encoding="utf-8")
    if setting is not None:
        text += f"\nreporting:\n  query_files: {setting}\n"
    # The mapping reads sibling files, so it is written beside the fixtures' copies.
    shutil.copytree(FIXTURES, tmp_path / "fx", dirs_exist_ok=True)
    path = tmp_path / "fx" / "mapping-under-test.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def _build(tmp_path: Path, setting: str | None, *extra: str) -> Path:
    out = tmp_path / "out"
    result = runner.invoke(app, [
        "build",
        "--schema", str(FIXTURES / "simple.dbml"),
        "--mapping", str(_mapping(tmp_path, setting)),
        "--release", str(FIXTURES / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/test",
        "--time-zone", "UTC",
        "--out", str(out),
        *extra,
    ])
    assert result.exit_code == 0, result.output
    return out


def _queries(out: Path) -> list[Path]:
    return sorted((out / "reporting" / "powerquery").glob("*.pq"))


def _listed(out: Path) -> set[str]:
    lines = (out / "checksums.txt").read_text(encoding="utf-8").splitlines()
    return {line.partition("  ")[2] for line in lines}


def test_the_default_writes_the_query_files(tmp_path: Path) -> None:
    out = _build(tmp_path, None)
    assert _queries(out)
    assert "reporting/powerquery/APP_Task.pq" in _listed(out)


def test_the_setting_off_writes_no_query_files(tmp_path: Path) -> None:
    out = _build(tmp_path, "false")
    assert not (out / "reporting" / "powerquery").exists()
    assert (out / "reporting" / "sql" / "views.sql").is_file()
    assert (out / "reporting" / "guide.md").is_file()


def test_the_flag_overrides_the_setting(tmp_path: Path) -> None:
    out = _build(tmp_path, "true", "--no-query-files")
    assert not _queries(out)


def test_the_setting_off_holds_without_the_flag(tmp_path: Path) -> None:
    assert not _queries(_build(tmp_path, "false"))


def test_the_manifest_and_checksums_list_only_what_was_written(tmp_path: Path) -> None:
    out = _build(tmp_path, "false")
    listed = _listed(out)
    assert not any("powerquery" in name for name in listed)
    assert "reporting/sql/views.sql" in listed
    for name in listed:
        assert (out / name).is_file()


def test_the_api_still_returns_every_query_with_the_setting_off(tmp_path: Path) -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(_mapping(tmp_path, "false"))
    assert bundle.mapping.reporting.query_files is False
    assert set(generate_powerquery(schema, bundle, "default")) == {
        "APP_Project.pq", "APP_Task.pq", "APP_AppSettings.pq",
    }


def test_a_non_boolean_setting_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="query_files"):
        load_mapping(_mapping(tmp_path, '"no"'))


def test_a_bundle_without_query_files_never_points_at_one(tmp_path: Path) -> None:
    off = _build(tmp_path / "off", "false")
    for name in ("index.md", "reporting/guide.md"):
        text = (off / name).read_text(encoding="utf-8")
        assert ".pq" not in text
        assert "Power Query M" not in text
    guide = (off / "reporting/guide.md").read_text(encoding="utf-8")
    assert "loadable" not in guide
    assert "_DataDictionary.pq" not in guide
    on = _build(tmp_path / "on", None)
    assert "Power Query M" in (on / "index.md").read_text(encoding="utf-8")
    assert "paste the file contents" in (on / "reporting/guide.md").read_text(encoding="utf-8")
