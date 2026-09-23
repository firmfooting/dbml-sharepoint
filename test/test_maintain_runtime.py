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

from dbml_sharepoint.analysis import list_description, sidecars
from dbml_sharepoint.analysis.provenance import MARKER_PREFIX
from dbml_sharepoint.generators.maintaingen import (
    generate_columns_js,
    generate_list_js,
    generate_protection_js,
)

SITE = "https://example.sharepoint.com/sites/test"
LIST_ID = "11111111-1111-1111-1111-111111111111"
#: The fixture list's URL slug and the path it is served at. Both differ from
#: its title on purpose; see the note in `_config`.
LIST_SLUG = "OldThing"
LIST_PATH = f"/sites/test/Lists/{LIST_SLUG}"

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
      // A console prompt has no timeout, so a live list can change while it
      // is open. `afterPrompt` is how a test makes that happen.
      if (FLAGS.afterPrompt) Object.assign(state.list, FLAGS.afterPrompt);
      return answers.length ? answers.shift() : '';
    };
    console.table = (rows) => { tables.push(rows); };

    const state = {
      list: { ...CONFIG.list, deleted: false },
      fields: CONFIG.fields.map((f) => ({ ...f, deleted: false })),
      items: CONFIG.items,
      otherLists: CONFIG.otherLists || {},
      // How much has already succeeded, so a flag can let the first N writes
      // take and refuse the rest. A run that fails on its FIRST write leaves
      // nothing behind, which is the one partial state that needs no report.
      recycledOk: 0,
      fieldMerges: 0,
      // Which AllowDeletion readback this is. The unlock's is the first and
      // the re-lock's the second, so a test can fail one of them.
      lockReads: 0,
      // Which read of the items collection this is, for the same job.
      itemReads: 0,
    };

    const reply = (status, payload) => ({
      ok: status < 400,
      status,
      headers: { get: () => null },
      json: async () => payload,
      text: async () => JSON.stringify(payload),
    });
    // A response whose BODY never arrives: the status is known and the stream
    // then fails. A 400 is the case that needs its body read, because the
    // status alone does not say whether it is the documented absent one.
    const bodyFails = (status) => ({
      ...reply(status, {}),
      text: async () => { throw new TypeError('Failed to fetch'); },
    });
    const notFound = (what) => reply(404, { error: { message: { value: `${what} not found` } } });
    // What a by-GUID read of a field that is no longer there answers. 404 is
    // the shape the mock assumed; live on 2026-09-03 a just-deleted field
    // answered 400 instead (#383), so the flag makes both reachable, plus a
    // 400 the absent-shape test does not recognise.
    const absentField = () => {
      if (FLAGS.absentField === 'absent400') {
        return reply(400, { error: {
          code: '-2147024809, System.ArgumentException',
          message: { value: 'Value does not fall within the expected range.' },
        } });
      }
      if (FLAGS.absentField === 'other400') {
        return reply(400, { error: {
          code: '-2130575252, Microsoft.SharePoint.SPException',
          message: { value: 'something this script has never seen' },
        } });
      }
      return notFound('field');
    };
    const fieldById = (id) => state.fields.find((f) => f.Id === id);
    // field-sealed-probe.js measured the seal on a Text column only (#381).
    const sealMeasured = (f) => f.TypeAsString === 'Text';
    // A stored CanBeDeleted wins over the derived one, so a MERGE that stores it shows.
    const fieldView = (f) => {
      const { deleted, lookupList, refusesDeleteUnsealed, ...rest } = f;
      if ('CanBeDeleted' in rest) return rest;
      return { ...rest, CanBeDeleted: !f.Sealed && !refusesDeleteUnsealed };
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
      if (/web\/lists\/getbytitle\(/.test(u)) {
        // The live site resolves a renamed list by PATH only. Answering a
        // by-title read here would let a regression pass, so this fake
        // refuses it the way a renamed list does.
        return notFound('list');
      }
      const byPath = /GetList\(@listUrl\)\?@listUrl='([^']+)'/.exec(u);
      if (byPath) {
        if (byPath[1] !== state.list.Path || state.list.deleted) return notFound('list');
        return reply(200, { d: {
          Id: state.list.Id, Title: state.list.Title, Description: state.list.Description,
          AllowDeletion: state.list.AllowDeletion,
          // A stale count is a real state: ItemCount is not updated in step
          // with the items collection.
          ItemCount: FLAGS.staleItemCount === undefined
            ? state.items.length : FLAGS.staleItemCount,
        } });
      }
      const listGuid = /web\/lists\(guid'([^']+)'\)/.exec(u);
      if (!listGuid) return reply(400, { error: { message: { value: `unmocked ${u}` } } });
      const guid = listGuid[1].toLowerCase();
      if (guid === state.list.Id && state.list.deleted) {
        // A readback that REJECTS. A connection can drop on the confirming
        // GET exactly as it can on the DELETE, and a request that never
        // answered settles nothing, which no status code stands in for.
        if (FLAGS.absentList === 'never-answers') throw new TypeError('Failed to fetch');
        if (FLAGS.absentList === 'body-never-arrives') return bodyFails(400);
        if (FLAGS.absentList === 'lingers') {
          return reply(200, { d: { Id: state.list.Id, Title: state.list.Title } });
        }
        if (FLAGS.absentList === 'unreadable') {
          return reply(500, { error: { message: { value: 'server error' } } });
        }
        if (FLAGS.absentList === 'absent400') {
          return reply(400, { error: {
            code: '-2147024809, System.ArgumentException',
            message: { value: 'Value does not fall within the expected range.' },
          } });
        }
        return notFound('list');
      }
      if (guid !== state.list.Id) {
        const title = state.otherLists[guid];
        return title ? reply(200, { d: { Id: guid, Title: title } }) : notFound('list');
      }
      const fieldGuid = /fields\(guid'([^']+)'\)/.exec(u);
      if (fieldGuid) {
        const f = fieldById(fieldGuid[1]);
        if (!f || f.deleted) return absentField();
        if (method === 'POST' && headers['X-HTTP-Method'] === 'MERGE') {
          state.fieldMerges += 1;
          const takes = state.fieldMerges <= (FLAGS.discardFieldMergeAfter || 0);
          if (!FLAGS.discardFieldMerge || takes) {
            // Read-only on a Text column: a write of it answers 204 and changes nothing (#381).
            const { CanBeDeleted, ...writable } = body || {};
            Object.assign(f, sealMeasured(f) ? writable : body || {}, { __metadata: undefined });
          }
          return reply(204, {});
        }
        if (method === 'POST' && headers['X-HTTP-Method'] === 'DELETE') {
          // A sealed Text column refuses the delete with this answer and survives (#381).
          if (f.Sealed === true && sealMeasured(f)) {
            return reply(400, { error: {
              code: '-1, System.InvalidOperationException',
              message: { value: 'Operation is not valid due to the current state of the object.' },
            } });
          }
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
        if (FLAGS.pageFields && !u.includes('field_page=2')) {
          return reply(200, { d: { results: [], __next: String(url) + '&field_page=2' } });
        }
        const live = state.fields.filter((f) => !f.deleted).map(fieldView);
        return reply(200, { d: { results: live, __next: FLAGS.fieldNext } });
      }
      if (u.includes('/items?')) {
        if (FLAGS.pageItems && !u.includes('item_page=2')) {
          return reply(200, { d: { results: [], __next: String(url) + '&item_page=2' } });
        }
        if (FLAGS.itemsStatus) {
          return reply(FLAGS.itemsStatus, { error: { message: { value: 'items refused' } } });
        }
        // A row another user adds while this runs. Counted by READ so a test
        // can place it after the drain has already come back empty, which is
        // the one window the drain cannot close.
        state.itemReads += 1;
        if (FLAGS.itemArrivesBeforeRead === state.itemReads) {
          state.items = state.items.concat([{ Id: 99 }]);
        }
        // $top is HONOURED: the final check asks for one row, and a mock
        // answering every row would let a script reading results[1] pass.
        const top = Number((/\$top=(\d+)/.exec(u) || [])[1]) || state.items.length;
        return reply(200, { d: { results: state.items.slice(0, top), __next: FLAGS.itemNext } });
      }
      const recycled = /\/items\((\d+)\)\/recycle\(\)/.exec(u);
      if (recycled && method === 'POST') {
        const takes = state.recycledOk < (FLAGS.recycleFailsAfter || 0);
        if (FLAGS.recycleStatus && !takes) {
          return reply(FLAGS.recycleStatus, { error: { message: { value: 'recycle refused' } } });
        }
        state.recycledOk += 1;
        state.items = state.items.filter((row) => String(row.Id) !== recycled[1]);
        return reply(200, {});
      }
      if (method === 'POST' && headers['X-HTTP-Method'] === 'DELETE') {
        if (FLAGS.listDeleteStatus) {
          return reply(FLAGS.listDeleteStatus, { error: { message: { value: 'delete refused' } } });
        }
        if (!FLAGS.discardListDelete) state.list.deleted = true;
        // A REJECTED fetch, which is what a dropped connection looks like to
        // the script. Thrown after the delete is applied, so `listDeleteThrows`
        // alone is a DELETE SharePoint took whose answer never arrived, and
        // with `discardListDelete` one it never got.
        if (FLAGS.listDeleteThrows) throw new TypeError('Failed to fetch');
        return reply(200, {});
      }
      if (method === 'POST' && headers['X-HTTP-Method'] === 'MERGE') {
        // `discardRelockMerge` discards only the write that puts a lock BACK,
        // so the unlock on the way in can take and the restore can be the
        // thing that silently fails.
        const relock = body && body.AllowDeletion === false;
        const discarded = FLAGS.discardListMerge || (FLAGS.discardRelockMerge && relock);
        if (!discarded && body && 'AllowDeletion' in body) {
          state.list.AllowDeletion = body.AllowDeletion;
        }
        return reply(204, {});
      }
      if (u.includes('$select=AllowDeletion')) {
        const d = { AllowDeletion: state.list.AllowDeletion, ItemCount: state.items.length };
        return reply(200, { d });
      }
      // A lock readback that FAILS, which is not a lock readback that reports
      // the write was discarded: the site keeps whatever the MERGE wrote.
      if (method === 'GET' && u.includes('$select=Id,AllowDeletion')) {
        state.lockReads += 1;
        if (FLAGS.lockReadbackFailsAt === state.lockReads) {
          return reply(500, { error: { message: { value: 'readback failed' } } });
        }
      }
      return reply(200, { d: {
        Id: state.list.Id, Title: state.list.Title,
        Description: state.list.Description,
        AllowDeletion: state.list.AllowDeletion, ItemCount: state.items.length,
      } });
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
    can_delete: bool | None = None,
    lookup_list: str | None = None,
) -> dict[str, Any]:
    """One field's shape, with `CanBeDeleted` derived rather than assumed.

    Sealing a column is what makes SharePoint report `CanBeDeleted: false`,
    and unsealing it restores true. First observed 2026-09-03 on a live list
    (11 sealed columns false, 3 unsealed true), then MEASURED by
    `field-sealed-probe.js` on 2026-09-19 and 2026-09-20 (#381), both runs
    identical, on a Text column only. A fixture pairing `Sealed: true` with
    `CanBeDeleted: true` describes a list no tenant can produce, and that
    pairing is what let the sidecars ship unable to see a sealed column.

    Only the Text measurement is enforced. A Text column stores no
    `CanBeDeleted`: the mock derives it from the CURRENT seal on every read,
    so an unseal is visible the way it is live. Other types store the value
    below, from the 2026-09-03 observation, and are not held to the rest.
    `can_delete=False` on an unsealed column is the one case the seal cannot
    express: a column SharePoint refuses to delete for its own reasons.
    """
    if can_delete is None:
        can_delete = not sealed
    measured = kind == "Text"
    if measured:
        assert not (sealed and can_delete), "no tenant reports a sealed Text column as deletable"
    stored = {} if measured else {"CanBeDeleted": can_delete}
    return {
        "Id": field_id,
        "InternalName": internal,
        "Title": internal.replace("_", " "),
        "TypeAsString": kind,
        "Hidden": hidden,
        "ReadOnlyField": False,
        "Sealed": sealed,
        "FromBaseType": from_base,
        **stored,
        "refusesDeleteUnsealed": measured and not sealed and not can_delete,
        "lookupList": lookup_list,
    }


F_TITLE = "aaaaaaaa-0000-0000-0000-000000000001"
F_ID = "aaaaaaaa-0000-0000-0000-000000000002"
F_HIDDEN = "aaaaaaaa-0000-0000-0000-000000000003"
F_ONE = "aaaaaaaa-0000-0000-0000-000000000011"
F_TWO = "aaaaaaaa-0000-0000-0000-000000000012"
F_LOOKUP = "aaaaaaaa-0000-0000-0000-000000000013"
F_ORPHAN = "aaaaaaaa-0000-0000-0000-000000000014"
F_UNDELETABLE = "aaaaaaaa-0000-0000-0000-000000000015"


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
    description: str | None = None,
) -> dict[str, Any]:
    if description is None:
        description = (
            f"{MARKER_PREFIX} from demo for list Thing." if ours else "A hand-made list."
        )
    return {
        "list": {
            # RENAMED, deliberately: the fixture list is TITLED APP_Thing and
            # SERVED at /Lists/OldThing, which is what a list that has been
            # through a `renamed_from` migration looks like. Every runtime
            # test therefore exercises the case #385 was filed for, and a
            # script that resolves by the slug fails all of them.
            "Id": LIST_ID, "Title": "APP_Thing", "Path": LIST_PATH,
            "Description": description, "AllowDeletion": allow_deletion,
        },
        "fields": fields if fields is not None else _fields(),
        "items": items if items is not None else [],
        "otherLists": {OTHER_LIST_ID: "APP_Other"},
    }


def _tag(line: str, marker: str) -> Any:
    return json.loads(line.removeprefix(marker))


Run = tuple[dict[str, Any], list[dict[str, Any]], list[str], list[Any]]


def _wrap(
    body: str,
    config: dict[str, Any],
    answers: list[str],
    flags: dict[str, Any] | None = None,
) -> str:
    """The emitted script, plus the mock, as one runnable file.

    Separate from `_run_script` so a test can read the script's own log lines
    rather than only the four JSON markers. Both go through here, so what runs
    is the same file either way.
    """
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
    return (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(calls));\n"
        "  console.log('__PROMPTS__' + JSON.stringify(prompts));\n"
        "  console.log('__TABLES__' + JSON.stringify(tables));\n"
        "});\n"
    )


def _run_script(
    body: str,
    config: dict[str, Any],
    answers: list[str],
    flags: dict[str, Any] | None = None,
) -> Run:
    """Run one emitted script against the mock.

    Returns (summary, calls, prompts, tables)."""
    return _parse(_run(_wrap(body, config, answers, flags)))


def _parse(output: str) -> Run:
    """The four JSON markers out of one run's output.

    Separate from `_run_script` so a test that reads the script's log lines
    can read the summary out of the SAME run rather than executing it twice.
    """
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
    js = generate_protection_js(
        site_url=SITE, list_title=LIST_SLUG, list_path=LIST_PATH,
        generated_at=GENERATED_AT,
    )
    return _run_script(js, config, answers, flags)


def _columns(
    config: dict[str, Any], answers: list[str], flags: dict[str, Any] | None = None,
) -> Run:
    js = generate_columns_js(
        site_url=SITE, list_title=LIST_SLUG, list_path=LIST_PATH,
        generated_at=GENERATED_AT,
    )
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


def test_a_seal_that_fails_part_way_reports_the_columns_it_did_seal() -> None:
    """The same argument the list script's recycle count makes: columns
    already written and read back are state the operator has to know about,
    and a run reporting no actions at all hides them behind the error."""
    summary, calls, _prompts, _tables = _protection(
        _config(), ["unseal", "unlock"],
        {"discardFieldMerge": True, "discardFieldMergeAfter": 1},
    )

    assert summary["aborted"] == "readback-mismatch"
    assert summary["actions"] == [{"action": "unseal", "columns": 1, "verified": True}]
    assert _merges_of(calls, "AllowDeletion") == [], "the run must stop before the next action"


def test_the_state_table_reports_the_custom_columns_and_the_marker() -> None:
    summary, _calls, _prompts, tables = _protection(_config(ours=False), [""])
    assert summary["list"]["provisioned_by_dbml_sharepoint"] is False
    assert summary["list"]["allow_deletion"] is False
    names = [row["internal_name"] for row in tables[0]]
    # Title leads, and is the one row that is not a custom column. See
    # test_the_state_table_names_the_built_in_title below for why it is here.
    assert names == ["Title", "ColumnOne", "ColumnTwo", "Related", "Orphan"]


def test_the_state_table_names_the_built_in_title() -> None:
    """The column an operator most wants to check, and the one the readout
    could not show.

    `isCustom` excludes anything with `FromBaseType`, and the built-in Title
    reads `FromBaseType: true` on every list (measured 2026-09-07,
    test/manual/title-seal-probe.js, on two sites). So the one column whose
    display name a site owner can change without touching anything the tool
    manages was the one column this script never printed.

    It is reported and never offered: `isCustom` still decides what the seal
    and unseal loops touch, and the same run established that a generic
    list's Title refuses `Sealed: true` by every route, so offering it would
    only produce an error an operator cannot act on.
    """
    summary, _calls, _prompts, tables = _protection(_config(), [""])
    row = next(r for r in tables[0] if r["internal_name"] == "Title")
    assert row["built_in"] is True
    assert row["title"] == "Title"
    assert all(r.get("built_in") is False
               for r in tables[0] if r["internal_name"] != "Title")
    # The count keeps meaning what it meant, so a readout gaining a row does
    # not silently restate how many columns the operator owns.
    assert summary["list"]["custom_columns"] == 4
    assert summary["list"]["built_in_title"] == {"title": "Title", "sealed": True}


def test_the_built_in_title_is_reported_but_never_offered_for_sealing() -> None:
    """The seal and unseal loops keep reading `isCustom`.

    A generic list refuses Sealed:true on its built-in Title with HTTP 400
    (measured, as above), so a loop that included it would fail on a write
    nothing can make succeed, on every run, on every list.
    """
    _summary, calls, _prompts, _tables = _protection(_config(), ["seal", ""])
    title_writes = [
        c for c in calls
        if c["method"] == "POST" and c.get("body") and F_TITLE in c["url"]
    ]
    assert title_writes == [], f"the seal loop reached the built-in Title: {title_writes}"


def test_a_missing_list_aborts_and_names_what_exists() -> None:
    js = generate_protection_js(
        site_url=SITE, list_title="APP_Missing",
        list_path="/sites/test/Lists/APP_Missing", generated_at=GENERATED_AT,
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
    assert all("number" not in row for row in tables[0]), (
        "a position column beside console.table's own 0-based index is two "
        "differently-based ways to name a row on a destructive menu"
    )


def test_a_sealed_column_reaches_the_menu_even_though_it_cannot_be_deleted_yet() -> None:
    """The regression this file could not see while its fixture was impossible.

    Sealing is what sets `CanBeDeleted: false`, so a filter reading that
    property alone removed every column this script exists to delete. The
    column is offered; the delete path unseals it first.
    """
    rows = _columns(_config(), [""])[3][0]
    sealed = {row["internal_name"] for row in rows if row["sealed"]}
    assert sealed == {"ColumnOne", "Related", "Orphan"}, (
        "a sealed column was filtered off the menu, so it can never be deleted"
    )


def test_a_column_sharepoint_refuses_to_delete_while_unsealed_stays_off_the_menu() -> None:
    """The other half: only a SEAL earns the exemption.

    An unsealed column reporting `CanBeDeleted: false` is refusing for
    SharePoint's own reasons, and unsealing it would not help.
    """
    fields = [
        *_fields(),
        _field("Undeletable", field_id=F_UNDELETABLE, sealed=False, can_delete=False),
    ]
    rows = _columns(_config(fields=fields), [""])[3][0]
    assert "Undeletable" not in {row["internal_name"] for row in rows}


def test_a_lookup_whose_target_list_is_gone_is_flagged() -> None:
    _summary, _calls, _prompts, tables = _columns(_config(), [""])
    by_name = {row["internal_name"]: row for row in tables[0]}
    assert by_name["Related"]["lookup_target"] == "APP_Other"
    assert by_name["Orphan"]["lookup_target"] == "MISSING"
    assert by_name["ColumnOne"]["lookup_target"] == ""


def test_an_empty_sealed_column_is_unsealed_and_read_back_before_the_delete() -> None:
    config = _config(items=[{"Id": 1, "ColumnOne": None}])
    summary, calls, _prompts, _tables = _columns(config, ["ColumnOne", "ColumnOne", ""])
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


_SEAL_WALK = textwrap.dedent("""
    (async () => {
      const f = `https://example.sharepoint.com/sites/test/_api/web/lists(guid'__LIST__')/fields(guid'__FIELD__')`;
      const read = async () => {
        const d = (await (await fetch(f)).json()).d;
        return `Sealed=${d.Sealed} CanBeDeleted=${d.CanBeDeleted}`;
      };
      const write = async (verb, body) => (await fetch(f, {
        method: 'POST', headers: { 'X-HTTP-Method': verb },
        body: body ? JSON.stringify(body) : undefined,
      })).status;
      const merge = async (body) => [await write('MERGE', body), await read()];
      const out = {};
      out.start = await read();
      out.seal = await merge({ Sealed: true });
      out.unseal = await merge({ Sealed: false });
      out.writeWhileUnsealed = await merge({ CanBeDeleted: false });
      out.reseal = await merge({ Sealed: true });
      out.writeWhileSealed = await merge({ CanBeDeleted: true });
      out.bothAtOnce = await merge({ Sealed: false, CanBeDeleted: false });
      out.sealForDelete = await merge({ Sealed: true });
      out.deleteWhileSealed = [await write('DELETE'), (await fetch(f)).status];
      out.unsealForDelete = await merge({ Sealed: false });
      out.deleteWhileUnsealed = [await write('DELETE'), (await fetch(f)).status];
      return out;
    })();
""")

F_SUBJECT = "aaaaaaaa-0000-0000-0000-000000000016"


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_mock_seals_a_column_the_way_the_probe_measured() -> None:
    """Every script test in this file is only as strict as this mock.

    `field-sealed-probe.js`'s own sequence, on an unsealed Text column, with
    the readbacks its two runs recorded (2026-09-19 and 2026-09-20, #381,
    identical). A mock looser than that passes a script that skips the
    unseal, which is the class #574 describes.
    """
    fields = [*_fields(), _field("Subject", field_id=F_SUBJECT)]
    body = _SEAL_WALK.replace("__LIST__", LIST_ID).replace("__FIELD__", F_SUBJECT)
    walk = _run_script(body, _config(fields=fields), [])[0]
    sealed, unsealed = "Sealed=true CanBeDeleted=false", "Sealed=false CanBeDeleted=true"
    assert walk == {
        "start": unsealed,
        "seal": [204, sealed],
        "unseal": [204, unsealed],
        "writeWhileUnsealed": [204, unsealed],
        "reseal": [204, sealed],
        "writeWhileSealed": [204, sealed],
        # The writable half of the pair lands; the read-only half is dropped.
        "bothAtOnce": [204, unsealed],
        "sealForDelete": [204, sealed],
        "deleteWhileSealed": [400, 200],
        "unsealForDelete": [204, unsealed],
        "deleteWhileUnsealed": [200, 404],
    }


def test_the_seal_contract_is_held_to_the_type_it_was_measured_on() -> None:
    """`field-sealed-probe.js` sealed a Text column and nothing else (#381).

    Holding a Lookup to the same contract would certify scripts against
    behaviour no run has observed, so only Text is refused the impossible
    pairing and only Text has its `CanBeDeleted` derived.
    """
    with pytest.raises(AssertionError, match="sealed Text column"):
        _field("Measured", field_id=F_ONE, sealed=True, can_delete=True)
    text = _field("Measured", field_id=F_ONE, sealed=True)
    assert "CanBeDeleted" not in text
    lookup = _field("Unmeasured", field_id=F_LOOKUP, kind="Lookup", sealed=True)
    assert lookup["CanBeDeleted"] is False
    assert _field(
        "Unmeasured", field_id=F_LOOKUP, kind="Lookup", sealed=True, can_delete=True,
    )["CanBeDeleted"] is True


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_an_unseal_that_does_not_take_stops_before_the_delete() -> None:
    """Live, a DELETE on a column still sealed is refused with a 400 naming no
    property, so the readback between the unseal and the delete is the only
    place the operator can be told why."""
    config = _config(items=[{"Id": 1, "ColumnOne": None}])
    summary, calls, _prompts, _tables = _columns(
        config, ["ColumnOne", "ColumnOne", ""], {"discardFieldMerge": True},
    )
    assert _deletes(calls) == []
    assert summary["deleted"] == []
    assert summary["aborted"] == "readback-mismatch"
    assert "Sealed=true after writing false" in summary["errors"][0]["error"]


def test_a_delete_readback_that_answers_400_is_recorded_as_deleted() -> None:
    """The success signal read as a failure.

    Seen live 2026-09-03: the by-GUID read of a just-deleted field answered
    HTTP 400, the strict `!== 404` check raised a readback mismatch, and the
    run aborted after deleting the column it said it had not. An operator
    removing five superseded columns ran the script five times and read five
    false errors, indistinguishable from the genuine failed delete the
    readback exists to catch.
    """
    config = _config(items=[{"Id": 1, "ColumnOne": None}])
    summary, _calls, _prompts, _tables = _columns(
        config, ["ColumnOne", "ColumnOne", ""], {"absentField": "absent400"},
    )
    assert summary["deleted"] == ["ColumnOne"]
    assert summary["errors"] == []
    assert "aborted" not in summary


def test_a_delete_readback_answering_an_unknown_400_is_settled_by_enumeration(
) -> None:
    """A 400 whose shape means nothing here is not taken either way.

    `isAbsent400` matches one shape, and its comment scopes that to the
    BY-NAME getters. This readback is by GUID, and the live error body was
    never captured, so an unrecognised 400 falls through to a read of the
    fields collection: absence measured rather than an error body read as a
    claim. The delete succeeded here, so the column is gone and the run says
    which signal it trusted.
    """
    config = _config(items=[{"Id": 1, "ColumnOne": None}])
    js = generate_columns_js(
        site_url=SITE, list_title=LIST_SLUG, list_path=LIST_PATH,
        generated_at=GENERATED_AT,
    )
    out = _run(_wrap(js, config, ["ColumnOne", "ColumnOne", ""], {"absentField": "other400"}))
    assert "__RESULT__" in out
    summary = _tag(
        next(ln for ln in out.splitlines() if ln.startswith("__RESULT__")), "__RESULT__",
    )
    assert summary["deleted"] == ["ColumnOne"]
    assert summary["errors"] == []
    assert "absent from the fields collection" in out


def test_a_delete_that_did_not_take_still_aborts_the_run() -> None:
    """The case the readback exists for, unchanged.

    The DELETE answers 200 and the field is still there, so every signal
    agrees it is present: the by-GUID read succeeds and the enumeration still
    names it. Accepting more absent-shapes must not cost this.
    """
    config = _config(items=[{"Id": 1, "ColumnOne": None}])
    summary, _calls, _prompts, _tables = _columns(
        config, ["ColumnOne", "ColumnOne", ""], {"discardDelete": True},
    )
    assert summary["aborted"] == "readback-mismatch"
    assert summary["deleted"] == []
    assert "still reads back after the delete" in summary["errors"][0]["error"]


def test_an_unsealed_column_is_not_merged_before_the_delete() -> None:
    _summary, calls, _prompts, _tables = _columns(_config(), ["ColumnTwo", "ColumnTwo", ""])
    assert _merges_of(calls, "Sealed") == []
    assert len(_deletes(calls)) == 1 and F_TWO in _deletes(calls)[0]


def test_typing_the_wrong_name_skips_the_column() -> None:
    summary, calls, _prompts, _tables = _columns(_config(), ["ColumnOne", "ColumnTwo", ""])
    assert _writes(calls) == []
    assert summary["deleted"] == []
    assert summary["skipped"] == [{"column": "ColumnOne", "reason": "not-confirmed"}]


def test_a_column_holding_values_needs_the_phrase() -> None:
    items = [{"Id": 1, "ColumnOne": ""}, {"Id": 2, "ColumnOne": "kept"}]
    summary, calls, prompts, _tables = _columns(
        _config(items=items),
        ["ColumnOne", "ColumnOne", "ColumnOne", "DELETE NON-EMPTY", ""],
    )
    asked = [p for p in prompts if "DELETE NON-EMPTY" in p]
    assert len(asked) == 2 and "holds values" in asked[0]
    assert len(_deletes(calls)) == 1, "the internal name is not enough for a column with values"
    assert summary["skipped"] == [{"column": "ColumnOne", "reason": "not-confirmed"}]
    assert summary["deleted"] == ["ColumnOne"]


def test_a_column_whose_values_cannot_be_read_needs_the_phrase() -> None:
    summary, calls, prompts, _tables = _columns(
        _config(), ["ColumnTwo", "ColumnTwo", ""], {"itemsStatus": 400},
    )
    assert any("could not be read" in p and "DELETE NON-EMPTY" in p for p in prompts)
    assert _deletes(calls) == []
    assert summary["skipped"] == [{"column": "ColumnTwo", "reason": "not-confirmed"}]


def test_a_lookup_value_is_read_through_its_id_projection() -> None:
    items = [{"Id": 1, "RelatedId": 7}]
    _summary, calls, prompts, _tables = _columns(_config(items=items), ["Related", ""])
    assert any("$select=Id,RelatedId" in c["url"] for c in calls)
    assert any("holds values" in p for p in prompts)


def test_a_delete_that_still_reads_back_stops_the_run() -> None:
    summary, calls, prompts, _tables = _columns(
        _config(), ["ColumnTwo", "ColumnTwo", "ColumnOne", "ColumnOne"], {"discardDelete": True},
    )
    assert summary["aborted"] == "readback-mismatch"
    assert len(_deletes(calls)) == 1
    assert len(prompts) == 2, "the run must stop rather than offer the menu again"


def test_the_menu_is_re_enumerated_after_a_delete() -> None:
    summary, _calls, _prompts, tables = _columns(
        _config(), ["ColumnOne", "ColumnOne", "ColumnTwo", "ColumnTwo", ""],
    )
    assert summary["deleted"] == ["ColumnOne", "ColumnTwo"]
    assert [row["internal_name"] for row in tables[1]] == ["ColumnTwo", "Related", "Orphan"]
    assert [row["internal_name"] for row in tables[2]] == ["Related", "Orphan"]


def test_a_menu_position_no_longer_selects_a_column() -> None:
    """The regression this selection change exists to prevent.

    console.table prints its own 0-based (index), so a 1-based menu number sat
    one column away from a number naming a different row. Typing a position now
    selects nothing rather than the neighbour of what was meant.
    """
    # Before this change "1" selected ColumnOne and the name that follows
    # confirmed it, so this exact sequence deleted a column.
    summary, calls, _prompts, _tables = _columns(_config(), ["1", "ColumnOne", ""])
    assert _deletes(calls) == [], "a menu position selected a column on a delete menu"
    assert summary["deleted"] == []


def test_a_name_differing_only_by_case_is_refused_and_the_exact_one_named() -> None:
    """SharePoint resolves a field case-insensitively; this menu must not.

    Two columns can differ by case alone, so accepting a near miss would let
    one name delete the other.
    """
    summary, calls, prompts, _tables = _columns(_config(), ["columnone", ""])
    assert _deletes(calls) == []
    assert summary["deleted"] == []
    # Re-prompted rather than resolved: two answers consumed, not one.
    assert len(prompts) == 2


def test_a_name_off_the_menu_re_prompts() -> None:
    summary, calls, prompts, _tables = _columns(_config(), ["NoSuchColumn", "x", ""])
    assert _writes(calls) == []
    assert summary["deleted"] == []
    assert len(prompts) == 3


def test_a_column_holding_values_prints_them_before_the_phrase() -> None:
    """The operator re-keys those values into the replacement column after the
    redeploy, so the script shows them rather than only saying they exist."""
    items = [
        {"Id": 1, "ColumnOne": ""}, {"Id": 2, "ColumnOne": "kept"}, {"Id": 3, "ColumnOne": "also"},
    ]
    _summary, _calls, prompts, tables = _columns(_config(items=items), ["ColumnOne", ""])
    values = next(t for t in tables if t and "item" in t[0])
    assert values == [{"item": 2, "value": "kept"}, {"item": 3, "value": "also"}]
    assert any("holds values in 2 item(s)" in p for p in prompts)


def test_a_lookup_value_prints_its_id_projection() -> None:
    items = [{"Id": 4, "RelatedId": 7}]
    _summary, _calls, _prompts, tables = _columns(_config(items=items), ["Related", ""])
    values = next(t for t in tables if t and "item" in t[0])
    assert values == [{"item": 4, "value": 7}]


# --- Resolution by URL rather than by title (#385) --------------------------


def test_a_renamed_list_resolves_and_reports_the_title_it_has_now() -> None:
    """The defect this closes, from the operator's side.

    The fixture list is served at `/Lists/OldThing` and titled `APP_Thing`,
    which is what a list looks like after a `renamed_from` migration. A script
    resolving by the slug asks for a list called `OldThing` and gets 404 on
    every request; the mock refuses by-title reads outright so that regression
    cannot pass here.

    Asserted on the resolved TITLE, not merely on a clean run: the point is
    that the script reports what the list is called now rather than echoing
    back the folder name it was given.
    """
    summary, calls, _prompts, _tables = _columns(_config(), [""])
    assert summary.get("aborted") is None, summary
    assert summary["list"]["title"] == "APP_Thing"
    resolved = [c for c in calls if "GetList(@listUrl)" in c["url"]]
    assert len(resolved) == 1, "the list is resolved once, then addressed by id"
    assert LIST_PATH in resolved[0]["url"]


def test_the_run_says_the_slug_and_the_title_differ() -> None:
    """A destructive script must name the list it is actually pointed at.

    An operator pastes a URL reading `OldThing` and is about to be asked to
    confirm deletions on it. Saying which list that is, once, is what stops
    the confirmation being taken on trust.
    """
    js = generate_columns_js(
        site_url=SITE, list_title=LIST_SLUG, list_path=LIST_PATH,
        generated_at=GENERATED_AT,
    )
    out = _run(_wrap(js, _config(), [""]))
    assert f"'{LIST_PATH}' is the list titled 'APP_Thing'" in out


def test_a_path_naming_no_list_names_the_path_not_a_title() -> None:
    """The message an operator gets when the URL is wrong.

    Before this change it read "No list titled 'OldThing'", which sent people
    looking for a list by that name. The path is the thing that was wrong.
    """
    js = generate_columns_js(
        site_url=SITE, list_title="Nope", list_path="/sites/test/Lists/Nope",
        generated_at=GENERATED_AT,
    )
    out = _run(_wrap(js, _config(), []))
    assert "__RESULT__" in out
    # The PATH, and only the path. Asserted on the message rather than on the
    # abort code, because a by-title script aborts with the same code and this
    # test would pass against the defect it exists to pin.
    assert "No list at '/sites/test/Lists/Nope'" in out
    assert "No list titled" not in out
# --------------------------------------------------------------------------
# list.js: deleting the whole list. Rollback deletes the lists a bundle
# DECLARES; this is for the one it no longer does, so the marker test is the
# weaker "provisioned by this tool at all" and every other guard is stricter.
# --------------------------------------------------------------------------
def _list_js() -> str:
    return generate_list_js(
        site_url=SITE, list_title=LIST_SLUG, list_path=LIST_PATH,
        generated_at=GENERATED_AT,
    )


def _list(
    config: dict[str, Any], answers: list[str], flags: dict[str, Any] | None = None,
) -> Run:
    return _run_script(_list_js(), config, answers, flags)


def _list_output(
    config: dict[str, Any], answers: list[str], flags: dict[str, Any] | None = None,
) -> str:
    """One run's whole output, for the tests that read its log lines.

    `_parse` reads the summary out of the same output, so a test asserting on
    both does not run the script twice.
    """
    return _run(_wrap(_list_js(), config, answers, flags))


#: What the script asks for first. The fixture list is TITLED APP_Thing and
#: SERVED at /Lists/OldThing, so typing the slug back must not work.
TITLE = "APP_Thing"

#: Two items, because draining has to be observed rather than assumed: a
#: single one passes even if the loop only ever recycles the first.
_TWO_ITEMS = [{"Id": 1}, {"Id": 2}]


def _recycles(calls: list[dict[str, Any]]) -> list[str]:
    return [c["url"] for c in calls if "/recycle()" in c["url"]]


def test_a_list_this_tool_did_not_provision_is_refused() -> None:
    """The one gate the other two sidecars only report.

    protection.js and columns.js change one flag or one column on a list the
    operator named, and say whether it carries a marker. This removes the
    list, and a hand-made list at a pasted URL is the mistake that cannot be
    walked back, so here the same fact is a refusal.
    """
    summary, calls, prompts, _ = _list(_config(ours=False), [TITLE])

    assert summary["aborted"] == "not-provisioned"
    assert prompts == [], "it asked before it refused"
    assert _deletes(calls) == [] and _recycles(calls) == []


def test_a_description_that_only_mentions_this_tool_is_not_a_marker() -> None:
    """The gate is the whole grammar, not the words a marker opens with.

    A prefix search passes on any Description that happens to name the tool.
    `test_identify_runtime.py` already exercises this decoy on the inventory,
    where it costs a wrong row; here it stands between an operator and a
    permanent delete.
    """
    summary, calls, prompts, _ = _list(
        _config(description=(
            f"Hand-made. Looks like something {MARKER_PREFIX} would leave behind."
        )),
        [TITLE],
    )

    assert summary["aborted"] == "not-provisioned"
    assert prompts == [], "it asked before it refused"
    assert _deletes(calls) == [] and _recycles(calls) == []


@pytest.mark.parametrize(
    "description",
    [
        list_description.marker_for("demo", "Thing"),
        list_description.list_description(
            "A note the author wrote.", family="demo", entity="Thing",
        ),
        sidecars.run_log_marker(),
        sidecars.change_log_marker(),
        list_description.verify_marker(),
    ],
    ids=["family-list", "note-then-marker", "run-log", "change-log", "verify-scratch"],
)
def test_every_marker_this_tool_writes_on_a_list_is_accepted(description: str) -> None:
    """The refusal must never be stronger than what the deploy writes.

    A family's list carries `for list <entity>`; the verify scratch list and
    the two log sidecars carry `for scratch <title>` and no family at all,
    and a retired sidecar is the case this script was written for. The
    markers come from the modules that write them, so a grammar change
    reaches this test rather than going unnoticed.
    """
    summary, calls, _, _ = _list(
        _config(description=description), [TITLE, "DELETE NON-EMPTY"],
    )

    assert summary["deleted"] == {"list": TITLE, "id": LIST_ID}
    assert len(_deletes(calls)) == 1


def test_the_title_has_to_be_typed_back_and_the_slug_will_not_do() -> None:
    """The URL slug is what the operator has in front of them and is NOT the
    title on any list that has been renamed in place. Accepting it would make
    the confirmation a formality on exactly the lists this script is for."""
    summary, calls, prompts, _ = _list(_config(), [LIST_SLUG])

    assert summary["skipped"] == {"list": TITLE, "reason": "title-not-typed"}
    assert summary["deleted"] is None
    assert _deletes(calls) == [] and _recycles(calls) == []
    assert f"({TITLE})" in prompts[0]


def test_a_list_holding_items_needs_delete_non_empty_as_well() -> None:
    """Typing the title is consent to delete the list. It is not consent to
    take two items with it, which is the second thing columns.js asks about
    for the same reason."""
    summary, calls, prompts = _list(_config(items=_TWO_ITEMS), [TITLE, "yes"])[:3]

    assert summary["skipped"] == {"list": TITLE, "reason": "items-unconfirmed"}
    assert _deletes(calls) == [] and _recycles(calls) == []
    assert "DELETE NON-EMPTY" in prompts[1]
    assert "2 item(s)" in prompts[1]


def test_a_list_reporting_no_items_is_asked_the_same_second_question() -> None:
    """ItemCount is not an atomic gate, so the phrase has to authorise the
    items rather than a snapshot of them: a stale zero would otherwise drain
    a list on consent nobody gave. Rollback asks unconditionally too."""
    summary, calls, prompts, _ = _list(_config(), [TITLE, "yes"])

    assert summary["skipped"] == {"list": TITLE, "reason": "items-unconfirmed"}
    assert summary["deleted"] is None
    assert len(prompts) == 2
    assert "0 item(s)" in prompts[1]
    assert _deletes(calls) == []


def test_items_a_stale_count_missed_are_still_drained_before_the_delete() -> None:
    """The other half of that: the phrase authorised whatever is there when
    draining starts, so the run recycles the items and not the count."""
    summary, calls, _, _ = _list(
        _config(items=_TWO_ITEMS), [TITLE, "DELETE NON-EMPTY"],
        flags={"staleItemCount": 0},
    )

    assert summary["recycled_items"] == 2
    assert len(_recycles(calls)) == 2
    assert summary["deleted"] == {"list": TITLE, "id": LIST_ID}


def test_a_locked_list_holding_items_is_drained_unlocked_and_deleted() -> None:
    """The whole sequence, in order: recycle every item, unlock and read the
    unlock back, DELETE, then read the absence back by id."""
    summary, calls, _, tables = _list(
        _config(items=_TWO_ITEMS, allow_deletion=False),
        [TITLE, "DELETE NON-EMPTY"],
    )

    assert summary["deleted"] == {"list": TITLE, "id": LIST_ID}
    assert summary["recycled_items"] == 2
    assert summary["errors"] == []
    assert len(_recycles(calls)) == 2
    assert len(_deletes(calls)) == 1
    # The two recycles, then the unlock MERGE, then the DELETE. Recycling
    # never needs AllowDeletion, so unlocking first would leave the list
    # deletable by anybody else for as long as the drain takes, and rollback
    # unlocks immediately before its own DELETE for that reason. An order this
    # test does not pin is one a refactor can invert, in either direction:
    # recycling after the delete would recycle nothing and still report two.
    unlock_at = [
        i for i, c in enumerate(calls)
        if c["body"] and c["body"].get("AllowDeletion") is True
    ]
    recycle_at = [i for i, c in enumerate(calls) if "/recycle()" in c["url"]]
    delete_at = [i for i, c in enumerate(calls) if _method(c) == "DELETE"]
    assert recycle_at[-1] < unlock_at[0] < delete_at[0]
    # The columns are printed before the prompt, because they are what says
    # whether this is the list the operator meant.
    assert tables and any(r["internal_name"] == "ColumnOne" for r in tables[0])


def test_a_list_renamed_while_the_prompt_was_open_is_not_deleted() -> None:
    """A console prompt has no timeout, so the read that authorised the
    delete is as old as the operator took to answer. Rollback re-reads for
    the same reason."""
    summary, calls, _, _ = _list(
        _config(), [TITLE, "DELETE NON-EMPTY"],
        flags={"afterPrompt": {"Title": "Something Else"}},
    )

    assert summary["skipped"] == {"list": TITLE, "reason": "changed-during-confirmation"}
    assert summary["deleted"] is None
    assert _deletes(calls) == [] and _recycles(calls) == []


def test_a_marker_removed_while_the_prompt_was_open_is_not_deleted() -> None:
    """The other half of the re-read. A list that stopped being ours between
    the refusal gate and the delete is not ours to delete."""
    summary, calls, _, _ = _list(
        _config(), [TITLE, "DELETE NON-EMPTY"],
        flags={"afterPrompt": {"Description": "A hand-made list."}},
    )

    assert summary["skipped"] == {"list": TITLE, "reason": "changed-during-confirmation"}
    assert _deletes(calls) == [] and _recycles(calls) == []


def test_a_marker_replaced_by_prose_about_the_tool_is_not_deleted() -> None:
    """The re-read tests the same grammar the gate does, so a Description
    edited during the prompt into something that only mentions this tool
    stops the delete exactly as one with no marker at all does."""
    summary, calls, _, _ = _list(
        _config(), [TITLE, "DELETE NON-EMPTY"],
        flags={"afterPrompt": {
            "Description": f"Now only prose about {MARKER_PREFIX} and nothing more",
        }},
    )

    assert summary["skipped"] == {"list": TITLE, "reason": "changed-during-confirmation"}
    assert _deletes(calls) == [] and _recycles(calls) == []


def test_a_drain_that_fails_part_way_reports_what_it_already_recycled() -> None:
    """Items that reached the recycle bin before the failure are in it
    whatever the run does next, and an operator told none were moved has no
    reason to go and restore them."""
    summary, calls, _, _ = _list(
        _config(items=_TWO_ITEMS), [TITLE, "DELETE NON-EMPTY"],
        flags={"recycleStatus": 403, "recycleFailsAfter": 1},
    )

    assert summary["recycled_items"] == 1
    assert len(_recycles(calls)) == 2, "it stopped at the item that failed"
    assert summary["deleted"] is None
    assert _deletes(calls) == []


def test_a_delete_that_answers_200_while_the_list_stays_is_not_a_delete() -> None:
    """The failure this project exists to close, one level up from a column:
    the write reports success and nothing happened. An operator told "Deleted
    X" stops looking for X."""
    summary, _, _, _ = _list(
        _config(), [TITLE, "DELETE NON-EMPTY"],
        flags={"discardListDelete": True, "absentList": "lingers"},
    )

    assert summary["deleted"] is None
    assert summary["aborted"] == "write-failed"
    assert "has NOT been deleted" in summary["errors"][0]["error"]


def test_a_readback_that_cannot_settle_it_says_so_rather_than_claiming_a_delete() -> None:
    """A 500 on the readback is not absence. Reporting a delete off it would
    record a list as gone on the strength of a request that failed."""
    summary, _, _, _ = _list(
        _config(), [TITLE, "DELETE NON-EMPTY"], flags={"absentList": "unreadable"},
    )

    assert summary["deleted"] is None
    assert "is gone is unknown" in summary["errors"][0]["error"]


def test_the_documented_absent_400_counts_as_gone() -> None:
    """Measured on a live list for a field (#383, 2026-09-03): a by-GUID read
    of a just-deleted object answered 400, not 404. Treating only 404 as gone
    read a successful delete as a failure."""
    summary, _, _, _ = _list(
        _config(), [TITLE, "DELETE NON-EMPTY"], flags={"absentList": "absent400"},
    )

    assert summary["deleted"] == {"list": TITLE, "id": LIST_ID}


def test_a_discarded_unlock_stops_the_run_before_the_list_is_deleted() -> None:
    """A MERGE SharePoint discards answers 204 exactly as one it applied
    does, so the readback is the only thing that counts.

    The items are in the recycle bin by the time this is discovered, because
    the drain runs first. That is what the second prompt authorised and it is
    restorable; the list is not deleted and its lock was never taken off, so
    nothing here is a state the operator cannot walk back.
    """
    summary, calls, _, _ = _list(
        _config(items=_TWO_ITEMS, allow_deletion=False),
        [TITLE, "DELETE NON-EMPTY"],
        flags={"discardListMerge": True},
    )

    assert summary["aborted"] == "readback-mismatch"
    assert _deletes(calls) == []
    assert len(_recycles(calls)) == 2
    assert summary["recycled_items"] == 2
    assert summary["relocked"] is None, "the lock was never taken off"


def test_a_delete_that_fails_after_unlocking_puts_the_lock_back() -> None:
    """Leaving a list unlocked that the deploy had locked is a state the
    operator did not ask for and would not know to look for."""
    summary, calls, _, _ = _list(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        flags={"listDeleteStatus": 403},
    )

    assert summary["deleted"] is None
    assert summary["aborted"] == "write-failed"
    relocks = [
        c for c in calls
        if c["body"] and c["body"].get("AllowDeletion") is False
    ]
    assert len(relocks) == 1, "the lock this run took off was not put back"
    assert summary["relocked"] is True
    after = calls.index(relocks[0])
    assert any(
        c["method"] == "GET" and "$select=Id,AllowDeletion" in c["url"]
        for c in calls[after + 1:]
    ), "the lock was reported restored without being read back"


def test_a_re_lock_the_site_discards_is_not_reported_as_restored() -> None:
    """The MERGE that puts the lock back gets the readback the MERGE that
    took it off already gets. A discarded write answers 204 the same as one
    that took, and this is the line that tells the operator the protection
    is there."""
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"listDeleteStatus": 403, "discardRelockMerge": True},
    )
    summary = _parse(out)[0]

    assert summary["relocked"] is False
    assert "its deletion lock is back" not in out
    assert "is still UNLOCKED and was not deleted" in out


def test_an_unlock_whose_readback_fails_still_puts_the_lock_back() -> None:
    """A readback that FAILED is not a readback that answered false.

    The MERGE took here and the GET that would confirm it did not arrive, so
    the list is standing unlocked. Recording the unlock only once its readback
    succeeds leaves the re-lock skipped, the run aborting on a list the deploy
    had protected and anybody can now delete, and nothing in the transcript
    saying so.
    """
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"lockReadbackFailsAt": 1},
    )
    summary, calls, _, _ = _parse(out)

    assert summary["deleted"] is None
    assert _deletes(calls) == [], "it deleted a list on an unlock it never read back"
    relocks = [
        c for c in calls
        if c["body"] and c["body"].get("AllowDeletion") is False
    ]
    assert len(relocks) == 1, "the lock the unlock may have taken off was left off"
    assert summary["relocked"] is True
    assert "its deletion lock is back" in out


def test_an_unlock_that_could_not_be_read_back_reads_as_unknown_not_as_locked() -> None:
    """And when the re-lock fails too, the report says which of the two
    states it cannot tell apart.

    The unlock's readback never arrived, so whether the lock came off is
    unknown; a line saying the list is still UNLOCKED would state a fact this
    run does not have, and one saying it is locked would send the operator
    away from a list that may be standing open.
    """
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"lockReadbackFailsAt": 1, "discardRelockMerge": True},
    )
    summary = _parse(out)[0]

    assert summary["deleted"] is None
    assert summary["relocked"] is False
    assert "whether its deletion lock came off is UNKNOWN" in out
    assert "is still UNLOCKED" not in out
    assert "protection-script" in out


def test_a_delete_whose_answer_is_lost_is_settled_by_the_id() -> None:
    """A fetch that rejects says nothing about whether SharePoint applied the
    DELETE. The list really went here, and reporting the transport failure as
    a failed delete would send the operator looking for a list that is gone,
    so the id is what settles it."""
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"listDeleteThrows": True},
    )
    summary = _parse(out)[0]

    assert summary["deleted"] == {"list": TITLE, "id": LIST_ID}
    assert summary["errors"] == []
    assert "never answered" in out


def test_a_delete_that_never_answered_and_never_happened_says_so() -> None:
    """The other outcome of the same rejected fetch: the list is still there,
    which the readback by id reports as the delete not having happened rather
    than as a transport error the operator has to interpret."""
    summary = _list(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        flags={"listDeleteThrows": True, "discardListDelete": True},
    )[0]

    assert summary["deleted"] is None
    assert "has NOT been deleted" in summary["errors"][0]["error"]
    assert "never answered" in summary["errors"][0]["error"]
    assert summary["relocked"] is True, "the lock was not put back on a list still there"


def test_a_delete_that_never_answered_and_cannot_be_read_back_is_unknown() -> None:
    """Neither the transport nor the readback settled it, so the list's fate
    is unknown and must read that way. A run reporting "was not deleted" off a
    request that never answered claims the opposite of what happened here."""
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"listDeleteThrows": True, "absentList": "unreadable"},
    )
    summary = _parse(out)[0]

    assert summary["deleted"] is None
    assert "is gone is unknown" in summary["errors"][0]["error"]
    assert "could not be confirmed deleted" in out
    assert "was not deleted" not in out


def test_an_unsettled_delete_is_not_rewritten_into_a_list_that_survived() -> None:
    """A readback that could not settle the delete leaves the list unknown.

    If it really went, the re-lock then fails because there is nothing to
    lock, and the line reporting that must not turn "unknown" into "was not
    deleted": an operator reading that stops looking for the list.
    """
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"absentList": "unreadable"},
    )
    summary = _parse(out)[0]

    assert summary["deleted"] is None
    assert summary["relocked"] is False
    assert "is gone is unknown" in out
    assert "could not be confirmed deleted" in out
    assert "was not deleted" not in out


def test_an_item_added_after_the_drain_stops_the_delete() -> None:
    """The drain's last read is not the state the DELETE acts on.

    Another user can add a row between the read that came back empty and the
    delete, and that row is destroyed with the list rather than recycled. The
    window cannot be closed, so the list is read empty once more immediately
    before the DELETE and a run that finds anything refuses. The lock this
    run took off goes back on, because the list is still there.
    """
    summary, calls, _, _ = _list(
        _config(items=_TWO_ITEMS, allow_deletion=False),
        [TITLE, "DELETE NON-EMPTY"],
        flags={"itemArrivesBeforeRead": 3},
    )

    assert summary["deleted"] is None
    assert _deletes(calls) == [], "it deleted a list holding a row it never recycled"
    assert summary["recycled_items"] == 2
    assert "was added to" in summary["errors"][0]["error"]
    # Named apart from a failed write: nothing here failed, the run refused.
    assert summary["aborted"] == "items-arrived"
    assert summary["relocked"] is True


@pytest.mark.parametrize(("items", "allow_deletion"), [
    (_TWO_ITEMS, False),
    # Nothing to recycle and no lock to take off, so this run reaches the
    # delete having written nothing and holding no cached digest. Without the
    # warm-up, the contextinfo POST lands between the check and the DELETE.
    ([], True),
], ids=["items-and-a-lock", "nothing-written-yet"])
def test_the_final_drain_check_is_the_last_request_before_the_delete(
    items: list[dict[str, Any]], allow_deletion: bool,
) -> None:
    """What narrowing the window means, and the part of it that can be
    pinned: no request at all stands between the read that found the list
    empty and the DELETE."""
    summary, calls, _, _ = _list(
        _config(items=items, allow_deletion=allow_deletion),
        [TITLE, "DELETE NON-EMPTY"],
    )

    assert summary["deleted"] == {"list": TITLE, "id": LIST_ID}
    delete_at = next(i for i, c in enumerate(calls) if _method(c) == "DELETE")
    before = calls[delete_at - 1]
    assert before["method"] == "GET" and "/items?" in before["url"], before


def test_the_run_says_the_window_it_cannot_close_before_it_asks() -> None:
    """The script's promise has to match what it can do. "Items are recycled
    first and stay restorable" over-reaches for a row that arrives during the
    run, and the operator reads that line before typing anything."""
    out = _list_output(_config(items=_TWO_ITEMS), ["not the title"])
    summary = _parse(out)[0]

    assert summary["skipped"] == {"list": TITLE, "reason": "title-not-typed"}
    assert "is NOT restorable" in out
    assert "that window cannot be closed" in out


def test_a_confirming_read_that_never_answered_leaves_the_delete_unknown() -> None:
    """The same class one level in. The DELETE may have gone through and the
    GET that would confirm it can reject just as the DELETE can, so a run
    that treats the rejection as a plain fetch error reports a list "was not
    deleted" when it is gone."""
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"absentList": "never-answers"},
    )
    summary = _parse(out)[0]

    assert summary["deleted"] is None
    assert "is gone is unknown" in summary["errors"][0]["error"]
    assert "could not be confirmed deleted" in out
    assert "was not deleted" not in out


def test_a_confirming_read_whose_body_never_arrived_leaves_the_delete_unknown() -> None:
    """The same class one request further in again. The readback's STATUS
    arrived and its body did not, and a 400 is only the documented absent one
    if the body says so, so the read has not settled the delete either."""
    out = _list_output(
        _config(allow_deletion=False), [TITLE, "DELETE NON-EMPTY"],
        {"absentList": "body-never-arrives"},
    )
    summary = _parse(out)[0]

    assert summary["deleted"] is None
    assert "is gone is unknown" in summary["errors"][0]["error"]
    assert "could not be confirmed deleted" in out
    assert "was not deleted" not in out


def test_a_refused_item_recycle_stops_before_the_list_is_deleted() -> None:
    """The items are recycled so the delete is survivable. A recycle that
    failed means they are not, and deleting the list then takes them
    permanently."""
    summary, calls, _, _ = _list(
        _config(items=_TWO_ITEMS), [TITLE, "DELETE NON-EMPTY"],
        flags={"recycleStatus": 403},
    )

    assert summary["deleted"] is None
    assert _deletes(calls) == []
    assert "recycle of item 1 failed" in summary["errors"][0]["error"]


@pytest.mark.parametrize("continuation", [False, 0, True, 1, [], {}])
def test_malformed_field_continuation_stops_before_maintenance(
    continuation: Any,
) -> None:
    js = generate_protection_js(
        site_url=SITE, list_title=LIST_SLUG, list_path=LIST_PATH,
        generated_at=GENERATED_AT,
    )
    script = _wrap(js, _config(), ["unlock"], {"fieldNext": continuation})
    script = script.rstrip().removesuffix(";") + (
        ".catch((err) => { console.log('__ERROR__' + err.message);"
        "console.log('__CALLS__' + JSON.stringify(calls)); });"
    )
    output = _run(script)
    assert "malformed OData __next" in output
    calls_line = next(line for line in output.splitlines() if line.startswith("__CALLS__"))
    assert _writes(_tag(calls_line, "__CALLS__")) == []


@pytest.mark.parametrize("continuation", [False, 0, True, 1, [], {}])
def test_malformed_value_continuation_requires_non_empty_confirmation(
    continuation: Any,
) -> None:
    summary, calls, prompts, _tables = _columns(
        _config(), ["ColumnTwo", "ColumnTwo", ""], {"itemNext": continuation},
    )
    assert any("could not be read" in p and "DELETE NON-EMPTY" in p for p in prompts)
    assert any("malformed OData __next" in p for p in prompts)
    assert _writes(calls) == []
    assert summary["skipped"] == [{"column": "ColumnTwo", "reason": "not-confirmed"}]


@pytest.mark.parametrize("continuation", [None, ""])
def test_valid_maintenance_terminators_allow_empty_column_deletion(continuation: Any) -> None:
    summary, calls, prompts, _tables = _columns(
        _config(), ["ColumnTwo", "ColumnTwo", ""],
        {"fieldNext": continuation, "itemNext": continuation},
    )
    assert summary["deleted"] == ["ColumnTwo"]
    assert len(_deletes(calls)) == 1
    assert not any("DELETE NON-EMPTY" in p for p in prompts)



def test_later_maintenance_pages_find_columns_and_their_values() -> None:
    summary, calls, prompts, tables = _columns(
        _config(items=[{"Id": 1, "ColumnTwo": 42}]),
        ["ColumnTwo", "ColumnTwo", ""], {"pageFields": True, "pageItems": True},
    )
    assert any("holds values" in p and "DELETE NON-EMPTY" in p for p in prompts)
    assert any(table == [{"item": 1, "value": 42}] for table in tables)
    assert _writes(calls) == []
    assert summary["skipped"] == [{"column": "ColumnTwo", "reason": "not-confirmed"}]
