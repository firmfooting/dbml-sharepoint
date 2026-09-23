# test/test_raw_enum_readers.py
"""Only `analysis/resolve.py` may read a `from_enum` source before it resolves.

Pieces 1-3 merged `SCHEMA.list_assignments` and `SCHEMA.folder_assignments`
into one `SCHEMA.acl_scopes` and moved every enum-source resolution
(`entities.<name>.folders`, `groups[].from_enum`) into `analysis/resolve.py`.
Nothing stops a future rule or generator reaching past that boundary for
`entity.folder_source`, `perms.group_sources` or `perms.folder_policies`
directly, re-deriving the same resolution a second way -- which is the shape
of drift this whole piece exists to close. This is that gate.

See `_raw_enum_readers.py` for the walk and why `folder_policies` colliding
with a `ResolvedMapping` field name is not a problem it needs to solve.
"""

from _paths import PACKAGE
from _ratchet import Ratchet
from _raw_enum_readers import (
    PERMITTED,
    RATCHETED,
    _readers_in,
    modules_reading_raw_enum_sources,
)

#: `src/`, not `src/dbml_sharepoint/`: the universe the ratchet checks
#: recorded entries against, and what `PERMITTED`'s paths are spelled
#: relative to.
SRC = PACKAGE.parent


def test_the_walk_sees_a_read_off_a_raw_object() -> None:
    assert _readers_in("x = perms.folder_policies") == {"folder_policies"}


def test_the_walk_ignores_a_keyword_argument_of_the_same_name() -> None:
    """Constructing a mapping is not reading one.

    `EntityMapping(folder_source=...)` and an annotation both mention the
    name without reading the field off an object, and a gate that flagged
    them would push the loader onto its own allowlist for doing its job.
    """
    assert _readers_in("EntityMapping(folder_source=src)") == set()
    assert _readers_in("folder_source: FolderSource") == set()


def test_the_walk_ignores_an_assignment_to_the_field() -> None:
    assert _readers_in("obj.folder_source = src") == set()


def test_the_walk_sees_a_read_through_a_chain() -> None:
    assert _readers_in("n = bundle.mapping.permissions.group_sources") == {
        "group_sources",
    }


def test_the_walk_ignores_an_unrelated_attribute() -> None:
    """Only the three ratcheted names are ever reported, nothing else."""
    assert _readers_in("x = perms.levels") == set()


#: Modules outside the resolver that still read a raw enum source, with the
#: reason read off each one rather than assumed. A RATCHET: entries come
#: out when a module migrates onto `ResolvedMapping`, and one going in needs
#: a reason in the pull request.
#:
#: `checks/_library.py` reads `entity.folder_source` and `perms.folder_policies`
#: to judge the DECLARATION itself: whether a source was written at all
#: (`declared=bool(entity.folder_source)`), whether a `folders.from_enum`
#: name matches a column type the entity actually has
#: (`_folder_enum_is_this_entity_s`), and whether every
#: `list_permissions.folders` key names a real, folder-capable entity
#: (`_folder_permissions`). All three are questions about what was written,
#: independent of whether it resolves; the folder names a source produces
#: come from `vc.resolved.folders` already, and are not re-derived here.
#:
#: `permissions.py::requires_manage_permissions` reads `perms.folder_policies`
#: as a raw membership test ("did this entity declare a folder policy at
#: all"), because its own docstring requires it to stay exactly as lenient
#: as `resolved.groups` and never call `require_resolved()`: this answers a
#: `table_names`-scoped question and must not fail the whole mapping over an
#: entity the caller never asked about.
#:
#: `validator.py::_enums_used_by_mapping` reads `entity.folder_source` and
#: `perms.group_sources` to collect every enum a mapping source NAMES, so
#: `orphan_enum` is not reported against an enum a `folders.from_enum` or
#: `groups[].from_enum` depends on. It runs at the top of `validate_all`,
#: before `validate_against_mapping` builds a `ValidationContext` (and so
#: before any `ResolvedMapping` exists for this call), and it deliberately
#: wants the name a source WROTE rather than what it resolved to: a
#: misspelled source is still a source, and reading `resolved.groups` or
#: `resolved.folders` here would already have dropped it.
#:
#: `checks/_permissions.py` reads `perms.folder_policies` in
#: `_expanded_folder_policies` to walk every DECLARED policy block (paired
#: with `vc.resolved.folders` for the folder names it expands `{member}`
#: against), and `perms.group_sources` in `_enum_groups` to validate each
#: declared source's enum and template individually. Both need the raw list
#: because the check each one owns (`group_enum_unknown`, the folder
#: assignment checks) has to fire for exactly the sources that fail to
#: resolve, and `resolved.groups`/`resolved.folders` have already dropped
#: those by the time either function runs.
RAW_ENUM_SOURCE_READERS: frozenset[str] = frozenset({
    "dbml_sharepoint/analysis/checks/_library.py",
    "dbml_sharepoint/analysis/permissions.py",
    "dbml_sharepoint/analysis/validator.py",
    "dbml_sharepoint/analysis/checks/_permissions.py",
})


def test_only_the_resolver_reads_a_raw_enum_source() -> None:
    """`analysis/resolve.py` (and the `folders.py`/`groups.py` it delegates
    to) is meant to be the only place `group_sources`, `folder_source` or
    `folder_policies` is read before it has gone through `ResolvedMapping`.
    """
    Ratchet(
        name="RAW_ENUM_SOURCE_READERS",
        subject="module",
        resolved="now reading only through ResolvedMapping",
        violation="read a raw enum source outside the resolver",
    ).check(
        recorded=RAW_ENUM_SOURCE_READERS,
        violating=modules_reading_raw_enum_sources(SRC),
        universe={p.relative_to(SRC).as_posix() for p in SRC.rglob("*.py")},
    )


def test_permitted_and_recorded_do_not_overlap() -> None:
    """A module listed twice would silently exempt itself from the ratchet
    turning: `PERMITTED` is excluded before the recorded set is ever
    compared, so an entry appearing in both would never show up as
    resolved."""
    assert not (PERMITTED & RAW_ENUM_SOURCE_READERS)


def test_ratcheted_names_are_what_the_docstring_claims() -> None:
    """Pins the three names directly, so a typo in the module-level constant
    silently narrowing the walk is caught here rather than by a gate that
    would just report fewer violations."""
    assert {"group_sources", "folder_source", "folder_policies"} == RATCHETED
