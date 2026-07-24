# test/test_parser.py
from pathlib import Path

from dbml_sharepoint.model.parser import parse_dbml

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_simple_returns_core_tables_and_one_enum() -> None:
    result = parse_dbml(FIXTURES / "simple.dbml")
    table_names = {t.name for t in result.tables}
    assert "Project" in table_names
    assert "Task" in table_names
    assert "AppSettings" in table_names
    assert {e.name for e in result.enums} == {"status"}


def test_status_enum_members_are_in_declaration_order() -> None:
    result = parse_dbml(FIXTURES / "simple.dbml")
    status = next(e for e in result.enums if e.name == "status")
    assert status.members == ["Open", "Closed"]


def test_task_project_column_is_a_lookup() -> None:
    result = parse_dbml(FIXTURES / "simple.dbml")
    task = next(t for t in result.tables if t.name == "Task")
    project_col = next(c for c in task.columns if c.name == "Project")
    assert project_col.ref is not None
    assert project_col.ref.target_table == "Project"
    assert project_col.ref.target_column == "Id"
    assert project_col.required is True


def test_id_pk_increment_is_marked() -> None:
    result = parse_dbml(FIXTURES / "simple.dbml")
    project = next(t for t in result.tables if t.name == "Project")
    id_col = next(c for c in project.columns if c.name == "Id")
    assert id_col.is_pk is True
    assert id_col.is_auto_increment is True
