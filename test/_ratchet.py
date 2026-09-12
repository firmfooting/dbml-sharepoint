# test/_ratchet.py
"""One shape for every ratchet in this suite.

A RATCHET is a recorded set of known violations that a gate tolerates so the
rule can refuse NEW ones without a sweep landing first. Nine of them existed
before this module, each with its own assertions and its own wording, and all
nine were asking the same three questions:

1. Does an entry name something that no longer exists? A misspelled or
   renamed entry never matches, so it is subtracted from nothing and the live
   rule it was meant to cover loses its guard SILENTLY while the roster keeps
   a dead line for ever. This is the failure that makes a ratchet worse than
   no ratchet, and it is the one a hand-written `assert measured == recorded`
   reports least clearly.
2. Has an entry stopped violating? Then it has to come out in the same change,
   or the list rots into a permanent exemption nobody rereads. This is the
   ratchet turning, and it is the half that makes the number go down.
3. Is something violating that is not recorded? The regression the gate is
   for.

Question 1 needs a `universe` (every name that could legitimately appear);
without one it cannot be asked at all, which is why the sites that only
asserted equality could not ask it.

NOT a magnitude ratchet. `test_public_api.DEFERRED_IMPORTS` counts occurrences
per file rather than recording membership, so "has it stopped violating" is a
smaller number rather than an absent key, and exact dict equality already says
that in one line. Forcing it through here would lose the count.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class Ratchet:
    """The nouns one ratchet's failures are phrased with.

    Wording is per-ratchet because a message naming the constant and the thing
    it holds is what makes a failure actionable without opening this file. The
    LOGIC is not per-ratchet, which is the point.
    """

    #: The constant's name, so the message says what to edit.
    name: str
    #: What an entry names, for the stale-entry message: "FindingCode",
    #: "limit constant", "shipped column".
    subject: str
    #: What being on the list means, phrased as a state that can end:
    #: "now reached", "now guarded".
    resolved: str
    #: What a violation is, phrased as a predicate: "no test makes them fire".
    violation: str

    def problems(
        self,
        *,
        recorded: Iterable[str],
        violating: Iterable[str],
        universe: Iterable[str] | None = None,
    ) -> list[str]:
        """The ways this ratchet is currently wrong, empty when it is right.

        Pure, and returning rather than asserting, so the decisions can be
        tested directly rather than through whichever gate collects the sets.
        """
        recorded_set, violating_set = set(recorded), set(violating)
        found: list[str] = []

        stale: set[str] = set()
        if universe is not None:
            stale = recorded_set - set(universe)
            if stale:
                found.append(
                    f"these {self.name} entries name no declared "
                    f"{self.subject} and must be deleted:\n  "
                    + "\n  ".join(sorted(stale)),
                )

        # Stale entries are excluded rather than counted again. A name that
        # exists nowhere also violates nothing, so without this every typo
        # reports twice, once correctly and once telling the reader to delete
        # it because it has been fixed.
        turned = recorded_set - stale - violating_set
        if turned:
            found.append(
                f"these are {self.resolved} -- delete them from {self.name} "
                f"so the ratchet holds:\n  " + "\n  ".join(sorted(turned)),
            )

        new = violating_set - recorded_set
        if new:
            found.append(
                f"these are not on {self.name} and {self.violation}:\n  "
                + "\n  ".join(sorted(new)),
            )

        return found

    def check(
        self,
        *,
        recorded: Iterable[str],
        violating: Iterable[str],
        universe: Iterable[str] | None = None,
    ) -> None:
        """`problems`, raised. The spelling a gate that only asserts wants."""
        found = self.problems(
            recorded=recorded, violating=violating, universe=universe,
        )
        assert not found, "\n\n".join(found)
