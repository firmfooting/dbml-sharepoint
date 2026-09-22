---
title: folders
sidebar_position: 20
---

# `dbml_sharepoint.analysis.folders`

*which folders a library declares, enum sources resolved*

Which root folders a document library actually declares.

`entities.<name>.folders` is written either as the names themselves or as
`{from_enum: <enum>}`, and four callers need the answer: the deploy script,
the assessment, the reporting pack and the library check. Where both sides
need the same fact it lives in a shared module (`analysis/joins.py` is the
worked example), because a check and a generator that resolved it
separately could disagree about which folders a library has, and the deploy
would then create folders the assessment never looked for.

Nothing here imports a check, so a generator can read it.

### `UnknownFolderEnumError`

`folders.from_enum` names an enum the schema does not declare.

Raised rather than answered with an empty tuple: a library that silently
declared no folders would deploy clean, pass every phase and leave an
operator filing into a root that has none of the folders the mapping
asked for. The validator reports this as `folder_enum_unknown` before a
generator ever runs, so reaching this exception is a defect.

Both bases on purpose. `LookupError` is what it is; `ValueError` is what
`pipeline.execute_report` catches, and escaping that handler skipped the
path that clears a previously generated pack, leaving a stale report
looking current behind an unhandled traceback.

### `declared_folders`

```python
def declared_folders(source: FolderSource, enum_members: collections.abc.Mapping[str, collections.abc.Sequence[str]]) -> tuple[str, ...]
```

The folder names `source` declares, in declaration order.

Enum members are taken in the order the DBML writes them, which is the
order the folder phase creates them in and the order the reporting pack
lists them in, so a reordered enum reorders nothing that matters and a
diff of either stays readable.

### `policy_for_folder`

```python
def policy_for_folder(policy: dbml_sharepoint.model.mapping_types.ListPermissionPolicy, folder: str) -> dbml_sharepoint.model.mapping_types.ListPermissionPolicy
```

`policy` with `{member}` expanded to one folder's name.

Public because the validator expands the same policy the generator does:
a level or principal that only exists after expansion has to be judged
after expansion, and judging it against a second implementation would be
the drift this module exists to remove.

Both the principal and the level take the token. A per-division group is
the obvious use of the first; the second is there because a family that
wanted a level per division would otherwise have to write the policy out
once per folder, which is the duplication this whole shape removes.

### `folder_policies`

```python
def folder_policies(entity_name: str, source: FolderSource, perms: dbml_sharepoint.model.mapping_types.PermissionsConfig | None, enum_members: collections.abc.Mapping[str, collections.abc.Sequence[str]]) -> tuple[tuple[str, dbml_sharepoint.model.mapping_types.ListPermissionPolicy], ...]
```

(folder name, policy) for every folder `entity_name` declares.

`list_permissions.folders` is keyed by entity and never by folder, so
the folders this returns are exactly `declared_folders`' answer and the
two cannot drift. An entity with a policy and no folders gets an empty
tuple here; that the block then does nothing is the validator's finding
(`folder_permissions_without_folders`), not a silence to paper over.

