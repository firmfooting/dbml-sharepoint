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

The form asks in four sections, in this order.

1. **MR_Measure** → **New** (custodians create; owners draft with them).
2. **Name the measure** — name it as it will appear on the report,
   including the unit: "Complaints acknowledged within 2 days (%)". Pick
   the **Measure Area** from the ones already in use ("The catalogue"
   groups on it, so a new spelling makes a new group), and name the
   **Owner** who is accountable for the number being right.
3. **Define it** — Definition per the test above; **Data Source** names the
   actual system/list; **Direction** says which way is good; **Target**
   only if someone with authority set one. A monitored measure without a
   target is honest; an invented target is theatre.
4. **Report it** — **Frequency**, and **Reported To** naming the forum(s).
   A measure nobody receives is Under development or nothing.
5. **Govern it** — **Status**, **Review Date**, and **Notes** for the dated
   definition-change history.

Two things the form will refuse to save, so you find out now rather than at
the next committee:

- An **Active** measure with no **Review Date**. Without one it never
  reaches "Definition reviews due" and its definition is never re-tested.
- A **Review Date** more than twelve months away. The cadence is at least
  annual; a date further out is a measure leaving the cull rather than a
  slower cadence. Leave it blank while the measure is Under development.

## The five views, and what each is for

Deployed with the list — there is nothing to build by hand.

| View | Use it when |
| --- | --- |
| **The catalogue** *(default)* | Browsing what is actually in force, grouped by area |
| **By forum** | Before an agenda goes out: what does this committee receive? |
| **Definition reviews due** | Working the review cadence — anything due within 60 days, oldest first, overdue dates in red |
| **In development** | The drafting queue: measures being defined, with their draft definition and data source |
| **Retired** | Decoding an old report: the definitions behind numbers nobody produces any more |

## When someone proposes a new report or dashboard

First question, always: *are its measures registered?* If not, register
them first — the definition conversation is cheaper before the chart
exists than after two committees have seen different versions of it.

## Changing a definition

Never silently. Definition changes go through the custodians (see
governance): the change is dated in Notes, and every downstream consumer
in ReportedTo is told the series has a break in it. A trend across an
unannounced definition change is fiction with an x-axis.
