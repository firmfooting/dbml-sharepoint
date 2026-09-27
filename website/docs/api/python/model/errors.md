---
title: errors
sidebar_position: 8
---

# `dbml_sharepoint.model.errors`

*the named refusals a mapping reader raises*

The refusals the mapping loader raises, named so a caller can tell them apart.

Every class here is a `ValueError`. The CLI funnels configuration failures
through `project.CONFIG_ERRORS`, which lists `ValueError`, and prints the
message instead of a traceback, so a SharePoint admin reads the sentence
rather than twenty lines of loader internals. Naming the errors adds an axis
a caller can switch on without matching message text; it removes nothing.

The hierarchy lives in its own module for the reason `_keys.py` does: every
section family, the shared readers, the condition parser and the loader itself
raise these, and none of them may import another. `mapping_loader.py` is the
loader's public face, but it imports `reading` and `sections`, so the classes
cannot live there without a cycle.

`model/env_file.py` is the precedent for the shape: one base class a caller can
catch everything with, and subclasses that separate the kinds an author
actually distinguishes.

### `MappingError`

Anything wrong with a mapping.yaml or a file it names.

### `MappingSourceError`

A document the loader had to read never became data it would use.

The file could not be opened, its bytes are not UTF-8 or do not parse,
or the parser refused what they say. Distinct from the refusals below
because none of them can be stated yet: no block of the document has
been read, so the fix is to the file or to the path rather than to a
declaration.

The parser refuses a key written twice in any mapping of the document,
at any depth and inside a merged one, naming the key and the line of
each occurrence. It also refuses an explicit tag or a directive, naming
each line, and valid YAML it will not read, such as a reused anchor.
Its error is kept as `__cause__`.

### `MappingShapeError`

A block is not the shape its section takes.

The wrong YAML type, a required key absent, an empty group, or two keys
that exclude each other. This is most of what the loader refuses, because
YAML itself imposes almost no structure on the document.

### `UnknownMappingKeyError`

A key no reader admits, including one this loader used to read.

Separate from a shape error because the fix differs: a shape error is
corrected in place, and this one is a key to rename or delete.

### `MappingValueError`

A value of the right shape that this loader will not accept.

Outside a closed vocabulary such as a sort direction, an entity kind or a
view scope, or text that does not parse as what it claims to be.

### `MappingReferenceError`

Something the mapping points at does not resolve.

A file beside the mapping that cannot be read, a fragment naming a key the
target file does not hold, or a declaration naming another that this
document does not produce. The fix is outside the block that reported it.

