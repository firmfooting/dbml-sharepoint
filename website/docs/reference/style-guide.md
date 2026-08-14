---
title: Style guide
sidebar_position: 5
---

# The dbml-sharepoint style standard

One palette, one iconography, one set of shapes — defined here, inherited
by every mapping through the style library. Everything below uses
SharePoint's OWN documented formatting classes and Fluent icons, so
styled columns match the product UI, follow the tenant theme, and behave
in dark mode. No hexes.

Reference: [Use column formatting to customize SharePoint](https://learn.microsoft.com/en-us/sharepoint/dev/declarative-customization/column-formatting)
— the emitted structures mirror that document's severity, data-bar,
trending and date examples.

## Tokens

| Token | Classes | Default icon | Use for |
| --- | --- | --- | --- |
| `good` | `sp-field-severity--good` | `CheckMark` | Complete / healthy / approved |
| `low` | `sp-field-severity--low` | `Forward` | Open / in motion / in progress |
| `warning` | `sp-field-severity--warning` | `Error` | Needs attention |
| `severe` | `sp-field-severity--severeWarning` | `Warning` | Serious / late / degraded |
| `blocked` | `sp-field-severity--blocked` | `ErrorBadge` | Blocked / failed / extreme |
| `neutral` | `ms-bgColor-neutralLighter` | — | Draft / provisional / pending |
| `muted` | `ms-bgColor-neutralLight` | — | Cancelled / superseded / inactive |

`muted` is also the automatic fallback for unmapped values.

## Map by role, never by word

A status member takes its token from **the role it plays in its
lifecycle**, not from what it is called. This is the whole reason colour
means the same thing across a fleet of solutions: "Received", "Draft" and
"Submitted" are three vocabularies for one role, and somebody meeting the
second register of their week should not have to relearn what grey means.

| Role in the lifecycle | Token | Members that play it |
| --- | --- | --- |
| Intake, not yet triaged | `neutral` | Provisional, Draft, Received, Submitted, Reported, Applying, Idea |
| In motion | `low` | Open, In progress, Assigned, In service, Under review, Testing, Current |
| Needs attention | `warning` | Waiting, Partially compliant, On hold, Pending decision, Out of range |
| Late or degraded | `severe` | Overdue, Non-compliant, Out of service, Expiring, Breached |
| Blocked or failed | `blocked` | Failed, Withdrawn, Escalated, Uncontrolled, Extreme |
| Complete and healthy | `good` | Closed, Completed, Compliant, Adopted, Published, Approved, Returned |
| Cancelled or superseded | `muted` | Cancelled, Superseded, Declined, Abandoned, Retired, Disposed, Expired |

The members are illustrative, not a closed list — the column is what
matters. Ask which of the seven roles a value occupies in *that* list's
lifecycle and take the token from the answer. A member the map does not
name falls back to `muted`, so the cost of forgetting one is neutral grey
rather than a false severity, and a map key that is not a member of the
column's enum at all — the stale key a rename leaves behind — is a build
error.

Two bindings follow from the roles rather than from per-column taste:

- **Every deadline date gets `overdue-date`, with a `guard` naming that
  list's terminal statuses.** A due date that keeps shouting after the
  item is closed trains people to ignore the colour, which costs more
  than the colour ever earned.
- **Every score, count or ratio gets `data-bar` with an explicit `max`**,
  and where a rating column sits beside it, `color_by` takes the fill
  from that column's map so the bar and the cell cannot disagree.

## Styles

Declared per column under `column_formatting` in the mapping:

```yaml
column_formatting:
  Risk:
    Status: { style: severity, map: { Open: low, Closed: good } }
    Rating: { style: severity, calculated: true,
              map: { Low: good, Medium: warning, High: severe, Extreme: blocked } }
    Score:  { style: data-bar, max: 25 }
    ReviewDate: { style: overdue-date, guard: { field: Status, not: [Closed] } }
    Delta:  { style: trend, against: Baseline }
```

- **severity** — the standard look: SharePoint's full-height severity box
  with the token's icon and the value. `icons: false` disables icons;
  `calculated: true` is REQUIRED for calculated-text columns (SharePoint
  renders their values with a `string;#` prefix — the style switches to
  contains-matching and strips the prefix for display).

:::note The `string;#` prefix is a COLUMN-formatting thing only

Characterised on a live tenant, 2026-07-28, because getting this backwards
costs a silently-not-firing format either way:

| Where | Reference | A calculated-text value arrives as |
| --- | --- | --- |
| Column formatting | `@currentField` | `string;#Extreme` |
| View formatting (`views[].formatting`) | `[$Field]` | `Extreme` |

So `calculated: true` is required in `column_formatting` and an exact
comparison there silently never matches — but a **view** row formatter
compares directly, and `"=if([$Rating] == 'Extreme', …)"` is correct as
written. `solutions/risk-register` relies on this for its Extreme row
wash, confirmed rendering on a real list.

Do not add contains-matching to a view formatter "to be safe": it works,
so it survives, and it leaves the next reader believing the prefix reaches
somewhere it does not.

:::

- **pill** — compact native choice-pill look (opt-in alternative).
- **data-bar** — the documented `sp-field-dataBars` bar; `max` sets the
  full-width value. Optional `color_by: { field, map, calculated }` is
  the fleet's mapping-translation pattern: the bar keeps its width
  semantics but takes its fill from the severity token mapped from
  ANOTHER column's value (same `map` vocabulary as **severity**), so a
  score bar wears the standardised colours of the rating column beside
  it and the two can never disagree. `calculated: true` when the source
  column is calculated text (`string;#` contains-matching); unmapped
  values fall back to the neutral `muted` fill, never a false severity.
- **trend** — `sp-field-trending--up/--down` with SortUp/SortDown icons;
  `against` is a column internal name or a number.
- **overdue-date** — locale date, escalating to the `severe` treatment
  (box + Warning icon) once past due; `guard` suppresses the escalation
  when another column holds any excluded value (e.g. Status Closed).

## Iconography rules

- Lifecycle/status and severity/rating columns: token icons ON.
- Deadline dates: icon only in the overdue state.
- Numeric deltas: trend arrows.
- Neutral text, people, lookups, titles: NO icons.
- Icons come only from Fluent UI's documented set, only via `iconName`.

### Form-header icons come from one curated vocabulary

The icon at the top of a
[form header](./mapping.md#form_formatting) is not drawn from the token
table — it names the list rather than a value — so it is the one place an
author picks a Fluent name freely. That freedom is where the fleet's icons
would drift, and the failure mode is the worst kind: SharePoint renders an
unknown `iconName` as **nothing**. No build error, no deploy error, no
console message. The only witness is a person looking at the form.

So the vocabulary has one home — `FLEET_ICONS` in
`src/dbml_sharepoint/analysis/icons.py` — with every member checked once
against Microsoft's published MDL2 icon source, which is what `iconName`
resolves against. The template sweep asserts that every shipped form
header's icon is a member.

Names that read as obviously real and do not exist include `Calendar`,
`Key`, `Flow`, `Scales`, `AddFriend`, `Handshake` and `Signature` — the
last two being the first two anyone reaches for on a contract register.
Adding a name means verifying it in the catalogue first, then adding it to
that module: an offline test suite can assert membership, but it cannot
check a catalogue, which is exactly why the set is small, central and
reviewed.

## Authoring rules

1. Styles first. Bespoke formatter JSON is allowed only for shapes the
   library does not cover.
2. Bespoke JSON must draw on the classes in the token table (or other
   documented `sp-*`/`ms-*`/Fluent classes) — never introduce a hex.
3. A tenant that insists on brand colours overrides tokens via the
   mapping's `style_theme:` key; the default IS the standard.
