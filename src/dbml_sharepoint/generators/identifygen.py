# src/dbml_sharepoint/generators/identifygen.py
"""Render identify.js.txt, the read-only site inventory script.

The fleet counterpart to the list maintenance sidecars. Where protection.js
and columns.js act on one list an operator names, this one is pasted on any
site and reports what is there: the web's own facts, every list, group and
permission level, which of them this tool provisioned and for which family,
the columns of the ones it owns, and the last deployment the site recorded.
It answers "what is on this site" for a site nobody kept notes for.

Strictly read-only, the same way extract.js is: it includes ``_http.js.j2``
and never ``_http_write.js.j2``, so the write helpers are not in the emitted
file at all, and a guarantee test pins that.

The provenance grammar is not restated here or in the template. What this
tool owns is decided by ``analysis/provenance.py``, and the marker's parts
are rendered in, so the script and the deploy cannot come to disagree about
what a marker looks like. The sidecar list titles and the run log's stamp
columns come from ``analysis/sidecars.py`` for the same reason.
"""

from dbml_sharepoint import __version__
from dbml_sharepoint.analysis import sidecars
from dbml_sharepoint.analysis.provenance import (
    GROUP_KIND,
    LEVEL_KIND,
    LIST_KIND,
    MARKER_PREFIX,
    MARKER_TERMINATOR,
    SCRATCH_KIND,
)
from dbml_sharepoint.templating import script_env

#: What the CLI writes the script as. `.js.txt` for the reason every other
#: pasteable carries it: a `.js` on Windows is associated with Windows
#: Script Host, and double-clicking one runs it outside the browser.
IDENTIFY_SCRIPT = "identify.js.txt"

#: What the browser saves. One name for every site, because the payload
#: carries the web it came from and an operator walking a fleet renames the
#: downloads or sorts them by time either way.
DEFAULT_DOWNLOAD_NAME = "sharepoint-identify.json"

#: Stamped into the payload so a reader knows what it has before parsing it.
PAYLOAD_FORMAT = "dbml-sharepoint/identify"

#: Bumped when a field changes meaning or leaves. A fleet view combines files
#: written by different versions of this tool, so the shape has to say which
#: it is rather than be guessed at from which keys happen to be present.
PAYLOAD_VERSION = 1

#: The object kinds the marker grammar can name, in the order the script's
#: pattern alternates them. Taken from the grammar rather than typed, so a
#: new kind cannot be added there and silently go unrecognised here.
MARKER_KINDS: tuple[str, ...] = (LIST_KIND, GROUP_KIND, LEVEL_KIND, SCRATCH_KIND)

#: The columns a deployment stamp writes on the local run log. Read off each
#: row rather than named in a `$select`, because a run log created before a
#: column existed is reused and selecting an absent column answers HTTP 400.
RUN_LOG_STAMP_FIELDS: tuple[str, ...] = tuple(
    str(column["Title"]) for column in sidecars.RUN_LOG_STAMP_COLUMNS
)


def generate_identify_js(*, generated_at: str, site_url: str | None = None) -> str:
    """The pasteable inventory script for one site, or for any site.

    ``site_url`` is optional: with none, the script inventories whichever web
    it is pasted into, so one file walks a whole fleet. Pass one to re-arm the
    site-match guard the writing sidecars carry, which is worth doing when the
    file goes to somebody else to paste.
    """
    return script_env().get_template("identify.js.j2").render(
        site_url=site_url,
        require_site_match=site_url is not None,
        generated_at=generated_at,
        deployer_version=__version__,
        payload_format=PAYLOAD_FORMAT,
        payload_version=PAYLOAD_VERSION,
        download_name=DEFAULT_DOWNLOAD_NAME,
        marker_prefix=MARKER_PREFIX,
        marker_terminator=MARKER_TERMINATOR,
        marker_kinds=MARKER_KINDS,
        list_kind=LIST_KIND,
        group_kind=GROUP_KIND,
        level_kind=LEVEL_KIND,
        scratch_kind=SCRATCH_KIND,
        run_log_title=sidecars.RUN_LOG_TITLE,
        run_log_previous_titles=sidecars.RUN_LOG_PREVIOUS_TITLES,
        change_log_title=sidecars.CHANGE_LOG_TITLE,
        stamp_fields=RUN_LOG_STAMP_FIELDS,
    )
