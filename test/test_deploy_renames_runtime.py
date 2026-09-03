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
from _model import column
from _model import schema as make_schema
from _model import table as make_table
from _node import NODE
from _node import run_node as _run
from _paths import FIXTURES

from dbml_sharepoint.analysis.list_description import family_for, marker_for
from dbml_sharepoint.generators.jsgen import generate_deploy_js
from dbml_sharepoint.model.mapping_types import EntityMapping, MappingBundle
from dbml_sharepoint.model.parser import Schema
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


# ---------------------------------------------------------------------------
# A renamed list that is also a lookup TARGET.
#
# The preflight reads the list being probed under its PREVIOUS title, but
# resolved a lookup's target list by its DECLARED one, so every cross-list
# lookup on an unmigrated site failed with "target display field does not
# exist" -- naming the field when the missing thing was the list. Nothing here
# is lookup-specific to one family: it is every schema with a ref.
# ---------------------------------------------------------------------------

WS_ID = "aaaaaaaa-2222-2222-2222-222222222222"

_LOOKUP_HARNESS = textwrap.dedent(r"""
    const LISTS = {};
    const FIELDS = {};
    const calls = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const state = { lists: { ...LISTS }, fields: { ...FIELDS }, nextId: 1 };
    const byGuid = (guid) => Object.values(state.lists)
      .find((l) => String(l.Id).toLowerCase() === String(guid).toLowerCase());
    const shapeOf = (l) => ({
      Id: l.Id, Title: l.Title, BaseTemplate: 100, ContentTypesEnabled: false,
      Description: l.Description, EnableVersioning: false, EnableMinorVersions: false,
      MajorVersionLimit: 0, ValidationFormula: null, ValidationMessage: null,
    });
    const fieldShape = (f) => ({
      Id: f.Id, InternalName: f.InternalName, Title: f.Title,
      TypeAsString: f.TypeAsString, Description: f.Description ?? null,
      Required: !!f.Required, EnforceUniqueValues: !!f.EnforceUniqueValues,
      Indexed: !!f.Indexed, ReadOnlyField: !!f.ReadOnlyField, Sealed: !!f.Sealed,
      DefaultValue: f.DefaultValue ?? null, CustomFormatter: f.CustomFormatter ?? null,
    });
    const reply = (status, payload) => ({
      ok: status < 400, status, headers: { get: () => null },
      json: async () => payload, text: async () => JSON.stringify(payload),
    });
    const notFound = () => reply(404, { error: { message: { value: 'not found' } } });
    const applyMerge = (l, body) => {
      if (typeof body.Title === 'string' && body.Title !== l.Title) {
        const held = state.fields[l.Title];
        delete state.lists[l.Title];
        delete state.fields[l.Title];
        l.Title = body.Title;
        state.lists[l.Title] = l;
        if (held) state.fields[l.Title] = held;
      }
      if (typeof body.Description === 'string') l.Description = body.Description;
    };
    const findField = (title, name) => (state.fields[title] || [])
      .find((f) => String(f.InternalName).toLowerCase() === String(name).toLowerCase()
                || String(f.Title).toLowerCase() === String(name).toLowerCase());
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
        const one = /^\/fields\/getbyinternalnameortitle\('([^']+)'\)/.exec(rest);
        if (one) {
          const f = findField(list.Title, one[1]);
          if (!f) return notFound();
          if (verb === 'MERGE') return reply(204, {});
          // Every $select on one field answers from the seeded row: the shape
          // probe, the LookupList/LookupField pair and the per-type derived
          // properties (MaxLength and the rest) all read the same object.
          return reply(200, { d: { ...fieldShape(f), ...f } });
        }
        if (/^\/fields(\?|$)/.test(rest)) {
          return reply(200, {
            d: { results: (state.fields[list.Title] || []).map(fieldShape) } });
        }
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


def _lookup_schema(*, display_column: bool = False) -> Schema:
    """Risk.Workstream is a lookup at Workstream, which is itself renamed."""
    workstream_columns: list[Any] = ["Title"]
    if display_column:
        workstream_columns.append(column("Reference"))
    return make_schema(
        make_table("Workstream", *workstream_columns, note="Streams of work."),
        make_table(
            "Risk", "Title", column("Workstream", "int", ref="Workstream.Id"),
            note="Risks.",
        ),
    )


def _lookup_bundle(*, display_column: bool = False) -> MappingBundle:
    # Any display column other than Title defers the lookup to Phase 2.2
    # (`analysis/ordering.py`), which is the second path the resolver has to
    # reach. A text column keeps the fixture off the calculated-column probes,
    # which are not what these runs are about.
    workstream = EntityMapping(
        name="Workstream", kind="List", base_template=100, site_role="default",
        renamed_from=("ProgramWorkstream",),
        display_column="Reference" if display_column else None,
    )
    return make_bundle(entities={
        "Workstream": workstream,
        "Risk": EntityMapping(
            name="Risk", kind="List", base_template=100, site_role="default",
            renamed_from=("ProgramRisk",),
        ),
    })


def _run_lookup_deploy(
    lists: dict[str, dict[str, Any]],
    fields: dict[str, list[dict[str, Any]]],
    *,
    display_column: bool = False,
) -> dict[str, Any]:
    js = generate_deploy_js(
        schema=_lookup_schema(display_column=display_column),
        bundle=_lookup_bundle(display_column=display_column),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test", site_role="default",
        source_dbml="x.dbml", source_mtime="2026-09-03T00:00:00Z",
        generated_at="2026-09-03T00:00:00Z",
    )
    body = js.replace(
        "    assessment = await assessSite({",
        "    assessment = { findings: [], verdict: 'COMPATIBLE' };\n"
        "    if (false) await assessSite({",
        1,
    ).rstrip()
    assert body.endswith("})();")
    harness = (
        _LOOKUP_HARNESS
        .replace("const LISTS = {};", f"const LISTS = {json.dumps(lists)};", 1)
        .replace("const FIELDS = {};", f"const FIELDS = {json.dumps(fields)};", 1)
    )
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "});\n"
    )
    output = _run(script)
    line = next((ln for ln in output.splitlines() if ln.startswith("__RESULT__")), None)
    assert line is not None, f"deploy.js never returned a summary:\n{output[-4000:]}"
    summary: dict[str, Any] = json.loads(line.removeprefix("__RESULT__"))
    return summary


def _text_field(name: str, ident: str) -> dict[str, Any]:
    return {
        "Id": ident, "InternalName": name, "Title": name, "TypeAsString": "Text",
        "Description": "", "Required": False, "EnforceUniqueValues": False,
        "Indexed": False, "ReadOnlyField": False, "Sealed": False,
        "DefaultValue": None, "CustomFormatter": None, "MaxLength": 255,
    }


def _lookup_field(name: str, ident: str, target: str, show: str) -> dict[str, Any]:
    return {
        **_text_field(name, ident), "TypeAsString": "Lookup",
        "LookupList": target, "LookupField": show,
    }


def _unmigrated_site(*, display_column: bool = False) -> tuple[
    dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]],
]:
    """Both lists still under their previous titles, each carrying its marker."""
    family = family_for(_lookup_schema(display_column=display_column))
    lists = {
        "APP_ProgramWorkstream": {
            "Id": WS_ID, "Title": "APP_ProgramWorkstream",
            "Description": f"Streams. {marker_for(family, 'ProgramWorkstream')}",
        },
        "APP_ProgramRisk": {
            "Id": OLD_ID, "Title": "APP_ProgramRisk",
            "Description": f"Risks. {marker_for(family, 'ProgramRisk')}",
        },
    }
    show = "Reference" if display_column else "Title"
    workstream_fields = [_text_field("Title", "f-ws-title")]
    if display_column:
        workstream_fields.append(_text_field("Reference", "f-ws-ref"))
    fields = {
        "APP_ProgramWorkstream": workstream_fields,
        "APP_ProgramRisk": [
            _text_field("Title", "f-risk-title"),
            _lookup_field("Workstream", "f-risk-ws", WS_ID, show),
        ],
    }
    return lists, fields


def _display_field_errors(summary: dict[str, Any]) -> list[str]:
    return [
        e["error"] for e in summary.get("errors", [])
        if e.get("phase") == "preflight" and "target display field" in str(e.get("error", ""))
    ]


def test_a_lookup_at_a_renamed_target_list_is_resolved_by_its_previous_title() -> None:
    """The bug: the target was looked up under the title it does not carry yet."""
    lists, fields = _unmigrated_site()
    summary = _run_lookup_deploy(lists, fields)
    assert _display_field_errors(summary) == [], (
        "preflight refused a lookup whose target list is still under its previous "
        "title; the target must be resolved through the rename plan"
    )
    assert summary.get("aborted") != "existing-schema-shape-errors"


def test_a_deferred_lookup_at_a_renamed_target_resolves_its_display_column() -> None:
    """Same path for a lookup whose display column is not the built-in Title."""
    lists, fields = _unmigrated_site(display_column=True)
    summary = _run_lookup_deploy(lists, fields, display_column=True)
    assert _display_field_errors(summary) == [], (
        "preflight refused a deferred lookup because it read the declared target "
        "title rather than the previous one"
    )
    assert summary.get("aborted") != "existing-schema-shape-errors"
