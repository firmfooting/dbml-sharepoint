# test/test_derived_columns.py
"""Derived reporting columns: the declaration, the rules and the emitted M.

These columns are the one thing this mapping declares that no deploy ever
verifies. A SharePoint field is created, read back and reconciled; a derived
column is a string that becomes M and is first read by Power BI, at refresh,
after the model is published. So the tests here stand in for the readback
the rest of the pipeline has.
"""

import re
from pathlib import Path
from typing import Any

import pytest
from _model import bundle as make_bundle
from _model import column, person
from _model import ref as make_ref
from _model import schema as make_schema
from _model import table as make_table
from _paths import FIXTURES, SOLUTION_TEMPLATES

from dbml_sharepoint.analysis.derived import report_column_names
from dbml_sharepoint.analysis.findings import Finding, FindingCode
from dbml_sharepoint.analysis.validator import validate_against_mapping
from dbml_sharepoint.generators.report_m import generate_powerquery
from dbml_sharepoint.generators.reportgen import (
    generate_data_dictionary,
    generate_sql_views,
)
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.mapping_types import (
    DerivedColumn,
    MappingBundle,
    ReportingOptions,
)
from dbml_sharepoint.model.parser import Schema, parse_dbml

#: The least a mapping can say and still load, so a loader test is about the
#: declaration under test and nothing else.
_MINIMAL = (
    "prefix: APP_\n"
    "entities:\n"
    "  Risk: {kind: List, base_template: 100, site_role: default}\n"
)

FAMILIES = sorted(
    path.parent.parent.name
    for path in SOLUTION_TEMPLATES.glob("*/10-design/schema.dbml")
)


def _schema() -> Schema:
    return make_schema(
        make_table("Decision", column("Title"), column("Status")),
        make_table(
            "Risk",
            column("Title"),
            column("Status"),
            column("Score", "int"),
            person("Owner"),
            make_ref("ToleranceDecision", "Decision.Id"),
        ),
        make_table(
            "Action",
            column("Title"),
            column("Status"),
            column("DueDate", "date"),
            make_ref("RelatedRisk", "Risk.Id"),
        ),
    )


def _bundle(risk: list[DerivedColumn], **kwargs: Any) -> MappingBundle:
    return make_bundle(
        entities=["Risk", "Decision", "Action"],
        derived_columns={"Risk": risk},
        **kwargs,
    )


def _errors(schema: Schema, bundle: MappingBundle) -> list[Finding]:
    return [
        f for f in validate_against_mapping(schema, bundle)
        if f.severity == "error"
    ]


def _codes(schema: Schema, bundle: MappingBundle) -> set[FindingCode]:
    return {f.code for f in _errors(schema, bundle)}


def _risk_query(bundle: MappingBundle) -> str:
    return generate_powerquery(_schema(), bundle, "default")["APP_Risk.pq"]


# ------------------------------------------------------------- the rules


def test_a_derived_column_on_an_unknown_entity_is_refused() -> None:
    bundle = make_bundle(
        entities=["Risk", "Decision", "Action"],
        derived_columns={
            "Nowhere": [
                DerivedColumn(kind="expr", name="X", type="text", m='"a"'),
            ],
        },
    )
    assert FindingCode.DERIVED_UNKNOWN_ENTITY in _codes(_schema(), bundle)


def test_a_derived_column_reading_a_column_that_is_not_there_is_refused() -> None:
    """THE rule this feature turns on. Nothing between the build and Power BI
    reads these names, so an unresolved one is a refresh failure after
    publication rather than a build failure, and it takes every query queued
    behind it. Measured on a consumer's model: release 3.1.0 renamed each
    list's Title, six derived lookups went on asking for the old name, and
    thirteen queries were blocked."""
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="IsStale", type="logical",
            m='[LastReviewed] < [Status]',
        ),
    ])
    finding = next(
        f for f in _errors(_schema(), bundle)
        if f.code is FindingCode.DERIVED_UNKNOWN_REFERENCE
    )
    assert "[LastReviewed]" in finding.message
    # The one that DOES resolve is not reported.
    assert "[Status]" not in finding.message


def test_a_derived_column_may_read_one_declared_above_it() -> None:
    """Declaration order is the contract: a flag reads the column a lookup
    two entries up produced, which is how the consumer's model was written
    and what makes the ordering worth keeping."""
    bundle = _bundle([
        DerivedColumn(
            kind="lookup", from_entity="Decision", via="ToleranceDecision",
            pick={"ToleranceStatus": "Status"},
            types={"ToleranceStatus": "text"},
        ),
        DerivedColumn(
            kind="expr", name="HasAuthority", type="logical",
            m='[ToleranceStatus] = "Approved"',
        ),
    ])
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE not in _codes(_schema(), bundle)


def test_a_derived_column_may_not_read_one_declared_below_it() -> None:
    """The same rule from the other side. M binds a step to the step above
    it, so a forward reference is not a late binding, it is a failure."""
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="HasAuthority", type="logical",
            m='[ToleranceStatus] = "Approved"',
        ),
        DerivedColumn(
            kind="lookup", from_entity="Decision", via="ToleranceDecision",
            pick={"ToleranceStatus": "Status"},
            types={"ToleranceStatus": "text"},
        ),
    ])
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE in _codes(_schema(), bundle)


def test_a_derived_name_that_is_taken_is_refused() -> None:
    """`Table.AddColumn` onto a name the table has fails the refresh rather
    than overwriting, so this cannot be left to be discovered there."""
    bundle = _bundle([
        DerivedColumn(kind="expr", name="Status", type="text", m='"x"'),
    ])
    assert FindingCode.DERIVED_NAME_COLLIDES in _codes(_schema(), bundle)


def test_replace_is_how_a_column_already_there_is_computed_over() -> None:
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="Status", type="text", replace=True,
            m='if [Status] = null then "Unknown" else [Status]',
        ),
    ])
    assert FindingCode.DERIVED_NAME_COLLIDES not in _codes(_schema(), bundle)


def test_replace_over_a_column_that_is_not_there_is_refused() -> None:
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="Absent", type="text", replace=True, m='"x"',
        ),
    ])
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE in _codes(_schema(), bundle)


def test_a_lookup_needs_a_via_that_really_is_a_lookup() -> None:
    bundle = _bundle([
        DerivedColumn(
            kind="lookup", from_entity="Decision", via="Status",
            pick={"D": "Status"}, types={"D": "text"},
        ),
    ])
    assert FindingCode.DERIVED_LOOKUP_BAD_TARGET in _codes(_schema(), bundle)


def test_a_lookup_whose_via_points_elsewhere_is_refused() -> None:
    """The keys come from the ref and the query read comes from `from`, so a
    disagreement joins one list against another list's keys and matches
    nothing, silently."""
    bundle = _bundle([
        DerivedColumn(
            kind="lookup", from_entity="Action", via="ToleranceDecision",
            pick={"D": "Status"}, types={"D": "text"},
        ),
    ])
    finding = next(
        f for f in _errors(_schema(), bundle)
        if f.code is FindingCode.DERIVED_LOOKUP_BAD_TARGET
    )
    assert "points at Decision" in finding.message


def test_a_lookup_picking_a_column_the_target_lacks_is_refused() -> None:
    bundle = _bundle([
        DerivedColumn(
            kind="lookup", from_entity="Decision", via="ToleranceDecision",
            pick={"D": "Nonsense"}, types={"D": "text"},
        ),
    ])
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE in _codes(_schema(), bundle)


def test_a_count_needs_a_child_column_pointing_back() -> None:
    """A count reads the join from the CHILD's end, and a `via` that points
    somewhere else groups rows against keys they do not carry."""
    bundle = _bundle([
        DerivedColumn(
            kind="count", from_entity="Action", via="Status",
            name="N", aggregate="count", type="Int64",
        ),
    ])
    finding = next(
        f for f in _errors(_schema(), bundle)
        if f.code is FindingCode.DERIVED_COUNT_BAD_SOURCE
    )
    assert "is not a lookup column" in finding.message


def test_a_count_from_an_entity_that_is_not_in_the_schema_is_refused() -> None:
    bundle = _bundle([
        DerivedColumn(
            kind="count", from_entity="Nowhere", via="RelatedRisk",
            name="N", aggregate="count", type="Int64",
        ),
    ])
    assert FindingCode.DERIVED_COUNT_BAD_SOURCE in _codes(_schema(), bundle)


def test_a_count_filter_resolves_against_the_child_not_this_list() -> None:
    """A `where` selects the CHILD rows. Reading it against this list's
    columns is how a filter silently matches nothing and the count reads
    zero, which is a wrong number rather than a missing one."""
    ok = _bundle([
        DerivedColumn(
            kind="count", from_entity="Action", via="RelatedRisk",
            name="DueCount", aggregate="count", type="Int64",
            where="[DueDate] <> null",
        ),
    ])
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE not in _codes(_schema(), ok)
    # `Score` is a column of Risk, not of Action.
    bad = _bundle([
        DerivedColumn(
            kind="count", from_entity="Action", via="RelatedRisk",
            name="DueCount", aggregate="count", type="Int64",
            where="[Score] > 3",
        ),
    ])
    assert FindingCode.DERIVED_UNKNOWN_REFERENCE in _codes(_schema(), bad)


def test_a_users_lookup_needs_a_person_column_and_the_users_table() -> None:
    """`_Users` is the one source that is not an entity: a person column has
    no ref, and the pack gives it a key into the users dimension instead."""
    entry = DerivedColumn(
        kind="lookup", from_entity="_Users", via="Owner",
        pick={"OwnerEmail": "EMail"}, types={"OwnerEmail": "text"},
    )
    on = _bundle([entry], reporting=ReportingOptions(users_table=True))
    assert FindingCode.DERIVED_LOOKUP_BAD_TARGET not in _codes(_schema(), on)
    off = _bundle([entry])
    finding = next(
        f for f in _errors(_schema(), off)
        if f.code is FindingCode.DERIVED_LOOKUP_BAD_TARGET
    )
    assert "users_table" in finding.message


def test_a_users_lookup_on_a_column_that_is_not_a_person_is_refused() -> None:
    bundle = _bundle(
        [DerivedColumn(
            kind="lookup", from_entity="_Users", via="Status",
            pick={"E": "EMail"}, types={"E": "text"},
        )],
        reporting=ReportingOptions(users_table=True),
    )
    assert FindingCode.DERIVED_LOOKUP_BAD_TARGET in _codes(_schema(), bundle)


# ------------------------------------------------------------- the shape


def test_the_loader_refuses_a_kind_it_has_no_plan_for(tmp_path: Path) -> None:
    """`filter` in particular: a reporting column may not DROP rows, because
    every audit and count beside it assumes the query carries the list."""
    path = tmp_path / "mapping.yaml"
    path.write_text(
        _MINIMAL
        + "derived_columns:\n  Risk:\n    - kind: filter\n      m: 'true'\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="deliberately absent"):
        load_mapping(path)


@pytest.mark.parametrize(("body", "message"), [
    (
        "    - kind: expr\n      name: X\n      type: guess\n      m: '1'\n",
        "type must be one of",
    ),
    (
        ("    - kind: count\n      from: Action\n      via: RelatedRisk\n"
         "      name: X\n      aggregate: min\n      type: date\n"),
        "`column` is required",
    ),
    (
        ("    - kind: count\n      from: Action\n      via: RelatedRisk\n"
         "      name: X\n      aggregate: count\n      type: Int64\n"
         "      column: DueDate\n"),
        "must be absent",
    ),
    (
        ("    - kind: lookup\n      from: Decision\n      via: A\n      key: B\n"
         "      pick: {X: Status}\n      types: {X: text}\n"),
        "Exactly one",
    ),
    (
        ("    - kind: lookup\n      from: Decision\n      via: A\n"
         "      pick: {X: Status}\n      types: {Y: text}\n"),
        "must be one of",
    ),
])
def test_the_loader_refuses_a_malformed_declaration(
    tmp_path: Path, body: str, message: str,
) -> None:
    """Shape is the loader's; whether the names RESOLVE is the validator's.
    An aggregate with no column and a type nobody has decided both reach the
    query as `type any`, which loads as an Error value in every populated
    cell while the refresh reports success."""
    path = tmp_path / "mapping.yaml"
    path.write_text(
        _MINIMAL + f"derived_columns:\n  Risk:\n{body}",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        load_mapping(path)


# --------------------------------------------------------- the emitted M


def test_an_expr_becomes_one_added_column() -> None:
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="IsOpen", type="logical", m='[Status] = "Open"',
        ),
    ])
    query = _risk_query(bundle)
    assert '"IsOpen",' in query
    assert 'each [Status] = "Open",' in query
    assert "type logical" in query


def test_a_replace_reads_the_row_and_keeps_the_column_in_place() -> None:
    """`Table.TransformColumns` hands the expression the VALUE alone, so a
    fallback that reads any other column of the row cannot be written that
    way. Every replace in the family's own configuration is such a
    fallback."""
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="Status", type="text", replace=True,
            m='if [Status] = null then [Title] else [Status]',
        ),
    ])
    query = _risk_query(bundle)
    assert "Table.ReplaceValue(" in query
    assert "each [Status]," in query
    assert "Replacer.ReplaceValue," in query


def test_a_lookup_joins_on_the_packs_own_keys() -> None:
    """Keys, not ids: a key carries the site, so appending two sites cannot
    join a row to the same-numbered row of the other."""
    bundle = _bundle([
        DerivedColumn(
            kind="lookup", from_entity="Decision", via="ToleranceDecision",
            pick={"ToleranceStatus": "Status"},
            types={"ToleranceStatus": "text"},
        ),
    ])
    query = _risk_query(bundle)
    assert '{"ToleranceDecision Key"}' in query
    assert '{"Decision Key"}' in query
    assert '{"Decision Key", "Status"}' in query
    assert '{"ToleranceStatus"}' in query


def test_a_picked_column_is_translated_to_what_the_target_query_renames_it_to() -> None:
    """An author writes internal names everywhere. The target query renames
    its columns in its LAST step, so the join has to ask for the name it
    ends with, and that map is read off the target's own plan rather than
    re-derived."""
    schema = make_schema(
        make_table("Decision", column("Title"), column("ReviewStatus")),
        make_table("Risk", column("Title"), make_ref("D", "Decision.Id")),
    )
    bundle = make_bundle(
        entities=["Risk", "Decision"], display_name_mode="auto",
        derived_columns={"Risk": [
            DerivedColumn(
                kind="lookup", from_entity="Decision", via="D",
                pick={"DStatus": "ReviewStatus"}, types={"DStatus": "text"},
            ),
        ]},
    )
    query = generate_powerquery(schema, bundle, "default")["APP_Risk.pq"]
    assert '{"Decision Key", "Review Status"}' in query
    assert "ReviewStatus" not in query.split("Derived1")[1]


def test_a_count_groups_the_child_and_joins_the_aggregate_back() -> None:
    bundle = _bundle([
        DerivedColumn(
            kind="count", from_entity="Action", via="RelatedRisk",
            name="OpenActions", aggregate="count", type="Int64",
            where='[Status] = "Open"',
        ),
    ])
    query = _risk_query(bundle)
    assert 'Table.SelectRows(#"APP_Action", each [Status] = "Open")' in query
    assert '{"RelatedRisk Key"}' in query
    assert "each Table.RowCount(_)" in query


def test_a_count_that_finds_another_site_reports_blank_not_zero() -> None:
    """THE guard. A derived join reads the other query as it stands, and the
    guide tells an operator building a multi-site report to duplicate each
    query per site. A duplicate pointed elsewhere still reads THIS child, so
    nothing matches and a coalesced zero would be a confident wrong number
    where the truth is not zero. An EMPTY child list still reads zero: it
    names no site and there are no rows to miss."""
    bundle = _bundle([
        DerivedColumn(
            kind="count", from_entity="Action", via="RelatedRisk",
            name="N", aggregate="count", type="Int64",
        ),
    ])
    query = _risk_query(bundle)
    assert 'Table.Column(#"APP_Action", "Site Url")' in query
    assert (
        "if DerivedSite1 = null or DerivedSite1 = SiteRoot then 0 else null"
    ) in query


def test_only_a_count_coalesces_a_missing_match() -> None:
    """A min over no rows is unknown, not zero, so nothing is filled in."""
    bundle = _bundle([
        DerivedColumn(
            kind="count", from_entity="Action", via="RelatedRisk",
            name="FirstDue", aggregate="min", column="DueDate", type="date",
        ),
    ])
    query = _risk_query(bundle)
    assert "each List.Min(_[DueDate])" in query
    assert "then 0 else null" not in query


def test_a_users_lookup_reads_the_users_dimension() -> None:
    bundle = _bundle(
        [DerivedColumn(
            kind="lookup", from_entity="_Users", via="Owner",
            pick={"OwnerEmail": "EMail"}, types={"OwnerEmail": "text"},
        )],
        reporting=ReportingOptions(users_table=True),
    )
    query = _risk_query(bundle)
    assert '#"_Users"' in query
    assert '{"Owner Key"}' in query
    assert '{"User Key", "Email"}' in query


def test_every_cross_query_reference_is_a_quoted_identifier() -> None:
    """`#"..."` is valid M for ANY name and a bare identifier is not:
    `_Users` leads with an underscore, and a prefix carrying a space or a
    dash would not be an identifier at all."""
    bundle = _bundle(
        [
            DerivedColumn(
                kind="count", from_entity="Action", via="RelatedRisk",
                name="N", aggregate="count", type="Int64",
            ),
            DerivedColumn(
                kind="lookup", from_entity="_Users", via="Owner",
                pick={"OwnerEmail": "EMail"}, types={"OwnerEmail": "text"},
            ),
        ],
        reporting=ReportingOptions(users_table=True),
    )
    query = _risk_query(bundle)
    for name in ("APP_Action", "_Users"):
        assert f'#"{name}"' in query
        # No bare reference anywhere, which would resolve only by luck.
        assert f"({name}," not in query


def test_a_derived_column_takes_a_display_title_like_any_other() -> None:
    bundle = _bundle(
        [DerivedColumn(
            kind="expr", name="IsOpen", type="logical", m='[Status] = "Open"',
        )],
        display_name_mode="auto",
    )
    assert '{"IsOpen", "Is Open"}' in _risk_query(bundle)


def test_the_derived_steps_run_after_the_keys_and_before_the_rename() -> None:
    """A join reads the keys, so it cannot precede them; the rename must see
    the derived columns, so it cannot precede those."""
    bundle = _bundle(
        [DerivedColumn(
            kind="lookup", from_entity="Decision", via="ToleranceDecision",
            pick={"ToleranceStatus": "Status"},
            types={"ToleranceStatus": "text"},
        )],
        display_name_mode="auto",
    )
    query = _risk_query(bundle)
    assert query.index("WithFkKey1 =") < query.index("Derived1 =")
    assert query.index("Derived1 =") < query.index("RenamedForModel =")


def test_the_sql_views_carry_no_derived_column() -> None:
    """A row-level M expression has no SQL to translate to, so the SQL side
    carries none of them rather than some of them. `data-dictionary.md` says
    so where a reader would look."""
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="IsOpen", type="logical", m='[Status] = "Open"',
        ),
    ])
    assert "IsOpen" not in generate_sql_views(_schema(), bundle, "default")


def test_the_dictionary_says_a_derived_column_is_not_on_the_list() -> None:
    """A reader looking for one of these on the site will not find it, and
    the dictionary is where they would look first."""
    bundle = _bundle([
        DerivedColumn(
            kind="expr", name="IsOpen", type="logical", m='[Status] = "Open"',
            description="Whether the risk is still open.",
        ),
    ])
    md = generate_data_dictionary(_schema(), bundle, "default")
    assert "| IsOpen | Reporting only (computed per row) |" in md
    assert "Whether the risk is still open." in md
    assert "## Reporting-only columns" in md


# ----------------------------------------------- the derivation is pinned


@pytest.mark.parametrize("family", FAMILIES)
def test_the_shared_column_set_matches_what_the_query_declares(
    family: str,
) -> None:
    """`report_column_names` is what the validator checks a derived
    reference against, and the query is what actually carries the columns.
    A drift between them makes the rule either refuse a valid name or, far
    worse, pass one that fails at refresh.

    Compared against the REAL generated query for every shipped family, so
    the pin cannot be satisfied by two copies of the same mistake.
    """
    root = SOLUTION_TEMPLATES / family
    schema = parse_dbml(root / "10-design/schema.dbml")
    bundle = load_mapping(root / "20-configure/mapping.yaml")
    enums = {e.name for e in schema.enums}
    queries = generate_powerquery(schema, bundle, "default")
    checked = 0
    for table in schema.tables:
        query = queries.get(f"{bundle.mapping.prefix}{table.name}.pq")
        if query is None:
            continue
        _, _, rest = query.partition("Declared = Table.SelectColumns(")
        listed = re.search(r"\{(.*?)\}\n", rest, re.DOTALL)
        assert listed is not None, table.name
        columns = [c.strip().strip('"') for c in listed.group(1).split(",")]
        # Only the steps AFTER `Declared` add columns the model keeps. The
        # guarded expands above it add theirs into a branch `Declared` then
        # filters, so counting those would double every lookup title.
        after = rest[listed.end():]
        columns += re.findall(
            r'Table\.AddColumn\(\s*\n?\s*\w+, "([^"]+)"', after,
        )
        for landed in re.findall(
            r"Table\.ExpandTableColumn\([^)]*?\{([^{}]*)\}\n?\s*\)", after,
        ):
            columns += re.findall(r'"([^"]+)"', landed)
        assert len(columns) == len(set(columns)), f"{family}.{table.name}"
        # MEMBERSHIP, not order: the query lists its multi-value columns
        # after the rest, and nothing downstream depends on the sequence.
        assert set(columns) == set(
            report_column_names(table, bundle, enums),
        ), f"{family}.{table.name}"
        checked += 1
    assert checked, family


def test_the_simple_fixture_declares_no_derived_columns() -> None:
    """The feature is off unless a mapping asks for it, so every family that
    declares nothing emits exactly what it did before."""
    bundle = load_mapping(FIXTURES / "sharepoint-mapping.yaml")
    assert bundle.mapping.derived_columns == {}
    schema = parse_dbml(FIXTURES / "simple.dbml")
    for query in generate_powerquery(schema, bundle, "default").values():
        assert "Derived1" not in query
        assert "DerivedSite1" not in query
