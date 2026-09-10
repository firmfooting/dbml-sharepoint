# test/test_reporting_layout.py
"""The reporting pack's module boundaries, pinned.

`generators/reportgen.py` was one 3,400 line module that planned and
rendered six artifacts. It is now a plan side under `analysis/reporting/`
and a render side under `generators/`, split by one rule: a function that
is a pure derivation of (schema, bundle, site_role) returning data is plan;
a function returning text written to a file, or a fragment of one, is
render; and the renderers are split by the escaping function the text
needs (`_m_string`, `_sql_string`, `_md_cell`).

THE INTENDED DEPENDENCY DIRECTION, which this module is the gate for:

    model/  ->  analysis/reporting/{plan, dictionary}
            ->  generators/{report_m, report_sql, report_md}
            ->  generators/reportgen  ->  bundle (deferred, one site)

- `analysis/reporting/` imports nothing from `generators/`, `bundle` or
  `cli`, and nothing from `analysis/checks/`. The checks import it, never
  the reverse, which is what lets a validator rule read the plan.
- The three renderers import the plan side, not each other and never
  `reportgen`, which composes them. No escaping function crosses a module.
- `bundle.py` reaches the pack only through `reportgen.emit_reporting`,
  inside a function body that `test_public_api` ratchets. No decomposed
  module recreates that cycle by importing `bundle` at module level and
  being imported back from it.

Every check here reads import statements, so a violation names the file
and the module it reached for.
"""

import ast
from pathlib import Path

from _paths import PACKAGE

PLAN_SIDE = sorted((PACKAGE / "analysis" / "reporting").glob("*.py"))
RENDERERS = [
    PACKAGE / "generators" / name
    for name in ("report_m.py", "report_sql.py", "report_md.py")
]
COMPOSITION = PACKAGE / "generators" / "reportgen.py"
ESCAPING = ("_m_string", "_sql_string", "_md_cell")


def _imports(path: Path, *, module_level_only: bool = False) -> list[str]:
    """Every module `path` imports, dotted, in source order."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    nodes = tree.body if module_level_only else list(ast.walk(tree))
    found: list[str] = []
    for node in nodes:
        if isinstance(node, ast.Import):
            found += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.append(node.module)
    return found


def _reaching(path: Path, forbidden: tuple[str, ...], **kwargs: bool) -> list[str]:
    return [
        f"{path.relative_to(PACKAGE).as_posix()} imports {module}"
        for module in _imports(path, **kwargs)
        if any(module == root or module.startswith(f"{root}.") for root in forbidden)
    ]


def test_the_layout_is_present() -> None:
    """The other tests pass on an empty walk, so this pins the walk."""
    assert [p.name for p in PLAN_SIDE] == ["__init__.py", "dictionary.py", "plan.py"]
    assert all(p.is_file() for p in RENDERERS) and COMPOSITION.is_file()


def test_the_plan_side_reaches_no_renderer_packaging_or_check() -> None:
    forbidden = (
        "dbml_sharepoint.generators",
        "dbml_sharepoint.bundle",
        "dbml_sharepoint.cli",
        "dbml_sharepoint.analysis.checks",
    )
    offenders = [line for path in PLAN_SIDE for line in _reaching(path, forbidden)]
    assert offenders == [], "\n".join(offenders)


def test_the_renderers_reach_neither_each_other_nor_the_composition() -> None:
    forbidden = (
        "dbml_sharepoint.generators.report_m",
        "dbml_sharepoint.generators.report_sql",
        "dbml_sharepoint.generators.report_md",
        "dbml_sharepoint.generators.reportgen",
        "dbml_sharepoint.analysis.checks",
    )
    offenders = [line for path in RENDERERS for line in _reaching(path, forbidden)]
    assert offenders == [], "\n".join(offenders)


def test_no_escaping_function_crosses_a_module() -> None:
    """Which escaping a fragment needs is what decides its module, so a
    plan-side function reaching for one, or a renderer borrowing another's,
    is the split coming undone."""
    offenders: list[str] = []
    for path in [*PLAN_SIDE, *RENDERERS, COMPOSITION]:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined = {
            node.name for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name in ESCAPING
        }
        used = {
            node.id for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id in ESCAPING
        }
        offenders += [
            f"{path.relative_to(PACKAGE).as_posix()} uses {name} without defining it"
            for name in sorted(used - defined)
        ]
    assert offenders == [], "\n".join(offenders)
    # Not vacuous: each renderer defines exactly its own.
    for path, name in zip(RENDERERS, ESCAPING, strict=True):
        assert name in path.read_text(encoding="utf-8"), (path.name, name)


def test_bundle_reaches_the_pack_only_through_the_composition() -> None:
    """`emit_bundle` defers its import of `reportgen.emit_reporting`, the
    one cycle the package docstring records. Nothing decomposed may give it
    a second route in."""
    bundle = PACKAGE / "bundle.py"
    at_import = _reaching(
        bundle, ("dbml_sharepoint.generators", "dbml_sharepoint.analysis.reporting"),
        module_level_only=True,
    )
    assert at_import == [], "\n".join(at_import)
    anywhere = _reaching(
        bundle,
        (
            "dbml_sharepoint.generators.report_m",
            "dbml_sharepoint.generators.report_sql",
            "dbml_sharepoint.generators.report_md",
            "dbml_sharepoint.analysis.reporting",
        ),
    )
    assert anywhere == [], "\n".join(anywhere)
