# test/test_deploy_renames_runtime.py
"""Execute the generated deploy.js against a mock site that holds a list
under a previous title.

`renamed_from` is only worth anything at the point the deploy decides
whether the list it found is the one it declared. These runs pin that
decision: a previous title carrying its exact previous marker is retitled
in place and read back, and nothing is created under the new title; a
previous title without that marker, or present beside the new title, stops
the run before any write, at preflight and, with the assessment on, at the
assessment itself.

Node is required; the tests skip without it rather than failing.
"""

import json
import textwrap
from typing import Any

import pytest
from _model import bundle as make_bundle
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE
from _node import run_node as _run
from _paths import FIXTURES

from dbml_sharepoint.analysis.list_description import family_for, marker_for
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.mapping_types import EntityMapping
from dbml_sharepoint.model.release import load_release

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

OLD_ID = "aaaaaaaa-1111-1111-1111-111111111111"

_HARNESS = textwrap.dedent(r"""
    const LISTS = {};
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    // Title -> list. A MERGE that carries Title moves the entry, exactly as
    // SharePoint resolves getbytitle after a rename.
    const state = { lists: { ...LISTS }, nextId: 1 };
    const byGuid = (guid) => Object.values(state.lists)
      .find((l) => String(l.Id).toLowerCase() === String(guid).toLowerCase());
    const shapeOf = (l) => ({
      Id: l.Id, Title: l.Title, BaseTemplate: 100, ContentTypesEnabled: false,
      Description: l.Description, EnableVersioning: false, EnableMinorVersions: false,
      MajorVersionLimit: 0, ValidationFormula: null, ValidationMessage: null,
    });
    const reply = (status, payload) => ({
      ok: status < 400, status, headers: { get: () => null },
      json: async () => payload, text: async () => JSON.stringify(payload),
    });
    const notFound = () => reply(404, { error: { message: { value: 'not found' } } });
    const applyMerge = (l, body) => {
      if (typeof body.Title === 'string' && body.Title !== l.Title) {
        delete state.lists[l.Title];
        l.Title = body.Title;
        state.lists[l.Title] = l;
      }
      if (typeof body.Description === 'string') l.Description = body.Description;
    };
    globalThis.fetch = async (url, opts = {}) => {
      const u = decodeURIComponent(String(url));
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const body = opts.body ? JSON.parse(opts.body) : null;
      calls.push({ url: u, method, headers, body });
      const verb = headers['X-HTTP-Method'] || method;
      if (u.includes('contextinfo')) {
        return reply(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } });
      }
      if (u.toLowerCase().includes('effectivebasepermissions')) {
        const all = { High: 4294967295, Low: 4294967295 };
        return reply(200, { d: { EffectiveBasePermissions: all } });
      }
      if (/web\/lists\?\$select=Title/.test(u)) {
        const rows = Object.values(state.lists)
          .map((l) => ({ Title: l.Title, ItemCount: 0, Hidden: false }));
        return reply(200, { d: { results: rows } });
      }
      const byTitle = /web\/lists\/getbytitle\('([^']+)'\)(.*)$/.exec(u);
      const byId = /web\/lists\(guid'([^']+)'\)(.*)$/.exec(u);
      let list = null;
      let rest = '';
      if (byTitle) { list = state.lists[byTitle[1]] || null; rest = byTitle[2]; }
      else if (byId) { list = byGuid(byId[1]) || null; rest = byId[2]; }
      if (byTitle || byId) {
        if (!list) return notFound();
        if (rest.startsWith('/')) return reply(200, { d: { results: [] } });
        if (verb === 'MERGE') { applyMerge(list, body || {}); return reply(204, {}); }
        return reply(200, { d: shapeOf(list) });
      }
      if (method === 'POST' && /\/_api\/web\/lists$/.test(u) && body && body.Title) {
        const suffix = String(state.nextId++).padStart(12, '0');
        const created = { Id: `bbbbbbbb-0000-0000-0000-${suffix}`,
          Title: body.Title, Description: body.Description || '' };
        state.lists[created.Title] = created;
        return reply(201, { d: shapeOf(created) });
      }
      return reply(200, { d: { results: [] } });
    };
""")


def _deploy_js(*, with_assessment: bool = False) -> str:
    schema = make_schema(make_table("Risk", "Title", note="Risks."))
    bundle = make_bundle(entities={
        "Risk": EntityMapping(
            name="Risk", kind="List", base_template=100, site_role="default",
            renamed_from=("ProgramRisk",),
        ),
    })
    js = generate_deploy_js(
        schema=schema, bundle=bundle, release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test", site_role="default",
        source_dbml="x.dbml", source_mtime="2026-09-03T00:00:00Z",
        generated_at="2026-09-03T00:00:00Z",
    )
    if with_assessment:
        return js
    stubbed = js.replace(
        "    assessment = await assessSite({",
        "    assessment = { findings: [], verdict: 'COMPATIBLE' };\n"
        "    if (false) await assessSite({",
        1,
    )
    assert stubbed != js
    return stubbed


def _family() -> str:
    return family_for(make_schema(make_table("Risk", "Title", note="Risks.")))


def _old_marker() -> str:
    return marker_for(_family(), "ProgramRisk")


def _new_marker() -> str:
    return marker_for(_family(), "Risk")


def _run_deploy(
    lists: dict[str, dict[str, Any]], *, with_assessment: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    harness = _HARNESS.replace("const LISTS = {};", f"const LISTS = {json.dumps(lists)};", 1)
    body = _deploy_js(with_assessment=with_assessment).rstrip()
    assert body.endswith("})();")
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(calls));\n"
        "  console.log('__STATE__' + JSON.stringify(state.lists));\n"
        "});\n"
    )
    output = _run(script)
    lines = output.splitlines()
    markers = ("__RESULT__", "__CALLS__", "__STATE__")
    found = {m: next((ln for ln in lines if ln.startswith(m)), None) for m in markers}
    missing = [m for m, ln in found.items() if ln is None]
    assert not missing, f"deploy.js never reached {missing}:\n{output[-4000:]}"
    summary, calls, state = (json.loads((found[m] or "").removeprefix(m)) for m in markers)
    return summary, calls, state


def _old_list(description: str) -> dict[str, dict[str, Any]]:
    return {
        "APP_ProgramRisk": {"Id": OLD_ID, "Title": "APP_ProgramRisk", "Description": description},
    }


def _writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        c for c in calls
        if c["method"] == "POST" and (
            c["headers"].get("X-HTTP-Method") in ("MERGE", "DELETE")
            or c["url"].endswith("/_api/web/lists")
        )
    ]


def test_a_previous_title_carrying_its_marker_is_retitled_in_place() -> None:
    summary, calls, state = _run_deploy(_old_list(f"Old risks. {_old_marker()}"))
    renames = [
        c for c in calls
        if c["headers"].get("X-HTTP-Method") == "MERGE" and OLD_ID in c["url"]
        and (c["body"] or {}).get("Title") == "APP_Risk"
    ]
    assert len(renames) == 1, "expected exactly one retitle MERGE by list id"
    assert _new_marker() in renames[0]["body"]["Description"]
    i_rename = calls.index(renames[0])
    assert any(
        c["method"] == "GET" and OLD_ID in c["url"] for c in calls[i_rename + 1:]
    ), "no readback after the retitle"
    creates = [c for c in calls if c["url"].endswith("/_api/web/lists") and c["method"] == "POST"]
    assert creates == [], f"the deploy created a list instead of renaming: {creates}"
    assert summary["listsRenamed"] == [{"from": "APP_ProgramRisk", "to": "APP_Risk"}]
    assert "APP_Risk" in state and "APP_ProgramRisk" not in state
    assert state["APP_Risk"]["Id"] == OLD_ID


def test_a_previous_title_without_its_marker_stops_the_run_before_any_write() -> None:
    summary, calls, state = _run_deploy(_old_list("A hand-made list called ProgramRisk."))
    assert summary["aborted"] == "existing-schema-shape-errors"
    assert _writes(calls) == []
    assert "APP_ProgramRisk" in state and "APP_Risk" not in state


def test_a_previous_title_beside_the_current_title_stops_the_run() -> None:
    lists = _old_list(f"Old risks. {_old_marker()}")
    lists["APP_Risk"] = {
        "Id": "cccccccc-2222-2222-2222-222222222222", "Title": "APP_Risk",
        "Description": f"Risks. {_new_marker()}",
    }
    summary, calls, _state = _run_deploy(lists)
    assert summary["aborted"] == "existing-schema-shape-errors"
    assert _writes(calls) == []


def test_the_assessment_blocks_a_previous_title_without_its_marker() -> None:
    summary, calls, _state = _run_deploy(
        _old_list("A hand-made list called ProgramRisk."), with_assessment=True,
    )
    assert summary["aborted"] == "assessment-blocked"
    blocked = [f for f in summary["assessment"]["findings"] if f["key"] == "rename:APP_Risk"]
    assert len(blocked) == 1 and blocked[0]["level"] == "BLOCKED"
    assert _writes(calls) == []


def test_the_assessment_reports_the_rename_it_will_make() -> None:
    summary, _calls, _state = _run_deploy(
        _old_list(f"Old risks. {_old_marker()}"), with_assessment=True,
    )
    planned = [f for f in summary["assessment"]["findings"] if f["key"] == "rename:APP_Risk"]
    assert len(planned) == 1 and planned[0]["level"] == "INFO"
    assert "APP_ProgramRisk" in planned[0]["detail"] and "renamed" in planned[0]["detail"]
