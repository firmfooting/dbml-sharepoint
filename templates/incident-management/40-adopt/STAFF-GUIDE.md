# Incident management — staff guide

## Reporting an incident (everyone — 3 minutes)

If something went wrong — safety, security, systems, facilities, a process
failure — report it. You don't decide whether it's "serious enough"; that's
what triage is for.

1. Open **IN_Incident** → **New**.
2. **Title**: one plain line. "Ladder left blocking fire exit, Store B."
3. **Category**; pick the closest. **Severity**: your honest first guess —
   triage will adjust it.
4. **Reported date** = today. **Occurred date** if it happened earlier.
5. **Detail**: what you saw, where, who was involved, what you did about it
   immediately. Facts, not fault.
6. Save. Done — you can't edit it afterwards (that's deliberate; add a
   follow-up comment to the handler if you remember something).

**If there is immediate danger, act and phone first. Report after.**

## Running an incident (handlers)

1. **Triage queue** view daily: set `Severity` properly, set `Handler` to
   yourself, Status → **Triaged**.
2. Work it: Status → **In progress**. Record what you learn in Detail
   (append, don't overwrite the reporter's words).
3. Fix the cause, not just the symptom: create **Corrective actions** linked
   to the incident, each with an owner and a due date.
4. When the situation is resolved: set **ResolvedDate**, Status →
   **Resolved**. Days-to-resolve calculates itself.
5. **Closed** only when every linked corrective action is Done or Cancelled
   (with a reason in its Notes).

## What NOT to do

- Don't name-and-blame in Detail — describe events, not character.
- Don't report on behalf of someone who can report themselves.
- Handlers: don't delete reports, ever — even duplicates get Closed with a
  note pointing at the surviving row.
