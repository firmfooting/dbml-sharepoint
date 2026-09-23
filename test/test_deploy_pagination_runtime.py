"""Malformed continuations must not authorize deploy writes from partial reads."""

import json
from pathlib import Path
from typing import Any

import pytest
from _node import NODE
from test_deploy_runtime import (
    _ADOPTED_HARNESS,
    _READER_ACL_HARNESS,
    _RESOLVED_USER,
    _deploy_js,
    _membership_writes,
    _ownership_deploy_js,
    _ownership_list_descriptions,
    _reader_deploy_js,
    _reader_harness,
    _run_capturing_calls,
)

from dbml_sharepoint.analysis.phases import phase_number

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _continuation_overlay(phase: str, url_part: str, marker: Any) -> str:
    return f"""
const continuationFetch = globalThis.fetch;
globalThis.fetch = async (url, opts = {{}}) => {{
  const response = await continuationFetch(url, opts);
  if (mockPhase !== {json.dumps(phase_number(phase))}
      || !String(url).includes({json.dumps(url_part)})
      || (opts.method || 'GET') !== 'GET') return response;
  const payload = await response.json();
  payload.d.__next = {json.dumps(marker)};
  console.log('CONTINUATION_INJECTED');
  return {{ ...response, json: async () => payload, text: async () => JSON.stringify(payload) }};
}};
"""


@pytest.mark.parametrize("marker", [False, 0, True, 7, [], {}, None, ""])
@pytest.mark.parametrize("surface", [
    "group_members", "role_usage", "role_existence", "reader_members", "reader_roles",
    "fields", "acl", "seeds",
])
def test_deploy_reads_validate_continuation_markers(
    tmp_path: Path, surface: str, marker: Any,
) -> None:
    if surface.startswith("reader"):
        js = _reader_deploy_js()
        harness = _reader_harness(_RESOLVED_USER)
        phase = "reader_enrolment"
        part = "/users?" if surface == "reader_members" else "web/roleassignments?"
    elif surface in {"acl", "seeds"}:
        js = _ownership_deploy_js(tmp_path, ("Escalation",))
        descriptions = _ownership_list_descriptions(tmp_path, ("Escalation",))
        harness = _READER_ACL_HARNESS.replace(
            "const LIST_DESCRIPTIONS = new Map([]);",
            f"const LIST_DESCRIPTIONS = new Map({json.dumps(list(descriptions.items()))});",
        )
        phase = "seeds" if surface == "seeds" else "acls"
        part = "/items?" if surface == "seeds" else "/roleassignments?"
    else:
        js = _deploy_js()
        harness = _ADOPTED_HARNESS
        phase = "preflight" if surface == "fields" else "security"
        part = {
            "fields": "/fields?",
            "group_members": "/users?",
            "role_usage": "web/roleassignments?",
            "role_existence": "web/roledefinitions?",
        }[surface]
        if surface == "group_members":
            harness = harness.replace(
                "const KNOWN_GROUP_NAMES = [];",
                'const KNOWN_GROUP_NAMES = ["List Maintainer"];',
            )
        if surface == "role_usage":
            harness = harness.replace(
                "const ROLE_DEF_DESCRIPTION_OVERRIDE = null;",
                'const ROLE_DEF_DESCRIPTION_OVERRIDE = "Unmarked level";',
            )
    summary, calls, output = _run_capturing_calls(
        harness + _continuation_overlay(phase, part, marker), js,
    )
    assert "CONTINUATION_INJECTED" in output, output[-4000:]
    if marker is None or marker == "":
        assert "invalid OData __next continuation" not in output, output[-4000:]
        baseline, _calls, _output = _run_capturing_calls(harness, js)
        assert summary.get("errors") == baseline.get("errors")
        assert summary.get("aborted") == baseline.get("aborted")
        return
    assert "invalid OData __next continuation" in output, output[-4000:]
    assert summary.get("aborted"), summary
    if surface.startswith("reader"):
        assert not _membership_writes(calls)
    if surface == "acl":
        assert not any("removeroleassignment" in c["url"] for c in calls)
    if surface == "seeds":
        assert not any(c["method"] == "POST" and c["url"].endswith("/items") for c in calls)


@pytest.mark.parametrize("surface", ["lists", "groups"])
@pytest.mark.parametrize("payload", [
    {}, {"d": {}}, {"d": {"results": None}},
    {"d": {"results": [] , "__next": False}},
    {"d": {"results": [], "__next": 0}},
    {"d": {"results": [], "__next": {}}},
    {"d": {"results": [], "__next": "https://example.sharepoint.com/next"}},
    {"d": {"results": [{"Title": "Other"}] * 5000}},
])
def test_incomplete_name_indexes_fall_back_to_direct_probes(
    surface: str, payload: Any,
) -> None:
    harness = _ADOPTED_HARNESS.replace(
        "const KNOWN_GROUP_NAMES = [];",
        'const KNOWN_GROUP_NAMES = ["List Maintainer"];',
    )
    part = "web/lists?" if surface == "lists" else "web/sitegroups?"
    harness += f"""
const indexFetch = globalThis.fetch;
globalThis.fetch = async (url, opts = {{}}) => {{
  const response = await indexFetch(url, opts);
  if (!String(url).includes({json.dumps(part)})) return response;
  console.log('INDEX_INJECTED');
  return {{ ...response, ok: true, status: 200, json: async () => ({json.dumps(payload)}) }};
}};
"""
    js = _deploy_js()
    if surface == "lists":
        anchor = "  // The by-title read and its fail-closed shape gate"
        assert anchor in js
        js = js.replace(
            anchor,
            "  console.log('NAME_INDEX_RESULT:' + JSON.stringify(await ensureKnownListTitles()));\n"
            + anchor, 1,
        )
    _summary, calls, output = _run_capturing_calls(harness, js)
    assert "INDEX_INJECTED" in output, output[-4000:]
    if surface == "lists":
        assert "NAME_INDEX_RESULT:null" in output, output[-4000:]
    endpoint = "/web/lists" if surface == "lists" else "/web/sitegroups"
    assert not any(c["method"] == "POST" and c["url"].endswith(endpoint) for c in calls)
    by_name = "lists/getbytitle('" if surface == "lists" else "sitegroups/getbyname('"
    assert any(
        c["method"] == "GET" and by_name in c["url"]
        and c.get("phase") == phase_number("preflight" if surface == "lists" else "security")
        for c in calls
    )


@pytest.mark.parametrize("marker", [False, 0, {}, "https://example.sharepoint.com/next"])
def test_incomplete_group_rename_index_blocks_all_principal_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, marker: Any,
) -> None:
    import test_deploy_principal_renames_runtime as renames

    overlay = f"""
const renameIndexFetch = globalThis.fetch;
globalThis.fetch = async (url, opts = {{}}) => {{
  const response = await renameIndexFetch(url, opts);
  if (!String(url).includes('web/sitegroups?$select=Id,Title,Description')) return response;
  const payload = await response.json();
  payload.d.__next = {json.dumps(marker)};
  return {{ ...response, json: async () => payload }};
}};
"""
    monkeypatch.setattr(renames, "_HARNESS", renames._HARNESS + overlay)
    summary, calls, _state = renames._run_deploy(
        tmp_path, renames._old_group(renames._old_group_marker()),
        renames._old_level(renames._old_level_marker()),
    )
    assert summary["aborted"] == "phase-0-rename-errors"
    assert "invalid or incomplete response" in json.dumps(summary["errors"])
    assert renames._writes(calls) == []


def test_paged_role_existence_probe_does_not_authorize_principal_writes() -> None:
    from test_deploy_runtime import _security_writes

    summary, calls, output = _run_capturing_calls(
        _ADOPTED_HARNESS + _continuation_overlay(
            "security", "web/roledefinitions?", "https://example.sharepoint.com/next",
        ),
        _deploy_js(),
    )
    assert "CONTINUATION_INJECTED" in output
    assert "returned an incomplete response" in output
    assert summary["aborted"] == "phase-0-security-errors"
    assert not _security_writes(calls)
