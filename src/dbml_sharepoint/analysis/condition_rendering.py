# src/dbml_sharepoint/analysis/condition_rendering.py
"""Normalisation and rendering for the shared condition grammar.

This module is dependency-light by design. It owns target capability truth and
raises renderer-neutral refusals; diagnosis translates those refusals into
classified diagnostics in :mod:`dbml_sharepoint.analysis.conditions`.

BREAKING API MOVE (#168): import rendering constants and functions from
`dbml_sharepoint.analysis.condition_rendering`. They are not re-exported from
`dbml_sharepoint.analysis.conditions`.
"""

import datetime as dt
import math
import re
from enum import Enum, auto

from dbml_sharepoint.analysis.typemap import (
    CALCULATED_TYPES,
    DATE_TYPES,
    NOW_SENTINEL,
    NUMBER_TYPES,
    TODAY_SENTINEL,
    is_boolean,
    is_multi_value,
)
from dbml_sharepoint.model.conditions import VALUELESS_OPS, Condition, Group, Leaf


class ConditionRefusalKind(Enum):
    """Renderer-neutral identities for failures to render a condition."""

    COLUMN_TYPE_UNKNOWN = auto()
    DATE_IS_AN_UNQUOTED_YAML_DATETIME = auto()
    DATE_UNPARSEABLE = auto()
    DATE_WEARS_WHITESPACE = auto()
    MEASURE_UNRENDERABLE = auto()
    ME_UNSUPPORTED_BY_TARGET = auto()
    NEEDLE_EMPTY = auto()
    NEGATIVE_TEXT_OPERATOR_UNRENDERABLE = auto()
    NOW_ON_A_DATE_COLUMN = auto()
    NOW_UNSUPPORTED_BY_TARGET = auto()
    OPERAND_TYPE_UNSUPPORTED = auto()
    OPERATOR_NOT_NEGATABLE = auto()
    OPERATOR_UNRENDERABLE = auto()
    OPERATOR_UNVERIFIED = auto()
    PROPERTY_UNRENDERABLE = auto()
    SENTINEL_WITH_A_SUBSTRING_OPERATOR = auto()
    SET_EMPTY = auto()
    SUBSTRING_TEST_ON_A_NON_TEXT_COLUMN = auto()
    TODAY_ON_A_DATETIME_COLUMN = auto()
    TODAY_UNSUPPORTED_BY_TARGET = auto()
    VALUE_HAS_A_CONTROL_CHARACTER = auto()
    VALUE_MISSING = auto()
    VALUE_NOT_ALLOWED = auto()
    VALUE_NOT_A_BOOLEAN = auto()
    VALUE_NOT_A_LIST = auto()
    VALUE_NOT_A_NUMBER = auto()
    VALUE_NOT_FINITE = auto()
    MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED = auto()
    MULTI_VALUE_MEMBERSHIP_ON_A_SINGLE_VALUE_COLUMN = auto()
    MULTI_VALUE_OPERAND_UNSUPPORTED = auto()
    MULTI_VALUE_SET_EQUALITY_UNSUPPORTED = auto()


class ConditionRefusal(ValueError):  # noqa: N818 - public API name required by #168
    """A rendering refusal with stable identity and source coordinates."""

    def __init__(
        self,
        kind: ConditionRefusalKind,
        message: str,
        *,
        path: str | None = None,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.path = path
        self.field = field


_CONDITIONS_ROOT = "conditions"


def _at(parent: str, name: str) -> str:
    return f"{parent}.{name}"


# Every operator's exact inverse. The involution is asserted by a test: an
# operator added here without one silently breaks `none_of`, because the
# normaliser would have nothing to flip it to.
NEGATION: dict[str, str] = {
    "eq": "neq",
    "neq": "eq",
    "lt": "geq",
    "geq": "lt",
    "gt": "leq",
    "leq": "gt",
    "is_null": "is_not_null",
    "is_not_null": "is_null",
    "in": "not_in",
    "not_in": "in",
    "contains": "not_contains",
    "not_contains": "contains",
    "begins_with": "not_begins_with",
    "not_begins_with": "begins_with",
    # Membership, for a MULTI-VALUE column and only for one. `eq` is not
    # widened to mean this: see `_MEMBERSHIP_OPS`.
    "includes": "not_includes",
    "not_includes": "includes",
}

# Negative operators whose own rendering already admits the empty value, so
# `_push` must not OR a second `is_null` arm around them. `neq` and `not_in`
# define the empty value as outside the compared literal or set and say so in
# their renderers; `not_includes` is here on a MEASUREMENT rather than on the
# resemblance -- probe C9, 2026-08-10, found a bare `<Neq>` against a
# MultiChoice column returning the rows without the member AND the empty row.
_NULL_INCLUSIVE_NEGATIVES = frozenset({"neq", "not_in", "not_includes"})

_FLIP: dict[str, str] = {"all_of": "any_of", "any_of": "all_of"}


def normalise(condition: Condition) -> Condition:
    """Return an equivalent tree of `all_of`/`any_of` over positive leaves."""
    return normalise_with_polarity(condition, negated=False)


def normalise_with_polarity(condition: Condition, *, negated: bool) -> Condition:
    """Normalise one authored occurrence under its inherited negation state."""
    return _push(condition, negate=negated)


def _push(node: Condition, *, negate: bool) -> Condition:
    if isinstance(node, Leaf):
        if not negate:
            return node
        if node.op not in NEGATION:
            # Reached before the renderer's capability check, so an unknown
            # operator under none_of would otherwise surface as a bare
            # KeyError rather than a build error naming it.
            raise ConditionRefusal(
                ConditionRefusalKind.OPERATOR_NOT_NEGATABLE,
                f"cannot negate unknown operator {node.op!r} on {node.field!r}; "
                f"known operators: {', '.join(sorted(NEGATION))}",
                path=_at(_CONDITIONS_ROOT, node.field),
                field=node.field,
            )
        flipped = Leaf(node.field, NEGATION[node.op], node.value, node.property, node.measure)
        if node.op in VALUELESS_OPS or node.measure:
            # A null test is its own inverse, and a measure is never null.
            # LEN(blank) is 0, so the flipped comparison already matches.
            return flipped
        if node.op in ("not_contains", "not_begins_with"):
            # A negative text predicate is ALREADY true for a blank: indexOf
            # on an empty string is -1, which satisfies both `< 0` and
            # `!= 0`. Its negation must therefore be false there, and the
            # null arm below would OR the blank back in, making an authored
            # rule and its own negation both true for a blank value.
            #
            # That -1 was arithmetic until 2026-07-29, when it was watched:
            # row 4 of the probe's eyes-on table leaves the box EMPTY, and
            # both negative candidates were VISIBLE for it
            # (test/manual/expression-text-operators-probe.js,
            # `expression.client-validation.not-contains-indexof` and
            # `.not-begins-with-indexof`, X2 and X6 in that run).
            # The open form showed the same two columns before anything was
            # typed, so the answer was seen twice in one run.
            #
            # Same reasoning as neq/not_in, and it must stay a separate test:
            # `_TEXT_OPS` holds all four, and the `flipped.op` half of the
            # condition below would catch the POSITIVE two by their flips.
            # For those the null arm is right (`contains` is false for a
            # blank, so none_of must be true) and dropping it would change
            # output for a shape that already exists on main.
            return flipped
        if node.op in _NULL_INCLUSIVE_NEGATIVES or flipped.op in _NULL_INCLUSIVE_NEGATIVES:
            # These inverse operators define the empty value as outside the
            # compared literal/set. Their renderers already carry that
            # semantic, so adding another null arm here would only duplicate
            # it in every none_of[eq/in/includes] tree.
            return flipped
        # SharePoint comparisons are three-valued: CAML's bare Leq does NOT
        # match rows where the column is empty, so a bare operator flip would
        # make "none of the items where Count > 5" exclude items with no
        # Count at all, which is the opposite of what the words say, and
        # disagrees with the expression target, where a blank coerces and is
        # included. Relational negation therefore admits the empty case
        # explicitly; neq/not_in do so in their own renderings above.
        return Group("any_of", (Leaf(node.field, "is_null", None, node.property), flipped))

    if node.kind == "none_of":
        # none_of[C] == all_of[!C];  !none_of[C] == any_of[C].
        kind = "any_of" if negate else "all_of"
        child_negate = not negate
    else:
        kind = _FLIP[node.kind] if negate else node.kind
        child_negate = negate

    children = tuple(_push(child, negate=child_negate) for child in node.children)
    return Group(kind, children)  # type: ignore[arg-type]


# === Rendering ==============================================================
# Three targets, three syntaxes, none of them the author's problem. Every
# rule below was established by running it against a live tenant and is
# recorded in the form_visibility spec; the differences are not stylistic
# and must not be harmonised.
#
#            reference        string literal          booleans
#   caml     <FieldRef/>      typed <Value>           <And>/<Or>
#   expr     [$X]             'x', '' doubles a quote &&  /  ||
#   valid    [X]              "x" (single REJECTED)   AND(...)/OR(...)

CAML = "caml"
EXPRESSION = "expression"
VALIDATION = "validation"

# Conjoined onto a VIEW's filter so the classic filter editor refuses to open
# it, which is what stops an operator truncating the filter. See #267 and
# MAX_FILTER_EDITOR_CONDITIONS.
# Measured 2026-08-17 on `caml-chain-depth-probe.js`: the editor refuses this
# shape (`view.filter-editor.wrapper-group-left-editable`,
# `view.filter-editor.wrapper-group-right-editable` and
# `view.filter-editor.tautology-guard-editable`, W2/W4/T2 in those runs), and
# the two halves return every row when asked alone, so conjoining them removes
# nothing (`query.caml.tautology-always-true`, 41 of 41; and
# `query.caml.tautology-alone-partitions`, S2 in the view-edit-page-probe.js
# runs, which asks the same thing of a three-row fixture).
CAML_VIEW_FILTER_GUARD = (
    "<Or>"
    '<IsNotNull><FieldRef Name="ID"/></IsNotNull>'
    '<IsNull><FieldRef Name="ID"/></IsNull>'
    "</Or>"
)

_CAML_OP_TAGS: dict[str, str] = {
    "eq": "Eq",
    "neq": "Neq",
    "lt": "Lt",
    "leq": "Leq",
    "gt": "Gt",
    "geq": "Geq",
    "is_null": "IsNull",
    "is_not_null": "IsNotNull",
    "contains": "Contains",
    "begins_with": "BeginsWith",
    # NOT <Includes>/<NotIncludes>, and this is the sharpest measurement in
    # the whole feature. Learn documents those two elements for a multi-value
    # LOOKUP and documents nothing for MultiChoice; against a live MultiChoice
    # column on 2026-08-10 both returned an EMPTY SET WITH NO ERROR (probe C4,
    # C5), while the undocumented <Eq> did the membership test (C1: the two
    # rows containing the member) and <Neq> its negative (C9). A grammar that
    # emitted the documented elements would produce a view that is always
    # empty, on a build that passes and a deploy that verifies clean -- this
    # project's exact failure class. The two operators Learn documents are the
    # two that are broken, so the authored names borrow their spelling and
    # emit what was measured instead.
    #
    # ON A MULTI-VALUE LOOKUP ALL FOUR WORK, measured 2026-09-04
    # (`query.caml-adhoc.multilookup-{eq,includes}-{text,lookupid}` and the
    # four negatives): the documented elements do work on the type they are
    # documented for, and <Eq>/<Neq> answer identically there. So the mapping
    # does not have to branch on which multi-value kind the column is, which
    # matters because this module sees a declared TYPE STRING and cannot tell
    # `int[]` from `audit_event[]` in the first place. One spelling, measured
    # correct on both kinds.
    "includes": "Eq",
    "not_includes": "Neq",
}
_EXPR_OPS: dict[str, str] = {
    "eq": "==",
    "neq": "!=",
    "lt": "<",
    "leq": "<=",
    "gt": ">",
    "geq": ">=",
}
_VALIDATION_OPS: dict[str, str] = {
    "eq": "=",
    "neq": "<>",
    "lt": "<",
    "leq": "<=",
    "gt": ">",
    "geq": ">=",
}

_TEXT_OPS = frozenset({"contains", "not_contains", "begins_with", "not_begins_with"})

# Operators each target can render. A miss is a build error naming the
# target, never a formula emitted in hope.
CAPABILITIES: dict[str, frozenset[str]] = {
    # CAML has Contains/BeginsWith and no negation of either, and this is a
    # PLATFORM limit rather than a gap here, so it is cited rather than
    # probed. Microsoft's Where element documents its complete child set:
    # And, BeginsWith, Contains, DateRangesOverlap, Eq, Geq, Gt, In,
    # Includes, IsNotNull, IsNull, Leq, Lt, Membership, Neq, NotIncludes,
    # Or. There is no <Not>, no <NotContains> and no <NotBeginsWith>, and
    # <NotIncludes> negates <Includes> (a MULTI-VALUE membership test, not
    # a substring match). So "does not contain" has no CAML spelling at all,
    # by any arrangement of the elements that exist.
    # https://learn.microsoft.com/sharepoint/dev/schema/where-element-query
    CAML: frozenset(_CAML_OP_TAGS) | {"in", "not_in"},
    EXPRESSION: frozenset(_EXPR_OPS) | {"is_null", "is_not_null", "in", "not_in"} | _TEXT_OPS,
    VALIDATION: frozenset(_VALIDATION_OPS) | {"is_null", "is_not_null", "in", "not_in"} | _TEXT_OPS,
}

# Operators plausible from the documented syntax but never observed in a
# formula on a live tenant. Unverified is treated as unknown, and the probe
# that settles one is named in the error. A signpost pointing at a probe
# that does not ask reads as though somebody already checked.
#
# EMPTY, and what the emptiness means is narrower than it looks: nothing is
# waiting on a probe that has been WRITTEN AND NOT RUN. It is not a claim
# that all fourteen operators the expression target renders were watched.
# (Fourteen, not sixteen: `includes`/`not_includes` are CAML-only, and a
# multi-value column is refused on this target as an operand outright.)
#
# What was watched, on 2026-07-29 and by eye
# (test/manual/expression-text-operators-probe.js): the four TEXT operators.
# X6 was the last one carried on reasoning rather than sight, and the second
# pass added it and found it DISCRIMINATING rather than merely stored,
# hidden for a value beginning with the needle, visible for the three that
# do not, with all twenty-four cells of the table matching prediction.
#
# The other ten (eq, neq, lt, leq, gt, geq, is_null, is_not_null, in,
# not_in) predate this list and rest on the form_visibility spec's
# harvested formulas rather than on a probe of their own. That is a weaker
# footing than the text four, and it is recorded here rather than smoothed
# over, because a list whose whole worth is honesty cannot round its own
# coverage up.
#
# It stays here because storage cannot establish anything on this target.
# SharePoint does not validate ClientValidationFormula on write. A call to
# a function that does not exist is accepted and read back byte-identical
# (test/manual/expression-text-operators-probe.js,
# `expression.client-validation.control-unknown-function-refused`, X0 in
# those runs), so the only proof
# a rendering works is a person watching a column appear and disappear.
# Anything added to CAPABILITIES[EXPRESSION] without that belongs here
# first.
DISABLED_PENDING_PROBE: dict[str, frozenset[str]] = {}

# Transforms a target cannot express at all, as opposed to merely unproven.
#
# `measure: length` on the expression target is the important one, and it is
# not an omission: list formatting's `length` returns an ARRAY's item count,
# and 1 or 0 for anything else. It does not measure a string. Rendering
# `length([$Note]) > 3` would therefore be false for every possible value,
# hiding the column unconditionally, with a formula that saves cleanly. The
# documented idiom is a sentinel trick (`indexOf([$Note] + '^', '^')`), which
# is not enabled here because it has not been run against a tenant.
_UNSUPPORTED_MEASURE: dict[str, str] = {
    CAML: "CAML has no LEN",
    EXPRESSION: (
        "list formatting's length() counts array items and returns 1/0 for other "
        "types -- it does not measure a string, so the formula would be false for "
        "every value"
    ),
}
# CAML reaches a lookup's id via FieldRef LookupId, and a person's email not
# at all. Rendering the accessor away (comparing a display name to an email
# address) is a view that silently returns the wrong rows, so it is refused.
_UNSUPPORTED_PROPERTY: dict[str, str] = {
    CAML: (
        "CAML cannot reach person or lookup sub-properties. The one exception "
        "is a comparison against a MULTI-VALUE lookup, where 'lookupValue' and "
        "'lookupId' name the two operand dialects measured on 2026-09-04; a "
        "null test is not a comparison and needs no operand, since a row with "
        "no value has neither a title nor an id"
    ),
    VALIDATION: "person and lookup operands are unsupported in validation formulas",
}

# Operand types a target refuses outright. SharePoint validation formulas
# cannot read a person, a multi-line column or a calculated column, and
# reject the rule at save, so the build refuses first.
#
# Conditional show/hide is worse, and that is why it is listed here too:
# Microsoft documents calculated columns as unsupported, but the formula
# stays SYNTACTICALLY valid, so it saves, the read-back compares equal and
# the phase passes. The failure is invisible from the deploy side
# entirely (a green build, a green manifest, and a form that never
# reacts). The most natural rule in the shipped risk register ("show
# Treatment only when the calculated RiskRating is High or Extreme") is
# exactly this shape.
#
# The same Learn page lists Currency, Location, Managed Metadata and the
# multi-select Person/Choice/Lookup variants as unsupported. Currency,
# Location and Managed Metadata still have no DBML type in this tool, so
# there is still nothing here to reject for them. The multi-select variants
# DO now (`enum_name[]`), and they are refused just below, by arity rather
# than by a type name this dict could hold. Time-of-day comparisons on Date
# and Time are likewise unreachable: `today` is already refused for this
# target (the client-side equivalent is @now, with datetime rather than
# date semantics).
# https://learn.microsoft.com/sharepoint/dev/declarative-customization/list-form-conditional-show-hide
_CALCULATED_OPERAND = dict.fromkeys(CALCULATED_TYPES, "a calculated column")
_FORBIDDEN_OPERAND_TYPES: dict[str, dict[str, str]] = {
    VALIDATION: {
        "person": "a person column",
        "richtext": "a multi-line column",
        "longtext": "a multi-line column",
        # Settled by probe on 2026-07-29, having first shipped here as
        # merely UNVERIFIED. SharePoint refuses the ValidationFormula
        # outright (HTTP 500, "One or more column references are not
        # allowed, because the columns are defined as a data type that is
        # not supported in formulas"), so this is a closed question, not an
        # open one, and it belongs with the other cannots.
        #
        # Worth recording that this is a LOUD failure, not the silent one
        # first assumed: a template carrying such a rule fails at the
        # validation phase of the paste, in front of the operator. The
        # build-time refusal is still the right place for it, because it
        # turns a failed deploy into a failed build.
        # See test/manual/hyperlink-validation-operand-probe.js.
        "hyperlink": "a hyperlink column, which SharePoint refuses in a validation formula",
        **_CALCULATED_OPERAND,
    },
    EXPRESSION: dict(_CALCULATED_OPERAND),
}

# The same question asked by ARITY, because the dict above cannot hold the
# answer. Its keys are DBML type names and a multi-value type is spelled
# `<enum>[]`, which would have to be minted per enum per schema -- so a
# membership test against it reads as though it covers the new type and
# silently does not.
#
# CAML IS DELIBERATELY ABSENT, and that is the measured half of this. A view
# filter over a multi-value column works: two probe runs on 2026-08-10 showed
# `<Eq>` against a single member returning the rows that contain it, `<Neq>`
# returning the rows that do not plus the empty ones, and the predicate
# surviving being stored as a view's ViewQuery. Adding CAML here would refuse
# a filter SharePoint demonstrably serves. Measured again on 2026-09-04 over a
# multi-value LOOKUP, in both operand dialects, with the same answers.
#
# The two that ARE here refuse for different evidence, and each says which:
# VALIDATION was measured, EXPRESSION is documented.
_MULTI_VALUE_OPERAND_REFUSALS: dict[str, str] = {
    # Measured 2026-08-10 on a live tenant: setting ValidationFormula against
    # a MultiChoice column was refused with HTTP 500 and "This field type does
    # not support validation formulas." Loud rather than silent, which is the
    # good outcome -- but the build still refuses first, so a failed deploy
    # part-way through a paste becomes a failed build.
    VALIDATION: (
        'SharePoint refuses a validation formula that reads one -- "This '
        'field type does not support validation formulas"'
    ),
    # Documented rather than probed, and this is the target where a wrong
    # answer is worst: the formula stays SYNTACTICALLY valid, so it saves,
    # reads back byte-identical and passes the deploy phase, leaving a green
    # build and a form that never reacts. Microsoft lists "Choice with
    # multiple selections" among the column types conditional show/hide
    # cannot read.
    EXPRESSION: (
        'conditional show/hide cannot read one -- Microsoft lists "Choice '
        'with multiple selections" among the unsupported column types, and '
        "the formula would still save and still never react"
    ),
}

# The authored spelling of membership, and the whole answer to the design
# question a multi-value column asks: what should `eq` mean against a set?
#
# It means MEMBERSHIP to SharePoint. Measured 2026-08-10 on a live tenant over
# three runs, against the fixture R1 {View} R2 {View,Edit} R3 {Edit,Export}
# R4 {}: `<Eq>` "View" returned R1 and R2 -- the rows CONTAINING the member,
# not the row whose whole set is {View}.
#
# The tempting move is to let the authored `eq` carry that, since the renderer
# would emit the same XML either way. It is refused, and the reason is not
# tidiness. `eq` would then mean equality on a scalar column and membership on
# a multi-value one, separated only by a `[]` in a DBML file the mapping does
# not show -- so a reader of `{field: Events, op: eq, value: View}` could not
# tell which question was being asked, and adding `[]` to a column's type would
# silently change the meaning of every filter already written against it, on a
# green build. This module already refuses that trade once: PROPERTY_ACCESSORS
# exists because "there is no defensible default between a person's display
# name, their email and their id, so the accessor is DECLARED rather than
# guessed". Same shape, same answer.
#
# So membership is its own operator, it is legal only where it was measured,
# and `eq` on a multi-value column is a named build error pointing at it.
_MEMBERSHIP_OPS = frozenset({"includes", "not_includes"})

# What a multi-value column can be asked, per target. A miss is refused by
# name; a target absent from this table can be asked NOTHING, which is the
# fails-closed direction -- the formula targets refuse the operand outright
# just above, and any target added later starts from nothing rather than from
# the scalar vocabulary.
#
# Only these four were measured, and each was measured directly:
#   includes      -> <Eq>          C1: R1 + R2, and C8 survives a stored view
#   not_includes  -> <Or><IsNull><Neq></Or>
#                                  C9: R3 + R4 (a bare Neq ALREADY admits the
#                                  empty row here, unlike single-value CAML),
#                                  C6: R4, so the union is R3 + R4 either way
#   is_null       -> <IsNull>      C6: R4
#   is_not_null   -> <IsNotNull>   C7: R1 + R2 + R3
#
# What is deliberately absent, and why refusing is not a rule stronger than
# the platform:
#   * `contains` WORKS -- C3 returned R1 and R2. It is refused because that
#     result cannot distinguish membership from a substring match over the
#     delimited form, the two readings disagree for a needle that is a prefix
#     of a member, and no probe has sent one. Every case C3 observed is
#     `includes`, so nothing measured becomes inexpressible.
#   * `in`/`not_in` would be "intersects" rather than "is one of" -- the same
#     arity-overloading trap as `eq`, one level up. `any_of`/`all_of` over
#     `includes` says it in the author's own vocabulary. MEASURED on
#     2026-09-04 (`query.caml-adhoc.multilookup-in-text`, `-in-lookupid`):
#     <In> over two members returned every row holding EITHER, so the reading
#     that was refused as ambiguous is the one SharePoint has. It stays
#     refused -- the reason was never that <In> might not work, it was that
#     one authored word would mean "is one of" on a scalar and "intersects"
#     on a set. `any_of[includes, includes]` emits <Or> and returns the same
#     rows (`-or-membership`), so nothing measured is inexpressible.
#   * the ordering operators and `begins_with` were never asked, and a set has
#     no order.
#
# THE SAME FOUR WERE MEASURED ON A MULTI-VALUE LOOKUP on 2026-09-04, over an
# analogue fixture (L1 {Alpha} L2 {Alpha,Bravo} L3 {Bravo,Charlie} L4 {}), in
# both operand dialects and row for row against the Choice run:
#   includes      -> <Eq>          L1 + L2, in text and in id
#   not_includes  -> <Or><IsNull><Neq></Or>
#                                  L3 + L4 from the composed form
#                                  (`-neq-isnull-wrapper`), and L3 from the
#                                  bare negative. Unlike MultiChoice the
#                                  wrapper is doing work here rather than being
#                                  uniform for its own sake: see `_leaf`.
#   is_null       -> <IsNull>      L4
#   is_not_null   -> <IsNotNull>   L1 + L2 + L3
# `contains` was not asked of a lookup at all, so its refusal above needs no
# revisiting on that side either.
_MULTI_VALUE_OPERATORS: dict[str, frozenset[str]] = {
    CAML: _MEMBERSHIP_OPS | VALUELESS_OPS,
}

# THE TWO OPERAND DIALECTS a multi-value lookup answers in, and the deadlock
# they break. A lookup carries no defensible default operand -- the item's
# title and the item's id are different values -- so `PROPERTY_ACCESSORS`
# makes the author name one. CAML then refused every accessor
# (`_UNSUPPORTED_PROPERTY`), which left a lookup filterable only by a null
# test. That refusal was honest while nothing had been measured; on
# 2026-09-04 both dialects were, over a multi-value lookup, and they returned
# the same rows for every one of the fifteen predicates:
#
#   lookupValue -> <FieldRef Name="X"/>
#                  <Value Type="Lookup">Alpha</Value>
#   lookupId    -> <FieldRef Name="X" LookupId="TRUE"/>
#                  <Value Type="Integer">3</Value>
#
# Type="Lookup" and Type="Integer" are what was measured. Neither is what
# `_ACCESSOR_TYPES` would have produced (Text and Number), which is why this
# table exists rather than a mapping onto the scalar types -- emitting an
# operand spelling nobody sent is how a filter comes back with the wrong rows
# and no error.
#
# SINGLE-VALUE LOOKUPS ARE NOT INCLUDED, and the asymmetry is evidence rather
# than principle: the probe asked its predicates of a multi-value column, and
# a single-value lookup appeared in that run only as the index control. The
# spellings would very likely work there too, and "very likely" is what this
# file does not emit.
_CAML_LOOKUP_ACCESSORS: dict[str, str] = {
    "lookupValue": "Lookup",
    "lookupId": "Integer",
}

# SharePoint's own separator between the members of a set on the wire.
# Measured C2: `<Eq>` against "View;#Edit" matched the row whose set is exactly
# {View, Edit} -- so the SAME operator answers a second, different question,
# and the only thing distinguishing them is whether the value happens to
# contain these two characters. That is undetectable when reading a mapping,
# so the delimited form is refused rather than offered.
#
# Nor is it given an operator of its own, and the reason is what was NOT
# measured. C2 sent `View;#Edit` and got back the row holding exactly that
# set. Nobody sent `Edit;#View`, so whether SharePoint compares the delimited
# string literally or normalises the set first is unknown -- and those two
# behaviours differ for every author who lists the members in a different
# order from the one the field happens to store.
#
# It would be easy to write "the comparison is against a string, so it is
# order-sensitive" here. That is an inference from the shape of the request,
# not a thing anyone watched happen, and this file is the wrong place to start
# guessing about SharePoint. Exact-set equality is therefore not offered,
# because it is not characterised -- not because it is known to be broken. The
# probe would need one more query to settle it.
_SET_DELIMITER = ";#"

_NUMBER_TYPES = NUMBER_TYPES  # one home: analysis/typemap.py
_DATE_TYPES = DATE_TYPES  # same home, same reason
# `now` is for the columns that carry a time of day. A DATE column has no
# time to compare, so `now` on one is `today` written confusingly, and the
# semantic check below says so rather than rendering it.
_DATETIME_TYPES = frozenset({"datetime"})
_TODAY = TODAY_SENTINEL  # one home: analysis/typemap.py
_NOW = NOW_SENTINEL  # same home, same reason
# Only to make the error helpful: `now+1` is refused like any other bad date
# literal, but silently, it would read as a typo rather than as the one
# offset form this grammar deliberately does not have.
_NOW_OFFSET = re.compile(r"^now[+-]\d+$")

# `datetime.fromisoformat` is far wider than the grammar this tool emits: it
# takes ANY single character as the date/time separator (`2026-07-29x14:30`),
# plus basic format (`20260729`) and ISO week dates (`2026-W01-1`). The
# literal is emitted UNCHANGED, so without this a one-character typo reaches
# the wire wearing the guard's approval and the view answers emptily. The
# shape is pinned here; the parse that follows only settles whether the
# numbers are real, which a regex cannot say.
_ISO_DATE_LITERAL = re.compile(
    r"^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}(:\d{2}(\.\d+)?)?(Z|[+-]\d{2}:\d{2})?)?\Z",
)

# The current-instant sentinel. Every rendering below was established by
# test/manual/datetime-sentinel-probe.js on 2026-07-29, against a live
# tenant, and two of the three answers contradict a Microsoft document.
#
# MEASURED 2026-09-02 (analysis/save_rules.py has the run): TODAY() and
# NOW() in a validation formula run 16 to 20 hours behind the site, so a
# validation comparison against `today` or `now` renders against [Modified]
# (`_save_instant_leaf`), bare `today` on a datetime column is refused, and
# only the offset form `TODAY()+N` on a datetime still reaches
# `_validation_literal`. For the record: the 2026-07-29 probe set
# `=[ProbeWhen]<=NOW()`, SharePoint returned 204 and enforced it, which
# contradicts the formula reference's "Lists and libraries do not support
# the RAND and NOW functions". That sentence holds for calculated columns.
#
#   CAML -> <Today/> with IncludeTimeValue="TRUE", NOT <Now/>
#       Learn documents <Now/> as a child of <Value> beside <Today/>. It
#       does not work in a comparison, and the decisive evidence is an A/B
#       rather than an absence: two views were built over the SAME list, at
#       the same moment, each with columns, differing only in that element.
#       The <Today/>+IncludeTimeValue view listed two rows in the browser;
#       the <Now/> view listed none. A negative control had already shown
#       SharePoint silently accepts an INVENTED element in that position
#       and returns nothing, which is the signature <Now/> matches.
#
#       IncludeTimeValue makes the comparison an INSTANT, not midnight: a
#       row stamped three hours earlier matched `Lt`, which a midnight
#       comparison would have excluded, and the row stamped three hours
#       later did not.
#
#       The two-row result is itself diagnostic. Plain <Today/> with no
#       IncludeTimeValue returns ONE row on the same data (yesterday only),
#       so two rows can only mean the attribute is active and the
#       comparison really is running against the instant.
#
#       Verified where it SHIPS, not merely where it was convenient to ask.
#       datetime-sentinel-probe.js's `query.caml-adhoc.*` rows used an ad-hoc
#       CamlQuery; the deploy writes a view's stored ViewQuery, and SharePoint
#       rewrites that XML on save. So query.view-query.today-include-time-
#       roundtrip read the stored query back (the attribute survived) and
#       query.view-query.today-include-time-selects re-ran THAT XML and got
#       the same two rows, confirmed a third time by eye, in the view itself.
#
#       CORROBORATED BY SHAREPOINT'S OWN UI, from a direction the probe
#       cannot reach. Opening the <Now/> view's filter panel shows an EMPTY
#       value. The UI cannot represent that element, and a date comparison
#       against nothing matches nothing, which is the zero-row result.
#       Typing the UI's own token spelling, [Now], into that panel is
#       refused outright: "Filter value is not in a supported date format."
#       [Today] and [Me] are accepted there; [Now] is not a token SharePoint
#       has. Microsoft's product contradicts Microsoft's documentation, and
#       the product wins.
#
#   EXPRESSION -> refused, exactly as `today` is.
#       @now stores and reads back intact, so it is not obviously absent.
#       Whether a show/hide rule built on it FIRES is a rendering
#       behaviour no headless probe can see, and this surface has already
#       produced one formula (length()) that stored perfectly and evaluated
#       false for every value.
# The current-user sentinel. A person column could not be filtered at all
# before this: the operand rules demand an accessor because there is no
# defensible default between a name, an email and an id, and CAML refuses
# every accessor it might be given. `me` resolves that deadlock rather than
# side-stepping it. CAML's <UserID/> compares the person field's user id
# natively, so the sentinel SUPPLIES the missing accessor instead of
# declaring one, which is why it takes no `property` and refuses one.
_ME = "me"
_PERSON_TYPES = frozenset({"person"})

# Column types a substring test cannot mean anything on. A DENYLIST, not a
# whitelist, because a Choice column's declared type IS its enum name. A
# whitelist would have to know every enum in every schema, and would refuse
# `contains` on a choice, which is the one non-text case that does make
# sense.
#
# What it stops: the renderers type the needle by the COLUMN, so
# `contains` on a boolean emitted `indexOf([$Flag], true)` (a substring
# search for an unquoted boolean) and on a number `indexOf([$Count], 5)`.
# Neither is a shape any probe has sent: the text-operator probe built its
# subject as `<Field Type="Text"/>` and every one of its six candidates
# used a quoted string needle.
_NON_TEXT_FOR_SUBSTRING = frozenset(
    {
        "boolean",
        "int",
        "number",
        "date",
        "datetime",
        "person",
        "calculated_number",
        "calculated_date",
    }
)
# True == 1 and False == 0 in Python, so the bare ints cover the bools.
_TRUTHY = frozenset({1, "1", "true", "True", "TRUE", "yes", "Yes", "YES"})
_FALSY = frozenset({0, "0", "false", "False", "FALSE", "no", "No", "NO"})


def _reject(
    kind: ConditionRefusalKind,
    target: str,
    reason: str,
    path: str,
) -> ConditionRefusal:
    return ConditionRefusal(
        kind,
        f"{path}: {reason} (target: {target})",
        path=path,
        field=path.rsplit(".", 1)[-1],
    )


#: Characters XML 1.0 forbids outright. Tab, LF and CR are legal and omitted.
#: Same expression as `test_probes.CONTROL_CHARS`, which guards probe SOURCES;
#: this guards a value arriving from a mapping and reaching a rendered formula.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def _caml_lookup_accessor(leaf: Leaf, declared_type: str, target: str) -> str | None:
    """The CAML operand dialect this leaf names, or None for every other leaf.

    ARITY DECIDES, so this cannot live in the accessor rules themselves: only
    a MULTI-VALUE lookup's dialects were measured (see
    `_CAML_LOOKUP_ACCESSORS`), and a valueless operator has no operand to put
    in one. A `None` here means the ordinary CAML property refusal applies,
    which is the fails-closed direction.

    Like every other rule in this module it reads a declared TYPE, so it
    cannot tell an `int[]` lookup from an `<enum>[]` Choice. It does not have
    to: `conditions.py` refuses an accessor on a column that is not a person
    or a lookup before anything is rendered, and it holds the ref set that
    settles which this is.
    """
    if target != CAML or leaf.op in VALUELESS_OPS or leaf.measure:
        return None
    if not is_multi_value(declared_type):
        return None
    return leaf.property if leaf.property in _CAML_LOOKUP_ACCESSORS else None


def _check(leaf: Leaf, target: str, at: str, accessor: str | None = None) -> None:
    if isinstance(leaf.value, str) and (bad := _CONTROL_CHARS.search(leaf.value)):
        # XML 1.0 forbids these, so a CAML <Value> containing one is not a
        # formula SharePoint can parse -- and `_xml_escape` handles &, < and >
        # only, so nothing downstream removes it. Found by the property suite
        # (test_conditions_properties), which generated \x1f into a filter
        # value and got malformed XML back.
        #
        # This repository has already paid for this exact class once: a NUL
        # byte reached generated deploy.js and was invisible to ruff, mypy,
        # j2lint, the golden comparison and the whole suite -- only git saw it,
        # as "Bin N -> M bytes". Refusing here is the fails-closed answer;
        # stripping silently would change the author's declared filter.
        raise _reject(
            ConditionRefusalKind.VALUE_HAS_A_CONTROL_CHARACTER,
            target,
            f"value for {leaf.field!r} contains control character "
            f"{hex(ord(bad.group()))}, which XML forbids and no escaping can "
            f"carry; remove it from the declared value",
            at,
        )
    if leaf.op in DISABLED_PENDING_PROBE.get(target, frozenset()):
        raise _reject(
            ConditionRefusalKind.OPERATOR_UNVERIFIED,
            target,
            f"operator {leaf.op!r} is not yet verified against a live tenant for this "
            f"target; confirm it with test/manual/expression-text-operators-probe.js "
            f"and enable it deliberately",
            at,
        )
    if leaf.op in ("not_contains", "not_begins_with") and target == CAML:
        # The generic message below names an operator the author may never
        # have written: `none_of[contains]` normalises to `not_contains`
        # before it reaches here, so "operator 'not_contains' has no
        # rendering" reads as a tool defect. It is a platform one, it is
        # permanent, and the two targets where the same condition DOES render
        # are worth naming rather than leaving the author to discover.
        #
        # Both sources are named, because this cannot tell them apart and
        # naming only one was backwards for the other. The last sentence is
        # not padding: `none_of[not_contains]` is the shape that WAS refused
        # here (#20) and now builds, so an author who reads this message on a
        # neighbouring rule must not conclude their working one is doomed.
        positive = NEGATION[leaf.op]
        raise _reject(
            ConditionRefusalKind.NEGATIVE_TEXT_OPERATOR_UNRENDERABLE,
            target,
            f"a view filter cannot say {leaf.op!r}. CAML has <Contains> and "
            f"<BeginsWith> and no negation of either -- its <Where> element has "
            f"no <Not>, and <NotIncludes> negates <Includes>, which is a "
            f"multi-value membership test rather than a substring match. This "
            f"is a SharePoint limit, not one this tool can lift. You either "
            f"wrote {leaf.op!r} directly or wrote none_of[{positive}], which "
            f"normalises to it; none_of[{leaf.op}] is NOT this case and does "
            f"render, since it normalises back to {positive!r}. The same "
            f"condition renders on column_validation/list_validation and on "
            f"form_visibility; for a view, filter the other way round, or "
            f"precompute the test into a column and filter on that",
            at,
        )
    if leaf.op not in CAPABILITIES[target]:
        raise _reject(
            ConditionRefusalKind.OPERATOR_UNRENDERABLE,
            target,
            f"operator {leaf.op!r} has no rendering",
            at,
        )
    if leaf.measure and target in _UNSUPPORTED_MEASURE:
        raise _reject(
            ConditionRefusalKind.MEASURE_UNRENDERABLE,
            target,
            f"'measure' cannot be rendered: {_UNSUPPORTED_MEASURE[target]}",
            at,
        )
    if leaf.property and target in _UNSUPPORTED_PROPERTY and accessor is None:
        raise _reject(
            ConditionRefusalKind.PROPERTY_UNRENDERABLE,
            target,
            _UNSUPPORTED_PROPERTY[target],
            at,
        )
    if leaf.op not in VALUELESS_OPS and leaf.value is None:
        raise _reject(
            ConditionRefusalKind.VALUE_MISSING,
            target,
            f"operator {leaf.op!r} needs a 'value'",
            at,
        )
    if leaf.op in VALUELESS_OPS and leaf.value is not None:
        raise _reject(
            ConditionRefusalKind.VALUE_NOT_ALLOWED,
            target,
            f"operator {leaf.op!r} takes no 'value'",
            at,
        )
    if leaf.op in ("in", "not_in") and not isinstance(leaf.value, list):
        raise _reject(
            ConditionRefusalKind.VALUE_NOT_A_LIST,
            target,
            f"operator {leaf.op!r} needs a list 'value'",
            at,
        )
    if leaf.op in _TEXT_OPS and leaf.value == "":
        # Meaningless before it is wrong: `contains(x, '')` is true of every
        # possible value and `not_contains(x, '')` false of every one, so no
        # authored rule wants this.
        #
        # It also broke `none_of`. indexOf('', '') is 0, so `contains` is
        # TRUE for a blank field and its negation must be FALSE, but the
        # null arm `_push` adds for the positive text operators ORs the
        # blank back in, and the rule and its negation both came out true.
        # Refusing costs nothing and needs no claim about how SharePoint
        # compares an empty needle; special-casing the normaliser would
        # need one.
        raise _reject(
            ConditionRefusalKind.NEEDLE_EMPTY,
            target,
            f"operator {leaf.op!r} needs a non-empty 'value' -- an empty needle "
            f"matches every value on the positive operators and none on the "
            f"negative ones, so the condition cannot discriminate. Use "
            f"'is_null'/'is_not_null' to test for a blank column",
            at,
        )
    if leaf.op in _MEMBERSHIP_OPS and leaf.value == "":
        # Same code as the text operators above, deliberately different
        # reasoning, and the difference is the whole point. An empty needle
        # matches EVERY value under `contains`; measured on a live tenant on
        # 2026-08-17 by multi-value-probe.js
        # `query.caml-adhoc.multichoice-eq-empty-value` (once C13), CAML <Eq>
        # against an empty value on a MultiChoice matches NONE. So this one is
        # not merely undiscriminating, it renders a view that is empty forever,
        # builds clean and deploys clean. `_TEXT_OPS` does not cover
        # `includes`, so nothing refused this until that row said what the
        # empty case does.
        raise _reject(
            ConditionRefusalKind.NEEDLE_EMPTY,
            target,
            f"operator {leaf.op!r} needs a member name. Measured on 2026-08-17: "
            f"CAML renders this as <Eq> against an empty value, which matches NO "
            f"rows at all on a multi-value column, so this would build, deploy "
            f"and show an empty view forever. Name a member, or use "
            f"'is_null'/'is_not_null' to test for a blank column",
            at,
        )
    if leaf.op in ("in", "not_in") and not leaf.value:
        raise _reject(
            ConditionRefusalKind.SET_EMPTY,
            target,
            f"operator {leaf.op!r} has an empty list, which is a constant -- say what "
            f"you mean with a condition rather than an empty set",
            at,
        )


def _xml_escape(text: str, extra: dict[str, str] | None = None) -> str:
    out = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    for char, entity in (extra or {}).items():
        out = out.replace(char, entity)
    return out


def _is_today(value: object, column_type: str) -> bool:
    """A `today` sentinel only means a date on a DATE column. On a text
    column it is the literal word, and reading it as TODAY() would give one
    authored condition three different meanings across the three targets."""
    return column_type in _DATE_TYPES and isinstance(value, str) and bool(_TODAY.match(value))


def _is_now(value: object, column_type: str) -> bool:
    """A `now` sentinel only means the current instant on a DATETIME column.

    Narrower than `_is_today`, which accepts every date-ish type: a DATE
    column has no time of day, so comparing one to the instant is `today`
    spelled confusingly. `_reject_meaningless_now` turns that into a build
    error naming the alternative rather than letting it render.
    """
    return column_type in _DATETIME_TYPES and isinstance(value, str) and bool(_NOW.match(value))


def _looks_like_a_date(value: object) -> bool:
    """`YYYY-MM-DD`, optionally with a `T` time and an offset. This is the
    grammar the renderers emit, and the only literal form a date column may
    carry once the sentinels have had their turn.

    Deliberately strict, and strict in the direction of emitting less. What
    SharePoint does with an unparseable DateTime operand has not been probed
    (it might refuse the view, or take it and filter on something nobody
    intended), and a filter that quietly matches the wrong rows is invisible
    from the build and from the deploy alike. Refusing here needs no answer
    to that question.

    A bare `datetime.date` passes: PyYAML resolves an unquoted `2026-07-29`
    to one before this module sees it, and `str()` on a date is the ISO
    literal exactly. A `datetime.datetime` does NOT (`str()` spells the
    separator as a space, which no probe has run), and it is rejected by
    `_check_date_literal` with its own message rather than here.

    Surrounding whitespace is NOT tolerated, and the absence of a `.strip()`
    here is the point. Every renderer emits `str(value)` unchanged, so a
    value this function trimmed in order to parse would validate as one
    string and reach SharePoint as another, approving a spelling no probe
    has run, which is the exact hole the guard exists to close. The
    sentinels have always been strict this way; matching them leaves one
    whitespace policy rather than two.
    """
    if isinstance(value, dt.datetime):
        return False
    if isinstance(value, dt.date):
        return True
    if not isinstance(value, str):
        return False
    if not _ISO_DATE_LITERAL.match(value):
        return False
    text = value.replace("Z", "+00:00")
    for parse in (dt.datetime.fromisoformat, dt.date.fromisoformat):
        try:
            parse(text)
        except ValueError:
            continue
        return True
    return False


def _reject_meaningless_now(
    value: object,
    column_type: str,
    field: str,
    target: str,
    where: str,
) -> None:
    """`now` on a DATE column would silently render as the literal string
    "now" inside a DateTime value, which SharePoint accepts and answers with
    the wrong rows. Caught here, named, and pointed at `today`.

    A function rather than an inline guard because it has to run from two
    places. `in` recurses through `_leaf` per member and so met it; CAML
    renders `not_in` by looping the members itself, and that loop called only
    `_check_date_literal`, for which `now` on a non-datetime column is merely
    an unparseable literal. Both spellings refused, so nothing wrong was ever
    emitted -- but only one of the two messages named `today`, which is the
    fix (#21).
    """
    if (
        isinstance(value, str)
        and _NOW.match(value)
        and column_type in _DATE_TYPES
        and column_type not in _DATETIME_TYPES
    ):
        raise _reject(
            ConditionRefusalKind.NOW_ON_A_DATE_COLUMN,
            target,
            f"the 'now' sentinel needs a datetime column; {field!r} is "
            f"{column_type!r}, which has no time of day -- use 'today'",
            where,
        )


def _reject_sentinel_with_a_substring_operator(
    value: object,
    column_type: str,
    op: str,
    target: str,
    where: str,
) -> None:
    """A sentinel is a POINT IN TIME. Comparison, ordering and set membership
    mean something against one; a substring test does not. What the renderers
    emit for the combination -- verified by running them, not by reasoning:

        contains + now  ->  ISNUMBER(FIND(NOW(),[OccurredAt]))
        begins_with     ->  LEFT([OccurredAt],3)=NOW()

    That 3 is len('now'): the sentinel's SPELLING reaching the formula as a
    character count. It is measuring the word, not the date, and that is
    decidable here without knowing anything about how SharePoint would treat
    either formula -- which nobody does, since no probe has ever sent one.
    Refusing needs no such answer.

    Called from `_leaf` ahead of the non-text-column guard, and that ordering
    is the whole reason this is a function. It lived inside
    `_check_date_literal` until 2026-08-10 and could not fire from there:
    every sentinel column type is a date type, every date type is in
    `_NON_TEXT_FOR_SUBSTRING`, and that guard ran first -- so a rule with a
    row in the published catalogue was unreachable by any input (#140). The
    generic message it lost to is true and says less.

    It does NOT disturb the ordering `_leaf`'s own comment records. That one
    is about type RESOLUTION -- the real declared type before the measure
    substitution -- and this guard reads `declared_type` and runs before the
    substitution too.
    """
    if op in _TEXT_OPS and (_is_today(value, column_type) or _is_now(value, column_type)):
        raise _reject(
            ConditionRefusalKind.SENTINEL_WITH_A_SUBSTRING_OPERATOR,
            target,
            f"{value!r} is a point in time and {op!r} is a substring test, so "
            f"the two cannot be combined -- the sentinel would reach the formula "
            f"as its own spelling rather than as a date. Use a comparison "
            f"(eq/neq/lt/leq/gt/geq) or a set test (in/not_in)",
            where,
        )


def _check_date_literal(
    value: object,
    column_type: str,
    target: str,
    where: str,
) -> None:
    """A date column's literal, once `today` and `now` have had their turn,
    must be a real date. Nothing downstream checks it, and no probe has
    asked what SharePoint does with an unparseable one, so the failure is
    UNBOUNDED rather than known: it may refuse the view, or accept it and
    filter on something nobody intended. The build is the only place that
    can be settled without a tenant, so it is settled here.

    `now+1` is the case that matters most. `today+/-N` works, which makes the
    offset form the obvious thing to reach for, and without this it is an
    unparseable literal in a filter that silently matches nothing.

    Called per SET MEMBER as well as per leaf: CAML renders `not_in` by
    looping the members itself rather than recursing through `_leaf`, so one
    bad literal among good ones used to walk straight past this.
    """
    if column_type not in _DATE_TYPES or value is None:
        return
    if _is_today(value, column_type) or _is_now(value, column_type):
        # A sentinel is not a literal, so there is nothing here to parse. The
        # one combination it cannot survive -- a substring operator -- is
        # refused by `_reject_sentinel_with_a_substring_operator`, which runs
        # earlier in `_leaf` and says why it has to.
        return
    if _looks_like_a_date(value):
        return

    # PyYAML resolves an unquoted `2026-07-29T14:30:00` to a datetime, and
    # `str()` on one spells the separator as a SPACE. Quoting it gives the
    # `T` spelling the probe ran, so say that rather than claiming the value
    # the author wrote is not a date.
    if isinstance(value, dt.datetime):
        raise _reject(
            ConditionRefusalKind.DATE_IS_AN_UNQUOTED_YAML_DATETIME,
            target,
            f"{value!r} is an unquoted YAML datetime; quote it. Unquoted, it "
            f"reaches the renderers as a datetime object whose text form "
            f"separates date from time with a SPACE, and no probe has run "
            f"that spelling -- '{value.isoformat()}' has",
            where,
        )

    # A padded date gets its own message: "is not a date" would send the
    # author hunting a typo in a value that is already correct apart from
    # the spaces. Both branches deliberately strip before MATCHING - the
    # leniency is diagnostic only, so the hint can recognise what the guard
    # above has already refused.
    if isinstance(value, str) and value != value.strip() and _looks_like_a_date(value.strip()):
        raise _reject(
            ConditionRefusalKind.DATE_WEARS_WHITESPACE,
            target,
            f"{value!r} is a date wearing surrounding whitespace. Every "
            f"renderer emits the literal UNCHANGED, so the spaces would go "
            f"out to SharePoint inside the operand; drop them. A YAML block "
            f"scalar leaves a trailing newline the same way",
            where,
        )

    hint = ""
    if isinstance(value, str) and _NOW_OFFSET.match(value.strip()):
        hint = (
            " -- 'now' takes no offset form (today+/-N does, now+/-N has no "
            "verified rendering); use a bare 'now', or 'today+/-N' for a "
            "whole-day boundary"
        )
    raise _reject(
        ConditionRefusalKind.DATE_UNPARSEABLE,
        target,
        f"{value!r} is not a date, the sentinel 'today'/'today+/-N', or "
        f"'now'. What SharePoint does with an unparseable date literal has "
        f"not been probed -- it may refuse the view or filter on something "
        f"nobody intended -- so it is refused here, where the answer does not "
        f"matter{hint}",
        where,
    )


def is_current_user_sentinel(value: object, column_type: str) -> bool:
    """A `me` sentinel only means the current user on a PERSON column. On a
    text column it is the literal word, the same rule `today` follows, and
    for the same reason: one authored condition must not mean three
    different things across the three targets."""
    return column_type in _PERSON_TYPES and value == _ME


def _number(value: object, at: str, target: str) -> str:
    """A numeric column's operand is emitted bare. The declared type is
    authoritative: a value that is not a number on a numeric column is a
    build error, not a silent string comparison where '10' < '5'.

    The two "is not a number" branches share one code deliberately: they are
    one rule reached by two type tests, and the sentences differ only to say
    which test refused.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise _reject(
            ConditionRefusalKind.VALUE_NOT_A_NUMBER,
            target,
            f"{value!r} is not a number",
            at,
        )
    try:
        numeric = float(value)
    except ValueError:
        raise _reject(
            ConditionRefusalKind.VALUE_NOT_A_NUMBER,
            target,
            f"{value!r} is not a number on a numeric column",
            at,
        ) from None
    if not math.isfinite(numeric):
        raise _reject(
            ConditionRefusalKind.VALUE_NOT_FINITE,
            target,
            f"{value!r} is not a finite number",
            at,
        )
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def _boolean(value: object, at: str, target: str) -> bool:
    """Coercion is two-sided. A one-sided test silently inverts the
    condition for the author who quotes 'true', which is the cautious
    thing to do and so exactly the author who should not be punished."""
    if not isinstance(value, (bool, int, str)):
        raise _reject(
            ConditionRefusalKind.VALUE_NOT_A_BOOLEAN,
            target,
            f"{value!r} is not a boolean",
            at,
        )
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise _reject(
        ConditionRefusalKind.VALUE_NOT_A_BOOLEAN,
        target,
        f"{value!r} is not a boolean",
        at,
    )


def to_caml(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a CAML `<Where>` body."""
    return _render(normalise(condition), column_types, CAML, _CONDITIONS_ROOT)


def to_caml_protected(condition: Condition, column_types: dict[str, str]) -> str:
    """Render a VIEW's `<Where>` body in the shape the filter editor refuses.

    A separate function rather than a `protected` flag on `to_caml`, because
    `to_caml` is an entry in `_RENDERERS` and is dispatched there as
    `(condition, types)` to decide what a target can express. A required flag
    would break that registry, and a defaulted one would let a future view
    path emit an unguarded filter with nothing to say so.

    The editor refuses a filter whose right child is a group, and a view it
    cannot open it cannot truncate (measured 2026-08-17 on
    `caml-chain-depth-probe.js`, by
    `view.filter-editor.wrapper-group-left-editable`,
    `view.filter-editor.wrapper-group-right-editable` and
    `view.filter-editor.tautology-guard-editable`).
    """
    return f"<And>{to_caml(condition, column_types)}{CAML_VIEW_FILTER_GUARD}</And>"


def caml_condition_count(condition: Condition, column_types: dict[str, str]) -> int:
    """How many comparisons the rendered CAML presents to the filter editor.

    Not the tree's leaf count. `neq` and `not_includes` each render an
    `<IsNull>` arm beside the comparison, and `not_in` renders one for the
    whole group, so six authored `neq` clauses render twelve comparisons. The
    editor shows a row per comparison, so that larger number is the one an
    author is warned about.

    Counted on the UNGUARDED form: the guard adds two comparisons of its own
    and is not something the author wrote.
    """
    return to_caml(condition, column_types).count("<FieldRef")


def to_expression(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a list-formatting predicate for `ClientValidationFormula`."""
    return _render(normalise(condition), column_types, EXPRESSION, _CONDITIONS_ROOT)


def to_validation(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a classic validation predicate for `ValidationFormula`."""
    return _render(normalise(condition), column_types, VALIDATION, _CONDITIONS_ROOT)


def _render(node: Condition, types: dict[str, str], target: str, at: str) -> str:
    if isinstance(node, Leaf):
        return _leaf(node, types, target, at)
    parts = [_render(child, types, target, at) for child in node.children]
    return _combine(parts, conjunction=node.kind == "all_of", target=target)


def _combine(parts: list[str], *, conjunction: bool, target: str) -> str:
    if len(parts) == 1:
        return parts[0]
    if target == CAML:
        # CAML's And/Or are strictly binary, so fold left.
        tag = "And" if conjunction else "Or"
        combined = parts[0]
        for nxt in parts[1:]:
            combined = f"<{tag}>{combined}{nxt}</{tag}>"
        return combined
    if target == EXPRESSION:
        # Parenthesised so precedence can never alter the declared meaning.
        return "(" + f" {'&&' if conjunction else '||'} ".join(parts) + ")"
    return f"{'AND' if conjunction else 'OR'}({','.join(parts)})"


def _column_type(field: str, types: dict[str, str], target: str, at: str) -> str:
    """The declared type drives literal rendering, so an unknown column is
    an error rather than a silent 'nvarchar'. A date column defaulting to
    text renders `<Value Type="Text">today-30</Value>`, the sentinel as a
    literal string, which is not the comparison anybody wrote, whatever
    SharePoint then does with it."""
    if field not in types:
        raise _reject(
            ConditionRefusalKind.COLUMN_TYPE_UNKNOWN,
            target,
            f"no declared type for column {field!r}",
            at,
        )
    return types[field]


def _check_arity(leaf: Leaf, declared_type: str, target: str, where: str) -> None:
    """Whether this operator means anything against a column of this ARITY.

    Both directions are guarded, and that is the point rather than symmetry
    for its own sake. Guarding only the scalar operators would leave
    `includes` rendering `<Eq>` on a single-value Choice and quietly meaning
    equality; guarding only membership would leave `eq` quietly meaning
    membership on a set. Either hole gives one authored word two meanings, and
    a mapping shows neither.
    """
    if is_multi_value(declared_type):
        allowed = _MULTI_VALUE_OPERATORS.get(target, frozenset())
        if leaf.op not in allowed:
            raise _reject(
                ConditionRefusalKind.MULTI_VALUE_CONDITION_OPERATOR_UNSUPPORTED,
                target,
                f"{leaf.field!r} holds many values, and operator {leaf.op!r} has "
                f"no verified rendering against one. Measured on a live tenant "
                f"on 2026-08-10, CAML's <Eq> against a multi-value column tests "
                f"MEMBERSHIP rather than equality, so this grammar spells that "
                f"'includes' and refuses {leaf.op!r} rather than letting one "
                f"word mean two things. Available here: "
                f"{', '.join(sorted(allowed))}; combine several with "
                f"all_of/any_of. (<Includes>/<NotIncludes>, which Microsoft "
                f"documents, returned nothing at all against a Choice and are "
                f"not emitted; against a multi-value LOOKUP they work and "
                f"return what <Eq>/<Neq> return, measured 2026-09-04.)",
                where,
            )
        if leaf.op in _MEMBERSHIP_OPS and _SET_DELIMITER in str(leaf.value):
            raise _reject(
                ConditionRefusalKind.MULTI_VALUE_SET_EQUALITY_UNSUPPORTED,
                target,
                f"{leaf.value!r} contains {_SET_DELIMITER!r}, which is how "
                f"SharePoint delimits the members of a set. Measured on "
                f"2026-08-10: <Eq> against a delimited value stops testing "
                f"membership and matches the WHOLE SET instead, so this one "
                f"leaf would silently ask a different question from the one it "
                f"reads like. Name a single member; exact-set equality is not "
                f"offered, because it is not characterised -- one member order "
                f"was measured and the other never was",
                where,
            )
    elif leaf.op in _MEMBERSHIP_OPS:
        scalar = "eq" if leaf.op == "includes" else "neq"
        raise _reject(
            ConditionRefusalKind.MULTI_VALUE_MEMBERSHIP_ON_A_SINGLE_VALUE_COLUMN,
            target,
            # The array remedy names the FORM, not this column's type.
            # `map_column` accepts `<enum>[]` and `<scalar>[]` on a ref
            # column, so the earlier
            # `{declared_type}[]` was advice a text column could not take --
            # `nvarchar[]` is refused as an unknown type, and the message whose
            # job was to end one error started the next.
            #
            # Deciding it by "is this type a known scalar" was worse than
            # useless: an enum may be NAMED like a scalar, `_resolve_column`
            # checks enum names before scalar mapping, and so `nvarchar[]` is
            # legal for a schema declaring `Enum nvarchar`. The test would have
            # withheld correct advice for exactly that case. The grammar does
            # not know the schema's enum names and threading them through every
            # renderer to phrase one sentence is not worth it -- so the sentence
            # stops claiming anything about this column and says what shape to
            # reach for.
            f"operator {leaf.op!r} tests whether a column CONTAINS a value, and "
            f"{leaf.field!r} is {declared_type!r}, which holds exactly one. Use "
            f"{scalar!r} -- or, if it really does hold many, declare it as an "
            f"array of an enum (`<enum>[]`), which is the multi-value form this "
            f"grammar can filter",
            where,
        )


def _leaf(leaf: Leaf, types: dict[str, str], target: str, at: str) -> str:
    where = _at(at, leaf.field)
    # Resolved before `_check` because the property rule it feeds runs there,
    # and read with `.get` because an unknown column is `_column_type`'s
    # refusal to make, two lines below. A missing type is not multi-value, so
    # an unknown column with an accessor keeps refusing on the accessor,
    # exactly as it did before this dialect existed.
    accessor = _caml_lookup_accessor(leaf, types.get(leaf.field, ""), target)
    _check(leaf, target, where, accessor)
    # Gate on the REAL column type first. Substituting "number" for a
    # measure ahead of this check lets LEN([MultiLine]) past a rule that
    # is_not_null on the same column hits, the tool contradicting itself,
    # and routing the author to whichever spelling the guard misses.
    declared_type = _column_type(leaf.field, types, target, where)
    # Ahead of the type guard below, and deliberately: both refuse a substring
    # test against `today`/`now`, and this one says which of the two facts is
    # the author's problem. The type guard subsumed it entirely until
    # 2026-08-10, leaving a rule with a published catalogue row that nothing
    # could reach -- see the helper.
    _reject_sentinel_with_a_substring_operator(
        leaf.value,
        declared_type,
        leaf.op,
        target,
        where,
    )
    if leaf.op in _TEXT_OPS and declared_type in _NON_TEXT_FOR_SUBSTRING:
        raise _reject(
            ConditionRefusalKind.SUBSTRING_TEST_ON_A_NON_TEXT_COLUMN,
            target,
            f"operator {leaf.op!r} is a substring test and {leaf.field!r} is "
            f"{declared_type!r}, so the needle would be typed as {declared_type!r} "
            f"and searched for inside a value that is not text. Compare it instead "
            f"(eq/neq/lt/leq/gt/geq), or test a text column",
            where,
        )
    if is_multi_value(declared_type) and target in _MULTI_VALUE_OPERAND_REFUSALS:
        raise _reject(
            ConditionRefusalKind.MULTI_VALUE_OPERAND_UNSUPPORTED,
            target,
            f"{leaf.field!r} holds many values, and "
            f"{_MULTI_VALUE_OPERAND_REFUSALS[target]}. Test a scalar column "
            f"instead, or filter a view on this one -- a view filter over a "
            f"multi-value column is the one target that works",
            where,
        )
    _check_arity(leaf, declared_type, target, where)
    forbidden = _FORBIDDEN_OPERAND_TYPES.get(target, {})
    if declared_type in forbidden:
        raise _reject(
            ConditionRefusalKind.OPERAND_TYPE_UNSUPPORTED,
            target,
            f"{leaf.field!r} is {forbidden[declared_type]}",
            where,
        )
    # Only then: a measure changes what is compared (LEN(x) is a number
    # whatever x is), so the operand must not be quoted as the column would be.
    column_type = "number" if leaf.measure == "length" else declared_type
    # An accessor changes it too, and for the same reason: the literal is
    # compared against the SUB-PROPERTY, not the column. A lookup is
    # int-typed in DBML, so without this `property: lookupValue` typed its
    # operand numerically and rejected every real title as "not a number",
    # leaving lookupId the only usable accessor.
    if leaf.property and leaf.measure != "length":
        column_type = _ACCESSOR_TYPES.get(leaf.property, column_type)

    if leaf.op in ("in", "not_in"):
        if target == CAML and leaf.op == "not_in":
            # CAML's bare Neq drops an empty field, but an empty value is
            # outside every non-empty set. Admit null once around the whole
            # conjunction rather than once per set member.
            ref = f'<FieldRef Name="{leaf.field}"/>'
            for item in leaf.value:
                # Same order as the leaf path below, so `not_in [now]` and
                # `in [now]` answer identically rather than differing by
                # which branch of this function happened to loop.
                _reject_meaningless_now(item, column_type, leaf.field, target, where)
                _check_date_literal(item, column_type, target, where)
            parts = [
                f"<Neq>{ref}{_caml_value(column_type, item, where, accessor)}</Neq>"
                for item in leaf.value
            ]
            excluded = _combine(parts, conjunction=True, target=CAML)
            return f"<Or><IsNull>{ref}</IsNull>{excluded}</Or>"
        op = "eq" if leaf.op == "in" else "neq"
        parts = [
            _leaf(Leaf(leaf.field, op, item, leaf.property, leaf.measure), types, target, at)
            for item in leaf.value
        ]
        return _combine(parts, conjunction=leaf.op == "not_in", target=target)

    if _is_today(leaf.value, column_type) and target == EXPRESSION:
        raise _reject(
            ConditionRefusalKind.TODAY_UNSUPPORTED_BY_TARGET,
            target,
            "the 'today' sentinel has no verified client-side equivalent "
            "(@now carries datetime rather than date semantics)",
            where,
        )

    _reject_meaningless_now(leaf.value, column_type, leaf.field, target, where)
    _check_date_literal(leaf.value, column_type, target, where)

    if _is_now(leaf.value, column_type) and target == EXPRESSION:
        raise _reject(
            ConditionRefusalKind.NOW_UNSUPPORTED_BY_TARGET,
            target,
            "the 'now' sentinel has no VERIFIED client-side equivalent. @now "
            "stores and reads back intact, but whether a show/hide rule built "
            "on it fires is a rendering behaviour no probe has observed, and "
            "this target has already produced one formula that stored "
            "perfectly and evaluated false for every value",
            where,
        )

    if is_current_user_sentinel(leaf.value, column_type) and target == EXPRESSION:
        raise _reject(
            ConditionRefusalKind.ME_UNSUPPORTED_BY_TARGET,
            target,
            "the 'me' sentinel has no verified client-side equivalent -- a "
            "show/hide formula is evaluated against the item's field values, "
            "not against the signed-in user, so the rule would save, read "
            "back equal, pass the phase and never fire",
            where,
        )

    if target == CAML:
        # Two refs, and the difference is measured rather than tidy. The id
        # dialect compares the lookup's ID and says so on the FieldRef; the
        # <IsNull> arm below keeps the BARE ref in either dialect, because
        # emptiness is a property of the field (a row with no value has
        # neither a title nor an id) and because bare is the spelling the
        # null tests and the composed wrapper were measured in.
        bare_ref = f'<FieldRef Name="{leaf.field}"/>'
        ref = (
            f'<FieldRef Name="{leaf.field}" LookupId="TRUE"/>'
            if accessor == "lookupId" else bare_ref
        )
        tag = _CAML_OP_TAGS[leaf.op]
        if leaf.op in VALUELESS_OPS:
            return f"<{tag}>{bare_ref}</{tag}>"
        rendered = f"<{tag}>{ref}{_caml_value(column_type, leaf.value, where, accessor)}</{tag}>"
        if leaf.op in ("neq", "not_includes"):
            # Neq is the exact inverse of Eq in the authored grammar. CAML
            # comparisons are three-valued, so make the empty case explicit
            # to match the expression and validation targets.
            #
            # `not_includes` takes the SAME wrapper, and on a MultiChoice
            # measurement says it need not: a bare <Neq> already returns the
            # empty row there (probe C9, 2026-08-10, R3 + R4), unlike every
            # single-value column, and C10 measured the composed form
            # returning exactly the same rows. So on that kind the wrapper is
            # redundant rather than wrong, and it was kept because uniformity
            # is worth more than the four elements it saves -- one `neq`
            # rendering, correct on both arities, with no branch to get
            # backwards. Nothing rests on <Or> child order either: C9 gives
            # R3 + R4 and C6's <IsNull> gives R4, a subset.
            #
            # ON A MULTI-VALUE LOOKUP THE WRAPPER DOES REAL WORK, measured
            # 2026-09-04: a bare negative there returns L3 alone and drops the
            # empty L4, as every single-value negative does and unlike
            # MultiChoice. So the two kinds differ in whether the wrapper is
            # needed and agree on what it emits, which is what makes one
            # rendering right for both.
            # `query.caml-adhoc.multilookup-neq-isnull-wrapper` measured the
            # composed form and got L3 + L4. It sent the negation first and
            # this emits <IsNull> first; the union is the same either way and
            # is established twice over, since <IsNull> alone measured L4 and
            # the negative alone measured L3.
            return f"<Or><IsNull>{bare_ref}</IsNull>{rendered}</Or>"
        return rendered

    if target == EXPRESSION:
        ref = f"[${leaf.field}{'.' + leaf.property if leaf.property else ''}]"
        if leaf.op == "is_null":
            return f"{ref} == ''"
        if leaf.op == "is_not_null":
            return f"{ref} != ''"
        if leaf.op in _TEXT_OPS:
            # All four text operators go through indexOf, which returns the
            # position or -1. One function carries the whole set, so there
            # is one behaviour to have verified rather than three.
            #
            # startsWith() and substring(...) == also render begins_with
            # correctly on a live tenant, and are not used: an extra
            # function is an extra thing that has to keep being true.
            literal = _expr_literal(column_type, leaf.value, where)
            found = f"indexOf({ref}, {literal})"
            return {
                "contains": f"{found} >= 0",
                "not_contains": f"{found} < 0",
                "begins_with": f"{found} == 0",
                "not_begins_with": f"{found} != 0",
            }[leaf.op]
        return f"{ref} {_EXPR_OPS[leaf.op]} {_expr_literal(column_type, leaf.value, where)}"

    return _validation_leaf(leaf, column_type, where)


def _today_offset(value: object) -> int:
    """The signed day offset of a `today` sentinel; bare `today` is 0."""
    match = _TODAY.match(str(value))
    if match is None or match.group(2) is None:
        return 0
    days = int(match.group(2))
    return -days if match.group(1) == "-" else days


def _shift(ref: str, days: int) -> str:
    """`ref` moved by whole days; a date is a serial number in a formula."""
    if days == 0:
        return ref
    return f"{ref}+{days}" if days > 0 else f"{ref}-{-days}"


def _save_instant_leaf(leaf: Leaf, column_type: str) -> str | None:
    """A comparison with `today` or `now`, rendered against the SAVE INSTANT.

    MEASURED 2026-09-02 (analysis/save_rules.py has the run): TODAY() and
    NOW() in a validation formula ran 16 to 20 hours behind an AUS Eastern
    site, so `=[D]<=TODAY()` refused the current date until late afternoon,
    while `[Modified]` in a list validation formula was the instant of the
    save being validated, site-local, on create and on update.

    A date-only value is stored as site-local midnight, so its date is
    "today+N" exactly when its midnight, shifted back by N days, is not
    after the save instant and its next midnight is. The offset shifts the
    column rather than the clock. A datetime carries a time of day, so the
    same arithmetic would compare instants rather than days; `today` on a
    datetime keeps the clock, and `now` is its exact form. Only the six
    comparison operators have a day-range reading; anything else keeps
    the clock too.
    """
    op = leaf.op
    if op not in _VALIDATION_OPS or leaf.measure:
        return None
    ref = f"[{leaf.field}]"
    if _is_now(leaf.value, column_type):
        return f"{ref}{_VALIDATION_OPS[op]}[Modified]"
    if column_type in _DATETIME_TYPES or not _is_today(leaf.value, column_type):
        return None
    offset = _today_offset(leaf.value)
    day = _shift(ref, -offset)
    next_day = _shift(ref, -offset + 1)
    match op:
        case "leq":
            return f"{day}<=[Modified]"
        case "lt":
            return f"{next_day}<=[Modified]"
        case "gt":
            return f"{day}>[Modified]"
        case "geq":
            return f"{next_day}>[Modified]"
        case "eq":
            return f"AND({day}<=[Modified],{next_day}>[Modified])"
        case _:
            return f"OR({day}>[Modified],{next_day}<=[Modified])"


def _validation_leaf(leaf: Leaf, column_type: str, where: str) -> str:
    ref = f"LEN([{leaf.field}])" if leaf.measure == "length" else f"[{leaf.field}]"
    if leaf.op == "is_null":
        return f"ISBLANK({ref})"
    if leaf.op == "is_not_null":
        return f"NOT(ISBLANK({ref}))"
    against_save = _save_instant_leaf(leaf, column_type)
    if against_save is not None:
        return against_save
    if (
        _is_today(leaf.value, column_type)
        and column_type in _DATETIME_TYPES
        and leaf.op in _VALIDATION_OPS
        and not leaf.measure
        and _today_offset(leaf.value) == 0
    ):
        # `[W]<=TODAY()` has no correct reading: TODAY() is midnight on a
        # clock measured 16 to 20 hours behind the site (2026-09-02), so
        # "not after today" refuses most of the last two days and "not
        # before today" accepts yesterday. `now` compares with the save
        # instant and is exact.
        raise _reject(
            ConditionRefusalKind.TODAY_ON_A_DATETIME_COLUMN,
            VALIDATION,
            f"'today' compared on the datetime column {leaf.field!r} would read "
            f"TODAY(), a clock measured hours behind the site; say 'now', which "
            f"compares with the instant of the save",
            where,
        )
    literal = _validation_literal(column_type, leaf.value, where)
    if leaf.op in ("contains", "not_contains"):
        rendered = f"ISNUMBER(FIND({literal},{ref}))"
        return f"NOT({rendered})" if leaf.op == "not_contains" else rendered
    if leaf.op in ("begins_with", "not_begins_with"):
        rendered = f"LEFT({ref},{len(str(leaf.value))})={literal}"
        return f"NOT({rendered})" if leaf.op == "not_begins_with" else rendered
    return f"{ref}{_VALIDATION_OPS[leaf.op]}{literal}"


def _caml_value(
    column_type: str, value: object, where: str, accessor: str | None = None,
) -> str:
    # First, because the accessor names the operand outright and the type
    # tests below would answer for the column instead. `_ACCESSOR_TYPES` has
    # already rewritten `column_type` to nvarchar/number for these two, which
    # is what the numeric guard wants and NOT what the Type= attribute wants:
    # the measured spellings are Lookup and Integer (see
    # `_CAML_LOOKUP_ACCESSORS`). `_number` still runs on the id dialect, so a
    # non-numeric id is a named build error rather than a filter that returns
    # nothing.
    if accessor is not None:
        # The table carries the attribute; the branch is on the ACCESSOR rather
        # than on what the table returned, because it is about the value being
        # numeric and not about how the attribute is spelled.
        spelling = _CAML_LOOKUP_ACCESSORS[accessor]
        if accessor == "lookupId":
            return f'<Value Type="{spelling}">{_number(value, where, CAML)}</Value>'
        escaped = _xml_escape(str(value), {chr(34): "&quot;"})
        return f'<Value Type="{spelling}">{escaped}</Value>'
    if is_current_user_sentinel(value, column_type):
        # SharePoint's own "[Me]" filter, and the only spelling by which a
        # person column can be compared in CAML at all.
        return '<Value Type="Integer"><UserID/></Value>'
    if is_boolean(column_type):
        return f'<Value Type="Integer">{"1" if _boolean(value, where, CAML) else "0"}</Value>'
    if column_type in _NUMBER_TYPES:
        return f'<Value Type="Number">{_number(value, where, CAML)}</Value>'
    if column_type in _DATE_TYPES:
        if _is_now(value, column_type):
            # NOT <Now/>. Learn documents that element, and the probe found
            # it returns nothing, the same signature an invented element
            # produces, because SharePoint does not validate this position.
            # IncludeTimeValue on <Today/> is the mechanism that works, and
            # it compares against the instant rather than midnight.
            return '<Value Type="DateTime" IncludeTimeValue="TRUE"><Today/></Value>'
        match = _TODAY.match(value) if isinstance(value, str) else None
        if match:
            sign, days = match.group(1), match.group(2)
            if not days or int(days) == 0:
                return '<Value Type="DateTime"><Today/></Value>'
            offset = days if sign == "+" else f"-{days}"
            return f'<Value Type="DateTime"><Today OffsetDays="{offset}"/></Value>'
        return f'<Value Type="DateTime">{_xml_escape(str(value))}</Value>'
    return f'<Value Type="Text">{_xml_escape(str(value), {chr(34): "&quot;"})}</Value>'


def _expr_literal(column_type: str, value: object, where: str) -> str:
    if is_boolean(column_type):
        return "true" if _boolean(value, where, EXPRESSION) else "false"
    if column_type in _NUMBER_TYPES:
        return _number(value, where, EXPRESSION)
    # Verified live: apostrophes escape by DOUBLING, not by backslash.
    return "'" + str(value).replace("'", "''") + "'"


def _validation_literal(column_type: str, value: object, where: str) -> str:
    if _is_today(value, column_type):
        # Only the offset form on a datetime column reaches here: a date
        # column renders against the save instant, and bare `today` on a
        # datetime is refused (`_validation_leaf`). It reads the lagging
        # clock, which the validator warns about.
        offset = _today_offset(value)
        return f"TODAY(){'+' if offset >= 0 else '-'}{abs(offset)}"
    if is_boolean(column_type):
        return "TRUE" if _boolean(value, where, VALIDATION) else "FALSE"
    if column_type in _NUMBER_TYPES:
        return _number(value, where, VALIDATION)
    # Verified live: validation literals are DOUBLE-quoted; single quotes are
    # rejected outright by SharePoint, the reverse of the expression target.
    # The doubling escape for an embedded double quote is the Excel
    # convention but was NOT among the harvested formulas. See the spec's
    # open items.
    return '"' + str(value).replace('"', '""') + '"'


# What each accessor compares, rather than the type of its parent column.
_ACCESSOR_TYPES: dict[str, str] = {
    "title": "nvarchar",
    "email": "nvarchar",
    "lookupValue": "nvarchar",
    "id": "number",
    "lookupId": "number",
}
