# test/test_family_count_prose.py
"""One gate: no tracked prose may state how many solution families ship.

The count under `src/dbml_sharepoint/solutions/` changes every time a family
is added, and it used to be written out in eighteen places across nine files.
Nothing read those sentences, so nothing noticed when they went wrong -- and
they did, repeatedly. Measured 2026-08-13, before this gate existed: with 32
families shipping, the repository variously claimed thirty, 30, 31 and 32,
with several statements predating three separate family additions.

`test/test_catalogue.py` warned in prose that "an assertion that thirty
templates exist goes stale the moment a family is added". That sentence was
itself stale. This is the executable version of it.

The counts that were CORRECT throughout were the asserted ones --
`len(solutions) == 32` and friends. A number that runs stays true; a number
that is merely written rots. So the rule is: put the count in an assertion,
or leave it out of the sentence.

A dated measurement is exempt. `RE-MEASURED 2026-08-12 across 32 templates /
57 entities` in test_template_standard.py is a record of a real join survey,
which AGENTS.md asks for by name ("If a live run teaches you something,
encode it: a dated comment"). A stale DATE is visible; a stale NUMBER is not.
"""

import re
import subprocess
from pathlib import Path

import pytest
from _paths import REPO_ROOT

#: A count qualifying a family noun: "32 shipped templates", "all thirty
#: families", "the 30 solution templates". Two-digit numerals only -- "one of
#: three lists" inside a family's own README is not a roster claim, and the
#: roster has never been under ten.
FAMILY_COUNT = re.compile(
    r"\b(?:all\s+|the\s+)?"
    r"(?:[0-9]{2}|twenty|thirty|forty)(?:[- ](?:one|two|three|four|five|six|seven|eight|nine))?"
    r"\s+(?:(?:shipped|solution|list)\s+)*"
    r"(?:templates|families|solutions|READMEs)\b",
    re.IGNORECASE,
)

#: A measurement that says when it was taken may keep its numbers. Case
#: insensitive because the join survey opens "Measured 2026-07-31" and
#: continues "RE-MEASURED 2026-08-12"; both are the same claim.
DATED_MEASUREMENT = re.compile(
    r"(?:RE-)?MEASURED[^\n]{0,40}?\d{4}-\d{2}-\d{2}", re.IGNORECASE,
)

#: Excluded for a reason, not for convenience:
#: - api/ is GENERATED from the docstrings this gate already covers, so an
#:   offender there names a file nobody edits by hand.
#: - superpowers/ holds specs and plans, which are point-in-time records.
#: - CHANGELOG.md is release history and correct as written.
#: - THIS file, because its fixtures must contain the very strings it hunts
#:   for. Found the honest way: the gate went green while untracked and
#:   failed on itself the moment it was committed. Nothing is lost by the
#:   exemption -- `test_the_gate_would_catch_a_reintroduced_count` below is
#:   the proof that the pattern still bites, and it does not depend on this
#:   file being scanned.
EXCLUDED = (
    "website/docs/api/",
    "docs/superpowers/",
    "CHANGELOG.md",
    "test/test_family_count_prose.py",
)


def _tracked_prose() -> list[Path]:
    """Every tracked .md and .py file the count could hide in."""
    result = subprocess.run(
        ["git", "ls-files", "-z", "--", "*.md", "*.py"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        # Skipping is honest; returning [] would make this vacuously pass and
        # it would stay green forever without reading a single file.
        pytest.skip(f"git ls-files unavailable: {result.stderr.strip()!r}")
    return [
        REPO_ROOT / name
        for name in result.stdout.split("\0")
        if name and not name.startswith(EXCLUDED)
    ]


def test_no_tracked_prose_states_the_family_count() -> None:
    """Adding a family must not require editing a single sentence.

    The failure names every site, because the whole point is that nobody
    should have to go hunting for the number.
    """
    offenders = []
    for path in _tracked_prose():
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for number, line in enumerate(lines, start=1):
            match = FAMILY_COUNT.search(line)
            if not match:
                continue
            # The marker may sit on the line above, where a docstring wraps.
            context = line + "\n" + (lines[number - 2] if number > 1 else "")
            if DATED_MEASUREMENT.search(context):
                continue
            relative = path.relative_to(REPO_ROOT).as_posix()
            offenders.append(f"{relative}:{number}: {match.group(0).strip()!r}")

    assert not offenders, (
        "Tracked prose states the shipped-family count, which goes stale the "
        "moment a family is added and which nothing else checks:\n  "
        + "\n  ".join(offenders)
        + "\n\nDrop the number -- 'the shipped templates' reads the same and "
        "cannot rot. If the number is genuinely evidence, stamp it with a "
        "measurement date ('MEASURED 2026-08-13: ...') so a reader can tell "
        "how old it is. The count belongs in an assertion, not a sentence."
    )


def test_the_gate_would_catch_a_reintroduced_count() -> None:
    """The complement, so the rule above cannot pass by matching nothing.

    Without this, a typo in FAMILY_COUNT that matched nothing at all would
    leave the gate permanently, silently green -- which is the exact failure
    it was written to stop.
    """
    caught = [
        "The 32 shipped list templates (schema + mapping + release per family)",
        "Run it with no arguments and pick one of the 32 shipped templates:",
        "enforces it across all thirty shipped families,",
        "Fourteen of the thirty READMEs open with a `*Theme: ...*` line",
        "The 30 solution templates are part of the package",
        "over 31 families.",
    ]
    assert [line for line in caught if not FAMILY_COUNT.search(line)] == []

    ignored = [
        "The shipped list templates (schema + mapping + release per family)",
        "Most, but not all, READMEs open with a `*Theme: ...*` line",
        "one of three lists",  # a family's own shape, not the roster
        "assert len(solutions) == 32",  # an assertion is the correct home
    ]
    assert [line for line in ignored if FAMILY_COUNT.search(line)] == []


def test_a_dated_measurement_keeps_its_numbers() -> None:
    """The join survey in test_template_standard.py must stay legal.

    It is the repository's worked example of encoding a real measurement, and
    a gate that forced its numbers out would be destroying evidence to satisfy
    a lint.
    """
    survey = "    RE-MEASURED 2026-08-12 across 32 templates / 57 entities, when"
    assert FAMILY_COUNT.search(survey), "the count itself must still match"
    assert DATED_MEASUREMENT.search(survey), "and the date must exempt it"

    undated = "    across 32 templates / 57 entities, when"
    assert not DATED_MEASUREMENT.search(undated)
