# Improvement register

*Theme: process digitisation & improvement.*

A continuous-improvement log with test-before-adopt discipline: every
improvement idea moves Idea -> Planned -> Testing -> **Adopted** (or
**Abandoned**, honourably), with before/after measures recorded so
"improved" is a number, not a feeling. One list: `CI_Improvement`.

**The value case.** Organisations are full of improvement energy that
evaporates for want of somewhere to put it. This register catches ideas
from everywhere (staff suggestions, complaints, incidents, audit findings,
the data) and runs them through small, honest test cycles (Plan-Do-Study-
Act by intent, not by jargon). The two design commitments that make it more
than a suggestion box: every idea gets a **decision**, and every adoption
gets a **measured** before/after. Days-from-idea-to-adoption is calculated,
so the improvement system can itself be improved.

**Five declared views**, deployed with the paste, nothing to build by
hand: *In flight* (the default, grouped by owner), *Triage*, *Adopted this
quarter*, *The learning shelf* (kept under that name, the staff guide asks
people to celebrate what is on it), and *By source*. "Adopted this quarter"
is a **rolling ninety days**: SharePoint's view filters have no
calendar-quarter predicate, and the substitution is stated rather than
silently made.

**Two save rules.** An Adopted or Abandoned improvement needs its outcome
date; an Adopted one needs its **Measure after**. That is where "improved
is a number, not a feeling" stops being a slogan. The rest of `50-govern`'s
data-quality list stays a governance check, and that document now says
which parts and why. A prediction and three of the four adoption criteria
are judgements or multi-line text, and SharePoint validation formulas can
read neither.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit sources/benefit language to your framework |
| 2 | `20-configure/` | Prefix; everyone-contributes model |
| 3 | `30-deploy/` | Administrator: build, paste, verify |
| 4 | `40-adopt/` | The idea-to-test habit for staff and improvement leads |
| 5 | `50-govern/` | Test discipline, adoption criteria, the feeding loops |

**Customisation points:** `Source` enum (align to the registers you
actually run, this template is designed to be fed by complaints-feedback,
incident-management and audit-actions); and the `max:` on the
`DaysIdeaToOutcome` bar, which ships at 180 days because two quarters from
idea to outcome is a cycle that stopped being a test somewhere.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes six `[DEMO]`-titled rows, one per stage, from five different
sources, with two adoptions (one inside the rolling window and one outside
it) and an abandoned test whose lesson is written down. See
`30-deploy/deploy.md`.
