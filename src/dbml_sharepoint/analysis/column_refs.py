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
