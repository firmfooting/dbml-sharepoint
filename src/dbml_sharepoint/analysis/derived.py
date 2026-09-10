"""Derived reporting columns: what each one contributes, and what it reads.

Reporting-only columns declared under `derived_columns`. Nothing here is
deployed: no SharePoint field is created, nothing is read back, and a list
carries no trace of one. They exist in the generated Power Query and nowhere
else.

SHARED because two sides need the same facts and must not drift. `reportgen`
emits the steps; `checks/_derived` refuses a declaration that names a column
the query does not produce. `AGENTS.md` is explicit that such a fact lives in
a shared module, and that a generator must never import from
`analysis/checks/`.

WHY THE REFERENCE CHECK IS THE RULE THAT MATTERS. A derived column names its
inputs in a string. Nothing downstream reads that string until Power BI does:
the build succeeds, the pack writes, the query text is well formed, and the
failure arrives at refresh as `The column 'X' of the table wasn't found`,
which takes every query behind it with it. Measured on the consumer's model:
release 3.1.0 renamed each list's Title, six derived lookups went on asking
for `Title`, and thirteen queries were blocked with nothing before Power BI
saying a word.
"""

import re
from collections.abc import Iterable
from collections.abc import Set as AbstractSet

from dbml_sharepoint.analysis.column_projection import (
    SYSTEM_COLUMN_TYPES as _SYSTEM_TYPES,
)
from dbml_sharepoint.analysis.lookups import display_column_for
from dbml_sharepoint.analysis.ordering import is_deployed_here
from dbml_sharepoint.analysis.report_columns import (
    DATE_ZONE_RESOLVED_COLUMN,
    ITEM_URL_COLUMN,
    ITEM_URL_RESOLVED_COLUMN,
    REPORT_FIXED_COLUMNS,
    REPORT_KEY_SUFFIX,
    REPORT_SYSTEM_COLUMNS,
    USERS_DISPLAY_TITLES,
    USERS_KEY_LIST,
    USERS_ROW_KEY,
    fk_key_column,
    person_key_column,
    report_output_names,
)
from dbml_sharepoint.analysis.typemap import is_person, map_column
from dbml_sharepoint.model.mapping_types import DerivedColumn, MappingBundle
from dbml_sharepoint.model.parser import Schema, Table

#: The M type token each declared type maps to, and so the vocabulary a
#: `derived_columns` entry may name. Deliberately small: every one of these
#: has an unambiguous M literal type, and a kind whose M shape nobody has
#: decided must not resolve to `type any` and load as an Error value in
#: every populated cell. The loader refuses a type outside it and the
#: generator reads the token off it, so the two cannot disagree.
DERIVED_TYPES: dict[str, str] = {
    "logical": "type logical",
    "text": "type text",
    "number": "type number",
    "Int64": "Int64.Type",
    "date": "type date",
    "datetime": "type datetime",
    "datetimezone": "type datetimezone",
}

#: What a `count` may ask of the child rows. `count` needs no column;
#: the other three name one.
DERIVED_AGGREGATES: frozenset[str] = frozenset(
    {"count", "min", "max", "names"},
)

#: A `[Column]` reference inside an `m` or a `where`. Column names may carry
#: spaces, because the pack's own added columns do (`Site Url`, `Risk Key`).
#: M has no other bracketed form at row level, and a literal `[` inside a
#: string would be a false positive that costs an author one rename rather
#: than a silent blank, which is the safer way round.
DERIVED_REFERENCE = re.compile(r"\[([^\[\]]+)\]")


def derived_references(text: str) -> tuple[str, ...]:
    """Every column an M fragment names, in order and without duplicates."""
    seen: dict[str, None] = {}
    for name in DERIVED_REFERENCE.findall(text):
        seen.setdefault(name, None)
    return tuple(seen)


def derived_output_names(entry: DerivedColumn) -> tuple[str, ...]:
    """The columns one entry ADDS to the query.

    A `replace` entry adds nothing: it overwrites a column that is already
    there, which is why it is not a collision with itself.
    """
    match entry.kind:
        case "expr":
            return () if entry.replace else (entry.name,)
        case "lookup":
            return tuple(entry.pick)
        case "count":
            return (entry.name,)
        case _:
            return ()


def target_entity(entry: DerivedColumn) -> str:
    """The entity a `lookup` or a `count` reads. Empty for an `expr`."""
    return entry.from_entity if entry.kind in {"lookup", "count"} else ""


def is_users_source(entry: DerivedColumn) -> bool:
    """Whether a `lookup` reads the users dimension rather than a list.

    `_Users` is the one source that is not an entity. A person column has no
    DBML ref to derive keys from, but the pack already gives it a `... Key`
    into `_Users` for exactly this join, so the shape is the same and only
    where the two key names come from differs.
    """
    return entry.kind == "lookup" and entry.from_entity == USERS_KEY_LIST


def lookup_key_columns(entry: DerivedColumn, entity: str) -> tuple[str, str]:
    """The (this side, other side) key columns one join matches on.

    Derived from the schema's own ref rather than declared, so a key spelled
    in a mapping cannot disagree with the key the query carries. A `lookup`
    matches this list's foreign key against the TARGET's row key; a `count`
    matches this list's row key against the CHILD's foreign key, which is the
    same join read from the other end.
    """
    if is_users_source(entry):
        return (person_key_column(entry.via), USERS_ROW_KEY)
    if entry.key:
        return (entry.key, f"{entry.from_entity}{REPORT_KEY_SUFFIX}")
    foreign = fk_key_column(f"{entry.via}Id")
    own = f"{entity}{REPORT_KEY_SUFFIX}"
    if entry.kind == "count":
        return (own, foreign)
    return (foreign, f"{entry.from_entity}{REPORT_KEY_SUFFIX}")


def users_column_names() -> frozenset[str]:
    """The internal names a `lookup` into `_Users` may pick."""
    return frozenset(USERS_DISPLAY_TITLES)


def report_column_names(
    table: Table,
    bundle: MappingBundle,
    enum_names: Iterable[str],
    *,
    include_derived: bool = True,
) -> tuple[str, ...]:
    """Every column the report query for one entity produces, in query order.

    INTERNAL names, which is what the query carries until its last step: the
    model-facing rename runs after everything here, so an author writing an
    `m` expression is writing against these.

    `test_reportgen` pins this against the columns a generated query really
    declares, for every shipped family, so the two cannot drift.
    """
    enum_names = set(enum_names)
    mapping = bundle.mapping
    cross_site_keys = bundle.mapping.cross_site_keys()
    names: list[str] = []
    person_columns: list[str] = []
    fk_keys: list[str] = []
    for col in table.columns:
        if (table.name, col.name) in cross_site_keys:
            continue
        sp = map_column(col, enum_names)
        lookup_display = display_column_for(
            mapping.entities.get(sp.target_list or ""),
        )
        names += report_output_names(
            sp, lookup_display=lookup_display,
            projections=tuple(mapping.projections_for(table.name, col.name)),
        )
        if sp.kind == "User":
            person_columns.append(sp.name)
        # A lookup carries a key into its target only where the target is
        # reported beside it, which is the same condition `_build_plans`
        # puts on the join.
        if sp.kind == "Lookup" and is_deployed_here(
            mapping.entities, sp.target_list or "",
            mapping.entities[table.name].site_role,
        ):
            fk_keys.append(fk_key_column(f"{sp.name}Id"))
    if mapping.reporting.system_columns:
        for name in REPORT_SYSTEM_COLUMNS:
            if is_person(_SYSTEM_TYPES[name]):
                names += [f"{name}Id", f"{name}Title"]
                person_columns.append(name)
            else:
                names.append(name)
    names += [ITEM_URL_COLUMN, ITEM_URL_RESOLVED_COLUMN]
    names += list(REPORT_FIXED_COLUMNS)
    names.append(f"{table.name}{REPORT_KEY_SUFFIX}")
    # A declared zone puts the flag on every list: the query reads the site's
    # zone to check it against the declaration whether or not a column here
    # needs converting, and the flag is where that answer surfaces.
    if mapping.reporting.time_zone is not None or _has_date_column(
        table, enum_names, cross_site_keys,
    ):
        names.append(DATE_ZONE_RESOLVED_COLUMN)
    names += fk_keys
    if mapping.reporting.users_table:
        names += [person_key_column(name) for name in person_columns]
    if include_derived:
        for entry in mapping.derived_for(table.name):
            names += derived_output_names(entry)
    return tuple(names)


def _has_date_column(
    table: Table,
    enum_names: set[str],
    cross_site_keys: AbstractSet[tuple[str, str]],
) -> bool:
    """Whether the query converts a date-only column, and so whether it reads
    the site's zone and carries the flag saying it did."""
    for col in table.columns:
        if (table.name, col.name) in cross_site_keys:
            continue
        sp = map_column(col, enum_names)
        if sp.kind == "DateTime" and sp.date_only:
            return True
        if sp.kind == "Calculated" and sp.output_type == 4:
            return True
    return False


def child_column_names(
    schema: Schema, bundle: MappingBundle, entity: str,
) -> tuple[str, ...]:
    """The columns another entity's query produces, for a `where` or a
    `column` that reads the CHILD rows rather than this list's."""
    table = next((t for t in schema.tables if t.name == entity), None)
    if table is None:
        return ()
    return report_column_names(
        table, bundle, {e.name for e in schema.enums},
    )
