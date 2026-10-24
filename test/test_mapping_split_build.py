"""A split mapping builds the bundle its single file built, and the command that splits it."""

import shutil
from pathlib import Path
from typing import cast

import pytest
from _paths import FIXTURES, REPO_ROOT, SOLUTION_TEMPLATES, TEST_BLUEPRINTS
from typer.testing import CliRunner

from dbml_sharepoint.cli import app
from dbml_sharepoint.mapping_split import split_mapping
from dbml_sharepoint.model.yamlio import safe_load
from dbml_sharepoint.pipeline import execute_build

FAMILIES = sorted(p.parent.parent.name for p in SOLUTION_TEMPLATES.glob("*/10-design/schema.dbml"))
# Case to (source folder, schema, mapping, release); a str release lives in the copy.
CASES: dict[str, tuple[Path, str, str, Path | str]] = {
    **{
        family: (
            SOLUTION_TEMPLATES / family,
            "10-design/schema.dbml",
            "20-configure/mapping.yaml",
            "20-configure/release.yaml",
        )
        for family in FAMILIES
    },
    "examples/project-tracker": (
        REPO_ROOT / "examples" / "project-tracker", "schema.dbml", "mapping.yaml", "release.yaml",
    ),
    "test/fixtures/blueprints/reporting-sample": (
        TEST_BLUEPRINTS / "reporting-sample",
        "10-design/schema.dbml",
        "20-configure/mapping.yaml",
        FIXTURES / "release.yaml",
    ),
}


def _build(
    pack: Path, schema: str, mapping: str, release: Path, *, seed: bool, out: Path,
) -> dict[str, bytes]:
    execute_build(
        schema=pack / schema,
        mapping=pack / mapping,
        release=release,
        site_url="https://example.sharepoint.com/sites/ci",
        time_zone="UTC",
        site_role="default",
        out=out,
        seed=seed,
        source_date_epoch=1759276800,
    )
    return _files(out)


def _files(root: Path) -> dict[str, bytes]:
    files = sorted(p for p in root.rglob("*") if p.is_file())
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in files}


def test_every_shipped_family_is_a_case() -> None:
    assert len(FAMILIES) > 1


@pytest.mark.parametrize("case", sorted(CASES))
def test_a_split_mapping_builds_byte_identical(case: str, tmp_path: Path) -> None:
    source, schema, mapping, release = CASES[case]
    pack = tmp_path / "pack"
    shutil.copytree(source, pack)
    release_path = pack / release if isinstance(release, str) else release
    # A seeded build of a mapping without demo rows is refused.
    keys = cast("dict[str, object]", safe_load((pack / mapping).read_text(encoding="utf-8")))
    seed = bool({"demo_items", "demo_source"} & keys.keys())
    out = tmp_path / "out"
    before = _build(pack, schema, mapping, release_path, seed=seed, out=out)
    assert split_mapping(pack / mapping)
    shutil.rmtree(out)
    assert _build(pack, schema, mapping, release_path, seed=seed, out=out) == before


def _mapping(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(SOLUTION_TEMPLATES / "training-register", pack)
    return pack / "20-configure" / "mapping.yaml"


def test_the_command_splits_and_reports(tmp_path: Path) -> None:
    mapping = _mapping(tmp_path)
    result = CliRunner().invoke(app, ["mapping", "split", "--mapping", str(mapping)])
    assert result.exit_code == 0, result.output
    assert "views.yaml: field_sets, views" in result.output
    assert (mapping.parent / "views.yaml").is_file()


def test_a_second_run_has_nothing_to_split(tmp_path: Path) -> None:
    mapping = _mapping(tmp_path)
    CliRunner().invoke(app, ["mapping", "split", "--mapping", str(mapping)])
    files = _files(mapping.parent)
    result = CliRunner().invoke(app, ["mapping", "split", "--mapping", str(mapping)])
    assert result.exit_code == 0, result.output
    assert result.output.strip() == "nothing to split"
    assert _files(mapping.parent) == files


def test_a_refusal_exits_1_with_its_reason(tmp_path: Path) -> None:
    other = _mapping(tmp_path).rename(tmp_path / "pack" / "20-configure" / "other-mapping.yaml")
    result = CliRunner().invoke(app, ["mapping", "split", "--mapping", str(other)])
    assert result.exit_code == 1
    assert "[ERROR]" in result.stderr
    assert "only a file named mapping.yaml" in result.stderr
    assert "[ERROR]" not in result.stdout
