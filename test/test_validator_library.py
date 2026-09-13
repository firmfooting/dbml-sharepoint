"""Validator: what a document library declares that a list cannot.

The file-identity vocabulary, declared folders and view scope. Each rule is
pinned in both directions where a direction exists: a library may, a list may
not, and the same declaration is asserted on both containers so a guard that
stops distinguishing them turns a test red.
"""

from pathlib import Path

from _builders import ID_PK, TITLE, table
from _findings import none_of, only
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


def test_a_per_column_declaration_on_the_file_name_is_undeployable() -> None:
    """FileLeafRef is a system column the per-field deploy loop never
    writes, so a formatter declared on it would validate clean and deploy
    nothing. Same rule as Created or Author."""
    findings = _findings(
        _docs(),
        column_formatting={"Docs": {"FileLeafRef": {"elmType": "div"}}},
    )
    only(findings, FindingCode.UNDEPLOYABLE_COLUMN_DECLARATION)
