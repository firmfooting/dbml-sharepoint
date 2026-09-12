# test/test_ratchet.py
"""`_ratchet.Ratchet`'s own decisions.

Every ratchet gate in this suite defers its judgement here, so a mistake in
this file disarms all of them at once and each one keeps passing while it does.
That is the same failure the ratchets exist to catch, one level up, which is
why the logic is pinned directly rather than through any gate that uses it.
"""

from _ratchet import Ratchet

R = Ratchet(
    name="ROSTER",
    subject="widget",
    resolved="now fine",
    violation="they are broken",
)


def test_a_ratchet_matching_reality_has_no_problems() -> None:
    assert R.problems(recorded={"a"}, violating={"a"}, universe={"a", "b"}) == []


def test_a_new_violation_is_named() -> None:
    """The regression the gate is for."""
    found = R.problems(recorded=set(), violating={"b"}, universe={"a", "b"})

    assert len(found) == 1
    assert "not on ROSTER and they are broken" in found[0]
    assert "b" in found[0]


def test_an_entry_that_stopped_violating_must_come_out() -> None:
    """The ratchet turning. Without this the list rots into a permanent
    exemption nobody rereads, which is the state it exists to prevent."""
    found = R.problems(recorded={"a"}, violating=set(), universe={"a"})

    assert len(found) == 1
    assert "now fine" in found[0]
    assert "delete them from ROSTER" in found[0]


def test_an_entry_naming_nothing_is_named_as_a_dead_line() -> None:
    """The failure that makes a ratchet worse than no ratchet: the entry
    matches nothing, so the live rule it was meant to cover loses its guard
    while the roster keeps the line for ever."""
    found = R.problems(recorded={"typo"}, violating=set(), universe={"a"})

    assert len(found) == 1
    assert "name no declared widget" in found[0]
    assert "typo" in found[0]


def test_a_dead_line_is_not_also_reported_as_fixed() -> None:
    """A name that exists nowhere violates nothing, so the naive subtraction
    reports it twice: once correctly, and once telling the reader to delete it
    because it has been fixed. Only the first is true."""
    found = R.problems(recorded={"typo"}, violating=set(), universe={"a"})

    assert len(found) == 1, found


def test_without_a_universe_the_dead_line_question_is_not_asked() -> None:
    """Not every ratchet has a roster to check against. One that does not
    must not have its entries read as dead lines by default."""
    assert R.problems(recorded={"typo"}, violating={"typo"}) == []


def test_all_three_problems_are_reported_together() -> None:
    """One run, one list. A gate that reported only the first would need three
    runs to clear three faults."""
    found = R.problems(
        recorded={"typo", "fixed"}, violating={"new"}, universe={"fixed", "new"},
    )

    assert len(found) == 3
    joined = "\n".join(found)
    assert "typo" in joined and "fixed" in joined and "new" in joined


def test_check_raises_what_problems_returns() -> None:
    try:
        R.check(recorded=set(), violating={"b"}, universe={"b"})
    except AssertionError as raised:
        assert "b" in str(raised)
    else:  # pragma: no cover - the assert above is the contract
        raise AssertionError("check() accepted an unrecorded violation")
