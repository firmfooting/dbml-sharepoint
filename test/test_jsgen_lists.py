# test/test_jsgen_lists.py
"""The list and library objects: their settings, and how a run finds them again.

Versioning, content types, the library kind with its folders and view scope,
and the Description a list carries, which is where the provenance marker
lives. Adoption keys on that marker and on the previous titles a rename
leaves behind, so both are pinned against what assess.js looks for.
"""

from pathlib import Path
from typing import Any

from _builders import ID_PK, TITLE, table
from _model import bundle as make_bundle
from _model import schema as make_schema
from _model import table as make_table
from _packs import blocks, entities, pack
from _paths import FIXTURES
from test_jsgen import _generate_simple_js

from dbml_sharepoint.analysis import provenance
from dbml_sharepoint.analysis.list_description import (
    DESCRIPTION_LIMIT,
    MARKER_GROWTH_RESERVE,
    UNNAMED_FAMILY,
    family_for,
    list_description,
    marker_for,
    note_budget,
)
from dbml_sharepoint.generators.assessgen import assess_targets
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import EntityMapping
from dbml_sharepoint.model.parser import parse_dbml


def test_each_list_emits_one_exact_adoption_marker() -> None:
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    built = build_schema_json(schema, bundle, "default")
    markers = {entry["title"]: entry["expected_marker"] for entry in built["lists"]}
    assessed = dict(assess_targets(schema, bundle, "default")["list_markers"])

    assert markers == assessed
    assert all(
        entry["expected_marker"] in entry["description"]
        for entry in built["lists"]
    )


def test_list_creation_applies_enable_minor_versions() -> None:
    """Regression: enable_minor_versions from the mapping versioning config
    was loaded but never applied. It must reach both the schema-json list
    entry and the rendered SP.List creation body."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    sj = build_schema_json(schema, bundle, "default")
    assert sj["lists"]
    assert all("enable_minor_versions" in lst for lst in sj["lists"])

    js = _generate_simple_js()
    assert "EnableMinorVersions" in js


def test_schema_declares_content_type_setting_for_shape_reconciliation() -> None:
    """The resume gate needs an explicit desired value, not a JS default."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    schema_json = build_schema_json(schema, bundle, "default")

    assert schema_json["lists"]
    assert all(lst["content_types_enabled"] is False for lst in schema_json["lists"])


def test_document_library_template_101_reaches_shape_gate() -> None:
    """Libraries must be distinguished from same-title generic lists."""
    schema = parse_dbml(FIXTURES / "simple.dbml")
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    bundle.mapping.entities["Project"] = EntityMapping(
        name="Project",
        kind="DocumentLibrary",
        base_template=101,
        site_role="default",
    )

    project = next(
        lst for lst in build_schema_json(schema, bundle, "default")["lists"]
        if lst["title"] == "APP_Project"
    )
    assert project["base_template"] == 101


def _library_schema_json(
    tmp_path: Path, kind: str, template: int, tail: str = "",
) -> dict[str, Any]:
    """One `Doc` entity of the given kind, with an optional mapping tail."""
    tmp_path.mkdir(exist_ok=True)
    schema, bundle = pack(
        tmp_path,
        dbml=table("Doc", ID_PK, TITLE, "Division nvarchar"),
        mapping=f"""
            entities:
              Doc:
                kind: {kind}
                base_template: {template}
                site_role: default
                {tail}
        """,
    )
    return build_schema_json(schema, bundle, "default")


def test_a_library_list_carries_its_folders_and_kind_flag(tmp_path: Path) -> None:
    """The folder phase and the seeding script key on these two fields."""
    schema_json = _library_schema_json(
        tmp_path, "DocumentLibrary", 101, 'folders: ["Clinical services", "Corporate"]',
    )
    doc = next(lst for lst in schema_json["lists"] if lst["title"] == "APP_Doc")
    assert doc["is_library"] is True
    assert doc["folders"] == ["Clinical services", "Corporate"]
    as_list = _library_schema_json(tmp_path / "list", "List", 100)
    plain = next(lst for lst in as_list["lists"] if lst["title"] == "APP_Doc")
    assert plain["is_library"] is False
    assert plain["folders"] == []


def test_a_library_all_items_leads_with_the_file_name_and_flattens_folders(
    tmp_path: Path,
) -> None:
    """A file's Title is null after upload (MEASURED 2026-07-29,
    `library.file-vs-item.title-after-upload`), so the recovery view names
    the file first and is recursive so every folder's files reach it."""
    schema_json = _library_schema_json(tmp_path, "DocumentLibrary", 101)
    all_items = next(
        v for v in schema_json["views"] if v["list"] == "APP_Doc" and v["title"] == "All Items"
    )
    assert all_items["view_fields"][:4] == ["DocIcon", "ID", "FileLeafRef", "Title"]
    assert "Division" in all_items["view_fields"]
    assert all_items["scope"] == 1
    as_list = _library_schema_json(tmp_path / "list", "List", 100)
    plain = next(
        v for v in as_list["views"] if v["list"] == "APP_Doc" and v["title"] == "All Items"
    )
    assert "FileLeafRef" not in plain["view_fields"]
    assert plain["scope"] is None


def test_a_declared_scope_emits_its_number_and_no_scope_emits_null(tmp_path: Path) -> None:
    """SP.View.Scope Recursive is 1 and DefaultValue is 0 (Learn, CSOM
    ViewScope). A declared `default` must reach the site as 0, so a view
    somebody flipped to Recursive by hand is put back; only a view with no
    scope emits null, which leaves the live property alone."""
    tail = """folders: []
            views:
              Doc:
                - title: "Flat"
                  default: true
                  fields: [FileLeafRef]
                  scope: recursive
                - title: "Folders"
                  fields: [FileLeafRef]
                  scope: default
                - title: "Here"
                  fields: [FileLeafRef]"""
    schema_json = _library_schema_json(tmp_path, "DocumentLibrary", 101, tail)
    by_title = {v["title"]: v for v in schema_json["views"] if v["list"] == "APP_Doc"}
    assert by_title["Flat"]["scope"] == 1
    assert by_title["Folders"]["scope"] == 0
    assert by_title["Here"]["scope"] is None


# --- the list Description: a human note, then the provenance marker ---------


def test_the_list_description_carries_the_note_then_the_marker() -> None:
    """The description is for a human first. The marker follows it so the
    settings page reads as prose, not as a machine tag."""
    desc = list_description("Scheduled checks and their ranges.",
                            family="routine-checks", entity="CheckPoint")
    assert desc.startswith("Scheduled checks and their ranges.")
    assert desc.endswith("Provisioned by dbml-sharepoint from routine-checks for list CheckPoint.")


def test_a_note_without_a_marker_is_never_emitted() -> None:
    """Discovery keys on the marker. A description without one deploys a list
    that is invisible to reporting, with no error anywhere."""
    desc = list_description("", family="routine-checks", entity="CheckPoint")
    assert "Provisioned by dbml-sharepoint" in desc


def test_the_marker_is_never_truncated_away() -> None:
    """The 255 budget truncates the NOTE, never the marker.

    Appending a marker after a 250-character note and cutting at 255 removes
    the marker: the list deploys, the deploy reads back the truncated
    description it sent, and the list is invisible to discovery forever.
    Nothing downstream can see that.
    """
    desc = list_description("x" * 400, family="routine-checks", entity="CheckPoint")
    assert len(desc) <= 255
    assert desc.endswith("Provisioned by dbml-sharepoint from routine-checks for list CheckPoint.")


def test_the_marker_survives_a_note_that_lands_exactly_on_the_budget() -> None:
    """The boundary, both sides of it.

    A note of exactly `note_budget` characters must survive whole AND keep the
    marker; one character more must lose a character of NOTE, never a
    character of marker. A naive `[:255]` after appending passes neither.

    The full description lands on 255 LESS `MARKER_GROWTH_RESERVE`, not on
    255: the budget holds that much back so the marker can grow later without
    invalidating notes already written. The unused tail is deliberate, and
    `test_validator_core` pins the reserve itself.
    """
    budget = note_budget("routine-checks", "CheckPoint")
    marker = "Provisioned by dbml-sharepoint from routine-checks for list CheckPoint."
    full = DESCRIPTION_LIMIT - MARKER_GROWTH_RESERVE

    exact = list_description("y" * budget, family="routine-checks", entity="CheckPoint")
    assert exact == f"{'y' * budget} {marker}"
    assert len(exact) == full

    over = list_description("y" * (budget + 1), family="routine-checks", entity="CheckPoint")
    assert over == f"{'y' * budget} {marker}"
    assert len(over) == full


def test_the_emitted_list_description_names_the_family_from_the_dbml_project(
    tmp_path: Path,
) -> None:
    """End to end through the emitter: the family is the DBML `Project` name,
    so a deployed list says which template family produced it.

    The composer is unit-tested above; this pins that `build_schema_json`
    actually calls it, because the emitter is where the silent truncation
    lived.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=blocks(
            "Project routine_checks { database_type: 'SharePoint Online' }",
            table("CheckPoint", ID_PK, TITLE, "Note: 'Scheduled checks.'"),
        ),
        mapping=entities("CheckPoint"),
        preamble=False,
    )
    schema_json = build_schema_json(schema, bundle, "default")

    assert schema_json["lists"][0]["description"] == (
        "Scheduled checks. Provisioned by dbml-sharepoint from routine-checks for list CheckPoint."
    )


def test_a_list_from_a_schema_with_no_project_still_carries_a_marker(
    tmp_path: Path,
) -> None:
    """A hand-written DBML need not declare a `Project`. The family is then
    unknown, but the list must still be discoverable -- an undiscoverable list
    is the whole failure this marker exists to prevent.

    `notes=False` so the description is the marker and nothing else, which is
    what makes the equality below say what it means. It also matches the
    emitter contract being pinned: `list_description` returns the marker alone
    for a note-less table, and the generator has to keep doing that whatever
    the validator says about it.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=table("Risk", ID_PK, TITLE),
        mapping=entities("Risk"),
        preamble=False,
        notes=False,
    )
    schema_json = build_schema_json(schema, bundle, "default")

    assert schema_json["lists"][0]["description"] == (
        f"Provisioned by dbml-sharepoint from {UNNAMED_FAMILY} for list Risk."
    )


def test_a_budget_of_zero_or_less_still_returns_the_marker_intact() -> None:
    """The backstop's own edge, where a negative slice would silently invert it.

    A family and entity long enough to fill the 255 on their own drive the
    budget to zero and below. `note[:-1]` is not "keep nothing" -- it is "keep
    all but the last character" -- so an unclamped budget makes the backstop
    return the note plus the marker, LONGER than the limit, in exactly the case
    it exists to handle.

    Unreachable through the CLI today: `ENTITY_NOTE_TOO_LONG_FOR_MARKER` fires
    first and errors gate generation. Pinned anyway, because a backstop that is
    wrong when reached is not a backstop.

    Both cases pin that the result is the marker ALONE rather than " " +
    marker, which is what a naive join would leave on the settings page.

    WHAT THE TWO FAMILIES ARE, measured rather than described from the
    arithmetic that predates `MARKER_GROWTH_RESERVE`. A marker is
    `len(family) + len(entity) + EMPTY` characters, where EMPTY is the marker
    with both fields blank, so at combined lengths of `254 - EMPTY` and
    `255 - EMPTY` it is 254 and 255 -- the second is the LONGEST marker that fits in
    the 255-character Description, and one more would be the first that does not.
    Both are far past the point where `note_budget` clamps: with the reserve
    taken off, it reaches zero at a combined length of 184 and would be -32
    and -33 here if it did not clamp.

    So the pair is not a boundary in today's arithmetic -- either family alone
    would exercise the clamp. It is kept because it is the boundary in the
    RESERVE-LESS arithmetic the backstop was written against, where 216 and 217
    gave a budget of exactly 0 and exactly -1, and -1 is the value that makes
    `note[:-1]` slice from the wrong end. Removing the reserve tomorrow puts
    these two back on either side of that edge.
    """
    entity = "e" * 10
    # Derived, not restated: the grammar has changed once and a hard-coded
    # length silently stopped describing the boundary it names.
    empty = provenance.empty_marker_length(kind=provenance.LIST_KIND, family="")

    # Marker 254 characters, one to spare. Reserve-less budget exactly 0.
    family_zero = "f" * (254 - empty - len(entity))
    zero = list_description("some note", family=family_zero, entity=entity)
    assert zero == marker_for(family_zero, entity)
    assert len(zero) == 254
    assert not zero.startswith(" ")

    # Marker exactly 255, the longest that fits. Reserve-less budget -1, which
    # is the case a negative slice inverts.
    family_negative = "f" * (255 - empty - len(entity))
    negative = list_description("some note", family=family_negative, entity=entity)
    assert negative == marker_for(family_negative, entity)
    assert len(negative) == 255
    assert "some note" not in negative

    assert note_budget(family_negative, entity) == 0, "the budget must never go negative"


def test_each_list_carries_its_previous_titles_and_their_markers() -> None:
    """`renamed_from` reaches the deploy as the previous TITLE (prefix
    applied) paired with the marker that title must carry, computed by the
    same helper the current marker is, so the two cannot disagree."""
    schema = make_schema(make_table("Risk", "Title", note="Risks."))
    bundle = make_bundle(entities={
        "Risk": EntityMapping(
            name="Risk", kind="List", base_template=100, site_role="default",
            renamed_from=("ProgramRisk", "ProjectRisk"),
        ),
    })
    built = build_schema_json(schema, bundle, "default")
    family = family_for(schema)
    assert built["lists"][0]["renamed_from"] == [
        {"title": "APP_ProgramRisk", "expected_marker": marker_for(family, "ProgramRisk")},
        {"title": "APP_ProjectRisk", "expected_marker": marker_for(family, "ProjectRisk")},
    ]


def test_previous_prefixes_multiply_the_previous_titles_of_every_list() -> None:
    """A prefix change is a rename: every previous prefix is tried with the
    current name and with every previous name, each paired with the marker
    its own entity name produces, and the current title is never a candidate."""
    schema = make_schema(make_table("Risk", "Title", note="Risks."))
    bundle = make_bundle(
        prefix="GOV_", previous_prefixes=("", "ADOPT_"),
        entities={
            "Risk": EntityMapping(
                name="Risk", kind="List", base_template=100, site_role="default",
                renamed_from=("ProgramRisk",),
            ),
        },
    )
    built = build_schema_json(schema, bundle, "default")
    family = family_for(schema)
    risk, program = marker_for(family, "Risk"), marker_for(family, "ProgramRisk")
    assert built["lists"][0]["renamed_from"] == [
        {"title": "GOV_ProgramRisk", "expected_marker": program},
        {"title": "Risk", "expected_marker": risk},
        {"title": "ProgramRisk", "expected_marker": program},
        {"title": "ADOPT_Risk", "expected_marker": risk},
        {"title": "ADOPT_ProgramRisk", "expected_marker": program},
    ]
