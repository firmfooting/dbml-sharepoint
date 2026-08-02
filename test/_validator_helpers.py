"""Helpers shared by more than one test_validator_*.py module.

Only the seven that are genuinely used outside the section that defined
them live here; everything else stayed beside its tests.
"""
from pathlib import Path

from _packs import blocks, pack

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    EntityMapping,
    Mapping,
    MappingBundle,
    Versioning,
)
from dbml_sharepoint.model.parser import (
    EnumDef,
    Schema,
    Table,
)

RESERVED_NAMES = {"Created", "Modified", "Editor", "Author", "Attachments", "_UIVersion"}

def _schema(*tables: Table, enums: list[EnumDef] | None = None) -> Schema:
    return Schema(tables=list(tables), enums=enums or [])

def _bundle_with_formulas(
    formulas: dict[str, dict[str, str]], *entity_names: str,
) -> MappingBundle:
    """A minimal bundle declaring the named entities plus calculated formulas."""
    mapping = Mapping(
        prefix="APP_", prefix_owner="", prefix_registry="",
        entities={
            name: EntityMapping(
                name=name, kind="List", base_template=100, site_role="default",
            )
            for name in entity_names
        },
        cross_site_reference_columns=[],
        versioning_default=Versioning(True, 500, False), versioning_overrides={},
        enum_sources={}, watched_lists=[], calculated_formulas=formulas,
    )
    return MappingBundle(
        mapping=mapping, enum_choices={}, retention_policies={},
        retention_list_defaults={},
    )

# --- Declared views ---------------------------------------------------------


def _view_inputs(tmp_path: Path, views_block: str) -> tuple[Schema, MappingBundle]:
    """The standard Project entity, plus whatever mapping block the test adds.

    `views_block` is dedented, so a caller may pass a triple-quoted block
    indented to match its surrounding code. A block already flush against the
    left margin is unaffected.
    """
    return pack(
        tmp_path,
        dbml="""
            Enum status {
              "Open"
              "Closed"
            }
            Table Project {
              Id int [pk, increment]
              Title nvarchar [not null]
              Status status
              SortOrder int
              DueDate date
            }
        """,
        mapping=blocks(
            """
            entities:
              Project: { kind: List, base_template: 100, site_role: default }
            """,
            views_block,
        ),
    )


def _view_errors(tmp_path: Path, views_block: str) -> list[Finding]:
    schema, bundle = _view_inputs(tmp_path, views_block)
    return [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]


def _calculated_form_inputs(tmp_path: Path, block: str) -> tuple[Schema, MappingBundle]:
    """A calculated `Band` column derived from `Score`, plus the test's block.

    `block` is dedented on the caller's behalf, as in `_view_inputs`.
    """
    return pack(
        tmp_path,
        dbml="""
            Table Project {
              Id int [pk, increment]
              Title nvarchar [not null]
              Score int
              Band calculated_text
            }
        """,
        mapping=blocks(
            """
            entities:
              Project: { kind: List, base_template: 100, site_role: default }
            calculated_formulas:
              Project:
                Band: '=IF([Score]>5,"High","Low")'
            """,
            block,
        ),
    )
