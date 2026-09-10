# src/dbml_sharepoint/model/sections/_identity.py
"""`prefix`, `prefix_owner` and `previous_prefixes`.

The namespace every deployed object is named under. `prefix` is required
and stays the KeyError an absent key has always raised; the owner is
provenance, stamped into the manifest.
"""

from typing import Any

from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    prefix = sc.required("prefix")
    return {
        "prefix": prefix,
        "prefix_owner": sc.block("prefix_owner", ""),
        "previous_prefixes": _parse_previous_prefixes(sc.block("previous_prefixes"), prefix),
    }


def _parse_previous_prefixes(declared: Any, current: Any) -> tuple[str, ...]:
    """`previous_prefixes`, refused when it repeats or names the current prefix."""
    if declared is None:
        return ()
    if not isinstance(declared, list) or not all(isinstance(p, str) for p in declared):
        raise ValueError("previous_prefixes must be a list of strings")
    seen: set[str] = set()
    for previous in declared:
        if previous == current:
            raise ValueError(
                f"previous_prefixes names the current prefix {previous!r}; a prefix "
                f"that is still in use is not a previous one",
            )
        if previous in seen:
            raise ValueError(f"previous_prefixes names {previous!r} twice")
        seen.add(previous)
    return tuple(declared)
