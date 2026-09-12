"""The per-finding reachability gate: which declared rules actually FIRE.

`test_findings.test_every_code_can_actually_be_produced` is a STATIC check --
it proves each `FindingCode` appears in a construction site somewhere in `src`,
and its own docstring says it does not prove any test reaches that site.

Total-coverage floors cannot close that gap either. Measured when this gate
was introduced: the suite sat at 95.25% against a 95 floor while 21 declared
codes were never constructed by any test. One rule's firing branch is a handful of lines out of
~6,000, so it disappears into the rounding and unrelated coverage gains offset
it indefinitely. An aggregate number cannot enforce a per-rule invariant.

So this gate observes the thing itself: every `FindingCode` a test run actually
constructs, checked against the roster at the end of the session. It watches
construction rather than reading coverage of the enclosing statement, which
also makes it immune to the lazy-comprehension problem -- a `FindingCode` inside
a generator expression passed to `findings.extend(...)` marks the outer line
executed even when the generator is empty and the `Finding(...)` body never
runs. Nothing is recorded here unless a finding was really built.

Opt-in, via `--check-finding-reachability`; CI passes it. Same reasoning as
`--cov`: it is only meaningful over a WHOLE suite run, and would fail loudly and
uselessly on `pytest test/test_joins.py`.
"""

from __future__ import annotations

from _ratchet import Ratchet

# Codes no test constructs yet. A ratchet that only shrinks: deleting a line is
# the point, and adding one needs a reason in the pull request. Measured, not
# guessed -- see the module docstring.
#
# Every name here is checked against `FindingCode` too, so a typo or a code that
# was later renamed or deleted fails the gate rather than silently disarming the
# guard for a rule that still exists.
# EMPTY since 2026-09-12. The last entry read "diagnosis reports an unknown
# operator before normalisation can try to negate it", which was FALSE for the
# view path: `checks/_views.py` normalises before that diagnosis runs, so the
# refusal escaped as an uncaught `ConditionRefusal` and the run reported
# nothing at all. Guarding it turned the crash into this finding.
NOT_YET_REACHED: frozenset[str] = frozenset()


#: This gate's wording. The three questions it asks are `_ratchet.Ratchet`'s,
#: shared with every other ratchet in the suite.
_RATCHET = Ratchet(
    name="NOT_YET_REACHED",
    subject="FindingCode",
    resolved="now reached",
    violation="no test makes them fire",
)


def evaluate(
    *,
    declared: frozenset[str] | set[str],
    seen: frozenset[str] | set[str],
    allowed_unreached: frozenset[str] | set[str] = NOT_YET_REACHED,
) -> list[str]:
    """Return the problems with one run's reachability, empty when clean.

    Pure on purpose: the pytest wiring that collects `seen` is awkward to test
    directly, and the decisions worth pinning are all here.
    """
    return _RATCHET.problems(
        recorded=allowed_unreached,
        # A declared code nothing constructed is the violation this gate is
        # for; the roster of declared codes is also the universe a stale
        # entry is measured against.
        violating=set(declared) - set(seen),
        universe=declared,
    )
