# src/dbml_sharepoint/model/_yaml.py
"""The YAML parser every file this package reads goes through.

It reads with ruamel.yaml 0.19.1's pure-Python safe loader, which reads
YAML 1.2: `yes`, `no`, `on` and `off` are text, `010` is 10 and `1:30` is
text. Until 2026-09 every file here was read by PyYAML, which reads YAML
1.1, where those are a boolean, 8 and 90. ruamel.yaml reads `1_000` and
`0b101` as numbers, as YAML 1.1 does, where the YAML 1.2 core schema
reads them as text.

The YAML spec requires the keys of a mapping to be unique. ruamel.yaml
checks, but not in a mapping that merges another nor inside the merged
one, so this loader refuses a repeated key itself (#672). It also refuses
an explicit tag and a `%YAML` or `%TAG` directive, which would read a
value by other rules, and the valid YAML `RefusedYAMLError` names (#686).

A leaf that imports only `ruamel.yaml`, so every module that parses YAML
can use it without importing another's parser. The mapping reader, the
release reader and the catalogue import none of one another; the wizard
imports the catalogue and the mapping loader, and parses one line of its
own through this module. `_keys.py` is shared across the parsers the same
way, though it imports `model.errors` and so is not a leaf.
"""

import datetime as dt
import io
from collections.abc import Hashable
from typing import IO, Any, override

from ruamel.yaml import YAML
from ruamel.yaml.composer import Composer, ComposerError
from ruamel.yaml.constructor import ConstructorError, SafeConstructor
from ruamel.yaml.error import FileMark, StreamMark, YAMLError
from ruamel.yaml.events import AliasEvent, CollectionStartEvent, ScalarEvent
from ruamel.yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode
from ruamel.yaml.representer import SafeRepresenter
from ruamel.yaml.scanner import Scanner, ScannerError
from ruamel.yaml.tokens import DirectiveToken

#: What a parse of malformed YAML raises, so a caller can catch it without ruamel.yaml.
PARSE_ERRORS: tuple[type[YAMLError]] = (YAMLError,)

#: The tag ruamel.yaml gives `<<`, the merge key.
_MERGE_TAG = "tag:yaml.org,2002:merge"

_STR = "tag:yaml.org,2002:str"
_TIME = "tag:yaml.org,2002:timestamp"

#: How deep a document may nest, well inside the interpreter's recursion limit.
_MAX_DEPTH = 100

#: How many refusals one error lists before it counts the rest.
_MAX_LISTED = 20

#: NEL (U+0085), by code point so no string literal here holds a character a console cannot print.
_NEL = chr(0x85)


def _tag_name(tag: str) -> str:
    """`tag` as an author would write it."""
    if tag.startswith("tag:yaml.org,2002:"):
        return "!!" + tag.removeprefix("tag:yaml.org,2002:")
    return tag if tag.startswith("!") else f"!<{tag}>"


class TagOrDirectiveError(YAMLError):
    """A document that writes an explicit tag or a directive the loader refuses.

    Every one found is listed with its line, up to `_MAX_LISTED`, so one run
    names them all. `str()` begins "uses tags or directives", so a caller
    can prefix the file's path.
    """

    def __init__(self, found: list[tuple[StreamMark, str]]) -> None:
        self.found = tuple(found)
        # Marks count from zero; the line an author reads counts from one.
        lines = [
            f"  line {mark.line + 1}, column {mark.column + 1}: {why}"
            for mark, why in found[:_MAX_LISTED]
        ]
        if len(found) > _MAX_LISTED:
            lines.append(f"  and {len(found) - _MAX_LISTED} more")
        super().__init__("\n".join(["uses tags or directives the loader refuses:", *lines]))

    def moved(self, line: int, column: int) -> "TagOrDirectiveError":
        """This refusal of a fragment cut from a file, placed where the fragment starts there.

        `line` and `column` count from zero, as a mark does. Only the
        fragment's first line is offset by `column`.
        """
        return TagOrDirectiveError([
            (
                FileMark(
                    mark.name, mark.index, mark.line + line,
                    mark.column + (column if mark.line == 0 else 0),
                ),
                why,
            )
            for mark, why in self.found
        ])


class RefusedYAMLError(ComposerError):
    """Valid YAML the loader refuses as it composes the document.

    A reused anchor, a sequence or mapping used as a key, an alias inside
    the collection its anchor names, and nesting deeper than `_MAX_DEPTH`.
    The YAML spec allows each; the loader refuses them because ruamel.yaml
    would build a value no reader here expects or can finish walking. `str()`
    is the marked message, so a caller can prefix the file's path.
    """


def _found(loader: Any) -> list[tuple[StreamMark, str]]:
    """The refusals `_Reading` collects for the document its parts are reading."""
    found: list[tuple[StreamMark, str]] = loader.found
    return found


class _Scanner(Scanner):
    """ruamel.yaml's scanner, refusing a `%YAML` or `%TAG` directive as it reads one.

    `%YAML 1.1` would switch ruamel.yaml to YAML 1.1's rules for the rest of
    the file, and `%TAG` can point `!!` anywhere. The scanner sees a
    directive first, before ruamel.yaml acts on it. Two ValueErrors that
    ruamel.yaml's scanner lets escape are raised as a `ScannerError`.
    """

    @override
    def scan_yaml_directive_number(self, start_mark: Any) -> int:
        try:
            number: int = super().scan_yaml_directive_number(start_mark)
        except ValueError as exc:
            # int() refuses more digits than sys.get_int_max_str_digits() allows.
            raise ScannerError(
                "while scanning a directive", start_mark,
                "found a version number too long to read; remove the directive",
                self.reader.get_mark(),
            ) from exc
        return number

    @override
    def scan_flow_scalar_non_spaces(self, double: Any, start_mark: Any) -> Any:
        try:
            return super().scan_flow_scalar_non_spaces(double, start_mark)
        except ValueError as exc:
            # chr() refuses an escape past U+10FFFF, which only `\U` can spell.
            raise ScannerError(
                "while scanning a double-quoted scalar", start_mark,
                "found an escape that names no character; the last is `\\U0010FFFF`",
                self.reader.get_mark(),
            ) from exc

    @override
    def scan_directive(self) -> DirectiveToken:
        token: DirectiveToken = super().scan_directive()
        if token.name in {"YAML", "TAG"}:
            why = (
                f"the `%{token.name}` directive is refused, because the loader reads every "
                "file by one fixed set of rules; remove it"
            )
            _found(self.loader).append((token.start_mark, why))
        if token.name == "YAML":
            # The scanner and parser would switch to the version named, and assert on 1.0 or 1.3.
            self.yaml_version = None
            if token.value[0] == 1:
                token.value = (1, 2)
        return token


class _Composer(Composer):
    """ruamel.yaml's composer, refusing explicit tags and the valid YAML it will not read.

    The tag check runs as each node is composed, from the parser's event: a
    node cannot say whether its tag was written or resolved. It refuses
    every explicit tag, a bare `!` among them, but `!!str` on a scalar, and
    collects them with the scanner's refused directives before one
    `TagOrDirectiveError`. What `RefusedYAMLError` names is refused as it is
    found, among it an alias inside the collection its anchor names, which
    ruamel.yaml would read as a collection that contains itself.
    """

    def __init__(self, loader: Any = None) -> None:
        super().__init__(loader)
        self._depth = 0
        # The anchor of each collection still being composed, and where it starts.
        self._enclosing: dict[str, StreamMark] = {}

    def _refuse_tag(self, tag: str, mark: StreamMark, *, scalar: bool) -> None:
        """Record an explicit `tag`, which would read its value by rules of its own."""
        # Removing a bare `!` is the whole fix: ruamel.yaml reads `! '08'` as 8 and `'08'` as text.
        fix = (
            "remove it to read the value as though untagged, or write `!!str` for text"
            if scalar and tag != "!" else "remove it"
        )
        why = (
            f"the tag `{_tag_name(tag)}` is refused, because the loader reads every value "
            f"by one fixed set of rules; {fix}"
        )
        _found(self.loader).append((mark, why))

    @override
    def compose_scalar_node(self, anchor: Any) -> ScalarNode:
        event: ScalarEvent = self.parser.peek_event()
        tag: str | None = event.tag
        if tag is not None and tag != _STR:
            self._refuse_tag(tag, event.start_mark, scalar=True)
        node: ScalarNode = super().compose_scalar_node(anchor)
        return node

    @override
    def compose_node(self, parent: Any, index: Any) -> Any:
        event = self.parser.peek_event()
        if isinstance(event, AliasEvent) and event.anchor in self._enclosing:
            # ruamel.yaml would hand back the open collection, which would then contain itself.
            raise RefusedYAMLError(
                f"while composing the collection anchored {event.anchor!r}",
                self._enclosing[event.anchor],
                f"found an alias to the anchor {event.anchor!r} inside the collection it names",
                event.start_mark,
            )
        if isinstance(event, ScalarEvent | CollectionStartEvent) and event.anchor in self.anchors:
            # ruamel.yaml only warns, and would alias the second; these are PyYAML's words.
            first: Node = self.anchors[event.anchor]
            raise RefusedYAMLError(
                f"found duplicate anchor {event.anchor!r}; first occurrence",
                first.start_mark, "second occurrence", event.start_mark,
            )
        return super().compose_node(parent, index)

    def _open(self, kind: str) -> str | None:
        """Enter a sequence or mapping, refusing an explicit tag and nesting past the limit.

        Returns its anchor, which no alias inside it may name.
        """
        event: CollectionStartEvent = self.parser.peek_event()
        if self._depth == _MAX_DEPTH:
            raise RefusedYAMLError(
                None, None, f"found a {kind} nested deeper than {_MAX_DEPTH} levels",
                event.start_mark,
            )
        self._depth += 1
        tag: str | None = event.tag
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
    def compose_sequence_node(self, anchor: Any) -> SequenceNode:
        name = self._open("sequence")
        node: SequenceNode = super().compose_sequence_node(anchor)
        self._close(name)
        return node

    @override
    def compose_mapping_node(self, anchor: Any) -> MappingNode:
        name = self._open("mapping")
        node: MappingNode = super().compose_mapping_node(anchor)
        self._close(name)
        pairs: list[tuple[Node, Node]] = node.value
        for key_node, _ in pairs:
            # ruamel.yaml reads a sequence key as a tuple, where PyYAML refused it.
            if not isinstance(key_node, ScalarNode):
                kind = "sequence" if isinstance(key_node, SequenceNode) else "mapping"
                raise RefusedYAMLError(
                    "while composing a mapping", node.start_mark,
                    f"found a {kind} used as a key; a key must be a single value",
                    key_node.start_mark,
                )
        return node


class UniqueKeyConstructor(SafeConstructor):
    """ruamel.yaml's safe constructor, refusing a repeated key and any construction error.

    A key written beside a merge (`<<: *anchor`) is not a repeat. It overrides
    the merged key, as the merge-key spec documents, and the shipped
    programme-governance mapping widens one column of a merged view that way.
    A second `<<` in one mapping is a repeat, and PyYAML settled a clash
    between two of them the opposite way to the list form `<<: [*a, *b]`.

    The repeat check runs in `flatten_mapping`, the first place a mapping's
    pairs are rewritten. A mapping used as a merge source is flattened into
    its user before it is constructed itself, so a check in
    `construct_mapping` would miss a repeat inside the source and read the
    merged pairs of a nested merge as repeats. It runs before ruamel.yaml's
    own check, which skips a mapping that merges.
    """

    def __init__(self, preserve_quotes: bool | None = None, loader: Any = None) -> None:
        super().__init__(preserve_quotes, loader)
        # A mapping is checked once: flattening rewrites its pairs in place.
        self._checked: set[MappingNode] = set()

    @override
    def get_single_data(self) -> Any:
        node: Node | None = self.composer.get_single_node()
        if found := _found(self.loader):
            raise TagOrDirectiveError(found)
        return None if node is None else self.construct_document(node)

    @override
    def construct_yaml_timestamp(self, node: Any, values: Any = None) -> Any:
        stamp: dt.date = super().construct_yaml_timestamp(node, values)
        if isinstance(stamp, dt.datetime) and (offset := stamp.utcoffset()) is not None:
            # ruamel.yaml names the zone as written, which `repr` shows; PyYAML's was unnamed.
            return stamp.replace(tzinfo=dt.timezone(offset))
        return stamp

    @override
    def construct_object(self, node: Any, deep: bool = False) -> Any:
        try:
            return super().construct_object(node, deep)
        except (ValueError, KeyError, IndexError, OverflowError, AssertionError) as exc:
            built: Node = node
            # So every caller's YAML handler sees it, where a bare ValueError escaped them.
            raise ConstructorError(
                None, None,
                f"cannot construct {_tag_name(str(built.tag))} from {built.value!r}: {exc}",
                built.start_mark,
            ) from exc

    @override
    def flatten_mapping(self, node: Any) -> Any:
        if node in self._checked:
            return super().flatten_mapping(node)
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
        return None

    def _refuse_repeats(self, node: MappingNode, written: list[Node]) -> None:
        """Raise on the second of two keys in `written` that construct equal."""
        first: dict[Hashable, tuple[Hashable, Node]] = {}
        for key_node in written:
            # A key is a scalar, refused otherwise as it was composed, so it constructs hashable.
            key: Hashable = self.construct_object(key_node)
            if key in first:
                raise _repeat(node, first[key], (key, key_node))
            first[key] = (key, key_node)


UniqueKeyConstructor.add_constructor(_TIME, UniqueKeyConstructor.construct_yaml_timestamp)


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


class _Reading(YAML):
    """One read of one document: ruamel.yaml's pure-Python safe loader, with these parts.

    Built per read, because ruamel.yaml keeps the version a `%YAML` directive
    names on this object, and because the refusals its parts find collect here.
    """

    def __init__(self) -> None:
        super().__init__(typ="safe", pure=True)
        self.Scanner = _Scanner
        self.Composer = _Composer
        self.Constructor = UniqueKeyConstructor
        #: What the parts refused, raised together once the document is composed.
        self.found: list[tuple[StreamMark, str]] = []


def safe_load(stream: str | IO[str]) -> Any:
    """ruamel.yaml's safe load, with the refusals the module docstring lists."""
    return _Reading().load(stream)


class _Representer(SafeRepresenter):
    """ruamel.yaml's safe representer, double-quoting a string that holds NEL (U+0085)."""

    @override
    def represent_str(self, data: Any) -> ScalarNode:
        if _NEL in data:
            # Single-quoted, the writer breaks the line at NEL, and `a<NEL>b` reads back as `a b`.
            node: ScalarNode = self.represent_scalar(_STR, data, style='"')
            return node
        represented: ScalarNode = super().represent_str(data)
        return represented


_Representer.add_representer(str, _Representer.represent_str)


def safe_dump(data: object) -> str:
    """`data` as YAML for an operator to edit and diff.

    ruamel.yaml's safe writer quotes a string its reader would read as
    another type, so the output reads back through `safe_load` unchanged.
    A string holding NEL is double-quoted, which writes it as `\\N`. Keys
    keep their order, text is written as it is, and `width` is effectively
    off: the default wraps a long scalar across lines, which is legal YAML
    and unreadable in a diff, since a one-word edit to a validation message
    reflows the whole block.
    """
    writer = YAML(typ="safe", pure=True)
    writer.Representer = _Representer
    writer.default_flow_style = False
    writer.sort_base_mapping_type_on_output = False
    writer.allow_unicode = True
    writer.width = 10_000
    written = io.StringIO()
    writer.dump(data, written)
    return written.getvalue()
