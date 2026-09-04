# src/dbml_sharepoint/generators/maintaingen.py
"""Render protection.js.txt and columns.js.txt, the list maintenance scripts.

Like extract.js, neither has a schema or a mapping behind it: the operator
names one list by pasting its URL, and the script does the rest against
the live site. Unlike extract.js, both WRITE, so both include
`_http_write.js.j2` and the cached digest.

Why they exist. The deployer never deletes a column and never touches one
it did not declare, so a lookup left behind when its target list was
replaced stays on the list forever, sealed, and shows up on every form.
Rollback deletes whole lists. Nothing in between existed, and doing it by
hand means unsealing a column through REST, which is the step people get
wrong.
"""

from dbml_sharepoint import __version__
from dbml_sharepoint.analysis.provenance import MARKER_PREFIX
from dbml_sharepoint.templating import script_env

#: What the CLI writes each script as. `.js.txt` for the reason every other
#: pasteable carries it: a `.js` on Windows is associated with Windows
#: Script Host, and double-clicking one runs it outside the browser.
PROTECTION_SCRIPT = "protection.js.txt"
COLUMNS_SCRIPT = "columns.js.txt"


def _render(
    template: str, *, site_url: str, list_title: str, list_path: str, generated_at: str,
) -> str:
    return script_env().get_template(template).render(
        site_url=site_url,
        # BOTH, and they are different things. `list_path` is what the script
        # resolves the list by; `list_title` is the URL slug, which names the
        # output folder and the header comment and stops being the list's
        # title the moment the list is renamed in place.
        list_title=list_title,
        list_path=list_path,
        generated_at=generated_at,
        deployer_version=__version__,
        # Passed in rather than typed into the template, so the scripts and
        # the deployer can never disagree about what a marker starts with.
        marker_prefix=MARKER_PREFIX,
    )


def generate_protection_js(
    *, site_url: str, list_title: str, list_path: str, generated_at: str,
) -> str:
    """The pasteable script that locks, unlocks, seals or unseals one list.

    `list_path` is the list's server-relative URL and is what the script
    resolves by; `list_title` is the slug from that URL, and the two differ on
    any list renamed in place.
    """
    return _render(
        "protection.js.j2", site_url=site_url, list_title=list_title,
        list_path=list_path, generated_at=generated_at,
    )


def generate_columns_js(
    *, site_url: str, list_title: str, list_path: str, generated_at: str,
) -> str:
    """The pasteable script that enumerates and deletes one list's custom columns.

    `list_path` is the list's server-relative URL and is what the script
    resolves by; `list_title` is the slug from that URL, and the two differ on
    any list renamed in place.
    """
    return _render(
        "columns.js.j2", site_url=site_url, list_title=list_title,
        list_path=list_path, generated_at=generated_at,
    )
