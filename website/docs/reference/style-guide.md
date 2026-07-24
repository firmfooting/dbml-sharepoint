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
|---|---|---|---|
| `good` | `sp-field-severity--good` | `CheckMark` | Complete / healthy / approved |
| `low` | `sp-field-severity--low` | `Forward` | Open / in motion / in progress |
| `warning` | `sp-field-severity--warning` | `Error` | Needs attention |
| `severe` | `sp-field-severity--severeWarning` | `Warning` | Serious / late / degraded |
| `blocked` | `sp-field-severity--blocked` | `ErrorBadge` | Blocked / failed / extreme |
| `neutral` | `ms-bgColor-neutralLighter` | — | Draft / provisional / pending |
| `muted` | `ms-bgColor-neutralLight` | — | Cancelled / superseded / inactive |

`muted` is also the automatic fallback for unmapped values.

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

## Authoring rules

1. Styles first. Bespoke formatter JSON is allowed only for shapes the
   library does not cover.
2. Bespoke JSON must draw on the classes in the token table (or other
   documented `sp-*`/`ms-*`/Fluent classes) — never introduce a hex.
3. A tenant that insists on brand colours overrides tokens via the
   mapping's `style_theme:` key; the default IS the standard.
