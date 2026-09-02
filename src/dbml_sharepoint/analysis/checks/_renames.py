# src/dbml_sharepoint/analysis/checks/_renames.py
"""`renamed_from` on an entity, a group or a permission level: the previous
names a redeploy may adopt.

The deploy adopts an object under a previous name only when nothing carries
the current one, and then retitles it. Both rules here refuse a declaration
that would make that adoption ambiguous before any site is touched.
"""

from collections.abc import Callable, Iterable

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section


def check(vc: ValidationContext) -> list[Finding]:
    mapping = vc.bundle.mapping
    findings = _findings(
        "entity",
        [(name, e.renamed_from) for name, e in mapping.entities.items()],
        lambda name: Location(Section.ENTITIES, entity=name, sub="renamed_from"),
    )
    perms = mapping.permissions
    if perms is not None:
        findings += _findings(
            "group",
            [(g.name, g.previous_names) for g in perms.groups],
            lambda _name: Location(Section.GROUPS),
        )
        findings += _findings(
            "permission level",
            [(lvl.name, lvl.previous_names) for lvl in perms.levels],
            lambda _name: Location(Section.PERMISSION_LEVELS),
        )
    return findings


def _findings(
    kind: str,
    declared: Iterable[tuple[str, tuple[str, ...]]],
    where: Callable[[str], Location],
) -> list[Finding]:
    declared = list(declared)
    current = {name for name, _previous in declared}
    findings: list[Finding] = []
    claims: dict[str, list[str]] = {}
    for name, previous_names in declared:
        for previous in previous_names:
            claims.setdefault(previous, []).append(name)
            if previous in current:
                findings.append(Finding(
                    FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY,
                    f"{kind} {name!r}: renamed_from resolves to {previous!r}, "
                    f"which is still a declared {kind}. A redeploy would find "
                    f"both and could not tell a rename from a collision. Remove "
                    f"the declaration that no longer exists, or drop the name "
                    f"from renamed_from.",
                    location=where(name),
                ))
    for previous, claimants in claims.items():
        if len(claimants) > 1:
            findings.append(Finding(
                FindingCode.RENAMED_FROM_CLAIMED_TWICE,
                f"renamed_from resolves to {previous!r} on more than one "
                f"{kind} ({', '.join(claimants)}), so two would race to adopt "
                f"one existing object. A previous name belongs to exactly one "
                f"{kind}, once.",
                location=where(claimants[0]),
            ))
    return findings
