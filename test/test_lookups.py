"""The one derivation the validator and the generator both read.

Two consumers computing "which column does a lookup into this entity show"
separately is how a validator comes to warn about an index the deployer never
creates. There is one function, and both call it.

The last two sections are about what a DBML `ref` DOES NOT carry, and they
are here rather than in `test_parser.py` because they are the evidence
behind the claims on `website/docs/concepts/relationships.md`. That page
states that a ref's cardinality symbol and its target column reach nothing,
and that no lookup this tool emits carries a relationship knob. Each is a
sentence an adopter plans a schema around, so each is pinned rather than
read off the source.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from _builders import ID_PK, TITLE
from _builders import table as dbml_table
from _model import column as make_column
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, entities, pack, with_tail
from _paths import FIXTURES

from dbml_sharepoint.analysis.lookups import (
    lookup_display_columns,
    lookup_target_entities,
)
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.extension import NullExtension
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.mapping_types import EntityMapping
from dbml_sharepoint.model.parser import Reference, Schema, Table
from dbml_sharepoint.model.release import load_release


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


# --- A ref's cardinality symbol reaches nothing -----------------------------

#: Every cardinality DBML spells, none of which the parser records.
_CARDINALITY_SYMBOLS = (">", "<", "-", "<>")

#: What the parse below must produce, whichever symbol was written.
_ONE_LOOKUP = {("Action", "RiskId"): Reference("Risk", "Id")}


def _refs(schema: Schema) -> dict[tuple[str, str], Reference | None]:
    """Every column that became a lookup, and what it points at."""
    return {
        (table.name, col.name): col.ref
        for table in schema.tables
        for col in table.columns
        if col.ref is not None
    }


def _one_ref_schema(tmp_path: Path, declaration: str) -> Schema:
    """Risk, and an Action whose `RiskId` carries `declaration`."""
    schema, _ = pack(
        tmp_path,
        dbml=blocks(
            dbml_table("Risk", ID_PK, TITLE),
            dbml_table("Action", ID_PK, TITLE, declaration),
        ),
        mapping=entities("Risk", "Action"),
    )
    return schema


@pytest.mark.parametrize("symbol", _CARDINALITY_SYMBOLS)
def test_every_cardinality_symbol_parses_to_the_same_reference(
    tmp_path: Path, symbol: str,
) -> None:
    """`>`, `<`, `-` and `<>` are indistinguishable once parsed.

    DBML spells them many-to-one (`>`), one-to-many (`<`), one-to-one (`-`)
    and many-to-many (`<>`). A data engineer reads `<>` as a junction table
    and `<` as putting the column on the other list. Neither happens: the
    column that DECLARES the ref becomes the lookup, the target side gets
    nothing, and no third table appears. Parametrised rather than four
    assertions in one test so a symbol that starts behaving differently names
    itself.
    """
    schema = _one_ref_schema(tmp_path, f"RiskId int [ref: {symbol} Risk.Id]")
    assert _refs(schema) == _ONE_LOOKUP
    assert [t.name for t in schema.tables] == ["Risk", "Action"]


@pytest.mark.parametrize("symbol", _CARDINALITY_SYMBOLS)
def test_a_standalone_ref_carries_the_symbol_no_further_either(
    tmp_path: Path, symbol: str,
) -> None:
    """The `Ref:` block spelling resolves the same way as the inline one.

    Worth asking separately: the two spellings reach pydbml by different
    paths, and the standalone form is the one whose left and right sides a
    reader expects `<` to swap.
    """
    schema, _ = pack(
        tmp_path,
        dbml=blocks(
            dbml_table("Risk", ID_PK, TITLE),
            dbml_table("Action", ID_PK, TITLE, "RiskId int"),
            f"Ref: Action.RiskId {symbol} Risk.Id",
        ),
        mapping=entities("Risk", "Action"),
    )
    assert _refs(schema) == _ONE_LOOKUP


def test_the_second_ref_on_one_column_is_dropped(tmp_path: Path) -> None:
    """`_to_column` breaks after the first ref, so a column pointing at two
    tables deploys as a lookup into whichever was declared first, with nothing
    reported. Declaration order is the observable, which is why this asserts
    both orders rather than one."""
    def parsed(first: str, second: str) -> dict[tuple[str, str], Reference | None]:
        schema, _ = pack(
            tmp_path,
            dbml=blocks(
                dbml_table("Risk", ID_PK, TITLE),
                dbml_table("Issue", ID_PK, TITLE),
                dbml_table("Action", ID_PK, TITLE, "ParentId int"),
                f"Ref: Action.ParentId > {first}.Id",
                f"Ref: Action.ParentId > {second}.Id",
            ),
            mapping=entities("Risk", "Issue", "Action"),
        )
        return _refs(schema)

    assert parsed("Risk", "Issue") == {("Action", "ParentId"): Reference("Risk", "Id")}
    assert parsed("Issue", "Risk") == {("Action", "ParentId"): Reference("Issue", "Id")}


def test_the_refs_target_column_does_not_choose_what_the_lookup_shows(
    tmp_path: Path,
) -> None:
    """`Reference.target_column` is parsed and read by nothing.

    A ref at `Risk.Title` is recorded as such and still deploys as a lookup
    at the Risk LIST, displaying the column `display_column_for` picks. The
    right-hand side of a ref names the table; it does not name the field the
    picker shows.
    """
    schema = _one_ref_schema(tmp_path, "RiskId int [ref: > Risk.Title]")
    assert _refs(schema) == {("Action", "RiskId"): Reference("Risk", "Title")}
    declared = _declared(_entity("Risk"), _entity("Action"))
    assert lookup_display_columns(schema, declared, {}, set()) == {"Risk": "Title"}

    named = _declared(_entity("Risk", "Summary"), _entity("Action"))
    assert lookup_display_columns(schema, named, {}, set()) == {"Risk": "Summary"}


# --- No emitted lookup carries a relationship knob --------------------------

#: The properties that would make a lookup a relational constraint.
_RELATIONSHIP_KNOBS = (
    "RelationshipDeleteBehavior",
    "IsRelationship",
    "PrimaryKey",
    "LookupWebId",
    "Cascade",
    "Restrict",
)


def _every_lookup_route(tmp_path: Path) -> str:
    """A deploy script exercising all four routes a lookup is created by.

    `Risk.ParentId` is a self-reference, so it defers to the lookups phase;
    `Action.RiskId` is a `[unique]` single-value lookup, so it takes AddField
    and then a MERGE; `Action.WatchedRisks` is multi-value, so it takes
    createfieldasxml; and the projection on `RiskId` adds a dependent field.
    One fixture rather than four, because the claim is about the script as a
    whole and a route added later should have to opt out of it explicitly.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            dbml_table("Risk", ID_PK, TITLE, "ParentId int [ref: > Risk.Id]"),
            dbml_table(
                "Action",
                ID_PK,
                TITLE,
                "RiskId int [not null, unique, ref: > Risk.Id]",
                "WatchedRisks int[] [ref: > Risk.Id]",
            ),
        ),
        mapping=with_tail(
            entities("Risk", "Action"),
            "lookup_projections:\n  Action:\n    RiskId: [Title]\n",
        ),
    )
    # A script the build refuses is never generated, so the absence below would be vacuous.
    findings = validate_all(schema, bundle, NullExtension())
    assert [f.code.value for f in findings if f.severity == "error"] == []
    return generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z", resolved=resolve(schema, bundle.mapping),
    )


#: The one function allowed to name a knob: it reads an adopted lookup's
#: delete behaviour to report it (#576) and never writes it.
_DELETE_BEHAVIOUR_READER = "async function readLookupDeleteBehaviour("


def _reader_span(js: str) -> tuple[int, int]:
    """Where the delete-behaviour reader starts and ends in the emitted script.

    It ends at the first line after its signature that closes a block at the
    signature's own indentation, which is how the template lays it out.
    """
    assert js.count(_DELETE_BEHAVIOUR_READER) == 1
    start = js.index(_DELETE_BEHAVIOUR_READER)
    indent = start - js.rindex("\n", 0, start) - 1
    end = js.index("\n" + " " * indent + "}\n", start) + indent + 2
    return start, end


def test_the_deploy_script_never_writes_a_delete_behaviour_or_relationship_flag(
    tmp_path: Path,
) -> None:
    """A lookup this script CREATES is at SharePoint's default for every knob.

    Since #576 the deploy reads `RelationshipDeleteBehavior` on an adopted
    lookup and reports it, so the knob names appear in the script. What must
    still hold is that no write carries them. A write body is built from one
    of two places: the SCHEMA payload (every field body, the AddField
    parameters, and the schema XML a multi-value lookup is created by), or a
    literal in the script, such as a MERGE. The first is asserted over the
    parsed payload. The second is asserted over the script with the one
    reader excised, and that reader is pinned to a GET with no method or body.

    Microsoft documents each of `_RELATIONSHIP_KNOBS` on the [`Field`
    element](https://learn.microsoft.com/sharepoint/dev/schema/field-element-field).
    `Cascade` and `Restrict` are the two non-default values of
    `RelationshipDeleteBehavior` and are matched as bare words, so a knob
    arriving by any spelling is caught. The runtime tests in
    `test_deploy_runtime.py` also check every request body of an adopted run.
    """
    js = _every_lookup_route(tmp_path)
    payload = json.dumps(_schema_payload(js))
    assert [knob for knob in _RELATIONSHIP_KNOBS if knob in payload] == []

    start, end = _reader_span(js)
    reader = js[start:end]
    rest = js[:start] + js[end:]
    assert [knob for knob in _RELATIONSHIP_KNOBS if knob in rest] == []
    # The reader is a read: one fetch, no method, no body.
    assert reader.count("fetchWithRetry(") == 1, reader
    assert "method" not in reader, reader
    assert "body:" not in reader, reader
    assert "$select=${property}" in reader, reader


def _schema_payload(js: str) -> dict[str, Any]:
    """The SCHEMA object the emitted script carries, parsed.

    `raw_decode` rather than counting braces: a formatter or a validation
    message can carry a brace inside a string, and a counter reads that as
    structure.
    """
    marker = "const SCHEMA = "
    start = js.index(marker) + len(marker)
    payload: dict[str, Any] = json.JSONDecoder().raw_decode(js, start)[0]
    return payload


def test_the_fixture_really_does_reach_every_lookup_route(tmp_path: Path) -> None:
    """The control for the test above.

    Its assertion is an absence, so it would pass just as well against a
    script that created no lookups at all. This one proves the four routes
    are in the SCHEMA the absence was measured over, which is the same text:
    the deploy embeds this payload and branches on it.

    It reads the field objects and NOT the names of the helpers that create
    them. `deploy/_field_reconcile.js.j2` ships `addfield`,
    `createfieldasxml`, `LookupMulti` and `createDeclaredLookupField` in
    every deploy whether or not the schema declares a lookup (measured
    2026-09-14 against a two-column fixture with no ref at all), so a text
    search for those four passes on a script that creates no lookup, and the
    control would stay green while parsing dropped a fixture declaration.
    """
    payload = _schema_payload(_every_lookup_route(tmp_path))
    action = {
        field["title"]: field
        for entity in payload["lists"]
        if entity["title"] == "APP_Action"
        for field in entity["fields_phase1"]
    }

    # AddField, whose creation shape omits the properties the MERGE then sets.
    assert action["RiskId"]["lookup_creation_parameters"]["FieldTypeKind"] == 7
    assert action["RiskId"]["body"]["AllowMultipleValues"] is False
    # createfieldasxml, the one route a multi-value lookup can be created by.
    assert action["WatchedRisks"]["lookup_creation_xml"]["type"] == "LookupMulti"
    assert action["WatchedRisks"]["body"]["AllowMultipleValues"] is True
    # The dependent field a projection adds, beside the lookup it projects.
    assert [p["show_field"] for p in action["RiskId"]["projections"]] == ["Title"]
    # createDeclaredLookupField, which is what the deferred phase creates.
    deferred = [(d["list"], d["field"]["title"]) for d in payload["phase2_lookups"]]
    assert deferred == [("APP_Risk", "ParentId")]
