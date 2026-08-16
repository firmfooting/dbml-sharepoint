# src/dbml_sharepoint/analysis/provenance.py
"""The provenance marker every provisioned object carries, and its grammar.

Three surfaces record provenance in a description: a site group, a list, and
a permission level. All three build their marker here, so a change to the
grammar reaches every surface at once and no two can drift.

The marker is what the deploy tests before adopting an object it did not
create, and what rollback tests before deleting one. Two properties make that
test sound, and both are enforced here rather than assumed:

SELF-REFERENTIAL. The marker names the object it belongs to, so a description
copied from one object to another no longer matches the second object's
expected marker. Argo CD reached the same design after off-the-shelf charts
copied its tracking label onto resources it then wrongly adopted.

PREFIX-FREE. `MARKER_TERMINATOR` ends the marker and is refused inside every
field the grammar interpolates, by the rules in `checks/_provenance.py`.
Given that, one marker is a substring of another only if the two are equal:
the terminator occurs once, at the end, so a containing match must align
terminators, and `MARKER_PREFIX` occurs only at position zero. Without the
refusal, `from risk.` matched inside `from risk.v2.` and family `risk` adopted
family `risk.v2`'s group.
"""

from typing import Final

#: The text every marker opens with. Changing it is not a cosmetic edit: it
#: is what a human greps for to find everything this tool provisioned.
MARKER_PREFIX: Final = "Provisioned by dbml-sharepoint"

#: Ends every marker, and is refused inside family, group, level and entity
#: names. That refusal is what makes the grammar prefix-free.
MARKER_TERMINATOR: Final = "."

#: What the grammar calls each object type, in the marker text.
LIST_KIND: Final = "list"
GROUP_KIND: Final = "group"
LEVEL_KIND: Final = "level"


def marker_for_object(*, kind: str, name: str, family: str | None) -> str:
    """The exact marker for one provisioned object. The single authority.

    `family` is None for the groups this tool owns rather than a family,
    which any family may adopt. That form stays prefix-free against the
    family form because the next word after the prefix differs: ` for`
    against ` from`.
    """
    scope = "" if family is None else f" from {family}"
    return f"{MARKER_PREFIX}{scope} for {kind} {name}{MARKER_TERMINATOR}"


def empty_marker_length(*, kind: str, family: str | None) -> int:
    """The marker's length with an empty name, for a description budget."""
    return len(marker_for_object(kind=kind, name="", family=family))
