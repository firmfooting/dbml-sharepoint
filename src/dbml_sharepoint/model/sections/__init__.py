# src/dbml_sharepoint/model/sections/__init__.py
"""Mapping sections, one module per family.

``load_mapping`` was a single function of about 320 lines parsing most
sections inline, in a module of 1,550. Each family of top-level keys now
lives in its own module behind the same ``read(sc) -> dict`` signature: it
takes a :class:`SectionContext` holding only the keys it declared and
returns the ``Mapping`` (or ``MappingBundle``) fields it produces. A reader
looking for one section opens one file, and that file holds the section's
shape check and typed construction together. Semantics stay in the
validator, the line ``_parse_derived_column`` drew before the split.

SECTION_FAMILIES is ordered, and the order is part of the contract: a
family sees what earlier families produced through ``sc.loaded``, and
permissions expand the ``{prefix}`` placeholder that identity reads, so
identity comes first. With several defects in one mapping the first family
to refuse is the one reported. Append rather than reorder.

The registry IS the allow-list. ``KNOWN_SECTIONS`` is derived from it, so a
key is admitted only by the family that reads it, and a test holds each
family to reading exactly the keys it declared. That replaces a hand-kept
set that once admitted two sections nothing read.

A family may carry a pointer, ``source``: an optional key whose value names
a file beside the mapping holding the family's sections and nothing else.
``reporting_source`` was the first and ``demo_source`` the second. The
resolution is generic, so each is a registry entry rather than a copy.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from dbml_sharepoint.model._keys import _reject_unknown_keys, _require_mapping
from dbml_sharepoint.model.mapping_types import _REMOVED_SECTIONS
from dbml_sharepoint.model.sections import (
    _columns,
    _demo,
    _display_names,
    _entities,
    _extensions,
    _formatting,
    _forms,
    _identity,
    _list_settings,
    _permissions,
    _reporting,
    _retired,
    _sources,
    _views,
)
from dbml_sharepoint.model.sections.context import SectionContext


@dataclass(frozen=True)
class Section:
    """One family of top-level mapping keys and the reader that parses them."""

    #: The top-level keys the family reads. Each is admitted by the loader
    #: because it is listed here, and no key belongs to two families.
    keys: tuple[str, ...]
    read: Callable[[SectionContext], dict[str, Any]]
    #: The pointer that may move `keys` into a file beside the mapping.
    source: str | None = None


SECTION_FAMILIES: tuple[Section, ...] = (
    Section(("prefix", "prefix_owner", "previous_prefixes"), _identity.read),
    Section(("entities",), _entities.read),
    Section(
        (
            "cross_site_reference_columns", "polymorphic_patterns", "watched_lists",
            "lookup_projections", "calculated_formulas",
        ),
        _columns.read,
    ),
    Section(("reporting", "derived_columns"), _reporting.read, source="reporting_source"),
    Section(
        ("versioning", "item_security", "seal_columns", "prevent_list_deletion", "attachments"),
        _list_settings.read,
    ),
    Section(("enum_sources", "retention_policies_source"), _sources.read),
    Section(("extension", "extensions"), _extensions.read),
    Section(("groups", "permission_levels", "list_permissions"), _permissions.read),
    Section(("style_theme", "column_formatting", "form_formatting"), _formatting.read),
    Section(("field_sets", "views"), _views.read),
    Section(("form_visibility", "column_validation", "list_validation"), _forms.read),
    Section(("display_names",), _display_names.read),
    Section(("demo_items",), _demo.read, source="demo_source"),
    Section(("retired_columns",), _retired.read),
)

#: Every top-level key load_mapping understands. A misspelling must fail
#: rather than be ignored: `form_visibilty:` would otherwise build clean,
#: report "(none declared)" and deploy nothing.
#:
#: Derived from the registry, never from website/docs/reference/mapping.md:
#: an allow-listed key with no reader is worse than no allow-list, because
#: it makes a section that deploys nothing look supported while the build
#: reports success.
KNOWN_SECTIONS: frozenset[str] = frozenset(
    {key for family in SECTION_FAMILIES for key in family.keys}
    | {family.source for family in SECTION_FAMILIES if family.source is not None}
    | set(_REMOVED_SECTIONS),
)


def section_context(
    family: Section, raw: Mapping[str, Any], base_dir: Path, loaded: Mapping[str, Any],
) -> SectionContext:
    """The context one family reads from: its blocks, from wherever they live.

    A mapping may keep a family's sections inline or, when the family has a
    pointer, name a file beside the mapping that holds them. The pointed-at
    file may hold NOTHING ELSE, and a mapping that points at one may not also
    declare any of the family's sections inline.

    REFUSED RATHER THAN MERGED. Two declarations of one section is a
    question with no right answer: whichever one this picked, the other
    would be edited by somebody who could not see it being ignored. The
    same reason `enum_sources` names one file per vocabulary instead of
    layering them.
    """
    if family.source is not None and (source := raw.get(family.source)) is not None:
        blocks = _pointed_blocks(family.keys, family.source, source, raw, base_dir)
    else:
        blocks = {key: raw[key] for key in family.keys if key in raw}
    return SectionContext(base_dir=base_dir, keys=family.keys, blocks=blocks, loaded=loaded)


def _pointed_blocks(
    keys: tuple[str, ...], pointer: str, source: Any, raw: Mapping[str, Any], base_dir: Path,
) -> dict[str, Any]:
    if not isinstance(source, str) or not source.strip():
        raise ValueError(
            f"{pointer} must be a path relative to the mapping, got {source!r}",
        )
    inline = sorted(set(keys) & set(raw))
    if inline:
        raise ValueError(
            f"{pointer} points at {source!r}, so "
            f"{', '.join(inline)} may not also be declared in the mapping. "
            f"Move the section into that file, or drop {pointer}.",
        )
    path = (base_dir / source).resolve()
    if not path.is_file():
        raise ValueError(f"{pointer}: cannot read {source!r} at {path}")
    contents = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    block = _require_mapping(contents, f"{source}")
    _reject_unknown_keys(block, frozenset(keys), f"{source}")
    return {key: block[key] for key in keys if key in block}
