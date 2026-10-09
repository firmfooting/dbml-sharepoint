"""Identities: the named accounts a mapping's groups enrol.

A mapping declares which identities a group holds and a build supplies each
identity's values. This module holds the vocabulary both sides share, so a
validator rule and a generator read one table. Pure: no typer and no file
access, so a downstream tool validates values with the same code.
"""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast, get_args

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


class IdentityError(ValueError):
    """A supplied identity value the build refuses before writing anything."""


class IdentityValueMissing(IdentityError):  # noqa: N818 - the spec names the refusal class
    """A required identity some group enrols has no value."""


class IdentityNotDeclared(IdentityError):  # noqa: N818 - the spec names the refusal class
    """A value for a name this mapping neither declares nor enrols."""


class IdentityValueMalformed(IdentityError):  # noqa: N818 - the spec names the refusal class
    """A value that does not parse as KIND:VALUE."""


class IdentityKindNotAllowed(IdentityError):  # noqa: N818 - the spec names the refusal class
    """A value whose kind the identity's `kinds` does not include."""


class IdentityKindNotYetSupported(IdentityError):  # noqa: N818 - the spec names the refusal class
    """A group kind, refused until the sandbox probe proves the claim it builds."""


class SharePointGroupNotEnrollable(IdentityError):  # noqa: N818 - the spec names the refusal class
    """A value naming a SharePoint group, which cannot be a member of another."""


class IdentityValueCount(IdentityError):  # noqa: N818 - the spec names the refusal class
    """More values than the identity takes."""


class IdentityGivenTwice(IdentityError):  # noqa: N818 - the spec names the refusal class
    """One name given twice in one source."""


_GUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
# PRINCIPAL_KINDS in mapping_types, plus two spellings a person might reach for.
SHAREPOINT_GROUP_WORDS: Final = frozenset({
    "group", "associated_owner_group", "associated_member_group",
    "associated_visitor_group", "sharepoint_group", "site_group",
})
NESTING_REASON = (
    "SharePoint groups cannot be nested (Microsoft Learn: "
    "https://learn.microsoft.com/sharepoint/sites/"
    "determine-permission-levels-and-groups-in-sharepoint-server"
    "#review-available-default-groups; "
    "that page is written for SharePoint Server, so this refusal fails closed on its word). "
    "Grant the permission level to associated_owner_group, associated_member_group or "
    "associated_visitor_group in list_permissions instead."
)


@dataclass(frozen=True)
class IdentityValue:
    """One parsed value: a UPN for a user, an Entra object id for a group."""

    kind: IdentityKind
    value: str
    # m365_group only: the group's owners claim rather than its members.
    owners: bool = False

    @property
    def spelled(self) -> str:
        return f"{self.kind}:{self.value}" + (":owners" if self.owners else "")


def _user_problem(upn: str) -> str | None:
    # The same rules as project.validate_enterprise_reader, which the alias still runs.
    if upn.count("@") != 1:
        return "a user value is a UPN with exactly one '@'"
    if any(c.isspace() or c == "|" or ord(c) < 0x20 or ord(c) == 0x7F for c in upn):
        return "a user value has no whitespace, no '|' and no control characters"
    if "#ext#" in upn or upn.startswith("live.com#"):
        return "guest and Microsoft account logins are not enrolled by this tool"
    return None


def _parse_one(name: str, item: str) -> IdentityValue:
    kind, sep, rest = item.partition(":")
    if not sep or not rest:
        raise IdentityValueMalformed(f"identity {name}: {item!r} is not KIND:VALUE")
    if kind in SHAREPOINT_GROUP_WORDS:
        raise SharePointGroupNotEnrollable(f"identity {name}: {item!r}. {NESTING_REASON}")
    if kind not in IDENTITY_KINDS:
        raise IdentityValueMalformed(
            f"identity {name}: kind {kind!r} is not one of {', '.join(sorted(IDENTITY_KINDS))}",
        )
    lowered = rest.lower()
    if kind == "user":
        if problem := _user_problem(lowered):
            raise IdentityValueMalformed(f"identity {name}: {item!r}: {problem}")
        return IdentityValue("user", lowered)
    owners = kind == "m365_group" and lowered.endswith(":owners")
    guid = lowered.removesuffix(":owners") if owners else lowered
    if not _GUID.fullmatch(guid):
        raise IdentityValueMalformed(
            f"identity {name}: {item!r}: a group value is the Entra object id, a GUID",
        )
    return IdentityValue(cast("IdentityKind", kind), guid, owners=owners)


def parse_values(name: str, raw: str) -> tuple[IdentityValue, ...]:
    """`KIND:VALUE[,KIND:VALUE...]`, refused whole when any part is wrong."""
    if not raw or raw != raw.strip():
        raise IdentityValueMalformed(f"identity {name}: a value must not be empty or padded")
    return tuple(_parse_one(name, item) for item in raw.split(","))


def identity_hash(values: Sequence[IdentityValue]) -> str:
    """SHA-256 of the sorted spellings, 12 hex digits. One value hashes `kind:value` exactly."""
    joined = ",".join(sorted(v.spelled for v in values))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:12]


def describe_identity(name: str, values: Sequence[IdentityValue]) -> str:
    """How every persisted artefact names an identity: never by its value."""
    return f"{name} (sha256:{identity_hash(values)})"
