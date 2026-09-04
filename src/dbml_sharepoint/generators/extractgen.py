# src/dbml_sharepoint/generators/extractgen.py
"""Render extract.js.txt, the read-only browser-paste schema reader.

The only generator here with no schema and no mapping behind it: this
script runs BEFORE either file exists, which is the whole point of it. It
reads a live list's field definitions and downloads them as the JSON
`extract.sources.load_live_json` accepts.

Strictly read-only. It includes `_http.js.j2` and never `_http_write.js.j2`,
so the write helpers are not in the emitted file at all, and a read-only
guarantee test pins that.
"""

import re

from dbml_sharepoint import __version__
from dbml_sharepoint.extract.sources import LIVE_FORMAT
from dbml_sharepoint.templating import script_env

#: What the CLI writes the script as. `.js.txt` for the reason every other
#: pasteable carries it: a `.js` on Windows is associated with Windows
#: Script Host, and double-clicking one runs it outside the browser.
EXTRACT_SCRIPT = "extract.js.txt"

#: What the browser saves when a run covers more than one list, or when the
#: one title has nothing usable left in it.
DEFAULT_DOWNLOAD_NAME = "sharepoint-extract.json"

_UNSAFE_IN_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


class NoListsError(ValueError):
    """Asked for a script that would read nothing."""


def list_slug(title: str) -> str:
    """A list title folded to what a file name and a directory name share.

    Every character outside a conservative set becomes `-`. The download
    name below reaches the DOM as an anchor's `download` attribute, and the
    browsers that honour a path separator in one differ from the ones that
    do not; the extraction folder is a real directory and takes the same
    characters for the same reason. One function, so the folder and the
    file that belongs in it cannot come to disagree.

    Returns "" when nothing usable is left, which the callers answer for
    themselves: a title of only non-ASCII characters is a perfectly good
    SharePoint list title and folds away to nothing here.
    """
    return _UNSAFE_IN_FILENAME.sub("-", title).strip("-.")


def slug_from_path(list_path: str) -> str:
    """The last segment of a server-relative list URL.

    Not `list_slug`, which folds a name down to what a filesystem accepts.
    This one only splits a path; its result is then passed THROUGH
    `list_slug` by `download_name`.

    The slug is what names the local extraction folder and the downloaded
    file, and it is what an operator sees in the address bar, so it stays the
    right thing to name local artefacts after even once it has stopped being
    the list's title.
    """
    return list_path.rstrip("/").rsplit("/", 1)[-1]


def download_name(list_titles: list[str]) -> str:
    """The file name the browser saves the payload as.

    Derived from a single list's title so an operator extracting several
    sites does not end up with four downloads called the same thing.
    """
    if len(list_titles) != 1:
        return DEFAULT_DOWNLOAD_NAME
    slug = list_slug(list_titles[0])
    return f"{slug}-extract.json" if slug else DEFAULT_DOWNLOAD_NAME


def generate_extract_js(
    *,
    site_url: str,
    list_paths: list[str],
    generated_at: str,
) -> str:
    """The pasteable extraction script for one site and its named lists.

    PATHS, NOT TITLES. Each entry is a list's server-relative URL, which is
    what the script resolves by: a list renamed in place keeps the slug it
    was created with, so the segment the address bar shows stops being the
    list's title and a by-title read 404s. `_get_list_by_path.js.j2` carries
    the full reason.

    The download name still comes from the slug, because it names a local
    file rather than a list. It is derived from the path here rather than
    taken as a second argument, so the two cannot be passed out of step.
    """
    if not list_paths:
        raise NoListsError(
            "no lists were named, so the script would read nothing. Pass "
            "--list once per list to extract.",
        )
    return script_env().get_template("extract.js.j2").render(
        site_url=site_url,
        list_paths=list_paths,
        generated_at=generated_at,
        deployer_version=__version__,
        live_format=LIVE_FORMAT,
        download_name=download_name([slug_from_path(p) for p in list_paths]),
    )
