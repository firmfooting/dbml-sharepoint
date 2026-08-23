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
| `property (person)` | _not supported: CAML cannot reach person or lookup sub-properties_ | `[$Owner.title] != ''` | _not supported: person and lookup operands are unsupported in validation formulas_ |

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

Normalisation, validation and rendering for the shared condition grammar.

`none_of` is eliminated here rather than at render time, because CAML has
no group-level negation: a renderer meeting a negated group would have
nothing to emit. De Morgan pushes negation down to the leaves, where every
operator has an exact inverse, so both renderers only ever see
`all_of`/`any_of` over positive leaves. That is the single property which
lets one authored grammar serve targets of very different expressive power.

The transformation is mechanical, terminating and depth-preserving:

    none_of[A, B]     ->  all_of[!A, !B]
    !(all_of[X, Y])   ->  any_of[!X, !Y]
    !(any_of[X, Y])   ->  all_of[!X, !Y]

Implications need no operator of their own. A validation rule is usually
"if A then B", which is `any_of[none_of[A], B]`, expressible in the
grammar as authored and normalised by the rules above.

BREAKING API CHANGE (#168): `validate_condition` was removed. Use
`condition_findings`, which preserves each problem's finding code and leaf
location instead of returning message-only prose.



