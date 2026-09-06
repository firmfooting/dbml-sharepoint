# Deployment log

*Theme: process digitisation & improvement.*

The fleet's own record of itself: two lists, `firmfooting_Deployments` and
`firmfooting_Changes`, holding a row for every deploy run any firmfooting
application performs anywhere in the tenant, saying what was deployed, to
which site, by whom, from which release, whether the run finished, and what
it changed. They are deployed like any other family, to one site you
nominate as the logging site, and every other family's deploy writes to them
from wherever it runs.

**The value case.** Without it, "when did the risk register last change, and
who changed it?" is answered by asking around. A deploy that cannot reach
these lists keeps a hidden run log and a hidden change log on its own site,
but those can only answer questions about that site, and nobody opens twenty
of them. These lists are the one place the whole estate is visible: an
aborted run somebody never mentioned, a site still on last quarter's schema
version, the deployer version a support question needs, and which
application made a given change. Deploy them once, and they fill themselves.

**What deploys with it:** five views across the two lists (*Latest first*,
*Aborted runs*, *Runs* and *Provenance* on `Deployments`; *Latest first* on
`Changes`), a four-section form on each list for the one case a person writes
a row by hand, a save rule on each list that refuses a row dated in the
future, a drop-box permission posture so nobody can rewrite the record of
what they did, and six demo rows behind `--seed` so every view and every pill
has something in it before the first real deploy lands.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Read the stamp kinds; they are a contract, not a preference |
| 2 | `20-configure/` | Set the org prefix if `firmfooting` is not your organisation's token; decide who is in Members and who administers |
| 3 | `30-deploy/` | Administrator: create the logging site, build, paste |
| 4 | `40-adopt/` | Who reads it, and what each stamp kind means |
| 5 | `50-govern/` | Retention, the rules no save rule can carry, permissions |

**Customisation points:** almost none, and that is deliberate. The two list
titles, the column internal names and the `StampKind` members are the
addresses every other family's deploy writes to, so renaming an entity or a
column stops the stamps arriving rather than changing how they look. `prefix`
is the one part of the address you are meant to change: it is your
organisation's own token in place of the `firmfooting` placeholder, and every
other firmfooting application's deploy needs to agree on it. What else you do
choose is the site the lists live on, who is in their shared Members group
(they get submit-only: add a row, read back only their own, edit and delete
nothing), and how long stamps are kept.
