"""How many join operations a view performs, and which of its columns pay one.

Shared for the same reason `lookups.py` is: the validator refuses a view the
platform would render blank, and `generators.jsgen` builds the one view no
author declares. Computed separately, a drift between them means a build that
passes a view the deploy then creates over the ceiling, or one refused that was
never going to exist. A generator must not import from `analysis/checks/`, which
is the other half of why this is a module and not a helper in `_views.py`.

WHY IT MATTERS. This threshold is a property of a view's SHAPE, not of its size:
a view with 13 or more join-bearing columns is blank on a list holding ten rows.
No amount of indexing helps and no deployment is small enough to avoid it. It is
a DIFFERENT limit from the 5,000-item list view threshold `_views.py` also warns
about, and the two are distinguishable in a transcript: this one refuses with
`SPQueryThrottledException` code `-2147024749`, the item-count one with
`-2147024860`.

MEASURED 2026-07-31, test/manual/templates/threshold-index-probe.js.j2, at 6,000
items with the filter held constant at the same 60-row indexed query so the join
count was the only variable. The ids are under `scale.join`, and the mnemonic
each one replaced follows it because the recorded transcripts quote the mnemonic:

    lookup-column-ceiling         (JOINMAX)  a DBML `ref`: 12 render, 13 REFUSED
    person-counts-as-join         (JOINPER)  at the ceiling, adding one REFUSED
    created-by-counts-as-join     (JOINSYS)  Author: at the ceiling, REFUSED
    modified-by-counts-as-join    (JOINEDT)  Editor: at the ceiling, REFUSED
    projected-field-costs-a-join  (JOINPRJ)  at the ceiling, SERVED and READ BACK

Each suspect was tested at the ceiling PLUS EXACTLY ONE column, because that is
the only shape that discriminates: against a ceiling of 12, adding one column to
a base of 11 lands on 12 and renders whether or not it counts. An earlier
revision made that mistake and reported Person as not counting. A lookup holding
NO DATA still counts. All 14 probe columns were empty and the ceiling was still
12.

`Created` and `Modified` are NOT counted, and that row is INFERRED rather than
measured: they are `datetime`, and only Author and Editor are person-typed in
SYSTEM_COLUMN_TYPES. Counting all five members of SYSTEM_COLUMNS would be wrong
by two on every list. Closing it needs two more entries in the probe's
`suspects` array; see issue #44.

A CROSS-SITE reference costs nothing: it is expanded into a Choice + URL pair, so
no Lookup exists to join through. Same exclusion as the lookup ShowField work,
off the same `cross_site_pairs`.

A LOOKUP'S ADDITIONAL-FIELD PROJECTIONS cost nothing extra, measured free twice,
`scale.join.projected-field-costs-a-join` (JOINPRJ in those transcripts) on runs
35700faa and f663165e, and on the later run the dependent field was verified
PRESENT in the returned row (31 keys) rather than assumed. A view that silently
dropped the field would have rendered too, which is how the earlier
`scale.index.caml-eq-indexed-lookup-projected` (LOOPRJ) question misled. So a
lookup showing five of its target's fields costs ONE, not six. Projections ARE
declarable now: the `lookup_projections` mapping key generates each dependent
field as ``<column><target>`` (e.g.
`RelatedRiskTitle`), and that generated name is not a DBML column, so
`join_bearing_columns` never sees it and nothing here has to exclude it.
`test/test_joins.py::test_a_lookup_projection_costs_no_join` is the test this
paragraph was waiting for.

A MULTI-VALUE LOOKUP COSTS ONE, the same as a single-value one. It is one
column, one `LookupList` binding and one relationship, and the count here is a
count of join-bearing COLUMNS, so `join_bearing_columns` already returns it once
on the strength of `col.ref is not None` with no arity test anywhere. This row
is INFERRED, not measured, like the `Created`/`Modified` row above: the
2026-09-02 multi-lookup probe answered creation, indexing, mutability and write
shape, and left join cost open (#409 Q3). It is recorded as one rather than more
because a rule must never be stronger than what has been shown: counting two
would refuse views that may well render, and nothing has been observed that
says they do not. Closing it needs the same ceiling-plus-one shape every other
row here was measured at, a view of 11 ordinary lookups plus one multi-value
lookup against a list over the threshold. `test/test_joins.py::
test_a_multi_value_lookup_costs_one_join_at_the_ceiling` pins the answer, so
changing it is a deliberate act with a failing test attached.

8 IS NOT THE NUMBER. It comes from `MaxQueryLookupFields`, a farm property that
does not exist in SharePoint Online; there is no "default 8 raised by a
cumulative update" here, that is the on-premises upgrade story. The strongest
first-party SPO statement of 12 is in the Power Query connector documentation.
The citation being that thin is why the ceiling was measured, and why the
uncertainty is carried by a warning band rather than hidden. The band covers
the two counts before the ceiling, 11 and 12.
"""

# Two lines, not `from collections.abc import Iterable, Set as AbstractSet`:
# that single-line form fails ruff I001 and ruff's own fix is to SPLIT it.
# `analysis/lookups.py:28` uses the same shape.
from collections.abc import Iterable
from collections.abc import Set as AbstractSet

from dbml_sharepoint.analysis.column_projection import SYSTEM_COLUMN_TYPES
from dbml_sharepoint.analysis.rendered_columns import SYSTEM_COLUMNS, rendered_columns
from dbml_sharepoint.analysis.typemap import JOIN_BEARING_TYPES
from dbml_sharepoint.model.mapping_types import EntityMapping
from dbml_sharepoint.model.parser import Table

# Measured: 12 rendered, 13 refused. Above this a view is blank at any list size.
JOIN_LIMIT = 12

# The last two counts before the measured ceiling warn. 12 held on the tenant
# measured and the SharePoint Online citation is thin, so a view at 11 or 12
# may not travel. The band used to start at 9, because 8 was a real ceiling
# on some on-premises farms; it was narrowed on 2026-09-02 when a shipped
# entity needed nine, since that farm property does not exist in SharePoint
# Online and no measurement here has ever shown fewer than 12.
JOIN_WARN_AT = 11

# Appended to every generated `All Items` view without being asked for, and the
# two nobody counts. DERIVED, not written out: `column_projection` already
# records that Author and Editor are `person` while Created and Modified
# are `datetime`, and a second hand-written copy of that fact is exactly what
# goes stale. `Created` and `Modified` fall out of this expression on their own,
# which is the INFERRED half of the rule, never measured; see the module
# docstring. `test/test_joins.py::test_the_bands_are_eleven_and_twelve` pins
# what this must evaluate to.
SYSTEM_JOIN_COLUMNS = frozenset(
    name for name, col_type in SYSTEM_COLUMN_TYPES.items()
    if col_type in JOIN_BEARING_TYPES
)


def join_bearing_columns(table: Table, cross_site_cols: AbstractSet[str]) -> set[str]:
    """Every column whose presence in a view of `table` costs one join.

    Refs are collected separately from JOIN_BEARING_TYPES because a DBML `ref`
    is `int`-typed and a type test cannot see it. A ref named in
    `cross_site_reference_columns` is excluded: it never becomes a Lookup.

    Arity is not tested, which is the decision and not an omission: a
    multi-value ref (`int[] [ref: > X.Id]`, a LookupMulti) is one column and
    costs one join. See the module docstring for why that is recorded as one
    and what would settle it.

    The two system columns are always included. A declared view may name them,
    and the generated `All Items` always does.
    """
    bearing = set(SYSTEM_JOIN_COLUMNS)
    for col in table.columns:
        if col.name in cross_site_cols:
            continue
        if col.ref is not None or col.type in JOIN_BEARING_TYPES:
            bearing.add(col.name)
    return bearing


def joining_fields(
    fields: Iterable[str], join_bearing: AbstractSet[str],
) -> list[str]:
    """The members of `fields` that cost a join, sorted and deduplicated.

    Returned as NAMES rather than a count because every message has to name
    them: `Author` and `Editor` are the two an author never wrote down, and on
    `All Items` there is no declaration to read, so a bare number sends the
    reader looking in the wrong file.

    A lookup's additional-field projections cost nothing extra and nothing here
    excludes them: each is a generated dependent field named ``<column><target>``,
    which is not a DBML column and so is not in `join_bearing`. Measurement and
    reasoning are in the module docstring; the test that hangs off them is
    `test/test_joins.py::test_a_lookup_projection_costs_no_join`.
    """
    return sorted({name for name in fields if name in join_bearing})


def all_items_hidden(entity: EntityMapping) -> frozenset[str]:
    """Columns the generated `All Items` view must not render.

    One line, in the shared module, so the validator counts exactly what the
    generator omits. Declared views are unaffected. They keep every field they
    declare, and nothing here is consulted for them.
    """
    return frozenset(entity.hide_from_all_items)


def all_items_rendered(
    table: Table,
    cross_site_cols: AbstractSet[str],
    projected_cols: AbstractSet[str] = frozenset(),
) -> set[str]:
    """Every column the generated `All Items` view renders, before hiding.

    `rendered_columns` plus `Title` plus the five `SYSTEM_COLUMNS`. The
    `{"Title"}` union is not redundant padding: a DBML table need not declare
    its own `Title` column at all, because SharePoint's base-template `Title` exists
    on every list regardless, and `jsgen.py` writes it into `All Items`
    literally (see that file's `title_patch` branch), never through
    `rendered_columns`, which only sees columns `table.columns` actually
    lists. An entity that DOES declare `Title` masks this: `rendered_columns`
    already contains it with no union applied, which is exactly what let this
    union go silently unread by one of its two former call sites. See
    `test/test_validator_joins.py::test_hiding_title_is_refused_as_not_join_bearing_not_as_a_typo`
    for the fixture shaped to catch that.

    ONE place this set is written down, on purpose: `all_items_joining_fields`
    below and `_views.py`'s entity loop both call this rather than each
    carrying their own copy of the same three-term union. Two copies of an
    identical-looking expression is how a dropped term goes unnoticed.
    The two used to be `rendered_columns(...) | {"Title"} | SYSTEM_COLUMNS`
    written out twice, and dropping the term from either one alone left the
    other's callers unaffected, which is what the test above exists to catch
    now that there is only one copy for it to catch a drift in.
    """
    return (
        rendered_columns(table, set(cross_site_cols), set(projected_cols))
        | {"Title"} | SYSTEM_COLUMNS
    )


def all_items_joining_fields(
    table: Table,
    entity: EntityMapping,
    cross_site_cols: AbstractSet[str],
    projected_cols: AbstractSet[str] = frozenset(),
) -> list[str]:
    """The join-bearing fields the GENERATED `All Items` view renders.

    The single place this arithmetic is written down: `all_items_rendered`
    minus whatever `hide_from_all_items` hides, narrowed to what
    `join_bearing_columns` counts. `_views.py`'s entity loop and
    `test_template_standard.py`'s shipped-template survey both call this
    rather than each carrying their own copy, because a survey test that re-typed
    the formula by hand would be pinning its OWN arithmetic, not what the
    validator computes, and would keep passing even if the validator's copy
    silently dropped a term.

    NOT the same code the generator runs. Read this honestly. jsgen builds
    All Items from `emitted_fields` (phase-1 titles plus the phase-2 lookup
    titles), which is a different code path that happens to produce the same
    set. `test/test_jsgen.py::test_the_validator_and_the_generator_agree_on_what_all_items_renders`
    carries ONE equivalence test pinning the two together; if that test goes,
    so does the guarantee.
    """
    rendered = all_items_rendered(table, cross_site_cols, projected_cols)
    bearing = join_bearing_columns(table, cross_site_cols)
    hidden = all_items_hidden(entity)
    return joining_fields(rendered - hidden, bearing)
