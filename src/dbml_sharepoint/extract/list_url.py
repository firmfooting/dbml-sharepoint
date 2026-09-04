# src/dbml_sharepoint/extract/list_url.py
"""A pasted SharePoint list URL, split into the site, the slug and the path.

Every operator-pasted script needs those, and the browser address bar shows
one string carrying all three, so this splits it rather than making the
operator do it. The same split reportgen's `_SITE_ROOT_M` performs in M, and
for the same measured reason: an operator hands over what the address bar
shows while viewing a list, and everything built from it as if it were a site
URL asks SharePoint for `.../Lists/<Title>/_api/...`, which answers 404.

Unlike that one, this refuses a URL with no list segment instead of
trimming what it finds. `_SITE_ROOT_M` only needs the site and can leave a
site URL alone; here the list is the thing being read, and a URL that does
not name one cannot be guessed at.
"""

from dataclasses import dataclass
from urllib.parse import unquote, urlparse, urlunparse

#: The path segment every SharePoint list sits under. Matched
#: case-insensitively because the address bar shows `/Lists/` and an
#: operator retyping one has no reason to keep the capital.
_LISTS_SEGMENT = "/lists/"


class ListUrlError(ValueError):
    """A URL that does not name a site and a list."""


@dataclass(frozen=True)
class ListUrl:
    """One list, as the parts every caller downstream wants.

    `list_title` IS THE URL SLUG, and the two are not the same thing. A list
    renamed in place keeps the slug it was created with, so after a
    `renamed_from` migration the slug names nothing on the site. It stays
    useful for naming the output folder and for saying which URL was pasted;
    it is not safe to resolve a list with. `list_path` is.
    """

    site_url: str
    list_title: str
    list_path: str


def parse_list_url(url: str) -> ListUrl:
    """Split a list URL into its site URL, its slug and its server path.

    Any query string or fragment is dropped first: SharePoint's own
    **Copy link** puts `?web=1` on the clipboard, and a list view URL
    carries `?RootFolder=...` and `#` anchors that say nothing about which
    list this is.
    """
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.netloc:
        raise ListUrlError(
            f"expected an absolute https:// list URL with a host, got {url!r}.",
        )

    path = parsed.path
    # Searched in the PATH rather than in the whole URL, so a tenant hosted
    # at a name containing "lists" is not cut at its own hostname. Last
    # occurrence rather than first, because the list title is one segment
    # and the only way a second `/Lists/` appears is a site literally named
    # Lists, where the first match is the site's own segment.
    at = path.lower().rfind(_LISTS_SEGMENT)
    if at < 0:
        raise ListUrlError(
            f"{url!r} has no /Lists/<name>/ segment, so it does not say which "
            "list to read. Open the list in SharePoint and copy the URL from "
            "the address bar; it looks like "
            "https://contoso.sharepoint.com/sites/Risk/Lists/RG_Project/AllItems.aspx",
        )

    rest = path[at + len(_LISTS_SEGMENT):]
    title = unquote(rest.split("/", 1)[0])
    if not title.strip():
        raise ListUrlError(
            f"{url!r} names no list after /Lists/. The list is the segment "
            "that follows it.",
        )
    # A slug is ONE path segment. `%2F` decodes to a separator, so a crafted
    # URL could otherwise widen `list_path` into a different folder, and that
    # path is what `columns-script` points its deletes at. No SharePoint list
    # slug contains a separator, so this refuses rather than normalising.
    if "/" in title or "\\" in title:
        raise ListUrlError(
            f"{url!r} has an encoded path separator in its list segment "
            f"({title!r}), so it does not name one list. Copy the URL from "
            "the address bar with the list open.",
        )

    site = urlunparse(parsed._replace(path=path[:at], query="", fragment=""))
    # DECODED, and sliced rather than recomposed. `web/GetList` takes a
    # server-relative URL, which is a decoded path; the emitted script encodes
    # the whole literal itself, so leaving `%20` here would double-encode a
    # list whose slug has a space. Sliced from the pasted path so the casing of
    # the `/Lists/` segment survives, because that is what the site serves the
    # list at and this string is handed over verbatim.
    list_path = unquote(path[:at + len(_LISTS_SEGMENT)]) + title
    return ListUrl(site_url=site, list_title=title, list_path=list_path)
