"""Validator: retired columns.

Almost every fixture here stays on the filesystem, and deliberately.
Retirement is a LOAD-TIME transform: `_apply_retirement` runs inside
`load_mapping`, synthesising `form_visibility` entries, appending the
' (retired)' display-name override, stripping the column out of views,
widths and form body sections, and recording a `retirement_strips` entry
for each rewrite. Every assertion below is about what that fold produced,
and an object-built bundle never meets it.

The tempting fix is a `retired=` option on `_model.mapping` that runs the
fold. That would NOT be a test asserting its own arithmetic -- the builder
would call the real `_apply_retirement`, so the fold stays under test. It
was rejected for two other reasons:

1. It buys nothing measurable. These tests pass and their coverage is
   identical either way; the migration exists to delete text that was never
   the subject, and here the load-time fold IS the subject.
2. It would make `_model` run a production transform, which no other
   builder does -- `_loader_defaults` copies the loader's defaults by hand
   precisely so a fixture is always the literal shape it reads as. Once one
   builder folds, a reader cannot tell whether any given fixture is pre- or
   post-fold without going and reading the builder.

What these tests actually protect is the VALIDATOR check, not the fold:
deleting this module takes `analysis/checks/_retirement.py` from 95% to
79% (7 missing lines to 27), while `model/_retirement.py` does not move --
its parse half is covered by `test_mapping_loader.py`. So the thing to
preserve here is coverage of the checks, which is reached through a loaded
bundle and by nothing else.

The one exception is the pairing guard immediately below, which declares no
`retired_columns` at all.
"""
from pathlib import Path

from _builders import ID_PK, table
from _findings import by_severity, messages, none_of, only
from _model import bundle as make_bundle
from _model import column as make_column
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, entities, pack

from dbml_sharepoint.analysis.findings import (
    Finding,
    FindingCode,
    Location,
    Section,
)
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


def test_calculated_formula_pairing_guards_the_retirement_carve_out() -> None:
    """GUARD. `_apply_retirement` (model/mapping_loader.py) skips the
    form_visibility fold for calculated columns, and identifies them by
    their `calculated_formulas` keys. The loader has never seen the DBML
    and cannot read column types. That is correct ONLY while those keys are
    exactly the set of `calculated_*` columns.

    Both directions of that pairing are asserted below. If you are here
    because you relaxed one of them, go and read `_apply_retirement`'s
    carve-out first: loosening either rule silently lets a calculated
    column reach form_visibility, where the validator rejects it, making
    retiring that column an unfixable build error.

    Built as objects, unlike the rest of this module: it declares no
    `retired_columns`, so there is no fold for the loader to perform.
    """
    # Direction 1: a calculated column with NO formula must error.
    schema = make_schema(make_table(
        "Board",
        make_column("Title"),
        make_column("BoardDate", "date"),
        make_column("Route", "calculated_text"),
    ))
    f = only(
        validate_against_mapping(schema, make_bundle(entities=["Board"])),
        FindingCode.CALCULATED_COLUMN_HAS_NO_FORMULA,
    )
    assert f.severity == "error"
    # No location on this one, so the column reaches the reader in prose.
    assert "Board.Route" in f.message

    # Direction 2: a formula targeting a NON-calculated column must error.
    schema = make_schema(make_table(
        "Board", make_column("Title"), make_column("BoardDate", "date"),
    ))
    bundle = make_bundle(
        entities=["Board"], calculated_formulas={"Board": {"BoardDate": "=1"}},
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.FORMULA_TARGET_NOT_CALCULATED,
    )
    assert f.severity == "error"
    assert f.location == Location(Section.CALCULATED_FORMULAS, entity="Board")
    assert "'BoardDate'" in f.message

def test_retired_columns_errors(tmp_path: Path) -> None:
    """Fail closed where a retirement mistake would break the list. The
    not-null-with-no-default case is the one that matters: retirement hides
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
    errors = by_severity(validate_against_mapping(schema, bundle), "error")
    board = Location(Section.RETIRED_COLUMNS, entity="Board")
    ops = Location(Section.RETIRED_COLUMNS, entity="Board", column="OperationsStatus")

    def at(location: Location, code: FindingCode) -> Finding:
        """The one error with `code` reported AT `location`.

        Two of these codes are reachable from more than one place in this
        single fixture (`unknown_entity` fires for both the retirement and
        the form_visibility section it folds into), so the location is what
        picks out the report this line is about.
        """
        return only([f for f in errors if f.location == location], code)

    # Unknown entity, and a column the DBML does not declare.
    at(Location(Section.RETIRED_COLUMNS, entity="Widget"), FindingCode.UNKNOWN_ENTITY)
    assert "'Ghost'" in at(board, FindingCode.RETIRED_COLUMN_NOT_RENDERED).message
    # Unparseable retirement date.
    assert "'not-a-date'" in at(ops, FindingCode.RETIRED_DATE_NOT_ISO).message
    # superseded_by pointing at itself, and at nothing.
    at(ops, FindingCode.SUPERSEDED_BY_NAMES_THE_RETIRED_COLUMN)
    assert "'Nowhere'" in at(
        Location(Section.RETIRED_COLUMNS, entity="Board", column="MustFill"),
        FindingCode.SUPERSEDED_BY_NOT_RENDERED,
    ).message
    # not null with no declared default (the escalation, reported against
    # retirement rather than against a form_visibility section nobody wrote).
    assert "'MustFill'" in at(
        board, FindingCode.REQUIRED_COLUMN_HIDDEN_FROM_THE_NEW_FORM,
    ).message
    # Live formulas referencing a retired column.
    assert "[OperationsStatus]" in at(
        Location(Section.CALCULATED_FORMULAS, entity="Board", column="Route"),
        FindingCode.CALCULATED_FORMULA_REFERENCES_A_RETIRED_COLUMN,
    ).message
    at(
        Location(Section.LIST_VALIDATION, entity="Board"),
        FindingCode.LIST_VALIDATION_REFERENCES_A_RETIRED_COLUMN,
    )
    # A save rule ON a retired column: retirement hides it from the new form,
    # so is_not_null there rejects every new item with no field to satisfy
    # it. The list silently stops accepting rows.
    at(
        Location(Section.COLUMN_VALIDATION, entity="Board", column="OperationsStatus"),
        FindingCode.COLUMN_VALIDATION_ON_A_RETIRED_COLUMN,
    )

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
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.SUPERSEDED_BY_IS_ITSELF_RETIRED,
    )
    assert f.severity == "error"
    assert f.location == Location(
        Section.RETIRED_COLUMNS, entity="Board", column="OldA",
    )
    assert "'OldB'" in f.message

def test_retiring_an_undeployable_column_is_rejected(tmp_path: Path) -> None:
    """Retirement resolves into a per-column declaration, and the built-in
    Title never receives one. It is provisioned through its own patch. A
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
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.UNDEPLOYABLE_DECLARATION_COLUMN,
    )
    assert f.severity == "error"
    # Reported against retirement, which is where the author has to fix it,
    # even though the sentence belongs to the undeployable-column rule.
    assert f.location == Location(Section.RETIRED_COLUMNS, entity="Board")
    assert "'Title'" in f.message

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
    assert not by_severity(findings, "error")
    none_of(findings, FindingCode.FORM_VISIBILITY_ON_A_CALCULATED_COLUMN)
    assert "Board" not in bundle.mapping.form_visibility

def test_retired_calculated_column_without_a_formula_reports_only_root_cause(
    tmp_path: Path,
) -> None:
    """The one wrong answer the loader's calculated-column heuristic can
    give. The author declared a calculated column and forgot its formula,
    so `_apply_retirement` cannot tell it is calculated and folds it into
    form_visibility. The build must report the missing formula and NOTHING
    else. Blaming the author for a form_visibility entry they never wrote
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

    errors = by_severity(validate_against_mapping(schema, bundle), "error")
    assert len(errors) == 1, [f.message for f in errors]
    f = only(errors, FindingCode.CALCULATED_COLUMN_HAS_NO_FORMULA)
    # The mapping key the author has to add, the one thing they can act on.
    assert "calculated_formulas.Board.Route" in f.message

def test_retired_columns_warnings(tmp_path: Path) -> None:
    """Warn where a retirement mistake only wastes something. Retirement
    must never break a build: a stale view or width reference is stripped
    and reported, not rejected. A column_formatting entry on a retired
    column is KEPT deliberately. Historical values still render with their
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

    # not null WITH a default: saves succeed, the default is stamped forever.
    stamped = only(findings, FindingCode.RETIRED_COLUMN_REQUIRED_WITH_A_DEFAULT)
    assert stamped.severity == "warning"
    assert "'Stamp'" in stamped.message and "'x'" in stamped.message
    # A dead index is dead weight against a finite per-list budget.
    indexed = only(findings, FindingCode.RETIRED_COLUMN_STILL_INDEXED)
    assert "'OperationsStatus'" in indexed.message
    # Stripped view field, width and form-section references (reported,
    # never rejected). One generic loop over retirement_strips covers all
    # three under ONE code, so the declaration each one names is the only
    # thing that tells them apart and stays a message assertion.
    stripped = messages(findings, FindingCode.RETIREMENT_STRIPPED_A_DECLARATION)
    for named in (
        "views[Board].Heat grid fields",
        "views[Board].Heat grid widths",
        "form_formatting[Board].body sections",
    ):
        assert any(named in m for m in stripped), (named, stripped)
    # A view left with no fields at all.
    emptied = only(findings, FindingCode.VIEW_EMPTIED_BY_RETIREMENT)
    assert emptied.location == Location(
        Section.VIEWS, entity="Board", view="Statuses only",
    )
    # Never an error: retirement must not break a build.
    assert not by_severity(findings, "error")
    # column_formatting on a retired column is kept, not flagged: nothing is
    # reported about that section at all, and no strip names it.
    assert not [
        f for f in findings
        if f.location is not None and f.location.section is Section.COLUMN_FORMATTING
    ], findings
    assert not any("column_formatting" in m for m in stripped), stripped

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
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.RETIREMENT_WITHOUT_DISPLAY_NAMES,
    )
    assert f.severity == "warning"
    # The suffix that never reaches SharePoint, named so the author can see
    # what they are not getting.
    assert "(retired)" in f.message

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
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.RETIREMENT_STRIPPED_A_DECLARATION,
    )
    assert f.severity == "warning"
    # NOT this finding's own location, which is retired_columns[Board]: it is
    # the OTHER declaration retirement rewrote. One code covers every strip,
    # so which one it was reaches the reader only through the message.
    rewritten = "form_visibility[Board].columns"
    assert rewritten in f.message
