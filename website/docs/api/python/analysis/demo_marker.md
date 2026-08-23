---
title: demo_marker
sidebar_position: 20
---

# `dbml_sharepoint.analysis.demo_marker`

*the demo-row Title-prefix contract*

The demo-row Title-prefix contract, named exactly once.

One string with three jobs. The validator refuses a `demo_items:` row whose
Title does not start with it, demo-data.js writes rows that carry it, and
rollback.js currently bypasses the DELETE NON-EMPTY prompt when every item
starts with it.

It was spelled in `generators/demogen.py`, again in `analysis/checks/_demo.py`,
and a third time as `const DEMO_PREFIX` inside `templates/rollback.js.j2`,
with four more copies in the sentences the CLI, the wizard, the manifest and
`explain` show an operator. The teardown copy is the one that matters most: a
marker changed in the validator and not there leaves a build that passes, a
seed that pastes, and a teardown that no longer recognises its own rows, so
the demo-only path stops applying. A marker changed in teardown alone can be
worse: it may make a different Title prefix satisfy the automatic heuristic
and bypass the non-empty prompt. Nothing between validation and the pasted
script can see the disagreement.

THE PREFIX IS NOT PROVENANCE. `Title` is user-editable and a real record can
carry it. Centralising the string prevents components disagreeing about the
heuristic; it does not make the automatic rollback bypass safe. Issue #293
owns replacing that heuristic with confirmation or durable row provenance.

Nothing in this module imports anything, so `analysis/checks/`, `generators/`
and package-root orchestration can all read it without touching the one-way
dependency rule in AGENTS.md. The same reasoning, and the same shape,
as `limits.py`.

`test_demo_marker_authority.py` holds the package to it: no other module or
template may directly spell the text under another name, and behavioural
tests prove the validator and generated scripts move with this owner.

BREAKING API MOVE (#287): the canonical import is now
`dbml_sharepoint.analysis.demo_marker.DEMO_TITLE_PREFIX`, not
`dbml_sharepoint.generators.demogen.DEMO_TITLE_PREFIX`. There is deliberately
no compatibility re-export because public names have one importable home.

### `DEMO_TITLE_PREFIX`

```python
DEMO_TITLE_PREFIX = '[DEMO] '
```

