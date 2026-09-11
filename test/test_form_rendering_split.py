"""The forms/form_rendering boundary introduced by #299."""

import ast
import subprocess
import sys
from pathlib import Path

from _paths import PACKAGE

_IMPORT_PROBE = (
    "import importlib, sys\n"
    "importlib.import_module(sys.argv[1])\n"
    "print('\\n'.join(sorted(n for n in sys.modules if n.startswith('dbml_sharepoint'))))\n"
)


def _import_closure(module_name: str) -> set[str]:
    probe = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _IMPORT_PROBE, module_name],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(probe.stdout.split())


def _imports(path: Path) -> list[ast.ImportFrom]:
    return [
        node
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
    ]


def test_form_rendering_import_closure_does_not_load_diagnosis() -> None:
    """Importing the renderer alone must not pull in classified diagnosis."""
    loaded = _import_closure("dbml_sharepoint.analysis.form_rendering")
    assert "dbml_sharepoint.analysis.conditions" not in loaded
    assert "dbml_sharepoint.analysis.findings" not in loaded
    assert not any(name.startswith("dbml_sharepoint.analysis.checks") for name in loaded)


def test_form_rendering_source_does_not_import_findings() -> None:
    """The source text itself must name no findings symbol, not just at runtime."""
    tree = ast.parse(
        (PACKAGE / "analysis/form_rendering.py").read_text(encoding="utf-8"),
    )
    forbidden_names = {"FindingCode", "Finding", "Location", "findings"}
    imported_names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert imported_names.isdisjoint(forbidden_names)
    assert "dbml_sharepoint.analysis.findings" not in imported_names | imported_modules


def test_generators_import_composition_from_form_rendering() -> None:
    """Every `compose_visibility` consumer under src/ takes it from the new module."""
    for relative in ("generators/jsgen.py", "extract/inverse.py"):
        imports = _imports(PACKAGE / relative)
        rendering_names = {
            alias.name
            for node in imports
            if node.module == "dbml_sharepoint.analysis.form_rendering"
            for alias in node.names
        }
        assert "compose_visibility" in rendering_names, relative

    for path in PACKAGE.rglob("*.py"):
        imports = _imports(path)
        assert not any(
            node.module == "dbml_sharepoint.analysis.forms"
            and any(alias.name == "compose_visibility" for alias in node.names)
            for node in imports
        ), path.relative_to(PACKAGE)


def test_forms_keeps_no_compatibility_re_export() -> None:
    """The split refuses a re-export; a consumer that still guesses `analysis.forms` fails."""
    from dbml_sharepoint.analysis import forms

    assert not hasattr(forms, "compose_visibility")
