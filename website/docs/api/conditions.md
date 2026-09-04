---
title: Condition grammar
sidebar_position: 4
---

# Condition grammar

:::note Generated
Every rendering below is produced by running the renderer, not written
by hand; see `website/scripts/generate_api.py`.
:::

The shared condition grammar's types and structural parser.

One grammar serves every conditional surface in the mapping
(`views[].where`, `form_visibility.when`, `column_validation.when` and
`list_validation.when`), because every SharePoint syntax difference the
alternative exposes is a rendering concern the author should never meet.
Those differences are not hypothetical: validation formulas reject single
quotes and require double, conditional-visibility expressions require
single and double an embedded apostrophe, one target spells booleans
`AND(...)` and the other `&&`, and column references are `[Col]` here and
`[$Col]` there. Authors who write target syntax by hand get those wrong
silently, because a malformed formula still saves and simply evaluates to
the wrong answer.

Structural checks only: shape, required keys, group arity. Anything needing
the schema (does this column exist, can this target render this operator)
lives in `analysis.conditions`, matching the parser/validator split used
everywhere else in this package.



## Operators

`views[].where` renders to CAML, `form_visibility.when` to a list-formatting expression, and `column_validation.when` / `list_validation.when` to a classic validation formula.

| Declared | CAML | Expression | Validation |
|---|---|---|---|
| `eq` | `<Eq><FieldRef Name="Status"/><Value Type="Text">Open</Value></Eq>` | `[$Status] == 'Open'` | `[Status]="Open"` |
| `neq` | `<Or><IsNull><FieldRef Name="Status"/></IsNull><Neq><FieldRef Name="Status"/><Value Type="Text">Open</Value></Neq></Or>` | `[$Status] != 'Open'` | `[Status]<>"Open"` |
| `lt` | `<Lt><FieldRef Name="Count"/><Value Type="Number">5</Value></Lt>` | `[$Count] < 5` | `[Count]<5` |
| `geq` | `<Geq><FieldRef Name="Count"/><Value Type="Number">5</Value></Geq>` | `[$Count] >= 5` | `[Count]>=5` |
| `is_null` | `<IsNull><FieldRef Name="Note"/></IsNull>` | `[$Note] == ''` | `ISBLANK([Note])` |
| `is_not_null` | `<IsNotNull><FieldRef Name="Note"/></IsNotNull>` | `[$Note] != ''` | `NOT(ISBLANK([Note]))` |
| `in` | `<Or><Eq><FieldRef Name="Status"/><Value Type="Text">A</Value></Eq><Eq><FieldRef Name="Status"/><Value Type="Text">B</Value></Eq></Or>` | `([$Status] == 'A' || [$Status] == 'B')` | `OR([Status]="A",[Status]="B")` |
| `not_in` | `<Or><IsNull><FieldRef Name="Status"/></IsNull><And><Neq><FieldRef Name="Status"/><Value Type="Text">A</Value></Neq><Neq><FieldRef Name="Status"/><Value Type="Text">B</Value></Neq></And></Or>` | `([$Status] != 'A' && [$Status] != 'B')` | `AND([Status]<>"A",[Status]<>"B")` |
| `contains` | `<Contains><FieldRef Name="Note"/><Value Type="Text">x</Value></Contains>` | `indexOf([$Note], 'x') >= 0` | `ISNUMBER(FIND("x",[Note]))` |
| `begins_with` | `<BeginsWith><FieldRef Name="Note"/><Value Type="Text">ab</Value></BeginsWith>` | `indexOf([$Note], 'ab') == 0` | `LEFT([Note],2)="ab"` |
| `includes` | `<Eq><FieldRef Name="Events"/><Value Type="Text">View</Value></Eq>` | _not supported: operator 'includes' has no rendering_ | _not supported: operator 'includes' has no rendering_ |
| `not_includes` | `<Or><IsNull><FieldRef Name="Events"/></IsNull><Neq><FieldRef Name="Events"/><Value Type="Text">View</Value></Neq></Or>` | _not supported: operator 'not_includes' has no rendering_ | _not supported: operator 'not_includes' has no rendering_ |
| `measure: length` | _not supported: 'measure' cannot be rendered: CAML has no LEN_ | _not supported: 'measure' cannot be rendered: list formatting's length() counts array items and returns 1/0 for other types -- it does not measure a string, so the formula would be false for every value_ | `LEN([Note])>10` |
| `property (person)` | _not supported: CAML cannot reach person or lookup sub-properties. The one exception is a comparison against a MULTI-VALUE lookup, where 'lookupValue' and 'lookupId' name the two operand dialects measured on 2026-09-04; a null test is not a comparison and needs no operand, since a row with no value has neither a title nor an id_ | `[$Owner.title] != ''` | _not supported: person and lookup operands are unsupported in validation formulas_ |

## Not yet verified

Nothing is waiting on a probe that has been written and not run. That
is what this section reports, and an empty one is the good state, so
it says so rather than leaving a blank.

It is not a claim that every operator was watched in a form. The four
text operators were; the comparison and null tests rest on formulas
harvested from a live tenant rather than on written syntax. Where a
rendering is derived rather than observed, the source says so.

## Operand accessors

| Column kind | Required `property` |
|---|---|
| lookup | `lookupId`, `lookupValue` |
| person | `email`, `id`, `title` |

## Bounds

At most **4** nested groups and **32** conditions, counted after normalisation;
negation expands each leaf and `in` expands to one condition per value.

## Normalisation

Normalisation and rendering for the shared condition grammar.

This module is dependency-light by design. It owns target capability truth and
raises renderer-neutral refusals; diagnosis translates those refusals into
classified diagnostics in :mod:`dbml_sharepoint.analysis.conditions`.

BREAKING API MOVE (#168): import rendering constants and functions from
`dbml_sharepoint.analysis.condition_rendering`. They are not re-exported from
`dbml_sharepoint.analysis.conditions`.



