# test/test_rollback_runtime.py
"""Execute the generated rollback.js against a mock SharePoint.

The generation tests prove what the teardown SAYS. These run it. #293
removed the automatic demo-prefix bypass, and a static assertion can only
show the bypass is absent from the text; only a run shows that a list of
`[DEMO] `-titled rows now reaches the same DELETE NON-EMPTY prompt as any
other non-empty list, and that cancelling it writes nothing.

Node is required; the tests skip without it rather than failing, since it
is not a dependency of the package.
"""

import json
import textwrap
from typing import Any

import pytest
from _model import as_library
from _node import NODE
from _node import run_node as _run
from _paths import FIXTURES

from dbml_sharepoint.analysis.list_description import family_for, marker_for
from dbml_sharepoint.generators.rollbackgen import generate_rollback_js
from dbml_sharepoint.model.mapping_loader import load_mapping
from dbml_sharepoint.model.parser import parse_dbml
from dbml_sharepoint.model.release import load_release

_SCHEMA = parse_dbml(FIXTURES / "simple.dbml")
_MARKER = {
    f"APP_{entity}": marker_for(family_for(_SCHEMA), entity)
    for entity in ("Project", "Task")
}
_DEMO = "[DEMO] "

# The mock answers the site-leaf prompt itself; ANSWERS carries only the
# per-list replies under test, which is what every test here is about.
_HARNESS = textwrap.dedent(r"""
    const CONFIG = {};
    const ANSWERS = [];
    const PAGED_TITLES = [];
    const FAIL_SECOND_PAGE = false;
    const calls = [];
    const prompts = [];
    globalThis.window = { location: { origin: 'https://example.sharepoint.com' } };
    globalThis._spPageContextInfo = {
      webServerRelativeUrl: '/sites/test',
      userLoginName: 'probe@example.com',
      userId: 1,
    };
    const answers = ANSWERS.slice();
    globalThis.prompt = (message) => {
      prompts.push(message);
      if (message.includes('site leaf path')) return 'test';
      return answers.length ? answers.shift() : 'no';
    };

    // ItemCount is carried separately from the rows so a list can be asked
    // about and read from independently, as the live script does.
    const state = {};
    for (const [title, spec] of Object.entries(CONFIG)) {
      state[title] = {
        count: spec.count,
        description: spec.description,
        id: spec.id,
        // The deletion lock, what the DELETE answers, and whether the write
        // that puts the lock BACK is discarded. Rollback unlocks a locked
        // list, deletes it and re-locks when that delete fails, and the mock
        // could not reach any of those three until it carried these.
        allowDeletion: spec.allowDeletion === undefined ? true : spec.allowDeletion,
        deleteStatus: spec.deleteStatus,
        // A DELETE whose fetch REJECTS, which is what a dropped connection
        // looks like to the script, and which AllowDeletion read fails the
        // same way. Neither is a refusal: the site keeps whatever the request
        // before it wrote.
        deleteThrows: spec.deleteThrows === true,
        allowDeletionReadFailsAt: spec.allowDeletionReadFailsAt,
        allowDeletionReads: 0,
        discardRelock: spec.discardRelock === true,
        // How many item recycles succeed before the rest are refused.
        recycleFailsAfter: spec.recycleFailsAfter,
        recycledOk: 0,
        // What the site says on every ownership read after the first, which
        // is the window between the confirmation prompt and the first
        // destructive write. Undefined means nothing changes in it.
        afterPrompt: spec.afterPrompt,
        // What the by-id readback after the DELETE answers. Undefined is a
        // list that really went; 'lingers' answers 200 and 'unreadable' 500.
        afterDelete: spec.afterDelete,
        ownershipReads: 0,
        rows: spec.titles.map((t, i) => ({ Id: i + 1, Title: t })),
        deleted: false,
      };
    }

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

    globalThis.fetch = async (url, opts = {}) => {
      const u = String(url);
      const method = opts.method || 'GET';
      const headers = opts.headers || {};
      const body = opts.body ? JSON.parse(opts.body) : null;
      calls.push({ url: u, method, headers, body });
      if (u.includes('contextinfo')) {
        return reply(200, { d: { GetContextWebInformation: {
          FormDigestValue: 'digest', FormDigestTimeoutSeconds: 1800 } } });
      }
      if (u.includes('EffectiveBasePermissions')) {
        return reply(200, { d: { EffectiveBasePermissions: {
          Low: 0x800 | 0x2000000, High: 0 } } });
      }
      if (u.includes('web/lists?$select=Title,ItemCount') || u.includes('__list_page=2')) {
        const secondPage = u.includes('__list_page=2');
        if (secondPage && FAIL_SECOND_PAGE) {
          return reply(500, { error: { message: { value: 'page failed' } } });
        }
        const results = Object.entries(state)
          .filter(([Title]) => PAGED_TITLES.includes(Title) === secondPage)
          .map(([Title, s]) => ({ Title, ItemCount: s.count }));
        const d = { results };
        if (!secondPage && PAGED_TITLES.length) {
          d.__next = 'https://example.sharepoint.com/sites/test/_api/__list_page=2';
        }
        return reply(200, { d });
      }
      // The post-delete confirmation, addressed by list id so a same-titled
      // replacement cannot answer for the list this run deleted.
      const byGuid = /\/lists\(guid'([^']+)'\)/.exec(u);
      if (byGuid) {
        const entry = Object.values(state).find((x) => x.id === byGuid[1]);
        if (entry && entry.afterDelete === 'lingers') {
          return reply(200, { d: { Id: entry.id } });
        }
        if (entry && entry.afterDelete === 'unreadable') {
          return reply(500, { error: { message: { value: 'readback failed' } } });
        }
        // The confirming GET can drop exactly as the DELETE can, and its body
        // can fail after its status arrives. Neither answers the question.
        if (entry && entry.afterDelete === 'never-answers') {
          throw new TypeError('Failed to fetch');
        }
        if (entry && entry.afterDelete === 'body-never-arrives') {
          return bodyFails(400);
        }
        return reply(404, { error: { message: { value: 'list not found' } } });
      }
      const match = /getbytitle\('([^']+)'\)/.exec(u);
      const s = match ? state[decodeURIComponent(match[1])] : null;
      if (!s) return reply(404, { error: { message: { value: 'list not found' } } });
      if (u.includes('$select=Id,Description')) {
        // The ownership read happens twice per list: once to classify it and
        // once again after the confirmation prompt returns. `afterPrompt`
        // lets a test change what the site says between the two, which is
        // the whole window this guard exists to cover.
        s.ownershipReads = (s.ownershipReads || 0) + 1;
        const after = s.ownershipReads > 1 && s.afterPrompt ? s.afterPrompt : null;
        const description = after && 'description' in after
          ? after.description : s.description;
        const id = after && 'id' in after ? after.id : s.id;
        return description === null
          ? reply(500, { error: { message: { value: 'description unreadable' } } })
          : reply(200, { d: { Id: id, Description: description } });
      }
      if (u.includes('$select=AllowDeletion')) {
        s.allowDeletionReads += 1;
        if (s.allowDeletionReadFailsAt === s.allowDeletionReads) {
          return reply(500, { error: { message: { value: 'AllowDeletion unreadable' } } });
        }
        return reply(200, { d: { AllowDeletion: s.allowDeletion } });
      }
      const recycled = /\/items\((\d+)\)\/recycle\(\)/.exec(u);
      if (recycled) {
        const cap = s.recycleFailsAfter === undefined ? Infinity : s.recycleFailsAfter;
        if (s.recycledOk >= cap) {
          return reply(403, { error: { message: { value: 'recycle refused' } } });
        }
        s.recycledOk += 1;
        s.rows = s.rows.filter((row) => row.Id !== Number(recycled[1]));
        return reply(200, { d: { Recycle: '00000000-0000-0000-0000-000000000000' } });
      }
      if (u.includes('/items?')) return reply(200, { d: { results: s.rows } });
      if (method === 'POST' && headers['X-HTTP-Method'] === 'DELETE') {
        if (s.deleteStatus) {
          return reply(s.deleteStatus, { error: { message: { value: 'delete refused' } } });
        }
        s.deleted = true;
        // Thrown after the delete is applied, so `deleteThrows` is a DELETE
        // SharePoint took whose answer never reached the browser.
        if (s.deleteThrows) throw new TypeError('Failed to fetch');
        return reply(200, {});
      }
      if (method === 'POST' && headers['X-HTTP-Method'] === 'MERGE') {
        const relock = body && body.AllowDeletion === false;
        if (body && 'AllowDeletion' in body && !(s.discardRelock && relock)) {
          s.allowDeletion = body.AllowDeletion;
        }
        return reply(204, {});
      }
      return reply(200, {});
    };
""")


def _rollback_js() -> str:
    return generate_rollback_js(
        schema=_SCHEMA,
        bundle=load_mapping(FIXTURES / "sharepoint-mapping.yaml"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


def _library_rollback_js() -> str:
    """The same fixture with APP_Task declared as a document library."""
    return generate_rollback_js(
        schema=_SCHEMA,
        bundle=as_library(load_mapping(FIXTURES / "sharepoint-mapping.yaml"), "Task"),
        release=load_release(FIXTURES / "release.yaml"),
        site_url="https://example.sharepoint.com/sites/test",
        site_role="default",
        source_dbml="simple.dbml",
        generated_at="2026-05-04T00:00:00Z",
    )


#: A stand-in list GUID. Any well-formed value does: rollback compares the
#: one it read before the prompt against the one it reads after, and never
#: parses either.
_ID = "11111111-1111-4111-8111-111111111111"
_OTHER_ID = "22222222-2222-4222-8222-222222222222"


def _listing(
    list_title: str,
    titles: list[str],
    *,
    ours: bool = True,
    description: str | None = "",
    count: int | None = None,
    list_id: str = _ID,
    after_prompt: dict[str, Any] | None = None,
    after_delete: str | None = None,
    allow_deletion: bool = True,
    delete_status: int | None = None,
    delete_throws: bool = False,
    allow_deletion_read_fails_at: int | None = None,
    discard_relock: bool = False,
    recycle_fails_after: int | None = None,
) -> dict[str, Any]:
    """One list's live state. `description=None` means unreadable.

    `after_prompt` replaces `id` and/or `description` on every ownership read
    after the first, which is how a test puts a change inside the window
    between the confirmation and the first destructive write.

    `after_delete` is what the by-id readback answers once the DELETE has
    returned 200: 'lingers' for a list that is still there, 'unreadable' for
    a read that never answered the question, 'never-answers' for a fetch that
    rejects the way the DELETE's own can, and 'body-never-arrives' for a
    status that arrives while the body it has to be classified by does not.

    `allow_deletion=False` is a list the deploy locked, which rollback has to
    unlock before it can delete. `delete_status` refuses the DELETE, which is
    what sends rollback down the re-lock path; `discard_relock` then lets that
    re-lock answer success and keep the list unlocked, the failure a readback
    is the only way to see. `recycle_fails_after` refuses every item recycle
    past the first N.

    `delete_throws` rejects the DELETE's fetch after the site has applied it,
    which is a dropped connection rather than a refusal, and
    `allow_deletion_read_fails_at` fails the Nth AllowDeletion read: the
    probe is the first, the unlock's readback the second and the re-lock's
    the third.
    """
    if ours and description is not None:
        description = f"{_MARKER[list_title]} {description}".strip()
    state: dict[str, Any] = {
        "count": len(titles) if count is None else count,
        "description": description,
        "id": list_id,
        "titles": titles,
        "allowDeletion": allow_deletion,
    }
    if after_prompt is not None:
        state["afterPrompt"] = after_prompt
    if after_delete is not None:
        state["afterDelete"] = after_delete
    if delete_status is not None:
        state["deleteStatus"] = delete_status
    if delete_throws:
        state["deleteThrows"] = True
    if allow_deletion_read_fails_at is not None:
        state["allowDeletionReadFailsAt"] = allow_deletion_read_fails_at
    if discard_relock:
        state["discardRelock"] = True
    if recycle_fails_after is not None:
        state["recycleFailsAfter"] = recycle_fails_after
    return state


def _tag(line: str, marker: str) -> Any:
    return json.loads(line.removeprefix(marker))


def _rollback(
    lists: dict[str, dict[str, Any]],
    answers: list[str] | None = None,
    paged_titles: list[str] | None = None,
    fail_second_page: bool = False,
    js: str | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """Run rollback.js against the mock and return (summary, calls, prompts)."""
    return _parse(_rollback_output(lists, answers, paged_titles, fail_second_page, js))


def _rollback_output(
    lists: dict[str, dict[str, Any]],
    answers: list[str] | None = None,
    paged_titles: list[str] | None = None,
    fail_second_page: bool = False,
    js: str | None = None,
) -> str:
    """One run's whole output, for the tests that read its log lines.

    `_parse` reads the summary out of the same output, so a test asserting on
    both does not run the script twice.
    """
    harness = _HARNESS.replace(
        "const CONFIG = {};", f"const CONFIG = {json.dumps(lists)};", 1,
    ).replace(
        "const ANSWERS = [];", f"const ANSWERS = {json.dumps(answers or [])};", 1,
    ).replace(
        "const PAGED_TITLES = [];",
        f"const PAGED_TITLES = {json.dumps(paged_titles or [])};",
        1,
    ).replace(
        "const FAIL_SECOND_PAGE = false;",
        f"const FAIL_SECOND_PAGE = {json.dumps(fail_second_page)};",
        1,
    )
    body = (js or _rollback_js()).rstrip()
    assert body.endswith("})();")
    # Wrap the emitted IIFE rather than editing inside it, so what runs is
    # the artefact byte for byte.
    script = (
        f"{harness}\n({body[:-1]}).then((r) => {{\n"
        "  console.log('__RESULT__' + JSON.stringify(r));\n"
        "  console.log('__CALLS__' + JSON.stringify(calls));\n"
        "  console.log('__PROMPTS__' + JSON.stringify(prompts));\n"
        "});\n"
    )
    return _run(script)


def _parse(output: str) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    """The three JSON markers out of one run's output."""
    lines = output.splitlines()
    found = {
        marker: next((ln for ln in lines if ln.startswith(marker)), None)
        for marker in ("__RESULT__", "__CALLS__", "__PROMPTS__")
    }
    missing = [marker for marker, line in found.items() if line is None]
    assert not missing, f"rollback.js never reached {missing}:\n{output[-3000:]}"
    result_line = found["__RESULT__"]
    calls_line = found["__CALLS__"]
    prompts_line = found["__PROMPTS__"]
    assert result_line is not None and calls_line is not None and prompts_line is not None
    return (
        _tag(result_line, "__RESULT__"),
        _tag(calls_line, "__CALLS__"),
        _tag(prompts_line, "__PROMPTS__"),
    )


def _non_empty_prompts(prompts: list[str]) -> list[str]:
    return [p for p in prompts if "DELETE NON-EMPTY" in p]


def _writes(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every request that changes the site. The digest POST changes nothing."""
    return [c for c in calls if c["method"] == "POST" and "contextinfo" not in c["url"]]


def _recycles(calls: list[dict[str, Any]]) -> list[str]:
    return [c["url"] for c in calls if "/recycle()" in c["url"]]


def _skips(summary: dict[str, Any]) -> dict[str, str]:
    return {row["list"]: row["reason"] for row in summary["skipped"]}


pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def test_a_list_of_demo_titled_rows_still_asks_for_delete_non_empty() -> None:
    """The collision case #293 closed.

    `Title` is user-editable, so a real record can carry the prefix. The
    rows here are indistinguishable from seeded demo data by prefix alone,
    and a tool-provisioned list holding them must still be confirmed.
    """
    _, _, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}One", f"{_DEMO}Two", f"{_DEMO}Three"])},
    )
    asked = _non_empty_prompts(prompts)
    assert len(asked) == 1, f"expected one non-empty confirmation, got {prompts}"
    assert "APP_Task" in asked[0]


def test_cancelling_a_demo_titled_list_skips_it_and_writes_nothing() -> None:
    summary, calls, _ = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}One", f"{_DEMO}Two"])},
        answers=["no"],
    )
    assert _skips(summary)["APP_Task"] == "non-empty"
    assert "APP_Task" not in summary["deleted"]
    assert summary["errors"] == []
    assert _writes(calls) == []


def test_mixed_marked_and_unmarked_rows_never_bypass_the_prompt() -> None:
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}Sample", "Real record"])},
        answers=["no"],
    )
    assert len(_non_empty_prompts(prompts)) == 1
    assert _skips(summary)["APP_Task"] == "non-empty"
    assert _writes(calls) == []


def test_confirming_recycles_every_item_then_deletes_the_list() -> None:
    """No marker survives on the recycle path: the operator authorised
    deleting this list with its contents, and emptying it first is what
    makes the delete succeed under retention."""
    summary, calls, _ = _rollback(
        {
            "APP_Task": _listing(
                "APP_Task", [f"{_DEMO}Sample", "Real record", "Another record"],
            ),
        },
        answers=["DELETE NON-EMPTY"],
    )
    assert summary["deleted"] == ["APP_Task"]
    assert summary["errors"] == []
    assert len(_recycles(calls)) == 3
    deletes = [
        i for i, c in enumerate(calls)
        if c["method"] == "POST" and c["headers"].get("X-HTTP-Method") == "DELETE"
    ]
    last_recycle = max(
        i for i, c in enumerate(calls) if "/recycle()" in c["url"]
    )
    assert len(deletes) == 1
    assert last_recycle < deletes[0]


def test_a_list_still_reading_back_after_its_delete_is_not_reported_deleted() -> None:
    """HTTP 200 on the DELETE is the request being accepted, not the list
    being gone. An operator told "Deleted X" stops looking for X, so the
    absence is confirmed by list id before that line is printed."""
    summary, _calls, _ = _rollback(
        {"APP_Task": _listing("APP_Task", ["Real record"], after_delete="lingers")},
        answers=["DELETE NON-EMPTY"],
    )
    assert summary["deleted"] == []
    assert [e["error"] for e in summary["errors"]] == [
        ("the delete answered HTTP 200 and the list still reads back by its "
         f"id ({_ID}); it has NOT been deleted."),
    ], summary["errors"]


def test_a_confirmation_read_that_fails_leaves_the_delete_unreported() -> None:
    """The other half: a readback that never answered cannot confirm the
    deletion either, and reporting it as done would be the same claim."""
    summary, _calls, _ = _rollback(
        {"APP_Task": _listing("APP_Task", ["Real record"], after_delete="unreadable")},
        answers=["DELETE NON-EMPTY"],
    )
    assert summary["deleted"] == []
    assert "whether 'APP_Task' is gone is unknown" in summary["errors"][0]["error"]


def test_each_non_empty_list_is_confirmed_on_its_own() -> None:
    """One DELETE NON-EMPTY authorises one list. The second is asked again
    and its refusal leaves it standing."""
    summary, _, prompts = _rollback(
        {
            "APP_Task": _listing("APP_Task", [f"{_DEMO}Sample"]),
            "APP_Project": _listing("APP_Project", ["Real record"]),
        },
        answers=["DELETE NON-EMPTY", "no"],
    )
    assert len(_non_empty_prompts(prompts)) == 2
    assert summary["deleted"] == ["APP_Task"]
    assert _skips(summary)["APP_Project"] == "non-empty"


def test_a_document_library_is_confirmed_as_files_and_folders() -> None:
    """The operator should read the word for what is really being deleted.

    A library's items are files and folders, and recycling a folder takes its
    children with it (MEASURED 2026-09-03, `library.folder.delete-recycles`),
    so the prompt says so. The phrase that authorises the delete is the same
    one, and cancelling still writes nothing.
    """
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", ["Real record"])},
        answers=["no"],
        js=_library_rollback_js(),
    )
    (asked,) = _non_empty_prompts(prompts)
    assert "document library" in asked
    assert "every file and folder in it" in asked
    assert _skips(summary)["APP_Task"] == "non-empty"
    assert _writes(calls) == []


def test_a_list_is_never_described_as_a_library() -> None:
    """The other direction: the same fixture as a list says items, not files,
    so a generator that stopped telling the two apart turns this red."""
    _summary, _calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", ["Real record"])}, answers=["no"],
    )
    (asked,) = _non_empty_prompts(prompts)
    assert "document library" not in asked
    assert "currently reports 1 items" in asked


def test_a_list_this_family_never_provisioned_is_never_prompted_for() -> None:
    """The list-level provenance refusal is untouched by #293, and it comes
    first: a list that is not ours is not offered for confirmation at all."""
    summary, calls, prompts = _rollback(
        {
            "APP_Task": _listing(
                "APP_Task", [f"{_DEMO}One"], ours=False, description="somebody else's",
            ),
        },
    )
    assert _skips(summary)["APP_Task"] == "not-ours"
    assert _non_empty_prompts(prompts) == []
    assert _writes(calls) == []


def test_an_unreadable_description_is_never_prompted_for() -> None:
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}One"], description=None)},
    )
    assert _skips(summary)["APP_Task"] == "provenance-unreadable"
    assert _non_empty_prompts(prompts) == []
    assert _writes(calls) == []


def test_an_empty_list_still_requires_per_list_confirmation() -> None:
    """A zero count is a snapshot, not authority to delete without asking."""
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [])},
        answers=["no"],
    )
    assert len(_non_empty_prompts(prompts)) == 1
    assert _skips(summary)["APP_Task"] == "empty-unconfirmed"
    assert "APP_Task" not in summary["deleted"]
    assert _writes(calls) == []


def test_confirmed_empty_list_deletes_without_item_writes() -> None:
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [])},
        answers=["DELETE NON-EMPTY"],
    )
    assert len(_non_empty_prompts(prompts)) == 1
    assert summary["deleted"] == ["APP_Task"]
    assert _recycles(calls) == []


def test_stale_zero_count_with_live_rows_still_prompts_and_cancels_without_writes() -> None:
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}Real collision"], count=0)},
        answers=["no"],
    )
    assert len(_non_empty_prompts(prompts)) == 1
    assert _skips(summary)["APP_Task"] == "empty-unconfirmed"
    assert "APP_Task" not in summary["deleted"]
    assert _writes(calls) == []


def test_confirmed_stale_zero_count_recycles_live_rows_before_delete() -> None:
    summary, calls, _ = _rollback(
        {"APP_Task": _listing("APP_Task", ["Arrived after count"], count=0)},
        answers=["DELETE NON-EMPTY"],
    )
    assert summary["deleted"] == ["APP_Task"]
    assert len(_recycles(calls)) == 1
    recycle_index = next(i for i, call in enumerate(calls) if "/recycle()" in call["url"])
    delete_index = next(
        i for i, call in enumerate(calls)
        if call["method"] == "POST" and call["headers"].get("X-HTTP-Method") == "DELETE"
    )
    assert recycle_index < delete_index


def test_target_on_second_enumeration_page_is_still_confirmed() -> None:
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing("APP_Task", ["Real record"])},
        answers=["no"],
        paged_titles=["APP_Task"],
    )
    assert len(_non_empty_prompts(prompts)) == 1
    assert _skips(summary)["APP_Task"] == "non-empty"
    assert "APP_Task" not in summary["deleted"]
    assert _writes(calls) == []


def test_failed_later_enumeration_page_never_publishes_partial_absence() -> None:
    summary, calls, prompts = _rollback(
        {
            "APP_Task": _listing("APP_Task", ["First-page record"]),
            "APP_Project": _listing("APP_Project", ["Second-page record"]),
        },
        paged_titles=["APP_Project"],
        fail_second_page=True,
    )
    assert "APP_Task" not in summary["deleted"]
    assert summary["skipped"] == []
    assert len(summary["errors"]) == 3
    assert _non_empty_prompts(prompts) == []
    assert _writes(calls) == []
# --- The window between the confirmation and the first destructive write ---
#
# `prompt()` blocks for as long as a human takes to read and type, and the
# check that authorises a delete ran before it. Everything after it is
# irreversible in practice, so the classification is re-asked immediately
# before the first recycle. These four make that re-ask fire; without them
# the guard is a comment.


def test_a_marker_removed_during_the_prompt_stops_the_delete() -> None:
    """The plain case: it was ours when asked, and is not ours now."""
    summary, calls, prompts = _rollback(
        {"APP_Task": _listing(
            "APP_Task", [f"{_DEMO}One"],
            after_prompt={"description": "somebody else took this title"},
        )},
        answers=["DELETE NON-EMPTY"],
    )
    assert len(_non_empty_prompts(prompts)) == 1, "it never got as far as asking"
    assert "APP_Task" not in summary["deleted"]
    assert {"list": "APP_Task", "reason": "ownership-changed-during-confirmation"} \
        in summary["skipped"]
    # Nothing destructive may have happened, not even the recycle that runs
    # before the delete.
    assert not [c for c in calls if "/recycle" in c["url"]], "items were recycled anyway"
    assert not [
        c for c in calls
        if c["method"] == "POST" and c["headers"].get("X-HTTP-Method") == "DELETE"
    ], "the list was deleted anyway"


def test_a_same_titled_replacement_during_the_prompt_stops_the_delete() -> None:
    """The case the marker alone cannot see.

    A replacement can carry a copied Description, so it answers the marker
    question correctly while being a different object. The Id is what
    separates them, which is why the ownership read takes both.
    """
    summary, calls, _prompts = _rollback(
        {"APP_Task": _listing(
            "APP_Task", [f"{_DEMO}One"], after_prompt={"id": _OTHER_ID},
        )},
        answers=["DELETE NON-EMPTY"],
    )
    assert "APP_Task" not in summary["deleted"]
    assert {"list": "APP_Task", "reason": "ownership-changed-during-confirmation"} \
        in summary["skipped"]
    assert not [c for c in calls if "/recycle" in c["url"]]


def test_an_unreadable_recheck_stops_the_delete() -> None:
    """Fail closed, the same way the first check does.

    An answer that could not be read is not evidence of ownership and not
    evidence against it. Deleting on it would make an outage authorise the
    destruction it cannot describe.
    """
    summary, calls, _prompts = _rollback(
        {"APP_Task": _listing(
            "APP_Task", [f"{_DEMO}One"], after_prompt={"description": None},
        )},
        answers=["DELETE NON-EMPTY"],
    )
    assert "APP_Task" not in summary["deleted"]
    assert {"list": "APP_Task", "reason": "ownership-changed-during-confirmation"} \
        in summary["skipped"]
    assert not [c for c in calls if "/recycle" in c["url"]]


def test_an_unchanged_list_is_still_deleted_after_the_recheck() -> None:
    """The guard must not cost a correct rollback its delete.

    A second read that agrees with the first is the ordinary path, and it has
    to stay ordinary, or the fix would trade a rare wrong delete for a
    reliable failure to delete anything.
    """
    summary, calls, _prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}One"])},
        answers=["DELETE NON-EMPTY"],
    )
    assert "APP_Task" in summary["deleted"]
    assert not [r for r in summary["skipped"] if r["list"] == "APP_Task"]
    assert [c for c in calls if "/recycle" in c["url"]], "the item was never recycled"


def test_the_ownership_question_is_asked_exactly_twice() -> None:
    """Once to classify, once to re-confirm. Not once, and not per item."""
    _summary, calls, _prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}One", f"{_DEMO}Two"])},
        answers=["DELETE NON-EMPTY"],
    )
    reads = [c for c in calls if "$select=Id,Description" in c["url"]]
    assert len(reads) == 2, f"asked {len(reads)} times, expected 2"


def test_a_list_refused_at_the_prompt_is_never_rechecked() -> None:
    """A skip needs no second read: nothing destructive follows it.

    The re-ask exists to cover the window before a WRITE. Spending a request
    on a list the operator declined would be cost with nothing behind it.
    """
    _summary, calls, _prompts = _rollback(
        {"APP_Task": _listing("APP_Task", [f"{_DEMO}One"])},
        answers=["no"],
    )
    reads = [c for c in calls if "$select=Id,Description" in c["url"]]
    assert len(reads) == 1, f"asked {len(reads)} times, expected 1"


def _allow_deletion_writes(calls: list[dict[str, Any]], want: bool) -> list[int]:
    """Where in the run each AllowDeletion MERGE sits."""
    return [
        i for i, c in enumerate(calls)
        if c["body"] and c["body"].get("AllowDeletion") is want
    ]


def test_a_delete_that_fails_after_unlocking_puts_the_lock_back_and_reads_it_back() -> None:
    """Rollback unlocks a list the deploy locked, and puts the lock back when
    the delete then fails. That restore is a write like any other here, so it
    is read back before the operator is told the protection is there."""
    out = _rollback_output(
        {"APP_Task": _listing("APP_Task", [], allow_deletion=False, delete_status=403)},
        answers=["DELETE NON-EMPTY"],
    )
    summary, calls, _prompts = _parse(out)

    assert summary["deleted"] == []
    relocks = _allow_deletion_writes(calls, want=False)
    assert len(relocks) == 1, "the lock this run took off was not put back"
    assert any(
        c["method"] == "GET" and "$select=AllowDeletion" in c["url"]
        for c in calls[relocks[0] + 1:]
    ), "the lock was reported restored without being read back"
    assert "deletion block restored (read back)" in out


def test_a_re_lock_the_site_discards_is_not_reported_as_restored() -> None:
    """A MERGE SharePoint discards answers exactly as one it applied does, so
    the MERGE's own status cannot say the protection is back. This is the
    same guard `list.js` applies to the same write on the same property."""
    out = _rollback_output(
        {
            "APP_Task": _listing(
                "APP_Task", [], allow_deletion=False, delete_status=403,
                discard_relock=True,
            ),
        },
        answers=["DELETE NON-EMPTY"],
    )
    summary, _calls, _prompts = _parse(out)

    assert summary["deleted"] == []
    assert "could NOT be confirmed restored" in out
    assert "restored (read back)" not in out


def test_an_unlock_whose_readback_fails_still_puts_the_block_back() -> None:
    """A readback that FAILED is not a readback that answered false.

    The MERGE took and the GET that would confirm it did not arrive, so the
    list is standing unlocked. Recording the unlock only once its readback
    answers leaves the restore skipped, and a list the deploy protected is
    then deletable by anyone with nothing in the transcript saying so.
    """
    out = _rollback_output(
        {
            "APP_Task": _listing(
                "APP_Task", [], allow_deletion=False, allow_deletion_read_fails_at=2,
            ),
        },
        answers=["DELETE NON-EMPTY"],
    )
    summary, calls, _prompts = _parse(out)

    assert summary["deleted"] == []
    assert not [
        c for c in calls
        if c["method"] == "POST" and c["headers"].get("X-HTTP-Method") == "DELETE"
    ], "it deleted a list on an unlock it never read back"
    assert len(_allow_deletion_writes(calls, want=False)) == 1, (
        "the block the unlock may have taken off was left off"
    )
    assert "could not be read back" in summary["errors"][0]["error"]
    assert "restored (read back) after an unlock that could not be read back" in out


def test_a_delete_whose_answer_is_lost_is_settled_by_the_id() -> None:
    """A fetch that rejects says nothing about whether SharePoint applied the
    DELETE. The list really went here, and reporting the transport failure as
    a failed delete would send the operator looking for a list that is gone,
    so the id is what settles it."""
    out = _rollback_output(
        {"APP_Task": _listing("APP_Task", [], delete_throws=True)},
        answers=["DELETE NON-EMPTY"],
    )
    summary, _calls, _prompts = _parse(out)

    assert summary["deleted"] == ["APP_Task"]
    assert summary["errors"] == []
    assert "the DELETE never answered" in out


def test_a_delete_that_never_answered_and_never_happened_puts_the_block_back() -> None:
    """The other outcome of the same rejected fetch. The list is still there,
    which the readback by id reports as the delete not having happened, and
    the block this run took off goes back on: a stranded list is stranded
    however its delete failed."""
    out = _rollback_output(
        {
            "APP_Task": _listing(
                "APP_Task", [], allow_deletion=False, delete_throws=True,
                after_delete="lingers",
            ),
        },
        answers=["DELETE NON-EMPTY"],
    )
    summary, calls, _prompts = _parse(out)

    assert summary["deleted"] == []
    assert "the delete never answered and the list still reads back" in (
        summary["errors"][0]["error"]
    )
    assert len(_allow_deletion_writes(calls, want=False)) == 1, (
        "the block was left off on a list still standing"
    )
    assert "restored (read back) after a failed delete" in out


def test_an_unconfirmed_delete_puts_the_block_back_without_claiming_a_failure() -> None:
    """A delete the readback could not settle strands the list exactly as a
    refused one does, and the re-lock ran only on the refusal. What it says
    has to keep the uncertainty: the list may be gone, in which case this
    restore is the request that proves nothing was left unprotected."""
    out = _rollback_output(
        {
            "APP_Task": _listing(
                "APP_Task", [], allow_deletion=False, after_delete="unreadable",
            ),
        },
        answers=["DELETE NON-EMPTY"],
    )
    summary, calls, _prompts = _parse(out)

    assert summary["deleted"] == []
    assert "is gone is unknown" in summary["errors"][0]["error"]
    assert len(_allow_deletion_writes(calls, want=False)) == 1, (
        "a delete that could not be confirmed left the block off"
    )
    assert "after a delete that could not be confirmed" in out
    assert "after a failed delete" not in out


@pytest.mark.parametrize("after_delete", ["never-answers", "body-never-arrives"])
def test_a_confirming_read_that_never_answered_leaves_the_delete_unknown(
    after_delete: str,
) -> None:
    """The confirming GET can fail the way the DELETE it confirms can.

    A rejected fetch, and a status whose body never arrives, both leave this
    run knowing nothing about whether the list went. Reaching the catch with
    a bare transport error instead reported "a failed delete" for a list that
    may be gone, which is what `list.js` already settles by id. Same class,
    same posture: the lock goes back on, and what the run says keeps the
    uncertainty.
    """
    out = _rollback_output(
        {
            "APP_Task": _listing(
                "APP_Task", [], allow_deletion=False, after_delete=after_delete,
            ),
        },
        answers=["DELETE NON-EMPTY"],
    )
    summary, calls, _prompts = _parse(out)

    assert summary["deleted"] == []
    assert "is gone is unknown" in summary["errors"][0]["error"]
    assert len(_allow_deletion_writes(calls, want=False)) == 1, (
        "a delete that could not be confirmed left the block off"
    )
    assert "after a delete that could not be confirmed" in out
    assert "after a failed delete" not in out


def test_a_drain_that_fails_part_way_still_reports_what_it_recycled() -> None:
    """Items that reached the recycle bin before the failure are in it
    whatever the run does next, and a run that never names them leaves the
    operator no reason to go and restore them."""
    out = _rollback_output(
        {
            "APP_Task": _listing(
                "APP_Task", ["One", "Two", "Three"], recycle_fails_after=1,
            ),
        },
        answers=["DELETE NON-EMPTY"],
    )
    summary, calls, _prompts = _parse(out)

    assert summary["deleted"] == []
    assert "'APP_Task': recycled 1 item(s)" in out
    assert len(_recycles(calls)) == 2, "it stopped at the item that failed"
    assert "recycle of item 2 failed" in summary["errors"][0]["error"]


@pytest.mark.parametrize("continuation", [False, 0, True, 1, [], {}])
def test_malformed_list_continuation_never_publishes_partial_catalogue(
    continuation: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _HARNESS.replace(
        "const d = { results };",
        "const d = { results, __next: " + json.dumps(continuation) + " };",
    )
    monkeypatch.setattr(__name__ + "._HARNESS", harness)
    summary, calls, prompts = _rollback({"APP_Task": _listing("APP_Task", ["Record"])})
    assert summary["deleted"] == []
    assert summary["skipped"] == []
    assert len(summary["errors"]) == 3
    assert all("malformed OData __next" in error["error"] for error in summary["errors"])
    assert _non_empty_prompts(prompts) == []
    assert _writes(calls) == []


@pytest.mark.parametrize("continuation", [None, ""])
def test_valid_rollback_terminators_preserve_non_empty_confirmation(
    continuation: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _HARNESS.replace(
        "const d = { results };",
        "const d = { results, __next: " + json.dumps(continuation) + " };",
    )
    monkeypatch.setattr(__name__ + "._HARNESS", harness)
    summary, calls, prompts = _rollback({"APP_Task": _listing("APP_Task", ["Record"])})
    assert len(_non_empty_prompts(prompts)) == 1
    assert _skips(summary)["APP_Task"] == "non-empty"
    assert _writes(calls) == []
