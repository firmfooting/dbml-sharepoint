# test/test_maintain_runtime.py
"""Execute the generated protection.js and columns.js against a mock SharePoint.

Both scripts delete or unlock things on a live site, so a static read of
their text proves only what they say. Running them proves the order the
guards fire in: the unseal readback before the DELETE, the 404 readback
after it, the typed phrase before a column that holds values goes, and a
readback that disagrees stopping the run.

Node is required; the tests skip without it rather than failing, since it
is not a dependency of the package.
"""

import json
import textwrap
from typing import Any

import pytest
from _node import NODE
from _node import run_node as _run

from dbml_sharepoint.analysis.provenance import MARKER_PREFIX
from dbml_sharepoint.generators.maintaingen import (
    generate_columns_js,
    generate_protection_js,
)

SITE = "https://example.sharepoint.com/sites/test"
LIST_ID = "11111111-1111-1111-1111-111111111111"
OTHER_LIST_ID = "22222222-2222-2222-2222-222222222222"
GONE_LIST_ID = "33333333-3333-3333-3333-333333333333"

_HARNESS = textwrap.dedent(r"""
    const CONFIG = {};
    const ANSWERS = [];
    const FLAGS = {};
    const calls = [];
    const prompts = [];
    const tables = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const answers = ANSWERS.slice();
    globalThis.prompt = (message) => {
      prompts.push(message);
      return answers.length ? answers.shift() : '';
    };
    console.table = (rows) => { tables.push(rows); };

    const state = {
      list: CONFIG.list,
      fields: CONFIG.fields.map((f) => ({ ...f, deleted: false })),
      items: CONFIG.items,
      otherLists: CONFIG.otherLists || {},
    };

    const reply = (status, payload) => ({
      ok: status < 400,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    const notFound = (what) => reply(404, { error: { message: { value: `${what} not found` } } });
    const fieldById = (id) => state.fields.find((f) => f.Id === id);
    const fieldView = (f) => {
      const { deleted, lookupList, ...rest } = f;
      return rest;
    };

    globalThis.fetch = async (url, opts = {}) => {
      const u = decodeURIComponent(String(url));
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const body = opts.body ? JSON.parse(opts.body) : null;
      calls.push({ url: u, method, headers, body });
      if (u.includes('contextinfo')) {
        return reply(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } });
      }
      if (u.includes('EffectiveBasePermissions')) {
        return reply(200, { d: { EffectiveBasePermissions: { Low: 0x800, High: 0 } } });
      }
      if (u.includes("web/lists?$select=Title,Hidden")) {
        return reply(200, { d: { results: [{ Title: state.list.Title, Hidden: false }] } });
      }
      const byTitle = /getbytitle\('([^']+)'\)/.exec(u);
      if (byTitle) {
        if (byTitle[1] !== state.list.Title) return notFound('list');
        return reply(200, { d: {
          Id: state.list.Id, Title: state.list.Title, Description: state.list.Description,
          AllowDeletion: state.list.AllowDeletion, ItemCount: state.items.length,
        } });
      }
      const listGuid = /web\/lists\(guid'([^']+)'\)/.exec(u);
      if (!listGuid) return reply(400, { error: { message: { value: `unmocked ${u}` } } });
      const guid = listGuid[1].toLowerCase();
      if (guid !== state.list.Id) {
        const title = state.otherLists[guid];
        return title ? reply(200, { d: { Id: guid, Title: title } }) : notFound('list');
      }
      const fieldGuid = /fields\(guid'([^']+)'\)/.exec(u);
      if (fieldGuid) {
        const f = fieldById(fieldGuid[1]);
        if (!f || f.deleted) return notFound('field');
        if (method === 'POST' && headers['X-HTTP-Method'] === 'MERGE') {
          if (!FLAGS.discardFieldMerge) Object.assign(f, body || {}, { __metadata: undefined });
          return reply(204, {});
        }
        if (method === 'POST' && headers['X-HTTP-Method'] === 'DELETE') {
          if (!FLAGS.discardDelete) f.deleted = true;
          return reply(200, {});
        }
        if (u.includes('$select=LookupList')) {
          const lookupList = f.lookupList ? `{${f.lookupList}}` : '';
          return reply(200, { d: { LookupList: lookupList, LookupField: 'Title' } });
        }
        return reply(200, { d: fieldView(f) });
      }
      if (u.includes('/fields?')) {
        const live = state.fields.filter((f) => !f.deleted).map(fieldView);
        return reply(200, { d: { results: live } });
      }
      if (u.includes('/items?')) {
        if (FLAGS.itemsStatus) {
          return reply(FLAGS.itemsStatus, { error: { message: { value: 'items refused' } } });
        }
        return reply(200, { d: { results: state.items } });
      }
      if (method === 'POST' && headers['X-HTTP-Method'] === 'MERGE') {
        if (!FLAGS.discardListMerge && body && 'AllowDeletion' in body) {
          state.list.AllowDeletion = body.AllowDeletion;
        }
        return reply(204, {});
      }
      if (u.includes('$select=AllowDeletion')) {
        const d = { AllowDeletion: state.list.AllowDeletion, ItemCount: state.items.length };
        return reply(200, { d });
      }
      return reply(200, { d: { Id: state.list.Id, Title: state.list.Title } });
    };
""")


def _field(
    internal: str,
    *,
    field_id: str,
    kind: str = "Text",
    sealed: bool = False,
    hidden: bool = False,
    from_base: bool = False,
    can_delete: bool = True,
    lookup_list: str | None = None,
) -> dict[str, Any]:
    return {
        "Id": field_id,
        "InternalName": internal,
        "Title": internal.replace("_", " "),
        "TypeAsString": kind,
        "Hidden": hidden,
        "ReadOnlyField": False,
        "Sealed": sealed,
        "FromBaseType": from_base,
        "CanBeDeleted": can_delete,
        "lookupList": lookup_list,
    }


F_TITLE = "aaaaaaaa-0000-0000-0000-000000000001"
F_ID = "aaaaaaaa-0000-0000-0000-000000000002"
F_HIDDEN = "aaaaaaaa-0000-0000-0000-000000000003"
F_ONE = "aaaaaaaa-0000-0000-0000-000000000011"
F_TWO = "aaaaaaaa-0000-0000-0000-000000000012"
F_LOOKUP = "aaaaaaaa-0000-0000-0000-000000000013"
F_ORPHAN = "aaaaaaaa-0000-0000-0000-000000000014"


def _fields() -> list[dict[str, Any]]:
    return [
        _field("Title", field_id=F_TITLE, from_base=True, sealed=True),
        _field("ID", field_id=F_ID, kind="Counter", from_base=True, can_delete=False),
        _field("_Hidden", field_id=F_HIDDEN, hidden=True, sealed=True),
        _field("ColumnOne", field_id=F_ONE, sealed=True),
        _field("ColumnTwo", field_id=F_TWO, kind="Number", sealed=False),
        _field("Related", field_id=F_LOOKUP, kind="Lookup", sealed=True, lookup_list=OTHER_LIST_ID),
        _field("Orphan", field_id=F_ORPHAN, kind="Lookup", sealed=True, lookup_list=GONE_LIST_ID),
    ]


def _config(
    *,
    items: list[dict[str, Any]] | None = None,
    allow_deletion: bool = False,
    ours: bool = True,
    fields: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    description = f"{MARKER_PREFIX} from demo for list Thing." if ours else "A hand-made list."
    return {
        "list": {
            "Id": LIST_ID, "Title": "APP_Thing", "Description": description,
            "AllowDeletion": allow_deletion,
        },
        "fields": fields if fields is not None else _fields(),
        "items": items if items is not None else [],
        "otherLists": {OTHER_LIST_ID: "APP_Other"},
    }


def _tag(line: str, marker: str) -> Any:
    return json.loads(line.removeprefix(marker))


Run = tuple[dict[str, Any], list[dict[str, Any]], list[str], list[Any]]


def _run_script(
    body: str,
    config: dict[str, Any],
    answers: list[str],
    flags: dict[str, Any] | None = None,
) -> Run:
    """Run one emitted script against the mock.

    Returns (summary, calls, prompts, tables)."""
    harness = _HARNESS.replace(
        "const CONFIG = {};", f"const CONFIG = {json.dumps(config)};", 1,
    ).replace(
        "const ANSWERS = [];", f"const ANSWERS = {json.dumps(answers)};", 1,
    ).replace(
        "const FLAGS = {};", f"const FLAGS = {json.dumps(flags or {})};", 1,
    )
    body = body.rstrip()
    assert body.endswith("})();")
    # Wrap the emitted IIFE rather than editing inside it, so what runs is
    # the artefact byte for byte.
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(calls));\n"
        "  console.log('__PROMPTS__' + JSON.stringify(prompts));\n"
        "  console.log('__TABLES__' + JSON.stringify(tables));\n"
        "});\n"
    )
    output = _run(script)
    lines = output.splitlines()
    markers = ("__RESULT__", "__CALLS__", "__PROMPTS__", "__TABLES__")
    found = {
        marker: next((ln for ln in lines if ln.startswith(marker)), None)
        for marker in markers
    }
    missing = [marker for marker, line in found.items() if line is None]
    assert not missing, f"the script never reached {missing}:\n{output[-3000:]}"
    summary, calls, prompts, tables = (_tag(found[m] or "", m) for m in markers)
    return summary, calls, prompts, tables


GENERATED_AT = "2026-09-02T00:00:00Z"


def _protection(
    config: dict[str, Any], answers: list[str], flags: dict[str, Any] | None = None,
) -> Run:
    js = generate_protection_js(site_url=SITE, list_title="APP_Thing", generated_at=GENERATED_AT)
    return _run_script(js, config, answers, flags)


def _columns(
    config: dict[str, Any], answers: list[str], flags: dict[str, Any] | None = None,
) -> Run:
    js = generate_columns_js(site_url=SITE, list_title="APP_Thing", generated_at=GENERATED_AT)
    return _run_script(js, config, answers, flags)


def _method(call: dict[str, Any]) -> str | None:
    return call["headers"].get("X-HTTP-Method") if call["method"] == "POST" else None


def _writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [c for c in calls if _method(c) in ("MERGE", "DELETE")]


def _merges_of(calls: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return [c for c in _writes(calls) if _method(c) == "MERGE" and key in (c["body"] or {})]


def _deletes(calls: list[dict[str, Any]]) -> list[str]:
    return [c["url"] for c in _writes(calls) if _method(c) == "DELETE"]


def _field_of(url: str) -> str:
    return url.split("fields(guid'")[1].split("'")[0]


def _readbacks_of(calls: list[dict[str, Any]], field_id: str, select: str) -> list[int]:
    return [
        i for i, c in enumerate(calls)
        if c["method"] == "GET" and field_id in c["url"] and select in c["url"]
    ]


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


# === protection.js =========================================================


def test_unlock_merges_allow_deletion_and_reads_it_back() -> None:
    summary, calls, _prompts, _tables = _protection(_config(allow_deletion=False), ["unlock", ""])
    merges = _merges_of(calls, "AllowDeletion")
    assert [m["body"]["AllowDeletion"] for m in merges] == [True]
    after = calls.index(merges[0])
    assert any("$select=AllowDeletion" in c["url"] for c in calls[after + 1:]), (
        "no readback after the MERGE"
    )
    assert summary["actions"] == [{"action": "unlock", "verified": True}]
    assert summary["errors"] == []


def test_lock_sets_the_deletion_block() -> None:
    summary, calls, _prompts, _tables = _protection(_config(allow_deletion=True), ["lock", ""])
    assert [m["body"]["AllowDeletion"] for m in _merges_of(calls, "AllowDeletion")] == [False]
    assert summary["actions"] == [{"action": "lock", "verified": True}]


def test_unseal_touches_only_the_sealed_custom_columns() -> None:
    summary, calls, _prompts, _tables = _protection(_config(), ["unseal", ""])
    merges = _merges_of(calls, "Sealed")
    # ColumnOne, Related and Orphan are sealed custom columns. Title is a
    # base-type field, _Hidden is hidden, ColumnTwo is already unsealed.
    assert sorted(_field_of(m["url"]) for m in merges) == sorted([F_ONE, F_LOOKUP, F_ORPHAN])
    assert all(m["body"]["Sealed"] is False for m in merges)
    assert summary["actions"] == [{"action": "unseal", "columns": 3, "verified": True}]


def test_seal_touches_only_the_unsealed_custom_columns() -> None:
    summary, calls, _prompts, _tables = _protection(_config(), ["seal", ""])
    assert [_field_of(m["url"]) for m in _merges_of(calls, "Sealed")] == [F_TWO]
    assert summary["actions"] == [{"action": "seal", "columns": 1, "verified": True}]


def test_a_word_it_does_not_know_changes_nothing() -> None:
    summary, calls, prompts, _tables = _protection(_config(), ["toggle", ""])
    assert _writes(calls) == []
    assert summary["actions"] == []
    assert len(prompts) == 2, "an unknown word re-prompts rather than exiting"


def test_a_seal_readback_that_disagrees_stops_the_run() -> None:
    summary, calls, prompts, _tables = _protection(
        _config(), ["unseal", "unlock"], {"discardFieldMerge": True},
    )
    assert summary["aborted"] == "readback-mismatch"
    assert _merges_of(calls, "AllowDeletion") == [], "the run must stop before the next action"
    assert len(prompts) == 1


def test_the_state_table_reports_the_custom_columns_and_the_marker() -> None:
    summary, _calls, _prompts, tables = _protection(_config(ours=False), [""])
    assert summary["list"]["provisioned_by_dbml_sharepoint"] is False
    assert summary["list"]["allow_deletion"] is False
    names = [row["internal_name"] for row in tables[0]]
    assert names == ["ColumnOne", "ColumnTwo", "Related", "Orphan"]


def test_a_missing_list_aborts_and_names_what_exists() -> None:
    js = generate_protection_js(
        site_url=SITE, list_title="APP_Missing", generated_at=GENERATED_AT,
    )
    summary, calls, _prompts, _tables = _run_script(js, _config(), [""])
    assert summary["aborted"] == "list-not-found"
    assert any("web/lists?$select=Title,Hidden" in c["url"] for c in calls)


# === columns.js ============================================================


def test_built_ins_and_hidden_fields_never_reach_the_menu() -> None:
    _summary, _calls, _prompts, tables = _columns(_config(), [""])
    assert [row["internal_name"] for row in tables[0]] == [
        "ColumnOne", "ColumnTwo", "Related", "Orphan",
    ]
    assert [row["number"] for row in tables[0]] == [1, 2, 3, 4]


def test_a_lookup_whose_target_list_is_gone_is_flagged() -> None:
    _summary, _calls, _prompts, tables = _columns(_config(), [""])
    by_name = {row["internal_name"]: row for row in tables[0]}
    assert by_name["Related"]["lookup_target"] == "APP_Other"
    assert by_name["Orphan"]["lookup_target"] == "MISSING"
    assert by_name["ColumnOne"]["lookup_target"] == ""


def test_an_empty_sealed_column_is_unsealed_and_read_back_before_the_delete() -> None:
    config = _config(items=[{"Id": 1, "ColumnOne": None}])
    summary, calls, _prompts, _tables = _columns(config, ["1", "ColumnOne", ""])
    unseal = _merges_of(calls, "Sealed")
    assert len(unseal) == 1 and unseal[0]["body"]["Sealed"] is False
    deletes = _deletes(calls)
    assert len(deletes) == 1 and F_ONE in deletes[0]
    i_unseal = calls.index(unseal[0])
    i_delete = next(
        i for i, c in enumerate(calls) if c["url"] == deletes[0] and _method(c) == "DELETE"
    )
    sealed_reads = _readbacks_of(calls, F_ONE, "$select=Id,Sealed")
    between = [i for i in sealed_reads if i_unseal < i < i_delete]
    assert between, "no sealed-state readback between the unseal and the delete"
    assert [i for i in _readbacks_of(calls, F_ONE, "$select=Id") if i > i_delete], (
        "no readback after the delete"
    )
    assert summary["deleted"] == ["ColumnOne"]
    assert summary["errors"] == []


def test_an_unsealed_column_is_not_merged_before_the_delete() -> None:
    _summary, calls, _prompts, _tables = _columns(_config(), ["2", "ColumnTwo", ""])
    assert _merges_of(calls, "Sealed") == []
    assert len(_deletes(calls)) == 1 and F_TWO in _deletes(calls)[0]


def test_typing_the_wrong_name_skips_the_column() -> None:
    summary, calls, _prompts, _tables = _columns(_config(), ["1", "ColumnTwo", ""])
    assert _writes(calls) == []
    assert summary["deleted"] == []
    assert summary["skipped"] == [{"column": "ColumnOne", "reason": "not-confirmed"}]


def test_a_column_holding_values_needs_the_phrase() -> None:
    items = [{"Id": 1, "ColumnOne": ""}, {"Id": 2, "ColumnOne": "kept"}]
    summary, calls, prompts, _tables = _columns(
        _config(items=items), ["1", "ColumnOne", "1", "DELETE NON-EMPTY", ""],
    )
    asked = [p for p in prompts if "DELETE NON-EMPTY" in p]
    assert len(asked) == 2 and "holds values" in asked[0]
    assert len(_deletes(calls)) == 1, "the internal name is not enough for a column with values"
    assert summary["skipped"] == [{"column": "ColumnOne", "reason": "not-confirmed"}]
    assert summary["deleted"] == ["ColumnOne"]


def test_a_column_whose_values_cannot_be_read_needs_the_phrase() -> None:
    summary, calls, prompts, _tables = _columns(
        _config(), ["2", "ColumnTwo", ""], {"itemsStatus": 400},
    )
    assert any("could not be read" in p and "DELETE NON-EMPTY" in p for p in prompts)
    assert _deletes(calls) == []
    assert summary["skipped"] == [{"column": "ColumnTwo", "reason": "not-confirmed"}]


def test_a_lookup_value_is_read_through_its_id_projection() -> None:
    items = [{"Id": 1, "RelatedId": 7}]
    _summary, calls, prompts, _tables = _columns(_config(items=items), ["3", ""])
    assert any("$select=Id,RelatedId" in c["url"] for c in calls)
    assert any("holds values" in p for p in prompts)


def test_a_delete_that_still_reads_back_stops_the_run() -> None:
    summary, calls, prompts, _tables = _columns(
        _config(), ["2", "ColumnTwo", "1", "ColumnOne"], {"discardDelete": True},
    )
    assert summary["aborted"] == "readback-mismatch"
    assert len(_deletes(calls)) == 1
    assert len(prompts) == 2, "the run must stop rather than offer the menu again"


def test_the_menu_is_re_enumerated_after_a_delete() -> None:
    summary, _calls, _prompts, tables = _columns(
        _config(), ["1", "ColumnOne", "1", "ColumnTwo", ""],
    )
    assert summary["deleted"] == ["ColumnOne", "ColumnTwo"]
    assert [row["internal_name"] for row in tables[1]] == ["ColumnTwo", "Related", "Orphan"]
    assert [row["internal_name"] for row in tables[2]] == ["Related", "Orphan"]


def test_a_number_off_the_menu_re_prompts() -> None:
    summary, calls, prompts, _tables = _columns(_config(), ["9", "x", ""])
    assert _writes(calls) == []
    assert summary["deleted"] == []
    assert len(prompts) == 3


def test_a_column_holding_values_prints_them_before_the_phrase() -> None:
    """The operator re-keys those values into the replacement column after the
    redeploy, so the script shows them rather than only saying they exist."""
    items = [
        {"Id": 1, "ColumnOne": ""}, {"Id": 2, "ColumnOne": "kept"}, {"Id": 3, "ColumnOne": "also"},
    ]
    _summary, _calls, prompts, tables = _columns(_config(items=items), ["1", ""])
    values = next(t for t in tables if t and "item" in t[0])
    assert values == [{"item": 2, "value": "kept"}, {"item": 3, "value": "also"}]
    assert any("holds values in 2 item(s)" in p for p in prompts)


def test_a_lookup_value_prints_its_id_projection() -> None:
    items = [{"Id": 4, "RelatedId": 7}]
    _summary, _calls, _prompts, tables = _columns(_config(items=items), ["3", ""])
    values = next(t for t in tables if t and "item" in t[0])
    assert values == [{"item": 4, "value": 7}]
