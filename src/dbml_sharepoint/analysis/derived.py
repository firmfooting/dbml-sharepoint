"""Derived reporting columns: what each one contributes, and what it reads.

Reporting-only columns declared under `derived_columns`. Nothing here is
deployed: no SharePoint field is created, nothing is read back, and a list
carries no trace of one. They exist in the generated Power Query and nowhere
else.

SHARED because two sides need the same facts and must not drift.
`reporting/plan` resolves each entry into a step and `generators/report_m`
emits it; `checks/_derived` refuses a declaration that names a column the
query does not produce, reading `plan.report_column_names` for what it does
produce. `AGENTS.md` is explicit that such a fact lives in a shared module,
and that a generator must never import from `analysis/checks/`.

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

from dbml_sharepoint.analysis.report_columns import (
    REPORT_KEY_SUFFIX,
    USERS_DISPLAY_TITLES,
    USERS_KEY_LIST,
    USERS_ROW_KEY,
    fk_key_column,
    person_key_column,
)
from dbml_sharepoint.model.mapping_types import DerivedColumn

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
