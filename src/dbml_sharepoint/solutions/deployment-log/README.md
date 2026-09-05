# Deployment log

*Theme: process digitisation & improvement.*

The fleet's own record of itself: one list (`dbml-deployment-log`) holding a
row for every deploy run this tool performs anywhere in the tenant, saying
what was deployed, to which site, by whom, from which release, and whether
the run finished. It is deployed like any other family, to one site you
nominate as the logging site, and every other family's deploy stamps it from
wherever it runs.

**The value case.** Without it, "when did the risk register last change, and
who changed it?" is answered by asking around. Each site keeps a hidden local
run log, but a local log can only answer questions about its own site, and
nobody opens twenty of them. This list is the one place the whole estate is
visible: an aborted run somebody never mentioned, a site still on last
quarter's schema version, the deployer version a support question needs.
Deploy it once, and it fills itself.

**What deploys with it:** four views (*Latest first*, *Aborted runs*, *Runs*,
*Provenance*), a four-section form for the one case a person writes a row by
hand, a save rule that refuses a stamp dated in the future, and five demo
stamps behind `--seed` so every view and every pill has something in it
before the first real deploy lands.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Read the stamp kinds; they are a contract, not a preference |
| 2 | `20-configure/` | Nothing to prefix; decide who holds Contribute |
| 3 | `30-deploy/` | Administrator: create the logging site, build, paste |
| 4 | `40-adopt/` | Who reads it, and what each stamp kind means |
| 5 | `50-govern/` | Retention, the rules no save rule can carry, permissions |

**Customisation points:** almost none, and that is deliberate. The list title,
the column internal names and the `StampKind` members are the addresses every
other family's deploy writes to, so renaming any of them stops the stamps
arriving rather than changing how they look. `prefix` is empty for the same
reason. What you do choose is the site it lives on, who holds Contribute
there, and how long stamps are kept.
