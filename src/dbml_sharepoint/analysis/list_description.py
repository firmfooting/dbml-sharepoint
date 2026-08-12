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

from dbml_sharepoint.model.parser import Schema

# The list Description budget the emitter has always applied.
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
MARKER_TEMPLATE = "Provisioned by dbml-sharepoint from {family}/{entity}."

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
# WHY IT HAD TO BE RESERVED RATHER THAN LEFT TO CHANCE. Measured over the 54
# shipped notes when they were first written, the median note left 20
# characters spare and the tightest left 9. That corpus tolerates no growth at
# all: a marker one word longer would have turned roughly half the shipped
# families into build ERRORS -- `ENTITY_NOTE_TOO_LONG_FOR_MARKER` is an error,
# so the family stops building -- and the fix would have been re-editing 25
# templates' prose under whatever deadline the marker change arrived with.
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
MARKER_GROWTH_RESERVE = 32

# The family recorded for a schema that declares no DBML `Project`. A
# hand-written schema is a perfectly ordinary input -- `dbml-sharepoint build`
# takes any DBML path -- and such a list must still be DISCOVERABLE even
# though its family is unknown. Losing the family name costs precision in a
# report; losing the marker loses the list entirely, which is the failure this
# whole module exists to prevent.
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
    - len(MARKER_TEMPLATE.format(family="", entity=""))
    - 1
    - MARKER_GROWTH_RESERVE
)


def normalise_family(project_name: str) -> str:
    """The family slug for a DBML `Project` name.

    MEASURED against the shipped catalogue, not assumed: for all 31 families
    the DBML `Project` name is the solution directory name with underscores
    for hyphens (`Project routine_checks` in `solutions/routine-checks/`), so
    swapping them back makes the marker name the family the way the docs,
    the wizard and `catalogue.Solution.id` all name it. That parity is pinned
    by `test_template_standard.py`, so a new family that breaks it fails the
    build rather than emitting a family nobody can look up.

    `/` is folded too because the marker's grammar is `family/entity` and a
    separator inside the family would make it ambiguous to the reader that
    parses it back out.

    THE FOLD IS NOT INJECTIVE, and that is accepted rather than overlooked.
    `a_b`, `a/b` and `a-b` all become `a-b`, and a schema declaring
    `Project custom` is indistinguishable from one declaring no `Project` at
    all. Both are fail-OPEN: the marker is still present and the list is still
    discoverable, so the cost is a mis-attributed row in a report rather than
    a list missing from it. That is the right way round -- the failure this
    module exists to prevent is a list nobody can find, and no collision here
    can cause one. Making the fold injective (escaping, or refusing a name
    that collides) would add a build-time refusal for a problem no shipped
    family has: the catalogue sweep in `test_template_standard.py` pins all 31
    to distinct slugs.
    """
    slug = project_name.strip().replace("_", "-").replace("/", "-")
    return slug or UNNAMED_FAMILY


def family_for(schema: Schema) -> str:
    """The family a schema belongs to, from its DBML `Project` declaration."""
    return normalise_family(schema.project_name)


def marker_for(family: str, entity: str) -> str:
    """The exact marker text for one entity. The single spelling authority."""
    return MARKER_TEMPLATE.format(family=family, entity=entity)


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
    still reads back byte-identical, and still passes every deploy phase. So
    if the two cannot both fit, `ENTITY_NOTE_TOO_LONG_FOR_MARKER` refuses the
    note at build time and this never runs on one. The clamp here is a
    backstop, not the enforcement.

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
