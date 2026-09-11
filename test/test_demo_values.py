"""Validator: demo-row value grammar (`analysis/checks/_demo.py`).

`test_validator_views.py` already covers the identity and reference rules a
demo row is judged by (duplicate keys, `demo_ref` targets, enum and date
grammar). These three are the value-shape rules that module leaves out: a
dict that is not a lookup reference, a person value that is not "@me", and a
value written to a column that cannot be written at all.
"""

from _findings import only
from _model import bundle as make_bundle
from _model import column as make_column
from _model import person as make_person
from _model import schema as make_schema
from _model import table as make_table
from _validator_helpers import _project_errors

from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.mapping_types import DemoItem


def test_a_demo_dict_value_that_is_not_a_demo_ref_is_refused() -> None:
    """Any demo value that is a dict is read as `{demo_ref: <key>}` first,
    on any column, not only a lookup, so an author's own object shape is
    refused before the column's own type is consulted."""
    errors = _project_errors(
        demo_items={
            "Project": [
                DemoItem(key="p1", values={
                    "Title": "[DEMO] Row",
                    "Status": {"literal": "Open"},
                }),
            ],
        },
    )
    f = only(errors, FindingCode.DEMO_OBJECT_VALUE_INVALID)
    assert f.severity == "error"
    assert f.location == Location(Section.DEMO_ITEMS, entity="Project", sub="p1")
    assert "demo_ref" in f.message


def test_a_demo_person_value_other_than_me_is_refused() -> None:
    """The demo planner writes only the deploying operator; there is no
    other identity a build-time seed can resolve to a real account."""
    schema = make_schema(make_table(
        "Task", make_column("Title"), make_person("Owner"), note="Task fixture.",
    ))
    bundle = make_bundle(
        entities=["Task"],
        demo_items={
            "Task": [DemoItem(key="t1", values={
                "Title": "[DEMO] Row", "Owner": "someone@example.com",
            })],
        },
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.DEMO_PERSON_VALUE_UNSUPPORTED,
    )
    assert f.severity == "error"
    assert f.location == Location(Section.DEMO_ITEMS, entity="Task", sub="t1")
    assert '"@me"' in f.message


def test_a_demo_value_on_a_calculated_column_is_refused() -> None:
    """A calculated column is rendered but never writable; a demo row that
    names it directly cannot be seeded and must set the column's inputs
    instead."""
    schema = make_schema(make_table(
        "Widget", make_column("Title"), make_column("Score", "calculated_number"),
        note="Widget fixture.",
    ))
    bundle = make_bundle(
        entities=["Widget"],
        calculated_formulas={"Widget": {"Score": "=1+1"}},
        demo_items={
            "Widget": [DemoItem(key="w1", values={
                "Title": "[DEMO] Row", "Score": 42,
            })],
        },
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.DEMO_VALUE_ON_CALCULATED_COLUMN,
    )
    assert f.severity == "error"
    assert f.location == Location(Section.DEMO_ITEMS, entity="Widget", sub="w1")
    assert "Score" in f.message
