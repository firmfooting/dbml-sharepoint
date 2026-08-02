"""Validator: retired columns."""
from pathlib import Path

from _builders import ID_PK, table
from _packs import blocks, entities, pack

from dbml_sharepoint.analysis.validator import (
    validate_against_mapping,
)

#: The severity enum these fixtures retire columns from.
_RAG = """
Enum rag {
  "Green"
  "Amber"
}
"""


def _board(*columns: str) -> str:
    """The `Board` table every test in this module retires a column of.

    Deliberately not `_builders.TITLE`: these fixtures declare a nullable
    `Title`, and the not-null retirement rules are exercised through explicit
    `MustFill` and `Stamp` columns instead.
    """
    return table("Board", ID_PK, "Title nvarchar", *columns)


# --- Retired columns --------------------------------------------------------


def test_calculated_formula_pairing_guards_the_retirement_carve_out(
    tmp_path: Path,
) -> None:
    """GUARD. `_apply_retirement` (model/mapping_loader.py) skips the
    form_visibility fold for calculated columns, and identifies them by
    their `calculated_formulas` keys — the loader has never seen the DBML
    and cannot read column types. That is correct ONLY while those keys are
    exactly the set of `calculated_*` columns.

    Both directions of that pairing are asserted below. If you are here
    because you relaxed one of them, go and read `_apply_retirement`'s
    carve-out first: loosening either rule silently lets a calculated
    column reach form_visibility, where the validator rejects it, making
    retiring that column an unfixable build error.
    """
    # Direction 1: a calculated column with NO formula must error.
    schema, bundle = pack(
        tmp_path,
        dbml=_board("BoardDate date", "Route calculated_text"),
        mapping=entities("Board"),
        dbml_name="no-formula.dbml",
        mapping_name="no-formula.yaml",
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        "Board.Route" in f.message and "has no" in f.message and "formula" in f.message
        for f in findings if f.severity == "error"
    )

    # Direction 2: a formula targeting a NON-calculated column must error.
    schema, bundle = pack(
        tmp_path,
        dbml=_board("BoardDate date"),
        mapping=blocks(entities("Board"), """
            calculated_formulas:
              Board:
                BoardDate: '=1'
        """),
        dbml_name="wrong-target.dbml",
        mapping_name="wrong-target.yaml",
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        "calculated_formulas[Board]" in f.message and "'BoardDate'" in f.message
        for f in findings if f.severity == "error"
    )

def test_retired_columns_errors(tmp_path: Path) -> None:
    """Fail closed where a retirement mistake would break the list. The
    not-null-with-no-default case is the load-bearing one: retirement hides
    the column from the New form, so every subsequent save would fail."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(_RAG, _board(
            "BoardDate date [not null]",
            "OperationsStatus rag",
            "SiteServicesStatus rag",
            "MustFill nvarchar [not null]",
            "Route calculated_text",
        )),
        mapping=blocks(entities("Board"), """
            calculated_formulas:
              Board:
                Route: '=[OperationsStatus]'
            list_validation:
              Board:
                when:
                  - { field: OperationsStatus, op: is_not_null }
                message: "Give a status."
            column_validation:
              Board:
                reconcile: declared
                columns:
                  OperationsStatus:
                    when: [{ field: OperationsStatus, op: is_not_null }]
                    message: "Needed."
            retired_columns:
              Widget: [Anything]
              Board:
                Ghost:
                  retired: 2026-09-01
                OperationsStatus:
                  retired: not-a-date
                  superseded_by: OperationsStatus
                MustFill:
                  retired: 2026-09-01
                  superseded_by: Nowhere
                SiteServicesStatus:
                  retired: 2026-09-01
        """),
    )
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]

    def has(*needles: str) -> bool:
        return any(all(n in f.message for n in needles) for f in errors)

    # Unknown entity, and a column the DBML does not declare.
    assert has("retired_columns[Widget]", "unknown entity")
    assert has("retired_columns[Board]", "'Ghost'", "not a rendered column")
    # Unparseable retirement date.
    assert has("retired_columns[Board].OperationsStatus", "not an ISO date")
    # superseded_by pointing at itself, and at nothing.
    assert has("retired_columns[Board].OperationsStatus", "the retired column itself")
    assert has("retired_columns[Board].MustFill", "'Nowhere'", "not a rendered column")
    # not null with no declared default — the escalation, reported against
    # retirement rather than against a form_visibility section nobody wrote.
    assert has("retired_columns[Board]", "'MustFill'", "every save would fail")
    # Live formulas referencing a retired column.
    assert has("calculated_formulas[Board].Route", "[OperationsStatus]", "retired")
    assert has("list_validation[Board]", "OperationsStatus", "retired")
    # A save rule ON a retired column: retirement hides it from the new form,
    # so is_not_null there rejects every new item with no field to satisfy
    # it. The list silently stops accepting rows.
    assert has("column_validation[Board].OperationsStatus", "retired", "every new item")

def test_retired_supersession_may_not_name_another_retirement(tmp_path: Path) -> None:
    """Superseding one dead column with another leaves the operator with no
    live destination for the data."""
    schema, bundle = pack(
        tmp_path,
        dbml=_board("OldA nvarchar", "OldB nvarchar"),
        mapping=blocks(entities("Board"), """
            retired_columns:
              Board:
                OldA:
                  retired: 2026-09-01
                  superseded_by: OldB
                OldB:
                  retired: 2026-09-01
        """),
    )
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert any(
        "retired_columns[Board].OldA" in f.message and "itself retired" in f.message
        for f in errors
    )

def test_retiring_an_undeployable_column_is_rejected(tmp_path: Path) -> None:
    """Retirement resolves into a per-column declaration, and the built-in
    Title never receives one — it is provisioned through its own patch. A
    retirement that cannot be carried out must say so rather than validate
    clean and deploy nothing."""
    schema, bundle = pack(
        tmp_path,
        dbml=_board("BoardDate date"),
        mapping=blocks(entities("Board"), """
            retired_columns:
              Board: [Title]
        """),
    )
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert any(
        "retired_columns[Board]" in f.message and "'Title'" in f.message
        for f in errors
    )
    # The message is the one the undeployable-column rule already owns, so
    # the two cannot drift; only the context says where to fix it.
    assert any("its own patch" in f.message for f in errors)

def test_retired_calculated_column_is_not_an_unfixable_build_error(
    tmp_path: Path,
) -> None:
    """Retiring a calculated column must be possible. It is never folded
    into form_visibility, so the validator's "calculated columns never
    appear on entry forms" error must not fire."""
    schema, bundle = pack(
        tmp_path,
        dbml=_board("BoardDate date", "Route calculated_text"),
        mapping=blocks(entities("Board"), """
            calculated_formulas:
              Board:
                Route: '=[BoardDate]'
            retired_columns:
              Board:
                Route:
                  retired: 2026-09-01
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    assert not [f for f in findings if f.severity == "error"]
    assert "Board" not in bundle.mapping.form_visibility

def test_retired_calculated_column_without_a_formula_reports_only_root_cause(
    tmp_path: Path,
) -> None:
    """The one wrong answer the loader's calculated-column heuristic can
    give. The author declared a calculated column and forgot its formula,
    so `_apply_retirement` cannot tell it is calculated and folds it into
    form_visibility. The build must report the missing formula and NOTHING
    else — blaming the author for a form_visibility entry they never wrote
    buries the error they can actually act on."""
    schema, bundle = pack(
        tmp_path,
        dbml=_board("BoardDate date", "Route calculated_text"),
        mapping=blocks(entities("Board"), """
            retired_columns:
              Board: [Route]
        """),
    )
    # The loader could not know Route was calculated, so it DID fold it.
    assert "Route" in bundle.mapping.form_visibility["Board"].columns

    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert len(errors) == 1, [f.message for f in errors]
    assert "Board.Route" in errors[0].message
    assert "calculated_formulas.Board.Route" in errors[0].message

def test_retired_columns_warnings(tmp_path: Path) -> None:
    """Warn where a retirement mistake only wastes something. Retirement
    must never break a build: a stale view or width reference is stripped
    and reported, not rejected. A column_formatting entry on a retired
    column is KEPT deliberately — historical values still render with their
    severity colours wherever the column is still shown."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(_RAG, _board(
            "BoardDate date",
            "OperationsStatus rag",
            "Stamp nvarchar [not null, default: 'x']",
            "indexes { OperationsStatus }",
        )),
        mapping=blocks(entities("Board"), """
            display_names:
              mode: auto
            column_formatting:
              Board:
                OperationsStatus: { style: severity, map: { Green: good } }
            form_formatting:
              Board:
                body:
                  sections:
                    - displayname: "Header"
                      fields: [BoardDate, OperationsStatus]
            views:
              Board:
                - title: "Heat grid"
                  fields: [BoardDate, OperationsStatus]
                  widths: { OperationsStatus: 120 }
                - title: "Statuses only"
                  fields: [OperationsStatus]
            retired_columns:
              Board:
                OperationsStatus:
                  retired: 2026-09-01
                Stamp:
                  retired: 2026-09-01
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    warnings = [f for f in findings if f.severity == "warning"]

    def warned(*needles: str) -> bool:
        return any(all(n in f.message for n in needles) for f in warnings)

    # not null WITH a default: saves succeed, the default is stamped forever.
    assert warned("retired_columns[Board]", "'Stamp'", "stamped with")
    # A dead index is dead weight against a finite per-list budget.
    assert warned("retired_columns[Board]", "'OperationsStatus'", "indexes block")
    # Stripped view field, width and form-section references — reported,
    # never rejected. One generic loop over retirement_strips covers all
    # three; the context string is what distinguishes them.
    assert warned("views[Board].Heat grid fields", "stripped it")
    assert warned("views[Board].Heat grid widths", "stripped it")
    assert warned("form_formatting[Board].body sections", "stripped it")
    # A view left with no fields at all.
    assert warned("views[Board].Statuses only", "every declared field")
    # Never an error: retirement must not break a build.
    assert not [f for f in findings if f.severity == "error"]
    # column_formatting on a retired column is kept, not flagged.
    assert not warned("column_formatting")

def test_retirement_without_display_names_warns_the_suffix_is_inert(
    tmp_path: Path,
) -> None:
    """display_name_for ignores overrides unless mode is auto, so without a
    display_names section the ' (retired)' suffix never reaches SharePoint."""
    schema, bundle = pack(
        tmp_path,
        dbml=_board("OldColumn nvarchar"),
        mapping=blocks(entities("Board"), """
            retired_columns:
              Board: [OldColumn]
        """),
    )
    warnings = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "warning"
    ]
    assert any(
        "display_names is not enabled" in f.message and "(retired)" in f.message
        for f in warnings
    )

def test_retirement_replacing_a_form_visibility_declaration_warns(
    tmp_path: Path,
) -> None:
    """The fold overwrites a hand-written declaration for a retired column.
    Silent mutation of the author's own YAML is exactly what the strip
    record exists to surface."""
    schema, bundle = pack(
        tmp_path,
        dbml=_board("OldColumn nvarchar"),
        mapping=blocks(entities("Board"), """
            form_visibility:
              Board:
                columns:
                  OldColumn: visible
            retired_columns:
              Board: [OldColumn]
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "warning"
        and "form_visibility[Board].columns" in f.message
        and "stripped it" in f.message
        for f in findings
    )
