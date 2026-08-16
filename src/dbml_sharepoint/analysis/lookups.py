"""Which entities a lookup points at, and what such a lookup displays.

Derived in one place because two consumers read it and they must not disagree:
`analysis.checks.context` folds the answer into `effective_indexes` so the
per-list ceiling counts it, and `generators.jsgen` emits it so the deployer
creates it. Computed separately, a drift between them is a validator warning
about an index nothing deploys, or a deployed index the ceiling never counted.

WHY THE INDEX MATTERS. A Lookup's picker enumerates the target list. Past the
5,000-item list view threshold that enumeration is refused and the NEW-ITEM FORM
stops working, while views that merely display the column carry on, so the
failure surfaces late, on the busiest list, looking like a form bug.

MEASURED 2026-07-31, test/manual/templates/threshold-index-probe.js.j2: at 6,500
items in the target, against `GetLookupFieldChoices` (the call the form makes):

    Title, INDEXED           SERVED, 2,000 choices
    PickLabel, Calculated    REFUSED, SPQueryThrottledException
    PickCond,  Calculated    REFUSED, SPQueryThrottledException

`Title` is not indexed by default. The same run read `Indexed=false` on it and
indexing it flipped two other target queries from refused to served.

A CROSS-SITE reference is not a Lookup and gets none of this: it is expanded
into a Choice + URL pair, so no far-side list is ever enumerated.
"""

from collections.abc import Set as AbstractSet

from dbml_sharepoint.model.mapping_types import EntityMapping
from dbml_sharepoint.model.parser import Schema

# A SharePoint list's built-in primary field, and the LookupField a lookup
# displays when the mapping declares nothing else.
DEFAULT_DISPLAY_COLUMN = "Title"


def display_column_for(entity: EntityMapping | None) -> str:
    """The column a lookup INTO this entity displays (SP `LookupField`).

    ONE line, and a function anyway, because the question had three answers.
    `jsgen` wrote `... or "Title"` when composing the field body, `reportgen`
    wrote `return "Title"` when choosing what to `$expand`, and this module
    wrote `entity.display_column or DEFAULT_DISPLAY_COLUMN`. Three spellings
    of one rule, and the bare literal in two of them meant a change to the
    default would have moved the deploy without moving the reports
    (a Power Query that expands a column the list does not surface).

    Takes `None` deliberately: the callers all reach this through
    `entities.get(...)`, and a ref at a table with no mapping entry is
    reported by other checks. Answering with the built-in Title keeps those
    callers from each inventing their own None branch.

    NOT the same question as "which display column can be indexed".
    `lookup_display_columns` below answers that one, and excludes calculated
    columns because they cannot carry an index. A calculated display column
    is still what SharePoint DISPLAYS, so folding that exclusion in here
    would leave a real lookup with no LookupField at all.
    """
    if entity is None:
        return DEFAULT_DISPLAY_COLUMN
    return entity.display_column or DEFAULT_DISPLAY_COLUMN


def lookup_target_entities(
    schema: Schema,
    cross_site_pairs: AbstractSet[tuple[str, str]],
) -> set[str]:
    """Entity names that a real SharePoint Lookup points at.

    The one derivation of "is this list looked up?". `lookup_display_columns`
    below and `analysis.checks._structure`'s calculated-display-column warning
    both read it, so they cannot disagree about which lists are targets, the
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
    """`{entity: display column to INDEX}` for every lookup target.

    The INDEXABLE subset, not the answer to "what does a lookup display".
    That is `display_column_for` above, and this reads it so the two cannot
    disagree about the default.

    Excludes an entity whose display column is calculated: such a column cannot
    carry an index, so returning it would have callers count or deploy one that
    cannot exist. `analysis.checks._structure` warns about those separately.
    Silence here is not silence overall.

    Also excludes an entity reached only by a cross-site reference. See
    `lookup_target_entities`.
    """
    displayed: dict[str, str] = {}
    for name in sorted(lookup_target_entities(schema, cross_site_pairs)):
        entity = entities.get(name)
        if entity is None:
            # A ref at a table with no mapping entry. Other checks report that;
            # inventing an index for it here would be a second, worse message.
            continue
        column = display_column_for(entity)
        if column in calculated.get(name, set()):
            continue
        displayed[name] = column
    return displayed
