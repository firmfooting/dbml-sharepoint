"""Identities: what a mapping declares, and what each group enrols."""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.permissions import ASSOCIATED_GROUP_ALIASES, BUILTIN_SP_GROUPS
from dbml_sharepoint.model.identities import (
    BUILTIN_IDENTITIES,
    IDENTITY_KINDS,
    NAME_PATTERN,
    is_run_lifetime,
)
from dbml_sharepoint.model.mapping_types import PRINCIPAL_KINDS

_IDENTITIES = Location(Section.IDENTITIES)
_GROUPS = Location(Section.GROUPS)
# Microsoft Learn, "Review available default groups": "SharePoint groups cannot be nested."
_NESTING = (
    "SharePoint groups cannot be nested (Microsoft Learn: "
    "https://learn.microsoft.com/sharepoint/sites/"
    "determine-permission-levels-and-groups-in-sharepoint-server"
    "#review-available-default-groups; "
    "that page is written for SharePoint Server, so this refusal fails closed on its word). "
    "Grant the permission level to associated_owner_group, associated_member_group or "
    "associated_visitor_group in list_permissions instead."
)
_REPLACEMENT = {
    "enroll_enterprise_reader": "enroll: [enterprise_reader] with membership: exclusive",
    "enroll_operator_during_deploy": "enroll_during_run: [operator]",
}


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    declared = vc.bundle.mapping.identities
    for name, identity in declared.items():
        if name in BUILTIN_IDENTITIES:
            findings.append(Finding(
                FindingCode.IDENTITY_REDECLARES_BUILTIN,
                f"identities: {name!r} is built in; enrol it without declaring it.",
                location=_IDENTITIES,
            ))
            continue
        if not NAME_PATTERN.fullmatch(name):
            findings.append(Finding(
                FindingCode.IDENTITY_NAME_INVALID,
                f"identities: {name!r} must match [a-z][a-z0-9_]{{0,63}}, so its env "
                f"key DBMLSP_IDENTITY_<NAME> spells it exactly.",
                location=_IDENTITIES,
            ))
        unknown = [k for k in identity.kinds if k not in IDENTITY_KINDS]
        if unknown or not identity.kinds:
            findings.append(Finding(
                FindingCode.IDENTITY_KIND_UNKNOWN,
                f"identities.{name}.kinds must be a non-empty list of "
                f"{', '.join(sorted(IDENTITY_KINDS))}; got {list(identity.kinds)!r}.",
                location=_IDENTITIES,
            ))

    groups = vc.site_groups
    sharepoint_names = (
        {g.name for g in groups} | set(BUILTIN_SP_GROUPS)
        | set(ASSOCIATED_GROUP_ALIASES) | set(PRINCIPAL_KINDS)
    )
    enrolled: set[str] = set()
    for grp in groups:
        for key, names in (("enroll", grp.enroll), ("enroll_during_run", grp.enroll_during_run)):
            for name in names:
                enrolled.add(name)
                if name in sharepoint_names or name.casefold() in ASSOCIATED_GROUP_ALIASES:
                    findings.append(Finding(
                        FindingCode.SHAREPOINT_GROUP_ENROLLED,
                        f"groups: {grp.name!r} {key} names {name!r}, a SharePoint group. "
                        f"{_NESTING}",
                        location=_GROUPS,
                    ))
                elif name not in BUILTIN_IDENTITIES and name not in declared:
                    findings.append(Finding(
                        FindingCode.IDENTITY_UNKNOWN,
                        f"groups: {grp.name!r} {key} names {name!r}, which is neither "
                        f"built in ({', '.join(sorted(BUILTIN_IDENTITIES))}) nor declared "
                        f"under identities:.",
                        location=_GROUPS,
                    ))
                elif (key == "enroll") == is_run_lifetime(name):
                    findings.append(Finding(
                        FindingCode.OPERATOR_ENROLLED_PERSISTENTLY,
                        f"groups: {grp.name!r} {key} names {name!r}. The operator belongs "
                        f"in enroll_during_run, which holds only run-lifetime identities, "
                        f"and every other identity belongs in enroll.",
                        location=_GROUPS,
                    ))
        if grp.membership == "exclusive":
            for name in grp.enroll:
                kinds = (
                    BUILTIN_IDENTITIES[name].kinds if name in BUILTIN_IDENTITIES
                    else declared[name].kinds if name in declared else ("user",)
                )
                if any(kind != "user" for kind in kinds):
                    findings.append(Finding(
                        FindingCode.EXCLUSIVE_GROUP_ENROLS_A_GROUP_KIND,
                        f"groups: {grp.name!r} is exclusive and enrols {name!r}, whose "
                        f"kinds include a group. Neither the deploy nor assess can see "
                        f"inside an Entra group, so 'nobody else' cannot be checked.",
                        location=_GROUPS,
                    ))
        for legacy in grp.legacy_flags:
            findings.append(Finding(
                FindingCode.DEPRECATED_ENROLMENT_FLAG,
                f"groups: {grp.name!r} uses {legacy.flag}: true; write "
                f"{_REPLACEMENT[legacy.flag]} instead.",
                location=_GROUPS,
            ))
            if legacy.also_declared:
                findings.append(Finding(
                    FindingCode.ENROLMENT_DECLARED_TWICE,
                    f"groups: {grp.name!r} enrols {legacy.identity!r} through both "
                    f"{legacy.flag} and the new key. Keep the new key and drop the flag.",
                    location=_GROUPS,
                ))

    for name in sorted(set(declared) - enrolled - set(BUILTIN_IDENTITIES)):
        findings.append(Finding(
            FindingCode.IDENTITY_DECLARED_NOT_ENROLLED,
            f"identities: {name!r} is declared but no group enrols it.",
            location=_IDENTITIES,
        ))
    return findings
