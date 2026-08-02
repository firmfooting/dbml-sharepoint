"""DBML fragments repeated across the suite.

Separate from `_packs` deliberately: `_packs` writes files, this composes DBML.
They change for different reasons.
"""

#: The primary key every table in the suite declares. 126 hand-written copies.
ID_PK = "Id int [pk, increment]"

#: The required title column.
TITLE = "Title nvarchar [not null]"


def table(name: str, *columns: str) -> str:
    """A DBML table block, one column per line, with a trailing newline."""
    body = "".join(f"  {c}\n" for c in columns)
    return f"Table {name} {{\n{body}}}\n"
