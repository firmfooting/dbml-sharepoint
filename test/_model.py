"""Domain objects for tests, without going through text and the filesystem.

391 of 877 test functions took `tmp_path` and 382 obtained their inputs by
writing DBML/YAML to disk and parsing it back, to test pure functions. The
text was never the subject: it was the only way to get a `Schema`.

Text still belongs in the tests that are ABOUT the text -- `test_parser.py`,
`test_mapping_loader.py` -- and in `test_model_contract.py`, which proves
these builders and the loader do not disagree.

Three rules this module keeps, each of which is a way it could go wrong:

1. **Every builder returns the REAL domain type.** A parallel test-only model
   would be a second dialect, and the contract test could not tell the two
   apart because it would be comparing the dialect against itself.
2. **Nothing mutable is shared between calls.** `Column`, `Table`, `Schema`,
   `Mapping` and `PermissionsConfig` are all mutable dataclasses and tests do
   mutate what they are given, so a module-level `ID = Column(...)` or a
   module-level defaults dict would alias one object into every schema in the
   suite. Everything here is built fresh per call.
3. **Defaults match what the LOADER produces, not what the dataclass
   declares.** They differ, and `permissions` is the case that bites -- see
   `_loader_defaults`.

Note the name collision with `_builders`: `_builders.table` composes DBML
TEXT, `_model.table` builds a `Table` OBJECT. Import one or the other under an
alias when a test needs both, as `test_model_contract.py` does.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Any, TypedDict, Unpack

from dbml_sharepoint.model.mapping_loader import (
    ColumnValidation,
    CrossSiteRef,
    DemoItem,
    EntityMapping,
    EntitySection,
    FormFormatting,
    FormVisibility,
    ListValidation,
    Mapping,
    MappingBundle,
    PermissionsConfig,
    PolymorphicPattern,
    RetentionPolicy,
    RetiredColumn,
    RetirementStrip,
    Versioning,
    ViewDef,
    WatchedList,
)
from dbml_sharepoint.model.parser import (
    Column,
    EnumDef,
    Reference,
    Schema,
    Table,
    TableIndex,
)

# --- Schema -----------------------------------------------------------------


def id_column() -> Column:
    """The `Id int [pk, increment]` every table in the suite declares.

    A function rather than a constant: `Column` is a mutable dataclass, so one
    shared instance would be the same object in every table in every test.

    `required` stays False deliberately. That is what the parser produces for
    `[pk, increment]` -- pydbml does not imply `not_null` from `pk` -- and a
    builder that "corrected" it would be asserting something no DBML file in
    this repository actually says.
    """
    return Column(name="Id", type="int", is_pk=True, is_auto_increment=True)


def column(
    name: str,
    type: str = "nvarchar",  # noqa: A002  (the field on Column is `type`; a
    # second spelling here is how the two come to disagree)
    *,
    required: bool = False,
    unique: bool = False,
    ref: str | None = None,
    default: str | int | bool | None = None,
    note: str = "",
) -> Column:
    """One column. `ref="Risk.Id"` makes it a DBML reference.

    `required` defaults to False -- i.e. NULLABLE -- and must be asked for by
    name. The text idiom it replaces defaults the other way: `_builders.TITLE`
    is `Title nvarchar [not null]`, and several fixtures need a nullable Title.
    A shorthand that quietly supplied `not null` would change which validation
    rules those fixtures reach while every one of them still passed.
    """
    reference = None
    if ref is not None:
        target_table, target_column = ref.split(".")
        reference = Reference(target_table=target_table, target_column=target_column)
    return Column(
        name=name,
        type=type,
        required=required,
        unique=unique,
        default=default,
        ref=reference,
        note=note,
    )


def person(name: str) -> Column:
    """A person column -- one of the two join-bearing shapes."""
    return column(name, "person")


def ref(name: str, target: str) -> Column:
    """A lookup column -- the other join-bearing shape."""
    return column(name, "int", ref=target)


def table(
    name: str,
    *columns: Column | str,
    indexes: Sequence[TableIndex | str] | None = None,
    note: str = "",
) -> Table:
    """A table with an implicit `Id` primary key.

    A bare string is shorthand for a default-typed, NULLABLE column, so
    `table("Risk", "Title")` reads the way the DBML did. Anything else --
    a type, `required=True`, a ref -- is spelled with `column()`.

    `indexes` takes bare column names for the single-column shape SharePoint
    accepts, or a full `TableIndex` for the shapes it does NOT: a composite
    `(Status, Category)`, or one carrying a `name`.

    Being able to build an invalid index is the point, not a hole. DBML's
    parser produces both, the validator's job is to refuse them, and a
    builder that could only express valid input would make those refusals
    untestable at the object level. Same reasoning as accepting `Column`
    objects alongside bare names above.
    """
    cols = [id_column()] + [column(c) if isinstance(c, str) else c for c in columns]
    return Table(
        name=name,
        columns=cols,
        indexes=[
            TableIndex(columns=(i,)) if isinstance(i, str) else i
            for i in indexes or []
        ],
        note=note,
    )


def enum(name: str, *members: str) -> EnumDef:
    """A DBML enum. The parser strips the quotes, so these are bare values."""
    return EnumDef(name=name, members=list(members))


def schema(
    *tables: Table,
    enums: list[EnumDef] | None = None,
    project_note: str = "",
    project_name: str = "",
) -> Schema:
    return Schema(
        tables=list(tables),
        enums=enums or [],
        project_note=project_note,
        project_name=project_name,
    )


# --- Mapping ----------------------------------------------------------------


class MappingSections(TypedDict, total=False):
    """Every `Mapping` field except `prefix` and `entities`, which `mapping()`
    takes by name.

    A `TypedDict` rather than `**sections: object`. The plan offered either,
    with two `# type: ignore[arg-type]` as the price of the second; but an
    untyped `**kwargs` in the builder is the same untyped boundary the rest of
    this plan is closing, and it fails in the worst way -- a misspelled section
    is accepted, silently dropped, and the test then asserts about a feature it
    never turned on.

    `test_the_section_typeddict_covers_every_mapping_field` pins this against
    `Mapping`'s own fields, so a section added to the model cannot be one the
    builders have no way to express.
    """

    prefix_owner: str
    prefix_registry: str
    cross_site_reference_columns: list[CrossSiteRef]
    versioning_default: Versioning
    versioning_overrides: dict[str, dict[str, Any]]
    enum_sources: dict[str, Path]
    watched_lists: list[WatchedList]
    polymorphic_patterns: list[PolymorphicPattern]
    retention_policies_source: Path | None
    extension: str | None
    permissions: PermissionsConfig | None
    calculated_formulas: dict[str, dict[str, str]]
    form_visibility: dict[str, EntitySection[FormVisibility]]
    column_validation: dict[str, EntitySection[ColumnValidation]]
    views: dict[str, list[ViewDef]]
    field_sets: dict[str, dict[str, list[str]]]
    demo_items: dict[str, list[DemoItem]]
    display_name_mode: str | None
    display_name_overrides: dict[str, dict[str, str]]
    column_style_specs: dict[str, dict[str, dict[str, Any]]]
    column_formatting: dict[str, dict[str, dict[str, Any]]]
    form_formatting: dict[str, FormFormatting]
    list_validation: dict[str, ListValidation]
    retired_columns: dict[str, dict[str, RetiredColumn]]
    retirement_strips: list[RetirementStrip]
    seal_columns: bool
    prevent_list_deletion: bool


def _loader_defaults() -> MappingSections:
    """What `load_mapping` leaves on a mapping that declares nothing.

    Not the same as the dataclass defaults, and the difference is not cosmetic.
    `load_mapping` runs `_parse_permissions` unconditionally, so a loaded
    mapping's `permissions` is an EMPTY `PermissionsConfig` -- never `None`.
    `checks/_permissions.py` opens with `if bundle.mapping.permissions is not
    None`, so a builder taking the dataclass default of `None` would skip that
    entire check module for every test built this way, while looking correct
    and costing no assertion.

    `versioning_default` is the same story in miniature: the dataclass has no
    default at all, and the loader's is `Versioning(True, 500, False)`.

    Rebuilt per call because these lists, dicts and the `PermissionsConfig`
    are mutable and tests mutate them.
    """
    return {
        "prefix_owner": "",
        "prefix_registry": "",
        "cross_site_reference_columns": [],
        "versioning_default": Versioning(
            enable_versioning=True, major_version_limit=500, enable_minor_versions=False,
        ),
        "versioning_overrides": {},
        "enum_sources": {},
        "watched_lists": [],
        "permissions": PermissionsConfig(
            levels=[], groups=[], default_policy=None, overrides={},
        ),
    }


def mapping(
    *,
    entities: list[str] | dict[str, EntityMapping] | None = None,
    prefix: str = "APP_",
    **sections: Unpack[MappingSections],
) -> Mapping:
    """A mapping. `entities=["Risk"]` gets the default declaration for each."""
    declared: dict[str, EntityMapping]
    if entities is None:
        declared = {}
    elif isinstance(entities, list):
        declared = {
            name: EntityMapping(
                name=name, kind="List", base_template=100, site_role="default",
            )
            for name in entities
        }
    else:
        declared = entities
    resolved = _loader_defaults()
    resolved.update(sections)
    return Mapping(prefix=prefix, entities=declared, **resolved)


def bundle(
    *,
    entities: list[str] | dict[str, EntityMapping] | None = None,
    prefix: str = "APP_",
    enum_choices: dict[str, list[str]] | None = None,
    retention_policies: dict[str, RetentionPolicy] | None = None,
    retention_list_defaults: dict[str, str] | None = None,
    extension_configs: dict[str, dict[str, Any]] | None = None,
    source_paths: dict[str, Path] | None = None,
    **sections: Unpack[MappingSections],
) -> MappingBundle:
    """A bundle around `mapping(...)`, which is what the checks consume.

    The five bundle-level fields are spelled out rather than forwarded, so a
    `enum_choices=` meant for the bundle cannot land in the mapping's
    `**sections` and be rejected as an unknown section -- or worse, resemble
    one that exists.
    """
    return MappingBundle(
        mapping=mapping(entities=entities, prefix=prefix, **sections),
        enum_choices=enum_choices if enum_choices is not None else {},
        retention_policies=retention_policies if retention_policies is not None else {},
        retention_list_defaults=(
            retention_list_defaults if retention_list_defaults is not None else {}
        ),
        extension_configs=extension_configs if extension_configs is not None else {},
        source_paths=source_paths if source_paths is not None else {},
    )
