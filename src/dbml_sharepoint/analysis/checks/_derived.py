# src/dbml_sharepoint/analysis/checks/_derived.py
"""Derived reporting columns: their names, their joins and their references.

Reporting-only columns are the one declaration in this mapping that NOTHING
downstream verifies. A deployed column is created, read back and reconciled;
a derived column is a string that becomes M, and the first thing that reads
it is Power BI, at refresh, in front of whoever published the model. So the
rules here are the only place a mistake can be caught at all.

The reference rule is the one that earns its keep. `derived.py` records the
run: release 3.1.0 renamed each list's Title, six derived lookups went on
asking for `Title`, and thirteen queries were blocked behind the failure.
"""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.derived import (
    derived_output_names,
    derived_references,
    is_users_source,
    lookup_key_columns,
    users_column_names,
)
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.report_columns import USERS_KEY_LIST
from dbml_sharepoint.analysis.reporting.plan import report_column_names
from dbml_sharepoint.analysis.typemap import is_person
from dbml_sharepoint.model.mapping_types import DerivedColumn
from dbml_sharepoint.model.parser import Table


def check(vc: ValidationContext) -> list[Finding]:
    return _derived_columns(vc)


def _at(entity: str, sub: str = "") -> Location:
    return Location(
        Section.DERIVED_COLUMNS, entity=entity, sub=sub or None,
    )


def _lookup_target(table: Table, via: str) -> str | None:
    """The entity `via` points at, or None when it is not a lookup here."""
    col = next((c for c in table.columns if c.name == via), None)
    if col is None or col.ref is None:
        return None
    return col.ref.target_table


def _produced(vc: ValidationContext, entity: str) -> set[str] | None:
    """Every column `entity`'s report query produces, or None where no query
    exists for it at any site."""
    plan = vc.report_plan(entity)
    return None if plan is None else set(report_column_names(plan))


def _derived_columns(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    bundle = vc.bundle
    for entity, entries in bundle.mapping.derived_columns.items():
        if entity not in vc.table_names:
            findings.append(Finding(
                FindingCode.DERIVED_UNKNOWN_ENTITY,
                f"derived_columns: entity {entity} not in schema",
                location=_at(entity),
            ))
            continue
        table = vc.tables_by_name[entity]
        plan = vc.report_plan(entity)
        if plan is None:
            # No query for this entity at any site (`_structure` reports the
            # missing mapping entry), or a role the planner refused, whose
            # causes each have a rule of their own. Nothing to check against.
            continue
        # The columns the query carries WITHOUT any derived one, so each
        # entry below is checked against what exists at the point it runs
        # rather than against the finished table. Declaration order is the
        # contract: an entry may read what an entry above it produced and
        # must not read what one below it will.
        available = set(report_column_names(plan, include_derived=False))
        for index, entry in enumerate(entries):
            findings += _one(vc, entity, table, entry, index, available)
            available.update(derived_output_names(entry))
    return findings


def _one(
    vc: ValidationContext,
    entity: str,
    table: Table,
    entry: DerivedColumn,
    index: int,
    available: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    where = f"derived_columns.{entity}[{index}]"
    for name in derived_output_names(entry):
        if name in available:
            findings.append(Finding(
                FindingCode.DERIVED_NAME_COLLIDES,
                f"{where}: {name!r} is already a column of this list's "
                f"report query. A derived column is ADDED, so a name that "
                f"is taken fails the refresh rather than overwriting it. "
                f"Rename it, or set `replace: true` to compute over the "
                f"column that is there.",
                location=_at(entity, name),
            ))
    if entry.kind == "expr":
        findings += _expr(entry, entity, where, available)
        return findings
    if entry.kind == "lookup":
        findings += _lookup(vc, entity, table, entry, where, available)
        return findings
    findings += _count(vc, entity, entry, where)
    return findings


def _expr(
    entry: DerivedColumn, entity: str, where: str, available: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    if entry.replace and entry.name not in available:
        findings.append(Finding(
            FindingCode.DERIVED_UNKNOWN_REFERENCE,
            f"{where}: `replace: true` overwrites {entry.name!r}, which "
            f"this list's report query does not produce. A replace over a "
            f"column that is not there fails the refresh; drop the flag to "
            f"add the column instead.",
            location=_at(entity, entry.name),
        ))
    findings += _references(
        entry.m, available, entity, where, entry.name or "m",
        subject="this list's report query",
    )
    return findings


def _lookup(
    vc: ValidationContext,
    entity: str,
    table: Table,
    entry: DerivedColumn,
    where: str,
    available: set[str],
) -> list[Finding]:
    findings: list[Finding] = []
    if is_users_source(entry):
        return _users_lookup(vc, entity, table, entry, where, available)
    if entry.key:
        # A chained join: the key was computed by an entry above rather than
        # derived from a ref, so the only thing to check is that it is
        # really there by the time this entry runs.
        if entry.key not in available:
            return [Finding(
                FindingCode.DERIVED_UNKNOWN_REFERENCE,
                f"{where}: key {entry.key!r} is not a column this list's "
                f"report query carries at this point. A `key` join reads a "
                f"column produced ABOVE it; declaration order is what makes "
                f"one available.",
                location=_at(entity, entry.key),
            )]
        if entry.from_entity not in vc.table_names:
            return [Finding(
                FindingCode.DERIVED_LOOKUP_BAD_TARGET,
                f"{where}: from {entry.from_entity!r} is not in the schema.",
                location=_at(entity, entry.from_entity),
            )]
        return _picks(vc, entity, entry, where, entry.from_entity)
    target = _lookup_target(table, entry.via)
    if target is None:
        return [Finding(
            FindingCode.DERIVED_LOOKUP_BAD_TARGET,
            f"{where}: via {entry.via!r} is not a lookup column of "
            f"{entity}. The join matches this list's {entry.via!r} key "
            f"against the target's row key, so it needs a DBML ref to "
            f"build either of them.",
            location=_at(entity, entry.via),
        )]
    if target != entry.from_entity:
        return [Finding(
            FindingCode.DERIVED_LOOKUP_BAD_TARGET,
            f"{where}: via {entry.via!r} points at {target}, not at "
            f"{entry.from_entity!r}. The two must agree: the key columns "
            f"come from the ref and the query read comes from `from`, so a "
            f"disagreement joins one list against another list's keys and "
            f"matches nothing.",
            location=_at(entity, entry.via),
        )]
    own_key, _target_key = lookup_key_columns(entry, entity)
    if own_key not in available:
        # The query carries a key into a lookup's target only where that
        # target is reported beside it, which is the same condition
        # `_build_plans` puts on the join.
        return [_unreported_target(entity, where, entry.from_entity)]
    return findings + _picks(vc, entity, entry, where, target)


def _picks(
    vc: ValidationContext,
    entity: str,
    entry: DerivedColumn,
    where: str,
    target: str,
) -> list[Finding]:
    """Every column a `lookup` takes must be one the target query produces."""
    target_columns = _produced(vc, target)
    if target_columns is None:
        return [_unreported_target(entity, where, target)]
    return [
        Finding(
            FindingCode.DERIVED_UNKNOWN_REFERENCE,
            f"{where}: pick {new_name!r} reads {source!r}, which "
            f"{target}'s report query does not produce. Name the "
            f"column as the SCHEMA declares it; the generator "
            f"translates it to whatever that query renames it to.",
            location=_at(entity, new_name),
        )
        for new_name, source in entry.pick.items()
        if source not in target_columns
    ]


def _users_lookup(
    vc: ValidationContext,
    entity: str,
    table: Table,
    entry: DerivedColumn,
    where: str,
    available: set[str],
) -> list[Finding]:
    """A `lookup` into `_Users`, which joins a PERSON column's key."""
    column = next((c for c in table.columns if c.name == entry.via), None)
    if column is None or not is_person(column.type):
        return [Finding(
            FindingCode.DERIVED_LOOKUP_BAD_TARGET,
            f"{where}: reading {USERS_KEY_LIST} joins a PERSON column's "
            f"key, and via {entry.via!r} is not a person column of "
            f"{entity}.",
            location=_at(entity, entry.via),
        )]
    if not vc.bundle.mapping.reporting.users_table:
        return [Finding(
            FindingCode.DERIVED_LOOKUP_BAD_TARGET,
            f"{where}: reading {USERS_KEY_LIST} needs "
            f"`reporting.users_table: true`. Without it the pack emits no "
            f"users dimension and no person key to join it on, so this "
            f"join has neither side.",
            location=_at(entity, entry.via),
        )]
    own_key, _ = lookup_key_columns(entry, entity)
    if own_key not in available:
        return [_unreported_target(entity, where, USERS_KEY_LIST)]
    known = users_column_names()
    return [
        Finding(
            FindingCode.DERIVED_UNKNOWN_REFERENCE,
            f"{where}: pick {new_name!r} reads {source!r}, which "
            f"{USERS_KEY_LIST} does not carry. Its columns are "
            f"{', '.join(sorted(known))}.",
            location=_at(entity, new_name),
        )
        for new_name, source in entry.pick.items()
        if source not in known
    ]


def _count(
    vc: ValidationContext,
    entity: str,
    entry: DerivedColumn,
    where: str,
) -> list[Finding]:
    findings: list[Finding] = []
    child = vc.tables_by_name.get(entry.from_entity)
    if child is None:
        return [Finding(
            FindingCode.DERIVED_COUNT_BAD_SOURCE,
            f"{where}: from {entry.from_entity!r} is not in the schema, so "
            f"there are no child rows to aggregate.",
            location=_at(entity, entry.from_entity),
        )]
    target = _lookup_target(child, entry.via)
    if target != entity:
        return [Finding(
            FindingCode.DERIVED_COUNT_BAD_SOURCE,
            f"{where}: {entry.from_entity}.{entry.via} "
            + (
                "is not a lookup column" if target is None
                else f"points at {target}"
            )
            + f", so it cannot group {entry.from_entity} rows against "
            f"{entity}. A count reads the join from the CHILD's end: `via` "
            f"is the child's column that points back here.",
            location=_at(entity, entry.via),
        )]
    child_columns = _produced(vc, entry.from_entity)
    if child_columns is None:
        return [_unreported_target(entity, where, entry.from_entity)]
    _own_key, child_key = lookup_key_columns(entry, entity)
    if child_key not in child_columns:
        return [_unreported_target(entity, where, entry.from_entity)]
    if entry.column and entry.column not in child_columns:
        findings.append(Finding(
            FindingCode.DERIVED_UNKNOWN_REFERENCE,
            f"{where}: aggregate {entry.aggregate} reads "
            f"{entry.column!r}, which {entry.from_entity}'s report query "
            f"does not produce.",
            location=_at(entity, entry.name),
        ))
    # A `where` filters the CHILD rows, so it resolves against the child's
    # columns and not this list's. Reading it against the wrong table is how
    # a filter silently matches nothing and the count reads zero.
    findings += _references(
        entry.where, child_columns, entity, where, entry.name,
        subject=f"{entry.from_entity}'s report query",
    )
    return findings


def _unreported_target(entity: str, where: str, target: str) -> Finding:
    return Finding(
        FindingCode.DERIVED_LOOKUP_BAD_TARGET,
        f"{where}: {target} is not reported beside {entity}, so this "
        f"list's query carries no key into it and there is nothing to "
        f"join on. Both entities must be deployed to the same site role.",
        location=_at(entity, target),
    )


def _references(
    text: str,
    available: set[str],
    entity: str,
    where: str,
    subject_name: str,
    *,
    subject: str,
) -> list[Finding]:
    """Every `[Column]` an M fragment names must be a column that exists.

    THE RULE THIS MODULE EXISTS FOR. Nothing between here and Power BI reads
    these strings, so an unresolved name is not a build failure, not a pack
    failure and not a load failure. It is a refresh failure, after
    publication, and it takes every query queued behind it.
    """
    return [
        Finding(
            FindingCode.DERIVED_UNKNOWN_REFERENCE,
            f"{where}: {subject_name!r} reads [{name}], which {subject} "
            f"does not produce. Column names here are the INTERNAL names "
            f"the schema declares, not the display titles the model shows.",
            location=Location(
                Section.DERIVED_COLUMNS, entity=entity, sub=name,
            ),
        )
        for name in derived_references(text)
        if name not in available
    ]
