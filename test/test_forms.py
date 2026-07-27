# test/test_forms.py
"""form_visibility and column_validation: parsing, composition, validation."""

from typing import cast

import pytest

from dbml_sharepoint.analysis.forms import compose_visibility, validate_form_visibility
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


def _problems(**kwargs: object) -> list[str]:
    base = dict(
        column="Note", new=True, existing=True, when=None, required=False,
        has_default=False, is_calculated=False, rendered={"Status", "Count", "Note"},
        types=TYPES, lookups=set(), context="form_visibility[X]",
    )
    return validate_form_visibility(**{**base, **kwargs})  # type: ignore[arg-type]


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


def test_condition_problems_are_reported_through_the_shared_validator() -> None:
    bad = parse_condition([{"field": "Nope", "op": "eq", "value": 1}], "w")
    assert any("not a rendered column" in p for p in _problems(when=bad))


# === Loader ================================================================

def _load(tmp_path: object, section: str) -> object:
    from pathlib import Path

    from dbml_sharepoint.model.mapping_loader import load_mapping

    base = Path(str(tmp_path))
    (base / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Escalation: { kind: List, base_template: 100, site_role: default }\n" + section,
        encoding="utf-8",
    )
    return load_mapping(base / "m.yaml").mapping


def test_shorthand_strings_parse(tmp_path: object) -> None:
    mapping = _load(tmp_path, (
        "form_visibility:\n"
        "  Escalation:\n"
        "    columns:\n"
        "      Route: hidden\n"
        "      Note: visible\n"
    ))
    columns = mapping.form_visibility["Escalation"].columns  # type: ignore[attr-defined]
    assert (columns["Route"].new, columns["Route"].existing) == (False, False)
    assert (columns["Note"].new, columns["Note"].existing) == (True, True)


def test_reconcile_defaults_to_exact(tmp_path: object) -> None:
    """Deployed state should be a function of the declaration, not of
    declaration history — deleting an entry must revert the column."""
    mapping = _load(tmp_path, (
        "form_visibility:\n  Escalation:\n    columns:\n      Route: hidden\n"
    ))
    assert mapping.form_visibility["Escalation"].reconcile == "exact"  # type: ignore[attr-defined]


def test_column_validation_requires_both_when_and_message(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="'message' is required"):
        _load(tmp_path, (
            "column_validation:\n"
            "  Escalation:\n"
            "    columns:\n"
            "      Note:\n"
            "        when:\n"
            "          - { field: Note, op: is_not_null }\n"
        ))


def test_unknown_keys_are_rejected_in_both_sections(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="unknown key"):
        _load(tmp_path, (
            "form_visibility:\n"
            "  Escalation:\n"
            "    columns:\n"
            "      Note: { new: false, edit: false }\n"
        ))


def test_bad_reconcile_mode_is_rejected(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="'exact' or 'declared'"):
        _load(tmp_path, (
            "form_visibility:\n  Escalation:\n    reconcile: sometimes\n    columns: {}\n"
        ))


def test_removed_sections_fail_loudly(tmp_path: object) -> None:
    """The loader ignores unknown top-level keys, so deleting these
    silently would leave a mapping that builds clean and quietly makes
    every declared column visible."""
    for removed in ("hidden_on_forms", "hidden_on_display"):
        with pytest.raises(ValueError, match=f"{removed!r} has been replaced"):
            _load(tmp_path, f"{removed}:\n  Escalation: [Note]\n")


def test_list_validation_formula_key_names_its_replacement(tmp_path: object) -> None:
    with pytest.raises(ValueError, match="'formula' has been replaced by 'when'"):
        _load(tmp_path, (
            "list_validation:\n"
            "  Escalation:\n"
            "    formula: '=TRUE'\n"
            "    message: nope\n"
        ))


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
        _load(tmp_path, (
            "form_visibility:\n  Escalation:\n    columns:\n"
            "      Note: { new: false, when: [] }\n"
        ))


# === Deploy-side: the sentinel and reconcile modes ==========================

def _schema_json(tmp_path: object, section: str) -> dict[str, object]:
    from pathlib import Path

    from dbml_sharepoint.generators.jsgen import build_schema_json
    from dbml_sharepoint.model.mapping_loader import load_mapping
    from dbml_sharepoint.model.parser import parse_dbml

    base = Path(str(tmp_path))
    (base / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Escalation {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Note nvarchar\n"
        "  Other nvarchar\n"
        "}\n",
        encoding="utf-8",
    )
    (base / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Escalation: { kind: List, base_template: 100, site_role: default }\n" + section,
        encoding="utf-8",
    )
    return build_schema_json(
        parse_dbml(base / "s.dbml"), load_mapping(base / "m.yaml"), "default",
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
    schema = _schema_json(tmp_path, (
        "form_visibility:\n"
        "  Escalation:\n"
        "    columns:\n"
        "      Note: hidden\n"
    ))
    assert _field(schema, "Note")["client_validation_formula"] == "=if(false, 'true', 'false')"
    assert _field(schema, "Other")["client_validation_formula"] == ""


def test_declared_mode_leaves_undeclared_columns_alone(tmp_path: object) -> None:
    from dbml_sharepoint.generators.jsgen import UNMANAGED

    schema = _schema_json(tmp_path, (
        "form_visibility:\n"
        "  Escalation:\n"
        "    reconcile: declared\n"
        "    columns:\n"
        "      Note: hidden\n"
    ))
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
    _schema_json(tmp_path, "form_visibility:\n  Escalation:\n    columns:\n      Note: hidden\n")
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
    schema_json = _schema_json(tmp_path, (
        "form_visibility:\n"
        "  Escalation:\n"
        "    columns:\n"
        "      Note: { new: false }\n"
        "column_validation:\n"
        "  Escalation:\n"
        "    columns:\n"
        "      Other:\n"
        "        when:\n"
        "          - { field: Other, op: is_not_null }\n"
        "        message: Say something.\n"
    ))
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
