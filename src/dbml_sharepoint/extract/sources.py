# src/dbml_sharepoint/extract/sources.py
"""Read field XML out of the JSON `extract.js.txt` downloads.

That download is the only input this tool takes. Everything in it is
normalised to a `SourceList` of `RawField`, so `decode` reads records
rather than a file format.

An "Export to CSV with schema" was read here once as a second path. It
carried no list title, no view definitions and, for a calculated column,
values but no formula, so the schema it produced was quietly short of the
formulas somebody modifying the list most needs back. It was removed
rather than kept as a lesser option.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dbml_sharepoint.extract.field_xml import FieldXmlError, RawField, parse_field_xml

#: What `extract.js.txt` writes into its download, so a JSON file that is
#: something else fails with a sentence rather than a KeyError.
LIVE_FORMAT = "dbml-sharepoint-extract/1"

#: Stripped by hand as well as by `utf-8-sig`, because `load_live_json`
#: also takes text a caller read some other way.
_BOM = "\ufeff"

#: How the source names itself. Written to read after "from" or "Extracted
#: from", because this string is prose everywhere it appears: the notes,
#: the schema header, the mapping header and the CLI's summary line all
#: interpolate it.
LIVE_KIND = "a live read of the site"


class SourceError(ValueError):
    """The input is not a source this tool reads, or is damaged."""


@dataclass(frozen=True)
class SourceList:
    """One list as the download described it."""

    title: str
    fields: list[RawField]
    description: str = ""
    #: Views, as read live. Kept whole and reported rather than decoded:
    #: recovering a `views:` declaration from CAML is a second inversion
    #: problem and this tool does not guess at one.
    views: list[dict[str, Any]] = field(default_factory=list)
    content_type_formatter: str = ""


@dataclass(frozen=True)
class Source:
    """Everything one download described."""

    kind: str
    lists: list[SourceList]
    #: What a read structurally cannot carry, for the notes.
    capabilities: tuple[str, ...] = ()
    site_url: str = ""


#: What a live read does not recover, whatever the list has. Read by the
#: notes so the report distinguishes "this list has none" from "this tool
#: was never going to tell you".
LIVE_ABSENCES = (
    "permissions, groups and role assignments",
    "versioning settings",
    "list-level validation beyond what the fields carry",
)


def load_source(path: Path) -> Source:
    """Read one `extract.js.txt` download from disk."""
    return load_live_json(_read_text(path))


def load_live_json(raw: str) -> Source:
    """Decode the JSON `extract.js.txt` downloads from a live site."""
    try:
        document = json.loads(raw.lstrip(_BOM))
    except json.JSONDecodeError as exc:
        raise SourceError(
            f"not valid JSON: {exc}. This command reads the JSON that "
            "extract.js.txt downloads; run `dbml-sharepoint extract-script` "
            "to generate that script.",
        ) from exc
    if not isinstance(document, dict):
        raise SourceError("expected a JSON object at the top level")
    if document.get("format") != LIVE_FORMAT:
        raise SourceError(
            f"expected {LIVE_FORMAT!r} in the 'format' key; this JSON was not "
            "written by extract.js.txt.",
        )
    raw_lists = document.get("lists")
    if not isinstance(raw_lists, list) or not raw_lists:
        raise SourceError("the download declares no lists")

    lists = []
    for index, entry in enumerate(raw_lists):
        if not isinstance(entry, dict):
            raise SourceError(f"lists[{index}] is not an object")
        title = entry.get("title") or ""
        if not title:
            raise SourceError(f"lists[{index}] has no title")
        lists.append(SourceList(
            title=title,
            fields=_parse_all(entry.get("fields"), f"lists[{index}].fields"),
            description=entry.get("description") or "",
            views=[v for v in entry.get("views") or [] if isinstance(v, dict)],
            content_type_formatter=entry.get("contentTypeFormatter") or "",
        ))
    return Source(
        kind=LIVE_KIND,
        capabilities=LIVE_ABSENCES,
        lists=lists,
        site_url=document.get("siteUrl") or "",
    )


def _parse_all(entries: object, context: str) -> list[RawField]:
    if not isinstance(entries, list):
        raise SourceError(f"{context} is missing or is not a list")
    fields = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, str):
            raise SourceError(f"{context}[{index}] is not a string of XML")
        try:
            fields.append(parse_field_xml(entry))
        except FieldXmlError as exc:
            raise SourceError(f"{context}[{index}]: {exc}") from exc
    if not fields:
        raise SourceError(f"{context} is empty; there is nothing to extract")
    return fields


def _read_text(path: Path) -> str:
    try:
        # `utf-8-sig` because a download re-saved by an editor can carry a
        # byte order mark, and `json.loads` refuses one.
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise SourceError(f"{path}: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise SourceError(f"{path}: not UTF-8 text ({exc})") from exc
