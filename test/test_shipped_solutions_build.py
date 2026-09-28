# test/test_shipped_solutions_build.py
"""Every shipped solution builds.

CI builds each family under `src/dbml_sharepoint/solutions` in a shell loop
(`.github/workflows/ci.yml`), and until this test existed no local gate did
the same. A combined list rule three characters over SharePoint's formula
limit passed every local gate and failed only in CI (2026-09-02).
"""
from pathlib import Path

import pytest
from _paths import FIXTURES, TEST_BLUEPRINTS

import dbml_sharepoint
from dbml_sharepoint.bundle import DEMO_SCRIPT
from dbml_sharepoint.pipeline import execute_build

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
        time_zone="UTC",
        site_role="default",
        out=tmp_path / family,
    )
    assert (tmp_path / family / "deploy.js.txt").is_file()


def test_the_reporting_sample_builds_seeded_the_way_ci_builds_it(tmp_path: Path) -> None:
    """A seeded build of a pack whose reporting and demo rows sit in side files.

    No shipped pack reaches these paths: derived lookups and counts with no
    description of their own, view totals in the manifest, and the demo
    script with its index row.
    """
    root = TEST_BLUEPRINTS / "reporting-sample"
    execute_build(
        schema=root / "10-design" / "schema.dbml",
        mapping=root / "20-configure" / "mapping.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/ci",
        time_zone="UTC",
        site_role="default",
        out=tmp_path,
        seed=True,
    )
    assert (tmp_path / DEMO_SCRIPT).is_file()
    assert f"`{DEMO_SCRIPT}`" in (tmp_path / "index.md").read_text(encoding="utf-8")
    assert "totals: Minutes sum" in (tmp_path / "deploy-manifest.md").read_text(encoding="utf-8")
    dictionary = (tmp_path / "reporting" / "data-dictionary.md").read_text(encoding="utf-8")
    assert "Score read from the matching Risk row, through the report's own keys." in dictionary
    assert "The count of rows of Action pointing at this one through RelatedRisk." in dictionary
    assert "Computed in the report query; no SharePoint column behind it." in dictionary
