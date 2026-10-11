"""Validator: the `governance` section.

Every test makes its rule fire, because the reachability gate wants a test
that causes the finding and not a reference to its code. Vocabularies here
are invented; core ships none.
"""

from pathlib import Path

from _findings import none_of, only
from _model import bundle, column, schema, table
from _packs import blocks, entities, pack

from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.mapping_types import (
    ColumnGovernance,
    Governance,
    GovernanceVocabulary,
    ListGovernance,
    MappingBundle,
    RetentionPolicy,
)
from dbml_sharepoint.model.parser import Schema

_GOVERNANCE_CODES = {
    FindingCode.GOVERNANCE_UNKNOWN_ENTITY,
    FindingCode.GOVERNANCE_UNKNOWN_COLUMN,
    FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
    FindingCode.GOVERNANCE_UNKNOWN_RETENTION_POLICY,
}

_VOCABULARY = GovernanceVocabulary(
    classification=("open", "internal", "restricted"),
    personal_data=("none", "contact", "sensitive"),
    owners=("list_steward", "records_lead"),
)

_POLICY = RetentionPolicy(
    name="keep_seven_years",
    description="Seven years.",
    sp_label="",
    retain_years=7,
    retain_days=None,
    trigger="creation",
)


def _inputs(governance: Governance, *, policies: bool = True) -> tuple[Schema, MappingBundle]:
    """A `Risk` list with a `Notes` column, and an `Elsewhere` table the mapping omits."""
    return (
        schema(
            table("Risk", column("Title", required=True), "Notes", note="Risks."),
            table("Elsewhere", column("Title", required=True), note="Not mapped."),
        ),
        bundle(
            entities=["Risk"],
            governance=governance,
            retention_policies={"keep_seven_years": _POLICY} if policies else {},
        ),
    )


def _governance_findings(governance: Governance, *, policies: bool = True) -> list[Finding]:
    found = validate_against_mapping(*_inputs(governance, policies=policies))
    return [f for f in found if f.code in _GOVERNANCE_CODES]


def _risk(
    *,
    purpose: str | None = None,
    owner: str | None = None,
    classification: str | None = None,
    personal_data: str | None = None,
    retention: str | None = None,
    columns: dict[str, ColumnGovernance] | None = None,
) -> Governance:
    return Governance(
        vocabulary=_VOCABULARY,
        lists={
            "Risk": ListGovernance(
                purpose=purpose,
                owner=owner,
                classification=classification,
                personal_data=personal_data,
                retention=retention,
                columns=columns or {},
            ),
        },
    )


def test_a_clean_section_reports_nothing() -> None:
    governance = _risk(
        purpose="Tracks risks.",
        owner="list_steward",
        classification="internal",
        personal_data="contact",
        retention="keep_seven_years",
        columns={"Notes": ColumnGovernance(purpose="Commentary.", personal_data="sensitive")},
    )
    assert _governance_findings(governance) == []


def test_no_section_reports_nothing() -> None:
    assert _governance_findings(Governance()) == []


def test_an_entry_for_an_entity_the_schema_lacks_is_refused() -> None:
    governance = Governance(lists={"Ghost": ListGovernance(purpose="Nothing.")})
    found = only(_governance_findings(governance), FindingCode.GOVERNANCE_UNKNOWN_ENTITY)
    assert found.location == Location(Section.GOVERNANCE, entity="Ghost")
    assert "'Ghost'" in found.message


def test_an_entry_for_a_table_the_mapping_does_not_deploy_is_refused() -> None:
    governance = Governance(lists={"Elsewhere": ListGovernance(purpose="Not deployed.")})
    only(_governance_findings(governance), FindingCode.GOVERNANCE_UNKNOWN_ENTITY)


def test_an_unknown_entity_is_not_also_judged_on_its_values() -> None:
    governance = Governance(lists={"Ghost": ListGovernance(owner="nobody")})
    assert [f.code for f in _governance_findings(governance)] == [
        FindingCode.GOVERNANCE_UNKNOWN_ENTITY,
    ]


def test_an_entry_for_a_column_the_schema_lacks_is_refused() -> None:
    governance = _risk(columns={"Ghost": ColumnGovernance(purpose="Nothing.")})
    found = only(_governance_findings(governance), FindingCode.GOVERNANCE_UNKNOWN_COLUMN)
    assert found.location == Location(Section.GOVERNANCE, entity="Risk", column="Ghost")
    assert "'Ghost'" in found.message


def test_a_list_value_outside_the_vocabulary_is_refused() -> None:
    found = only(
        _governance_findings(_risk(classification="top_secret")),
        FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
    )
    assert found.location == Location(Section.GOVERNANCE, entity="Risk", sub="classification")
    assert "'top_secret'" in found.message
    assert "'restricted'" in found.message


def test_an_owner_outside_the_declared_roles_is_refused() -> None:
    found = only(
        _governance_findings(_risk(owner="somebody")),
        FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
    )
    assert found.location == Location(Section.GOVERNANCE, entity="Risk", sub="owner")
    assert "governance.vocabulary.owners" in found.message


def test_a_column_personal_data_value_outside_the_vocabulary_is_refused() -> None:
    governance = _risk(columns={"Notes": ColumnGovernance(personal_data="medical")})
    found = only(
        _governance_findings(governance),
        FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
    )
    assert found.location == Location(
        Section.GOVERNANCE, entity="Risk", column="Notes", sub="personal_data",
    )


def test_a_value_differing_only_in_case_is_refused() -> None:
    found = only(
        _governance_findings(_risk(classification="Restricted")),
        FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
    )
    assert "'Restricted'" in found.message
    assert "'restricted'" in found.message


def test_a_mapping_with_no_vocabulary_can_use_no_values() -> None:
    governance = Governance(lists={"Risk": ListGovernance(owner="list_steward")})
    found = only(
        _governance_findings(governance),
        FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
    )
    assert "declares none" in found.message


def test_free_text_purpose_needs_no_vocabulary() -> None:
    governance = Governance(lists={"Risk": ListGovernance(purpose="Anything at all.")})
    assert _governance_findings(governance) == []


def test_a_retention_reference_to_an_undeclared_policy_is_refused() -> None:
    found = only(
        _governance_findings(_risk(retention="keep_forever")),
        FindingCode.GOVERNANCE_UNKNOWN_RETENTION_POLICY,
    )
    assert found.location == Location(Section.GOVERNANCE, entity="Risk", sub="retention")
    assert "'keep_forever'" in found.message
    assert "'keep_seven_years'" in found.message


def test_a_retention_reference_with_no_policies_loaded_names_the_source_key() -> None:
    found = only(
        _governance_findings(_risk(retention="keep_seven_years"), policies=False),
        FindingCode.GOVERNANCE_UNKNOWN_RETENTION_POLICY,
    )
    assert "retention_policies_source" in found.message


def test_every_problem_in_one_section_is_reported_together() -> None:
    governance = Governance(
        vocabulary=_VOCABULARY,
        lists={
            "Ghost": ListGovernance(),
            "Risk": ListGovernance(
                owner="somebody",
                retention="keep_forever",
                columns={"Ghost": ColumnGovernance()},
            ),
        },
    )
    assert [f.code for f in _governance_findings(governance)] == [
        FindingCode.GOVERNANCE_UNKNOWN_ENTITY,
        FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
        FindingCode.GOVERNANCE_UNKNOWN_RETENTION_POLICY,
        FindingCode.GOVERNANCE_UNKNOWN_COLUMN,
    ]


def test_a_retired_column_can_still_carry_governance(tmp_path: Path) -> None:
    """Retirement keeps the column declared, and the data stays on the site."""
    parsed_schema, loaded = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
              Notes nvarchar
            }
        """,
        mapping=blocks(entities("Risk"), """
            retired_columns:
              Risk: [Notes]
            governance:
              vocabulary:
                personal_data: [none, contact]
              lists:
                Risk:
                  columns:
                    Notes: { personal_data: contact }
        """),
    )
    found = validate_against_mapping(parsed_schema, loaded)
    for code in _GOVERNANCE_CODES:
        none_of(found, code)


def test_a_loaded_section_reaches_the_validator(tmp_path: Path) -> None:
    parsed_schema, loaded = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
            }
        """,
        mapping=blocks(entities("Risk"), """
            governance:
              vocabulary:
                owners: [list_steward]
              lists:
                Risk: { owner: records_lead }
        """),
    )
    only(
        validate_against_mapping(parsed_schema, loaded),
        FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
    )
