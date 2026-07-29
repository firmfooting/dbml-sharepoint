# Governing the service evidence register

Read this before you deploy the template, not after.

A register that characterises another organisation's performance fails on
governance long before it fails on schema. The five sections below are the
ways it fails, in rough order of how often they happen, and what to do about
each. Everything after them is the ordinary ownership and cadence material.

---

## 1. Selection bias is the strongest attack on this register

**The objection, in the room:** *"You only wrote down the bad days."*

It is a good objection, and if it lands the register is worthless — worse than
worthless, because you will have spent political capital producing something
that made you look partisan rather than organised. It is also the objection
you can prepare for completely, and almost nobody does.

**What makes it land.** A register that fills up only after somebody gets
annoyed. Forty rows across eighteen months with a suspicious cluster in the
six weeks before a contract review. Events logged for one team and not others.
No denominator anywhere.

**Three things that answer it:**

- **Decide what you log, in advance, by category — not by how annoyed you
  were.** Write it down: *"we log every access request that misses its
  target, every unnotified outage, and every request closed without contact."*
  Then log all of them, including the ones that were resolved politely the
  same afternoon. The ordinary rows are not filler; they are what proves the
  bad rows were not cherry-picked.
- **Record the denominator.** *"Fourteen failures"* invites the answer *"out
  of how many?"* — and if the honest answer is fourteen out of two thousand,
  you should know that before the meeting rather than during it. Capture the
  period's total request volume from the provider's own reporting and put it
  beside your figures. If their volume reporting is itself unreliable, that is
  a service issue in its own right, and it belongs in `ServiceIssue`.
- **Show the *Not substantiated* rows.** A register that has thrown some of
  its own material out is dramatically more credible than one that has not.
  This is what the status exists for.

**The framing to use:** this is a record of a service relationship, kept
routinely, not a case built against anyone. Registers that read as the former
get acted on. Registers that read as the latter get argued with.

## 2. Record conduct and events, never character

Name the **role**, the **team** or the **forum**, never the individual —
in `Raised With`, in `Contacted Role` and in every free-text box.

Two reasons, and the second is the one people forget:

- **Fairness and legal exposure.** Written statements characterising a named
  person's competence, circulated within your organisation and potentially to
  theirs, are the shape of a defamation problem. Nothing about "it was only an
  internal list" changes that.
- **It weakens the argument.** A pattern attributed to a person reads as a
  personality clash and invites the provider to replace one individual and
  declare the matter closed. The same pattern attributed to a process is a
  service failure they have to actually fix.

Curators should treat an individual's name appearing in a row as a data-quality
defect and edit it out, the same way they would a typo.

## 3. Assume it will be read by people you did not write it for

This register is **discoverable**. Depending on your jurisdiction and sector
that may mean freedom-of-information or equivalent access legislation, legal
discovery, a subpoena, an audit, or simply somebody forwarding a view. And
quite apart from any formal process: if the themes are ever raised properly,
the provider will see the substance of what you wrote about them.

None of that is a reason not to keep the register. It is a reason to keep it
well. **Write every row as though the provider will read it, because one day
they may.** In practice that means: no speculation about motive, no
characterisation of people, no venting, and nothing in a row you would not be
willing to say across a table.

A register kept to that standard is more useful, not less. The restraint is
what makes it quotable.

## 4. It is not a substitute for raising things at the time

A register full of complaints nobody ever made is a *weaker* document than a
short one where each entry was raised when it happened. *"You never told us"*
is a complete answer to an unraised event, and it is available to the provider
for free.

This is what `Raised With Provider` and the whole `FollowUp` list exist to
evidence. Use them:

- Raise it at the time, through the normal channel, and record that you did.
- Log the follow-up every time you chase.
- Escalate deliberately, one rung at a time, and record each rung.

An event marked *Deliberately not raised* is legitimate — sometimes it is not
worth the friction — but a register where most rows carry it is telling you
something about your own practice, not the provider's.

## 5. The one hand-maintained link

`ServiceEvent.LastFollowedUp` is **not** derived from the `FollowUp` rows.
SharePoint cannot roll a child value up to a parent, and nothing in the
deployer invents one, so this is a value a person keeps up to date.

It is kept because the chase worklist has to sort on *when did we last chase
this* — that is the question that decides what to do today, and a derived-only
answer that lived on another list would not be sortable here.

**The drift is bounded and visible.** The `FollowUp` **By event** view shows
the true most recent follow-up beside the group count. Reconciling the two is
a standing item in the review cadence below.

`TimesFollowedUp` was considered as a companion column and **cut** for the
same reason without the compensating benefit: a count that can only drift,
where the grouped view gives an accurate one for free.

---

## Ownership

| Role | Who | Responsibility |
|---|---|---|
| Register owner | One named person | Owns the categories logged, the denominator, and what is raised. Answers for the register's fairness. |
| Curators | 2–4 people | Review the queue, accept or reject events, assemble and own themes. The only people who can see `ServiceIssue`. |
| Contributors | Named staff | Log events and follow-ups. Cannot edit after saving, which is what makes the record worth having. |
| List administrators | Empty by default | Schema changes and redeploys, per run. |

Contributors deliberately cannot see `ServiceIssue`. Escalation strategy —
what you intend to raise, at what level, and when — is not something everyone
who can log an event should be reading, and a leaked one is worse than no
register at all.

## Cadence

| When | What |
|---|---|
| Weekly | Curator works **Needs review**: accept, reject as *Not substantiated*, or send back for detail. A queue worked weekly stays honest; one worked before a review does not. |
| Weekly | Curator works **Outstanding and ageing**. Anything past its Response Due Date gets chased and a `FollowUp` row. |
| Monthly | Reconcile `Last Followed Up` against the **By event** view. Update `Event Count` on any theme being assembled. |
| Monthly | Review whether the categories being logged still match what was agreed, and whether any team has stopped logging. |
| Per service review | Assemble the pack from **Evidence pack** and **By failure mode**. Bring the denominator. |
| Annually | Re-read this file with the register owner. Re-agree the escalation threshold. |

## The escalation threshold

An event is a candidate for promotion into a `ServiceIssue` when it is **past
its Response Due Date, has been chased twice or more, and is still
unresolved**.

That is the shipped default, not a rule handed down. Two chases is where a
delay stops being a delay and becomes a pattern of not responding; earlier
than that you are escalating normal friction and will spend credibility you
need later. **Set your own number, write it down, and tell the curators.** A
threshold nobody agreed is a threshold that moves to suit whoever is annoyed
this week — which is section 1's problem arriving by a different door.

Promotion is a curator judgement, not an automatic trigger. Several events
that individually clear the bar may be one theme; one that does not clear it
may still belong to a theme worth raising.

## Data quality

- **`Provider` spelling.** Free text, and every grouped and filtered view
  depends on it. Agree one spelling and check it monthly.
- **Facts and judgement stay separated.** *The account* is what happened; the
  *reviewer's assessment* is what we make of it. A curator finding opinion in
  the account should move it, not delete it.
- **Estimates stay estimates.** Hours Lost and People Affected are honest
  approximations and should be described that way in any pack. Precision you
  do not have is the fastest way to lose an argument you would otherwise win.
- **Individuals' names** are a defect. Edit them out.

## Retention and lifecycle

Rows in this register are organisational records about a commercial or service
relationship. They are likely to be relevant to contract management, audit and
any dispute, and they should be retained under your records schedule rather
than tidied up when a theme closes.

`rollback.js` is for empty or demonstration deployments only. Deleting a
populated register is a deliberate, authorised act: export it first, and treat
the deletion protection on the lists as friction rather than as authority.

## When to stop keeping it

Worth saying, because a register nobody ever intends to close becomes an
institution.

Close it when the arrangement ends, or when the service has been good enough
for long enough that the logging costs more than it tells you. If the second
happens, say so explicitly at a service review — *"we have kept this for four
quarters and there is nothing in it"* is a genuinely valuable finding, and it
is one you can only make because you were logging the ordinary weeks as well
as the bad ones.
