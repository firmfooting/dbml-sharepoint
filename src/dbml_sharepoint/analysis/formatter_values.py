"""Shared value expressions for SharePoint column formatters.

Operators follow Microsoft's formatting-syntax-reference. Live-confirmed on
2026-09-16: constant plain/prefixed values in calculated styles, exact text
matching, blank/zero display and invalid numeric/date fallbacks passed the
generated visual probes. Native date fields retain their direct-value path.
"""

from dataclasses import dataclass


def text_value(ref: str = "@currentField", *, calculated: bool = False) -> str:
    """Read text without removing a character from an unprefixed value."""
    text = f"toString({ref})"
    if not calculated:
        return text
    # These prefixes are the supported calculated-value wire forms.
    prefix = " || ".join(
        f"indexOf({text}, '{kind};#') == 0"
        for kind in ("string", "float", "number", "datetime")
    )
    return (
        f"if({prefix}, "
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
    def _native_date(self) -> bool:
        return self.constructor == "Date" and not self.calculated

    @property
    def value(self) -> str:
        # Native dates already have the type used by comparisons and locale display.
        if self._native_date:
            return self.ref
        source = self.text if self.calculated else self.ref
        return f"{self.constructor}({source})"

    @property
    def valid(self) -> str:
        if self._native_date:
            return f"({self.ref} != '')"
        number = f"Number({self.value})" if self.constructor == "Date" else self.value
        # Subtracting itself rejects NaN and infinity using documented arithmetic.
        return f"({self.text} != '' && ({number} - {number}) == 0)"

    @property
    def label(self) -> str:
        display = f"toLocaleDateString({self.value})" if self.constructor == "Date" else self.value
        return f"=if({self.valid}, {display}, {self.text})"
