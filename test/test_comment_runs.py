"""The comment-run ratchet: paragraph-length comments may not grow (#610).

`AGENTS.md` asks for one-line comments. Existing prose is grandfathered by a
per-file pin in `_comment_run_pins.PINNED`, so a new run fails and a removed
one must lower its pin in the same change.
"""

import pytest
from _comment_run_pins import PINNED
from _comment_runs import (
    MIN_RUN,
    Run,
    comment_runs,
    excluded,
    measure,
    problems,
    scanned_files,
)
from _paths import REPO_ROOT


def _lines(prefix: str, count: int, first: str = "why") -> str:
    """`count` comment lines, the first reading `first`."""
    body = [f"{prefix} {first}"] + [f"{prefix} more" for _ in range(count - 1)]
    return "\n".join(body) + "\n"


def _flagged(text: str, name: str) -> list[Run]:
    return [run for run in comment_runs(text, name) if run.exemption is None]


@pytest.mark.parametrize(
    ("prefix", "name"),
    [("#", "a.py"), ("//", "a.js"), ("//", "a.js.j2"), ("//", "a.pq")],
)
def test_six_line_comments_pass_and_seven_are_a_run(prefix: str, name: str) -> None:
    six = "x = 1\n" + _lines(prefix, MIN_RUN - 1) + "y = 2\n"
    seven = "x = 1\n" + _lines(prefix, MIN_RUN) + "y = 2\n"

    assert _flagged(six, name) == []
    assert [(run.first_line, run.length) for run in _flagged(seven, name)] == [(2, 7)]


def test_every_line_of_a_c_block_comment_counts() -> None:
    block = "/*\n" + " * why\n" * 5 + " */\nrun();\n"

    assert [(run.first_line, run.length) for run in _flagged(block, "a.js")] == [(1, 7)]


def test_a_one_line_c_block_counts_as_one_comment_line() -> None:
    text = "/* a */\n" * 7

    assert [run.length for run in _flagged(text, "a.js")] == [7]


def test_every_line_of_a_jinja_comment_block_counts() -> None:
    block = "{#\n" + "  why\n" * 5 + "#}\n{{ value }}\n"

    assert [(run.first_line, run.length) for run in _flagged(block, "a.md.j2")] == [(1, 7)]


def test_jinja_and_js_comments_join_one_run_in_a_js_template() -> None:
    text = "{# why #}\n" * 4 + "// more\n" * 3

    assert [run.length for run in _flagged(text, "a.js.j2")] == [7]


def test_js_comment_syntax_is_not_read_in_a_markdown_template() -> None:
    assert comment_runs("// not a comment\n" * 9, "a.md.j2") == []


def test_a_blank_line_breaks_a_run() -> None:
    text = _lines("#", 4) + "\n" + _lines("#", 4)

    assert comment_runs(text, "a.py") == []


def test_a_code_line_breaks_a_run() -> None:
    text = _lines("//", 4) + "run();\n" + _lines("//", 4)

    assert comment_runs(text, "a.js") == []


def test_a_trailing_comment_is_a_code_line() -> None:
    text = _lines("#", 4) + "x = 1  # why\n" + _lines("#", 4)

    assert comment_runs(text, "a.py") == []


def test_a_hash_inside_a_python_string_is_not_a_comment() -> None:
    text = 'FIXTURE = """\n' + "# not a comment\n" * 9 + '"""\n'

    assert comment_runs(text, "a.py") == []


@pytest.mark.parametrize(
    ("first", "exemption"),
    [
        ("MEASURED on a live site: it held", "MEASURED"),
        ("On 2026-09-24 the site refused it", "dated"),
        ("---- Operator gate ----", "banner"),
    ],
)
def test_an_evidence_shaped_first_line_exempts_the_run(first: str, exemption: str) -> None:
    runs = comment_runs(_lines("//", MIN_RUN, first), "a.js")

    assert [run.exemption for run in runs] == [exemption]


def test_an_attribute_docstring_exempts_the_run() -> None:
    text = "#: why\n" * MIN_RUN + "LIMIT = 3\n"

    assert [run.exemption for run in comment_runs(text, "a.py")] == ["attribute"]


def test_only_the_first_line_can_exempt_a_run() -> None:
    text = _lines("#", 3) + "# MEASURED 2026-09-24\n" + _lines("#", 3)

    assert [run.exemption for run in comment_runs(text, "a.py")] == [None]


def test_generated_files_are_excluded_and_their_templates_are_not() -> None:
    tracked = {
        "test/manual/probe.js",
        "test/manual/templates/probe.js.j2",
        "test/manual/handwritten.js",
    }

    assert excluded("test/fixtures/expected/deploy.js", tracked)
    assert excluded("website/docs/api/index.py", tracked)
    assert excluded("test/manual/probe.js", tracked)
    assert not excluded("test/manual/templates/probe.js.j2", tracked)
    assert not excluded("test/manual/handwritten.js", tracked)


def test_a_count_above_the_pin_names_the_file_and_the_run() -> None:
    runs = {"a.py": [Run(first_line=12, length=7, text="# why", exemption=None)]}

    [found] = problems(runs, pinned={})

    assert "a.py:12" in found
    assert "# why" in found


def test_a_count_below_the_pin_asks_for_the_pin_to_come_down() -> None:
    runs = {"a.py": [Run(first_line=12, length=7, text="# why", exemption=None)]}

    [found] = problems(runs, pinned={"a.py": 2})

    assert "lower" in found
    assert "'a.py': 1" in found


def test_a_pin_on_a_file_with_no_runs_must_be_deleted() -> None:
    [found] = problems({}, pinned={"gone.py": 1})

    assert "gone.py" in found
    assert "delete" in found


def test_the_scan_reads_tracked_files_only() -> None:
    """Untracked scratch never counts, so a local draft cannot move a pin."""
    names = scanned_files(REPO_ROOT)

    assert "test/_comment_runs.py" in names
    assert all(not name.startswith("test/fixtures/expected/") for name in names)


def test_the_repository_matches_its_pins() -> None:
    found = problems(measure(REPO_ROOT), pinned=PINNED)

    assert not found, "\n\n".join(found)
