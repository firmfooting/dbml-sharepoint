"""Validator: `lists-forms.yaml`, the column and structure refusals.

A Lists form shows and accepts whatever columns it names, so each rule here
refuses a question the form would present differently from the list, or one
a respondent could not complete.
"""

from typing import Unpack

from _findings import none_of, only
from _model import MappingSections, column, enum, person
from _model import bundle as make_bundle
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.conditions import Leaf
from dbml_sharepoint.model.mapping_types import (
    EntityListsForms,
    EntityMapping,
    EntitySection,
    FormVisibility,
    ListsForm,
    ListsFormQuestion,
    ListValidation,
    RetiredColumn,
)
from dbml_sharepoint.model.parser import Column, Schema

_OWN = frozenset(
    code for code in FindingCode if code.name.startswith("LISTS_FORM_")
) | {FindingCode.UNKNOWN_ENTITY}


def _schema(*extra: Column) -> Schema:
    return make_schema(
        make_table(
            "Request",
            column("Title", required=True),
            column("Details", "longtext"),
            column("Priority", "priority", required=True, default="Normal"),
            column("Due", "datetime"),
            column("Status", "priority"),
            *extra,
            note="A request.",
        ),
        make_table("Site", column("Title", required=True), note="A site."),
        enums=[enum("priority", "Low", "Normal", "High")],
    )


_q = ListsFormQuestion


def _forms(*questions: ListsFormQuestion) -> dict[str, EntityListsForms]:
    return {"Request": EntityListsForms(forms=(ListsForm(title="Intake", questions=questions),))}


def _check(
    *questions: ListsFormQuestion,
    schema: Schema | None = None,
    lists_forms: dict[str, EntityListsForms] | None = None,
    entities: list[str] | dict[str, EntityMapping] | None = None,
    **sections: Unpack[MappingSections],
) -> list[Finding]:
    """This family's findings only, so an unrelated rule cannot mask one."""
    bundle = make_bundle(
        entities=entities if entities is not None else ["Request", "Site"],
        lists_forms=lists_forms if lists_forms is not None else _forms(*questions),
        **sections,
    )
    findings = validate_against_mapping(schema or _schema(), bundle)
    return [f for f in findings if f.code in _OWN]


def _at(j: int) -> Location:
    return Location(Section.LISTS_FORMS, entity="Request", sub=f"forms[0].questions[{j}]")


# --- accepted declarations --------------------------------------------------


def test_a_clean_declaration_has_no_findings() -> None:
    bundle = make_bundle(
        entities=["Request", "Site"],
        lists_forms=_forms(
            _q("Title"), _q("Details"), _q("Priority"), _q("Due"), _q("Attachments"),
        ),
    )
    assert validate_against_mapping(_schema(), bundle) == []


def test_required_column_with_default_may_be_left_off() -> None:
    none_of(_check(_q("Title")), FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING)


def test_required_column_with_default_formula_may_be_left_off() -> None:
    schema = _schema(column("Opened", "date", required=True))
    findings = _check(
        _q("Title"), schema=schema, default_formulas={"Request": {"Opened": "=TODAY()"}},
    )
    none_of(findings, FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING)


def test_lookup_with_acknowledgement_is_accepted() -> None:
    schema = _schema(make_ref("Site", "Site.Id"))
    findings = _check(_q("Title"), _q("Site", respondents_read_source=True), schema=schema)
    none_of(findings, FindingCode.LISTS_FORM_LOOKUP_SOURCE_UNREADABLE)


def test_person_column_is_not_a_lookup() -> None:
    findings = _check(_q("Title"), _q("Owner"), schema=_schema(person("Owner")))
    assert findings == []


def test_shown_but_hidden_on_edit_is_accepted() -> None:
    findings = _check(
        _q("Title"), _q("Status"),
        form_visibility={"Request": EntitySection(columns={
            "Status": FormVisibility(new=True, existing=False),
        })},
    )
    assert findings == []


# --- refusals ---------------------------------------------------------------


def test_unknown_entity_fires_when_the_entity_is_not_in_the_mapping() -> None:
    forms = {"Ticket": _forms(_q("Title"))["Request"]}
    finding = only(_check(lists_forms=forms), FindingCode.UNKNOWN_ENTITY)
    assert finding.location == Location(Section.LISTS_FORMS, entity="Ticket")


def test_lists_form_on_document_library_fires_when_the_entity_is_a_library() -> None:
    entities = {
        "Request": EntityMapping(
            name="Request", kind="DocumentLibrary", base_template=101, site_role="default",
        ),
        "Site": EntityMapping(name="Site", kind="List", base_template=100, site_role="default"),
    }
    findings = _check(_q("Nope"), entities=entities)
    only(findings, FindingCode.LISTS_FORM_ON_DOCUMENT_LIBRARY)
    # The library refusal stands alone: the questions are not judged.
    assert len(findings) == 1


def test_lists_form_question_not_offered_fires_when_the_column_is_calculated() -> None:
    schema = _schema(column("Band", "calculated_text"))
    findings = _check(
        _q("Title"), _q("Band"), schema=schema, calculated_formulas={"Request": {"Band": '="x"'}},
    )
    assert only(findings, FindingCode.LISTS_FORM_QUESTION_NOT_OFFERED).location == _at(1)


def test_lists_form_question_not_offered_fires_when_the_column_is_the_content_type() -> None:
    findings = _check(_q("Title"), _q("ContentType"))
    only(findings, FindingCode.LISTS_FORM_QUESTION_NOT_OFFERED)
    none_of(findings, FindingCode.LISTS_FORM_COLUMN_UNKNOWN)


def test_lists_form_question_not_offered_fires_when_the_column_is_a_projection() -> None:
    schema = _schema(make_ref("Site", "Site.Id"))
    findings = _check(
        _q("Title"), _q("SiteTitle"), schema=schema,
        lookup_projections={"Request": {"Site": ["Title"]}},
    )
    only(findings, FindingCode.LISTS_FORM_QUESTION_NOT_OFFERED)
    none_of(findings, FindingCode.LISTS_FORM_COLUMN_UNKNOWN)


def test_lists_form_column_unknown_fires_when_the_entity_has_no_such_column() -> None:
    findings = _check(_q("Title"), _q("Colour"))
    assert only(findings, FindingCode.LISTS_FORM_COLUMN_UNKNOWN).location == _at(1)


def test_lists_form_column_unknown_fires_when_the_column_is_retired() -> None:
    findings = _check(
        _q("Title"), _q("Details"),
        retired_columns={"Request": {"Details": RetiredColumn(column="Details")}},
    )
    only(findings, FindingCode.LISTS_FORM_COLUMN_UNKNOWN)
    # Retirement folds into form_visibility; the column is reported once.
    none_of(findings, FindingCode.LISTS_FORM_QUESTION_HIDDEN_ON_LIST_FORM)


def test_lists_form_question_repeated_fires_when_two_questions_name_one_column() -> None:
    findings = _check(_q("Title"), _q("Details"), _q("Details"))
    assert only(findings, FindingCode.LISTS_FORM_QUESTION_REPEATED).location == _at(2)


def test_lists_form_question_hidden_on_list_form_fires_when_new_is_false() -> None:
    findings = _check(
        _q("Title"), _q("Status"),
        form_visibility={"Request": EntitySection(columns={
            "Status": FormVisibility(new=False),
        })},
    )
    assert only(findings, FindingCode.LISTS_FORM_QUESTION_HIDDEN_ON_LIST_FORM).location == _at(1)


def test_lists_form_question_hidden_on_list_form_fires_when_shown_conditionally() -> None:
    findings = _check(
        _q("Title"), _q("Status"),
        form_visibility={"Request": EntitySection(columns={
            "Status": FormVisibility(when=Leaf("Priority", "eq", "High")),
        })},
    )
    only(findings, FindingCode.LISTS_FORM_QUESTION_HIDDEN_ON_LIST_FORM)


def test_lists_form_question_sets_column_fires_when_required_is_declared() -> None:
    findings = _check(_q("Title"), _q("Due", sets_column=("include_time",)))
    assert only(findings, FindingCode.LISTS_FORM_QUESTION_SETS_COLUMN).location == _at(1)


def test_lists_form_required_column_missing_fires_when_a_not_null_column_is_left_off() -> None:
    findings = _check(_q("Details"))
    finding = only(findings, FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING)
    assert finding.location == Location(Section.LISTS_FORMS, entity="Request", sub="forms[0]")
    assert "'Title'" in finding.message


def test_lists_form_required_column_missing_fires_when_an_undeclared_title_is_left_off() -> None:
    schema = make_schema(
        make_table("Request", column("Details", "longtext"), note="A request."),
    )
    findings = _check(_q("Details"), schema=schema, entities=["Request"])
    assert "'Title'" in only(findings, FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING).message


def test_lists_form_lookup_source_unreadable_fires_when_a_lookup_is_not_acknowledged() -> None:
    findings = _check(_q("Title"), _q("Site"), schema=_schema(make_ref("Site", "Site.Id")))
    assert only(findings, FindingCode.LISTS_FORM_LOOKUP_SOURCE_UNREADABLE).location == _at(1)


def test_lists_form_attachments_off_fires_when_the_list_takes_no_attachments() -> None:
    findings = _check(_q("Title"), _q("Attachments"), attachments=False)
    assert only(findings, FindingCode.LISTS_FORM_ATTACHMENTS_OFF).location == _at(1)


def test_lists_form_rich_text_is_plain_fires_when_the_column_is_richtext() -> None:
    findings = _check(_q("Title"), _q("Body"), schema=_schema(column("Body", "richtext")))
    finding = only(findings, FindingCode.LISTS_FORM_RICH_TEXT_IS_PLAIN)
    assert finding.severity == "warning"


def test_lists_form_list_validation_is_silent_fires_when_the_entity_declares_one() -> None:
    two_forms = EntityListsForms(forms=(
        ListsForm(title="Intake", questions=(_q("Title"),)),
        ListsForm(title="Follow-up", questions=(_q("Title"),)),
    ))
    findings = _check(
        lists_forms={"Request": two_forms},
        list_validation={"Request": ListValidation(
            when=Leaf("Title", "ne", ""), message="Give it a title.",
        )},
    )
    # Once per entity, not once per form.
    finding = only(findings, FindingCode.LISTS_FORM_LIST_VALIDATION_IS_SILENT)
    assert finding.severity == "warning"


def test_spec_refused_example_column_rules() -> None:
    schema = make_schema(
        make_table(
            "Request",
            column("Status", "priority"),
            make_ref("Site", "Site.Id"),
            note="A request.",
        ),
        make_table("Site", column("Title", required=True), note="A site."),
        enums=[enum("priority", "Low", "Normal", "High")],
    )
    findings = _check(
        _q("Status", sets_column=("required",)), _q("Site"),
        schema=schema,
        form_visibility={"Request": EntitySection(columns={
            "Status": FormVisibility(new=False, existing=False),
        })},
    )
    assert sorted(f.code for f in findings) == sorted([
        FindingCode.LISTS_FORM_QUESTION_HIDDEN_ON_LIST_FORM,
        FindingCode.LISTS_FORM_QUESTION_SETS_COLUMN,
        FindingCode.LISTS_FORM_LOOKUP_SOURCE_UNREADABLE,
        FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING,
    ])

