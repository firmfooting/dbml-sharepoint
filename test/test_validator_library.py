"""Validator: what a document library declares that a list cannot.

The file-identity vocabulary, declared folders and view scope. Each rule is
pinned in both directions where a direction exists: a library may, a list may
not, and the same declaration is asserted on both containers so a guard that
stops distinguishing them turns a test red.
"""

from pathlib import Path

import pytest
from _builders import ID_PK, TITLE, table
from _findings import by_severity, none_of, only
from _model import bundle as make_bundle
from _model import column as make_column
from _model import schema as make_schema
from _model import table as make_table
from _packs import pack

from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.model.mapping_types import (
    EntityKind,
    EntityMapping,
    FormFormatting,
    ViewDef,
)

#: A header whose title line names the file, the shape the family standard
#: asks of a library. Reviewed capture `library.doc-lib.header-fileleafref`,
#: 2026-09-03: it renders on the file panel.
_FILE_NAME_HEADER = {
    "elmType": "div",
    "children": [{"elmType": "span", "txtContent": "[$FileLeafRef]"}],
}


def _docs(kind: EntityKind = "DocumentLibrary", base_template: int = 101) -> EntityMapping:
    return EntityMapping(
        name="Docs", kind=kind, base_template=base_template, site_role="default",
    )


def _findings(entity: EntityMapping, **sections: object) -> list[Finding]:
    schema = make_schema(make_table("Docs", make_column("Title", required=True)))
    bundle = make_bundle(entities={"Docs": entity}, **sections)  # type: ignore[arg-type]
    return validate_against_mapping(schema, bundle)


def test_a_library_view_and_header_may_name_the_file() -> None:
    """MEASURED 2026-07-29, `library.doc-lib.view-fileleafref` in
    document-library-probe.js: a library view carries FileLeafRef through
    REST and reads it back among its fields. The header half is the reviewed
    capture above."""
    findings = _findings(
        _docs(),
        views={"Docs": [ViewDef(title="Files", fields=["FileLeafRef"], default=True)]},
        form_formatting={"Docs": FormFormatting(header=_FILE_NAME_HEADER)},
    )
    none_of(findings, FindingCode.COLUMN_NOT_RENDERED)
    none_of(findings, FindingCode.FORMATTER_FIELD_NOT_RENDERED)


def test_a_list_view_and_header_may_not_name_the_file() -> None:
    """The pair. A list item has no file, so the same declarations on a
    generic list name a column that is not rendered there."""
    findings = _findings(
        _docs(kind="List", base_template=100),
        views={"Docs": [ViewDef(title="Files", fields=["FileLeafRef"], default=True)]},
        form_formatting={"Docs": FormFormatting(header=_FILE_NAME_HEADER)},
    )
    only(findings, FindingCode.COLUMN_NOT_RENDERED)
    only(findings, FindingCode.FORMATTER_FIELD_NOT_RENDERED)


def test_a_library_field_set_may_name_the_file(tmp_path: Path) -> None:
    """Field sets expand at load, so this one goes through the loader."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Docs", ID_PK, TITLE),
        mapping="""
            entities:
              Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }
            field_sets:
              Docs:
                identity: [FileLeafRef, Title]
            views:
              Docs:
                - title: "Files"
                  default: true
                  fields: ["@identity"]
        """,
    )
    none_of(validate_against_mapping(schema, bundle), FindingCode.COLUMN_NOT_RENDERED)


def test_a_list_field_set_may_not_name_the_file(tmp_path: Path) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Docs", ID_PK, TITLE),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }
            field_sets:
              Docs:
                identity: [FileLeafRef, Title]
            views:
              Docs:
                - title: "Files"
                  default: true
                  fields: ["@identity"]
        """,
    )
    assert [
        f for f in validate_against_mapping(schema, bundle)
        if f.code is FindingCode.COLUMN_NOT_RENDERED
    ], "a list field set naming FileLeafRef must be refused"


def _folders(tmp_path: Path, kind: str, template: int, folders: str) -> list[Finding]:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Docs", ID_PK, TITLE),
        mapping=f"""
            entities:
              Docs:
                kind: {kind}
                base_template: {template}
                site_role: default
                folders: {folders}
        """,
    )
    return validate_against_mapping(schema, bundle)


def test_folders_are_refused_on_a_list(tmp_path: Path) -> None:
    """Only a library holds folders; on a list the key would validate clean
    and the folder phase would then address a container with no root
    folder to create under."""
    f = only(_folders(tmp_path, "List", 100, '["A"]'), FindingCode.FOLDERS_ON_A_LIST)
    assert "Docs" in f.message


def test_a_library_may_declare_folders(tmp_path: Path) -> None:
    """MEASURED 2026-09-03, `library.folder.creation-path` in
    folder-probe.js: Folders/add(url=) under the root creates a folder that
    reads back as an SP.Folder, so declared names with legal characters
    validate clean."""
    findings = _folders(
        tmp_path, "DocumentLibrary", 101, '["Clinical services", "Corporate services"]',
    )
    none_of(findings, FindingCode.FOLDERS_ON_A_LIST)
    none_of(findings, FindingCode.FOLDER_NAME_INVALID)
    none_of(findings, FindingCode.DUPLICATE_FOLDER)


def test_an_invalid_folder_name_is_refused(tmp_path: Path) -> None:
    f = only(
        _folders(tmp_path, "DocumentLibrary", 101, '["Clinical/Services"]'),
        FindingCode.FOLDER_NAME_INVALID,
    )
    assert "/" in f.message


def test_a_duplicate_folder_is_refused_case_insensitively(tmp_path: Path) -> None:
    """A folder is addressed by URL, which SharePoint resolves without
    regard to case, so two names differing only in case are one folder
    declared twice."""
    f = only(
        _folders(tmp_path, "DocumentLibrary", 101, '["Clinical", "clinical"]'),
        FindingCode.DUPLICATE_FOLDER,
    )
    assert "clinical" in f.message


def _scoped_view(
    tmp_path: Path, kind: str, template: int, scope_line: str, group_line: str = "",
) -> list[Finding]:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Docs", ID_PK, TITLE, "Division nvarchar"),
        mapping=f"""
            entities:
              Docs: {{ kind: {kind}, base_template: {template}, site_role: default }}
            views:
              Docs:
                - title: "Pending"
                  default: true
                  fields: [Title]
                  {scope_line}
                  {group_line}
        """,
    )
    return validate_against_mapping(schema, bundle)


def test_scope_is_refused_on_a_list(tmp_path: Path) -> None:
    findings = _scoped_view(tmp_path, "List", 100, "scope: recursive")
    f = only(findings, FindingCode.VIEW_SCOPE_ON_A_LIST)
    assert "Pending" in f.message


def test_a_library_view_may_be_recursive(tmp_path: Path) -> None:
    """MEASURED 2026-09-08, `library.folder.view-flattens-depth`: Recursive
    flattens the files at every depth, and 2026-09-13,
    `library.view.scope-on-create-reads-back`: the property sticks."""
    findings = _scoped_view(tmp_path, "DocumentLibrary", 101, "scope: recursive")
    none_of(findings, FindingCode.VIEW_SCOPE_ON_A_LIST)
    none_of(findings, FindingCode.LIBRARY_GROUP_BY_FOLDER_SCOPED)


def test_a_recursive_grouped_library_view_warns_about_folder_scoping(tmp_path: Path) -> None:
    """The large-list measurements in analysis/limits.py: past the threshold
    a root-scoped group-by is refused and only a folder-scoped one is
    served, so a recursive grouped view stops rendering at that size."""
    findings = _scoped_view(
        tmp_path, "DocumentLibrary", 101, "scope: recursive", "group_by: { field: Division }",
    )
    f = only(by_severity(findings, "warning"), FindingCode.LIBRARY_GROUP_BY_FOLDER_SCOPED)
    assert "Division" in f.message
    none_of(by_severity(findings, "error"), FindingCode.LIBRARY_GROUP_BY_FOLDER_SCOPED)


def test_a_default_scoped_grouped_library_view_does_not_warn(tmp_path: Path) -> None:
    findings = _scoped_view(
        tmp_path, "DocumentLibrary", 101, "scope: default", "group_by: { field: Division }",
    )
    none_of(findings, FindingCode.LIBRARY_GROUP_BY_FOLDER_SCOPED)


def test_an_unknown_scope_is_refused_at_load(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="scope"):
        _scoped_view(tmp_path, "DocumentLibrary", 101, "scope: sideways")


def _demo(tmp_path: Path, kind: str, template: int, row: str) -> list[Finding]:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Docs", ID_PK, TITLE, "Division nvarchar"),
        mapping=f"""
            entities:
              Docs:
                kind: {kind}
                base_template: {template}
                site_role: default
                folders: ["Clinical services"]
            demo_items:
              Docs:
                - key: d1
                  {row}
        """,
    )
    return validate_against_mapping(schema, bundle)


def test_a_library_demo_file_in_a_declared_folder_validates_clean(tmp_path: Path) -> None:
    """MEASURED 2026-09-03, `library.file.upload-path-files-add`: a file
    uploads through Files/add into a folder and its item carries the values
    set on it. The marker rides on the file name, so Title is not required."""
    findings = _demo(
        tmp_path, "DocumentLibrary", 101,
        'values: { Division: "Clinical services" }\n'
        '                  file: { name: "[DEMO] Privacy.txt", folder: "Clinical services" }',
    )
    for code in (
        FindingCode.DEMO_FILE_REQUIRED_ON_LIBRARY, FindingCode.DEMO_FILE_ON_A_LIST,
        FindingCode.DEMO_FILE_FOLDER_UNDECLARED, FindingCode.DEMO_FILE_NAME_INVALID,
        FindingCode.DEMO_FILE_NAME_MISSING_MARKER, FindingCode.DEMO_TITLE_MISSING_MARKER,
    ):
        none_of(findings, code)


def test_a_demo_file_on_a_list_is_refused(tmp_path: Path) -> None:
    findings = _demo(
        tmp_path, "List", 100,
        'values: { Title: "[DEMO] Row" }\n'
        '                  file: { name: "[DEMO] Privacy.txt" }',
    )
    only(findings, FindingCode.DEMO_FILE_ON_A_LIST)


def test_a_demo_file_in_an_undeclared_folder_is_refused(tmp_path: Path) -> None:
    findings = _demo(
        tmp_path, "DocumentLibrary", 101,
        'values: { Division: "Clinical services" }\n'
        '                  file: { name: "[DEMO] Privacy.txt", folder: "Archive" }',
    )
    f = only(findings, FindingCode.DEMO_FILE_FOLDER_UNDECLARED)
    assert "Archive" in f.message and "Clinical services" in f.message


def test_a_demo_file_name_needs_the_marker_and_legal_characters(tmp_path: Path) -> None:
    findings = _demo(
        tmp_path, "DocumentLibrary", 101,
        'values: { Division: "Clinical services" }\n'
        '                  file: { name: "Privacy:2026.txt" }',
    )
    only(findings, FindingCode.DEMO_FILE_NAME_MISSING_MARKER)
    f = only(findings, FindingCode.DEMO_FILE_NAME_INVALID)
    assert ":" in f.message


def test_a_demo_file_needs_a_name_at_load(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="name"):
        _demo(
            tmp_path, "DocumentLibrary", 101,
            'values: { Division: "Clinical services" }\n'
            '                  file: { folder: "Clinical services" }',
        )


def test_a_per_column_declaration_on_the_file_name_is_undeployable() -> None:
    """FileLeafRef is a system column the per-field deploy loop never
    writes, so a formatter declared on it would validate clean and deploy
    nothing. Same rule as Created or Author."""
    findings = _findings(
        _docs(),
        column_formatting={"Docs": {"FileLeafRef": {"elmType": "div"}}},
    )
    only(findings, FindingCode.UNDEPLOYABLE_COLUMN_DECLARATION)
