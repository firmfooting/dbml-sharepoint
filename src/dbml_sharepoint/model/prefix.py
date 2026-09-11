# src/dbml_sharepoint/model/prefix.py
"""The `{prefix}` placeholder and the names it expands to.

`prefix:` names every deployed list, and a group or permission level takes
the same namespace through a placeholder at the start of its name, so one
rewrite of the prefix renames all three. The identity family reads the
prefix and the permissions family expands the names, so the expansion lives
in a public module rather than in either of them.
"""

from collections.abc import Sequence

#: The placeholder a group or permission-level name may open with. It expands
#: to the list prefix STEM (the prefix without its trailing underscore), so
#: one `prefix:` rewrite renames the groups and levels with the lists. The
#: marker is computed from the expanded name; provenance never sees this.
PREFIX_PLACEHOLDER = "{prefix}"


def prefix_stem(prefix: str) -> str:
    """`RR_` names lists `RR_Risk` and groups `RR Risk Managers`: the stem."""
    return prefix.removesuffix("_")


def expand_prefix(value: str, prefix: str, context: str) -> str:
    """Replace a leading `{prefix}` with the stem; drop it and its space when empty.

    Refused anywhere but the start: the stem is a namespace and a namespace
    goes first, which is also what the fleet's own naming test checks.
    """
    if PREFIX_PLACEHOLDER not in value:
        return value
    if not value.startswith(PREFIX_PLACEHOLDER) or value.count(PREFIX_PLACEHOLDER) > 1:
        raise ValueError(
            f"{context}: the {PREFIX_PLACEHOLDER} placeholder may appear once, at the "
            f"start of the name, got {value!r}",
        )
    rest = value[len(PREFIX_PLACEHOLDER):]
    stem = prefix_stem(prefix)
    return stem + rest if stem else rest.lstrip(" ")


def previous_object_names(
    raw_name: str,
    raw_previous: Sequence[str],
    prefix: str,
    previous_prefixes: Sequence[str],
    context: str,
) -> tuple[str, ...]:
    """Every name a group or level may be found under on an unmigrated site.

    Each base name (the current one and every `renamed_from`) is expanded
    under the current stem and then under every previous stem; a literal base
    with no placeholder is taken once. The current name is never a candidate
    and nothing is listed twice.
    """
    current = expand_prefix(raw_name, prefix, context)
    out: list[str] = []
    for base in (raw_name, *raw_previous):
        stems = [prefix, *previous_prefixes] if PREFIX_PLACEHOLDER in base else [prefix]
        for stem_prefix in stems:
            name = expand_prefix(base, stem_prefix, context)
            if name == current or name in out:
                continue
            out.append(name)
    return tuple(out)
