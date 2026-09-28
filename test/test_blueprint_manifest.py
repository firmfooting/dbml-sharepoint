"""blueprint.toml: what a blueprint declares about itself, and each claim the catalogue refuses."""

import re
import tomllib
from pathlib import Path

import pytest
from _catalogue_fixtures import CORE_LICENSE, manifest_text, without
from _paths import REPO_ROOT, SOLUTION_TEMPLATES

from dbml_sharepoint.catalogue import (
    BLUEPRINT_MANIFEST,
    ORIGIN_OWN,
    BlueprintManifestError,
    read_blueprint_manifest,
)

_KEYS = ("id", "title", "summary", "license", "origin", "notice", "min_core")


def _pack(tmp_path: Path, text: str, name: str = "acme-thing") -> Path:
    pack_dir = tmp_path / name
    pack_dir.mkdir()
    (pack_dir / BLUEPRINT_MANIFEST).write_text(text, encoding="utf-8", newline="\n")
    return pack_dir


def _read(tmp_path: Path, overrides: dict[str, str]) -> None:
    read_blueprint_manifest(_pack(tmp_path, manifest_text("acme-thing", overrides)), CORE_LICENSE)


def test_core_license_is_the_one_pyproject_declares() -> None:
    """The cross-check compares against installed metadata, so pin that to the source."""
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["license"] == CORE_LICENSE


def test_a_valid_manifest_is_read(tmp_path: Path) -> None:
    manifest = read_blueprint_manifest(_pack(tmp_path, manifest_text("acme-thing")), CORE_LICENSE)
    assert manifest.id == "acme-thing"
    assert manifest.title == "Acme thing"
    assert manifest.summary == "A pack written for a test."
    assert (manifest.license, manifest.origin, manifest.notice) == (CORE_LICENSE, ORIGIN_OWN, "")
    assert manifest.min_core == ">=0.5,<1"


def test_a_pack_without_a_manifest_is_refused(tmp_path: Path) -> None:
    pack_dir = tmp_path / "acme-thing"
    pack_dir.mkdir()
    with pytest.raises(BlueprintManifestError, match=r"no blueprint\.toml"):
        read_blueprint_manifest(pack_dir, CORE_LICENSE)


@pytest.mark.parametrize("key", _KEYS)
def test_every_key_is_required(tmp_path: Path, key: str) -> None:
    text = without(manifest_text("acme-thing"), key)
    with pytest.raises(BlueprintManifestError, match=f"declares no '{key}'"):
        read_blueprint_manifest(_pack(tmp_path, text), CORE_LICENSE)


@pytest.mark.parametrize("key", [k for k in _KEYS if k != "notice"])
def test_an_empty_value_is_refused(tmp_path: Path, key: str) -> None:
    with pytest.raises(BlueprintManifestError, match=f"'{key}' is empty"):
        _read(tmp_path, {key: "  "})


def test_a_value_that_is_not_a_string_is_refused(tmp_path: Path) -> None:
    text = without(manifest_text("acme-thing"), "license") + "license = 3\n"
    with pytest.raises(BlueprintManifestError, match="'license' must be a string, not int"):
        read_blueprint_manifest(_pack(tmp_path, text), CORE_LICENSE)


def test_text_that_is_not_toml_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BlueprintManifestError, match="not valid TOML"):
        read_blueprint_manifest(_pack(tmp_path, 'id = "acme-thing\n'), CORE_LICENSE)


def test_bytes_that_are_not_utf8_are_refused(tmp_path: Path) -> None:
    pack_dir = tmp_path / "acme-thing"
    pack_dir.mkdir()
    (pack_dir / BLUEPRINT_MANIFEST).write_bytes(b'title = "caf\xe9"\n')
    with pytest.raises(BlueprintManifestError, match="not UTF-8"):
        read_blueprint_manifest(pack_dir, CORE_LICENSE)


def test_a_byte_order_mark_and_crlf_endings_are_read(tmp_path: Path) -> None:
    """What an editor on Windows may save; it is the same pack."""
    pack_dir = tmp_path / "acme-thing"
    pack_dir.mkdir()
    text = manifest_text("acme-thing").replace("\n", "\r\n")
    (pack_dir / BLUEPRINT_MANIFEST).write_bytes(b"\xef\xbb\xbf" + text.encode("utf-8"))
    assert read_blueprint_manifest(pack_dir, CORE_LICENSE).id == "acme-thing"


def test_an_unknown_key_is_refused(tmp_path: Path) -> None:
    text = manifest_text("acme-thing") + 'licence = "MIT"\n'
    with pytest.raises(BlueprintManifestError, match=r"unknown key\(s\) \['licence'\]"):
        read_blueprint_manifest(_pack(tmp_path, text), CORE_LICENSE)


def test_an_id_that_is_not_the_directory_name_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BlueprintManifestError, match="is not the directory name 'acme-thing'"):
        _read(tmp_path, {"id": "acme-other"})


def test_a_licence_other_than_the_distribution_s_is_refused(tmp_path: Path) -> None:
    expected = re.escape(f"license 'BUSL-1.1' differs from '{CORE_LICENSE}'")
    with pytest.raises(BlueprintManifestError, match=expected):
        _read(tmp_path, {"license": "BUSL-1.1"})


def test_a_released_origin_without_a_notice_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BlueprintManifestError, match="'acme-released' needs a notice"):
        _read(tmp_path, {"origin": "acme-released"})


def test_a_notice_that_is_not_in_the_pack_is_refused(tmp_path: Path) -> None:
    expected = "notice 'NOTICE' is not a file inside the blueprint"
    with pytest.raises(BlueprintManifestError, match=expected):
        _read(tmp_path, {"origin": "acme-released", "notice": "NOTICE"})


def test_a_notice_outside_the_pack_is_refused_even_when_it_exists(tmp_path: Path) -> None:
    (tmp_path / "NOTICE").write_text("terms\n", encoding="utf-8")
    with pytest.raises(BlueprintManifestError, match="is not a file inside the blueprint"):
        _read(tmp_path, {"origin": "acme-released", "notice": "../NOTICE"})


def test_a_released_origin_with_its_notice_is_read(tmp_path: Path) -> None:
    overrides = {"origin": "acme-released", "notice": "NOTICE"}
    pack_dir = _pack(tmp_path, manifest_text("acme-thing", overrides))
    (pack_dir / "NOTICE").write_text("terms\n", encoding="utf-8")
    manifest = read_blueprint_manifest(pack_dir, CORE_LICENSE)
    assert (manifest.origin, manifest.notice) == ("acme-released", "NOTICE")


def test_a_held_origin_needs_no_notice(tmp_path: Path) -> None:
    pack_dir = _pack(tmp_path, manifest_text("acme-thing", {"origin": "acme-held"}))
    assert read_blueprint_manifest(pack_dir, CORE_LICENSE).origin == "acme-held"


@pytest.mark.parametrize(
    "origin", ["somewhere", "acme", "-held", "Acme-held", "acme-released-late"],
)
def test_an_origin_outside_the_vocabulary_is_refused(tmp_path: Path, origin: str) -> None:
    with pytest.raises(BlueprintManifestError, match="is not 'firmfooting'"):
        _read(tmp_path, {"origin": origin})


def test_typography_in_a_title_is_folded_to_ascii(tmp_path: Path) -> None:
    """A provider's pack reaches a legacy console the way core's do."""
    title = "Risk " + chr(0x2014) + " register"
    pack_dir = _pack(tmp_path, manifest_text("acme-thing", {"title": title}))
    assert read_blueprint_manifest(pack_dir, CORE_LICENSE).title == "Risk -- register"


def test_a_character_with_no_console_spelling_is_refused(tmp_path: Path) -> None:
    with pytest.raises(BlueprintManifestError, match=r"'summary' carries .* U\+00E9"):
        _read(tmp_path, {"summary": "Caf" + chr(0x00E9) + " bookings."})


def _shipped_packs() -> list[Path]:
    return sorted(p.parent.parent for p in SOLUTION_TEMPLATES.glob("*/10-design/schema.dbml"))


def test_the_shipped_sweep_reads_packs() -> None:
    """Core keeps six starter packs after the split, so fewer means the glob broke."""
    assert len(_shipped_packs()) >= 6


@pytest.mark.parametrize("pack_dir", _shipped_packs(), ids=lambda p: p.name)
def test_every_shipped_pack_has_a_valid_manifest(pack_dir: Path) -> None:
    manifest = read_blueprint_manifest(pack_dir, CORE_LICENSE)
    assert manifest.origin == ORIGIN_OWN


def test_a_manifest_that_cannot_be_read_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lock or a permission error refuses that one pack rather than raising past the picker."""
    pack_dir = _pack(tmp_path, manifest_text("acme-thing"))
    real = Path.read_text

    def locked(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        if self.name == BLUEPRINT_MANIFEST:
            raise PermissionError(13, "Permission denied", str(self))
        return real(self, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", locked)
    with pytest.raises(BlueprintManifestError, match=r"cannot be read: .*Permission denied"):
        read_blueprint_manifest(pack_dir, CORE_LICENSE)


def test_an_id_a_console_cannot_print_is_refused(tmp_path: Path) -> None:
    """The id is printed by the picker and by `blueprints`, like the title."""
    name = "caf" + chr(0x00E9)
    pack_dir = _pack(tmp_path, manifest_text(name), name=name)
    with pytest.raises(BlueprintManifestError, match=r"'id' carries .* U\+00E9"):
        read_blueprint_manifest(pack_dir, CORE_LICENSE)


def test_the_manifest_file_is_blueprint_toml() -> None:
    """The file name is a contract with every provider, so it is pinned literally."""
    assert BLUEPRINT_MANIFEST == "blueprint.toml"


def test_no_shipped_blueprint_keeps_the_old_manifest_name() -> None:
    assert not sorted(SOLUTION_TEMPLATES.glob("*/pack.toml"))


@pytest.mark.parametrize("control", [0x1B, 0x07, 0x7F])
def test_a_control_character_in_manifest_text_is_refused(tmp_path: Path, control: int) -> None:
    """An escape sequence in a title could clear or rewrite the operator's terminal."""
    title = "Risk" + chr(control) + "[2J register"
    with pytest.raises(BlueprintManifestError, match=rf"'title' carries .* U\+{control:04X}"):
        _read(tmp_path, {"title": title})


def test_an_absolute_notice_is_refused_even_inside_the_blueprint(tmp_path: Path) -> None:
    """Copied into a project, an absolute notice would still point at the provider's install."""
    pack_dir = tmp_path / "acme-thing"
    notice = pack_dir / "NOTICE"
    overrides = {"origin": "acme-released", "notice": str(notice)}
    _pack(tmp_path, manifest_text("acme-thing", overrides))
    notice.write_text("terms\n", encoding="utf-8")
    with pytest.raises(BlueprintManifestError, match="must be a path relative to the blueprint"):
        read_blueprint_manifest(pack_dir, CORE_LICENSE)
