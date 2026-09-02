# test/test_shipped_solutions_build.py
"""Every shipped solution builds.

CI builds each family under `src/dbml_sharepoint/solutions` in a shell loop
(`.github/workflows/ci.yml`), and until this test existed no local gate did
the same. A combined list rule three characters over SharePoint's formula
limit passed every local gate and failed only in CI (2026-09-02).
"""
from pathlib import Path

import pytest

import dbml_sharepoint
from dbml_sharepoint.cli import execute_build

SOLUTIONS = Path(dbml_sharepoint.__file__).parent / "solutions"
FAMILIES = sorted(p.parent.parent.name for p in SOLUTIONS.glob("*/10-design/schema.dbml"))


def test_the_catalogue_is_not_empty() -> None:
    assert len(FAMILIES) > 1


@pytest.mark.parametrize("family", FAMILIES)
def test_every_shipped_solution_builds_the_way_ci_builds_it(family: str, tmp_path: Path) -> None:
    root = SOLUTIONS / family
    execute_build(
        schema=root / "10-design" / "schema.dbml",
        mapping=root / "20-configure" / "mapping.yaml",
        release=root / "20-configure" / "release.yaml",
        site_url="https://example.sharepoint.com/sites/ci",
        site_role="default",
        out=tmp_path / family,
    )
    assert (tmp_path / family / "deploy.js.txt").is_file()
