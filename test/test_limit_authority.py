"""Gates holding consumers to the named home of a fact.

`limits.py` and `typemap.py` each give a fact one home. Neither had anything
holding a consumer to it, and three failure modes followed: a literal that
bypasses the home, prose that restates the value, and a constant whose value
changes nothing observable.

`_structure.py:507` was all three at once. It compared against a bare 32 and
wrote "SP internal-name limit is 32." in its message, while `MAX_INTERNAL_NAME`
was read only by `validator.py`. Setting the constant to 33 made the two
enforcement sites disagree and no test saw it, which is the surviving mutant
recorded in the `limits.py` docstring.
"""

import ast
import re
from pathlib import Path

from _paths import PACKAGE, TEST_DIR

from dbml_sharepoint.analysis import limits

#: Words that turn a number in a message into a claim about a ceiling.
_CEILING_WORDS = ("limit", "max", "chars", "characters", "ceiling")

#: The string each typemap predicate owns, and the function that owns it.
#: Keyed by function name so moving a predicate keeps it exempt and copying
#: its body does not.
_PREDICATE_OWNERS = {
    "boolean": "is_boolean",
    "person": "is_person",
    "hyperlink": "is_hyperlink",
    "choice": "is_legacy_choice",
}

#: Constants no test names yet. A RATCHET: entries come out, and one going in
#: needs a reason in the pull request.
#:
#: This gate is the weakest of the four and is here because it costs nothing.
#: MEASURED before the #259 sweep: this same list was used to predict which
#: constants would survive mutation. Four of the seven were killed by tests
#: that exercise the boundary without naming the constant, and two constants
#: absent from it survived. Naming is a floor, not proof of enforcement.
NOT_YET_PINNED = frozenset({
    "LIST_VIEW_THRESHOLD",
    "MAX_DISPLAY_TITLE",
    "MAX_FIELD_DESCRIPTION",
    "MAX_TEXT_FIELD_LENGTH",
    "MAX_CALCULATED_FORMULA",
    "MAX_VALIDATION_MESSAGE",
    "MAX_VIEW_ROW_LIMIT",
    "LIST_VIEW_THRESHOLD_FALLBACK_ROWS",
})


def _limit_values() -> set[int]:
    """Every value `limits.py` names, read from the module rather than copied."""
    return {
        value for name, value in vars(limits).items()
        if name.isupper() and isinstance(value, int) and not isinstance(value, bool)
    }


def _limit_names() -> list[str]:
    """Every constant `limits.py` names."""
    return sorted(
        name for name, value in vars(limits).items()
        if name.isupper() and isinstance(value, int) and not isinstance(value, bool)
    )


def _src_modules() -> list[Path]:
    """Every package module except the home itself."""
    return [p for p in sorted(PACKAGE.rglob("*.py")) if p.name != "limits.py"]


def _string_parts(node: ast.expr) -> str:
    """The literal text of a string or f-string, ignoring interpolations.

    Joined so a message wrapped across three physical lines is searched as one
    sentence. A line-by-line scan missed the `_structure.py` message for
    exactly that reason.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            part.value for part in node.values
            if isinstance(part, ast.Constant) and isinstance(part.value, str)
        )
    return ""


def _states_value(text: str, value: int) -> bool:
    """Whether `text` contains `value` as a standalone number."""
    return re.search(rf"(?<!\d){value}(?!\d)", text) is not None


def _offending_literals(path: Path, values: set[int]) -> list[str]:
    """Comparisons against a decimal literal equal to a named limit.

    Comparisons only, and decimal only. `0x20` and `32` are the same value and
    different facts: the permission bitmasks, a `>> 32` shift and a
    control-character test all hold 32 and none of them is a ceiling.
    """
    source = path.read_text(encoding="utf-8")
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Compare):
            continue
        for side in [node.left, *node.comparators]:
            if not isinstance(side, ast.Constant) or isinstance(side.value, bool):
                continue
            if not isinstance(side.value, int) or side.value not in values:
                continue
            if (ast.get_source_segment(source, side) or "").lower().startswith("0x"):
                continue
            offenders.append(
                f"{path.name}:{side.lineno}: compares against {side.value}, "
                f"which limits.py names"
            )
    return offenders


def _offending_messages(path: Path, values: set[int]) -> list[str]:
    """Messages stating a limit value instead of interpolating it."""
    offenders: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        text = " ".join(_string_parts(arg) for arg in node.args)
        if not any(word in text.lower() for word in _CEILING_WORDS):
            continue
        for value in values:
            # Digit boundaries only. A lookahead excluding "." made a value
            # ending a sentence invisible, and the scan reported zero twice.
            if _states_value(text, value):
                offenders.append(
                    f"{path.name}:{node.lineno}: message states {value} "
                    f"instead of interpolating the constant"
                )
                break
    return offenders


def _offending_vocabulary(path: Path) -> list[str]:
    """Comparisons against a type string a predicate already owns."""
    offenders: list[str] = []
    for func in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(func, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Compare):
                continue
            for side in [node.left, *node.comparators]:
                if not isinstance(side, ast.Constant) or not isinstance(side.value, str):
                    continue
                owner = _PREDICATE_OWNERS.get(side.value)
                if owner is None or owner == func.name:
                    continue
                offenders.append(
                    f"{path.name}:{side.lineno}: {func.name} compares against "
                    f"{side.value!r}; call {owner}() instead"
                )
    return offenders


def test_no_comparison_uses_a_bare_limit_value() -> None:
    """A ceiling enforced by a literal is a second copy of the number."""
    modules = _src_modules()
    assert len(modules) > 30, f"only {len(modules)} modules scanned, so this pins nothing"

    values = _limit_values()
    offenders = [
        line for path in modules for line in _offending_literals(path, values)
    ]
    assert not offenders, (
        "Comparisons against a bare limit value. Import the constant from "
        "`analysis.limits` instead:\n" + "\n".join(offenders)
    )


def test_no_message_states_a_limit_value() -> None:
    """The sentence an operator reads and the check must be one number."""
    modules = _src_modules()
    assert len(modules) > 30, f"only {len(modules)} modules scanned, so this pins nothing"

    values = _limit_values()
    offenders = [
        line for path in modules for line in _offending_messages(path, values)
    ]
    assert not offenders, (
        "Messages stating a limit value. Interpolate the constant so the "
        "sentence cannot disagree with the check:\n" + "\n".join(offenders)
    )


def test_a_hex_literal_of_the_same_value_is_not_reported(tmp_path: Path) -> None:
    """`0x20` and `32` are one value and two facts.

    Without the spelling test this gate reports the permission bitmasks, a
    shift and a control-character test, none of which is a ceiling.
    """
    seeded = tmp_path / "m.py"
    seeded.write_text(
        "if flags > 0x20:\n    pass\nif len(n) > 32:\n    pass\n",
        encoding="utf-8", newline="\n",
    )

    found = _offending_literals(seeded, {32})
    assert len(found) == 1, found
    assert ":3:" in found[0]


def test_a_wrapped_message_ending_in_a_value_is_reported(tmp_path: Path) -> None:
    """Both ways the first two attempts at this scan failed.

    The f-string wraps across lines, and the number ends the sentence.
    """
    seeded = tmp_path / "m.py"
    seeded.write_text(
        'Finding(\n'
        '    CODE,\n'
        '    f"name is {n} chars; "\n'
        '    f"SP internal-name limit is 32.",\n'
        ')\n',
        encoding="utf-8", newline="\n",
    )

    found = _offending_messages(seeded, {32})
    assert len(found) == 1, found


def test_no_module_bypasses_a_predicate_it_owns() -> None:
    """Closes #251. A hand-rolled comparison is where a vocabulary diverges."""
    modules = _src_modules()
    assert len(modules) > 30, f"only {len(modules)} modules scanned, so this pins nothing"

    offenders = [line for path in modules for line in _offending_vocabulary(path)]
    assert not offenders, (
        "Comparisons against a type string typemap owns:\n" + "\n".join(offenders)
    )


def test_the_predicate_body_is_the_one_place_the_string_may_appear(
    tmp_path: Path,
) -> None:
    """The exemption is the rule, not a loophole.

    A gate without it reports the four predicate definitions themselves.
    """
    seeded = tmp_path / "m.py"
    seeded.write_text(
        'def is_boolean(t):\n'
        '    return t == "boolean"\n'
        'def other(t):\n'
        '    return t == "boolean"\n',
        encoding="utf-8", newline="\n",
    )

    found = _offending_vocabulary(seeded)
    assert len(found) == 1, found
    assert "other" in found[0]


def test_every_limit_is_named_by_a_test_or_ratcheted() -> None:
    """A new ceiling with no test at all is what this catches."""
    corpus = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(TEST_DIR.rglob("test_*.py"))
        if p.name != "test_limit_authority.py"
    )
    assert len(corpus) > 100_000, "the test corpus did not load, so this pins nothing"

    names = _limit_names()
    assert names, "no limits were found, so this pins nothing"
    unnamed = {name for name in names if name not in corpus}

    assert unnamed <= NOT_YET_PINNED, (
        "A limit is named by no test and is not on the ratchet: "
        f"{sorted(unnamed - NOT_YET_PINNED)}"
    )
    assert set(names) >= NOT_YET_PINNED, (
        "The ratchet names a constant that no longer exists: "
        f"{sorted(NOT_YET_PINNED - set(names))}"
    )
    stale = NOT_YET_PINNED - unnamed
    assert not stale, (
        f"These are now named by a test; remove them from the ratchet: {sorted(stale)}"
    )
