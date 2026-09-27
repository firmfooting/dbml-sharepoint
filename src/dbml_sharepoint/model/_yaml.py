# src/dbml_sharepoint/model/_yaml.py
"""The YAML parser every file this package reads goes through.

`yaml.safe_load` keeps the last of two identical keys in a mapping and reports
nothing, so a second declaration silently replaced the first (#672). The YAML
spec requires the keys of a mapping to be unique; PyYAML does not enforce it,
so this loader does.

A leaf importing only `yaml`, for the reason `_keys.py` is one: the mapping
loader, the release reader, the catalogue and the wizard all parse YAML, and
none of them may import another.
"""

from collections.abc import Hashable
from typing import IO, Any, override

import yaml
from yaml.constructor import ConstructorError
from yaml.nodes import MappingNode, Node

#: The tag PyYAML gives `<<`, the merge key.
_MERGE_TAG = "tag:yaml.org,2002:merge"


class UniqueKeyLoader(yaml.SafeLoader):
    """`yaml.SafeLoader`, refusing a key written twice in one mapping.

    A key written beside a merge (`<<: *anchor`) is not a repeat. It overrides
    the merged key, as the merge-key spec documents, and the shipped
    programme-governance mapping widens one column of a merged view that way.
    A second `<<` in one mapping is a repeat, and PyYAML settles a clash
    between two of them the opposite way to the list form `<<: [*a, *b]`.

    The check runs in `flatten_mapping`, the first place a mapping's pairs are
    rewritten. A mapping used as a merge source is flattened into its user
    before it is constructed itself, so a check in `construct_mapping` would
    miss a repeat inside the source and read the merged pairs of a nested
    merge as repeats.
    """

    def __init__(self, stream: str | IO[str]) -> None:
        super().__init__(stream)
        # A mapping is checked once: flattening rewrites its pairs in place.
        self._checked: set[MappingNode] = set()

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
            raise _repeat(node, "<<", merges[0], merges[1])
        written = [key_node for key_node, _ in pairs if key_node.tag != _MERGE_TAG]
        # After the flatten, which retags a `=` key as text; constructing it before fails.
        super().flatten_mapping(node)
        self._refuse_repeats(node, written)

    def _refuse_repeats(self, node: MappingNode, written: list[Node]) -> None:
        """Raise on the second of two keys in `written` that construct equal."""
        first: dict[Hashable, Node] = {}
        for key_node in written:
            key: object = self.construct_object(key_node)
            # SafeLoader's own "found unhashable key" follows in construct_mapping.
            if not isinstance(key, Hashable):
                continue
            if key in first:
                raise _repeat(node, key, first[key], key_node)
            first[key] = key_node


def _repeat(node: MappingNode, key: object, first: Node, second: Node) -> ConstructorError:
    """The refusal of `second`, a key of `node` that reads as `key` as `first` did."""
    # Marks count from zero; the line printed under the error counts from one.
    first_line = first.start_mark.line + 1
    return ConstructorError(
        "while constructing a mapping", node.start_mark,
        f"found duplicate key {key!r} (first at line {first_line})",
        second.start_mark,
    )


def safe_load(stream: str | IO[str]) -> Any:
    """`yaml.safe_load`, refusing a key written twice in one mapping."""
    loader = UniqueKeyLoader(stream)
    try:
        return loader.get_single_data()
    finally:
        loader.dispose()
