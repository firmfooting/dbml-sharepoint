"""Identities: the named accounts a mapping's groups enrol.

A mapping declares which identities a group holds and a build supplies each
identity's values. This module holds the vocabulary both sides share, so a
validator rule and a generator read one table. Pure: no typer and no file
access, so a downstream tool validates values with the same code.
"""

import re
from dataclasses import dataclass
from typing import Final, Literal, get_args

type IdentityKind = Literal["user", "security_group", "m365_group"]
type Lifetime = Literal["persistent", "run"]
type ValueCount = Literal["one", "many", "none"]
type MembershipMode = Literal["additive", "exclusive"]

IDENTITY_KINDS: Final[frozenset[str]] = frozenset(get_args(IdentityKind.__value__))
MEMBERSHIP_MODES: Final[frozenset[str]] = frozenset(get_args(MembershipMode.__value__))
# The env key is DBMLSP_IDENTITY_ plus the upper-cased name, so a name must survive that.
NAME_PATTERN: Final = re.compile(r"[a-z][a-z0-9_]{0,63}")


@dataclass(frozen=True)
class BuiltinIdentity:
    """An identity a mapping may enrol without declaring it."""

    name: str
    description: str
    kinds: tuple[IdentityKind, ...]
    lifetime: Lifetime
    count: ValueCount
    # Whether a build must supply a value when some group enrols it (ruling A1).
    required: bool


BUILTIN_IDENTITIES: Final[dict[str, BuiltinIdentity]] = {
    "enterprise_reader": BuiltinIdentity(
        name="enterprise_reader",
        description="The read-only reporting account.",
        kinds=("user",), lifetime="persistent", count="one", required=False,
    ),
    "automation": BuiltinIdentity(
        name="automation",
        description="The accounts whose flows write to these lists.",
        kinds=("user",), lifetime="persistent", count="many", required=True,
    ),
    "operator": BuiltinIdentity(
        name="operator",
        description="The person running this deploy, added and removed within the run.",
        kinds=("user",), lifetime="run", count="none", required=False,
    ),
}


def is_run_lifetime(name: str) -> bool:
    """Whether `name` is an identity only `enroll_during_run` may hold."""
    builtin = BUILTIN_IDENTITIES.get(name)
    return builtin is not None and builtin.lifetime == "run"
