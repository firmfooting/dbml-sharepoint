# test/test_forms.py
"""form_visibility and column_validation: parsing, composition, validation."""

from typing import Unpack, cast

import pytest
from _findings import only
from _model import MappingSections
from _model import bundle as make_bundle
from _model import column as make_column
from _model import enum as make_enum
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, entities, write_mapping

from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.forms import compose_visibility, validate_form_visibility
from dbml_sharepoint.model.conditions import Condition, parse_condition
from dbml_sharepoint.model.mapping_types import (
    ColumnValidation,
    EntitySection,
    FormVisibility,
    MappingBundle,
)
from dbml_sharepoint.model.parser import Schema

TYPES = {"Status": "nvarchar", "Count": "number", "Note": "nvarchar"}
WHEN = parse_condition([{"field": "Status", "op": "eq", "value": "Resolved"}], "w")


def _compose(new: bool = True, existing: bool = True, when: Condition | None = None) -> str:
    return compose_visibility(new=new, existing=existing, when=when, types=TYPES)


def test_nothing_declared_clears_the_formula() -> None:
    assert _compose() == ""


def test_hidden_at_creation_only() -> None:
    """The case the whole feature exists for: absent from New, editable
    afterwards. [$ID] is empty on the New form and populated after."""
    assert _compose(new=False) == "=if([$ID] != '', 'true', 'false')"


def test_hidden_after_creation_only() -> None:
    assert _compose(existing=False) == "=if([$ID] == '', 'true', 'false')"


def test_hidden_everywhere() -> None:
    assert _compose(new=False, existing=False) == "=if(false, 'true', 'false')"


def test_condition_only() -> None:
    assert _compose(when=WHEN) == "=if([$Status] == 'Resolved', 'true', 'false')"


def test_gate_and_condition_compose_rather_than_replace() -> None:
    """One slot holds both, so they must combine at build time. Declaring
    one would otherwise silently destroy the other."""
    assert _compose(new=False, when=WHEN) == (
        "=if([$ID] != '' && ([$Status] == 'Resolved'), 'true', 'false')"
    )


def test_composition_uses_operators_not_functions() -> None:
    """Verified live: the conditional-formula dialog rejects and()/or()."""
    rendered = _compose(new=False, when=WHEN)
    assert "&&" in rendered
    assert "and(" not in rendered


def test_condition_is_parenthesised_inside_the_gate() -> None:
    """Without the parentheses, an or-condition would bind loosely and the
    gate would apply to only its first arm."""
    disjunction = parse_condition(
        {"any_of": [
            {"field": "Status", "op": "eq", "value": "A"},
            {"field": "Status", "op": "eq", "value": "B"},
        ]},
        "w",
    )
    assert _compose(new=False, when=disjunction) == (
        "=if([$ID] != '' && (([$Status] == 'A' || [$Status] == 'B')), 'true', 'false')"
    )


#: Where the declaration under test lives. `form_visibility[X]` is what the
#: helper used to pass as a bare context string; the path is now derived.
AT = Location(Section.FORM_VISIBILITY, entity="X")


def _findings(
    *,
    column: str = "Note",
    new: bool = True,
    existing: bool = True,
    when: Condition | None = None,
    required: bool = False,
    has_default: bool = False,
    is_calculated: bool = False,
) -> list[Finding]:
    """One column's declaration, defaulted to the harmless case.

    Spelled out rather than `**kwargs: object` so mypy checks the call. The
    old helper needed a `type: ignore[arg-type]` to hand a `dict[str, object]`
    to a keyword-only signature, which is exactly the untyped boundary the
    surrounding work exists to close.
    """
    return validate_form_visibility(
        column=column,
        new=new,
        existing=existing,
        when=when,
        required=required,
        has_default=has_default,
        is_calculated=is_calculated,
        rendered={"Status", "Count", "Note"},
        types=TYPES,
        lookups=set(),
        enum_members={},
        at=AT,
    )


def test_required_and_hidden_from_new_is_an_error() -> None:
    """Statically provable: the gate is false on the New form whatever the
    condition says, so every create would fail its required check."""
    found = _findings(new=False, required=True)[0]
    assert found.code is FindingCode.REQUIRED_COLUMN_HIDDEN_FROM_THE_NEW_FORM
    assert "every save would fail" in found.message


def test_required_with_a_default_hidden_from_new_is_fine() -> None:
    assert _findings(new=False, required=True, has_default=True) == []


def test_hidden_everywhere_with_a_condition_is_an_error() -> None:
    found = _findings(new=False, existing=False, when=WHEN)[0]
    assert found.code is FindingCode.FORM_VISIBILITY_CONDITION_UNREACHABLE
    assert "can never be reached" in found.message


def test_calculated_columns_cannot_declare_visibility() -> None:
    found = _findings(is_calculated=True)[0]
    assert found.code is FindingCode.FORM_VISIBILITY_ON_A_CALCULATED_COLUMN
    assert "calculated" in found.message


def test_conditionally_hidden_required_column_is_a_warning_not_an_error() -> None:
    """The spec makes this a warning precisely because it cannot be decided
    statically. Every message came back as an "error", with the word
    "warning" buried in the prose, so the one genuinely conditional case
    the feature exists to express failed the build."""
    findings = _findings(when=WHEN, required=True)
    assert [f.severity for f in findings] == ["warning"]
    assert findings[0].code is FindingCode.REQUIRED_COLUMN_MAY_BE_HIDDEN_AT_CREATION
    # And the severity is carried structurally, not spelled out in the text.
    assert "warning" not in findings[0].message


def test_statically_provable_cases_stay_errors() -> None:
    for findings in (
        _findings(new=False, required=True),
        _findings(new=False, existing=False, when=WHEN),
        _findings(is_calculated=True),
    ):
        assert findings
        assert all(f.severity == "error" for f in findings), findings


def test_each_rule_here_has_its_own_code() -> None:
    """The reason this function returns Findings rather than
    (severity, message) pairs. The caller cannot know which of the five
    rules fired, so one code assigned there would collapse all of them,
    and a rule with no code of its own can never be asserted on, or
    suppressed, or looked up in the catalogue.
    """
    codes = [
        _findings(is_calculated=True)[0].code,
        _findings(new=False, existing=False, when=WHEN)[0].code,
        _findings(new=False, required=True)[0].code,
        _findings(when=WHEN, required=True)[0].code,
        _findings(when=parse_condition(
            [{"field": "Nope", "op": "eq", "value": 1}], "w",
        ))[0].code,
    ]
    assert len(set(codes)) == len(codes), codes


def test_form_visibility_refuses_a_multi_value_operand() -> None:
    """Documented, and the comment in `conditions.py` that anticipated this
    said so: Microsoft lists "Choice with multiple selections" among the
    column types conditional show/hide cannot read. That comment closed with
    "None of them has a DBML type in this tool, so there is nothing here to
    reject -- the omission is considered, not missed", which stopped being
    true the day `enum_name[]` resolved.

    This is the target where being wrong is worst. The formula stays
    SYNTACTICALLY valid, so it saves, the read-back compares equal and the
    deploy phase passes -- a green build, a green manifest, and a form that
    never reacts.
    https://learn.microsoft.com/sharepoint/dev/declarative-customization/list-form-conditional-show-hide
    """
    findings = validate_form_visibility(
        column="Note",
        new=True,
        existing=True,
        when=parse_condition([{"field": "Events", "op": "eq", "value": "View"}], "w"),
        required=False,
        has_default=False,
        is_calculated=False,
        rendered={"Note", "Events"},
        types={"Note": "nvarchar", "Events": "audit_event[]"},
        lookups=set(),
        enum_members={"audit_event": ("View", "Edit", "Export")},
        at=AT,
    )

    found = only(findings, FindingCode.MULTI_VALUE_OPERAND_UNSUPPORTED)
    assert found.severity == "error"
    assert "Events" in found.message
    assert found.location == Location(
        Section.FORM_VISIBILITY, entity="X", column="Note", sub="when.Events",
    )


def test_column_validation_refuses_a_multi_value_operand() -> None:
    """Measured 2026-08-10, not inferred: SharePoint refused the
    ValidationFormula outright -- HTTP 500, "This field type does not support
    validation formulas."

    A loud failure rather than a silent one, which is the good outcome. The
    build-time refusal still belongs here, because it turns a failed deploy
    -- part-way through a paste, in front of an operator -- into a failed
    build. That is the same argument the hyperlink operand carries beside it.
    """
    from dbml_sharepoint.analysis.validator import validate_against_mapping

    schema = make_schema(
        make_table(
            "Platform",
            make_column("Title"),
            make_column("Events", "audit_event[]"),
        ),
        enums=[make_enum("audit_event", "View", "Edit", "Export")],
    )
    bundle = make_bundle(
        entities=["Platform"],
        column_validation={"Platform": EntitySection(columns={
            "Events": ColumnValidation(
                when=parse_condition(
                    [{"field": "Events", "op": "eq", "value": "View"}],
                    "column_validation",
                ),
                message="Say what is logged.",
            ),
        })},
    )

    found = only(
        validate_against_mapping(schema, bundle),
        FindingCode.MULTI_VALUE_OPERAND_UNSUPPORTED,
    )
    assert found.severity == "error"
    assert found.location == Location(
        Section.COLUMN_VALIDATION,
        entity="Platform",
        column="Events",
        sub="when.Events",
    )


def test_form_and_column_validation_refuse_unknown_choice_members() -> None:
    from dbml_sharepoint.analysis.validator import validate_against_mapping

    schema = make_schema(
        make_table(
            "Escalation",
            make_column("Title", required=True),
            make_column("Status", "status"),
            make_column("Note"),
        ),
        enums=[make_enum("status", "Open", "Closed")],
    )
    typo = parse_condition(
        [{"field": "Status", "op": "eq", "value": "Opne"}], "when",
    )
    bundle = make_bundle(
        entities=["Escalation"],
        form_visibility={
            "Escalation": EntitySection(columns={
                "Note": FormVisibility(when=typo),
            }),
        },
        column_validation={
            "Escalation": EntitySection(columns={
                "Status": ColumnValidation(when=typo, message="Choose a status."),
            }),
        },
    )

    findings = validate_against_mapping(schema, bundle)
    member_findings = [
        finding
        for finding in findings
        if finding.code is FindingCode.CONDITION_CHOICE_MEMBER_UNKNOWN
    ]

    assert {finding.location for finding in member_findings} == {
        Location(
            Section.FORM_VISIBILITY,
            entity="Escalation",
            column="Note",
            sub="when.Status",
        ),
        Location(
            Section.COLUMN_VALIDATION,
            entity="Escalation",
            column="Status",
            sub="when.Status",
        ),
    }


def _caml_findings(op: str) -> list[Finding]:
    from dbml_sharepoint.analysis.condition_rendering import CAML
    from dbml_sharepoint.analysis.conditions import condition_findings

    return condition_findings(
        parse_condition([{"field": "Events", "op": op, "value": "View"}], "w"),
        target=CAML,
        rendered={"Events"},
        types={"Events": "audit_event[]"},
        lookups=set(),
        enum_members={"audit_event": ("View", "Edit", "Export")},
        at=AT,
    )


def test_a_view_filter_still_accepts_a_multi_value_operand() -> None:
    """The refusal is per TARGET, and CAML is not one of them.

    Measured 2026-08-10 across two runs: `<Eq>` against a single member does
    the membership test and returns the rows containing it, `<Neq>` returns
    the rows without it plus the empty ones, and the predicate survives being
    stored as a view's ViewQuery. Refusing here would remove a filter
    SharePoint demonstrably serves -- an enforced rule must never be stronger
    than what the reference implementation satisfies.

    Written with `eq` when this guard was minted, because `eq` was then the
    only way to say it. It is `includes` now: S6 gave membership its own
    operator so the word could not mean equality on one column and containment
    on another. The GUARD is unchanged and is the point -- one target, one
    measured predicate, no finding.
    """
    assert _caml_findings("includes") == []


def test_the_membership_spelling_is_the_only_one_a_view_filter_takes() -> None:
    """The other side of the guard above, so neither can drift alone.

    Without this, deleting the arity check would leave the test above passing
    on a grammar where `eq` and `includes` both rendered `<Eq>` and meant
    different things depending on a `[]` nobody can see in a mapping.
    """
    found = only(_caml_findings("eq"), FindingCode.MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED)

    assert found.severity == "error"
    assert "includes" in found.message


def test_condition_problems_are_reported_through_the_shared_validator() -> None:
    bad = parse_condition([{"field": "Nope", "op": "eq", "value": 1}], "w")
    findings = _findings(when=bad)
    # The condition grammar classifies its own problems, so the leaf's fault
    # keeps its identity instead of arriving as "the when is bad".
    f = only(findings, FindingCode.CONDITION_FIELD_NOT_RENDERED)
    assert f.location == Location(
        Section.FORM_VISIBILITY, entity="X", column="Note", sub="when.Nope",
    )


# === Loader ================================================================
#
# Everything from here to the next banner stays on the filesystem: each of
# these tests IS about the YAML -- a shorthand string, a defaulted key, or a
# refusal `load_mapping` raises. There is no object to build; the text is the
# subject.

def _load(tmp_path: object, section: str) -> object:
    from pathlib import Path

    from dbml_sharepoint.model.mapping_loader import load_mapping

    base = Path(str(tmp_path))
    # `section` is a top-level YAML section, so it dedents flush like the
    # entities block it follows and `blocks` can take both.
    return load_mapping(
        write_mapping(base, blocks(entities("Escalation"), section)),
    ).mapping


def test_shorthand_strings_parse(tmp_path: object) -> None:
    mapping = _load(tmp_path, """
        form_visibility:
          Escalation:
            columns:
              Route: hidden
              Note: visible
    """)
    columns = mapping.form_visibility["Escalation"].columns  # type: ignore[attr-defined]
    assert (columns["Route"].new, columns["Route"].existing) == (False, False)
    assert (columns["Note"].new, columns["Note"].existing) == (True, True)


def test_reconcile_defaults_to_exact(tmp_path: object) -> None:
    """Deployed state should be a function of the declaration, not of
    declaration history. Deleting an entry must revert the column."""
    mapping = _load(tmp_path, """
        form_visibility:
          Escalation:
            columns:
              Route: hidden
    """)
    assert mapping.form_visibility["Escalation"].reconcile == "exact"  # type: ignore[attr-defined]


def test_column_validation_requires_both_when_and_message(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="'message' is required"):
        _load(tmp_path, """
            column_validation:
              Escalation:
                columns:
                  Note:
                    when:
                      - { field: Note, op: is_not_null }
        """)


def test_unknown_keys_are_rejected_in_both_sections(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="unknown key"):
        _load(tmp_path, """
            form_visibility:
              Escalation:
                columns:
                  Note: { new: false, edit: false }
        """)


def test_bad_reconcile_mode_is_rejected(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="'exact' or 'declared'"):
        _load(tmp_path, """
            form_visibility:
              Escalation:
                reconcile: sometimes
                columns: {}
        """)


def test_removed_sections_fail_loudly(tmp_path: object) -> None:
    """The loader ignores unknown top-level keys, so deleting these
    silently would leave a mapping that builds clean and quietly makes
    every declared column visible."""
    for removed in ("hidden_on_forms", "hidden_on_display"):
        with pytest.raises(ValueError, match=f"{removed!r} has been replaced"):
            _load(tmp_path, f"{removed}:\n  Escalation: [Note]\n")


def test_list_validation_formula_key_names_its_replacement(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="'formula' has been replaced by 'when'"):
        _load(tmp_path, """
            list_validation:
              Escalation:
                formula: '=TRUE'
                message: nope
        """)


# === Regressions from the second adversarial review ========================

def test_boolean_flags_reject_quoted_yaml(tmp_path: object) -> None:
    """bool("false") is True, so a quoted boolean meant its opposite: the
    author writing `new: "false"` to hide a column got it shown."""
    for value in ('"false"', "'no'", '"0"'):
        with pytest.raises(ValueError, match="expected true or false"):
            _load(tmp_path, (
                "form_visibility:\n  Escalation:\n    columns:\n"
                f"      Note: {{ new: {value} }}\n"
            ))


def test_empty_when_is_an_error_not_an_absence(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="empty"):
        _load(tmp_path, """
            form_visibility:
              Escalation:
                columns:
                  Note: { new: false, when: [] }
        """)


# === Deploy-side: the sentinel and reconcile modes ==========================

def _escalation(**sections: Unpack[MappingSections]) -> tuple[Schema, MappingBundle]:
    """The four-column `Escalation` fixture, plus whatever the test declares."""
    schema = make_schema(make_table(
        "Escalation",
        make_column("Title", required=True),
        make_column("Note"),
        make_column("Other"),
    ))
    return schema, make_bundle(entities=["Escalation"], **sections)


def _visibility(
    columns: dict[str, FormVisibility], reconcile: str = "exact",
) -> dict[str, EntitySection[FormVisibility]]:
    return {"Escalation": EntitySection(reconcile=reconcile, columns=columns)}


#: The `hidden` shorthand, which the loader expands to both flags off.
HIDDEN = FormVisibility(new=False, existing=False)


def _schema_json(**sections: Unpack[MappingSections]) -> dict[str, object]:
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = _escalation(**sections)
    return build_schema_json(
        schema, bundle, "default",
        site_url="https://example.sharepoint.com/sites/t",
    )


def _field(schema: dict[str, object], name: str) -> dict[str, object]:
    lists = cast("list[dict[str, object]]", schema["lists"])
    fields = cast("list[dict[str, object]]", lists[0]["fields_phase1"])
    return next(f for f in fields if f["title"] == name)


def test_undeclared_section_leaves_every_column_unmanaged() -> None:
    """No declaration must mean 'do not touch', never 'clear it'. A deploy
    that blanked formulas nobody declared would erase configuration it does
    not own."""
    from dbml_sharepoint.generators.jsgen import UNMANAGED

    schema = _schema_json()
    assert _field(schema, "Note")["client_validation_formula"] == UNMANAGED


def test_exact_clears_undeclared_columns_but_declared_wins() -> None:
    """Under exact the declaration is authoritative for the whole entity,
    so deleting an entry reverts that column on the next deploy."""
    schema = _schema_json(form_visibility=_visibility({"Note": HIDDEN}))
    assert _field(schema, "Note")["client_validation_formula"] == "=if(false, 'true', 'false')"
    assert _field(schema, "Other")["client_validation_formula"] == ""


def test_declared_mode_leaves_undeclared_columns_alone() -> None:
    from dbml_sharepoint.generators.jsgen import UNMANAGED

    schema = _schema_json(
        form_visibility=_visibility({"Note": HIDDEN}, reconcile="declared"),
    )
    assert _field(schema, "Other")["client_validation_formula"] == UNMANAGED


def test_the_sentinel_never_reaches_a_formula_position() -> None:
    """The highest-risk item in the feature: if the marker leaked, SharePoint
    would receive the literal string as a formula. The deploy script must
    compare against it, never write it."""
    from pathlib import Path

    from dbml_sharepoint.generators.jsgen import UNMANAGED, generate_deploy_js
    from dbml_sharepoint.model.release import load_release

    schema, bundle = _escalation(form_visibility=_visibility({"Note": HIDDEN}))
    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(Path("test/fixtures") / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/t",
        site_role="default", source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z", generated_at="2026-05-04T00:00:00Z",
    )
    # It appears as the comparison constant and as data, never assigned into
    # ClientValidationFormula or ValidationFormula.
    assert f'const UNMANAGED = "{UNMANAGED}"' in js
    assert f'"ClientValidationFormula": "{UNMANAGED}"' not in js
    assert f'"ValidationFormula": "{UNMANAGED}"' not in js
    # And the SchemaXml writer that provokes the unrepairable FieldLink
    # migration is gone, not merely unreachable.
    assert "setshowinnewform" not in js
    assert "enforceFormVisibility" not in js


def test_manifest_shows_the_composed_formula_and_reconcile_mode() -> None:
    """An operator reading the manifest should see what will be written,
    not have to infer it from a declaration two files away."""
    from pathlib import Path

    from dbml_sharepoint.generators.manifestgen import generate_manifest
    from dbml_sharepoint.model.release import load_release

    declared: MappingSections = {
        "form_visibility": _visibility({"Note": FormVisibility(new=False)}),
        "column_validation": {"Escalation": EntitySection(columns={
            "Other": ColumnValidation(
                when=parse_condition(
                    [{"field": "Other", "op": "is_not_null"}], "column_validation",
                ),
                message="Say something.",
            ),
        })},
    }
    schema_json = _schema_json(**declared)
    _, bundle = _escalation(**declared)
    manifest = generate_manifest(
        schema_json=schema_json,
        bundle=bundle,
        release=load_release(Path("test/fixtures") / "release.yaml"),
        findings=[],
        site_url="https://example.sharepoint.com/sites/t",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "## Form visibility" in manifest
    assert "=if([$ID] != '', 'true', 'false')" in manifest
    assert "`exact`" in manifest
    assert "## Column validation" in manifest
    assert "Say something." in manifest
    # Undeclared columns under exact are shown as cleared, so the operator
    # can see what the deploy will remove rather than discovering it live.
    assert "cleared" in manifest


# --- Title and system columns -----------------------------------------------


def _errors(**sections: Unpack[MappingSections]) -> list[str]:
    """Error messages for the `Escalation` fixture with a NULLABLE Title.

    Title is deliberately not required here: a required column hidden from
    the New form is already an error, which would mask the silent drop these
    exercise. `_escalation` makes it required, so this builds its own.

    The table-level `note` is here for the same masking reason: without one
    `ENTITY_HAS_NO_NOTE` is an error on every call, and the tests that assert
    `_errors(...) == []` would stop saying anything about form declarations.
    It is unrelated to the column that happens to be called `Note`.
    """
    from dbml_sharepoint.analysis.validator import validate_against_mapping

    schema = make_schema(make_table(
        "Escalation", make_column("Title"), make_column("Note"), make_column("Other"),
        note="The fixture escalation list.",
    ))
    bundle = make_bundle(entities=["Escalation"], **sections)
    return [
        f.message
        for f in validate_against_mapping(schema, bundle)
        if f.severity == "error"
    ]


def test_title_form_visibility_is_rejected_not_silently_dropped() -> None:
    """jsgen routes Title through `title_patch` and continues before the
    formula keys are attached, so a declaration on it validated clean, the
    manifest reported "(none declared)", and nothing deployed. An asserted,
    validated, silently unenforced data-quality guarantee is the worst
    shape available. Fail closed instead."""
    messages = _errors(form_visibility=_visibility({"Title": HIDDEN}))
    assert any("Title" in m for m in messages), messages


def test_title_column_validation_is_rejected() -> None:
    messages = _errors(column_validation={"Escalation": EntitySection(columns={
        "Title": ColumnValidation(
            when=parse_condition(
                [{"field": "Title", "measure": "length", "op": "geq", "value": 5}],
                "column_validation",
            ),
            message="Titles must be at least 5 characters.",
        ),
    })})
    assert any("Title" in m for m in messages), messages


def test_title_column_formatting_is_rejected() -> None:
    """The untouched sibling: the formatter is looked up from the same
    fields_phase1 loop Title never enters, so it validated clean and
    deployed nothing either."""
    messages = _errors(
        column_formatting={"Escalation": {"Title": {"elmType": "div"}}},
    )
    assert any("Title" in m for m in messages), messages


def test_system_column_formatting_is_rejected() -> None:
    """System columns are not DBML columns, so they never reach
    fields_phase1 either. The validator allow-listed them and the
    generator dropped them."""
    messages = _errors(
        column_formatting={"Escalation": {"Created": {"elmType": "div"}}},
    )
    assert any("Created" in m for m in messages), messages


def test_declarations_on_ordinary_columns_still_validate_clean() -> None:
    """The rejections must be scoped to columns the generator drops."""
    messages = _errors(
        form_visibility=_visibility({"Note": HIDDEN}),
        column_formatting={"Escalation": {"Other": {"elmType": "div"}}},
    )
    assert messages == []


def _calculated_schema_json(**sections: Unpack[MappingSections]) -> dict[str, object]:
    """Escalation with a calculated column, plus a mapping section."""
    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema = make_schema(make_table(
        "Escalation",
        make_column("Title"),
        make_column("Note"),
        make_column("Band", "calculated_text"),
    ))
    declared: MappingSections = {
        "calculated_formulas": {"Escalation": {"Band": '=IF([Note]="","low","high")'}},
    }
    declared.update(sections)
    return build_schema_json(
        schema, make_bundle(entities=["Escalation"], **declared), "default",
        site_url="https://example.sharepoint.com/sites/t",
    )


def test_exact_reconcile_never_touches_a_calculated_column() -> None:
    """Both sections exclude calculated columns. They never reach an entry
    form, and declaring one is a build error. form_visibility carried the
    exclusion and column_validation did not, so `reconcile: exact` cleared
    a calculated column's rule. The write is a no-op, but the asymmetry is
    the hazard: two siblings disagreeing is how someone later "fixes" the
    wrong one, and meanwhile the manifest reports a clear that never
    happens."""
    from dbml_sharepoint.generators.jsgen import UNMANAGED

    schema = _calculated_schema_json(
        form_visibility=_visibility({"Note": HIDDEN}),
        column_validation={"Escalation": EntitySection(columns={
            "Note": ColumnValidation(
                when=parse_condition(
                    [{"field": "Note", "op": "is_not_null"}], "column_validation",
                ),
                message="Say something.",
            ),
        })},
    )
    band = _field(schema, "Band")
    assert band["client_validation_formula"] == UNMANAGED
    assert band["validation_formula"] == UNMANAGED
    assert band["validation_message"] == UNMANAGED
    # The ordinary column beside it is still cleared/declared as usual.
    note = _field(schema, "Note")
    assert note["validation_formula"] != UNMANAGED
