# Project pipeline

One funnel for every project idea, from suggestion to decision to delivery.
One list: `PP_Proposal`, with stage gates as statuses and a **calculated
priority score** (benefit × feasibility, 1–9) that makes ranking a sort
instead of a shouting match.

**The value case.** Without an intake, projects start three ways: loudly,
politically, or secretly — and the organisation discovers its portfolio by
archaeology. A visible pipeline changes the conversation: every idea gets
written down the same way, scored the same way, and decided at a recorded
gate. The kill decisions become findable ("we declined that in March —
here's why"), which is half of what a PMO buys, at none of the cost.

**Five declared views**, deployed with the paste — nothing to build by
hand: *The funnel* (the default, grouped by stage), *Decision queue* (the
gate agenda, in score order), *Portfolio* (grouped by sponsor), *Graveyard*
(kept, and kept under that name — governance reads it annually), and
*Delivered*. The score renders as a bar out of 9, coloured from the
**Benefit** beside it, so a high-benefit proposal reads as green whatever
its feasibility drags the number down to. An unscored idea shows a blank
score, not a low one.

**Three save rules.** Ready for decision needs Benefit, Feasibility and
Cost Band; anything past the gate needs a decision date; Delivered needs a
delivered date. The rest of `50-govern`'s data-quality list stays a
governance check, and that document now says which parts and why —
Problem, Outcome and Sponsor are column types SharePoint validation
formulas cannot read.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit stages/cost bands to your delivery approach |
| 2 | `20-configure/` | Prefix; the scoring weights ARE the mapping formulas |
| 3 | `30-deploy/` | Administrator: build, paste, verify the score |
| 4 | `40-adopt/` | Proposers' guide + gate-keepers' guide |
| 5 | `50-govern/` | Gate authority, scoring honesty, portfolio review |

**Customisation points:** `CostBand` thresholds; the score is deliberately
simple (3×3) — resist adding weights until you've run the simple version
for two quarters and can say what it got wrong. If you rename a `Stage`
member, re-read every `where:` in `mapping.yaml`: five views filter on
stage names, and a renamed member empties a view without failing the build.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes six `[DEMO] `-titled rows — one per live stage plus a declined
and a delivered one — so every view, every rating band and the score bar
render on a first look. One is deliberately left unscored. See
`30-deploy/deploy.md`.
