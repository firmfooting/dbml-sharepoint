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
from collections import Counter
from dataclasses import dataclass, field, is_dataclass, replace
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
    # The same three sources snapshotted as text, so an edit to the mapping
    # after it was resolved is a difference rather than one pointer compare.
    "dbml_sharepoint/analysis/resolve.py::_consumed_inputs::folder_policies",
    "dbml_sharepoint/analysis/resolve.py::_consumed_inputs::folder_source",
    "dbml_sharepoint/analysis/resolve.py::_consumed_inputs::group_sources",
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

#: The only module whose classes those names belong to, path-relative to the
#: scanned root.
RESOLVER_MODULE = "dbml_sharepoint/analysis/resolve.py"


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
    bound: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        for alias in node.names:
            bound.setdefault(alias.asname or alias.name, set()).add(alias.name)
    # A name two imports bind differently, or that is assigned, looped over or
    # taken as a parameter anywhere, is UNPLACEABLE: `_fields_matched` then
    # reports every ratcheted field.
    rebound = _bound_names(tree)
    return {
        name: next(iter(classes))
        if len(classes) == 1 and not rebound[name]
        else _SHADOWED
        for name, classes in bound.items()
    }


def _bound_names(tree: ast.AST) -> Counter[str]:
    """How many times each name is bound under `tree` by anything but a
    `from ... import`: assignment, loop, `with`, `except`, `match`, walrus,
    parameter, `def`, `class` or plain `import`."""
    count: Counter[str] = Counter()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load):
            count[node.id] += 1
        elif isinstance(node, ast.arg):
            count[node.arg] += 1
        elif isinstance(node, (*_SCOPES, ast.ExceptHandler, ast.MatchAs, ast.MatchStar)):
            if node.name:
                count[node.name] += 1
        elif isinstance(node, ast.MatchMapping) and node.rest:
            count[node.rest] += 1
        elif isinstance(node, ast.Import):
            for alias in node.names:
                count[(alias.asname or alias.name).split(".")[0]] += 1
    return count


def _resolver_imports(tree: ast.Module) -> set[str]:
    """Local names bound by importing from `analysis.resolve`."""
    return {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("analysis.resolve")
        for alias in node.names
    }


#: What an import name bound to more than one class resolves to. No class is
#: called this, so every lookup on it misses and the pattern fails closed.
_SHADOWED = "<shadowed>"


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


def _fields_matched(
    node: ast.MatchClass, aliases: dict[str, str], resolved: set[str],
) -> set[str]:
    """The ratcheted fields one `case Cls(...)` pattern reads, which an
    `ast.Attribute` walk never sees because a pattern spells them in
    `kwd_attrs` or, positionally, nowhere at all."""
    cls = _pattern_class(node.cls, aliases)
    # A class `resolve.py` declares holds its ratcheted names already
    # resolved, so matching them is the answer and not a raw read. Only a bare
    # name proven to be that class counts; anything else fails closed.
    own = (
        RESOLUTION_FIELDS.get(cls, frozenset())
        if isinstance(node.cls, ast.Name) and node.cls.id in resolved
        else frozenset()
    )
    fields = (set(node.kwd_attrs) & RATCHETED) - own
    if not node.patterns:
        return fields
    positions = POSITIONAL_FIELDS.get(cls)
    if positions is None:
        # A class this walk cannot place reports every field, because a
        # ratchet that fails open is not a ratchet.
        return fields | set(RATCHETED)
    return fields | ((set(positions[: len(node.patterns)]) & RATCHETED) - own)


def _reads_its_own_answer(
    node: ast.Attribute, owner: str, module: str, trusted: bool,
) -> bool:
    """Whether `node` is a resolution reading its OWN resolved field.

    `ResolvedMapping.require_folder_policies` reads `self.folder_policies`,
    the resolved answer, and `perms.folder_policies`, the raw source. Keyed by
    field name alone the two collapse into one site, so a single exemption
    covers both and outlives whichever read goes first. The receiver tells
    them apart without the type inference the module docstring rules out.

    Scoped to the resolver's own module, because the class name alone is not
    the class: another module declaring its own `ResolvedMapping` would have
    every `self.folder_policies` in it suppressed. `trusted` is true only for
    a method whose `self` parameter is never rebound.
    """
    return (
        trusted
        and module == RESOLVER_MODULE
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
        and node.attr in RESOLUTION_FIELDS.get(owner, frozenset())
    )


def _fields_read(node: ast.AST, ctx: _Ctx) -> set[str]:
    """The ratcheted fields `node` itself reads, its children aside."""
    if isinstance(node, ast.Attribute):
        # `Load` context separates a read from a keyword argument, a type
        # annotation and an assignment target, none of which read a field.
        reads = node.attr in RATCHETED and isinstance(node.ctx, ast.Load)
        if reads and not _reads_its_own_answer(
            node, ctx.owner, ctx.module, ctx.trusted,
        ):
            return {node.attr}
        return set()
    if isinstance(node, ast.MatchClass):
        return _fields_matched(node, ctx.aliases, ctx.resolved)
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


@dataclass(frozen=True)
class _Ctx:
    """What a read is judged against: the module's import facts, the class it
    sits in and whether `self` there is provably the method instance."""

    aliases: dict[str, str]
    resolved: set[str]
    module: str
    owner: str = ""
    trusted: bool = False


def _method_self_is_intact(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Whether `self` is `fn`'s first parameter and nothing rebinds it."""
    first = fn.args.posonlyargs + fn.args.args
    return bool(first) and first[0].arg == "self" and _bound_names(fn)["self"] == 1


def _outer_parts(node: ast.AST) -> list[ast.AST]:
    """What a `def` or `class` evaluates in the scope holding it: decorators,
    defaults, annotations, bases and keywords. Only its body is the inner scope."""
    if isinstance(node, ast.ClassDef):
        return [*node.decorator_list, *node.bases, *node.keywords]
    assert isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    return [*node.decorator_list, node.args, *([node.returns] if node.returns else [])]


def _collect(
    node: ast.AST, scope: tuple[str, ...], found: _Found, ctx: _Ctx,
) -> None:
    """Walk `node`'s children under the qualified name `scope`."""
    for child in ast.iter_child_nodes(node):
        _visit(child, isinstance(node, ast.ClassDef), scope, found, ctx)


def _visit(
    child: ast.AST, in_class: bool, scope: tuple[str, ...], found: _Found, ctx: _Ctx,
) -> None:
    """Record `child`'s reads, opening a new scope for a `def` or `class`."""
    qualname = ".".join(scope) if scope else MODULE_SCOPE
    if not isinstance(child, _SCOPES):
        found.reads |= {(qualname, name) for name in _fields_read(child, ctx)}
        _collect(child, scope, found, ctx)
        return
    for part in _outer_parts(child):
        _visit(part, False, scope, found, ctx)
    nested = (*scope, child.name)
    found.functions.add(".".join(nested))
    if isinstance(child, ast.ClassDef):
        inner = replace(ctx, owner=child.name, trusted=False)
    else:
        # Only a method directly in a class can trust its `self`; a nested
        # helper may take its own.
        inner = replace(ctx, trusted=in_class and _method_self_is_intact(child))
    for stmt in child.body:
        _visit(stmt, isinstance(child, ast.ClassDef), nested, found, inner)


def _walk(source: str, module: str = "") -> _Found:
    tree = ast.parse(source)
    found = _Found()
    ctx = _Ctx(_import_aliases(tree), _resolver_imports(tree), module)
    if module == RESOLVER_MODULE:
        ctx = replace(ctx, resolved=set(RESOLUTION_FIELDS))
    _collect(tree, (), found, ctx)
    return found


def _reads_in(source: str, module: str = RESOLVER_MODULE) -> set[tuple[str, str]]:
    """(scope, ratcheted field) for every raw read in `source`.

    A chained read such as `bundle.mapping.permissions.group_sources` reports
    only the ratcheted attribute at the end of the chain: the others are not
    fields this walk is about.
    """
    return _walk(source, module).reads


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
        found = _walk(path.read_text(encoding="utf-8"), rel)
        reads |= {f"{rel}::{scope}::{name}" for scope, name in found.reads}
        for scope in {MODULE_SCOPE, *found.functions}:
            sites |= {f"{rel}::{scope}::{name}" for name in RATCHETED}
    return Scan(reads=reads - PERMITTED, sites=sites, exempted=reads & PERMITTED)
