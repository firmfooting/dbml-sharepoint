"""The comment-run ratchet: paragraph-length comments may not grow (#610).

`AGENTS.md` asks for one-line comments. Existing prose is grandfathered by a
per-run fingerprint in `_comment_run_pins.PINNED`, so a new or edited run
fails and a removed one must drop its pin in the same change.
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


@pytest.mark.parametrize(
    ("prefix", "name"),
    [("#", "mapping.yaml"), ("#", "a.yml"), ("//", "schema.dbml")],
)
def test_yaml_and_dbml_comment_runs_are_flagged(prefix: str, name: str) -> None:
    seven = "a: 1\n" + _lines(prefix, MIN_RUN) + "b: 2\n"

    assert [(run.first_line, run.length) for run in _flagged(seven, name)] == [(2, 7)]


def test_toml_comment_runs_are_flagged() -> None:
    """#637: `pyproject.toml` was not scanned, so a new run there bypassed the ratchet."""
    seven = "[tool.x]\n" + _lines("#", MIN_RUN) + "a = 1\n"

    assert [(run.first_line, run.length) for run in _flagged(seven, "pyproject.toml")] == [(2, 7)]
    assert _flagged("[tool.x]\n" + _lines("#", MIN_RUN - 1), "pyproject.toml") == []


@pytest.mark.parametrize("quote", ['"""', "'''"])
def test_hash_lines_in_a_toml_multiline_string_are_content(quote: str) -> None:
    text = f"notes = {quote}\n" + "# A heading\n" * MIN_RUN + f"{quote}\n" + _lines("#", 3)

    assert comment_runs(text, "pyproject.toml") == []


def test_a_quote_in_a_toml_comment_or_string_does_not_open_a_multiline_string() -> None:
    text = "a = \"'''\"  # say \"\"\"\n" + _lines("#", MIN_RUN)

    assert [(run.first_line, run.length) for run in _flagged(text, "a.toml")] == [(2, 7)]


@pytest.mark.parametrize("name", ["a.pq", "a.js"])
def test_the_first_block_closer_ends_the_comment_because_comments_do_not_nest(name: str) -> None:
    """#637 asked for nesting in `.pq`; the M spec on Learn says "Comments do not nest"."""
    text = "/* outer\n" + "   /* inner */\n" + "   Source = 1,\n" * (MIN_RUN - 2) + "*/\n"

    assert comment_runs(text, name) == []
    nested = "/*\n" + "   /* inner\n" * (MIN_RUN - 2) + "*/\n"
    assert [run.length for run in _flagged(nested, name)] == [MIN_RUN]


def test_a_dbml_block_comment_counts() -> None:
    block = "/*\n" + " * why\n" * 5 + " */\nTable t {}\n"

    assert [run.length for run in _flagged(block, "schema.dbml")] == [7]


@pytest.mark.parametrize("name", ["a.js", "a.js.j2"])
def test_comment_shaped_lines_in_a_template_literal_are_not_comments(name: str) -> None:
    text = "const body = `\n" + "// in the string\n" * MIN_RUN + "`;\n"

    assert comment_runs(text, name) == []


def test_an_escaped_backtick_does_not_close_a_template_literal() -> None:
    text = "const body = `a \\` b\n" + "/* in the string */\n" * MIN_RUN + "`;\n"

    assert comment_runs(text, "a.js") == []


def test_comments_after_a_closed_template_literal_count() -> None:
    text = "const a = `one`, b = '`';\n" + _lines("//", MIN_RUN)

    assert [run.length for run in _flagged(text, "a.js")] == [7]


def test_a_nested_template_in_an_interpolation_does_not_close_the_outer_one() -> None:
    text = "const a = `x ${ok ? `y` : `z`}\n" + "// in the string\n" * MIN_RUN + "`;\n"

    assert comment_runs(text, "a.js") == []


def test_a_quote_in_a_regex_literal_does_not_hide_the_comments_after_it() -> None:
    text = "const q = `'${name.replace(/'/g, \"''\")}'`;\n" + _lines("//", MIN_RUN)

    assert [run.length for run in _flagged(text, "a.js")] == [7]


def test_a_backtick_in_a_jinja_comment_does_not_open_a_template_literal() -> None:
    text = "{# see `name` #}\nrun();\n" + _lines("//", MIN_RUN)

    assert [run.length for run in _flagged(text, "a.js.j2")] == [7]


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
        ("MEASURED 2026-09-24: it held", "MEASURED"),
        ("---- MEASURED 2026-09-24 ----", "MEASURED"),
        ("2026-09-24: the site refused it", "dated"),
        ("--- 2026-09-24 ------", "dated"),
        ("---- Operator gate ----", "banner"),
        ("--- The wizard -------", "banner"),
    ],
)
def test_an_evidence_shaped_first_line_exempts_the_run(first: str, exemption: str) -> None:
    runs = comment_runs(_lines("//", MIN_RUN, first), "a.js")

    assert [run.exemption for run in runs] == [exemption]


@pytest.mark.parametrize(
    "first",
    [
        "UNMEASURED assumption",
        "UN-MEASURED guess",
        "This was not MEASURED on a live site",
        "TODO remove by 2026-12-01",
        "On 2026-09-24 the site refused it",
        "Measured live 2026-09-04: lower case is prose",
        "A rule of thumb ---- not a banner ----",
    ],
)
def test_a_marker_that_does_not_open_the_line_does_not_exempt_a_run(first: str) -> None:
    """#637: a marker anywhere in the line let a negated or incidental one exempt."""
    runs = comment_runs(_lines("#", MIN_RUN, first), "a.py")

    assert [run.exemption for run in runs] == [None]


@pytest.mark.parametrize(
    ("name", "opener", "closer"),
    [("a.js", "run(); /* why", " */"), ("s.dbml", "Table t { /* why", " */"),
     ("a.md.j2", "{{ x }} {# why", "#}")],
)
def test_a_block_opened_after_code_counts_its_lines_but_not_the_code_line(
    name: str, opener: str, closer: str,
) -> None:
    text = opener + "\n" + "   more\n" * (MIN_RUN - 1) + closer + "\nafter\n"

    assert [(run.first_line, run.length) for run in _flagged(text, name)] == [(2, 7)]


@pytest.mark.parametrize(
    ("name", "opener", "closer"),
    [("a.js", "/* why", " */ run();"), ("a.pq", "/* why", "*/ Source = 1,"),
     ("s.dbml", "/* why", "*/ Table t {}"), ("a.md.j2", "{# why", "#} {{ x }}"),
     ("a.js.j2", "{# why", "#} run();")],
)
def test_code_after_a_block_closer_makes_the_line_code(
    name: str, opener: str, closer: str,
) -> None:
    """#637: the mixed closing line joined two short runs into one of seven."""
    after = "{# more #}\n" * 3 if name.endswith(".j2") else _lines("//", 3)
    text = opener + "\n" + "   more\n" * 2 + closer + "\n" + after

    assert comment_runs(text, name) == []


@pytest.mark.parametrize(
    ("name", "opener", "closer"),
    [("a.js", "/* why", " */ // more"), ("a.md.j2", "{# why", "#} {# more #}")],
)
def test_a_comment_after_a_block_closer_keeps_the_line_a_comment(
    name: str, opener: str, closer: str,
) -> None:
    text = opener + "\n" + "   more\n" * (MIN_RUN - 2) + closer + "\nafter\n"

    assert [(run.first_line, run.length) for run in _flagged(text, name)] == [(1, 7)]


def test_a_one_line_block_followed_by_code_is_a_code_line() -> None:
    text = _lines("//", 3) + "/* why */ run();\n" + _lines("//", 3)

    assert comment_runs(text, "a.js") == []


@pytest.mark.parametrize("indicator", ["|", ">", "|-", ">+", "|2"])
def test_hash_lines_in_a_yaml_block_scalar_are_content(indicator: str) -> None:
    text = f"notes: {indicator}\n" + "  # A heading\n" * MIN_RUN + "next: 1\n"

    assert comment_runs(text, "release.yaml") == []


def test_a_sibling_comment_run_ends_a_sequence_item_block_scalar() -> None:
    """#637: the scalar ran on to the next `- ` item, swallowing sibling comments."""
    text = "- notes: |\n    text\n" + _lines("  #", MIN_RUN) + "  next: 1\n"

    assert [(run.first_line, run.length) for run in _flagged(text, "a.yaml")] == [(3, 7)]


def test_hash_lines_in_a_sequence_item_block_scalar_are_content() -> None:
    text = "- notes: |\n" + "    # A heading\n" * MIN_RUN + "  next: 1\n"

    assert comment_runs(text, "a.yaml") == []


def test_a_sequence_item_block_scalar_takes_its_first_line_indentation() -> None:
    text = "- - notes: >\n" + "        # deep\n" * MIN_RUN + "    next: 1\n"

    assert comment_runs(text, "a.yaml") == []
    assert [run.length for run in _flagged(text + _lines("    #", MIN_RUN), "a.yaml")] == [7]


def test_a_yaml_comment_run_after_a_block_scalar_counts() -> None:
    text = "- notes: |\n    text\n" + _lines("#", MIN_RUN)

    assert [(run.first_line, run.length) for run in _flagged(text, "a.yaml")] == [(3, 7)]


def test_comments_inside_a_template_interpolation_count() -> None:
    text = "const a = `x ${\n" + "  // why\n" * MIN_RUN + "  value\n}`;\n"

    assert [(run.first_line, run.length) for run in _flagged(text, "a.js")] == [(2, 7)]


@pytest.mark.parametrize("keyword", ["return", "typeof", "case", "yield", "await", "else"])
def test_a_regex_after_a_keyword_does_not_open_a_template(keyword: str) -> None:
    text = f"function f() {{\n  {keyword} /`/;\n}}\n" + _lines("//", MIN_RUN)

    assert [run.length for run in _flagged(text, "a.js")] == [7]


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


def _measured(text: str, name: str = "a.py") -> dict[str, list[Run]]:
    return {name: comment_runs(text, name)}


def _pins(text: str, name: str = "a.py") -> dict[str, list[str]]:
    return {name: [run.fingerprint for run in _flagged(text, name)]}


def test_an_unpinned_run_names_the_file_and_the_run() -> None:
    [found] = problems(_measured("x = 1\n" + _lines("#", MIN_RUN)), pinned={})

    assert "a.py:2" in found
    assert "# why" in found


def test_a_pinned_run_that_moves_still_matches_its_pin() -> None:
    old = _lines("#", MIN_RUN)
    moved = "x = 1\n" * 20 + "    " + old.replace("\n#", "\n    #")

    assert problems(_measured(moved), pinned=_pins(old)) == []


def test_editing_a_pinned_run_fails() -> None:
    old = _lines("#", MIN_RUN)
    edited = old.replace("more", "changed", 1)

    found = problems(_measured(edited), pinned=_pins(old))

    assert any("fix the lines you are already touching" in item for item in found)


def test_replacing_a_pinned_run_with_a_new_one_of_the_same_count_fails() -> None:
    """The count was equal, so the per-file pin #636 first shipped let this through."""
    old = _lines("#", MIN_RUN, "old reason")
    new = _lines("#", MIN_RUN, "new reason")

    found = problems(_measured(new), pinned=_pins(old))

    assert any("a.py:1" in item and "new reason" in item for item in found)
    assert any("remove" in item for item in found)


def test_identical_runs_are_pinned_with_multiplicity() -> None:
    one = _lines("#", MIN_RUN)
    two = one + "x = 1\n" + one

    assert problems(_measured(two), pinned=_pins(two)) == []
    assert problems(_measured(two), pinned=_pins(one)) != []


def test_a_pin_with_no_run_left_must_be_removed() -> None:
    [found] = problems({}, pinned={"gone.py": ["0123456789ab"]})

    assert "gone.py" in found
    assert "remove" in found


def test_the_scan_reads_tracked_files_only() -> None:
    """Untracked scratch never counts, so a local draft cannot move a pin."""
    names = scanned_files(REPO_ROOT)

    assert "test/_comment_runs.py" in names
    assert "examples/minimal/mapping.yaml" in names
    assert "examples/project-tracker/schema.dbml" in names
    assert ".github/workflows/ci.yml" in names
    assert "pyproject.toml" in names
    assert all(not name.startswith("test/fixtures/expected/") for name in names)


def test_the_repository_matches_its_pins() -> None:
    found = problems(measure(REPO_ROOT), pinned=PINNED)

    assert not found, "\n\n".join(found)
