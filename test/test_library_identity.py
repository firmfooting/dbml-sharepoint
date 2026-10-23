import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _model import RollbackArgs
from _packs import pack
from _paths import FIXTURES

from dbml_sharepoint.analysis.reporting.plan import build_plans
from dbml_sharepoint.analysis.resolve import resolve
from dbml_sharepoint.catalogue import load_solution
from dbml_sharepoint.generators.assessgen import assess_targets
from dbml_sharepoint.generators.demogen import generate_demo_js
from dbml_sharepoint.generators.jsgen import build_schema_json
from dbml_sharepoint.generators.manifestgen import generate_manifest
from dbml_sharepoint.generators.rollbackgen import generate_rollback_js
from dbml_sharepoint.model.errors import MappingValueError
from dbml_sharepoint.model.release import load_release
from dbml_sharepoint.wizard import TemplateChoice, _read_facts

_NAMED_LIBRARY_DBML = """
Enum review_body {
  "Audit Committee"
  "Executive Committee"
}

Table Document {
  Id int [pk, increment]
  Title nvarchar
  ReviewBody review_body [note: 'The body that reviews this file']
  Status nvarchar [note: 'Where the file is in its cycle']
}
"""

_NAMED_LIBRARY_MAPPING = """
entities:
  Document:
    title: Policy Documents
    internal_name: PolicyDocuments
    kind: DocumentLibrary
    base_template: 101
    site_role: default
display_names:
  mode: auto
views:
  Document:
    - title: Folder View
      scope: default
      fields: [FileLeafRef, Title]
    - title: Pending
      scope: recursive
      default: true
      fields: [FileLeafRef, Status]
      where:
        - {field: Status, op: eq, value: "Pending"}
      sort:
        - {field: Modified, direction: desc}
demo_items:
  Document:
    - key: file-01
      file:
        name: "[DEMO] Leave policy.txt"
        content: Demo placeholder for a policy document.
      values:
        Status: Pending
"""


def test_a_named_library_is_deployed_and_navigated_under_its_own_title(tmp_path: Path) -> None:
    """A library's declared title and immutable URL name reach every generator.

    Written against a synthetic library when the one shipped pack with a named
    library left core: the entity name must reach none of the emitted scripts.
    """
    (tmp_path / "20-configure").mkdir()
    schema, bundle = pack(
        tmp_path / "20-configure", dbml=_NAMED_LIBRARY_DBML, mapping=_NAMED_LIBRARY_MAPPING,
        dbml_name="schema.dbml", mapping_name="mapping.yaml",
    )
    # The wizard's facts reader loads the schema and release from a blueprint's own layout.
    (tmp_path / "10-design").mkdir()
    (tmp_path / "20-configure" / "schema.dbml").rename(tmp_path / "10-design" / "schema.dbml")
    shutil.copy(FIXTURES / "release.yaml", tmp_path / "20-configure" / "release.yaml")
    release = load_release(FIXTURES / "release.yaml")
    built = build_schema_json(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))
    title = "Policy Documents"
    assert built["lists"][0]["title"] == title
    assert built["lists"][0]["internal_name"] == "PolicyDocuments"
    reviewer = next(
        f for f in built["lists"][0]["fields_phase1"] if f["title"] == "ReviewBody"
    )
    assert reviewer["display_title"] == "Review Body"
    assert not reviewer["body"].get("Required", False)
    assert reviewer["body"]["FieldTypeKind"] == 6
    assert reviewer["body"]["Choices"]["results"] == ["Audit Committee", "Executive Committee"]
    targets = assess_targets(schema, bundle, "default", resolved=resolve(schema, bundle.mapping))
    assert list(dict(targets["list_markers"])) == [title]
    assert all(v["list"] == title and v["view_fields"][0] == "DocIcon" for v in built["views"])
    folder = next(v for v in built["views"] if v["title"] == "Folder View")
    assert folder["scope"] == 0
    assert "<Where>" not in folder["caml_query"]
    assert next(v for v in built["views"] if v["title"] == "Pending")["set_default"]
    plan, = build_plans(schema, bundle, "default")
    assert plan.list_title == title
    assert plan.item_url_path == "/PolicyDocuments/Forms/DispForm.aspx?ID="
    args = RollbackArgs(
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="schema.dbml", generated_at="2026-09-15T00:00:00Z",
    )
    for generator in (generate_demo_js, generate_rollback_js):
        emitted = generator(schema=schema, bundle=bundle, release=release, **args)
        assert title in emitted
    manifest = generate_manifest(
        resolved=resolve(schema, bundle.mapping),
        schema_json=built, findings=[], bundle=bundle,
        source_mtime="2026-09-15T00:00:00Z", release=release, **args,
    )
    assert "Immutable library URL name: `PolicyDocuments`" in manifest
    assert "filter:" in manifest
    assert "sort: Modified desc" in manifest
    solution = replace(load_solution("visitor-log"), id="named-library", root=tmp_path)
    facts = _read_facts(solution)
    assert TemplateChoice(
        solution, "TEST_", facts.entity_roles, facts.entity_titles,
    ).list_titles("default") == (title,)


@pytest.mark.parametrize("spec", [
    "internal_name: ../escape", "internal_name: 'bad?name'", "internal_name: 123",
    "title: '../escape'", "title: '   '",
])
def test_library_identity_rejects_invalid_names(tmp_path: Path, spec: str) -> None:
    with pytest.raises(ValueError, match=r"^entities\.Doc\.(internal_name|title)"):
        pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=f"""
            entities:
              Doc:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                {spec}
        """)


def test_two_entities_cannot_claim_the_same_title(tmp_path: Path) -> None:
    with pytest.raises(MappingValueError, match="duplicate deployed title"):
        pack(tmp_path, dbml=table("A", ID_PK, TITLE) + table("B", ID_PK, TITLE), mapping="""
            entities:
              A: {kind: List, base_template: 100, site_role: default, title: Same}
              B: {kind: List, base_template: 100, site_role: default, title: same}
        """)


@pytest.mark.parametrize("length", [255, 256])
def test_explicit_title_length_boundary(tmp_path: Path, length: int) -> None:
    mapping = f"""
        entities:
          Doc:
            kind: DocumentLibrary
            base_template: 101
            site_role: default
            title: {'A' * length}
    """
    if length == 256:
        with pytest.raises(MappingValueError, match="at most 255"):
            pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=mapping)
    else:
        pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=mapping)


def test_rename_cannot_declare_an_immutable_root(tmp_path: Path) -> None:
    with pytest.raises(MappingValueError, match="internal_name cannot be combined"):
        pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping="""
            entities:
              Doc:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                internal_name: NewRoot
                renamed_from: [OldDoc]
        """)



def test_immutable_root_cannot_use_previous_prefix_adoption(tmp_path: Path) -> None:
    with pytest.raises(MappingValueError, match="previous_prefixes"):
        pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping="""
            previous_prefixes: [OLD_]
            entities:
              Doc:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                internal_name: NewRoot
        """)


@pytest.mark.parametrize("root", [
    "Shared Documents", "Legal-Compliance", "Compliance_2026", "A" * 129,
])
def test_library_root_accepts_supported_folder_names(tmp_path: Path, root: str) -> None:
    _, bundle = pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=f"""
        entities:
          Doc:
            kind: DocumentLibrary
            base_template: 101
            site_role: default
            internal_name: {root}
    """)
    assert bundle.mapping.entities["Doc"].internal_name == root


@pytest.mark.parametrize("fields", ["DocIcon, FileLeafRef", "FileLeafRef, DocIcon", "FileLeafRef"])
def test_library_view_emits_one_native_icon(tmp_path: Path, fields: str) -> None:
    schema, bundle = pack(tmp_path, dbml=table("Doc", ID_PK, TITLE), mapping=f"""
        entities:
          Doc: {{kind: DocumentLibrary, base_template: 101, site_role: default}}
        views:
          Doc:
            - title: Files
              fields: [{fields}]
    """)
    views = build_schema_json(
        schema, bundle, "default", resolved=resolve(schema, bundle.mapping),
    )["views"]
    view = next(v for v in views if v["title"] == "Files")
    assert view["view_fields"].count("DocIcon") == 1
    assert view["view_fields"].count("FileLeafRef") == 1


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("role", ["default", "another"])
def test_explicit_root_cannot_collide_with_an_implicit_library(
    tmp_path: Path, reverse: bool, role: str,
) -> None:
    declarations = [
        "First: {kind: DocumentLibrary, base_template: 101, site_role: default, title: Docs}",
        (f"Second: {{kind: DocumentLibrary, base_template: 101, site_role: {role}, "
         "title: Other, internal_name: docs}"),
    ]
    if reverse:
        declarations.reverse()
    mapping = "entities:\n" + "\n".join("  " + value for value in declarations)
    schema = table("First", ID_PK, TITLE) + table("Second", ID_PK, TITLE)
    if role == "default":
        with pytest.raises(MappingValueError, match="duplicate list or library root"):
            pack(tmp_path, dbml=schema, mapping=mapping)
    else:
        pack(tmp_path, dbml=schema, mapping=mapping)


@pytest.mark.parametrize(("kind", "template", "first", "second", "clashes"), [
    # Punctuation is dropped from a derived root and a space is kept.
    ("List", 100, "Risk-Log", "RiskLog", True),
    ("List", 100, "Risk Log", "RiskLog", False),
    ("List", 100, "Risk.Log", "Risk&Log", True),
    ("DocumentLibrary", 101, "Docs-A", "DocsA", True),
    ("DocumentLibrary", 101, "Docs A", "DocsA", False),
    # An accent is unmeasured, so no root is predicted for it.
    ("List", 100, "Caf\u00e9", "Caf", False),
])
def test_implicit_title_derived_roots_are_compared(
    tmp_path: Path, kind: str, template: int, first: str, second: str, clashes: bool,
) -> None:
    mapping = f"""
        entities:
          First: {{kind: {kind}, base_template: {template}, site_role: default, title: "{first}"}}
          Second: {{kind: {kind}, base_template: {template}, site_role: default, title: "{second}"}}
    """
    schema = table("First", ID_PK, TITLE) + table("Second", ID_PK, TITLE)
    if clashes:
        with pytest.raises(MappingValueError, match="duplicate list or library root"):
            pack(tmp_path, dbml=schema, mapping=mapping)
    else:
        pack(tmp_path, dbml=schema, mapping=mapping)


def test_an_explicit_list_root_cannot_collide_with_an_implicit_one(tmp_path: Path) -> None:
    mapping = """
        entities:
          First: {kind: List, base_template: 100, site_role: default, title: Risk-Log}
          Second:
            {kind: List, base_template: 100, site_role: default, title: Other,
             internal_name: Lists/RiskLog}
    """
    with pytest.raises(MappingValueError, match="duplicate list or library root"):
        pack(tmp_path, dbml=table("First", ID_PK, TITLE) + table("Second", ID_PK, TITLE),
             mapping=mapping)


def test_manifest_renders_rename_sources_that_carry_no_implicit_flag(tmp_path: Path) -> None:
    """The `implicit` key exists only on an implicit source; its absence must not fail the build."""
    schema, bundle = pack(
        tmp_path, dbml=table("Alpha", ID_PK, TITLE) + "\n" + table("Beta", ID_PK, TITLE),
        mapping="""
            entities:
              Alpha:
                kind: List
                site_role: default
                base_template: 100
                title: Alpha Things
                renamed_from: [Alpha, Old Alpha]
              Beta:
                kind: List
                site_role: default
                base_template: 100
                title: Beta Things
                renamed_from: [Old Beta]
        """,
    )
    release = load_release(FIXTURES / "release.yaml")
    resolved = resolve(schema, bundle.mapping)
    built = build_schema_json(schema, bundle, "default", resolved=resolved)
    sources = {
        lst["title"]: [r.get("implicit", False) for r in lst["renamed_from"]]
        for lst in built["lists"]
    }
    assert not any(sources["Alpha Things"]) and any(sources["Beta Things"])
    manifest = generate_manifest(
        resolved=resolved, schema_json=built, findings=[], bundle=bundle,
        source_mtime="2026-09-15T00:00:00Z", release=release,
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default", source_dbml="schema.dbml", generated_at="2026-09-15T00:00:00Z",
    )
    rows = [x for x in manifest.splitlines() if "Renamed in place from" in x]
    assert len(rows) == 2
    noted = ["an implicit source" in x for x in rows]
    assert noted == [False, True]
