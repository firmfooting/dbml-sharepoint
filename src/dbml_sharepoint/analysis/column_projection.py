# src/dbml_sharepoint/analysis/column_projection.py
"""Which columns a provisioned list has a type for, and what each type is.

Split out of `analysis/conditions.py` (#168), which is normalisation,
validation and three SharePoint renderings in one 1,900-line module. This
concern is none of those: it answers what a deployed list ends up holding,
which is a fact about provisioning rather than about the condition grammar.
Its callers use that projection at different condition and view boundaries.

The dependency here is nothing. This module imports no other module in the
package, and `test_column_projection.py` gates that by importing it in a fresh
interpreter and reading back what got loaded. That is what makes it safe for
`analysis/joins.py`, which needs the system column types to derive
`SYSTEM_JOIN_COLUMNS` and has no business loading a renderer or the finding
vocabulary to get them.

BREAKING API MOVE (#168): the canonical imports are now
`dbml_sharepoint.analysis.column_projection.SYSTEM_COLUMN_TYPES` and
`dbml_sharepoint.analysis.column_projection.effective_column_types`, not the
`dbml_sharepoint.analysis.conditions` spellings of either. There is
deliberately no compatibility re-export: this package gives each public name
one importable home, and keeping the old path would recreate the shim the
architecture work is removing.

`effective_column_types` deliberately does NOT fold `SYSTEM_COLUMN_TYPES` in,
and the two are separate names for that reason. Their callers differ:
`generators.jsgen` and `checks/_views` merge the system types in where a view
may filter on `Created`, while `checks/_formatting` and `checks/_retirement`
pass the projection alone. Folding them in would change what every caller sees
in order to save two of them a merge, so the composition stays at the call
site. The absence is pinned by a test, because it reads like an oversight.
"""

# Types for the system columns this project models but DBML never declares.
# Views may reference these, and without them a date comparison on Created
# would render as Type="Text" rather than the intended date type.
SYSTEM_COLUMN_TYPES: dict[str, str] = {
    "ID": "int",
    "Created": "datetime",
    "Modified": "datetime",
    "Author": "person",
    "Editor": "person",
}


def effective_column_types(
    declared: dict[str, str], cross_site_columns: set[str] | frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Types for DBML columns plus fields provisioned implicitly or by expansion."""
    effective = {"Title": "nvarchar", **declared}
    for name in cross_site_columns:
        effective.setdefault(f"{name}Abbreviation", "nvarchar")
        effective.setdefault(f"{name}SiteUrl", "hyperlink")
    return effective
