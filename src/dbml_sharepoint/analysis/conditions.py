# src/dbml_sharepoint/analysis/conditions.py
"""Normalisation, validation and rendering for the shared condition grammar.

`none_of` is eliminated here rather than at render time, because CAML has
no group-level negation: a renderer meeting a negated group would have
nothing to emit. De Morgan pushes negation down to the leaves, where every
operator has an exact inverse, so both renderers only ever see
`all_of`/`any_of` over positive leaves. That is the single property which
lets one authored grammar serve targets of very different expressive power.

The transformation is mechanical, terminating and depth-preserving:

    none_of[A, B]     ->  all_of[!A, !B]
    !(all_of[X, Y])   ->  any_of[!X, !Y]
    !(any_of[X, Y])   ->  all_of[!X, !Y]

Implications need no operator of their own. A validation rule is usually
"if A then B", which is `any_of[none_of[A], B]` — expressible in the
grammar as authored and normalised by the rules above.
"""

import datetime as dt
import math
import re

from dbml_sharepoint.analysis.typemap import CALCULATED_TYPES, NOW_SENTINEL, TODAY_SENTINEL
from dbml_sharepoint.model.conditions import Condition, Group, Leaf

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
}

# Bounds keep a pathological declaration a build error rather than a
# formula truncated at whatever limit the target happens to impose.
MAX_DEPTH = 4
MAX_LEAVES = 32

# Their own inverses, and never null-ambiguous.
_NULL_TESTS = frozenset({"is_null", "is_not_null"})

_FLIP: dict[str, str] = {"all_of": "any_of", "any_of": "all_of"}


def normalise(condition: Condition) -> Condition:
    """Return an equivalent tree of `all_of`/`any_of` over positive leaves."""
    return _push(condition, negate=False)


def _push(node: Condition, *, negate: bool) -> Condition:
    if isinstance(node, Leaf):
        if not negate:
            return node
        if node.op not in NEGATION:
            # Reached before the renderer's capability check, so an unknown
            # operator under none_of would otherwise surface as a bare
            # KeyError rather than a build error naming it.
            raise ValueError(
                f"cannot negate unknown operator {node.op!r} on {node.field!r}; "
                f"known operators: {', '.join(sorted(NEGATION))}",
            )
        flipped = Leaf(node.field, NEGATION[node.op], node.value, node.property, node.measure)
        if node.op in _NULL_TESTS or node.measure:
            # A null test is its own inverse, and a measure is never null —
            # LEN(blank) is 0, so the flipped comparison already matches.
            return flipped
        if node.op in ("not_contains", "not_begins_with"):
            # A negative text predicate is ALREADY true for a blank: indexOf
            # on an empty string is -1, which satisfies both `< 0` and
            # `!= 0`. Its negation must therefore be false there, and the
            # null arm below would OR the blank back in — making an authored
            # rule and its own negation both true for a blank value.
            #
            # That -1 is arithmetic, not an observation: the probe's typed
            # cases were all non-empty. It is row 4 of the eyes-on table now
            # (test/manual/expression-text-operators-probe.js), which asks it
            # directly and has not yet been run. If that row ever comes back
            # with X2 or X6 HIDDEN for the empty box, this branch is wrong
            # and so is the neq/not_in one below it.
            #
            # Same reasoning as neq/not_in, and it must stay a separate test:
            # `_TEXT_OPS` holds all four, and the `flipped.op` half of the
            # condition below would catch the POSITIVE two by their flips.
            # For those the null arm is right — `contains` is false for a
            # blank, so none_of must be true — and dropping it would change
            # output for a shape that already exists on main.
            return flipped
        if node.op in ("neq", "not_in") or flipped.op in ("neq", "not_in"):
            # These two inverse operators define the empty value as outside
            # the compared literal/set. Their renderers already carry that
            # semantic, so adding another null arm here would only duplicate
            # it in every none_of[eq/in] tree.
            return flipped
        # SharePoint comparisons are three-valued: CAML's bare Leq does NOT
        # match rows where the column is empty, so a bare operator flip would
        # make "none of the items where Count > 5" exclude items with no
        # Count at all — which is the opposite of what the words say, and
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

_CAML_OP_TAGS: dict[str, str] = {
    "eq": "Eq", "neq": "Neq", "lt": "Lt", "leq": "Leq", "gt": "Gt", "geq": "Geq",
    "is_null": "IsNull", "is_not_null": "IsNotNull",
    "contains": "Contains", "begins_with": "BeginsWith",
}
_EXPR_OPS: dict[str, str] = {
    "eq": "==", "neq": "!=", "lt": "<", "leq": "<=", "gt": ">", "geq": ">=",
}
_VALIDATION_OPS: dict[str, str] = {
    "eq": "=", "neq": "<>", "lt": "<", "leq": "<=", "gt": ">", "geq": ">=",
}

_TEXT_OPS = frozenset({"contains", "not_contains", "begins_with", "not_begins_with"})

# Operators each target can render. A miss is a build error naming the
# target — never a formula emitted in hope.
CAPABILITIES: dict[str, frozenset[str]] = {
    # CAML has Contains/BeginsWith but no negation of either.
    CAML: frozenset(_CAML_OP_TAGS) | {"in", "not_in"},
    EXPRESSION: frozenset(_EXPR_OPS) | {"is_null", "is_not_null", "in", "not_in"} | _TEXT_OPS,
    VALIDATION: frozenset(_VALIDATION_OPS) | {"is_null", "is_not_null", "in", "not_in"} | _TEXT_OPS,
}

# Operators plausible from the documented syntax but never observed in a
# formula on a live tenant. Unverified is treated as unknown, and the probe
# that settles one is named in the error — a signpost pointing at a probe
# that does not ask reads as though somebody already checked.
#
# EMPTY, and the emptiness is the claim: every operator this tool renders
# onto the expression target has been watched working in a form — with one
# stated exception. `not_begins_with` renders `indexOf(...) != 0`, which was
# not among the candidates the 2026-07-29 pass carried; it is the exact
# negation of the `== 0` that WAS watched, over the same call whose value was
# watched, so it is derived rather than observed. Named here rather than left
# for a reader to assume, because the whole worth of this list is that it is
# honest. The probe now asks it directly, as X6, and asking is not answering
# — the row is unrun until somebody pastes the script and reports it.
#
# It stays here because storage cannot establish anything on this target.
# SharePoint does not validate ClientValidationFormula on write — a call to
# a function that does not exist is accepted and read back byte-identical
# (test/manual/expression-text-operators-probe.js, X0) — so the only proof
# a rendering works is a person watching a column appear and disappear.
# Anything added to CAPABILITIES[EXPRESSION] without that belongs here
# first.
DISABLED_PENDING_PROBE: dict[str, frozenset[str]] = {}

# Transforms a target cannot express at all, as opposed to merely unproven.
#
# `measure: length` on the expression target is the important one, and it is
# not an omission: list formatting's `length` returns an ARRAY's item count,
# and 1 or 0 for anything else — it does not measure a string. Rendering
# `length([$Note]) > 3` would therefore be false for every possible value,
# hiding the column unconditionally, with a formula that saves cleanly. The
# documented idiom is a sentinel trick (`indexOf([$Note] + '^', '^')`), which
# is not enabled here because it has not been run against a tenant.
_UNSUPPORTED_MEASURE: dict[str, str] = {
    CAML: "CAML has no LEN",
    EXPRESSION: (
        "list formatting's length() counts array items and returns 1/0 for other "
        "types — it does not measure a string, so the formula would be false for "
        "every value"
    ),
}
# CAML reaches a lookup's id via FieldRef LookupId, and a person's email not
# at all. Rendering the accessor away — comparing a display name to an email
# address — is a view that silently returns the wrong rows, so it is refused.
_UNSUPPORTED_PROPERTY: dict[str, str] = {
    CAML: "CAML cannot reach person or lookup sub-properties",
    VALIDATION: "person and lookup operands are unsupported in validation formulas",
}

# Operand types a target refuses outright. SharePoint validation formulas
# cannot read a person, a multi-line column or a calculated column, and
# reject the rule at save — so the build refuses first.
#
# Conditional show/hide is worse, and that is why it is listed here too:
# Microsoft documents calculated columns as unsupported, but the formula
# stays SYNTACTICALLY valid, so it saves, the read-back compares equal and
# the phase passes. The failure is invisible from the deploy side
# entirely — a green build, a green manifest, and a form that never
# reacts. The most natural rule in the shipped risk register ("show
# Treatment only when the calculated RiskRating is High or Extreme") is
# exactly this shape.
#
# The same Learn page lists Currency, Location, Managed Metadata and the
# multi-select Person/Choice/Lookup variants as unsupported. None of them
# has a DBML type in this tool, so there is nothing here to reject — the
# omission is considered, not missed. Time-of-day comparisons on Date and
# Time are likewise unreachable: `today` is already refused for this
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
        # outright — HTTP 500, "One or more column references are not
        # allowed, because the columns are defined as a data type that is
        # not supported in formulas" — so this is a closed question, not an
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

_NUMBER_TYPES = frozenset({"int", "number", "calculated_number"})
_DATE_TYPES = frozenset({"date", "datetime", "calculated_date"})
# `now` is for the columns that carry a time of day. A DATE column has no
# time to compare, so `now` on one is `today` written confusingly, and the
# semantic check below says so rather than rendering it.
_DATETIME_TYPES = frozenset({"datetime"})
_TODAY = TODAY_SENTINEL          # one home: analysis/typemap.py
_NOW = NOW_SENTINEL              # same home, same reason
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
# tenant, and two of the three answers contradict a Microsoft document:
#
#   VALIDATION -> NOW()
#       Microsoft's "Introduction to SharePoint formulas and functions"
#       states "Lists and libraries do not support the RAND and NOW
#       functions". That is TRUE of calculated columns and FALSE here: the
#       probe set `=[ProbeWhen]<=NOW()`, SharePoint returned 204, read it
#       back, and REFUSED an item stamped three hours in the future.
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
#       C2-C5 used an ad-hoc CamlQuery; the deploy writes a view's stored
#       ViewQuery, and SharePoint rewrites that XML on save. So C6 read the
#       stored query back (the attribute survived) and C7 re-ran THAT XML
#       and got the same two rows — confirmed a third time by eye, in the
#       view itself.
#
#       CORROBORATED BY SHAREPOINT'S OWN UI, from a direction the probe
#       cannot reach. Opening the <Now/> view's filter panel shows an EMPTY
#       value — the UI cannot represent that element, and a date comparison
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
# side-stepping it — CAML's <UserID/> compares the person field's user id
# natively, so the sentinel SUPPLIES the missing accessor instead of
# declaring one, which is why it takes no `property` and refuses one.
_ME = "me"
_PERSON_TYPES = frozenset({"person"})
# <UserID/> is an identity. Ordering it, or asking whether it contains a
# substring, is meaningless rather than merely unrendered.
_ME_OPS = frozenset({"eq", "neq"})
# True == 1 and False == 0 in Python, so the bare ints cover the bools.
_TRUTHY = frozenset({1, "1", "true", "True", "TRUE", "yes", "Yes", "YES"})
_FALSY = frozenset({0, "0", "false", "False", "FALSE", "no", "No", "NO"})
_VALUELESS_OPS = frozenset({"is_null", "is_not_null"})


def _reject(target: str, reason: str, context: str) -> ValueError:
    return ValueError(f"{context}: {reason} (target: {target})")


def _check(leaf: Leaf, target: str, context: str) -> None:
    if leaf.op in DISABLED_PENDING_PROBE.get(target, frozenset()):
        raise _reject(
            target,
            f"operator {leaf.op!r} is not yet verified against a live tenant for this "
            f"target; confirm it with test/manual/expression-text-operators-probe.js "
            f"and enable it deliberately",
            context,
        )
    if leaf.op not in CAPABILITIES[target]:
        raise _reject(target, f"operator {leaf.op!r} has no rendering", context)
    if leaf.measure and target in _UNSUPPORTED_MEASURE:
        raise _reject(
            target, f"'measure' cannot be rendered: {_UNSUPPORTED_MEASURE[target]}", context,
        )
    if leaf.property and target in _UNSUPPORTED_PROPERTY:
        raise _reject(target, _UNSUPPORTED_PROPERTY[target], context)
    if leaf.op not in _VALUELESS_OPS and leaf.value is None:
        raise _reject(target, f"operator {leaf.op!r} needs a 'value'", context)
    if leaf.op in _VALUELESS_OPS and leaf.value is not None:
        raise _reject(target, f"operator {leaf.op!r} takes no 'value'", context)
    if leaf.op in ("in", "not_in") and not isinstance(leaf.value, list):
        raise _reject(target, f"operator {leaf.op!r} needs a list 'value'", context)
    if leaf.op in ("in", "not_in") and not leaf.value:
        raise _reject(
            target,
            f"operator {leaf.op!r} has an empty list, which is a constant — say what "
            f"you mean with a condition rather than an empty set",
            context,
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
    return (
        column_type in _DATETIME_TYPES
        and isinstance(value, str)
        and bool(_NOW.match(value))
    )


def _looks_like_a_date(value: object) -> bool:
    """`YYYY-MM-DD`, optionally with a `T` time and an offset — the grammar
    the renderers emit, and the only literal form a date column may carry
    once the sentinels have had their turn.

    Deliberately strict, and strict in the direction of emitting less. What
    SharePoint does with an unparseable DateTime operand has not been probed
    — it might refuse the view, or take it and filter on something nobody
    intended — and a filter that quietly matches the wrong rows is invisible
    from the build and from the deploy alike. Refusing here needs no answer
    to that question.

    A bare `datetime.date` passes: PyYAML resolves an unquoted `2026-07-29`
    to one before this module sees it, and `str()` on a date is the ISO
    literal exactly. A `datetime.datetime` does NOT — `str()` spells the
    separator as a space, which no probe has run — and it is rejected by
    `_check_date_literal` with its own message rather than here.

    Surrounding whitespace is NOT tolerated, and the absence of a `.strip()`
    here is the point. Every renderer emits `str(value)` unchanged, so a
    value this function trimmed in order to parse would validate as one
    string and reach SharePoint as another — approving a spelling no probe
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


def _check_date_literal(
    value: object, column_type: str, target: str, where: str, op: str = "eq",
) -> None:
    """A date column's literal, once `today` and `now` have had their turn,
    must be a real date. Nothing downstream checks it, and no probe has
    asked what SharePoint does with an unparseable one — so the failure is
    UNBOUNDED rather than known: it may refuse the view, or accept it and
    filter on something nobody intended. The build is the only place that
    can be settled without a tenant, so it is settled here.

    `now+1` is the case that matters most. `today±N` works, which makes the
    offset form the obvious thing to reach for, and without this it is an
    unparseable literal in a filter that silently matches nothing.

    Called per SET MEMBER as well as per leaf: CAML renders `not_in` by
    looping the members itself rather than recursing through `_leaf`, so one
    bad literal among good ones used to walk straight past this.
    """
    if column_type not in _DATE_TYPES or value is None:
        return
    if _is_today(value, column_type) or _is_now(value, column_type):
        # A sentinel is a POINT IN TIME. Comparison, ordering and set
        # membership mean something against one; a substring test does not,
        # and the exemption used to wave it past this guard. What the
        # renderers then emit — verified by running them, not by reasoning:
        #
        #   contains + now  ->  ISNUMBER(FIND(NOW(),[OccurredAt]))
        #   begins_with     ->  LEFT([OccurredAt],3)=NOW()
        #
        # That 3 is len('now'): the sentinel's SPELLING reaching the formula
        # as a character count. It is measuring the word, not the date, and
        # that is decidable here without knowing anything about how
        # SharePoint would treat either formula — which nobody does, since
        # no probe has ever sent one. Refusing needs no such answer.
        if op in _TEXT_OPS:
            raise _reject(
                target,
                f"{value!r} is a point in time and {op!r} is a substring test, so "
                f"the two cannot be combined — the sentinel would reach the formula "
                f"as its own spelling rather than as a date. Use a comparison "
                f"(eq/neq/lt/leq/gt/geq) or a set test (in/not_in)",
                where,
            )
        return
    if _looks_like_a_date(value):
        return

    # PyYAML resolves an unquoted `2026-07-29T14:30:00` to a datetime, and
    # `str()` on one spells the separator as a SPACE. Quoting it gives the
    # `T` spelling the probe ran, so say that rather than claiming the value
    # the author wrote is not a date.
    if isinstance(value, dt.datetime):
        raise _reject(
            target,
            f"{value!r} is an unquoted YAML datetime; quote it. Unquoted, it "
            f"reaches the renderers as a datetime object whose text form "
            f"separates date from time with a SPACE, and no probe has run "
            f"that spelling — '{value.isoformat()}' has",
            where,
        )

    # A padded date gets its own message: "is not a date" would send the
    # author hunting a typo in a value that is already correct apart from
    # the spaces. Both branches deliberately strip before MATCHING - the
    # leniency is diagnostic only, so the hint can recognise what the guard
    # above has already refused.
    if (
        isinstance(value, str)
        and value != value.strip()
        and _looks_like_a_date(value.strip())
    ):
        raise _reject(
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
            " — 'now' takes no offset form (today±N does, now±N has no "
            "verified rendering); use a bare 'now', or 'today±N' for a "
            "whole-day boundary"
        )
    raise _reject(
        target,
        f"{value!r} is not a date, the sentinel 'today'/'today±N', or "
        f"'now'. What SharePoint does with an unparseable date literal has "
        f"not been probed — it may refuse the view or filter on something "
        f"nobody intended — so it is refused here, where the answer does not "
        f"matter{hint}",
        where,
    )


def _is_me(value: object, column_type: str) -> bool:
    """A `me` sentinel only means the current user on a PERSON column. On a
    text column it is the literal word — the same rule `today` follows, and
    for the same reason: one authored condition must not mean three
    different things across the three targets."""
    return column_type in _PERSON_TYPES and value == _ME


def _number(value: object, context: str, target: str) -> str:
    """A numeric column's operand is emitted bare. The declared type is
    authoritative: a value that is not a number on a numeric column is a
    build error, not a silent string comparison where '10' < '5'."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise _reject(target, f"{value!r} is not a number", context)
    try:
        numeric = float(value)
    except ValueError:
        raise _reject(target, f"{value!r} is not a number on a numeric column", context) from None
    if not math.isfinite(numeric):
        raise _reject(target, f"{value!r} is not a finite number", context)
    return str(int(numeric)) if numeric.is_integer() else str(numeric)


def _boolean(value: object, context: str, target: str) -> bool:
    """Coercion is two-sided. A one-sided test silently inverts the
    condition for the author who quotes 'true', which is the cautious
    thing to do and so exactly the author who should not be punished."""
    if not isinstance(value, (bool, int, str)):
        raise _reject(target, f"{value!r} is not a boolean", context)
    if value in _TRUTHY:
        return True
    if value in _FALSY:
        return False
    raise _reject(target, f"{value!r} is not a boolean", context)


def to_caml(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a CAML `<Where>` body."""
    return _render(normalise(condition), column_types, CAML, "conditions")


def to_expression(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a list-formatting predicate for `ClientValidationFormula`."""
    return _render(normalise(condition), column_types, EXPRESSION, "conditions")


def to_validation(condition: Condition, column_types: dict[str, str]) -> str:
    """Render to a classic validation predicate for `ValidationFormula`."""
    return _render(normalise(condition), column_types, VALIDATION, "conditions")


def _render(node: Condition, types: dict[str, str], target: str, context: str) -> str:
    if isinstance(node, Leaf):
        return _leaf(node, types, target, context)
    parts = [_render(child, types, target, context) for child in node.children]
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


def _column_type(field: str, types: dict[str, str], target: str, context: str) -> str:
    """The declared type drives literal rendering, so an unknown column is
    an error rather than a silent 'nvarchar'. A date column defaulting to
    text renders `<Value Type="Text">today-30</Value>` — the sentinel as a
    literal string, which is not the comparison anybody wrote, whatever
    SharePoint then does with it."""
    if field not in types:
        raise _reject(target, f"no declared type for column {field!r}", context)
    return types[field]


def _leaf(leaf: Leaf, types: dict[str, str], target: str, context: str) -> str:
    where = f"{context}.{leaf.field}"
    _check(leaf, target, where)
    # Gate on the REAL column type first. Substituting "number" for a
    # measure ahead of this check lets LEN([MultiLine]) past a rule that
    # is_not_null on the same column hits — the tool contradicting itself,
    # and routing the author to whichever spelling the guard misses.
    declared_type = _column_type(leaf.field, types, target, where)
    forbidden = _FORBIDDEN_OPERAND_TYPES.get(target, {})
    if declared_type in forbidden:
        raise _reject(target, f"{leaf.field!r} is {forbidden[declared_type]}", where)
    # Only then: a measure changes what is compared — LEN(x) is a number
    # whatever x is — so the operand must not be quoted as the column would be.
    column_type = "number" if leaf.measure == "length" else declared_type
    # An accessor changes it too, and for the same reason: the literal is
    # compared against the SUB-PROPERTY, not the column. A lookup is
    # int-typed in DBML, so without this `property: lookupValue` typed its
    # operand numerically and rejected every real title as "not a number" —
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
                _check_date_literal(item, column_type, target, where, leaf.op)
            parts = [
                f"<Neq>{ref}{_caml_value(column_type, item, where)}</Neq>"
                for item in leaf.value
            ]
            excluded = _combine(parts, conjunction=True, target=CAML)
            return f"<Or><IsNull>{ref}</IsNull>{excluded}</Or>"
        op = "eq" if leaf.op == "in" else "neq"
        parts = [
            _leaf(Leaf(leaf.field, op, item, leaf.property, leaf.measure), types, target, context)
            for item in leaf.value
        ]
        return _combine(parts, conjunction=leaf.op == "not_in", target=target)

    if _is_today(leaf.value, column_type) and target == EXPRESSION:
        raise _reject(
            target,
            "the 'today' sentinel has no verified client-side equivalent "
            "(@now carries datetime rather than date semantics)",
            where,
        )

    # `now` on a DATE column would silently render as the literal string
    # "now" inside a DateTime value, which SharePoint accepts and answers
    # with the wrong rows. Caught here, named, and pointed at `today`.
    if (
        isinstance(leaf.value, str)
        and _NOW.match(leaf.value)
        and column_type in _DATE_TYPES
        and column_type not in _DATETIME_TYPES
    ):
        raise _reject(
            target,
            f"the 'now' sentinel needs a datetime column; {leaf.field!r} is "
            f"{column_type!r}, which has no time of day — use 'today'",
            where,
        )

    _check_date_literal(leaf.value, column_type, target, where, leaf.op)

    if _is_now(leaf.value, column_type) and target == EXPRESSION:
        raise _reject(
            target,
            "the 'now' sentinel has no VERIFIED client-side equivalent. @now "
            "stores and reads back intact, but whether a show/hide rule built "
            "on it fires is a rendering behaviour no probe has observed, and "
            "this target has already produced one formula that stored "
            "perfectly and evaluated false for every value",
            where,
        )

    if _is_me(leaf.value, column_type) and target == EXPRESSION:
        raise _reject(
            target,
            "the 'me' sentinel has no verified client-side equivalent — a "
            "show/hide formula is evaluated against the item's field values, "
            "not against the signed-in user, so the rule would save, read "
            "back equal, pass the phase and never fire",
            where,
        )

    if target == CAML:
        ref = f'<FieldRef Name="{leaf.field}"/>'
        tag = _CAML_OP_TAGS[leaf.op]
        if leaf.op in _VALUELESS_OPS:
            return f"<{tag}>{ref}</{tag}>"
        rendered = f"<{tag}>{ref}{_caml_value(column_type, leaf.value, where)}</{tag}>"
        if leaf.op == "neq":
            # Neq is the exact inverse of Eq in the authored grammar. CAML
            # comparisons are three-valued, so make the empty case explicit
            # to match the expression and validation targets.
            return f"<Or><IsNull>{ref}</IsNull>{rendered}</Or>"
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


def _validation_leaf(leaf: Leaf, column_type: str, where: str) -> str:
    ref = f"LEN([{leaf.field}])" if leaf.measure == "length" else f"[{leaf.field}]"
    if leaf.op == "is_null":
        return f"ISBLANK({ref})"
    if leaf.op == "is_not_null":
        return f"NOT(ISBLANK({ref}))"
    literal = _validation_literal(column_type, leaf.value, where)
    if leaf.op in ("contains", "not_contains"):
        rendered = f"ISNUMBER(FIND({literal},{ref}))"
        return f"NOT({rendered})" if leaf.op == "not_contains" else rendered
    if leaf.op in ("begins_with", "not_begins_with"):
        rendered = f"LEFT({ref},{len(str(leaf.value))})={literal}"
        return f"NOT({rendered})" if leaf.op == "not_begins_with" else rendered
    return f"{ref}{_VALIDATION_OPS[leaf.op]}{literal}"


def _caml_value(column_type: str, value: object, where: str) -> str:
    if _is_me(value, column_type):
        # SharePoint's own "[Me]" filter, and the only spelling by which a
        # person column can be compared in CAML at all.
        return '<Value Type="Integer"><UserID/></Value>'
    if column_type == "boolean":
        return f'<Value Type="Integer">{"1" if _boolean(value, where, CAML) else "0"}</Value>'
    if column_type in _NUMBER_TYPES:
        return f'<Value Type="Number">{_number(value, where, CAML)}</Value>'
    if column_type in _DATE_TYPES:
        if _is_now(value, column_type):
            # NOT <Now/>. Learn documents that element, and the probe found
            # it returns nothing — the same signature an invented element
            # produces, because SharePoint does not validate this position.
            # IncludeTimeValue on <Today/> is the mechanism that works, and
            # it compares against the instant rather than midnight.
            return '<Value Type="DateTime" IncludeTimeValue="TRUE"><Today/></Value>'
        match = _TODAY.match(value) if isinstance(value, str) else None
        if match:
            sign, days = match.group(1), match.group(2)
            if days is None:
                return '<Value Type="DateTime"><Today/></Value>'
            offset = days if sign == "+" else f"-{days}"
            return f'<Value Type="DateTime"><Today OffsetDays="{offset}"/></Value>'
        return f'<Value Type="DateTime">{_xml_escape(str(value))}</Value>'
    return f'<Value Type="Text">{_xml_escape(str(value), {chr(34): "&quot;"})}</Value>'


def _expr_literal(column_type: str, value: object, where: str) -> str:
    if column_type == "boolean":
        return "true" if _boolean(value, where, EXPRESSION) else "false"
    if column_type in _NUMBER_TYPES:
        return _number(value, where, EXPRESSION)
    # Verified live: apostrophes escape by DOUBLING, not by backslash.
    return "'" + str(value).replace("'", "''") + "'"


def _validation_literal(column_type: str, value: object, where: str) -> str:
    if _is_now(value, column_type):
        # Microsoft's formula reference says Lists do not support NOW().
        # That holds for calculated columns and not for validation: probed
        # 2026-07-29, accepted with HTTP 204 and enforced against a
        # timestamp three hours in the future.
        return "NOW()"
    if _is_today(value, column_type):
        match = _TODAY.match(str(value))
        sign, days = (match.group(1), match.group(2)) if match else (None, None)
        return "TODAY()" if days is None else f"TODAY(){sign}{days}"
    if column_type == "boolean":
        return "TRUE" if _boolean(value, where, VALIDATION) else "FALSE"
    if column_type in _NUMBER_TYPES:
        return _number(value, where, VALIDATION)
    # Verified live: validation literals are DOUBLE-quoted; single quotes are
    # rejected outright by SharePoint, the reverse of the expression target.
    # The doubling escape for an embedded double quote is the Excel
    # convention but was NOT among the harvested formulas — see the spec's
    # open items.
    return '"' + str(value).replace('"', '""') + '"'


# === Semantic validation ====================================================
# Types for the columns SharePoint provides but DBML never declares. Views
# may reference these, and without them a date comparison on Created would
# render as Type="Text" — which SharePoint accepts and answers with the
# wrong rows.
SYSTEM_COLUMN_TYPES: dict[str, str] = {
    "ID": "int",
    "Created": "datetime",
    "Modified": "datetime",
    "Author": "person",
    "Editor": "person",
}


def effective_column_types(
    declared: dict[str, str], cross_site_columns: set[str] | frozenset[str] = frozenset(),
) -> dict[str, str]:
    """Types for DBML columns plus fields provisioned implicitly or by expansion."""
    effective = {"Title": "nvarchar", **declared}
    for name in cross_site_columns:
        effective.setdefault(f"{name}Abbreviation", "nvarchar")
        effective.setdefault(f"{name}SiteUrl", "hyperlink")
    return effective

# There is no defensible default between a person's display name, their
# email and their id, so the accessor is declared rather than guessed.
PROPERTY_ACCESSORS: dict[str, frozenset[str]] = {
    "person": frozenset({"title", "email", "id"}),
    "lookup": frozenset({"lookupValue", "lookupId"}),
}
# What each accessor COMPARES, which is not what the column is declared as.
# A lookup is int-typed in DBML and a person is its own type, but a title,
# an email or a lookup's display value are all text, and the two id
# accessors are numbers. Typing the literal by the column instead of the
# accessor is what made `property: lookupValue` unusable.
_ACCESSOR_TYPES: dict[str, str] = {
    "title": "nvarchar",
    "email": "nvarchar",
    "lookupValue": "nvarchar",
    "id": "number",
    "lookupId": "number",
}
_MEASURABLE_TYPES = frozenset({"nvarchar", "longtext", "richtext", "calculated_text"})

_RENDERERS = {CAML: to_caml, EXPRESSION: to_expression, VALIDATION: to_validation}


def leaves(node: Condition) -> list[Leaf]:
    """Every leaf of a tree, in declaration order."""
    if isinstance(node, Leaf):
        return [node]
    return [leaf for child in node.children for leaf in leaves(child)]


def validate_condition(
    condition: Condition,
    *,
    target: str,
    rendered: set[str],
    types: dict[str, str],
    lookups: set[str],
    context: str,
) -> list[str]:
    """Semantic problems with a declared condition, as messages.

    Returns rather than raises, and keeps going after the first problem, so
    one build reports every broken leaf instead of one per run. Messages are
    wrapped into Findings by the caller — this module stays free of a
    validator import, which would be a cycle.
    """
    problems: list[str] = []
    # Keyed by identity, not by field name: two leaves on one column can
    # fail for different reasons, and reporting only the first costs the
    # author another build.
    suppressed: set[int] = set()
    unknown_ops = {leaf.op for leaf in leaves(condition) if leaf.op not in NEGATION}
    # Bounds are measured after normalisation, since negation expands each
    # leaf into any_of[is_null, flipped] and `in` into one leaf per value.
    # Skipped when an operator is unknown, because normalise cannot run.
    depth, leaf_count = measure_tree(condition if unknown_ops else normalise(condition))
    if depth > MAX_DEPTH:
        problems.append(f"{context}: nested {depth} groups deep; the limit is {MAX_DEPTH}")
    if leaf_count > MAX_LEAVES:
        problems.append(
            f"{context}: {leaf_count} conditions after expanding any 'in' lists; "
            f"the limit is {MAX_LEAVES}",
        )

    for leaf in leaves(condition):
        where = f"{context}.{leaf.field}"
        if leaf.field not in rendered:
            problems.append(f"{where}: not a rendered column")
            continue
        if leaf.op not in NEGATION:
            problems.append(
                f"{where}: unknown operator {leaf.op!r}; "
                f"known operators: {', '.join(sorted(NEGATION))}",
            )
            continue
        operand = _operand_problems(leaf, where, types=types, lookups=lookups)
        lookup_problem = _lookup_problem(leaf, where, target, lookups)
        if lookup_problem:
            operand.append(lookup_problem)
        if operand:
            # Rendering a leaf whose operands are already wrong would report
            # the same fault twice in different words — but only THAT leaf is
            # suppressed, so one bad operand cannot mask any other fault.
            problems.extend(operand)
            suppressed.add(id(leaf))

    if unknown_ops:
        # normalise() needs a negation for every operator, so it cannot run
        # over a tree containing one it does not know. The unknown operator
        # is already reported above; raising here instead would turn a typo
        # into a traceback.
        return _dedupe(problems)

    for leaf in leaves(condition):
        if id(leaf) in suppressed or leaf.field not in rendered:
            continue
        problems.extend(_render_problems(leaf, target, types, context))

    # Second pass, over the tree the RENDERER will actually see. De Morgan
    # normalisation rewrites operators — none_of[contains] becomes
    # not_contains — so a rule can pass every check above and still be
    # unrenderable. Without this it surfaced as a ValueError out of
    # build_schema_json instead of a finding: a traceback where the author
    # needed a sentence.
    #
    # Only operators normalisation INTRODUCED are reported here. Anything
    # the author wrote was already judged above, in their own vocabulary,
    # and repeating it under a rewritten name would read as two faults.
    authored_ops = {leaf.op for leaf in leaves(condition)}
    for leaf in leaves(normalise(condition)):
        if leaf.op in authored_ops or leaf.field not in rendered:
            continue
        for problem in _render_problems(leaf, target, types, context):
            problems.append(
                f"{problem} — negating this rule turns it into {leaf.op!r}, "
                f"which that target cannot express. Rewrite it as a positive "
                f"filter, or move it to a target that supports the negation.",
            )
    return _dedupe(problems)


def _operand_problems(
    leaf: Leaf, where: str, *, types: dict[str, str], lookups: set[str],
) -> list[str]:
    column_type = types.get(leaf.field, "")
    kind = "lookup" if leaf.field in lookups else column_type
    problems: list[str] = []
    # The `me` sentinel carries its own accessor semantics: <UserID/>
    # compares the person field's user id, so an accessor is neither needed
    # nor meaningful beside it. Handled before the accessor rules rather
    # than inside them, because the exemption is the whole point — without
    # it a person column cannot be filtered in CAML at all.
    if _is_me(leaf.value, column_type):
        if leaf.property:
            problems.append(
                f"{where}: 'me' compares the person column's user id, so it takes no "
                f"'property' — drop {leaf.property!r}",
            )
        if leaf.op not in _ME_OPS:
            problems.append(
                f"{where}: 'me' is an identity, so operator {leaf.op!r} has no meaning "
                f"against it; use one of {', '.join(sorted(_ME_OPS))}",
            )
        return problems
    # A null test needs no accessor either, and for the same reason `me`
    # needs none: emptiness is a property of the FIELD, not of a name, an
    # email or an id — all three are absent together. CAML's IsNull takes a
    # bare FieldRef and no Value, so there is nothing for an accessor to
    # change. Without this, "organisations with no owner" — a view
    # stakeholder-contacts' governance doc asks for by name — was
    # inexpressible: the accessor rules demanded a property and CAML
    # refuses every property.
    if kind in PROPERTY_ACCESSORS and leaf.op in _VALUELESS_OPS and not leaf.property:
        return problems
    if kind in PROPERTY_ACCESSORS:
        allowed = PROPERTY_ACCESSORS[kind]
        if not leaf.property:
            problems.append(
                f"{where}: a {kind} column needs 'property' "
                f"(one of {', '.join(sorted(allowed))})",
            )
        elif leaf.property not in allowed:
            problems.append(
                f"{where}: {leaf.property!r} is not a {kind} accessor; "
                f"use one of {', '.join(sorted(allowed))}",
            )
    elif leaf.property:
        problems.append(f"{where}: 'property' applies to person and lookup columns only")
    if leaf.measure and leaf.measure != "length":
        problems.append(f"{where}: unknown measure {leaf.measure!r}; only 'length' is supported")
    if leaf.measure and column_type not in _MEASURABLE_TYPES:
        problems.append(f"{where}: 'measure: length' applies to text columns only")
    return problems


def _lookup_problem(leaf: Leaf, where: str, target: str, lookups: set[str]) -> str | None:
    """Lookups are int-typed in DBML, so the type map alone cannot see them."""
    if target == VALIDATION and leaf.field in lookups:
        return f"{where}: {leaf.field!r} is a lookup column, unsupported in validation formulas"
    return None


def _render_problems(
    leaf: Leaf, target: str, types: dict[str, str], context: str,
) -> list[str]:
    """Reuse the renderer as the capability oracle, one leaf at a time, so a
    second copy of the capability rules cannot drift from the first."""
    try:
        _RENDERERS[target](leaf, types)
    except ValueError as exc:
        return [str(exc).replace("conditions.", f"{context}.", 1)]
    return []


def _dedupe(messages: list[str]) -> list[str]:
    seen: list[str] = []
    for message in messages:
        if message not in seen:
            seen.append(message)
    return seen


def describe(node: Condition) -> str:
    """A human-readable summary for manifests and documentation.

    Deliberately not any target's syntax: an operator reads as its declared
    name, so an operator a reader does not recognise sends them to the
    grammar reference rather than to a SharePoint dialect they would then
    have to identify.
    """
    if isinstance(node, Leaf):
        subject = f"{node.field}.{node.property}" if node.property else node.field
        if node.measure:
            subject = f"{node.measure}({subject})"
        if node.op in _NULL_TESTS:
            return f"{subject} {node.op}"
        return f"{subject} {node.op} {node.value!r}"
    joiner = {"all_of": " AND ", "any_of": " OR ", "none_of": " OR "}[node.kind]
    inner = joiner.join(describe(child) for child in node.children)
    if node.kind == "none_of":
        # NOT must survive a single child: `none_of[A]` is the canonical
        # implication idiom, and dropping the negation made the manifest
        # state the opposite of the rule it described.
        return f"NOT({inner})"
    return inner if len(node.children) == 1 else f"({inner})"
