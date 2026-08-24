# src/dbml_sharepoint/analysis/list_description.py
"""How a list's Description is composed, shared by the generator and the rule.

Both sides need the same fact: the marker's exact text and the budget it
leaves for a human note. A generator that appended one spelling while a
validator refused another would be worse than either alone -- so this module
is the single spelling authority, imported by `generators.jsgen` and by
`analysis.checks._structure`. A generator must not import from
`analysis/checks/`, which is the other half of why this is a module rather
than a helper inside the rule (`analysis/joins.py` is the worked example).

WHY A MARKER AT ALL. A deployed list carries no record of what produced it.
Fleet reporting across a hundred sites has to be able to ask "which lists did
this tool provision, and from which template family" without a registry that
somebody has to maintain by hand. The Description is the one list-level
string this tool already writes, a human reads it in list settings, and it
survives a rename of the list.
"""

from dbml_sharepoint.analysis import provenance
from dbml_sharepoint.model.parser import Schema

# The list Description budget the emitter has always applied.
#
# This tool's budget, not a SharePoint limit: MEASURED 2026-08-14, the
# platform accepted at least 1018 characters. Kept at 255 because the list
# settings UI, the search index and the reporting pack all read this string
# and none of them has been measured at a greater length. See issue #219.
DESCRIPTION_LIMIT = 255

# The discovery marker. It is a sentence, not a tag, because it sits at the
# end of a description a human reads in list settings.
#
# HOW IT IS MEANT TO BE FOUND, and what is actually established. Enumerating
# lists (`GET /_api/web/lists` and reading `Description`) needs no search
# index and is the mechanism this marker is designed for.
#
# Finding it through SEARCH instead is NOT established, and the tempting
# version of that claim is half wrong -- checked on Learn 2026-08-12:
#
#   DOCUMENTED: the `Description` managed property defaults to Queryable=Yes,
#   Searchable=No, so `Description:"..."` works as a property restriction
#   while the value stays out of the full-text index.
#   https://learn.microsoft.com/sharepoint/technical-reference/crawled-and-managed-properties-overview#managed-properties-overview
#   https://learn.microsoft.com/sharepoint/search/search-schema-overview#managed-property-settings-overview
#
#   NOT DOCUMENTED: that this managed property carries a LIST's description.
#   Its mapped crawled properties are `Description, Office:6, DESCRIPTION` --
#   Office document metadata, the same source as `DocComments` -- and Learn
#   documents no `ows_Description` crawled property at all. The web-level
#   description has its own `SiteDescription` property (Queryable=No), and
#   there is no `ListDescription` analogue. Whether a list-settings
#   Description reaches the index, and under which property, is undocumented.
#
# Also: those flags are DEFAULTS a tenant admin can change in the search
# schema, so they are not invariants of the platform.
#
# So do not build search-based discovery on this without a `test/manual/`
# probe: set a distinctive Description, wait for a crawl, then compare a
# free-text query, a `Description:"..."` restriction, and a
# `contentclass:STS_List` retrieval.
#: Kept for the budget arithmetic below; the marker itself is built by
#: `provenance.marker_for_object`, which is the single authority.
MARKER_TEMPLATE = provenance.MARKER_PREFIX + " from {family} for list {entity}."

# Characters held back from every note's budget, on top of the marker itself.
#
# THE INVARIANT: the marker may grow by up to 32 characters and every shipped
# note still fits. Nothing has to be re-edited, and no family becomes
# unbuildable, until a marker change exceeds that.
#
# WHY IT IS NEEDED. The marker's length is not a constant of the design. Two
# ways it can grow are already foreseen:
#
#   - A VERSION SUFFIX. Version-aware discovery -- a fleet report that can tell
#     which lists came from which release of a family -- was contemplated in
#     the design spec, and the natural spelling of it lengthens the marker
#     (` v0.12.3` and the like).
#   - A LONGER FAMILY OR ENTITY NAME. The budget already depends on both, so a
#     family renamed to something more descriptive shortens every note in it.
#
# WHY IT HAD TO BE RESERVED RATHER THAN LEFT TO CHANCE. MEASURED 2026-08-12
# over the 54 shipped notes as they then stood, the median note left 20
# characters spare and the tightest left 9. That corpus tolerates no growth at
# all: a marker one word longer would have turned roughly half the shipped
# families into build ERRORS -- `ENTITY_NOTE_TOO_LONG_FOR_MARKER` is an error,
# so the family stops building -- and the fix would have been re-editing that
# half of the catalogue's prose under whatever deadline the marker change
# arrived with.
# Charging the reserve to the budget makes that a change to one constant.
#
# 32 IS A JUDGEMENT, not a measurement, and it is deliberately generous enough
# to cover a version suffix with room to spare. It costs each note about a
# fifth of a line of prose; that is much cheaper than the alternative it buys
# out of. Raising it later re-runs the same editorial pass over every family,
# so it is sized once, high, rather than crept upward.
#
# `test_template_standard.py` pins the invariant over the whole catalogue: no
# shipped note may eat into this reserve.
#: 9 of the original 32 were spent when the marker gained the
#: object's own name, so it could stop matching a description copied
#: from another object (#241). The total held back is unchanged, so no
#: note already written became invalid.
MARKER_GROWTH_RESERVE = 23

# Backstop for callers that render without validation. The public build path
# refuses a schema with no DBML `Project`, because an unattributed marker cannot
# establish ownership for adoption or rollback.
UNNAMED_FAMILY = "custom"


# The combined length of a family and entity name at which `note_budget`
# reaches zero -- the marker, the space before it and the growth reserve fill
# the Description on their own, and no note of any length can be accepted.
#
# Equivalently: `note_budget(family, entity)` is this number minus
# `len(family) + len(entity)`, clamped at zero. Derived from the template
# rather than written down, so a reworded marker moves it automatically.
#
# Absurdly far from anything shipped -- the longest family and entity names in
# the catalogue come to well under half of it -- but the rules in
# `analysis/checks/_structure.py` name it when they hit it, because "shorten
# the note" is not advice an author can act on once the budget is zero.
NAME_BUDGET = (
    DESCRIPTION_LIMIT
    - provenance.empty_marker_length(kind=provenance.LIST_KIND, family="")
    - 1
    - MARKER_GROWTH_RESERVE
)


def normalise_family(project_name: str) -> str:
    """The family slug for a DBML `Project` name.

    MEASURED against the shipped catalogue, not assumed: for every family
    the DBML `Project` name is the solution directory name with underscores
    for hyphens (`Project routine_checks` in `solutions/routine-checks/`), so
    swapping them back makes the marker name the family the way the docs,
    the wizard and `catalogue.Solution.id` all name it. That parity is pinned
    by `test_template_standard.py`, so a new family that breaks it fails the
    build rather than emitting a family nobody can look up.

    The fold remains for marker compatibility, but validation now admits only
    the canonical underscore spelling. Hyphens, slashes, surrounding
    whitespace and family/kind boundaries for the current list, group and level
    kinds are refused before generation.
    This keeps the emitted marker bytes unchanged while making the fold
    injective over accepted project names. That matters because family identity
    now authorizes adoption, ACL reconciliation and rollback rather than merely
    attributing a reporting row.
    """
    slug = project_name.strip().replace("_", "-").replace("/", "-")
    return slug or UNNAMED_FAMILY


def family_for(schema: Schema) -> str:
    """The family a schema belongs to, from its DBML `Project` declaration."""
    return normalise_family(schema.project_name)


def marker_for(family: str, entity: str) -> str:
    """The exact marker text for one entity."""
    return provenance.marker_for_object(
        kind=provenance.LIST_KIND, name=entity, family=family,
    )


def note_budget(family: str, entity: str) -> int:
    """How many characters a human note may use before the marker will not fit.

    One character comes off for the space that separates the note from the
    marker. The budget therefore depends on the family and entity names, which
    is why the rule computes it rather than comparing against a constant.

    DELIBERATELY LESS THAN WHAT FITS. `MARKER_GROWTH_RESERVE` comes off too,
    so a note that passes here still fits after the marker grows by up to that
    many characters. An author measuring their note against the marker they
    can see will find this budget short by exactly that reserve; see the
    constant for why the corpus is worth protecting that way.

    NEVER NEGATIVE. A family and entity long enough to fill the limit on their
    own would otherwise produce a negative budget, and `note[:-5]` is not
    "keep nothing" -- it is "keep everything but the last five characters", so
    the backstop in `list_description` would return a string LONGER than the
    limit rather than the marker alone. Unreachable today, because the rule
    refuses the note first and the CLI gates errors before generation; but a
    backstop that is wrong in the case it exists for is not a backstop.
    """
    return max(0, NAME_BUDGET - len(family) - len(entity))


def list_description(table_note: str, *, family: str, entity: str) -> str:
    """Note then marker, within the budget, with the MARKER never truncated.

    Truncating the note loses prose. Truncating the marker loses the list from
    every fleet report, silently and permanently -- the list still deploys,
    the deploy still reads back the truncated description it sent, and every
    deploy phase still passes. So if the two cannot both fit,
    `ENTITY_NOTE_TOO_LONG_FOR_MARKER` refuses the note at build time and this
    never runs on one. The clamp here is a backstop, not the enforcement.

    A list Description round-trips byte for byte, MEASURED 2026-08-14 by
    `test/manual/list-description-probe.js`. Nothing here depends on that,
    because a truncated marker is invisible to fleet reporting whether or not
    the round trip is exact.

    Note the order of operations: the note is clamped BEFORE the marker is
    appended. Appending first and clamping the result is the defect -- it
    cuts the tail, and the tail is the marker.

    A zero budget returns the marker alone rather than a description with a
    leading space: there is no room for a note, and " Provisioned by ..." is
    not what "no room" should look like on a settings page.

    The result therefore stops `MARKER_GROWTH_RESERVE` characters short of
    `DESCRIPTION_LIMIT`, not at it. That unused tail is the point of the
    reserve, not slack going to waste.
    """
    marker = marker_for(family, entity)
    note = (table_note or "").strip()
    budget = note_budget(family, entity)
    if not note or budget == 0:
        return marker
    return f"{note[:budget].rstrip()} {marker}"
