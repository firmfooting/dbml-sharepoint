# test/test_resolve.py
"""`resolve()` builds every enum-sourced answer once, and never raises.

The strict resolvers in `analysis/folders.py` and `analysis/groups.py` still
exist and still raise; `resolve()` is the lenient path the checks always
needed, plus `require_resolved()` for the generator side that must not
silently omit a declared group or folder.
"""

import pytest
from _model import enum as make_enum
from _model import mapping as make_mapping
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.folders import UnknownFolderEnumError
from dbml_sharepoint.analysis.groups import UnknownGroupEnumError
from dbml_sharepoint.analysis.resolve import UnresolvedEnum, resolve
from dbml_sharepoint.model.mapping_types import (
    EntityMapping,
    FoldersFromEnum,
    GroupsFromEnum,
    ListPermissionPolicy,
    PermissionsConfig,
    Principal,
    RoleAssignment,
    SiteGroup,
)


def _group(name: str, owner_group: str = "Site Owners") -> SiteGroup:
    """A SiteGroup with the membership controls every declaration must set."""
    return SiteGroup(
        name=name,
        description="Declared by a test.",
        owner_group=owner_group,
        allow_members_edit_membership=False,
        allow_request_to_join_leave=False,
        auto_accept_request_to_join_leave=False,
        only_allow_members_view_membership=False,
    )


def test_resolve_expands_groups_folders_and_policies_once() -> None:
    """The happy path: every enum source resolved, nothing unresolved."""
    schema = make_schema(
        make_table("Risk", "Title"),
        enums=[make_enum("division", "North", "South")],
    )
    perms = PermissionsConfig(
        levels=[], groups=[], default_policy=None, overrides={},
        group_sources=(GroupsFromEnum(enum="division", template=_group("{member} Owners")),),
        folder_policies={"Risk": ListPermissionPolicy(
            break_inheritance=True,
            assignments=[RoleAssignment(
                principal=Principal(kind="group", name="{member} Owners"),
                level="Read",
            )],
        )},
    )
    mapping = make_mapping(
        entities={"Risk": EntityMapping(
            name="Risk", kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=FoldersFromEnum(enum="division"),
        )},
        permissions=perms,
    )

    resolved = resolve(schema, mapping)

    assert resolved.enum_members == {"division": ("North", "South")}
    assert resolved.folders == {"Risk": ("North", "South")}
    assert [name for name, _policy in resolved.folder_policies["Risk"]] == ["North", "South"]
    assert [g.name for g in resolved.groups] == ["North Owners", "South Owners"]
    assert resolved.unresolved == ()
    # Nothing unresolved: the generator-side call is a no-op, not a raise.
    resolved.require_resolved()


def test_resolve_keeps_the_declaration_order_the_strict_resolver_uses() -> None:
    """Generated groups sit where their `from_enum` entry was written.

    The deploy creates groups in this order and resolves a custom
    `owner_group` right after creating the group that names it, so this
    order is a contract and not a presentation choice.
    """
    schema = make_schema(enums=[make_enum("division", "Clinical")])
    owner = _group("{member} Owners")
    literal = _group("Coordinators", owner_group="Clinical Owners")
    perms = PermissionsConfig(
        levels=[], groups=[literal], default_policy=None, overrides={},
        # Declared BEFORE the literal group, which is what `after=0` records.
        group_sources=(GroupsFromEnum(enum="division", template=owner, after=0),),
    )
    mapping = make_mapping(permissions=perms)

    resolved = resolve(schema, mapping)

    assert [g.name for g in resolved.groups] == ["Clinical Owners", "Coordinators"]


def test_resolve_records_an_unknown_enum_rather_than_raising() -> None:
    """A check must still see every OTHER group and folder.

    One misspelled `from_enum` used to stop the whole resolution, and the
    checks then silently stopped judging groups and folders that had
    resolved.
    """
    schema = make_schema(
        make_table("Risk", "Title"),
        make_table("Action", "Title"),
        enums=[make_enum("division", "North")],
    )
    perms = PermissionsConfig(
        levels=[], groups=[_group("Coordinators")], default_policy=None, overrides={},
        group_sources=(
            GroupsFromEnum(enum="not_a_real_enum", template=_group("{member} Owners")),
        ),
    )
    mapping = make_mapping(
        entities={
            "Risk": EntityMapping(
                name="Risk", kind="DocumentLibrary", base_template=101,
                site_role="default",
                folder_source=FoldersFromEnum(enum="not_a_real_enum"),
            ),
            "Action": EntityMapping(
                name="Action", kind="DocumentLibrary", base_template=101,
                site_role="default", folder_source=FoldersFromEnum(enum="division"),
            ),
        },
        permissions=perms,
    )

    resolved = resolve(schema, mapping)

    # The misspelled folder source is absent, not silently empty; the other
    # entity's folders still resolve.
    assert "Risk" not in resolved.folders
    assert "Risk" not in resolved.folder_policies
    assert resolved.folders["Action"] == ("North",)
    # The literal group still resolves although the generated source did not.
    assert [g.name for g in resolved.groups] == ["Coordinators"]
    assert UnresolvedEnum(enum="not_a_real_enum", entity="Risk") in resolved.unresolved
    assert UnresolvedEnum(enum="not_a_real_enum", entity=None) in resolved.unresolved


def test_require_resolved_raises_the_named_error_for_a_generator() -> None:
    """A build must not silently omit a declared group or folder.

    The error type and its `.enum` must match what `declared_groups` and
    `declared_folders` raise today, because `_library.py` formats its
    finding off `err.enum` and the message has to keep agreeing with the
    deploy's tuple.
    """
    schema = make_schema(make_table("Risk", "Title"))
    folder_mapping = make_mapping(entities={
        "Risk": EntityMapping(
            name="Risk", kind="DocumentLibrary", base_template=101,
            site_role="default", folder_source=FoldersFromEnum(enum="missing"),
        ),
    })

    with pytest.raises(UnknownFolderEnumError) as folder_excinfo:
        resolve(schema, folder_mapping).require_resolved()
    assert folder_excinfo.value.enum == "missing"

    group_mapping = make_mapping(permissions=PermissionsConfig(
        levels=[], groups=[], default_policy=None, overrides={},
        group_sources=(GroupsFromEnum(enum="missing", template=_group("{member} Owners")),),
    ))

    with pytest.raises(UnknownGroupEnumError) as group_excinfo:
        resolve(schema, group_mapping).require_resolved()
    assert group_excinfo.value.enum == "missing"
