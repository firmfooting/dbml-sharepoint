# src/dbml_sharepoint/extract/folder.py
"""The per-list folder: where one list's extraction lives.

Both halves of the flow land here. `extract-script` seeds the folder with
the browser-paste script and a readme; `extract` writes the draft schema,
the mapping and the notes into the same one. The folder is named after the
list, through the same slug the download carries, so the two commands agree
on where the work is without the operator threading a path between them.

The readme is written because the flow has a gap in the middle of it that
no command can close: the script has to be pasted into a browser and the
download saved by hand before the second half can run. A folder holding a
script and nothing else does not say that.
"""

import textwrap
from dataclasses import dataclass
from pathlib import Path

from dbml_sharepoint.bundle import write_artifact
from dbml_sharepoint.catalogue import (
    MAPPING_RELPATH,
    RELEASE_RELPATH,
    SCHEMA_RELPATH,
)
from dbml_sharepoint.extract.run import NOTES_RELPATH
from dbml_sharepoint.generators.extractgen import (
    EXTRACT_SCRIPT,
    download_name,
    generate_extract_js,
    list_slug,
)

#: What the readme is called. Lower case, because it sits beside
#: `EXTRACTION-NOTES.md` in a directory this tool made rather than at the
#: root of a repository somebody browses on GitHub.
README_FILENAME = "readme.md"

#: Where a run lands when the list title folds away to nothing. Reachable:
#: a title of only non-ASCII characters is a valid SharePoint list title and
#: `list_slug` keeps none of it.
FALLBACK_FOLDER = "sharepoint-list"

#: Hard wrap, for the same reason `notes.py` carries one: the readme lands
#: in an operator's project, where markdownlint's default line length
#: applies to it exactly as it does to this repository's own markdown.
_WIDTH = 79


@dataclass(frozen=True)
class Seeded:
    """What seeding one list's folder put on disk."""

    folder: Path
    script: Path
    #: None when a readme was already there and was left alone. The name is
    #: case-insensitive on Windows, so this guard is what keeps a `--out`
    #: aimed at a directory somebody else owns from overwriting their
    #: README.md.
    readme: Path | None


def folder_for(list_title: str) -> Path:
    """The directory one list's extraction lives in."""
    return Path(list_slug(list_title) or FALLBACK_FOLDER)


def folder_for_download(source: Path, list_title: str) -> Path:
    """Where an extraction of `source` lands, with no `--out` to say.

    The list's own folder, unless the download is already sitting in one
    named for the list, in which case the extraction joins it rather than
    nesting a second folder of the same name inside it. That case is the
    normal one: `extract-script` makes the folder, and the readme in it says
    to save the download there.

    So `extract RG_Project/RG_Project-extract.json` from the parent and
    `extract RG_Project-extract.json` from inside the folder both write to
    the same place, which is what an operator following either instruction
    expects. The second spelling has no directory in it at all, so the
    comparison is against the RESOLVED parent, which is the current
    directory; the relative form is what comes back, because that is what
    the summary lines print.
    """
    folder = folder_for(list_title)
    return source.parent if source.parent.resolve().name == folder.name else folder


def _wrapped(text: str) -> str:
    """One paragraph, hard-wrapped.

    Wrapped HERE rather than written pre-wrapped, because the list title and
    the file names are what push a line over the limit and none of them are
    known until this runs. A path in backticks is never broken.
    """
    return textwrap.fill(
        text, width=_WIDTH, break_long_words=False, break_on_hyphens=False,
    )


def render_readme(*, list_title: str, site_url: str) -> str:
    """The readme.md that seeds one list's folder."""
    download = download_name([list_title])
    return "\n\n".join((
        "# Extraction folder",
        # The site URL is in backticks because markdownlint's MD034 refuses a
        # bare one, and this file lands in a project that may well lint it.
        _wrapped(
            f"This folder holds one SharePoint list's extraction. The list is "
            f"{list_title} on `{site_url}`, and dbml-sharepoint writes its "
            f"draft schema and mapping here.",
        ),
        "## Step 1: read the list",
        _wrapped(
            f"Open the list in SharePoint, open the browser console (F12 in "
            f"Edge and in Chrome), and paste the whole of `{EXTRACT_SCRIPT}` "
            f"into it. Every request that script makes is a GET, so it changes "
            f"nothing on the site.",
        ),
        _wrapped(
            f"It saves the list's field definitions as `{download}`. Put that "
            f"file in this folder, beside this one.",
        ),
        "## Step 2: recover the draft",
        "From inside this folder, run:",
        f"```text\ndbml-sharepoint extract {download}\n```",
        _wrapped(
            f"That writes `{SCHEMA_RELPATH.as_posix()}`, "
            f"`{MAPPING_RELPATH.as_posix()}` and "
            f"`{RELEASE_RELPATH.as_posix()}` here.",
        ),
        "## Step 3: read the notes",
        _wrapped(
            f"`{NOTES_RELPATH.as_posix()}` is written along with them, and it "
            f"is the part to read first. It lists what the read did not carry "
            f"and what this tool would not guess at.",
        ),
        _wrapped(
            "What lands here is a draft: read the notes before you edit the "
            "schema, and read them again before you deploy anything.",
        ),
    )) + "\n"


def seed(
    *,
    list_title: str,
    list_path: str,
    site_url: str,
    generated_at: str,
    script: Path | None = None,
) -> Seeded:
    """Write the browser-paste script and the readme, making the folder.

    `script` overrides where the script goes, which is what `--out` passes.
    The readme follows it, because the two are one document in two files and
    a script in a directory with no procedure beside it is the state this
    module exists to avoid.

    `list_title` is the URL slug and names the FOLDER; `list_path` is the
    server-relative URL and is what the emitted script RESOLVES BY. They stop
    being the same string the moment the list is renamed in place.
    """
    path = script if script is not None else folder_for(list_title) / EXTRACT_SCRIPT
    write_artifact(path, generate_extract_js(
        site_url=site_url, list_paths=[list_path], generated_at=generated_at,
    ))
    readme = path.parent / README_FILENAME
    if readme.exists():
        return Seeded(folder=path.parent, script=path, readme=None)
    write_artifact(readme, render_readme(list_title=list_title, site_url=site_url))
    return Seeded(folder=path.parent, script=path, readme=readme)
