# src/dbml_sharepoint/analysis/checks/_permissions.py
"""Permission levels, groups, and per-list policies."""

from dbml_sharepoint.analysis.checks._context import ValidationContext
from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
from dbml_sharepoint.analysis.permissions import (
    ASSIGNABLE_BUILT_IN_LEVELS,
    BASE_PERMISSIONS,
    BUILT_IN_LEVELS,
    DERIVED_BUILT_IN_LEVELS,
    GROUP_DESCRIPTION_MAX,
)
from dbml_sharepoint.analysis.validator import (
    _ASSOCIATED_GROUP_ALIASES,
    _BUILTIN_SP_GROUPS,
    Finding,
)
from dbml_sharepoint.model.mapping_loader import ListPermissionPolicy, PermissionsConfig

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
        # site role — a typo would silently scope the default to nothing. The
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

        # permission_levels[*].name must be unique — CASE-INSENSITIVELY,
        # because that is how SharePoint resolves and de-duplicates them.
        # Two declarations differing only in case are one object on the
        # site: the second create fails on a name collision, mid-deploy,
        # after the first has already been made.
        seen_level_names: dict[str, str] = {}
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

        # groups[*].name must be unique — case-insensitively, for the same
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

            # The server refuses a longer one with HTTP 500, in phase 1.2 --
            # after lists may already exist. Caught here so an over-long
            # description is a build error rather than a half-provisioned
            # site. See permissions.GROUP_DESCRIPTION_MAX for the live
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

            if len(grp.description) > GROUP_DESCRIPTION_MAX:
                findings.append(Finding(
                    FindingCode.GROUP_DESCRIPTION_TOO_LONG,
                    f"groups[{grp.name!r}]: description is "
                    f"{len(grp.description)} characters; SharePoint refuses "
                    f"anything over {GROUP_DESCRIPTION_MAX} and does so "
                    f"part-way through the deploy. Shorten it.",
                    location=_GROUPS,
                ))

        # groups[*].owner_group must be a built-in SP group or a declared custom group.
        for grp in perms.groups:
            owner_ok = (
                grp.owner_group in _BUILTIN_SP_GROUPS
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
        all_group_names = custom_group_names | _BUILTIN_SP_GROUPS

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
                suggested_kind = _ASSOCIATED_GROUP_ALIASES.get(
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
                    f"enroll_operator_during_deploy. Phase 1.3 puts the "
                    f"operator in the group, so Phase 1.4 finds a principal "
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
                    f"applies that setting before Phase 1.4 enrols the "
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
            over_privileged = sorted(
                {(level, origin) for level, origin in grants if level != "Read"},
                key=lambda pair: (pair[0], pair[1].path),
            )
            for level, origin in over_privileged:
                findings.append(Finding(
                    FindingCode.ENTERPRISE_READER_GROUP_OVER_PRIVILEGED,
                    f"list_permissions: {grp.name!r} is an enterprise-reader "
                    f"group granted {level!r}; only the built-in 'Read' is "
                    f"allowed.",
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
