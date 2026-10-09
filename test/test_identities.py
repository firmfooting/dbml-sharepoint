"""The identity vocabulary: built-ins, names, kinds, and a group's defaults."""

import hashlib

import pytest

from dbml_sharepoint.model.identities import (
    BUILTIN_IDENTITIES,
    IDENTITY_KINDS,
    MEMBERSHIP_MODES,
    NAME_PATTERN,
    SHAREPOINT_GROUP_WORDS,
    IdentityError,
    IdentityKindNotYetSupported,
    IdentityValue,
    IdentityValueMalformed,
    SharePointGroupNotEnrollable,
    describe_identity,
    identity_hash,
    is_run_lifetime,
    parse_values,
)
from dbml_sharepoint.model.mapping_types import PRINCIPAL_KINDS, SiteGroup


def test_the_three_built_ins_and_their_lifetimes() -> None:
    assert set(BUILTIN_IDENTITIES) == {"enterprise_reader", "automation", "operator"}
    # Ruling A1: a family with a reader group builds without a reader value.
    assert BUILTIN_IDENTITIES["enterprise_reader"].required is False
    assert BUILTIN_IDENTITIES["automation"].required is True
    assert BUILTIN_IDENTITIES["enterprise_reader"].count == "one"
    assert BUILTIN_IDENTITIES["automation"].count == "many"
    assert BUILTIN_IDENTITIES["operator"].count == "none"
    assert is_run_lifetime("operator")
    assert not is_run_lifetime("automation")
    assert not is_run_lifetime("records_clerk")


def test_every_built_in_takes_users_only_until_the_probe_passes() -> None:
    # Ruling A6.
    assert all(b.kinds == ("user",) for b in BUILTIN_IDENTITIES.values())


def test_the_closed_vocabularies() -> None:
    assert {"user", "security_group", "m365_group"} == IDENTITY_KINDS
    assert {"additive", "exclusive"} == MEMBERSHIP_MODES


@pytest.mark.parametrize("name", ["a", "records_clerk", "x" + "1" * 63, "a_1_b"])
def test_a_name_the_env_key_can_spell_is_accepted(name: str) -> None:
    assert NAME_PATTERN.fullmatch(name)


@pytest.mark.parametrize("name", ["", "Records", "1a", "a-b", "a" * 65, "a b", "_a"])
def test_a_name_the_env_key_cannot_spell_is_refused(name: str) -> None:
    assert NAME_PATTERN.fullmatch(name) is None


def test_a_group_enrols_nobody_by_default() -> None:
    group = SiteGroup(
        name="G", description="", owner_group="Site Owners",
        allow_members_edit_membership=False, allow_request_to_join_leave=False,
        auto_accept_request_to_join_leave=False,
        only_allow_members_view_membership=False,
    )
    assert group.enroll == ()
    assert group.enroll_during_run == ()
    assert group.membership == "additive"
    assert group.legacy_flags == ()


_GUID = "0F8FAD5B-D9CB-469F-A165-70867728950E"


def test_a_user_value_is_lower_cased() -> None:
    assert parse_values("automation", "user:Flows@Example.com") == (
        IdentityValue("user", "flows@example.com"),
    )


def test_several_values_keep_their_order() -> None:
    values = parse_values("automation", "user:a@example.com,user:b@example.com")
    assert [v.value for v in values] == ["a@example.com", "b@example.com"]


def test_a_group_value_is_a_lower_case_guid() -> None:
    (value,) = parse_values("intake", f"security_group:{_GUID}")
    assert value == IdentityValue("security_group", _GUID.lower())


def test_the_owners_form_parses_and_is_marked() -> None:
    (value,) = parse_values("leads", f"m365_group:{_GUID}:owners")
    assert value.owners is True
    assert value.spelled == f"m365_group:{_GUID.lower()}:owners"


@pytest.mark.parametrize("raw", [
    "", " user:a@example.com", "a@example.com", "mailbox:a@example.com",
    "user:", "user:a@b@example.com", "user:a @example.com",
    "user:i:0#.f|membership|a@example.com", "user:a\x07@example.com",
    "user:guest_example.org#EXT#@example.com", "user:live.com#a@example.com",
    "security_group:not-a-guid", f"user:{_GUID}:owners",
    f"security_group:{_GUID}:owners", "user:a@example.com,",
])
def test_a_value_that_does_not_parse_is_malformed(raw: str) -> None:
    with pytest.raises(IdentityValueMalformed, match="automation"):
        parse_values("automation", raw)


@pytest.mark.parametrize("kind", ["group", "sharepoint_group", "associated_member_group"])
def test_a_sharepoint_group_kind_is_refused_with_the_nesting_reason(kind: str) -> None:
    with pytest.raises(SharePointGroupNotEnrollable, match="cannot be nested"):
        parse_values("automation", f"{kind}:Site Members")


def test_one_value_hashes_exactly_its_spelling() -> None:
    expected = hashlib.sha256(b"user:flows@example.com").hexdigest()[:12]
    assert identity_hash((IdentityValue("user", "flows@example.com"),)) == expected


def test_the_hash_ignores_order_and_case() -> None:
    a = parse_values("automation", "user:B@example.com,user:a@example.com")
    b = parse_values("automation", "user:a@example.com,user:b@example.com")
    assert identity_hash(a) == identity_hash(b)


def test_a_description_carries_the_name_and_hash_and_never_the_value() -> None:
    values = parse_values("automation", "user:flows@example.com")
    described = describe_identity("automation", values)
    assert described == f"automation (sha256:{identity_hash(values)})"
    assert "example.com" not in described


def test_the_kind_not_yet_supported_error_is_an_identity_error() -> None:
    assert issubclass(IdentityKindNotYetSupported, IdentityError)


def test_the_sharepoint_group_words_cover_every_grant_principal_kind() -> None:
    assert PRINCIPAL_KINDS <= SHAREPOINT_GROUP_WORDS


def test_claim_for_builds_the_claim_from_the_kind_and_refuses_owners() -> None:
    from dbml_sharepoint.model.identities import claim_for

    assert claim_for(IdentityValue("user", "a@example.com")) == "a@example.com"
    assert claim_for(IdentityValue("security_group", _GUID.lower())) == (
        f"c:0t.c|tenant|{_GUID.lower()}"
    )
    assert claim_for(IdentityValue("m365_group", _GUID.lower())) == (
        f"c:0o.c|federateddirectoryclaimprovider|{_GUID.lower()}"
    )
    with pytest.raises(IdentityKindNotYetSupported):
        claim_for(IdentityValue("m365_group", _GUID.lower(), owners=True))
