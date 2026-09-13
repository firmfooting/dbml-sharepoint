"""Inspect a condition tree, for tests asserting on its shape.

`test_conditions.py` and `test_conditions_properties.py` each carried their own
`_kinds`, written from opposite sides (one recursed on `Group`, the other
returned early on `Leaf`) and returning the same list either way (#172). Two
copies of one fact is how they come to disagree: the property test generates
trees the example test never writes, so a divergence would show up as a
hypothesis counterexample against a helper rather than against the normaliser
it is meant to be testing.

Named for its subject the way `_findings.py` is, and separate from `_model.py`,
which builds domain objects rather than asking questions about them.
"""

from dbml_sharepoint.model.conditions import Condition, Group


def kinds(node: Condition) -> list[str]:
    """Every group kind in `node`, outermost first, depth-first.

    Leaves contribute nothing: the normaliser's contract is about which
    GROUPS survive it, and `none_of` never being one of them is what both
    call sites assert.
    """
    if not isinstance(node, Group):
        return []
    return [node.kind, *(k for child in node.children for k in kinds(child))]
