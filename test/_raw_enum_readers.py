# test/_raw_enum_readers.py
"""The AST walk behind the ratchet in `test_raw_enum_readers.py`.

`analysis/resolve.py::resolve()` is meant to be the one place that reads a
`folders.from_enum` or `groups[].from_enum` source before it has been
resolved against the schema. A module that reads `entity.folder_source`,
`perms.group_sources` or `perms.folder_policies` directly re-derives that
resolution somewhere else, which is exactly how the two ACL collections
Pieces 1-3 merged drifted apart in the first place.

A read is recorded against the function holding it, not against its module.
A roster of modules exempts every later read in a file the moment one read in
it is justified, and `checks/_permissions.py` and `checks/_library.py` each
already hold justified reads, so the two files most likely to grow another
one were the two the gate had stopped watching.

`folder_policies` also names a field on `ResolvedMapping` itself
(`resolved.folder_policies`), so a walk keyed on attribute name alone cannot
tell that read apart from the raw `perms.folder_policies` without type
inference. It does not need to: nothing outside `analysis/resolve.py` reads
`resolved.folder_policies` on this branch, because Piece 3 moved every
consumer onto the `require_folder_policies` accessor. A future function that
reaches for the field directly, whichever object it hangs off, is exactly
what this walk should name, so it is named rather than resolved by teaching
the walk to tell the two apart.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import NamedTuple

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

#: What a read outside any function is attributed to.
MODULE_SCOPE = "<module>"


#: The nodes that open a new qualified name. A read is recorded against the
#: innermost one holding it.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


@dataclass
class _Found:
    """What one module's walk turned up.

    `functions` is every scope the module declares, whether it reads anything
    or not: it is what a recorded entry naming a renamed function is checked
    against, and that question cannot be asked from the reads alone.
    """

    reads: set[tuple[str, str]] = field(default_factory=set)
    functions: set[str] = field(default_factory=set)


def _collect(node: ast.AST, scope: tuple[str, ...], found: _Found) -> None:
    """Walk `node`, carrying the qualified name its children sit under."""
    qualname = ".".join(scope) if scope else MODULE_SCOPE
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPES):
            nested = (*scope, child.name)
            found.functions.add(".".join(nested))
            _collect(child, nested, found)
            continue
        # `Load` context separates a read from a keyword argument, a type
        # annotation and an assignment target, none of which read a field.
        if (
            isinstance(child, ast.Attribute)
            and child.attr in RATCHETED
            and isinstance(child.ctx, ast.Load)
        ):
            found.reads.add((qualname, child.attr))
        # `case EntityMapping(folder_source=src)` reads the field and spells
        # its name as a plain string, which the Attribute walk never sees.
        if isinstance(child, ast.MatchClass):
            found.reads |= {
                (qualname, name) for name in child.kwd_attrs if name in RATCHETED
            }
        _collect(child, scope, found)


def _walk(source: str) -> _Found:
    found = _Found()
    _collect(ast.parse(source), (), found)
    return found


def _reads_in(source: str) -> set[tuple[str, str]]:
    """(scope, ratcheted field) for every raw read in `source`.

    A chained read such as `bundle.mapping.permissions.group_sources` reports
    only the ratcheted attribute at the end of the chain: the others are not
    fields this walk is about.
    """
    return _walk(source).reads


class Scan(NamedTuple):
    """One pass over `root`, answering both of the ratchet's questions."""

    #: `<module>::<scope>::<field>` for every raw read found.
    reads: set[str]
    #: Every `<module>::<scope>::<field>` a recorded entry could name, so an
    #: entry whose function was renamed reports as stale rather than as a
    #: violation that quietly stopped being checked.
    sites: set[str]


def scan(root: Path) -> Scan:
    """Walk every `.py` module under `root` except the resolver's own.

    Paths are relative to `root` (posix-separated, so the result is stable
    whichever platform this runs on) and `PERMITTED` is excluded before the
    caller ever sees it: those modules are the resolver itself, not
    violations recorded against it.
    """
    reads: set[str] = set()
    sites: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        if rel in PERMITTED:
            continue
        found = _walk(path.read_text(encoding="utf-8"))
        reads |= {f"{rel}::{scope}::{name}" for scope, name in found.reads}
        for scope in {MODULE_SCOPE, *found.functions}:
            sites |= {f"{rel}::{scope}::{name}" for name in RATCHETED}
    return Scan(reads=reads, sites=sites)
