"""The shipped-solution catalogue the wizard offers.

The catalogue is discovery, not validation: it must describe every shipped
family without loading any of them through the mapping loader, so one
malformed template cannot take the picker down with it.
"""

from pathlib import Path

import pytest
import yaml
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint import catalogue
from dbml_sharepoint.catalogue import (
    UnknownSolutionError,
    available_solutions,
    load_solution,
)


def test_every_shipped_family_is_offered() -> None:
    """Discovered by glob, never by roster.

    Compared against the directory listing rather than against a number:
    an assertion that some fixed number of templates exists goes stale the
    moment the next one is added, and the failure would read as a bug in
    the catalogue rather than as a template nobody wired up.
    """
    on_disk = {
        path.parent.parent.name
        for path in SOLUTION_TEMPLATES.glob("*/10-design/schema.dbml")
    }
    assert {s.id for s in available_solutions()} == on_disk


def test_the_catalogue_ships_inside_the_package() -> None:
    """The whole reason the templates moved.

    `uvx dbml-sharepoint` installs the package and nothing else, so a
    catalogue that resolved to a repository path would be empty for every
    user who did not clone.
    """
    package_root = Path(catalogue.__file__).parent
    assert catalogue.SOLUTIONS_DIR.parent == package_root


@pytest.mark.parametrize("solution", available_solutions(), ids=lambda s: s.id)
def test_each_solution_describes_itself(solution: catalogue.Solution) -> None:
    """A blank cell in the picker is indistinguishable from a broken one.

    The prefix may legitimately be empty (programme-governance declares
    `prefix: ""` and the picker shows "(none)"), so what is pinned is that
    the mapping DECLARES the key: an empty cell is a decision, never an
    omission the catalogue papered over."""
    assert solution.title
    assert solution.summary
    assert solution.lists
    assert isinstance(solution.prefix, str)
    raw = yaml.safe_load(solution.mapping_path.read_text(encoding="utf-8"))
    assert "prefix" in raw, f"{solution.id}: mapping.yaml declares no prefix key"


@pytest.mark.parametrize("solution", available_solutions(), ids=lambda s: s.id)
def test_each_summary_fits_a_terminal(solution: catalogue.Solution) -> None:
    assert len(solution.summary) <= catalogue._SUMMARY_MAX
    assert "\n" not in solution.summary
    # The markdown is stripped, not rendered: a stray ** in a table cell
    # reads as a typo in the template.
    assert "**" not in solution.summary
    assert "`" not in solution.summary


@pytest.mark.parametrize("solution", available_solutions(), ids=lambda s: s.id)
def test_each_solution_ships_all_three_build_inputs(
    solution: catalogue.Solution,
) -> None:
    assert solution.schema_path.is_file()
    assert solution.mapping_path.is_file()
    assert solution.release_path.is_file()


def test_the_collection_readmes_are_not_offered_as_templates() -> None:
    ids = {s.id for s in available_solutions()}
    assert "README.md" not in ids
    assert "healthcare.md" not in ids


def test_a_directory_without_a_schema_is_not_a_solution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A leftover build directory or an editor backup must not appear as
    something the user can pick and then fail to deploy."""
    (tmp_path / "real" / "10-design").mkdir(parents=True)
    (tmp_path / "real" / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
    (tmp_path / "real" / "20-configure").mkdir()
    (tmp_path / "real" / "20-configure" / "mapping.yaml").write_text(
        'prefix: "X_"\nentities: {}\n', encoding="utf-8",
    )
    (tmp_path / "stray").mkdir()

    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    assert [s.id for s in available_solutions()] == ["real"]


def test_a_malformed_mapping_does_not_break_the_whole_picker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing what is available must not depend on all of it being valid.

    `_mapping_facts` reads two keys with `yaml.safe_load` rather than going
    through `load_mapping`, precisely so one bad template costs its own row
    and not the other twenty-nine.
    """
    for name, mapping_text in (
        ("good", 'prefix: "G_"\nentities:\n  Thing: {}\n'),
        ("broken", "prefix: [this is not\n  valid: yaml: at all\n"),
    ):
        (tmp_path / name / "10-design").mkdir(parents=True)
        (tmp_path / name / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
        (tmp_path / name / "20-configure").mkdir()
        (tmp_path / name / "20-configure" / "mapping.yaml").write_text(
            mapping_text, encoding="utf-8",
        )

    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    found = {s.id: s for s in available_solutions()}
    assert set(found) == {"good", "broken"}
    assert found["good"].prefix == "G_"
    assert found["broken"].prefix == ""


def test_load_solution_names_the_alternatives() -> None:
    """A typo'd template name should not make the user go and list them."""
    with pytest.raises(UnknownSolutionError) as caught:
        load_solution("risk-registry")
    assert "risk-register" in str(caught.value)
    assert caught.value.name == "risk-registry"


def test_load_solution_returns_the_named_family() -> None:
    assert load_solution("risk-register").id == "risk-register"


def test_a_missing_solutions_directory_is_empty_not_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The wizard reports "this build shipped without them" and exits 1;
    it must get an empty list to do that, not an exception."""
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path / "nope")
    assert available_solutions() == []


def test_the_theme_line_is_skipped_not_shown() -> None:
    """Many READMEs open with `*Theme: ...*`, which is metadata about the
    collection rather than a description of the template. It is skipped
    rather than parsed because it wraps inconsistently and only about half
    the families carry it."""
    assert not load_solution("visitor-log").summary.startswith("Theme")


def test_detail_is_the_untruncated_summary() -> None:
    """The table cell needs a cap; the wizard's detail panel does not.

    Reusing `summary` there cut a sentence mid-word -- `...SharePoint
    calculates Resi...` -- in a Panel with room for all of it.
    """
    long_ones = [
        s for s in available_solutions() if len(s.detail) > catalogue._SUMMARY_MAX
    ]
    assert long_ones, (
        "no shipped template has a summary long enough to be truncated, so "
        "this test cannot show that `detail` is not truncated"
    )
    for solution in long_ones:
        assert not solution.detail.endswith(catalogue._ELLIPSIS)
        # Strip the marker itself rather than re-slicing at a fixed offset:
        # `_summary` rstrips *after* cutting to `_SUMMARY_MAX - len(_ELLIPSIS)`,
        # so on a template where that cut lands on whitespace the kept text
        # is a few characters shorter than the offset. Re-slicing `summary`
        # at that same offset then grabs a leading fragment of the "..."
        # marker instead -- true for service-evidence-register and
        # volunteer-register today. Removing the marker by suffix instead of
        # by position holds regardless of where the cut landed.
        assert solution.detail.startswith(
            solution.summary.removesuffix(catalogue._ELLIPSIS).rstrip(),
        )


def test_detail_is_a_whole_sentence() -> None:
    """Not a hard cut. Every non-empty detail ends in a full stop."""
    for solution in available_solutions():
        if solution.detail:
            assert solution.detail.endswith("."), solution.id


def test_detail_is_ascii() -> None:
    """Same reason as `summary`: it is rendered into a terminal.

    `test_every_catalogue_entry_is_ascii` covers the other fields; this
    keeps the new one from being the exception nobody noticed.
    """
    offenders = [
        (s.id, sorted({c for c in s.detail if ord(c) > 127}))
        for s in available_solutions()
        if not s.detail.isascii()
    ]
    assert not offenders, (
        "detail text a terminal may not encode -- give each character an "
        f"ASCII spelling in `_TERMINAL_SPELLINGS`: {offenders}"
    )


def test_every_catalogue_entry_is_ascii() -> None:
    """What the wizard prints must survive a legacy console.

    The picker renders every title into a rich table and the chosen
    template's summary into a panel, before any build has run. Several
    families carried typographic punctuation from their README --
    including `→`, which no Windows console code page can encode, so picking
    one could raise `UnicodeEncodeError` from inside rich.

    Asserted over the whole shipped catalogue rather than those, so a new
    template introducing a character `_TERMINAL_SPELLINGS` does not know
    fails here -- visibly, and fixable in one line -- rather than being
    silently mangled or crashing somebody's wizard.
    """
    offenders = [
        (solution.id, field, sorted({c for c in value if ord(c) > 127}))
        for solution in available_solutions()
        for field in ("id", "title", "summary", "prefix")
        if not (value := getattr(solution, field)).isascii()
    ]
    assert not offenders, f"catalogue text a terminal may not encode: {offenders}"


def test_clean_folds_typography_a_console_cannot_encode() -> None:
    """The only observer of `_TERMINAL_SPELLINGS` now that shipped text is ASCII.

    Every README used to carry typographic punctuation, so the fold was
    exercised by real data and the tests above passed because it worked.
    `test_shipped_text_is_ascii` removed that data, and emptying the table
    then left the whole of this module green.
    """
    # Built with chr() so this file needs no exemption from the ASCII rule,
    # which is how _TERMINAL_SPELLINGS itself is written.
    messy = (
        "**Risk 5" + chr(0x00D7) + "5** " + chr(0x2014)
        + " owner " + chr(0x2192) + " review" + chr(0x2026)
    )
    assert catalogue._clean(messy) == "Risk 5x5 -- owner -> review..."
