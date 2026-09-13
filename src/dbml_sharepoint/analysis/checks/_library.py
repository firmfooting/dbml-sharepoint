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
from dbml_sharepoint.model.mapping_types import EntityMapping


def check(vc: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for entity_name, entity in vc.bundle.mapping.entities.items():
        findings += _folders(entity_name, entity)
    return findings


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
