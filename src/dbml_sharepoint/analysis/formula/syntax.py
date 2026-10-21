"""Nodes of a parsed calculated-column formula."""

from dataclasses import dataclass
from typing import Literal

ColumnKind = Literal["text", "number", "date", "choice"]


class FormulaSyntaxError(ValueError):
    """A formula that does not parse; `position` is a 0-based offset into it."""

    def __init__(self, message: str, position: int) -> None:
        super().__init__(f"{message} (at position {position})")
        self.position = position


@dataclass(frozen=True, slots=True)
class Num:
    value: float


@dataclass(frozen=True, slots=True)
class Text:
    value: str


@dataclass(frozen=True, slots=True)
class Ref:
    name: str


@dataclass(frozen=True, slots=True)
class Neg:
    operand: "Expr"


@dataclass(frozen=True, slots=True)
class Percent:
    operand: "Expr"


@dataclass(frozen=True, slots=True)
class Binary:
    op: str
    left: "Expr"
    right: "Expr"


@dataclass(frozen=True, slots=True)
class Call:
    name: str
    args: tuple["Expr", ...]


type Expr = Num | Text | Ref | Neg | Percent | Binary | Call
