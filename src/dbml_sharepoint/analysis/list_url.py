"""One definition of a list's identity URL: the key part, the clean path, and
the server-relative form.

Shared for the reason joins.py is: the report generator builds the key in M and
pro builds the same key in a flow expression, and a rule written twice drifts.
The input is the mapping's declared web-relative root folder URL, written decoded.
"""
import re
from unicodedata import category

from dbml_sharepoint.model.errors import MappingValueError
from dbml_sharepoint.model.mapping_types import EntityMapping

_ESCAPE = re.compile(r"%[0-9A-Fa-f]{2}")


def list_url_path(declared: str) -> str:
    """The declared URL with slashes normalised, in its declared case."""
    # Learn documents % as legal in a name, so decoding would alias two lists.
    if _ESCAPE.search(declared):
        raise MappingValueError(
            f"list URL {declared!r} holds a %XX escape; write the decoded form",
        )
    # Checked before strip(), which would trim a stray leading or trailing \n or \t.
    if any(category(c) == "Cc" for c in declared):
        raise MappingValueError(f"list URL {declared!r} holds a control character")
    text = declared.strip().replace("\\", "/")
    if "|" in text:
        raise MappingValueError(f"list URL {declared!r} holds '|', which the key splits on")
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


# Conservative allow-list (list-identity title-derived URL finding); other
# characters predict no root.
_KEPT_IN_DERIVED_ROOT = re.compile(r"[A-Za-z0-9_ ]")
_DROPPED_FROM_DERIVED_ROOT = frozenset("-.&'()+,~!@$=;")


def implicit_list_root(title: str, *, is_library: bool) -> str | None:
    """The root SharePoint derives from a title when no `internal_name` is
    declared, or None when the title holds a character outside that allow-list."""
    kept = []
    for char in title:
        if _KEPT_IN_DERIVED_ROOT.fullmatch(char):
            kept.append(char)
        elif char not in _DROPPED_FROM_DERIVED_ROOT:
            return None
    name = "".join(kept)
    if not name.strip():
        return None
    return name if is_library else f"Lists/{name}"


def list_folder(entity: EntityMapping | None, list_title: str) -> str:
    """The web-relative folder a list or library lives in, decoded, no edge slashes.

    The declared URL when there is one; else the root SharePoint derives from the
    title (the deploy sends a Title and no Url), or the raw title when that root
    is not predictable. One home for deploy-side item links and form headers.
    """
    if entity is not None and entity.internal_name:
        return list_url_path(entity.internal_name)
    is_library = entity is not None and entity.is_library
    derived = implicit_list_root(list_title, is_library=is_library)
    if derived is not None:
        return derived
    return list_title if is_library else f"Lists/{list_title}"
