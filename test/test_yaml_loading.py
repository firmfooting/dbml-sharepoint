# test/test_yaml_loading.py
"""The one YAML parser, and the gate that keeps every read going through it.

ruamel.yaml's own loader checks for a repeated key, but not in a mapping
that merges another nor inside the merged one, and PyYAML, which read every
file here until 2026-09, kept the last of two and reported nothing (#672).
`model/_yaml.py` refuses the repeat, and it only protects the files that are
read with it, so the gate below holds the package and its tests to it.

The version guard's own cases are in `test_yaml_versions.py`, which imports
neither library. The ones here pin the frozen tables the guard compares:
YAML 1.2's against ruamel.yaml's live resolver, and YAML 1.1's against the
values PyYAML 6.0.3 held, since PyYAML is no longer installed.
"""

import io
import itertools
import re
import tomllib

import pytest
from _paths import REPO_ROOT, SOLUTION_TEMPLATES
from ruamel.yaml import YAML
from ruamel.yaml.constructor import ConstructorError
from ruamel.yaml.nodes import ScalarNode

from dbml_sharepoint.model import _yaml

#: The tags whose resolution YAML 1.2 changed, the only ones the frozen tables hold.
_THREE = frozenset({"tag:yaml.org,2002:bool", "tag:yaml.org,2002:float", "tag:yaml.org,2002:int"})

_TIMESTAMP_TAG = "tag:yaml.org,2002:timestamp"

#: A compiled pattern's flags: `re.compile` adds UNICODE to every text pattern.
_VERBOSE = re.VERBOSE | re.UNICODE


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
    if kind == "sequence":
        assert YAML(typ="safe", pure=True).load(text) == {("a", "b"): 1}
    assert _refusal(text) == (
        "while composing a mapping\n"
        '  in "<file>", line 1, column 1\n'
        f"found a {kind} used as a key; a key must be a single value\n"
        '  in "<file>", line 1, column 3'
    )


def test_every_shipped_yaml_file_loads_unchanged() -> None:
    """An enforced rule must not be stronger than the reference implementation.

    Every shipped file loads unrefused, to what ruamel.yaml's own safe loader
    reads. The programme-governance mapping overrides a merged width, which
    is the case a naive repeat check refuses, so it is named as well as
    globbed, with the widths PyYAML read there.
    """
    shipped = sorted(SOLUTION_TEMPLATES.rglob("*.yaml"))
    governance = SOLUTION_TEMPLATES / "programme-governance" / "20-configure" / "mapping.yaml"
    assert governance in shipped
    assert "<<: *action_spine\n        Title: 300\n" in governance.read_text(encoding="utf-8")
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        assert _yaml.safe_load(text) == YAML(typ="safe", pure=True).load(text), path
    views = _yaml.safe_load(governance.read_text(encoding="utf-8"))["views"]["Action"]
    overdue = next(view for view in views if view["title"] == "Overdue")
    assert overdue["widths"] == {
        "Title": 300, "Workstream": 180, "WorkstreamPhase": 130, "AssignedTo": 160,
        "DueDate": 160, "Status": 120, "RelatedRiskTitle": 220, "CompletedDate": 160,
    }


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


def test_the_frozen_yaml_1_2_table_is_the_resolver_ruamel_runs() -> None:
    """The guard reads a frozen copy and never asks the live resolver, so a
    ruamel.yaml that changed its rules would go unnoticed without this. Its
    bool, float and int resolvers are tried before any other, so a value none
    of them takes is resolved by the rules both versions share."""
    resolvers = _yaml._Reading().resolver.versioned_resolver
    live: dict[tuple[str, str, int], set[str]] = {}
    for first, entries in resolvers.items():
        tags = [str(tag) for tag, _ in entries]
        assert tags[: len(set(tags) & _THREE)] == [
            tag for tag, _, chars in _yaml._YAML_1_2 if first in chars
        ], first
        for tag, pattern in entries:
            live.setdefault((str(tag), pattern.pattern, pattern.flags), set()).add(first)
    for tag, pattern, chars in _yaml._YAML_1_2:
        assert live[tag, pattern.pattern, pattern.flags] == set(chars), tag
    assert len({tag for tag, _, _ in live} & _THREE) == len(_yaml._YAML_1_2)


def test_ruamel_resolves_every_fuzz_token_as_the_frozen_tables_say() -> None:
    """The three tags by the frozen YAML 1.2 table, and a timestamp by the
    pattern the guard copied from PyYAML, whose text differs in spacing only."""
    resolver = _yaml._Reading().resolver
    stems = ("2026-01-02", "2026-1-2", "2026-01-02T03:04:05", "2026-01-02 03:04:05.5 +10:00")
    for token in [*_fuzz(), *stems, *(f"{stem}Z" for stem in stems)]:
        resolved = str(resolver.resolve(ScalarNode, token, (True, False)))
        expected = resolved if resolved in _THREE else None
        assert _yaml._tag(_yaml._YAML_1_2, token) == expected, token
        assert bool(_yaml._TIMESTAMP.match(token)) == (resolved == _TIMESTAMP_TAG), token


#: PyYAML 6.0.3's resolvers for the three tags, as its `SafeLoader` held them on 2026-09-27:
#: the tag, the pattern, and the first characters it was tried on, in the order tried.
_PYYAML_6_0_3 = [
    (
        "tag:yaml.org,2002:bool",
        (
            "^(?:yes|Yes|YES|no|No|NO\n"
            "                    |true|True|TRUE|false|False|FALSE\n"
            "                    |on|On|ON|off|Off|OFF)$"
        ),
        "FNOTYfnoty",
    ),
    (
        "tag:yaml.org,2002:float",
        (
            "^(?:[-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+][0-9]+)?\n"
            "                    |\\.[0-9][0-9_]*(?:[eE][-+][0-9]+)?\n"
            "                    |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\\.[0-9_]*\n"
            "                    |[-+]?\\.(?:inf|Inf|INF)\n"
            "                    |\\.(?:nan|NaN|NAN))$"
        ),
        "+-.0123456789",
    ),
    (
        "tag:yaml.org,2002:int",
        (
            "^(?:[-+]?0b[0-1_]+\n"
            "                    |[-+]?0[0-7_]+\n"
            "                    |[-+]?(?:0|[1-9][0-9_]*)\n"
            "                    |[-+]?0x[0-9a-fA-F_]+\n"
            "                    |[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$"
        ),
        "+-0123456789",
    ),
]


def test_the_frozen_yaml_1_1_table_is_the_resolver_pyyaml_ran() -> None:
    """The table is PyYAML 6.0.3's, which read every file here until 2026-09.

    PyYAML is no longer installed, so the table cannot be compared with a
    live resolver. These are the values its `SafeLoader` held when the two
    were last compared live, on 2026-09-27, and the table must not move from
    them: it states the reading a file has had until now.
    """
    assert [
        (tag, pattern.pattern, "".join(sorted(first)))
        for tag, pattern, first in _yaml._YAML_1_1
    ] == _PYYAML_6_0_3
    assert {pattern.flags for _, pattern, _ in _yaml._YAML_1_1} == {_VERBOSE}


def test_the_frozen_timestamp_patterns_are_the_ones_pyyaml_ran() -> None:
    """The resolver's timestamp pattern and the constructor's, which split a
    timestamp into the parts the guard states PyYAML's time from, as PyYAML
    6.0.3 held them on 2026-09-27."""
    assert _yaml._TIMESTAMP.pattern == (
        "^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]\n"
        "                    |[0-9][0-9][0-9][0-9] -[0-9][0-9]? -[0-9][0-9]?\n"
        "                     (?:[Tt]|[ \\t]+)[0-9][0-9]?\n"
        "                     :[0-9][0-9] :[0-9][0-9] (?:\\.[0-9]*)?\n"
        "                     (?:[ \\t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$"
    )
    assert _yaml._TIME_PARTS.pattern == (
        "^(?P<year>[0-9][0-9][0-9][0-9])\n"
        "                -(?P<month>[0-9][0-9]?)\n"
        "                -(?P<day>[0-9][0-9]?)\n"
        "                (?:(?:[Tt]|[ \\t]+)\n"
        "                (?P<hour>[0-9][0-9]?)\n"
        "                :(?P<minute>[0-9][0-9])\n"
        "                :(?P<second>[0-9][0-9])\n"
        "                (?:\\.(?P<fraction>[0-9]*))?\n"
        "                (?:[ \\t]*(?P<tz>Z|(?P<tz_sign>[-+])(?P<tz_hour>[0-9][0-9]?)\n"
        "                (?::(?P<tz_minute>[0-9][0-9]))?))?)?$"
    )
    assert _yaml._TIMESTAMP.flags == _yaml._TIME_PARTS.flags == _VERBOSE


def test_the_frozen_boolean_spellings_are_the_ones_pyyaml_looked_up() -> None:
    """The keys of PyYAML 6.0.3's `SafeConstructor.bool_values`. The guard
    says a resolved boolean outside them fails to load, as PyYAML's lookup
    raised KeyError on `yes` read with its line break."""
    assert frozenset({"yes", "no", "true", "false", "on", "off"}) == _yaml._BOOLEANS_1_1


@pytest.mark.parametrize(
    ("fraction", "read"),
    [
        ("1234565", "2026-01-02T03:04:05.123456+10:00"),
        ("1234564", "2026-01-02T03:04:05.123456+10:00"),
        ("9999995", "2026-01-02T03:04:05.999999+10:00"),
        ("12345650", "2026-01-02T03:04:05.123456+10:00"),
        ("12345612345678901234", "2026-01-02T03:04:05.123456+10:00"),
    ],
)
def test_the_guard_states_the_time_pyyaml_read(fraction: str, read: str) -> None:
    """PyYAML 6.0.3 kept six fraction digits: `read` is the time it read, as
    measured on 2026-09-27. That is the time the refusal says has been read
    until now, and the spelling it offers reads as that time today."""
    token = f"2026-01-02T03:04:05.{fraction}+10:00"
    kept = token.replace(fraction, fraction[:6])
    assert _yaml.safe_load(f"v: {kept}\n")["v"].isoformat() == read
    why = _yaml._refusal(token)
    assert (why is None) == (fraction[6] < "5")
    if why is not None:
        assert f"read as the time {read} until now" in why
        assert f"write `{kept}` to keep the time" in why


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
def test_a_version_directive_the_parser_rejects_is_rejected_in_pyyaml_s_words(
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
    Without an explicit tag only ValueError and KeyError can be raised, so
    the int constructor is made to raise each in turn."""

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
    mapping, and every YAML 1.1 spelling, without a word.

    Ruff's banned-api rule refuses every spelling of an import of either
    library: `ruamel` covers `ruamel.yaml` and its modules. This pins that
    the rule is on and that only `model/_yaml.py` and this module, which reads
    ruamel.yaml's live resolver, are exempt from it. PyYAML is no longer
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
