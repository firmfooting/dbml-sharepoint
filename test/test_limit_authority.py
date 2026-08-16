"""Gates holding consumers to the module that declares a fact.

`limits.py` and `typemap.py` each declare a fact once. Neither had anything
holding a consumer to that declaration, and three failure modes followed: a
literal that bypasses it, prose that restates the value, and a constant whose
value changes nothing observable.

`_structure.py:507` was all three at once. It compared against a bare 32 and
wrote "SP internal-name limit is 32." in its message, while `MAX_INTERNAL_NAME`
was read only by `validator.py`. Setting the constant to 33 made the two
enforcement sites disagree and no test saw it, which is the surviving mutant
recorded in the `limits.py` docstring.

These gates read `limits.py` as it stands on disk, so `scripts/mutate_limits.py`
deselects this module. Under a mutant they search for the mutated number, and a
kill would say nothing about whether anything enforces it.
"""

import ast
import re
from collections.abc import Iterator
from pathlib import Path

from _paths import PACKAGE, TEST_DIR

from dbml_sharepoint.analysis import limits

#: Words that turn a number in a message into a claim about a ceiling.
_CEILING_WORDS = ("limit", "max", "chars", "characters", "ceiling")

#: A dated measurement keeps its numbers. `finding_help.py` quotes SharePoint's
#: own refusal verbatim beside a MEASURED date, and interpolating a constant
#: into a quoted observation would falsify it. Same exemption, and same
#: spelling, as `test_family_count_prose.py`.
_DATED_MEASUREMENT = re.compile(
    r"(?:RE-)?MEASURED.{0,40}?\d{4}-\d{2}-\d{2}", re.IGNORECASE,
)

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
#: absent from it survived.
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
    """Every package module except `limits.py` itself."""
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
    """Whether `text` contains `value` as a standalone number.

    A separator excludes the value only when digits sit on the far side of
    it, so "Measured 2026-07-31" is not a claim about a 31-character
    ceiling while "32-character limit" still is. Excluding every
    hyphen-adjacent number, which an earlier version did, hid that second
    wording. A value ending a sentence counts, since excluding the
    character after it made two earlier attempts report zero.
    """
    return re.search(
        rf"(?<!\d)(?<!\d[-/.]){value}(?!\d)(?![-/.]\d)", text,
    ) is not None


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


def _docstrings(tree: ast.AST) -> set[int]:
    """The id() of every docstring node, which this gate does not scan.

    A docstring is read in an editor and never shown to an operator, so a
    limit named in one is prose rather than a second copy. `test_cli.py`
    excludes them from its console-encoding gate for the same reason.
    """
    holders = (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    found: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, holders) or not node.body:
            continue
        first = node.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            found.add(id(first.value))
    return found


def _offending_messages(path: Path, values: set[int]) -> list[str]:
    """Any string stating a limit value instead of interpolating it.

    Every string constant, not only a call argument. `finding_help.py`
    holds its entries as dictionary values, so a call-argument scan let
    `dbml-sharepoint explain` tell an operator a hardcoded ceiling.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstrings(tree)
    # An f-string's own parts, so one wrapped message is not reported twice
    # and its text is searched whole. A MEASURED marker and the number it
    # records often sit in different physical strings of one expression.
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            skip.update(id(part) for part in node.values)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant | ast.JoinedStr):
            continue
        if id(node) in skip:
            continue
        text = _string_parts(node)
        if _DATED_MEASUREMENT.search(text):
            continue
        if not any(word in text.lower() for word in _CEILING_WORDS):
            continue
        for value in values:
            if _states_value(text, value):
                offenders.append(
                    f"{path.name}:{node.lineno}: text states {value} "
                    f"instead of interpolating the constant"
                )
                break
    return offenders


def _comparisons(node: ast.AST, enclosing: str | None) -> Iterator[tuple[ast.Compare, str | None]]:
    """Every comparison in the tree, paired with the function enclosing it.

    A comparison at module level or in a class body has no enclosing function,
    and the innermost function wins, so a nested one is reported once under its
    own name rather than once per function it sits inside.
    """
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
            yield from _comparisons(child, child.name)
            continue
        if isinstance(child, ast.Compare):
            yield child, enclosing
        yield from _comparisons(child, enclosing)


def _string_literals(node: ast.expr) -> list[tuple[str, int]]:
    """A bare string operand, or the strings inside an inline set, tuple or list.

    Each paired with its own line number, so a collection written across
    several lines reports the one the offending string sits on.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [(node.value, node.lineno)]
    if isinstance(node, ast.Set | ast.Tuple | ast.List):
        return [found for element in node.elts for found in _string_literals(element)]
    return []


def _offending_vocabulary(path: Path) -> list[str]:
    """Comparisons against a type string a predicate already owns."""
    offenders: list[str] = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node, enclosing in _comparisons(tree, None):
        for side in [node.left, *node.comparators]:
            for text, lineno in _string_literals(side):
                owner = _PREDICATE_OWNERS.get(text)
                if owner is None or owner == enclosing:
                    continue
                where = enclosing or "code outside any function"
                offenders.append(
                    f"{path.name}:{lineno}: {where} compares against "
                    f"{text!r}; call {owner}() instead"
                )
    return offenders


def test_no_comparison_uses_a_bare_limit_value() -> None:
    """Every package module, scanned for a comparison against a bare limit value.

    A ceiling enforced by a literal is a second copy of the number, and the two
    copies drift.
    """
    modules = _src_modules()
    assert len(modules) > 30, f"only {len(modules)} modules scanned, so this pins nothing"

    values = _limit_values()
    assert values, "no limits were found, so this pins nothing"
    offenders = [
        line for path in modules for line in _offending_literals(path, values)
    ]
    assert not offenders, (
        "Comparisons against a bare limit value. Import the constant from "
        "`analysis.limits` instead:\n" + "\n".join(offenders)
    )


def test_no_message_states_a_limit_value() -> None:
    """Every package module, scanned for a message quoting a limit value.

    The sentence an operator reads and the check that refuses the save must
    quote the same number, which they do by interpolating the constant.
    """
    modules = _src_modules()
    assert len(modules) > 30, f"only {len(modules)} modules scanned, so this pins nothing"

    values = _limit_values()
    assert values, "no limits were found, so this pins nothing"
    offenders = [
        line for path in modules for line in _offending_messages(path, values)
    ]
    assert not offenders, (
        "Messages stating a limit value. Interpolate the constant so the "
        "sentence cannot disagree with the check:\n" + "\n".join(offenders)
    )


def test_a_hex_literal_of_the_same_value_is_not_reported(tmp_path: Path) -> None:
    """A seeded `0x20` is not reported, and a seeded `32` on the next line is.

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


def test_a_date_in_a_message_is_not_read_as_a_limit_value(tmp_path: Path) -> None:
    """A seeded date is not reported for the number inside it, and a sentence is.

    `_views.py:366` quotes "Measured 2026-07-31" in a join finding. With a
    digit-only boundary, a sweep that set MAX_INTERNAL_NAME to 31 made this
    gate report that line, so the mutant read as killed by a scan that was only
    finding the value the sweep had just written.

    The second half also pins the keyword form, because `message=` is the same
    defect as a positional argument.
    """
    dated = tmp_path / "dated.py"
    dated.write_text(
        'Finding(\n'
        '    CODE,\n'
        '    f"against a measured ceiling of {n}. "\n'
        '    f"That ceiling held on the tenant measured 2026-07-31.",\n'
        ')\n',
        encoding="utf-8", newline="\n",
    )
    assert _offending_messages(dated, {31}) == []

    stated = tmp_path / "stated.py"
    stated.write_text(
        'Finding(CODE, message="SP internal-name limit is 31.")\n',
        encoding="utf-8", newline="\n",
    )
    assert len(_offending_messages(stated, {31})) == 1


def test_no_module_bypasses_a_predicate_it_owns() -> None:
    """Every package module, scanned for a comparison against a string typemap owns.

    Closes #251. A hand-rolled `t == "boolean"` keeps answering the old way
    once typemap learns an alias for `boolean`, so the two answers to "is this
    a boolean column" disagree with nothing to report it.

    `test_no_module_outside_typemap_compares_a_column_type_to_a_literal` in
    test_typemap.py already forbids comparing a column type to a string literal
    outside typemap. This adds to that rather than replacing it: it fires
    whether or not the other operand looks like a column type, and it scans
    inside `typemap.py`, where only the predicate that owns a string may
    spell it.
    """
    modules = _src_modules()
    assert len(modules) > 30, f"only {len(modules)} modules scanned, so this pins nothing"

    offenders = [line for path in modules for line in _offending_vocabulary(path)]
    assert not offenders, (
        "Comparisons against a type string typemap owns:\n" + "\n".join(offenders)
    )


def test_the_predicate_body_is_the_one_place_the_string_may_appear(
    tmp_path: Path,
) -> None:
    """The exemption lets `is_boolean` spell "boolean" and lets nothing else.

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


def test_the_vocabulary_gate_reads_collections_and_code_outside_a_function(
    tmp_path: Path,
) -> None:
    """The three shapes a function-body scan of bare constants missed.

    A comparison at module level, one in a class body, and a string inside an
    inline set. The nested function is here to prove it is reported once, under
    its own name, rather than once per function it sits inside.
    """
    seeded = tmp_path / "m.py"
    seeded.write_text(
        'FLAG = t == "boolean"\n'
        'class C:\n'
        '    OWNED = t == "hyperlink"\n'
        'def outer(t):\n'
        '    def inner(t):\n'
        '        return t in {"person", "text"}\n'
        '    return inner\n',
        encoding="utf-8", newline="\n",
    )

    found = _offending_vocabulary(seeded)
    assert len(found) == 3, found
    assert sum("inner" in line for line in found) == 1, found
    assert sum("outside any function" in line for line in found) == 2, found


def test_every_limit_is_named_by_a_test_or_ratcheted() -> None:
    """The test corpus, searched for the name of every constant `limits.py` declares.

    A ceiling that no test so much as names is one nobody has tried to enforce.
    """
    corpus = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(TEST_DIR.rglob("test_*.py"))
        if p.name != "test_limit_authority.py"
    )
    assert len(corpus) > 100_000, "the test corpus did not load, so this pins nothing"

    names = _limit_names()
    assert names, "no limits were found, so this pins nothing"
    # Word boundaries: LIST_VIEW_THRESHOLD is a substring of
    # LIST_VIEW_THRESHOLD_FALLBACK_ROWS, and a substring match would read a
    # test naming only the longer one as pinning both.
    unnamed = {name for name in names if re.search(rf"\b{name}\b", corpus) is None}

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
