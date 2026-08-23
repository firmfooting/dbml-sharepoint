# test/test_condition_description.py
"""Condition prose and the import boundary that keeps it generator-safe."""

import ast
import subprocess
import sys
from pathlib import Path

import pytest
from _paths import PACKAGE

from dbml_sharepoint.analysis import condition_description, conditions
from dbml_sharepoint.analysis.condition_description import describe
from dbml_sharepoint.model import conditions as model_conditions
from dbml_sharepoint.model.conditions import VALUELESS_OPS, Condition, Group, Leaf

#: Previous `analysis.conditions.describe` outputs, captured before the move.
DESCRIBED: list[tuple[str, Condition, str]] = [
    ("leaf", Leaf("Status", "eq", "Open"), "Status eq 'Open'"),
    ("list-value", Leaf("Status", "in", ["A", "B"]), "Status in ['A', 'B']"),
    ("property", Leaf("Owner", "eq", "a@b.c", property="email"), "Owner.email eq 'a@b.c'"),
    ("measure", Leaf("Note", "gt", 10, measure="length"), "length(Note) gt 10"),
    (
        "property-and-measure",
        Leaf("Owner", "gt", 3, property="title", measure="length"),
        "length(Owner.title) gt 3",
    ),
    ("is-null", Leaf("Note", "is_null"), "Note is_null"),
    ("membership", Leaf("Events", "includes", "View"), "Events includes 'View'"),
    ("all-of-one", Group("all_of", (Leaf("A", "eq", 1),)), "A eq 1"),
    (
        "all-of-two",
        Group("all_of", (Leaf("A", "eq", 1), Leaf("B", "eq", 2))),
        "(A eq 1 AND B eq 2)",
    ),
    (
        "any-of-two",
        Group("any_of", (Leaf("A", "eq", 1), Leaf("B", "eq", 2))),
        "(A eq 1 OR B eq 2)",
    ),
    ("none-of-one", Group("none_of", (Leaf("A", "eq", 1),)), "NOT(A eq 1)"),
    (
        "none-of-two",
        Group("none_of", (Leaf("A", "eq", 1), Leaf("B", "eq", 2))),
        "NOT(A eq 1 OR B eq 2)",
    ),
    (
        "nested",
        Group("any_of", (
            Group("none_of", (Leaf("Status", "eq", "Closed"),)),
            Group("all_of", (Leaf("Count", "geq", 5), Leaf("Note", "is_not_null"))),
        )),
        "(NOT(Status eq 'Closed') OR (Count geq 5 AND Note is_not_null))",
    ),
]

_IMPORT_PROBE = (
    "import importlib, sys\n"
    "importlib.import_module(sys.argv[1])\n"
    "print('\\n'.join(sorted(n for n in sys.modules if n.startswith('dbml_sharepoint'))))\n"
)
_FORBIDDEN_DESCRIPTION_IMPORTS = (
    "dbml_sharepoint.analysis.conditions",
    "dbml_sharepoint.analysis.findings",
    "dbml_sharepoint.analysis.checks",
)


def _valueless_literal_sites(root: Path) -> list[str]:
    """Production files containing the exact two-member operator literal."""
    sites: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Set):
                continue
            members = {
                item.value for item in node.elts
                if isinstance(item, ast.Constant) and isinstance(item.value, str)
            }
            if members == {"is_null", "is_not_null"} and len(node.elts) == 2:
                sites.append(path.relative_to(root).as_posix())
    return sites


def _import_closure(module_name: str) -> set[str]:
    probe = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _IMPORT_PROBE, module_name],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(probe.stdout.split())


@pytest.mark.parametrize(
    ("condition", "prose"),
    [(condition, prose) for _, condition, prose in DESCRIBED],
    ids=[name for name, _, _ in DESCRIBED],
)
def test_describe_renders_each_shape_exactly_as_before(
    condition: Condition,
    prose: str,
) -> None:
    assert describe(condition) == prose


def test_valueless_operator_vocabulary_has_one_owner() -> None:
    """The grammar owns the fact; analysis and description only consume it."""
    assert _valueless_literal_sites(PACKAGE) == ["model/conditions.py"]
    assert sorted(VALUELESS_OPS) == ["is_not_null", "is_null"]
    assert vars(conditions)["VALUELESS_OPS"] is model_conditions.VALUELESS_OPS
    assert vars(condition_description)["VALUELESS_OPS"] is model_conditions.VALUELESS_OPS
    assert not hasattr(conditions, "_NULL_TESTS")
    assert not hasattr(conditions, "_VALUELESS_OPS")


def test_description_import_closure_is_dependency_light() -> None:
    """Generators importing prose must not load diagnosis or check families."""
    loaded = _import_closure("dbml_sharepoint.analysis.condition_description")
    forbidden = {
        module for module in loaded
        if any(
            module == root or module.startswith(f"{root}.")
            for root in _FORBIDDEN_DESCRIPTION_IMPORTS
        )
    }
    assert forbidden == set()


def test_reporting_generators_use_the_dependency_light_module() -> None:
    """The new seam matters only while both intended callers import it directly."""
    for relative in ("generators/manifestgen.py", "generators/reportgen.py"):
        imports = [
            node
            for node in ast.walk(ast.parse((PACKAGE / relative).read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom)
        ]
        assert any(
            node.module == "dbml_sharepoint.analysis.condition_description"
            and any(alias.name == "describe" for alias in node.names)
            for node in imports
        ), relative
        assert not any(
            node.module == "dbml_sharepoint.analysis.conditions"
            and any(alias.name == "describe" for alias in node.names)
            for node in imports
        ), relative
