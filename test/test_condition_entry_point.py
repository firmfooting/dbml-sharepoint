# test/test_condition_entry_point.py
"""One entry point into condition validation, and the ratchet that keeps it.

`condition_findings` returns a classified `Finding` per problem;
`validate_condition` returned the same problems as bare prose, so every caller
that used it had to invent a code and a location for all ~28 of the grammar's
distinct rejections. There was exactly one such caller left, and the code it
invented was `invalid_condition`.

Both are gone. These gates fail if either comes back: a second entry point is
what let the two vocabularies exist side by side, and a generic code is what
a message-only return forces.
"""

import ast

from _paths import PACKAGE

from dbml_sharepoint.analysis.finding_help import RETIRED_FINDINGS

MODULE = "dbml_sharepoint.analysis.conditions"

#: Every package module that directly imports the classified entry point.
#: The roster is deliberate: adding another direct consumer requires review.
_INTENDED_CALLERS = frozenset({
    "analysis/forms.py",
    "analysis/checks/_formatting.py",
    "analysis/checks/_retirement.py",
    "analysis/checks/_views.py",
    "analysis/checks/_watched.py",
})


def _imported_names(relative: str, module: str) -> set[str]:
    """Names `relative` takes from `module` by a `from ... import` statement."""
    tree = ast.parse((PACKAGE / relative).read_text(encoding="utf-8"))
    return {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == module
        for alias in node.names
    }


def _callers_of(name: str) -> set[str]:
    """Package modules importing `name` from the conditions module."""
    return {
        path.relative_to(PACKAGE).as_posix()
        for path in PACKAGE.rglob("*.py")
        if name in _imported_names(path.relative_to(PACKAGE).as_posix(), MODULE)
    }


def test_direct_condition_entry_point_imports_match_the_roster() -> None:
    """Each listed file imports `condition_findings`, no other package module
    directly imports it, and the removed direct import cannot return."""
    assert _callers_of("condition_findings") == set(_INTENDED_CALLERS)


def test_the_retired_code_is_still_answerable() -> None:
    """`explain` documents a code as a stable identity, so a build older than
    this change printing `invalid_condition` must still get an answer rather
    than "no finding code", which reads as a typo."""
    assert "invalid_condition" in RETIRED_FINDINGS
