"""The renderer/diagnosis boundary introduced by #168."""

import ast
import datetime as dt
import subprocess
import sys
from pathlib import Path

import pytest
from _paths import PACKAGE

from dbml_sharepoint.analysis import condition_rendering as rendering
from dbml_sharepoint.analysis.conditions import condition_findings
from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.model.conditions import Group, Leaf

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


def test_rendering_import_closure_does_not_load_diagnosis() -> None:
    loaded = _import_closure("dbml_sharepoint.analysis.condition_rendering")
    assert "dbml_sharepoint.analysis.conditions" not in loaded
    assert "dbml_sharepoint.analysis.findings" not in loaded
    assert not any(name.startswith("dbml_sharepoint.analysis.checks") for name in loaded)


def test_rendering_source_does_not_import_findings() -> None:
    tree = ast.parse(
        (PACKAGE / "analysis/condition_rendering.py").read_text(encoding="utf-8"),
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


def test_refusal_carries_neutral_identity_and_source_coordinates() -> None:
    from dbml_sharepoint.analysis.condition_rendering import (
        ConditionRefusal,
        ConditionRefusalKind,
        to_caml,
    )

    with pytest.raises(ConditionRefusal) as caught:
        to_caml(Leaf("Title", "eq", "Open"), {})

    refusal = caught.value
    assert refusal.kind is ConditionRefusalKind.COLUMN_TYPE_UNKNOWN
    assert refusal.path == "conditions.Title"
    assert refusal.field == "Title"
    assert str(refusal) == ("conditions.Title: no declared type for column 'Title' (target: caml)")


def test_normalisation_refusal_carries_source_coordinates() -> None:
    with pytest.raises(rendering.ConditionRefusal) as caught:
        rendering.normalise(Group("none_of", (Leaf("Title", "bogus", "x"),)))

    refusal = caught.value
    assert refusal.kind is rendering.ConditionRefusalKind.OPERATOR_NOT_NEGATABLE
    assert refusal.path == "conditions.Title"
    assert refusal.field == "Title"


def test_refusal_kind_mapping_is_exact_and_exhaustive() -> None:
    from dbml_sharepoint.analysis.condition_rendering import ConditionRefusalKind
    from dbml_sharepoint.analysis.conditions import _REFUSAL_FINDING_CODES

    expected = {
        "COLUMN_TYPE_UNKNOWN": FindingCode.CONDITION_COLUMN_TYPE_UNKNOWN,
        "DATE_IS_AN_UNQUOTED_YAML_DATETIME": (
            FindingCode.CONDITION_DATE_IS_AN_UNQUOTED_YAML_DATETIME
        ),
        "DATE_UNPARSEABLE": FindingCode.CONDITION_DATE_UNPARSEABLE,
        "DATE_WEARS_WHITESPACE": FindingCode.CONDITION_DATE_WEARS_WHITESPACE,
        "MEASURE_UNRENDERABLE": FindingCode.CONDITION_MEASURE_UNRENDERABLE,
        "ME_UNSUPPORTED_BY_TARGET": FindingCode.CONDITION_ME_UNSUPPORTED_BY_TARGET,
        "NEEDLE_EMPTY": FindingCode.CONDITION_NEEDLE_EMPTY,
        "NEGATIVE_TEXT_OPERATOR_UNRENDERABLE": (
            FindingCode.CONDITION_NEGATIVE_TEXT_OPERATOR_UNRENDERABLE
        ),
        "NOW_ON_A_DATE_COLUMN": FindingCode.CONDITION_NOW_ON_A_DATE_COLUMN,
        "NOW_UNSUPPORTED_BY_TARGET": FindingCode.CONDITION_NOW_UNSUPPORTED_BY_TARGET,
        "OPERAND_TYPE_UNSUPPORTED": FindingCode.CONDITION_OPERAND_TYPE_UNSUPPORTED,
        "OPERATOR_NOT_NEGATABLE": FindingCode.CONDITION_OPERATOR_NOT_NEGATABLE,
        "OPERATOR_UNRENDERABLE": FindingCode.CONDITION_OPERATOR_UNRENDERABLE,
        "OPERATOR_UNVERIFIED": FindingCode.CONDITION_OPERATOR_UNVERIFIED,
        "PROPERTY_UNRENDERABLE": FindingCode.CONDITION_PROPERTY_UNRENDERABLE,
        "SENTINEL_WITH_A_SUBSTRING_OPERATOR": (
            FindingCode.CONDITION_SENTINEL_WITH_A_SUBSTRING_OPERATOR
        ),
        "SET_EMPTY": FindingCode.CONDITION_SET_EMPTY,
        "SUBSTRING_TEST_ON_A_NON_TEXT_COLUMN": (
            FindingCode.CONDITION_SUBSTRING_TEST_ON_A_NON_TEXT_COLUMN
        ),
        "TODAY_UNSUPPORTED_BY_TARGET": FindingCode.CONDITION_TODAY_UNSUPPORTED_BY_TARGET,
        "VALUE_HAS_A_CONTROL_CHARACTER": FindingCode.CONDITION_VALUE_HAS_A_CONTROL_CHARACTER,
        "VALUE_MISSING": FindingCode.CONDITION_VALUE_MISSING,
        "VALUE_NOT_ALLOWED": FindingCode.CONDITION_VALUE_NOT_ALLOWED,
        "VALUE_NOT_A_BOOLEAN": FindingCode.CONDITION_VALUE_NOT_A_BOOLEAN,
        "VALUE_NOT_A_LIST": FindingCode.CONDITION_VALUE_NOT_A_LIST,
        "VALUE_NOT_A_NUMBER": FindingCode.CONDITION_VALUE_NOT_A_NUMBER,
        "VALUE_NOT_FINITE": FindingCode.CONDITION_VALUE_NOT_FINITE,
        "MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED": (
            FindingCode.MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED
        ),
        "MULTI_VALUE_MEMBERSHIP_ON_A_SINGLE_VALUE_COLUMN": (
            FindingCode.MULTI_VALUE_MEMBERSHIP_ON_A_SINGLE_VALUE_COLUMN
        ),
        "MULTI_VALUE_OPERAND_UNSUPPORTED": FindingCode.MULTI_VALUE_OPERAND_UNSUPPORTED,
        "MULTI_VALUE_SET_EQUALITY_UNSUPPORTED": FindingCode.MULTI_VALUE_SET_EQUALITY_UNSUPPORTED,
    }
    assert set(_REFUSAL_FINDING_CODES) == set(ConditionRefusalKind)
    assert {kind.name: code for kind, code in _REFUSAL_FINDING_CODES.items()} == expected


@pytest.mark.parametrize(
    ("code", "leaf", "target", "types", "rendered"),
    [
        (
            FindingCode.CONDITION_COLUMN_TYPE_UNKNOWN,
            Leaf("X", "eq", "x"),
            rendering.CAML,
            {},
            {"X"},
        ),
        (
            FindingCode.CONDITION_DATE_IS_AN_UNQUOTED_YAML_DATETIME,
            Leaf("Due", "leq", dt.datetime(2026, 7, 29, 14, 30)),  # noqa: DTZ001
            rendering.CAML,
            {"Due": "date"},
            {"Due"},
        ),
        (
            FindingCode.CONDITION_DATE_WEARS_WHITESPACE,
            Leaf("Due", "leq", " 2026-07-29 "),
            rendering.CAML,
            {"Due": "date"},
            {"Due"},
        ),
        (
            FindingCode.CONDITION_ME_UNSUPPORTED_BY_TARGET,
            Leaf("Owner", "eq", "me"),
            rendering.EXPRESSION,
            {"Owner": "person"},
            {"Owner"},
        ),
        (
            FindingCode.CONDITION_NOW_UNSUPPORTED_BY_TARGET,
            Leaf("Occurred", "leq", "now"),
            rendering.EXPRESSION,
            {"Occurred": "datetime"},
            {"Occurred"},
        ),
        (
            FindingCode.CONDITION_PROPERTY_UNRENDERABLE,
            Leaf("Owner", "eq", "a", "email"),
            rendering.CAML,
            {"Owner": "person"},
            {"Owner"},
        ),
        (
            FindingCode.CONDITION_SET_EMPTY,
            Leaf("X", "in", []),
            rendering.CAML,
            {"X": "nvarchar"},
            {"X"},
        ),
        (
            FindingCode.CONDITION_TODAY_UNSUPPORTED_BY_TARGET,
            Leaf("Due", "leq", "today"),
            rendering.EXPRESSION,
            {"Due": "date"},
            {"Due"},
        ),
        (
            FindingCode.CONDITION_VALUE_HAS_A_CONTROL_CHARACTER,
            Leaf("X", "eq", "\x01"),
            rendering.CAML,
            {"X": "nvarchar"},
            {"X"},
        ),
        (
            FindingCode.CONDITION_VALUE_NOT_A_BOOLEAN,
            Leaf("Flag", "eq", "maybe"),
            rendering.CAML,
            {"Flag": "boolean"},
            {"Flag"},
        ),
        (
            FindingCode.CONDITION_VALUE_NOT_FINITE,
            Leaf("Count", "eq", float("inf")),
            rendering.CAML,
            {"Count": "number"},
            {"Count"},
        ),
    ],
)
def test_renderer_refusals_reach_classified_diagnosis(
    code: FindingCode,
    leaf: Leaf,
    target: str,
    types: dict[str, str],
    rendered: set[str],
) -> None:
    findings = condition_findings(
        leaf,
        target=target,
        rendered=rendered,
        types=types,
        lookups=set(),
        enum_members={},
        at=Location(Section.VIEWS, entity="X", view="V", sub="where"),
    )
    assert [finding.code for finding in findings] == [code]


def test_conditions_has_no_renderer_compatibility_reexports() -> None:
    from dbml_sharepoint.analysis import conditions

    moved = {
        "condition_rendering",
        "CAML",
        "EXPRESSION",
        "VALIDATION",
        "NEGATION",
        "CAPABILITIES",
        "DISABLED_PENDING_PROBE",
        "normalise",
        "normalise_with_polarity",
        "is_current_user_sentinel",
        "to_caml",
        "to_expression",
        "to_validation",
        "ConditionRefusalKind",
        "ConditionRefusal",
    }
    assert moved.isdisjoint(vars(conditions))


def test_production_consumers_import_renderers_directly() -> None:
    expected = {
        "analysis/forms.py": {"EXPRESSION", "to_expression"},
        "analysis/checks/_formatting.py": {"VALIDATION", "to_validation"},
        "analysis/checks/_retirement.py": {"VALIDATION", "to_validation"},
        "analysis/checks/_views.py": {"CAML", "normalise"},
        "generators/jsgen.py": {"to_caml", "to_validation"},
    }
    for relative, names in expected.items():
        imports = _imports(PACKAGE / relative)
        rendering_names = {
            alias.name
            for node in imports
            if node.module == "dbml_sharepoint.analysis.condition_rendering"
            for alias in node.names
        }
        assert names <= rendering_names, relative
        assert not any(
            node.module == "dbml_sharepoint.analysis.conditions"
            and any(alias.name in names for alias in node.names)
            for node in imports
        ), relative
