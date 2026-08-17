# src/dbml_sharepoint/analysis/immutable_shape.py
"""The field and list properties `deploy.js.txt` refuses to reconcile.

A mismatch aborts the run before anything is written, instead of being changed to
match the declaration. `InternalName`, `TypeAsString` and `BaseTemplate` are
refused because the platform offers no in-place change and the tool will not
delete and recreate an object holding somebody's data. `ReadOnlyField` and
`Sealed` are not platform immutability at all, they are impostor checks: this
deploy writes `Sealed` itself (the maintenance unseal clears it, the seal phase
sets it), and the expected `ReadOnlyField` is derived from the declared type, so
an unexpected value means the existing column is not the one that was declared.

The comparisons live in `templates/deploy/_field_reconcile.js.j2`. This module
names the set so that `test/test_immutable_shape.py` can cross-check the two
against each other; nothing else reads it yet.
"""

#: Read back for every declared field, from `_FIELD_SHAPE_SELECT`. The first two
#: are platform immutability; the last two are impostor checks.
IMMUTABLE_FIELD_PROPERTIES: tuple[str, ...] = (
    "InternalName",
    "TypeAsString",
    "ReadOnlyField",
    "Sealed",
)

#: Separate because the probe is: only a field with a declared target list
#: issues the second request that reads these.
IMMUTABLE_LOOKUP_PROPERTIES: tuple[str, ...] = ("LookupList", "LookupField")

#: Read back for every declared list.
IMMUTABLE_LIST_PROPERTIES: tuple[str, ...] = ("BaseTemplate",)
