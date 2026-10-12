"""The generator import rule fails on a tree that breaks it.

The real tree passing is `uv run lint-imports`, a gate. This proves the
contract text itself can fire, so a mistyped module path cannot go green.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

from _paths import REPO_ROOT


def _contract_from_pyproject() -> str:
    """The shipped contract, so the test cannot drift from the configuration."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "Generators never import analysis checks" in text
    return text


def test_contract_fails_when_a_generator_imports_checks(tmp_path: Path) -> None:
    pkg = tmp_path / "dbml_sharepoint"
    for d in (pkg, pkg / "generators", pkg / "analysis", pkg / "analysis" / "checks"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "generators" / "bad.py").write_text(
        "from dbml_sharepoint.analysis.checks import x\n", encoding="utf-8"
    )
    (pkg / "analysis" / "checks" / "x.py").write_text("", encoding="utf-8")
    pyproject = _contract_from_pyproject()
    start = pyproject.index("\n[tool.importlinter]\n")
    (tmp_path / "pyproject.toml").write_text(pyproject[start:], encoding="utf-8")
    result = subprocess.run(  # noqa: S603 (fixed argv, no untrusted input)
        [
            str(Path(sys.executable).parent / "lint-imports"),
            "--config",
            str(tmp_path / "pyproject.toml"),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
        env={"PYTHONPATH": str(tmp_path)},
    )
    assert result.returncode != 0, textwrap.dedent(result.stdout + result.stderr)
    assert "Generators never import analysis checks" in result.stdout
    assert "BROKEN" in result.stdout
