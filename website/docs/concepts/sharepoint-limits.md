---
title: SharePoint limits you must know
sidebar_position: 5
---

# SharePoint limits you must know

A DBML schema that is perfectly ordinary as a relational design can silently
cross one of SharePoint Online's platform ceilings at runtime, after a clean
`dbml-sharepoint build` and a green `deploy.js.txt` run. Every DBML `Ref`
becomes a Lookup column, every `person` column is a lookup **type** for the
purposes below, and both cost the same platform budget a hand-authored
SharePoint list would.

This page collects the ceilings that matter for schema design, states where
each is documented, and (because a page that claims a check exists when it
does not is worse than no page) says plainly whether this build's validator
catches it, warns about it, or is silent. The audit below reads the
validator source directly (`analysis/checks/_structure.py`,
`analysis/checks/_views.py`, `analysis/joins.py`); it is not a guess at what
"probably" fires.

Read this before you design a schema, not after a deploy surprises you.
Read [DBML reference](../reference/dbml.md) and
[mapping reference](../reference/mapping.md) for the full, live-verified
detail behind each ceiling. This page is the map, they are the
territory.

## The list view threshold: 5,000 items

**The limit.** A list view query that touches more than 5,000 items is
throttled. Microsoft states the limit [cannot be raised](https://support.microsoft.com/en-us/office/manage-large-lists-and-libraries-b8588dae-9387-48c2-9248-c24122f07c59)
and that, past it, a query may not error at all. It can silently return a
truncated answer (up to the newest 1,250 items) instead of the rows a filter
actually matches.

**How it maps here.** Every declared `views[].where` clause and the
generated `All Items` view are queries against the list. A filter with no
selective index behind it is exactly the shape that gets truncated rather
than refused. [Indexing a Lookup or Person column does not avert
it](https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0)
Microsoft's own indexing guidance says so, and treats Person/Group
(single value) and Managed Metadata as lookup types for this purpose
too.

**What the build does.** **Warns, never errors**: `unindexed_filter_columns`
when a `where` clause filters only on columns no effective index covers. The
build cannot know how large a list will grow, so it reports the exposure
rather than refusing the build over it.

**Mitigation.** Add a bare DBML `indexes` entry on a selective *scalar*
filter column (Text, Number, Choice or Date, not Lookup or Person). See the
full mechanics, including the multi-value case that has no index remedy at
all, in [mapping reference: views](../reference/mapping.md#views).

## The lookup-and-person-column ceiling: 12 per view, not 8

**The limit.** A single view query can perform at most **12** join
operations: one per rendered Lookup or Person column (Managed Metadata,
too). Microsoft's [Power Query SharePoint Online list connector
documentation](https://learn.microsoft.com/power-query/connectors/sharepoint-online-list#troubleshooting)
states this explicitly for SharePoint Online: *"a maximum of 12 join
operations per query… This issue manifests as SharePoint queries failing when
more than 12 columns are accessed simultaneously,"* citing the same figure
Microsoft's [SharePoint Server 2016/2019 boundaries
page](https://learn.microsoft.com/sharepoint/install/software-boundaries-limits-2019#list-and-library-limits)
documents as the **List view lookup threshold**.

An older figure of **8** circulates from a farm property
(`MaxQueryLookupFields`) that does not exist in SharePoint Online at all.
That is an on-premises upgrade story, not a SharePoint Online one, and it is
not what either citation above states. This repository also measured the
ceiling directly against a live tenant, at 6,000 items with the filter held
constant so the join count was the only variable: **12 rendered, 13
refused**, `SPQueryThrottledException` code `-2147024749` (2026-07-31,
`test/manual/threshold-index-probe.js`). The 12-join figure is corroborated
independently by measurement, not assumed from the citation alone.

**How it maps here.** Every DBML `Ref` (a real Lookup) and every `person`
column costs one join, whether or not it holds data. `Author` (Created By)
and `Editor` (Modified By) cost one each too. The generated `All Items` view
appends both unconditionally, so **every `All Items` starts at 2**: an
entity's real budget for its own lookup and person columns is **10**, not
12.

**What the build does.** **Silent at 10 or fewer, warns at 11 and 12
(`join_threshold_approached`), errors at 13+
(`join_threshold_exceeded`).** The warning band exists because 12 held on the
tenant this repository measured, but the SharePoint Online citation, while
explicit, is not exhaustive platform documentation. A view in the 11 to 12
band may not travel to every tenant. The band once started at 9, because 8
was a real limit on some on-premises farms; that property does not exist in
SharePoint Online, so the band was narrowed in September 2026.

**Mitigation.** Fewer rendered lookup/person columns per view; on the
generated `All Items` view specifically, `hide_from_all_items` can drop
`Author`, `Editor` and other join-bearing columns that cost joins without
declaring you a view. See [mapping reference: a view can only perform 12
joins](../reference/mapping.md#views) for the full budget arithmetic and the
`hide_from_all_items` syntax.

## The indexed-columns-per-list cap: 20

**The limit.** A list can carry at most **20** indexed columns. Microsoft
states it directly: *"You can add indexes on up to 20 columns on a list or
library… While you can add up to 20 indexes per list or library, it's
recommended you add indexes to only… the most commonly used columns."*
([Add an index to a list or library
column](https://support.microsoft.com/en-us/office/add-an-index-to-a-sharepoint-column-f3f00554-b7dc-44d1-a2ed-d477eac463b0)).
The same page's supported/unsupported table confirms which SharePoint column
types can carry an index at all: Text, Number, Currency, Date/Time, Choice
(single), Yes/No, Lookup and Person/Group (single) can; Multiple lines of
text, Choice (multi-valued), Calculated, Hyperlink/Picture and Person/Group
(multi-valued) cannot.

**How it maps here.** The DBML `indexes {}` block spends this budget one
entry at a time. Two more are spent without a corresponding `indexes {}`
entry: a `[unique]` column carries one implicitly, and a list a real Lookup
points at carries one on its `display_column` automatically (so its lookup
picker keeps working past 5,000 items). SharePoint also creates indexes of
its own when a view is sorted on an unindexed column. Those are invisible
to this build.

**What the build does.** **Warns at 18–19 of 20 (`index_limit_approaching`),
errors above 20 (`index_limit_exceeded`).** The message names the implicit
contributors, the ones an author cannot see just by counting `indexes {}`
entries.

**Mitigation.** Spend the budget on the columns actually used to filter
large lists; drop indexes that only sped up a Metadata Navigation view
you no longer use. See
[DBML reference: indexes](../reference/dbml.md#indexes) for the full
declaration rules, including which DBML types can carry `[unique]`.

## The calculated-column operand rules

**The limit.** A calculated formula can reference only its own row's
columns, and not every column type is a legal operand. Microsoft's own
[formula reference](https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/examples-of-common-formulas-in-lists)
states plainly: *"Calculated fields can only operate on their own row, so
you can't reference a value in another row, or columns contained in another
list or library. Lookup fields are not supported in a formula."* This is
why a DBML `Ref` can never be a calculated-formula operand.

This repository's own live probe extends that matrix to every operand type
this tool can emit (`test/manual/calculated-operand-probe.js`, run against
SharePoint Online 2026-07-30): Person, Multiple lines of text, Rich text,
Hyperlink and Choice (multi-valued) are **all** refused the same way Lookup
is: HTTP 500, *"One or more column references are not allowed, because the
columns are defined as a data type that is not supported in formulas."* This
is a finding this repository verified rather than assumed, in keeping with [this
project's rule against asserting SharePoint behaviour from
plausibility](https://github.com/firmfooting/dbml-sharepoint/blob/main/AGENTS.md#the-one-rule-that-matters-most).

`[Today]`, `[Me]` and any other bracketed token that is not a declared
column name fail for a related but distinct reason: they are not row
columns at all, and the same Microsoft formula reference's "own row" rule
above is why a calculated formula has no way to name them.

**How it maps here.** Every `calculated_text`, `calculated_number` and
`calculated_date` column's formula, declared in `mapping.yaml`'s
`calculated_formulas`, is checked against this matrix.

**What the build does.** **Errors, always**: before any script is
emitted. `calculated_formula_unsupported_operand` and
`multi_value_operand_unsupported` name the forbidden operand and column;
`calculated_formula_unknown_column` catches `[Today]`, `[Me]` and any typo,
because none of them names a declared column of the entity. The build
refuses the formula at build time rather than letting SharePoint refuse the
field creation at HTTP 500, part-way through a deploy that has already
written earlier phases.

**Mitigation.** Compute from a supported operand type (text, number, date,
choice, boolean or another calculated column) instead. See [DBML reference:
calculated-formula operand types](../reference/dbml.md#constraints-sharepoint-imposes)
for the full, live-verified operand table.

## What this page leaves out, and why

**No cross-site lookups.** DBML `Ref` columns become same-site SharePoint
Lookup columns; a relationship into a list on a different site needs the
mapping's `cross_site_reference_columns` pattern (a Choice + URL pair)
instead of a real Lookup.
[DBML reference](../reference/dbml.md#references-lookups) and
[mapping reference](../reference/mapping.md) already state this. It is
not repeated here
with a fresh citation: a focused search for a current Microsoft Learn or
Support page that states the same-site restriction as its own subject,
rather than as a side effect of a template- or workflow-scoped article,
did not turn one up. Rather than publish it with a citation that does not
really support it, it stays where it already lives, and
[issue #184](https://github.com/firmfooting/dbml-sharepoint/issues/184)
tracks sourcing it properly, by a probe if Microsoft documentation never
states it directly.

**The two-level `group_by` ceiling.** Documented in
[mapping reference](../reference/mapping.md#views); not repeated here
because it was not part of the set of ceilings this page was written to
cover.

Any other limit not listed above is, as far as this page is concerned,
either not yet known to bite a DBML-shaped schema, or not yet sourced to
Microsoft documentation strongly enough to publish. If you hit one, please
open an issue, ideally with a `test/manual/` transcript.
