# src/dbml_sharepoint/analysis/condition_description.py
"""How a condition tree reads in prose, for the manifest and the reporting pack.

Split out of `analysis/conditions.py` (#168), which is normalisation,
validation and three SharePoint renderings in one 1,900-line module. This
concern shares none of that: no target, no capability table, no finding, no
column type. It is a pure recursive walk over the authored tree.

The split is worth having because of who calls it. `generators.manifestgen` and
`generators.reportgen` want one sentence per rule, and importing `describe`
used to pull in the whole validation stack, including the finding vocabulary a
generator has no business with. So the dependency here is the grammar's own
types and nothing else, and `test_condition_description.py` gates that by
importing this module in a fresh interpreter and reading back what got loaded.

BREAKING API MOVE (#168): the canonical import is now
`dbml_sharepoint.analysis.condition_description.describe`, not
`dbml_sharepoint.analysis.conditions.describe`. There is deliberately no
compatibility re-export: this package gives each public name one importable
home, and keeping the old path would recreate the shim the architecture work
is removing.

`VALUELESS_OPS` comes from `model.conditions` rather than being restated here.
A private copy would agree with the renderers' copy right up until somebody
edited one of them, and the disagreement would show as a manifest line printing
`None` after an operator that never had a value.
"""

from dbml_sharepoint.model.conditions import VALUELESS_OPS, Condition, Leaf

#: The word each group kind reads as. `none_of` joins with OR because `describe`
#: wraps the result in NOT, and NOT(A OR B) is what none_of means.
_JOINERS: dict[str, str] = {"all_of": " AND ", "any_of": " OR ", "none_of": " OR "}


def describe(node: Condition) -> str:
    """A human-readable summary for manifests and documentation.

    Deliberately not any target's syntax: an operator reads as its declared
    name, so an operator a reader does not recognise sends them to the
    grammar reference rather than to a SharePoint dialect they would then
    have to identify.
    """
    if isinstance(node, Leaf):
        subject = f"{node.field}.{node.property}" if node.property else node.field
        if node.measure:
            subject = f"{node.measure}({subject})"
        if node.op in VALUELESS_OPS:
            return f"{subject} {node.op}"
        return f"{subject} {node.op} {node.value!r}"
    inner = _JOINERS[node.kind].join(describe(child) for child in node.children)
    if node.kind == "none_of":
        # NOT must survive a single child: `none_of[A]` is the canonical
        # implication idiom, and dropping the negation made the manifest
        # state the opposite of the rule it described.
        return f"NOT({inner})"
    return inner if len(node.children) == 1 else f"({inner})"
