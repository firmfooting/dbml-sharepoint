# src/dbml_sharepoint/model/sections/_governance.py
"""`governance`: purpose, owner, classification, personal-data class and retention.

Shape only, as `identities` is. Whether a value is in the declared vocabulary,
whether an entity or column exists and whether a retention policy is declared
are the validator's calls (the GOVERNANCE_* codes), so one mapping reports
every fault at once rather than the first one the loader meets.
"""

from collections.abc import Mapping

from dbml_sharepoint.model._keys import _known_keys, _require_mapping
from dbml_sharepoint.model.errors import MappingValueError
from dbml_sharepoint.model.mapping_types import (
    ColumnGovernance,
    Governance,
    GovernanceVocabulary,
    ListGovernance,
)
from dbml_sharepoint.model.reading import optional_str, optional_str_list
from dbml_sharepoint.model.sections.context import LoadedFields, SectionContext

_SECTION_KEYS = frozenset({"vocabulary", "lists"})
_VOCABULARY_KEYS = frozenset({"classification", "personal_data", "owners"})
_LIST_KEYS = frozenset(
    {"purpose", "owner", "classification", "personal_data", "retention", "columns"},
)
_COLUMN_KEYS = frozenset({"purpose", "personal_data"})


def read(sc: SectionContext) -> LoadedFields:
    raw = sc.block("governance")
    if raw is None:
        return {"governance": Governance()}
    section = _known_keys(raw, _SECTION_KEYS, "governance")
    return {
        "governance": Governance(
            vocabulary=_vocabulary(section.get("vocabulary")),
            lists={
                entity: _list(spec, f"governance.lists.{entity}")
                for entity, spec in _require_mapping(
                    section.get("lists"), "governance.lists",
                ).items()
            },
        ),
    }


def _vocabulary(raw: object) -> GovernanceVocabulary:
    if raw is None:
        return GovernanceVocabulary()
    context = "governance.vocabulary"
    block = _known_keys(raw, _VOCABULARY_KEYS, context)
    return GovernanceVocabulary(
        classification=_values(block, "classification", context),
        personal_data=_values(block, "personal_data", context),
        owners=_values(block, "owners", context),
    )


def _values(block: Mapping[str, object], key: str, context: str) -> tuple[str, ...]:
    values = optional_str_list(block, key, context)
    if any(not value.strip() for value in values):
        raise MappingValueError(f"{context}.{key} has a blank value; remove it")
    padded = [value for value in values if value != value.strip()]
    if padded:
        raise MappingValueError(
            f"{context}.{key} has {padded!r} with surrounding whitespace; "
            f"values are compared exactly, so remove it",
        )
    repeated = sorted({value for value in values if values.count(value) > 1})
    if repeated:
        raise MappingValueError(f"{context}.{key} lists {repeated} more than once")
    return values


def _list(raw: object, context: str) -> ListGovernance:
    block = _known_keys(raw, _LIST_KEYS, context)
    columns = _require_mapping(block.get("columns"), f"{context}.columns")
    return ListGovernance(
        purpose=_text(block, "purpose", context, one_line=True),
        owner=_text(block, "owner", context),
        classification=_text(block, "classification", context),
        personal_data=_text(block, "personal_data", context),
        retention=_text(block, "retention", context),
        columns={
            name: _column(spec, f"{context}.columns.{name}") for name, spec in columns.items()
        },
    )


def _column(raw: object, context: str) -> ColumnGovernance:
    block = _known_keys(raw, _COLUMN_KEYS, context)
    return ColumnGovernance(
        purpose=_text(block, "purpose", context, one_line=True),
        personal_data=_text(block, "personal_data", context),
    )


def _text(
    block: Mapping[str, object], key: str, context: str, *, one_line: bool = False,
) -> str | None:
    """A text value, or None when the key is absent (or a bare `purpose:`).

    `one_line` is for the free-text keys: a document renders them in a table
    cell, where a line break would split the row. A folded YAML block (`>`)
    reads as one line, so only a real line break is refused. Every other key
    is matched against the vocabulary exactly, so surrounding whitespace is
    refused rather than trimmed.
    """
    value = optional_str(block, key, context)
    if value is None:
        # Only the free-text key may be left bare; an empty enum-like key is a mistake.
        if key in block and not one_line:
            raise MappingValueError(
                f"{context}.{key} is empty; omit the key or give it a value",
            )
        return None
    text = value.strip()
    if not text:
        raise MappingValueError(
            f"{context}.{key} is blank; omit the key to leave it undeclared",
        )
    if one_line:
        if len(text.splitlines()) > 1:
            raise MappingValueError(f"{context}.{key} must be one line")
        return text
    if text != value:
        raise MappingValueError(
            f"{context}.{key} {value!r} has surrounding whitespace; "
            f"values are compared exactly, so remove it",
        )
    return text
