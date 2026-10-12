"""Pins the untyped-escape-hatch count per unit that has not been cleaned yet.

A unit listed in `PINS` may not gain uses of the escape hatch. A count below the
pin is only a printed note, so concurrent pull requests that clean it do not
serialise on one pin line; the stage that cleans the unit lowers the pin. Every other
Python file under the package, `test`, `scripts` and `website/scripts` may hold none, so
cleaned code cannot regress even if the pyrefly sub-config for it is mis-set.
"""

import io
import re
import sys
import tokenize
from pathlib import Path

import pytest
from _paths import REPO_ROOT

# Spelled in pieces so this file does not count itself as a use.
NAME = "An" + "y"
_TYPE_COMMENT = re.compile(r"#\s*type:")
_ANNOTATION = re.compile(rf"[\w.\[\], |]*\b{NAME}\b[\w.\[\], |]*")

PINS: dict[str, int] = {
    "test runtime": 614,
    "test other": 217,
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
        elif token.type == tokenize.COMMENT and _TYPE_COMMENT.match(token.string):
            total += len(re.findall(rf"\b{NAME}\b", token.string))
        elif token.type == tokenize.STRING:
            body = token.string.strip("rbuRBUfF").strip("\"'")
            if not re.search(r"\w \w", body) and _ANNOTATION.fullmatch(body):
                total += 1
    return total


def unit_of(path: Path) -> str | None:
    """The pinned unit owning ``path``, or None when the unit is cleaned."""
    rel = path.relative_to(REPO_ROOT).as_posix()
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


def over_and_under(
    pinned: dict[str, int], pins: dict[str, int],
) -> tuple[dict[str, tuple[int, int]], dict[str, tuple[int, int]]]:
    """Units above and below their pin, each as ``{unit: (found, pinned)}``."""
    over = {unit: (n, pins[unit]) for unit, n in pinned.items() if n > pins[unit]}
    under = {unit: (n, pins[unit]) for unit, n in pinned.items() if n < pins[unit]}
    return over, under


def test_pinned_units_do_not_gain_uses() -> None:
    pinned, _ = _counts()
    over, under = over_and_under(pinned, PINS)
    for unit, (found, pin) in under.items():
        sys.stdout.write(f"NOTE: lower the pin for {unit} from {pin} to {found}\n")
    assert not over, f"{NAME} went up (found, pinned): {over}. Replace it with a real type."


def test_over_fails_and_under_is_only_reported() -> None:
    over, under = over_and_under({"a": 3, "b": 1, "c": 2}, {"a": 2, "b": 2, "c": 2})
    assert over == {"a": (3, 2)}
    assert under == {"b": (1, 2)}
    assert over_and_under({"b": 1}, {"b": 2})[0] == {}


def test_cleaned_units_hold_none() -> None:
    _, cleaned = _counts()
    assert not cleaned, f"{NAME} in a cleaned unit (file: count): {cleaned}"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("x: A" + "ny = 1\n", 1),
        ("# A" + "ny comment\n'''A" + "ny prose here'''\n", 0),
        ("y = cast(\"dict[str, A" + "ny]\", z)\n", 1),
        ("x = []  # type: list[A" + "ny]\n", 1),
        ("x = []  # type: ignore[misc]\n", 0),
        ("x = 1  # not a type: A" + "ny\n", 0),
    ],
)
def test_count_uses(source: str, expected: int) -> None:
    assert count_uses(source) == expected


def test_unit_of_routes_paths() -> None:
    assert unit_of(REPO_ROOT / "test" / "test_x_runtime.py") == "test runtime"
    assert unit_of(REPO_ROOT / "test" / "test_x.py") == "test other"
    assert unit_of(_PACKAGE / "model" / "a.py") is None
    assert unit_of(_PACKAGE / "analysis" / "a.py") is None


def test_a_type_comment_counts_and_fails_in_a_cleaned_unit_and_ratchets_in_a_pinned_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "repo"
    cleaned = root / "src" / "dbml_sharepoint" / "analysis"
    pinned = root / "test"
    for directory, name in ((cleaned, "m.py"), (pinned, "test_m.py")):
        directory.mkdir(parents=True)
        (directory / name).write_text(f"x = []  # type: list[{NAME}]\n", encoding="utf-8")
    monkeypatch.setattr(sys.modules[__name__], "REPO_ROOT", root)
    monkeypatch.setattr(sys.modules[__name__], "_ROOTS", (root / "src" / "dbml_sharepoint", pinned))

    found_pinned, found_cleaned = _counts()

    assert found_cleaned == {"src/dbml_sharepoint/analysis/m.py": 1}
    assert found_pinned["test other"] == 1
    monkeypatch.setitem(PINS, "test other", 0)
    with pytest.raises(AssertionError, match="went up"):
        test_pinned_units_do_not_gain_uses()
