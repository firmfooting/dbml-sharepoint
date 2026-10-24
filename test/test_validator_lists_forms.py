"""Validator: `lists-forms.yaml`, the column and structure refusals.

A Lists form shows and accepts whatever columns it names, so each rule here
refuses a question the form would present differently from the list, or one
a respondent could not complete.
"""

from pathlib import Path
from typing import Unpack

import pytest
from _findings import none_of, only
from _model import MappingSections, column, enum, person
from _model import bundle as make_bundle
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.checks._lists_forms import DESCRIPTION_MAX, MESSAGE_MAX, TITLE_MAX
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.conditions import Leaf
from dbml_sharepoint.model.lists_forms import LISTS_FORMS_FILE_NAME, read_lists_forms_file
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
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
    findings = _check(_q("Title"), _q("Due", sets_column=("required",)))
    assert only(findings, FindingCode.LISTS_FORM_QUESTION_SETS_COLUMN).location == _at(1)


def test_lists_form_question_sets_column_fires_when_include_time_is_declared() -> None:
    findings = _check(_q("Title"), _q("Due", sets_column=("include_time",)))
    assert only(findings, FindingCode.LISTS_FORM_QUESTION_SETS_COLUMN).location == _at(1)


def test_lists_form_question_sets_column_names_both_keys_in_one_sentence() -> None:
    findings = _check(_q("Title"), _q("Due", sets_column=("required", "include_time")))
    message = only(findings, FindingCode.LISTS_FORM_QUESTION_SETS_COLUMN).message
    assert "`required` and `include_time`" in message


def test_lists_form_required_column_missing_fires_when_a_not_null_column_is_left_off() -> None:
    findings = _check(_q("Details"))
    finding = only(findings, FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING)
    assert finding.location == Location(Section.LISTS_FORMS, entity="Request", sub="forms[0]")
    assert "'Title'" in finding.message


def test_an_undeclared_title_is_optional_and_may_still_be_asked() -> None:
    # The deploy patches the built-in Title optional when the DBML omits it.
    schema = make_schema(
        make_table("Request", column("Details", "longtext"), note="A request."),
    )
    assert _check(_q("Details"), schema=schema, entities=["Request"]) == []
    assert _check(_q("Title"), _q("Details"), schema=schema, entities=["Request"]) == []


def test_lists_form_lookup_source_unreadable_fires_when_a_lookup_is_not_acknowledged() -> None:
    findings = _check(_q("Title"), _q("Site"), schema=_schema(make_ref("Site", "Site.Id")))
    assert only(findings, FindingCode.LISTS_FORM_LOOKUP_SOURCE_UNREADABLE).location == _at(1)


def test_lists_form_attachments_off_fires_when_the_list_takes_no_attachments() -> None:
    findings = _check(_q("Title"), _q("Attachments"), attachments=False)
    finding = only(findings, FindingCode.LISTS_FORM_ATTACHMENTS_OFF)
    assert finding.location == _at(1)
    assert "the mapping declares `attachments: false`" in finding.message


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


def test_lists_form_list_validation_is_silent_fires_when_a_column_rule_is_hoisted() -> None:
    # A column rule comparing a date with the clock is deployed on the list rule.
    findings = _check(
        _q("Title"),
        column_validation={"Request": EntitySection(columns={
            "Due": ColumnValidation(when=Leaf("Due", "geq", "today"), message="Not in the past."),
        })},
    )
    only(findings, FindingCode.LISTS_FORM_LIST_VALIDATION_IS_SILENT)


def test_a_column_rule_that_stays_on_the_column_is_not_silent() -> None:
    findings = _check(
        _q("Title"),
        column_validation={"Request": EntitySection(columns={
            "Details": ColumnValidation(when=Leaf("Details", "ne", "x"), message="Not x."),
        })},
    )
    none_of(findings, FindingCode.LISTS_FORM_LIST_VALIDATION_IS_SILENT)


@pytest.mark.parametrize(("type_", "default"), [
    ("nvarchar", "n/a"), ("int", 1), ("number", 1), ("boolean", True),
    ("date", "2026-01-01"), ("datetime", "2026-01-01T09:00:00Z"),
])
def test_a_deployed_default_exempts_a_required_column(type_: str, default: str | int) -> None:
    schema = _schema(column("Extra", type_, required=True, default=default))
    none_of(_check(_q("Title"), schema=schema), FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING)


@pytest.mark.parametrize(("type_", "default"), [
    ("longtext", "n/a"), ("richtext", "n/a"), ("hyperlink", "https://example.com"),
    ("person", "someone@example.com"),
])
def test_lists_form_required_column_missing_fires_when_the_default_is_not_deployed(
    type_: str, default: str,
) -> None:
    # The deploy writes no DefaultValue for these kinds, so the column stays required.
    schema = _schema(column("Extra", type_, required=True, default=default))
    finding = only(
        _check(_q("Title"), schema=schema), FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING,
    )
    assert "'Extra'" in finding.message


def test_spec_refused_example_column_rules() -> None:
    schema = make_schema(
        make_table(
            "Request",
            column("Title", required=True),
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



# --- title, text, link and schedule refusals ------------------------------


_FORM_AT = Location(Section.LISTS_FORMS, entity="Request", sub="forms[0]")


def _form(
    title: str = "Intake",
    description: str = "",
    thank_you: str | None = None,
    closed_message: str | None = None,
    opens: str | None = None,
    closes: str | None = None,
) -> list[Finding]:
    """One form asking for Title, with the text and schedule given."""
    form = ListsForm(
        title=title, questions=(_q("Title"),), description=description, thank_you=thank_you,
        closed_message=closed_message, opens=opens, closes=closes,
    )
    return _check(lists_forms={"Request": EntityListsForms(forms=(form,))})


def _two(first: ListsForm, second: ListsForm, retired: tuple[str, ...] = ()) -> list[Finding]:
    return _check(lists_forms={"Request": EntityListsForms(forms=(first, second), retired=retired)})


def _named(title: str, *previous: str) -> ListsForm:
    return ListsForm(title=title, questions=(_q("Title"),), previous_titles=previous)


def test_lists_form_title_invalid_fires_when_the_title_holds_a_line_break() -> None:
    assert only(_form(title="Intake\rform"), FindingCode.LISTS_FORM_TITLE_INVALID).location == (
        _FORM_AT
    )


def test_whitespace_title_is_empty() -> None:
    only(_form(title="  "), FindingCode.LISTS_FORM_TITLE_INVALID)


def test_title_at_80_is_accepted_and_81_refused() -> None:
    assert _form(title="x" * TITLE_MAX) == []
    only(_form(title="x" * (TITLE_MAX + 1)), FindingCode.LISTS_FORM_TITLE_INVALID)


def test_lists_form_title_invalid_fires_when_two_forms_share_a_title() -> None:
    finding = only(_two(_named("Intake"), _named("Intake")), FindingCode.LISTS_FORM_TITLE_INVALID)
    # Reported on the later form, as a repeated question is.
    assert finding.location == Location(Section.LISTS_FORMS, entity="Request", sub="forms[1]")


def test_lists_form_title_invalid_fires_when_a_title_is_another_forms_previous_title() -> None:
    findings = _two(_named("Intake", "Old intake"), _named("Old intake"))
    only(findings, FindingCode.LISTS_FORM_TITLE_INVALID)


def test_lists_form_title_invalid_fires_when_two_forms_share_a_previous_title() -> None:
    findings = _two(_named("Intake", "Old"), _named("Follow-up", "Old"))
    only(findings, FindingCode.LISTS_FORM_TITLE_INVALID)


def test_lists_form_title_invalid_fires_when_a_previous_title_is_retired() -> None:
    findings = _two(_named("Intake", "Old"), _named("Follow-up"), retired=("Old",))
    assert only(findings, FindingCode.LISTS_FORM_TITLE_INVALID).location == _FORM_AT


def test_lists_form_retired_and_declared_fires_when_a_title_is_retired() -> None:
    findings = _two(_named("Intake"), _named("Follow-up"), retired=("Intake",))
    assert only(findings, FindingCode.LISTS_FORM_RETIRED_AND_DECLARED).location == _FORM_AT


def test_description_at_1260_is_accepted() -> None:
    assert _form(description="x" * DESCRIPTION_MAX) == []


def test_lists_form_text_too_long_fires_when_the_description_is_over_1260() -> None:
    only(_form(description="x" * (DESCRIPTION_MAX + 1)), FindingCode.LISTS_FORM_TEXT_TOO_LONG)


def test_lists_form_text_too_long_fires_when_the_thank_you_is_over_300() -> None:
    assert _form(thank_you="x" * MESSAGE_MAX) == []
    only(_form(thank_you="x" * (MESSAGE_MAX + 1)), FindingCode.LISTS_FORM_TEXT_TOO_LONG)


def test_lists_form_text_too_long_fires_when_the_closed_message_is_over_300() -> None:
    only(_form(closed_message="x" * (MESSAGE_MAX + 1)), FindingCode.LISTS_FORM_TEXT_TOO_LONG)


def test_lists_form_link_markup_fires_when_the_description_holds_a_markdown_link() -> None:
    findings = _form(description="See [the policy](https://example.com/p).")
    assert only(findings, FindingCode.LISTS_FORM_LINK_MARKUP).location == _FORM_AT


def test_lists_form_link_markup_fires_when_a_help_holds_an_anchor() -> None:
    findings = _check(_q("Title", help='See <A href="https://example.com">here</A>.'))
    assert only(findings, FindingCode.LISTS_FORM_LINK_MARKUP).location == _at(0)


def test_lists_form_link_not_https_fires_when_the_description_holds_http() -> None:
    only(_form(description="See HTTP://example.com/x"), FindingCode.LISTS_FORM_LINK_NOT_HTTPS)


def test_lists_form_link_not_https_fires_when_a_help_holds_mailto() -> None:
    findings = _check(_q("Title", help="Write to mailto:desk@example.com"))
    assert only(findings, FindingCode.LISTS_FORM_LINK_NOT_HTTPS).location == _at(0)


def test_https_www_url_is_not_a_bare_www() -> None:
    assert _form(description="See https://www.example.com/x") == []
    assert _form(description="See https://example.com/www.x") == []
    only(_form(description="See www.example.com"), FindingCode.LISTS_FORM_LINK_NOT_HTTPS)


def test_lists_form_image_in_text_fires_when_a_label_holds_an_img_tag() -> None:
    findings = _check(_q("Title", label='Name <IMG src="https://example.com/a.png">'))
    assert only(findings, FindingCode.LISTS_FORM_IMAGE_IN_TEXT).location == _at(0)


def test_lists_form_image_in_text_fires_when_the_title_holds_markdown_image() -> None:
    findings = _form(title="![logo](https://example.com/a.png) Intake")
    only(findings, FindingCode.LISTS_FORM_IMAGE_IN_TEXT)


def test_image_markdown_is_not_also_link_markup() -> None:
    findings = _form(description="![x](https://example.com/a.png)")
    assert [f.code for f in findings] == [FindingCode.LISTS_FORM_IMAGE_IN_TEXT]


def test_lists_form_link_in_message_fires_when_the_closed_message_holds_www() -> None:
    findings = _form(closed_message="Try www.example.com instead.")
    assert only(findings, FindingCode.LISTS_FORM_LINK_IN_MESSAGE).location == _FORM_AT


def test_lists_form_schedule_invalid_fires_when_a_time_has_no_offset() -> None:
    only(_form(opens="2026-11-02T09:00:00"), FindingCode.LISTS_FORM_SCHEDULE_INVALID)


def test_lists_form_schedule_invalid_fires_when_a_time_does_not_parse() -> None:
    only(_form(closes="next Friday"), FindingCode.LISTS_FORM_SCHEDULE_INVALID)


def test_date_only_schedule_is_refused() -> None:
    only(_form(opens="2026-11-02"), FindingCode.LISTS_FORM_SCHEDULE_INVALID)


def test_lists_form_schedule_invalid_fires_when_closes_is_not_after_opens() -> None:
    # The same instant in two zones is not "after".
    findings = _form(opens="2026-11-02T09:00:00+11:00", closes="2026-11-01T22:00:00Z")
    only(findings, FindingCode.LISTS_FORM_SCHEDULE_INVALID)


def test_a_valid_schedule_is_accepted() -> None:
    assert _form(opens="2026-11-02T09:00:00+11:00", closes="2026-12-18T17:00:00Z") == []


def test_block_scalar_title_is_refused_but_block_description_is_not(tmp_path: Path) -> None:
    (tmp_path / LISTS_FORMS_FILE_NAME).write_text(
        "Request:\n  forms:\n    - title: |\n        Intake\n"
        "      description: |\n        First line.\n        Second line.\n"
        "      questions:\n        - column: Title\n",
        encoding="utf-8",
    )
    findings = _check(lists_forms=read_lists_forms_file(tmp_path))
    assert [f.code for f in findings] == [FindingCode.LISTS_FORM_TITLE_INVALID]


def test_spec_refused_example_text_rules() -> None:
    findings = _form(title="Intake\nform", thank_you="Track it at https://example.com/track")
    assert sorted(f.code for f in findings) == sorted([
        FindingCode.LISTS_FORM_TITLE_INVALID,
        FindingCode.LISTS_FORM_LINK_IN_MESSAGE,
    ])
