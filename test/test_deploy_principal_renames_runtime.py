# test/test_deploy_principal_renames_runtime.py
"""Execute the generated deploy.js against a mock site holding a group and
a permission level under previous names.

The security phase renames a group or level in place only when exactly one
previous name exists carrying the marker that name produces, and the
current name is absent. These runs pin the retitle by id and its readback,
that nothing is created under the current name, that a previous name
without its marker or beside the current name stops the phase before any
write, and that the assessment predicts the same decision.

Node is required; the tests skip without it rather than failing.
"""

import json
import textwrap
from pathlib import Path
from typing import Any

import pytest
from _batch_mock import BATCH_MOCK
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE
from _node import run_node as _run
from _packs import write_mapping
from _paths import FIXTURES

from dbml_sharepoint.analysis.group_description import marker_for_group
from dbml_sharepoint.analysis.list_description import family_for
from dbml_sharepoint.analysis.role_definition_description import marker_for_level
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.release import load_release

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

OLD_GROUP_ID = 11
OLD_LEVEL_ID = 1073741925

_MAPPING = """
    prefix: "GOV_"
    previous_prefixes: ["", "ADOPT_"]
    entities:
      Risk: { kind: List, base_template: 100, site_role: default }
    permission_levels:
      - name: "{prefix} Submit Only"
        description: "Add and read."
        base_permissions: [AddListItems, ViewListItems]
    groups:
      - name: "{prefix} Programme Leads"
        description: "The programme owner and the governance lead."
        owner_group: "Site Owners"
        renamed_from: ["{prefix} Program Governance"]
"""

_HARNESS = textwrap.dedent(r"""
    const GROUPS = {};
    const LEVELS = {};
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const state = {
      groups: { ...GROUPS }, levels: { ...LEVELS }, lists: {},
      nextGroupId: 20, nextLevelId: 1073741990, nextListId: 1,
    };
    const lower = (v) => String(v).toLowerCase();
    const groups = () => Object.values(state.groups);
    const levels = () => Object.values(state.levels);
    const groupByName = (name) => groups().find((g) => lower(g.Title) === lower(name)) || null;
    const groupById = (id) => groups().find((g) => String(g.Id) === String(id)) || null;
    const levelByName = (name) => levels().find((l) => lower(l.Name) === lower(name)) || null;
    const levelById = (id) => levels().find((l) => String(l.Id) === String(id)) || null;
    const builtin = { Id: 3, Title: 'Site Owners', PrincipalType: 8 };
    const reply = (status, payload) => ({
      ok: status < 400, status, headers: { get: () => null },
      json: async () => payload, text: async () => JSON.stringify(payload),
    });
    const notFound = () => reply(404, { error: { message: { value: 'not found' } } });
    const groupShape = (g) => ({
      Id: g.Id, Title: g.Title, Description: g.Description, PrincipalType: 8,
      AllowMembersEditMembership: !!g.AllowMembersEditMembership,
      AllowRequestToJoinLeave: !!g.AllowRequestToJoinLeave,
      AutoAcceptRequestToJoinLeave: !!g.AutoAcceptRequestToJoinLeave,
      OnlyAllowMembersViewMembership: !!g.OnlyAllowMembersViewMembership,
    });
    const levelShape = (l) => ({
      Id: l.Id, Name: l.Name, Description: l.Description,
      BasePermissions: { High: String(l.High || 0), Low: String(l.Low || 0) },
    });
    const applyGroupMerge = (g, body) => {
      if (typeof body.Title === 'string' && body.Title !== g.Title) {
        delete state.groups[g.Title]; g.Title = body.Title; state.groups[g.Title] = g;
      }
      for (const k of ['Description', 'AllowMembersEditMembership', 'AllowRequestToJoinLeave',
        'AutoAcceptRequestToJoinLeave', 'OnlyAllowMembersViewMembership']) {
        if (k in body) g[k] = body[k];
      }
    };
    const applyLevelMerge = (l, body) => {
      if (typeof body.Name === 'string' && body.Name !== l.Name) {
        delete state.levels[l.Name]; l.Name = body.Name; state.levels[l.Name] = l;
      }
      if ('Description' in body) l.Description = body.Description;
      if (body.BasePermissions) {
        l.High = body.BasePermissions.High;
        l.Low = body.BasePermissions.Low;
      }
    };
    globalThis.fetch = async (url, opts = {}) => {
      const u = decodeURIComponent(String(url));
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const body = opts.body ? JSON.parse(opts.body) : null;
      calls.push({ url: u, method, headers, body });
      const verb = headers['X-HTTP-Method'] || method;
      if (u.includes('contextinfo')) {
        const info = { FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 };
        return reply(200, { d: { GetContextWebInformation: info } });
      }
      if (u.toLowerCase().includes('effectivebasepermissions')) {
        const all = { High: 4294967295, Low: 4294967295 };
        return reply(200, { d: { EffectiveBasePermissions: all } });
      }
      if (u.includes('web/currentuser')) {
        const me = { Id: 1, LoginName: 'i:0#.f|membership|probe@example.com', Title: 'Probe' };
        return reply(200, { d: me });
      }
      if (/web\/Associated(Owner|Member|Visitor)Group/.test(u)) return reply(200, { d: builtin });
      // Site groups.
      if (/web\/sitegroups\?/.test(u)) {
        return reply(200, { d: { results: groups().map(groupShape) } });
      }
      const gByName = /web\/sitegroups\/getbyname\('([^']+)'\)(.*)$/.exec(u);
      const gById = /web\/sitegroups\((\d+)\)(.*)$/.exec(u);
      if (gByName || gById) {
        const rest = (gByName || gById)[2];
        const g = gByName
          ? (lower(gByName[1]) === 'site owners' ? builtin : groupByName(gByName[1]))
          : groupById(gById[1]);
        if (!g) return notFound();
        if (rest.startsWith('/owner')) return reply(200, { d: builtin });
        if (rest.startsWith('/users')) {
          return reply(200, method === 'POST' ? { d: {} } : { d: { results: [] } });
        }
        if (verb === 'MERGE') {
          if (g !== builtin) applyGroupMerge(g, body || {});
          return reply(204, {});
        }
        return reply(200, { d: g === builtin ? builtin : groupShape(g) });
      }
      if (method === 'POST' && /\/_api\/web\/sitegroups$/.test(u) && body && body.Title) {
        const created = {
          Id: state.nextGroupId++, Title: body.Title, Description: body.Description || '',
        };
        applyGroupMerge(created, body);
        state.groups[created.Title] = created;
        return reply(201, { d: groupShape(created) });
      }
      // Role definitions.
      const filtered = /web\/roledefinitions\?.*\$filter=Name eq '([^']+)'/.exec(u);
      if (filtered) {
        const l = levelByName(filtered[1]);
        return reply(200, { d: { results: l ? [levelShape(l)] : [] } });
      }
      if (/web\/roledefinitions\?/.test(u)) {
        return reply(200, { d: { results: levels().map(levelShape) } });
      }
      const lByName = /web\/roledefinitions\/getbyname\('([^']+)'\)(.*)$/.exec(u);
      const lById = /web\/roledefinitions\((\d+)\)(.*)$/.exec(u);
      if (lByName || lById) {
        const l = lByName ? levelByName(lByName[1]) : levelById(lById[1]);
        if (!l) return reply(500, { error: { message: { value: 'no such role definition' } } });
        if (verb === 'MERGE') { applyLevelMerge(l, body || {}); return reply(204, {}); }
        return reply(200, { d: levelShape(l) });
      }
      if (method === 'POST' && /\/_api\/web\/roledefinitions$/.test(u) && body && body.Name) {
        const created = {
          Id: state.nextLevelId++, Name: body.Name, Description: body.Description || '',
        };
        applyLevelMerge(created, body);
        state.levels[created.Name] = created;
        return reply(201, { d: levelShape(created) });
      }
      if (u.includes('web/roleassignments')) return reply(200, { d: { results: [] } });
      // Lists: none exist; a create answers with an id so later phases proceed.
      if (/web\/lists\?\$select=Title/.test(u)) return reply(200, { d: { results: [] } });
      if (/web\/lists\/getbytitle\(/.test(u) || /web\/lists\(guid'/.test(u)) return notFound();
      if (method === 'POST' && /\/_api\/web\/lists$/.test(u) && body && body.Title) {
        const id = `bbbbbbbb-0000-0000-0000-${String(state.nextListId++).padStart(12, '0')}`;
        return reply(201, { d: { Id: id, Title: body.Title } });
      }
      return reply(200, { d: { results: [] } });
    };
""") + BATCH_MOCK


def _family() -> str:
    return family_for(make_schema(make_table("Risk", "Title", note="Risks.")))


def _deploy_js(tmp_path: Path, *, with_assessment: bool = False) -> str:
    write_mapping(tmp_path, _MAPPING)
    bundle = load_mapping(tmp_path / "m.yaml")
    schema = make_schema(make_table("Risk", "Title", note="Risks."))
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


def _run_deploy(
    tmp_path: Path, groups: dict[str, dict[str, Any]], levels: dict[str, dict[str, Any]],
    *, with_assessment: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    harness = _HARNESS.replace(
        "const GROUPS = {};", f"const GROUPS = {json.dumps(groups)};", 1,
    ).replace(
        "const LEVELS = {};", f"const LEVELS = {json.dumps(levels)};", 1,
    )
    body = _deploy_js(tmp_path, with_assessment=with_assessment).rstrip()
    assert body.endswith("})();")
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(calls));\n"
        "  console.log('__STATE__' + JSON.stringify("
        "    { groups: state.groups, levels: state.levels }));\n"
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


def _old_group(description: str) -> dict[str, dict[str, Any]]:
    return {"ADOPT Program Governance": {
        "Id": OLD_GROUP_ID, "Title": "ADOPT Program Governance", "Description": description,
    }}


def _old_level(description: str) -> dict[str, dict[str, Any]]:
    return {"ADOPT Submit Only": {
        "Id": OLD_LEVEL_ID, "Name": "ADOPT Submit Only", "Description": description,
        "High": 0, "Low": 3,
    }}


def _old_group_marker() -> str:
    return marker_for_group("ADOPT Program Governance", _family())


def _old_level_marker() -> str:
    return marker_for_level(_family(), "ADOPT Submit Only")


def _writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        c for c in calls
        if c["method"] == "POST" and (
            c["headers"].get("X-HTTP-Method") in ("MERGE", "DELETE")
            or c["url"].endswith(
                ("/_api/web/sitegroups", "/_api/web/roledefinitions", "/_api/web/lists"),
            )
        )
    ]


def test_a_previous_group_name_carrying_its_marker_is_retitled_in_place(tmp_path: Path) -> None:
    summary, calls, state = _run_deploy(
        tmp_path, _old_group(f"Old leads. {_old_group_marker()}"),
        _old_level(f"x {_old_level_marker()}"),
    )
    renames = [
        c for c in calls
        if c["headers"].get("X-HTTP-Method") == "MERGE"
        and f"web/sitegroups({OLD_GROUP_ID})" in c["url"]
        and (c["body"] or {}).get("Title") == "GOV Programme Leads"
    ]
    assert len(renames) == 1, "expected exactly one retitle MERGE by group id"
    assert marker_for_group("GOV Programme Leads", _family()) in renames[0]["body"]["Description"]
    i_rename = calls.index(renames[0])
    assert any(
        c["method"] == "GET" and f"web/sitegroups({OLD_GROUP_ID})" in c["url"]
        for c in calls[i_rename + 1:]
    )
    creates = [
        c for c in calls if c["url"].endswith("/_api/web/sitegroups") and c["method"] == "POST"
    ]
    assert creates == [], f"the deploy created a group instead of renaming: {creates}"
    assert summary["groupsRenamed"] == [
        {"from": "ADOPT Program Governance", "to": "GOV Programme Leads"},
    ]
    assert state["groups"]["GOV Programme Leads"]["Id"] == OLD_GROUP_ID
    assert "ADOPT Program Governance" not in state["groups"]


def test_a_previous_level_name_carrying_its_marker_is_retitled_in_place(tmp_path: Path) -> None:
    summary, calls, state = _run_deploy(
        tmp_path, _old_group(f"Old leads. {_old_group_marker()}"),
        _old_level(f"x {_old_level_marker()}"),
    )
    renames = [
        c for c in calls
        if c["headers"].get("X-HTTP-Method") == "MERGE"
        and f"web/roledefinitions({OLD_LEVEL_ID})" in c["url"]
        and (c["body"] or {}).get("Name") == "GOV Submit Only"
    ]
    assert len(renames) == 1, "expected exactly one retitle MERGE by role definition id"
    assert marker_for_level(_family(), "GOV Submit Only") in renames[0]["body"]["Description"]
    creates = [
        c for c in calls
        if c["url"].endswith("/_api/web/roledefinitions") and c["method"] == "POST"
    ]
    assert creates == []
    assert summary["levelsRenamed"] == [{"from": "ADOPT Submit Only", "to": "GOV Submit Only"}]
    assert state["levels"]["GOV Submit Only"]["Id"] == OLD_LEVEL_ID


def test_a_previous_group_without_its_marker_stops_the_phase_before_any_write(
    tmp_path: Path,
) -> None:
    summary, calls, state = _run_deploy(
        tmp_path, _old_group("A hand-made group."), _old_level(f"x {_old_level_marker()}"),
    )
    assert summary["aborted"] == "phase-0-rename-errors"
    assert _writes(calls) == []
    assert "ADOPT Program Governance" in state["groups"] and "ADOPT Submit Only" in state["levels"]


def test_a_previous_name_beside_the_current_name_stops_the_phase(tmp_path: Path) -> None:
    groups = _old_group(f"Old leads. {_old_group_marker()}")
    groups["GOV Programme Leads"] = {"Id": 12, "Title": "GOV Programme Leads", "Description": "x"}
    summary, calls, _state = _run_deploy(tmp_path, groups, _old_level(f"x {_old_level_marker()}"))
    assert summary["aborted"] == "phase-0-rename-errors"
    assert _writes(calls) == []


def test_the_assessment_blocks_a_previous_group_without_its_marker(tmp_path: Path) -> None:
    summary, calls, _state = _run_deploy(
        tmp_path, _old_group("A hand-made group."), _old_level(f"x {_old_level_marker()}"),
        with_assessment=True,
    )
    assert summary["aborted"] == "assessment-blocked"
    findings = summary["assessment"]["findings"]
    blocked = [f for f in findings if f["key"] == "rename_group:GOV Programme Leads"]
    assert len(blocked) == 1 and blocked[0]["level"] == "BLOCKED"
    assert _writes(calls) == []


def test_the_assessment_reports_the_level_it_will_rename(tmp_path: Path) -> None:
    summary, _calls, _state = _run_deploy(
        tmp_path, _old_group(f"Old leads. {_old_group_marker()}"),
        _old_level(f"x {_old_level_marker()}"),
        with_assessment=True,
    )
    findings = summary["assessment"]["findings"]
    planned = [f for f in findings if f["key"] == "rename_level:GOV Submit Only"]
    assert len(planned) == 1 and planned[0]["level"] == "INFO"
    assert "ADOPT Submit Only" in planned[0]["detail"]
