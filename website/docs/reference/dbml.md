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

## Indexes

Declare ordinary SharePoint column indexes in the table's DBML `indexes`
block. Each entry is one column name:

```dbml
Table Risk {
  Id          int         [pk, increment]
  Status      risk_status
  Category    risk_category
  ReviewDate  date

  indexes {
    Status
    Category
    ReviewDate
  }
}
```

The block is the sole source of truth for ordinary indexes. A build turns
each entry into `Indexed: true`, verifies the property by readback, and lists
the result in the deployment manifest and data dictionary. Deployment is
declarative for additions and repairs: a missing declared index is created,
but removing an entry does not delete an existing SharePoint index.

The supported DBML subset is intentionally narrow:

- One bare column per entry. Composite indexes are rejected.
- Index options such as `name`, `type`, `unique`, `pk` and `note` are
  rejected because SharePoint has no equivalent deployment contract.
- Put `unique` on the column itself, for example
  `Code nvarchar [unique]`. SharePoint creates an index as part of enforcing
  uniqueness, so it counts toward the same per-list limit even when it is
  not repeated in `indexes`. Repeating it in `indexes` is rejected as a
  redundant declaration. Supported DBML types are `nvarchar`, `int`, `number`,
  `date`, `datetime`, named enums (single-value Choice), `person`, and
  single-value lookup columns. `boolean`, `longtext`, `richtext`, `hyperlink`,
  and calculated types reject `[unique]` because SharePoint cannot enforce it.
  This follows Microsoft's documented [unique-column type
  matrix](https://support.microsoft.com/en-US/SharePoint/lists/data-and-lists/create-list-relationships-by-using-lookup-columns).
- A list may have at most 20 effective declared/unique indexes. Declaring the
  same column twice is an error.
- Text, Number, Date/DateTime, Boolean, Choice, Lookup and Person columns can
  be declared. Multiple-lines-of-text, Hyperlink and Calculated columns
  cannot be indexed and fail validation.
  See Microsoft's [supported and unsupported index column
  types](https://support.microsoft.com/en-US/SharePoint/data-and-lists/add-an-index-to-a-list-or-library-column).
- Lookup and Person indexes do not make those fields suitable as the first
  filter in a large-list threshold query. Prefer a selective scalar field.
- A mapping `cross_site_reference_columns` entry replaces its logical DBML
  column with generated Abbreviation and SiteUrl fields. Neither the logical
  column nor its generated `Abbreviation`/`SiteUrl` fields can be indexed from
  DBML; pydbml accepts only declared columns as index subjects, while declaring
  either generated name would collide with the expansion.

`mapping.yaml` has no index API. The former `indexed_columns` section is a
load error rather than a compatibility alias.

## Column settings

- `not null` → required column.
- `unique` → enforce unique values and its implicit index on supported
  single-value field types; unsupported types fail validation.
- `default: 'value'` → field default (Choice defaults validated against
  the enum).
- `note: '...'` → the column description operators see; also feeds the
  data dictionary.

## Constraints SharePoint imposes

Surfaced at build time by the validator, not discovered at deploy time:

- Lookups are same-site only.
- A schema *upgrade* whose immutable shapes changed (types, lookup
  targets, list templates) fails closed for explicit migration.
- A calculated formula referencing a name that is not a column of the
  entity is refused, naming the reference.

:::warning Calculated formulas: check the operand types yourself

SharePoint does not allow a calculated column to reference a **Lookup** or
**Person** column, and the validator does **not** catch it. Verified:
`OwnerCopy: '=[Owner]'` over a `person` column builds with exit 0 and zero
findings. SharePoint rejects it at paste time with an HTTP 500, part-way
through provisioning.

The reference check is a name check, not a type check — it verifies the
name is a column of the entity and nothing more. `[Today]` happens to be
caught only because no column is called `Today`.

Until this is a build error, treat the operands of every
`calculated_formulas` entry as your responsibility: single-select Choice,
Text, Number, Boolean, Date and other **calculated** columns of the same
list. Calculated operands are supported — the build provisions a
calc-on-calc chain in dependency order and refuses a cycle — but Person
and Lookup are not, and nothing checks them for you.

:::
