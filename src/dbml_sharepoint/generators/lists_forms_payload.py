"""The Lists forms payload deploy, assess and verify read, one spelling for all three."""

from datetime import UTC, datetime
from typing import Literal

from dbml_sharepoint.analysis.typemap import map_column
from dbml_sharepoint.generators.schema_types import (
    ListsFormQuestionRow,
    ListsFormRow,
    ListsFormsRow,
)
from dbml_sharepoint.model.mapping_types import ListsForm, ListsFormQuestion, MappingBundle
from dbml_sharepoint.model.parser import Column, Schema

# The designer's create default (`lists-forms.api.create`); an empty string is unmeasured.
PLATFORM_THANK_YOU = "Your response has been submitted!"

# Enforced only when declared: an absent key leaves the site's value to the owner.
type OperationalKey = Literal["accepting_responses", "closed_message", "opens", "closes"]
OPERATIONAL_KEYS: tuple[OperationalKey, ...] = (
    "accepting_responses", "closed_message", "opens", "closes",
)

# SharePoint's `DisplayFormat`: 0 is date only, 1 is date and time.
_DISPLAY_FORMAT = {"date": 0, "datetime": 1}


def utc_text(value: str) -> str:
    """Aware ISO text as UTC with milliseconds and a `Z`, as JavaScript `toISOString` writes it."""
    when = datetime.fromisoformat(value).astimezone(UTC)
    return when.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def lists_forms_payload(
    bundle: MappingBundle, schema: Schema, table_name: str,
) -> ListsFormsRow | None:
    """The entity's declared Lists forms and retired titles, or None when it declares none."""
    declared = bundle.lists_forms.get(table_name)
    if declared is None:
        return None
    table = next(t for t in schema.tables if t.name == table_name)
    columns = {c.name: c for c in table.columns}
    enum_names = {e.name for e in schema.enums}
    return {
        "list": bundle.mapping.list_title(table_name),
        "forms": [
            _form_row(bundle, table_name, form, columns, enum_names) for form in declared.forms
        ],
        "retired": list(declared.retired),
    }


def _form_row(
    bundle: MappingBundle, table_name: str, form: ListsForm,
    columns: dict[str, Column], enum_names: set[str],
) -> ListsFormRow:
    row: ListsFormRow = {
        "title": form.title,
        "previous_titles": list(form.previous_titles),
        "description": form.description,
        "questions": [
            _question_row(bundle, table_name, question, columns, enum_names)
            for question in form.questions
        ],
        "thank_you": form.thank_you if form.thank_you is not None else PLATFORM_THANK_YOU,
        "one_response_per_person": form.one_response_per_person,
    }
    # Explicit per key so each keeps its type; a test pins this set to OPERATIONAL_KEYS.
    if form.accepting_responses is not None:
        row["accepting_responses"] = form.accepting_responses
    if form.closed_message is not None:
        row["closed_message"] = form.closed_message
    if form.opens is not None:
        row["opens"] = utc_text(form.opens)
    if form.closes is not None:
        row["closes"] = utc_text(form.closes)
    return row


def _question_row(
    bundle: MappingBundle, table_name: str, question: ListsFormQuestion,
    columns: dict[str, Column], enum_names: set[str],
) -> ListsFormQuestionRow:
    name = question.column
    column = columns.get(name)
    if name == "Attachments":
        default_label = "Attachments"
    else:
        default_label = bundle.mapping.display_name_for(table_name, name)
    return {
        "column": name,
        "label": question.label if question.label is not None else default_label,
        "help": question.help,
        # An undeclared Title (or Attachments) is false: the deploy patches that Title optional.
        "required": column is not None and map_column(column, enum_names).required,
        "display_format": _DISPLAY_FORMAT.get(column.type) if column is not None else None,
    }
