# src/dbml_sharepoint/analysis/forms.py
"""Classified validation of a form-visibility declaration.

Composing the declaration into the single stored `ClientValidationFormula`
lives in `analysis.form_rendering`; this module only diagnoses what a
declaration gets wrong, as `Finding`s.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace

from dbml_sharepoint.analysis.condition_rendering import EXPRESSION
from dbml_sharepoint.analysis.conditions import condition_findings
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location
from dbml_sharepoint.analysis.typemap import is_boolean
from dbml_sharepoint.model.conditions import Condition


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
    enum_members: Mapping[str, Sequence[str]],
    at: Location,
) -> list[Finding]:
    """Semantic problems with one column's declaration, as Findings.

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
    """
    findings: list[Finding] = []
    if is_calculated:
        findings.append(Finding(
            FindingCode.FORM_VISIBILITY_ON_A_CALCULATED_COLUMN,
            (f"{at.path}: {column!r} is a calculated column -- calculated columns never "
             f"appear on entry forms, so declaring their visibility is a mistake"),
            location=at,
        ))
    if when is not None and is_boolean(types.get(column)):
        # Measured live 2026-09-04: the MERGE that sets a composed
        # ClientValidationFormula on a Yes/No field (kind 8) is refused with
        # HTTP 500 "This field type does not support validation formulas",
        # which aborts phase 2.1 at that field. Only the composed formula is
        # measured, so only `when` is refused; a gate-only declaration and a
        # server-side ValidationFormula on kind 8 are both untested and stay
        # deployable rather than being guessed at.
        findings.append(Finding(
            FindingCode.FORM_VISIBILITY_CONDITION_ON_A_BOOLEAN_COLUMN,
            (f"{at.path}: {column!r} is a Yes/No column and SharePoint refuses "
             f"validation formulas on that field type, so conditional visibility "
             f"cannot be deployed -- declare the visibility without 'when', or move "
             f"the column off boolean"),
            location=at,
        ))
    if not new and not existing and when is not None:
        findings.append(Finding(
            FindingCode.FORM_VISIBILITY_CONDITION_UNREACHABLE,
            (f"{at.path}: {column!r} is hidden on every form, so 'when' can never be "
             f"reached -- drop one or the other"),
            location=at,
        ))
    if not new and required and not has_default:
        # Statically provable: the gate is false on the New form whatever
        # `when` says, so every create would fail its required check. The
        # equivalent hidden_on_forms case is only a warning today; this is
        # an error because the build can prove it.
        findings.append(Finding(
            FindingCode.REQUIRED_COLUMN_HIDDEN_FROM_THE_NEW_FORM,
            (f"{at.path}: {column!r} is required with no default and hidden from the New "
             f"form, so every save would fail"),
            location=at,
        ))
    elif when is not None and required and not has_default:
        # NOT provable: whether the predicate holds on the New form depends
        # on what the person types. A warning, per the spec.
        findings.append(Finding(
            FindingCode.REQUIRED_COLUMN_MAY_BE_HIDDEN_AT_CREATION,
            (f"{at.path}: {column!r} is required with no default and 'when' may hide it "
             f"at creation, which would fail the save -- this cannot be decided at "
             f"build time"),
            location=at,
        ))
    if when is not None:
        # The condition grammar classifies its own problems: one code per
        # broken leaf rather than one code for "the when is bad".
        findings.extend(condition_findings(
            when,
            target=EXPRESSION,
            rendered=rendered,
            types=types,
            lookups=lookups,
            enum_members=enum_members,
            at=replace(at, column=column, sub="when"),
        ))
    return findings
