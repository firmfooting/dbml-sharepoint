# src/dbml_sharepoint/model/sections/_identity.py
"""`prefix`, `prefix_owner` and `previous_prefixes`.

The namespace every deployed object is named under. `prefix` is required
and its absence is a `MappingShapeError`; the owner is provenance, stamped
into the manifest.
"""

from typing import Any

from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.reading import optional_str, require_str
from dbml_sharepoint.model.sections.context import SectionContext


def read(sc: SectionContext) -> dict[str, Any]:
    # `required` names an absent prefix; a blank one titled every list "None" + its name.
    sc.required("prefix")
    prefix = require_str(sc.blocks, "prefix", "mapping")
    return {
        "prefix": prefix,
        "prefix_owner": optional_str(sc.blocks, "prefix_owner", "mapping") or "",
        "previous_prefixes": _parse_previous_prefixes(sc.block("previous_prefixes"), prefix),
    }


def _parse_previous_prefixes(declared: Any, current: Any) -> tuple[str, ...]:
    """`previous_prefixes`, refused when it repeats or names the current prefix."""
    if declared is None:
        return ()
    if not isinstance(declared, list) or not all(isinstance(p, str) for p in declared):
        raise MappingShapeError("previous_prefixes must be a list of strings")
    names: list[str] = declared
    seen: set[str] = set()
    for previous in names:
        if previous == current:
            raise MappingValueError(
                f"previous_prefixes names the current prefix {previous!r}; a prefix "
                f"that is still in use is not a previous one",
            )
        if previous in seen:
            raise MappingValueError(f"previous_prefixes names {previous!r} twice")
        seen.add(previous)
    return tuple(names)
