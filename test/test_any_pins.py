"""Pins the untyped-escape-hatch count per unit that has not been cleaned yet.

A unit listed in `PINS` may not gain uses of the escape hatch; every other
Python file under the package, `test`, `scripts` and `website/scripts` may hold none, so
cleaned code cannot regress even if the pyrefly sub-config for it is mis-set.
"""

import io
import re
import tokenize
from pathlib import Path

import pytest
from _paths import REPO_ROOT

# Spelled in pieces so this file does not count itself as a use.
NAME = "An" + "y"
_ANNOTATION = re.compile(rf"[\w.\[\], |]*\b{NAME}\b[\w.\[\], |]*")

PINS: dict[str, int] = {
    "src/dbml_sharepoint/generators": 71,
    "src/dbml_sharepoint/model": 159,
    "test runtime": 616,
    "test other": 248,
    "scripts": 0,
    "website/scripts": 0,
}

_PACKAGE = REPO_ROOT / "src" / "dbml_sharepoint"
_ROOTS = (_PACKAGE, REPO_ROOT / "test", REPO_ROOT / "scripts", REPO_ROOT / "website" / "scripts")


def count_uses(source: str) -> int:
    """Name tokens and annotation-shaped strings spelling the escape hatch."""
    total = 0
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type == tokenize.NAME and token.string == NAME:
            total += 1
        elif token.type == tokenize.STRING:
            body = token.string.strip("rbuRBUfF").strip("\"'")
            if not re.search(r"\w \w", body) and _ANNOTATION.fullmatch(body):
                total += 1
    return total


def unit_of(path: Path) -> str | None:
    """The pinned unit owning ``path``, or None when the unit is cleaned."""
    rel = path.relative_to(REPO_ROOT).as_posix()
    for unit in ("src/dbml_sharepoint/generators", "src/dbml_sharepoint/model"):
        if rel.startswith(unit + "/"):
            return unit
    if rel.startswith("test/"):
        return "test runtime" if re.fullmatch(r"test_.*_runtime\.py", path.name) else "test other"
    if rel.startswith("website/scripts/"):
        return "website/scripts"
    if rel.startswith("scripts/"):
        return "scripts"
    return None


def _counts() -> tuple[dict[str, int], dict[str, int]]:
    pinned = dict.fromkeys(PINS, 0)
    cleaned: dict[str, int] = {}
    for root in _ROOTS:
        for path in sorted(root.rglob("*.py")):
            uses = count_uses(path.read_text(encoding="utf-8"))
            unit = unit_of(path)
            if unit is None:
                if uses:
                    cleaned[path.relative_to(REPO_ROOT).as_posix()] = uses
            else:
                pinned[unit] += uses
    return pinned, cleaned


def test_pinned_units_do_not_gain_uses() -> None:
    pinned, _ = _counts()
    over = {unit: (n, PINS[unit]) for unit, n in pinned.items() if n > PINS[unit]}
    assert not over, f"{NAME} went up (found, pinned): {over}. Replace it with a real type."
    under = {unit: (n, PINS[unit]) for unit, n in pinned.items() if n < PINS[unit]}
    assert not under, f"Lower the pin in PINS to the cleaned count (found, pinned): {under}"


def test_cleaned_units_hold_none() -> None:
    _, cleaned = _counts()
    assert not cleaned, f"{NAME} in a cleaned unit (file: count): {cleaned}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x: A" + "ny = 1\n", 1),
        ("# A" + "ny comment\n'''A" + "ny prose here'''\n", 0),
        ("y = cast(\"dict[str, A" + "ny]\", z)\n", 1),
    ],
)
def test_count_uses(source: str, expected: int) -> None:
    assert count_uses(source) == expected


def test_unit_of_routes_paths() -> None:
    assert unit_of(REPO_ROOT / "test" / "test_x_runtime.py") == "test runtime"
    assert unit_of(REPO_ROOT / "test" / "test_x.py") == "test other"
    assert unit_of(_PACKAGE / "model" / "a.py") == "src/dbml_sharepoint/model"
    assert unit_of(_PACKAGE / "analysis" / "a.py") is None
