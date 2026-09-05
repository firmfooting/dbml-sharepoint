# src/dbml_sharepoint/analysis/checks/_permissions.py
"""Permission levels, groups, and per-list policies."""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.group_description import (
    AUTOMATION_GROUP_NAME,
    description_budget,
    marker_for_group,
)
from dbml_sharepoint.analysis.limits import (
    MAX_GROUP_DESCRIPTION,
    MAX_ROLE_DEFINITION_DESCRIPTION,
)
from dbml_sharepoint.analysis.list_description import family_for
from dbml_sharepoint.analysis.permissions import (
    ASSIGNABLE_BUILT_IN_LEVELS,
    ASSOCIATED_GROUP_ALIASES,
    BASE_PERMISSIONS,
    BUILT_IN_LEVELS,
    BUILTIN_SP_GROUPS,
    DERIVED_BUILT_IN_LEVELS,
)
from dbml_sharepoint.analysis.role_definition_description import (
    level_description_budget,
    marker_for_level,
)
from dbml_sharepoint.model.mapping_types import ListPermissionPolicy, PermissionsConfig

# These messages spell the level or group name with `!r`, so the quotes are
# inside the bracket -- `permission_levels['Reader']`. A Location holding
# `Reader` would render `permission_levels[Reader]` and stop being the
# message's prefix, and a Location holding `'Reader'` would be storing a
# repr in a data field. The section-level Location is the honest one until
# the messages themselves drop the `!r`.
_LEVELS = Location(Section.PERMISSION_LEVELS)
_GROUPS = Location(Section.GROUPS)
#: `list_permissions` is not one of the mapping's per-entity sections; its
#: paths are `list_permissions.default...` and `list_permissions.overrides`.
_DEFAULT_POLICY = Location(Section.LIST_PERMISSIONS, sub="default")
_OVERRIDES = Location(Section.LIST_PERMISSIONS, sub="overrides")

#: Matched case-insensitively, the same way the duplicate-name rule below
#: treats level names -- one stance, not two. A case variant is refused for
#: the same reason a duplicate is: the site resolves the name to one object.
_RESERVED_LEVEL_KEYS: frozenset[str] = frozenset(
    name.casefold() for name in BUILT_IN_LEVELS
)

#: Case-folded for the same reason as the reserved names: the site resolves an
#: assignment's level by name, so `limited access` reaches the same object.
_DERIVED_LEVEL_KEYS: frozenset[str] = frozenset(
    name.casefold() for name in DERIVED_BUILT_IN_LEVELS
)


def _levels_granted_to_group(
    perms: PermissionsConfig, name: str,
) -> list[tuple[str, Location]]:
    """Every (level, origin) grant to `name` across all policy blocks.

    Both the default policy and every override, because an override carries
    its OWN complete assignment list rather than adding to the default. The
    union is what lets `ENTERPRISE_READER_GROUP_OVER_PRIVILEGED` see a
    reader granted Contribute on an override alone, which a default-only
    read would miss entirely; and it lets
    `ENTERPRISE_READER_GROUP_NOT_GRANTED` mean what it says -- the group
    that NO block grants anything, so enrolling an account into it would
    grant nothing anywhere.

    What the union deliberately does NOT catch is the mirror case: Read on
    the default and silence on some override. `check` tests `if not grants`
    over the union, so one grant anywhere satisfies it. That is allowed on
    purpose -- an override exists to differ, and may exclude the reader
    from one list intentionally, so a rule firing on it would be stronger
    than the mapping format's own meaning. For the SHIPPED families, where
    such an omission would be a hole in fleet-wide reporting rather than a
    choice, it is pinned separately by
    `test_the_reader_group_is_granted_read_on_every_policy_block` in
    test/test_template_standard.py.

    The origin travels with each grant so an over-privileged finding can
    point at the block that actually granted it (an override-sourced grant
    must not be reported against the default).
    """
    policies: list[tuple[ListPermissionPolicy | None, Location]] = [
        (perms.default_policy, _DEFAULT_POLICY),
        *((policy, _OVERRIDES) for policy in perms.overrides.values()),
    ]
    return [
        (a.level, origin)
        for policy, origin in policies
        if policy is not None
        for a in policy.assignments
        if a.principal.kind == "group" and a.principal.name == name
    ]


def check(vc: ValidationContext) -> list[Finding]:
    bundle = vc.bundle
    table_names = vc.table_names
    findings: list[Finding] = []
    # === Permissions cross-checks (R4) ===
    if bundle.mapping.permissions is not None:
        perms = bundle.mapping.permissions

        # list_permissions.default.site_role, when declared, must be a known
        # site role. A typo would silently scope the default to nothing. The
        # valid roles are data-driven: those declared on the mapping's
        # entities, plus "default" (no hardcoded any labels you choose.
        scope = perms.default_policy_site_role
        known_roles = {e.site_role for e in bundle.mapping.entities.values()} | {"default"}
        if scope is not None and scope not in known_roles:
            findings.append(Finding(
                FindingCode.UNKNOWN_SITE_ROLE,
                f"list_permissions.default.site_role: unknown site role "
                f"{scope!r} (mapping declares: {', '.join(sorted(known_roles))}).",
                location=Location(
                    Section.LIST_PERMISSIONS, sub="default.site_role",
                ),
            ))

        # permission_levels[*].name must be unique, CASE-INSENSITIVELY,
        # because that is how SharePoint resolves and de-duplicates them.
        # Two declarations differing only in case are one object on the
        # site: the second create fails on a name collision, mid-deploy,
        # after the first has already been made.
        seen_level_names: dict[str, str] = {}
        family = family_for(vc.schema)
        for lvl in perms.levels:
            key = lvl.name.casefold()
            # ALL eleven built-ins are reserved, including the three that are
            # publishing-template levels and may be absent from a modern team
            # or communication site. Raised in review on #208: on such a site
            # the existence probe would find no `Approve`, create the custom
            # level safely, and this rule refused a build that would have
            # worked.
            #
            # Kept, because the build cannot see the target site. The same
            # mapping is pasted into whatever site the operator has, so the
            # choice is between refusing a name that MIGHT have been free and
            # allowing one that MIGHT rewrite a live level for every principal
            # holding it. `AGENTS.md` settles that: an uncertainty fails
            # closed with a named error, and this one costs a rename.
            #
            # The corollary quoted against it -- a rule must not be stronger
            # than the reference implementation satisfies -- is about the
            # shipped families, and none of them declares a level named after
            # any built-in. The conformance sweep would fail if one did.
            if key in _RESERVED_LEVEL_KEYS:
                findings.append(Finding(
                    FindingCode.PERMISSION_LEVEL_REDEFINES_A_BUILTIN,
                    f"permission_levels: {lvl.name!r} is a built-in SharePoint "
                    f"permission level. Declaring it does not create a second "
                    f"level -- the deploy reconciles the one already on the "
                    f"site, rewriting its description and base permissions "
                    f"for every principal that holds it. Give the custom "
                    f"level a name of its own.",
                    location=_LEVELS,
                ))
            if key in seen_level_names:
                findings.append(Finding(
                    FindingCode.DUPLICATE_PERMISSION_LEVEL_NAME,
                    f"permission_levels: duplicate name {lvl.name!r}"
                    + (f" (differs from {seen_level_names[key]!r} only in case; "
                       f"SharePoint treats them as one)"
                       if seen_level_names[key] != lvl.name else ""),
                    location=_LEVELS,
                ))
            seen_level_names.setdefault(key, lvl.name)

        # permission_levels[*].base_permissions must be known bits.
        for lvl in perms.levels:
            for bit in lvl.base_permissions:
                if bit not in BASE_PERMISSIONS:
                    findings.append(Finding(
                        FindingCode.UNKNOWN_BASE_PERMISSION,
                        f"permission_levels[{lvl.name!r}]: unknown base permission {bit!r}",
                        location=_LEVELS,
                    ))

        # permission_levels[*].description must fit SP.RoleDefinition.Description.
        # The server refuses a longer one with HTTP 500, in phase 1.3 -- part-way
        # through writing permission levels and before any list exists. See
        # limits.MAX_ROLE_DEFINITION_DESCRIPTION for the live measurement behind
        # the number. The deploy appends a provenance marker to every level
        # description it writes, so `elif` chains onto the budget check below:
        # a description over the raw ceiling reports one code, the same as the
        # group check.
        for lvl in perms.levels:
            # Per level, because the marker now carries the level's own name
            # and so its length varies with it.
            level_budget = level_description_budget(family, lvl.name)
            if len(lvl.description) > MAX_ROLE_DEFINITION_DESCRIPTION:
                findings.append(Finding(
                    FindingCode.PERMISSION_LEVEL_DESCRIPTION_TOO_LONG,
                    f"permission_levels[{lvl.name!r}]: description is "
                    f"{len(lvl.description)} characters; SharePoint refuses "
                    f"anything over {MAX_ROLE_DEFINITION_DESCRIPTION} and does "
                    f"so part-way through the deploy. Shorten it.",
                    location=_LEVELS,
                ))
            elif len(lvl.description) > level_budget:
                findings.append(Finding(
                    FindingCode.PERMISSION_LEVEL_DESCRIPTION_TOO_LONG_FOR_MARKER,
                    f"permission_levels[{lvl.name!r}]: description is "
                    f"{len(lvl.description)} characters, and the budget is "
                    f"{level_budget} once the provenance marker "
                    f"{marker_for_level(family, lvl.name)!r} and its separating space "
                    f"are appended. Shorten it.",
                    location=_LEVELS,
                ))

        # groups[*].name must be unique, case-insensitively, for the same
        # reason as the levels above.
        seen_group_names: dict[str, str] = {}
        custom_group_names = {g.name for g in perms.groups}
        for grp in perms.groups:
            key = grp.name.casefold()
            if key in seen_group_names:
                findings.append(Finding(
                    FindingCode.DUPLICATE_GROUP_NAME,
                    f"groups: duplicate name {grp.name!r}"
                    + (f" (differs from {seen_group_names[key]!r} only in case; "
                       f"SharePoint treats them as one)"
                       if seen_group_names[key] != grp.name else ""),
                    location=_GROUPS,
                ))
            seen_group_names.setdefault(key, grp.name)

            # The server refuses a longer one with HTTP 500, in phase 1.3 --
            # after lists may already exist. Caught here so an over-long
            # description is a build error rather than a half-provisioned
            # site. See limits.MAX_GROUP_DESCRIPTION for the live
            # measurement behind the number.
            # MEASURED 2026-08-13/14, two runs: SharePoint accepts this pair
            # with HTTP 200 and then stores AutoAccept as FALSE, because a
            # group cannot auto-accept join requests it does not accept. The
            # deploy would report the group reconciled while the site
            # disagreed with the mapping -- silently, since nothing reads the
            # flags back. Refused here so the mapping cannot claim it.
            if (grp.auto_accept_request_to_join_leave
                    and not grp.allow_request_to_join_leave):
                findings.append(Finding(
                    FindingCode.GROUP_AUTO_ACCEPT_WITHOUT_REQUESTS,
                    f"groups[{grp.name!r}]: declares "
                    f"auto_accept_request_to_join_leave without "
                    f"allow_request_to_join_leave. SharePoint accepts that "
                    f"pair and then silently stores auto-accept as false, so "
                    f"the deployed group would not match this mapping. Set "
                    f"allow_request_to_join_leave as well, or drop the "
                    f"auto-accept.",
                    location=_GROUPS,
                ))

            # The COMPOSED string is what reaches SharePoint, so the budget
            # rather than the raw ceiling is what a description must fit.
            # `elif`, so a description over the raw ceiling reports one code:
            # the second would add nothing an author can act on separately.
            budget = description_budget(grp.name, family)
            if len(grp.description) > MAX_GROUP_DESCRIPTION:
                findings.append(Finding(
                    FindingCode.GROUP_DESCRIPTION_TOO_LONG,
                    f"groups[{grp.name!r}]: description is "
                    f"{len(grp.description)} characters; SharePoint refuses "
                    f"anything over {MAX_GROUP_DESCRIPTION} and does so "
                    f"part-way through the deploy. Shorten it.",
                    location=_GROUPS,
                ))
            elif len(grp.description) > budget:
                findings.append(Finding(
                    FindingCode.GROUP_DESCRIPTION_TOO_LONG_FOR_MARKER,
                    f"groups[{grp.name!r}]: description is "
                    f"{len(grp.description)} characters, and the budget is "
                    f"{budget} once the provenance marker "
                    f"{marker_for_group(grp.name, family)!r} and its "
                    f"separating space are appended. Shorten it.",
                    location=_GROUPS,
                ))

        # groups[*].owner_group must be a built-in SP group or a declared custom group.
        for grp in perms.groups:
            owner_ok = (
                grp.owner_group in BUILTIN_SP_GROUPS
                or grp.owner_group in custom_group_names
            )
            if not owner_ok:
                findings.append(Finding(
                    FindingCode.UNKNOWN_OWNER_GROUP,
                    f"groups[{grp.name!r}]: owner_group {grp.owner_group!r} is not a "
                    f"built-in SP group or a declared custom group",
                    location=_GROUPS,
                ))

        # Collect all valid level names (built-in + declared custom).
        all_level_names = ASSIGNABLE_BUILT_IN_LEVELS | set(seen_level_names.values())
        # Collect all valid group names (declared custom + built-in SP groups).
        all_group_names = custom_group_names | BUILTIN_SP_GROUPS

        def _check_policy_assignments(
            policy: ListPermissionPolicy, ctx: str, at: Location,
        ) -> None:
            """`ctx` renders the message prefix and `at` locates the finding.

            They are not the same string for an override: the message spells
            the entity with `!r` inside the bracket, which a Location cannot
            reproduce without storing a repr. `at` is the enclosing section
            instead, which is still a prefix of every message here.
            """
            for i, assignment in enumerate(policy.assignments):
                lvl = assignment.level
                # Ordered so a derived level gets its own message. It IS a
                # built-in, so "not a built-in or declared custom level"
                # would be false and would send the author looking for a
                # typo instead of at the grant they cannot make.
                if lvl.casefold() in _DERIVED_LEVEL_KEYS:
                    findings.append(Finding(
                        FindingCode.PERMISSION_LEVEL_NOT_DIRECTLY_ASSIGNABLE,
                        f"{ctx}.assignments[{i}]: level {lvl!r} is derived by "
                        f"SharePoint and cannot be assigned directly. It is "
                        f"what a principal is given on a parent so it can "
                        f"reach one item granted below, and it grants no "
                        f"access of its own. Grant the level you mean, "
                        f"usually 'Read'.",
                        location=at,
                    ))
                elif lvl not in all_level_names:
                    findings.append(Finding(
                        FindingCode.UNKNOWN_PERMISSION_LEVEL,
                        f"{ctx}.assignments[{i}]: level {lvl!r} is not a built-in "
                        f"or declared custom permission level",
                        location=at,
                    ))
                principal = assignment.principal
                if principal.kind != "group":
                    continue
                suggested_kind = ASSOCIATED_GROUP_ALIASES.get(
                    (principal.name or "").casefold(),
                )
                if suggested_kind is not None:
                    # Phase 4.2 resolves kind=group via sitegroups/getbyname(name).
                    # The built-in aliases never exist under these literal names
                    # on real sites (the associated groups are named
                    # '<SiteTitle> Owners' etc.), so the assignment would fail
                    # at deploy time.
                    findings.append(Finding(
                        FindingCode.UNRESOLVABLE_ASSOCIATED_GROUP_ALIAS,
                        f"{ctx}.assignments[{i}]: principal group "
                        f"{principal.name!r} is a built-in associated-group "
                        f"alias that cannot be resolved by name at deploy time "
                        f"(real sites name it '<SiteTitle> ...'). Use principal "
                        f"kind {suggested_kind!r} instead.",
                        location=at,
                    ))
                elif principal.name not in all_group_names:
                    findings.append(Finding(
                        FindingCode.UNKNOWN_PRINCIPAL_GROUP,
                        f"{ctx}.assignments[{i}]: principal group {principal.name!r} "
                        f"is not a built-in or declared custom group",
                        location=at,
                    ))

        if perms.default_policy is not None:
            _check_policy_assignments(
                perms.default_policy, "list_permissions.default", _DEFAULT_POLICY,
            )

        # === Enterprise reader tier ===
        # The flagged group is the target of `build --enterprise-reader`.
        # Every rule here refuses a mapping that would deploy green and
        # leave the reporting account seeing nothing.
        reader_groups = [g for g in perms.groups if g.enroll_enterprise_reader]

        if len(reader_groups) > 1:
            findings.append(Finding(
                FindingCode.MULTIPLE_ENTERPRISE_READER_GROUPS,
                f"groups: {len(reader_groups)} groups declare "
                f"enroll_enterprise_reader "
                f"({', '.join(repr(g.name) for g in reader_groups)}); "
                f"--enterprise-reader needs exactly one target.",
                location=_GROUPS,
            ))

        for grp in reader_groups:
            if grp.enroll_operator_during_deploy:
                findings.append(Finding(
                    FindingCode.ENTERPRISE_READER_GROUP_ENROLS_THE_OPERATOR,
                    f"groups: {grp.name!r} declares both "
                    f"enroll_enterprise_reader and "
                    f"enroll_operator_during_deploy. Phase 1.4 puts the "
                    f"operator in the group, so Phase 1.5 finds a principal "
                    f"other than the named reader and aborts the run -- "
                    f"every run, on a correct address.",
                    location=_GROUPS,
                ))

            if grp.allow_members_edit_membership:
                findings.append(Finding(
                    FindingCode.ENTERPRISE_READER_GROUP_MEMBERS_MAY_EDIT_MEMBERSHIP,
                    f"groups: {grp.name!r} declares both "
                    f"enroll_enterprise_reader and "
                    f"allow_members_edit_membership. The security phase "
                    f"applies that setting before Phase 1.5 enrols the "
                    f"reader, so the enrolled account can then add "
                    f"principals to its own group and pass on the group's "
                    f"Read. The one-account guard would hold for the length "
                    f"of one run and be unenforceable afterwards.",
                    location=_GROUPS,
                ))

            if grp.require_empty_at_deploy:
                findings.append(Finding(
                    FindingCode.ENTERPRISE_READER_GROUP_REQUIRES_EMPTY,
                    f"groups: {grp.name!r} declares both "
                    f"enroll_enterprise_reader and require_empty_at_deploy. "
                    f"The reader is enrolled after the empty-group gate and "
                    f"stays, so the next deploy aborts on that gate.",
                    location=_GROUPS,
                ))

            grants = _levels_granted_to_group(perms, grp.name)
            if not grants:
                findings.append(Finding(
                    FindingCode.ENTERPRISE_READER_GROUP_NOT_GRANTED,
                    f"groups: {grp.name!r} declares "
                    f"enroll_enterprise_reader but holds no role assignment; "
                    f"enrolling an account into it would grant nothing.",
                    location=_GROUPS,
                ))
            # THE ONE EXCEPTION, and it is a weakening of this guard, so it
            # is argued here rather than assumed.
            #
            # The rule's premise is that 'Read' lets the reporting account
            # see everything it needs, so anything above it is unearned. A
            # mapping declaring `item_security.read: own` breaks that
            # premise outright: on such a list the built-in Read reaches
            # only the rows the reporting account itself created, which for
            # an account that writes nothing is no rows at all. Holding the
            # rule there would refuse every posture that works and permit
            # only the one that does not.
            #
            # So the exception is keyed on read trimming and nothing else.
            # No shipped family except `deployment-log` declares it, so the
            # guard is unchanged for all of them, and a custom mapping only
            # reaches the exception by declaring the trimming that creates
            # the problem it answers.
            #
            # It is NOT a claim that the elevated level clears the trim.
            # Which levels bypass created-by trimming has not been measured
            # here; `deployment-log`'s `30-deploy/deploy.md` carries the
            # probe. What this rule can say is that Read demonstrably does
            # not solve it, and that is all it stops saying.
            trims_reads = bundle.mapping.declares_item_read_trimming()
            over_privileged = sorted(
                {(level, origin) for level, origin in grants if level != "Read"},
                key=lambda pair: (pair[0], pair[1].path),
            )
            if not trims_reads:
                for level, origin in over_privileged:
                    findings.append(Finding(
                        FindingCode.ENTERPRISE_READER_GROUP_OVER_PRIVILEGED,
                        f"list_permissions: {grp.name!r} is an "
                        f"enterprise-reader group granted {level!r}; only "
                        f"the built-in 'Read' is allowed.",
                        location=origin,
                    ))
            # The compensating half. Dropping the rule above would otherwise
            # make a trimming family's reader posture invisible either way:
            # elevated is allowed and Read is silently useless.
            for level, origin in sorted(
                {(level, origin) for level, origin in grants if level == "Read"}
                if trims_reads else set(),
                key=lambda pair: (pair[0], pair[1].path),
            ):
                findings.append(Finding(
                    FindingCode.ENTERPRISE_READER_ON_TRIMMED_LIST,
                    f"list_permissions: {grp.name!r} is an enterprise-reader "
                    f"group granted {level!r} where item_security trims "
                    f"reads to the caller's own items. A reporting account "
                    f"that writes nothing then reads nothing.",
                    location=origin,
                ))

        # === Automation tier ===
        # Keyed off the NAME, not a flag. The reader tier has a flag because
        # `build --enterprise-reader` must know which group to enrol an
        # account into; nothing about this group happens at build time, so a
        # flag would select nothing.
        #
        # A DENYLIST of one level rather than the reader tier's allowlist:
        # what an automation legitimately needs is the family's call
        # (Contribute, Edit, a custom level), and only Full Control is knowably
        # wrong here. It is what `dbml List Administrators` already holds, so
        # granting it reproduces the breadth this group exists to avoid.
        #
        # Same locale blind spot as `ENTERPRISE_READER_GROUP_OVER_PRIVILEGED`:
        # the built-in names are English, so on a non-English tenant the
        # equivalent level is spelled otherwise and is not matched here.
        full_control_grants = sorted(
            {
                origin
                for level, origin in _levels_granted_to_group(
                    perms, AUTOMATION_GROUP_NAME,
                )
                if level == "Full Control"
            },
            key=lambda origin: origin.path,
        )
        for origin in full_control_grants:
            findings.append(Finding(
                FindingCode.AUTOMATION_GROUP_GRANTED_FULL_CONTROL,
                f"list_permissions: {AUTOMATION_GROUP_NAME!r} is granted "
                f"'Full Control'. The group exists so an automation identity "
                f"can hold a narrow declared write on the lists it stamps, and "
                f"Full Control is what 'dbml List Administrators' already "
                f"carries on every list, so this grant leaves the automation "
                f"the breadth the group was declared to avoid. Grant the "
                f"narrowest level that lets the flow write, or name a group of "
                f"your own.",
                location=origin,
            ))

        # list_permissions.overrides keys must be unprefixed DBML table names.
        for entity_name, override_policy in perms.overrides.items():
            if entity_name not in table_names:
                # Distinct from UNKNOWN_ENTITY, which is about a name the
                # MAPPING does not declare. This one is about a name the DBML
                # does not declare, and the fix is usually the prefix.
                findings.append(Finding(
                    FindingCode.UNKNOWN_TABLE,
                    f"list_permissions.overrides: key {entity_name!r} is not a "
                    "known DBML table name (use unprefixed name, "
                    "e.g. 'Ticket' not 'APP_Ticket')",
                    location=_OVERRIDES,
                ))
            ctx_key = f"list_permissions.overrides[{entity_name!r}]"
            _check_policy_assignments(override_policy, ctx_key, _OVERRIDES)

    return findings
