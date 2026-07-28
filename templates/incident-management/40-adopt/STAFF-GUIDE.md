# Incident management — staff guide

## Reporting an incident (everyone — 3 minutes)

If something went wrong — safety, security, systems, facilities, a process
failure — report it. You don't decide whether it's "serious enough"; that's
what triage is for.

1. Open **IN_Incident** → **New**.
2. **What happened**: **Title**, one plain line — "Ladder left blocking
   fire exit, Store B". **Category**; pick the closest. **Occurred date**
   if it happened earlier than today, **Reported date** = today. Then
   **Detail**: what you saw, where, who was involved, what you did about it
   immediately. Facts, not fault.
3. **Triage**: **Severity** — your honest first guess; triage will adjust
   it.
4. Save. Done — you can't edit it afterwards (that's deliberate; add a
   follow-up comment to the handler if you remember something).

The New form doesn't ask you who will handle it or when it was resolved.
Those aren't yours, so they aren't there.

**If there is immediate danger, act and phone first. Report after.**

## Running an incident (handlers)

The incident list opens on **Open by severity** — everything live, grouped
by severity band and collapsed. An open **Critical** incident washes its
whole row pink; that is the only row-level signal on the list, and it is
reserved for exactly that.

1. **Triage queue** daily: set `Severity` properly, set `Handler` to
   yourself, Status → **Triaged**.
2. Work it: Status → **In progress**. Record what you learn in Detail
   (append, don't overwrite the reporter's words).
3. Fix the cause, not just the symptom: create **Corrective actions**
   linked to the incident, each with **one named person** and a due date.
   An action assigned to a team is an action assigned to nobody.
4. When the situation is resolved: Status → **Resolved**, and **Resolved
   Date** appears — the list will not save without it. Days-to-resolve
   calculates itself and draws a bar coloured by the incident's severity,
   so eight days reads differently on a Minor and on a Critical.
5. **Closed** only when every linked corrective action is Done or Cancelled
   (with a reason in its Notes). **By incident** is how you check: expand
   the incident, read its actions, then close it or don't. Nothing enforces
   this one — the two lists are separate and a save rule reaches only its
   own — so the view is the control.

## Working the actions

- **Open actions** (the default) — everything live, soonest due first.
- **Overdue** — past its due date and not finished. Due dates go red on
  their own, everywhere, and stop once the action is Done or Cancelled.
- **By owner** — grouped by the person who owns it. This is the chase
  list; take it to a meeting rather than a spreadsheet.
- **By incident** — the closure check above.

## What NOT to do

- Don't name-and-blame in Detail — describe events, not character.
- Don't report on behalf of someone who can report themselves.
- Handlers: don't delete reports, ever — even duplicates get Closed with a
  note pointing at the surviving row.
