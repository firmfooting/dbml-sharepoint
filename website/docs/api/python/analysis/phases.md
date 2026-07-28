---
title: phases
sidebar_position: 8
---

# `dbml_sharepoint.analysis.phases`

*the deploy-phase manifest*

The deploy-phase manifest: THE single source of phase truth.

Group/step numbers derive from position here — add or move a step and
every consumer renumbers automatically: deploy.js banners/Starting
lines/[Phase X.Y] prefixes/error tags (templates receive
phases_context()), the manifest's phase references (phase_numbers()),
and test expectations (phase_number()). Reference steps by NAME or key
in prose and docs; numbers belong to generated artifacts.

### `PhaseStep`

```python
@dataclass
class PhaseStep:
    key: str
    name: str
    template: str
```

PhaseStep(key: str, name: str, template: str)

### `DEPLOY_GROUPS`

```python
DEPLOY_GROUPS = (('PREPARE', (PhaseStep(key='preflight', name='read-only preflight', template='deploy/_preflight.js.j2'), PhaseStep(key='security', name='permission levels and site groups', template='deploy/_security…
```

### `phases_context`

```python
def phases_context() -> list[dict[str, typing.Any]]
```

Render-ready structure for deploy.js.j2 (numbers derived).

### `phase_numbers`

```python
def phase_numbers() -> dict[str, str]
```

{step key: dotted number} — the manifest template's lookup.

### `phase_number`

```python
def phase_number(key: str) -> str
```

