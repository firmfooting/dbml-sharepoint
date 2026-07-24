---
title: release
sidebar_position: 3
---

# `dbml_sharepoint.release`

*Model — load release.yaml provenance*

release.yaml reader + config-snapshot hashing.

### `Release`

```python
@dataclass
class Release:
    release_tag: str
    date: str
    deployer_version: str
    schema_version: str
    flow_package_version: str
    notes: str
```

Release(release_tag: str, date: str, deployer_version: str, schema_version: str, flow_package_version: str, notes: str)

### `load_release`

```python
def load_release(path: pathlib.Path) -> dbml_sharepoint.release.Release
```

### `snapshot_hashes`

```python
def snapshot_hashes(paths: dict[str, pathlib.Path]) -> dict[str, str]
```

SHA-256 of each file's bytes; used to populate config_snapshot at
deployer-build time.

