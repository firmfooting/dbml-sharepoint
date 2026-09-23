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
function rather than its module, and how `self.folder_policies` on a
`ResolvedMapping` is told apart from the raw field of the same name.
"""

from pathlib import Path

from _paths import PACKAGE
from _ratchet import Ratchet
from _raw_enum_readers import (
    MODULE_SCOPE,
    PERMITTED,
    POSITIONAL_FIELDS,
    RATCHETED,
    RESOLUTION_FIELDS,
    RESOLVER_MODULE,
    _reads_in,
    scan,
)

from dbml_sharepoint.analysis.resolve import ResolvedMapping
from dbml_sharepoint.model.mapping_types import EntityMapping, PermissionsConfig

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


def test_the_walk_sees_an_augmented_assignment() -> None:
    """`+=` reads the field before it writes it, and the plain `=` does not.

    Both spell the target with `Store` context, so the `Load` test that keeps
    a constructor keyword out of the reads was dropping this one with it.
    """
    assert _reads_in("perms.group_sources += extra") == {
        (MODULE_SCOPE, "group_sources"),
    }


def test_the_walk_sees_a_literal_getattr() -> None:
    """The same field access, held in the AST as a `Call` and not an
    `Attribute`, so the attribute walk never sees it."""
    assert _reads_in('x = getattr(perms, "group_sources")') == {
        (MODULE_SCOPE, "group_sources"),
    }
    assert _reads_in('x = getattr(perms, "folder_policies", {})') == {
        (MODULE_SCOPE, "folder_policies"),
    }


def test_the_walk_cannot_see_a_computed_getattr() -> None:
    """Pinned as the limit it is: a name assembled at runtime is invisible to
    any static walk, so only the literal spelling above is claimed."""
    assert _reads_in("x = getattr(perms, field_name)") == set()


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


def _positional_case(cls: str, name: str) -> str:
    """A `match` whose positional pattern reaches `name` on `cls`.

    The run of `_` is built from the live `__match_args__` rather than
    written out, so a field added to the class moves this source too.
    """
    positions = ", ".join([*["_"] * POSITIONAL_FIELDS[cls].index(name), "wanted"])
    return f"match obj:\n    case {cls}({positions}):\n        use(wanted)\n"


def test_the_walk_sees_a_positional_class_pattern_read() -> None:
    """A positional pattern spells the field name nowhere at all.

    `case EntityMapping(_, ..., source)` reads `folder_source` through the
    dataclass's `__match_args__`, leaving `kwd_attrs` empty, so the keyword
    handling above reported nothing for it and the same hole was open on
    `PermissionsConfig.group_sources` and `folder_policies`.
    """
    for cls, name in (
        ("EntityMapping", "folder_source"),
        ("PermissionsConfig", "group_sources"),
        ("PermissionsConfig", "folder_policies"),
    ):
        reads = _reads_in(_positional_case(cls, name))
        assert (MODULE_SCOPE, name) in reads, (cls, name, reads)


def test_the_walk_ignores_a_positional_pattern_that_stops_short() -> None:
    """Which position was reached is resolved against the real class.

    `case EntityMapping(name, kind)` binds two fields that are not ratcheted
    and reads no enum source, so reporting it would put a module on the
    allowlist for pattern-matching an entity at all.
    """
    assert _reads_in(
        "match e:\n"
        "    case EntityMapping(name, kind):\n"
        "        use(name)\n",
    ) == set()


def _aliased_case(cls: str, alias: str, name: str) -> str:
    """`_positional_case`, with the class imported under another name."""
    positions = ", ".join([*["_"] * POSITIONAL_FIELDS[cls].index(name), "wanted"])
    return (
        f"from dbml_sharepoint.model.mapping_types import {cls} as {alias}\n"
        f"match obj:\n    case {alias}({positions}):\n        use(wanted)\n"
    )


def test_the_walk_resolves_an_imported_alias_in_a_class_pattern() -> None:
    """`POSITIONAL_FIELDS` is keyed by the canonical class name, so a module
    that imported the class under another one matched against no positions at
    all and its raw read was reported nowhere.
    """
    assert _reads_in(_aliased_case("PermissionsConfig", "PC", "group_sources")) == {
        (MODULE_SCOPE, "group_sources"),
    }


def test_a_positional_pattern_on_an_unplaceable_class_is_flagged() -> None:
    """A class this walk cannot tie to a model class could bind any of the
    three, so it is reported as reading all of them and has to be accounted
    for rather than passing unseen. A keyword pattern spells exactly what it
    reads and needs no such guess.
    """
    assert _reads_in("match obj:\n    case Elsewhere(a, b):\n        use(a)\n") == {
        (MODULE_SCOPE, name) for name in RATCHETED
    }
    assert _reads_in("match obj:\n    case Elsewhere(levels=n):\n        use(n)\n") == set()


def test_an_alias_two_imports_bind_differently_is_treated_as_unplaceable() -> None:
    """The alias map is per module, so a name rebound in a second import used
    to resolve to whichever the walk reached last and could silently place a
    pattern against the wrong class's `__match_args__`.
    """
    source = (
        "from dbml_sharepoint.model.mapping_types import PermissionsConfig as C\n"
        "match obj:\n    case C(_, wanted):\n        use(wanted)\n"
        "def later():\n"
        "    from dbml_sharepoint.model.mapping_types import EntityMapping as C\n"
        "    return C\n"
    )
    assert _reads_in(source) == {(MODULE_SCOPE, name) for name in RATCHETED}


def test_a_resolved_field_is_suppressed_only_inside_the_resolver_module() -> None:
    """`RESOLUTION_FIELDS` is keyed by the short class name, so a class called
    `ResolvedMapping` in any other module had every `self.folder_policies` in
    it suppressed and its raw read hidden.
    """
    source = (
        "class ResolvedMapping:\n"
        "    def read(self):\n        return self.folder_policies\n"
    )
    assert _reads_in(source, RESOLVER_MODULE) == set()
    assert _reads_in(source, "dbml_sharepoint/generators/jsgen.py") == {
        ("ResolvedMapping.read", "folder_policies"),
    }


def test_positional_positions_come_from_the_live_classes() -> None:
    """A written-out index shifts silently the moment a field is added, so
    the positions are the classes' own `__match_args__` and nothing else."""
    assert POSITIONAL_FIELDS["EntityMapping"] == EntityMapping.__match_args__
    assert POSITIONAL_FIELDS["PermissionsConfig"] == PermissionsConfig.__match_args__
    assert POSITIONAL_FIELDS["ResolvedMapping"] == ResolvedMapping.__match_args__


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


def _resolved_and_raw(read: str) -> str:
    """The shape `ResolvedMapping.require_folder_policies` has: one method
    holding both a resolved read and a raw one."""
    return (
        "class ResolvedMapping:\n"
        "    def require_folder_policies(self, perms):\n"
        f"        return {read}\n"
    )


def test_a_resolutions_own_field_is_not_a_raw_read() -> None:
    """Keyed by field name alone the two reads collapse into one site, so a
    single exemption covered both and outlived whichever went first."""
    assert _reads_in(_resolved_and_raw("self.folder_policies")) == set()
    assert _reads_in(_resolved_and_raw("perms.folder_policies")) == {
        ("ResolvedMapping.require_folder_policies", "folder_policies"),
    }


def test_the_class_that_holds_a_raw_source_reads_it_through_self_too() -> None:
    """The receiver alone exempts nothing: `self` is a resolved answer only in
    the class `analysis/resolve.py` declares it on."""
    assert _reads_in(
        "class EntityMapping:\n    def f(self):\n        return self.folder_source\n",
    ) == {("EntityMapping.f", "folder_source")}


def test_only_the_resolution_module_declares_a_resolved_answer() -> None:
    """Read off the live classes, and only that module's own: `EntityMapping`
    and `PermissionsConfig` carry the raw fields under these same names."""
    assert {"ResolvedMapping": frozenset({"folder_policies"})} == RESOLUTION_FIELDS


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
    violation="read a raw enum source outside the sites PERMITTED records",
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


def test_no_site_is_both_recorded_and_permitted() -> None:
    """A site listed twice would silently exempt itself from the ratchet
    turning: `PERMITTED` is subtracted before the reads are ever compared, so
    an entry that is also permitted could never show up as resolved."""
    assert not (RAW_ENUM_SOURCE_READS & PERMITTED)


def test_only_the_recorded_sites_in_a_permitted_module_are_exempt(tmp_path: Path) -> None:
    """The hole a roster of MODULES had on the resolver's own side.

    `groups.py::declaring_groups` reads `group_sources` and is called
    straight from `pipeline.py` and `wizard.py`, so neither it nor
    `folders.py` is exclusively resolver internals. While the exemption was
    the whole file, a function added to either could re-resolve a raw source
    and never enter `found.reads` at all.
    """
    listed = "dbml_sharepoint/analysis/groups.py::declaring_groups::group_sources"
    assert listed in PERMITTED
    module = tmp_path / "dbml_sharepoint" / "analysis" / "groups.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "def declaring_groups(perms):\n"
        "    return perms.group_sources\n"
        "def added_later(perms):\n"
        "    return perms.group_sources\n",
        encoding="utf-8",
    )
    found = scan(tmp_path)
    assert found.reads == {
        "dbml_sharepoint/analysis/groups.py::added_later::group_sources",
    }
    assert found.exempted == {listed}


def test_a_permitted_entry_stops_exempting_when_its_raw_read_goes(tmp_path: Path) -> None:
    """The entry below names the RAW read, so the currency test can retire it.

    `require_folder_policies` reads the resolved field beside it, and while
    that counted as the same site the exemption could never go stale: a new
    raw read anywhere in the function stayed permitted by an entry written
    for one that had gone.
    """
    listed = (
        "dbml_sharepoint/analysis/resolve.py"
        "::ResolvedMapping.require_folder_policies::folder_policies"
    )
    assert listed in PERMITTED
    module = tmp_path / "dbml_sharepoint" / "analysis" / "resolve.py"
    module.parent.mkdir(parents=True)
    module.write_text(
        "class ResolvedMapping:\n"
        "    def require_folder_policies(self, entity):\n"
        "        return self.folder_policies.get(entity)\n",
        encoding="utf-8",
    )
    assert scan(tmp_path).exempted == set()


def test_every_permitted_site_still_reads_a_raw_source() -> None:
    """An exemption for a read that no longer happens guards nothing, and is
    the same dead-entry failure `Ratchet` asks its first question about."""
    stale = PERMITTED - scan(SRC).exempted
    assert not stale, (
        "these PERMITTED entries read no raw enum source and must be deleted:\n  "
        + "\n  ".join(sorted(stale))
    )


def test_ratcheted_names_are_what_the_docstring_claims() -> None:
    """Pins the three names directly, so a typo in the module-level constant
    silently narrowing the walk is caught here rather than by a gate that
    would just report fewer violations."""
    assert {"group_sources", "folder_source", "folder_policies"} == RATCHETED
