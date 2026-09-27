# test/test_yaml_versions.py
"""What YAML 1.1 and 1.2 read differently is refused, not read either way (#686).

PyYAML reads YAML 1.1, where `off` is False, `010` is 8 and `1:30` is 90, and
YAML 1.2 reads all three as something else. A file does not say which version
it was written for, so `model/_yaml.py` refuses a value the two read
differently, naming each line and the spelling that keeps what it has meant.

Every expectation here is literal, measured on PyYAML 6.0.3 and on
ruamel.yaml 0.19.1 reading 1.2, and nothing here imports either library, so
the same cases hold whichever one parses.
"""

import datetime as dt
import io
import math
from pathlib import Path

import pytest
import typer
from _packs import DEFAULT_PREFIX, blocks, entities, write_mapping
from _paths import FIXTURES

from dbml_sharepoint import catalogue
from dbml_sharepoint.model import _yaml
from dbml_sharepoint.model.errors import MappingError, MappingSourceError
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.project import load_config

#: The guard refuses the value.
REFUSED = "refused"
#: Both versions read the value alike and cannot construct it, a parse error of another kind.
BROKEN = "broken"

_HEADER = "uses spellings YAML 1.1 and 1.2 read differently:"

#: A plain value and what both versions read it as, or REFUSED or BROKEN.
_READINGS: list[tuple[str, object]] = [
    # Booleans in YAML 1.1, in each case form it recognises, and text in 1.2.
    *[(word, REFUSED) for word in ("yes", "Yes", "YES", "no", "No", "NO")],
    *[(word, REFUSED) for word in ("on", "On", "ON", "off", "Off", "OFF")],
    # Text in both: 1.1 does not read a mixed case form, nor `y` and `n`.
    ("yEs", "yEs"), ("oN", "oN"), ("y", "y"), ("Y", "Y"), ("n", "n"), ("N", "N"),
    ("true", True), ("False", False), ("TRUE", True),
    # Octal in YAML 1.1 and decimal in 1.2.
    ("010", REFUSED), ("-010", REFUSED), ("+010", REFUSED), ("0_10", REFUSED), ("0777", REFUSED),
    # Octal digits both bases read as one number.
    ("0", 0), ("00", 0), ("07", 7), ("0_7", 7), ("-0", 0), ("+1", 1),
    # Text in YAML 1.1 and an int in 1.2, which cannot construct the last four.
    ("08", REFUSED), ("09", REFUSED), ("0_8", REFUSED), ("-08", REFUSED), ("0o10", REFUSED),
    ("0o_", REFUSED), ("-_", REFUSED), ("+_", REFUSED), ("-__", REFUSED),
    ("0o8", "0o8"), ("0O7", "0O7"), ("_1", "_1"),
    # Base 60 in YAML 1.1 and text in 1.2.
    ("1:30", REFUSED), ("1:30.5", REFUSED), ("-1:30", REFUSED), ("190:20:30", REFUSED),
    ("1_0:30", REFUSED), ("1:5", REFUSED),
    ("0:30", "0:30"), ("1:60", "1:60"),
    # Text in YAML 1.1 and a float in 1.2, which cannot construct `._` or `-._`.
    ("1e3", REFUSED), ("1E3", REFUSED), ("1e+3", REFUSED), ("1.0e3", REFUSED),
    ("1.5e3", REFUSED), ("1.e3", REFUSED), ("-1e3", REFUSED), ("-.5", REFUSED),
    ("+.5", REFUSED), ("._5", REFUSED), ("1_e3", REFUSED), ("1e999", REFUSED),
    ("._", REFUSED), ("-._", REFUSED),
    (".5e3", ".5e3"), ("1e", "1e"), ("1e3_", "1e3_"),
    # Numbers both read alike, among them ruamel.yaml's `1_000` and `0b101`.
    ("1_000", 1000), ("1__000", 1000), ("1_", 1), ("0b101", 5), ("-0b101", -5),
    ("0x1F", 31), ("-0x1F", -31), ("0X1F", "0X1F"), ("0B101", "0B101"),
    ("1.0e+3", 1000.0), ("1.5", 1.5), (".5", 0.5), ("1_0.5", 10.5), ("1.", 1.0),
    ("-0.0", -0.0), (".5_", 0.5), ("1._", 1.0),
    (".inf", math.inf), (".Inf", math.inf), (".INF", math.inf), ("-.inf", -math.inf),
    ("+.inf", math.inf), (".nan", math.nan), (".NaN", math.nan), (".NAN", math.nan),
    ("-.nan", "-.nan"), (".Nan", ".Nan"), (".iNF", ".iNF"), ("inf", "inf"), ("nan", "nan"),
    # Null in both.
    ("~", None), ("null", None), ("Null", None), ("NULL", None), ("", None), ("nULL", "nULL"),
    # Timestamps both read alike.
    ("2026-01-02", dt.date(2026, 1, 2)),
    ("2026-01-02T03:04:05", dt.datetime(2026, 1, 2, 3, 4, 5)),  # noqa: DTZ001
    ("2026-01-02 03:04:05Z", dt.datetime(2026, 1, 2, 3, 4, 5, tzinfo=dt.UTC)),
    ("2026-01-02T03:04:05.123456", dt.datetime(2026, 1, 2, 3, 4, 5, 123456)),  # noqa: DTZ001
    ("2026-01-02T03:04:05.5", dt.datetime(2026, 1, 2, 3, 4, 5, 500000)),  # noqa: DTZ001
    ("2026-1-2", "2026-1-2"),
    # Past six fraction digits 1.1 drops the rest, and 1.2 adds one to the sixth when the
    # seventh is 5 or more, carrying a fraction that reaches a million into the second.
    ("2026-01-02T03:04:05.1234564", dt.datetime(2026, 1, 2, 3, 4, 5, 123456)),  # noqa: DTZ001
    ("2026-01-02T03:04:05.1234560", dt.datetime(2026, 1, 2, 3, 4, 5, 123456)),  # noqa: DTZ001
    ("2026-01-02T03:04:05.9999994", dt.datetime(2026, 1, 2, 3, 4, 5, 999999)),  # noqa: DTZ001
    ("2026-01-02T03:04:05.12345649", dt.datetime(2026, 1, 2, 3, 4, 5, 123456)),  # noqa: DTZ001
    (
        "2026-01-02T03:04:05.12345612345678901234",
        dt.datetime(2026, 1, 2, 3, 4, 5, 123456),  # noqa: DTZ001
    ),
    ("2026-01-02T03:04:05.1234565", REFUSED), ("2026-01-02T03:04:05.1234567", REFUSED),
    ("2026-01-02T03:04:05.12345650", REFUSED), ("2026-01-02T03:04:05.00000050", REFUSED),
    ("2026-01-02T03:04:05.9999995", REFUSED), ("2026-01-02T03:04:05.9999999", REFUSED),
    ("2026-01-02T03:04:05.99999950000000000000", REFUSED),
    ("9999-12-31T23:59:59.9999995", REFUSED),
    # Read alike, and constructed by neither.
    ("0x_", BROKEN), ("0b_", BROKEN), ("2026-02-30", BROKEN), ("2026-01-02T25:00:00", BROKEN),
    ("2026-02-30T03:04:05.1234565", BROKEN),
]


@pytest.mark.parametrize(
    ("token", "reading"), [pytest.param(t, r, id=t or "empty") for t, r in _READINGS],
)
def test_a_plain_value_is_read_alike_by_both_versions_or_refused(
    token: str, reading: object,
) -> None:
    """The literal fuzz table: every class the two versions read apart, the
    spellings next to each that they read alike, and the tokens ruamel.yaml
    cannot construct. Only a refusal may stand where the readings differ."""
    text = f"v: {token}\n"
    if reading == REFUSED:
        with pytest.raises(_yaml.AmbiguousYAMLError):
            _yaml.safe_load(text)
        with pytest.raises(_yaml.AmbiguousYAMLError):
            _yaml.safe_load(f"{token}: v\n")
        return
    if reading == BROKEN:
        with pytest.raises(_yaml.PARSE_ERRORS) as err:
            _yaml.safe_load(text)
        assert not isinstance(err.value, _yaml.AmbiguousYAMLError)
        return
    value = _yaml.safe_load(text)["v"]
    assert type(value) is type(reading)
    if isinstance(reading, float):
        assert isinstance(value, float)
        if math.isnan(reading):
            assert math.isnan(value)
        else:
            assert (value, math.copysign(1, value)) == (reading, math.copysign(1, reading))
    else:
        assert value == reading
    if isinstance(reading, dt.datetime):
        assert isinstance(value, dt.datetime)
        # Compared by offset: the two libraries name a UTC zone differently.
        assert value.utcoffset() == reading.utcoffset()


#: One spelling of each class the guard refuses, and its line of the refusal.
_CLASSES = [
    pytest.param(
        "yes",
        '`yes` is read as a boolean until now and as text in YAML 1.2; write `true` to '
        'keep the boolean, or quote it ("yes") for text',
        id="boolean-true",
    ),
    pytest.param(
        "Off",
        '`Off` is read as a boolean until now and as text in YAML 1.2; write `false` to '
        'keep the boolean, or quote it ("Off") for text',
        id="boolean-false",
    ),
    pytest.param(
        "010",
        '`010` is read as the number 8 until now and as the number 10 in YAML 1.2; write 8 '
        'to keep the number, or quote it ("010") for text',
        id="octal",
    ),
    pytest.param(
        "08",
        '`08` is read as text until now and as the number 8 in YAML 1.2; quote it ("08") '
        "to keep the text, or write 8",
        id="text-then-int",
    ),
    pytest.param(
        "0o10",
        '`0o10` is read as text until now and as the number 8 in YAML 1.2; quote it '
        '("0o10") to keep the text, or write 8',
        id="text-then-0o-int",
    ),
    pytest.param(
        "-_",
        '`-_` is read as text until now and as a number YAML 1.2 cannot construct; quote '
        'it ("-_") to keep the text',
        id="text-then-no-number",
    ),
    pytest.param(
        "1:30",
        '`1:30` is read as the number 90 until now and as text in YAML 1.2; write 90 to '
        'keep the number, or quote it ("1:30") for text',
        id="base-60-int",
    ),
    pytest.param(
        "1:30.5",
        '`1:30.5` is read as the number 90.5 until now and as text in YAML 1.2; write '
        '90.5 to keep the number, or quote it ("1:30.5") for text',
        id="base-60-float",
    ),
    pytest.param(
        "1e3",
        '`1e3` is read as text until now and as the number 1000.0 in YAML 1.2; quote it '
        '("1e3") to keep the text, or write 1000.0',
        id="text-then-float",
    ),
    pytest.param(
        "-.5",
        '`-.5` is read as text until now and as the number -0.5 in YAML 1.2; quote it '
        '("-.5") to keep the text, or write -0.5',
        id="text-then-signed-float",
    ),
    pytest.param(
        "2026-01-02T03:04:05.1234567",
        "`2026-01-02T03:04:05.1234567` is read as the time 2026-01-02T03:04:05.123456 until "
        "now and as the time 2026-01-02T03:04:05.123457 in YAML 1.2; write "
        '`2026-01-02T03:04:05.123456` to keep the time, or quote it '
        '("2026-01-02T03:04:05.1234567") for text',
        id="long-fraction",
    ),
    pytest.param(
        "2026-01-02T03:04:05.9999995",
        "`2026-01-02T03:04:05.9999995` is read as the time 2026-01-02T03:04:05.999999 until "
        "now and as the time 2026-01-02T03:04:06 in YAML 1.2; write "
        '`2026-01-02T03:04:05.999999` to keep the time, or quote it '
        '("2026-01-02T03:04:05.9999995") for text',
        id="long-fraction-carried",
    ),
]


def _found(line: int, column: int, token: str, why: str) -> list[str]:
    """The refusal's lines for `token` written as a key at `column` and as its value."""
    return [
        f"  line {line}, column {column}: {why}",
        f"  line {line}, column {column + len(token) + 2}: {why}",
    ]


@pytest.mark.parametrize(("token", "why"), _CLASSES)
def test_each_class_is_named_as_a_key_and_as_a_value(token: str, why: str) -> None:
    """The reading until now leads, and the spelling that keeps it comes first."""
    with pytest.raises(_yaml.AmbiguousYAMLError) as err:
        _yaml.safe_load(f"{token}: {token}\n")
    assert isinstance(err.value, _yaml.PARSE_ERRORS)
    assert str(err.value) == "\n".join([_HEADER, *_found(1, 1, token, why)])


@pytest.mark.parametrize(("token", "why"), _CLASSES)
def test_each_class_is_refused_in_the_mapping_naming_the_file(
    tmp_path: Path, token: str, why: str,
) -> None:
    path = write_mapping(tmp_path, blocks(entities("Risk"), f"{token}: {token}"))
    with pytest.raises(MappingError) as err:
        load_mapping(path)
    assert type(err.value) is MappingSourceError
    assert isinstance(err.value.__cause__, _yaml.AmbiguousYAMLError)
    assert str(err.value) == "\n".join([f"{path.resolve()}: {_HEADER}", *_found(4, 1, token, why)])


@pytest.mark.parametrize(("token", "why"), _CLASSES)
def test_each_class_is_refused_inside_an_extensions_block(
    tmp_path: Path, token: str, why: str,
) -> None:
    """The block reaches its extension untyped, but it is still parsed."""
    path = write_mapping(
        tmp_path, blocks(entities("Risk"), f"extensions:\n  audit:\n    {token}: {token}"),
    )
    with pytest.raises(MappingSourceError) as err:
        load_mapping(path)
    assert str(err.value) == "\n".join([f"{path.resolve()}: {_HEADER}", *_found(6, 5, token, why)])


@pytest.mark.parametrize(
    "declaration",
    [
        pytest.param("enum_sources:\n  topic: side.yaml", id="enum-source"),
        pytest.param("retention_policies_source: side.yaml", id="retention-source"),
        pytest.param("reporting_source: side.yaml", id="section-pointer"),
    ],
)
@pytest.mark.parametrize(("token", "why"), _CLASSES)
def test_each_class_is_refused_in_a_file_the_mapping_names(
    tmp_path: Path, declaration: str, token: str, why: str,
) -> None:
    side = tmp_path / "side.yaml"
    side.write_text(f"{token}: {token}\n", encoding="utf-8")
    path = write_mapping(tmp_path, blocks(entities("Risk"), declaration))
    with pytest.raises(MappingSourceError) as err:
        load_mapping(path)
    assert str(err.value) == "\n".join([f"{side.resolve()}: {_HEADER}", *_found(1, 1, token, why)])


@pytest.mark.parametrize(("token", "why"), _CLASSES)
def test_each_class_is_refused_in_release_yaml_as_a_config_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], token: str, why: str,
) -> None:
    """`release.yaml` is read with no wrapper, so the refusal reaches the CLI
    as the parser's own error, which `project.CONFIG_ERRORS` catches."""
    release = write_mapping(
        tmp_path,
        'release: "1.0.0"\ndate: "2026-01-01"\ndeployer_version: "dbml-sharepoint/0.1.0"\n'
        f'schema_version: "1.0.0"\n{token}: {token}',
        prefix=None,
        name="release.yaml",
    )
    with pytest.raises(typer.Exit) as exit_:
        load_config(FIXTURES / "simple.dbml", FIXTURES / "sharepoint-mapping.yaml", release)
    assert exit_.value.exit_code == 1
    assert capsys.readouterr().err == "\n".join(
        [f"[ERROR] release {release}: {_HEADER}", *_found(5, 1, token, why), ""],
    )


@pytest.mark.parametrize(("token", "why"), _CLASSES)
def test_each_class_is_refused_in_a_journey_s_front_matter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str, why: str,
) -> None:
    journeys = tmp_path / catalogue.JOURNEYS_DIRNAME
    journeys.mkdir()
    journey = journeys / "j.md"
    journey.write_text(
        f"---\ntitle: J\nsummary: S\nsolutions: [a]\n{token}: {token}\n---\n", encoding="utf-8",
    )
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    with pytest.raises(ValueError) as err:
        catalogue.available_journeys()
    assert str(err.value) == "\n".join(
        [f"{journey}: front matter {_HEADER}", *_found(5, 1, token, why)],
    )


def test_every_refusal_in_a_document_is_named_in_its_order_up_to_twenty() -> None:
    """One build lists them all, rather than one per run. Past twenty the
    rest are counted, so a file written for YAML 1.1 throughout stays readable."""
    text = "".join(f"k{n}: {'yes' if n % 2 else '010'}\n" for n in range(25))
    with pytest.raises(_yaml.AmbiguousYAMLError) as err:
        _yaml.safe_load(text)
    lines = str(err.value).splitlines()
    assert lines[0] == _HEADER
    assert [line.split(":")[0] for line in lines[1:21]] == [
        f"  line {n + 1}, column {len(f'k{n}: ') + 1}" for n in range(20)
    ]
    assert lines[1].endswith('quote it ("010") for text')
    assert lines[2].endswith('quote it ("yes") for text')
    assert lines[21:] == ["  and 5 more"]
    assert len(err.value.found) == 25


def test_a_number_too_long_to_write_is_refused_without_its_readings() -> None:
    """Past Python's 4,300-digit limit neither reading can be written, and a
    base-60 float past a float's range overflows in YAML 1.1 itself."""
    octal = "0" + "7" * 4400
    base_60 = "1" + ":00" * 180 + ".5"
    for token in (octal, base_60):
        with pytest.raises(_yaml.AmbiguousYAMLError) as err:
            _yaml.safe_load(f"v: {token}\n")
        assert str(err.value) == (
            f"{_HEADER}\n  line 1, column 4: `{token[:40]}...` is a number too long to "
            "compare between YAML 1.1 and 1.2; quote it for text"
        )


@pytest.mark.parametrize(
    ("token", "was", "now", "kept"),
    [
        pytest.param(
            "2026-01-02 03:04:05.12345678 +10:00", "2026-01-02T03:04:05.123456+10:00",
            "as the time 2026-01-02T03:04:05.123457+10:00 in YAML 1.2",
            "2026-01-02 03:04:05.123456 +10:00", id="zoned",
        ),
        pytest.param(
            "2026-12-31T23:59:59.9999995Z", "2026-12-31T23:59:59.999999+00:00",
            "as the time 2027-01-01T00:00:00+00:00 in YAML 1.2",
            "2026-12-31T23:59:59.999999Z", id="carried-into-the-year",
        ),
        pytest.param(
            "9999-12-31T23:59:59.9999995", "9999-12-31T23:59:59.999999",
            "as a time YAML 1.2 cannot construct", "9999-12-31T23:59:59.999999",
            id="carried-past-the-last-time",
        ),
    ],
)
def test_a_long_fraction_is_refused_naming_both_times(
    token: str, was: str, now: str, kept: str,
) -> None:
    """The fix keeps the author's spelling and cuts the fraction to the six
    digits YAML 1.1 has read. ruamel.yaml raises where the carry passes the
    last time a datetime holds."""
    with pytest.raises(_yaml.AmbiguousYAMLError) as err:
        _yaml.safe_load(f"v: {token}\n")
    assert str(err.value) == (
        f"{_HEADER}\n  line 1, column 4: `{token}` is read as the time {was} until now and "
        f'{now}; write `{kept}` to keep the time, or quote it ("{token}") for text'
    )


#: The end of a scalar tag's refusal, where removing the tag leaves the guard to read the value.
_SCALAR_FIX = " to read the value as though untagged, or write `!!str` for text"

#: An explicit tag and where its value sits; every tag but `!!str` on a scalar is refused.
_TAGS = [
    pytest.param("v: !!int 010", "!!int", _SCALAR_FIX, id="int"),
    pytest.param('v: !!int "010"', "!!int", _SCALAR_FIX, id="int-quoted"),
    pytest.param("v: !!bool y", "!!bool", _SCALAR_FIX, id="bool"),
    pytest.param("v: !!float 1e3", "!!float", _SCALAR_FIX, id="float"),
    pytest.param("v: !!null x", "!!null", _SCALAR_FIX, id="null"),
    pytest.param("v: !!binary aGk=", "!!binary", _SCALAR_FIX, id="binary"),
    pytest.param("v: !foo bar", "!foo", _SCALAR_FIX, id="local"),
    pytest.param("v: !<tag:example.com,2026:x> 1", "!<tag:example.com,2026:x>",
                 _SCALAR_FIX, id="verbatim"),
    pytest.param("v: !!str [a]", "!!str", "", id="str-on-a-sequence"),
    pytest.param("v: !!seq [a]", "!!seq", "", id="seq"),
    pytest.param("v: !!map {a: 1}", "!!map", "", id="map"),
    pytest.param("v: !!set {a}", "!!set", "", id="set"),
    pytest.param("v: !!omap [a: 1]", "!!omap", "", id="omap"),
]


@pytest.mark.parametrize(("text", "tag", "scalar_fix"), _TAGS)
def test_an_explicit_tag_is_refused(text: str, tag: str, scalar_fix: str) -> None:
    """`!!int 010` is 8 in YAML 1.1 and 10 in 1.2 even quoted, and `!!bool y`
    was a KeyError in PyYAML, so a tag is not a way around the guard."""
    with pytest.raises(_yaml.AmbiguousYAMLError) as err:
        _yaml.safe_load(text)
    assert str(err.value) == (
        f"{_HEADER}\n  line 1, column 4: the tag `{tag}` is refused, because YAML 1.1 and "
        f"1.2 construct tagged values differently; remove it{scalar_fix}"
    )


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
def test_a_str_tag_on_a_scalar_is_text_in_both_versions(text: str, value: str) -> None:
    assert _yaml.safe_load(text) == {"v": value}


@pytest.mark.parametrize(
    ("text", "found"),
    [
        pytest.param("v: ! 010", "`010` is read as the number 8", id="plain"),
        pytest.param('v: ! "010"', "`010` is read as the number 8", id="double-quoted"),
        pytest.param("v: ! '08'", "`08` is read as text", id="single-quoted"),
        pytest.param("v: ! |\n  1:30\n", "`1:30\\n` is read as the number 90", id="literal"),
    ],
)
def test_a_non_specific_tag_is_resolved_like_a_plain_value_and_guarded(
    text: str, found: str,
) -> None:
    """`!` asks the resolver to read the text, and both libraries then read
    it as though it were plain, quotes and all."""
    with pytest.raises(_yaml.AmbiguousYAMLError) as err:
        _yaml.safe_load(text)
    assert str(err.value).startswith(f"{_HEADER}\n  line 1, column 4: {found} until now")


def test_a_boolean_yaml_1_1_could_not_construct_is_refused_as_failing_to_load() -> None:
    """With `!` a block scalar keeps its line break. YAML 1.1 resolves `yes\\n`
    as a boolean and then finds no boolean spelled that way, and ruamel.yaml
    reads the text, so the refusal cannot say the file read a boolean."""
    with pytest.raises(_yaml.AmbiguousYAMLError) as err:
        _yaml.safe_load("v: ! |\n  yes\n")
    assert str(err.value) == (
        f"{_HEADER}\n  line 1, column 4: `yes\\n` fails to load until now and is read as "
        'text in YAML 1.2; quote it ("yes\\n") for text'
    )


def test_a_non_specific_tag_both_versions_read_alike_loads() -> None:
    assert _yaml.safe_load("a: ! '1.5'\nb: ! [x]\n") == {"a": 1.5, "b": ["x"]}


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
    on `%YAML 1.3` and `%YAML 1.0`, which PyYAML reads."""
    with pytest.raises(_yaml.AmbiguousYAMLError) as err:
        _yaml.safe_load(text)
    assert str(err.value) == (
        f"{_HEADER}\n  line 1, column 1: the `%{name}` directive is refused, because the "
        "loader reads every file by one fixed set of rules; remove it"
    )


def test_a_reserved_directive_is_ignored_by_both_versions_and_loads() -> None:
    assert _yaml.safe_load("%FOO bar\n---\nv: 1\n") == {"v": 1}


def _refusal(text: str) -> str:
    """The parser's message for `text`, read as a stream so it carries no snippet."""
    with pytest.raises(_yaml.PARSE_ERRORS) as err:
        _yaml.safe_load(io.StringIO(text))
    return str(err.value)


def test_a_reused_anchor_is_refused_naming_both() -> None:
    """ruamel.yaml only warns and aliases the second, so a later `*x` would
    silently mean a different node."""
    assert _refusal("a: &x 1\nb: &x 2\nc: *x\n") == (
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
        pytest.param("m: &m {a: 1}\n? *m\n: 1\n", "mapping", "line 1, column 4", id="alias"),
    ],
)
def test_a_sequence_or_mapping_used_as_a_key_is_refused(text: str, kind: str, at: str) -> None:
    """ruamel.yaml reads a sequence key as a tuple where PyYAML refuses it."""
    assert _refusal(text) == (
        "while composing a mapping\n"
        '  in "<file>", line 1, column 1\n'
        f"found a {kind} used as a key; a key must be a single value\n"
        f'  in "<file>", {at}'
    )


def test_nesting_is_bounded_before_the_interpreter_s_recursion_limit() -> None:
    """A RecursionError is no parse error, so it escaped every handler."""
    assert _yaml.safe_load("[" * 100 + "]" * 100) == _nested(100)
    for depth in (101, 5000):
        assert _refusal("[" * depth + "]" * depth) == (
            "found a sequence nested deeper than 100 levels\n"
            '  in "<file>", line 1, column 101'
        )
    assert _refusal("{a: " * 101 + "}" * 101) == (
        "found a mapping nested deeper than 100 levels\n"
        '  in "<file>", line 1, column 401'
    )


def _nested(depth: int) -> list[object]:
    """`depth` empty lists, each inside the next."""
    value: list[object] = []
    for _ in range(depth - 1):
        value = [value]
    return value


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
            "v: 0x_", "cannot construct !!int from '0x_': invalid literal for int() with "
            "base 16: ''", "column 4", id="empty-hex",
        ),
        pytest.param(
            "v: ! |\n  true\n", "cannot construct !!bool from 'true\\n': 'true\\n'", "column 4",
            id="bool-with-a-line-break",
        ),
    ],
)
def test_a_value_neither_version_can_construct_is_a_parse_error(
    text: str, problem: str, at: str,
) -> None:
    """A ValueError or KeyError from a constructor escaped every handler
    that catches the parser's errors, the catalogue's skip among them. A key
    is constructed too, to find repeats. Python words a bad date its own way
    in each version, so that part is not compared."""
    message = _refusal(text)
    assert message.startswith(problem), message
    assert message.endswith(f'\n  in "<file>", line 1, {at}'), message


def test_a_template_a_parse_refuses_is_skipped_by_the_picker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The picker offers no prefix or lists for a mapping the build refuses."""
    for name, mapping_text in (
        ("good", f"{DEFAULT_PREFIX}\nentities:\n  Thing: {{}}\n"),
        ("read-differently", f"{DEFAULT_PREFIX}\nentities:\n  Thing: {{}}\nlocked: yes\n"),
        ("unconstructable", f"{DEFAULT_PREFIX}\nentities:\n  Thing: {{}}\nwhen: 2026-02-30\n"),
    ):
        (tmp_path / name / "10-design").mkdir(parents=True)
        (tmp_path / name / "10-design" / "schema.dbml").write_text("", encoding="utf-8")
        (tmp_path / name / "20-configure").mkdir()
        (tmp_path / name / "20-configure" / "mapping.yaml").write_text(
            mapping_text, encoding="utf-8",
        )
    monkeypatch.setattr(catalogue, "SOLUTIONS_DIR", tmp_path)
    found = {s.id: (s.prefix, s.lists) for s in catalogue.available_solutions()}
    assert found == {
        "good": ("APP_", ("Thing",)), "read-differently": ("", ()), "unconstructable": ("", ()),
    }
