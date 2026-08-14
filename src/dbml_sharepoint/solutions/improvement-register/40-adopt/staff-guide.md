# Improvement register: staff guide

## Raising an idea (everyone, 5 minutes)

Something in your work is slower, clunkier or riskier than it should be,
and you can see a better way?

1. **CI_Improvement** → **New**. The form asks for **The idea** and the
   three fields of **Plan the test**, and nothing else. Test notes, the
   after-measure and the outcome date only appear once there is something
   to put in them.
2. **Title**: the change, as a change: "Pre-fill the referral form from
   the booking record", not "referral form is annoying".
3. **Problem**: describe it as the people who feel it would; include the
   number if you have one ("takes ~30 minutes", "bounces back twice a
   week").
4. **Change idea**: what to try, and your prediction: "if we do X, we
   expect Y". A prediction is what separates a test from a tinker.
5. **Measure before**: the baseline. This field is required on purpose.
   Count something this week (even roughly: "timed 5 cases, avg 34 min").
   If truly nothing is countable, write "none available" and say why.

## Running an improvement (owners)

- **Planned**: you own it; the test is scoped, *small*: one team, one
  clinic, one fortnight. Big rollouts are for after the evidence.
- **Testing**: try it; log what happens in **TestNotes** (dated, newest
  first). Keep collecting the measure.
- **Study honestly**: did the number move the way the prediction said?
  - Yes → **Adopted**: **Measure after** and **Adopted date** appear on the
    form as you set the stage, and the list refuses to save without both.
    Then make the new way the standard way. That step is the actual
    improvement (see governance for what adoption requires).
  - No → **Abandoned**: record what was learned, and the **Adopted date**
    doubles as the abandon-decision date. An abandoned test with a lesson
    costs a fortnight; an unexamined rollout costs a year.

## The five views, and what each is for

Deployed with the list. There is nothing to build by hand.

| View | Use it when |
| --- | --- |
| **In flight** *(default)* | What is actually being run, grouped by owner |
| **Triage** | The fortnightly meeting: every Idea, oldest first |
| **Adopted this quarter** | The quarterly slide: adoptions with their before/after numbers |
| **The learning shelf** | The abandoned tests and what they taught, both measures side by side |
| **By source** | The loop check: are complaints, incidents and audits really feeding this? |

**One thing to know about "Adopted this quarter":** it is a rolling ninety
days, not a calendar quarter. SharePoint's view filters have no
calendar-quarter predicate. On the first day of a quarter the two differ,
so reconcile the slide against an export rather than the view if the exact
boundary matters.

## The two habits that keep this alive

1. **Feed it from the other registers.** Closing a complaint with a
   Learning field, an incident with corrective actions, an audit action.
   Ask each time: does this belong here as an improvement cycle? Put the
   origin in SourceRef.
2. **Celebrate Abandoned.** Publicly, occasionally. The register works
   when a failed test is a contribution, not a confession.
