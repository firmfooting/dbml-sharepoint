"""The shape of the schema JSON `build_schema_json` returns and the manifest reads."""

from typing import NotRequired, TypedDict, TypeGuard

from dbml_sharepoint.jsonvalue import JsonValue, is_text_keyed


class Projection(TypedDict):
    name: str
    display_title: str
    show_field: str


# Functional form: `__metadata` would be name-mangled inside a class body.
FieldBody = TypedDict(
    "FieldBody",
    {
        "__metadata": dict[str, str],
        "Title": str,
        "FieldTypeKind": int,
        "Required": bool,
        "EnforceUniqueValues": bool,
        "Indexed": bool,
        "Description": str,
        "DefaultFormula": str,
        "DefaultValue": JsonValue,
        "MaxLength": int | None,
        "RichText": bool,
        "NumberOfLines": int,
        "AppendOnly": bool,
        "Choices": dict[str, list[str]],
        "FillInChoice": bool,
        "DisplayFormat": int,
        "SelectionMode": int,
        "LookupField": str,
        "AllowMultipleValues": bool,
        "OutputType": int | None,
        "Formula": str,
    },
    total=False,
)

TitlePatch = TypedDict(
    "TitlePatch",
    {
        "__metadata": dict[str, str],
        "Required": bool,
        "Description": str,
        "Title": str,
        "EnforceUniqueValues": bool,
        "Indexed": bool,
        "DefaultValue": JsonValue,
    },
    total=False,
)

LookupCreationParameters = TypedDict(
    "LookupCreationParameters",
    {
        "__metadata": dict[str, str],
        "FieldTypeKind": int,
        "Title": str,
        "Required": bool,
        "LookupFieldName": str,
    },
)


class FieldSpec(TypedDict):
    """One column to create; the keys after `body` are added as the list is built."""

    title: str
    body: FieldBody
    target_list: NotRequired[str]
    lookup_creation_xml: NotRequired[dict[str, str]]
    user_creation_xml: NotRequired[dict[str, str]]
    lookup_creation_parameters: NotRequired[LookupCreationParameters]
    projections: NotRequired[list[Projection]]
    display_title: NotRequired[str]
    custom_formatter: NotRequired[str | None]
    client_validation_formula: NotRequired[str]
    validation_formula: NotRequired[str]
    validation_message: NotRequired[str]
    seal: NotRequired[bool]


class RenamedFrom(TypedDict):
    title: str
    expected_marker: str


class BuiltinFormulaRef(TypedDict):
    builtin: str
    columns: list[str]


class ItemSecurity(TypedDict):
    read_security: int
    write_security: int
    read: JsonValue
    write: JsonValue


class FolderDefaultValue(TypedDict):
    field: str
    value: str


class FolderDefaults(TypedDict):
    folder: str
    values: list[FolderDefaultValue]


class ListRow(TypedDict):
    title: str
    kind: str
    base_template: int
    internal_name: NotRequired[str]
    is_library: bool
    folders: list[str]
    folder_defaults: list[FolderDefaults]
    description: str
    expected_marker: str
    renamed_from: list[RenamedFrom]
    content_types_enabled: bool
    enable_versioning: bool
    major_version_limit: int | None
    enable_minor_versions: bool
    fields_phase1: list[FieldSpec]
    builtin_formula_refs: NotRequired[list[BuiltinFormulaRef]]
    title_patch: TitlePatch | None
    validation_formula: str | None
    validation_message: str | None
    validation_described: str | None
    validation_hoisted: list[str]
    prevent_deletion: bool
    disable_attachments: bool
    require_checkout: bool | None
    enable_folder_creation: bool | None
    draft_version_visibility: int | None
    item_security: ItemSecurity | None


class Phase2Lookup(TypedDict):
    list: str
    target_list: str
    field: FieldSpec
    projections: list[Projection]


class IndexedColumn(TypedDict):
    list: str
    field: str


class ViewRow(TypedDict):
    list: str
    title: str
    view_fields: list[str]
    caml_query: str
    scope: int | None
    aggregations: str
    row_limit: int | None
    set_default: bool
    renamed_from: list[str]
    hidden: bool
    formatting: str | None
    widths: dict[str, int] | None
    url_slug: str
    adopts_builtin_view: bool


class FormFormattingRow(TypedDict):
    list: str
    client_form_custom_formatter: str


class FieldLinkRow(TypedDict):
    list: str
    hidden: dict[str, bool]


class FieldDefault(TypedDict):
    list: str
    field: str
    metadata_type: str
    default_value: JsonValue
    default_formula: JsonValue


class BasePermissions(TypedDict):
    high: str
    low: str


class PreviousName(TypedDict):
    name: str
    expected_marker: str


class PermissionLevelRow(TypedDict):
    name: str
    description: str
    expected_marker: str
    previous_names: list[PreviousName]
    base_permissions: BasePermissions


class GroupRow(TypedDict):
    name: str
    description: str
    expected_marker: str
    previous_names: list[PreviousName]
    owner_group: str | None
    allow_members_edit_membership: bool
    allow_request_to_join_leave: bool
    auto_accept_request_to_join_leave: bool
    only_allow_members_view_membership: bool
    require_empty_at_deploy: bool
    enroll: list[str]
    enroll_during_run: list[str]
    membership: JsonValue


class PrincipalRow(TypedDict):
    kind: str
    name: NotRequired[str]


class AssignmentRow(TypedDict):
    principal: PrincipalRow
    level: str


class AclScope(TypedDict):
    list: str
    folder: NotRequired[str]
    break_inheritance: bool
    reconcile_mode: str
    file_scopes: NotRequired[str]
    assignments: list[AssignmentRow]


class SeedItem(TypedDict):
    title: str
    fields: dict[str, JsonValue]
    skip_if_has_rows: bool


class SchemaJson(TypedDict):
    lists: list[ListRow]
    phase2_lookups: list[Phase2Lookup]
    indexed_columns: list[IndexedColumn]
    views: list[ViewRow]
    form_formatting: list[FormFormattingRow]
    field_links: list[FieldLinkRow]
    field_defaults: list[FieldDefault]
    permission_levels: list[PermissionLevelRow]
    groups: list[GroupRow]
    acl_scopes: list[AclScope]
    requires_manage_permissions: bool
    seed_items: list[SeedItem]


def is_field_spec(value: dict[str, JsonValue]) -> TypeGuard[FieldSpec]:
    """Whether ``value`` carries what the generator reads from an extension's field."""
    body = value.get("body")
    if not isinstance(value.get("title"), str) or not is_text_keyed(body):
        return False
    kind = body.get("FieldTypeKind")
    if not isinstance(kind, int) or isinstance(kind, bool):
        return False
    return isinstance(body.get("Formula", ""), str)
