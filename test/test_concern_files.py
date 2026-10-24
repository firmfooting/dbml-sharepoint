# test/test_concern_files.py
import shutil
from pathlib import Path

import pytest
from _paths import FIXTURES, SOLUTION_TEMPLATES

import dbml_sharepoint
from dbml_sharepoint.model import yamlio
from dbml_sharepoint.model.errors import MappingReferenceError, MappingShapeError
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.sections import KNOWN_SECTIONS, SECTION_FAMILIES
from dbml_sharepoint.model.sections._concern_files import CONCERN_FILES
from dbml_sharepoint.pipeline import execute_build

_VISITOR_LOG = SOLUTION_TEMPLATES / "visitor-log" / "20-configure"
_REPORTING_SAMPLE = FIXTURES / "blueprints" / "reporting-sample" / "20-configure"
_ASSET_REGISTER = Path(dbml_sharepoint.__file__).parent / "solutions" / "asset-register"


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


def test_a_concern_file_spelled_yml_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "views.yml", "views")
    with pytest.raises(
        MappingShapeError, match=r"^views\.yml: concern files are named views\.yaml$",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_pointer_naming_a_yml_file_reads_it(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    original = load_mapping(pack / "mapping.yaml").mapping
    _move(pack, "demo.yml", "demo_items")
    _write(pack / "mapping.yaml", {**_read(pack / "mapping.yaml"), "demo_source": "demo.yml"})
    assert load_mapping(pack / "mapping.yaml").mapping.demo_items == original.demo_items


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


def test_a_form_section_in_a_concern_file_belongs_in_form_yaml(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    (pack / "form.yaml").write_text("{}\n", encoding="utf-8")
    _move(pack, "views.yaml", "views", "form_formatting")
    belongs = r"views\.yaml:\d+: .* not form_formatting; form_formatting belongs in form\.yaml$"
    with pytest.raises(MappingShapeError, match=belongs):
        load_mapping(pack / "mapping.yaml")


def test_a_pointer_naming_its_absent_concern_file_is_refused_as_today(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    data = _read(pack / "mapping.yaml")
    del data["demo_items"]
    _write(pack / "mapping.yaml", {**data, "demo_source": "demo.yaml"})
    with pytest.raises(MappingReferenceError, match=r"demo_source: cannot read 'demo\.yaml'"):
        load_mapping(pack / "mapping.yaml")


def test_a_pointer_elsewhere_with_no_concern_file_loads_as_today(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    original = load_mapping(pack / "mapping.yaml").mapping
    _move(pack, "rows.yaml", "demo_items")
    _write(pack / "mapping.yaml", {**_read(pack / "mapping.yaml"), "demo_source": "rows.yaml"})
    assert load_mapping(pack / "mapping.yaml").mapping.demo_items == original.demo_items


def test_a_pointer_elsewhere_beside_a_concern_folder_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "rows.yaml", "demo_items")
    (pack / "demo.d").mkdir()
    shutil.copy(pack / "rows.yaml", pack / "demo.d" / "a.yaml")
    _write(pack / "mapping.yaml", {**_read(pack / "mapping.yaml"), "demo_source": "rows.yaml"})
    with pytest.raises(
        MappingShapeError, match=r"demo_source points at 'rows\.yaml' and demo\.d/ exists",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_pointer_naming_its_concern_file_beside_its_folder_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "demo.yaml", "demo_items")
    (pack / "demo.d").mkdir()
    (pack / "demo.yaml").rename(pack / "demo.d" / "a.yaml")
    _write(pack / "mapping.yaml", {**_read(pack / "mapping.yaml"), "demo_source": "demo.yaml"})
    with pytest.raises(
        MappingShapeError, match=r"demo_source points at 'demo\.yaml' and demo\.d/ exists",
    ):
        load_mapping(pack / "mapping.yaml")


def _split_views(pack: Path) -> None:
    """Move the views and field sets into views.d/, one numbered file per list in view order."""
    data = _read(pack / "mapping.yaml")
    views, field_sets = data.pop("views"), data.pop("field_sets", {})
    assert isinstance(views, dict) and isinstance(field_sets, dict)
    lists = [*views, *(name for name in field_sets if name not in views)]
    (pack / "views.d").mkdir()
    for number, name in enumerate(lists, 1):
        block: dict[str, object] = {}
        if name in field_sets:
            block["field_sets"] = {name: field_sets[name]}
        if name in views:
            block["views"] = {name: views[name]}
        _write(pack / "views.d" / f"{number * 10}-{name}.yaml", block)
    _write(pack / "mapping.yaml", data)


def test_views_split_across_a_folder_load_like_one_file(tmp_path: Path) -> None:
    pack = tmp_path / "pack"
    shutil.copytree(_ASSET_REGISTER / "20-configure", pack)
    original = load_mapping(pack / "mapping.yaml").mapping
    _split_views(pack)
    assert len(list((pack / "views.d").iterdir())) > 1
    got = load_mapping(pack / "mapping.yaml").mapping
    assert list(got.views) == list(original.views)
    assert got.views == original.views
    assert got == original


def _folder(pack: Path, files: dict[str, dict[str, object]]) -> None:
    (pack / "views.d").mkdir()
    for name, block in files.items():
        _write(pack / "views.d" / name, block)


def _views_without(pack: Path) -> dict[str, object]:
    data = _read(pack / "mapping.yaml")
    views = data.pop("views")
    assert isinstance(views, dict)
    _write(pack / "mapping.yaml", data)
    return views


def test_a_list_declared_in_two_folder_files_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    views = _views_without(pack)
    _folder(pack, {"a.yaml": {"views": views}, "b.yaml": {"field_sets": {}, "views": views}})
    with pytest.raises(
        MappingShapeError,
        match=r"views\[\w+\] is declared in views\.d/a\.yaml:2 and views\.d/b\.yaml:3",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_scalar_section_in_two_folder_files_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    (pack / "formatting.d").mkdir()
    _write(pack / "formatting.d" / "a.yaml", {"style_theme": "a"})
    _write(pack / "formatting.d" / "b.yaml", {"style_theme": {"x": 1}})
    with pytest.raises(
        MappingShapeError,
        match=r"^style_theme is declared in formatting\.d/a\.yaml:1 and formatting\.d/b\.yaml:1$",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_file_and_a_folder_for_one_concern_are_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _move(pack, "views.yaml", "views")
    (pack / "views.d").mkdir()
    with pytest.raises(
        MappingShapeError,
        match=r"^views\.yaml and views\.d/ both exist: a concern lives in one file or one folder\.",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_non_yaml_entry_in_a_folder_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _folder(pack, {"a.yaml": {"views": _views_without(pack)}, "extra.yml": {"views": {}}})
    with pytest.raises(
        MappingShapeError, match=r"views\.d/extra\.yml: a concern folder holds \.yaml files only",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_folder_file_holding_a_foreign_key_names_itself(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _folder(pack, {"a.yaml": {"field_sets": {}, "groups": {}}})
    with pytest.raises(
        MappingShapeError,
        match=r"^views\.d/a\.yaml:2: .* not groups; groups belongs in permissions\.yaml$",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_folder_section_also_inline_is_refused_with_both_lines(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    _folder(pack, {"a.yaml": {"field_sets": {}}, "b.yaml": {"views": {}}})
    with pytest.raises(
        MappingShapeError, match=r"views is declared in mapping\.yaml:\d+ and views\.d/b\.yaml:1",
    ):
        load_mapping(pack / "mapping.yaml")


def test_a_path_in_a_folder_file_resolves_from_the_mapping_folder(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    original = load_mapping(pack / "mapping.yaml").mapping
    data = _read(pack / "mapping.yaml")
    assert "formatting/signed-out-at.json" in str(data["column_formatting"])
    (pack / "formatting.d").mkdir()
    _move(pack, "formatting.d/a.yaml", "column_formatting")
    assert load_mapping(pack / "mapping.yaml").mapping == original


def test_a_concern_folder_name_that_is_a_file_is_refused(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    (pack / "views.d").write_text("views: {}\n", encoding="utf-8")
    with pytest.raises(MappingShapeError, match=r"^views\.d exists but is not a folder$"):
        load_mapping(pack / "mapping.yaml")


def test_an_aliased_section_is_not_extended_through_its_alias(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    views = _views_without(pack)
    _folder(pack, {"b.yaml": {"views": views}})
    (pack / "views.d" / "a.yaml").write_text(
        "field_sets: &empty {}\nviews: *empty\n", encoding="utf-8",
    )
    got = load_mapping(pack / "mapping.yaml").mapping
    assert got.field_sets == {}
    assert list(got.views) == list(views)


def test_folder_entries_take_file_name_order(tmp_path: Path) -> None:
    pack = _pack(tmp_path)
    views = _views_without(pack)
    first = next(iter(views))
    _folder(pack, {
        "b.yaml": {"views": {"X": views[first]}},
        "a.yaml": {"views": {"Y": views[first]}},
    })
    assert list(load_mapping(pack / "mapping.yaml").mapping.views) == ["Y", "X"]


def _build(root: Path, out: Path) -> dict[str, bytes]:
    execute_build(
        schema=root / "10-design" / "schema.dbml",
        mapping=root / "20-configure" / "mapping.yaml",
        release=root / "20-configure" / "release.yaml",
        site_url="https://example.sharepoint.com/sites/test",
        time_zone="UTC",
        site_role="default",
        out=out,
        seed=True,
        source_date_epoch=1759276800,
    )
    built = {str(p.relative_to(out)): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}
    shutil.rmtree(out)
    return built


def test_a_folder_split_in_original_order_builds_byte_identical(tmp_path: Path) -> None:
    root = tmp_path / "asset-register"
    shutil.copytree(_ASSET_REGISTER, root)
    out = tmp_path / "out"
    before = _build(root, out)
    _split_views(root / "20-configure")
    assert _build(root, out) == before
