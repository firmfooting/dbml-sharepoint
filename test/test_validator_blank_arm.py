"""Validator: a nullable column's save rule must say what a blank does.

The defect this closes (issue #156) is a column validation formula that
compares an optional value against something and never states the blank
case. Whether SharePoint refuses the blank operand or ignores the rule has
not been measured, and the two answers differ by whether a row in its
normal starting state can be saved at all. The guarded spelling behaves the
same under both, so the rule requires it.

The exemption worth reading twice is the clock one. A rule comparing a date
with `today` is NOT reported, because `analysis/save_rules.py` hoists it
onto the list rule and wraps it in an `is_null` arm on the way. That is 46
of the 71 clock comparisons in the shipped library, so a rule without the
exemption would refuse 25 families that already build correctly.
"""
from pathlib import Path

import pytest
from _findings import none_of, only
from _packs import blocks, entities, pack

from dbml_sharepoint.analysis.checks import _retirement
from dbml_sharepoint.analysis.checks._retirement import GRANDFATHERED_BLANK_ARMS
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location, Section
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.catalogue import available_solutions
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml

CODE = FindingCode.COLUMN_VALIDATION_MISSING_A_BLANK_ARM

_TABLE = """
    Table Job {
      Id int [pk, increment]
      Title nvarchar [not null]
      Cost number
      Budget number [not null]
      DoneDate date
    }
"""


def _rule(tmp_path: Path, column: str, when: str) -> list[Finding]:
    schema, bundle = pack(
        tmp_path,
        dbml=_TABLE,
        mapping=blocks(entities("Job"), f"""
            column_validation:
              Job:
                reconcile: declared
                columns:
                  {column}:
                    when: {when}
                    message: "Check {column}."
        """),
    )
    return validate_against_mapping(schema, bundle)


def test_a_bare_comparison_on_a_nullable_column_is_refused(tmp_path: Path) -> None:
    finding = only(
        _rule(tmp_path, "Cost", "[{ field: Cost, op: geq, value: 0 }]"), CODE,
    )
    assert finding.location == Location(
        Section.COLUMN_VALIDATION, entity="Job", column="Cost",
    )
    assert "'Cost'" in finding.message
    assert finding.severity == "error"


def test_the_blank_arm_satisfies_the_rule(tmp_path: Path) -> None:
    none_of(
        _rule(tmp_path, "Cost", """
                      any_of:
                        - { field: Cost, op: is_null }
                        - { field: Cost, op: geq, value: 0 }
        """),
        CODE,
    )


def test_a_not_null_column_needs_no_blank_arm(tmp_path: Path) -> None:
    """A column that cannot be blank has no blank case to state."""
    none_of(_rule(tmp_path, "Budget", "[{ field: Budget, op: geq, value: 0 }]"), CODE)


def test_a_rule_that_requires_a_value_is_not_asked_to_admit_a_blank(
    tmp_path: Path,
) -> None:
    """`is_not_null` beside the comparison settles the blank case the other
    way. Reporting here would ask the author to write a rule contradicting
    itself."""
    none_of(
        _rule(tmp_path, "Cost", """
                      all_of:
                        - { field: Cost, op: is_not_null }
                        - { field: Cost, op: geq, value: 0 }
        """),
        CODE,
    )


def test_a_rule_with_no_comparison_is_not_reported(tmp_path: Path) -> None:
    """A rule made only of `is_null` compares nothing and is entirely ABOUT
    the blank. `is_not_null` reaches the same exemption through
    `refuses_a_blank`, so this uses the spelling that reaches it here and
    nowhere else."""
    none_of(_rule(tmp_path, "Cost", "[{ field: Cost, op: is_null }]"), CODE)


def test_a_clock_comparison_is_exempt_because_the_build_guards_it(
    tmp_path: Path,
) -> None:
    """Hoisted onto the list rule under an `is_null` arm by
    `joined_list_validation`, so the emitted formula already admits the
    blank. Reporting it would enforce a rule the build itself satisfies by
    another route."""
    none_of(
        _rule(tmp_path, "DoneDate", "[{ field: DoneDate, op: leq, value: today }]"), CODE,
    )


def test_the_grandfather_list_is_exactly_the_shipped_violations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ratchet, measured rather than declared.

    #156 reserves the library-wide sweep for one change with one argument, so
    the eight spots measured on 2026-09-06 build on. Emptying the exemption and
    running the real check over every shipped family pins the set both ways: a
    NEW unguarded comparison in a shipped family fails here even though the
    validator would let it build, and an entry that has been fixed has to come
    out rather than linger and silence a rule that still exists.
    """
    monkeypatch.setattr(_retirement, "GRANDFATHERED_BLANK_ARMS", frozenset())
    fired = set()
    for solution in available_solutions():
        schema = parse_dbml(solution.schema_path)
        bundle = load_mapping(solution.mapping_path)
        for finding in validate_against_mapping(schema, bundle):
            if finding.code is CODE:
                assert finding.location is not None
                fired.add((finding.location.entity, finding.location.column))
    assert fired == set(GRANDFATHERED_BLANK_ARMS)


def test_no_shipped_family_reports_the_rule_as_exempted() -> None:
    """The other half: with the real exemption in place every shipped family
    is clean, so this change adds no build error to the library."""
    for solution in available_solutions():
        schema = parse_dbml(solution.schema_path)
        bundle = load_mapping(solution.mapping_path)
        none_of(validate_against_mapping(schema, bundle), CODE)
