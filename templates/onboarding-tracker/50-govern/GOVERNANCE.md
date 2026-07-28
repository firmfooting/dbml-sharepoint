# Onboarding tracker — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Process owner | *(e.g. HR manager)* | The standard task set, overall SLA, this document |
| Coordinator (per starter) | HR | Creating the record + tasks, chasing overdue |
| Each function | Their queue | Their tasks, honestly statused |
| Hiring manager | Per starter | Day-one readiness, post-start tasks |

## The standard task set (edit to your organisation, review annually)

| Function | Task | Due |
|---|---|---|
| HR | Contract signed & filed | start − 10 |
| HR | Payroll & super forms to Finance | start − 7 |
| Finance / payroll | Payroll setup complete | start − 3 |
| IT | Account created, licences assigned | start − 3 |
| IT | Laptop/phone ordered and imaged | start − 3 |
| Facilities | Desk, access pass, parking | start − 2 |
| Manager | First-week plan and buddy assigned | start − 2 |
| HR | Induction booked | start + 2 |
| Manager | Week-one check-in done | start + 5 |
| HR | Probation checkpoint scheduled | start + 10 |

## Monitoring

- **Weekly** (coordinator): *Overdue before start* to zero; chase by
  function, escalate to the process owner anything overdue twice. Then
  *Starting soon* for the fortnight ahead.
- **Monthly** (process owner): completion stats per function, read off
  *Open by function*; recurring late tasks get a process conversation,
  not a nag.
- **At each closure** (coordinator): *Complete and withdrawn* is where the
  privacy trim below is worked from.

## What is enforced at save, and what stays a governance check

Three rules refuse a save. Everything else on this page is a discipline,
and the difference is worth knowing precisely rather than assuming the
software has your back:

| Rule | Where it lives | Why there |
|---|---|---|
| A task cannot be dated done in the future | **Enforced at save**, on the column | Reads only its own column, so it keeps its own message. A forward-dated completion is indistinguishable from a real one in every view and in the monthly stats |
| Status **Done** needs a done date | **Enforced at save**, on the list | Cross-column, so it shares the list's single validation formula with the rule below and its message names both |
| Status **Not applicable** needs a word in Notes | **Enforced at save**, on the list | A task closed with nothing behind it is indistinguishable from one nobody looked at. `Notes` is single-line nvarchar precisely so a validation formula can reference it — SharePoint refuses a multi-line column as an operand |
| That the standard task set was actually created for a hire | **Governance check** | Nothing on `Starter` can know what tasks *should* exist. The task set above is the control; *By starter* is where it is read back |
| That a due date is right relative to the start date | **Governance check** | Cross-list arithmetic. SharePoint validation formulas cannot reach the parent row at all |
| That withdrawn and completed records are trimmed on time | **Governance check** — the privacy rules below | Retention is a decision about time passing, and no save-time rule can see it |

## Privacy (this register holds personal data)

- Site membership is limited to onboarding participants; don't widen the
  site audience for convenience.
- Record only what the process needs — role, dates, logistics. **No**
  salary, visa, health or background-check detail; those live in HR's
  systems of record.
- Withdrawn starters: after closing the tasks, trim the record to name +
  "Withdrawn" and clear Notes — you no longer have a reason to hold the
  logistics detail.
- Completed starters: keep rows for the probation period + your HR
  retention rule, then delete or anonymise per policy. (This is the one
  register in the set where deletion is *expected* at end-of-life.)

## Lifecycle

The **leavers/offboarding variant** is this same design with the task set
inverted (access revoked, equipment returned, payroll ended) — copy the
template, change the prefix to `LV_`, and reuse everything else.
