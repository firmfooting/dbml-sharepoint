# test/test_column_projection.py
"""The column projection, and the import boundary that keeps it free-standing."""

import ast
import subprocess
import sys

from _paths import PACKAGE

from dbml_sharepoint.analysis.column_projection import (
    SYSTEM_COLUMN_TYPES,
    effective_column_types,
)

MODULE = "dbml_sharepoint.analysis.column_projection"

_IMPORT_PROBE = (
    "import importlib, sys\n"
    "importlib.import_module(sys.argv[1])\n"
    "print('\\n'.join(sorted(n for n in sys.modules if n.startswith('dbml_sharepoint'))))\n"
)
#: Whole families this module must not pull in, named as roots so a new
#: sibling inside one is covered without editing this list.
_FORBIDDEN_PROJECTION_IMPORTS = (
    "dbml_sharepoint.analysis.conditions",
    "dbml_sharepoint.analysis.findings",
    "dbml_sharepoint.analysis.checks",
    "dbml_sharepoint.generators",
    "dbml_sharepoint.model",
)
#: Every file the move repointed, and the names each one takes from here.
_INTENDED_IMPORTERS: dict[str, set[str]] = {
    "generators/jsgen.py": {"SYSTEM_COLUMN_TYPES", "effective_column_types"},
    "analysis/checks/_views.py": {"SYSTEM_COLUMN_TYPES", "effective_column_types"},
    "analysis/checks/_formatting.py": {"effective_column_types"},
    "analysis/checks/_retirement.py": {"effective_column_types"},
    "analysis/joins.py": {"SYSTEM_COLUMN_TYPES"},
}


def _import_closure(module_name: str) -> set[str]:
    probe = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _IMPORT_PROBE, module_name],
        capture_output=True,
        text=True,
        check=True,
    )
    return set(probe.stdout.split())


def _imported_names(relative: str, module: str) -> set[str]:
    """Names `relative` takes from `module` by a `from ... import` statement."""
    tree = ast.parse((PACKAGE / relative).read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def _projection_importers() -> set[str]:
    """Package modules importing either projection name from the new owner."""
    names = {"SYSTEM_COLUMN_TYPES", "effective_column_types"}
    importers: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        relative = path.relative_to(PACKAGE).as_posix()
        if _imported_names(relative, MODULE) & names:
            importers.add(relative)
    return importers


def test_modeled_system_column_types_are_exact() -> None:
    """Views may reference these modeled columns and DBML never declares
    them. Without a type, a date comparison on Created renders as Type="Text"
    rather than the intended date type."""
    assert SYSTEM_COLUMN_TYPES == {
        "ID": "int",
        "Created": "datetime",
        "Modified": "datetime",
        "Author": "person",
        "Editor": "person",
    }


def test_projection_includes_implicit_title_when_not_declared() -> None:
    """The project models Title even when DBML does not declare it."""
    assert effective_column_types({"Status": "nvarchar"}) == {
        "Title": "nvarchar",
        "Status": "nvarchar",
    }


def test_a_declared_title_wins_over_the_implicit_one() -> None:
    """The implicit entry is a floor, not an override. `**declared` comes
    second so a schema that types Title itself keeps its own answer."""
    assert effective_column_types({"Title": "calculated_text"})["Title"] == "calculated_text"


def test_a_cross_site_reference_projects_its_companion_pair() -> None:
    """The generator expands one reference into a Choice + URL pair, so both
    companions have types even though neither is a DBML column."""
    types = effective_column_types({"Unit": "int"}, {"Unit"})
    assert types == {
        "Title": "nvarchar",
        "Unit": "int",
        "UnitAbbreviation": "nvarchar",
        "UnitSiteUrl": "hyperlink",
    }


def test_a_declared_column_wins_over_a_companion_of_the_same_name() -> None:
    """`setdefault`, not assignment: a schema really declaring `UnitSiteUrl`
    keeps its own type rather than being retyped by the expansion."""
    types = effective_column_types({"UnitSiteUrl": "nvarchar"}, {"Unit"})
    assert types["UnitSiteUrl"] == "nvarchar"
    assert types["UnitAbbreviation"] == "nvarchar"


def test_the_inputs_are_left_alone() -> None:
    """Callers pass a dict comprehension over a table's columns and reuse it.
    A projection that wrote Title back into that dict would leak an implicit
    column into whatever the caller does next."""
    declared = {"Unit": "int"}
    cross_site = {"Unit"}
    effective_column_types(declared, cross_site)
    assert declared == {"Unit": "int"}
    assert cross_site == {"Unit"}


def test_the_projection_does_not_carry_the_system_columns() -> None:
    """Deliberate, and it reads like an oversight, so it is pinned. Two
    callers merge SYSTEM_COLUMN_TYPES in where a view may filter on Created;
    the other three pass the projection alone. Folding them in here would
    change what all five see to save two of them a merge."""
    projected = effective_column_types({"Status": "nvarchar"}, {"Unit"})
    assert set(projected) & set(SYSTEM_COLUMN_TYPES) == set()


def test_projection_import_closure_excludes_validation_families() -> None:
    """`analysis.joins` needs the system types and nothing else. Importing
    them must not load a renderer, the finding vocabulary or a check family.
    Harmless package-initializer dependencies are not part of this boundary."""
    loaded = _import_closure(MODULE)
    forbidden = {
        module for module in loaded
        if any(
            module == root or module.startswith(f"{root}.")
            for root in _FORBIDDEN_PROJECTION_IMPORTS
        )
    }
    assert forbidden == set()


def test_joins_no_longer_loads_the_condition_validation_stack() -> None:
    """The bounded extraction's immediate architectural payoff."""
    loaded = _import_closure("dbml_sharepoint.analysis.joins")
    forbidden = {
        module for module in loaded
        if module == "dbml_sharepoint.analysis.conditions"
        or module == "dbml_sharepoint.analysis.findings"
        or module == "dbml_sharepoint.analysis.checks"
        or module.startswith("dbml_sharepoint.analysis.checks.")
    }
    assert forbidden == set()


def test_intended_importers_take_the_projection_from_its_own_module() -> None:
    """The seam matters only while every caller uses it. Each file must take
    its projection names from here and none of them from `analysis.conditions`,
    which keeps the renderer and diagnosis imports it still needs."""
    assert _projection_importers() == set(_INTENDED_IMPORTERS)
    for relative, names in _INTENDED_IMPORTERS.items():
        assert _imported_names(relative, MODULE) == names, relative
        from_conditions = _imported_names(relative, "dbml_sharepoint.analysis.conditions")
        assert from_conditions & {"SYSTEM_COLUMN_TYPES", "effective_column_types"} == set(), (
            relative
        )


def test_the_old_home_keeps_no_compatibility_re_export() -> None:
    """One importable home per name. A re-export would recreate the shim the
    architecture work is removing, and nothing else would notice."""
    from dbml_sharepoint.analysis import conditions

    assert not hasattr(conditions, "SYSTEM_COLUMN_TYPES")
    assert not hasattr(conditions, "effective_column_types")
