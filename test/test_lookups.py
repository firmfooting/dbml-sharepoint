"""The one derivation the validator and the generator both read.

Two consumers computing "which column does a lookup into this entity show"
separately is how a validator comes to warn about an index the deployer never
creates. There is one function, and both call it.
"""

from _model import column as make_column
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table

from dbml_sharepoint.analysis.lookups import (
    lookup_display_columns,
    lookup_target_entities,
)
from dbml_sharepoint.model.mapping_types import EntityMapping
from dbml_sharepoint.model.parser import Schema, Table


def _entity(name: str, display_column: str | None = None) -> EntityMapping:
    """One entity declaration. Only the display column ever varies here."""
    return EntityMapping(
        name=name, kind="List", base_template=100, site_role="default",
        display_column=display_column,
    )


def _declared(*entities: EntityMapping) -> dict[str, EntityMapping]:
    """The `entities` map these derivations read, keyed the way the loader keys it."""
    return {e.name: e for e in entities}


def _schema() -> Schema:
    """Event, the FollowUp that looks it up, and a list nothing points at.

    A function rather than a module constant: `Schema`, `Table` and `Column`
    are mutable dataclasses, so one shared instance would be the same object
    in every test in the file (the rule `_model` states in its own docstring).
    """
    return make_schema(
        make_table("Event", make_column("EventRef")),
        make_table("FollowUp", make_ref("Event", "Event.Id")),
        make_table("Untouched", make_column("Note")),
    )


def _plain(event: EntityMapping | None = None) -> dict[str, EntityMapping]:
    """The three-entity declaration these tests vary.

    `event` is the Event declaration: pass `_entity("Event", "EventRef")` to
    give it a display column. Built rather than patched. The previous form
    was a YAML constant each test string-replaced a whole line out of, which
    meant the needles had to match it byte for byte, including their two-space
    indent. `str.replace` returns the input unchanged when the needle drifts,
    so the test would assert against the unmodified mapping and still pass.
    """
    return _declared(
        event if event is not None else _entity("Event"),
        _entity("FollowUp"),
        _entity("Untouched"),
    )


def test_target_entities_names_only_the_pointed_at_side() -> None:
    """The shared derivation. `_structure`'s calculated-display warning used to
    carry its own byte-identical copy of this comprehension, which is how one
    could come to fire for a list the other never indexes."""
    assert lookup_target_entities(_schema(), set()) == {"Event"}


def test_a_lookup_target_defaults_to_title() -> None:
    assert lookup_display_columns(_schema(), _plain(), {}, set()) == {"Event": "Title"}


def test_an_entity_no_ref_points_at_is_absent() -> None:
    """Only a lookup TARGET needs the index. Indexing every list's Title would
    spend a slot on lists nothing looks up."""
    shown = lookup_display_columns(_schema(), _plain(), {}, set())
    assert "Untouched" not in shown
    assert "FollowUp" not in shown


def test_a_declared_display_column_wins() -> None:
    declared = _plain(_entity("Event", "EventRef"))
    assert lookup_display_columns(_schema(), declared, {}, set()) == {
        "Event": "EventRef",
    }


def test_a_calculated_display_column_is_excluded() -> None:
    """It cannot carry an index. `scale.index.calculated-indexable` sets
    Indexed=true, the MERGE is accepted and the flag reads back false.
    Including it would make the caller count an index that cannot exist."""
    declared = _plain(_entity("Event", "EventRef"))
    assert lookup_display_columns(
        _schema(), declared, {"Event": {"EventRef"}}, set(),
    ) == {}


def test_a_ref_target_unmapped_is_absent() -> None:
    """A ref points at a table with no mapping entry: other checks report that
    error. Inventing an index for it here would be a second, worse message."""
    # Schema still has Event (FollowUp refs it), but only FollowUp is mapped.
    # The unmapped ref target is silently skipped.
    declared = _declared(_entity("FollowUp"), _entity("Untouched"))
    assert lookup_display_columns(_schema(), declared, {}, set()) == {}


# --- Cross-site references are not lookups ----------------------------------

#: The one declared cross-site pair, in the shape `lookups` takes it.
_CROSS_SITE_PAIRS = frozenset({("FollowUp", "Elsewhere")})


def _cross_site_schema(*extra: Table) -> Schema:
    """FollowUp's only ref into Event is the cross-site one."""
    return make_schema(
        make_table("Event", make_column("EventRef")),
        make_table("FollowUp", make_ref("Elsewhere", "Event.Id")),
        *extra,
    )


def test_a_cross_site_only_target_is_not_a_lookup_target() -> None:
    """A cross-site ref is expanded into a Choice + URL pair on the SOURCE list.
    Nothing enumerates the far list, so there is no picker to protect, and
    indexing its display column would be a real Indexed=true MERGE on a customer
    tenant buying nothing."""
    schema = _cross_site_schema()
    declared = _declared(_entity("Event"), _entity("FollowUp"))
    pairs = set(_CROSS_SITE_PAIRS)
    assert lookup_target_entities(schema, pairs) == set()
    assert lookup_display_columns(schema, declared, {}, pairs) == {}
    # Without the exclusion this is exactly what happens, which is the defect.
    assert lookup_target_entities(schema, set()) == {"Event"}


def test_a_target_of_both_kinds_keeps_its_index() -> None:
    """The filter is per (entity, column) PAIR, not per entity. Excluding every
    entity merely NAMED in cross_site_reference_columns would strip the index
    off a list that really does have a picker."""
    schema = _cross_site_schema(make_table("Reminder", make_ref("Event", "Event.Id")))
    declared = _declared(_entity("Event"), _entity("FollowUp"), _entity("Reminder"))
    pairs = set(_CROSS_SITE_PAIRS)
    assert lookup_target_entities(schema, pairs) == {"Event"}
    assert lookup_display_columns(schema, declared, {}, pairs) == {"Event": "Title"}
