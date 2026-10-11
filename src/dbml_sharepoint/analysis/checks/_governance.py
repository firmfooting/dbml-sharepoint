# src/dbml_sharepoint/analysis/checks/_governance.py
"""Governance: every name and value the section uses resolves to something declared."""

from dataclasses import replace

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section


def _path(at: Location, sub: str | None = None) -> str:
    """The path as authored in the mapping, not `Location.path`'s `governance[Risk]`."""
    path = f"governance.lists.{at.entity}"
    if at.column is not None:
        path += f".columns.{at.column}"
    return f"{path}.{sub}" if sub else path


def _outside(
    at: Location, field: str, value: str | None, allowed: tuple[str, ...],
) -> list[Finding]:
    """A finding when `value` is set and not in `allowed`; exact comparison, no folding."""
    if value is None or value in allowed:
        return []
    declared = ", ".join(repr(v) for v in allowed) if allowed else "none"
    vocabulary = "owners" if field == "owner" else field
    where = replace(at, sub=field)
    return [
        Finding(
            FindingCode.GOVERNANCE_VALUE_OUTSIDE_VOCABULARY,
            f"{_path(at, field)}: {value!r} is not in governance.vocabulary.{vocabulary} "
            f"(the mapping declares {declared}).",
            location=where,
        ),
    ]


def _conflicting_default(
    vc: ValidationContext, entity: str, retention: str | None, at: Location,
) -> list[Finding]:
    """A finding when the list's file default names a different policy than governance."""
    if retention is None:
        return []
    defaults = vc.bundle.retention_list_defaults
    # The file may key a list by entity name or by its prefixed title, as the manifest accepts.
    for key in dict.fromkeys((entity, vc.bundle.mapping.list_title(entity))):
        default = defaults.get(key)
        if default is not None and default != retention:
            return [
                Finding(
                    FindingCode.GOVERNANCE_RETENTION_CONFLICTS_WITH_DEFAULT,
                    f"{_path(at, 'retention')}: {retention!r} conflicts with the policy "
                    f"{default!r} that retention list_defaults sets for {key!r}.",
                    location=replace(at, sub="retention"),
                ),
            ]
    return []


def check(vc: ValidationContext) -> list[Finding]:
    bundle = vc.bundle
    vocabulary = bundle.governance.vocabulary
    findings: list[Finding] = []
    for entity, spec in bundle.governance.lists.items():
        at = Location(Section.GOVERNANCE, entity=entity)
        table = vc.tables_by_name.get(entity)
        if table is None or entity not in bundle.mapping.entities:
            findings.append(Finding(
                FindingCode.GOVERNANCE_UNKNOWN_ENTITY,
                f"{_path(at)}: {entity!r} is not an entity this mapping deploys from the schema.",
                location=at,
            ))
            continue
        findings += _outside(at, "owner", spec.owner, vocabulary.owners)
        findings += _outside(at, "classification", spec.classification, vocabulary.classification)
        findings += _outside(at, "personal_data", spec.personal_data, vocabulary.personal_data)
        if spec.retention is not None and spec.retention not in bundle.retention_policies:
            declared = (
                ", ".join(repr(name) for name in bundle.retention_policies)
                if bundle.retention_policies
                else "none (the mapping loads no retention_policies_source, or it defines none)"
            )
            findings.append(Finding(
                FindingCode.GOVERNANCE_UNKNOWN_RETENTION_POLICY,
                f"{_path(at, 'retention')}: {spec.retention!r} is not a declared retention "
                f"policy (declared: {declared}).",
                location=replace(at, sub="retention"),
            ))
        findings += _conflicting_default(vc, entity, spec.retention, at)
        # A retired column stays in the DBML, so table.columns is the declared set.
        declared_columns = {c.name for c in table.columns}
        for name, column in spec.columns.items():
            column_at = replace(at, column=name)
            if name not in declared_columns:
                findings.append(Finding(
                    FindingCode.GOVERNANCE_UNKNOWN_COLUMN,
                    f"{_path(column_at)}: {name!r} is not a column the schema declares "
                    f"for {entity}.",
                    location=column_at,
                ))
                continue
            findings += _outside(
                column_at, "personal_data", column.personal_data, vocabulary.personal_data,
            )
    return findings
