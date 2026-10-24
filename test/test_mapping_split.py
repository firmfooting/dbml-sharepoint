# test/test_mapping_split.py
import shutil
from pathlib import Path

import pytest
from _paths import FIXTURES

import dbml_sharepoint
from dbml_sharepoint import mapping_split
from dbml_sharepoint.bundle import write_artifact
from dbml_sharepoint.mapping_split import SplitRefusedError, plan_split, split_mapping
from dbml_sharepoint.model import yamlio
from dbml_sharepoint.model.mapping_loader import load_mapping

_ASSET_REGISTER = (
    Path(dbml_sharepoint.__file__).parent / "solutions" / "asset-register" / "20-configure"
)
_REPORTING_SAMPLE = FIXTURES / "blueprints" / "reporting-sample" / "20-configure"
_POINTED = ("reporting.yaml", "demo.yaml")


def _pack(tmp_path: Path, source: Path = _ASSET_REGISTER) -> Path:
    pack = tmp_path / "pack"
    shutil.copytree(source, pack)
    return pack / "mapping.yaml"


def _edit(mapping: Path, old: str, new: str) -> None:
    text = mapping.read_text(encoding="utf-8")
    assert old in text
    mapping.write_bytes(text.replace(old, new, 1).encode())


def _files(folder: Path) -> dict[Path, bytes]:
    return {path: path.read_bytes() for path in folder.rglob("*") if path.is_file()}


def _nonblank(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def test_each_concern_moves_to_its_file_and_identity_stays(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    plan = plan_split(mapping)
    assert plan.moved == {
        "views.yaml": ("field_sets", "views"),
        "permissions.yaml": ("groups", "permission_levels", "list_permissions"),
        "formatting.yaml": ("column_formatting",),
        "validation.yaml": ("column_validation", "list_validation"),
        "demo.yaml": ("demo_items",),
    }
    assert list(plan.texts) == ["mapping.yaml", *plan.moved]
    assert "prefix:" in plan.texts["mapping.yaml"]
    assert "entities:" in plan.texts["mapping.yaml"]
    # form.yaml has its own shape, so the form sections stay.
    assert "form_formatting:" in plan.texts["mapping.yaml"]
    assert "form_visibility:" in plan.texts["mapping.yaml"]


def test_the_split_files_load_as_the_same_mapping(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    original = load_mapping(mapping).mapping
    moved = split_mapping(mapping)
    assert "views.yaml" in moved
    assert (mapping.parent / "views.yaml").is_file()
    assert load_mapping(mapping).mapping == original


def test_no_line_is_lost_or_reordered(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    original = _nonblank(mapping.read_text(encoding="utf-8"))
    plan = plan_split(mapping)
    split = [line for text in plan.texts.values() for line in _nonblank(text)]
    assert sorted(split) == sorted(original)
    for text in plan.texts.values():
        lines = _nonblank(text)
        remaining = iter(original)
        assert all(line in remaining for line in lines)
        assert text.endswith("\n")
        assert not text.endswith("\n\n")
        assert text.strip("\n") == text.rstrip("\n")


def test_a_comment_above_a_key_travels_with_it(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    spine = "\n# The identifying spine"
    _edit(mapping, spine, f"\n# Why these views exist\n{spine}")
    views = plan_split(mapping).texts["views.yaml"].splitlines()
    assert views[0] == "# Why these views exist"
    assert views[views.index("views:") - 1].startswith("# ColumnWidth binds by display name.")


def test_an_indented_comment_stays_with_the_block_above(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    _edit(mapping, "\nform_visibility:", "\n  # Closes the views block.\nform_visibility:")
    plan = plan_split(mapping)
    assert "  # Closes the views block." in plan.texts["views.yaml"]
    assert "Closes the views block" not in plan.texts["mapping.yaml"]


def test_the_header_comment_stays_in_the_mapping(tmp_path: Path) -> None:
    plan = plan_split(_pack(tmp_path))
    assert plan.texts["mapping.yaml"].startswith("# Asset register: physical mapping.\nprefix:")


def test_an_alias_across_concerns_is_refused(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    _edit(mapping, '- name: "Managed List', '- name: &g "Managed List')
    _edit(mapping, '- title: "Locations by name"', "- title: *g")
    load_mapping(mapping)
    with pytest.raises(SplitRefusedError, match=r"views\.yaml would not parse on its own"):
        split_mapping(mapping)
    assert not (mapping.parent / "views.yaml").exists()


def test_a_key_line_the_pattern_misses_is_refused(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    # Quoted, the key joins column_formatting's block and would land in formatting.yaml.
    _edit(mapping, "\nfield_sets:", '\n"field_sets":')
    load_mapping(mapping)
    with pytest.raises(SplitRefusedError, match="does not read back as the same mapping"):
        plan_split(mapping)


def test_a_missed_key_line_in_its_own_concern_is_still_reported(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    # Quoted, views rides in field_sets' block, which is its own home.
    _edit(mapping, "\nviews:", '\n"views":')
    assert plan_split(mapping).moved["views.yaml"] == ("field_sets", "views")


def test_a_value_the_cut_changes_is_refused_and_nothing_is_written(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    # Keep-chomped, the message holds the blank line that travels with the next block.
    warranty = "    message: |+\n      An asset with a Warranty"
    _edit(mapping, '    message: "An asset with a Warranty', warranty)
    _edit(mapping, "cannot be calculated.\"\n", "cannot be calculated.\n")
    load_mapping(mapping)
    before = _files(mapping.parent)
    match = r"^the split does not read back as the same mapping; nothing was written$"
    with pytest.raises(SplitRefusedError, match=match):
        split_mapping(mapping)
    assert _files(mapping.parent) == before


def test_a_failed_mapping_write_leaves_it_whole(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    mapping = _pack(tmp_path)
    before = mapping.read_bytes()

    def half_write(path: Path, text: str) -> None:
        write_artifact(path, text[:10])
        if path.suffix == ".split":
            raise OSError("disk full")

    monkeypatch.setattr(mapping_split, "write_artifact", half_write)
    with pytest.raises(OSError, match="disk full"):
        split_mapping(mapping)
    assert mapping.read_bytes() == before
    assert not (mapping.parent / ".mapping.yaml.split").exists()


def test_a_mapping_with_another_name_is_refused(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    other = mapping.rename(mapping.parent / "other.yaml")
    with pytest.raises(SplitRefusedError, match=r"^other\.yaml: only a file named mapping\.yaml"):
        split_mapping(other)


@pytest.mark.parametrize(
    ("existing", "name"), [("views.yaml", "views.yaml"), ("views.d/a.yaml", "views.d/")],
)
def test_an_existing_concern_is_not_overwritten(tmp_path: Path, existing: str, name: str) -> None:
    mapping = _pack(tmp_path)
    data = yamlio.safe_load(mapping.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    target = mapping.parent / existing
    target.parent.mkdir(exist_ok=True)
    target.write_text(yamlio.safe_dump({"field_sets": data.pop("field_sets")}), encoding="utf-8")
    mapping.write_text(yamlio.safe_dump(data), encoding="utf-8")
    load_mapping(mapping)
    before = {path: path.read_bytes() for path in (mapping, target)}
    with pytest.raises(SplitRefusedError, match=rf"^{name} already exists; move views into it"):
        split_mapping(mapping)
    assert {path: path.read_bytes() for path in before} == before


def test_a_mapping_that_does_not_load_is_refused(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    _edit(mapping, "\nprefix:", "\nbogus_section: 1\nprefix:")
    with pytest.raises(SplitRefusedError, match="must load before it is split: unknown mapping"):
        split_mapping(mapping)


def test_crlf_input_splits_into_lf_files_that_load(tmp_path: Path) -> None:
    mapping = _pack(tmp_path)
    original = load_mapping(mapping).mapping
    mapping.write_bytes(mapping.read_bytes().replace(b"\n", b"\r\n"))
    moved = split_mapping(mapping)
    for name in ("mapping.yaml", *moved):
        assert b"\r" not in (mapping.parent / name).read_bytes()
    assert load_mapping(mapping).mapping == original


def test_a_pointer_stays_in_the_mapping(tmp_path: Path) -> None:
    mapping = _pack(tmp_path, _REPORTING_SAMPLE)
    pointed = {name: (mapping.parent / name).read_bytes() for name in _POINTED}
    original = load_mapping(mapping).mapping
    assert split_mapping(mapping) == {"views.yaml": ("views",)}
    text = mapping.read_text(encoding="utf-8")
    assert "reporting_source: reporting.yaml\n" in text
    assert "demo_source: demo.yaml\n" in text
    assert {name: (mapping.parent / name).read_bytes() for name in pointed} == pointed
    assert load_mapping(mapping).mapping == original


def test_nothing_to_split_writes_nothing(tmp_path: Path) -> None:
    mapping = _pack(tmp_path, _REPORTING_SAMPLE)
    split_mapping(mapping)
    before = mapping.read_bytes()
    assert split_mapping(mapping) == {}
    assert mapping.read_bytes() == before
