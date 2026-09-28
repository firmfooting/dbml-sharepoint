# test/test_yaml_loading.py
"""The one YAML parser, and the gate that keeps every read going through it.

ruamel.yaml's own loader checks for a repeated key, but not in a mapping
that merges another nor inside the merged one, and PyYAML, which read every
file here until 2026-09, kept the last of two and reported nothing (#672).
`model/_yaml.py` refuses the repeat, and it only protects the files that are
read with it, so the gate below holds the package and its tests to it.

The loader's other refusals are in `test_yaml_refusals.py`, which imports
neither library.
"""

import io
import tomllib
from pathlib import Path

import pytest
from _paths import FIXTURES, REPO_ROOT, SOLUTION_TEMPLATES, TEST_BLUEPRINTS
from ruamel.yaml import YAML
from ruamel.yaml.constructor import ConstructorError
from ruamel.yaml.nodes import ScalarNode

from dbml_sharepoint import catalogue
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
        # The `!!set {a, a}` this case was written as is an explicit tag, refused first (#686).
        pytest.param("{a, a}\n", "'a'", id="keys-only"),
    ],
)
def test_a_repeat_is_refused_wherever_a_mapping_sits(text: str, key: str) -> None:
    assert f"found duplicate key {key}" in _refusal(text)


def test_two_spellings_read_as_one_boolean_are_both_named() -> None:
    """`True` and `true` are two spellings to the author, so naming only
    `True` would not say what was written twice. `No` and `Off` were the
    case here until YAML 1.2 read both as text (#686)."""
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
    one, and the reporting-sample test blueprint's mapping does that."""
    assert _yaml.safe_load("base: &b {x: 1}\nuse: {<<: *b, x: 2}\n")["use"] == {"x": 2}
    merged = _yaml.safe_load("a: &a {x: 1}\nb: &b {y: 1}\nuse: {<<: [*a, *b], x: 2, y: 3}\n")
    assert merged["use"] == {"x": 2, "y": 3}


def test_a_second_merge_key_in_one_mapping_is_refused() -> None:
    """Two `<<` keys are a repeat under the spec. PyYAML settled their clash
    the opposite way to the list form, reading `x` as 2 here where the list
    reads 1, so neither reading is safe."""
    two_keys = "a: &a {x: 1}\nb: &b {x: 2}\nuse:\n  <<: *a\n  <<: *b\n"
    listed = "a: &a {x: 1}\nb: &b {x: 2}\nuse:\n  <<: [*a, *b]\n"
    assert _yaml.safe_load(listed)["use"] == {"x": 1}
    assert _refusal(two_keys) == (
        "while constructing a mapping\n"
        '  in "<file>", line 4, column 3\n'
        "found duplicate key '<<' (first at line 4)\n"
        '  in "<file>", line 5, column 3'
    )


def test_a_quoted_merge_spelling_is_a_text_key_not_a_second_merge() -> None:
    text = 'a: &a {x: 1}\nuse: {<<: *a, "<<": 2}\n'
    assert _yaml.safe_load(text) == {"a": {"x": 1}, "use": {"x": 1, "<<": 2}}


def test_a_repeat_inside_a_merge_source_is_refused() -> None:
    """The source is flattened into its user and never constructed alone, so
    a check in `construct_mapping` would not see it."""
    assert "found duplicate key 'x'" in _refusal("use: {<<: {x: 1, x: 2}}\n")


def test_a_nested_merge_flattened_before_it_is_built_is_not_a_repeat() -> None:
    """Mappings are built breadth first, so `use` flattens `b` in place
    before `b` is built, leaving `x` twice in its pairs. A check that read
    those pairs again would refuse a document the parser reads correctly."""
    text = "defs:\n  inner:\n    b: &b {<<: &a {x: 1}, x: 3}\nuse: {<<: *b}\n"
    assert _yaml.safe_load(text) == {"defs": {"inner": {"b": {"x": 3}}}, "use": {"x": 3}}


def test_a_value_key_loads_as_text() -> None:
    """The parser tags a bare `=` key specially and retags it as text while
    flattening, so it cannot be constructed before that."""
    assert _yaml.safe_load("=: 1\n") == {"=": 1}


@pytest.mark.parametrize(
    ("text", "kind"), [("? [a, b]\n: 1\n", "sequence"), ("? {a: 1}\n: 1\n", "mapping")],
)
def test_a_collection_key_is_refused_as_it_is_composed(text: str, kind: str) -> None:
    """PyYAML refused both keys as unhashable, and ruamel.yaml reads the
    sequence as a tuple, so the loader refuses both itself (#686)."""
    assert _refusal(text) == (
        "while composing a mapping\n"
        '  in "<file>", line 1, column 1\n'
        f"found a {kind} used as a key; a key must be a single value\n"
        '  in "<file>", line 1, column 3'
    )


def test_every_shipped_yaml_file_loads_unchanged() -> None:
    """An enforced rule must not be stronger than the reference implementation.

    Every shipped file loads unrefused, to what ruamel.yaml's own safe loader
    reads. No shipped mapping overrides a merged width any more, which is the
    case a naive repeat check refuses, so the reporting-sample test blueprint's
    mapping carries one and is named as well as globbed.
    """
    sample = TEST_BLUEPRINTS / "reporting-sample" / "20-configure" / "mapping.yaml"
    read = sorted({*SOLUTION_TEMPLATES.rglob("*.yaml"), sample})
    assert "<<: *spine\n        Title: 300\n" in sample.read_text(encoding="utf-8")
    for path in read:
        text = path.read_text(encoding="utf-8")
        assert _yaml.safe_load(text) == YAML(typ="safe", pure=True).load(text), path
    views = _yaml.safe_load(sample.read_text(encoding="utf-8"))["views"]["Action"]
    done = next(view for view in views if view["title"] == "Done")
    assert done["widths"] == {"Title": 300, "Status": 120, "Minutes": 100, "RelatedRisk": 200}


def _roots() -> dict[str, set[Path]]:
    """Every YAML document the tool reads that the repository holds, by where it is.

    Each mapping, release and side file of the shipped templates, the
    examples and the fixtures, and each journey, whose front matter is read.
    """
    return {
        "templates": set(SOLUTION_TEMPLATES.rglob("*.yaml")),
        "examples": set((REPO_ROOT / "examples").rglob("*.yaml")),
        "fixtures": set(FIXTURES.rglob("*.yaml")),
        "journeys": set((SOLUTION_TEMPLATES / catalogue.JOURNEYS_DIRNAME).glob("*.md")),
    }


_ROOTS = _roots()
_DOCUMENTS = sorted({path for found in _ROOTS.values() for path in found})

# Raised as documents are added and never lowered to pass: a drop means a glob stopped matching.
# Lowered once, 2026-09-28, from 103: the blueprints that left core took their files with them.
_FLOOR = 32


def test_the_round_trip_covers_every_kind_of_document() -> None:
    """A glob that matched nothing would pass the round trip below vacuously,
    and one that matched fewer would pass it on what was left."""
    assert [root for root, found in _ROOTS.items() if not found] == []
    assert len(_DOCUMENTS) >= _FLOOR
    names = {path.name for path in _DOCUMENTS}
    assert {"mapping.yaml", "release.yaml", "reporting.yaml", "demo.yaml", "topics.yaml"} <= names
    assert any(path.suffix == ".md" for path in _DOCUMENTS)


@pytest.mark.parametrize(
    "path", _DOCUMENTS, ids=lambda path: path.relative_to(REPO_ROOT).as_posix(),
)
def test_every_document_the_tool_reads_round_trips_through_the_writer(path: Path) -> None:
    """What the loader reads, the writer writes back as a document that
    reads as the same value, so a file `extract` or an edit writes loads."""
    text = path.read_text(encoding="utf-8")
    loaded = catalogue._front_matter(text, path) if path.suffix == ".md" else _yaml.safe_load(text)
    # `repr` also tells 1 from 1.0 and True, and one key order from another.
    assert repr(_yaml.safe_load(_yaml.safe_dump(loaded))) == repr(loaded)


@pytest.mark.parametrize(
    ("zone", "read"),
    [
        ("Z", ", tzinfo=datetime.timezone.utc"),
        ("+00:00", ", tzinfo=datetime.timezone.utc"),
        ("-00:00", ", tzinfo=datetime.timezone.utc"),
        ("+10:00", ", tzinfo=datetime.timezone(datetime.timedelta(seconds=36000))"),
        (" -05", ", tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))"),
        ("", ""),
    ],
)
def test_a_zoned_time_keeps_the_zone_pyyaml_gave_it(zone: str, read: str) -> None:
    """ruamel.yaml names a zone as it was written, `Z` or `+10:00`, and
    PyYAML 6.0.3 did not, as measured on 2026-09-27. A message that shows a
    loaded time with `!r`, as a condition's and a demo row's refusals do,
    would otherwise change its words; this is the value those have shown."""
    value = _yaml.safe_load(f"v: 2026-01-02 03:04:05{zone}\n")["v"]
    assert repr(value) == f"datetime.datetime(2026, 1, 2, 3, 4, 5{read})"


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("%YAML 2.0\n---\na: 1\n", "found incompatible YAML document (version 1.* is required)"),
        ("%YAML 0.9\n---\na: 1\n", "found incompatible YAML document (version 1.* is required)"),
        ("%YAML 1.2\n%YAML 1.2\n---\na: 1\n", "found duplicate YAML directive"),
        ("%YAML 1.1\n%YAML 2.0\n---\na: 1\n", "found duplicate YAML directive"),
    ],
    ids=["major-2", "major-0", "repeated", "repeated-major-2"],
)
def test_a_version_directive_the_parser_rejects_is_still_rejected(
    text: str, message: str,
) -> None:
    """The scanner hands the parser `1.2` for any `%YAML 1.x`, so ruamel.yaml
    neither switches version nor asserts. Another major version, and a second
    `%YAML`, still reach the parser's own checks, whose words and marks are
    the ones PyYAML 6.0.3 gave, as measured on 2026-09-27."""
    where = "2" if message.endswith("directive") else "1"
    assert _refusal(text) == f'{message}\n  in "<file>", line {where}, column 1'


@pytest.mark.parametrize(
    "error", [ValueError, KeyError, IndexError, OverflowError, AssertionError],
)
def test_a_construction_error_is_a_yaml_error_at_its_node(
    monkeypatch: pytest.MonkeyPatch, error: type[Exception],
) -> None:
    """Each escaped every handler that catches the parser's errors: the
    mapping reader's, the catalogue's skip, the CLI's and the wizard's.
    Every tag is refused, which closes the usual way to reach most of them,
    so the int constructor is made to raise each in turn."""

    def fail(constructor: _yaml.UniqueKeyConstructor, node: ScalarNode) -> int:
        raise error(f"{constructor.construct_scalar(node)} failed")

    constructors = _yaml.UniqueKeyConstructor.yaml_constructors
    monkeypatch.setitem(constructors, "tag:yaml.org,2002:int", fail)
    with pytest.raises(ConstructorError) as err:
        _yaml.safe_load(io.StringIO("a: x\nb: 12\n"))
    assert type(err.value.__cause__) is error
    assert str(err.value) == (
        f"cannot construct !!int from '12': {err.value.__cause__}\n"
        '  in "<file>", line 2, column 4'
    )


def test_a_yaml_library_may_be_imported_only_by_the_parser_and_its_own_test() -> None:
    """ruamel.yaml's loader anywhere else would read a repeat in a merging
    mapping, an explicit tag and a `%YAML 1.1` directive without a word.

    Ruff's banned-api rule refuses every spelling of an import of either
    library: `ruamel` covers `ruamel.yaml` and its modules. This pins that
    the rule is on and that only `model/_yaml.py` and this module, which
    compares the loader with ruamel.yaml's own, are exempt from it. PyYAML is no longer
    installed, and its ban stays so that it cannot come back unnoticed.
    """
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    lint = pyproject["tool"]["ruff"]["lint"]
    assert "TID251" in lint["select"]
    assert sorted(lint["flake8-tidy-imports"]["banned-api"]) == ["ruamel", "yaml"]
    exempt = sorted(
        pattern for pattern, rules in lint["per-file-ignores"].items() if "TID251" in rules
    )
    assert exempt == ["src/dbml_sharepoint/model/_yaml.py", "test/test_yaml_loading.py"]
