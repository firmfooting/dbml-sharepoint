# Compliance obligations

*Theme: governance, risk & compliance.*

Every obligation the organisation must meet (legislation, accreditation
standards, funding agreements, formal commitments) with an owner, a
compliance status, linked evidence and a review date. One list:
`CO_Obligation`.

**The value case.** Accreditation and audit both ask the same structured
question: *how do you know you comply?* Organisations without an
obligations register answer it fresh every cycle, from memory, expensively.
With one, the answer is standing: obligation -> owner -> evidence -> last
assessed. It also ends the quieter failure: obligations nobody owns
(the funding-agreement clause everyone assumes someone else reads). For a
health service this is the NSQHS/aged-care standards backbone; for anyone
else, swap in your acts, standards and contracts: the discipline is
identical.

**Five views deploy with the list**, including the accreditation pack:
*By source*, grouped by source type and then by the named instrument
inside it. A status other than *Not assessed* cannot be saved without a
date and a line of evidence, which is the whole assessment standard turned
into something the list refuses rather than something a document asks for.
Build with `--seed` and five demo rows show every status colour and both
grouping levels working before you load a thing.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit source types to your obligation landscape |
| 2 | `20-configure/` | Prefix; coordinators-maintain model |
| 3 | `30-deploy/` | Administrator: build, paste; load the obligations |
| 4 | `40-adopt/` | Writing obligations at the right grain; owner duties |
| 5 | `50-govern/` | Assessment standard, non-compliance handling, cycles |

**Customisation points:** `SourceType` enum; the obligation *grain*
guidance in `40-adopt` (the make-or-break editorial decision).
