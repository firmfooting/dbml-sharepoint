"""The shipped-solution catalogue the wizard offers.

The catalogue is discovery, not validation: it must describe every shipped
family without loading any of them through the mapping loader, so one
malformed template cannot take the picker down with it.
"""

from email.message import Message
from importlib.metadata import PackageNotFoundError
from pathlib import Path

import pytest
from _catalogue_fixtures import CORE_LICENSE, manifest_text, write_family
from _paths import SOLUTION_TEMPLATES

from dbml_sharepoint import catalogue
from dbml_sharepoint.catalogue import (
    BLUEPRINT_MANIFEST,
    CORE_DISTRIBUTION,
    BlueprintRoot,
    BlueprintRootError,
    UnknownSolutionError,
    available_journeys,
    available_solutions,
    blueprint_roots,
    load_solution,
    notices,
    read_catalogue,
)
from dbml_sharepoint.model import _yaml


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
    raw = _yaml.safe_load(solution.mapping_path.read_text(encoding="utf-8"))
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
    (tmp_path / "real" / "20-configure" / "release.yaml").write_text("", encoding="utf-8")
    (tmp_path / "real" / BLUEPRINT_MANIFEST).write_text(manifest_text("real"), encoding="utf-8")
    (tmp_path / "stray").mkdir()

    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    assert [s.id for s in available_solutions()] == ["real"]


def test_a_malformed_mapping_does_not_break_the_whole_picker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Listing what is available must not depend on all of it being valid.

    `_mapping_facts` reads two keys with a plain parse rather than going
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
        (tmp_path / name / "20-configure" / "release.yaml").write_text("", encoding="utf-8")
        (tmp_path / name / BLUEPRINT_MANIFEST).write_text(manifest_text(name), encoding="utf-8")

    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    found = {s.id: s for s in available_solutions()}
    assert set(found) == {"good", "broken"}
    assert found["good"].prefix == "G_"
    assert found["broken"].prefix == ""


def test_a_mapping_declaring_a_key_twice_is_skipped_like_a_broken_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The picker reads with the loader the build uses, so it offers no
    prefix or lists for a mapping the build will refuse (#672). Read with a
    loader that kept the last key, this one offered `E_` and one list."""
    for name, mapping_text in (
        ("good", 'prefix: "G_"\nentities:\n  Thing: {}\n'),
        ("repeated", 'prefix: "D_"\nentities:\n  Thing: {}\nprefix: "E_"\n'),
    ):
        (tmp_path / name / "10-design").mkdir(parents=True)
        (tmp_path / name / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
        (tmp_path / name / "20-configure").mkdir()
        (tmp_path / name / "20-configure" / "mapping.yaml").write_text(
            mapping_text, encoding="utf-8",
        )
        (tmp_path / name / "20-configure" / "release.yaml").write_text("", encoding="utf-8")
        (tmp_path / name / BLUEPRINT_MANIFEST).write_text(manifest_text(name), encoding="utf-8")

    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    found = {s.id: s for s in available_solutions()}
    assert set(found) == {"good", "repeated"}
    assert (found["good"].prefix, found["good"].lists) == ("G_", ("Thing",))
    assert (found["repeated"].prefix, found["repeated"].lists) == ("", ())


def test_a_journey_declaring_a_key_twice_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A second `solutions:` replaced the first, so the families only the
    first one named dropped out of the journey with nothing said (#672).

    Refused rather than skipped, as `available_journeys` treats every
    malformed journey.
    """
    journeys = tmp_path / catalogue.JOURNEYS_DIRNAME
    journeys.mkdir()
    journey = journeys / "j.md"
    journey.write_text(
        "---\ntitle: J\nsummary: S\nsolutions: [a, b]\nsolutions: [c]\n---\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    with pytest.raises(ValueError) as err:
        catalogue.available_journeys()
    message = str(err.value)
    assert message.startswith(f"{journey}: front matter is not valid YAML: "), message
    # The file's own line numbers: the repeat is on line 5 and the first on line 4.
    assert "found duplicate key 'solutions' (first at line 4)\n" in message, message
    assert '"<unicode string>", line 5, column 1' in message, message


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
        # By suffix, not offset: `_cap` rstrips after cutting, so the kept text may be shorter.
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


def test_the_core_root_comes_first_and_carries_core_s_licence() -> None:
    assert blueprint_roots()[0] == BlueprintRoot(
        CORE_DISTRIBUTION, catalogue.SOLUTIONS_DIR, CORE_LICENSE,
    )


def test_core_without_distribution_metadata_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Imported from a bare source tree, core's licence is unknowable, so nothing is offered."""

    def missing(name: str) -> Message:
        raise PackageNotFoundError(name)

    monkeypatch.setattr(catalogue, "metadata", missing)
    with pytest.raises(BlueprintRootError, match="dbml-sharepoint is not installed"):
        read_catalogue()


def test_core_metadata_without_a_licence_expression_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(catalogue, "metadata", lambda name: Message())
    with pytest.raises(BlueprintRootError, match="declares no License-Expression"):
        read_catalogue()


def test_every_shipped_solution_is_tagged_with_core() -> None:
    assert {(s.distribution, s.license, s.origin) for s in available_solutions()} == {
        (CORE_DISTRIBUTION, CORE_LICENSE, "firmfooting"),
    }


def test_no_shipped_pack_is_refused() -> None:
    """A refused pack drops out of the picker, which no other test would notice."""
    assert read_catalogue().refused == ()


def test_every_journey_names_the_distribution_that_ships_it() -> None:
    assert {j.distribution for j in available_journeys()} == {CORE_DISTRIBUTION}


def test_a_pack_without_a_manifest_is_refused_and_named(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_family(tmp_path, "good")
    (write_family(tmp_path, "bare") / BLUEPRINT_MANIFEST).unlink()
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)

    found = read_catalogue()
    assert [s.id for s in found.solutions] == ["good"]
    assert [(r.distribution, r.path.name) for r in found.refused] == [
        (CORE_DISTRIBUTION, "bare"),
    ]
    assert "no blueprint.toml" in found.refused[0].reason
    assert notices(found) == [f"Not offered: {CORE_DISTRIBUTION}: {found.refused[0].reason}"]
    assert [s.id for s in available_solutions()] == ["good"]


def test_a_pack_claiming_another_licence_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_family(tmp_path, "relicensed", {"license": "Apache-2.0"})
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    found = read_catalogue()
    assert found.solutions == ()
    assert "differs from" in found.refused[0].reason


def test_title_and_summary_come_from_the_manifest_not_the_readme(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One source for each: the README is documentation, blueprint.toml is what the picker shows."""
    family = write_family(
        tmp_path, "declared", {"title": "Declared title", "summary": "Declared summary."},
    )
    (family / "README.md").write_text("# Readme title\n\nReadme sentence.\n", encoding="utf-8")
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    (solution,) = available_solutions()
    assert (solution.title, solution.summary, solution.detail) == (
        "Declared title", "Declared summary.", "Declared summary.",
    )


def test_a_long_manifest_summary_is_capped_for_the_table_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    sentence = "A summary " + "long " * 40 + "enough to cap."
    write_family(tmp_path, "wordy", {"summary": sentence})
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    (solution,) = available_solutions()
    assert len(solution.summary) <= catalogue._SUMMARY_MAX
    assert solution.summary.endswith(catalogue._ELLIPSIS)
    assert solution.detail == sentence
