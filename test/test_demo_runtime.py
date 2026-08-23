# test/test_demo_runtime.py
"""Execute the generated demo-data.js against a mock SharePoint.

The generation tests prove the plan and payload. These tests execute the
response path where SharePoint accepts a POST but stores different members.
A row is not recorded as created until the stored value matches the mapping.

Node is required; the tests skip without it rather than failing, since it is
not a dependency of the package.
"""

import json
import textwrap
from typing import Any

import pytest
from _model import bundle as make_bundle
from _model import column, enum, ref
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE
from _node import run_node as _run
from _paths import FIXTURES

from dbml_sharepoint.generators.demogen import generate_demo_js
from dbml_sharepoint.model.mapping_types import DemoItem
from dbml_sharepoint.model.release import load_release

# The Note row tests no unnecessary readback and no demo_ref into an unverified row.
_MEMBERS = ["View", "Edit"]


def _demo_js(members: list[str]) -> str:
    schema = make_schema(
        make_table("Audit", column("Title", required=True), column("Events", "audit_event[]")),
        make_table("Note", column("Title", required=True), ref("RelatedAudit", "Audit.Id")),
        enums=[enum("audit_event", "View", "Edit", "Delete")],
    )
    bundle = make_bundle(
        entities=["Audit", "Note"],
        demo_items={
            "Audit": [
                DemoItem(key="a1", values={"Title": "[DEMO] Audit", "Events": members}),
            ],
            "Note": [
                DemoItem(key="n1", values={
                    "Title": "[DEMO] Note", "RelatedAudit": {"demo_ref": "a1"},
                }),
            ],
        },
    )
    return generate_demo_js(
        schema=schema,
        bundle=bundle,
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="s.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


# The mock stores the configured verbose-OData answer after accepting each create.
_HARNESS = textwrap.dedent(r"""
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const STORED = null;
    const READBACK_STATUS = 200;
    let nextId = 100;
    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      calls.push({ url: u, method, headers: opts.headers || null,
                   body: opts.body === undefined ? null : opts.body });
      let status = 200;
      // No matching title exists, so every row follows the create path.
      let payload = { d: { results: [] } };
      if (u.includes('contextinfo')) {
        payload = { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } };
      } else if (u.includes('ListItemEntityTypeFullName')) {
        payload = { d: { ListItemEntityTypeFullName: 'SP.Data.APP_AuditListItem' } };
      } else if (method === 'POST') {
        payload = { d: { Id: nextId++ } };
      } else if (/\/items\(\d+\)/.test(u)) {
        status = READBACK_STATUS;
        payload = status === 200
          ? { d: { Events: STORED } }
          : { error: { message: { value: 'read-back refused' } } };
      }
      return {
        ok: status < 400, status,
        headers: { get: () => null },
        json: async () => payload,
        text: async () => JSON.stringify(payload),
      };
    };
    globalThis.__calls = calls;
""")

_FAITHFUL: dict[str, Any] = {
    "__metadata": {"type": "Collection(Edm.String)"},
    "results": ["View", "Edit"],
}


def _seed(
    *,
    stored: Any = _FAITHFUL,
    readback_status: int = 200,
    members: list[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run demo-data.js against the mock and return (summary, calls)."""
    harness = _HARNESS.replace(
        "const STORED = null;", f"const STORED = {json.dumps(stored)};", 1,
    ).replace(
        "const READBACK_STATUS = 200;", f"const READBACK_STATUS = {readback_status};", 1,
    )
    # Preserve an explicit empty member list rather than replacing it through truthiness.
    script = harness + "\n" + _demo_js(_MEMBERS if members is None else members).replace(
        "})();",
        "}))().then(r => { console.log('__RESULT__' + JSON.stringify(r)); "
        "console.log('__CALLS__' + JSON.stringify(globalThis.__calls)); })",
    ).replace("(async () => {", "((async () => {", 1)
    output = _run(script)
    lines = output.splitlines()
    result = next((ln for ln in lines if ln.startswith("__RESULT__")), None)
    calls = next((ln for ln in lines if ln.startswith("__CALLS__")), None)
    assert result is not None, f"demo-data.js did not return a summary:\n{output[-3000:]}"
    assert calls is not None, f"demo-data.js did not reach the call log:\n{output[-3000:]}"
    return (
        json.loads(result.removeprefix("__RESULT__")),
        json.loads(calls.removeprefix("__CALLS__")),
    )


def _keys(rows: list[dict[str, Any]]) -> set[str]:
    return {row["key"] for row in rows}


def _error_for(summary: dict[str, Any], key: str) -> str:
    matches = [row["error"] for row in summary["errors"] if row["key"] == key]
    assert matches, f"demo row '{key}' reported no error: {summary}"
    return str(matches[0])


def _readbacks(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every per-item GET, which is the read-back and nothing else."""
    return [c for c in calls if c["method"] == "GET" and "/items(" in c["url"]]


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def test_a_multi_value_row_is_read_back_before_it_is_recorded_created() -> None:
    """The write is not a fact until the stored value has been seen.

    Nothing else in this file can tell a verified write from an unverified
    one that happened to be faithful, so the request itself is asserted.
    """
    _, calls = _seed()
    reads = _readbacks(calls)
    assert len(reads) == 1, f"expected one read-back, got {[c['url'] for c in reads]}"
    assert "%24select=Events" in reads[0]["url"] or "$select=Events" in reads[0]["url"]
    assert reads[0]["headers"]["Accept"] == "application/json;odata=verbose"


def test_a_faithful_readback_records_the_row_as_created() -> None:
    """The measured shape must still pass.

    An order-sensitive or `results`-blind comparison would fail this row,
    which is correct seeding answered by the shape probe M3 wrote.
    """
    summary, _ = _seed()
    assert _keys(summary["created"]) == {"a1", "n1"}
    assert summary["errors"] == []


def test_a_dropped_member_is_never_recorded_as_created() -> None:
    """SharePoint accepting a POST is not SharePoint storing what was sent."""
    summary, _ = _seed(stored={**_FAITHFUL, "results": ["View"]})
    assert "a1" not in _keys(summary["created"])
    assert "Edit" in _error_for(summary, "a1")
    assert "Events" in _error_for(summary, "a1")


def test_a_normalised_member_is_never_recorded_as_created() -> None:
    """A member stored under a different casing is a different member.

    The demo row exists so a view filter and a formatter map have something
    to match, and both compare exactly.
    """
    summary, _ = _seed(stored={**_FAITHFUL, "results": ["View", "edit"]})
    assert "a1" not in _keys(summary["created"])
    assert "Edit" in _error_for(summary, "a1")


def test_a_member_the_row_never_asked_for_is_never_recorded_as_created() -> None:
    summary, _ = _seed(stored={**_FAITHFUL, "results": ["View", "Edit", "Delete"]})
    assert "a1" not in _keys(summary["created"])
    assert "Delete" in _error_for(summary, "a1")


def test_a_seeded_column_reading_back_null_is_never_recorded_as_created() -> None:
    """`null` is the M4 shape for an UNSET column (2026-08-17).

    Reading it where members were sent means the write did nothing, which is
    the exact failure a bare `createResp.ok` cannot see.
    """
    summary, _ = _seed(stored=None)
    assert "a1" not in _keys(summary["created"])
    assert "Events" in _error_for(summary, "a1")


def test_an_unrecognised_readback_shape_is_never_recorded_as_created() -> None:
    """A delimited string is not the measured verbose-OData collection shape."""
    summary, _ = _seed(stored="View;#Edit")
    assert "a1" not in _keys(summary["created"])
    assert "Events" in _error_for(summary, "a1")


def test_a_readback_without_collection_metadata_is_never_verified() -> None:
    summary, _ = _seed(stored={"results": ["View", "Edit"]})
    assert "a1" not in _keys(summary["created"])
    assert "Events" in _error_for(summary, "a1")


def test_a_readback_with_the_wrong_collection_type_is_never_verified() -> None:
    summary, _ = _seed(stored={
        "__metadata": {"type": "Collection(Edm.Int32)"},
        "results": ["View", "Edit"],
    })
    assert "a1" not in _keys(summary["created"])
    assert "Events" in _error_for(summary, "a1")


def test_a_readback_with_an_unmeasured_top_level_property_is_never_verified() -> None:
    summary, _ = _seed(stored={**_FAITHFUL, "unexpected": True})
    assert "a1" not in _keys(summary["created"])
    assert "Events" in _error_for(summary, "a1")


def test_a_bare_array_readback_is_never_recorded_as_created() -> None:
    """One reading of a Collection(Edm.String), the one this repository has
    seen: `deploy/_shape_probes.js.j2` refuses anything but `{results: [...]}`
    for a field's `Choices` under the same verbose Accept, and an item's value
    is written as the same EDM type. A second reading here would be a shape
    accepted on plausibility, and the members it yielded would be recorded as
    verified.
    """
    summary, _ = _seed(stored=["View", "Edit"])
    assert "a1" not in _keys(summary["created"])
    assert "Events" in _error_for(summary, "a1")


def test_a_refused_readback_is_never_recorded_as_created() -> None:
    """A GET that did not arrive is not an observation that the write stuck."""
    summary, _ = _seed(readback_status=500)
    assert "a1" not in _keys(summary["created"])
    assert "500" in _error_for(summary, "a1")


def test_a_row_whose_write_is_unverified_resolves_no_later_demo_ref() -> None:
    """Fail closed all the way down: a lookup into an unverified row would
    point a second demo row at an item nothing has proved."""
    summary, _ = _seed(stored={**_FAITHFUL, "results": ["View"]})
    assert _keys(summary["created"]) == set()
    assert _keys(summary["errors"]) == {"a1", "n1"}


def test_a_row_with_no_multi_value_field_is_not_read_back() -> None:
    """Single-value seeding keeps its one POST and its one existence probe.

    The Note row has a literal Title and a lookup, so a read-back against it
    would be a request no measurement asked for.
    """
    _, calls = _seed()
    assert not [c for c in _readbacks(calls) if "APP_Note" in c["url"]]


def test_an_empty_multi_value_row_is_not_read_back() -> None:
    """The planner omits an empty list, so there is no member to verify.

    Reading back would compare against nothing and, on the `null` M4 answer,
    would have to call an unset column either right or wrong with no
    declaration to check it against.
    """
    _, calls = _seed(members=[])
    assert _readbacks(calls) == []


def test_the_created_item_is_posted_as_the_measured_collection() -> None:
    """The read-back must not have changed what goes out (probe M3)."""
    _, calls = _seed()
    posts = [
        json.loads(c["body"]) for c in calls
        if c["method"] == "POST" and c["body"] and "Events" in c["body"]
    ]
    assert len(posts) == 1
    assert posts[0]["Events"] == {
        "__metadata": {"type": "Collection(Edm.String)"},
        "results": ["View", "Edit"],
    }


def test_the_readback_uses_the_same_metadata_type_as_the_write_plan() -> None:
    js = _demo_js(_MEMBERS)
    assert "metadata.type !== field.metadata_type" in js
    assert "storedMembers(item, f, stored[f.name])" in js
