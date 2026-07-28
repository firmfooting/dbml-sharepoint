# test/test_release.py
from pathlib import Path

import pytest

from dbml_sharepoint.model.release import load_release, snapshot_hashes

FIXTURES = Path(__file__).parent / "fixtures"


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
    version and no error — and the version stamp is what a later run
    compares against."""
    (tmp_path / "release.yaml").write_text(
        'release: "1.0.0"\n'
        'date: "2026-01-01"\n'
        'deployer_version: "dbml-sharepoint/0.1.0"\n'
        'schema_version: "1.0.0"\n'
        'schema_verison: "1.0.1"\n',
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="schema_verison"):
        load_release(tmp_path / "release.yaml")


def test_release_missing_key_is_named_not_a_keyerror(tmp_path: Path) -> None:
    """A missing key raised a bare KeyError('release'), which reaches the
    operator as a traceback naming a dict lookup rather than a file."""
    (tmp_path / "release.yaml").write_text('date: "2026-01-01"\n', encoding="utf-8")
    with pytest.raises(ValueError, match="release") as err:
        load_release(tmp_path / "release.yaml")
    assert "release.yaml" in str(err.value)
