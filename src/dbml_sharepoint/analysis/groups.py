# src/dbml_sharepoint/analysis/groups.py
"""Which site groups a mapping actually declares.

`groups:` is written either as the groups themselves or as one
`{from_enum: <enum>, name: '{prefix} {member} ...'}` entry standing for one
group per enum member, and everything that reads the group list needs the
same answer: the deploy script, the assessment, the manifest, the wizard and
five check families. The same argument as `analysis/folders.py` -- where both
sides need the same fact it lives in a shared module -- with a sharper edge
here, because a generator that resolved the enum differently from the
validator would create groups no rule had judged.

Nothing here imports a check, so a generator can read it.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace

from dbml_sharepoint.model.mapping_types import GroupsFromEnum, PermissionsConfig, SiteGroup
from dbml_sharepoint.model.prefix import expand_member


class UnknownGroupEnumError(LookupError):
    """`groups[].from_enum` names an enum the schema does not declare.

    Raised rather than answered with an empty tuple, for the reason
    `UnknownFolderEnumError` gives: a mapping that silently declared no
    groups would deploy clean and leave every folder grant pointing at a
    principal that was never created. The validator reports this as
    `group_enum_unknown` before a generator runs, so reaching this exception
    is a defect.
    """

    def __init__(self, enum: str) -> None:
        super().__init__(f"groups[].from_enum names unknown enum {enum!r}")
        self.enum = enum


def group_for_member(source: GroupsFromEnum, member: str) -> SiteGroup:
    """`source`'s template with `{member}` expanded to one enum member.

    Name, description and every previous name take the member, because all
    three are the group's identity on a site: the description carries the
    provenance marker a later run adopts by, and the previous names are what
    a rename is found under.
    """
    template = source.template
    return replace(
        template,
        name=expand_member(template.name, member),
        description=expand_member(template.description, member),
        owner_group=expand_member(template.owner_group, member),
        previous_names=tuple(
            expand_member(name, member) for name in template.previous_names
        ),
    )


def declaring_groups(perms: PermissionsConfig | None) -> tuple[SiteGroup, ...]:
    """Every group DECLARATION: the literal groups and the enum templates.

    `{member}` is unexpanded, so these are not the groups a site ends up
    with and must not be used to write one. It answers the questions about
    what a mapping DECLARES -- does anything carry `enroll_enterprise_reader`,
    does this mapping declare groups at all -- which is the only kind a
    caller holding no schema can ask, and the CLI asks several of them
    before validation has run.
    """
    if perms is None:
        return ()
    return (*perms.groups, *(source.template for source in perms.group_sources))


def declared_groups(
    perms: PermissionsConfig | None, enum_members: Mapping[str, Sequence[str]],
) -> tuple[SiteGroup, ...]:
    """Every group the mapping declares: the literal ones, then the generated.

    Literal groups keep their declaration order and come first, so the shared
    tool-owned groups stay where a reader expects them. Generated groups
    follow in enum order, which is the order the DBML writes the members in
    and therefore the order the folders are created in.
    """
    if perms is None:
        return ()
    out = list(perms.groups)
    for source in perms.group_sources:
        if source.enum not in enum_members:
            raise UnknownGroupEnumError(source.enum)
        out.extend(
            group_for_member(source, member) for member in enum_members[source.enum]
        )
    return tuple(out)
