# src/dbml_sharepoint/model/_keys.py
"""The unknown-key guard, shared by every parser in this package.

Lives alone so the parsers and the retirement fold can both apply it
without importing each other.
"""

from typing import Any


def _reject_unknown_keys(block: Any, allowed: frozenset[str] | set[str], context: str) -> None:
    """Fail on any key the loader does not read.

    Apply this at EVERY nesting level, not just the top. A fail-open level
    makes a typo'd build byte-identical to one with the key deleted, so
    `deafult:` never makes a view the default, a filter under `wheres:`
    deploys an unfiltered view, and a misspelled `break_inheritance` leaves
    a list on inherited permissions — all reporting zero findings.
    """
    if not isinstance(block, dict):
        raise ValueError(
            f"{context}: expected a mapping, got {type(block).__name__}",
        )
    unknown = set(block) - set(allowed)
    if unknown:
        raise ValueError(
            f"{context}: unknown key(s) {sorted(unknown)} "
            f"(known: {sorted(allowed)})",
        )
