"""The one derivation the validator and the generator both read.

Two consumers computing "which column does a lookup into this entity show"
separately is how a validator comes to warn about an index the deployer never
creates. There is one function, and both call it.
"""

from pathlib import Path

from _builders import ID_PK, table
from _packs import blocks, entities, entity, write_dbml, write_mapping

from dbml_sharepoint.analysis.lookups import (
    lookup_display_columns,
    lookup_target_entities,
)
from dbml_sharepoint.model.mapping_loader import MappingBundle, load_mapping
from dbml_sharepoint.model.parser import Schema, parse_dbml

_SCHEMA = blocks(
    table("Event", ID_PK, "EventRef nvarchar"),
    table("FollowUp", ID_PK, "Event int [ref: > Event.Id]"),
    table("Untouched", ID_PK, "Note nvarchar"),
)


def _inputs(tmp_path: Path, mapping: str) -> tuple[Schema, MappingBundle]:
    schema_path = write_dbml(tmp_path, _SCHEMA)
    return parse_dbml(schema_path), load_mapping(write_mapping(tmp_path, mapping))


def _plain(event: str | None = entity("Event")) -> str:
    """The three-entity mapping these tests vary.

    `event` is the Event declaration: pass `entity("Event", display_column=...)`
    to add a key to it, or None to drop Event from the mapping entirely.

    Built rather than patched. The previous form was a `_PLAIN` constant that
    each test string-replaced a whole line out of, which meant the needles had
    to match the constant byte for byte — including its two-space indent. That
    is a silent failure if it ever drifts: `str.replace` returns the input
    unchanged and the test asserts against the unmodified mapping. `replaced()`
    was added to make that loud; expressing the variant directly removes the
    need for it here.
    """
    return entities(*([event] if event else []), "FollowUp", "Untouched")


def test_target_entities_names_only_the_pointed_at_side(tmp_path: Path) -> None:
    """The shared derivation. `_structure`'s calculated-display warning used to
    carry its own byte-identical copy of this comprehension, which is how one
    could come to fire for a list the other never indexes."""
    schema, _ = _inputs(tmp_path, _plain())
    assert lookup_target_entities(schema, set()) == {"Event"}


def test_a_lookup_target_defaults_to_title(tmp_path: Path) -> None:
    schema, bundle = _inputs(tmp_path, _plain())
    assert lookup_display_columns(schema, bundle.mapping.entities, {}, set()) == {
        "Event": "Title",
    }


def test_an_entity_no_ref_points_at_is_absent(tmp_path: Path) -> None:
    """Only a lookup TARGET needs the index. Indexing every list's Title would
    spend a slot on lists nothing looks up."""
    schema, bundle = _inputs(tmp_path, _plain())
    assert "Untouched" not in lookup_display_columns(
        schema, bundle.mapping.entities, {}, set(),
    )
    assert "FollowUp" not in lookup_display_columns(
        schema, bundle.mapping.entities, {}, set(),
    )


def test_a_declared_display_column_wins(tmp_path: Path) -> None:
    schema, bundle = _inputs(tmp_path, _plain(entity("Event", display_column="EventRef")))
    assert lookup_display_columns(schema, bundle.mapping.entities, {}, set()) == {
        "Event": "EventRef",
    }


def test_a_calculated_display_column_is_excluded(tmp_path: Path) -> None:
    """It cannot carry an index — CALCIDX sets Indexed=true, the MERGE is
    accepted and the flag reads back false. Including it would make the caller
    count an index that cannot exist."""
    schema, bundle = _inputs(tmp_path, _plain(entity("Event", display_column="EventRef")))
    assert lookup_display_columns(
        schema, bundle.mapping.entities, {"Event": {"EventRef"}}, set(),
    ) == {}


def test_a_ref_target_unmapped_is_absent(tmp_path: Path) -> None:
    """A ref points at a table with no mapping entry: other checks report that
    error. Inventing an index for it here would be a second, worse message."""
    schema, bundle = _inputs(tmp_path, _plain(None))
    # Schema still has Event (FollowUp refs it), but only FollowUp is mapped.
    # The unmapped ref target is silently skipped.
    assert lookup_display_columns(schema, bundle.mapping.entities, {}, set()) == {}


# --- Cross-site references are not lookups ----------------------------------

_CROSS_SITE_SCHEMA = blocks(
    table("Event", ID_PK, "EventRef nvarchar"),
    table("FollowUp", ID_PK, "Elsewhere int [ref: > Event.Id]"),
)

def _cross_site_mapping(*extra: str) -> str:
    """Event and FollowUp, plus any extra entities, with one cross-site pair.

    Built for the same reason as `_plain`: the variant used to be produced by
    string-replacing the `cross_site_reference_columns:` line to smuggle an
    entity in above it, which only worked while that needle matched exactly.
    """
    return blocks(
        entities("Event", "FollowUp", *extra),
        """
        cross_site_reference_columns:
          - { entity: FollowUp, column: Elsewhere }
        """,
    )


def _cross_site_inputs(
    tmp_path: Path, schema_text: str, mapping_text: str,
) -> tuple[Schema, MappingBundle, set[tuple[str, str]]]:
    schema_path = write_dbml(tmp_path, schema_text)
    bundle = load_mapping(write_mapping(tmp_path, mapping_text))
    pairs = {
        (x.entity, x.column) for x in bundle.mapping.cross_site_reference_columns
    }
    return parse_dbml(schema_path), bundle, pairs


def test_a_cross_site_only_target_is_not_a_lookup_target(tmp_path: Path) -> None:
    """A cross-site ref is expanded into a Choice + URL pair on the SOURCE list.
    Nothing enumerates the far list, so there is no picker to protect — and
    indexing its display column would be a real Indexed=true MERGE on a customer
    tenant buying nothing."""
    schema, bundle, pairs = _cross_site_inputs(
        tmp_path, _CROSS_SITE_SCHEMA, _cross_site_mapping(),
    )
    assert pairs == {("FollowUp", "Elsewhere")}
    assert lookup_target_entities(schema, pairs) == set()
    assert lookup_display_columns(
        schema, bundle.mapping.entities, {}, pairs,
    ) == {}
    # Without the exclusion this is exactly what happens, which is the defect.
    assert lookup_target_entities(schema, set()) == {"Event"}


def test_a_target_of_both_kinds_keeps_its_index(tmp_path: Path) -> None:
    """The filter is per (entity, column) PAIR, not per entity. Excluding every
    entity merely NAMED in cross_site_reference_columns would strip the index
    off a list that really does have a picker."""
    schema, bundle, pairs = _cross_site_inputs(
        tmp_path,
        _CROSS_SITE_SCHEMA + table("Reminder", ID_PK, "Event int [ref: > Event.Id]"),
        _cross_site_mapping("Reminder"),
    )
    assert lookup_target_entities(schema, pairs) == {"Event"}
    assert lookup_display_columns(
        schema, bundle.mapping.entities, {}, pairs,
    ) == {"Event": "Title"}
