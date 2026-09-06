# test/test_identifygen.py
"""Static guarantees for identify.js.txt, the read-only site inventory script.

The script is pasted into a console on somebody else's production site and
walks every list, group and permission level it can see. Two properties have
to hold before anything else is worth asserting: it never writes, and it
never restates the provenance grammar that decides what this tool owns.
"""

from dbml_sharepoint.analysis.provenance import (
    MARKER_PREFIX,
    MARKER_TERMINATOR,
    marker_for_object,
)
from dbml_sharepoint.generators.identifygen import (
    IDENTIFY_SCRIPT,
    PAYLOAD_FORMAT,
    PAYLOAD_VERSION,
    generate_identify_js,
)

GENERATED_AT = "2026-09-06T12:00:00+00:00"
SITE = "https://example.sharepoint.com/sites/risk"


def _identify_js(site_url: str | None = None) -> str:
    return generate_identify_js(site_url=site_url, generated_at=GENERATED_AT)


def test_the_identify_script_is_read_only() -> None:
    """It carries no write helpers at all, which is stronger than not using
    them: `_http_write.js.j2` is simply not included."""
    js = _identify_js()
    assert "method: 'POST'" not in js
    assert "X-HTTP-Method" not in js
    assert "X-RequestDigest" not in js
    assert "contextinfo" not in js
    assert "postJson" not in js


def test_the_script_is_portable_across_a_fleet_by_default() -> None:
    """No site URL means it inventories whichever web it is pasted on.

    The site-match guard exists because the other sidecars write, and a write
    on the wrong site cannot be taken back. This one reads, so pinning it to
    one site would only stop an operator walking a fleet with one file.
    """
    js = _identify_js()
    assert "site-mismatch" not in js
    assert "const SITE_URL" not in js


def test_a_named_site_still_pins_the_script_to_it() -> None:
    """`--site-url` re-arms the same guard every writing sidecar carries."""
    js = _identify_js(SITE)
    assert "site-mismatch" in js
    assert SITE in js


def test_the_marker_prefix_is_rendered_rather_than_typed() -> None:
    """The grammar has one authority, `analysis/provenance.py`.

    A regex typed into the template would be free to disagree with the
    markers the deploy actually writes, and nothing in the build would see it.
    """
    js = _identify_js()
    assert MARKER_PREFIX in js
    assert f"{MARKER_TERMINATOR!r}"[1:-1] in js


def test_the_payload_declares_its_format_and_version() -> None:
    """Several sites' downloads get combined into a fleet view, so each file
    has to say what shape it is before anything reads it."""
    js = _identify_js()
    assert PAYLOAD_FORMAT in js
    assert f"payload_version: {PAYLOAD_VERSION}" in js or str(PAYLOAD_VERSION) in js


def test_the_column_read_is_guarded_by_ownership() -> None:
    """The request budget is the design constraint: one call per owned list,
    not one per list on the web. A live run tripped the tenant throttle at
    3,156 requests in 145 seconds on 2026-09-03.

    This pins the guard in the emitted text. That only one call per owned
    list actually goes out is proved by counting them in
    `test_identify_runtime.py`, which is where a request budget can be
    measured rather than asserted.
    """
    js = _identify_js()
    assert "web/lists?$select=" in js
    assert "lists.filter((l) => l.owned)" in js
    assert "$select=InternalName" in js


def test_the_script_names_itself_for_the_file_the_cli_writes() -> None:
    assert IDENTIFY_SCRIPT == "identify.js.txt"


def test_a_marker_built_by_the_authority_is_what_the_script_looks_for() -> None:
    """Pins the two halves together: the string the deploy writes for a list
    has to be the string this script's prefix matches."""
    marker = marker_for_object(kind="list", name="GOV_Risk", family="programme-governance")
    js = _identify_js()
    assert marker.startswith(MARKER_PREFIX)
    assert MARKER_PREFIX in js
