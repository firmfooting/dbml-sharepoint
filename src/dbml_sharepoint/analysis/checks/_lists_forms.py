# src/dbml_sharepoint/analysis/checks/_lists_forms.py
"""`lists-forms.yaml`: questions and text a Lists form cannot honour.

A Lists form shows and accepts every column it names, whatever the list's
own form does, so these rules refuse a question that would let a respondent
write what the list keeps from them, or leave them unable to submit. They
also refuse a title, text, link or schedule the form cannot show as written.
"""

import re
from datetime import datetime

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.rendered_columns import rendered_columns
from dbml_sharepoint.analysis.typemap import SPField, map_column
from dbml_sharepoint.model.mapping_types import EntityListsForms, ListsForm, ListsFormQuestion
from dbml_sharepoint.model.parser import Table

TITLE_MAX = 80
DESCRIPTION_MAX = 1260
MESSAGE_MAX = 300

_LINK_MARKUP = re.compile(r"(?<!!)\[[^\]\n]*\]\([^)\s]*\)|<a\s", re.IGNORECASE)
# A `www.` inside an `https://` URL or its path is not a bare address.
_NOT_HTTPS = re.compile(r"http://|mailto:|(?<![\w./])www\.", re.IGNORECASE)
_IMAGE = re.compile(r"!\[[^\]\n]*\]\(|<img", re.IGNORECASE)
_URL = re.compile(r"https://|http://|www\.|mailto:", re.IGNORECASE)

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
        findings += _titles(entity, declared)
        for i, form in enumerate(declared.forms):
            findings += _form(vc, table, fields, i, form)
            findings += _text(entity, i, form)
            findings += _schedule(entity, i, form)
    return findings


def _titles(entity: str, declared: EntityListsForms) -> list[Finding]:
    """Titles identify forms on redeploy, so each must be one valid line and unique."""
    findings: list[Finding] = []
    seen: set[str] = set()
    for i, form in enumerate(declared.forms):
        at = Location(Section.LISTS_FORMS, entity=entity, sub=f"forms[{i}]")
        title = form.title
        problems = []
        if not title.strip():
            problems.append("the title is empty")
        if "\n" in title or "\r" in title:
            problems.append("the title holds a line break")
        if len(title) > TITLE_MAX:
            problems.append(f"the title is longer than {TITLE_MAX} characters")
        names = {title, *form.previous_titles}
        problems += [
            f"{name!r} is already a title or previous title of an earlier form"
            for name in sorted(names & seen)
        ]
        problems += [
            f"previous title {name!r} is also in `retired`"
            for name in sorted(set(form.previous_titles) & set(declared.retired))
        ]
        seen |= names
        findings += [
            Finding(FindingCode.LISTS_FORM_TITLE_INVALID, f"{at.path}: {problem}.", location=at)
            for problem in problems
        ]
        if title in declared.retired:
            findings.append(Finding(
                FindingCode.LISTS_FORM_RETIRED_AND_DECLARED,
                f"{at.path}: {title!r} is also in `retired`, which deletes it on deploy.",
                location=at,
            ))
    return findings


def _text(entity: str, i: int, form: ListsForm) -> list[Finding]:
    findings: list[Finding] = []
    at = Location(Section.LISTS_FORMS, entity=entity, sub=f"forms[{i}]")
    for key, text, limit in (
        ("description", form.description, DESCRIPTION_MAX),
        ("thank_you", form.thank_you or "", MESSAGE_MAX),
        ("closed_message", form.closed_message or "", MESSAGE_MAX),
    ):
        if len(text) > limit:
            findings.append(Finding(
                FindingCode.LISTS_FORM_TEXT_TOO_LONG,
                f"{at.path}: `{key}` is {len(text)} characters, over the {limit} the "
                f"form designer keeps.",
                location=at,
            ))
    texts = [
        (at, "title", form.title),
        (at, "description", form.description),
        (at, "thank_you", form.thank_you or ""),
        (at, "closed_message", form.closed_message or ""),
    ]
    for j, question in enumerate(form.questions):
        q_at = Location(Section.LISTS_FORMS, entity=entity, sub=f"forms[{i}].questions[{j}]")
        texts += [(q_at, "label", question.label or ""), (q_at, "help", question.help)]
    for where, key, text in texts:
        if key in {"description", "help"} and _LINK_MARKUP.search(text):
            findings.append(Finding(
                FindingCode.LISTS_FORM_LINK_MARKUP,
                f"{where.path}: `{key}` holds Markdown or HTML link markup, which a "
                f"Lists form shows as text. Write the bare `https://` URL.",
                location=where,
            ))
        if key in {"description", "help"} and _NOT_HTTPS.search(text):
            findings.append(Finding(
                FindingCode.LISTS_FORM_LINK_NOT_HTTPS,
                f"{where.path}: `{key}` holds a `www.`, `mailto:` or `http://` address, "
                f"which a Lists form does not link. Write the full `https://` URL.",
                location=where,
            ))
        if _IMAGE.search(text):
            findings.append(Finding(
                FindingCode.LISTS_FORM_IMAGE_IN_TEXT,
                f"{where.path}: `{key}` holds Markdown or HTML image markup, and a "
                f"Lists form draws no image inside text.",
                location=where,
            ))
        if key in {"thank_you", "closed_message"} and _URL.search(text):
            findings.append(Finding(
                FindingCode.LISTS_FORM_LINK_IN_MESSAGE,
                f"{where.path}: `{key}` holds a URL, which the form shows as plain "
                f"text. Put the link in the description.",
                location=where,
            ))
    return findings


def _schedule(entity: str, i: int, form: ListsForm) -> list[Finding]:
    at = Location(Section.LISTS_FORMS, entity=entity, sub=f"forms[{i}]")
    findings: list[Finding] = []
    times: dict[str, datetime] = {}
    for key, text in (("opens", form.opens), ("closes", form.closes)):
        if text is None:
            continue
        try:
            when = datetime.fromisoformat(text)
        except ValueError:
            when = None
        if when is None or when.utcoffset() is None:
            findings.append(Finding(
                FindingCode.LISTS_FORM_SCHEDULE_INVALID,
                f"{at.path}: `{key}` {text!r} is not an ISO 8601 time with an offset, "
                f"such as \"2026-11-02T09:00:00+11:00\".",
                location=at,
            ))
        else:
            times[key] = when
    if len(times) == 2 and times["closes"] <= times["opens"]:
        findings.append(Finding(
            FindingCode.LISTS_FORM_SCHEDULE_INVALID,
            f"{at.path}: `closes` is not after `opens`.",
            location=at,
        ))
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
            f"{at.path}: the column, not the form, holds "
            f"{' and '.join(f'`{key}`' for key in question.sets_column)}. "
            f"Declare `not null`, or `date` against `datetime`, in the DBML.",
            location=at,
        ))
    if name == "Attachments" and not mapping.attachments:
        findings.append(Finding(
            FindingCode.LISTS_FORM_ATTACHMENTS_OFF,
            f"{at.path}: the mapping declares `attachments: false`, so {entity} takes "
            f"no attachments.",
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
