# Visitor log — governance

## Ownership

| Role | Held by | Accountable for |
|---|---|---|
| Log owner | *(e.g. facilities/reception manager)* | The muster procedure, retention, this document |
| Reception | — | Front-door sign-ins, the morning tidy-up |
| Every host | — | Their guests: induction, escort rules, sign-out |
| Wardens | — | Using *On site now* at the assembly point |

## What the list enforces at save, and what stays a governance check

The register enforces two things itself, both with their own message on
the form:

| Enforced at save | Rule |
|---|---|
| `Signed In At` | Cannot be in the future |
| `Signed Out At` | Cannot be in the future |

Everything else in this document is a **governance check** — a habit, a
review or a drill, not something SharePoint refuses. Two of them look
enforceable and are not, and the reason is worth recording so nobody
spends an afternoon trying:

- **A sign-out earlier than its own sign-in.** SharePoint validation
  formulas can compare a column to a literal, and the condition grammar
  this template is written in only expresses that. Column-to-column
  comparison is not available, so a mis-typed sign-out saves. The morning
  tidy-up is what catches it.
- **A visitor with no host.** SharePoint validation formulas cannot read
  person columns at all — not as an operand, not as a null test. `Host` is
  therefore optional at save and mandatory by practice. A visitor row with
  no host is a name at the assembly point with nobody who knows where they
  went; reception fills it in, and the log owner audits for blanks.

The *Induction sighted* tick is likewise a record, not a gate: it appears
on the form only for Contractors and Students, and nothing stops a
contractor being signed in before it is ticked. That is deliberate — a
muster list must be able to record that somebody is in the building
whether or not their paperwork is in order. Whether they may then *work*
is the contractor rule below.

## The muster procedure (rehearse it)

*On site now* is the deployed default view: opening `VI_Visit` on a phone
lands on it. Rehearse against it — every evacuation drill includes the
register: wardens open the list at the assembly point and check visitors
off by name with their hosts. A drill that skips the visitor muster is
rehearsing the easy part.

After each drill, note what failed (phantom entries? missing sign-outs?)
and feed the fixes into the daily tidy-up habit.

## Contractor rules

- *Induction sighted* is ticked only on sighting evidence of the current
  site induction — the tick is a compliance record with a name and
  timestamp behind it.
- No induction, no work. Presence is recorded either way; permission to
  start is the host's call, not the form's.
- Contractor insurances/licences are **not** recorded here — that's the
  engagement process's job (pair with contract-register); this log records
  presence, not qualification.
- Contractors on site out-of-hours follow your permit/after-hours rules;
  the switchboard-log key register pairs naturally.

## Privacy and retention (load-bearing — visit rows are personal data)

1. Record the minimum: name, organisation, host, times, purpose in a few
   words. No phone numbers, no vehicle regos unless your site genuinely
   requires them (record the decision here if so).
2. **Retention**: keep visits for your safety/security window — commonly
   90 days to 2 years depending on site risk profile — then delete in
   bulk (monthly batch). Write your chosen period here: ______.
   A sign-in book kept forever is a surveillance archive nobody decided
   to build.
3. Subject access applies; the log owner handles requests.

## Data-quality rules

1. One row per person, no group entries.
2. The *Never signed out* view is emptied every morning — sign-outs
   back-filled honestly ("left approx 15:00 per host") are marked as such
   in the row.
3. Kiosk entries get a reception glance for legibility (a muster list of
   "asdfgh" protects nobody).

## Lifecycle

This register expects **routine deletion** per the retention rule above —
it and the other personal-data registers (onboarding, volunteers,
stakeholders) are the deliberate exceptions to keep-everything. Never run
`rollback.js.txt` against real rows.
