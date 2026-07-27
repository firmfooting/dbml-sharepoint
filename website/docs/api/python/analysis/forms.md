---
title: forms
sidebar_position: 12
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
afterwards — the only per-form discriminator available in a formula that
the form designer preserves. SchemaXml's ShowIn*Form attributes look like
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
def validate_form_visibility(*, column: str, new: bool, existing: bool, when: Condition | None, required: bool, has_default: bool, is_calculated: bool, rendered: set[str], types: dict[str, str], lookups: set[str], context: str) -> list[str]
```

Semantic problems with one column's declaration, as messages.

