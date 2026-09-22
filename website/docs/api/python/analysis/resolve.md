---
title: resolve
sidebar_position: 23
---

# `dbml_sharepoint.analysis.resolve`

*every enum-sourced mapping section, resolved once*

Resolve every enum-sourced mapping section once, at the boundary.

`entities.<name>.folders` and `groups[].from_enum` are both written against a
schema enum and resolved by `analysis/folders.py` and `analysis/groups.py`.
Each of those already offers a strict resolver (raise on an unknown enum) and
a lenient one (drop that source, keep the rest), because a generator and a
check need different behaviour for the same defect: a build must never
silently omit a declared group or folder, but a check must keep judging every
OTHER group and folder while the misspelling itself is reported by its own
rule.

This module does not choose between the two. It resolves LENIENTLY, once, and
records what it could not resolve, so the difference between a generator's
needs and a check's becomes what a caller does with one field (`unresolved`)
rather than which function it called. `ResolvedMapping.require_resolved`
gives a generator the strict behaviour back, raising the same error types
the strict resolvers raise today.

Nothing here imports a check, so a generator can read it.

### `UnresolvedEnum`

```python
@dataclass(frozen=True)
class UnresolvedEnum:
    enum: str
    entity: str | None = None
```

One `from_enum` source naming an enum the schema does not declare.

`entity` is the entity whose `folders` named it, for a folder source.
It is `None` for a `groups[].from_enum` source, which is not scoped to
any one entity. One shape carries both rather than a tagged type per
source, because nothing downstream asks for more than this: the finding
each source's own rule reports (`FOLDER_ENUM_UNKNOWN`,
`GROUP_ENUM_UNKNOWN`) builds its message from the enum name alone, and
where an entity is part of that message the check already has it from
the loop that found the source, not from this record.

### `ResolvedMapping`

```python
@dataclass(frozen=True)
class ResolvedMapping:
    mapping: Mapping
    enum_members: collections.abc.Mapping[str, tuple[str, ...]]
    folders: collections.abc.Mapping[str, tuple[str, ...]]
    folder_policies: collections.abc.Mapping[str, tuple[tuple[str, dbml_sharepoint.model.mapping_types.ListPermissionPolicy], ...]]
    groups: tuple[dbml_sharepoint.model.mapping_types.SiteGroup, ...]
    unresolved: tuple[dbml_sharepoint.analysis.resolve.UnresolvedEnum, ...] = ()
```

Every enum source in a mapping, resolved once against a schema.

Built by `resolve()`, always leniently: a folder or group source naming
an enum the schema does not declare is left out of the resolved fields
below and recorded in `unresolved` instead of raised, so one bad
`from_enum` does not stop every OTHER group or folder from being judged.
A caller that must fail closed instead -- a generator, which must never
silently omit a declared group or folder -- calls `require_resolved()`
first.

`folders` and `folder_policies` key by entity name and agree with each
other on what "no answer" means: an entity ABSENT from either is one
whose folder source could not be resolved (recorded in `unresolved`); an
entity PRESENT with an empty tuple is one that resolved and declares no
folders. An entity that never writes a `folders:` key at all falls into
the second case, never the first: `EntityMapping.folder_source` defaults
to `()`, which `declared_folders` resolves to no folders without ever
raising. So every entity in the mapping is a key in both `folders` and
`folder_policies`, except the ones actually unresolved.

#### `ResolvedMapping.require_resolved`

```python
def require_resolved(self) -> None
```

Raise what the strict resolvers raise today, for a generator.

Raises on the FIRST unresolved source: `UnknownFolderEnumError` for
a folder source, `UnknownGroupEnumError` for a group source, each
carrying the same `.enum` the strict `declared_folders` and
`declared_groups` raise today. An existing `except
UnknownFolderEnumError` therefore still catches it, and a finding
that formats its message off `err.enum` (`_library.py` does exactly
this) reads the same whichever resolver raised it.

A no-op when nothing is unresolved.

### `resolve`

```python
def resolve(schema: dbml_sharepoint.model.parser.Schema, mapping: dbml_sharepoint.model.mapping_types.Mapping) -> dbml_sharepoint.analysis.resolve.ResolvedMapping
```

Resolve `mapping`'s folders, folder policies and groups against `schema`.

Lenient, as `ResolvedMapping` describes: an entity or group source naming
an enum the schema does not declare is left out of the resolved fields
and appended to `unresolved` rather than raised. Folders are resolved per
entity, in `mapping.entities` order; groups are resolved once via
`resolvable_groups`, which already leaves out only the sources it cannot
resolve, and `mapping.permissions.group_sources` is then walked once more
to name which of those, if any, that was.

