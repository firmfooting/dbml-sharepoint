# test/_raw_enum_readers.py
"""The AST walk behind the ratchet in `test_raw_enum_readers.py`.

`analysis/resolve.py` is meant to be the only place a `from_enum` source is
read before it resolves, so any other reader re-derives that resolution
somewhere else. Reads and exemptions are both recorded per function, because
a roster of modules frees every later read in a file that already holds one.
`folder_policies` also names a `ResolvedMapping` field, and `self.folder_policies`
inside that class is told apart from a raw read by its receiver rather than by
the type inference that would take, so the exemption for the raw read beside it
retires when that read goes.
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
    # The declared blocks, which tell an entity with no policy block apart
    # from an unresolved one. The resolved field this function reads beside
    # them is not this entry, so deleting the raw read retires it.
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


def _resolution_fields() -> dict[str, frozenset[str]]:
    """The ratcheted names each `analysis/resolve.py` class holds ALREADY
    resolved, by class name.

    Read off the live classes, and only that module's own, so the model class
    that actually carries a raw source is not covered by its own name.
    """
    found: dict[str, frozenset[str]] = {}
    for name, obj in vars(resolve).items():
        if not (isinstance(obj, type) and is_dataclass(obj)):
            continue
        if obj.__module__ != resolve.__name__:
            continue
        own = frozenset(obj.__dataclass_fields__) & RATCHETED
        if own:
            found[name] = own
    return found


#: Which ratcheted names are a resolution's own answer, by the class holding
#: them. `self.folder_policies` on one of these is that answer, not a source.
RESOLUTION_FIELDS = _resolution_fields()


@dataclass
class _Found:
    """What one module's walk turned up.

    `functions` is every scope the module declares, whether it reads anything
    or not: it is what a recorded entry naming a renamed function is checked
    against, and that question cannot be asked from the reads alone.
    """

    reads: set[tuple[str, str]] = field(default_factory=set)
    functions: set[str] = field(default_factory=set)


def _import_aliases(tree: ast.Module) -> dict[str, str]:
    """Every class name a module's `from ... import` binds, to the name it
    was imported under.

    `from ... import PermissionsConfig as PC` binds the model class under a
    name `POSITIONAL_FIELDS` does not hold, and a lookup on `PC` alone finds
    no positions. A plain `import` is not collected: it binds a module, and a
    pattern reaching a class through one spells the class name itself.
    """
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            aliases[alias.asname or alias.name] = alias.name
    return aliases


def _pattern_class(node: ast.expr, aliases: dict[str, str]) -> str:
    """The class a pattern names, aliased or reached through a module."""
    if isinstance(node, ast.Attribute):
        return node.attr
    return aliases.get(node.id, node.id) if isinstance(node, ast.Name) else ""


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


def _fields_matched(node: ast.MatchClass, aliases: dict[str, str]) -> set[str]:
    """The ratcheted fields one `case Cls(...)` pattern reads.

    `case EntityMapping(folder_source=src)` spells the name as a plain string
    in `kwd_attrs`, which an `ast.Attribute` walk never sees. A POSITIONAL
    pattern spells it nowhere at all: `case EntityMapping(_, ..., source)`
    reads whatever `__match_args__` holds at that index, so the positions are
    resolved against the real class, through `aliases` where the module
    imported it under another name.

    A positional pattern on a class this walk cannot place is reported as
    reading every ratcheted field, so it lands on the allowlist rather than
    passing unseen: a ratchet that fails open is not a ratchet. A pattern
    naming its fields as keywords needs none of this, because it spells
    exactly what it reads.
    """
    fields = set(node.kwd_attrs) & RATCHETED
    if not node.patterns:
        return fields
    positions = POSITIONAL_FIELDS.get(_pattern_class(node.cls, aliases))
    if positions is None:
        return fields | set(RATCHETED)
    return fields | (set(positions[: len(node.patterns)]) & RATCHETED)


def _reads_its_own_answer(node: ast.Attribute, owner: str) -> bool:
    """Whether `node` is a resolution reading its OWN resolved field.

    `ResolvedMapping.require_folder_policies` reads `self.folder_policies`,
    the resolved answer, and `perms.folder_policies`, the raw source. Keyed by
    field name alone the two collapse into one site, so a single exemption
    covers both and outlives whichever read goes first. The receiver tells
    them apart without the type inference the module docstring rules out.
    """
    return (
        isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr in RESOLUTION_FIELDS.get(owner, frozenset())
    )


def _fields_read(node: ast.AST, aliases: dict[str, str], owner: str) -> set[str]:
    """The ratcheted fields `node` itself reads, its children aside."""
    if isinstance(node, ast.Attribute):
        # `Load` context separates a read from a keyword argument, a type
        # annotation and an assignment target, none of which read a field.
        reads = node.attr in RATCHETED and isinstance(node.ctx, ast.Load)
        if reads and not _reads_its_own_answer(node, owner):
            return {node.attr}
        return set()
    if isinstance(node, ast.MatchClass):
        return _fields_matched(node, aliases)
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


def _collect(
    node: ast.AST,
    scope: tuple[str, ...],
    found: _Found,
    aliases: dict[str, str],
    owner: str,
) -> None:
    """Walk `node`, carrying the qualified name its children sit under and the
    class they are declared in."""
    qualname = ".".join(scope) if scope else MODULE_SCOPE
    for child in ast.iter_child_nodes(node):
        if isinstance(child, _SCOPES):
            nested = (*scope, child.name)
            found.functions.add(".".join(nested))
            holder = child.name if isinstance(child, ast.ClassDef) else owner
            _collect(child, nested, found, aliases, holder)
            continue
        found.reads |= {(qualname, name) for name in _fields_read(child, aliases, owner)}
        _collect(child, scope, found, aliases, owner)


def _walk(source: str) -> _Found:
    tree = ast.parse(source)
    found = _Found()
    _collect(tree, (), found, _import_aliases(tree), "")
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
