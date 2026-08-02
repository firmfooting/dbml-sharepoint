"""Validator: field sets, and the refusals a deploy cannot see."""
import ast
from pathlib import Path

from _paths import PACKAGE
from _validator_helpers import _calculated_form_inputs, _view_errors, _view_inputs

from dbml_sharepoint.analysis.validator import (
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    load_mapping,
)
from dbml_sharepoint.model.parser import (
    parse_dbml,
)

# --- Field sets -------------------------------------------------------------


def test_field_set_on_unknown_entity_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Widget:\n    header: [Title]\n",
    )
    assert any(
        "field_sets" in f.message
        and "Widget" in f.message
        and "unknown entity" in f.message
        for f in errors
    )

def test_field_set_member_must_be_a_rendered_column(tmp_path: Path) -> None:
    """The declaration message is the one that says where to fix it."""
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: [Title, Nope]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header"]\n',
    )
    assert any(
        "field_sets[Project].header" in f.message and "Nope" in f.message
        for f in errors
    )
    assert not any("'Title'" in f.message for f in errors)

def test_view_referencing_an_undeclared_field_set_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: [Title]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@headr"]\n',
    )
    assert any("@headr" in f.message and "field set" in f.message for f in errors)
    # One precise error, not that plus a confusing "not a rendered column".
    assert not any(
        "rendered column" in f.message and "headr" in f.message for f in errors
    )

def test_field_set_name_cannot_contain_the_reference_marker(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        'field_sets:\n  Project:\n    "hea@der": [Title]\n',
    )
    assert any(
        "field_sets[Project].hea@der" in f.message and "'@'" in f.message
        for f in errors
    )

def test_empty_field_set_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: []\n",
    )
    assert any(
        "field_sets[Project].header" in f.message and "empty" in f.message
        for f in errors
    )

def test_valid_field_set_produces_no_errors(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "field_sets:\n  Project:\n    header: [Title, Status]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header", DueDate]\n',
    )
    assert errors == []

def test_unreferenced_field_set_is_a_warning(tmp_path: Path) -> None:
    """Dead config wastes nothing but the reader's time, so it warns rather
    than failing the build — the fail-closed line is drawn at declarations
    that would break the list."""
    schema, bundle = _view_inputs(
        tmp_path,
        "field_sets:\n"
        "  Project:\n"
        "    header: [Title]\n"
        "    orphan: [Status]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header"]\n',
    )
    findings = validate_against_mapping(schema, bundle)
    assert any(
        f.severity == "warning"
        and "field_sets[Project].orphan" in f.message
        and "@orphan" in f.message
        for f in findings
    )
    assert not any("field_sets[Project].header" in f.message for f in findings)

def test_retired_column_in_a_field_set_is_a_warning(tmp_path: Path) -> None:
    """Expansion runs first, so the column is stripped from every view that
    pulls the set in and the strip is recorded against the VIEW. The set
    itself is where the author fixes it, so it gets its own warning naming
    the set — otherwise the only report points at a view that no longer
    mentions the column."""
    schema, bundle = _view_inputs(
        tmp_path,
        "field_sets:\n"
        "  Project:\n"
        "    header: [Title, Status]\n"
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        '      fields: ["@header"]\n'
        "retired_columns:\n"
        "  Project:\n"
        "    Status:\n"
        "      retired: 2026-09-01\n",
    )
    findings = validate_against_mapping(schema, bundle)
    assert bundle.mapping.views["Project"][0].fields == ["Title"]
    assert any(
        f.severity == "warning"
        and "field_sets[Project].header" in f.message
        and "'Status'" in f.message
        and "retired" in f.message
        for f in findings
    )
    assert not [f for f in findings if f.severity == "error"]

def test_view_formatting_may_only_read_columns_the_view_displays(tmp_path: Path) -> None:
    """SharePoint resolves a view formatter's [$Field] against the columns
    that view renders, not the list's columns — "reference to other fields
    will work only if they are included in the same view". A reference to a
    real column the view omits therefore resolves to nothing: the format
    silently never fires, the build exits 0, and the only symptom is a row
    wash nobody sees. Catching it needs the VIEW's field list, which is why
    checking against the table's columns was not enough."""
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      formatting: { additionalRowClass: \"=if([$Status] == 'Open', 'x', '')\" }\n",
    )
    assert any(
        "Status" in f.message and "V" in f.message for f in errors
    ), f"a formatter reading a column the view does not show must be refused: {errors}"

    # The same reference is fine once the view actually shows the column.
    ok = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      formatting: { additionalRowClass: \"=if([$Status] == 'Open', 'x', '')\" }\n",
    )
    assert ok == [], ok

def test_view_formatting_may_only_read_system_columns_the_view_displays(
    tmp_path: Path,
) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      formatting: { additionalRowClass: \"=if([$Created] != '', 'x', '')\" }\n",
    )
    assert any("Created" in f.message and "does not display" in f.message for f in errors), (
        f"a formatter cannot read an omitted system column: {errors}"
    )

    ok = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Created]\n"
        "      formatting: { additionalRowClass: \"=if([$Created] != '', 'x', '')\" }\n",
    )
    assert ok == [], ok

def test_a_form_header_may_not_read_a_calculated_column(tmp_path: Path) -> None:
    """A calculated column resolves to an empty string in a form header or
    footer — verified on a live tenant against a saved item that had a
    value. Nothing errors: the header renders, that one value is blank. The
    deploy cannot see it either, because the formatter saves and reads back
    byte-identical. So the build is the only place it can be caught.

    Body sections are exempt: they list field NAMES rather than reading
    values, and a calculated column placed in one renders on the Display
    form exactly as intended."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_formatting:\n"
        "  Project:\n"
        "    header: { elmType: div, txtContent: '=[$Band]' }\n",
    )
    errors = [
        f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
    ]
    assert any(
        "Band" in f.message and "calculated" in f.message.lower() for f in errors
    ), f"a header reading a calculated column must be refused: {errors}"

    # A non-calculated reference is fine, and so is the same calculated
    # column named in a body section.
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_formatting:\n"
        "  Project:\n"
        "    header: { elmType: div, txtContent: '=[$Title]' }\n"
        "    body: { sections: [ { displayname: X, fields: [Title, Band] } ] }\n",
    )
    ok = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert ok == [], ok

def test_the_calculated_type_vocabulary_is_enumerated_in_exactly_one_place() -> None:
    """No collection may re-list the three calculated DBML types.

    They belong to typemap's CALCULATED_OUTPUT_TYPES, because each needs an
    SP OutputType — a calculated type without one cannot deploy, which is
    what forces that map to stay complete and makes its keys authoritative.
    Everywhere else derives from CALCULATED_TYPES.

    A second copy is not a style problem: it is a set that can disagree
    with the first. Add a fourth calculated type and the copy is silently
    short, so every check reading it quietly stops covering the new type
    while the suite stays green.

    The rule is per-COLLECTION, not per-file. `conditions.py` legitimately
    names calculated_number in its numeric types, calculated_date in its
    date types and calculated_text in its measurable types — three
    different classifications that each happen to include one. That is not
    a copy of the vocabulary; a single literal holding all three is.
    """
    names = {"calculated_text", "calculated_number", "calculated_date"}
    src = PACKAGE
    offenders: list[str] = []
    for path in sorted(src.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Set | ast.List | ast.Tuple):
                literals = {
                    e.value for e in node.elts
                    if isinstance(e, ast.Constant) and isinstance(e.value, str)
                }
            elif isinstance(node, ast.Dict):
                literals = {
                    k.value for k in node.keys
                    if isinstance(k, ast.Constant) and isinstance(k.value, str)
                }
            else:
                continue
            if names <= literals:
                offenders.append(path.relative_to(src).as_posix())
                break
    assert offenders == ["analysis/typemap.py"], (
        f"the calculated type vocabulary is enumerated in {offenders}; it "
        f"belongs only in analysis/typemap.py, with everything else "
        f"deriving from CALCULATED_TYPES"
    )

# --- Three refusals for mistakes a deploy cannot see -------------------------
#
# A fourth was considered and NOT added: refusing a `widths` key that names a
# field the view does not display already exists above.


def test_group_by_need_not_be_one_of_the_views_own_fields(tmp_path: Path) -> None:
    """SharePoint renders the grouped value in the group HEADER, from the
    GroupBy FieldRef itself, so grouping by a column the view does not also
    list is a normal way to avoid repeating one value in every row.

    Only the weaker rule holds: the column must exist on the entity.
    """
    errors = _view_errors(
        tmp_path,
        "views:\n  Project:\n    - title: By status\n      fields: [Title]\n"
        "      group_by: { field: Status }\n",
    )
    assert not [f for f in errors if "group_by" in f.message], errors

def test_group_by_on_an_unknown_column_is_still_refused(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n  Project:\n    - title: By ghost\n      fields: [Title]\n"
        "      group_by: { field: Ghost }\n",
    )
    assert any("Ghost" in f.message for f in errors), errors

def test_group_by_in_the_views_fields_is_accepted(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: By status\n"
        "      fields: [Title, Status]\n"
        "      group_by: { field: Status }\n",
    )
    assert not [f for f in errors if "group_by" in f.message], errors

def test_a_body_section_hidden_from_every_form_is_refused(tmp_path: Path) -> None:
    """The section renders as a heading with nothing under it. Asserted of a
    NON-LAST section: Learn documents that unreferenced columns are appended
    to the last one, so only an earlier section can be provably empty."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_visibility:\n"
        "  Project:\n"
        "    columns:\n"
        "      Score: { new: false, existing: false }\n"
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Hidden, fields: [Score] }\n"
        "        - { displayname: Everything else, fields: [Title, Band] }\n",
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert any(
        "Hidden" in f.message and "bare heading" in f.message for f in errors
    ), errors

def test_the_last_section_may_be_empty_because_it_is_the_catch_all(tmp_path: Path) -> None:
    """Learn: "A column not referenced in any of the sections will be
    automatically referenced in the last section." risk-register's System
    section is exactly this shape and its DEPLOY.md documents the bare
    heading on the New form as cosmetic and expected."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_visibility:\n"
        "  Project:\n"
        "    columns:\n"
        "      Score: { new: false, existing: false }\n"
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Everything else, fields: [Title, Band] }\n"
        "        - { displayname: System, fields: [Score] }\n",
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert not [f for f in errors if "bare heading" in f.message], errors

def test_a_column_in_no_section_warns_rather_than_failing(tmp_path: Path) -> None:
    """It is drift, not breakage: SharePoint appends the column to the last
    section, so the form renders it. What is lost is the guarantee that the
    declared arrangement is the deployed one — and every column added later
    lands in that same section."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Main, fields: [Title] }\n",
    )
    findings = validate_against_mapping(schema, bundle)
    assert not [f for f in findings if f.severity == "error"], findings
    warnings = [f for f in findings if f.severity == "warning"]
    assert any("Score" in f.message and "Band" in f.message for f in warnings), warnings

def test_a_retired_column_in_no_section_does_not_warn(tmp_path: Path) -> None:
    """Retirement STRIPS a column from body sections on purpose, and warns
    separately about the declarations it rewrote. Warning again here would
    ask the author to re-add exactly what the fold just removed — which is
    what the first version of the rule did to tiered-huddle."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "retired_columns:\n"
        "  Project:\n"
        "    Score: { retired: '2026-01-01', reason: 'superseded' }\n"
        "form_formatting:\n"
        "  Project:\n"
        "    body:\n"
        "      sections:\n"
        "        - { displayname: Main, fields: [Title, Band] }\n",
    )
    findings = validate_against_mapping(schema, bundle)
    assert not [
        f for f in findings if f.severity == "warning" and "in no section" in f.message
    ], findings

def test_demo_items_on_a_document_library_are_refused(tmp_path: Path) -> None:
    """A library's items ARE files. demo-data.js posts to /items, which asks
    SharePoint to create a library row with nothing behind it.

    This built GREEN until the policy-library uplift went looking: the
    bundle would have shipped and failed at paste time, in front of whoever
    was being shown the demo — which is the audience this tool's fail-closed
    posture exists to protect.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }\n"
        "demo_items:\n"
        "  Docs:\n"
        "    - key: d1\n"
        "      values:\n"
        '        Title: "[DEMO] A document"\n',
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert any(
        "DocumentLibrary" in f.message and "SPFileCollection.Add()" in f.message
        for f in errors
    ), errors

def test_a_document_library_entity_is_refused_outright(tmp_path: Path) -> None:
    """`kind: DocumentLibrary` fails the build, with or without demo rows.

    A library's items are files and this tool writes list rows. Probed on a
    tenant (test/manual/document-library-probe.js, 2026-07-29): SharePoint
    answers a POST to a library's /items with "To add an item to a document
    library, use SPFileCollection.Add()", and an uploaded file reads back
    with `Title: null`, so the standard form header renders blank.

    Half-support — a library that provisions but carries no usable header,
    no view naming its files and no demo rows — reads as a bug in every
    direction, so the kind is refused until that work is done. The message
    must offer the way round, because an adopter hitting this needs to know
    a List plus a hyperlink column is the supported shape.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    offending = [f for f in errors if "not supported" in f.message]
    assert offending, errors
    assert "entities[Docs]" in offending[0].message
    assert "List" in offending[0].message, "the message must name the supported shape"

def test_a_list_declaring_a_non_generic_base_template_is_refused(tmp_path: Path) -> None:
    """The refusal above says "model the metadata as a 'List'". An author who
    changes only `kind` and leaves `base_template: 101` behind got a GREEN
    build that provisioned a real document library: the create body sends
    BaseTemplate and never `kind`, while every library guard in the build
    keys on `kind` and so does not fire.

    Checked as an allowlist rather than a denylist on 101. `base_template` is
    an unconstrained int taken straight from YAML, so a denylist would close
    one integer and leave 109, 119, 851 and the rest one keystroke from the
    same defect. This states what the tool builds, which needs no claim about
    SharePoint: every declaration in the repo is 100.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    for template in (101, 109, 119):
        (tmp_path / "m.yaml").write_text(
            'prefix: "APP_"\n'
            "entities:\n"
            f"  Docs: {{ kind: List, base_template: {template}, site_role: default }}\n",
            encoding="utf-8",
        )
        schema = parse_dbml(tmp_path / "s.dbml")
        bundle = load_mapping(tmp_path / "m.yaml")
        errors = [
            f for f in validate_against_mapping(schema, bundle) if f.severity == "error"
        ]
        assert any(
            "entities[Docs]" in f.message and str(template) in f.message for f in errors
        ), f"base_template {template} was accepted: {errors}"

def test_a_document_library_reports_the_kind_not_the_base_template(tmp_path: Path) -> None:
    """The two checks are one `elif`, so `kind: DocumentLibrary` with its
    matching 101 gets the message that explains the actual problem rather
    than a second one about the integer it was always going to carry."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Docs {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    about_entity = [f for f in errors if "entities[Docs]" in f.message]
    assert len(about_entity) == 1, about_entity
    assert "DocumentLibrary" in about_entity[0].message
