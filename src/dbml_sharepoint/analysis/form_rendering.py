# src/dbml_sharepoint/analysis/form_rendering.py
"""Composing declared form visibility into a single stored formula.

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

`compose_visibility` moved here from `analysis.forms` so the generators can
import composition without loading diagnosis, and `analysis.forms` keeps no
re-export.
"""

from dbml_sharepoint.analysis.condition_rendering import to_expression
from dbml_sharepoint.model.conditions import Condition

# Empty on the New form, populated on Edit and Display. Verified live.
_NEW_ONLY = "[$ID] == ''"
_EXISTING_ONLY = "[$ID] != ''"
_NEVER = "false"


def compose_visibility(
    *,
    new: bool,
    existing: bool,
    when: Condition | None,
    types: dict[str, str],
) -> str:
    """The formula for one column, or `""` when nothing is declared.

    Operators are `&&` and `||`, never `and()`/`or()`: the
    conditional-formula dialog rejects the function forms. The `when` tree
    is parenthesised when combined with a gate so operator precedence
    cannot change what the author declared.
    """
    gate = _gate(new=new, existing=existing)
    predicate = to_expression(when, types) if when is not None else None

    if gate is None and predicate is None:
        return ""
    if gate == _NEVER:
        # Hidden everywhere; a condition on top would be unreachable, and
        # the validator rejects that combination before this is reached.
        expression = _NEVER
    elif gate is None:
        expression = predicate or _NEVER
    elif predicate is None:
        expression = gate
    else:
        expression = f"{gate} && ({predicate})"
    return f"=if({expression}, 'true', 'false')"


def _gate(*, new: bool, existing: bool) -> str | None:
    if new and existing:
        return None
    if not new and not existing:
        return _NEVER
    return _EXISTING_ONLY if existing else _NEW_ONLY
