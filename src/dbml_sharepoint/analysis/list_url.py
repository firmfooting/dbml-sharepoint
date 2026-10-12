"""One definition of a list's identity URL: the key part, the clean path, and
the server-relative form.

Shared for the reason joins.py is: the report generator builds the key in M and
pro builds the same key in a flow expression, and a rule written twice drifts.
The input is the mapping's declared web-relative root folder URL, written decoded.
"""
import re
from unicodedata import category

from dbml_sharepoint.model.errors import MappingValueError

_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")


def list_url_path(declared: str) -> str:
    """The declared URL with slashes normalised, in its declared case."""
    # Learn documents % as legal in a name, so decoding would alias two lists.
    if _ESCAPE.search(declared):
        raise MappingValueError(
            f"list URL {declared!r} holds a %XX escape; write the decoded form",
        )
    text = declared.strip().replace("\\", "/")
    if "|" in text:
        raise MappingValueError(f"list URL {declared!r} holds '|', which the key splits on")
    if any(category(c) == "Cc" for c in text):
        raise MappingValueError(f"list URL {declared!r} holds a control character")
    parts = [p for p in text.split("/") if p]
    if not parts:
        raise MappingValueError("a list URL is empty")
    if any(p in {".", ".."} for p in parts):
        raise MappingValueError(f"list URL {declared!r} holds a traversal segment")
    return "/".join(parts)


def list_url_key(declared: str) -> str:
    """The key part: the path, lower-cased."""
    return list_url_path(declared).lower()


def server_relative(site_path: str, declared: str) -> str:
    """The server-relative URL GetList takes: the site's path and the list's."""
    site = site_path.strip().strip("/")
    return "/" + "/".join(p for p in (site, list_url_path(declared)) if p)
