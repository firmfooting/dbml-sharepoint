# src/dbml_sharepoint/analysis/checks/_renames.py
"""`renamed_from` on an entity: the previous list names a redeploy may adopt.

The deploy adopts a list under a previous name only when nothing carries the
current one, and then retitles it. Both rules here refuse a declaration that
would make that adoption ambiguous before any site is touched.
"""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    entities = vc.bundle.mapping.entities
    claims: dict[str, list[str]] = {}
    for entity_name, entity in entities.items():
        at = Location(Section.ENTITIES, entity=entity_name, sub="renamed_from")
        for previous in entity.renamed_from:
            claims.setdefault(previous, []).append(entity_name)
            if previous in entities:
                findings.append(Finding(
                    FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY,
                    f"entities[{entity_name}].renamed_from names {previous!r}, "
                    f"which is still a declared entity. A redeploy would find "
                    f"both lists and could not tell a rename from a collision. "
                    f"Remove the declaration that no longer exists, or drop the "
                    f"name from renamed_from.",
                    location=at,
                ))
    for previous, claimants in claims.items():
        if len(claimants) > 1:
            findings.append(Finding(
                FindingCode.RENAMED_FROM_CLAIMED_TWICE,
                f"renamed_from names {previous!r} more than once "
                f"({', '.join(claimants)}), so two lists would race to adopt "
                f"one existing list. A previous name belongs to exactly one "
                f"entity, once.",
                location=Location(
                    Section.ENTITIES, entity=claimants[0], sub="renamed_from",
                ),
            ))
    return findings
