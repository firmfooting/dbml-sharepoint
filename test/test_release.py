# test/test_release.py
from pathlib import Path

import pytest
from _packs import write_mapping
from _paths import FIXTURES

from dbml_sharepoint.model.release import load_release, snapshot_hashes


def test_load_release_returns_tag_and_versions() -> None:
    rel = load_release(FIXTURES / "release.yaml")
    assert rel.release_tag == "0.1.0-test"
    assert rel.deployer_version == "dbml-sharepoint/0.1.0"
    assert rel.schema_version == "0.8"


def test_snapshot_hashes_returns_sha256_for_each_path() -> None:
    paths = {
        "topics": FIXTURES / "topics.yaml",
        "retention": FIXTURES / "retention-policies.yaml",
    }
    hashes = snapshot_hashes(paths)
    assert {"topics", "retention"} == set(hashes)
    assert all(len(h) == 64 for h in hashes.values())


def test_release_unknown_keys_are_rejected(tmp_path: Path) -> None:
    """release.yaml was read key-by-key and everything else ignored, so
    `schema_verison:` shipped a snapshot stamped with the wrong schema
    version and no error, and the version stamp is what a later run
    compares against."""
    write_mapping(
        tmp_path,
        """
        release: "1.0.0"
        date: "2026-01-01"
        deployer_version: "dbml-sharepoint/0.1.0"
        schema_version: "1.0.0"
        schema_verison: "1.0.1"
        """,
        prefix=None,
        name="release.yaml",
    )
    with pytest.raises(ValueError, match="schema_verison"):
        load_release(tmp_path / "release.yaml")


def test_release_unknown_keys_of_two_types_are_named_rather_than_compared(
    tmp_path: Path,
) -> None:
    """YAML reads `2026:` as an int, and sorting it beside a text key raised a
    bare TypeError before the refusal could be built."""
    write_mapping(
        tmp_path,
        """
        release: "1.0.0"
        date: "2026-01-01"
        deployer_version: "dbml-sharepoint/0.1.0"
        schema_version: "1.0.0"
        2026: x
        note: y
        """,
        prefix=None,
        name="release.yaml",
    )
    with pytest.raises(ValueError, match=r"unknown key\(s\) \[2026, 'note'\]"):
        load_release(tmp_path / "release.yaml")


def test_release_missing_key_is_named_not_a_keyerror(tmp_path: Path) -> None:
    """A missing key raised a bare KeyError('release'), which reaches the
    operator as a traceback naming a dict lookup rather than a file."""
    write_mapping(tmp_path, 'date: "2026-01-01"', prefix=None, name="release.yaml")
    with pytest.raises(ValueError, match="release") as err:
        load_release(tmp_path / "release.yaml")
    assert "release.yaml" in str(err.value)


_QUOTED = {
    "release": '"1.0.0"',
    "date": '"2026-01-01"',
    "deployer_version": '"dbml-sharepoint/0.1.0"',
    "schema_version": '"1.0.0"',
}


def _release_yaml(**overrides: str) -> str:
    return "\n".join(f"{key}: {value}" for key, value in {**_QUOTED, **overrides}.items())


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("release", "2.10", r"'release' must be text, got float 2\.1; quote it"),
        ("schema_version", "1", r"'schema_version' must be text, got int 1; quote it"),
        ("deployer_version", "[a]", r"'deployer_version' must be text, got list"),
        ("flow_package_version", "1.0", r"'flow_package_version' must be text, got float"),
        ("date", "20260101", r"'date' must be text, got int"),
        ("release", "", r"'release' is required"),
        ("date", "", r"'date' is required"),
    ],
)
def test_release_value_that_is_not_text_is_refused(
    tmp_path: Path, key: str, value: str, message: str,
) -> None:
    """An unquoted `release: 2.10` loads as the float 2.1, which reached
    deploy.js as the number 2.1 through `tojson`."""
    write_mapping(tmp_path, _release_yaml(**{key: value}), prefix=None, name="release.yaml")
    with pytest.raises(ValueError, match=message) as err:
        load_release(tmp_path / "release.yaml")
    assert "release.yaml" in str(err.value)


def test_release_blank_optional_key_takes_its_default(tmp_path: Path) -> None:
    """A blank key reads as absent, the rule `model/reading.py` states. Both
    defaults here only describe the release, so nothing is reported."""
    write_mapping(
        tmp_path, _release_yaml(notes="", flow_package_version=""),
        prefix=None, name="release.yaml",
    )
    release = load_release(tmp_path / "release.yaml")
    assert (release.notes, release.flow_package_version) == ("", "none")


def test_release_unquoted_date_is_read_as_iso_text(tmp_path: Path) -> None:
    write_mapping(tmp_path, _release_yaml(date="2026-09-24"), prefix=None, name="release.yaml")
    assert load_release(tmp_path / "release.yaml").date == "2026-09-24"
