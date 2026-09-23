---
title: groups
sidebar_position: 22
---

# `dbml_sharepoint.analysis.groups`

*which site groups a mapping declares, enum sources resolved*

Which site groups a mapping actually declares.

`groups:` is written either as the groups themselves or as one
`{from_enum: <enum>, name: '{prefix} {member} ...'}` entry standing for one
group per enum member, and everything that reads the group list needs the
same answer: the deploy script, the assessment, the manifest, the wizard and
five check families. The same argument as `analysis/folders.py` -- where both
sides need the same fact it lives in a shared module -- with a sharper edge
here, because a generator that resolved the enum differently from the
validator would create groups no rule had judged.

Nothing here imports a check, so a generator can read it.

### `UnknownGroupEnumError`

`groups[].from_enum` names an enum the schema does not declare.

Raised rather than answered with an empty tuple, for the reason
`UnknownFolderEnumError` gives: a mapping that silently declared no
groups would deploy clean and leave every folder grant pointing at a
principal that was never created. The validator reports this as
`group_enum_unknown` before a generator runs, so reaching this exception
is a defect.

### `group_for_member`

```python
def group_for_member(source: dbml_sharepoint.model.mapping_types.GroupsFromEnum, member: str) -> dbml_sharepoint.model.mapping_types.SiteGroup
```

`source`'s template with `{member}` expanded to one enum member.

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

### `declaring_groups`

```python
def declaring_groups(perms: dbml_sharepoint.model.mapping_types.PermissionsConfig | None) -> tuple[dbml_sharepoint.model.mapping_types.SiteGroup, ...]
```

Every group DECLARATION: the literal groups and the enum templates.

`{member}` is unexpanded, so these are not the groups a site ends up
with and must not be used to write one. It answers the questions about
what a mapping DECLARES -- does anything carry `enroll_enterprise_reader`,
does this mapping declare groups at all -- which is the only kind a
caller holding no schema can ask, and the CLI asks several of them
before validation has run.

### `declared_groups`

```python
def declared_groups(perms: dbml_sharepoint.model.mapping_types.PermissionsConfig | None, enum_members: collections.abc.Mapping[str, collections.abc.Sequence[str]]) -> tuple[dbml_sharepoint.model.mapping_types.SiteGroup, ...]
```

Every group the mapping declares, in the order it declares them.

Generated groups sit where their `from_enum` entry was written rather
than after every literal group. The deploy creates groups in this order,
then reconciles every custom `owner_group` in a second pass, so an owner
declared after the group that names it is no longer a broken deployment.
Within one source the groups follow enum order, which is the order the
DBML writes the members in and therefore the order the folders are
created in.

### `resolvable_groups`

```python
def resolvable_groups(perms: dbml_sharepoint.model.mapping_types.PermissionsConfig | None, enum_members: collections.abc.Mapping[str, collections.abc.Sequence[str]]) -> tuple[dbml_sharepoint.model.mapping_types.SiteGroup, ...]
```

`declared_groups`, but an unknown enum leaves out only its own source.

For the validator, which must keep judging everything it CAN resolve
while one misspelled `from_enum` is reported by its own rule. Discarding
every generated group instead would skip the duplicate, name, owner,
provenance and rename checks for groups that resolved perfectly well, and
make list policies naming them look like unknown principals.

