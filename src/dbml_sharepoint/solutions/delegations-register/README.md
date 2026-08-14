# Delegations register

*Theme: governance, risk & compliance.*

Who may approve what, up to what limit, under which instrument. One list:
`DG_Delegation`: each authority stated as a **role** (not a person), with
its limit, conditions, source and review date.

**The value case.** Every approval process in the organisation leans on
delegations, and in most organisations they live in a PDF nobody can
search and a folklore everybody misquotes ("I'm pretty sure I can sign up
to ten"). The register makes the answer a filter, and it's the glue this
template library already assumes: change-register's authority table,
grants' bid approvals, project-pipeline's gates and audit-actions'
extension authorities all say *"per your delegations"*. This is where that
finally points. When an auditor asks "who approved this and were they
authorised?", the second half of the answer comes from here.

**Four views deploy with the list**: *By area* (the default working
lookup), *By role* (the ten-second check before you sign), *Reviews due*,
and *History*, which is how an approval made three years ago is read back
against the authority that existed then. A superseded delegation cannot be
saved without recording what replaced it. The form header links straight
to the instrument, because when the two disagree the instrument wins;
substituting that URL is a blocking step in `30-deploy/deploy.md`. Build
with `--seed` and five demo rows show every view working before you
transcribe a clause.

**Work the folders in order:**

| Step | Folder | You |
| --- | --- | --- |
| 1 | `10-design/` | Fit delegation areas to your instrument |
| 2 | `20-configure/` | Prefix; governance-maintains, everyone-reads |
| 3 | `30-deploy/` | Administrator: build, paste; load from the instrument |
| 4 | `40-adopt/` | How to check your authority in ten seconds |
| 5 | `50-govern/` | Instrument alignment, review cycle, acting arrangements |

**Customisation points:** `DelegationArea` enum; whether limits are stated
as amounts, ranges or references. Mirror your instrument's own language.
