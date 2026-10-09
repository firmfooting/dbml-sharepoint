"""The identity vocabulary: built-ins, names, kinds, and a group's defaults."""

import pytest

from dbml_sharepoint.model.identities import (
    BUILTIN_IDENTITIES,
    IDENTITY_KINDS,
    MEMBERSHIP_MODES,
    NAME_PATTERN,
    is_run_lifetime,
)
from dbml_sharepoint.model.mapping_types import SiteGroup


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
