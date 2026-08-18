# src/dbml_sharepoint/analysis/checks/_provenance.py
"""Names the marker interpolates, and the terminator they may not hold.

The deploy tests for the marker with a substring search, which is sound only
while no marker can sit inside another. That holds only while no interpolated
name contains the terminator, so refusing one here is what makes the grammar
prefix-free. Without it, `from risk.` matches inside `from risk.v2.`.
"""

from collections.abc import Iterator

from dbml_sharepoint.analysis import provenance
from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.group_description import marker_for_group
from dbml_sharepoint.analysis.limits import (
    MAX_GROUP_DESCRIPTION,
    MAX_ROLE_DEFINITION_DESCRIPTION,
)
from dbml_sharepoint.analysis.list_description import (
    DESCRIPTION_LIMIT,
    family_for,
    marker_for,
)
from dbml_sharepoint.analysis.role_definition_description import marker_for_level

#: Refused inside every interpolated name. The terminator occurring once, at
#: the end, and the prefix occurring once, at position zero, are jointly what
#: make one marker never a substring of another. Refusing only the terminator
#: left a name embedding the whole prefix able to carry another family's
#: complete marker as a suffix.
_RESERVED = (provenance.MARKER_TERMINATOR, provenance.MARKER_PREFIX)

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

    findings.extend(_marker_over_ceiling(vc))
    findings.extend(
        _reserved_text_finding(subject, reserved, location)
        for subject, name, location in _interpolated_names(vc)
        for reserved in _RESERVED
        if reserved in name
    )
    return findings


def _marker_over_ceiling(vc: ValidationContext) -> Iterator[Finding]:
    """A marker too long for the field, before the budget clamps to zero.

    `level_description_budget` clamps at 0, so an empty declared description
    passes `len("") > budget` and generation emits a marker over the ceiling,
    which SharePoint refuses part-way through phase 1.3.
    """
    family = family_for(vc.schema)
    for entity_name in vc.bundle.mapping.entities:
        marker = marker_for(family, entity_name)
        if len(marker) > DESCRIPTION_LIMIT:
            yield Finding(
                FindingCode.MARKER_LONGER_THAN_THE_FIELD,
                f"entity {entity_name!r}: its provenance marker is "
                f"{len(marker)} characters, over the "
                f"{DESCRIPTION_LIMIT}-character budget this tool sets for a "
                f"list Description, so the marker would be emitted whole and "
                f"over the limit. Shorten the `Project` name or the entity "
                f"name.",
                location=_ENTITIES,
            )

    perms = vc.bundle.mapping.permissions
    if perms is None:
        return
    for lvl in perms.levels:
        marker = marker_for_level(family, lvl.name)
        if len(marker) > MAX_ROLE_DEFINITION_DESCRIPTION:
            yield Finding(
                FindingCode.MARKER_LONGER_THAN_THE_FIELD,
                f"permission level {lvl.name!r}: its provenance marker is "
                f"{len(marker)} characters, over the "
                f"{MAX_ROLE_DEFINITION_DESCRIPTION}-character ceiling, so "
                f"the deploy would be refused part-way through. Shorten the "
                f"`Project` name or the level name.",
                location=_LEVELS,
            )
    for grp in perms.groups:
        marker = marker_for_group(grp.name, family)
        if len(marker) > MAX_GROUP_DESCRIPTION:
            yield Finding(
                FindingCode.MARKER_LONGER_THAN_THE_FIELD,
                f"site group {grp.name!r}: its provenance marker is "
                f"{len(marker)} characters, over the "
                f"{MAX_GROUP_DESCRIPTION}-character ceiling, so the deploy "
                f"would be refused part-way through. Shorten the `Project` "
                f"name or the group name.",
                location=_GROUPS,
            )


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


def _reserved_text_finding(
    subject: str, reserved: str, location: Location,
) -> Finding:
    return Finding(
        FindingCode.MARKER_FIELD_HAS_RESERVED_TEXT,
        f"{subject} contains {reserved!r}, which the provenance marker "
        f"reserves. A name holding it lets one marker sit inside another, "
        f"so another family could adopt the object and take whatever access "
        f"it declares. Rename it without {reserved!r}.",
        location=location,
    )
