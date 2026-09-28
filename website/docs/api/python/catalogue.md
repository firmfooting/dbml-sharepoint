---
title: catalogue
sidebar_position: 54
---

# `dbml_sharepoint.catalogue`

*Packaging: the shipped solution templates, as data*

The shipped solution templates, as data the wizard can offer.

One `Solution` per directory under `solutions/`. Everything here is
read-only discovery: nothing in this module writes, validates or deploys.

Discovered by glob, never by roster. A hardcoded list of names fails open.
A new template is simply never offered, and every test stays green saying
so. `.github/workflows/ci.yml` builds the same set the same way, and
`test_template_standard.py` derives its conformance cases from it.

The directory is located the way `templating.py` locates the Jinja
templates, relative to this file, inside the installed package. That is
the whole reason the templates were moved here: the audience for the wizard
is somebody who ran `uvx dbml-sharepoint` and has no checkout.

### `SOLUTIONS_DIR`

```python
SOLUTIONS_DIR = Path("dbml_sharepoint/solutions")
```

### `SCHEMA_RELPATH`

```python
SCHEMA_RELPATH = Path("10-design/schema.dbml")
```

### `MAPPING_RELPATH`

```python
MAPPING_RELPATH = Path("20-configure/mapping.yaml")
```

### `RELEASE_RELPATH`

```python
RELEASE_RELPATH = Path("20-configure/release.yaml")
```

### `PLACEHOLDER_SITE_URL`

```python
PLACEHOLDER_SITE_URL = 'https://yourtenant.sharepoint.com/sites/your-site'
```

### `PLACEHOLDER_TIME_ZONE`

```python
PLACEHOLDER_TIME_ZONE = 'Region/City'
```

### `JOURNEYS_DIRNAME`

```python
JOURNEYS_DIRNAME = 'journeys'
```

### `SECTORS_DIRNAME`

```python
SECTORS_DIRNAME = 'sectors'
```

### `CORE_DISTRIBUTION`

```python
CORE_DISTRIBUTION = 'dbml-sharepoint'
```

### `PACK_MANIFEST`

```python
PACK_MANIFEST = 'pack.toml'
```

### `ORIGIN_OWN`

```python
ORIGIN_OWN = 'firmfooting'
```

### `UnknownSolutionError`

Named solution does not exist. Carries the available names.

A `LookupError` rather than a bare `ValueError` so a caller can
distinguish "no such template" from "this template is malformed", which
fail in completely different ways and want different messages.

### `PackManifestError`

A pack's pack.toml is missing, malformed, or claims what the catalogue refuses.

Named so the catalogue can refuse that one pack and keep offering the rest,
and so the reason reaches the operator rather than a traceback.

### `Solution`

```python
@dataclass(frozen=True)
class Solution:
    id: str
    title: str
    summary: str
    detail: str
    lists: tuple[str, ...]
    prefix: str
    root: Path
```

One shipped list family.

Frozen because the catalogue is read once and handed to a UI; nothing
downstream has any business editing a template's identity.

### `Journey`

```python
@dataclass(frozen=True)
class Journey:
    id: str
    title: str
    summary: str
    solution_ids: tuple[str, ...]
    path: Path
```

One curated reading order over the families.

The wizard's first step. Grouping is DECLARED here rather than derived
from a family's own prose: `catalogue._lead_sentence` explains why the
READMEs' `*Theme:*` line was never consistent enough to key off, and a
grouping nothing verifies is a grouping that goes stale, which is how one
shipped family came to sit in no theme at all.

### `PackManifest`

```python
@dataclass(frozen=True)
class PackManifest:
    id: str
    title: str
    summary: str
    license: str
    origin: str
    notice: str
    min_core: str
```

What a pack declares about itself in pack.toml, checked.

### `read_pack_manifest`

```python
def read_pack_manifest(pack_dir: pathlib.Path, distribution_licence: str) -> dbml_sharepoint.catalogue.PackManifest
```

Read and check `pack_dir/pack.toml`, or raise `PackManifestError`.

`distribution_licence` is the License-Expression of the distribution the
pack was found in. A pack may not claim a different one, so the licence a
listing shows is the one the installed package was published under.

### `available_solutions`

```python
def available_solutions() -> list[dbml_sharepoint.catalogue.Solution]
```

Every shipped family, ordered by id.

A directory only counts when it carries a `schema.dbml` at the family
standard's path. That keeps a stray directory -- a leftover `build/`,
an editor's backup -- from appearing in the picker as a template the
user can choose and then fail to deploy.

### `available_journeys`

```python
def available_journeys() -> list[dbml_sharepoint.catalogue.Journey]
```

Every curated reading order, ordered by id.

Unlike `available_solutions`, a malformed file RAISES rather than being
skipped. A family that will not load is one template out of the picker;
a journey that will not load is a grouping silently missing its members,
and the guard that would have caught it is the one being bypassed.

### `load_solution`

```python
def load_solution(name: str) -> dbml_sharepoint.catalogue.Solution
```

One family by directory name, or `UnknownSolutionError`.

