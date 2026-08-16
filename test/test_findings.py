"""The finding vocabulary.

A finding's identity is its code. The message is prose for a human and may be
reworded at any time; nothing may key off it. `Location` exists so the dotted
path in a message is derived from structured data rather than being the only
place that data exists.
"""

import dataclasses
import inspect

import pytest
from _findings import none_of, only
from _paths import PACKAGE

from dbml_sharepoint.analysis.findings import (
    Finding,
    FindingCode,
    Location,
    Section,
)


def test_location_renders_the_dotted_path() -> None:
    loc = Location(Section.VIEWS, entity="Risk", view="Open")
    assert loc.path == "views[Risk].Open"


def test_location_renders_a_column_path() -> None:
    loc = Location(Section.COLUMN_FORMATTING, entity="Risk", column="Status")
    assert loc.path == "column_formatting[Risk].Status"


def test_location_renders_a_bare_section() -> None:
    assert Location(Section.ENTITIES, entity="Risk").path == "entities[Risk]"


def test_location_appends_a_sub_path() -> None:
    loc = Location(Section.FORM_VISIBILITY, entity="Risk", column="Status", sub="when")
    assert loc.path == "form_visibility[Risk].Status.when"


def test_location_renders_a_section_with_no_entity() -> None:
    """The whole-section shape, which nothing pinned.

    `path` builds its head conditionally, so this is what would break if the
    brackets were ever made unconditional -- `schema[None]` reads as a real
    entity called None and no other test would see it.
    """
    assert Location(Section.SCHEMA).path == "schema"


def test_location_orders_view_then_column_then_sub() -> None:
    """The tail is one tuple literal, and its ORDER is the whole rendering.

    Each of the three has a test of its own above, and all three pass with
    the tuple in any order -- only a location carrying more than one of them
    can tell them apart.
    """
    loc = Location(
        Section.VIEWS, entity="Risk", view="Open", column="Status", sub="sort",
    )
    assert loc.path == "views[Risk].Open.Status.sort"


def test_finding_is_hashable_and_frozen() -> None:
    """Findings go into sets in tests, and nothing may mutate one after the
    check that produced it has returned."""
    f = Finding(
        code=FindingCode.UNKNOWN_ENTITY,
        message="views[Risk]: unknown entity.",
        location=Location(Section.VIEWS, entity="Risk"),
    )
    assert {f, f} == {f}
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.message = "something else"  # type: ignore[misc]

    # `severity` is a read-only property now rather than a field, so the
    # interesting assertion is that there is nowhere to write it -- not which
    # exception a write raises. On a frozen slots dataclass an assignment to a
    # non-field attribute surfaces as TypeError from the generated
    # `__setattr__`, which is a CPython implementation detail and not a
    # contract worth pinning.
    severity = inspect.getattr_static(Finding, "severity")
    assert isinstance(severity, property)
    assert severity.fset is None


def test_every_code_is_screaming_snake_case() -> None:
    """The code is an API. A typo in one is a silent no-match in a test."""
    for code in FindingCode:
        assert code.name == code.name.upper()
        assert code.value == code.name.lower()


def test_the_finding_vocabulary_has_one_home() -> None:
    """`extension.py` documents `Finding` as the reporting type and
    `manifestgen` consumes it. Both now name `findings.py`, which defines it.

    `validator.py` re-exported the five names until #168 and no longer does.
    The ABSENCE is what is asserted, because a re-export that creeps back is
    invisible: every consumer keeps working, and the cycle it forces
    reappears as a deferred import somewhere else. `Severity` is the one of
    the five validator has no use of its own for, so it is the honest probe;
    the other four are still in its namespace because its own rules
    construct them. mypy holds the other half, refusing any module that
    imports the vocabulary through validator rather than from here.
    """
    from dbml_sharepoint.analysis import findings, validator

    for name in ("Finding", "FindingCode", "Location", "Section", "Severity"):
        assert hasattr(findings, name), name
    assert not hasattr(validator, "Severity")


#: Modules that still construct findings with no `location=`, with the issue
#: that closes them. A RATCHET, exactly like `_reachability.NOT_YET_REACHED`:
#: a name comes out when the module is converted and one going back in needs a
#: reason in the pull request. `analysis/validator.py` left it with #99's first
#: pass; `_structure.py` holds 25 sites whose "path" is often a derived name
#: rather than a declared one, so it may need a `Section`/`Location` member
#: that does not exist yet.
_LOCATION_INCOMPLETE = frozenset({"_structure.py"})  # 25 sites, #99


def test_every_finding_site_carries_a_location() -> None:
    """`location` is where the dotted path lives; `message` is prose.

    A site that passes none leaves the path existing only inside a sentence,
    so a consumer that wants to say which declaration is at fault has to
    parse prose (the defect this suite's `_findings.py` opens by describing,
    and one `manifestgen`, the reporting output and extension authors all
    inherit).

    Adding a location WITHOUT reworking such a message is no better: two
    spellings of one fact, free to drift apart. `validator.py` renders its
    prefix from `Location.path` so there is only ever one.

    Static in the same way `test_severity_is_declared_exactly_once` is: it
    proves no construction site omits the keyword, which is a property of the
    source rather than of any particular run.
    """
    import ast

    def constructs_a_finding(func: ast.expr) -> bool:
        """Both `Finding(...)` and `findings.Finding(...)` are written."""
        if isinstance(func, ast.Name):
            return func.id == "Finding"
        return isinstance(func, ast.Attribute) and func.attr == "Finding"

    offenders: list[str] = []
    sites = 0
    for path in sorted(PACKAGE.rglob("*.py")):
        if path.name in _LOCATION_INCOMPLETE:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and constructs_a_finding(node.func)):
                continue
            sites += 1
            if not any(kw.arg == "location" for kw in node.keywords):
                offenders.append(f"{path.relative_to(PACKAGE)}:{node.lineno}")

    # Without this the test is green on a package that constructs nothing at
    # all: rename the class, or move the checks, and "no offenders" reads as a
    # clean bill of health. 139 sites outside the allowlist when this was
    # written.
    assert sites > 100, (
        f"only {sites} Finding construction sites found -- has it been renamed?"
    )
    assert not offenders, (
        "Finding(...) constructed with no location=: " + ", ".join(offenders)
    )


def test_severity_is_declared_exactly_once() -> None:
    """It was declared twice, in validator.py and forms.py, with identical
    bodies. Two spellings of one type is how they drift."""
    import ast

    from _paths import PACKAGE

    declared = []
    for path in PACKAGE.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.TypeAlias) and node.name.id == "Severity":
                declared.append(path.name)
    assert declared == ["findings.py"], declared


# --- The assertion helpers, and the catalogue guard --------------------------


def test_only_returns_the_single_finding_with_that_code() -> None:
    f = Finding(FindingCode.UNKNOWN_ENTITY, "x")
    assert only([f], FindingCode.UNKNOWN_ENTITY) is f


def test_only_names_what_it_found_when_the_code_is_absent() -> None:
    """A bare `assert len(x) == 1` reports a count. The count is never the
    interesting part -- which rule fired instead is."""
    with pytest.raises(AssertionError, match="unknown_entity"):
        only(
            [Finding(FindingCode.UNKNOWN_ENTITY, "x")],
            FindingCode.EXTENSION_REPORTED,
        )


def test_none_of_names_the_offender() -> None:
    with pytest.raises(AssertionError, match="expected no unknown_entity"):
        none_of([Finding(FindingCode.UNKNOWN_ENTITY, "boom")],
                FindingCode.UNKNOWN_ENTITY)


# `test_every_code_is_documented` used to live here. It read
# `website/docs/reference/findings.md`, regex-matched row-shaped lines and
# compared that set of codes against `FindingCode` in both directions.
#
# It passed for as long as the page was unreadable. The file had lost every
# blank line, grown a second `# ` title and an orphaned `sidebar_position: 4`
# in its body, so all 194 rules rendered as one run-on paragraph instead of a
# table -- and none of that changes the SET of codes on row-shaped lines. The
# test checked the data and never the artifact, which is the whole lesson.
#
# The catalogue now lives in `analysis/finding_help.py`, the page is generated
# from it, and `test_finding_help.py` guards the pair by byte equality against
# the generator's own output. That cannot be satisfied by a broken document.


def test_no_finding_is_unclassified() -> None:
    """UNCLASSIFIED was migration scaffolding. Its absence is the proof the
    migration finished, and its re-appearance would mean a new rule shipped
    without a name."""
    assert "UNCLASSIFIED" not in FindingCode.__members__


def test_every_code_can_actually_be_produced() -> None:
    """A code nothing constructs is a lie in the catalogue.

    `findings.md` is published documentation. A row for a rule no code path
    can reach tells a reader the build checks something it does not, which is
    worse than an undocumented rule -- they will not go looking for the check
    that is missing.

    This is a STATIC check: it proves each code appears in a construction site
    somewhere in `src`, not that any test reaches that site. Runtime
    reachability is the stronger property and is NOT tested here; the
    classification pass found roughly seventeen codes whose paths no test
    exercises, and closing that needs a corpus of deliberately-broken mappings
    rather than an allowlist. Recorded so the gap is known rather than implied
    away by this test's name.
    """
    import ast

    # `finding_help.py` is excluded for the same reason `findings.py` is, and
    # the reason is sharper: the catalogue names EVERY code by construction,
    # so counting it as a reference would make this test vacuous. It does not
    # happen to fail today -- every code really is constructed somewhere --
    # but the next catalogued-and-never-raised code would pass in silence,
    # which is precisely the lie this test exists to catch.
    declarations_not_uses = {"findings.py", "finding_help.py"}

    # Parsed, not regex-matched over the raw text: a code named in a comment
    # or a docstring is not a construction site, and the text scan counted
    # both.
    #
    # NOT narrowed to literal `Finding(...)` calls, which is the obvious next
    # step and is wrong. `analysis/conditions.py` routes every refusal through
    # `_reject(code, ...)` and builds its findings in a comprehension, so a
    # call-shaped check reports 39 of the 193 codes as unconstructed --
    # measured, and the same 39 that misled the first attempt at #98. An
    # executable reference to the code is the honest signal at this level;
    # whether the rule FIRES is a runtime question, and the paragraph above
    # says so.
    referenced: set[str] = set()
    for path in PACKAGE.rglob("*.py"):
        if path.name in declarations_not_uses:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "FindingCode"
            ):
                referenced.add(node.attr)

    declared = {c.name for c in FindingCode}

    # Raised by an extension's own validators, never by the core -- see the
    # members' comment. Both exist so an extension can report either strength
    # without anybody restating a severity, and `test_validator_core` builds
    # one of each: `_StubExtension` the warning, `_ErrorExtension` the error.
    extension_only = {"EXTENSION_REPORTED", "EXTENSION_WARNING"}

    unreachable = declared - referenced - extension_only
    assert not unreachable, (
        "declared but never constructed: " + ", ".join(sorted(unreachable))
    )
