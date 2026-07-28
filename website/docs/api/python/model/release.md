---
title: release
sidebar_position: 3
---

# `dbml_sharepoint.model.release`

*load release.yaml provenance*

release.yaml reader + config-snapshot hashing.

### `Release`

```python
@dataclass(frozen=True)
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
def load_release(path: pathlib.Path) -> dbml_sharepoint.model.release.Release
```

Read release.yaml.

Every key is checked. The file was read key-by-key with everything else
ignored, so `schema_verison:` stamped the bundle with the wrong schema
version and reported nothing — and the version stamp is precisely what
a later run compares against. A missing key raised a bare
KeyError('release'), which reaches the operator as a traceback naming a
dict lookup rather than the file they mistyped.

### `snapshot_hashes`

```python
def snapshot_hashes(paths: dict[str, pathlib.Path]) -> dict[str, str]
```

SHA-256 of each file's bytes; used to populate config_snapshot at
deployer-build time.

