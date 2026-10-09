"""Which values each group enrols: one table for the deploy, manifest, assess and verify.

`values` are for the generated private scripts only. `described` is the one
string that may reach a persisted artefact.
"""

from collections.abc import Mapping as AbcMapping
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from dbml_sharepoint.analysis.resolve import ResolvedMapping, guards_resolution
from dbml_sharepoint.model.identities import (
    IdentityValue,
    MembershipMode,
    claim_for,
    describe_identity,
)
from dbml_sharepoint.model.mapping_types import MappingBundle

_CEILINGS: dict[str, Literal["reader", "automation"]] = {
    "enterprise_reader": "reader", "automation": "automation",
}


@dataclass(frozen=True)
class EnrolmentRow:
    identity: str
    ceiling: Literal["reader", "automation"] | None
    values: tuple[IdentityValue, ...]
    described: str


@dataclass(frozen=True)
class GroupEnrolment:
    group: str
    membership: MembershipMode
    rows: tuple[EnrolmentRow, ...]
    during_run: tuple[str, ...]


@guards_resolution
def enrolment_plan(
    bundle: MappingBundle, resolved: ResolvedMapping,
    identities: AbcMapping[str, tuple[IdentityValue, ...]],
) -> tuple[GroupEnrolment, ...]:
    # Resolved groups, not declarations: a `{member}` template name matches no deployed group.
    plan = []
    for grp in resolved.groups:
        rows = tuple(
            EnrolmentRow(
                identity=name, ceiling=_CEILINGS.get(name),
                values=identities.get(name, ()),
                described=describe_identity(name, identities.get(name, ())),
            )
            for name in grp.enroll
        )
        if any(row.values for row in rows):
            plan.append(GroupEnrolment(grp.name, grp.membership, rows, grp.enroll_during_run))
    return tuple(plan)


def as_json(plan: Sequence[GroupEnrolment]) -> list[dict[str, Any]]:
    return [
        {
            "group": g.group, "membership": g.membership, "during_run": list(g.during_run),
            "rows": [
                {
                    "identity": r.identity, "ceiling": r.ceiling, "described": r.described,
                    "values": [
                        {
                            "kind": v.kind, "value": v.value, "owners": v.owners,
                            "claim": claim_for(v),
                        }
                        for v in r.values
                    ],
                }
                for r in g.rows
            ],
        }
        for g in plan
    ]
