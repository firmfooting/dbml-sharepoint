# test/test_examples.py
"""The two repository examples build under the ordinary pytest gate."""

from pathlib import Path

import pytest
from _paths import REPO_ROOT
from typer.testing import CliRunner

from dbml_sharepoint.cli import app

runner = CliRunner()


@pytest.mark.parametrize("name", ["minimal", "project-tracker"])
def test_shipped_example_builds_end_to_end(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep local pytest and CI responsible for the same shipped schemas.

    Measured before adding this gate and again in review: both builds are fast
    enough for the default suite. The conformance marker would not buy a
    meaningful faster loop, and these examples are exactly what a new validator
    rule can break while every solution-family test remains green.
    """
    example = REPO_ROOT / "examples" / name
    out = tmp_path / name
    monkeypatch.chdir(tmp_path)  # An ambient dbml-sharepoint.env cannot affect the build.

    result = runner.invoke(app, [
        "build",
        "--schema", str(example / "schema.dbml"),
        "--mapping", str(example / "mapping.yaml"),
        "--release", str(example / "release.yaml"),
        "--site-url", "https://example.sharepoint.com/sites/ci",
        "--site-role", "default",
        "--out", str(out),
    ])

    assert result.exit_code == 0, result.output
    assert (out / "deploy.js.txt").is_file()
    assert (out / "rollback.js.txt").is_file()
    assert (out / "assess.js.txt").is_file()
    assert (out / "reporting" / "guide.md").is_file()
