"""Validator: declared views, and display names."""
from pathlib import Path

import pytest
from _validator_helpers import _view_errors, _view_inputs

from dbml_sharepoint.analysis.validator import (
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    load_mapping,
)
from dbml_sharepoint.model.parser import (
    TableIndex,
    parse_dbml,
)


def test_view_on_unknown_entity_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n  Widget:\n    - title: V\n      fields: [Title]\n",
    )
    assert any("Widget" in f.message and "views" in f.message for f in errors)

def test_view_previous_titles_cannot_collide_or_claim_all_items(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Open\n"
        "      renamed_from: [Open, All Items, Legacy]\n"
        "      fields: [Title]\n"
        "    - title: Closed\n"
        "      renamed_from: [Legacy, Open]\n"
        "      fields: [Title]\n",
    )
    assert any("Open" in f.message and "own title" in f.message for f in errors)
    assert any("All Items" in f.message and "reserved" in f.message for f in errors)
    assert any("Legacy" in f.message and "more than one" in f.message for f in errors)
    assert any("Open" in f.message and "current title" in f.message for f in errors)

def test_view_field_references_must_be_rendered_columns(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Nope]\n"
        "      where:\n"
        "        - { field: Missing, op: eq, value: x }\n"
        "      sort:\n"
        "        - { field: AlsoMissing, direction: asc }\n"
        "      group_by: { field: GoneToo }\n",
    )
    for name in ("Nope", "Missing", "AlsoMissing", "GoneToo"):
        assert any(name in f.message for f in errors), name

def test_view_operator_allowlist(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: Status, op: like, value: x }\n",
    )
    assert any("like" in f.message and "op" in f.message.lower() for f in errors)

def test_view_condition_value_pairing(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: Status, op: is_null, value: x }\n"
        "        - { field: SortOrder, op: eq }\n",
    )
    assert any("is_null" in f.message and "value" in f.message for f in errors)
    assert any("eq" in f.message and "value" in f.message for f in errors)

def test_unindexed_view_filter_warns_with_threshold_and_fields(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Due work\n"
        "      fields: [Title, Status, DueDate]\n"
        "      where:\n"
        "        any_of:\n"
        "          - { field: Status, op: is_not_null }\n"
        "          - { field: DueDate, op: geq, value: today }\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "effective index" in finding.message
    ]
    assert len(warnings) == 1
    assert "Due work" in warnings[0]
    assert "DueDate" in warnings[0] and "Status" in warnings[0]
    assert "5,000" in warnings[0]
    # One indexed condition suffices and its position is irrelevant — measured
    # at 6,000 items, both orderings of a degenerate AND served. Selectivity is
    # the caveat that survives, so the message must still carry one.
    assert "position in the filter does not matter" in warnings[0]
    assert "selectivity does" in warnings[0]
    assert "filter order" not in warnings[0]

def test_explicit_or_unique_filter_index_clears_warning(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Open work\n"
        "      fields: [Title, Status]\n"
        "      where: [{ field: Status, op: eq, value: Open }]\n"
        "    - title: Ordered work\n"
        "      fields: [Title, SortOrder]\n"
        "      where: [{ field: SortOrder, op: gt, value: 0 }]\n",
    )
    table = schema.tables[0]
    table.indexes.append(TableIndex(("Status",)))
    next(column for column in table.columns if column.name == "SortOrder").unique = True
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "view threshold" in finding.message
    ]
    assert not warnings

def test_native_id_filter_and_view_without_filter_do_not_warn(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: By id\n"
        "      fields: [Title, ID]\n"
        "      where: [{ field: ID, op: gt, value: 100 }]\n"
        "    - title: Everything\n"
        "      fields: [Title]\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "view threshold" in finding.message
    ]
    assert not warnings

def test_indexed_lookup_filter_does_not_warn(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Parent {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "}\n"
        "Table Child {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Parent int [ref: > Parent.Id]\n"
        "  indexes { Parent }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Parent: { kind: List, base_template: 100, site_role: default }\n"
        "  Child: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Child:\n"
        "    - title: By parent\n"
        "      fields: [Title, Parent]\n"
        "      where: [{ field: Parent, op: eq, value: 1 }]\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"),
        load_mapping(tmp_path / "m.yaml"),
    )
    # No threshold warning at all: the only filter column IS indexed, and an
    # index on a Lookup counts. Asserted over every threshold finding rather
    # than the old "indexed filter" phrasing, so a warning reintroduced under
    # any wording fails here.
    warnings = [
        finding.message
        for finding in findings
        if finding.severity == "warning"
        and "list view threshold" in finding.message
    ]
    assert warnings == []

@pytest.mark.parametrize(
    "display_column",
    [None, "Label"],
    ids=["default_title", "declared_display_column"],
)
def test_view_filtered_on_lookup_targets_display_column_does_not_warn(
    tmp_path: Path, display_column: str | None,
) -> None:
    """Locks in what Task 2 exists to produce: a lookup target's display
    column carries an implicit index (a picker past the 5,000-item threshold
    needs it — see analysis/lookups.py), so THIS check — which only ever
    reads `vc.effective_indexes` — must score a view on the TARGET entity
    that filters on that column as safe, even with no explicit `indexes {}`
    entry naming it. Parameterised over the default display column (Title,
    when the mapping declares nothing) and an explicit `display_column`,
    because Task 2 folds both in the same way.

    Filtering on a different, non-display, unindexed column on the same
    entity must still warn — proving the check still fires at all, so a bug
    that silenced it completely could not pass the first half vacuously.
    """
    filtered_column = display_column or "Title"
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Event {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Label nvarchar\n"
        "  Status nvarchar\n"
        "}\n"
        "Table FollowUp {\n"
        "  Id int [pk, increment]\n"
        "  Event int [ref: > Event.Id]\n"
        "}\n",
        encoding="utf-8",
    )
    display_clause = f", display_column: {display_column}" if display_column else ""
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        f"  Event: {{ kind: List, base_template: 100, site_role: default"
        f"{display_clause} }}\n"
        "  FollowUp: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Event:\n"
        "    - title: Filtered by display\n"
        "      fields: [Title, Label, Status]\n"
        f"      where: [{{ field: {filtered_column}, op: eq, value: X }}]\n"
        "    - title: Filtered by other\n"
        "      fields: [Title, Label, Status]\n"
        "      where: [{ field: Status, op: eq, value: Y }]\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    threshold_warnings = [
        f.message for f in findings
        if f.severity == "warning" and "list view threshold" in f.message
    ]
    display_warnings = [
        m for m in threshold_warnings if "views[Event].Filtered by display" in m
    ]
    other_warnings = [
        m for m in threshold_warnings if "views[Event].Filtered by other" in m
    ]
    assert display_warnings == [], display_warnings
    assert other_warnings != [], "the check must still warn on a real gap"

def test_indexed_person_filter_does_not_warn(tmp_path: Path) -> None:
    """An indexed Person column counts as a useful index.

    Microsoft classifies Person or Group (single value) as a lookup field and
    documents that indexing one does not avert the threshold. Measured at 6,000
    items with the person projected into the view and the join verified, the
    query was served — see _LOOKUP_FIELD_TYPES for the full evidence and the
    one-line revert.
    """
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Request {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  RequestedBy person\n"
        "  indexes { RequestedBy }\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Request: { kind: List, base_template: 100, site_role: default }\n"
        "views:\n"
        "  Request:\n"
        "    - title: My requests\n"
        "      fields: [Title, RequestedBy]\n"
        "      where: [{ field: RequestedBy, op: eq, value: me }]\n",
        encoding="utf-8",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(
            parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
        )
        if finding.severity == "warning"
        and "list view threshold" in finding.message
    ]
    # An indexed Person column is a useful index. Measured at 6,000 items with
    # the person projected into the view and the join verified — see
    # _LOOKUP_FIELD_TYPES. This is the personal-work-queue idiom the template
    # library ships, and it needs no remedy.
    assert warnings == []

def test_system_column_filter_is_not_warned_about(tmp_path: Path) -> None:
    """A warning must name a remedy the author can carry out. `Created` is
    filterable but not declarable, so there is no index to add — pydbml
    refuses the declaration outright, which the second half asserts so the
    reason for the silence cannot quietly stop being true."""
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Recently raised\n"
        "      fields: [Title, Created]\n"
        "      where: [{ field: Created, op: geq, value: today }]\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "list view threshold" in finding.message
    ]
    assert not warnings, warnings

    (tmp_path / "sys.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  indexes { Created }\n"
        "}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Created"):
        parse_dbml(tmp_path / "sys.dbml")

def test_null_only_filter_recommends_an_index(tmp_path: Path) -> None:
    """The library's "blank means still open" idiom. Measured on a matched pair
    at 6,000 items by test/manual/threshold-index-probe.js: the indexed column
    returned all 60 expected rows, the unindexed one returned 50 of 60 with
    HTTP 200 and no error. So the warning names the index as the remedy.

    The message must carry the SILENCE, not just the risk. An author who reads
    "may be truncated" will ship it and wait for the error; there is no error,
    and the view is wrong from the day it is deployed."""
    schema, bundle = _view_inputs(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Still open\n"
        "      fields: [Title, DueDate]\n"
        "      where: [{ field: DueDate, op: is_null }]\n",
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "list view threshold" in finding.message
    ]
    assert len(warnings) == 1
    assert "Still open" in warnings[0]
    assert "add a bare dbml index" in warnings[0].lower()
    # The null-test remedy, not the comparison one — they differ, and a
    # null-only filter reaching the comparison branch would recommend indexing
    # "a selective filter column" when the only filter column IS the null test.
    assert "50 of 6,000" not in warnings[0]  # the pair is 50 of 60, not of 6,000
    assert "50 of 60" in warnings[0]
    assert "unverified" not in warnings[0]
    # The failure is silent, and the message has to say so. "May be truncated"
    # reads as a risk an author can wait to see; there is nothing to see.
    assert "no error" in warnings[0]

def test_view_widths_keys_must_be_view_fields(tmp_path: Path) -> None:
    # SortOrder IS a rendered column, but a width on a column the view does
    # not show is dead config — error, not silence.
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      widths:\n"
        "        Title: 240\n"
        "        SortOrder: 120\n",
    )
    assert any("widths" in f.message and "SortOrder" in f.message for f in errors)
    assert not any("widths" in f.message and "'Title'" in f.message for f in errors)

def test_view_widths_pixel_bounds(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title, Status]\n"
        "      widths:\n"
        "        Title: 8\n"
        "        Status: 5000\n",
    )
    assert any("widths[Title]" in f.message and "16" in f.message for f in errors)
    assert any("widths[Status]" in f.message and "2000" in f.message for f in errors)

def test_demo_items_validated(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "demo_items:\n"
        "  Project:\n"
        "    - key: p1\n"
        "      values:\n"
        '        Title: "Not marked"\n'          # missing [DEMO] prefix
        '        Status: "Sideways"\n'           # not an enum member
        "        Nope: 1\n"                      # unknown column
        '        DueDate: "someday"\n'           # bad date grammar
        "    - key: p1\n"                        # duplicate key
        "      values:\n"
        '        Title: "[DEMO] Ok"\n'
        "        SortOrder: { demo_ref: ghost }\n",
    )
    assert any("[DEMO] " in f.message and "Title" in f.message for f in errors)
    assert any("Sideways" in f.message and "status" in f.message for f in errors)
    assert any("Nope" in f.message and "writable" in f.message for f in errors)
    assert any("DueDate" in f.message and "today" in f.message for f in errors)
    assert any("duplicate demo key" in f.message for f in errors)
    assert any("ghost" in f.message for f in errors)

def test_demo_items_valid_set_passes(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "demo_items:\n"
        "  Project:\n"
        "    - key: p1\n"
        "      values:\n"
        '        Title: "[DEMO] Sample"\n'
        '        Status: "Open"\n'
        "        SortOrder: 3\n"
        '        DueDate: "today+14"\n',
    )
    assert not any("demo_items" in f.message for f in errors)

def test_view_url_slug_collision_is_error(tmp_path: Path) -> None:
    # "A+B" and "A B" both slug to ABApsx — two views cannot share one URL.
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: A+B\n"
        "      fields: [Title]\n"
        "    - title: A B\n"
        "      fields: [Title]\n",
    )
    assert any("slug" in f.message and "AB.aspx" in f.message for f in errors)

def test_view_url_slug_must_be_nonempty(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: '!!!'\n"
        "      fields: [Title]\n",
    )
    assert any("slug" in f.message and "empty" in f.message for f in errors)

@pytest.mark.parametrize("title", ["AllItems", "All-Items", "all items"])
def test_authored_views_cannot_take_the_generated_all_items_url(
    tmp_path: Path, title: str,
) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        f"    - title: {title}\n"
        "      fields: [Title]\n",
    )
    assert any("AllItems.aspx" in f.message for f in errors)

def test_cross_site_expansion_cannot_collide_with_declared_columns(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Unit {\n"
        "  Id int [pk, increment]\n"
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Unit int [ref: > Unit.Id]\n"
        "  UnitAbbreviation nvarchar\n"
        "  UnitSiteUrl hyperlink\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Unit: { kind: List, base_template: 100, site_role: default }\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "cross_site_reference_columns:\n"
        "  - { entity: Project, column: Unit }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    collisions = [f.message for f in findings if "collides" in f.message]
    assert any("UnitAbbreviation" in message for message in collisions)
    assert any("UnitSiteUrl" in message for message in collisions)

def test_demo_refs_and_calendar_dates_are_validated_before_generation(tmp_path: Path) -> None:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Parent {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "}\n"
        "Table Task {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar\n"
        "  Parent int [ref: > Parent.Id]\n"
        "  Previous int [ref: > Task.Id]\n"
        "  Note nvarchar\n"
        "  DueDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Parent: { kind: List, base_template: 100, site_role: default }\n"
        "  Task: { kind: List, base_template: 100, site_role: default }\n"
        "demo_items:\n"
        "  Parent:\n"
        "    - { key: p1, values: { Title: '[DEMO] Parent' } }\n"
        "  Task:\n"
        "    - key: t1\n"
        "      values:\n"
        "        Title: '[DEMO] First'\n"
        "        Previous: { demo_ref: t2 }\n"
        "        Note: { demo_ref: t1 }\n"
        "        DueDate: '2026-02-31'\n"
        "    - key: t2\n"
        "      values:\n"
        "        Title: '[DEMO] Second'\n"
        "        Parent: { demo_ref: t1 }\n",
        encoding="utf-8",
    )
    findings = validate_against_mapping(
        parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml"),
    )
    errors = [f.message for f in findings if f.severity == "error"]
    assert any("Previous" in message and "before" in message for message in errors)
    assert any("Note" in message and "lookup" in message for message in errors)
    assert any(
        "Parent" in message and "Task" in message and "targets" in message
        for message in errors
    )
    assert any("2026-02-31" in message and "calendar" in message for message in errors)

def test_rendered_validation_formula_length_is_checked(tmp_path: Path) -> None:
    values = ", ".join(f"'value-{i}-{'x' * 40}'" for i in range(24))
    errors = _view_errors(
        tmp_path,
        "list_validation:\n"
        "  Project:\n"
        f"    when: [{{ field: Status, op: in, value: [{values}] }}]\n"
        "    message: Too long.\n"
        "column_validation:\n"
        "  Project:\n"
        "    columns:\n"
        "      Status:\n"
        f"        when: [{{ field: Status, op: in, value: [{values}] }}]\n"
        "        message: Too long.\n",
    )
    overlong = [f.message for f in errors if "1024" in f.message]
    assert any("list_validation" in message for message in overlong)
    assert any("column_validation" in message for message in overlong)

def test_view_today_sentinel_only_on_date_columns(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: SortOrder, op: leq, value: today+30 }\n",
    )
    assert any("today" in f.message and "SortOrder" in f.message for f in errors)
    ok = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: DueDate, op: leq, value: today+30 }\n",
    )
    assert ok == []

def test_view_titles_unique_and_single_default(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: Same\n"
        "      default: true\n"
        "      fields: [Title]\n"
        "    - title: Same\n"
        "      default: true\n"
        "      fields: [Status]\n",
    )
    assert any("duplicate" in f.message.lower() for f in errors)
    assert any("default" in f.message.lower() for f in errors)

def test_all_items_title_is_reserved_for_the_generated_unfiltered_view(
    tmp_path: Path,
) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: All Items\n"
        "      fields: [Title]\n"
        "      where:\n"
        "        - { field: Status, op: eq, value: Open }\n",
    )
    assert any(
        "All Items" in f.message and "generated" in f.message
        for f in errors
    ), errors

def test_view_row_limit_range(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "views:\n"
        "  Project:\n"
        "    - title: V\n"
        "      fields: [Title]\n"
        "      row_limit: 9000\n",
    )
    assert any("row_limit" in f.message for f in errors)

# --- Display names ----------------------------------------------------------


def test_display_override_must_target_rendered_column(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "display_names:\n"
        "  mode: auto\n"
        "  overrides:\n"
        "    Widget:\n"
        '      Anything: "X"\n'
        "    Project:\n"
        '      Nope: "Not A Column"\n',
    )
    assert any("Widget" in f.message and "display_names" in f.message for f in errors)
    assert any("Nope" in f.message and "display_names" in f.message for f in errors)

def test_display_names_must_be_unique_and_bounded(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        "display_names:\n"
        "  mode: auto\n"
        "  overrides:\n"
        "    Project:\n"
        '      Status: "Sort Order"\n'   # collides with auto(SortOrder)
        '      DueDate: ""\n',           # empty
    )
    assert any("Sort Order" in f.message and "duplicate" in f.message.lower() for f in errors)
    assert any("DueDate" in f.message and "empty" in f.message.lower() for f in errors)
