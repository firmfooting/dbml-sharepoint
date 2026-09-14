# src/dbml_sharepoint/model/sections/context.py
"""What one section family is allowed to see.

A family reads the top-level keys it declared in its registry entry and
nothing else. The runner builds one of these per family, holding only that
family's blocks, so a reader cannot reach a section it did not declare and
a section no family declared cannot be read. Holding those two directions
equal is what the registry is for.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbml_sharepoint.model.errors import MappingShapeError


@dataclass(frozen=True)
class SectionContext:
    """One family's view of the mapping being loaded.

    `blocks` holds those of the family's declared keys that the document
    actually carries, already taken from the file the family's pointer names
    when the mapping used one. An absent key is absent here too, and
    `required` refuses it.

    `loaded` is what earlier families produced, keyed by field name. It
    exists for the one dependency that crosses families: permissions expand
    the `{prefix}` placeholder, so identity runs first and permissions read
    `loaded["prefix"]`.
    """

    base_dir: Path
    keys: tuple[str, ...]
    blocks: Mapping[str, Any]
    loaded: Mapping[str, Any]

    def block(self, key: str, default: Any = None) -> Any:
        """The block under `key`, or `default` when the mapping omits it."""
        self._declared(key)
        return self.blocks.get(key, default)

    def required(self, key: str) -> Any:
        """The block under `key`, refusing a mapping that omits it.

        A `MappingShapeError` and not the bare `KeyError` this raised before
        #170: the class advertises "a required key absent" as one of its
        cases, and an absent `prefix:` or `entities:` is the most ordinary way
        a mapping is wrong, so a caller catching `MappingError` has to see it.
        The sentence is the one the CLI already printed for the KeyError.
        """
        self._declared(key)
        if key not in self.blocks:
            raise MappingShapeError(f"missing required key {key!r}")
        return self.blocks[key]

    def _declared(self, key: str) -> None:
        # A LookupError and not a KeyError: this is a defect in a family, not
        # in the mapping, and the CLI must keep the traceback for it.
        if key not in self.keys:
            raise LookupError(
                f"{key!r} is not a section this family declared; it reads {self.keys}",
            )
