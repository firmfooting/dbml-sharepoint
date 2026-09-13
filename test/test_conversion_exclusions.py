"""One gate: every site `_conversion_exclusions.md` names still exists.

That document is consulted before converting any test input to the `_packs`
helpers, and each entry is there because a mechanical conversion would change
the input silently while the test kept passing. A row pointing at a module or
a function that has moved is worse than no row: the contributor looks, finds
nothing, and converts the thing the row existed to protect.

It rots the way documents that nothing reads always rot. Splitting
`test_jsgen.py` into eight modules moved three of the sites it names and the
table went on naming the old file, which is what this test now catches. The
document says it is anchored on test function names rather than line numbers
because the line numbers had already drifted once before the list was first
used; anchoring is necessary and was not sufficient.
"""

import ast
import re

from _paths import TEST_DIR

EXCLUSIONS = TEST_DIR / "_conversion_exclusions.md"

#: A table row, captured with its middle cell RAW. Matching the cell as a
#: name here would skip every row it did not fit, which is how an unresolved
#: row hides from the test meant to catch it.
ROW = re.compile(r"^\| `(test_[a-z_0-9]+\.py)` \| (.+?) \|")

#: A middle cell that is a name: the table spells one in backticks.
NAME_CELL = re.compile(r"^`([A-Za-z_][A-Za-z0-9_]*)`$")

#: Rows whose middle cell is prose rather than a name, so there is nothing to
#: resolve. Spelled out so a new one has to be added deliberately.
PROSE_CELLS = ("(cross-site test)", "(second malformed-schema test)")


def _top_level_names(source: str) -> set[str]:
    """Functions and module-level assignments defined in one test module."""
    tree = ast.parse(source)
    names = {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names |= {t.id for t in node.targets if isinstance(t, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_every_excluded_site_still_resolves() -> None:
    """Each row names something real, or prose this test already knows about.

    Every row is parsed, including the ones whose middle cell is prose. A
    parser that matched only name cells would skip an unresolvable row rather
    than fail on it, and skipping is the behaviour this whole module exists
    to prevent.
    """
    rows = [ROW.match(line) for line in EXCLUSIONS.read_text(encoding="utf-8").splitlines()]
    sites = [m.groups() for m in rows if m]
    assert len(sites) >= 18, (
        f"only {len(sites)} rows parsed out of the exclusion tables, so this "
        "test is pinning almost nothing. The table format has probably changed."
    )

    missing = []
    for module, cell in sites:
        path = TEST_DIR / module
        named = NAME_CELL.match(cell)
        if not path.exists():
            missing.append(f"{module} does not exist")
        elif named is None:
            if cell not in PROSE_CELLS:
                missing.append(
                    f"{module} row has the unlisted prose cell {cell!r}, which "
                    "names no function. Give it the function name, or add the "
                    "cell to PROSE_CELLS so the exception is deliberate",
                )
        # Explicit encoding: the platform default is cp1252 on Windows,
        # and a test module carrying one byte outside it fails to decode.
        elif named.group(1) not in _top_level_names(
            path.read_text(encoding="utf-8"),
        ):
            missing.append(f"{module} defines no {named.group(1)}")
    assert not missing, (
        "_conversion_exclusions.md points at sites that have moved: "
        + "; ".join(missing)
        + ". Update the table rather than deleting the row: the exclusion is "
        "still real, it just lives somewhere else now."
    )


def test_every_module_named_in_the_prose_sections_exists() -> None:
    """Sections C to F name whole modules rather than functions."""
    named = set(re.findall(r"`(test_[a-z_0-9]+\.py)`", EXCLUSIONS.read_text(encoding="utf-8")))
    assert len(named) >= 16, f"only {len(named)} modules named, expected the suite"
    absent = sorted(m for m in named if not (TEST_DIR / m).exists())
    assert not absent, f"_conversion_exclusions.md names modules that are gone: {absent}"
