# src/dbml_sharepoint/analysis/checks/_library.py
"""What a document library declares that a list cannot.

Declared folders and a view's folder scope are library concepts. They are
checked here, in their own module, rather than as arms in `_views.py::check`
or `_structure.py`, because both of those sit at or near the complexity
ceiling and a library rule should read as one function per question.
"""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.demo_marker import DEMO_TITLE_PREFIX
from dbml_sharepoint.analysis.file_names import invalid_file_name_reason
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.folders import UnknownFolderEnumError, declared_folders
from dbml_sharepoint.analysis.limits import LIST_VIEW_THRESHOLD
from dbml_sharepoint.analysis.typemap import element_type
from dbml_sharepoint.model.mapping_types import (
    DemoItem,
    EntityMapping,
    FoldersFromEnum,
    ViewDef,
)


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for entity_name, entity in vc.bundle.mapping.entities.items():
        at = Location(Section.ENTITIES, entity=entity_name, sub="folders")
        try:
            folders = declared_folders(
                entity.folder_source, vc.enum_members_by_name,
            )
        except UnknownFolderEnumError as err:
            # Resolved through the shared module and not by re-testing
            # membership here, so the sentence an operator reads and the
            # tuple the deploy is built from come from one answer. Nothing
            # further is judged about folders this entity has none of.
            findings.append(Finding(
                FindingCode.FOLDER_ENUM_UNKNOWN,
                f"entities[{entity_name}].folders: from_enum names "
                f"{err.enum!r}, which the schema does not declare. Declared "
                f"enums are: "
                f"{', '.join(sorted(vc.enum_members_by_name)) or 'none'}.",
                location=at,
            ))
            # Unresolved, which is not the same answer as "declares none".
            folders = None
        findings += _folder_enum_is_this_entity_s(vc, entity_name, entity)
        findings += _folders(
            entity_name, entity, folders or (),
            declared=bool(entity.folder_source),
        )
        for view in vc.bundle.mapping.views.get(entity_name, []):
            findings += _view_scope(entity_name, entity, view)
        for row in vc.bundle.mapping.demo_items.get(entity_name, []):
            findings += _demo_file(entity_name, entity, row, folders)
    findings += _folder_permissions(vc)
    return findings


def _folder_permissions(vc: ValidationContext) -> list[Finding]:
    """`list_permissions.folders.<entity>`: it must name a library with folders.

    Keyed by entity and never by folder, so the only questions left are
    whether the entity exists, whether it can hold folders, and whether it
    declares any. Which folders it declares is `declared_folders`' answer
    and is not re-derived here.
    """
    perms = vc.bundle.mapping.permissions
    if perms is None:
        return []
    at = Location(Section.LIST_PERMISSIONS, sub="folders")
    findings: list[Finding] = []
    for entity_name in perms.folder_policies:
        entity = vc.bundle.mapping.entities.get(entity_name)
        if entity is None:
            findings.append(Finding(
                FindingCode.UNKNOWN_TABLE,
                f"list_permissions.folders.{entity_name}: no such entity; the "
                f"mapping declares "
                f"{', '.join(sorted(vc.bundle.mapping.entities)) or 'none'}.",
                location=at,
            ))
            continue
        if not entity.is_library:
            findings.append(Finding(
                FindingCode.FOLDER_PERMISSIONS_ON_A_LIST,
                f"list_permissions.folders.{entity_name}: {entity_name} is not "
                f"a DocumentLibrary, so it has no folders to secure.",
                location=at,
            ))
            continue
        try:
            folders = declared_folders(entity.folder_source, vc.enum_members_by_name)
        except UnknownFolderEnumError:
            # Already reported against the entity by `check` above, where the
            # message can name the enum and the declared ones. Saying it twice
            # from two locations reads as two faults.
            continue
        if not folders:
            findings.append(Finding(
                FindingCode.FOLDER_PERMISSIONS_WITHOUT_FOLDERS,
                f"list_permissions.folders.{entity_name}: {entity_name} "
                f"declares no folders, so this policy governs nothing and no "
                f"folder ACL is written.",
                location=at,
            ))
    return findings


def _folder_enum_is_this_entity_s(
    vc: ValidationContext, entity_name: str, entity: EntityMapping,
) -> list[Finding]:
    """`folders.from_enum` usually names an enum this entity has a column of.

    A schema holds many enums and `from_enum` accepts any of them, so a name
    that matches a DIFFERENT enum resolves, passes every rule, and creates a
    full set of the wrong folders. Nothing downstream can see it: both
    declarations are individually valid, which is the same shape as the drift
    this spelling exists to remove.

    A warning rather than an error, because folders keyed by something the
    library does not store are a legitimate design and an enforced rule must
    not be stronger than what a reference implementation has to satisfy.
    """
    source = entity.folder_source
    if not isinstance(source, FoldersFromEnum):
        return []
    if source.enum not in vc.enum_members_by_name:
        return []  # folder_enum_unknown owns that sentence
    table = vc.tables_by_name.get(entity_name)
    if table is None:
        return []
    # `division[]` is a MultiChoice of the same enum, so compare elements.
    if any(element_type(column.type) == source.enum for column in table.columns):
        return []
    return [Finding(
        FindingCode.FOLDER_ENUM_NOT_A_COLUMN_TYPE,
        f"entities[{entity_name}].folders: from_enum names {source.enum!r}, "
        f"which no column on {entity_name} uses. That is legal, but it is "
        f"also what naming the wrong enum looks like: the folders resolve "
        f"and every one of them is wrong. Columns on {entity_name} carry: "
        f"{', '.join(sorted({element_type(c.type) for c in table.columns})) or 'nothing'}.",
        location=Location(Section.ENTITIES, entity=entity_name, sub="folders"),
    )]


def _demo_file(
    entity_name: str, entity: EntityMapping, row: DemoItem,
    folders: tuple[str, ...] | None,
) -> list[Finding]:
    """`demo_items[].file`: required on a library, refused on a list, and a
    legal, marked name filed in a declared folder.

    A library's items are files and a POST to /items is refused outright
    (MEASURED 2026-07-29, `library.file-vs-item.fileless-item-post` in
    document-library-probe.js), so the seeding script uploads the file
    through Files/add and sets the row's values on its item
    (`library.file.upload-path-files-add`, 2026-09-03). The file name is what
    a view and the file panel show (`library.file.name-field-is-leafref`), so
    it carries the sample-data notice a list row carries in its Title.
    """
    at = Location(Section.DEMO_ITEMS, entity=entity_name, sub=row.key)
    ctx = f"demo_items[{entity_name}].{row.key}"
    if row.file is None:
        if not entity.is_library:
            return []
        return [Finding(
            FindingCode.DEMO_FILE_REQUIRED_ON_LIBRARY,
            f"{ctx}: {entity_name} is a DocumentLibrary and this row declares no "
            f"file. A library's items are files, so declare "
            f"file: {{ name, folder, content }} for it to upload.",
            location=at,
        )]
    if not entity.is_library:
        return [Finding(
            FindingCode.DEMO_FILE_ON_A_LIST,
            f"{ctx}: file is declared and {entity_name} is a {entity.kind}; a "
            f"list row is created with a POST to /items and has nowhere to put "
            f"a file. Remove the key.",
            location=at,
        )]
    findings: list[Finding] = []
    if not row.file.name.startswith(DEMO_TITLE_PREFIX):
        findings.append(Finding(
            FindingCode.DEMO_FILE_NAME_MISSING_MARKER,
            f"{ctx}: file.name must start with '{DEMO_TITLE_PREFIX}'. On a "
            f"library the file name is the visible notice that identifies "
            f"this row as sample data.",
            location=at,
        ))
    reason = invalid_file_name_reason(row.file.name)
    if reason is not None:
        findings.append(Finding(
            FindingCode.DEMO_FILE_NAME_INVALID,
            f"{ctx}: {row.file.name!r} cannot be a file name: {reason}.",
            location=at,
        ))
    # None means unresolved, so membership is unanswerable rather than false.
    if (
        row.file.folder is not None
        and folders is not None
        and row.file.folder not in folders
    ):
        findings.append(Finding(
            FindingCode.DEMO_FILE_FOLDER_UNDECLARED,
            f"{ctx}: file.folder {row.file.folder!r} is not one of "
            f"{entity_name}'s declared folders "
            f"({', '.join(folders) or 'none declared'}).",
            location=at,
        ))
    return findings


def _view_scope(entity_name: str, entity: EntityMapping, view: ViewDef) -> list[Finding]:
    """`scope`: library only, and a warning where a grouping will stop rendering.

    MEASURED 2026-09-08, `library.folder.view-flattens-depth` in
    library-nesting-probe.js: a view read with no Scope returns only direct
    children, FilesOnly only the root file, and Recursive and RecursiveAll
    flatten the files at depth. `recursive` renders as Recursive rather than
    RecursiveAll because RecursiveAll adds subfolder rows a grouped view would
    count. The property write on a stored view is measured too
    (`library.view.scope-on-create-reads-back` and
    `library.view.scope-on-merge-reads-back`, 2026-09-13,
    library-guards-probe.js: Scope 1 reads back 1 both ways).
    """
    if view.scope is None:
        return []
    at = Location(Section.VIEWS, entity=entity_name, view=view.title, sub="scope")
    if not entity.is_library:
        return [Finding(
            FindingCode.VIEW_SCOPE_ON_A_LIST,
            f"views[{entity_name}].{view.title}: scope is declared and {entity_name} "
            f"is a {entity.kind}; only a DocumentLibrary has folders for a scope "
            f"to flatten. Remove the key.",
            location=at,
        )]
    if view.scope == "recursive" and view.group_by is not None:
        return [Finding(
            FindingCode.LIBRARY_GROUP_BY_FOLDER_SCOPED,
            f"views[{entity_name}].{view.title}: a recursive view groups by "
            f"{', '.join(view.group_by.fields)}. Past {LIST_VIEW_THRESHOLD:,} files "
            f"a root-scoped group-by is refused and only a folder-scoped one is "
            f"served (`library.large-list.preindex-group-by-refusal-signature`, "
            f"`library.large-list.foldered-group-by-folder-scoped`), so this "
            f"grouping stops rendering at that size.",
            location=at,
        )]
    return []


def _folders(
    entity_name: str, entity: EntityMapping, folders: tuple[str, ...],
    *, declared: bool,
) -> list[Finding]:
    """Declared folders: library only, legal names, no duplicates.

    Judged over the RESOLVED names, so an enum member that cannot be a
    folder name fails the build here rather than at the folder phase. That
    is the whole value of naming the enum: the schema's choices and the
    library's folders are one list, held to the folder rules.

    MEASURED 2026-09-03, `library.folder.creation-path` in folder-probe.js:
    POST web/GetFolderByServerRelativeUrl('<root>')/folders/add(url='<name>')
    answered HTTP 200 and returned an SP.Folder, so a declared name reaches
    the site as one URL segment under the library root. The name rules are
    Microsoft's (analysis/file_names.py).
    """
    at = Location(Section.ENTITIES, entity=entity_name, sub="folders")
    # Before the empty return: the container question is independent.
    if declared and not entity.is_library:
        return [Finding(
            FindingCode.FOLDERS_ON_A_LIST,
            f"entities[{entity_name}].folders: {entity_name} is a {entity.kind}, "
            f"and only a DocumentLibrary holds folders. Remove the key, or "
            f"declare kind: DocumentLibrary with base_template: 101.",
            location=at,
        )]
    findings: list[Finding] = []
    # Lower-cased because a folder is addressed by URL, which SharePoint
    # resolves without regard to case: two names differing only in case are
    # one folder declared twice.
    seen: dict[str, str] = {}
    for name in folders:
        reason = invalid_file_name_reason(name)
        if reason is not None:
            findings.append(Finding(
                FindingCode.FOLDER_NAME_INVALID,
                f"entities[{entity_name}].folders: {name!r} cannot be a folder "
                f"name: {reason}.",
                location=at,
            ))
        if name.lower() in seen:
            findings.append(Finding(
                FindingCode.DUPLICATE_FOLDER,
                f"entities[{entity_name}].folders: {name!r} duplicates "
                f"{seen[name.lower()]!r}.",
                location=at,
            ))
        seen.setdefault(name.lower(), name)
    return findings
