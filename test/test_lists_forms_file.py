# test/test_lists_forms_file.py
from pathlib import Path

import pytest
from _packs import blocks, entities, write_mapping

from dbml_sharepoint.model.errors import MappingShapeError, UnknownMappingKeyError
from dbml_sharepoint.model.lists_forms import LISTS_FORMS_FILE_NAME, read_lists_forms_file
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import ListsFormQuestion

_EXAMPLE = """\
Request:
  forms:
    - title: Facilities request
      description: |
        Tell us what needs fixing. We reply within two working days.
        How we handle requests: https://example.com/facilities/requests
      thank_you: Thanks. The facilities team reads every request.
      one_response_per_person: false
      opens: "2026-11-02T09:00:00+11:00"
      closes: "2026-12-18T17:00:00+11:00"
      questions:
        - column: Title
          label: What needs fixing?
        - column: Details
          help: Include the building and room number.
        - column: Category
        - column: Priority
        - column: NeededBy
        - column: Attachments
"""


def _write(tmp_path: Path, text: str) -> Path:
    (tmp_path / LISTS_FORMS_FILE_NAME).write_text(text, encoding="utf-8")
    return tmp_path


def _one_form(extra: str = "", question: str = "") -> str:
    """One entity with one form of one question, `extra` and `question` appended."""
    return (
        "Request:\n  forms:\n    - title: Facilities request\n"
        f"{extra}"
        "      questions:\n        - column: Title\n"
        f"{question}"
    )


def test_spec_phase_a_example_loads(tmp_path: Path) -> None:
    got = read_lists_forms_file(_write(tmp_path, _EXAMPLE))
    assert list(got) == ["Request"]
    (form,) = got["Request"].forms
    assert form.questions[0] == ListsFormQuestion(column="Title", label="What needs fixing?")
    assert form.opens == "2026-11-02T09:00:00+11:00"
    assert form.thank_you == "Thanks. The facilities team reads every request."
    assert form.accepting_responses is None
    assert form.description.endswith("requests\n")
    assert [q.column for q in form.questions][-1] == "Attachments"
    assert form.questions[1].help == "Include the building and room number."
    assert got["Request"].retired == ()


def test_absent_file_reads_as_no_forms(tmp_path: Path) -> None:
    assert read_lists_forms_file(tmp_path) == {}


@pytest.mark.parametrize(
    ("text", "key"),
    [
        (_one_form() + "  respondent_link: organisation\n", "respondent_link"),
        (_one_form("      logo: logo.png\n"), "logo"),
        (_one_form("      sections: []\n"), "sections"),
        (_one_form(question="          branches: {}\n"), "branches"),
    ],
)
def test_unknown_key_is_refused(tmp_path: Path, text: str, key: str) -> None:
    with pytest.raises(UnknownMappingKeyError, match=key):
        read_lists_forms_file(_write(tmp_path, text))


def test_unquoted_time_is_refused(tmp_path: Path) -> None:
    text = _one_form("      opens: 2026-11-02T09:00:00+11:00\n")
    with pytest.raises(MappingShapeError, match=r"forms\[0\]\.opens.*quote it"):
        read_lists_forms_file(_write(tmp_path, text))


@pytest.mark.parametrize(
    "text",
    [
        _one_form('      one_response_per_person: "yes"\n'),
        "Request:\n  forms:\n    - title: Facilities request\n      questions: []\n",
        "Request:\n  forms: []\n",
        _one_form("      previous_titles: Old\n"),
        "Request:\n  forms: {}\n",
    ],
    ids=["bool-as-text", "no-questions", "no-forms", "previous-titles-text", "forms-mapping"],
)
def test_wrong_types_are_refused(tmp_path: Path, text: str) -> None:
    with pytest.raises(MappingShapeError, match=r"lists-forms\.yaml\.Request"):
        read_lists_forms_file(_write(tmp_path, text))


def test_sets_column_keys_are_recorded_not_refused(tmp_path: Path) -> None:
    text = _one_form(question="          required: true\n          include_time: false\n")
    (form,) = read_lists_forms_file(_write(tmp_path, text))["Request"].forms
    assert form.questions[0].sets_column == ("required", "include_time")


_MAPPING = blocks(entities("Request"))


def test_lists_forms_section_in_mapping_is_refused(tmp_path: Path) -> None:
    body = blocks(_MAPPING, "lists_forms:\n  Request: {}\n")
    with pytest.raises(UnknownMappingKeyError, match="lists_forms"):
        load_mapping(write_mapping(tmp_path, body, name="mapping.yaml"))


def test_load_mapping_carries_the_file(tmp_path: Path) -> None:
    write_mapping(_write(tmp_path, _EXAMPLE), _MAPPING, name="mapping.yaml")
    got = load_mapping(tmp_path / "mapping.yaml").lists_forms
    assert got["Request"].forms[0].title == "Facilities request"
