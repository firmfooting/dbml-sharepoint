---
title: forms
sidebar_position: 18
---

# `dbml_sharepoint.analysis.forms`

*composing declared form visibility*

Composing declared form visibility into a single stored formula.

SharePoint gives a column exactly one `ClientValidationFormula`, so
per-form visibility and conditional visibility must be combined at build
time or declaring one would silently destroy the other. That composition is
the reason this feature is declarative at all: an author states both and
never learns they share a slot.

The gate exploits `[$ID]`, which is empty on the New form and populated
afterwards (the only per-form discriminator available in a formula that
the form designer preserves). SchemaXml's ShowIn*Form attributes look like
the obvious mechanism and are not: saving the designer migrates them into
`FieldLink.Hidden`, which hides a column from *every* form and cannot be
undone over REST. See the form_visibility spec.

### `compose_visibility`

```python
def compose_visibility(*, new: bool, existing: bool, when: Condition | None, types: dict[str, str]) -> str
```

The formula for one column, or `""` when nothing is declared.

Operators are `&&` and `||`, never `and()`/`or()`: the
conditional-formula dialog rejects the function forms. The `when` tree
is parenthesised when combined with a gate so operator precedence
cannot change what the author declared.

### `validate_form_visibility`

```python
def validate_form_visibility(*, column: str, new: bool, existing: bool, when: Condition | None, required: bool, has_default: bool, is_calculated: bool, rendered: set[str], types: dict[str, str], lookups: set[str], at: dbml_sharepoint.analysis.findings.Location) -> list[dbml_sharepoint.analysis.findings.Finding]
```

Semantic problems with one column's declaration, as Findings.

Five distinct rules live here, and each has its own code. The severity
is carried structurally rather than described in the prose: every
message used to be returned as a bare string and wrapped by the caller
as an error, including the one case the spec makes a WARNING, a
required column that a `when` predicate *may* hide at creation. Its
text said "(warning: ...)" while it failed the build, so the one
genuinely conditional declaration the feature exists to express could
not be deployed at all.

Returning Findings rather than (severity, message) pairs is what keeps
those five apart. The caller cannot supply the code, because it does
not know which rule fired. One code at the call site would collapse
all five into one.

`at` locates the DECLARATION, which is `retired_columns[E]` when the
retirement fold synthesised it and `form_visibility[E]` otherwise. The
column is named in the prose rather than in the path, because that is
where these messages have always put it.

