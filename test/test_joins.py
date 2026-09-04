# test/test_joins.py
from _model import bundle as make_bundle
from _model import column as make_column
from _model import person as make_person
from _model import ref as make_ref
from _model import table as make_table

from dbml_sharepoint.analysis.joins import (
    JOIN_LIMIT,
    JOIN_WARN_AT,
    SYSTEM_JOIN_COLUMNS,
    all_items_hidden,
    join_bearing_columns,
    joining_fields,
)
from dbml_sharepoint.analysis.typemap import JOIN_BEARING_TYPES
from dbml_sharepoint.model.mapping_types import CrossSiteRef, EntityMapping, MappingBundle
from dbml_sharepoint.model.parser import Table


def _task() -> tuple[Table, MappingBundle]:
    """A `Task` carrying one of every column shape these derivations sort.

    `Notes` and `DueDate` are the free ones, `Owner` and `Assignee` bear
    joins, and `Elsewhere` is a ref that does NOT because it is declared
    cross-site. `Title` is nullable: nothing here is about the schema rules.
    """
    task = make_table(
        "Task",
        make_column("Title"),
        make_person("Owner"),
        make_ref("Assignee", "Person.Id"),
        make_ref("Elsewhere", "Person.Id"),
        make_column("Notes"),
        make_column("DueDate", "date"),
    )
    bundle = make_bundle(
        entities={
            "Person": EntityMapping(
                name="Person", kind="List", base_template=100, site_role="default",
            ),
            "Task": EntityMapping(
                name="Task", kind="List", base_template=100, site_role="default",
                hide_from_all_items=("Author", "Editor"),
            ),
        },
        cross_site_reference_columns=[CrossSiteRef(entity="Task", column="Elsewhere")],
    )
    return task, bundle


def test_the_bands_are_eleven_and_twelve() -> None:
    """The last two assertions are the GUARD ON THE DERIVATION, not a second
    copy of it. SYSTEM_JOIN_COLUMNS is computed from SYSTEM_COLUMN_TYPES, so
    these pin what that computation must come out as: Created and Modified are
    absent because they are `datetime`, and that row of the rule is INFERRED
    rather than measured. Widen JOIN_BEARING_TYPES and this fails, which is the
    point.

    Written `sorted(X) == [...]` rather than `X == frozenset({...})` because
    ruff reads an uppercase name as the constant side and flags the latter
    SIM300 'Yoda condition detected'."""
    assert JOIN_WARN_AT == 11
    assert JOIN_LIMIT == 12
    assert sorted(SYSTEM_JOIN_COLUMNS) == ["Author", "Editor"]
    assert sorted(JOIN_BEARING_TYPES) == ["person"]


def test_refs_person_columns_and_the_two_system_columns_bear_joins() -> None:
    table, _ = _task()
    assert join_bearing_columns(table, {"Elsewhere"}) == {
        "Owner", "Assignee", "Author", "Editor",
    }


def test_a_multi_value_choice_bears_no_join() -> None:
    """THE claim that made MultiChoice the cheap multi-value type, checked
    against `joins.py` rather than assumed -- and this is the assertion that
    keeps it true.

    `join_bearing_columns` counts a column when it has a `ref` or its type is
    in JOIN_BEARING_TYPES, which is `{"person"}`. A multi-value Choice is
    enum-typed and has neither, so it costs no join: it touches neither the
    12-join view ceiling nor the list view threshold, and no change to the
    join model is needed for it.

    That is a fact about arity NOT mattering here, which is why it is pinned.
    Multi-value Lookup and Person keep their `ref`/`person` shape and so are
    join-bearing. What a multi-value LOOKUP costs is settled at one by
    `test_a_multi_value_lookup_costs_one_join_at_the_ceiling` below; multi-value
    Person is still unresolved and nothing here may start counting it.
    """
    table = make_table(
        "Platform",
        make_column("Title"),
        make_column("Events", "audit_event[]"),
    )
    assert join_bearing_columns(table, set()) == {"Author", "Editor"}


def test_a_multi_value_lookup_costs_one_join_at_the_ceiling() -> None:
    """A LookupMulti costs ONE join, same as a single-value lookup (#409 Q3).

    Built at the ceiling PLUS EXACTLY ONE, the only shape that discriminates:
    eleven single-value lookups render at 11, and the twelfth column decides
    whether the view sits at the measured ceiling of 12 or over it. The pair of
    tables differs in nothing but that column's arity, so a change that started
    charging two for the multi-value one fails here and nowhere else.

    The answer is INFERRED, not measured. `analysis/joins.py`'s docstring says
    so and names the probe that would settle it. This test exists so the
    inference cannot be revised by accident.
    """
    def _at_the_ceiling(twelfth: str) -> list[str]:
        table = make_table(
            "Matter",
            make_column("Title"),
            *(make_ref(f"Ref{n}", "Party.Id") for n in range(1, JOIN_LIMIT)),
            make_column("Parties", twelfth, ref="Party.Id"),
        )
        named = ["Parties", *(f"Ref{n}" for n in range(1, JOIN_LIMIT))]
        return joining_fields(named, join_bearing_columns(table, set()))

    multi = _at_the_ceiling("int[]")
    single = _at_the_ceiling("int")
    assert multi == single
    assert len(multi) == JOIN_LIMIT
    assert "Parties" in multi


def test_a_cross_site_ref_bears_no_join() -> None:
    """It expands to a Choice + URL pair, so no Lookup exists to join through.
    The second assertion is the negative case: without the exclusion the same
    column IS counted, which is exactly the defect."""
    table, _ = _task()
    assert "Elsewhere" not in join_bearing_columns(table, {"Elsewhere"})
    assert "Elsewhere" in join_bearing_columns(table, set())


def test_dates_and_text_are_free_but_author_and_editor_are_not() -> None:
    table, _ = _task()
    bearing = join_bearing_columns(table, {"Elsewhere"})
    assert joining_fields(["Created", "Modified", "Notes", "DueDate"], bearing) == []
    assert joining_fields(["Author", "Editor"], bearing) == ["Author", "Editor"]


def test_joining_fields_is_sorted_and_deduplicated() -> None:
    table, _ = _task()
    bearing = join_bearing_columns(table, {"Elsewhere"})
    assert joining_fields(
        ["Owner", "Assignee", "Owner", "Title", "Notes"], bearing,
    ) == ["Assignee", "Owner"]


def test_all_items_hidden_reads_the_entity_key() -> None:
    _, bundle = _task()
    assert all_items_hidden(bundle.mapping.entities["Task"]) == frozenset(
        {"Author", "Editor"},
    )
    # The negative case: an entity that declares nothing hides nothing.
    assert all_items_hidden(bundle.mapping.entities["Person"]) == frozenset()


def test_a_lookup_projection_costs_no_join() -> None:
    """The module docstring's `scale.join.projected-field-costs-a-join`
    claim, now that projections are declarable. A lookup column bears one
    join; each of its additional-field projections is a generated dependent
    field -- not a DBML column -- so
    `join_bearing_columns` never sees it. A view showing a lookup and five of
    its target's fields therefore costs ONE, not six, and no projection can
    push a view over the 12-join ceiling on its own.

    `RelatedRiskTitle` and `RelatedActionTitle` are the names the
    `lookup_projections` key generates for projecting Title from each lookup;
    they are asserted ABSENT from the join set while the lookups themselves
    are asserted present.
    """
    table = make_table(
        "ProjectAction",
        make_column("Title"),
        make_ref("RelatedRisk", "ProjectRisk.Id"),
        make_ref("RelatedAction", "ProjectAction.Id"),
    )
    bearing = join_bearing_columns(table, set())
    assert "RelatedRisk" in bearing
    assert "RelatedAction" in bearing
    # Generated dependent names are not DBML columns, so they cannot count.
    assert "RelatedRiskTitle" not in bearing
    assert "RelatedActionTitle" not in bearing
    # A view that lists the lookups plus their projected Titles costs two
    # joins, not four.
    assert joining_fields(
        ["RelatedRisk", "RelatedRiskTitle", "RelatedAction", "RelatedActionTitle"],
        bearing,
    ) == ["RelatedAction", "RelatedRisk"]
