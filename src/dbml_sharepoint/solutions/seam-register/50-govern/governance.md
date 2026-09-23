# Seam register: governance

## Roles

| Role | Assignment | Responsibility |
| --- | --- | --- |
| Interviewer | SEAM Discovery Team group | Runs the interviews and owns the evidence: every evidence row, every artefact, every seam raised |
| Register owner | SEAM Discovery Team group | Owns the register's hygiene, the one-page seam map, and the order in which people are asked, because sequencing is politics |
| Contributor | SEAM Contributors group | A person offered rows to correct, such as the ICT manager or a provider's nominated contact. Edits without deleting |

Both members of the discovery team read every evidence row before a service
moves to *Verified*. That is a working rule, not a permission: the register
cannot tell who has read what.

## The exercise

Six weeks, three areas in the first pass: identity and access; backup,
retention and records; infrastructure and devices. Business applications
get one question each and otherwise wait for a second pass. Three ways in,
run in parallel: documents, incidents and people.

| Week | What happens |
| --- | --- |
| 1 | The provider list filled in. Document asks out. Interviews booked. The identity anchor session. Backup questions to the ICT manager with a five-working-day date |
| 2 | Backup, retention and records: answers or silence, each provider's own description through its channel, and whoever touches backups and records |
| 3 | The risk note to the chief executive's office, fed by the identity and backup rows that are Verified or visibly Assumed. Start infrastructure and devices |
| 4 | Triangulate with each provider: the rows **By provider** and **By support provider** list against it go in front of it row by row |
| 5 | Consolidate: every row gets a final confidence, every seam gets a type and a status, the backlog is sized |
| 6 | The one-page seam map and the hand-over |

## Rules

This section is the register's whole rule set. The README and the guide
describe how the exercise is run; where either says something is required,
the rule is here. Anything they describe that is not here is working
practice, and the register does not hold it.

### Save rules

SharePoint refuses a save that breaks one of these. Every required column
on a form is required as well, and a date the table below marks as
recorded cannot be in the future.

| List | A save is refused unless |
| --- | --- |
| Provider | **Provider** is unique |
| Service | **Title** is unique. **Run by** other than *Unknown* has a **Run by team**, and **Support from** other than *Unknown* has a **Support team**. **Single person** has an **Out of hours call**. **Last failure date** is recorded |
| Evidence | **Evidence date** is recorded |
| Seam | *Escalated* in **Status** has a **Resolve owner** and a **Resolve by**, and *Resolved* has a **Resolved on**. **Raised on** and **Resolved on** are recorded |
| DocumentRequest | Any **Status** past *To ask* has **Asked on**, **Due on**, a **Holder** and a **Held by** other than *Unknown*. *Received*, *Refused* and *Not found* have **Answered on**. A *Received* services agreement, services schedule or attestation in **Type** has **Signed by**, which may say *Unsigned*. **Asked on** and **Answered on** are recorded |
| Artefact | **Dated** is recorded |
| Interview | *Completed* in **Status** has **Minutes** and an **Interview date** that is not in the future. **Minutes** is 1 to 30 |
| Incident | **Title** is unique. A *Recalled outage* in **Source** has a **Source detail**. **Incident date** is recorded |
| WeeklyUpdate | **Week** is unique and 1 to 6. **Rows verified** and **Seams found** are not negative. **Week ending** is recorded |

### Friday checks

SharePoint validation cannot express these. Run them on the Friday, before
the five lines are written. A check that a view answers names the view.

| ID | Check | Why the register cannot enforce it |
| --- | --- | --- |
| F1 | A *Verified* service has two evidence rows that agree about the same **Bears on** column from two different known source sides, or one *System data* row, no evidence row with **Contradicts** ticked, and no unresolved *Disputed owner*, *Disputed support* or *Contradicts document* seam | A formula cannot count rows on another list |
| F2 | No service above *Assumed* has zero evidence rows | Same. A service with no evidence rows is *Assumed* by definition, whatever its confidence says |
| F3 | By the end of week 5, no first-pass service has zero evidence rows. Before then **Assumed** lists them as the week's work | Same |
| F4 | Every evidence row with **Contradicts** ticked appears in a seam's **Evidence in conflict** | A multi-value lookup on another list |
| F5 | Every row a seam picks in **Evidence in conflict** belongs to the seam's own **Service** | A lookup cannot be filtered by another column |
| F6 | A *Held* or *Verified* documentation status has a **Documentation link** | A hyperlink column cannot be a formula operand |
| F7 | A row whose side is *Provider*, *Third party* or *Shared* names the provider. **Provider not named** on the service, document request, interview and incident lists shows the rows that do not | A formula cannot read a lookup |
| F8 | An evidence row's **Artefact file**, where set, lists the evidence row's **Service** among its **Services** | A lookup cannot be filtered by another column, and the picker offers every titled file |
| F9 | Every file in **SEAM_Artefact** has a **Title** | A file's Title is optional on a library, and a file without one is not offered by the pickers |
| F10 | A resolved seam has a **Resolution** | Multi-line text cannot be a formula operand |
| F11 | A received, refused or not-found document has a **Summary** saying what came back or who said no | Multi-line text cannot be a formula operand |
| F12 | **Last failure date** and **Last failure** are filled together or not at all | Multi-line text cannot be a formula operand |
| F13 | A received document has at least one file in **SEAM_Artefact** whose **Request** points at it | A formula cannot count rows on another list |
| F14 | **Resolve by** and **Resolved on** are on or after **Raised on**; **Due on** and **Answered on** are on or after **Asked on** | A formula compares a column with a literal, not with another column |
| F15 | Every completed interview answers all eight questions; a refusal or a don't-know is written as the answer | Multi-line text cannot be a formula operand |
| F16 | Every completed interview has its notes in **SEAM_Artefact**, picked in **Notes file**, and the file picked has **Type** *Interview notes* | A formula cannot read a lookup |
| F17 | Every answer in a completed interview that makes a claim about a service has an evidence row against that service, bearing on the column the claim is about | A relationship the register does not model |
| F18 | A weekly update's **Title** names the same week as its **Week** | A formula cannot build text from a number and compare it |
| F19 | No row names a person | A reading check. Roles, never names |
| F20 | A *Disputed support* seam picks rows in **Evidence in conflict** with **Contradicts** ticked from at least two different known **Source side** values that bear on *Support*; a *Disputed owner* seam does the same on *Run by* or on *Decided by* | A formula cannot count a multi-value lookup |
| F21 | No two files in **SEAM_Artefact** share a **Title**, because the pickers show nothing else | Uniqueness on a library column has not been measured |
| F22 | By the week 6 hand-over, every seam not *Resolved* has a **Resolve owner**. Before then **Open seams** shows the ones without | An owner is only required once a seam is *Escalated*, and the deadline is a date in the exercise, not a status |
| F23 | Every seam except *No owner* picks the evidence rows it rests on in **Evidence in conflict**: at least one row, and for *Contradicts document* one *Document* row and one row of another **Type** | A formula cannot read a multi-value lookup |

### What the register does not check

- A field the form hides for the row's status or side keeps its value when
  the row moves back, and the row still saves. The form stays uncluttered;
  views and reporting filter on status and side, so the old value does not
  surface. No rule forbids it.
- Only the columns marked unique above are unique. Two evidence rows,
  seams, document asks or interviews may describe the same thing, and
  often should.
- An evidence row's **Source side** is the side that made the statement,
  and its file's **Source side** is the side that produced the file. They
  can differ, as when a provider's minutes record what our manager said,
  so no check compares them. F1 counts statements, not files.
- The weekly rhythm, the stop rules, the size of the first pass and who has
  read which evidence are working practice in the guide.

## Confidence

*Verified* is the only value with a rule, and the rule is F1. A row does
not move to *Verified* because it feels settled. A row does move back to
*Claimed* when a second source disagrees, and the disagreement becomes a
seam.

## Seams

A seam is the product of the exercise. It closes in one of two ways: a
source of truth is found and the service row is updated, which is
*Resolved* with a resolution saying what changed; or it is handed to a
decision-maker with a date, which is *Escalated* and stays open on this
register until the decision comes back. *Confirmed gap* is a seam we and
the provider agree is real; it may already carry an owner and a date, and
it stays open until it is resolved or escalated. Nothing is resolved by
quietly editing a service row.

## Retention

Keep every row and every file, including declined interviews, refused
documents and resolved seams. A provider that is no longer used is set to
*Retired*; neither group can delete one. The register is the evidence for the risk
note in week three and the hand-over in week six, and the backlog is the
second pass. Agree a retention label for the library with records
governance: interview notes and correspondence with a provider are the kind
of record that policy usually covers. Never use rollback to clean up.

## Hand-over

The outputs are the register, which nobody senior needs to read; the
one-page seam map, which is **Seam map** read alongside **By resolver**;
the six weekly updates; and the seam list itself with an owner against
every seam still open (F22). Hand over to whoever will run the second pass, with
**Backlog** as their starting list.
