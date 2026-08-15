# test/test_parser.py
from pathlib import Path
from textwrap import dedent

import pytest
from _packs import write_dbml
from _paths import FIXTURES

from dbml_sharepoint.model.parser import parse_dbml


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


def test_table_indexes_are_preserved_from_dbml(tmp_path: Path) -> None:
    schema_path = write_dbml(
        tmp_path,
        """
        Table Risk {
          Id int [pk, increment]
          Status nvarchar
          Category nvarchar
          indexes {
            Status
            Category
          }
        }
        """,
        preamble=False,
        name="indexed.dbml",
    )
    risk = parse_dbml(schema_path).tables[0]
    assert [index.columns for index in risk.indexes] == [("Status",), ("Category",)]


def test_a_ref_to_a_missing_table_is_a_message_not_a_traceback(tmp_path: Path) -> None:
    """pydbml raises `TableNotFoundError`, which is not a `ValueError`.

    The CLI's config-error handling keys on `ValueError`, so without the
    translation in `parse_dbml` a schema typo prints a traceback at the person
    least able to read one, a SharePoint admin editing DBML. This is the same
    contract `test_cli.test_malformed_dbml_is_a_message_not_a_traceback`
    asserts end to end; here it is pinned at the boundary that does the work.

    Covered only incidentally before, by validator tests that happened to
    parse a broken schema. Those are being migrated to build objects directly,
    so this path needs a test of its own or it loses its coverage silently.
    """
    path = write_dbml(tmp_path, """
        Table Risk {
          Id int [pk, increment]
          Owner int [ref: > Ghost.Id]
        }
    """)
    with pytest.raises(ValueError, match="Ghost"):
        parse_dbml(path)


# --- pydbml's vocabulary, translated ----------------------------------------


def _write(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "schema.dbml"
    path.write_text(
        "Project t { database_type: 'SharePoint Online' }\n" + dedent(body),
        encoding="utf-8",
    )
    return path


def test_a_ref_to_a_missing_table_is_reported_in_our_own_words(
    tmp_path: Path,
) -> None:
    """pydbml says `Table public.Nope not present in the database`.

    `public` is a Postgres schema namespace that means nothing here, and
    `database` is not a word this tool uses -- the target is a SharePoint
    site. The person reading it hand-edited a .dbml file.
    """
    path = _write(tmp_path, """
        Table Risk {
          Id int [pk, increment]
          Owner nvarchar [ref: > Nope.Id]
        }
    """)

    with pytest.raises(ValueError) as raised:
        parse_dbml(path)

    message = str(raised.value)
    assert "Nope" in message
    assert "public" not in message
    assert "database" not in message


def test_a_duplicate_table_is_reported_in_our_own_words(tmp_path: Path) -> None:
    path = _write(tmp_path, """
        Table Risk {
          Id int [pk, increment]
        }
        Table Risk {
          Id int [pk]
        }
    """)

    with pytest.raises(ValueError) as raised:
        parse_dbml(path)

    message = str(raised.value)
    assert "Risk" in message
    assert "public" not in message


def test_a_ref_error_cites_the_line_when_it_can_find_it(tmp_path: Path) -> None:
    """The message names a table, not a position, and the file was typed by
    hand -- so the line is the part that makes it actionable."""
    path = _write(tmp_path, """
        Table Risk {
          Id int [pk, increment]
          Owner nvarchar [ref: > Nope.Id]
        }
    """)

    with pytest.raises(ValueError) as raised:
        parse_dbml(path)

    # Line 5 is the `Owner ... [ref: > Nope.Id]` line: the dedented block
    # opens with a newline, so the Project line is 1 and the table body
    # starts at 3.
    assert "line 5" in str(raised.value)
    assert path.read_text(encoding="utf-8").splitlines()[4].strip().startswith("Owner")


def test_an_unrecognised_parse_error_passes_through_untouched(
    tmp_path: Path,
) -> None:
    """Translating what we recognise is worth doing; guessing at what we do
    not is worse than the leak. A syntax error already carries its own line
    and column and says nothing about `public`, so it must arrive intact."""
    path = _write(tmp_path, """
        Table Risk {
          Id int [pk, increment]
          Title nvarchar [not null
        }
    """)

    with pytest.raises(Exception, match="line:6") as raised:
        parse_dbml(path)

    assert "Expected" in str(raised.value)
