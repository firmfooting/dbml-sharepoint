# test/test_form_file.py
from pathlib import Path

import pytest
from _packs import blocks, entities, write_mapping

from dbml_sharepoint.model.errors import (
    MappingReferenceError,
    MappingShapeError,
    UnknownMappingKeyError,
)
from dbml_sharepoint.model.mapping_loader import load_mapping

_BASE = blocks(entities("Doc"))
_FORM_IN_MAPPING = """
    form_formatting:
      Doc:
        header: h.json
        body: { sections: [ { displayname: Core, fields: [Title] } ] }
    form_visibility:
      Doc:
        reconcile: declared
        columns:
          Calc: hidden
"""
_FORM_FILE = """
Doc:
  header: { file: h.json }
  body: { sections: [ { displayname: Core, fields: [Title] } ] }
  visibility:
    reconcile: declared
    columns:
      Calc: hidden
"""


def _form(tmp_path: Path, text: str) -> None:
    (tmp_path / "h.json").write_text("{}", encoding="utf-8")
    (tmp_path / "form.yaml").write_text(text, encoding="utf-8")


def test_no_form_yaml_changes_nothing(tmp_path: Path) -> None:
    bundle = load_mapping(write_mapping(tmp_path, _BASE))
    assert bundle.form_trees == {}
    assert bundle.mapping.form_formatting == {}
    assert bundle.mapping.form_visibility == {}


def test_form_yaml_fills_form_formatting_and_visibility(tmp_path: Path) -> None:
    (tmp_path / "h.json").write_text("{}", encoding="utf-8")
    expected = load_mapping(write_mapping(tmp_path, blocks(_BASE, _FORM_IN_MAPPING)))
    _form(tmp_path, _FORM_FILE)
    got = load_mapping(write_mapping(tmp_path, _BASE, name="m2.yaml"))
    assert got.mapping.form_formatting == expected.mapping.form_formatting
    assert got.mapping.form_visibility == expected.mapping.form_visibility
    assert got.form_trees == {}


@pytest.mark.parametrize("section", ["form_formatting", "form_visibility"])
def test_mapping_declaring_a_form_section_with_a_form_yaml_is_refused(
    tmp_path: Path, section: str,
) -> None:
    _form(tmp_path, _FORM_FILE)
    body = blocks(_BASE, f"{section}:\n  Doc: {{}}\n")
    with pytest.raises(MappingReferenceError, match=rf"mapping\.yaml.*{section}.*form\.yaml.*Move"):
        load_mapping(write_mapping(tmp_path, body))


def test_unknown_key_in_an_entity_is_refused(tmp_path: Path) -> None:
    _form(tmp_path, "Doc:\n  headr: { file: h.json }\n")
    with pytest.raises(UnknownMappingKeyError, match="headr"):
        load_mapping(write_mapping(tmp_path, _BASE))


def test_an_entity_with_no_part_is_refused(tmp_path: Path) -> None:
    _form(tmp_path, "Doc: {}\n")
    with pytest.raises(MappingShapeError, match=r"form\.yaml\.Doc"):
        load_mapping(write_mapping(tmp_path, _BASE))


def test_a_component_header_alone_is_accepted(tmp_path: Path) -> None:
    _form(tmp_path, "Doc:\n  header:\n    title: { column: Title }\n")
    bundle = load_mapping(write_mapping(tmp_path, _BASE))
    assert bundle.form_trees["Doc"]["header"] == {"title": {"column": "Title"}}
    assert bundle.mapping.form_formatting["Doc"].header is None
