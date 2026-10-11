# src/dbml_sharepoint/analysis/checks/_governance.py
"""Governance: every name and value the section uses resolves to something declared."""

from dataclasses import replace

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section


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
            f"{where.path}: {value!r} is not in governance.vocabulary.{vocabulary} "
            f"(the mapping declares {declared}).",
            location=where,
        ),
    ]


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
                f"{at.path}: {entity!r} is not an entity this mapping deploys from the schema.",
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
                f"{at.path}.retention: {spec.retention!r} is not a declared retention "
                f"policy (declared: {declared}).",
                location=replace(at, sub="retention"),
            ))
        # A retired column stays in the DBML, so table.columns is the declared set.
        declared_columns = {c.name for c in table.columns}
        for name, column in spec.columns.items():
            column_at = replace(at, column=name)
            if name not in declared_columns:
                findings.append(Finding(
                    FindingCode.GOVERNANCE_UNKNOWN_COLUMN,
                    f"{at.path}: {name!r} is not a column the schema declares for {entity}.",
                    location=column_at,
                ))
                continue
            findings += _outside(
                column_at, "personal_data", column.personal_data, vocabulary.personal_data,
            )
    return findings
