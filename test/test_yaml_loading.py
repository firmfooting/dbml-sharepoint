# test/test_yaml_loading.py
"""The one YAML parser, and the gate that keeps every read going through it.

`yaml.safe_load` keeps the last of two identical keys in a mapping and reports
nothing (#672). `model/_yaml.py` refuses the repeat, and it only protects the
files that are read with it, so the gate below holds the package and its tests
to it.

The version guard's own cases are in `test_yaml_versions.py`, which does not
import PyYAML. The ones here compare the loader with PyYAML itself.
"""

import io
import itertools
import tomllib

import pytest
import yaml
from _paths import REPO_ROOT, SOLUTION_TEMPLATES
from yaml.constructor import ConstructorError

from dbml_sharepoint.model import _yaml

#: The tags whose resolution YAML 1.2 changed, the only ones the frozen tables hold.
_THREE = frozenset({"tag:yaml.org,2002:bool", "tag:yaml.org,2002:float", "tag:yaml.org,2002:int"})


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
        # The `!!set {a, a}` this case was written as is an explicit tag, refused first (#686).
        pytest.param("{a, a}\n", "'a'", id="keys-only"),
    ],
)
def test_a_repeat_is_refused_wherever_a_mapping_sits(text: str, key: str) -> None:
    assert f"found duplicate key {key}" in _refusal(text)


def test_two_spellings_read_as_one_boolean_are_both_named() -> None:
    """`True` and `true` are two spellings to the author, so naming only
    `True` would not say what was written twice. `No` and `Off` were the
    case here until the parser refused both (#686)."""
    assert _refusal("map: { True: blocked, true: warning }\n") == (
        "while constructing a mapping\n"
        '  in "<file>", line 1, column 6\n'
        "found duplicate key True: 'True' (line 1) and 'true' (line 1) both read as True; "
        "quote them\n"
        '  in "<file>", line 1, column 23'
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
            "true: a\ntrue: b\n", "found duplicate key True (first at line 1)",
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


@pytest.mark.parametrize(
    ("text", "kind"), [("? [a, b]\n: 1\n", "sequence"), ("? {a: 1}\n: 1\n", "mapping")],
)
def test_a_collection_key_is_refused_before_safe_loader_would_refuse_it(
    text: str, kind: str,
) -> None:
    """SafeLoader refuses both keys as unhashable, and ruamel.yaml reads the
    sequence as a tuple, so the loader refuses both itself, as composed (#686)."""
    with pytest.raises(yaml.YAMLError, match="found unhashable key"):
        yaml.safe_load(text)
    assert _refusal(text) == (
        "while composing a mapping\n"
        '  in "<file>", line 1, column 1\n'
        f"found a {kind} used as a key; a key must be a single value\n"
        '  in "<file>", line 1, column 3'
    )


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


def _fuzz() -> list[str]:
    """Every token of up to four characters that numbers are spelled with, and the booleans.

    The alphabet the research fuzz measured the two libraries over (#686).
    """
    alphabet = "0178_.-+eE:obx"
    spelled = {
        "".join(chars) for n in range(1, 5) for chars in itertools.product(alphabet, repeat=n)
    }
    words = ("yes", "no", "on", "off", "y", "n", "true", "false", "null")
    return sorted(spelled | {w for word in words for w in (word, word.upper(), word.title())})


def test_the_frozen_yaml_1_1_table_is_the_resolver_pyyaml_runs() -> None:
    """The guard reads a frozen copy and never asks the live resolver, so a
    PyYAML that changed its rules would go unnoticed without this. Its bool,
    float and int resolvers are tried before any other, so a value none of
    them takes is resolved by the rules both versions share."""
    live: dict[tuple[str, str, int], set[str]] = {}
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items():
        tags = [tag for tag, _ in resolvers]
        assert tags[: len(set(tags) & _THREE)] == [
            tag for tag, _, chars in _yaml._YAML_1_1 if first in chars
        ], first
        for tag, pattern in resolvers:
            live.setdefault((tag, pattern.pattern, pattern.flags), set()).add(first)
    for tag, pattern, chars in _yaml._YAML_1_1:
        assert live[tag, pattern.pattern, pattern.flags] == set(chars), tag
    timestamp = _yaml._TIMESTAMP
    assert ("tag:yaml.org,2002:timestamp", timestamp.pattern, timestamp.flags) in live


def test_the_frozen_boolean_spellings_are_the_ones_pyyaml_looks_up() -> None:
    """The guard says a resolved boolean outside these fails to load, as it does here."""
    assert frozenset(yaml.SafeLoader.bool_values) == _yaml._BOOLEANS_1_1
    with pytest.raises(KeyError):
        yaml.safe_load("v: ! |\n  yes\n")


def test_the_frozen_timestamp_parts_are_the_ones_pyyaml_constructs_from() -> None:
    """The guard states the time YAML 1.1 has read from a copy of this regex."""
    parts, live = _yaml._TIME_PARTS, yaml.SafeLoader.timestamp_regexp
    assert (parts.pattern, parts.flags) == (live.pattern, live.flags)


@pytest.mark.parametrize(
    "fraction", ["1234565", "1234564", "9999995", "12345650", "12345612345678901234"],
)
def test_pyyaml_reads_the_time_the_guard_states(fraction: str) -> None:
    """PyYAML keeps six fraction digits, which is the time the refusal says
    has been read until now and the spelling it offers."""
    token = f"2026-01-02T03:04:05.{fraction}+10:00"
    read = yaml.safe_load(f"v: {token}\n")["v"]
    kept = token.replace(fraction, fraction[:6])
    assert read == yaml.safe_load(f"v: {kept}\n")["v"]
    why = _yaml._refusal(token)
    assert (why is None) == (fraction[6] < "5")
    if why is not None:
        assert f"read as the time {read.isoformat()} until now" in why
        assert f"write `{kept}` to keep the time" in why


def test_pyyaml_resolves_every_fuzz_token_as_the_frozen_table_says() -> None:
    loader = yaml.SafeLoader("")
    try:
        for token in _fuzz():
            resolved = loader.resolve(yaml.ScalarNode, token, (True, False))
            expected = resolved if resolved in _THREE else None
            assert _yaml._tag(_yaml._YAML_1_1, token) == expected, token
    finally:
        loader.dispose()


@pytest.mark.parametrize(
    "error", [ValueError, KeyError, IndexError, OverflowError, AssertionError],
)
def test_a_construction_error_is_a_yaml_error_at_its_node(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception],
) -> None:
    """Each escaped every handler that catches the parser's errors: the
    mapping reader's, the catalogue's skip, the CLI's and the wizard's.
    Without an explicit tag only ValueError and KeyError can be raised, so
    the int constructor is made to raise each in turn."""

    def fail(loader: _yaml.UniqueKeyLoader, node: yaml.ScalarNode) -> int:
        raise error(f"{loader.construct_scalar(node)} failed")

    monkeypatch.setitem(_yaml.UniqueKeyLoader.yaml_constructors, "tag:yaml.org,2002:int", fail)
    with pytest.raises(ConstructorError) as err:
        _yaml.safe_load(io.StringIO("a: x\nb: 12\n"))
    assert type(err.value.__cause__) is error
    assert str(err.value) == (
        f"cannot construct !!int from '12': {err.value.__cause__}\n"
        '  in "<file>", line 2, column 4'
    )


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
