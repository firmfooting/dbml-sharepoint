# Service evidence register

A contemporaneous record of what an external service provider is actually
delivering — the events, the chases it took to get an answer, and the themes
worth raising formally.

The failure this closes is specific and common. An organisation knows a
provider is underperforming, everyone can name three incidents, and when the
service review arrives nobody can produce anything better than recollection
and a feeling. The events happened; they were never written down in a form
that carries weight. By the review they are anecdotes, and anecdotes lose to
a provider's own dashboard.

**Deliberately domain-neutral.** The same register serves a technology
arrangement, a payroll bureau, a facilities contractor, a cleaning contract or
a finance shared service. Nothing in this template names a provider or a
sector, and the demo rows use `[DEMO] Example Service Partner` as a
placeholder.

## The idea, in one table

The register separates three things that most logs mash into a single text
box, and that separation *is* the rigour:

| | Columns | Why it is separate |
|---|---|---|
| **Fact** | What happened, Occurred At, Provider Reference | Written at the time, attributable, verifiable from the provider's own records |
| **Impact** | Severity, People Affected, Hours Lost | Estimated — and honestly labelled as estimated |
| **Characterisation** | Failure Mode, Reviewer's assessment, Materiality | Somebody's judgement, and marked as such |

A row where all three share one box is an anecdote. A row where they are
separate columns is a business record.

## Robust without being forensic

Three cheap things carry most of the weight, and they are the three fields on
the capture form that a hurried person might be tempted to skip:

- **How you know** — did you see it, or were you told? A second-hand account
  is still worth recording; it simply carries less weight, and now that is
  visible instead of assumed.
- **Provider reference** — their ticket or case number. The single most useful
  field in the template: it lets them verify the event from their own system,
  so it cannot simply be denied.
- **Evidence held** — what actually backs this up, down to and including
  *None, recollection only*, which the register is willing to say out loud.

On top of those, **contemporaneity is a rendered column rather than a claim.**
`Days To Log` and `Record Timeliness` put *Same day* or *Retrospective* on
every row in the family's severity colours. Nobody has to take the register's
word for how promptly it was kept.

What is deliberately absent: chain of custody, hashing, tamper-proofing,
witness attestation and a costing model. Those are the forensic end, they
would halve the number of events anyone bothered to log, and the argument
would shift from service quality to your arithmetic.

## Three lists

**`ServiceEvent`** — one row per occurrence, and the one people use daily.
A single occurrence is loggable in about a minute. The **Event Nature**
choice at the top of the form switches between two temporal shapes: a
*Single occurrence* is closed-book and never shows the chase fields, while an
*Unactioned request or ticket* opens a clock whose evidence is the ageing
itself.

**`FollowUp`** — one row per chase, against the event being chased. What you
asked, how, how far up the escalation ladder you went, and what came back.
Four dated rows against one request say more at a review than any adjective.

**`ServiceIssue`** — the theme you raise formally, with the response clock and
the remedy trail. Curator-visible only: what you intend to raise, at what
level and when is not something everyone who can log an event should read.

## What to change before first deploy

- **`Provider`** is free text so the register works for one provider or
  several. Write the name identically on every record — the grouped views
  depend on it. If you have exactly one arrangement, consider making it a
  Choice with a single member.
- **`service_domain`** — replace the eleven generic members in
  `10-design/schema.dbml` with your own service breakdown.
- **`failure_mode`** — the fourteen members are drawn from what goes wrong in
  outsourced arrangements generally. Cut the ones that cannot happen to you;
  keep *Closed without resolving* and *Repeatedly reassigned or handed off*
  if you have a ticketing relationship at all.
- **Prefix** — `SE_`, in `20-configure/mapping.yaml`.

Choices are cheap to edit now and expensive to rename later: a rename strands
every row already sitting on the old value.

## Deploying

```bash
dbml-sharepoint build \
  --schema templates/service-evidence-register/10-design/schema.dbml \
  --mapping templates/service-evidence-register/20-configure/mapping.yaml \
  --release templates/service-evidence-register/20-configure/release.yaml \
  --site-url https://yourtenant.sharepoint.com/sites/your-site \
  --site-role default \
  --out ./build
```

Then follow [`30-deploy/DEPLOY.md`](30-deploy/DEPLOY.md). The shared
procedure is in [`templates/README.md`](../README.md).

## Before you deploy it, read the governance file

[`50-govern/GOVERNANCE.md`](50-govern/GOVERNANCE.md) is not optional reading
for this template. A register that characterises another organisation's
performance fails on governance long before it fails on schema, and the four
things that sink one are all avoidable: selection bias, naming individuals,
forgetting the register is discoverable, and treating it as a substitute for
raising things at the time.
