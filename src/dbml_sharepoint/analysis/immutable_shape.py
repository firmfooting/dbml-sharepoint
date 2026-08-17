# src/dbml_sharepoint/analysis/immutable_shape.py
"""The field and list properties SharePoint will not let a deploy change.

`deploy.js.txt` refuses to reconcile these: a mismatch aborts before anything is
written, because the platform offers no in-place change and the tool will not
delete and recreate an object holding somebody's data. The comparisons live in
`templates/deploy/_field_reconcile.js.j2`; this module is the list of what they
cover, so the delta report and the deployment record can iterate it instead of
restating it. `test/test_immutable_shape.py` fails if the two ever disagree.
"""

#: Read back for every declared field, from `_FIELD_SHAPE_SELECT`.
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
