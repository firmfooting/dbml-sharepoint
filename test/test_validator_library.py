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

from dbml_sharepoint.analysis.checks._structure import TEMPLATE_BY_KIND
from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.analysis.validator import validate_against_mapping
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


def _library_findings(entity: EntityMapping, **sections: object) -> list[Finding]:
    schema = make_schema(make_table("Docs", make_column("Title", required=True)))
    bundle = make_bundle(entities={"Docs": entity}, **sections)  # type: ignore[arg-type]
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
    """The shipped legislative compliance register declared its divisions
    twice, once as an enum and once as a folder list, and an edit to the
    enum left the deploy creating the four retired folders. Naming the enum
    removes the second copy."""
    findings = _folders_from_enum(
        tmp_path, "DocumentLibrary", 101,
        '  "Clinical services"\n  "Corporate & community services"',
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
            tmp_path, "DocumentLibrary", 101, '  "Clinical services"',
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
            'Enum division {\n  "Clinical services"\n}\n'
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
            'Enum division {\n  "Clinical services"\n}\n'
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
        tmp_path, "List", 100, '  "Clinical services"', named="divison",
    )
    only(findings, FindingCode.FOLDER_ENUM_UNKNOWN)
    only(findings, FindingCode.FOLDERS_ON_A_LIST)


def test_folders_from_the_entitys_own_enum_are_not_flagged(tmp_path: Path) -> None:
    """The ordinary shape stays quiet, or the warning is noise."""
    none_of(
        _folders_from_enum(
            tmp_path, "DocumentLibrary", 101, '  "Clinical services"',
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
            'Enum division {\n  "Clinical services"\n}\n'
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
                  values: { Division: "Clinical services" }
                  file: { name: "[DEMO] Privacy.txt", folder: "Clinical services" }
                - key: d2
                  values: { Division: "Clinical services" }
                  file: { name: "[DEMO] Records.txt", folder: "Clinical services" }
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
            tmp_path, "DocumentLibrary", 101, '  "Clinical/services"',
        ),
        FindingCode.FOLDER_NAME_INVALID,
    )
    assert "/" in f.message


def test_folders_from_enum_are_refused_on_a_list(tmp_path: Path) -> None:
    """Whichever way the folders are spelled, only a library holds them."""
    f = only(
        _folders_from_enum(tmp_path, "List", 100, '  "Clinical services"'),
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
    with pytest.raises(MappingShapeError, match=r"demo_items\.Docs\[0\]\.file"):
        _demo(
            tmp_path, "DocumentLibrary", 101,
            'values: { Division: "Clinical services" }\n'
            '                  file: { folder: "Clinical services" }',
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
            'Enum division {\n  "Clinical services"\n  "Corporate services"\n}\n'
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
    assert {"Clinical services", "Corporate services"} == {
        folder for folder in ("Clinical services", "Corporate services")
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
            'Enum division {\n  "Clinical, services"\n}\n'
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


@pytest.mark.parametrize(
    "flag", ["enroll_enterprise_reader", "enroll_operator_during_deploy"],
)
def test_an_enum_group_cannot_enrol_an_identity(tmp_path: Path, flag: str) -> None:
    """Each flag enrols ONE identity, and `from_enum` makes one group per
    member to enrol it into.

    Refused rather than given a meaning it does not have. It also keeps the
    three callers that ask whether ANY declaration carries these flags --
    `pipeline`, `wizard` and `manifestgen`, none of which holds a schema and
    so none of which can resolve the enum -- correct by construction.
    """
    schema, bundle = pack(
        tmp_path,
        dbml=('Enum division {\n  "Clinical services"\n}\n' + table("Docs", ID_PK, TITLE)),
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
            'Enum division {\n  "Clinical, community & aged services"\n}\n'
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


def test_member_safe_makes_a_refused_member_usable(tmp_path: Path) -> None:
    """`{member_safe}` replaces each refused character with a space and
    collapses the run, so the comma case becomes a name SharePoint accepts
    while the folder it secures keeps its real name."""
    schema, bundle = pack(
        tmp_path,
        dbml=(
            'Enum division {\n  "Clinical, community & aged services"\n}\n'
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
    # Still one group per member: {member_safe} varies the name exactly as
    # {member} does, so it must not trip the collapse rule either.
    none_of(findings, FindingCode.GROUP_ENUM_NAME_NOT_UNIQUE)

    from dbml_sharepoint.analysis.groups import declared_groups

    assert [g.name for g in declared_groups(
        bundle.mapping.permissions,
        {e.name: e.members for e in schema.enums},
    )] == ["Clinical community & aged services Division"]
