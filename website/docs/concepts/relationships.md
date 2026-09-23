---
title: Relationships and lookups
sidebar_position: 7
---

# Relationships and lookups

A DBML `Ref` is a pointer, and this tool deploys it as one. It is not a
foreign key: this tool writes no constraint, and no cardinality you declare
changes that. What SharePoint itself does underneath is a separate question,
and two halves of it are open. Whether a lookup id is checked against the
target list when a row is written, and what a child row reads once its parent
is deleted, are each marked not established below, with the experiment that
would settle them named.

That gap is the reason for this page. A data engineer reading

```dbml
Ref: Action.RiskId > Risk.Id
```

brings relational expectations to it: referential integrity, cascade or
restrict on delete, a junction list for a many-to-many. None of those are
what deploys.

Everything below is either sourced to Microsoft, sourced to a measurement
recorded in this repository, or marked as not established with the
experiment that would settle it named. Where a claim is a build rule, its
finding code is given so that `dbml-sharepoint explain <code>` reaches the
same statement.

## What a `Ref` becomes

One SharePoint Lookup column, on the list the **declaring** table maps to,
pointing at the list the target table maps to. It is single-valued unless
the declaring column's type carries `[]`, which is the only thing that
changes its arity and is covered under [arity](#multi-value-lookups) below.

One case deploys no Lookup at all. When the declaring column is named in the
mapping's
[`cross_site_reference_columns`](../reference/mapping.md#entities),
`build_schema_json()` takes it out of both lookup phases and hands it to the
active extension, which expands it into a Choice and URL pair on the source
list. That case is covered under [what is not
configurable](#what-is-not-configurable) below.

| Written | Deployed |
| --- | --- |
| `RiskId int [ref: > Risk.Id]` on `Action` | a Lookup named `RiskId` on the Action list, `LookupList` = the Risk list, `LookupField` = Risk's display column |

Nothing is created on the target side. The Risk list gets no column, no
back-reference and no constraint; the only thing a target list acquires is
an automatic index on its display column, because a Lookup's picker
enumerates the target and an unindexed enumeration stops working past the
list view threshold. See
[`display_column`](../reference/mapping.md#entities) for that index and what
it costs.

## Cardinality symbols are parsed and discarded

DBML spells four cardinalities. This tool records none of them: the parser
keeps the ref's target table and target column and nothing else, so all four
produce the same column.

| Declaration | What deploys | What does **not** happen |
| --- | --- | --- |
| `[ref: > Risk.Id]` (many-to-one) | one Lookup on the declaring list | |
| `[ref: < Risk.Id]` (one-to-many) | one Lookup on the **declaring** list | the column is not moved to the other list |
| `[ref: - Risk.Id]` (one-to-one) | one Lookup on the declaring list | no uniqueness is implied; declare `[unique]` if you want it |
| `[ref: <> Risk.Id]` (many-to-many) | one Lookup on the declaring list | no junction list is created, and the symbol does not make the lookup multi-value |

The standalone `Ref: Action.RiskId <> Risk.Id` block form behaves
identically to the inline one.

Two more things a ref does not carry:

- **A second ref on one column is dropped.** A column with refs at two
  tables deploys as a lookup into whichever was declared first, and nothing
  reports the one that was discarded. A column that genuinely points at more
  than one list is a logical foreign key rather than a Lookup; the mapping's
  [`polymorphic_patterns`](../reference/mapping.md#structure-and-behaviour)
  records the discriminator so the manifest can surface it, and SharePoint
  enforces nothing about it either.
- **The target column is recorded and read by nothing.**
  `Ref: Action.RiskId > Risk.Title` and `Ref: Action.RiskId > Risk.Id`
  deploy the same field. A lookup points at a **list**; what it displays
  comes from the target entity's `display_column`, not from the right-hand
  side of the ref.

**Nothing warns about any of this.** A `<>` that the author meant as a
many-to-many builds clean and deploys exactly what `>` would. Whether the
build should refuse or warn on `-` and `<>` is a validator question and is
not settled here.

Source: established in this repository by test, not read off the parser.
`test/test_lookups.py` feeds each symbol through `parse_dbml` in both
spellings, asserts the resulting `Reference` is identical and that no third
table appears, and separately pins the dropped second ref and the ignored
target column.

## Arity is declared with `[]`, not with a symbol {#multi-value-lookups}

A multi-value lookup **does** exist, and `<>` is not how you ask for one.
Add `[]` to the column type:

```dbml
WatchedRisks int[] [ref: > Risk.Id]
```

That deploys as SharePoint's **Lookup (multi-valued)**: `TypeAsString`
`LookupMulti`, `FieldTypeKind` 7, `AllowMultipleValues` true. It costs the
same one join as a single-value lookup, and it refuses `[unique]` and every
index. See [DBML reference: multi-value
columns](../reference/dbml.md#multi-value-columns) for the shared arity
mechanics.

Source, all measured 2026-09-02 against `test/manual/multilookup-probe.js`:
the create shape and read-back are `field.multilookup.create-readback-type`;
the index refusal (HTTP 500, *"This column type is not supported for
indexing"*, against a single-value control in the same list that took the
index and kept it) is `field.multilookup.indexed-property` and
`.control-single-value-indexed`. The join cost was measured 2026-09-04 as
`scale.join.multi-value-lookup-costs-a-join` and is pinned by
`test/test_joins.py`.

## What the deploy writes

**The create call.** A Lookup is the one field type SharePoint refuses
through a plain `POST` of `SP.FieldLookup` to a list's `/fields`
collection; the server answers *"Please use addfield to add a lookup
field"*. So a single-value lookup is created through
`fields/addfield` with an `SP.FieldCreationInformation` body carrying
exactly `FieldTypeKind` 7, `Title`, `Required` and `LookupFieldName`, plus
the `LookupListId` the browser resolves at run time. A multi-value one is
created through `fields/createfieldasxml`, because
`SP.FieldCreationInformation` has no `AllowMultipleValues` and the POST is
refused HTTP 400.

The refusal text above is an observed server message recorded in this
repository's deploy template rather than something Microsoft documents; the
multi-value half is the dated measurement cited in the previous section.

**`required`.** Rides the create body as `Required` on the single-value
`addfield` route, like any other column. The multi-value route cannot carry
it. The schema XML handed to `createfieldasxml` holds exactly the attributes
measured on 2026-09-02 and no others, so for an `int[]` lookup `Required`
arrives on the reconciliation `MERGE` the deployer issues straight after the
create, which is the same patch `[unique]` uses below. Neither route can carry
`Description`, which arrives the same way.

**`[unique]`.** Does **not** ride the create body. `SP.FieldCreationInformation`
carries neither `EnforceUniqueValues` nor `Indexed`, so a `[unique]` lookup
is the one field type where both arrive on the `MERGE` the deployer issues
straight after the create, in a single patch, and are then read back.

A multi-value lookup cannot be unique, and the build refuses it as
`multi_value_unique_unsupported`, an error, rather than letting the deploy
fail part-way through. That refusal is weaker-footed than it looks and the
validator says so in its own comment: only the **indexing** half was
measured on a multi-value lookup (2026-09-02, HTTP 500). The uniqueness half
rests on Microsoft's [list of the column types unique values cannot be
enforced for](https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/create-list-relationships-by-using-lookup-columns),
which names "Lookup (multi-valued)", plus the measured Choice
(multi-valued) precedent from 2026-08-10. It fails closed, which is why it
is enforced on that footing.

**What the lookup displays.** The target entity's `display_column`, falling
back to the built-in `Title`. Five build rules guard it:

| Situation | Code | Severity |
| --- | --- | --- |
| target has no `Title` column and declares no `display_column` | `lookup_would_render_blank` | error |
| `display_column` names a column the target does not have | `lookup_display_column_unknown` | error |
| `display_column` names a column the deploy never creates | `display_column_not_rendered` | error |
| `display_column` is a type SharePoint cannot index | `display_column_type_unindexable` | error |
| `display_column` is calculated, so it can carry no index | `calculated_display_column_unindexable` | warning |

The last two are about the automatic index on the target, not about what the
column shows; a calculated display column is still displayed, it just leaves
the picker unprotected past the list view threshold.

The first rule only catches a target with **no** `Title` column at all. A
target that has one and never writes to it is caught by nothing: the lookup
saves, reads back byte-identical and shows blank text for every row, because
what a lookup displays is the target row's value in the shown field.
Microsoft's [`Field`
element](https://learn.microsoft.com/sharepoint/dev/schema/field-element-field)
documents that default: `ShowField` "specifies the internal name of the
target field to look up. If no value is specified, the hyperlinked text from
the Title field of the record in the target list is displayed". The same
page lists `Counter`, `DateTime`, `Number` and `Text` as the field types
allowed as a lookup target, with `Computed` and text-output `Calculated` as
conditional cases. If the target's meaningful name lives somewhere other
than `Title`, declare `display_column`.

**Projected fields.** A lookup can carry additional fields across from its
target. Declare them in the mapping's
[`lookup_projections`](../reference/mapping.md#lookup_projections); each
becomes a read-only dependent Lookup named `<column><target>`, linked back
to the primary by `FieldRef`. Microsoft documents the concept as
[`FieldCollection.AddDependentLookup`](https://learn.microsoft.com/dotnet/api/microsoft.sharepoint.client.fieldcollection.adddependentlookup?view=sharepoint-csom)
and the linkage attribute on the [`Field`
element](https://learn.microsoft.com/sharepoint/dev/schema/field-element-field)
("For a secondary lookup field, specifies the ID of the primary lookup field
on which it depends"). A projection adds no join on top of its lookup,
measured twice as `scale.join.projected-field-costs-a-join` and pinned by
`test/test_joins.py::test_a_lookup_projection_costs_no_join`.

**When the column is created.** Most lookups are created with the rest of
their list's columns. Three kinds wait for the deferred-lookups phase, after
every list exists:

1. a self-reference;
2. the lookups on whichever side of a reference cycle is created first;
3. a lookup whose target declares a `display_column` other than `Title`.

Only one side of a cycle waits, so a cycle member is not by itself a
deferred lookup. `compute_phases()` defers the lookups on an edge that still
runs from an earlier-placed list to a later-placed one, which is what breaks
the cycle; the reverse edge points at a list that already exists by then and
is created in Phase 1 like any other lookup.
`test/test_ordering.py::test_circular_dependency_goes_to_phase2_for_one_side`
pins that one side is enough, and
`test_circular_with_multiple_lookups_defers_all_matching_columns` pins that
every column on the deferred side goes, not just the first.

The third is not obvious and was measured: the field wave runs one lane per
list in parallel, so a lookup whose `LookupField` is a custom or calculated
column can read a field the target's lane has not created yet. Observed
2026-08-27, a lookup displaying a calculated column failing with *"target
display field ... does not exist"*.

One consequence of deferral:

- A calculated formula cannot reference a deferred lookup, because the
  calculated field is created in the earlier phase. That is
  `calculated_formula_deferred_lookup`, an error.

Nothing else about the column changes. `form_visibility`,
`column_validation`, formatters and display names are computed for a
deferred lookup by the same calls that compute them for a Phase 1 column,
the deploy writes them, and `deploy-manifest.md` lists them. See [mapping
reference:
reconciliation](../reference/mapping.md#reconciliation-reconcile-on-form_visibility-and-column_validation).

## What is not configurable

SharePoint has knobs that would make a lookup behave like a foreign key.
This tool sets none of them, and there is no mapping key that would. A
lookup this deploy creates therefore carries the platform default.

| Knob | What SharePoint calls it | State here |
| --- | --- | --- |
| delete behaviour (cascade / restrict) | `RelationshipDeleteBehavior` | never written; `None` on a lookup this deploy creates; read and reported on an adopted lookup |
| relationship discovery flag | `IsRelationship` | never written |
| primary-key marker | `PrimaryKey` | never written |
| a target list in another web | `LookupWebId` | never written; refused at build time |

**What that rests on.** For the first three, the code:
`test/test_lookups.py` generates a deploy script covering all four routes
a lookup is created by (deferred self-reference, `[unique]` single-value,
multi-value, and a projection) and asserts that none of them, nor `Cascade`
or `Restrict`, appears in the SCHEMA payload every write body is built
from, or anywhere in the script outside the one function that reads an
adopted lookup's delete behaviour. That function is pinned to a GET with no
method or body. Microsoft's side is the [`Field`
element](https://learn.microsoft.com/sharepoint/dev/schema/field-element-field),
which documents `RelationshipDeleteBehavior` as "Optional Text. Specifies a
deletion constraint for a lookup field ... It can be **None** (the default),
or the attribute can be omitted", and adds that any other value requires
`Indexed` TRUE and `Mult` FALSE. So a multi-value lookup could not carry a
delete constraint even if this tool wrote one.

`IsRelationship` is worth naming precisely, because it reads like the
enforcement switch and is not. The same page defines it as "TRUE if this
field is returned by the `GetRelatedFields()` method from another list",
which is a discovery flag rather than a constraint.

**An existing lookup is adopted, not reset.** "Never written" is a claim
about the deploy, not about the column it leaves behind. When the declared
column is already on the list, `reconcileDeclaredField` adopts it and
patches only the mutable settings it owns: `Title`, `Description`,
`Required`, `EnforceUniqueValues`, `Indexed`, `DefaultValue`,
`DefaultFormula`, `CustomFormatter` and the declared derived properties
(`DERIVED_FIELD_PROPERTIES` in `analysis/typemap.py`). None of the knobs
above is in that set, so a delete behaviour somebody put on an adopted
lookup is not cleared. It is read and reported: preflight reads
`RelationshipDeleteBehavior` on its own GET for each existing declared
lookup, and one that is `Cascade`, `Restrict` or unreadable is logged as a
WARN and recorded in the run summary's `warnings`. It does not stop the
deploy. Whether verbose REST returns the value as a number or a name has
not been measured, so both are accepted and anything else is reported as
unreadable. Sealing narrows the window rather than closing
it: `seal_columns: true` is the default and [blocks UI schema
edits](../reference/mapping.md#protection), but a mapping running
`seal_columns: false` has no such cover. So what this section guarantees is
the state of the lookups this deploy creates.

**Cross-web targets** are a separate case: not merely unset but refused, by
`lookup_crosses_site_role`, an error, when a lookup's source and target
entities map to different `site_role`s. Use
[`cross_site_reference_columns`](../reference/mapping.md#entities) instead,
which expands to a Choice + URL pair on the source list and never creates a
Lookup at all. The evidence for and against the same-site rule, including
the server object model overload that documents a cross-web lookup as
supported on a surface this project does not use, is recorded in
`analysis/limits.py` under "lookup target scope" and summarised on
[SharePoint limits you must know](./sharepoint-limits.md).

### Whether a write is checked against the target list

This is **not established**, so this page does not answer it.

The question is what SharePoint does with a write that names a row the target
list does not hold. It is a real path rather than a hypothetical one, because
an id reaches a lookup without a picker whenever a row is written through the
REST API, which sends it as a plain number (`RelatedRiskId: 4`). Whether
SharePoint refuses such an id, accepts it and stores it, or accepts it and
stores nothing, is not documented. Searched Microsoft Learn and Microsoft
Support 2026-09-14: the [`Field`
element](https://learn.microsoft.com/sharepoint/dev/schema/field-element-field)
documents `RelationshipDeleteBehavior` and its default, and neither that page
nor Microsoft's [lookup column
guidance](https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/create-list-relationships-by-using-lookup-columns)
says what a write of an unmatched id does. The build cannot answer it either: a
schema has no way to know which rows a list will hold.

What would settle it is the absent-id arm of
`test/manual/projected-lookup-probe.js`, which is written and not yet run. It
derives an id the target list does not hold, reads it back as absent to prove
it, then writes it into the lookup and records what the write answered and what
the row then carries: `field.lookup.absent-target-id-write` and
`field.lookup.absent-target-id-readback`, each behind
`field.lookup.control-present-target-id-write-accepted` and
`field.lookup.control-absent-target-id-names-no-row`. `analysis/limits.py`
records the same parking under "lookup write-time enforcement". Until that has
run, treat write-time enforcement as unknown rather than as absent.

### What happens to a child row when its parent is deleted

This is **not established**, so this page does not answer it.

The default is documented. Microsoft's [`Field`
element](https://learn.microsoft.com/sharepoint/dev/schema/field-element-field)
states that `RelationshipDeleteBehavior` is `None` unless set, and this tool
never sets it, so every lookup it creates is at `None`. An adopted lookup is
at whatever it already carried, for the reason given above. What `None` then
does to an existing child row when the referenced parent is recycled, and
again when it is deleted from the recycle bin, is not stated on that page
and is not recorded anywhere in this repository.

Microsoft's [lookup column
guidance](https://support.microsoft.com/en-us/sharepoint/lists/data-and-lists/create-list-relationships-by-using-lookup-columns)
does say something about the default, read 2026-09-14, and it makes the
question more open rather than less. It states that if **Enforce relationship
behavior** is left unchecked, "then the default is when you delete from the
source list, the item is also removed from the target list". That page's
vocabulary is the reverse of this one's, since there the *source* list is the
one being looked up and the *target* list is the one carrying the Lookup
column, so the sentence describes a parent delete removing the child row. That
is a cascade, and the `Field` element page above documents the unset value as
`None`. Two Microsoft pages that disagree are a reason to measure.

The plausible answers differ sharply for anyone reporting on the data (the
cell blanks, the cell keeps a dangling id, the cell keeps the stale text)
and a schema diagram cannot tell them apart, which is exactly the sort of
claim this project declines to guess at.

What would settle it is the probe named in issue #31, a
`test/manual/lookup-delete-probe.js` for a human to paste into a live site.
It should create a parent and a child through the normal deploy path, read
back the lookup's relationship properties as deployed, recycle a referenced
parent item, then delete it from the recycle bin, and record what the child
row's lookup reads at each step. Until that has run, treat parent deletion
as an unknown.

## What a relationship costs

Two budgets, both on [SharePoint limits you must
know](./sharepoint-limits.md) and neither of them optional reading before a
schema accumulates refs:

- **12 joins per view.** Every rendered Lookup costs one, whether or not it
  holds data, and so does every `person` column plus `Author` and `Editor`.
  A view over the ceiling is blank at any list size, including a list of ten
  rows. A multi-value lookup costs one, a projection costs nothing.
- **The target list's index budget.** A lookup target carries an automatic
  index on its display column, out of the twenty a list has. A list reached
  only by a `cross_site_reference_columns` entry carries none, because
  nothing enumerates it.

Indexing a Lookup column does not make it a useful filter on a large list.
Microsoft says so on the [`Field`
element](https://learn.microsoft.com/sharepoint/dev/schema/field-element-field):
"Although you can index a Lookup column to improve performance, using an
indexed Lookup column to prevent exceeding the list view threshold does not
work." Filter on a selective scalar column instead.

## Reading on

- [DBML reference: references](../reference/dbml.md#references-lookups) for
  the declaration syntax in context.
- [Mapping reference: `entities`](../reference/mapping.md#entities) for
  `display_column` and `cross_site_reference_columns`.
- [Mapping reference:
  `lookup_projections`](../reference/mapping.md#lookup_projections).
- [SharePoint limits you must know](./sharepoint-limits.md) for the join
  ceiling and the list view threshold in full.
