# src/dbml_sharepoint/analysis/folders.py
"""Which root folders a document library actually declares.

`entities.<name>.folders` is written either as the names themselves or as
`{from_enum: <enum>}`, and four callers need the answer: the deploy script,
the assessment, the reporting pack and the library check. Where both sides
need the same fact it lives in a shared module (`analysis/joins.py` is the
worked example), because a check and a generator that resolved it
separately could disagree about which folders a library has, and the deploy
would then create folders the assessment never looked for.

Nothing here imports a check, so a generator can read it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace

from dbml_sharepoint.model.mapping_types import (
    FoldersFromEnum,
    FolderSource,
    ListPermissionPolicy,
    PermissionsConfig,
    Principal,
    RoleAssignment,
)
from dbml_sharepoint.model.prefix import expand_member


class UnknownFolderEnumError(LookupError):
    """`folders.from_enum` names an enum the schema does not declare.

    Raised rather than answered with an empty tuple: a library that silently
    declared no folders would deploy clean, pass every phase and leave an
    operator filing into a root that has none of the folders the mapping
    asked for. The validator reports this as `folder_enum_unknown` before a
    generator ever runs, so reaching this exception is a defect.
    """

    def __init__(self, enum: str) -> None:
        super().__init__(f"folders.from_enum names unknown enum {enum!r}")
        self.enum = enum


def declared_folders(
    source: FolderSource, enum_members: Mapping[str, Sequence[str]],
) -> tuple[str, ...]:
    """The folder names `source` declares, in declaration order.

    Enum members are taken in the order the DBML writes them, which is the
    order the folder phase creates them in and the order the reporting pack
    lists them in, so a reordered enum reorders nothing that matters and a
    diff of either stays readable.
    """
    if isinstance(source, FoldersFromEnum):
        if source.enum not in enum_members:
            raise UnknownFolderEnumError(source.enum)
        return tuple(enum_members[source.enum])
    return source


def _policy_for_folder(
    policy: ListPermissionPolicy, folder: str,
) -> ListPermissionPolicy:
    """`policy` with `{member}` expanded to one folder's name.

    Both the principal and the level take the token. A per-division group is
    the obvious use of the first; the second is there because a family that
    wanted a level per division would otherwise have to write the policy out
    once per folder, which is the duplication this whole shape removes.
    """
    return replace(policy, assignments=[
        RoleAssignment(
            principal=Principal(
                kind=a.principal.kind,
                name=(
                    None if a.principal.name is None
                    else expand_member(a.principal.name, folder)
                ),
            ),
            level=expand_member(a.level, folder),
        )
        for a in policy.assignments
    ])


def folder_policies(
    entity_name: str,
    source: FolderSource,
    perms: PermissionsConfig | None,
    enum_members: Mapping[str, Sequence[str]],
) -> tuple[tuple[str, ListPermissionPolicy], ...]:
    """(folder name, policy) for every folder `entity_name` declares.

    `list_permissions.folders` is keyed by entity and never by folder, so
    the folders this returns are exactly `declared_folders`' answer and the
    two cannot drift. An entity with a policy and no folders gets an empty
    tuple here; that the block then does nothing is the validator's finding
    (`folder_permissions_without_folders`), not a silence to paper over.
    """
    if perms is None:
        return ()
    policy = perms.folder_policies.get(entity_name)
    if policy is None:
        return ()
    return tuple(
        (folder, _policy_for_folder(policy, folder))
        for folder in declared_folders(source, enum_members)
    )
