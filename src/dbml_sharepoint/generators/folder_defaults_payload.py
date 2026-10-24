# src/dbml_sharepoint/generators/folder_defaults_payload.py
"""The folder defaults payload verify and assess read, one spelling for both."""

from collections.abc import Mapping, Sequence

from dbml_sharepoint.analysis.folder_defaults import encode_folder_default
from dbml_sharepoint.generators.schema_types import FolderDefaults
from dbml_sharepoint.model.mapping_types import EntityMapping


def folder_defaults_payload(
    entity: EntityMapping, folders: Sequence[str], column_types: Mapping[str, str],
) -> list[FolderDefaults]:
    """Every declared folder of a library that manages defaults, in folder order.

    A declared folder the mapping gives no defaults is reconciled to none by the
    deploy, so it appears with an empty value list and a stale entry is caught.
    Each value is the text the defaults file holds, so verify compares like with like.
    An undeclared column, which the validator refuses, is spelled as text.
    """
    if not (entity.is_library and entity.folder_defaults):
        return []
    return [
        {"folder": folder, "values": [
            {"field": column, "value": encode_folder_default(column_types.get(column, ""), value)}
            for column, value in entity.folder_defaults.get(folder, {}).items()
        ]}
        for folder in folders
    ]
