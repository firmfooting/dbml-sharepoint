# test/test_maintaingen.py
"""What the three maintenance scripts SAY, as text.

The runtime tests in test_maintain_runtime.py prove the order the guards
fire in. These pin the facts that hold before the script runs at all: the
site guard is present, the write helpers are present (both scripts write),
the log prefix names the script, and the field properties read are ones
Microsoft Learn documents on the remote Field entity.
"""

import json
from collections.abc import Callable

import pytest

from dbml_sharepoint.analysis.provenance import MARKER_PREFIX, MARKER_TERMINATOR
from dbml_sharepoint.generators.maintaingen import (
    COLUMNS_SCRIPT,
    LIST_MARKER_KINDS,
    LIST_SCRIPT,
    PROTECTION_SCRIPT,
    generate_columns_js,
    generate_list_js,
    generate_protection_js,
)

SITE = "https://example.sharepoint.com/sites/risk"
GENERATED_AT = "2026-09-02T00:00:00Z"


def _protection() -> str:
    return generate_protection_js(
        site_url=SITE, list_title="RR_Risk",
        list_path="/sites/risk/Lists/RR_Risk", generated_at=GENERATED_AT,
    )


def _columns() -> str:
    return generate_columns_js(
        site_url=SITE, list_title="RR_Risk",
        list_path="/sites/risk/Lists/RR_Risk", generated_at=GENERATED_AT,
    )


def _list() -> str:
    return generate_list_js(
        site_url=SITE, list_title="RR_Risk",
        list_path="/sites/risk/Lists/RR_Risk", generated_at=GENERATED_AT,
    )


def test_the_script_names_are_pasteable_text_files() -> None:
    assert PROTECTION_SCRIPT == "protection.js.txt"
    assert COLUMNS_SCRIPT == "columns.js.txt"
    assert LIST_SCRIPT == "list.js.txt"


@pytest.mark.parametrize(
    ("render", "prefix"),
    [(_protection, "[SP-PROTECT]"), (_columns, "[SP-COLUMNS]"), (_list, "[SP-LIST]")],
    ids=["protection", "columns", "list"],
)
def test_each_script_carries_the_site_guard_and_its_own_log_prefix(
    render: Callable[[], str], prefix: str,
) -> None:
    js = render()
    assert "_spPageContextInfo" in js
    assert "site-mismatch" in js
    assert prefix in js
    # BOTH, and the pair is the point: the script resolves by LIST_PATH and
    # keeps LIST_SLUG only to say what the operator pasted. A script emitting
    # the slug alone is the defect this pins (#385).
    assert 'const LIST_SLUG = "RR_Risk"' in js
    assert 'const LIST_PATH = "/sites/risk/Lists/RR_Risk"' in js
    assert "web/lists/getbytitle(" not in js, (
        "resolves the list by title; a renamed list keeps its old slug and "
        "every request would 404"
    )
    assert f'const SITE_URL = "{SITE}"' in js


@pytest.mark.parametrize("render", [_protection, _columns], ids=["protection", "columns"])
def test_each_script_carries_the_write_helpers_it_needs(render: Callable[[], str]) -> None:
    """The opposite of extract.js: these scripts exist to write, so the
    digest and the verbose write headers must be in the emitted text."""
    js = render()
    assert "X-RequestDigest" in js
    assert "contextinfo" in js
    assert "'X-HTTP-Method': 'MERGE'" in js


def test_the_columns_script_deletes_and_the_protection_script_never_does() -> None:
    assert "'X-HTTP-Method': 'DELETE'" in _columns()
    assert "'X-HTTP-Method': 'DELETE'" not in _protection()


@pytest.mark.parametrize("render", [_protection, _columns], ids=["protection", "columns"])
def test_the_field_properties_read_are_documented_remote_properties(
    render: Callable[[], str],
) -> None:
    """`Sealed`, `Hidden`, `FromBaseType`, `CanBeDeleted` and `TypeAsString`
    are documented on Microsoft.SharePoint.Client.Field with the Remote
    attribute, and the first two plus InternalName and ReadOnlyField are
    already read live by the deployer and the probes."""
    js = render()
    documented = (
        "Id,InternalName,Title,TypeAsString,Hidden,ReadOnlyField,Sealed,FromBaseType,CanBeDeleted"
    )
    assert f"const FIELD_SELECT = '{documented}'" in js
    assert "/fields?$select=${FIELD_SELECT}" in js


def test_the_columns_script_reads_a_lookup_target_the_way_the_deployer_does() -> None:
    assert "$select=LookupList,LookupField" in _columns()


def test_the_columns_script_pages_items_by_id_rather_than_filtering() -> None:
    """A `$filter` on an unindexed column throws past the view threshold
    and a Note column refuses one outright; paging by Id does neither."""
    js = _columns()
    assert "$orderby=Id" in js
    assert "__next" in js
    assert "$filter=" not in js


def test_the_columns_script_says_a_deleted_column_is_not_recoverable() -> None:
    """Microsoft Learn: deleting a column removes all data stored in it for
    every item, and neither goes to the recycle bin."""
    js = _columns()
    assert "recycle bin" in js
    assert "DELETE NON-EMPTY" in js


def test_a_crafted_title_cannot_close_the_header_comment() -> None:
    js = generate_columns_js(
        site_url=SITE, list_title="x */ alert(1) /*",
        list_path="/sites/risk/Lists/x */ alert(1) /*", generated_at=GENERATED_AT,
    )
    header = js.split("(async () => {")[0]
    assert "*/ alert" not in header


def test_the_list_script_states_what_survives_the_delete_and_what_does_not() -> None:
    """The two sidecars must not disagree about what a delete means.
    `rollback.js` recycles a list's items and then DELETEs the list, which is
    permanent; this says so before it asks for anything, the row it cannot
    promise to recycle included."""
    js = _list()
    assert "restorable from the site recycle bin" in js
    assert "DOES NOT GO TO THE RECYCLE BIN" in js
    assert "is NOT restorable" in js
    assert "DELETE NON-EMPTY" in js


@pytest.mark.parametrize(
    "render", [_protection, _columns, _list], ids=["protection", "columns", "list"],
)
def test_the_marker_grammar_is_rendered_rather_than_typed(
    render: Callable[[], str],
) -> None:
    """A pattern spelled out in a template is free to drift from
    `analysis/provenance.py`, which is what writes the markers these scripts
    read. identify.js renders the same three parts for the same reason."""
    js = render()
    assert f"const MARKER_PREFIX = {json.dumps(MARKER_PREFIX)}" in js
    assert f"const MARKER_TERMINATOR = {json.dumps(MARKER_TERMINATOR)}" in js
    assert f"const MARKER_KINDS = {json.dumps(list(LIST_MARKER_KINDS))}" in js


def test_the_list_script_refuses_on_the_grammar_not_an_exact_marker() -> None:
    """A retired sidecar's marker names a family and a list the current
    bundle has no entry for, so the deploy's exact-marker comparison can
    never match it. The family-agnostic test is the one available, and what
    it accepts is the whole grammar: a description that merely mentions this
    tool is not a provenance record, and here that test refuses a delete."""
    js = _list()
    assert "carriesMarker(list.Description)" in js
    assert "not-provisioned" in js


def test_the_list_script_reads_the_delete_back_by_id() -> None:
    """By id, not by title: a same-titled replacement created since must not
    read as the list this run deleted."""
    js = _list()
    assert "has NOT been deleted" in js
    assert "is gone is unknown" in js
