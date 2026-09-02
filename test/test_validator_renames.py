# test/test_validator_renames.py
"""`renamed_from` on an entity: the previous list names a redeploy may adopt.

Each rule here refuses a declaration the deploy could not act on safely: a
previous name that is still a declared entity would make the preflight find
both, and one claimed by two entities would make two lists race for one.
"""

from _findings import none_of, only
from _model import bundle as make_bundle
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.mapping_types import (
    CustomPermissionLevel,
    EntityMapping,
    PermissionsConfig,
    SiteGroup,
)


def _entity(name: str, *previous: str) -> EntityMapping:
    return EntityMapping(
        name=name, kind="List", base_template=100, site_role="default",
        renamed_from=tuple(previous),
    )


def _findings(entities: dict[str, EntityMapping]) -> list[Finding]:
    schema = make_schema(*(make_table(n, "Title", note=f"{n} note") for n in entities))
    return validate_against_mapping(schema, make_bundle(entities=entities))


def test_a_clean_rename_declaration_is_silent() -> None:
    found = _findings({"Risk": _entity("Risk", "ProgramRisk", "ProjectRisk")})
    none_of(found, FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY)
    none_of(found, FindingCode.RENAMED_FROM_CLAIMED_TWICE)
    none_of(found, FindingCode.MARKER_FIELD_HAS_RESERVED_TEXT)


def test_a_previous_name_that_is_still_declared_errors() -> None:
    found = _findings({
        "Risk": _entity("Risk", "Issue"),
        "Issue": _entity("Issue"),
    })
    f = only(found, FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY)
    assert f.severity == "error"
    assert "'Issue'" in f.message and "Risk" in f.message


def test_an_entity_renamed_from_itself_errors() -> None:
    found = _findings({"Risk": _entity("Risk", "Risk")})
    only(found, FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY)


def test_a_previous_name_claimed_by_two_entities_errors() -> None:
    found = _findings({
        "Risk": _entity("Risk", "ProgramRisk"),
        "Hazard": _entity("Hazard", "ProgramRisk"),
    })
    f = only(found, FindingCode.RENAMED_FROM_CLAIMED_TWICE)
    assert "'ProgramRisk'" in f.message
    assert "Hazard" in f.message and "Risk" in f.message


def test_a_previous_name_listed_twice_on_one_entity_errors() -> None:
    found = _findings({"Risk": _entity("Risk", "ProgramRisk", "ProgramRisk")})
    only(found, FindingCode.RENAMED_FROM_CLAIMED_TWICE)


def test_a_previous_name_with_reserved_text_errors() -> None:
    """The old marker is computed from the previous name exactly as the
    current one is from the entity name, so the same grammar applies."""
    found = _findings({"Risk": _entity("Risk", "Program.Risk")})
    f = only(found, FindingCode.MARKER_FIELD_HAS_RESERVED_TEXT)
    assert "previous name" in f.message and "'Program.Risk'" in f.message


def _perms(
    groups: list[SiteGroup], levels: list[CustomPermissionLevel] | None = None,
) -> PermissionsConfig:
    return PermissionsConfig(
        levels=levels or [], groups=groups, default_policy=None, overrides={},
    )


def _group(name: str, *previous: str) -> SiteGroup:
    return SiteGroup(
        name=name, description="", owner_group="Site Owners",
        allow_members_edit_membership=False, allow_request_to_join_leave=False,
        auto_accept_request_to_join_leave=False, only_allow_members_view_membership=False,
        previous_names=tuple(previous),
    )


def _level(name: str, *previous: str) -> CustomPermissionLevel:
    return CustomPermissionLevel(
        name=name, description="", base_permissions=["ViewListItems"],
        previous_names=tuple(previous),
    )


def _perm_findings(
    groups: list[SiteGroup], levels: list[CustomPermissionLevel] | None = None,
) -> list[Finding]:
    schema = make_schema(make_table("Risk", "Title", note="Risks."))
    bundle = make_bundle(entities=["Risk"], permissions=_perms(groups, levels))
    return validate_against_mapping(schema, bundle)


def test_a_previous_group_name_that_is_still_a_declared_group_errors() -> None:
    found = _perm_findings([_group("GOV Leads", "GOV Handlers"), _group("GOV Handlers")])
    f = only(found, FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY)
    assert "group" in f.message and "'GOV Handlers'" in f.message


def test_a_previous_group_name_claimed_by_two_groups_errors() -> None:
    found = _perm_findings(
        [_group("GOV Leads", "Old Leads"), _group("GOV Handlers", "Old Leads")],
    )
    f = only(found, FindingCode.RENAMED_FROM_CLAIMED_TWICE)
    assert "'Old Leads'" in f.message


def test_a_previous_level_name_that_is_still_a_declared_level_errors() -> None:
    found = _perm_findings(
        [], [_level("GOV Submit Only", "GOV Read Only"), _level("GOV Read Only")],
    )
    f = only(found, FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY)
    assert "permission level" in f.message


def test_clean_group_and_level_renames_are_silent() -> None:
    found = _perm_findings(
        [_group("GOV Leads", "ADOPT Program Governance")],
        [_level("GOV Submit Only", "ADOPT Submit Only")],
    )
    none_of(found, FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY)
    none_of(found, FindingCode.RENAMED_FROM_CLAIMED_TWICE)
