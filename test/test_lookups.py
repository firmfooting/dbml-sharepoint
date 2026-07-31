"""The one derivation the validator and the generator both read.

Two consumers computing "which column does a lookup into this entity show"
separately is how a validator comes to warn about an index the deployer never
creates. There is one function, and both call it.
"""

from pathlib import Path

from dbml_sharepoint.analysis.lookups import lookup_display_columns
from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import Schema, parse_dbml

_SCHEMA = (
    "Project t { database_type: 'SharePoint Online' }\n"
    "Table Event {\n"
    "  Id int [pk, increment]\n"
    "  EventRef nvarchar\n"
    "}\n"
    "Table FollowUp {\n"
    "  Id int [pk, increment]\n"
    "  Event int [ref: > Event.Id]\n"
    "}\n"
    "Table Untouched {\n"
    "  Id int [pk, increment]\n"
    "  Note nvarchar\n"
    "}\n"
)


def _inputs(tmp_path: Path, mapping: str) -> tuple[Schema, MappingBundle]:
    (tmp_path / "s.dbml").write_text(_SCHEMA, encoding="utf-8")
    (tmp_path / "m.yaml").write_text(mapping, encoding="utf-8")
    return parse_dbml(tmp_path / "s.dbml"), load_mapping(tmp_path / "m.yaml")


_PLAIN = (
    'prefix: "APP_"\n'
    "entities:\n"
    "  Event: { kind: List, base_template: 100, site_role: default }\n"
    "  FollowUp: { kind: List, base_template: 100, site_role: default }\n"
    "  Untouched: { kind: List, base_template: 100, site_role: default }\n"
)


def test_a_lookup_target_defaults_to_title(tmp_path: Path) -> None:
    schema, bundle = _inputs(tmp_path, _PLAIN)
    assert lookup_display_columns(schema, bundle.mapping.entities, {}) == {
        "Event": "Title",
    }


def test_an_entity_no_ref_points_at_is_absent(tmp_path: Path) -> None:
    """Only a lookup TARGET needs the index. Indexing every list's Title would
    spend a slot on lists nothing looks up."""
    schema, bundle = _inputs(tmp_path, _PLAIN)
    assert "Untouched" not in lookup_display_columns(
        schema, bundle.mapping.entities, {},
    )
    assert "FollowUp" not in lookup_display_columns(
        schema, bundle.mapping.entities, {},
    )


def test_a_declared_display_column_wins(tmp_path: Path) -> None:
    schema, bundle = _inputs(tmp_path, _PLAIN.replace(
        "  Event: { kind: List, base_template: 100, site_role: default }",
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: EventRef }",
    ))
    assert lookup_display_columns(schema, bundle.mapping.entities, {}) == {
        "Event": "EventRef",
    }


def test_a_calculated_display_column_is_excluded(tmp_path: Path) -> None:
    """It cannot carry an index — CALCIDX sets Indexed=true, the MERGE is
    accepted and the flag reads back false. Including it would make the caller
    count an index that cannot exist."""
    schema, bundle = _inputs(tmp_path, _PLAIN.replace(
        "  Event: { kind: List, base_template: 100, site_role: default }",
        "  Event: { kind: List, base_template: 100, site_role: default, "
        "display_column: EventRef }",
    ))
    assert lookup_display_columns(
        schema, bundle.mapping.entities, {"Event": {"EventRef"}},
    ) == {}


def test_a_ref_target_unmapped_is_absent(tmp_path: Path) -> None:
    """A ref points at a table with no mapping entry: other checks report that
    error. Inventing an index for it here would be a second, worse message."""
    schema, bundle = _inputs(tmp_path, _PLAIN.replace(
        "  Event: { kind: List, base_template: 100, site_role: default }\n",
        "",
    ))
    # Schema still has Event (FollowUp refs it), but only FollowUp is mapped.
    # The unmapped ref target is silently skipped.
    assert lookup_display_columns(schema, bundle.mapping.entities, {}) == {}
