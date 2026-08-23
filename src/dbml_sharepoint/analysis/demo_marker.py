# src/dbml_sharepoint/analysis/demo_marker.py
"""The demo-row Title-prefix contract, named exactly once.

The prefix is a visible sample-data notice. Validation requires every declared
`demo_items:` Title to start with it, generated demo and operator prose quote
it, and users can see it in every list view and form.

THE PREFIX IS NOT PROVENANCE OR DELETION AUTHORITY. `Title` is user-editable and
a real record can carry the same text. Issue #293 removed rollback's automatic
prefix-based bypass; rollback now requires per-list confirmation before every
delete. Centralising
the string prevents the remaining validation, generation and guidance surfaces
from disagreeing about the notice they show.

The value was previously declared in `generators/demogen.py`, hard-coded in the
demo validator and prose, and repeated in rollback. PR #294 gave it this one
home; #293 removed the rollback dependency after its safety review established
that a naming convention could not prove row ownership.

Nothing in this module imports anything, so `analysis/checks/`, `generators/`
and package-root orchestration can read it without reversing the dependency
rule in AGENTS.md. `test_demo_marker_authority.py` holds the package to the
single owner and proves validator and demo rendering move with it.

BREAKING API MOVE (#287): the canonical import is
`dbml_sharepoint.analysis.demo_marker.DEMO_TITLE_PREFIX`, not
`dbml_sharepoint.generators.demogen.DEMO_TITLE_PREFIX`. There is deliberately
no compatibility re-export because public names have one importable home.
"""

#: The Title prefix every declared demo row carries. The trailing space is part
#: of it: `[DEMO]Sample` is not marked sample data.
#:
#: It is the in-record notice visible in every view and form. Per-row list-item
#: comments were tried and withdrawn: the modern Comments() endpoint is an
#: undocumented surface and rejected the write live, 2026-07-24, while adding
#: nothing the visible Title prefix does not already show.
#:
#: `demo.js.j2` interpolates the controlled value into JavaScript comments and
#: a single-quoted log line. The authority test refuses characters that could
#: terminate any of those contexts before this value can change.
DEMO_TITLE_PREFIX = "[DEMO] "
