# src/dbml_sharepoint/analysis/conditions.py
"""Semantic diagnosis for the shared condition grammar.

Rendering and target capability truth live in
:mod:`dbml_sharepoint.analysis.condition_rendering`. This module retains
classified Findings, source locations, operand diagnosis and deduplication.

BREAKING API MOVE (#168): import `CAML`, `EXPRESSION`, `VALIDATION`, `NEGATION`,
`CAPABILITIES`, `DISABLED_PENDING_PROBE`, `normalise`, `to_caml`,
`to_expression`, and `to_validation` from
`dbml_sharepoint.analysis.condition_rendering`. There are deliberately no
compatibility re-exports here.
"""

from collections.abc import Mapping, Sequence
from dataclasses import replace
from difflib import get_close_matches

from dbml_sharepoint.analysis import condition_rendering as _rendering
from dbml_sharepoint.analysis.findings import Finding, FindingCode, Location
from dbml_sharepoint.analysis.typemap import choice_enum_for
from dbml_sharepoint.model.conditions import VALUELESS_OPS, Condition, Group, Leaf

# Bounds keep a pathological declaration a build error rather than a formula
# truncated at whatever limit the target happens to impose.
MAX_DEPTH = 4
MAX_LEAVES = 32


def _at(parent: Location, name: str) -> Location:
    """Return `parent` with one more dotted path element."""
    return replace(parent, sub=f"{parent.sub}.{name}" if parent.sub else name)


def measure_tree(node: Condition) -> tuple[int, int]:
    """`(group depth, leaf count)` for the bounds checks.

    Counts POST-expansion: `in` with twenty values renders twenty
    comparisons, so counting the authored leaf as one would let a tree
    inside the cap render far past the formula length the cap exists to
    protect."""
    if isinstance(node, Leaf):
        if node.op in ("in", "not_in") and isinstance(node.value, list):
            return (0, max(len(node.value), 1))
        return (0, 1)
    measured = [measure_tree(child) for child in node.children]
    return (1 + max(depth for depth, _ in measured), sum(count for _, count in measured))


def condition_fields(node: Condition) -> frozenset[str]:
    """Every field referenced by a condition tree.

    Values are deliberately ignored: valueless operators such as
    ``is_null`` still carry a field, while sentinels such as ``today`` are
    operands rather than column references. The helper is shared by
    checks that need the dependency set without rendering or re-walking
    the grammar in their own way.
    """
    if isinstance(node, Leaf):
        return frozenset({node.field})
    return frozenset(field for child in node.children for field in condition_fields(child))


# === Semantic validation ====================================================
# There is no defensible default between a person's display name, their
# email and their id, so the accessor is declared rather than guessed.
PROPERTY_ACCESSORS: dict[str, frozenset[str]] = {
    "person": frozenset({"title", "email", "id"}),
    "lookup": frozenset({"lookupValue", "lookupId"}),
}
_MEASURABLE_TYPES = frozenset({"nvarchar", "longtext", "richtext", "calculated_text"})
_ME_OPS = frozenset({"eq", "neq"})

_RENDERERS = {
    _rendering.CAML: _rendering.to_caml,
    _rendering.EXPRESSION: _rendering.to_expression,
    _rendering.VALIDATION: _rendering.to_validation,
}

_RefusalKind = _rendering.ConditionRefusalKind

# The only renderer-refusal to Finding-code translation. Exhaustiveness is
# asserted against the enum so a new refusal cannot fall through generically.
_REFUSAL_FINDING_CODES: dict[
    _rendering.ConditionRefusalKind,
    FindingCode,
] = {
    _RefusalKind.COLUMN_TYPE_UNKNOWN: FindingCode.CONDITION_COLUMN_TYPE_UNKNOWN,
    _RefusalKind.DATE_IS_AN_UNQUOTED_YAML_DATETIME: (
        FindingCode.CONDITION_DATE_IS_AN_UNQUOTED_YAML_DATETIME
    ),
    _RefusalKind.DATE_UNPARSEABLE: FindingCode.CONDITION_DATE_UNPARSEABLE,
    _RefusalKind.DATE_WEARS_WHITESPACE: FindingCode.CONDITION_DATE_WEARS_WHITESPACE,
    _RefusalKind.MEASURE_UNRENDERABLE: FindingCode.CONDITION_MEASURE_UNRENDERABLE,
    _RefusalKind.ME_UNSUPPORTED_BY_TARGET: FindingCode.CONDITION_ME_UNSUPPORTED_BY_TARGET,
    _RefusalKind.NEEDLE_EMPTY: FindingCode.CONDITION_NEEDLE_EMPTY,
    _RefusalKind.NEGATIVE_TEXT_OPERATOR_UNRENDERABLE: (
        FindingCode.CONDITION_NEGATIVE_TEXT_OPERATOR_UNRENDERABLE
    ),
    _RefusalKind.NOW_ON_A_DATE_COLUMN: FindingCode.CONDITION_NOW_ON_A_DATE_COLUMN,
    _RefusalKind.NOW_UNSUPPORTED_BY_TARGET: FindingCode.CONDITION_NOW_UNSUPPORTED_BY_TARGET,
    _RefusalKind.OPERAND_TYPE_UNSUPPORTED: FindingCode.CONDITION_OPERAND_TYPE_UNSUPPORTED,
    _RefusalKind.OPERATOR_NOT_NEGATABLE: FindingCode.CONDITION_OPERATOR_NOT_NEGATABLE,
    _RefusalKind.OPERATOR_UNRENDERABLE: FindingCode.CONDITION_OPERATOR_UNRENDERABLE,
    _RefusalKind.OPERATOR_UNVERIFIED: FindingCode.CONDITION_OPERATOR_UNVERIFIED,
    _RefusalKind.PROPERTY_UNRENDERABLE: FindingCode.CONDITION_PROPERTY_UNRENDERABLE,
    _RefusalKind.SENTINEL_WITH_A_SUBSTRING_OPERATOR: (
        FindingCode.CONDITION_SENTINEL_WITH_A_SUBSTRING_OPERATOR
    ),
    _RefusalKind.SET_EMPTY: FindingCode.CONDITION_SET_EMPTY,
    _RefusalKind.SUBSTRING_TEST_ON_A_NON_TEXT_COLUMN: (
        FindingCode.CONDITION_SUBSTRING_TEST_ON_A_NON_TEXT_COLUMN
    ),
    _RefusalKind.TODAY_ON_A_DATETIME_COLUMN: FindingCode.CONDITION_TODAY_ON_A_DATETIME_COLUMN,
    _RefusalKind.TODAY_UNSUPPORTED_BY_TARGET: FindingCode.CONDITION_TODAY_UNSUPPORTED_BY_TARGET,
    _RefusalKind.VALUE_HAS_A_CONTROL_CHARACTER: FindingCode.CONDITION_VALUE_HAS_A_CONTROL_CHARACTER,
    _RefusalKind.VALUE_MISSING: FindingCode.CONDITION_VALUE_MISSING,
    _RefusalKind.VALUE_NOT_ALLOWED: FindingCode.CONDITION_VALUE_NOT_ALLOWED,
    _RefusalKind.VALUE_NOT_A_BOOLEAN: FindingCode.CONDITION_VALUE_NOT_A_BOOLEAN,
    _RefusalKind.VALUE_NOT_A_LIST: FindingCode.CONDITION_VALUE_NOT_A_LIST,
    _RefusalKind.VALUE_NOT_A_NUMBER: FindingCode.CONDITION_VALUE_NOT_A_NUMBER,
    _RefusalKind.VALUE_NOT_FINITE: FindingCode.CONDITION_VALUE_NOT_FINITE,
    _RefusalKind.MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED: (
        FindingCode.MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED
    ),
    _RefusalKind.MULTI_VALUE_MEMBERSHIP_ON_A_SINGLE_VALUE_COLUMN: (
        FindingCode.MULTI_VALUE_MEMBERSHIP_ON_A_SINGLE_VALUE_COLUMN
    ),
    _RefusalKind.MULTI_VALUE_OPERAND_UNSUPPORTED: FindingCode.MULTI_VALUE_OPERAND_UNSUPPORTED,
    _RefusalKind.MULTI_VALUE_SET_EQUALITY_UNSUPPORTED: (
        FindingCode.MULTI_VALUE_SET_EQUALITY_UNSUPPORTED
    ),
}


def leaves(node: Condition) -> list[Leaf]:
    """Every leaf of a tree, in declaration order."""
    if isinstance(node, Leaf):
        return [node]
    return [leaf for child in node.children for leaf in leaves(child)]


#: One problem before it becomes a `Finding`: its code, its prose, and the
#: leaf field it is about (`None` for the two whole-tree bounds, which are
#: not about any one leaf).
type _Problem = tuple[FindingCode, str, str | None]


def condition_findings(
    condition: Condition,
    *,
    target: str,
    rendered: set[str],
    types: dict[str, str],
    lookups: set[str],
    enum_members: Mapping[str, Sequence[str]],
    at: Location,
) -> list[Finding]:
    """Semantic problems with a declared condition, as classified Findings.

    Every one is an error: a condition that cannot be rendered has no
    degraded form to fall back to, so there is nothing to warn about.

    A leaf's finding is located one element below `at`, which is exactly
    what the message prefix has always spelled by hand.

    `enum_members` is the ordered schema projection for Choice columns.
    Whole-member operands must use the declared spelling. This is a schema
    consistency rule and makes no claim about SharePoint's comparison casing.
    """
    return [
        Finding(
            code,
            message,
            location=at if field is None else _at(at, field),
        )
        for code, message, field in _condition_problems(
            condition,
            target=target,
            rendered=rendered,
            types=types,
            lookups=lookups,
            enum_members=enum_members,
            context=at.path,
        )
    ]


def _dealias(node: Condition) -> Condition:
    """The same tree with a fresh `Leaf` object at every position.

    Structurally identical and equal by value; only object identity differs,
    which is exactly what the passes in `_condition_problems` use to mean
    "this occurrence".
    """
    if isinstance(node, Leaf):
        return replace(node)
    return Group(node.kind, tuple(_dealias(child) for child in node.children))


def _condition_problems(
    condition: Condition,
    *,
    target: str,
    rendered: set[str],
    types: dict[str, str],
    lookups: set[str],
    enum_members: Mapping[str, Sequence[str]],
    context: str,
) -> list[_Problem]:
    """The shared body. `context` renders the message prefixes; the caller
    supplies `at.path` for it when it wants locations back as well."""
    problems: list[_Problem] = []
    # EVERY LEAF A DISTINCT OBJECT, before anything below keys on one. Three
    # things here identify a leaf by `id` -- the operand suppression set, the
    # set normalisation flips, and the attribution of a normalised fault to
    # its origin -- and all three mean the leaf's OCCURRENCE in this tree.
    # `parse_condition` never shares a leaf, so a mapping file cannot tell the
    # difference; a caller building a tree in Python can, and did: one `Leaf`
    # placed both bare and under `none_of` made `_flipped_by_normalisation`
    # report the object as flipped, so the bare occurrence was skipped as
    # though it were the negated one. Validation passed and `to_caml` raised
    # on it -- a traceback where the whole point was a named finding.
    #
    # De-aliased rather than re-keyed on a path: a path would have to be
    # threaded through all three, and the only property any of them wants is
    # that two occurrences are two things. `Leaf` is frozen, so the copy is
    # equal to the original everywhere it is compared.
    condition = _dealias(condition)
    # Keyed by identity, not by field name: two leaves on one column can
    # fail for different reasons, and reporting only the first costs the
    # author another build.
    suppressed: set[int] = set()
    #: What each AUTHORED leaf has already been reported for, by `id`. The
    #: normalisation pass at the end judges the leaves that replace a given
    #: authored leaf, so an operand fault it finds there is the fault already
    #: reported for THAT leaf, worded around the other operator -- and only
    #: for that leaf.
    reported: dict[int, set[FindingCode]] = {}
    unknown_ops = {
        leaf.op for leaf in leaves(condition) if leaf.op not in _rendering.NEGATION
    }
    # Bounds are measured after normalisation, since negation expands each
    # leaf into any_of[is_null, flipped] and `in` into one leaf per value.
    # Skipped when an operator is unknown, because normalise cannot run.
    depth, leaf_count = measure_tree(
        condition if unknown_ops else _rendering.normalise(condition)
    )
    if depth > MAX_DEPTH:
        problems.append(
            (
                FindingCode.CONDITION_TOO_DEEP,
                f"{context}: nested {depth} groups deep; the limit is {MAX_DEPTH}",
                None,
            )
        )
    if leaf_count > MAX_LEAVES:
        problems.append(
            (
                FindingCode.CONDITION_TOO_MANY_LEAVES,
                (
                    f"{context}: {leaf_count} conditions after expanding any 'in' lists; "
                    f"the limit is {MAX_LEAVES}"
                ),
                None,
            )
        )

    for leaf in leaves(condition):
        where = f"{context}.{leaf.field}"
        if leaf.field not in rendered:
            problems.append(
                (
                    FindingCode.CONDITION_FIELD_NOT_RENDERED,
                    f"{where}: not a rendered column",
                    leaf.field,
                )
            )
            continue
        if leaf.op not in _rendering.NEGATION:
            problems.append(
                (
                    FindingCode.CONDITION_OPERATOR_UNKNOWN,
                    (
                        f"{where}: unknown operator {leaf.op!r}; "
                        f"known operators: {', '.join(sorted(_rendering.NEGATION))}"
                    ),
                    leaf.field,
                )
            )
            continue
        operand = _operand_problems(leaf, where, types=types, lookups=lookups)
        lookup_problem = _lookup_problem(leaf, where, target, lookups)
        if lookup_problem:
            operand.append(lookup_problem)
        if operand:
            # Rendering a leaf whose operands are already wrong would report
            # the same fault twice in different words, but only THAT leaf is
            # suppressed, so one bad operand cannot mask any other fault.
            problems.extend((code, message, leaf.field) for code, message in operand)
            suppressed.add(id(leaf))
            reported.setdefault(id(leaf), set()).update(code for code, _ in operand)

    if unknown_ops:
        # normalise() needs a negation for every operator, so it cannot run
        # over a tree containing one it does not know. The unknown operator
        # is already reported above; raising here instead would turn a typo
        # into a traceback.
        return _dedupe(problems)

    flipped = _flipped_by_normalisation(condition)
    for leaf in leaves(condition):
        if id(leaf) in suppressed or leaf.field not in rendered:
            continue
        if id(leaf) in flipped and _renders_only_inverted(leaf.op, target):
            # This leaf never reaches the renderer: `_push` flips it first, so
            # judging it standalone judges an operator that is never emitted.
            # The build refused `none_of[not_contains]` on a rule the tool had
            # just proved it could emit -- `all_of[contains]`, straight to
            # <Contains> (#20). Whatever normalisation puts in its place is
            # judged by the second pass below.
            #
            # Narrow on purpose. A blanket "skip any authored leaf
            # normalisation replaces" would also skip relational leaves under
            # `none_of`, whose faults are then reported only by that second
            # pass, in a rewritten vocabulary and under a code about the
            # negation rather than about the fault.
            continue
        rendering = _render_problems(leaf, target, types, context)
        problems.extend((code, message, leaf.field) for code, message in rendering)
        reported.setdefault(id(leaf), set()).update(code for code, _ in rendering)
        if not rendering:
            problems.extend(
                (code, message, leaf.field)
                for code, message in _choice_member_problems(
                    leaf,
                    where=f"{context}.{leaf.field}",
                    types=types,
                    enum_members=enum_members,
                )
            )

    # Second pass, over the tree the RENDERER will actually see. De Morgan
    # normalisation rewrites operators (none_of[contains] becomes
    # not_contains), so a rule can pass every check above and still be
    # unrenderable. Without this it surfaced as a ValueError out of
    # build_schema_json instead of a finding: a traceback where the author
    # needed a sentence.
    #
    # Only leaves normalisation INTRODUCED are reported here. Anything the
    # author wrote was already judged above, in their own vocabulary, and
    # repeating it under a rewritten name would read as two faults.
    #
    # By IDENTITY, not by operator name, and the difference is a hole rather
    # than a nicety. `_push` returns the authored object unchanged when it
    # does not flip a leaf and builds a new one when it does, so identity
    # answers the question exactly. Names only approximate it, and the
    # approximation failed in the direction that reports nothing: an authored
    # `contains` anywhere in the tree made this skip the `contains` that
    # normalisation had just introduced somewhere else. Paired with the
    # standalone-refusal skip above, `none_of[not_contains(Note, "")]` beside
    # any authored `contains` was judged by neither pass -- no finding, and
    # then a ConditionRefusal out of `to_caml` at generation time, which is the
    # traceback this pass exists to prevent.
    #
    # Walked PER AUTHORED LEAF rather than over
    # `condition_rendering.normalise(condition)` as a
    # whole, which is what makes the suppression below able to name an
    # origin. Per-occurrence normalisation depends only on that leaf and its
    # polarity, and `_flipped_by_normalisation` computes the same polarity
    # normaliser would, so `normalise_with_polarity` is exactly what the whole-
    # tree normalisation puts in that leaf's place -- pinned by
    # `test_per_leaf_normalisation_matches_the_whole_tree`.
    for leaf in leaves(condition):
        if leaf.field not in rendered:
            continue
        for introduced in leaves(
            _rendering.normalise_with_polarity(
                leaf,
                negated=id(leaf) in flipped,
            )
        ):
            if introduced is leaf:
                continue
            for code, problem in _render_problems(introduced, target, types, context):
                if code not in _CAPABILITY_REFUSALS:
                    # Not about the negation at all. The operand is wrong and
                    # would be wrong at either polarity, so it keeps its own
                    # code and its own words.
                    #
                    # Recoding these was saying something false.
                    # `none_of[gt(Due, "banana")]` normalises to `leq`, which
                    # condition_rendering.CAML renders perfectly well, and the
                    # appended sentence
                    # told the author the target could not express it. The
                    # fault is the date.
                    #
                    # Suppressed when THIS leaf has already been reported for
                    # this code: one operand, one fault, one finding, shown in
                    # the operator the author wrote. Keyed on the leaf and not
                    # on `(code, column)`, which folded two different leaves
                    # together -- `begins_with(Note, "")` stood in for the
                    # empty needle in `none_of[not_contains(Note, "")]` beside
                    # it, so fixing the first made the second appear on the
                    # NEXT build, reading as though the fix had caused it.
                    if code not in reported.get(id(leaf), ()):
                        problems.append((code, problem, leaf.field))
                    continue
                # Its own code, not the inner one: the author never wrote the
                # operator being named, and the remedy is different. Rewrite
                # the rule positively rather than fix the operator they chose.
                problems.append(
                    (
                        FindingCode.CONDITION_NEGATION_UNRENDERABLE,
                        (
                            f"{problem} -- negating this rule turns it into {introduced.op!r}, "
                            f"which that target cannot express. Rewrite it as a positive "
                            f"filter, or move it to a target that supports the negation."
                        ),
                        leaf.field,
                    )
                )
    return _dedupe(problems)


def _flipped_by_normalisation(node: Condition, *, negate: bool = False) -> frozenset[int]:
    """Identities of the AUTHORED leaves `normalise` inverts.

    Mirrors `_push`'s polarity bookkeeping and nothing else: a leaf under an
    odd number of `none_of` wrappers is flipped, and every other leaf reaches
    the renderer as written. Keyed by `id`, the way `_condition_problems`
    already keys its suppression set, because two leaves on one column can sit
    at different polarities.
    """
    if isinstance(node, Leaf):
        return frozenset({id(node)}) if negate else frozenset()
    child_negate = not negate if node.kind == "none_of" else negate
    return frozenset().union(
        *(_flipped_by_normalisation(child, negate=child_negate) for child in node.children)
    )


#: The refusals that are about the OPERATOR the target cannot render, as
#: opposed to the operand it was handed. Only these earn
#: `CONDITION_NEGATION_UNRENDERABLE` when normalisation introduced the leaf:
#: the sentence that code appends -- "which that target cannot express" -- is
#: a claim about capability, and appending it to an operand fault states
#: something the module itself knows to be untrue.
_CAPABILITY_REFUSALS = frozenset(
    {
        FindingCode.CONDITION_OPERATOR_UNRENDERABLE,
        FindingCode.CONDITION_NEGATIVE_TEXT_OPERATOR_UNRENDERABLE,
    }
)


def _renders_only_inverted(op: str, target: str) -> bool:
    """Whether the target refuses this operator but renders its inverse.

    The exact condition under which judging an authored leaf standalone
    contradicts what will be emitted, and it is a small set: `not_contains`
    and `not_begins_with` on condition_rendering.CAML, because `<Where>` has no
    negation of `<Contains>` or `<BeginsWith>` while both positives are elements
    it does have. Every operator in the grammar renders on the two formula
    targets, so this is False for them throughout.

    Derived from `condition_rendering.CAPABILITIES` rather than listing the two
    operators, so an operator added to the grammar that some target cannot
    render is covered the day it is added rather than the day somebody
    remembers this function.
    """
    return (
        op not in _rendering.CAPABILITIES[target]
        and _rendering.NEGATION[op] in _rendering.CAPABILITIES[target]
    )


def _operand_problems(
    leaf: Leaf,
    where: str,
    *,
    types: dict[str, str],
    lookups: set[str],
) -> list[tuple[FindingCode, str]]:
    """Every problem here is about one leaf, so the caller supplies the field
    and these carry only the code and the prose."""
    column_type = types.get(leaf.field, "")
    kind = "lookup" if leaf.field in lookups else column_type
    problems: list[tuple[FindingCode, str]] = []
    # The `me` sentinel carries its own accessor semantics: <UserID/>
    # compares the person field's user id, so an accessor is neither needed
    # nor meaningful beside it. Handled before the accessor rules rather
    # than inside them, because the exemption is the whole point. Without
    # it a person column cannot be filtered in condition_rendering.CAML at all.
    if _rendering.is_current_user_sentinel(leaf.value, column_type):
        if leaf.property:
            problems.append(
                (
                    FindingCode.CONDITION_ME_TAKES_NO_PROPERTY,
                    (
                        f"{where}: 'me' compares the person column's user id, so it takes no "
                        f"'property' -- drop {leaf.property!r}"
                    ),
                )
            )
        if leaf.op not in _ME_OPS:
            problems.append(
                (
                    FindingCode.CONDITION_ME_OPERATOR_MEANINGLESS,
                    (
                        f"{where}: 'me' is an identity, so operator {leaf.op!r} has no meaning "
                        f"against it; use one of {', '.join(sorted(_ME_OPS))}"
                    ),
                )
            )
        return problems
    # A null test needs no accessor either, and for the same reason `me`
    # needs none: emptiness is a property of the FIELD, not of a name, an
    # email or an id. All three are absent together. condition_rendering.CAML's
    # IsNull takes a
    # bare FieldRef and no Value, so there is nothing for an accessor to
    # change. Without this, "organisations with no owner" (a view
    # stakeholder-contacts' governance doc asks for by name) was
    # inexpressible: the accessor rules demanded a property and
    # condition_rendering.CAML refuses every property.
    if kind in PROPERTY_ACCESSORS and leaf.op in VALUELESS_OPS and not leaf.property:
        return problems
    if kind in PROPERTY_ACCESSORS:
        allowed = PROPERTY_ACCESSORS[kind]
        if not leaf.property:
            problems.append(
                (
                    FindingCode.CONDITION_PROPERTY_REQUIRED,
                    (
                        f"{where}: a {kind} column needs 'property' "
                        f"(one of {', '.join(sorted(allowed))})"
                    ),
                )
            )
        elif leaf.property not in allowed:
            problems.append(
                (
                    FindingCode.CONDITION_PROPERTY_UNKNOWN,
                    (
                        f"{where}: {leaf.property!r} is not a {kind} accessor; "
                        f"use one of {', '.join(sorted(allowed))}"
                    ),
                )
            )
    elif leaf.property:
        problems.append(
            (
                FindingCode.CONDITION_PROPERTY_NOT_APPLICABLE,
                f"{where}: 'property' applies to person and lookup columns only",
            )
        )
    if leaf.measure and leaf.measure != "length":
        problems.append(
            (
                FindingCode.CONDITION_MEASURE_UNKNOWN,
                f"{where}: unknown measure {leaf.measure!r}; only 'length' is supported",
            )
        )
    if leaf.measure and column_type not in _MEASURABLE_TYPES:
        problems.append(
            (
                FindingCode.CONDITION_MEASURE_NOT_APPLICABLE,
                f"{where}: 'measure: length' applies to text columns only",
            )
        )
    return problems


def _choice_member_problems(
    leaf: Leaf,
    *,
    where: str,
    types: Mapping[str, str],
    enum_members: Mapping[str, Sequence[str]],
) -> list[tuple[FindingCode, str]]:
    """Unknown whole-member Choice operands, after shape and target checks."""
    enum_name = choice_enum_for(types.get(leaf.field, ""), enum_members)
    whole_member_ops = {"eq", "neq", "in", "not_in", "includes", "not_includes"}
    if enum_name is None or leaf.op not in whole_member_ops:
        return []
    values = (
        leaf.value
        if leaf.op in {"in", "not_in"} and isinstance(leaf.value, list)
        else [leaf.value]
    )
    declared = tuple(enum_members[enum_name])
    problems: list[tuple[FindingCode, str]] = []
    # Choice columns render as text on every target. Compare the same value
    # the renderer emits, so YAML `1` matches a declared member named `"1"`.
    unique_values: list[str] = []
    for value in values:
        rendered_value = str(value)
        if rendered_value not in unique_values:
            unique_values.append(rendered_value)
    for value in unique_values:
        if value in declared:
            continue
        nearest = get_close_matches(value, declared, n=1, cutoff=0.6)
        remedy = (
            f"use declared member {nearest[0]!r}"
            if nearest
            else f"declared members: {', '.join(repr(member) for member in declared)}"
        )
        problems.append(
            (
                FindingCode.CONDITION_CHOICE_MEMBER_UNKNOWN,
                f"{where}: {value!r} is not an exact member of enum {enum_name!r}; {remedy}",
            )
        )
    return problems


def _lookup_problem(
    leaf: Leaf,
    where: str,
    target: str,
    lookups: set[str],
) -> tuple[FindingCode, str] | None:
    """Lookups are int-typed in DBML, so the type map alone cannot see them.

    A MULTI-value lookup was refused here as unmeasured until 2026-09-04, when
    `multilookup-probe.js` asked fifteen CAML predicates of one and got the
    expected rows from every one, in both operand dialects. What governs it now
    is the same machinery every other multi-value column goes through:
    `_check_arity` for the operator, `_CAML_LOOKUP_ACCESSORS` for the operand
    spelling. The accessor rules in `_operand_problems` still apply, so a
    comparison against one still has to name lookupValue or lookupId.
    """
    if leaf.field not in lookups:
        return None
    if target == _rendering.VALIDATION:
        return (
            FindingCode.CONDITION_LOOKUP_UNSUPPORTED_BY_TARGET,
            f"{where}: {leaf.field!r} is a lookup column, unsupported in validation formulas",
        )
    return None


def _render_problems(
    leaf: Leaf,
    target: str,
    types: dict[str, str],
    context: str,
) -> list[tuple[FindingCode, str]]:
    """Reuse the renderer as the capability oracle, one leaf at a time, so a
    second copy of the capability rules cannot drift from the first.

    The renderers take no context (they hang everything off
    `_CONDITIONS_ROOT`), so the prefix is rewritten to the caller's here. The
    literal below is that root's rendered path, spelled out because it is a
    `str.replace` needle rather than a path being built.

    Only `ConditionRefusal` is caught. Every refusal the renderer raises is one,
    so a plain `ValueError` reaching here is a defect rather than a finding, and
    burying it under a catch-all code would hide it.
    """
    try:
        _RENDERERS[target](leaf, types)
    except _rendering.ConditionRefusal as exc:
        code = _REFUSAL_FINDING_CODES[exc.kind]
        message = str(exc)
        if exc.path is not None:
            message = message.replace(f"{exc.path}:", f"{context}.{exc.field}:", 1)
        return [(code, message)]
    return []


def _dedupe(problems: list[_Problem]) -> list[_Problem]:
    seen: list[_Problem] = []
    messages: set[str] = set()
    for problem in problems:
        if problem[1] not in messages:
            messages.add(problem[1])
            seen.append(problem)
    return seen
