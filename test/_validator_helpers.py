"""Helpers shared by more than one test_validator_*.py module.

Only the ones genuinely used outside the section that defined them live
here; everything else stayed beside its tests.

`_view_inputs`/`_view_errors` and `_project_inputs`/`_project_errors` are
the same Project fixture spelled two ways -- written to disk and parsed, or
built as objects. The text pair is still right for a test whose subject IS
the text; everything else should take the object pair.
"""
from pathlib import Path
from typing import Unpack

from _model import MappingSections, column, enum
from _model import bundle as _object_bundle
from _model import schema as _object_schema
from _model import table as _object_table
from _packs import blocks, pack

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import (
    EntityMapping,
    Mapping,
    MappingBundle,
    PermissionsConfig,
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
        # Matches what load_mapping always produces. Left as the dataclass
        # default (None) this helper silently skipped checks/_permissions.py
        # entirely, because that module opens with `if permissions is not None`.
        permissions=PermissionsConfig(
            levels=[], groups=[], default_policy=None, overrides={},
        ),
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


def _project_inputs(
    **sections: Unpack[MappingSections],
) -> tuple[Schema, MappingBundle]:
    """`_view_inputs`, built as objects rather than written to disk and parsed.

    The same Project entity and `status` enum, so a test may move between the
    two without its fixture changing underneath it — `test_model_contract.py`
    is what says the two spellings agree. The mapping sections arrive as
    keyword arguments instead of a YAML block, which is what removes the
    indentation from the test.

    Both spellings exist because the text one is still right for a test that
    is ABOUT the text: a parse error, a loader refusal, or a section whose
    subject is what `load_mapping` does to it on the way through.
    """
    return (
        _object_schema(
            _object_table(
                "Project",
                column("Title", required=True),
                column("Status", "status"),
                column("SortOrder", "int"),
                column("DueDate", "date"),
            ),
            enums=[enum("status", "Open", "Closed")],
        ),
        _object_bundle(entities=["Project"], **sections),
    )


def _project_errors(**sections: Unpack[MappingSections]) -> list[Finding]:
    """`_project_inputs`, validated, keeping only the errors."""
    schema, bundle = _project_inputs(**sections)
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
