# test/test_conditions.py
"""The shared condition grammar: parse, normalise, render."""

import pytest

from dbml_sharepoint.analysis.conditions import (
    CAML,
    CAPABILITIES,
    EXPRESSION,
    MAX_LEAVES,
    NEGATION,
    SYSTEM_COLUMN_TYPES,
    VALIDATION,
    describe,
    measure_tree,
    normalise,
    to_caml,
    to_expression,
    to_validation,
    validate_condition,
)
from dbml_sharepoint.model.conditions import Condition, Group, Leaf, parse_condition


def test_bare_list_is_all_of() -> None:
    """views[].where has always been a flat ANDed list; that spelling must
    keep working, so a bare list is sugar for all_of."""
    condition = parse_condition([{"field": "Status", "op": "eq", "value": "Open"}], "ctx")
    assert condition == Group("all_of", (Leaf("Status", "eq", "Open"),))


def test_groups_nest() -> None:
    condition = parse_condition(
        {
            "any_of": [
                {"field": "A", "op": "eq", "value": 1},
                {"all_of": [{"field": "B", "op": "is_null"}]},
            ],
        },
        "ctx",
    )
    assert isinstance(condition, Group)
    assert condition.kind == "any_of"
    inner = condition.children[1]
    assert isinstance(inner, Group)
    assert inner.kind == "all_of"


def test_operand_transforms_parse() -> None:
    """`property` reaches into a person/lookup column, `measure` compares a
    derived scalar. Both leave op/value uniform so negation stays a flip."""
    persons = parse_condition(
        [{"field": "Owner", "property": "title", "op": "neq", "value": ""}], "ctx",
    )
    assert isinstance(persons, Group)
    leaf = persons.children[0]
    assert isinstance(leaf, Leaf)
    assert leaf.property == "title"

    lengths = parse_condition(
        [{"field": "Note", "measure": "length", "op": "gt", "value": 10}], "ctx",
    )
    assert isinstance(lengths, Group)
    measured = lengths.children[0]
    assert isinstance(measured, Leaf)
    assert measured.measure == "length"


@pytest.mark.parametrize(
    ("raw", "match"),
    [
        ({}, "exactly one of"),
        ({"all_of": [], "any_of": []}, "exactly one of"),
        ({"all_of": []}, "empty"),
        ({"all_of": "nope"}, "list"),
        ({"nope": []}, "exactly one of"),
        ([{"op": "eq", "value": 1}], "'field' is required"),
        ([{"field": "A"}], "'op' is required"),
        ("=TRUE", "mapping or a list"),
    ],
)
def test_structural_errors(raw: object, match: str) -> None:
    """Shape problems are load errors naming the offending context, as
    everywhere else in the mapping loader."""
    with pytest.raises(ValueError, match=match):
        parse_condition(raw, "ctx")


def test_unknown_leaf_key_is_rejected() -> None:
    """A typo in a leaf key must not be silently ignored — the loader's
    fail-open handling of unknown keys is a known defect elsewhere and is
    not repeated here."""
    with pytest.raises(ValueError, match="unknown key"):
        parse_condition([{"field": "A", "op": "eq", "vaule": 1}], "ctx")


# === Normalisation ==========================================================

def test_every_operator_has_an_exact_negation() -> None:
    """De Morgan is what lets one grammar serve a CAML target with no
    group-level NOT: negation is pushed to the leaves and each operator
    flips. An operator added without an inverse would silently break
    none_of, so the involution is asserted rather than assumed."""
    for op, negated in NEGATION.items():
        assert NEGATION[negated] == op, f"{op}/{negated} is not an involution"


def test_none_of_admits_the_empty_case() -> None:
    """SharePoint comparisons are three-valued: CAML's Neq does not match an
    empty column, so a bare flip would make "none of the items where A is 1"
    exclude items with no A at all — the opposite of the plain reading, and
    a disagreement with the expression target, where a blank coerces in."""
    condition = parse_condition({"none_of": [{"field": "A", "op": "eq", "value": 1}]}, "ctx")
    assert normalise(condition) == Group(
        "all_of", (Group("any_of", (Leaf("A", "is_null"), Leaf("A", "neq", 1))),),
    )


def test_nested_negation_flips_group_kind() -> None:
    """not(any_of[X, Y]) is all_of[not X, not Y]."""
    condition = parse_condition(
        {
            "none_of": [
                {
                    "any_of": [
                        {"field": "A", "op": "eq", "value": 1},
                        {"field": "B", "op": "gt", "value": 2},
                    ],
                },
            ],
        },
        "ctx",
    )
    assert normalise(condition) == Group(
        "all_of",
        (
            Group(
                "all_of",
                (
                    Group("any_of", (Leaf("A", "is_null"), Leaf("A", "neq", 1))),
                    Group("any_of", (Leaf("B", "is_null"), Leaf("B", "leq", 2))),
                ),
            ),
        ),
    )


def test_double_negation_restores_the_original() -> None:
    """none_of[none_of[A]] is A. A normaliser that does not round-trip here
    is flipping something it should not."""
    condition = parse_condition(
        {"none_of": [{"none_of": [{"field": "A", "op": "eq", "value": 1}]}]}, "ctx",
    )
    assert normalise(condition) == Group("all_of", (Group("any_of", (Leaf("A", "eq", 1),)),))


def _kinds(node: Condition) -> list[str]:
    if isinstance(node, Group):
        return [node.kind, *[k for child in node.children for k in _kinds(child)]]
    return []


def test_normalise_leaves_no_none_of() -> None:
    """The renderers' contract: they never meet a negated group, which is
    why CAML — which cannot express one — is a viable target."""
    condition = parse_condition(
        {
            "any_of": [
                {"none_of": [{"field": "A", "op": "is_null"}]},
                {"field": "B", "op": "eq", "value": 1},
            ],
        },
        "ctx",
    )
    assert "none_of" not in _kinds(normalise(condition))


def test_normalise_preserves_operand_transforms() -> None:
    condition = parse_condition(
        {"none_of": [{"field": "Owner", "property": "title", "op": "eq", "value": "x"}]}, "ctx",
    )
    normalised = normalise(condition)
    assert isinstance(normalised, Group)
    admitted = normalised.children[0]
    assert isinstance(admitted, Group)
    # Both arms keep the accessor: a null test on a person column must test
    # the same sub-property the comparison reads.
    arms = [leaf for leaf in admitted.children if isinstance(leaf, Leaf)]
    assert [(leaf.op, leaf.property) for leaf in arms] == [
        ("is_null", "title"), ("neq", "title"),
    ]


def test_measure_tree_counts_depth_and_leaves() -> None:
    condition = parse_condition(
        {
            "any_of": [
                {"field": "A", "op": "eq", "value": 1},
                {
                    "all_of": [
                        {"field": "B", "op": "eq", "value": 2},
                        {"field": "C", "op": "eq", "value": 3},
                    ],
                },
            ],
        },
        "ctx",
    )
    assert measure_tree(condition) == (2, 3)


# === Rendering ==============================================================
# Every expectation below is a live-verified fact from the form_visibility
# spec, not a stylistic preference. Changing one means SharePoint rejected
# something, not that the renderer got tidier.

TYPES = {
    "Status": "nvarchar", "Count": "number", "Owner": "person",
    "Note": "nvarchar", "Parent": "int", "Due": "date", "Flag": "boolean",
}


def test_expression_uses_single_quotes_and_doubles_apostrophes() -> None:
    """Verified live: expression literals are single-quoted, and an
    apostrophe is escaped by doubling."""
    condition = parse_condition([{"field": "Status", "op": "eq", "value": "O'Brien"}], "ctx")
    assert to_expression(condition, TYPES) == "[$Status] == 'O''Brien'"


def test_expression_uses_operators_not_functions() -> None:
    """Verified live: the conditional-formula dialog REJECTS and()/or().
    This assertion is the guard against someone 'tidying' it back."""
    condition = parse_condition(
        {
            "any_of": [
                {"field": "Status", "op": "eq", "value": "x"},
                {"field": "Count", "op": "gt", "value": 5},
            ],
        },
        "ctx",
    )
    rendered = to_expression(condition, TYPES)
    assert rendered == "([$Status] == 'x' || [$Count] > 5)"
    assert "or(" not in rendered
    assert "and(" not in rendered


def test_expression_renders_null_as_empty_string_comparison() -> None:
    condition = parse_condition([{"field": "Note", "op": "is_null"}], "ctx")
    assert to_expression(condition, TYPES) == "[$Note] == ''"


def test_validation_uses_double_quotes_and_functions() -> None:
    """Verified live: validation literals are DOUBLE-quoted — single quotes
    are rejected outright, the exact reverse of the expression target."""
    condition = parse_condition(
        {
            "all_of": [
                {"field": "Status", "op": "neq", "value": "forbidden"},
                {"field": "Note", "op": "is_not_null"},
            ],
        },
        "ctx",
    )
    assert to_validation(condition, TYPES) == 'AND([Status]<>"forbidden",NOT(ISBLANK([Note])))'


def test_person_property_renders_the_accessor() -> None:
    condition = parse_condition(
        [{"field": "Owner", "property": "title", "op": "neq", "value": ""}], "ctx",
    )
    assert to_expression(condition, TYPES) == "[$Owner.title] != ''"


def test_caml_matches_the_previous_hand_rolled_fold() -> None:
    """The migration's acceptance criterion: identical output to the
    left-associative fold this replaces."""
    condition = parse_condition(
        [
            {"field": "Status", "op": "eq", "value": "Open"},
            {"field": "Count", "op": "gt", "value": 5},
        ],
        "ctx",
    )
    assert to_caml(condition, TYPES) == (
        '<And><Eq><FieldRef Name="Status"/><Value Type="Text">Open</Value></Eq>'
        '<Gt><FieldRef Name="Count"/><Value Type="Number">5</Value></Gt></And>'
    )


def test_caml_renders_or() -> None:
    """The capability views gain from this change."""
    condition = parse_condition(
        {
            "any_of": [
                {"field": "Status", "op": "eq", "value": "A"},
                {"field": "Status", "op": "eq", "value": "B"},
            ],
        },
        "ctx",
    )
    assert to_caml(condition, TYPES).startswith("<Or>")


def test_in_expands_per_target() -> None:
    condition = parse_condition(
        [{"field": "Status", "op": "in", "value": ["A", "B"]}], "ctx",
    )
    assert to_expression(condition, TYPES) == "([$Status] == 'A' || [$Status] == 'B')"
    assert to_validation(condition, TYPES) == 'OR([Status]="A",[Status]="B")'


def test_measure_length_has_no_caml_rendering() -> None:
    """CAML has no LEN. The failure must name the target rather than emit
    something that cannot work."""
    condition = parse_condition(
        [{"field": "Note", "measure": "length", "op": "gt", "value": 3}], "ctx",
    )
    assert to_validation(condition, TYPES) == "LEN([Note])>3"
    with pytest.raises(ValueError, match="caml"):
        to_caml(condition, TYPES)


def test_today_sentinel_is_rejected_by_the_expression_target() -> None:
    """CAML and validation have a today; the client-side equivalent is
    @now with datetime rather than date semantics and was never verified."""
    condition = parse_condition([{"field": "Due", "op": "lt", "value": "today"}], "ctx")
    assert "<Today/>" in to_caml(condition, TYPES)
    assert to_validation(condition, TYPES) == "[Due]<TODAY()"
    with pytest.raises(ValueError, match="expression"):
        to_expression(condition, TYPES)


def test_operators_pending_probe_are_disabled_for_the_expression_target() -> None:
    """Plausible from documentation, never run against a tenant. This
    project has twice been wrong about unexercised expression syntax, so
    unverified is treated as unknown."""
    condition = parse_condition(
        [{"field": "Status", "op": "contains", "value": "x"}], "ctx",
    )
    assert "<Contains>" in to_caml(condition, TYPES)
    with pytest.raises(ValueError, match="not yet verified"):
        to_expression(condition, TYPES)


# === Hardening from the adversarial review ==================================

def test_negation_table_covers_every_renderable_operator() -> None:
    """The original form of this test asserted only that NEGATION is
    self-inverse — a property of the dict restated. It did not assert
    COVERAGE, so an operator added to a capability set without a negation
    passed the suite and crashed at render time with a bare KeyError."""
    renderable = set().union(*CAPABILITIES.values())
    assert renderable <= set(NEGATION), (
        f"operators with no negation: {sorted(renderable - set(NEGATION))}"
    )


def test_unknown_operator_under_none_of_is_a_named_error() -> None:
    condition = parse_condition(
        {"none_of": [{"field": "A", "op": "startswith", "value": "x"}]}, "c",
    )
    with pytest.raises(ValueError, match="cannot negate unknown operator"):
        normalise(condition)


def test_length_measure_is_refused_by_the_expression_target() -> None:
    """list formatting's length() counts ARRAY items and returns 1/0 for
    anything else — it does not measure a string. Rendering it would give a
    formula that is false for every value, hiding the column
    unconditionally, and saving cleanly."""
    condition = parse_condition(
        [{"field": "Note", "measure": "length", "op": "gt", "value": 3}], "c",
    )
    assert to_validation(condition, TYPES) == "LEN([Note])>3"
    for renderer in (to_caml, to_expression):
        with pytest.raises(ValueError, match="measure"):
            renderer(condition, TYPES)


def test_property_is_refused_rather_than_silently_dropped_by_caml() -> None:
    """Rendering the accessor away compares a person's display name to an
    email address — a view that returns the wrong rows with a clean build."""
    condition = parse_condition(
        [{"field": "Owner", "property": "email", "op": "eq", "value": "a@b.com"}], "c",
    )
    with pytest.raises(ValueError, match="sub-propert"):
        to_caml(condition, TYPES)


def test_empty_in_list_is_an_error_in_every_target() -> None:
    condition = parse_condition([{"field": "Status", "op": "in", "value": []}], "c")
    for renderer in (to_caml, to_expression, to_validation):
        with pytest.raises(ValueError, match="empty list"):
            renderer(condition, TYPES)


def test_today_on_a_text_column_is_the_literal_word() -> None:
    """One authored condition must not mean three different things. Gated
    on the column type, `today` on a text column is just text."""
    condition = parse_condition([{"field": "Status", "op": "eq", "value": "today"}], "c")
    assert to_validation(condition, TYPES) == '[Status]="today"'
    assert to_expression(condition, TYPES) == "[$Status] == 'today'"
    assert '<Value Type="Text">today</Value>' in to_caml(condition, TYPES)


def test_numeric_column_ignores_yaml_quoting() -> None:
    """The declared type is authoritative. Quoted '5' rendered as a string
    made '10' > '5' false — and quoting a number is the cautious thing to
    do, so it punished the careful author."""
    condition = parse_condition([{"field": "Count", "op": "gt", "value": "5"}], "c")
    assert to_expression(condition, TYPES) == "[$Count] > 5"
    assert to_validation(condition, TYPES) == "[Count]>5"


def test_non_numeric_value_on_a_numeric_column_is_an_error() -> None:
    condition = parse_condition([{"field": "Count", "op": "gt", "value": "many"}], "c")
    with pytest.raises(ValueError, match="not a number"):
        to_expression(condition, TYPES)


def test_boolean_coercion_is_two_sided() -> None:
    """A one-sided truthy test silently INVERTED the condition for anyone
    who quoted the value."""
    truthy = parse_condition([{"field": "Flag", "op": "eq", "value": "true"}], "c")
    assert to_expression(truthy, TYPES) == "[$Flag] == true"
    with pytest.raises(ValueError, match="not a boolean"):
        to_expression(
            parse_condition([{"field": "Flag", "op": "eq", "value": "maybe"}], "c"), TYPES,
        )


def test_unknown_column_type_is_an_error_not_a_text_default() -> None:
    """Defaulting an unknown column to text renders a date comparison as
    <Value Type="Text">, which SharePoint accepts and answers with the
    wrong rows."""
    condition = parse_condition([{"field": "Created", "op": "lt", "value": "today-30"}], "c")
    with pytest.raises(ValueError, match="no declared type"):
        to_caml(condition, TYPES)


def test_missing_value_is_an_error() -> None:
    condition = parse_condition([{"field": "Status", "op": "eq"}], "c")
    with pytest.raises(ValueError, match="needs a 'value'"):
        to_expression(condition, TYPES)


def test_in_expansion_counts_toward_the_leaf_bound() -> None:
    """One authored leaf renders N comparisons; counting it as one let a
    tree inside the cap render far past the length the cap protects."""
    condition = parse_condition([{"field": "Status", "op": "in", "value": ["a", "b", "c"]}], "c")
    assert measure_tree(condition) == (1, 3)


def test_validation_renders_text_operators() -> None:
    condition = parse_condition([{"field": "Note", "op": "contains", "value": "x"}], "c")
    assert to_validation(condition, TYPES) == 'ISNUMBER(FIND("x",[Note]))'
    negated = parse_condition(
        {"none_of": [{"field": "Note", "op": "begins_with", "value": "ab"}]}, "c",
    )
    assert to_validation(negated, TYPES) == (
        'OR(ISBLANK([Note]),NOT(LEFT([Note],2)="ab"))'
    )


def test_negation_agrees_across_targets_about_blanks() -> None:
    """The point of admitting the empty case: all three targets answer the
    same question. Before this, CAML excluded blank rows and the expression
    target included them, from one authored condition."""
    condition = parse_condition({"none_of": [{"field": "Count", "op": "gt", "value": 5}]}, "c")
    assert to_caml(condition, TYPES) == (
        '<Or><IsNull><FieldRef Name="Count"/></IsNull>'
        '<Leq><FieldRef Name="Count"/><Value Type="Number">5</Value></Leq></Or>'
    )
    assert to_expression(condition, TYPES) == "([$Count] == '' || [$Count] <= 5)"
    assert to_validation(condition, TYPES) == "OR(ISBLANK([Count]),[Count]<=5)"


def test_negated_measure_needs_no_null_arm() -> None:
    """LEN(blank) is 0, so the flipped comparison already matches an empty
    column — a null arm would be noise that consumes the leaf bound."""
    condition = parse_condition(
        {"none_of": [{"field": "Note", "measure": "length", "op": "gt", "value": 3}]}, "c",
    )
    assert to_validation(condition, TYPES) == "LEN([Note])<=3"


def test_negated_null_test_stays_a_single_leaf() -> None:
    condition = parse_condition({"none_of": [{"field": "Note", "op": "is_null"}]}, "c")
    assert to_validation(condition, TYPES) == "NOT(ISBLANK([Note]))"


# === Semantic validation ====================================================

RENDERED = {"Status", "Count", "Owner", "Note", "Parent", "Due", "Flag"}
LOOKUPS = {"Parent"}


def _problems(condition_raw: object, target: str = EXPRESSION) -> list[str]:
    return validate_condition(
        parse_condition(condition_raw, "when"),
        target=target, rendered=RENDERED, types=TYPES, lookups=LOOKUPS, context="when",
    )


def test_valid_condition_has_no_problems() -> None:
    assert _problems([{"field": "Status", "op": "eq", "value": "Open"}]) == []


def test_unknown_column_is_reported() -> None:
    assert "not a rendered column" in _problems([{"field": "Nope", "op": "eq", "value": 1}])[0]


def test_person_column_requires_an_accessor() -> None:
    """No defensible default exists between a person's name, email and id,
    so it is declared rather than guessed."""
    assert "needs 'property'" in _problems([{"field": "Owner", "op": "neq", "value": ""}])[0]
    bad = _problems([{"field": "Owner", "property": "nickname", "op": "neq", "value": ""}])
    assert "not a person accessor" in bad[0]


def test_lookup_column_requires_a_lookup_accessor() -> None:
    assert "needs 'property'" in _problems([{"field": "Parent", "op": "eq", "value": 1}])[0]


def test_property_on_a_plain_column_is_reported() -> None:
    bad = _problems([{"field": "Status", "property": "title", "op": "eq", "value": "x"}])
    assert "person and lookup columns only" in bad[0]


def test_measure_on_a_non_text_column_is_reported() -> None:
    bad = _problems([{"field": "Count", "measure": "length", "op": "gt", "value": 1}])
    assert "text columns only" in bad[0]


def test_every_broken_leaf_is_reported_not_just_the_first() -> None:
    """One build should name every fault. Reporting one per run turns a
    five-mistake mapping into five paste-and-wait cycles."""
    problems = _problems(
        [
            {"field": "Nope", "op": "eq", "value": 1},
            {"field": "Alsonope", "op": "eq", "value": 2},
        ],
    )
    assert len(problems) == 2


def test_capability_violations_come_from_the_renderer() -> None:
    """The renderer is the single capability oracle; a second copy of the
    rules in the validator would drift from it."""
    problems = _problems(
        [{"field": "Note", "measure": "length", "op": "gt", "value": 3}], target=EXPRESSION,
    )
    assert any("length()" in p for p in problems)
    assert _problems([{"field": "Note", "measure": "length", "op": "gt", "value": 3}],
                     target=VALIDATION) == []


def test_bounds_are_reported_with_the_actual_numbers() -> None:
    wide = [{"field": "Status", "op": "eq", "value": str(i)} for i in range(MAX_LEAVES + 1)]
    assert "the limit is" in _problems(wide)[0]


def test_system_columns_have_declared_types() -> None:
    """Views may reference these and DBML never declares them. Without a
    type, a date comparison on Created renders as Type="Text", which
    SharePoint accepts and answers with the wrong rows."""
    assert SYSTEM_COLUMN_TYPES["Created"] == "datetime"
    assert set(SYSTEM_COLUMN_TYPES) == {"ID", "Created", "Modified", "Author", "Editor"}


def test_unknown_operator_under_none_of_reports_rather_than_raises() -> None:
    """A typo in a view's operator must stay a Finding. normalise() needs a
    negation for every operator, so running it over an unknown one raised —
    turning a shipped, working surface into a traceback."""
    condition = parse_condition(
        {"none_of": [{"field": "Status", "op": "equals", "value": "x"}]}, "w",
    )
    problems = validate_condition(
        condition, target=CAML, rendered={"Status"}, types=TYPES, lookups=set(), context="w",
    )
    assert any("unknown operator" in p for p in problems)


def test_two_faults_on_one_column_are_both_reported() -> None:
    """Suppression keyed on the column name dropped the second fault."""
    condition = parse_condition(
        [
            {"field": "Owner", "op": "eq", "value": "x"},
            {"field": "Owner", "property": "nickname", "op": "eq", "value": "y"},
        ],
        "w",
    )
    problems = validate_condition(
        condition, target=EXPRESSION, rendered={"Owner"}, types=TYPES,
        lookups=set(), context="w",
    )
    assert len(problems) == 2


def test_describe_keeps_the_negation_of_a_single_child_group() -> None:
    """none_of with one child is the canonical implication idiom, and
    dropping its NOT made the manifest state the opposite of the rule."""
    condition = parse_condition(
        {"none_of": [{"field": "Status", "op": "eq", "value": "Closed"}]}, "w",
    )
    assert describe(condition) == "NOT(Status eq 'Closed')"
