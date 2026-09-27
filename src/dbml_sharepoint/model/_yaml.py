# src/dbml_sharepoint/model/_yaml.py
"""The YAML parser every file this package reads goes through.

`yaml.safe_load` keeps the last of two identical keys in a mapping and reports
nothing, so a second declaration silently replaced the first (#672). The YAML
spec requires the keys of a mapping to be unique; PyYAML does not enforce it,
so this loader does.

PyYAML reads YAML 1.1, where `off` is a boolean, `010` is 8 and `1:30` is 90.
YAML 1.2 reads all three differently, and a file does not say which version
it was written for, so a value the two read differently is refused rather
than read either way (#686). The 1.2 reading compared is ruamel.yaml
0.19.1's, which reads `1_000` and `0b101` as numbers, as YAML 1.1 does.

A leaf that imports only `yaml`, so every module that parses YAML can use it
without importing another's parser. The mapping reader, the release reader
and the catalogue import none of one another; the wizard imports the
catalogue and the mapping loader, and parses one line of its own through
this module. `_keys.py` is shared across the parsers the same way, though it
imports `model.errors` and so is not a leaf.
"""

import datetime as dt
import json
import math
import re
from collections.abc import Callable, Hashable
from typing import IO, Any, override

import yaml
from yaml.composer import ComposerError
from yaml.constructor import ConstructorError
from yaml.error import Mark
from yaml.events import AliasEvent, CollectionStartEvent, Event, ScalarEvent
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from yaml.tokens import DirectiveToken

#: What a parse of malformed YAML raises, so a caller can catch it without PyYAML.
PARSE_ERRORS: tuple[type[yaml.YAMLError]] = (yaml.YAMLError,)

#: The tag PyYAML gives `<<`, the merge key.
_MERGE_TAG = "tag:yaml.org,2002:merge"

_STR = "tag:yaml.org,2002:str"
_BOOL = "tag:yaml.org,2002:bool"
_FLOAT = "tag:yaml.org,2002:float"
_INT = "tag:yaml.org,2002:int"

#: A version's implicit resolvers: a tag, its pattern and the first characters it is tried on.
type _Table = tuple[tuple[str, re.Pattern[str], frozenset[str]], ...]

#: PyYAML 6.0.3's resolvers for the three tags YAML 1.2 changed, copied from its
#: `resolver.py` in the order it tries them. Its null, merge, timestamp and value
#: resolvers are the same as ruamel.yaml's, and are tried after these.
_YAML_1_1: _Table = (
    (
        _BOOL,
        re.compile(r'''^(?:yes|Yes|YES|no|No|NO
                    |true|True|TRUE|false|False|FALSE
                    |on|On|ON|off|Off|OFF)$''', re.VERBOSE),
        frozenset('yYnNtTfFoO'),
    ),
    (
        _FLOAT,
        re.compile(r'''^(?:[-+]?(?:[0-9][0-9_]*)\.[0-9_]*(?:[eE][-+][0-9]+)?
                    |\.[0-9][0-9_]*(?:[eE][-+][0-9]+)?
                    |[-+]?[0-9][0-9_]*(?::[0-5]?[0-9])+\.[0-9_]*
                    |[-+]?\.(?:inf|Inf|INF)
                    |\.(?:nan|NaN|NAN))$''', re.VERBOSE),
        frozenset('-+0123456789.'),
    ),
    (
        _INT,
        re.compile(r'''^(?:[-+]?0b[0-1_]+
                    |[-+]?0[0-7_]+
                    |[-+]?(?:0|[1-9][0-9_]*)
                    |[-+]?0x[0-9a-fA-F_]+
                    |[-+]?[1-9][0-9_]*(?::[0-5]?[0-9])+)$''', re.VERBOSE),
        frozenset('-+0123456789'),
    ),
)

#: ruamel.yaml 0.19.1's YAML 1.2 resolvers for the same three tags, copied from
#: its `resolver.py` in the order it tries them.
_YAML_1_2: _Table = (
    (
        _BOOL,
        re.compile('''^(?:true|True|TRUE|false|False|FALSE)$''', re.VERBOSE),
        frozenset('tTfF'),
    ),
    (
        _FLOAT,
        re.compile('''^(?:
         [-+]?(?:[0-9][0-9_]*)\\.[0-9_]*(?:[eE][-+]?[0-9]+)?
        |[-+]?(?:[0-9][0-9_]*)(?:[eE][-+]?[0-9]+)
        |[-+]?\\.[0-9_]+(?:[eE][-+][0-9]+)?
        |[-+]?\\.(?:inf|Inf|INF)
        |\\.(?:nan|NaN|NAN))$''', re.VERBOSE),
        frozenset('-+0123456789.'),
    ),
    (
        _INT,
        re.compile('''^(?:[-+]?0b[0-1_]+
        |[-+]?0o?[0-7_]+
        |[-+]?[0-9_]+
        |[-+]?0x[0-9a-fA-F_]+)$''', re.VERBOSE),
        frozenset('-+0123456789'),
    ),
)

#: The timestamp resolver both libraries share, copied from PyYAML 6.0.3.
_TIMESTAMP = re.compile(r'''^(?:[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]
                    |[0-9][0-9][0-9][0-9] -[0-9][0-9]? -[0-9][0-9]?
                     (?:[Tt]|[ \t]+)[0-9][0-9]?
                     :[0-9][0-9] :[0-9][0-9] (?:\.[0-9]*)?
                     (?:[ \t]*(?:Z|[-+][0-9][0-9]?(?::[0-9][0-9])?))?)$''', re.VERBOSE)

#: PyYAML 6.0.3's `SafeConstructor.timestamp_regexp`, which splits what the resolver matched.
_TIME_PARTS = re.compile(r'''^(?P<year>[0-9][0-9][0-9][0-9])
                -(?P<month>[0-9][0-9]?)
                -(?P<day>[0-9][0-9]?)
                (?:(?:[Tt]|[ \t]+)
                (?P<hour>[0-9][0-9]?)
                :(?P<minute>[0-9][0-9])
                :(?P<second>[0-9][0-9])
                (?:\.(?P<fraction>[0-9]*))?
                (?:[ \t]*(?P<tz>Z|(?P<tz_sign>[-+])(?P<tz_hour>[0-9][0-9]?)
                (?::(?P<tz_minute>[0-9][0-9]))?))?)?$''', re.VERBOSE)

#: The keys of PyYAML 6.0.3's `SafeConstructor.bool_values`, which it looks a boolean up in.
_BOOLEANS_1_1 = frozenset({"yes", "no", "true", "false", "on", "off"})

#: A fraction's digits past the sixth, cut to spell the time PyYAML has read.
_LONG_FRACTION = re.compile(r"(\.[0-9]{6})[0-9]+")

#: An int both versions read, in digits YAML 1.1 takes as octal.
_OCTAL = re.compile(r"^[-+]?0[0-7_]+$")

#: How deep a document may nest, well inside the interpreter's recursion limit.
_MAX_DEPTH = 100

#: How many refusals one error lists before it counts the rest.
_MAX_LISTED = 20


def _tag(table: _Table, value: str) -> str | None:
    """The tag `table` resolves a plain `value` to, or None where it resolves none of the three."""
    for tag, pattern, first in table:
        # A resolver is tried only on a value whose first character it lists, so `_1` is text.
        if value[:1] in first and pattern.match(value):
            return tag
    return None


def _shown(value: str) -> str:
    """`value` as a double-quoted YAML scalar, which is also how a message quotes it."""
    return json.dumps(value, ensure_ascii=False)


def _spelling(number: float) -> str:
    """`number` written so that YAML 1.1 and 1.2 both read it back as itself."""
    if isinstance(number, int):
        return str(number)
    if math.isinf(number):
        return ".inf" if number > 0 else "-.inf"
    text = repr(number)
    mantissa, exponent, power = text.partition("e")
    # YAML 1.1 reads `1e+300` as text; its float needs a dot in the mantissa.
    return f"{mantissa}.0e{power}" if exponent and "." not in mantissa else text


def _sexagesimal(tag: str, value: str) -> float:
    """The number PyYAML 6.0.3 constructs from a base-60 `value`, such as 90 from `1:30`."""
    digits = value.replace("_", "")
    sign = -1 if digits[0] == "-" else 1
    convert: Callable[[str], float] = float if tag == _FLOAT else int
    number: float = 0
    base = 1
    for part in reversed(digits.lstrip("+-").split(":")):
        number += convert(part) * base
        base *= 60
    return sign * number


def _number_1_2(tag: str, value: str) -> float:
    """The number ruamel.yaml 0.19.1 reads from a `value` YAML 1.1 read as text.

    Raises ValueError where ruamel.yaml fails too, as it does on `-_` and `._`.
    """
    digits = value.replace("_", "")
    if tag == _FLOAT:
        return float(digits)
    sign = -1 if digits[:1] == "-" else 1
    digits = digits.lstrip("+-")
    base = 8 if digits.startswith("0o") else 10
    return sign * int(digits[2:] if base == 8 else digits, base)


def _refusal(value: str) -> str | None:
    """Why a `value` the resolver reads is refused, or None where YAML 1.1 and 1.2 agree.

    The regexes admit six disagreements and no more: a 1.1 boolean that 1.2
    reads as text, a 1.1 base-60 int or float that 1.2 reads as text, a 1.1
    text that 1.2 reads as an int or a float, and an int whose digits 1.1
    reads as octal. A timestamp whose seventh fraction digit is 5 or more is
    the one value both tag alike and construct differently.
    """
    was, now = _tag(_YAML_1_1, value), _tag(_YAML_1_2, value)
    if was == now and not (was == _INT and _OCTAL.match(value)):
        return _timestamp_refusal(value) if was is None and _TIMESTAMP.match(value) else None
    if was == _BOOL:
        if value.lower() not in _BOOLEANS_1_1:
            # A `!` block scalar keeps its line break, which the resolver takes and the lookup not.
            return (
                f"`{_shown(value)[1:-1]}` fails to load until now and is read as text in "
                f"YAML 1.2; quote it ({_shown(value)}) for text"
            )
        word = "true" if value.lower() in {"yes", "on"} else "false"
        return (
            f"`{_shown(value)[1:-1]}` is read as a boolean until now and as text in YAML 1.2; "
            f"write `{word}` to keep the boolean, or quote it ({_shown(value)}) for text"
        )
    try:
        return _number_refusal(value, was, now)
    except (ValueError, OverflowError):
        # Past Python's 4,300-digit limit or a float's range, so a reading cannot be written.
        return (
            f"`{_shown(value)[1:41]}...` is a number too long to compare between YAML 1.1 "
            "and 1.2; quote it for text"
        )


def _number_refusal(value: str, was: str | None, now: str | None) -> str | None:
    """Why a number YAML 1.1 or 1.2 reads is refused, or None for an octal both read alike.

    Raises ValueError or OverflowError for a number too long to write.
    """
    shown, quoted = _shown(value)[1:-1], _shown(value)
    if was == now:
        digits = value.replace("_", "")
        octal, decimal = int(digits, 8), int(digits, 10)
        if octal == decimal:
            return None
        return (
            f"`{shown}` is read as the number {octal} until now and as the number "
            f"{decimal} in YAML 1.2; write {octal} to keep the number, "
            f"or quote it ({quoted}) for text"
        )
    if now is None:
        number = _spelling(_sexagesimal(was or _INT, value))
        return (
            f"`{shown}` is read as the number {number} until now and as text in YAML 1.2; "
            f"write {number} to keep the number, or quote it ({quoted}) for text"
        )
    try:
        constructed = _number_1_2(now, value)
    except ValueError:
        return (
            f"`{shown}` is read as text until now and as a number YAML 1.2 cannot "
            f"construct; quote it ({quoted}) to keep the text"
        )
    number = _spelling(constructed)
    return (
        f"`{shown}` is read as text until now and as the number {number} in YAML 1.2; "
        f"quote it ({quoted}) to keep the text, or write {number}"
    )


def _timestamp_refusal(value: str) -> str | None:
    """Why a timestamp is refused, or None where both versions construct the same time.

    PyYAML 6.0.3 keeps six fraction digits and drops the rest. ruamel.yaml
    0.19.1 adds one to the sixth when the seventh is 5 or more, and carries
    a fraction that reaches a million into the second, so only then do the
    two differ.
    """
    parts = _TIME_PARTS.match(value)
    if parts is None or len(fraction := parts["fraction"] or "") < 7 or fraction[6] < "5":
        return None
    try:
        was = _time_1_1(parts)
    except ValueError:
        # Neither version constructs it, and the constructor's error names why.
        return None
    try:
        now = f"as the time {(was + dt.timedelta(microseconds=1)).isoformat()} in YAML 1.2"
    except OverflowError:
        # The carry passes the last time a datetime holds, and ruamel.yaml raises.
        now = "as a time YAML 1.2 cannot construct"
    kept = _shown(_LONG_FRACTION.sub(r"\1", value, count=1))[1:-1]
    return (
        f"`{_shown(value)[1:-1]}` is read as the time {was.isoformat()} until now and {now}; "
        f"write `{kept}` to keep the time, or quote it ({_shown(value)}) for text"
    )


def _time_1_1(parts: re.Match[str]) -> dt.datetime:
    """The time PyYAML 6.0.3 constructs from a timestamp's `parts`, its fraction cut to six."""
    tzinfo: dt.tzinfo | None = None
    if parts["tz_sign"]:
        offset = dt.timedelta(hours=int(parts["tz_hour"]), minutes=int(parts["tz_minute"] or 0))
        tzinfo = dt.timezone(-offset if parts["tz_sign"] == "-" else offset)
    elif parts["tz"]:
        tzinfo = dt.UTC
    return dt.datetime(
        int(parts["year"]), int(parts["month"]), int(parts["day"]), int(parts["hour"]),
        int(parts["minute"]), int(parts["second"]), int(parts["fraction"][:6].ljust(6, "0")),
        tzinfo=tzinfo,
    )


def _written_tag(tag: str | None) -> str | None:
    """The tag an event carries when its author wrote one; `!` only asks for the resolver."""
    return None if tag in {None, "!"} else tag


def _tag_name(tag: str) -> str:
    """`tag` as an author would write it."""
    if tag.startswith("tag:yaml.org,2002:"):
        return "!!" + tag.removeprefix("tag:yaml.org,2002:")
    return tag if tag.startswith("!") else f"!<{tag}>"


class AmbiguousYAMLError(yaml.YAMLError):
    """A document that uses spellings YAML 1.1 and 1.2 read differently.

    Every one found is listed with its line, up to `_MAX_LISTED`, so one run
    names them all. `str()` begins "uses spellings", so a caller can prefix
    the file's path.
    """

    def __init__(self, found: list[tuple[Mark, str]]) -> None:
        self.found = tuple(found)
        # Marks count from zero; the line an author reads counts from one.
        lines = [
            f"  line {mark.line + 1}, column {mark.column + 1}: {why}"
            for mark, why in found[:_MAX_LISTED]
        ]
        if len(found) > _MAX_LISTED:
            lines.append(f"  and {len(found) - _MAX_LISTED} more")
        super().__init__("\n".join(["uses spellings YAML 1.1 and 1.2 read differently:", *lines]))

    def moved(self, line: int, column: int) -> "AmbiguousYAMLError":
        """This refusal of a fragment cut from a file, placed where the fragment starts there.

        `line` and `column` count from zero, as a mark does. Only the
        fragment's first line is offset by `column`.
        """
        return AmbiguousYAMLError([
            (
                Mark(
                    mark.name, mark.index, mark.line + line,
                    mark.column + (column if mark.line == 0 else 0), None, 0,
                ),
                why,
            )
            for mark, why in self.found
        ])


class UniqueKeyLoader(yaml.SafeLoader):
    """`yaml.SafeLoader`, refusing a repeated key and what YAML 1.2 reads differently.

    A key written beside a merge (`<<: *anchor`) is not a repeat. It overrides
    the merged key, as the merge-key spec documents, and the shipped
    programme-governance mapping widens one column of a merged view that way.
    A second `<<` in one mapping is a repeat, and PyYAML settles a clash
    between two of them the opposite way to the list form `<<: [*a, *b]`.

    The repeat check runs in `flatten_mapping`, the first place a mapping's
    pairs are rewritten. A mapping used as a merge source is flattened into
    its user before it is constructed itself, so a check in
    `construct_mapping` would miss a repeat inside the source and read the
    merged pairs of a nested merge as repeats.

    The version check runs as each node is composed, from the parser's event:
    a node cannot say whether its tag was written or resolved. It refuses a
    resolved scalar the two versions read differently, every explicit tag but
    `!!str` on a scalar, and a `%YAML` or `%TAG` directive, and collects them
    all before one `AmbiguousYAMLError`. A sequence or mapping used as a key
    is refused as it is found, and so is an alias inside the collection its
    anchor names, which PyYAML reads as a collection that contains itself.
    """

    def __init__(self, stream: str | IO[str]) -> None:
        # Set before the scanner starts, which may read a directive.
        self._found: list[tuple[Mark, str]] = []
        self._depth = 0
        # The anchor of each collection still being composed, and where it starts.
        self._enclosing: dict[str, Mark] = {}
        super().__init__(stream)
        # A mapping is checked once: flattening rewrites its pairs in place.
        self._checked: set[MappingNode] = set()

    @override
    def scan_directive(self) -> DirectiveToken:
        token = super().scan_directive()
        if token.name in {"YAML", "TAG"}:
            why = (
                f"the `%{token.name}` directive is refused, because the loader reads every "
                "file by one fixed set of rules; remove it"
            )
            self._found.append((token.start_mark, why))
        return token

    def _refuse_tag(self, tag: str, mark: Mark, *, scalar: bool) -> None:
        """Record an explicit `tag`, which the two versions may construct differently."""
        fix = (
            "remove it to read the value as though untagged, or write `!!str` for text"
            if scalar else "remove it"
        )
        why = (
            f"the tag `{_tag_name(tag)}` is refused, because YAML 1.1 and 1.2 construct "
            f"tagged values differently; {fix}"
        )
        self._found.append((mark, why))

    @override
    def compose_scalar_node(self, anchor: dict[Any, Node]) -> ScalarNode:
        event: ScalarEvent = self.peek_event()
        tag = _written_tag(event.tag)
        if tag is None:
            # A `!` scalar is resolved from its text like a plain one, even when quoted.
            if event.implicit[0] and (why := _refusal(event.value)) is not None:
                self._found.append((event.start_mark, why))
        elif tag != _STR:
            self._refuse_tag(tag, event.start_mark, scalar=True)
        return super().compose_scalar_node(anchor)

    @override
    def compose_node(self, parent: Node | None, index: int) -> Node | None:
        event: Event = self.peek_event()
        if isinstance(event, AliasEvent) and event.anchor in self._enclosing:
            # PyYAML would hand back the open collection, which would then contain itself.
            raise ComposerError(
                f"while composing the collection anchored {event.anchor!r}",
                self._enclosing[event.anchor],
                f"found an alias to the anchor {event.anchor!r} inside the collection it names",
                event.start_mark,
            )
        return super().compose_node(parent, index)

    def _open(self, kind: str) -> str | None:
        """Enter a sequence or mapping, refusing an explicit tag and nesting past the limit.

        Returns its anchor, which no alias inside it may name.
        """
        event: CollectionStartEvent = self.peek_event()
        if self._depth == _MAX_DEPTH:
            raise ComposerError(
                None, None, f"found a {kind} nested deeper than {_MAX_DEPTH} levels",
                event.start_mark,
            )
        self._depth += 1
        tag = _written_tag(event.tag)
        if tag is not None:
            self._refuse_tag(tag, event.start_mark, scalar=False)
        anchor: str | None = event.anchor
        if anchor is not None:
            self._enclosing[anchor] = event.start_mark
        return anchor

    def _close(self, anchor: str | None) -> None:
        """Leave the sequence or mapping `_open` entered."""
        self._depth -= 1
        if anchor is not None:
            del self._enclosing[anchor]

    @override
    def compose_sequence_node(self, anchor: dict[Any, Node]) -> SequenceNode:
        name = self._open("sequence")
        node = super().compose_sequence_node(anchor)
        self._close(name)
        return node

    @override
    def compose_mapping_node(self, anchor: dict[Any, Node]) -> MappingNode:
        name = self._open("mapping")
        node = super().compose_mapping_node(anchor)
        self._close(name)
        pairs: list[tuple[Node, Node]] = node.value
        for key_node, _ in pairs:
            # ruamel.yaml reads a sequence key as a tuple, where PyYAML refuses it.
            if not isinstance(key_node, ScalarNode):
                kind = "sequence" if isinstance(key_node, SequenceNode) else "mapping"
                raise ComposerError(
                    "while composing a mapping", node.start_mark,
                    f"found a {kind} used as a key; a key must be a single value",
                    key_node.start_mark,
                )
        return node

    @override
    def get_single_data(self) -> Any:
        node = self.get_single_node()
        if self._found:
            raise AmbiguousYAMLError(self._found)
        return None if node is None else self.construct_document(node)

    @override
    def construct_object(self, node: Node, deep: bool = False) -> Any:
        try:
            return super().construct_object(node, deep)
        except (ValueError, KeyError, IndexError, OverflowError, AssertionError) as exc:
            # So every caller's YAML handler sees it, where a bare ValueError escaped them.
            raise ConstructorError(
                None, None, f"cannot construct {_tag_name(node.tag)} from {node.value!r}: {exc}",
                node.start_mark,
            ) from exc

    @override
    def flatten_mapping(self, node: MappingNode) -> None:
        if node in self._checked:
            super().flatten_mapping(node)
            return
        self._checked.add(node)
        pairs: list[tuple[Node, Node]] = node.value
        merges = [key_node for key_node, _ in pairs if key_node.tag == _MERGE_TAG]
        if len(merges) > 1:
            # A merge key has no constructor, so it is named by its spelling.
            raise _repeat(node, ("<<", merges[0]), ("<<", merges[1]))
        written = [key_node for key_node, _ in pairs if key_node.tag != _MERGE_TAG]
        # After the flatten, which retags a `=` key as text; constructing it before fails.
        super().flatten_mapping(node)
        self._refuse_repeats(node, written)

    def _refuse_repeats(self, node: MappingNode, written: list[Node]) -> None:
        """Raise on the second of two keys in `written` that construct equal."""
        first: dict[Hashable, tuple[Hashable, Node]] = {}
        for key_node in written:
            # A key is a scalar, refused otherwise as it was composed, so it constructs hashable.
            key: Hashable = self.construct_object(key_node)
            if key in first:
                raise _repeat(node, first[key], (key, key_node))
            first[key] = (key, key_node)


def _repeat(
    node: MappingNode, first: tuple[Hashable, Node], second: tuple[Hashable, Node],
) -> ConstructorError:
    """The refusal of the second of two keys of `node` that read as equal."""
    (was, first_node), (key, key_node) = first, second
    # Marks count from zero; the line printed under the error counts from one.
    first_line, line = first_node.start_mark.line + 1, key_node.start_mark.line + 1
    problem = f"found duplicate key {key!r} (first at line {first_line})"
    if not isinstance(key, str) and first_node.value != key_node.value:
        # `True` and `true` are two spellings to the author and one boolean to the parser.
        read = (
            f"both read as {key!r}" if repr(was) == repr(key)
            else f"read as {was!r} and {key!r}, which are equal"
        )
        problem = (
            f"found duplicate key {key!r}: {first_node.value!r} (line {first_line}) and "
            f"{key_node.value!r} (line {line}) {read}; quote them"
        )
    return ConstructorError(
        "while constructing a mapping", node.start_mark, problem, key_node.start_mark,
    )


def safe_load(stream: str | IO[str]) -> Any:
    """`yaml.safe_load`, refusing a repeated key and what YAML 1.2 reads differently."""
    loader = UniqueKeyLoader(stream)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()


class _Dumper(yaml.SafeDumper):
    """`yaml.SafeDumper`, quoting a string YAML 1.2 would read as another type too."""


for _tag_rule, _pattern, _first in _YAML_1_2:
    _Dumper.add_implicit_resolver(_tag_rule, _pattern, sorted(_first))


def safe_dump(data: object) -> str:
    """`data` as YAML for an operator to edit and diff.

    A string either YAML version would read as another type is quoted, so
    the output reads back through `safe_load` unrefused and unchanged. Keys
    keep their order, and `width` is effectively off: the default wraps a
    long scalar across lines, which is legal YAML and unreadable in a diff,
    since a one-word edit to a validation message reflows the whole block.
    """
    dumped: str = yaml.dump(
        data, Dumper=_Dumper, sort_keys=False, default_flow_style=False,
        allow_unicode=True, width=10_000,
    )
    return dumped
