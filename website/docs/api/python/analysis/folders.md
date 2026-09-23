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

