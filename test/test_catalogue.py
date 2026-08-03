"""The shipped-solution catalogue the wizard offers.

The catalogue is discovery, not validation: it must describe every shipped
family without loading any of them through the mapping loader, so one
malformed template cannot take the picker down with it.
"""

from pathlib import Path

import pytest
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
    an assertion that thirty templates exist goes stale the moment a
    thirty-first is added, and the failure would read as a bug in the
    catalogue rather than as a template nobody wired up.
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
    """A blank cell in the picker is indistinguishable from a broken one."""
    assert solution.title
    assert solution.summary
    assert solution.lists
    assert solution.prefix


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
    """Fourteen of the thirty READMEs open with `*Theme: ...*`, which is
    metadata about the collection rather than a description of the
    template. It is skipped rather than parsed because it wraps
    inconsistently and only half the families carry it."""
    assert not load_solution("visitor-log").summary.startswith("Theme")
