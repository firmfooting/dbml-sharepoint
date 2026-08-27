# src/dbml_sharepoint/extract/field_xml.py
"""CAML `<Field>` XML to a normalised field record.

A live read returns one of these elements in each field's `SchemaXml`
property, and it is everything the extraction has to work from.

Nothing in this module interprets a field as a DBML type. It reports what
the element says and no more; `decode.py` owns the translation, and the
split is what lets a field this tool cannot type still be listed in the
extraction notes rather than dropped.
"""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from xml.etree.ElementTree import ParseError

#: Fields SharePoint provisions itself, which a schema must not re-declare.
#:
#: `Title` is deliberately absent: it is a built-in by every test below, and
#: it is also the one built-in this tool DOES manage (`nvarchar [not null]`
#: in every shipped family), so `is_builtin` exempts it by name.
#:
#: A closed set alongside the attribute tests rather than instead of them.
#: The attribute tests catch built-ins nobody listed here; the names catch
#: the ones a tenant has customised until the attributes no longer say so.
BUILTIN_INTERNAL_NAMES = frozenset({
    "ContentType", "ContentTypeId", "Attachments", "Author", "Editor",
    "Created", "Modified", "ID", "GUID", "FileLeafRef", "FileDirRef",
    "FileRef", "FSObjType", "Order", "WorkflowVersion", "InstanceID",
    "UniqueId", "owshiddenversion", "Version", "_UIVersion",
    "_UIVersionString", "_ModerationStatus", "_ModerationComments",
    "_Level", "_IsCurrentVersion", "_HasCopyDestinations", "_CopySource",
    "AppAuthor", "AppEditor", "ItemChildCount", "FolderChildCount",
    "Restricted", "OriginatorId", "NoExecute", "ContentVersion",
    "AccessPolicy", "ComplianceAssetId", "SMTotalSize", "SMLastModifiedDate",
    "SMTotalFileStreamSize", "SMTotalFileCount", "ParentVersionString",
    "ParentLeafName", "DocConcurrencyNumber", "PrincipalCount", "Combine",
    "RepairDocument", "TemplateUrl", "xd_ProgID", "xd_Signature", "Last_x0020_Modified",
    "Created_x0020_Date", "File_x0020_Type", "HTML_x0020_File_x0020_Type",
    "_SourceUrl", "_SharedFileIndex", "SelectTitle", "SelectFilename",
    "Edit", "LinkTitleNoMenu", "LinkTitle", "LinkTitle2", "LinkFilename",
    "LinkFilenameNoMenu", "LinkFilename2", "DocIcon", "ServerUrl",
    "EncodedAbsUrl", "BaseName", "MetaInfo", "_CommentFlags", "_CommentCount",
    "_DisplayName", "_ShortcutUrl", "_ShortcutSiteId", "_ShortcutWebId",
    "_ShortcutUniqueId", "_ExtendedDescription", "_ip_UnifiedCompliancePolicyUIAction",
    "_ip_UnifiedCompliancePolicyProperties", "TaxCatchAll", "TaxCatchAllLabel",
})

#: The built-in this tool owns rather than skips.
MANAGED_BUILTIN = "Title"

#: SharePoint's own namespace for the fields it ships. A field carrying it
#: was not created by anybody's schema.
_BUILTIN_SOURCE_ID = "http://schemas.microsoft.com/sharepoint/v3"

#: The only way an entity definition reaches the parser, so it is refused.
_DOCTYPE = re.compile(r"<!DOCTYPE", re.IGNORECASE)

#: CAML spells booleans as these words, not as `1`/`0`.
_TRUE = "TRUE"


def _flag(element: ET.Element, name: str, *, default: bool = False) -> bool:
    raw = element.get(name)
    if raw is None:
        return default
    return raw.strip().upper() == _TRUE


def _int(element: ET.Element, name: str) -> int | None:
    raw = element.get(name)
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        # A non-numeric MaxLength/NumLines is the tenant's, not ours to
        # repair; treat it as absent and let the notes record the field.
        return None


def _child_text(element: ET.Element, tag: str) -> str | None:
    found = element.find(tag)
    if found is None:
        return None
    return "".join(found.itertext())


@dataclass(frozen=True)
class RawField:
    """One column exactly as its `<Field>` element describes it.

    Frozen because a decoded field is evidence. Everything downstream
    derives from it and nothing has any business editing the reading.
    """

    internal_name: str
    display_name: str
    sp_type: str
    required: bool = False
    unique: bool = False
    description: str = ""
    choices: tuple[str, ...] = ()
    default: str | None = None
    indexed: bool = False
    sealed: bool = False
    hidden: bool = False
    read_only: bool = False
    from_base_type: bool = False
    source_id: str = ""
    group: str = ""
    # Type-specific. `None` means the attribute was absent, which is not
    # the same as a zero or an empty string on any of them.
    max_length: int | None = None
    rich_text: bool | None = None
    num_lines: int | None = None
    date_only: bool | None = None
    fill_in_choice: bool | None = None
    multi_value: bool = False
    user_selection_mode: str | None = None
    lookup_list: str | None = None
    lookup_field: str | None = None
    formula: str | None = None
    result_type: str | None = None
    field_refs: tuple[str, ...] = ()
    custom_formatter: str | None = None
    client_validation_formula: str | None = None
    validation_formula: str | None = None
    validation_message: str | None = None
    #: The element as it arrived, so the notes can quote a field this tool
    #: could not type rather than describing it from memory.
    raw_xml: str = field(default="", repr=False)

    @property
    def is_managed_builtin(self) -> bool:
        return self.internal_name == MANAGED_BUILTIN


class FieldXmlError(ValueError):
    """A `<Field>` element that is not one, or is not parseable."""


def parse_field_xml(xml: str) -> RawField:
    """Decode one CAML `<Field>` element.

    Raises `FieldXmlError` rather than letting `ParseError` out, so a
    single malformed element in a read names itself instead of aborting
    the extraction with a stack trace from the XML library.
    """
    if _DOCTYPE.search(xml):
        # MEASURED 2026-08-27 on CPython 3.14: `ET.fromstring` refuses an
        # external entity but expands an internal one, so a document type
        # declaration is the whole billion-laughs surface. SharePoint's
        # SchemaXml is one element with no prolog, so refusing it costs
        # nothing a real read carries.
        raise FieldXmlError(
            "carries a document type declaration. A SharePoint field element "
            "has none, and entity expansion is refused here rather than run.",
        )
    try:
        element = ET.fromstring(xml)  # noqa: S314 - no DTD reaches here
    except ParseError as exc:
        raise FieldXmlError(f"not parseable as XML: {exc}") from exc
    if element.tag != "Field":
        raise FieldXmlError(f"expected a <Field> element, found <{element.tag}>")

    internal = element.get("StaticName") or element.get("Name") or ""
    if not internal:
        raise FieldXmlError("has neither StaticName nor Name")

    choices = tuple(
        "".join(choice.itertext())
        for choice in element.findall("./CHOICES/CHOICE")
    )
    refs = tuple(
        name
        for ref in element.findall("./FieldRefs/FieldRef")
        if (name := ref.get("Name")) is not None
    )

    validation = element.find("Validation")
    validation_formula = None
    validation_message = None
    if validation is not None:
        # The text content is the formula. The `Script` attribute is
        # SharePoint's own compiled form of it, regenerated on save, so it
        # is read past rather than recovered.
        validation_formula = "".join(validation.itertext()) or None
        validation_message = validation.get("Message")

    return RawField(
        internal_name=internal,
        display_name=element.get("DisplayName") or internal,
        sp_type=element.get("Type") or "",
        required=_flag(element, "Required"),
        unique=_flag(element, "EnforceUniqueValues"),
        description=element.get("Description") or "",
        choices=choices,
        default=_child_text(element, "Default"),
        indexed=_flag(element, "Indexed"),
        sealed=_flag(element, "Sealed"),
        hidden=_flag(element, "Hidden"),
        read_only=_flag(element, "ReadOnly"),
        from_base_type=_flag(element, "FromBaseType"),
        source_id=element.get("SourceID") or "",
        group=element.get("Group") or "",
        max_length=_int(element, "MaxLength"),
        rich_text=_flag(element, "RichText") if element.get("RichText") else None,
        num_lines=_int(element, "NumLines"),
        date_only=(
            element.get("Format") == "DateOnly" if element.get("Format") else None
        ),
        fill_in_choice=(
            _flag(element, "FillInChoice") if element.get("FillInChoice") else None
        ),
        multi_value=_flag(element, "Mult"),
        user_selection_mode=element.get("UserSelectionMode"),
        lookup_list=element.get("List"),
        lookup_field=element.get("ShowField"),
        formula=_child_text(element, "Formula"),
        result_type=element.get("ResultType"),
        field_refs=refs,
        custom_formatter=element.get("CustomFormatter"),
        client_validation_formula=_child_text(element, "ClientValidationFormula"),
        validation_formula=validation_formula,
        validation_message=validation_message,
        raw_xml=xml,
    )


def is_builtin(raw: RawField) -> bool:
    """Whether SharePoint provisions this field itself.

    `Title` is exempt: it satisfies every test here and is still the one
    built-in a schema declares, because the tool manages its display name,
    its description and its required flag.
    """
    if raw.is_managed_builtin:
        return False
    return (
        raw.internal_name in BUILTIN_INTERNAL_NAMES
        or raw.group.startswith("_")
        or raw.hidden
        or raw.from_base_type
        or raw.source_id == _BUILTIN_SOURCE_ID
    )


def builtin_reason(raw: RawField) -> str:
    """Why `is_builtin` said yes, for the extraction notes.

    The notes list every skipped field, and "skipped as a built-in" is not
    a reason somebody can check. Naming the test that fired lets a reader
    disagree with it.
    """
    if raw.internal_name in BUILTIN_INTERNAL_NAMES:
        return "a known built-in column name"
    if raw.group.startswith("_"):
        return f"in the hidden field group {raw.group!r}"
    if raw.hidden:
        return 'marked Hidden="TRUE"'
    if raw.from_base_type:
        return 'marked FromBaseType="TRUE" (inherited from the list template)'
    if raw.source_id == _BUILTIN_SOURCE_ID:
        return "in SharePoint's own field namespace"
    return "a built-in column"
