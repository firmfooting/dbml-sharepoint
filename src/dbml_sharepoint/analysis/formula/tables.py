"""Finite-domain tables: a sub-formula that reads only choice columns, each compared with `=` or
`<>` against text literals, takes one of a few results, so it is written as a nested table.

A choice column's domain is the literals, a blank and any other value. A blank and an unlisted
value make every literal comparison false, so they share one class, and the table's result for
it is the formula's own with every comparison false. A comparison ignores case (measured), so a
stored `a` takes the literal `A` branch.
"""

import itertools
import math
from collections.abc import Callable, Mapping
from typing import Protocol

from dbml_sharepoint.analysis.formatter_values import quoted
from dbml_sharepoint.analysis.formula.parse import parse_formula
from dbml_sharepoint.analysis.formula.syntax import (
    Binary,
    Call,
    Expr,
    FormulaSyntaxError,
    Neg,
    Num,
    Percent,
    Ref,
    Text,
)

# A work bound on the leaves one table may hold, not a platform fact.
_MAX_LEAVES = 4096


class Coded(Protocol):
    @property
    def code(self) -> str: ...


class _NotATable(Exception):  # noqa: N818 -- control flow, not an error
    pass


class _Rewrite:
    """The formula with calculated columns inlined and each choice comparison replaced by a
    constant comparison: `1 = 1` when `picked` makes it hold, `1 = 0` when not."""

    def __init__(
        self,
        formulas: Mapping[str, str],
        choices: frozenset[str],
        picked: Mapping[str, str | None] | None,
    ) -> None:
        self.formulas, self.choices, self.picked = formulas, choices, picked
        self.uses: dict[str, dict[str, str]] = {}  # column -> casefolded literal -> literal

    def go(self, node: Expr, stack: tuple[str, ...]) -> Expr:
        match node:
            case Num() | Text():
                return node
            case Ref(name=name):
                return self.inline(name, stack)
            case Neg(operand=operand):
                return Neg(self.go(operand, stack))
            case Percent(operand=operand):
                return Percent(self.go(operand, stack))
            case Binary(op=op, left=left, right=right):
                return self.binary(op, left, right, stack)
            case Call(name=name, args=args):
                return Call(name, tuple(self.go(arg, stack) for arg in args))

    def inline(self, name: str, stack: tuple[str, ...]) -> Expr:
        if name not in self.formulas or name in stack:
            raise _NotATable  # a stored column read outside a comparison, or a cycle
        try:
            return self.go(parse_formula(self.formulas[name]), (*stack, name))
        except FormulaSyntaxError:
            raise _NotATable from None

    def binary(self, op: str, left: Expr, right: Expr, stack: tuple[str, ...]) -> Expr:
        pair = (left, right) if isinstance(right, Text) else (right, left)
        match pair:
            case (Ref(name=name), Text(value=literal)) if (
                op in ("=", "<>") and name in self.choices and name not in self.formulas
            ):
                return self.compare(op, name, literal)
        return Binary(op, self.go(left, stack), self.go(right, stack))

    def compare(self, op: str, name: str, literal: str) -> Expr:
        if literal == "" or "'" in literal:
            # A blank would be a listed value, and a quote has no documented escape: the plain
            # translation refuses the latter by name.
            raise _NotATable
        key = literal.lower()
        self.uses.setdefault(name, {}).setdefault(key, literal)
        equal = self.picked is not None and self.picked[name] == key
        return Binary("=", Num(1), Num(int(equal == (op == "="))))


def tabulate[T: Coded](
    expr: Expr,
    formulas: Mapping[str, str],
    choices: frozenset[str],
    leaf: Callable[[Expr], T | None],
) -> tuple[str, list[T]] | None:
    """The table for `expr` and the translation of every leaf, or None when it does not qualify.

    `leaf` translates a formula that no longer reads any column; None from it declines the table.
    """
    survey = _Rewrite(formulas, choices, None)
    try:
        survey.go(expr, ())
    except _NotATable:
        return None
    domains = {name: [*uses, None] for name, uses in survey.uses.items()}
    if not domains or math.prod(map(len, domains.values())) > _MAX_LEAVES:
        return None
    leaves: dict[tuple[str | None, ...], T] = {}
    for combo in itertools.product(*domains.values()):
        picked = dict(zip(domains, combo, strict=True))
        found = leaf(_Rewrite(formulas, choices, picked).go(expr, ()))
        if found is None:
            return None
        leaves[combo] = found
    names = list(domains)

    def build(depth: int, chosen: tuple[str | None, ...]) -> str:
        if depth == len(names):
            return leaves[chosen].code
        name = names[depth]
        code = build(depth + 1, (*chosen, None))
        rest = {key: build(depth + 1, (*chosen, key)) for key in survey.uses[name]}
        if all(branch == code for branch in rest.values()):
            return code  # every class gives the same result, so the column does not matter here
        for key in reversed(rest):
            test = f"toLowerCase([${name}]) == toLowerCase({quoted(survey.uses[name][key])})"
            code = f"if({test}, {rest[key]}, {code})"
        return code

    return build(0, ()), list(leaves.values())

