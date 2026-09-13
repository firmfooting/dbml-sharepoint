# src/dbml_sharepoint/analysis/checks/_library.py
"""What a document library declares that a list cannot.

Declared folders and a view's folder scope are library concepts. They are
checked here, in their own module, rather than as arms in `_views.py::check`
or `_structure.py`, because both of those sit at or near the complexity
ceiling and a library rule should read as one function per question.
"""

from dbml_sharepoint.analysis.checks.context import ValidationContext
from dbml_sharepoint.analysis.file_names import invalid_file_name_reason
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.limits import LIST_VIEW_THRESHOLD
from dbml_sharepoint.model.mapping_types import EntityMapping, ViewDef


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for entity_name, entity in vc.bundle.mapping.entities.items():
        findings += _folders(entity_name, entity)
        for view in vc.bundle.mapping.views.get(entity_name, []):
            findings += _view_scope(entity_name, entity, view)
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


def _folders(entity_name: str, entity: EntityMapping) -> list[Finding]:
    """Declared folders: library only, legal names, no duplicates.

    MEASURED 2026-09-03, `library.folder.creation-path` in folder-probe.js:
    POST web/GetFolderByServerRelativeUrl('<root>')/folders/add(url='<name>')
    answered HTTP 200 and returned an SP.Folder, so a declared name reaches
    the site as one URL segment under the library root. The name rules are
    Microsoft's (analysis/file_names.py).
    """
    if not entity.folders:
        return []
    at = Location(Section.ENTITIES, entity=entity_name, sub="folders")
    if not entity.is_library:
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
    for name in entity.folders:
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
