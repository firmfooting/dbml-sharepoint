"""Demo values and text-column condition literals are typed (YAML 1.2 readings)."""
from typing import Unpack

import pytest
from _findings import by_severity, codes, none_of, only
from _model import MappingSections, bundle, column, schema, table

from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.conditions import Group, Leaf
from dbml_sharepoint.model.mapping_types import DemoItem, ViewDef

_COLUMNS = {"Active": "boolean", "Qty": "int", "Cost": "number", "Code": "nvarchar"}


def _findings(**sections: Unpack[MappingSections]) -> list[Finding]:
    sch = schema(table(
        "Thing", column("Title", required=True),
        *(column(name, kind) for name, kind in _COLUMNS.items()),
        note="Fixture.",
    ))
    found = validate_against_mapping(sch, bundle(entities=["Thing"], **sections))
    return by_severity(found, "error")


def _demo(**values: object) -> list[Finding]:
    row = DemoItem(key="t", values={"Title": "[DEMO] x", **values})
    return _findings(demo_items={"Thing": [row]})


@pytest.mark.parametrize(("values", "code"), [
    ({"Active": "no"}, FindingCode.DEMO_BOOLEAN_VALUE_INVALID),
    ({"Qty": True}, FindingCode.DEMO_NUMBER_VALUE_INVALID),
    ({"Cost": "1.5"}, FindingCode.DEMO_NUMBER_VALUE_INVALID),
    ({"Code": 800}, FindingCode.DEMO_TEXT_VALUE_INVALID),
])
def test_a_wrongly_typed_demo_value_is_refused(
    values: dict[str, object], code: FindingCode,
) -> None:
    assert codes(_demo(**values)) == {code}


def test_correctly_typed_demo_values_pass() -> None:
    assert _demo(Active=False, Qty=3, Cost=1.5, Code="0800") == []


def _where(value: object, op: str = "eq") -> list[Finding]:
    leaf = Leaf(field="Code", op=op, value=value)
    view = ViewDef(title="V", fields=["Title"], where=Group("all_of", (leaf,)))
    return _findings(views={"Thing": [view]})


def test_a_non_string_literal_on_a_text_column_is_refused() -> None:
    finding = only(_where(800), FindingCode.CONDITION_VALUE_NOT_TEXT)
    assert "'800'" in finding.message
    only(_where([800, "a"], "in"), FindingCode.CONDITION_VALUE_NOT_TEXT)


def test_string_and_valueless_literals_on_a_text_column_pass() -> None:
    none_of(_where("0800"), FindingCode.CONDITION_VALUE_NOT_TEXT)
    none_of(_where(None, "is_null"), FindingCode.CONDITION_VALUE_NOT_TEXT)
