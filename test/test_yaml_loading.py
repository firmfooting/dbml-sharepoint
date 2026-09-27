# test/test_yaml_loading.py
"""The one YAML parser, and the gate that keeps every read going through it.

`yaml.safe_load` keeps the last of two identical keys in a mapping and reports
nothing (#672). `model/_yaml.py` refuses the repeat, and it only protects the
files that are read with it, so the gate below holds the package and its tests
to it.
"""

import io
import tomllib

import pytest
import yaml
from _paths import REPO_ROOT, SOLUTION_TEMPLATES

from dbml_sharepoint.model import _yaml


def _refusal(text: str) -> str:
    """The parser's message for `text`, read as a stream so it carries no snippet."""
    with pytest.raises(_yaml.PARSE_ERRORS) as err:
        _yaml.safe_load(io.StringIO(text))
    return str(err.value)


def test_a_key_written_twice_is_refused_naming_both_lines() -> None:
    assert _refusal("a: 1\nb: 2\na: 3\n") == (
        "while constructing a mapping\n"
        '  in "<file>", line 1, column 1\n'
        "found duplicate key 'a' (first at line 1)\n"
        '  in "<file>", line 3, column 1'
    )


@pytest.mark.parametrize(
    ("text", "key"),
    [
        pytest.param("a:\n  b: 1\n  c: 2\n  b: 3\n", "'b'", id="nested"),
        pytest.param("a: {b: 1, b: 2}\n", "'b'", id="flow"),
        pytest.param("- {b: 1, b: 2}\n", "'b'", id="in-a-sequence"),
        pytest.param("!!set {a, a}\n", "'a'", id="set"),
    ],
)
def test_a_repeat_is_refused_wherever_a_mapping_sits(text: str, key: str) -> None:
    assert f"found duplicate key {key}" in _refusal(text)


def test_two_words_read_as_one_boolean_are_both_named() -> None:
    """`No` and `Off` are two words to the author, so naming only `False`
    would not say what was written twice."""
    assert _refusal("map: { No: blocked, Off: warning }\n") == (
        "while constructing a mapping\n"
        '  in "<file>", line 1, column 6\n'
        "found duplicate key False: 'No' (line 1) and 'Off' (line 1) both read as False; "
        "quote them\n"
        '  in "<file>", line 1, column 21'
    )


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        pytest.param(
            "1: a\n0x1: b\n",
            "found duplicate key 1: '1' (line 1) and '0x1' (line 2) both read as 1; quote them",
            id="int-and-hex",
        ),
        pytest.param(
            "~: a\nnull: b\n",
            "found duplicate key None: '~' (line 1) and 'null' (line 2) both read as None; "
            "quote them",
            id="two-nulls",
        ),
        pytest.param(
            "1: a\n1.0: b\n",
            "found duplicate key 1.0: '1' (line 1) and '1.0' (line 2) read as 1 and 1.0, "
            "which are equal; quote them",
            id="int-and-float",
        ),
        pytest.param(
            "No: a\nNo: b\n", "found duplicate key False (first at line 1)",
            id="one-spelling-twice",
        ),
    ],
)
def test_keys_that_construct_equal_are_one_key(text: str, problem: str) -> None:
    """A dict holds one entry for two keys that compare equal, so the second
    replaced the first exactly as a repeated spelling did. Both spellings are
    named where they differ."""
    assert f"\n{problem}\n" in _refusal(text)


def test_keys_of_different_types_are_distinct() -> None:
    """`1:` and `"1":` are two keys to YAML and to a dict alike. Refusing the
    int is `_text_key`'s job, where the context can be named."""
    assert _yaml.safe_load('1: a\n"1": b\n') == {1: "a", "1": "b"}


def test_a_key_beside_a_merge_overrides_it() -> None:
    """The merge-key spec lets a key written beside `<<` override the merged
    one, and the shipped programme-governance mapping does that."""
    assert _yaml.safe_load("base: &b {x: 1}\nuse: {<<: *b, x: 2}\n")["use"] == {"x": 2}
    merged = _yaml.safe_load("a: &a {x: 1}\nb: &b {y: 1}\nuse: {<<: [*a, *b], x: 2, y: 3}\n")
    assert merged["use"] == {"x": 2, "y": 3}


def test_a_second_merge_key_in_one_mapping_is_refused() -> None:
    """Two `<<` keys are a repeat under the spec, and PyYAML settles their
    clash the opposite way to the list form, so neither reading is safe."""
    two_keys = "a: &a {x: 1}\nb: &b {x: 2}\nuse:\n  <<: *a\n  <<: *b\n"
    listed = "a: &a {x: 1}\nb: &b {x: 2}\nuse:\n  <<: [*a, *b]\n"
    assert yaml.safe_load(two_keys)["use"] == {"x": 2}
    assert yaml.safe_load(listed)["use"] == _yaml.safe_load(listed)["use"] == {"x": 1}
    assert _refusal(two_keys) == (
        "while constructing a mapping\n"
        '  in "<file>", line 4, column 3\n'
        "found duplicate key '<<' (first at line 4)\n"
        '  in "<file>", line 5, column 3'
    )


def test_a_quoted_merge_spelling_is_a_text_key_not_a_second_merge() -> None:
    text = 'a: &a {x: 1}\nuse: {<<: *a, "<<": 2}\n'
    assert _yaml.safe_load(text) == yaml.safe_load(text)
    assert _yaml.safe_load(text)["use"] == {"x": 1, "<<": 2}


def test_a_repeat_inside_a_merge_source_is_refused() -> None:
    """The source is flattened into its user and never constructed alone, so
    a check in `construct_mapping` would not see it."""
    assert "found duplicate key 'x'" in _refusal("use: {<<: {x: 1, x: 2}}\n")


def test_a_nested_merge_flattened_before_it_is_built_is_not_a_repeat() -> None:
    """PyYAML builds mappings breadth first, so `use` flattens `b` in place
    before `b` is built, leaving `x` twice in its pairs. A check that read
    those pairs again would refuse a document SafeLoader reads correctly."""
    text = "defs:\n  inner:\n    b: &b {<<: &a {x: 1}, x: 3}\nuse: {<<: *b}\n"
    assert _yaml.safe_load(text) == yaml.safe_load(text)
    assert _yaml.safe_load(text)["use"] == {"x": 3}


def test_a_value_key_loads_as_safe_loader_reads_it() -> None:
    """PyYAML tags a bare `=` key specially and retags it as text while
    flattening, so it cannot be constructed before that."""
    assert _yaml.safe_load("=: 1\n") == yaml.safe_load("=: 1\n") == {"=": 1}


@pytest.mark.parametrize("text", ["? [a, b]\n: 1\n", "? {a: 1}\n: 1\n"])
def test_an_unhashable_key_fails_as_safe_loader_fails(text: str) -> None:
    with pytest.raises(_yaml.PARSE_ERRORS) as ours:
        _yaml.safe_load(text)
    with pytest.raises(yaml.YAMLError) as theirs:
        yaml.safe_load(text)
    assert str(ours.value) == str(theirs.value)
    assert "found unhashable key" in str(ours.value)


def test_every_shipped_yaml_file_loads_unchanged() -> None:
    """An enforced rule must not be stronger than the reference implementation.

    The programme-governance mapping overrides a merged width, which is the
    case a naive repeat check refuses, so it is named as well as globbed.
    """
    shipped = sorted(SOLUTION_TEMPLATES.rglob("*.yaml"))
    governance = SOLUTION_TEMPLATES / "programme-governance" / "20-configure" / "mapping.yaml"
    assert governance in shipped
    assert "<<: *action_spine\n        Title: 300\n" in governance.read_text(encoding="utf-8")
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        assert _yaml.safe_load(text) == yaml.safe_load(text), path


def test_pyyaml_may_be_imported_only_by_the_parser_and_its_own_test() -> None:
    """`yaml.safe_load` anywhere else would read a repeated key silently again.

    Ruff's banned-api rule refuses every spelling of a PyYAML import; this pins
    that the rule is on and that only `model/_yaml.py` and this module, which
    compares the parser with PyYAML, are exempt from it. A test reading YAML
    through PyYAML would go on testing PyYAML's reading once the parser changes.
    """
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = pyproject["tool"]["ruff"]["lint"]
    assert "TID251" in lint["select"]
    assert "yaml" in lint["flake8-tidy-imports"]["banned-api"]
    exempt = sorted(
        pattern for pattern, rules in lint["per-file-ignores"].items() if "TID251" in rules
    )
    assert exempt == ["src/dbml_sharepoint/model/_yaml.py", "test/test_yaml_loading.py"]
