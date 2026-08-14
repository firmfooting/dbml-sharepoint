# Using the service evidence register

This register exists so that when someone asks *"can you show me?"*, you can.

Everyone can name three things the provider got wrong. Almost nobody can
produce dates, reference numbers and what it cost, six months later, from
memory. That gap is the entire reason this list exists, and it closes only
if the events go in when they happen.

## Log it the same day

This is the one habit that matters more than anything else on this page.

A record made at the time carries weight that a better-written one made next
month does not. It is why every row shows **Record Timeliness** (*Same day*,
*Within a week*, *Delayed* or *Retrospective*) calculated from the gap
between when it happened and when you wrote it down. Nobody has to take our
word for how this register was kept; each row says.

Two minutes today beats twenty minutes in six months, and it is worth more.

## Logging an event: the one-minute path

Open **SE_ServiceEvent** and press **New**.

1. **What happened**: one line, plain language.
2. **Event Nature**: leave it on **Single occurrence** if the thing happened
   and is over.
3. **Occurred At**: when. Include the time if it matters.
4. **Which service**, and **Failure Mode**: what kind of thing went wrong.
   Take a moment on Failure Mode: it is the column that turns a list of bad
   days into a pattern.
5. **The account**: facts only. What happened, in what order, with times.
   Keep what you *think* of it out of this box; there is another one for that.
6. **How you know**, **Provider Reference**, **Evidence Held**: the three
   fields it is tempting to skip. Do not skip them. See below.
7. **Impact**: severity, roughly how many people, roughly how many hours.
   Estimates are fine. Write 1 if it was only you.
8. **Raised with provider**: did you tell them, and when?

Save. That is the whole thing.

## The three fields worth thirty seconds

**How you know.** Did you see it yourself, or were you told? Say so plainly.
A second-hand account is still worth recording. It just carries less weight,
and it is far better to have that written on the row than to have somebody
assume it was first-hand.

**Provider reference.** Their ticket or case number. This is the most useful
thing on the form. With it, the provider can look the event up in their own
system and confirm it happened; without it, the whole row rests on your word
against theirs. If there is a reference, get it in.

**Evidence held.** What actually backs this up: an attachment, their ticket,
an email, or nothing but your recollection. *None, recollection only* is a
legitimate answer and you should use it when it is true. Being honest here is
what makes the rest of the register believable.

## When it is a request nobody has actioned

Set **Event Nature** to **Unactioned request or ticket**. Two fields appear,
and one you have already filled in changes meaning:

- **Occurred At** now means *the date you raised it*: that is when the clock
  starts.
- **Response Due Date**: when they promised, or when their published target
  says it should have been done. This is what turns red when it passes.
- **Last Followed Up**: the date you last chased. Fill it in now if you
  already have; you cannot come back and change it later.

**Resolved Date** is on the form whatever the Event Nature: leave it blank
while it is still outstanding. If you do fill it in, pick the **Outcome for
us** beside it: the form will not save one without the other, in either
direction.

You must give a **Provider Reference** for this kind of event. A complaint
about an unactioned request that cannot say *which* request is not evidence,
so the form will not let you save without it.

## Every time you chase, add a follow-up

Open **SE_FollowUp** and press **New**. Record what you asked, how you asked
it, who (by **role**, not by name), how far up the escalation ladder you went,
and what came back.

This feels like extra work the first time and pays for itself the first time
somebody says *"nobody raised this with us"*. Four dated rows against one
request, each with what was asked and what was answered, ends that
conversation. A single sentence saying "we chased them repeatedly" does not.

**Your follow-up row is the record: you do not go back and edit the event.**
You cannot: once you have saved an event it is fixed, and that is what makes
it worth having. Nothing links the two lists automatically either, so
**Last Followed Up** on the event is carried across by a curator as part of
the weekly chase, and reconciled against **By event** each month.

**If the answer arrives afterwards, tell a curator: do not open a second
row.** Receiving an answer is not a chase, and a second row would be counted
as one: the group count on **By event** *is* the chase count, and Days To
Respond would measure from the wrong date. A curator records **What came
back**, **Response Date** and the summary on the row that did the asking, from
the **Awaiting a response** view. The same applies to an event that is later
resolved. **Resolved Date** and **Outcome for us** are a curator's to fill
in once you have saved it.

## The views you will actually use

**Outstanding and ageing** is what the list opens on. It is the chase
worklist, so it shows only what there is still something to do about: events
with no resolved date, oldest first, with overdue response dates in red. A
single occurrence is not on it (there is nothing to chase), and neither is
anything closed or rejected. **When it is empty, that is good news, not a
broken view.**

**By event** on the follow-up list groups every chase under its request. The
number beside each group *is* the chase count: nobody maintains it, so it
cannot be wrong.

**By failure mode** groups the events by what went wrong and totals the hours
lost under each. This is the view you take to a service review.

## Why Days Outstanding is blank

You will notice **Days Outstanding** is empty on anything still open, and only
fills in once you record a Resolved Date. That is deliberate, not a fault.

SharePoint cannot calculate a column against today's date. A stored value
would freeze on the day the row was last saved and then quietly lie. So the
live ageing lives where it can be trusted: the **Outstanding and ageing**
view, which re-evaluates every time you open it, and the red on **Response
Due Date**, which is worked out fresh each time the page draws.

A blank you can explain beats a number you cannot.

## Two things to keep out of it

**Names of individuals.** Record the role, the team or the forum: *service
desk*, *relationship manager*, *the monthly service review*. This register is
about an arrangement's performance, not any person's. Naming individuals turns
a usable document into one nobody can circulate.

**What you think of them.** The account is for what happened. Judgement
belongs in the reviewer's assessment, and characterisation belongs in Failure
Mode and Severity, where it is marked as somebody's view. Keeping them apart
is what stops this reading as a complaint file, and it is what makes it
usable when it matters.

Write every row as though the provider will one day read it. They might.

## Log the ordinary weeks too

If the register only ever contains disasters, the first question at a review
will be *how many requests went fine?*: not being able to answer costs
you more than the bad rows gained. Log every event of a kind you have decided
to track, not just the memorable ones. Your register owner can tell you which
kinds those are.
