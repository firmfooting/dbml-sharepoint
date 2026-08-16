# src/dbml_sharepoint/analysis/checks/_provenance.py
"""Names the provenance marker interpolates must keep it unambiguous.

The marker ends with `provenance.MARKER_TERMINATOR` and the deploy tests for
it with a substring search. That test is only sound while no marker can sit
inside another, and that holds only while no interpolated name contains the
terminator. Refusing it here is what makes the grammar prefix-free; without
it, `from risk.` matches inside `from risk.v2.`.
"""

from dbml_sharepoint.analysis import provenance
from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.analysis.list_description import family_for
from dbml_sharepoint.analysis.validator import Finding

_SCHEMA = Location(Section.SCHEMA)
_LEVELS = Location(Section.PERMISSION_LEVELS)
_GROUPS = Location(Section.GROUPS)


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    # The RAW name, because `family_for` substitutes `UNNAMED_FAMILY` for an
    # absent one and the substitute is what every such schema then collides on.
    declared = vc.schema.project_name
    family = family_for(vc.schema)

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
    elif provenance.MARKER_TERMINATOR in family:
        findings.append(_terminator_finding(
            f"the DBML `Project` name {family!r}", _SCHEMA,
        ))

    for entity_name in vc.bundle.mapping.entities:
        if provenance.MARKER_TERMINATOR in entity_name:
            findings.append(_terminator_finding(
                f"entity {entity_name!r}", _SCHEMA,
            ))

    perms = vc.bundle.mapping.permissions
    if perms is not None:
        for lvl in perms.levels:
            if provenance.MARKER_TERMINATOR in lvl.name:
                findings.append(_terminator_finding(
                    f"permission level {lvl.name!r}", _LEVELS,
                ))
        for grp in perms.groups:
            if provenance.MARKER_TERMINATOR in grp.name:
                findings.append(_terminator_finding(
                    f"site group {grp.name!r}", _GROUPS,
                ))
    return findings


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
