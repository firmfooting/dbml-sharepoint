# Legal compliance register: governance

## Ownership

| Role | Held by | Accountable for |
| --- | --- | --- |
| Compliance owner | *(e.g. head of governance/quality)* | The register's coverage, the assessment standard, reporting, this document |
| LC Compliance Coordinators | The maintaining group | Filing each period's SAQs, keeping the topic register current, chasing due dates |
| LC Assessment Owners | The business owners and executives named on topics | Completing and confirming SAQs under their own names |
| Business owner (per topic) | `Topic.BusinessOwner` | Answering the SAQ for the topic each period |
| Executive responsible (per topic) | `Topic.ExecutiveResponsible` | Confirming each result against the file; owning any action arising |
| Licence holder (per topic) | `Topic.LicenceHolder` | Recording the confirmed result in the compliance portal |

## Assessment standard

A result is real only when the executive responsible has confirmed it
**against the file**, and dated it (`CompletedDate`). Reading the panel is
not confirming; opening the SAQ and checking that the answers match the
evidence the business owner names in `Notes` is.

- **Compliant**: every question answered and evidenced; the practice the
  answers describe actually happens (spot-check, do not just file-check).
- **Partially compliant**: met in part; the gap is named in `Notes` and an
  action is linked in `ActionUrl`.
- **Non-compliant**: the duty is not being met; non-compliance handling
  below applies.
- **Not assessed**: the SAQ has not been answered. A result is never
  implied by a blank, which is why this member exists.

## Separation of duties

The person who completes a SAQ does not set it *Complete*. The business
owner answers and sets *Submitted*; the executive responsible confirms and
sets *Complete*. Where one person holds both roles for a topic, the
compliance owner confirms.

This is not enforceable by permission: both roles hold the same level on
the library, and SharePoint cannot make one status value the property of
one group. It is stated as policy and it is visible: the file's version
history records who set each status, and the quarterly review samples it.

## Non-compliance handling

1. Every *Partially compliant* or *Non-compliant* result carries an action
   with an owner and a date, recorded on `audit-actions` or
   `improvement-register` and linked from `ActionUrl`. The action lives
   there, never here; this register holds the result and the pointer.
2. The result is reported to the oversight committee named on the topic at
   its next meeting, with the action beside it.
3. Honest reporting is protected explicitly: a gap a business owner raises
   is the system working. Regulatory self-disclosure decisions remain with
   the executive; the register informs them and does not make them.

## Recording in the portal

The compliance portal is the statutory system of record and the library is
the working record. Comply Online, Law Compliance's portal, is the worked
example: it issues an SAQ per topic each quarter, and its delegation tier
would let business owners answer in the portal directly; an organisation
holding a handful of seats re-keys instead. Only the named licence holders
log in, and each topic names which one records its results.

The shared generic login is retired at go-live. If it must persist for a
transition, three interim controls apply: the password is held in the
organisation's password vault and nowhere else, it is rotated after each
use, and whoever used it writes their name and the date in the SAQ's
`Notes` beside the recording date, so the audit trail the library provides
is not broken at the last step.

A confirmed result is recorded within five business days of confirmation.
**To record in the portal** is the worklist and is expected to be empty at
the end of each week.

## Register changes

The owner columns exist on both entities, and only one of the two copies
is the truth at any moment:

- **The SAQ row's owners are the assignment of record for that period.**
  Who was accountable for the 2026 Q2 SAQ is a historical fact and must not
  change when the register changes in 2026 Q4. The file's version history
  is the evidence.
- **The register's owners are the default for the next filing**, and the
  value open SAQs should follow when it changes.

So drift is a defect only on open SAQs (*Required*, *In progress*,
*Submitted*) whose owners disagree with their topic. Closed SAQs may
disagree.

**The reassignment procedure.** When a topic's business owner, executive
or division changes, the coordinator opens **Pending**, filters the
**Topic** column to that topic, updates the open rows in Quick edit, and
only then saves the change to the topic row. Two minutes per topic. A
division change also moves the open files to the new folder.

**The drift audit.** The reporting bundle carries `OwnerDrift`, computed
in Power Query from the SAQ's owner ids against its topic's, and true only
on an open SAQ that disagrees. Keep it on the report's documentation page
beside the `_UserAddedColumns` audit; expected all false, and any true row
is a reassignment that was skipped.

**The optional flow.** A Power Automate flow can do the reassignment
instead: on a change to `Topic.BusinessOwner`, `Topic.ExecutiveResponsible`
or `Topic.Division`, update the same three columns on every SAQ whose
`Topic` matches and whose `Status` is open. It is described here and not
shipped. If you build it, declare the columns it binds under
`watched_lists` in `20-configure/mapping.yaml` (the block is there in a
comment), so a rename fails the build rather than the flow, and grant its
identity through a declared group rather than by hand, because
`reconcile: exact` removes a hand-added grant on the next deploy.

## Review cycles

| What | When |
| --- | --- |
| Filing the period's SAQs | Each calendar quarter, as the portal releases them |
| Chasing | Weekly, from **Overdue** |
| Recording | Weekly, from **To record in the portal**; empty by Friday |
| The topic register | Quarterly: owners and licence holders still current; leavers reassigned within a month |
| Retired topics | Annually: whether any has come back into scope |

## Reporting

- **Quarterly** to the executive and the oversight committees: results by
  division, every gap with its action, the overdue count and the
  not-yet-recorded count.
- **The generated Power Query bundle** carries both lists and the
  `OwnerDrift` audit. A reporting account is enrolled through the
  `dbml Enterprise Readers` group (`30-deploy/deploy.md`, Enterprise
  reporting access); nothing is shared by hand.

## Data-quality rules

1. Every SAQ past *Required* names its topic, division, both owners and a
   due date.
2. *Submitted* or *Complete* carries a result other than *Not assessed*;
   *Complete* carries a completed date.
3. Every gap result carries an action link.
4. Every *Complete* SAQ is recorded in the portal within five business days.
5. The owners on every open SAQ match its topic.

## What the library enforces, and what this document does

Rules 1 and 2 are refused at save in part, and the reasons the rest are not
are worth knowing rather than discovering.

**Enforced at save (SharePoint rejects the row):**

| Rule | Where it lives | Message shown |
| --- | --- | --- |
| A status past *Required* needs `Division` and `DueDate` | list validation | Shared, names all three list checks |
| *Submitted* or *Complete* needs a `Compliance` other than *Not assessed* | list validation | Shared, names all three list checks |
| *Complete* needs a `CompletedDate` | list validation | Shared, names all three list checks |
| `CompletedDate` and `ExternalRecorded` cannot be in the future | list validation, hoisted from the column rules | Their sentences join the list message |
| `PeriodYear` is four digits, 2024 to 2100 | column validation | Its own |

The three list rules share one message because a SharePoint list has
exactly one validation formula and cannot say which branch failed. The
year rule reads only its own column, so it lives there and keeps a message
of its own.

**Still a governance check (nothing stops a wrong entry):**

- **The topic and the owners on a SAQ (rule 1, the other half).** `Topic`
  is a lookup and the owners are person columns, and neither can be an
  operand in a validation formula. A required column would not close the
  gap either: a file uploaded over REST lands with the column empty and is
  not checked out. **Pending** shows both owners beside every open file so
  a blank is visible where the coordinator looks daily.
- **The action link (rule 3).** A hyperlink column is refused in a
  validation formula outright, measured on a live tenant. **My
  accountability** shows `ActionUrl` beside `Compliance` so its absence is
  visible at confirmation.
- **Recording timeliness (rule 4).** A rule about a date being set within
  days of another is a report, not a save rule. **To record in the portal**
  sorted by completed date is the worklist.
- **Owner drift (rule 5).** Cross-list, so unreachable by any formula. The
  `OwnerDrift` audit is the control.
- **That a result is true.** A save rule proves a result and a date exist.
  Whether the answers match the evidence is what the assessment standard,
  and the executive opening the file, is for.

**What the colours enforce, which is nothing, but usefully.** `DueDate`
escalates to red once it is past and stops once the status is *Complete*
or *No longer required*, so a finished SAQ does not keep shouting and
train people to ignore the colour on the ones that are late.

## Lifecycle

Retire topics, never delete them: `Status: Retired` keeps every SAQ ever
filed for the topic in the library with its history. Files are kept; their
retention follows the label applied to the library by hand at deploy
(`30-deploy/deploy.md`), which is a records-governance decision. Folders
are never renamed after go-live, because the URL is the file's identity
and every link to a file breaks with it. Export before decommission, and
never run `rollback.js.txt` against real files: a deleted file goes to the
recycle bin, and the library goes with it.
