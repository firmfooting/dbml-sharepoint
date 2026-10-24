# src/dbml_sharepoint/analysis/checks/_lists_forms.py
"""`lists-forms.yaml`: questions a Lists form cannot honour.

A Lists form shows and accepts every column it names, whatever the list's
own form does, so these rules refuse a question that would let a respondent
write what the list keeps from them, or leave them unable to submit.
"""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.rendered_columns import rendered_columns
from dbml_sharepoint.analysis.typemap import SPField, map_column
from dbml_sharepoint.model.mapping_types import ListsForm, ListsFormQuestion
from dbml_sharepoint.model.parser import Table

#: Columns a question may name although the DBML need not declare them.
_PLATFORM_COLUMNS = frozenset({"Title", "Attachments"})


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    mapping = vc.bundle.mapping
    for entity, declared in vc.bundle.lists_forms.items():
        at = Location(Section.LISTS_FORMS, entity=entity)
        table = vc.tables_by_name.get(entity)
        entity_mapping = mapping.entities.get(entity)
        if table is None or entity_mapping is None:
            findings.append(Finding(
                FindingCode.UNKNOWN_ENTITY, f"lists_forms[{entity}]: unknown entity.",
                location=at,
            ))
            continue
        if entity_mapping.is_library:
            findings.append(Finding(
                FindingCode.LISTS_FORM_ON_DOCUMENT_LIBRARY,
                f"lists_forms[{entity}]: {entity} is a document library, which "
                f"cannot give a Lists form to respondents. Collect the answers in a list.",
                location=at,
            ))
            continue
        if entity in mapping.list_validation:
            findings.append(Finding(
                FindingCode.LISTS_FORM_LIST_VALIDATION_IS_SILENT,
                f"lists_forms[{entity}]: {entity} declares list_validation, and a "
                f"Lists form hides its message when the rule fails.",
                location=at,
            ))
        fields = _fields(vc, table)
        for i, form in enumerate(declared.forms):
            findings += _form(vc, table, fields, i, form)
    return findings


def _fields(vc: ValidationContext, table: Table) -> dict[str, SPField]:
    """The rendered DBML columns that map, by name."""
    rendered = rendered_columns(table, vc.cross_site_columns(table.name))
    enum_names = set(vc.enum_by_name)
    fields: dict[str, SPField] = {}
    for col in table.columns:
        if col.name not in rendered:
            continue
        try:
            fields[col.name] = map_column(col, enum_names)
        except ValueError:
            # An unresolvable type, which `validate_column` reports on its own.
            continue
    return fields


def _form(
    vc: ValidationContext, table: Table, fields: dict[str, SPField], i: int, form: ListsForm,
) -> list[Finding]:
    findings: list[Finding] = []
    entity = table.name
    asked: set[str] = set()
    for j, question in enumerate(form.questions):
        at = Location(Section.LISTS_FORMS, entity=entity, sub=f"forms[{i}].questions[{j}]")
        if question.column in asked:
            findings.append(Finding(
                FindingCode.LISTS_FORM_QUESTION_REPEATED,
                f"{at.path}: {question.column!r} is already a question on this form.",
                location=at,
            ))
            continue
        asked.add(question.column)
        findings += _question(vc, table, fields, at, question)
    retired = vc.bundle.mapping.retired_columns.get(entity, {})
    formulas = vc.bundle.mapping.default_formulas.get(entity, {})
    required = [
        name for name, sp in fields.items()
        if sp.required and sp.default is None and name not in formulas and name not in retired
    ]
    # Core leaves an undeclared Title as the platform made it: required.
    if "Title" not in {c.name for c in table.columns}:
        required.insert(0, "Title")
    at = Location(Section.LISTS_FORMS, entity=entity, sub=f"forms[{i}]")
    findings += [
        Finding(
            FindingCode.LISTS_FORM_REQUIRED_COLUMN_MISSING,
            f"{at.path}: {entity} requires {name!r} with no default, and the form "
            f"does not ask for it. Add the question or give the column a default.",
            location=at,
        )
        for name in required if name not in asked
    ]
    return findings


def _question(
    vc: ValidationContext,
    table: Table,
    fields: dict[str, SPField],
    at: Location,
    question: ListsFormQuestion,
) -> list[Finding]:
    entity, name = table.name, question.column
    mapping = vc.bundle.mapping
    # Asked before "unknown": a projection is not a DBML column, yet the mistake is the kind.
    if (
        name == "ContentType"
        or name in vc.calculated_by_entity.get(entity, set())
        or name in vc.projected_columns(entity)
    ):
        return [Finding(
            FindingCode.LISTS_FORM_QUESTION_NOT_OFFERED,
            f"{at.path}: a Lists form never shows {name!r}, a calculated column, the "
            f"content type or a projected lookup field. Remove the question.",
            location=at,
        )]
    known = rendered_columns(table, vc.cross_site_columns(entity)) | _PLATFORM_COLUMNS
    if name not in known or name in mapping.retired_columns.get(entity, {}):
        return [Finding(
            FindingCode.LISTS_FORM_COLUMN_UNKNOWN,
            f"{at.path}: {name!r} is not a column of {entity}, or it is retired.",
            location=at,
        )]
    findings: list[Finding] = []
    section = mapping.form_visibility.get(entity)
    visibility = section.columns.get(name) if section is not None else None
    if visibility is not None and (not visibility.new or visibility.when is not None):
        findings.append(Finding(
            FindingCode.LISTS_FORM_QUESTION_HIDDEN_ON_LIST_FORM,
            f"{at.path}: {name!r} is hidden or shown conditionally on the list's own "
            f"new form, and a Lists form would show it to every respondent.",
            location=at,
        ))
    if question.sets_column:
        findings.append(Finding(
            FindingCode.LISTS_FORM_QUESTION_SETS_COLUMN,
            f"{at.path}: {', '.join(question.sets_column)} belongs to the column. "
            f"Declare `not null`, or `date` against `datetime`, in the DBML.",
            location=at,
        ))
    if name == "Attachments" and not mapping.attachments:
        findings.append(Finding(
            FindingCode.LISTS_FORM_ATTACHMENTS_OFF,
            f"{at.path}: {entity} declares `attachments: false`, so the list takes no "
            f"attachments.",
            location=at,
        ))
    sp = fields.get(name)
    if sp is None:
        return findings
    if sp.kind in {"Lookup", "LookupMulti"} and not question.respondents_read_source:
        findings.append(Finding(
            FindingCode.LISTS_FORM_LOOKUP_SOURCE_UNREADABLE,
            f"{at.path}: {name!r} is a lookup, and a respondent who cannot read "
            f"{sp.target_list} sees no options. Declare `respondents_read_source: true` "
            f"only when every respondent can read it.",
            location=at,
        ))
    if sp.rich_text:
        findings.append(Finding(
            FindingCode.LISTS_FORM_RICH_TEXT_IS_PLAIN,
            f"{at.path}: {name!r} is rich text, which a Lists form asks for in a plain box.",
            location=at,
        ))
    return findings
