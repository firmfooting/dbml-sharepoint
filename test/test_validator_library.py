"""Validator: what a document library declares that a list cannot.

The file-identity vocabulary, declared folders and view scope. Each rule is
pinned in both directions where a direction exists: a library may, a list may
not, and the same declaration is asserted on both containers so a guard that
stops distinguishing them turns a test red.
"""

from pathlib import Path
from typing import Unpack

import pytest
from _builders import ID_PK, TITLE, table
from _findings import by_severity, none_of, only
from _model import MappingSections
from _model import bundle as make_bundle
from _model import column as make_column
from _model import schema as make_schema
from _model import table as make_table
from _packs import pack

from dbml_sharepoint.analysis.checks._structure import TEMPLATE_BY_KIND
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping, validate_all
from dbml_sharepoint.extension import NullExtension
from dbml_sharepoint.model.errors import MappingShapeError, MappingValueError
from dbml_sharepoint.model.mapping_types import (
    ENTITY_KINDS,
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


def _library_findings(entity: EntityMapping, **sections: Unpack[MappingSections]) -> list[Finding]:
    schema = make_schema(make_table("Docs", make_column("Title", required=True)))
    bundle = make_bundle(entities={"Docs": entity}, **sections)
    return validate_against_mapping(schema, bundle)


def test_a_library_view_and_header_may_name_the_file() -> None:
    """MEASURED 2026-07-29, `library.doc-lib.view-fileleafref` in
    document-library-probe.js: a library view carries FileLeafRef through
    REST and reads it back among its fields. The header half is the reviewed
    capture above."""
    findings = _library_findings(
        _docs(),
        views={"Docs": [ViewDef(title="Files", fields=["FileLeafRef"], default=True)]},
        form_formatting={"Docs": FormFormatting(header=_FILE_NAME_HEADER)},
    )
    none_of(findings, FindingCode.COLUMN_NOT_RENDERED)
    none_of(findings, FindingCode.FORMATTER_FIELD_NOT_RENDERED)


def test_a_list_view_and_header_may_not_name_the_file() -> None:
    """The pair. A list item has no file, so the same declarations on a
    generic list name a column that is not rendered there."""
    findings = _library_findings(
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
        tmp_path, "DocumentLibrary", 101, '["Field operations", "Corporate"]',
    )
    none_of(findings, FindingCode.FOLDERS_ON_A_LIST)
    none_of(findings, FindingCode.FOLDER_NAME_INVALID)
    none_of(findings, FindingCode.DUPLICATE_FOLDER)


def test_an_invalid_folder_name_is_refused(tmp_path: Path) -> None:
    f = only(
        _folders(tmp_path, "DocumentLibrary", 101, '["Field operations/Services"]'),
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


def _folders_from_enum(
    tmp_path: Path, kind: str, template: int, members: str, named: str = "division",
) -> list[Finding]:
    """The same library, declaring its folders as one enum's members."""
    schema, bundle = pack(
        tmp_path,
        dbml=(
            f"Enum division {{\n{members}\n}}\n"
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping=f"""
            entities:
              Docs:
                kind: {kind}
                base_template: {template}
                site_role: default
                folders: {{from_enum: {named}}}
        """,
    )
    return validate_against_mapping(schema, bundle)


def test_folders_from_enum_are_the_enums_members(tmp_path: Path) -> None:
    """A shipped document library declared its divisions twice, once as an
    enum and once as a folder list, and an edit to the enum left the deploy
    creating the retired folders. Naming the enum removes the second copy."""
    findings = _folders_from_enum(
        tmp_path, "DocumentLibrary", 101,
        '  "Field operations"\n  "Corporate & community"',
    )
    none_of(findings, FindingCode.FOLDER_ENUM_UNKNOWN)
    none_of(findings, FindingCode.FOLDER_NAME_INVALID)
    none_of(findings, FindingCode.DUPLICATE_FOLDER)


def test_folders_from_an_unknown_enum_are_refused(tmp_path: Path) -> None:
    """The folders ARE the members, so an enum that does not exist leaves
    the library with none. Silently creating nothing is the failure this
    spelling exists to prevent, so it is an error and names what is
    declared."""
    f = only(
        _folders_from_enum(
            tmp_path, "DocumentLibrary", 101, '  "Field operations"',
            named="divison",
        ),
        FindingCode.FOLDER_ENUM_UNKNOWN,
    )
    assert "divison" in f.message
    assert "division" in f.message, "the message must name the enums that DO exist"


def test_folders_from_an_enum_no_column_uses_are_flagged(tmp_path: Path) -> None:
    """A schema holds many enums and `from_enum` takes any of them.

    Naming the wrong one resolves, passes every rule and creates a full set
    of the wrong folders, which nothing downstream can see because both
    declarations are individually valid. A warning and not an error: folders
    keyed by something the library does not store are a legitimate design.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n}\n'
            'Enum region {\n  "North"\n  "South"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: {from_enum: region}
        """,
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.FOLDER_ENUM_NOT_A_COLUMN_TYPE,
    )
    assert "region" in f.message
    assert "division" in f.message, "the message must name what the columns DO carry"


def test_a_multichoice_column_of_the_enum_counts_as_using_it(
    tmp_path: Path,
) -> None:
    """`Division division[]` is a MultiChoice of the same enum.

    Compared raw, `division[]` never equals `division`, so a library that
    files by a multi-value column got told its folders came from an enum it
    does not use, which is the opposite of true.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division[]")
        ),
        mapping="""
            entities:
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: {from_enum: division}
        """,
    )
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.FOLDER_ENUM_NOT_A_COLUMN_TYPE,
    )


def test_a_list_declaring_folders_from_an_unknown_enum_is_told_both(
    tmp_path: Path,
) -> None:
    """Two independent errors, reported together.

    Whether a list may hold folders at all does not depend on how many names
    resolved. Reporting only the spelling meant the author fixed it, rebuilt,
    and met a second error that had been true all along.
    """
    findings = _folders_from_enum(
        tmp_path, "List", 100, '  "Field operations"', named="divison",
    )
    only(findings, FindingCode.FOLDER_ENUM_UNKNOWN)
    only(findings, FindingCode.FOLDERS_ON_A_LIST)


def test_an_enum_used_only_for_folders_is_not_called_an_orphan(
    tmp_path: Path,
) -> None:
    """The mapping can be the only thing that uses an enum.

    `orphan_enum` is a schema-only rule and cannot see a mapping, but
    `folders: {from_enum: <name>}` turns an enum's members into a library's
    folders without any column naming it. The remedy the finding invites is
    deleting the enum, which would take the deploy's folders with it.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum shelf {\n  "Ground floor"\n}\n'
            + table("Docs", ID_PK, TITLE)
        ),
        mapping="""
            entities:
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: {from_enum: shelf}
        """,
    )
    none_of(validate_all(schema, bundle, NullExtension()), FindingCode.ORPHAN_ENUM)
    # Still reported when nothing uses it at all, or the rule is gone.
    unused = tmp_path / "unused"
    unused.mkdir()
    schema2, bundle2 = pack(
        unused,
        dbml=('Enum shelf {\n  "Ground floor"\n}\n' + table("Docs", ID_PK, TITLE)),
        mapping="""
            entities:
              Docs: { kind: DocumentLibrary, base_template: 101, site_role: default }
        """,
    )
    only(validate_all(schema2, bundle2, NullExtension()), FindingCode.ORPHAN_ENUM)


def test_an_enum_used_only_for_groups_is_not_called_an_orphan(
    tmp_path: Path,
) -> None:
    """`groups[].from_enum` uses an enum exactly as `folders` does.

    The remedy `orphan_enum` invites is deleting the enum, which here would
    take every group the site is given with it.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n}\n'
            + table("Docs", ID_PK, TITLE)
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member} Editors"
                description: "Editors."
                owner_group: "Site Owners"
        """,
    )
    none_of(validate_all(schema, bundle, NullExtension()), FindingCode.ORPHAN_ENUM)


def test_folders_from_the_entitys_own_enum_are_not_flagged(tmp_path: Path) -> None:
    """The ordinary shape stays quiet, or the warning is noise."""
    none_of(
        _folders_from_enum(
            tmp_path, "DocumentLibrary", 101, '  "Field operations"',
        ),
        FindingCode.FOLDER_ENUM_NOT_A_COLUMN_TYPE,
    )


def test_an_unresolved_folder_enum_does_not_condemn_every_demo_file(
    tmp_path: Path,
) -> None:
    """One actionable finding, not one per row.

    The folders are unresolved, which is not the same answer as "this library
    declares none". Treating the failure as an empty declaration made every
    demo row report a folder the library does not declare, so the finding an
    author can act on arrived buried under a cascade caused by it.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: {from_enum: divison}
            demo_items:
              Docs:
                - key: d1
                  values: { Division: "Field operations" }
                  file: { name: "[DEMO] Privacy.txt", folder: "Field operations" }
                - key: d2
                  values: { Division: "Field operations" }
                  file: { name: "[DEMO] Records.txt", folder: "Field operations" }
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    only(findings, FindingCode.FOLDER_ENUM_UNKNOWN)
    none_of(findings, FindingCode.DEMO_FILE_FOLDER_UNDECLARED)


def test_an_enum_member_that_cannot_be_a_folder_is_refused(tmp_path: Path) -> None:
    """The folder name rules apply to the resolved names. An enum is free
    to carry a `/` where a folder name is not, and the build has to say so
    rather than let the folder phase fail on a live site."""
    f = only(
        _folders_from_enum(
            tmp_path, "DocumentLibrary", 101, '  "Field operations/services"',
        ),
        FindingCode.FOLDER_NAME_INVALID,
    )
    assert "/" in f.message


def test_folders_from_enum_are_refused_on_a_list(tmp_path: Path) -> None:
    """Whichever way the folders are spelled, only a library holds them."""
    f = only(
        _folders_from_enum(tmp_path, "List", 100, '  "Field operations"'),
        FindingCode.FOLDERS_ON_A_LIST,
    )
    assert "Docs" in f.message


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
    with pytest.raises(MappingValueError, match=r"views\.Docs\[0\]: scope"):
        _scoped_view(tmp_path, "DocumentLibrary", 101, "scope: sideways")


def test_a_list_shaped_scope_is_refused_at_load(tmp_path: Path) -> None:
    """A list is unhashable, so without an isinstance guard the loader would
    raise TypeError, which the CLI does not catch, instead of its refusal.

    A shape error and not a value error: the vocabulary is about which word,
    and this is not a word.
    """
    with pytest.raises(MappingShapeError, match=r"views\.Docs\[0\]: scope"):
        _scoped_view(tmp_path, "DocumentLibrary", 101, "scope: [recursive]")


def test_a_library_display_title_may_not_be_a_file_report_column() -> None:
    """The reporting pack names a library's rows by file name and path,
    under no switch at all, and renaming a schema column onto a name the
    table already carries is an error in M: the build stays green, the
    model publishes and the refresh fails. The auto split alone reaches
    it, so the rule cannot be documentation.

    Asserted on both containers: a list carries no file columns, so the
    same schema must pass there.
    """
    schema = make_schema(make_table(
        "Docs", make_column("Title", required=True), make_column("FileName", "nvarchar"),
    ))
    as_library = make_bundle(entities={"Docs": _docs()}, display_name_mode="auto")
    finding = only(
        validate_against_mapping(schema, as_library),
        FindingCode.DISPLAY_TITLE_COLLIDES_WITH_REPORT_COLUMN,
    )
    assert "'File Name'" in finding.message
    as_list = make_bundle(
        entities={"Docs": _docs("List", 100)}, display_name_mode="auto",
    )
    none_of(
        validate_against_mapping(schema, as_list),
        FindingCode.DISPLAY_TITLE_COLLIDES_WITH_REPORT_COLUMN,
    )


def test_every_declared_kind_has_a_base_template() -> None:
    """A kind the Literal admits and `TEMPLATE_BY_KIND` omits is a KeyError
    inside validation, not a finding."""
    assert set(TEMPLATE_BY_KIND) == ENTITY_KINDS


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
                folders: ["Field operations"]
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
        'values: { Division: "Field operations" }\n'
        '                  file: { name: "[DEMO] Privacy.txt", folder: "Field operations" }',
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
        'values: { Division: "Field operations" }\n'
        '                  file: { name: "[DEMO] Privacy.txt", folder: "Archive" }',
    )
    f = only(findings, FindingCode.DEMO_FILE_FOLDER_UNDECLARED)
    assert "Archive" in f.message and "Field operations" in f.message


def test_a_demo_file_name_needs_the_marker_and_legal_characters(tmp_path: Path) -> None:
    findings = _demo(
        tmp_path, "DocumentLibrary", 101,
        'values: { Division: "Field operations" }\n'
        '                  file: { name: "Privacy:2026.txt" }',
    )
    only(findings, FindingCode.DEMO_FILE_NAME_MISSING_MARKER)
    f = only(findings, FindingCode.DEMO_FILE_NAME_INVALID)
    assert ":" in f.message


def test_a_demo_file_needs_a_name_at_load(tmp_path: Path) -> None:
    with pytest.raises(MappingShapeError, match=r"demo_items\.Docs\[0\]\.file"):
        _demo(
            tmp_path, "DocumentLibrary", 101,
            'values: { Division: "Field operations" }\n'
            '                  file: { folder: "Field operations" }',
        )


def test_a_per_column_declaration_on_the_file_name_is_undeployable() -> None:
    """FileLeafRef is a system column the per-field deploy loop never
    writes, so a formatter declared on it would validate clean and deploy
    nothing. Same rule as Created or Author."""
    findings = _library_findings(
        _docs(),
        column_formatting={"Docs": {"FileLeafRef": {"elmType": "div"}}},
    )
    only(findings, FindingCode.UNDEPLOYABLE_COLUMN_DECLARATION)


# --- list_permissions.folders and groups[].from_enum ------------------------

def _folder_policy(
    tmp_path: Path,
    *,
    kind: str = "DocumentLibrary",
    template: int = 101,
    folders: str = "{from_enum: division}",
    entity: str = "Docs",
    group_name: str = "{member} Editors",
    from_enum: str = "division",
    folder_level: str = "Folder Editor",
    folder_principal: str | None = None,
) -> list[Finding]:
    """A library whose folders carry their own ACL, and one group per member
    to hold it. The two halves are declared together because that is the only
    shape either is useful in."""
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n  "Corporate"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping=f"""
            entities:
              Docs:
                kind: {kind}
                base_template: {template}
                site_role: default
                folders: {folders}

            permission_levels:
              - name: "Folder Editor"
                description: "Edit inside one folder."
                base_permissions: [ViewListItems, AddListItems, EditListItems]

            groups:
              - from_enum: {from_enum}
                name: "{group_name}"
                description: "Editors for {{member}}."
                owner_group: "Site Owners"

            list_permissions:
              default:
                site_role: default
                break_inheritance: true
                reconcile: exact
                assignments:
                  - principal: {{ kind: associated_owner_group }}
                    level: "Folder Editor"
              folders:
                {entity}:
                  break_inheritance: true
                  reconcile: exact
                  assignments:
                    - principal: {{ kind: group, name: "{folder_principal or group_name}" }}
                      level: "{folder_level}"
        """,
    )
    return validate_against_mapping(schema, bundle)


def test_a_group_per_enum_member_securing_its_own_folder_is_clean(
    tmp_path: Path,
) -> None:
    """The whole point of the pair: the folders and the groups that hold their
    grants come from one enum, so neither list can drift from the other."""
    findings = _folder_policy(tmp_path)
    none_of(findings, FindingCode.GROUP_ENUM_UNKNOWN)
    none_of(findings, FindingCode.GROUP_ENUM_NAME_NOT_UNIQUE)
    none_of(findings, FindingCode.FOLDER_PERMISSIONS_ON_A_LIST)
    none_of(findings, FindingCode.FOLDER_PERMISSIONS_WITHOUT_FOLDERS)
    none_of(findings, FindingCode.UNKNOWN_PRINCIPAL_GROUP)
    none_of(findings, FindingCode.EXACT_POLICY_GRANTS_NOTHING)
    assert by_severity(findings, "error") == [], by_severity(findings, "error")


def test_a_folder_policy_level_that_does_not_exist_is_refused(
    tmp_path: Path,
) -> None:
    """A folder policy is a policy block and gets a policy block's checks.

    Folder policies were resolved and emitted but never handed to the
    assignment checks, so a misspelled level passed the build and failed at
    the ACL phase, after the list, column and view phases had already written
    to the site. The whole point of this tool is that a name that cannot
    resolve fails before anything is touched.
    """
    findings = [
        f for f in _folder_policy(tmp_path, folder_level="Folder Edtior")
        if f.code == FindingCode.UNKNOWN_PERMISSION_LEVEL
    ]
    assert findings, "a folder policy's level must be judged like any other"
    assert all("Folder Edtior" in f.message for f in findings)
    # One per folder, each naming its own: the principal resolves to a
    # different group per member, so no single folder speaks for the rest.
    assert {"Field operations", "Corporate"} == {
        folder for folder in ("Field operations", "Corporate")
        for f in findings if folder in f.message
    }


def test_a_folder_policy_principal_that_does_not_exist_is_refused(
    tmp_path: Path,
) -> None:
    """The same for the principal, judged AFTER expansion.

    The name is checked per folder, so a principal that resolves for one
    member and not another is caught rather than averaged away.
    """
    findings = _folder_policy(tmp_path, folder_principal="{member} Editers")
    codes = [f.code for f in findings]
    assert FindingCode.UNKNOWN_PRINCIPAL_GROUP in codes, codes


def test_a_member_that_sanitises_to_nothing_is_refused(tmp_path: Path) -> None:
    """`{member_safe}` can produce an empty name, which SharePoint refuses.

    The measured server error refuses an empty name in the same sentence as
    the character list. A member built only from refused characters leaves
    nothing behind, so the name passed the character test by having no
    characters at all.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "@"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member_safe}"
                description: "Editors."
                owner_group: "Site Owners"
        """,
    )
    f = only(validate_against_mapping(schema, bundle), FindingCode.GROUP_NAME_INVALID)
    assert "empty" in f.message


def test_one_unknown_enum_does_not_hide_the_groups_that_resolved(
    tmp_path: Path,
) -> None:
    """A misspelled source reports itself and nothing else stops being judged.

    The old fallback dropped every generated group as soon as one source was
    unknown, so the duplicate, name, owner, provenance and rename checks
    silently stopped covering groups that had resolved perfectly well.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations, north"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member} Editors"
                description: "Editors."
                owner_group: "Site Owners"
              - from_enum: divison
                name: "{member} Readers"
                description: "Readers."
                owner_group: "Site Owners"
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    only(findings, FindingCode.GROUP_ENUM_UNKNOWN)
    # The resolvable source still gets judged: its member carries a comma.
    f = only(findings, FindingCode.GROUP_NAME_INVALID)
    assert "','" in f.message


def test_groups_from_an_unknown_enum_are_refused(tmp_path: Path) -> None:
    """No enum, no groups, and every folder grant then names a principal that
    was never created. Named like the folder rule, and for the same reason."""
    f = only(
        _folder_policy(tmp_path, from_enum="divison"),
        FindingCode.GROUP_ENUM_UNKNOWN,
    )
    assert "divison" in f.message
    assert "division" in f.message, "the message must name the enums that DO exist"


def test_an_enum_group_name_without_the_member_token_is_refused(
    tmp_path: Path,
) -> None:
    """The silent one. Every member resolves to the same name, so ONE group is
    created, written, read back byte-identical and reported clean, while every
    folder grant meant for a particular division lands on it."""
    f = only(
        _folder_policy(tmp_path, group_name="Division Editors"),
        FindingCode.GROUP_ENUM_NAME_NOT_UNIQUE,
    )
    assert "{member}" in f.message
    assert "division" in f.message


def test_a_fixed_name_over_a_single_member_enum_is_allowed(tmp_path: Path) -> None:
    """One member generates one group, so a fixed name is what the author
    wrote rather than seven declarations collapsing onto one.

    An enforced rule must not be stronger than what it is judging.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "Division Editors"
                description: "Editors."
                owner_group: "Site Owners"
        """,
    )
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.GROUP_ENUM_NAME_NOT_UNIQUE,
    )


def test_a_folder_principal_resolving_to_a_protected_group_is_judged(
    tmp_path: Path,
) -> None:
    """A `{member}` principal is not necessarily a per-member group.

    `dbml Enterprise {member}` over a folder named Automation resolves to
    `dbml Enterprise Automation`, which the deploy grants and the targeted
    rules are about. Compared unexpanded, the template spelling matched no
    protected name and the grant went out unjudged.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum area {\n  "Automation"\n}\n'
            + table("Docs", ID_PK, TITLE, "Area area")
        ),
        mapping="""
            entities:
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: {from_enum: area}

            list_permissions:
              folders:
                Docs:
                  break_inheritance: true
                  reconcile: exact
                  assignments:
                    - principal: { kind: group, name: "dbml Enterprise {member}" }
                      level: "Full Control"
        """,
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.AUTOMATION_GROUP_GRANTED_FULL_CONTROL,
    )
    assert "dbml Enterprise Automation" in f.message


def test_folder_permissions_on_a_list_are_refused(tmp_path: Path) -> None:
    """A folder ACL is written against the folder's list item, and a list has
    no folders to write one on."""
    f = only(
        _folder_policy(tmp_path, kind="List", template=100, folders="[]"),
        FindingCode.FOLDER_PERMISSIONS_ON_A_LIST,
    )
    assert "Docs" in f.message


def test_folder_permissions_on_a_library_with_no_folders_are_refused(
    tmp_path: Path,
) -> None:
    """A policy governing nothing is the failure this rule exists to make
    loud: it builds, deploys, writes no folder ACL at all and reports
    success."""
    f = only(
        _folder_policy(tmp_path, folders="[]"),
        FindingCode.FOLDER_PERMISSIONS_WITHOUT_FOLDERS,
    )
    assert "Docs" in f.message


def test_folder_permissions_on_an_unknown_entity_are_refused(
    tmp_path: Path,
) -> None:
    """Keyed by entity exactly as `overrides` is, and refused the same way."""
    f = only(
        _folder_policy(tmp_path, entity="Nope"),
        FindingCode.UNKNOWN_TABLE,
    )
    assert "Nope" in f.message


#: List policies in YAML flow style, for `_folder_policy_body`'s `default` and `overrides`.
_EXACT_LIST = (
    "{break_inheritance: true, reconcile: exact, assignments: "
    '[{principal: {kind: associated_owner_group}, level: "Full Control"}]}'
)
_CONFIGURED_LIST = (
    "{break_inheritance: true, reconcile: configured, assignments: "
    '[{principal: {kind: associated_owner_group}, level: "Full Control"}]}'
)


def _folder_policy_body(
    tmp_path: Path,
    policy: str,
    *,
    folders: str = "{from_enum: division}",
    default: str | None = _EXACT_LIST,
    override: str | None = None,
) -> list[Finding]:
    """A two-folder library whose folder policy is `policy`, in YAML flow style.

    `default` and `override` are the library's list policy through each
    route; `None` leaves that route undeclared.
    """
    blocks = [f"folders: {{Docs: {policy}}}"]
    if default is not None:
        blocks.append(f"default: {default}")
    if override is not None:
        blocks.append(f"overrides: {{Docs: {override}}}")
    list_permissions = "{" + ", ".join(blocks) + "}"
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n  "Corporate"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping=f"""
            entities:
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: {folders}

            list_permissions: {list_permissions}
        """,
    )
    return validate_against_mapping(schema, bundle)


@pytest.mark.parametrize(
    "default",
    [
        pytest.param(_EXACT_LIST, id="exact-list"),
        # The folder prunes whatever its list does, unlike `folder_policy_manages_nothing`.
        pytest.param(_CONFIGURED_LIST, id="configured-list"),
        pytest.param(None, id="no-list-policy"),
    ],
)
def test_an_exact_folder_policy_granting_nothing_warns_once(
    tmp_path: Path, default: str | None,
) -> None:
    """One declared block over two folders is one warning, not one per folder."""
    f = only(
        _folder_policy_body(
            tmp_path, "{break_inheritance: true, reconcile: exact, assignments: []}",
            default=default,
        ),
        FindingCode.EXACT_POLICY_GRANTS_NOTHING,
    )
    assert f.location == Location(Section.LIST_PERMISSIONS, sub="folders")
    assert "Docs" in f.message


def test_an_exact_folder_policy_on_a_library_the_schema_lacks_does_not_warn(
    tmp_path: Path,
) -> None:
    """The deploy emits no scope for a library the DBML does not declare, so
    there is no removal to warn about; `entity_not_in_schema` says why."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Other", ID_PK, TITLE),
        mapping="""
            entities:
              Other:
                kind: List
                base_template: 100
                site_role: default
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: [Alpha, Beta]

            list_permissions:
              folders:
                Docs: {break_inheritance: true, reconcile: exact, assignments: []}
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    only(findings, FindingCode.ENTITY_NOT_IN_SCHEMA)
    none_of(findings, FindingCode.EXACT_POLICY_GRANTS_NOTHING)


def test_an_exact_folder_policy_on_a_list_is_left_to_the_folder_rules(
    tmp_path: Path,
) -> None:
    """A list has no folders to secure, so no folder scope is emitted to prune."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Tasks", ID_PK, TITLE),
        mapping="""
            entities:
              Tasks:
                kind: List
                base_template: 100
                site_role: default
                folders: [Alpha, Beta]

            list_permissions:
              folders:
                Tasks: {break_inheritance: true, reconcile: exact, assignments: []}
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    only(findings, FindingCode.FOLDER_PERMISSIONS_ON_A_LIST)
    none_of(findings, FindingCode.EXACT_POLICY_GRANTS_NOTHING)


def test_an_empty_folder_policy_on_a_library_the_schema_lacks_is_not_refused(
    tmp_path: Path,
) -> None:
    """No scope is emitted for a library the DBML does not declare, so no
    guard is switched off; `entity_not_in_schema` says why."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Other", ID_PK, TITLE),
        mapping=f"""
            entities:
              Other:
                kind: List
                base_template: 100
                site_role: default
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: [Alpha, Beta]

            list_permissions:
              default: {_EXACT_LIST}
              folders:
                Docs: {{break_inheritance: true}}
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    only(findings, FindingCode.ENTITY_NOT_IN_SCHEMA)
    none_of(findings, FindingCode.FOLDER_POLICY_MANAGES_NOTHING)


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param("{break_inheritance: false}", id="inherits"),
        # A break is POSTed only on a scope that still inherits, so on an
        # already-unique folder this spelling writes nothing either.
        pytest.param("{break_inheritance: true}", id="breaks"),
        pytest.param("{break_inheritance: true, reconcile: configured}", id="breaks-explicit"),
    ],
)
def test_a_configured_folder_policy_granting_nothing_is_refused(
    tmp_path: Path, policy: str,
) -> None:
    """Under an exact list (here through the default) it grants and removes
    nothing, and still took both folders out of the exact-mode check that
    refuses an undeclared folder scope (#617)."""
    f = only(
        _folder_policy_body(tmp_path, policy),
        FindingCode.FOLDER_POLICY_MANAGES_NOTHING,
    )
    assert f.severity == "error"
    assert f.location == Location(Section.LIST_PERMISSIONS, sub="folders")
    assert "Docs" in f.message


def test_an_exact_list_reached_through_an_override_is_judged_too(tmp_path: Path) -> None:
    only(
        _folder_policy_body(
            tmp_path, "{break_inheritance: true}",
            default=_CONFIGURED_LIST, override=_EXACT_LIST,
        ),
        FindingCode.FOLDER_POLICY_MANAGES_NOTHING,
    )


@pytest.mark.parametrize(
    ("default", "override"),
    [
        pytest.param(_CONFIGURED_LIST, None, id="configured-default"),
        # The override is what the library deploys under, not the exact default.
        pytest.param(_EXACT_LIST, _CONFIGURED_LIST, id="configured-override"),
        pytest.param(None, None, id="no-list-policy"),
    ],
)
@pytest.mark.parametrize(
    "policy",
    [
        pytest.param("{break_inheritance: true}", id="breaks"),
        pytest.param("{break_inheritance: false}", id="inherits"),
    ],
)
def test_a_configured_folder_policy_granting_nothing_is_allowed_off_an_exact_list(
    tmp_path: Path, policy: str, default: str | None, override: str | None,
) -> None:
    """The descendant check runs only under an exact list, so here there is
    nothing to exempt, and breaking a folder to manage it by hand is legal."""
    none_of(
        _folder_policy_body(tmp_path, policy, default=default, override=override),
        FindingCode.FOLDER_POLICY_MANAGES_NOTHING,
    )


@pytest.mark.parametrize(
    "policy",
    [
        pytest.param(
            "{break_inheritance: false, assignments: "
            "[{principal: {kind: associated_member_group}, level: Read}]}",
            id="configured-grants",
        ),
        pytest.param(
            "{break_inheritance: true, assignments: "
            "[{principal: {kind: associated_member_group}, level: Read}]}",
            id="configured-breaks-and-grants",
        ),
        # Exact reviews every grant on the folder; granting none is the warning's case.
        pytest.param(
            "{break_inheritance: true, reconcile: exact, assignments: []}",
            id="exact-grants-nothing",
        ),
    ],
)
def test_a_folder_policy_that_grants_or_reviews_is_not_refused(
    tmp_path: Path, policy: str,
) -> None:
    none_of(
        _folder_policy_body(tmp_path, policy),
        FindingCode.FOLDER_POLICY_MANAGES_NOTHING,
    )


@pytest.mark.parametrize(
    ("default", "override"),
    [
        pytest.param(_CONFIGURED_LIST, None, id="configured-default"),
        pytest.param(_EXACT_LIST, _CONFIGURED_LIST, id="configured-override"),
        pytest.param(None, None, id="no-list-policy"),
    ],
)
def test_a_configured_folder_policy_breaking_with_no_assignments_warns_once(
    tmp_path: Path, default: str | None, override: str | None,
) -> None:
    """Allowed off an exact list to hand the folders to manual management,
    and the break still copies none of a folder's inherited role assignments
    (#684). What a folder keeps after it is not measured."""
    f = only(
        _folder_policy_body(
            tmp_path, "{break_inheritance: true}", default=default, override=override,
        ),
        FindingCode.CONFIGURED_BREAK_GRANTS_NOTHING,
    )
    assert f.severity == "warning"
    assert f.location == Location(Section.LIST_PERMISSIONS, sub="folders")
    assert "Docs" in f.message


def test_a_configured_folder_policy_refused_under_an_exact_list_is_not_also_warned(
    tmp_path: Path,
) -> None:
    findings = _folder_policy_body(tmp_path, "{break_inheritance: true}")
    only(findings, FindingCode.FOLDER_POLICY_MANAGES_NOTHING)
    none_of(findings, FindingCode.CONFIGURED_BREAK_GRANTS_NOTHING)


def test_a_configured_folder_policy_on_a_library_the_schema_lacks_does_not_warn(
    tmp_path: Path,
) -> None:
    schema, bundle = pack(
        tmp_path,
        dbml=table("Other", ID_PK, TITLE),
        mapping="""
            entities:
              Other:
                kind: List
                base_template: 100
                site_role: default
              Docs:
                kind: DocumentLibrary
                base_template: 101
                site_role: default
                folders: [Alpha, Beta]

            list_permissions:
              folders:
                Docs: {break_inheritance: true}
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    only(findings, FindingCode.ENTITY_NOT_IN_SCHEMA)
    none_of(findings, FindingCode.CONFIGURED_BREAK_GRANTS_NOTHING)


def test_a_library_with_no_folders_is_told_that_rather_than_both(
    tmp_path: Path,
) -> None:
    """With no folders there is nothing for the policy to exempt, and the
    remedy is the container's, so the policy is not judged as well."""
    findings = _folder_policy_body(
        tmp_path, "{break_inheritance: false}", folders="[]",
    )
    only(findings, FindingCode.FOLDER_PERMISSIONS_WITHOUT_FOLDERS)
    none_of(findings, FindingCode.FOLDER_POLICY_MANAGES_NOTHING)


_EXTERNAL_LIST = (
    "{break_inheritance: true, reconcile: exact, file_scopes: external, assignments: "
    '[{principal: {kind: associated_owner_group}, level: "Full Control"}]}'
)


def _file_scopes(tmp_path: Path, kind: str, template: int, route: str) -> list[Finding]:
    """One entity of `kind` whose list policy is `_EXTERNAL_LIST` through `route`."""
    schema, bundle = pack(
        tmp_path,
        dbml=table("Docs", ID_PK, TITLE),
        mapping=f"""
            entities:
              Docs:
                kind: {kind}
                base_template: {template}
                site_role: default

            list_permissions:
              {route}
        """,
    )
    return validate_against_mapping(schema, bundle)


#: The two keys a list policy is reached through; the key is the finding's location.
_ROUTES = [
    pytest.param(f"default: {_EXTERNAL_LIST}", id="default"),
    pytest.param(f"overrides: {{Docs: {_EXTERNAL_LIST}}}", id="override"),
]


@pytest.mark.parametrize("route", _ROUTES)
def test_external_file_scopes_on_a_list_are_refused(tmp_path: Path, route: str) -> None:
    """The deploy keeps `refuse` on a list, so `external` there would do nothing."""
    f = only(
        _file_scopes(tmp_path, "List", 100, route),
        FindingCode.FILE_SCOPES_EXTERNAL_NEEDS_LIBRARY,
    )
    assert f.severity == "error"
    assert f.location == Location(Section.LIST_PERMISSIONS, sub=route.partition(":")[0])
    assert "Docs" in f.message


@pytest.mark.parametrize("route", _ROUTES)
def test_external_file_scopes_on_a_library_are_accepted(tmp_path: Path, route: str) -> None:
    none_of(
        _file_scopes(tmp_path, "DocumentLibrary", 101, route),
        FindingCode.FILE_SCOPES_EXTERNAL_NEEDS_LIBRARY,
    )


@pytest.mark.parametrize(
    "flag", ["enroll_enterprise_reader", "enroll_operator_during_deploy"],
)
def test_an_enum_group_cannot_enrol_an_identity(tmp_path: Path, flag: str) -> None:
    """Each flag enrols ONE identity, and `from_enum` makes one group per
    member to enrol it into.

    Refused rather than given a meaning it does not have: the account lands
    in whichever group the phase reaches first and every other one is left
    empty.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Field operations"\n  "Corporate"\n}\n'
            + table("Docs", ID_PK, TITLE)
        ),
        mapping=f"""
            entities:
              Docs: {{ kind: List, base_template: 100, site_role: default }}

            groups:
              - from_enum: division
                name: "{{member}} Editors"
                description: "Editors."
                owner_group: "Site Owners"
                {flag}: true
        """,
    )
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.GROUP_ENUM_ENROLS_AN_IDENTITY,
    )
    assert flag in f.message
    assert "division" in f.message


@pytest.mark.parametrize(
    "flag", ["enroll_enterprise_reader", "enroll_operator_during_deploy"],
)
def test_a_single_member_enum_may_enrol_an_identity(tmp_path: Path, flag: str) -> None:
    """One member generates one group, so the sentence the refusal gives --
    the identity lands in the first and the rest stay empty -- is not true of
    it, and a finding whose reason does not hold is the wrong finding.

    The name every reader resolves is the generated one: `manifestgen` takes
    it from `schema_json`, whose groups are already expanded, and `pipeline`
    and `wizard` only ask whether any declaration carries the flag at all.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=('Enum division {\n  "Field operations"\n}\n' + table("Docs", ID_PK, TITLE)),
        mapping=f"""
            entities:
              Docs: {{ kind: List, base_template: 100, site_role: default }}

            groups:
              - from_enum: division
                name: "{{member}} Editors"
                description: "Editors."
                owner_group: "Site Owners"
                {flag}: true
        """,
    )
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.GROUP_ENUM_ENROLS_AN_IDENTITY,
    )


@pytest.mark.parametrize(
    "flag", ["enroll_enterprise_reader", "enroll_operator_during_deploy"],
)
def test_an_empty_enum_may_not_enrol_an_identity(tmp_path: Path, flag: str) -> None:
    """No members, no generated group, so the flag would enrol nobody.

    The DBML grammar refuses an empty enum body, so the members are cleared
    after parsing. `validate_against_mapping` is public API and a caller that
    builds its own Schema reaches this, which is the same reason
    `build_schema_json` guards its own inputs. An empty enum is only a
    warning, so nothing else in the run stops the build.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=('Enum division {\n  "Field operations"\n}\n' + table("Docs", ID_PK, TITLE)),
        mapping=f"""
            entities:
              Docs: {{ kind: List, base_template: 100, site_role: default }}

            groups:
              - from_enum: division
                name: "{{member}} Editors"
                description: "Editors."
                owner_group: "Site Owners"
                {flag}: true
        """,
    )
    next(e for e in schema.enums if e.name == "division").members.clear()
    f = only(
        validate_against_mapping(schema, bundle),
        FindingCode.GROUP_ENUM_ENROLS_AN_IDENTITY,
    )
    assert flag in f.message
    assert "no members" in f.message


def test_a_generated_group_name_sharepoint_refuses_is_caught_at_build(
    tmp_path: Path,
) -> None:
    """The live failure, pinned.

    MEASURED 2026-09-21: a live deploy created six division groups from one
    `from_enum` declaration and then stopped at phase 1.4 on the seventh,
    whose member carried a comma: "The group name is empty, or you are using
    one or more of the following invalid characters:
    \" / \\ [ ] : | < > + = ; , ? * ' @".

    Nothing before this rule could see it. The template reads
    `{prefix} {member} Division` and carries nothing refused; only one of the
    names it generates does, so the name has to be judged after expansion or
    not at all.
    """
    findings = _folder_policy(
        tmp_path, group_name="{member} Division", folders="{from_enum: division}",
    )
    none_of(findings, FindingCode.GROUP_NAME_INVALID)

    comma = tmp_path / "comma"
    comma.mkdir()
    schema, bundle = pack(
        comma,
        dbml=(
            'Enum division {\n  "Community, aged & home care"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member} Division"
                description: "Editors."
                owner_group: "Site Owners"
        """,
    )
    f = only(validate_against_mapping(schema, bundle), FindingCode.GROUP_NAME_INVALID)
    assert "','" in f.message, f.message
    assert "{member_safe}" in f.message, "the message must name the way out"
    # `&` is allowed: sibling groups whose names carried one were created in
    # the same live run, which is what stops this widening to punctuation.
    assert "'&'" not in f.message


def test_member_safe_varies_a_name_as_the_uniqueness_rule_requires(
    tmp_path: Path,
) -> None:
    """Two members, so `group_enum_name_not_unique` is live.

    The single-member run below cannot say this: with one member the rule is
    skipped whatever the name carries. It matters because the help for that
    finding sends an author whose member holds a refused character to
    `{member_safe}`, and `{member}` alone would trade the finding for
    `group_name_invalid`.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum region {\n  "Alpha, Beta & Gamma"\n  "Delta"\n}\n'
            + table("Docs", ID_PK, TITLE, "Region region")
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: region
                name: "{member_safe} Editors"
                description: "Editors."
                owner_group: "Site Owners"
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    none_of(findings, FindingCode.GROUP_ENUM_NAME_NOT_UNIQUE)
    none_of(findings, FindingCode.GROUP_NAME_INVALID)


def test_member_safe_makes_a_refused_member_usable(tmp_path: Path) -> None:
    """`{member_safe}` replaces each refused character with a space and
    collapses the run, so the comma case becomes a name SharePoint accepts
    while the folder it secures keeps its real name."""
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Community, aged & home care"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member_safe} Division"
                description: "Editors."
                owner_group: "Site Owners"
        """,
    )
    findings = validate_against_mapping(schema, bundle)
    none_of(findings, FindingCode.GROUP_NAME_INVALID)

    from dbml_sharepoint.analysis.groups import declared_groups

    assert [g.name for g in declared_groups(
        bundle.mapping.permissions,
        {e.name: e.members for e in schema.enums},
    )] == ["Community aged & home care Division"]


def test_a_previous_name_that_expands_onto_the_current_one_is_dropped(
    tmp_path: Path,
) -> None:
    """Moving a generated group from `{member}` to `{member_safe}` renames
    only the members carrying a refused character.

    Every other member expands both templates to one string, so the group
    would declare itself as its own previous name and
    `renamed_from_is_a_declared_entity` would reject the whole migration,
    including the member whose name genuinely does need sanitising. The
    filter runs after expansion because that is where the two templates
    collide.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Community, aged & home care"\n'
            '  "Corporate"\n}\n'
            + table("Docs", ID_PK, TITLE, "Division division")
        ),
        mapping="""
            entities:
              Docs: { kind: List, base_template: 100, site_role: default }

            groups:
              - from_enum: division
                name: "{member_safe} Editors"
                renamed_from: ["{member} Editors"]
                description: "Editors."
                owner_group: "Site Owners"
        """,
    )
    none_of(
        validate_against_mapping(schema, bundle),
        FindingCode.RENAMED_FROM_IS_A_DECLARED_ENTITY,
    )

    from dbml_sharepoint.analysis.groups import declared_groups

    assert [
        (g.name, g.previous_names)
        for g in declared_groups(
            bundle.mapping.permissions,
            {e.name: e.members for e in schema.enums},
        )
    ] == [
        (
            "Community aged & home care Editors",
            ("Community, aged & home care Editors",),
        ),
        ("Corporate Editors", ()),
    ]
