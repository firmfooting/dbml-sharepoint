"""Validator: declared views, and display names."""
from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _packs import blocks, entities, entity, pack, write_dbml
from _validator_helpers import _view_errors, _view_inputs

from dbml_sharepoint.analysis.validator import (
    validate_against_mapping,
)
from dbml_sharepoint.model.parser import (
    TableIndex,
    parse_dbml,
)


def test_view_on_unknown_entity_is_error(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Widget:
            - title: V
              fields: [Title]
        """,
    )
    assert any("Widget" in f.message and "views" in f.message for f in errors)

def test_view_previous_titles_cannot_collide_or_claim_all_items(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: Open
              renamed_from: [Open, All Items, Legacy]
              fields: [Title]
            - title: Closed
              renamed_from: [Legacy, Open]
              fields: [Title]
        """,
    )
    assert any("Open" in f.message and "own title" in f.message for f in errors)
    assert any("All Items" in f.message and "reserved" in f.message for f in errors)
    assert any("Legacy" in f.message and "more than one" in f.message for f in errors)
    assert any("Open" in f.message and "current title" in f.message for f in errors)

def test_view_field_references_must_be_rendered_columns(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: V
              fields: [Title, Nope]
              where:
                - { field: Missing, op: eq, value: x }
              sort:
                - { field: AlsoMissing, direction: asc }
              group_by: { field: GoneToo }
        """,
    )
    for name in ("Nope", "Missing", "AlsoMissing", "GoneToo"):
        assert any(name in f.message for f in errors), name

def test_view_operator_allowlist(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: V
              fields: [Title]
              where:
                - { field: Status, op: like, value: x }
        """,
    )
    assert any("like" in f.message and "op" in f.message.lower() for f in errors)

def test_view_condition_value_pairing(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: V
              fields: [Title]
              where:
                - { field: Status, op: is_null, value: x }
                - { field: SortOrder, op: eq }
        """,
    )
    assert any("is_null" in f.message and "value" in f.message for f in errors)
    assert any("eq" in f.message and "value" in f.message for f in errors)

def test_unindexed_view_filter_warns_with_threshold_and_fields(tmp_path: Path) -> None:
    schema, bundle = _view_inputs(
        tmp_path,
        """
        views:
          Project:
            - title: Due work
              fields: [Title, Status, DueDate]
              where:
                any_of:
                  - { field: Status, op: is_not_null }
                  - { field: DueDate, op: geq, value: today }
        """,
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
        """
        views:
          Project:
            - title: Open work
              fields: [Title, Status]
              where: [{ field: Status, op: eq, value: Open }]
            - title: Ordered work
              fields: [Title, SortOrder]
              where: [{ field: SortOrder, op: gt, value: 0 }]
        """,
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
        """
        views:
          Project:
            - title: By id
              fields: [Title, ID]
              where: [{ field: ID, op: gt, value: 100 }]
            - title: Everything
              fields: [Title]
        """,
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "view threshold" in finding.message
    ]
    assert not warnings

def test_indexed_lookup_filter_does_not_warn(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Parent", ID_PK, TITLE),
            table(
                "Child",
                ID_PK,
                TITLE,
                "Parent int [ref: > Parent.Id]",
                "indexes { Parent }",
            ),
        ),
        mapping=blocks(entities("Parent", "Child"), """
            views:
              Child:
                - title: By parent
                  fields: [Title, Parent]
                  where: [{ field: Parent, op: eq, value: 1 }]
        """),
    )
    findings = validate_against_mapping(schema, bundle)
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
    event = entity("Event", display_column=display_column) if display_column else "Event"
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Event", ID_PK, TITLE, "Label nvarchar", "Status nvarchar"),
            table("FollowUp", ID_PK, "Event int [ref: > Event.Id]"),
        ),
        mapping=blocks(entities(event, "FollowUp"), f"""
            views:
              Event:
                - title: Filtered by display
                  fields: [Title, Label, Status]
                  where: [{{ field: {filtered_column}, op: eq, value: X }}]
                - title: Filtered by other
                  fields: [Title, Label, Status]
                  where: [{{ field: Status, op: eq, value: Y }}]
        """),
    )
    findings = validate_against_mapping(schema, bundle)
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
    schema, bundle = pack(
        tmp_path,
        dbml=table("Request", ID_PK, TITLE, "RequestedBy person", "indexes { RequestedBy }"),
        mapping=blocks(entities("Request"), """
            views:
              Request:
                - title: My requests
                  fields: [Title, RequestedBy]
                  where: [{ field: RequestedBy, op: eq, value: me }]
        """),
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
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
        """
        views:
          Project:
            - title: Recently raised
              fields: [Title, Created]
              where: [{ field: Created, op: geq, value: today }]
        """,
    )
    warnings = [
        finding.message
        for finding in validate_against_mapping(schema, bundle)
        if finding.severity == "warning" and "list view threshold" in finding.message
    ]
    assert not warnings, warnings

    sys_dbml = write_dbml(
        tmp_path,
        table("Project", ID_PK, TITLE, "indexes { Created }"),
        name="sys.dbml",
    )
    with pytest.raises(ValueError, match="Created"):
        parse_dbml(sys_dbml)

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
        """
        views:
          Project:
            - title: Still open
              fields: [Title, DueDate]
              where: [{ field: DueDate, op: is_null }]
        """,
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
        """
        views:
          Project:
            - title: V
              fields: [Title, Status]
              widths:
                Title: 240
                SortOrder: 120
        """,
    )
    assert any("widths" in f.message and "SortOrder" in f.message for f in errors)
    assert not any("widths" in f.message and "'Title'" in f.message for f in errors)

def test_view_widths_pixel_bounds(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: V
              fields: [Title, Status]
              widths:
                Title: 8
                Status: 5000
        """,
    )
    assert any("widths[Title]" in f.message and "16" in f.message for f in errors)
    assert any("widths[Status]" in f.message and "2000" in f.message for f in errors)

def test_demo_items_validated(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        demo_items:
          Project:
            - key: p1
              values:
                Title: "Not marked"        # missing [DEMO] prefix
                Status: "Sideways"         # not an enum member
                Nope: 1                    # unknown column
                DueDate: "someday"         # bad date grammar
            - key: p1                      # duplicate key
              values:
                Title: "[DEMO] Ok"
                SortOrder: { demo_ref: ghost }
        """,
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
        """
        demo_items:
          Project:
            - key: p1
              values:
                Title: "[DEMO] Sample"
                Status: "Open"
                SortOrder: 3
                DueDate: "today+14"
        """,
    )
    assert not any("demo_items" in f.message for f in errors)

def test_view_url_slug_collision_is_error(tmp_path: Path) -> None:
    # "A+B" and "A B" both slug to ABApsx — two views cannot share one URL.
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: A+B
              fields: [Title]
            - title: A B
              fields: [Title]
        """,
    )
    assert any("slug" in f.message and "AB.aspx" in f.message for f in errors)

def test_view_url_slug_must_be_nonempty(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: '!!!'
              fields: [Title]
        """,
    )
    assert any("slug" in f.message and "empty" in f.message for f in errors)

@pytest.mark.parametrize("title", ["AllItems", "All-Items", "all items"])
def test_authored_views_cannot_take_the_generated_all_items_url(
    tmp_path: Path, title: str,
) -> None:
    errors = _view_errors(
        tmp_path,
        f"""
        views:
          Project:
            - title: {title}
              fields: [Title]
        """,
    )
    assert any("AllItems.aspx" in f.message for f in errors)

def test_cross_site_expansion_cannot_collide_with_declared_columns(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Unit", ID_PK),
            table(
                "Project",
                ID_PK,
                "Unit int [ref: > Unit.Id]",
                "UnitAbbreviation nvarchar",
                "UnitSiteUrl hyperlink",
            ),
        ),
        mapping=blocks(entities("Unit", "Project"), """
            cross_site_reference_columns:
              - { entity: Project, column: Unit }
        """),
    )
    findings = validate_against_mapping(schema, bundle)
    collisions = [f.message for f in findings if "collides" in f.message]
    assert any("UnitAbbreviation" in message for message in collisions)
    assert any("UnitSiteUrl" in message for message in collisions)

def test_demo_refs_and_calendar_dates_are_validated_before_generation(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Parent", ID_PK, "Title nvarchar"),
            table(
                "Task",
                ID_PK,
                "Title nvarchar",
                "Parent int [ref: > Parent.Id]",
                "Previous int [ref: > Task.Id]",
                "Note nvarchar",
                "DueDate date",
            ),
        ),
        mapping=blocks(entities("Parent", "Task"), """
            demo_items:
              Parent:
                - { key: p1, values: { Title: '[DEMO] Parent' } }
              Task:
                - key: t1
                  values:
                    Title: '[DEMO] First'
                    Previous: { demo_ref: t2 }
                    Note: { demo_ref: t1 }
                    DueDate: '2026-02-31'
                - key: t2
                  values:
                    Title: '[DEMO] Second'
                    Parent: { demo_ref: t1 }
        """),
    )
    findings = validate_against_mapping(schema, bundle)
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
        f"""
        list_validation:
          Project:
            when: [{{ field: Status, op: in, value: [{values}] }}]
            message: Too long.
        column_validation:
          Project:
            columns:
              Status:
                when: [{{ field: Status, op: in, value: [{values}] }}]
                message: Too long.
        """,
    )
    overlong = [f.message for f in errors if "1024" in f.message]
    assert any("list_validation" in message for message in overlong)
    assert any("column_validation" in message for message in overlong)

def test_view_today_sentinel_only_on_date_columns(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: V
              fields: [Title]
              where:
                - { field: SortOrder, op: leq, value: today+30 }
        """,
    )
    assert any("today" in f.message and "SortOrder" in f.message for f in errors)
    ok = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: V
              fields: [Title]
              where:
                - { field: DueDate, op: leq, value: today+30 }
        """,
    )
    assert ok == []

def test_view_titles_unique_and_single_default(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: Same
              default: true
              fields: [Title]
            - title: Same
              default: true
              fields: [Status]
        """,
    )
    assert any("duplicate" in f.message.lower() for f in errors)
    assert any("default" in f.message.lower() for f in errors)

def test_all_items_title_is_reserved_for_the_generated_unfiltered_view(
    tmp_path: Path,
) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: All Items
              fields: [Title]
              where:
                - { field: Status, op: eq, value: Open }
        """,
    )
    assert any(
        "All Items" in f.message and "generated" in f.message
        for f in errors
    ), errors

def test_view_row_limit_range(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        views:
          Project:
            - title: V
              fields: [Title]
              row_limit: 9000
        """,
    )
    assert any("row_limit" in f.message for f in errors)

# --- Display names ----------------------------------------------------------


def test_display_override_must_target_rendered_column(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        display_names:
          mode: auto
          overrides:
            Widget:
              Anything: "X"
            Project:
              Nope: "Not A Column"
        """,
    )
    assert any("Widget" in f.message and "display_names" in f.message for f in errors)
    assert any("Nope" in f.message and "display_names" in f.message for f in errors)

def test_display_names_must_be_unique_and_bounded(tmp_path: Path) -> None:
    errors = _view_errors(
        tmp_path,
        """
        display_names:
          mode: auto
          overrides:
            Project:
              Status: "Sort Order"   # collides with auto(SortOrder)
              DueDate: ""            # empty
        """,
    )
    assert any("Sort Order" in f.message and "duplicate" in f.message.lower() for f in errors)
    assert any("DueDate" in f.message and "empty" in f.message.lower() for f in errors)
