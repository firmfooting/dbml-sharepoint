"""Loader: the `governance` section.

Shape only. Whether a value is in the declared vocabulary, and whether an
entity, column or retention policy exists, is the validator's call and is
tested in `test_validator_governance.py`.
"""

from pathlib import Path

import pytest
from _packs import blocks, entities, write_mapping

from dbml_sharepoint.model.errors import (
    MappingShapeError,
    MappingValueError,
    UnknownMappingKeyError,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    ColumnGovernance,
    Governance,
    GovernanceVocabulary,
    ListGovernance,
)

_FULL = """
    governance:
      vocabulary:
        classification: [open, internal, restricted]
        personal_data: [none, contact, sensitive]
        owners: [list_steward, records_lead]
      lists:
        Risk:
          purpose: "Tracks risks raised against projects."
          owner: list_steward
          classification: internal
          personal_data: contact
          retention: keep_seven_years
          columns:
            Notes: { purpose: "Free-text commentary.", personal_data: sensitive }
            Title: { purpose: "Short name of the risk." }
"""


def _load(tmp_path: Path, governance: str) -> Governance:
    path = write_mapping(tmp_path, blocks(entities("Risk"), governance), name="mapping.yaml")
    return load_mapping(path).governance


def _refuses(tmp_path: Path, governance: str, error: type[Exception], text: str) -> None:
    path = write_mapping(tmp_path, blocks(entities("Risk"), governance), name="mapping.yaml")
    with pytest.raises(error, match=text):
        load_mapping(path)


def test_a_mapping_without_the_section_loads_an_empty_one(tmp_path: Path) -> None:
    path = write_mapping(tmp_path, entities("Risk"), name="mapping.yaml")
    assert load_mapping(path).governance == Governance()


def test_a_blank_section_loads_an_empty_one(tmp_path: Path) -> None:
    assert _load(tmp_path, "governance:\n") == Governance()


def test_the_full_section_loads_typed(tmp_path: Path) -> None:
    loaded = _load(tmp_path, _FULL)
    assert loaded.vocabulary == GovernanceVocabulary(
        classification=("open", "internal", "restricted"),
        personal_data=("none", "contact", "sensitive"),
        owners=("list_steward", "records_lead"),
    )
    assert loaded.lists == {
        "Risk": ListGovernance(
            purpose="Tracks risks raised against projects.",
            owner="list_steward",
            classification="internal",
            personal_data="contact",
            retention="keep_seven_years",
            columns={
                "Notes": ColumnGovernance(
                    purpose="Free-text commentary.", personal_data="sensitive",
                ),
                "Title": ColumnGovernance(purpose="Short name of the risk."),
            },
        ),
    }


def test_every_key_is_optional(tmp_path: Path) -> None:
    loaded = _load(
        tmp_path,
        """
        governance:
          lists:
            Risk: { purpose: "Only a purpose." }
        """,
    )
    assert loaded.lists["Risk"] == ListGovernance(purpose="Only a purpose.")
    assert loaded.vocabulary == GovernanceVocabulary()


def test_a_bare_purpose_key_means_not_declared(tmp_path: Path) -> None:
    loaded = _load(
        tmp_path,
        """
        governance:
          lists:
            Risk:
              purpose:
              owner: list_steward
        """,
    )
    assert loaded.lists["Risk"].purpose is None


def test_a_misspelled_top_level_section_is_refused(tmp_path: Path) -> None:
    _refuses(tmp_path, "governence:\n  lists: {}\n", UnknownMappingKeyError, "governence")


@pytest.mark.parametrize(
    ("body", "where"),
    [
        ("governance:\n  vocabulry: {}\n", "governance: .*vocabulry"),
        ("governance:\n  vocabulary:\n    levels: [a]\n", "governance.vocabulary"),
        ("governance:\n  lists:\n    Risk:\n      porpoise: x\n", "governance.lists.Risk"),
        (
            (
                "governance:\n  lists:\n    Risk:\n      columns:\n        Notes:\n"
                "          classification: open\n"
            ),
            "governance.lists.Risk.columns.Notes",
        ),
    ],
)
def test_an_unknown_key_is_refused_at_every_level(
    tmp_path: Path, body: str, where: str,
) -> None:
    _refuses(tmp_path, body, UnknownMappingKeyError, where)


@pytest.mark.parametrize(
    ("body", "text"),
    [
        ("governance: []\n", "governance: expected a mapping"),
        ("governance:\n  lists: [Risk]\n", "governance.lists: expected a mapping"),
        ("governance:\n  vocabulary:\n    owners: list_steward\n", "must be a list of strings"),
        ("governance:\n  vocabulary:\n    owners: [1, 2]\n", "must be a list of strings"),
        ("governance:\n  lists:\n    Risk:\n", "governance.lists.Risk: expected a mapping"),
        (
            "governance:\n  lists:\n    Risk:\n      columns:\n        Notes:\n",
            "governance.lists.Risk.columns.Notes: expected a mapping",
        ),
        ("governance:\n  lists:\n    Risk: { owner: 5 }\n", "owner must be a string"),
        (
            "governance:\n  lists:\n    Risk: { columns: { Notes: { personal_data: true } } }\n",
            "personal_data must be a string",
        ),
    ],
)
def test_a_value_of_the_wrong_shape_is_refused_naming_the_key(
    tmp_path: Path, body: str, text: str,
) -> None:
    _refuses(tmp_path, body, MappingShapeError, text)


def test_a_blank_text_value_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        'governance:\n  lists:\n    Risk: { owner: "" }\n',
        MappingValueError,
        "governance.lists.Risk.owner is blank",
    )


@pytest.mark.parametrize(
    "body",
    [
        'governance:\n  lists:\n    Risk: { purpose: "" }\n',
        'governance:\n  lists:\n    Risk: { columns: { Notes: { purpose: "" } } }\n',
    ],
)
def test_a_blank_purpose_is_refused(tmp_path: Path, body: str) -> None:
    _refuses(tmp_path, body, MappingValueError, "purpose is blank")


def test_a_carriage_return_in_a_purpose_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        'governance:\n  lists:\n    Risk: { purpose: "a\\rb" }\n',
        MappingValueError,
        "purpose must be one line",
    )


def test_a_multi_line_purpose_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        'governance:\n  lists:\n    Risk: { purpose: "Line one.\\nLine two." }\n',
        MappingValueError,
        "purpose must be one line",
    )


def test_a_folded_block_purpose_is_one_line(tmp_path: Path) -> None:
    loaded = _load(
        tmp_path,
        """
        governance:
          lists:
            Risk:
              purpose: >
                Wrapped in the file,
                one line when read.
        """,
    )
    assert loaded.lists["Risk"].purpose == "Wrapped in the file, one line when read."


def test_a_repeated_vocabulary_value_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        "governance:\n  vocabulary:\n    owners: [list_steward, list_steward]\n",
        MappingValueError,
        "lists .*list_steward.* more than once",
    )


def test_a_padded_value_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        'governance:\n  lists:\n    Risk: { classification: " restricted " }\n',
        MappingValueError,
        "surrounding whitespace",
    )


def test_a_padded_vocabulary_declaration_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        'governance:\n  vocabulary:\n    classification: [open, " restricted"]\n',
        MappingValueError,
        "surrounding whitespace",
    )


def test_a_blank_vocabulary_value_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        'governance:\n  vocabulary:\n    classification: [open, ""]\n',
        MappingValueError,
        "blank value",
    )


@pytest.mark.parametrize("key", ["owner", "classification", "personal_data", "retention"])
def test_a_bare_non_purpose_key_is_refused(tmp_path: Path, key: str) -> None:
    _refuses(
        tmp_path,
        f"governance:\n  lists:\n    Risk:\n      {key}:\n",
        MappingValueError,
        f"governance.lists.Risk.{key} is empty",
    )


def test_a_bare_column_personal_data_key_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        "governance:\n  lists:\n    Risk:\n      columns:\n        Notes:\n"
        "          personal_data:\n",
        MappingValueError,
        "governance.lists.Risk.columns.Notes.personal_data is empty",
    )


def test_a_bare_column_purpose_key_means_not_declared(tmp_path: Path) -> None:
    loaded = _load(
        tmp_path,
        "governance:\n  lists:\n    Risk:\n      columns:\n        Notes:\n          purpose:\n",
    )
    assert loaded.lists["Risk"].columns["Notes"].purpose is None
