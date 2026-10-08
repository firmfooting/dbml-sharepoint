"""Execute file-move-probe.js under node against a mock web, leg by leg.

Each leg is pasted alone on a live site, so each runs alone here, on the state the leg
before it leaves. The probe records what a move does and never decides it, so these tests
pin the rows it fills and the rows a failed fixture voids, never a verdict.
"""

import json
from typing import Any

import pytest
from _file_move_mock import FILE_MOVE_MOCK
from _node import NODE, run_node
from _paths import MANUAL
from _probe_runs import catalogued_dependents, ended_with_report, run_probe, voided

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "file-move-probe.js"
ROOT = "/sites/probe/dbmlspProbeFileMove"
FOLDER = f"{ROOT}/Move & Folder, A"
FILE = "dbmlsp move probe.txt"
LOGINS = {
    "  const TEST_USER_LOGIN = 'CHANGE ME - the editing account claims login';":
        "  const TEST_USER_LOGIN = 'i:0#.f|membership|editor@example.com';",
    "  const MOVER_LOGIN = 'CHANGE ME - the moving account claims login';":
        "  const MOVER_LOGIN = 'i:0#.f|membership|mover@example.com';",
}
CLEANUP = {"  const CLEANUP = false;": "  const CLEANUP = true;"}
ANSWERED = "library.file.fixture-move-answered"
LIBRARY = "library.file.fixture-move-library"
F1 = "library.file.move-keeps-id-and-versions"
F2 = "library.file.move-keeps-column-values"
F3 = "library.file.move-system-fields"
F4 = "library.file.move-keeps-unique-permissions"
F5 = "library.file.move-adds-version"
F6 = "library.folder.recycle-empty-restorable"
FOREIGN = "A library the probe did not make."
OWNER_ROW = "library.folder.fixture-owner-account"
BEFORE_PERMS = "library.file.fixture-move-permissions-before"
BEFORE = "library.file.fixture-move-before"
LINK_URL = "https://example.sharepoint.com/:t:/s/probe/link"

Run = tuple[dict[str, dict[str, str]], list[dict[str, str]], str]


def _state_three_start() -> dict[str, Any]:
    """What STATE 1 and STATE 2 leave: the file in the folder with three versions."""
    return {
        "library": True, "folders": [FOLDER], "unique": True, "grants": [8],
        "links": [LINK_URL],
        "file": {"id": 41, "path": f"{FOLDER}/{FILE}",
                 "values": {"MoveChoice": "Q2", "MovePersonId": 7,
                            "MoveDate": "2026-01-15T00:00:00Z", "MoveFlag": True,
                            "MoveLink": {"Url": "https://example.org/x", "Description": "x"}},
                 "versions": ["1.0", "2.0", "3.0"], "created": "2026-10-01T00:00:00Z",
                 "author": 7, "modified": "2026-10-02T00:00:00Z", "editor": 8},
    }


def _state_four_start() -> dict[str, Any]:
    """What STATE 3 leaves: the file moved to the root, the folder empty."""
    start = _state_three_start()
    start["file"]["path"] = f"{ROOT}/{FILE}"
    return start


def _fnv(text: str) -> str:
    """The probe's link digest: 32-bit FNV-1a of the URL, as eight hex digits."""
    h = 0x811C9DC5
    for ch in text.encode("utf-8"):
        h = ((h ^ ch) * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _digest_swap(url: str = LINK_URL) -> dict[str, str]:
    return {"  const LINK_DIGEST = '';": f"  const LINK_DIGEST = '{_fnv(url)}';"}


def _leg(leg: int, me: int, swaps: dict[str, str] | None = None, /, **config: Any) -> Run:
    """Paste STATE `leg` as site user `me`; `config` reaches the mock, its `state` included."""
    # A swap must change the probe, and STATE 1 is what it ships with.
    pasted = {} if leg == 1 else {"  const STATE = 1;": f"  const STATE = {leg};"}
    digest = _digest_swap() if leg in (3, 5) and not config.pop("no_digest", False) else {}
    swaps = {**LOGINS, **pasted, **digest, **(swaps or {})}
    return run_probe(FILE_MOVE_MOCK, PROBE, ("CONFIRMED", "ALLOW_WRITES"),
                     {"me": me, **config}, swaps, pin=False)


def _printed(output: str) -> str:
    """What the probe printed, without the mock's own record of the requests it saw."""
    return "\n".join(ln for ln in output.splitlines() if not ln.startswith("__SENT__"))


def _writes(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    """Every request but a read and the digest it takes to write."""
    return [s for s in sent if s["verb"] != "GET" and not s["path"].startswith("contextinfo")]


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = run_probe(FILE_MOVE_MOCK, PROBE, gates, {}, LOGINS, pin=False)
    assert [s for s in sent if s["verb"] != "GET"] == []
    assert all(r["state"] != "settled" for r in rows.values())


def test_with_the_logins_left_as_placeholders_the_probe_sends_nothing() -> None:
    _, sent, output = run_probe(FILE_MOVE_MOCK, PROBE, ("CONFIRMED", "ALLOW_WRITES"), {}, pin=False)
    assert sent == []
    assert "TEST_USER_LOGIN" in output


def test_state_one_builds_the_fixture_in_a_folder_with_an_ampersand_and_a_comma() -> None:
    rows, sent, output = _leg(1, 7)
    assert rows["library.file.fixture-move-library"]["outcome"] == "PASS"
    assert rows["library.file.fixture-move-folder"]["outcome"] == "PASS"
    assert any("AddUsingPath" in s["path"] and "Move & Folder, A" in s["path"] for s in sent)
    assert rows["library.file.fixture-move-values"]["outcome"] == "PASS"
    assert rows["library.file.fixture-move-unique-grant"]["outcome"] == "PASS"
    assert rows["library.file.fixture-move-sharing-link"]["outcome"] == "PASS"
    assert ended_with_report(output)
    assert "editor@example.com" not in _printed(output)


def test_state_one_never_builds_on_a_library_that_already_stands() -> None:
    rows, sent, _ = _leg(1, 7, state={"library": True})
    assert rows[LIBRARY]["outcome"] == "FAIL"
    assert voided(rows) == set(rows) - {LIBRARY, OWNER_ROW}
    assert _writes(sent) == []


def test_a_refused_sharing_link_voids_only_what_rests_on_it() -> None:
    rows, _, _ = _leg(1, 7, linkRefused=True)
    assert rows["library.file.fixture-move-sharing-link"]["outcome"] == "FAIL"
    assert rows["library.file.fixture-move-unique-grant"]["outcome"] == "PASS"
    assert voided(rows) == {BEFORE_PERMS, F4}


def test_state_two_edits_the_file_once() -> None:
    start = _state_three_start()
    start["file"]["versions"] = ["1.0", "2.0"]
    _, sent, output = _leg(2, 8, state=start)
    assert [s["verb"] for s in _writes(sent)] == ["MERGE"]
    assert ended_with_report(output)


def test_state_two_edits_nothing_when_the_file_is_not_in_the_folder() -> None:
    _, sent, output = _leg(2, 8, state=_state_four_start())
    assert _writes(sent) == []
    assert ended_with_report(output)


def test_a_leg_on_a_library_the_probe_did_not_make_writes_nothing() -> None:
    start = {**_state_three_start(), "description": FOREIGN}
    rows, sent, _ = _leg(4, 9, state=start)
    assert _writes(sent) == []
    assert all(r["state"] != "settled" for r in rows.values())


def test_state_three_records_a_move_that_keeps_everything() -> None:
    rows, sent, output = _leg(4, 9, state=_state_three_start())
    assert rows[ANSWERED]["outcome"] == "PASS"
    assert any("MoveToUsingPath" in s["path"] for s in sent)
    assert rows[F1]["outcome"] == "ID AND VERSIONS KEPT"
    assert rows[F2]["outcome"] == "EVERY VALUE KEPT"
    assert rows[F5]["outcome"] == "NO VERSION ADDED"
    assert "Editor: the editing account -> the editing account" in rows[F3]["evidence"]
    assert "editor@example.com" not in _printed(output)
    assert "mover@example.com" not in _printed(output)


def test_state_three_records_what_a_move_changes_without_failing() -> None:
    move = {"newId": True, "addsVersion": True, "editorBecomesMover": True, "dropsValues": True}
    rows, _, _ = _leg(4, 9, state=_state_three_start(), move=move)
    assert rows[F1]["outcome"] == "ID CHANGED"
    assert rows[F2]["outcome"] == "VALUES CHANGED"
    assert rows[F5]["outcome"] == "VERSION ADDED"
    assert "Editor: the editing account -> the moving account" in rows[F3]["evidence"]
    assert all(rows[c]["state"] == "settled" for c in (F1, F2, F3, F5))


def test_a_refused_move_voids_every_row_resting_on_it() -> None:
    rows, _, _ = _leg(4, 9, state=_state_three_start(), moveRefused=True)
    assert rows[ANSWERED]["outcome"] == "FAIL"
    assert "move refused" in rows[ANSWERED]["evidence"]
    for check in catalogued_dependents(PROBE.name, ANSWERED):
        assert rows[check]["state"] == "void", check


def test_a_moved_file_that_cannot_be_read_leaves_every_observation_open() -> None:
    rows, _, output = _leg(4, 9, state=_state_three_start(), afterReadRefused=True)
    assert rows[ANSWERED]["outcome"] == "PASS"
    assert all(rows[c]["state"] == "open" for c in (F1, F2, F3, F5))
    assert ended_with_report(output)


def test_a_mover_who_is_also_the_editor_voids_the_system_fields_row() -> None:
    rows, sent, _ = _leg(4, 8, state=_state_three_start())
    assert rows["library.file.fixture-move-before"]["outcome"] == "FAIL"
    assert rows[F3]["state"] == "void"
    assert not any("MoveToUsingPath" in s["path"] for s in sent)


def test_state_four_records_the_grant_and_link_after_the_move() -> None:
    rows, _, _ = _leg(5, 7, state=_state_four_start())
    assert rows[F4]["outcome"] == "GRANT AND LINK PRESENT"


@pytest.mark.parametrize(("change", "head"), [
    ({"linksShape": "nested"}, "GRANT AND LINK PRESENT"),
    ({"grants": []}, "GRANT LOST"),
    ({"links": []}, "LINK LOST"),
    ({"grants": [], "links": []}, "GRANT AND LINK LOST"),
    ({"linksShape": "none"}, "NOT ESTABLISHED"),
], ids=["nested-links", "grant-lost", "link-lost", "both-lost", "no-links-array"])
def test_state_four_names_what_the_move_left_of_the_grant_and_link(
        change: dict[str, Any], head: str) -> None:
    start = _state_four_start()
    config = {k: v for k, v in change.items() if k == "linksShape"}
    start.update({k: v for k, v in change.items() if k != "linksShape"})
    rows, _, _ = _leg(5, 7, state=start, **config)
    assert rows[F4]["outcome"] == head


def test_state_four_recycles_the_empty_folder_and_restores_it() -> None:
    rows, sent, _ = _leg(5, 7, state=_state_four_start())
    assert rows["library.folder.fixture-recycle-empty"]["outcome"] == "PASS"
    assert rows[F6]["outcome"] == "RECYCLED AND RESTORED"
    assert any(s["path"].endswith("/recycle()") for s in sent)
    assert any(s["path"].endswith("/restore()") for s in sent)


def test_a_folder_that_still_holds_the_file_is_never_recycled() -> None:
    rows, sent, _ = _leg(5, 7, state=_state_three_start())
    assert rows["library.folder.fixture-recycle-empty"]["outcome"] == "FAIL"
    assert rows[F6]["state"] == "void"
    assert not any(s["path"].endswith("/recycle()") for s in sent)


def test_a_refused_restore_is_recorded_not_raised() -> None:
    rows, _, output = _leg(5, 7, state=_state_four_start(), restoreRefused=True)
    assert rows[F6]["outcome"] == "RECYCLED, NOT RESTORED"
    assert "UNHANDLED" not in output


def test_a_refused_recycle_is_recorded_as_refused() -> None:
    rows, sent, output = _leg(5, 7, state=_state_four_start(), recycleRefused=True)
    assert rows[F6]["outcome"] == "REFUSED"
    assert not any("RecycleBin(" in s["path"] for s in sent)
    assert ended_with_report(output)


def test_only_the_bin_item_the_recycle_returned_is_restored() -> None:
    start = _state_four_start()
    start["recycle"] = [{"Id": "bin-0", "LeafName": "Move & Folder, A", "DirName": ROOT[1:]}]
    rows, sent, _ = _leg(5, 7, state=start)
    assert rows[F6]["outcome"] == "RECYCLED AND RESTORED"
    restores = [s["path"] for s in sent if s["path"].endswith("/restore()")]
    assert restores == ["web/RecycleBin('bin-1')/restore()"]


def test_a_recycle_that_returns_no_item_id_restores_nothing() -> None:
    rows, sent, _ = _leg(5, 7, state=_state_four_start(), recycleNoId=True)
    assert rows[F6]["outcome"] == "NOT ESTABLISHED"
    assert not any("RecycleBin(" in s["path"] for s in sent)


def test_an_unreadable_bin_item_leaves_the_restore_question_open() -> None:
    rows, sent, _ = _leg(5, 7, state=_state_four_start(), binRefused=True)
    assert rows[F6]["state"] == "open"
    assert not any(s["path"].endswith("/restore()") for s in sent)


def test_an_invalid_state_is_refused_before_any_request() -> None:
    swaps = {"  const STATE = 1;": "  const STATE = 7;"}
    _, sent, output = _leg(7, 7, swaps, state=_state_four_start())
    assert sent == []
    assert "STATE" in output


def test_state_one_types_the_url_value_and_reads_the_date_back() -> None:
    rows, sent, _ = _leg(1, 7)
    assert rows["library.file.fixture-move-values"]["outcome"] == "PASS"
    reads = [s["path"] for s in sent if s["verb"] == "GET" and "$select" in s["path"]]
    assert any("MoveDate" in p for p in reads)


def test_a_date_that_did_not_store_fails_the_values_fixture() -> None:
    rows, _, _ = _leg(1, 7, dropsDate=True)
    assert rows["library.file.fixture-move-values"]["outcome"] == "FAIL"


def test_state_one_prints_the_digest_of_the_link_it_made() -> None:
    _, _, output = _leg(1, 7)
    assert f"link digest: {_fnv(LINK_URL)}" in _printed(output)


def test_state_four_without_the_link_digest_sends_nothing() -> None:
    _, sent, output = _leg(5, 7, state=_state_four_start(), no_digest=True)
    assert sent == []
    assert "LINK_DIGEST" in output


def test_a_binding_seen_while_inheritance_was_restored_is_not_a_grant() -> None:
    start = _state_four_start()
    start["unique"] = False
    rows, _, _ = _leg(5, 7, state=start)
    assert rows[F4]["outcome"] == "GRANT LOST"


@pytest.mark.parametrize(("change", "head"), [
    ({"links": ["https://example.sharepoint.com/:t:/s/probe/other"]}, "LINK REPLACED"),
    ({"links": ["https://example.sharepoint.com/:t:/s/probe/other"], "grants": []},
     "GRANT LOST, LINK REPLACED"),
], ids=["replaced", "grant-lost-and-replaced"])
def test_a_regenerated_link_is_told_from_the_original(change: dict[str, Any], head: str) -> None:
    rows, _, _ = _leg(5, 7, state={**_state_four_start(), **change})
    assert rows[F4]["outcome"] == head


def test_state_four_as_another_account_voids_what_rests_on_the_owner_and_writes_nothing() -> None:
    rows, sent, _ = _leg(5, 8, state=_state_four_start())
    assert rows[OWNER_ROW]["outcome"] == "FAIL"
    assert voided(rows) == {BEFORE_PERMS, F4, "library.folder.fixture-recycle-empty", F6}
    assert _writes(sent) == []


def test_cleanup_recycles_the_probe_library_by_its_id() -> None:
    _, sent, output = _leg(1, 7, CLEANUP, state={"library": True})
    recycles = [s["path"] for s in sent if s["path"].endswith("/recycle")]
    assert len(recycles) == 1 and "lists(guid'" in recycles[0]
    assert ended_with_report(output)


def test_cleanup_never_touches_a_same_title_library_it_did_not_make() -> None:
    _, sent, _ = _leg(1, 7, CLEANUP, state={"library": True, "description": FOREIGN})
    assert _writes(sent) == []


def test_the_probe_voids_what_the_catalogue_says_rests_on_each_fixture() -> None:
    """The probe's own dependency table is the catalogue's, so a failure voids what it should."""
    source = PROBE.read_text(encoding="utf-8")
    block = source[source.index("  const DEPENDS = {"):]
    block = block[:block.index("\n  };\n") + len("\n  };\n")]
    table = json.loads(run_node(f"{block}\nconsole.log(JSON.stringify(DEPENDS));").splitlines()[-1])
    catalog = json.loads((MANUAL / "probe-catalog.json").read_text(encoding="utf-8"))
    [entry] = [p for p in catalog["probes"] if p["file"] == PROBE.name]
    declared = {finding["id"]: finding["depends_on"] for scenario in entry["scenarios"]
                for finding in scenario["findings"] if finding["depends_on"]}
    assert table == declared


def _changes(sent: list[dict[str, str]]) -> list[dict[str, str]]:
    """Writes other than GetSharingInformation, a POST that only reads."""
    return [w for w in _writes(sent) if "GetSharingInformation" not in w["path"]]


def test_state_three_is_an_owner_read_of_the_grant_and_link_that_writes_nothing() -> None:
    rows, sent, output = _leg(3, 7, state=_state_three_start())
    assert rows[BEFORE_PERMS]["outcome"] == "PASS"
    assert rows[OWNER_ROW]["outcome"] == "PASS"
    assert _changes(sent) == []
    assert ended_with_report(output)


def test_the_moving_account_reads_no_role_assignments_or_sharing_information() -> None:
    _, sent, _ = _leg(4, 9, state=_state_three_start())
    assert any("MoveToUsingPath" in s["path"] for s in sent)
    assert not any("roleassignments" in s["path"] or "GetSharingInformation" in s["path"]
                   for s in sent)


@pytest.mark.parametrize(("change", "config"), [
    ({"grants": []}, {}),
    ({"links": ["https://example.sharepoint.com/:t:/s/probe/other"]}, {}),
    ({"unique": False}, {}),
    ({"grantRoles": {8: [1073741827]}}, {}),
    ({}, {"grantsRefused": True}),
], ids=["grant-gone", "link-replaced", "inheriting", "other-level", "unreadable"])
def test_a_grant_or_link_that_does_not_hold_before_the_move_voids_only_f4(
        change: dict[str, Any], config: dict[str, Any]) -> None:
    rows, sent, _ = _leg(3, 7, state={**_state_three_start(), **change}, **config)
    assert rows[BEFORE_PERMS]["outcome"] == "FAIL"
    assert voided(rows) == {F4}
    assert _changes(sent) == []


def test_state_three_as_another_account_voids_the_snapshot_and_reads_no_grants() -> None:
    rows, sent, _ = _leg(3, 8, state=_state_three_start())
    assert rows[OWNER_ROW]["outcome"] == "FAIL"
    assert rows[BEFORE_PERMS]["state"] == "void"
    assert not any("roleassignments" in s["path"] for s in sent)


def test_state_three_needs_the_link_digest_before_it_sends_anything() -> None:
    _, sent, output = _leg(3, 7, state=_state_three_start(), no_digest=True)
    assert sent == []
    assert "LINK_DIGEST" in output


def test_a_changed_permission_level_is_a_lost_grant_after_the_move() -> None:
    start = {**_state_four_start(), "grantRoles": {8: [1073741827]}}
    rows, _, _ = _leg(5, 7, state=start)
    assert rows[F4]["outcome"] == "GRANT LOST"
    assert "1073741827" in rows[F4]["evidence"]


def test_an_editing_account_that_does_not_resolve_leaves_f4_open() -> None:
    swaps = {"  const TEST_USER_LOGIN = 'CHANGE ME - the editing account claims login';":
             "  const TEST_USER_LOGIN = 'i:0#.f|membership|nobody@example.com';"}
    rows, _, _ = _leg(5, 7, swaps, state=_state_four_start())
    assert rows[F4]["outcome"] == "NOT ESTABLISHED"


def test_a_fourth_account_pasting_state_three_moves_nothing() -> None:
    rows, sent, _ = _leg(4, 10, state=_state_three_start())
    assert rows[BEFORE]["outcome"] == "FAIL"
    assert "the moving account" not in rows[BEFORE]["evidence"].split("read ")[-1]
    assert not any("MoveToUsingPath" in s["path"] for s in sent)


@pytest.mark.parametrize("me", [7, 9, 10])
def test_state_two_edits_nothing_unless_the_editing_account_pastes_it(me: int) -> None:
    start = _state_three_start()
    start["file"]["versions"] = ["1.0", "2.0"]
    _, sent, output = _leg(2, me, state=start)
    assert _writes(sent) == []
    assert "editing account" in output


@pytest.mark.parametrize(("where", "fields"), [
    ("omitBefore", ["Created"]), ("omitBefore", ["MoveChoice"]), ("omitBefore", ["EditorId"]),
], ids=["created", "choice", "editor"])
def test_a_before_read_missing_a_field_stops_before_the_move(where: str, fields: list[str]) -> None:
    rows, sent, _ = _leg(4, 9, state=_state_three_start(), **{where: fields})
    assert rows[BEFORE]["outcome"] == "FAIL"
    assert not any("MoveToUsingPath" in s["path"] for s in sent)


@pytest.mark.parametrize(("fields", "open_rows", "settled"), [
    (["Modified"], {F3}, {F1, F2, F5}),
    (["AuthorId"], {F3}, {F1, F2, F5}),
    (["MoveFlag"], {F2}, {F1, F3, F5}),
    (["MoveChoice", "MoveDate"], {F2}, {F1, F3, F5}),
], ids=["modified", "author", "flag", "two-columns"])
def test_a_moved_item_missing_a_field_leaves_only_the_rows_that_need_it_open(
        fields: list[str], open_rows: set[str], settled: set[str]) -> None:
    rows, _, _ = _leg(4, 9, state=_state_three_start(), omitAfter=fields)
    for row in open_rows:
        assert rows[row]["outcome"] == "NOT ESTABLISHED", row
    for row in settled:
        assert rows[row]["state"] == "settled", row


def test_a_moved_item_whose_versions_carry_no_label_leaves_the_version_rows_open() -> None:
    rows, _, _ = _leg(4, 9, state=_state_three_start(), versionsUnlabelled=True)
    assert all(rows[c]["state"] == "open" for c in (F1, F2, F3, F5))


def test_an_added_version_does_not_make_the_original_versions_lost() -> None:
    rows, _, _ = _leg(4, 9, state=_state_three_start(), move={"addsVersion": True})
    assert rows[F1]["outcome"] == "ID AND VERSIONS KEPT"
    assert rows[F5]["outcome"] == "VERSION ADDED"


def test_a_dropped_version_label_is_a_versions_change() -> None:
    rows, _, _ = _leg(4, 9, state=_state_three_start(), move={"dropsLabel": True})
    assert rows[F1]["outcome"] == "VERSIONS CHANGED"


@pytest.mark.parametrize("config", [{"rootUrlMissing": True}, {"rootRefused": True}],
                         ids=["no-url", "refused"])
@pytest.mark.parametrize("leg", [1, 2, 3, 4, 5])
def test_a_library_root_without_a_url_stops_every_leg_before_a_path_is_built(
        leg: int, config: dict[str, Any]) -> None:
    me = {1: 7, 2: 8, 3: 7, 4: 9, 5: 7}[leg]
    state = {} if leg == 1 else _state_three_start()
    _, sent, output = _leg(leg, me, state=state, **config)
    assert not any("null" in s["path"] or "undefined" in s["path"] for s in sent)
    built = ("Folders/AddUsingPath", "MoveToUsingPath", "GetFolderByServerRelativePath",
             "GetFileByServerRelativePath")
    assert not any(b in s["path"] for s in sent for b in built)
    assert ended_with_report(output)
