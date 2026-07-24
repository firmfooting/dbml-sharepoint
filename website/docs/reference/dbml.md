---
title: DBML schema
sidebar_position: 2
---

# DBML reference

The schema is standard [DBML](https://dbml.dbdiagram.io/docs/) — the
same file renders as an ERD on dbdiagram.io. The deployer consumes the
subset below; the validator rejects anything outside it with a named
finding rather than guessing.

## Column types

| DBML type | SharePoint field | Notes |
|---|---|---|
| `int` (as `pk, increment`) | built-in ID | The conventional surrogate key; not created as a column |
| `int`, `number` | Number | |
| `nvarchar` | Single line of text | |
| `longtext` | Multiple lines, plain text | |
| `richtext` | Multiple lines, rich text | |
| an enum name | Choice | Enum values become the choice set; `default:` supported |
| `date` | Date only | |
| `datetime` | Date and time | |
| `boolean` | Yes/No | |
| `person` | Person | |
| `hyperlink` | Hyperlink | |
| `calculated_text` / `calculated_number` / `calculated_date` | Calculated | Formula comes from the mapping's `calculated_formulas` |

The legacy bare `choice` type is rejected — declare an enum so the
choice set is part of the reviewed schema.

## Enums

```dbml
enum risk_rating {
  Low
  Medium
  High
  Extreme
}

Table Risk {
  RiskRating risk_rating [note: 'Assessed rating']
}
```

Enum-typed columns become Choice columns with exactly the declared
values. Enum value sets can also be loaded from YAML via the mapping's
`enum_sources` when several schemas share a vocabulary.

## References (lookups)

```dbml
Ref: Action.RiskId > Risk.Id
```

Refs become same-site Lookup columns. Self-references and reference
cycles are handled by deferring those columns to a dedicated phase after
all lists exist. SharePoint cannot span webs with a lookup; cross-site
relationships use the mapping's `cross_site_reference_columns` pattern
(a Choice + URL pair) instead.

## Column settings

- `not null` → required column.
- `unique` → enforce unique values (SharePoint indexes it as a side
  effect).
- `default: 'value'` → field default (Choice defaults validated against
  the enum).
- `note: '...'` → the column description operators see; also feeds the
  data dictionary.

## Constraints SharePoint imposes

Surfaced at build time by the validator, not discovered at deploy time:

- Calculated columns cannot reference Lookup or Person columns, or
  `[Today]`.
- Lookups are same-site only.
- A schema *upgrade* whose immutable shapes changed (types, lookup
  targets, list templates) fails closed for explicit migration.
