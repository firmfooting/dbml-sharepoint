"""The generator import rule fails on a tree that breaks it.

The real tree passing is `uv run lint-imports`, a gate. This proves the
contract text itself can fire, so a mistyped module path cannot go green.
"""

import os
import re
import subprocess
import sys
from pathlib import Path

from _paths import REPO_ROOT


def test_contract_fails_when_a_generator_imports_checks(tmp_path: Path) -> None:
    pkg = tmp_path / "dbml_sharepoint"
    for d in (pkg, pkg / "generators", pkg / "analysis", pkg / "analysis" / "checks"):
        d.mkdir(parents=True, exist_ok=True)
        (d / "__init__.py").write_text("", encoding="utf-8")
    (pkg / "generators" / "bad.py").write_text(
        "from dbml_sharepoint.analysis.checks import x\n", encoding="utf-8"
    )
    (pkg / "analysis" / "checks" / "x.py").write_text("", encoding="utf-8")
    pyproject = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    # Only the importlinter tables: a table added after them must not leak into the config.
    tables = re.findall(r"^\[+tool\.importlinter[^\n]*\n(?:(?!\[).*\n)*", pyproject, re.MULTILINE)
    contract = "".join(tables)
    assert "Generators never import analysis checks" in contract
    (tmp_path / "pyproject.toml").write_text(contract, encoding="utf-8")
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
        env={**os.environ, "PYTHONPATH": str(tmp_path)},
    )
    assert result.returncode != 0, result.stdout + result.stderr
    assert "Generators never import analysis checks" in result.stdout
    assert "BROKEN" in result.stdout
