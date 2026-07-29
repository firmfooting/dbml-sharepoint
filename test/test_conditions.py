# test/test_conditions.py
"""The shared condition grammar: parse, normalise, render."""

from pathlib import Path

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
    assert normalise(condition) == Group("all_of", (Leaf("A", "neq", 1),))


def test_direct_neq_agrees_across_targets_about_blanks() -> None:
    """`neq` is the exact inverse of `eq`, so an empty value is not equal
    to a non-empty literal. CAML's bare Neq drops that row while the two
    formula targets admit it; the CAML renderer must make the null arm
    explicit rather than giving one authored condition two meanings."""
    condition = parse_condition([{"field": "Status", "op": "neq", "value": "Closed"}], "c")

    assert to_caml(condition, TYPES) == (
        '<Or><IsNull><FieldRef Name="Status"/></IsNull>'
        '<Neq><FieldRef Name="Status"/><Value Type="Text">Closed</Value></Neq></Or>'
    )
    assert to_expression(condition, TYPES) == "[$Status] != 'Closed'"
    assert to_validation(condition, TYPES) == '[Status]<>"Closed"'


def test_direct_not_in_admits_a_blank_once_in_caml() -> None:
    """A blank is outside every non-empty set. Keep one explicit null arm
    around the conjunction instead of repeating it for every member."""
    condition = parse_condition(
        [{"field": "Status", "op": "not_in", "value": ["Closed", "Deferred"]}], "c",
    )

    assert to_caml(condition, TYPES) == (
        '<Or><IsNull><FieldRef Name="Status"/></IsNull><And>'
        '<Neq><FieldRef Name="Status"/><Value Type="Text">Closed</Value></Neq>'
        '<Neq><FieldRef Name="Status"/><Value Type="Text">Deferred</Value></Neq>'
        '</And></Or>'
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
                    Leaf("A", "neq", 1),
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
    assert isinstance(admitted, Leaf)
    assert (admitted.op, admitted.property) == ("neq", "title")


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
    # A DATETIME, which `now` needs and `Due` deliberately is not.
    "OccurredAt": "datetime",
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


def test_now_renders_now_in_a_validation_formula() -> None:
    """The one target where the evidence reaches all the way to behaviour.

    test/manual/datetime-sentinel-probe.js set `=[ProbeWhen]<=NOW()` on a
    live tenant on 2026-07-29: SharePoint returned 204, read it back, and
    then REFUSED an item stamped three hours in the future. That is not a
    round-trip claim, it is the rule working.

    It also contradicts Microsoft's own formula reference, which says Lists
    and libraries do not support NOW(). True of calculated columns, where
    the value would go stale between saves; false in a validation formula,
    which is evaluated at save.
    """
    condition = parse_condition(
        [{"field": "OccurredAt", "op": "leq", "value": "now"}], "ctx",
    )
    assert to_validation(condition, TYPES) == "[OccurredAt]<=NOW()"


def test_now_is_gated_on_caml_until_a_saved_view_is_probed() -> None:
    """The CAML rendering exists, is correct as far as anything has been
    observed, and is deliberately unreachable.

    `<Today/>` with IncludeTimeValue="TRUE" was verified through `getitems`
    with an ad-hoc CamlQuery. The deploy writes a view's stored ViewQuery,
    which is a different surface: the same probe watched SharePoint rewrite
    that XML on save, and the only element ever observed inside a real saved
    view was `<Now/>` — the one that does not work.

    Distance between "observed here" and "shipped there" is exactly what
    this module refuses to paper over.
    """
    condition = parse_condition(
        [{"field": "OccurredAt", "op": "leq", "value": "now"}], "ctx",
    )
    with pytest.raises(ValueError, match="not through a saved ViewQuery"):
        to_caml(condition, TYPES)


def test_the_gated_caml_rendering_is_still_the_verified_one() -> None:
    """Guards the rendering itself while it is unreachable. A gate that
    outlives its probe would otherwise let the code beneath it rot, and the
    day someone lifts it they would ship whatever had drifted in.

    `<Now/>` is NOT it: Learn documents that element as a child of `<Value>`
    and the probe found it returns nothing — the same signature an INVENTED
    element produced, because SharePoint does not validate this position.
    """
    from dbml_sharepoint.analysis.conditions import _caml_value

    rendered = _caml_value("datetime", "now", "ctx")
    assert 'IncludeTimeValue="TRUE"' in rendered
    assert "<Today/>" in rendered
    assert "<Now/>" not in rendered, "the element Learn documents does not work"


def test_now_is_refused_on_the_expression_target() -> None:
    """@now stores and reads back intact, so it is not obviously absent —
    but whether a show/hide rule built on it FIRES is a rendering behaviour
    no probe has seen, and this target already produced one formula
    (`length()`) that stored perfectly and evaluated false for every value.
    """
    condition = parse_condition(
        [{"field": "OccurredAt", "op": "leq", "value": "now"}], "ctx",
    )
    with pytest.raises(ValueError, match="VERIFIED client-side"):
        to_expression(condition, TYPES)


def test_now_on_a_date_column_is_refused_and_names_today() -> None:
    """A DATE column has no time of day, so `now` on one is `today` written
    confusingly. Without this it would render as the literal string "now"
    inside a DateTime value — which SharePoint accepts and answers with the
    wrong rows, the failure shape this whole module exists to prevent."""
    condition = parse_condition([{"field": "Due", "op": "leq", "value": "now"}], "ctx")
    for render in (to_caml, to_validation):
        with pytest.raises(ValueError, match="use 'today'"):
            render(condition, TYPES)


def test_the_caml_gate_names_a_probe_that_asks_the_question() -> None:
    """The signpost rule, applied to the gate this file just added.

    A build error saying "confirm it with X" is worse than none when X does
    not ask — it reads as though somebody already checked. That happened
    here once already, with the expression text operators pointing at
    form-visibility-evidence-probe.js, and this keeps the new gate honest.
    """
    probe = Path(__file__).parent / "manual" / "datetime-sentinel-probe.js"
    text = probe.read_text(encoding="utf-8")
    for marker in ("C6", "C7", "ViewQuery"):
        assert marker in text, f"the named probe does not mention {marker}"


def test_now_takes_no_offset_form() -> None:
    """`today±N` has a verified rendering on both targets; `now±N` does not,
    and unverified is treated as unknown. `now+1` is therefore an ordinary
    string, and on a datetime column that is a bad date rather than a
    sentinel — so it must not silently become NOW()+1."""
    condition = parse_condition(
        [{"field": "OccurredAt", "op": "leq", "value": "now+1"}], "ctx",
    )
    assert "NOW()" not in to_validation(condition, TYPES)


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


def test_calculated_columns_are_refused_as_expression_operands() -> None:
    """Microsoft documents calculated columns as unsupported in conditional
    show/hide formulas. The formula is syntactically valid, so it saves and
    the read-back passes — a green deploy and a form that never reacts. The
    most natural rule in the shipped risk register ("show Treatment only
    when the calculated RiskRating is High") was exactly this."""
    types = {**TYPES, "Score": "calculated_number", "Band": "calculated_text",
             "Reviewed": "calculated_date"}
    for field in ("Score", "Band", "Reviewed"):
        condition = parse_condition([{"field": field, "op": "is_not_null"}], "w")
        with pytest.raises(ValueError, match="calculated"):
            to_expression(condition, types)


def test_calculated_operands_are_still_fine_in_caml() -> None:
    """A view CAN filter on a calculated column; only the two formula
    targets cannot. The rejection must not spread to CAML."""
    types = {**TYPES, "Score": "calculated_number"}
    condition = parse_condition([{"field": "Score", "op": "gt", "value": 3}], "w")
    assert "Score" in to_caml(condition, types)


def test_a_negation_that_normalisation_breaks_is_a_finding_not_a_crash() -> None:
    """Regression: the capability check ran only over the leaves the author
    wrote. De Morgan normalisation rewrites none_of[contains] to
    not_contains, which CAML cannot render, so the rule passed validation
    and then raised ValueError out of build_schema_json — a traceback where
    the author needed a sentence."""
    condition = parse_condition(
        {"none_of": [{"field": "Status", "op": "contains", "value": "x"}]}, "w",
    )
    problems = validate_condition(
        condition, target=CAML, rendered={"Status"},
        types={"Status": "nvarchar"}, lookups=set(), context="views[X].where",
    )
    assert problems, "a rule CAML cannot render must be reported, not raised"
    assert "not_contains" in problems[0]
    # The message must explain WHY an operator the author never typed appears.
    assert "negating this rule" in problems[0]


def test_an_authored_operator_is_not_re_reported_under_a_rewritten_name() -> None:
    """The second pass reports only what normalisation introduced. A rule the
    author wrote was already judged in their own vocabulary above."""
    condition = parse_condition([{"field": "Status", "op": "contains", "value": "x"}], "w")
    problems = validate_condition(
        condition, target=CAML, rendered={"Status"},
        types={"Status": "nvarchar"}, lookups=set(), context="views[X].where",
    )
    assert problems == [], f"a plain supported operator must be clean: {problems}"


def test_a_lookup_value_accessor_compares_as_text() -> None:
    """Regression: a lookup is int-typed in DBML, so typing the literal by the
    COLUMN rejected every real title as 'not a number' and left lookupId the
    only usable accessor."""
    condition = parse_condition(
        [{"field": "Project", "property": "lookupValue", "op": "eq", "value": "Alpha"}], "w",
    )
    assert to_expression(condition, {"Project": "int"}) == "[$Project.lookupValue] == 'Alpha'"
    numeric = parse_condition(
        [{"field": "Project", "property": "lookupId", "op": "eq", "value": 7}], "w",
    )
    assert to_expression(numeric, {"Project": "int"}) == "[$Project.lookupId] == 7"


def test_condition_accessors_must_be_strings() -> None:
    with pytest.raises(ValueError, match=r"property.*string"):
        parse_condition(
            {"field": "Project", "property": ["lookupValue"], "op": "eq", "value": "Alpha"},
            "w",
        )


@pytest.mark.parametrize("value", [[True], {"answer": True}])
def test_boolean_container_operands_are_configuration_errors(value: object) -> None:
    condition = parse_condition({"field": "Active", "op": "eq", "value": value}, "w")
    with pytest.raises(ValueError, match="not a boolean"):
        to_validation(condition, {"Active": "boolean"})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "NaN", "Infinity"])
def test_non_finite_numeric_operands_are_rejected(value: object) -> None:
    condition = parse_condition({"field": "Score", "op": "eq", "value": value}, "w")
    with pytest.raises(ValueError, match="finite number"):
        to_caml(condition, {"Score": "number"})


def test_negating_negative_operators_does_not_admit_nulls() -> None:
    neq = parse_condition(
        {"none_of": [{"field": "Status", "op": "neq", "value": "Closed"}]}, "w",
    )
    not_in = parse_condition(
        {"none_of": [{"field": "Status", "op": "not_in", "value": ["A", "B"]}]}, "w",
    )
    assert "IsNull" not in to_caml(neq, {"Status": "nvarchar"})
    assert "IsNull" not in to_caml(not_in, {"Status": "nvarchar"})
    assert to_validation(neq, {"Status": "nvarchar"}) == '[Status]="Closed"'
    assert to_validation(not_in, {"Status": "nvarchar"}) == 'OR([Status]="A",[Status]="B")'


# --- The `me` sentinel ------------------------------------------------------
#
# A person column could not appear in a view filter at all before this: the
# operand rules require an accessor (no defensible default between a name,
# an email and an id) and CAML refuses every accessor. `me` resolves the
# deadlock rather than working around it — <UserID/> compares the person
# field's user id natively, which IS the missing accessor, supplied by the
# sentinel instead of declared.


def test_me_renders_the_current_user_on_a_person_column() -> None:
    """'My requests', 'My trips' and 'My function's queue' are published in
    three templates' recommended views and have never been buildable."""
    condition = parse_condition([{"field": "Owner", "op": "eq", "value": "me"}], "c")
    assert to_caml(condition, TYPES) == (
        '<Eq><FieldRef Name="Owner"/><Value Type="Integer"><UserID/></Value></Eq>'
    )


def test_me_needs_no_accessor_and_refuses_one() -> None:
    """The sentinel IS the accessor. `property: email` beside it would ask
    to compare an email address against a user id."""
    assert _problems([{"field": "Owner", "op": "eq", "value": "me"}], CAML) == []
    bad = _problems(
        [{"field": "Owner", "property": "email", "op": "eq", "value": "me"}], CAML,
    )
    assert any("'me'" in problem for problem in bad), bad


def test_me_on_a_text_column_is_the_literal_word() -> None:
    """Same rule `today` follows: a sentinel means itself only on the column
    type it belongs to. On text it is someone literally called 'me'."""
    condition = parse_condition([{"field": "Status", "op": "eq", "value": "me"}], "c")
    assert '<Value Type="Text">me</Value>' in to_caml(condition, TYPES)


def test_me_is_refused_for_conditional_visibility() -> None:
    """A show/hide formula is evaluated against the item's field values and
    has no verified current-user equivalent. It would save, read back equal,
    pass the phase and never fire — the failure this whole grammar exists to
    make impossible."""
    condition = parse_condition([{"field": "Owner", "op": "eq", "value": "me"}], "c")
    with pytest.raises(ValueError, match="'me'"):
        to_expression(condition, TYPES)


def test_me_is_refused_in_validation_formulas() -> None:
    """Person operands are already refused there outright; asserted so the
    sentinel cannot later be routed around that gate."""
    condition = parse_condition([{"field": "Owner", "op": "eq", "value": "me"}], "c")
    with pytest.raises(ValueError, match="person"):
        to_validation(condition, TYPES)


def test_me_supports_only_equality() -> None:
    """<UserID/> is an identity, so ordering and substring comparisons
    against it are meaningless rather than merely unsupported."""
    bad = _problems([{"field": "Owner", "op": "contains", "value": "me"}], CAML)
    assert any("'me'" in problem for problem in bad), bad


def test_a_hyperlink_operand_in_a_validation_formula_is_refused() -> None:
    """Settled on a live tenant, 2026-07-29. SharePoint refuses the
    ValidationFormula outright: HTTP 500, "One or more column references
    are not allowed, because the columns are defined as a data type that is
    not supported in formulas."

    The formula never even stores, so questions about which half of a URL
    column a formula would compare have no subject. See
    test/manual/hyperlink-validation-operand-probe.js.
    """
    condition = parse_condition([{"field": "Doc", "op": "is_not_null"}], "c")
    with pytest.raises(ValueError, match="hyperlink"):
        to_validation(condition, {"Doc": "hyperlink"})


def test_a_hyperlink_operand_is_fine_in_a_view_filter() -> None:
    """The refusal is scoped to validation formulas. CAML comparisons on a
    URL column are ordinary text comparisons and are not in question."""
    condition = parse_condition([{"field": "Doc", "op": "is_not_null"}], "c")
    assert to_caml(condition, {"Doc": "hyperlink"}) == (
        '<IsNotNull><FieldRef Name="Doc"/></IsNotNull>'
    )


def test_a_person_column_may_be_null_tested_without_an_accessor() -> None:
    """Emptiness is a property of the FIELD, not of a name, an email or an
    id — all three are absent together, so there is nothing for an accessor
    to choose between. CAML's IsNull takes a bare FieldRef and no Value.

    Without this, "organisations with no owner" — which
    stakeholder-contacts' governance document asks for by name — was
    inexpressible: the accessor rules demanded a property and CAML refuses
    every property.
    """
    assert _problems([{"field": "Owner", "op": "is_null"}], CAML) == []
    condition = parse_condition([{"field": "Owner", "op": "is_null"}], "c")
    assert to_caml(condition, TYPES) == '<IsNull><FieldRef Name="Owner"/></IsNull>'


def test_a_lookup_column_may_be_null_tested_without_an_accessor() -> None:
    """Same argument, same mechanism — an absent lookup has neither a value
    nor an id."""
    assert _problems([{"field": "Parent", "op": "is_not_null"}], CAML) == []


def test_a_person_null_test_still_refuses_an_accessor() -> None:
    """The exemption is for the ACCESSOR being unnecessary, not for CAML
    having gained the ability to reach sub-properties."""
    condition = parse_condition(
        [{"field": "Owner", "property": "email", "op": "is_null"}], "c",
    )
    with pytest.raises(ValueError, match="sub-propert"):
        to_caml(condition, TYPES)


def test_a_person_comparison_still_needs_an_accessor() -> None:
    """Unchanged: only the null tests are exempt."""
    assert "needs 'property'" in _problems([{"field": "Owner", "op": "neq", "value": ""}])[0]
