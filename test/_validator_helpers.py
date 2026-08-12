"""Helpers shared by more than one test_validator_*.py module.

Only the ones genuinely used outside the section that defined them live
here; everything else stayed beside its tests.

There is one spelling of the Project fixture, and it builds objects. There
were two: the other wrote the same entity out as DBML and YAML, parsed it
back and returned the result. A shared module offering two ways to build one
thing is how half a suite ends up on the slower one for no reason, and a
check before the deletion confirmed the pair agreed field for field --
identical `Schema`, identical `Mapping`, and the only differing
`MappingBundle` field was `source_paths`, which only a loaded bundle can
have. The text spelling now lives in `test_validator_field_sets.py`, beside
the five tests that need a LOAD-TIME transform (`_expand_field_sets`, the
retirement fold) and so cannot use objects.

A helper composing a bundle around `calculated_formulas` also lived here, and
is gone for a sharper reason: it hand-rolled a `MappingBundle`, and
hand-rolled bundles keep getting the loader's defaults wrong. That one had
already been patched to set `permissions` to the empty `PermissionsConfig`
the loader produces, because the dataclass default of `None` made
`checks/_permissions.py` skip every test using it -- the third time the same
bug was found in a different helper. `_model.bundle` is the one builder that
gets those defaults right; call it with `calculated_formulas=...`.
"""
from typing import Unpack

from _model import MappingSections, column, enum
from _model import bundle as _object_bundle
from _model import schema as _object_schema
from _model import table as _object_table

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate_against_mapping,
)
from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.parser import (
    EnumDef,
    Schema,
    Table,
)

RESERVED_NAMES = {"Created", "Modified", "Editor", "Author", "Attachments", "_UIVersion"}

def _schema(*tables: Table, enums: list[EnumDef] | None = None) -> Schema:
    return Schema(tables=list(tables), enums=enums or [])

# --- Declared views ---------------------------------------------------------


def _project_inputs(
    **sections: Unpack[MappingSections],
) -> tuple[Schema, MappingBundle]:
    """The standard Project entity, plus whatever mapping sections a test adds.

    The mapping sections arrive as keyword arguments rather than as a YAML
    block, which is what removes the indentation -- and the loader -- from the
    test.

    The table carries a `note`, because `ENTITY_HAS_NO_NOTE` is an ERROR and
    several of the tests built on this fixture assert that the errors are
    exactly the ones they provoked. `_model.table()` deliberately does NOT
    default it -- the tests that make that rule fire need a table with none --
    so the fixtures that want to be clean say so here.
    """
    return (
        _object_schema(
            _object_table(
                "Project",
                column("Title", required=True),
                column("Status", "status"),
                column("SortOrder", "int"),
                column("DueDate", "date"),
                note="The standard fixture project list.",
            ),
            enums=[enum("status", "Open", "Closed")],
        ),
        _object_bundle(entities=["Project"], **sections),
    )


def _project_errors(**sections: Unpack[MappingSections]) -> list[Finding]:
    """`_project_inputs`, validated, keeping only the errors."""
    schema, bundle = _project_inputs(**sections)
    return [f for f in validate_against_mapping(schema, bundle) if f.severity == "error"]
