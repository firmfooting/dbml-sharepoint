# test/_raw_enum_readers.py
"""The AST walk behind the ratchet in `test_raw_enum_readers.py`.

`analysis/resolve.py::resolve()` is meant to be the one place that reads a
`folders.from_enum` or `groups[].from_enum` source before it has been
resolved against the schema. A module that reads `entity.folder_source`,
`perms.group_sources` or `perms.folder_policies` directly re-derives that
resolution somewhere else, which is exactly how the two ACL collections
Pieces 1-3 merged drifted apart in the first place.

`folder_policies` also names a field on `ResolvedMapping` itself
(`resolved.folder_policies`), so a walk keyed on attribute name alone cannot
tell that read apart from the raw `perms.folder_policies` without type
inference. It does not need to: nothing outside `analysis/resolve.py` reads
`resolved.folder_policies` on this branch, because Piece 3 moved every
consumer onto the `require_folder_policies` accessor. A future module that
reaches for the field directly, whichever object it hangs off, is exactly
what this walk should name, so it is named rather than resolved by teaching
the walk to tell the two apart.
"""

from __future__ import annotations

import ast
from pathlib import Path

#: The enum-source fields `resolve()` exists to be the sole raw reader of.
RATCHETED = frozenset({"group_sources", "folder_source", "folder_policies"})

#: The resolution mechanism, not debt. `resolve()` delegates to
#: `analysis/folders.py` and `analysis/groups.py`, and they are where the
#: reading actually happens, so listing them here is the design rather than
#: an allowlist entry that should shrink.
PERMITTED = frozenset({
    "dbml_sharepoint/analysis/resolve.py",
    "dbml_sharepoint/analysis/folders.py",
    "dbml_sharepoint/analysis/groups.py",
})


def _readers_in(source: str) -> set[str]:
    """The ratcheted names `source` reads off some object, in `Load` context.

    `Load` context is what separates a read from a keyword argument, a type
    annotation and an assignment target, all three of which mention the same
    name without reading it off an object. A chained read such as
    `bundle.mapping.permissions.group_sources` reports only the ratcheted
    attribute at the end of the chain: the others are not fields this walk
    is about.
    """
    tree = ast.parse(source)
    return {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in RATCHETED
        and isinstance(node.ctx, ast.Load)
    }


def modules_reading_raw_enum_sources(root: Path) -> set[str]:
    """Every `.py` module under `root` that reads a ratcheted field raw.

    Paths are relative to `root` (posix-separated, so the result is stable
    whichever platform this runs on) and `PERMITTED` is excluded before the
    caller ever sees it: those modules are the resolver itself, not
    violations recorded against it.
    """
    found: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in PERMITTED:
            continue
        if _readers_in(path.read_text(encoding="utf-8")):
            found.add(rel)
    return found
