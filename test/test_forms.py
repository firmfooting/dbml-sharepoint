# test/test_forms.py
"""form_visibility and column_validation: parsing, composition, validation."""

from typing import cast

import pytest
from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, pack, write_mapping

from dbml_sharepoint.analysis.forms import (
    Severity,
    compose_visibility,
    validate_form_visibility,
)
from dbml_sharepoint.model.conditions import Condition, parse_condition

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
    """One slot holds both, so they must combine at build time — declaring
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


def _findings(**kwargs: object) -> list[tuple[Severity, str]]:
    base = dict(
        column="Note", new=True, existing=True, when=None, required=False,
        has_default=False, is_calculated=False, rendered={"Status", "Count", "Note"},
        types=TYPES, lookups=set(), context="form_visibility[X]",
    )
    return validate_form_visibility(**{**base, **kwargs})  # type: ignore[arg-type]


def _problems(**kwargs: object) -> list[str]:
    return [message for _, message in _findings(**kwargs)]


def test_required_and_hidden_from_new_is_an_error() -> None:
    """Statically provable: the gate is false on the New form whatever the
    condition says, so every create would fail its required check."""
    assert "every save would fail" in _problems(new=False, required=True)[0]


def test_required_with_a_default_hidden_from_new_is_fine() -> None:
    assert _problems(new=False, required=True, has_default=True) == []


def test_hidden_everywhere_with_a_condition_is_an_error() -> None:
    assert "can never be reached" in _problems(new=False, existing=False, when=WHEN)[0]


def test_calculated_columns_cannot_declare_visibility() -> None:
    assert "calculated" in _problems(is_calculated=True)[0]


def test_conditionally_hidden_required_column_is_a_warning_not_an_error() -> None:
    """The spec makes this a warning precisely because it cannot be decided
    statically. Every message came back as an "error", with the word
    "warning" buried in the prose — so the one genuinely conditional case
    the feature exists to express failed the build."""
    findings = _findings(when=WHEN, required=True)
    assert [severity for severity, _ in findings] == ["warning"]
    # And the severity is carried structurally, not spelled out in the text.
    assert "warning" not in findings[0][1]


def test_statically_provable_cases_stay_errors() -> None:
    for kwargs in (
        {"new": False, "required": True},
        {"new": False, "existing": False, "when": WHEN},
        {"is_calculated": True},
    ):
        findings = _findings(**kwargs)
        assert findings, kwargs
        assert all(severity == "error" for severity, _ in findings), kwargs


def test_condition_problems_are_reported_through_the_shared_validator() -> None:
    bad = parse_condition([{"field": "Nope", "op": "eq", "value": 1}], "w")
    assert any("not a rendered column" in p for p in _problems(when=bad))


# === Loader ================================================================

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
    declaration history — deleting an entry must revert the column."""
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

def _schema_json(tmp_path: object, section: str) -> dict[str, object]:
    from pathlib import Path

    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = pack(
        Path(str(tmp_path)),
        dbml=table("Escalation", ID_PK, TITLE, "Note nvarchar", "Other nvarchar"),
        mapping=blocks(entities("Escalation"), section),
    )
    return build_schema_json(
        schema, bundle, "default",
        site_url="https://example.sharepoint.com/sites/t",
    )


def _field(schema: dict[str, object], name: str) -> dict[str, object]:
    lists = cast("list[dict[str, object]]", schema["lists"])
    fields = cast("list[dict[str, object]]", lists[0]["fields_phase1"])
    return next(f for f in fields if f["title"] == name)


def test_undeclared_section_leaves_every_column_unmanaged(tmp_path: object) -> None:
    """No declaration must mean 'do not touch', never 'clear it' — a deploy
    that blanked formulas nobody declared would erase configuration it does
    not own."""
    from dbml_sharepoint.generators.jsgen import UNMANAGED

    schema = _schema_json(tmp_path, "")
    assert _field(schema, "Note")["client_validation_formula"] == UNMANAGED


def test_exact_clears_undeclared_columns_but_declared_wins(tmp_path: object) -> None:
    """Under exact the declaration is authoritative for the whole entity,
    so deleting an entry reverts that column on the next deploy."""
    schema = _schema_json(tmp_path, """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
    """)
    assert _field(schema, "Note")["client_validation_formula"] == "=if(false, 'true', 'false')"
    assert _field(schema, "Other")["client_validation_formula"] == ""


def test_declared_mode_leaves_undeclared_columns_alone(tmp_path: object) -> None:
    from dbml_sharepoint.generators.jsgen import UNMANAGED

    schema = _schema_json(tmp_path, """
        form_visibility:
          Escalation:
            reconcile: declared
            columns:
              Note: hidden
    """)
    assert _field(schema, "Other")["client_validation_formula"] == UNMANAGED


def test_the_sentinel_never_reaches_a_formula_position(tmp_path: object) -> None:
    """The highest-risk item in the feature: if the marker leaked, SharePoint
    would receive the literal string as a formula. The deploy script must
    compare against it, never write it."""
    from pathlib import Path

    from dbml_sharepoint.generators.jsgen import UNMANAGED, generate_deploy_js
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.parser import parse_dbml
    from dbml_sharepoint.model.release import load_release

    base = Path(str(tmp_path))
    _schema_json(tmp_path, """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
    """)
    js = generate_deploy_js(
        schema=parse_dbml(base / "s.dbml"),
        bundle=load_mapping(base / "m.yaml"),
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


def test_manifest_shows_the_composed_formula_and_reconcile_mode(tmp_path: object) -> None:
    """An operator reading the manifest should see what will be written,
    not have to infer it from a declaration two files away."""
    from pathlib import Path

    from dbml_sharepoint.generators.manifestgen import generate_manifest
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.release import load_release

    base = Path(str(tmp_path))
    schema_json = _schema_json(tmp_path, """
        form_visibility:
          Escalation:
            columns:
              Note: { new: false }
        column_validation:
          Escalation:
            columns:
              Other:
                when:
                  - { field: Other, op: is_not_null }
                message: Say something.
    """)
    manifest = generate_manifest(
        schema_json=schema_json,
        bundle=load_mapping(base / "m.yaml"),
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


def _forms_inputs(tmp_path: object, section: str) -> tuple[object, object]:
    """(schema, bundle) for a one-table fixture plus a mapping section."""
    from pathlib import Path

    # Title is deliberately NOT required here: a required column hidden from
    # the New form is already an error, which would mask the silent drop
    # this exercises.
    return pack(
        Path(str(tmp_path)),
        dbml=table(
            "Escalation", ID_PK, "Title nvarchar", "Note nvarchar", "Other nvarchar",
        ),
        mapping=blocks(entities("Escalation"), section),
    )


def _errors(tmp_path: object, section: str) -> list[str]:
    from dbml_sharepoint.analysis.validator import validate_against_mapping

    schema, bundle = _forms_inputs(tmp_path, section)
    return [
        f.message
        for f in validate_against_mapping(schema, bundle)  # type: ignore[arg-type]
        if f.severity == "error"
    ]


def test_title_form_visibility_is_rejected_not_silently_dropped(tmp_path: object) -> None:
    """jsgen routes Title through `title_patch` and continues before the
    formula keys are attached, so a declaration on it validated clean, the
    manifest reported "(none declared)", and nothing deployed. An asserted,
    validated, silently unenforced data-quality guarantee is the worst
    shape available — fail closed instead."""
    messages = _errors(
        tmp_path,
        """
        form_visibility:
          Escalation:
            columns:
              Title: hidden
        """,
    )
    assert any("Title" in m for m in messages), messages


def test_title_column_validation_is_rejected(tmp_path: object) -> None:
    messages = _errors(
        tmp_path,
        """
        column_validation:
          Escalation:
            columns:
              Title:
                when:
                  - { field: Title, measure: length, op: geq, value: 5 }
                message: Titles must be at least 5 characters.
        """,
    )
    assert any("Title" in m for m in messages), messages


def test_title_column_formatting_is_rejected(tmp_path: object) -> None:
    """The untouched sibling: the formatter is looked up from the same
    fields_phase1 loop Title never enters, so it validated clean and
    deployed nothing either."""
    messages = _errors(
        tmp_path,
        """
        column_formatting:
          Escalation:
            Title: { elmType: div }
        """,
    )
    assert any("Title" in m for m in messages), messages


def test_system_column_formatting_is_rejected(tmp_path: object) -> None:
    """System columns are not DBML columns, so they never reach
    fields_phase1 either — the validator allow-listed them and the
    generator dropped them."""
    messages = _errors(
        tmp_path,
        """
        column_formatting:
          Escalation:
            Created: { elmType: div }
        """,
    )
    assert any("Created" in m for m in messages), messages


def test_declarations_on_ordinary_columns_still_validate_clean(tmp_path: object) -> None:
    """The rejections must be scoped to columns the generator drops."""
    messages = _errors(
        tmp_path,
        """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
        column_formatting:
          Escalation:
            Other: { elmType: div }
        """,
    )
    assert messages == []


def _calculated_schema_json(tmp_path: object, section: str) -> dict[str, object]:
    """Escalation with a calculated column, plus a mapping section."""
    from pathlib import Path

    from dbml_sharepoint.generators.jsgen import build_schema_json

    schema, bundle = pack(
        Path(str(tmp_path)),
        dbml=table(
            "Escalation", ID_PK, "Title nvarchar", "Note nvarchar", "Band calculated_text",
        ),
        mapping=blocks(
            entities("Escalation"),
            """
            calculated_formulas:
              Escalation:
                Band: '=IF([Note]="","low","high")'
            """,
            section,
        ),
    )
    return build_schema_json(
        schema, bundle, "default",
        site_url="https://example.sharepoint.com/sites/t",
    )


def test_exact_reconcile_never_touches_a_calculated_column(tmp_path: object) -> None:
    """Both sections exclude calculated columns — they never reach an entry
    form, and declaring one is a build error. form_visibility carried the
    exclusion and column_validation did not, so `reconcile: exact` cleared
    a calculated column's rule. The write is a no-op, but the asymmetry is
    the hazard: two siblings disagreeing is how someone later "fixes" the
    wrong one, and meanwhile the manifest reports a clear that never
    happens."""
    from dbml_sharepoint.generators.jsgen import UNMANAGED

    schema = _calculated_schema_json(tmp_path, """
        form_visibility:
          Escalation:
            columns:
              Note: hidden
        column_validation:
          Escalation:
            columns:
              Note:
                when:
                  - { field: Note, op: is_not_null }
                message: Say something.
    """)
    band = _field(schema, "Band")
    assert band["client_validation_formula"] == UNMANAGED
    assert band["validation_formula"] == UNMANAGED
    assert band["validation_message"] == UNMANAGED
    # The ordinary column beside it is still cleared/declared as usual.
    note = _field(schema, "Note")
    assert note["validation_formula"] != UNMANAGED
