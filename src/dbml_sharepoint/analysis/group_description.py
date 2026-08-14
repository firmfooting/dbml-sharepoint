# src/dbml_sharepoint/analysis/group_description.py
"""How a site group's Description is composed, shared by the generator and the rule.

Both sides need the same fact: the marker's exact text and the budget it
leaves for a human sentence. This module is the single spelling authority,
imported by `generators.jsgen` and by `analysis.checks._permissions`. A
generator must not import from `analysis/checks/`, which is the other half of
why this is a module rather than a helper inside the rule
(`analysis/joins.py` is the worked example, and `analysis/list_description.py`
is the same pattern for lists).

WHY A MARKER AT ALL. `templates/deploy/_security_principals.js.j2` adopts any
existing site group whose name matches a declared one and grants it whatever
the mapping declares, which for `dbml List Administrators` is Full Control on
every list in the family. Deciding whether that is safe needs an answer to
"did this tool create this group", and nothing on a group recorded that. The
Description is the one group-level string this tool already writes, and a
human reads it in site settings.

MEASURED, NOT ASSUMED. `test/manual/group-description-probe.js` ran
2026-08-13 and again 2026-08-14 against a live tenant: `SP.Group.Description`
round-trips byte-identically, refuses over 512 characters with an HTTP 500
rather than truncating, and accepts empty. A marker composed here therefore
comes back exactly as written, which is what makes the deploy-side test a
byte compare rather than a guess.

NOT THE SAME SURFACE AS A LIST. `SP.List.Description` accepted 1018
characters in `test/manual/list-description-probe.js` and has no comparable
ceiling. Same-named property, different type. Neither result is evidence for
the other, which is why both were measured.
"""

from dbml_sharepoint.analysis.limits import MAX_GROUP_DESCRIPTION

#: The text every marker opens with.
#:
#: Both shapes below build on it, but the deploy no longer tests this prefix
#: on its own: `_security_principals.js.j2` compares the exact marker one
#: group is expected to carry, from `marker_for_group`, so a group another
#: family stamped cannot satisfy this family's adoption test. Changing this
#: string still changes what every already-deployed group is recognised by,
#: so it is not a cosmetic edit.
MARKER_PREFIX = "Provisioned by dbml-sharepoint"

#: The marker for a group this tool names for itself.
SHARED_MARKER = f"{MARKER_PREFIX}."

#: The marker for a group the deploying organisation owns.
FAMILY_MARKER_TEMPLATE = MARKER_PREFIX + " from {family}."

#: Groups this tool names for ITSELF rather than for the organisation
#: deploying it, and which therefore carry no family name.
#:
#: These two are declared identically by every shipped family and reconcile
#: one group object per site, so a marker naming one family would be false on
#: a site running five. Every other group is named by the organisation
#: (`RR Risk Managers`), belongs to exactly one family, and says so.
#:
#: NOT DERIVED FROM THE `dbml ` PREFIX, deliberately. The prefix exists to
#: make a collision with a hand-made group unlikely, which is a different job
#: from recording which groups span families, and an operator who names their
#: own group `dbml Something` should not silently change its marker shape.
#:
#: `test_template_standard.py` pins these values independently rather than
#: importing them, because a test that imports the value it is checking
#: verifies nothing.
TOOL_OWNED_GROUP_NAMES: frozenset[str] = frozenset({
    "dbml Enterprise Readers",
    "dbml List Administrators",
})

#: Characters held back from every description's budget, on top of the marker.
#:
#: THE INVARIANT: the marker may grow by up to this many characters and every
#: shipped group description still fits, so no family becomes unbuildable
#: until a marker change exceeds it.
#:
#: A SEPARATE CONSTANT FROM `list_description.MARKER_GROWTH_RESERVE`, not a
#: reuse of it. That one was sized against 54 table notes under a
#: 255-character ceiling where the tightest left 9 characters spare; group
#: descriptions run against 512 and are far shorter. Sharing one constant
#: would tie a future group-marker change to re-editing every table note,
#: which is the coupling `analysis/limits.py` exists to prevent.
GROUP_MARKER_GROWTH_RESERVE = 32


def marker_for_group(group_name: str, family: str) -> str:
    """The exact marker for one group. The single spelling authority."""
    if group_name in TOOL_OWNED_GROUP_NAMES:
        return SHARED_MARKER
    return FAMILY_MARKER_TEMPLATE.format(family=family)


def description_budget(group_name: str, family: str) -> int:
    """How many characters a declared description may use before the marker will not fit.

    One character comes off for the separating space. `GROUP_MARKER_GROWTH_RESERVE`
    comes off too, so a description that passes here still fits after the marker
    grows by that much.

    NEVER NEGATIVE. A family name long enough to fill the ceiling on its own
    would otherwise give a negative budget, and `text[:-5]` is not "keep
    nothing", it is "keep everything but the last five characters", so the
    backstop below would return a string LONGER than the ceiling.
    """
    marker = marker_for_group(group_name, family)
    return max(0, MAX_GROUP_DESCRIPTION - len(marker) - 1 - GROUP_MARKER_GROWTH_RESERVE)


def group_description(declared: str, *, group_name: str, family: str) -> str:
    """Declared text then marker, within the budget, with the MARKER never truncated.

    Truncating the declared text loses a sentence a human wrote. Truncating
    the marker loses the group from the adoption gate, which then refuses to
    adopt a group this tool created. So `GROUP_DESCRIPTION_TOO_LONG_FOR_MARKER`
    refuses it at build time and this clamp is a backstop, not the enforcement.

    Note the order: the text is clamped BEFORE the marker is appended.
    Appending first and clamping the result cuts the tail, and the tail is the
    marker.
    """
    marker = marker_for_group(group_name, family)
    text = (declared or "").strip()
    budget = description_budget(group_name, family)
    if not text or budget == 0:
        return marker
    return f"{text[:budget].rstrip()} {marker}"
