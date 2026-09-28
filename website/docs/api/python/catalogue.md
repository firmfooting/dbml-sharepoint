---
title: catalogue
sidebar_position: 54
---

# `dbml_sharepoint.catalogue`

*Packaging: the shipped solution templates, as data*

The solution templates the wizard can offer, as data.

Templates come from solution roots: core's own `solutions/` directory first,
then the directory each installed distribution registers under the
`dbml_sharepoint.solution_roots` entry-point group. One `Solution` per pack
directory in any root. Everything here is read-only discovery: nothing in
this module writes, validates a mapping or deploys.

Discovered by glob, never by roster. A hardcoded list of names fails open.
A new template is simply never offered, and every test stays green saying
so. `.github/workflows/ci.yml` builds core's set the same way, and
`test_template_standard.py` derives its conformance cases from it.

Each pack declares its id, title, summary and licence in `pack.toml`. A pack
whose manifest is missing, or claims a licence its distribution does not
declare, is refused rather than offered. Core's root is located relative to
this file, inside the installed package, because the audience for the wizard
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

### `SOLUTION_ROOTS_GROUP`

```python
SOLUTION_ROOTS_GROUP = 'dbml_sharepoint.solution_roots'
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
    distribution: str
    license: str
    origin: str
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
    distribution: str
```

One curated reading order over the families.

The wizard's first step. Grouping is DECLARED here rather than derived
from a family's own prose: the READMEs' `*Theme:*` line was never
consistent enough to key off, and a grouping nothing verifies is a
grouping that goes stale, which is how one shipped family came to sit in
no theme at all.

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

### `SolutionRoot`

Where one installed distribution keeps its packs, and the licence it declares.

### `SolutionRootError`

A solution root cannot be read, so no licence the catalogue would print is certain.

Always names the distribution, so the operator knows what to reinstall or remove.

### `Refusal`

```python
@dataclass(frozen=True)
class Refusal:
    distribution: str
    path: Path
    reason: str
```

A pack directory the catalogue will not offer, and the named error why.

### `Shadowed`

```python
@dataclass(frozen=True)
class Shadowed:
    kind: str
    id: str
    distribution: str
    kept_from: str
```

A template or journey not offered because an earlier root offers the same id.

### `Catalogue`

```python
@dataclass(frozen=True)
class Catalogue:
    solutions: tuple[dbml_sharepoint.catalogue.Solution, ...]
    journeys: tuple[dbml_sharepoint.catalogue.Journey, ...]
    refused: tuple[dbml_sharepoint.catalogue.Refusal, ...]
    shadowed: tuple[dbml_sharepoint.catalogue.Shadowed, ...]
```

Everything offered from every root, and what was refused.

Read once per command, so the wizard and `solutions` report the same thing.

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

Every template offered, core's first, each root's ordered by id.

A refused pack is left out; `read_catalogue` says which and why.

### `available_journeys`

```python
def available_journeys() -> list[dbml_sharepoint.catalogue.Journey]
```

Every curated reading order, ordered by id.

Unlike `available_solutions`, a malformed file RAISES rather than being
skipped. A family that will not load is one template out of the picker;
a journey that will not load is a grouping silently missing its members,
and the guard that would have caught it is the one being bypassed.

### `solution_roots`

```python
def solution_roots() -> list[dbml_sharepoint.catalogue.SolutionRoot]
```

Where packs are read from: core first, then each provider by distribution name.

Raises `SolutionRootError` when any root cannot be read. A provider that is
installed but unreadable makes every licence the catalogue would print
uncertain, so nothing is offered until it is fixed or removed.

### `read_catalogue`

```python
def read_catalogue() -> dbml_sharepoint.catalogue.Catalogue
```

Every root's templates and journeys, what was refused, and what was hidden.

Raises `SolutionRootError` when a root cannot be read or a provider's
journey is malformed, and `ValueError` for a malformed journey of core's own.

### `notices`

```python
def notices(found: dbml_sharepoint.catalogue.Catalogue) -> list[str]
```

What an interface prints once per run: each refused pack, then each hidden group.

Hidden ids are grouped by package, so a provider that repeats every core
pack costs one line rather than one per pack.

### `load_solution`

```python
def load_solution(name: str) -> dbml_sharepoint.catalogue.Solution
```

One family by directory name, or `UnknownSolutionError`.

