# src/dbml_sharepoint/analysis/checks/_provenance.py
"""Names the marker interpolates, and the terminator they may not hold.

The deploy tests for the marker with a substring search, which is sound only
while no marker can sit inside another. That holds only while no interpolated
name contains the terminator, so refusing one here is what makes the grammar
prefix-free. Without it, `from risk.` matches inside `from risk.v2.`.
"""

from collections.abc import Iterator

from dbml_sharepoint.analysis import provenance
from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import Finding

_SCHEMA = Location(Section.SCHEMA)
_ENTITIES = Location(Section.ENTITIES)
_LEVELS = Location(Section.PERMISSION_LEVELS)
_GROUPS = Location(Section.GROUPS)


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    # The name as DECLARED. `family_for` folds it, and reporting the folded
    # spelling back names something the author did not write.
    declared = vc.schema.project_name

    if not declared.strip():
        findings.append(Finding(
            FindingCode.MARKER_FAMILY_MISSING,
            "the schema declares no `Project` name, so every object this "
            "build provisions would be attributed to nobody. The marker is "
            "how a later deploy tells its own objects from another family's, "
            "and how rollback decides what it may delete. Declare "
            "`Project my_thing { }`.",
            location=_SCHEMA,
        ))

    findings.extend(
        _terminator_finding(subject, location)
        for subject, name, location in _interpolated_names(vc)
        if provenance.MARKER_TERMINATOR in name
    )
    return findings


def _interpolated_names(
    vc: ValidationContext,
) -> Iterator[tuple[str, str, Location]]:
    """Every name the marker grammar interpolates, with where it came from."""
    declared = vc.schema.project_name
    yield f"the DBML `Project` name {declared!r}", declared, _SCHEMA

    for entity_name in vc.bundle.mapping.entities:
        yield f"entity {entity_name!r}", entity_name, _ENTITIES

    perms = vc.bundle.mapping.permissions
    if perms is None:
        return
    for lvl in perms.levels:
        yield f"permission level {lvl.name!r}", lvl.name, _LEVELS
    for grp in perms.groups:
        yield f"site group {grp.name!r}", grp.name, _GROUPS


def _terminator_finding(subject: str, location: Location) -> Finding:
    return Finding(
        FindingCode.MARKER_FIELD_HAS_TERMINATOR,
        f"{subject} contains {provenance.MARKER_TERMINATOR!r}, which ends "
        f"the provenance marker. A name holding it lets one marker sit "
        f"inside another, so a family whose name is a prefix of this one "
        f"would adopt the object and take whatever access it declares. "
        f"Rename it without the {provenance.MARKER_TERMINATOR!r}.",
        location=location,
    )
