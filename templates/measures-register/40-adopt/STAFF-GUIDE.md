# Measures register — writing definitions that survive contact with data

*For measure owners and custodians. Everyone else: this is where you check
what a number on a dashboard actually means.*

## The test a definition must pass

Two strangers, given your definition and access to the data source, compute
the **same number**. That's it. Every element below exists because its
absence has made two reasonable people compute different numbers:

- **Numerator** — what's being counted, exactly. "Complaints acknowledged
  within 2 business days of ReceivedDate."
- **Denominator** — counted out of what. "All complaints received in the
  month, excluding Withdrawn."
- **Exclusions** — named, with reasons. Every silent exclusion is a future
  argument.
- **Date anchor** — which date field, and calendar or business days.
  Half of all measure disputes are date-anchor disputes.
- **Unit and rounding** — %, days, count; to how many places.

## Registering a measure

1. **MR_Measure** → **New** (custodians create; owners draft with them).
2. Name it as it will appear on the report — including the unit:
   "Complaints acknowledged within 2 days (%)".
3. Definition per the test above; **DataSource** names the actual
   system/list; **ReportedTo** names the forum(s) — a measure nobody
   receives is Under development or nothing.
4. **Target** only if someone with authority set one. A monitored measure
   without a target is honest; an invented target is theatre.

## When someone proposes a new report or dashboard

First question, always: *are its measures registered?* If not, register
them first — the definition conversation is cheaper before the chart
exists than after two committees have seen different versions of it.

## Changing a definition

Never silently. Definition changes go through the custodians (see
governance): the change is dated in Notes, and every downstream consumer
in ReportedTo is told the series has a break in it. A trend across an
unannounced definition change is fiction with an x-axis.
