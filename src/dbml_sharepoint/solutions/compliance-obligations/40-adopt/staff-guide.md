# Compliance obligations: guide

## Getting the grain right (read this before loading anything)

The register lives or dies on obligation *size*:

- **Too coarse** ("Comply with the Privacy Act") is unactionable: no
  single owner, no single evidence, status means nothing.
- **Too fine** (a row per sub-clause) collapses under its own review
  burden by year two.
- **Right**: one row per *duty that one owner can evidence*: "Report
  notifiable data breaches to the OAIC within 72 hours", "Maintain a
  current food safety program at each kitchen". Rule of thumb: if you
  can't name the evidence in one sentence, split it; if ten rows share one
  owner and one evidence link, merge them.

Expect 10–40 rows per major instrument, not 3 and not 300.

## The five views

The list opens on **By owner**: every obligation, grouped and collapsed by
who owns it. Find your name, expand it, and that is your list. Four other
views are already built for you:

| View | What it shows |
| --- | --- |
| **By owner** | The default. Everything, grouped by owner. |
| **The gap list** | Non-compliant and Partially compliant rows, worst first, with the Notes column beside them. |
| **Not yet assessed** | Rows still on *Not assessed*, grouped by owner. |
| **Reviews due** | Anything due for reassessment inside the next sixty days, a *rolling* sixty days, not "this quarter". |
| **By source** | The accreditation pack: grouped by source type, then by the named instrument inside it. |

You don't need to build any of these, and you shouldn't rename them: a
redeploy puts the declared name back.

## Writing a row (coordinators, with the owner)

The form has four sections, in the order the work happens.

1. **The duty**: **Title** as a duty, verb first. **Source type** and
   **Source instrument**, the latter precise enough that a stranger finds
   the clause. Those two are the grouping levels of the accreditation
   pack, so sloppiness here shows up as a chapter heading nobody
   recognises. **Obligation detail** is the duty translated into *our*
   operations: what we actually do that discharges it.
2. **Assessment and evidence**: status stays **Not assessed** until a
   real assessment happens; an unassessed truth beats an optimistic guess.
   **Last assessed date** is not even on the form until you move off *Not
   assessed*, and once you do, the register will not let you save without
   it. Choose *Compliant*, *Partially compliant* or *Non-compliant* and it
   also wants **Evidence notes**: one sentence on what the evidence is
   and where more of it lives.
3. **Gaps and remediation**: **Notes**. Nothing checks this field, and it
   is the one the governance rules lean on hardest: a gap row without a
   remediation pointer here is the register's real failure mode.
4. **Ownership and cycle**: **Owner** is the person whose role discharges
   the duty, not the compliance coordinator (they run the register, not
   the obligations). **Review date** is required and colours red once it
   passes, on every row.

## Owning an obligation

- You'll be assessed against it on the review cycle: bring the evidence,
  current, linked.
- If reality changes (new process, lost capability, changed law) tell
  the coordinators *then*, not at review time. A status that went stale
  silently is the register's only real failure mode.
- **Non-compliant is safe to say.** The register exists to find gaps
  while they're cheap; the governance rules protect honest reporting:
  a gap raised is a remediation; a gap hidden is a finding.

## When the law or standard changes

Coordinators sweep affected rows (open **By source** and expand the
instrument that changed; that second grouping level exists for exactly this
sweep), update ObligationDetail, and reset statuses to Not assessed where
the duty materially moved. Resetting a status to *Not assessed* takes
**Last assessed date** off the form but does **not** clear it; SharePoint
has no mechanism to do that, so an old date can survive behind a reset
status. Nothing reads it there. New instruments get the
one-slice-end-to-end treatment.
