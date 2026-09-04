# test/test_maintaingen.py
"""What the two maintenance scripts SAY, as text.

The runtime tests in test_maintain_runtime.py prove the order the guards
fire in. These pin the facts that hold before the script runs at all: the
site guard is present, the write helpers are present (both scripts write),
the log prefix names the script, and the field properties read are ones
Microsoft Learn documents on the remote Field entity.
"""

from collections.abc import Callable

import pytest

from dbml_sharepoint.generators.maintaingen import (
    COLUMNS_SCRIPT,
    PROTECTION_SCRIPT,
    generate_columns_js,
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


def test_the_script_names_are_pasteable_text_files() -> None:
    assert PROTECTION_SCRIPT == "protection.js.txt"
    assert COLUMNS_SCRIPT == "columns.js.txt"


@pytest.mark.parametrize(
    ("render", "prefix"),
    [(_protection, "[SP-PROTECT]"), (_columns, "[SP-COLUMNS]")],
    ids=["protection", "columns"],
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
