"""Validator: declared views, and display names."""
from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _findings import by_severity, codes, messages, none_of, only
from _packs import blocks, entities, entity, pack, write_dbml
from _validator_helpers import _view_errors, _view_inputs

from dbml_sharepoint.analysis.findings import FindingCode, Location, Section
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
    finding = only(errors, FindingCode.UNKNOWN_ENTITY)
    assert finding.location == Location(Section.VIEWS, entity="Widget")

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
    own = only(errors, FindingCode.PREVIOUS_TITLE_IS_OWN_TITLE)
    assert own.location == Location(
        Section.VIEWS, entity="Project", view="Open", sub="renamed_from",
    )
    reserved = only(errors, FindingCode.PREVIOUS_TITLE_IS_RESERVED)
    assert "All Items" in reserved.message
    current = only(errors, FindingCode.PREVIOUS_TITLE_IS_A_CURRENT_TITLE)
    assert current.location == Location(
        Section.VIEWS, entity="Project", view="Closed", sub="renamed_from",
    )
    # The clashing title lives only in the prose: this finding is located on
    # the view that claimed it, not on the view that owns it.
    assert "'Open'" in current.message
    # 'Open' and 'Legacy' are both claimed twice, and the entity-level finding
    # carries no view to tell the two apart.
    claimed = messages(errors, FindingCode.PREVIOUS_TITLE_CLAIMED_TWICE)
    assert len(claimed) == 2, claimed
    assert any("'Legacy'" in m for m in claimed)

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
    # fields, sort and group_by are one rule; the clause and the column it
    # names survive only in the prose, so the names are the value here.
    unrendered = messages(errors, FindingCode.COLUMN_NOT_RENDERED)
    assert len(unrendered) == 3, unrendered
    for name in ("Nope", "AlsoMissing", "GoneToo"):
        assert any(name in m for m in unrendered), name
    # `where` goes through the condition grammar, which puts the column in the
    # location instead.
    where = only(errors, FindingCode.CONDITION_FIELD_NOT_RENDERED)
    assert where.location == Location(
        Section.VIEWS, entity="Project", view="V", sub="where.Missing",
    )

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
    finding = only(errors, FindingCode.CONDITION_OPERATOR_UNKNOWN)
    assert finding.location == Location(
        Section.VIEWS, entity="Project", view="V", sub="where.Status",
    )
    assert "'like'" in finding.message

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
    surplus = only(errors, FindingCode.CONDITION_VALUE_NOT_ALLOWED)
    assert surplus.location == Location(
        Section.VIEWS, entity="Project", view="V", sub="where.Status",
    )
    assert "'is_null'" in surplus.message
    absent = only(errors, FindingCode.CONDITION_VALUE_MISSING)
    assert absent.location == Location(
        Section.VIEWS, entity="Project", view="V", sub="where.SortOrder",
    )
    assert "'eq'" in absent.message

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
    finding = only(
        validate_against_mapping(schema, bundle),
        FindingCode.UNINDEXED_FILTER_COLUMNS,
    )
    assert finding.severity == "warning"
    assert finding.location == Location(
        Section.VIEWS, entity="Project", view="Due work", sub="where",
    )
    # Which columns are exposed and what the threshold is: the two things an
    # author cannot act on without.
    assert "DueDate" in finding.message and "Status" in finding.message
    assert "5,000" in finding.message
    # One indexed condition suffices and its position is irrelevant — measured
    # at 6,000 items, both orderings of a degenerate AND served. Selectivity is
    # the caveat that survives, so the message must still carry one.
    assert "position in the filter does not matter" in finding.message
    assert "selectivity does" in finding.message
    assert "filter order" not in finding.message

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
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.UNINDEXED_FILTER_COLUMNS,
    )

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
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.UNINDEXED_FILTER_COLUMNS,
    )

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
    # No threshold warning at all: the only filter column IS indexed, and an
    # index on a Lookup counts. Asserted on the code rather than on any
    # phrasing, so a warning reintroduced under any wording fails here.
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.UNINDEXED_FILTER_COLUMNS,
    )

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
    warned_on = {
        f.location for f in findings
        if f.code == FindingCode.UNINDEXED_FILTER_COLUMNS
    }
    on_display = Location(
        Section.VIEWS, entity="Event", view="Filtered by display", sub="where",
    )
    on_other = Location(
        Section.VIEWS, entity="Event", view="Filtered by other", sub="where",
    )
    assert on_display not in warned_on, warned_on
    assert on_other in warned_on, "the check must still warn on a real gap"

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
    # An indexed Person column is a useful index. Measured at 6,000 items with
    # the person projected into the view and the join verified — see
    # _LOOKUP_FIELD_TYPES. This is the personal-work-queue idiom the template
    # library ships, and it needs no remedy.
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.UNINDEXED_FILTER_COLUMNS,
    )

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
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.UNINDEXED_FILTER_COLUMNS,
    )

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
    finding = only(
        validate_against_mapping(schema, bundle),
        FindingCode.UNINDEXED_FILTER_COLUMNS,
    )
    assert finding.severity == "warning"
    assert finding.location == Location(
        Section.VIEWS, entity="Project", view="Still open", sub="where",
    )
    assert "add a bare dbml index" in finding.message.lower()
    # The null-test remedy, not the comparison one — they differ, and a
    # null-only filter reaching the comparison branch would recommend indexing
    # "a selective filter column" when the only filter column IS the null test.
    assert "50 of 6,000" not in finding.message  # the pair is 50 of 60, not of 6,000
    assert "50 of 60" in finding.message
    assert "unverified" not in finding.message
    # The failure is silent, and the message has to say so. "May be truncated"
    # reads as a risk an author can wait to see; there is nothing to see.
    assert "no error" in finding.message

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
    # One finding, so the width on Title — a column the view DOES show — did
    # not produce one.
    finding = only(errors, FindingCode.WIDTH_COLUMN_NOT_DISPLAYED)
    assert finding.location == Location(Section.VIEWS, entity="Project", view="V")
    assert "SortOrder" in finding.message

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
    # Both bounds are on one view, so the location cannot tell the two apart:
    # the width key and the bound it broke are the values in the prose.
    out_of_range = messages(errors, FindingCode.WIDTH_OUT_OF_RANGE)
    assert len(out_of_range) == 2, out_of_range
    assert any("widths[Title]" in m and "16" in m for m in out_of_range)
    assert any("widths[Status]" in m and "2000" in m for m in out_of_range)

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
    # Six deliberate mistakes, six rules, and nothing else fires.
    assert codes(errors) == {
        FindingCode.DEMO_TITLE_MISSING_MARKER,
        FindingCode.DEMO_ENUM_VALUE_UNKNOWN,
        FindingCode.DEMO_COLUMN_NOT_WRITABLE,
        FindingCode.DEMO_DATE_VALUE_INVALID,
        FindingCode.DUPLICATE_DEMO_KEY,
        FindingCode.DEMO_REF_UNKNOWN_KEY,
    }
    # The marker itself, spelled exactly: it is what the teardown matches on.
    assert "[DEMO] " in only(errors, FindingCode.DEMO_TITLE_MISSING_MARKER).message

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
    assert [
        f for f in errors
        if f.location is not None and f.location.section == Section.DEMO_ITEMS
    ] == []

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
    assert "AB.aspx" in only(errors, FindingCode.DUPLICATE_VIEW_URL_SLUG).message

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
    finding = only(errors, FindingCode.EMPTY_VIEW_URL_SLUG)
    assert finding.location == Location(Section.VIEWS, entity="Project", view="!!!")

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
    # The generated view's own URL is the value: it is what the authored title
    # would have taken over.
    assert "AllItems.aspx" in only(errors, FindingCode.DUPLICATE_VIEW_URL_SLUG).message

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
    # One expansion, two generated names, and the finding carries no location:
    # the generated field name is the only thing that tells them apart.
    collisions = messages(findings, FindingCode.CROSS_SITE_GENERATED_NAME_COLLIDES)
    assert len(collisions) == 2, collisions
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
    errors = by_severity(validate_against_mapping(schema, bundle), "error")
    # Each location carries the demo key; the column inside that row is what
    # only the prose has.
    forward = only(errors, FindingCode.DEMO_REF_FORWARD_REFERENCE)
    assert forward.location == Location(Section.DEMO_ITEMS, entity="Task", sub="t1")
    assert "Previous" in forward.message
    non_lookup = only(errors, FindingCode.DEMO_REF_ON_NON_LOOKUP)
    assert "Note" in non_lookup.message
    mismatch = only(errors, FindingCode.DEMO_REF_TARGET_MISMATCH)
    assert mismatch.location == Location(Section.DEMO_ITEMS, entity="Task", sub="t2")
    assert "Parent" in mismatch.message
    bad_date = only(errors, FindingCode.DEMO_DATE_VALUE_INVALID)
    assert "2026-02-31" in bad_date.message

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
    list_level = only(errors, FindingCode.LIST_VALIDATION_FORMULA_TOO_LONG)
    assert list_level.location == Location(Section.LIST_VALIDATION, entity="Project")
    # The limit is the number the author has to write the formula under.
    assert "1024" in list_level.message
    column_level = only(errors, FindingCode.VALIDATION_FORMULA_TOO_LONG)
    assert column_level.location == Location(
        Section.COLUMN_VALIDATION, entity="Project", column="Status",
    )

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
    finding = only(errors, FindingCode.CONDITION_VALUE_NOT_A_NUMBER)
    assert finding.location == Location(
        Section.VIEWS, entity="Project", view="V", sub="where.SortOrder",
    )
    assert "'today+30'" in finding.message
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
    none_of(ok, FindingCode.CONDITION_VALUE_NOT_A_NUMBER)

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
    assert "'Same'" in only(errors, FindingCode.DUPLICATE_VIEW_TITLE).message
    only(errors, FindingCode.MULTIPLE_DEFAULT_VIEWS)

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
    finding = only(errors, FindingCode.ALL_ITEMS_VIEW_DECLARED)
    assert finding.location == Location(Section.VIEWS, entity="Project")

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
    finding = only(errors, FindingCode.ROW_LIMIT_OUT_OF_RANGE)
    assert finding.location == Location(Section.VIEWS, entity="Project", view="V")

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
    # Both rules are shared with `views:`; the section in the location is what
    # says these two came from display_names.
    unknown = only(errors, FindingCode.UNKNOWN_ENTITY)
    assert unknown.location == Location(Section.DISPLAY_NAMES, entity="Widget")
    unrendered = only(errors, FindingCode.COLUMN_NOT_RENDERED)
    assert unrendered.location == Location(Section.DISPLAY_NAMES, entity="Project")
    assert "Nope" in unrendered.message

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
    # The colliding title and the column that resolved to nothing: neither is
    # in the location, which is the whole entity.
    assert "'Sort Order'" in only(errors, FindingCode.DUPLICATE_DISPLAY_TITLE).message
    assert "'DueDate'" in only(errors, FindingCode.EMPTY_DISPLAY_TITLE).message
