"""Which entities a lookup points at, and what such a lookup displays.

Derived in one place because two consumers read it and they must not disagree:
`analysis.checks._context` folds the answer into `effective_indexes` so the
per-list ceiling counts it, and `generators.jsgen` emits it so the deployer
creates it. Computed separately, a drift between them is a validator warning
about an index nothing deploys, or a deployed index the ceiling never counted.

WHY THE INDEX MATTERS. A Lookup's picker enumerates the target list. Past the
5,000-item list view threshold that enumeration is refused and the NEW-ITEM FORM
stops working, while views that merely display the column carry on — so the
failure surfaces late, on the busiest list, looking like a form bug.

Measured at 6,500 items in the target against `GetLookupFieldChoices`, the call
the form itself makes (`test/manual/threshold-index-probe.js`):

    Title, INDEXED           SERVED, 2,000 choices
    PickLabel, Calculated    REFUSED, SPQueryThrottledException
    PickCond,  Calculated    REFUSED, SPQueryThrottledException

`Title` is not indexed by default — the same run read `Indexed=false` on it and
indexing it flipped two other target queries from refused to served.
"""

from dbml_sharepoint.model.mapping_loader import EntityMapping
from dbml_sharepoint.model.parser import Schema

# A SharePoint list's built-in primary field, and the LookupField a lookup
# displays when the mapping declares nothing else.
DEFAULT_DISPLAY_COLUMN = "Title"


def lookup_display_columns(
    schema: Schema,
    entities: dict[str, EntityMapping],
    calculated: dict[str, set[str]],
) -> dict[str, str]:
    """`{entity: column a lookup into it displays}` for every lookup target.

    Excludes an entity whose display column is calculated: such a column cannot
    carry an index, so returning it would have callers count or deploy one that
    cannot exist. `analysis.checks._structure` warns about those separately —
    silence here is not silence overall.
    """
    targets = {
        column.ref.target_table
        for table in schema.tables
        for column in table.columns
        if column.ref is not None
    }
    displayed: dict[str, str] = {}
    for name in sorted(targets):
        entity = entities.get(name)
        if entity is None:
            # A ref at a table with no mapping entry. Other checks report that;
            # inventing an index for it here would be a second, worse message.
            continue
        column = entity.display_column or DEFAULT_DISPLAY_COLUMN
        if column in calculated.get(name, set()):
            continue
        displayed[name] = column
    return displayed
