"""The Lists forms payload: one spelling of each declared form for deploy, assess and verify."""

from dataclasses import replace

from _model import bundle as make_bundle
from _model import column, enum
from _model import schema as make_schema
from _model import table as make_table
from _paths import FIXTURES

from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.lists_forms_payload import (
    OPERATIONAL_KEYS,
    PLATFORM_THANK_YOU,
    lists_forms_payload,
    utc_text,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    EntityListsForms,
    ListsForm,
    ListsFormQuestion,
    MappingBundle,
)
from dbml_sharepoint.model.parser import Schema, parse_dbml

_q = ListsFormQuestion


def _schema() -> Schema:
    return make_schema(
        make_table(
            "Request",
            column("Title", required=True),
            column("Details", "longtext"),
            column("Category", "category"),
            column("Priority", "priority", required=True, default="Normal"),
            column("NeededBy", "date"),
            column("Due", "datetime"),
            note="A request.",
        ),
        make_table("Site", column("Title", required=True), note="A site."),
        enums=[
            enum("category", "Building", "IT", "Other"),
            enum("priority", "Low", "Normal", "High"),
        ],
    )


def _bundle(*forms: ListsForm, entities: list[str] | None = None) -> MappingBundle:
    return make_bundle(
        entities=entities if entities is not None else ["Request", "Site"],
        display_name_mode="auto",
        lists_forms={"Request": EntityListsForms(forms=forms, retired=("Old intake",))},
    )


def _form(*questions: ListsFormQuestion) -> ListsForm:
    return ListsForm(title="Intake", questions=questions or (_q("Title"),))


def test_spec_example_payload() -> None:
    form = ListsForm(
        title="Facilities request",
        description="Tell us what needs fixing.\nHow we handle requests: https://example.com/x\n",
        thank_you="Thanks. The facilities team reads every request.",
        opens="2026-11-02T09:00:00+11:00",
        closes="2026-12-18T17:00:00+11:00",
        questions=(
            _q("Title", label="What needs fixing?"),
            _q("Details", help="Include the building and room number."),
            _q("Category"),
            _q("Priority"),
            _q("NeededBy"),
            _q("Attachments"),
        ),
    )
    row = lists_forms_payload(_bundle(form), _schema(), "Request")
    assert row is not None
    assert row["list"] == "APP_Request"
    assert row["retired"] == ["Old intake"]
    (out,) = row["forms"]
    assert out["title"] == "Facilities request"
    assert out["description"] == form.description
    assert out["thank_you"] == form.thank_you
    assert out["one_response_per_person"] is False
    assert out["opens"] == "2026-11-01T22:00:00.000Z"
    assert out["closes"] == "2026-12-18T06:00:00.000Z"
    assert "accepting_responses" not in out
    assert "closed_message" not in out
    assert [(q["column"], q["label"], q["help"]) for q in out["questions"]] == [
        ("Title", "What needs fixing?", ""),
        ("Details", "Details", "Include the building and room number."),
        ("Category", "Category", ""),
        ("Priority", "Priority", ""),
        ("NeededBy", "Needed by", ""),
        ("Attachments", "Attachments", ""),
    ]


def test_question_required_follows_the_column() -> None:
    row = lists_forms_payload(
        _bundle(_form(_q("Title"), _q("Details"), _q("Attachments"))), _schema(), "Request",
    )
    assert row is not None
    assert [q["required"] for q in row["forms"][0]["questions"]] == [True, False, False]


def test_undeclared_title_follows_the_deployed_patch() -> None:
    """Core patches an undeclared Title optional on a list, so the form must agree."""
    schema = make_schema(make_table("Request", column("Details"), note="A request."))
    row = lists_forms_payload(
        _bundle(_form(_q("Title"), _q("Details")), entities=["Request"]), schema, "Request",
    )
    assert row is not None
    (title, _) = row["forms"][0]["questions"]
    assert title == {
        "column": "Title", "label": "Title", "help": "", "required": False,
        "display_format": None,
    }


def test_display_format_follows_the_type() -> None:
    row = lists_forms_payload(
        _bundle(_form(_q("NeededBy"), _q("Due"), _q("Title"))), _schema(), "Request",
    )
    assert row is not None
    assert [q["display_format"] for q in row["forms"][0]["questions"]] == [0, 1, None]


def test_undeclared_thank_you_is_the_platform_text() -> None:
    row = lists_forms_payload(_bundle(_form()), _schema(), "Request")
    assert row is not None
    assert row["forms"][0]["thank_you"] == PLATFORM_THANK_YOU == "Your response has been submitted!"


def test_declared_operational_keys_only() -> None:
    row = lists_forms_payload(
        _bundle(replace(_form(), accepting_responses=False, closed_message="Closed")),
        _schema(),
        "Request",
    )
    assert row is not None
    out = row["forms"][0]
    assert out["accepting_responses"] is False
    assert out["closed_message"] == "Closed"
    assert "opens" not in out
    assert "closes" not in out


def test_operational_keys_constant_names_what_the_row_writes() -> None:
    when = "2026-11-01T09:00:00+11:00"
    form = replace(
        _form(), accepting_responses=True, closed_message="Closed", opens=when, closes=when
    )
    row = lists_forms_payload(_bundle(form), _schema(), "Request")
    assert row is not None
    bare = lists_forms_payload(_bundle(_form()), _schema(), "Request")
    assert bare is not None
    added = set(row["forms"][0]) - set(bare["forms"][0])
    assert added == set(OPERATIONAL_KEYS)


def test_entity_without_forms_has_no_payload() -> None:
    assert lists_forms_payload(_bundle(_form()), _schema(), "Site") is None


def test_utc_text_is_the_javascript_iso_spelling() -> None:
    assert utc_text("2026-11-02T09:00:00+11:00") == "2026-11-01T22:00:00.000Z"
    assert utc_text("2026-11-01T22:00:00Z") == "2026-11-01T22:00:00.000Z"


def test_schema_json_carries_lists_forms_in_site_order() -> None:
    schema, bundle = _schema(), _bundle(_form())
    rows = build_schema_json(
        schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
    )["lists_forms"]
    assert [row["list"] for row in rows] == ["APP_Request"]

    simple = parse_dbml(FIXTURES / "simple.dbml")
    simple_bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert build_schema_json(
        simple, simple_bundle, "default", resolved=resolve(simple, simple_bundle.mapping),
    )["lists_forms"] == []


def test_entity_the_role_does_not_deploy_has_no_row() -> None:
    schema, bundle = _schema(), _bundle(_form())
    assert build_schema_json(
        schema, bundle, "other", resolved=resolve(schema, bundle.mapping),
    )["lists_forms"] == []
