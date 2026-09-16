"""Shared value expressions for SharePoint column formatters.

Operators follow Microsoft's formatting-syntax-reference. Live-confirmed on
2026-09-16: plain/prefixed values, exact text matching, blank/zero display,
and invalid numeric/date fallbacks passed the generated visual probes.
"""

from dataclasses import dataclass


def text_value(ref: str = "@currentField", *, calculated: bool = False) -> str:
    """Read text without removing a character from an unprefixed value."""
    text = f"toString({ref})"
    if not calculated:
        return text
    return (
        f"if(indexOf({text}, ';#') >= 0, "
        f"substring({text}, indexOf({text}, ';#') + 2, 1000), {text})"
    )


def quoted(value: str) -> str:
    """Quote a literal for SharePoint's Excel-style expression syntax."""
    return "'" + value.replace("'", "''") + "'"


def hide_blank(text: str, display: str = "flex") -> str:
    """Check text emptiness so numeric zero is not treated as blank."""
    return f"=if({text} == '', 'none', '{display}')"


@dataclass(frozen=True)
class ScalarValue:
    """Expressions for a numeric or date value and its display guards."""

    constructor: str
    ref: str = "@currentField"
    calculated: bool = False

    @property
    def text(self) -> str:
        return text_value(self.ref, calculated=self.calculated)

    @property
    def value(self) -> str:
        # Preserve native date objects; calculated dates need prefix removal.
        source = self.text if self.calculated else self.ref
        return f"{self.constructor}({source})"

    @property
    def valid(self) -> str:
        number = f"Number({self.value})" if self.constructor == "Date" else self.value
        # Subtracting itself rejects NaN and infinity using documented arithmetic.
        return f"({self.text} != '' && ({number} - {number}) == 0)"

    @property
    def label(self) -> str:
        display = f"toLocaleDateString({self.value})" if self.constructor == "Date" else self.value
        return f"=if({self.valid}, {display}, {self.text})"
