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

TWO SHAPES, because a document library's URL carries no `/Lists/` segment.
Microsoft Learn documents the list one as `<web>/Lists/<List_Title>/
AllItems.aspx`, in which `Lists/<List_Title>/AllItems.aspx` is
website-relative and so is "a complete path from the website address to the
file name"
(https://learn.microsoft.com/sharepoint/dev/general-development/urls-and-tokens-in-sharepoint),
and the library one is `<web>/<library>/Forms/<page>`. `DocumentLibrary` is
an entity kind this tool provisions, so a parser reading only the first
cannot address half of what the deploy creates.

BOTH MARKERS ARE POSITIONAL, and either word can also be a site segment, so
the LATER one names the object and everything before it is the web. Taking
the library shape first instead read `/sites/Forms/Lists/APP_Task/
AllItems.aspx`, an ordinary list on a site called Forms, as the library
`sites` on the root web, which is a site URL and a path the maintenance
sidecars would then have pointed a delete at.
"""

from dataclasses import dataclass
from urllib.parse import unquote, urlparse, urlunparse

#: The path segment every SharePoint list sits under. Matched
#: case-insensitively because the address bar shows `/Lists/` and an
#: operator retyping one has no reason to keep the capital.
_LISTS_SEGMENT = "/lists/"

#: What a document library's view pages sit under, and what names the
#: library: Microsoft Learn derives a library's root folder from the browser
#: URL by "deleting '/Forms/AllItems.aspx' and everything after that"
#: (https://learn.microsoft.com/graph/teams-configuring-builtin-tabs#document-library-tabs).
#: That root folder is exactly what `web/GetList` resolves by.
_FORMS_SEGMENT = "/forms/"


@dataclass(frozen=True)
class _Cut:
    """One reading of a pasted path, and where the segment saying so sits.

    `at` is what decides between two readings of the same path: both markers
    can be present, and the one nearer the end names the object while the
    other is a segment of the site path.
    """

    at: int
    site: str
    #: The prefix `list_path` keeps. Sliced rather than rebuilt, so the
    #: casing the site serves survives.
    prefix: str
    slug: str
    #: Where the name should have been, for the refusal that fires when the
    #: segment beside the marker is blank.
    names: str
    #: What follows a library's forms folder, and None for a list, whose
    #: marker comes before its name rather than after it.
    page: str | None = None


class ListUrlError(ValueError):
    """A URL that does not name a site and a list or document library."""


@dataclass(frozen=True)
class ListUrl:
    """One list or document library, as the parts every caller wants.

    `list_title` IS THE URL SLUG, and the two are not the same thing. A list
    renamed in place keeps the slug it was created with, so after a
    `renamed_from` migration the slug names nothing on the site. It stays
    useful for naming the output folder and for saying which URL was pasted;
    it is not safe to resolve a list with. `list_path` is: for a list it is
    `<site>/Lists/<slug>` and for a library it is the library's own root
    folder, which is what the emitted scripts hand to `web/GetList`.
    """

    site_url: str
    list_title: str
    list_path: str


def _list_cut(path: str) -> _Cut | None:
    """Split a `/Lists/<name>/` path, or None when it carries no such segment."""
    # Searched in the PATH rather than in the whole URL, so a tenant hosted
    # at a name containing "lists" is not cut at its own hostname. Last
    # occurrence rather than first, because the list title is one segment
    # and the only way a second `/Lists/` appears is a site literally named
    # Lists, where the first match is the site's own segment.
    at = path.lower().rfind(_LISTS_SEGMENT)
    if at < 0:
        return None
    end = at + len(_LISTS_SEGMENT)
    return _Cut(
        at, path[:at], path[:end], path[end:].split("/", 1)[0], "list after /Lists/",
    )


def _library_cut(path: str) -> _Cut | None:
    """Split a `/<library>/Forms/<page>` path, or None when it is not that shape."""
    at = path.lower().rfind(_FORMS_SEGMENT)
    if at < 0:
        return None
    # A forms folder holds the library's view pages, so a `/Forms/` with
    # nothing under it names no library: `/sites/Forms/` is a site.
    page = path[at + len(_FORMS_SEGMENT):]
    if not page:
        return None
    head = path[:at]
    cut = head.rfind("/")
    if cut < 0:
        return None
    # `/Lists/Forms/` is read as the list titled Forms rather than a library
    # titled Lists: Learn documents `Lists/<List_Title>/<page>` as
    # website-relative, so `<web>/Lists` is the folder lists are served under.
    if head[cut + 1:].lower() == "lists":
        return None
    return _Cut(
        at, head[:cut], f"{head[:cut]}/", head[cut + 1:], "library before /Forms/",
        page,
    )


def parse_list_url(url: str) -> ListUrl:
    """Split a list or library URL into its site URL, its slug and its server path.

    Both shapes the address bar shows are accepted: `/Lists/<name>/` for a
    list and `/<library>/Forms/<page>` for a document library. A path
    carrying both markers is cut at the later one, because the earlier is
    then a segment of the site path. A URL matching neither is refused
    rather than guessed at.

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
    readings = [c for c in (_list_cut(path), _library_cut(path)) if c is not None]
    cut = max(readings, key=lambda reading: reading.at) if readings else None
    if cut is None:
        raise ListUrlError(
            f"{url!r} has no /Lists/<name>/ segment and no /<library>/Forms/"
            "<page> one, so it names neither a list nor a document library. "
            "Open it in SharePoint and copy the URL from the address bar; a "
            "list looks like https://contoso.sharepoint.com/sites/Risk/Lists/"
            "RG_Project/AllItems.aspx and a library like https://contoso."
            "sharepoint.com/sites/Risk/RG_Evidence/Forms/AllItems.aspx",
        )
    # The library marker sits AFTER the name it identifies, so what follows it
    # is what separates a forms folder from a site segment of the same name:
    # Learn's derivation deletes exactly `/Forms/AllItems.aspx`, so one view
    # page follows it and a path does not.
    if cut.page is not None and "/" in cut.page.rstrip("/"):
        raise ListUrlError(
            f"{url!r} has a /Forms/ segment followed by {cut.page!r} rather "
            "than by one view page, so that segment belongs to the site path "
            "and this URL names neither a list nor a document library. Open "
            "the library in SharePoint and copy the URL from the address bar; "
            "it looks like https://contoso.sharepoint.com/sites/Risk/"
            "RG_Evidence/Forms/AllItems.aspx",
        )

    title = unquote(cut.slug)
    if not title.strip():
        raise ListUrlError(
            f"{url!r} names no {cut.names}, so it does not say what to read. "
            "The name is the segment beside that one.",
        )
    # A slug is ONE path segment. `%2F` decodes to a separator, so a crafted
    # URL could otherwise widen `list_path` into a different folder, and that
    # path is what `columns-script` points its deletes at. No SharePoint list
    # slug contains a separator, so this refuses rather than normalising.
    if "/" in title or "\\" in title:
        raise ListUrlError(
            f"{url!r} has an encoded path separator in its name segment "
            f"({title!r}), so it does not name one list. Copy the URL from "
            "the address bar with the list open.",
        )

    site = urlunparse(parsed._replace(path=cut.site, query="", fragment=""))
    # DECODED, and sliced rather than recomposed. `web/GetList` takes a
    # server-relative URL, which is a decoded path; the emitted script encodes
    # the whole literal itself, so leaving `%20` here would double-encode a
    # list whose slug has a space. Sliced from the pasted path so the casing of
    # the `/Lists/` segment survives, because that is what the site serves the
    # list at and this string is handed over verbatim.
    return ListUrl(
        site_url=site, list_title=title, list_path=unquote(cut.prefix) + title,
    )
