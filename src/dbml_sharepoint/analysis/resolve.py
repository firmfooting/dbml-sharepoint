# src/dbml_sharepoint/analysis/resolve.py
"""Resolve every enum-sourced mapping section once, at the boundary.

`entities.<name>.folders` and `groups[].from_enum` are both written against a
schema enum and resolved by `analysis/folders.py` and `analysis/groups.py`.
Each of those already offers a strict resolver (raise on an unknown enum) and
a lenient one (drop that source, keep the rest), because a generator and a
check need different behaviour for the same defect: a build must never
silently omit a declared group or folder, but a check must keep judging every
OTHER group and folder while the misspelling itself is reported by its own
rule.

This module does not choose between the two. It resolves LENIENTLY, once, and
records what it could not resolve, so the difference between a generator's
needs and a check's becomes what a caller does with one field (`unresolved`)
rather than which function it called. `ResolvedMapping.require_resolved`
gives a generator the strict behaviour back, raising the same error types
the strict resolvers raise today.

Nothing here imports a check, so a generator can read it.
"""

from collections.abc import Callable, Iterable
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from functools import wraps
from inspect import signature

from dbml_sharepoint.analysis.folders import (
    UnknownFolderEnumError,
    declared_folders,
    folder_policies,
)
from dbml_sharepoint.analysis.groups import UnknownGroupEnumError, resolvable_groups
from dbml_sharepoint.model.mapping_types import (
    ListPermissionPolicy,
    Mapping,
    MappingBundle,
    SiteGroup,
)
from dbml_sharepoint.model.parser import Schema


class MismatchedResolutionError(ValueError):
    """A `ResolvedMapping` that was not built from the inputs it arrived with.

    Every consumer of a resolution also takes the schema and bundle it is
    meant to describe, then combines the two: lists and columns from the
    schema, folders, groups and ACL policies from the resolution. A
    resolution built from a DIFFERENT mapping answers every one of those
    reads, so the build emits a deploy script that provisions one mapping's
    lists with another's permissions, passes every phase and reads back
    clean. Nothing downstream can see it, which is why this refuses rather
    than reconciles.

    `ValueError` because that is what `pipeline.execute_report` catches, so
    a refusal here clears a previously generated pack instead of leaving a
    stale one looking current behind a traceback.
    """

    def __init__(self, detail: str) -> None:
        super().__init__(
            "this ResolvedMapping was not built from the inputs it was passed "
            f"with: {detail}. Build one for these inputs with "
            "analysis.resolve.resolve().",
        )
        self.detail = detail


@dataclass(frozen=True)
class UnresolvedEnum:
    """One `from_enum` source naming an enum the schema does not declare.

    `entity` is the entity whose `folders` named it, for a folder source.
    It is `None` for a `groups[].from_enum` source, which is not scoped to
    any one entity. One shape carries both rather than a tagged type per
    source, because nothing downstream asks for more than this: the finding
    each source's own rule reports (`FOLDER_ENUM_UNKNOWN`,
    `GROUP_ENUM_UNKNOWN`) builds its message from the enum name alone, and
    where an entity is part of that message the check already has it from
    the loop that found the source, not from this record.
    """

    enum: str
    entity: str | None = None


@dataclass(frozen=True)
class ResolvedMapping:
    """Every enum source in a mapping, resolved once against a schema.

    Built by `resolve()`, always leniently: a folder or group source naming
    an enum the schema does not declare is left out of the resolved fields
    below and recorded in `unresolved` instead of raised, so one bad
    `from_enum` does not stop every OTHER group or folder from being judged.
    A caller that must fail closed instead -- a generator, which must never
    silently omit a declared group or folder -- calls `require_resolved()`
    first.

    `folders` and `folder_policies` key by entity name and agree with each
    other on what "no answer" means: an entity ABSENT from either is one
    whose folder source could not be resolved (recorded in `unresolved`); an
    entity PRESENT with an empty tuple is one that resolved and declares no
    folders. An entity that never writes a `folders:` key at all falls into
    the second case, never the first: `EntityMapping.folder_source` defaults
    to `()`, which `declared_folders` resolves to no folders without ever
    raising. So every entity in the mapping is a key in both `folders` and
    `folder_policies`, except the ones actually unresolved.

    A caller that has NOT called `require_resolved()` reads one entity
    through `require_folders` or `require_folder_policies` rather than by
    subscript: a subscript answers an unresolved entity with a bare
    `KeyError`, which is not a `ValueError` and so escapes the handlers that
    catch the named errors raised everywhere else here.
    """

    #: The mapping this was resolved from, so a consumer needs no second
    #: parameter for the many fields that have nothing to do with enums.
    #: That leaves the raw enum-source fields reachable through it, which is
    #: what Piece 4's ratchet is for.
    mapping: Mapping
    #: The schema's own enums, keyed by name. Five call sites used to rebuild
    #: this same projection from `schema.enums`; built once here instead.
    enum_members: MappingABC[str, tuple[str, ...]]
    folders: MappingABC[str, tuple[str, ...]]
    folder_policies: MappingABC[str, tuple[tuple[str, ListPermissionPolicy], ...]]
    #: Every group that resolved, literal and enum-generated, in declaration
    #: order -- `analysis/groups.py::_ordered`'s order, not re-derived here.
    groups: tuple[SiteGroup, ...]
    unresolved: tuple[UnresolvedEnum, ...] = ()
    #: What `resolve()` read off `mapping`, snapshotted at construction, so
    #: a later edit to that same mutable object is a difference and not one
    #: pointer. Compared by `require_matching_resolution`.
    consumed: MappingABC[str, str] = field(
        default_factory=dict, init=False, repr=False,
    )

    def __post_init__(self) -> None:
        # Taken here rather than in `resolve()`, so a hand-built resolution
        # carries one too and the guard has something to compare.
        object.__setattr__(self, "consumed", _consumed_inputs(self.mapping))

    def require_resolved(self) -> None:
        """Raise what the strict resolvers raise today, for a generator.

        Raises on the FIRST unresolved source: `UnknownFolderEnumError` for
        a folder source, `UnknownGroupEnumError` for a group source, each
        carrying the same `.enum` the strict `declared_folders` and
        `declared_groups` raise today. An existing `except
        UnknownFolderEnumError` therefore still catches it, and a finding
        that formats its message off `err.enum` (`_library.py` does exactly
        this) reads the same whichever resolver raised it.

        A no-op when nothing is unresolved.
        """
        if not self.unresolved:
            return
        first = self.unresolved[0]
        if first.entity is not None:
            raise UnknownFolderEnumError(first.enum)
        raise UnknownGroupEnumError(first.enum)

    def require_folders(self, entity: str) -> tuple[str, ...]:
        """`folders[entity]`, raising the named error rather than `KeyError`.

        The strict read, for a caller already scoped to entities it knows
        this build touches and which therefore wants one entity's defect and
        not the whole mapping's. Subscripting `folders` directly answers a
        `KeyError`, which is a `LookupError` and not a `ValueError`, so it
        walks straight through `pipeline.execute_report`'s handler and skips
        the path that clears a previously generated pack, leaving a stale
        report looking current behind an unhandled traceback.
        `UnknownFolderEnumError` is both bases, which is why it has both.

        An entity this mapping does not declare is still a `KeyError`: that
        is a caller bug about a name, not a defect in an enum, and blaming
        it on one would name an enum nobody wrote.
        """
        folders = self.folders.get(entity)
        if folders is not None:
            return folders
        unknown = next(
            (item.enum for item in self.unresolved if item.entity == entity), None,
        )
        if unknown is None:
            raise KeyError(entity)
        raise UnknownFolderEnumError(unknown)

    def require_folder_policies(
        self, entity: str,
    ) -> tuple[tuple[str, ListPermissionPolicy], ...]:
        """Every (folder, policy) `entity` declares, strict where it matters.

        Scoped exactly as `analysis/folders.py::folder_policies` was: an
        entity with no `list_permissions.folders` entry contributes no folder
        assignments whatever its folder source resolves to, so answering `()`
        there is the correct answer and not a default papering over an
        unknown. Where the answer DOES depend on an enum that did not
        resolve, this raises `UnknownFolderEnumError` as `require_folders`
        does, rather than the `KeyError` a direct subscript gives.
        """
        policies = self.folder_policies.get(entity)
        if policies is not None:
            return policies
        perms = self.mapping.permissions
        if perms is not None and entity in perms.folder_policies:
            self.require_folders(entity)
        return ()


def resolve(schema: Schema, mapping: Mapping) -> ResolvedMapping:
    """Resolve `mapping`'s folders, folder policies and groups against `schema`.

    Lenient, as `ResolvedMapping` describes: an entity or group source naming
    an enum the schema does not declare is left out of the resolved fields
    and appended to `unresolved` rather than raised. Folders are resolved per
    entity, in `mapping.entities` order; groups are resolved once via
    `resolvable_groups`, which already leaves out only the sources it cannot
    resolve, and `mapping.permissions.group_sources` is then walked once more
    to name which of those, if any, that was.
    """
    enum_members = enum_members_of(schema)
    unresolved: list[UnresolvedEnum] = []

    folders: dict[str, tuple[str, ...]] = {}
    policies: dict[str, tuple[tuple[str, ListPermissionPolicy], ...]] = {}
    perms = mapping.permissions
    for entity_name, entity in mapping.entities.items():
        try:
            folders[entity_name] = declared_folders(entity.folder_source, enum_members)
        except UnknownFolderEnumError as err:
            unresolved.append(UnresolvedEnum(enum=err.enum, entity=entity_name))
            continue
        policies[entity_name] = folder_policies(
            entity_name, entity.folder_source, perms, enum_members,
        )

    groups = resolvable_groups(perms, enum_members)
    if perms is not None:
        unresolved.extend(
            UnresolvedEnum(enum=source.enum)
            for source in perms.group_sources
            if source.enum not in enum_members
        )

    return ResolvedMapping(
        mapping=mapping,
        enum_members=enum_members,
        folders=folders,
        folder_policies=policies,
        groups=groups,
        unresolved=tuple(unresolved),
    )


def enum_members_of(schema: Schema) -> dict[str, tuple[str, ...]]:
    """`schema`'s enums as `ResolvedMapping.enum_members`, one derivation.

    Public because the guard below compares a resolution's copy against a
    freshly derived one, and a second spelling of this projection is exactly
    the drift that comparison exists to catch.
    """
    return {enum.name: tuple(enum.members) for enum in schema.enums}


def _consumed_inputs(mapping: Mapping) -> dict[str, str]:
    """Exactly the mapping fields `resolve()` reads, as comparable text.

    Scoped to what the resolution consumes rather than to the whole
    `Mapping`, because a guard that refuses edits the resolution cannot see
    gets suppressed by its callers. Held as `repr` because `Mapping` and
    `PermissionsConfig` are both mutable, so keeping the objects themselves
    would compare a later edit against itself.
    """
    perms = mapping.permissions
    if perms is None:
        blocks = groups = sources = repr(None)
    else:
        # Read by key, so the order the author wrote the blocks in is not a
        # change this resolution can see.
        ordered = {name: perms.folder_policies[name] for name in sorted(perms.folder_policies)}
        blocks, groups, sources = repr(ordered), repr(list(perms.groups)), repr(perms.group_sources)
    return {
        "folder sources": repr(
            [(name, entity.folder_source) for name, entity in mapping.entities.items()],
        ),
        "folder policies": blocks,
        "groups": groups,
        "group sources": sources,
    }


def require_matching_resolution(
    resolved: ResolvedMapping,
    bundle: MappingBundle,
    schema: Schema | None = None,
) -> None:
    """Refuse a resolution that was not built from these same inputs.

    The mapping is compared first by IDENTITY, because `ResolvedMapping.mapping`
    is the very object `resolve()` read, and then on `consumed`, the snapshot
    of what that read took. `Mapping` is not frozen, so a caller that resolves,
    edits the same object and then builds holds the pointer while `folders`,
    `folder_policies` and `groups` still answer with the pre-edit values, and
    the build combines the current bundle with stale permissions.

    The schema is compared on `enum_members`, which is the whole of what a
    resolution takes from a schema, so two schemas differing only in ways
    the resolution cannot see are correctly accepted.
    """
    if resolved.mapping is not bundle.mapping:
        raise MismatchedResolutionError("its mapping is a different object")
    require_current_resolution(resolved)
    if schema is not None and resolved.enum_members != enum_members_of(schema):
        raise MismatchedResolutionError("its enum members are not this schema's")


def require_current_resolution(resolved: ResolvedMapping) -> None:
    """Refuse a resolution whose mapping was edited after it was taken.

    The half of `require_matching_resolution` that needs no bundle, so the
    public helpers taking a resolution ALONE can run it. `guards_resolution`
    cannot reach those: it matches arguments by type and fails closed when no
    bundle is supplied, so decorating them would refuse every legitimate call.
    Without this they mix a caller's current `mapping.permissions` with the
    cached `resolved.groups`, which is the staleness the snapshot exists to
    catch.
    """
    current = _consumed_inputs(resolved.mapping)
    changed = sorted(
        name for name, value in current.items() if value != resolved.consumed.get(name)
    )
    if changed:
        raise MismatchedResolutionError(
            f"its {', '.join(changed)} changed after it was resolved",
        )


def _argument_of[T](supplied: Iterable[object], kind: type[T]) -> T | None:
    """The first argument that IS a `kind`, or None."""
    return next((value for value in supplied if isinstance(value, kind)), None)


def guards_resolution[**P, R](fn: Callable[P, R]) -> Callable[P, R]:
    """Run `require_matching_resolution` before every call of `fn`.

    A decorator rather than a line inside each consumer: eleven public
    functions take a resolution alongside the bundle it must describe, under
    four different parameter names, and a guard written out at each would be
    eleven copies of the same two comparisons with eleven chances to be left
    out. Arguments are matched by TYPE, so `bundle.emit_bundle`'s
    `mapping_bundle` is covered without this module naming it.

    Fails closed when a decorated call supplies no bundle at all, rather
    than passing the call through unchecked: a guard that silently stops
    guarding is the defect class this repository exists to close.
    `test_resolve.py::test_every_consumer_taking_both_is_guarded` covers the
    other half, a consumer added without the decorator.
    """
    sig = signature(fn)

    @wraps(fn)
    def guarded(*args: P.args, **kwargs: P.kwargs) -> R:
        supplied = list(sig.bind(*args, **kwargs).arguments.values())
        resolved = _argument_of(supplied, ResolvedMapping)
        bundle = _argument_of(supplied, MappingBundle)
        if resolved is None or bundle is None:
            raise MismatchedResolutionError(
                f"{fn.__qualname__} was called with no MappingBundle to check "
                "it against",
            )
        require_matching_resolution(resolved, bundle, _argument_of(supplied, Schema))
        return fn(*args, **kwargs)

    # Read by the static test above. A function's __dict__ is typed, an invented attribute is not.
    guarded.__dict__["__resolution_guarded__"] = True
    return guarded
