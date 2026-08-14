# src/dbml_sharepoint/analysis/role_definition_description.py
"""How a permission level's Description is composed, shared by the generator and the rule.

Both sides need the same fact: the marker's exact text and the budget it
leaves for a human sentence. This module is the single spelling authority,
imported by `generators.jsgen` and by `analysis.checks._permissions`. A
generator must not import from `analysis/checks/`, which is the other half of
why this is a module rather than a helper inside the rule
(`analysis/joins.py` is the worked example, and `group_description.py` is the
same pattern for a site group).

WHY A MARKER AT ALL. A role definition is SITE-SCOPED: its permission bitmap
decides what every principal holding it can do, on every list that assigns
it, including lists this tool never enumerates. `deploy.js.txt` adopts any
existing role definition whose name matches a declared one and MERGEs the
declared bitmap onto it, so deciding whether that adoption is safe needs an
answer to "did this tool create this level", and nothing on a role
definition recorded that. The Description is the one level-level string this
tool already writes, and a human reads it in site permissions.

ONE MARKER SHAPE, NOT TWO. Unlike a site group, no permission level is
shared across families, so there is no tool-owned name and no `SHARED_MARKER`
counterpart here; every level belongs to exactly one family and its marker
always names it.

MEASURED, NOT ASSUMED. `test/manual/role-definition-probe.js` ran 2026-08-14,
revisions `709c2549` and `4dd7de1c`, against a live tenant:
`SP.RoleDefinition.Description` round-trips byte-identically through both the
create path and the MERGE path, a partial MERGE leaves the rest of the
bitmap untouched, empty is accepted, and 512 characters is REFUSED with an
HTTP 500 rather than truncated.

THE CEILING MATCHING A GROUP'S IS TWO FACTS, NOT ONE. `MAX_GROUP_DESCRIPTION`
and `MAX_ROLE_DEFINITION_DESCRIPTION` are both 512, but that is two separately
measured surfaces agreeing rather than one fact wearing two names: the group
probe's refusal read "cannot be null or bigger than 512 characters" and this
one's read "cannot be bigger than 512 characters", omitting the null clause.
A probe that moves one number has no authority over the other, which is why
`MAX_ROLE_DEFINITION_DESCRIPTION` is `analysis/limits.py`'s own constant
rather than a reuse of `MAX_GROUP_DESCRIPTION`.
"""

from dbml_sharepoint.analysis.group_description import FAMILY_MARKER_TEMPLATE
from dbml_sharepoint.analysis.limits import MAX_ROLE_DEFINITION_DESCRIPTION

#: Characters held back from every description's budget, on top of the marker.
#:
#: THE INVARIANT: the marker may grow by up to this many characters and every
#: shipped level description still fits, so no family becomes unbuildable
#: until a marker change exceeds it.
#:
#: A SEPARATE CONSTANT FROM `group_description.GROUP_MARKER_GROWTH_RESERVE`,
#: not a reuse of it, for the reason that constant's own comment gives:
#: sharing one reserve would tie a future change to one marker to re-editing
#: descriptions that belong to the other surface.
LEVEL_MARKER_GROWTH_RESERVE = 32


def marker_for_level(family: str) -> str:
    """The exact marker for one permission level. The single spelling authority."""
    return FAMILY_MARKER_TEMPLATE.format(family=family)


def level_description_budget(family: str) -> int:
    """How many characters a declared description may use before the marker will not fit.

    One character comes off for the separating space. `LEVEL_MARKER_GROWTH_RESERVE`
    comes off too, so a description that passes here still fits after the marker
    grows by that much.

    NEVER NEGATIVE. A family name long enough to fill the ceiling on its own
    would otherwise give a negative budget, and `text[:-5]` is not "keep
    nothing", it is "keep everything but the last five characters", so the
    backstop below would return a string LONGER than the ceiling.
    """
    marker = marker_for_level(family)
    return max(
        0,
        MAX_ROLE_DEFINITION_DESCRIPTION - len(marker) - 1 - LEVEL_MARKER_GROWTH_RESERVE,
    )


def level_description(declared: str, *, family: str) -> str:
    """Declared text then marker, within the budget, with the MARKER never truncated.

    Truncating the declared text loses a sentence a human wrote. Truncating
    the marker loses the level from the adoption gate, which then refuses to
    adopt a level this tool created. A build-time rule is meant to refuse a
    description too long for its marker before this ever has to choose; this
    clamp is the backstop, not the enforcement.

    Note the order: the text is clamped BEFORE the marker is appended.
    Appending first and clamping the result cuts the tail, and the tail is
    the marker.
    """
    marker = marker_for_level(family)
    text = (declared or "").strip()
    budget = level_description_budget(family)
    if not text or budget == 0:
        return marker
    return f"{text[:budget].rstrip()} {marker}"
