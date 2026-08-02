"""Validator: declared view totals."""
from pathlib import Path

from _validator_helpers import _calculated_form_inputs, _view_errors

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    MappingBundle,
    load_mapping,
)
from dbml_sharepoint.model.parser import (
    Schema,
    parse_dbml,
)

# --- Declared view totals ---------------------------------------------------


def test_a_total_on_a_column_the_view_does_not_show_is_refused(tmp_path: Path) -> None:
    """The widths failure shape exactly: SharePoint accepts the property and
    renders nothing, because the view has no column to put a figure under."""
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      totals: { SortOrder: sum }\n",
    )
    assert any("SortOrder" in f.message and "totals" in f.message for f in errors), errors

def test_summing_a_choice_column_is_refused_and_points_at_count(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      totals: { Status: sum }\n",
    )
    assert any(
        "Status" in f.message and "count" in f.message for f in errors
    ), errors

def test_counting_a_choice_column_is_allowed(tmp_path: Path) -> None:
    """count counts ROWS, not values, so it is legal on any displayed
    column — which is why it is excluded from the numeric-only set rather
    than sharing the numeric rule."""
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      totals: { Status: count }\n",
    )
    assert not [f for f in errors if "totals" in f.message], errors

def test_summing_a_numeric_column_is_allowed(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, SortOrder]\n"
        "      totals: { SortOrder: sum }\n",
    )
    assert not [f for f in errors if "totals" in f.message], errors

def test_a_total_on_a_calculated_number_is_allowed(tmp_path: Path) -> None:
    """Three of the columns this feature exists for are calculated
    day-counts. The `string;#` prefix that complicates calculated TEXT is a
    column-formatting concern and never reaches a view's Aggregations."""
    schema, bundle = _calculated_form_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Score]\n"
        "      totals: { Score: avg }\n",
    )
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    assert not [f for f in errors if "totals" in f.message], errors

def _hyperlink_demo(tmp_path: Path, value: str) -> list[Finding]:
    """A whole build's worth of validation, not `_field_plan` alone: the
    demo planner and the demo VALIDATOR are separate readers of the same
    authored value, and a form one accepts and the other refuses never
    reaches generation."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Doc {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Link hyperlink\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Doc: { kind: List, base_template: 100, site_role: default }\n"
        "demo_items:\n"
        "  Doc:\n"
        "    - key: d1\n"
        "      values:\n"
        '        Title: "[DEMO] A row"\n'
        f"        Link: {value}\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    return [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]

def test_a_hyperlink_demo_value_may_be_a_bare_url(tmp_path: Path) -> None:
    assert not _hyperlink_demo(tmp_path, '"https://example.invalid/a.pdf"')

def test_a_hyperlink_demo_value_may_carry_a_description(tmp_path: Path) -> None:
    """The object form the demo planner accepts. The validator must accept
    it too — it reads every dict, and a lookup reference is not the only
    thing that is one."""
    assert not _hyperlink_demo(
        tmp_path, '{ url: "https://example.invalid/a.pdf", description: "The file" }',
    )

def test_a_hyperlink_demo_object_needs_a_url(tmp_path: Path) -> None:
    errors = _hyperlink_demo(tmp_path, '{ description: "no address" }')
    assert any("url" in f.message for f in errors), errors

def test_a_hyperlink_demo_object_refuses_unknown_keys(tmp_path: Path) -> None:
    errors = _hyperlink_demo(
        tmp_path, '{ url: "https://example.invalid/a.pdf", label: "wrong key" }',
    )
    assert any("label" in f.message for f in errors), errors

def test_a_null_hyperlink_url_is_refused(tmp_path: Path) -> None:
    """`str(None)` is "None" — non-empty, and a perfectly valid-looking
    string. A coerced emptiness test passes it through to become a link
    pointing at the word None, so the check is on the STRING, not on its
    stringification."""
    errors = _hyperlink_demo(tmp_path, "{ url: null }")
    assert any("non-empty string" in f.message for f in errors), errors

def test_an_empty_hyperlink_url_is_refused(tmp_path: Path) -> None:
    errors = _hyperlink_demo(tmp_path, '{ url: "   " }')
    assert any("non-empty string" in f.message for f in errors), errors

def test_a_scalar_hyperlink_demo_value_is_validated_too(tmp_path: Path) -> None:
    """A URL column takes a bare address as well as a record. Checking only
    the record shape left `Link: null` and `Link: 123` unvalidated — and the
    generator refuses both, so the build surfaced a traceback instead of a
    finding. A validator must refuse everything its generator refuses."""
    for bad in ("null", "123", '""'):
        errors = _hyperlink_demo(tmp_path, bad)
        assert any("non-empty string" in f.message for f in errors), (bad, errors)

def test_names_that_differ_only_in_case_are_refused(tmp_path: Path) -> None:
    """SharePoint resolves group, permission-level and view names
    case-insensitively and will not hold two that differ only in case. A
    build that permits both produces a deploy that creates the first and
    collides on the second, mid-run, after the site has already changed.

    Caught here so the collision is a build error rather than a half-applied
    paste.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "permission_levels:\n"
        '  - { name: "APP Reader", description: "d", base_permissions: [ViewListItems] }\n'
        '  - { name: "app reader", description: "d", base_permissions: [ViewListItems] }\n'
        "groups:\n"
        '  - { name: "APP Owners", description: "d", owner_group: "Site Owners" }\n'
        '  - { name: "app owners", description: "d", owner_group: "Site Owners" }\n'
        "views:\n"
        "  Project:\n"
        "    - { title: Open, fields: [Title], default: true }\n"
        "    - { title: open, fields: [Title] }\n",
        encoding="utf-8",
    )
    schema, bundle = parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
    errors = [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
    for what in ("permission_levels", "groups", "views"):
        assert any(
            f.message.startswith(what) and "case" in f.message for f in errors
        ), (what, [f.message for f in errors])

def test_a_lookup_targets_display_column_counts_as_an_index(tmp_path: Path) -> None:
    """The picker's index is real and spends a real slot, so the ceiling must
    see it. Declaring 20 and needing a 21st has to fail at validate time, not at
    deploy time on someone's tenant."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Status nvarchar\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default }\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    vc = ValidationContext.build(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert "Title" in vc.effective_indexes("Event")
    # The child is not a target of anything.
    assert vc.effective_indexes("FollowUp") == set()

def _cross_site_only_target(tmp_path: Path, *, calculated: bool) -> tuple[Schema, MappingBundle]:
    """FlowRunLog is pointed at by exactly one ref, and that ref is cross-site."""
    display = "  Label calculated_text\n" if calculated else "  Label nvarchar\n"
    formulas = (
        "calculated_formulas:\n  FlowRunLog:\n    Label: \"=[Title]\"\n"
        if calculated else ""
    )
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table FlowRunLog {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        + display +
        "}\n"
        "Table Request {\n"
        "  Id int [pk, increment]\n"
        "  Origin int [ref: > FlowRunLog.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  FlowRunLog: { kind: List, base_template: 100, site_role: default, "
        "display_column: Label }\n"
        "  Request: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Request, column: Origin }\n"
        + formulas,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")

def test_a_cross_site_only_target_spends_no_index(tmp_path: Path) -> None:
    """A cross-site ref becomes a Choice + URL pair on the SOURCE list. Nothing
    enumerates FlowRunLog, so it has no picker — charging it an index would spend
    one of its twenty on a query that never happens."""
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    schema, bundle = _cross_site_only_target(tmp_path, calculated=False)
    vc = ValidationContext.build(schema, bundle)
    assert vc.effective_indexes("FlowRunLog") == set()

def test_a_cross_site_only_target_is_not_told_its_picker_breaks(
    tmp_path: Path,
) -> None:
    """The warning claims 'this list's lookup picker stops working'. Said about a
    list with no picker it is simply false, and the author's only way to silence
    it is to accept a consequence that cannot occur."""
    schema, bundle = _cross_site_only_target(tmp_path, calculated=True)
    assert not [
        f for f in validate_against_mapping(schema, bundle)
        if "display_column" in f.message and "FlowRunLog" in f.message
    ], [f.message for f in validate_against_mapping(schema, bundle)]

def test_a_target_of_both_ref_kinds_keeps_its_index(tmp_path: Path) -> None:
    """Per-pair, not per-entity. Excluding every entity NAMED in
    cross_site_reference_columns would strip the index off a list whose picker is
    real, which is the same defect pointing the other way."""
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table FlowRunLog {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "}\n"
        "Table Request {\n"
        "  Id int [pk, increment]\n"
        "  Origin int [ref: > FlowRunLog.Id]\n"
        "}\n"
        "Table Alert {\n"
        "  Id int [pk, increment]\n"
        "  Source int [ref: > FlowRunLog.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  FlowRunLog: { kind: List, base_template: 100, site_role: default }\n"
        "  Request: { kind: List, base_template: 100, site_role: default }\n"
        "  Alert: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Request, column: Origin }\n",
        encoding="utf-8",
    )
    vc = ValidationContext.build(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert vc.effective_indexes("FlowRunLog") == {"Title"}

def test_a_calculated_display_column_does_not_count_as_an_index(tmp_path: Path) -> None:
    """It cannot be indexed, so counting it would push a schema over the ceiling
    for an index that cannot exist — the failure mode in the other direction."""
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Ref nvarchar\n"
        "  Label calculated_text\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: Label }\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n",
        encoding="utf-8",
    )
    from dbml_sharepoint.analysis.checks._context import ValidationContext

    vc = ValidationContext.build(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    assert "Label" not in vc.effective_indexes("Event")

_SHAPE_SCHEMA = (
    "Project t { database_type: 'SharePoint Online' }\n"
    "Table Job {\n"
    "  Id int [pk, increment]\n"
    "  Title nvarchar\n"
    "  Status nvarchar\n"
    "  DueDate date\n"
    "  indexes { Status }\n"
    "}\n"
)

def _shape_warnings(tmp_path: Path, where: str) -> list[str]:
    (tmp_path / "s.dbml").write_text(_SHAPE_SCHEMA, encoding="utf-8")
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Job: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Job:\n"
        "    - title: V\n"
        "      fields: [Title, Status, DueDate]\n" + where,
        encoding="utf-8",
    )
    return [
        f.message
        for f in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if "list view threshold" in f.message
    ]

def test_an_or_needs_every_branch_indexed(tmp_path: Path) -> None:
    """An OR cannot narrow to one index. A row matching only the unindexed
    branch is still a row SharePoint has to find, so an indexed branch beside
    an unindexed one buys nothing — and scoring it safe because SOME filtered
    column is indexed is how a scanning view passes validation."""
    assert len(_shape_warnings(
        tmp_path,
        "      where:\n"
        "        any_of:\n"
        "          - { field: Status, op: eq, value: Open }\n"
        "          - { field: DueDate, op: leq, value: today }\n",
    )) == 1

def test_an_or_with_every_branch_indexed_is_quiet(tmp_path: Path) -> None:
    """Both branches narrow, so neither forces a scan."""
    assert _shape_warnings(
        tmp_path,
        "      where:\n"
        "        any_of:\n"
        "          - { field: Status, op: eq, value: Open }\n"
        "          - { field: Status, op: eq, value: Held }\n",
    ) == []

def test_an_and_needs_only_one_branch_indexed(tmp_path: Path) -> None:
    """Measured at 6,000 items: an unindexed comparison refused on its own is
    served when ANDed with an indexed one, in either order — SharePoint picks
    the index rather than taking the first column and stopping. So an AND is
    covered by one indexed condition wherever it sits, and this test is what
    stops the OR rule above being applied to both."""
    assert _shape_warnings(
        tmp_path,
        "      where:\n"
        "        - { field: Status, op: eq, value: Open }\n"
        "        - { field: DueDate, op: leq, value: today }\n",
    ) == []
