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


class UnknownGroupEnumError(LookupError, ValueError):
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

    A previous name that expands onto this group's own current name is
    dropped here, AFTER expansion, because that is where the collision
    appears: `{member}` and `{member_safe}` differ only for a member carrying
    a character SharePoint refuses, so a template renamed from the one to the
    other expands both to the same string for every other member and
    `renamed_from_is_a_declared_entity` then rejects the whole migration.
    Folded, and the survivors deduplicated folded, because `_renames.py`
    compares that way and a narrower filter would leave the rule it protects
    firing.
    """
    template = source.template
    name = expand_member(template.name, member)
    previous: list[str] = []
    seen = {name.casefold()}
    for raw in template.previous_names:
        expanded = expand_member(raw, member)
        if expanded.casefold() in seen:
            continue
        seen.add(expanded.casefold())
        previous.append(expanded)
    return replace(
        template,
        name=name,
        description=expand_member(template.description, member),
        owner_group=expand_member(template.owner_group, member),
        previous_names=tuple(previous),
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


def _ordered(
    perms: PermissionsConfig,
    enum_members: Mapping[str, Sequence[str]],
    *,
    strict: bool,
) -> tuple[SiteGroup, ...]:
    """The shared body of `declared_groups` and `resolvable_groups`.

    `strict` decides what an unknown enum does: raise, or leave that source
    out and resolve the rest. The order is the same either way.
    """
    literals = list(perms.groups)
    at_position: dict[int, list[SiteGroup]] = {}
    for source in perms.group_sources:
        if source.enum not in enum_members:
            if strict:
                raise UnknownGroupEnumError(source.enum)
            continue
        where = len(literals) if source.after is None else source.after
        at_position.setdefault(where, []).extend(
            group_for_member(source, member) for member in enum_members[source.enum]
        )
    out: list[SiteGroup] = []
    for index in range(len(literals) + 1):
        out.extend(at_position.get(index, ()))
        if index < len(literals):
            out.append(literals[index])
    return tuple(out)


def declared_groups(
    perms: PermissionsConfig | None, enum_members: Mapping[str, Sequence[str]],
) -> tuple[SiteGroup, ...]:
    """Every group the mapping declares, in the order it declares them.

    Generated groups sit where their `from_enum` entry was written rather
    than after every literal group. The deploy creates groups in this order,
    then reconciles every custom `owner_group` in a second pass, so an owner
    declared after the group that names it is no longer a broken deployment.
    Within one source the groups follow enum order, which is the order the
    DBML writes the members in and therefore the order the folders are
    created in.
    """
    if perms is None:
        return ()
    return _ordered(perms, enum_members, strict=True)


def resolvable_groups(
    perms: PermissionsConfig | None, enum_members: Mapping[str, Sequence[str]],
) -> tuple[SiteGroup, ...]:
    """`declared_groups`, but an unknown enum leaves out only its own source.

    For the validator, which must keep judging everything it CAN resolve
    while one misspelled `from_enum` is reported by its own rule. Discarding
    every generated group instead would skip the duplicate, name, owner,
    provenance and rename checks for groups that resolved perfectly well, and
    make list policies naming them look like unknown principals.
    """
    if perms is None:
        return ()
    return _ordered(perms, enum_members, strict=False)
