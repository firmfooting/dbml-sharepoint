# test/test_journeys.py
"""The guards that keep the journeys honest.

Before journeys existed the only grouping over the families was four themes
hand-written into `solutions/README.md`, and nothing checked them. A family
could ship without appearing in any theme and the whole suite stayed green,
which is exactly what happened: one shipped family sat in no theme at all.

A grouping nothing verifies goes stale, so these are the checks that make the
journeys a contract rather than prose.
"""

from dbml_sharepoint.catalogue import (
    CORE_DISTRIBUTION,
    JOURNEYS_DIRNAME,
    SECTORS_DIRNAME,
    Journey,
    available_journeys,
    available_solutions,
)


def _core_journeys() -> list[Journey]:
    """Core's own journeys; a provider's may name another package's templates."""
    journeys = [j for j in available_journeys() if j.distribution == CORE_DISTRIBUTION]
    assert journeys, "core ships no journey, so these guards would pass over nothing"
    return journeys


def _core_ids() -> set[str]:
    return {s.id for s in available_solutions() if s.distribution == CORE_DISTRIBUTION}


def test_every_journey_names_only_families_that_exist() -> None:
    """A journey naming a deleted or misspelled family is a dead menu entry."""
    known = _core_ids()
    for journey in _core_journeys():
        missing = [i for i in journey.solution_ids if i not in known]
        assert not missing, (
            f"{journey.path.name} names {missing}, which is not a shipped family. "
            "Fix the id or drop it from the journey."
        )


def test_every_family_appears_in_at_least_one_journey() -> None:
    """The hole this file exists to close.

    A family reachable only by typing its exact name is a family nobody
    finds. Adding one now means placing it, which is a smaller decision at
    the point the family is written than it is a year later.
    """
    named = {i for journey in _core_journeys() for i in journey.solution_ids}
    orphans = sorted(_core_ids() - named)
    assert not orphans, (
        f"{orphans} appear in no journey, so the wizard can only reach them "
        f"through 'browse all'. Add each to a journey in "
        f"solutions/{JOURNEYS_DIRNAME}/, or write a new one."
    )


def test_a_journey_is_more_than_one_family_or_says_why() -> None:
    """A journey of one is a template with extra steps."""
    singles = {j.id for j in _core_journeys() if len(j.solution_ids) == 1}
    assert not singles, (
        f"{sorted(singles)} name one family each. A journey sequences families; "
        "one family needs no sequence."
    )


def test_journeys_and_sectors_are_not_offered_as_templates() -> None:
    """Both names are reserved beside the families for documentation."""
    ids = {solution.id for solution in available_solutions()}
    assert JOURNEYS_DIRNAME not in ids
    assert SECTORS_DIRNAME not in ids

