"""Precedence-climbing parser for SharePoint calculated-column formulas.

Literal and reference rules match `analysis/column_refs.py`: `""` escapes a
quote inside a string literal and a reference is `[Name]` with no brackets
inside the name.
"""

import re

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

_TOKEN = re.compile(
    r"""
    (?P<num>\d+\.?\d*|\.\d+)
  | (?P<text>"(?:""|[^"])*")
  | (?P<ref>\[[^\[\]]+\])
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op><=|>=|<>|[-+*/^&=<>%(),])
    """,
    re.VERBOSE,
)

# Binary operators from loosest to tightest; all are left-associative.
_LEVELS: tuple[frozenset[str], ...] = (
    frozenset({"=", "<>", "<", ">", "<=", ">="}),
    frozenset({"&"}),
    frozenset({"+", "-"}),
    frozenset({"*", "/"}),
    frozenset({"^"}),
)

type _Token = tuple[str, str, int]


def _tokens(text: str, start: int) -> list[_Token]:
    found: list[_Token] = []
    pos = start
    while True:
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text):
            return found
        match = _TOKEN.match(text, pos)
        if match is None or match.lastgroup is None:
            raise FormulaSyntaxError(f"unexpected character {text[pos]!r}", pos)
        found.append((match.lastgroup, match.group(), pos))
        pos = match.end()


class _Parser:
    def __init__(self, text: str, start: int) -> None:
        self.tokens = _tokens(text, start)
        self.end = len(text)
        self.index = 0

    def peek(self) -> _Token | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def take(self) -> _Token:
        token = self.peek()
        if token is None:
            raise FormulaSyntaxError("unexpected end of formula", self.end)
        self.index += 1
        return token

    def at_op(self, *ops: str) -> bool:
        token = self.peek()
        return token is not None and token[0] == "op" and token[1] in ops

    def close(self, opened_at: int) -> None:
        if not self.at_op(")"):
            raise FormulaSyntaxError("missing ')' for the '(' opened here", opened_at)
        self.index += 1

    def binary(self, level: int) -> Expr:
        if level == len(_LEVELS):
            return self.prefix()
        left = self.binary(level + 1)
        while (token := self.peek()) and token[0] == "op" and token[1] in _LEVELS[level]:
            self.index += 1
            left = Binary(token[1], left, self.binary(level + 1))
        return left

    def prefix(self) -> Expr:
        # Negation sits above % and ^ in the Excel table, so -2^2 is (-2)^2 and -5% is (-5)%.
        signs: list[str] = []
        while self.at_op("-", "+"):
            signs.append(self.take()[1])
        node = self.primary()
        for sign in reversed(signs):
            node = Neg(node) if sign == "-" else node
        while self.at_op("%"):
            self.index += 1
            node = Percent(node)
        return node

    def primary(self) -> Expr:
        kind, value, pos = self.take()
        if kind == "num":
            return Num(float(value))
        if kind == "text":
            return Text(value[1:-1].replace('""', '"'))
        if kind == "ref":
            return Ref(value[1:-1])
        if kind == "name":
            if not self.at_op("("):
                raise FormulaSyntaxError(
                    f"{value!r} is neither a function call nor a [column] reference", pos
                )
            return self.call(value.upper())
        if value == "(":
            inner = self.binary(0)
            self.close(pos)
            return inner
        raise FormulaSyntaxError(f"unexpected {value!r}", pos)

    def call(self, name: str) -> Expr:
        opened_at = self.take()[2]
        args: list[Expr] = []
        if not self.at_op(")"):
            args.append(self.binary(0))
            while self.at_op(","):
                self.index += 1
                args.append(self.binary(0))
        self.close(opened_at)
        return Call(name, tuple(args))


def parse_formula(text: str) -> Expr:
    """Parse a calculated formula; the leading ``=`` is optional."""
    start = len(text) - len(text.lstrip())
    if text.startswith("=", start):
        start += 1
    parser = _Parser(text, start)
    expr = parser.binary(0)
    if (extra := parser.peek()) is not None:
        raise FormulaSyntaxError(f"unexpected {extra[1]!r}", extra[2])
    return expr
