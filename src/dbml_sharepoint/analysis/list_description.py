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

# The family recorded for a schema that declares no DBML `Project`. A
# hand-written schema is a perfectly ordinary input -- `dbml-sharepoint build`
# takes any DBML path -- and such a list must still be DISCOVERABLE even
# though its family is unknown. Losing the family name costs precision in a
# report; losing the marker loses the list entirely, which is the failure this
# whole module exists to prevent.
UNNAMED_FAMILY = "custom"


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
    """
    return DESCRIPTION_LIMIT - len(marker_for(family, entity)) - 1


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
    """
    marker = marker_for(family, entity)
    note = (table_note or "").strip()
    if not note:
        return marker
    return f"{note[:note_budget(family, entity)].rstrip()} {marker}"
