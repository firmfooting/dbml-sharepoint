# test/test_joins.py
from pathlib import Path

from dbml_sharepoint.analysis.joins import (
    JOIN_LIMIT,
    JOIN_WARN_AT,
    SYSTEM_JOIN_COLUMNS,
    all_items_hidden,
    join_bearing_columns,
    joining_fields,
)
from dbml_sharepoint.analysis.typemap import JOIN_BEARING_TYPES
from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import Table, parse_dbml

_SCHEMA = (
    "Project t { database_type: 'SharePoint Online' }\n"
    "Table Person {\n"
    "  Id int [pk, increment]\n"
    "  Title nvarchar [not null]\n"
    "}\n"
    "Table Task {\n"
    "  Id int [pk, increment]\n"
    "  Title nvarchar [not null]\n"
    "  Owner person\n"
    "  Assignee int [ref: > Person.Id]\n"
    "  Elsewhere int [ref: > Person.Id]\n"
    "  Notes nvarchar\n"
    "  DueDate date\n"
    "}\n"
)
_MAPPING = (
    'prefix: "APP_"\n'
    "entities:\n"
    "  Person: { kind: List, base_template: 100, site_role: default }\n"
    "  Task:\n"
    "    kind: List\n"
    "    base_template: 100\n"
    "    site_role: default\n"
    "    hide_from_all_items: [Author, Editor]\n"
    "cross_site_reference_columns:\n"
    "  - { entity: Task, column: Elsewhere }\n"
)


def _task(tmp_path: Path) -> tuple[Table, MappingBundle]:
    (tmp_path / "s.dbml").write_text(_SCHEMA, encoding="utf-8")
    (tmp_path / "m.yaml").write_text(_MAPPING, encoding="utf-8")
    schema = parse_dbml(tmp_path / "s.dbml")
    bundle = load_mapping(tmp_path / "m.yaml")
    table = next(t for t in schema.tables if t.name == "Task")
    return table, bundle


def test_the_bands_are_nine_and_twelve() -> None:
    """The last two assertions are the GUARD ON THE DERIVATION, not a second
    copy of it. SYSTEM_JOIN_COLUMNS is computed from SYSTEM_COLUMN_TYPES, so
    these pin what that computation must come out as: Created and Modified are
    absent because they are `datetime`, and that row of the rule is INFERRED
    rather than measured. Widen JOIN_BEARING_TYPES and this fails, which is the
    point.

    Written `sorted(X) == [...]` rather than `X == frozenset({...})` because
    ruff reads an uppercase name as the constant side and flags the latter
    SIM300 'Yoda condition detected'."""
    assert JOIN_WARN_AT == 9
    assert JOIN_LIMIT == 12
    assert sorted(SYSTEM_JOIN_COLUMNS) == ["Author", "Editor"]
    assert sorted(JOIN_BEARING_TYPES) == ["person"]


def test_refs_person_columns_and_the_two_system_columns_bear_joins(
    tmp_path: Path,
) -> None:
    table, _ = _task(tmp_path)
    assert join_bearing_columns(table, {"Elsewhere"}) == {
        "Owner", "Assignee", "Author", "Editor",
    }


def test_a_cross_site_ref_bears_no_join(tmp_path: Path) -> None:
    """It expands to a Choice + URL pair, so no Lookup exists to join through.
    The second assertion is the negative case: without the exclusion the same
    column IS counted, which is exactly the defect."""
    table, _ = _task(tmp_path)
    assert "Elsewhere" not in join_bearing_columns(table, {"Elsewhere"})
    assert "Elsewhere" in join_bearing_columns(table, set())


def test_dates_and_text_are_free_but_author_and_editor_are_not(
    tmp_path: Path,
) -> None:
    table, _ = _task(tmp_path)
    bearing = join_bearing_columns(table, {"Elsewhere"})
    assert joining_fields(["Created", "Modified", "Notes", "DueDate"], bearing) == []
    assert joining_fields(["Author", "Editor"], bearing) == ["Author", "Editor"]


def test_joining_fields_is_sorted_and_deduplicated(tmp_path: Path) -> None:
    table, _ = _task(tmp_path)
    bearing = join_bearing_columns(table, {"Elsewhere"})
    assert joining_fields(
        ["Owner", "Assignee", "Owner", "Title", "Notes"], bearing,
    ) == ["Assignee", "Owner"]


def test_all_items_hidden_reads_the_entity_key(tmp_path: Path) -> None:
    _, bundle = _task(tmp_path)
    assert all_items_hidden(bundle.mapping.entities["Task"]) == frozenset(
        {"Author", "Editor"},
    )
    # The negative case: an entity that declares nothing hides nothing.
    assert all_items_hidden(bundle.mapping.entities["Person"]) == frozenset()
