# src/dbml_sharepoint/analysis/column_refs.py
"""Column names written inside a calculated formula or a formatter JSON.

Read by rule modules under `analysis/checks/` and by `generators/jsgen.py`,
which orders Phase-1 field creation by a formula's references, so it lives
outside both packages. It is not named
`references.py`, because a ref in this codebase is already a DBML foreign
key.

Nothing here may import from `analysis/checks/` or `analysis/validator.py`,
or the cycle this module exists to close would move rather than close.
"""

import re

_FORMULA_STRING_LITERAL = re.compile(r'"[^"]*"')
FORMULA_COLUMN_REF = re.compile(r"\[([^\[\]]+)\]")

# Formatter JSON `[$Field]` references (column/view/form formatting). SP
# resolves these against INTERNAL names at runtime.
_FORMATTER_FIELD_REF = re.compile(r"\[\$([A-Za-z0-9_]+)")


def formatter_field_refs(node: object) -> frozenset[str]:
    """Every `[$Field]` reference in a formatter JSON structure, walking
    nested dicts/lists and scanning every string value."""
    refs: set[str] = set()

    def _walk(value: object) -> None:
        if isinstance(value, str):
            refs.update(_FORMATTER_FIELD_REF.findall(value))
        elif isinstance(value, dict):
            for child in value.values():
                _walk(child)
        elif isinstance(value, list):
            for child in value:
                _walk(child)

    _walk(node)
    return frozenset(refs)


def formula_column_refs(formula: str) -> frozenset[str]:
    """Column names referenced as ``[Name]`` in a calculated formula.

    String literals are stripped first so bracket text inside a quoted
    constant is not misread as a reference. Shared with jsgen, which orders
    Phase-1 field creation by these references."""
    return frozenset(
        FORMULA_COLUMN_REF.findall(_FORMULA_STRING_LITERAL.sub("", formula)),
    )


# SP formula string literals use Excel-style "" escaping; odd split indices
# are literal tokens and pass through any rewrite untouched.
_FORMULA_LITERAL_SPLIT = re.compile(r'("(?:""|[^"])*")')


def rewrite_formula_refs(formula: str, rename: dict[str, str]) -> str:
    """Rewrite a calculated formula's ``[Name]`` references through `rename`.

    SharePoint resolves calculated-formula column references against DISPLAY
    names when the formula is written, so once fields are renamed a formula
    authored with internal names would fail to create. Authors keep writing
    internal names; the build translates on the way out, and the extractor
    translates back on the way in. One function, because the two directions
    have to agree about what a reference is and where a string literal
    begins; two copies would be free to disagree in the one direction
    nothing re-reads. String literals are data and are never rewritten.
    """

    def _replace(match: "re.Match[str]") -> str:
        name = match.group(1)
        return f"[{rename.get(name, name)}]"

    return "".join(
        part if index % 2 == 1 else FORMULA_COLUMN_REF.sub(_replace, part)
        for index, part in enumerate(_FORMULA_LITERAL_SPLIT.split(formula))
    )
