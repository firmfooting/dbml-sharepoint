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

Two indexes are spent without appearing in `indexes { }`:

- a `[unique]` column carries one implicitly;
- **a list that anything looks up** carries one on its `display_column`, so its
  lookup pickers keep working past 5,000 items.

SharePoint also creates indexes on its own — opening a view sorted on an
unindexed column adds one, marked *"(Automatically created)"* on the Indexed
Columns page — and those are invisible to this build. The validator warns once a
list reaches 18 of its 20 for that reason.

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

:::warning Calculated-formula operand types

The build refuses a calculated formula whose operand SharePoint will not
accept. The error names the calculated column and the operand before any
script is emitted; SharePoint otherwise rejects the field creation with HTTP
500 part-way through provisioning.

The matrix is **live-verified**, not inferred. `calculated-operand-probe.js`
was run against SharePoint Online on 2026-07-30 and answered every question:

| Operand column type | Result |
|---|---|
| Single line of text (`nvarchar`) | accepted |
| Number (`number`, `int`) | accepted |
| Date, Date/Time (`date`, `datetime`) | accepted |
| Choice (a named enum) | accepted |
| Yes/No (`boolean`) | accepted |
| Another calculated column | accepted |
| Lookup (a `ref` column) | **refused** |
| Person (`person`) | **refused** |
| Plain multi-line text (`longtext`) | **refused** |
| Rich text (`richtext`) | **refused** |
| Hyperlink (`hyperlink`) | **refused** |

Every refusal returned the same body: *"One or more column references are not
allowed, because the columns are defined as a data type that is not supported
in formulas."* This agrees with Microsoft's formula reference, which lists the
supported operand types and states explicitly that [Lookup fields are not
supported in a
formula](https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/examples-of-common-formulas-in-lists).

Calc-on-calc chains are provisioned in dependency order and cycles are
refused.

Cross-site logical refs do not deploy as lookups. A generated
`<column>Abbreviation` companion is Text and can be used in a formula; the
logical ref name cannot, because no such field is created.

:::
