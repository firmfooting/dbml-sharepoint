# test/_raw_enum_readers.py
"""The AST walk behind the ratchet in `test_raw_enum_readers.py`.

`analysis/resolve.py` is meant to be the only place a `from_enum` source is
read before it resolves, so any other reader re-derives that resolution
somewhere else. Reads and exemptions are both recorded per function, because
a roster of modules frees every later read in a file that already holds one.
`folder_policies` also names a `ResolvedMapping` field, and a read of that is
reported rather than told apart by the type inference that would take.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, is_dataclass
from pathlib import Path
from typing import NamedTuple

from dbml_sharepoint.analysis import resolve
from dbml_sharepoint.model import mapping_types

#: The enum-source fields `resolve()` exists to be the sole raw reader of.
RATCHETED = frozenset({"group_sources", "folder_source", "folder_policies"})

#: The resolution mechanism, not debt. `resolve()` delegates to
#: `analysis/folders.py` and `analysis/groups.py`, and they are where the
#: reading actually happens, so these entries are the design rather than an
#: allowlist that should shrink. Sites rather than modules, because none of
#: the three files is exclusively resolver internals: a function added to any
#: of them would otherwise re-resolve a raw source unwatched.
PERMITTED = frozenset({
    # One entity's declared policy block, which is the resolution itself.
    "dbml_sharepoint/analysis/folders.py::folder_policies::folder_policies",
    # Each declared source expanded into its groups, in declaration order.
    "dbml_sharepoint/analysis/groups.py::_ordered::group_sources",
    # The UNEXPANDED declarations, the only kind a caller holding no schema
    # can ask about, which is why the CLI calls this one directly.
    "dbml_sharepoint/analysis/groups.py::declaring_groups::group_sources",
    # Tells an entity with no policy block apart from an unresolved one.
    "dbml_sharepoint/analysis/resolve.py::ResolvedMapping.require_folder_policies::folder_policies",
    # Every entity's folder source, resolved once, here.
    "dbml_sharepoint/analysis/resolve.py::resolve::folder_source",
    # The group sources walked a second time, to name the ones that did not
    # resolve.
    "dbml_sharepoint/analysis/resolve.py::resolve::group_sources",
})

#: What a read outside any function is attributed to.
MODULE_SCOPE = "<module>"


#: The nodes that open a new qualified name. A read is recorded against the
#: innermost one holding it.
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def _positional_fields() -> dict[str, tuple[str, ...]]:
    """`__match_args__` per model class that carries a ratcheted field.

    Read off the live classes rather than written out here, so a field added
    to one of them moves the positions without this walk needing an edit.
    """
    found: dict[str, tuple[str, ...]] = {}
    for module in (mapping_types, resolve):
        for name, obj in vars(module).items():
            if not (isinstance(obj, type) and is_dataclass(obj)):
                continue
            match_args: tuple[str, ...] = getattr(obj, "__match_args__", ())
            if set(match_args) & RATCHETED:
                found[name] = match_args
    return found


#: Which field each position of a class pattern reads, by class name.
POSITIONAL_FIELDS = _positional_fields()


@dataclass
class _Found:
    """What one module's walk turned up.

    `functions` is every scope the module declares, whether it reads anything
    or not: it is what a recorded entry naming a renamed function is checked
    against, and that question cannot be asked from the reads alone.
    """

    reads: set[tuple[str, str]] = field(default_factory=set)
    functions: set[str] = field(default_factory=set)


def _pattern_class(node: ast.expr) -> str:
    """The class a pattern names, bare or reached through a module alias."""
    if isinstance(node, ast.Attribute):
        return node.attr
    return node.id if isinstance(node, ast.Name) else ""


def _getattr_field(node: ast.Call) -> str | None:
    """The field a literal `getattr(obj, "field")` reads, if it is one.

    Only the literal spelling is detectable: a `getattr` over a computed name
    is invisible to any static walk, here and in every linter.
    """
    if not (isinstance(node.func, ast.Name) and node.func.id == "getattr"):
        return None
    if len(node.args) < 2:
        return None
    literal = node.args[1]
    if isinstance(literal, ast.Constant) and isinstance(literal.value, str):
        return literal.value
    return None


def _fields_matched(node: ast.MatchClass) -> set[str]:
    """The ratcheted fields one `case Cls(...)` pattern reads.

    `case EntityMapping(folder_source=src)` spells the name as a plain string
    in `kwd_attrs`, which an `ast.Attribute` walk never sees. A POSITIONAL
    pattern spells it nowhere at all: `case EntityMapping(_, ..., source)`
    reads whatever `__match_args__` holds at that index, so the positions are
    resolved against the real class.
    """
    fields = set(node.kwd_attrs) & RATCHETED
    positions = POSITIONAL_FIELDS.get(_pattern_class(node.cls), ())
    return fields | (set(positions[: len(node.patterns)]) & RATCHETED)


def _fields_read(node: ast.AST) -> set[str]:
    """The ratcheted fields `node` itself reads, its children aside."""
    if isinstance(node, ast.Attribute):
        # `Load` context separates a read from a keyword argument, a type
        # annotation and an assignment target, none of which read a field.
        if node.attr in RATCHETED and isinstance(node.ctx, ast.Load):
            return {node.attr}
        return set()
    if isinstance(node, ast.MatchClass):
        return _fields_matched(node)
    if isinstance(node, ast.Call):
        name = _getattr_field(node)
        return {name} if name is not None and name in RATCHETED else set()
    if isinstance(node, ast.AugAssign):
        # `perms.group_sources += extra` reads the field before writing it,
        # and its target carries `Store` context rather than `Load`.
        target = node.target
        if isinstance(target, ast.Attribute) and target.attr in RATCHETED:
            return {target.attr}
    return set()


def _collect(node: ast.AST, scope: tuple[str, ...], found: _Found) -> None:
    """Walk `node`, carrying the qualified name its children sit under."""
    qualname = ".".join(scope) if scope else MODULE_SCOPE
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPES):
            nested = (*scope, child.name)
            found.functions.add(".".join(nested))
            _collect(child, nested, found)
            continue
        found.reads |= {(qualname, name) for name in _fields_read(child)}
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
    """One pass over `root`, answering all of the ratchet's questions."""

    #: `<module>::<scope>::<field>` for every raw read `PERMITTED` does not
    #: already account for.
    reads: set[str]
    #: Every `<module>::<scope>::<field>` a recorded entry could name, so an
    #: entry whose function was renamed reports as stale rather than as a
    #: violation that quietly stopped being checked.
    sites: set[str]
    #: The `PERMITTED` sites this pass found actually reading, so an entry
    #: that has stopped reading is visible rather than exempting nothing.
    exempted: set[str]


def scan(root: Path) -> Scan:
    """Walk every `.py` module under `root`, the resolver's own included.

    Paths are relative to `root` (posix-separated, so the result is stable
    whichever platform this runs on). `PERMITTED` is subtracted site by site
    rather than module by module, so a read the resolver does not already do
    is reported even when it sits in `analysis/resolve.py` itself.
    """
    reads: set[str] = set()
    sites: set[str] = set()
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).as_posix()
        found = _walk(path.read_text(encoding="utf-8"))
        reads |= {f"{rel}::{scope}::{name}" for scope, name in found.reads}
        for scope in {MODULE_SCOPE, *found.functions}:
            sites |= {f"{rel}::{scope}::{name}" for name in RATCHETED}
    return Scan(reads=reads - PERMITTED, sites=sites, exempted=reads & PERMITTED)
