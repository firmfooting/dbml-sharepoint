# test/test_library_build.py
"""A family with one list and one document library builds end to end.

The fixture under `test/fixtures/library/` is what the shipped-solution
build gate would see for a family holding a library: the build validates
clean, the manifest names the folder phase and the folders, and every
emitted script parses under Node.
"""

import subprocess
from pathlib import Path

import pytest
from _node import NODE
from _paths import FIXTURES

from dbml_sharepoint.analysis.phases import phase_number
from dbml_sharepoint.cli import execute_build

LIBRARY = FIXTURES / "library"


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("library-build")
    execute_build(
        schema=LIBRARY / "schema.dbml",
        mapping=LIBRARY / "mapping.yaml",
        release=FIXTURES / "release.yaml",
        site_url="https://example.sharepoint.com/sites/ci",
        time_zone="UTC",
        site_role="default",
        out=out,
    )
    return out


def test_the_library_family_builds(built: Path) -> None:
    assert (built / "deploy.js.txt").is_file()
    assert (built / "rollback.js.txt").is_file()


def test_the_manifest_names_the_folder_phase_and_its_folders(built: Path) -> None:
    manifest = (built / "deploy-manifest.md").read_text(encoding="utf-8")
    assert f"## Phase {phase_number('folders')}: declared folders" in manifest
    assert "**LIB_Doc**: Clinical services, Corporate services" in manifest


def test_the_deploy_carries_the_library_facts(built: Path) -> None:
    deploy = (built / "deploy.js.txt").read_text(encoding="utf-8")
    assert '"is_library": true' in deploy
    assert '"Clinical services",\n        "Corporate services"' in deploy
    assert '"scope": 1' in deploy
    assert "FileLeafRef" in deploy


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("script", ["deploy.js.txt", "rollback.js.txt"])
def test_every_emitted_script_parses(built: Path, script: str) -> None:
    """The way CI checks a `.js.txt`: piped in, since Node will not read the
    extension, with the CommonJS input type the scripts are written for."""
    assert NODE is not None
    with (built / script).open("rb") as source:
        subprocess.run(  # noqa: S603
            [NODE, "--check", "--input-type=commonjs"],
            stdin=source, check=True, capture_output=True, text=True,
        )
