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
    findings: list[Finding] = []
    for role in dict.fromkeys(e.site_role for e in mapping.entities.values()):
        entities = {name: e for name, e in mapping.entities.items() if e.site_role == role}
        by_title = {mapping.list_title(name): name for name in entities}
        declared = []
        for name, entity in entities.items():
            previous = [mapping.prefix + old for old in entity.renamed_from]
            previous += [
                prefix + old for prefix in mapping.previous_prefixes
                for old in (name, *entity.renamed_from)
                if prefix + old != mapping.list_title(name)
            ]
            declared.append((mapping.list_title(name), tuple(previous)))
        def location(title: str, names: dict[str, str] = by_title) -> Location:
            return Location(Section.ENTITIES, entity=names[title], sub="renamed_from")

        findings += _findings("entity", declared, location)
    perms = mapping.permissions
    if perms is not None:
        findings += _findings(
            "group",
            [(g.name, g.previous_names) for g in vc.site_groups],
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
    # Case-insensitively: every one of these is resolved on the site by a
    # case-insensitive read (lists and levels by getbytitle/getbyname, groups
    # by a folded compare over the enumeration), so comparing exactly here
    # passes a declaration the deploy then refuses on the operator's site.
    current = {name.casefold() for name, _previous in declared}
    findings: list[Finding] = []
    claims: dict[str, tuple[str, list[str]]] = {}
    for name, previous_names in declared:
        for previous in previous_names:
            claim = claims.setdefault(previous.casefold(), (previous, []))
            claim[1].append(name)
            if previous.casefold() in current:
                findings.append(Finding(
                    FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY,
                    f"{kind} {name!r}: renamed_from resolves to {previous!r}, "
                    f"which is still a declared {kind}. A redeploy would find "
                    f"both and could not tell a rename from a collision. Remove "
                    f"the declaration that no longer exists, or drop the name "
                    f"from renamed_from.",
                    location=where(name),
                ))
    for previous, claimants in claims.values():
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
