# test/test_yaml_refusals.py
"""What the loader reads as YAML 1.2, and the valid YAML it refuses (#686).

`model/_yaml.py` reads plain values as ruamel.yaml reads YAML 1.2, so `yes`
is text and `010` is 10. It refuses an explicit tag, a `%YAML` or `%TAG`
directive, and the valid YAML `RefusedYAMLError` names, and reports a value
it cannot construct as a parse error.

Every expectation here is literal, measured on ruamel.yaml 0.19.1, and
nothing here imports it.
"""

import datetime as dt
import io
import sys
from pathlib import Path

import pytest
import typer
from _catalogue_fixtures import manifest_text
from _packs import DEFAULT_PREFIX, blocks, entities, write_mapping
from _paths import FIXTURES

from dbml_sharepoint import catalogue
from dbml_sharepoint.model import _yaml
from dbml_sharepoint.model.errors import MappingError, MappingSourceError
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.project import load_config

_HEADER = "uses tags or directives the loader refuses:"


@pytest.mark.parametrize(
    ("token", "reading"),
    [
        # Booleans in YAML 1.1 and text in YAML 1.2, which spells a boolean `true` or `false`.
        ("yes", "yes"), ("No", "No"), ("on", "on"), ("OFF", "OFF"), ("true", True),
        # A leading zero is decimal, and base 60 is text.
        ("010", 10), ("08", 8), ("1:30", "1:30"),
        # Numbers to ruamel.yaml, and text to the YAML 1.2 core schema.
        ("1_000", 1000), ("0b101", 5),
        # Text in YAML 1.1, and numbers in YAML 1.2.
        ("0o10", 8), ("1e3", 1000.0), ("1.0e3", 1000.0), ("-.5", -0.5),
    ],
)
def test_a_plain_value_is_read_as_yaml_1_2(token: str, reading: object) -> None:
    """The spellings the mapping reference names, which a YAML 1.1 reader
    reads otherwise."""
    value = _yaml.safe_load(f"v: {token}\n")["v"]
    assert (type(value), value) == (type(reading), reading)


#: How a tag's refusal ends on a scalar, but for a bare `!`.
_UNTAG = "remove it to read the value as though untagged, or write `!!str` for text"


def _tag(name: str, fix: str = _UNTAG) -> str:
    """The refusal of the explicit tag `name`."""
    return (
        f"the tag `{name}` is refused, because the loader reads every value by one fixed set "
        f"of rules; {fix}"
    )


#: An explicit tag written at line 1, column 4; every tag but `!!str` on a scalar is refused.
_TAGS = [
    pytest.param("v: !!int 010", _tag("!!int"), id="int"),
    pytest.param('v: !!int "010"', _tag("!!int"), id="int-quoted"),
    pytest.param("v: !!bool y", _tag("!!bool"), id="bool"),
    pytest.param("v: !!float 1e3", _tag("!!float"), id="float"),
    pytest.param("v: !!null x", _tag("!!null"), id="null"),
    pytest.param("v: !!binary aGk=", _tag("!!binary"), id="binary"),
    pytest.param("v: !foo bar", _tag("!foo"), id="local"),
    pytest.param(
        "v: !<tag:example.com,2026:x> 1", _tag("!<tag:example.com,2026:x>"), id="verbatim",
    ),
    pytest.param("v: !!str [a]", _tag("!!str", "remove it"), id="str-on-a-sequence"),
    pytest.param("v: !!seq [a]", _tag("!!seq", "remove it"), id="seq"),
    pytest.param("v: !!map {a: 1}", _tag("!!map", "remove it"), id="map"),
    pytest.param("v: !!set {a}", _tag("!!set", "remove it"), id="set"),
    pytest.param("v: !!omap [a: 1]", _tag("!!omap", "remove it"), id="omap"),
    # ruamel.yaml read the first as 8 and the third as a boolean it cannot construct.
    pytest.param("v: ! '08'", _tag("!", "remove it"), id="bang-quoted"),
    pytest.param("v: ! 010", _tag("!", "remove it"), id="bang-plain"),
    pytest.param("v: ! |\n  true\n", _tag("!", "remove it"), id="bang-block"),
    pytest.param("v: ! [x]", _tag("!", "remove it"), id="bang-sequence"),
    pytest.param("v: !<!> x", _tag("!", "remove it"), id="bang-verbatim"),
]


@pytest.mark.parametrize(("text", "why"), _TAGS)
def test_an_explicit_tag_is_refused(text: str, why: str) -> None:
    """A tag reads its value by rules of its own: `!!int "010"` turns quoted
    text into 10, `!!binary` gives bytes and `!!set` a set, none of which a
    reader here takes, and a bare `!` has ruamel.yaml read `'08'` as 8."""
    with pytest.raises(_yaml.TagOrDirectiveError) as err:
        _yaml.safe_load(text)
    assert isinstance(err.value, _yaml.PARSE_ERRORS)
    assert str(err.value) == f"{_HEADER}\n  line 1, column 4: {why}"


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("v: !!str 010", "010"),
        ("v: !!str yes", "yes"),
        ("v: !!str", ""),
        ("v: !<tag:yaml.org,2002:str> 1:30", "1:30"),
        ("v: !!str '08'", "08"),
    ],
)
def test_a_str_tag_on_a_scalar_is_text(text: str, value: str) -> None:
    assert _yaml.safe_load(text) == {"v": value}


@pytest.mark.parametrize(
    ("text", "name"),
    [
        pytest.param("%YAML 1.1\n---\nv: 1\n", "YAML", id="yaml-1.1"),
        pytest.param("%YAML 1.2\n---\nv: 1\n", "YAML", id="yaml-1.2"),
        pytest.param("%YAML 1.3\n---\nv: 1\n", "YAML", id="yaml-1.3"),
        pytest.param("%YAML 1.0\n---\nv: 1\n", "YAML", id="yaml-1.0"),
        pytest.param("%TAG !e! tag:example.com,2026:\n---\nv: 1\n", "TAG", id="tag"),
    ],
)
def test_a_version_or_tag_directive_is_refused(text: str, name: str) -> None:
    """`%YAML 1.1` switches a YAML 1.2 reader back to 1.1's readings, and
    `%TAG` can point `!!` anywhere. ruamel.yaml raises a bare AssertionError
    on `%YAML 1.3` and `%YAML 1.0`."""
    with pytest.raises(_yaml.TagOrDirectiveError) as err:
        _yaml.safe_load(text)
    assert str(err.value) == (
        f"{_HEADER}\n  line 1, column 1: the `%{name}` directive is refused, because the "
        "loader reads every file by one fixed set of rules; remove it"
    )


def test_a_reserved_directive_is_ignored_and_loads() -> None:
    assert _yaml.safe_load("%FOO bar\n---\nv: 1\n") == {"v": 1}


def test_every_refusal_in_a_document_is_named_in_its_order_up_to_twenty() -> None:
    """One build lists them all, rather than one per run. Past twenty the
    rest are counted, so a file tagged throughout stays readable."""
    text = "".join(f"k{n}: {'!!bool true' if n % 2 else '!!int 1'}\n" for n in range(25))
    with pytest.raises(_yaml.TagOrDirectiveError) as err:
        _yaml.safe_load(text)
    lines = str(err.value).splitlines()
    assert lines[0] == _HEADER
    assert [line.split(": the tag")[0] for line in lines[1:21]] == [
        f"  line {n + 1}, column {len(f'k{n}: ') + 1}" for n in range(20)
    ]
    assert lines[1].endswith(_tag("!!int"))
    assert lines[2].endswith(_tag("!!bool"))
    assert lines[21:] == ["  and 5 more"]
    assert len(err.value.found) == 25


#: A tag at line 1, column 4 of the document that holds it.
_TAGGED = "v: !!int 1"


def _found(line: int, column: int) -> str:
    """The refusal's line for the tag in `_TAGGED`, found at `line` and `column`."""
    return f"  line {line}, column {column}: {_tag('!!int')}"


def test_a_tag_is_refused_in_the_mapping_naming_the_file(tmp_path: Path) -> None:
    path = write_mapping(tmp_path, blocks(entities("Risk"), _TAGGED))
    with pytest.raises(MappingError) as err:
        load_mapping(path)
    assert type(err.value) is MappingSourceError
    assert isinstance(err.value.__cause__, _yaml.TagOrDirectiveError)
    assert str(err.value) == f"{path.resolve()}: {_HEADER}\n{_found(4, 4)}"


def test_a_tag_is_refused_inside_an_extensions_block(tmp_path: Path) -> None:
    """The block reaches its extension untyped, but it is still parsed."""
    path = write_mapping(
        tmp_path, blocks(entities("Risk"), f"extensions:\n  audit:\n    {_TAGGED}"),
    )
    with pytest.raises(MappingSourceError) as err:
        load_mapping(path)
    assert str(err.value) == f"{path.resolve()}: {_HEADER}\n{_found(6, 8)}"


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param("enum_sources:\n  topic: side.yaml", id="enum-source"),
        pytest.param("retention_policies_source: side.yaml", id="retention-source"),
        pytest.param("reporting_source: side.yaml", id="section-pointer"),
    ],
)
def test_a_tag_is_refused_in_a_file_the_mapping_names(tmp_path: Path, declaration: str) -> None:
    side = tmp_path / "side.yaml"
    side.write_text(f"{_TAGGED}\n", encoding="utf-8")
    path = write_mapping(tmp_path, blocks(entities("Risk"), declaration))
    with pytest.raises(MappingSourceError) as err:
        load_mapping(path)
    assert str(err.value) == f"{side.resolve()}: {_HEADER}\n{_found(1, 4)}"


def test_a_tag_is_refused_in_release_yaml_as_a_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """`release.yaml` is read with no wrapper, so the refusal reaches the CLI
    as the parser's own error, which `project.CONFIG_ERRORS` catches."""
    release = write_mapping(
        tmp_path,
        'release: "1.0.0"\ndate: "2026-01-01"\ndeployer_version: "dbml-sharepoint/0.1.0"\n'
        f'schema_version: "1.0.0"\n{_TAGGED}',
        prefix=None,
        name="release.yaml",
    )
    with pytest.raises(typer.Exit) as exit_:
        load_config(FIXTURES / "simple.dbml", FIXTURES / "sharepoint-mapping.yaml", release)
    assert exit_.value.exit_code == 1
    assert capsys.readouterr().err == f"[ERROR] release {release}: {_HEADER}\n{_found(5, 4)}\n"


def test_a_tag_is_refused_in_a_journey_s_front_matter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    journeys = tmp_path / catalogue.JOURNEYS_DIRNAME
    journeys.mkdir()
    journey = journeys / "j.md"
    journey.write_text(
        f"---\ntitle: J\nsummary: S\nsolutions: [a]\n{_TAGGED}\n---\n", encoding="utf-8",
    )
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    with pytest.raises(ValueError) as err:
        catalogue.available_journeys()
    assert str(err.value) == f"{journey}: front matter {_HEADER}\n{_found(5, 4)}"


def _refusal(text: str) -> str:
    """The parser's message for `text`, read as a stream so it carries no snippet."""
    with pytest.raises(_yaml.PARSE_ERRORS) as err:
        _yaml.safe_load(io.StringIO(text))
    return str(err.value)


def _refused(text: str) -> str:
    """The message for valid YAML `text` the loader refuses, which is its own class."""
    with pytest.raises(_yaml.RefusedYAMLError) as err:
        _yaml.safe_load(io.StringIO(text))
    return str(err.value)


def test_a_reused_anchor_is_refused_naming_both() -> None:
    """ruamel.yaml only warns and aliases the second, so a later `*x` would
    silently mean a different node."""
    assert _refused("a: &x 1\nb: &x 2\nc: *x\n") == (
        "found duplicate anchor 'x'; first occurrence\n"
        '  in "<file>", line 1, column 4\n'
        "second occurrence\n"
        '  in "<file>", line 2, column 4'
    )


@pytest.mark.parametrize(
    ("text", "kind", "at"),
    [
        pytest.param("{[a, b]: 1}\n", "sequence", "line 1, column 2", id="flow-sequence"),
        pytest.param("? [a, b]\n: 1\n", "sequence", "line 1, column 3", id="block-sequence"),
        pytest.param("? {a: 1}\n: 1\n", "mapping", "line 1, column 3", id="mapping"),
        pytest.param(
            "m: &m {a: 1}\n? *m\n: 1\n", "mapping", "line 2, column 3", id="aliased-mapping",
        ),
        pytest.param(
            "x: &a [1]\n? *a\n: 2\n", "sequence", "line 2, column 3", id="aliased-sequence",
        ),
    ],
)
def test_a_sequence_or_mapping_used_as_a_key_is_refused(text: str, kind: str, at: str) -> None:
    """ruamel.yaml would read a sequence key as a tuple. An aliased key is
    marked at the alias, where the author wrote the key, not at the anchor."""
    assert _refused(text) == (
        "while composing a mapping\n"
        '  in "<file>", line 1, column 1\n'
        f"found a {kind} used as a key; a key must be a single value\n"
        f'  in "<file>", {at}'
    )


@pytest.mark.parametrize(
    ("text", "anchor_at", "alias_at"),
    [
        pytest.param("a: &x [*x]\n", "line 1, column 4", "line 1, column 8", id="sequence"),
        pytest.param("a: &x {k: *x}\n", "line 1, column 4", "line 1, column 11", id="mapping"),
        pytest.param(
            "a: &x [1, [2, *x]]\n", "line 1, column 4", "line 1, column 15", id="nested-sequence",
        ),
        pytest.param(
            "a: &x\n  k:\n    j: *x\n", "line 1, column 4", "line 3, column 8", id="nested-mapping",
        ),
        pytest.param("a: &x {b: 1, <<: *x}\n", "line 1, column 4", "line 1, column 18", id="merge"),
        pytest.param("&x [*x]\n", "line 1, column 1", "line 1, column 5", id="document"),
    ],
)
def test_an_alias_inside_the_collection_it_names_is_refused(
    text: str, anchor_at: str, alias_at: str,
) -> None:
    """PyYAML and ruamel.yaml both read `&x [*x]` as a list that contains
    itself, and any walk of it, an extension's among them, never ends."""
    assert _refused(text) == (
        "while composing the collection anchored 'x'\n"
        f'  in "<file>", {anchor_at}\n'
        "found an alias to the anchor 'x' inside the collection it names\n"
        f'  in "<file>", {alias_at}'
    )


@pytest.mark.parametrize(
    ("text", "value"),
    [
        ("a: &x [1]\nb: *x\n", {"a": [1], "b": [1]}),
        ("a: &x [1]\nb: [*x, *x]\n", {"a": [1], "b": [[1], [1]]}),
        ("a: {x: &x [1], y: *x}\n", {"a": {"x": [1], "y": [1]}}),
        ("a: &x {k: 1}\nb: {<<: *x, j: 2}\n", {"a": {"k": 1}, "b": {"k": 1, "j": 2}}),
    ],
)
def test_an_alias_to_a_collection_already_composed_loads(
    text: str, value: dict[str, object],
) -> None:
    assert _yaml.safe_load(text) == value


def test_a_recursive_alias_in_an_extensions_block_is_refused_naming_the_file(
    tmp_path: Path,
) -> None:
    """The block reached its extension untouched, which then recursed without end."""
    path = write_mapping(
        tmp_path, blocks(entities("Risk"), "extensions:\n  audit: &x {k: *x}"),
    )
    with pytest.raises(MappingSourceError) as err:
        load_mapping(path)
    assert type(err.value.__cause__) is _yaml.RefusedYAMLError
    assert str(err.value) == (
        f"{path.resolve()}: is refused: while composing the collection anchored 'x'\n"
        f'  in "{path.resolve()}", line 5, column 10\n'
        "found an alias to the anchor 'x' inside the collection it names\n"
        f'  in "{path.resolve()}", line 5, column 17'
    )


#: Valid YAML the loader refuses, written as a top-level key's value at line 4, and its problem.
_REFUSED = [
    pytest.param("v: &x 1\nw: &x 2", "found duplicate anchor 'x'; first occurrence", id="anchor"),
    pytest.param("v: {[a]: 1}", "while composing a mapping", id="collection-key"),
    pytest.param("v: &x [*x]", "while composing the collection anchored 'x'", id="recursive"),
    pytest.param("v: " + "[" * 101 + "]" * 101, "found a sequence nested deeper", id="depth"),
]


@pytest.mark.parametrize(("text", "problem"), _REFUSED)
def test_valid_yaml_the_loader_refuses_is_worded_as_refused_not_invalid(
    tmp_path: Path, text: str, problem: str,
) -> None:
    path = write_mapping(tmp_path, blocks(entities("Risk"), text))
    with pytest.raises(MappingSourceError) as err:
        load_mapping(path)
    assert type(err.value.__cause__) is _yaml.RefusedYAMLError
    assert str(err.value).startswith(f"{path.resolve()}: is refused: {problem}")


@pytest.mark.parametrize(("text", "problem"), _REFUSED)
def test_valid_yaml_the_loader_refuses_in_release_yaml_is_a_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], text: str, problem: str,
) -> None:
    release = write_mapping(
        tmp_path,
        'release: "1.0.0"\ndate: "2026-01-01"\ndeployer_version: "dbml-sharepoint/0.1.0"\n'
        f'schema_version: "1.0.0"\n{text}',
        prefix=None,
        name="release.yaml",
    )
    with pytest.raises(typer.Exit) as exit_:
        load_config(FIXTURES / "simple.dbml", FIXTURES / "sharepoint-mapping.yaml", release)
    assert exit_.value.exit_code == 1
    assert capsys.readouterr().err.startswith(f"[ERROR] release {release}: {problem}")


@pytest.mark.parametrize(("text", "problem"), _REFUSED)
def test_valid_yaml_the_loader_refuses_in_a_journey_is_worded_as_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, text: str, problem: str,
) -> None:
    journeys = tmp_path / catalogue.JOURNEYS_DIRNAME
    journeys.mkdir()
    journey = journeys / "j.md"
    journey.write_text(f"---\ntitle: J\nsummary: S\n{text}\n---\n", encoding="utf-8")
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    with pytest.raises(ValueError) as err:
        catalogue.available_journeys()
    assert str(err.value).startswith(f"{journey}: front matter is refused: {problem}")


def test_nesting_is_bounded_before_the_interpreter_s_recursion_limit() -> None:
    """A RecursionError is no parse error, so it escaped every handler."""
    assert _yaml.safe_load("[" * 100 + "]" * 100) == _nested(100)
    for depth in (101, 5000):
        assert _refused("[" * depth + "]" * depth) == (
            "found a sequence nested deeper than 100 levels\n"
            '  in "<file>", line 1, column 101'
        )
    assert _refused("{a: " * 101 + "}" * 101) == (
        "found a mapping nested deeper than 100 levels\n"
        '  in "<file>", line 1, column 401'
    )


def _nested(depth: int) -> list[object]:
    """`depth` empty lists, each inside the next."""
    value: list[object] = []
    for _ in range(depth - 1):
        value = [value]
    return value


def _chain(links: int) -> str:
    """Anchors `a0` to `a<links>`, each a sequence holding an alias to the one before."""
    return "a0: &a0 []\n" + "".join(f"a{n}: &a{n} [*a{n - 1}]\n" for n in range(1, links + 1))


def test_nesting_is_bounded_through_an_alias() -> None:
    """The value built holds what an anchor names wherever its alias stands,
    so a chain of short aliases nested as deep as it was long. The
    collection named is the one that would stand at level 101."""
    assert _yaml.safe_load(_chain(98))["a98"] == _nested(99)
    for links in (99, 3000):
        assert _refused(_chain(links)) == (
            "found a sequence nested deeper than 100 levels\n"
            '  in "<file>", line 100, column 12'
        )
    assert _yaml.safe_load("x: &x {k: 1}\ny: " + "[" * 98 + "*x" + "]" * 98)["x"] == {"k": 1}
    assert _refused("x: &x {k: 1}\ny: " + "[" * 99 + "*x" + "]" * 99) == (
        "found a mapping nested deeper than 100 levels\n"
        '  in "<file>", line 2, column 103'
    )
    # `*m48` names a mapping, and the collection at level 101 inside it is a sequence.
    mixed = "m0: &m0 {k: []}\n" + "".join(
        f"m{n}: &m{n} {{k: [*m{n - 1}]}}\n" for n in range(1, 50)
    )
    assert _refused(mixed) == (
        "found a sequence nested deeper than 100 levels\n"
        '  in "<file>", line 50, column 16'
    )


@pytest.mark.parametrize(
    ("text", "problem", "at"),
    [
        pytest.param(
            "v: 2026-02-30", "cannot construct !!timestamp from '2026-02-30': ", "column 4",
            id="invalid-date",
        ),
        pytest.param(
            "2026-13-01: x", "cannot construct !!timestamp from '2026-13-01': ", "column 1",
            id="invalid-date-as-a-key",
        ),
        pytest.param(
            "v: 0o_", "cannot construct !!int from '0o_': invalid literal for int() with "
            "base 8: ''", "column 4", id="empty-octal",
        ),
    ],
)
def test_a_value_the_loader_cannot_construct_is_a_parse_error(
    text: str, problem: str, at: str,
) -> None:
    """A ValueError or KeyError from a constructor escaped every handler
    that catches the parser's errors, the catalogue's skip among them. A key
    is constructed too, to find repeats. Python words a bad date its own way
    in each version, so that part is not compared."""
    message = _refusal(text)
    assert message.startswith(problem), message
    assert message.endswith(f'\n  in "<file>", line 1, {at}'), message


def test_an_escape_past_the_last_character_is_a_parse_error() -> None:
    """ruamel.yaml's scanner let chr()'s ValueError escape every handler
    that catches the parser's errors. `\\U0010FFFF`, the last, loads."""
    assert _yaml.safe_load('v: "\\U0010FFFF"\n') == {"v": chr(0x10FFFF)}
    assert _refusal('v: "\\U00110000"\n') == (
        "while scanning a double-quoted scalar\n"
        '  in "<file>", line 1, column 4\n'
        "found an escape that names no character; the last is `\\U0010FFFF`\n"
        '  in "<file>", line 1, column 7'
    )


@pytest.mark.parametrize(
    ("before", "after", "column"),
    [pytest.param("1.", "", 9, id="minor"), pytest.param("", ".1", 7, id="major")],
)
def test_a_version_number_too_long_to_read_is_a_parse_error(
    before: str, after: str, column: int,
) -> None:
    """int() refuses more digits than Python's limit with a ValueError, which
    escaped as the escape above did. At the limit, the directive is refused
    as any `%YAML` is. 640 is the lowest limit Python accepts, and each
    number here is 1, written with leading zeros."""
    limit = sys.get_int_max_str_digits()
    sys.set_int_max_str_digits(640)
    try:
        at_limit = _refusal(f"%YAML {before}{'0' * 639}1{after}\n---\nv: 1\n")
        past_limit = _refusal(f"%YAML {before}{'0' * 640}1{after}\n---\nv: 1\n")
    finally:
        sys.set_int_max_str_digits(limit)
    assert at_limit.startswith(f"{_HEADER}\n  line 1, column 1: the `%YAML` directive")
    assert past_limit == (
        "while scanning a directive\n"
        '  in "<file>", line 1, column 1\n'
        "found a version number too long to read; remove the directive\n"
        f'  in "<file>", line 1, column {column}'
    )


def test_the_writer_keeps_order_width_and_unicode() -> None:
    """The options the extract passed are the writer's own now: keys in the
    order given, one line per long scalar, block style, and text as written."""
    long_text = "word " * 40
    written = _yaml.safe_dump({
        "z": 1, "a": [True, None, 2.5, 1e300], "t": long_text, "u": "Café",
        "d": dt.date(2026, 1, 2),
    })
    assert written == (
        f"z: 1\na:\n- true\n- null\n- 2.5\n- 1e+300\nt: '{long_text}'\nu: Café\nd: 2026-01-02\n"
    )


@pytest.mark.parametrize(
    "text",
    [
        "010", "0o10", "08", "1e3", "~", "null", "<<", "=", "2026-01-02", "true", "yes", "1:30",
        "0x1F",
    ],
)
def test_text_the_writer_writes_reads_back_as_the_same_text(text: str) -> None:
    """Each reads as another value, a merge or a value key under YAML 1.1 or
    1.2 when bare. `extract` writes text from a live list, as values and keys."""
    document = {"v": text, text: 1}
    assert repr(_yaml.safe_load(_yaml.safe_dump(document))) == repr(document)


def test_the_writer_double_quotes_a_string_holding_nel() -> None:
    """Extract writes text read from a live list. The writer single-quoted
    a string holding NEL (U+0085) and broke the line at it, so `a<NEL>b`
    read back as `a b`."""
    document = {"v": "a\x85b", "a\x85b": 1}
    written = _yaml.safe_dump(document)
    assert written == 'v: "a\\Nb"\n? "a\\Nb"\n: 1\n'
    assert repr(_yaml.safe_load(written)) == repr(document)


def test_a_template_a_parse_refuses_is_skipped_by_the_picker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The picker offers no prefix or lists for a mapping the build refuses."""
    head = f"{DEFAULT_PREFIX}\nentities:\n  Thing: {{}}\n".encode()
    for name, mapping_text in (
        ("good", head),
        ("tagged", head + b"locked: !!bool true\n"),
        ("unconstructable", head + b"when: 2026-02-30\n"),
        ("refused", head + b"loop: &x [*x]\n"),
        ("escape", head + b'note: "\\U00110000"\n'),
        # Latin-1, as an editor saving in a Windows code page writes it.
        ("undecodable", head + b"note: caf\xe9\n"),
    ):
        (tmp_path / name / "10-design").mkdir(parents=True)
        (tmp_path / name / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
        (tmp_path / name / "20-configure").mkdir()
        (tmp_path / name / "20-configure" / "mapping.yaml").write_bytes(mapping_text)
        (tmp_path / name / "pack.toml").write_text(manifest_text(name), encoding="utf-8")
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    found = {s.id: (s.prefix, s.lists) for s in catalogue.available_solutions()}
    assert found == {
        "good": ("APP_", ("Thing",)), "tagged": ("", ()), "unconstructable": ("", ()),
        "refused": ("", ()), "escape": ("", ()), "undecodable": ("", ()),
    }
