"""The builders must agree with the loader, or they are a second dialect.

Today every validator test incidentally proves the YAML loader accepts its
input, because every test goes text -> disk -> parse. Building objects
directly is faster and clearer but drops that guarantee, so it is replaced
here with an explicit one: anything the builders can express must survive a
round trip through the real writer and the real loader unchanged.

This is the whole safety argument for Phase 3. If it is weak, the phase is
wrong.

So the assertions here are **whole-object equality**, not a field subset.
Comparing `(name, type, ref)` would have said nothing about `required`, and
`required` is precisely where a builder silently changes what a migrated test
exercises: `_builders.TITLE` is `Title nvarchar [not null]`, several fixtures
need a nullable Title, and a rule keyed on requiredness would flip without a
single test going red. `Schema`, `Table`, `Column` and `Mapping` are all
dataclasses, so `==` covers every field they will ever grow.
"""

from dataclasses import fields
from pathlib import Path

import pytest
from _model import (
    MappingSections,
    bundle,
    column,
    enum,
    mapping,
    person,
    ref,
    schema,
    table,
)
from _packs import entities as yaml_entities
from _packs import pack

from dbml_sharepoint.model.mapping_loader import Mapping


def test_builders_and_loader_agree_on_a_representative_document(
    tmp_path: Path,
) -> None:
    built_schema = schema(
        table("Risk", column("Title", "nvarchar"), person("Owner")),
        table("FollowUp", ref("Risk", "Risk.Id")),
    )
    built_bundle = bundle(entities=["Risk", "FollowUp"])

    parsed_schema, parsed_bundle = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar
              Owner person
            }
            Table FollowUp {
              Id int [pk, increment]
              Risk int [ref: > Risk.Id]
            }
        """,
        mapping="""
            entities:
              Risk: { kind: List, base_template: 100, site_role: default }
              FollowUp: { kind: List, base_template: 100, site_role: default }
        """,
    )

    # Table by table first: a whole-schema mismatch reports as one enormous
    # repr, and the column list is where a disagreement will actually be.
    assert [t.name for t in built_schema.tables] == [t.name for t in parsed_schema.tables]
    for built, parsed in zip(built_schema.tables, parsed_schema.tables, strict=True):
        assert built.columns == parsed.columns
    assert built_schema == parsed_schema
    assert built_bundle.mapping == parsed_bundle.mapping


def test_builders_and_loader_agree_on_every_column_attribute(tmp_path: Path) -> None:
    """The attributes the representative document happens not to carry.

    `required`, `unique`, `default`, `note`, a table index and an enum are each
    a field the parser fills in and a builder could get wrong in silence. The
    pk column is here too: DBML `[pk, increment]` yields `is_pk` and
    `is_auto_increment` but leaves `required` FALSE, which is not what "primary
    key" suggests and is exactly the sort of thing a hand-written builder gets
    backwards.
    """
    built = schema(
        table(
            "Risk",
            column("Title", required=True),
            column("Code", unique=True),
            column("Reason", note="why it exists"),
            column("Rank", "int", default=3),
            person("Owner"),
            indexes=["Code"],
        ),
        enums=[enum("status", "Open", "Closed")],
    )

    parsed, _ = pack(
        tmp_path,
        dbml="""
            Enum status {
              "Open"
              "Closed"
            }
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
              Code nvarchar [unique]
              Reason nvarchar [note: 'why it exists']
              Rank int [default: 3]
              Owner person

              indexes {
                Code
              }
            }
        """,
        mapping=yaml_entities("Risk"),
    )

    assert built.tables[0].columns == parsed.tables[0].columns
    assert built.tables[0].indexes == parsed.tables[0].indexes
    assert built.enums == parsed.enums
    assert built == parsed


def test_a_built_mapping_is_one_the_loader_could_have_produced(tmp_path: Path) -> None:
    """Whole-`Mapping` equality, called out separately because of `permissions`.

    `load_mapping` always runs `_parse_permissions`, so a loaded mapping's
    `permissions` is an EMPTY `PermissionsConfig` and never `None` -- while the
    dataclass default is `None`, and `checks/_permissions.py` skips its entire
    module on `is None`. A builder that took the dataclass default would hand
    several hundred migrated tests a mapping no YAML file can produce, and
    quietly stop running the permission checks against any of them.
    """
    _, parsed = pack(tmp_path, dbml="Table Risk {\n  Id int [pk, increment]\n}",
                     mapping=yaml_entities("Risk"))

    assert mapping(entities=["Risk"]) == parsed.mapping
    assert mapping(entities=["Risk"]).permissions is not None


def test_the_section_typeddict_covers_every_mapping_field() -> None:
    """The builder's keyword surface is the whole of `Mapping`, minus the two
    it takes by name.

    A field added to `Mapping` that is missing here is a section no migrated
    test can declare -- and `**kwargs: object` would have accepted the
    keyword and thrown it away, which is the untyped boundary this plan
    exists to close.
    """
    assert set(MappingSections.__annotations__) == {
        f.name for f in fields(Mapping)
    } - {"prefix", "entities"}


def test_an_unknown_section_is_a_type_error_not_a_silent_drop() -> None:
    """mypy is the real gate; this is the runtime half of the same statement."""
    with pytest.raises(TypeError):
        mapping(entities=["Risk"], form_visibilty={})  # type: ignore[call-arg]


def test_the_builders_do_not_share_mutable_state_between_calls() -> None:
    """`Column`, `Table`, `Schema`, `Mapping` and `PermissionsConfig` are all
    MUTABLE dataclasses, and tests do mutate the objects they are handed.

    A module-level `ID = Column(...)` constant, or a module-level defaults
    dict holding `[]`, would alias that one object into every schema in the
    suite -- so one test appending a watched list would change what an
    unrelated test in another worker file exercises.
    """
    first, second = table("Risk"), table("Risk")
    assert first.columns[0] == second.columns[0]
    assert first.columns[0] is not second.columns[0]

    one, two = mapping(), mapping()
    assert one.watched_lists is not two.watched_lists
    assert one.permissions is not two.permissions
