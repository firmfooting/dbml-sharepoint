"""What each validation entry point is responsible for.

There are three, they partition the rules, and until now nothing tested the
partition. That matters because 132 test call sites use
`validate_against_mapping` directly and about eleven of them assert emptiness
— and emptiness through a partial entry point is a weaker claim than it reads
as.

Concretely: a schema whose column type is misspelled produces ONE error from
`validate` and ZERO from `validate_against_mapping`. An `== []` against the
latter passes on a schema the build rejects.

The partition itself is deliberate and correct — `validate` needs no mapping,
so it can run on a schema alone. These tests exist so that moving a rule
between the two is a decision somebody makes on purpose rather than a quiet
change in what a hundred tests cover.
"""

from pathlib import Path

import pytest
from _packs import pack

from dbml_sharepoint.analysis.validator import (
    Finding,
    validate,
    validate_against_mapping,
    validate_all,
)
from dbml_sharepoint.extension import BaseExtension
from dbml_sharepoint.model.mapping_loader import MappingBundle
from dbml_sharepoint.model.parser import Schema


def _errors(findings: list[Finding]) -> list[str]:
    return [f.message for f in findings if f.severity == "error"]


@pytest.fixture
def broken_schema(tmp_path: Path) -> tuple[Schema, MappingBundle]:
    """A schema-only defect: `peson` is not a type the typemap knows.

    Chosen because it is decidable from the DBML alone, so it belongs
    unambiguously to `validate` and not to the mapping cross-checks.
    """
    return pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
              Owner peson
            }
        """,
        mapping="""
            entities:
              Risk: { kind: List, base_template: 100, site_role: default }
        """,
    )


def test_validate_owns_the_schema_only_rules(broken_schema: tuple[Schema, MappingBundle]) -> None:
    schema, _ = broken_schema
    assert any("unknown type 'peson'" in m for m in _errors(validate(schema)))


def test_validate_against_mapping_does_not_repeat_them(
    broken_schema: tuple[Schema, MappingBundle],
) -> None:
    """Not a defect — the rule needs no mapping, so it does not live here.

    Pinned so that a well-meaning change that duplicates the rule into the
    mapping checks has to be deliberate: two copies of one rule is how they
    come to disagree, and this repository has fixed that class before.
    """
    schema, bundle = broken_schema
    assert not any(
        "unknown type" in m for m in _errors(validate_against_mapping(schema, bundle))
    )


def test_a_mapping_rule_does_not_appear_in_the_schema_pass(tmp_path: Path) -> None:
    """The partition holds in the other direction too."""
    schema, bundle = pack(
        tmp_path,
        dbml="""
            Table Risk {
              Id int [pk, increment]
              Title nvarchar [not null]
            }
        """,
        mapping="""
            entities:
              Risk: { kind: List, base_template: 100, site_role: default }
            views:
              Nope:
                - title: V
                  fields: [Title]
        """,
    )
    assert any("Nope" in m for m in _errors(validate_against_mapping(schema, bundle)))
    assert not any("Nope" in m for m in _errors(validate(schema)))


def test_validate_all_is_the_union_and_is_what_the_cli_runs(
    broken_schema: tuple[Schema, MappingBundle],
) -> None:
    """`cli.py` calls `validate_all`, which is why a misspelled type reaches
    the operator as `[ERROR] Project.Owner: unknown type 'peson'.` rather than
    as a traceback out of the generator.

    A test that wants to claim "this declaration is clean" should use this,
    not one of the halves.
    """
    schema, bundle = broken_schema
    every = _errors(validate_all(schema, bundle, BaseExtension()))
    assert any("unknown type 'peson'" in m for m in every)
    for message in _errors(validate(schema)):
        assert message in every
    for message in _errors(validate_against_mapping(schema, bundle)):
        assert message in every
