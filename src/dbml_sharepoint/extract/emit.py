# src/dbml_sharepoint/extract/emit.py
"""Render a decoded extraction as the family layout `build` reads.

The output is a draft an operator edits, so it is written to be read: the
DBML columns are aligned the way the shipped families are, and every
place this tool had to choose carries a comment saying so. What could not
be recovered is NOT represented here at all; it is in the notes, because a
placeholder in a schema is indistinguishable from a decision.

Everything is written through `bundle.write_artifact`, the one writer, so
the output is UTF-8 with LF endings on every platform.
"""

from typing import Any

import yaml

from dbml_sharepoint.extract.decode import DecodedColumn, DecodedEntity, Extraction

#: The prefix an extracted mapping carries until the operator sets theirs.
#: Not derived from the list title: a prefix names the DEPLOYING project,
#: and a list that already exists was not necessarily deployed by one.
DEFAULT_PREFIX = "EX_"

#: What a fresh extraction's release stamp says. `0.0.0` rather than a
#: version that looks like the live list's, which nothing here knows.
DRAFT_RELEASE = "0.0.0"

#: The DBML the schema opens with, before the enums.
_HEADER = """\
// ============================================================================
// Extracted from {source}.
//
// This is a DRAFT: read EXTRACTION-NOTES.md beside it for everything the
// source could not carry, then edit both files before deploying anything.
// ============================================================================
"""


def render_schema(extraction: Extraction, *, project: str) -> str:
    """The `10-design/schema.dbml` for one extraction."""
    parts = [_HEADER.format(source=extraction.source)]
    parts.append(
        f"Project {project} {{ database_type: 'SharePoint Online Lists' }}\n",
    )
    for enum in extraction.enums:
        members = "\n".join(f'  "{_escape(member)}"' for member in enum.members)
        parts.append(f"Enum {enum.name} {{\n{members}\n}}\n")
    for entity in extraction.entities:
        parts.append(_render_table(entity))
    return "\n".join(parts)


def _render_table(entity: DecodedEntity) -> str:
    # `Id` is synthesised rather than read: SharePoint provisions it on
    # every list and the read describes it as a built-in, so a schema
    # that declared it from the source would be declaring a column the
    # deploy must never create.
    columns = [
        DecodedColumn(name="Id", dbml_type="int"),
        *entity.columns,
    ]
    name_width = max(len(col.name) for col in columns)
    type_width = max(len(col.dbml_type) for col in columns)

    lines = [f"Table {entity.name} {{"]
    for col in columns:
        settings = ["pk", "increment"] if col.name == "Id" else _settings(col)
        rendered = f"[{', '.join(settings)}]" if settings else ""
        lines.append(
            f"  {col.name:<{name_width}} {col.dbml_type:<{type_width}} {rendered}".rstrip(),
        )

    if entity.indexes:
        lines.append("")
        lines.append(
            "  // Indexed on the live list. SharePoint refuses an index on "
            "some types,",
        )
        lines.append("  // so the build may still reject one of these.")
        lines.append("  indexes {")
        lines.extend(f"    {name}" for name in entity.indexes)
        lines.append("  }")

    if entity.note:
        lines.append("")
        lines.append(f"  Note: '{_escape_note(entity.note)}'")
    lines.append("}")
    return "\n".join(lines) + "\n"


def _settings(col: DecodedColumn) -> list[str]:
    settings = []
    if col.required:
        settings.append("not null")
    if col.unique:
        settings.append("unique")
    if col.default is not None:
        settings.append(f"default: {_default_literal(col.default)}")
    if col.note:
        settings.append(f"note: '{_escape_note(col.note)}'")
    return settings


def _default_literal(value: str | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return f"'{_escape_note(value)}'"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _escape_note(value: str) -> str:
    """A DBML single-quoted string body.

    Newlines are folded to spaces rather than escaped: a SharePoint field
    description is one paragraph of prose and a literal break inside a
    single-quoted DBML string is a parse error, not a formatting choice.
    """
    folded = " ".join(value.split())
    return folded.replace("\\", "\\\\").replace("'", "\\'")


def render_mapping(extraction: Extraction, *, prefix: str = DEFAULT_PREFIX) -> str:
    """The `20-configure/mapping.yaml` for one extraction."""
    entities = {
        entity.name: {"kind": "List", "base_template": 100, "site_role": "default"}
        for entity in extraction.entities
    }
    document: dict[str, Any] = {
        "prefix": prefix,
        "entities": entities,
        "cross_site_reference_columns": [],
        # A required section neither source carries. Declared conservatively
        # (versioning on, minor versions off) so a first deploy does not turn
        # off history somebody is relying on; the notes list it as a value to
        # check rather than one that was read.
        "versioning": {
            "default": {
                "enable_versioning": True,
                "major_version_limit": 500,
                "enable_minor_versions": False,
            },
            "overrides": {},
        },
        "enum_sources": {},
        "watched_lists": [],
    }

    if any(_renames_a_column(entity) for entity in extraction.entities):
        display: dict[str, Any] = {"mode": "auto"}
        overrides = {
            entity.name: entity.display_overrides
            for entity in extraction.entities
            if entity.display_overrides
        }
        if overrides:
            display["overrides"] = overrides
        document["display_names"] = display

    # Which sections wrap their columns in a `columns:` key and which do not
    # is read from `mapping_loader`, the thing that actually parses them.
    for key, nest in (
        ("calculated_formulas", False),
        ("column_formatting", False),
        ("form_visibility", True),
        ("column_validation", True),
    ):
        section = _per_entity(extraction, key, nest=nest)
        if section:
            document[key] = section

    body = _dump(document)
    return _MAPPING_HEADER.format(source=extraction.source, prefix=prefix) + body


_MAPPING_HEADER = """\
# Extracted from {source}.
#
# This is a DRAFT: read EXTRACTION-NOTES.md beside it before deploying
# anything.
#
# `prefix` is {prefix!r} because an extraction cannot know the deploying
# project's prefix. Set it to yours; it is what the deploy names lists with.
# `versioning` and `entities.*.base_template` are DECLARED here rather than
# recovered, because neither source carries the live settings.
"""


def _dump(document: dict[str, Any]) -> str:
    """YAML for an operator to edit and diff.

    `width` is effectively off. The default wraps a long scalar across
    lines, which is legal YAML and unreadable in a diff: a one-word edit to
    a validation message reflows the whole block.
    """
    return yaml.safe_dump(
        document,
        sort_keys=False,
        default_flow_style=False,
        allow_unicode=True,
        width=10_000,
    )


def _renames_a_column(entity: DecodedEntity) -> bool:
    """Whether any column's live display title differs from its internal name.

    The section is only emitted when the live list actually renames
    something. Declaring it otherwise would have the deploy rename every
    column to the name it already has, which is a no-op that still shows up
    as a reconcile action on every run.
    """
    return any(
        col.raw is not None and col.raw.display_name != col.name
        for col in entity.columns
    )


def _per_entity(extraction: Extraction, attribute: str, *, nest: bool) -> dict[str, Any]:
    """Collect one per-column mapping section across every entity."""
    section: dict[str, Any] = {}
    for entity in extraction.entities:
        declared = getattr(entity, attribute)
        if not declared:
            continue
        section[entity.name] = {"columns": declared} if nest else dict(declared)
    return section


def render_release(*, source: str, generated_at: str) -> str:
    """The `20-configure/release.yaml` stub.

    A stub rather than a recovery: nothing in either source says which
    release of anything produced the live list. Every key `load_release`
    requires is present, so `build` runs; the values say plainly that they
    are a starting point.
    """
    document = {
        "release": DRAFT_RELEASE,
        "date": generated_at,
        "deployer_version": "dbml-sharepoint/extracted",
        "schema_version": DRAFT_RELEASE,
        "notes": (
            f"Extracted from {source} on {generated_at}. Nothing in the source "
            "records which release built the live list, so these versions are "
            "a starting point. Set them before the first deploy, and bump "
            "schema_version on every schema or mapping change after it."
        ),
    }
    return _dump(document)
