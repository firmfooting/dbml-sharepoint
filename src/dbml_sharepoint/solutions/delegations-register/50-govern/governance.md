# Delegations register: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Delegating authority | Board / CEO per your constitution | The instrument itself |
| Register owner | *(e.g. head of governance / company secretary)* | Register-instrument lockstep, reviews, this document |
| DG Governance Coordinators | The maintaining group | Transcription accuracy, supersession hygiene |

## The one iron rule: the register transcribes, never creates

Authority lives in the formally approved instrument of delegation. The
register is its searchable mirror, loaded clause by clause, in the
instrument's own wording, with the clause reference on every row. No row
exists without a clause; no clause change lands without a row change
(same week). Where transcription exposes ambiguity in the instrument,
that's recorded as an instrument issue for the next formal review. The
register never "clarifies" authority on its own.

## Instrument change workflow

1. The delegating authority approves an instrument change (new version).
2. Coordinators update the register the same week: changed rows edited
   with the new clause wording and ApprovedDate; removed authorities ->
   Status **Superseded** with the supersession noted; new authorities
   added. **The list now refuses to save a Superseded row with an empty
   `Notes`**. Step 2 is the one step of this workflow that is enforced
   rather than remembered.
3. The *History* view preserves what authority existed when, which is
   exactly what an auditor reconstructing an old approval needs. It
   deploys with the list, filtered to Superseded and sorted by
   `ApprovedDate` descending, with `Notes` beside each row.

## Acting arrangements

Delegations attach to roles, so acting appointments carry them **only
when the acting arrangement is formal** (an instrument or policy that
says acting = full delegations, or a specific acting instrument). Record
your organisation's rule here: ______. Informal "watching the shop"
carries nothing. The register's *By role* view is only truthful if
acting rules are.

## Review cycle

- **Annually** (or per your governance calendar): the delegating
  authority reviews the instrument; the register review rides along:
  every Current row's clause still exists, every ReviewDate resets.
- **Quarterly** (register owner): the *Reviews due* view, which deploys with
  the list, filtered to Current rows due inside a **rolling** ninety days
  (CAML has no calendar-quarter predicate, so it is ninety days from
  whenever you open it, not "this quarter"). Spot-check five rows against
  the instrument verbatim.

## Data-quality rules

1. Role names match your org structure's current titles. A delegation
   to a role that no longer exists is flagged at every review.
2. Limits and conditions are verbatim, not paraphrased.
3. Superseded rows are never deleted.

## What the list enforces, and what this document does

One step of the instrument-change workflow is now refused at save. The
three data-quality rules above are not, and cannot be.

**Enforced at save, SharePoint rejects the row:**

| Rule | Where it lives | Message shown |
| --- | --- | --- |
| A **Superseded** row must record its supersession in `Notes` | list validation | Names what the note has to say: which instrument version replaced it, and where the authority went |
| `ApprovedDate` cannot be in the future | list validation, hoisted from the column rule | Its sentence joins the list message |

The supersession rule is a cross-column rule, so it takes the list's single
`ValidationFormula`. The future-date rule reads only its own column, so it
lives there and keeps a message of its own, which is why it can say
something specific rather than sharing a sentence with an unrelated check.

**Still a governance check, nothing stops a wrong entry:**

- **Rule 1, role-not-person.** `RoleHolder` is free text and no formula can
  tell "Director of Nursing" from "Jane Chen". This is the register's most
  important editorial rule and it is entirely unenforceable; the quarterly
  five-row verbatim spot-check is the control.
- **Rule 2, verbatim limits and conditions.** A save rule can prove text
  exists. It cannot prove the text matches the instrument. The register
  cannot read the instrument, which is why the form header links to it.
- **Rule 3, never deleting a superseded row.** Deletion is a permission
  question, not a validation question: ordinary members read only, and
  Contribute is confined to DG Governance Coordinators. Sealed columns and
  `prevent_list_deletion` block the UI routes to losing the list itself.
- **That a `SourceInstrument` clause exists at all.** Same reason as rule 2.
- **Acting arrangements.** They are a rule about people, and the register
  holds only roles. The *By role* view is truthful only if your acting rule
  above is written down and followed.

**What the colours do, which is not enforcement but is useful.**
`ReviewDate` escalates to red once past, and the escalation is suppressed
on Superseded rows. A review date on an authority nobody holds is not a
deadline, and a date that keeps shouting after the row is finished trains
people to ignore the colour everywhere else.

## Lifecycle

The history IS the value: retain permanently (it decodes every historical
approval). Export before decommission; never run `rollback.js.txt` against
real rows.
