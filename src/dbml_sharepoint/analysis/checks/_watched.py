# src/dbml_sharepoint/analysis/checks/_watched.py
"""The uses declared on a watched column.

Core checks the name's and id's spelling, that each can be told apart, that
`enter` and `leave` have a condition, and that the condition fits the schema.
Which use names exist is the consumer's question.
"""

import re
from collections import Counter

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.column_projection import effective_column_types
from dbml_sharepoint.analysis.conditions import condition_findings
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.rendered_columns import rendered_columns

USE_NAME = re.compile(r"[a-z][a-z0-9-]*")


def check(vc: ValidationContext) -> list[Finding]:
    return [*_names_and_conditions(vc), *_identities(vc)]


def _at(i: int, j: int) -> Location:
    return Location(Section.WATCHED_LISTS, sub=f"[{i}].uses[{j}]")


def _names_and_conditions(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for i, watched in enumerate(vc.bundle.mapping.watched_lists):
        for j, use in enumerate(watched.uses):
            at = _at(i, j)
            if not USE_NAME.fullmatch(use.name):
                findings.append(Finding(
                    FindingCode.WATCH_USE_NAME_INVALID,
                    f"{at.path}: use name {use.name!r} must be lowercase letters, digits "
                    f"and hyphens, starting with a letter.",
                    location=at,
                ))
            # An id names what the consumer builds, so it takes the name's spelling.
            if use.id is not None and not USE_NAME.fullmatch(use.id):
                findings.append(Finding(
                    FindingCode.WATCH_USE_ID_INVALID,
                    f"{at.path}: id {use.id!r} must be lowercase letters, digits and hyphens, "
                    f"starting with a letter.",
                    location=at,
                ))
            if use.on in {"enter", "leave"} and use.when is None:
                findings.append(Finding(
                    FindingCode.WATCH_USE_WHEN_REQUIRED,
                    f"{at.path}: 'on: {use.on}' needs a 'when' saying which values of "
                    f"{watched.column!r} it {use.on}s.",
                    location=at,
                ))
        findings.extend(_conditions(vc, i))
    return findings


def _conditions(vc: ValidationContext, i: int) -> list[Finding]:
    """Each `when` against the watched entity's schema, once the column is known to render."""
    watched = vc.bundle.mapping.watched_lists[i]
    table = vc.tables_by_name.get(watched.entity)
    if table is None:
        return []
    xcols = vc.cross_site_columns(watched.entity)
    # _structure reports an unknown entity, or a column outside this set, as unrendered.
    if watched.column not in rendered_columns(table, xcols):
        return []
    projected = vc.projected_columns(watched.entity)
    rendered = rendered_columns(table, xcols, projected)
    types = effective_column_types({c.name: c.type for c in table.columns}, xcols, projected)
    lookups = {c.name for c in table.columns if c.ref is not None}
    findings: list[Finding] = []
    for j, use in enumerate(watched.uses):
        if use.when is None:
            continue
        findings.extend(condition_findings(
            use.when,
            target=None,
            rendered=rendered,
            types=types,
            lookups=lookups,
            enum_members=vc.enum_members_by_name,
            at=Location(Section.WATCHED_LISTS, sub=f"[{i}].uses[{j}].when"),
        ))
    return findings


def _identities(vc: ValidationContext) -> list[Finding]:
    """Per entity, across every watched column of it: ids unique, and a repeated name needs one."""
    placed: dict[str, list[tuple[Location, str, str | None]]] = {}
    for i, watched in enumerate(vc.bundle.mapping.watched_lists):
        for j, use in enumerate(watched.uses):
            placed.setdefault(watched.entity, []).append((_at(i, j), use.name, use.id))
    findings: list[Finding] = []
    for entity, uses in placed.items():
        names = Counter(name for _, name, _ in uses)
        first_with_id: dict[str, Location] = {}
        for at, name, use_id in uses:
            if use_id is None:
                if names[name] > 1:
                    findings.append(Finding(
                        FindingCode.WATCH_USE_REPEATED_WITHOUT_ID,
                        f"{at.path}: {name!r} is used {names[name]} times on {entity}, so "
                        f"each needs an 'id'.",
                        location=at,
                    ))
                continue
            first = first_with_id.setdefault(use_id, at)
            if first is not at:
                findings.append(Finding(
                    FindingCode.WATCH_USE_ID_DUPLICATE,
                    f"{at.path}: id {use_id!r} is already used on {entity} by {first.path}.",
                    location=at,
                ))
    return findings
