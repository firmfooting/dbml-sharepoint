# src/dbml_sharepoint/analysis/demo_marker.py
"""The demo-row Title-prefix contract, named exactly once.

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
"""

#: The Title prefix every demo row carries. The trailing space is part of it:
#: `[DEMO]Sample` is not a marked row, and the teardown's `startsWith` is
#: where that distinction decides whether a live list is deleted unprompted.
#:
#: The marker is the in-record demo notice: visible in every view and form
#: header, and the prefix rollback.js currently treats as a demo heuristic.
#: It is not ownership evidence; see #293. (Per-row list-item comments were
#: tried and withdrawn: the modern Comments() endpoint is undocumented surface
#: and rejected the write live, 2026-07-24, while adding nothing the marker
#: does not already show.)
#:
#: `rollback.js.j2` interpolates this into a single-quoted JavaScript literal
#: rather than through `| tojson`, which keeps that executable literal line
#: byte for byte what it was before #287. A value holding an apostrophe or a
#: backslash would break that script;
#: `test_owner_declares_the_marker_and_safe_javascript_shape` refuses
#: one.
DEMO_TITLE_PREFIX = "[DEMO] "
