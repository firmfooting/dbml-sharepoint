---
title: forms
sidebar_position: 26
---

# `dbml_sharepoint.analysis.forms`

*classified form-visibility validation*

Classified validation of a form-visibility declaration.

Composing the declaration into the single stored `ClientValidationFormula`
lives in `analysis.form_rendering`; this module only diagnoses what a
declaration gets wrong, as `Finding`s.

### `validate_form_visibility`

```python
def validate_form_visibility(*, column: str, new: bool, existing: bool, when: Condition | None, required: bool, has_default: bool, is_calculated: bool, rendered: set[str], types: dict[str, str], lookups: set[str], enum_members: collections.abc.Mapping[str, collections.abc.Sequence[str]], at: dbml_sharepoint.analysis.findings.Location) -> list[dbml_sharepoint.analysis.findings.Finding]
```

Semantic problems with one column's declaration, as Findings.

Six distinct rules live here, and each has its own code. The severity
is carried structurally rather than described in the prose: every
message used to be returned as a bare string and wrapped by the caller
as an error, including the one case the spec makes a WARNING, a
required column that a `when` predicate *may* hide at creation. Its
text said "(warning: ...)" while it failed the build, so the one
genuinely conditional declaration the feature exists to express could
not be deployed at all.

Returning Findings rather than (severity, message) pairs is what keeps
those six apart. The caller cannot supply the code, because it does
not know which rule fired. One code at the call site would collapse
all six into one.

`at` locates the DECLARATION, which is `retired_columns[E]` when the
retirement fold synthesised it and `form_visibility[E]` otherwise. The
column is named in the prose rather than in the path, because that is
where these messages have always put it.

