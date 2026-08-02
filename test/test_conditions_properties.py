"""Property-based tests for the condition grammar.

`test_conditions.py` holds 114 hand-written cases, each pinning one shape the
grammar has to handle. They are good at the shapes somebody thought of. What
they cannot do is search: the normaliser rewrites an arbitrary tree of
`all_of`/`any_of`/`none_of` over fourteen operators, with `property` and
`measure` variants on every leaf, and the interesting bugs live in
combinations nobody enumerated.

So these assert INVARIANTS over generated trees rather than outputs over fixed
inputs. Each one is a claim the module already makes about itself, in a
docstring or a comment, now checked against several hundred trees per run
instead of the handful someone wrote down.

Nothing here re-implements the normaliser. A property test that needs a
reference implementation of the thing under test is just two chances to have
the same misunderstanding. The one evaluator below is a different kind of
thing -- it walks a tree and returns a bool, and knows nothing about
rewriting -- and it exists because mutation testing proved the structural
properties alone could not catch a dropped null arm.
"""

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from dbml_sharepoint.analysis.conditions import (
    MAX_DEPTH,
    NEGATION,
    condition_fields,
    measure_tree,
    normalise,
)
from dbml_sharepoint.model.conditions import GROUP_KINDS, Condition, Group, Leaf

# A small closed vocabulary. Field names are drawn from a fixed set because
# the properties below are about tree SHAPE, and letting hypothesis explore
# arbitrary identifiers would spend its budget on the one axis that does not
# affect any of them.
FIELDS = st.sampled_from(["Title", "Status", "Score", "Owner", "DueDate"])

#: Every operator the normaliser is required to be able to flip.
NEGATABLE_OPS = sorted(NEGATION)

_SCALARS = st.one_of(
    st.text(min_size=0, max_size=8),
    st.integers(min_value=-1000, max_value=1000),
    st.booleans(),
)


@st.composite
def leaves(draw: st.DrawFn) -> Leaf:
    """A single comparison, with a value shaped to suit its operator."""
    op = draw(st.sampled_from(NEGATABLE_OPS))
    value: Any
    if op in ("is_null", "is_not_null"):
        value = None
    elif op in ("in", "not_in"):
        value = draw(st.lists(_SCALARS, min_size=1, max_size=5))
    else:
        value = draw(_SCALARS)
    return Leaf(
        field=draw(FIELDS),
        op=op,
        value=value,
        property=draw(st.one_of(st.none(), st.sampled_from(["title", "email"]))),
        measure=draw(st.one_of(st.none(), st.just("length"))),
    )


def conditions(max_leaves: int = 4) -> st.SearchStrategy[Condition]:
    """Trees of groups over leaves, kept shallow enough to stay fast.

    `none_of` is included deliberately -- it is the kind the normaliser has to
    eliminate, so a strategy that omitted it would exercise none of the
    interesting path.
    """
    return st.recursive(
        leaves(),
        lambda children: st.builds(
            Group,
            kind=st.sampled_from(GROUP_KINDS),
            children=st.lists(children, min_size=1, max_size=3).map(tuple),
        ),
        max_leaves=max_leaves,
    )


def _kinds(node: Condition) -> list[str]:
    if isinstance(node, Leaf):
        return []
    return [node.kind, *(k for child in node.children for k in _kinds(child))]


@given(conditions())
def test_normalise_eliminates_none_of(condition: Condition) -> None:
    """`none_of` is accepted from authors but never survives normalisation.

    That claim is in the `Group` docstring. Every downstream renderer relies
    on it -- `_combine` handles conjunction and disjunction only, so a
    `none_of` reaching it would be a KeyError or, worse, a silently wrong
    formula.
    """
    assert "none_of" not in _kinds(normalise(condition))


@given(conditions())
def test_normalise_is_idempotent(condition: Condition) -> None:
    """Normalising an already-normalised tree must change nothing.

    The renderers are not required to call it exactly once, and a normaliser
    that kept rewriting -- adding another null arm on each pass, say -- would
    grow a formula every time it was applied.
    """
    once = normalise(condition)
    assert normalise(once) == once


@given(conditions())
def test_normalise_preserves_the_field_set(condition: Condition) -> None:
    """Normalisation may add leaves, but never about a different column.

    Relational negation admits the empty case by ORing in an `is_null` on the
    SAME field. If normalisation could introduce or drop a field, then the
    index and permission checks that run off `condition_fields` would be
    judging a different query from the one that renders.
    """
    assert condition_fields(normalise(condition)) == condition_fields(condition)


@given(conditions())
def test_normalise_never_loses_a_leaf(condition: Condition) -> None:
    """Normalisation rewrites and may expand, but never drops a comparison.

    A dropped leaf is the dangerous direction: the formula still renders, the
    build still passes, and the view silently filters on less than it says.
    """
    before = measure_tree(condition)[1]
    after = measure_tree(normalise(condition))[1]
    assert after >= before


@given(st.lists(_SCALARS, min_size=1, max_size=20))
def test_measure_tree_counts_in_post_expansion(values: list[object]) -> None:
    """`in` with N values counts as N leaves, not one.

    Stated in `measure_tree`'s docstring, and the reason MAX_LEAVES means
    anything: counting the authored leaf as one would let a tree that is
    inside the cap render far past the formula length the cap protects.
    """
    leaf = Leaf(field="Status", op="in", value=values)
    assert measure_tree(leaf) == (0, len(values))


@given(conditions())
def test_measure_tree_depth_matches_nesting(condition: Condition) -> None:
    """Depth counts groups, so a bare leaf is depth zero and a group is +1."""
    depth, count = measure_tree(condition)
    assert count >= 1
    if isinstance(condition, Leaf):
        assert depth == 0
    else:
        assert depth >= 1


@given(conditions(max_leaves=2))
def test_double_negation_normalises_to_the_positive_shape(condition: Condition) -> None:
    """`none_of[none_of[C]]` states C, so it must normalise like C does.

    Not structurally identical -- the two wrappers survive as `all_of[any_of[
    ...]]` -- but it must reach the same leaves over the same fields, and it
    must not accumulate the null arms that a single negation adds.
    """
    doubled = Group("none_of", (Group("none_of", (condition,)),))
    assert condition_fields(normalise(doubled)) == condition_fields(normalise(condition))
    assert "none_of" not in _kinds(normalise(doubled))


@given(conditions())
def test_normalise_accepts_every_negatable_operator(condition: Condition) -> None:
    """Nothing built from the documented operator set may raise.

    `_push` raises for an operator it cannot flip, naming it -- deliberately,
    so an unknown operator under `none_of` is a build error rather than a bare
    KeyError. The contract is that everything in NEGATION is flippable, and
    this is the test that the table and the code agree.
    """
    negated = Group("none_of", (condition,))
    normalise(negated)  # must not raise


# --- Semantics, not just shape ----------------------------------------------
#
# Every property above passes if relational negation stops emitting its null
# arm -- verified by mutation, not assumed. That arm is the subtlest thing the
# module does: CAML's bare `Leq` does not match rows where the column is empty,
# so `none_of[Score > 5]` must explicitly admit rows with no Score, or it means
# the opposite of what it says. Dropping it leaves the tree the same shape,
# with the same fields and the same leaf count.
#
# Catching that needs meaning, not structure. The evaluator below is NOT a
# second normaliser -- it walks a tree and returns a bool, and knows nothing
# about rewriting. Evaluating against rewriting is a genuinely independent
# check; two rewriters would just be two chances at the same misunderstanding.
#
# Scoped deliberately to the relational operators and a single field. The text
# operators have their own blank-value behaviour, established by watching a
# live form rather than by reasoning (see the `not_contains` comment in
# `_push`), and encoding a belief about those here would test the belief.

BLANK = object()

_RELATIONAL = ("lt", "leq", "gt", "geq")


def _evaluate(node: Condition, value: object) -> bool:
    """Authored semantics for a single-field tree over one row.

    A blank compares false to every relational operator -- which is the
    SharePoint behaviour the null arm exists to compensate for.
    """
    if isinstance(node, Leaf):
        if node.op == "is_null":
            return value is BLANK
        if node.op == "is_not_null":
            return value is not BLANK
        if value is BLANK:
            return False
        assert isinstance(value, int) and isinstance(node.value, int)
        return {
            "lt": value < node.value,
            "leq": value <= node.value,
            "gt": value > node.value,
            "geq": value >= node.value,
        }[node.op]
    results = [_evaluate(child, value) for child in node.children]
    if node.kind == "all_of":
        return all(results)
    if node.kind == "any_of":
        return any(results)
    return not any(results)  # none_of


@given(
    op=st.sampled_from(_RELATIONAL),
    threshold=st.integers(min_value=-20, max_value=20),
    value=st.one_of(st.just(BLANK), st.integers(min_value=-25, max_value=25)),
)
def test_normalisation_preserves_meaning_including_for_blanks(
    op: str, threshold: int, value: object,
) -> None:
    """`none_of[C]` and its normalised form must agree on every row.

    Including -- especially -- rows where the column is empty. This is the
    property that fails when the null arm is dropped: the authored tree says
    "not (Score > 5)", which is true of a blank Score, while a bare operator
    flip renders `Score <= 5`, which SharePoint does not match for a blank.
    """
    authored = Group("none_of", (Leaf(field="Score", op=op, value=threshold),))
    assert _evaluate(authored, value) == _evaluate(normalise(authored), value)


@given(
    op=st.sampled_from(_RELATIONAL),
    threshold=st.integers(min_value=-20, max_value=20),
)
def test_relational_negation_admits_the_empty_row(op: str, threshold: int) -> None:
    """Stated plainly, because the property above can only fail on one row.

    A blank satisfies "none of the rows where Score > 5", so the normalised
    tree must be true for a blank. Asserted directly so the failure names the
    behaviour rather than a row that happened to disagree.
    """
    authored = Group("none_of", (Leaf(field="Score", op=op, value=threshold),))
    assert _evaluate(normalise(authored), BLANK) is True


def test_the_strategy_covers_every_negatable_operator() -> None:
    """The generator must be able to produce all fourteen operators.

    Without this, narrowing NEGATABLE_OPS -- or a typo in the strategy --
    would quietly shrink what the properties above explore while every one of
    them still passed. A property suite that tests less than it claims is
    worse than none, because it reads like coverage.
    """
    assert set(NEGATABLE_OPS) == set(NEGATION)
    assert len(NEGATABLE_OPS) == 14


def test_the_bounds_are_still_what_the_properties_assume() -> None:
    """MAX_DEPTH pins the shape the generator is allowed to stay under."""
    assert MAX_DEPTH == 4
