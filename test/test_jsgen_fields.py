# test/test_jsgen_fields.py
"""What a DBML column becomes: the schema entry, the create body, the patch.

Types and their defaults, lookups (immediate, deferred and self), choice and
multi-choice, calculated columns and their formulas, indexes, the uniqueness
constraint, and the built-in Title, which is patched rather than created and
so takes its own route through the generator.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from _builders import ID_PK, TITLE, table
from _model import as_library
from _packs import blocks, entities, entity, pack, with_tail, write_mapping
from _paths import FIXTURES
from test_jsgen import _CrossSiteExpansion, _generate_simple_js

from dbml_sharepoint.analysis.phases import phase_number as pn
from dbml_sharepoint.analysis.typemap import FieldKind, map_column
from dbml_sharepoint.analysis.validator import validate_all
from dbml_sharepoint.extension import BaseExtension
from dbml_sharepoint.generators import jsgen
from dbml_sharepoint.generators.jsgen import (
    _field_body,
    _meta_type,
    build_schema_json,
    generate_deploy_js,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import EntityMapping
from dbml_sharepoint.model.parser import Column, EnumDef, Reference, parse_dbml
from dbml_sharepoint.model.release import load_release


def test_schema_output_takes_indexes_from_dbml(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, "Status nvarchar", "indexes { Status }"),
        mapping=entities("Risk"),
    )
    output = build_schema_json(schema, bundle, "default")
    assert output["indexed_columns"] == [{"list": "APP_Risk", "field": "Status"}]


def test_a_lookup_targets_display_column_is_deployed_as_an_index(
    tmp_path: Path,
) -> None:
    """The validator counts this index against the ceiling; the deployer has to
    actually create it, or the picker breaks on the first large list."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Event", ID_PK, "EventRef nvarchar", "indexes { EventRef }"),
            table("FollowUp", ID_PK, "Event int [ref: > Event.Id]"),
        ),
        mapping=entities(entity("Event", display_column="EventRef"), "FollowUp"),
    )
    output = build_schema_json(schema, bundle, "default")
    assert {"list": "APP_Event", "field": "EventRef"} in output["indexed_columns"]
    # Once, not twice, when it is also declared in indexes { }.
    assert output["indexed_columns"].count(
        {"list": "APP_Event", "field": "EventRef"},
    ) == 1


def test_a_cross_site_ref_does_not_index_the_far_list(tmp_path: Path) -> None:
    """A cross_site_reference_columns entry is expanded into a Choice + URL pair
    on the source list, not a Lookup. Nothing enumerates the far list, so it has
    no picker. Emitting an index for it is a real Indexed=true MERGE on a
    customer tenant that buys nothing."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("FlowRunLog", ID_PK, "Title nvarchar"),
            table("Request", ID_PK, "Origin int [ref: > FlowRunLog.Id]"),
        ),
        mapping=blocks(entities("FlowRunLog", "Request"), """
            cross_site_reference_columns:
              - { entity: Request, column: Origin }
        """),
    )
    output = build_schema_json(
        schema, bundle, "default", extension=_CrossSiteExpansion(),
    )
    assert output["indexed_columns"] == []


def test_a_target_of_both_ref_kinds_still_gets_its_index(tmp_path: Path) -> None:
    """Per-pair, not per-entity: FlowRunLog is named by a cross-site ref AND by a
    real lookup, so its picker exists and its display column must stay indexed."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("FlowRunLog", ID_PK, "Title nvarchar"),
            table("Request", ID_PK, "Origin int [ref: > FlowRunLog.Id]"),
            table("Alert", ID_PK, "Source int [ref: > FlowRunLog.Id]"),
        ),
        mapping=blocks(entities("FlowRunLog", "Request", "Alert"), """
            cross_site_reference_columns:
              - { entity: Request, column: Origin }
        """),
    )
    output = build_schema_json(
        schema, bundle, "default", extension=_CrossSiteExpansion(),
    )
    assert output["indexed_columns"] == [{"list": "APP_FlowRunLog", "field": "Title"}]


def test_choice_and_lookup_unique_constraints_are_deployed(tmp_path: Path) -> None:
    """Single-value Choice and Lookup fields support SharePoint uniqueness."""
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            """
            Enum status {
              Open
              Closed
            }
            """,
            table("Project", ID_PK, TITLE),
            table(
                "Task",
                ID_PK,
                "Status status [not null, unique]",
                "Project int [not null, unique, ref: > Project.Id]",
            ),
        ),
        mapping=entities("Project", "Task"),
    )

    output = build_schema_json(schema, bundle, "default")
    task = next(item for item in output["lists"] if item["title"] == "APP_Task")
    fields = {field["title"]: field for field in task["fields_phase1"]}

    for name in ("Status", "Project"):
        assert fields[name]["body"]["EnforceUniqueValues"] is True
        assert fields[name]["body"]["Indexed"] is True

    # The Choice field is POSTed as this body, so its flags are set at
    # creation. A lookup cannot be: SharePoint only accepts it through
    # AddField, whose SP.FieldCreationInformation carries neither property.
    # Both therefore arrive by the MERGE reconcileDeclaredField issues right
    # after creation, so assert the split so a future change that drops that
    # reconcile call cannot leave a [unique] lookup silently non-unique.
    creation = fields["Project"]["lookup_creation_parameters"]
    assert "EnforceUniqueValues" not in creation
    assert "Indexed" not in creation
    assert "lookup_creation_parameters" not in fields["Status"]


def test_boolean_default_only_emitted_when_declared() -> None:
    """Regression: the Boolean branch must only emit ``DefaultValue`` when the
    DBML column actually declares a default. Previously it unconditionally
    wrote ``"0"`` for unset booleans (``None`` is falsy in the ternary),
    silently forcing optional booleans to default to false and erasing the
    null-vs-false distinction downstream flows may rely on.
    """
    no_default = _field_body(Column(name="QuorumMet", type="boolean"), {}, "APP_")
    assert no_default is not None
    assert "DefaultValue" not in no_default["body"]

    # NB: keep as a list, because a dict would collapse False/0 and True/1 into one
    # key each (Python treats them as equal), hiding the int cases.
    cases: list[tuple[str | int | bool, str]] = [
        (False, "0"),
        (True, "1"),
        (0, "0"),
        (1, "1"),
    ]
    for declared, expected in cases:
        field = _field_body(
            Column(name="Flag", type="boolean", default=declared), {}, "APP_",
        )
        assert field is not None
        assert field["body"]["DefaultValue"] == expected, (declared, expected)


def test_text_default_is_emitted_when_declared() -> None:
    """Text defaults are required for provisioned, site-specific metadata.

    SharePoint applies the field default before validating a normal list-item
    create, so a build can stamp organisation constants
    without an after-create flow on every list.
    """
    field = _field_body(
        Column(name="OrgUnitCode", type="nvarchar", default="UNIT-A"),
        {},
        "APP_",
    )
    assert field is not None
    assert field["body"]["DefaultValue"] == "UNIT-A"


def test_number_default_is_string_in_create_and_merge_shapes() -> None:
    """SP.Field.DefaultValue is String even when the field is numeric."""
    field = _field_body(Column(name="SortOrder", type="int", default=0), {}, "APP_")
    assert field is not None
    assert field["body"]["DefaultValue"] == "0"

    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    project = next(lst for lst in schema_json["lists"] if lst["title"] == "APP_Project")
    sort_order = next(
        entry for entry in project["fields_phase1"] if entry["title"] == "SortOrder"
    )
    assert sort_order["body"]["DefaultValue"] == "0"  # initial field POST
    assert {
        "list": "APP_Project",
        "field": "SortOrder",
        "metadata_type": "SP.FieldNumber",
        "default_value": "0",
        "default_formula": None,
    } in schema_json["field_defaults"]  # Phase 2.4 field MERGE

    js = _generate_simple_js()
    assert '"DefaultValue": "0"' in js
    assert '"default_value": "0"' in js
    assert "defaultBody.DefaultValue = entry.fieldDefault.default_value" in js


def test_longtext_emits_plain_multiline_note_field() -> None:
    """Opaque connector values can exceed SharePoint URL/Text's 255 chars.

    ``longtext`` must therefore emit a plain multi-line Note field without
    silently enabling rich text or append-only history.
    """
    field = _field_body(Column(name="JoinWebUrl", type="longtext"), {}, "APP_")

    assert field is not None
    assert field["body"] == {
        "Title": "JoinWebUrl",
        "FieldTypeKind": 3,
        "__metadata": {"type": "SP.FieldMultiLineText"},
        "RichText": False,
        "NumberOfLines": 6,
        "AppendOnly": False,
    }


def test_hyperlink_emits_field_url_display_format() -> None:
    """SP.FieldUrl writes DisplayFormat; UrlFormat is not a REST property."""
    field = _field_body(Column(name="TermsOfReference", type="hyperlink"), {}, "APP_")

    assert field is not None
    assert field["body"] == {
        "Title": "TermsOfReference",
        "FieldTypeKind": 11,
        "__metadata": {"type": "SP.FieldUrl"},
        "DisplayFormat": 0,
    }


def test_meta_type_names_the_kind_it_cannot_map() -> None:
    """A field kind absent from ENTITY_TYPE_BY_KIND must name itself and the
    map to fix in its error, rather than raising a bare KeyError that leaves
    the caller to work out which kind and which map were involved.
    """
    with pytest.raises(ValueError, match="ENTITY_TYPE_BY_KIND") as excinfo:
        _meta_type(cast("FieldKind", "Bogus"))
    assert "'Bogus'" in str(excinfo.value)


def test_field_body_refuses_a_kind_the_match_does_not_know(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """mypy is the real gate that keeps `match sp.kind` exhaustive; this pins
    the runtime shape of its default arm so a later refactor cannot turn
    `assert_never` into a silent fall-through that drops the field's body.
    """
    col = Column(name="Whatever", type="nvarchar")
    bogus = replace(map_column(col, set()), kind=cast("FieldKind", "Bogus"))
    monkeypatch.setattr(jsgen, "_meta_type", lambda kind: "SP.FieldText")
    monkeypatch.setattr(jsgen, "map_column", lambda col, enum_names: bogus)

    with pytest.raises(AssertionError):
        jsgen._field_body(col, {}, "APP_")


def test_declared_defaults_are_reconciled_on_existing_fields() -> None:
    """A skipped existing field must still receive its declared default."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert {
        "list": "APP_Project",
        "field": "Status",
        "metadata_type": "SP.FieldChoice",
        "default_value": "Open",
        "default_formula": None,
    } in schema_json["field_defaults"]

    js = _generate_simple_js()
    assert f"Starting Phase {pn('defaults')}: field defaults" in js
    assert "for (const fieldDefault of SCHEMA.field_defaults)" in js


def test_lookup_uses_target_display_column() -> None:
    """A1: a lookup into a target whose mapping declares display_column emits
    that field in both the desired field shape and AddField parameters, not the
    (possibly empty) built-in Title."""
    col = Column(name="Chair", type="int", ref=Reference("Membership", "Id"))
    entities = {
        "Membership": EntityMapping(
            name="Membership", kind="List", base_template=100,
            site_role="default", display_column="DisplayName",
        ),
    }
    field = _field_body(col, {}, "APP_", entities)
    assert field is not None
    assert field["body"]["LookupField"] == "DisplayName"
    assert field["lookup_creation_parameters"] == {
        "__metadata": {"type": "SP.FieldCreationInformation"},
        "FieldTypeKind": 7,
        "Title": "Chair",
        "Required": False,
        "LookupFieldName": "DisplayName",
    }
    assert field["target_list"] == "APP_Membership"


def test_lookup_defaults_to_title_without_display_column() -> None:
    """A1: with no display_column on the target, the lookup falls back to the
    built-in Title (backward-compatible default)."""
    col = Column(name="Project", type="int", ref=Reference("Project", "Id"))
    field = _field_body(col, {}, "APP_", {})
    assert field is not None
    assert field["body"]["LookupField"] == "Title"
    assert field["lookup_creation_parameters"]["LookupFieldName"] == "Title"


def _lookup_create_helper(js: str) -> str:
    """The body of `declaredFieldCreateOp`, the one route choice every create reads.

    Phase 1 hands it to BatchWriter and the deferred phase hands it to
    postJson, so the ChangeSet part and the single write share it.
    """
    return js.split("function declaredFieldCreateOp", 1)[1].split("\n  }", 1)[0]


def test_immediate_lookup_uses_addfield_creation_information() -> None:
    """A normal Phase-1 lookup uses FieldCollection.AddField's exact shape."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    task = next(item for item in schema_json["lists"] if item["title"] == "APP_Task")
    lookup = next(field for field in task["fields_phase1"] if field["title"] == "Project")
    assert lookup["lookup_creation_parameters"] == {
        "__metadata": {"type": "SP.FieldCreationInformation"},
        "FieldTypeKind": 7,
        "Title": "Project",
        "Required": True,
        "LookupFieldName": "Title",
    }
    assert "LookupListId" not in lookup["lookup_creation_parameters"]

    js = _generate_simple_js()
    phase1 = js.split(f"Starting Phase {pn('lists')}")[1].split(
        f"Starting Phase {pn('lookups')}")[0]

    # Every create reads one shared route choice, because a multi-value lookup
    # needs a second route (createfieldasxml) that AddField cannot express.
    # AddField is still what a single-value lookup takes.
    assert "declaredFieldCreateOp(list.title, col, targetGuid)" in phase1
    assert "{ ...col.body, LookupList:" not in phase1
    assert "reconcileDeclaredField" in phase1

    helper = _lookup_create_helper(js)
    assert "...field.lookup_creation_parameters" in helper
    assert "LookupListId: targetGuid" in helper
    assert "/fields/addfield`" in helper


def test_deferred_circular_lookup_uses_addfield_creation_information(
    tmp_path: Path,
) -> None:
    """A circular dependency deferred to the deferred-lookups phase uses the same AddField API."""
    write_mapping(tmp_path, entities("A", "B"), name="mapping.yaml")
    schema = parse_dbml(FIXTURES / "circular.dbml")
    bundle = load_mapping(tmp_path / "mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")

    schema_json = build_schema_json(schema, bundle, "default")
    assert schema_json["phase2_lookups"]
    for deferred in schema_json["phase2_lookups"]:
        parameters = deferred["field"]["lookup_creation_parameters"]
        assert parameters["__metadata"] == {
            "type": "SP.FieldCreationInformation",
        }
        assert parameters["FieldTypeKind"] == 7
        assert parameters["LookupFieldName"] == "Title"
        assert "LookupListId" not in parameters

    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="circular.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    phase2 = js.split(f"Starting Phase {pn('lookups')}")[1].split(
        f"Starting Phase {pn('indexes')}")[0]
    assert "await createDeclaredLookupField(lookup.list, lookup.field," in phase2
    assert "{ ...lookup.field.body, LookupList:" not in phase2
    assert "reconcileDeclaredField" in phase2

    helper = _lookup_create_helper(js)
    assert "...field.lookup_creation_parameters" in helper
    assert "LookupListId: targetGuid" in helper
    assert "/fields/addfield`" in helper


def test_self_lookup_is_deferred_with_addfield_parameters(tmp_path: Path) -> None:
    """A self-reference remains deferred and carries a complete lookup spec."""
    write_mapping(tmp_path, entities("Node"), name="mapping.yaml")
    schema = parse_dbml(FIXTURES / "self-ref.dbml")
    bundle = load_mapping(tmp_path / "mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert len(schema_json["phase2_lookups"]) == 1
    deferred = schema_json["phase2_lookups"][0]
    assert deferred["list"] == "APP_Node"
    assert deferred["target_list"] == "APP_Node"
    assert deferred["field"]["lookup_creation_parameters"] == {
        "__metadata": {"type": "SP.FieldCreationInformation"},
        "FieldTypeKind": 7,
        "Title": "Parent",
        "Required": False,
        "LookupFieldName": "Title",
    }
    all_items = next(view for view in schema_json["views"] if view["title"] == "All Items")
    assert "Parent" in all_items["view_fields"]

    js = generate_deploy_js(
        schema=schema,
        bundle=bundle,
        release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="self-ref.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert '"target_list": "APP_Node"' in js
    assert '"type": "SP.FieldCreationInformation"' in js
    assert '"LookupFieldName": "Title"' in js
    assert "/fields/addfield`" in js


def test_choice_fields_disable_fill_in_and_preserve_exact_order() -> None:
    """Choice adoption cannot silently accept extra/reordered free-form values."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")
    project = next(lst for lst in schema_json["lists"] if lst["title"] == "APP_Project")
    status = next(field for field in project["fields_phase1"] if field["title"] == "Status")

    assert status["body"]["Choices"] == {"results": ["Open", "Closed"]}
    assert status["body"]["FillInChoice"] is False


def test_a_multi_value_enum_is_created_as_a_multichoice_field() -> None:
    """MEASURED on a live tenant, 2026-08-10. A plain POST to `/fields` with
    `__metadata: {type: 'SP.FieldMultiChoice'}`, `FieldTypeKind: 15` and
    `Choices: {results: [...]}` returned HTTP 201, and the field read back
    `TypeAsString="MultiChoice"`, `FieldTypeKind=15` and `Choices` as
    `Collection(Edm.String)`.

    So no new creation machinery: Lookup is still the one field type that
    needs the `AddField` detour, and this is not in that class. That is what
    made MultiChoice the multi-value type worth building first, and the claim
    was a probe question until this date rather than an inference from Learn.

    `FillInChoice: false` for the same reason the single-value arm sets it:
    adoption of an existing column must not silently accept free-form values
    that were never declared.
    """
    field = _field_body(
        Column(name="Events", type="audit_event[]"),
        {"audit_event": EnumDef(name="audit_event", members=["View", "Edit", "Export"])},
        "APP_",
    )

    assert field is not None
    assert field["body"]["__metadata"] == {"type": "SP.FieldMultiChoice"}
    assert field["body"]["FieldTypeKind"] == 15
    assert field["body"]["Choices"] == {"results": ["View", "Edit", "Export"]}
    assert field["body"]["FillInChoice"] is False


def test_the_multichoice_kind_is_wired_into_the_reconciler() -> None:
    """`TYPE_AS_STRING_BY_KIND` is what `declaredFieldState` reads to decide
    the immutable shape a field must keep. Without an entry for kind 15 it
    throws `unsupported declared FieldTypeKind` the moment Phase 2.1 creates
    one, aborting the whole deployment -- so the map has to learn the
    vocabulary in the same change that starts emitting the kind.

    `MultiChoice` is what SharePoint itself reported on read-back, not a name
    transcribed from a documentation page.

    Double-quoted since the map became `| tojson` of
    `typemap.TYPE_AS_STRING_PAIRS` rather than a hand-written JS literal.
    `test_typemap.test_the_deploy_script_map_covers_every_field_kind` now
    asserts the whole vocabulary rather than one member; this stays as the
    named regression for kind 15.
    """
    assert '[15, "MultiChoice"]' in _generate_simple_js()


def test_no_title_list_gets_required_false_title_patch(tmp_path: Path) -> None:
    """A4: a list with no DBML Title column gets its built-in Title patched
    Required:false so programmatic inserts / manual entry aren't blocked."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Attendance", ID_PK, "Notes nvarchar"),
        mapping=entities("Attendance"),
    )
    sj = build_schema_json(schema, bundle, "default")
    att = next(lst for lst in sj["lists"] if lst["title"] == "APP_Attendance")
    assert att["title_patch"] is not None
    assert att["title_patch"]["Required"] is False


def test_a_library_gets_no_title_patch_when_it_would_only_clear_required(
    tmp_path: Path,
) -> None:
    """The same list as a library declares no patch at all.

    MEASURED 2026-09-13 on a live document library: the built-in Title reads
    Sealed true and the maintenance unseal's MERGE of Sealed=false is refused
    HTTP 400, so the patch could never land and the run aborted before any
    structural phase. It would buy nothing there in any case, because a
    required column on a library is not enforced at REST upload.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=table("Attendance", ID_PK, "Notes nvarchar"),
        mapping=entities("Attendance"),
    )
    sj = build_schema_json(schema, as_library(bundle, "Attendance"), "default")
    att = next(lst for lst in sj["lists"] if lst["title"] == "APP_Attendance")
    assert att["title_patch"] is None


def test_a_library_still_patches_title_for_a_declared_rename(
    tmp_path: Path,
) -> None:
    """A rename is a different write, and nothing has measured it.

    Only the Required-clearing patch is dropped above. Whether a rename of a
    library's sealed Title is refused as the unseal was is unknown, so the
    write stays declared: a run that tries one fails closed and says so,
    rather than skipping it and leaving a column nobody renamed.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=table("Attendance", ID_PK, "Notes nvarchar"),
        mapping=with_tail(entities("Attendance"), "\n".join([
            "display_names:", "  mode: auto", "  overrides:", "    Attendance:",
            "      Title: 'Session'",
        ])),
    )
    sj = build_schema_json(schema, as_library(bundle, "Attendance"), "default")
    att = next(lst for lst in sj["lists"] if lst["title"] == "APP_Attendance")
    assert att["title_patch"]["Title"] == "Session"


def test_generated_condition_fields_are_typed_in_schema_output(tmp_path: Path) -> None:
    """Built-in Title and cross-site expansion fields can drive conditions
    even though neither appears as an ordinary rendered DBML column."""

    class Expansion(BaseExtension):
        def expand_column(
            self, table: Any, column: Any, bundle: Any,
        ) -> list[dict[str, Any]] | None:
            return [
                {
                    "title": "UnitAbbreviation",
                    "body": {
                        "__metadata": {"type": "SP.FieldChoice"},
                        "Title": "UnitAbbreviation",
                        "FieldTypeKind": 6,
                        "Choices": {"results": ["A"]},
                        "Required": False,
                    },
                },
                {
                    "title": "UnitSiteUrl",
                    "body": {
                        "__metadata": {"type": "SP.FieldUrl"},
                        "Title": "UnitSiteUrl",
                        "FieldTypeKind": 11,
                        "Required": False,
                    },
                },
            ]

    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            table("Unit", ID_PK),
            table("Risk", ID_PK, "Unit int [ref: > Unit.Id]", "Note nvarchar"),
        ),
        mapping=blocks(entities("Unit", "Risk"), """
            cross_site_reference_columns:
              - { entity: Risk, column: Unit }
            form_visibility:
              Risk:
                columns:
                  Note:
                    when:
                      any_of:
                        - { field: Title, op: eq, value: Named }
                        - { field: UnitAbbreviation, op: eq, value: A }
            views:
              Risk:
                - title: A unit
                  fields: [UnitAbbreviation, Note]
                  where: [{ field: UnitAbbreviation, op: eq, value: A }]
            list_validation:
              Risk:
                when: [{ field: Title, op: is_not_null }]
                message: A title is required.
        """),
    )
    assert not [
        f for f in validate_all(schema, bundle, Expansion()) if f.severity == "error"
    ]
    output = build_schema_json(schema, bundle, "default", extension=Expansion())
    risk = next(item for item in output["lists"] if item["title"] == "APP_Risk")
    note = next(item for item in risk["fields_phase1"] if item["title"] == "Note")
    assert "[$Title]" in note["client_validation_formula"]
    assert "[$UnitAbbreviation]" in note["client_validation_formula"]
    assert risk["validation_formula"] == "=NOT(ISBLANK([Title]))"
    unit_view = next(item for item in output["views"] if item["title"] == "A unit")
    assert '<Value Type="Text">A</Value>' in unit_view["caml_query"]


def test_calculated_field_rendered_with_formula_and_output_type() -> None:
    """calculated_* columns render as SP.FieldCalculated with the mapping's
    formula and the right OutputType; they are never marked Required."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "SP.FieldCalculated" in js
    assert '"FieldTypeKind": 17' in js
    assert '"OutputType": 9' in js   # RiskScore -> Number
    assert '"OutputType": 2' in js   # RiskBand -> Text
    assert "IF([Severity]=" in js    # the formula body made it through


def test_calculated_fields_are_created_after_referenced_columns(
    tmp_path: Path,
) -> None:
    """SharePoint validates a calculated formula's [Column] references when
    the field is CREATED, so a calculated field POSTed before a column its
    formula references fails with HTTP 500 ("The formula refers to a column
    that does not exist"). Seen live on a register pack: the
    MatrixVersion guard column was declared after the two matrix formulas
    that reference it. Phase-1 field order must keep plain fields in
    declaration order (which drives form order; calculated fields never
    appear on entry forms) and move calculated fields after them,
    topologically ordered among themselves for calc-on-calc chains."""
    # Score depends on Rating (calc-on-calc) although declared first;
    # Rating depends on the plain columns declared AFTER both.
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            """
            Enum severity {
              "Low"
              "High"
            }
            """,
            table(
                "Risk", ID_PK, TITLE,
                "Severity severity",
                "Score calculated_number",
                "Rating calculated_text",
                "MatrixVersion nvarchar",
            ),
        ),
        mapping=blocks(entities("Risk"), """
            calculated_formulas:
              Risk:
                Score: '=IF([Rating]="High",10,1)'
                Rating: '=IF([MatrixVersion]="13.0",[Severity],"")'
        """),
    )
    risk = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Risk"
    )
    assert [field["title"] for field in risk["fields_phase1"]] == [
        "Severity", "MatrixVersion", "Rating", "Score",
    ]


def test_calculated_field_shape_gate_expects_intrinsic_read_only() -> None:
    """SP.FieldCalculated is intrinsically ReadOnlyField=true (users never
    write it), so a blanket writability assertion rejects every calculated
    field the deployer itself created a moment earlier. The rerun/resume
    path fails in preflight with 'read-only or sealed; expected a writable
    declared field'. The shape gate must expect read-only exactly for
    declared calculated fields, still reject read-only for every other
    declared type, and treat sealed as fatal for all."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "const expectReadOnly = desired.typeAsString === 'Calculated'" in js
    assert "actual.ReadOnlyField !== expectReadOnly" in js
    assert "is sealed; expected an unsealed declared field" in js
    assert "expected a writable declared field" not in js


def test_formula_comparison_decodes_xml_character_entities() -> None:
    """SharePoint stores a calculated field's Formula in the field schema XML
    and returns it with XML character entities intact (a formula containing
    `<>` reads back as `&lt;&gt;`), so a byte-for-byte comparison never
    converges: reconciliation MERGEs the identical formula and the readback
    'drift' persists ('did not retain declared mutable setting(s): Formula')
    on every rerun. Formula comparison must canonicalise both sides by
    decoding XML entities (amp last, so double-encoded text stays distinct)."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    assert "if (name === 'Formula') return canonicalFormula(value)" in js
    assert "replace(/&lt;/g, '<')" in js
    assert "replace(/&gt;/g, '>')" in js
    assert "replace(/&quot;/g, '\"')" in js
    assert "replace(/&amp;/g, '&')" in js
    assert js.index("replace(/&lt;/g") < js.index("replace(/&amp;/g")


def test_formula_comparison_strips_removable_reference_brackets() -> None:
    """SharePoint canonicalises a stored formula's column references: square
    brackets around names that do not need delimiting are stripped
    (`[Likelihood]` is stored and read back as `Likelihood`), so a
    byte-for-byte comparison of declared vs readback never converges even
    after XML entity decoding (the same trap the PnP provisioning engine
    documents). The comparison must canonicalise both sides by removing
    removable brackets OUTSIDE string literals only: bracket text inside a
    quoted constant is data, not a reference."""
    js = _generate_simple_js()
    probe = js.split("const canonicalFormula")[1].split("function normalizeDerivedValue")[0]
    assert 'split(/("(?:""|[^"])*")/)' in probe
    assert "replace(/\\[([A-Za-z0-9_]+)\\]/g, '$1')" in probe
    assert "i % 2 === 1 ? token" in probe  # string-literal tokens pass through


def test_mutable_drift_errors_carry_declared_and_readback_values() -> None:
    """A drift that survives reconciliation must be diagnosable from the
    console log alone: the error names each setting WITH the declared and
    readback values, not just the property name (live debugging of a register
    formula loop burned three paste round-trips on 'Formula' with no
    values)."""
    js = _generate_simple_js()
    assert "const drift = (name, declaredValue, actualValue, note)" in js
    assert "declared ${JSON.stringify(declaredValue)}" in js
    assert "readback ${JSON.stringify(actualValue)}" in js
    assert "did not retain declared mutable setting(s)" in js


def test_calculated_kind_wired_into_reconciliation_machinery() -> None:
    """FieldTypeKind 17 must be declared in TYPE_AS_STRING_BY_KIND and
    Formula/OutputType must be probed + reconciled derived properties.
    Without them declaredFieldState throws immediately after Phase 2.1 creates
    a calculated field, aborting the whole deployment."""
    schema = parse_dbml(FIXTURES / "calculated.dbml")
    bundle = load_mapping(FIXTURES / "calculated-mapping.yaml")
    release = load_release(FIXTURES / "release.yaml")
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="calculated.dbml",
        source_mtime="2026-05-04T00:00:00Z",
        generated_at="2026-05-04T00:00:00Z",
    )
    # Double-quoted since the map became `| tojson` of the Python pairing.
    assert '[17, "Calculated"]' in js
    # Once in readFieldShape's probe list, once in DERIVED_FIELD_PROPERTIES.
    # Both are now rendered from typemap.DERIVED_FIELD_PROPERTIES, hence the
    # JSON spelling.
    assert js.count('"Formula", "OutputType"') >= 2


def test_field_probe_treats_missing_column_400_as_absent() -> None:
    """SP's fields/getbyinternalnameortitle returns HTTP 400
    (System.ArgumentException, locale-invariant code -2147024809, "Column 'X'
    does not exist") for a missing field, not 404 like the list/group
    getters. Treating only 404 as absent aborted every clean first provision
    in Phase 2.1: each just-created list's declared fields all failed their
    shape probe before they could be created. The probe must map exactly that
    400 shape to "field absent" (the create path) and keep every other
    non-ok response fatal."""
    js = _generate_simple_js()
    helper = js.split("const isAbsent400")[1].split("async function")[0]
    assert "-2147024809" in helper
    assert "System.ArgumentException" in helper
    field_probe = js.split("async function readFieldShape")[1].split("async function")[0]
    assert "isAbsent400(r.status, text)" in field_probe
    assert "return null" in field_probe
    # The narrow match must not relax the fatal path for other errors.
    assert "shape probe failed" in field_probe


def test_field_shapes_keep_internal_names_and_titles_apart() -> None:
    """getbyinternalnameortitle resolves an internal name first. Folding both
    into one keyspace lets one field's display Title shadow another field's
    InternalName when they match case-insensitively, and the shadowed field
    is then read as an impostor, aborting preflight over a column SharePoint
    resolves perfectly well."""
    js = _generate_simple_js()
    assert "const byInternal = new Map();" in js
    assert "const byTitle = new Map();" in js
    assert "byInternal.get(nameKey(name)) || byTitle.get(nameKey(name))" in js, (
        "internal names must take precedence over display titles"
    )


# --- The built-in Title takes a display title --------------------------------
#
# MEASURED on a live tenant 2026-09-07, test/manual/title-rename-probe.js,
# revision 709c786d. A MERGE of a new Title onto a base-template list's
# built-in Title answered HTTP 204 and the field read back Title="Risk
# Statement", InternalName="Title", StaticName="Title". Both addresses still
# resolved, and an item POST carrying `Title` still created a row.
#
# The constraint the same run found, and the reason these two tests are one
# pair: a calculated column whose formula said `[Title]` was REFUSED after the
# rename, HTTP 500 "The formula refers to a column that does not exist", while
# the identical formula naming the new display title was accepted. SharePoint
# resolves a formula by DISPLAY name, so a bundle that renames Title without
# rewriting the formulas that reference it deploys a broken column.


def _titled(
    tmp_path: Path, override: str, *, formula: str | None = None,
) -> dict[str, Any]:
    tail = ["display_names:", "  mode: auto", "  overrides:", "    Risk:",
            f"      Title: {override!r}"]
    if formula is not None:
        tail += ["calculated_formulas:", "  Risk:", f"    Live: {formula!r}"]
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE, *(
            ["Live calculated_text"] if formula is not None else []
        )),
        mapping=with_tail(entities("Risk"), "\n".join(tail)),
    )
    sj = build_schema_json(schema, bundle, "default")
    return next(lst for lst in sj["lists"] if lst["title"] == "APP_Risk")


def test_a_display_name_override_renames_the_built_in_title(
    tmp_path: Path,
) -> None:
    """The patch carries the declared title, so the column is actually renamed.

    #330 found the override reaching the view width map, the form body section
    field list and the Power Query rename while never reaching the column, so
    the bundle referenced a display title the deploy did not create. #426
    refused the declaration because the rename was unmeasured. It is measured
    now, so the patch carries it and the four halves agree.
    """
    risk = _titled(tmp_path, "Risk Statement")
    assert risk["title_patch"]["Title"] == "Risk Statement"


def test_an_undeclared_title_keeps_the_patch_free_of_a_display_title(
    tmp_path: Path,
) -> None:
    """`auto` resolves Title to "Title", which is the name it already has.

    Emitting the no-op would put a redundant property in every bundle every
    family ships, and a reviewer reading a deploy diff could not tell it from
    a real rename.
    """
    risk = _titled(tmp_path, "Title")
    assert "Title" not in risk["title_patch"]


def test_a_formula_referencing_title_is_rewritten_to_its_display_name(
    tmp_path: Path,
) -> None:
    """The constraint the probe found, in the one place that can honour it.

    `display_map` is built from the declared fields, and Title is not one, so
    before this the rewrite left `[Title]` alone and the calculated create was
    refused on the live site with "The formula refers to a column that does
    not exist".
    """
    risk = _titled(
        tmp_path, "Risk Statement", formula='=CONCATENATE("x",[Title])',
    )
    live = next(f for f in risk["fields_phase1"] if f["title"] == "Live")
    assert live["body"]["Formula"] == '=CONCATENATE("x",[Risk Statement])'


def test_a_declared_default_formula_rides_the_create_body_and_the_defaults_phase(
    tmp_path: Path,
) -> None:
    """DefaultFormula is emitted beside DefaultValue: in the create body, and
    mirrored into the field_defaults entry the defaults phase re-applies."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Saq", ID_PK, TITLE, "PeriodYear int", "Due date"),
        mapping=blocks(entities("Saq"), """
            default_formulas:
              Saq:
                PeriodYear: "=YEAR(TODAY())"
                Due: "=TODAY()"
        """),
    )
    schema_json = build_schema_json(schema, bundle, "default")
    bodies = {f["title"]: f["body"] for f in schema_json["lists"][0]["fields_phase1"]}
    assert bodies["PeriodYear"]["DefaultFormula"] == "=YEAR(TODAY())"
    assert "DefaultValue" not in bodies["PeriodYear"]
    assert {
        "list": "APP_Saq", "field": "PeriodYear", "metadata_type": "SP.FieldNumber",
        "default_value": None, "default_formula": "=YEAR(TODAY())",
    } in schema_json["field_defaults"]
    assert {
        "list": "APP_Saq", "field": "Due", "metadata_type": "SP.FieldDateTime",
        "default_value": None, "default_formula": "=TODAY()",
    } in schema_json["field_defaults"]


def test_a_column_without_a_default_formula_carries_no_such_key() -> None:
    schema_json = build_schema_json(
        parse_dbml(FIXTURES / "simple.dbml"),
        load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        "default",
    )
    assert all(
        "DefaultFormula" not in f["body"]
        for lst in schema_json["lists"]
        for f in lst["fields_phase1"]
    )
    assert all(entry["default_formula"] is None for entry in schema_json["field_defaults"])


def test_the_deploy_reconciles_and_reads_back_the_default_formula() -> None:
    """Every place a DefaultValue is handled handles the formula beside it."""
    js = _generate_simple_js()
    assert "defaultFormula: normalizeDefaultFormula(field.body.DefaultFormula)" in js
    assert "normalizeDefaultFormula(actual.DefaultFormula) !== desired.defaultFormula" in js
    assert "patchBody.DefaultFormula = field.body.DefaultFormula" in js
    assert "drift(\n        'DefaultFormula'" in js
    # MEASURED 2026-09-13: clearing a formula is accepted and does nothing,
    # so the surviving drift has to name the manual step.
    assert "remove it in the column settings page" in js
    # The same run: a MERGE carrying DefaultValue drops the formula beside it.
    assert "if ('DefaultValue' in patchBody && desired.defaultFormula !== null)" in js
    assert "defaultBody.DefaultFormula = entry.fieldDefault.default_formula" in js
    assert "DefaultFormula readback did not match the declared formula" in js
    assert "shape.DefaultFormula === null || typeof shape.DefaultFormula === 'string'" in js


# --- A unique Title deploys its constraint -----------------------------------
#
# The failure this closes is the one AGENTS.md opens with. A DBML
# `Title [unique]` produced no uniqueness constraint on the deployed list, saved,
# read back clean and passed every deploy phase, because jsgen routes Title into
# `title_patch` and `continue`s past the field-body builder where
# `EnforceUniqueValues` is written (#307). `programme-governance` declares one,
# so this was shipping.
#
# NOT a claim that SharePoint accepts the write. Nothing has measured a MERGE of
# EnforceUniqueValues onto a BUILT-IN Title: `field.unique.*` is a column the
# probe created and `field.title.*` never asked. The patch goes through
# `reconcileDeclaredField` like every other column, so a refusal surfaces as a
# named failure instead of a silent drop, which is the point.


def _stakeholder_title_patch(tmp_path: Path, *, unique: bool) -> dict[str, Any]:
    declaration = "Title nvarchar [not null, unique]" if unique else TITLE
    schema, bundle = pack(
        tmp_path,
        dbml=table("Stakeholder", ID_PK, declaration),
        mapping=entities("Stakeholder"),
    )
    sj = build_schema_json(schema, bundle, "default")
    built = next(lst for lst in sj["lists"] if lst["title"] == "APP_Stakeholder")
    patch = built["title_patch"]
    assert patch is not None
    return cast("dict[str, Any]", patch)


def test_a_unique_title_patches_enforce_unique_values(tmp_path: Path) -> None:
    """The declaration reaches the column instead of being dropped."""
    patch = _stakeholder_title_patch(tmp_path, unique=True)
    assert patch["EnforceUniqueValues"] is True


def test_a_unique_title_is_indexed_with_the_constraint(tmp_path: Path) -> None:
    """The pair the field-body builder writes together, written together here.

    SharePoint will not enforce uniqueness on an unindexed column, so sending
    one without the other is a constraint that cannot take.
    """
    patch = _stakeholder_title_patch(tmp_path, unique=True)
    assert patch["Indexed"] is True


def test_a_title_that_is_not_unique_declares_nothing_about_the_constraint(
    tmp_path: Path,
) -> None:
    """ABSENT, not `False`, and the distinction is the whole safety of this.

    `_field_reconcile.js.j2` reads `field.body.EnforceUniqueValues === true`
    off this same patch. An explicit `False` is a declaration ABOUT the
    property rather than silence about it, and it would make every family that
    ships a plain Title start asserting the constraint is off.
    """
    patch = _stakeholder_title_patch(tmp_path, unique=False)
    assert "EnforceUniqueValues" not in patch
    assert "Indexed" not in patch


def test_the_reconciler_reads_the_declared_title_shape_off_the_patch() -> None:
    """The coupling that makes one edit close both halves of #307.

    An operator who noticed the missing constraint and ticked the box in list
    settings had it turned off again by the next paste, because the reconciler
    builds the declared Title shape out of this same body and compared a live
    `true` against a declared `false`. Pinned here because the fix relies on
    it: if the reconciler ever stopped reading the patch, the deploy would
    apply the constraint and the reconciler would go back to removing it, and
    nothing else in the suite would notice.
    """
    js = _generate_simple_js()
    assert "{ ...list.title_patch, FieldTypeKind: 2 }" in js
