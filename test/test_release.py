# test/test_release.py
from pathlib import Path

from dbml_sharepoint.release import load_release, snapshot_hashes

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


