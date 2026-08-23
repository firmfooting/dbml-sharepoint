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

from dbml_sharepoint.analysis import conditions
from dbml_sharepoint.analysis.finding_help import FINDING_HELP, RETIRED_FINDINGS
from dbml_sharepoint.analysis.findings import FindingCode

MODULE = "dbml_sharepoint.analysis.conditions"

#: Every package module that directly imports the classified entry point.
#: The roster is deliberate: adding another direct consumer requires review.
_INTENDED_CALLERS = frozenset({
    "analysis/forms.py",
    "analysis/checks/_formatting.py",
    "analysis/checks/_retirement.py",
    "analysis/checks/_views.py",
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


def test_the_message_only_entry_point_is_gone() -> None:
    """Deleted rather than deprecated. A wrapper left in place is a wrapper
    the next caller reaches for, and its whole behaviour was to drop the code
    and the location on the floor."""
    assert not hasattr(conditions, "validate_condition")


def test_direct_condition_entry_point_imports_match_the_roster() -> None:
    """Each listed file imports `condition_findings`, no other package module
    directly imports it, and the removed direct import cannot return."""
    assert _callers_of("condition_findings") == set(_INTENDED_CALLERS)
    assert _callers_of("validate_condition") == set()


def test_the_generic_condition_code_is_gone() -> None:
    """`invalid_condition` existed only because a message-only return had no
    code to carry. With the caller repointed nothing constructs it, and a
    declared code nothing constructs fails the reachability gate."""
    assert "INVALID_CONDITION" not in FindingCode.__members__
    assert "invalid_condition" not in {str(code) for code in FindingCode}
    assert "invalid_condition" not in {str(code) for code in FINDING_HELP}


def test_the_retired_code_is_still_answerable() -> None:
    """`explain` documents a code as a stable identity, so a build older than
    this change printing `invalid_condition` must still get an answer rather
    than "no finding code", which reads as a typo."""
    assert "invalid_condition" in RETIRED_FINDINGS
