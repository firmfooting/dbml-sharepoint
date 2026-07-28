"""Shared projection of validated DBML indexes into generator inputs."""

from dbml_sharepoint.model.parser import Table


def deployable_index_columns(table: Table) -> list[str]:
    """Return single-column index targets, failing closed on composites."""
    columns: list[str] = []
    for index in table.indexes:
        if len(index.columns) != 1:
            raise ValueError(
                f"{table.name}: composite DBML indexes cannot be deployed to SharePoint",
            )
        columns.append(index.columns[0])
    return columns
