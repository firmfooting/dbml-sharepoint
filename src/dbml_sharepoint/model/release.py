# src/dbml_sharepoint/model/release.py
"""release.yaml reader + config-snapshot hashing."""

import hashlib
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Release:
    release_tag: str
    date: str
    deployer_version: str
    schema_version: str
    flow_package_version: str
    notes: str


def load_release(path: Path) -> Release:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return Release(
        release_tag=raw["release"],
        date=raw["date"],
        deployer_version=raw["deployer_version"],
        schema_version=raw["schema_version"],
        flow_package_version=raw.get("flow_package_version", "none"),
        notes=raw.get("notes", ""),
    )


def snapshot_hashes(paths: dict[str, Path]) -> dict[str, str]:
    """SHA-256 of each file's bytes; used to populate config_snapshot at
    deployer-build time."""
    out: dict[str, str] = {}
    for name, path in paths.items():
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        out[name] = digest
    return out
