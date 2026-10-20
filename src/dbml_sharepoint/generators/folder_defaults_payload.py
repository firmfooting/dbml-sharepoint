# src/dbml_sharepoint/generators/folder_defaults_payload.py
"""The folder defaults payload verify and assess read, one spelling for both."""

from collections.abc import Sequence

from dbml_sharepoint.generators.schema_types import FolderDefaults
from dbml_sharepoint.model.mapping_types import EntityMapping


def folder_defaults_payload(
    entity: EntityMapping, folders: Sequence[str],
) -> list[FolderDefaults]:
    """Every declared folder of a library that manages defaults, in folder order.

    A declared folder the mapping gives no defaults is reconciled to none by the
    deploy, so it appears with an empty value list and a stale entry is caught.
    """
    if not (entity.is_library and entity.folder_defaults):
        return []
    return [
        {"folder": folder, "values": [
            {"field": column, "value": value}
            for column, value in entity.folder_defaults.get(folder, {}).items()
        ]}
        for folder in folders
    ]
