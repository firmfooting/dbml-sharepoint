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

MEASURED 2026-07-31, test/manual/templates/threshold-index-probe.js.j2: at 6,500
items in the target, against `GetLookupFieldChoices` — the call the form makes:

    Title, INDEXED           SERVED, 2,000 choices
    PickLabel, Calculated    REFUSED, SPQueryThrottledException
    PickCond,  Calculated    REFUSED, SPQueryThrottledException

`Title` is not indexed by default — the same run read `Indexed=false` on it and
indexing it flipped two other target queries from refused to served.

A CROSS-SITE reference is not a Lookup and gets none of this: it is expanded
into a Choice + URL pair, so no far-side list is ever enumerated.
"""

from collections.abc import Set as AbstractSet

from dbml_sharepoint.model.mapping_loader import EntityMapping
from dbml_sharepoint.model.parser import Schema

# A SharePoint list's built-in primary field, and the LookupField a lookup
# displays when the mapping declares nothing else.
DEFAULT_DISPLAY_COLUMN = "Title"


def lookup_target_entities(
    schema: Schema,
    cross_site_pairs: AbstractSet[tuple[str, str]],
) -> set[str]:
    """Entity names that a real SharePoint Lookup points at.

    The one derivation of "is this list looked up?". `lookup_display_columns`
    below and `analysis.checks._structure`'s calculated-display-column warning
    both read it, so they cannot disagree about which lists are targets — the
    same guarantee this module already gives for *which column* is displayed.

    A column named in `cross_site_reference_columns` is NOT a Lookup. It is
    expanded into a Choice + URL pair on the source list, so nothing on the far
    side is ever enumerated: there is no picker to protect, and indexing that
    list's display column would be a real `Indexed=true` MERGE on a customer
    tenant buying nothing.

    Filtered per (entity, column) PAIR, not per entity. A list targeted by a
    cross-site ref *and* a real lookup still has a picker and must keep its
    index; excluding every entity merely named in `cross_site_reference_columns`
    would drop it. `analysis.checks._naming` skips cross-site refs the same way,
    for the same reason.
    """
    return {
        column.ref.target_table
        for table in schema.tables
        for column in table.columns
        if column.ref is not None
        and (table.name, column.name) not in cross_site_pairs
    }


def lookup_display_columns(
    schema: Schema,
    entities: dict[str, EntityMapping],
    calculated: dict[str, set[str]],
    cross_site_pairs: AbstractSet[tuple[str, str]],
) -> dict[str, str]:
    """`{entity: column a lookup into it displays}` for every lookup target.

    Excludes an entity whose display column is calculated: such a column cannot
    carry an index, so returning it would have callers count or deploy one that
    cannot exist. `analysis.checks._structure` warns about those separately —
    silence here is not silence overall.

    Also excludes an entity reached only by a cross-site reference — see
    `lookup_target_entities`.
    """
    displayed: dict[str, str] = {}
    for name in sorted(lookup_target_entities(schema, cross_site_pairs)):
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
