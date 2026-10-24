# src/dbml_sharepoint/model/lists_forms.py
"""`lists-forms.yaml`: the Lists forms of each entity, in one file beside the mapping.

It is keyed by entity, and each entity holds `forms` and `retired`. This
module only reads and shapes the file. Whether a question's column exists,
may be asked, or a title fits is the validator's job, so `required` and
`include_time` are recorded by name for it to refuse. The shapes live in
`mapping_types`, because `reading` imports that module.
"""

from collections.abc import Mapping
from pathlib import Path

from dbml_sharepoint.model._keys import _known_keys, _require_list, _text_key
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_types import EntityListsForms, ListsForm, ListsFormQuestion
from dbml_sharepoint.model.reading import (
    load_yaml,
    optional_bool,
    optional_str,
    optional_str_list,
    require_str,
)

LISTS_FORMS_FILE_NAME = "lists-forms.yaml"
_ENTITY_KEYS = frozenset({"forms", "retired"})
_FORM_KEYS = frozenset({
    "title", "previous_titles", "description", "questions", "thank_you",
    "one_response_per_person", "accepting_responses", "closed_message", "opens", "closes",
})
# Column settings a Lists form cannot hold; read so the validator can name them.
_SETS_COLUMN = ("required", "include_time")
_QUESTION_KEYS = frozenset({"column", "label", "help", "respondents_read_source", *_SETS_COLUMN})


def _items(raw: Mapping[str, object], key: str, context: str) -> list[object]:
    """A required, non-empty list under `key`."""
    items = _require_list(raw.get(key), f"{context}.{key}")
    if not items:
        raise MappingShapeError(f"{context}.{key}: expected a non-empty list")
    return items


def _optional_bool_or_none(raw: Mapping[str, object], key: str, context: str) -> bool | None:
    value = raw.get(key)
    if value is not None and not isinstance(value, bool):
        raise MappingShapeError(f"{context}.{key} must be a boolean, got {value!r}")
    return value


def _time(raw: Mapping[str, object], key: str, context: str) -> str | None:
    """The time as the author typed it; an unquoted one reached here as a YAML timestamp."""
    value = raw.get(key)
    if value is not None and not isinstance(value, str):
        raise MappingShapeError(
            f"{context}.{key}: expected text, got {type(value).__name__} {value!r}; quote it",
        )
    return value


def _read_question(raw: object, context: str) -> ListsFormQuestion:
    block = _known_keys(raw, _QUESTION_KEYS, context)
    return ListsFormQuestion(
        column=require_str(block, "column", context),
        label=optional_str(block, "label", context),
        help=optional_str(block, "help", context) or "",
        respondents_read_source=optional_bool(block, "respondents_read_source", context),
        sets_column=tuple(key for key in block if key in _SETS_COLUMN),
    )


def _read_form(raw: object, context: str) -> ListsForm:
    block = _known_keys(raw, _FORM_KEYS, context)
    questions = _items(block, "questions", context)
    return ListsForm(
        title=require_str(block, "title", context),
        questions=tuple(
            _read_question(q, f"{context}.questions[{i}]") for i, q in enumerate(questions)
        ),
        previous_titles=optional_str_list(block, "previous_titles", context),
        description=optional_str(block, "description", context) or "",
        thank_you=optional_str(block, "thank_you", context),
        one_response_per_person=optional_bool(block, "one_response_per_person", context),
        accepting_responses=_optional_bool_or_none(block, "accepting_responses", context),
        closed_message=optional_str(block, "closed_message", context),
        opens=_time(block, "opens", context),
        closes=_time(block, "closes", context),
    )


def read_lists_forms_file(base_dir: Path) -> dict[str, EntityListsForms]:
    """Each entity's Lists forms from `lists-forms.yaml`, or none without the file."""
    path = base_dir / LISTS_FORMS_FILE_NAME
    if not path.is_file():
        return {}
    result: dict[str, EntityListsForms] = {}
    for key, raw in load_yaml(path).items():
        entity = _text_key(key, LISTS_FORMS_FILE_NAME)
        context = f"{LISTS_FORMS_FILE_NAME}.{entity}"
        block = _known_keys(raw, _ENTITY_KEYS, context)
        result[entity] = EntityListsForms(
            forms=tuple(
                _read_form(form, f"{context}.forms[{i}]")
                for i, form in enumerate(_items(block, "forms", context))
            ),
            retired=optional_str_list(block, "retired", context),
        )
    return result
