# test/test_manage_permissions_agreement.py
"""Pin that assess.js, the manifest, and deploy.js's own preflight all reach
the SAME verdict on whether a build needs ManagePermissions.

#166 item 5: three call sites each answered "does this deploy need
ManagePermissions?" -- `assessgen.assess_targets` (feeding assess.js's
preflight requirement), `jsgen.build_schema_json`'s
`requires_manage_permissions` (feeding both the manifest and deploy.js's own
preflight abort). They used to be THREE independently-hand-rolled
expressions (one of them wrong); now assessgen and jsgen both call the one
shared `analysis.permissions.requires_manage_permissions`, and the manifest
and deploy.js templates just read jsgen's precomputed field instead of
re-deriving it. This test constructs several mappings -- including the one
that used to diverge -- and asserts assess and jsgen agree on all of them, so
a future edit to either call site that reintroduces a second definition is
caught here rather than by a customer's aborted deploy.
"""

from _model import as_library, column
from _model import bundle as make_bundle
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.generators.assessgen import assess_targets
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.model.mapping_types import (
    ListPermissionPolicy,
    MappingBundle,
    PermissionsConfig,
    Principal,
    RoleAssignment,
    SiteGroup,
)


def _agree(bundle: MappingBundle, *, expected: bool) -> None:
    schema = make_schema(make_table("Risk", column("Title", required=True)))
    assess_flag = assess_targets(schema, bundle, "default")["requires_manage_permissions"]
    jsgen_flag = build_schema_json(schema, bundle, "default")["requires_manage_permissions"]
    assert assess_flag is expected, (
        f"assessgen.assess_targets disagreed with the fixture: "
        f"expected {expected}, got {assess_flag}"
    )
    assert jsgen_flag is expected, (
        f"jsgen.build_schema_json disagreed with the fixture: "
        f"expected {expected}, got {jsgen_flag}"
    )
    assert assess_flag == jsgen_flag


def test_bare_mapping_needs_no_manage_permissions() -> None:
    bundle = make_bundle(entities=["Risk"])
    _agree(bundle, expected=False)


def test_custom_level_and_group_declared_needs_manage_permissions() -> None:
    bundle = make_bundle(
        entities=["Risk"],
        permissions=PermissionsConfig(
            levels=[],
            groups=[
                SiteGroup(
                    name="G", description="d", owner_group="Site Owners",
                    allow_members_edit_membership=False,
                    allow_request_to_join_leave=False,
                    auto_accept_request_to_join_leave=False,
                    only_allow_members_view_membership=False,
                ),
            ],
            default_policy=None,
            overrides={},
        ),
    )
    _agree(bundle, expected=True)


def test_break_inheritance_true_needs_manage_permissions() -> None:
    bundle = make_bundle(
        entities=["Risk"],
        permissions=PermissionsConfig(
            levels=[],
            groups=[],
            default_policy=ListPermissionPolicy(
                break_inheritance=True,
                assignments=[
                    RoleAssignment(
                        principal=Principal(kind="associated_owner_group"),
                        level="Full Control",
                    ),
                ],
            ),
            overrides={},
        ),
    )
    _agree(bundle, expected=True)


def test_break_inheritance_false_still_needs_manage_permissions() -> None:
    """The regression case: no custom levels, no custom groups, inheritance
    left alone -- only a per-list policy binding a built-in level to a
    built-in associated group. Before the fix, assessgen said False here
    while jsgen (and therefore the manifest and deploy.js) said True."""
    bundle = make_bundle(
        entities=["Risk"],
        permissions=PermissionsConfig(
            levels=[],
            groups=[],
            default_policy=ListPermissionPolicy(
                break_inheritance=False,
                assignments=[
                    RoleAssignment(
                        principal=Principal(kind="associated_member_group"),
                        level="Contribute",
                    ),
                ],
            ),
            overrides={},
        ),
    )
    _agree(bundle, expected=True)


def _folder_policy_bundle(policy: ListPermissionPolicy) -> MappingBundle:
    """A library with one folder and `policy` as the only permission
    declaration, so the verdict can only come from the folder arm."""
    return as_library(
        make_bundle(
            entities=["Risk"],
            permissions=PermissionsConfig(
                levels=[],
                groups=[],
                default_policy=None,
                overrides={},
                folder_policies={"Risk": policy},
            ),
        ),
        "Risk",
        folders=("Alpha",),
    )


def test_a_folder_policy_that_writes_nothing_needs_no_manage_permissions() -> None:
    """Membership in `folder_policies` was a proxy for "this build writes an
    ACL". `reconcileScope` breaks no inheritance here, has no assignment to
    add and prunes nothing in `configured` mode, so the whole policy is
    reads, and demanding the right made both the assessment and deploy.js's
    preflight reject an operator holding every right the deploy uses."""
    _agree(
        _folder_policy_bundle(ListPermissionPolicy(
            break_inheritance=False, assignments=[], reconcile_mode="configured",
        )),
        expected=False,
    )


def test_a_folder_policy_that_breaks_inheritance_needs_manage_permissions() -> None:
    """breakroleinheritance is a write whether or not anything is granted
    afterwards."""
    _agree(
        _folder_policy_bundle(ListPermissionPolicy(
            break_inheritance=True, assignments=[], reconcile_mode="configured",
        )),
        expected=True,
    )


def test_a_folder_policy_with_an_assignment_needs_manage_permissions() -> None:
    """The grant is bound on the inherited folder, exactly as the per-list
    arm binds one on an inherited list."""
    _agree(
        _folder_policy_bundle(ListPermissionPolicy(
            break_inheritance=False,
            assignments=[
                RoleAssignment(
                    principal=Principal(kind="associated_member_group"),
                    level="Contribute",
                ),
            ],
            reconcile_mode="configured",
        )),
        expected=True,
    )


def test_an_exact_folder_policy_needs_manage_permissions_with_nothing_declared() -> None:
    """Exact mode is an allowlist, so an empty declared set is the policy
    that removes every binding rather than the policy that does nothing."""
    _agree(
        _folder_policy_bundle(ListPermissionPolicy(
            break_inheritance=False, assignments=[], reconcile_mode="exact",
        )),
        expected=True,
    )
