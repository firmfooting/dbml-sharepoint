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


_REQUIRED_KEYS = ("release", "date", "deployer_version", "schema_version")
_OPTIONAL_KEYS = ("flow_package_version", "notes")


def load_release(path: Path) -> Release:
    """Read release.yaml.

    Every key is checked. The file was read key-by-key with everything else
    ignored, so `schema_verison:` stamped the bundle with the wrong schema
    version and reported nothing, and the version stamp is precisely what
    a later run compares against. A missing key raised a bare
    KeyError('release'), which reaches the operator as a traceback naming a
    dict lookup rather than the file they mistyped.
    """
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(
            f"{path}: expected a YAML mapping at the top level, "
            f"got {type(raw).__name__}",
        )
    unknown = set(raw) - set(_REQUIRED_KEYS) - set(_OPTIONAL_KEYS)
    if unknown:
        raise ValueError(
            f"{path}: unknown key(s) {sorted(unknown)} "
            f"(known: {sorted((*_REQUIRED_KEYS, *_OPTIONAL_KEYS))})",
        )
    missing = [key for key in _REQUIRED_KEYS if key not in raw]
    if missing:
        raise ValueError(f"{path}: missing required key(s) {missing}")
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
