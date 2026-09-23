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

## Data quality

The save rules hold what a formula can hold: a named operator or supporter
has a team beside it, a single-person service has its out-of-hours answer,
an escalated seam has an owner and a date, a resolved seam has its date, an
asked document has its dates, a completed interview has its duration within
thirty minutes, a remembered outage says who remembered it, and no recorded
date is in the future.

The following are governance checks, because SharePoint validation cannot
express them. Run them on the Friday, before the five lines are written.

| Check | Why the register cannot enforce it |
| --- | --- |
| A *Verified* service has at least two evidence rows from different source sides that agree, or one *System data* row | A formula cannot count rows on another list |
| No first-pass service has zero evidence rows | Same. A service with no evidence rows is *Assumed* by definition, whatever its confidence says |
| Every evidence row with **Contradicts** ticked appears in a seam's **Evidence in conflict**, and every row a seam picks there belongs to the seam's own **Service** | A multi-value lookup on another list; a lookup cannot be filtered by another column |
| A *Held* or *Verified* documentation status has a **Documentation link** | A hyperlink column cannot be a formula operand |
| A row whose side is *Provider*, *Third party* or *Shared* names the provider. **Provider not named** is empty on the service, document request, interview and incident lists | A formula cannot read a lookup |
| An evidence row's **Artefact file**, where set, lists the evidence row's **Service** among its **Services** | A lookup cannot be filtered by another column, and the picker offers every titled file |
| Every file in **SEAM_Artefact** has a **Title** | A file's Title is optional on a library, and a file without one is not offered by the pickers |
| A resolved seam has a **Resolution**; a received, refused or not-found document has a **Summary** saying what came back or who said no | Multi-line text cannot be a formula operand |
| **Last failure date** and **Last failure** are filled together or not at all | Multi-line text cannot be a formula operand |
| A received document has at least one file in **SEAM_Artefact** whose **Request** points at it | A formula cannot count rows on another list |
| **Resolve by** and **Resolved on** are on or after **Raised on**; **Due on** and **Answered on** are on or after **Asked on** | A formula compares a column with a literal, not with another column |
| Every completed interview answers all eight questions; a refusal or a don't-know is written as the answer | Multi-line text cannot be a formula operand |
| Every completed interview's answers have been transcribed into evidence rows | A relationship the register does not model |
| A weekly update's **Title** names the same week as its **Week** | A formula cannot build text from a number and compare it |
| No row names a person | A reading check. Roles, never names |

## Confidence

*Verified* is the only value with a rule, and the rule is the two-source
rule above. A row does not move to *Verified* because it feels settled. A
row does move back to *Claimed* when a second source disagrees, and the
disagreement becomes a seam.

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
every entry. Hand over to whoever will run the second pass, with
**Backlog** as their starting list.
