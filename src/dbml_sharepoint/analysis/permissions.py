# src/dbml_sharepoint/analysis/permissions.py
"""SP base permissions bitmask + permission-level / group / role-assignment helpers."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import NamedTuple

from dbml_sharepoint.analysis.resolve import ResolvedMapping
from dbml_sharepoint.model.mapping_types import ListPermissionPolicy, RoleAssignment

# Per Microsoft.SharePoint.SPBasePermissions (64-bit unsigned). All bit
# positions below 32 land in Low; positions 32..62 land in High. Values
# are the full 64-bit form; we split into (high, low) when emitting.
BASE_PERMISSIONS: dict[str, int] = {
    "EmptyMask":                  0x0000000000000000,
    "ViewListItems":              0x0000000000000001,
    "AddListItems":               0x0000000000000002,
    "EditListItems":              0x0000000000000004,
    "DeleteListItems":            0x0000000000000008,
    "ApproveItems":               0x0000000000000010,
    "OpenItems":                  0x0000000000000020,
    "ViewVersions":               0x0000000000000040,
    "DeleteVersions":             0x0000000000000080,
    "CancelCheckout":             0x0000000000000100,
    "ManagePersonalViews":        0x0000000000000200,
    "ManageLists":                0x0000000000000800,
    "ViewFormPages":              0x0000000000001000,
    "AnonymousSearchAccessList":  0x0000000000002000,
    "Open":                       0x0000000000010000,
    "ViewPages":                  0x0000000000020000,
    "AddAndCustomizePages":       0x0000000000040000,
    "ApplyThemeAndBorder":        0x0000000000080000,
    "ApplyStyleSheets":           0x0000000000100000,
    "ViewUsageData":              0x0000000000200000,
    "CreateSSCSite":              0x0000000000400000,
    "ManageSubwebs":              0x0000000000800000,
    "CreateGroups":               0x0000000001000000,
    "ManagePermissions":          0x0000000002000000,
    "BrowseDirectories":          0x0000000004000000,
    "BrowseUserInfo":             0x0000000008000000,
    "AddDelPrivateWebParts":      0x0000000010000000,
    "UpdatePersonalWebParts":     0x0000000020000000,
    "ManageWeb":                  0x0000000040000000,
    "UseClientIntegration":       0x0000001000000000,
    "UseRemoteAPIs":              0x0000002000000000,
    "ManageAlerts":               0x0000004000000000,
    "CreateAlerts":               0x0000008000000000,
    "EditMyUserInfo":             0x0000010000000000,
    "EnumeratePermissions":       0x4000000000000000,
    "FullMask":                   0x7FFFFFFFFFFFFFFF,
}


@dataclass(frozen=True)
class HighLow:
    high: str   # decimal string of upper-32-bit value
    low: str    # decimal string of lower-32-bit value


def base_permissions_to_high_low(perm_names: list[str]) -> HighLow:
    """Combine a list of permission names into the High/Low decimal strings
    SP REST expects on SP.BasePermissions."""
    if not perm_names:
        return HighLow(high="0", low="0")
    combined = 0
    unknown: list[str] = []
    for name in perm_names:
        if name not in BASE_PERMISSIONS:
            unknown.append(name)
        else:
            combined |= BASE_PERMISSIONS[name]
    if unknown:
        raise ValueError(
            f"Unknown base permission name(s): {', '.join(sorted(unknown))}. "
            f"See dbml_sharepoint.analysis.permissions.BASE_PERMISSIONS for the full list.",
        )
    high = (combined >> 32) & 0xFFFFFFFF
    low = combined & 0xFFFFFFFF
    return HighLow(high=str(high), low=str(low))


# Built-in level names that don't need creation; the deployer just resolves
# them by name when binding role assignments. Also the RESERVED set: a
# mapping may not declare a `permission_levels` entry named after one, because
# `_security_principals.js.j2` reconciles a same-name role definition rather
# than skipping it, and would rewrite the site's copy for every principal.
#
# All eleven from Microsoft Learn, "Permission levels in SharePoint"
# (https://learn.microsoft.com/sharepoint/understanding-permission-levels),
# checked 2026-08-13 rather than written from memory. `View Only` and
# `Web-Only Limited Access` were both missing; the second is in the same Learn
# table and is routinely left out of the commonly-quoted list of ten.
#
# ONE CAVEAT this set cannot express: Approve, Manage Hierarchy and Restricted
# Read are publishing-template levels and may not exist on a modern team or
# communication site. They are reserved anyway -- see DERIVED_BUILT_IN_LEVELS
# below for the neighbouring case, and the reserved-name rule in
# checks/_permissions.py for why a build that cannot see the target site fails
# closed rather than guessing which template it will meet.
#
# The names are ENGLISH. Built-in levels are locale-dependent, so on a
# non-English tenant none of these match and a mapping could still redefine a
# built-in. Closing that means resolving by RoleType or Id against a live
# site. `ENTERPRISE_READER_GROUP_OVER_PRIVILEGED` has the same blind spot.
BUILT_IN_LEVELS: frozenset[str] = frozenset({
    "Read", "Contribute", "Edit", "Design", "Full Control",
    "Limited Access", "Web-Only Limited Access", "Approve",
    "Manage Hierarchy", "Restricted Read", "View Only",
})

#: Built-in levels SharePoint DERIVES and a mapping may not assign.
#:
#: Learn is explicit that Limited Access is "automatically assigned by
#: SharePoint" and "cannot be assigned directly": it is what a principal ends
#: up holding on a parent web or list so it can reach one item it was granted
#: below, and it "grants no additional access" on its own. Web-Only Limited
#: Access is the same mechanism scoped to the web object.
#:
#: Writing one into `list_permissions` is therefore not a grant that happens to
#: be narrow -- it is a request the site does not honour as written, and the
#: deploy would bind a role assignment whose meaning is decided by SharePoint's
#: own inheritance rather than by the mapping. A grant nobody can predict from
#: reading the mapping is exactly what this repository refuses.
#:
#: They stay RESERVED in BUILT_IN_LEVELS above -- a custom level may not take
#: the name either -- so the two sets differ on purpose and neither is a
#: superset shortcut for the other.
DERIVED_BUILT_IN_LEVELS: frozenset[str] = frozenset({
    "Limited Access", "Web-Only Limited Access",
})

#: What a `list_permissions` assignment may name without declaring it.
ASSIGNABLE_BUILT_IN_LEVELS: frozenset[str] = BUILT_IN_LEVELS - DERIVED_BUILT_IN_LEVELS

#: Bits the level behind an enterprise-reader grant MUST carry (#199).
#:
#: The name is not the grant. `Read` is a built-in on a stock site, but a level
#: name is site-scoped and writable, so a site can carry one called Read that
#: grants something else entirely, and the deploy binds it, reads it back
#: byte-identical, and reports success. Reserving the name at build time
#: (BUILT_IN_LEVELS) stops THIS tool creating that level; it says nothing about
#: what a site already has. So `_reader_enrolment.js.j2` reads the live
#: BasePermissions before it enrols anybody and judges the bitmap.
#:
#: These three are the floor for reading a list at all: the rows
#: (ViewListItems), the list's own forms and application pages
#: (ViewFormPages), and the site (Open). Missing any one and the reporting
#: account holds a grant that reaches nothing, which is the failure mode a
#: name-based check cannot see.
ENTERPRISE_READER_REQUIRED_PERMISSIONS: tuple[str, ...] = (
    "ViewListItems",
    "ViewFormPages",
    "Open",
)

#: Bits whose absence NARROWS an enterprise-reader grant without emptying it.
#:
#: A reporting client that enumerates lists over REST or CSOM needs
#: UseRemoteAPIs, and resolving the person columns it reads needs
#: BrowseUserInfo. Both are in the built-in Read, so a level missing either is
#: not that level, but a browser-based reader still works without them. Warn,
#: because refusing here would fail a posture that does read the data.
ENTERPRISE_READER_ADVISORY_PERMISSIONS: tuple[str, ...] = (
    "BrowseUserInfo",
    "UseRemoteAPIs",
)

#: Bits that make a binding too strong for the reader group to be holding (#198).
#:
#: The two sets above judge the level this bundle GRANTS. They cannot see a
#: role assignment the group already carries for some other reason: an earlier
#: deploy, a hand edit, another tool. The reader group is resolved by name and
#: enrolled into, so the account inherits every one of those bindings
#: permanently, and no phase removes them -- `_acls.js.j2` reconciles the
#: scopes `SCHEMA.acl_scopes` names and nothing else. So
#: `_reader_enrolment.js.j2` enumerates what the group holds at web scope and
#: judges each binding's live bitmap against this set.
#:
#: THIS IS NOT "anything outside the reader triad", and the difference is the
#: whole design. A level narrower than Read, or Read itself under another name,
#: grants the account nothing it does not already have through the declared
#: grant; refusing those would refuse an untidy site rather than a dangerous
#: one. What cannot be inherited is the authority to change content, structure
#: or access, which is what every name below carries.
#:
#: EVERY ONE OF THEM IS ABSENT FROM THE MEASURED BUILT-IN READ
#: (`reader-bindings-probe.js`, 2026-08-14, High=176 Low=138612833), and
#: `test_no_elevated_bit_is_one_the_built_in_read_carries` pins that. Without
#: it the rule could grow a bit the reference implementation satisfies and
#: refuse every real deploy, which is the failure the AGENTS.md rule about
#: reference implementations names.
#:
#: Deliberately NOT here, and each stays a warning rather than a refusal:
#: ManagePersonalViews, UpdatePersonalWebParts and EditMyUserInfo are scoped to
#: the holder's own view of the site; BrowseDirectories and ViewUsageData are
#: reads; AnonymousSearchAccessList changes what ANONYMOUS callers reach rather
#: than what this account does, so it is a site posture question and not an
#: inherited privilege one.
ENTERPRISE_READER_ELEVATED_PERMISSIONS: tuple[str, ...] = (
    # Content.
    "AddListItems",
    "EditListItems",
    "DeleteListItems",
    "ApproveItems",
    "DeleteVersions",
    "CancelCheckout",
    # Structure.
    "ManageLists",
    "AddAndCustomizePages",
    "ApplyThemeAndBorder",
    "ApplyStyleSheets",
    "AddDelPrivateWebParts",
    "ManageSubwebs",
    "ManageWeb",
    # Access, and the site-wide administration of other people's alerts.
    "CreateGroups",
    "ManagePermissions",
    "EnumeratePermissions",
    "ManageAlerts",
)


def permission_bit_table(perm_names: Iterable[str]) -> list[dict[str, str]]:
    """`{name, high, low}` per permission, for a runtime bitmap test.

    Split the same way `base_permissions_to_high_low` splits a level, because
    SP.BasePermissions is read back as two Int64 halves and the emitted script
    compares against each half separately.
    """
    rows: list[dict[str, str]] = []
    for name in perm_names:
        bits = base_permissions_to_high_low([name])
        rows.append({"name": name, "high": bits.high, "low": bits.low})
    return rows

# Built-in SP groups a group name may reference: an owner_group, or the
# principal on a list_permissions assignment.
BUILTIN_SP_GROUPS = frozenset({
    "Site Owners", "Site Members", "Site Visitors",
    "Owners", "Members", "Visitors",
})

# Built-in associated-group ALIASES (casefolded) mapped to the principal kind
# that resolves them correctly at deploy time. `kind: group` principals are
# resolved via sitegroups/getbyname(name), which fails for these aliases on
# real sites (the actual groups are named '<SiteTitle> Owners' etc.). Note the
# aliases remain valid for groups[*].owner_group, where the template resolves
# them through the AssociatedOwnerGroup/... endpoints.
ASSOCIATED_GROUP_ALIASES = {
    "site owners": "associated_owner_group",
    "site members": "associated_member_group",
    "site visitors": "associated_visitor_group",
}


def _policy_writes(policy: ListPermissionPolicy) -> bool:
    """True when applying `policy` performs at least one ACL WRITE.

    Read off the one body both scopes go through,
    `templates/deploy/_acls.js.j2::reconcileScope`: it POSTs
    `breakroleinheritance` only when the policy breaks inheritance,
    `addroleassignment` only for a declared assignment it does not already
    find, and `removeroleassignment` only in exact mode, where an empty
    declared set is the allowlist that strips the scope. Every other request
    it makes is a read, so those three are the whole of the write set.
    """
    return (
        policy.break_inheritance
        or bool(policy.assignments)
        or policy.reconcile_mode == "exact"
    )


def requires_manage_permissions(
    resolved: ResolvedMapping,
    table_names: Iterable[str],
) -> bool:
    """True when deploying `table_names` performs ANY ACL work, and so needs
    the ManagePermissions site right.

    Three call sites each used to answer this on their own: assessgen's
    preflight requirement, the human-readable manifest, and deploy.js's own
    live preflight abort. The manifest and deploy.js already agreed --
    "declares custom permission levels, custom groups, or a per-list ACL
    policy" -- but assessgen tested `declares_break_inheritance` instead of
    "a policy exists", so a `break_inheritance: false` policy (built-in level,
    built-in associated group, inheritance left alone) made assess.js predict
    no ManagePermissions requirement while deploy.js demanded it and aborted.
    See #166 item 5, reproduced against a from-scratch mapping with zero
    validator findings.

    A per-list policy counts even with `break_inheritance: false`: deploy.js
    still binds the declared role assignments on the (inherited) list, which
    still needs the bit. What it does NOT do is count the policy's existence,
    which was a proxy for the ACL work it performs: a policy that breaks no
    inheritance, declares no assignment and reconciles `configured` makes
    `reconcileScope` read and write nothing, and demanding the right for it
    made both the assessment and deploy.js's live preflight reject an
    operator holding every right the deployment exercises. `_policy_writes`
    asks the effective question for both scopes.

    `table_names` should be the entity names actually in this build
    (`analysis.ordering.site_tables_in_order`'s output), not every entity in
    the mapping -- a policy scoped to a site_role this build does not deploy
    must not demand a right the build never exercises. `groups` is
    `resolved.groups`, for the same reason -- and no `require_resolved()`
    call precedes reading it: an unresolved source is reported by its own
    validator rule, and this function must stay exactly as lenient as
    `resolved.groups` already is rather than fail closed on a mapping-wide
    check a `table_names`-scoped question never asked.
    """
    mapping = resolved.mapping
    perms = mapping.permissions
    if perms is None:
        return False
    # The RESOLVED groups, because a `from_enum` source over an empty enum
    # declares none and this build would then demand a right it never uses.
    if perms.levels or resolved.groups:
        return True
    # A folder policy is keyed by entity, so it is counted through
    # `table_names` like a per-list policy and not as a mapping-wide fact. A
    # policy on a library this build does not deploy must not make the build
    # demand a right it never exercises.
    # The DECLARED folder policy block, not the resolved per-folder pairs: the
    # block is the same for every folder it expands to, and this question must
    # stay answerable when the enum does not resolve (see the reader gate).
    for name in table_names:
        policies = (mapping.permissions_for_entity(name), perms.folder_policies.get(name))
        if any(policy is not None and _policy_writes(policy) for policy in policies):
            return True
    return False


class GroupReach(NamedTuple):
    """Where a group is granted across the lists a caller asked about.

    Three ways, not two: a folder grant binds inside the declared folders and
    nowhere else, so a caller that cannot tell it from a list grant reports
    access to a whole library the deploy never binds.
    """

    #: Granted by the list's own policy, so the whole list is readable.
    granted: list[str]
    #: Granted only inside one or more declared folders of that list.
    folder_only: list[str]
    #: Granted at neither scope.
    excluded: list[str]


def lists_granting_group(
    resolved: ResolvedMapping,
    group_name: str,
    table_names: Iterable[str],
) -> GroupReach:
    """Split `table_names` by where `group_name` is granted, if anywhere.

    Resolved per entity through `Mapping.permissions_for_entity`, which is the
    same resolution `jsgen` uses to bind the live role assignments -- so this
    reports what the deploy will actually do rather than restating the
    mapping's shape.

    Deliberately NOT `checks/_permissions._levels_granted_to_group`, which
    unions every policy block. That union answers "does any block grant this
    group at all", and its own docstring records that it lets an override
    exclude the group from one list ON PURPOSE, because an override exists to
    differ. The manifest needs the opposite question, asked per list.

    The manifest said the enterprise reader "can read every list this bundle"
    creates, unconditionally, and later said it of a list whose only grant
    was on the declared folders inside it. For a valid custom mapping that grants the
    reader on the default policy and omits it from one override, that told an
    operator the reporting account had fleet-wide access while one list was
    silently unreadable. The shipped families are pinned separately by
    `test_the_reader_group_is_granted_read_on_every_policy_block`; nothing
    constrains a custom one.

    Folder policies are read through `require_folder_policies`, which keeps
    the scope `analysis/folders.py::folder_policies` had: an entity with no
    `list_permissions.folders` entry answers `()` whatever its folder source
    resolves to, and one whose policy's folders depend on an enum that did
    not resolve raises `UnknownFolderEnumError`. Subscripting
    `resolved.folder_policies` instead raised for every unresolved entity,
    including the ones with no folder policy, and raised `KeyError`:
    `pipeline` calls this at the reader gate BEFORE `validate_all`, so a
    mapping whose only defect is a misspelled `folders.from_enum` died on a
    bare traceback instead of reporting `folder_enum_unknown` with its
    findings manifest. No `require_resolved()` call precedes this either --
    `table_names` is scoped to one build's site role, and this must judge
    exactly that scope rather than fail the whole mapping over an entity
    this call was never asked about.
    """
    mapping = resolved.mapping

    def holds(assignments: Iterable[RoleAssignment]) -> bool:
        return any(
            a.principal.kind == "group" and a.principal.name == group_name
            for a in assignments
        )

    reach = GroupReach(granted=[], folder_only=[], excluded=[])
    for name in table_names:
        policy = mapping.permissions_for_entity(name)
        at_list = holds(policy.assignments if policy is not None else [])
        # Expanded per folder, because a `{member}` principal is not
        # necessarily a per-member group: `dbml Enterprise {member}` over a
        # folder named Automation resolves to a literal group somebody may be
        # asking about.
        entity = mapping.entities.get(name)
        in_folders = entity is not None and any(
            holds(folder_policy.assignments)
            for _folder, folder_policy in resolved.require_folder_policies(name)
        )
        if at_list:
            reach.granted.append(name)
        elif in_folders:
            reach.folder_only.append(name)
        else:
            reach.excluded.append(name)
    return reach
