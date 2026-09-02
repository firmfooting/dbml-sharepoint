---
title: save_rules
sidebar_position: 24
---

# `dbml_sharepoint.analysis.save_rules`

*which date rules move from a column to the list rule*

Where a save rule that compares a date with the clock is enforced.

MEASURED 2026-09-02 on a live tenant in "(UTC+10:00) Canberra, Melbourne,
Sydney", at 10:57 local, with the server clock correct:

- A date-only column with default formula `=TODAY()` filled 1 September
  while the site's date was the 2nd; `=[D]<=TODAY()` refused the 2nd as
  "in the future". `=[W]<=NOW()` accepted an instant 20 hours before now
  and refused one 12 hours before. The formula clock sits 16 to 20 hours
  behind the site: a western wall clock read as site-local time, and no
  site setting moves it.
- In a LIST validation formula, `[D]<=[Modified]` accepted today's
  site-local midnight and refused tomorrow's and a 30-day control; an
  update to five seconds before the save was accepted while an hour after
  was refused. SharePoint stamps Created and Modified for the save in
  progress before it evaluates the list formula, so `[Modified]` is the
  save's own instant, in site-local time, on create and on update.
- A COLUMN validation formula may reference only its own column:
  "The formula cannot refer to another column."
- Through the modern form at 11:49 local, with the site zone unchanged for
  over an hour: a date-only column under `=[DT]<=TODAY()` still refused
  today, so the lag is not a setting propagating; under the list rule
  `=OR(ISBLANK([DM]),[DM]<=[Modified])` the form saved today and refused
  tomorrow with the rule's own message. The form path behaves as REST did.

So a column rule that compares a date with `today` or `now` cannot be
exact where it was declared, and is hoisted onto the list rule here. The
renderer then compares against `[Modified]`. Shared by the deployer, the
manifest and the validator, so the three cannot disagree about which
rules moved.

### `compares_with_the_clock`

```python
def compares_with_the_clock(condition: Condition, column_types: dict[str, str]) -> bool
```

Whether any leaf compares a date or datetime column with `today` or
`now`. The literal word on a text column is a word.

### `hoisted_columns`

```python
def hoisted_columns(section: dbml_sharepoint.model.mapping_types.EntitySection[dbml_sharepoint.model.mapping_types.ColumnValidation] | None, column_types: dict[str, str]) -> list[tuple[str, dbml_sharepoint.model.mapping_types.ColumnValidation]]
```

The column rules that move to the list, in declaration order.

### `effective_list_validation`

```python
def effective_list_validation(mapping: dbml_sharepoint.model.mapping_types.Mapping, entity: str, column_types: dict[str, str]) -> dbml_sharepoint.model.mapping_types.ListValidation | None
```

The list rule the deployer writes: the declared one, with every
hoisted column rule joined by AND and each hoisted rule guarded so a
blank never fails it, as a column rule never fires on a blank. Messages
are joined in the same order, the declared list rule's first.

