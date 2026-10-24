# test/test_testing_kit.py
"""The node runner, the SharePoint mock and the CI node gate ship in the package.

A dependent loads the gate with `pytest_plugins = ["dbml_sharepoint.testing.plugin"]`
and imports `run_node`, so both have to reach the wheel, and the gate has to
refuse a CI run without node in the dependent's own session, not only in this one.
"""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from _paths import REPO_ROOT

KIT = ("node.py", "sp_mock.py", "plugin.py")


def test_the_kit_imports_from_the_package() -> None:
    from dbml_sharepoint.testing.node import run_node

    assert callable(run_node)


def test_a_ci_run_without_node_is_refused_by_the_plugin(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI", "1")
    monkeypatch.setattr("dbml_sharepoint.testing.node.NODE", None)
    pytester.makeconftest('pytest_plugins = ["dbml_sharepoint.testing.plugin"]')
    pytester.makepyfile("def test_x():\n    pass\n")
    assert pytester.runpytest_inprocess().ret == pytest.ExitCode.USAGE_ERROR


def test_a_local_run_without_node_skips_requires_node_items(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.setattr("dbml_sharepoint.testing.node.NODE", None)
    pytester.makeconftest('pytest_plugins = ["dbml_sharepoint.testing.plugin"]')
    pytester.makepyfile(
        "import pytest\n\n"
        "@pytest.mark.requires_node\n"
        "def test_runs_a_script():\n    pass\n\n"
        "def test_needs_no_node():\n    pass\n",
    )
    pytester.runpytest_inprocess("--strict-markers").assert_outcomes(passed=1, skipped=1)


def test_a_run_with_node_runs_requires_node_items(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CI", "1")
    monkeypatch.setattr("dbml_sharepoint.testing.node.NODE", "/usr/bin/node")
    pytester.makeconftest('pytest_plugins = ["dbml_sharepoint.testing.plugin"]')
    pytester.makepyfile(
        "import pytest\n\n@pytest.mark.requires_node\ndef test_runs_a_script():\n    pass\n",
    )
    pytester.runpytest_inprocess("--strict-markers").assert_outcomes(passed=1)


def test_the_wheel_ships_the_kit(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None, "uv is not on PATH; the wheel cannot be built"
    subprocess.run(
        [uv, "build", "--wheel", "--quiet", "-o", str(tmp_path)], cwd=REPO_ROOT, check=True,
    )
    [wheel] = tmp_path.glob("*.whl")
    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
    missing = [name for name in KIT if f"dbml_sharepoint/testing/{name}" not in names]
    assert not missing, f"the wheel does not ship {missing}"
