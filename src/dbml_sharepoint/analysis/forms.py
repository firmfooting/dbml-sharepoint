# src/dbml_sharepoint/analysis/forms.py
"""Composing declared form visibility into a single stored formula.

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
"""

from dbml_sharepoint.analysis.conditions import EXPRESSION, to_expression, validate_condition

# `as Severity` is the PEP 484 explicit re-export. This module's public
# signature is `list[tuple[Severity, str]]`, so a caller reading it has
# always been able to import the name from here; under mypy --strict a
# plain import would quietly stop being importable.
from dbml_sharepoint.analysis.findings import Severity as Severity
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


def validate_form_visibility(
    *,
    column: str,
    new: bool,
    existing: bool,
    when: Condition | None,
    required: bool,
    has_default: bool,
    is_calculated: bool,
    rendered: set[str],
    types: dict[str, str],
    lookups: set[str],
    context: str,
) -> list[tuple[Severity, str]]:
    """Semantic problems with one column's declaration, as
    (severity, message) pairs.

    The severity is carried structurally rather than described in the
    prose. Every message used to be returned as a bare string and wrapped
    by the caller as an error, including the one case the spec makes a
    WARNING — a required column that a `when` predicate *may* hide at
    creation. Its text said "(warning: …)" while it failed the build, so
    the one genuinely conditional declaration the feature exists to
    express could not be deployed at all.
    """
    problems: list[tuple[Severity, str]] = []
    if is_calculated:
        problems.append((
            "error",
            (f"{context}: {column!r} is a calculated column — calculated columns never "
             f"appear on entry forms, so declaring their visibility is a mistake"),
        ))
    if not new and not existing and when is not None:
        problems.append((
            "error",
            (f"{context}: {column!r} is hidden on every form, so 'when' can never be "
             f"reached — drop one or the other"),
        ))
    if not new and required and not has_default:
        # Statically provable: the gate is false on the New form whatever
        # `when` says, so every create would fail its required check. The
        # equivalent hidden_on_forms case is only a warning today; this is
        # an error because the build can prove it.
        problems.append((
            "error",
            (f"{context}: {column!r} is required with no default and hidden from the New "
             f"form, so every save would fail"),
        ))
    elif when is not None and required and not has_default:
        # NOT provable: whether the predicate holds on the New form depends
        # on what the person types. A warning, per the spec.
        problems.append((
            "warning",
            (f"{context}: {column!r} is required with no default and 'when' may hide it "
             f"at creation, which would fail the save — this cannot be decided at "
             f"build time"),
        ))
    if when is not None:
        problems.extend(
            ("error", message)
            for message in validate_condition(
                when,
                target=EXPRESSION,
                rendered=rendered,
                types=types,
                lookups=lookups,
                context=f"{context}.{column}.when",
            )
        )
    return problems
