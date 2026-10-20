"""Which functions a header formula may call, and what a parsed formula uses."""

from dbml_sharepoint.analysis.formula.syntax import Binary, Call, Expr, Neg, Percent, Ref

# Each has an exact formatting equivalent (formatting syntax reference, Microsoft Learn). TRIM is
# absent: it also collapses inner runs of spaces and formatting has no trim operator.
# Name to (minimum, maximum) argument count; None means no maximum.
SUPPORTED: dict[str, tuple[int, int | None]] = {
    "IF": (2, 3),
    "AND": (1, None),
    "OR": (1, None),
    "NOT": (1, 1),
    "ISBLANK": (1, 1),
    "CHOOSE": (2, None),
    "MIN": (1, None),
    "MAX": (1, None),
    "ABS": (1, 1),
    "INT": (1, 1),
    "ROUND": (2, 2),
    "CONCATENATE": (1, None),
    "LEFT": (1, 2),
    "RIGHT": (1, 2),
    "MID": (3, 3),
    "LEN": (1, 1),
    "LOWER": (1, 1),
    "UPPER": (1, 1),
    "DATE": (3, 3),
    "YEAR": (1, 1),
    "MONTH": (1, 1),
    "DAY": (1, 1),
}

# Their value changes with no column changing, so a header could not match its column.
VOLATILE: frozenset[str] = frozenset({"TODAY", "NOW"})


def _children(expr: Expr) -> tuple[Expr, ...]:
    if isinstance(expr, Neg | Percent):
        return (expr.operand,)
    if isinstance(expr, Binary):
        return (expr.left, expr.right)
    if isinstance(expr, Call):
        return expr.args
    return ()


def function_names(expr: Expr) -> frozenset[str]:
    """Upper-cased names of every function the formula calls."""
    own = frozenset({expr.name}) if isinstance(expr, Call) else frozenset()
    return own.union(*(function_names(child) for child in _children(expr)))


def refs(expr: Expr) -> frozenset[str]:
    """Names of every column the formula references."""
    own = frozenset({expr.name}) if isinstance(expr, Ref) else frozenset()
    return own.union(*(refs(child) for child in _children(expr)))
