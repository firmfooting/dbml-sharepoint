# Measures register

*Theme: process digitisation & improvement*

A catalogue of the measures the organisation actually runs on: each KPI's
**definition** (numerator, denominator, exclusions), owner, target, data
source, frequency and reporting destination. One list: `MR_Measure`.

**The value case.** Ask three teams for "the complaints response rate" and
you'll get three numbers — different date anchors, different exclusions,
all defensible, none comparable. The measures register kills that quietly
expensive problem: one definition per measure, written down, owned, and
findable. It's also the backbone of the improvement theme — process-
register asks for a measure that proves digitisation stuck; improvement-
register asks for baselines; this is where those measures live permanently.
And when someone proposes a new report, the first question becomes "is the
measure registered?" — which is how measure sprawl dies.

**Five declared views**, deployed with the paste — nothing to build by
hand: *The catalogue* (the default, grouped by area), *By forum*,
*Definition reviews due*, *In development*, *Retired*. The review date
turns red once it is past due, and stops shouting once the measure is
retired.

**Two save rules.** An Active measure cannot be saved without a review
date, and a review date cannot be set more than twelve months out — the
"at least annual" cadence in `50-govern/governance.md` was a rule nothing
enforced until now.

**Work the folders in order:**

| Step | Folder | You |
|---|---|---|
| 1 | `10-design/` | Fit frequency/direction language to your reporting |
| 2 | `20-configure/` | Prefix; custodians-maintain model |
| 3 | `30-deploy/` | Administrator: build, paste, verify; load the current KPIs |
| 4 | `40-adopt/` | Writing definitions that survive contact with data |
| 5 | `50-govern/` | Definition change control, the annual measure cull |

**Customisation points:** none structural — the discipline is the product.
The definition-writing guide in `40-adopt` is the part to socialise. The
review cadence in `column_validation` is the one number worth agreeing
before first deploy.

**Demo data.** Build with `--seed` and the bundle gains a `demo-data.js.txt`
that pastes six `[DEMO] `-titled rows — four Active measures across four
areas and four forums, one Under development with no review date, and one
Retired — so every view and every status colour renders on a first look.
See `30-deploy/deploy.md`.
