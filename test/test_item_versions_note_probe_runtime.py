"""Execute item-versions-note-probe.js under node against the item-versions mock web.

Each case reaches one branch of the probe: a healthy run, each fixture failing, the versions
read refused, throttled or paged, and the masking of text once no display name is known.
"""

import json
from typing import Any

import pytest
from _node import NODE
from _paths import MANUAL
from _probe_runs import catalogued_dependents, ended_with_report, run_probe, voided
from _versions_mock import VERSIONS_MOCK, mock_list_id

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")

PROBE = MANUAL / "item-versions-note-probe.js"
USER = "field.version.control-current-user"
LIST = "field.version.fixture-note-list"
COLUMN = "field.version.fixture-note-column"
ITEM = "field.version.fixture-note-item"
READ = "field.version.control-note-versions-read"
NOTE = "field.version.payload-note"
FIXTURES = (USER, LIST, COLUMN, ITEM, READ)
NOTE_TEXTS = ('Reviewed; "partly" met.\nSee gaps;#2.', "Second: 'met'.\nNone;# \"open\".")
TITLE = "dbmlsp Probe NoteVersions"
LIST_AT = f"{mock_list_id(TITLE)}')"
READ_RULE = f"{LIST_AT}/items(1)/versions"
NEXT = {"odata.nextLink": "https://example.sharepoint.com/sites/probe/_api/web/lists/versions"}


def _run(gates: tuple[str, ...] = ("CONFIRMED", "ALLOW_WRITES"), **config: Any,
         ) -> tuple[dict[str, dict[str, str]], list[dict[str, str]], str]:
    return run_probe(VERSIONS_MOCK, PROBE, gates, config)


def _deps(fixture: str) -> set[str]:
    return catalogued_dependents(PROBE.name, fixture)


def _recycled(sent: list[dict[str, str]]) -> list[str]:
    return [r["path"] for r in sent if r["path"].endswith("/recycle")]


@pytest.mark.parametrize("gates", [(), ("CONFIRMED",)], ids=["unconfirmed", "no-writes"])
def test_without_both_gates_the_probe_sends_nothing(gates: tuple[str, ...]) -> None:
    rows, sent, _ = _run(gates)

    assert sent == []
    assert rows == {}


def test_each_version_records_the_note_property_verbatim() -> None:
    rows, sent, output = _run()

    for row_id in FIXTURES:
        assert rows[row_id]["outcome"] == "PASS", rows[row_id]
    row = rows[NOTE]
    assert row["outcome"] == "OBSERVED"
    assert row["state"] == "settled"
    assert row["evidence"] == (
        "3 version(s) in the order answered; properties beginning ProbeNote: ProbeNote; "
        f"3.0: {{ProbeNote={json.dumps(NOTE_TEXTS[1])}}}; "
        f"2.0: {{ProbeNote={json.dumps(NOTE_TEXTS[0])}}}; 1.0: {{ProbeNote=(absent)}}")
    assert len(_recycled(sent)) == 1
    assert ended_with_report(output)


def test_the_column_is_created_as_plain_multi_line_text() -> None:
    _, sent, _ = _run()

    [made] = [r for r in sent if r["path"].endswith("/fields") and r["verb"] == "POST"]
    body = json.loads(made["body"])
    assert body["FieldTypeKind"] == 3
    assert body["RichText"] is False


def test_a_note_read_back_unlike_what_was_sent_fails_the_item_and_voids_the_observation() -> None:
    rows, sent, _ = _run(mergeTakes={"2": {"ProbeNote": "changed on the way in"}})

    assert rows[ITEM]["outcome"] == "FAIL"
    assert voided(rows) == _deps(ITEM)
    assert NOTE in voided(rows)
    assert len(_recycled(sent)) == 1


def test_a_note_column_that_reads_back_as_rich_text_voids_what_rests_on_it() -> None:
    rows, _, _ = _run(fieldsTake={"ProbeNote": {"RichText": True}})

    assert rows[COLUMN]["outcome"] == "FAIL"
    assert "RichText differs: read true, declared false" in rows[COLUMN]["evidence"]
    assert voided(rows) == _deps(COLUMN)


def test_a_refused_column_create_voids_what_follows() -> None:
    rows, sent, _ = _run(rules=[{"contains": "/fields", "verb": "POST", "status": 500,
                                 "text": "not supported"}])

    assert rows[COLUMN]["outcome"] == "FAIL"
    assert voided(rows) == _deps(COLUMN)
    assert len(_recycled(sent)) == 1


def test_a_list_whose_versioning_does_not_stick_voids_everything_after_it() -> None:
    rows, _, _ = _run(listMerge={"EnableVersioning": False})

    assert rows[LIST]["outcome"] == "FAIL"
    assert voided(rows) == _deps(LIST)


def test_an_account_read_back_with_no_id_voids_everything_and_writes_nothing() -> None:
    rows, sent, _ = _run(rules=[{"contains": "web/currentuser", "status": 200,
                                 "text": '{"Id": 0}'}])

    assert rows[USER]["outcome"] == "FAIL"
    assert voided(rows) == _deps(USER)
    assert not [r for r in sent if r["verb"] != "GET" and r["path"] != "contextinfo"]


def test_a_versions_read_with_a_continuation_is_not_comparable() -> None:
    rows, _, output = _run(versionsNext=NEXT, versionsNextFor=f"{LIST_AT}/items(1)")

    assert rows[READ]["outcome"] == "PASS"
    assert rows[NOTE]["outcome"] == "NOT COMPARABLE"
    assert rows[NOTE]["state"] == "open"
    assert "which this probe does not follow" in rows[NOTE]["evidence"]
    assert ended_with_report(output)


@pytest.mark.parametrize("status", [400, 500])
def test_a_refused_versions_read_voids_the_observation(status: int) -> None:
    rows, sent, _ = _run(rules=[{"contains": READ_RULE, "status": status, "text": "refused"}])

    assert rows[READ]["outcome"] == "FAIL"
    assert voided(rows) == _deps(READ)
    assert len(_recycled(sent)) == 1


@pytest.mark.parametrize("status", [429, 503, 403])
def test_a_throttled_or_denied_versions_read_leaves_the_observation_open(status: int) -> None:
    rows, _, _ = _run(rules=[{"contains": READ_RULE, "status": status, "text": "busy"}])

    assert rows[READ]["outcome"] == "NOT ESTABLISHED"
    assert rows[NOTE]["state"] == "open"
    assert "a re-run can ask it" in rows[NOTE]["evidence"]


def test_a_versions_answer_with_no_entries_fails_the_control() -> None:
    rows, _, _ = _run(rules=[{"contains": READ_RULE, "status": 200, "text": '{"value": []}'}])

    assert rows[READ]["outcome"] == "FAIL"
    assert voided(rows) == _deps(READ)


def test_a_version_entry_carrying_no_note_property_is_recorded_absent() -> None:
    rows, _, _ = _run(versionsOmit=["ProbeNote"])

    assert rows[NOTE]["outcome"] == "ABSENT"
    assert rows[NOTE]["state"] == "settled"


def test_without_a_display_name_no_note_text_is_quoted_and_the_fixtures_still_hold() -> None:
    rows, _, output = _run(me={"Id": 7, "Email": "ada@example.com",
                               "LoginName": "i:0#.f|membership|ada@example.com"})

    assert rows[ITEM]["outcome"] == "PASS"
    assert rows[NOTE]["outcome"] == "OBSERVED"
    assert "Second:" not in rows[NOTE]["evidence"]
    assert ended_with_report(output)
