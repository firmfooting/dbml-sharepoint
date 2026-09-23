# test/test_raw_enum_readers.py
"""Only `analysis/resolve.py` may read a `from_enum` source before it resolves.

Pieces 1-3 merged `SCHEMA.list_assignments` and `SCHEMA.folder_assignments`
into one `SCHEMA.acl_scopes` and moved every enum-source resolution
(`entities.<name>.folders`, `groups[].from_enum`) into `analysis/resolve.py`.
Nothing stops a future rule or generator reaching past that boundary for
`entity.folder_source`, `perms.group_sources` or `perms.folder_policies`
directly, re-deriving the same resolution a second way -- which is the shape
of drift this whole piece exists to close. This is that gate.

See `_raw_enum_readers.py` for the walk, why a read is recorded against its
function rather than its module, and why `folder_policies` colliding with a
`ResolvedMapping` field name is not a problem it needs to solve.
"""

from _paths import PACKAGE
from _ratchet import Ratchet
from _raw_enum_readers import (
    MODULE_SCOPE,
    PERMITTED,
    RATCHETED,
    _reads_in,
    scan,
)

#: `src/`, not `src/dbml_sharepoint/`: the universe the ratchet checks
#: recorded entries against, and what `PERMITTED`'s paths are spelled
#: relative to.
SRC = PACKAGE.parent


def test_the_walk_sees_a_read_off_a_raw_object() -> None:
    assert _reads_in("x = perms.folder_policies") == {
        (MODULE_SCOPE, "folder_policies"),
    }


def test_the_walk_ignores_a_keyword_argument_of_the_same_name() -> None:
    """Constructing a mapping is not reading one.

    `EntityMapping(folder_source=...)` and an annotation both mention the
    name without reading the field off an object, and a gate that flagged
    them would push the loader onto its own allowlist for doing its job.
    """
    assert _reads_in("EntityMapping(folder_source=src)") == set()
    assert _reads_in("folder_source: FolderSource") == set()


def test_the_walk_ignores_an_assignment_to_the_field() -> None:
    assert _reads_in("obj.folder_source = src") == set()


def test_the_walk_sees_a_read_through_a_chain() -> None:
    assert _reads_in("n = bundle.mapping.permissions.group_sources") == {
        (MODULE_SCOPE, "group_sources"),
    }


def test_the_walk_sees_a_class_pattern_read() -> None:
    """A class pattern reads the field, and spells the name as a string.

    `case EntityMapping(folder_source=src)` puts `folder_source` in
    `ast.MatchClass.kwd_attrs`, where an `ast.Attribute` walk cannot see it,
    so a module could have consumed a raw source in a `match` and passed.
    The keyword-argument test above is the reason this needs saying: the two
    spellings look identical and only one of them is a read.
    """
    assert _reads_in(
        "match entity:\n"
        "    case EntityMapping(folder_source=src):\n"
        "        use(src)\n",
    ) == {(MODULE_SCOPE, "folder_source")}


def test_the_walk_ignores_an_unrelated_attribute() -> None:
    """Only the three ratcheted names are ever reported, nothing else."""
    assert _reads_in("x = perms.levels") == set()


def test_a_read_is_recorded_against_the_function_holding_it() -> None:
    """Which is the whole point of the granularity, so it is pinned here."""
    assert _reads_in("def f(p):\n    return p.group_sources\n") == {
        ("f", "group_sources"),
    }
    assert _reads_in(
        "class C:\n    def m(self, p):\n        return p.folder_source\n",
    ) == {("C.m", "folder_source")}


#: Raw enum-source reads outside the resolver: one entry per reading function
#: and field, with the question that read asks. A RATCHET: entries come out
#: when a function migrates onto `ResolvedMapping`, and one going in needs a
#: reason in the pull request.
RAW_ENUM_SOURCE_READS: frozenset[str] = frozenset({
    # Whether a source was written at all, which no resolution can answer.
    "dbml_sharepoint/analysis/checks/_library.py::check::folder_source",
    # The declared policy keys themselves, judged against the entities.
    "dbml_sharepoint/analysis/checks/_library.py::_folder_permissions::folder_policies",
    # The enum a source NAMES, matched against a column type the entity has.
    "dbml_sharepoint/analysis/checks/_library.py::_folder_enum_is_this_entity_s::folder_source",
    # Each declared source alone, so `group_enum_unknown` fires for the ones
    # resolution drops.
    "dbml_sharepoint/analysis/checks/_permissions.py::_enum_groups::group_sources",
    # Every declared policy block, including the ones resolution drops.
    "dbml_sharepoint/analysis/checks/_permissions.py::_expanded_folder_policies::folder_policies",
    # A membership test that must stay as lenient as `resolved.groups`, so it
    # cannot fail the mapping over an entity the caller never asked about.
    "dbml_sharepoint/analysis/permissions.py::requires_manage_permissions::folder_policies",
    # The enum names a mapping WROTE, collected before any `ResolvedMapping`
    # exists, so `orphan_enum` is not reported against a misspelled source.
    "dbml_sharepoint/analysis/validator.py::_enums_used_by_mapping::folder_source",
    "dbml_sharepoint/analysis/validator.py::_enums_used_by_mapping::group_sources",
})

#: Shared by the gate and by the tests that make it fire, so a failure they
#: prove is the failure the gate reports.
_RATCHET = Ratchet(
    name="RAW_ENUM_SOURCE_READS",
    subject="read site",
    resolved="now reading only through ResolvedMapping",
    violation="read a raw enum source outside the resolver",
)


def test_only_the_resolver_reads_a_raw_enum_source() -> None:
    """`analysis/resolve.py` (and the `folders.py`/`groups.py` it delegates
    to) is meant to be the only place `group_sources`, `folder_source` or
    `folder_policies` is read before it has gone through `ResolvedMapping`.
    """
    found = scan(SRC)
    _RATCHET.check(
        recorded=RAW_ENUM_SOURCE_READS,
        violating=found.reads,
        universe=found.sites,
    )


def test_a_new_read_in_an_already_listed_module_is_not_exempted() -> None:
    """The hole a roster of MODULES had, and the reason for the granularity.

    `checks/_permissions.py` and `checks/_library.py` each already hold
    justified reads, so a module-granular entry made every later read in
    those two files free. The two files most likely to grow another raw read
    were the two the gate had stopped watching.
    """
    listed = min(RAW_ENUM_SOURCE_READS)
    intruder = f"{listed.split('::')[0]}::_a_function_added_later::folder_source"
    problems = _RATCHET.problems(
        recorded=RAW_ENUM_SOURCE_READS,
        violating=RAW_ENUM_SOURCE_READS | {intruder},
    )
    assert any(intruder in problem for problem in problems), problems


def test_an_entry_naming_a_function_that_no_longer_exists_is_stale() -> None:
    """A renamed function's entry guards nothing, and says nothing about it.

    This is the failure that makes a ratchet worse than no ratchet, and it is
    only askable because the scan reports every site a module could hold
    rather than only the ones it does.
    """
    problems = _RATCHET.problems(
        recorded={"dbml_sharepoint/analysis/validator.py::_gone::folder_source"},
        violating=set(),
        universe=scan(SRC).sites,
    )
    assert any("name no declared read site" in problem for problem in problems), problems


def test_no_recorded_read_sits_in_a_permitted_module() -> None:
    """A module listed twice would silently exempt itself from the ratchet
    turning: `PERMITTED` is excluded before the reads are ever compared, so
    an entry under one of those paths could never show up as resolved."""
    assert not {
        entry for entry in RAW_ENUM_SOURCE_READS
        if entry.split("::")[0] in PERMITTED
    }


def test_ratcheted_names_are_what_the_docstring_claims() -> None:
    """Pins the three names directly, so a typo in the module-level constant
    silently narrowing the walk is caught here rather than by a gate that
    would just report fewer violations."""
    assert {"group_sources", "folder_source", "folder_policies"} == RATCHETED
