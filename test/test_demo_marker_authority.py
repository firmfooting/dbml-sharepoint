# test/test_demo_marker_authority.py
"""One owner for the demo-row prefix used by validation and demo rendering.

The static scan is a ratchet over direct and constant-concatenated copies. The
behavioral tests are the stronger evidence: validator and seed output must move
when their imported owner moves. Rollback no longer consumes this prefix.
"""

import ast
from pathlib import Path

import pytest
from _findings import codes
from _model import bundle as make_bundle
from _model import column
from _model import schema as make_schema
from _model import table as make_table
from _paths import FIXTURES, JINJA_TEMPLATES, PACKAGE
from _validator_helpers import _project_errors

from dbml_sharepoint.analysis import finding_help
from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX
from dbml_sharepoint.analysis.findings import FindingCode
from dbml_sharepoint.generators import demogen
from dbml_sharepoint.model.mapping_types import DemoItem
from dbml_sharepoint.model.release import load_release

_OWNER = PACKAGE / "analysis" / "demo_marker.py"
_OWNER_MODULE = "dbml_sharepoint.analysis.demo_marker"
_CONSUMERS = (
    PACKAGE / "analysis" / "checks" / "_demo.py",
    PACKAGE / "analysis" / "finding_help.py",
    PACKAGE / "bundle.py",
    PACKAGE / "cli.py",
    PACKAGE / "generators" / "demogen.py",
    PACKAGE / "wizard.py",
)
_COMMON_ARGS = {
    "site_url": "https://example.sharepoint.com/sites/test",
    "site_role": "default",
    "source_dbml": "simple.dbml",
    "generated_at": "2026-05-04T00:00:00Z",
}


def _docstrings(tree: ast.AST) -> set[int]:
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def _string_parts(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _string_parts(node.left)
        right = _string_parts(node.right)
        return left + right if left and right else ""
    return ""


def _offending_python(path: Path, marker: str) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstrings(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip.update(id(part) for part in node.values)
    return [
        f"{path.name}:{node.lineno}"
        for node in ast.walk(tree)
        if isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp))
        and id(node) not in skip
        and marker in _string_parts(node)
    ]


def _offending_template(path: Path, marker: str) -> list[str]:
    return [
        f"{path.name}:{number}"
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if marker in line
    ]


def _imports_owner(path: Path) -> bool:
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == _OWNER_MODULE
        and any(alias.name == "DEMO_TITLE_PREFIX" for alias in node.names)
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
    )


def _demo_js(title_prefix: str = DEMO_TITLE_PREFIX) -> str:
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    bundle = make_bundle(
        entities=["Risk"],
        demo_items={
            "Risk": [
                DemoItem(key="r1", values={"Title": f"{title_prefix}Sample risk"}),
            ],
        },
    )
    return demogen.generate_demo_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        **_COMMON_ARGS,
    )



def test_owner_declares_the_marker_and_safe_javascript_shape() -> None:
    assert DEMO_TITLE_PREFIX == "[DEMO] "
    for forbidden in (
        "'", "\\", "\n", "\r", chr(0x2028), chr(0x2029),
        "`", "${", "*/", "</script",
    ):
        assert forbidden not in DEMO_TITLE_PREFIX


def test_no_other_package_module_or_template_spells_the_marker() -> None:
    modules = [path for path in sorted(PACKAGE.rglob("*.py")) if path != _OWNER]
    templates = sorted(JINJA_TEMPLATES.rglob("*.j2"))
    assert len(modules) > 30 and len(templates) > 10

    offenders = [
        item
        for path in modules
        for item in _offending_python(path, DEMO_TITLE_PREFIX)
    ] + [
        item
        for path in templates
        for item in _offending_template(path, DEMO_TITLE_PREFIX)
    ]
    assert offenders == []


def test_every_production_consumer_imports_the_owner() -> None:
    assert [path.name for path in _CONSUMERS if not _imports_owner(path)] == []


def test_literal_scans_detect_the_marker_under_another_name(tmp_path: Path) -> None:
    module = tmp_path / "seeded.py"
    module.write_text(
        'DEMO_PREFIX = "[DEMO]" + " "\n', encoding="utf-8", newline="\n",
    )
    template = tmp_path / "seeded.js.j2"
    template.write_text(
        "const DEMO_PREFIX = '[DEMO] ';\n", encoding="utf-8", newline="\n",
    )
    assert len(_offending_python(module, "[DEMO] ")) == 1
    assert len(_offending_template(template, "[DEMO] ")) == 1


def test_validator_rule_and_message_move_with_the_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dbml_sharepoint.analysis.checks import _demo

    monkeypatch.setattr(_demo, "DEMO_TITLE_PREFIX", "[SAMPLE] ")
    errors = _project_errors(
        demo_items={
            "Project": [DemoItem(key="p1", values={"Title": "[DEMO] Sample"})],
        },
    )
    assert FindingCode.DEMO_TITLE_MISSING_MARKER in codes(errors)
    assert "[SAMPLE] " in next(
        finding.message
        for finding in errors
        if finding.code == FindingCode.DEMO_TITLE_MISSING_MARKER
    )


def test_seed_script_moves_with_the_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(demogen, "DEMO_TITLE_PREFIX", "[SAMPLE] ")
    assert "[SAMPLE] " in _demo_js("[SAMPLE] ")


def test_default_rendering_is_byte_pinned_at_changed_template_lines() -> None:
    demo = _demo_js()
    assert " * demo/sample rows. Every Title starts with '[DEMO] ' (visible in every" in demo
    assert (
        "  log('INFO', 'Every demo row is prefixed \"[DEMO] \". Delete before active "
        "use; rollback.js.txt confirms every list before delete.');"
    ) in demo


def test_finding_help_quotes_the_owner() -> None:
    assert DEMO_TITLE_PREFIX in finding_help.FINDING_HELP[
        FindingCode.DEMO_TITLE_MISSING_MARKER
    ]
