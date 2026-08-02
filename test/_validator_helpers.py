"""Helpers shared by more than one test_validator_*.py module.

Only the seven that are genuinely used outside the section that defined
them live here; everything else stayed beside its tests.
"""
from pathlib import Path

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    EntityMapping,
    Mapping,
    MappingBundle,
    Versioning,
    load_mapping,
)
from dbml_sharepoint.model.parser import (
    EnumDef,
    Schema,
    Table,
    parse_dbml,
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
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Enum status {\n"
        '  "Open"\n'
        '  "Closed"\n'
        "}\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Status status\n"
        "  SortOrder int\n"
        "  DueDate date\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        + views_block,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")

def _view_errors(tmp_path: Path, views_block: str) -> list[Finding]:
    schema, bundle = _view_inputs(tmp_path, views_block)
    return [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]

def _calculated_form_inputs(tmp_path: Path, block: str) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(
        "Project t { database_type: 'SharePoint Online' }\n"
        "Table Project {\n"
        "  Id int [pk, increment]\n"
        "  Title nvarchar [not null]\n"
        "  Score int\n"
        "  Band calculated_text\n"
        "}\n",
        encoding="utf-8",
    )
    (tmp_path / "m.yaml").write_text(
        'prefix: "APP_"\n'
        "entities:\n"
        "  Project: { kind: List, base_template: 100, site_role: default }\n"
        "calculated_formulas:\n"
        "  Project:\n"
        "    Band: '=IF([Score]>5,\"High\",\"Low\")'\n"
        + block,
        encoding="utf-8",
    )
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")
