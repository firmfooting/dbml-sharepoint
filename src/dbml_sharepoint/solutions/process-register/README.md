# Process register

*Theme: process digitisation & improvement*

An inventory of how the organisation actually runs: every business process,
who owns it, how it's currently done (paper? email? spreadsheet? a real
system?), how much it hurts, and a **calculated digitisation-priority
score** (criticality × pain, 1–9) that turns "we should digitise things"
into a ranked worklist. One list: `PR_BusinessProcess`.

**The value case.** Digitisation programmes fail at step zero: nobody knows
what the processes *are*, so effort chases whoever shouted latest. The
inventory is the map — built in workshops in days, not months — and the
score makes the first ten targets obvious and defensible. It also surfaces
the quiet catastrophes: the critical process living in one person's
spreadsheet, the paper form nobody can find the master of. Six months
later, `DigitisationStatus` is your programme dashboard.

**Four declared views**, deployed with the paste — nothing to build by
hand: *The worklist* (the default, ranked by score), *Programme dashboard*
(grouped by status), *By function*, and *Key-person risk* — critical
processes still on paper or in a spreadsheet, which is the slide leadership
remembers. The score renders as a bar out of 9, coloured from the **Pain
level** beside it, so a severely painful process reads red whatever its
criticality drags the number down to. The review date turns red once
overdue, and stops shouting once a process is digitised or ruled out.

**One save rule and one column rule.** A process that is Planned, In
progress or Digitised needs a **Target state** — a plan with nowhere named
is not a plan — and a review date cannot be set more than twelve months
out, because the inventory refresh is annual.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit state/criticality language to your context |
| 2 | `20-configure/` | Prefix; everyone-contributes (inventory is a team sport) |
| 3 | `30-deploy/` | Administrator: build, paste, verify the score |
| 4 | `40-adopt/` | How to run the inventory workshops that fill it |
| 5 | `50-govern/` | Scoring definitions, programme cadence, done-means-done |

**Customisation points:** `CurrentState` reflects your reality (add your
legacy systems by name if that helps honesty — but re-read the
*Key-person risk* filter in `mapping.yaml`, which names two of those
members); the scoring definitions in governance are the calibration that
makes scores comparable across teams.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes six `[DEMO] `-titled rows across four functions, covering all
five current states and all six digitisation statuses, with two landing in
*Key-person risk* — so every view, every colour band and the score bar
render on a first look. See `30-deploy/DEPLOY.md`.
