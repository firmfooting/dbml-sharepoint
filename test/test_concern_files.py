# test/test_concern_files.py
import shutil
from pathlib import Path

import pytest
from _paths import FIXTURES, SOLUTION_TEMPLATES

from dbml_sharepoint.model import yamlio
from dbml_sharepoint.model.errors import MappingShapeError
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.sections import KNOWN_SECTIONS, SECTION_FAMILIES
from dbml_sharepoint.model.sections._concern_files import CONCERN_FILES

_VISITOR_LOG = SOLUTION_TEMPLATES / "visitor-log" / "20-configure"
_REPORTING_SAMPLE = FIXTURES / "blueprints" / "reporting-sample" / "20-configure"


def _pack(tmp_path: Path) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(_VISITOR_LOG, pack)
    return pack


def _read(path: Path) -> dict[str, object]:
    data = yamlio.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _write(path: Path, data: dict[str, object]) -> None:
    path.write_text(yamlio.safe_dump(data), encoding="utf-8")


def _move(pack: Path, concern: str, *keys: str, mapping: str = "mapping.yaml") -> None:
    """Move `keys` out of the pack's mapping into `concern`, written in that order."""
    data = _read(pack / "mapping.yaml")
    _write(pack / concern, {key: data.pop(key) for key in keys})
    (pack / "mapping.yaml").unlink()
    _write(pack / mapping, data)


def test_views_in_views_yaml_load_like_inline_views(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    original = load_mapping(pack / "mapping.yaml").mapping
    _move(pack, "views.yaml", "views")
    got = load_mapping(pack / "mapping.yaml").mapping
    assert got.views == original.views
    assert got.field_sets == original.field_sets
    assert got == original


def test_a_section_in_two_homes_is_refused_with_both_lines(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _write(pack / "views.yaml", {"views": _read(pack / "mapping.yaml")["views"]})
    with pytest.raises(
        MappingShapeError, match=r"views is declared in mapping\.yaml:\d+ and views\.yaml:1",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_foreign_key_names_where_it_belongs(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "views.yaml", "groups", "views")
    belongs = r"views\.yaml:1: .* not groups; groups belongs in permissions\.yaml"
    with pytest.raises(MappingShapeError, match=belongs):
        load_mapping(pack / "mapping.yaml")


def test_a_foreign_key_the_mapping_reads_belongs_in_the_mapping(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "views.yaml", "views", "seal_columns")
    belongs = r"views\.yaml:\d+: .* not seal_columns; seal_columns belongs in mapping\.yaml$"
    with pytest.raises(MappingShapeError, match=belongs):
        load_mapping(pack / "mapping.yaml")


def test_an_unknown_key_in_a_concern_file_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _write(pack / "views.yaml", {"field_sets": {}, "viewz": {}})
    with pytest.raises(MappingShapeError, match=r"views\.yaml:2: .* not viewz$"):
        load_mapping(pack / "mapping.yaml")


def test_a_pointer_naming_the_concern_file_reads_it_once(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    original = load_mapping(pack / "mapping.yaml").mapping
    _move(pack, "demo.yaml", "demo_items")
    data = _read(pack / "mapping.yaml")
    _write(pack / "mapping.yaml", {**data, "demo_source": "demo.yaml"})
    assert load_mapping(pack / "mapping.yaml").mapping.demo_items == original.demo_items


def test_a_pointer_elsewhere_beside_a_concern_file_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "demo.yaml", "demo_items")
    shutil.copy(pack / "demo.yaml", pack / "rows.yaml")
    _write(pack / "mapping.yaml", {**_read(pack / "mapping.yaml"), "demo_source": "rows.yaml"})
    with pytest.raises(
        MappingShapeError, match=r"demo_source points at 'rows\.yaml' and demo\.yaml exists",
    ):
        load_mapping(pack / "mapping.yaml")


def test_concern_files_beside_another_name_are_not_read(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "views.yaml", "views", mapping="other-mapping.yaml")
    assert load_mapping(pack / "other-mapping.yaml").mapping.views == {}


def test_a_non_text_pointer_is_refused_as_today(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "demo.yaml", "demo_items")
    _write(pack / "mapping.yaml", {**_read(pack / "mapping.yaml"), "demo_source": 3})
    with pytest.raises(MappingShapeError, match="demo_source must be a path relative to"):
        load_mapping(pack / "mapping.yaml")


def test_a_removed_section_in_a_concern_file_gets_no_home(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _write(pack / "views.yaml", {"hidden_on_forms": {}})
    with pytest.raises(MappingShapeError, match=r"views\.yaml:1: .* not hidden_on_forms$"):
        load_mapping(pack / "mapping.yaml")


def test_an_empty_concern_file_is_absent(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    original = load_mapping(pack / "mapping.yaml").mapping
    (pack / "views.yaml").write_text("# nothing yet\n", encoding="utf-8")
    assert load_mapping(pack / "mapping.yaml").mapping.views == original.views


def test_a_concern_file_that_is_not_a_mapping_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    (pack / "views.yaml").write_text("- views\n", encoding="utf-8")
    with pytest.raises(MappingShapeError, match=r"views\.yaml: expected a mapping of names"):
        load_mapping(pack / "mapping.yaml")


def test_the_reporting_sample_pointers_read_their_concern_files(tmp_path: Path) -> None:
    pointed = load_mapping(_REPORTING_SAMPLE / "mapping.yaml")
    inline = tmp_path / "inline"
    inline.mkdir()
    data = _read(_REPORTING_SAMPLE / "mapping.yaml")
    del data["reporting_source"], data["demo_source"]
    data |= _read(_REPORTING_SAMPLE / "reporting.yaml") | _read(_REPORTING_SAMPLE / "demo.yaml")
    _write(inline / "mapping.yaml", data)
    expected = load_mapping(inline / "mapping.yaml")
    assert pointed.mapping.demo_items == expected.mapping.demo_items
    assert pointed.mapping.reporting == expected.mapping.reporting
    assert pointed.mapping.derived_columns == expected.mapping.derived_columns


def test_every_concern_key_is_a_known_section_in_one_concern() -> None:
    keys = [k for ks in CONCERN_FILES.values() for k in ks]
    assert len(keys) == len(set(keys))
    assert set(keys) <= KNOWN_SECTIONS


def test_the_pointer_families_match_their_concern_files() -> None:
    pointed = {f.keys: f.source for f in SECTION_FAMILIES if f.source}
    assert pointed == {
        CONCERN_FILES["reporting.yaml"]: "reporting_source",
        CONCERN_FILES["demo.yaml"]: "demo_source",
    }
